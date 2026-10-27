"""Post-hoc causal timing sensitivity, immutable strict outputs and replay."""
import copy
import json
from pathlib import Path
import unittest

try:
    import numpy as np
    from research import bitman_weekly_state_machine as sm
    from research import bitman_state_source_alignment as aligned
except ModuleNotFoundError as error:
    if error.name == 'numpy':
        raise unittest.SkipTest('Dedicated research workflow installs existing numpy dependency') from error
    raise


def fixture(ao, color, vol, valid=None):
    n = len(ao)
    times = 4*86400000+np.arange(n)*7*86400000
    f = dict(ao=np.asarray(ao,float),color=np.asarray(color),bbwp_slope=np.asarray(vol,float),
             valid=np.asarray(valid,bool) if valid is not None else np.ones(n,bool),
             frame=np.column_stack((times,np.full((n,6),100.))),available_at=times+7*86400000,
             sign=np.where(np.asarray(ao)>0,'ABOVE',np.where(np.asarray(ao)<0,'BELOW','ZERO')),
             ao_slope=np.r_[0,np.diff(ao)],bbwp=50+np.cumsum(vol))
    f['turn']=(f['bbwp_slope']>0)&(np.r_[np.nan,f['bbwp_slope'][:-1]]<=0)&f['valid']
    f['state'],f['pullback_weeks']=sm.classify(f)
    f['signal']=np.isin(f['state'],sm.SIGNALS)
    f['side']=np.where(np.isin(f['state'],(sm.SIGNALS[0],sm.SIGNALS[2])),1,
                       np.where(np.isin(f['state'],(sm.SIGNALS[1],sm.SIGNALS[3])),-1,0))
    return f


class LagMachineTests(unittest.TestCase):
    def up(self,lag):
        return fixture([3,2,2.5,3,3.5,4],['GREEN','RED','GREEN','GREEN','GREEN','GREEN'],
                       [1,-1,-1,1,1,1] if lag==1 else [1,-1,-1,-1,1,1])

    def test_only_three_requested_lags_allowed(self):
        f=self.up(1)
        for lag in (-1,3,4,5,1.0,True,None):
            with self.subTest(lag=lag),self.assertRaises(ValueError):
                aligned.resolve(f,lag)

    def test_reacceleration_up_one_week_delay_not_backdated(self):
        f=self.up(1)
        self.assertEqual(len(aligned.resolve(f,0)['events']),0)
        event=aligned.resolve(f,1)['events'][0]
        self.assertEqual((event['activation_index'],event['index'],event['lag']),(2,3,1))
        self.assertEqual(event['kind'],'REACCELERATION_UP')
        self.assertEqual(event['confirmed_at'],sm.iso(f['available_at'][3]))

    def test_reacceleration_down_one_week_delay(self):
        f=self.up(1)
        f['ao']=-f['ao'];f['ao_slope']=-f['ao_slope']
        f['color']=np.where(f['color']=='GREEN','RED','GREEN');f['sign']=np.full(6,'BELOW')
        f['state'],f['pullback_weeks']=sm.classify(f)
        event=aligned.resolve(f,1)['events'][0]
        self.assertEqual((event['kind'],event['side'],event['lag']),('REACCELERATION_DOWN',-1,1))

    def test_two_week_delay_requires_lag_two(self):
        f=self.up(2)
        self.assertEqual(len(aligned.resolve(f,1)['events']),0)
        event=aligned.resolve(f,2)['events'][0]
        self.assertEqual((event['activation_index'],event['index'],event['lag']),(2,4,2))

    def test_zero_cross_up_delayed_turn(self):
        f=fixture([-2,-1,.1,.2,.3],['GREEN']*5,[-1,-1,-1,1,1])
        event=aligned.resolve(f,1)['events'][0]
        self.assertEqual((event['kind'],event['activation_index'],event['index']),('ZERO_CROSS_UP_EXPANSION',2,3))

    def test_zero_cross_down_delayed_turn(self):
        f=fixture([2,1,-.1,-.2,-.3],['RED']*5,[-1,-1,-1,1,1])
        event=aligned.resolve(f,1)['events'][0]
        self.assertEqual((event['kind'],event['lag']),('ZERO_CROSS_DOWN_EXPANSION',1))

    def test_zero_cross_active_same_week_retains_original_behavior(self):
        f=fixture([1,-1,-2],['RED']*3,[1,1,1])
        self.assertFalse(f['turn'][1])
        for lag in aligned.LAGS:
            event=aligned.resolve(f,lag)['events'][0]
            self.assertEqual((event['index'],event['lag']),(1,0))

    def test_pending_same_zero_side_does_not_add_new_color_gate(self):
        f=fixture([-1,.2,.1],['GREEN','GREEN','RED'],[-1,-1,1])
        event=aligned.resolve(f,1)['events'][0]
        self.assertEqual(event['resolution_color'],'RED')
        self.assertEqual(event['kind'],'ZERO_CROSS_UP_EXPANSION')

    def test_exact_zero_cancels_and_cannot_resurrect(self):
        f=fixture([-1,.1,0,.2],['GREEN','GREEN','RED','GREEN'],[-1,-1,-1,1])
        model=aligned.resolve(f,2)
        self.assertEqual(model['events'],[])
        self.assertTrue(any(x['reason']=='ZERO_OR_OPPOSITE_SIGN' for x in model['audit']))

    def test_opposite_cross_cancels_and_can_start_new_sequence(self):
        f=fixture([-1,.1,-.1,-.2],['GREEN','GREEN','RED','RED'],[-1,-1,-1,1])
        model=aligned.resolve(f,2)
        self.assertEqual(len(model['events']),1)
        self.assertEqual(model['events'][0]['kind'],'ZERO_CROSS_DOWN_EXPANSION')
        self.assertEqual(model['events'][0]['activation_index'],2)

    def test_invalid_week_cancels_pending(self):
        f=fixture([-1,.1,.2,.3],['GREEN']*4,[-1,-1,-1,1],[True,True,False,True])
        model=aligned.resolve(f,2)
        self.assertEqual(model['events'],[])
        self.assertTrue(any(x['reason']=='INVALID_WEEK' for x in model['audit']))

    def test_new_correction_cancels_previous_return(self):
        f=fixture([3,2,2.5,2.4,2.6],['GREEN','RED','GREEN','RED','GREEN'],[1,-1,-1,-1,1])
        model=aligned.resolve(f,2)
        self.assertEqual(len(model['events']),1)
        self.assertEqual(model['events'][0]['activation_index'],4)
        self.assertTrue(any(x['reason']=='NEW_CORRECTION' for x in model['audit']))

    def test_expired_sequence_never_reanimated(self):
        f=fixture([-1,.1,.2,.3,.4],['GREEN']*5,[-1,-1,-1,-1,1])
        model=aligned.resolve(f,2)
        self.assertEqual(model['events'],[])
        self.assertIsNone(model['pending_by_week'][-1])

    def test_pending_zero_cross_owns_one_resolution_over_color_return(self):
        f=fixture([-1,.2,.1,.3,.4],['GREEN','GREEN','RED','GREEN','GREEN'],[-1,-1,-1,1,1])
        model=aligned.resolve(f,2)
        self.assertEqual(len(model['events']),1)
        self.assertEqual(model['events'][0]['kind'],'ZERO_CROSS_UP_EXPANSION')
        self.assertEqual(model['events'][0]['lag'],2)
        self.assertTrue(any(x['action']=='IGNORED' and x['kind']=='REACCELERATION_UP' for x in model['audit']))

    def test_persistent_expansion_never_repeated(self):
        f=self.up(1)
        self.assertEqual(len(aligned.resolve(f,2)['events']),1)

    def test_prefix_invariance_events_states_audit_and_pending(self):
        f=self.up(2)
        for lag in aligned.LAGS:
            full=aligned.resolve(f,lag)
            for end in range(1,len(f['ao'])+1):
                prefix={k:v[:end] for k,v in f.items()}
                got=aligned.resolve(prefix,lag)
                self.assertEqual(got['events'],[e for e in full['events'] if e['index']<end])
                self.assertEqual(got['audit'],[e for e in full['audit'] if e['index']<end])
                self.assertEqual(got['pending_by_week'],full['pending_by_week'][:end])
                np.testing.assert_array_equal(got['states'],full['states'][:end])

    def test_inputs_unmodified_and_no_outcomes_consulted(self):
        f=self.up(1); before=copy.deepcopy(f)
        for lag in aligned.LAGS:
            aligned.resolve(f,lag)
        for key in before:
            np.testing.assert_array_equal(f[key],before[key])
        # Resolution needs no future prices/returns, only causal feature timestamps.
        self.assertNotIn('outcomes',aligned.resolve.__code__.co_names)

    def test_unresolved_final_candidate_is_pending_not_signal(self):
        f={k:v[:3] for k,v in self.up(2).items()}
        model=aligned.resolve(f,2)
        self.assertEqual(model['events'],[])
        self.assertIsNotNone(model['pending_by_week'][-1])
        self.assertFalse(model['signal'][-1])


class PublicAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=sm.load_inputs()
        cls.saved=json.loads((aligned.DEST/'analysis.json').read_text('utf-8'))

    def test_strict_fourteen_sources_and_numeric_artifacts_frozen(self):
        self.assertEqual(len(aligned.verify_strict()['sha256']),14)

    def test_lag_zero_matches_all_original_seven_timestamps_sides_types(self):
        model=aligned.resolve(self.f,0)
        self.assertEqual(len(model['events']),7)
        np.testing.assert_array_equal(model['signal'],self.f['signal'])
        np.testing.assert_array_equal(model['side'],self.f['side'])
        np.testing.assert_array_equal(model['states'][model['signal']],self.f['state'][self.f['signal']])

    def test_each_activation_and_resolution_unique_and_within_window(self):
        for lag in aligned.LAGS:
            model=aligned.resolve(self.f,lag)
            events=model['events']
            self.assertEqual(len({e['episode_id'] for e in events}),len(events))
            self.assertEqual(len({e['index'] for e in events}),len(events))
            for event in events:
                self.assertEqual(event['index']-event['activation_index'],event['lag'])
                self.assertLessEqual(event['lag'],lag)
                self.assertGreaterEqual(event['lag'],0)

    def test_saved_models_events_audit_current_reproduce(self):
        for saved in self.saved['models']:
            model=aligned.resolve(self.f,saved['max_lag'])
            self.assertEqual(sm.clean(model['events']),saved['events'])
            self.assertEqual(model['audit'],saved['audit'])
            self.assertEqual(str(model['states'][-1]),saved['current']['state'])

    def test_only_requested_models_and_post_hoc_caveats(self):
        self.assertEqual([m['max_lag'] for m in self.saved['models']],[0,1,2])
        self.assertEqual(self.saved['label'],'POST_HOC_SOURCE_ALIGNED_LAG_SENSITIVITY')
        self.assertTrue(self.saved['no_virgin_holdout'])
        self.assertFalse(self.saved['agent_direct_transcript_access'])
        self.assertEqual(self.saved['strict_conclusion'],'INCONCLUSIVE')
        self.assertIn(self.saved['conclusion'],(
            'SOURCE-ALIGNED SENSITIVITY STILL INCONCLUSIVE',
            'SOURCE-ALIGNED SENSITIVITY SUGGESTIVE — FORWARD TEST REQUIRED',
            'SOURCE-ALIGNED SENSITIVITY WEAKER THAN STRICT MODEL','PROXY LIMITATION DOMINATES'))

    def test_current_is_same_last_closed_week_and_never_signal(self):
        for model in self.saved['models']:
            current=model['current']
            self.assertEqual(current['available_at'],'2026-10-19T00:00:00+00:00')
            self.assertEqual(current['note'],'CURRENT OBSERVATION — NOT PART OF VALIDATION')
            self.assertEqual(current['large_move_watch'],'NOT VALIDATED')

    def test_metrics_directly_from_confirmation_anchors_for_all_models_and_scopes(self):
        from research.bitman_state_reporting import read_csv
        metrics=read_csv(aligned.DEST,'metrics')
        outcomes={(n,h):sm.outcomes(self.f,n,h) for n in sm.RANGES for h in sm.HORIZONS}
        resolved={lag:aligned.resolve(self.f,lag) for lag in aligned.LAGS}
        for row in metrics:
            out=outcomes[row['range_weeks'],row['horizon']]
            model=resolved[int(row['max_lag'])]
            valid=self.f['valid']&np.isfinite(out['forward'])
            scope=np.ones(len(valid),bool) if row['scope']=='FULL' else (
                self.f['regime']==row['scope'] if row['scope'] in ('BULL','BEAR') else self.f['era']==row['scope'])
            group=(model['signal'] if row['group']=='ALL_SIGNALS' else model['side']==1 if row['group']=='UP'
                   else model['side']==-1 if row['group']=='DOWN' else model['states']==row['group'])
            selected=valid&scope&group
            positive=int(out['large_10'][valid&scope].sum())
            tp=int(out['large_10'][selected].sum())
            n=int(selected.sum())
            self.assertEqual(row['n'],n)
            self.assertEqual(row['true_positive'],tp)
            self.assertEqual(row['false_positive'],n-tp)
            self.assertEqual(row['false_negative'],positive-tp)
            if n:
                self.assertAlmostEqual(row['precision'],tp/n)
                self.assertAlmostEqual(row['signed_mean'],np.mean((out['forward']*model['side'])[selected]))
                self.assertAlmostEqual(row['max_move_median'],np.median(out['max_move'][selected]))
            else:
                self.assertIsNone(row['precision'])

    def test_episode_outcomes_do_not_credit_activation_to_confirmation_move(self):
        from research.bitman_state_reporting import read_csv
        indices={m['name']:{e['episode_id']:e for e in m['events']} for m in self.saved['models']}
        for row in read_csv(aligned.DEST,'observations'):
            event=indices[row['model']][row['episode_id']]
            i=event['index']
            self.assertEqual(row['anchor'],self.f['frame'][i,4])
            high,low=sm.causal_range(self.f['frame'],i,int(row['range_weeks']))
            self.assertEqual((row['range_high'],row['range_low']),(high,low))
            end=i+int(row['horizon'])
            expected=100*(self.f['frame'][end,4]/self.f['frame'][i,4]-1)
            self.assertAlmostEqual(row['forward'],expected)

    def test_all_seven_strict_episodes_retained_without_merging_models(self):
        strict={(e['index'],e['kind']) for e in self.saved['models'][0]['events']}
        self.assertEqual([m['episode_count'] for m in self.saved['models']],[7,11,13])
        for model in self.saved['models']:
            self.assertTrue(strict.issubset({(e['index'],e['kind']) for e in model['events']}))
            self.assertEqual(sum(model['family_counts'].values()),model['episode_count'])

    def test_lag_zero_metrics_equal_unchanged_original_strict_tables(self):
        from research.bitman_state_reporting import read_csv
        strict=read_csv(sm.DEST,'summaries')
        metrics=read_csv(aligned.DEST,'metrics')
        lookup={(r['range_weeks'],r['horizon'],r['scope'],r['group']):r for r in metrics if r['model']=='STRICT_SAME_WEEK'}
        mapping=dict(SIGNALS='ALL_SIGNALS',SIGNAL_UP='UP',SIGNAL_DOWN='DOWN',**{k:k for k in sm.SIGNALS})
        for row in strict:
            if row['group'] not in mapping:
                continue
            got=lookup[row['range_weeks'],row['horizon'],row['scope'],mapping[row['group']]]
            for key in ('n','precision','base_rate','recall','lift','signed_mean','max_move_mean','max_move_median','directional_n','directional_mean'):
                if row[key] is None:
                    self.assertIsNone(got[key])
                else:
                    self.assertAlmostEqual(row[key],got[key],places=10)

    def test_complete_sensitivity_replay_including_blocked_intervals(self):
        from research.bitman_state_reporting import read_csv
        replay=aligned.analyze(self.f)
        for name in ('metrics','observations','influence'):
            saved=read_csv(aligned.DEST,name)
            self.assertEqual(len(saved),len(replay[name]))
            for expected,actual in zip(saved,replay[name]):
                for key,value in actual.items():
                    if value is None:
                        self.assertIsNone(expected[key])
                    elif isinstance(value,(int,float)):
                        self.assertAlmostEqual(value,expected[key],places=9,msg=(name,key))
                    elif isinstance(value,list):
                        import ast
                        self.assertEqual(value,ast.literal_eval(expected[key]))
                    else:
                        self.assertEqual(value,expected[key])
        self.assertEqual(replay['models'],self.saved['models'])

    def test_addendum_report_deterministic_and_semantics_explicit(self):
        from research import bitman_source_alignment_reporting as report
        from research.bitman_state_reporting import read_csv
        rendered=report.render(self.saved,read_csv(aligned.DEST,'metrics'),read_csv(aligned.DEST,'influence'))
        self.assertEqual(rendered,report.REPORT.read_text('utf-8'))
        for required in ('POST-HOC SOURCE ALIGNMENT','NO VIRGIN HOLDOUT',aligned.REVIEW_STATUS,
                         'EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN','EXACT BITMAN VOLATILITY PARITY: NOT PROVEN',
                         'CURRENT OBSERVATION — NOT PART OF VALIDATION','LARGE MOVE WATCH: NOT VALIDATED'):
            self.assertIn(required,rendered)


if __name__=='__main__':
    unittest.main()
