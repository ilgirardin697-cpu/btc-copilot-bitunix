"""Offline user-observed TradingView table vs calculations, never fitted thresholds."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Dedicated ML RSI CI explicitly installs numpy/requests') from None
from mlrsi_math import CausalSeries, CONFIG_VERSION, pine_percentile
from mlrsi_pine_reference import pine_reference_mlrsi
from mlrsi_observer import MLRSIObserver

FIXTURES = Path('tests/fixtures')


class ExactSourceParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = json.loads((FIXTURES / 'mlrsi_binance_low_20261004.json').read_text('utf-8'))
        cls.table = json.loads((FIXTURES / 'mlrsi_tradingview_fixture_20261004.json').read_text('utf-8'))
        cls.series = CausalSeries()
        cls.series.configure_bootstrap(cls.public['bootstrap_last_bar_index'])
        cls.results = [cls.series.push(low) for low in cls.public['lows']]
        cls.reference = pine_reference_mlrsi(cls.public['lows'], last_bar_index=cls.public['bootstrap_last_bar_index'])
        first, interval = cls.public['first_open_timestamp_ms'], cls.public['interval_ms']
        cls.indices = [(row['open_timestamp_ms'] - first) // interval for row in cls.table['observations']]

    def test_source_is_user_supplied_authority_with_unchanged_constructors(self):
        self.assertEqual(self.table['authority'], 'USER_DIRECT_TRADINGVIEW_SOURCE_TAB_AND_DATA_TABLE')
        source = (FIXTURES / self.table['source_file']).read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(hashlib.sha256(source).hexdigest(), self.table['source_sha256'])
        text = source.decode('utf-8')
        for snippet in ('var centroids = array.new_float(3)', 'distances = array.new_float(3)',
                        'new_centroids = array.new_float(3)', 'if f_arrays_equal(new_centroids, centroids)'):
            self.assertIn(snippet, text)
        self.assertNotIn('array.sort(rsi_values)', text)
        self.assertIn('Mozilla Public License 2.0', text)

    def test_inputs_frozen_checksum_closed_and_contiguous(self):
        p = self.public
        digest = hashlib.sha256(json.dumps(p['lows'], separators=(',', ':')).encode('ascii')).hexdigest()
        self.assertEqual(digest, p['low_sha256'])
        self.assertEqual(p['row_count'], len(p['lows']))
        self.assertGreater(p['row_count'], 3000)
        self.assertEqual(p['last_open_timestamp_ms'] - p['first_open_timestamp_ms'], (p['row_count'] - 1) * p['interval_ms'])
        self.assertEqual(p['bootstrap_last_bar_index'], 3999)  # original replay, not tuned
        for source in p['sources']:
            self.assertTrue(source['url'].startswith('https://data-api.binance.vision/api/v3/klines?'))
            self.assertEqual(len(source['sha256']), 64)

    def test_literal_reference_every_real_bar(self):
        for i, (actual, reference) in enumerate(zip(self.results, self.reference)):
            for key in ('mlrsi_raw', 'mlrsi_smoothed', 'lower_threshold', 'middle_centroid', 'upper_threshold'):
                if reference[key] is None:
                    self.assertIsNone(actual[key], (i, key))
                else:
                    self.assertAlmostEqual(actual[key], reference[key], places=11, msg=str((i, key)))
            for key in ('color', 'threshold_sample_count', 'iterations', 'valid', 'converged'):
                self.assertEqual(actual[key], reference[key], (i, key))

    def test_all_ten_tradingview_rows_match_rsi_and_thresholds_at_display_precision(self):
        self.assertEqual(len(self.table['observations']), 10)
        for row, i in zip(self.table['observations'], self.indices):
            actual = self.results[i]
            for displayed, key in (('displayed_rsi', 'mlrsi_smoothed'),
                                   ('displayed_long_threshold', 'upper_threshold'),
                                   ('displayed_short_threshold', 'lower_threshold')):
                self.assertEqual(format(actual[key], '.2f'), row[displayed], (row['open_time_utc'], key))
            self.assertEqual(actual['color'], 'GREEN')
            if row['explicitly_observed_color']:
                self.assertEqual(actual['color'], row['explicitly_observed_color'])

    def test_1030_old_mismatch_explained_without_rsi_or_gate_changes(self):
        actual = self.results[self.indices[6]]
        old = self.table['prior_v3_python_1030']
        self.assertEqual(actual['mlrsi_smoothed'], old['mlrsi_smoothed'])
        self.assertEqual(actual['threshold_sample_count'], 3000)
        self.assertEqual(format(actual['upper_threshold'], '.2f'), '56.15')
        self.assertEqual(format(actual['lower_threshold'], '.2f'), '45.55')
        self.assertNotAlmostEqual(actual['upper_threshold'], old['upper_threshold'])
        self.assertEqual(actual['color'], 'GREEN')
        self.assertEqual(old['color'], 'NEUTRAL')

    def test_rsi_ema_and_history_gate_ast_unchanged_from_7659(self):
        old = subprocess.check_output(['git', 'show', '7659f8dbb9616136e43cf24531076b42f7c9ef82:mlrsi_math.py']).decode('utf-8')
        new = Path('mlrsi_math.py').read_text('utf-8')
        def rsi_prelude(source):
            tree = ast.parse(source)
            series = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CausalSeries')
            push = next(n for n in series.body if isinstance(n, ast.FunctionDef) and n.name == 'push')
            result = []
            for node in push.body:
                result.append(ast.dump(node, include_attributes=False))
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'result' for t in node.targets):
                    break
            return result
        self.assertEqual(rsi_prelude(new), rsi_prelude(old))

    def test_retained_percentiles_and_one_iteration_on_mature_bars(self):
        for i in self.indices:
            history = [v['mlrsi_smoothed'] for v in self.results[999:i + 1]]
            actual = self.results[i]
            self.assertEqual([actual[k] for k in ('lower_threshold', 'middle_centroid', 'upper_threshold')],
                             [pine_percentile(history, p) for p in (25, 50, 75)])
            self.assertEqual(actual['iterations'], 1)
        self.assertEqual(self.series.pine_centroids[3:], [None] * 3)

    def test_positional_unsorted_percentile_does_not_explain_tv(self):
        i = self.indices[6]
        data = [v['mlrsi_smoothed'] for v in self.results[999:i + 1]]
        rank = (len(data) - 1) * .75
        positional = data[int(rank)] + (data[int(rank) + 1] - data[int(rank)]) * (rank - int(rank))
        self.assertNotEqual(format(positional, '.2f'), self.table['observations'][6]['displayed_long_threshold'])
        self.assertEqual(format(pine_percentile(data, 75), '.2f'), self.table['observations'][6]['displayed_long_threshold'])

    def test_boundary_and_realtime_counts_unchanged(self):
        self.assertEqual(self.results[998]['threshold_sample_count'], 0)
        self.assertEqual(self.results[999]['threshold_sample_count'], 1)
        self.assertEqual(self.results[3999]['threshold_sample_count'], 3001)
        self.assertEqual(self.results[4000]['threshold_sample_count'], 3002)
        self.assertEqual(self.results[4001]['threshold_sample_count'], 3003)

    def test_restart_preserves_six_slot_carry_and_not_just_three_thresholds(self):
        series = CausalSeries()
        series.configure_bootstrap(self.public['bootstrap_last_bar_index'])
        for low in self.public['lows'][:3999]:
            series.push(low)
        restored = CausalSeries(json.loads(json.dumps(series.dump())))
        self.assertEqual(restored.pine_centroids, series.pine_centroids)
        self.assertEqual(len(restored.pine_centroids), 6)
        for i in range(3999, len(self.results)):
            self.assertEqual(restored.push(self.public['lows'][i]), self.results[i])

    def test_provisional_uses_literal_math_and_rollback(self):
        original = copy.deepcopy(self.series.dump())
        provisional = self.series.provisional(self.public['lows'][-1] - 100)
        expected = pine_reference_mlrsi(self.public['lows'] + [self.public['lows'][-1] - 100],
                                        last_bar_index=self.public['bootstrap_last_bar_index'])[-1]
        self.assertEqual(provisional, expected)
        self.assertEqual(self.series.dump(), original)

    def test_normal_constructor_seed_runs_before_data_gate(self):
        series = CausalSeries()
        series.configure_bootstrap(3999)
        self.assertEqual(series.push(self.public['lows'][0])['threshold_sample_count'], 0)
        self.assertEqual(series.pine_centroids, [None] * 6)
        self.assertEqual(series.count, 1)

    def test_snapshot_confirmed_green_with_no_network_or_bitunix(self):
        p = self.public
        now = self.table['observations'][6]['open_timestamp_ms'] + p['interval_ms']
        rows = [dict(time=p['first_open_timestamp_ms'] + i * p['interval_ms'],
                     open=x + 5, low=x, high=x + 10, close=x + 5) for i, x in enumerate(p['lows'][:4000])]
        # At the original as-of, candle index3999 is open. Its final OHLC is
        # NEVER fed into a confirmed calculation; only its timestamp sets anchor.
        with tempfile.TemporaryDirectory() as directory, patch.object(requests.Session, 'request', side_effect=AssertionError('NO_HTTP')):
            observer = MLRSIObserver(directory, logger=lambda _: None, clock=lambda: now / 1000)
            observer.observe({'15m': rows}, now + 240000)
            self.assertEqual(observer.frames['15m']['confirmed_color'], 'GREEN')
            self.assertEqual(observer.frames['15m']['latest_confirmed_values']['threshold_sample_count'], 3000)
            text = observer.status_text()
            self.assertIn('Math mode: PINE_PARITY', text)
            self.assertIn('RSI: Wilder 29', text)
            self.assertIn('Upper: 56.15', text)
            self.assertIn('TRADE AUTHORITY: NONE', text)

    def test_diagnostic_keeps_exact_source_cluster_block(self):
        source = (FIXTURES / 'backquant_user_source.pine').read_text('utf-8')
        diagnostic = (FIXTURES / 'mlrsi_backquant_diagnostic.pine').read_text('utf-8')
        def core(text):
            block = text.split('// Clustering for RSI\n', 1)[1].split('// Dynamic thresholds\n', 1)[0]
            return '\n'.join(line for line in block.splitlines() if 'diag_' not in line)
        self.assertEqual(core(source), core(diagnostic))
        for fragment in ('DIAG threshold sample count', 'DIAG last_bar_index', 'DIAG bar_index',
                         'DIAG initial percentile 25', 'DIAG final centroid 2', 'DIAG iterations',
                         'DIAG unsorted percentile 75', 'DIAG sorted copy percentile 75'):
            self.assertIn(fragment, diagnostic)
        self.assertNotIn('array.sort(rsi_values)', diagnostic)

    def test_fixture_is_observation_not_full_precision_parity_claim(self):
        self.assertEqual(self.table['displayed_decimal_places'], 2)
        self.assertEqual(self.table['date_column_semantics'], 'CANDLE_OPEN_TIME')
        self.assertTrue(any('NOT proven' in warning for warning in self.table['limitations']))
        self.assertEqual(CONFIG_VERSION, 'CAPTURE_LOW29_EMA4_PINE_PARITY_V4')


if __name__ == '__main__':
    unittest.main()
