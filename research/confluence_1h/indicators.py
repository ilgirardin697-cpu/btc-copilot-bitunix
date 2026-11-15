"""Default public-source ports, MPL-2.0; no private Bitman parity claim.

Koncorde: supplied OskarGallard/Blai5 public adaptation, BITMAN PROXY.
BBWP: supplied The_Caretaker v6, literal rightmost-index rank including ties.
No trading/runtime imports. Undefined mathematical ratios remain unavailable.
"""
from bisect import bisect_left,bisect_right,insort_right
from collections import deque
import numpy as np


def lag(x,n=1):
    x=np.asarray(x);return np.r_[np.full(min(n,len(x)),np.nan),x[:-n]] if n<len(x) else np.full(len(x),np.nan)


def roll(x,n,method='mean',partial=False):
    x=np.asarray(x,float);out=np.full(len(x),np.nan)
    if n<1:raise ValueError('POSITIVE_LENGTH')
    if len(x)>=n:
        w=np.lib.stride_tricks.sliding_window_view(x,n)
        out[n-1:]=getattr(np,method)(w,axis=1)
    if partial:
        for i in range(min(n-1,len(x))):out[i]=getattr(np,method)(x[:i+1])
    return out


def smooth(x,n,kind):
    x=np.asarray(x,float);out=np.full(len(x),np.nan);seed=[];last=np.nan
    if n<1 or kind not in ('ema','rma'):raise ValueError('SMOOTHER')
    for i,v in enumerate(x):
        if not np.isfinite(v):
            out[i]=last;continue
        if not np.isfinite(last):
            if kind=='ema':last=v
            else:
                seed.append(v)
                if len(seed)<n:continue
                last=float(np.mean(seed))
        else:
            alpha=2/(n+1) if kind=='ema' else 1/n
            last=alpha*v+(1-alpha)*last
        out[i]=last
    return out


def divide(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float)
    return np.divide(a,b,out=np.full(np.broadcast_shapes(a.shape,b.shape),np.nan),where=b!=0)


def pine_rightmost(a,v):
    """TradingView: last equal index, otherwise insertion/right-neighbor index."""
    right=bisect_right(a,v)
    return right-1 if right and a[right-1]==v else right


def bbwp(width,length=100,basis_length=7,literal=True):
    out=np.full(len(width),np.nan);raw=deque();ordered=[]
    # Literal source starts at bar_index >= basis_length, not basis_length-1.
    for i,w in enumerate(width):
        if i<basis_length or not np.isfinite(w):continue
        if ordered:
            rank=pine_rightmost(ordered,w) if literal else bisect_right(ordered,w)
            out[i]=rank*100/len(ordered)
        insort_right(ordered,float(w));raw.append(float(w))
        if len(raw)>length:
            old=raw.popleft();ordered.pop(pine_rightmost(ordered,old))
    return out


def calculate(bars,bbwp_literal=True):
    a=np.asarray(bars,float)
    if a.ndim!=2 or a.shape[1]!=6:raise ValueError('OHLCV_SHAPE')
    t,o,h,l,c,v=a.T;p=(o+h+l+c)/4;typical=(h+l+c)/3
    change=p-lag(p);up=smooth(np.maximum(change,0),14,'rma');down=smooth(np.maximum(-change,0),14,'rma')
    rsi=100*divide(up,up+down)
    money=typical*v;delta=typical-lag(typical)
    pos=roll(np.where(delta>0,money,0),14,'sum');neg=roll(np.where(delta<0,money,0),14,'sum')
    mfi=100*divide(pos,pos+neg)
    base=roll(p,25);std=roll(p,25,'std');boll=100*divide(p-base,4*std)
    k=100*divide(p-roll(l,21,'min'),roll(h,21,'max')-roll(l,21,'min'))
    stoch=roll(k,3);trend=(rsi+mfi+boll+stoch/3)/2;signal=smooth(trend,15,'ema')
    pvi=np.ones(len(c));nvi=np.ones(len(c))
    for i in range(1,len(c)):
        pvi[i]=pvi[i-1]*(c[i]/c[i-1] if v[i]>v[i-1] else 1)
        nvi[i]=nvi[i-1]*(c[i]/c[i-1] if v[i]<v[i-1] else 1)
    layers={}
    for name,x in [('pvi',pvi),('nvi',nvi)]:
        average=smooth(x,15,'ema');span=roll(average,90,'max',True)-roll(average,90,'min',True)
        layers[name]=x;layers[name+'_ema']=average;layers[name+'_osc']=100*divide(x-average,span)
    prev=lag(c);tr=np.maximum(h-l,np.maximum(abs(h-prev),abs(l-prev)))
    firsttr=tr.copy()
    if len(firsttr):firsttr[0]=h[0]-l[0]
    atr=smooth(firsttr,14,'rma')
    plus=h-lag(h);minus=lag(l)-l
    pdm=np.where((plus>minus)&(plus>0),plus,0.);mdm=np.where((minus>plus)&(minus>0),minus,0.)
    if len(pdm):pdm[0]=mdm[0]=np.nan
    # ta.dmi uses ta.tr with first previous close unavailable. ATR uses ta.tr(true).
    dmitr=smooth(tr,14,'rma');pdi=100*divide(smooth(pdm,14,'rma'),dmitr);mdi=100*divide(smooth(mdm,14,'rma'),dmitr)
    total=pdi+mdi;dx=100*divide(abs(pdi-mdi),np.where(total==0,1,total));adx=smooth(dx,14,'rma')
    ao=roll((h+l)/2,5)-roll((h+l)/2,34)
    width=2*divide(roll(c,7,'std'),roll(c,7));rank=bbwp(width,literal=bbwp_literal)
    result=dict(time=t,kon_trend=trend,kon_signal=signal,rsi=rsi,mfi=mfi,boll=boll,stoch=stoch,
        minnows=trend+layers['pvi_osc'],sharks=layers['nvi_osc'],atr=atr,plus_di=pdi,minus_di=mdi,
        adx=adx,ao=ao,bbw=width,bbwp=rank,**layers)
    for name in ('adx','ao','bbwp','kon_trend'):result[name+'_slope']=result[name]-lag(result[name])
    return result


def signals(f,adx_threshold=40.,bbwp_threshold=85.):
    k=f['kon_trend'];s=f['kon_signal'];adx=f['adx'];ao=f['ao'];b=f['bbwp']
    konlong=(k>s)&(lag(k)<=lag(s))&(lag(k)<0)
    konshort=(k<s)&(lag(k)>=lag(s))&(lag(k)>0)
    decline=(lag(adx)<lag(adx,2))&(lag(adx,2)>adx_threshold)
    aolong=(ao<0)&(ao>lag(ao))&(lag(ao)>lag(ao,2))
    aoshort=(ao>0)&(ao<lag(ao))&(lag(ao)<lag(ao,2))
    expansion=b>bbwp_threshold;valid=np.isfinite(f['atr'])&(f['atr']>0)
    return dict(long=valid&konlong&decline&aolong&expansion,short=valid&konshort&decline&aoshort&expansion,
        kon_long=konlong,kon_short=konshort,adx_lagged_decline=decline,ao_long=aolong,ao_short=aoshort,
        bbwp_above=expansion)


def regime(bars):
    """Existing causal convention: last confirmed 4H close relative to SMA200."""
    n=len(bars);r=np.full(n,np.nan)
    groups=[];times=[]
    for i in range(n-3):
        if int(bars[i,0])%14400000==0 and np.array_equal(bars[i:i+4,0],bars[i,0]+np.arange(4)*3600000):
            groups.append(bars[i+3,4]);times.append(bars[i,0]+14400000)
    if groups:
        g=np.asarray(groups);ma=roll(g,200);v=np.sign(g-ma)
        ids=np.searchsorted(times,bars[:,0]+3600000,side='right')-1;ok=ids>=0;r[ok]=v[ids[ok]]
    return r
