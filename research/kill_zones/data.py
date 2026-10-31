"""Public archive acquisition only; no private endpoint, keys or trade adapter."""
import argparse,calendar,csv,hashlib,io,json,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
M5=300000
HOUR=3600000
HOST='https://data.binance.vision/data/futures/um/monthly/'
MONTHS=tuple(f'{y}-{m:02}' for y in range(2023,2027) for m in range(1,13)
             if (2023,9)<=(y,m)<=(2026,9))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def iso(ms):return datetime.fromtimestamp(int(ms)/1000,timezone.utc).isoformat()
def stamp(text):return int(datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()*1000)
def url(kind,month):
    if month not in MONTHS:raise ValueError('MONTH_NOT_IN_PROTOCOL')
    if kind=='bars':return HOST+f'klines/BTCUSDT/5m/BTCUSDT-5m-{month}.zip'
    if kind=='funding':return HOST+f'fundingRate/BTCUSDT/BTCUSDT-fundingRate-{month}.zip'
    raise ValueError('UNKNOWN_ARCHIVE_KIND')
def read(cache,kind,month):
    stem=Path(cache)/f'{kind}-{month}'
    raw=stem.with_suffix('.zip').read_bytes()
    expected=stem.with_suffix('.checksum').read_text('utf-8').split()[0]
    if sha(raw)!=expected:raise ValueError('PUBLIC_CHECKSUM_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist())!=1:raise ValueError('ARCHIVE_MEMBERS')
        rows=list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))
    if rows and not rows[0][0].isdigit():rows=rows[1:]
    return rows,dict(kind=kind,month=month,url=url(kind,month),checksum_url=url(kind,month)+'.CHECKSUM',
                     sha256=expected,bytes=len(raw),rows=len(rows))
def download(cache,months=MONTHS):
    import requests
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    def task(pair):
        kind,month=pair;stem=cache/f'{kind}-{month}'
        if stem.with_suffix('.zip').exists() and stem.with_suffix('.checksum').exists():
            read(cache,kind,month);return
        with requests.Session() as s:
            s.trust_env=False
            payload=[]
            for suffix in ('','.CHECKSUM'):
                r=s.get(url(kind,month)+suffix,timeout=(8,45),allow_redirects=False)
                if r.status_code!=200:raise ValueError('PUBLIC_HTTP_'+str(r.status_code))
                payload.append(r.content)
        if sha(payload[0])!=payload[1].decode().split()[0]:raise ValueError('PUBLIC_CHECKSUM_MISMATCH')
        stem.with_suffix('.zip').write_bytes(payload[0])
        stem.with_suffix('.checksum').write_bytes(payload[1])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(task,[(k,m) for m in months for k in ('bars','funding')]))
def validate(a,interval=M5):
    a=np.asarray(a,float)
    if a.ndim!=2 or a.shape[1]!=7 or not len(a) or not np.all(np.isfinite(a)):raise ValueError('BAR_SCHEMA')
    if np.any(a[:,0]%interval) or np.any(np.diff(a[:,0])<=0):raise ValueError('BAR_TIME_OR_DUPLICATE')
    o,h,l,c=a[:,1:5].T
    if np.any(a[:,1:5]<=0) or np.any(h<np.maximum(o,c)) or np.any(l>np.minimum(o,c)) or np.any(h<l):raise ValueError('BAD_OHLC')
    if np.any(a[:,5:]<0) or np.any(a[:,6]>a[:,5]):raise ValueError('BAD_VOLUME')
    return a
def aggregate(a,width,base=M5):
    validate(a,base);ids=(a[:,0]//width).astype(np.int64)
    cuts=np.r_[0,np.flatnonzero(np.diff(ids))+1,len(a)];out=[]
    for i,j in zip(cuts[:-1],cuts[1:]):
        g=a[i:j];t=int(ids[i]*width)
        if len(g)!=width//base or not np.array_equal(g[:,0],np.arange(t,t+width,base)):continue
        out.append([t,g[0,1],g[:,2].max(),g[:,3].min(),g[-1,4],g[:,5].sum(),g[:,6].sum()])
    return np.asarray(out,float).reshape(-1,7)
def load(cache,months=MONTHS):
    bars=[];funds=[];sources=[]
    for month in months:
        rows,r=read(cache,'bars',month);sources.append(r)
        if not rows or any(len(x)!=12 for x in rows):raise ValueError('KLINE_SCHEMA')
        if any(int(x[6])!=int(x[0])+M5-1 for x in rows):raise ValueError('KLINE_CLOSE_TIME')
        a=validate([[float(x[k]) for k in (0,1,2,3,4,5,9)] for x in rows])
        y,m=map(int,month.split('-'))
        lo=int(datetime(y,m,1,tzinfo=timezone.utc).timestamp()*1000)
        hi=lo+calendar.monthrange(y,m)[1]*24*HOUR
        if np.any((a[:,0]<lo)|(a[:,0]>=hi)):raise ValueError('WRONG_MONTH')
        bars.append(a)
        rows,r=read(cache,'funding',month);sources.append(r)
        if not rows or any(len(x)!=3 or float(x[1])!=8 for x in rows):raise ValueError('FUNDING_SCHEMA_OR_INTERVAL')
        funds.extend([[int(x[0]),float(x[2])] for x in rows])
    a=validate(np.concatenate(bars));f=np.asarray(funds,float)
    if (not np.all(np.isfinite(f)) or np.any(np.diff(f[:,0])<=0)
        or np.any(np.diff(f[:,0]//(8*HOUR))!=1)):raise ValueError('FUNDING_GAP_OR_DUPLICATE')
    if f[0,0]//(8*HOUR)*8*HOUR>a[0,0] or (f[-1,0]//(8*HOUR)+1)*8*HOUR<a[-1,0]+M5:raise ValueError('FUNDING_COVERAGE')
    hourly=aggregate(a,HOUR)
    gaps=np.flatnonzero(np.diff(a[:,0])!=M5)
    manifest=dict(venue='BINANCE_USDM_PERPETUAL',symbol='BTCUSDT',historical_not_forward=True,
        no_virgin_holdout=True,first_open=iso(a[0,0]),last_close=iso(a[-1,0]+M5),
        rows_5m=len(a),rows_1h=len(hourly),funding_rows=len(f),duplicate_count=0,
        bars_sha256=sha(a.astype('<f8').tobytes()),hourly_sha256=sha(hourly.astype('<f8').tobytes()),
        funding_sha256=sha(f.astype('<f8').tobytes()),normalization='UTC milliseconds; float64 OHLCV; no filling; raw funding milliseconds preserved',
        funding_max_offset_ms=int(max(f[:,0]%(8*HOUR))),
        funding_mark_price='LAST_CLOSED_5M_TRADE_PRICE_PROXY_NOT_EXACT_SETTLEMENT_MARK',
        gaps=[dict(after=iso(a[i,0]),before=iso(a[i+1,0]),missing=int((a[i+1,0]-a[i,0])/M5)-1) for i in gaps],
        archives=sources)
    return a,hourly,f,manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--download',action='store_true')
    args=p.parse_args()
    if args.download:download(args.cache)
    a,h,f,m=load(args.cache)
    out=Path(args.cache)/'manifest.json';out.write_text(json.dumps(m,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in m.items() if k!='archives'}))
