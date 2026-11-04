"""Mechanics and isolation tests, never independent TradingView or profit evidence."""
import ast
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import csv
import gzip
import json
from pathlib import Path
import unittest
try:
    import numpy as np
except ModuleNotFoundError as exc:
    if exc.name != 'numpy':
        raise
    raise unittest.SkipTest('Research NumPy dependencies are installed and required by the dedicated offline workflow') from None

from .data import HERE, ROOT, HOUR, MINUTE, NY, read_json, schedule, validate_rows, verify_hourly_aggregation, freeze_cycle, wall
from .evaluate import block_indices, verify_freeze
from .reference_geometry import ATR14, Candle, project
from .signals import METHODS, net_terms, signal_for, stop_target
from .simulate import execute


def cycle():
    return dict(cycle='2026-01-01', freeze=0, expiry=6*MINUTE, l_open=99., l_close=108.,
                aHigh=105., aLow=85., lHigh=110., lLow=90., atr14=10.,
                highGuideValue=110., lowGuideValue=85., newTopTarget=160., newBottomTarget=50.)


def signal(side=1, limit=None):
    return dict(method='LIMIT_ZONE' if limit is not None else 'BASELINE', cycle='2026-01-01',
                status='SIGNAL', side=side, signal_at=0,
                theoretical_entry=108. if side == 1 else 92., limit_price=limit)


def minutes():
    return np.array([[i*MINUTE, 108., 109., 107., 108.] for i in range(7)], float)


class GeometryAndTiming(unittest.TestCase):
    def test_frozen_spec_and_verbatim_core(self):
        self.assertEqual(verify_freeze()['spec_sha256'], '525d73e8f3982430c9d0c1cc199693a21504eaf93a5c074c7a89fd13e4b88237')

    def test_reused_real_pine_geometry_no_new_parity_claim(self):
        gold = read_json('golden_prior_pine_records.json')
        self.assertIn('NOT_NEW_INDEPENDENT_EVIDENCE', gold['source'])
        self.assertEqual(len(gold['records']), 3)
        for record in gold['records']:
            got = project(*(record[k] for k in ('aHigh', 'aLow', 'lHigh', 'lLow')))
            for k in ('amplitude', 'topInAsia', 'bottomInAsia', 'topBoxHeight', 'bottomBoxHeight',
                      'topAnchor', 'bottomAnchor', 'newTopTarget', 'newBottomTarget', 'highGuideValue', 'lowGuideValue'):
                self.assertAlmostEqual(got[k], record[k], delta=1e-7)

    def test_original_visible_levels(self):
        p = project(77897.03, 77517.2, 78285., 77850.)
        self.assertEqual(p['highGuideValue'], 78285.)
        self.assertEqual(p['lowGuideValue'], 77517.2)
        self.assertAlmostEqual(p['newTopTarget'], 78653.4351)
        self.assertAlmostEqual(p['newBottomTarget'], 77095.25)

    def test_nested_and_overlapping_boxes_are_not_rejected(self):
        for values in ((110, 90, 105, 95), (105, 95, 110, 90), (110, 95, 115, 100), (100, 100, 100, 100)):
            self.assertGreaterEqual(project(*values)['amplitude'], 0)

    def test_summer_vs_winter_freeze(self):
        for day, hour in ((date(2026, 7, 1), 10), (date(2026, 1, 1), 11)):
            s = schedule(day)
            self.assertEqual(datetime.fromtimestamp(s['freeze']/1000, timezone.utc).hour, hour)
            self.assertEqual(s['freeze'] - s['london'], 4*HOUR)

    def test_fall_dst_not_owner_fixed_utc4(self):
        self.assertEqual(schedule(date(2025, 11, 2))['freeze'] - schedule(date(2025, 11, 1))['freeze'], 25*HOUR)

    def test_spring_dst_cycle_remains_incomplete(self):
        with self.assertRaisesRegex(ValueError, 'DST_MISSING'):
            schedule(date(2026, 3, 8))

    def test_atr_seed_and_causality(self):
        a = ATR14()
        for i in range(13):
            self.assertIsNone(a.append(Candle(i*HOUR, 100, 102, 98, 100)))
        self.assertEqual(a.append(Candle(13*HOUR, 100, 102, 98, 100)), 4)
        first = a.value
        a.append(Candle(14*HOUR, 100, 110, 90, 100))
        self.assertEqual(first, 4)

    def test_freeze_ignores_future_london_targets_and_prices(self):
        d = date(2026, 1, 1)
        s = schedule(d)
        h = np.array([[t, 100., 102., 98., 101.] for t in range(s['asia'], s['freeze']+3*HOUR, HOUR)])
        av = np.full(len(h), 4.)
        first = freeze_cycle(d, h, av)
        h[h[:, 0] >= s['freeze'], 1:] = [1000., 1100., 900., 1050.]
        av[h[:, 0] >= s['freeze']] = 200.
        self.assertEqual(first, freeze_cycle(d, h, av))
        self.assertEqual(first['levels_available_at'], s['freeze'])

    def test_hour_aggregation_exact(self):
        mm = np.array([[i*MINUTE, 100., 102., 98., 101.] for i in range(60)])
        hh = np.array([[0, 100., 102., 98., 101.]])
        self.assertEqual(verify_hourly_aggregation(hh, mm), 1)
        hh[0, 4] += .01
        with self.assertRaisesRegex(ValueError, 'MISMATCH'):
            verify_hourly_aggregation(hh, mm)

    def test_gaps_duplicates_nan_and_partial_fail_closed(self):
        base = np.array([[i*MINUTE, 100., 102., 98., 101.] for i in range(3)])
        for bad in (base[:2], np.vstack([base[:2], base[1]]), base[[0, 2]]):
            with self.assertRaises(ValueError):
                validate_rows(bad, 0, 3*MINUTE, MINUTE)
        base[0, 4] = np.nan
        with self.assertRaises(ValueError):
            validate_rows(base, 0, 3*MINUTE, MINUTE)


class Signals(unittest.TestCase):
    def test_baseline_direction_frozen_at_london(self):
        c = cycle()
        self.assertEqual(signal_for('BASELINE', c, np.empty((0, 5)))['side'], 1)
        c['l_close'] = 98.
        self.assertEqual(signal_for('BASELINE', c, np.empty((0, 5)))['side'], -1)
        c['l_close'] = c['l_open']
        self.assertEqual(signal_for('BASELINE', c, np.empty((0, 5)))['status'], 'NO_SIGNAL')

    def test_after_london_requires_asia_structure(self):
        c = cycle()
        self.assertEqual(signal_for('AFTER_LONDON', c, np.empty((0, 5)))['status'], 'SIGNAL')
        c['aHigh'] = 109.
        self.assertEqual(signal_for('AFTER_LONDON', c, np.empty((0, 5)))['status'], 'NO_SIGNAL')

    def test_breakout_full_body_not_wick_or_equality(self):
        c = dict(cycle(), freeze=HOUR, expiry=10*HOUR)
        for o, high, low, close in ((109, 115, 108, 111), (110, 115, 109, 112)):
            h = np.array([[HOUR, o, high, low, close]])
            self.assertEqual(signal_for('BREAKOUT', c, h)['status'], 'NO_SIGNAL')
        h = np.array([[HOUR, 111, 115, 110, 112]])
        self.assertEqual(signal_for('BREAKOUT', c, h)['signal_at'], 2*HOUR)

    def test_breakout_short_symmetric(self):
        c = dict(cycle(), freeze=HOUR, expiry=10*HOUR)
        h = np.array([[HOUR, 84, 86, 80, 82]])
        self.assertEqual(signal_for('BREAKOUT', c, h)['side'], -1)

    def test_first_confirmation_no_retrospective_side_switch(self):
        c = dict(cycle(), freeze=HOUR, expiry=10*HOUR)
        h = np.array([[HOUR, 111, 115, 110, 112], [2*HOUR, 84, 86, 80, 82]])
        self.assertEqual(signal_for('BREAKOUT', c, h)['side'], 1)

    def test_retest_requires_later_bar(self):
        c = dict(cycle(), freeze=HOUR, expiry=10*HOUR)
        h = np.array([[HOUR, 111, 115, 109, 112], [2*HOUR, 112, 114, 109, 111]])
        self.assertEqual(signal_for('RETEST', c, h[:1])['status'], 'RETEST_NOT_CONFIRMED')
        self.assertEqual(signal_for('RETEST', c, h)['signal_at'], 3*HOUR)

    def test_prefix_invariance_once_confirmed(self):
        c = dict(cycle(), freeze=HOUR, expiry=10*HOUR)
        h = np.array([[HOUR, 111, 115, 109, 112], [2*HOUR, 112, 114, 109, 111], [3*HOUR, 10, 20, 5, 8]])
        for method in ('BREAKOUT', 'RETEST'):
            self.assertEqual(signal_for(method, c, h[:2]), signal_for(method, c, h))

    def test_limit_zone_known_before_any_price_arrives(self):
        c = cycle()
        s = signal_for('LIMIT_ZONE', c, np.empty((0, 5)))
        self.assertEqual(s['limit_price'], 100.)
        self.assertEqual((s['zone_low'], s['zone_high']), (100., 108.))
        self.assertEqual(s['signal_at'], 0)

    def test_unknown_model_no_radar_model_or_tolerance(self):
        with self.assertRaises(ValueError):
            signal_for('PRICE_PROBABILITY', cycle(), np.empty((0, 5)))
        self.assertEqual(set(METHODS), {'BASELINE', 'AFTER_LONDON', 'BREAKOUT', 'RETEST', 'LIMIT_ZONE'})


class Execution(unittest.TestCase):
    def test_market_never_fills_on_confirmation_bar(self):
        m = minutes()
        m[0] = [0, 108, 200, 10, 108]
        r, t = execute(cycle(), signal(), m, 10000., .001, .0002)
        self.assertEqual(t['entry_at'], MINUTE)
        self.assertEqual(t['exit_reason'], 'TIME')
        self.assertGreater(t['entry'], m[1, 1])

    def test_stop_first_on_intraminute_ambiguity(self):
        m = minutes()
        m[2] = [2*MINUTE, 108, 170, 80, 108]
        _, t = execute(cycle(), signal(), m, 10000., .001, .0002)
        self.assertEqual(t['exit_reason'], 'SL')
        self.assertLess(t['net_pnl'], 0)
        self.assertIn('STOP_AND_TP', t['ambiguity'])

    def test_tp_later_than_entry_is_distinct_from_win_rate(self):
        m = minutes()
        m[2] = [2*MINUTE, 108, 161, 107, 150]
        _, t = execute(cycle(), signal(), m, 10000., .001, .0002)
        self.assertEqual(t['exit_reason'], 'TP')
        self.assertGreater(t['net_pnl'], 0)
        self.assertAlmostEqual(t['gross_pnl'] - t['fees'] - t['slippage_pnl_cost'], t['net_pnl'])

    def test_limit_touch_is_not_fill(self):
        m = minutes()
        m[1, 3] = 100.
        s = dict(signal(limit=100.), theoretical_entry=100.)
        r, t = execute(cycle(), s, m, 10000., .001, .0002)
        self.assertEqual(r['status'], 'UNFILLED')
        self.assertIsNone(t)

    def test_limit_strict_penetration_fills_without_adverse_limit_violation(self):
        m = minutes()
        m[1, 3] = 99.98
        s = dict(signal(limit=100.), theoretical_entry=100.)
        _, t = execute(cycle(), s, m, 10000., .001, .0002)
        self.assertEqual(t['entry'], 100.)

    def test_limit_tp_entry_minute_not_credited(self):
        m = minutes()
        m[1] = [MINUTE, 108., 170., 99.98, 108.]
        s = dict(signal(limit=100.), theoretical_entry=100.)
        _, t = execute(cycle(), s, m, 10000., .001, .0002)
        self.assertEqual(t['exit_reason'], 'TIME')
        self.assertIn('NO_TP_CREDIT', t['ambiguity'])

    def test_gap_through_limit_and_stop_does_not_escape_loss(self):
        m = minutes()
        m[1] = [MINUTE, 80., 85., 70., 78.]
        s = dict(signal(limit=100.), theoretical_entry=100.)
        _, t = execute(cycle(), s, m, 10000., .001, .0002)
        self.assertEqual(t['exit_reason'], 'SL')
        self.assertLess(t['exit_price'], 80.)
        self.assertLess(t['net_r'], -1.)

    def test_net_rr_filters_with_costs(self):
        self.assertTrue(net_terms(100., 90., 115.1, 1, 0., 0.)['valid'])
        self.assertFalse(net_terms(100., 90., 115.1, 1, .001, .0002)['valid'])

    def test_target_behind_and_invalid_stop_reject(self):
        self.assertEqual(net_terms(108, 88, 107, 1, .001, .0002)['reason'], 'TARGET_BEHIND_ENTRY')
        self.assertEqual(net_terms(108, 109, 160, 1, .001, .0002)['reason'], 'STOP_NOT_PROTECTIVE')
        self.assertFalse(net_terms(108, -1, 160, 1, .001, .0002)['valid'])

    def test_execution_gap_rechecks_rr_without_repositioning_stop(self):
        m = minutes()
        m[1] = [MINUTE, 155., 156., 154., 155.]
        r, t = execute(cycle(), signal(), m, 10000., .001, .0002)
        self.assertEqual(r['reason'], 'EXECUTION_NET_RR_BELOW_1_5')
        self.assertIsNone(t)
        self.assertEqual(r['stop'], 88.)

    def test_quantity_risk_and_notional_caps(self):
        _, t = execute(cycle(), signal(), minutes(), 10000., .001, .0002)
        self.assertLessEqual(t['planned_risk'], 25. + 1e-9)
        self.assertLessEqual(t['quantity_btc'] * t['entry'] * 1.001, 10000. + 1e-9)

    def test_no_capital_reset(self):
        m = minutes()
        m[1] = [MINUTE, 108., 109., 80., 90.]
        _, first = execute(cycle(), signal(), m, 10000., .001, .0002)
        _, second = execute(cycle(), signal(), m, first['equity_after'], .001, .0002)
        self.assertLess(second['quantity_btc'], first['quantity_btc'])
        self.assertEqual(second['equity_before'], first['equity_after'])

    def test_deadline_and_data_gaps_fail_closed(self):
        r, t = execute(dict(cycle(), expiry=MINUTE), signal(), minutes(), 10000., .001, .0002)
        self.assertEqual(r['reason'], 'NO_EXECUTION_WINDOW')
        r, t = execute(cycle(), signal(), np.delete(minutes(), 3, axis=0), 10000., .001, .0002)
        self.assertEqual(r['reason'], 'EXECUTION_DATA_UNAVAILABLE')

    def test_time_exit_does_not_use_last_minute_high_low_or_close(self):
        m = minutes()
        _, t = execute(cycle(), signal(), m, 10000., .001, .0002)
        m[-1] = [6*MINUTE, 108., 1000., 1., 900.]
        _, changed = execute(cycle(), signal(), m, 10000., .001, .0002)
        self.assertEqual(t, changed)

    def test_deterministic_and_inputs_immutable(self):
        c, s, m = cycle(), signal(), minutes()
        before = deepcopy((c, s, m))
        a = execute(c, s, m, 10000., .001, .0002)
        self.assertEqual(a, execute(c, s, m, 10000., .001, .0002))
        self.assertEqual(c, before[0]); self.assertEqual(s, before[1])
        self.assertTrue(np.array_equal(m, before[2]))

    def test_short_explicitly_hypothetical(self):
        c = dict(cycle(), l_open=110., l_close=92.)
        m = minutes(); m[:, 1:] = [92., 93., 91., 92.]
        _, t = execute(c, signal(-1), m, 10000., .001, .0002)
        self.assertEqual(t['position_exposure'], 'SHORT_PRICE_ONLY_NOT_EXECUTABLE')


class Isolation(unittest.TestCase):
    def test_all_162_protected_base_files_unchanged(self):
        f, canonical = read_json('freeze_manifest.json'), read_json('protected_git_blob_hashes.json')
        self.assertEqual(len(f['protected_base_files']), 162)
        for name, expected in f['protected_base_files'].items():
            actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            self.assertIn(actual, (expected, canonical['files'][name]), name)

    def test_production_cannot_import_entry_research_directly_or_by_string(self):
        files = read_json('freeze_manifest.json')['protected_base_files']
        for name in files:
            if not name.endswith('.py') or Path(name).name.startswith('test_'):
                continue
            text = (ROOT / name).read_text(encoding='utf-8-sig')
            self.assertNotIn('killzone_optimal_entry', text, name)

    def test_no_network_exchange_telegram_or_live_clients_in_new_modules(self):
        forbidden = {'requests', 'httpx', 'socket', 'urllib', 'ccxt', 'telegram', 'guardian_bitunix',
                     'trade_guardian', 'guardian_risk', 'v8_executor', 'subprocess'}
        for p in HERE.glob('*.py'):
            tree = ast.parse(p.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split('.')[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or '').split('.')[0]]
                else:
                    continue
                self.assertFalse(set(names) & forbidden, (p.name, names))

    def test_independent_of_radar_and_owner_b_rules(self):
        text = '\n'.join((HERE / n).read_text() for n in ('signals.py', 'simulate.py', 'data.py'))
        for forbidden in ('killzone_price_radar', 'killzone_probability_radar', 'OWNER_B', 'OWNER_C'):
            self.assertNotIn(forbidden, text)
        s = read_json('specification.json')
        self.assertEqual(s['geometry']['asia_hours'], [20, 21, 22, 23])
        self.assertEqual(s['geometry']['london_hours'], [2, 3, 4, 5])

    def test_bootstrap_groups_calendar_cycles_not_minutes(self):
        x = block_indices(365)
        self.assertEqual(x.shape, (2000, 365))
        self.assertTrue(np.array_equal(x, block_indices(365)))
        self.assertTrue((np.diff(x[:, :7], axis=1) % 365 == 1).all())


class ActualArtifactIntegrity(unittest.TestCase):
    """Checks of published historical artifacts, not independent market validation."""

    @classmethod
    def setUpClass(cls):
        cls.out = HERE / 'artifacts'
        cls.actual = json.loads(gzip.decompress((cls.out / 'results.json.gz').read_bytes()))

    def test_all_files_match_artifact_hashes(self):
        manifest = json.loads((self.out / 'artifact_manifest.json').read_text())
        for name, record in manifest.items():
            raw = (self.out / name).read_bytes()
            self.assertEqual(len(raw), record['bytes'], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['sha256'], name)

    def test_all_calendar_method_side_cost_rows_retained(self):
        rows = self.actual['cycles']
        self.assertEqual(len(rows), 365*5*2*2)
        identities = {(r['cycle'], r['method'], r['cost'], r['account_side']) for r in rows}
        self.assertEqual(len(identities), len(rows))
        self.assertEqual(self.actual['quality']['complete_cycles'], 364)
        self.assertEqual(self.actual['quality']['incomplete'], [{'cycle': '2026-03-08', 'reason': 'DST_MISSING_LOCAL_HOUR'}])
        self.assertEqual(self.actual['quality']['forward_observations'], 0)

    def test_each_real_simulated_trade_has_delayed_entry_fixed_stop_and_cash_cap(self):
        for t in self.actual['trades']:
            self.assertGreaterEqual(t['entry_at'], t['signal_at']+MINUTE)
            self.assertGreaterEqual(t['exit_at'], t['entry_at'])
            self.assertGreaterEqual(t['net_rr'], 1.5)
            self.assertLessEqual(t['planned_risk'], t['equity_before']*.0025+1e-8)
            fee = .001 if t['cost']=='PRIMARY' else .0015
            self.assertLessEqual(t['quantity_btc']*t['entry']*(1+fee), t['equity_before']+1e-8)
            self.assertAlmostEqual(t['equity_before']+t['net_pnl'], t['equity_after'])
            self.assertGreater(t['side']*(t['entry']-t['stop']), 0)
            self.assertGreater(t['side']*(t['target']-t['entry']), 0)

    def test_each_account_never_resets_or_uses_other_side_capital(self):
        for cost in ('PRIMARY', 'STRESS'):
            for method in METHODS:
                for side in (1, -1):
                    rows = [r for r in self.actual['cycles'] if r['cost']==cost and r['method']==method and r['account_side']==side]
                    equity = 10000.
                    for r in rows:
                        self.assertEqual(r['equity_before'], equity)
                        equity = r['equity_after']

    def test_real_limit_prices_are_frozen_not_selected_from_future_extremes(self):
        for r in self.actual['cycles']:
            if r['method']=='LIMIT_ZONE' and r.get('signal_at') is not None:
                self.assertEqual(r['signal_at'], r['levels_available_at'])
                # Exact predeclared midpoint is reported for all signals, including rejected/unfilled.
                self.assertEqual(r['limit_price'], r['theoretical_entry'])
        with (self.out / 'frozen_levels.csv').open(encoding='utf-8') as stream:
            levels = list(csv.DictReader(stream))
        lookup = {r['cycle']: r for r in levels}
        for t in self.actual['trades']:
            if t['is_limit']:
                c = lookup[t['cycle']]
                self.assertEqual(t['entry'], (float(c['lHigh'])+float(c['lLow']))/2)

    def test_short_is_not_certified_and_n_zero_does_not_imply_success(self):
        for s in self.actual['summaries']:
            if s['side']==-1:
                self.assertNotEqual(s['classification'], 'PROMISING FOR FORWARD VALIDATION')
            if s['n']==0:
                self.assertEqual(s['classification'], 'INCONCLUSIVE')
                self.assertIsNone(s['mean_net_r'])
                self.assertIsNone(s['net_win_rate'])

    def test_partition_and_month_sums_preserve_losses(self):
        for s in self.actual['summaries']:
            self.assertEqual(sum(m['n'] for m in s['months']), s['n'])
            self.assertEqual(sum(m['n'] for m in s['partitions'].values()), s['n'])
            self.assertAlmostEqual(sum(m['net_pnl'] for m in s['months']), s['net_pnl'])

    def test_same_frozen_levels_across_all_methods_costs_and_side_accounts(self):
        seen = {}
        for r in self.actual['cycles']:
            if r['status']=='INCOMPLETE':
                continue
            values = tuple(r[k] for k in ('HIGH','LOW','SUPERIOR','INFERIOR','levels_available_at','ATR14'))
            if r['cycle'] in seen:
                self.assertEqual(values, seen[r['cycle']])
            seen[r['cycle']] = values


if __name__ == '__main__':
    unittest.main()
