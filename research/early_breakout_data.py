"""Reproducible BTCUSDT SPOT public archives and market-data-only tail."""
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
import numpy as np
import requests
from early_breakout_core import validate_rows

ARCHIVE = 'https://data.binance.vision/data/spot/'
MARKET = 'https://data-api.binance.vision/api/v3/klines'
STEP = 300000


def public_get(url, **kwargs):
    if not (url.startswith(ARCHIVE) or url == MARKET):
        raise ValueError('PUBLIC_URL_BLOCKED')
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(5, 25), allow_redirects=False, **kwargs)
            if response.status_code in (200, 404):
                return response
        except requests.RequestException:
            pass
        if attempt < 2:
            time.sleep(.5*(attempt+1))
    raise ValueError('PUBLIC_DOWNLOAD_UNAVAILABLE')


def row(values):
    stamp = int(values[0])
    if stamp >= 10**14:  # Binance SPOT archive timestamps switch to microseconds in 2025
        stamp //= 1000
    return [stamp, *[float(values[i]) for i in (1, 2, 3, 4, 5, 9)]]


def archive(kind, label, cache):
    name = f'BTCUSDT-5m-{label}.zip'
    url = ARCHIVE + f'{kind}/klines/BTCUSDT/5m/' + name
    target = cache/name
    check = cache/(name+'.CHECKSUM')
    if not target.exists() or not check.exists():
        response = public_get(url)
        if response.status_code == 404:
            return None
        checksum = public_get(url+'.CHECKSUM')
        if checksum.status_code != 200:
            raise ValueError('CHECKSUM_MISSING')
        target.write_bytes(response.content)
        check.write_text(checksum.text, encoding='utf-8')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != check.read_text(encoding='utf-8').split()[0]:
        raise ValueError('CHECKSUM_MISMATCH')
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
        if len(names) != 1:
            raise ValueError('ARCHIVE_SCHEMA_INVALID')
        rows = np.asarray([row(r) for r in csv.reader(io.StringIO(z.read(names[0]).decode()))], float)
    validate_rows(rows, STEP)
    return rows, dict(url=url, checksum_url=url+'.CHECKSUM', sha256=digest, rows=len(rows),
                      first_timestamp=int(rows[0, 0]), last_timestamp=int(rows[-1, 0]))


def download(cache, end_ms):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.fromtimestamp(end_ms/1000, timezone.utc)
    months = []
    year, month = 2019, 8  # warm-up: full causal RSI window before TRAIN begins
    while (year, month) < (cutoff.year, cutoff.month):
        months.append(f'{year}-{month:02d}')
        year, month = (year+1, 1) if month == 12 else (year, month+1)
    with ThreadPoolExecutor(max_workers=6) as pool:
        loaded = list(pool.map(lambda label: archive('monthly', label, cache), months))
    parts, manifest = [], []
    for label, result in zip(months, loaded):
        if result is not None:
            rows, entry = result
            parts.append(rows)
            manifest.append(entry)
            continue
        day = datetime.strptime(label+'-01', '%Y-%m-%d').replace(tzinfo=timezone.utc)
        dates = []
        while day.strftime('%Y-%m') == label:
            dates.append(day.strftime('%Y-%m-%d'))
            day += timedelta(days=1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            daily = list(pool.map(lambda date: archive('daily', date, cache), dates))
        if any(item is None for item in daily):
            raise ValueError('HISTORICAL_ARCHIVE_GAP')
        for rows, entry in daily:
            parts.append(rows)
            manifest.append(entry)
    start = int(datetime(cutoff.year, cutoff.month, 1, tzinfo=timezone.utc).timestamp()*1000)
    # Current month: public REST only, independently checksummed with exact parameters.
    cursor = start
    while cursor + STEP <= end_ms:
        params = dict(symbol='BTCUSDT', interval='5m', limit=1000, startTime=cursor, endTime=end_ms-1)
        target = cache/f'tail-{cursor}-{end_ms}.json'
        if not target.exists():
            response = public_get(MARKET, params=params)
            if response.status_code != 200:
                raise ValueError('PUBLIC_TAIL_UNAVAILABLE')
            target.write_bytes(response.content)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, list) or not payload:
            raise ValueError('PUBLIC_TAIL_INVALID')
        rows = validate_rows([row(r) for r in payload], STEP, end_ms)
        if not len(rows) or rows[0, 0] != cursor:
            raise ValueError('PUBLIC_TAIL_GAP')
        parts.append(rows)
        manifest.append(dict(url=MARKET, params=params, sha256=hashlib.sha256(raw).hexdigest(),
                             rows=len(rows), first_timestamp=int(rows[0, 0]), last_timestamp=int(rows[-1, 0])))
        cursor = int(rows[-1, 0])+STEP
    rows = validate_rows(np.concatenate(parts), STEP, end_ms)
    np.savez_compressed(cache/'spot_5m.npz', bars=rows)
    (cache/'manifest.json').write_text(json.dumps(dict(as_of=end_ms, sources=manifest), indent=2), encoding='utf-8')
    print(json.dumps({'downloaded_rows': len(rows), 'first': int(rows[0, 0]), 'last': int(rows[-1, 0]),
                      'gap_count': int(np.count_nonzero(np.diff(rows[:, 0]) != STEP))}), flush=True)
    return rows, manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--cache', default='research/cache/early_breakout')
    args = parser.parse_args()
    end = int(datetime.fromisoformat(args.as_of).timestamp()*1000)//STEP*STEP
    download(args.cache, end)
