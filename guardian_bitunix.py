"""Restricted Bitunix transport. No generic public order API. No POST retries."""
import hashlib
import json
import secrets
import time
from email.utils import parsedate_to_datetime
import requests
from guardian_risk import SafetyError, parse_positions, number, risk, catastrophic_stop

POSITIONS = '/api/v1/futures/position/get_pending_positions'
TPSL = '/api/v1/futures/tpsl/get_pending_orders'
TICKERS = '/api/v1/futures/market/tickers'
PAIRS = '/api/v1/futures/market/trading_pairs'
KLINES = '/api/v1/futures/market/kline'
PLACE_SL = '/api/v1/futures/tpsl/position/place_order'
FLASH_CLOSE = '/api/v1/futures/trade/flash_close_position'
GET_ALLOWLIST = frozenset((POSITIONS, TPSL, TICKERS, PAIRS, KLINES))
POST_ALLOWLIST = frozenset((PLACE_SL, FLASH_CLOSE))


def signature(key, secret, nonce, timestamp, params, body):
    def text(value):
        return 'true' if value is True else 'false' if value is False else str(value)
    canonical = ''.join(str(k) + text(params[k]) for k in sorted(params))
    digest = hashlib.sha256((nonce + timestamp + key + canonical + body).encode()).hexdigest()
    return hashlib.sha256((digest + secret).encode()).hexdigest()


def _response_list(data, list_key, code):
    """Normalize documented lists and production wrappers without hiding omissions."""
    if isinstance(data, list):
        return data, None
    if not isinstance(data, dict) or not isinstance(data.get(list_key), list):
        raise SafetyError(code + '_RESPONSE_INVALID')
    rows, total = data[list_key], data.get('total')
    if type(total) is not int or total < len(rows):
        raise SafetyError(code + '_TOTAL_INVALID')
    return rows, total


class Bitunix:
    def __init__(self, config, key='', secret='', transport=None, clock=time.time):
        self.config = config
        self._key, self._secret = key, secret
        self._http = transport or requests.Session()
        self.clock = clock
        self.last_private = None
        self.last_public = None
        self._last_wall = clock()
        self._last_mono = time.monotonic()
        self._permit = None
        self._permit_body = None
        self._permit_path = None
        self._permit_time = None

    @property
    def credentials_present(self):
        return bool(self._key and self._secret)

    def _request(self, method, path, params=None, body=None, permit=None):
        params = params or {}
        if method == 'GET':
            if path not in GET_ALLOWLIST or body is not None:
                raise SafetyError('ENDPOINT_BLOCKED')
            schemas = {
                POSITIONS: {'symbol': 'BTCUSDT', 'includeSubAccounts': 'false'},
                TICKERS: {'symbols': 'BTCUSDT'}, PAIRS: {'symbols': 'BTCUSDT'},
                KLINES: {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 100,
                         'type': params.get('type')},
            }
            if path == TPSL:
                valid = (set(params) == {'symbol', 'positionId', 'limit', 'skip'}
                         and params.get('symbol') == 'BTCUSDT'
                         and isinstance(params.get('positionId'), str)
                         and params['positionId'].isdecimal()
                         and params.get('limit') == 100 and isinstance(params.get('skip'), int)
                         and 0 <= params['skip'] < 1000)
            else:
                valid = path in schemas and params == schemas[path]
                if path == KLINES:
                    valid = valid and params['type'] in ('MARK_PRICE', 'LAST_PRICE')
            if not valid:
                raise SafetyError('GET_SCOPE_BLOCKED')
        elif method == 'POST':
            action = 'SL' if path == PLACE_SL else 'CLOSE' if path == FLASH_CLOSE else ''
            if path not in POST_ALLOWLIST or not self.config.armed(action):
                raise SafetyError('POST_DISARMED_OR_BLOCKED')
            if not permit or permit is not self._permit or self._permit_time is None or self.clock() - self._permit_time > 5:
                raise SafetyError('FRESH_PREFLIGHT_REQUIRED')
            expected = self._permit_body
            if path != self._permit_path or json.dumps(body, sort_keys=True) != expected or params:
                raise SafetyError('MUTATION_SHAPE_BLOCKED')
            self._permit = None  # single-use even if transport times out
        else:
            raise SafetyError('METHOD_BLOCKED')
        private = path in (POSITIONS, TPSL, PLACE_SL, FLASH_CLOSE)
        if private and not self.credentials_present:
            raise SafetyError('CREDENTIALS_ABSENT')
        wall, mono = self.clock(), time.monotonic()
        if abs((wall - self._last_wall) - (mono - self._last_mono)) > 5:
            self._permit = None
            self._last_wall, self._last_mono = wall, mono
            raise SafetyError('CLOCK_JUMP')
        self._last_wall, self._last_mono = wall, mono
        payload = json.dumps(body, separators=(',', ':'), ensure_ascii=True) if body is not None else ''
        headers = {'Content-Type': 'application/json', 'language': 'en-US'}
        if private:
            nonce, stamp = secrets.token_hex(16), str(int(wall * 1000))
            headers.update({'api-key': self._key, 'nonce': nonce, 'timestamp': stamp,
                            'sign': signature(self._key, self._secret, nonce, stamp, params, payload)})
        try:
            response = self._http.request(method, 'https://fapi.bitunix.com' + path,
                                          params=params, data=payload or None, headers=headers,
                                          timeout=(2, 3), allow_redirects=False)
            if time.monotonic() - mono > 5 or response.status_code != 200:
                raise SafetyError('HTTP_FAILURE_OR_STALE')
            date = response.headers.get('Date')
            if not date or abs(parsedate_to_datetime(date).timestamp() - self.clock()) > 5:
                raise SafetyError('SERVER_CLOCK_UNVERIFIED')
            result = response.json()
            if not isinstance(result, dict) or result.get('code') != 0:
                raise SafetyError('API_REJECTED_AUTH_OR_REQUEST')
            if 'data' not in result:
                raise SafetyError('API_DATA_MISSING')
        except SafetyError:
            self._permit = None
            raise
        except Exception:
            self._permit = None
            raise SafetyError('TRANSPORT_OR_RESPONSE_FAILURE') from None
        if method == 'GET':
            if private:
                self.last_private = self.clock()
            else:
                self.last_public = self.clock()
        return result['data']

    def position(self):
        try:
            rows, total = _response_list(self._request('GET', POSITIONS,
                                        {'symbol': 'BTCUSDT', 'includeSubAccounts': 'false'}),
                                        'positionList', 'POSITIONS')
            if total is not None and total != len(rows):
                raise SafetyError('POSITIONS_PAGINATION_INCOMPLETE')
            value = parse_positions(rows)
            self.last_private = self.clock()
            return value
        except SafetyError:
            self.last_private = None
            raise

    def mark(self):
        rows = self._request('GET', TICKERS, {'symbols': 'BTCUSDT'})
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('symbol') != 'BTCUSDT':
            self.last_public = None
            raise SafetyError('TICKER_AMBIGUOUS')
        try:
            value = number(rows[0].get('markPrice'))
            number(rows[0].get('lastPrice'))
        except SafetyError:
            self.last_public = None
            raise
        if value <= 0:
            self.last_public = None
            raise SafetyError('MARK_INVALID')
        self.last_public = self.clock()
        return value

    def orders(self, position_id):
        try:
            rows, total = [], None
            for skip in range(0, 1000, 100):
                page, page_total = _response_list(self._request('GET', TPSL,
                    {'symbol': 'BTCUSDT', 'positionId': position_id, 'limit': 100, 'skip': skip}),
                    'orderList', 'ORDERS')
                if page_total is not None:
                    if (total is not None and page_total != total) or page_total < skip + len(page):
                        raise SafetyError('ORDERS_TOTAL_INVALID')
                    total = page_total
                if len(page) > 100:
                    raise SafetyError('ORDERS_PAGINATION_INCOMPLETE')
                if any(not isinstance(p, dict) or p.get('positionId') != position_id or p.get('symbol') != 'BTCUSDT' for p in page):
                    raise SafetyError('ORDERS_SCOPE_INVALID')
                rows.extend(page)
                if len(page) < 100 or (total is not None and len(rows) == total):
                    if total is not None and len(rows) != total:
                        raise SafetyError('ORDERS_PAGINATION_INCOMPLETE')
                    self.last_private = self.clock()
                    return rows
            raise SafetyError('ORDERS_PAGINATION_INCOMPLETE')
        except SafetyError:
            self.last_private = None
            raise

    def precision(self):
        rows = self._request('GET', PAIRS, {'symbols': 'BTCUSDT'})
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('symbol') != 'BTCUSDT'
                or rows[0].get('symbolStatus') != 'OPEN' or rows[0].get('isApiSupported') is not True):
            raise SafetyError('PAIR_METADATA_INVALID')
        precision = rows[0].get('quotePrecision')
        if not isinstance(precision, int) or not 0 <= precision <= 12:
            raise SafetyError('PRECISION_INVALID')
        self.last_public = self.clock()
        return precision

    def klines(self, price_type='MARK_PRICE'):
        if price_type not in ('MARK_PRICE', 'LAST_PRICE'):
            raise SafetyError('KLINE_TYPE_INVALID')
        rows = self._request('GET', KLINES, {'symbol': 'BTCUSDT', 'interval': '1h',
                                             'limit': 100, 'type': price_type})
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            self.last_public = None
            raise SafetyError('KLINES_INVALID')
        self.last_public = self.clock()
        return rows

    def preflight(self, action, original, atr):
        """Returns a one-use capability after fresh position, orders and mark reads."""
        self._permit = None
        started = self.clock()
        if action not in ('SL', 'CLOSE') or not self.config.armed(action):
            raise SafetyError('ACTION_DISARMED')
        current = self.position()
        if (current is None or current.position_id != original.position_id or current.side != original.side
                or current.qty != original.qty or current.leverage < 2):
            raise SafetyError('POSITION_CHANGED_OR_ADVISORY_ONLY')
        orders = self.orders(current.position_id)
        precision = self.precision() if action == 'SL' else None
        mark = self.mark()  # last read, closest to action
        current_risk = risk(current, mark, atr, self.config)
        if self.clock() - started > 10:
            raise SafetyError('PREFLIGHT_STALE')
        if action == 'CLOSE':
            if current_risk['state'] != 'EMERGENCY':
                raise SafetyError('EMERGENCY_CANCELLED_RISK_IMPROVED')
            path, body = FLASH_CLOSE, {'positionId': current.position_id}
        else:
            if orders:
                raise SafetyError('EXISTING_MANUAL_ORDER_UNTOUCHED')
            stop = catastrophic_stop(current, mark, atr, precision, self.config)
            path, body = PLACE_SL, {'symbol': 'BTCUSDT', 'positionId': current.position_id,
                                  'slPrice': stop, 'slStopType': 'MARK_PRICE'}
        self._permit = {'path': path, 'body': body, 'time': self.clock()}
        self._permit_body = json.dumps(body, sort_keys=True)
        self._permit_path = path
        self._permit_time = self.clock()
        return self._permit

    def execute(self, permit):
        data = self._request('POST', permit['path'], body=permit['body'], permit=permit)
        # Do not retain arbitrary exchange messages or payloads.
        field = 'orderId' if permit['path'] == PLACE_SL else 'positionId'
        value = data.get(field) if isinstance(data, dict) else None
        if not isinstance(value, str) or not value.isdecimal() or len(value) > 64:
            raise SafetyError('MUTATION_RESPONSE_AMBIGUOUS')
        if field == 'positionId' and value != permit['body']['positionId']:
            raise SafetyError('MUTATION_RESPONSE_AMBIGUOUS')
        return {field: value}
