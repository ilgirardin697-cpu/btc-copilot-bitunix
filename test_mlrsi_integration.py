"""Guardian topology, unchanged protection traces and read-only commands; offline only."""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
try:
    import numpy
    import requests
except ImportError:
    raise unittest.SkipTest('Dependencies installed in dedicated observer and Guardian CI') from None
from mlrsi_safety_audit import (BASELINE, HELP_LINE, fingerprint, verify_guardian_ast,
                               verify_live_ast, verify_protected_sources, verify_observer_boundary)
from mlrsi_guardian_host import MLRSIHost, StatusCache, UNAVAILABLE, storage_directory
from mlrsi_observer import MLRSIObserver
from guardian_commands import COMMANDS, HELP, SnapshotCache, TelegramCommands, render_command
from guardian_bitunix import Bitunix, POST_ALLOWLIST, PLACE_SL, FLASH_CLOSE
from guardian_risk import Config
from guardian_store import Store
import trade_guardian
from test_trade_guardian import ARMED, FakeBitunix, FakeMarket, FakeTelegram, position


def baseline(path):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path]).decode('utf-8')


class BoundaryTests(unittest.TestCase):
    def test_entire_guardian_and_command_ast_matches_baseline(self):
        self.assertTrue(verify_guardian_ast())

    def test_live_auto_restored_completely(self):
        self.assertTrue(verify_live_ast())

    def test_v8_main_rules_and_validated_math_hashes(self):
        self.assertTrue(verify_protected_sources())

    def test_guardian_entire_class_byte_equivalent_ast(self):
        old = ast.parse(baseline('trade_guardian.py'))
        new = ast.parse(Path('trade_guardian.py').read_text('utf-8'))
        a = next(n for n in old.body if isinstance(n, ast.ClassDef) and n.name == 'Guardian')
        b = next(n for n in new.body if isinstance(n, ast.ClassDef) and n.name == 'Guardian')
        self.assertEqual(fingerprint(a), fingerprint(b))  # includes _act/reconcile/cycle/lockout

    def test_all_protection_and_risk_sources_frozen(self):
        self.assertTrue(verify_protected_sources())  # client preflight/permit/execute and all safety flags

    def test_zero_trading_http_capability(self):
        self.assertTrue(verify_observer_boundary())

    def test_forever_no_authority(self):
        self.assertIs(MLRSIObserver.trade_authority, False)
        self.assertIs(MLRSIObserver.shadow_only, True)

    def test_no_new_credentials_or_guardian_object(self):
        for path in ('mlrsi_math.py', 'mlrsi_public.py', 'mlrsi_observer.py', 'mlrsi_telegram.py', 'mlrsi_guardian_host.py'):
            text = Path(path).read_text('utf-8')
            for forbidden in ('BITUNIX_API_KEY', 'BITUNIX_SECRET_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
                self.assertNotIn(forbidden, text)

    def test_single_getupdates_consumer_in_runtime(self):
        modules = ['trade_guardian.py', 'guardian_commands.py', 'mlrsi_guardian_host.py',
                   'mlrsi_observer.py', 'mlrsi_public.py', 'mlrsi_telegram.py']
        calls = []
        for path in modules:
            for node in ast.walk(ast.parse(Path(path).read_text('utf-8'))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and 'getUpdates' in node.value:
                    calls.append(path)
        self.assertEqual(calls, ['guardian_commands.py'])
        before = next(n for n in ast.walk(ast.parse(baseline('guardian_commands.py')))
                      if isinstance(n, ast.FunctionDef) and n.name == 'poll_once')
        after = next(n for n in ast.walk(ast.parse(Path('guardian_commands.py').read_text('utf-8')))
                     if isinstance(n, ast.FunctionDef) and n.name == 'poll_once')
        self.assertEqual(fingerprint(before), fingerprint(after))
        source = Path('trade_guardian.py').read_text('utf-8')
        self.assertNotIn('poll_commands', source)
        self.assertNotIn('live_auto', source)

    def test_post_allowlist_unchanged(self):
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logs = []
        self.host = MLRSIHost(self.tmp.name, send=Mock(return_value=True), logger=self.logs.append)
        self.addCleanup(self.host.stop)

    def test_public_cache_is_deep_copy_only(self):
        self.host.status_cache.publish('<b>ML RSI</b> 15m 1H 4H', True)
        value = self.host.status_cache.read()
        value['text'] = 'changed'
        self.assertEqual(self.host.status_cache.read(), {'text': 'ML RSI 15m 1H 4H', 'enabled': True})
        self.assertEqual(set(vars(self.host.status_cache)), {'_lock', '_value'})
        self.assertIs(self.host.status_cache.read.__self__, self.host.status_cache)

    def test_outbound_existing_callback_plain_text(self):
        self.host._send_text('<b>GREEN CONFIRMED</b>\nSHADOW ONLY')
        self.host._send.assert_called_once_with('GREEN CONFIRMED\nSHADOW ONLY')

    def test_start_is_daemon_no_import_or_join_in_caller(self):
        with patch('mlrsi_guardian_host.threading.Thread') as factory, patch('mlrsi_observer.MLRSIObserver') as observer:
            self.host.start()
            self.host.start()
            observer.assert_not_called()
            factory.assert_called_once_with(target=self.host._run, name='guardian-mlrsi-host', daemon=True)
            factory.return_value.start.assert_called_once()
            self.host.stop()
            factory.return_value.join.assert_not_called()

    def test_constructor_does_no_filesystem_resolution(self):
        with patch('mlrsi_guardian_host.storage_directory', side_effect=OSError('secret disk')) as resolve:
            host = MLRSIHost(send=Mock(), logger=self.logs.append)
            resolve.assert_not_called()
            host._run()
        self.assertEqual(self.logs, ['MLRSI_HOST_FAILED_IGNORED'])

    def test_explicit_override_cannot_write_guardian_directory(self):
        host = MLRSIHost(self.tmp.name, send=Mock(), logger=self.logs.append)
        with patch.dict(os.environ, {'GUARDIAN_STATE_DIR': self.tmp.name}), patch('mlrsi_observer.MLRSIObserver') as observer:
            host._run()
        observer.assert_not_called()
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
        self.assertEqual(self.logs, ['MLRSI_HOST_FAILED_IGNORED'])

    def test_heavy_import_init_happens_only_in_worker(self):
        with patch('mlrsi_observer.MLRSIObserver') as factory:
            observer = factory.return_value
            observer.config.enabled = True
            observer.status_text.return_value = '<b>snapshot</b>'
            self.host._stop = Mock()
            self.host._stop.is_set.side_effect = [False, False, True]
            self.host._run()
            self.assertEqual(factory.call_args.args, (Path(self.tmp.name),))
            self.assertEqual(set(factory.call_args.kwargs), {'send', 'logger'})
            self.assertIs(factory.call_args.kwargs['send'].__self__, self.host)
            observer.start.assert_called_once()
            observer.stop.assert_called_once()
            self.assertEqual(self.host.status_cache.read()['text'], 'snapshot')
            self.host._stop.wait.assert_called_once_with(1)

    def test_import_failure_static_nonfatal(self):
        import builtins
        original = builtins.__import__
        def imported(name, *args, **kwargs):
            if name == 'mlrsi_observer':
                raise ImportError('must-not-log secret')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=imported):
            self.host._run()
        self.assertEqual(self.logs, ['MLRSI_HOST_FAILED_IGNORED'])

    def test_init_disk_error_nonfatal(self):
        with patch('mlrsi_observer.MLRSIObserver', side_effect=OSError('must-not-log secret')):
            self.host._run()
        self.assertEqual(self.logs, ['MLRSI_HOST_FAILED_IGNORED'])
        self.assertFalse(self.host.status_cache.read()['enabled'])

    def test_start_failure_nonfatal(self):
        with patch('mlrsi_observer.MLRSIObserver') as factory:
            factory.return_value.start.side_effect = RuntimeError('must-not-log secret')
            self.host._run()
            factory.return_value.stop.assert_called_once()
        self.assertEqual(self.logs, ['MLRSI_HOST_FAILED_IGNORED'])

    def test_snapshot_failure_nonfatal_and_cached_unknown(self):
        with patch('mlrsi_observer.MLRSIObserver') as factory:
            factory.return_value.status_text.side_effect = RuntimeError('must-not-log secret')
            self.host._stop = Mock()
            self.host._stop.is_set.side_effect = [False, False, True]
            self.host._run()
        self.assertEqual(self.logs, ['MLRSI_STATUS_FAILED_IGNORED'])
        self.assertEqual(self.host.status_cache.read()['text'], UNAVAILABLE)

    def test_stop_nonblocking_and_error_nonfatal(self):
        self.host._observer = Mock()
        self.host._observer.stop.side_effect = RuntimeError('must-not-log secret')
        self.host._thread = Mock()
        self.host.stop()
        self.host._thread.join.assert_not_called()
        self.assertEqual(self.logs, ['MLRSI_STOP_FAILED_IGNORED'])
        self.assertTrue(self.host._stop.is_set())

    def test_stop_during_initialization_never_starts_worker(self):
        self.host.stop()
        with patch('mlrsi_observer.MLRSIObserver') as factory:
            self.host._run()
            factory.return_value.start.assert_not_called()
            factory.return_value.stop.assert_called_once()

    def test_actual_worker_clustering_error_isolated(self):
        observer = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        observer.cycle = Mock(side_effect=ValueError('must-not-log secret'))
        observer.stop_event = Mock()
        observer.stop_event.is_set.side_effect = [False, True]
        observer._worker()
        self.assertEqual(self.logs, ['MLRSI_OBSERVER_ERROR_IGNORED'])

    def test_logger_failure_nonfatal(self):
        self.host._logger = Mock(side_effect=RuntimeError('must-not-log secret'))
        self.host._log('MLRSI_HOST_FAILED_IGNORED')

    def test_storage_explicit(self):
        self.assertEqual(storage_directory({'MLRSI_STATE_DIR': self.tmp.name}), Path(self.tmp.name))

    def test_storage_railway_volume_default(self):
        self.assertEqual(storage_directory({'RAILWAY_VOLUME_MOUNT_PATH': self.tmp.name}), Path(self.tmp.name) / 'mlrsi')

    def test_storage_data_default_when_present(self):
        with patch('mlrsi_guardian_host.Path.is_dir', return_value=True):
            self.assertEqual(storage_directory({}), Path('/data/mlrsi'))

    def test_storage_safe_local_fallback(self):
        with patch('mlrsi_guardian_host.Path.is_dir', return_value=False):
            self.assertEqual(storage_directory({}), Path('mlrsi_observations'))

    def test_storage_rejects_shared_namespaces(self):
        for name in ('GUARDIAN_STATE_DIR', 'COPILOT_AUDIT_STATE_DIR', 'EARLY_BREAKOUT_STATE_DIR'):
            for suffix in ('', '/mlrsi'):
                with self.subTest(name=name, suffix=suffix), self.assertRaises(ValueError):
                    storage_directory({name: self.tmp.name, 'MLRSI_STATE_DIR': self.tmp.name + suffix})

    def test_storage_rejects_volume_root_and_cwd(self):
        for path in (self.tmp.name, str(Path.cwd()), '/data'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                storage_directory({'MLRSI_STATE_DIR': path, 'RAILWAY_VOLUME_MOUNT_PATH': self.tmp.name})


class GuardianTraceTests(unittest.TestCase):
    def run_trace(self, mode='ON', liq=9900, side='LONG', *, old=False, shadow=False,
                  ambiguous=False, pending=False, private_fail=False):
        """Run actual main/cycle/preflight/execute with fake HTTP; no production threads."""
        with TemporaryDirectory() as folder:
            fake = FakeBitunix()
            fake.positions = [position(side=side, liqPrice=str(liq))]
            fake.ambiguous, fake.fail = ambiguous, private_fail
            config = Config(state_dir=folder) if shadow else ARMED
            client = Bitunix(config, 'fake-key', 'fake-secret', fake)
            store = Store(folder)
            if pending:
                store.append('actions', dict(key='CLOSE:123:1', action='CLOSE', positionId='123',
                                            risk_epoch=1, status='INTENT', timestamp=1, body={'positionId': '123'}))
            telegram = FakeTelegram()
            telegram.send_owner = telegram.send
            diagnostics = []
            telegram_factory = Mock(return_value=telegram)
            telegram_factory._diagnostic = diagnostics.append
            audit = Mock()
            host = Mock(status_cache=StatusCache())
            host.status_cache.publish('cached SHADOW ONLY', mode == 'ON')
            if mode == 'ERROR':
                host.start.side_effect = RuntimeError('secret observer failure')
            if mode == 'STOP_ERROR':
                host.stop.side_effect = RuntimeError('secret stop failure')
            if mode == 'WORKER_ERROR':
                # Run real host bootstrap failure; worker catches it and returns.
                def failed_worker():
                    real = MLRSIHost(Path(folder) / 'mlrsi', send=telegram.send, logger=diagnostics.append)
                    with patch('mlrsi_observer.MLRSIObserver', side_effect=RuntimeError('observer failure')):
                        real._run()
                host.start.side_effect = failed_worker
            host_factory = Mock(return_value=host)
            if mode == 'INIT_ERROR':
                host_factory.side_effect = OSError('secret disk failure')
            commands = Mock()
            env = dict(trade_guardian.__dict__)
            env.update(Config=SimpleNamespace(from_env=lambda: config), Store=lambda _: store,
                       Bitunix=lambda *args: client, Market=lambda _: FakeMarket(), Telegram=telegram_factory,
                       ForwardAudit=Mock(return_value=audit), runtime_git_sha=lambda: 'offline-fixture',
                       TelegramCommands=commands)
            source = baseline('trade_guardian.py') if old else Path('trade_guardian.py').read_text('utf-8')
            main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
            exec(compile(ast.fix_missing_locations(ast.Module(body=[main], type_ignores=[])), '<offline-main>', 'exec'), env)
            def end_cycle(seconds):
                if seconds > 1:
                    raise KeyboardInterrupt
            with patch('mlrsi_guardian_host.MLRSIHost', host_factory), patch('trade_guardian.time.sleep', side_effect=end_cycle), \
                 patch('requests.sessions.Session.request', side_effect=AssertionError('REAL HTTP FORBIDDEN')), \
                 patch('builtins.print'):
                env['main']()
            trace = [(method, path, options.get('params'), json.loads(options['data']) if options.get('data') else None)
                     for method, path, options in fake.calls]
            actions_path = Path(folder) / 'actions.jsonl'
            actions = [json.loads(line) for line in actions_path.read_text().splitlines()] if actions_path.exists() else []
            for row in actions:
                row.pop('timestamp', None)
            state = copy.deepcopy(store.state)
            callbacks = commands.call_args.kwargs if commands.called else {}
            return dict(trace=trace, actions=actions, posts=[t for t in trace if t[0] == 'POST'],
                        state=state, diagnostics=diagnostics, callbacks=callbacks, host=host)

    def equivalent(self, mode, **scenario):
        old = self.run_trace(old=True, **scenario)
        new = self.run_trace(mode, **scenario)
        self.assertEqual(old['trace'], new['trace'])
        self.assertEqual(old['actions'], new['actions'])
        self.assertEqual(old['state'].get('owned_sl'), new['state'].get('owned_sl'))
        self.assertEqual(bool(old['state'].get('lockout_until')), bool(new['state'].get('lockout_until')))
        return new

    def test_emergency_off_identical_baseline(self):
        result = self.equivalent('OFF')
        self.assertEqual(result['posts'], [('POST', FLASH_CLOSE, {}, {'positionId': '123'})])

    def test_emergency_on_identical_baseline(self):
        self.equivalent('ON')

    def test_observer_error_during_emergency_exact_same_protection(self):
        result = self.equivalent('ERROR')
        self.assertEqual(result['posts'], [('POST', FLASH_CLOSE, {}, {'positionId': '123'})])
        self.assertIn('MLRSI_HOST_UNAVAILABLE', result['diagnostics'])

    def test_observer_init_error_emergency_not_blocked(self):
        self.equivalent('INIT_ERROR')

    def test_observer_worker_error_emergency_not_blocked(self):
        result = self.equivalent('WORKER_ERROR')
        self.assertIn('MLRSI_HOST_FAILED_IGNORED', result['diagnostics'])

    def test_observer_stop_error_does_not_prevent_shutdown(self):
        result = self.equivalent('STOP_ERROR')
        self.assertIn('MLRSI_STOP_FAILED_IGNORED', result['diagnostics'])

    def test_missing_sl_protection_identical_all_modes(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            result = self.equivalent(mode, liq=9500)
            self.assertEqual(len(result['posts']), 1)
            self.assertEqual(result['posts'][0][1], PLACE_SL)

    def test_short_emergency_identical_all_modes(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            result = self.equivalent(mode, liq=10100, side='SHORT')
            self.assertEqual(result['posts'][0][1], FLASH_CLOSE)

    def test_shadow_zero_posts_all_modes(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            self.assertEqual(self.equivalent(mode, shadow=True)['posts'], [])

    def test_pending_reconciliation_identical_no_duplicate(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            self.assertEqual(self.equivalent(mode, pending=True)['posts'], [])

    def test_ambiguous_response_identical(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            self.equivalent(mode, ambiguous=True)

    def test_private_failure_fail_closed_all_modes(self):
        for mode in ('OFF', 'ON', 'ERROR'):
            self.assertEqual(self.equivalent(mode, private_fail=True)['posts'], [])

    def test_command_receives_cache_only_not_observer(self):
        result = self.run_trace()
        self.assertIs(result['callbacks']['mlrsi_status'].__self__, result['host'].status_cache)
        self.assertNotIsInstance(result['callbacks']['mlrsi_status'].__self__, MLRSIHost)


class CommandIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.cache, self.reply, self.http = SnapshotCache(), Mock(return_value=True), Mock()
        self.status = StatusCache()
        with TemporaryDirectory() as folder:
            observer = MLRSIObserver(folder, logger=lambda _: None)
            self.status.publish(observer.status_text(), True)
        self.commands = TelegramCommands('fake-token', 'owner', self.cache, self.reply,
                                          enabled=True, transport=self.http, mlrsi_status=self.status.read)

    @staticmethod
    def update(command, owner='owner', identifier=1):
        return {'update_id': identifier, 'message': {'chat': {'id': owner}, 'text': command}}

    def test_mlrsi_no_recent_event_full_readonly_panel(self):
        self.assertTrue(self.commands.process(self.update('/mlrsi')))
        text = self.reply.call_args.args[0]
        for word in ('15m', '1H', '4H', 'Confirmed', 'Provisional', 'Approaching', 'Upper', 'Lower',
                     'Middle', 'Último cierre', 'Último evento', 'CONFLUENCIA', 'GREEN_CROSS',
                     'GREEN_RESUME', 'SHADOW ONLY', 'TRADE AUTHORITY: NONE', 'LOW'):
            self.assertIn(word, text)
        self.assertNotIn('<b>', text)

    def test_help_preserves_all_previous_text_and_commands(self):
        old_help = next(n for n in ast.parse(baseline('guardian_commands.py')).body
                        if isinstance(n, ast.Assign) and n.targets[0].id == 'HELP').value.value
        self.assertEqual(HELP.replace(HELP_LINE, ''), old_help)
        self.assertEqual(COMMANDS, ('/status', '/why', '/position', '/risk', '/levels', '/stats', '/help', '/mlrsi'))
        self.commands.process(self.update('/help'))
        self.assertEqual(self.reply.call_args.args[0], HELP)
        self.assertNotIn('/mlrsi_help', HELP)

    def test_status_adds_exactly_one_information_line(self):
        self.commands.process(self.update('/status'))
        self.assertEqual(self.reply.call_args.args[0], render_command('/status', None, 0) + '\nML RSI MTF Observer: ON')

    def test_owner_only_alert_recipients_not_authorized(self):
        for owner in ('alert-recipient', 'other', ' owner ', '', None):
            self.assertFalse(self.commands.process(self.update('/mlrsi', owner)))
        self.reply.assert_not_called()
        self.assertTrue(self.commands.process(self.update('/mlrsi')))

    def test_disabled_no_polling(self):
        self.commands.enabled = False
        self.assertFalse(self.commands.poll_once())
        self.assertFalse(self.commands.process(self.update('/mlrsi')))
        self.http.get.assert_not_called()

    def test_mlrsi_same_single_poller_as_help(self):
        self.http.get.return_value = SimpleNamespace(status_code=200, json=lambda: dict(ok=True, result=[
            self.update('/mlrsi', identifier=1), self.update('/help', identifier=2)]))
        self.assertTrue(self.commands.poll_once())
        self.http.get.assert_called_once()
        self.assertTrue(self.http.get.call_args.args[0].endswith('/getUpdates'))
        self.assertEqual(self.reply.call_count, 2)

    def test_command_zero_private_public_requests_writes_or_mutations(self):
        before = self.status.read()
        env = dict(os.environ)
        with patch.object(Bitunix, '_request', side_effect=AssertionError('NO BITUNIX')) as bitunix, \
             patch.object(MLRSIObserver, 'cycle', side_effect=AssertionError('NO REFRESH')) as cycle, \
             patch.object(MLRSIObserver, '_persist', side_effect=AssertionError('NO WRITE')) as persist, \
             patch('requests.sessions.Session.request', side_effect=AssertionError('NO HTTP')) as http:
            for command in list(COMMANDS) + ['/arm', '/close', '/protect'] + ['/' + str(i) for i in range(200)]:
                self.assertTrue(self.commands.process(self.update(command)))
        for call in (bitunix, cycle, persist, http):
            call.assert_not_called()
        self.assertEqual(self.status.read(), before)
        self.assertEqual(dict(os.environ), env)

    def test_cache_reader_error_nonfatal(self):
        self.commands._mlrsi_status = Mock(side_effect=RuntimeError('token secret'))
        self.assertTrue(self.commands.process(self.update('/mlrsi')))
        self.assertIn('no disponible', self.reply.call_args.args[0])
        self.assertNotIn('token secret', self.reply.call_args.args[0])

    def test_malformed_cache_nonfatal(self):
        for value in (None, [], {}, {'text': None}):
            self.commands._mlrsi_status = lambda: value
            self.assertTrue(self.commands.process(self.update('/mlrsi')))
            self.assertIn('SHADOW ONLY', self.reply.call_args.args[0])

    def test_missing_observer_nonfatal(self):
        self.commands._mlrsi_status = None
        self.assertTrue(self.commands.process(self.update('/mlrsi')))
        self.assertIn('OFF / no disponible', self.reply.call_args.args[0])

    def test_no_logs_of_token_chat_or_incoming_text(self):
        with patch('builtins.print') as output:
            self.commands.process(self.update('/mlrsi private-message'))
        output.assert_not_called()
        text = self.reply.call_args.args[0]
        for word in ('fake-token', 'owner', 'private-message'):
            self.assertNotIn(word, text)

    def test_telegram_exception_nonfatal_no_other_action(self):
        self.reply.side_effect = RuntimeError('secret')
        self.assertFalse(self.commands.process(self.update('/mlrsi')))
        self.http.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
