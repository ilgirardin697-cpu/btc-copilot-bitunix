"""Offline presentation/notification tests; capital protection uses the existing fake."""
import copy
import unittest
from unittest.mock import patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('UX dependencies are installed by the Guardian workflow') from None
import test_trade_guardian as harness
from guardian_commands import COMMANDS, HELP, TelegramCommands, render_command
from guardian_signals import confirmed_market_levels, confirmed_structure, snapshot
from guardian_telegram import render_copilot, render_risk, direction_label
from guardian_risk import Config, SafetyError
from guardian_bitunix import POST_ALLOWLIST, PLACE_SL, FLASH_CLOSE, POSITIONS
from trade_guardian import Guardian


class LevelTests(unittest.TestCase):
    @staticmethod
    def candles():
        h, q = harness.GuardianTests.entry_candles()
        h[:, 0] = np.arange(-15, 5) * 3600000
        q[-1, 1:5] = [105, 109, 101, 105]
        return h, q, int(q[-1, 0] + 900000)

    def levels(self):
        h, q, now = self.candles()
        return confirmed_market_levels(h, q, 90000, now_ms=now)

    def test_support_strictly_below_closed_reference(self):
        result = self.levels()
        self.assertEqual(result['support'], 96)
        self.assertLess(result['support'], result['reference_price'])

    def test_resistance_strictly_above_closed_reference(self):
        result = self.levels()
        self.assertEqual(result['resistance'], 110)
        self.assertGreater(result['resistance'], result['reference_price'])

    def test_distances_percent(self):
        result = self.levels()
        self.assertAlmostEqual(result['support_distance_pct'], 9 / 105)
        self.assertAlmostEqual(result['resistance_distance_pct'], 5 / 105)

    def test_atr_distances(self):
        result = self.levels()
        self.assertEqual(result['atr_1h'], 4)
        self.assertEqual(result['support_distance_atr'], 2.25)
        self.assertEqual(result['resistance_distance_atr'], 1.25)

    def test_previous_confirmed_levels(self):
        result = self.levels()
        self.assertEqual(result['previous_support'], 94)
        self.assertEqual(result['previous_resistance'], 120)
        self.assertLessEqual(result['support_confirmed_time'], result['reference_time'])

    def test_open_candles_excluded_from_levels_and_atr(self):
        h, q, now = self.candles()
        expected = confirmed_market_levels(h, q, 105, now_ms=now)
        q = np.vstack([q, [now, 150, 1000, 1, 150, 10, 6]])
        h = np.vstack([h, [5 * 3600000, 150, 1000, 1, 150, 10, 6]])
        self.assertEqual(expected, confirmed_market_levels(h, q, 105, now_ms=now))

    def test_prefix_invariant_future_does_not_define_levels(self):
        h, q, _ = self.candles()
        for count in range(5, len(q) + 1):
            now = int(q[count - 1, 0] + 900000)
            self.assertEqual(confirmed_market_levels(h, q[:count], 105, now_ms=now),
                             confirmed_market_levels(h, q, 105, now_ms=now))

    def test_pivot_waits_for_two_closed_confirmation_bars(self):
        h, q, now = self.candles()
        q[-1, 1:5] = [150, 200, 145, 150]
        later = np.vstack([q, [now, 145, 160, 140, 145, 10, 6],
                                [now + 900000, 145, 170, 140, 145, 10, 6]])
        before = confirmed_market_levels(h, later, 145, now_ms=now + 900000)
        after = confirmed_market_levels(h, later, 145, now_ms=now + 1800000)
        self.assertIsNone(before['resistance'])
        self.assertEqual(after['resistance'], 200)
        self.assertEqual(after['resistance_pivot_time'], now - 900000)
        self.assertEqual(after['resistance_confirmed_time'], now + 1800000)

    def test_live_mark_does_not_redefine_closed_levels(self):
        h, q, now = self.candles()
        self.assertEqual(confirmed_market_levels(h, q, 1, now_ms=now),
                         confirmed_market_levels(h, q, 1000000, now_ms=now))

    def test_insufficient_pivots_unavailable(self):
        h, q, now = self.candles()
        result = confirmed_market_levels(h, q[:4], 105, now_ms=now)
        self.assertEqual(result['status'], 'INSUFFICIENT_CONFIRMED_PIVOTS')
        self.assertIsNone(result['support'])
        self.assertIsNone(result['resistance'])

    def test_missing_atr_keeps_real_levels(self):
        h, q, now = self.candles()
        result = confirmed_market_levels(h[:2], q, 105, now_ms=now)
        self.assertEqual(result['support'], 96)
        self.assertIsNone(result['atr_1h'])
        self.assertIsNone(result['support_distance_atr'])

    def test_malformed_market_data_fails_safe(self):
        h, q, now = self.candles()
        q[2, 4] = float('nan')
        result = confirmed_market_levels(h, q, 105, now_ms=now)
        self.assertEqual(result['status'], 'INVALID_CLOSED_DATA')
        self.assertIsNone(result['support'])

    def test_snapshot_publishes_levels_while_wait_without_entry_permission(self):
        # All source bars are closed at the same cutoff; force neutral diagnostic
        # momentum to exercise WAIT without changing the production rules.
        now = 4000 * 14400000
        def rows(interval, count):
            a = np.array([[now - (count - i) * interval, 105, 109, 101, 105, 10, 5]
                          for i in range(count)], float)
            a[:-1, 4] = 104
            return a
        h, f, q = rows(3600000, 220), rows(14400000, 220), rows(900000, 220)
        _, fixture, _ = self.candles()
        q[-len(fixture):, 1:] = fixture[:, 1:]
        ml = dict(state=0, green_event=False, red_event=False, rsi=50,
                  long_threshold=60, short_threshold=40, window_count=200)
        with patch('guardian_signals.latest_mlrsi', return_value=ml):
            result = snapshot(h, f, q, now)
        self.assertEqual(result['bias'], 'WAIT')
        self.assertEqual(result['entry_quality'], 'CAUTION')
        self.assertIsNone(result['entry_level'])
        self.assertEqual(result['market_levels']['support'], 96)
        self.assertEqual(result['market_levels']['resistance'], 110)


class GuardianUXTests(unittest.TestCase):
    def setUp(self):
        self.fixture = harness.GuardianNotificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.guardian, self.fake = self.fixture.guardian, self.fixture.fake
        self.store, self.telegram = self.fixture.store, self.fixture.telegram
        self.now = 1000000000.
        self.guardian.clock = lambda: self.now
        self.cycle()
        self.telegram.messages.clear()

    def cycle(self):
        with patch('builtins.print'):
            return self.guardian.cycle()

    def view(self, bias='WAIT'):
        view = self.guardian.command_snapshot.read()
        view['data'].update(bias=bias, momentum='NEUTRAL', taker_buy=.463,
                            structure='MIXED', entry_quality='CAUTION')
        view['data']['market_levels'] = LevelTests().levels()
        view['human_snapshot'] = render_copilot(view['data'], Config())
        return view

    def command(self, command, view=None):
        return render_command(command, view or self.view(), self.now)

    def notice_count(self):
        return sum(row['key'].startswith('tpsl:') for row in self.store.read('alerts'))

    def tp_only(self):
        self.fake.orders = [dict(id='777', symbol='BTCUSDT', positionId='123', tpPrice='11000')]

    def fail_private(self):
        def failed(_):
            raise SafetyError('POSITION_UNVERIFIED')
        self.fake.before_position = failed
        return self.cycle()

    def test_levels_work_while_wait(self):
        text = self.command('/levels')
        for value in ('R1: 110.00', 'S1: 96.00',
                      'SIN DIRECCIÓN CONFIRMADA', 'Cierre 15m por encima de 110.00',
                      'Cierre 15m por debajo de 96.00', 'NO son una señal de entrada'):
            self.assertIn(value, text)
        self.assertNotIn('Reclaim relevante', text)

    def test_levels_display_signed_distances_and_closed_reference(self):
        text = self.command('/levels')
        for value in ('Referencia 15m cerrada: 105.00', '+4.76%', '-8.57%', '1.25 ATR1H', '2.25 ATR1H'):
            self.assertIn(value, text)

    def test_levels_insufficient_explicit(self):
        view = self.view()
        view['data']['market_levels'] = {}
        text = self.command('/levels', view)
        self.assertIn('Sin niveles confirmados suficientes', text)
        self.assertNotIn('R1: 110.00', text)

    def test_status_has_compact_levels(self):
        self.assertIn('🏗 NIVELES\n⚡ 15m\n🔴 R1: 110.00\n🟢 S1: 96.00', self.command('/status'))

    def test_status_omits_unavailable_levels(self):
        view = self.view()
        view['data'].pop('market_levels')
        self.assertNotIn('🏗 NIVELES', self.command('/status', view))

    def test_no_user_facing_bias_any_command_or_direction(self):
        for bias in ('LONG_ALLOWED', 'SHORT_ALLOWED', 'WAIT', 'UNKNOWN'):
            view = self.view(bias)
            for command in COMMANDS:
                self.assertNotIn('bias', self.command(command, view).lower())
            self.assertNotIn('bias', view['human_snapshot'].lower())

    def test_direction_wording_exact(self):
        for bias, text in (('LONG_ALLOWED', '🟢 LONG CONFIRMADO'),
                           ('SHORT_ALLOWED', '🔴 SHORT CONFIRMADO'),
                           ('WAIT', '🟡 SIN DIRECCIÓN CONFIRMADA'),
                           ('UNKNOWN', '⚫ DATOS INSUFICIENTES')):
            self.assertEqual(direction_label(bias), text)
            self.assertIn(text, self.command('/status', self.view(bias)))

    def test_why_wait_explains_each_missing_confirmation(self):
        text = self.command('/why')
        for value in ('4H 🟢 BULL', '1H 🟢 BULL', '⚪ NEUTRAL', 'falta impulso LONG',
                      '46.3%', '→ neutral', '⚪ MIXTA', 'falta estructura 15m alcista/bajista',
                      'ML RSI vuelva a GREEN', 'Flujo taker comprador ≥55%',
                      'Estructura 15m confirme alcista', 'al menos 2 de 3'):
            self.assertIn(value, text)

    def test_position_clear_relationship_and_positive_pnl(self):
        view = self.view()
        view['position']['pnl'] = 2
        text = self.command('/position', view)
        self.assertIn('PnL: +2.00', text)
        self.assertIn('Dirección del mercado todavía sin confirmar', text)
        self.assertIn('💼 TU POSICIÓN', text)
        self.assertIn('DIRECCIÓN DEL COPILOT', text)

    def test_opposite_position_warning_has_no_close_recommendation(self):
        text = self.command('/position', self.view('SHORT_ALLOWED'))
        self.assertIn('Posición contraria a la dirección confirmada', text)
        self.assertIn('NO AÑADIR', text)
        self.assertNotIn('considerar reducir/cerrar', text.lower())
        self.assertIn('Cierre automático por dirección: NO', text)
        self.assertEqual(self.fake.posts, [])

    def test_duplicate_tpsl_warning_renders_once(self):
        view = self.view()
        code = 'EXISTING_TP_OR_UNKNOWN_UNTOUCHED'
        view['sl_status'] = [code, code]
        text = self.command('/risk', view)
        self.assertEqual(text.count('TP/SL sin stop protector verificado; no se reemplaza'), 1)

    def test_shadow_risk_theoretical_stop_and_disarmed(self):
        text = self.command('/risk')
        for value in ('RIESGO DE TU POSICIÓN', 'STOP PROTECTOR', 'Objetivo catastrófico teórico',
                      'GUARDIAN: SHADOW', 'Protección automática DESARMADA',
                      'Guardian NO colocará este stop automáticamente.'):
            self.assertIn(value, text)

    def test_identical_warning_not_repeated_every_five_minutes(self):
        self.tp_only()
        self.cycle()
        initial = self.notice_count()
        for _ in range(11):
            self.now += 300
            self.cycle()
        self.assertEqual(self.notice_count(), initial)

    def test_risk_and_countertrend_cooldowns_do_not_repeat_identical_tpsl_warning(self):
        self.tp_only()
        self.fake.positions[0]['liqPrice'] = '9800'
        self.guardian.bias = harness.GuardianTests.human_bias('SHORT_ALLOWED')
        self.fixture.market.bias = lambda: harness.GuardianTests.human_bias('SHORT_ALLOWED')
        self.cycle()
        warning = '⚠️ TP/SL sin stop protector verificado; no se reemplaza'
        initial = sum(text.count(warning) for text in self.telegram.messages)
        self.assertEqual(initial, 1)
        for _ in range(3):
            self.now += 300
            self.cycle()
        self.assertEqual(sum(text.count(warning) for text in self.telegram.messages), initial)

    def test_tpsl_state_change_alerts_immediately(self):
        self.tp_only()
        self.cycle()
        self.fake.orders[0]['tpPrice'] = '11100'
        self.cycle()
        self.assertEqual(self.notice_count(), 2)

    def test_position_change_alerts_immediately(self):
        self.tp_only()
        self.cycle()
        self.fake.positions[0]['positionId'] = '456'
        self.fake.orders[0]['positionId'] = '456'
        self.cycle()
        self.assertEqual(self.notice_count(), 2)

    def test_warning_clears_then_returns(self):
        self.tp_only()
        original = copy.deepcopy(self.fake.orders)
        self.cycle()
        self.fake.orders = [dict(id='777', symbol='BTCUSDT', positionId='123',
                                 slPrice='9800', slStopType='MARK_PRICE')]
        self.cycle()
        self.fake.orders = original
        self.cycle()
        self.assertEqual(self.notice_count(), 2)

    def test_risk_escalation_alerts_immediately(self):
        self.tp_only()
        self.cycle()
        for liquidation in (9700, 9800, 9900):
            self.fake.positions[0]['liqPrice'] = str(liquidation)
            self.cycle()
        self.assertEqual(self.notice_count(), 4)
        self.assertEqual(self.fake.posts, [])

    def test_sixty_minute_reminder_boundary(self):
        self.tp_only()
        self.cycle()
        self.now += 3599
        self.cycle()
        self.assertEqual(self.notice_count(), 1)
        self.now += 1
        self.cycle()
        self.assertEqual(self.notice_count(), 2)

    def test_target_noise_suppressed_material_change_alerts(self):
        self.tp_only()
        self.cycle()
        self.fixture.market.atr = 101
        self.cycle()
        self.assertEqual(self.notice_count(), 1)
        self.fixture.market.atr = 200
        self.cycle()
        self.assertEqual(self.notice_count(), 2)

    def test_tpsl_dedupe_survives_restart(self):
        self.tp_only()
        self.cycle()
        self.guardian = Guardian(self.fixture.client, self.store, self.fixture.market, self.telegram,
                                 clock=lambda: self.now)
        self.guardian.bias = self.fixture.market.bias()
        self.cycle()
        self.assertEqual(self.notice_count(), 1)

    def test_first_failed_fresh_private_verification_blocks_armed_emergency(self):
        self.guardian.config = self.fixture.client.config = harness.ARMED
        self.fake.positions[0]['liqPrice'] = '9900'
        heartbeat = self.fail_private()
        self.assertEqual(heartbeat['risk'], 'UNKNOWN')
        self.assertIsNone(self.guardian.command_snapshot.read())
        self.assertEqual(self.fake.posts, [])
        self.assertFalse(self.store.read('actions'))

    def test_first_failure_yellow_not_emergency(self):
        self.fail_private()
        self.assertTrue(any('🟡 DATOS TEMPORALMENTE NO VERIFICABLES' in text for text in self.telegram.messages))
        self.assertFalse(any('GUARDIAN SIN DATOS FIABLES' in text for text in self.telegram.messages))

    def test_second_consecutive_failure_orange(self):
        self.fail_private()
        self.telegram.messages.clear()
        self.cycle()
        self.assertTrue(any('🟠 DATOS DEGRADADOS' in text for text in self.telegram.messages))

    def test_third_consecutive_failure_red_even_inside_cooldown(self):
        self.fail_private()
        self.cycle()
        self.telegram.messages.clear()
        self.cycle()
        self.assertTrue(any('🚨 GUARDIAN SIN DATOS FIABLES' in text and 'NO MUTATION' in text
                            for text in self.telegram.messages))
        self.assertEqual(self.fake.posts, [])

    def test_recovery_once_and_failure_counter_reset(self):
        self.fail_private()
        self.cycle()
        self.cycle()
        self.fake.before_position = None
        self.cycle()
        self.cycle()
        self.assertEqual(sum('✅ CONEXIÓN RECUPERADA' in text for text in self.telegram.messages), 1)
        self.assertEqual(self.guardian._failures, 0)
        self.telegram.messages.clear()
        self.fail_private()
        self.assertTrue(any('🟡 DATOS TEMPORALMENTE NO VERIFICABLES' in text for text in self.telegram.messages))

    def test_readonly_commands_owner_only_and_arbitrary_zero_bitunix_calls(self):
        replies = []
        commands = TelegramCommands('fake-token', 'owner', self.guardian.command_snapshot,
                                    lambda text: replies.append(text) or True, enabled=True, clock=lambda: self.now)
        original = copy.deepcopy(self.store.state)
        with patch.object(self.fixture.client, '_request', side_effect=AssertionError('BITUNIX FORBIDDEN')) as http:
            for text in list(COMMANDS) + ['/arm', '/protect', '/close'] + ['/' + str(i) for i in range(200)]:
                self.assertFalse(commands.process({'message': {'chat': {'id': 'alert'}, 'text': text}}))
                self.assertTrue(commands.process({'message': {'chat': {'id': 'owner'}, 'text': text}}))
        http.assert_not_called()
        self.assertEqual(self.store.state, original)
        self.assertEqual(self.fake.posts, [])
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})
        self.assertFalse(self.guardian.config.armed('SL'))
        self.assertFalse(self.guardian.config.armed('CLOSE'))

    def test_shadow_zero_posts_in_all_risk_states(self):
        self.fake.orders = []
        for liquidation in (9500, 9700, 9800, 9900):
            self.fake.positions[0]['liqPrice'] = str(liquidation)
            self.cycle()
        self.assertEqual(self.fake.posts, [])

    def test_only_emergency_can_flash_close_despite_counter_direction(self):
        self.guardian.config = self.fixture.client.config = harness.ARMED
        self.guardian.bias = harness.GuardianTests.human_bias('SHORT_ALLOWED')
        self.fixture.market.bias = lambda: harness.GuardianTests.human_bias('SHORT_ALLOWED')
        for liquidation in (9500, 9700, 9800):
            self.fake.positions[0]['liqPrice'] = str(liquidation)
            self.cycle()
            self.assertEqual(self.fake.posts, [])
        self.fake.positions[0]['liqPrice'] = '9900'
        self.cycle()
        self.assertEqual([call[1] for call in self.fake.posts], [FLASH_CLOSE])

    def test_help_plain_spanish_and_readonly(self):
        self.assertIn('🔒 Estos comandos son solo consulta.', HELP)
        self.assertIn('Nunca abren ni cierran operaciones.', HELP)
        self.assertIn('soportes, resistencias y niveles a vigilar', HELP)


if __name__ == '__main__':
    unittest.main()
