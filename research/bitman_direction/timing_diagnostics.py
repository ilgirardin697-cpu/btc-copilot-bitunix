"""Supplementary existing-detail transitions, NOT new directional episodes/rules.

Primary rules/results remain frozen. This descriptive audit answers pullback vs
transition beyond the primary episode-onset cohorts; never enters promotion gates.
"""
import hashlib
from pathlib import Path
import numpy as np
from research.bitman_real.market import verified_cache
from . import core,evaluation as ev
from .study import ART,SPLITS,stamp,write,check
from .spec import CUTOFF,HOUR,VERSION

TAGS=('UP_WITH_1H_PULLBACK','DOWN_WITH_1H_PULLBACK','POSSIBLE_BULLISH_TRANSITION','POSSIBLE_BEARISH_TRANSITION')


def diagnostic_events(data,series):
    changes=np.r_[False,series['detail'][1:]!=series['detail'][:-1]]
    # These nested timing observations DO NOT rearm/reset the primary episode.
    ids=np.flatnonzero(changes&np.isin(series['detail'],TAGS));all_changes=np.flatnonzero(changes)
    rows=[]
    for i in ids:
        tag=str(series['detail'][i]);t=int(data['times'][i]);side=int(series['direction'][i])
        later=all_changes[all_changes>i]
        segment_end=int(data['times'][later[0]]) if len(later) else None
        rows.append(dict(id=hashlib.sha256(f'TIMING_DETAIL|{t}|{tag}'.encode()).hexdigest(),stream='MTF',state=tag,
            direction=side,timestamp=t,index=int(i),reference=float(data['bars'][i,4]),episode_end=segment_end,
            source='HISTORICAL_NESTED_TIMING_DIAGNOSTIC',trade_authority=False))
    return rows


def build(output=None):
    check();bars,_=verified_cache();data=core.prepare(bars,stamp(CUTOFF));series=core.series(data)
    rows=diagnostic_events(data,series);qcut=data['aligned']['1H']['atr']/bars[:,4]
    mask=(data['times']>=SPLITS['TRAIN'][0])&(data['times']<SPLITS['TRAIN'][1]);cuts=np.quantile(qcut[mask],[.25,.5,.75])
    keys=ev.control_keys(data,cuts);horizons=(4,12,24,72)
    result=dict(version=VERSION,scope='SUPPLEMENTARY_DESCRIPTIVE_NOT_PRIMARY_EPISODES',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        changes_primary_protocol=False,used_for_selection_or_classification=False,
        note='Existing frozen detail labels; nested transitions overlap primary episodes. Not independent extra signals.',
        periods={})
    for period,(a,b) in SPLITS.items():
        measured=ev.evaluate_rows(rows,data,horizons,a,b,keys);result['periods'][period]={}
        for tag in TAGS:
            group=[r for r in measured if r['state']==tag];summary=ev.group_summary(group,horizons)
            recovery=[];macro_change=[]
            for r in group:
                t=r['timestamp'];i=r['index'];side=r['direction']
                if t+72*HOUR>b:continue
                after=(data['times']>t)&(data['times']<=t+72*HOUR)
                hourly=data['aligned']['1H']['momentum'];di=data['aligned']['1H']['di_direction']
                wanted=('BULLISH_MOMENTUM','BULLISH') if side==1 else ('BEARISH_MOMENTUM','BEARISH')
                # For a pullback, direction=macro; for transition, direction=the proposed new swing.
                candidate=np.flatnonzero(after&(hourly==wanted[0])&(di==wanted[1]))
                recovery.append((data['times'][candidate[0]]-t)/HOUR if len(candidate) else None)
                old=data['aligned']['1D']['bias'][i];new='DOWN' if old=='UP' else 'UP' if old=='DOWN' else None
                macro_change.append(bool(new and np.any(data['aligned']['1D']['bias'][after]==new)))
            summary['mature_72h_for_timing']=len(recovery)
            summary['aligned_hourly_impulse_within72h']=sum(x is not None for x in recovery)/len(recovery) if recovery else None
            summary['median_hours_to_aligned_impulse']=float(np.median([x for x in recovery if x is not None])) if any(x is not None for x in recovery) else None
            summary['macro_flip_within72h']=float(np.mean(macro_change)) if macro_change else None
            result['periods'][period][tag]=summary
    write(Path(output) if output else ART/'timing_diagnostics.json',result)
    return result


if __name__=='__main__':build()
