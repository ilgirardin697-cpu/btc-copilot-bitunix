"""Actual source-derived coordinates; no trading outputs or price calibration."""
import copy
import json
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal as D
from pathlib import Path
from .model import PixelPoint,clone_pixels
from .render import reconstruction,drawing
from .source_review import registration_observations

HERE=Path(__file__).resolve().parent


class ActualSourceGeometryTests(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
        self.a,self.b=self.manifest['cases']

    def test_source_identifiers_and_sizes_are_exact(self):
        self.assertEqual(self.a['sha256'],'8cb3f56448834682d5195f7812d58cddc2bd193fe1f2184aa6256a6c23d8869a')
        self.assertEqual(self.b['sha256'],'15e018e4440e91187e2e8ef5fd97222b12880f95e07fe7ad4aa2ad19987af5ac')
        self.assertEqual(self.a['image_size'],[687,561]);self.assertEqual(self.b['image_size'],[485,436])

    def test_both_visible_heights_are_158(self):
        r=registration_observations(self.manifest)
        self.assertEqual((r['original_height_px'],r['copy_height_px']),(D(158),D(158)))

    def test_scene_translation_uses_six_box_corners(self):
        r=registration_observations(self.manifest)
        self.assertEqual(r['scene_translation_px'],[D(57),D(-20)])
        self.assertEqual(r['landmark_count'],6);self.assertEqual(r['max_absolute_landmark_residual_px'],0)

    def test_lower_anchor_predicts_observed_upper_endpoint(self):
        r=registration_observations(self.manifest)
        self.assertEqual(r['copy_translation_px'],[D(74),D(-66)])
        self.assertEqual(r['predicted_upper_px'],[D(333),D(81)])
        self.assertEqual(r['endpoint_residual_px'],[D(0),D(0)])

    def test_prediction_does_not_fit_observed_free_endpoint(self):
        changed=copy.deepcopy(self.manifest)
        changed['cases'][1]['observed_upper_copy']['upper']=[333,90]
        r=registration_observations(changed)
        self.assertEqual(r['predicted_upper_px'],[D(333),D(81)])
        self.assertEqual(r['endpoint_residual_px'],[D(0),D(9)])

    def test_original_circles_not_forced_onto_box_edges(self):
        self.assertEqual(self.a['original_upper'][1]-self.a['rectangles'][0]['bounds'][1],-4)
        self.assertEqual(self.a['original_lower'][1]-self.a['rectangles'][1]['bounds'][3],-4)

    def test_observed_support_inside_top_of_lower_box_not_on_border(self):
        center=self.b['observed_upper_copy']['lower'][1]
        top,bottom=self.b['rectangles'][1]['bounds'][1],self.b['rectangles'][1]['bounds'][3]
        self.assertEqual(center-top,10);self.assertGreater(center-7,top);self.assertLess(center+7,bottom)

    def test_original_not_falsely_marked_visible_in_second_frame(self):
        self.assertEqual(self.a['measurement_evidence'],'OBSERVED')
        self.assertIn('REGISTERED',self.b['measurement_evidence'])
        body,_=drawing(self.b)
        self.assertIn('A registrado de 01',body)

    def test_lower_projection_is_not_observed_and_all_hypotheses_retained(self):
        for case in (self.a,self.b):
            self.assertIsNone(case['observed_lower_copy'])
            self.assertEqual([x['id'] for x in case['lower_anchor_hypotheses']],['D_TOP','D_BOTTOM'])
        outputs=[]
        for h in self.b['lower_anchor_hypotheses']:
            point=lambda p:PixelPoint(self.b['case_id'],D(p[0]),D(p[1]))
            upper,lower=clone_pixels(point(self.b['original_upper']),point(self.b['original_lower']),point(h['point']),'DOWN')
            outputs.append(int(lower.y));self.assertEqual(lower.y-upper.y,158)
        self.assertEqual(outputs,[316,430])

    def test_scene_binding_does_not_bind_old_reference_setup(self):
        self.assertEqual(self.a['case_id'],self.b['case_id'])
        self.assertNotEqual(self.a['frame_id'],self.b['frame_id'])
        for c in (self.a,self.b):
            self.assertEqual(c['same_setup_as_old_levels'],'UNVERIFIED')
            self.assertIsNone(c['price_height']);self.assertFalse(c['confirmation_lines'])

    def test_vector_artifacts_reproduce_exactly(self):
        for i,case in enumerate((self.a,self.b),1):
            result=reconstruction(case);ET.fromstring(result)
            self.assertEqual(result,(HERE/f'artifacts/frame_{i:02}_geometry.svg').read_text(encoding='utf-8'))

    def test_no_exact_currency_or_operational_claim(self):
        r=registration_observations(self.manifest)
        self.assertIsNone(r['height_USDT']);self.assertFalse(r['price_calibration_verified'])
        self.assertFalse(r['observed_lower_projection']);self.assertEqual(r['operational_paper'],'BLOCKED')


if __name__=='__main__':unittest.main()
