"""Official public archives only. No credentials, trading API or runtime imports."""
import argparse
import concurrent.futures
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import requests

HERE=Path(__file__).resolve().parent
HOUR=3600000


def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)
def iso(t):return datetime.fromtimestamp(int(t)/1000,timezone.utc).isoformat().replace('+00:00','Z')
def sha(raw):return hashlib.sha256(raw).hexdigest()


def months(first,last):
    y,m=map(int,first.split('-'));end=tuple(map(int,last.split('-')))
    while (y,m)<=end:
        yield f'{y:04d}-{m:02d}'
        y,m=(y+1,1) if m==12 else (y,m+1)


def get(url):
    if not any(url.startswith('https://data.binance.vision/data/futures/um/'+kind+'/') for kind in ('monthly','daily')):
        raise ValueError('UNAPPROVED_PUBLIC_SOURCE')
    with requests.Session() as s:
        s.trust_env=False
        r=s.get(url,timeout=40,allow_redirects=False)
        if r.status_code!=200:raise ValueError('PUBLIC_HTTP_'+str(r.status_code)+':'+url)
        if len(r.content)>2000000:raise ValueError('ARCHIVE_SIZE')
        return r.content


def acquire(cache,family,month,frequency='monthly'):
    name=f'BTCUSDT-fundingRate-{month}.zip' if family=='fundingRate' else f'BTCUSDT-1h-{month}.zip'
    relative=f'{family}/BTCUSDT/'+('' if family=='fundingRate' else '1h/')+name
    url='https://data.binance.vision/data/futures/um/'+frequency+'/'+relative
    folder=cache/family;folder.mkdir(parents=True,exist_ok=True)
    path=folder/name;check=folder/(name+'.CHECKSUM')
    checkraw=check.read_bytes() if check.exists() else get(url+'.CHECKSUM')
    expected=checkraw.decode().split()[0]
    if len(expected)!=64:raise ValueError('INVALID_OFFICIAL_CHECKSUM')
    raw=path.read_bytes() if path.exists() else get(url)
    if sha(raw)!=expected:raise ValueError('OFFICIAL_CHECKSUM_MISMATCH')
    for p,body in ((check,checkraw),(path,raw)):
        if not p.exists():
            with p.open('xb') as f:f.write(body)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=1 or not z.infolist()[0].filename.endswith('.csv'):raise ValueError('ARCHIVE_SCHEMA')
        csvraw=z.read(z.infolist()[0]);rows=list(csv.reader(io.StringIO(csvraw.decode('utf-8-sig'))))
    return dict(family=family,month=month,frequency=frequency,file=str(path.relative_to(cache)).replace('\\','/'),
                url=url,sha256=sha(raw),bytes=len(raw),official_checksum_sha256=sha(checkraw),
                csv_sha256=sha(csvraw),rows=len(rows)),rows


def decode_klines(rows,allow_gaps=False):
    data=[]
    for r in rows:
        if str(r[0]).lower() in ('open_time','open time'):continue
        if len(r)!=12:raise ValueError('KLINE_NOT12')
        t,closed=int(r[0]),int(r[6])
        if t%HOUR or closed!=t+HOUR-1:raise ValueError('USDM_H1_TIMESTAMP_OR_CLOSE')
        o,h,l,c,v=map(float,r[1:6]);taker=float(r[9])
        if not np.isfinite([o,h,l,c,v,taker]).all() or min(o,h,l,c)<=0 or v<0 or taker<0 or taker>v+1e-7:
            raise ValueError('NONFINITE_PRICE_VOLUME')
        if h<max(o,l,c) or l>min(o,h,c):raise ValueError('BAD_OHLC')
        data.append([t,o,h,l,c,v])
    a=np.asarray(data,float)
    if not len(a) or (np.diff(a[:,0])<=0).any() or (not allow_gaps and (np.diff(a[:,0])!=HOUR).any()):raise ValueError('GAP_OR_DUPLICATE')
    return a


def exact_funding_marks(cache,start,end):
    cursor=start;rows=[];records=[];folder=cache/'funding_api';folder.mkdir(exist_ok=True)
    for page in range(20):
        path=folder/f'{cursor}.json';url='https://fapi.binance.com/fapi/v1/fundingRate'
        params=dict(symbol='BTCUSDT',startTime=cursor,endTime=end-1,limit=1000)
        if path.exists():raw=path.read_bytes()
        else:
            with requests.Session() as s:
                s.trust_env=False;r=s.get(url,params=params,timeout=30,allow_redirects=False)
                if r.status_code!=200:raise ValueError('EXACT_FUNDING_MARK_BLOCKED_HTTP_'+str(r.status_code))
                raw=r.content
            with path.open('xb') as f:f.write(raw)
        batch=json.loads(raw)
        if not isinstance(batch,list):raise ValueError('FUNDING_API_NOT_LIST')
        records.append(dict(family='fundingRateREST',url=url,params=params,file=str(path.relative_to(cache)).replace('\\','/'),
                            bytes=len(raw),sha256=sha(raw),rows=len(batch),checksum='LOCAL_SHA256_OF_OFFICIAL_RESPONSE_NOT_OFFICIAL_CHECKSUM'))
        rows.extend(batch)
        if not batch or len(batch)<1000:break
        new_cursor=int(batch[-1]['fundingTime'])+1
        if new_cursor<=cursor:raise ValueError('FUNDING_PAGINATION')
        cursor=new_cursor
    else:raise ValueError('FUNDING_TOO_MANY_PAGES')
    result={}
    for row in rows:
        t=int(row['fundingTime']);rate=float(row['fundingRate']);mark=float(row['markPrice']) if row.get('markPrice') else np.nan
        if row['symbol']!='BTCUSDT' or not np.isfinite(rate) or (np.isfinite(mark) and mark<=0) or t in result:
            raise ValueError('FUNDING_API_SCHEMA_OR_DUPLICATE')
        result[t]=(rate,mark)
    return result,records


def fetch(cache):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    jobs=[('klines',m) for m in months('2022-09','2026-10')]
    jobs += [(f,m) for f in ('fundingRate','markPriceKlines') for m in months('2022-11','2026-10')]
    records=[];batches={f:[] for f in ('klines','fundingRate','markPriceKlines')}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(acquire,cache,*job) for job in jobs]
        for future in futures:
            record,rows=future.result();records.append(record);batches[record['family']].extend(rows)
    bars=decode_klines(batches['klines']);monthly_marks=decode_klines(batches['markPriceKlines'],allow_gaps=True)
    missing_marks=np.setdiff1d(np.arange(stamp('2022-11-01T00:00:00Z'),stamp('2026-11-01T00:00:00Z'),HOUR),monthly_marks[:,0])
    allowed=json.loads((HERE/'DATA_RECOVERY_ADDENDUM.json').read_text())['dates']
    missing_days=sorted(set(iso(t)[:10] for t in missing_marks))
    if any(d not in allowed for d in missing_days):raise ValueError('UNDECLARED_MARK_DATA_GAP')
    for day in missing_days:
        record,rows=acquire(cache,'markPriceKlines',day,'daily');records.append(record)
        extra=decode_klines(rows)
        if not np.array_equal(extra[:,0],np.arange(stamp(day+'T00:00:00Z'),stamp(day+'T00:00:00Z')+24*HOUR,HOUR)):
            raise ValueError('DAILY_RECOVERY_NOT24_REAL_HOURS')
        monthly_marks=np.concatenate([monthly_marks,extra])
    marks=monthly_marks[np.argsort(monthly_marks[:,0])]
    if not np.array_equal(marks[:,0],np.arange(stamp('2022-11-01T00:00:00Z'),stamp('2026-11-01T00:00:00Z'),HOUR)):
        raise ValueError('REMAINING_MARK_GAP_OR_DUPLICATE')
    start=stamp('2022-09-01T00:00:00Z');end=stamp('2026-11-01T00:00:00Z')
    if not np.array_equal(bars[:,0],np.arange(start,end,HOUR)):raise ValueError('FULL_HISTORY_MISSING')
    exact,api_records=exact_funding_marks(cache,stamp('2022-11-01T00:00:00Z'),end);records.extend(api_records)
    funding=[]
    for r in batches['fundingRate']:
        if r[0]=='calc_time':continue
        if len(r)!=3:raise ValueError('FUNDING_SCHEMA')
        t,interval,rate=int(r[0]),int(r[1]),float(r[2])
        if not np.isfinite(rate) or interval<=0:raise ValueError('FUNDING_UNVERIFIED_MARK_TIME')
        if t not in exact or abs(exact[t][0]-rate)>1e-12:raise ValueError('MONTHLY_REST_FUNDING_MISMATCH')
        j=np.searchsorted(marks[:,0],t//HOUR*HOUR)
        if j>=len(marks) or marks[j,0]!=t//HOUR*HOUR:raise ValueError('MISSING_MARK_BOUND_BAR')
        funding.append([t,rate,exact[t][1],interval,marks[j,3],marks[j,2]])
    fund=np.asarray(funding,float)
    if not len(fund) or (np.diff(fund[:,0])<=0).any():raise ValueError('FUNDING_ORDER_DUPLICATE')
    # Validate the supplied settlement cadence, rather than inventing missing rates.
    if any((fund[i,0]//HOUR-fund[i-1,0]//HOUR)!=fund[i,3] for i in range(1,len(fund))):raise ValueError('FUNDING_COVERAGE_GAP')
    np.savez_compressed(cache/'validated_market.npz',bars=bars,marks=marks,funding=fund)
    manifest=dict(venue='BINANCE_USDM_PERPETUAL',symbol='BTCUSDT',interval='1h',
        downloaded_at=datetime.now(timezone.utc).isoformat(),first_open=iso(bars[0,0]),last_open=iso(bars[-1,0]),
        bars=len(bars),funding_settlements=len(fund),gaps=0,duplicates=0,imputed=0,
        monthly_mark_missing_hours=len(missing_marks),official_daily_mark_recovered_hours=len(missing_marks),
        exact_funding_marks_missing=int(np.isnan(fund[:,2]).sum()),
        funding_missing_mark_policy='EXACT_NET_BLOCKED_WHERE_USED; SEPARATE_PREDECLARED_H1_MARK_HIGH_LOW_SCENARIOS',
        raw_schema=12,timestamps='UTC_MILLISECONDS_OPEN_TIMES',archives=records,
        npz_sha256=sha((cache/'validated_market.npz').read_bytes()),
        protocol_sha256=sha((HERE/'protocol.json').read_bytes().replace(b'\r\n',b'\n')))
    (cache/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='archives'}))


def load(cache):
    cache=Path(cache);m=json.loads((cache/'data_manifest.json').read_text())
    if sha((cache/'validated_market.npz').read_bytes())!=m['npz_sha256']:raise ValueError('VALIDATED_DATA_CHANGED')
    for r in m['archives']:
        if sha((cache/r['file']).read_bytes())!=r['sha256']:raise ValueError('RAW_DATA_CHANGED')
    with np.load(cache/'validated_market.npz') as z:return z['bars'],z['funding'],m


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',default='research/cache/confluence_1h_market_data')
    fetch(p.parse_args().cache)
