"""Pure causal features; frozen public indicators are read-only dependencies."""
import numpy as np
from bitman_manual.frozen import indicators as frozen
from bitman_manual.frozen.core import align
from bitman_manual.frozen import levels
from .data import M5,HOUR,validate_bars

def segments(times,interval):
    cuts=np.r_[0,np.flatnonzero(np.diff(times)!=interval)+1,len(times)]
    return zip(cuts[:-1],cuts[1:])

def aggregate(a,interval):
    validate_bars(a)
    ids=(a[:,0]//interval).astype(np.int64);cuts=np.r_[0,np.flatnonzero(np.diff(ids))+1,len(a)];out=[]
    for i,j in zip(cuts[:-1],cuts[1:]):
        g=a[i:j];t=int(ids[i]*interval)
        if len(g)!=interval//M5 or not np.array_equal(g[:,0],np.arange(t,t+interval,M5)):continue
        out.append([t,g[0,1],g[:,2].max(),g[:,3].min(),g[-1,4],g[:,5].sum(),g[:,6].sum()])
    return np.asarray(out,float).reshape(-1,7)

def fe13(a):
    n=13;prev=frozen.lag(a[:,4])
    tr=np.maximum(a[:,2],prev)-np.minimum(a[:,3],prev)
    total=frozen.roll(tr,n,'sum');span=frozen.roll(a[:,2],n,'max')-frozen.roll(a[:,3],n,'min')
    valid=(span>0)&(total>0)
    out=np.full(len(a),np.nan)
    out[valid]=np.log(total[valid]/span[valid])/np.log(n)
    return out

def calculate(a,interval,with_levels=False):
    out={}
    for left,right in segments(a[:,0],interval):
        g=a[left:right];f=frozen.calculate(g)
        f['fe']=fe13(g);f['fe_slope']=f['fe']-frozen.lag(f['fe'])
        for name,n,mode,col in (('high3',3,'max',2),('low3',3,'min',3),('high6',6,'max',2),('low6',6,'min',3)):
            f[name]=frozen.lag(frozen.roll(g[:,col],n,mode))
        f['sma200']=frozen.roll(g[:,4],200)
        if with_levels: f.update({'pivot_'+k:v for k,v in levels.scale(g,interval).items()})
        for k,v in f.items():
            if k not in out:out[k]=np.full(len(a),np.nan)
            out[k][left:right]=v
    return out

def prepare(a,interval=HOUR):
    frames={width:aggregate(a,width) for width in sorted({interval,4*HOUR,24*HOUR})}
    features={width:calculate(b,width,with_levels=width==interval) for width,b in frames.items()}
    b=frames[interval];query=b[:,0]+interval;htf={}
    for width,label in ((4*HOUR,'h4'),(24*HOUR,'d1')):
        frame=frames[width];f=features[width]
        for key in ('ao','ao_slope','adx','adx_slope','di_plus','di_minus','bbwp','bbwp_slope','sma200','close','time'):
            values=align(frame[:,0],f[key],width,query)
            latest=align(frame[:,0],frame[:,0]+width,width,query)
            values[(query-latest>=width)|~np.isfinite(latest)]=np.nan
            htf[label+'_'+key]=values
        htf[label+'_available_at']=align(frame[:,0],frame[:,0]+width,width,query)
    f=features[interval];f.update(htf)
    f['regime']=np.sign(f['h4_close']-f['h4_sma200'])
    return dict(bars=b,features=f,interval=interval,available_at=query)

def raw_events(data,family):
    b,f=data['bars'],data['features'];n=len(b);out=np.zeros(n,int)
    for s in (1,-1):
        ao=s*f['ao'];slope=s*f['ao_slope']
        if family=='A':
            ok=(ao>0)&(frozen.lag(ao)>0)&(frozen.lag(frozen.lag(ao))>0)&(slope>0)&(frozen.lag(slope)<0)&(frozen.lag(frozen.lag(slope))<0)
        elif family=='B':ok=(ao>0)&(frozen.lag(ao)<=0)
        elif family=='C':
            structural=b[:,4]>f['high6'] if s==1 else b[:,4]<f['low6']
            ok=(ao<0)&(slope>0)&(frozen.lag(slope)<0)&(frozen.lag(frozen.lag(slope))<0)&structural
        else:raise ValueError('UNKNOWN_FAMILY')
        # Histories must be contiguous across all event lookbacks.
        ok[:3]=False
        for lag in (1,2,3):
            ok[lag:] &= b[lag:,0]-b[:-lag,0]==lag*data['interval']
        out[ok]=s
    return out

def gates(data,i,side,family):
    b,f=data['bars'],data['features'];s=side
    if family=='A':
        context=(s*f['h4_ao'][i]>0 and s*f['d1_ao'][i]>0 and
            (b[i,4]>f['high3'][i] if s==1 else b[i,4]<f['low3'][i]))
    elif family=='B':context=s*f['h4_ao_slope'][i]>0 and s*f['d1_ao'][i]>0
    else:context=s*f['h4_ao'][i]<0 and s*f['h4_ao_slope'][i]>0
    di=s*(f['di_plus']-f['di_minus'])
    if family=='A':dmi=di[i]>0 and f['adx_slope'][i]>0 and f['adx_slope'][i-1]<=0
    elif family=='B':
        crossed=any(di[j]>0 and di[j-1]<=0 for j in range(max(1,i-2),i+1))
        dmi=di[i]>0 and crossed and f['adx_slope'][i]>0
    else:dmi=di[i]>0 and f['adx_slope'][i-1]<0
    fe=f['fe_slope'][i]<0
    return dict(AO_ONLY=True,AO_CONTEXT=bool(context),AO_DMI=bool(context and dmi),
        AO_FE=bool(context and fe),AO_DMI_FE=bool(context and dmi and fe))

