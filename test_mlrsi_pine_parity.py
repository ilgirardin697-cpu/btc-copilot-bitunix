"""Offline equivalence of the specified Pine contract; NOT visual TV parity."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Dedicated ML RSI CI installs all required dependencies') from None
from mlrsi_math import CausalSeries, MATH_MODE, CONFIG_VERSION, pine_percentile, pine_cluster_three, PINE_ARRAY_LIMIT
from mlrsi_pine_reference import pine_reference_mlrsi, reference_clusters
from mlrsi_observer import MLRSIObserver, TIMEFRAMES
from test_mlrsi_observer import candle


class PineReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(Path('tests/fixtures/mlrsi_pine_low29.json').read_text('utf-8'))
        cls.lows = cls.fixture['lows']
        cls.anchor = cls.fixture['bootstrap_last_bar_index']
        cls.expected = pine_reference_mlrsi(cls.lows, last_bar_index=cls.anchor)
        cls.series = CausalSeries()
        cls.series.configure_bootstrap(cls.anchor)
        cls.actual = [cls.series.push(x) for x in cls.lows]

    def test_fixture_is_frozen_more_than_3000(self):
        self.assertGreater(len(self.lows), 3000)
        self.assertEqual(self.fixture['source'], 'SYNTHETIC_FROZEN')
        digest = hashlib.sha256(json.dumps(self.lows, separators=(',', ':')).encode('ascii')).hexdigest()
        self.assertEqual(digest, self.fixture['low_sha256'])

    def test_every_bar_raw_rsi_ema_and_three_centroids(self):
        for index, (actual, expected) in enumerate(zip(self.actual, self.expected)):
            for key in ('mlrsi_raw', 'mlrsi_smoothed', 'lower_threshold', 'middle_centroid', 'upper_threshold'):
                if expected[key] is None:
                    self.assertIsNone(actual[key], (index, key))
                else:
                    self.assertAlmostEqual(actual[key], expected[key], places=11, msg=str((index, key)))

    def test_every_bar_colors_iterations_and_counts(self):
        for index, (actual, expected) in enumerate(zip(self.actual, self.expected)):
            for key in ('color', 'valid', 'converged', 'iterations', 'threshold_sample_count'):
                self.assertEqual(actual[key], expected[key], (index, key))
        self.assertEqual({v['color'] for v in self.actual if v['valid']}, {'GREEN', 'NEUTRAL', 'RED'})

    def test_maxdata_gate_off_by_one(self):
        start = self.anchor - 3000
        self.assertEqual(self.actual[start - 1]['threshold_sample_count'], 0)
        self.assertEqual(self.actual[start]['threshold_sample_count'], 1)
        self.assertEqual(self.actual[self.anchor]['threshold_sample_count'], 3001)

    def test_indices_2999_3000_3001(self):
        for i in (2999, 3000, 3001):
            self.assertEqual(self.actual[i]['threshold_sample_count'], i - (self.anchor - 3000) + 1)

    def test_realtime_array_grows_without_eviction(self):
        self.assertEqual(self.actual[self.anchor + 1]['threshold_sample_count'], 3002)
        self.assertEqual(self.actual[-1]['threshold_sample_count'], 3037)
        self.assertAlmostEqual(self.series.history[0], self.actual[self.anchor - 3000]['mlrsi_smoothed'])

    def test_historical_prefix_invariant_with_fixed_anchor(self):
        series = CausalSeries()
        series.configure_bootstrap(self.anchor)
        self.assertEqual([series.push(x) for x in self.lows[:3002]], self.actual[:3002])

    def test_future_low_cannot_mutate_committed_outputs(self):
        saved = copy.deepcopy(self.actual)
        self.series.provisional(500000)
        self.assertEqual(self.actual, saved)

    def test_restart_continues_same_pine_episode(self):
        series = CausalSeries()
        series.configure_bootstrap(self.anchor)
        for low in self.lows[:self.anchor + 1]:
            series.push(low)
        restarted = CausalSeries(json.loads(json.dumps(series.dump())))
        self.assertEqual(restarted.bootstrap_last_bar_index, self.anchor)
        self.assertEqual([restarted.push(x) for x in self.lows[self.anchor + 1:]], self.actual[self.anchor + 1:])

    def test_provisional_rollback_no_tick_accumulation(self):
        original = self.series.dump()
        one, two = self.series.provisional(85000), self.series.provisional(85100)
        self.assertEqual(one['threshold_sample_count'], 3038)
        self.assertEqual(two['threshold_sample_count'], 3038)
        self.assertEqual(self.series.dump(), original)
        clone = CausalSeries(original)
        self.assertEqual(two, clone.push(85100))

    def test_chart_reload_may_repaint_not_prefix_invariant_across_new_anchor(self):
        # This is Pine's visible-history gate, NOT an unbiased research backtest.
        series = CausalSeries()
        series.configure_bootstrap(len(self.lows) - 1)
        for x in self.lows:
            last = series.push(x)
        self.assertEqual(last['threshold_sample_count'], 3001)
        self.assertNotEqual(last['threshold_sample_count'], self.actual[-1]['threshold_sample_count'])


class PinePrimitiveTests(unittest.TestCase):
    def test_known_linear_interpolation_vectors(self):
        for data, expected in (([1, 2, 3, 4], (1.75, 2.5, 3.25)),
                               ([0, 10, 20, 30, 40], (10, 20, 30)),
                               ([40, 10, 10, 20], (10, 15, 25)),
                               ([7], (7, 7, 7))):
            self.assertEqual(tuple(pine_percentile(data, p) for p in (25, 50, 75)), expected)

    def test_numpy_linear_equivalence_not_assumed(self):
        for n in (4, 5, 17, 3000, 3001):
            data = np.random.default_rng(76 + n).normal(size=n).tolist()
            np.testing.assert_allclose([pine_percentile(data, p) for p in (25, 50, 75)],
                                       np.quantile(data, [.25, .5, .75], method='linear'), atol=1e-14)

    def test_percentile_na_and_empty(self):
        self.assertIsNone(pine_percentile([], 50))
        self.assertIsNone(pine_percentile([None, None], 25))
        self.assertEqual(pine_percentile([None, 1, 2, 3, 4], 25), 1.75)

    def test_ties_first_index_not_last(self):
        data = [0, 1, 2, 3, 4]
        centroids, attempts, _ = pine_cluster_three(data, 0)
        # Initial (1,2,3): 1.5/2.5 cases tested with duplicate fractional data.
        self.assertEqual(centroids, [.5, 2, 3.5])
        self.assertEqual(attempts, 1)
        self.assertEqual(pine_cluster_three(data, 0), reference_clusters(data, 0))
        for data in ([0, 1, 1.5, 2, 2.5, 3, 4], [0, 0, 1, 1, 2, 2]):
            self.assertEqual(pine_cluster_three(data, 0), reference_clusters(data, 0))

    def test_loop_zero_executes_once(self):
        self.assertEqual(pine_cluster_three([0, 1, 2, 3, 4], 0)[1], 1)

    def test_loop_1000_includes_1001st_attempt(self):
        calls = 0
        def alternating(*args, **kwargs):
            nonlocal calls
            calls += 1
            if 'weights' not in kwargs:
                return np.ones(3, dtype=int)
            return np.array([1., 2. + (calls // 2) % 2, 3.])
        # Force exact inequality each iteration; finite nonempty clusters.
        with patch('mlrsi_math.np.bincount', side_effect=alternating):
            result = pine_cluster_three([0, 1, 2, 3, 4], 1000)
        self.assertEqual(result[1], 1001)

    def test_empty_clusters_are_na_not_retained(self):
        c, attempts, converged = pine_cluster_three([50.] * 10)
        self.assertEqual(c, [50., None, None])
        self.assertEqual(attempts, 1)
        self.assertFalse(converged)

    def test_convergence_exact_not_epsilon(self):
        self.assertEqual(pine_cluster_three([0, 1, 2, 3, 4]), reference_clusters([0, 1, 2, 3, 4]))

    def test_array_limit_never_silently_rolls(self):
        series = CausalSeries()
        series.history = [None] * PINE_ARRAY_LIMIT
        before = series.dump()
        with self.assertRaisesRegex(ValueError, 'MLRSI_PINE_ARRAY_LIMIT'):
            series.push(100)
        self.assertEqual(len(series.history), PINE_ARRAY_LIMIT)
        self.assertEqual(before, series.dump())

    def test_no_quantile_or_guardian_math_dependency(self):
        source = Path('mlrsi_math.py').read_text('utf-8')
        self.assertNotIn('from guardian_signals', source)
        self.assertNotIn('deque(', source)


class PineObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.low = json.loads(Path('tests/fixtures/mlrsi_pine_low29.json').read_text('utf-8'))['lows'][:3400]

    def make_observer(self, directory, open_candle=True):
        observer = MLRSIObserver(directory, logger=lambda code: None)
        interval = TIMEFRAMES['15m']
        rows = [candle(i * interval, low) for i, low in enumerate(self.low)]
        now = len(rows) * interval + (1000 if open_candle else 0)
        if open_candle:
            rows.append(candle(len(rows) * interval, self.low[-1] - 50))
        observer.observe({'15m': rows}, now)
        return observer, rows, now

    def test_open_last_bar_anchor_3000_confirmed_3001_provisional(self):
        with tempfile.TemporaryDirectory() as folder:
            observer, rows, now = self.make_observer(folder)
            p = observer.frames['15m']
            self.assertEqual(p['latest_confirmed_values']['threshold_sample_count'], 3000)
            self.assertEqual(p['latest_provisional_values']['threshold_sample_count'], 3001)
            self.assertEqual(observer.series['15m'].bootstrap_last_bar_index, len(rows) - 1)
            self.assertEqual(p['last_closed_timestamp'], now - 1000)

    def test_closed_last_bar_anchor_3001_confirmed(self):
        with tempfile.TemporaryDirectory() as folder:
            observer, _, _ = self.make_observer(folder, False)
            self.assertEqual(observer.frames['15m']['latest_confirmed_values']['threshold_sample_count'], 3001)

    def test_status_shows_math_mode_sample_count_centroids(self):
        with tempfile.TemporaryDirectory() as folder:
            observer, _, _ = self.make_observer(folder)
            text = observer.status_text()
            for fragment in ('Math mode: PINE_PARITY', 'Threshold sample count: 3000',
                             'Provisional threshold sample count: 3001', 'RSI: Wilder 29',
                             'Provisional Upper:', 'Provisional Lower:', 'TRADE AUTHORITY: NONE'):
                self.assertIn(fragment, text)

    def test_v2_state_rebuilds_once_old_journal_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            observer, rows, now = self.make_observer(folder)
            old = json.loads(observer.state_path.read_text('utf-8'))
            old['config_version'] = 'CAPTURE_LOW29_EMA4_CAUSAL_V2'
            observer.state_path.write_text(json.dumps(old), encoding='utf-8')
            row = observer._record('COLOR_CHANGE', '15m', True, now)
            row['config_version'] = 'CAPTURE_LOW29_EMA4_CAUSAL_V2'
            journal = json.dumps(row) + '\n'
            observer.journal_path.write_text(journal, encoding='utf-8')
            rebuilt = MLRSIObserver(folder, logger=lambda code: None)
            self.assertEqual(rebuilt.series['15m'].count, 0)
            rebuilt.observe({'15m': rows}, now)
            self.assertEqual(rebuilt.journal_path.read_text('utf-8'), journal)
            self.assertEqual(json.loads(rebuilt.state_path.read_text('utf-8'))['config_version'], CONFIG_VERSION)
            same = MLRSIObserver(folder, logger=lambda code: None)
            self.assertEqual(same.series['15m'].count, len(self.low))
            same.observe({'15m': rows}, now)
            self.assertEqual(same.series['15m'].count, len(self.low))


if __name__ == '__main__':
    unittest.main()
