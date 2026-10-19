"""Snapshot-only gates and manual display. Synthetic fixtures, no market research."""
import ast
from collections import Counter
import copy
import hashlib
import inspect
import itertools
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch

from bitman_manual import readiness, render

ROOT = Path(__file__).resolve().parent
BASE = '5a61ca5cb942290377909dcfb569651a80c39dd3'


def ready_snapshot(state='UP'):
    color = 'GREEN' if state == 'UP' else 'RED'
    return dict(state=state, strength='STRONG', evidence_grade='A',
        timing_state='impulse_up' if state == 'UP' else 'impulse_down', mlrsi_confirmation='SUPPORTING',
        macro_bias=state, swing_bias=state, components={tf: {'bias': state} for tf in ('1D', '4H', '1H')},
        display_mlrsi={tf: {'color': color} for tf in ('15m', '1H', '4H')}, structure={},
        timestamp=1792432800000, symbol='BTCUSDT', venue='BINANCE_USDM_PERPETUAL',
        shadow_only=True, trade_authority=False, not_trade_signal=True)


def current_example():
    # Only fields actually supplied by the owner; missing grade/timing are not reconstructed.
    return dict(state='TRANSITION', strength='WEAK',
        components={'1D': {'bias': 'DOWN'}, '4H': {'bias': 'TRANSITION'}, '1H': {'bias': 'DOWN'}},
        display_mlrsi={'15m': {'color': 'RED'}, '1H': {'color': 'NEUTRAL'}, '4H': {'color': 'NEUTRAL'}})


class ReadinessTests(unittest.TestCase):
    def changed(self, state='UP', **changes):
        return readiness.evaluate(dict(ready_snapshot(state), **changes))

    def assert_status(self, result, status):
        self.assertEqual(result['status'], status)
        self.assertIs(result['gates_ready'], status.startswith('READY_'))
        self.assertNotIn('operate', result)
        self.assertEqual(result['side'], status.split('_')[1] if status != 'WAIT' else None)

    def test_transition_always_wait(self):
        self.assert_status(self.changed(state='TRANSITION'), 'WAIT')

    def test_unclear_always_wait(self):
        self.assert_status(self.changed(state='UNCLEAR'), 'WAIT')

    def test_conflict_always_wait(self):
        self.assert_status(self.changed(state='CONFLICT'), 'WAIT')

    def test_up_weak_wait(self):
        self.assert_status(self.changed(strength='WEAK'), 'WAIT')

    def test_down_weak_wait(self):
        self.assert_status(self.changed('DOWN', strength='WEAK'), 'WAIT')

    def test_up_building_watch_long(self):
        self.assert_status(self.changed(strength='BUILDING'), 'WATCH_LONG')

    def test_down_building_watch_short(self):
        self.assert_status(self.changed('DOWN', strength='BUILDING'), 'WATCH_SHORT')

    def test_up_grade_b_watch_long(self):
        self.assert_status(self.changed(evidence_grade='B'), 'WATCH_LONG')

    def test_down_grade_b_watch_short(self):
        self.assert_status(self.changed('DOWN', evidence_grade='B'), 'WATCH_SHORT')

    def test_grade_c_always_wait(self):
        for state in ('UP', 'DOWN'):
            self.assert_status(self.changed(state, evidence_grade='C'), 'WAIT')

    def test_wrong_up_timing_watch_long(self):
        self.assert_status(self.changed(timing_state='impulse_down'), 'WATCH_LONG')

    def test_wrong_down_timing_watch_short(self):
        self.assert_status(self.changed('DOWN', timing_state='impulse_up'), 'WATCH_SHORT')

    def test_transition_or_no_impulse_timing_watch(self):
        for state, side in (('UP', 'LONG'), ('DOWN', 'SHORT')):
            for timing in ('transition', 'no_impulse'):
                self.assert_status(self.changed(state, timing_state=timing), 'WATCH_' + side)

    def test_mlrsi_neutral_watch(self):
        for state, side in (('UP', 'LONG'), ('DOWN', 'SHORT')):
            self.assert_status(self.changed(state, mlrsi_confirmation='NEUTRAL'), 'WATCH_' + side)

    def test_mlrsi_unavailable_watch(self):
        for state, side in (('UP', 'LONG'), ('DOWN', 'SHORT')):
            self.assert_status(self.changed(state, mlrsi_confirmation='UNAVAILABLE'), 'WATCH_' + side)

    def test_mlrsi_opposing_wait(self):
        for state in ('UP', 'DOWN'):
            self.assert_status(self.changed(state, mlrsi_confirmation='OPPOSING'), 'WAIT')

    def test_full_long_gates_ready_long(self):
        result = self.changed()
        self.assert_status(result, 'READY_LONG')
        self.assertEqual(result['missing_conditions'], [])
        self.assertEqual(result['reason_codes'], [])

    def test_full_short_gates_ready_short(self):
        self.assert_status(self.changed('DOWN'), 'READY_SHORT')

    def test_pullback_never_ready(self):
        for state, side in (('UP', 'LONG'), ('DOWN', 'SHORT')):
            result = self.changed(state, timing_state='pullback', pullback_direction='DOWN' if state == 'UP' else 'UP')
            self.assert_status(result, 'WATCH_' + side)
            self.assertIn('TIMING_PULLBACK', result['reason_codes'])

    def test_each_gate_alone_prevents_ready(self):
        for state in ('UP', 'DOWN'):
            for field, value in (('state', 'CONFLICT'), ('strength', 'BUILDING'), ('evidence_grade', 'B'),
                                 ('timing_state', 'no_impulse'), ('mlrsi_confirmation', 'NEUTRAL')):
                with self.subTest(state=state, field=field):
                    snapshot = ready_snapshot(state)
                    snapshot[field] = value
                    self.assertFalse(readiness.evaluate(snapshot)['gates_ready'])

    def test_exact_failed_gates_and_codes_no_passed_gate_listed(self):
        result = self.changed('DOWN', strength='BUILDING', mlrsi_confirmation='NEUTRAL')
        self.assertEqual(result, dict(gates_ready=False, status='WATCH_SHORT', side='SHORT',
            reason_codes=['STRENGTH_BUILDING', 'MLRSI_NEUTRAL'], missing_conditions=[
                dict(field='strength', actual='BUILDING', required='STRONG'),
                dict(field='mlrsi_confirmation', actual='NEUTRAL', required='SUPPORTING')]))

    def test_wait_priority_keeps_all_failed_conditions(self):
        result = self.changed(strength='WEAK', evidence_grade='C', timing_state='pullback', mlrsi_confirmation='OPPOSING')
        self.assert_status(result, 'WAIT')
        self.assertEqual([c['field'] for c in result['missing_conditions']],
                         ['strength', 'evidence_grade', 'timing_state', 'mlrsi_confirmation'])

    def test_current_real_example_wait_without_reconstructing_missing_fields(self):
        result = readiness.evaluate(current_example())
        self.assert_status(result, 'WAIT')
        self.assertIn('DIRECTION_TRANSITION', result['reason_codes'])
        self.assertIn('STRENGTH_WEAK', result['reason_codes'])
        self.assertEqual(next(c for c in result['missing_conditions'] if c['field'] == 'evidence_grade')['actual'], 'UNKNOWN')

    def test_no_direction_from_macro_indicator_color_or_direction_field(self):
        snapshot = dict(ready_snapshot(), state='TRANSITION', direction=1, macro_bias='UP', swing_bias='UP',
                        ao=999, di_plus=100, di_minus=0, confirmed_mlrsi={'4H': {'color': 'GREEN'}})
        self.assert_status(readiness.evaluate(snapshot), 'WAIT')

    def test_arbitrary_fields_cannot_affect_result_or_inject_authority(self):
        for state in ('UP', 'DOWN'):
            snapshot = ready_snapshot(state)
            expected = readiness.evaluate(snapshot)
            snapshot.update(gates_ready=False, status='WAIT', side='OTHER', reason_codes=['fake'], readiness={'gates_ready': True},
                order={'execute': True}, direction=0, strength_score=999, evidence_probability=1,
                macro_bias='DOWN', swing_bias='UP', components=object(), confirmed_mlrsi=object(),
                display_mlrsi={'4H': {'color': 'UNKNOWN'}}, provisional='RED', approaching='GREEN')
            self.assertEqual(readiness.evaluate(snapshot), expected)
        self.assert_status(self.changed(strength='WEAK', gates_ready=True, status='READY_LONG'), 'WAIT')

    def test_missing_unknown_and_malformed_gate_values_fail_closed(self):
        for field in readiness.VALUES:
            for value in (None, True, 1, {}, [], 'secret-canary', 'a' * 20000):
                with self.subTest(field=field, type=type(value).__name__):
                    result = self.changed(**{field: value})
                    self.assert_status(result, 'WAIT')
                    self.assertNotIn('secret-canary', json.dumps(result))
                    self.assertLess(len(json.dumps(result)), 2000)
            snapshot = ready_snapshot()
            del snapshot[field]
            self.assert_status(readiness.evaluate(snapshot), 'WAIT')
        for snapshot in (None, [], 'READY_LONG', True, 1):
            self.assert_status(readiness.evaluate(snapshot), 'WAIT')

    def test_no_alias_case_or_probability_substitution(self):
        for field, value in (('state', 'LONG'), ('state', 'up'), ('strength', 'strong'),
                             ('evidence_grade', 1.0), ('timing_state', 'UP'), ('mlrsi_confirmation', 'GREEN')):
            self.assert_status(self.changed(**{field: value}), 'WAIT')

    def test_input_unchanged_and_result_not_an_alias(self):
        snapshot = ready_snapshot()
        snapshot.update(strength='BUILDING', mlrsi_confirmation='NEUTRAL')
        before = copy.deepcopy(snapshot)
        one = readiness.evaluate(snapshot)
        two = readiness.evaluate(snapshot)
        self.assertEqual(snapshot, before)
        self.assertEqual(one, two)
        one['missing_conditions'][0]['actual'] = 'CHANGED'
        one['reason_codes'].append('CHANGED')
        self.assertEqual(snapshot, before)
        self.assertEqual(readiness.evaluate(snapshot), two)

    def test_function_signature_has_only_snapshot(self):
        self.assertEqual(tuple(inspect.signature(readiness.evaluate).parameters), ('snapshot',))

    def test_all_900_canonical_combinations_obey_exact_contract(self):
        combinations = itertools.product(readiness.VALUES['state'], readiness.VALUES['strength'],
            readiness.VALUES['evidence_grade'], readiness.VALUES['timing_state'], readiness.VALUES['mlrsi_confirmation'])
        count = 0
        for state, strength, grade, timing, ml in combinations:
            snapshot = dict(state=state, strength=strength, evidence_grade=grade, timing_state=timing, mlrsi_confirmation=ml)
            side = {'UP': 'LONG', 'DOWN': 'SHORT'}.get(state)
            blocked = side is None or strength == 'WEAK' or grade == 'C' or ml == 'OPPOSING'
            ready = bool(side and strength == 'STRONG' and grade == 'A' and ml == 'SUPPORTING'
                         and timing == ('impulse_up' if side == 'LONG' else 'impulse_down'))
            expected = 'WAIT' if blocked else ('READY_' if ready else 'WATCH_') + side
            result = readiness.evaluate(snapshot)
            self.assert_status(result, expected)
            self.assertIs(result['gates_ready'], ready)
            count += 1
        self.assertEqual(count, 900)

    def test_all_900_complete_results_identical_to_externally_approved_commit(self):
        baseline = json.loads((ROOT / 'tests/fixtures/bitman_readiness_approved.json').read_text('utf-8'))
        self.assertEqual(baseline['approved_commit'], '1875f91e0c8515c267129c6e9cf8ccc6bc4306fa')
        results = [readiness.evaluate(dict(zip(readiness.VALUES, values)))
                   for values in itertools.product(*readiness.VALUES.values())]
        self.assertEqual(len(results), baseline['combinations'])
        self.assertEqual(dict(Counter(r['status'] for r in results)), baseline['status_counts'])
        encoded = json.dumps(results, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), baseline['normalized_results_sha256'])

    def test_approved_gate_source_has_only_three_boolean_keyword_renames(self):
        baseline = json.loads((ROOT / 'tests/fixtures/bitman_readiness_approved.json').read_text('utf-8'))
        source = Path(readiness.__file__).read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(source.count(b'gates_ready='), 3)
        restored = source.replace(b'gates_ready=', b'operate=')
        self.assertEqual(hashlib.sha256(restored).hexdigest(), baseline['source_sha256'])

    def test_no_old_runtime_field_or_alias(self):
        for module in (readiness, render):
            self.assertNotIn('operate', Path(module.__file__).read_text('utf-8'))
        self.assertEqual(set(readiness.evaluate(ready_snapshot())),
                         {'gates_ready', 'status', 'side', 'reason_codes', 'missing_conditions'})


class RenderReadinessTests(unittest.TestCase):
    def test_ready_long_exact_headline_and_no_what_to_watch_when_no_gate_failed(self):
        text = render.render(ready_snapshot())
        self.assertIn('🎯 OPERATIVA BITMAN: SETUP READY — CANDIDATO LONG\n✅ READY_LONG', text)
        self.assertNotIn('👀 QUÉ TIENE QUE PASAR', text)
        self.assertIn('⚠️ SETUP READY = gates técnicos alineados.', text)
        self.assertIn('No garantiza rentabilidad y no es una orden automática.', text)

    def test_ready_short_exact_headline(self):
        text = render.render(ready_snapshot('DOWN'))
        self.assertIn('🎯 OPERATIVA BITMAN: SETUP READY — CANDIDATO SHORT\n✅ READY_SHORT', text)
        self.assertIn('• Timing 1H: impulse_down (alineado)', text)
        self.assertIn('• ML RSI 4H: SUPPORTING', text)

    def test_current_real_example_no_wait_and_4h_confirmation(self):
        text = render.render(current_example())
        self.assertIn('🎯 OPERATIVA BITMAN: NO OPERAR\n⏳ WAIT', text)
        self.assertIn('4H 🟡 TRANSITION', text)
        self.assertIn('Direction: TRANSITION → necesita UP / DOWN', text)
        self.assertIn('Strength: WEAK → necesita STRONG', text)
        self.assertIn('Confirmación 4H de la dirección', text)
        self.assertNotIn('CANDIDATO', text)
        self.assertNotIn('WATCH_SHORT', text)  # macro bearish alone does not assign a candidate

    def test_watch_lists_only_failed_gates(self):
        snapshot = dict(ready_snapshot('DOWN'), strength='BUILDING', mlrsi_confirmation='NEUTRAL')
        lines = render.operability_lines(snapshot)
        text = '\n'.join(lines)
        self.assertIn('🎯 OPERATIVA BITMAN: NO OPERAR\n👀 WATCH_SHORT', text)
        self.assertIn('• Strength: BUILDING → necesita STRONG', text)
        self.assertIn('• ML RSI 4H: NEUTRAL → necesita SUPPORTING', text)
        watch = text.split('👀 QUÉ TIENE QUE PASAR\n')[1].splitlines()
        self.assertEqual(watch, ['• Strength debe pasar a STRONG', '• Esperar confirmación ML RSI 4H: SUPPORTING'])
        self.assertNotIn('Timing', text)
        self.assertNotIn('Evidence', text)

    def test_pullback_grade_b_and_opposition_explanations(self):
        text = render.render(dict(ready_snapshot(), timing_state='pullback', evidence_grade='B'))
        self.assertIn('WATCH_LONG', text)
        self.assertIn('Evidence debe ser A', text)
        self.assertIn('Esperar impulso 1H alineado', text)
        opposed = render.render(dict(ready_snapshot(), mlrsi_confirmation='OPPOSING'))
        self.assertIn('⏳ WAIT', opposed)
        self.assertIn('Resolver oposición ML RSI 4H', opposed)

    def test_existing_panel_order_and_unmodified_footer(self):
        text = render.render(ready_snapshot())
        sections = ['Direction: UP', 'Strength: STRONG', '1D ', '4H ', '1H ', 'AO:', 'ADX/DI', 'Konkorde',
                    'BBWP', 'ML RSI confirmed', 'Support:', 'Resistance:', 'OPERATIVA BITMAN:', 'Confluencia:', render.FOOTER]
        offsets = [text.index(section) for section in sections]
        self.assertEqual(offsets, sorted(offsets))
        self.assertTrue(text.endswith(render.FOOTER))
        waiting = render.render(current_example())
        self.assertLess(waiting.index('👀 QUÉ TIENE QUE PASAR'), waiting.index(render.FOOTER))

    def test_safety_footer_every_status_and_unavailable(self):
        samples = [ready_snapshot(), ready_snapshot('DOWN'), current_example(), {},
                   dict(ready_snapshot(), strength='BUILDING'), dict(ready_snapshot('DOWN'), evidence_grade='B')]
        for snapshot in samples:
            text = render.render(snapshot)
            for token in ('INCONCLUSIVE DIRECTION ENGINE', 'EXACT BITMAN KONKORDE PARITY: NOT PROVEN',
                          'SHADOW ONLY', 'MANUAL ONLY', 'NO AUTO ALERTS', 'NOT AN ORDER', 'TRADE AUTHORITY: NONE'):
                self.assertIn(token, text)
            self.assertLess(len(text.encode('utf-16-le')) // 2, 3900)
        self.assertEqual(render.render(None), render.unavailable())
        self.assertTrue(render.unavailable().startswith('⚪ BITMAN: DATA TEMPORARILY UNAVAILABLE\n\n'
                        '🎯 OPERATIVA BITMAN: NO OPERAR\n⏳ WAIT\n\n'))

    def test_all_900_panels_use_manual_semantics_and_preserve_footer_and_limit(self):
        for values in itertools.product(*readiness.VALUES.values()):
            snapshot = dict(ready_snapshot(), **dict(zip(readiness.VALUES, values)))
            result = readiness.evaluate(snapshot)
            text = render.render(snapshot)
            self.assertNotEqual(text, render.unavailable())
            expected = ('SETUP READY — CANDIDATO ' + result['side']) if result['gates_ready'] else 'NO OPERAR'
            self.assertIn('🎯 OPERATIVA BITMAN: ' + expected, text)
            self.assertNotIn('¿OPERAR AHORA?', text)
            self.assertNotIn('SÍ', text)
            self.assertTrue(text.endswith(render.FOOTER))
            self.assertLess(len(text.encode('utf-16-le')) // 2, 3900)
        self.assertNotIn('¿OPERAR AHORA?', render.unavailable())

    def test_secret_or_huge_gate_payload_not_echoed(self):
        snapshot = dict(ready_snapshot(), evidence_grade='secret-canary' * 10000)
        text = render.render(snapshot)
        self.assertIn('⏳ WAIT', text)
        self.assertNotIn('secret-canary', text)
        self.assertLess(len(text.encode('utf-16-le')) // 2, 3900)

    def test_operability_helper_handles_missing_snapshot(self):
        text = '\n'.join(render.operability_lines(None))
        self.assertIn('OPERATIVA BITMAN: NO OPERAR\n⏳ WAIT', text)

    def test_gate_evaluation_and_render_make_no_io_and_do_not_mutate(self):
        for snapshot in (ready_snapshot(), ready_snapshot('DOWN'), current_example()):
            before = copy.deepcopy(snapshot)
            with patch('builtins.open', side_effect=AssertionError('NO FILE ACCESS')), \
                 patch.object(socket, 'socket', side_effect=AssertionError('NO NETWORK')), \
                 patch.object(subprocess, 'Popen', side_effect=AssertionError('NO SUBPROCESS')):
                readiness.evaluate(snapshot)
                text = render.render(snapshot)
            self.assertEqual(snapshot, before)
            self.assertNotEqual(text, render.unavailable())
            for forbidden in ('BUY', 'SELL', 'Stop loss:', 'Target:', 'Entry price:'):
                self.assertNotIn(forbidden, text)


class SafetyTests(unittest.TestCase):
    def protected(self, paths):
        baseline = json.loads((ROOT / 'tests/fixtures/bitman_readiness_base.json').read_text('utf-8'))
        self.assertEqual(baseline['base'], BASE)
        for name in paths:
            with self.subTest(path=name):
                data = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')
                self.assertEqual(hashlib.sha256(data).hexdigest(), baseline['sha256'][name])

    def test_entire_frozen_engine_unchanged_from_production(self):
        baseline = json.loads((ROOT / 'tests/fixtures/bitman_readiness_base.json').read_text('utf-8'))
        names = {p for p in baseline['sha256'] if p.startswith('bitman_manual/frozen/')}
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'bitman_manual/frozen').iterdir() if p.is_file()}
        self.assertEqual(actual, names)
        self.protected(names)

    def test_v8_runtime_and_existing_tests_unchanged(self):
        self.protected(['trend_v8.py', 'test_trend_v8.py'])

    def test_guardian_risk_execution_commands_sender_and_copilot_unchanged(self):
        self.protected(['trade_guardian.py', 'guardian_risk.py', 'guardian_bitunix.py', 'guardian_store.py',
            'guardian_telegram.py', 'guardian_signals.py', 'guardian_commands.py', 'live_auto.py',
            'main.py', 'railway.json', 'copilot_audit.py'])

    def test_mlrsi_math_confirmation_recovery_alerts_and_audit_unchanged(self):
        self.protected(['mlrsi_math.py', 'mlrsi_observer.py', 'mlrsi_public.py', 'mlrsi_guardian_host.py',
                        'mlrsi_telegram.py', 'mlrsi_safety_audit.py'])

    def test_existing_child_protocol_acquisition_and_readonly_ml_adapter_unchanged(self):
        self.protected(['bitman_manual/worker.py', 'bitman_manual/host.py', 'bitman_manual/public.py',
            'bitman_manual/transport.py', 'bitman_manual/confirmed.py', 'bitman_manual/safety.py',
            'bitman_market_data_service.py'])

    def test_readiness_has_no_imports_and_no_io_execution_or_account_calls(self):
        tree = ast.parse(Path(readiness.__file__).read_text('utf-8'))
        self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)))
        allowed_names = {'isinstance', 'type', 'dict', 'failed'}
        allowed_attributes = {'items', 'get', 'append', 'values'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertIn(node.func.id, allowed_names)
                else:
                    self.assertIsInstance(node.func, ast.Attribute)
                    self.assertIn(node.func.attr, allowed_attributes)


if __name__ == '__main__':
    unittest.main()
