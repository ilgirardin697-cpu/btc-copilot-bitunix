"""Derive observation fixtures from closed public OHLC prefixes, without fetching."""
import hashlib
import numpy as np
from bitman_manual.frozen.indicators import roll
from .formulas import calculate,HOUR

def aggregate(rows,width):
    a=np.asarray(rows,float);groups={}
    for row in a:groups.setdefault(int(row[0]//width)*width,[]).append(row)
    out=[]
    for opening,group in sorted(groups.items()):
        g=np.asarray(group)
        if len(g)!=width//HOUR or not np.array_equal(g[:,0],np.arange(opening,opening+width,HOUR)):continue
        out.append([opening,g[0,1],g[:,2].max(),g[:,3].min(),g[-1,4]])
    return np.asarray(out,float).reshape(-1,5)

def observation(rows,activation_at,observed_at,venue):
    a=np.asarray(rows,float)
    if len(a)<7:raise ValueError('SNAPSHOT_WARMUP_DATA')
    if venue!='BINANCE_USDM_PERPETUAL':raise ValueError('SOURCE_VENUE')
    f=calculate(a)
    if np.any(a[:,0]+HOUR>observed_at):raise ValueError('UNCONFIRMED_INPUT')
    contexts={}
    for label,width in (('h4',4*HOUR),('d1',24*HOUR)):
        frame=aggregate(a,width)
        if not len(frame):raise ValueError('CONTEXT_UNAVAILABLE')
        value=calculate(frame,width)
        contexts[label+'_ao']=value['ao'][-1];contexts[label+'_available_at']=int(frame[-1,0]+width)
        if label=='h4':contexts['h4_regime']=np.sign(frame[-1,4]-roll(frame[:,4],200)[-1])
    result=dict(candle_open_ms=int(a[-1,0]),available_at=int(a[-1,0]+HOUR),observed_at=observed_at,activation_at=activation_at,
        venue=venue,ao=f['ao'][-1],ao_previous=f['ao'][-2],ao_previous2=f['ao'][-3],
        ao_slope=f['ao_slope'][-1],ao_slope_previous=f['ao_slope'][-2],ao_slope_previous2=f['ao_slope'][-3],
        atr=f['atr'][-1],signal_close=a[-1,4],prior_high3=a[-4:-1,2].max(),prior_low3=a[-4:-1,3].min(),
        prior_high6=a[-7:-1,2].max(),prior_low6=a[-7:-1,3].min(),adx=f['adx'][-1],
        adx_slope=f['adx_slope'][-1],adx_slope_previous=f['adx_slope'][-2],
        di_plus=f['di_plus'][-1],di_minus=f['di_minus'][-1],fe=f['fe'][-1],fe_previous=f['fe'][-2],
        source_input_sha256=hashlib.sha256(a.astype('<f8').tobytes()).hexdigest(),**contexts)
    return {k:float(v) if isinstance(v,np.floating) and np.isfinite(v) else None if isinstance(v,np.floating) else v for k,v in result.items()}
