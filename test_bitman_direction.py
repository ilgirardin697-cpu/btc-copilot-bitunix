"""Offline directional, causal, read-only boundary and safety regressions."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from research.bitman_direction import core,levels,evaluation as ev,confirmed,noise
from research.bitman_direction.spec import HOUR,BASE_SHA,MLRSI_CONFIG,protocol
from research.bitman_direction.observer import DirectionObserver
from research.bitman_direction.telegram import render
from guardian_signals import confirmed_level_scale


def prices(n=4000,start=1577836800000):
    rng=np.random.default_rng(662);c=100*np.exp(np.cumsum(rng.normal(0,.004,n)));o=np.r_[c[0],c[:-1]]
    return np.column_stack([start+np.arange(n)*HOUR,o,np.maximum(o,c)*1.003,np.minimum(o,c)*.997,c,np.ones(n)*100,np.ones(n)*50])


def components(d='UP',h='UP',timer='UP'):
    def part(b):return dict(bias=b,ao_bias=b,momentum='BULLISH_MOMENTUM' if b=='UP' else 'BEARISH_MOMENTUM' if b=='DOWN' else 'MIXED',
        di_direction='BULLISH' if b=='UP' else 'BEARISH' if b=='DOWN' else 'NEUTRAL',adx_slope=1.,bbwp_slope=1.,adx_turn_up=True)
    return {'1D':part(d),'4H':part(h),'1H':part(timer)}


def ml_export(now):
    def frame(interval):return dict(observation=dict(last_closed_timestamp=now//interval*interval,last_successful_read=now,fresh=True,
        confirmed_color='GREEN',latest_confirmed_values=dict(color='GREEN',valid=True,mlrsi_smoothed=60.,upper_threshold=55.,lower_threshold=45.),
        latest_provisional_values=dict(color='RED'),approaching_state='APPROACHING_RED'))
    return dict(config_version=MLRSI_CONFIG,symbol='BTCUSDT',venue='BINANCE_SPOT',trade_authority=False,shadow_only=True,
        timeframes={'1h':frame(HOUR),'4h':frame(4*HOUR)})


class HierarchyTests(unittest.TestCase):
    def test_macro_swing_up_timing_up(self):self.assertEqual(core.decide(components())['detail'],'UP_CONFIRMED')
    def test_macro_swing_down(self):self.assertEqual(core.decide(components('DOWN','DOWN','DOWN'))['state'],'DOWN')
    def test_hourly_down_is_pullback_not_macro_reversal(self):
        s=core.decide(components('UP','UP','DOWN'));self.assertEqual(s['state'],'UP');self.assertEqual(s['timing_state'],'pullback');self.assertEqual(s['pullback_direction'],'DOWN')
    def test_hourly_up_pullback_in_macro_down(self):self.assertEqual(core.decide(components('DOWN','DOWN','UP'))['detail'],'DOWN_WITH_1H_PULLBACK')
    def test_bullish_transition(self):self.assertEqual(core.decide(components('DOWN','UP','UP'))['detail'],'POSSIBLE_BULLISH_TRANSITION')
    def test_bearish_transition(self):self.assertEqual(core.decide(components('UP','DOWN','DOWN'))['state'],'TRANSITION')
    def test_disagreeing_swing_without_supporting_timing_is_conflict(self):self.assertEqual(core.decide(components('UP','DOWN','UP'))['state'],'CONFLICT')
    def test_missing_daily_not_overruled_by_two_lower_frames(self):self.assertEqual(core.decide(components('UNKNOWN','UP','UP'))['state'],'UNCLEAR')
    def test_adx_magnitude_cannot_assign_direction(self):
        p=components()
        for f in p.values():f['adx_slope']=-10.;f['adx_turn_up']=False
        self.assertEqual(core.decide(p)['state'],'UP');self.assertEqual(core.decide(p)['strength'],'WEAK')
    def test_strength_requires_both_contexts_for_strong(self):
        p=components();self.assertEqual(core.decide(p)['strength'],'STRONG');p['1D']['bbwp_slope']=-1.
        self.assertEqual(core.decide(p)['strength'],'BUILDING')
    def test_grade_not_size_or_probability(self):
        self.assertEqual(core.decide(components())['evidence_grade'],'B')
        self.assertEqual(core.decide(components(),ml={'4H':{'color':'GREEN'}})['evidence_grade'],'A')
    def test_neutral_ml_no_confirmation(self):self.assertEqual(core.decide(components(),ml={'4H':{'color':'NEUTRAL'}})['mlrsi_confirmation'],'NEUTRAL')
    def test_opposite_confirmed_ml_conflict(self):self.assertEqual(core.decide(components(),ml={'4H':{'color':'RED'}})['state'],'CONFLICT')
    def test_major_resistance_test_is_conflict(self):self.assertEqual(core.decide(components(),{'opposing_up':True,'opposing_down':False})['state'],'CONFLICT')
    def test_major_support_down_conflict(self):self.assertEqual(core.decide(components('DOWN','DOWN','DOWN'),{'opposing_up':False,'opposing_down':True})['state'],'CONFLICT')
    def test_missing_levels_do_not_invent_permission(self):self.assertTrue(core.decide(components())['state']=='UP')
    def test_ao_only_ablation_drops_di_from_timing(self):
        p=components();p['1H']['di_direction']='BEARISH';self.assertEqual(core.decide(p,ao_only=True)['detail'],'UP_CONFIRMED')


class CausalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=prices();cls.now=int(cls.a[-1,0]+HOUR);cls.data=core.prepare(cls.a,cls.now)
    def test_only_closed_frames(self):
        for tf,f in self.data['frames'].items():self.assertTrue(np.all(f['closes']<=self.now))
    def test_open_hour_cannot_change_confirmed(self):
        changed=self.a.copy();changed[-1,1:5]*=2;now=int(self.a[-1,0]+HOUR/2)
        one=core.prepare(self.a,now);two=core.prepare(changed,now)
        np.testing.assert_array_equal(core.series(one)['state'],core.series(two)['state'])
    def test_feature_prefix_invariance(self):
        cut=3300;p=core.prepare(self.a[:cut],int(self.a[cut-1,0]+HOUR))
        for tf in ('1H','4H','1D'):
            n=len(p['frames'][tf]['frame'])
            for field in ('ao','adx','bbwp','mountain','ma','ao_acceleration','bbwp_acceleration'):
                np.testing.assert_allclose(self.data['frames'][tf]['features'][field][:n],p['frames'][tf]['features'][field],equal_nan=True)
    def test_state_and_structure_prefix_invariant(self):
        cut=3300;p=core.prepare(self.a[:cut],int(self.a[cut-1,0]+HOUR))
        np.testing.assert_array_equal(core.series(self.data)['state'][:cut],core.series(p)['state'])
        self.assertEqual(core.snapshot(self.data,cut-1),core.snapshot(p,cut-1))
    def test_daily_available_after_close_only(self):
        values=core.align(np.array([0.]),np.array([9.]),24*HOUR,np.array([23*HOUR,24*HOUR]));self.assertTrue(np.isnan(values[0]));self.assertEqual(values[1],9.)
    def test_single_ao_slope_is_not_sustained(self):
        a=prices(100,start=0);f=core.feature(a);same=(f['ao_slope']>0)&~(np.r_[False,f['ao_slope'][:-1]>0])&~f['ao_cross_up']
        self.assertTrue(np.all(f['momentum'][same]!='BULLISH_MOMENTUM'))
    def test_adx_turn_definition(self):
        f=self.data['frames']['1H']['features'];expected=(f['adx_slope']>0)&(np.r_[np.nan,f['adx_slope'][:-1]]<=0)
        np.testing.assert_array_equal(expected,f['adx_turn_up'])
    def test_bbwp_prior_window_matches_frozen_math(self):
        from research.bitman_real.indicators import calculate
        np.testing.assert_allclose(core.feature(self.a)['bbwp'],calculate(self.a)['bbwp'],equal_nan=True)
    def test_level_helper_reuses_copilot(self):
        a=self.a[:1000];result=levels.scale(a,HOUR)
        for i in (100,219,220,500,999):
            baseline=confirmed_level_scale(a[max(0,i-219):i+1],float(a[i,4]),1.,HOUR)
            for key in ('support','resistance'):
                if baseline[key] is None:self.assertTrue(np.isnan(result[key][i]))
                else:self.assertEqual(result[key][i],baseline[key])
    def test_pivots_two_right_not_backdated(self):
        a=prices(15,start=0);a[:,2]=110;a[5,2]=120
        r=levels.scale(a,HOUR);self.assertTrue(np.isnan(r['resistance'][6]));self.assertEqual(r['resistance_known'][7],8*HOUR)
    def test_previous_day_completed_only(self):
        a=prices(60,start=0);a[25:,2]=10000
        r=levels.previous_periods(a,np.array([24*HOUR,25*HOUR]));self.assertEqual(r['previous_day_high'][0],max(a[:24,2]));self.assertEqual(r['previous_day_high'][0],r['previous_day_high'][1])
    def test_previous_week_monday_complete(self):
        start=4*24*HOUR;a=prices(200,start=start);r=levels.previous_periods(a,np.array([start+168*HOUR]));self.assertEqual(r['previous_week_high'][0],max(a[:168,2]))
    def test_crossed_level_not_relabelled(self):
        s={'4H':{'resistance':100.,'support':80.}};r=levels.context(s,{},102.,103.,101.,2.)
        self.assertEqual(r['scales']['4H']['resistance']['relationship'],'CROSSED_AWAITING_4H_CLOSE');self.assertEqual(r['nearest_support'],80.)
    def test_continuous_distances(self):
        s={'4H':{'resistance':110.,'support':90.}};r=levels.context(s,{},100.,101.,99.,5.)
        self.assertAlmostEqual(r['resistance_distance_pct'],.1);self.assertAlmostEqual(r['support_distance_pct'],-.1);self.assertEqual(r['resistance_distance_atr'],2.)
    def test_no_pivots_not_open_space(self):
        r=levels.context({}, {},100.,101.,99.,5.);self.assertIsNone(r['nearest_resistance']);self.assertTrue(r['absent_level_not_open_space'])
    def test_old_known_level_touch_only(self):
        s={'4H':{'resistance':100.}};self.assertFalse(levels.context(s,{},99.,101.,98.,1.)['opposing_up'])
        self.assertTrue(levels.context(s,s,99.,101.,98.,1.)['opposing_up'])
    def test_konkorde_exit_does_not_make_short(self):
        p=components();p['4H']['konkorde']='KONKORDE_EXIT_CONTEXT';self.assertEqual(core.decide(p)['state'],'UP')


class ConfirmedBoundaryTests(unittest.TestCase):
    def test_only_confirmed_existing_colors(self):
        now=20*HOUR+1000;r=confirmed.confirmed_cache(ml_export(now),now);self.assertEqual(r['4H']['color'],'GREEN');self.assertEqual(r['1H']['color'],'GREEN')
    def test_provisional_red_cannot_override_confirmed_green(self):
        now=20*HOUR+1000;p=ml_export(now);p['timeframes']['4h']['observation']['latest_provisional_values']['color']='RED'
        self.assertEqual(confirmed.confirmed_cache(p,now)['4H']['color'],'GREEN')
    def test_approaching_not_confirmation(self):
        now=20*HOUR+1000;p=ml_export(now);p['timeframes']['4h']['observation']['confirmed_color']='NEUTRAL';p['timeframes']['4h']['observation']['latest_confirmed_values']['color']='NEUTRAL'
        self.assertEqual(confirmed.confirmed_cache(p,now)['4H']['color'],'NEUTRAL')
    def test_1d_not_fabricated(self):self.assertEqual(confirmed.confirmed_cache(ml_export(20*HOUR),20*HOUR)['1D']['color'],'UNKNOWN')
    def test_stale_read_unknown(self):self.assertEqual(confirmed.confirmed_cache(ml_export(20*HOUR),20*HOUR+90001)['4H']['color'],'UNKNOWN')
    def test_future_candle_unknown(self):
        now=20*HOUR;p=ml_export(now);p['timeframes']['4h']['observation']['last_closed_timestamp']+=4*HOUR
        self.assertEqual(confirmed.confirmed_cache(p,now)['4H']['color'],'UNKNOWN')
    def test_wrong_preset_not_substituted(self):
        p=ml_export(20*HOUR);p['config_version']='RSI27';self.assertEqual(confirmed.confirmed_cache(p,20*HOUR)['4H']['color'],'UNKNOWN')
    def test_missing_corrupt_cache_fail_safe(self):
        for p in (None,{},[],{'timeframes':None}):self.assertEqual(confirmed.confirmed_cache(p,0)['1H']['color'],'UNKNOWN')
    def test_projection_does_not_copy_secrets_or_modify_input(self):
        p=ml_export(20*HOUR);p['unrelated_private_field']='sensitive-value';original=copy.deepcopy(p)
        r=confirmed.confirmed_cache(p,20*HOUR);self.assertNotIn('sensitive-value',json.dumps(r));self.assertEqual(p,original)
    def test_cache_read_only_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'copy.json';p.write_text(json.dumps(ml_export(20*HOUR)));before=p.read_bytes()
            confirmed.read_cache(p,20*HOUR);self.assertEqual(p.read_bytes(),before)
    def test_journal_does_not_retime_late_observation(self):
        r=dict(config_version=MLRSI_CONFIG,symbol='BTCUSDT',source='LOW',timeframe='1h',candle_complete=True,trade_authority=False,shadow_only=True,
            event='GREEN_CROSS',confirmed_color='GREEN',recorded_at_utc='2026-10-01T01:00:40Z',candle_timestamp_utc='2026-10-01T01:00:00Z')
        rows=confirmed.confirmed_journal_rows([r]);self.assertEqual(rows[0]['available_at']-rows[0]['closed_at'],40000)
        r['candle_complete']=False;self.assertEqual(confirmed.confirmed_journal_rows([r]),[])


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.a=prices(10,start=0);self.a[:,1:5]=[100.,101.,99.,100.]
    def test_long_return(self):
        self.a[1,4]=103.;self.assertAlmostEqual(ev.measure(self.a,HOUR,100,1,1,10*HOUR)['signed_return'],.03)
    def test_short_return(self):
        self.a[1,4]=97.;self.assertAlmostEqual(ev.measure(self.a,HOUR,100,-1,1,10*HOUR)['signed_return'],.03)
    def test_future_only(self):
        self.a[0,2]=1000.;r=ev.measure(self.a,HOUR,100,1,1,10*HOUR);self.assertAlmostEqual(r['mfe'],.01)
    def test_mfe_mae_short(self):
        self.a[1,2:4]=[104,93];r=ev.measure(self.a,HOUR,100,-1,1,10*HOUR);self.assertAlmostEqual(r['mfe'],.07);self.assertAlmostEqual(r['mae'],-.04)
    def test_2_5_10_targets_long(self):
        self.a[1,2]=111.;r=ev.measure(self.a,HOUR,100,1,2,10*HOUR)
        for k in ('2','5','10'):self.assertEqual(r['targets'][k]['favorable_hour'],1)
    def test_2_5_10_targets_short(self):
        self.a[1,3]=89.;r=ev.measure(self.a,HOUR,100,-1,2,10*HOUR)
        for k in ('2','5','10'):self.assertEqual(r['targets'][k]['favorable_hour'],1)
    def test_same_bar_is_ambiguous_not_win(self):
        self.a[1,2:4]=[111,89];r=ev.measure(self.a,HOUR,100,1,2,10*HOUR)
        self.assertEqual(r['targets']['10']['race'],'AMBIGUOUS')
    def test_adverse_before_target_is_bounded(self):
        self.a[1,2:4]=[111,89];r=ev.measure(self.a,HOUR,100,1,2,10*HOUR)['targets']['10']
        self.assertEqual(r['adverse_before_touch_definite'],0.);self.assertAlmostEqual(r['adverse_through_touch_bar_upper_bound'],.11)
    def test_missing_data_censored(self):self.assertFalse(ev.measure(self.a[[1,3,4]],HOUR,100,1,2,10*HOUR)['complete'])
    def test_unmature_not_loss(self):self.assertFalse(ev.measure(self.a,9*HOUR,100,1,2,10*HOUR)['complete'])
    def test_unclear_has_no_directional_accuracy(self):
        s=ev.summarize([ev.measure(self.a,0,100,0,1,10*HOUR)]);self.assertNotIn('directional_accuracy',s);self.assertEqual(s['n_directional'],0)
    def test_one_continuous_episode(self):
        rows=ev.episodes(['UP']*10,np.arange(10)*HOUR,np.ones(10)*100);self.assertEqual(len(rows),1)
    def test_state_transition_new_episode(self):
        rows=ev.episodes(['UP','UP','TRANSITION','DOWN'],np.arange(4)*HOUR,np.ones(4)*100);self.assertEqual(len(rows),3);self.assertEqual(rows[0]['episode_end'],2*HOUR)
    def test_episode_original_side_immutable(self):
        rows=ev.episodes(['TRANSITION']*3,np.arange(3)*HOUR,np.ones(3)*100,np.array([1,-1,-1]));self.assertEqual(rows[0]['direction'],1)
    def test_weekly_bootstrap_deterministic(self):self.assertEqual(ev.paired_bootstrap([.01,-.02],[0,200*HOUR]),ev.paired_bootstrap([.01,-.02],[0,200*HOUR]))
    def test_false_reversal_is_evaluation_only(self):
        rows=ev.episodes(['DOWN','UP','DOWN']+['DOWN']*7,np.arange(10)*HOUR,np.ones(10)*100,stream='1H')
        data=dict(bars=self.a,times=self.a[:,0]);q=ev.evaluate_rows(rows,data,(4,),0,10*HOUR,['k']*10)
        self.assertTrue(q[1]['false_reversal']);self.assertNotIn('false_reversal',rows[1])
    def test_false_reversal_right_censored(self):
        rows=ev.episodes(['DOWN']*8+['UP']*2,np.arange(10)*HOUR,np.ones(10)*100,stream='1H')
        q=ev.evaluate_rows(rows,dict(bars=self.a,times=self.a[:,0]),(4,),0,10*HOUR,['k']*10)
        self.assertIsNone(q[-1]['false_reversal'])
    def test_pending_not_in_mean(self):
        s=ev.summarize([ev.measure(self.a,0,100,1,4,10*HOUR),ev.measure(self.a,9*HOUR,100,1,4,10*HOUR)])
        self.assertEqual(s['n_complete'],1);self.assertEqual(s['n_incomplete'],1);self.assertEqual(s['signed_return']['mean'],0.)
    def test_controls_not_chosen_by_future_returns(self):
        rows=ev.episodes(['UNCLEAR','UP']+['UP']*8,np.arange(10)*HOUR,np.ones(10)*100,stream='1H')
        q=ev.evaluate_rows(rows,dict(bars=self.a,times=self.a[:,0]),(4,),0,10*HOUR,['k']*10)
        b=self.a.copy();b[4:,1:5]*=1.5
        changed=ev.evaluate_rows(rows,dict(bars=b,times=b[:,0]),(4,),0,10*HOUR,['k']*10)
        self.assertEqual(q[1]['control_outcomes']['4']['timestamps'],changed[1]['control_outcomes']['4']['timestamps'])


class ObserverAndSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.a=prices(3000);cls.now=int(cls.a[-1,0]+HOUR)
    def test_bootstrap_is_status_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=DirectionObserver(tmp);r=o.cycle(self.a,self.now);self.assertEqual(r['messages'],[]);self.assertTrue(r['current_status_only'])
    def test_same_candle_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=DirectionObserver(tmp);o.cycle(self.a,self.now);self.assertEqual(o.cycle(self.a,self.now)['messages'],[])
    def test_restart_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            DirectionObserver(tmp).cycle(self.a,self.now);r=DirectionObserver(tmp).cycle(self.a,self.now);self.assertEqual(r['messages'],[])
    def test_outage_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=DirectionObserver(tmp).cycle(np.empty((0,7)),self.now);self.assertEqual(r['status'],'DIRECTION_OBSERVATION_FAILED');self.assertEqual(r['messages'],[])
    def test_no_production_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):DirectionObserver(Path(tmp)/'guardian')
    def test_no_network_any_public_calculation(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('NETWORK_FORBIDDEN')) as transport:
            p=core.prepare(self.a,self.now);s=core.snapshot(p,len(self.a)-1);render(s);confirmed.confirmed_cache({},self.now)
            transport.assert_not_called()
    def test_no_senders_or_account_capability(self):
        forbidden=('requests','httpx','aiohttp','socket','trade_guardian','guardian_bitunix','v8_executor','mlrsi_math','mlrsi_observer','live_auto','main')
        for path in Path('research/bitman_direction').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                self.assertFalse(any(x in forbidden for x in imports))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):self.assertNotIn(node.func.attr,('post','getUpdates','place_order','flash_close_position','change_leverage','withdraw','transfer'))
    def test_parent_source_identity(self):
        files=subprocess.check_output(['git','diff','--name-only','ee4e59016220ec733b19a37d14429f8fdde6d348',BASE_SHA],text=True).splitlines()
        for p in files:
            old=subprocess.check_output(['git','show',BASE_SHA+':'+p]);self.assertEqual(old.replace(b'\r\n',b'\n'),Path(p).read_bytes().replace(b'\r\n',b'\n'),p)
    def test_renderer_every_state_no_authority(self):
        for state in ('UP','DOWN','TRANSITION','UNCLEAR','CONFLICT'):
            text=render(dict(state=state));self.assertIn('DIRECTION: '+state,text);self.assertIn('NOT A TRADE SIGNAL',text);self.assertIn('TRADE AUTHORITY: NONE',text);self.assertIn('NOT A GUARANTEE',text)
    def test_noise_one_to_one(self):
        a=[dict(id='a',state='UP',timestamp=HOUR),dict(id='b',state='UP',timestamp=2*HOUR)];b=[dict(id='c',state='UP',timestamp=3*HOUR)]
        s=noise.compare(a,b);self.assertEqual(s['matched'],1);self.assertEqual(s['median_engine_minus_other_hours'],-1.)
    def test_noise_no_match_opposite_direction(self):self.assertEqual(noise.compare([dict(id='a',state='UP',timestamp=0)],[dict(id='b',state='DOWN',timestamp=0)])['matched'],0)
    def test_no_fitted_indicator_thresholds(self):
        p=protocol();self.assertFalse(p['production_integration']);self.assertEqual(p['paid_source_calls'],0);self.assertFalse(p['trade_authority'])
    def fake_snapshot(self,data,i,ml):
        return dict(state=data['test_state'],detail=data['test_state']+'_CONFIRMED',direction=1 if data['test_state']=='UP' else -1,
            strength='BUILDING',evidence_grade='B',reference_price=100.,timestamp=int(data['times'][-1]),trade_authority=False)
    def feed(self,observer,stamp,state):
        data=dict(times=np.array([stamp]),bars=np.array([[stamp-HOUR,100,101,99,100,10,5]]),test_state=state)
        with patch('research.bitman_direction.core.prepare',return_value=data),patch('research.bitman_direction.core.snapshot',side_effect=self.fake_snapshot):
            return observer.cycle(data['bars'],stamp)
    def test_transition_emits_once_without_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=DirectionObserver(tmp);self.feed(o,100*HOUR,'UP');r=self.feed(o,101*HOUR,'DOWN')
            self.assertEqual(len(r['messages']),1);self.assertIn('DIRECTION: DOWN',r['messages'][0]);self.assertEqual(self.feed(o,102*HOUR,'DOWN')['messages'],[])
    def test_gap_catchup_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=DirectionObserver(tmp);self.feed(o,100*HOUR,'UP');r=self.feed(o,110*HOUR,'DOWN');self.assertEqual(r['messages'],[]);self.assertTrue(r['current_status_only'])
    def test_restart_changed_state_is_status_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.feed(DirectionObserver(tmp),100*HOUR,'UP');r=self.feed(DirectionObserver(tmp),101*HOUR,'DOWN');self.assertEqual(r['messages'],[])
    def test_failed_storage_does_not_return_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=DirectionObserver(tmp);self.feed(o,100*HOUR,'UP')
            with patch('research.bitman_direction.observer.atomic',side_effect=OSError('disk')):
                r=self.feed(o,101*HOUR,'DOWN');self.assertEqual(r['messages'],[]);self.assertEqual(r['status'],'DIRECTION_OBSERVATION_FAILED')
    def test_atomic_fsync_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('research.bitman_real.storage.os.fsync') as fsync:
                o=DirectionObserver(tmp);self.feed(o,100*HOUR,'UP');self.assertTrue(fsync.called)
            self.assertEqual(json.loads((Path(tmp)/'direction_state.json').read_text())['timestamp'],100*HOUR)
    def test_direction_state_not_a_point_score(self):
        self.assertNotIn('score',core.decide(components()))
    def test_renderer_ignores_unrelated_payload_fields(self):
        s=dict(state='UP',api_key='sentinel-key',chat_id='sentinel-chat',raw_payload='sentinel-raw')
        text=render(s)
        for value in ('sentinel-key','sentinel-chat','sentinel-raw'):self.assertNotIn(value,text)
    def test_strict_read_only_safety_audit(self):
        from research.bitman_direction.safety import audit
        r=audit();self.assertEqual(r['status'],'PASS');self.assertFalse(r['http_transport']);self.assertFalse(r['order_capability'])


class FrozenEvidenceTests(unittest.TestCase):
    def test_frozen_protocol_intact(self):
        from research.bitman_direction.study import check
        check()
    def test_only_train_matching_calibration(self):
        from research.bitman_direction.study import ART,SPLITS
        d=json.loads((ART/'calibration_lock.json').read_text());self.assertEqual(d['end'],SPLITS['TRAIN'][1]);self.assertTrue(d['no_parameter_selection'])
    def test_no_fabricated_historical_ml(self):
        from research.bitman_direction.study import ART
        d=json.loads((ART/'results.json').read_text());self.assertFalse(d['mlrsi_ablation']['computed']);self.assertEqual(d['mlrsi_ablation']['rows'],0)
    def test_annual_walkforward_calibrates_before_testyear(self):
        from research.bitman_direction.study import ART,stamp
        d=json.loads((ART/'results.json').read_text())
        for year,fold in d['walk_forward'].items():self.assertEqual(fold['last_calibration_data_before'],stamp(year+'-01-01T00:00:00Z'));self.assertFalse(fold['parameter_selection'])
    def test_reporting_unmixes_raw_and_signed(self):
        from research.bitman_direction.reporting import unmixed
        rows=[dict(direction=0,timestamp=0,outcomes={'72':dict(complete=True,raw_return=.1)},control_outcomes={'72':dict(mean=.02)},paired_excess={'72':.08}),
            dict(direction=-1,timestamp=HOUR,outcomes={'72':dict(complete=True,raw_return=.03)},control_outcomes={'72':dict(mean=-.02)},paired_excess={'72':-.01})]
        result=unmixed(rows,72);self.assertAlmostEqual(result['raw_btc_excess']['mean'],.045);self.assertAlmostEqual(result['signed_lean_excess']['mean'],-.01)
    def test_canonical_reporting_preserves_primary_up_down(self):
        from research.bitman_direction.study import ART
        original=json.loads((ART/'results.json').read_text());canonical=json.loads((ART/'canonical_control_reporting.json').read_text())
        self.assertFalse(canonical['primary_up_down_changed']);self.assertFalse(canonical['classification_changed'])
        for period in ('TRAIN','VALIDATION','TEST'):
            for state in ('UP','DOWN'):
                self.assertEqual(original['splits']['MTF'][period][state]['matched']['72'],canonical['canonical']['MTF'][period][state]['72']['signed_lean_excess'])
    def test_nested_pullback_does_not_create_new_direction_episode(self):
        from research.bitman_direction.timing_diagnostics import diagnostic_events
        times=np.arange(4)*HOUR;states=['UP']*4
        series=dict(detail=np.array(['UP_CONFIRMED','UP_WITH_1H_PULLBACK','UP_WITH_1H_PULLBACK','UP_CONFIRMED']),direction=np.ones(4,dtype=int))
        data=dict(times=times,bars=prices(4,start=0));rows=diagnostic_events(data,series)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['episode_end'],3*HOUR);self.assertEqual(len(ev.episodes(states,times,np.ones(4)*100)),1)
    def test_renderer_samples_coherent_and_under_telegram_limit(self):
        from research.bitman_direction.report import samples
        for state,text in samples().items():self.assertIn('DIRECTION: '+state,text);self.assertLess(len(text),3900);self.assertIn('TRADE AUTHORITY: NONE',text)


if __name__=='__main__':unittest.main()
