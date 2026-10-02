"""Prospective audit tests, synthetic public candles only; all live HTTP blocked."""
import ast
import copy
import inspect
import json
from pathlib import Path
import tempfile
import queue
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Guardian workflow installs dependencies') from None
import copilot_audit as audit
import test_trade_guardian as harness
from guardian_commands import SnapshotCache, TelegramCommands, HELP

T = 1800000000000


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = T
        self.public = Mock()
        self.observer = audit.ForwardAudit(self.tmp.name, self.public, clock=lambda: self.now / 1000,
                                           git_sha='a' * 40)
        self.network = patch('requests.sessions.Session.request', side_effect=AssertionError('LIVE HTTP FORBIDDEN'))
        self.network.start()

    def tearDown(self):
        self.network.stop()
        self.observer.close()
        self.tmp.cleanup()

    def value(self, bias='WAIT', quality='GOOD', stamp=None):
        stamp = self.now if stamp is None else stamp
        data = harness.GuardianTests.human_bias(bias, quality)
        data['market_levels'].update(reference_price=100, reference_time=stamp // 900000 * 900000,
                                     structural=dict(resistance=110, support=90))
        return audit.packet(data, stamp, 100)

    def signal(self, side='LONG', quality='GOOD'):
        self.observer.observe(self.value('WAIT'))
        self.now += 1000
        return self.observer.observe(self.value(side + '_ALLOWED', quality))

    @staticmethod
    def rows(signal, hours=48):
        start = ((signal['signal_time'] + audit.STEP - 1) // audit.STEP) * audit.STEP
        end = (signal['signal_time'] + hours * 3600000) // audit.STEP * audit.STEP
        return [[t, 100, 100.1, 99.9, 100] for t in range(start, end, audit.STEP)]

    def restart(self):
        self.observer.close()
        self.observer = audit.ForwardAudit(self.tmp.name, self.public, clock=lambda: self.now / 1000)

    def test_one_long_episode_one_event(self):
        first = self.signal()
        for _ in range(10):
            self.now += 1000
            self.assertIsNone(self.observer.observe(self.value('LONG_ALLOWED')))
        self.assertEqual(len(self.observer.store.signals), 1)
        self.assertEqual(first['source'], 'FORWARD_LIVE')

    def test_one_short_episode_one_event(self):
        self.signal('SHORT')
        self.now += 1000
        self.assertIsNone(self.observer.observe(self.value('SHORT_ALLOWED')))
        self.assertEqual(len(self.observer.store.signals), 1)

    def test_wait_rearms_episode(self):
        self.signal()
        self.now += 1000
        self.observer.observe(self.value('WAIT'))
        self.now += 1000
        second = self.observer.observe(self.value('LONG_ALLOWED'))
        self.assertIsNotNone(second)
        self.assertEqual(len(self.observer.store.signals), 2)

    def test_direction_flip_new_event(self):
        first = self.signal()
        self.now += 1000
        second = self.observer.observe(self.value('SHORT_ALLOWED'))
        self.assertNotEqual(first['event_id'], second['event_id'])
        self.assertEqual(second['side'], 'SHORT')

    def test_restart_does_not_duplicate(self):
        self.signal()
        self.restart()
        self.now += 1000
        self.assertIsNone(self.observer.observe(self.value('LONG_ALLOWED')))
        self.assertEqual(len(self.observer.store.signals), 1)

    def test_initial_active_direction_not_claimed_as_new_transition(self):
        self.assertIsNone(self.observer.observe(self.value('LONG_ALLOWED')))
        self.assertEqual(self.observer.store.signals, [])

    def test_unknown_outage_does_not_rearm(self):
        self.signal()
        self.now += 1000
        self.assertIsNone(self.observer.observe(self.value('UNKNOWN')))
        self.now += 1000
        self.assertIsNone(self.observer.observe(self.value('LONG_ALLOWED')))

    def test_immutable_signal_and_quality(self):
        event = self.signal(quality='CAUTION')
        original = copy.deepcopy(self.observer.store.signals[0])
        event.update(reference_price=900, entry_quality='GOOD')
        self.now += 1000
        self.observer.observe(self.value('LONG_ALLOWED', 'POOR'))
        self.assertEqual(self.observer.store.signals[0], original)

    def test_all_quality_cohorts_stored_without_rewriting(self):
        for quality in audit.QUALITIES:
            self.signal(quality=quality)
            self.now += 1000
        self.assertEqual([s['entry_quality'] for s in self.observer.store.signals], list(audit.QUALITIES))

    def test_signal_fields_sha_and_explanation(self):
        signal = self.signal()
        for name in ('event_id', 'side', 'signal_time', 'closed_15m_time', 'reference_price', 'public_mark',
                     'trend4', 'trend1', 'ml_rsi', 'taker_buy', 'structure', 'volatility', 'entry_quality',
                     'entry_reason', 'R1', 'S1', 'R2', 'S2', 'atr_1h', 'git_sha', 'software_version', 'explanation'):
            self.assertIn(name, signal)
        self.assertEqual(signal['git_sha'], 'a' * 40)

    def test_future_closed_reference_rejected(self):
        data = harness.GuardianTests.human_bias()
        data['market_levels'].update(reference_time=T + 900000, reference_price=100)
        self.assertIsNone(audit.packet(data, T))

    def test_secrets_and_user_pnl_never_stored(self):
        data = harness.GuardianTests.human_bias()
        data.update(api_key='PRIVATE_KEY', secret='PRIVATE_SECRET', token='TELEGRAM_TOKEN',
                    chat_id='PRIVATE_CHAT', pnl='USER_PNL', why='RAW_PRIVATE_BODY')
        data['market_levels'].update(reference_time=T, reference_price=100)
        self.observer.observe(self.value('WAIT'))
        self.observer.observe(audit.packet(data, T + 1000))
        stored = ''.join(p.read_text() for p in Path(self.tmp.name).glob('*.json*'))
        for secret in ('PRIVATE_KEY', 'PRIVATE_SECRET', 'TELEGRAM_TOKEN', 'PRIVATE_CHAT', 'USER_PNL', 'RAW_PRIVATE_BODY'):
            self.assertNotIn(secret, stored)

    def test_long_return_mfe_mae(self):
        event = self.signal()
        rows = self.rows(event)
        rows[0][2:4] = [104, 99]
        rows[-1][1:5] = [102, 102.1, 101.9, 102]
        result = audit.evaluate(event, rows, 48, event['signal_time'] + 48 * 3600000)
        self.assertAlmostEqual(result['directional_return'], .02)
        self.assertAlmostEqual(result['mfe'], .04)
        self.assertAlmostEqual(result['mae'], -.01)

    def test_short_return_mfe_mae(self):
        event = self.signal('SHORT')
        rows = self.rows(event)
        rows[0][2:4] = [101, 96]
        rows[-1][1:5] = [98, 98.1, 97.9, 98]
        result = audit.evaluate(event, rows, 48, event['signal_time'] + 48 * 3600000)
        self.assertAlmostEqual(result['directional_return'], .02)
        self.assertAlmostEqual(result['mfe'], .04)
        self.assertAlmostEqual(result['mae'], -.01)

    def test_all_pairs_long_win(self):
        event = self.signal()
        rows = self.rows(event)
        rows[0][2] = 104
        result = audit.evaluate(event, rows, 24, event['signal_time'] + 24 * 3600000)
        self.assertEqual(set(result['first_passage'].values()), {'WIN'})
        self.assertEqual(len(result['first_passage']), 5)

    def test_all_pairs_short_win(self):
        event = self.signal('SHORT')
        rows = self.rows(event)
        rows[0][3] = 96
        self.assertEqual(set(audit.evaluate(event, rows, 24, event['signal_time'] + 24 * 3600000)['first_passage'].values()), {'WIN'})

    def test_all_pairs_loss(self):
        for side in ('LONG', 'SHORT'):
            event = self.signal(side)
            rows = self.rows(event)
            rows[0][3 if side == 'LONG' else 2] = 98 if side == 'LONG' else 102
            self.assertEqual(set(audit.evaluate(event, rows, 24, event['signal_time'] + 24 * 3600000)['first_passage'].values()), {'LOSS'})

    def test_same_bar_ambiguous_not_success(self):
        event = self.signal()
        rows = self.rows(event)
        rows[0][2:4] = [104, 98]
        result = audit.evaluate(event, rows, 24, event['signal_time'] + 24 * 3600000)
        self.assertEqual(set(result['first_passage'].values()), {'AMBIGUOUS'})

    def test_neither_is_not_a_win(self):
        event = self.signal()
        result = audit.evaluate(event, self.rows(event), 24, event['signal_time'] + 24 * 3600000)
        self.assertEqual(set(result['first_passage'].values()), {'NEITHER'})

    def test_pre_event_and_partial_first_candle_excluded(self):
        event = self.signal()
        rows = [[T, 100, 1000, 1, 100]] + self.rows(event)
        result = audit.evaluate(event, rows, 1, event['signal_time'] + 3600000)
        self.assertAlmostEqual(result['mfe'], .001)
        self.assertEqual(result['candles'], 11)

    def test_all_horizons_time_maturity(self):
        event = self.signal()
        for hours in audit.HORIZONS:
            end = event['signal_time'] + hours * 3600000
            self.assertEqual(audit.evaluate(event, self.rows(event), hours, end - 1)['status'], 'PENDING')
            self.assertEqual(audit.evaluate(event, self.rows(event), hours, end)['status'], 'COMPLETE')

    def test_missing_gap_censored(self):
        event = self.signal()
        rows = self.rows(event)
        del rows[3]
        result = audit.evaluate(event, rows, 24, event['signal_time'] + 24 * 3600000)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertNotIn('directional_return', result)

    def test_current_unfinished_last_candle_not_counted(self):
        event = self.signal()
        end = event['signal_time'] + 3600000
        rows = self.rows(event)
        result = audit.evaluate(event, rows, 1, end - 1)
        self.assertEqual(result['status'], 'PENDING')

    def test_future_rows_cannot_change_horizon(self):
        event = self.signal()
        rows = self.rows(event)
        cutoff = event['signal_time'] + 3600000
        expected = audit.evaluate(event, rows, 1, cutoff)
        for row in rows[12:]:
            row[2:4] = [1000, 1]
        self.assertEqual(expected, audit.evaluate(event, rows, 1, cutoff))

    def test_pending_and_incomplete_excluded_from_medians(self):
        self.signal()
        self.public.candles.return_value = []
        self.observer.refresh(self.now + 24 * 3600000)
        row = self.observer.stats_cache.read()['windows']['all']['ALL']
        self.assertEqual(row['n'], 1)
        self.assertEqual(row['mature'], 0)
        self.assertEqual(row['incomplete'], 1)
        self.assertIsNone(row['median_return'])

    def test_outage_not_recorded_as_loss(self):
        self.signal()
        self.public.candles.side_effect = requests.Timeout('RAW_PRIVATE_SECRET')
        self.observer.refresh(self.now + 24 * 3600000)
        self.assertEqual(self.observer.store.outcomes, {})
        self.assertEqual(self.observer.stats_cache.read()['windows']['all']['ALL']['pending'], 1)

    def test_restart_recovery_after_signal_append_before_state(self):
        self.observer.observe(self.value('WAIT'))
        self.now += 1000
        with patch.object(self.observer.store, 'save', side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):
                self.observer.observe(self.value('LONG_ALLOWED'))
        self.restart()
        self.now += 1000
        self.assertIsNone(self.observer.observe(self.value('LONG_ALLOWED')))
        self.assertEqual(len(self.observer.store.signals), 1)

    def test_restart_outcome_recovery_no_duplicate_complete_record(self):
        event = self.signal()
        self.public.candles.return_value = self.rows(event)
        self.now += 48 * 3600000
        self.observer.refresh(self.now)
        before = (Path(self.tmp.name) / 'outcomes.jsonl').read_bytes()
        self.restart()
        self.observer.refresh(self.now)
        self.assertEqual((Path(self.tmp.name) / 'outcomes.jsonl').read_bytes(), before)

    def test_crash_after_first_outcome_append_reconciles_before_evaluation(self):
        event = self.signal()
        self.public.candles.return_value = self.rows(event)
        original = self.observer.store.append
        def interrupted(name, row):
            original(name, row)
            if name == 'outcomes':
                raise RuntimeError('simulated crash after fsync')
        with patch.object(self.observer.store, 'append', side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.observer.refresh(self.now + 48 * 3600000)
        self.restart()
        self.observer.refresh(self.now + 48 * 3600000)
        rows = self.observer.store.read('outcomes')
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(r['hours'] == 1 for r in rows), 1)

    def test_medium_sample_warns_and_ambiguity_excluded(self):
        event = self.signal()
        rows = self.rows(event)
        rows[0][2:4] = [104, 98]
        outcome = audit.evaluate(event, rows, 24, self.now + 24 * 3600000)
        self.observer.store.signals = []
        for i in range(14):
            signal = dict(event, event_id=str(i))
            self.observer.store.signals.append(signal)
            self.observer.store.outcomes[(str(i), 24)] = dict(outcome, event_id=str(i))
        stats = audit.statistics_snapshot(self.observer.store, self.now + 24 * 3600000)
        self.assertIn('Muestra todavía pequeña', audit.render_stats(stats))
        self.assertEqual(stats['windows']['all']['ALL']['pairs']['0.01/0.01']['eligible'], 0)

    def test_runtime_git_sha_metadata_only(self):
        with patch.dict('os.environ', {'RAILWAY_GIT_COMMIT_SHA': 'b' * 40}):
            self.assertEqual(audit.runtime_git_sha(), 'b' * 40)
        with patch.dict('os.environ', {'RAILWAY_GIT_COMMIT_SHA': ''}), patch('copilot_audit.subprocess.check_output', return_value='c' * 40):
            self.assertEqual(audit.runtime_git_sha(), 'c' * 40)

    def test_gap_can_later_complete_without_rewriting_signal(self):
        event = self.signal()
        original = (Path(self.tmp.name) / 'signals.jsonl').read_bytes()
        self.public.candles.return_value = self.rows(event)[1:]
        self.observer.refresh(self.now + 48 * 3600000)
        self.public.candles.return_value = self.rows(event)
        self.observer.refresh(self.now + 48 * 3600000)
        self.assertEqual(self.observer.store.outcomes[(event['event_id'], 24)]['status'], 'COMPLETE')
        self.assertEqual((Path(self.tmp.name) / 'signals.jsonl').read_bytes(), original)

    def test_fsync_journal_and_atomic_state(self):
        with patch('copilot_audit.os.fsync', wraps=audit.os.fsync) as fsync:
            with patch('copilot_audit.os.replace', wraps=audit.os.replace) as replace:
                self.signal()
        self.assertGreaterEqual(fsync.call_count, 3)
        self.assertTrue(replace.called)
        self.assertEqual(replace.call_args.args[1], Path(self.tmp.name) / 'state.json')

    def test_torn_outcome_tail_recovered(self):
        event = self.signal()
        self.public.candles.return_value = self.rows(event)
        self.observer.refresh(self.now + 48 * 3600000)
        with (Path(self.tmp.name) / 'outcomes.jsonl').open('ab') as stream:
            stream.write(b'{"torn":')
        self.restart()
        self.assertEqual(len(self.observer.store.outcomes), 5)

    def test_daily_snapshot_once_per_utc_day(self):
        self.observer.refresh(T)
        self.observer.refresh(T + 1000)
        self.assertEqual(len(self.observer.store.snapshots), 1)
        self.observer.refresh(T + 86400000)
        self.assertEqual(len(self.observer.store.snapshots), 2)

    def test_tiny_sample_warning_and_no_profitability_claim(self):
        self.signal()
        text = audit.render_stats(audit.statistics_snapshot(self.observer.store, self.now))
        self.assertIn('Muy pocos casos', text)
        self.assertIn('NO es tu rentabilidad real', text)
        self.assertNotIn('we are profitable', text)
        self.assertIn('ENTRY QUALITY = CAUTION', text)
        self.assertIn('ENTRY QUALITY = POOR', text)
        self.assertIn('SHORT', text)

    def test_cohorts_separate_and_forward_only(self):
        for side, quality in (('LONG', 'GOOD'), ('LONG', 'CAUTION'), ('SHORT', 'POOR')):
            self.signal(side, quality)
            self.now += 1000
        historical = copy.deepcopy(self.observer.store.signals[0])
        historical['source'] = 'HISTORICAL_SIMULATION'
        self.observer.store.signals.append(historical)
        groups = audit.statistics_snapshot(self.observer.store, self.now)['windows']['all']
        self.assertEqual(groups['ALL']['n'], 3)
        self.assertEqual(groups['GOOD']['n'], 1)
        self.assertEqual(groups['CAUTION']['n'], 1)
        self.assertEqual(groups['POOR']['n'], 1)
        self.assertEqual(groups['LONG']['n'], 2)
        self.assertEqual(groups['SHORT']['n'], 1)

    def test_time_windows_30_90_all(self):
        self.signal()
        now = self.now + 60 * 86400000
        windows = audit.statistics_snapshot(self.observer.store, now)['windows']
        self.assertEqual(windows['30d']['ALL']['n'], 0)
        self.assertEqual(windows['90d']['ALL']['n'], 1)
        self.assertEqual(windows['all']['ALL']['n'], 1)

    def test_stats_owner_only_windows_invalid_args_zero_bitunix(self):
        replies = Mock(return_value=True)
        commands = TelegramCommands('token', 'owner', SnapshotCache(), replies, enabled=True,
                                    stats_cache=self.observer.stats_cache, clock=lambda: self.now / 1000)
        for arg in ('', '30d', '90d', 'all'):
            update = {'message': {'chat': {'id': 'owner'}, 'text': '/stats ' + arg}}
            self.assertTrue(commands.process(update))
            self.assertIn('RESULTADOS FORWARD', replies.call_args.args[0])
            update['message']['chat']['id'] = 'alert-only'
            self.assertFalse(commands.process(update))
        for arg in ('1d', 'sql SELECT', 'all extra', '/arm'):
            self.assertTrue(commands.process({'message': {'chat': {'id': 'owner'}, 'text': '/stats ' + arg}}))
            self.assertEqual(replies.call_args.args[0], HELP)
        self.assertFalse(hasattr(commands, 'client'))

    def test_public_adapter_exact_get_only_and_closed(self):
        event = self.signal()
        http = Mock()
        row = [T + audit.STEP, '100', '101', '99', '100', '10', T + 2 * audit.STEP - 1]
        http.get.return_value = Mock(status_code=200, json=Mock(return_value=[row]))
        client = audit.PublicFiveMinuteData(http)
        self.assertEqual(client.candles(event, T + 2 * audit.STEP - 1), [])
        self.assertEqual(len(client.candles(event, T + 2 * audit.STEP)), 1)
        self.assertEqual(http.get.call_args.args[0], audit.BASE)
        self.assertFalse(http.get.call_args.kwargs['allow_redirects'])
        http.post.assert_not_called()

    def test_audit_has_no_trading_transport_or_credentials(self):
        root = ast.parse(inspect.getsource(audit))
        methods = {n.func.attr for n in ast.walk(root) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(methods & {'post', 'put', 'delete', 'execute', 'preflight', 'flash_close_position', 'place_order'})
        self.assertFalse(hasattr(self.observer, 'client'))
        self.assertFalse(hasattr(self.observer, 'config'))
        self.assertFalse(hasattr(self.observer, 'telegram'))

    def test_queue_full_disclosed_not_hidden_in_statistics(self):
        self.observer.queue = queue.Queue(maxsize=1)
        data = harness.GuardianTests.human_bias()
        data['market_levels'].update(reference_time=T, reference_price=100)
        self.assertTrue(self.observer.submit(data, T))
        with patch('builtins.print') as logs:
            self.assertFalse(self.observer.submit(data, T + 1000))
        logs.assert_called_once_with('COPILOT_AUDIT_QUEUE_FULL', flush=True)
        self.assertEqual(self.observer.lost_observations, 1)
        self.assertIsNone(self.observer.stats_cache.read())
        self.observer.store.state['lost_observations'] = 1
        self.assertIn('Cobertura incompleta', audit.render_stats(audit.statistics_snapshot(self.observer.store, T)))

    def test_audit_submit_exception_cannot_stop_guardian_or_mutate(self):
        fixture = harness.GuardianNotificationTests()
        fixture.setUp()
        try:
            fixture.guardian.audit = Mock()
            fixture.guardian.audit.submit.side_effect = RuntimeError('private fake secret')
            with patch('builtins.print') as logs:
                heartbeat = fixture.guardian.cycle()
            self.assertEqual(heartbeat['risk'], 'NORMAL')
            self.assertEqual(fixture.fake.posts, [])
            self.assertNotIn('private fake secret', str(logs.call_args_list))
        finally:
            fixture.tearDown()

    def test_invalid_software_sha_not_recorded(self):
        self.observer.git_sha = None
        signal = self.signal()
        self.assertIsNone(signal['git_sha'])


if __name__ == '__main__':
    unittest.main()
