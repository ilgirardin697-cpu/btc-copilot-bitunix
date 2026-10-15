"""Clean-room causal public-indicator proxy; no accounts or execution authority."""
from collections import deque
import numpy as np
from .data import HOUR, aggregate


def lag(x, n=1):
    x=np.asarray(x); result=np.full(len(x),np.nan)
    if n<len(x): result[n:]=x[:-n]
    return result


def ema(x, n):
    out=np.full(len(x),np.nan); previous=np.nan; alpha=2/(n+1)
    for i,v in enumerate(x):
        if np.isfinite(v):
            previous=v if not np.isfinite(previous) else alpha*v+(1-alpha)*previous
            out[i]=previous
    return out


def rolling(x,n,operation='mean'):
    out=np.full(len(x),np.nan)
    if len(x)>=n:
        windows=np.lib.stride_tricks.sliding_window_view(np.asarray(x,float),n)
        out[n-1:]=getattr(np,operation)(windows,axis=1)
    return out


def mean(x,n): return rolling(x,n)


def rma(x,n):
    out=np.full(len(x),np.nan); seed=[]; previous=np.nan
    for i,v in enumerate(x):
        if not np.isfinite(v): continue
        if not np.isfinite(previous):
            seed.append(v)
            if len(seed)<n: continue
            previous=float(np.mean(seed))
        else: previous=(previous*(n-1)+v)/n
        out[i]=previous
    return out


def rsi(x,n):
    diff=np.r_[np.nan,np.diff(x)]
    up=rma(np.maximum(diff,0),n); down=rma(np.maximum(-diff,0),n)
    return np.divide(100*up,up+down,out=np.full(len(x),np.nan),where=up+down>0)


def align(source_times, values, interval, target_closes):
    """A higher-TF feature exists only at/after that candle's real close."""
    idx=np.searchsorted(source_times+interval,target_closes,side='right')-1
    result=np.full(len(target_closes),np.nan)
    valid=idx>=0; result[valid]=np.asarray(values)[idx[valid]]
    return result


def regression_endpoint(x,n=20):
    axis=np.arange(n,dtype=float); centered=axis-axis.mean()
    weights=1/n+centered*(n-1-axis.mean())/np.dot(centered,centered)
    out=np.full(len(x),np.nan)
    if len(x)>=n: out[n-1:]=np.convolve(x,weights[::-1],mode='valid')
    return out


def structures(bars,atr,width=2):
    n=len(bars); close=bars[:,4]
    result={k:np.full(n,np.nan) for k in ('support','resistance','swing_high','swing_low','pattern')}
    result.update({k:np.zeros(n,bool) for k in ('bull','bear','break_long','break_short','retest_long','retest_short')})
    highs=deque(maxlen=200); lows=deque(maxlen=200); long_break=short_break=None
    for i in range(n):
        old_high=highs[-1][1] if highs else np.nan
        old_low=lows[-1][1] if lows else np.nan
        if i and close[i]>old_high and close[i-1]<=old_high:
            long_break=(i,old_high); result['break_long'][i]=True
        if i and close[i]<old_low and close[i-1]>=old_low:
            short_break=(i,old_low); result['break_short'][i]=True
        if long_break and 0<i-long_break[0]<=3:
            level=long_break[1]
            result['retest_long'][i]=bars[i,3]<=level+.1*atr[i] and close[i]>level
        if short_break and 0<i-short_break[0]<=3:
            level=short_break[1]
            result['retest_short'][i]=bars[i,2]>=level-.1*atr[i] and close[i]<level
        pivot=i-width
        if pivot>=width:
            h,l=bars[pivot,2:4]
            neighbors=np.r_[np.arange(pivot-width,pivot),np.arange(pivot+1,i+1)]
            if np.all(h>bars[neighbors,2]): highs.append((pivot,h))
            if np.all(l<bars[neighbors,3]): lows.append((pivot,l))
        if highs: result['swing_high'][i]=highs[-1][1]
        if lows: result['swing_low'][i]=lows[-1][1]
        supports=[v for _,v in lows if v<close[i]]; resistances=[v for _,v in highs if v>close[i]]
        if supports: result['support'][i]=max(supports)
        if resistances: result['resistance'][i]=min(resistances)
        if len(highs)>=2 and len(lows)>=2:
            result['bull'][i]=highs[-1][1]>highs[-2][1] and lows[-1][1]>lows[-2][1]
            result['bear'][i]=highs[-1][1]<highs[-2][1] and lows[-1][1]<lows[-2][1]
        if len(highs)>=3 and len(lows)>=3:
            hs=np.polyfit([p[0] for p in list(highs)[-3:]],[p[1] for p in list(highs)[-3:]],1)[0]
            ls=np.polyfit([p[0] for p in list(lows)[-3:]],[p[1] for p in list(lows)[-3:]],1)[0]
            narrowing=highs[-1][1]-lows[-1][1]<highs[-3][1]-lows[-3][1]
            result['pattern'][i]=1 if narrowing and hs<ls<0 else -1 if narrowing and 0<hs<ls else 2 if narrowing and hs<0<ls else 0
    return result


def base_features(bars):
    t,o,h,l,c,v,buy=bars.T; n=len(c)
    tr=np.maximum(h-l,np.maximum(np.abs(h-lag(c)),np.abs(l-lag(c)))); tr[0]=h[0]-l[0]
    atr=rma(tr,14)
    up=h-lag(h); down=lag(l)-l
    plus=100*np.divide(rma(np.where((up>down)&(up>0),up,0),14),atr,out=np.zeros(n),where=atr>0)
    minus=100*np.divide(rma(np.where((down>up)&(down>0),down,0),14),atr,out=np.zeros(n),where=atr>0)
    dx=100*np.divide(np.abs(plus-minus),plus+minus,out=np.zeros(n),where=plus+minus>0)
    dx[~np.isfinite(atr)]=np.nan
    adx=rma(dx,14)
    basis=mean(c,20); std=rolling(c,20,'std')
    width=4*std/basis
    bbwp=np.full(n,np.nan)
    if n>=253:
        windows=np.lib.stride_tricks.sliding_window_view(width,253)
        values=(windows[:,:-1]<windows[:,-1:]).sum(axis=1)/252*100
        values[~np.all(np.isfinite(windows),axis=1)]=np.nan
        bbwp[252:]=values
    hh=rolling(h,20,'max'); ll=rolling(l,20,'min')
    sqz=regression_endpoint(c-((hh+ll)/2+basis)/2,20)
    kcw=1.5*mean(tr,20)
    flow=np.divide(buy,v,out=np.full(n,.5),where=v>0)
    result=dict(time=t,close=c,atr=atr,adx=adx,adx_slope=adx-lag(adx),plus_di=plus,minus_di=minus,
        di_spread=plus-minus,ao=mean((h+l)/2,5)-mean((h+l)/2,34),sqz=sqz,bbwp=bbwp,
        bbwp_rising=bbwp>lag(bbwp),bbwp_expansion=(bbwp>=15)&(bbwp<90)&(bbwp>lag(bbwp)),
        squeeze=(2*std<kcw),flow=flow,flow_mean3=lag(mean(flow,3)),
        sma200=mean(c,200),regime_mean=mean(c,55),atr_pct=atr/c,
        h4=aggregate(bars,4*HOUR,HOUR),day=aggregate(bars,24*HOUR,HOUR))
    result.update(structures(bars,atr))
    result['vpoc']=np.full(n,np.nan)
    typical=(h+l+c)/3
    for i in range(72,n):
        counts,edges=np.histogram(typical[i-72:i],bins=24,weights=v[i-72:i])
        k=int(np.argmax(counts)); result['vpoc'][i]=(edges[k]+edges[k+1])/2
    result['sma4']=align(result['h4'][:,0],mean(result['h4'][:,4],200),4*HOUR,t+HOUR)
    return result


def candidate_features(bars,base,candidate,cache):
    def get(key,fn):
        if key not in cache: cache[key]=fn()
        return cache[key]
    c=bars[:,4]; t=bars[:,0]+HOUR; p=candidate
    fast=get(('ema',p.ema_fast),lambda:ema(c,p.ema_fast))
    slow=get(('ema',p.ema_slow),lambda:ema(c,p.ema_slow))
    rr=get(('rsi',p.rsi_length),lambda:rsi(c,p.rsi_length))
    cf=get(('cloud',p.rsi_length,p.cloud_fast),lambda:ema(rr,p.cloud_fast))
    cs=get(('cloud',p.rsi_length,p.cloud_slow),lambda:ema(rr,p.cloud_slow))
    result=dict(base,ema_fast=fast,ema_slow=slow,rsi=rr,cloud_fast=cf,cloud_slow=cs)
    for name,interval in (('h4',4*HOUR),('day',24*HOUR)):
        frame=base[name]
        result[name+'_trend']=get((name,p.ema_fast,p.ema_slow),lambda frame=frame,interval=interval:
            align(frame[:,0],np.sign(ema(frame[:,4],p.ema_fast)-ema(frame[:,4],p.ema_slow)),interval,t))
    return result


def blocks(f,p,side):
    c=f['close']; disabled=set(p.disabled); direction=1 if side==1 else -1
    trend=(f['ema_fast']-f['ema_slow'])*direction>0
    if p.trend in ('4h','1d'): trend &= f['h4_trend']==direction
    if p.trend=='1d': trend &= f['day_trend']==direction
    if p.slope: trend &= (f['ema_slow']-lag(f['ema_slow'],3))*direction>0
    cloud=(f['cloud_fast']-f['cloud_slow'])*direction>0
    if p.midpoint: cloud &= (f['rsi']-50)*direction>0
    osc=f['ao' if p.oscillator=='AO' else 'sqz']; delta=osc-lag(osc)
    if p.momentum=='cross': momentum=(osc*direction>0)&(lag(osc)*direction<=0)
    elif p.momentum=='slope': momentum=delta*direction>0
    elif p.momentum=='acceleration': momentum=(osc*direction>0)&(delta*direction>0)&((delta-lag(delta))*direction>0)
    else: momentum=osc*direction>0
    dmi=f['di_spread']*direction>0
    if p.dmi in ('threshold','both'): dmi &= f['adx']>=p.adx_level
    if p.dmi in ('rising','both'): dmi &= f['adx_slope']>0
    structure=np.ones(len(c),bool)
    if p.structure=='trend':
        room=(f['resistance']-c if side==1 else c-f['support'])/f['atr']
        structure=f['bull' if side==1 else 'bear']&(~np.isfinite(room)|(room>=.5))
    if p.structure=='retest': structure=f['retest_long' if side==1 else 'retest_short']
    volatility=f['bbwp_expansion'] if p.volatility=='expansion' else np.ones(len(c),bool)
    all_blocks=dict(TREND=trend,RSI_CLOUD=cloud,MOMENTUM=momentum,DMI=dmi,STRUCTURE=structure,VOLATILITY=volatility)
    for key in disabled:
        if key in all_blocks: all_blocks[key]=np.ones(len(c),bool)
    for feature in p.fusion:
        if feature=='MLRSI': value=f['ml_state']*direction>=0 # neutral allowed, opposite veto; UNKNOWN blocked
        elif feature=='MLRSI_RESUME': value=f['ml_resume_long' if side==1 else 'ml_resume_short']
        elif feature=='BBWP': value=f['bbwp_expansion']
        elif feature=='FLOW': value=(f['flow']-.5)*direction>0; value &= (f['flow']-f['flow_mean3'])*direction>0
        elif feature=='STRUCTURE': value=f['bull' if side==1 else 'bear']
        elif feature=='VPOC': value=(c-f['vpoc'])*direction>0
        else: raise ValueError('FUSION_FEATURE_UNKNOWN')
        all_blocks[feature]=value
    return all_blocks


def signals(f,p,side):
    groups=blocks(f,p,side)
    setup=np.logical_and.reduce(list(groups.values()))&np.isfinite(f['atr'])&np.isfinite(f['adx'])&np.isfinite(f['rsi'])
    event=setup&~np.r_[False,setup[:-1]]
    opposite=np.zeros(len(setup),bool)
    if 'TREND' not in p.disabled: opposite |= (f['ema_fast']-f['ema_slow'])*side<=0
    if 'RSI_CLOUD' not in p.disabled: opposite |= (f['cloud_fast']-f['cloud_slow'])*side<=0
    return event,opposite,setup
