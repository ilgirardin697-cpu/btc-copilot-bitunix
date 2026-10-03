"""Offline causal/execution fixtures; these are NOT TradingView parity exports."""
import ast
import copy
import inspect
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Research workflow installs numpy/requests') from None
from research import mlrsi_pattern_backtest as study
from guardian_signals import cluster_three, pine_rsi, pine_ema, rolling_mlrsi


ZERO = study.Costs(0, 0, 0)


def bars(prices, start=0):
    return np.asarray([[start + i * study.STEP, *p, 10, 5] for i, p in enumerate(prices)], float)


class IndicatorTests(unittest.TestCase):
    def test_saved_fixtures_explicitly_not_tradingview(self):
        fixture = json.loads((study.ROOT / 'math_fixtures.json').read_text('utf-8'))
        self.assertEqual(fixture['provenance'], 'INDEPENDENT_MATH_NOT_TRADINGVIEW_EXPORT')
        np.testing.assert_array_equal(cluster_three(fixture['clustering']['input'])[0], fixture['clustering']['centroids'])

    def test_color_equality_is_neutral(self):
        from guardian_signals import states_and_events
        state = states_and_events(np.array([20, 30, 40, 50, 60]), np.full(5, 30), np.full(5, 50))[0]
        np.testing.assert_array_equal(state, [-1, 0, 0, 0, 1])

    def test_wilder_seed_and_update_independent_fixture(self):
        rsi = pine_rsi([10, 11, 10, 12, 11], 3)
        self.assertTrue(np.isnan(rsi[:3]).all())
        self.assertAlmostEqual(rsi[3], 75)
        self.assertAlmostEqual(rsi[4], 100 * 2 / (2 + 5 / 3))

    def test_ema_seed_and_alpha(self):
        np.testing.assert_allclose(pine_ema([np.nan, 10, 20, 15], 4), [np.nan, 10, 14, 14.4], equal_nan=True)

    def test_percentile_centroid_fixture(self):
        centers, _, converged = cluster_three([10, 10, 50, 50, 90, 90])
        np.testing.assert_array_equal(centers, [10, 50, 90])
        self.assertTrue(converged)

    def test_cluster_against_independent_absolute_distance_reference(self):
        values = np.random.default_rng(12).uniform(10, 90, 100)
        c = np.quantile(values, [.25, .5, .75])
        for _ in range(1000):
            labels = abs(values[:, None] - c).argmin(axis=1)
            updated = np.array([values[labels == k].mean() if np.any(labels == k) else c[k] for k in range(3)])
            if np.array_equal(updated, c):
                break
            c = updated
        np.testing.assert_allclose(cluster_three(values)[0], c, atol=1e-10)

    def test_mlrsi_prefix_invariant(self):
        prices = np.random.default_rng(3).uniform(100, 105, 150)
        full = rolling_mlrsi(prices, 27, 64)
        for n in (40, 70, 110):
            prefix = rolling_mlrsi(prices[:n], 27, 64)
            for key in ('rsi', 'centroids', 'state', 'valid'):
                np.testing.assert_allclose(prefix[key], full[key][:n], equal_nan=True)

    def test_rolling_window_only_prior_finite_samples(self):
        prices = np.random.default_rng(3).uniform(100, 105, 100)
        ml = rolling_mlrsi(prices, 27, 16)
        self.assertEqual(ml['window_count'][-1], 16)
        np.testing.assert_allclose(ml['centroids'][-1], cluster_three(ml['rsi'][-16:])[0])

    def test_feature_source_low_not_close(self):
        a = bars([[100 + i, 102 + i, 98 + i, 101 + i] for i in range(48)])
        q = study.aggregate(a, study.QUARTER)
        result = dict(rsi=np.ones(len(q)), state=np.ones(len(q)), valid=np.ones(len(q), bool),
                      converged=np.ones(len(q), bool))
        with patch.object(study, 'rolling_mlrsi', return_value=result) as calc:
            study.features(a)
        np.testing.assert_array_equal(calc.call_args.args[0], q[:, 3])
        self.assertFalse(np.array_equal(calc.call_args.args[0], q[:, 4]))
        self.assertEqual(calc.call_args.kwargs, dict(length=27, max_data=3000, max_iter=1000))

    def test_context_closed_hour_only(self):
        h = bars([[100, 102, 98, 101] for _ in range(220)])
        h[:, 0] = np.arange(220) * study.HOUR
        q = h[199:202].copy()
        q[:, 0] += study.HOUR - study.QUARTER
        before = study.context(q, h)
        h[-1, 1:5] = [1000, 2000, 1, 1500]
        after = study.context(q, h)
        for x, y in zip(before, after):
            np.testing.assert_array_equal(x, y)


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.rsi = np.array([40, 60, 62, 61, 61, 63, 64, 62, 65, 66], float)
        self.states = np.array([0] + [1] * 9)

    def test_green_cross_once(self):
        events = study.detect_events(self.rsi, self.states)
        np.testing.assert_array_equal(events['GREEN_CROSS'], [1])

    def test_red_cross_direct_opposite_transitions(self):
        e = study.detect_events([50, 30, 70, 20], [0, -1, 1, -1])
        np.testing.assert_array_equal(e['RED_CROSS'], [1, 3])
        np.testing.assert_array_equal(e['GREEN_CROSS'], [2])

    def test_green_resume_reset_flat_and_down(self):
        np.testing.assert_array_equal(study.detect_events(self.rsi, self.states)['GREEN_RESUME'], [5, 8])

    def test_red_resume_symmetric(self):
        np.testing.assert_array_equal(study.detect_events(100 - self.rsi, -self.states)['RED_RESUME'], [5, 8])

    def test_no_duplicate_on_every_rising_candle(self):
        e = study.detect_events([40, 60, 59, 61, 62, 63, 64], [0, 1, 1, 1, 1, 1, 1])
        np.testing.assert_array_equal(e['GREEN_RESUME'], [3])

    def test_two_bar_confirmation_not_retrospective(self):
        e = study.detect_events(self.rsi, self.states, confirmations=2)
        np.testing.assert_array_equal(e['GREEN_CROSS'], [2])
        np.testing.assert_array_equal(e['GREEN_RESUME'], [6, 9])

    def test_two_bar_pending_cancelled_on_neutral(self):
        e = study.detect_events([40, 60, 59, 61, 62], [0, 1, 1, 1, 0], confirmations=2)
        self.assertEqual(len(e['GREEN_RESUME']), 0)

    def test_cross_not_also_resume_on_color_change(self):
        e = study.detect_events([50, 40, 70], [0, 0, 1])
        np.testing.assert_array_equal(e['GREEN_CROSS'], [2])
        self.assertEqual(len(e['GREEN_RESUME']), 0)

    def test_signal_prefix_and_future_changes(self):
        full = study.detect_events(self.rsi, self.states, confirmations=2)
        for count in range(2, len(self.rsi)):
            prefix = study.detect_events(self.rsi[:count], self.states[:count], confirmations=2)
            for key in study.EVENTS:
                np.testing.assert_array_equal(prefix[key], full[key][full[key] < count])

    def test_missing_bar_resets_event_state(self):
        ts = np.arange(len(self.rsi)) * study.QUARTER
        ts[5:] += study.QUARTER
        e = study.detect_events(self.rsi, self.states, timestamps=ts)
        self.assertNotIn(5, e['GREEN_RESUME'])


class ExecutionTests(unittest.TestCase):
    def path(self):
        return bars([[100000, 100400, 100050, 100300],
                     [100300, 101000, 100200, 100900],
                     [100900, 101000, 100400, 100600]])

    def test_next_bar_entry_no_signal_candle_fill(self):
        a = bars([[100000, 200000, 1, 100000], [100000, 100100, 99500, 99900]])
        r = study.simulate(a, study.STEP, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['entry'], 100000)
        self.assertEqual(r['entry_time'], study.STEP)
        self.assertFalse(r['tp1'])

    def test_partial_tp_and_breakeven_move(self):
        r = study.simulate(self.path(), 0, 1, 1000, study.Management(), ZERO)
        self.assertTrue(r['tp1'])
        self.assertTrue(r['moved_be'])
        self.assertEqual([f['qty'] for f in r['fills']], [.3, .7])
        self.assertEqual(r['fills'][0]['raw'], 100300)

    def test_fixed500_trailing(self):
        r = study.simulate(self.path(), 0, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['exit_reason'], 'TRAIL')
        self.assertEqual(r['fills'][-1]['raw'], 100500)
        self.assertAlmostEqual(r['net'], .0044)

    def test_atr_trailing_frozen_at_entry(self):
        a = self.path()
        a[1, 2] = 101500
        a[2, 1:5] = [101400, 101500, 100700, 101000]
        r = study.simulate(a, 0, 1, 1000, study.Management('atr', .003, .75), ZERO)
        self.assertEqual(r['fills'][-1]['raw'], 100750)
        self.assertEqual(r['exit_reason'], 'TRAIL')

    def test_trail_not_applied_inside_its_update_candle(self):
        a = self.path()
        a[1, 2] = 101500  # raised stop 101000 would touch this same bar's low
        r = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['exit_time'], 2 * study.STEP)  # next bar's OPEN gap, not prior intrabar
        self.assertEqual(r['fills'][-1]['raw'], 100900)  # next-bar gap through raised stop

    def test_stop_and_target_same_bar_stop_precedes(self):
        a = bars([[100000, 101000, 99000, 100500]])
        r = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['exit_reason'], 'INITIAL_STOP')
        self.assertFalse(r['tp1'])
        self.assertTrue(r['ambiguity'])
        self.assertAlmostEqual(r['net'], -.003)

    def test_partial_and_be_same_bar_conservative(self):
        a = bars([[100000, 100400, 99900, 100300]])
        r = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['exit_reason'], 'BREAKEVEN')
        self.assertTrue(r['ambiguity'])
        self.assertAlmostEqual(r['net'], .0009)

    def test_all_fill_fees_including_partial_and_runner(self):
        costs = study.Costs(5, 2, 5)
        r = study.simulate(self.path(), 0, 1, 1000, study.Management(), costs)
        expected = .0005 * (1 + sum(f['qty'] * f['price'] / r['entry'] for f in r['fills']))
        self.assertAlmostEqual(r['fees'], expected)
        before_fees = sum(f['qty'] * f['price'] / r['entry'] for f in r['fills']) - 1
        self.assertAlmostEqual(r['net'], before_fees - expected)
        self.assertGreater(r['gross'], r['net'])

    def test_entry_adverse_slippage_both_sides(self):
        a = bars([[100000, 101000, 99000, 100000]])
        for side in (1, -1):
            r = study.simulate(a, 0, side, 1000, study.Management(), study.Costs(0, 2, 5))
            self.assertAlmostEqual(r['entry'], 100000 * (1 + side * .0002))

    def test_stop_slippage_is_separate_and_adverse(self):
        a = bars([[100000, 100100, 99500, 99900]])
        r = study.simulate(a, 0, 1, 1000, study.Management(), study.Costs(0, 0, 10))
        self.assertAlmostEqual(r['fills'][0]['price'], 99700 * .999)

    def test_gap_stop_no_favorable_fill_at_unavailable_stop(self):
        a = bars([[100000, 100100, 99900, 100000], [99000, 99100, 98500, 98800]])
        r = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        self.assertEqual(r['fills'][0]['raw'], 99000)

    def test_long_short_symmetry(self):
        a = self.path()
        mirrored = a.copy()
        mirrored[:, 1] = 200000 - a[:, 1]
        mirrored[:, 2] = 200000 - a[:, 3]
        mirrored[:, 3] = 200000 - a[:, 2]
        mirrored[:, 4] = 200000 - a[:, 4]
        long = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        short = study.simulate(mirrored, 0, -1, 1000, study.Management(), ZERO)
        for key in ('net', 'gross', 'mfe', 'mae', 'hold_hours'):
            self.assertAlmostEqual(long[key], short[key])

    def test_fixed_one_and_two_r_baselines(self):
        a = bars([[100000, 100700, 99900, 100600]])
        for kind, expected in (('fixed1r', .003), ('fixed2r', .006)):
            r = study.simulate(a, 0, 1, 1000, study.Management(kind), ZERO)
            self.assertAlmostEqual(r['net'], expected)
            self.assertEqual(r['exit_reason'], 'TARGET')

    def test_opposite_signal_executes_open_not_future_low(self):
        a = bars([[100000, 100100, 99900, 100000], [100200, 100500, 90000, 100300]])
        r = study.simulate(a, 0, 1, 1000, study.Management('opposite'), ZERO, [study.STEP])
        self.assertEqual(r['fills'][0]['raw'], 100200)
        self.assertAlmostEqual(r['net'], .002)

    def test_missing_future_gap_censored(self):
        a = bars([[100000, 100100, 99900, 100000], [100000, 100100, 99900, 100000]])
        a[1, 0] += study.STEP
        self.assertEqual(study.simulate(a, 0, 1, 1000, study.Management(), ZERO)['status'], 'INCOMPLETE')

    def test_incomplete_future_or_open_candle_censored(self):
        self.assertEqual(study.simulate(self.path(), 0, 1, 1000, study.Management(), ZERO, cutoff=study.STEP - 1)['status'], 'INCOMPLETE')

    def test_prefix_and_unseen_future_do_not_change_completed_trade(self):
        a = self.path()
        r = study.simulate(a, 0, 1, 1000, study.Management(), ZERO)
        later = np.vstack([a, [3 * study.STEP, 100000, 200000, 1, 100000, 10, 5]])
        self.assertEqual(r, study.simulate(later, 0, 1, 1000, study.Management(), ZERO))

    def test_close_fill_sensitivity_separate_from_primary(self):
        r = study.simulate(self.path(), 0, 1, 1000, study.Management(), ZERO, close_fill=100010)
        self.assertEqual(r['reference'], 100010)

    def test_stop_never_widens_even_if_trail_greater_than_risk(self):
        a = bars([[100000, 100400, 100050, 100300], [100200, 100300, 99990, 100100]])
        r = study.simulate(a, 0, 1, 20000, study.Management('atr'), ZERO)
        self.assertEqual(r['fills'][-1]['raw'], 100000)
        self.assertEqual(r['exit_reason'], 'BREAKEVEN')


class MethodologyTests(unittest.TestCase):
    def test_canonical_text_hash_survives_windows_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'first.py', Path(tmp) / 'second.py'
            first.write_bytes(b'x = 1\ny = 2\n')
            second.write_bytes(b'x = 1\r\ny = 2\r\n')
            self.assertEqual(study.digest(first), study.digest(second))

    def test_public_market_data_endpoint_only(self):
        from research import mlrsi_pattern_data
        self.assertEqual(mlrsi_pattern_data.URL, 'https://data-api.binance.vision/api/v3/klines')
        tree = ast.parse(inspect.getsource(mlrsi_pattern_data))
        network = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == 'get' and isinstance(n.func.value, ast.Name) and n.func.value.id == 'http']
        self.assertEqual(len(network), 1)
        self.assertEqual(ast.dump(network[0].args[0]), "Name(id='URL', ctx=Load())")

    def test_full_pipeline_freezes_then_test_without_network(self):
        rng = np.random.default_rng(9)
        prices = rng.uniform(100, 101, 720)
        base = bars([[p, p + .2, p - .2, p] for p in prices], start=study.START)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = (study.ROOT / 'preregistered.json').read_bytes()
            (root / 'preregistered.json').write_bytes(config)
            np.savez_compressed(root / 'data.npz', bars=base)
            with patch.object(study, 'ROOT', root), patch.object(study, 'CACHE', root / 'cache'), \
                    patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK')) as http, patch('builtins.print'):
                study.run('development', root / 'data.npz', study.VALID_END)
                frozen = (root / 'frozen_selection.json').read_bytes()
                study.run('test', root / 'data.npz', study.VALID_END)
                first = json.loads((root / 'test_results.json').read_text('utf-8'))
                study.run('test', root / 'data.npz', study.VALID_END)
                self.assertEqual(first, json.loads((root / 'test_results.json').read_text('utf-8')))
                self.assertEqual((root / 'frozen_selection.json').read_bytes(), frozen)
                self.assertEqual(first['base_costs']['fee_bps'], 5)
                self.assertEqual(first['classification'], 'NO EDGE')
                http.assert_not_called()

    def test_aggregate_only_closed_complete_groups(self):
        a = bars([[100, 101, 99, 100] for _ in range(7)])
        q = study.aggregate(study.validate(a, cutoff=6 * study.STEP), study.QUARTER)
        self.assertEqual(len(q), 2)
        a = np.delete(a, 1, axis=0)
        q = study.aggregate(a, study.QUARTER)
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0, 0], study.QUARTER)

    def test_aggregate_low_and_open_close_semantics(self):
        a = bars([[100, 105, 95, 101], [101, 106, 90, 102], [102, 110, 99, 103]])
        q = study.aggregate(a, study.QUARTER)[0]
        np.testing.assert_array_equal(q, [0, 100, 110, 90, 103, 30, 15])

    def test_split_boundaries_clean(self):
        self.assertEqual(study.period(study.TRAIN_END - 1), 'TRAIN')
        self.assertEqual(study.period(study.TRAIN_END), 'VALIDATION')
        self.assertEqual(study.period(study.VALID_END - 1), 'VALIDATION')
        self.assertEqual(study.period(study.VALID_END), 'TEST')

    def test_selection_rejects_test(self):
        row = dict(period='TEST', metrics={}, parameters={})
        with self.assertRaisesRegex(ValueError, 'TEST_SELECTION_BLOCKED'):
            study.choose({'a': row}, {})

    def test_selection_deterministic_development_only(self):
        train, val = {}, {}
        for model, means in ((study.Management(), (.001, -.001)), (study.Management('atr'), (.002, .001))):
            for dest, label, mean in ((train, 'TRAIN', means[0]), (val, 'VALIDATION', means[1])):
                dest[model.key()] = dict(period=label, parameters=study.asdict(model), metrics=dict(trades=100, mean_net=mean))
        self.assertEqual(study.choose(train, val), study.Management('atr').key())

    def test_incomplete_not_counted_as_losing_trade(self):
        a = self.complete()
        metrics = study.summarize([a, dict(status='INCOMPLETE')])
        self.assertEqual(metrics['trades'], 1)
        self.assertEqual(metrics['incomplete'], 1)
        self.assertEqual(metrics['loss_rate'], 0)

    def complete(self):
        return study.simulate(ExecutionTests().path(), 0, 1, 1000, study.Management(), ZERO)

    def test_concentration_top_and_worst_three(self):
        rows = [dict(self.complete(), net=x, expectancy_r=x / .003) for x in (-.003, -.002, -.001, .001, .002, .003, .004)]
        metrics = study.summarize(rows)
        self.assertAlmostEqual(metrics['without_top3_expectancy_r'], (-.003 - .002 - .001 + .001) / 4 / .003)
        self.assertAlmostEqual(metrics['without_worst3_expectancy_r'], (.001 + .002 + .003 + .004) / 4 / .003)

    def test_net_breakeven_distinct_from_price_breakeven(self):
        a = bars([[100000, 100400, 99900, 100300]])
        trade = study.simulate(a, 0, 1, 1000, study.Management(), study.Costs(5, 0, 5))
        self.assertEqual(trade['exit_reason'], 'BREAKEVEN')
        self.assertLess(trade['net'], 0)

    def test_sequential_does_not_count_overlapping_capital(self):
        a = self.complete()
        rows = [dict(a, entry_time=0, exit_time=100), dict(a, entry_time=50, exit_time=150), dict(a, entry_time=100, exit_time=200)]
        self.assertEqual(len(study.sequential(rows)), 2)

    def test_bootstrap_deterministic_week_blocks(self):
        a = self.complete()
        rows = [dict(a, entry_time=i * 24 * study.HOUR, net=i * .0001) for i in range(40)]
        self.assertEqual(study.bootstrap(rows), study.bootstrap(rows))
        self.assertGreater(study.bootstrap(rows)['blocks'], 1)

    def test_zero_network_from_simulation_and_signals(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK')) as http:
            self.complete()
            study.detect_events([40, 60, 58, 62], [0, 1, 1, 1])
        http.assert_not_called()

    def test_no_trading_credentials_or_mutating_transport(self):
        for path in ('research/mlrsi_pattern_backtest.py', 'research/mlrsi_pattern_data.py', 'research/mlrsi_pattern_report.py'):
            text = Path(path).read_text('utf-8')
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ('post', 'put', 'delete', 'place_order', 'flash_close_position', 'getenv'))
            for forbidden in ('BITUNIX_API_', 'TELEGRAM_BOT_TOKEN', 'v8_executor', 'trade_guardian', 'guardian_bitunix'):
                self.assertNotIn(forbidden, text)

    def test_report_cannot_silently_use_unfrozen_results(self):
        from research import mlrsi_pattern_report
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('test_results', 'development_results', 'frozen_selection', 'data_manifest'):
                (root / (name + '.json')).write_text(json.dumps({'code_sha256': 'invalid'}), encoding='utf-8')
            with patch.object(study, 'ROOT', root), patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK')) as http:
                with self.assertRaisesRegex(ValueError, 'FROZEN_ARTIFACT_MISMATCH'):
                    mlrsi_pattern_report.report()
                http.assert_not_called()

    def test_parity_gate_explicit_and_no_shadow_promotion(self):
        spec = json.loads((study.ROOT / 'preregistered.json').read_text('utf-8'))
        self.assertEqual(spec['parity'], 'NOT_ESTABLISHED_OFFICIAL_SOURCE_HTTP_401')
        self.assertTrue(spec['promotion_requires_exact_parity'])
        self.assertIn("output['classification'] = 'NO EDGE'", inspect.getsource(study.run))


if __name__ == '__main__':
    unittest.main()
