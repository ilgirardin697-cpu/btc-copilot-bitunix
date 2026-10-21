"""Explicit offline freeze/run entry points. Importing performs no work."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from . import data as market
from .features import prepare,raw_events,gates
from .simulation import simulate,COSTS
from .statistics import summarize,paired,classify,SEED
from .report import report

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=Path(__file__).resolve().parent
ART=PACKAGE/'artifacts'
BASE='fc211d8e36c6db55185efa8309eb8f980beab2ea'
VARIANTS=('AO_ONLY','AO_CONTEXT','AO_DMI','AO_FE','AO_DMI_FE')
EXITS=('ATR_2R','STRUCTURE_2R')
BOUND=('specification.md','data.py','features.py','simulation.py','statistics.py','study.py','report.py')
def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
def hashes():
    return {n:hashlib.sha256((PACKAGE/n).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for n in BOUND}
def year(t):return datetime.fromtimestamp(int(t)/1000,timezone.utc).year
def month(t):return datetime.fromtimestamp(int(t)/1000,timezone.utc).strftime('%Y-%m')
def split(t):return 'DEVELOPMENT' if year(t)<2022 else 'VALIDATION' if year(t)<2024 else 'REUSED_EVALUATION'

def eligible(data,i):
    f,dt=data['features'],data['interval'];t=int(data['available_at'][i])
    if t<market.START or t>=market.END:return False
    y=year(t);first=int(datetime(y,1,1,tzinfo=timezone.utc).timestamp()*1000)
    last=min(int(datetime(y+1,1,1,tzinfo=timezone.utc).timestamp()*1000),market.END)
    embargo=48*dt
    finite=all(np.isfinite(f[k][i]) for k in ('ao','ao_slope','atr','adx_slope','di_plus','di_minus','fe_slope','h4_ao','d1_ao','regime','low6','high6'))
    return finite and t>=first+embargo and t+embargo<=last

def anchors(data,family):
    raw=raw_events(data,family);spacing=48*data['interval'];last=-spacing;selected=[]
    counts=Counter(raw_events=int(np.count_nonzero(raw)),ineligible=0,thinned=0)
    for i in np.flatnonzero(raw):
        if not eligible(data,int(i)):counts['ineligible']+=1;continue
        t=int(data['available_at'][i])
        if t-last<spacing:counts['thinned']+=1;continue
        selected.append((int(i),int(raw[i])));last=t
    counts['anchors']=len(selected)
    return selected,dict(counts)

def controls(data,events,seed):
    dt=data['interval'];f=data['features'];times=data['available_at']
    pools={}
    for i in range(len(times)):
        if eligible(data,i):
            key=(month(times[i]),int(f['regime'][i]));pools.setdefault(key,[]).append(i)
    used=[];rng=np.random.default_rng(seed);result={}
    for i,side in events:
        key=(month(times[i]),int(f['regime'][i]));pool=np.asarray(pools.get(key,[]),int)
        for j in rng.permutation(pool):
            t=int(times[j])
            if j==i or any(abs(t-u)<48*dt for u in used):continue
            used.append(t);result[i]=(int(j),side);break
    return result

def incremental_stats(rows,parent_rows,parent):
    if not rows or not parent_rows:return dict(parent=parent,mean_delta_R=None,ci95_delta_R=[None,None],n_parent=len(parent_rows),n_filtered=len(rows))
    width=30*86400000;t0=min(r['signal_time'] for r in rows+parent_rows)//width
    t1=max(r['signal_time'] for r in rows+parent_rows)//width
    n=int(t1-t0+1)
    if n<2:return dict(parent=parent,mean_delta_R=summarize(rows,bootstrap=False)['mean_R']-summarize(parent_rows,bootstrap=False)['mean_R'],ci95_delta_R=[None,None],n_parent=len(parent_rows),n_filtered=len(rows))
    rng=np.random.default_rng(SEED);counts=[];totals=[]
    for cohort in (rows,parent_rows):
        ids=np.asarray([r['signal_time']//width-t0 for r in cohort],int)
        counts.append(np.bincount(ids,minlength=n))
        totals.append(np.bincount(ids,weights=[r['costs']['BASE']['net_R'] for r in cohort],minlength=n))
    draw=rng.integers(0,n,size=(5000,n));den=[c[draw].sum(axis=1) for c in counts];ok=(den[0]>0)&(den[1]>0)
    dif=totals[0][draw].sum(axis=1)[ok]/den[0][ok]-totals[1][draw].sum(axis=1)[ok]/den[1][ok]
    return dict(parent=parent,mean_delta_R=summarize(rows,bootstrap=False)['mean_R']-summarize(parent_rows,bootstrap=False)['mean_R'],
        ci95_delta_R=np.quantile(dif,[.025,.975]).tolist(),n_parent=len(parent_rows),n_filtered=len(rows))

def run_dataset(base,funding,interval,families):
    d=prepare(base,interval);all_rows=[];out={};quality={}
    for k,family in enumerate(families):
        events,counts=anchors(d,family);matched=controls(d,events,SEED+interval+k)
        quality[family]=dict(**counts,random_timestamps_matched=len(matched))
        outcomes={};reference={};excluded=Counter()
        for i,side in events:
            anchor=f'{interval}:{family}:{int(d["available_at"][i])}:{side}';gate=gates(d,i,side,family)
            for exit_kind in EXITS if interval==market.HOUR else EXITS[:1]:
                trade,error=simulate(base,funding,d,i,side,exit_kind)
                if error:excluded[exit_kind+':'+error]+=1;continue
                f=d['features'];trade.update(anchor_id=anchor,signal_index=i,family=family,timeframe='1H' if interval==market.HOUR else '15m',
                    exit_kind=exit_kind,split=split(trade['signal_time']),year=year(trade['signal_time']),regime=int(f['regime'][i]),
                    context=dict(ao=float(f['ao'][i]),ao_slope=float(f['ao_slope'][i]),adx=float(f['adx'][i]),adx_slope=float(f['adx_slope'][i]),
                        di_plus=float(f['di_plus'][i]),di_minus=float(f['di_minus'][i]),fe=float(f['fe'][i]),
                        d1_ao=float(f['d1_ao'][i]),h4_ao=float(f['h4_ao'][i]),
                        h4_available_at=int(f['h4_available_at'][i]),d1_available_at=int(f['d1_available_at'][i]),
                        support=float(f['pivot_support'][i]) if np.isfinite(f['pivot_support'][i]) else None,
                        resistance=float(f['pivot_resistance'][i]) if np.isfinite(f['pivot_resistance'][i]) else None,mlrsi='UNAVAILABLE'))
                outcomes[(i,exit_kind)]=(trade,gate)
                if i in matched:
                    j,random_side=matched[i];control,reason=simulate(base,funding,d,j,random_side,exit_kind)
                    if control:
                        control.update(anchor_id=anchor,signal_time=int(d['available_at'][j]))
                        reference[(anchor,exit_kind)]=control
        quality[family]['excluded']=dict(excluded)
        for exit_kind in EXITS if interval==market.HOUR else EXITS[:1]:
            cohorts={v:[dict(t,variant=v) for (i,e),(t,g) in outcomes.items() if e==exit_kind and g[v]] for v in VARIANTS}
            refs={anchor:c for (anchor,e),c in reference.items() if e==exit_kind}
            for variant,rows in cohorts.items():
                key=f'{interval//market.M5*5}m:{family}:{variant}:{exit_kind}'
                groups={s:[r for r in rows if r['split']==s] for s in ('DEVELOPMENT','VALIDATION','REUSED_EVALUATION')}
                evaluation=groups['REUSED_EVALUATION'];stats={s:summarize(rs) for s,rs in groups.items()}
                costs={s:summarize(evaluation,s) for s in COSTS}
                annual={str(y):summarize([r for r in rows if r['year']==y],bootstrap=False) for y in range(2020,2027)}
                pc=paired(evaluation,{a:c for a,c in refs.items() if split(c['signal_time'])=='REUSED_EVALUATION'})
                parent='AO_CONTEXT' if variant in ('AO_DMI','AO_FE') else 'AO_DMI' if variant=='AO_DMI_FE' else 'AO_ONLY'
                full_parent=[r for r in cohorts[parent] if r['split']=='REUSED_EVALUATION']
                incremental=incremental_stats(evaluation,full_parent,parent)
                label=classify(stats['REUSED_EVALUATION'],costs['CONSERVATIVE'],stats['VALIDATION'],pc,
                    {y:s for y,s in annual.items() if int(y)>=2024},incremental)
                extra={}
                if variant=='AO_DMI_FE':
                    extra['versus_FE']=incremental_stats(evaluation,[r for r in cohorts['AO_FE'] if r['split']=='REUSED_EVALUATION'],'AO_FE')
                out[key]=dict(timeframe=rows[0]['timeframe'] if rows else ('1H' if interval==market.HOUR else '15m'),family=family,variant=variant,exit_kind=exit_kind,
                    classification=label,splits=stats,costs=costs,annual=annual,matched_control=pc,incremental=incremental,**extra,
                    side={str(s):summarize([r for r in evaluation if r['side']==s]) for s in (1,-1)},
                    regime={str(s):summarize([r for r in evaluation if r['regime']==s],bootstrap=False) for s in (-1,0,1)},
                    attrition=dict(anchors=len(events),trades=len(rows),filtered_or_invalid=len(events)-len(rows)))
                all_rows.extend(rows)
    return out,all_rows,quality

def freeze(cache):
    if (ART/'protocol_lock.json').exists():raise ValueError('PROTOCOL_ALREADY_LOCKED')
    base,funding,manifest=market.load(cache)
    if base[0,0]!=market.START or base[-1,0]+market.M5!=market.END:raise ValueError('DATA_COVERAGE')
    ART.mkdir(parents=True,exist_ok=True);write(ART/'data_manifest.json',manifest)
    write(ART/'protocol_lock.json',dict(version='BITMAN_ENTRY_RESEARCH_V0',base=BASE,
        specification_commit=subprocess.check_output(['git','log','-1','--format=%H','--','research/bitman_entry_lab/specification.md'],cwd=ROOT).decode().strip(),
        locked_at=datetime.now(timezone.utc).isoformat(),code=hashes(),manifest_sha256=market.sha((ART/'data_manifest.json').read_bytes()),
        no_virgin_holdout=True,hypothesis_families=3,primary_comparisons=30,secondary_comparisons=5))
    print('ENTRY_V0_PROTOCOL_LOCKED_NO_OUTCOMES_COMPUTED')

def run(cache):
    lock=json.loads((ART/'protocol_lock.json').read_text('utf-8'))
    if lock['code']!=hashes():raise ValueError('LOCKED_RESEARCH_CHANGED')
    if market.sha((ART/'data_manifest.json').read_bytes())!=lock['manifest_sha256']:raise ValueError('MANIFEST_CHANGED')
    base,funding,manifest=market.load(cache)
    if manifest!=json.loads((ART/'data_manifest.json').read_text('utf-8')):raise ValueError('DATA_CHANGED')
    one,rows,quality=run_dataset(base,funding,market.HOUR,('A','B','C'))
    secondary,extra,q15=run_dataset(base,funding,3*market.M5,('B',));rows+=extra
    results=dict(version=lock['version'],protocol_lock_sha256=market.sha((ART/'protocol_lock.json').read_bytes()),
        candidates={**one,**secondary},quality_1H=quality,quality_15m=q15,
        classification_counts=dict(Counter(x['classification'] for x in [*one.values(),*secondary.values()])),
        historical_only=True,no_virgin_holdout=True,trade_authority='NONE')
    write(ART/'results.json',results)
    raw=''.join(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for r in rows).encode()
    (ART/'simulated_trades.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    report(results,rows,manifest,PACKAGE/'BITMAN_ENTRY_RESEARCH_V0.md')
    print(json.dumps(dict(candidates=len(results['candidates']),classifications=results['classification_counts'],trades=len(rows),
        results_sha256=market.sha((ART/'results.json').read_bytes()))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','run'));p.add_argument('--cache',required=True)
    a=p.parse_args()
    if a.command=='freeze':freeze(a.cache)
    else:run(a.cache)
