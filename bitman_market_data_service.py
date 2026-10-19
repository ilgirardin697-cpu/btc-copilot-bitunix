"""Stateless, private-only BTCUSDT USD-M closed-hour data gateway. No authority."""
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import time
from urllib import request as http
from urllib.parse import parse_qsl, urlencode, urlsplit

UPSTREAM = 'https://fapi.binance.com/fapi/v1/klines'
PRIVATE_HOST = 'bitman-market-data.railway.internal'
HOUR = 3_600_000
UPSTREAM_TIMEOUT = 4
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
QUERY_KEYS = frozenset(('symbol', 'interval', 'startTime', 'endTime', 'limit'))


def page_request(query, now_ms):
    """Only complete, aligned hourly ranges of at most 1500 closed candles."""
    if len(query) > 256:
        raise ValueError('INVALID_REQUEST')
    pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
    params = dict(pairs)
    if len(pairs) != len(params) or set(params) != QUERY_KEYS:
        raise ValueError('INVALID_REQUEST')
    if params['symbol'] != 'BTCUSDT' or params['interval'] != '1h':
        raise ValueError('INVALID_REQUEST')
    for key in ('startTime', 'endTime', 'limit'):
        value = params[key]
        if not value or len(value) > 16 or not value.isascii() or not value.isdecimal():
            raise ValueError('INVALID_REQUEST')
    start, end, limit = (int(params[key]) for key in ('startTime', 'endTime', 'limit'))
    if (not 1 <= limit <= 1500 or start % HOUR or (end + 1) % HOUR or end < start
            or end >= int(now_ms) // HOUR * HOUR or (end - start + 1) // HOUR > limit):
        raise ValueError('INVALID_REQUEST')
    return params


class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_page(params):
    """Fixed HTTPS upstream, no env proxies, credentials, redirects or retries."""
    opener = http.build_opener(http.ProxyHandler({}), NoRedirect())
    req = http.Request(UPSTREAM + '?' + urlencode(params), headers={'Accept': 'application/json'})
    with opener.open(req, timeout=UPSTREAM_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError('UPSTREAM_UNAVAILABLE')
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError('UPSTREAM_UNAVAILABLE')
        return raw


def _number(value):
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise ValueError('INVALID_MARKET_DATA')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('INVALID_MARKET_DATA') from None
    if not result.is_finite():
        raise ValueError('INVALID_MARKET_DATA')
    return result


def _invalid_constant(_):
    raise ValueError('INVALID_MARKET_DATA')


def validate_page(raw, params):
    """Validation only: return original bytes, preserving every Binance value."""
    if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('INVALID_MARKET_DATA')
    rows = json.loads(raw, parse_float=Decimal, parse_constant=_invalid_constant)
    start, end = int(params['startTime']), int(params['endTime'])
    if not isinstance(rows, list) or len(rows) != (end - start + 1) // HOUR:
        raise ValueError('INVALID_MARKET_DATA')
    for index, row in enumerate(rows):
        if (not isinstance(row, list) or len(row) != 12 or type(row[0]) is not int
                or type(row[6]) is not int or row[0] != start + index * HOUR
                or row[6] != row[0] + HOUR - 1):
            raise ValueError('INVALID_MARKET_DATA')
        opening, high, low, close, volume, taker = (_number(row[i]) for i in (1, 2, 3, 4, 5, 9))
        if (min(opening, high, low, close) <= 0 or low > min(opening, close)
                or high < max(opening, close) or low > high or volume < 0 or not 0 <= taker <= volume):
            raise ValueError('INVALID_MARKET_DATA')
    return raw


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'  # one bounded request, no persistent request body

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_):
        pass  # no query, upstream payload, environment or credentials in logs

    def respond(self, status, body):
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self.respond(405 if code == 501 else code, b'{"ok":false}')

    def do_GET(self):
        try:
            target = urlsplit(self.path)
        except ValueError:
            self.respond(400, b'{"ok":false}')
            return
        hosts = self.headers.get_all('Host', [])
        private_hosts = (PRIVATE_HOST, PRIVATE_HOST + ':8080')
        allowed_hosts = private_hosts + (('healthcheck.railway.app',) if self.path == '/health' else ())
        if (len(hosts) != 1 or hosts[0] not in allowed_hosts or target.scheme or target.netloc or target.fragment
                or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0'):
            self.respond(400, b'{"ok":false}')
            return
        if self.path == '/health':
            self.respond(200, b'{"ok":true}')
            return
        if target.path != '/fapi/v1/klines':
            self.respond(404, b'{"ok":false}')
            return
        try:
            params = page_request(target.query, self.server.clock() * 1000)
        except (ValueError, OverflowError):
            self.respond(400, b'{"ok":false}')
            return
        try:
            raw = validate_page(self.server.fetch(params), params)
        except Exception:
            self.respond(502, b'{"ok":false,"error":"MARKET_DATA_UNAVAILABLE"}')
            return
        self.respond(200, raw)


class MarketDataServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, *, fetch=fetch_page, clock=time.time):
        self.fetch, self.clock = fetch, clock
        super().__init__(address, Handler)


class DualStackServer(MarketDataServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def main():
    # IPv4 (0.0.0.0) and IPv6 (::) on the same fixed private service port.
    with DualStackServer(('::', 8080)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
