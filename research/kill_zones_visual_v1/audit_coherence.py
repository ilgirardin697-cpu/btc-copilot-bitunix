"""Thirty-day frozen-rule feasibility counts. No trade outcomes or optimization."""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from . import model
from .chart import svg_chart
from .data import COLUMNS, json_text, read_csv, sha

FROZEN_COMMIT = 'cc81cca28cf1b770ae8b9c22ad7c680821151e11'
FROZEN_MODEL_SHA = '20a646c5cd5300b6cb478d578a1904d446fd28a72ebb94ff527679345df926e2'
FIRST = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
URL = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09.zip'
MEMBER = 'BTCUSDT-5m-2026-09.csv'
DAYS = tuple(date(2026, 9, 1) + timedelta(days=i) for i in range(30))


def assert_frozen():
    if sha(Path(model.__file__)) != FROZEN_MODEL_SHA:
        raise ValueError('FROZEN_V1_MODEL_CHANGED')


def write(path, value):
    path.write_text(value, encoding='utf-8', newline='\n')


def extract_month(archive, checksum, out):
    """Reverify original public bytes; no loader/results imported from PR #40."""
    raw = archive.read_bytes()
    expected = checksum.read_text(encoding='utf-8').split()[0]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('OFFICIAL_ARCHIVE_CHECKSUM_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist() != [MEMBER]:
            raise ValueError('SOURCE_MEMBER_INVALID')
        rows = list(csv.reader(io.StringIO(z.read(MEMBER).decode('utf-8-sig'))))
    if rows and not rows[0][0].isdigit():
        rows = rows[1:]
    expected_times = list(range(FIRST, END, 300_000))
    if len(rows) != len(expected_times) or any(len(r) != 12 for r in rows):
        raise ValueError('SOURCE_ROW_COUNT_OR_SCHEMA')
    if [int(r[0]) for r in rows] != expected_times:
        raise ValueError('SOURCE_GAP_OR_DUPLICATE')
    if any(int(r[6]) != int(r[0]) + 299_999 for r in rows):
        raise ValueError('SOURCE_CLOSE_TIME')
    # Validate source OHLC/volume too, before aggregation could hide an error.
    for r in rows:
        o,h,l,c,v = (Decimal(r[i]) for i in (1,2,3,4,5))
        if (not all(p.is_finite() for p in (o,h,l,c,v)) or min(o,h,l,c) <= 0
                or v < 0 or l > min(o,c) or h < max(o,c) or l > h):
            raise ValueError('SOURCE_OHLC_INVALID')
    out.mkdir(parents=True, exist_ok=True)
    path = out/'BTCUSDT_USDM_1h_202609.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(COLUMNS)
        for i in range(0,len(rows),12):
            g = rows[i:i+12]
            w.writerow([g[0][0],g[0][1],max(Decimal(r[2]) for r in g),
                        min(Decimal(r[3]) for r in g),g[-1][4],sum(Decimal(r[5]) for r in g)])
    bars = read_csv(path)
    model.validate(bars)
    manifest = dict(symbol='BTCUSDT',venue='BINANCE_USDM_PERPETUAL',source_url=URL,
                    checksum_url=URL+'.CHECKSUM',archive_sha256=expected,
                    checksum_origin='Saved official checksum, verified locally; not re-fetched',
                    source_rows=len(rows),rows_1h=len(bars),source_interval='5m',interval='1h',
                    first_open=model.iso(FIRST),last_available=model.iso(END),
                    local_london_dates=[DAYS[0].isoformat(),DAYS[-1].isoformat()],
                    hourly_csv_sha256=sha(path),gaps=0,duplicates=0,filled=0,
                    aggregation='Exact 12 closed contiguous 5m; O first / H max / L min / C last / Decimal base-volume sum',
                    timezone='UTC milliseconds; available at open + 3600000; model clock America/New_York unchanged',
                    no_virgin_holdout=True,no_performance_evaluation=True)
    write(out/'data_manifest.json',json_text(manifest))
    return bars,manifest


def relation(a,l):
    if l.high > a.high and l.low < a.low:
        return 'LONDON_CONTAINS_ASIA'
    if a.high > l.high and a.low < l.low:
        return 'ASIA_CONTAINS_LONDON'
    if a.high == l.high or a.low == l.low:
        return 'TIED_BOUNDARY'
    return 'STRICTLY_ORDERED'


def diagnose(result, bars):
    row = dict(status=result['status'],geometry_valid=result['setup'] is not None,
               geometry_reason=result.get('reason'),confirmation=False,side=None,
               plan_status=None,rejection_reasons=[],rejection_partition=None)
    boxes = ((result['setup'].asia,result['setup'].london) if result['setup']
             else result.get('session_boxes'))
    if boxes:
        a,l = boxes
        row.update(box_relation=relation(a,l),asia_high=a.high,asia_low=a.low,
                   london_high=l.high,london_low=l.low)
    c = result['confirmation']
    if c is None:
        return row
    side = 1 if c['side'] == 'UP' else -1
    bar = next(b for b in bars if b.open_time == c['candle_open'])
    row.update(confirmation=True,side=c['side'],available_at=model.iso(c['available_at']),
               candle_open=model.iso(c['candle_open']),body_open=bar.open,body_close=bar.close,
               line_value=c['line_value'],target=c['target'],stop=c['stop'],
               target_not_ahead_of_line=side*(c['target']-c['line_value']) <= 0,
               target_not_ahead_of_signal_close=side*(c['target']-c['signal_close']) <= 0,
               plan_status=result['plan']['status'])
    if 'reference_entry' not in result['plan']:
        return row
    p = result['plan']
    target_bad = side*(p['target']-p['reference_entry']) <= 0
    stop_bad = side*(p['reference_entry']-p['stop']) <= 0
    reasons = (['TARGET_NOT_AHEAD_OF_ENTRY'] if target_bad else [])
    reasons += ['STOP_NOT_ON_PROTECTIVE_SIDE'] if stop_bad else []
    if (bool(reasons)) != (p['status'] == 'REJECTED_STOP_TARGET_ORDER'):
        raise ValueError('DIAGNOSTIC_DISAGREES_WITH_FROZEN_V1')
    row.update(reference_entry=p['reference_entry'],entry_gap_from_signal_close=p['reference_entry']-c['signal_close'],
               rejection_reasons=reasons,rejection_partition=('BOTH' if target_bad and stop_bad
               else 'TARGET_ONLY' if target_bad else 'STOP_ONLY' if stop_bad else None))
    return row


def counts(rows):
    def count(key):
        out = {}
        for r in rows:
            value = r.get(key)
            if value is not None:
                out[str(value)] = out.get(str(value),0)+1
        return out
    confirmed = [r for r in rows if r['confirmation']]
    valid_geometry = sum(r['geometry_valid'] for r in rows)
    plan_counts = count('plan_status')
    return dict(days=len(rows),valid_geometry=valid_geometry,invalid_geometry=len(rows)-valid_geometry,
                geometry_reasons=count('geometry_reason'),box_relations=count('box_relation'),
                confirmations=len(confirmed),confirmation_sides=count('side'),
                valid_geometry_without_confirmation=valid_geometry-len(confirmed),
                reference_plans=plan_counts.get('REFERENCE_PLAN',0),
                rejected_plans=plan_counts.get('REJECTED_STOP_TARGET_ORDER',0),
                pending_entries=plan_counts.get('ENTRY_PENDING',0),plan_statuses=plan_counts,
                rejection_partition=count('rejection_partition'),
                target_not_ahead_of_line=sum(bool(r.get('target_not_ahead_of_line')) for r in confirmed),
                target_not_ahead_of_signal_close=sum(bool(r.get('target_not_ahead_of_signal_close')) for r in confirmed),
                no_performance_evaluation=True,decision='NO_GO_FOR_VIDEO_STRATEGY_FORWARD_PAPER',
                decision_basis='Trigger identity and temporal anchors remain unverified; counts do not prove fidelity or edge')


def audit(bars, out):
    assert_frozen()
    if [b.open_time for b in bars] != list(range(FIRST,END,model.HOUR)):
        raise ValueError('AUDIT_REQUIRES_EXACT_720_HOURS')
    model.validate(bars)
    rows = []
    charts = out/'charts'
    charts.mkdir(parents=True,exist_ok=True)
    for day in DAYS:
        cutoff = model.boundary(day,20)
        result = model.observe(bars,day,cutoff)
        row = dict(day=day.isoformat(),as_of=model.iso(cutoff),**diagnose(result,bars))
        if result['confirmation']:
            early = model.observe(bars,day,result['confirmation']['available_at'])
            if json_text(early['confirmation']) != json_text(result['confirmation']) or json_text(early['plan']) != json_text(result['plan']):
                raise ValueError('CAUSAL_PREFIX_CHANGED')
        write(charts/f'{day}.svg',svg_chart(bars,result,f'BTCUSDT USD-M | {day} | FROZEN V1 COHERENCE ONLY'))
        write(charts/f'{day}.json',json_text(dict(observation=result,diagnostic=row)))
        rows.append(row)
    summary = counts(rows)
    summary.update(frozen_commit=FROZEN_COMMIT,model_sha256=FROZEN_MODEL_SHA,
                   closed_prefix_check='PASS_FOR_EVERY_CONFIRMATION',data_interval='2026-09-01/2026-10-01 UTC')
    write(out/'daily_audit.json',json_text(rows))
    write(out/'summary.json',json_text(summary))
    with (out/'daily_audit.csv').open('w',encoding='utf-8',newline='') as f:
        fields=sorted({key for row in rows for key in row})
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in r.items()})
    from html import escape
    cards = []
    for r in rows:
        day = r['day']
        label = r['geometry_reason'] or r['plan_status'] or r['status']
        cards.append(f'<section><h2>{day} — {escape(label)}</h2><a href="charts/{day}.json">JSON completo</a><img src="charts/{day}.svg" alt="{day} frozen V1"></section>')
    write(out/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><title>V1 — auditoría 30 días</title><style>body{background:#101824;color:#edf1f7;font:16px Arial;margin:20px}img{width:100%;max-width:1400px}a{color:#5ad8ec}section{margin:35px 0}</style><h1>V1 congelada — todos los 30 días de septiembre 2026</h1><p>No es un backtest de rentabilidad. Sin PnL ni selección de ejemplos favorables. Paridad de línea de ruptura: NO PROBADA.</p><p><a href="COHERENCE_AUDIT.md">Informe</a> · <a href="summary.json">Recuento</a> · <a href="daily_audit.csv">Todos los días CSV</a></p>'+''.join(cards)+'</html>\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--checksum',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    assert_frozen()
    bars,manifest=extract_month(args.archive,args.checksum,args.out)
    print(json_text(dict(data=manifest,summary=audit(bars,args.out))))


if __name__ == '__main__':
    main()
