"""Read-only instrumentation and diagnostics, not alternative-strategy evidence."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Dedicated research CI requires NumPy') from error
from .. import detect as frozen
from ..test_turns import fixture
from ..evaluate import clean
from ..outcomes import outcome
from ..inference import required_n
from . import trace
from .replay import latency, read_fixture, hourly, early_turns, BEGIN, HERE

PREFIX='research/confluence_1h_phase2/event_proximity/strict_series_audit/turn_intensity_phase1/phase1b_diagnostics/'
ROOT=HERE.parents[5]
BASE='a48af422f485554dd28ee8da45a3cf1aa0a01929'


class InstrumentationTests(unittest.TestCase):
    def test_traced_events_and_audit_identical_all_patterns_and_mirrors(self):
        for p in range(3):
            for side in (1,-1):
                a,f,i=fixture(p,side);before={k:v.copy() for k,v in f.items()}
                expected,audit=frozen.detect(a,f);actual,aa,rows=trace.instrument(a,f)
                self.assertEqual(clean(actual),clean(expected));self.assertEqual(aa,audit)
                self.assertTrue(rows)
                for k in f:np.testing.assert_array_equal(f[k],before[k])
    def test_previous_trace_restored_on_success(self):
        previous=sys.gettrace();sentinel=lambda frame,event,arg:None
        try:
            sys.settrace(sentinel);a,f,i=fixture();trace.instrument(a,f)
            self.assertIs(sys.gettrace(),sentinel)
        finally:sys.settrace(previous)
    def test_trace_restored_on_error(self):
        previous=sys.gettrace()
        with self.assertRaises(ValueError):trace.instrument(np.ones((2,2)),{})
        self.assertIs(sys.gettrace(),previous)
    def test_unrecognized_original_source_fails_closed(self):
        with patch.object(trace,'EXPECTED_SOURCE','0'*64),self.assertRaisesRegex(ValueError,'UNRECOGNIZED'):
            trace.source_lines()
    def test_pececillos_missing_prior_slope_does_not_get_relaxed(self):
        a,f,i=fixture();f['minnows'][i-4:i+1]=[-1,-2,-1,0,1]
        self.assertTrue(frozen.two_turn(f['ao'],1)[i]);self.assertTrue(frozen.two_turn(f['adx'],-1)[i])
        self.assertFalse(frozen.two_turn(f['minnows'],1)[i])
        events,_,rows=trace.instrument(a,f)
        self.assertFalse(any(e['pattern']==frozen.PATTERNS[0] and e['side']==1 for e in events))
        row=next(r for r in rows if r['i']==i and r['pattern']==frozen.PATTERNS[0] and r['side']==1)
        self.assertIn('pece',row['missing_tokens'])
    def test_funnel_final_counts_are_original_events(self):
        a,f,i=fixture();ee,aa,rr=trace.instrument(a,f)
        counts,potential=trace.funnel(a,f,ee,aa,rr,{'TEST':(0,len(a)+25)})
        for row in counts:
            events=[e for e in ee if e['pattern']==row['pattern'] and e['side']==row['side']]
            for s in ('ALL','Q75','Q90'):self.assertEqual(row[s],sum(s in e['strata'] for e in events))
        self.assertTrue(potential)
    def test_trace_prefix_invariance(self):
        a,f,i=fixture();ee,aa,rr=trace.instrument(a,f)
        pre={k:v[:20] for k,v in f.items()};ev,av,rv=trace.instrument(a[:20],pre)
        self.assertEqual(clean([r for r in rr if r['i']<20]),clean(rv))
        self.assertEqual(clean([e for e in ee if e['i']<20]),clean(ev))
    def test_actual_alignment_reasons_are_not_rewritten_as_dmi_only(self):
        a,f,i=fixture(1,-1);f['plus_di'][:]=50
        _,_,rows=trace.instrument(a,f)
        row=next(r for r in rows if r['i']==i and r['pattern']==frozen.PATTERNS[1] and r['side']==-1)
        self.assertIn('dmi_ok',row['failed_flags']);self.assertTrue(row['adx_slope_ok'])


class TimingTests(unittest.TestCase):
    def case(self):
        a,f,i=fixture();a[:,0]=BEGIN+np.arange(len(a))*frozen.HOUR
        f['adx_slope']=f['adx']-frozen.lag(f['adx']);f['kon_signal']=np.zeros(len(a))
        ee,_,rr=trace.instrument(a,f);return a,f,i,ee,rr
    def test_hindsight_extreme_never_labeled_causal_entry(self):
        a,f,i,ee,_=self.case();rows=latency('SYNTHETIC',a,f,ee)
        old=[r for r in rows if r['stage']=='EXTREME_HINDSIGHT']
        self.assertTrue(old);self.assertTrue(all(not r['causal'] for r in old))
        self.assertTrue(all(r['extreme_intrabar_timestamp']=='UNKNOWN' for r in old))
        self.assertTrue(all(r.get('entry_model_slip') is None for r in old))
    def test_first_slope_22_and_full_have_distinct_next_open_availability(self):
        a,f,i,ee,_=self.case();rows=[r for r in latency('SYNTHETIC',a,f,ee) if r['pattern']==frozen.PATTERNS[0] and r['side']==1]
        by={r['stage']:r for r in rows}
        self.assertEqual(by['FIRST_SLOPE_OBSERVABLE']['delay_from_vertex_close_h'],1)
        self.assertEqual(by['AO22_CONFIRMED']['delay_from_vertex_close_h'],2)
        self.assertEqual(by['FULL_FROZEN_COINCIDENCE']['signal_available'],by['AO22_CONFIRMED']['signal_available'])
    def test_missing_coincidence_not_replaced_by_unrelated_future_event(self):
        a,f,i,ee,_=self.case();wrong=[dict(e,tokens={'ao':e['i']-1}) for e in ee]
        rows=latency('SYNTHETIC',a,f,wrong)
        self.assertTrue(all(r['status']=='NOT_CONFIRMED' for r in rows if r['stage']=='FULL_FROZEN_COINCIDENCE'))
    def test_future_horizons_censored_no_fabricated_remaining_move(self):
        a,f,i,ee,_=self.case();rows=latency('SYNTHETIC',a,f,ee)
        for r in rows:
            if r.get('entry_at'):
                self.assertFalse(r['common_endpoint_complete']);self.assertNotIn('remaining_mfe_fraction',r)
    def test_original_live_emission_not_invented_in_replay(self):
        a,f,i,ee,rr=self.case();rows=hourly('SYNTHETIC',a,f,ee,rr)
        self.assertTrue(all(r['actual_original_emitted_at'] is None for r in rows))
        self.assertTrue(all(r['capture_mode']=='HISTORICAL_DIAGNOSTIC_NOT_FORWARD' for r in rows))
    def test_all_first_slope_turns_include_failures_not_just_22_survivors(self):
        a,f,i,_,_=self.case();f['ao']=np.resize(np.array([1.,2,1,2.]),len(a))
        rows=[r for r in early_turns('SYNTHETIC',a,f) if r['series']=='AO']
        self.assertTrue(rows);self.assertTrue(all(r['later22_status']=='PRIOR_RUN_LT2' for r in rows))
        self.assertFalse(frozen.two_turn(f['ao'],1).any())
    def test_both_venues_closed_contiguous_and_separate(self):
        for venue in ('SPOT','USDM'):
            a,m=read_fixture(venue);self.assertEqual(len(a),m['rows'])
            self.assertLessEqual(a[-1,0]+frozen.HOUR,m['closed_cutoff_ms'])
        self.assertNotEqual(read_fixture('SPOT')[1]['venue'],read_fixture('USDM')[1]['venue'])


class CostAndIsolationTests(unittest.TestCase):
    def test_mde_sensitivity_does_not_change_primary_default(self):
        sigma=.02;primary=required_n(sigma)
        self.assertEqual(primary,required_n(sigma,.001))
        for effect in (.003,.005):self.assertLess(required_n(sigma,effect),primary)
    def test_funding_and_slippage_unchanged_between_fee_scenarios(self):
        a,f,i=fixture();fund=np.array([[a[i+5,0],.001,100.,8,99.,101.]])
        base=outcome(a,fund,i,1,1,fee=.001);vip=outcome(a,fund,i,1,1,fee=.0006)
        for key in ('entry','exit','funding_low_per_btc','funding_high_per_btc','missing_marks','boundary_settlements'):
            self.assertEqual(base[key],vip[key])
        self.assertAlmostEqual(vip['net_fraction']-base['net_fraction'],.0004*(base['entry']+base['exit'])/base['entry'])
    def test_frozen_detector_protocol_and_previous_files_unchanged(self):
        changes=subprocess.check_output(['git','diff',BASE,'--name-status'],cwd=ROOT,text=True).splitlines()
        for line in changes:
            status,path=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(path.startswith(PREFIX),line)
        for name in ('detect.py','protocol.json','inference.py','outcomes.py'):
            raw=subprocess.check_output(['git','show',BASE+':'+PREFIX.rsplit('/phase1b_diagnostics/',1)[0]+'/'+name],cwd=ROOT)
            self.assertEqual((HERE.parent/name).read_bytes(),raw)
    def test_new_modules_no_broker_network_or_runtime_imports(self):
        forbidden={'requests','socket','urllib','ccxt','guardian_bitunix','trade_guardian','live_auto','bitman_manual'}
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):continue
            for n in ast.walk(ast.parse(path.read_text('utf-8'))):
                if isinstance(n,(ast.Import,ast.ImportFrom)):
                    names=[v.name for v in n.names]+([n.module or ''] if isinstance(n,ast.ImportFrom) else [])
                    for name in names:self.assertFalse(forbidden.intersection(name.split('.')))
    def test_raw_public_responses_have_sha_receipts_and_no_authentication(self):
        for venue in ('SPOT','USDM'):
            for name in ('time','klines'):
                p=HERE/'fixtures'/(venue+'_'+name+'.json');m=json.loads(p.with_suffix('.receipt.json').read_text())
                self.assertEqual(m['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
                self.assertFalse(m['authentication']);self.assertEqual(m['method'],'GET');self.assertEqual(m['status'],200)


class ObservedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import csv,gzip,io
        def read(name):
            raw=(HERE/'artifacts'/name).read_bytes()
            if name.endswith('.gz'):raw=gzip.decompress(raw)
            return list(csv.DictReader(io.StringIO(raw.decode())))
        cls.read=staticmethod(read)
        cls.result=json.loads((HERE/'artifacts/results.json').read_text())
    def test_instrumented_actual_events_and_primary_counts_preserved(self):
        self.assertTrue(self.result['trace_events_identical']);self.assertTrue(self.result['published_counts_identical'])
        rows=[r for r in self.read('funnel.csv') if r['stage']=='EVALUATION']
        self.assertEqual(sum(int(r['ALL']) for r in rows),371)
        self.assertEqual(sum(int(r['Q75']) for r in rows),23)
        self.assertEqual(sum(int(r['Q90']) for r in rows),7)
        for r in rows:
            self.assertEqual(int(r['complete_stateful_before_cooldown'])-int(r['cooldown']),int(r['ALL']))
            self.assertGreaterEqual(int(r['ordered_drop_stateful_tokens']),0)
    def test_missing_prior_pece_slope_confirmed_both_actual_venues_0500(self):
        rows=json.loads((HERE/'artifacts/nov15_0500.json').read_text())
        self.assertEqual(len(rows),2)
        for r in rows:
            self.assertTrue(r['adx_22_down']);self.assertTrue(r['ao_22_up']);self.assertFalse(r['pece_22_up'])
            self.assertTrue(r['pece_cross_up']);self.assertEqual(r['p1_long_missing'],['pece'])
            self.assertLess(r['pece_delta_lag2'],0);self.assertGreater(r['pece_delta_lag3'],0)
            self.assertEqual(r['confirmed_events'],[])
            self.assertIsNone(r['actual_original_emitted_at'])
    def test_development_pairs_reproduce_sigma_and_all_three_mdes(self):
        rows=self.read('dev_variance.csv');power=self.read('power_MDE.csv')
        self.assertEqual(len(power),18)
        for cell in power:
            values=[float(r['paired_excess']) for r in rows if r['pattern']==cell['pattern'] and r['side']==cell['side']]
            self.assertAlmostEqual(float(np.std(values,ddof=1)),float(cell['sigma_sample_ddof1']),places=13)
            self.assertEqual(required_n(float(cell['sigma_sample_ddof1']),float(cell['MDE_pp'])/100),int(cell['required_effective_n']))
    def test_cost_scenarios_have_identical_cohort_funding_and_slip(self):
        rows=self.read('cost_rows.csv.gz');groups={}
        for r in rows:
            key=tuple(r[k] for k in ('stage','pattern','side','stratum','horizon','event_id'))
            groups.setdefault(key,{})[r['scenario']]=r
        for pair in groups.values():
            a=pair['CONSERVATIVE'];b=pair['BITUNIX_VIP0_TAKER_ASSUMPTION']
            for k in ('entry','exit','slip_per_side','funding_low_per_btc','funding_high_per_btc','missing_marks','boundary_settlements'):
                self.assertEqual(a[k],b[k])
            self.assertGreater(float(b['net_conservative_funding']),float(a['net_conservative_funding']))
    def test_delay_never_invents_full_event_or_censored_future(self):
        rows=self.read('delay.csv')
        for r in rows:
            if r['stage']=='EXTREME_HINDSIGHT':self.assertEqual(r['causal'],'False');self.assertEqual(r.get('entry_model_slip',''),'')
            if r['status']=='NOT_CONFIRMED':self.assertEqual(r['entry_at'],'')
            if r.get('common_endpoint_complete')=='False':self.assertEqual(r.get('remaining_mfe_fraction',''),'')
    def test_all_simple_turn_failures_retained_and_daily_coverage_not_extended(self):
        early=self.read('early_turns.csv');hours=self.read('november.csv')
        self.assertTrue(any(r['later22_status']=='PRIOR_RUN_LT2' for r in early))
        self.assertTrue(any(r['later22_status']=='NEXT_SLOPE_FAILED' for r in early))
        self.assertEqual(len(hours),190)
        self.assertEqual(max(r['earliest_available_utc'] for r in hours),'2026-11-15T22:00:00Z')
    def test_no_new_strategy_or_2019_data_or_inference_classification(self):
        self.assertEqual(self.result['new_strategy_variants'],0)
        self.assertEqual(self.result['original_conclusion'],'NO TESTABLE')
        self.assertFalse(self.result['new_history_since2019']);self.assertFalse(self.result['phase2_management'])
    def test_separate_completion_has_all_96_requested_hours_per_venue(self):
        rows=self.read('november_full.csv');m=json.loads((HERE/'artifacts/completion.json').read_text())
        self.assertEqual(len(rows),192);self.assertTrue(m['old_events_preserved']);self.assertTrue(m['earlier_capture_preserved'])
        for venue in ('SPOT','USDM'):
            dates=[r['bar_open_utc'] for r in rows if r['venue']==venue]
            self.assertEqual(len(dates),96);self.assertEqual(len(set(dates)),96)
        self.assertEqual(max(r['earliest_available_utc'] for r in rows),'2026-11-15T23:00:00Z')
    def test_completion_does_not_rewrite_initial_indicators_or_claim_live_emission(self):
        original={(r['venue'],r['bar_open_utc']):r for r in self.read('november.csv')}
        for row in self.read('november_full.csv'):
            prior=original.get((row['venue'],row['bar_open_utc']))
            if prior:
                for key in ('adx','ao','pececillos','confirmed_events','earliest_available_utc'):
                    self.assertEqual(row[key],prior[key])
            self.assertEqual(row['actual_original_emitted_at'],'')
    def test_last_hour_has_new_real_receipts_and_old_fixture_hash_preserved(self):
        for venue in ('SPOT','USDM'):
            m=json.loads((HERE/'fixtures'/(venue+'_FULL.json')).read_text())
            raw=(HERE/'fixtures'/(venue+'_FULL.csv.gz')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),m['sha256'])
            original=(HERE/'fixtures'/(venue+'_H1.csv.gz')).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(),m['previous_fixture_sha256'])
            self.assertTrue(m['actual_received_at'].startswith('2026-11-16'))


if __name__=='__main__':unittest.main()
