"""Synthetic/offline tests only. No production, market or Telegram calls."""
import ast
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
from research.bitman import core, engine, mlrsi
from research.bitman.data import HOUR, aggregate, public_get
from research.bitman.spec import Candidate, candidates, neighbors, BASE_SHA
from research.bitman.telegram import render
from research.bitman.shadow import ShadowObserver


def setUpModule():
    global _network_block
    _network_block=patch('requests.sessions.Session.request',side_effect=AssertionError('LIVE HTTP FORBIDDEN IN TESTS'))
    _network_block.start()


def tearDownModule():
    _network_block.stop()


def fixture(n=900,start=1577664000000):
    rng=np.random.default_rng(44); close=100*np.exp(np.cumsum(rng.normal(0,.006,n)))
    opening=np.r_[close[0],close[:-1]]; high=np.maximum(opening,close)*1.004; low=np.minimum(opening,close)*.996
    volume=rng.uniform(100,200,n); ratio=rng.uniform(.3,.7,n)
    return np.column_stack([start+np.arange(n)*HOUR,opening,high,low,close,volume,volume*ratio])


class IndicatorTests(unittest.TestCase):
    def test_complete_aggregate(self):
        a=fixture(12,start=0); a[:,0]=np.arange(12)*300000
        b=aggregate(a,HOUR)
        self.assertEqual(b.shape,(1,7)); self.assertEqual(b[0,4],a[-1,4])

    def test_gap_not_interpolated(self):
        a=fixture(12,start=0); a[:,0]=np.arange(12)*300000
        self.assertEqual(len(aggregate(np.delete(a,5,axis=0),HOUR)),0)

    def test_open_incomplete_group_omitted(self):
        a=fixture(11,start=0); a[:,0]=np.arange(11)*300000
        self.assertEqual(len(aggregate(a,HOUR)),0)

    def test_alignment_closed_only(self):
        values=core.align(np.array([0.]),np.array([7.]),4*HOUR,np.array([3*HOUR,4*HOUR]))
        self.assertTrue(np.isnan(values[0])); self.assertEqual(values[1],7.)

    def test_v8_uses_last_closed_4h_state_not_current_1h_price(self):
        from research.bitman.comparators import v8_closed_state
        a=fixture(900,start=0)
        before=v8_closed_state(a)
        # Last three1H closes vary massively, but no new4H bar has closed yet.
        end=899 # index899 is a4H close; indices896..898 must carry index895's state
        for k in range(896,899):
            self.assertEqual(before[k],before[895])
        changed=a.copy();changed[896:899,4]*=2
        np.testing.assert_array_equal(v8_closed_state(changed)[896:899],before[896:899])

    def test_ema_seed(self):
        np.testing.assert_allclose(core.ema(np.array([1.,2.,3.]),3),[1,1.5,2.25])

    def test_wilder_rsi_seed(self):
        a=np.arange(100,dtype=float)+1; rr=core.rsi(a,89)
        self.assertTrue(np.all(np.isnan(rr[:89]))); self.assertEqual(rr[89],100.)

    def test_ao_formula(self):
        a=fixture(); f=core.base_features(a); midpoint=(a[:,2]+a[:,3])/2
        self.assertAlmostEqual(f['ao'][-1],np.mean(midpoint[-5:])-np.mean(midpoint[-34:]))

    def test_linreg_endpoint(self):
        a=np.arange(100,dtype=float)
        np.testing.assert_allclose(core.regression_endpoint(a)[19:],a[19:],atol=1e-10)

    def test_adx_di_direction(self):
        a=fixture(100); a[:,1:5]=np.column_stack([np.arange(100)+100,np.arange(100)+102,np.arange(100)+99,np.arange(100)+101])
        f=core.base_features(a)
        self.assertGreater(f['plus_di'][-1],f['minus_di'][-1]); self.assertAlmostEqual(f['adx'][-1],100.)

    def test_pivot_confirmation_delay(self):
        a=fixture(5,start=0); a[:,2]=[2,3,6,4,3]; a[:,3]=.5; a[:,4]=1.
        before=core.structures(a[:4],np.ones(4)); after=core.structures(a,np.ones(5))
        self.assertTrue(np.isnan(before['swing_high'][-1])); self.assertEqual(after['swing_high'][-1],6.)

    def test_all_feature_prefix_invariant(self):
        a=fixture(); full=core.base_features(a); prefix=core.base_features(a[:750])
        for k,v in prefix.items():
            if k not in ('h4','day'):
                np.testing.assert_allclose(v,full[k][:len(v)],equal_nan=True,err_msg=k)

    def test_candidate_signal_prefix_invariant(self):
        a=fixture(); p=Candidate(); f=core.candidate_features(a,core.base_features(a),p,{})
        b=a[:750]; prefix=core.candidate_features(b,core.base_features(b),p,{})
        for x,y in zip(core.signals(f,p,1),core.signals(prefix,p,1)): np.testing.assert_array_equal(x[:750],y)

    def test_no_duplicate_inside_episode(self):
        a=fixture(); p=Candidate(); f=core.candidate_features(a,core.base_features(a),p,{})
        event,_,setup=core.signals(f,p,1)
        self.assertFalse(np.any(event[1:]&setup[:-1]))

    def test_short_is_separate_mask(self):
        a=fixture(); p=Candidate(); f=core.candidate_features(a,core.base_features(a),p,{})
        long=core.signals(f,p,1)[0]; short=core.signals(f,p,-1)[0]
        self.assertFalse(np.any(long&short)); self.assertFalse(np.array_equal(short,~long))

    def test_disabled_trend_removed_from_exit(self):
        a=fixture(); p=Candidate(disabled=('TREND','RSI_CLOUD'))
        f=core.candidate_features(a,core.base_features(a),p,{})
        self.assertFalse(np.any(core.signals(f,p,1)[1]))

    def test_neighbors_not_cartesian_grid(self):
        self.assertEqual(len(neighbors(Candidate())),14)
        self.assertEqual(len(neighbors(Candidate(dmi='direction',exit='opposite'))),10)
        self.assertEqual(len(candidates()),18)

    def test_frozen_math_bytes(self):
        self.assertEqual(len(mlrsi.frozen_source_ok()),64)

    def test_ml_adapter_uses_low_and_frozen_port(self):
        a=fixture(100); result=mlrsi.features(a,use_cache=False)
        expected=mlrsi.CausalSeries(); expected.configure_bootstrap(47)
        # fixture starts2019-12-30: Jan1 starts at48; compare the2020session.
        for i in range(100):
            row=expected.push(a[i,3])
            if i>=48 and row['mlrsi_raw'] is not None:
                self.assertAlmostEqual(result['ml_raw'][i],row['mlrsi_raw'])

    def test_ml_adapter_prefix(self):
        a=fixture(120)
        full=mlrsi.features(a,use_cache=False); before=mlrsi.features(a[:90],use_cache=False)
        for k,v in before.items(): np.testing.assert_allclose(v,full[k][:90],equal_nan=True)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.bars=np.array([[i*HOUR,100.,100.5,99.5,100.,100.,50.] for i in range(5)])
        self.f=dict(atr=np.ones(5)); self.p=Candidate(); self.entry=np.array([True,False,False,False,False])
        self.opposite=np.zeros(5,bool); self.zero=dict(fee_bps=0,slip_bps=0,stop_slip_bps=0)

    def run_case(self,**kw):
        args=dict(bars=self.bars,f=self.f,entry=self.entry,opposite=self.opposite,funding=np.empty((0,2)),
                  p=self.p,side=1,start=0,end=5*HOUR,costs=self.zero)
        args.update(kw); return engine.simulate(**args)

    def test_next_bar_entry(self):
        t=self.run_case()['trades'][0]
        self.assertEqual(t['entry_time'],HOUR);self.assertEqual(t['signal_time'],HOUR)

    def test_no_entry_signal_candle_favorable_fill(self):
        self.bars[0,3]=1.
        self.assertEqual(self.run_case()['trades'][0]['entry_fill'],100.)

    def test_stop_before_target_ambiguous(self):
        self.bars[1,2:4]=[106.,97.]
        t=self.run_case()['trades'][0]
        self.assertEqual(t['exit_reason'],'initial_stop');self.assertFalse(t['tp1_hit'])
        self.assertAlmostEqual(t['net_return'],-.02)

    def test_partial_tp_and_runner(self):
        self.bars[1,2:5]=[105.,100.,104.]
        self.bars[2,1:5]=[103.,103.2,102.5,103.]
        t=self.run_case()['trades'][0]
        self.assertEqual([r['reason'] for r in t['fills']][:2],['tp1','tp2'])
        self.assertAlmostEqual(t['fills'][0]['fraction'],.3);self.assertAlmostEqual(t['fills'][1]['fraction'],.3)

    def test_be_ambiguous_before_tp2(self):
        self.bars[1,2:4]=[106.,99.]
        t=self.run_case()['trades'][0]
        self.assertEqual(t['exit_reason'],'economic_be'); self.assertFalse(t['tp2_hit'])
        self.assertAlmostEqual(t['net_return'],0.,places=12)

    def test_trailing_applies_next_bar_gap_fill(self):
        self.bars[1,2:5]=[103.,100.1,102.5]
        t=self.run_case()['trades'][0]
        self.assertEqual(t['exit_time'],2*HOUR);self.assertEqual(t['exit_reason'],'trailing')
        self.assertAlmostEqual(t['fills'][-1]['price'],100.)

    def test_adverse_slippage_and_all_fees(self):
        r=self.run_case(benchmark=True,costs=dict(fee_bps=5,slip_bps=2,stop_slip_bps=5))
        t=r['trades'][0]
        self.assertGreater(t['entry_fill'],100.);self.assertLess(t['fills'][-1]['price'],100.)
        self.assertAlmostEqual(t['net_return'],-t['fees']-t['slippage'])

    def test_cost_adjusted_be_total_trade(self):
        be=engine.economic_be(1.005,1.,.007,100.,1,.0005,.0005)
        fill=be*(1-.0005)
        final=1.005+.007*(fill-100.)-.007*fill*.0005
        self.assertAlmostEqual(final,1.)

    def test_short_be_total_trade(self):
        be=engine.economic_be(1.005,1.,.007,100.,-1,.0005,.0005)
        fill=be*(1+.0005)
        self.assertAlmostEqual(1.005-.007*(fill-100.)-.007*fill*.0005,1.)

    def test_signed_funding(self):
        funding=np.array([[2*HOUR,.01]])
        long=self.run_case(benchmark=True,funding=funding)['metrics']
        short=self.run_case(benchmark=True,funding=funding,side=-1)['metrics']
        self.assertAlmostEqual(long['total_return'],-.01);self.assertAlmostEqual(short['total_return'],.01)

    def test_future_funding_ignored(self):
        a=self.run_case(benchmark=True)['metrics']
        b=self.run_case(benchmark=True,funding=np.array([[100*HOUR,.9]]))['metrics']
        self.assertEqual(a,b)

    def test_gap_stop_before_opposite_exit(self):
        self.bars[2,1:5]=[97.,98.,96.,97.]; self.opposite[1]=True
        t=self.run_case()['trades'][0]
        self.assertEqual(t['exit_reason'],'initial_stop'); self.assertEqual(t['fills'][-1]['price'],97.)

    def test_combined_never_two_positions(self):
        entries={1:self.entry,-1:self.entry.copy()}
        result=self.run_case(entry=entries,opposite={1:self.opposite,-1:self.opposite},p={1:self.p,-1:self.p},side=0)
        self.assertEqual(result['metrics']['trades'],0);self.assertEqual(result['metrics']['simultaneous_signal_conflicts'],1)

    def test_no_same_bar_reverse(self):
        entries={1:self.entry,-1:np.array([False,True,False,False,False])}; self.opposite[1]=True
        result=self.run_case(entry=entries,opposite={1:self.opposite,-1:self.opposite},p={1:self.p,-1:self.p},side=0)
        self.assertEqual(result['metrics']['trades'],1)

    def test_split_force_flat(self):
        self.assertEqual(self.run_case()['trades'][0]['exit_reason'],'split_end')

    def test_removal_and_bootstrap_deterministic(self):
        r=self.run_case()
        self.assertEqual(engine.bootstrap(r),engine.bootstrap(r))
        self.assertEqual(engine.removal(r,1)['trades'],0)


class IsolationTests(unittest.TestCase):
    def test_frozen_protocol_and_selection_match_artifacts(self):
        from research.bitman import run
        run.check_protocol()
        lock=json.loads((run.ART/'selection_lock.json').read_text())
        results=json.loads((run.ART/'test_results.json').read_text())
        self.assertEqual(run.code_hash(),lock['code_sha256'])
        self.assertEqual(run.digest(run.ART/'selection_lock.json'),results['selection_sha256'])
        self.assertEqual(results['classification'],'REJECT')
        for family in ('classic','fusion'):
            for side in ('1','-1'):
                self.assertEqual(lock[family][side]['selected'],results['configurations'][family+'_'+side]['parameters'])

    def test_production_and_audit_identity_safety(self):
        from research.bitman.safety import audit
        result=audit()
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['trade_authority'])
        self.assertIn('guardian_bitunix.py',result['protected_sha256'])
        self.assertIn('trend_v8.py',result['protected_sha256'])

    def test_serialization_adapter_no_numeric_change(self):
        from research.bitman.evaluate import dumps
        payload=json.loads(dumps(dict(hours=np.int64(7),value=np.float64(.125))))
        self.assertEqual(payload,dict(hours=7,value=.125))

    def test_public_allowlist_blocks_unknown(self):
        with self.assertRaisesRegex(ValueError,'NOT_ALLOWED'): public_get('/not-public',{},[])

    def test_protocol_has_no_test_selection(self):
        from research.bitman.run import eligibility, score
        a=dict(TRAIN=dict(trades=30,expectancy=.1,sharpe=1.,max_dd=-.1),
               VALIDATION=dict(trades=30,expectancy=.1,sharpe=1.,max_dd=-.1),TEST=dict(sharpe=-999))
        s=score(a); a['TEST']['sharpe']=999999
        self.assertEqual(score(a),s);self.assertTrue(eligibility(a))

    def test_no_trading_or_operational_imports(self):
        for name in ('core.py','engine.py','mlrsi.py','data.py','run.py'):
            source=(Path('research/bitman')/name).read_text(encoding='utf-8')
            tree=ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,('post','place_order','flash_close_position','change_leverage'))
            self.assertNotIn('BITUNIX_API_',source);self.assertNotIn('TELEGRAM_BOT_TOKEN',source)

    def test_base_audit_files_identical(self):
        import subprocess
        names=['PRE_BITMAN_AUDIT.md','research/import_forward_journals.py','research/pre_bitman_audit.py']
        for path in names:
            baseline=subprocess.check_output(['git','show',BASE_SHA+':'+path])
            self.assertEqual(Path(path).read_bytes().replace(b'\r\n',b'\n'),baseline.replace(b'\r\n',b'\n'))


class RendererTests(unittest.TestCase):
    def test_long(self): self.assertIn('🟢🔥 BITMAN LONG CONFIRMED',render(dict(state='LONG')))
    def test_short(self): self.assertIn('🔴🔥 BITMAN SHORT CONFIRMED',render(dict(state='SHORT')))
    def test_setup(self): self.assertIn('SETUP FORMING',render(dict(state='SETUP_FORMING')))
    def test_wait(self): self.assertIn('WAIT — ESPERAR',render(dict(state='WAIT')))
    def test_blocked(self): self.assertIn('BLOCKED',render(dict(state='BLOCKED')))
    def test_error(self): self.assertIn('DATA/RISK ERROR',render(dict(state='DATA_RISK_ERROR')))
    def test_no_fabricated_bitunix_data_source(self): self.assertIn('BINANCE USD-M',render(dict(state='WAIT')))
    def test_no_entry_permission_or_authority(self):
        for state in ('LONG','SHORT','SETUP_FORMING','WAIT','BLOCKED','DATA_RISK_ERROR'):
            text=render(dict(state=state));self.assertIn('SHADOW ONLY',text)
            self.assertIn('TRADE AUTHORITY: NONE',text);self.assertNotIn('PUEDES ENTRAR',text)
    def test_reference_levels_and_actual_theoretical_risk(self):
        text=render(dict(state='LONG',entry=82150.,atr=600.))
        self.assertIn('80,950.00',text);self.assertIn('83,350.00',text);self.assertIn('84,550.00',text)
        self.assertIn('1.46%',text);self.assertNotIn('0.50%',text)
    def test_only_active_conditions_count(self):
        text=render(dict(state='SETUP_FORMING',conditions={'TREND':True,'STRUCTURE':False}))
        self.assertIn('1 / 2',text);self.assertIn('❌ STRUCTURE',text)


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'bitman'; self.selection={str(s):dict(selected=Candidate().__dict__) for s in (1,-1)}
        self.bars=fixture(1330);self.messages=[];self.direction=0
        def blocks(f,p,s):
            return {name:np.full(len(f['close']),s==self.direction) for name in ('TREND','RSI_CLOUD','MOMENTUM','DMI')}
        self.patcher=patch('research.bitman.core.blocks',side_effect=blocks);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.observer=ShadowObserver(self.root,self.selection,send=self.messages.append)

    def cycle(self,n): return self.observer.cycle(self.bars[:n],int(self.bars[n-1,0]+HOUR))

    def test_startup_not_new_signal(self):
        self.direction=1;self.cycle(1325)
        self.assertFalse(self.observer.journal.exists())

    def test_new_transition_once(self):
        self.cycle(1325);self.direction=1;self.cycle(1326);self.cycle(1326);self.cycle(1327)
        self.assertEqual(len(self.observer.journal.read_text().splitlines()),1)
        self.assertEqual(len(self.messages),2)

    def test_restart_dedup(self):
        self.cycle(1325);self.direction=1;self.cycle(1326)
        before=self.observer.journal.read_bytes()
        self.observer=ShadowObserver(self.root,self.selection,send=self.messages.append)
        self.cycle(1326);self.cycle(1327)
        self.assertEqual(self.observer.journal.read_bytes(),before)

    def test_gap_recovery_silent(self):
        self.cycle(1325);self.direction=1;self.cycle(1329)
        self.assertFalse(self.observer.journal.exists());self.assertEqual(len(self.messages),1)

    def test_future_open_bar_excluded(self):
        self.cycle(1325)
        result=self.observer.cycle(self.bars[:1327],int(self.bars[1324,0]+HOUR))
        self.assertEqual(result,self.observer.state['snapshot'])

    def test_bad_public_data_nonfatal(self):
        bad=self.bars[:1325].copy();bad[-1,3]=-1
        self.assertEqual(self.observer.cycle(bad,int(bad[-1,0]+HOUR))['state'],'DATA_RISK_ERROR')

    def test_separate_storage(self):
        with self.assertRaisesRegex(ValueError,'SEPARATE'):
            ShadowObserver(Path(self.tmp.name)/'guardian',self.selection)

    def test_callback_failure_nonfatal(self):
        self.observer.send=lambda _:(_ for _ in ()).throw(RuntimeError('not propagated'))
        self.assertIn(self.cycle(1325)['state'],('WAIT','SETUP_FORMING'))

    def test_no_capabilities_in_observer(self):
        self.assertFalse(self.observer.trade_authority)
        for method in ('execute','place_order','flash_close_position','change_leverage','close_all_position'):
            self.assertFalse(hasattr(self.observer,method))

    def test_readonly_forward_bridge(self):
        from research.bitman.forward import run
        self.cycle(1325);self.direction=1;self.cycle(1326)
        before=self.observer.journal.read_bytes()
        result=run(self.root,Path(self.tmp.name)/'report',int(self.bars[-1,0]+HOUR))
        self.assertTrue(result['cohorts']);self.assertFalse(result['signal_reconstruction'])
        self.assertEqual(self.observer.journal.read_bytes(),before)


if __name__=='__main__': unittest.main()
