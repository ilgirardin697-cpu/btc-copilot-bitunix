"""Adapter only. Frozen observer mathematical source remains byte-identical."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .data import CACHE, HOUR
from .vendor.mlrsi_math import CausalSeries, ResearchEvents


def frozen_source_ok():
    root=Path(__file__).parent/'vendor'
    expected=json.loads((root/'SOURCE.json').read_text())['sha256']
    if hashlib.sha256((root/'mlrsi_math.py').read_bytes()).hexdigest()!=expected:
        raise ValueError('FROZEN_MLRSI_MATH_CHANGED')
    return expected


def features(bars, use_cache=True):
    """Known-history calendar-year sessions; no anchor at end of unseen TEST."""
    source_sha=frozen_source_ok()
    years=np.array([datetime.fromtimestamp(t/1000,timezone.utc).year for t in bars[:,0]])
    state=np.full(len(bars),np.nan); resume_long=np.zeros(len(bars),bool); resume_short=np.zeros(len(bars),bool)
    raw=np.full(len(bars),np.nan); upper=raw.copy(); lower=raw.copy(); smooth=raw.copy()
    for year in np.unique(years):
        where=np.flatnonzero(years==year); i,j=int(where[0]),int(where[-1])+1
        start=max(0,i-3200)
        key=hashlib.sha256(bars[start:j].tobytes()+source_sha.encode()).hexdigest()[:24]
        path=CACHE/f'mlrsi-{year}-{key}.npz'
        names=('state','resume_long','resume_short','raw','upper','lower','smooth')
        targets=(state,resume_long,resume_short,raw,upper,lower,smooth)
        if use_cache and path.exists():
            z=np.load(path)
            for name,target in zip(names,targets): target[i:j]=z[name]
            continue
        series=CausalSeries(); series.configure_bootstrap(max(0,i-start-1))
        events=ResearchEvents(HOUR)
        for k in range(start,j):
            result=series.push(bars[k,3]); event=events.step(int(bars[k,0])+HOUR,result)
            if k>=i:
                state[k]={'GREEN':1.,'RED':-1.,'NEUTRAL':0.}.get(result['color'],np.nan)
                resume_long[k]=event=='GREEN_RESUME'; resume_short[k]=event=='RED_RESUME'
                for target,name in ((raw,'mlrsi_raw'),(upper,'upper_threshold'),(lower,'lower_threshold'),(smooth,'mlrsi_smoothed')):
                    target[k]=result[name] if result[name] is not None else np.nan
        if use_cache:
            CACHE.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(path,**{name:target[i:j] for name,target in zip(names,targets)})
        print('BITMAN_FROZEN_MLRSI_YEAR',year,j-i,flush=True)
    return dict(ml_state=state,ml_resume_long=resume_long,ml_resume_short=resume_short,
                ml_raw=raw,ml_upper=upper,ml_lower=lower,ml_smoothed=smooth)
