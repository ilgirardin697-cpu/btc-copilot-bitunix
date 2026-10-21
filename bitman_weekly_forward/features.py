"""Public weekly AO and BBWP proxies, with the audited causal ATR checkpoint."""
import csv
import json
import math
import numpy as np
from bitman_manual.frozen.indicators import roll, lag
from .protocol import ROOT, WEEK, MONDAY, file_hash


def validate_week(row):
    if not isinstance(row,dict) or set(row)!= {'open_time','open','high','low','close'}:
        raise ValueError('INVALID_WEEK_SCHEMA')
    t=row['open_time']
    if type(t) is not int or (t-MONDAY)%WEEK:
        raise ValueError('INVALID_WEEK_TIME')
    try:
        o,h,l,c=(float(row[k]) for k in ('open','high','low','close'))
    except (TypeError,ValueError):
        raise ValueError('INVALID_WEEK_VALUES') from None
    if not all(math.isfinite(x) and x>0 for x in (o,h,l,c)) or h<max(o,c) or l>min(o,c):
        raise ValueError('INVALID_WEEK_OHLC')
    return row


def load_bootstrap():
    manifest=json.loads((ROOT/'bootstrap_manifest.json').read_text('utf-8'))
    if file_hash(ROOT/'bootstrap_v1.csv')!=manifest['sha256'] or manifest['rows']!=120:
        raise ValueError('BOOTSTRAP_INVALID')
    with (ROOT/'bootstrap_v1.csv').open(newline='',encoding='utf-8') as stream:
        rows=[dict(row,open_time=int(row['open_time'])) for row in csv.DictReader(stream)]
    for i,row in enumerate(rows):
        validate_week(row)
        if i and row['open_time']!=rows[i-1]['open_time']+WEEK:
            raise ValueError('BOOTSTRAP_GAP')
    if len(rows)!=manifest['rows'] or rows[-1]['open_time']+WEEK!=manifest['available_at']:
        raise ValueError('BOOTSTRAP_INVALID')
    return rows,manifest


def calculate(rows,manifest):
    frame=np.asarray([[r['open_time'],*[float(r[k]) for k in ('open','high','low','close')]] for r in rows])
    t,o,h,l,c=frame.T
    ao=roll((h+l)/2,5)-roll((h+l)/2,34)
    width=4*roll(c,7,'std')/roll(c,7)
    bbwp=np.full(len(rows),np.nan)
    if len(rows)>100:
        windows=np.lib.stride_tricks.sliding_window_view(width,101)
        rank=np.sum(windows[:,:-1]<windows[:,-1:],axis=1).astype(float)
        rank[~np.all(np.isfinite(windows),axis=1)]=np.nan
        bbwp[100:]=rank
    atr=np.full(len(rows),np.nan)
    previous=float(manifest['previous_close'])
    last=float(manifest['atr_seed_before_first_week'])
    for i in range(len(rows)):
        tr=max(h[i]-l[i],abs(h[i]-previous),abs(l[i]-previous))
        last=(last*13+tr)/14
        atr[i],previous=last,c[i]
    f=dict(frame=frame,ao=ao,ao_slope=ao-lag(ao),bbwp=bbwp,prior_bbwp=lag(bbwp),
           bbwp_slope=bbwp-lag(bbwp),atr=atr,available_at=t+WEEK)
    f['color']=np.where(f['ao_slope']>0,'GREEN',np.where(f['ao_slope']<0,'RED','FLAT'))
    f['sign']=np.where(ao>0,'ABOVE',np.where(ao<0,'BELOW','ZERO'))
    f['vol']=np.where(f['bbwp_slope']>0,'ACTIVE_RISING',np.where(f['bbwp_slope']<0,'COOLING','FLAT'))
    f['valid']=np.logical_and.reduce([np.isfinite(x) for x in
        (ao,f['ao_slope'],lag(ao),lag(f['ao_slope']),bbwp,f['bbwp_slope'],lag(f['bbwp_slope']),atr)]) & (atr>0)
    f['turn']=(f['bbwp_slope']>0)&(lag(f['bbwp_slope'])<=0)&f['valid']
    return f


def snapshot(f,models,index=-1):
    i=len(f['ao'])-1 if index==-1 else index
    if not f['valid'][i]:
        raise ValueError('WEEKLY_FEATURES_UNAVAILABLE')
    return dict(ao=float(f['ao'][i]),ao_slope=float(f['ao_slope'][i]),ao_sign=str(f['sign'][i]),
        ao_color=str(f['color'][i]),bbwp=float(f['bbwp'][i]),prior_bbwp=float(f['prior_bbwp'][i]),
        bbwp_slope=float(f['bbwp_slope'][i]),atr=float(f['atr'][i]),volatility=str(f['vol'][i]),
        turn_up=bool(f['turn'][i]),available_at=int(f['available_at'][i]),
        models={name:dict(state=str(m['states'][i]),pending=m['pending_by_week'][i]) for name,m in models.items()})


def golden_check(rows,manifest):
    from .models import calculate_models
    f=calculate(rows,manifest)
    value=snapshot(f,calculate_models(f))
    golden=manifest['golden']
    for key,expected in golden.items():
        actual=value.get(key)
        if type(expected) is float:
            if type(actual) is not float or not math.isclose(actual,expected,rel_tol=0,abs_tol=1e-9):
                raise ValueError('BOOTSTRAP_GOLDEN_MISMATCH')
        elif actual!=expected:
            raise ValueError('BOOTSTRAP_GOLDEN_MISMATCH')
    return value
