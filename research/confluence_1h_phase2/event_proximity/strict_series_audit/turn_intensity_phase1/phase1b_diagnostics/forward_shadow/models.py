"""Independent incremental22/11 protocols. No comparative-layer inputs."""
import numpy as np
from ... import detect as frozen

PROFILES={'TURN22_FORWARD_V1':2,'TURN11_EXPLORATORY_V1':1}


def turns(x,side,n):
    if n not in (1,2):raise ValueError('FROZEN_TURN_LENGTH')
    d=np.asarray(x)-frozen.lag(x)
    return np.logical_and.reduce([side*frozen.lag(d,j)>0 for j in range(n)]+
                                 [side*frozen.lag(d,j)<0 for j in range(n,2*n)])


def feature_sets(a):
    original=frozen.features(a)
    one=dict(original)
    one['adx_curve']=abs(original['adx_slope']-frozen.lag(original['adx_slope']))
    one['ao_intensity']=abs(original['ao']-frozen.lag(original['ao']))/a[:,4]
    one['pece_intensity']=abs(original['minnows']-frozen.lag(original['minnows']))
    for k in ('adx_curve','ao_intensity','pece_intensity'):one[k+'_rank']=frozen.prior_rank(one[k])
    return {'TURN22_FORWARD_V1':original,'TURN11_EXPLORATORY_V1':one}


class Engine:
    def __init__(self,profile):
        if profile not in PROFILES:raise ValueError('UNKNOWN_PROTOCOL')
        self.profile=profile;self.n=PROFILES[profile];self.valid_run=0
        self.pending={(p,s):{} for p in frozen.PATTERNS for s in (1,-1)}
        self.last={k:-1000 for k in self.pending}

    def step(self,i,a,f):
        n=self.n;events=[];audit=[];attempts=[]
        finite=np.isfinite(a[i]).all() and all(np.isfinite(f[k][i]) for k in ('ao','minnows','adx','plus_di','minus_di','atr'))
        candle=finite and min(a[i,1:5])>0 and a[i,2]>=max(a[i,1],a[i,3],a[i,4]) and a[i,3]<=min(a[i,1],a[i,4])
        if not candle or (i and a[i,0]-a[i-1,0]!=frozen.HOUR):
            for key,tokens in self.pending.items():
                if tokens:audit.append(dict(i=i,pattern=key[0],side=key[1],status='DATA_INVALIDATED'))
                tokens.clear()
            self.valid_run=0;return events,audit,attempts
        self.valid_run+=1
        if self.valid_run<2*n+1:return events,audit,attempts
        def turn(k,side):
            x=f[k];post=all(side*(x[i-j]-x[i-j-1])>0 for j in range(n))
            pre=all(side*(x[i-j]-x[i-j-1])<0 for j in range(n,2*n))
            return bool(post and pre)
        ao,pece,adx=f['ao'],f['minnows'],f['adx']
        for key,tokens in self.pending.items():
            p,side=key;statuses=[]
            pece_ok=bool(side*(pece[i]-pece[i-1])>0);ao_ok=bool(side*(ao[i]-ao[i-1])>0)
            if p==frozen.PATTERNS[0]:
                ao_ok &= side*ao[i]<0;adx_ok=adx[i]<adx[i-1]
                ao_event=turn('ao',side) and np.all(side*ao[i-(2*n-1):i+1]<0);adx_event=turn('adx',-1)
            elif p==frozen.PATTERNS[1]:
                adx_ok=adx[i]>adx[i-1]
                adx_ok &= f['plus_di'][i]>f['minus_di'][i] if side==1 else f['minus_di'][i]>f['plus_di'][i]
                ao_event,adx_event=turn('ao',side),turn('adx',1)
            else:
                ao_ok &= side*ao[i]>0;ao_event=turn('ao',side) and np.all(side*ao[i-2*n:i+1]>0)
                adx_ok,adx_event=True,False
            def note(status):
                audit.append(dict(i=i,pattern=p,side=side,status=status));statuses.append(status)
            if tokens and i-min(t['i'] for t in tokens.values())>2:note('EXPIRED');tokens.clear()
            if tokens and not (pece_ok and ao_ok and adx_ok):note('ALIGNMENT_INVALIDATED');tokens.clear()
            pece_event=turn('minnows',side)
            if ao_event:tokens['ao']=dict(i=i,rank=float(f['ao_intensity_rank'][i]))
            if pece_event:tokens['pece']=dict(i=i,rank=float(f['pece_intensity_rank'][i]))
            if adx_event:
                level=f['adx_rank'][i-n];tail=level if p==frozen.PATTERNS[0] else 1-level
                tokens['adx']=dict(i=i,rank=float(min(tail,f['adx_curve_rank'][i])) if np.isfinite([tail,f['adx_curve_rank'][i]]).all() else float('nan'))
            needed={'ao','pece'} if p==frozen.PATTERNS[2] else {'ao','pece','adx'}
            missing=sorted(needed-set(tokens));score=None;emitted=False
            if not missing and pece_ok and ao_ok and adx_ok:
                values=[tokens[k]['rank'] for k in needed];score=min(values) if np.isfinite(values).all() else np.nan
                status='COOLDOWN' if i-self.last[key]<25 else 'EPISODE';note(status)
                if status=='EPISODE':
                    emitted=True;self.last[key]=i
                    row=dict(i=i,pattern=p,side=side,available_at=int(a[i,0]+frozen.HOUR),
                             event_id=f'{p}:{side}:{int(a[i,0]+frozen.HOUR)}',intensity=score,
                             ao=float(ao[i]),ao_normalized=float(f['ao_level_normalized'][i]),ao_slope_normalized=float(f['ao_slope_normalized'][i]),
                             adx=float(adx[i]),adx_curve=float(f['adx_curve'][i]),pececillos=float(pece[i]),pece_turn=float(f['pece_intensity'][i]),
                             bbwp=float(f['bbwp'][i]),tokens={k:t['i'] for k,t in tokens.items()},four_h=f['regime4h'][i],daily=f['regime1d'][i])
                    row['strata']=[s for s,q in frozen.STRATA.items() if q==0 or (np.isfinite(score) and score>=q)];events.append(row)
                tokens.clear()
            attempts.append(dict(pattern=p,side=side,primitive_ao=bool(ao_event),primitive_adx=bool(adx_event),primitive_pece=pece_event,
                                 aligned_ao=bool(ao_ok),aligned_pece=pece_ok,aligned_adx_dmi=bool(adx_ok),
                                 missing_tokens=missing,pending={k:t['i'] for k,t in tokens.items()},statuses=statuses,
                                 emitted=emitted,intensity=score,
                                 q75=bool(emitted and np.isfinite(score) and score>=.75),q90=bool(emitted and np.isfinite(score) and score>=.9)))
        return events,audit,attempts

    def warm(self,a,f):
        events=[];audit=[]
        for i in range(len(a)):
            ee,aa,_=self.step(i,a,f);events.extend(ee);audit.extend(aa)
        return events,audit
