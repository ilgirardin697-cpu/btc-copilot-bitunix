"""Causal clustering and frozen-selection tests, entirely offline."""
import inspect
import unittest
from unittest.mock import patch

import numpy as np

from research import confluence_exact_mlrsi as e
from research import confluence_engine_backtest as common
from research.test_confluence_engine import bars


def reference_cluster(values, max_iter=1000):
    values = np.asarray(values, float)
    centers = np.quantile(values, [.25, .5, .75])
    for _ in range(max_iter):
        assignments = np.argmin(abs(values[:, None] - centers[None, :]), axis=1)
        updated = centers.copy()
        for i in range(3):
            members = values[assignments == i]
            if len(members):
                updated[i] = members.mean()
        if np.array_equal(updated, centers):
            break
        centers = updated
    return centers


class ExactMlrsiTests(unittest.TestCase):
    def test_three_centroids_match_individual_assignments(self):
        rng = np.random.default_rng(10)
        for n in (4, 10, 50, 3000):
            values = rng.uniform(0, 100, n)
            actual, _, converged = e.cluster_three(values)
            np.testing.assert_allclose(actual, reference_cluster(values), atol=1e-10)
            self.assertTrue(converged)

    def test_cluster_degenerate_empty_and_ties(self):
        for values in ([50.] * 12, [0., 0., 100., 100.], [10., 20., 30., 40., 50., 60.]):
            actual, _, _ = e.cluster_three(values)
            np.testing.assert_allclose(actual, reference_cluster(values), atol=1e-12)
            self.assertTrue(np.all(np.diff(actual) >= 0))

    def test_pine_rsi_initialization(self):
        close = np.arange(100., 150.)
        rsi = e.pine_rsi(close, 14)
        self.assertTrue(np.all(np.isnan(rsi[:14])))
        np.testing.assert_array_equal(rsi[14:], 100.)
        down = e.pine_rsi(close[::-1], 27)
        np.testing.assert_array_equal(down[27:], 0.)
        raw = np.array([np.nan, np.nan, 20., 40., 80.])
        np.testing.assert_allclose(e.pine_ema(raw), [np.nan, np.nan, 20., 28., 48.8], equal_nan=True)

    def test_wilder_rsi_hand_calculated_seed_and_recursion(self):
        actual = e.pine_rsi(np.array([10., 11., 10., 12., 11.]), 3)
        # Seed gains mean=1, losses mean=1/3 =>75; next gain=2/3,
        # loss=5/9 => 100*(2/3)/(2/3+5/9)=600/11.
        np.testing.assert_allclose(actual, [np.nan, np.nan, np.nan, 75., 600 / 11], equal_nan=True)

    def test_no_event_from_unavailable_threshold(self):
        values = np.array([50., 80.])
        state, green, _, valid = e.states_and_events(values, np.array([np.nan, 40.]), np.array([np.nan, 60.]))
        np.testing.assert_array_equal(state, [0, 1])
        np.testing.assert_array_equal(valid, [0, 1])
        self.assertFalse(green[1])

    def test_clustering_prefix_invariant(self):
        close = bars(350)[:, 4]
        for length in (14, 27):
            full = e.rolling_mlrsi(close, length, max_data=60)
            for n in (45, 90, 173, 299):
                prefix = e.rolling_mlrsi(close[:n], length, max_data=60)
                for key in full:
                    np.testing.assert_allclose(prefix[key], full[key][:n], equal_nan=True, err_msg=key)

    def test_future_cannot_enter_centroids_or_thresholds(self):
        close = bars(230)[:, 4]
        altered = close.copy()
        altered[150:] *= np.linspace(5, 100, len(close) - 150)
        original = e.rolling_mlrsi(close, 14, max_data=50)
        changed = e.rolling_mlrsi(altered, 14, max_data=50)
        for key in ('centroids', 'short_threshold', 'long_threshold', 'state', 'green_event', 'red_event'):
            np.testing.assert_allclose(original[key][:150], changed[key][:150], equal_nan=True)

    def test_rolling_maxdata_and_current_close(self):
        close = bars(250)[:, 4]
        actual = e.rolling_mlrsi(close, 27, max_data=31)
        for i in (31, 60, 170, 249):
            available = actual['rsi'][:i + 1]
            available = available[np.isfinite(available)][-31:]
            self.assertEqual(actual['window_count'][i], len(available))
            if len(available) >= 4:
                np.testing.assert_allclose(actual['centroids'][i], reference_cluster(available), atol=1e-10)
        self.assertEqual(actual['window_count'][-1], 31)
        self.assertEqual(e.rolling_mlrsi(close, 27)['window_count'][-1], 223)

    def test_state_event_transitions_and_equalities(self):
        values = np.array([np.nan, 50, 70, 75, 50, 30, 70, 60, 40.])
        lo = np.full(len(values), 40.)
        hi = np.full(len(values), 60.)
        state, green, red, valid = e.states_and_events(values, lo, hi)
        np.testing.assert_array_equal(state, [0, 0, 1, 1, 0, -1, 1, 0, 0])
        np.testing.assert_array_equal(green, [0, 0, 1, 0, 0, 0, 0, 0, 0])
        np.testing.assert_array_equal(red, [0, 0, 0, 0, 0, 1, 0, 0, 0])
        self.assertFalse(valid[0])

    def test_entry_next_bar_with_actual_ml_state(self):
        base = bars(3600)
        a, regime, atr, ratio = e.hourly_inputs(base)
        ml = e.rolling_mlrsi(a[:, 4], 14, max_data=40)
        row = {'system': 'M', 'mode': 'EVENT', 'threshold': .60, 'side': 1, 'exit': 'opposite'}
        signal = e.entry_signal(ml, regime, ratio, 'M', 'EVENT')
        first = np.flatnonzero(signal[:-1])[0]
        result = e.simulate(a, ml, regime, atr, ratio, np.empty((0, 2)), row, common.START, common.ASOF)
        self.assertEqual(result['trades'][0]['entry_time'], int(a[first + 1, 0]))
        self.assertGreater(result['trades'][0]['entry_time'], a[first, 0])

    def test_no_hidden_regime_exit_without_regime_entry(self):
        ml = {'state': np.array([1, 1, -1]), 'valid': np.ones(3, bool), 'green_event': np.array([1, 0, 0], bool), 'red_event': np.array([0, 0, 1], bool)}
        regime = np.array([-1, -1, -1])
        for side in (1, -1):
            f = e.execution_features(ml, regime, np.ones(3), 'LM', side)
            np.testing.assert_array_equal(f['reg'], np.full(3, side == 1))
        sig = e.entry_signal(ml, regime, np.full(3, .7), 'LM', 'STATE')
        np.testing.assert_array_equal(sig, [1, 1, 0])

    def test_TEST_and_threshold_neighbors_never_select(self):
        def row(name, threshold, val, test):
            return {'id': name, 'side': 1, 'threshold': threshold,
                    'TRAIN': {'trades': 30, 'expectancy': .01, 'Sharpe': 1},
                    'VALIDATION': {'trades': 30, 'expectancy': .01, 'Sharpe': val},
                    'TEST': {'Sharpe': test}}
        rows = [row('a', .60, 2, -100), row('b', .60, 1, 100), row('neighbor', .65, 1000, 1000)]
        self.assertEqual(e.select(rows)['id'], 'a')
        rows[0]['TEST']['Sharpe'] = 10000
        rows[1]['TEST']['Sharpe'] = -10000
        self.assertEqual(e.select(rows)['id'], 'a')
        self.assertIsNone(e.select([rows[2]]))

    def test_no_private_api_no_orders_no_network(self):
        source = inspect.getsource(e)
        for forbidden in ('requests.', 'public_get(', 'v8_executor', 'live_auto', 'os.environ', 'place_order', 'create_order'):
            self.assertNotIn(forbidden, source)
        with patch.object(common.requests, 'get', side_effect=AssertionError('Network prohibited')):
            a, _, _, _ = e.hourly_inputs(bars(1000))
            e.rolling_mlrsi(a[:, 4], 14, max_data=20)

    def test_only_closed_hourly_candles(self):
        a, _, _, _ = e.hourly_inputs(bars(49))
        self.assertEqual(len(a), 4)
        self.assertEqual(a[-1, 0] + 3600000, common.START + 48 * common.STEP)

    def test_exactly_two_presets_and_two_exits(self):
        rows = e.specifications()
        self.assertEqual(len(rows), 88)
        self.assertEqual({r['length'] for r in rows}, {14, 27})
        self.assertEqual({r['exit'] for r in rows}, {'opposite', 'atr'})
        self.assertTrue(all(r['system'] == 'RLM' for r in rows if r['side'] == -1))


if __name__ == '__main__':
    unittest.main()
