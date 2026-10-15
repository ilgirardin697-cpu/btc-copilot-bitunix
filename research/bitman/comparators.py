"""Canonical comparison adapter; frozen BITMAN strategy/results never modified.

The initial run's V8 diagnostic compared hourly price to the last4H SMA.
Canonical V8 must instead carry the LAST CLOSED4H close>SMA200 state.
This correction cannot enter CLASSIC/FUSION selection or signal generation.
"""
import numpy as np
from . import core, engine, run
from .data import HOUR
from .spec import Candidate


def v8_closed_state(bars):
    h4=core.aggregate(bars,4*HOUR,HOUR)
    avg=core.mean(h4[:,4],200)
    values=np.where(np.isfinite(avg),(h4[:,4]>avg).astype(float),np.nan)
    return core.align(h4[:,0],values,4*HOUR,bars[:,0]+HOUR)


def definitions(bars,base):
    close=bars[:,4]
    gain=core.ema(np.maximum(np.r_[0.,np.diff(close)],0),27)
    loss=core.ema(np.maximum(-np.r_[0.,np.diff(close)],0),27)
    rsi=np.divide(100*gain,gain+loss,out=np.full(len(close),50.),where=gain+loss>0)
    state=core.ema(rsi,5);sma1=core.mean(close,200)
    v8=v8_closed_state(bars)
    return {
        'V8':(v8==1,v8==0),
        'CONFLUENCE_D60':((close>sma1)&(base['flow']>=.6)&(state>55),(close<=sma1)|(state<45)),
        'EMA_10_55':(core.ema(close,10)>core.ema(close,55),core.ema(close,10)<=core.ema(close,55)),
        'BUY_HOLD':(np.ones(len(close),bool),np.zeros(len(close),bool)),
        'MLRSI_STATE':(base['ml_state']==1,base['ml_state']==-1),
        'BUY_HOLD_NO_FUNDING':(np.ones(len(close),bool),np.zeros(len(close),bool)),
    }


def evaluate(bars,base,funding,periods=None,keep_returns=False):
    p=Candidate(name='control');periods=periods or run.SPLITS;result={}
    for name,(entry,opposite) in definitions(bars,base).items():
        result[name]={}
        for split,(start,end) in periods.items():
            trial=engine.simulate(bars,base,entry,opposite,np.empty((0,2)) if name=='BUY_HOLD_NO_FUNDING' else funding,
                                  p,1,start,end,benchmark=True)
            result[name][split]=trial if keep_returns else trial['metrics']
    return result
