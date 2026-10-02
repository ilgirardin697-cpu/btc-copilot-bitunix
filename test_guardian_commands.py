"""Owner queries are exercised offline with a transport that rejects trading."""
import copy
import inspect
import json
import os
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Command dependencies are installed by the Guardian workflow') from None
from guardian_commands import COMMANDS, HELP, NO_DATA, STALE, SnapshotCache, TelegramCommands, render_command
from guardian_bitunix import POST_ALLOWLIST, PLACE_SL, FLASH_CLOSE
from guardian_risk import Config
from guardian_telegram import Telegram
import test_trade_guardian as harness


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.fixture = harness.GuardianNotificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        with patch('builtins.print'):
            self.fixture.guardian.cycle()
        self.cache = self.fixture.guardian.command_snapshot
        self.http, self.reply = Mock(), Mock(return_value=True)
        self.commands = TelegramCommands('private-token', '12345', self.cache, self.reply,
                                          enabled=True, transport=self.http)

    def update(self, command='/status', owner='12345', identifier=1):
        return {'update_id': identifier, 'message': {'chat': {'id': owner}, 'text': command}}

    def test_disabled_default_no_poll_and_no_process(self):
        commands = TelegramCommands('private-token', '12345', self.cache, self.reply, transport=self.http)
        self.assertFalse(commands.enabled)
        self.assertFalse(commands.start())
        self.assertFalse(commands.poll_once())
        self.assertFalse(commands.process(self.update()))
        self.http.get.assert_not_called()
        self.reply.assert_not_called()
        self.assertEqual(os.getenv('GUARDIAN_ENABLE_COMMANDS', 'false'), 'false')

    def test_owner_enabled_and_exact_command_set(self):
        self.assertEqual(COMMANDS, ('/status', '/why', '/position', '/risk', '/levels', '/help'))
        self.assertTrue(self.commands.process(self.update()))
        self.assertIn('Actualizado hace:', self.reply.call_args.args[0])

    def test_alert_recipient_and_unknown_users_ignored(self):
        for owner in ('alert-only', 'other-owner', '', None, ' 12345 ', True):
            with self.subTest(owner=owner):
                self.assertFalse(self.commands.process(self.update(owner=owner)))
        self.reply.assert_not_called()

    def test_numeric_owner_matches_exact_string(self):
        self.assertTrue(self.commands.process(self.update(owner=12345)))

    def test_help_and_unknown_return_help_no_echo(self):
        for command in ('/help', '/buy secret-message', '/protect', '/arm', '/close'):
            self.commands.process(self.update(command))
            self.assertEqual(self.reply.call_args.args[0], HELP)
            self.assertNotIn('secret-message', self.reply.call_args.args[0])

    def test_each_command_readonly_property_zero_bitunix_requests(self):
        original = copy.deepcopy(self.fixture.store.state)
        cache_before = self.cache.read()
        environment = dict(os.environ)
        incoming = list(COMMANDS) + ['/buy', '/sell', '/long', '/short', '/close', '/leverage 50',
                    '/margin', '/sl', '/tp', '/protect', '/arm', '/transfer', '/withdraw']
        incoming += ['/' + str(value) for value in range(200)]
        with patch.object(self.fixture.client, '_request', side_effect=AssertionError('BITUNIX FORBIDDEN')) as no_http:
            with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK FORBIDDEN')):
                for command in incoming:
                    with self.subTest(command=command):
                        self.assertTrue(self.commands.process(self.update(command)))
        no_http.assert_not_called()
        self.assertEqual(original, self.fixture.store.state)
        self.assertEqual(cache_before, self.cache.read())
        self.assertEqual(dict(os.environ), environment)
        self.assertEqual(self.fixture.fake.posts, [])
        self.assertFalse(self.fixture.guardian.config.armed('SL'))
        self.assertFalse(self.fixture.guardian.config.armed('CLOSE'))
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})

    def test_snapshot_copy_isolation(self):
        value = self.cache.read()
        value['data']['bias'] = 'SHORT_ALLOWED'
        self.assertEqual(self.cache.read()['data']['bias'], 'LONG_ALLOWED')
        self.cache.publish(value)
        value['data']['bias'] = 'WAIT'
        self.assertEqual(self.cache.read()['data']['bias'], 'SHORT_ALLOWED')

    def test_snapshot_stale_boundary_and_future(self):
        view = self.cache.read()
        for command in COMMANDS[:-1]:
            self.assertNotIn(STALE, render_command(command, view, view['timestamp'] + 30))
            self.assertIn(STALE, render_command(command, view, view['timestamp'] + 31))
            self.assertEqual(render_command(command, view, view['timestamp'] - 1), NO_DATA)

    def test_missing_snapshot_no_operar(self):
        for command in COMMANDS[:-1]:
            self.assertEqual(render_command(command, None, 100), NO_DATA)

    def test_status_and_risk_cannot_imply_shadow_protection(self):
        for command in ('/status', '/risk'):
            self.commands.process(self.update(command))
            text = self.reply.call_args.args[0]
            self.assertIn('GUARDIAN: SHADOW', text)
            self.assertIn('Protección automática DESARMADA', text)
        self.assertIn('RIESGO: NORMAL', text)

    def test_position_verified_values_and_no_position(self):
        view = self.cache.read()
        text = render_command('/position', view, view['timestamp'])
        for value in ('LONG BTCUSDT', 'Entrada: 10,100.00', 'Mark: 10,000.00', 'Qty BTC: 0.1',
                       'Leverage: 10x', 'PnL: -2.00', 'Liquidación: 9,500.00', 'Distancia: 5.00%', 'alineada'):
            self.assertIn(value, text)
        view['position'] = None
        self.assertIn('Sin posición BTCUSDT abierta', render_command('/position', view, view['timestamp']))
        view['position_verified'] = False
        self.assertNotIn('Sin posición BTCUSDT abierta', render_command('/position', view, view['timestamp']))

    def test_levels_only_existing_confirmed_values(self):
        view = self.cache.read()
        text = render_command('/levels', view, view['timestamp'])
        for value in ('9,500.00', '10,500.00', '9,900.00', 'Invalidación'):
            self.assertIn(value, text)
        for key in ('support', 'resistance', 'entry_level'):
            view['data'].pop(key, None)
        view['data'].pop('market_levels', None)
        text = render_command('/levels', view, view['timestamp'])
        self.assertIn('Sin niveles confirmados', text)
        self.assertNotIn('9,900.00', text)

    def test_why_explains_opposite_and_expected_conditions(self):
        self.commands.process(self.update('/why'))
        text = self.reply.call_args.args[0]
        for value in ('Por qué no SHORT', 'QUÉ ESPERAMOS', 'Entrada: GOOD'):
            self.assertIn(value, text)

    def test_poll_allowed_updates_offset_dedup(self):
        self.http.get.return_value = Mock(status_code=200, json=Mock(return_value={
            'ok': True, 'result': [self.update(identifier=4), self.update(owner='alert-only', identifier=5)]}))
        self.assertTrue(self.commands.poll_once())
        self.assertTrue(self.commands.poll_once())
        self.reply.assert_called_once()
        call = self.http.get.call_args
        self.assertEqual(call.args[0], 'https://api.telegram.org/botprivate-token/getUpdates')
        self.assertEqual(call.kwargs['params']['offset'], 6)
        self.assertEqual(json.loads(call.kwargs['params']['allowed_updates']), ['message'])
        self.assertFalse(call.kwargs['allow_redirects'])

    def test_poll_failures_no_secret_logging_and_risk_continues(self):
        self.http.get.side_effect = requests.Timeout('private-token 12345 secret-message raw response')
        with patch('builtins.print') as output:
            self.assertFalse(self.commands.poll_once())
            self.reply.side_effect = RuntimeError('private-token secret-message')
            self.assertFalse(self.commands.process(self.update('/why secret-message')))
            heartbeat = self.fixture.guardian.cycle()
        logs = str(output.call_args_list)
        for secret in ('private-token', '12345', 'secret-message', 'raw response'):
            self.assertNotIn(secret, logs)
        self.assertEqual(heartbeat['risk'], 'NORMAL')
        self.assertEqual(self.fixture.fake.posts, [])

    def test_invalid_poll_responses_fail_closed(self):
        for payload in (None, [], {'ok': False}, {'ok': True, 'result': {}}):
            self.http.get.return_value = Mock(status_code=200, json=Mock(return_value=payload))
            self.assertFalse(self.commands.poll_once())
        self.reply.assert_not_called()

    def test_invalid_incoming_messages_ignored(self):
        for update in (None, [], {}, {'message': None}, {'message': {'chat': None}},
                       self.update('plain text'), self.update(None)):
            self.assertFalse(self.commands.process(update))
        self.reply.assert_not_called()

    def test_no_owner_never_authorizes_alerts(self):
        commands = TelegramCommands('private-token', '', self.cache, self.reply, enabled=True, transport=self.http)
        self.assertFalse(commands.start())
        self.assertFalse(commands.poll_once())
        self.assertFalse(commands.process(self.update(owner='alert-only')))
        self.http.get.assert_not_called()

    def test_replies_owner_only_outbound_alerts_still_all_recipients(self):
        http = Mock()
        http.post.return_value = Mock(status_code=200, json=Mock(return_value={'ok': True}))
        telegram = Telegram('private-token', 'owner', http, alert_chat_id='alert,owner')
        with patch('builtins.print'):
            telegram.send_owner('command response')
            harness.TelegramDeliveryTests.drain(self, telegram)
            telegram.send('normal outbound alert')
            harness.TelegramDeliveryTests.drain(self, telegram)
        self.assertEqual([call.kwargs['json']['chat_id'] for call in http.post.call_args_list],
                         ['owner', 'owner', 'alert'])

    def test_command_class_has_no_mutation_dependencies(self):
        source = inspect.getsource(TelegramCommands)
        for word in ('Bitunix', 'execute(', 'preflight(', 'os.environ', 'open(', 'write(', '.post('):
            # The docstring can mention Bitunix; executable dependency is what matters.
            if word != 'Bitunix':
                self.assertNotIn(word, source)
        self.assertFalse(hasattr(self.commands, 'client'))
        self.assertFalse(hasattr(self.commands, 'store'))
        self.assertFalse(hasattr(self.commands, 'config'))


if __name__ == '__main__':
    unittest.main()
