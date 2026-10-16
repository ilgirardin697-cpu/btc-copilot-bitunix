"""Clean-room public formula. No operational or historical strategy imports."""
import numpy as np


def lag(x): return np.r_[np.nan,np.asarray(x,float)[:-1]]


def roll(x,n,method='mean'):
    x=np.asarray(x,float);out=np.full(len(x),np.nan)
    if len(x)>=n:
        w=np.lib.stride_tricks.sliding_window_view(x,n)
        out[n-1:]=getattr(np,method)(w,axis=1)
    return out


def ema(x,n):
    out=np.full(len(x),np.nan);last=np.nan
    for i,v in enumerate(x):
        if np.isfinite(v):
            last=v if not np.isfinite(last) else last+2/(n+1)*(v-last)
            out[i]=last
        else: last=np.nan
    return out


def rma(x,n):
    out=np.full(len(x),np.nan);seed=[];last=np.nan
    for i,v in enumerate(x):
        if not np.isfinite(v): seed=[];last=np.nan;continue
        if not np.isfinite(last):
            seed.append(v)
            if len(seed)<n:continue
            last=float(np.mean(seed))
        else:last=(last*(n-1)+v)/n
        out[i]=last
    return out


def ratio100(a,b):
    """RSI-style ratio of positive/negative sums; both zero is unavailable."""
    return np.divide(100*a,a+b,out=np.full(len(a),np.nan),where=(a+b)>0)


def calculate(bars):
    t,o,h,l,c,v,_=np.asarray(bars,float).T
    price=(o+h+l+c)/4;typical=(h+l+c)/3
    delta=price-lag(price)
    rsi=ratio100(rma(np.maximum(delta,0),14),rma(np.maximum(-delta,0),14))
    change=typical-lag(typical);flow=typical*v
    positive=roll(np.where(change>0,flow,0.),14,'sum')
    negative=roll(np.where(change<0,flow,0.),14,'sum')
    mfi=ratio100(positive,negative)
    basis=roll(price,25);std=roll(price,25,'std')
    boll=np.divide(100*(price-basis),4*std,out=np.full(len(price),np.nan),where=std>0)
    low=roll(l,21,'min');high=roll(h,21,'max')
    stoch=roll(np.divide(100*(price-low),high-low,out=np.full(len(price),np.nan),where=high>low),3)
    mountain=(rsi+mfi+boll+stoch/3)/2
    ma=ema(mountain,15)
    prev=lag(c);tr=np.maximum(h-l,np.maximum(abs(h-prev),abs(l-prev)))
    tr[0]=h[0]-l[0]
    atr=rma(tr,14);up=h-lag(h);down=lag(l)-l
    plus=np.where((up>down)&(up>0),up,0.);minus=np.where((down>up)&(down>0),down,0.)
    # First DM observation is unknown, not a fabricated directional movement.
    plus[0]=minus[0]=np.nan
    di_plus=np.divide(100*rma(plus,14),atr,out=np.full(len(c),np.nan),where=atr>0)
    di_minus=np.divide(100*rma(minus,14),atr,out=np.full(len(c),np.nan),where=atr>0)
    total=di_plus+di_minus
    dx=np.divide(100*abs(di_plus-di_minus),total,out=np.full(len(c),np.nan),where=total>0)
    # Finite, exactly equal zero DIs indicate no directional strength.
    dx[np.isfinite(total)&(total==0)]=0.
    adx=rma(dx,14)
    ao=roll((h+l)/2,5)-roll((h+l)/2,34)
    bb_basis=roll(c,7);bb_width=4*roll(c,7,'std')/bb_basis
    bbwp=np.full(len(c),np.nan)
    if len(c)>100:
        w=np.lib.stride_tricks.sliding_window_view(bb_width,101)
        rank=np.sum(w[:,:-1]<w[:,-1:],axis=1).astype(float)
        rank[~np.all(np.isfinite(w),axis=1)]=np.nan
        bbwp[100:]=rank
    return dict(time=t,close=c,rsi=rsi,mfi=mfi,boll=boll,stoch=stoch,mountain=mountain,ma=ma,
        mountain_slope=mountain-lag(mountain),atr=atr,adx=adx,adx_slope=adx-lag(adx),
        di_plus=di_plus,di_minus=di_minus,ao=ao,ao_slope=ao-lag(ao),bbwp=bbwp,
        bbwp_slope=bbwp-lag(bbwp))
