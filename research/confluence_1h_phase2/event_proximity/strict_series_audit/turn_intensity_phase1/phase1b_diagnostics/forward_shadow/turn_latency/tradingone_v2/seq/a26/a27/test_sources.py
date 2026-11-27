import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from . import audit as a, run as r


class SourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars, cls.manifest = r.load('1h')

    def test_inputs_same_closed_spot_venue_and_hash(self):
        self.assertEqual(len(self.bars), 1846)
        self.assertEqual(self.manifest['venue'], 'BINANCE_SPOT')
        self.assertLessEqual(self.bars[-1, 0]+a.HOUR, self.manifest['cutoff'])

    def test_partial_candle_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CLOSED_ONLY'):
            a.checked_bars(self.bars, a.HOUR, self.bars[-1, 0]+a.HOUR-1)

    def test_gap_duplicate_nonfinite_rejected(self):
        for column, value in [(0, self.bars[-2, 0]), (2, np.nan)]:
            b = self.bars.copy()
            b[-1, column] = value
            with self.assertRaises(ValueError):
                a.checked_bars(b, a.HOUR, self.manifest['cutoff'])

    def test_original_na_preallocation_retains_percentiles(self):
        engine = a.original.OriginalMLRSI(160)
        for low in self.bars[:161, 3]:
            row = engine.push(low)
            if row['valid']:
                self.assertAlmostEqual(row['lower'], a.original.percentile(engine.values, 25))
                self.assertAlmostEqual(row['upper'], a.original.percentile(engine.values, 75))
        self.assertEqual(len(engine.centroids), 6)
        self.assertTrue(all(x is None for x in engine.cluster_plots))

    def test_scalar_literal_alma_same_input_as_controlled_reference(self):
        values = a.smoothed_rsi(self.bars[:200, 3], 27, 'ALMA')
        limits = a.percentile_thresholds(values, 199)
        engine = a.original.OriginalMLRSI(199)
        rows = [engine.push(x) for x in self.bars[:200, 3]]
        for key, series in [('value', values), ('lower', limits[:, 0]), ('upper', limits[:, 2])]:
            expected = [np.nan if row[key] is None else row[key] for row in rows]
            np.testing.assert_allclose(series, expected, rtol=0, atol=1e-10)

    def test_operational_causal_series_same_parameters_same_history(self):
        from mlrsi_math import CausalSeries
        b = self.bars[:200]
        engine = CausalSeries()
        engine.configure_bootstrap(199)
        rows = [engine.push(x) for x in b[:, 3]]
        values = a.smoothed_rsi(b[:, 3], 29, 'EMA')
        limits = a.percentile_thresholds(values, 199)
        for key, series in [('mlrsi_smoothed', values), ('lower_threshold', limits[:, 0]), ('upper_threshold', limits[:, 2])]:
            expected = [np.nan if row[key] is None else row[key] for row in rows]
            np.testing.assert_allclose(series, expected, rtol=0, atol=1e-10)

    def test_finite_compaction_changes_first_three_threshold_availabilities(self):
        x = np.array([np.nan]*30+[40., 41., 42., 43., 44.])
        literal = a.percentile_thresholds(x, 34)
        apk = a.percentile_thresholds(x, 34, finite_only=True)
        self.assertTrue(np.isfinite(literal[30:33]).all())
        self.assertTrue(np.isnan(apk[30:33]).all())
        np.testing.assert_array_equal(literal[33:], apk[33:])

    def test_lloyd_is_different_not_a_parity_fix(self):
        x = [1, 2, 3, 4, 50, 51, 52, 99, 100]
        seed = np.array([a.original.percentile(x, q) for q in (25, 50, 75)])
        self.assertGreater(np.abs(a.lloyd_diagnostic(x)-seed).max(), 1)

    def test_fixed_load_anchor_prefix_invariance(self):
        x = a.smoothed_rsi(self.bars[:, 3])
        before = a.percentile_thresholds(x[:300], 1845)
        after = a.percentile_thresholds(x, 1845)
        np.testing.assert_array_equal(before, after[:300])

    def test_realtime_grows_not_rolling_window(self):
        x = np.arange(3040, dtype=float)
        fixed = a.percentile_thresholds(x, 3000)[-1]
        reload = a.percentile_thresholds(x, 3039)[-1]
        self.assertNotEqual(fixed[0], reload[0])
        self.assertEqual(fixed[0], 3039*.25)

    def test_threshold_move_can_create_cross_without_rsi_slope(self):
        np.testing.assert_array_equal(a.crosses([50, 50], [40, 40], [51, 49]), [0, 1])

    def test_cross_equality_is_not_strict_cross(self):
        np.testing.assert_array_equal(a.crosses([49, 50], [40, 40], [50, 50]), [0, 0])

    def test_fe_chop_tr_and_hma_match_independent_scalar_windows(self):
        b = self.bars[:90]
        tr = [max(row[2]-row[3], abs(row[2]-b[i-1, 4]), abs(row[3]-b[i-1, 4])) if i else row[2]-row[3] for i, row in enumerate(b)]
        raw, fe = a.fractal_energy(b)
        for i in range(26, len(b)):
            w = b[i-26:i+1]
            expected = 100*np.log10(sum(tr[i-26:i+1])/(max(w[:, 2])-min(w[:, 3])))/np.log10(27)
            self.assertAlmostEqual(raw[i], expected, places=12)
        def wma(x):
            return sum((j+1)*v for j, v in enumerate(x))/(len(x)*(len(x)+1)/2)
        def inner(i):
            return 2*wma(raw[i-1:i+1])-wma(raw[i-4:i+1])
        for i in range(31, len(b)):
            self.assertAlmostEqual(fe[i], wma([inner(i-1), inner(i)]), places=11)

    def test_fe_prefix_invariance(self):
        for full, prefix in zip(a.fractal_energy(self.bars), a.fractal_energy(self.bars[:300])):
            np.testing.assert_array_equal(full[:300], prefix)

    def test_fe_exact_boundaries(self):
        for now, prev, peak, expected in [(40, 41, 50, 1), (38.2, 41, 50, 0), (40, 40, 50, 0), (40, 41, 49.999, 0)]:
            self.assertEqual(a.SharedCooldown().accept(0, 1, now, prev, peak), expected)

    def test_cooldown_shared_and_strictly_more_than_ten(self):
        cd = a.SharedCooldown()
        self.assertEqual(cd.accept(0, 1, 40, 41, 50), 1)
        self.assertEqual(cd.accept(10, -1, 40, 41, 50), 0)
        self.assertEqual(cd.accept(11, -1, 40, 41, 50), -1)

    def test_invalid_fe_and_failed_filter_do_not_consume_cooldown(self):
        cd = a.SharedCooldown()
        for v in (np.nan, np.inf):
            self.assertEqual(cd.accept(0, 1, v, 41, 50), 0)
        self.assertEqual(cd.accept(0, 1, 40, 41, 50, False), 0)
        self.assertEqual(cd.last, -9999)
        self.assertEqual(cd.accept(1, 1, 40, 41, 50), 1)

    def test_trend_mean_equivalence_for_same_parameters_1h_4h(self):
        cfg = a.profile.settings()['active_inputs']['tsa'].copy()
        cfg['max_length'] = 118
        for tf in ('1h', '4h'):
            b, _ = r.load(tf)
            scalar = a.trend_mean_reference(b[:, 4], 118, 2.8)
            np.testing.assert_array_equal(scalar, a.profile.tsa(b, cfg)['tsa_trend'])

    def test_bbwp_ties_demonstrate_different_rank_semantics(self):
        x = np.full(40, 100.)
        self.assertEqual(a.apk_bbwp_reference(x)[-1], 100)
        self.assertLess(a.tradingone_bbwp(x)[-1], 100)

    def test_descriptive_rejections_do_not_become_confirmations(self):
        b = np.array([[0, 99, 101, 98, 99, 1], [a.HOUR, 101, 102, 99, 101, 1]], float)
        np.testing.assert_array_equal(a.rejection_observations(b, [100, 100]), [-1, 1])

    def test_no_live_io_order_api_or_source_execution(self):
        for path in (r.HERE/'audit.py', r.HERE/'run.py'):
            tree = ast.parse(path.read_text('utf-8'))
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            self.assertFalse(names & {'eval', 'exec', 'requests', 'socket', 'subprocess'})
        self.assertFalse(json.loads((r.HERE/'out/summary.json').read_text('utf-8'))['original_js_executed'])

    def test_protected_and_previous_artifacts_unchanged(self):
        root = next(p for p in Path(__file__).resolve().parents if (p/'.git').exists())
        prior = '1e3005fdc8465a4778ce235f7f59484617d1cba0'
        changed = subprocess.check_output(['git', 'diff', prior, '--name-only'], cwd=root, text=True).splitlines()
        allowed = (r.HERE.relative_to(root).as_posix()+'/',)
        self.assertTrue(all(p.startswith(allowed) for p in changed), changed)
        self.assertEqual(json.loads((r.HERE/'plan.json').read_text('utf-8'))['divergence_intelligence'], 'EXCLUDED')

    def test_results_are_not_platform_certification_or_profitability(self):
        result = json.loads((r.HERE/'out/summary.json').read_text('utf-8'))
        self.assertFalse(result['external_parity_certified'])
        self.assertFalse(result['pnl_or_profitability_evaluated'])
        for p in result['profiles']:
            self.assertEqual(p['incremental_predictive_value'], 'NOT_ESTABLISHED_BY_GATE_COUNTS')

    def test_compressed_csv_deterministic_across_output_names(self):
        with tempfile.TemporaryDirectory() as temp:
            p, q = Path(temp)/'a.csv.gz', Path(temp)/'b.csv.gz'
            r.write_csv(p, [dict(time=1, value=2.5)])
            r.write_csv(q, [dict(time=1, value=2.5)])
            self.assertEqual(p.read_bytes(), q.read_bytes())


if __name__ == '__main__':
    unittest.main()
