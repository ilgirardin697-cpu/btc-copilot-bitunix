"""Compare future genuine diagnostic exports. Synthetic inputs are only tests."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .data import HOUR,load
from .indicators import calculate,signals

PREFIX='IGOD_CONFLUENCE_AUDIT_V0='
FIELDS=('kon_trend','kon_signal','adx','plus_di','minus_di','ao','bbwp','atr')


def compare(records,bars,ticker='BINANCE:BTCUSDT.P'):
    if ticker!='BINANCE:BTCUSDT.P':raise ValueError('SEPARATE_VENUE_REQUIRED')
    f=calculate(bars);s=signals(f);lookup={int(t):i for i,t in enumerate(bars[:,0])};out=[]
    for p in records:
        if p['ticker']!=ticker or p['timeframe']!='60':raise ValueError('TICKER_OR_TIMEFRAME_MISMATCH')
        if p.get('adx_threshold')!=40 or p.get('bbwp_threshold')!=85:raise ValueError('CONFIGURATION_MISMATCH')
        t=p['open_time']
        if type(t) is not int or p['available_at']!=t+HOUR:raise ValueError('CAUSAL_TIMESTAMP_MISMATCH')
        if t not in lookup:
            out.append(dict(open_time=t,status='NO_INDEPENDENT_MARKET_OVERLAP'));continue
        i=lookup[t]
        price_error=max(abs(float(p[k])-bars[i,j]) for k,j in [('open',1),('high',2),('low',3),('close',4),('volume',5)])
        errors={k:None if p[k] is None or not np.isfinite(f[k][i]) else abs(float(p[k])-f[k][i]) for k in FIELDS}
        comparable=all(v is not None for v in errors.values())
        passed=comparable and price_error<=1e-8 and all(v<=1e-7 for v in errors.values()) and p['long']==bool(s['long'][i]) and p['short']==bool(s['short'][i])
        out.append(dict(open_time=t,available_at=p['available_at'],price_max_error=price_error,errors=errors,
                        signal_match=p['long']==bool(s['long'][i]) and p['short']==bool(s['short'][i]),
                        status='PASSED' if passed else 'DIFFERENCE_OR_INSUFFICIENT_WARMUP'))
    return dict(actual_records_provided=len(records),passed=sum(r['status']=='PASSED' for r in out),
        rows=out,source='OWNER_SUPPLIED_PINE_DIAGNOSTIC_LOGS_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED',
        parity_status='NO_ACTUAL_RECORDS' if not records else 'REQUIRES_SOURCE_AND_WARMUP_REVIEW',
        proprietary_bitman_parity='NOT_PROVEN',trade_authority='NONE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('logs');p.add_argument('--cache',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();raw=Path(a.logs).read_bytes();records=[]
    for r in csv.DictReader(raw.decode('utf-8-sig').splitlines()):
        message=r.get('Mensaje',r.get('Message',''))
        if PREFIX in message:records.append(json.loads(message.split(PREFIX,1)[1]))
    bars,_,_=load(a.cache);result=compare(records,bars);result['original_export_sha256']=hashlib.sha256(raw).hexdigest()
    path=Path(a.out)
    with path.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
