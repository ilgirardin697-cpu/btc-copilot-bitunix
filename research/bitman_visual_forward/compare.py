"""Explicit offline TradingView CSV audit; reports no original-chart parity claim."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from .formulas import calculate,HOUR,SERIES

ABS_TOL=1e-8
REL_TOL=1e-9
KEYS=('open_ms','close_ms','closed','seed_start_ms','open','high','low','close')
PROFILES=('FROZEN_DEFINITION_V0','TV_BUILTINS_OR_ORIGINAL')
VENUES=('UNKNOWN','BINANCE_SPOT','BINANCE_USDM_PERPETUAL')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def number(value):
    if not isinstance(value,str):raise ValueError('CSV_NUMERIC_VALUE')
    if value.strip().lower() in ('','na','nan','n/a'):return np.nan
    try:x=float(value)
    except (TypeError,ValueError):raise ValueError('CSV_NUMERIC_VALUE') from None
    if not np.isfinite(x):raise ValueError('CSV_NONFINITE')
    return x

def series_diff(actual,expected,times):
    a=np.asarray(actual,float);e=np.asarray(expected,float)
    both=np.isfinite(a)&np.isfinite(e);missing=np.isfinite(a)!=np.isfinite(e)
    mismatch=both&~np.isclose(a,e,atol=ABS_TOL,rtol=REL_TOL)
    diff=abs(a[both]-e[both])
    bad=np.flatnonzero(mismatch|missing)
    return dict(compared=int(both.sum()),missing_pattern_differences=int(missing.sum()),
        numeric_mismatches=int(mismatch.sum()),max_abs_error=float(diff.max()) if len(diff) else None,
        median_abs_error=float(np.median(diff)) if len(diff) else None,
        sign_disagreements=int(np.sum(np.sign(a[both])!=np.sign(e[both]))),
        first_difference_open_ms=int(times[bad[0]]) if len(bad) else None)

def formula_match(differences):
    # A rounded value inside numeric tolerance must not hide a changed sign/event.
    return all(not v['numeric_mismatches'] and not v['missing_pattern_differences']
        and not v['sign_disagreements'] for v in differences.values())

def compare(raw,meta,reference_ohlc=None):
    if len(raw)>32*1024*1024:raise ValueError('CSV_TOO_LARGE')
    if meta.get('csv_sha256')!=sha(raw):raise ValueError('CSV_HASH')
    if meta.get('timeframe_minutes')!=60 or meta.get('timestamp_unit')!='UNIX_MILLISECONDS':
        raise ValueError('UNCONFIRMED_TIMEFRAME_OR_UNIT')
    if meta.get('profile') not in PROFILES or meta.get('venue') not in VENUES:
        raise ValueError('REFERENCE_PROFILE')
    cutoff=meta.get('exported_at_ms')
    if type(cutoff) is not int or cutoff<0:raise ValueError('EXPORT_TIME_REQUIRED')
    mapping=meta.get('columns')
    if not isinstance(mapping,dict) or not set(KEYS).issubset(mapping):raise ValueError('EXPLICIT_COLUMN_MAPPING_REQUIRED')
    if not set(mapping).issubset(set(KEYS)|set(SERIES)|{'native_di_plus','native_di_minus','native_adx','native_atr'}):
        raise ValueError('UNSUPPORTED_SERIES_MAPPING')
    if not all(isinstance(k,str) and isinstance(v,str) and len(v)<=256 for k,v in mapping.items()):raise ValueError('COLUMN_MAPPING_SCHEMA')
    if len(set(mapping.values()))!=len(mapping):raise ValueError('DUPLICATE_COLUMN_MAPPING')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('CSV_HEADERS')
    if not all(v in reader.fieldnames for v in mapping.values()):raise ValueError('MAPPED_COLUMN_MISSING')
    rows=[];exported={k:[] for k in mapping if k not in KEYS};excluded=0;seed=None
    for index,row in enumerate(reader):
        if index>=100000:raise ValueError('CSV_TOO_MANY_ROWS')
        values={k:number(row[v]) for k,v in mapping.items()}
        if values['closed'] not in (0.,1.):raise ValueError('CONFIRMED_FLAG')
        if values['closed']==0:
            excluded+=1;continue
        if excluded:raise ValueError('OPEN_CANDLE_NOT_FINAL')
        t=values['open_ms'];close=values['close_ms'];first=values['seed_start_ms']
        if not all(np.isfinite(x) and int(x)==x for x in (t,close,first)) or close!=t+HOUR:
            raise ValueError('CLOSE_AVAILABILITY_TIME')
        if close>cutoff:raise ValueError('FUTURE_CANDLE')
        if seed is None:seed=int(first)
        if seed!=first:raise ValueError('SEED_CHANGED')
        rows.append([t,values['open'],values['high'],values['low'],values['close']])
        for k in exported:exported[k].append(values[k])
    if len(rows)<200:raise ValueError('INSUFFICIENT_COMPARISON_WINDOW')
    if rows[0][0]!=seed:raise ValueError('SEED_HISTORY_MISSING')
    a=np.asarray(rows,float);expected=calculate(a)
    if 'ao' not in exported or 'adx' not in exported:raise ValueError('AO_AND_ADX_COLUMNS_REQUIRED')
    if meta['profile']=='FROZEN_DEFINITION_V0':
        if not set(SERIES).issubset(exported):raise ValueError('FROZEN_EXPORT_INCOMPLETE')
        script=Path(__file__).parent/'pine/visual_export_v0.pine'
        if meta.get('pine_source_sha256')!=sha(script.read_bytes().replace(b'\r\n',b'\n')):
            raise ValueError('EXPORTER_SOURCE_UNVERIFIED')
    differences={k:series_diff(v,expected[k],a[:,0]) for k,v in exported.items() if k in expected}
    native={k:series_diff(v,expected[k.removeprefix('native_')],a[:,0])
        for k,v in exported.items() if k.startswith('native_')}
    matched=formula_match(differences)
    market_comparison='NOT_PROVIDED'
    if reference_ohlc is not None:
        if meta.get('venue')!='BINANCE_USDM_PERPETUAL' or meta.get('ticker_id')!='BINANCE:BTCUSDT.P' or meta.get('venue_verified') is not True:
            raise ValueError('CROSS_VENUE_COMPARISON_FORBIDDEN')
        ref=np.asarray(reference_ohlc,float)
        if a.shape!=ref.shape or not np.array_equal(a,ref):market_comparison='OHLC_DIFFERENCES'
        else:market_comparison='EXACT_OHLC_MATCH'
    status=('FORMULA_MATCH_ON_EXPORTED_OHLC' if matched else 'FORMULA_DIFFERENCES') if meta['profile']=='FROZEN_DEFINITION_V0' else 'ORIGINAL_OR_NATIVE_SERIES_DIAGNOSTIC_ONLY'
    return dict(status=status,scope='OFFLINE_NUMERIC_AUDIT_ONLY',csv_sha256=sha(raw),rows=len(a),
        first_open_ms=int(a[0,0]),last_available_at_ms=int(a[-1,0]+HOUR),excluded_open_rows=excluded,
        seed_start_ms=seed,venue=meta['venue'],market_comparison=market_comparison,
        series=differences,native_comparison=native,
        original_screenshot_parity='NOT_PROVEN',exact_bitman_parity='NOT_PROVEN',
        pine_execution_verification='EXTERNAL_EXPORT_REQUIRED_NOT_PROVEN_BY_SYNTHETIC_TESTS')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',required=True);p.add_argument('--metadata',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    try:
        out=Path(args.output).resolve();research_root=Path(__file__).resolve().parents[1]
        if (out.exists() or not out.is_relative_to(research_root)
            or out in (Path(args.csv).resolve(),Path(args.metadata).resolve())):raise ValueError('OUTPUT_NOT_FRESH_RESEARCH_ARTIFACT')
        result=compare(Path(args.csv).read_bytes(),json.loads(Path(args.metadata).read_text('utf-8')))
        Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(result['status'])
    except (ValueError,OSError,UnicodeError):raise SystemExit('VISUAL_REFERENCE_AUDIT_FAILED_NO_PAYLOAD') from None
