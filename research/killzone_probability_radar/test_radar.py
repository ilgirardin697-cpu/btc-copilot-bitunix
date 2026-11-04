"""Offline mechanics and leakage tests. Never presented as independent TradingView evidence."""
import ast
import copy
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
from .data import HERE, HOUR, MINUTE, archive_rows, protocol_hash
from .dataset import build, features, label, schedule, stamp, window, contiguous, indicators
from .model import fit, predict, softmax, losses, ci, calibration
from .build import pine_function
from .parity import pine_arithmetic, compare
from .journal import append, read, digest, validate_prediction


class ClockTests(unittest.TestCase):
    def test_summer_05_is_09_utc(self):
        self.assertEqual(schedule(date(2026, 7, 1))['radar'], 1782896400000)

    def test_winter_05_is_10_utc(self):
        self.assertEqual(stamp(date(2026, 11, 2), 5)-stamp(date(2026, 11, 2), 0), 5*HOUR)
        self.assertEqual((stamp(date(2026, 11, 2), 5)//HOUR) % 24, 10)

    def test_dst_spring_is_missing_london_hour(self):
        s = schedule(date(2026, 3, 8)); self.assertEqual(s['close']-s['london'], 3*HOUR)

    def test_dst_fall_london_still_four(self):
        s = schedule(date(2026, 11, 1)); self.assertEqual(s['close']-s['london'], 4*HOUR)
        self.assertEqual(s['radar'] % (24*HOUR), 10*HOUR)

    def test_asia_four_even_dst(self):
        for d in (date(2026, 3, 8), date(2026, 11, 1)):
            s = schedule(d); self.assertEqual(s['asia_end']-s['asia'], 4*HOUR)

    def test_label_window_fourteen_hours(self):
        for d in (date(2026, 3, 8), date(2026, 11, 1), date(2025, 7, 1)):
            s = schedule(d); self.assertEqual(s['end']-s['close'], 14*HOUR)


class DataTests(unittest.TestCase):
    def archive(self, rows):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); p=Path(t.name)/'public.zip'
        with zipfile.ZipFile(p, 'w') as z:z.writestr('public.csv', '\n'.join(','.join(map(str,r)) for r in rows))
        return p

    def row(self, t=1640995200000, unit=1):
        return [t*unit, 100, 110, 90, 101, 3, (t+MINUTE)*unit-1, 300, 2, 1, 100, 0]

    def test_ms_before_2025(self):
        r=archive_rows(self.archive([self.row()]), '1m', '2022-01'); self.assertEqual(r[0,0],1640995200000)

    def test_us_since_2025(self):
        t=1735689600000;r=archive_rows(self.archive([self.row(t,1000)]),'1m','2025-01');self.assertEqual(r[0,0],t)

    def test_early_archive_close_not_repaired(self):
        r=self.row(); r[6]-=123; quality=[]
        b=archive_rows(self.archive([r]),'1m','2022-01',quality)
        self.assertEqual(len(b),0); self.assertEqual(quality[0]['original_close_time'],r[6])

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,'TIME_ORDER'):archive_rows(self.archive([self.row(),self.row()]),'1m','2022-01')

    def test_bad_schema(self):
        with self.assertRaisesRegex(ValueError,'SCHEMA'):archive_rows(self.archive([self.row()[:-1]]),'1m','2022-01')

    def test_gap_not_contiguous(self):
        rows=np.array([[0,1,1,1,1],[2*MINUTE,1,1,1,1]])
        self.assertFalse(contiguous(rows,0,3*MINUTE,MINUTE))

    def test_window_exclusive_end(self):
        rows=np.array([[i*MINUTE,1,1,1,1] for i in range(4)])
        self.assertEqual(len(window(rows,0,3*MINUTE)),3)


class CausalFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[i*HOUR,100,110,90,102] for i in range(4)],float)
        self.l=np.array([[(6+i)*HOUR,102,112,95,104] for i in range(3)],float)
        self.m=np.array([[9*HOUR+i*MINUTE,104,113,96,105] for i in range(60)],float)
        self.static=np.array([3,2,1,20,1,25,15,40,-3,5],float)

    def test_zero_does_not_use_open_h1(self):
        x=features(self.a,self.l,self.m[:0],self.static,0);self.assertEqual(x[0],0)
        changed=self.m.copy();changed[:]=1e9
        np.testing.assert_array_equal(x,features(self.a,self.l,changed[:0],self.static,0))

    def test_prefix_invariance(self):
        for n in (1,15,30,59):
            x=features(self.a,self.l,self.m[:n],self.static,n)
            changed=self.m.copy();changed[n:,2]=1e8
            np.testing.assert_array_equal(x,features(self.a,self.l,changed[:n],self.static,n))

    def test_future_targets_not_an_input(self):
        self.assertNotIn('target',features.__code__.co_varnames)
        self.assertNotIn('outcome',features.__code__.co_varnames)

    def test_minute60_not_predicted(self):
        with self.assertRaisesRegex(ValueError,'PREFIX'):features(self.a,self.l,self.m,self.static,60)

    def test_missing_prefix_rejected(self):
        with self.assertRaisesRegex(ValueError,'PREFIX'):features(self.a,self.l,self.m[:14],self.static,15)

    def test_indicators_static_within_hour(self):
        a=features(self.a,self.l,self.m[:5],self.static,5)
        b=features(self.a,self.l,self.m[:40],self.static,40)
        np.testing.assert_array_equal(a[6:],b[6:])

    def test_real_dataset_labels_cannot_change_predictor_prefix(self):
        a=np.load(HERE/'artifacts/features_and_labels.npz')
        self.assertEqual(a['X'].shape,(1755,60,14)); self.assertEqual(a['Y'].shape,(1755,))
        self.assertTrue(np.isfinite(a['X']).all())

    def test_full_build_future_append_invariance(self):
        day=date(2022,1,8);s=schedule(day)
        start=stamp(date(2021,12,20),0)
        h=np.array([[t,100+np.sin(t/HOUR),103,97,100] for t in range(start,s['end']+HOUR,HOUR)])
        m=np.array([[t,100,103,97,100] for t in range(s['radar'],s['end'],MINUTE)])
        # Make H1/minute OHLC exact in covered windows; past seed remains nonflat.
        mask=h[:,0]>=s['radar'];h[mask,1]=100
        before=build(h,m,day,day)
        later=np.r_[h,[[s['end']+HOUR,100,1000,1,999]]]
        after=build(later,m,day,day)
        np.testing.assert_array_equal(before[0],after[0]);self.assertEqual(before[3],after[3])
        self.assertEqual(len(before[0]),1)


class LabelTests(unittest.TestCase):
    def test_upper_first(self):
        b=np.array([[0,100,112,95,108],[MINUTE,100,105,85,90]])
        self.assertEqual(label(b,110,90),(0,0))

    def test_lower_first(self):
        b=np.array([[0,100,105,85,90],[MINUTE,100,112,95,108]])
        self.assertEqual(label(b,110,90),(1,0))

    def test_neither(self):
        self.assertEqual(label(np.array([[0,100,105,95,101]]),110,90),(2,None))

    def test_same_minute_ambiguous_not_neither(self):
        self.assertEqual(label(np.array([[0,100,112,88,101]]),110,90),(-1,0))

    def test_both_later_does_not_erase_first(self):
        self.assertEqual(label(np.array([[0,100,111,95,101],[MINUTE,100,120,80,101]]),110,90),(0,0))

    def test_empty_labels_fail(self):
        with self.assertRaises(ValueError):label([],110,90)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.a=np.load(HERE/'artifacts/features_and_labels.npz')
        self.r=json.loads((HERE/'artifacts/model_validation.json').read_text())
        self.m=self.r['models'][self.r['selected_on_validation']]

    def test_softmax_sums_one_and_finite(self):
        p=softmax(np.array([[10000,9999,-10000.]]));self.assertAlmostEqual(float(p.sum()),1);self.assertTrue(np.isfinite(p).all())

    def test_multiclass_brier_definition(self):
        p=np.array([[[1.,0,0]]*60]);b,l=losses(p,np.array([0]));self.assertEqual(float(b.sum()),0);self.assertEqual(float(l.sum()),0)

    def test_scalar_mirror_explicitly_not_runtime_parity(self):
        x=self.a['X'][:20,::11];p=predict(self.m,x)
        q=np.array([[pine_arithmetic(self.m,v) for v in row] for row in x])
        np.testing.assert_allclose(p,q,rtol=0,atol=1e-12)
        r=json.loads((HERE/'artifacts/pine_comparison.json').read_text());self.assertEqual(r['actual_tradingview_records_compared'],0)

    def test_generation_reuses_exact_coefficients(self):
        source=(HERE/'I_GOD_Killzone_Probability_Radar.pine').read_text(encoding='utf-8')
        self.assertIn(pine_function(self.m),source)

    def test_optimizer_converged_all_four(self):
        self.assertTrue(all(m['converged'] for m in self.r['models'].values()))

    def test_standardization_train_only(self):
        train=self.a['days']<='2023-12-30';ix=self.m['indices']
        x=self.a['X'][train][:,:,ix].reshape(-1,len(ix))
        np.testing.assert_allclose(x.mean(axis=0),self.m['mean'],rtol=1e-13)

    def test_selection_validation_only(self):
        val=self.r['partitions']['validation']
        selected=min(self.r['models'],key=lambda k:val[k]['brier'])
        self.assertEqual(selected,self.r['selected_on_validation'])

    def test_no_probabilities_if_gate_fails(self):
        self.assertFalse(self.r['historical_gate_passed']);self.assertFalse(self.r['visible_probabilities_allowed'])
        self.assertEqual(self.r['model_status'],'NO VALIDADO')

    def test_cycle_bootstrap_deterministic(self):
        self.assertEqual(ci(np.arange(30)),ci(np.arange(30)))

    def test_partition_n_counts_cycles_not_minutes(self):
        self.assertEqual(self.r['partitions']['test']['PRICE']['cycles'],667)
        self.assertEqual(self.r['partitions']['test']['PRICE']['predictions'],667*60)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'capture.jsonl'
        self.p=dict(version='TEST',available_at=stamp(date(2026,11,2),5),emitted_at=stamp(date(2026,11,2),5)+1000,
                    minute=0,status='NO VALIDADO',features=[0.]*14,probabilities=None)

    def test_append_and_replay(self):
        self.assertTrue(append(self.path,self.p));self.assertEqual(len(read(self.path)),1)

    def test_duplicate_no_write(self):
        append(self.path,self.p);raw=self.path.read_bytes();self.assertFalse(append(self.path,self.p));self.assertEqual(raw,self.path.read_bytes())

    def test_conflicting_existing_prediction_no_rewrite(self):
        append(self.path,self.p);q=copy.deepcopy(self.p);q['features'][0]=1
        with self.assertRaisesRegex(ValueError,'CONFLICTING'):append(self.path,q)

    def test_tamper_never_repaired(self):
        append(self.path,self.p);r=self.path.read_text().replace('TEST','FAKE');self.path.write_text(r)
        with self.assertRaisesRegex(ValueError,'INVALID'):read(self.path)
        self.assertEqual(self.path.read_text(),r)

    def test_truncation_never_repaired(self):
        append(self.path,self.p);raw=self.path.read_bytes()[:-1];self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'INVALID'):read(self.path)

    def test_no_fake_validated_probabilities(self):
        self.p['probabilities']=[.2,.3,.5]
        with self.assertRaisesRegex(ValueError,'GATE'):validate_prediction(self.p)

    def test_no_fields_with_secrets(self):
        self.p['token']='PRIVATE'
        with self.assertRaisesRegex(ValueError,'FIELDS'):validate_prediction(self.p)

    def test_future_minute_rejected(self):
        self.p['emitted_at']=self.p['available_at']-1
        with self.assertRaisesRegex(ValueError,'CAUSAL'):validate_prediction(self.p)


class ArchitectureTests(unittest.TestCase):
    def test_protocol_is_frozen(self):
        self.assertEqual(protocol_hash(),'23e8d5ce83b0fae2ace74dcc1e789d27cb1e6764b513ecb059911268fb6edad1')

    def test_protected_sources_unchanged(self):
        root=HERE.parents[1]
        guard=json.loads((HERE.parent/'alpha_arcanox_pine_v37/fixtures/protected_runtime_hashes.json').read_text())
        for name,expected in guard['files'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),expected,name)

    def test_original_killzone_unchanged(self):
        p=HERE.parent/'alpha_arcanox_pine_v37/source/Killzone_H1_v3_7_Lite.txt'
        self.assertEqual(hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'058532c5c7964eefa3993b8aae761aef7598a542c7e43c7469ad0531f39e03a7')

    def test_no_execution_paths_or_credentials(self):
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):continue
            source=path.read_text(encoding='utf-8')
            for n in ast.walk(ast.parse(source)):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                    self.assertNotIn(n.func.attr,('post','put','patch','delete','create_order','place_order','cancel_order'))
                if isinstance(n,ast.ImportFrom):
                    self.assertFalse(any(x in (n.module or '') for x in ('guardian','bitunix','v8_executor','Telegram')))

    def test_pine_gates_and_causal_order(self):
        p=(HERE/'I_GOD_Killzone_Probability_Radar.pine').read_text(encoding='utf-8')
        self.assertIn('const bool MODEL_VALIDATED = false',p);self.assertIn('request.security_lower_tf',p)
        self.assertIn('tc < time_close and tc <= cutoff',p)
        self.assertLess(p.index('if radarHour'),p.index('if identityOK and barstate.isconfirmed'))
        self.assertIn('close[1] - close[2]',p)
        self.assertIn('f_segmentRma',p);self.assertIn('mathBars >= 107',p)
        self.assertNotIn('strategy(',p);self.assertNotIn('alert(',p);self.assertNotIn('alertcondition(',p)
        self.assertIn('barstate.isrealtime and logRealtime',p)
        self.assertNotIn('input.bool(true, "Activar probabilidades',p)

    def test_all_artifact_checksums(self):
        manifest=json.loads((HERE/'artifacts/artifact_manifest.json').read_text())
        for name,row in manifest.items():
            raw=(HERE/'artifacts'/name).read_bytes()
            self.assertEqual(len(raw),row['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'],name)


if __name__ == '__main__':
    unittest.main()
