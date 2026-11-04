"""Offline mechanics. Synthetic capture fixtures never count as prospective/TradingView evidence."""
import ast
import copy
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
try:
    import numpy as np
    import requests
except ModuleNotFoundError as exc:
    if exc.name not in ('numpy','requests'):raise
    raise unittest.SkipTest('Dedicated PRICE workflow installs numpy/requests; V8 remains dependency-free') from exc
from . import forward
from .core import HERE,ANCHORS,canonical,read_json,verify_freeze,predict,fit_structure,structure_predict,scores,interval
from .features import stamp,schedule,vector,reference_vectors,final_label,atr_series,HOUR,MINUTE
from .build import pine_function,scalar_export_check
from .parity import compare


def fixture(day=date(2026,11,5),outcome=2):
    s=schedule(day);h=np.array([[t,100,103,97,100] for t in range(s['asia']-500*HOUR,s['end'],HOUR)],float)
    m=np.array([[t,100,103,97,100] for t in range(s['radar'],s['end'],MINUTE)],float)
    if outcome in (0,1,-1):
        i=int((s['close']-s['radar'])/MINUTE);j=int(np.flatnonzero(h[:,0]==s['close'])[0])
        if outcome in (0,-1):m[i,2]=h[j,2]=110
        if outcome in (1,-1):m[i,3]=h[j,3]=90
    return h,m


def payload(day=date(2026,11,5),minute=0,x=None):
    frozen=verify_freeze();t=stamp(day,5)+minute*MINUTE
    if x is None:
        h,m=fixture(day);x=reference_vectors(day,h,m)[minute]
    return dict(protocol='IGOD_KILLZONE_PRICE_FORWARD_V1',protocol_hash=frozen['protocol_sha256'],version=frozen['model_version'],
        available_at=t,emitted_at=t+100,status='EXPERIMENTAL_NOT_VALIDATED',origin='PINE_REALTIME_UNATTESTED',
        minute=minute,features=list(x),research_probabilities=predict(x).tolist())


class FreezeTests(unittest.TestCase):
    def test_protocol_and_model_frozen(self):
        f=verify_freeze();self.assertEqual(f['protocol_sha256'],'892ec9aa89c4b1984eab46d6c20d97704379e022671ddc34c68227131e164289')
        self.assertEqual(f['model_sha256'],'db59d952e6c79da87adb7a31cba41a6ee3a5879a8e0c57638336e58f7be6a6d9')

    def test_PRICE_dict_exactly_parent(self):
        parent=read_json('../killzone_probability_radar/artifacts/model_validation.json')
        self.assertEqual(canonical(parent['models']['PRICE']),canonical(read_json('frozen_PRICE.json')))

    def test_prior_exactly_parent(self):
        parent=read_json('../killzone_probability_radar/artifacts/model_validation.json')
        self.assertEqual(parent['prior'],read_json('frozen_PRIOR.json'))

    def test_all_PR41_PR42_sources_and_results_unchanged(self):
        root=HERE.parents[1]
        for name,record in read_json('freeze_manifest.json')['protected_parent_files'].items():
            raw=(root/name).read_bytes()
            if record['normalize_lf']:raw=raw.replace(b'\r\n',b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),record['sha256'],name)

    def test_protected_production_unchanged(self):
        root=HERE.parents[1];guard=read_json('../alpha_arcanox_pine_v37/fixtures/protected_runtime_hashes.json')
        for name,expected in guard['files'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),expected,name)

    def test_six_features_only(self):
        self.assertEqual(read_json('frozen_PRICE.json')['indices'],list(range(6)))
        with self.assertRaisesRegex(ValueError,'SIX'):predict(np.ones(7))

    def test_actual_old_test_PRICE_results_exact(self):
        parent=read_json('../killzone_probability_radar/artifacts/model_validation.json')['partitions']['test']['PRICE']
        own=read_json('artifacts/historical_comparison.json')['partitions']['examined_test']['PRICE']
        self.assertEqual((own['brier'],own['logloss']),(parent['brier'],parent['logloss']))

    def test_no_training_PRICE_path(self):
        source=(HERE/'core.py').read_text(encoding='utf-8')
        self.assertNotIn('Adam',source);self.assertNotIn('gradient',source);self.assertNotIn('def fit(',source)


class ModelTests(unittest.TestCase):
    def setUp(self):self.a=np.load(HERE.parent/'killzone_probability_radar/artifacts/features_and_labels.npz')

    def test_parent_probabilities_bitwise(self):
        from ..killzone_probability_radar.model import predict as parent
        x=self.a['X'][::29];expected=parent(read_json('frozen_PRICE.json'),x)
        np.testing.assert_array_equal(predict(x[:,:,:6]),expected)

    def test_normalized_probabilities(self):
        p=predict(self.a['X'][::31,:,:6]);np.testing.assert_allclose(p.sum(axis=-1),1,rtol=0,atol=5e-16)
        self.assertTrue(np.all(p>=0));self.assertTrue(np.isfinite(p).all())

    def test_fixed_structure_train_only(self):
        mask=self.a['days']<='2023-12-30'
        actual=fit_structure(self.a['X'][mask,:,:6],self.a['Y'][mask])
        self.assertEqual(actual,read_json('artifacts/frozen_STRUCTURE.json'))
        self.assertEqual(actual['training_cycles'],722)

    def test_structure_weights_not_60_independent_samples(self):
        model=read_json('artifacts/frozen_STRUCTURE.json')
        n=sum(sum(r['cycle_equivalent_counts']) for r in model['rows'])
        self.assertAlmostEqual(n,722)

    def test_fixed_tercile_boundaries(self):
        model=read_json('artifacts/frozen_STRUCTURE.json');x=np.zeros((3,6));x[:,1]=[0,1/3,2/3]
        np.testing.assert_array_equal(structure_predict(x,model),[r['probabilities'] for r in model['rows']])

    def test_both_baselines_positive_historical_gain_not_forward(self):
        r=read_json('artifacts/historical_comparison.json');p=r['partitions']['examined_test']['PRICE']
        self.assertGreater(p['gains']['PRIOR']['brier_ci95'][0],0)
        self.assertGreater(p['gains']['STRUCTURE']['brier_ci95'][0],0)
        self.assertEqual(r['prospective']['observed_cycles'],0)

    def test_five_anchor_minutes_fixed(self):self.assertEqual(ANCHORS,[0,15,30,45,59])

    def test_three_outcomes_reported(self):
        p=read_json('artifacts/historical_comparison.json')['partitions']['examined_test']['PRICE']
        self.assertEqual([r['class_name'] for r in p['classes']],['SUPERIOR_FIRST','INFERIOR_FIRST','NEITHER'])
        self.assertEqual(sum(p['class_counts']),667)

    def test_grouped_intervals_deterministic(self):self.assertEqual(interval(np.arange(30)),interval(np.arange(30)))

    def test_arithmetic_mirror_is_not_platform_evidence(self):
        model=read_json('frozen_PRICE.json');x=self.a['X'][::137,::15,:6]
        actual=np.array([[scalar_export_check(model,v) for v in row] for row in x])
        np.testing.assert_allclose(actual,predict(x),rtol=0,atol=1e-12)
        self.assertEqual(read_json('artifacts/pine_parity_status.json')['actual_tradingview_records'],0)


class CausalityTests(unittest.TestCase):
    def test_clock_DST_summer_winter(self):
        self.assertEqual(stamp(date(2026,7,1),5)%(24*HOUR),9*HOUR)
        self.assertEqual(stamp(date(2026,11,5),5)%(24*HOUR),10*HOUR)

    def test_DST_missing02_not_repaired(self):
        s=schedule(date(2026,3,8));self.assertEqual(s['close']-s['london'],3*HOUR)
        h,m=fixture(date(2026,3,8))
        with self.assertRaisesRegex(ValueError,'DST'):reference_vectors(date(2026,3,8),h,m)

    def test_future_h1_and_minute_cannot_change_05_15(self):
        d=date(2026,11,5);s=schedule(d);h,m=fixture(d)
        before=reference_vectors(d,h,m);changed=m.copy();changed[15:,2]=200
        hchanged=h.copy();hchanged[h[:,0]>=s['radar'],2]=200
        after=reference_vectors(d,hchanged,changed)
        np.testing.assert_array_equal(before[:16],after[:16])

    def test_minute_zero_uses_no_open_minute(self):
        d=date(2026,11,5);h,m=fixture(d);before=reference_vectors(d,h,m)
        m[:,2]=200;np.testing.assert_array_equal(before[0],reference_vectors(d,h,m)[0])

    def test_no_minute60(self):
        d=date(2026,11,5);s=schedule(d);h,m=fixture(d)
        with self.assertRaisesRegex(ValueError,'PREFIX'):vector(h[:4],h[4:7],m[:60],6,60)

    def test_gap_intrabar_rejected(self):
        d=date(2026,11,5);h,m=fixture(d)
        with self.assertRaisesRegex(ValueError,'MISSING'):reference_vectors(d,h,np.delete(m,3,axis=0))

    def test_duplicate_intrabar_rejected(self):
        d=date(2026,11,5);h,m=fixture(d)
        with self.assertRaisesRegex(ValueError,'MISSING'):reference_vectors(d,h,np.insert(m,3,m[3],axis=0))

    def test_ATR_same_public_formula_as_parent(self):
        from ..killzone_probability_radar.dataset import indicators
        h,_=fixture();np.testing.assert_allclose(atr_series(h),indicators(h)[:,0],rtol=0,atol=0,equal_nan=True)

    def test_labels_after06_only_and_exclude20(self):
        d=date(2026,11,5);h,m=fixture(d);s=schedule(d)
        before=final_label(d,h,m,s['end']);self.assertEqual(before['class_index'],2)
        after=np.r_[m,[[s['end'],100,1000,1,100]]]
        self.assertEqual(final_label(d,h,after,s['end']),before)

    def test_label_cannot_mature_early(self):
        d=date(2026,11,5);h,m=fixture(d)
        with self.assertRaisesRegex(ValueError,'NOT_MATURE'):final_label(d,h,m,schedule(d)['end']-1)

    def test_all_outcomes_and_ambiguity(self):
        d=date(2026,11,5)
        for expected in (0,1,2,-1):
            h,m=fixture(d,expected);self.assertEqual(final_label(d,h,m,schedule(d)['end'])['class_index'],expected)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.path=Path(temp.name)/'journal.jsonl'

    def capture(self,p):
        with patch.object(forward,'now_ms',return_value=p['emitted_at']+100):return forward.capture(self.path,p)

    def test_first_capture_and_replay(self):
        self.assertTrue(self.capture(payload()));self.assertTrue(forward.read(self.path)[0]['eligible_capture'])

    def test_dedupe_reload_same_forecast_later_emitted(self):
        p=payload();self.capture(p);old=self.path.read_bytes();p['emitted_at']+=300
        self.assertFalse(self.capture(p));self.assertEqual(old,self.path.read_bytes())

    def test_conflicting_revision_never_rewrites(self):
        p=payload();self.capture(p);old=self.path.read_bytes();p['features'][2]+=.1;p['research_probabilities']=predict(p['features']).tolist()
        with self.assertRaisesRegex(ValueError,'CONFLICTING'):self.capture(p)
        self.assertEqual(old,self.path.read_bytes())

    def test_late_capture_kept_but_never_forward(self):
        p=payload()
        with patch.object(forward,'now_ms',return_value=schedule(date(2026,11,5))['end']):forward.capture(self.path,p)
        r=forward.read(self.path)[0];self.assertFalse(r['eligible_capture']);self.assertIn('LATE_CAPTURE_NOT_FORWARD',r['ineligible_reasons'])

    def test_past_market_history_never_forward(self):
        p=payload(date(2026,10,1));self.capture(p);self.assertFalse(forward.read(self.path)[0]['eligible_capture'])

    def test_wrong_model_or_protocol_rejected(self):
        p=payload();p['version']='OTHER'
        with self.assertRaisesRegex(ValueError,'MODEL'):self.capture(p)

    def test_future_emission_rejected(self):
        p=payload()
        with patch.object(forward,'now_ms',return_value=p['available_at']-1):
            with self.assertRaisesRegex(ValueError,'FUTURE'):forward.capture(self.path,p)

    def test_wrong_probability_recorded_as_ineligible(self):
        p=payload();p['research_probabilities']=[.2,.3,.5];self.capture(p)
        self.assertIn('ACTUAL_PROBABILITY_PARITY_MISMATCH',forward.read(self.path)[0]['ineligible_reasons'])

    def test_sensitive_extra_field_rejected(self):
        p=payload();p['api_key']='PRIVATE'
        with self.assertRaisesRegex(ValueError,'FIELDS'):self.capture(p)

    def test_truncation_no_repair(self):
        self.capture(payload());raw=self.path.read_bytes()[:-1];self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'INVALID'):forward.read(self.path)
        self.assertEqual(raw,self.path.read_bytes())

    def test_tampering_no_repair(self):
        self.capture(payload());raw=self.path.read_bytes().replace(b'PREDICTION',b'CORRUPTION');self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'INVALID'):forward.read(self.path)
        self.assertEqual(raw,self.path.read_bytes())

    def test_fsync_failure_not_reported_success(self):
        with patch.object(forward.os,'fsync',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.capture(payload())

    def test_settle_appends_does_not_change_prediction(self):
        d=date(2026,11,5);h,m=fixture(d);p=payload(d);self.capture(p);raw=self.path.read_bytes()
        with patch.object(forward,'now_ms',return_value=schedule(d)['end']+100):self.assertTrue(forward.settle(self.path,d.isoformat(),h,m,{'TEST_FIXTURE':'SYNTHETIC'}))
        self.assertTrue(self.path.read_bytes().startswith(raw));self.assertEqual(len(forward.read(self.path)),2)

    def test_settle_dedupe(self):
        d=date(2026,11,5);h,m=fixture(d);self.capture(payload(d))
        with patch.object(forward,'now_ms',return_value=schedule(d)['end']+100):
            self.assertTrue(forward.settle(self.path,d.isoformat(),h,m,{}));self.assertFalse(forward.settle(self.path,d.isoformat(),h,m,{}))

    def test_five_anchors_and_verified_market_required(self):
        d=date(2026,11,5);h,m=fixture(d)
        for i in ANCHORS:self.capture(payload(d,i))
        with patch.object(forward,'now_ms',return_value=schedule(d)['end']+100):forward.settle(self.path,d.isoformat(),h,m,{})
        days,y,p,prior,structure,excluded=forward.cohort(forward.read(self.path))
        self.assertEqual(days,[d.isoformat()]);self.assertEqual(p.shape,(1,5,3));self.assertFalse(excluded)

    def test_missing_anchor_excludes_cycle(self):
        d=date(2026,11,5);h,m=fixture(d);self.capture(payload(d))
        with patch.object(forward,'now_ms',return_value=schedule(d)['end']+100):forward.settle(self.path,d.isoformat(),h,m,{})
        self.assertEqual(len(forward.cohort(forward.read(self.path))[1]),0)

    def test_no_early_approval(self):
        result=forward.evaluate([]);self.assertEqual(result['decision'],'B');self.assertFalse(result['publication_enabled'])

    def test_no_automatic_approval_from_calendar(self):
        with patch.object(forward,'now_ms',return_value=stamp(date(2027,6,1),0)):
            r=forward.evaluate([])
        self.assertEqual(r['decision'],'B');self.assertIn('INSUFFICIENT',r['status'])

    def test_actual_logs_absent_not_synthetic_parity(self):
        self.assertEqual(compare('')['actual_log_records'],0)

    def test_technical_parity_not_sufficient_for_publication(self):
        p=payload();r=compare('IGOD_PRICE_RADAR_V1='+json.dumps(p))
        self.assertTrue(r['rows'][0]['probability_pass']);self.assertIsNone(r['rows'][0]['market_feature_pass']);self.assertFalse(r['publication_enabled'])


class ArchitectureTests(unittest.TestCase):
    def test_PRICE_Pine_has_no_other_indicators(self):
        p=(HERE/'I_GOD_Killzone_Probability_Radar.pine').read_text(encoding='utf-8')
        for forbidden in ('ta.sma','ta.dmi','adx14','plusDI','minusDI','bbwp','change4h','request.security('):self.assertNotIn(forbidden,p)
        self.assertIn('atr14[1]',p);self.assertIn('request.security_lower_tf',p)
        self.assertIn(pine_function(read_json('frozen_PRICE.json')),p)

    def test_Pine_publication_locked_and_logging_explicit(self):
        p=(HERE/'I_GOD_Killzone_Probability_Radar.pine').read_text(encoding='utf-8')
        self.assertIn('const bool MODEL_VALIDATED = false',p);self.assertIn('EXPERIMENTAL_NOT_VALIDATED',p)
        self.assertIn('research_probabilities',p);self.assertIn('barstate.isrealtime and logRealtime',p)
        self.assertNotIn('alert(',p);self.assertNotIn('strategy(',p)

    def test_no_execution_import_or_mutating_network(self):
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):continue
            for n in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                    self.assertNotIn(n.func.attr,('post','put','patch','delete','create_order','cancel_order','place_order'))
                if isinstance(n,ast.ImportFrom):
                    self.assertFalse(any(x in (n.module or '') for x in ('guardian','bitunix','Telegram','v8_executor','frozen.indicators')))

    def test_no_clock_override_CLI(self):
        self.assertNotIn("add_argument('--asof'",(HERE/'forward.py').read_text())
        self.assertNotIn("add_argument('--now'",(HERE/'forward.py').read_text())

    def test_artifact_hashes(self):
        for name,r in read_json('artifacts/artifact_manifest.json').items():
            raw=(HERE/'artifacts'/name).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),r['sha256'],name)


class ProspectiveDecisionTests(unittest.TestCase):
    def records(self,good=True):
        # Artificial probability arrays ONLY to test gate control flow, never evidence.
        records=[];day=date(2026,11,5)
        for n in range(181):
            d=day+timedelta(days=n);label=n%3;verified={}
            price=np.full(3,.01);price[label if good else (label+1)%3]=.98
            for minute in ANCHORS:
                rid=f'SYNTHETIC_GATE_TEST:{d}:{minute}';verified[rid]=True
                records.append(dict(record_type='PREDICTION',record_id=rid,cycle=d.isoformat(),eligible_capture=True,
                    payload=dict(minute=minute),python_probabilities=price.tolist(),prior_probabilities=[1/3]*3,
                    structure_probabilities=[1/3]*3))
            records.append(dict(record_type='OUTCOME',cycle=d.isoformat(),outcome=dict(class_index=label),feature_verified=verified))
        return records

    def test_sufficient_fixed_cohort_failure_returns_C(self):
        with patch.object(forward,'now_ms',return_value=stamp(date(2027,6,1),0)):
            r=forward.evaluate(self.records(False))
        self.assertEqual(r['decision'],'C');self.assertFalse(r['publication_enabled']);self.assertIn('CALIBRATION',r['gate_failures'])

    def test_statistical_pass_never_self_certifies_A_or_TV_parity(self):
        with patch.object(forward,'now_ms',return_value=stamp(date(2027,6,1),0)):
            r=forward.evaluate(self.records(True))
        self.assertFalse(r['gate_failures']);self.assertEqual(r['decision'],'B');self.assertFalse(r['publication_enabled'])
        self.assertIn('PARITY_REVIEW',r['status'])

    def test_cannot_pass_before_fixed_end_even_with_artificial_full_data(self):
        with patch.object(forward,'now_ms',return_value=stamp(date(2027,2,1),0)):
            r=forward.evaluate(self.records(True))
        self.assertEqual(r['status'],'COHORT_NOT_FINISHED_NO_EARLY_APPROVAL');self.assertEqual(r['decision'],'B')


if __name__=='__main__':unittest.main()
