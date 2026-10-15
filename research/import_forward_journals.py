"""Offline, read-only analysis of EXPORTED observation journals; no production imports.

No HTTP, accounts, orders, signal reconstruction or writable store constructors.
Input: a copy of /data (or one exported subsystem directory), optional closed 5m
CSV time,open,high,low,close in UTC milliseconds. Outputs must be outside input.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

STEP = 300000
HORIZONS = (1, 4, 12, 24, 48, 72)
PAIRS = ((.005, .005), (.01, .01), (.02, .01), (.03, .015))
CONFIRMED = {'GREEN_CROSS', 'GREEN_RESUME', 'RED_CROSS', 'RED_RESUME',
             'CONFLUENCE_3OF3_GREEN', 'CONFLUENCE_3OF3_RED'}
LAYOUT = {
    'copilot_audit': ('signals.jsonl', 'outcomes.jsonl', 'snapshots.jsonl', 'state.json', 'durability_canary.json'),
    'mlrsi': ('igod_mlrsi_events.jsonl', 'igod_mlrsi_state.json'),
    'early_breakout': ('events.jsonl', 'outcomes.jsonl', 'snapshots.jsonl', 'state.json'),
}


def milliseconds(value):
    if isinstance(value, bool):
        raise ValueError('TIMESTAMP_INVALID')
    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('TIMESTAMP_NOT_UTC')
    return int(parsed.timestamp() * 1000)


def positive(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_export(root):
    """Never repairs/truncates journals. Corrupt/torn lines are reported, not used."""
    root = Path(root).resolve(strict=True)
    rows, manifest, issues = {}, [], Counter()
    for system, names in LAYOUT.items():
        directory = root / system
        if root.name == system:
            directory = root
        for name in names:
            path = directory / name
            if not path.exists():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('INPUT_SYMLINK_REJECTED')
            content = path.read_bytes()
            records = []
            if path.suffix == '.jsonl':
                for line in content.splitlines(keepends=True):
                    if not line.endswith(b'\n'):
                        issues['TORN_LINE_NOT_MODIFIED'] += 1
                        continue
                    try:
                        record = json.loads(line)
                        if not isinstance(record, dict):
                            raise ValueError
                        records.append(record)
                    except (ValueError, UnicodeError):
                        issues['INVALID_JSONL_ROW'] += 1
            else:
                try:
                    record = json.loads(content)
                    if not isinstance(record, dict):
                        raise ValueError
                    records.append(record)
                except (ValueError, UnicodeError):
                    issues['INVALID_JSON_FILE'] += 1
            rows[(system, name)] = records
            manifest.append(dict(path=str(path.relative_to(root)).replace('\\', '/'),
                                 sha256=hashlib.sha256(content).hexdigest(), bytes=len(content), rows=len(records)))
    return rows, manifest, issues


def event_records(rows, as_of, issues):
    """Only actual immutable journal events. Never derive events from snapshots."""
    candidates = []
    for row in rows.get(('copilot_audit', 'signals.jsonl'), []):
        try:
            if row.get('source') != 'FORWARD_LIVE':
                issues['NON_FORWARD_SOURCE_EXCLUDED'] += 1
                continue
            stamp = milliseconds(row['signal_time'])
            if milliseconds(row['closed_15m_time']) > stamp:
                raise ValueError
            if row['side'] not in ('LONG', 'SHORT') or not positive(row['reference_price']):
                raise ValueError
            if row.get('entry_quality') not in ('GOOD', 'CAUTION', 'POOR'):
                raise ValueError
            candidates.append(dict(system='copilot_audit', identity=str(row['event_id']),
                event='LONG_ALLOWED' if row['side'] == 'LONG' else 'SHORT_ALLOWED', side=row['side'],
                observed_at=stamp, candle_time=milliseconds(row['closed_15m_time']),
                reference=row['reference_price'], quality=row['entry_quality'], timeframe='15m',
                version=str(row.get('software_version', 'UNKNOWN')),
                trend4=row.get('trend4'), trend1=row.get('trend1'), momentum=row.get('ml_rsi'),
                flow=row.get('taker_buy'), structure=row.get('structure'), volatility=row.get('volatility')))
        except (KeyError, ValueError, TypeError, OverflowError):
            issues['INVALID_SIGNAL_EXCLUDED'] += 1
    for row in rows.get(('mlrsi', 'igod_mlrsi_events.jsonl'), []):
        if row.get('event') not in CONFIRMED or row.get('candle_complete') is not True:
            issues['NON_CONFIRMED_EVENT_EXCLUDED'] += 1
            continue
        try:
            if (row.get('symbol') != 'BTCUSDT' or row.get('source') != 'LOW'
                    or row.get('shadow_only') is not True or row.get('trade_authority') is not False
                    or row.get('timeframe') not in ('15m', '1h', '4h') or not positive(row['close'])):
                raise ValueError
            stamp = milliseconds(row['recorded_at_utc'])
            closed = milliseconds(row['candle_timestamp_utc'])
            if stamp < closed:
                raise ValueError
            tf = row['timeframe']
            interval = {'15m': 900000, '1h': 3600000, '4h': 14400000}[tf]
            # Catch-up can be journalized with old candle timestamps. Do not
            # relabel that as an event observed prospectively at the old price.
            if stamp - closed >= interval:
                issues['DELAYED_OR_CATCHUP_EVENT_EXCLUDED'] += 1
                continue
            event = row['event']
            candidates.append(dict(system='mlrsi', identity=str(row['dedupe_key']), event=event,
                side='LONG' if 'GREEN' in event else 'SHORT', observed_at=stamp, candle_time=closed,
                reference=row['close'], quality='NA', timeframe=tf,
                version=str(row['config_version']), observation_lag_ms=stamp - closed))
        except (KeyError, ValueError, TypeError, OverflowError):
            issues['INVALID_SIGNAL_EXCLUDED'] += 1
    unique, conflicts = {}, set()
    for event in candidates:
        if event['observed_at'] > as_of:
            issues['AFTER_AS_OF_EXCLUDED'] += 1
            continue
        key = (event['system'], event['version'], event['identity'])
        if key in unique:
            if event != unique[key]:
                conflicts.add(key)
            else:
                issues['EXACT_DUPLICATE_IGNORED'] += 1
        else:
            unique[key] = event
    issues['CONFLICTING_EVENTS_EXCLUDED'] += len(conflicts)
    return sorted((event for key, event in unique.items() if key not in conflicts),
                  key=lambda e: (e['observed_at'], e['system'], e['identity']))


def load_market(path):
    rows = []
    with Path(path).open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            candle = [int(row['time']), *(float(row[k]) for k in ('open', 'high', 'low', 'close'))]
            t, o, h, low, close = candle
            if t % STEP or not all(positive(v) for v in candle[1:]) or not low <= min(o, close) <= max(o, close) <= h:
                raise ValueError('INVALID_MARKET_CSV')
            if rows and t <= rows[-1][0]:
                raise ValueError('MARKET_ORDER_OR_DUPLICATE')
            rows.append(candle)
    return rows


def evaluate(event, market, hours, as_of, times=None, stored=None):
    """Signal close reference; post-observation complete 5m bars, no fill/PnL claim."""
    stamp = event['observed_at']
    if as_of < stamp + hours * 3600000:
        return dict(status='PENDING')
    if market is None:
        prior = (stored or {}).get((event['identity'], hours)) if event['system'] == 'copilot_audit' else None
        if prior and prior.get('status') == 'COMPLETE':
            try:
                values = [prior[k] for k in ('directional_return', 'mfe', 'mae')]
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                    raise ValueError
                if values[1] < 0 or values[2] > 0:
                    raise ValueError
                pairs = {}
                for a, b in PAIRS:
                    outcome = prior['first_passage'].get(f'{a:g}/{b:g}', 'UNAVAILABLE')
                    if outcome not in ('WIN', 'LOSS', 'NEITHER', 'AMBIGUOUS', 'UNAVAILABLE'):
                        raise ValueError
                    pairs[f'+{a * 100:g}/-{b * 100:g}'] = outcome
                return dict(status='COMPLETE', mean_return=values[0], mfe=values[1], mae=values[2],
                            first_passage=pairs, evaluation_source='EXISTING_FORWARDED_OUTCOME')
            except (ValueError, KeyError, TypeError):
                return dict(status='STORED_OUTCOME_INVALID')
        if prior and prior.get('status') == 'INCOMPLETE':
            return dict(status='INCOMPLETE')
        return dict(status='MARKET_DATA_PENDING')
    start = ((stamp + STEP - 1) // STEP) * STEP
    end = ((stamp + hours * 3600000) // STEP) * STEP
    times = times if times is not None else [r[0] for r in market]
    bars = market[bisect.bisect_left(times, start):bisect.bisect_left(times, end)]
    if [r[0] for r in bars] != list(range(start, end, STEP)) or not bars or bars[-1][0] + STEP > as_of:
        return dict(status='INCOMPLETE')
    price, long = event['reference'], event['side'] == 'LONG'
    favorable = [r[2] / price - 1 if long else 1 - r[3] / price for r in bars]
    adverse = [r[3] / price - 1 if long else 1 - r[2] / price for r in bars]
    passages = {}
    for up, down in PAIRS:
        outcome = 'NEITHER'
        for good, bad in zip(favorable, adverse):
            hit_up, hit_down = good >= up - 1e-12, bad <= -down + 1e-12
            if hit_up or hit_down:
                outcome = 'AMBIGUOUS' if hit_up and hit_down else 'WIN' if hit_up else 'LOSS'
                break
        passages[f'+{up * 100:g}/-{down * 100:g}'] = outcome
    return dict(status='COMPLETE', mean_return=bars[-1][4] / price - 1 if long else 1 - bars[-1][4] / price,
                mfe=max(0., *favorable), mae=min(0., *adverse), first_passage=passages,
                coverage_start=start, coverage_end=end)


def summarize(events, market, as_of, stored=None):
    groups = defaultdict(list)
    times = [r[0] for r in market] if market is not None else None
    for event in events:
        keys = [(event['system'], event['version'], event['timeframe'], event['event'], 'ALL')]
        year = datetime.fromtimestamp(event['observed_at'] / 1000, timezone.utc).year
        keys.append((event['system'], event['version'], event['timeframe'], event['event'], f'YEAR_{year}'))
        if event['system'] == 'copilot_audit':
            keys += [('copilot_audit', event['version'], '15m', 'ALL_CONFIRMED', q)
                     for q in ('ALL', event['quality'], event['side'])]
            for field in ('trend4', 'trend1', 'momentum', 'structure', 'volatility'):
                value = event.get(field)
                if value in ('BULL', 'BEAR', 'GREEN', 'NEUTRAL', 'RED', 'BULLISH', 'BEARISH', 'MIXED',
                             'NORMAL', 'ELEVATED', 'HIGH'):
                    keys.append(('copilot_audit', event['version'], '15m', event['event'], field + '_' + value))
        for key in keys:
            groups[key].append(event)
    output = []
    for key, cohort in sorted(groups.items()):
        horizons = {}
        for hours in HORIZONS:
            outcomes = [evaluate(e, market, hours, as_of, times, stored) for e in cohort]
            complete = [r for r in outcomes if r['status'] == 'COMPLETE']
            status = dict(Counter(r['status'] for r in outcomes))
            passage_stats = {}
            for pair in [f'+{a * 100:g}/-{b * 100:g}' for a, b in PAIRS]:
                counts = Counter(r['first_passage'][pair] for r in complete)
                n = len(complete) - counts['AMBIGUOUS'] - counts['UNAVAILABLE']
                passage_stats[pair] = dict(counts=counts, evaluable=n,
                                           favorable_first=counts['WIN'] / n if n else None)
            horizons[str(hours)] = dict(status_counts=status, mature_complete=len(complete),
                mean_return=statistics.mean(r['mean_return'] for r in complete) if complete else None,
                median_return=statistics.median(r['mean_return'] for r in complete) if complete else None,
                median_mfe=statistics.median(r['mfe'] for r in complete) if complete else None,
                median_mae=statistics.median(r['mae'] for r in complete) if complete else None,
                sample_warning='VERY_SMALL_N_LT_10' if len(complete) < 10 else 'SMALL_N_LT_20' if len(complete) < 20 else None,
                first_passage=passage_stats)
        output.append(dict(system=key[0], version=key[1], timeframe=key[2], event=key[3], cohort=key[4],
                           n=len(cohort), first_observed=min(e['observed_at'] for e in cohort),
                           last_observed=max(e['observed_at'] for e in cohort), horizons=horizons))
    return output


def run(input_dir, output_dir, as_of, market_csv=None):
    root, out = Path(input_dir).resolve(strict=True), Path(output_dir).resolve()
    if out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('OUTPUT_MUST_BE_DISJOINT_FROM_INPUT')
    if market_csv and Path(market_csv).resolve().is_relative_to(out):
        raise ValueError('OUTPUT_MUST_NOT_CONTAIN_MARKET_SOURCE')
    rows, manifest, issues = read_export(root)
    events = event_records(rows, as_of, issues)
    market_hash = sha(Path(market_csv)) if market_csv else None
    market = load_market(market_csv) if market_csv else None
    stored, conflicts = {}, set()
    for row in rows.get(('copilot_audit', 'outcomes.jsonl'), []):
        if row.get('source') != 'FORWARD_LIVE':
            continue
        if not isinstance(row.get('hours'), int) or not isinstance(row.get('event_id'), str):
            issues['INVALID_OUTCOME_EXCLUDED'] += 1
            continue
        key = (row['event_id'], row['hours'])
        prior = stored.get(key)
        if prior and prior.get('status') == 'COMPLETE':
            if row.get('status') == 'COMPLETE' and prior != row:
                conflicts.add(key)
        else:
            stored[key] = row
    for key in conflicts:
        stored.pop(key, None)
    issues['CONFLICTING_OUTCOMES_EXCLUDED'] += len(conflicts)
    cohorts = summarize(events, market, as_of, stored)
    audit_states = rows.get(('copilot_audit', 'state.json'), [])
    lost = audit_states[-1].get('lost_observations') if audit_states else None
    if not isinstance(lost, int) or isinstance(lost, bool) or lost < 0:
        lost = None
    verified = {r['path']: r['sha256'] for r in manifest}
    for name, digest in verified.items():
        if sha(root / name) != digest:
            raise ValueError('INPUT_CHANGED_DURING_ANALYSIS')
    if market_csv and sha(Path(market_csv)) != market_hash:
        raise ValueError('MARKET_CHANGED_DURING_ANALYSIS')
    report = dict(schema=1, source='IMPORTED_OBSERVATION_JOURNALS', as_of=as_of,
        forward_volume_data='EXPORTED_COPY_READ_ONLY' if manifest else 'NO_RECOGNIZED_EXPORTED_JOURNALS',
        original_files_unchanged=True, manifest=manifest, market_sha256=market_hash,
        no_signal_reconstruction=True, issues=dict(issues), cohorts=cohorts,
        early_breakout=dict(journal_rows=len(rows.get(('early_breakout', 'events.jsonl'), [])),
                            outcomes_rows=len(rows.get(('early_breakout', 'outcomes.jsonl'), [])),
                            classification_unchanged='NO EDGE', performance_not_inferred=True),
        stored_outcomes_rows=len(rows.get(('copilot_audit', 'outcomes.jsonl'), [])),
        coverage=dict(copilot_lost_observations=lost,
                      copilot_snapshot_rows=len(rows.get(('copilot_audit', 'snapshots.jsonl'), [])),
                      mlrsi_catchup_identification='Delayed >=1 TF excluded; recent recovery not fully identifiable from journal schema'),
        note='Signal-price statistics; no executions, fees, account PnL, significance or strategy promotion.')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'forward_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                                       allow_nan=False) + '\n', encoding='utf-8')
    lines = ['# Forward journals — análisis offline', '',
             f"As-of UTC ms: {as_of}. Journals: {len(manifest)}. Eventos observados únicos: {len(events)}.",
             'Los originales no se modifican. Versiones y TF no se mezclan.',
             'Estadísticas de señal, no rentabilidad de cuenta. Sin costes ni fills.', '',
             '| Sistema/config/TF/evento/cohorte | n | 24h maduros | 24h media | 24h mediana | 24h MFE | 24h MAE | +1/-1 | +2/-1 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(v):
        return 'NA' if v is None else f'{v * 100:.2f}%'
    for cohort in cohorts:
        h = cohort['horizons']['24']
        name = '/'.join(str(cohort[k]) for k in ('system', 'version', 'timeframe', 'event', 'cohort'))
        lines.append(f"| {name} | {cohort['n']} | {h['mature_complete']} | {fmt(h['mean_return'])} | "
                     f"{fmt(h['median_return'])} | {fmt(h['median_mfe'])} | {fmt(h['median_mae'])} | "
                     f"{fmt(h['first_passage']['+1/-1']['favorable_first'])} | "
                     f"{fmt(h['first_passage']['+2/-1']['favorable_first'])} |")
        if h['sample_warning']:
            lines.append('Muestra insuficiente/pequeña: no concluir edge. ' + h['sample_warning'])
    if market is None:
        lines += ['', 'Sin CSV público 5m: se aprovechan outcomes FORWARD_LIVE completos ya almacenados; '
                  'otros horizontes/barreras permanecen MARKET_DATA_PENDING / UNAVAILABLE.']
    lines += ['', 'Contadores de incidencias: ' + json.dumps(dict(issues), sort_keys=True),
              'First-passage: AMBIGUOUS excluido; NEITHER no es éxito; pendientes no son pérdidas.',
              'Los archivos de snapshots/outcomes constan en el inventario; no generan señales nuevas.']
    (out / 'FORWARD_REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--as-of', required=True, help='Explicit UTC timestamp, e.g. 2026-10-15T19:00:00Z')
    parser.add_argument('--market-csv', help='Offline public closed 5m CSV: time,open,high,low,close')
    args = parser.parse_args()
    report = run(args.input_dir, args.output_dir, milliseconds(args.as_of), args.market_csv)
    print('FORWARD_IMPORT_OK', len(report['manifest']), 'files;', len(report['cohorts']), 'cohorts')


if __name__ == '__main__':
    main()
