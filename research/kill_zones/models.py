"""Fixed causal session geometries. No results or future candles enter signals."""
from datetime import datetime,timedelta,timezone,time
from zoneinfo import ZoneInfo
import numpy as np
from .data import HOUR,aggregate
from bitman_manual.frozen.core import feature,align
CLOCKS={'NY':ZoneInfo('America/New_York'),'UTC4':timezone(timedelta(hours=-4))}
GEOMETRIES=('EXTREME_TIMES','BOX_ENDS','RANGE')
FRACTIONS=(1.,.95)
def millis(dt):return int(dt.timestamp()*1000)
def boundaries(day,clock):
    tz=CLOCKS[clock]
    return tuple(millis(datetime.combine(d,t,tz)) for d,t in
        ((day-timedelta(days=1),time(20)),(day,time(0)),(day,time(2)),(day,time(5)),(day,time(12))))
def session(a,start,end):
    i,j=np.searchsorted(a[:,0],[start,end]);g=a[i:j]
    if not np.array_equal(g[:,0],np.arange(start,end,HOUR)):raise ValueError('SESSION_INCOMPLETE')
    if len(g)==0:raise ValueError('SESSION_EMPTY')
    hi=int(np.argmax(g[:,2]));lo=int(np.argmin(g[:,3]))
    return dict(start=start,end=end,high=float(g[hi,2]),low=float(g[lo,3]),
                high_at=int(g[hi,0]+HOUR),low_at=int(g[lo,0]+HOUR),hours=len(g))
def line(p0,t0,p1,t1,t):
    if t1<=t0:raise ValueError('LINE_ANCHOR_ORDER')
    return p0+(p1-p0)*(t-t0)/(t1-t0)
def levels(z,geometry,t):
    a,l=z['asia'],z['london']
    if geometry=='RANGE':return z['high'],z['low']
    if geometry not in GEOMETRIES:raise ValueError('UNKNOWN_GEOMETRY')
    def project(k):
        ta=a[k+'_at'] if geometry=='EXTREME_TIMES' else a['end']
        tl=l[k+'_at'] if geometry=='EXTREME_TIMES' else l['end']
        return line(a[k],ta,l[k],tl,t)
    return project('high'),project('low')
def crossing(prev,current,upper0,lower0,upper1,lower1):
    if upper0<=lower0 or upper1<=lower1:return 0
    up=prev<=upper0 and current>upper1
    down=prev>=lower0 and current<lower1
    return 1 if up and not down else -1 if down and not up else 0
def first_signal(a,day,clock,geometry):
    start,end,ls,le,expiry=boundaries(day,clock)
    z=dict(asia=session(a,start,end),london=session(a,ls,le))
    z.update(high=max(z['asia']['high'],z['london']['high']),
             low=min(z['asia']['low'],z['london']['low']))
    z['width']=z['high']-z['low']
    if z['width']<=0:raise ValueError('ZERO_RANGE')
    left,right=np.searchsorted(a[:,0],[le,expiry])
    for i in range(left,right):
        if i==0 or a[i,0]-a[i-1,0]!=HOUR:continue
        t=int(a[i,0]+HOUR)
        if t>expiry:break
        u0,d0=levels(z,geometry,int(a[i,0]));u1,d1=levels(z,geometry,t)
        s=crossing(a[i-1,4],a[i,4],u0,d0,u1,d1)
        if not s:continue
        crossed=u1 if s==1 else d1
        target=crossed+s*z['width']
        return dict(date=day.isoformat(),weekend=day.weekday()>=5,clock=clock,geometry=geometry,
            side=s,signal_index=i,signal_at=t,entry_at=t,signal_close=float(a[i,4]),
            stop=z['low'] if s==1 else z['high'],full_target=target,boxes=z,
            crossed_line=crossed,line_drift_only=bool(s*(a[i,4]-a[i-1,4])<=0))
    return None
def candidates(a):
    first=datetime.fromtimestamp(a[0,0]/1000,timezone.utc).date()
    last=datetime.fromtimestamp(a[-1,0]/1000,timezone.utc).date();out=[];rejected={}
    for clock in CLOCKS:
        day=first
        while day<=last:
            for geometry in GEOMETRIES:
                try:row=first_signal(a,day,clock,geometry)
                except ValueError as error:
                    key=str(error);rejected[key]=rejected.get(key,0)+1;continue
                if row:
                    for fraction in FRACTIONS:
                        r=dict(row,fraction=fraction)
                        r['target']=r['signal_close']+fraction*(r['full_target']-r['signal_close'])
                        r['model']=f'{clock}_{geometry}_TP{round(fraction*100)}'
                        out.append(r)
            day+=timedelta(days=1)
    return sorted(out,key=lambda r:(r['entry_at'],r['model'])),rejected
def context(a):
    """Segmented frozen calculations; higher frames aligned by availability."""
    output={}
    for width,label in ((HOUR,'h1'),(4*HOUR,'h4'),(24*HOUR,'d1')):
        frame=a if width==HOUR else aggregate(a,width,HOUR)
        cuts=np.r_[0,np.flatnonzero(np.diff(frame[:,0])!=width)+1,len(frame)]
        f={}
        for lo,hi in zip(cuts[:-1],cuts[1:]):
            part=feature(frame[lo:hi])
            for key in ('ao','ao_slope','adx','adx_slope','di_plus','di_minus','konkorde'):
                if key not in f:f[key]=np.full(len(frame),'UNKNOWN',object) if key=='konkorde' else np.full(len(frame),np.nan)
                f[key][lo:hi]=part[key]
        for key,values in f.items():
            out=align(frame[:,0],values,width,a[:,0]+HOUR,'UNKNOWN' if key=='konkorde' else np.nan)
            available=align(frame[:,0],frame[:,0]+width,width,a[:,0]+HOUR)
            stale=~np.isfinite(available)|(a[:,0]+HOUR-available>=width)
            out[stale]='UNKNOWN' if key=='konkorde' else np.nan
            output[label+'_'+key]=out
    return output
def gate(c,i,side,name):
    ao=side*c['h1_ao_slope'][i]>0
    adx=side*(c['h1_di_plus'][i]-c['h1_di_minus'][i])>0 and c['h1_adx_slope'][i]>0
    k=c['h1_konkorde'][i]
    proxy=k in ('KONKORDE_BULLISH_ENTRY_CONTEXT','KONKORDE_BULLISH_INSIDE','KONKORDE_REENTRY') if side==1 else k=='KONKORDE_BEARISH_CONTEXT'
    return bool(dict(ALL=True,AO=ao,DMI_ADX=adx,KONKORDE_PROXY=proxy,AO_DMI_KONKORDE=ao and adx and proxy)[name])
