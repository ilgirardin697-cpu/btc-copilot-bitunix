"""OHLC-only mathematical audit. No volume/venue substitution or chart matching."""
import numpy as np
from bitman_manual.frozen.indicators import lag,roll,rma

HOUR=3600000
SERIES=('ao','ao_slope','atr','di_plus','di_minus','adx','adx_slope','fe','fe_slope')

def calculate(rows,interval=HOUR):
    a=np.asarray(rows,float)
    if a.ndim!=2 or a.shape[1]!=5 or not len(a) or not np.all(np.isfinite(a)):
        raise ValueError('OHLC_SCHEMA')
    t,o,h,l,c=a.T
    if np.any(t%interval) or np.any(np.diff(t)!=interval):raise ValueError('OHLC_GAP_OR_ORDER')
    if np.any(a[:,1:]<=0) or np.any(h<np.maximum(o,c)) or np.any(l>np.minimum(o,c)) or np.any(l>h):
        raise ValueError('OHLC_VALUES')
    previous=lag(c);tr=np.maximum(h-l,np.maximum(abs(h-previous),abs(l-previous)));tr[0]=h[0]-l[0]
    atr=rma(tr,14);up=h-lag(h);down=lag(l)-l
    plus=np.where((up>down)&(up>0),up,0.);minus=np.where((down>up)&(down>0),down,0.)
    plus[0]=minus[0]=np.nan
    dp=np.divide(100*rma(plus,14),atr,out=np.full(len(c),np.nan),where=atr>0)
    dm=np.divide(100*rma(minus,14),atr,out=np.full(len(c),np.nan),where=atr>0)
    total=dp+dm
    dx=np.divide(100*abs(dp-dm),total,out=np.full(len(c),np.nan),where=total>0)
    dx[np.isfinite(total)&(total==0)]=0.
    adx=rma(dx,14);ao=roll((h+l)/2,5)-roll((h+l)/2,34)
    raw_tr=np.maximum(h,previous)-np.minimum(l,previous)
    span=roll(h,13,'max')-roll(l,13,'min');summed=roll(raw_tr,13,'sum');fe=np.full(len(c),np.nan)
    ok=(span>0)&(summed>0);fe[ok]=np.log(summed[ok]/span[ok])/np.log(13)
    return dict(ao=ao,ao_slope=ao-lag(ao),atr=atr,di_plus=dp,di_minus=dm,adx=adx,
        adx_slope=adx-lag(adx),fe=fe,fe_slope=fe-lag(fe))
