"""Allowlisted public Binance USD-M GETs only; never uses account credentials."""
import hashlib
import json
import math
import time

import requests

BASE = 'https://fapi.binance.com'
VENUE = 'BINANCE_USDM_PERPETUAL'
STEPS = {'5m': 300_000, '15m': 900_000, '1h': 3_600_000, '4h': 14_400_000}


class DataError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_rows(rows, interval, start, end):
    step = STEPS[interval]
    if not isinstance(rows, list) or len(rows) != (end - start) // step:
        raise DataError('MARKET_INCOMPLETE')
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 12:
            raise DataError('MARKET_SCHEMA')
        if type(row[0]) is not int or type(row[6]) is not int or row[0] != start + i * step or row[6] != row[0] + step - 1:
            raise DataError('MARKET_TIME_OR_GAP')
        try:
            o, h, l, c, v, buy = [float(row[k]) for k in (1, 2, 3, 4, 5, 9)]
        except (ValueError, TypeError, OverflowError):
            raise DataError('MARKET_NUMERIC') from None
        if not all(math.isfinite(x) for x in (o, h, l, c, v, buy)) or not 0 < l <= min(o, c) <= max(o, c) <= h or not 0 <= buy <= v:
            raise DataError('MARKET_VALUES')
    return rows


class PublicMarket:
    def __init__(self, session=None, clock=time.time):
        self.http = session or requests.Session()
        self.http.trust_env = False
        self.http.headers.clear()
        self.http.auth = None
        self.clock = clock

    def _get(self, path, params):
        if path not in ('/fapi/v1/klines', '/fapi/v1/fundingRate') or params.get('symbol') != 'BTCUSDT':
            raise DataError('PUBLIC_ENDPOINT_DENIED')
        response = self.http.get(BASE + path, params=params, timeout=(3, 10), allow_redirects=False)
        if response.status_code != 200:
            raise DataError('PUBLIC_HTTP_' + str(response.status_code))
        try:
            value = response.json()
        except ValueError:
            raise DataError('PUBLIC_JSON') from None
        if not isinstance(value, list):
            raise DataError('PUBLIC_SCHEMA')
        return value

    def candles(self, interval, start, end):
        if interval not in STEPS or type(start) is not int or type(end) is not int:
            raise DataError('PUBLIC_REQUEST')
        step = STEPS[interval]
        if start < 0 or start % step or end % step or end <= start or end > int(self.clock() * 1000) // step * step or (end - start) // step > 10_000:
            raise DataError('PUBLIC_RANGE_OR_OPEN_CANDLE')
        rows = []
        for page_start in range(start, end, 1500 * step):
            page_end = min(end, page_start + 1500 * step)
            page = self._get('/fapi/v1/klines', {'symbol': 'BTCUSDT', 'interval': interval,
                            'startTime': page_start, 'endTime': page_end - 1,
                            'limit': (page_end - page_start) // step})
            rows.extend(validate_rows(page, interval, page_start, page_end))
        return validate_rows(rows, interval, start, end)

    def history(self, interval, count, cutoff):
        end = cutoff // STEPS[interval] * STEPS[interval]
        return self.candles(interval, end - count * STEPS[interval], end)

    def funding(self, start, end):
        if end > int(self.clock() * 1000) or end - start != STEPS['5m']:
            raise DataError('FUNDING_RANGE')
        rows = self._get('/fapi/v1/fundingRate', {'symbol': 'BTCUSDT', 'startTime': start, 'endTime': end - 1, 'limit': 1000})
        if len(rows) >= 1000:
            raise DataError('FUNDING_TRUNCATED')
        times = []
        for row in rows:
            try:
                stamp, rate, price = row['fundingTime'], float(row['fundingRate']), float(row['markPrice'])
                if row['symbol'] != 'BTCUSDT' or type(stamp) is not int or not start <= stamp < end or not math.isfinite(rate) or not math.isfinite(price) or price <= 0:
                    raise ValueError
            except (TypeError, ValueError, KeyError):
                raise DataError('FUNDING_INVALID') from None
            times.append(stamp)
        if times != sorted(set(times)):
            raise DataError('FUNDING_DUPLICATE')
        return rows
