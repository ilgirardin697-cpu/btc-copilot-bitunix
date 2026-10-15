"""Public-only frozen input builder. The only transport is requests.get."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import requests
from .spec import CONFLUENCE_SHA, CUTOFF

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT/'research/cache/bitman'
ART = ROOT/'research/bitman/artifacts'
HOUR = 3600000
BASE = 'https://fapi.binance.com'
ALLOW = {'/fapi/v1/klines', '/fapi/v1/fundingRate'}


def stamp(s):
    return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aggregate(bars, interval, base=300000):
    """UTC complete groups only; never combine across a missing source candle."""
    bars=np.asarray(bars,float)
    if not len(bars): return np.empty((0,7))
    if interval % base or np.any(np.diff(bars[:,0])<=0): raise ValueError('SOURCE_ORDER_INVALID')
    buckets=(bars[:,0]//interval).astype(np.int64)
    starts=np.r_[0,np.flatnonzero(np.diff(buckets))+1]
    result=[]
    for i,j in zip(starts,np.r_[starts[1:],len(bars)]):
        group=bars[i:j]; opening=int(buckets[i]*interval)
        if len(group)!=interval//base or not np.array_equal(group[:,0],np.arange(opening,opening+interval,base)):
            continue
        result.append([opening,group[0,1],max(group[:,2]),min(group[:,3]),group[-1,4],
                       sum(group[:,5]),sum(group[:,6])])
    return np.asarray(result,float).reshape(-1,7)


def public_get(path, params, manifest):
    if path not in ALLOW: raise ValueError('PUBLIC_PATH_NOT_ALLOWED')
    key=hashlib.sha256(json.dumps([path,params],sort_keys=True).encode()).hexdigest()[:24]
    target=CACHE/(key+'.json')
    if target.exists(): raw=target.read_bytes()
    else:
        response=requests.get(BASE+path,params=params,timeout=30)
        if response.status_code!=200: raise RuntimeError(f'PUBLIC_HTTP_{response.status_code}')
        raw=response.content
        value=json.loads(raw)
        if not isinstance(value,list): raise ValueError('PUBLIC_SCHEMA_INVALID')
        target.write_bytes(raw)
    rows=json.loads(raw)
    if not isinstance(rows,list): raise ValueError('PUBLIC_SCHEMA_INVALID')
    manifest.append(dict(url=BASE+path,params=params,sha256=hashlib.sha256(raw).hexdigest(),rows=len(rows)))
    return rows


def hourly_range(start, end, manifest):
    result=[]
    while start<end:
        rows=public_get('/fapi/v1/klines',dict(symbol='BTCUSDT',interval='1h',startTime=start,endTime=end-1,limit=1500),manifest)
        if not rows: break
        for r in rows:
            t=int(r[0])
            if t+HOUR<=end:
                if int(r[6])!=t+HOUR-1: raise ValueError('INCOMPLETE_HOURLY_BAR')
                result.append([t,*map(float,r[1:6]),float(r[9])])
        next_start=int(rows[-1][0])+HOUR
        if next_start<=start: raise ValueError('PUBLIC_CURSOR_STALLED')
        start=next_start
    return np.asarray(result,float).reshape(-1,7)


def prepare():
    CACHE.mkdir(parents=True,exist_ok=True); ART.mkdir(parents=True,exist_ok=True)
    old=ROOT/'research/cache/confluence/data.npz'
    source=json.loads(subprocess.check_output(['git','show',CONFLUENCE_SHA+':research/confluence_artifacts/data_manifest.json'],cwd=ROOT))
    if not old.exists() or digest(old)!=source[-1]['normalized_sha256']:
        raise ValueError('VERIFIED_CONFLUENCE_CACHE_REQUIRED')
    z=np.load(old); bars=aggregate(z['bars'],HOUR); funding=z['funding']
    manifest=[dict(source_commit=CONFLUENCE_SHA,source_path='research/confluence_artifacts/data_manifest.json',
                   inherited_archive_manifest_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
                   dataset_sha256=digest(old),rows_5m=len(z['bars']),rows_1h=len(bars),funding_rows=len(funding))]
    end=stamp(CUTOFF)
    before=hourly_range(stamp('2019-10-01T00:00:00Z'),int(bars[0,0]),manifest)
    after=hourly_range(int(bars[-1,0])+HOUR,end,manifest)
    bars=np.concatenate([before,bars,after])
    start=int(funding[-1,0])+1; more=[]
    while start<end:
        rows=public_get('/fapi/v1/fundingRate',dict(symbol='BTCUSDT',startTime=start,endTime=end-1,limit=1000),manifest)
        if not rows: break
        more.extend([[int(r['fundingTime']),float(r['fundingRate'])] for r in rows])
        next_start=int(rows[-1]['fundingTime'])+1
        if next_start<=start: raise ValueError('PUBLIC_CURSOR_STALLED')
        start=next_start
    if more: funding=np.concatenate([funding,np.array(more,float)])
    if np.any(~np.isfinite(bars)) or np.any(np.diff(bars[:,0])!=HOUR) or bars[-1,0]+HOUR!=end:
        raise ValueError('CLOSED_HOURLY_COVERAGE_FAILED')
    if np.any(bars[:,0]%HOUR) or np.any(bars[:,3]<=0) or np.any(bars[:,2]<np.maximum(bars[:,1],bars[:,4])) or np.any(bars[:,3]>np.minimum(bars[:,1],bars[:,4])):
        raise ValueError('OHLC_INVALID')
    if np.any((bars[:,6]<0)|(bars[:,6]>bars[:,5])) or np.any(np.diff(funding[:,0])<=0):
        raise ValueError('FLOW_OR_FUNDING_INVALID')
    # Verify each expected8h settlement has a historical row within its actual
    # millisecond stamp; no fabricated zero funding. Preserve exact timestamps.
    expected=np.arange(stamp('2020-01-01T00:00:00Z'),end,8*HOUR,dtype=np.int64)
    actual=(funding[:,0]//HOUR).astype(np.int64)*HOUR
    if not set(expected).issubset(set(actual)): raise ValueError('FUNDING_COVERAGE_GAP')
    target=CACHE/'hourly.npz'
    np.savez_compressed(target,bars=bars,funding=funding)
    manifest.append(dict(rows=len(bars),first_timestamp=int(bars[0,0]),last_timestamp=int(bars[-1,0]),
                         cutoff=end,funding_rows=len(funding),dataset_sha256=digest(target),
                         array_sha256=hashlib.sha256(bars.tobytes()+funding.tobytes()).hexdigest(),
                         venue='BINANCE_USDM_PERPETUAL',funding_expected_8h=len(expected),complete=True))
    (ART/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('BITMAN_PUBLIC_DATA_READY',len(bars),len(funding))


def load(end=None):
    manifest=json.loads((ART/'data_manifest.json').read_text())
    path=CACHE/'hourly.npz'
    if digest(path)!=manifest[-1]['dataset_sha256']: raise ValueError('DATASET_CHANGED')
    z=np.load(path)
    bars,funding=z['bars'],z['funding']
    if end is not None:
        bars=bars[bars[:,0]+HOUR<=end]
        funding=funding[funding[:,0]<end]
    return bars,funding


if __name__=='__main__':
    prepare()
