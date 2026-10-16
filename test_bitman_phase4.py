"""Offline tests of sequence causality, exits, costs, selection and isolation."""
import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import numpy as np
from research.bitman_phase4 import core,ledger
from research.bitman_phase4.spec import Candidate,candidates,BASE_SHA,HOUR
from research.bitman_phase4.telegram import render


def prices(n=3000,start=1577836800000):
    rng=np.random.default_rng(912);c=100*np.exp(np.cumsum(rng.normal(0,.005,n)));o=np.r_[c[0],c[:-1]];v=np.ones(n)*100
    return np.column_stack([start+np.arange(n)*HOUR,o,np.maximum(o,c)*1.003,np.minimum(o,c)*.997,c,v,v*.5])


def features(n=12):
    ao=np.r_[-2.,-1.,np.arange(1,n-1.)]
    f={k:np.ones(n) for k in ('atr','adx','bbwp_slope','mountain','sep_expanding')}
    f.update(ao=ao,ao_slope=np.r_[np.nan,np.diff(ao)],adx_slope=np.r_[-np.ones(5),np.ones(n-5)],
        di_plus=np.ones(n)*20,di_minus=np.ones(n)*10,bbwp=np.ones(n)*50,inside=np.ones(n,bool),
        k_entry=np.zeros(n,bool),k_exit=np.zeros(n,bool),entry_age=np.arange(n),exit_age=np.arange(n),
        reentry_age={w:np.arange(n) for w in (2,3,5)},mountain_slope=np.ones(n))
    f['k_entry'][0]=True
    return f


class SequenceTests(unittest.TestCase):
    def test_ao_zero_cross_long(self):self.assertTrue(core.anchors(features(),1)[1][2])
    def test_ao_zero_cross_short(self):
        f=features();f['ao']=-f['ao'];f['ao_slope']=-f['ao_slope'];self.assertTrue(core.anchors(f,-1)[1][2])
    def test_resume_needs_reset(self):
        f=features();f['ao']=np.array([1.,2.,3.,2.,1.,2.,3.,4.,5.,6.,7.,8.]);f['ao_slope']=np.r_[np.nan,np.diff(f['ao'])]
        self.assertEqual(np.flatnonzero(core.anchors(f,1)[2]).tolist(),[5])
    def test_no_anchor_each_rising_bar(self):self.assertEqual(int(core.anchors(features(),1)[0].sum()),1)
    def test_adx_lag_after_cross(self):
        mask,meta=core.sequence(features(),1,6);self.assertEqual(np.flatnonzero(mask).tolist(),[5]);self.assertEqual(meta['anchor_age'][5],3)
    def test_adx_before_anchor_not_accepted(self):
        f=features();f['adx_slope'][:]=1.;self.assertFalse(core.sequence(f,1,6)[0].any())
    def test_lag_window_inclusive(self):
        self.assertFalse(core.sequence(features(),1,2)[0].any());self.assertTrue(core.sequence(features(),1,3)[0][5])
    def test_adx_turn_then_di_align(self):
        f=features();f['di_plus'][5]=0.;mask,meta=core.sequence(f,1,6)
        self.assertTrue(mask[6]);self.assertEqual(meta['after_adx_turn'][6],1)
    def test_non_improving_momentum_not_trigger(self):
        f=features();f['ao_slope'][5]=-1.;self.assertFalse(core.sequence(f,1,6)[0][5])
    def test_anchor_consumed_once(self):self.assertEqual(int(core.sequence(features(),1,9)[0].sum()),1)
    def test_opposite_ao_invalidates_anchor(self):
        f=features();f['ao'][4:]=-1.;f['ao_slope']=np.r_[np.nan,np.diff(f['ao'])]
        self.assertFalse(core.sequence(f,1,6)[0].any())
    def test_short_uses_rising_adx_and_bearish_di(self):
        f=features();f['ao']=-f['ao'];f['ao_slope']=-f['ao_slope'];f['di_plus'],f['di_minus']=f['di_minus'],f['di_plus']
        self.assertTrue(core.entry(f,Candidate(),-1)[0][5])
    def test_bbwp_rising_gate(self):
        f=features();f['bbwp_slope'][5]=0.;self.assertFalse(core.entry(f,Candidate(),1)[0][5])
    def test_50_fixed_reference_equality(self):
        f=features();p=Candidate('C1_BBWP50');self.assertTrue(core.entry(f,p,1)[0][5])
        f['bbwp'][5]=49.99;self.assertFalse(core.entry(f,p,1)[0][5])
    def test_k_long_inside_positive(self):
        f=features();self.assertTrue(core.entry(f,Candidate('C2_K_CONTEXT'),1)[0][5])
        f['inside'][5]=False;self.assertFalse(core.entry(f,Candidate('C2_K_CONTEXT'),1)[0][5])
    def test_short_k_is_exit_fade_not_inverted_inside(self):
        f=features();f['ao']=-f['ao'];f['ao_slope']=-f['ao_slope'];f['di_plus'],f['di_minus']=f['di_minus'],f['di_plus']
        f['inside'][:]=False;f['mountain_slope'][:]=-1.
        self.assertTrue(core.entry(f,Candidate('C2_K_CONTEXT'),-1)[0][5])
        f['mountain_slope'][5]=1.;self.assertFalse(core.entry(f,Candidate('C2_K_CONTEXT'),-1)[0][5])
    def test_unsupported_short_geometry_rejected(self):
        for family in ('C4_K_SEPARATION','C5_K_REENTRY'):
            with self.assertRaises(ValueError):core.entry(features(),Candidate(family),-1)
    def test_family_counts_small(self):self.assertEqual((len(candidates(1)),len(candidates(-1))),(6,4))
    def test_ablation_adx_drops_turn_and_di(self):
        f=features();f['adx_slope'][:]=-1.;f['di_plus'][:]=0.;f['adx'][:]=np.nan
        self.assertFalse(core.entry(f,Candidate(),1)[0].any());self.assertTrue(core.entry(f,Candidate(),1,'ADX_DI')[0][2])
    def test_ablation_ao_no_anchor_needed(self):
        f=features();f['ao'][:]=np.nan;f['ao_slope'][:]=np.nan
        self.assertTrue(core.entry(f,Candidate(),1,'AO')[0][5])
    def test_ablation_bb_removes50_and_validity(self):
        f=features();f['bbwp'][:]=np.nan;f['bbwp_slope'][:]=np.nan
        self.assertTrue(core.entry(f,Candidate('C1_BBWP50'),1,'BBWP')[0][5])
    def test_ablation_k_removes_geometry_only(self):
        f=features();f['inside'][:]=False
        self.assertFalse(core.entry(f,Candidate('C2_K_CONTEXT'),1)[0].any())
        self.assertTrue(core.entry(f,Candidate('C2_K_CONTEXT'),1,'KONKORDE')[0][5])
    def test_sequence_prefix(self):
        f=features(30);all_=core.sequence(f,1,6)[0];prefix={k:({w:v[:8] for w,v in a.items()} if isinstance(a,dict) else a[:8]) for k,a in f.items()}
        np.testing.assert_array_equal(all_[:8],core.sequence(prefix,1,6)[0])


class CausalityTests(unittest.TestCase):
    def test_closed_frames_1h_4h(self):
        a=prices();now=int(a[-2,0]+HOUR)
        for tf in ('1H','4H'):
            f=core.prepare(a,tf,now);self.assertTrue(np.all(f['closes']<=now))
    def test_all_feature_prefix(self):
        a=prices();now=int(a[-1,0]+HOUR);cut=int(a[2499,0]+HOUR)
        for tf in ('1H','4H'):
            full=core.prepare(a,tf,now);past=core.prepare(a[:2500],tf,cut);n=len(past['close'])
            for key in ('ao','adx','bbwp','mountain','ma','h4_trend','day_trend','ao_bull_div'):
                np.testing.assert_allclose(full[key][:n],past[key],equal_nan=True)
            for side in (1,-1):
                for p in candidates(side):np.testing.assert_array_equal(core.entry(full,p,side)[0][:n],core.entry(past,p,side)[0])
    def test_confirmed_daily_alignment(self):
        out=core.align(np.array([0.]),np.array([1.]),24*HOUR,np.array([23*HOUR,24*HOUR]));self.assertTrue(np.isnan(out[0]));self.assertEqual(out[1],1.)
    def test_divergence_confirmed_not_backdated(self):
        a=prices(15,start=0);a[:,3]=10.;a[3,3]=5.;a[8,3]=4.;ao=np.zeros(15);ao[3]=-4;ao[8]=-2
        bull,_=core.divergence(a,ao);self.assertFalse(bull[8]);self.assertTrue(bull[10])
        self.assertFalse(core.divergence(a[:10],ao[:10])[0].any())
    def test_entry_maps_next_tf_open(self):
        a=prices(12,start=0);f=dict(closes=np.array([4*HOUR,8*HOUR]),ao=np.array([1.,-1.]),atr=np.array([2.,3.]))
        entry,opposite,atr=core.hourly_inputs(a,f,np.array([True,False]),1)
        self.assertEqual(np.flatnonzero(entry).tolist(),[4]);self.assertFalse(opposite[7]);self.assertTrue(opposite[8]);self.assertEqual(atr[4],2.)
    def test_1d_only_context(self):
        from research.bitman_phase4.spec import TIMEFRAMES
        self.assertEqual(set(TIMEFRAMES),{'1H','4H'})


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.a=prices(5,start=0);self.a[:,1:5]=[100,100.5,99.5,100.]
        self.e=np.array([False,True,False,False,False]);self.o=np.zeros(5,bool);self.atr=np.ones(5)
        self.zero=dict(fee_bps=0,slip_bps=0,stop_slip_bps=0)
    def run_case(self,**kwargs):
        params=dict(bars=self.a,funding=np.empty((0,2)),entries=self.e,opposite=self.o,atr=self.atr,side=1,start=0,end=5*HOUR,costs=self.zero)
        params.update(kwargs);return ledger.simulate(**params)
    def test_no_earlier_entry(self):self.assertEqual(self.run_case()['trades'][0]['entry_time'],HOUR)
    def test_fees_both_fills(self):
        r=self.run_case(costs=dict(fee_bps=5,slip_bps=0,stop_slip_bps=0));self.assertAlmostEqual(r['metrics']['total_return'],-.001)
    def test_adverse_slippage(self):
        r=self.run_case(costs=dict(fee_bps=0,slip_bps=10,stop_slip_bps=0));t=r['trades'][0]
        self.assertEqual(t['entry_fill'],100.1);self.assertEqual(t['exit_fill'],99.9)
    def test_signed_historical_funding(self):
        f=np.array([[2*HOUR,.01]])
        self.assertAlmostEqual(self.run_case(funding=f)['metrics']['total_return'],-.01)
        self.assertAlmostEqual(self.run_case(funding=f,side=-1)['metrics']['total_return'],.01)
    def test_funding_before_new_entry_not_charged(self):
        self.assertAlmostEqual(self.run_case(funding=np.array([[HOUR,.01]]))['metrics']['total_return'],0.)
    def test_future_funding_ignored(self):
        self.assertEqual(self.run_case()['metrics'],self.run_case(funding=np.array([[20*HOUR,1.]]))['metrics'])
    def test_stop_gap_adverse(self):
        self.a[2,1:5]=[95,96,94,95]
        t=self.run_case(costs=dict(fee_bps=0,slip_bps=0,stop_slip_bps=10))['trades'][0]
        self.assertEqual(t['exit_reason'],'gap_stop');self.assertAlmostEqual(t['exit_fill'],95*.999)
    def test_stop_long_short(self):
        self.a[2,2]=103;self.a[2,3]=97
        self.assertEqual(self.run_case()['trades'][0]['exit_fill'],98.)
        self.assertEqual(self.run_case(side=-1)['trades'][0]['exit_fill'],102.)
    def test_opposite_at_open(self):
        self.o[2]=True;self.assertEqual(self.run_case()['trades'][0]['exit_time'],2*HOUR)
    def test_no_pyramid(self):self.assertEqual(self.run_case(entries=np.ones(5,bool))['metrics']['trades'],1)
    def test_no_samebar_reentry(self):
        self.o[2]=True;r=self.run_case(entries=np.array([False,True,True,False,False]));self.assertEqual(r['metrics']['trades'],1)
    def test_atr_frozen_after_entry(self):
        self.atr[2:]=100.;self.a[3,3]=97
        self.assertEqual(self.run_case()['trades'][0]['exit_fill'],98.)
    def test_trail_only_next_bar(self):
        self.a[1,2]=110.;self.a[1,3]=99.;t=self.run_case(trailing=True)['trades'][0]
        self.assertEqual(t['exit_time'],2*HOUR);self.assertEqual(t['exit_reason'],'gap_stop')
    def test_split_forces_flat(self):self.assertEqual(self.run_case()['trades'][0]['exit_reason'],'split_end')
    def test_removal_without_reentry(self):
        r=self.run_case();self.assertEqual(ledger.removal(r,1)['trades'],0)
    def test_bootstrap_deterministic(self):self.assertEqual(ledger.bootstrap(self.run_case()),ledger.bootstrap(self.run_case()))
    def test_insolvency_recorded(self):
        r=self.run_case(funding=np.array([[2*HOUR,2.]]));self.assertTrue(r['metrics']['insolvent']);self.assertEqual(r['trades'][0]['net_return'],-1.)
    def test_metrics_and_trades_json_serializable(self):
        r=self.run_case();json.dumps(dict(metrics=r['metrics'],trades=r['trades']),allow_nan=False)
    def test_stress_never_reduces_costs(self):
        self.assertLess(self.run_case(costs=ledger.STRESS_COSTS)['metrics']['total_return'],self.run_case(costs=ledger.BASE_COSTS)['metrics']['total_return'])


class SelectionAndSafetyTests(unittest.TestCase):
    def test_frozen_protocol_source_and_manifest(self):
        from research.bitman_phase4.study import check
        check()
    def test_development_data_ends_before_test(self):
        from research.bitman_phase4.study import ART,SPLITS
        lock=json.loads((ART/'selection_lock.json').read_text())
        self.assertEqual(lock['development_last_closed'],SPLITS['TEST'][0])
        for s in lock['selection'].values():
            self.assertEqual(set(s['strategy_development']),{'TRAIN','VALIDATION'})
            for row in s['event_development_rows']:
                self.assertNotIn('TEST',row)
    def test_event_lock_precedes_net_check_and_matches_frozen_parents(self):
        from research.bitman_phase4.study import ART,digest
        event=json.loads((ART/'event_lock.json').read_text());net=json.loads((ART/'selection_lock.json').read_text())
        self.assertEqual(net['event_lock_sha256'],digest(ART/'event_lock.json'))
        for key,s in event['selection'].items():
            self.assertNotIn('strategy_development',s)
            self.assertEqual(s['selected'],net['selection'][key]['selected'])
    def test_test_cannot_replace_frozen_parent(self):
        from research.bitman_phase4.study import ART
        r=json.loads((ART/'results.json').read_text());lock=json.loads((ART/'selection_lock.json').read_text())
        for key,s in r['selected'].items():self.assertEqual(s['parameters'],lock['selection'][key]['selected'])
    def test_v8_common_ledger_identical_across_signal_timeframes(self):
        from research.bitman_phase4.study import ART
        r=json.loads((ART/'results.json').read_text())
        self.assertEqual(r['comparators']['1H_1']['V8'],r['comparators']['4H_1']['V8'])
    def test_walk_forward_selection_cutoff_is_prior_to_tested_year(self):
        from research.bitman_phase4.study import ART,stamp
        r=json.loads((ART/'results.json').read_text())
        for year,fold in r['walk_forward'].items():
            for row in fold.values():self.assertEqual(row['selection_cutoff'],stamp(year+'-01-01T00:00:00Z'))
    def test_vidiq_only_four_authorized_transcript_calls(self):
        from research.bitman_phase4.study import ART
        r=json.loads((ART/'primary_sources.json').read_text())
        self.assertEqual(len(r['videos']),4);self.assertEqual(r['authorization']['transcript_calls'],4)
        self.assertLessEqual(r['authorization']['nominal_total'],r['authorization']['maximum_credits'])
        self.assertIsNone(r['authorization']['actual_billed_credits'])
        for video in r['videos'].values():self.assertNotIn('transcription',video)
    def test_source_identity_and_capability_audit(self):
        from research.bitman_phase4.safety import audit
        r=audit();self.assertEqual(r['status'],'PASS');self.assertFalse(r['trade_authority']);self.assertFalse(r['order_capability'])
    def test_short_directional_mfe_mae_and_return(self):
        from research.bitman_phase4.study import directional
        from research.bitman_real.outcomes import measure
        a=prices(3,start=0);a[:,1:5]=[100,103,96,98]
        raw=measure(a,0,100,1,3*HOUR);s=directional(raw,-1)
        self.assertAlmostEqual(s['forward_return'],.02);self.assertAlmostEqual(s['mfe'],.04);self.assertAlmostEqual(s['mae'],-.03)
        self.assertEqual(raw['forward_return'],-.020000000000000018)
    def test_short_first_passage_mirrored_conservatively(self):
        from research.bitman_phase4.study import directional
        r=dict(complete=True,forward_return=.02,mfe=.03,mae=-.01,first_up1_hour=1,first_down1_hour=2,first_up2_hour=1,first_down2_hour=None,race_1pct='UP_FIRST',race_2pct='AMBIGUOUS')
        s=directional(r,-1);self.assertEqual(s['race_1pct'],'DOWN_FIRST');self.assertEqual(s['race_2pct'],'AMBIGUOUS');self.assertEqual(s['first_up1_hour'],2)
    def test_pending_horizon_not_turned_into_success(self):
        from research.bitman_phase4.study import directional
        from research.bitman_real.outcomes import measure
        r=measure(prices(3,start=0),0,100,4,3*HOUR)
        self.assertFalse(r['complete']);self.assertEqual(directional(r,-1),r)
    def test_missing_market_gap_censored(self):
        from research.bitman_real.outcomes import measure
        a=prices(5,start=0);self.assertFalse(measure(a[[0,2,3,4]],0,100,4,5*HOUR)['complete'])
    def test_test_cannot_select(self):
        from research.bitman_phase4.study import eligible,rank
        row={p:dict(matched24h=dict(n=40,mean=.01),directional24h_mean=.02) for p in ('TRAIN','VALIDATION')}
        row['TEST']=dict(profit=100);before=rank(row);row['TEST']['profit']=-9999
        self.assertTrue(eligible(row));self.assertEqual(rank(row),before)
    def test_no_parameter_grid(self):
        from research.bitman_phase4.spec import protocol
        self.assertEqual(sum(len(x) for x in protocol()['candidates'].values()),10)
    def test_bbwp_neighbors_diagnostic_not_candidate_search(self):
        from research.bitman_phase4.study import neighbors
        self.assertEqual([p.bb_reference for p in candidates(1) if p.family=='C1_BBWP50'],[50.])
        self.assertIn(40.,[p.bb_reference for p in neighbors(Candidate('C1_BBWP50'),1)])
    def test_original_pr23_every_file_unchanged(self):
        files=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',BASE_SHA],text=True).splitlines()
        for path in files:
            old=subprocess.check_output(['git','show',BASE_SHA+':'+path]);new=Path(path).read_bytes()
            self.assertEqual(old.replace(b'\r\n',b'\n'),new.replace(b'\r\n',b'\n'),path)
    def test_no_network_or_trading_capabilities(self):
        for p in Path('research/bitman_phase4').glob('*.py'):
            source=p.read_text(encoding='utf-8');tree=ast.parse(source)
            for node in ast.walk(tree):
                modules=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                self.assertFalse(any(x.split('.')[0] in ('requests','httpx','socket','guardian_bitunix','trade_guardian','v8_executor','live_auto','main') for x in modules))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):self.assertNotIn(node.func.attr,('post','getUpdates','place_order','place_market','flash_close_position','change_leverage','withdraw','transfer'))
            self.assertNotIn('BITUNIX_API_',source)
    def test_no_http_from_render_or_sim(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('HTTP FORBIDDEN')) as network:
            for state in ('LONG','SHORT','FORMING','WAIT','BLOCKED'):render(dict(state=state))
            network.assert_not_called()
    def test_grades_not_indicator_vote_or_sizing(self):
        s=render(dict(state='LONG',grade='A',research_classification='INCONCLUSIVE'))
        self.assertIn('GRADE: C',s);self.assertNotIn('GRADE: A',s);self.assertIn('NO controla sizing',s)
    def test_no_forward_grade_a(self):
        s=render(dict(state='SHORT',research_classification='PROMISING FOR SHADOW'))
        self.assertIn('GRADE: B',s);self.assertIn('TRADE AUTHORITY: NONE',s)
    def test_renderer_all_states(self):
        for state in ('LONG','SHORT','FORMING','WAIT','BLOCKED'):
            s=render(dict(state=state));self.assertIn('BITMAN '+state,s)
            self.assertIn('PRIVATE / PARITY NOT PROVEN',s);self.assertIn('FORMULA NOT VERIFIED',s);self.assertIn('SHADOW ONLY',s)


if __name__=='__main__':unittest.main()
