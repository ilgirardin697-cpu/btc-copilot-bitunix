"""Frozen public candle validation/aggregation only; no file loaders or strategies."""
import numpy as np
from .constants import HOUR

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
