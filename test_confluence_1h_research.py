"""Offline synthetic unit fixtures; never evidence of profitability or Pine execution."""
import ast
import gzip
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('NumPy required by dedicated research CI') from error

from research.confluence_1h import indicators as ind
from research.confluence_1h.data import HOUR,decode_klines,stamp
from research.confluence_1h.engine import Assumptions,simulate,metrics
from research.confluence_1h.reference import calculate_scalar
from research.confluence_1h.statistics import block_indices,ratio_ci,daily
from research.confluence_1h.compare_pine import compare

ROOT=Path(__file__).resolve().parent;LAB=ROOT/'research/confluence_1h'


def bars(n=1000):
    rng=np.random.default_rng(551);c=30000*np.exp(np.cumsum(rng.normal(0,.004,n)))
    o=np.r_[c[0],c[:-1]];h=np.maximum(o,c)+rng.uniform(5,90,n);l=np.minimum(o,c)-rng.uniform(5,90,n)
    return np.c_[np.arange(n)*HOUR+stamp('2025-01-01T00:00:00Z'),o,h,l,c,rng.uniform(10,1000,n)]


class IndicatorTests(unittest.TestCase):
    def test_independent_scalar_reference_all_public_math(self):
        a=bars(700);f=ind.calculate(a);r=calculate_scalar(a)
        for key,value in r.items():
            with self.subTest(key=key):np.testing.assert_allclose(f[key],value,rtol=1e-9,atol=1e-8,equal_nan=True)

    def test_ao_linear_known_value(self):
        a=bars(80);a[:,2]=np.arange(80)+100;a[:,3]=a[:,2]-2
        np.testing.assert_allclose(ind.calculate(a)['ao'][33:],14.5,atol=1e-12)

    def test_atr_and_dmi_have_different_first_tr_seeds(self):
        f=ind.calculate(bars(80))
        self.assertEqual(np.flatnonzero(np.isfinite(f['atr']))[0],13)
        self.assertEqual(np.flatnonzero(np.isfinite(f['plus_di']))[0],14)
        self.assertEqual(np.flatnonzero(np.isfinite(f['adx']))[0],27)

    def test_bbwp_rightmost_is_index_not_inclusive_count(self):
        self.assertEqual(ind.pine_rightmost([4,5,5,5],5),3)
        self.assertEqual(ind.pine_rightmost([-2,0,1,5,9],3),3)
        self.assertEqual(ind.pine_rightmost([],3),0)
        w=np.r_[np.full(7,np.nan),np.zeros(150)]
        self.assertEqual(ind.bbwp(w)[-1],99.)
        self.assertEqual(ind.bbwp(w,literal=False)[-1],100.)

    def test_prefix_invariance_all_features_and_signals(self):
        a=bars(500);full=ind.calculate(a);prefix=ind.calculate(a[:300])
        for key in full:np.testing.assert_array_equal(full[key][:300],prefix[key])
        fs=ind.signals(full);ps=ind.signals(prefix)
        for key in fs:np.testing.assert_array_equal(fs[key][:300],ps[key])

    def test_signal_exact_lagged_adx_rule_not_current_turn(self):
        f=dict(kon_trend=np.array([-4,-3,-2,-2,1,1.]),kon_signal=np.zeros(6),
            adx=np.array([10,20,45,42,90,90.]),ao=np.array([-5,-4,-3,-2,-1,0.]),bbwp=np.full(6,90),atr=np.ones(6))
        self.assertTrue(ind.signals(f)['long'][4])  # current ADX rises: still satisfies original rule
        f['kon_trend']=-f['kon_trend'];f['ao']=-f['ao']
        self.assertTrue(ind.signals(f)['short'][4])

    def test_no_simultaneous_long_short_and_no_warmup_signals(self):
        s=ind.signals(ind.calculate(bars()))
        self.assertFalse((s['long']&s['short']).any());self.assertFalse(s['long'][:34].any())

    def test_closed_4h_regime_never_uses_current_4h(self):
        a=bars(1000);r=ind.regime(a);b=a.copy();b[901:,4]*=2
        np.testing.assert_array_equal(r[:901],ind.regime(b)[:901])
        self.assertTrue(np.isnan(r[:799]).all())


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.a=bars(65);self.a[:,1:5]=[100,101,99,100];self.atr=np.full(65,10.)
        self.l=np.zeros(65,bool);self.s=np.zeros(65,bool);self.l[1]=True
    def run_case(self,**kwargs):return simulate(self.a,self.atr,self.l,self.s,np.empty((0,6)),**kwargs)

    def test_next_open_fill_and_signal_available_timestamp(self):
        t,e,_=self.run_case();self.assertEqual(t[0]['entry_i'],2)
        self.assertEqual(t[0]['available_at'],t[0]['entry_time'])
        self.assertAlmostEqual(t[0]['entry'],100.05)

    def test_stop_first_ambiguous(self):
        self.a[2,2:4]=[140,80];t,_,_=self.run_case()
        self.assertEqual(t[0]['reason'],'STOP_AMBIGUOUS_BOTH');self.assertLess(t[0]['net_r'],0)

    def test_open_barrier_has_priority_over_later_wicks(self):
        self.a[3,1:5]=[140,145,80,100];t,_,_=self.run_case()
        self.assertEqual(t[0]['reason'],'TARGET_AT_OPEN_CONSERVATIVE')
        self.assertFalse(t[0]['ambiguous'])

    def test_adverse_stop_gap_can_exceed_risk(self):
        self.a[3,1:5]=[70,75,65,70];t,_,_=self.run_case()
        self.assertEqual(t[0]['reason'],'STOP_GAP');self.assertTrue(t[0]['risk_budget_breached'])

    def test_time_exit_after24_closed_bars_not_same_close(self):
        t,_,_=self.run_case();self.assertEqual(t[0]['exit_i'],26)
        self.assertEqual(t[0]['reason'],'TIME_24H_NEXT_OPEN')

    def test_one_position_and_all_skipped_signals_recorded(self):
        self.l[4]=self.l[30]=True;t,_,d=self.run_case()
        self.assertEqual(len(t),2);self.assertEqual(d[1]['status'],'OVERLAPPING_POSITION')
        self.assertGreater(t[1]['entry_i'],t[0]['exit_i'])

    def test_entry_fees_immediately_in_mtm_and_cash_identity(self):
        t,e,_=self.run_case();x=t[0]
        self.assertLess(e[2,1],200)
        self.assertAlmostEqual(x['net_usdt'],x['gross_before_friction']-x['slippage_cost']-x['fees']-x['funding_paid'])
        self.assertAlmostEqual(e[-1,1],200+x['net_usdt'])

    def test_stop_budget_includes_costs_and_notional_cap(self):
        t,_,_=self.run_case();x=t[0]
        self.assertLessEqual(x['planned_risk_usdt'],2+1e-12)
        self.assertLessEqual(x['qty_btc']*x['entry']*1.001,200+1e-12)

    def test_short_symmetry(self):
        self.l[:]=False;self.s[1]=True;self.a[2,2:4]=[120,60];t,_,_=self.run_case()
        self.assertEqual(t[0]['side'],-1);self.assertEqual(t[0]['reason'],'STOP_AMBIGUOUS_BOTH')

    def test_period_purge_and_no_forced_favorable_close(self):
        self.l[60]=True;t,_,d=self.run_case()
        self.assertEqual(d[-1]['status'],'PURGED_END_HORIZON');self.assertEqual(len(t),1)

    def test_funding_exact_and_missing_mark_never_zero(self):
        f=np.array([[self.a[3,0]+2,.001,100,8,99,101]])
        t,_,_=simulate(self.a,self.atr,self.l,self.s,f)
        self.assertAlmostEqual(t[0]['funding_paid'],t[0]['qty_btc']*.1)
        f[0,2]=np.nan
        with self.assertRaisesRegex(ValueError,'EXACT_FUNDING_MARK'):
            simulate(self.a,self.atr,self.l,self.s,f,p=replace(Assumptions(),funding_mode='EXACT_MARK_REQUIRED'))
        t,_,_=simulate(self.a,self.atr,self.l,self.s,f)
        self.assertEqual(t[0]['funding_missing_marks_used'],1)
        self.assertAlmostEqual(t[0]['funding_paid'],t[0]['qty_btc']*.101)

    def test_ambiguous_funding_credit_omitted_but_debit_charged(self):
        self.a[3,2]=140;f=np.array([[self.a[3,0]+2,-.001,100,8,99,101]])
        t,_,_=simulate(self.a,self.atr,self.l,self.s,f)
        self.assertEqual(t[0]['funding_paid'],0);self.assertEqual(t[0]['funding_timing_ambiguities'],1)
        f[0,1]=.001;t,_,_=simulate(self.a,self.atr,self.l,self.s,f)
        self.assertGreater(t[0]['funding_paid'],0)

    def test_future_prices_do_not_change_completed_trade(self):
        self.a[3,3]=80;first=self.run_case()[0];self.a[10:,4]*=.7
        self.assertEqual(first,self.run_case()[0])

    def test_zero_trades_are_not_zero_uncertainty_or_profit_factor(self):
        self.l[:]=False;t,e,_=self.run_case();m=metrics(t,e)
        self.assertEqual(m['n'],0);self.assertIsNone(m['expectancy_r']);self.assertIsNone(m['profit_factor'])


class StatisticsAndParityTests(unittest.TestCase):
    def test_block_bootstrap_deterministic_and_seven_day_contiguous(self):
        x=block_indices(31);np.testing.assert_array_equal(x,block_indices(31))
        np.testing.assert_array_equal(x[:,:7],(x[:,:1]+np.arange(7))%31)

    def test_no_events_no_confidence_interval(self):
        r=ratio_ci(np.zeros(100),np.zeros(100))
        self.assertIsNone(r['ci']);self.assertEqual(r['valid_replicates'],0)

    def test_zero_event_days_remain_in_denominator(self):
        a=bars(24*30);r,c=daily([dict(entry_i=3,net_r=1.)],a,0,len(a))
        self.assertEqual(len(c),30);self.assertEqual(c.sum(),1);self.assertEqual((c==0).sum(),29)

    def test_perfect_local_fixture_comparison_is_not_real_pine_evidence(self):
        a=bars(200);f=ind.calculate(a);s=ind.signals(f);i=150
        row=dict(ticker='BINANCE:BTCUSDT.P',timeframe='60',open_time=int(a[i,0]),available_at=int(a[i,0])+HOUR,
            adx_threshold=40,bbwp_threshold=85,long=bool(s['long'][i]),short=bool(s['short'][i]))
        row.update({k:float(f[k][i]) for k in ('kon_trend','kon_signal','adx','plus_di','minus_di','ao','bbwp','atr')})
        row.update({k:float(a[i,j]) for k,j in [('open',1),('high',2),('low',3),('close',4),('volume',5)]})
        self.assertEqual(compare([row],a)['passed'],1)
        row['ticker']='BINANCE:BTCUSDT'
        with self.assertRaises(ValueError):compare([row],a)

    def test_empty_real_log_set_cannot_certify_parity(self):
        self.assertEqual(compare([],bars(150))['parity_status'],'NO_ACTUAL_RECORDS')
        from research.confluence_1h.evaluate import json_write,csv_write
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            csv_write(p/'sample.csv',[dict(n=1)])
            json_write(p/'sample.json',dict(n=1))
            self.assertEqual((p/'sample.csv').read_bytes(),b'n\n1\n')
            self.assertNotIn(b'\r',(p/'sample.json').read_bytes())


class SafetyTests(unittest.TestCase):
    def test_source_references_and_base_files_unchanged(self):
        m=json.loads((LAB/'source_manifest.json').read_text())
        for name,entry in m['sources'].items():self.assertEqual(hashlib.sha256((LAB/'reference_sources'/name).read_bytes()).hexdigest(),entry['sha256'])
        for name,expected in m['protected_git_sha256'].items():
            raw=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),expected,name)
        evidence=LAB/'artifacts'
        if (evidence/'artifact_checksums.json').exists():
            for name,digest in json.loads((evidence/'artifact_checksums.json').read_text()).items():
                path=evidence/name
                raw=path.read_bytes() if path.exists() else gzip.decompress((evidence/(name+'.gz')).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(),digest,name)

    def test_production_has_no_new_research_dependency(self):
        m=json.loads((LAB/'source_manifest.json').read_text())
        for name in m['protected_git_sha256']:
            if not name.endswith('.py') or name.startswith('test_'):continue
            source=(ROOT/name).read_text(encoding='utf-8-sig');ast.parse(source)
            self.assertNotIn('confluence_1h',source,name)

    def test_no_execution_or_credentials_in_lab(self):
        forbidden={'ccxt','guardian_bitunix','trade_guardian','v8_executor','guardian_capital_v2','dotenv'}
        for path in LAB.glob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):self.assertFalse(any(x.name.split('.')[0] in forbidden for x in node.names))
                if isinstance(node,ast.ImportFrom):self.assertNotIn((node.module or '').split('.')[0],forbidden)
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):self.assertNotIn(node.func.attr,('post','put','delete','create_order','cancel_order','set_leverage'))

    def test_original_protocol_is_fixed_before_outcomes(self):
        raw=(LAB/'protocol.json').read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'8562b94976abaad64bb49e7d46cb2fe94ee546e3d81cfb5b8b5511c8739519e5')

    def test_bad_raw_timestamps_rejected(self):
        row=['0','100','101','99','100','1','3599999','0','0','0','0','0']
        self.assertEqual(len(decode_klines([row])),1)
        numeric_first=row.copy();numeric_first[0]=0
        self.assertEqual(len(decode_klines([numeric_first])),1)
        with self.assertRaises(ValueError):decode_klines([row,row])
        row[6]='3600000'
        with self.assertRaises(ValueError):decode_klines([row])


if __name__=='__main__':unittest.main()
