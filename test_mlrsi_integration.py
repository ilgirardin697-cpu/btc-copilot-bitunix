"""Executor isolation tests. All transports/actions are offline fakes."""
import ast
import copy
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
try:
    import numpy
    import requests
except ImportError:
    raise unittest.SkipTest('Observer dependencies are installed and fully tested by mlrsi-observer CI') from None
from mlrsi_safety_audit import BASELINE, verify_live_ast, verify_observer_boundary
from mlrsi_observer import MLRSIObserver


class BoundaryTests(unittest.TestCase):
    def test_entire_operational_ast_unchanged(self):
        self.assertTrue(verify_live_ast())

    def test_zero_trading_http_capability(self):
        self.assertTrue(verify_observer_boundary())

    def test_forever_no_authority(self):
        self.assertIs(MLRSIObserver.trade_authority, False)
        self.assertIs(MLRSIObserver.shadow_only, True)

    def test_no_new_credentials(self):
        for path in ('mlrsi_observer.py', 'mlrsi_public.py', 'mlrsi_math.py', 'mlrsi_telegram.py'):
            text = Path(path).read_text('utf-8')
            for forbidden in ('BITUNIX_API_KEY', 'BITUNIX_SECRET_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
                self.assertNotIn(forbidden, text)

    def test_no_provisional_data_in_live_decisions(self):
        tree = ast.parse(Path('live_auto.py').read_text('utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RealAuto')
        allowed = {'__init__', 'run', 'commands', '_init_mlrsi_observer', '_start_mlrsi_observer',
                   '_mlrsi_observer_label', '_send_mlrsi_status'}
        for method in cls.body:
            if isinstance(method, ast.FunctionDef) and method.name not in allowed:
                self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr == 'mlrsi_observer' for n in ast.walk(method)), method.name)

    def test_no_ml_math_in_authorization_or_execution(self):
        self.assertTrue(verify_live_ast())
        # Exact comparison includes sizing, orders, leverage, SL/TP, fee guard,
        # reversals, thesis exit, daily risk, locks and entry authorization.

    def test_main_guardian_v8_early_research_untouched(self):
        paths = ['main.py', 'guardian_risk.py', 'guardian_bitunix.py', 'guardian_signals.py',
                 'trade_guardian.py', 'guardian_commands.py', 'copilot_audit.py', 'trend_v8.py',
                 'early_breakout_shadow.py', 'railway.json']
        for path in paths:
            expected = subprocess.check_output(['git', 'show', BASELINE + ':' + path]).decode('utf-8')
            self.assertEqual(Path(path).read_text('utf-8'), expected.replace('\r\n', '\n'), path)


@unittest.skipUnless(importlib.util.find_spec('pandas') and importlib.util.find_spec('websocket'),
                     'Integration requires requirements.txt; dedicated CI installs every dependency')
class RealAutoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import live_auto
        cls.live = live_auto
        baseline = subprocess.check_output(['git', 'show', BASELINE + ':live_auto.py']).decode('utf-8')
        tree = ast.parse(baseline)
        real = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RealAuto')
        method = copy.deepcopy(next(n for n in real.body if isinstance(n, ast.FunctionDef) and n.name == 'run'))
        method.name = 'baseline_run'
        env = dict(live_auto.__dict__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<baseline>', 'exec'), env)
        cls.baseline_run = staticmethod(env['baseline_run'])

    def bot(self, observer=None, commands=()):
        bot = self.live.RealAuto.__new__(self.live.RealAuto)
        bot.mlrsi_observer = observer
        bot.tg = Mock()
        bot.tg.poll_commands.return_value = list(commands)
        bot.state = SimpleNamespace(auto_enabled=False, locked=False, position=None, entry_armed=True,
                                    save=Mock(), new_day=Mock())
        bot.api = Mock()
        bot.plan = SimpleNamespace(action='WAIT', setup='x', bias='WAIT', price=100)
        return bot

    def command(self, cmd, observer=None):
        bot = self.bot(observer or SimpleNamespace(config=SimpleNamespace(enabled=True), status_text=lambda: 'cached ML RSI'), [cmd])
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Real HTTP forbidden')):
            bot.commands()
        for action in ('post', 'place_order', 'place_market', 'flash_close_position', 'change_leverage'):
            self.assertFalse(getattr(bot.api, action).called)
        self.assertEqual(bot.state.auto_enabled, False)
        self.assertFalse(bot.state.save.called)
        return bot

    def test_mlrsi_command_cached_no_api(self):
        bot = self.command('/mlrsi')
        bot.tg.send.assert_called_once_with('cached ML RSI')
        self.assertEqual(bot.api.mock_calls, [])

    def test_mlrsi_does_not_change_plan_or_state(self):
        bot = self.command('/mlrsi')
        self.assertEqual((bot.plan.action, bot.plan.setup, bot.plan.bias), ('WAIT', 'x', 'WAIT'))

    def test_help_preserves_every_existing_command(self):
        bot = self.command('/help')
        text = bot.tg.send.call_args.args[0]
        for cmd in ('/status', '/account', '/position', '/check', '/plan', '/live_on', '/live_off',
                    '/unlock', '/data', '/why', '/help', '/mlrsi'):
            self.assertIn(cmd, text)
        self.assertNotIn('/mlrsi_help', text)

    def test_status_one_line_only(self):
        bot = self.bot(SimpleNamespace(config=SimpleNamespace(enabled=True)), ['/status'])
        bot.status = Mock(return_value='existing status')
        bot.commands()
        bot.tg.send.assert_called_once_with('existing status\nML RSI MTF Observer: ON')

    def test_mlrsi_missing_observer_nonfatal(self):
        bot = self.bot(commands=['/mlrsi'])
        bot.commands()
        self.assertIn('no disponible', bot.tg.send.call_args.args[0])

    def test_mlrsi_error_static_nonfatal(self):
        bot = self.bot(Mock(), ['/mlrsi'])
        bot.mlrsi_observer.status_text.side_effect = RuntimeError('secret token')
        with patch.object(self.live, 'log') as log:
            bot.commands()
        log.assert_called_once_with('MLRSI_COMMAND_FAILED_IGNORED')
        self.assertEqual(bot.api.mock_calls, [])

    def test_observer_init_failure_nonfatal(self):
        bot = self.bot()
        with patch('mlrsi_observer.MLRSIObserver', side_effect=RuntimeError('secret')):
            bot._init_mlrsi_observer()
        self.assertIsNone(bot.mlrsi_observer)

    def test_observer_constructor_receives_no_trading_capability(self):
        bot = self.bot()
        with patch('mlrsi_observer.MLRSIObserver') as observer:
            bot._init_mlrsi_observer()
        self.assertEqual(set(observer.call_args.kwargs), {'send', 'logger'})
        self.assertEqual(observer.call_args.args, (self.live.OBSERVER_STATE_FILE.parent,))
        self.assertEqual(observer.call_args.kwargs['send'], bot.tg.send)

    def run_trace(self, action, has_position, mode, baseline=False):
        trace = []
        observer = Mock()
        observer.config.enabled = mode != 'OFF'
        if mode == 'ERROR':
            observer.start.side_effect = RuntimeError('observer failed')
        bot = self.bot(observer)
        bot.max_leverage = 50
        bot.live = SimpleNamespace(start=lambda: trace.append('market_start'))
        bot.observer = SimpleNamespace(observe_signal=lambda *a: trace.append('legacy_observe'), tick=lambda *a: trace.append('legacy_tick'))
        bot.last_analysis = 0
        bot.plan = SimpleNamespace(action=action, bias='LONG', setup='test', price=100)
        bot.analyzer = SimpleNamespace(analyze=lambda: bot.plan)
        bot.state.position = object() if has_position else None
        bot.state.new_day = lambda: trace.append('new_day')
        bot.state.save = lambda: trace.append('save')
        bot.commands = lambda: trace.append('commands')
        bot.record_plan_visibility = lambda *a: trace.append('visibility')
        bot.maybe_visibility_alert = lambda *a: trace.append('notice')
        bot.evaluate_thesis_change = lambda *a: trace.append('thesis')
        bot.signal_id = lambda *a: 'id'
        bot.open_real = lambda *a: trace.append('open')
        bot.get_mark = lambda: 100
        bot.manage_real = lambda *a: trace.append('manage')
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        stop.wait.side_effect = lambda *a: trace.append('wait')
        with patch.object(self.live.C, 'STOP_EVENT', stop), patch.object(self.live, 'LIVE_EXECUTION', True), \
             patch.object(self.live, 'log'), patch('requests.sessions.Session.request', side_effect=AssertionError('No real HTTP')):
            (self.baseline_run if baseline else self.live.RealAuto.run)(bot)
        return trace

    def test_observer_off_dispatch_identical_to_main(self):
        for action in ('WAIT', 'ENTER LONG NOW', 'ENTER SHORT NOW'):
            for position in (False, True):
                self.assertEqual(self.run_trace(action, position, 'OFF'), self.run_trace(action, position, 'OFF', True))

    def test_observer_on_dispatch_identical_even_live_true(self):
        for action in ('WAIT', 'ENTER LONG NOW', 'ENTER SHORT NOW'):
            for position in (False, True):
                self.assertEqual(self.run_trace(action, position, 'ON'), self.run_trace(action, position, 'OFF', True))

    def test_observer_exception_does_not_prevent_real_position_management(self):
        trace = self.run_trace('ENTER SHORT NOW', True, 'ERROR')
        self.assertIn('thesis', trace)
        self.assertIn('manage', trace)
        self.assertEqual(trace, self.run_trace('ENTER SHORT NOW', True, 'OFF', True))

    def test_worker_math_exception_nonfatal_and_stops(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            logs = []
            o = MLRSIObserver(folder, logger=logs.append)
            o.cycle = Mock(side_effect=ValueError('secret'))
            o.stop_event = Mock()
            o.stop_event.is_set.side_effect = [False, True]
            o._worker()
            self.assertEqual(logs, ['MLRSI_OBSERVER_ERROR_IGNORED'])

    def test_owner_authorization_transport_unchanged(self):
        bot = self.live.C.Telegram('fake-token', 'owner')
        bot.api = Mock(return_value=[{'update_id': 1, 'message': {'chat': {'id': 'other'}, 'text': '/mlrsi'}},
                                    {'update_id': 2, 'message': {'chat': {'id': 'owner'}, 'text': '/mlrsi'}}])
        self.assertEqual(bot.poll_commands(), ['/mlrsi'])

    def test_mlrsi_arbitrary_cached_outputs_zero_bitunix_requests(self):
        for response in ('UNKNOWN', 'GREEN', 'RED', '3/3 GREEN', 'APPROACHING_GREEN', 'PROVISIONAL_RED'):
            observer = SimpleNamespace(status_text=lambda: response)
            self.assertEqual(self.command('/mlrsi', observer).api.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
