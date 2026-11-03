"""ONLY public HTTPS GET to official Binance Vision; no credentials or fallback venue."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import requests
from .data import CACHE,HERE,read_archive,spec,ts,iso,HOUR,MINUTE


def months(start):
    year,month=map(int,start.split('-'))
    out=[]
    while (year,month)<=(2026,10):
        out.append(f'{year:04}-{month:02}')
        month+=1
        if month==13:year+=1;month=1
    return out


def fetch(interval,month):
    filename=f'BTCUSDT-{interval}-{month}.zip'
    url=f'https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/{interval}/{filename}'
    destination=CACHE/filename
    s=requests.Session();s.trust_env=False
    r=s.get(url+'.CHECKSUM',timeout=30,allow_redirects=False)
    if r.status_code!=200:raise RuntimeError(f'CHECKSUM_HTTP_{r.status_code}_{month}_{interval}')
    checksum=r.text.split()[0].lower()
    if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):
        raise ValueError('BAD_CHECKSUM_RESPONSE')
    if destination.exists():
        raw=destination.read_bytes()
    else:
        r=s.get(url,timeout=90,allow_redirects=False)
        if r.status_code!=200:raise RuntimeError(f'ZIP_HTTP_{r.status_code}_{month}_{interval}')
        raw=r.content
        if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('OFFICIAL_CHECKSUM_MISMATCH')
        with destination.open('xb') as f:f.write(raw)
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('CACHE_HASH_MISMATCH_NO_OVERWRITE')
    bars=read_archive(destination,interval)
    y,m=map(int,month.split('-'));ny,nm=(y+1,1) if m==12 else (y,m+1)
    start=ts(f'{month}-01T00:00:00Z');end=ts(f'{ny:04}-{nm:02}-01T00:00:00Z')
    step=HOUR if interval=='1h' else MINUTE
    if len(bars)!=(end-start)//step or bars[0].open_time!=start or bars[-1].available_at!=end:
        raise ValueError('MONTH_COVERAGE_INCOMPLETE')
    return dict(file=filename,url=url,checksum_url=url+'.CHECKSUM',sha256=checksum,
                bytes=len(raw),rows=len(bars),first_open=iso(start),last_available=iso(end),
                source_time_unit='microseconds',normalized_time_unit='milliseconds',
                schema_fields=12,official_checksum_verified=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interval',choices=('1h','1m'),required=True)
    a=p.parse_args();frozen=spec()
    CACHE.mkdir(parents=True,exist_ok=True)
    requested=months('2025-10' if a.interval=='1h' else '2025-11')
    result=dict(status='PENDING',interval=a.interval,venue='BINANCE_SPOT',symbol='BTCUSDT',
        protocol_sha256=hashlib.sha256((HERE/'specification.json').read_bytes()).hexdigest(),
        warmup_excluded_from_outcomes=True,archives=[])
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs=[pool.submit(fetch,a.interval,m) for m in requested]
            for m,job in zip(requested,jobs):
                record=job.result();result['archives'].append(record)
                print(json.dumps(dict(interval=a.interval,month=m,rows=record['rows'],checksum='OK')),flush=True)
        result['status']='COMPLETE'
    except Exception as exc:
        result.update(status='BLOCKED',error_type=type(exc).__name__,safe_code=str(exc)
            if isinstance(exc,(RuntimeError,ValueError)) else 'NETWORK_OR_LOCAL_IO_UNAVAILABLE')
    path=CACHE/f'manifest_{a.interval}.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print('DATASET_STATUS='+result['status'])
    if result['status']!='COMPLETE':raise SystemExit(1)


if __name__=='__main__':main()
