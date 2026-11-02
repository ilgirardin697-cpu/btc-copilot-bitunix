"""Geometry contracts, case separation and frozen parent protection only."""
import ast
import copy
import hashlib
import inspect
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal as D
from pathlib import Path
from .. import core
from .model import (PriceMark,Measurement,project,project_all_hypotheses,
                    compare_verified_label,PixelPoint,clone_pixels)
from .render import comparison,save_comparison

HERE=Path(__file__).resolve().parent


def mark(name,value,case='SYNTHETIC_CASE',evidence='OBSERVED_PRICE'):
    return PriceMark(case,name,None if value is None else D(value),evidence)


class GeometryTests(unittest.TestCase):
    def setUp(self):self.m=Measurement(mark('upper','120'),mark('lower','100'))

    def test_vertical_price_height_only(self):self.assertEqual(self.m.height,D(20))

    def test_upper_copy_supports_lower_circle(self):
        r=project(self.m,mark('inside_lower_box','108'),'UP')
        self.assertEqual((r.support_circle,r.free_circle,r.free_endpoint_price),('LOWER','UPPER',D(128)))
        self.assertIsNone(r.indicator_level)

    def test_lower_copy_supports_upper_circle(self):
        r=project(self.m,mark('inside_upper_box','115'),'DOWN')
        self.assertEqual((r.support_circle,r.free_circle,r.free_endpoint_price),('UPPER','LOWER',D(95)))

    def test_no_high_low_in_projection_inputs(self):
        self.assertEqual(tuple(inspect.signature(project).parameters),('measurement','anchor','direction'))
        self.assertFalse(hasattr(self.m,'at'))

    def test_missing_circle_prices_do_not_become_pixels_or_global_extremes(self):
        m=Measurement(mark('upper',None),mark('lower',None))
        r=project(m,mark('anchor',None),'UP')
        self.assertIsNone(m.height);self.assertIsNone(r.free_endpoint_price)

    def test_hypothesis_never_becomes_observed_target(self):
        r=project(self.m,mark('edge_candidate','108',evidence='HYPOTHESIS'),'UP')
        self.assertEqual(r.status,'CONDITIONAL_ANCHOR_HYPOTHESIS')
        self.assertIsNone(r.indicator_level)

    def test_anchor_alternatives_preserved_without_best_fit_selection(self):
        anchors=[mark('edge','108',evidence='HYPOTHESIS'),mark('interior','107',evidence='HYPOTHESIS')]
        a=project_all_hypotheses(self.m,anchors,'UP')
        b=project_all_hypotheses(self.m,list(reversed(anchors)),'UP')
        self.assertEqual([p.anchor.name for p in a],['edge','interior'])
        self.assertEqual(tuple(reversed(a)),b)

    def test_mixed_setup_measurement_rejected(self):
        with self.assertRaisesRegex(ValueError,'MIXED'):Measurement(mark('top','120'),mark('bottom','100',case='OTHER'))

    def test_mixed_setup_anchor_rejected(self):
        with self.assertRaisesRegex(ValueError,'MIXED'):project(self.m,mark('anchor','108',case='OLD_LABEL_SETUP'),'UP')

    def test_old_labels_not_compared_to_new_geometry(self):
        r=project(self.m,mark('anchor','108'),'UP')
        with self.assertRaisesRegex(ValueError,'MIXED'):
            compare_verified_label(r,mark('SUPERIOR','78653.44',case='ALPHA_LABEL_REFERENCE_78285_77517'))

    def test_no_automatic_endpoint_to_indicator_binding(self):
        r=project(self.m,mark('anchor','108'),'UP')
        label=mark('SUPERIOR','128')
        self.assertIsNone(compare_verified_label(r,label)['difference'])
        self.assertIsNone(compare_verified_label(r,label,same_setup_verified=True)['difference'])

    def test_confirmed_same_setup_comparison_has_no_fit(self):
        r=project(self.m,mark('anchor','108'),'UP')
        check=compare_verified_label(r,mark('SUPERIOR','129'),same_setup_verified=True,endpoint_identity_verified=True)
        self.assertEqual(check['difference'],D(-1));self.assertEqual(r.free_endpoint_price,D(128))

    def test_bad_circle_order_and_nan_rejected(self):
        for top,bottom in [('100','100'),('99','100'),('NaN','100')]:
            with self.assertRaises(ValueError):Measurement(mark('top',top),mark('bottom',bottom))

    def test_exact_vertical_pixel_segment_is_valid(self):
        u=PixelPoint('X',D(10),D(20));l=PixelPoint('X',D(10),D(80));c=PixelPoint('X',D(30),D(100))
        a,b=clone_pixels(u,l,c,'UP')
        self.assertEqual((a.x,a.y,b.x,b.y),(D(30),D(40),D(30),D(100)))

    def test_slight_tilt_copy_keeps_full_apparent_vector(self):
        u=PixelPoint('X',D(11),D(20));l=PixelPoint('X',D(10),D(80));c=PixelPoint('X',D(30),D(100))
        for direction in ('UP','DOWN'):
            a,b=clone_pixels(u,l,c,direction)
            self.assertEqual((a.x-b.x,a.y-b.y),(u.x-l.x,u.y-l.y))

    def test_pixel_case_mixing_rejected(self):
        with self.assertRaisesRegex(ValueError,'MIXED'):
            clone_pixels(PixelPoint('X',D(1),D(2)),PixelPoint('X',D(1),D(4)),PixelPoint('Y',D(3),D(5)),'UP')


class EvidenceTests(unittest.TestCase):
    def test_parent_sources_and_results_unchanged(self):
        ledger=json.loads((HERE/'frozen_parent_sources.json').read_text(encoding='utf-8'))
        package=HERE.parent
        for name,expected in ledger['sha256'].items():
            self.assertEqual(hashlib.sha256((package/name).read_bytes()).hexdigest(),expected,name)

    def test_no_level_formula_activated(self):self.assertFalse(core.APPROVED_FORMULA_IDS)

    def test_missing_new_images_stay_explicit_not_replaced_by_old_case(self):
        data=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
        for c in data['cases']:
            if c['status']=='AWAITING_ORIGINAL_IMAGE':
                self.assertIsNone(c['image']);self.assertIsNone(c['original_upper'])
                with self.assertRaisesRegex(ValueError,'MISSING'):comparison(c,Path('not_a_source.jpg'))

    def test_render_refuses_output_with_raw_sources_in_tracked_directory(self):
        with self.assertRaisesRegex(ValueError,'GITIGNORED'):
            save_comparison({},Path('unknown.jpg'),HERE/'bad.svg')

    def test_annotation_renderer_keeps_all_clones_and_hash_checks(self):
        # Tiny fake bytes are only a string/geometry control, NOT an image evidence claim.
        raw=b'SYNTHETIC_IMAGE_BYTES_NOT_MARKET_EVIDENCE'
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'control.png';p.write_bytes(raw)
            case=dict(case_id='ARTIFICIAL',image=p.name,sha256=hashlib.sha256(raw).hexdigest(),image_size=[100,200],
                original_upper=[50,20],original_lower=[50,120],upper_anchor_hypotheses=[
                    dict(id='H1',feature='SYNTHETIC_EDGE',point=[60,30]),dict(id='H2',feature='SYNTHETIC_INTERIOR',point=[60,40])],
                lower_anchor_hypotheses=[dict(id='H3',feature='SYNTHETIC_EDGE',point=[80,150])],confirmation_lines={})
            s=comparison(case,p);ET.fromstring(s)
            self.assertIn('H1:',s);self.assertIn('H2:',s);self.assertIn('H3:',s)
            self.assertIn('data:image/png',s)
            bad=copy.deepcopy(case);bad['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'HASH'):comparison(bad,p)

    def test_no_execution_legacy_or_network_imports_in_geometry(self):
        allowed={'dataclasses','decimal','base64','hashlib','html','pathlib','argparse','json'}
        for p in HERE.glob('*.py'):
            if p.name.startswith('test_'):continue
            permitted=allowed|({'PIL'} if p.name=='source_review.py' else set())
            for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                if isinstance(n,ast.Import):self.assertTrue(all(a.name.split('.')[0] in permitted for a in n.names))
                if isinstance(n,ast.ImportFrom) and not n.level:self.assertIn(n.module.split('.')[0],permitted)


if __name__=='__main__':unittest.main()
