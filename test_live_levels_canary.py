"""Offline regression for the observed intrabar crossing and restart evidence."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Guardian workflow installs dependencies') from None
import copilot_audit as audit
import test_guardian_ux as ux
from guardian_commands import _level_view, _levels, _why, render_command, SnapshotCache, TelegramCommands
from guardian_signals import confirmed_market_levels, direction
from guardian_risk import Config
from guardian_bitunix import POST_ALLOWLIST, PLACE_SL, FLASH_CLOSE
from guardian_telegram import render_copilot


def production_case():
    # User-observed prices; illustrative ATR only, never presented as a live read.
    levels = dict(status='AVAILABLE', reference_price=84040.72, resistance=84048.01,
                  support=84019., atr_1h=500., resistance_distance_pct=7.29 / 84040.72,
                  structural=dict(status='AVAILABLE', resistance=84098.01, support=83948.))
    return dict(bias='WAIT', trend4='BULL', trend1='BULL', momentum='NEUTRAL', taker_buy=.463,
                structure='MIXED', entry_quality='CAUTION', market_levels=levels)


class LivePresentationTests(unittest.TestCase):
    def setUp(self):
        self.data = production_case()
        self.mark = 84140.90

    def test_mark_above_r1_awaits_closed_quarter(self):
        self.assertIn('Mark por encima de R1, ruptura 15m todavía NO confirmada',
                      _levels(self.data, mark=self.mark))

    def test_mark_below_s1_awaits_closed_quarter(self):
        self.assertIn('Mark por debajo de S1, pérdida 15m todavía NO confirmada',
                      _levels(self.data, mark=83900))

    def test_mark_above_r2_awaits_closed_hour(self):
        self.assertIn('Mark por encima de R2, ruptura 1H todavía NO confirmada',
                      _levels(self.data, mark=self.mark))

    def test_mark_below_s2_awaits_closed_hour(self):
        self.assertIn('Mark por debajo de S2, pérdida 1H todavía NO confirmada',
                      _levels(self.data, mark=83900))

    def test_resistance_not_relabelled_support(self):
        text = _levels(self.data, mark=self.mark)
        self.assertIn('🔴 R1: 84,048.01', text)
        self.assertIn('🔴 R2: 84,098.01', text)
        self.assertNotIn('S1: 84,048.01', text)
        self.assertNotIn('S2: 84,098.01', text)

    def test_support_not_relabelled_resistance(self):
        text = _levels(self.data, mark=83900)
        self.assertIn('🟢 S1: 84,019.00', text)
        self.assertIn('🟢 S2: 83,948.00', text)
        self.assertNotIn('R1: 84,019.00', text)

    def test_current_mark_signed_distance_both_sides(self):
        for mark, expected in ((90, 10 / 90), (110, -10 / 110), (100, 0)):
            view = _level_view(95, mark, 100, 'R1', '15m')
            self.assertAlmostEqual(view['distance_pct'], expected)
        text = _levels(self.data, mark=self.mark)
        self.assertIn('Distancia desde mark: -0.11% (nivel por debajo del mark)', text)
        self.assertIn('Desde cierre de referencia: +0.01%', text)

    def test_live_atr_distance(self):
        view = _level_view(84040.72, self.mark, 84048.01, 'R1', '15m', 500)
        self.assertAlmostEqual(view['distance_atr'], abs(self.mark - 84048.01) / 500)
        self.assertIn('0.19 ATR1H desde mark', _levels(self.data, mark=self.mark))

    def test_equality_does_not_claim_crossing(self):
        self.assertFalse(_level_view(90, 100, 100, 'R1', '15m')['crossed'])
        self.assertEqual(_level_view(90, 100, 100, 'R1', '15m')['mark_relation'], 'AT')

    def test_missing_invalid_mark_never_falls_back_to_reference(self):
        for mark in (None, 0, -1, float('nan'), float('inf')):
            text = _levels(self.data, mark=mark)
            self.assertIn('Distancia desde mark: Sin mark verificable', text)
            self.assertNotIn('todavía NO confirmada', text)
            self.assertNotIn('muy cerca', _why(self.data, mark=mark))

    def test_reference_mark_relationships_and_timeframe(self):
        view = _level_view(90, 110, 100, 'R2', '1H')
        self.assertEqual((view['reference_relation'], view['mark_relation'], view['timeframe']),
                         ('BELOW', 'ABOVE', '1H'))
        view = _level_view(110, 90, 100, 'S2', '1H')
        self.assertEqual((view['reference_relation'], view['mark_relation']), ('ABOVE', 'BELOW'))

    def view(self):
        return dict(timestamp=100, data=self.data, mark=self.mark, position_verified=True,
                    position=None, risk=None, sl_status='No verificado', stop_target=None,
                    mode='SHADOW', protection='👁️ GUARDIAN: SHADOW\n🔒 Protección automática DESARMADA',
                    human_snapshot=render_copilot(self.data, Config()))

    def test_status_compact_crossed_lines_both_scales(self):
        text = render_command('/status', self.view(), 100)
        self.assertIn('🔴 R1: 84,048.01\n⏳ Mark encima — falta cierre 15m', text)
        self.assertIn('🔴 R2: 84,098.01\n⏳ Mark encima — falta cierre 1H', text)
        self.assertNotIn('Desde cierre de referencia', text)

    def test_levels_watch_matches_current_mark(self):
        text = render_command('/levels', self.view(), 100)
        for label, frame in (('R1', '15m'), ('R2', '1H')):
            self.assertIn(f'BTC está actualmente sobre {label}, pero falta un cierre {frame}', text)
        self.assertNotIn('Cierre 15m por encima de 84,048.01', text)
        self.assertNotIn('Cierre 1H sobre R2', text)
        self.mark = 83900
        text = render_command('/levels', self.view(), 100)
        self.assertIn('BTC está actualmente bajo S1, pero falta un cierre 15m', text)
        self.assertIn('BTC está actualmente bajo S2, pero falta un cierre 1H', text)

    def test_why_no_false_near_after_crossing(self):
        text = render_command('/why', self.view(), 100)
        self.assertIn('Mark por encima de R1', text)
        self.assertIn('Mark por encima de R2', text)
        self.assertNotIn('muy cerca de R1', text)
        self.assertNotIn('Precio muy cerca', text)

    def test_why_near_uses_mark_not_reference(self):
        self.assertIn('Mark muy cerca de R1', _why(self.data, mark=84047))
        text = _why(self.data, mark=83000)
        self.assertNotIn('muy cerca de R1', text)

    def test_live_mark_never_changes_direction_quality_or_causal_state(self):
        for bias, quality in (('WAIT', 'CAUTION'), ('LONG_ALLOWED', 'GOOD'), ('SHORT_ALLOWED', 'POOR')):
            self.data.update(bias=bias, entry_quality=quality)
            original = copy.deepcopy(self.data)
            with patch('requests.sessions.Session.request', side_effect=AssertionError('NO HTTP')) as http:
                for mark in (83000, 84047, self.mark, 90000):
                    _levels(self.data, mark=mark)
                    _why(self.data, mark=mark)
                    self.assertEqual(self.data, original)
            http.assert_not_called()
        self.assertEqual(direction('BULL', 'BULL', 'NEUTRAL', .463, 'MIXED')[0], 'WAIT')

    def test_closed_engine_unchanged_after_intrabar_cross(self):
        h, q, now = ux.LevelTests.candles()
        before = confirmed_market_levels(h, q, 105, now_ms=now)
        self.assertEqual(before, confirmed_market_levels(h, q, 115, now_ms=now))
        self.assertEqual(before['resistance'], 110)
        # Only a NEW CLOSED reference can make the normal engine reconsider levels.
        q = np.vstack([q, [now, 115, 119, 111, 115, 10, 5]])
        self.assertEqual(before, confirmed_market_levels(h, q, 115, now_ms=now))
        after = confirmed_market_levels(h, q, 115, now_ms=now + 900000)
        self.assertEqual(after['reference_price'], 115)
        self.assertNotEqual(after['resistance'], before['resistance'])
        self.assertNotEqual(after['support'], 110)  # no automatic role reversal

    def test_arbitrary_commands_readonly_owner_only_zero_network(self):
        cache = SnapshotCache()
        cache.publish(self.view())
        reply = Mock(return_value=True)
        commands = TelegramCommands('test-token', 'owner', cache, reply, enabled=True, clock=lambda: 100)
        before = cache.read()
        with patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK')) as http:
            for text in ('/status', '/why', '/position', '/risk', '/levels', '/stats', '/arm', '/close') + tuple('/' + str(i) for i in range(100)):
                update = dict(message=dict(chat=dict(id='alert-only'), text=text))
                self.assertFalse(commands.process(update))
                update['message']['chat']['id'] = 'owner'
                self.assertTrue(commands.process(update))
        http.assert_not_called()
        self.assertEqual(cache.read(), before)
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})
        self.assertFalse(Config().armed('SL'))
        self.assertFalse(Config().armed('CLOSE'))


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.boot_a, self.boot_b = str(uuid.uuid4()), str(uuid.uuid4())
        self.now = 1800000000.
        self.stores = []

    def tearDown(self):
        for store in self.stores:
            store.close()

    def open(self, boot=None):
        store = audit.AuditStore(self.root, boot_id=boot or self.boot_a, clock=lambda: self.now)
        self.stores.append(store)
        return store

    def canary(self):
        return json.loads((self.root / 'durability_canary.json').read_text('utf-8'))

    def restart(self, boot=None):
        self.stores[-1].close()
        self.now += 10
        return self.open(boot or self.boot_b)

    def test_first_initialization(self):
        store = self.open()
        row = self.canary()
        self.assertEqual(row['boot_count'], 1)
        self.assertEqual(row['created_at'], self.now)
        self.assertEqual(str(uuid.UUID(row['uuid'])), row['uuid'])
        self.assertNotIn('last_reopened_at', row)
        self.assertEqual(store.durability, 'INITIALIZED_NOT_RESTART_VERIFIED')

    def test_survives_simulated_restart_same_uuid_count_increments(self):
        self.open()
        old = self.canary()
        store = self.restart()
        new = self.canary()
        self.assertEqual(new['uuid'], old['uuid'])
        self.assertEqual(new['created_at'], old['created_at'])
        self.assertEqual(new['boot_count'], 2)
        self.assertEqual(new['last_reopened_at'], self.now)
        self.assertEqual(store.durability, 'REOPENED_FROM_PERSISTENT_STORAGE')
        self.restart(str(uuid.uuid4()))
        self.assertEqual(self.canary()['boot_count'], 3)

    def test_same_process_store_restart_does_not_claim_survival(self):
        self.open()
        store = self.restart(self.boot_a)
        self.assertEqual(self.canary()['boot_count'], 1)
        self.assertEqual(store.durability, 'INITIALIZED_NOT_RESTART_VERIFIED')
        self.restart(self.boot_b)
        store = self.restart(self.boot_b)
        self.assertEqual(self.canary()['boot_count'], 2)
        self.assertEqual(store.durability, 'REOPENED_FROM_PERSISTENT_STORAGE')

    def test_real_subprocess_boot_preserves_uuid(self):
        self.now = audit.time.time() - 1
        self.open().close()
        old = self.canary()
        result = subprocess.run([sys.executable, '-c',
                                 'from copilot_audit import AuditStore; import sys; s=AuditStore(sys.argv[1]); s.close()',
                                 str(self.root)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(self.canary()['uuid'], old['uuid'])
        self.assertEqual(self.canary()['boot_count'], 2)

    def test_corrupt_canary_fails_safe_not_overwritten(self):
        self.open().close()
        path = self.root / 'durability_canary.json'
        path.write_text('{invalid secret-payload', encoding='utf-8')
        with patch('builtins.print') as output:
            store = self.open(self.boot_b)
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        self.assertEqual(path.read_text('utf-8'), '{invalid secret-payload')
        output.assert_not_called()

    def test_malformed_canary_fields_fail_safe(self):
        self.open().close()
        original = self.canary()
        for field, value in (('uuid', 'bad'), ('boot_count', True), ('boot_count', 0),
                             ('created_at', float('nan')), ('last_boot_id', None),
                             ('last_reopened_at', float('inf')), ('unknown', 'payload')):
            row = dict(original, **{field: value})
            (self.root / 'durability_canary.json').write_text(json.dumps(row), encoding='utf-8')
            store = self.open(self.boot_b)
            self.assertEqual(store.durability, 'NOT_VERIFIED')
            store.close()

    def test_missing_previously_initialized_canary_fails_safe(self):
        self.open().close()
        (self.root / 'durability_canary.json').unlink()
        store = self.open(self.boot_b)
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        self.assertFalse((self.root / 'durability_canary.json').exists())

    def test_valid_canary_with_wrong_expected_uuid_fails_safe(self):
        store = self.open()
        store.state['durability_canary_uuid'] = str(uuid.uuid4())
        store.save()
        store = self.restart()
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        self.assertEqual(self.canary()['boot_count'], 1)

    def test_unwritable_canary_nonfatal_unverified(self):
        with patch.object(audit.AuditStore, '_write_canary', side_effect=OSError('secret-payload')), patch('builtins.print') as output:
            store = self.open()
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        store.append('snapshots', {'safe': True})
        output.assert_not_called()

    def test_clock_regression_does_not_increment(self):
        self.open().close()
        self.now -= 10
        store = self.open(self.boot_b)
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        self.assertEqual(self.canary()['boot_count'], 1)

    def test_atomic_replace_and_fsync_file_directory(self):
        operations = []
        original_fsync, original_replace = os.fsync, os.replace
        def fsync(fd):
            operations.append('fsync')
            return original_fsync(fd)
        def replace(src, dst):
            operations.append(Path(dst).name)
            return original_replace(src, dst)
        with patch('copilot_audit.os.fsync', side_effect=fsync), patch('copilot_audit.os.replace', side_effect=replace):
            store = self.open()
        canary_replace = operations.index('durability_canary.json')
        self.assertEqual(operations[canary_replace - 1], 'fsync')
        if os.name != 'nt':
            self.assertEqual(operations[canary_replace + 1], 'fsync')
        self.assertFalse((self.root / 'durability_canary.json.tmp').exists())
        store.close()
        with patch.object(audit.AuditStore, 'sync_directory', autospec=True) as sync:
            self.open(self.boot_b)
        self.assertGreaterEqual(sync.call_count, 1)

    def test_restart_write_failure_never_claims_persistence(self):
        self.open().close()
        with patch('copilot_audit.os.replace', side_effect=OSError('secret-payload')):
            store = self.open(self.boot_b)
        self.assertEqual(store.durability, 'NOT_VERIFIED')
        self.assertEqual(self.canary()['boot_count'], 1)

    def test_canary_only_harmless_metadata_no_environment(self):
        with patch.dict(os.environ, {'BITUNIX_API_SECRET': 'must-not-store', 'TELEGRAM_BOT_TOKEN': 'secret-token',
                                     'TELEGRAM_CHAT_ID': 'secret-chat'}):
            self.open()
        self.assertEqual(set(self.canary()), {'uuid', 'created_at', 'boot_count', 'last_boot_id'})
        for path in self.root.glob('*.json'):
            text = path.read_text('utf-8')
            for secret in ('must-not-store', 'secret-token', 'secret-chat', 'BITUNIX', 'TELEGRAM'):
                self.assertNotIn(secret, text)

    def test_stats_yellow_first_boot_green_later_red_unverified(self):
        first = self.open()
        text = audit.render_stats(audit.statistics_snapshot(first, int(self.now * 1000)))
        self.assertIn(audit.PERSISTENCE_MESSAGES['INITIALIZED_NOT_RESTART_VERIFIED'], text)
        store = self.restart()
        text = audit.render_stats(audit.statistics_snapshot(store, int(self.now * 1000)))
        self.assertIn(audit.PERSISTENCE_MESSAGES['REOPENED_FROM_PERSISTENT_STORAGE'], text)
        store.durability = 'NOT_VERIFIED'
        self.assertIn(audit.PERSISTENCE_UNVERIFIED, audit.render_stats(audit.statistics_snapshot(store, int(self.now * 1000))))
        self.assertIn(audit.PERSISTENCE_UNVERIFIED, audit.render_stats(None))


class SafetyBaselineTests(unittest.TestCase):
    def test_rules_and_mutation_ast_unchanged_from_main_bdf7ae4(self):
        # Intentional freeze for this presentation-only corrective PR. An audited
        # future rule change must explicitly update this baseline regression.
        expected = {
            'guardian_signals.py': '36b5853b101ce96a113aa30d38432e87c5c2c583f215b280ac953b3fbe0662e3',
            'guardian_risk.py': 'e916050d1b5dc00ce3f12a21575f94a5deac85db8e228c318bd5cab25e158486',
            'guardian_bitunix.py': 'f33cb306655fb4770022021020ca2827d5ee76f6058ffb052b90288d55ea1dfe',
            'trade_guardian.py': 'e36093c09d70e1831d70dc37ba52c590501e804a1784b727bd5bb7d2bb8a77da',
            'guardian_market.py': 'bb897496c59f02c13b154ab119121f819004184489f64752d09739fc0b0ccc76',
            'guardian_store.py': 'b146bba119575444d62ac79780ee8334fd193ebe43f71f812483e42977967e43',
            'trend_v8.py': 'fc9454cf32ce759ec601de47ecc5d67733ade96546b1dafe6d09a6bd4e796b35',
        }
        root = Path(__file__).resolve().parent
        for path, digest in expected.items():
            if path == 'trade_guardian.py':
                # Strip only exact audited passive host additions; retain old digest.
                from mlrsi_safety_audit import guardian_baseline_tree, verify_guardian_ast
                self.assertTrue(verify_guardian_ast())
                tree = guardian_baseline_tree(path)
            else:
                tree = ast.parse((root / path).read_text('utf-8'))
            self.assertEqual(hashlib.sha256(ast.dump(tree).encode()).hexdigest(), digest, path)
        methods = {
            'guardian_commands.py:TelegramCommands': 'a801dc35cecf05eeb7aee2ab2139cf6dcbd393ded733868a7ac5672f34bc02c2',
            'guardian_commands.py:SnapshotCache': '87ae5ccb1e3fa3d64bb227f9d83c6447d10b6c318eb9657739bfb84ec3603892',
            'copilot_audit.py:ForwardAudit': '3190cbc3f753ca76a1ed11b372b5affa8b4579a561ce9c30a8baa1650e467e84',
            'copilot_audit.py:packet': 'e8748dca3f2a2b28b5f3d30a6e306035e5311ed28d1261e4c0463dc4730d3f95',
            'copilot_audit.py:evaluate': '2249809fc8f0af8bdce6697235112286e423d271f7205f4874a728aad64ed9c0',
        }
        for path_name, digest in methods.items():
            path, name = path_name.split(':')
            if path == 'guardian_commands.py':
                tree = guardian_baseline_tree(path)
            else:
                tree = ast.parse((root / path).read_text('utf-8'))
            node = next(n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
            self.assertEqual(hashlib.sha256(ast.dump(node).encode()).hexdigest(), digest, path_name)


if __name__ == '__main__':
    unittest.main()
