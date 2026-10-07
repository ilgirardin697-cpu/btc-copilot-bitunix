"""Reproduce the deployed cache poison; public-only recovery, no network tests."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Dedicated ML RSI CI explicitly installs dependencies') from None
from mlrsi_public import PublicHistory, CLOSED_GRACE_MS, public_error_code, atomic_json
from mlrsi_math import CausalSeries, CAPTURED_CONFIG, CONFIG_VERSION, TIMEFRAMES
from mlrsi_observer import MLRSIObserver
import test_mlrsi_observer as fixtures
from test_mlrsi_observer import candle, values

DEPLOYED = 'f6612014be20aca52fd35b872bc504e8f0727eb1'


def response(rows=None, status=200):
    r = Mock(status_code=status)
    r.json.return_value = [[p[k] for k in ('time', 'open', 'high', 'low', 'close')] for p in (rows or [])]
    return r


class ProviderRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.interval = TIMEFRAMES['15m']
        self.t = 800 * self.interval
        self.rows = [candle(i * self.interval) for i in range(768, 801)]
        self.http, self.logs = Mock(), []
        self.p = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
        small = patch('mlrsi_public.WARMUP_BARS', 32)
        small.start()
        self.addCleanup(small.stop)

    def bootstrap(self, now=None, rows=None):
        self.http.get.return_value = response(rows or self.rows)
        return self.p.fetch('15m', self.t + 1 if now is None else now)

    def finalize(self, low=98, age=1000):
        self.http.get.return_value = response([candle(self.t, low)])
        return self.p.fetch('15m', self.t + self.interval + age)

    def test_deployed_open_closed_revised_poison_repeats_and_survives_restart(self):
        module = types.ModuleType('deployed_mlrsi_public')
        source = subprocess.check_output(['git', 'show', DEPLOYED + ':mlrsi_public.py']).decode('utf-8')
        exec(compile(source, 'deployed_mlrsi_public.py', 'exec'), module.__dict__)
        module.WARMUP_BARS = 32
        old = module.PublicHistory(self.tmp.name, transport=self.http)
        self.http.get.return_value = response(self.rows)  # open stored
        old.fetch('15m', self.t + self.interval - 1)
        self.http.get.return_value = response([candle(self.t, 98)])  # first closed, no new open yet
        old.fetch('15m', self.t + self.interval + 1000)
        frozen = copy.deepcopy(old.cache)
        self.http.get.return_value = response([candle(self.t, 97)])
        for attempt in range(12):
            with self.assertRaisesRegex(ValueError, '^MLRSI_CLOSED_CANDLE_REVISED$'):
                old.fetch('15m', self.t + self.interval + 40000 + attempt * 30000)
            self.assertEqual(old.cache, frozen)
        restart = module.PublicHistory(self.tmp.name, transport=self.http)
        with self.assertRaisesRegex(ValueError, '^MLRSI_CLOSED_CANDLE_REVISED$'):
            restart.fetch('15m', self.t + self.interval + 600000)

    def test_open_close_first_version_later_finalization_does_not_poison(self):
        self.bootstrap(self.t + self.interval - 1)
        self.finalize()
        first_generation = self.p.generation('15m')
        result = self.finalize(97, 40000)
        self.assertEqual(result[-1]['low'], 97)
        self.assertEqual(self.p.generation('15m'), first_generation + 1)
        self.assertIn('MLRSI_RECENT_CANDLE_FINALIZED 15m', self.logs)
        self.finalize(97, 70000)
        self.assertEqual(self.p.generation('15m'), first_generation + 1)

    def test_shared_closed_boundary_recovers_all_three_timeframes(self):
        boundary = 800 * TIMEFRAMES['4h']
        for tf, interval in TIMEFRAMES.items():
            index = boundary // interval - 1
            rows = [candle(i * interval) for i in range(index - 32, index + 1)]
            self.http.get.return_value = response(rows)
            self.p.fetch(tf, boundary - 1)
            self.http.get.return_value = response([candle(index * interval, 98)])
            self.p.fetch(tf, boundary + 1000)
            self.http.get.return_value = response([candle(index * interval, 97)])
            self.assertEqual(self.p.fetch(tf, boundary + 40000)[-1]['low'], 97)
            self.assertEqual(self.p.verified_at[tf], boundary + 40000)

    def test_grace_edge_inclusive_and_outside_resets(self):
        self.bootstrap(self.t + self.interval - 1)
        self.finalize()
        self.finalize(97, CLOSED_GRACE_MS)
        with self.assertRaisesRegex(ValueError, 'MLRSI_CLOSED_CANDLE_REVISED'):
            self.finalize(96, CLOSED_GRACE_MS + 1)
        self.assertEqual(self.p.cache['15m'], [])
        tombstone = json.loads(self.p._path('15m').read_text('utf-8'))
        self.assertEqual(tombstone['candles'], [])
        self.assertEqual(tombstone['generation'], self.p.generation('15m'))

    def test_old_revision_next_cycle_rebootstraps_without_restart(self):
        self.bootstrap(self.t + self.interval - 1)
        self.finalize()
        with self.assertRaises(ValueError):
            self.finalize(97, CLOSED_GRACE_MS + 1)
        fresh = [candle(i * self.interval, 97 if i == 800 else 100) for i in range(769, 802)]
        self.http.get.return_value = response(fresh)
        recovered = self.p.fetch('15m', self.t + self.interval + CLOSED_GRACE_MS + 30000)
        self.assertEqual(recovered, [{k: float(v) if k != 'time' else v for k, v in p.items()} for p in fresh])
        self.assertNotIn('startTime', self.http.get.call_args.kwargs['params'])
        self.assertGreater(self.p.verified_at['15m'], self.t + self.interval)

    def test_restart_with_revised_cache_preserves_generation(self):
        self.bootstrap(self.t + self.interval - 1)
        self.finalize()
        self.finalize(97, 40000)
        restart = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
        result = restart.fetch('15m', self.t + self.interval + 70000)
        self.assertEqual(result[-1]['low'], 97)
        self.assertEqual(restart.generation('15m'), self.p.generation('15m'))

    def test_corrupt_json_and_schema_cache_rebootstrap(self):
        for data in ('{corrupt', json.dumps(dict(venue='BINANCE_SPOT', symbol='BTCUSDT', candles=[{'invalid': 1}]))):
            self.p._path('15m').write_text(data, encoding='utf-8')
            p = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
            self.http.get.return_value = response(self.rows)
            self.assertTrue(p.fetch('15m', self.t + 1))
            self.assertGreater(p.generation('15m'), 0)
        self.assertTrue(any('MLRSI_CACHE_INVALID' in line for line in self.logs))

    def test_tombstone_survives_restart(self):
        self.bootstrap()
        self.p.reset('15m')
        p = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
        self.http.get.return_value = response(self.rows)
        p.fetch('15m', self.t + 1)
        self.assertEqual(p.generation('15m'), self.p.generation('15m'))

    def test_corrupt_or_missing_cache_never_reuses_previous_epoch(self):
        self.bootstrap()
        original = self.p.epoch('15m')
        self.p._path('15m').write_text('{corrupt', encoding='utf-8')
        restart = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
        self.http.get.return_value = response(self.rows)
        restart.fetch('15m', self.t + 1)
        self.assertNotEqual(restart.epoch('15m'), original)
        old_load = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
        # Simulate missing cache without deleting any real workspace file.
        with patch.object(Path, 'read_text', side_effect=FileNotFoundError):
            old_load.fetch('15m', self.t + 1)
        self.assertNotEqual(old_load.epoch('15m'), restart.epoch('15m'))

    def test_huge_offline_gap_uses_bounded_fresh_bootstrap(self):
        self.bootstrap()
        current = 9000
        rows = [candle(i * self.interval) for i in range(current - 32, current + 1)]
        self.http.get.return_value = response(rows)
        calls = self.http.get.call_count
        self.assertEqual(self.p.fetch('15m', current * self.interval + 1)[-1]['time'], current * self.interval)
        self.assertEqual(self.http.get.call_count - calls, 1)
        self.assertNotIn('startTime', self.http.get.call_args.kwargs['params'])

    def test_missing_data_gap_does_not_merge_or_interpolate(self):
        self.bootstrap()
        self.http.get.return_value = response([candle(self.t + 2 * self.interval)])
        with self.assertRaisesRegex(ValueError, 'MLRSI_HISTORY_GAP'):
            self.p.fetch('15m', self.t + 2 * self.interval + 1)
        self.assertEqual(self.p.cache['15m'], [])

    def test_stale_reply_resets_instead_of_poisoning_cursor(self):
        self.bootstrap()
        self.http.get.return_value = response([candle(self.t)])
        with self.assertRaisesRegex(ValueError, 'MLRSI_HISTORY_STALE_OR_INSUFFICIENT'):
            self.p.fetch('15m', self.t + 2 * self.interval)
        self.assertEqual(self.p.cache['15m'], [])

    def test_tf_failure_does_not_touch_other_cache(self):
        self.bootstrap(self.t + self.interval - 1)
        self.finalize()
        self.p.cache['1h'] = [candle(0)]
        other = copy.deepcopy(self.p.cache['1h'])
        with self.assertRaises(ValueError):
            self.finalize(97, CLOSED_GRACE_MS + 1)
        self.assertEqual(self.p.cache['1h'], other)
        self.assertEqual(self.p.generation('1h'), 0)

    def test_http_status_backoff_and_recovery(self):
        for status in (429, 500, 503):
            p = PublicHistory(self.tmp.name, transport=self.http, logger=self.logs.append)
            self.http.get.return_value = response(status=status)
            with self.assertRaisesRegex(ValueError, '^HTTP_' + str(status) + '$'):
                p.fetch('15m', self.t)
            calls = self.http.get.call_count
            with self.assertRaisesRegex(ValueError, 'MLRSI_PUBLIC_BACKOFF'):
                p.fetch('15m', self.t + 1000)
            self.assertEqual(self.http.get.call_count, calls)
            self.http.get.return_value = response(self.rows)
            self.assertTrue(p.fetch('15m', self.t + 30000))

    def test_timeout_and_network_recover_without_mutating_cache(self):
        self.bootstrap()
        before = copy.deepcopy(self.p.cache)
        for error in (requests.Timeout('secret URL/body'), requests.ConnectionError('secret')):
            self.http.get.side_effect = error
            with self.assertRaises(type(error)):
                self.p.fetch('15m', self.t + 30000)
            self.assertEqual(self.p.cache, before)
        self.http.get.side_effect = None
        self.http.get.return_value = response(self.rows[-2:])
        self.assertTrue(self.p.fetch('15m', self.t + 60000))

    def test_json_schema_codes_are_static(self):
        r = response()
        r.json.side_effect = ValueError('secret response body')
        self.http.get.return_value = r
        with self.assertRaisesRegex(ValueError, '^MLRSI_JSON_INVALID$'):
            self.p.fetch('15m', self.t)
        r.json.side_effect = None
        for data in ({'body': 'secret'}, [[1]], [[0, 'secret', 100, 99, 100]]):
            r.json.return_value = data
            with self.assertRaises(ValueError) as context:
                self.p.fetch('15m', self.t)
            self.assertNotIn('secret', public_error_code(context.exception))

    def test_write_error_does_not_commit_unverified_ram(self):
        self.bootstrap()
        before, verified = copy.deepcopy(self.p.cache), dict(self.p.verified_at)
        self.http.get.return_value = response([candle(self.t, 99)])
        with patch('mlrsi_public.atomic_json', side_effect=OSError('secret path')):
            with self.assertRaisesRegex(ValueError, '^MLRSI_CACHE_WRITE_ERROR$'):
                self.p.fetch('15m', self.t + 30000)
        self.assertEqual(self.p.cache, before)
        self.assertEqual(self.p.verified_at, verified)

    def test_cache_read_error_has_static_code(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError('private path')):
            with self.assertRaisesRegex(ValueError, '^MLRSI_CACHE_READ_ERROR$'):
                self.p.fetch('15m', self.t)

    def test_error_sanitizer_never_prints_untrusted_values(self):
        for error in (RuntimeError('token chat_id raw payload'), ValueError('HTTP_429 token'),
                      ValueError('HTTP_999'), ValueError('MLRSI_FAKE_SECRET')):
            self.assertEqual(public_error_code(error), 'MLRSI_PUBLIC_ERROR')
        self.assertEqual(public_error_code(requests.Timeout('sensitive')), 'MLRSI_TIMEOUT')
        self.assertEqual(public_error_code(requests.ConnectionError('sensitive')), 'MLRSI_NETWORK_ERROR')
        self.assertEqual(public_error_code(ValueError('HTTP_429')), 'HTTP_429')

    def test_math_preset_reference_and_protection_files_unchanged(self):
        for path in ('mlrsi_math.py', 'mlrsi_pine_reference.py', 'mlrsi_telegram.py', 'trade_guardian.py',
                     'guardian_commands.py', 'guardian_risk.py', 'guardian_bitunix.py', 'live_auto.py', 'trend_v8.py'):
            old = subprocess.check_output(['git', 'show', DEPLOYED + ':' + path])
            self.assertEqual(Path(path).read_bytes().replace(b'\r\n', b'\n'), old.replace(b'\r\n', b'\n'), path)
        self.assertEqual(CONFIG_VERSION, 'CAPTURE_LOW29_EMA4_PINE_PARITY_V4')
        self.assertEqual(CAPTURED_CONFIG['rsi_length'], 29)
        self.assertFalse(self.http.post.called)


class ObserverRecoveryTests(unittest.TestCase):
    setUp = fixtures.ObserverTests.setUp
    closed_frame = fixtures.ObserverTests.closed_frame
    transition = fixtures.ObserverTests.transition
    record_events = fixtures.ObserverTests.record_events

    def test_diagnostic_includes_tf_and_safe_exception_code(self):
        self.o.provider = Mock()
        self.o.provider.fetch.side_effect = [ValueError('MLRSI_CLOSED_CANDLE_REVISED'), ValueError('HTTP_429'), requests.Timeout('secret URL')]
        self.o.cycle()
        for expected in ('15m MLRSI_CLOSED_CANDLE_REVISED', '1h HTTP_429', '4h MLRSI_TIMEOUT'):
            self.assertIn('MLRSI_PUBLIC_READ_FAILED ' + expected, self.logs)
        self.assertNotIn('secret', str(self.logs))

    def test_outage_recovery_current_cross_is_not_alerted_then_new_event_is(self):
        self.o.provider = Mock()
        self.o.provider.fetch.side_effect = requests.Timeout('secret')
        self.o.cycle()
        self.assertFalse(self.o.frames['15m']['fresh'])
        self.transition(color='GREEN', rsi=61)
        self.assertTrue(self.o.frames['15m']['fresh'])
        self.assertFalse(self.sent)
        self.assertNotIn('15m', self.o.recovering)
        self.transition(color='RED', rsi=39)
        self.assertEqual(len(self.sent), 1)
        self.assertIn('RED_CROSS', self.sent[0])

    def test_recovery_does_not_alert_open_provisional_or_approaching(self):
        for color, rsi in (('GREEN', 61), ('NEUTRAL', 59.1)):
            self.o.recovering.add('15m')
            with patch.object(self.o.series['15m'], 'provisional', return_value=values(color, rsi)):
                self.o.observe({'15m': self.closed_frame('15m', False, 99)}, self.now + 1)
            self.assertFalse(self.sent)

    def test_recovery_confluence_is_current_state_not_new_alert(self):
        for p in self.o.frames.values():
            p['confirmed_color'] = 'GREEN'
        self.o.recovering.update(TIMEFRAMES)
        rows = {tf: self.closed_frame(tf, False) for tf in TIMEFRAMES}
        self.o.observe(rows, self.now)
        self.assertTrue(self.o.previous_3of3_green)
        self.assertFalse(self.sent)
        self.o.observe(rows, self.now + 30000)
        self.assertFalse(self.sent)

    def test_long_catchup_latest_event_is_silent(self):
        rows = [candle(self.now + i * 900000) for i in range(4)]
        self.now += 4 * 900000
        with patch.object(self.o.series['15m'], 'push', side_effect=[values('GREEN', 61), values('NEUTRAL'), values('RED', 39), values('GREEN', 61)]):
            self.o.observe({'15m': rows}, self.now)
        self.assertTrue(self.o.frames['15m']['fresh'])
        self.assertTrue(self.record_events())
        self.assertFalse(self.sent)

    def test_approaching_rearm_same_candle_sends_once_both_directions(self):
        for color in ('GREEN', 'RED'):
            events = []
            for distance in (.9, 1.7, .8, 1.8, .7):
                rsi = 60 - distance if color == 'GREEN' else 40 + distance
                with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=rsi)):
                    events += self.o._open('15m', candle(self.now), True)
            self.assertEqual(sum(event[0] == 'APPROACHING_' + color for event in events), 1)

    def test_approaching_new_candle_can_alert_after_rearm(self):
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=59.1)):
            self.assertTrue(self.o._open('15m', candle(self.now), True))
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=58.3)):
            self.o._open('15m', candle(self.now + 900000), True)
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=59.1)):
            events = self.o._open('15m', candle(self.now + 900000), True)
        self.assertEqual(events, [('APPROACHING_GREEN', '15m', False)])

    def test_approaching_restart_preserves_candle_limit(self):
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=59.1)):
            self.o._open('15m', candle(self.now), True)
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=58.3)):
            self.o._open('15m', candle(self.now), True)
        self.o._persist()
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        with patch.object(r.series['15m'], 'provisional', return_value=values(rsi=59.1)):
            self.assertEqual(r._open('15m', candle(self.now), True), [])

    def test_provisional_independent_of_approaching_candle_limit(self):
        with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=59.1)):
            self.o._open('15m', candle(self.now), True)
        with patch.object(self.o.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            self.assertIn(('PROVISIONAL_GREEN', '15m', False), self.o._open('15m', candle(self.now), True))

    def test_gap_requests_provider_reset_and_does_not_advance_math(self):
        self.o.provider = Mock()
        before = copy.deepcopy(self.o.series['15m'].dump())
        self.now += 3 * 900000
        self.o.observe({'15m': [candle(self.now - 900000)]}, self.now)
        self.o.provider.reset.assert_called_once_with('15m')
        self.assertEqual(self.o.series['15m'].dump(), before)

    def test_storage_migration_keeps_current_math_carry(self):
        self.o._persist()
        old = json.loads(self.o.state_path.read_text('utf-8'))
        old.pop('provider_generations')
        old.pop('recovering_timeframes')
        for p in old['timeframes'].values():
            p['observation'].pop('approaching_green_alert_timestamp')
            p['observation'].pop('approaching_red_alert_timestamp')
        self.o.state_path.write_text(json.dumps(old), encoding='utf-8')
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertEqual(r.series['15m'].dump(), self.o.series['15m'].dump())
        self.assertNotIn('MLRSI_STATE_INVALID_REBOOTSTRAP', self.logs)

    def test_recovering_flag_is_durable(self):
        self.o.recovering.add('15m')
        self.o._persist()
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertEqual(r.recovering, {'15m'})

    def test_provider_generation_rebuilds_only_tf_silently(self):
        interval = TIMEFRAMES['15m']
        lows = 1000 + np.sin(np.arange(3233) / 9) * 30
        rows = [candle(self.now - (3232 - i) * interval, float(low)) for i, low in enumerate(lows)]
        other = copy.deepcopy(self.o.series['1h'].dump())
        self.o.observe({'15m': rows}, self.now + 1, {'15m': 1})
        self.assertTrue(self.o.frames['15m']['fresh'])
        self.assertEqual(self.o.provider_generations['15m'], 1)
        self.assertEqual(self.o.series['1h'].dump(), other)
        self.assertFalse(self.sent)
        reference = CausalSeries()
        reference.configure_bootstrap(len(rows) - 1)
        for row in rows[:-1]:
            last = reference.push(row['low'])
        self.assertEqual(self.o.frames['15m']['latest_confirmed_values']['mlrsi_smoothed'], last['mlrsi_smoothed'])
        self.assertEqual(self.o.series['15m'].dump(), reference.dump())
        self.o._persist()
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertEqual(r.provider_generations['15m'], 1)

    def test_epoch_changed_with_same_generation_still_rebuilds_silently(self):
        self.o.provider_epochs['15m'] = 'a' * 32
        interval = TIMEFRAMES['15m']
        rows = [candle(self.now - (3232 - i) * interval, 1000 + 10 * np.sin(i / 7)) for i in range(3233)]
        self.o.observe({'15m': rows}, self.now + 1, {'15m': 0}, {'15m': 'b' * 32})
        self.assertTrue(self.o.frames['15m']['fresh'])
        self.assertEqual(self.o.provider_epochs['15m'], 'b' * 32)
        self.assertEqual(self.o.series['15m'].count, 3232)
        self.assertFalse(self.sent)


if __name__ == '__main__':
    unittest.main()
