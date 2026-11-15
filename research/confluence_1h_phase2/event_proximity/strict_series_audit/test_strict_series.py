"""Exact substitution, strict gates, source preservation and actual run evidence."""
import ast
import csv
import gzip
import hashlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import unittest
from collections import Counter
from unittest.mock import patch

try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Confluence research CI installs NumPy') from error

from research.confluence_1h import engine, indicators
from research.confluence_1h.data import HOUR, stamp
from .variants import flags
from .evaluate import HERE, exact_net, windows

ROOT=HERE.parents[3]
PARENT='384032d7917e354552c5842a74d3f3f72918ac34'
PREFIX='research/confluence_1h_phase2/event_proximity/strict_series_audit/'


def features(side=1):
    f=dict(kon_trend=np.full(6,8.),kon_signal=np.zeros(6),minnows=np.array([-5,-4,-3,-2,1,2.]),
        adx=np.array([10,20,45,42,90,90.]),ao=np.array([-5,-4,-3,-2,-1,0.]),bbwp=np.full(6,90.),atr=np.ones(6))
    if side==-1:
        for k in ('kon_trend','minnows','ao'):f[k]=-f[k]
    return f


class NumericalTests(unittest.TestCase):
    def test_base_is_original_flags_bit_for_bit(self):
        f=features()
        expected=indicators.signals(f);actual=flags(f,'BASE')
        for k in expected:np.testing.assert_array_equal(actual[k],expected[k])

    def test_pececillos_changes_one_input_without_mutating_any_original_array(self):
        f=features();before={k:v.copy() for k,v in f.items()}
        with patch('research.confluence_1h_phase2.event_proximity.strict_series_audit.variants.signals',wraps=indicators.signals) as s:
            result=flags(f,'PECECILLOS');view=s.call_args.args[0]
        self.assertIs(view['kon_trend'],f['minnows']);self.assertIs(view['kon_signal'],f['kon_signal'])
        for k in f:
            np.testing.assert_array_equal(f[k],before[k])
            if k!='kon_trend':self.assertIs(view[k],f[k])
        self.assertTrue(result['long'][4]);self.assertFalse(flags(f,'BASE')['long'][4])

    def test_long_short_symmetry_with_original_prior_sign(self):
        for side,key in ((1,'long'),(-1,'short')):
            f=features(side);self.assertTrue(flags(f,'PECECILLOS')[key][4])
            self.assertFalse(flags(f,'BASE')[key][4])

    def test_previous_sign_is_pececillos_not_brown(self):
        f=features();f['kon_trend'][:]=-8;f['kon_signal'][:]=10
        f['minnows'][:]=[1,2,3,4,11,12]
        self.assertFalse(flags(f,'PECECILLOS')['long'].any())

    def test_adx_threshold40_is_strict_and_lagged_not_current_turn(self):
        f=features();self.assertTrue(flags(f,'PECECILLOS')['long'][4])
        self.assertGreater(f['adx'][4],f['adx'][3])  # current rise is allowed by ORIGINAL rule
        f['adx'][2]=40;self.assertFalse(flags(f,'PECECILLOS')['long'][4])

    def test_bbwp85_strict_and_no_parameter_arguments(self):
        f=features();f['bbwp'][4]=85
        self.assertFalse(flags(f,'PECECILLOS')['long'][4])
        self.assertEqual(list(inspect.signature(flags).parameters),['features','variant'])

    def test_ao_needs_two_strict_slopes_and_original_zero_side(self):
        for ao in (np.array([-5,-4,-3,-2,-2,0.]),np.array([-5,-4,-3,-2,0,1.])):
            f=features();f['ao']=ao
            self.assertFalse(flags(f,'PECECILLOS')['long'][4])

    def test_no_additional_variants(self):
        with self.assertRaises(ValueError):flags(features(),'ADX_FROM_MINIMUM')

    def test_prefix_invariance(self):
        rng=np.random.default_rng(431);c=40000*np.exp(np.cumsum(rng.normal(0,.002,600)))
        o=np.r_[c[0],c[:-1]];a=np.c_[stamp('2025-01-01T00:00:00Z')+np.arange(600)*HOUR,o,np.maximum(o,c)+30,np.minimum(o,c)-30,c,rng.uniform(100,200,600)]
        for variant in ('BASE','PECECILLOS'):
            full=flags(indicators.calculate(a),variant);prefix=flags(indicators.calculate(a[:400]),variant)
            for k in full:np.testing.assert_array_equal(full[k][:400],prefix[k])

    def test_original_simulation_costs_and_entry_time_unchanged(self):
        n=65;t=stamp('2025-01-01T00:00:00Z')+np.arange(n)*HOUR
        a=np.c_[t,np.full(n,100.),np.full(n,101.),np.full(n,99.),np.full(n,100.),np.ones(n)]
        f={k:np.resize(v,n) for k,v in features().items()};f['atr'][:]=10
        l=np.zeros(n,bool);l[1]=True
        deals,_,_=engine.simulate(a,f['atr'],l,np.zeros(n,bool),np.empty((0,6)))
        self.assertEqual(deals[0]['entry_i'],2);self.assertAlmostEqual(deals[0]['entry'],100.05)
        p=engine.Assumptions()
        self.assertEqual((p.fee,p.slippage,p.atr_multiple,p.hold_bars,p.risk,p.initial),(.001,.0005,1.5,24,.01,200))

    def test_exact_net_never_claimed_for_missing_marks_or_no_trades(self):
        m=dict(n=7,net_usdt=4.,funding_missing_marks_used=1,funding_timing_ambiguities=0)
        self.assertIsNone(exact_net(m));m['funding_missing_marks_used']=0
        self.assertEqual(exact_net(m),4.)
        m['funding_timing_ambiguities']=1;self.assertIsNone(exact_net(m))
        m.update(n=0,funding_timing_ambiguities=0);self.assertIsNone(exact_net(m))

    def test_original_windows_and_embargo(self):
        w=windows(1464,36528);cut=1464+int(.70*35064)
        self.assertEqual(w['DEVELOPMENT'],(1464,cut-24));self.assertEqual(w['TEST'],(cut+24,36528))
        self.assertEqual(len([k for k in w if k.startswith('WF')]),4)

    def test_original_random_control_draws_match_month_side_and_regime(self):
        from research.confluence_1h.statistics import random_controls
        from research.confluence_1h.data import iso
        n=160;t=stamp('2025-01-30T00:00:00Z')+np.arange(n)*HOUR
        a=np.c_[t,np.full(n,100.),np.full(n,101.),np.full(n,99.),np.full(n,100.),np.ones(n)]
        regime=np.where(np.arange(n)%2,1.,-1.)
        l=np.zeros(n,bool);s=l.copy();l[[10,50]]=True;s[80]=True
        def strata(long,short):
            return Counter((iso(t[i])[:7],side,int(regime[i])) for side,mask in [(1,long),(-1,short)] for i in np.flatnonzero(mask))
        expected=strata(l,s);observed=[]
        def capture(bars,atr,long,short,*args,**kwargs):
            observed.append(strata(long,short))
            return engine.simulate(bars,atr,long,short,*args,**kwargs)
        with patch('research.confluence_1h.statistics.simulate',side_effect=capture):
            controls,_=random_controls(a,{'atr':np.ones(n)},{'long':l,'short':s},regime,np.empty((0,6)),0,n,0,engine.Assumptions(),trials=3)
        self.assertEqual(observed,[expected]*3);self.assertEqual([c['candidates'] for c in controls],[3]*3)


class ObservedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results=json.loads((HERE/'artifacts/results.json').read_text())
    def test_same_four_year_dataset_and_exact_base_reproduction(self):
        r=self.results
        self.assertEqual((r['evaluation_bars'],r['warmup_bars'],r['raw_inputs_checked']),(35064,1464,153))
        self.assertEqual(r['signals']['BASE'],dict(long=0,short=0))
        self.assertTrue(r['base_matches_pr46_zero_signals'])
        self.assertEqual(r['original_data_sha256'],'5b2544c9bf353cedb77a07781ffe9e6202b12513c0c10f3d25bca67756a4825a')

    def test_seven_unique_signals_not_fourteen_independent_operations(self):
        self.assertEqual(self.results['signals']['PECECILLOS'],dict(long=3,short=4))
        rows=list(csv.DictReader((HERE/'artifacts/trades_all.csv').read_text().splitlines()))
        primary=[r for r in rows if r['variant']=='PECECILLOS' and r['window']=='FULL' and r['book']=='COMBINED']
        self.assertEqual(len(primary),14)
        self.assertEqual(len({r['available_at'] for r in primary}),7)
        for target in ('2.0','3.0'):self.assertEqual(sum(r['target_r']==target for r in primary),7)

    def test_all_70128_variant_hours_retained_and_only_series_gates_change(self):
        raw=gzip.decompress((HERE/'artifacts/signals_all.csv.gz').read_bytes()).decode()
        rows=list(csv.DictReader(io.StringIO(raw)))
        self.assertEqual(len(rows),2*35064)
        base=rows[:35064];pece=rows[35064:]
        for b,p in zip(base,pece):
            for k in ('open_time','available_at','red_ema_tendencia','adx','ao','bbwp','atr','adx_lagged_decline','ao_long','ao_short','bbwp_above'):
                self.assertEqual(b[k],p[k])

    def test_all_actual_signal_decisions_and_original_purge_kept(self):
        rows=list(csv.DictReader((HERE/'artifacts/signal_dispositions.csv').read_text().splitlines()))
        for target in ('2.0','3.0'):
            r=[x for x in rows if x['variant']=='PECECILLOS' and x['target_r']==target and x['book']=='COMBINED' and x['window']=='FULL']
            self.assertEqual(len(r),7);self.assertTrue(all(x['status']=='SIMULATED' for x in r))

    def test_november_signal_in_both_venues_but_not_outside_sample_evidence(self):
        rows=json.loads((HERE/'artifacts/november_incident.json').read_text())
        for row in rows:
            self.assertFalse(row['performance_scored']);self.assertFalse(row['held_out_validation'])
            self.assertEqual(row['long'],row['variant']=='PECECILLOS')
            self.assertFalse(row['short'])
            if row['long']:
                self.assertEqual(row['first_next_open_time'],'2026-11-15T04:00:00Z')
                self.assertEqual(row['available_madrid'],'2026-11-15T05:00:00+01:00')
                self.assertGreater(row['model_entry_with_original_slip'],row['next_open_reference'])

    def test_matched_controls_have_200_trials_and_small_test_sample_not_promoted(self):
        r=self.results
        for m in r['full_combined']:
            self.assertEqual(m['control_trials'],200)
            self.assertEqual(m['classification'],'INCONCLUSO')
        for m in r['test_results']:
            self.assertEqual(m['classification'],'INCONCLUSO')
            if m['variant']=='PECECILLOS' and m['book']=='COMBINED':self.assertEqual(m['n'],1)

    def test_conservative_optimistic_funding_results_kept_separate(self):
        primary=[r for r in self.results['full_combined'] if r['variant']=='PECECILLOS']
        bounds=list(csv.DictReader((HERE/'artifacts/funding_bounds.csv').read_text().splitlines()))
        for row in primary:
            self.assertIsNone(row['exact_net_usdt']);self.assertEqual(row['funding_missing_marks_used'],3)
            alternate=next(x for x in bounds if x['variant']=='PECECILLOS' and x['book']=='COMBINED' and float(x['target_r'])==row['target_r'])
            self.assertGreaterEqual(float(alternate['net_usdt']),row['net_usdt'])


class IsolationTests(unittest.TestCase):
    def test_frozen_protocol_and_single_substitution_source(self):
        for filename,ref in [('protocol.json','e626d46d278f115947a5ae69a2e8b6999401a272'),('variants.py','55b904af8950f8651b7eb8ee9700b1ca6e86c740')]:
            raw=subprocess.check_output(['git','show',ref+':'+PREFIX+filename],cwd=ROOT)
            self.assertEqual((HERE/filename).read_bytes(),raw)

    def test_all_prior_prs_and_runtime_sources_unchanged(self):
        rows=subprocess.check_output(['git','diff',PARENT,'--name-status'],cwd=ROOT,text=True).splitlines()
        for line in rows:
            status,path=line.split('\t',1);self.assertEqual(status,'A',line)
            self.assertTrue(path.startswith(PREFIX),line)

    def test_no_network_or_trading_dependency_and_no_proximity_detector_used(self):
        forbidden={'requests','urllib','socket','ccxt','guardian_bitunix','trade_guardian','bitman_manual','detector'}
        for p in HERE.glob('*.py'):
            if p.name.startswith('test_'):continue
            for n in ast.walk(ast.parse(p.read_text())):
                if isinstance(n,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in n.names]+([n.module or ''] if isinstance(n,ast.ImportFrom) else [])
                    for name in names:self.assertFalse(forbidden.intersection(name.split('.')),str(p))

    def test_original_engine_is_imported_not_forked(self):
        import research.confluence_1h_phase2.event_proximity.strict_series_audit.evaluate as evaluation
        self.assertIs(evaluation.simulate,engine.simulate)
        self.assertIs(evaluation.metrics,engine.metrics)


if __name__=='__main__':
    unittest.main()
