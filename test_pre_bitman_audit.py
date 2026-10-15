"""Offline fixtures test the audit tooling; fixture outcomes are NOT live evidence."""
import ast
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research import import_forward_journals as audit
from research.pre_bitman_audit import selected_metrics


class ForwardImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'export'
        self.root.mkdir()
        self.out = Path(self.tmp.name) / 'report'
        self.stamp = 1791417600000

    def journal(self, system, name, rows, tail=b''):
        path = self.root / system / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b''.join((json.dumps(r) + '\n').encode() for r in rows) + tail)
        return path

    def signal(self, **kw):
        return dict(dict(event_id='test-event', source='FORWARD_LIVE', side='LONG',
                         signal_time=self.stamp, closed_15m_time=self.stamp,
                         reference_price=100., entry_quality='GOOD', software_version='MANUAL_COPILOT_V1'), **kw)

    def mlrsi(self, **kw):
        row = dict(event='GREEN_RESUME', timeframe='1h', candle_complete=True,
            recorded_at_utc='2026-10-08T00:00:20Z', candle_timestamp_utc='2026-10-08T00:00:00Z',
            dedupe_key='BTCUSDT|1h|test|GREEN_RESUME', symbol='BTCUSDT', source='LOW', close=100.,
            shadow_only=True, trade_authority=False, config_version='CAPTURE_LOW29_EMA4_PINE_PARITY_V4')
        row.update(kw)
        return row

    def event(self, side='LONG'):
        return dict(system='copilot_audit', identity='test-event', observed_at=self.stamp,
                    reference=100., side=side)

    def market(self, hours=72, high=102., low=99.5, close=101.):
        return [[self.stamp+i*audit.STEP, 100., high, low, close] for i in range(hours*12)]

    def test_inputs_byte_unchanged(self):
        path = self.journal('copilot_audit', 'signals.jsonl', [self.signal()])
        before = path.read_bytes()
        report = audit.run(self.root, self.out, self.stamp+72*3600000)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report['manifest'][0]['sha256'], hashlib.sha256(before).hexdigest())

    def test_reject_output_inside_input(self):
        with self.assertRaisesRegex(ValueError, 'DISJOINT'):
            audit.run(self.root, self.root/'output', self.stamp)

    def test_torn_tail_not_repaired(self):
        path = self.journal('copilot_audit', 'signals.jsonl', [self.signal()], b'{bad')
        before = path.read_bytes()
        report = audit.run(self.root, self.out, self.stamp)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report['issues']['TORN_LINE_NOT_MODIFIED'], 1)

    def test_no_signal_reconstruction_from_snapshots(self):
        self.journal('copilot_audit', 'snapshots.jsonl', [dict(bias='LONG_ALLOWED')])
        self.assertFalse(audit.run(self.root, self.out, self.stamp)['cohorts'])

    def test_historical_signal_excluded(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal(source='HISTORICAL')])
        report = audit.run(self.root, self.out, self.stamp)
        self.assertFalse(report['cohorts'])

    def test_duplicates_removed(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal(), self.signal()])
        report = audit.run(self.root, self.out, self.stamp)
        self.assertTrue(all(c['n'] == 1 for c in report['cohorts']))

    def test_conflicting_duplicate_excluded(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal(), self.signal(reference_price=102.)])
        self.assertFalse(audit.run(self.root, self.out, self.stamp)['cohorts'])

    def test_configuration_versions_separated(self):
        self.journal('mlrsi', 'igod_mlrsi_events.jsonl', [self.mlrsi(), self.mlrsi(
            dedupe_key='other', config_version='CAPTURE_LOW29_EMA4_PINE_PARITY_V3')])
        report = audit.run(self.root, self.out, self.stamp+7*86400000)
        self.assertEqual({c['version'] for c in report['cohorts']},
                         {'CAPTURE_LOW29_EMA4_PINE_PARITY_V3', 'CAPTURE_LOW29_EMA4_PINE_PARITY_V4'})

    def test_provisional_not_confirmed_event(self):
        self.journal('mlrsi', 'igod_mlrsi_events.jsonl', [self.mlrsi(candle_complete=False)])
        self.assertFalse(audit.run(self.root, self.out, self.stamp+7*86400000)['cohorts'])

    def test_old_catchup_excluded(self):
        self.journal('mlrsi', 'igod_mlrsi_events.jsonl', [self.mlrsi(recorded_at_utc='2026-10-08T02:00:00Z')])
        report = audit.run(self.root, self.out, self.stamp+7*86400000)
        self.assertFalse(report['cohorts'])
        self.assertEqual(report['issues']['DELAYED_OR_CATCHUP_EVENT_EXCLUDED'], 1)

    def test_three_of_three_kept_as_recorded(self):
        self.journal('mlrsi', 'igod_mlrsi_events.jsonl', [self.mlrsi(event='CONFLUENCE_3OF3_GREEN')])
        c = audit.run(self.root, self.out, self.stamp+7*86400000)['cohorts']
        self.assertEqual(c[0]['event'], 'CONFLUENCE_3OF3_GREEN')
        self.assertEqual(c[0]['timeframe'], '1h')  # preserve journal TF; never create three fake events

    def test_pending_not_failure(self):
        out = audit.evaluate(self.event(), self.market(), 24, self.stamp+3600000)
        self.assertEqual(out['status'], 'PENDING')

    def test_missing_market_not_failure(self):
        out = audit.evaluate(self.event(), None, 24, self.stamp+24*3600000)
        self.assertEqual(out['status'], 'MARKET_DATA_PENDING')

    def test_gap_censored(self):
        rows = self.market(1)
        del rows[3]
        self.assertEqual(audit.evaluate(self.event(), rows, 1, self.stamp+3600000)['status'], 'INCOMPLETE')

    def test_only_future_closed_bars(self):
        rows = self.market(1)
        rows = [[self.stamp-audit.STEP, 100., 200., 1., 100.]]+rows
        out = audit.evaluate(self.event(), rows, 1, self.stamp+3600000)
        self.assertAlmostEqual(out['mfe'], .02)
        self.assertAlmostEqual(out['mae'], -.005)

    def test_long_return(self):
        self.assertAlmostEqual(audit.evaluate(self.event(), self.market(1), 1, self.stamp+3600000)['mean_return'], .01)

    def test_short_return_and_excursions(self):
        out = audit.evaluate(self.event('SHORT'), self.market(1, high=100.5, low=98., close=99.), 1, self.stamp+3600000)
        self.assertAlmostEqual(out['mean_return'], .01)
        self.assertAlmostEqual(out['mfe'], .02)
        self.assertAlmostEqual(out['mae'], -.005)

    def test_first_passage_all_pairs(self):
        out = audit.evaluate(self.event(), self.market(1, high=104., low=99.9), 1, self.stamp+3600000)
        self.assertEqual(set(out['first_passage'].values()), {'WIN'})
        self.assertEqual(len(out['first_passage']), 4)

    def test_ambiguous_not_invented_win(self):
        out = audit.evaluate(self.event(), self.market(1, high=104., low=98.), 1, self.stamp+3600000)
        self.assertEqual(set(out['first_passage'].values()), {'AMBIGUOUS'})

    def test_neither_counts(self):
        out = audit.evaluate(self.event(), self.market(1, high=100.1, low=99.9, close=100.), 1, self.stamp+3600000)
        self.assertEqual(set(out['first_passage'].values()), {'NEITHER'})

    def test_full_72h(self):
        self.assertEqual(audit.evaluate(self.event(), self.market(), 72, self.stamp+72*3600000)['status'], 'COMPLETE')

    def test_stored_outcomes_used_without_csv(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal()])
        self.journal('copilot_audit', 'outcomes.jsonl', [dict(event_id='test-event', hours=24,
            source='FORWARD_LIVE', status='COMPLETE', directional_return=.01, mfe=.02, mae=-.01,
            first_passage={'0.01/0.01':'WIN'})])
        report = audit.run(self.root, self.out, self.stamp+24*3600000)
        h = report['cohorts'][0]['horizons']['24']
        self.assertEqual(h['mature_complete'], 1)
        self.assertEqual(h['first_passage']['+1/-1']['favorable_first'], 1.)
        self.assertIsNone(h['first_passage']['+3/-1.5']['favorable_first'])

    def test_no_secret_or_account_pnl_copied(self):
        row = self.signal()
        row.update(api_key='SECRET_TEST', chat_id='CHAT_TEST', account_pnl=9999999)
        self.journal('copilot_audit', 'signals.jsonl', [row])
        audit.run(self.root, self.out, self.stamp)
        text = (self.out/'forward_report.json').read_text()
        self.assertNotIn('SECRET_TEST', text)
        self.assertNotIn('CHAT_TEST', text)
        self.assertNotIn('9999999', text)

    def test_invalid_market_and_duplicate_rejected(self):
        path = self.root/'market.csv'
        path.write_text('time,open,high,low,close\n0,100,101,99,100\n0,100,101,99,100\n')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            audit.load_market(path)

    def test_deterministic(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal()])
        one = audit.run(self.root, self.out, self.stamp)
        two = audit.run(self.root, self.out, self.stamp)
        self.assertEqual(one, two)

    def test_no_network_or_live_imports(self):
        source = Path(audit.__file__).read_text()
        tree = ast.parse(source)
        names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse(names & {'requests', 'urllib', 'guardian_bitunix', 'guardian_risk', 'trade_guardian',
                                 'v8_executor', 'copilot_audit', 'mlrsi_observer', 'early_breakout_shadow'})
        self.assertNotIn('AuditStore(', source)

    def test_selected_management_not_reranked(self):
        source = dict(selected={'key':'frozen'}, models={'frozen':{'TEST':{'metrics':{'mean_net':-.1}}},
                                                       'best_after_test':{'TEST':{'metrics':{'mean_net':100}}}})
        self.assertEqual(selected_metrics(source)[0], 'frozen')

    def test_year_cohort_uses_actual_observation(self):
        self.journal('copilot_audit', 'signals.jsonl', [self.signal()])
        cohorts = audit.run(self.root, self.out, self.stamp)['cohorts']
        self.assertTrue(any(c['cohort'] == 'YEAR_2026' for c in cohorts))

    def test_missing_barriers_in_stored_outcome_not_failures(self):
        stored = {('test-event', 24): dict(status='COMPLETE', directional_return=.01,
                  mfe=.02, mae=-.01, first_passage={})}
        event = dict(self.event(), version='V1', timeframe='15m', event='LONG_ALLOWED', quality='GOOD')
        stats = audit.summarize([event], None, self.stamp+24*3600000, stored)
        for c in stats:
            for pair in c['horizons']['24']['first_passage'].values():
                self.assertEqual(pair['evaluable'], 0)
                self.assertIsNone(pair['favorable_first'])


if __name__ == '__main__':
    unittest.main()
