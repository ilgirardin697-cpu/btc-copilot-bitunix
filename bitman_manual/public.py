"""Bounded, credential-free public USD-M klines, requested only by /bitman."""
import numpy as np
import requests
from .frozen.constants import HOUR
from .frozen.market import validate
from .transport import OFFICIAL_URL, validate_market_url

URL = OFFICIAL_URL
HISTORY_DAYS = 300  # transport warmup, not an engine threshold or fitted parameter
PAGE_SIZE = 1500


def fetch_closed(now_ms, transport=None, *, url=URL):
    url = validate_market_url(url)
    stop = int(now_ms) // HOUR * HOUR
    start = stop // (24 * HOUR) * (24 * HOUR) - HISTORY_DAYS * 24 * HOUR
    session = transport if transport is not None else requests.Session()
    session.trust_env = False
    rows = []
    cursor = start
    try:
        while cursor < stop:
            end = min(stop, cursor + PAGE_SIZE * HOUR)
            response = session.get(url, params=dict(symbol='BTCUSDT', interval='1h', startTime=cursor,
                endTime=end - 1, limit=PAGE_SIZE), timeout=(3, 5), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('PUBLIC_MARKET_UNAVAILABLE')
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != (end - cursor) // HOUR:
                raise ValueError('PUBLIC_MARKET_INCOMPLETE')
            for index, row in enumerate(payload):
                if not isinstance(row, list) or len(row) != 12 or type(row[0]) is not int or type(row[6]) is not int:
                    raise ValueError('PUBLIC_MARKET_SCHEMA')
                if row[0] != cursor + index * HOUR or row[6] != row[0] + HOUR - 1:
                    raise ValueError('PUBLIC_MARKET_TIME')
                rows.append([row[0], *[float(row[i]) for i in (1, 2, 3, 4, 5, 9)]])
            cursor = end
        return validate(np.asarray(rows, float))
    finally:
        if transport is None:
            session.close()
