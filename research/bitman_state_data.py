"""Pure aggregation/validation helpers reused from PR #30, commit c1c56bd.

No downloader or network client is retained. Original helper formulas unchanged.
"""
from decimal import Decimal


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
