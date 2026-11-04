"""Offline official archive input. Never downloads, repairs or imputes a row."""
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import numpy as np

from .reference_geometry import ATR14, Candle, HOUR, project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MINUTE = 60_000
NY = ZoneInfo('America/New_York')


def read_json(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def iso(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).isoformat().replace('+00:00', 'Z')


def stamp(s):
    return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000)


def wall(day, hour):
    local = datetime.combine(day, datetime.min.time()).replace(hour=hour, tzinfo=NY)
    t = int(local.timestamp() * 1000)
    if datetime.fromtimestamp(t / 1000, NY).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError('DST_MISSING_LOCAL_HOUR')
    return t


def schedule(day):
    return dict(asia=wall(day - timedelta(days=1), 20), asia_end=wall(day, 0),
                london=wall(day, 2), freeze=wall(day, 6), expiry=wall(day, 20) - MINUTE)


def validate_rows(a, start, end, step):
    if a.ndim != 2 or a.shape[1] != 5 or end <= start or (end - start) % step:
        raise ValueError('SCHEMA_OR_RANGE')
    if len(a) != (end - start) // step or not np.array_equal(a[:, 0], np.arange(start, end, step)):
        raise ValueError('GAP_DUPLICATE_OR_INCOMPLETE')
    if (not np.isfinite(a).all() or (a[:, 1:] <= 0).any()
            or (a[:, 3] > np.minimum(a[:, 1], a[:, 4])).any()
            or (a[:, 2] < np.maximum(a[:, 1], a[:, 4])).any()):
        raise ValueError('INVALID_OHLC')
    return a


def window(a, start, end):
    lo, hi = np.searchsorted(a[:, 0], [start, end])
    return a[lo:hi]


def load_interval(cache, interval):
    frozen = read_json('freeze_manifest.json')['cached_public_archives'][interval]
    cache = Path(cache)
    manifest_bytes = (cache / f'manifest_{interval}.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != frozen['manifest_sha256']:
        raise ValueError('INPUT_MANIFEST_CHANGED')
    step = HOUR if interval == '1h' else MINUTE
    batches = []
    for record in frozen['manifest']['archives']:
        raw = (cache / record['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('PUBLIC_ARCHIVE_HASH_CHANGED')
        rows = []
        with ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.namelist()) != 1:
                raise ValueError('ARCHIVE_SCHEMA')
            with archive.open(archive.namelist()[0]) as stream:
                for r in csv.reader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')):
                    if len(r) != 12:
                        raise ValueError('NOT_12_COLUMNS')
                    opened, closed = int(r[0]), int(r[6])
                    if opened < 10**14 or opened % 1000:
                        raise ValueError('EXPECTED_SPOT_MICROSECONDS')
                    t = opened // 1000
                    if closed != (t + step) * 1000 - 1 or t % step:
                        raise ValueError('INVALID_CLOSE_TIME')
                    volume, taker = float(r[5]), float(r[9])
                    if not np.isfinite([volume, taker]).all() or not 0 <= taker <= volume:
                        raise ValueError('INVALID_VOLUME')
                    rows.append([t, *map(float, r[1:5])])
        arr = np.asarray(rows, dtype=float)
        validate_rows(arr, stamp(record['first_open']), stamp(record['last_available']), step)
        batches.append(arr)
    a = np.concatenate(batches)
    validate_rows(a, int(a[0, 0]), int(a[-1, 0]) + step, step)
    return a


def verify_hourly_aggregation(h, m):
    if len(m) % 60:
        raise ValueError('PARTIAL_HOUR')
    mm = m.reshape(-1, 60, 5)
    hh = window(h, int(m[0, 0]), int(m[-1, 0]) + MINUTE)
    aggregate = np.column_stack([mm[:, 0, 0], mm[:, 0, 1], mm[:, :, 2].max(axis=1),
                                 mm[:, :, 3].min(axis=1), mm[:, -1, 4]])
    if not np.array_equal(aggregate, hh):
        raise ValueError('H1_VS_1M_MISMATCH')
    return len(hh)


def atr_values(h):
    atr = ATR14()
    return np.array([atr.append(Candle(int(b[0]), *b[1:])) or np.nan for b in h])


def freeze_cycle(day, h, atr):
    s = schedule(day)
    a, l = window(h, s['asia'], s['asia_end']), window(h, s['london'], s['freeze'])
    validate_rows(a, s['asia'], s['asia_end'], HOUR)
    validate_rows(l, s['london'], s['freeze'], HOUR)
    if len(a) != 4 or len(l) != 4:
        raise ValueError('NOT_PINE_A_FOUR_HOURS')
    idx = np.searchsorted(h[:, 0], s['freeze']) - 1
    av = float(atr[idx])
    if not np.isfinite(av) or av <= 0:
        raise ValueError('ATR_UNAVAILABLE')
    p = project(float(a[:, 2].max()), float(a[:, 3].min()),
                float(l[:, 2].max()), float(l[:, 3].min()))
    return dict(cycle=day.isoformat(), **s, levels_available_at=s['freeze'],
                a_open=float(a[0, 1]), a_close=float(a[-1, 4]),
                l_open=float(l[0, 1]), l_close=float(l[-1, 4]), atr14=av, **p)
