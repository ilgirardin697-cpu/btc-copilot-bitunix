"""Descriptive overlap/latency only. Never suppresses an actual alert."""
import numpy as np
from .spec import HOUR


def compare(engine,other,window=24*HOUR):
    used_engine=set();used_other=set();paired=[]
    choices=sorted((abs(a['timestamp']-b['timestamp']),a['timestamp'],b['timestamp'],i,j)
        for i,a in enumerate(engine) for j,b in enumerate(other)
        if a['state']==b['state'] and abs(a['timestamp']-b['timestamp'])<=window)
    for _,_,_,i,j in choices:
        if i in used_engine or j in used_other:continue
        used_engine.add(i);used_other.add(j);a,b=engine[i],other[j]
        paired.append(dict(engine_id=a['id'],other_id=b['id'],lag_hours=(a['timestamp']-b['timestamp'])/HOUR))
    return dict(engine_events=len(engine),other_events=len(other),matched=len(paired),
        engine_overlap_fraction=len(paired)/len(engine) if engine else None,
        other_overlap_fraction=len(paired)/len(other) if other else None,
        median_engine_minus_other_hours=float(np.median([x['lag_hours'] for x in paired])) if paired else None,
        pairs=paired,window_hours=window/HOUR,mode='HISTORICAL_SIMULATION_NOT_DELIVERED_ALERTS')


def frequency(states,times):
    changed=np.r_[False,np.asarray(states)[1:]!=np.asarray(states)[:-1]]
    days=(times[-1]-times[0])/ (24*HOUR) if len(times)>1 else 0.
    return dict(changes=int(sum(changed)),changes_per_day=float(sum(changed)/days) if days else 0.,
        same_state_fraction=float(np.mean(np.asarray(states)[1:]==np.asarray(states)[:-1])) if len(states)>1 else None)
