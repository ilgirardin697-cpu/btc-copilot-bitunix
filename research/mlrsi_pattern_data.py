"""Read existing checksumed public BTC data; optionally append public closed tail."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import numpy as np
import requests
from research.mlrsi_pattern_backtest import validate, STEP

URL = 'https://data-api.binance.vision/api/v3/klines'


def prepare(cutoff, refresh=False, transport=None):
    source = Path('research/cache/early_breakout')
    target = Path('research/cache/mlrsi_pattern')
    target.mkdir(parents=True, exist_ok=True)
    path = source / 'spot_5m.npz'
    rows = validate(np.load(path)['bars'], cutoff=cutoff)
    original = json.loads((source / 'manifest.json').read_text('utf-8'))
    manifest = list(original['sources'])
    # Verify all local immutable archives against their recorded hashes again.
    for item in manifest:
        if '.zip' in item['url']:
            archive = source / item['url'].rsplit('/', 1)[1]
            if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('ARCHIVE_CHECKSUM_MISMATCH')
    cursor = int(rows[-1, 0]) + STEP
    http = transport or requests.Session()
    parts = [rows]
    while refresh and cursor + STEP <= cutoff:
        params = dict(symbol='BTCUSDT', interval='5m', startTime=cursor, endTime=cutoff - 1, limit=1000)
        raw_path = target / f'tail-{cursor}-{cutoff}.json'
        if not raw_path.exists():
            response = http.get(URL, params=params, timeout=(5, 25), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('PUBLIC_TAIL_UNAVAILABLE')
            raw_path.write_bytes(response.content)
        raw = raw_path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, list) or not payload:
            raise ValueError('PUBLIC_TAIL_INVALID')
        values = []
        for r in payload:
            if int(r[6]) != int(r[0]) + STEP - 1:
                raise ValueError('PUBLIC_TAIL_CLOSE_INVALID')
            values.append([int(r[0]), *[float(r[i]) for i in (1, 2, 3, 4, 5, 9)]])
        tail = validate(values, cutoff=cutoff)
        if not len(tail) or tail[0, 0] != cursor:
            raise ValueError('PUBLIC_TAIL_GAP')
        parts.append(tail)
        manifest.append(dict(url=URL, params=params, sha256=hashlib.sha256(raw).hexdigest(),
                             rows=len(tail), first_timestamp=int(tail[0, 0]), last_timestamp=int(tail[-1, 0])))
        cursor = int(tail[-1, 0]) + STEP
    rows = validate(np.concatenate(parts), cutoff=cutoff)
    output_path = target / 'spot_5m.npz'
    np.savez_compressed(output_path, bars=rows)
    output = dict(as_of=int(rows[-1, 0]) + STEP, requested_cutoff=cutoff, rows=len(rows),
                  first_timestamp=int(rows[0, 0]), last_timestamp=int(rows[-1, 0]),
                  dataset_sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
                  original_dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  gap_count=int(np.count_nonzero(np.diff(rows[:, 0]) != STEP)), sources=manifest)
    artifacts = Path('research/mlrsi_pattern')
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / 'data_manifest.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in output.items() if k != 'sources'}), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cutoff', type=int, required=True)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    prepare(args.cutoff, args.refresh)
