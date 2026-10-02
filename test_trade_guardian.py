"""Offline harness: transport fakes only, never real private GET or POST."""
from dataclasses import replace
from email.utils import formatdate
from pathlib import Path
import hashlib
import inspect
import json
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import requests
from guardian_bitunix import (Bitunix, signature, POSITIONS, TPSL, TICKERS, PAIRS, KLINES,
                              PLACE_SL, FLASH_CLOSE, GET_ALLOWLIST, POST_ALLOWLIST)
from guardian_risk import Config, SafetyError, parse_positions, risk, catastrophic_stop, assess_orders
from guardian_signals import (closed_bars, rolling_mlrsi, cluster_three, states_and_events,
                              confirmed_structure, direction, flow_state, atr14, latest_mlrsi,
                              volatility_state, snapshot)
from guardian_store import Store
from guardian_market import Market
from guardian_telegram import Telegram
from trade_guardian import Guardian


def position(**changes):
    row = dict(positionId='123', symbol='BTCUSDT', qty='0.1', side='LONG',
               marginMode='ISOLATION', positionMode='ONE_WAY', leverage=10,
               unrealizedPNL='-2', margin='100', liqPrice='9900', marginRate='0.01',
               avgOpenPrice='10100', ctime=1000, mtime=1000)
    row.update(changes)
    return row


ARMED = Config(mode='PROTECT', allow_sl=True, allow_close=True, arm_phrase='PROTECT_CAPITAL_ONLY')


class Response:
    status_code = 200
    def __init__(self, data):
        self.data = data
        self.headers = {'Date': formatdate(time.time(), usegmt=True)}
    def json(self):
        return {'code': 0, 'data': self.data}


class FakeBitunix:
    """Full allowlisted HTTP surface, position/order changes and lost-response simulation."""
    def __init__(self):
        self.positions = [position()]
        self.orders = []
        self.mark = 10000
        self.calls = []
        self.fail = False
        self.ambiguous = False
        self.apply_close = True
        self.before_position = None
        self.before_post = None

    def request(self, method, url, **kwargs):
        path = url.removeprefix('https://fapi.bitunix.com')
        self.calls.append((method, path, kwargs))
        if self.fail:
            raise requests.Timeout('fake-secret MUST NEVER ESCAPE')
        if method == 'GET':
            if path == POSITIONS:
                if self.before_position:
                    self.before_position(self)
                return Response(self.positions)
            if path == TPSL:
                return Response(self.orders)
            if path == TICKERS:
                return Response([dict(symbol='BTCUSDT', markPrice=str(self.mark), lastPrice=str(self.mark))])
            if path == PAIRS:
                return Response([dict(symbol='BTCUSDT', quotePrecision=1, symbolStatus='OPEN', isApiSupported=True)])
            if path == KLINES:
                return Response([])
        if method == 'POST':
            if self.before_post:
                self.before_post(self)
            body = json.loads(kwargs['data'])
            if path == FLASH_CLOSE:
                if self.apply_close:
                    self.positions = []
                if self.ambiguous:
                    raise requests.Timeout('fake-secret')
                return Response({'positionId': body['positionId']})
            if path == PLACE_SL:
                self.orders = [dict(body, id='777', slOrderType='MARKET')]
                if self.ambiguous:
                    raise requests.Timeout('fake-secret')
                return Response({'orderId': '777'})
        raise AssertionError('Unexpected route')

    @property
    def posts(self):
        return [call for call in self.calls if call[0] == 'POST']


class FakeMarket:
    def __init__(self, atr=100, bias='LONG_ALLOWED'):
        self.atr, self.value = atr, bias
    def venue_atr(self):
        return self.atr
    def bias(self):
        return {'bias': self.value, 'why': 'offline evidence'}


class FakeTelegram:
    def __init__(self):
        self.messages = []
        self.fail = False
    def send(self, text):
        self.messages.append(text)
        if self.fail:
            raise RuntimeError('telegram unavailable')
        return True


class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.fake = FakeBitunix()
        self.client = Bitunix(ARMED, 'fake-key', 'fake-secret', self.fake)
        self.market = FakeMarket()
        self.telegram = FakeTelegram()
        self.guardian = Guardian(self.client, self.store, self.market, self.telegram)
        self.guardian.bias = {'bias': 'LONG_ALLOWED', 'why': 'offline'}
        self._network = patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('LIVE HTTP FORBIDDEN'))
        self._network.start()

    def tearDown(self):
        self._network.stop()
        self.store.close()
        self.tmp.cleanup()

    def p(self, **kwargs):
        return parse_positions([position(**kwargs)])

    def test_signed_get_canonical(self):
        self.client.position()
        _, _, options = self.fake.calls[-1]
        h = options['headers']
        text = h['nonce'] + h['timestamp'] + 'fake-key' + 'includeSubAccountsfalsesymbolBTCUSDT'
        digest = hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(h['sign'], hashlib.sha256((digest + 'fake-secret').encode()).hexdigest())
        self.assertFalse(options['allow_redirects'])

    def test_secret_never_logged(self):
        self.fake.fail = True
        with self.assertRaises(SafetyError) as caught:
            self.client.position()
        self.assertNotIn('fake-secret', str(caught.exception))
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertNotIn('fake-secret', ''.join(p.read_text() for p in Path(self.tmp.name).glob('*.json*')))

    def test_exact_allowlist(self):
        self.assertEqual(GET_ALLOWLIST, {POSITIONS, TPSL, TICKERS, PAIRS, KLINES})
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})

    def test_forbidden_posts(self):
        for name in ('place_order', 'batch_order', 'close_all_position', 'change_leverage', 'change_margin', 'transfer', 'withdraw'):
            with self.subTest(name=name), self.assertRaises(SafetyError):
                self.client._request('POST', '/api/v1/futures/trade/' + name, body={})
        self.assertEqual(self.fake.posts, [])

    def test_pending_position_parser(self):
        p = self.client.position()
        self.assertEqual((p.position_id, p.side, p.qty, p.margin_mode), ('123', 'LONG', .1, 'ISOLATION'))

    def test_long_liquidation_sanity(self):
        with self.assertRaises(SafetyError):
            risk(self.p(liqPrice=10100), 10000, 100, ARMED)

    def test_short_liquidation_sanity(self):
        with self.assertRaises(SafetyError):
            risk(self.p(side='SHORT', liqPrice=9900), 10000, 100, ARMED)

    def test_invalid_liquidation_no_emergency(self):
        for value in (0, -10, 'NaN'):
            with self.subTest(value=value), self.assertRaises(SafetyError):
                risk(self.p(liqPrice=value), 10000, 100, ARMED)

    def test_atr_risk_calculation(self):
        r = risk(self.p(liqPrice=9500), 10000, 100, ARMED)
        self.assertEqual((r['distance'], r['distance_pct'], r['distance_atr'], r['atr_pct']), (500, .05, 5, .01))

    def test_warning_threshold(self):
        self.assertEqual(risk(self.p(liqPrice=9700), 10000, 50, ARMED)['state'], 'WARNING')

    def test_danger_threshold(self):
        self.assertEqual(risk(self.p(liqPrice=9800), 10000, 50, ARMED)['state'], 'DANGER')

    def test_emergency_atr(self):
        self.assertEqual(risk(self.p(liqPrice=9600), 10000, 320, ARMED)['state'], 'EMERGENCY')

    def test_emergency_percentage_no_atr(self):
        self.assertEqual(risk(self.p(liqPrice=9875), 10000, None, ARMED)['state'], 'EMERGENCY')

    def test_edge_equality_deterministic(self):
        for distance, state in ((125, 'EMERGENCY'), (200, 'DANGER'), (300, 'WARNING'), (301, 'NORMAL')):
            self.assertEqual(risk(self.p(liqPrice=10000-distance), 10000, None, ARMED)['state'], state)

    def test_catastrophic_long(self):
        self.assertEqual(catastrophic_stop(self.p(liqPrice=9500), 10000, 100, 1, ARMED), '9575.0')

    def test_catastrophic_short(self):
        self.assertEqual(catastrophic_stop(self.p(side='SHORT', liqPrice=10500), 10000, 100, 1, ARMED), '10425.0')

    def test_stop_not_beyond_liquidation(self):
        for side, liq in (('LONG', 9000), ('SHORT', 11000)):
            stop = float(catastrophic_stop(self.p(side=side, liqPrice=liq), 10000, 100, 1, ARMED))
            self.assertTrue(min(liq, 10000) < stop < max(liq, 10000))

    def test_stop_not_behind_mark(self):
        with self.assertRaises(SafetyError):
            catastrophic_stop(self.p(liqPrice=9990), 10000, 100, 1, ARMED)

    def test_existing_safer_manual_sl_untouched(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9800', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertEqual(self.fake.orders[0]['slPrice'], '9800')

    def test_existing_weaker_manual_sl_warning(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9520', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('CLOSER TO LIQUIDATION' in x for x in self.telegram.messages))

    def test_missing_sl_shadow_dry_run(self):
        self.client.config = Config()
        self.guardian.config = self.client.config
        self.fake.positions = [position(liqPrice=9500)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('DRY-RUN INTENT SL' in x for x in self.telegram.messages))

    def test_protect_missing_phrase(self):
        self.client.config = replace(ARMED, arm_phrase='')
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_flag_false(self):
        self.client.config = replace(ARMED, allow_close=False)
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_shadow(self):
        self.client.config = replace(ARMED, mode='SHADOW')
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_flash_exactly_one_position_id(self):
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertEqual(len(self.fake.posts), 1)
        self.assertEqual(json.loads(self.fake.posts[0][2]['data']), {'positionId': '123'})
        self.assertEqual(self.fake.posts[0][1], FLASH_CLOSE)

    def test_no_global_close_operationally(self):
        for file in ('trade_guardian.py', 'guardian_bitunix.py', 'guardian_risk.py'):
            self.assertNotIn('close_all_position', Path(file).read_text(encoding='utf-8'))

    def test_preclose_revalidation(self):
        self.fake.positions = [position(positionId='456')]
        with self.assertRaises(SafetyError):
            self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.fake.posts)

    def test_risk_improves_cancel(self):
        self.fake.mark = 10100
        with self.assertRaises(SafetyError):
            self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.store.actions)
        self.assertFalse(self.fake.posts)

    def test_ambiguous_response_reconciles_closed(self):
        self.fake.ambiguous = True
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.store.pending())
        self.assertTrue(self.store.state['lockout_until'] > time.time())
        self.assertEqual(len(self.fake.posts), 1)

    def test_restart_intent_reconciles_first(self):
        row = dict(key='CLOSE:123:1', action='CLOSE', positionId='123', risk_epoch=1, status='INTENT', timestamp=time.time())
        self.store.append('actions', row)
        self.store.close()
        self.store = Store(self.tmp.name)
        self.guardian.store = self.store
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.fake.posts)
        self.assertFalse(self.guardian.reconcile())

    def test_duplicate_emergency_no_duplicate_post(self):
        self.fake.apply_close = False
        self.fake.ambiguous = True
        self.guardian._act('CLOSE', self.p(), 100)
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertEqual(len(self.fake.posts), 1)
        self.assertTrue(self.store.pending())

    def test_api_timeout_fail_closed(self):
        self.fake.fail = True
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_telegram_failure_nonfatal(self):
        self.telegram.fail = True
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertEqual(len(self.fake.posts), 1)

    def test_no_chat_polling(self):
        self.assertNotIn('getUpdates', Path('guardian_telegram.py').read_text(encoding='utf-8'))

    def test_manual_close_no_action(self):
        self.store.state['position_id'] = '123'
        self.fake.positions = []
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertEqual(self.store.read('positions')[0]['event'], 'MANUAL_CLOSE_DETECTED')

    def test_no_opening_function(self):
        public = [name for name, _ in inspect.getmembers(Bitunix, inspect.isfunction) if not name.startswith('_')]
        self.assertEqual(set(public), {'position', 'mark', 'orders', 'precision', 'klines', 'preflight', 'execute'})

    def test_no_leverage_mutation(self):
        self.assertFalse(any('leverage' in route for route in POST_ALLOWLIST))

    def test_no_margin_mutation(self):
        self.assertFalse(any('margin' in route for route in POST_ALLOWLIST))

    def test_multiple_hedge_ambiguous(self):
        self.fake.positions = [position(), position(side='SHORT', positionId='456', liqPrice=10100)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_one_x_advisory_only(self):
        self.fake.positions = [position(leverage=1)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_closed_candles_only(self):
        a = [[0, 100, 101, 99, 100, 10, 6], [3600000, 100, 101, 99, 100, 10, 6]]
        self.assertEqual(len(closed_bars(a, 3600000, 3600000)), 1)

    def test_mlrsi_prefix_invariant(self):
        c = 100 + np.cumsum(np.random.default_rng(10).normal(size=150))
        full, prefix = rolling_mlrsi(c, 27, 40), rolling_mlrsi(c[:100], 27, 40)
        for field in ('rsi', 'centroids', 'state', 'green_event', 'red_event'):
            np.testing.assert_equal(full[field][:100], prefix[field])

    def test_live_mlrsi_prefix_invariant(self):
        c = 100 + np.cumsum(np.random.default_rng(44).normal(size=600))
        current = latest_mlrsi(c, 27, 300)
        prior = latest_mlrsi(c[:-1], 27, 300)
        self.assertEqual(current['state'], prior['state'])
        self.assertEqual(current['green_event'], prior['green_event'])
        self.assertEqual(current, latest_mlrsi(np.r_[c, 100000][:-1], 27, 300))

    def test_volatility_bands(self):
        self.assertEqual(volatility_state(100, 10000), 'NORMAL')
        self.assertEqual(volatility_state(200, 10000), 'ELEVATED')
        self.assertEqual(volatility_state(400, 10000), 'HIGH')
        self.assertEqual(volatility_state(None, 10000), 'UNKNOWN')

    def test_public_get_scope_is_btc_only(self):
        with self.assertRaises(SafetyError):
            self.client._request('GET', TICKERS, {'symbols': 'BTCUSDT,ETHUSDT'})
        with self.assertRaises(SafetyError):
            self.client._request('GET', POSITIONS, {'symbol': 'ETHUSDT', 'includeSubAccounts': 'false'})
        self.assertEqual(self.fake.calls, [])

    def test_wrong_symbol_and_duplicate_positions_blocked(self):
        for rows in ([position(symbol='ETHUSDT')], [position(), position(positionId='456')]):
            with self.subTest(rows=rows), self.assertRaises(SafetyError):
                parse_positions(rows)

    def test_regime_correct(self):
        self.assertEqual(direction('BULL', 'BULL', 'GREEN', .60, 'MIXED')[0], 'LONG_ALLOWED')
        self.assertEqual(direction('BEAR', 'BEAR', 'RED', .40, 'MIXED')[0], 'SHORT_ALLOWED')

    def test_taker_flow_edges(self):
        for ratio, expected in ((.60, 'STRONG BUY'), (.55, 'BUY'), (.50, 'NEUTRAL'), (.45, 'SELL'), (.40, 'STRONG SELL')):
            self.assertEqual(flow_state(ratio), expected)

    def test_long_allowed_logic(self):
        self.assertEqual(direction('BULL', 'BULL', 'GREEN', .50, 'BULLISH')[0], 'LONG_ALLOWED')

    def test_short_allowed_logic(self):
        self.assertEqual(direction('BEAR', 'BEAR', 'RED', .50, 'BEARISH')[0], 'SHORT_ALLOWED')

    def test_conflicting_regime_wait(self):
        self.assertEqual(direction('BULL', 'BEAR', 'GREEN', .70, 'BULLISH')[0], 'WAIT')

    def test_countertrend_warning_only(self):
        self.fake.positions = [position(side='SHORT', liqPrice=10500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice=10400, slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertTrue(any('TRADE AGAINST BIAS' in x for x in self.telegram.messages))
        self.assertFalse(self.fake.posts)

    def test_direction_conflict_never_flash_closes(self):
        self.test_countertrend_warning_only()

    def test_only_emergency_can_flash(self):
        for liq in (9500, 9700, 9800):
            self.fake.positions = [position(liqPrice=liq)]
            with self.subTest(liq=liq), self.assertRaises(SafetyError):
                self.client.preflight('CLOSE', self.p(liqPrice=liq), 50)
        self.assertFalse(self.fake.posts)

    def test_property_all_public_routes_triple_arm(self):
        for mode in ('SHADOW', 'PROTECT'):
            for sl in (False, True):
                for close in (False, True):
                    for phrase in ('', 'PROTECT_CAPITAL_ONLY', ' protect_capital_only '):
                        self.client.config = Config(mode=mode, allow_sl=sl, allow_close=close, arm_phrase=phrase)
                        for action in ('SL', 'CLOSE'):
                            self.fake.positions = [position(liqPrice=9500 if action == 'SL' else 9900)]
                            self.fake.orders = []
                            before = len(self.fake.posts)
                            try:
                                permit = self.client.preflight(action, self.client.position(), 100)
                                self.client.execute(permit)
                            except SafetyError:
                                pass
                            expected = mode == 'PROTECT' and phrase == 'PROTECT_CAPITAL_ONLY' and (sl if action == 'SL' else close)
                            self.assertEqual(len(self.fake.posts) - before, int(expected))
        self.assertTrue(all(call[1] in POST_ALLOWLIST for call in self.fake.posts))

    def test_permit_tampering_blocked(self):
        permit = self.client.preflight('CLOSE', self.p(), 100)
        permit['body']['positionId'] = '456'
        with self.assertRaises(SafetyError):
            self.client.execute(permit)
        self.assertFalse(self.fake.posts)

    def test_journal_fsync_before_post(self):
        def check(fake):
            on_disk = self.store.read('actions')
            self.assertEqual(on_disk[-1]['status'], 'INTENT')
        self.fake.before_post = check
        self.guardian._act('CLOSE', self.p(), 100)

    def test_subaccount_blocked(self):
        with self.assertRaises(SafetyError):
            self.p(subAccountId=12345)

    def test_missing_fields_blocked(self):
        row = position()
        del row['qty']
        with self.assertRaises(SafetyError):
            parse_positions([row])

    def test_clock_unverified_blocks(self):
        response = Response([position()])
        response.headers = {}
        self.fake.request = lambda *a, **kw: response
        with self.assertRaises(SafetyError):
            self.client.position()

    def test_rolling_maxdata(self):
        c = 100 + np.cumsum(np.random.default_rng(11).normal(size=100))
        ml = rolling_mlrsi(c, 27, 20)
        self.assertEqual(ml['window_count'][-1], 20)
        expected = cluster_three(ml['rsi'][-20:])[0]
        np.testing.assert_allclose(ml['centroids'][-1], expected)

    def test_state_event_neutral_transition(self):
        state, green, red, valid = states_and_events(np.array([50, 70, 20, 50, 20]), np.full(5, 40), np.full(5, 60))
        np.testing.assert_equal(green, [False, True, False, False, False])
        np.testing.assert_equal(red, [False, False, False, False, True])

    def test_pivot_confirmation_delay(self):
        a = np.array([[i, 100, h, 90, 100, 1, .5] for i, h in enumerate([101, 102, 110, 103, 102, 101])], float)
        self.assertEqual(confirmed_structure(a[:4])[1], [])
        self.assertEqual(confirmed_structure(a[:5])[1], [(4, 110)])

    def test_atr_reference(self):
        a = np.array([[i, 100, 102, 98, 100, 1, .5] for i in range(20)], float)
        self.assertEqual(atr14(a), 4)

    def test_binance_failure_risk_survives(self):
        self.market.value = 'UNKNOWN'
        self.market.atr = None
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertEqual(self.fake.posts[0][1], FLASH_CLOSE)

    def test_torn_journal_fail_closed(self):
        self.store.close()
        Path(self.tmp.name, 'actions.jsonl').write_text('{"status":"INTENT"')
        with self.assertRaises(SafetyError):
            Store(self.tmp.name)

    def test_tp_only_untouched(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', tpPrice='11000')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_owned_sl_no_modify(self):
        self.fake.positions = [position(liqPrice=9500)]
        with patch('builtins.print'):
            self.guardian.cycle()
            self.guardian.cycle()
        self.assertEqual(len(self.fake.posts), 1)
        self.assertEqual(self.store.state['owned_sl']['123'], '777')

    def test_lockout_does_not_close_safe_new_position(self):
        self.store.state['lockout_until'] = time.time() + 7200
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9800', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('LOCKOUT VIOLATION' in x for x in self.telegram.messages))

    def test_emergency_closed_not_manual_close(self):
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(any('MANUAL_CLOSE' in x for x in self.telegram.messages))


if __name__ == '__main__':
    unittest.main()
