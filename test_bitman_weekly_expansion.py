"""Offline math/causality/protocol tests, never network market experiments."""
import copy
import csv
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    import numpy as np
    from bitman_manual.frozen.indicators import calculate
    from research import bitman_weekly_data as data
    from research import bitman_weekly_expansion as study
except ModuleNotFoundError as error:
    if error.name in ('numpy', 'requests'):
        raise unittest.SkipTest('Dedicated weekly and Guardian workflows install research dependencies') from error
    raise


def bars(count, start=data.MONDAY):
    result=[]
    for i in range(count):
        value=100+np.sin(i/17)*10+i*.01
        result.append([start+i*data.FOUR_HOURS,str(value),str(value+2),str(value-2),str(value+.2),
                       '10',start+(i+1)*data.FOUR_HOURS-1,'1000',2,'4','400','0'])
    return result


def context(slopes, bbwp=None, ao=None):
    s=np.asarray(slopes,float)
    n=len(s)
    previous=study.lag(s)
    run=0
    runs=[]
    for value in s:
        runs.append(run)
        run=run+1 if np.isfinite(value) and value<=0 else 0
    return dict(bbwp_slope=s,prior_slope=previous,bbwp=np.asarray(bbwp if bbwp is not None else np.arange(n)*5,float),
                prior_bbwp=study.lag(np.asarray(bbwp if bbwp is not None else np.arange(n)*5,float)),
                prior_nonincreasing=np.asarray(runs),valid=np.ones(n,bool),
                ao=np.asarray(ao if ao is not None else np.ones(n)),color=np.asarray(['GREEN']*n))


class WeeklyDataTests(unittest.TestCase):
    def test_monday_boundary_not_unix_thursday(self):
        stamp=int(datetime(2026,10,18,23,59,tzinfo=timezone.utc).timestamp()*1000)
        self.assertEqual(data.week_start(stamp),int(datetime(2026,10,12,tzinfo=timezone.utc).timestamp()*1000))
        self.assertEqual(data.week_start(stamp+60_000),data.CUTOFF)

    def test_exact_42_closed_bars_and_decimal_sums(self):
        raw=bars(42)
        before=copy.deepcopy(raw)
        weekly,excluded=data.aggregate_weeks(raw,data.MONDAY+data.WEEK)
        self.assertEqual(len(weekly),1)
        self.assertEqual(weekly[0][5],'420')
        self.assertEqual(weekly[0][9],'168')
        self.assertEqual(weekly[0][6],data.MONDAY+data.WEEK-1)
        self.assertEqual(excluded,[])
        self.assertEqual(raw,before)

    def test_incomplete_initial_week_is_excluded_never_filled(self):
        raw=bars(84)[1:]
        weekly,excluded=data.aggregate_weeks(raw,data.MONDAY+2*data.WEEK)
        self.assertEqual(len(weekly),1)
        self.assertEqual(excluded[0]['bars'],41)

    def test_open_week_never_aggregated(self):
        raw=bars(43)
        weekly,excluded=data.aggregate_weeks(raw,data.MONDAY+43*data.FOUR_HOURS)
        self.assertEqual(len(weekly),1)
        self.assertEqual(excluded[-1]['bars'],1)

    def test_gap_duplicate_schema_open_candle_and_bad_values_fail(self):
        original=bars(5)
        cases=[original[:2]+original[3:],original[:2]+[original[1]]+original[2:]]
        for field,value in ((6,1),(1,'nan'),(3,'20000'),(9,'11')):
            changed=copy.deepcopy(original)
            changed[2][field]=value
            cases.append(changed)
        cases.append([r[:-1] for r in original])
        for rows in cases:
            with self.assertRaises((ValueError, ArithmeticError)):
                data.validate(rows,data.FOUR_HOURS,data.MONDAY+5*data.FOUR_HOURS)
        with self.assertRaises(ValueError):
            data.validate(original,data.FOUR_HOURS,data.MONDAY+4*data.FOUR_HOURS)

    def test_source_comparison_preserves_exact_differences(self):
        expected=bars(2)
        actual=copy.deepcopy(expected)
        actual[0][5]='10.25'
        result=data.compare_fields(expected,actual)
        self.assertEqual(result,[dict(open_time=data.MONDAY,field='base_volume',reference='10',actual='10.25',delta='0.25')])

    def test_non200_never_switches_venue_or_uses_proxy_or_credentials(self):
        session=Mock()
        session.__enter__=Mock(return_value=session)
        session.__exit__=Mock(return_value=False)
        session.get.return_value=Mock(status_code=451,content=b'{}')
        with tempfile.TemporaryDirectory() as folder, patch.object(data.requests,'Session',return_value=session):
            with self.assertRaisesRegex(ValueError,'PUBLIC_HTTP_451'):
                data.acquire(folder)
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_count,1)
        args,kwargs=session.get.call_args
        self.assertEqual(args,(data.URL,))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertNotIn('auth',kwargs)
        self.assertNotIn('headers',kwargs)


class FormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=bars(160*42)
        cls.f,cls.weekly,_=study.features(cls.raw,data.MONDAY+160*data.WEEK)

    def test_reuses_frozen_math_exactly(self):
        expected=calculate(self.f['frame'])
        for key in ('ao','ao_slope','bbwp','bbwp_slope','adx','adx_slope','di_plus','di_minus'):
            np.testing.assert_equal(self.f[key],expected[key])

    def test_ao_sma5_minus_sma34_and_color_not_zero_position(self):
        median=(self.f['frame'][:,2]+self.f['frame'][:,3])/2
        for i in range(34,len(median)):
            expected=np.mean(median[i-4:i+1])-np.mean(median[i-33:i+1])
            self.assertAlmostEqual(self.f['ao'][i],expected,12)
        f=dict(self.f,ao=np.asarray([1.,1.,-1.,-1.]),color=np.asarray(['GREEN','RED','GREEN','RED']),valid=np.ones(4,bool))
        cases=study.strata(f)
        for i,key in enumerate(('GREEN_POS','RED_POS','GREEN_NEG','RED_NEG')):
            self.assertEqual(np.flatnonzero(cases[key]).tolist(),[i])

    def test_bbwp_population_std_strict_rank_and_full_warmup(self):
        c=self.f['frame'][:,4]
        widths=np.asarray([4*np.std(c[i-6:i+1],ddof=0)/np.mean(c[i-6:i+1]) if i>=6 else np.nan for i in range(len(c))])
        self.assertEqual(np.flatnonzero(np.isfinite(self.f['bbwp']))[0],106)
        self.assertEqual(np.flatnonzero(self.f['valid'])[0],108)
        for i in range(106,len(c)):
            self.assertEqual(self.f['bbwp'][i],np.count_nonzero(widths[i-100:i]<widths[i]))
        flat=np.asarray([[data.MONDAY+i*data.WEEK,100,101,99,100,10,4] for i in range(120)],float)
        self.assertEqual(calculate(flat)['bbwp'][-1],0)  # equal widths never rank as smaller

    def test_prefix_invariance_all_features_and_frozen_regime(self):
        short,_,_=study.features(self.raw[:140*42],data.MONDAY+140*data.WEEK)
        for key in ('ao','ao_slope','bbwp','bbwp_slope','adx','di_plus','di_minus','regime','valid'):
            np.testing.assert_equal(short[key],self.f[key][:140])
        index=139*42+41
        expected=np.sign(float(self.raw[index][4])-np.mean([float(r[4]) for r in self.raw[index-199:index+1]]))
        self.assertEqual(short['regime'][-1],'BULL' if expected>0 else 'BEAR')


class EventTests(unittest.TestCase):
    def test_start_requires_previous_nonpositive_slope(self):
        masks=study.events(context([-2,0,3,4,-1,2]))
        self.assertEqual(np.flatnonzero(masks['C_START']).tolist(),[2,5])
        self.assertEqual(np.flatnonzero(masks['A_RISING']).tolist(),[2,3,5])
        self.assertEqual(np.flatnonzero(masks['B_FALLING']).tolist(),[0,4])

    def test_nested_2_3_4_contraction_no_best_n_selection(self):
        masks=study.events(context([-1,0,-2,0,2]))
        self.assertTrue(all(masks['D_PRIOR_'+str(n)][4] for n in (2,3,4)))
        masks=study.events(context([1,-1,0,2]))
        self.assertTrue(masks['D_PRIOR_2'][3])
        self.assertFalse(masks['D_PRIOR_3'][3])

    def test_all_buckets_disjoint_and_cover_start_at_boundaries(self):
        for previous,expected in ((0,'E_0_10'),(10,'E_0_10'),(20,'E_10_20'),(30,'E_20_30'),(50,'E_30_50'),(51,'E_GT50'),(100,'E_GT50')):
            masks=study.events(context([-1,1],bbwp=[previous,previous+1]))
            chosen=[key for key,mask in masks.items() if key.startswith('E_') and mask[1]]
            self.assertEqual(chosen,[expected])

    def test_50_cross_is_strict_and_no_rounding(self):
        masks=study.events(context([-1,1,1],bbwp=[49,50,51]))
        self.assertFalse(masks['F_CROSS50'][1])
        self.assertTrue(masks['F_CROSS50'][2])
        self.assertFalse(masks['F_BELOW50_RISING'][1])
        self.assertFalse(masks['F_ABOVE50_RISING'][1])

    def test_nan_prior_is_not_a_start_and_no_lookahead_in_event_masks(self):
        f=context([np.nan,1,-1,1])
        masks=study.events(f)
        self.assertFalse(masks['C_START'][1])
        for key,mask in masks.items():
            np.testing.assert_equal(mask[:3],study.events(context([np.nan,1,-1]))[key])


class OutcomeTests(unittest.TestCase):
    def fixture(self,side):
        return dict(frame=np.asarray([[0,100,1000,1,100,10,4],[data.WEEK,100,110,90,105,10,4],
                                     [2*data.WEEK,105,120,80,90,10,4]],float),ao_side=np.asarray([side,side,side]))

    def test_green_red_signed_returns_and_event_candle_excluded(self):
        green=study.outcomes(self.fixture(1),1)
        red=study.outcomes(self.fixture(-1),1)
        self.assertAlmostEqual(green['signed'][0],5)
        self.assertAlmostEqual(red['signed'][0],-5)
        self.assertAlmostEqual(green['mfe'][0],10)
        self.assertAlmostEqual(green['mae'][0],10)
        self.assertAlmostEqual(green['max_move'][0],10)
        self.assertEqual(green['hit'][0],1)
        self.assertEqual(red['hit'][0],0)
        self.assertEqual(green['up'][0],1)

    def test_future_extrema_and_terminal_magnitude_are_separate(self):
        result=study.outcomes(self.fixture(-1),2)
        self.assertAlmostEqual(result['signed'][0],10)
        self.assertAlmostEqual(result['absolute'][0],10)
        self.assertAlmostEqual(result['mfe'][0],20)
        self.assertAlmostEqual(result['mae'][0],20)
        self.assertEqual(result['terminal_ge_15'][0],0)
        self.assertEqual(result['move_ge_15'][0],1)

    def test_incomplete_horizons_are_censored_never_zero_filled(self):
        result=study.outcomes(self.fixture(1),2)
        self.assertTrue(np.isnan(result['forward'][1:]).all())

    def test_flat_ao_has_unknown_signed_outcome_not_a_fake_win(self):
        result=study.outcomes(self.fixture(np.nan),1)
        self.assertTrue(np.isnan(result['signed'][0]))
        self.assertTrue(np.isnan(result['hit'][0]))
        self.assertTrue(np.isfinite(result['max_move'][0]))

    def test_temporal_control_uses_only_matured_prior_outcomes(self):
        grid=np.arange(30)
        out={key:np.arange(34,dtype=float) for key in ('forward','absolute','max_move','up','down')}
        controls=study.past_controls(out,grid,4)
        self.assertTrue(np.isnan(controls['forward'][14]))
        self.assertEqual(controls['forward'][15],np.mean(np.arange(12)))
        changed=copy.deepcopy(out)
        for value in changed.values(): value[12:]=9999
        self.assertEqual(study.past_controls(changed,grid,4)['forward'][15],controls['forward'][15])


class RobustnessTests(unittest.TestCase):
    def test_block_resampling_is_deterministic_and_preserves_sample_size(self):
        a=study.block_counts(37,50,123)
        np.testing.assert_equal(a,study.block_counts(37,50,123))
        self.assertTrue((a.sum(axis=1)==37).all())
        self.assertTrue((a.max(axis=1)>1).any())

    def test_bootstrap_median_matches_literal_resample_with_even_counts(self):
        values=np.asarray([1.,3.,7.])
        weights=np.asarray([[1,2,1],[0,0,0],[2,0,2]])
        med=study.bootstrap_median(values,np.ones(3,bool),weights)
        self.assertEqual(med[0],3)
        self.assertTrue(np.isnan(med[1]))
        self.assertEqual(med[2],4)

    def test_small_or_mostly_empty_bootstrap_has_no_confidence_interval(self):
        self.assertEqual(study.interval(np.arange(100,dtype=float),9),(None,None))
        self.assertEqual(study.interval(np.r_[np.arange(90),[np.nan]*10],30),(None,None))

    def test_contrast_uses_common_block_draws_and_trims_event_only(self):
        values=np.asarray([100.,2.,2.,1.,1.,1.])
        out=dict(absolute=values)
        event=np.asarray([1,1,1,0,0,0],bool)
        ref=~event
        row=study.contrast(out,np.arange(6),study.block_counts(6,30),event,ref,'absolute')
        self.assertAlmostEqual(row['difference'],values[:3].mean()-1)
        self.assertAlmostEqual(row['ex_best1_difference'],1)
        self.assertIsNone(row['ex_best3_difference'])

    def test_overlapping_identical_controls_have_exactly_zero_paired_lift(self):
        values=np.arange(30,dtype=float)
        mask=np.ones(30,bool)
        result=study.contrast(dict(absolute=values),np.arange(30),study.block_counts(30,50),mask,mask,'absolute')
        self.assertEqual(result['difference'],0)
        self.assertEqual((result['ci_low'],result['ci_high']),(0,0))

    def test_current_observation_never_uses_open_week_or_claims_validated_direction(self):
        f,_,_=study.features(bars(130*42+2),data.MONDAY+130*data.WEEK+2*data.FOUR_HOURS)
        current=study.current_observation(f,{})
        self.assertEqual(current['available_at'],study.iso(data.MONDAY+130*data.WEEK))
        self.assertEqual(current['strong_move_watch'],'UNKNOWN — NOT VALIDATED')
        self.assertIn('NOT PART OF VALIDATION',current['label'])


def robust_result():
    summaries=[]
    comparisons=[]
    for h in study.HORIZONS:
        for metric in ('absolute','max_move'):
            comparisons.append(dict(kind='MAGNITUDE',metric=metric,horizon=h,color='ALL',reference='B_FALLING',
                n_event=100,n_reference=100,difference=1.,ci_low=.5,ci_high=1.5,ex_best3_difference=.2))
        for color in ('GREEN','RED'):
            for metric,reference in (('signed','A_RISING_CONSTANT_SIDE'),('hit','A_RISING_CONSTANT_SIDE'),('signed','SAME_COLOR')):
                comparisons.append(dict(kind='DIRECTION',metric=metric,horizon=h,color=color,reference=reference,
                    n_event=100,n_reference=100,difference=1.,ci_low=.5,ci_high=1.5,ex_best3_difference=.2))
            summaries.append(dict(scope='FULL',event='A_RISING',stratum=color,horizon=h,
                                  signed_ci_low=.5,signed_ex_best3_mean=.2))
        for epoch in study.EPOCHS:
            for event in ('A_RISING','B_FALLING','ALL'):
                for color in ('ALL','GREEN','RED'):
                    summaries.append(dict(scope=epoch,event=event,stratum=color,horizon=h,n=30,
                        absolute_mean=4 if event=='A_RISING' else 2,max_move_mean=6 if event=='A_RISING' else 3,
                        signed_mean=2 if event=='A_RISING' else 1,forward_mean=0,hit=.6,up=.5,down=.5))
    return dict(summaries=summaries,contrasts=comparisons)


class ConclusionTests(unittest.TestCase):
    def test_all_predeclared_checks_needed_for_robust_result(self):
        result=study.decision(robust_result())
        self.assertEqual(result['conclusion'],'ROBUST EXPANSION EFFECT — DIRECTION EFFECT ROBUST')

    def test_small_n_never_robust_even_if_means_and_intervals_positive(self):
        data=robust_result()
        data['contrasts'][0]['n_event']=29
        self.assertFalse(study.decision(data)['magnitude_robust'])

    def test_wide_interval_prevents_integration(self):
        data=robust_result()
        data['contrasts'][0]['ci_low']=-.1
        self.assertEqual(study.decision(data)['conclusion'],'INCONCLUSIVE — DO NOT INTEGRATE')

    def test_best_three_dependence_is_fragile(self):
        data=robust_result()
        data['contrasts'][0]['ex_best3_difference']=-.1
        self.assertEqual(study.decision(data)['conclusion'],'EXPANSION EFFECT FRAGILE')

    def test_contradictory_era_prevents_robust_magnitude(self):
        data=robust_result()
        row=study.lookup(data,'2023-2024','A_RISING','ALL',2)
        row['absolute_mean']=1
        self.assertEqual(study.decision(data)['conclusion'],'EXPANSION EFFECT FRAGILE')

    def test_one_direction_or_horizon_failure_prevents_directional_claim(self):
        data=robust_result()
        row=study.lookup(data,'FULL','A_RISING','RED',4)
        row['signed_ci_low']=-.1
        self.assertEqual(study.decision(data)['conclusion'],'ROBUST EXPANSION EFFECT — DIRECTION INCONCLUSIVE')


class PublishedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=Path(__file__).resolve().parent/'research/results/bitman_weekly_expansion'
        cls.f=study.load_snapshot(cls.directory)
        # Only versioned public CSV inputs: no network, account or original RAW.
        with patch('requests.sessions.Session.request',side_effect=AssertionError('NO NETWORK')):
            cls.reproduced=study.analyze(cls.f)
        cls.published=json.loads((cls.directory/'analysis.json').read_text('utf-8'))

    def test_public_artifact_hashes_and_no_sensitive_identifiers(self):
        manifest=json.loads((self.directory/'artifact_manifest.json').read_text('utf-8'))
        self.assertEqual(len(manifest['sha256']),8)
        for name,checksum in manifest['sha256'].items():
            raw=(self.directory/name).read_bytes().replace(b'\r\n',b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum)
            text=raw.decode('utf-8').lower()
            for forbidden in ('api_key','api_secret','bot_token','chat_id','account_id','authorization:','github_pat_','bitunix'):
                self.assertNotIn(forbidden,text)

    def test_all_published_summary_values_and_confidence_intervals_reproduce(self):
        with (self.directory/'summaries.csv').open(encoding='utf-8',newline='') as stream:
            expected=list(csv.DictReader(stream))
        self.assertEqual(len(expected),len(self.reproduced['summaries']))
        self.assertEqual(len(expected),1146)
        for actual,saved in zip(self.reproduced['summaries'],expected):
            for key,value in actual.items():
                if value is None:
                    self.assertEqual(saved[key],'')
                elif isinstance(value,str):
                    self.assertEqual(value,saved[key])
                else:
                    self.assertAlmostEqual(value,float(saved[key]),delta=1e-8)

    def test_all_published_contrasts_temporal_controls_and_influence_reproduce(self):
        for key in ('contrasts','temporal','influence'):
            expected=self.published[key]
            actual=self.reproduced[key]
            self.assertEqual(len(expected),len(actual))
            for a,b in zip(actual,expected):
                for name,value in a.items():
                    if isinstance(value,float):
                        self.assertAlmostEqual(value,b[name],delta=1e-8)
                    else:
                        self.assertEqual(value,b[name])

    def test_censoring_and_current_observation_exactly_match_published(self):
        self.assertEqual(np.count_nonzero(self.f['valid']),263)
        self.assertEqual(len(self.reproduced['observations']),262+261+259)
        last=int(self.f['available_at'][-1])
        self.assertTrue(all(r['available_at']<last for r in self.reproduced['observations']))
        self.assertEqual(study.current_observation(self.f,{}),self.published['current'])
        self.assertEqual(study.decision(self.reproduced),self.published['decision'])

    def test_complete_event_horizon_epoch_quadrant_and_adx_grid_is_published(self):
        rows=self.reproduced['summaries']
        for event in study.events(self.f):
            for h in study.HORIZONS:
                for color in study.strata(self.f):
                    self.assertTrue(any((r['scope'],r['event'],r['stratum'],r['horizon'])==('FULL',event,color,h) for r in rows))
        self.assertEqual(sum(r['scope']=='ADX_SECONDARY' for r in rows),72)
        self.assertEqual(sum(r['scope'].startswith('NONOVERLAP_') for r in rows),84)

    def test_report_is_deterministic_complete_and_keeps_observation_outside_validation(self):
        from research.bitman_weekly_reporting import generate
        text=generate(self.directory)
        self.assertEqual(text,(self.directory.parent/'BITMAN_WEEKLY_EXPANSION.md').read_text('utf-8'))
        for marker in ('## '+str(n)+'.' for n in range(1,18)):
            self.assertIn(marker,text)
        for marker in ('CURRENT OBSERVATION — NOT PART OF VALIDATION','TEST REUSED / NO VIRGIN HOLDOUT',
                       'NO INTEGRAR','INSUFFICIENT FOR CONCLUSION','TRADE AUTHORITY: NONE'):
            self.assertIn(marker,text)


if __name__=='__main__':
    unittest.main()
