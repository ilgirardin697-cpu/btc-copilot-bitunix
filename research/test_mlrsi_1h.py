"""Offline fixtures for a causal port, NOT TradingView parity exports."""
import ast
from dataclasses import asdict
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
try:
    import numpy as np
except ImportError:
    raise unittest.SkipTest('Research CI explicitly installs numpy/requests') from None
from guardian_signals import rolling_mlrsi
from research import mlrsi_1h_core as s
from research import mlrsi_1h_run as runner


ZERO = s.Costs(0, 0, 0)


def bars(prices, start=0):
    return np.asarray([[start + i * s.STEP, *p, 10, 5] for i, p in enumerate(prices)], float)


def event(stamp=0, side=1):
    return dict(timestamp=stamp, side=side, period='TEST', reference=100., event='GREEN_CROSS')


class CausalityTests(unittest.TestCase):
    def test_hour_exact_twelve_closed_bars(self):
        a = bars([[100, 102, 98, 101]] * 13)
        h = s.aggregate(a)
        self.assertEqual(len(h), 1)
        np.testing.assert_array_equal(h[0], [0, 100, 102, 98, 101, 120, 60])

    def test_cutoff_excludes_open_last_bar(self):
        a = s.validate(bars([[100, 102, 98, 101]] * 12), cutoff=12 * s.STEP - 1)
        self.assertEqual(len(s.aggregate(a)), 0)

    def test_no_interpolation_over_gap(self):
        a = bars([[100, 102, 98, 101]] * 24)
        h = s.aggregate(np.delete(a, 4, axis=0))
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0, 0], s.HOUR)

    def test_partial_start_hour_dropped(self):
        a = bars([[100, 102, 98, 101]] * 24)[1:]
        self.assertEqual(s.aggregate(a)[0, 0], s.HOUR)

    def test_aggregation_prefix_invariant(self):
        a = bars([[100, 102, 98, 101]] * 48)
        np.testing.assert_array_equal(s.aggregate(a[:25]), s.aggregate(a)[:2])

    def test_invalid_ohlc_and_nonfinite_blocked(self):
        for a in (bars([[100, 99, 98, 101]]), bars([[100, 102, 98, np.nan]])):
            with self.assertRaises(ValueError):
                s.validate(a)

    def test_unsorted_and_duplicate_timestamps_blocked(self):
        a = bars([[100, 102, 98, 101]] * 2)
        for stamps in ([0, 0], [s.STEP, 0]):
            a[:, 0] = stamps
            with self.assertRaises(ValueError):
                s.validate(a)

    def test_1h_uses_low_not_close_and_exact_existing_port(self):
        a = bars([[100, 104, 97, 103]] * 24)
        ml = dict(rsi=np.ones(2), state=np.ones(2), valid=np.ones(2, bool), converged=np.ones(2, bool))
        with patch.object(s, 'rolling_mlrsi', return_value=ml) as f:
            s.features(a)
        np.testing.assert_array_equal(f.call_args.args[0], [97, 97])
        self.assertEqual(f.call_args.kwargs, dict(length=27, max_data=3000, max_iter=1000))
        self.assertIs(s.rolling_mlrsi, rolling_mlrsi)

    def test_indicator_prefix_invariance(self):
        prices = 100 + np.random.default_rng(31).normal(0, 2, 140)
        full = rolling_mlrsi(prices, 27, 64)
        for n in (40, 80, 110):
            prefix = rolling_mlrsi(prices[:n], 27, 64)
            for key in ('rsi', 'state', 'centroids', 'valid'):
                np.testing.assert_allclose(prefix[key], full[key][:n], equal_nan=True)

    def test_context_uses_closed_4h_only(self):
        c = bars([[100, 102, 98, 101]] * 202)
        c[:, 0] = np.arange(202) * 4 * s.HOUR
        h = c[200:201].copy()
        before = s.closed_trend(h, c, 4 * s.HOUR)
        self.assertTrue(before[1][0])
        c[200:, 4] = 10000
        after = s.closed_trend(h, c, 4 * s.HOUR)
        for x, y in zip(before, after):
            np.testing.assert_array_equal(x, y)

    def test_context_needs_200_closed_days(self):
        d = bars([[100, 102, 98, 101]] * 200)
        d[:, 0] = np.arange(200) * s.DAY
        h = d[-1:].copy()
        self.assertFalse(s.closed_trend(h, d, s.DAY)[1][0])

    def test_wilder_atr_seed(self):
        h = bars([[100, 102, 98, 101]] * 15)
        self.assertTrue(np.isnan(s.atr14(h)[:13]).all())
        self.assertEqual(s.atr14(h)[13], 4)

    def test_volatility_quartiles_train_only(self):
        f = dict(h=np.array([[s.START, 0], [s.TRAIN_END, 0]]), atr_pct=np.array([.01, 100.]))
        self.assertEqual(s.volatility_boundaries(f), [.01, .01, .01])

    def test_alignment_long_short_and_unknown(self):
        e = dict(side=1, trend4=1, trend_d=-1, known4=True, known_d=True)
        self.assertTrue(s.aligned(e, '4H'))
        self.assertFalse(s.aligned(e, 'BOTH'))
        self.assertTrue(s.aligned(dict(e, side=-1), '1D'))
        self.assertFalse(s.aligned(dict(e, known4=False), '4H'))


class EventTests(unittest.TestCase):
    def setUp(self):
        self.rsi = [40, 60, 62, 61, 61, 63, 64, 62, 65, 66]
        self.state = [0] + [1] * 9

    def test_green_cross_once(self):
        np.testing.assert_array_equal(s.detect_events(self.rsi, self.state)['GREEN_CROSS'], [1])

    def test_direct_red_cross(self):
        np.testing.assert_array_equal(s.detect_events([70, 30, 20], [1, -1, -1])['RED_CROSS'], [1])

    def test_green_resume_flat_down_rearm(self):
        np.testing.assert_array_equal(s.detect_events(self.rsi, self.state)['GREEN_RESUME'], [5, 8])

    def test_red_resume_mirror(self):
        np.testing.assert_array_equal(s.detect_events(100 - np.array(self.rsi), -np.array(self.state))['RED_RESUME'], [5, 8])

    def test_no_repeated_resume_without_reset(self):
        e = s.detect_events([40, 60, 59, 61, 62, 63, 64], [0, 1, 1, 1, 1, 1, 1])
        np.testing.assert_array_equal(e['GREEN_RESUME'], [3])

    def test_two_confirming_hours_later_timestamp(self):
        e = s.detect_events(self.rsi, self.state, confirmations=2)
        np.testing.assert_array_equal(e['GREEN_CROSS'], [2])
        np.testing.assert_array_equal(e['GREEN_RESUME'], [6, 9])

    def test_confirm_pending_cancelled_by_color(self):
        e = s.detect_events([40, 60, 59, 61, 62], [0, 1, 1, 1, 0], confirmations=2)
        self.assertEqual(len(e['GREEN_RESUME']), 0)

    def test_missing_hour_cancels_rearm(self):
        e = s.detect_events([60, 59, 61, 62], [1, 1, 1, 1], timestamps=[0, s.HOUR, 3 * s.HOUR, 4 * s.HOUR])
        self.assertEqual(len(e['GREEN_RESUME']), 0)

    def test_invalid_indicator_no_event(self):
        e = s.detect_events([40, 60, 62], [0, 1, 1], valid=[True, False, True])
        self.assertTrue(all(len(x) == 0 for x in e.values()))

    def test_signal_prefix_invariant(self):
        full = s.detect_events(self.rsi, self.state)
        prefix = s.detect_events(self.rsi[:7], self.state[:7])
        for name in s.EVENTS:
            np.testing.assert_array_equal(prefix[name], full[name][full[name] < 7])

    def test_event_timestamp_is_closed_hour_not_open(self):
        h = bars([[100, 102, 98, 101]] * 3)
        h[:, 0] = s.START + np.arange(3) * s.HOUR
        f = dict(h=h, rsi=np.array([40, 60, 62]), state=np.array([0, 1, 1]),
                 valid=np.ones(3, bool), converged=np.ones(3, bool), atr=np.ones(3),
                 atr_pct=np.ones(3), trend4=np.ones(3), known4=np.ones(3, bool),
                 trend_d=np.ones(3), known_d=np.ones(3, bool))
        e = s.event_rows(f, 1, [.005, .01, .02])[0]
        self.assertEqual(e['timestamp'], s.START + 2 * s.HOUR)


class ForwardTests(unittest.TestCase):
    def path(self):
        return bars([[100, 102, 99, 101]] * 24)

    def test_forward_long_return(self):
        r = s.forward(self.path(), event(), 1, ZERO)
        self.assertAlmostEqual(r['directional_return'], .01)

    def test_forward_short_return(self):
        r = s.forward(self.path(), event(side=-1), 1, ZERO)
        self.assertAlmostEqual(r['directional_return'], -.01)

    def test_mfe_mae_long(self):
        r = s.forward(self.path(), event(), 1, ZERO)
        self.assertAlmostEqual(r['mfe'], .02)
        self.assertAlmostEqual(r['mae'], -.01)

    def test_mfe_mae_short(self):
        r = s.forward(self.path(), event(side=-1), 1, ZERO)
        self.assertAlmostEqual(r['mfe'], .01)
        self.assertAlmostEqual(r['mae'], -.02)

    def test_all_first_passage_pairs(self):
        a = bars([[100, 106, 100, 105]] + [[105, 106, 104, 105]] * 11)
        r = s.forward(a, event(), 1, ZERO)
        self.assertEqual(len(r['passages']), 5)
        self.assertTrue(all(p['success'] for p in r['passages'].values()))

    def test_short_passage_mirror(self):
        a = bars([[100, 100, 94, 95]] + [[95, 96, 94, 95]] * 11)
        self.assertTrue(all(p['success'] for p in s.forward(a, event(side=-1), 1, ZERO)['passages'].values()))

    def test_same_candle_passage_is_ambiguous_failure(self):
        p = s.forward(self.path(), event(), 1, ZERO)['passages']['+0.5/-0.5']
        self.assertTrue(p['ambiguous'])
        self.assertFalse(p['success'])

    def test_neither_barrier_not_success(self):
        r = s.forward(bars([[100, 100, 100, 100]] * 12), event(), 1, ZERO)
        self.assertTrue(all(p['neither'] and not p['success'] for p in r['passages'].values()))

    def test_gap_horizon_censored(self):
        r = s.forward(np.delete(self.path(), 4, axis=0), event(), 1, ZERO)
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_horizon_requires_elapsed_and_closed_bars(self):
        r = s.forward(self.path(), event(), 2, ZERO, cutoff=2 * s.HOUR - 1)
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_no_signal_candle_retrospective_extreme(self):
        a = self.path()
        a[0, 1] = 101
        self.assertEqual(s.forward(a, event(), 1, ZERO)['entry'], 101)

    def test_primary_slippage_adverse_both_sides(self):
        self.assertGreater(s.forward(self.path(), event(), 1)['entry'], 100)
        self.assertLess(s.forward(self.path(), event(side=-1), 1)['entry'], 100)

    def test_close_fill_separate_sensitivity(self):
        r = s.forward(self.path(), dict(event(), reference=99), 1, ZERO, close_fill=True)
        self.assertEqual(r['entry'], 99)
        self.assertEqual(s.forward(self.path(), event(), 1, ZERO)['entry'], 100)

    def test_forward_net_has_full_entry_exit_fees(self):
        r = s.forward(bars([[100, 100, 100, 100]] * 12), event(), 1, s.Costs(5, 0, 0))
        self.assertAlmostEqual(r['net'], -.001)

    def test_forward_excludes_future_after_horizon(self):
        a = self.path()
        before = s.forward(a, event(), 1, ZERO)
        a[12:, 2] = 10000
        self.assertEqual(before, s.forward(a, event(), 1, ZERO))

    def test_split_boundary_no_test_into_validation(self):
        a = self.path()
        a[:, 0] += s.VALID_END - s.HOUR
        e = dict(event(s.VALID_END - s.HOUR), period='VALIDATION')
        self.assertEqual(s.forward(a, e, 2, ZERO)['status'], 'INCOMPLETE')

    def test_summary_pending_excluded(self):
        r = s.forward(self.path(), event(), 1, ZERO)
        summary = s.forward_summary([r, dict(status='INCOMPLETE')])
        self.assertEqual(summary['complete'], 1)
        self.assertEqual(summary['incomplete'], 1)
        self.assertEqual(summary['passages']['+1/-1']['n'], 1)


class ManagementTests(unittest.TestCase):
    def test_candidate_grid_small_one_factor(self):
        models = s.candidates()
        self.assertEqual(len(models), 16)
        self.assertEqual(len({m.key() for m in models}), 16)
        self.assertEqual(sum(m.exit == 'atr_runner' and m.economic_be for m in models), 6)

    def test_stop_precedence_before_target(self):
        r = s.simulate(bars([[100, 104, 96, 101]]), 0, 1, 2, s.Management('fixed2r'), ZERO)
        self.assertEqual(r['exit_reason'], 'INITIAL_STOP')
        self.assertTrue(r['ambiguity'])
        self.assertAlmostEqual(r['net'], -.02)

    def test_fixed1r_2r_3r(self):
        for multiple in (1, 2, 3):
            r = s.simulate(bars([[100, 107, 99, 105]]), 0, 1, 2, s.Management(f'fixed{multiple}r'), ZERO)
            self.assertAlmostEqual(r['net'], multiple * .02)

    def test_partial_tp1_has_thirty_percent(self):
        a = bars([[100, 102.5, 100, 102], [102, 102, 99, 100]])
        r = s.simulate(a, 0, 1, 2, s.Management(), ZERO)
        self.assertEqual(r['fills'][0]['qty'], .3)
        self.assertEqual(r['fills'][1]['qty'], .7)

    def test_economic_be_zero_whole_trade_long(self):
        c = s.Costs()
        e, tp = 100.02, 102 * (1 - .0002)
        trigger = s.economic_breakeven(e, tp, 1, c)
        last = trigger * (1 - .0005)
        net = (.3 * tp + .7 * last) / e - 1 - .0005 * (1 + (.3 * tp + .7 * last) / e)
        self.assertAlmostEqual(net, 0, places=12)
        self.assertNotEqual(trigger, e)

    def test_economic_be_zero_whole_trade_short(self):
        e, tp, c = 99.98, 98 * (1 + .0002), s.Costs()
        trigger = s.economic_breakeven(e, tp, -1, c)
        last = trigger * (1 + .0005)
        weighted = (.3 * tp + .7 * last) / e
        self.assertAlmostEqual(1 - weighted - .0005 * (1 + weighted), 0, places=12)

    def test_simulated_economic_be_costs_exact(self):
        a = bars([[100, 102.1, 100, 102], [102, 102, 99, 100]])
        r = s.simulate(a, 0, 1, 2, s.Management())
        self.assertEqual(r['exit_reason'], 'ECONOMIC_BE')
        self.assertAlmostEqual(r['net'], 0, places=12)

    def test_partial_exit_fee_not_full_size_twice(self):
        a = bars([[100, 102.5, 100, 102], [102, 102, 99, 100]])
        r = s.simulate(a, 0, 1, 2, s.Management())
        expected = .0005 * (1 + sum(f['qty'] * f['price'] / r['entry'] for f in r['fills']))
        self.assertAlmostEqual(r['fees'], expected)

    def test_naive_and_economic_be_different(self):
        a = bars([[100, 102.5, 100, 102], [102, 102, 99, 100]])
        naive = s.simulate(a, 0, 1, 2, s.Management(economic_be=False))
        economic = s.simulate(a, 0, 1, 2, s.Management())
        self.assertEqual(naive['be_trigger'], naive['entry'])
        self.assertNotEqual(economic['be_trigger'], economic['entry'])

    def test_unreachable_be_does_not_invent_profitable_fill(self):
        r = s.simulate(bars([[100, 100.2, 100, 100.1]]), 0, 1, .05, s.Management())
        self.assertEqual(r['exit_reason'], 'BE_UNREACHABLE')
        self.assertLess(r['net'], 0)

    def test_trail_update_not_same_bar_retrospective(self):
        a = bars([[100, 105, 100, 104], [104, 104, 102.5, 103]])
        r = s.simulate(a, 0, 1, 2, s.Management('atr_runner', 1, 1), ZERO)
        self.assertEqual(r['exit_reason'], 'TRAIL')
        self.assertEqual(r['fills'][-1]['time'], 2 * s.STEP)
        self.assertEqual(r['fills'][-1]['raw'], 103)

    def test_trailing_never_widens(self):
        a = bars([[100, 105, 100, 104], [104, 104, 103.5, 104], [104, 104, 102, 103]])
        r = s.simulate(a, 0, 1, 2, s.Management('atr_runner', 1, 1), ZERO)
        self.assertEqual(r['fills'][-1]['raw'], 103)

    def test_long_short_symmetry_zero_cost(self):
        long = bars([[100, 104, 99, 102]])
        short = bars([[100, 101, 96, 98]])
        x = s.simulate(long, 0, 1, 2, s.Management('fixed2r'), ZERO)
        y = s.simulate(short, 0, -1, 2, s.Management('fixed2r'), ZERO)
        self.assertAlmostEqual(x['net'], y['net'])

    def test_color_exit_next_hour_open(self):
        a = bars([[100, 102, 99, 101]] * 12 + [[103, 110, 50, 60]])
        r = s.simulate(a, 0, 1, 2, s.Management('color', 0), ZERO, [s.HOUR])
        self.assertEqual(r['fills'][-1]['raw'], 103)
        self.assertEqual(r['fills'][-1]['time'], s.HOUR)

    def test_color_with_catastrophic_stop(self):
        a = bars([[100, 102, 97, 101]])
        self.assertEqual(s.simulate(a, 0, 1, 2, s.Management('color', 1), ZERO)['exit_reason'], 'INITIAL_STOP')
        self.assertEqual(s.simulate(a, 0, 1, 2, s.Management('color', 0), ZERO)['status'], 'INCOMPLETE')

    def test_timeout_72h_not_favorable_future_bar(self):
        a = bars([[100, 101, 99, 100]] * (72 * 12 + 1))
        r = s.simulate(a, 0, 1, 2, s.Management('color', 0), ZERO)
        self.assertEqual(r['exit_reason'], 'TIMEOUT')
        self.assertEqual(r['hold_hours'], 72)

    def test_gap_stop_fills_adverse_open(self):
        a = bars([[95, 96, 94, 95]])
        # Entry=100 via close-fill sensitivity. Gap below 98 initial stop.
        r = s.simulate(a, 0, 1, 2, s.Management('fixed1r'), ZERO, close_fill=100)
        self.assertEqual(r['fills'][0]['raw'], 95)

    def test_stop_slippage_adverse(self):
        a = bars([[100, 100, 97, 98]])
        r = s.simulate(a, 0, 1, 2, s.Management('fixed1r'))
        self.assertLess(r['fills'][0]['price'], r['fills'][0]['raw'])

    def test_missing_bar_censors_trade(self):
        a = bars([[100, 101, 99, 100]] * 3)
        self.assertEqual(s.simulate(a[[0, 2]], 0, 1, 2, s.Management(), ZERO)['status'], 'INCOMPLETE')

    def test_unknown_entry_not_filled_inside_signal(self):
        a = bars([[100, 102, 98, 101]])
        self.assertEqual(s.simulate(a, s.HOUR, 1, 2, s.Management(), ZERO)['status'], 'INCOMPLETE')

    def test_costs_configurable_invalid_blocked(self):
        for value in (-1, float('nan'), 100):
            with self.assertRaises(ValueError):
                s.Costs(value)


class MethodologySafetyTests(unittest.TestCase):
    def test_clean_splits(self):
        self.assertEqual(s.period(s.TRAIN_END - 1), 'TRAIN')
        self.assertEqual(s.period(s.TRAIN_END), 'VALIDATION')
        self.assertEqual(s.period(s.VALID_END - 1), 'VALIDATION')
        self.assertEqual(s.period(s.VALID_END), 'TEST')

    def selection(self, p, value=.01):
        return dict(period=p, parameters=asdict(s.Management()), metrics=dict(trades=100, mean_net=value))

    def test_test_cannot_select(self):
        with self.assertRaisesRegex(ValueError, 'TEST_SELECTION_BLOCKED'):
            s.choose({'a': self.selection('TEST')}, {'a': self.selection('VALIDATION')})

    def test_only_train_validation_choose(self):
        train = {'a': self.selection('TRAIN', .02), 'b': self.selection('TRAIN', .01)}
        val = {'a': self.selection('VALIDATION', -.03), 'b': self.selection('VALIDATION', .005)}
        self.assertEqual(s.choose(train, val)['key'], 'b')

    def test_small_development_sample_fallback(self):
        t = self.selection('TRAIN')
        t['metrics']['trades'] = 99
        self.assertTrue(s.choose({'a': t}, {'a': self.selection('VALIDATION')})['fallback'])

    def test_changed_frozen_spec_rejected_before_loading_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'preregistered.json').write_text('{}', encoding='utf-8')
            data = root / 'dummy.npz'
            data.write_bytes(b'not used: guard must reject first')
            (root / 'frozen_selection.json').write_text(json.dumps(dict(code_sha256='wrong')), encoding='utf-8')
            with patch.object(s, 'ROOT', root), patch.object(s, 'CACHE', root), patch.object(np, 'load') as load:
                with self.assertRaisesRegex(ValueError, 'FROZEN_SPEC_CHANGED'):
                    runner.run('test', data, 123)
                load.assert_not_called()

    def test_whole_trade_be_sensitive_to_all_cost_components(self):
        baseline = s.economic_breakeven(100, 101, 1, ZERO)
        self.assertGreater(s.economic_breakeven(100, 101, 1, s.Costs(5, 0, 0)), baseline)
        self.assertGreater(s.economic_breakeven(100, 101, 1, s.Costs(0, 0, 5)), baseline)
        self.assertGreater(s.economic_breakeven(100, 100.8, 1, ZERO), baseline)

    def test_promotion_gates_json_serializable(self):
        m = dict(trades=120, mean_net=.01, profit_factor=1.2, without_best3_mean_net=.005)
        ci = dict(mean_ci95=[.001, .02])
        gates = runner.promotion_gates(dict(min_dev_mean=.002), m, m,
            dict(mean_advantage=.001, bootstrap=ci), ci, {'2024': m, '2025': m}, {'a': m, 'b': m})
        self.assertTrue(all(type(v) is bool for v in gates.values()))
        json.dumps(gates, allow_nan=False)

    def test_volatility_filters_not_selected(self):
        spec = json.loads((s.ROOT / 'preregistered.json').read_text('utf-8'))
        self.assertIn('no filters selected', spec['selection'])

    def test_matched_controls_exact_strata_non_event(self):
        h = bars([[100, 102, 98, 101]] * 5)
        h[:, 0] = s.START + np.arange(5) * 24 * s.HOUR
        f = dict(h=h, atr=np.ones(5), atr_pct=np.full(5, .01), trend4=np.ones(5), known4=np.ones(5, bool),
                 trend_d=np.ones(5), known_d=np.ones(5, bool))
        date = s.datetime.fromtimestamp((h[0, 0] + s.HOUR) / 1000, s.timezone.utc)
        e = dict(index=0, timestamp=int(h[0, 0] + s.HOUR), event='GREEN_CROSS', side=1, period='TRAIN',
                 month=date.strftime('%Y-%m'), hour=1, trend4=1, known4=True, volatility=2, reference=101)
        controls = s.matched_controls(f, [e], [e], [.005, .02, .03])
        self.assertEqual(len(controls), 1)
        self.assertNotEqual(controls[0]['index'], 0)
        self.assertEqual(controls[0]['timestamp'] % s.DAY, s.HOUR)
        self.assertEqual(controls, s.matched_controls(f, [e], [e], [.005, .02, .03]))

    def test_control_unmatched_not_relaxed(self):
        h = bars([[100, 102, 98, 101]])
        h[0, 0] = s.START
        f = dict(h=h, atr=np.ones(1), atr_pct=np.ones(1), trend4=np.ones(1), known4=np.ones(1, bool))
        e = dict(index=0, month='2020-01', hour=1, trend4=1, known4=True, volatility=4)
        self.assertEqual(s.matched_controls(f, [e], [e], [.005, .02, .03]), [])

    def test_bootstrap_weekly_and_deterministic(self):
        rows = [dict(status='COMPLETE', entry_time=i * s.DAY, net=i / 1000) for i in range(15)]
        self.assertEqual(s.bootstrap(rows), s.bootstrap(rows))
        self.assertEqual(s.bootstrap(rows)['blocks'], 3)

    def test_top_best_worst3_concentration(self):
        a = bars([[100, 102, 99, 101]])
        row = s.simulate(a, 0, 1, 1, s.Management('fixed1r'), ZERO)
        values = [dict(row, entry_time=i * s.HOUR, exit_time=(i + 1) * s.HOUR, net=i / 1000) for i in range(8)]
        out = s.summarize(values)
        self.assertAlmostEqual(out['without_best3_mean_net'], .002)
        self.assertAlmostEqual(out['without_worst3_mean_net'], .005)

    def test_pending_never_counts_as_loss(self):
        self.assertEqual(s.summarize([dict(status='INCOMPLETE')])['trades'], 0)

    def test_any_compute_execution_zero_http(self):
        import requests
        with patch.object(requests.Session, 'request', side_effect=AssertionError('HTTP forbidden')):
            for name in s.EVENTS:
                for side in (1, -1):
                    for m in s.candidates():
                        s.simulate(bars([[100, 104, 96, 101]]), 0, side, 2, m)
            s.forward(bars([[100, 102, 98, 101]] * 12), event(), 1)

    def test_research_ast_has_no_execution_or_secret_reads(self):
        for path in ('research/mlrsi_1h_core.py', 'research/mlrsi_1h_run.py', 'research/mlrsi_1h_data.py'):
            tree = ast.parse(Path(path).read_text('utf-8'))
            names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            self.assertFalse(names & {'post', 'put', 'delete', 'environ', 'getenv', 'place_order', 'flash_close_position'})
            imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertNotIn('guardian_bitunix', imports)
            self.assertNotIn('trade_guardian', imports)

    def test_only_market_public_url(self):
        from research.mlrsi_1h_data import URL
        self.assertEqual(URL, 'https://data-api.binance.vision/api/v3/klines')

    def test_explicit_nonparity_and_15m_preserved(self):
        spec = json.loads((s.ROOT / 'preregistered.json').read_text('utf-8'))
        self.assertEqual(spec['parity'], 'Exact BackQuant TradingView parity is NOT proven.')
        self.assertIn('15M = NO EDGE', spec['source_study'])

    def test_completed_artifacts_bound_to_frozen_spec_and_code(self):
        for name in ('development_results.json', 'test_results.json', 'frozen_selection.json'):
            a = json.loads((s.ROOT / name).read_text('utf-8'))
            self.assertEqual(a['code_sha256'], runner.code_hash())
            self.assertEqual(a['spec_sha256'], s.digest(s.ROOT / 'preregistered.json'))

    def test_selection_receipt_precedes_test(self):
        receipt = json.loads((s.ROOT / 'freeze_receipt.json').read_text('utf-8'))
        self.assertTrue(receipt['test_file_absent_at_freeze'])
        self.assertEqual(receipt['selection_sha256'], s.digest(s.ROOT / 'frozen_selection.json'))
        self.assertEqual(receipt['development_results_sha256'], s.digest(s.ROOT / 'development_results.json'))

    def test_diagnostic_replay_matches_preregistered_model_results(self):
        test = json.loads((s.ROOT / 'test_results.json').read_text('utf-8'))
        diagnostic = json.loads((s.ROOT / 'diagnostics.json').read_text('utf-8'))
        for key, r in diagnostic['results'].items():
            for model, v in r.items():
                if model != 'forward_excursion_means':
                    self.assertEqual(v['metrics'], test['results'][key]['models'][model]['TEST']['metrics'])

    def test_report_preserves_nonparity_and_no_live_promotion(self):
        report = (s.ROOT / 'RESULTS.md').read_text('utf-8')
        self.assertIn('Exact BackQuant TradingView parity is NOT proven.', report)
        self.assertIn('15M = NO EDGE for tested hypothesis', report)
        self.assertNotIn('READY FOR LIVE', report)

    def test_simulation_deterministic(self):
        a = bars([[100, 105, 100, 104], [104, 104, 102.5, 103]])
        self.assertEqual(s.simulate(a, 0, 1, 2, s.Management()), s.simulate(a, 0, 1, 2, s.Management()))


if __name__ == '__main__':
    unittest.main()
