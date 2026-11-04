"""Closed OHLC only. ATR14 is the SAME PRICE scale, no directional indicators."""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
import numpy as np
from ..alpha_arcanox_pine_v37.core import project

NY=ZoneInfo('America/New_York');HOUR=3600000;MINUTE=60000


def stamp(day,hour):
    return int(datetime.combine(day,time(hour),NY).timestamp()*1000)


def schedule(day):
    return dict(asia=stamp(day-timedelta(days=1),20),asia_end=stamp(day,0),london=stamp(day,2),
                radar=stamp(day,5),close=stamp(day,6),end=stamp(day,20))


def window(a,left,right):
    return a[np.searchsorted(a[:,0],left):np.searchsorted(a[:,0],right)]


def require_rows(a,left,right,step):
    if len(a)!=(right-left)//step or not np.array_equal(a[:,0],np.arange(left,right,step)):
        raise ValueError('MISSING_OR_DUPLICATE_CLOSED_CANDLES')
    if not np.isfinite(a).all() or np.any(a[:,1:]<=0) or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4])):
        raise ValueError('INVALID_OHLC')


def atr_series(h):
    result=np.full(len(h),np.nan);seed=[];last=None;previous=None;previous_time=None
    for i,b in enumerate(h):
        if previous_time is None or b[0]-previous_time!=HOUR:
            seed=[];last=None;previous=None
        tr=b[2]-b[3] if previous is None else max(b[2]-b[3],abs(b[2]-previous),abs(b[3]-previous))
        if last is None:
            seed.append(tr)
            if len(seed)==14:last=float(np.mean(seed))
        else:last=(last*13+tr)/14
        if last is not None:result[i]=last
        previous=b[4];previous_time=b[0]
    return result


def vector(asia,london3,prefix,atr,minute):
    if minute not in range(60) or len(asia)!=4 or len(london3)!=3 or len(prefix)!=minute:
        raise ValueError('INVALID_CAUSAL_PREFIX')
    ah,al=max(asia[:,2]),min(asia[:,3]);width=ah-al
    if width<=0 or not np.isfinite(atr) or atr<=0:raise ValueError('PRICE_SCALE_UNAVAILABLE')
    if minute:require_rows(prefix,int(london3[-1,0])+HOUR,int(london3[-1,0])+HOUR+minute*MINUTE,MINUTE)
    lh,ll=max(london3[:,2]),min(london3[:,3]);price=london3[-1,4]
    if minute:lh,ll,price=max(lh,max(prefix[:,2])),min(ll,min(prefix[:,3])),prefix[-1,4]
    hi,lo=max(ah,lh),min(al,ll)
    return np.array([minute/60,(price-lo)/(hi-lo),(price-london3[0,1])/width,
                     (lh-ll)/width,(asia[-1,4]-asia[0,1])/width,(hi-lo)/atr])


def reference_vectors(day,h,m):
    s=schedule(day)
    if s['close']-s['london']!=4*HOUR:raise ValueError('DST_LONDON_NOT_FOUR_H1')
    a=window(h,s['asia'],s['asia_end']);l=window(h,s['london'],s['radar'])
    require_rows(a,s['asia'],s['asia_end'],HOUR);require_rows(l,s['london'],s['radar'],HOUR)
    prefix=window(m,s['radar'],s['close']);require_rows(prefix,s['radar'],s['close'],MINUTE)
    before=h[h[:,0]<s['radar']]
    if not len(before) or before[-1,0]+HOUR!=s['radar']:raise ValueError('NO_CONFIRMED_ATR_CONTEXT')
    atr=atr_series(before)[-1]
    return np.array([vector(a,l,prefix[:i],atr,i) for i in range(60)])


def final_label(day,h,m,asof):
    s=schedule(day)
    if asof<s['end']:raise ValueError('OUTCOME_NOT_MATURE')
    if s['close']-s['london']!=4*HOUR:raise ValueError('DST_LONDON_NOT_FOUR_H1')
    a=window(h,s['asia'],s['asia_end']);l=window(h,s['london'],s['close'])
    require_rows(a,s['asia'],s['asia_end'],HOUR);require_rows(l,s['london'],s['close'],HOUR)
    after=window(m,s['close'],s['end']);require_rows(after,s['close'],s['end'],MINUTE)
    for t in range(s['radar'],s['end'],HOUR):
        minute=window(m,t,t+HOUR);hour=window(h,t,t+HOUR)
        require_rows(minute,t,t+HOUR,MINUTE);require_rows(hour,t,t+HOUR,HOUR)
        if not np.array_equal([minute[0,1],max(minute[:,2]),min(minute[:,3]),minute[-1,4]],hour[0,1:]):
            raise ValueError('PUBLIC_H1_1M_MISMATCH')
    p=project(max(a[:,2]),min(a[:,3]),max(l[:,2]),min(l[:,3]))
    u=np.flatnonzero(after[:,2]>=p['newTopTarget']);d=np.flatnonzero(after[:,3]<=p['newBottomTarget'])
    ui=int(u[0]) if len(u) else len(after);di=int(d[0]) if len(d) else len(after)
    label=2 if ui==di==len(after) else -1 if ui==di else 0 if ui<di else 1
    return dict(class_index=label,top=p['newTopTarget'],bottom=p['newBottomTarget'],
                first_touch=None if label==2 else int(after[min(ui,di),0]),label_available_at=s['end'])
