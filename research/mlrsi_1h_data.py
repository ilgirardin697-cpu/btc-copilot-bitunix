"""Verify PR19's immutable public data and append only a public closed tail."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import numpy as np
import requests
from research.mlrsi_1h_core import ROOT, CACHE, STEP, HOUR, digest, validate, aggregate, save

URL = 'https://data-api.binance.vision/api/v3/klines'


def prepare(cutoff, source='research/cache/mlrsi_pattern/spot_5m.npz', refresh=False, transport=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'input_manifest.json').read_text('utf-8'))
    if digest(source) != manifest['dataset_sha256']:
        raise ValueError('PARENT_DATASET_CHECKSUM_MISMATCH')
    rows = validate(np.load(source)['bars'], cutoff=cutoff)
    # Independently recheck every immutable archive used by the parent dataset.
    archive_dir = Path('research/cache/early_breakout')
    for item in manifest['sources']:
        if '.zip' in item['url']:
            path = archive_dir / item['url'].rsplit('/', 1)[1]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('ARCHIVE_CHECKSUM_MISMATCH')
    parts, additions = [rows], []
    cursor = int(rows[-1, 0] + STEP)
    http = transport or requests.Session()
    while refresh and cursor + STEP <= cutoff:
        params = dict(symbol='BTCUSDT', interval='5m', startTime=cursor, endTime=cutoff - 1, limit=1000)
        raw_path = CACHE / f'tail-{cursor}-{cutoff}.json'
        if not raw_path.exists():
            response = http.get(URL, params=params, timeout=(5, 25), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('PUBLIC_DATA_UNAVAILABLE')
            raw_path.write_bytes(response.content)
        data = json.loads(raw_path.read_bytes())
        if not isinstance(data, list) or not data:
            raise ValueError('PUBLIC_TAIL_INVALID')
        tail = validate([[int(r[0]), *[float(r[i]) for i in (1, 2, 3, 4, 5, 9)]] for r in data], cutoff=cutoff)
        if not len(tail) or tail[0, 0] < cursor:
            raise ValueError('PUBLIC_TAIL_TIME_INVALID')
        additions.append(dict(url=URL, params=params, sha256=digest(raw_path), rows=len(tail),
            first_timestamp=int(tail[0, 0]), last_timestamp=int(tail[-1, 0])))
        parts.append(tail)
        cursor = int(tail[-1, 0] + STEP)
    combined = validate(np.concatenate(parts), cutoff=cutoff)
    target = CACHE / 'spot_5m.npz'
    np.savez_compressed(target, bars=combined)
    hourly = aggregate(combined)
    out = dict(parent_pr=19, parent_commit='c049302691e7857691adaf652cd283874c0734a2',
        parent_dataset_sha256=manifest['dataset_sha256'], dataset_sha256=digest(target),
        requested_cutoff=cutoff, as_of=int(combined[-1, 0] + STEP), rows=len(combined),
        first_timestamp=int(combined[0, 0]), last_timestamp=int(combined[-1, 0]),
        hourly_rows=len(hourly), latest_closed_hour=int(hourly[-1, 0] + HOUR),
        gap_count=int(np.sum(np.diff(combined[:, 0]) != STEP)),
        sources=manifest['sources'] + additions, archive_checksums_reverified=True)
    save(ROOT / 'data_manifest.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'sources'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cutoff', type=int, required=True)
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--source', default='research/cache/mlrsi_pattern/spot_5m.npz')
    args = p.parse_args()
    prepare(args.cutoff, args.source, args.refresh)
