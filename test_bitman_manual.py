"""Offline manual command contract, causal frozen reuse and execution isolation.

All prices/states are synthetic fixtures, never forward observations or backtests.
"""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Runtime dependencies are installed by the Guardian/Bitman workflows') from None

from bitman_manual import confirmed, host, public, render, worker
from bitman_manual.frozen import core, levels
from bitman_manual.frozen.constants import HOUR, MLRSI_CONFIG, VERSION
from bitman_manual.safety import PRODUCTION_BASE, fingerprint, strip_commands, verify_command_extension
from guardian_commands import HELP, SnapshotCache, TelegramCommands

ROOT = Path(__file__).resolve().parent
NOW = 1792173900000  # 2026-10-16 18:05 UTC, synthetic fixture clock


def components(d='UP', h='UP', q='UP'):
    def part(b):
        up = b == 'UP'
        return dict(bias=b, ao_bias=b,
            momentum='BULLISH_MOMENTUM' if up else 'BEARISH_MOMENTUM' if b == 'DOWN' else 'MIXED',
            di_direction='BULLISH' if up else 'BEARISH' if b == 'DOWN' else 'NEUTRAL',
            ao=120. if up else -120., adx=24., adx_slope=1., bbwp=64., bbwp_slope=1., adx_turn_up=True,
            di_plus=30. if up else 10., di_minus=10. if up else 30., mountain=48., ma=42.,
            konkorde='KONKORDE_BULLISH_INSIDE')
    return {'1D': part(d), '4H': part(h), '1H': part(q)}


def snapshot(d='UP', h='UP', q='UP'):
    parts = components(d, h, q)
    structure = dict(opposing_up=False, opposing_down=False, nearest_support=80400., nearest_resistance=83200.)
    return dict(version=VERSION, symbol='BTCUSDT', venue='BINANCE_USDM_PERPETUAL', timestamp=NOW // HOUR * HOUR,
        components=parts, structure=structure, **core.decide(parts, structure),
        shadow_only=True, trade_authority=False, not_trade_signal=True,
        display_mlrsi={'15m': {'color': 'RED'}, '1H': {'color': 'RED'}, '4H': {'color': 'NEUTRAL'}})


def ml_export(color='GREEN'):
    def frame(interval):
        return dict(observation=dict(last_closed_timestamp=NOW // interval * interval, last_successful_read=NOW,
            fresh=True, confirmed_color=color, latest_confirmed_values=dict(color=color, valid=True,
                mlrsi_smoothed=60., upper_threshold=55., lower_threshold=45.),
            latest_provisional_values=dict(color='RED'), approaching_state='APPROACHING_RED'))
    return dict(config_version=MLRSI_CONFIG, symbol='BTCUSDT', venue='BINANCE_SPOT', shadow_only=True,
        trade_authority=False, timeframes={'15m': frame(HOUR // 4), '1h': frame(HOUR), '4h': frame(4 * HOUR)})


def prices(n=7205):
    t = NOW // (24 * HOUR) * (24 * HOUR) - 300 * 24 * HOUR + np.arange(n) * HOUR
    c = 80000. + np.arange(n) * .1 + np.sin(np.arange(n) / 19) * 600
    o = np.r_[c[0], c[:-1]]
    return np.column_stack([t, o, np.maximum(o, c) + 100, np.minimum(o, c) - 100, c,
        np.full(n, 100.), np.full(n, 50.)])


class RenderAndHierarchyTests(unittest.TestCase):
    def test_all_five_states_render_without_new_rules(self):
        cases = [('UP', 'UP', 'UP', 'UP'), ('DOWN', 'DOWN', 'DOWN', 'DOWN'),
                 ('UP', 'DOWN', 'DOWN', 'TRANSITION'), ('UP', 'DOWN', 'UP', 'CONFLICT'),
                 ('UNKNOWN', 'UP', 'UP', 'UNCLEAR')]
        for d, h, q, expected in cases:
            with self.subTest(expected=expected):
                s = snapshot(d, h, q)
                self.assertEqual(s['state'], expected)
                text = render.render(s)
                self.assertIn('Direction: ' + expected, text)
                self.assertIn('MACRO BIAS', text)
                self.assertIn('SWING BIAS', text)
                self.assertIn('IMPULSE / TIMING', text)

    def test_pullback_does_not_reverse_macro(self):
        s = snapshot('UP', 'UP', 'DOWN')
        self.assertEqual(s['state'], 'UP')
        self.assertIn('1H 🔴 DOWN — IMPULSE / TIMING (PULLBACK)', render.render(s))

    def test_strength_and_adx_are_not_direction(self):
        p = components()
        self.assertEqual(core.decide(p)['strength'], 'STRONG')
        p['1D']['bbwp_slope'] = -1.
        self.assertEqual(core.decide(p)['strength'], 'BUILDING')
        for f in p.values():
            f.update(adx=90., adx_slope=-10., adx_turn_up=False, bbwp_slope=-1.)
        self.assertEqual(core.decide(p)['state'], 'UP')
        self.assertEqual(core.decide(p)['strength'], 'WEAK')

    def test_existing_major_level_and_confirmed_4h_opposition(self):
        self.assertEqual(core.decide(components(), {'opposing_up': True})['state'], 'CONFLICT')
        self.assertEqual(core.decide(components(), ml={'4H': {'color': 'RED'}})['state'], 'CONFLICT')
        self.assertEqual(core.decide(components(), ml={'15m': {'color': 'RED'}, '1H': {'color': 'RED'}})['state'], 'UP')

    def test_real_colors_and_unknown_are_explicit(self):
        text = render.render(snapshot())
        for part in ('15m 🔴 RED', '1H 🔴 RED', '4H ⚪ NEUTRAL', 'Support: 80,400.00',
                     'Resistance: 83,200.00', 'ADX strength; DI direction', 'PROXY'):
            self.assertIn(part, text)
        s = snapshot()
        s.update(components={}, structure={}, display_mlrsi={})
        text = render.render(s)
        for part in ('Support: UNKNOWN', 'Resistance: UNKNOWN', '15m ⚪ UNKNOWN', '4H UNKNOWN'):
            self.assertIn(part, text)

    def test_safe_unavailable_no_payload_echo(self):
        for s in (None, {}, {'state': 'BUY', 'strength': 'STRONG'}, {'state': 'UP', 'strength': '99%'}):
            self.assertEqual(render.render(s), render.unavailable())
        s = snapshot()
        s['components']['4H'].update(konkorde='secret', adx=float('nan'), mountain=None)
        s['display_mlrsi']['1H']['color'] = 'secret'
        self.assertNotIn('secret', render.render(s))

    def test_mandatory_context_and_telegram_length(self):
        for text in (render.render(snapshot()), render.unavailable()):
            for phrase in ('INCONCLUSIVE DIRECTION ENGINE', 'EXACT BITMAN KONKORDE PARITY: NOT PROVEN',
                           'MANUAL ONLY', 'SHADOW ONLY', 'NO AUTO ALERTS', 'NOT AN ORDER',
                           'TRADE AUTHORITY: NONE', 'NO AUTO TRADE'):
                self.assertIn(phrase, text)
            self.assertLess(len(text.encode('utf-16-le')) // 2, 3900)
            for forbidden in ('BUY', 'SELL', 'probability', 'evidence_grade', 'Grade:'):
                self.assertNotIn(forbidden, text)


class ConfirmedStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'igod_mlrsi_state.json'

    def write(self, value):
        self.path.write_text(json.dumps(value), encoding='utf-8')

    def test_current_confirmed_only_and_original_not_changed(self):
        self.write(ml_export())
        before = self.path.read_bytes()
        engine, display = confirmed.read_current(self.path, NOW)
        self.assertEqual(engine['4H']['color'], 'GREEN')
        self.assertEqual(engine['1H']['color'], 'GREEN')
        self.assertEqual(display['15m']['color'], 'GREEN')
        self.assertEqual(engine['1D']['color'], 'UNKNOWN')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn('provisional', json.dumps(engine).lower())
        self.assertNotIn('approaching', json.dumps(display).lower())

    def test_missing_corrupt_stale_wrong_version_are_unknown(self):
        self.assertEqual(confirmed.read_current(self.path, NOW)[0]['4H']['color'], 'UNKNOWN')
        self.path.write_text('not json secret', encoding='utf-8')
        self.assertEqual(confirmed.read_current(self.path, NOW)[1]['15m']['color'], 'UNKNOWN')
        for field, value in (('config_version', 'OTHER'), ('symbol', 'ETHUSDT'), ('trade_authority', True),
                             ('venue', 'OTHER'), ('shadow_only', False)):
            state = ml_export()
            state[field] = value
            self.write(state)
            self.assertTrue(all(f['color'] == 'UNKNOWN' for f in confirmed.read_current(self.path, NOW)[1].values()))
        for variant in ('stale', 'future', 'invalid', 'mismatch', 'open'):
            state = ml_export()
            for tf, frame in state['timeframes'].items():
                p = frame['observation']
                if variant == 'stale': p['last_successful_read'] = NOW - 90001
                if variant == 'future': p['last_successful_read'] = NOW + 1
                if variant == 'invalid': p['latest_confirmed_values']['valid'] = False
                if variant == 'mismatch': p['latest_confirmed_values']['color'] = 'RED'
                if variant == 'open': p['last_closed_timestamp'] += {'15m': HOUR // 4, '1h': HOUR, '4h': 4 * HOUR}[tf]
            self.write(state)
            self.assertTrue(all(f['color'] == 'UNKNOWN' for f in confirmed.read_current(self.path, NOW)[1].values()), variant)

    def test_provisional_and_approaching_never_change_engine(self):
        state = ml_export()
        self.write(state)
        one = worker.calculate(dict(mlrsi_state_path=str(self.path), public_cache=snapshot()), NOW)
        for frame in state['timeframes'].values():
            frame['observation'].update(latest_provisional_values={'color': 'GREEN'}, approaching_state='APPROACHING_GREEN')
        self.write(state)
        two = worker.calculate(dict(mlrsi_state_path=str(self.path), public_cache=snapshot()), NOW)
        self.assertEqual(one, two)
        self.assertEqual(one['snapshot']['state'], 'UP')

    def test_cached_public_context_rereads_current_host(self):
        request = dict(mlrsi_state_path=str(self.path), public_cache=snapshot())
        self.write(ml_export('GREEN'))
        self.assertEqual(worker.calculate(request, NOW)['snapshot']['state'], 'UP')
        self.write(ml_export('RED'))
        result = worker.calculate(request, NOW)
        self.assertEqual(result['snapshot']['state'], 'CONFLICT')
        self.assertEqual(result['snapshot']['display_mlrsi']['15m']['color'], 'RED')
        self.assertEqual(request['public_cache']['state'], 'UP')

    def test_no_usable_ml_state_does_not_invent_confirmation(self):
        result = worker.calculate(dict(mlrsi_state_path=str(self.path), public_cache=snapshot()), NOW)
        self.assertEqual(result['snapshot']['state'], 'UP')
        self.assertEqual(result['snapshot']['mlrsi_confirmation'], 'UNAVAILABLE')

    def test_state_path_is_existing_host_resolution(self):
        with patch('mlrsi_guardian_host.storage_directory', return_value=Path('/volume/mlrsi')):
            self.assertEqual(host.state_path(), Path('/volume/mlrsi/igod_mlrsi_state.json'))


class FakePublic:
    def __init__(self, mutate=None, status=200):
        self.calls, self.mutate, self.status = [], mutate, status
        self.trust_env = True

    def get(self, url, *, params, timeout, allow_redirects):
        self.calls.append((url, params, timeout, allow_redirects))
        rows = [[t, '80000', '80100', '79900', '80001', '100', t + HOUR - 1, '8000000', 40, '50', '4000000', '0']
                for t in range(params['startTime'], params['endTime'] + 1, HOUR)]
        if self.mutate:
            rows = self.mutate(rows)
        return Mock(status_code=self.status, json=Mock(return_value=rows))


class PublicAndWorkerTests(unittest.TestCase):
    def test_public_get_only_closed_hourly_complete_schema(self):
        client = FakePublic()
        with patch.object(public, 'HISTORY_DAYS', 3), patch.object(public, 'PAGE_SIZE', 20):
            bars = public.fetch_closed(NOW, client)
        self.assertFalse(client.trust_env)
        self.assertLessEqual(bars[-1, 0] + HOUR, NOW)
        self.assertEqual(bars[-1, 0] + HOUR, NOW // HOUR * HOUR)
        self.assertTrue(np.all(bars[:, 6] == 50))  # base volume index 9, not quote volume index 10
        for url, params, timeout, redirect in client.calls:
            self.assertEqual(url, public.URL)
            self.assertEqual(set(params), {'symbol', 'interval', 'startTime', 'endTime', 'limit'})
            self.assertEqual((params['symbol'], params['interval']), ('BTCUSDT', '1h'))
            self.assertEqual(timeout, (3, 5))
            self.assertFalse(redirect)

    def test_gaps_duplicates_open_revision_bad_values_fail_closed(self):
        def modify(index, value):
            def mutate(rows):
                rows[0][index] = value
                return rows
            return mutate
        cases = [lambda rows: rows[1:], lambda rows: rows + [rows[-1]], lambda rows: {},
                 modify(0, NOW), modify(6, NOW), modify(4, 'nan'), modify(9, '101'), modify(3, '-1')]
        with patch.object(public, 'HISTORY_DAYS', 1):
            for mutate in cases:
                with self.subTest(mutate=mutate), self.assertRaises((ValueError, TypeError)):
                    public.fetch_closed(NOW, FakePublic(mutate))
            for status in (429, 451, 500, 302):
                with self.assertRaisesRegex(ValueError, 'PUBLIC_MARKET_UNAVAILABLE'):
                    public.fetch_closed(NOW, FakePublic(status=status))

    def test_frozen_preparation_ignores_open_candle_and_future_pivots(self):
        bars = prices(7230)
        one = core.prepare(bars, NOW)
        changed = bars.copy()
        changed[changed[:, 0] + HOUR > NOW, 1:5] *= 3
        two = core.prepare(changed, NOW)
        self.assertEqual(core.snapshot(one, -1), core.snapshot(two, -1))
        for tf, data in one['frames'].items():
            self.assertTrue(np.all(data['closes'] <= NOW), tf)
        scale = levels.scale(bars[:300], HOUR)
        for kind in ('support', 'resistance'):
            valid = np.isfinite(scale[kind + '_known'])
            self.assertTrue(np.all(scale[kind + '_known'][valid] == scale[kind + '_pivot'][valid] + 3 * HOUR))
            self.assertTrue(np.all(scale[kind + '_known'][valid] <= bars[:300, 0][valid] + HOUR))

    def test_full_manual_calculation_with_synthetic_public_data(self):
        bars = prices(7218)
        with patch.object(worker, 'fetch_closed', return_value=bars), patch.object(worker, 'read_current', return_value=({}, {})):
            result = worker.calculate(dict(mlrsi_state_path='unused', public_cache=None), NOW)
        self.assertTrue(result['ok'])
        self.assertEqual(result['snapshot']['timestamp'], NOW // HOUR * HOUR)
        self.assertIs(result['snapshot']['trade_authority'], False)
        json.dumps(result, allow_nan=False)

    def test_stale_hour_cache_rejected_not_used_as_current(self):
        s = snapshot()
        s['timestamp'] -= HOUR
        with self.assertRaisesRegex(ValueError, 'PUBLIC_CONTEXT_NOT_CURRENT'):
            worker.calculate(dict(mlrsi_state_path='unused', public_cache=s), NOW)

    def test_worker_safe_failure_never_echoes_error_or_secret(self):
        with patch('sys.stdin', io.StringIO('{"secret":"never echo"}')), patch('sys.stdout', new_callable=io.StringIO) as out:
            worker.main()
        self.assertEqual(out.getvalue(), '{"ok":false}\n')
        request = json.dumps(dict(mlrsi_state_path='unused', public_cache=None))
        with patch('sys.stdin', io.StringIO(request)), patch('sys.stdout', new_callable=io.StringIO) as out, \
             patch.object(worker, 'fetch_closed', side_effect=requests.Timeout('private-token response')):
            worker.main()
        self.assertEqual(out.getvalue(), '{"ok":false}\n')

    def test_real_child_protocol_invalid_request_no_network(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        result = subprocess.run([sys.executable, '-m', 'bitman_manual.worker'], input='{}', capture_output=True,
            text=True, encoding='utf-8', timeout=10, cwd=ROOT, env=env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {'ok': False})
        self.assertEqual(result.stderr, '')


class HostTests(unittest.TestCase):
    def setUp(self):
        self.host = host.BitmanHost(resolve_state=lambda: Path('/test/mlrsi/igod_mlrsi_state.json'), wall=lambda: NOW / 1000)
        self.addCleanup(self.host.stop)
        self.reply = Mock(return_value=True)
        self.process = Mock(returncode=0)
        self.process.poll.return_value = 0
        self.result = dict(ok=True, snapshot=snapshot(), public_cache=snapshot())
        self.process.communicate.return_value = (json.dumps(self.result), '')

    def test_nothing_automatic_at_construction(self):
        with patch.object(host.subprocess, 'Popen') as popen, patch.object(host.threading, 'Thread') as thread:
            host.BitmanHost()
        popen.assert_not_called()
        thread.assert_not_called()

    def test_one_reply_and_credential_free_child(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'sensitive', 'BITUNIX_API_KEY': 'sensitive', 'HTTP_PROXY': 'sensitive'}), \
             patch.object(host.subprocess, 'Popen', return_value=self.process) as popen:
            self.host._run(self.reply)
        self.reply.assert_called_once_with(render.render(snapshot()))
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [sys.executable, '-m', 'bitman_manual.worker'])
        self.assertTrue(set(kwargs['env']) <= {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PYTHONIOENCODING', 'PYTHONDONTWRITEBYTECODE'})
        self.assertNotIn('sensitive', json.dumps(kwargs['env']))
        request = json.loads(self.process.communicate.call_args.args[0])
        self.assertEqual(set(request), {'mlrsi_state_path', 'public_cache', 'market_data_url'})
        self.assertEqual(request['market_data_url'], public.URL)
        self.assertIsNone(request['public_cache'])
        self.assertEqual(self.process.communicate.call_args.kwargs['timeout'], 25)

    def test_timeout_kills_child_and_answers_once(self):
        self.process.poll.return_value = None
        self.process.communicate.side_effect = [subprocess.TimeoutExpired('worker', 25), ('', '')]
        with patch.object(host.subprocess, 'Popen', return_value=self.process):
            self.host._run(self.reply)
        self.process.kill.assert_called_once()
        self.reply.assert_called_once_with(render.unavailable())
        self.assertFalse(self.host._busy)

    def test_failure_and_malformed_child_are_contained(self):
        for output in ('not json secret', '{"ok":false}', '{"ok":true}', json.dumps(dict(self.result, snapshot={'trade_authority': True}))):
            self.reply.reset_mock()
            self.process.communicate.return_value = (output, '')
            with patch.object(host.subprocess, 'Popen', return_value=self.process):
                self.host._run(self.reply)
            self.reply.assert_called_once_with(render.unavailable())
        with patch.object(host.subprocess, 'Popen', side_effect=OSError('private secret')):
            self.host._run(Mock(side_effect=RuntimeError('sender unavailable')))

    def test_public_cache_ttl_and_hour_boundary(self):
        self.host._clock = lambda: 100
        with patch.object(host.subprocess, 'Popen', return_value=self.process):
            self.host._run(self.reply)
            self.host._clock = lambda: 129
            self.host._run(self.reply)
            self.assertIsNotNone(json.loads(self.process.communicate.call_args.args[0])['public_cache'])
            self.host._clock = lambda: 160
            self.host._run(self.reply)
            self.assertIsNone(json.loads(self.process.communicate.call_args.args[0])['public_cache'])
            self.host._wall = lambda: (NOW // HOUR * HOUR + HOUR) / 1000
            self.host._run(self.reply)
            self.assertIsNone(json.loads(self.process.communicate.call_args.args[0])['public_cache'])

    def test_stop_kills_and_suppresses_reply(self):
        self.host._process = self.process
        self.process.poll.return_value = None
        self.host.stop()
        self.process.kill.assert_called_once()
        self.assertFalse(self.host.request(self.reply))
        with patch.object(host.subprocess, 'Popen') as popen:
            self.host._run(self.reply)
        self.reply.assert_not_called()
        popen.assert_not_called()

    def test_busy_does_not_spawn_another_process(self):
        self.host._busy = True
        with patch.object(host.threading, 'Thread') as thread:
            self.assertTrue(self.host.request(self.reply))
        thread.assert_not_called()
        self.reply.assert_called_once_with(render.unavailable())


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.reply = Mock(return_value=True)
        self.cache = SnapshotCache()
        self.commands = TelegramCommands('private-token', '12345', self.cache, self.reply, enabled=True, transport=Mock())
        self.addCleanup(self.commands.stop)

    def update(self, text='/bitman', owner='12345'):
        return dict(message=dict(chat=dict(id=owner), text=text))

    def test_command_and_bot_suffix_use_existing_sender_callback(self):
        with patch.object(host, 'BitmanHost') as factory:
            factory.return_value.request.return_value = True
            for command in ('/bitman', '/bitman@existing_bot'):
                self.assertTrue(self.commands.process(self.update(command)))
            factory.assert_called_once_with()
            self.assertEqual(factory.return_value.request.call_count, 2)
            factory.return_value.request.assert_called_with(self.reply)

    def test_help_has_command_without_second_help(self):
        self.assertTrue(self.commands.process(self.update('/help')))
        self.reply.assert_called_with(HELP)
        self.assertIn('/bitman\n', HELP)
        self.assertNotIn('/bitman_help', HELP)

    def test_owner_and_enable_policy_before_host_creation(self):
        with patch.object(host, 'BitmanHost') as factory:
            for owner in ('other', '', None, ' 12345 '):
                self.assertFalse(self.commands.process(self.update(owner=owner)))
            for field, value in (('enabled', False), ('_token', ''), ('_owner', '')):
                previous = getattr(self.commands, field)
                setattr(self.commands, field, value)
                self.assertFalse(self.commands.process(self.update()))
                setattr(self.commands, field, previous)
        factory.assert_not_called()
        self.reply.assert_not_called()

    def test_slow_engine_does_not_block_poller_or_help(self):
        started, release, replied = threading.Event(), threading.Event(), threading.Event()
        child = Mock(returncode=0)
        child.poll.return_value = 0
        def communicate(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise TimeoutError
            return json.dumps(dict(ok=True, snapshot=snapshot(), public_cache=snapshot())), ''
        child.communicate.side_effect = communicate
        self.commands._bitman = host.BitmanHost(resolve_state=lambda: Path('unused'))
        self.reply.side_effect = lambda text: replied.set() or True
        with patch.object(host.subprocess, 'Popen', return_value=child):
            try:
                before = time.monotonic()
                self.assertTrue(self.commands.process(self.update()))
                self.assertLess(time.monotonic() - before, .5)
                self.assertTrue(started.wait(2))
                self.assertTrue(self.commands.process(self.update('/help')))
                self.reply.assert_called_once_with(HELP)
                replied.clear()
                release.set()
                self.assertTrue(replied.wait(2))
                self.assertEqual(self.reply.call_count, 2)
                self.assertIn('BITMAN', self.reply.call_args.args[0])
            finally:
                release.set()

    def test_engine_initialization_failure_preserves_command_loop(self):
        with patch.object(host, 'BitmanHost', side_effect=RuntimeError('secret')):
            self.assertTrue(self.commands.process(self.update()))
        self.reply.assert_called_with(render.unavailable())
        self.assertTrue(self.commands.process(self.update('/help')))
        self.reply.assert_called_with(HELP)

    def test_real_calculation_route_has_no_guardian_or_order_effects(self):
        import test_trade_guardian as harness
        fixture = harness.GuardianNotificationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with patch('builtins.print'):
            fixture.guardian.cycle()
        original = copy.deepcopy(fixture.store.state)
        cache = fixture.guardian.command_snapshot.read()
        environment = dict(os.environ)
        child = Mock(returncode=0)
        child.poll.return_value = 0
        replied = threading.Event()
        child.communicate.side_effect = lambda payload, **kwargs: (json.dumps(worker.calculate(json.loads(payload), NOW)), '')
        self.commands._bitman = host.BitmanHost(resolve_state=lambda: Path('missing-synthetic-state'))
        self.reply.side_effect = lambda text: replied.set() or True
        with patch.object(fixture.client, '_request', side_effect=AssertionError('NO BITUNIX')) as no_orders, \
             patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK')) as no_network, \
             patch.object(worker, 'fetch_closed', return_value=prices(7218)), \
             patch.object(host.subprocess, 'Popen', return_value=child):
            self.assertTrue(self.commands.process(self.update()))
            self.assertTrue(replied.wait(5))
        no_orders.assert_not_called()
        no_network.assert_not_called()
        self.assertIn('BITMAN — BTC DIRECTION', self.reply.call_args.args[0])
        self.assertEqual(fixture.store.state, original)
        self.assertEqual(fixture.guardian.command_snapshot.read(), cache)
        self.assertEqual(dict(os.environ), environment)
        self.assertEqual(fixture.fake.posts, [])


class ProvenanceAndSafetyTests(unittest.TestCase):
    def test_frozen_sources_match_research_exactly(self):
        folder = ROOT / 'bitman_manual/frozen'
        manifest = json.loads((folder / 'provenance.json').read_text('utf-8'))
        for name, record in manifest.items():
            with self.subTest(name=name):
                original = subprocess.check_output(['git', 'show', record['source_commit'] + ':' + record['source_path']])
                current = (folder / name).read_bytes().replace(b'\r\n', b'\n')
                self.assertEqual(hashlib.sha256(original).hexdigest(), record['original_sha256'])
                self.assertEqual(hashlib.sha256(current).hexdigest(), record['vendored_sha256'])
                source = original.decode('utf-8')
                for before, after in record['import_rewrites']:
                    source = source.replace(before, after)
                if record['selected_symbols'] is None:
                    self.assertEqual(current.decode('utf-8'), source)
                else:
                    old = ast.parse(source)
                    new = ast.parse(current)
                    def symbol(node):
                        return node.name if isinstance(node, ast.FunctionDef) else node.targets[0].id if isinstance(node, ast.Assign) else None
                    for symbol_name in record['selected_symbols']:
                        self.assertEqual(fingerprint(next(n for n in old.body if symbol(n) == symbol_name)),
                                         fingerprint(next(n for n in new.body if symbol(n) == symbol_name)))

    def test_existing_commands_ast_is_exact_and_mutations_not_hidden(self):
        self.assertTrue(verify_command_extension())
        source = (ROOT / 'guardian_commands.py').read_text('utf-8')
        original = ast.parse(subprocess.check_output(['git', 'show', PRODUCTION_BASE + ':guardian_commands.py']).decode('utf-8'))
        for old, new in (("!= self._owner", "== self._owner"), ('return False  # never log', 'return True  # never log'),
                         ('return copy.deepcopy(self._value)', 'return self._value'),
                         ("command == '/position'", "command == '/position_changed'")):
            self.assertIn(old, source)
            mutated = strip_commands(ast.parse(source.replace(old, new)))
            self.assertNotEqual(fingerprint(mutated), fingerprint(original))

    def test_only_exact_passive_bitman_fragments_can_be_normalized(self):
        source = (ROOT / 'guardian_commands.py').read_text('utf-8')
        for old, new in (('self._bitman.request(self._reply)', 'self._bitman.execute(self._reply)'),
                         ('self._bitman = None', 'self._bitman = dangerous_client()')):
            with self.subTest(old=old), self.assertRaises(AssertionError):
                strip_commands(ast.parse(source.replace(old, new)))

    def test_production_protections_math_alerts_sender_and_copilot_unchanged(self):
        paths = ('trade_guardian.py', 'guardian_bitunix.py', 'guardian_risk.py', 'guardian_telegram.py',
                 'guardian_signals.py', 'mlrsi_math.py', 'mlrsi_observer.py', 'mlrsi_public.py',
                 'mlrsi_guardian_host.py', 'mlrsi_telegram.py', 'live_auto.py', 'main.py', 'railway.json')
        for path in paths:
            original = subprocess.check_output(['git', 'show', PRODUCTION_BASE + ':' + path])
            self.assertEqual((ROOT / path).read_bytes().replace(b'\r\n', b'\n'), original.replace(b'\r\n', b'\n'), path)

    def test_no_order_capability_or_new_telegram_client(self):
        forbidden_modules = {'guardian_bitunix', 'trade_guardian', 'live_auto', 'main', 'v8_executor',
                             'v8_bitunix', 'guardian_telegram', 'research'}
        forbidden_attributes = {'post', 'put', 'delete', 'patch', 'place_order', 'place_market', 'flash_close_position',
                                'change_leverage', 'cancel_order', 'execute', 'preflight', 'reconcile', 'latest_mlrsi'}
        for path in (ROOT / 'bitman_manual').rglob('*.py'):
            if path.name == 'safety.py':
                continue
            source = path.read_text('utf-8')
            self.assertNotIn('api.telegram.org', source)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, forbidden_attributes, str(path))
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[0], forbidden_modules, str(path))
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.assertNotIn(name.name.split('.')[0], forbidden_modules, str(path))


if __name__ == '__main__':
    unittest.main()
