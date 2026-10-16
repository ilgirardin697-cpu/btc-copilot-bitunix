"""Sequential DEV freeze, net simulation and TEST; never rank with TEST."""
import argparse
from collections import defaultdict
from dataclasses import asdict,replace
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from research.bitman_real.market import verified_cache,ROOT
from research.bitman_real.outcomes import measure,summarize,block_bootstrap
from research.bitman_real.indicators import roll
from . import core,ledger
from .spec import (BASE_SHA,CUTOFF,VERSION,HOUR,TIMEFRAMES,HORIZONS,FROZEN_FILES,Candidate,candidates,protocol)

ART=Path(__file__).parent/'artifacts'


def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)


SPLITS=dict(TRAIN=(stamp('2020-01-01T00:00:00Z'),stamp('2022-01-01T00:00:00Z')),
    VALIDATION=(stamp('2022-01-01T00:00:00Z'),stamp('2024-01-01T00:00:00Z')),
    TEST=(stamp('2024-01-01T00:00:00Z'),stamp(CUTOFF)))


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_hash():return hashlib.sha256(b''.join((Path(__file__).parent/p).read_bytes().replace(b'\r\n',b'\n') for p in FROZEN_FILES)).hexdigest()


def load(end=None):
    bars,manifest=verified_cache()
    with np.load(ROOT/'research/cache/bitman/hourly.npz',allow_pickle=False) as z:funding=z['funding'].copy()
    if len(funding)!=manifest['inherited_manifest'][-1]['funding_rows'] or np.any(np.diff(funding[:,0])<=0):raise ValueError('FUNDING_INVALID')
    if end is not None:bars=bars[bars[:,0]+HOUR<=end];funding=funding[funding[:,0]<end]
    return bars,funding,manifest


def freeze():
    ART.mkdir(parents=True,exist_ok=True)
    if (ART/'protocol.json').exists():raise ValueError('PROTOCOL_ALREADY_FROZEN')
    _,_,manifest=load()
    write(ART/'data_manifest.json',manifest)
    write(ART/'protocol.json',dict(protocol=protocol(),code_sha256=code_hash(),data_manifest_sha256=digest(ART/'data_manifest.json'),
        frozen_at=datetime.now(timezone.utc).isoformat(),base_sha=BASE_SHA))
    print('PHASE4_PROTOCOL_FROZEN',code_hash(),flush=True)


def check():
    p=json.loads((ART/'protocol.json').read_text())
    if p['code_sha256']!=code_hash() or p['data_manifest_sha256']!=digest(ART/'data_manifest.json'):
        raise ValueError('FROZEN_SOURCE_OR_MANIFEST_CHANGED')
    if json.dumps(p['protocol'],sort_keys=True)!=json.dumps(protocol(),sort_keys=True):raise ValueError('PROTOCOL_CHANGED')


def event_controls(f,side):
    union=np.logical_or.reduce([core.entry(f,p,side)[0] for p in candidates(side)])
    keys=[];pools=defaultdict(list)
    for i,t in enumerate(f['closes']):
        d=datetime.fromtimestamp(t/1000,timezone.utc);trend=0 if i<24 else int(np.sign(f['close'][i]-f['close'][i-24]))
        key=(d.year,d.month,d.hour,trend);keys.append(key)
        if not union[i] and np.isfinite(f['bbwp'][i]) and t>=SPLITS['TRAIN'][0]:pools[key].append(i)
    return keys,pools


def directional(item,side):
    """Keep raw BTC outcomes separately; mirror returns/excursions/races for SHORT."""
    out=dict(item)
    if not item['complete'] or side==1:return out
    out.update(forward_return=-item['forward_return'],mfe=-item['mae'],mae=-item['mfe'])
    for size in (1,2):
        out[f'first_up{size}_hour']=item[f'first_down{size}_hour']
        out[f'first_down{size}_hour']=item[f'first_up{size}_hour']
    swap={'UP_FIRST':'DOWN_FIRST','DOWN_FIRST':'UP_FIRST','AMBIGUOUS':'AMBIGUOUS','UNRESOLVED':'UNRESOLVED'}
    for key in ('race_1pct','race_2pct'):out[key]=swap[item[key]]
    return out


def event_summary(bars,f,p,side,start,end,controls=None,mask=None):
    if mask is None:mask,meta=core.entry(f,p,side)
    else:meta={}
    ids=np.flatnonzero(mask&(f['closes']>=start)&(f['closes']<end));rows=[];differences=[];times=[]
    keys,pools=controls or event_controls(f,side)
    for i in ids:
        t=int(f['closes'][i]);ref=float(f['close'][i])
        outcomes={str(h):measure(bars,t,ref,h,end) for h in HORIZONS}
        # Freeze matching without inspecting either subsequent return.
        available=[j for j in pools.get(keys[i],[]) if j!=i and start<=f['closes'][j] and f['closes'][j]+72*HOUR<=end]
        chosen=available[int(hashlib.sha256(f'{f["tf"]}|{side}|{t}'.encode()).hexdigest()[:16],16)%len(available)] if available else None
        control=measure(bars,int(f['closes'][chosen]),float(f['close'][chosen]),24,end) if chosen is not None else None
        own=outcomes['24']
        if own['complete'] and control and control['complete']:
            differences.append(side*(own['forward_return']-control['forward_return']));times.append(t)
        row=dict(timestamp=t,reference=ref,side=side,outcomes=outcomes,
            directional_outcomes={h:directional(v,side) for h,v in outcomes.items()},
            control_timestamp=int(f['closes'][chosen]) if chosen is not None else None,
            control24h=control,source='HISTORICAL_BACKTEST',
            distance_to_zero=float(abs(f['ma'][i])) if np.isfinite(f['ma'][i]) else None,
            separation=float(f['separation'][i]) if np.isfinite(f['separation'][i]) else None,
            adx=float(f['adx'][i]) if np.isfinite(f['adx'][i]) else None,
            bbwp=float(f['bbwp'][i]) if np.isfinite(f['bbwp'][i]) else None,
            regime='RANGE' if f['adx'][i]<20 else 'UNKNOWN' if not np.isfinite(f['h4_trend'][i]) else 'BULL' if f['h4_trend'][i]>0 else 'BEAR',
            day_trend=float(f['day_trend'][i]) if np.isfinite(f['day_trend'][i]) else None,
            ao_divergence=bool(f['ao_bull_div' if side==1 else 'ao_bear_div'][i]),
            daily_ao_divergence=bool(f['day_bull_div' if side==1 else 'day_bear_div'][i]==1),
            anchor_age=float(meta['anchor_age'][i]) if 'anchor_age' in meta and np.isfinite(meta['anchor_age'][i]) else None,
            anchor_kind=int(meta['anchor_kind'][i]) if 'anchor_kind' in meta else None)
        rows.append(row)
    output=dict(n_events=len(rows),horizons={str(h):summarize([r['outcomes'][str(h)] for r in rows]) for h in HORIZONS},
        directional_horizons={str(h):summarize([r['directional_outcomes'][str(h)] for r in rows]) for h in HORIZONS},
        matched24h=block_bootstrap(differences,times,seed=6241))
    mature=[r['outcomes']['24']['forward_return']*side for r in rows if r['outcomes']['24']['complete']]
    output['directional24h_mean']=float(np.mean(mature)) if mature else None
    output['anchor_latency_counts']={str(k):sum(r['anchor_age']==k for r in rows) for k in range(p.lag+1)}
    output['anchor_kind_counts']={name:sum(r['anchor_kind']==k for r in rows) for k,name in ((1,'ZERO_CROSS'),(2,'STATE_RESUME'))}
    return output,rows


def eligible(row):
    return all(row[k]['matched24h']['n']>=30 and (row[k]['matched24h']['mean'] or 0)>0
               and (row[k]['directional24h_mean'] or 0)>0 for k in ('TRAIN','VALIDATION'))


def rank(row):
    return (min(row[k]['matched24h']['mean'] if row[k]['matched24h']['mean'] is not None else -1. for k in ('TRAIN','VALIDATION')),
            min(row[k]['matched24h']['n'] for k in ('TRAIN','VALIDATION')))


def select(bars,f,side,periods=None):
    periods=periods or {k:SPLITS[k] for k in ('TRAIN','VALIDATION')};controls=event_controls(f,side);rows=[]
    for p in candidates(side):
        rows.append(dict(parameters=asdict(p),**{k:event_summary(bars,f,p,side,a,b,controls)[0] for k,(a,b) in periods.items()}))
    valid=[r for r in rows if eligible(r)]
    chosen=sorted(valid or rows,key=lambda r:(-rank(r)[0],-rank(r)[1],r['parameters']['family']))[0]
    return dict(selected=chosen['parameters'],event_eligible=bool(valid),event_development_rows=rows)


def simulate(bars,funding,f,p,side,start,end,remove=None,**kwargs):
    mask,_=core.entry(f,p,side,remove);entry,opposite,atr=core.hourly_inputs(bars,f,mask,side)
    return ledger.simulate(bars,funding,entry,opposite,atr,side,start,end,**kwargs)


def develop():
    check()
    if (ART/'selection_lock.json').exists():raise ValueError('SELECTION_ALREADY_FROZEN')
    end=SPLITS['TEST'][0];bars,funding,_=load(end);selections={}
    for tf in TIMEFRAMES:
        f=core.prepare(bars,tf,end)
        for side in (1,-1):
            key=tf+'_'+str(side);selections[key]=select(bars,f,side)
            print('PHASE4_EVENT_SELECTED',key,selections[key]['selected']['family'],selections[key]['event_eligible'],flush=True)
    lock=dict(code_sha256=code_hash(),protocol_sha256=digest(ART/'protocol.json'),
        selection=selections,development_last_closed=int(bars[-1,0]+HOUR),created_at=datetime.now(timezone.utc).isoformat())
    write(ART/'event_lock.json',lock)  # freeze event selection BEFORE net strategy check
    for tf in TIMEFRAMES:
        f=core.prepare(bars,tf,end)
        for side in (1,-1):
            s=selections[tf+'_'+str(side)];p=Candidate(**s['selected'])
            s['strategy_development']={k:simulate(bars,funding,f,p,side,a,b)['metrics'] for k,(a,b) in SPLITS.items() if k!='TEST'}
            s['strategy_eligible']=s['event_eligible'] and all(m['trades']>=20 and m['expectancy']>0 for m in s['strategy_development'].values())
    lock.update(stage='STRATEGY_ELIGIBILITY_FROZEN_NO_RERANK',event_lock_sha256=digest(ART/'event_lock.json'))
    write(ART/'selection_lock.json',lock)
    print('PHASE4_ALL_SELECTIONS_FROZEN',flush=True)


def comparisons(bars,funding,f,side,periods):
    rows={};masks=core.control_masks(f,side)
    for name,mask in masks.items():
        if mask is None:continue
        e,o,a=core.hourly_inputs(bars,f,mask,side)
        rows[name]={period:ledger.simulate(bars,funding,e,o,a,side,start,end)['metrics'] for period,(start,end) in periods.items()}
        if name=='KONKORDE_ENTRY':
            native=core.align(f['frame'][:,0],(~f['inside']).astype(float),TIMEFRAMES[f['tf']],bars[:,0])==1
            rows['KONKORDE_NATIVE']={period:ledger.simulate(bars,funding,e,native,a,side,start,end)['metrics'] for period,(start,end) in periods.items()}
    if side==1:
        h4=aggregate_for_v8(bars);mean=roll(h4[:,4],200)
        v=core.align(h4[:,0],np.where(np.isfinite(mean),(h4[:,4]>mean).astype(float),np.nan),4*HOUR,bars[:,0])
        rows['V8']={period:ledger.simulate(bars,funding,v==1,v==0,np.ones(len(bars)),1,start,end,benchmark=True)['metrics'] for period,(start,end) in periods.items()}
    return rows


def aggregate_for_v8(bars):return core.aggregate(bars,4*HOUR,int(bars[-1,0]+HOUR))


def neighbors(p,side):
    result=[replace(p,lag=x) for x in (3,9)]
    if p.family=='C1_BBWP50':result += [replace(p,bb_reference=x) for x in (40.,60.)]
    if p.family=='C5_K_REENTRY':result += [replace(p,reentry_bars=x) for x in (2,5)]
    return result


def trade_cohorts(result,f,vol_cut):
    groups=defaultdict(list)
    for t in result['trades']:
        i=np.searchsorted(f['closes'],t['signal_known_at'],side='right')-1
        regime='RANGE' if f['adx'][i]<20 else 'UNKNOWN' if not np.isfinite(f['h4_trend'][i]) else 'BULL' if f['h4_trend'][i]>0 else 'BEAR'
        groups[regime].append(t['net_return']);groups['HIGH_VOL' if f['atr'][i]/f['close'][i]>=vol_cut else 'LOW_VOL'].append(t['net_return'])
        daily=f['day_trend'][i]
        groups['DAY_UNKNOWN' if not np.isfinite(daily) else 'DAY_ALIGNED' if daily*t['side']>0 else 'DAY_OPPOSED'].append(t['net_return'])
    return {k:dict(n=len(v),expectancy=float(np.mean(v)),win_rate=float(np.mean(np.array(v)>0))) for k,v in groups.items()}


def descriptive_events(rows,tf):
    # Existing PR23 TRAIN cutpoints; descriptive only, never affect selection.
    bins=json.loads((ROOT/'research/bitman_real/artifacts/train_descriptive_bins.json').read_text())[tf]
    groups=defaultdict(list)
    for r in rows:
        if not r['directional_outcomes']['24']['complete']:continue
        v=r['directional_outcomes']['24']['forward_return']
        for field in ('distance_to_zero','separation'):
            if r[field] is not None:
                tag=('LOW','MID','HIGH')[int(np.searchsorted(bins[field]['tertiles'],r[field],side='right'))]
                groups[field+'/'+tag].append(v)
        groups['regime/'+r['regime']].append(v)
        groups['divergence/'+str(r['ao_divergence'])].append(v)
        groups['daily_divergence/'+str(r['daily_ao_divergence'])].append(v)
    return {k:dict(n=len(v),mean=float(np.mean(v)),median=float(np.median(v))) for k,v in groups.items()}


def walk_forward(bars,funding):
    out={}
    for year in range(2022,2027):
        start=stamp(f'{year}-01-01T00:00:00Z');end=min(stamp(f'{year+1}-01-01T00:00:00Z'),stamp(CUTOFF))
        dev=bars[bars[:,0]+HOUR<=start];sample=bars[bars[:,0]+HOUR<=end]
        periods=dict(TRAIN=(SPLITS['TRAIN'][0],stamp(f'{year-1}-01-01T00:00:00Z')),VALIDATION=(stamp(f'{year-1}-01-01T00:00:00Z'),start))
        out[str(year)]={}
        for tf in TIMEFRAMES:
            f=core.prepare(dev,tf,start);trial=core.prepare(sample,tf,end)
            for side in (1,-1):
                selected=select(dev,f,side,periods);p=Candidate(**selected['selected'])
                devmetrics={k:simulate(dev,funding,f,p,side,a,b)['metrics'] for k,(a,b) in periods.items()}
                net_eligible=selected['event_eligible'] and all(m['trades']>=20 and m['expectancy']>0 for m in devmetrics.values())
                out[str(year)][tf+'_'+str(side)]=dict(selected=asdict(p),strategy_eligible=net_eligible,selection_cutoff=start,
                    metrics=simulate(sample,funding,trial,p,side,start,end)['metrics'])
        print('PHASE4_WALK_FORWARD',year,flush=True)
    return out


def evaluate(output_dir=None):
    check();out=Path(output_dir) if output_dir else ART;out.mkdir(parents=True,exist_ok=True)
    if (out/'results.json').exists():raise ValueError('RESULTS_ALREADY_EXIST')
    lock=json.loads((ART/'selection_lock.json').read_text())
    if lock['code_sha256']!=code_hash() or lock['protocol_sha256']!=digest(ART/'protocol.json'):raise ValueError('SELECTION_LOCK_MISMATCH')
    bars,funding,_=load();result=dict(version=VERSION,source='HISTORICAL_BACKTEST',code_sha256=code_hash(),
        selection_sha256=digest(ART/'selection_lock.json'),events={},selected={},comparators={},event_comparators={},trade_authority=False,
        private_bitman_parity='NOT PROVEN',forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR')
    all_event_rows=[];all_trades={}
    years={str(y):(stamp(f'{y}-01-01T00:00:00Z'),min(stamp(f'{y+1}-01-01T00:00:00Z'),stamp(CUTOFF))) for y in range(2020,2027)}
    for tf in TIMEFRAMES:
        f=core.prepare(bars,tf,stamp(CUTOFF))
        vol_cut=float(np.nanmedian((f['atr']/f['close'])[(f['closes']>=SPLITS['TRAIN'][0])&(f['closes']<SPLITS['TRAIN'][1])]))
        for side in (1,-1):
            key=tf+'_'+str(side);result['events'][key]={};controls=event_controls(f,side)
            for p in candidates(side):
                periods={}
                for name,(a,b) in SPLITS.items():
                    summary,rows=event_summary(bars,f,p,side,a,b,controls);summary['descriptive_cohorts24h']=descriptive_events(rows,tf);periods[name]=summary
                    all_event_rows += [dict(r,timeframe=tf,family=p.family,period=name) for r in rows]
                result['events'][key][p.family]=periods
            result['event_comparators'][key]={name:{period:event_summary(bars,f,Candidate(),side,a,b,controls,mask)[0]
                for period,(a,b) in SPLITS.items()} for name,mask in core.control_masks(f,side).items() if mask is not None}
            chosen=lock['selection'][key];p=Candidate(**chosen['selected'])
            trials={k:simulate(bars,funding,f,p,side,a,b) for k,(a,b) in SPLITS.items()}
            test=trials['TEST'];a,b=SPLITS['TEST'];adjacent=[];duplicates=[]
            parent_signal=hashlib.sha256(core.entry(f,p,side)[0].tobytes()).hexdigest();seen={parent_signal}
            for q in neighbors(p,side):
                mask,_=core.entry(f,q,side);sig=hashlib.sha256(mask.tobytes()).hexdigest()
                if sig in seen:
                    duplicates.append(dict(parameters=asdict(q),signal_sha256=sig,reason='IDENTICAL_TO_PARENT_OR_PREVIOUS_NEIGHBOR'))
                    continue
                seen.add(sig);adjacent.append(dict(parameters=asdict(q),signal_sha256=sig,
                    metrics=simulate(bars,funding,f,q,side,a,b)['metrics']))
            for stop in (1.6,2.4):adjacent.append(dict(stop_atr=stop,metrics=simulate(bars,funding,f,p,side,a,b,stop_atr=stop)['metrics']))
            yearly={y:simulate(bars,funding,f,p,side,a,b)['metrics'] for y,(a,b) in years.items()}
            ablation={k:simulate(bars,funding,f,p,side,*SPLITS['TEST'],remove=k)['metrics'] for k in ('AO','ADX_DI','BBWP','KONKORDE')}
            net=dict(parameters=asdict(p),event_eligible=chosen['event_eligible'],development_eligible=chosen['strategy_eligible'],
                splits={k:r['metrics'] for k,r in trials.items()},yearly=yearly,neighbors=adjacent,duplicate_neighbors=duplicates,ablation=ablation,
                stress=simulate(bars,funding,f,p,side,*SPLITS['TEST'],costs=ledger.STRESS_COSTS)['metrics'],
                costs={str(fee):simulate(bars,funding,f,p,side,*SPLITS['TEST'],costs=dict(fee_bps=fee,slip_bps=2,stop_slip_bps=5))['metrics'] for fee in (5,10,20)},
                without_best=ledger.removal(test,1),without_best3=ledger.removal(test,3),bootstrap=ledger.bootstrap(test),
                alternate_trailing=simulate(bars,funding,f,p,side,*SPLITS['TEST'],trailing=True)['metrics'],
                cohorts=trade_cohorts(test,f,vol_cut),train_vol_cut=vol_cut)
            result['selected'][key]=net;result['comparators'][key]=comparisons(bars,funding,f,side,SPLITS)
            all_trades[key]={k:r['trades'] for k,r in trials.items()}
            print('PHASE4_FROZEN_TEST',key,p.family,test['metrics']['expectancy'],flush=True)
    result['walk_forward']=walk_forward(bars,funding)
    for key,r in result['selected'].items():
        m=r['splits']['TEST'];side=int(key.split('_')[1]);p=Candidate(**r['parameters'])
        tf=key.split('_')[0];event=result['events'][key][p.family]['TEST']['matched24h']['mean']
        wf_positive=sum(result['walk_forward'][str(y)][key]['metrics']['total_return']>0 for y in range(2022,2027))
        baseline=result['comparators'][key]['AO_ADX']['TEST']
        development_rows=lock['selection'][key]['event_development_rows']
        selected_dev=next(x for x in development_rows if x['parameters']['family']==p.family)
        no_k_dev=next(x for x in development_rows if x['parameters']['family']=='C0_IMPULSE')
        k_increment=not p.family.startswith(('C2','C3','C4','C5')) or all(
            selected_dev[k]['matched24h']['mean'] is not None and no_k_dev[k]['matched24h']['mean'] is not None and
            selected_dev[k]['matched24h']['mean']>no_k_dev[k]['matched24h']['mean'] for k in ('TRAIN','VALIDATION'))
        gates=dict(development_eligible=r['development_eligible'],expectancy_positive=m['expectancy']>0,
            pf_gt1_20=m['profit_factor'] is not None and m['profit_factor']>1.2,sharpe_gt0_75=m['sharpe']>.75,
            maxdd_lt25pct=m['max_dd']>-.25,sample_at_least100=m['trades']>=100,
            neighbors_positive=sum(n['metrics']['expectancy']>0 for n in r['neighbors'])/len(r['neighbors'])>=.75,
            stress_positive=r['stress']['expectancy']>0,without_best3_positive=r['without_best3']['expectancy']>0,
            yearly_at_least2=sum(r['yearly'][str(y)]['total_return']>0 for y in (2024,2025,2026))>=2,
            matched_event_advantage=event is not None and event>0,walk_forward_at_least3=wf_positive>=3,
            comparator_advantage=m['total_return']>baseline['total_return'] or m['total_return']>0 and m['max_dd']>baseline['max_dd'],
            incremental_k_development=k_increment,not_insolvent=not m['insolvent'])
        r['gates']=gates;r['classification']='PROMISING FOR SHADOW' if all(gates.values()) else 'REJECT' if m['expectancy']<=0 else 'INCONCLUSIVE'
    result['classification']='PROMISING FOR SHADOW' if any(x['classification']=='PROMISING FOR SHADOW' for x in result['selected'].values()) else 'REJECT' if all(x['classification']=='REJECT' for x in result['selected'].values()) else 'INCONCLUSIVE'
    with gzip.open(out/'events.jsonl.gz','wt',encoding='utf-8') as stream:
        for r in all_event_rows:stream.write(json.dumps(r,allow_nan=False)+'\n')
    with gzip.open(out/'trades.json.gz','wt',encoding='utf-8') as stream:json.dump(all_trades,stream,allow_nan=False)
    write(out/'results.json',result);print('PHASE4_CLASSIFICATION',result['classification'],flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','develop','evaluate']);p.add_argument('--output-dir')
    a=p.parse_args();freeze() if a.phase=='freeze' else develop() if a.phase=='develop' else evaluate(a.output_dir)
