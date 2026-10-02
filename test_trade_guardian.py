"""Offline harness: transport fakes only, never real private GET or POST."""
from dataclasses import replace
from email.utils import formatdate
from pathlib import Path
import hashlib
import inspect
import json
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Guardian dependencies are installed and tested by its dedicated workflow') from None
import requests
from guardian_bitunix import (Bitunix, signature, POSITIONS, TPSL, TICKERS, PAIRS, KLINES,
                              PLACE_SL, FLASH_CLOSE, GET_ALLOWLIST, POST_ALLOWLIST)
from guardian_risk import Config, SafetyError, parse_positions, risk, catastrophic_stop, assess_orders, SIDE_ALIASES
from guardian_signals import (closed_bars, rolling_mlrsi, cluster_three, states_and_events,
                              confirmed_structure, direction, flow_state, atr14, latest_mlrsi,
                              volatility_state, snapshot, ML_RSI27_REAL, entry_quality, current_entry_quality)
from guardian_store import Store
from guardian_market import BINANCE_MARKET_DATA_BASE, Market
from guardian_telegram import Telegram, render_copilot, render_risk, protection_status
from trade_guardian import Guardian


def position(**changes):
    row = dict(positionId='123', symbol='BTCUSDT', qty='0.1', side='LONG',
               marginMode='ISOLATION', positionMode='ONE_WAY', leverage=10,
               unrealizedPNL='-2', margin='100', liqPrice='9900', marginRate='0.01',
               avgOpenPrice='10100', ctime=1000, mtime=1000)
    row.update(changes)
    return row


ARMED = Config(mode='PROTECT', allow_sl=True, allow_close=True, arm_phrase='PROTECT_CAPITAL_ONLY')


class Response:
    status_code = 200
    def __init__(self, data):
        self.data = data
        self.headers = {'Date': formatdate(time.time(), usegmt=True)}
    def json(self):
        return {'code': 0, 'data': self.data}


class FakeBitunix:
    """Full allowlisted HTTP surface, position/order changes and lost-response simulation."""
    def __init__(self):
        self.positions = [position()]
        self.orders = []
        self.positions_wrapped = False
        self.orders_wrapped = False
        self.mark = 10000
        self.calls = []
        self.fail = False
        self.ambiguous = False
        self.apply_close = True
        self.before_position = None
        self.before_post = None

    def request(self, method, url, **kwargs):
        path = url.removeprefix('https://fapi.bitunix.com')
        self.calls.append((method, path, kwargs))
        if self.fail:
            raise requests.Timeout('fake-secret MUST NEVER ESCAPE')
        if method == 'GET':
            if path == POSITIONS:
                if self.before_position:
                    self.before_position(self)
                data = {'positionList': self.positions, 'total': len(self.positions)} if self.positions_wrapped else self.positions
                return Response(data)
            if path == TPSL:
                if not isinstance(self.orders, list):
                    return Response(self.orders)
                start = kwargs['params']['skip']
                page = self.orders[start:start + kwargs['params']['limit']]
                data = {'orderList': page, 'total': len(self.orders)} if self.orders_wrapped else page
                return Response(data)
            if path == TICKERS:
                return Response([dict(symbol='BTCUSDT', markPrice=str(self.mark), lastPrice=str(self.mark))])
            if path == PAIRS:
                return Response([dict(symbol='BTCUSDT', quotePrecision=1, symbolStatus='OPEN', isApiSupported=True)])
            if path == KLINES:
                return Response([])
        if method == 'POST':
            if self.before_post:
                self.before_post(self)
            body = json.loads(kwargs['data'])
            if path == FLASH_CLOSE:
                if self.apply_close:
                    self.positions = []
                if self.ambiguous:
                    raise requests.Timeout('fake-secret')
                return Response({'positionId': body['positionId']})
            if path == PLACE_SL:
                self.orders = [dict(body, id='777', slOrderType='MARKET')]
                if self.ambiguous:
                    raise requests.Timeout('fake-secret')
                return Response({'orderId': '777'})
        raise AssertionError('Unexpected route')

    @property
    def posts(self):
        return [call for call in self.calls if call[0] == 'POST']


class FakeMarket:
    def __init__(self, atr=100, bias='LONG_ALLOWED'):
        self.atr, self.value = atr, bias
    def venue_atr(self):
        return self.atr
    def bias(self):
        return {'bias': self.value, 'why': 'offline evidence'}


class FakeTelegram:
    def __init__(self):
        self.messages = []
        self.fail = False
    def send(self, text):
        self.messages.append(text)
        if self.fail:
            raise RuntimeError('telegram unavailable')
        return True


class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.fake = FakeBitunix()
        self.client = Bitunix(ARMED, 'fake-key', 'fake-secret', self.fake)
        self.market = FakeMarket()
        self.telegram = FakeTelegram()
        self.guardian = Guardian(self.client, self.store, self.market, self.telegram)
        self.guardian.bias = {'bias': 'LONG_ALLOWED', 'why': 'offline'}
        self._network = patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('LIVE HTTP FORBIDDEN'))
        self._network.start()

    def tearDown(self):
        self._network.stop()
        self.store.close()
        self.tmp.cleanup()

    def p(self, **kwargs):
        return parse_positions([position(**kwargs)])

    def test_signed_get_canonical(self):
        self.client.position()
        _, _, options = self.fake.calls[-1]
        h = options['headers']
        text = h['nonce'] + h['timestamp'] + 'fake-key' + 'includeSubAccountsfalsesymbolBTCUSDT'
        digest = hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(h['sign'], hashlib.sha256((digest + 'fake-secret').encode()).hexdigest())
        self.assertEqual(h['language'], 'en-US')
        self.assertFalse(options['allow_redirects'])

    def test_secret_never_logged(self):
        self.fake.fail = True
        with self.assertRaises(SafetyError) as caught:
            self.client.position()
        self.assertNotIn('fake-secret', str(caught.exception))
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertNotIn('fake-secret', ''.join(p.read_text() for p in Path(self.tmp.name).glob('*.json*')))

    def test_exact_allowlist(self):
        self.assertEqual(GET_ALLOWLIST, {POSITIONS, TPSL, TICKERS, PAIRS, KLINES})
        self.assertEqual(POST_ALLOWLIST, {PLACE_SL, FLASH_CLOSE})

    def test_forbidden_posts(self):
        for name in ('place_order', 'batch_order', 'close_all_position', 'change_leverage', 'change_margin', 'transfer', 'withdraw'):
            with self.subTest(name=name), self.assertRaises(SafetyError):
                self.client._request('POST', '/api/v1/futures/trade/' + name, body={})
        self.assertEqual(self.fake.posts, [])

    def test_pending_position_parser(self):
        p = self.client.position()
        self.assertEqual((p.position_id, p.side, p.qty, p.margin_mode), ('123', 'LONG', .1, 'ISOLATION'))

    def test_direct_positions_list(self):
        self.assertEqual(self.client.position(), self.p())
        self.fake.positions = []
        self.assertIsNone(self.client.position())
        self.assertIsNotNone(self.client.last_private)

    def test_position_list_wrapper(self):
        self.fake.positions_wrapped = True
        self.assertEqual(self.client.position(), self.p())
        self.fake.positions = []
        self.assertIsNone(self.client.position())
        self.assertIsNotNone(self.client.last_private)

    def test_position_wrapper_truncated_fails_closed(self):
        self.fake.positions = {'positionList': [position()], 'total': 2}
        with self.assertRaisesRegex(SafetyError, '^POSITIONS_PAGINATION_INCOMPLETE$'):
            self.client.position()
        self.assertIsNone(self.client.last_private)
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_position_wrapper_invalid_list_or_total(self):
        invalid = [{'total': 0}, {'positionList': None, 'total': 0},
                   {'positionList': [position()]}]
        invalid += [{'positionList': [position()], 'total': value}
                    for value in (None, True, False, -1, 0, 1.0, '1', 'NaN')]
        for data in invalid:
            with self.subTest(data=data):
                self.fake.positions = data
                with self.assertRaises(SafetyError):
                    self.client.position()
                self.assertIsNone(self.client.last_private)
        self.assertFalse(self.fake.posts)

    def test_duplicate_wrapped_positions_fail_closed(self):
        self.fake.positions_wrapped = True
        self.fake.positions = [position(), position(positionId='456')]
        with self.assertRaisesRegex(SafetyError, '^AMBIGUOUS_POSITIONS$'):
            self.client.position()
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_wrapped_position_scope_validation_unchanged(self):
        self.fake.positions_wrapped = True
        cases = (({'symbol': 'ETHUSDT'}, 'POSITION_SYMBOL_INVALID'),
                 ({'subAccountId': 'malformed'}, 'POSITION_ACCOUNT_ID_INVALID'),
                 ({'side': 'UNSUPPORTED'}, 'POSITION_SIDE_INVALID'),
                 ({'marginMode': 'UNSUPPORTED'}, 'POSITION_MARGIN_MODE_INVALID'),
                 ({'positionMode': 'UNSUPPORTED'}, 'POSITION_MODE_INVALID'))
        for changes, code in cases:
            with self.subTest(changes=changes):
                self.fake.positions = [position(**changes)]
                with self.assertRaisesRegex(SafetyError, '^' + code + '$'):
                    self.client.position()
        self.assertFalse(self.fake.posts)

    def test_direct_tpsl_list(self):
        self.assertEqual(self.client.orders('123'), [])
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9950')]
        self.assertEqual(self.client.orders('123'), self.fake.orders)

    def test_order_list_wrapper(self):
        self.fake.orders_wrapped = True
        self.assertEqual(self.client.orders('123'), [])
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9950')]
        self.assertEqual(self.client.orders('123'), self.fake.orders)
        self.assertIsNotNone(self.client.last_private)

    def test_order_wrapper_truncation_fails_closed(self):
        self.fake.orders = {'orderList': [dict(positionId='123', symbol='BTCUSDT')], 'total': 2}
        with self.assertRaisesRegex(SafetyError, '^ORDERS_PAGINATION_INCOMPLETE$'):
            self.client.orders('123')
        self.assertIsNone(self.client.last_private)
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_order_wrapper_invalid_list_or_total(self):
        order = dict(positionId='123', symbol='BTCUSDT')
        invalid = [{'total': 0}, {'orderList': None, 'total': 0}, {'orderList': [order]}]
        invalid += [{'orderList': [order], 'total': value}
                    for value in (None, True, False, -1, 0, 1.0, '1', 'NaN')]
        for data in invalid:
            with self.subTest(data=data):
                self.fake.orders = data
                with self.assertRaises(SafetyError):
                    self.client.orders('123')
                self.assertIsNone(self.client.last_private)
        self.assertFalse(self.fake.posts)

    def test_tpsl_pagination_direct_and_wrapped(self):
        self.fake.orders = [dict(id=str(i), positionId='123', symbol='BTCUSDT') for i in range(101)]
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                self.fake.orders_wrapped = wrapped
                self.fake.calls.clear()
                self.assertEqual(self.client.orders('123'), self.fake.orders)
                self.assertEqual([call[2]['params']['skip'] for call in self.fake.calls], [0, 100])
        self.assertFalse(self.fake.posts)

    def test_tpsl_pagination_limit_preserved(self):
        self.fake.orders = [dict(id=str(i), positionId='123', symbol='BTCUSDT') for i in range(1001)]
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                self.fake.orders_wrapped = wrapped
                self.fake.calls.clear()
                with self.assertRaisesRegex(SafetyError, '^ORDERS_PAGINATION_INCOMPLETE$'):
                    self.client.orders('123')
                self.assertEqual(len(self.fake.calls), 10)
                self.assertIsNone(self.client.last_private)

    def test_order_wrapper_inconsistent_total_fails_closed(self):
        orders = [dict(id=str(i), positionId='123', symbol='BTCUSDT') for i in range(101)]
        responses = [Response({'orderList': orders[:100], 'total': 101}),
                     Response({'orderList': orders[100:], 'total': 102})]
        with patch.object(self.fake, 'request', side_effect=responses):
            with self.assertRaisesRegex(SafetyError, '^ORDERS_TOTAL_INVALID$'):
                self.client.orders('123')
        self.assertIsNone(self.client.last_private)

    def test_wrapped_tpsl_scope_validation_unchanged(self):
        self.fake.orders_wrapped = True
        for order in (dict(positionId='456', symbol='BTCUSDT'),
                      dict(positionId='123', symbol='ETHUSDT')):
            with self.subTest(order=order):
                self.fake.orders = [order]
                with self.assertRaisesRegex(SafetyError, '^ORDERS_SCOPE_INVALID$'):
                    self.client.orders('123')
        self.assertFalse(self.fake.posts)

    def test_market_data_url_and_public_kline_fields(self):
        raw = [[0, '100', '102', '98', '101', '10', 3599999, '1000', 20, '6', '600', '0']]
        http = Mock()
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = raw
        market = Market(self.client, transport=http, clock=lambda: 3600)
        self.assertEqual(market._binance('1h', 1), [[0, '100', '102', '98', '101', '10', '6']])
        self.assertEqual(BINANCE_MARKET_DATA_BASE, 'https://data-api.binance.vision')
        http.get.assert_called_once_with('https://data-api.binance.vision/api/v3/klines',
            params={'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 1, 'endTime': 3600000},
            timeout=(2, 3), allow_redirects=False)
        # The injected public transport has no authenticated request or POST route.
        self.assertEqual([call[0] for call in http.method_calls], ['get'])
        source = Path('guardian_market.py').read_text(encoding='utf-8')
        self.assertNotIn('api.binance.com', source)
        for private_marker in ('BINANCE_API_KEY', 'BINANCE_API_SECRET', 'X-MBX-APIKEY', '/api/v3/account', '/api/v3/order'):
            self.assertNotIn(private_marker, source)

    def test_blind_diagnostic_contains_only_static_code(self):
        self.fake.fail = True
        with patch('builtins.print') as output:
            self.guardian.cycle()
        diagnostic = [call.args[0] for call in output.call_args_list
                      if call.args and str(call.args[0]).startswith('GUARDIAN_BLIND_CODE=')]
        self.assertEqual(diagnostic, ['GUARDIAN_BLIND_CODE=TRANSPORT_OR_RESPONSE_FAILURE'])
        for call in output.call_args_list:
            self.assertNotIn('fake-secret', str(call))
            self.assertNotIn('fake-key', str(call))
            self.assertNotIn('https://fapi.bitunix.com', str(call))

    def test_exchange_payload_never_in_blind_diagnostic(self):
        response = Response(None)
        response.json = lambda: {'code': 10001, 'msg': 'fake-key fake-secret PRIVATE EXCHANGE BODY'}
        with patch.object(self.fake, 'request', return_value=response), patch('builtins.print') as output:
            self.guardian.cycle()
        output.assert_any_call('GUARDIAN_BLIND_CODE=API_REJECTED_AUTH_OR_REQUEST', flush=True)
        self.assertNotIn('fake-secret', str(output.call_args_list))
        self.assertNotIn('PRIVATE EXCHANGE BODY', str(output.call_args_list))
        self.assertFalse(self.fake.posts)

    def test_wrapped_reads_shadow_remains_non_mutating(self):
        self.fake.positions_wrapped = self.fake.orders_wrapped = True
        self.client.config = self.guardian.config = Config()
        with patch('builtins.print'):
            heartbeat = self.guardian.cycle()
        self.assertEqual(self.guardian.config.mode, 'SHADOW')
        self.assertEqual(heartbeat['armed'], {'sl': False, 'close': False})
        self.assertIsNotNone(heartbeat['last_successful_private_read'])
        self.assertFalse(self.fake.posts)

    def test_wrapped_reads_keep_mutation_capabilities_unchanged(self):
        self.fake.positions_wrapped = self.fake.orders_wrapped = True
        for action, liq in (('SL', 9500), ('CLOSE', 9900)):
            self.fake.positions = [position(liqPrice=liq)]
            self.fake.orders = []
            permit = self.client.preflight(action, self.client.position(), 100)
            self.client.execute(permit)
        self.assertEqual([call[1] for call in self.fake.posts], [PLACE_SL, FLASH_CLOSE])

    def test_long_liquidation_sanity(self):
        with self.assertRaises(SafetyError):
            risk(self.p(liqPrice=10100), 10000, 100, ARMED)

    def test_short_liquidation_sanity(self):
        with self.assertRaises(SafetyError):
            risk(self.p(side='SHORT', liqPrice=9900), 10000, 100, ARMED)

    def test_invalid_liquidation_no_emergency(self):
        for value in (0, -10, 'NaN'):
            with self.subTest(value=value), self.assertRaises(SafetyError):
                risk(self.p(liqPrice=value), 10000, 100, ARMED)

    def test_atr_risk_calculation(self):
        r = risk(self.p(liqPrice=9500), 10000, 100, ARMED)
        self.assertEqual((r['distance'], r['distance_pct'], r['distance_atr'], r['atr_pct']), (500, .05, 5, .01))

    def test_warning_threshold(self):
        self.assertEqual(risk(self.p(liqPrice=9700), 10000, 50, ARMED)['state'], 'WARNING')

    def test_danger_threshold(self):
        self.assertEqual(risk(self.p(liqPrice=9800), 10000, 50, ARMED)['state'], 'DANGER')

    def test_emergency_atr(self):
        self.assertEqual(risk(self.p(liqPrice=9600), 10000, 320, ARMED)['state'], 'EMERGENCY')

    def test_emergency_percentage_no_atr(self):
        self.assertEqual(risk(self.p(liqPrice=9875), 10000, None, ARMED)['state'], 'EMERGENCY')

    def test_edge_equality_deterministic(self):
        for distance, state in ((125, 'EMERGENCY'), (200, 'DANGER'), (300, 'WARNING'), (301, 'NORMAL')):
            self.assertEqual(risk(self.p(liqPrice=10000-distance), 10000, None, ARMED)['state'], state)

    def test_catastrophic_long(self):
        self.assertEqual(catastrophic_stop(self.p(liqPrice=9500), 10000, 100, 1, ARMED), '9575.0')

    def test_catastrophic_short(self):
        self.assertEqual(catastrophic_stop(self.p(side='SHORT', liqPrice=10500), 10000, 100, 1, ARMED), '10425.0')

    def test_stop_not_beyond_liquidation(self):
        for side, liq in (('LONG', 9000), ('SHORT', 11000)):
            stop = float(catastrophic_stop(self.p(side=side, liqPrice=liq), 10000, 100, 1, ARMED))
            self.assertTrue(min(liq, 10000) < stop < max(liq, 10000))

    def test_stop_not_behind_mark(self):
        with self.assertRaises(SafetyError):
            catastrophic_stop(self.p(liqPrice=9990), 10000, 100, 1, ARMED)

    def test_existing_safer_manual_sl_untouched(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9800', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertEqual(self.fake.orders[0]['slPrice'], '9800')

    def test_existing_weaker_manual_sl_warning(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9520', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('CLOSER TO LIQUIDATION' in x for x in self.telegram.messages))

    def test_missing_sl_shadow_dry_run(self):
        self.client.config = Config()
        self.guardian.config = self.client.config
        self.fake.positions = [position(liqPrice=9500)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('DRY-RUN INTENT SL' in x for x in self.telegram.messages))

    def test_protect_missing_phrase(self):
        self.client.config = replace(ARMED, arm_phrase='')
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_flag_false(self):
        self.client.config = replace(ARMED, allow_close=False)
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_shadow(self):
        self.client.config = replace(ARMED, mode='SHADOW')
        with self.assertRaises(SafetyError):
            self.client.preflight('CLOSE', self.p(), 100)

    def test_flash_exactly_one_position_id(self):
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertEqual(len(self.fake.posts), 1)
        self.assertEqual(json.loads(self.fake.posts[0][2]['data']), {'positionId': '123'})
        self.assertEqual(self.fake.posts[0][1], FLASH_CLOSE)

    def test_no_global_close_operationally(self):
        for file in ('trade_guardian.py', 'guardian_bitunix.py', 'guardian_risk.py'):
            self.assertNotIn('close_all_position', Path(file).read_text(encoding='utf-8'))

    def test_preclose_revalidation(self):
        self.fake.positions = [position(positionId='456')]
        with self.assertRaises(SafetyError):
            self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.fake.posts)

    def test_risk_improves_cancel(self):
        self.fake.mark = 10100
        with self.assertRaises(SafetyError):
            self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.store.actions)
        self.assertFalse(self.fake.posts)

    def test_ambiguous_response_reconciles_closed(self):
        self.fake.ambiguous = True
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.store.pending())
        self.assertTrue(self.store.state['lockout_until'] > time.time())
        self.assertEqual(len(self.fake.posts), 1)

    def test_restart_intent_reconciles_first(self):
        row = dict(key='CLOSE:123:1', action='CLOSE', positionId='123', risk_epoch=1, status='INTENT', timestamp=time.time())
        self.store.append('actions', row)
        self.store.close()
        self.store = Store(self.tmp.name)
        self.guardian.store = self.store
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(self.fake.posts)
        self.assertFalse(self.guardian.reconcile())

    def test_duplicate_emergency_no_duplicate_post(self):
        self.fake.apply_close = False
        self.fake.ambiguous = True
        self.guardian._act('CLOSE', self.p(), 100)
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertEqual(len(self.fake.posts), 1)
        self.assertTrue(self.store.pending())

    def test_api_timeout_fail_closed(self):
        self.fake.fail = True
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_telegram_failure_nonfatal(self):
        self.telegram.fail = True
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertEqual(len(self.fake.posts), 1)

    def test_no_chat_polling(self):
        self.assertNotIn('getUpdates', Path('guardian_telegram.py').read_text(encoding='utf-8'))

    def test_manual_close_no_action(self):
        self.store.state['position_id'] = '123'
        self.fake.positions = []
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertEqual(self.store.read('positions')[0]['event'], 'MANUAL_CLOSE_DETECTED')

    def test_no_opening_function(self):
        public = [name for name, _ in inspect.getmembers(Bitunix, inspect.isfunction) if not name.startswith('_')]
        self.assertEqual(set(public), {'position', 'mark', 'orders', 'precision', 'klines', 'preflight', 'execute'})

    def test_no_leverage_mutation(self):
        self.assertFalse(any('leverage' in route for route in POST_ALLOWLIST))

    def test_no_margin_mutation(self):
        self.assertFalse(any('margin' in route for route in POST_ALLOWLIST))

    def test_multiple_hedge_ambiguous(self):
        self.fake.positions = [position(), position(side='SHORT', positionId='456', liqPrice=10100)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_one_x_advisory_only(self):
        self.fake.positions = [position(leverage=1)]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_closed_candles_only(self):
        a = [[0, 100, 101, 99, 100, 10, 6], [3600000, 100, 101, 99, 100, 10, 6]]
        self.assertEqual(len(closed_bars(a, 3600000, 3600000)), 1)

    def test_mlrsi_prefix_invariant(self):
        c = 100 + np.cumsum(np.random.default_rng(10).normal(size=150))
        full, prefix = rolling_mlrsi(c, 27, 40), rolling_mlrsi(c[:100], 27, 40)
        for field in ('rsi', 'centroids', 'state', 'green_event', 'red_event'):
            np.testing.assert_equal(full[field][:100], prefix[field])

    def test_live_mlrsi_prefix_invariant(self):
        c = 100 + np.cumsum(np.random.default_rng(44).normal(size=600))
        current = latest_mlrsi(c, 27, 300)
        prior = latest_mlrsi(c[:-1], 27, 300)
        self.assertEqual(current['state'], prior['state'])
        self.assertEqual(current['green_event'], prior['green_event'])
        self.assertEqual(current, latest_mlrsi(np.r_[c, 100000][:-1], 27, 300))

    @staticmethod
    def _copilot_candles():
        now_ms = 200 * 14400000
        def rows(count, interval):
            index = np.arange(count)
            close = 100 + .02 * index
            low = 80 + 5 * np.sin(index / 7)
            return np.column_stack((now_ms - (count - index) * interval,
                                    close - .1, close + 1, low, close,
                                    np.full(count, 10), np.full(count, 6)))
        return rows(400, 3600000), rows(200, 14400000), rows(200, 900000), now_ms

    def test_primary_guardian_mlrsi_uses_low_not_close(self):
        hourly, four, quarter, now_ms = self._copilot_candles()
        observed = snapshot(hourly, four, quarter, now_ms)
        expected_low = latest_mlrsi(hourly[:, 3], length=27, max_data=3000, max_iter=1000)
        close_comparison = latest_mlrsi(hourly[:, 4], length=27, max_data=3000, max_iter=1000)
        self.assertAlmostEqual(observed['rsi27'], expected_low['rsi'])
        self.assertNotAlmostEqual(observed['rsi27'], close_comparison['rsi'])
        self.assertAlmostEqual(observed['long_threshold'], expected_low['long_threshold'])
        self.assertAlmostEqual(observed['short_threshold'], expected_low['short_threshold'])
        self.assertEqual(observed['momentum'], {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[expected_low['state']])
        self.assertEqual(observed['green_event'], expected_low['green_event'])
        self.assertEqual(observed['red_event'], expected_low['red_event'])
        self.assertEqual(observed['momentum_preset'], 'ML_RSI27_REAL')
        self.assertEqual(observed['momentum_source'], 'LOW')
        self.assertEqual(observed['momentum_parameters'], {
            'name': 'ML_RSI27_REAL', 'source': 'LOW', 'rsi_length': 27,
            'smoothing': 'EMA', 'smoothing_length': 4, 'smooth': True,
            'max_iter': 1000, 'max_data': 3000, 'clusters': 3})

    def test_close_only_changes_do_not_change_primary_mlrsi(self):
        hourly, four, quarter, now_ms = self._copilot_candles()
        before = snapshot(hourly, four, quarter, now_ms)
        changed = hourly.copy()
        changed[:, 4] = 110 + 3 * np.sin(np.arange(len(changed)) / 3)
        changed[:, 1] = changed[:, 4] - .1
        changed[:, 2] = changed[:, 4] + 1
        after = snapshot(changed, four, quarter, now_ms)
        self.assertNotAlmostEqual(latest_mlrsi(hourly[:, 4])['rsi'], latest_mlrsi(changed[:, 4])['rsi'])
        for key in ('rsi27', 'long_threshold', 'short_threshold', 'momentum', 'green_event', 'red_event'):
            self.assertEqual(before[key], after[key])

    def test_primary_low_mlrsi_excludes_open_candle(self):
        hourly, four, quarter, now_ms = self._copilot_candles()
        before = snapshot(hourly, four, quarter, now_ms)
        with_open = np.vstack((hourly, [now_ms, 105, 200, 1, 150, 10, 6]))
        after = snapshot(with_open, four, quarter, now_ms)
        self.assertEqual(before, after)

    def test_volatility_bands(self):
        self.assertEqual(volatility_state(100, 10000), 'NORMAL')
        self.assertEqual(volatility_state(200, 10000), 'ELEVATED')
        self.assertEqual(volatility_state(400, 10000), 'HIGH')
        self.assertEqual(volatility_state(None, 10000), 'UNKNOWN')

    def test_public_get_scope_is_btc_only(self):
        with self.assertRaises(SafetyError):
            self.client._request('GET', TICKERS, {'symbols': 'BTCUSDT,ETHUSDT'})
        with self.assertRaises(SafetyError):
            self.client._request('GET', POSITIONS, {'symbol': 'ETHUSDT', 'includeSubAccounts': 'false'})
        self.assertEqual(self.fake.calls, [])

    def test_wrong_symbol_and_duplicate_positions_blocked(self):
        for rows in ([position(symbol='ETHUSDT')], [position(), position(positionId='456')]):
            with self.subTest(rows=rows), self.assertRaises(SafetyError):
                parse_positions(rows)

    def test_regime_correct(self):
        self.assertEqual(direction('BULL', 'BULL', 'GREEN', .60, 'MIXED')[0], 'LONG_ALLOWED')
        self.assertEqual(direction('BEAR', 'BEAR', 'RED', .40, 'MIXED')[0], 'SHORT_ALLOWED')

    def test_taker_flow_edges(self):
        for ratio, expected in ((.60, 'STRONG BUY'), (.55, 'BUY'), (.50, 'NEUTRAL'), (.45, 'SELL'), (.40, 'STRONG SELL')):
            self.assertEqual(flow_state(ratio), expected)

    def test_long_allowed_logic(self):
        self.assertEqual(direction('BULL', 'BULL', 'GREEN', .50, 'BULLISH')[0], 'LONG_ALLOWED')

    def test_short_allowed_logic(self):
        self.assertEqual(direction('BEAR', 'BEAR', 'RED', .50, 'BEARISH')[0], 'SHORT_ALLOWED')

    def test_conflicting_regime_wait(self):
        self.assertEqual(direction('BULL', 'BEAR', 'GREEN', .70, 'BULLISH')[0], 'WAIT')

    def test_countertrend_warning_only(self):
        self.fake.positions = [position(side='SHORT', liqPrice=10500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice=10400, slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertTrue(any('⚠️⚠️ POSICIÓN CONTRA TENDENCIA ⚠️⚠️' in x for x in self.telegram.messages))
        self.assertFalse(self.fake.posts)

    def test_direction_conflict_never_flash_closes(self):
        self.test_countertrend_warning_only()

    def test_only_emergency_can_flash(self):
        for liq in (9500, 9700, 9800):
            self.fake.positions = [position(liqPrice=liq)]
            with self.subTest(liq=liq), self.assertRaises(SafetyError):
                self.client.preflight('CLOSE', self.p(liqPrice=liq), 50)
        self.assertFalse(self.fake.posts)

    def test_property_all_public_routes_triple_arm(self):
        for mode in ('SHADOW', 'PROTECT'):
            for sl in (False, True):
                for close in (False, True):
                    for phrase in ('', 'PROTECT_CAPITAL_ONLY', ' protect_capital_only '):
                        self.client.config = Config(mode=mode, allow_sl=sl, allow_close=close, arm_phrase=phrase)
                        for action in ('SL', 'CLOSE'):
                            self.fake.positions = [position(liqPrice=9500 if action == 'SL' else 9900)]
                            self.fake.orders = []
                            before = len(self.fake.posts)
                            try:
                                permit = self.client.preflight(action, self.client.position(), 100)
                                self.client.execute(permit)
                            except SafetyError:
                                pass
                            expected = mode == 'PROTECT' and phrase == 'PROTECT_CAPITAL_ONLY' and (sl if action == 'SL' else close)
                            self.assertEqual(len(self.fake.posts) - before, int(expected))
        self.assertTrue(all(call[1] in POST_ALLOWLIST for call in self.fake.posts))

    def test_permit_tampering_blocked(self):
        permit = self.client.preflight('CLOSE', self.p(), 100)
        permit['body']['positionId'] = '456'
        with self.assertRaises(SafetyError):
            self.client.execute(permit)
        self.assertFalse(self.fake.posts)

    def test_journal_fsync_before_post(self):
        def check(fake):
            on_disk = self.store.read('actions')
            self.assertEqual(on_disk[-1]['status'], 'INTENT')
        self.fake.before_post = check
        self.guardian._act('CLOSE', self.p(), 100)

    def test_nonzero_account_id_from_scoped_get_accepted(self):
        for wrapped in (False, True):
            self.fake.positions_wrapped = wrapped
            for account_id in (12345, '12345', 0, '0'):
                with self.subTest(wrapped=wrapped, account_id=account_id):
                    self.fake.positions = [position(subAccountId=account_id)]
                    self.assertEqual(self.client.position(), self.p())
                    self.assertEqual(self.fake.calls[-1][2]['params'],
                                     {'symbol': 'BTCUSDT', 'includeSubAccounts': 'false'})
                    self.assertIsNotNone(self.client.last_private)
        self.assertFalse(self.fake.posts)

    def test_malformed_account_ids_fail_closed(self):
        values = (None, '', True, False, -1, 1.0, 1.5, float('nan'), float('inf'),
                  float('-inf'), 'NaN', 'Infinity', '12.5', ' 123', '123abc',
                  '\u0661\u0662\u0663', [], {})
        for wrapped in (False, True):
            self.fake.positions_wrapped = wrapped
            for value in values:
                with self.subTest(wrapped=wrapped, value=value):
                    self.fake.positions = [position(subAccountId=value)]
                    with self.assertRaisesRegex(SafetyError, '^POSITION_ACCOUNT_ID_INVALID$'):
                        self.client.position()
                    self.assertIsNone(self.client.last_private)
                    with patch('builtins.print') as output:
                        self.guardian.cycle()
                    output.assert_any_call('GUARDIAN_BLIND_CODE=POSITION_ACCOUNT_ID_INVALID', flush=True)
        self.assertFalse(self.fake.posts)

    def test_position_field_specific_codes(self):
        fields = (('symbol', 'POSITION_SYMBOL_INVALID'),
                  ('side', 'POSITION_SIDE_INVALID'),
                  ('marginMode', 'POSITION_MARGIN_MODE_INVALID'),
                  ('positionMode', 'POSITION_MODE_INVALID'))
        for field, code in fields:
            for invalid in (None, 'UNSUPPORTED', [], {}):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaisesRegex(SafetyError, '^' + code + '$'):
                        self.p(**{field: invalid})
            row = position()
            del row[field]
            with self.subTest(field=field, missing=True), self.assertRaisesRegex(SafetyError, '^' + code + '$'):
                parse_positions([row])

    def test_field_diagnostics_never_log_actual_ids_or_payloads(self):
        cases = (({'symbol': 'PRIVATE_PAYLOAD'}, 'POSITION_SYMBOL_INVALID'),
                 ({'side': 'PRIVATE_PAYLOAD'}, 'POSITION_SIDE_INVALID'),
                 ({'marginMode': 'PRIVATE_PAYLOAD'}, 'POSITION_MARGIN_MODE_INVALID'),
                 ({'positionMode': 'PRIVATE_PAYLOAD'}, 'POSITION_MODE_INVALID'),
                 ({'subAccountId': 'PRIVATE_PAYLOAD'}, 'POSITION_ACCOUNT_ID_INVALID'))
        for changes, code in cases:
            with self.subTest(code=code):
                self.fake.positions = [position(positionId='987654321987654321', **changes)]
                with patch('builtins.print') as output:
                    self.guardian.cycle()
                output.assert_any_call('GUARDIAN_BLIND_CODE=' + code, flush=True)
                self.assertNotIn('PRIVATE_PAYLOAD', str(output.call_args_list))
                self.assertNotIn('987654321987654321', str(output.call_args_list))
                self.assertNotIn('fake-key', str(output.call_args_list))
                self.assertNotIn('fake-secret', str(output.call_args_list))
        self.assertFalse(self.fake.posts)

    def test_include_subaccounts_false_mandatory(self):
        invalid = ({'symbol': 'BTCUSDT'},
                   {'symbol': 'BTCUSDT', 'includeSubAccounts': 'true'},
                   {'symbol': 'BTCUSDT', 'includeSubAccounts': True},
                   {'symbol': 'BTCUSDT', 'includeSubAccounts': False},
                   {'symbol': 'BTCUSDT', 'includeSubAccounts': None},
                   {'symbol': 'BTCUSDT', 'includeSubAccounts': 'false', 'subAccountId': 12345})
        for params in invalid:
            with self.subTest(params=params), self.assertRaisesRegex(SafetyError, '^GET_SCOPE_BLOCKED$'):
                self.client._request('GET', POSITIONS, params)
        self.assertEqual(self.fake.calls, [])
        self.client.position()
        self.assertEqual(self.fake.calls[-1][2]['params'],
                         {'symbol': 'BTCUSDT', 'includeSubAccounts': 'false'})

    def test_duplicate_positions_with_valid_account_ids_fail_closed(self):
        self.fake.positions = [position(subAccountId=12345),
                               position(positionId='456', subAccountId=67890)]
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                self.fake.positions_wrapped = wrapped
                with self.assertRaisesRegex(SafetyError, '^AMBIGUOUS_POSITIONS$'):
                    self.client.position()
                with patch('builtins.print'):
                    self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_shadow_nonzero_account_id_zero_posts(self):
        self.client.config = self.guardian.config = Config()
        self.fake.positions = [position(subAccountId=12345)]
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                self.fake.positions_wrapped = wrapped
                with patch('builtins.print'):
                    heartbeat = self.guardian.cycle()
                self.assertTrue(heartbeat['position'])
                self.assertEqual(heartbeat['risk'], 'EMERGENCY')
                self.assertIsNotNone(heartbeat['last_successful_private_read'])
                self.assertEqual(heartbeat['armed'], {'sl': False, 'close': False})
        self.assertFalse(self.fake.posts)

    def test_side_aliases_normalize_only_to_long_short(self):
        self.assertEqual(SIDE_ALIASES, {'LONG': 'LONG', 'BUY': 'LONG', 'SHORT': 'SHORT', 'SELL': 'SHORT'})
        for raw, normalized in SIDE_ALIASES.items():
            for value in (raw, raw.lower(), raw.title()):
                with self.subTest(value=value):
                    self.fake.positions = [position(side=value)]
                    self.assertEqual(self.client.position().side, normalized)
        self.assertFalse(self.fake.posts)

    def test_unknown_side_aliases_fail_closed(self):
        for value in ('BULL', 'BEAR', 'OPEN', 'CLOSE', 1, 2, '', None, ' BUY', 'SELL ', True, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(SafetyError, '^POSITION_SIDE_INVALID$'):
                self.p(side=value)

    def test_buy_uses_long_liquidation_and_catastrophic_stop(self):
        p = self.p(side='BUY', liqPrice=9500)
        self.assertEqual(p.side, 'LONG')
        self.assertEqual(risk(p, 10000, 100, ARMED)['state'], 'NORMAL')
        self.assertEqual(catastrophic_stop(p, 10000, 100, 1, ARMED), '9575.0')
        with self.assertRaisesRegex(SafetyError, '^LIQUIDATION_SIDE_INVALID$'):
            risk(self.p(side='BUY', liqPrice=10500), 10000, 100, ARMED)

    def test_sell_uses_short_liquidation_and_catastrophic_stop(self):
        p = self.p(side='SELL', liqPrice=10500)
        self.assertEqual(p.side, 'SHORT')
        self.assertEqual(risk(p, 10000, 100, ARMED)['state'], 'NORMAL')
        self.assertEqual(catastrophic_stop(p, 10000, 100, 1, ARMED), '10425.0')
        with self.assertRaisesRegex(SafetyError, '^LIQUIDATION_SIDE_INVALID$'):
            risk(self.p(side='SELL', liqPrice=9500), 10000, 100, ARMED)

    def test_aliases_duplicate_positions_still_blocked(self):
        self.fake.positions = [position(side='BUY'), position(side='SELL', positionId='456')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertIsNone(self.client.last_private)

    def test_side_aliases_shadow_zero_posts(self):
        self.client.config = self.guardian.config = Config()
        for side, liq in (('BUY', 9900), ('SELL', 10100)):
            self.fake.positions = [position(side=side, liqPrice=liq)]
            with patch('builtins.print'):
                self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    @staticmethod
    def human_bias(bias='LONG_ALLOWED', quality='GOOD'):
        bearish = bias == 'SHORT_ALLOWED'
        return dict(bias=bias, entry_quality=quality,
                    entry_reason='CONFIRMED_RECLAIM' if quality == 'GOOD' else 'EXTENDED' if quality == 'POOR' else 'WAIT_RECLAIM',
                    trend4='BEAR' if bearish else 'BULL', trend1='BEAR' if bearish else 'BULL',
                    momentum='RED' if bearish else 'GREEN', taker_buy=.386 if bearish else .614,
                    structure='BEARISH' if bearish else 'BULLISH', volatility='ELEVATED',
                    entry_atr_1h=100, entry_level=10100 if bearish else 9900,
                    support=9500, resistance=10500)

    def test_long_good_has_green_entry_banner(self):
        text = render_copilot(self.human_bias(), Config())
        self.assertTrue(text.startswith('🟢📈 LONG — PUEDES BUSCAR ENTRADA'))
        self.assertIn('✅ Puedes buscar entrada LONG', text)
        self.assertIn('🚫 SHORT: NO recomendado ahora', text)
        self.assertIn('🟢 ENTRADA: BUENA ZONA', text)
        self.assertIn('🟢 Compras taker: 61.4%', text)

    def test_short_good_has_red_entry_banner(self):
        text = render_copilot(self.human_bias('SHORT_ALLOWED'), Config())
        self.assertTrue(text.startswith('🔴📉 SHORT — PUEDES BUSCAR ENTRADA'))
        self.assertIn('✅ Puedes buscar entrada SHORT', text)
        self.assertIn('🚫 LONG: NO recomendado ahora', text)
        self.assertIn('🔴 Compras taker: 38.6%', text)

    def test_wait_banner_says_no_trade(self):
        data = self.human_bias('WAIT')
        data['trend1'] = 'BEAR'
        text = render_copilot(data, Config())
        self.assertTrue(text.startswith('🟡⏳ NO OPERAR — ESPERAR'))
        self.assertIn('🚫 No LONG\n🚫 No SHORT', text)
        self.assertIn('4H y 1H no están alineados', text)
        self.assertIn('1H recupere SMA200', text)
        self.assertNotIn('BUENA ZONA', text)

    def test_unknown_banner_never_allows_an_entry(self):
        text = render_copilot({'bias': 'UNKNOWN', 'entry_quality': 'GOOD'}, Config())
        self.assertTrue(text.startswith('⚫❓ SIN DATOS SUFICIENTES — NO OPERAR'))
        self.assertIn('🚫 No abrir LONG\n🚫 No abrir SHORT', text)
        self.assertNotIn('BUENA ZONA', text)
        self.assertNotIn('Puedes buscar entrada', text)

    def test_poor_long_and_short_do_not_allow_entry(self):
        for bias, side, icon in (('LONG_ALLOWED', 'LONG', '📈'), ('SHORT_ALLOWED', 'SHORT', '📉')):
            with self.subTest(bias=bias):
                text = render_copilot(self.human_bias(bias, 'POOR'), Config())
                self.assertTrue(text.startswith('🟠' + icon + ' BIAS ' + side + ' — ESPERA MEJOR ENTRADA'))
                self.assertIn('🔴 ENTRADA: NO PERSEGUIR PRECIO', text)
                self.assertIn('🚫 NO ENTRAR AHORA', text)
                self.assertNotIn('Puedes buscar entrada', text)
                self.assertNotIn('ENTRADA PERMITIDA', text)
                self.assertNotIn('Se permite buscar entrada', text)

    def test_missing_entry_evidence_renders_caution(self):
        text = render_copilot({'bias': 'LONG_ALLOWED'}, Config())
        self.assertIn('🟠 ENTRADA: PRECAUCIÓN', text)
        self.assertNotIn('BUENA ZONA', text)
        self.assertNotIn('PUEDES BUSCAR ENTRADA', text)

    def test_shadow_banner_clearly_disarmed(self):
        text = render_copilot(self.human_bias(), replace(ARMED, mode='SHADOW'), private_ready=True)
        self.assertIn('👁️ GUARDIAN: SHADOW\n🔒 Protección automática DESARMADA', text)
        self.assertNotIn('✅ Cierre emergencia ARMADO', text)
        self.assertNotIn('✅ SL catastrófico ARMADO', text)

    def test_protection_display_requires_real_triple_arm_and_credentials(self):
        full = protection_status(ARMED, private_ready=True)
        self.assertIn('🛡️🚨 GUARDIAN: PROTECT CAPITAL', full)
        sl_only = protection_status(replace(ARMED, allow_close=False), private_ready=True)
        self.assertIn('✅ SL catastrófico ARMADO', sl_only)
        self.assertIn('❌ Auto-cierre desarmado', sl_only)
        for config, ready in ((replace(ARMED, arm_phrase=''), True), (ARMED, False)):
            text = protection_status(config, private_ready=ready)
            self.assertIn('Protección automática DESARMADA', text)
            self.assertNotIn('✅ Cierre emergencia ARMADO', text)

    def test_telegram_rendering_ignores_raw_payloads_and_credentials(self):
        data = self.human_bias()
        data.update(why='fake-secret raw exchange body', api_key='fake-key', payload={'token': 'TELEGRAM-SECRET'})
        text = render_copilot(data, ARMED, self.p(), risk(self.p(), 10000, 100, ARMED),
                              statuses=['fake-secret'], target='fake-secret', private_ready=True)
        for secret in ('fake-secret', 'fake-key', 'TELEGRAM-SECRET', 'raw exchange body', 'PROTECT_CAPITAL_ONLY'):
            self.assertNotIn(secret, text)

    def test_danger_banner_does_not_flash_close(self):
        self.fake.positions = [position(liqPrice=9800)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice=9950, slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            heartbeat = self.guardian.cycle()
        self.assertEqual(heartbeat['risk'], 'DANGER')
        self.assertTrue(any(x.startswith('🛡️🟠 RIESGO: DANGER') for x in self.telegram.messages))
        self.assertFalse(self.fake.posts)

    def test_emergency_closes_independently_of_entry_quality_and_bias(self):
        self.guardian.bias = {'bias': 'WAIT', 'entry_quality': 'POOR'}
        self.market.value = 'WAIT'
        self.fake.positions = [position(side='BUY')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertEqual([call[1] for call in self.fake.posts], [FLASH_CLOSE])
        self.assertTrue(any(x.startswith('🛡️🔴🚨 EMERGENCIA DE LIQUIDACIÓN') for x in self.telegram.messages))

    def test_startup_and_stored_copilot_snapshots_start_with_decision_banner(self):
        self.client.config = self.guardian.config = Config()
        data = self.human_bias('LONG_ALLOWED', 'POOR')
        self.market.bias = lambda: dict(data)
        with patch('builtins.print'):
            self.guardian.cycle()
        startup = next(text for text in self.telegram.messages if 'I-GOD TRADE GUARDIAN ONLINE' in text)
        self.assertTrue(startup.startswith('🟠📈 BIAS LONG'))
        self.assertTrue(self.store.read('bias')[0]['human_snapshot'].startswith('🟠📈 BIAS LONG'))
        self.assertFalse(self.fake.posts)

    def test_copilot_entry_change_alert_deduplicates(self):
        self.client.config = self.guardian.config = Config()
        data = self.human_bias(quality='CAUTION')
        self.market.bias = lambda: dict(data)
        with patch('builtins.print'):
            self.guardian.cycle()
            data.update(entry_quality='POOR', entry_reason='EXTENDED')
            self.guardian._bias_due = 0
            self.guardian.cycle()
            self.guardian.cycle()
        poor = [text for text in self.telegram.messages if text.startswith('🟠📈 BIAS LONG') and 'NO PERSEGUIR' in text]
        self.assertEqual(len(poor), 1)
        self.assertFalse(self.fake.posts)

    @staticmethod
    def entry_candles():
        hourly = np.array([[i * 3600000, 100, 102, 98, 100, 10, 6] for i in range(20)], float)
        highs = [100, 102, 110, 103, 102, 101, 104, 112, 105, 104, 103, 108, 120, 111, 110, 109, 106, 105, 104, 103, 114]
        lows = [95, 94, 93, 94, 95, 96, 95, 94, 95, 96, 97, 98, 97, 96, 97, 98, 99, 100, 99, 98, 112]
        quarter = np.array([[i * 900000, (h + l) / 2, h, l, (h + l) / 2, 10, 6]
                            for i, (h, l) in enumerate(zip(highs, lows))], float)
        return hourly, quarter

    def test_entry_quality_good_requires_confirmed_reclaim(self):
        h, q = self.entry_candles()
        self.assertEqual(confirmed_structure(q)[0], 'BULLISH')
        quality = entry_quality('LONG_ALLOWED', h, q, 'GREEN', 'BULLISH')
        self.assertEqual((quality['entry_quality'], quality['entry_level']), ('GOOD', 112))
        self.assertEqual(quality['resistance'], 120)
        q = q.copy()
        q[:, 1:5] = 200 - q[:, 1:5]
        q[:, [2, 3]] = q[:, [3, 2]]
        quality = entry_quality('SHORT_ALLOWED', h, q, 'RED', 'BEARISH')
        self.assertEqual((quality['entry_quality'], quality['entry_level']), ('GOOD', 88))

    def test_entry_quality_near_confirmed_resistance_or_support_is_poor(self):
        h, q = self.entry_candles()
        q[-1, 1:5] = [119, 119.5, 118.5, 119]
        quality = entry_quality('LONG_ALLOWED', h, q, 'GREEN', 'BULLISH')
        self.assertEqual((quality['entry_quality'], quality['entry_reason']), ('POOR', 'NEAR_RESISTANCE'))
        q[:, 1:5] = 200 - q[:, 1:5]
        q[:, [2, 3]] = q[:, [3, 2]]
        quality = entry_quality('SHORT_ALLOWED', h, q, 'RED', 'BEARISH')
        self.assertEqual((quality['entry_quality'], quality['entry_reason']), ('POOR', 'NEAR_SUPPORT'))

    def test_entry_quality_extension_is_poor_without_changing_bias(self):
        h, q = self.entry_candles()
        q[-1, 1:5] = [129, 130, 128, 129]
        result = entry_quality('LONG_ALLOWED', h, q, 'GREEN', 'BULLISH')
        self.assertEqual((result['entry_quality'], result['entry_reason']), ('POOR', 'EXTENDED'))
        self.assertNotIn('bias', result)
        self.assertEqual(direction('BULL', 'BULL', 'GREEN', .614, 'BULLISH')[0], 'LONG_ALLOWED')

    def test_entry_quality_missing_atr_pivots_or_alignment_never_good(self):
        h, q = self.entry_candles()
        for hours, quarters, momentum, structure in ((h[:2], q, 'GREEN', 'BULLISH'),
                (h, q[:4], 'GREEN', 'BULLISH'), (h, q, 'NEUTRAL', 'BULLISH'), (h, q, 'GREEN', 'MIXED')):
            with self.subTest(momentum=momentum, structure=structure):
                self.assertEqual(entry_quality('LONG_ALLOWED', hours, quarters, momentum, structure)['entry_quality'], 'CAUTION')

    def test_entry_snapshot_excludes_future_quarter_candles(self):
        h, f, q, now = self._copilot_candles()
        before = snapshot(h, f, q, now)
        q = np.vstack((q, [now, 110, 100000, 1, 111, 10, 6],
                      [now + 900000, 110, 100000, 1, 111, 10, 6]))
        self.assertEqual(before, snapshot(h, f, q, now))

    def test_entry_levels_are_only_confirmed_pivots(self):
        h, q = self.entry_candles()
        result = entry_quality('LONG_ALLOWED', h, q, 'GREEN', 'BULLISH')
        _, highs, lows = confirmed_structure(q)
        self.assertIn(result['entry_level'], [level for confirmation, level in highs if confirmation < len(q) - 1])
        self.assertIn(result['resistance'], [level for _, level in highs])
        self.assertIn(result['support'], [level for _, level in lows])

    def test_expectations_never_invent_levels(self):
        data = self.human_bias(quality='POOR')
        data.update(entry_reason='NEAR_RESISTANCE', resistance=120, entry_level=112)
        text = render_copilot(data, Config())
        self.assertIn('Breakout + reclaim de 120.00', text)
        missing_levels = self.human_bias(quality='CAUTION')
        missing_levels.update(entry_level=None, resistance=None, support=None)
        text = render_copilot(missing_levels, Config())
        self.assertNotIn('Pullback y reclaim del nivel confirmado', text)
        self.assertNotIn('Breakout + reclaim de ', text)

    def test_live_mark_prevents_chasing_between_closed_candles(self):
        data = self.human_bias()
        observed = current_entry_quality(data, 10300)
        self.assertEqual((observed['bias'], observed['entry_quality'], observed['entry_reason']),
                         ('LONG_ALLOWED', 'POOR', 'EXTENDED'))
        self.assertEqual(data['entry_quality'], 'GOOD')
        bearish = self.human_bias('SHORT_ALLOWED')
        observed = current_entry_quality(bearish, 9700)
        self.assertEqual((observed['bias'], observed['entry_quality']), ('SHORT_ALLOWED', 'POOR'))
        self.assertEqual(current_entry_quality(data, None)['entry_quality'], 'CAUTION')
        self.assertEqual(current_entry_quality(data, 9800)['entry_quality'], 'CAUTION')
        self.assertEqual(current_entry_quality(data, 10000)['entry_quality'], 'GOOD')

    def test_live_mark_does_not_promote_unconfirmed_entry(self):
        for quality in ('CAUTION', 'POOR'):
            self.assertEqual(current_entry_quality(self.human_bias(quality=quality), 10000)['entry_quality'], quality)

    def test_missing_fields_blocked(self):
        row = position()
        del row['qty']
        with self.assertRaises(SafetyError):
            parse_positions([row])

    def test_clock_unverified_blocks(self):
        response = Response([position()])
        response.headers = {}
        self.fake.request = lambda *a, **kw: response
        with self.assertRaises(SafetyError):
            self.client.position()

    def test_rolling_maxdata(self):
        c = 100 + np.cumsum(np.random.default_rng(11).normal(size=100))
        ml = rolling_mlrsi(c, 27, 20)
        self.assertEqual(ml['window_count'][-1], 20)
        expected = cluster_three(ml['rsi'][-20:])[0]
        np.testing.assert_allclose(ml['centroids'][-1], expected)

    def test_state_event_neutral_transition(self):
        state, green, red, valid = states_and_events(np.array([50, 70, 20, 50, 20]), np.full(5, 40), np.full(5, 60))
        np.testing.assert_equal(green, [False, True, False, False, False])
        np.testing.assert_equal(red, [False, False, False, False, True])

    def test_pivot_confirmation_delay(self):
        a = np.array([[i, 100, h, 90, 100, 1, .5] for i, h in enumerate([101, 102, 110, 103, 102, 101])], float)
        self.assertEqual(confirmed_structure(a[:4])[1], [])
        self.assertEqual(confirmed_structure(a[:5])[1], [(4, 110)])

    def test_atr_reference(self):
        a = np.array([[i, 100, 102, 98, 100, 1, .5] for i in range(20)], float)
        self.assertEqual(atr14(a), 4)

    def test_binance_failure_risk_survives(self):
        self.market.value = 'UNKNOWN'
        self.market.atr = None
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertEqual(self.fake.posts[0][1], FLASH_CLOSE)

    def test_torn_journal_fail_closed(self):
        self.store.close()
        Path(self.tmp.name, 'actions.jsonl').write_text('{"status":"INTENT"')
        with self.assertRaises(SafetyError):
            Store(self.tmp.name)

    def test_tp_only_untouched(self):
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', tpPrice='11000')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)

    def test_owned_sl_no_modify(self):
        self.fake.positions = [position(liqPrice=9500)]
        with patch('builtins.print'):
            self.guardian.cycle()
            self.guardian.cycle()
        self.assertEqual(len(self.fake.posts), 1)
        self.assertEqual(self.store.state['owned_sl']['123'], '777')

    def test_lockout_does_not_close_safe_new_position(self):
        self.store.state['lockout_until'] = time.time() + 7200
        self.fake.positions = [position(liqPrice=9500)]
        self.fake.orders = [dict(positionId='123', symbol='BTCUSDT', slPrice='9800', slStopType='MARK_PRICE')]
        with patch('builtins.print'):
            self.guardian.cycle()
        self.assertFalse(self.fake.posts)
        self.assertTrue(any('LOCKOUT VIOLATION' in x for x in self.telegram.messages))

    def test_emergency_closed_not_manual_close(self):
        self.guardian._act('CLOSE', self.p(), 100)
        self.assertFalse(any('MANUAL_CLOSE' in x for x in self.telegram.messages))


if __name__ == '__main__':
    unittest.main()
