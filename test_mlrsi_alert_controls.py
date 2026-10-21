"""Offline notification routing; synthetic fixtures never contact production."""
import ast
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

# Reuse the dependency guard and controlled event fixtures from the existing suite.
from test_mlrsi_observer import candle, values
from mlrsi_math import TIMEFRAMES, ResearchEvents
from mlrsi_observer import MLRSIObserver, ObserverConfig

PRODUCTION_BASE = '55c1c988df1dbfea80ed02fd13965f34f1727f14'


class AlertControlTests(unittest.TestCase):
    now = TIMEFRAMES['4h'] * 4000

    @contextmanager
    def observer(self, config):
        with tempfile.TemporaryDirectory() as folder:
            sent, logs = [], []
            observer = MLRSIObserver(folder, send=sent.append, config=config,
                                     logger=logs.append, clock=lambda: self.now / 1000)
            for tf in TIMEFRAMES:
                observer.frames[tf].update(last_closed_timestamp=self.now, confirmed_color='NEUTRAL',
                    fresh=True, last_successful_read=self.now,
                    latest_confirmed_values=dict(values(), source_low=100, close=102))
                observer.series[tf].history.extend([40, 50, 60] * 1000)
                observer.events[tf].step(self.now, values())
            observer.primed = set(TIMEFRAMES)
            observer.startup_sent = True
            observer._publish(self.now)
            yield observer, sent, logs

    def test_notification_flags_are_independent_of_calculation_and_each_other(self):
        for provisional in (False, True):
            for approaching in (False, True):
                with self.subTest(provisional=provisional, approaching=approaching):
                    config = ObserverConfig.from_env({
                        'MLRSI_PROVISIONAL_ALERTS': str(provisional),
                        'MLRSI_APPROACHING_ALERTS': str(approaching)})
                    self.assertEqual(config.provisional_alerts, provisional)
                    self.assertEqual(config.approaching_alerts, approaching)
                    self.assertTrue(config.enabled)
                    self.assertTrue(config.telegram_alerts)
                    self.assertTrue(config.approaching_enabled)

    def test_defaults_and_existing_positional_configuration_are_preserved(self):
        self.assertEqual(ObserverConfig.from_env({}), ObserverConfig())
        self.assertTrue(ObserverConfig().approaching_alerts)
        old_positional = ObserverConfig(True, True, True, 1.0, 1.5, False)
        self.assertFalse(old_positional.provisional_alerts)
        self.assertTrue(old_positional.approaching_alerts)

    def test_invalid_notification_flag_uses_existing_static_fallback(self):
        logs = []
        config = ObserverConfig.from_env({'MLRSI_APPROACHING_ALERTS': 'private invalid value'}, logs.append)
        self.assertTrue(config.approaching_alerts)
        self.assertEqual(logs, ['MLRSI_CONFIG_INVALID_DEFAULT_USED'])

    def open_observation(self, config, tf, kind, color):
        rsi = (59.1 if color == 'GREEN' else 40.9) if kind == 'APPROACHING' else (61 if color == 'GREEN' else 39)
        provisional_color = 'NEUTRAL' if kind == 'APPROACHING' else color
        rows = [candle(self.now - TIMEFRAMES[tf]), candle(self.now, 99)]
        with self.observer(config) as (observer, sent, logs):
            with patch.object(observer.series[tf], 'provisional', return_value=values(provisional_color, rsi)) as calculate:
                observer.observe({tf: rows}, self.now)
                self.assertEqual(calculate.call_count, 1)
                journal = observer.journal_path.read_bytes()
                state = observer.state_path.read_bytes()
                # Repeated polling and subsequently enabling Telegram cannot replay the hidden event.
                observer.observe({tf: rows}, self.now)
                observer.config = replace(config, provisional_alerts=True, approaching_alerts=True)
                observer.observe({tf: rows}, self.now)
                self.assertEqual(observer.journal_path.read_bytes(), journal)
                self.assertEqual(observer.state_path.read_bytes(), state)
            self.assertFalse(logs)
            return dict(sent=sent[:], journal=journal, state=state,
                        frames=observer.snapshot()['timeframes'], status=observer.status_text(),
                        keys=observer.journal_keys.copy())

    def assert_open_gate_preserves_telemetry(self, kind, flag):
        hidden_config = ObserverConfig(provisional_alerts=False, approaching_alerts=False)
        for tf in TIMEFRAMES:
            for color in ('GREEN', 'RED'):
                with self.subTest(timeframe=tf, color=color):
                    hidden = self.open_observation(hidden_config, tf, kind, color)
                    visible = self.open_observation(replace(hidden_config, **{flag: True}), tf, kind, color)
                    self.assertFalse(hidden['sent'])
                    self.assertEqual(len(visible['sent']), 1)
                    self.assertIn(kind + '_' + color, visible['sent'][0])
                    for key in ('journal', 'state', 'frames', 'status', 'keys'):
                        self.assertEqual(hidden[key], visible[key], key)
                    records = [json.loads(line) for line in hidden['journal'].splitlines()]
                    self.assertEqual([r['event'] for r in records], [kind + '_' + color])
                    self.assertFalse(records[0]['candle_complete'])
                    self.assertEqual(len(hidden['keys']), 1)
                    frame = hidden['frames'][tf]
                    self.assertEqual(frame['confirmed_color'], 'NEUTRAL')
                    self.assertTrue(frame[kind.lower() + '_' + color.lower() + '_latched'])
                    if kind == 'APPROACHING':
                        self.assertEqual(frame['approaching_state'], kind + '_' + color)
                        self.assertIn(kind + '_' + color, hidden['status'])
                    else:
                        self.assertEqual(frame['latest_provisional_values']['color'], color)
                        self.assertIn('Provisional:', hidden['status'])

    def test_approaching_off_retains_identical_journal_state_status_and_dedupe(self):
        self.assert_open_gate_preserves_telemetry('APPROACHING', 'approaching_alerts')

    def test_provisional_off_retains_identical_journal_state_status_and_dedupe(self):
        self.assert_open_gate_preserves_telemetry('PROVISIONAL', 'provisional_alerts')

    def test_confirmed_color_change_and_cross_still_send_one_message_per_transition(self):
        config = ObserverConfig(provisional_alerts=False, approaching_alerts=False)
        for tf, interval in TIMEFRAMES.items():
            for color, rsi in (('GREEN', 61), ('RED', 39)):
                with self.subTest(timeframe=tf, color=color), self.observer(config) as (observer, sent, logs):
                    with patch.object(observer.series[tf], 'push', return_value=values(color, rsi)):
                        observer.observe({tf: [candle(self.now)]}, self.now + interval)
                    records = [json.loads(line) for line in observer.journal_path.read_text('utf-8').splitlines()]
                    self.assertEqual([r['event'] for r in records], ['COLOR_CHANGE', color + '_CROSS'])
                    self.assertEqual(records[0]['candle_timestamp_utc'], records[1]['candle_timestamp_utc'])
                    self.assertEqual(len(sent), 1)
                    self.assertEqual(sent[0].count('Event: ' + color + '_CROSS'), 1)
                    self.assertNotIn('Event: COLOR_CHANGE', sent[0])
                    observer.observe({tf: [candle(self.now)]}, self.now + interval)
                    self.assertEqual(len(sent), 1)
                    self.assertEqual(len(observer.journal_path.read_text('utf-8').splitlines()), 2)
                    self.assertFalse(logs)

    def test_resume_remains_visible_with_both_open_event_alerts_off(self):
        config = ObserverConfig(provisional_alerts=False, approaching_alerts=False)
        for color, before, after in (('GREEN', 60, 61), ('RED', 40, 39)):
            with self.subTest(color=color), self.observer(config) as (observer, sent, logs):
                tf, interval = '15m', TIMEFRAMES['15m']
                observer.frames[tf]['confirmed_color'] = color
                observer.events[tf] = ResearchEvents(interval)
                observer.events[tf].step(self.now, values(color, before))
                observer.events[tf].armed = True
                with patch.object(observer.series[tf], 'push', return_value=values(color, after)):
                    observer.observe({tf: [candle(self.now)]}, self.now + interval)
                self.assertEqual(len(sent), 1)
                self.assertIn(color + '_RESUME', sent[0])
                self.assertFalse(logs)

    def test_confirmed_message_excludes_hidden_open_events_in_same_cycle(self):
        config = ObserverConfig(provisional_alerts=False, approaching_alerts=False)
        interval = TIMEFRAMES['15m']
        with self.observer(config) as (observer, sent, logs):
            with patch.object(observer.series['15m'], 'push', return_value=values('GREEN', 61)), \
                 patch.object(observer.series['15m'], 'provisional', return_value=values('RED', 39)), \
                 patch.object(observer.series['1h'], 'provisional', return_value=values('NEUTRAL', 59.1)):
                observer.observe({'15m': [candle(self.now), candle(self.now + interval)],
                                  '1h': [candle(self.now - TIMEFRAMES['1h']), candle(self.now)]}, self.now + interval)
            events = [json.loads(line)['event'] for line in observer.journal_path.read_text('utf-8').splitlines()]
            self.assertEqual(events, ['COLOR_CHANGE', 'GREEN_CROSS', 'PROVISIONAL_RED', 'APPROACHING_GREEN'])
            self.assertEqual(len(sent), 1)
            self.assertIn('Event: GREEN_CROSS', sent[0])
            self.assertNotIn('PROVISIONAL_RED', sent[0])
            self.assertNotIn('APPROACHING_GREEN', sent[0])
            self.assertFalse(logs)

    def test_global_telegram_switch_still_mutes_confirmed_without_losing_journal(self):
        with self.observer(ObserverConfig(telegram_alerts=False)) as (observer, sent, logs):
            with patch.object(observer.series['15m'], 'push', return_value=values('GREEN', 61)):
                observer.observe({'15m': [candle(self.now)]}, self.now + TIMEFRAMES['15m'])
            self.assertFalse(sent)
            self.assertEqual(len(observer.journal_path.read_text('utf-8').splitlines()), 2)
            self.assertFalse(logs)

    def test_entire_production_observer_ast_changes_only_at_notification_control(self):
        original = ast.parse(subprocess.check_output(['git', 'show', PRODUCTION_BASE + ':mlrsi_observer.py']).decode('utf-8'))
        current = ast.parse(Path('mlrsi_observer.py').read_text('utf-8'))
        dump = lambda node: ast.dump(node, include_attributes=False)
        config = next(n for n in current.body if isinstance(n, ast.ClassDef) and n.name == 'ObserverConfig')
        added = ast.parse('approaching_alerts: bool = True').body[0]
        self.assertEqual(dump(config.body[-2]), dump(added))
        config.body.pop(-2)  # appended field, immediately before from_env
        from_env = config.body[-1]
        call = from_env.body[-1].value
        self.assertEqual(dump(call.args[-1]), dump(ast.parse("flag('MLRSI_APPROACHING_ALERTS')", mode='eval').body))
        call.args.pop()
        def gate(tree):
            return next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'permitted' for t in n.targets))
        permitted = gate(current)
        allowed = ast.parse("""permitted = [] if first_ready else [r for r in alerts
            if (not r['event'].startswith('PROVISIONAL_') or self.config.provisional_alerts)
            and (not r['event'].startswith('APPROACHING_') or self.config.approaching_alerts)]""").body[0]
        self.assertEqual(dump(permitted), dump(allowed))
        permitted.value = gate(original).value
        self.assertEqual(dump(current), dump(original))


if __name__ == '__main__':
    unittest.main()
