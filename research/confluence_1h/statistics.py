"""Predeclared calendar-block uncertainty and matched timing controls. No fitting."""
from dataclasses import replace
import numpy as np
from .data import HOUR
from .engine import simulate,metrics

DAY=24*HOUR


def daily(trades,bars,start,end):
    origin=int(bars[start,0]//DAY)*DAY
    count=int((bars[end-1,0]-origin)//DAY)+1
    sums=np.zeros(count);counts=np.zeros(count)
    for t in trades:
        k=int((bars[t['entry_i'],0]-origin)//DAY);sums[k]+=t['net_r'];counts[k]+=1
    return sums,counts


def block_indices(n,replicates=2000):
    rng=np.random.default_rng(20261115)
    starts=rng.integers(0,n,(replicates,(n+6)//7))
    return ((starts[:,:,None]+np.arange(7))%n).reshape(replicates,-1)[:,:n]


def ratio_ci(sums,counts,confidence=.975,reference=None):
    if not counts.sum():return dict(ci=None,valid_replicates=0,unit='CALENDAR_7DAY_BLOCKS_INCLUDING_ZERO_EVENT_DAYS')
    ix=block_indices(len(sums));ns=counts[ix].sum(axis=1);ss=sums[ix].sum(axis=1);good=ns>0
    means=ss[good]/ns[good]
    if reference is not None:
        rs,rc=reference;rn=rc[ix].sum(axis=1);rr=rs[ix].sum(axis=1)
        good &=rn>0;means=ss[good]/ns[good]-rr[good]/rn[good]
    q=(1-confidence)/2
    return dict(ci=np.quantile(means,[q,1-q]).tolist() if len(means) else None,
                valid_replicates=len(means),unit='CALENDAR_7DAY_BLOCKS_INCLUDING_ZERO_EVENT_DAYS')


def random_controls(bars,features,signal,regime,funding,start,end,side,p,trials=200):
    """Match candidate count by month, side, closed4H regime. Never outcome-match."""
    from .data import iso
    labels=np.array([iso(t)[:7] for t in bars[:,0]])
    eligible=np.arange(start,end-p.hold_bars-1)
    eligible=eligible[np.isfinite(features['atr'][eligible])&np.isfinite(regime[eligible])]
    candidates=[]
    for sign,name in ((1,'long'),(-1,'short')):
        if side and side!=sign:continue
        ids=np.flatnonzero(signal[name]);ids=ids[(ids>=start)&(ids<end-p.hold_bars-1)]
        for month in sorted(set(labels[ids])):
            for r in (-1,0,1):
                n=int(((labels[ids]==month)&(regime[ids]==r)).sum())
                if n:candidates.append((sign,n,eligible[(labels[eligible]==month)&(regime[eligible]==r)]))
    rng=np.random.default_rng(20261115);rows=[];sums=[];counts=[]
    for trial in range(trials):
        long=np.zeros(len(bars),bool);short=long.copy();used=set()
        for sign,n,pool in candidates:
            pool=np.array([int(x) for x in pool if int(x) not in used])
            if len(pool)<n:raise ValueError('CONTROL_STRATUM_INSUFFICIENT_NO_FALLBACK')
            draw=rng.choice(pool,n,replace=False);used.update(draw)
            (long if sign==1 else short)[draw]=True
        deals,_,_=simulate(bars,features['atr'],long,short,funding,start,end,side,p,False)
        m=metrics(deals,None,p.initial,end-start)
        rows.append(dict(trial=trial,candidates=sum(n for _,n,_ in candidates),**m))
        s,c=daily(deals,bars,start,end);sums.append(s);counts.append(c)
    return rows,(np.mean(sums,axis=0),np.mean(counts,axis=0))
