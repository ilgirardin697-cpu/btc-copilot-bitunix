"""Extract ONE fixed visual audit window from a cached official public archive.

No signal selection and no outcome import. The day was fixed before extraction.
"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .data import COLUMNS
from .model import HOUR, iso

URL = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09.zip'
MEMBER = 'BTCUSDT-5m-2026-09.csv'
FIRST = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
END = FIRST + 3 * 24 * HOUR


def extract(archive, checksum, out):
    raw = archive.read_bytes()
    expected = checksum.read_text(encoding='utf-8').split()[0]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('OFFICIAL_ARCHIVE_CHECKSUM_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist() != [MEMBER]:
            raise ValueError('ARCHIVE_MEMBER_MISMATCH')
        reader = csv.reader(io.StringIO(z.read(MEMBER).decode('utf-8-sig')))
        rows = []
        for r in reader:
            if not r or not r[0].isdigit():
                continue
            t = int(r[0])
            if FIRST <= t < END:
                if len(r) != 12 or int(r[6]) != t + 300_000 - 1:
                    raise ValueError('SOURCE_SCHEMA_OR_CLOSETIME')
                rows.append(r)
    if [int(r[0]) for r in rows] != list(range(FIRST, END, 300_000)):
        raise ValueError('SOURCE_GAP_OR_DUPLICATE')
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'BTCUSDT_USDM_1h_20260901_03.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(COLUMNS)
        for i in range(0, len(rows), 12):
            g = rows[i:i+12]
            w.writerow([g[0][0], g[0][1], max(Decimal(r[2]) for r in g),
                        min(Decimal(r[3]) for r in g), g[-1][4], sum(Decimal(r[5]) for r in g)])
    manifest = dict(symbol='BTCUSDT', venue='BINANCE_USDM_PERPETUAL', source_url=URL,
                    checksum_url=URL+'.CHECKSUM', archive_sha256=expected,
                    checksum_origin='Previously downloaded official .CHECKSUM; reverified locally, not re-fetched',
                    source_interval='5m', excerpt_interval='1h', source_rows=len(rows), excerpt_rows=len(rows)//12,
                    first_open=iso(FIRST), available_at_end=iso(END),
                    aggregation='Exact 12 contiguous 5m; O first, H max, L min, C last, base_volume Decimal sum',
                    timezone='UTC milliseconds; close availability = open_time + 3600000',
                    excerpt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    fixed_display_day='2026-09-02', selected_before_reading_signals=True,
                    purpose='HISTORICAL_VISUAL_AND_CAUSAL_CHECK_ONLY_NOT_PERFORMANCE', no_virgin_holdout=True)
    (out/'data_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--checksum', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    extract(a.archive, a.checksum, a.out)
