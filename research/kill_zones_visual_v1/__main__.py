"""Offline rendering entrypoint. No background process, network or trading."""
import argparse
from datetime import datetime
from pathlib import Path
from .chart import svg_chart
from .data import json_text, read_csv, sha
from .model import observe


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--day', required=True)
    p.add_argument('--as-of', required=True, help='explicit ISO UTC cutoff; never implicit now')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    import json
    manifest = json.loads(a.manifest.read_text(encoding='utf-8'))
    if manifest.get('symbol') != 'BTCUSDT' or manifest.get('venue') != 'BINANCE_USDM_PERPETUAL':
        raise ValueError('DATA_PROVENANCE_NOT_DECLARED_USDM')
    if manifest.get('excerpt_sha256') != sha(a.csv):
        raise ValueError('DATA_HASH_MISMATCH')
    cutoff = datetime.fromisoformat(a.as_of.replace('Z', '+00:00'))
    if cutoff.utcoffset() is None or cutoff.utcoffset().total_seconds() != 0:
        raise ValueError('AS_OF_MUST_BE_UTC')
    bars = read_csv(a.csv)
    r = observe(bars, a.day, int(cutoff.timestamp() * 1000))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'observation.json').write_text(json_text(dict(input=manifest, observation=r)), encoding='utf-8', newline='\n')
    if r.get('setup') or r.get('session_boxes'):
        (a.out / 'chart.svg').write_text(svg_chart(bars, r, 'BTCUSDT | BINANCE_USDM_PERPETUAL | HISTORICAL GEOMETRY AUDIT'), encoding='utf-8', newline='\n')
    print(json_text(dict(status=r['status'], confirmation=r['confirmation'], plan=r['plan'])))


if __name__ == '__main__':
    main()
