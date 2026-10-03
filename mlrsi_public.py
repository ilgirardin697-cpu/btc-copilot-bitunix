"""Only Binance market-data GET klines. No account/client/secrets dependency."""
from pathlib import Path
import json
import math
import os
import requests
from mlrsi_math import TIMEFRAMES

URL = 'https://data-api.binance.vision/api/v3/klines'
WARMUP_BARS = 3232


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, allow_nan=False, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # directory fsync unsupported on some Windows/filesystem combinations


def validate_candles(rows, timeframe, now_ms):
    interval = TIMEFRAMES[timeframe]
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'time', 'open', 'high', 'low', 'close'}:
            raise ValueError('MLRSI_CANDLE_SCHEMA_INVALID')
        p = {k: float(v) for k, v in row.items()}
        if (not all(math.isfinite(v) for v in p.values()) or p['time'] % interval or p['time'] > now_ms
                or p['low'] <= 0 or p['low'] > min(p['open'], p['close'])
                or p['high'] < max(p['open'], p['close'])):
            raise ValueError('MLRSI_CANDLE_INVALID')
        stamp = int(p['time'])
        if stamp in seen:
            raise ValueError('MLRSI_CANDLE_DUPLICATE')
        seen.add(stamp)
        p['time'] = stamp
        result.append(p)
    return sorted(result, key=lambda p: p['time'])


class PublicHistory:
    """Bounded initial pagination, then incremental updates (including open bar).

    Stores price cache separately from RSI carry state; never mixes Bitunix
    Analyzer frames with Binance spot. A network failure doesn't reuse a cache
    as if it were freshly verified current market data.
    """
    def __init__(self, folder, transport=None):
        self.folder = Path(folder)
        self.http = transport or requests.Session()
        if transport is None:
            self.http.trust_env = False  # no implicit netrc credentials
        self.cache = {}
        self.verified_at = {}

    def _load(self, tf):
        if tf in self.cache:
            return
        path = self.folder / ('igod_mlrsi_cache_' + tf + '.json')
        try:
            stored = json.loads(path.read_text('utf-8'))
            if stored['venue'] != 'BINANCE_SPOT' or stored['symbol'] != 'BTCUSDT':
                raise ValueError('MLRSI_CACHE_SCOPE_INVALID')
            self.cache[tf] = stored['candles']
            self.verified_at[tf] = stored.get('verified_at', 0)
        except FileNotFoundError:
            self.cache[tf] = []
        except (ValueError, KeyError, TypeError):
            self.cache[tf] = []  # fresh public bootstrap; never trust a corrupt cache

    def fetch(self, tf, now_ms):
        if tf not in TIMEFRAMES:
            raise ValueError('MLRSI_TIMEFRAME_INVALID')
        self._load(tf)
        cached = validate_candles(self.cache[tf], tf, now_ms)
        rows = []
        params = dict(symbol='BTCUSDT', interval=tf, limit=1000, endTime=int(now_ms))
        if len(cached) >= WARMUP_BARS:
            params['startTime'] = int(cached[-1]['time'])  # refresh open or last closed candle
        # At most four requests for bootstrap, eight after a long offline gap.
        for _ in range(8):
            response = self.http.get(URL, params=params, timeout=(2, 5), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('MLRSI_PUBLIC_UNAVAILABLE')
            page = response.json()
            if not isinstance(page, list) or not page:
                raise ValueError('MLRSI_PUBLIC_INCOMPLETE')
            converted = [dict(time=r[0], open=r[1], high=r[2], low=r[3], close=r[4]) for r in page]
            converted = validate_candles(converted, tf, now_ms)
            rows.extend(converted)
            if 'startTime' in params:
                if len(page) < 1000 or converted[-1]['time'] + TIMEFRAMES[tf] > now_ms:
                    break
                cursor = converted[-1]['time'] + TIMEFRAMES[tf]
                if cursor <= params['startTime']:
                    raise ValueError('MLRSI_PUBLIC_NO_PROGRESS')
                params['startTime'] = cursor
            else:
                if len(rows) >= WARMUP_BARS:
                    break
                end = converted[0]['time'] - 1
                if end >= params['endTime'] or len(page) < 1000:
                    raise ValueError('MLRSI_HISTORY_INSUFFICIENT')
                params['endTime'] = end
        merged = {r['time']: r for r in cached}
        for row in rows:
            previous = merged.get(row['time'])
            if previous is not None and previous != row and row['time'] + TIMEFRAMES[tf] <= self.verified_at.get(tf, 0):
                raise ValueError('MLRSI_CLOSED_CANDLE_REVISED')
        merged.update({r['time']: r for r in rows})
        combined = validate_candles(list(merged.values()), tf, now_ms)
        closed = [r for r in combined if r['time'] + TIMEFRAMES[tf] <= now_ms]
        if len(closed) < WARMUP_BARS or closed[-1]['time'] + TIMEFRAMES[tf] <= now_ms - TIMEFRAMES[tf]:
            raise ValueError('MLRSI_HISTORY_STALE_OR_INSUFFICIENT')
        # Persist only after a successful fresh public response.
        self.cache[tf] = combined[-(WARMUP_BARS + 100):]
        self.verified_at[tf] = int(now_ms)
        atomic_json(self.folder / ('igod_mlrsi_cache_' + tf + '.json'),
                    dict(venue='BINANCE_SPOT', symbol='BTCUSDT', verified_at=int(now_ms), candles=self.cache[tf]))
        return combined
