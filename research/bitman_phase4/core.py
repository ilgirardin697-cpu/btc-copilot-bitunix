"""Pure causal features and independently specified LONG/SHORT hypotheses."""
from dataclasses import replace
import numpy as np
from research.bitman_real.indicators import calculate,lag,roll,ema
from research.bitman_real.market import aggregate
from research.bitman_real.events import geometry
from .spec import HOUR,TIMEFRAMES


def align(times,values,interval,closes):
    i=np.searchsorted(times+interval,closes,side='right')-1
    out=np.full(len(closes),np.nan);ok=i>=0;out[ok]=np.asarray(values)[i[ok]]
    return out


def divergence(frame,ao,width=2):
    bull=np.zeros(len(frame),bool);bear=bull.copy();last_low=last_high=None
    for i in range(2*width,len(frame)):
        p=i-width;others=np.r_[np.arange(p-width,p),np.arange(p+1,i+1)]
        if np.isfinite(ao[p]) and np.all(frame[p,3]<frame[others,3]):
            if last_low is not None:bull[i]=frame[p,3]<frame[last_low,3] and ao[p]>ao[last_low]
            last_low=p
        if np.isfinite(ao[p]) and np.all(frame[p,2]>frame[others,2]):
            if last_high is not None:bear[i]=frame[p,2]>frame[last_high,2] and ao[p]<ao[last_high]
            last_high=p
    return bull,bear


def prepare(hourly,tf,now):
    interval=TIMEFRAMES[tf];frame=aggregate(hourly,interval,now);f=calculate(frame)
    valid,inside,sep=geometry(f);n=len(frame)
    entry=valid&np.r_[False,valid[:-1]&~inside[:-1]]&inside
    exit_=valid&np.r_[False,valid[:-1]&inside[:-1]]&~inside
    f.update(frame=frame,tf=tf,closes=frame[:,0]+interval,valid=valid,inside=inside,separation=sep,
        k_entry=entry,k_exit=exit_,sep_expanding=inside&np.r_[False,inside[:-1]]&(sep>lag(sep)))
    last_exit=np.full(n,-100000);last_entry=last_exit.copy();last_reentry={w:last_exit.copy() for w in (2,3,5)}
    ex=en=-100000;re={w:-100000 for w in last_reentry}
    for i in range(n):
        if not valid[i]:ex=en=-100000;re={w:-100000 for w in re}
        if exit_[i]:ex=i
        if entry[i]:
            en=i
            for w in re:
                if 1<=i-ex<=w:re[w]=i
        last_exit[i]=ex;last_entry[i]=en
        for w in re:last_reentry[w][i]=re[w]
    f.update(exit_age=np.arange(n)-last_exit,entry_age=np.arange(n)-last_entry,reentry_age={w:np.arange(n)-a for w,a in last_reentry.items()})
    for name,inter in (('h4',4*HOUR),('day',24*HOUR)):
        h=aggregate(hourly,inter,now);sma=roll(h[:,4],200)
        trend=np.where(np.isfinite(sma),np.where(h[:,4]>sma,1.,-1.),np.nan)
        f[name+'_trend']=align(h[:,0],trend,inter,f['closes'])
        if name=='day':
            df=calculate(h);bull,bear=divergence(h,df['ao'])
            f['day_bull_div']=align(h[:,0],bull.astype(float),inter,f['closes'])
            f['day_bear_div']=align(h[:,0],bear.astype(float),inter,f['closes'])
    f['ao_bull_div'],f['ao_bear_div']=divergence(frame,f['ao'])
    f['ema_fast']=ema(frame[:,4],10);f['ema_slow']=ema(frame[:,4],55)
    return f


def anchors(f,side):
    ao=f['ao'];slope=f['ao_slope'];positive=ao*side>0
    cross=positive&(lag(ao)*side<=0)
    resume=positive&(lag(ao)*side>0)&(slope*side>0)&(lag(slope)*side<=0)
    return cross|resume,cross,resume


def sequence(f,side,window):
    anchor,cross,resume=anchors(f,side);n=len(anchor);trigger=np.zeros(n,bool)
    age=np.full(n,np.nan);kind=np.full(n,0,dtype=int);turn_age=age.copy()
    current=turn=None;used=False
    for i in range(n):
        if not np.isfinite(f['ao'][i]) or f['ao'][i]*side<=0:current=turn=None;used=False
        if anchor[i]:current=i;turn=None;used=False
        if current is None or used or i-current>window:continue
        if f['adx_slope'][i]>0 and i and f['adx_slope'][i-1]<=0:turn=i
        direction=(f['di_plus'][i]-f['di_minus'][i])*side>0
        if turn is not None and direction and f['adx_slope'][i]>0 and f['ao_slope'][i]*side>0:
            trigger[i]=True;age[i]=i-current;turn_age[i]=i-turn;kind[i]=1 if cross[current] else 2;used=True
    return trigger,dict(anchor_age=age,anchor_kind=kind,after_adx_turn=turn_age)


def entry(f,p,side,remove=None):
    anchor,_,_=anchors(f,side)
    if remove=='AO':
        mask=(f['adx_slope']>0)&(lag(f['adx_slope'])<=0)&((f['di_plus']-f['di_minus'])*side>0);meta={}
    elif remove=='ADX_DI':mask=anchor.copy();meta={}
    else:mask,meta=sequence(f,side,p.lag)
    if remove!='BBWP':
        mask &= f['bbwp_slope']>0
        if p.family=='C1_BBWP50':mask &= f['bbwp']>=p.bb_reference
    if remove!='KONKORDE':
        inside=f['inside']&(f['mountain']>0)
        if p.family=='C2_K_CONTEXT':
            mask &= inside if side==1 else (f['exit_age']<=p.lag)&~f['inside']&(f['mountain_slope']<0)
        elif p.family=='C3_K_TRANSITION':mask &= inside&(f['entry_age']<=p.lag) if side==1 else f['k_exit']
        elif p.family=='C4_K_SEPARATION':
            if side!=1:raise ValueError('UNSUPPORTED_SHORT_GEOMETRY')
            mask &= inside&f['sep_expanding']
        elif p.family=='C5_K_REENTRY':
            if side!=1:raise ValueError('UNSUPPORTED_SHORT_GEOMETRY')
            mask &= inside&(f['reentry_age'][p.reentry_bars]<=p.lag)
    mask &= np.isfinite(f['atr'])
    if remove!='ADX_DI':mask &= np.isfinite(f['adx'])
    if remove!='BBWP':mask &= np.isfinite(f['bbwp'])
    return mask,meta


def hourly_inputs(hourly,f,mask,side):
    t=hourly[:,0];signal_times=f['closes']
    at=np.searchsorted(signal_times,t,side='right')-1;valid=at>=0
    opposite=np.zeros(len(t),bool);atr=np.full(len(t),np.nan)
    opposite[valid]=f['ao'][at[valid]]*side<0;atr[valid]=f['atr'][at[valid]]
    entries=np.zeros(len(t),bool)
    i=np.searchsorted(t,signal_times[mask]);ok=i<len(t)
    i=i[ok];stamps=signal_times[mask][ok];entries[i[t[i]==stamps]]=True
    return entries,opposite,atr


def control_masks(f,side):
    state=(f['ao']*side>0)&(f['adx_slope']>0)&((f['di_plus']-f['di_minus'])*side>0)
    trend=(f['ema_fast']-f['ema_slow'])*side>0
    return dict(AO_ADX=state&~np.r_[False,state[:-1]],EMA_TREND=trend&~np.r_[False,trend[:-1]],
        AO_ONLY=anchors(f,side)[0],KONKORDE_ENTRY=f['k_entry'] if side==1 else None)
