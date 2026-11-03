"""Owner-supplied REAL TradingView observations, separate from synthetic tests.

Never seed the replay from aHigh/aLow or other logged indicator state. The
unprimed first cycle remains excluded even if its displayed levels are known.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .core import Candle, HOUR, display_tick, project
from .parity import compare, read_logs, NUMERIC, BOOLEAN
from .profiles import PINE_A, OWNER_B
from .replay import Replay

HERE=Path(__file__).resolve().parent
FIXTURE=HERE/'fixtures/tradingview_20261103'
LOGS=FIXTURE/'Killzone_PineLogs_64_registros_para_Codex.txt'
REVIEW=FIXTURE/'Killzone_revision_datos_2026-11-03.json'
LOG_SHA='3fc02a8fc12664591766df834c869b10d66cf54606ce12b5e9f87ce54b9d3097'


def utc(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat().replace('+00:00','Z')


def load_evidence():
    raw=LOGS.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=LOG_SHA:
        raise ValueError('REAL_LOG_FIXTURE_HASH_CHANGED')
    lines=raw.decode('utf-8-sig').splitlines()
    if len(lines)!=64 or any(not s.startswith('KZ_PARITY_V37=') for s in lines):
        raise ValueError('UNEXPECTED_LOG_CONTENT')
    rows=read_logs(LOGS)
    expected=set(NUMERIC+BOOLEAN)|{'tickerid','timeframe','source_sha256','mintick',
        'standard_chart','asiaTZ','londonTZ','asiaStartHour','asiaCandles','londonStartHour',
        'londonCandles','topInsetPct','bottomInsetPct','topUSD','bottomUSD','time','time_close',
        'open','high','low','close','confirmed'}
    if any(set(row)!=expected or row['tickerid']!='BINANCE:BTCUSDT' for row in rows):
        raise ValueError('NON_MARKET_OR_UNEXPECTED_FIELDS')
    if any(b['time']-a['time']!=HOUR for a,b in zip(rows,rows[1:])):
        raise ValueError('REAL_LOG_GAP_OR_DUPLICATE')
    revision=json.loads(REVIEW.read_text(encoding='utf-8-sig'))
    if revision['converted_logs_sha256']!=LOG_SHA or revision['rows']!=len(rows):
        raise ValueError('EXTERNAL_REVIEW_PROVENANCE_MISMATCH')
    return rows


def bars_from_rows(rows):
    return [Candle(r['time'],*(float(r[k]) for k in ('open','high','low','close'))) for r in rows]


def analyze():
    rows=load_evidence();baseline=compare(rows)
    if baseline['status']!='MATCH_FOR_SUPPLIED_LOGS':
        raise ValueError('REAL_PARITY_FAILED')
    replay=Replay(PINE_A);full=[];checked=[];cycles=0
    fields={k:dict(compared=0,numeric_pairs=0,null_pairs=0,mismatches=0,max_abs_error=0.0)
            for k in NUMERIC+BOOLEAN}
    for row,bar in zip(rows,bars_from_rows(rows)):
        py=replay.append(bar,as_of=row['time_close'])
        cycles+=int(py['measureNow'])
        full.append((row,py,bool(cycles)))
        if not cycles:continue
        checked.append(row['time'])
        for k in NUMERIC+BOOLEAN:
            stat=fields[k];stat['compared']+=1;a,b=row[k],py[k]
            if a is None or b is None:
                stat['null_pairs']+=1
                stat['mismatches']+=int(a is not b)
            elif k in BOOLEAN:
                stat['mismatches']+=int(a is not b)
            else:
                stat['numeric_pairs']+=1
                stat['max_abs_error']=max(stat['max_abs_error'],abs(a-b))
                stat['mismatches']+=int(abs(a-b)>baseline['absolute_tolerance'])
    signals=[];measurements=[];body_on_a=[];cycle=None;body_recorded=False
    for row,py,valid in full:
        if row['startAsia']:
            cycle=None;body_recorded=False
        if row['measureNow']:
            cycle=row['time'];body_recorded=False
            arithmetic=project(row['aHigh'],row['aLow'],row['lHigh'],row['lLow'])
            keys=('highGuideValue','lowGuideValue','newTopTarget','newBottomTarget')
            measurements.append(dict(measure_bar_open=utc(row['time']),
                measure_bar_close=utc(row['time_close']),
                complete_ohlc_replay_validated=bool(py['measureNow'] and valid),
                HIGH=row['globalHigh'],LOW=row['globalLow'],SUPERIOR=row['targetTop'],INFERIOR=row['targetBottom'],
                displayed_HIGH=display_tick(row['globalHigh'],row['mintick']),
                displayed_LOW=display_tick(row['globalLow'],row['mintick']),
                displayed_SUPERIOR=display_tick(row['targetTop'],row['mintick']),
                displayed_INFERIOR=display_tick(row['targetBottom'],row['mintick']),
                algebra_from_logged_extrema_only_max_error=max(abs(arithmetic[k]-row[k]) for k in keys),
                first_cycle_caveat=None if py['measureNow'] else 'LOGGED_EXTREMA_ALGEBRA_ONLY_NOT_RECONSTRUCTED_FROM_MISSING_ASIA_OHLC'))
        if row['highConfirmed'] or row['lowConfirmed']:
            long=row['highConfirmed']
            signals.append(dict(side='LONG' if long else 'SHORT',bar_open_utc=utc(row['time']),
                confirmed_at_utc=utc(row['time_close']),open=row['open'],close=row['close'],
                HIGH=row['globalHigh'],LOW=row['globalLow'],replay_validated=valid,
                python_confirmation=(py['highConfirmed'] if long else py['lowConfirmed']) if valid else None,
                whole_body_on_PINE_A_levels=(min(row['open'],row['close'])>row['globalHigh'] if long
                    else max(row['open'],row['close'])<row['globalLow']),
                interpretation='PINE_A_CLOSE_ONLY_NOT_OWNER_B'))
        if cycle is not None and row['pairReady'] and not body_recorded:
            up=min(row['open'],row['close'])>row['globalHigh']
            down=max(row['open'],row['close'])<row['globalLow']
            if up or down:
                body_on_a.append(dict(side='LONG' if up else 'SHORT',bar_open_utc=utc(row['time']),
                    confirmed_at_utc=utc(row['time_close']),HIGH=row['globalHigh'],LOW=row['globalLow'],
                    open=row['open'],close=row['close'],interpretation='BODY_ONLY_DIAGNOSTIC_ON_A_LEVELS_NOT_OWNER_B'))
                body_recorded=True
    dst=[]
    for row in rows[:8]:
        date=datetime.fromtimestamp(row['time']/1000,timezone.utc)
        ny=date.astimezone(PINE_A.tz)
        dst.append(dict(utc=utc(row['time']),new_york=ny.isoformat(),fold=ny.fold,
                        owner_fixed_utc4=date.astimezone(OWNER_B.tz).isoformat(),
                        inLondon_PINE_A=row['inLondon']))
    result=dict(**baseline,source_log_sha256=LOG_SHA,source_log_bytes=LOGS.stat().st_size,
        external_revision_sha256=hashlib.sha256(REVIEW.read_bytes()).hexdigest(),
        external_original_csv_sha256_status='DECLARED_IN_EXTERNAL_REVIEW_ORIGINAL_CSV_NOT_AVAILABLE',
        first_bar_open_utc=utc(rows[0]['time']),last_bar_open_utc=utc(rows[-1]['time']),
        last_close_utc=utc(rows[-1]['time_close']),skipped_rows=len(rows)-len(checked),
        comparison_first_bar_open_utc=utc(checked[0]),comparison_last_bar_open_utc=utc(checked[-1]),
        by_field=fields,max_abs_error=max(v['max_abs_error'] for v in fields.values()),
        measurement_records=measurements,logged_PINE_A_signals=signals,
        replay_validated_signal_count=sum(s['replay_validated'] for s in signals),
        PINE_A_body_diagnostics=body_on_a,dst_clock=dst,
        GO='GO_OFFLINE_OWNER_B_EVALUATION_ONLY_NOT_LIVE_OR_PROFITABILITY_VALIDATION')
    return result


if __name__=='__main__':
    print(json.dumps(analyze(),ensure_ascii=False,indent=2,allow_nan=False))
