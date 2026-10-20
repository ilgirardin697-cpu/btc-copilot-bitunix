"""Offline public USD-M research acquisition. Never imported by production."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile

import requests

DAY = 86_400_000
FOUR_HOURS = DAY // 6
WEEK = 7 * DAY
MONDAY = 4 * DAY  # 1970-01-05 00:00 UTC; Unix epoch itself was Thursday.
URL = 'https://fapi.binance.com/fapi/v1/klines'
CUTOFF = 1792368000000  # 2026-10-19T00:00:00Z, fixed before outcomes.
FIELDS = (0, 1, 2, 3, 4, 5, 6, 9)
NAMES = ('open_time', 'open', 'high', 'low', 'close', 'base_volume', 'close_time', 'taker_buy_base_volume')
ARCHIVE_MONTHS = ('2019-09', '2020-03', '2021-11', '2022-11', '2023-06', '2024-03', '2025-01', '2026-09')


def week_start(timestamp):
    return (int(timestamp) - MONDAY) // WEEK * WEEK + MONDAY


def validate(rows, interval, cutoff):
    if not isinstance(rows, list) or not rows:
        raise ValueError('EMPTY_MARKET_DATA')
    previous = None
    for row in rows:
        if not isinstance(row, list) or len(row) != 12:
            raise ValueError('BAD_SCHEMA')
        opening, closing = row[0], row[6]
        if type(opening) is not int or type(closing) is not int:
            raise ValueError('BAD_TIMESTAMP_TYPE')
        anchor = MONDAY if interval == WEEK else 0
        if (opening - anchor) % interval or closing != opening + interval - 1 or closing >= cutoff:
            raise ValueError('OPEN_OR_MISALIGNED_CANDLE')
        if previous is not None and opening != previous + interval:
            raise ValueError('GAP_DUPLICATE_OR_ORDER')
        previous = opening
        o, h, l, c, volume, taker = (Decimal(str(row[i])) for i in (1, 2, 3, 4, 5, 9))
        if not all(x.is_finite() for x in (o, h, l, c, volume, taker)):
            raise ValueError('NONFINITE_MARKET_VALUE')
        if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c) or l > h or not 0 <= taker <= volume:
            raise ValueError('BAD_OHLCV')
    return rows


def aggregate_weeks(rows, cutoff):
    validate(rows, FOUR_HOURS, cutoff)
    groups = {}
    for row in rows:
        groups.setdefault(week_start(row[0]), []).append(row)
    result, excluded = [], []
    for opening, group in sorted(groups.items()):
        expected = list(range(opening, opening + WEEK, FOUR_HOURS))
        if [r[0] for r in group] != expected or opening + WEEK > cutoff:
            excluded.append(dict(open_time=opening, bars=len(group), reason='INCOMPLETE_WEEK'))
            continue
        result.append([opening, group[0][1], str(max(Decimal(str(r[2])) for r in group)),
                       str(min(Decimal(str(r[3])) for r in group)), group[-1][4],
                       str(sum((Decimal(str(r[5])) for r in group), Decimal(0))), opening + WEEK - 1,
                       str(sum((Decimal(str(r[7])) for r in group), Decimal(0))),
                       sum(int(r[8]) for r in group),
                       str(sum((Decimal(str(r[9])) for r in group), Decimal(0))),
                       str(sum((Decimal(str(r[10])) for r in group), Decimal(0))), '0'])
    validate(result, WEEK, cutoff)
    return result, excluded


def compare_fields(expected, actual):
    reference = {r[0]: r for r in expected}
    differences = []
    for row in actual:
        if row[0] not in reference:
            differences.append(dict(open_time=row[0], field='MISSING_REFERENCE'))
            continue
        for field, name in zip(FIELDS, NAMES):
            a, b = Decimal(str(reference[row[0]][field])), Decimal(str(row[field]))
            if a != b:
                differences.append(dict(open_time=row[0], field=name, reference=str(a), actual=str(b), delta=str(b-a)))
    return differences


def acquire(cache, cutoff=CUTOFF):
    """Explicit CLI-only download; fixed official hosts, no credentials/proxies."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    if (cache / 'manifest.json').exists():
        raise ValueError('CACHE_EXISTS_USE_OFFLINE_OR_NEW_DIRECTORY')
    records = []
    with requests.Session() as session:
        session.trust_env = False

        def get(url, params, name, optional=False):
            response = session.get(url, params=params, timeout=(5, 25), allow_redirects=False)
            record = dict(url=url, params=params, http_status=response.status_code,
                          size=len(response.content), sha256=hashlib.sha256(response.content).hexdigest(), file=name)
            records.append(record)
            if optional and response.status_code == 404:
                return None
            if response.status_code != 200:
                raise ValueError('PUBLIC_HTTP_' + str(response.status_code))
            (cache / name).write_bytes(response.content)
            return response.content

        def pages(interval, duration):
            opening, all_rows = 0, []
            while opening < cutoff:
                params = dict(symbol='BTCUSDT', interval=interval, startTime=opening, endTime=cutoff-1, limit=1500)
                raw = get(URL, params, interval+'-'+str(len(all_rows))+'.json')
                rows = validate(json.loads(raw), duration, cutoff)
                if rows[0][0] < opening:
                    raise ValueError('PAGE_MOVED_BACKWARDS')
                all_rows += rows
                opening = rows[-1][0] + duration
                if len(rows) < 1500:
                    if opening != cutoff:
                        raise ValueError('HISTORY_TRUNCATED')
                    break
            validate(all_rows, duration, cutoff)
            return all_rows

        four = pages('4h', FOUR_HOURS)
        native = pages('1w', WEEK)
        weekly, excluded = aggregate_weeks(four, cutoff)
        native = [r for r in native if r[0] >= weekly[0][0]]
        if [r[0] for r in native] != [r[0] for r in weekly]:
            raise ValueError('WEEKLY_BOUNDARY_MISMATCH')
        weekly_diff = compare_fields(native, weekly)
        archive_results = []
        for month in ARCHIVE_MONTHS:
            filename = 'BTCUSDT-4h-'+month+'.zip'
            url = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/4h/'+filename
            raw = get(url, None, filename, optional=True)
            if raw is None:
                archive_results.append(dict(month=month, status='NOT_AVAILABLE'))
                continue
            checksum = get(url+'.CHECKSUM', None, filename+'.CHECKSUM').decode().split()[0]
            if hashlib.sha256(raw).hexdigest() != checksum:
                raise ValueError('ARCHIVE_CHECKSUM_MISMATCH')
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.namelist()
                if len(members) != 1:
                    raise ValueError('ARCHIVE_SCHEMA')
                parsed = list(csv.reader(io.StringIO(archive.read(members[0]).decode())))
            parsed = [row for row in parsed if row and row[0] != 'open_time']
            for row in parsed:
                row[0], row[6], row[8] = int(row[0]), int(row[6]), int(row[8])
            validate(parsed, FOUR_HOURS, cutoff)
            differences = compare_fields(four, parsed)
            archive_results.append(dict(month=month, status='COMPARED', rows=len(parsed),
                                        checksum_verified=True, differences=differences))
    manifest = dict(venue='BINANCE_USDM_PERPETUAL', symbol='BTCUSDT', source=URL,
                    historical_not_forward_observed=True, acquired_at=datetime.now(timezone.utc).isoformat(),
                    cutoff=cutoff, first_4h_open=four[0][0], last_4h_close=four[-1][6], rows_4h=len(four),
                    first_week_open=weekly[0][0], last_week_close=weekly[-1][6], weeks=len(weekly),
                    excluded_weeks=excluded, weekly_rest_comparison=dict(rows=len(native), differences=weekly_diff),
                    vision_comparisons=archive_results, requests=records,
                    protocol_sha256=hashlib.sha256(Path('research/results/BITMAN_WEEKLY_EXPANSION_PROTOCOL.md').read_bytes().replace(b'\r\n',b'\n')).hexdigest())
    for name, rows in (('four_hour.json', four), ('weekly.json', weekly)):
        raw = json.dumps(rows, separators=(',', ':')).encode()
        (cache / name).write_bytes(raw)
        manifest[name] = dict(rows=len(rows), sha256=hashlib.sha256(raw).hexdigest())
    (cache / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True)
    args = parser.parse_args()
    result = acquire(args.cache)
    print(json.dumps({k:result[k] for k in ('venue','rows_4h','weeks','first_week_open','last_week_close','weekly_rest_comparison','vision_comparisons')}))
