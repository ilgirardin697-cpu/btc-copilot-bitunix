"""Official public Spot archives. No credentials, account calls, proxies or venue fallback."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / 'cache' / 'killzone_radar_v1'
MINUTE = 60000
HOUR = 3600000


def protocol_hash():
    return hashlib.sha256((HERE/'specification.json').read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def months(start):
    y, m = map(int, start.split('-'))
    while (y, m) <= (2026, 10):
        yield f'{y:04}-{m:02}'
        y, m = (y+1, 1) if m == 12 else (y, m+1)


def fetch(item, reuse):
    interval, month = item
    filename = f'BTCUSDT-{interval}-{month}.zip'
    url = f'https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/{interval}/{filename}'
    s = requests.Session(); s.trust_env = False
    r = s.get(url+'.CHECKSUM', timeout=30, allow_redirects=False)
    if r.status_code != 200:
        raise ValueError(f'OFFICIAL_CHECKSUM_HTTP_{r.status_code}_{filename}')
    expected = r.text.split()[0].lower()
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('INVALID_OFFICIAL_SHA')
    path = CACHE/filename
    candidates = [path] + [Path(p)/filename for p in reuse]
    source = next((p for p in candidates if p.is_file()), None)
    if source is not None:
        raw = source.read_bytes()
    else:
        r = s.get(url, timeout=120, allow_redirects=False)
        if r.status_code != 200:
            raise ValueError(f'PUBLIC_ARCHIVE_HTTP_{r.status_code}_{filename}')
        raw = r.content
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('CHECKSUM_MISMATCH_NO_OVERWRITE')
    if not path.exists():
        with path.open('xb') as f:
            f.write(raw)
    return dict(filename=filename, interval=interval, month=month, url=url,
                sha256=expected, bytes=len(raw), time_unit='us' if month >= '2025-01' else 'ms')


def archive_rows(path, interval, month, quality=None):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != 1:
            raise ValueError('ARCHIVE_MEMBERS')
        with z.open(z.namelist()[0]) as f:
            a = np.loadtxt(io.TextIOWrapper(f), delimiter=',', dtype=np.float64, ndmin=2)
    if a.shape[1] != 12 or not np.isfinite(a).all():
        raise ValueError('SCHEMA_OR_NONFINITE')
    unit = 1000 if month >= '2025-01' else 1
    step = HOUR if interval == '1h' else MINUTE
    opens = a[:, 0]
    if np.any(opens % unit) or np.any(opens % (step*unit)):
        raise ValueError('TIMESTAMP_UNIT')
    if np.any(np.diff(opens) <= 0):
        raise ValueError('TIME_ORDER')
    invalid_close = a[:, 6] != opens + step*unit-1
    if quality is not None:
        for i in np.flatnonzero(invalid_close):
            quality.append(dict(archive=Path(path).name, reason='PARTIAL_ARCHIVE_CLOSE_TIME',
                                open_time=int(opens[i]/unit), original_close_time=int(a[i, 6]),
                                original_unit='us' if unit == 1000 else 'ms'))
    if np.any(a[:, 3] > np.minimum(a[:, 1], a[:, 4])) or np.any(a[:, 2] < np.maximum(a[:, 1], a[:, 4])) or np.any(a[:, 1:5] <= 0):
        raise ValueError('OHLC')
    b = a[:, :5].copy(); b[:, 0] /= unit
    expected_start = int(datetime.fromisoformat(month+'-01').replace(tzinfo=timezone.utc).timestamp()*1000)
    if b[0, 0] < expected_start:
        raise ValueError('WRONG_MONTH')
    # Never change the early closeTime or manufacture the rest of a halted candle.
    # Removing it leaves an explicit gap; affected cycles/warmup fail closed downstream.
    return b[~invalid_close]


def prepare():
    manifest = json.loads((CACHE/'download_manifest.json').read_text())
    quality = []
    for interval in ('1h', '1m'):
        parts = []
        for row in manifest['archives']:
            if row['interval'] == interval:
                path = CACHE/row['filename']
                if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                    raise ValueError('RAW_CHANGED')
                parts.append(archive_rows(path, interval, row['month'], quality))
        bars = np.concatenate(parts)
        if np.any(np.diff(bars[:, 0]) <= 0):
            raise ValueError('DUPLICATE_OR_REORDERED_ARCHIVE')
        np.save(CACHE/(interval+'.npy'), bars, allow_pickle=False)
        print(json.dumps(dict(interval=interval, rows=len(bars),
                              missing_slots=int(np.sum(np.diff(bars[:, 0])/(HOUR if interval=='1h' else MINUTE)-1)))))
    (CACHE/'quality.json').write_text(json.dumps(quality, indent=2)+'\n')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reuse-cache', action='append', default=[])
    p.add_argument('--prepare-only', action='store_true'); args = p.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    if not args.prepare_only:
        items = [('1h', m) for m in months('2021-12')] + [('1m', m) for m in months('2022-01')]
        with ThreadPoolExecutor(max_workers=4) as ex:
            rows = list(ex.map(lambda item: fetch(item, args.reuse_cache), items))
        (CACHE/'download_manifest.json').write_text(json.dumps(dict(protocol_hash=protocol_hash(), archives=rows), indent=2)+'\n')
        print(f'OFFICIAL_CHECKSUMS_VERIFIED={len(rows)}')
    prepare()


if __name__ == '__main__':
    main()
