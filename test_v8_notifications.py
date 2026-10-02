"""Notification text only; executor AST matches the audited branch baseline."""
import ast
import hashlib
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs
import v8_executor
from v8_notifications import render_v8_notification


class NotificationTests(unittest.TestCase):
    def test_long_signal_disarmed_distinct_from_copilot(self):
        text = render_v8_notification('V8 SIGNAL LONG')
        for value in ('V8 STRATEGY SIGNAL', '🟢 LONG detectado', 'EJECUCIÓN REAL DESARMADA',
                      'NO HA ABIERTO UNA OPERACIÓN POR ESTA SEÑAL', 'NO es la decisión del Manual Copilot'):
            self.assertIn(value, text)

    def test_short_presentation_symmetric_without_strategy_change(self):
        self.assertIn('🔴 SHORT detectado', render_v8_notification('V8 SIGNAL SHORT'))

    def test_flat_is_not_short(self):
        text = render_v8_notification('V8 SIGNAL FLAT')
        self.assertIn('FLAT detectado', text)
        self.assertNotIn('SHORT detectado', text)

    def test_armed_signal_never_claims_no_operation(self):
        text = render_v8_notification('V8 SIGNAL LONG', True)
        self.assertNotIn('NO HA ABIERTO', text)
        self.assertIn('NO confirma que se haya ejecutado', text)

    def test_disarm_file_overrides_presentation_only(self):
        self.assertIn('EJECUCIÓN REAL DESARMADA', render_v8_notification('V8 SIGNAL LONG', True, True))

    def test_real_open_confirmed_even_if_now_disarmed(self):
        text = render_v8_notification('V8 REAL LONG OPENED', False)
        self.assertIn('APERTURA REAL CONFIRMADA', text)
        self.assertNotIn('NO HA ABIERTO', text)

    def test_real_close_confirmed(self):
        self.assertIn('CIERRE REAL CONFIRMADO', render_v8_notification('V8 REAL POSITION CLOSED'))

    def test_blocked_uncertainty_does_not_claim_order_absent(self):
        text = render_v8_notification('V8 REAL BLOCKED — unresolved order; read-only reconciliation required', True)
        self.assertIn('NO confirma ejecución ni cierre de órdenes pendientes', text)
        self.assertNotIn('NO HA ABIERTO', text)

    def test_disabled_gate_readable(self):
        text = render_v8_notification('V8 REAL BLOCKED — V8_LIVE_EXECUTION=false or DISARM')
        self.assertIn('EJECUCIÓN REAL DESARMADA', text)
        self.assertNotIn('V8_LIVE_EXECUTION=false', text)

    def test_unknown_message_never_echoes_payload(self):
        self.assertNotIn('PRIVATE_SECRET', render_v8_notification('PRIVATE_SECRET RAW BODY'))

    def test_entire_executor_ast_except_renderer_exact_baseline(self):
        # 6b5da7eb0f1da40cf2793f0fab8a27fe68bae8dc, before this text-only PR.
        root = ast.parse(inspect.getsource(v8_executor))
        imports = [n for n in root.body if isinstance(n, ast.ImportFrom) and n.module == 'v8_notifications']
        self.assertEqual(len(imports), 1)
        root.body.remove(imports[0])
        telegram = next(n for n in root.body if isinstance(n, ast.FunctionDef) and n.name == 'telegram')
        call = telegram.body[0]
        self.assertIsInstance(call, ast.Assign)
        self.assertEqual(call.value.func.id, 'render_v8_notification')
        telegram.body.pop(0)
        digest = hashlib.sha256(ast.dump(root).encode()).hexdigest()
        self.assertEqual(digest, 'c3437fd0e6b49f3efe48ec97a0d7decf859247d2ac1fed665df81c4bba8b2bc7')

    def test_transport_uses_renderer_without_modifying_env_or_state(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as directory:
            values = {'TELEGRAM_BOT_TOKEN': 'fake-token', 'TELEGRAM_CHAT_ID': 'fake-owner',
                      'TELEGRAM_ALERT_CHAT_ID': '', 'V8_LIVE_EXECUTION': 'false', 'V8_DATA_DIR': directory}
            with patch.dict(os.environ, values), patch('v8_executor.urlopen', return_value=response) as outbound:
                with patch('v8_executor.json.load', return_value={'ok': True}):
                    original = dict(os.environ)
                    v8_executor.telegram('V8 SIGNAL LONG')
                    self.assertEqual(dict(os.environ), original)
                    self.assertEqual(list(Path(directory).iterdir()), [])
            request = outbound.call_args.args[0]
            text = parse_qs(request.data.decode())['text'][0]
            self.assertIn('V8 STRATEGY SIGNAL', text)
            self.assertIn('EJECUCIÓN REAL DESARMADA', text)


if __name__ == '__main__':
    unittest.main()
