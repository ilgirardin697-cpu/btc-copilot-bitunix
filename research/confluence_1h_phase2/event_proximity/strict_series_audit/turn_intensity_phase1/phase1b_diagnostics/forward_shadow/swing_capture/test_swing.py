import ast,json,subprocess,unittest
from pathlib import Path
import numpy as np
from . import detector
from .simulator import Config,Minutes,run,be_level,FEE,SLIP,H

def bars(n=7):
    a=np.tile([0,100,100.2,99.8,100,60.],(n,1)).astype(float);a[:,0]=1667260800000+np.arange(n)*H;return a
def signal(i=0,side=1):return dict(i=i,side=side,signal_id='S'+str(i)+':'+str(side),regime4h=1)
def execute(a,side=1,tp=.005,stop=1.5,risk=.005,**kw):return run(a,np.empty((0,6)),np.ones(len(a)),[signal(side=side)],Config(tp,stop,risk),**kw)
def features(series):
    f={k:np.asarray(v,float) for k,v in series.items()};n=len(f['ao'])
    for k in ('minnows','adx','bbwp'):f.setdefault(k,f['ao'].copy())
    for k in ('atr','plus_di','minus_di','kon_signal','sharks','regime4h','regime1d'):f.setdefault(k,np.ones(n))
    return f

class DetectorTests(unittest.TestCase):
    def test_symmetric_no_zero_or_intensity_gate(self):
        for side in (1,-1):
            f=features({'ao':side*np.array([30,20,10,20,30.])})
            ee,_=detector.detect(bars(5),f);self.assertEqual(len(ee),1);self.assertEqual(ee[0]['side'],side);self.assertEqual(ee[0]['i'],3)
    def test_adx_bbwp_any_turn_direction(self):
        for ad in (1,-1):
            for bb in (1,-1):
                x=np.array([3,2,1,2,3.]);f=features(dict(ao=x,adx=100+ad*x,bbwp=50+bb*x))
                ee,_=detector.detect(bars(5),f);self.assertEqual(len(ee),1);self.assertEqual(ee[0]['adx_phase'],ad);self.assertEqual(ee[0]['bbwp_phase'],bb)
    def test_two_hour_window_and_expiry(self):
        x=np.array([4,3,2,3,4,5,6,7.]);y=np.array([7,6,5,4,3,4,5,6.]);f=features(dict(ao=x,minnows=y,adx=y,bbwp=y))
        ee,_=detector.detect(bars(8),f);self.assertEqual([e['i'] for e in ee],[5])
        z=np.array([8,7,6,5,4,3,4,5.]);f=features(dict(ao=x,minnows=z,adx=z,bbwp=z))
        self.assertEqual(detector.detect(bars(8),f)[0],[])
    def test_no_persistent_duplicate(self):
        f=features({'ao':np.r_[3,2,1,np.arange(2,12)]});ee,_=detector.detect(bars(13),f);self.assertEqual(len(ee),1)
    def test_disagreement_no_signal_and_gap_reset(self):
        x=np.array([3,2,1,2,3.]);f=features(dict(ao=x,minnows=-x));self.assertEqual(detector.detect(bars(5),f)[0],[])
        f=features({'ao':x});a=bars(5);a[3:,0]+=H;self.assertEqual(detector.detect(a,f)[0],[])
    def test_prefix_invariance(self):
        x=np.sin(np.arange(30)/2);f=features({'ao':x});a=bars(30);full=detector.detect(a,f)[0]
        for n in range(3,30):self.assertEqual(detector.detect(a[:n],{k:v[:n] for k,v in f.items()})[0],[e for e in full if e['i']<n])
    def test_no_context_filter(self):
        f=features({'ao':np.array([3,2,1,2,3.])});f['regime4h'][:]=np.nan;f['regime1d'][:]=-1
        self.assertEqual(len(detector.detect(bars(5),f)[0]),1)
    def test_fresh_second_bundle_no_hidden_25h_cooldown(self):
        x=np.array([3,2,1,2,3,2,1,2,3.]);f=features({'ao':x});ee,_=detector.detect(bars(9),f)
        self.assertEqual([e['i'] for e in ee],[3,5,7])

class ExecutionTests(unittest.TestCase):
    def test_initial_stop_matches_planned_net_R(self):
        a=bars();a[1,3]=98
        t=execute(a)['trades'][0];self.assertAlmostEqual(t['net_R'],-1);self.assertEqual(t['exit_kind'],'INITIAL_STOP')
    def test_gap_is_adverse_not_guaranteed_stop(self):
        a=bars();a[2,1:5]=[97,98,96,97]
        t=execute(a)['trades'][0];self.assertLess(t['net_R'],-1);self.assertEqual(t['gaps'],1);self.assertEqual(t['fills'][-1]['reference'],97)
    def test_tp1_50_percent_and_BE_net_costs(self):
        a=bars();a[1,2]=101;a[2,1:5]=[100.5,100.5,100,100.1]
        t=execute(a)['trades'][0];self.assertTrue(t['tp1']);self.assertEqual(t['exit_kind'],'BE_STOP')
        self.assertAlmostEqual(t['fills'][0]['qty'],t['qty']/2);self.assertAlmostEqual(sum(x['qty'] for x in t['fills']),t['qty'])
        p=t['fills'][-1];remaining_net=t['qty']/2*(p['fill']-t['entry_fill'])-t['entry_fee']/2-p['fee'];self.assertAlmostEqual(remaining_net,0,places=8)
    def test_BE_not_active_inside_TP1_bar(self):
        a=bars();a[1,2:5]=[101,99.8,100.0];a[2,1:5]=[100.1,100.2,99.9,100]
        t=execute(a)['trades'][0];self.assertEqual(t['exit_i'],2);self.assertEqual(t['fills'][-1]['reference'],100.1)
    def test_trailing_ratchet_next_hour(self):
        a=bars();a[1,2:5]=[104,99.8,103.8];a[2,1:5]=[103.5,103.8,102,103]
        t=execute(a)['trades'][0];self.assertEqual(t['exit_kind'],'TRAIL_STOP');self.assertGreater(t['net'],0)
    def test_short_partial_BE_direction(self):
        a=bars();a[1,3]=99;a[2,1:5]=[99.5,100,99.3,99.8]
        t=execute(a,-1)['trades'][0];self.assertTrue(t['tp1']);self.assertEqual(t['exit_kind'],'BE_STOP');self.assertGreater(t['net'],0)
    def test_h1_both_stop_first(self):
        a=bars();a[1,2:4]=[101,98]
        t=execute(a)['trades'][0];self.assertFalse(t['tp1']);self.assertEqual(t['ambiguous_h1'],1)
    def make_minutes(self,a,stop_first=False,same=False):
        m=np.tile(a[1],(60,1));m[:,0]=a[1,0]+np.arange(60)*60000;m[:,1:5]=100;m[:,5]=1
        m[0,1:5]=[100,101,98 if same else 99.5,100]
        m[1,1:5]=[100,100,98,100]
        if stop_first:m[0,1:5]=[100,100,98,100];m[1,1:5]=[100,101,100,100]
        return Minutes(m,a)
    def test_minutes_resolve_target_then_stop(self):
        a=bars();a[1,2:4]=[101,98]
        t=execute(a,minutes=self.make_minutes(a))['trades'][0];self.assertTrue(t['tp1']);self.assertEqual(t['resolved_m1'],1);self.assertEqual(t['ambiguous_h1'],0)
    def test_minutes_stop_then_target_never_claims_TP(self):
        a=bars();a[1,2:4]=[101,98]
        t=execute(a,minutes=self.make_minutes(a,True))['trades'][0];self.assertFalse(t['tp1']);self.assertAlmostEqual(t['net_R'],-1)
    def test_same_minute_ambiguous_stop_first(self):
        a=bars();a[1,2:4]=[101,98]
        t=execute(a,minutes=self.make_minutes(a,same=True))['trades'][0];self.assertFalse(t['tp1']);self.assertEqual(t['ambiguous_m1'],1);self.assertEqual(t['resolved_m1'],0)
    def test_mismatching_minute_hour_not_used(self):
        a=bars();a[1,2:4]=[101,98];tape=self.make_minutes(a);tape.good.clear()
        t=execute(a,minutes=tape)['trades'][0];self.assertEqual(t['ambiguous_h1'],1)
    def test_capital_constraint_does_not_fake_constant_risk(self):
        a=bars();r=run(a,np.empty((0,6)),np.full(len(a),.01),[signal()],Config(.005,1.5,.01))
        self.assertEqual(r['summary']['counts']['leverage_required'],1);self.assertEqual(r['trades'],[]);self.assertEqual(r['summary']['ending_equity'],10000)
    def test_one_position_no_flip_or_reentry_in_exit_bar(self):
        a=bars();a[2,1:5]=[97,98,96,97]
        r=run(a,np.empty((0,6)),np.ones(len(a)),[signal(),signal(1,-1)],Config(.005,1.5,.005))
        self.assertEqual(len(r['trades']),1);self.assertEqual(r['opportunities'][1]['decision'],'POSITION_OPEN')
    def test_funding_remaining_quantity_and_delayed_cash(self):
        a=bars(10);a[1,2]=101;a[1,4]=100.8;a[2:,1:5]=[101,101.1,100.8,101]
        ff=np.array([[a[1,0],.0001,100,8,99,101],[a[2,0],.0001,100,8,99,101]])
        r=run(a,ff,np.ones(len(a)),[signal()],Config(.005,1.5,.005));t=r['trades'][0]
        self.assertAlmostEqual(t['funding_high'],t['qty']*.01*1.5);self.assertLess(t['net'],t['net_upper'])
    def test_future_mark_bounds_cannot_change_entry_or_TP1_fill(self):
        a=bars();a[1,2]=101
        results=[]
        for hi in (110,200):
            ff=np.array([[a[1,0],.001,np.nan,8,90,hi]])
            results.append(run(a,ff,np.ones(len(a)),[signal()],Config(.005,1.5,.005)))
        t,u=[r['trades'][0] for r in results];self.assertEqual(t['qty'],u['qty']);self.assertEqual(t['fills'][0],u['fills'][0]);self.assertGreater(u['funding_high'],t['funding_high'])
    def test_no_future_ATR_for_initial_stop(self):
        a=bars();a[1,3]=98;atr=np.ones(len(a));atr[1:]=100
        t=run(a,np.empty((0,6)),atr,[signal()],Config(.005,1.5,.005))['trades'][0];self.assertAlmostEqual(t['net_R'],-1)
    def test_cash_ledger_losing_sequence_no_reset(self):
        a=bars(8);a[1,3]=98;a[3,3]=98;a[5,3]=98
        r=run(a,np.empty((0,6)),np.ones(len(a)),[signal(0),signal(2),signal(4)],Config(.005,1.5,.01))
        self.assertAlmostEqual(r['summary']['ending_equity'],10000*.99**3);self.assertEqual(r['summary']['max_losing_streak'],3)
    def test_forced_end_and_no_new_scenarios(self):
        self.assertEqual(execute(bars())['trades'][0]['exit_kind'],'END_OF_DATA')
        with self.assertRaises(ValueError):Config(.03,1.5,.005)
    def test_reproducible(self):
        self.assertEqual(execute(bars()),execute(bars()))
    def test_unknown_funding_is_not_zero(self):
        a=bars();fund=np.array([[a[1,0],.001,np.nan,8,np.nan,np.nan]])
        with self.assertRaisesRegex(ValueError,'FUNDING'):run(a,fund,np.ones(len(a)),[signal()],Config(.005,1.5,.005))
    def test_stops_never_widen_after_TP1(self):
        a=bars(6);a[1,2:5]=[101,99.8,100.8];a[2:,1:5]=[101,101.1,100.8,101]
        t=execute(a)['trades'][0];levels=[r['level'] for r in t['stop_updates']]
        self.assertTrue(all(x<=y for x,y in zip(levels,levels[1:])))
    def test_duplicate_reference_collision_counts_both(self):
        a=bars();r=run(a,np.empty((0,6)),np.ones(len(a)),[signal(),signal(side=-1)],Config(.005,1.5,.005))
        self.assertEqual(r['summary']['counts']['collision'],2);self.assertEqual(r['trades'],[])

class ReferenceTests(unittest.TestCase):
    def test_inclusive_matched_reference_deterministic(self):
        from .study import reference
        cell=[('2023-01',1,0)]*10;ss=[signal(0),signal(3,-1),signal(6)]
        x=reference(ss,np.arange(10),cell,5);self.assertEqual(x,reference(ss,np.arange(10),cell,5))
        self.assertEqual(sum(s['side']==1 for s in x),2);self.assertEqual(sum(s['side']==-1 for s in x),1)
        # Full-census sampling is allowed: event hours are not excluded.
        allrows=reference([signal(i) for i in range(10)],np.arange(10),cell,7)
        self.assertEqual([s['i'] for s in allrows],list(range(10)))

class Boundaries(unittest.TestCase):
    def test_plan_byte_identity_pre_result_commit(self):
        root=detector.HERE.parents[7];name=(detector.HERE/'plan.json').relative_to(root).as_posix()
        old=subprocess.check_output(['git','show','3be6d30:'+name],cwd=root)
        self.assertEqual(old.replace(b'\r\n',b'\n'),(detector.HERE/'plan.json').read_bytes().replace(b'\r\n',b'\n'))
    def test_no_execution_or_observer_or_transport_import(self):
        root=detector.HERE.parents[7]
        for p in detector.HERE.glob('*.py'):
            if p.name.startswith('test_'):continue
            for node in ast.walk(ast.parse(p.read_text())):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    text=ast.get_source_segment(p.read_text(),node)
                    for name in ('requests','socket','http.client','guardian','v8_executor','live_auto','weekly_forward','Observer','Telegram'):self.assertNotIn(name,text)
        for name in subprocess.check_output(['git','ls-files','--','*.py'],cwd=root,text=True).splitlines():
            if name.startswith('research/') or Path(name).name.startswith('test_'):continue
            self.assertNotIn('swing_capture',(root/name).read_text('utf-8-sig'))

if __name__=='__main__':unittest.main()
