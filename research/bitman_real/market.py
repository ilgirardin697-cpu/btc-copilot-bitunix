"""Read verified PUBLIC data files only. This module has no HTTP transport."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from .config import HOUR,REJECTED_PHASE2_SHA

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(bars,interval=HOUR):
    a=np.asarray(bars,float)
    if a.ndim!=2 or a.shape[1]!=7 or not len(a) or np.any(~np.isfinite(a)):
        raise ValueError('MARKET_SCHEMA_INVALID')
    if np.any(a[:,0]%interval) or np.any(np.diff(a[:,0])!=interval):
        raise ValueError('MARKET_GAP_OR_ORDER_INVALID')
    if (np.any(a[:,1:5]<=0) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4]))
        or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,3]>a[:,2])
        or np.any(a[:,5]<0) or np.any((a[:,6]<0)|(a[:,6]>a[:,5]))):
        raise ValueError('MARKET_VALUES_INVALID')
    return a


def aggregate(hourly,interval,now_ms):
    a=validate(hourly);a=a[a[:,0]+HOUR<=now_ms]
    if not len(a):return np.empty((0,7))
    buckets=(a[:,0]//interval).astype(np.int64)
    starts=np.r_[0,np.flatnonzero(np.diff(buckets))+1];out=[]
    for i,j in zip(starts,np.r_[starts[1:],len(a)]):
        group=a[i:j];opening=int(buckets[i]*interval)
        if len(group)!=interval//HOUR or not np.array_equal(group[:,0],np.arange(opening,opening+interval,HOUR)):
            continue
        if opening+interval>now_ms:continue
        out.append([opening,group[0,1],max(group[:,2]),min(group[:,3]),group[-1,4],sum(group[:,5]),sum(group[:,6])])
    return np.asarray(out,float).reshape(-1,7)


def verified_cache(path=None):
    """Reuse DATA ONLY from Phase2; never import/reuse its rejected rules."""
    raw=subprocess.check_output(['git','show',REJECTED_PHASE2_SHA+':research/bitman/artifacts/data_manifest.json'],cwd=ROOT)
    manifest=json.loads(raw);path=Path(path) if path else ROOT/'research/cache/bitman/hourly.npz'
    if sha(path)!=manifest[-1]['dataset_sha256']:raise ValueError('PUBLIC_CACHE_CHECKSUM_MISMATCH')
    with np.load(path,allow_pickle=False) as z:bars=z['bars'].copy()
    validate(bars)
    return bars,dict(source='HISTORICAL_PUBLIC_MARKET_DATA',venue='BINANCE_USDM_PERPETUAL',
        inherited_manifest=manifest,inherited_commit=REJECTED_PHASE2_SHA,
        inherited_manifest_sha256=hashlib.sha256(raw).hexdigest(),rows=len(bars),dataset_sha256=sha(path),
        note='Market data reuse only. Phase2 remains REJECT; no Phase2 rules imported.')


def load_csv(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:
        rows=csv.DictReader(stream)
        a=np.array([[float(r[k]) for k in ('time','open','high','low','close','volume','taker_buy_volume')] for r in rows])
    return validate(a)
