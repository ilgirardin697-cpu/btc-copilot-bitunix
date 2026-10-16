"""Future PUBLIC price measurements, separate from causal event generation."""
import numpy as np
from .config import HOUR


def first_passage(high,low,reference,up,down):
    upper=np.flatnonzero(high>=reference*(1+up));lower=np.flatnonzero(low<=reference*(1-down))
    u=int(upper[0]+1) if len(upper) else None;d=int(lower[0]+1) if len(lower) else None
    race='UNRESOLVED' if u is None and d is None else 'UP_FIRST' if d is None or u is not None and u<d else 'DOWN_FIRST' if u is None or d<u else 'AMBIGUOUS'
    return dict(up_first_hour=u,down_first_hour=d,race=race)


def measure(hourly,timestamp,reference,hours,cutoff):
    if reference<=0 or not np.isfinite(reference):raise ValueError('REFERENCE_INVALID')
    if timestamp+hours*HOUR>cutoff:return dict(complete=False,reason='HORIZON_OR_SPLIT_NOT_MATURE')
    i=int(np.searchsorted(hourly[:,0],timestamp));a=hourly[i:i+hours]
    if len(a)!=hours or not np.array_equal(a[:,0],timestamp+np.arange(hours)*HOUR):
        return dict(complete=False,reason='MISSING_CLOSED_HOURLY_DATA')
    high,low=a[:,2],a[:,3]
    one=first_passage(high,low,reference,.01,.01);two=first_passage(high,low,reference,.02,.02)
    return dict(complete=True,forward_return=float(a[-1,4]/reference-1),
        mfe=float(max(0,max(high)/reference-1)),mae=float(min(0,min(low)/reference-1)),
        first_up1_hour=one['up_first_hour'],first_down1_hour=one['down_first_hour'],
        first_up2_hour=two['up_first_hour'],first_down2_hour=two['down_first_hour'],
        race_1pct=one['race'],race_2pct=two['race'])


def summarize(items):
    valid=[x for x in items if x['complete']];n=len(valid)
    out=dict(n_total=len(items),n_complete=n,n_incomplete=len(items)-n)
    if not n:return out
    for key in ('forward_return','mfe','mae'):
        values=[r[key] for r in valid]
        out[key]=dict(mean=float(np.mean(values)),median=float(np.median(values)))
    for key in ('first_up1_hour','first_down1_hour','first_up2_hour','first_down2_hour'):
        hit=[r[key] for r in valid if r[key] is not None]
        out[key]=dict(n_hit=len(hit),hit_fraction=len(hit)/n,median_hour_if_hit=float(np.median(hit)) if hit else None)
    for key in ('race_1pct','race_2pct'):
        out[key]={tag:sum(r[key]==tag for r in valid)/n for tag in ('UP_FIRST','DOWN_FIRST','AMBIGUOUS','UNRESOLVED')}
    return out


def block_bootstrap(values,times,seed=9821,repetitions=500):
    if not len(values):return dict(n=0,mean=None,ci95=[None,None])
    weeks=np.asarray(times,dtype=np.int64)//(7*24*HOUR)
    labels=np.arange(weeks.min(),weeks.max()+1)
    sums=np.array([np.asarray(values)[weeks==w].sum() for w in labels])
    counts=np.array([sum(weeks==w) for w in labels]);rng=np.random.default_rng(seed);samples=[]
    for _ in range(repetitions):
        ids=rng.integers(0,len(labels),len(labels));n=counts[ids].sum()
        if n:samples.append(float(sums[ids].sum()/n))
    return dict(n=len(values),mean=float(np.mean(values)),ci95=np.quantile(samples,[.025,.975]).tolist(),
                repetitions=repetitions,seed=seed,blocks='7day calendar',independent_events=False)
