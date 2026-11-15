"""Synthetic logic tests and public-data replay; NEVER real platform evidence."""
import ast
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np

from research.confluence_1h.indicators import calculate, signals, smooth
from research.confluence_1h_phase2.compare import (SETTINGS, REQUIRED, compare, load_market,
                                                 number, parse_time, read_export)
from research.confluence_1h_phase2.semantics import (HOUR, descriptive_rows, events, timestamps,
                                                    validate_bars)

ROOT = Path(__file__).resolve().parent
LAB = ROOT / 'research/confluence_1h_phase2'
BASE = '522201530c1b81453ea653fc8a1860b1b10eabaf'


def fixture():
    rng = np.random.default_rng(2461)
    c = 80000 * np.exp(np.cumsum(rng.normal(0, .003, 400)))
    o = np.r_[c[0], c[:-1]]
    return np.c_[np.arange(400)*HOUR+parse_time('2026-11-01T00:00:00Z', 'iso8601_offset'),
                 o, np.maximum(o, c)+100, np.minimum(o, c)-100, c, rng.uniform(10, 200, 400)]


def case():
    a = fixture()
    f = calculate(a)
    meta = json.loads((LAB/'export_metadata.template.json').read_text())
    meta.update(platform='SYNTHETIC_TEST_NOT_A_PLATFORM', full_ticker='TEST:BTCUSDT',
                venue='SYNTHETIC_TEST', source_kind='SYNTHETIC_UNIT_FIXTURE', settings=SETTINGS.copy(),
                indicator_history_start_open_ms=int(a[0, 0]))
    meta['timestamp_format'] = 'unix_ms'
    rows = []
    mapping = dict(pececillos='minnows', tendencia='kon_trend', tiburones='sharks', ma_trend='kon_signal',
                   adx='adx', plus_di='plus_di', minus_di='minus_di', ao='ao', atr='atr')
    for i in range(300, 306):
        row = dict(time=str(int(a[i, 0])), available_at=str(int(a[i, 0])+HOUR),
                   emitted_at='', confirmed='true')
        row.update({k: str(a[i, j]) for j, k in enumerate(('open','high','low','close','volume'), 1)})
        row.update({k: str(f[v][i]) for k, v in mapping.items()})
        rows.append(row)
    return a, meta, rows, dict(venue='SYNTHETIC_TEST', symbol='BTCUSDT', timeframe_seconds=3600)


def boundary(sources):
    bad = []
    for path, source in sources.items():
        if path.startswith('research/') or Path(path).name.startswith('test_') or 'tests' in Path(path).parts:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any('confluence_1h_phase2' in n.name for n in node.names):
                bad.append(path)
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('research'):
                if 'confluence_1h_phase2' in (node.module or '') or any(n.name in ('confluence_1h_phase2', '*') for n in node.names):
                    bad.append(path)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and 'confluence_1h_phase2' in node.value:
                bad.append(path)
    return bad


class ComparisonTests(unittest.TestCase):
    def run_case(self, change=None):
        a, meta, rows, market = case()
        if change:
            change(a, meta, rows, market)
        return compare(rows, meta, a, market)

    def test_synthetic_numeric_match_never_unlocks_backtest_or_line_identity(self):
        r = self.run_case()
        self.assertEqual(r['numerical_matches'], 6)
        self.assertFalse(r['new_backtests_allowed'])
        self.assertIn('NOT_EXTERNAL_PLATFORM_EVIDENCE', r['comparison_blockers'])
        self.assertTrue(r['visual_line_identity'].startswith('UNCONFIRMED'))

    def test_mislabeling_pececillos_as_tendencia_detected(self):
        r = self.run_case(lambda a,m,r,v: r[0].update(pececillos=r[0]['tendencia']))
        self.assertEqual(r['numerical_matches'], 5)
        self.assertGreater(r['field_max_abs_error']['pececillos'], 1)

    def test_both_venues_never_merged(self):
        with self.assertRaisesRegex(ValueError, 'VENUE'):
            self.run_case(lambda a,m,r,v: m.update(venue='OTHER'))

    def test_ohlcv_differences_fail_closed(self):
        r = self.run_case(lambda a,m,r,v: r[0].update(volume='999'))
        self.assertEqual(r['rows'][0]['status'], 'DIFFERENCE_OR_WARMUP')

    def test_unknown_settings_and_prefix_are_reported_not_assumed(self):
        r = self.run_case(lambda a,m,r,v: m.update(settings=None, indicator_history_start_open_ms=None))
        self.assertIn('SETTINGS_NOT_CONFIRMED_OR_DIFFERENT', r['comparison_blockers'])
        self.assertIn('INDICATOR_INITIALIZATION_PREFIX_NOT_VERIFIED', r['comparison_blockers'])

    def test_even_claimed_platform_match_requires_manual_line_review(self):
        r = self.run_case(lambda a,m,r,v: m.update(source_kind='OWNER_SUPPLIED_PLATFORM_EXPORT',
                                                 original_indicator_identity_reviewed=True))
        self.assertEqual(r['mathematical_status'], 'NUMERIC_EVIDENCE_REQUIRES_REVIEW')
        self.assertFalse(r['new_backtests_allowed'])

    def test_no_rows_cannot_pass(self):
        r = self.run_case(lambda a,m,r,v: r.clear())
        self.assertEqual(r['records'], 0)
        self.assertIn('NO_EXTERNAL_ROWS', r['comparison_blockers'])

    def test_duplicate_gap_or_reorder_export_rejected(self):
        for indexes in ([0,0,1], [0,2], [1,0]):
            a,m,r,v = case()
            with self.subTest(indexes=indexes), self.assertRaisesRegex(ValueError, 'EXPORT_GAP'):
                compare([r[i] for i in indexes],m,a,v)

    def test_closed_only_and_real_emission_not_before_available(self):
        with self.assertRaisesRegex(ValueError, 'CLOSED_CANDLE'):
            self.run_case(lambda a,m,r,v: r[0].update(confirmed='false'))
        def early(a,m,r,v):
            m['capture_mode']='LIVE';r[0]['emitted_at']=r[0]['time']
        with self.assertRaisesRegex(ValueError, 'EMITTED_BEFORE_CLOSE'):
            self.run_case(early)

    def test_historical_logging_clock_is_not_used_to_realign_bars(self):
        def replay(a,m,r,v):
            for row in r:row['emitted_at']=str(parse_time('2026-11-15T12:00:00Z','iso8601_offset'))
        r=self.run_case(replay)
        self.assertEqual(r['numerical_matches'],6)
        self.assertNotEqual(r['rows'][0]['actual_emitted_at'],r['rows'][0]['earliest_available_at'])

    def test_close_labels_normalized_explicitly_not_fitted(self):
        def closing(a,m,r,v):
            m['timestamp_kind']='close'
            for row in r:row['time']=row['available_at']
        r=self.run_case(closing)
        self.assertEqual(r['numerical_matches'],6)

    def test_no_missing_overlap_pass_and_no_nearest_timestamp_matching(self):
        def shifted(a,m,r,v):
            for row in r:
                row['time']=str(int(row['time'])+1000*HOUR)
                row['available_at']=str(int(row['available_at'])+1000*HOUR)
        r=self.run_case(shifted)
        self.assertEqual(r['numerical_matches'],0)
        self.assertTrue(all(x['status']=='NO_MARKET_OVERLAP' for x in r['rows']))

    def test_rounding_bound_predeclared_per_field(self):
        def rounded(a,m,r,v):
            m['decimal_places']={k:4 for k in REQUIRED}
            for row in r:
                for k in REQUIRED:row[k]=f'{float(row[k]):.4f}'
        self.assertEqual(self.run_case(rounded)['numerical_matches'],6)
        with self.assertRaisesRegex(ValueError,'PRECISION'):
            self.run_case(lambda a,m,r,v: m.update(decimal_places={'adx':0}))

    def test_nonfinite_export_rejected_and_na_is_not_zero(self):
        with self.assertRaisesRegex(ValueError,'NONFINITE'):
            number('inf')
        self.assertIsNone(number('na'))
        r=self.run_case(lambda a,m,r,v:r[0].update(pececillos='na'))
        self.assertIsNone(r['rows'][0]['errors']['pececillos'])

    def test_payload_ticker_history_and_replay_metadata_checked(self):
        for field,value,code in [('full_ticker','OTHER:TICKER','TICKER'),
                                  ('indicator_history_start_open_ms',0,'HISTORY')]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,code):
                self.run_case(lambda a,m,r,v:r[0].update({field:value}))
        def historical(a,m,r,v):
            m['capture_mode']='LIVE';r[0]['historical_recalculation']=True
        with self.assertRaisesRegex(ValueError,'HISTORICAL_REPLAY'):
            self.run_case(historical)

    def test_pine_log_csv_and_jsonl_adapters_keep_original_record_fields(self):
        a,m,rows,v=case()
        raw=json.dumps(rows[0]).encode()
        m['export_format']='JSONL'
        self.assertEqual(read_export(raw,m),[rows[0]])
        buf=io.StringIO();w=csv.writer(buf);w.writerow(['Message'])
        w.writerow(['IGOD_KONCORDE_SERIES_V1='+raw.decode()])
        m.update(export_format='PINE_LOGS_CSV',message_column='Message')
        self.assertEqual(read_export(buf.getvalue().encode(),m),[rows[0]])


class TimingAndSemanticsTests(unittest.TestCase):
    def test_madrid_open_close_availability_are_distinct(self):
        r=timestamps(parse_time('2026-11-15T01:00:00+01:00','iso8601_offset'))
        self.assertEqual(r['open_utc'],'2026-11-15T00:00:00Z')
        self.assertEqual(r['close_utc'],'2026-11-15T01:00:00Z')
        self.assertEqual(r['close_madrid'],'2026-11-15T02:00:00+01:00')
        self.assertIsNone(r['actual_received_at'])

    def test_dst_repeated_clock_needs_explicit_offsets(self):
        a=parse_time('2026-10-25T02:00:00+02:00','iso8601_offset')
        b=parse_time('2026-10-25T02:00:00+01:00','iso8601_offset')
        self.assertEqual(b-a,HOUR)
        with self.assertRaisesRegex(ValueError,'OFFSET'):
            parse_time('2026-11-15T02:00:00','iso8601_offset')

    def test_seconds_microseconds_and_fractional_ms_not_guessed(self):
        for t in ('1794700800','1794700800000000','1794700800000.0'):
            with self.subTest(t=t),self.assertRaises(ValueError):parse_time(t,'unix_ms')

    def test_market_gaps_duplicates_reverse_and_bad_ohlcv_rejected(self):
        a=fixture()
        for bad in (a[[0,2]],a[[0,0]],a[::-1],np.full((1,6),np.nan)):
            with self.assertRaises(ValueError):validate_bars(bad)
        a[0,2]=1
        with self.assertRaisesRegex(ValueError,'OHLC_ORDER'):validate_bars(a)

    def test_pececillos_identity_and_red_average_is_tendencia_not_pececillos(self):
        f=calculate(fixture())
        np.testing.assert_allclose(f['minnows'],f['kon_trend']+f['pvi_osc'],equal_nan=True)
        np.testing.assert_array_equal(f['kon_signal'],smooth(f['kon_trend'],15,'ema'))
        self.assertGreater(np.nanmax(abs(f['kon_signal']-smooth(f['minnows'],15,'ema'))),1)

    def test_pvi_volume_comparison_independent_scalar_oracle(self):
        a=fixture();f=calculate(a);pvi=[1.]
        for i in range(1,len(a)):
            pvi.append(pvi[-1]*a[i,4]/a[i-1,4] if a[i,5]>a[i-1,5] else pvi[-1])
        np.testing.assert_allclose(f['pvi'],pvi,rtol=1e-12)

    def test_all_volume_layers_match_separate_loop_formula(self):
        a=fixture();f=calculate(a)
        for name,rising in [('pvi',True),('nvi',False)]:
            raw=[1.]
            for i in range(1,len(a)):
                changed=a[i,5]>a[i-1,5] if rising else a[i,5]<a[i-1,5]
                raw.append(raw[-1]*a[i,4]/a[i-1,4] if changed else raw[-1])
            ema=[raw[0]]
            for x in raw[1:]:ema.append(x/8+ema[-1]*7/8)
            oscillator=[]
            for i,x in enumerate(raw):
                window=ema[max(0,i-89):i+1];span=max(window)-min(window)
                oscillator.append((x-ema[i])*100/span if span else np.nan)
            np.testing.assert_allclose(f[name+'_osc'],oscillator,rtol=1e-9,atol=1e-8,equal_nan=True)
            if name=='nvi':np.testing.assert_allclose(f['sharks'],oscillator,rtol=1e-9,atol=1e-8,equal_nan=True)

    def test_cross_slope_reversal_and_zero_pass_are_distinct_events_for_all_areas(self):
        f=calculate(fixture()[:5]);f['kon_signal']=np.full(5,-4.)
        for key in ('minnows','kon_trend','sharks'):f[key]=np.array([-6,-5,-3,-1,1.])
        e=events(f)
        for name in ('pececillos','tendencia','tiburones'):
            self.assertEqual(np.flatnonzero(e[name+'_cross_up']).tolist(),[2])
            self.assertEqual(np.flatnonzero(e[name+'_zero_cross_up']).tolist(),[4])
            self.assertFalse(e[name+'_slope_turn_up'].any())

    def test_slope_turn_can_exist_without_red_cross_or_zero_cross(self):
        f=calculate(fixture()[:4]);f['minnows']=np.array([-5,-6,-5,-4.]);f['kon_signal']=np.zeros(4)
        e=events(f)
        self.assertTrue(e['pececillos_slope_turn_up'][2])
        self.assertFalse(e['pececillos_cross_up'].any())
        self.assertFalse(e['pececillos_zero_cross_up'].any())

    def test_export_has_event_parity_for_all_three_areas(self):
        a,m,r,v=case();result=compare(r,m,a,v)
        last=result['rows'][-1]
        for name in ('pececillos','tendencia','tiburones'):
            self.assertIn(name+'_cross_up',last['crosses'])
            self.assertIn(name+'_slope_turn_up',last['events'])
            self.assertIn(name+'_zero_cross_up',last['events'])
        self.assertFalse(any(e['match'] is False for row in result['rows'] for e in row.get('events',{}).values()))

    def test_peak_trough_and_plateau_are_not_interchangeable(self):
        f=calculate(fixture()[:8]);f['adx']=np.array([10,11,12,11,10,11,11,12.])
        e=events(f)
        self.assertEqual(np.flatnonzero(e['adx_turn_down']).tolist(),[3])
        self.assertEqual(np.flatnonzero(e['adx_turn_up']).tolist(),[5])
        self.assertTrue(e['adx_flat'][6]);self.assertFalse(e['adx_turn_up'][7])

    def test_first_negative_recovery_is_not_two_rising_bars(self):
        f=calculate(fixture()[:6]);f['ao']=np.array([-1,-2,-3,-2,-1,1.])
        e=events(f)
        self.assertTrue(e['ao_negative_recovery_turn'][3])
        self.assertFalse(e['ao_negative_two_rising'][3])
        self.assertTrue(e['ao_negative_two_rising'][4])

    def test_positive_deterioration_does_not_mean_negative_ao(self):
        f=calculate(fixture()[:6]);f['ao']=np.array([1,2,3,2,1,-1.])
        e=events(f)
        self.assertTrue(e['ao_positive_deterioration_turn'][3])
        self.assertTrue(e['ao_positive_two_falling'][4])

    def test_both_crosses_can_happen_on_different_bars(self):
        f=calculate(fixture()[:4]);f['kon_trend']=np.array([-1,-1,1,1.])
        f['minnows']=np.array([-2,-2,-1,2.]);f['kon_signal']=np.zeros(4)
        e=events(f)
        self.assertEqual(np.flatnonzero(e['tendencia_cross_up']).tolist(),[2])
        self.assertEqual(np.flatnonzero(e['pececillos_cross_up']).tolist(),[3])

    def test_unknown_prior_cannot_emit_cross(self):
        f=calculate(fixture()[:3]);f['kon_trend']=np.array([np.nan,1,2.]);f['kon_signal']=np.zeros(3)
        self.assertFalse(events(f)['tendencia_cross_up'].any())

    def test_all_descriptive_rows_prefix_invariant(self):
        a=fixture();full=descriptive_rows(a);prefix=descriptive_rows(a[:315])
        self.assertEqual(full[:315],prefix)


class EvidenceAndIsolationTests(unittest.TestCase):
    def test_actual_export_missing_and_no_new_strategy_frozen(self):
        p=json.loads((LAB/'comparison_protocol.json').read_text())
        self.assertIsNone(p['coincidence_window']);self.assertIsNone(p['entry'])
        self.assertIsNone(p['invalidation']);self.assertEqual(p['new_backtests'],0)
        m=json.loads((LAB/'independent_audit_manifest.json').read_text())
        self.assertEqual(m['real_platform_exports'],0)
        self.assertTrue(m['copied_driver_identical_to_original_package'])
        self.assertFalse(m['scripts_executed_in_phase2'])

    def test_public_fixtures_hash_and_range_and_descriptive_focus_only(self):
        for venue in ('BINANCE_SPOT','BINANCE_USDM_PERPETUAL'):
            m=json.loads((LAB/'fixtures'/(venue+'.json')).read_text())
            a=load_market(LAB/'fixtures'/(venue+'.csv.gz'),m)
            self.assertEqual(a[-1,0]+HOUR,parse_time('2026-11-15T06:00:00+01:00','iso8601_offset'))
            self.assertFalse(m['platform_export']);self.assertFalse(m['historical_receipt_attested'])

    def test_tampered_market_input_rejected(self):
        m=json.loads((LAB/'fixtures/BINANCE_SPOT.json').read_text());m['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'MARKET_CHECKSUM'):
            load_market(LAB/'fixtures/BINANCE_SPOT.csv.gz',m)

    def test_nov15_local_observation_different_cross_times_no_platform_claim(self):
        for venue in ('BINANCE_SPOT','BINANCE_USDM_PERPETUAL'):
            rows=list(csv.DictReader((LAB/'artifacts'/(venue+'_focus.csv')).read_text(encoding='utf-8').splitlines()))
            trend=[r['close_madrid'] for r in rows if r['tendencia_cross_up']=='True']
            minnows=[r['close_madrid'] for r in rows if r['pececillos_cross_up']=='True']
            self.assertEqual(trend,['2026-11-15T04:00:00+01:00'])
            self.assertEqual(minnows,['2026-11-15T05:00:00+01:00'])

    def test_every_preexisting_file_in_pr46_and_production_is_unchanged(self):
        changed=subprocess.check_output(['git','diff',BASE,'--name-status','--'],cwd=ROOT,text=True).splitlines()
        allowed=('research/confluence_1h_phase2/','test_confluence_1h_phase2.py',
                 '.github/workflows/confluence-1h-series-parity.yml')
        for line in changed:
            status,path=line.split('\t',1)
            self.assertEqual(status,'A',line)
            self.assertTrue(path.startswith(allowed),line)

    def test_all_runtime_sources_cannot_depend_on_phase2(self):
        paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','*.py'],cwd=ROOT,text=True).splitlines()
        sources={p:(ROOT/p).read_text('utf-8-sig') for p in paths}
        self.assertEqual(boundary(sources),[])
        for source in ('import research.confluence_1h_phase2 as r',
                       'from research import confluence_1h_phase2 as r',
                       'from research.confluence_1h_phase2.semantics import events',
                       '__import__("research.confluence_1h_phase2")'):
            self.assertTrue(boundary({'trade_guardian.py':source}))

    def test_phase2_code_has_no_engine_simulator_or_network_dependency(self):
        forbidden={'requests','urllib','socket','engine','simulate','ccxt','guardian_bitunix'}
        for path in LAB.glob('*.py'):
            tree=ast.parse(path.read_text('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in node.names]+([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                    for name in names:self.assertFalse(forbidden.intersection(name.split('.')),str(path)+':'+name)

    def test_new_pine_passive_three_named_plots_and_no_changed_original(self):
        text=(LAB/'I_GOD_Koncorde_Three_Series.pine').read_text('utf-8')
        for name in ('pececillos','tendencia','tiburones','ma_trend','historyStart','barstate.isconfirmed','time_close','timenow'):
            self.assertIn(name,text)
        for token in ('strategy.','alert(','request.security','plotshape('):self.assertNotIn(token,text)
        self.assertIn('input.bool(false',text)


if __name__=='__main__':
    unittest.main()
