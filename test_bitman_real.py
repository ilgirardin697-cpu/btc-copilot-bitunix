"""Offline numerical, event, persistence and no-authority regression tests."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from research.bitman_real import indicators as m
from research.bitman_real.config import Config,HOUR,TIMEFRAMES,BASE_SHA,SHORT_PROVEN
from research.bitman_real.events import snapshots,analyze,geometry,direction
from research.bitman_real.market import aggregate,validate
from research.bitman_real.outcomes import measure,first_passage,summarize,block_bootstrap
from research.bitman_real.observer import BitmanRealObserver
from research.bitman_real.telegram import render
from research.bitman_real import storage


def fixture(n=400,start=1577836800000):
    rng=np.random.default_rng(672);c=100*np.exp(np.cumsum(rng.normal(0,.01,n)))
    o=np.r_[c[0],c[:-1]];v=rng.uniform(50,500,n)
    return np.column_stack([start+np.arange(n)*HOUR,o,np.maximum(c,o)*1.006,np.minimum(c,o)*.994,c,v,v*.5])


def simple_features(mountain,ma):
    n=len(ma);f={k:np.ones(n)*10 for k in ('close','rsi','mfi','boll','stoch','atr','adx','di_plus','ao','bbwp')}
    f.update(mountain=np.array(mountain,float),ma=np.array(ma,float),di_minus=np.ones(n),
             adx_slope=np.zeros(n),ao_slope=np.zeros(n),bbwp_slope=np.zeros(n),mountain_slope=np.ones(n))
    return f


class MathTests(unittest.TestCase):
    def test_rsi_wilder_seed(self):
        values=np.r_[np.nan,np.arange(1,16.)]
        out=m.rma(values,14)
        self.assertTrue(np.isnan(out[13]));self.assertEqual(out[14],7.5)
        self.assertAlmostEqual(out[15],(7.5*13+15)/14)

    def test_ema15_seed(self):
        a=m.ema([np.nan,10.,18.],15)
        self.assertTrue(np.isnan(a[0]));self.assertEqual(a[1],10.);self.assertEqual(a[2],11.)

    def test_public_mountain_formula(self):
        f=m.calculate(fixture())
        np.testing.assert_allclose(f['mountain'],(f['rsi']+f['mfi']+f['boll']+f['stoch']/3)/2,equal_nan=True)
        np.testing.assert_allclose(f['ma'],m.ema(f['mountain'],15),equal_nan=True)

    def test_mfi_hlc3_positive_negative(self):
        a=fixture(70);f=m.calculate(a);p=(a[:,2]+a[:,3]+a[:,4])/3;i=35
        j=np.arange(i-13,i+1);chg=p[j]-p[j-1];amount=p[j]*a[j,5]
        expected=100*sum(amount[chg>0])/sum(amount[chg!=0])
        self.assertAlmostEqual(f['mfi'][i],expected)

    def test_boll_population_std_25_ohlc4(self):
        a=fixture();f=m.calculate(a);p=a[:,1:5].mean(axis=1);w=p[30:55]
        self.assertAlmostEqual(f['boll'][54],100*(w[-1]-w.mean())/(4*w.std()))

    def test_stochastic_21_sma3(self):
        a=fixture();f=m.calculate(a);p=a[:,1:5].mean(axis=1);values=[]
        for i in range(48,51):
            low=min(a[i-20:i+1,3]);high=max(a[i-20:i+1,2]);values.append(100*(p[i]-low)/(high-low))
        self.assertAlmostEqual(f['stoch'][50],np.mean(values))

    def test_ao_standard(self):
        a=fixture();f=m.calculate(a);mid=(a[:,2]+a[:,3])/2
        self.assertAlmostEqual(f['ao'][99],mid[95:100].mean()-mid[66:100].mean())

    def test_adx_di14_no_threshold(self):
        f=m.calculate(fixture())
        self.assertTrue(np.all((f['adx'][100:]>=0)&(f['adx'][100:]<=100)))
        self.assertTrue(np.all(f['di_plus'][100:]>=0));self.assertTrue(np.all(f['di_minus'][100:]>=0))
        np.testing.assert_allclose(f['adx_slope'][101:],np.diff(f['adx'][100:]))

    def test_bbwp7_prior100(self):
        a=fixture();f=m.calculate(a);c=a[:,4];i=170
        width=lambda k:4*c[k-6:k+1].std()/c[k-6:k+1].mean()
        expected=sum(width(k)<width(i) for k in range(i-100,i))
        self.assertEqual(f['bbwp'][i],expected)

    def test_prefix_causality_all_indicators(self):
        a=fixture();full=m.calculate(a);prefix=m.calculate(a[:300])
        for k in full:np.testing.assert_allclose(full[k][:300],prefix[k],equal_nan=True)

    def test_future_changes_do_not_change_past(self):
        a=fixture();b=a.copy();b[250:,1:5]*=8
        f=m.calculate(a);g=m.calculate(b)
        for k in f:np.testing.assert_allclose(f[k][:250],g[k][:250],equal_nan=True)

    def test_degenerate_market_unavailable(self):
        a=fixture(150);a[:,1:5]=100.;a[:,5:]=0.
        f=m.calculate(a);self.assertTrue(np.isnan(f['mountain'][-1]))


class EventTests(unittest.TestCase):
    def rows(self,mountain,ma,window=3):
        n=len(ma);a=fixture(n)
        with patch('research.bitman_real.events.calculate',return_value=simple_features(mountain,ma)):
            return snapshots(a,'1H',Config(window))

    def test_geometry_entry_exit(self):
        r=self.rows([10]*4,[11,9,8,12])
        self.assertEqual([x['technical_event'] for x in r],[None,'KONKORDE_ENTRY',None,'KONKORDE_EXIT'])

    def test_reentry_one_event_not_two(self):
        r=self.rows([10]*5,[11,9,12,11,8],2)
        self.assertEqual(r[-1]['event'],'KONKORDE_REENTRY');self.assertEqual(r[-1]['exit_age_bars'],2)

    def test_reentry_window_explicit(self):
        for window,reentry in ((1,False),(2,True),(3,True)):
            self.assertEqual(self.rows([10]*5,[11,9,12,11,8],window)[-1]['reentry'],reentry)
        with self.assertRaises(TypeError):Config()

    def test_no_event_first_valid(self):
        self.assertIsNone(self.rows([10],[9])[0]['event'])

    def test_missing_geometry_resets_episode(self):
        r=self.rows([10,10,np.nan,10],[11,9,np.nan,8])
        self.assertIsNone(r[-1]['event'])

    def test_boundary_touch_is_outside(self):
        r=self.rows([10]*3,[10,0,5]);self.assertFalse(r[0]['inside']);self.assertFalse(r[1]['inside']);self.assertTrue(r[2]['inside'])

    def test_negative_mountain_geometry_not_long_inversion(self):
        r=self.rows([-10]*2,[-11,-9]);self.assertEqual(r[-1]['technical_event'],'KONKORDE_ENTRY')
        self.assertNotEqual(r[-1]['state'],'SHORT')

    def test_distance_zero_and_separation(self):
        r=self.rows([10]*3,[11,9,7]);self.assertEqual(r[-1]['distance_to_zero'],7.)
        self.assertEqual(r[-1]['separation'],3.);self.assertEqual(r[-1]['strength'],'EXPANDING')

    def test_strength_contracting_and_stable(self):
        r=self.rows([10]*4,[11,7,9,9])
        self.assertEqual(r[-2]['strength'],'CONTRACTING');self.assertEqual(r[-1]['strength'],'STABLE')

    def test_no_signal_every_bar(self):
        r=self.rows([10]*6,[11,9,8,7,6,5]);self.assertEqual(sum(x['technical_event'] is not None for x in r),1)

    def test_event_prefix_invariant(self):
        a=fixture(400);r=snapshots(a,'1H',Config(3));p=snapshots(a[:300],'1H',Config(3))
        self.assertEqual(r[:300],p)

    def test_closed_only_every_tf(self):
        a=fixture(400);now=int(a[-2,0]+HOUR)
        for tf,interval in TIMEFRAMES.items():
            r=analyze(a,tf,now,Config(3));self.assertTrue(all(x['candle_close']<=now for x in r))
            self.assertEqual(r[-1]['candle_close'],now//interval*interval)

    def test_no15m_or_weekly(self):
        for tf in ('15m','1W'):
            with self.assertRaises(ValueError):analyze(fixture(),tf,9999999999999,Config(3))

    def test_complete_4h_daily(self):
        a=fixture(48);self.assertEqual(len(aggregate(a,4*HOUR,a[-1,0]+HOUR)),12)
        self.assertEqual(len(aggregate(a,24*HOUR,a[-1,0]+HOUR)),2)

    def test_gap_rejected_not_interpolated(self):
        with self.assertRaises(ValueError):validate(np.delete(fixture(),8,axis=0))


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.a=fixture(80,start=0);self.a[:,1:5]=[100,102,99,101]

    def test_forward_return_mfe_mae(self):
        r=measure(self.a,0,100,4,80*HOUR)
        self.assertAlmostEqual(r['forward_return'],.01);self.assertAlmostEqual(r['mfe'],.02);self.assertAlmostEqual(r['mae'],-.01)

    def test_no_signal_candle_used(self):
        self.a[0,2]=99999
        r=measure(self.a,HOUR,100,1,80*HOUR);self.assertAlmostEqual(r['mfe'],.02)

    def test_future_beyond_horizon_ignored(self):
        r=measure(self.a,0,100,4,80*HOUR);self.a[4:,2]*=8
        self.assertEqual(r,measure(self.a,0,100,4,80*HOUR))

    def test_all_independent_hit_times(self):
        self.a[:3,2]=[100.5,101.5,102.5];self.a[:3,3]=[99.5,98.5,97.5]
        r=measure(self.a,0,100,3,80*HOUR)
        self.assertEqual([r[k] for k in ('first_up1_hour','first_down1_hour','first_up2_hour','first_down2_hour')],[2,2,3,3])

    def test_ambiguous_same_bar_not_success(self):
        self.assertEqual(first_passage(np.array([103]),np.array([97]),100,.01,.01)['race'],'AMBIGUOUS')

    def test_first_passage_up_down_unresolved(self):
        for high,low,expected in (([102],[100],'UP_FIRST'),([100],[98],'DOWN_FIRST'),([100.5],[99.5],'UNRESOLVED')):
            self.assertEqual(first_passage(np.array(high),np.array(low),100,.01,.01)['race'],expected)

    def test_missing_candle_censored(self):
        self.assertFalse(measure(np.delete(self.a,2,axis=0),0,100,4,80*HOUR)['complete'])

    def test_unmatured_censored(self):
        self.assertFalse(measure(self.a,0,100,72,48*HOUR)['complete'])

    def test_pending_not_failure(self):
        r=summarize([dict(complete=False),measure(self.a,0,100,1,80*HOUR)])
        self.assertEqual(r['n_complete'],1);self.assertEqual(r['n_incomplete'],1)

    def test_exit_still_raw_return_not_fake_short_profit(self):
        self.assertGreater(measure(self.a,0,100,1,80*HOUR)['forward_return'],0)

    def test_deterministic_block_bootstrap(self):
        self.assertEqual(block_bootstrap([.01,-.02],[0,8*24*HOUR]),block_bootstrap([.01,-.02],[0,8*24*HOUR]))

    def test_chronological_splits(self):
        from research.bitman_real.study import split,stamp
        self.assertEqual(split(stamp('2021-12-31T23:00:00Z'))[0],'TRAIN')
        self.assertEqual(split(stamp('2022-01-01T00:00:00Z'))[0],'VALIDATION')
        self.assertEqual(split(stamp('2024-01-01T00:00:00Z'))[0],'TEST')

    def test_descriptive_bins_ignore_test(self):
        from research.bitman_real.study import fit_bins,stamp
        rows={tf:[dict(candle_close=stamp('2021-01-01T00:00:00Z'),technical_event='KONKORDE_ENTRY',distance_to_zero=2.,separation=1.),
                  dict(candle_close=stamp('2025-01-01T00:00:00Z'),technical_event='KONKORDE_ENTRY',distance_to_zero=9999.,separation=9999.)] for tf in TIMEFRAMES}
        before=fit_bins(rows)
        for tf in rows:rows[tf][1]['distance_to_zero']=-999999
        self.assertEqual(before,fit_bins(rows))


class DirectionRendererTests(unittest.TestCase):
    def setUp(self):self.s=dict(mountain=10.,ma=8.,inside=True,di_plus=20.,di_minus=10.,ao=1.,adx=12.,bbwp=40.)
    def test_long_explained_no_score(self):
        state,reasons,_=direction(self.s);self.assertEqual(state,'LONG');self.assertTrue(reasons)
    def test_adx_no_absolute_threshold(self):
        self.s['adx']=1.;self.assertEqual(direction(self.s)[0],'LONG')
    def test_ao_and_bbwp_not_mandatory_filters(self):
        self.s.update(ao=-100.,bbwp=0.,bbwp_slope=-5.);self.assertEqual(direction(self.s)[0],'LONG')
    def test_setup_forming(self):
        self.s['di_plus']=5.;self.assertEqual(direction(self.s)[0],'SETUP_FORMING')
    def test_short_not_proven(self):
        self.s.update(mountain=-10.,ma=-8.,di_plus=5.,ao=-1.)
        state,reasons,_=direction(self.s);self.assertEqual(state,'BLOCKED');self.assertIn('SHORT_LOGIC_NOT_PROVEN',reasons)
    def test_wait(self):
        self.s.update(inside=False,mountain_slope=-1.);self.assertEqual(direction(self.s)[0],'WAIT')
    def test_missing_blocked(self):
        self.s['ma']=None;self.assertEqual(direction(self.s)[0],'BLOCKED')
    def test_banners_and_safety(self):
        for state,banner in (('LONG','🟢 LONG'),('SETUP_FORMING','🟡 SETUP FORMING'),('WAIT','⚪ WAIT'),('BLOCKED','🛑 BLOCKED')):
            text=render(dict(self.s,state=state));self.assertTrue(text.startswith(banner))
            self.assertIn('SHADOW ONLY',text);self.assertIn('TRADE AUTHORITY: NONE',text);self.assertIn('NOT PROVEN',text)
    def test_renderer_cannot_invent_short(self):self.assertTrue(render(dict(state='SHORT')).startswith('🛑 BLOCKED'))
    def test_technical_entry_exit_reentry(self):
        for kind in ('ENTRY','EXIT','REENTRY'):self.assertIn('KONKORDE '+kind,render(dict(state='WAIT',event='KONKORDE_'+kind)))
    def test_trend_speed_not_fabricated(self):self.assertIn('NOT IMPLEMENTED / FORMULA NOT VERIFIED',render(self.s))


class ObserverSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.sent=[]
        self.observer=BitmanRealObserver(Path(self.tmp.name)/'bitman_real',3,self.sent.append)
        self.bars=fixture(3000);self.now=int(self.bars[-1,0]+HOUR)
        self.states={tf:'WAIT' for tf in TIMEFRAMES}
        def analyze_stub(a,tf,now,cfg):
            stamp=now//TIMEFRAMES[tf]*TIMEFRAMES[tf]
            return [dict(state=self.states[tf],reasons=[],event=None,candle_close=stamp,timeframe=tf,shadow_only=True,trade_authority=False)]
        self.patcher=patch('research.bitman_real.observer.analyze',side_effect=analyze_stub)
        self.patcher.start();self.addCleanup(self.patcher.stop)
    def test_initial_context_not_new_event(self):self.observer.cycle(self.bars,self.now);self.assertEqual(self.sent,[])
    def test_no_wait_spam_or_same_candle_repeat(self):
        for i in range(4):self.observer.cycle(self.bars,self.now+i*HOUR)
        self.assertEqual(self.sent,[])
    def test_direction_transition_alerts_once(self):
        self.observer.cycle(self.bars,self.now);self.states['1H']='LONG'
        self.observer.cycle(self.bars,self.now+HOUR);self.observer.cycle(self.bars,self.now+HOUR)
        self.assertEqual(len(self.sent),1)
    def test_restart_dedupe(self):
        self.test_direction_transition_alerts_once();before=self.observer.journal.read_bytes()
        self.observer=BitmanRealObserver(self.observer.root,3,self.sent.append)
        self.observer.cycle(self.bars,self.now+HOUR);self.assertEqual(self.observer.journal.read_bytes(),before)
    def test_reconfigure_same_bar_refreshes_context_silently(self):
        self.observer.cycle(self.bars,self.now)
        self.observer=BitmanRealObserver(self.observer.root,5,self.sent.append)
        self.observer.cycle(self.bars,self.now)
        self.assertEqual(self.observer.state['1H']['signature'],self.observer.signature)
        self.assertEqual(self.sent,[])
    def test_offline_gap_catchup_silent(self):
        self.observer.cycle(self.bars,self.now);self.states['1H']='LONG'
        self.observer.cycle(self.bars,self.now+10*HOUR);self.assertEqual(self.sent,[])
    def test_failure_recovery_silent(self):
        self.observer.cycle(self.bars,self.now);self.observer.cycle(np.zeros((3,7)),self.now)
        self.states['1H']='LONG';self.observer.cycle(self.bars,self.now+HOUR);self.assertEqual(self.sent,[])
    def test_one_tf_failure_isolated(self):
        self.patcher.stop()
        def broken(a,tf,n,c):
            if tf=='4H':raise ValueError('no raw exception logged')
            return [dict(state='WAIT',reasons=[],event=None,candle_close=n//TIMEFRAMES[tf]*TIMEFRAMES[tf])]
        with patch('research.bitman_real.observer.analyze',side_effect=broken):
            r=self.observer.cycle(self.bars,self.now);self.assertIn('1H',r);self.assertIn('1D',r);self.assertNotIn('4H',r)
    def test_callback_failure_nonfatal(self):
        self.observer.cycle(self.bars,self.now);self.states['1H']='LONG';self.observer.send=lambda _:1/0
        self.assertIn('1H',self.observer.cycle(self.bars,self.now+HOUR))
    def test_separate_storage(self):
        with self.assertRaises(ValueError):BitmanRealObserver(Path(self.tmp.name)/'guardian',3)
    def test_no_operational_capabilities(self):
        self.assertFalse(self.observer.trade_authority)
        self.assertFalse(SHORT_PROVEN)
        for name in ('execute','place_order','flash_close_position','getUpdates','change_leverage'):
            self.assertFalse(hasattr(self.observer,name))
    def test_atomic_and_fsync(self):
        p=Path(self.tmp.name)/'s.json'
        with patch('research.bitman_real.storage.os.fsync',wraps=storage.os.fsync) as fs:
            storage.atomic(p,{'a':1});storage.append(p.with_suffix('.jsonl'),{'b':2});self.assertGreaterEqual(fs.call_count,2)
        self.assertEqual(json.loads(p.read_text()),{'a':1});self.assertFalse(list(p.parent.glob('*.tmp')))
    def test_entire_module_no_network_no_order_calls(self):
        forbidden=('requests','urllib','httpx','aiohttp','trade_guardian','guardian_bitunix','live_auto','v8_executor','research.bitman')
        for path in Path('research/bitman_real').glob('*.py'):
            source=path.read_text(encoding='utf-8');tree=ast.parse(source)
            for node in ast.walk(tree):
                names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                self.assertFalse(any(n==f or n.startswith(f+'.') for n in names for f in forbidden))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,('post','getUpdates','place_order','place_market','flash_close_position','change_leverage','withdraw','transfer'))
            self.assertNotIn('BITUNIX_API_',source);self.assertNotIn('TELEGRAM_BOT_TOKEN',source)

    def test_http_monkeypatch_zero_requests(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('NETWORK FORBIDDEN')) as network:
            self.observer.cycle(self.bars,self.now);self.states['1H']='LONG'
            self.observer.cycle(self.bars,self.now+HOUR)
            for state in ('LONG','SHORT','SETUP_FORMING','WAIT','BLOCKED'):
                render(dict(state=state))
            network.assert_not_called()

    def test_frozen_protocol_and_results(self):
        from research.bitman_real.study import ART,code_hash,digest
        p=json.loads((ART/'protocol.json').read_text());r=json.loads((ART/'results.json').read_text())
        self.assertEqual(code_hash(),p['code_sha256']);self.assertEqual(r['protocol_sha256'],digest(ART/'protocol.json'))
        self.assertEqual(r['phase2_status'],'REJECT');self.assertFalse(r['trade_authority'])

    def test_full_source_safety_audit(self):
        from research.bitman_real.safety import audit
        r=audit();self.assertEqual(r['status'],'PASS');self.assertFalse(r['network_transport'])
        self.assertFalse(r['order_capability']);self.assertFalse(r['trade_authority'])
    def test_production_files_unchanged(self):
        for path in ('trade_guardian.py','guardian_risk.py','guardian_bitunix.py','guardian_commands.py',
                     'guardian_signals.py','koncorde_shadow.py','trend_v8.py','main.py','live_auto.py','railway.json'):
            original=subprocess.check_output(['git','show',BASE_SHA+':'+path])
            self.assertEqual(Path(path).read_bytes().replace(b'\r\n',b'\n'),original.replace(b'\r\n',b'\n'))


if __name__=='__main__':unittest.main()
