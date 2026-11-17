"""Frozen-plan four-turn detector; no trading or observer imports."""
from pathlib import Path
import hashlib,json
import numpy as np
from research.confluence_1h.indicators import calculate,lag
from research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.detect import features,HOUR

HERE=Path(__file__).resolve().parent
def plan_hash():return hashlib.sha256((HERE/'plan.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def atomics(f):
    out={}
    for name,key in [('ao','ao'),('pece','minnows'),('adx','adx'),('bbwp','bbwp')]:
        d=f[key]-lag(f[key]);previous=lag(d)
        out[name]=dict(slope=d,up=(d>0)&(previous<=0 if name=='bbwp' else previous<0),
                       down=(d<0)&(previous>=0 if name=='bbwp' else previous>0))
    return out
def detect(a,f=None,trace=False):
    a=np.asarray(a,float);f=features(a) if f is None else f;ev=atomics(f);tokens={};signals=[];audit=[];seen=set();streak=0
    for i in range(len(a)):
        finite=np.isfinite(a[i]).all() and all(np.isfinite(f[k][i]) for k in ('ao','minnows','adx','bbwp','atr','plus_di','minus_di'))
        valid=finite and a[i,2]>=max(a[i,1],a[i,3],a[i,4]) and a[i,3]<=min(a[i,1],a[i,4]) and min(a[i,1:5])>0 and a[i,5]>=0
        if not valid or (i and a[i,0]-a[i-1,0]!=HOUR):
            if tokens:audit.append(dict(i=i,status='DATA_INVALIDATED',tokens=dict(tokens)))
            tokens.clear();streak=0;continue
        streak+=1
        if streak<3:continue
        for key,t in list(tokens.items()):
            if i-t['i']>2 or ev[key]['slope'][i]*t['side']<=0:
                if trace:audit.append(dict(i=i,status='EXPIRED' if i-t['i']>2 else 'ALIGNMENT_INVALIDATED',indicator=key,token=t))
                tokens.pop(key)
        fresh={}
        for key,values in ev.items():
            s=1 if values['up'][i] else -1 if values['down'][i] else 0
            if s:fresh[key]=dict(i=i,side=s);tokens[key]=fresh[key]
        emitted=False
        if len(tokens)==4 and tokens['ao']['side']==tokens['pece']['side']:
            side=tokens['ao']['side'];identity=tuple((k,t['i'],t['side']) for k,t in sorted(tokens.items()))
            if identity in seen:raise AssertionError('CONSUMED_BUNDLE_RESURRECTED')
            seen.add(identity);emitted=True
            signals.append(dict(i=i,side=side,available_at=int(a[i,0]+HOUR),signal_id='SWING:'+str(int(a[i,0]+HOUR))+':'+str(side),
                tokens={k:dict(t,available_at=int(a[t['i'],0]+HOUR)) for k,t in tokens.items()},adx_phase=tokens['adx']['side'],bbwp_phase=tokens['bbwp']['side'],
                ao=float(f['ao'][i]),adx=float(f['adx'][i]),pececillos=float(f['minnows'][i]),red=float(f['kon_signal'][i]),tiburones=float(f['sharks'][i]),
                bbwp=float(f['bbwp'][i]),plus_di=float(f['plus_di'][i]),minus_di=float(f['minus_di'][i]),atr=float(f['atr'][i]),
                regime4h=float(f['regime4h'][i]) if np.isfinite(f['regime4h'][i]) else None,
                regime1d=float(f['regime1d'][i]) if np.isfinite(f['regime1d'][i]) else None))
            tokens.clear()
        if trace and (fresh or emitted):audit.append(dict(i=i,status='CONFIRMED' if emitted else 'PENDING',fresh=fresh,pending=dict(tokens)))
    return signals,audit
