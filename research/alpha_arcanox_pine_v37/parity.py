"""Offline comparison with REAL Pine Logs; no fabricated TradingView observations.

CLI requires logs from the diagnostic copy and exact input metadata. Synthetic
test rows exercise the comparator only; they are never parity evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
from .core import Candle
from .profiles import PINE_A, SOURCE_SHA256
from .replay import Replay

NUMERIC = ('aHigh','aLow','lHigh','lLow','amplitude','topBoxHeight','bottomBoxHeight',
           'topAnchor','bottomAnchor','newTopTarget','newBottomTarget','highGuideValue',
           'lowGuideValue','globalHigh','globalLow','targetTop','targetBottom','aCount','lCount','direction')
BOOLEAN = ('inAsia','inLondon','startAsia','endAsia','startLondon','endLondon','asiaReady',
           'measureNow','pairReady','topInAsia','bottomInAsia','highConfirmed','lowConfirmed',
           'longBreak','shortBreak','upperTouch','lowerTouch','fired','highAlerted','lowAlerted')
PREFIX = 'KZ_PARITY_V37='


def read_logs(path):
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if PREFIX not in line:
            continue
        rows.append(json.loads(line.split(PREFIX,1)[1].strip()))
    if not rows:
        raise ValueError('NO_REAL_PINE_RECORDS')
    return rows


def compare(rows, atol=1e-7):
    if not rows:
        raise ValueError('NO_REAL_PINE_RECORDS')
    engine = Replay(PINE_A); errors = []; compared = 0; cycles = 0
    ticker = rows[0].get('tickerid')
    if not ticker or ':' not in ticker:
        raise ValueError('EXACT_TRADINGVIEW_TICKER_REQUIRED')
    expected = dict(timeframe='60', source_sha256=SOURCE_SHA256, standard_chart=True,
                    asiaTZ='America/New_York', londonTZ='America/New_York',
                    asiaStartHour=20, asiaCandles=4, londonStartHour=2, londonCandles=4,
                    topInsetPct=3.0, bottomInsetPct=3.0, topUSD=500.0, bottomUSD=500.0)
    for row in rows:
        if row.get('tickerid') != ticker or any(row.get(k) != v for k,v in expected.items()):
            raise ValueError('PROFILE_A_METADATA_MISMATCH')
        if type(row.get('mintick')) not in (int,float) or not row['mintick'] > 0:
            raise ValueError('MINTICK_REQUIRED')
        if row.get('confirmed') is not True:
            raise ValueError('UNCONFIRMED_TRADINGVIEW_ROW')
        if type(row.get('time')) is not int or row.get('time_close') != row['time']+3_600_000:
            raise ValueError('TRADINGVIEW_TIME_SCHEMA_MISMATCH')
        bar = Candle(row['time'],*(float(row[k]) for k in ('open','high','low','close')))
        py = engine.append(bar,as_of=row['time_close'])
        if py['measureNow']:
            cycles += 1
        # Require a fresh complete pair after the log begins. No initial stale-state fit.
        if not cycles:
            continue
        compared += 1
        for key in NUMERIC+BOOLEAN:
            if key not in row:
                raise ValueError('MISSING_PINE_FIELD:'+key)
            a, b = row[key], py[key]
            if key in BOOLEAN:
                equal = a is b
            elif a is None or b is None:
                equal = a is b
            else:
                equal = type(a) in (int,float) and abs(a-b) <= atol
            if not equal:
                errors.append(dict(time=row['time'],field=key,pine=a,python=b))
    return dict(status=('MATCH_FOR_SUPPLIED_LOGS' if compared and not errors else
                        'MISMATCH' if errors else 'INSUFFICIENT_COMPLETE_CYCLES'),
                evidence='CALLER_SUPPLIED_RECORDS_NOT_INDEPENDENTLY_AUTHENTICATED',
                tickerid=ticker, profile='PINE_A', input_rows=len(rows), compared_rows=compared,
                complete_cycles=cycles, absolute_tolerance=atol, mismatches=errors,
                alpha_original_parity='NOT_PROVEN', profitability='NOT_EVALUATED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pine_logs',type=Path)
    p.add_argument('--out',type=Path,required=True)
    args = p.parse_args()
    if args.out.resolve() == args.pine_logs.resolve():
        raise ValueError('DO_NOT_OVERWRITE_EVIDENCE')
    result = compare(read_logs(args.pine_logs))
    result['source_sha256'] = hashlib.sha256(args.pine_logs.read_bytes()).hexdigest()
    with args.out.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    print(result['status'])


if __name__ == '__main__':
    main()
