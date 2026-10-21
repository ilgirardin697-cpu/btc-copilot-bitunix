"""Offline fixtures, causal parity and production isolation for entry research V0."""
import ast
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from bitman_manual.frozen import indicators
from research.bitman_entry_lab import data,features,simulation,statistics,study

ROOT=Path(__file__).resolve().parent
BASE='fc211d8e36c6db55185efa8309eb8f980beab2ea'

def fixture(n=75*288):
    t=np.arange(n)*data.M5+data.START
    c=100+np.arange(n)*.0005+2*np.sin(np.arange(n)/39)+np.cos(np.arange(n)/111)
    o=np.r_[c[0],c[:-1]];h=np.maximum(o,c)+.3;l=np.minimum(o,c)-.3
    return np.column_stack((t,o,h,l,c,np.ones(n)*10,np.ones(n)*4))

def trade_fixture():
    start=int(datetime(2024,1,10,tzinfo=timezone.utc).timestamp()*1000)
    base=np.asarray([[start+i*data.M5,100,100.1,99.9,100,10,4] for i in range(24*12)],float)
    bars=np.asarray([[start-data.HOUR,100,101,99,100,10,4]],float)
    d=dict(bars=bars,features=dict(atr=np.array([1.]),low6=np.array([99.]),high6=np.array([101.])),
        interval=data.HOUR,available_at=np.array([start]))
    funding=np.asarray([[t,0.] for t in np.arange(start,start+24*data.HOUR,8*data.HOUR)])
    return base,funding,d

class EntryFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=fixture();cls.d=features.prepare(cls.base)

    def test_ao_independent_formula(self):
        b=self.d['bars'];m=(b[:,2]+b[:,3])/2;expected=np.full(len(b),np.nan)
        for i in range(33,len(b)):expected[i]=np.mean(m[i-4:i+1])-np.mean(m[i-33:i+1])
        np.testing.assert_allclose(self.d['features']['ao'],expected,equal_nan=True,atol=1e-12)

    def test_frozen_indicator_exact_parity(self):
        ref=indicators.calculate(self.d['bars'])
        for k in ('ao','ao_slope','atr','adx','adx_slope','di_plus','di_minus','bbwp','bbwp_slope'):
            np.testing.assert_array_equal(self.d['features'][k],ref[k])

    def test_atr_wilder_seed_and_recurrence(self):
        b=self.d['bars'];tr=np.r_[b[0,2]-b[0,3],np.maximum(b[1:,2]-b[1:,3],np.maximum(abs(b[1:,2]-b[:-1,4]),abs(b[1:,3]-b[:-1,4])))]
        atr=self.d['features']['atr']
        self.assertAlmostEqual(atr[13],np.mean(tr[:14]))
        self.assertAlmostEqual(atr[14],(atr[13]*13+tr[14])/14)

    def test_fe_public_formula_independent(self):
        b=self.d['bars'];actual=features.fe13(b)
        for i in (13,50,100):
            terms=[max(b[j,2],b[j-1,4])-min(b[j,3],b[j-1,4]) for j in range(i-12,i+1)]
            expected=np.log(sum(terms)/(b[i-12:i+1,2].max()-b[i-12:i+1,3].min()))/np.log(13)
            self.assertAlmostEqual(actual[i],expected,places=12)

    def test_fe_zero_range_unavailable(self):
        x=np.asarray([[i*data.M5,100,100,100,100,0,0] for i in range(30)],float)
        self.assertTrue(np.all(np.isnan(features.fe13(x))))

    def test_prefix_invariance_and_future_perturbation(self):
        prefix=self.base[:60*288];p=features.prepare(prefix)
        for k,v in p['features'].items():
            np.testing.assert_allclose(v,self.d['features'][k][:len(v)],equal_nan=True,atol=1e-12)
        changed=self.base.copy();changed[len(prefix):,1:5]*=1.5
        future=features.prepare(changed)
        np.testing.assert_array_equal(future['features']['ao'][:len(p['bars'])],p['features']['ao'])
        for family in ('A','B','C'):
            np.testing.assert_array_equal(features.raw_events(p,family),features.raw_events(self.d,family)[:len(p['bars'])])

    def test_context_only_closed_higher_timeframes(self):
        f=self.d['features'];t=self.d['available_at']
        for label,width in (('h4',4*data.HOUR),('d1',24*data.HOUR)):
            finite=np.isfinite(f[label+'_ao'])
            self.assertTrue(np.all(f[label+'_available_at'][finite]<=t[finite]))
            self.assertTrue(np.all(t[finite]-f[label+'_available_at'][finite]<width))

    def test_partial_aggregate_and_gap_not_filled(self):
        self.assertEqual(len(features.aggregate(self.base[:11],data.HOUR)),0)
        missing=np.delete(self.base,100,axis=0)
        aggregated=features.aggregate(missing,data.HOUR)
        self.assertNotIn(int(self.base[100,0]//data.HOUR*data.HOUR),aggregated[:,0])

    def test_indicator_resets_after_gap(self):
        b=self.d['bars'];x=np.delete(b,400,axis=0);f=features.calculate(x,data.HOUR)
        self.assertTrue(np.all(np.isnan(f['ao'][400:433])))

    def test_structural_pivots_not_future_available(self):
        f=self.d['features'];t=self.d['available_at']
        for name in ('support','resistance'):
            x=f['pivot_'+name+'_known'];ok=np.isfinite(x)
            self.assertTrue(np.all(x[ok]<=t[ok]))

    def test_anchors_nonoverlap_and_nested_gates(self):
        for family in ('A','B','C'):
            events,_=study.anchors(self.d,family)
            times=[self.d['available_at'][i] for i,s in events]
            self.assertTrue(np.all(np.diff(times)>=48*data.HOUR))
            for i,s in events:
                g=features.gates(self.d,i,s,family)
                if g['AO_DMI_FE']:self.assertTrue(g['AO_DMI'] and g['AO_FE'])

    def test_controls_deterministic_date_side_regime_and_nonoverlap(self):
        events,_=study.anchors(self.d,'B')
        c=study.controls(self.d,events,123);self.assertEqual(c,study.controls(self.d,events,123))
        dates=[];f=self.d['features'];times=self.d['available_at']
        for i,(j,s) in c.items():
            self.assertEqual(study.month(times[i]),study.month(times[j]))
            self.assertEqual(f['regime'][i],f['regime'][j])
            self.assertEqual(dict(events)[i],s);dates.append(times[j])
        self.assertTrue(np.all(np.diff(sorted(dates))>=48*data.HOUR))

    def test_temporal_embargo(self):
        d=dict(self.d);d['available_at']=self.d['available_at'].copy()
        i=1500;d['available_at'][i]=int(datetime(2024,1,2,tzinfo=timezone.utc).timestamp()*1000)
        self.assertFalse(study.eligible(d,i))
        d['available_at'][i]=int(datetime(2024,12,31,tzinfo=timezone.utc).timestamp()*1000)
        self.assertFalse(study.eligible(d,i))

    def test_symmetric_signal_families(self):
        n=10;ao=np.array([5.,4.,3.,2.,1.,2.,3.,4.,5.,6.])
        b=np.column_stack((np.arange(n)*data.HOUR,np.ones((n,6))*100))
        f=dict(ao=ao,ao_slope=ao-indicators.lag(ao),high6=np.ones(n)*99,low6=np.ones(n)*101)
        d=dict(bars=b,features=f,interval=data.HOUR)
        for family in ('A','B','C'):
            a=features.raw_events(d,family)
            inverse=dict(d,features=dict(f,ao=-ao,ao_slope=-f['ao_slope']))
            np.testing.assert_array_equal(a,-features.raw_events(inverse,family))

class EntryFillTests(unittest.TestCase):
    def run_trade(self,side=1,mutate=None):
        base,funding,d=trade_fixture()
        if mutate:mutate(base,funding,d)
        return simulation.simulate(base,funding,d,0,side,'ATR_2R')

    def test_entry_at_next_open_not_signal_close(self):
        r,e=self.run_trade()
        self.assertIsNone(e);self.assertEqual(r['entry_time'],r['signal_time'])
        self.assertEqual(r['entry'],100);self.assertEqual(r['reason'],'TIME')

    def test_stop_first_ambiguous_long(self):
        def change(b,f,d):b[0,2]=104;b[0,3]=98
        r,e=self.run_trade(mutate=change)
        self.assertEqual(r['gross_R'],-1);self.assertTrue(r['ambiguous_bar']);self.assertEqual(r['mfe_R'],0)

    def test_stop_first_ambiguous_short(self):
        def change(b,f,d):b[0,2]=102;b[0,3]=96
        r,e=self.run_trade(-1,change)
        self.assertEqual(r['gross_R'],-1);self.assertTrue(r['ambiguous_bar'])

    def test_gap_stop_adverse_open(self):
        def change(b,f,d):b[1,1:5]=[97,100,96,99]
        r,e=self.run_trade(mutate=change)
        self.assertEqual(r['exit_price'],97);self.assertLess(r['gross_R'],-1)

    def test_target_is_fixed_no_gap_price_improvement(self):
        def change(b,f,d):b[0,2]=105
        r,e=self.run_trade(mutate=change)
        self.assertEqual(r['gross_R'],2);self.assertEqual(r['exit_price'],103)

    def test_missing_path_fails_closed(self):
        b,f,d=trade_fixture()
        r,e=simulation.simulate(b[:-1],f,d,0,1,'ATR_2R')
        self.assertIsNone(r);self.assertEqual(e,'INCOMPLETE_PATH')

    def test_target_exit_mae_retains_adverse_candle_bound(self):
        def change(b,f,d):b[0,2]=104;b[0,3]=99
        r,e=self.run_trade(mutate=change)
        self.assertEqual(r['gross_R'],2)
        self.assertAlmostEqual(r['mae_R'],-1/1.5)

    def test_internal_gap_fails_closed(self):
        b,f,d=trade_fixture()
        r,e=simulation.simulate(np.delete(b,100,axis=0),f,d,0,1,'ATR_2R')
        self.assertIsNone(r);self.assertEqual(e,'INCOMPLETE_PATH')

    def test_missing_funding_not_assumed_zero(self):
        b,f,d=trade_fixture()
        r,e=simulation.simulate(b,f[1:],d,0,1,'ATR_2R')
        self.assertIsNone(r);self.assertEqual(e,'FUNDING_COVERAGE')

    def test_actual_funding_rate_sign_and_price_estimate(self):
        def change(b,f,d):f[1,1]=.001
        lo,e=self.run_trade(1,change);sh,e=self.run_trade(-1,change)
        self.assertGreater(lo['funding_R'],0);self.assertLess(sh['funding_R'],0)

    def test_ambiguous_entry_funding_no_credit(self):
        def change(b,f,d):f[0,1]=.001
        sh,e=self.run_trade(-1,change)
        self.assertEqual(sh['funding_R'],0)

    def test_costs_monotone_and_zero_edge_gross_loses_net(self):
        r,e=self.run_trade();c=r['costs']
        self.assertEqual(r['gross_R'],0)
        self.assertLess(c['STRESS']['net_R'],c['CONSERVATIVE']['net_R'])
        self.assertLess(c['CONSERVATIVE']['net_R'],c['BASE']['net_R'])
        self.assertLess(c['BASE']['net_R'],0)

    def test_invalid_structural_stop_rejected(self):
        self.assertIsNone(simulation.exit_levels(100,1,1,50,150,'STRUCTURE_2R'))
        self.assertIsNone(simulation.exit_levels(100,-1,1,50,150,'STRUCTURE_2R'))

    def test_outcome_deterministic(self):
        self.assertEqual(self.run_trade(),self.run_trade())

class EntryIntegrityTests(unittest.TestCase):
    def test_block_bootstrap_determinism_and_small_n_unknown(self):
        self.assertEqual(statistics.interval([1,2,3],[0,40*86400000,80*86400000]),
            statistics.interval([1,2,3],[0,40*86400000,80*86400000]))
        self.assertEqual(statistics.interval([1],[0]),([None,None],None))

    def test_empty_and_negative_candidate_classification(self):
        self.assertEqual(statistics.classify(dict(n=0),{}, {}, {}, {}, {}),'INCONCLUSIVE')
        self.assertEqual(statistics.classify(dict(n=100,mean_R=-.1),dict(mean_R=-.2),{},
            dict(mean_delta_R=0),{},{}),'NO EDGE')

    def test_market_values_and_duplicates_rejected(self):
        b=fixture(50);b[1]=b[0]
        with self.assertRaises(ValueError):data.validate_bars(b)
        b=fixture(50);b[1,6]=b[1,5]+1
        with self.assertRaises(ValueError):data.validate_bars(b)

    def test_no_arbitrary_download_host_or_venue(self):
        for month in data.MONTHS:
            for kind in ('bars','funding'):
                self.assertTrue(data.url(kind,month).startswith('https://data.binance.vision/data/futures/um/monthly/'))
                self.assertIn('BTCUSDT',data.url(kind,month))
        with self.assertRaises(ValueError):data.url('orders','2020-01')

    def test_no_runtime_consumer_or_execution_dependency(self):
        paths=subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT).decode().splitlines()
        for name in paths:
            if name.startswith('research/') or name.startswith('test') or name.startswith('tests/'):continue
            self.assertNotIn('bitman_entry_lab',(ROOT/name).read_text('utf-8'),name)
        for p in (ROOT/'research/bitman_entry_lab').glob('*.py'):
            tree=ast.parse(p.read_text('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    module=node.module or ''
                    self.assertFalse(any(x in module for x in ('guardian_bitunix','guardian_risk','trade_guardian','readiness','v8_executor','telegram')),p.name)
                if isinstance(node,ast.Attribute):
                    self.assertNotIn(node.attr,('place_order','cancel_order','create_order','set_leverage','send_message','post','put','patch','delete'))

    def test_all_tracked_production_sources_unchanged(self):
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT).decode().splitlines()
        for name in paths:
            if name.startswith('research/') or name.startswith('.github/') or name.startswith('test') or name.startswith('tests/'):continue
            original=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
            self.assertEqual((ROOT/name).read_bytes().replace(b'\r\n',b'\n'),original.replace(b'\r\n',b'\n'),name)

    def test_weekly_protocol_unchanged(self):
        from bitman_weekly_forward import protocol
        protocol.verify()
        self.assertEqual(protocol.EXPECTED_HASH,'d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8')

    def test_locked_analysis_and_specification(self):
        p=ROOT/'research/bitman_entry_lab/artifacts/protocol_lock.json'
        if not p.exists():self.skipTest('Protocol lock created only after fixture tests pass')
        lock=json.loads(p.read_text('utf-8'))
        self.assertEqual(study.hashes(),lock['code'])
        self.assertEqual(data.sha((p.parent/'data_manifest.json').read_bytes()),lock['manifest_sha256'])

    def test_result_archive_no_credentials_or_private_data(self):
        p=ROOT/'research/bitman_entry_lab/artifacts/simulated_trades.jsonl.gz'
        if not p.exists():self.skipTest('Results not calculated during protocol fixture phase')
        rows=[json.loads(line) for line in gzip.decompress(p.read_bytes()).splitlines()]
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r['entry_time'],r['signal_time'])
            self.assertLessEqual(r['context']['h4_available_at'],r['signal_time'])
            self.assertLessEqual(r['context']['d1_available_at'],r['signal_time'])
            self.assertEqual(r['context']['mlrsi'],'UNAVAILABLE')

    def test_financial_replay_identity_and_control_artifact(self):
        p=ROOT/'research/bitman_entry_lab/artifacts'
        if not (p/'audit.json').exists():self.skipTest('Independent audit is produced after the fixed evaluation')
        from research.bitman_entry_lab.audit import financial_hash
        audit=json.loads((p/'audit.json').read_text('utf-8'))
        rows=[json.loads(x) for x in gzip.decompress((p/'simulated_trades.jsonl.gz').read_bytes()).splitlines()]
        self.assertTrue(audit['financial_replay_identical'])
        self.assertEqual(financial_hash(rows),audit['financial_replay_hash'])
        self.assertTrue((p/'matched_controls.csv').is_file())

if __name__=='__main__':unittest.main()

