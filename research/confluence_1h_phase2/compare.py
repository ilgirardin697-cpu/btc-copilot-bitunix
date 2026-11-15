"""Explicit export mappings; no guessed timestamps, venue swaps or line colors.

This compares numerical evidence. It cannot authenticate an uploaded export,
identify a visually selected line or authorize a strategy/backtest by itself.
"""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np

from research.confluence_1h.indicators import calculate
from .semantics import HOUR, SERIES, events, validate_bars

SETTINGS = dict(price_source='OHLC4', mfi_source='HLC3', rsi_length=14,
                mfi_length=14, bb_length=25, bb_multiplier=2,
                stoch_length=21, stoch_smoothing=3, ma_type='EMA', ma_length=15,
                pvi_ema_length=15, pvi_range_length=90,
                nvi_ema_length=15, nvi_range_length=90,
                dmi_length=14, adx_smoothing=14, ao_fast=5, ao_slow=34, atr_length=14)
FIELDS = dict(SERIES, adx='adx', plus_di='plus_di', minus_di='minus_di',
              ao='ao', atr='atr', pvi='pvi', pvi_ema='pvi_ema', pvi_osc='pvi_osc')
REQUIRED = ('pececillos', 'tendencia', 'tiburones', 'ma_trend', 'adx', 'plus_di', 'minus_di', 'ao', 'atr')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_time(value, fmt):
    if fmt == 'unix_ms':
        if not str(value).isdigit():
            raise ValueError('INTEGER_MILLISECONDS_REQUIRED')
        t = int(value)
        # Explicit unit; seconds/us are rejected, not guessed or silently scaled.
        if not 946684800000 <= t < 4102444800000:
            raise ValueError('MILLISECONDS_OUT_OF_RANGE')
        return t
    if fmt == 'iso8601_offset':
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if d.utcoffset() is None:
            raise ValueError('EXPLICIT_OFFSET_REQUIRED')
        return int(d.astimezone(timezone.utc).timestamp() * 1000)
    raise ValueError('EXPLICIT_TIMESTAMP_FORMAT_REQUIRED')


def load_market(path, manifest):
    raw = Path(path).read_bytes()
    if sha(raw) != manifest['sha256']:
        raise ValueError('MARKET_CHECKSUM')
    body = gzip.decompress(raw) if str(path).endswith('.gz') else raw
    rows = list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
    a = validate_bars([[int(r['open_time_ms']), *[float(r[k]) for k in ('open', 'high', 'low', 'close', 'volume')]] for r in rows])
    if len(a) != manifest['rows'] or int(a[0, 0]) != manifest['first_open_ms'] or int(a[-1, 0]) != manifest['last_open_ms']:
        raise ValueError('MARKET_MANIFEST_RANGE')
    return a


def number(value):
    if value is None or value in ('', 'NA', 'na', 'null'):
        return None
    v = float(value)
    if not np.isfinite(v):
        raise ValueError('NONFINITE_EXPORT')
    return v


def bound(meta, name):
    # Predeclared: full precision tolerance or half the exported rounding quantum.
    # No fitted shifts, regression/rescaling, optimizing tolerances or best subset.
    places = meta['decimal_places'].get(name)
    if places is None:
        return 1e-7
    if type(places) is not int or not 2 <= places <= 15:
        raise ValueError('PRECISION_NOT_DECLARED_OR_TOO_COARSE')
    return .5 * 10 ** (-places) + 1e-7


def compare(records, meta, market, market_meta):
    a = validate_bars(market)
    if meta.get('venue') != market_meta.get('venue') or meta.get('symbol') != market_meta.get('symbol'):
        raise ValueError('VENUE_OR_SYMBOL_MISMATCH')
    if not meta.get('platform') or not meta.get('full_ticker'):
        raise ValueError('PLATFORM_AND_FULL_TICKER_REQUIRED')
    if meta.get('timeframe_seconds') != 3600 or market_meta.get('timeframe_seconds') != 3600 or meta.get('candle_type') != 'STANDARD':
        raise ValueError('STANDARD_H1_ONLY')
    if meta.get('volume_unit') != 'BTC_BASE':
        raise ValueError('BASE_VOLUME_REQUIRED')
    if meta.get('timestamp_kind') not in ('open', 'close'):
        raise ValueError('TIMESTAMP_KIND_REQUIRED')
    columns = meta['columns']
    if not all(k in columns for k in (*REQUIRED, 'time', 'confirmed', 'open', 'high', 'low', 'close', 'volume')):
        raise ValueError('EXPLICIT_NAMED_COLUMNS_REQUIRED')
    blockers = []
    if meta.get('settings') != SETTINGS:
        blockers.append('SETTINGS_NOT_CONFIRMED_OR_DIFFERENT')
    if meta.get('source_kind') != 'OWNER_SUPPLIED_PLATFORM_EXPORT':
        blockers.append('NOT_EXTERNAL_PLATFORM_EVIDENCE')
    if meta.get('indicator_history_start_open_ms') != int(a[0, 0]):
        blockers.append('INDICATOR_INITIALIZATION_PREFIX_NOT_VERIFIED')
    if not meta.get('original_indicator_identity_reviewed', False):
        blockers.append('ORIGINAL_INDICATOR_IDENTITY_NOT_REVIEWED')
    f = calculate(a)
    local_events = events(f)
    lookup = {int(t): i for i, t in enumerate(a[:, 0])}
    rows, previous = [], None
    for r in records:
        if 'full_ticker' in r and r['full_ticker'] != meta['full_ticker']:
            raise ValueError('PAYLOAD_TICKER_MISMATCH')
        if 'indicator_history_start_open_ms' in r and r['indicator_history_start_open_ms'] != meta.get('indicator_history_start_open_ms'):
            raise ValueError('PAYLOAD_HISTORY_START_MISMATCH')
        if r.get('settings_id', 'KONCORDE_SUPPLIED_DEFAULTS_V1') != 'KONCORDE_SUPPLIED_DEFAULTS_V1':
            raise ValueError('PAYLOAD_SETTINGS_ID_MISMATCH')
        if meta.get('capture_mode') == 'LIVE' and r.get('historical_recalculation') is True:
            raise ValueError('HISTORICAL_REPLAY_IS_NOT_LIVE')
        t = parse_time(r[columns['time']], meta['timestamp_format'])
        if meta['timestamp_kind'] == 'close':
            t -= HOUR
        if t % HOUR or (previous is not None and t != previous + HOUR):
            raise ValueError('EXPORT_GAP_DUPLICATE_OR_ORDER')
        previous = t
        if str(r[columns['confirmed']]).lower() != 'true':
            raise ValueError('CLOSED_CANDLE_REQUIRED')
        available = t + HOUR
        if 'available_at' in columns:
            if parse_time(r[columns['available_at']], meta['timestamp_format']) != available:
                raise ValueError('CLOSE_AVAILABILITY_MISMATCH')
        # An external logging clock is kept separate, never used to shift bars.
        receipt = None
        if 'emitted_at' in columns and r.get(columns['emitted_at']):
            receipt = parse_time(r[columns['emitted_at']], meta['timestamp_format'])
            if meta.get('capture_mode') == 'LIVE' and receipt < available:
                raise ValueError('EMITTED_BEFORE_CLOSE')
        row = dict(open_time_ms=t, close_time_ms=available, earliest_available_at=available,
                   actual_emitted_at=receipt, errors={}, matches={})
        if t not in lookup:
            row['status'] = 'NO_MARKET_OVERLAP'
            rows.append(row)
            continue
        i = lookup[t]
        price_ok = True
        row['ohlcv_errors'] = {}
        for j, k in enumerate(('open', 'high', 'low', 'close', 'volume'), 1):
            v = number(r[columns[k]])
            error = None if v is None else abs(v - a[i, j])
            row['ohlcv_errors'][k] = error
            price_ok &= error is not None and error <= bound(meta, k)
        for name, key in FIELDS.items():
            if name not in columns:
                continue
            v, x = number(r[columns[name]]), f[key][i]
            error = None if v is None or not np.isfinite(x) else abs(v - x)
            row['errors'][name] = error
            row['matches'][name] = error is not None and error <= bound(meta, name)
        row['status'] = 'NUMERIC_MATCH' if price_ok and all(row['matches'][k] for k in REQUIRED) else 'DIFFERENCE_OR_WARMUP'
        # Compare every area against the original red EMA(trend), never EMA(minnows).
        row['crosses'] = {}
        for name in ('pececillos', 'tendencia', 'tiburones'):
            key = SERIES[name]
            current = number(r[columns[name]])
            red = number(r[columns['ma_trend']])
            prior = rows[-1] if rows and rows[-1].get('open_time_ms') == t-HOUR else None
            for side in ('up', 'down'):
                event_name = name + '_cross_' + side
                local = None
                if i and np.isfinite([f[key][i-1], f['kon_signal'][i-1], f[key][i], f['kon_signal'][i]]).all():
                    x0, y0, x1, y1 = f[key][i-1], f['kon_signal'][i-1], f[key][i], f['kon_signal'][i]
                    local = bool(x1 > y1 and x0 <= y0) if side == 'up' else bool(x1 < y1 and x0 >= y0)
                external = None
                if prior and current is not None and red is not None and prior.get('source_values', {}).get(name) is not None and prior['source_values'].get('ma_trend') is not None:
                    v0, y0 = prior['source_values'][name], prior['source_values']['ma_trend']
                    # Rounded ties cannot establish the side of a crossing.
                    eps = bound(meta, name) + bound(meta, 'ma_trend')
                    if abs(current-red) > eps and abs(v0-y0) > eps:
                        external = bool(current > red and v0 <= y0) if side == 'up' else bool(current < red and v0 >= y0)
                row['crosses'][event_name] = dict(python=local, exported=external,
                                                 match=None if external is None or local is None else local == external)
        row['source_values'] = {k: number(r[columns[k]]) for k in (*SERIES, 'adx', 'ao')}
        row['events'] = {}
        # Three consecutive exported closes suffice for local slope reversals.
        # Near rounded equality the external event is UNDETERMINED, never guessed.
        prefix = [*rows[-2:], row]
        for name in SERIES:
            samples = [p.get('source_values', {}).get(name) for p in prefix]
            quantum = bound(meta, name)
            for kind in ('zero_cross_up', 'zero_cross_down', 'slope_turn_up', 'slope_turn_down'):
                external = None
                if len(samples) >= 2 and all(x is not None for x in samples[-2:]):
                    before, current = samples[-2:]
                    if kind.startswith('zero_') and min(abs(before), abs(current)) > quantum:
                        external = bool(current > 0 and before <= 0) if kind.endswith('_up') else bool(current < 0 and before >= 0)
                    if kind.startswith('slope_') and len(samples) == 3 and samples[0] is not None:
                        d0, d1 = before-samples[0], current-before
                        if min(abs(d0), abs(d1)) > 2*quantum:
                            external = bool(d0 < 0 and d1 > 0) if kind.endswith('_up') else bool(d0 > 0 and d1 < 0)
                k = name + '_' + kind
                row['events'][k] = dict(python=bool(local_events[k][i]), exported=external,
                                         match=None if external is None else bool(local_events[k][i]) == external)
        rows.append(row)
    if not records:
        blockers.append('NO_EXTERNAL_ROWS')
    if rows and any(r['status'] != 'NUMERIC_MATCH' for r in rows):
        blockers.append('NUMERIC_OR_PRICE_OR_OVERLAP_DIFFERENCE')
    if any(v['match'] is False for r in rows for v in r.get('crosses', {}).values()):
        blockers.append('CROSSING_DIFFERENCE')
    if any(v['match'] is False for r in rows for v in r.get('events', {}).values()):
        blockers.append('SLOPE_OR_ZERO_EVENT_DIFFERENCE')
    errors = {k: [r['errors'][k] for r in rows if r['errors'].get(k) is not None] for k in FIELDS}
    return dict(records=len(records), numerical_matches=sum(r['status'] == 'NUMERIC_MATCH' for r in rows),
                field_max_abs_error={k: max(v) if v else None for k, v in errors.items()}, rows=rows,
                comparison_blockers=blockers,
                mathematical_status='NUMERIC_EVIDENCE_REQUIRES_REVIEW' if rows and not blockers else 'NOT_ESTABLISHED',
                visual_line_identity='UNCONFIRMED_REQUIRES_NAMED_LINE_REVIEW',
                strategy_specification='NOT_FROZEN_PENDING_SERIES_IDENTIFICATION',
                proprietary_bitman_parity='NOT_PROVEN',
                new_backtests_allowed=False, trade_authority='NONE')


def read_export(raw, meta):
    text = raw.decode('utf-8-sig')
    fmt = meta['export_format']
    if fmt == 'CSV':
        return list(csv.DictReader(io.StringIO(text)))
    if fmt == 'JSONL':
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if fmt == 'PINE_LOGS_CSV':
        result = []
        prefix = 'IGOD_KONCORDE_SERIES_V1='
        for row in csv.DictReader(io.StringIO(text)):
            message = row[meta['message_column']]
            if prefix in message:
                result.append(json.loads(message.split(prefix, 1)[1]))
        return result
    raise ValueError('EXPLICIT_EXPORT_FORMAT_REQUIRED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('export_csv')
    p.add_argument('--metadata', required=True)
    p.add_argument('--market', required=True)
    p.add_argument('--market-manifest', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    raw = Path(args.export_csv).read_bytes()
    meta = json.loads(Path(args.metadata).read_text('utf-8-sig'))
    market_meta = json.loads(Path(args.market_manifest).read_text('utf-8-sig'))
    result = compare(read_export(raw, meta), meta,
                     load_market(args.market, market_meta), market_meta)
    result['original_export_sha256'] = sha(raw)
    result['metadata_sha256'] = sha(Path(args.metadata).read_bytes())
    with Path(args.out).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
