import copy
from dataclasses import replace
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen
from urllib.error import HTTPError

import numpy as np

from igod_paper.engine import Engine, STEP, MAX_HOLD_BARS
from igod_paper.journal import Journal, JournalError
from igod_paper.market import DataError, PublicMarket, validate_rows, digest
from igod_paper.report import build, markdown, publish
from igod_paper.service import Service, environment_guard
from igod_paper.signals import confirmed_context
from igod_paper.__main__ import handler
from igod_paper.vendor.paper_engine_v0 import Config

T = 1_761_868_800_000


def candle(stamp, price=100., high=100.5, low=99.5, close=None, step=STEP):
    return [stamp, str(price), str(high), str(low), str(price if close is None else close),
            '10', stamp + step - 1, '1000', 10, '5.5', '550', '0']


def context(side='LONG', close=T, quality='GOOD'):
    return dict(bias=side + '_ALLOWED', entry_quality=quality, entry_reason='CONFIRMED_RECLAIM',
                entry_level=99. if side == 'LONG' else 101., resistance=110., support=90.,
                signal_close=close, trend1='BULL', trend4='BULL', momentum='GREEN',
                source='BINANCE_USDM_PERPETUAL', structure='BULLISH')


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.journal = Journal(self.tmp.name)
        self.addCleanup(lambda: self.journal.close())
        self.engine = Engine(self.journal, T + 1000)

    def observe(self, side='LONG', **kwargs):
        self.engine.observe(context(side, **kwargs), 1., T + 5000)

    def feed(self, stamp, **kwargs):
        self.engine.process_bar(candle(stamp, **kwargs), [], stamp + STEP + 5000)

    def enter(self, side='LONG'):
        self.observe(side)
        self.feed(T)
        self.feed(T + STEP)

    def test_first_start_is_forward_only(self):
        self.assertEqual([r['type'] for r in self.journal.records], ['FORWARD_START'])
        self.assertEqual(self.engine.state['trades'], 0)
        self.assertEqual(self.engine.state['last_bar'], T - STEP)

    def test_late_observation_never_fills_already_open_bar(self):
        self.observe()
        self.assertEqual(self.engine.state['pending']['entry_open'], T + STEP)
        self.feed(T)
        self.assertIsNone(self.engine.state['position'])
        self.feed(T + STEP)
        self.assertEqual(self.engine.state['position']['entry_ts'], T + STEP)

    def test_boundary_observation_schedules_strictly_later_open(self):
        self.engine.observe(context(), 1., T)
        self.assertEqual(self.engine.state['pending']['entry_open'], T + STEP)

    def test_future_signal_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.observe(context(close=T + 900_000), 1., T + 1000)

    def test_stale_signal_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.observe(context(), 1., T + 900_000)

    def test_caution_no_plan(self):
        self.observe(quality='CAUTION')
        self.assertIsNone(self.engine.state['pending'])

    def test_wait_no_plan(self):
        c = dict(context(), bias='WAIT')
        self.engine.observe(c, 1., T + 1000)
        self.assertIsNone(self.engine.state['pending'])

    def test_observation_dedupe(self):
        self.observe()
        count = len(self.journal.records)
        self.observe()
        self.assertEqual(len(self.journal.records), count)

    def test_bar_dedupe(self):
        self.feed(T)
        self.feed(T)
        self.assertEqual(self.engine.state['bars'], 1)

    def test_open_bar_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.process_bar(candle(T), [], T + STEP - 1)

    def test_gap_rejected_without_mutation(self):
        old = copy.deepcopy(self.engine.state)
        with self.assertRaises(ValueError):
            self.feed(T + STEP)
        self.assertEqual(self.engine.state, old)

    def test_stop_collision_long_is_loss(self):
        self.observe()
        self.feed(T)
        self.feed(T + STEP, high=110., low=90.)
        trade = build(self.journal)['trades'][0]
        self.assertEqual(trade['exit_reason'], 'STOP')
        self.assertTrue(trade['collision'])
        self.assertLess(trade['net_pnl'], 0)

    def test_stop_collision_short_is_loss(self):
        self.observe('SHORT')
        self.feed(T)
        self.feed(T + STEP, high=110., low=90.)
        self.assertEqual(build(self.journal)['trades'][0]['exit_reason'], 'STOP')

    def test_target_long_and_cost_accounting(self):
        self.enter()
        self.feed(T + 2 * STEP, high=104., low=99.5, close=103.)
        r = build(self.journal)
        trade = r['trades'][0]
        self.assertEqual(trade['exit_reason'], 'TARGET')
        self.assertGreater(trade['net_pnl'], 0)
        self.assertAlmostEqual(trade['net_pnl'], trade['gross_pnl'] - trade['fees'] - trade['funding'])
        self.assertAlmostEqual(r['realized_equity'], 140 + trade['net_pnl'])
        self.assertGreater(trade['entry'], 100.)
        self.assertLess(trade['exit'], trade['target'])

    def test_target_short(self):
        self.enter('SHORT')
        self.feed(T + 2 * STEP, high=100.5, low=96., close=97.)
        trade = build(self.journal)['trades'][0]
        self.assertEqual(trade['exit_reason'], 'TARGET')
        self.assertGreater(trade['net_pnl'], 0)

    def test_gap_stop_uses_worse_open(self):
        self.enter()
        self.feed(T + 2 * STEP, price=90., high=91., low=89.)
        self.assertLess(build(self.journal)['trades'][0]['exit'], 90.)

    def test_entry_structure_gap_blocks_plan(self):
        self.observe()
        self.feed(T)
        self.feed(T + STEP, price=95., high=96., low=94.)
        self.assertIsNone(self.engine.state['position'])
        self.assertEqual(self.journal.records[-1]['payload']['actions'][0]['reason'], 'STRUCTURE_INVALIDATED_BEFORE_ENTRY')

    def test_structure_invalidation_at_closed_15m_only(self):
        self.enter()
        self.feed(T + 2 * STEP, high=100.5, low=98.7, close=98.9)
        self.assertEqual(build(self.journal)['trades'][0]['exit_reason'], 'STRUCTURE_INVALIDATION')

    def test_time_exit_fixed_24h(self):
        self.enter()
        for index in range(2, MAX_HOLD_BARS + 1):
            self.feed(T + index * STEP)
        self.assertEqual(build(self.journal)['trades'][0]['exit_reason'], 'TIME_EXIT')

    def test_funding_long_debit_short_credit(self):
        for side in ('LONG', 'SHORT'):
            with self.subTest(side=side), tempfile.TemporaryDirectory() as directory:
                j = Journal(directory)
                try:
                    e = Engine(j, T + 1000)
                    e.observe(context(side), 1., T + 5000)
                    for i in range(2):
                        e.process_bar(candle(T + i * STEP), [], T + (i + 1) * STEP + 1000)
                    fund = dict(symbol='BTCUSDT', fundingTime=T + 2 * STEP, fundingRate='0.001', markPrice='100')
                    e.process_bar(candle(T + 2 * STEP), [fund], T + 3 * STEP + 1000)
                    self.assertGreater(e.state['funding'] * (1 if side == 'LONG' else -1), 0)
                finally:
                    j.close()

    def test_unknown_funding_does_not_advance_bar(self):
        self.enter()
        before = self.engine.state['last_bar']
        with self.assertRaises(ValueError):
            self.engine.process_bar(candle(T + 2 * STEP), None, T + 3 * STEP + 1000)
        self.assertEqual(self.engine.state['last_bar'], before)

    def test_duplicate_funding_rejected(self):
        self.enter()
        fund = dict(symbol='BTCUSDT', fundingTime=T + 2 * STEP, fundingRate='0.001', markPrice='100')
        with self.assertRaises(ValueError):
            self.engine.process_bar(candle(T + 2 * STEP), [fund, fund], T + 3 * STEP + 1000)

    def test_one_hundred_restarts_do_not_duplicate_or_change_equity(self):
        self.enter()
        expected, count = copy.deepcopy(self.engine.state), len(self.journal.records)
        for _ in range(100):
            self.journal.close()
            self.journal = Journal(self.tmp.name)
            self.engine = Engine(self.journal, T + 12 * STEP)
            self.assertEqual(self.engine.state, expected)
            self.assertEqual(len(self.journal.records), count)

    def test_recovery_only_uses_already_committed_plan(self):
        self.observe()
        self.journal.close()
        self.journal = Journal(self.tmp.name)
        self.engine = Engine(self.journal, T + 10 * STEP)
        for i in range(3):
            self.engine.process_bar(candle(T + i * STEP), [], T + 10 * STEP)
        self.assertEqual(self.engine.state['position']['entry_ts'], T + STEP)
        self.assertTrue(self.journal.records[-1]['payload']['recovery'])
        self.assertEqual(sum(r['type'] == 'SIGNAL_OBSERVED' for r in self.journal.records), 1)

    def test_config_change_refused_on_restart(self):
        with self.assertRaises(JournalError):
            Engine(self.journal, T + 1000, replace(Config(), reward_to_risk=2.))

    def test_nonfinite_config_refused(self):
        with self.assertRaises(ValueError):
            Engine(self.journal, T, replace(Config(), starting_equity=float('nan')))

    def test_position_entry_fee_is_immediately_deducted(self):
        self.enter()
        self.assertLess(self.engine.state['equity'], 140.)
        self.assertGreater(self.engine.state['fees'], 0)

    def test_paper_cap_and_stop_risk(self):
        self.enter()
        pos = self.engine.state['position']
        self.assertLessEqual(pos['qty'] * pos['entry'], 280)
        self.assertLessEqual(pos['risk_cash'], .7)

    def test_drawdown_includes_mark_and_exit_estimates(self):
        self.enter()
        self.assertGreater(self.engine.state['max_drawdown'], 0.)

    def second_plan(self, after_cooldown=False):
        first = 6 if after_cooldown else 3
        for i in range(3, first):
            self.feed(T + i * STEP)
        self.engine.observe(context(close=T + first * STEP), 1., T + first * STEP + 5000)
        self.feed(T + first * STEP)
        self.feed(T + (first + 1) * STEP)

    def test_daily_trade_limit_blocks_second_plan(self):
        self.engine.config = replace(self.engine.config, max_trades_day=1)
        self.enter()
        self.feed(T + 2 * STEP, high=104., close=103.)
        self.second_plan(after_cooldown=True)
        self.assertIsNone(self.engine.state['position'])
        self.assertEqual(self.journal.records[-1]['payload']['actions'][0]['reason'], 'TRADES_DAY')

    def test_daily_loss_guard_blocks_after_adverse_gap(self):
        self.enter()
        self.feed(T + 2 * STEP, price=90., high=91., low=89.)
        self.second_plan(after_cooldown=True)
        self.assertIsNone(self.engine.state['position'])
        self.assertEqual(self.journal.records[-1]['payload']['actions'][0]['reason'], 'DAILY_LOSS_OR_CAPITAL')

    def test_cooldown_blocks_second_plan(self):
        self.enter()
        self.feed(T + 2 * STEP, high=104., close=103.)
        self.second_plan()
        self.assertIsNone(self.engine.state['position'])
        self.assertEqual(self.journal.records[-1]['payload']['actions'][0]['reason'], 'COOLDOWN')

    def test_source_change_refused_on_restart(self):
        with patch('igod_paper.engine.source_identity', return_value={'changed': 'source'}):
            with self.assertRaises(JournalError):
                Engine(self.journal, T + 1000)

    def test_no_force_close_at_end(self):
        self.enter()
        self.assertEqual(build(self.journal)['closed_trades'], 0)
        self.assertIsNotNone(build(self.journal)['open_paper_position'])

    def test_prefix_invariance(self):
        self.enter()
        prefix = json.dumps(self.journal.records, sort_keys=True)
        self.feed(T + 2 * STEP, high=104., close=103.)
        self.assertEqual(json.dumps(self.journal.records[:-1], sort_keys=True), prefix)

    def test_report_counts_zero_sample_without_claims(self):
        r = build(self.journal)
        self.assertIsNone(r['win_rate'])
        self.assertEqual(r['closed_trades'], 0)
        self.assertIn('INSUFFICIENT', markdown(r))

    def test_fsync_failure_halts_and_never_retries_uncertain_append(self):
        before = len(self.journal.records)
        with patch('igod_paper.journal.os.fsync', side_effect=OSError('synthetic')):
            with self.assertRaises(JournalError):
                self.observe()
        self.assertEqual(len(self.journal.records), before)
        self.assertIsNone(self.engine.state['pending'])
        with self.assertRaises(JournalError):
            self.observe()


class JournalTests(unittest.TestCase):
    def make(self, directory):
        j = Journal(directory)
        Engine(j, T)
        j.close()
        return Path(directory) / 'paper_v0.jsonl'

    def test_truncated_tail_is_never_repaired(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d)
            p.write_bytes(p.read_bytes()[:-1])
            before = p.read_bytes()
            with self.assertRaises(JournalError):
                Journal(d)
            self.assertEqual(p.read_bytes(), before)

    def test_modified_history_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d)
            p.write_bytes(p.read_bytes().replace(b'140.0', b'141.0'))
            with self.assertRaises(JournalError):
                Journal(d)

    def test_duplicate_record_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d)
            p.write_bytes(p.read_bytes() * 2)
            with self.assertRaises(JournalError):
                Journal(d)

    def test_wrong_previous_hash_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d)
            row = json.loads(p.read_text())
            row['previous_hash'] = 'a' * 64
            row.pop('record_hash')
            row['record_hash'] = digest(row)
            p.write_text(json.dumps(row) + '\n')
            with self.assertRaises(JournalError):
                Journal(d)

    def test_single_writer_lock(self):
        with tempfile.TemporaryDirectory() as d:
            j = Journal(d)
            try:
                with self.assertRaises(JournalError):
                    Journal(d)
            finally:
                j.close()

    def test_derived_checkpoint_not_authoritative(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d)
            Path(d, 'paper_state.json').write_text('{bad')
            j = Journal(d)
            try:
                self.assertEqual(Engine(j, T + STEP).state['equity'], 140.)
            finally:
                j.close()


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.market = PublicMarket(self.session, clock=lambda: (T + 2000 * STEP) / 1000)
        self.response = self.session.get.return_value
        self.response.status_code = 200

    def test_exact_1500_pagination(self):
        pages = [[candle(T + i * STEP) for i in range(a, b)] for a, b in ((0, 1500), (1500, 1501))]
        self.response.json.side_effect = pages
        result = self.market.candles('5m', T, T + 1501 * STEP)
        self.assertEqual(len(result), 1501)
        self.assertEqual([c.kwargs['params']['limit'] for c in self.session.get.call_args_list], [1500, 1])
        self.assertTrue(all(not c.kwargs['allow_redirects'] for c in self.session.get.call_args_list))
        self.assertFalse(self.session.trust_env)

    def test_public_only(self):
        with self.assertRaises(DataError):
            self.market._get('/fapi/v1/order', {'symbol': 'BTCUSDT'})
        with self.assertRaises(DataError):
            self.market._get('/fapi/v1/klines', {'symbol': 'ETHUSDT'})

    def test_non200_and_redirect_no_fallback(self):
        for code in (301, 403, 451, 429, 500):
            with self.subTest(code=code):
                self.response.status_code = code
                with self.assertRaises(DataError):
                    self.market.candles('5m', T, T + STEP)

    def test_closed_only_request(self):
        with self.assertRaises(DataError):
            self.market.candles('5m', T, T + 2001 * STEP)

    def test_bad_row_variants_fail_closed(self):
        variants = []
        for key, value in ((0, T + 1), (6, T + STEP), (1, 'NaN'), (4, 'inf'), (9, '11'), (3, '-1'), (1, '200')):
            row = candle(T)
            row[key] = value
            variants.append([row])
        variants += [[], [candle(T)[:-1]], [candle(T), candle(T)], {'error': 'none'}]
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(DataError):
                validate_rows(rows, '5m', T, T + STEP)

    def test_gap_and_duplicate_rejected(self):
        for second in (T, T + 2 * STEP):
            with self.subTest(second=second), self.assertRaises(DataError):
                validate_rows([candle(T), candle(second)], '5m', T, T + 2 * STEP)

    def test_funding_empty_means_no_settlement_not_unknown(self):
        self.response.json.return_value = []
        self.assertEqual(self.market.funding(T, T + STEP), [])

    def test_funding_schema_checked(self):
        self.response.json.return_value = [dict(symbol='BTCUSDT', fundingTime=T, fundingRate='nan', markPrice='100')]
        with self.assertRaises(DataError):
            self.market.funding(T, T + STEP)


class ServiceTests(unittest.TestCase):
    def test_environment_refuses_credentials_without_printing_them(self):
        for name in ('BITUNIX_API_KEY', 'TELEGRAM_BOT_TOKEN', 'OTHER_SECRET', 'V8_LIVE_EXECUTION'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, '^PAPER_FORBIDDEN_ENVIRONMENT$'):
                environment_guard({name: 'private-test-value'})
        environment_guard({'PATH': 'normal', 'PORT': '8080'})

    def test_storage_never_accepts_production_data(self):
        for directory in ('/data', '/data/mlrsi', '/data/anything'):
            with self.subTest(directory=directory), self.assertRaises(RuntimeError):
                Service(directory)

    def test_no_old_signals_on_restart_or_market_failure(self):
        with tempfile.TemporaryDirectory() as d:
            market = Mock()
            market.history.side_effect = DataError('PUBLIC_HTTP_451')
            service = Service(d, market=market, clock=lambda: (T + 5000) / 1000)
            try:
                r = service.cycle()
                self.assertEqual(r['status'], 'DEGRADED')
                self.assertEqual(r['closed_trades'], 0)
                self.assertEqual([x['type'] for x in service.journal.records], ['FORWARD_START'])
                self.assertFalse(market.candles.called)
            finally:
                service.journal.close()

    def test_full_runner_mocked_feed_and_existing_pure_rules(self):
        with tempfile.TemporaryDirectory() as d:
            market = Mock()
            cutoff = T
            def history(tf, count, end):
                step = {'5m': STEP, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000}[tf]
                end = end // step * step
                return [candle(end - (count-i)*step, price=100 + i * .01 + .3*np.sin(i),
                               high=102 + i*.01, low=98 + i*.01, step=step) for i in range(count)]
            market.history.side_effect = history
            service = Service(d, market=market, clock=lambda: (T + 5000) / 1000)
            try:
                result = service.cycle()
                self.assertEqual(result['status'], 'HEALTHY')
                signals = [x for x in service.journal.records if x['type'] == 'SIGNAL_OBSERVED']
                self.assertEqual(len(signals), 1)
                self.assertEqual(signals[0]['payload']['context']['source'], 'BINANCE_USDM_PERPETUAL')
                self.assertTrue(Path(d, 'report.md').exists())
            finally:
                service.journal.close()

    def test_http_report_get_only_and_no_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'report.json').write_text('{"mode":"PAPER_ONLY"}')
            Path(d, 'report.md').write_text('SHADOW ONLY')
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler(d))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                for path in ('/health', '/', '/report.json', '/report.md'):
                    with urlopen(base + path) as response:
                        self.assertEqual(response.status, 200)
                for path in ('/../paper_v0.jsonl', '/api/v1/order'):
                    with self.assertRaises(HTTPError):
                        urlopen(base + path)
                with self.assertRaises(HTTPError) as e:
                    urlopen(base + '/report.json', data=b'not-an-order')
                self.assertEqual(e.exception.code, 405)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
