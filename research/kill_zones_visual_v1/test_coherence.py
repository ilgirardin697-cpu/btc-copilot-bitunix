"""Frozen source, complete sample and contemporary price-order diagnostics."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from . import audit_coherence as audit
from . import model
from .data import json_text, read_csv, sha

HERE=Path(__file__).resolve().parent
OUT=HERE/'coherence_30d'


class CoherenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=read_csv(OUT/'BTCUSDT_USDM_1h_202609.csv')
        cls.rows=json.loads((OUT/'daily_audit.json').read_text(encoding='utf-8'))
        cls.summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))

    def test_model_exact_reviewed_blob_not_refrozen(self):
        audit.assert_frozen()
        raw=subprocess.check_output(['git','show',audit.FROZEN_COMMIT+':research/kill_zones_visual_v1/model.py'],cwd=HERE.parents[1])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),audit.FROZEN_MODEL_SHA)

    def test_source_change_fails_closed(self):
        with patch.object(audit,'sha',return_value='changed'):
            with self.assertRaisesRegex(ValueError,'MODEL_CHANGED'):
                audit.assert_frozen()

    def test_complete_fixed_month_and_original_excerpt_identical(self):
        manifest=json.loads((OUT/'data_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(self.bars),720)
        self.assertEqual(sha(OUT/'BTCUSDT_USDM_1h_202609.csv'),manifest['hourly_csv_sha256'])
        self.assertEqual(self.bars[:72],read_csv(HERE/'examples/BTCUSDT_USDM_1h_20260901_03.csv'))
        self.assertEqual([r['day'] for r in self.rows],[d.isoformat() for d in audit.DAYS])
        model.validate(self.bars)

    def test_counts_partition_without_losing_rejected_days(self):
        s=audit.counts(self.rows)
        self.assertEqual((s['days'],s['valid_geometry'],s['invalid_geometry']),(30,23,7))
        self.assertEqual((s['confirmations'],s['reference_plans'],s['rejected_plans'],s['pending_entries']),(5,0,5,0))
        self.assertEqual(s['valid_geometry_without_confirmation'],18)
        self.assertEqual(s['confirmation_sides'],{'UP':3,'DOWN':2})
        self.assertEqual(sum(s['rejection_partition'].values()),s['rejected_plans'])

    def test_nested_examples_are_not_simple_overlap(self):
        first,second=self.rows[:2]
        self.assertEqual(first['box_relation'],'LONDON_CONTAINS_ASIA')
        self.assertEqual(second['box_relation'],'ASIA_CONTAINS_LONDON')
        for r in (first,second):
            self.assertFalse(r['geometry_valid'])
            self.assertFalse(r['confirmation'])
            self.assertIsNone(r['plan_status'])

    def test_september_3_target_behind_line_not_entry_gap(self):
        r=self.rows[2]
        self.assertEqual(r['available_at'],'2026-09-03T15:00:00Z')
        self.assertLess(Decimal(r['body_open']),Decimal(r['line_value']))
        self.assertLess(Decimal(r['line_value']),Decimal(r['body_close']))
        self.assertLess(Decimal(r['target']),Decimal(r['line_value']))
        self.assertEqual(Decimal(r['entry_gap_from_signal_close']),0)
        self.assertEqual(r['rejection_reasons'],['TARGET_NOT_AHEAD_OF_ENTRY'])

    def test_all_five_rejections_explained_without_future_prices(self):
        for r in self.rows:
            if r['confirmation']:
                self.assertTrue(r['target_not_ahead_of_signal_close'])
                self.assertEqual(r['rejection_partition'],'TARGET_ONLY')
        self.assertEqual(self.summary['target_not_ahead_of_line'],3)
        self.assertEqual(self.summary['target_not_ahead_of_signal_close'],5)

    def test_every_confirmed_prefix_replays_identically(self):
        for r in self.rows:
            if r['confirmation']:
                day=date.fromisoformat(r['day'])
                end=model.observe(self.bars,day,model.boundary(day,20))
                early=model.observe(self.bars,day,end['confirmation']['available_at'])
                self.assertEqual(json_text(early['confirmation']),json_text(end['confirmation']))
                self.assertEqual(json_text(early['plan']),json_text(end['plan']))

    def test_bad_checksum_rejected_before_zip_parse(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/'archive').write_bytes(b'not a valid archive')
            (path/'checksum').write_text('0'*64)
            with self.assertRaisesRegex(ValueError,'CHECKSUM_MISMATCH'):
                audit.extract_month(path/'archive',path/'checksum',path/'out')

    def test_partial_month_rejected_not_extrapolated(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'EXACT_720'):
                audit.audit(self.bars[:-1],Path(folder))

    def test_all_30_charts_and_json_regenerate_identically(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)
            s=audit.audit(self.bars,target)
            self.assertEqual(s,self.summary)
            self.assertEqual(len(list((target/'charts').glob('*.svg'))),30)
            self.assertEqual(len(list((target/'charts').glob('*.json'))),30)
            for p in (target/'charts').iterdir():
                self.assertEqual(p.read_bytes(),(OUT/'charts'/p.name).read_bytes(),p.name)
            for name in ('summary.json','daily_audit.json','daily_audit.csv','index.html'):
                self.assertEqual((target/name).read_bytes(),(OUT/name).read_bytes(),name)

    def test_no_trade_outcome_or_profitability_columns(self):
        forbidden={'pnl','profit','win_rate','forward_return','MAE','MFE','exit_price','exit_at','profit_factor'}
        self.assertTrue(all(not forbidden.intersection(r) for r in self.rows))
        self.assertTrue(self.summary['no_performance_evaluation'])


if __name__=='__main__':
    unittest.main()
