"""Offline transport equivalence and fail-closed private data gateway contracts.

Only synthetic candles/states. No Railway, Binance, Telegram or account access.
"""
import ast
from contextlib import contextmanager
import copy
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

import numpy as np

import bitman_market_data_service as gateway
from bitman_manual import host, public, render, transport, worker
from bitman_manual.frozen import core
import test_bitman_manual as fixtures

NOW = fixtures.NOW
HOUR = gateway.HOUR
START = NOW // HOUR * HOUR - 10 * HOUR
HOST = gateway.PRIVATE_HOST + ':8080'


def params(count=10, start=START, limit=None):
    return dict(symbol='BTCUSDT', interval='1h', startTime=start,
                endTime=start + count * HOUR - 1, limit=count if limit is None else limit)


def rows_for(p):
    return [[t, '80000.00000000', '80100.00000000', '79900.00000000', '80001.00000000',
             '100.00000000', t + HOUR - 1, '8000000.00000000', 40, '50.00000000', '4000000.00000000', '0']
            for t in range(int(p['startTime']), int(p['endTime']) + 1, HOUR)]


def raw(rows):
    return json.dumps(rows, separators=(', ', ': ')).encode('utf-8')


@contextmanager
def running_server(fetch=None, *, server_class=gateway.MarketDataServer, address=('127.0.0.1', 0)):
    options = dict(clock=lambda: NOW / 1000)
    if fetch is not None:
        options['fetch'] = fetch
    server = server_class(address, **options)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def call(server, path='/health', *, method='GET', headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=3)
    try:
        conn.request(method, path, headers={'Host': HOST} if headers is None else headers)
        response = conn.getresponse()
        return response.status, response.read(), dict(response.getheaders())
    finally:
        conn.close()


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.fetch = Mock(side_effect=lambda p: raw(rows_for(p)))
        self.context = running_server(self.fetch)
        self.server = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def request(self, p=None, **kwargs):
        return call(self.server, '/fapi/v1/klines?' + urlencode(params() if p is None else p), **kwargs)

    def test_health_small_and_no_upstream_work(self):
        self.assertEqual(call(self.server)[:2], (200, b'{"ok":true}'))
        self.assertEqual(call(self.server, headers={'Host': 'healthcheck.railway.app'})[0], 200)
        self.fetch.assert_not_called()

    def test_btcusdt_one_hour_accepted_bytes_unchanged(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body, raw(rows_for(params())))
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(len(json.loads(body)), 10)

    def test_other_symbol_rejected(self):
        self.assertEqual(self.request(dict(params(), symbol='ETHUSDT'))[0], 400)
        self.fetch.assert_not_called()

    def test_other_timeframe_rejected(self):
        self.assertEqual(self.request(dict(params(), interval='15m'))[0], 400)
        self.fetch.assert_not_called()

    def test_unknown_missing_and_duplicate_query_rejected(self):
        for key in ('url', 'host', 'apiKey', 'recvWindow', 'unknown'):
            with self.subTest(key=key):
                self.assertEqual(self.request(dict(params(), **{key: 'unused'}))[0], 400)
        for key in params():
            p = params()
            del p[key]
            self.assertEqual(self.request(p)[0], 400)
        self.assertEqual(call(self.server, '/fapi/v1/klines?' + urlencode(params()) + '&symbol=BTCUSDT')[0], 400)
        self.fetch.assert_not_called()

    def test_limit_bounds_and_truncated_ranges_rejected(self):
        for limit in (0, 1501, -1, '1.0', '1e3', 'NaN', True, '９'):
            with self.subTest(limit=limit):
                self.assertEqual(self.request(dict(params(), limit=limit))[0], 400)
        self.assertEqual(self.request(params(10, limit=9))[0], 400)
        self.fetch.assert_not_called()

    def test_current_open_future_and_unaligned_candles_rejected(self):
        current = NOW // HOUR * HOUR
        for p in (params(1, current), params(1, current + HOUR),
                  dict(params(), startTime=START + 1), dict(params(), endTime=START + HOUR),
                  dict(params(), startTime='-1'), dict(params(), endTime='Infinity')):
            with self.subTest(params=p):
                self.assertEqual(self.request(p)[0], 400)
        self.fetch.assert_not_called()

    def test_last_closed_boundary_and_short_final_page_accepted(self):
        self.assertEqual(self.request(params(1, NOW // HOUR * HOUR - HOUR, limit=1500))[0], 200)
        self.assertEqual(self.request(params(1500, START - 1500 * HOUR))[0], 200)

    def malformed(self, mutate):
        rows = rows_for(params())
        changed = mutate(rows)
        self.fetch.side_effect = None
        self.fetch.return_value = raw(rows if changed is None else changed)
        status, body, _ = self.request()
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body), {'ok': False, 'error': 'MARKET_DATA_UNAVAILABLE'})
        self.assertNotIn(b'80000', body)

    def test_incomplete_response_rejected(self):
        self.malformed(lambda r: r[:-1])

    def test_gap_rejected(self):
        self.malformed(lambda r: r[3].__setitem__(0, r[3][0] + HOUR))

    def test_duplicate_rejected(self):
        self.malformed(lambda r: r.__setitem__(3, r[2]))

    def test_malformed_schema_rejected(self):
        for mutate in (lambda r: r[0].pop(), lambda r: r[0].append('extra'),
                       lambda r: {'code': -1}, lambda r: r[0].__setitem__(0, str(r[0][0])),
                       lambda r: r[0].__setitem__(6, True)):
            with self.subTest(mutate=mutate):
                self.malformed(mutate)

    def test_bad_close_time_and_open_response_rejected(self):
        self.malformed(lambda r: r[0].__setitem__(6, r[0][6] + 1))
        self.malformed(lambda r: r[-1].__setitem__(0, NOW // HOUR * HOUR))

    def test_invalid_ohlc_base_and_taker_volume_rejected(self):
        for index, value in ((1, '0'), (2, '1'), (3, '90000'), (4, 'NaN'), (4, 'Infinity'),
                             (5, '-1'), (9, '101'), (9, '-1'), (9, None), (4, True)):
            with self.subTest(index=index, value=value):
                self.malformed(lambda r: r[0].__setitem__(index, value))

    def test_upstream_timeout_or_exception_never_echoed(self):
        for failure in (TimeoutError('private diagnostic'), OSError('private diagnostic')):
            self.fetch.side_effect = failure
            status, body, _ = self.request()
            self.assertEqual(status, 502)
            self.assertNotIn(b'private diagnostic', body)

    def test_other_methods_paths_urls_hosts_and_bodies_rejected(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'CONNECT', 'TRACE'):
            with self.subTest(method=method):
                self.assertEqual(self.request(method=method)[0], 405)
        for path in ('/fapi/v1/order', '/fapi/v2/account', '/health?x=1', '/', '/fapi/v1/klines/'):
            self.assertEqual(call(self.server, path)[0], 404)
        for path in ('https://fapi.binance.com/fapi/v1/klines', 'http://['):
            self.assertEqual(call(self.server, path)[0], 400)
        # BaseHTTPRequestHandler collapses the leading // before routing; still no upstream call.
        self.assertEqual(call(self.server, '//other/fapi/v1/klines')[0], 404)
        for headers in ({'Host': 'other'}, {'Host': 'healthcheck.railway.app'},
                        {'Host': HOST, 'Content-Length': '1'}, {'Host': HOST, 'Transfer-Encoding': 'chunked'}):
            self.assertEqual(self.request(headers=headers)[0], 400)
        self.fetch.assert_not_called()

    @unittest.skipUnless(socket.has_dualstack_ipv6(), 'Dual-stack sockets unavailable locally')
    def test_private_ipv6_and_ipv4_share_the_listener(self):
        with running_server(self.fetch, server_class=gateway.DualStackServer, address=('::', 0)) as server:
            self.assertEqual(call(server)[0], 200)
            conn = http.client.HTTPConnection('::1', server.server_address[1], timeout=3)
            try:
                conn.request('GET', '/health', headers={'Host': HOST})
                self.assertEqual(conn.getresponse().status, 200)
            finally:
                conn.close()


class UpstreamTests(unittest.TestCase):
    def response(self, status=200, content=b'[]'):
        response = Mock(status=status)
        response.read.return_value = content
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_fixed_https_no_environment_proxy_and_bounded_timeout(self):
        response = self.response(content=raw(rows_for(params())))
        opener = Mock()
        opener.open.return_value = response
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://untrusted', 'HTTPS_PROXY': 'http://untrusted'}), \
             patch.object(gateway.http, 'build_opener', return_value=opener) as build:
            self.assertEqual(gateway.fetch_page(params()), raw(rows_for(params())))
        proxy, redirect = build.call_args.args
        self.assertEqual(proxy.proxies, {})
        self.assertIsInstance(redirect, gateway.NoRedirect)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, gateway.UPSTREAM + '?' + urlencode(params()))
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(opener.open.call_args.kwargs, {'timeout': 4})
        response.read.assert_called_once_with(gateway.MAX_RESPONSE_BYTES + 1)
        response.__exit__.assert_called_once()

    def test_non_200_fails_closed(self):
        for status in (301, 302, 307, 403, 429, 451, 500):
            opener = Mock()
            opener.open.return_value = self.response(status)
            with self.subTest(status=status), patch.object(gateway.http, 'build_opener', return_value=opener), \
                 self.assertRaisesRegex(ValueError, 'UPSTREAM_UNAVAILABLE'):
                gateway.fetch_page(params())

    def test_timeout_fails_closed(self):
        opener = Mock()
        opener.open.side_effect = TimeoutError
        with patch.object(gateway.http, 'build_opener', return_value=opener), self.assertRaises(TimeoutError):
            gateway.fetch_page(params())

    def test_redirect_handler_never_follows_location(self):
        handler = gateway.NoRedirect()
        for destination in ('https://other', 'http://127.0.0.1', 'https://fapi.binance.com/fapi/v1/order'):
            self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, destination))
        opener = Mock()
        opener.open.side_effect = HTTPError(gateway.UPSTREAM, 302, 'redirect', {}, None)
        with patch.object(gateway.http, 'build_opener', return_value=opener), self.assertRaises(HTTPError):
            gateway.fetch_page(params())
        self.assertEqual(opener.open.call_count, 1)

    def test_oversize_invalid_json_and_non_list_fail_closed(self):
        opener = Mock()
        opener.open.return_value = self.response(content=b'x' * (gateway.MAX_RESPONSE_BYTES + 1))
        with patch.object(gateway.http, 'build_opener', return_value=opener), self.assertRaises(ValueError):
            gateway.fetch_page(params())
        for body in (b'not json', b'{}', b'null', b'[]'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                gateway.validate_page(body, params())
        for value in (float('nan'), float('inf'), float('-inf')):
            rows = rows_for(params())
            rows[0][11] = value  # non-standard JSON is rejected even in unused columns
            with self.assertRaises(ValueError):
                gateway.validate_page(raw(rows), params())

    def test_upstream_has_no_url_parameter_or_trading_imports(self):
        with self.assertRaises(TypeError):
            gateway.fetch_page(params(), url='https://other')
        source = Path(gateway.__file__).read_text('utf-8')
        imports = {n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)}
        imports |= {alias.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for alias in n.names}
        self.assertEqual(imports, {'decimal', 'http.server', 'json', 'socket', 'time', 'urllib', 'urllib.parse'})


class ControlledTransportTests(unittest.TestCase):
    def test_worker_accepts_only_exact_official_or_private_url(self):
        for url in (transport.OFFICIAL_URL, transport.PRIVATE_URL):
            with self.subTest(url=url), patch.object(worker, 'fetch_closed', return_value=fixtures.prices(7218)) as fetch, \
                 patch.object(worker, 'read_current', return_value=({}, {})):
                self.assertTrue(worker.calculate(dict(mlrsi_state_path='unused', public_cache=None,
                                                     market_data_url=url), NOW)['ok'])
                fetch.assert_called_once_with(NOW, None, url=url)

    def test_arbitrary_or_lookalike_host_never_fetches_even_with_cache(self):
        for url in ('http://127.0.0.1:8080/fapi/v1/klines', transport.PRIVATE_URL + '?url=other',
                    transport.OFFICIAL_URL + '#fragment', transport.PRIVATE_URL.replace(':8080', ':80'),
                    transport.PRIVATE_URL.replace('http:', 'https:'),
                    transport.PRIVATE_URL.replace('bitman-market-data.', 'other.'),
                    transport.PRIVATE_URL.replace('http://', 'http://user:pass@'), '', None):
            with self.subTest(url=url), patch.object(worker, 'fetch_closed') as fetch:
                for cache in (None, fixtures.snapshot()):
                    with self.assertRaisesRegex(ValueError, 'INVALID_MARKET_DATA_URL'):
                        worker.calculate(dict(mlrsi_state_path='unused', public_cache=cache, market_data_url=url), NOW)
                fetch.assert_not_called()
                with self.assertRaisesRegex(ValueError, 'INVALID_MARKET_DATA_URL'):
                    public.fetch_closed(NOW, url=url)

    def test_child_receives_only_controlled_nonsecret_url_in_json(self):
        child = Mock(returncode=0)
        child.communicate.return_value = (json.dumps(dict(ok=True, snapshot=fixtures.snapshot(),
                                                        public_cache=fixtures.snapshot())), '')
        instance = host.BitmanHost(resolve_state=lambda: Path('unused'), wall=lambda: NOW / 1000)
        self.addCleanup(instance.stop)
        secret_environment = dict(TELEGRAM_BOT_TOKEN='secret-canary', BITUNIX_API_KEY='secret-canary',
                                 BINANCE_API_KEY='secret-canary', HTTPS_PROXY='secret-canary',
                                 BITMAN_MARKET_DATA_URL=transport.PRIVATE_URL)
        with patch.dict(os.environ, secret_environment), patch.object(host.subprocess, 'Popen', return_value=child) as popen:
            reply = Mock()
            instance._run(reply)
        env = popen.call_args.kwargs['env']
        self.assertNotIn('secret-canary', json.dumps(env))
        self.assertTrue(set(env) <= {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP',
                                    'PYTHONIOENCODING', 'PYTHONDONTWRITEBYTECODE'})
        self.assertNotIn(transport.MARKET_DATA_ENV, env)
        request = json.loads(child.communicate.call_args.args[0])
        self.assertEqual(set(request), {'mlrsi_state_path', 'public_cache', 'market_data_url'})
        self.assertEqual(request['market_data_url'], transport.PRIVATE_URL)
        self.assertEqual(host.CACHE_SECONDS, 30)
        reply.assert_called_once_with(render.render(fixtures.snapshot()))

    def test_invalid_parent_config_fails_without_starting_child(self):
        instance = host.BitmanHost(resolve_state=lambda: Path('unused'))
        with patch.dict(os.environ, {transport.MARKET_DATA_ENV: 'https://other'}), \
             patch.object(host.subprocess, 'Popen') as popen:
            reply = Mock()
            instance._run(reply)
        popen.assert_not_called()
        reply.assert_called_once_with(render.unavailable())

    def test_private_failure_has_no_official_fallback(self):
        for status in (302, 451, 502):
            client = fixtures.FakePublic(status=status)
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'PUBLIC_MARKET_UNAVAILABLE'):
                worker.calculate(dict(mlrsi_state_path='unused', public_cache=None,
                                      market_data_url=transport.PRIVATE_URL), NOW, client)
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(client.calls[0][0], transport.PRIVATE_URL)


class EquivalenceTests(unittest.TestCase):
    def test_host_worker_private_gateway_matches_direct_prepared_input_snapshot_and_output(self):
        """Full 300-day, five-page fixture through an actual loopback HTTP server."""
        bars = fixtures.prices(7218)
        by_time = {int(row[0]): [int(row[0]), *[repr(float(v)) for v in row[1:6]],
                    int(row[0]) + HOUR - 1, '0', 40, repr(float(row[6])), '0', '0'] for row in bars}
        calls, results, prepared, fetched = {}, [], [], []
        original_prepare, original_fetch = core.prepare, public.fetch_closed

        def body(p):
            return raw([by_time[t] for t in range(int(p['startTime']), int(p['endTime']) + 1, HOUR)])

        def upstream(req, *, timeout):
            self.assertEqual(urlsplit(req.full_url)._replace(query='').geturl(), gateway.UPSTREAM)
            p = {k: v[0] for k, v in parse_qs(urlsplit(req.full_url).query).items()}
            return UpstreamTests().response(content=body(p))

        def prepare(data, now):
            result = original_prepare(data, now)
            prepared.append(copy.deepcopy(result))
            return result

        def fetch(*args, **kwargs):
            result = original_fetch(*args, **kwargs)
            fetched.append(result.copy())
            return result

        with tempfile.TemporaryDirectory() as tmp, running_server() as server:
            state = Path(tmp) / 'state.json'
            state.write_text(json.dumps(fixtures.ml_export()), encoding='utf-8')
            state_before = state.read_bytes()
            for selected in (transport.OFFICIAL_URL, transport.PRIVATE_URL):
                calls[selected] = []

                class Client:
                    trust_env = True

                    def get(self, url, *, params, timeout, allow_redirects):
                        self_outer.assertEqual(url, selected)
                        self_outer.assertEqual(timeout, (3, 5))
                        self_outer.assertFalse(allow_redirects)
                        calls[selected].append(copy.deepcopy(params))
                        if selected == transport.PRIVATE_URL:
                            status, payload, _ = call(server, '/fapi/v1/klines?' + urlencode(params))
                        else:
                            status, payload = 200, body(params)
                        return Mock(status_code=status, json=lambda: json.loads(payload))

                self_outer = self
                client = Client()
                child = Mock(returncode=0)

                def communicate(payload, *, timeout):
                    self.assertEqual(timeout, 25)
                    result = worker.calculate(json.loads(payload), NOW, client)
                    results.append(copy.deepcopy(result))
                    return json.dumps(result, allow_nan=False), ''

                child.communicate.side_effect = communicate
                opener = Mock()
                opener.open.side_effect = upstream
                instance = host.BitmanHost(resolve_state=lambda: state, wall=lambda: NOW / 1000)
                try:
                    with patch.dict(os.environ, {transport.MARKET_DATA_ENV: selected}), \
                         patch.object(host.subprocess, 'Popen', return_value=child), \
                         patch.object(worker, 'fetch_closed', side_effect=fetch), \
                         patch.object(core, 'prepare', side_effect=prepare), \
                         patch.object(gateway.http, 'build_opener', return_value=opener):
                        reply = Mock()
                        instance._run(reply)
                    reply.assert_called_once_with(render.render(results[-1]['snapshot']))
                    self.assertNotEqual(reply.call_args.args[0], render.unavailable())
                    self.assertFalse(client.trust_env)
                    if selected == transport.PRIVATE_URL:
                        self.assertEqual(opener.open.call_count, 5)
                    else:
                        opener.open.assert_not_called()
                finally:
                    instance.stop()
            self.assertEqual(state.read_bytes(), state_before)
        self.assertEqual((public.HISTORY_DAYS, public.PAGE_SIZE), (300, 1500))
        self.assertEqual(calls[transport.OFFICIAL_URL], calls[transport.PRIVATE_URL])
        expected_start = NOW // (24 * HOUR) * (24 * HOUR) - 300 * 24 * HOUR
        self.assertEqual(len(calls[transport.PRIVATE_URL]), 5)
        for index, p in enumerate(calls[transport.PRIVATE_URL]):
            self.assertEqual(p, params(min(1500, 7218 - index * 1500), expected_start + index * 1500 * HOUR, 1500))
        self.assertEqual(fetched[0].shape, (7218, 7))
        np.testing.assert_array_equal(fetched[0], bars)
        np.testing.assert_array_equal(fetched[0], fetched[1])
        self.assert_nested_equal(prepared[0], prepared[1])
        self.assertEqual(results[0], results[1])
        self.assertEqual(render.render(results[0]['snapshot']), render.render(results[1]['snapshot']))

    def assert_nested_equal(self, one, two):
        if isinstance(one, np.ndarray):
            np.testing.assert_equal(one, two)
        elif isinstance(one, dict):
            self.assertEqual(set(one), set(two))
            for key in one:
                self.assert_nested_equal(one[key], two[key])
        else:
            self.assertEqual(one, two)


if __name__ == '__main__':
    unittest.main()
