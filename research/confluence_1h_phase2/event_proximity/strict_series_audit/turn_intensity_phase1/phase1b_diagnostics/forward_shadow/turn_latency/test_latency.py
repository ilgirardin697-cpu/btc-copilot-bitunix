import ast
import json
from pathlib import Path
import subprocess
import unittest
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Numerical research CI must install NumPy; optional bare-runtime environment') from error
from research.confluence_1h.indicators import calculate, smooth, bbwp
from .diagnostic import detect, features, episodes, price_description, confirmation_stability, H, HERE
from .compare_export import compare, SETTINGS


def times(n):
    return 1667260800000+np.arange(n, dtype=np.int64)*H


def bars(n=400):
    t = np.arange(n)
    c = 100+t*.03+np.sin(t/7)
    return np.column_stack((times(n), c, c+.4, c-.5, c, 50+10*np.sin(t)))


def clean(x):
    if isinstance(x, dict):
        return {k:clean(v) for k,v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return None if isinstance(x, float) and not np.isfinite(x) else x


class TimingTests(unittest.TestCase):
    def test_deceleration_is_not_turn_and_confirmation_not_backdated(self):
        x = [0, 125, 210, 248, 211]
        d = detect(times(5), x, 'ao')
        self.assertEqual([a['i'] for a in d['alerts']], [2])
        self.assertEqual([a['i'] for a in d['turns']], [4])
        self.assertEqual(d['resolutions'][0]['hours'], 2)
        self.assertEqual(d['resolutions'][0]['status'], 'CONFIRMED')
        self.assertEqual(d['alerts'][0]['expected_slope'], -1)
        self.assertEqual(d['hourly'][2]['acceleration'], -40)

    def test_mirror_symmetry(self):
        a = detect(times(5), [0,125,210,248,211], 'ao')
        b = detect(times(5), [0,-125,-210,-248,-211], 'ao')
        self.assertEqual([x['i'] for x in a['alerts']], [x['i'] for x in b['alerts']])
        self.assertEqual(a['alerts'][0]['expected_slope'], -b['alerts'][0]['expected_slope'])
        self.assertEqual([x['i'] for x in a['turns']], [x['i'] for x in b['turns']])

    def test_false_reacceleration(self):
        d = detect(times(5), [0,10,15,21,28], 'ao')
        self.assertEqual(len(d['alerts']), 1)
        self.assertEqual(d['resolutions'][0]['status'], 'INVALID_REACCELERATION')

    def test_expiry_without_turn_and_no_repeated_alerts(self):
        d = detect(times(7), [0,10,18,24,28,31,33], 'ao')
        self.assertEqual(len(d['alerts']), 1)
        self.assertEqual(d['resolutions'][0]['status'], 'EXPIRED_2H')

    def test_flat_invalidates(self):
        d = detect(times(4), [0,10,15,15], 'ao')
        self.assertEqual(d['resolutions'][0]['status'], 'INVALID_FLAT')
        self.assertEqual(d['turns'], [])

    def test_turn_without_prealert_is_kept(self):
        d = detect(times(4), [0,2,5,1], 'ao')
        self.assertEqual(d['alerts'], [])
        self.assertEqual(d['turns'][0]['prior_alert_id'], None)

    def test_end_of_file_is_censored_not_false(self):
        a = bars(3)
        d = detect(a[:,0]+H, [0,10,15], 'ao')
        e = episodes(a, d)
        self.assertEqual(e[0]['status'], 'CENSORED_END_OF_FILE')
        self.assertFalse(e[0]['price_horizon_complete'])
        self.assertIsNone(e[0]['up_remaining_pre_pct'])

    def test_gap_clears_pending(self):
        t = times(5)
        t[3:] += H
        d = detect(t, [0,10,15,17,18], 'ao')
        self.assertEqual(d['resolutions'][0]['status'], 'INVALID_DATA')

    def test_nan_clears_pending(self):
        d = detect(times(5), [0,10,15,np.nan,18], 'ao')
        self.assertEqual(d['resolutions'][0]['status'], 'INVALID_DATA')

    def test_prefix_invariance_causal_records(self):
        x = np.sin(np.arange(50)/2)+np.cos(np.arange(50)/7)
        full = detect(times(len(x)), x, 'ao')
        for n in range(3, len(x)):
            p = detect(times(n), x[:n], 'ao')
            for key, idx in [('alerts','i'), ('turns','i'), ('resolutions','resolution_i'), ('hourly','i')]:
                self.assertEqual(clean(p[key]), clean([r for r in full[key] if r[idx] < n]))

    def test_future_prices_do_not_change_alerts(self):
        x = np.r_[0,125,210,248,211,np.arange(20)]
        d = detect(times(len(x)), x, 'ao')
        a = bars(len(x)); b = a.copy(); b[5:,1:5] *= 5
        self.assertEqual(episodes(a,d)[0]['available_at'], episodes(b,d)[0]['available_at'])
        self.assertEqual(episodes(a,d)[0]['up_known_anchor'], episodes(b,d)[0]['up_known_anchor'])

    def test_known_anchor_ignores_lower_future_low(self):
        a = bars(10); a[3:,3] = 1
        alert = dict(i=2, known_leg_start_i=0)
        p = price_description(a, alert, dict(status='CONFIRMED', resolution_i=4))
        self.assertGreater(p['up_known_anchor'], 90)

    def test_remaining_excludes_prealert_own_bar(self):
        a = bars(10); a[2,2] = 10000
        p = price_description(a, dict(i=2, known_leg_start_i=0), dict(status='CONFIRMED', resolution_i=4))
        self.assertLess(p['up_remaining_pre_pct'], 10)

    def test_confirm_instability_is_not_price_failure(self):
        r = confirmation_stability(np.array([3,2,4,5,4.]), times(5), dict(i=2, slope_direction=1))
        self.assertEqual(r['stability'], 'FLAT_OR_REVERSED_WITHIN_2H')
        self.assertEqual(r['unstable_after_hours'], 2)

    def test_confirm_stability_censored(self):
        r = confirmation_stability(np.array([3,2,4.]), times(3), dict(i=2, slope_direction=1))
        self.assertEqual(r['stability'], 'CENSORED')


class FormulaTests(unittest.TestCase):
    def test_7_100_unchanged(self):
        a = bars()
        np.testing.assert_array_equal(features(a)['bbwp_7_100'], calculate(a)['bbwp'])

    def test_13_252_literal_rank_from_prior_widths(self):
        a = bars(); f = features(a)
        widths = np.full(len(a), np.nan)
        for i in range(12, len(a)):
            w = a[i-12:i+1,4]
            widths[i] = 2*np.std(w)/np.mean(w)
        expected = np.full(len(a), np.nan); history = []
        for i in range(13, len(a)):
            ordered = sorted(history[-252:])
            if ordered:
                equals = [j for j,v in enumerate(ordered) if v == widths[i]]
                rank = max(equals) if equals else sum(v < widths[i] for v in ordered)
                expected[i] = rank*100/len(ordered)
            history.append(widths[i])
        np.testing.assert_array_equal(f['bbwp_13_252'], expected)

    def test_bbwp_literal_tie_is_preserved_not_silently_fixed(self):
        r = bbwp(np.r_[np.full(13,np.nan), 1.,2.,2.,1.], 252, 13)
        self.assertEqual(r[14], 100)
        self.assertEqual(r[15], 50)

    def test_ao_direct_five_thirty_four(self):
        a = bars(); f = features(a); median = (a[:,2]+a[:,3])/2
        expected = np.mean(median[-5:])-np.mean(median[-34:])
        self.assertAlmostEqual(f['ao'][-1], expected, places=11)

    def test_adx_monotonic_known_limit(self):
        a = bars(); a[:,1:5] = np.arange(len(a))[:,None]+np.array([100,102,99,101])[None,:]
        f = features(a)
        self.assertAlmostEqual(f['adx'][-1], 100, places=10)
        self.assertEqual(f['minus_di'][-1], 0)
        self.assertGreater(f['plus_di'][-1], 0)

    def test_red_is_ema_of_trend_not_pececillos(self):
        f = features(bars())
        np.testing.assert_array_equal(f['roja'], smooth(f['tendencia'],15,'ema'))
        self.assertFalse(np.allclose(f['roja'][-50:], smooth(f['pececillos'],15,'ema')[-50:]))

    def test_feature_prefix_invariance(self):
        a = bars(); full = features(a); prefix = features(a[:290])
        for k in full:
            np.testing.assert_array_equal(full[k][:290], prefix[k])


class ExternalEvidenceTests(unittest.TestCase):
    def test_no_external_export_cannot_establish_parity(self):
        r = compare([], {}, bars(), 'BINANCE_SPOT')
        self.assertEqual(r['status'], 'NOT_ESTABLISHED')
        self.assertIn('NO_REAL_PLATFORM_ROWS', r['blockers'])

    def test_synthetic_comparison_checks_math_not_authenticity(self):
        a = bars(); f = features(a); i = 350
        row = dict(open_time_ms=int(a[i,0]), available_at_ms=int(a[i,0])+H, confirmed=True,
                   **dict(zip(('open','high','low','close','volume'), a[i,1:])), **{k:v[i] for k,v in f.items()})
        meta = dict(platform='TradingOne', source_kind='REAL_PLATFORM_EXPORT', full_ticker='EXPLICIT_TEST_FIXTURE',
                    venue='BINANCE_SPOT', history_first_open_ms=int(a[0,0]), settings=SETTINGS,
                    indicator_identities_reviewed=True)
        r = compare([row], meta, a, 'BINANCE_SPOT')
        json.dumps(r, allow_nan=False)
        self.assertEqual(r['status'], 'NUMERIC_MATCH_REQUIRES_SOURCE_REVIEW')
        self.assertIn('Synthetic', r['note'])
        meta['settings'] = None
        self.assertEqual(compare([row],meta,a,'BINANCE_SPOT')['status'], 'NOT_ESTABLISHED')

    def test_open_bar_or_wrong_available_time_is_rejected(self):
        row = dict(open_time_ms=int(times(1)[0]),available_at_ms=int(times(1)[0]),confirmed=True)
        with self.assertRaisesRegex(ValueError, 'CLOSED_AVAILABILITY'):
            compare([row], {}, bars(), 'BINANCE_SPOT')

    def test_no_network_trade_or_simulation_imports(self):
        forbidden = {'requests','urllib','socket','ccxt','engine','simulator','guardian_bitunix','telegram'}
        for p in HERE.glob('*.py'):
            tree = ast.parse(p.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                names = [x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                for name in names:
                    self.assertFalse(set(name.split('.')) & forbidden, (p.name,name))

    def test_previous_sources_and_pr55_are_unchanged(self):
        root = HERE.parents[7]
        changed = subprocess.check_output(['git','diff','9616b50c7eb34d27bdb33cde14ead31e0340daa4','--name-status'],cwd=root,text=True).splitlines()
        prefix = HERE.relative_to(root).as_posix()+'/'
        for line in changed:
            self.assertTrue(line.startswith('A\t'+prefix), line)

    def test_no_runtime_depends_on_this_package(self):
        root = HERE.parents[7]
        paths = subprocess.check_output(['git','ls-files','--','*.py'], cwd=root,text=True).splitlines()
        for p in paths:
            if p.startswith('research/') or Path(p).name.startswith('test_'):
                continue
            self.assertNotIn('turn_latency', (root/p).read_text(encoding='utf-8-sig'), p)


if __name__ == '__main__':
    unittest.main()
