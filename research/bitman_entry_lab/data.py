"""Explicit offline archive loader. Only the download command performs public GETs."""
import argparse
import calendar
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np

M5=300000
HOUR=12*M5
START=1577836800000
END=int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp()*1000)
MONTHS=tuple(f'{y}-{m:02}' for y in range(2020,2027) for m in range(1,13) if (y,m)<(2026,9))
HOST='https://data.binance.vision/data/futures/um/monthly/'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def iso(t): return datetime.fromtimestamp(int(t)/1000,timezone.utc).isoformat()
def url(kind,month):
    if kind=='bars': return HOST+f'klines/BTCUSDT/5m/BTCUSDT-5m-{month}.zip'
    if kind=='funding': return HOST+f'fundingRate/BTCUSDT/BTCUSDT-fundingRate-{month}.zip'
    raise ValueError('UNKNOWN_DATA_KIND')

def read_archive(cache,kind,month):
    stem=Path(cache)/f'{kind}-{month}'
    raw=stem.with_suffix('.zip').read_bytes()
    check=stem.with_suffix('.checksum').read_text('utf-8').split()[0]
    if sha(raw)!=check: raise ValueError('ARCHIVE_CHECKSUM_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist())!=1: raise ValueError('ARCHIVE_MEMBER_SCHEMA')
        rows=list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))
    if rows and not rows[0][0].isdigit(): rows=rows[1:]
    record=dict(kind=kind,month=month,url=url(kind,month),sha256=check,size=len(raw),rows=len(rows))
    return rows,record

def validate_bars(a,interval=M5):
    a=np.asarray(a,float)
    if a.ndim!=2 or a.shape[1]!=7 or not len(a) or not np.all(np.isfinite(a)): raise ValueError('BAR_SCHEMA')
    if np.any(a[:,0]%interval) or np.any(np.diff(a[:,0])<=0): raise ValueError('BAR_ORDER')
    if (np.any(a[:,1:5]<=0) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4]))
        or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,2]<a[:,3])
        or np.any(a[:,5]<0) or np.any(a[:,6]<0) or np.any(a[:,6]>a[:,5])):
        raise ValueError('BAR_VALUES')
    return a

def load(cache,months=MONTHS):
    arrays=[];funds=[];records=[]
    for month in months:
        rows,record=read_archive(cache,'bars',month);records.append(record)
        if not rows or any(len(r)!=12 for r in rows): raise ValueError('KLINE_12_COLUMNS_REQUIRED')
        x=np.asarray([[float(r[k]) for k in (0,1,2,3,4,5,9)] for r in rows])
        if any(int(r[6])!=int(r[0])+M5-1 for r in rows): raise ValueError('BAD_CLOSE_TIME')
        y,m=map(int,month.split('-'))
        lo=int(datetime(y,m,1,tzinfo=timezone.utc).timestamp()*1000)
        hi=lo+calendar.monthrange(y,m)[1]*24*HOUR
        if np.any((x[:,0]<lo)|(x[:,0]>=hi)): raise ValueError('WRONG_ARCHIVE_MONTH')
        arrays.append(validate_bars(x))
        rows,record=read_archive(cache,'funding',month);records.append(record)
        # Binance funding archive columns: calc_time, funding_interval_hours, last_funding_rate.
        if not rows or any(len(r)!=3 for r in rows): raise ValueError('FUNDING_SCHEMA')
        if any(float(r[1])!=8 for r in rows): raise ValueError('FUNDING_INTERVAL_UNSUPPORTED')
        funds.extend([[int(r[0]),float(r[2])] for r in rows])
    a=validate_bars(np.concatenate(arrays));f=np.asarray(funds,float)
    if not np.all(np.isfinite(f)) or np.any(np.diff(f[:,0])<=0): raise ValueError('FUNDING_ORDER')
    gaps=np.flatnonzero(np.diff(a[:,0])!=M5)
    manifest=dict(venue='BINANCE_USDM_PERPETUAL',symbol='BTCUSDT',source='OFFICIAL_BINANCE_VISION_USDM_MONTHLY',
        historical_not_forward_observed=True,no_virgin_holdout=True,first_open=iso(a[0,0]),
        last_close=iso(a[-1,0]+M5),rows_5m=len(a),funding_rows=len(f),interval_ms=M5,
        normalization='UTC milliseconds; OHLCV float64 without resampling fill; funding raw calc_time preserved',
        bars_array_sha256=sha(a.astype('<f8').tobytes()),funding_array_sha256=sha(f.astype('<f8').tobytes()),
        gaps=[dict(after=iso(a[i,0]),before=iso(a[i+1,0]),missing=int((a[i+1,0]-a[i,0])/M5)-1) for i in gaps],
        archives=records)
    return a,f,manifest

def download(cache):
    import requests
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    with requests.Session() as session:
        session.trust_env=False
        for month in MONTHS:
            for kind in ('bars','funding'):
                stem=cache/f'{kind}-{month}'
                if stem.with_suffix('.zip').exists() and stem.with_suffix('.checksum').exists():
                    read_archive(cache,kind,month);continue
                content=[]
                for suffix in ('','.CHECKSUM'):
                    r=session.get(url(kind,month)+suffix,timeout=(5,30),allow_redirects=False)
                    if r.status_code!=200: raise ValueError('PUBLIC_ARCHIVE_HTTP_'+str(r.status_code))
                    content.append(r.content)
                if sha(content[0])!=content[1].decode().split()[0]: raise ValueError('CHECKSUM')
                stem.with_suffix('.zip').write_bytes(content[0]);stem.with_suffix('.checksum').write_bytes(content[1])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');p.add_argument('--cache',required=True)
    args=p.parse_args()
    if args.download: download(args.cache)
    _,_,m=load(args.cache);print(json.dumps({k:v for k,v in m.items() if k!='archives'}))

