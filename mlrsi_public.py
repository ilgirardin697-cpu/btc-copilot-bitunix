"""Only Binance market-data GET klines. No account/client/secrets dependency."""
from pathlib import Path
import json
import math
import os
import uuid
import requests
from mlrsi_math import TIMEFRAMES

URL = 'https://data-api.binance.vision/api/v3/klines'
WARMUP_BARS = 3232
CLOSED_GRACE_MS = 120000
ERROR_CODES = frozenset({
    'MLRSI_CANDLE_SCHEMA_INVALID', 'MLRSI_CANDLE_INVALID', 'MLRSI_CANDLE_DUPLICATE',
    'MLRSI_TIMEFRAME_INVALID', 'MLRSI_PUBLIC_INCOMPLETE', 'MLRSI_PUBLIC_NO_PROGRESS',
    'MLRSI_HISTORY_INSUFFICIENT', 'MLRSI_HISTORY_STALE_OR_INSUFFICIENT',
    'MLRSI_HISTORY_GAP', 'MLRSI_CLOSED_CANDLE_REVISED', 'MLRSI_JSON_INVALID',
    'MLRSI_CACHE_INVALID', 'MLRSI_CACHE_READ_ERROR', 'MLRSI_CACHE_WRITE_ERROR',
    'MLRSI_TIMEOUT', 'MLRSI_NETWORK_ERROR', 'MLRSI_PUBLIC_BACKOFF',
})


def public_error_code(error):
    """Only known static codes or a bounded HTTP status; never exception text."""
    if isinstance(error, requests.Timeout):
        return 'MLRSI_TIMEOUT'
    if isinstance(error, requests.RequestException):
        return 'MLRSI_NETWORK_ERROR'
    code = error.args[0] if isinstance(error, ValueError) and error.args else None
    if isinstance(code, str):
        if code in ERROR_CODES:
            return code
        if code.startswith('HTTP_') and len(code) == 8 and code[5:].isdigit() and 100 <= int(code[5:]) <= 599:
            return code
    return 'MLRSI_PUBLIC_ERROR'


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
    def __init__(self, folder, transport=None, logger=print):
        self.folder = Path(folder)
        self.http = transport or requests.Session()
        if transport is None:
            self.http.trust_env = False  # no implicit netrc credentials
        self.cache = {}
        self.verified_at = {}
        self.generations = {}
        self.epochs = {}
        self.retry_at = {}
        self.log = logger

    def generation(self, tf):
        return self.generations.get(tf, 0)

    def epoch(self, tf):
        return self.epochs.get(tf)

    def _path(self, tf):
        return self.folder / ('igod_mlrsi_cache_' + tf + '.json')

    def _write(self, tf, rows, verified_at, generation):
        try:
            atomic_json(self._path(tf), dict(venue='BINANCE_SPOT', symbol='BTCUSDT',
                        verified_at=verified_at, generation=generation, epoch=self.epochs[tf], candles=rows))
        except (OSError, ValueError, TypeError):
            raise ValueError('MLRSI_CACHE_WRITE_ERROR') from None

    def reset(self, tf, code='MLRSI_HISTORY_GAP'):
        """Durable per-TF tombstone: next fetch bootstraps instead of retrying poison.

        Generation tells the observer to rebuild only public math carry silently.
        Even if disk fails, RAM forgets the bad cache; no fresh success is returned.
        """
        self.log('MLRSI_PUBLIC_REBOOTSTRAP ' + tf + ' ' + (code if code in ERROR_CODES else 'MLRSI_CACHE_INVALID'))
        self.cache[tf], self.verified_at[tf] = [], 0
        self.generations[tf] = self.generation(tf) + 1
        self.epochs[tf] = uuid.uuid4().hex
        self._write(tf, [], 0, self.generation(tf))

    def _load(self, tf, now_ms):
        if tf in self.cache:
            return
        path = self._path(tf)
        try:
            stored = json.loads(path.read_text('utf-8'))
            if stored['venue'] != 'BINANCE_SPOT' or stored['symbol'] != 'BTCUSDT':
                raise ValueError('MLRSI_CACHE_SCOPE_INVALID')
            verified, generation = stored.get('verified_at', 0), stored.get('generation', 0)
            if (type(verified) is not int or not 0 <= verified <= now_ms or type(generation) is not int or generation < 0):
                raise ValueError('MLRSI_CACHE_INVALID')
            self.cache[tf] = validate_candles(stored['candles'], tf, now_ms)
            self.verified_at[tf], self.generations[tf] = verified, generation
            epoch = stored.get('epoch', uuid.uuid4().hex)
            if not isinstance(epoch, str) or len(epoch) != 32 or any(c not in '0123456789abcdef' for c in epoch):
                raise ValueError('MLRSI_CACHE_INVALID')
            self.epochs[tf] = epoch
        except FileNotFoundError:
            self.cache[tf] = []
            self.epochs[tf] = uuid.uuid4().hex
        except OSError:
            raise ValueError('MLRSI_CACHE_READ_ERROR') from None
        except (ValueError, KeyError, TypeError, OverflowError):
            self.reset(tf, 'MLRSI_CACHE_INVALID')

    def _page(self, tf, params, now_ms):
        response = self.http.get(URL, params=dict(params), timeout=(2, 5), allow_redirects=False)
        if response.status_code != 200:
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                self.retry_at[tf] = now_ms + 30000  # bounded per-TF, no retry loop
            raise ValueError('HTTP_' + str(response.status_code))
        try:
            page = response.json()
        except (ValueError, TypeError):
            raise ValueError('MLRSI_JSON_INVALID') from None
        if not isinstance(page, list) or not page:
            raise ValueError('MLRSI_PUBLIC_INCOMPLETE')
        if any(not isinstance(r, (list, tuple)) or len(r) < 5 for r in page):
            raise ValueError('MLRSI_CANDLE_SCHEMA_INVALID')
        try:
            rows = validate_candles([dict(time=r[0], open=r[1], high=r[2], low=r[3], close=r[4]) for r in page], tf, now_ms)
        except (ValueError, TypeError, OverflowError) as error:
            if public_error_code(error) in ERROR_CODES:
                raise
            raise ValueError('MLRSI_CANDLE_SCHEMA_INVALID') from None
        return rows, len(page)

    def fetch(self, tf, now_ms):
        if tf not in TIMEFRAMES:
            raise ValueError('MLRSI_TIMEFRAME_INVALID')
        if now_ms < self.retry_at.get(tf, 0):
            raise ValueError('MLRSI_PUBLIC_BACKOFF')
        self._load(tf, now_ms)
        self.epochs.setdefault(tf, uuid.uuid4().hex)
        try:
            cached = validate_candles(self.cache[tf], tf, now_ms)
        except (ValueError, TypeError, OverflowError):
            self.reset(tf, 'MLRSI_CACHE_INVALID')
            cached = []
        interval = TIMEFRAMES[tf]
        # More than the incremental request budget: abandon the gap explicitly.
        if cached and now_ms - cached[-1]['time'] >= 7000 * interval:
            self.reset(tf, 'MLRSI_HISTORY_GAP')
            cached = []
        rows = []
        params = dict(symbol='BTCUSDT', interval=tf, limit=1000, endTime=int(now_ms))
        if len(cached) >= WARMUP_BARS:
            # Recheck the prior closed candle even when the new open is present.
            params['startTime'] = max(cached[0]['time'], cached[-1]['time'] - interval)
        # At most four requests for bootstrap, eight after a long offline gap.
        for _ in range(8):
            converted, page_size = self._page(tf, params, now_ms)
            rows.extend(converted)
            if 'startTime' in params:
                if page_size < 1000 or converted[-1]['time'] + interval > now_ms:
                    break
                cursor = converted[-1]['time'] + TIMEFRAMES[tf]
                if cursor <= params['startTime']:
                    raise ValueError('MLRSI_PUBLIC_NO_PROGRESS')
                params['startTime'] = cursor
            else:
                if len(rows) >= WARMUP_BARS:
                    break
                end = converted[0]['time'] - 1
                if end >= params['endTime'] or page_size < 1000:
                    raise ValueError('MLRSI_HISTORY_INSUFFICIENT')
                params['endTime'] = end
        merged = {r['time']: r for r in cached}
        revised_closed = False
        for row in rows:
            previous = merged.get(row['time'])
            if previous is not None and previous != row and row['time'] + interval <= self.verified_at.get(tf, 0):
                if now_ms - (row['time'] + interval) > CLOSED_GRACE_MS:
                    self.reset(tf, 'MLRSI_CLOSED_CANDLE_REVISED')
                    raise ValueError('MLRSI_CLOSED_CANDLE_REVISED')
                revised_closed = True
                self.log('MLRSI_RECENT_CANDLE_FINALIZED ' + tf)
        merged.update({r['time']: r for r in rows})
        combined = validate_candles(list(merged.values()), tf, now_ms)
        if any(b['time'] - a['time'] != interval for a, b in zip(combined, combined[1:])):
            self.reset(tf, 'MLRSI_HISTORY_GAP')
            raise ValueError('MLRSI_HISTORY_GAP')
        closed = [r for r in combined if r['time'] + TIMEFRAMES[tf] <= now_ms]
        if len(closed) < WARMUP_BARS or closed[-1]['time'] + TIMEFRAMES[tf] <= now_ms - TIMEFRAMES[tf]:
            if cached:
                self.reset(tf, 'MLRSI_HISTORY_STALE_OR_INSUFFICIENT')
            raise ValueError('MLRSI_HISTORY_STALE_OR_INSUFFICIENT')
        # Persist only after a successful fresh public response.
        next_cache = combined[-(WARMUP_BARS + 100):]
        generation = self.generation(tf) + int(revised_closed)
        self._write(tf, next_cache, int(now_ms), generation)
        self.cache[tf] = next_cache
        self.generations[tf] = generation
        self.verified_at[tf] = int(now_ms)
        return combined
