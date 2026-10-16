"""Future outcomes are evaluators only; never a dependency of engine state."""
from datetime import datetime,timezone
import hashlib
import numpy as np
from .spec import HOUR,FALSE_REVERSAL_HOURS


def episodes(states,times,prices,side=None,stream='MTF'):
    rows=[];previous=None
    for i,(state,t,price) in enumerate(zip(states,times,prices)):
        if state==previous:continue
        if rows:rows[-1]['episode_end']=int(t)
        value=1 if state=='UP' else -1 if state=='DOWN' else int(side[i]) if side is not None else 0
        rows.append(dict(id=hashlib.sha256(f'{stream}|{int(t)}|{state}'.encode()).hexdigest(),
            stream=stream,state=str(state),direction=value,timestamp=int(t),index=i,reference=float(price),
            episode_end=None,source='HISTORICAL_SIMULATION',trade_authority=False))
        previous=state
    return rows


def measure(bars,t,ref,side,horizon,end):
    if t+horizon*HOUR>end:return dict(complete=False,reason='HORIZON_OR_SPLIT_NOT_MATURE')
    i=int(np.searchsorted(bars[:,0],t));a=bars[i:i+horizon]
    if len(a)!=horizon or not np.array_equal(a[:,0],t+np.arange(horizon)*HOUR):return dict(complete=False,reason='MISSING_CLOSED_HOURLY_DATA')
    out=dict(complete=True,raw_return=float(a[-1,4]/ref-1),signed_return=None,hit_direction=None,mfe=None,mae=None,targets={})
    if side not in (1,-1):return out
    favorable=a[:,2]/ref-1 if side==1 else 1-a[:,3]/ref
    adverse=a[:,3]/ref-1 if side==1 else 1-a[:,2]/ref
    out.update(signed_return=float(side*(a[-1,4]/ref-1)),mfe=float(max(0,max(favorable))),mae=float(min(0,min(adverse))))
    out['hit_direction']=out['signed_return']>0
    for target in (.02,.05,.10):
        f=np.flatnonzero(favorable>=target);b=np.flatnonzero(adverse<=-target)
        good=int(f[0]) if len(f) else None;bad=int(b[0]) if len(b) else None
        race='UNRESOLVED' if good is None and bad is None else 'FAVORABLE_FIRST' if bad is None or good is not None and good<bad else 'ADVERSE_FIRST' if good is None or bad<good else 'AMBIGUOUS'
        prior=float(max(0,-min(adverse[:good]))) if good is not None and good else 0. if good==0 else None
        inclusive=float(max(0,-min(adverse[:good+1]))) if good is not None else None
        out['targets'][str(int(target*100))]=dict(favorable_hour=good+1 if good is not None else None,
            adverse_hour=bad+1 if bad is not None else None,race=race,
            adverse_before_touch_definite=prior,adverse_through_touch_bar_upper_bound=inclusive)
    return out


def summarize(items):
    valid=[x for x in items if x['complete']];directional=[x for x in valid if x['signed_return'] is not None]
    out=dict(n_total=len(items),n_complete=len(valid),n_incomplete=len(items)-len(valid),n_directional=len(directional))
    if valid:out['raw_return_mean']=float(np.mean([x['raw_return'] for x in valid]))
    if not directional:return out
    for field in ('signed_return','mfe','mae'):
        a=[x[field] for x in directional];out[field]=dict(mean=float(np.mean(a)),median=float(np.median(a)))
    out['directional_accuracy']=float(np.mean([x['hit_direction'] for x in directional]))
    out['targets']={}
    for key in ('2','5','10'):
        q=[x['targets'][key] for x in directional]
        favorable=[x['favorable_hour'] for x in q if x['favorable_hour'] is not None]
        adverse=[x['adverse_hour'] for x in q if x['adverse_hour'] is not None]
        out['targets'][key]=dict(n=len(q),favorable_hit_rate=len(favorable)/len(q),adverse_hit_rate=len(adverse)/len(q),
            median_hour_to_target=float(np.median(favorable)) if favorable else None,
            median_hour_to_adverse=float(np.median(adverse)) if adverse else None,
            race={tag:sum(x['race']==tag for x in q)/len(q) for tag in ('FAVORABLE_FIRST','ADVERSE_FIRST','AMBIGUOUS','UNRESOLVED')},
            median_adverse_before_touch=float(np.median([x['adverse_before_touch_definite'] for x in q if x['favorable_hour'] is not None])) if favorable else None,
            median_adverse_including_touch_bar=float(np.median([x['adverse_through_touch_bar_upper_bound'] for x in q if x['favorable_hour'] is not None])) if favorable else None)
    return out


def paired_bootstrap(values,times):
    if not len(values):return dict(n=0,mean=None,ci95=[None,None])
    weeks=np.asarray(times,dtype=np.int64)//(168*HOUR);unique=np.arange(weeks.min(),weeks.max()+1)
    sums=np.array([np.asarray(values)[weeks==w].sum() for w in unique]);counts=np.array([sum(weeks==w) for w in unique])
    rng=np.random.default_rng(8192);means=[]
    for _ in range(1000):
        ids=rng.integers(0,len(unique),len(unique));n=counts[ids].sum()
        if n:means.append(float(sums[ids].sum()/n))
    return dict(n=len(values),mean=float(np.mean(values)),ci95=np.quantile(means,[.025,.975]).tolist(),blocks='calendar7day',repetitions=1000,seed=8192,independent_events=False)


def control_keys(data,vol_cut):
    volatility=data['aligned']['1H']['atr']/data['bars'][:,4];quartile=np.searchsorted(vol_cut,volatility)
    keys=[]
    for t,r,q in zip(data['times'],data['regime'],quartile):
        date=datetime.fromtimestamp(t/1000,timezone.utc)
        keys.append((date.year,date.month,date.hour,int(r) if np.isfinite(r) else 0,int(q)))
    return keys


def evaluate_rows(rows,data,horizons,start,end,keys,interval=HOUR):
    from collections import defaultdict
    event_times={r['timestamp'] for r in rows};pools=defaultdict(list)
    for i,t in enumerate(data['times']):
        if start<=t<end and t%interval==0 and int(t) not in event_times:pools[keys[i]].append(i)
    evaluated=[];prior_rows=[];last=None
    for r in rows:
        prior_rows.append(last)
        if r['state'] in ('UP','DOWN'):last=r
    later_rows=[None]*len(rows);last=None
    for k in range(len(rows)-1,-1,-1):
        later_rows[k]=last
        if rows[k]['state'] in ('UP','DOWN'):last=rows[k]
    for position,row in enumerate(rows):
        t=row['timestamp']
        if not start<=t<end:continue
        r=dict(row);r['outcomes']={};r['control_outcomes']={};r['paired_excess']={}
        own=data['bars'][r['index'],4]
        for h in horizons:
            r['outcomes'][str(h)]=measure(data['bars'],t,own,r['direction'],h,end)
            candidates=[i for i in pools.get(keys[r['index']],[]) if data['times'][i]+h*HOUR<=end]
            control=[];ids=[]
            if candidates:
                rotate=int(hashlib.sha256((r['id']+'|'+str(h)).encode()).hexdigest()[:16],16)%len(candidates)
                ids=(candidates[rotate:]+candidates[:rotate])[:3]
                control=[measure(data['bars'],int(data['times'][i]),data['bars'][i,4],r['direction'],h,end) for i in ids]
            valid=[x for x in control if x['complete']]
            field='signed_return' if r['direction'] else 'raw_return'
            summary=float(np.mean([x[field] for x in valid])) if valid else None
            r['control_outcomes'][str(h)]=dict(n=len(valid),mean=summary,timestamps=[int(data['times'][i]) for i in ids])
            result=r['outcomes'][str(h)]
            r['paired_excess'][str(h)]=float(result[field]-summary) if result['complete'] and summary is not None else None
        episode_end=min(r['episode_end'] or end,end)
        duration=max(0,int((episode_end-t)//HOUR));r['persistence_hours']=duration;r['persistence_censored']=r['episode_end'] is None or r['episode_end']>end
        r['episode_extension']=measure(data['bars'],t,own,r['direction'],min(duration,336),end) if duration else dict(complete=False,reason='NO_CLOSED_FORWARD_BAR')
        window=FALSE_REVERSAL_HOURS[row['stream']] if row['stream'] in FALSE_REVERSAL_HOURS else 24
        prior=prior_rows[position];later=later_rows[position]
        r['false_reversal']=None if t+window*HOUR>end or row['state'] not in ('UP','DOWN') else bool(
            prior and prior['state']!=r['state'] and later and later['state']==prior['state'] and later['timestamp']<=t+window*HOUR)
        evaluated.append(r)
    return evaluated


def group_summary(rows,horizons):
    out=dict(n_episodes=len(rows),horizons={str(h):summarize([r['outcomes'][str(h)] for r in rows]) for h in horizons},
        matched={str(h):paired_bootstrap([r['paired_excess'][str(h)] for r in rows if r['paired_excess'][str(h)] is not None],
                                       [r['timestamp'] for r in rows if r['paired_excess'][str(h)] is not None]) for h in horizons},
        episode_extension=summarize([r['episode_extension'] for r in rows]),
        median_persistence_hours=float(np.median([r['persistence_hours'] for r in rows])) if rows else None,
        false_reversal_n=sum(r['false_reversal'] is not None for r in rows),
        false_reversal_rate=float(np.mean([r['false_reversal'] for r in rows if r['false_reversal'] is not None])) if any(r['false_reversal'] is not None for r in rows) else None)
    return out
