"""Reuse audited mathematical kernels; no new indicator variants.

TSA source translation is Zeiierman CC BY-NC-SA4.0, noncommercial research.
Koncorde and BBWP retain the supplied MPL2.0 source attribution in ../sources.
"""
from copy import deepcopy
import numpy as np
from research.confluence_1h.indicators import calculate, roll, bbwp, lag
from ..profile import adx14, tsa, settings

H=3600000
M=H//4
DAY=24*H
WEEK=7*DAY
TWO_ANCHOR=4*DAY
STEPS={'15m':M,'1h':H,'4h':4*H,'1d':DAY,'1w':WEEK,'2w':2*WEEK}


def validate(a,frame,asof):
    a=np.asarray(a,float)
    if a.ndim!=2 or a.shape[1]!=6 or not len(a) or not np.isfinite(a).all():
        raise ValueError('OHLCV_REQUIRED')
    step=STEPS[frame]
    anchor=TWO_ANCHOR if frame in ('1w','2w') else 0
    if np.any(a[:,0]!=a[:,0].astype(np.int64)) or np.any((a[:,0]-anchor)%step):
        raise ValueError('TIME_GRID')
    if len(a)>1 and np.any(np.diff(a[:,0])!=step):
        raise ValueError('GAP_OR_DUPLICATE')
    if a[-1,0]+step>asof:
        raise ValueError('OPEN_CANDLE')
    if np.any(a[:,3]<=0) or np.any(a[:,3]>np.minimum(a[:,1],a[:,4])) or np.any(a[:,2]<np.maximum(a[:,1],a[:,4])) or np.any(a[:,5]<0):
        raise ValueError('OHLCV_RANGE')
    return a


def fortnight(weekly):
    """Declared UTC Monday anchor; no claim of platform 2W parity."""
    out=[]
    for i in range(len(weekly)-1):
        a,b=weekly[i:i+2]
        if (int(a[0])-TWO_ANCHOR)%(2*WEEK)==0 and b[0]==a[0]+WEEK:
            out.append([a[0],a[1],max(a[2],b[2]),min(a[3],b[3]),b[4],a[5]+b[5]])
    return np.asarray(out,float)


def features(a):
    f=calculate(a)
    f['adx'],f['plus_di'],f['minus_di']=adx14(a)
    width=2*roll(a[:,4],13,'std')/roll(a[:,4],13)
    f['bbwp']=bbwp(width,252,13)
    # Partial rank is source math, but full ranking history is required here.
    f['bbwp'][:265]=np.nan
    f['bbwp_signal']=roll(f['bbwp'],5)
    f['pececillos']=f['minnows']
    f['tendencia']=f['kon_trend']
    f['tiburones']=f['sharks']
    f['roja']=f['kon_signal']
    f.update(tsa(a,settings()['active_inputs']['tsa']))
    for name in ('ao','adx','pececillos','tendencia','tiburones','roja','bbwp','bbwp_signal','tsa_trend','tsa_speed'):
        x=f[name]
        d=x-lag(x)
        f[name+'_slope']=d
        f[name+'_acceleration']=d-lag(d)
        f[name+'_turn']=np.where((d>0)&(lag(d)<0),1,np.where((d<0)&(lag(d)>0),-1,0))
        f[name+'_zero']=np.where((x>0)&(lag(x)<=0),1,np.where((x<0)&(lag(x)>=0),-1,0))
    f['pececillos_cross_roja']=np.where((f['pececillos']>f['roja'])&(lag(f['pececillos'])<=lag(f['roja'])),1,
        np.where((f['pececillos']<f['roja'])&(lag(f['pececillos'])>=lag(f['roja'])),-1,0))
    return f


def number(x):
    return float(x) if np.isfinite(x) else None


class Frame:
    """A closed-bar stream. A pivot is announced only two bars later."""
    def __init__(self,a,frame,asof):
        self.a=validate(a,frame,asof)
        self.frame=frame
        self.step=STEPS[frame]
        self.f=features(self.a)
        self.records=[]
        self._build()

    def _build(self):
        high=low=None
        breaks={1:None,-1:None}
        pivots={1:None,-1:None}
        for i,row in enumerate(self.a):
            t,o,h,l,c,v=row
            prev=self.a[i-1,4] if i else c
            r=dict(frame=self.frame,open_time=int(t),available_at=int(t+self.step),
                   open=o,high=h,low=l,close=c,volume=v,structure=[],
                   known_high=deepcopy(high),known_low=deepcopy(low),
                   new_fractals=[],divergences=[])
            for k,z in self.f.items():
                if np.ndim(z)==1 and len(z)==len(self.a) and np.issubdtype(z.dtype,np.number):
                    r[k]=number(z[i])
            for side,level in ((1,high),(-1,low)):
                if level is None:
                    continue
                price=level['price']
                crossed=prev<=price<c if side==1 else prev>=price>c
                if crossed:
                    r['structure'].append('BREAK_UP' if side==1 else 'BREAK_DOWN')
                    breaks[side]=dict(level=price,at=r['available_at'],max_extension=0.,min_extension=0.)
                b=breaks[side]
                if b is not None:
                    extension=(h-b['level']) if side==1 else (b['level']-l)
                    b['max_extension']=max(b['max_extension'],extension)
                    if r['available_at']>b['at']:
                        recovered=c<=b['level'] if side==1 else c>=b['level']
                        retest=l<=b['level']<c if side==1 else h>=b['level']>c
                        if recovered:
                            r['structure'].append('FAILED_BREAK_UP' if side==1 else 'FAILED_BREAK_DOWN')
                            r['failed_break']=dict(side=side,level=b['level'],break_at=b['at'],
                                reclaim_at=r['available_at'],extension_price=b['max_extension'],
                                extension_atr=b['max_extension']/r['atr'] if r.get('atr') else None)
                            breaks[side]=None
                        elif retest:
                            r['structure'].append('RETEST_UP' if side==1 else 'RETEST_DOWN')
            line=number(self.f['tsa_trend'][i-1]) if i else None
            r['tsa_test_line']=line
            r['tsa_events']=[]
            if line is not None:
                if l<=line<c:
                    r['tsa_events'].append('REJECTION_UP')
                if h>=line>c:
                    r['tsa_events'].append('REJECTION_DOWN')
                if i>1:
                    oldline=self.f['tsa_trend'][i-2]
                    if self.a[i-2,4]<=oldline and prev>oldline and c<line:
                        r['tsa_events'].append('FALSE_BREAK_UP')
                    if self.a[i-2,4]>=oldline and prev<oldline and c>line:
                        r['tsa_events'].append('FALSE_BREAK_DOWN')
            # Strict five-bar pivot; no future-marked pivot is usable at its vertex.
            if i>=4:
                j=i-2
                for side,col in ((1,2),(-1,3)):
                    value=self.a[j,col]
                    neighbors=np.r_[self.a[j-2:j,col],self.a[j+1:j+3,col]]
                    confirmed=np.all(value>neighbors) if side==1 else np.all(value<neighbors)
                    if confirmed:
                        pivot=dict(price=float(value),pivot_at=int(self.a[j,0]),
                                   known_at=r['available_at'],ao=number(self.f['ao'][j]))
                        r['new_fractals'].append(dict(side=side,**pivot))
                        old=pivots[side]
                        if old and old['ao'] is not None and pivot['ao'] is not None:
                            divergent=value>old['price'] and pivot['ao']<old['ao'] if side==1 else value<old['price'] and pivot['ao']>old['ao']
                            if divergent:
                                r['divergences'].append(dict(kind='BEARISH' if side==1 else 'BULLISH',
                                    previous=deepcopy(old),current=deepcopy(pivot),available_at=r['available_at']))
                        pivots[side]=pivot
                        if side==1:
                            high=pivot
                        else:
                            low=pivot
            for key in ('ao','pececillos','adx','bbwp'):
                d=r.get(key+'_slope')
                r[key+'_price_disagreement']=bool(d is not None and d*(c-prev)<0)
            r['fred']='UNVERIFIED_NOT_A_SIGNAL'
            r['warmup_complete']=all(r.get(k) is not None for k in ('ao','adx','pececillos','atr','bbwp'))
            self.records.append(r)

    def at(self,when):
        idx=np.searchsorted(self.a[:,0]+self.step,when,side='right')-1
        if idx<0:
            raise ValueError('CONTEXT_MISSING')
        row=self.records[idx]
        if when-row['available_at']>=self.step:
            raise ValueError('CONTEXT_STALE')
        return deepcopy(row)


def concordance(frames):
    """Verify all fully overlapping higher bars against available 15m inputs."""
    base=frames['15m'].a
    checks={}
    for name in ('1h','4h','1d','1w','2w'):
        count=0
        for row in frames[name].a:
            b=base[(base[:,0]>=row[0])&(base[:,0]<row[0]+STEPS[name])]
            if len(b)!=STEPS[name]//M:
                continue
            got=np.array([b[0,1],b[:,2].max(),b[:,3].min(),b[-1,4],b[:,5].sum()])
            if not np.allclose(got,row[1:6],atol=1e-7,rtol=1e-12):
                raise ValueError('CROSS_FRAME_MISMATCH_'+name)
            count+=1
        checks[name]=count
    return checks
