"""Separated development/freeze and TEST processes; no TEST reranking."""
import argparse
import gzip
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from . import core, engine, mlrsi
from .data import ART, CACHE, HOUR, ROOT, load, stamp, digest
from .spec import (BASE_SHA,CUTOFF,FROZEN_FILES,START,TEST_START,TRAIN_END,Candidate,
                   candidates,neighbors,FUSIONS,protocol)

SPLITS=dict(TRAIN=(stamp(START),stamp(TRAIN_END)),VALIDATION=(stamp(TRAIN_END),stamp(TEST_START)),
            TEST=(stamp(TEST_START),stamp(CUTOFF)),ALL=(stamp(START),stamp(CUTOFF)))


def save(name,value):
    (ART/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def code_hash():
    return hashlib.sha256(b''.join((Path(__file__).parent/f).read_bytes().replace(b'\r\n',b'\n') for f in FROZEN_FILES)).hexdigest()


def check_protocol():
    expected=json.dumps(protocol(),sort_keys=True)
    actual=json.dumps(json.loads((ART/'preregistered.json').read_text()),sort_keys=True)
    if expected!=actual: raise ValueError('PREDECLARED_PROTOCOL_CHANGED')


def get_features(bars,base,p,cache):
    return core.candidate_features(bars,base,p,cache)


def run_candidate(bars,base,cache,p,side,funding,start,end,costs=None):
    f=get_features(bars,base,p,cache); entry,opposite,_=core.signals(f,p,side)
    return engine.simulate(bars,f,entry,opposite,funding,p,side,start,end,costs)


def development(bars,base,cache,p,side,funding,periods=None):
    periods=periods or {k:SPLITS[k] for k in ('TRAIN','VALIDATION')}
    result={name:run_candidate(bars,base,cache,p,side,funding,a,b)['metrics'] for name,(a,b) in periods.items()}
    return dict(parameters=asdict(p),**result)


def eligibility(result):
    return all(result[k]['trades']>=30 and result[k]['expectancy']>0 for k in ('TRAIN','VALIDATION'))


def score(result):
    return min(result[k]['sharpe'] for k in ('TRAIN','VALIDATION'))-1.5*max(abs(result[k]['max_dd']) for k in ('TRAIN','VALIDATION'))


def select_classic(bars,base,cache,funding,side,periods=None,parents=None):
    parents=parents or candidates()
    rows=[development(bars,base,cache,p,side,funding,periods) for p in parents]
    eligible=[r for r in rows if eligibility(r)]
    ranking=sorted(eligible or rows,key=lambda r:(-score(r),r['parameters']['name']))[:3]
    diagnostics=[]
    for parent in ranking:
        p=Candidate(**{**parent['parameters'],'fusion':tuple(parent['parameters']['fusion']),'disabled':tuple(parent['parameters']['disabled'])})
        adjacent=[development(bars,base,cache,q,side,funding,periods) for q in neighbors(p)]
        scores=[score(r) if eligibility(r) else -100. for r in [parent,*adjacent]]
        diagnostics.append(dict(parent=parent,neighbors=adjacent,
            robust_score_q25=float(np.quantile(scores,.25)),eligible=eligibility(parent)))
    chosen=sorted(diagnostics,key=lambda r:(-r['robust_score_q25'],-score(r['parent']),r['parent']['parameters']['name']))[0]
    return dict(selected=chosen['parent']['parameters'],eligible=bool(eligible),candidate_rows=rows,
                top3_neighbor_diagnostics=diagnostics,selection_periods=periods or {k:SPLITS[k] for k in ('TRAIN','VALIDATION')})


def make_candidate(value):
    return Candidate(**{**value,'fusion':tuple(value.get('fusion',())),'disabled':tuple(value.get('disabled',()))})


def develop():
    check_protocol()
    if (ART/'selection_lock.json').exists(): raise ValueError('SELECTION_ALREADY_FROZEN')
    # Actual arrays are physically cut before indicators or any ranking.
    bars,funding=load(stamp(TEST_START)); base=core.base_features(bars); cache={}
    classic={str(s):select_classic(bars,base,cache,funding,s) for s in (1,-1)}
    lock=dict(phase='CLASSIC_FROZEN_BEFORE_FUSION',code_sha256=code_hash(),
              protocol_sha256=digest(ART/'preregistered.json'),data_sha256=json.loads((ART/'data_manifest.json').read_text())[-1]['dataset_sha256'],
              development_last_closed=int(bars[-1,0]+HOUR),audit_base=BASE_SHA,classic=classic,
              created_at=datetime.now(timezone.utc).isoformat())
    save('classic_lock.json',lock)
    print('BITMAN_CLASSIC_FROZEN', {s:r['selected']['name'] for s,r in classic.items()},flush=True)
    base.update(mlrsi.features(bars)); fusion={}
    for side in (1,-1):
        parent=make_candidate(classic[str(side)]['selected'])
        configs=[replace(parent,name=f'F{i:02}_'+('_'.join(features) or 'CLASSIC'),fusion=features) for i,features in enumerate(FUSIONS)]
        rows=[development(bars,base,cache,p,side,funding) for p in configs]
        eligible=[r for r in rows if eligibility(r)]
        chosen=sorted(eligible or rows,key=lambda r:(-score(r),len(r['parameters']['fusion']),r['parameters']['name']))[0]
        fusion[str(side)]=dict(selected=chosen['parameters'],eligible=bool(eligible),candidate_rows=rows)
    lock.update(phase='CLASSIC_AND_FUSION_FROZEN',fusion=fusion,
                frozen_at=datetime.now(timezone.utc).isoformat())
    save('selection_lock.json',lock)
    print('BITMAN_FUSION_FROZEN',{s:r['selected']['name'] for s,r in fusion.items()},flush=True)


def diagnostics(bars,base,cache,p,side,funding,result):
    a,b=SPLITS['TEST']
    neighbor_rows=[]
    for q in neighbors(p):
        neighbor_rows.append(dict(parameters=asdict(q),metrics=run_candidate(bars,base,cache,q,side,funding,a,b)['metrics']))
    ablation={}
    for block in ('TREND','RSI_CLOUD','MOMENTUM','DMI','STRUCTURE','VOLATILITY'):
        q=replace(p,disabled=(block,))
        ablation[block]=run_candidate(bars,base,cache,q,side,funding,a,b)['metrics']
    for feature in p.fusion:
        q=replace(p,fusion=tuple(f for f in p.fusion if f!=feature))
        ablation['FUSION_'+feature]=run_candidate(bars,base,cache,q,side,funding,a,b)['metrics']
    yearly={str(y):run_candidate(bars,base,cache,p,side,funding,max(a,stamp(f'{y}-01-01T00:00:00Z')),
                min(b,stamp(f'{y+1}-01-01T00:00:00Z')))['metrics'] for y in (2024,2025,2026)}
    high_cut=float(np.nanmedian(base['atr_pct'][(bars[:,0]>=SPLITS['TRAIN'][0])&(bars[:,0]<SPLITS['TRAIN'][1])]))
    masks=dict(BULL=(bars[:,4]>base['sma4'])&(base['adx']>=20),BEAR=(bars[:,4]<base['sma4'])&(base['adx']>=20),
               RANGE=base['adx']<20,HIGH_VOL=base['atr_pct']>=high_cut,LOW_VOL=base['atr_pct']<high_cut)
    cohorts={}
    for name,mask in masks.items():
        rows=[t for t in result['trades'] if mask[max(0,np.searchsorted(bars[:,0],t['signal_time'])-1)]]
        values=np.array([t['net_return'] for t in rows]); losses=values[values<0]
        cohorts[name]=dict(n=len(rows),expectancy=float(values.mean()) if len(values) else None,
            profit_factor=float(values[values>0].sum()/-losses.sum()) if len(losses) else None,
            caveat='Descriptive trade-entry cohort, not compressed-time Sharpe/tradable equity.')
    stressed=run_candidate(bars,base,cache,p,side,funding,a,b,dict(fee_bps=6,slip_bps=5,stop_slip_bps=10))
    fees={str(n):run_candidate(bars,base,cache,p,side,funding,a,b,
          dict(fee_bps=n,slip_bps=2,stop_slip_bps=5))['metrics'] for n in (5,10,20)}
    return dict(neighbors=neighbor_rows,ablation=ablation,yearly=yearly,cohorts=cohorts,
        volatility_cutpoint_TRAIN=high_cut,stress=stressed['metrics'],fee_sensitivity=fees,
        without_best=engine.removal(result,1),without_best3=engine.removal(result,3),
        bootstrap=engine.bootstrap(result))


def gates(metrics,diag,eligible):
    adjacent=diag['neighbors']; fraction=sum(r['metrics']['expectancy']>0 for r in adjacent)/len(adjacent)
    return dict(development_eligible=eligible,positive_expectancy=metrics['expectancy']>0,
        pf_gt_1_20=(metrics['profit_factor'] or 0)>1.2,sharpe_gt_0_75=metrics['sharpe']>.75,
        maxdd_lt_20pct=metrics['max_dd']>-.20,sample_at_least100=metrics['trades']>=100,
        positive_neighbors_at_least80pct=fraction>=.8,stress_positive=diag['stress']['expectancy']>0,
        without_best3_positive=diag['without_best3']['expectancy']>0)


def classify(metrics,checks):
    if all(checks.values()): return 'PROMISING'
    if metrics['expectancy']<=0 or not checks['development_eligible']: return 'REJECT'
    if metrics['trades']<100: return 'INCONCLUSIVE'
    return 'REJECT'


def benchmarks(bars,base,funding):
    c=bars[:,4]; dummy=Candidate(name='control')
    # D60 preserves its frozen definition, not a renewed threshold search.
    # Historical code uses Wilder alpha1/14 then EMA alpha2/6.
    gain=core.ema(np.maximum(np.r_[0.,np.diff(c)],0),27)
    loss=core.ema(np.maximum(-np.r_[0.,np.diff(c)],0),27)
    rr=np.divide(100*gain,gain+loss,out=np.full(len(c),50.),where=gain+loss>0)
    state=core.ema(rr,5)
    sma1=core.mean(c,200)
    ema_trend=core.ema(c,10)>core.ema(c,55)
    definitions=dict(V8=c>base['sma4'],CONFLUENCE_D60=(c>sma1)&(base['flow']>=.6)&(state>55),
                     EMA_10_55=ema_trend,BUY_HOLD=np.ones(len(c),bool),MLRSI_STATE=base['ml_state']==1)
    results={}
    for name,entry in definitions.items():
        opposite=~entry if name!='CONFLUENCE_D60' else ((c<=sma1)|(state<45))
        if name=='MLRSI_STATE': opposite=base['ml_state']==-1
        results[name]={}
        for split,(a,b) in SPLITS.items():
            result=engine.simulate(bars,base,entry,opposite,funding,dummy,1,a,b,benchmark=True)
            results[name][split]=result['metrics']
    # Same price path/quantity conventions, underlying control without funding.
    results['BUY_HOLD_NO_FUNDING']={split:engine.simulate(bars,base,definitions['BUY_HOLD'],
        np.zeros(len(c),bool),np.empty((0,2)),dummy,1,a,b,benchmark=True)['metrics'] for split,(a,b) in SPLITS.items()}
    return results


def regime_analysis(bars,base):
    close=bars[:,4]; change=np.diff(np.log(close),prepend=np.nan)
    signed=np.sign(change); sma_sign=np.sign(close-base['sma4'])
    result={}
    for y in range(2020,2027):
        mask=np.array([datetime.fromtimestamp(t/1000,timezone.utc).year==y for t in bars[:,0]])
        future=np.r_[close[1:],np.nan]/close-1
        ids=np.flatnonzero(mask); same=ids[ids+3<len(close)]
        same=same[mask[np.minimum(same+3,len(mask)-1)]]
        bl=base['break_long'][same]; bs=base['break_short'][same]
        failures=[]
        for k,up,down in zip(same,bl,bs):
            if up: failures.append(bool(np.any(close[k+1:k+4]<=base['swing_high'][max(0,k-1)])))
            if down: failures.append(bool(np.any(close[k+1:k+4]>=base['swing_low'][max(0,k-1)])))
        corr_mask=mask&np.r_[mask[1:],False]&np.isfinite(change)&np.isfinite(future)
        result[str(y)]=dict(hours=int(mask.sum()),median_atr_pct=float(np.nanmedian(base['atr_pct'][mask])),
            median_adx=float(np.nanmedian(base['adx'][mask])),fraction_adx_rising=float(np.mean(base['adx_slope'][mask]>0)),
            median_taker_buy=float(np.median(base['flow'][mask])),
            fraction_taker_ge60=float(np.mean(base['flow'][mask]>=.6)),
            sign_persistence=float(np.mean(signed[ids[1:]]==signed[ids[1:]-1])),
            lag1_return_correlation=float(np.corrcoef(change[corr_mask],future[corr_mask])[0,1]),
            regime_changes=int(np.count_nonzero(np.diff(sma_sign[mask]))),
            false_breakout_3h=float(np.mean(failures)) if failures else None,breakout_n=len(failures),
            median_cloud_rsi=float(np.nanmedian(core.rsi(close,89)[mask])),
            fraction_bbwp_expansion=float(np.mean(base['bbwp_expansion'][mask])))
    return result


def walk_forward(bars,funding):
    result={}
    for year in range(2022,2027):
        limit=min(stamp(f'{year+1}-01-01T00:00:00Z'),stamp(CUTOFF))
        sample=bars[bars[:,0]+HOUR<=limit]; base=core.base_features(sample); cache={}
        train_sample=sample[sample[:,0]+HOUR<=stamp(f'{year}-01-01T00:00:00Z')]
        train_base=core.base_features(train_sample); train_cache={}
        train_funding=funding[funding[:,0]<stamp(f'{year}-01-01T00:00:00Z')]
        periods=dict(TRAIN=(stamp(START),stamp(f'{year-1}-01-01T00:00:00Z')),
                     VALIDATION=(stamp(f'{year-1}-01-01T00:00:00Z'),stamp(f'{year}-01-01T00:00:00Z')))
        result[str(year)]={}
        for side in (1,-1):
            selection=select_classic(train_sample,train_base,train_cache,train_funding,side,periods)
            p=make_candidate(selection['selected'])
            metrics=run_candidate(sample,base,cache,p,side,funding,stamp(f'{year}-01-01T00:00:00Z'),limit)['metrics']
            result[str(year)][str(side)]=dict(selected=asdict(p),eligible=selection['eligible'],metrics=metrics,
                selection_cutoff=periods['VALIDATION'][1])
        print('BITMAN_ANNUAL_WALK_FORWARD',year,flush=True)
    return result


def evaluate():
    check_protocol(); lock=json.loads((ART/'selection_lock.json').read_text())
    if code_hash()!=lock['code_sha256'] or digest(ART/'preregistered.json')!=lock['protocol_sha256']:
        raise ValueError('FROZEN_IMPLEMENTATION_CHANGED')
    if json.loads((ART/'data_manifest.json').read_text())[-1]['dataset_sha256']!=lock['data_sha256']:
        raise ValueError('FROZEN_DATASET_CHANGED')
    if (ART/'test_results.json').exists(): raise ValueError('TEST_ALREADY_EVALUATED_USE_FROZEN_ARTIFACT')
    bars,funding=load(); base=core.base_features(bars); base.update(mlrsi.features(bars)); cache={}
    results=dict(source='HISTORICAL_BACKTEST',forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
                 audit_base=BASE_SHA,selection_sha256=digest(ART/'selection_lock.json'),cutoff=CUTOFF,
                 configurations={},comparators=benchmarks(bars,base,funding),regime=regime_analysis(bars,base))
    for family in ('classic','fusion'):
        for side in (1,-1):
            chosen=lock[family][str(side)]; p=make_candidate(chosen['selected']); key=f'{family}_{side}'
            periods={split:run_candidate(bars,base,cache,p,side,funding,a,b) for split,(a,b) in SPLITS.items()}
            diag=diagnostics(bars,base,cache,p,side,funding,periods['TEST'])
            checks=gates(periods['TEST']['metrics'],diag,chosen['eligible'])
            results['configurations'][key]=dict(parameters=asdict(p),splits={k:v['metrics'] for k,v in periods.items()},
                diagnostics=diag,gates=checks,classification=classify(periods['TEST']['metrics'],checks))
            with gzip.open(ART/(key+'_trades.jsonl.gz'),'wt',encoding='utf-8') as stream:
                for trade in periods['ALL']['trades']: stream.write(json.dumps(trade)+'\n')
            print('BITMAN_FROZEN_TEST',key,results['configurations'][key]['classification'],flush=True)
        plans={s:make_candidate(lock[family][str(s)]['selected']) for s in (1,-1)}
        entries,opposite={},{}
        for s,p in plans.items(): entries[s],opposite[s],_=core.signals(get_features(bars,base,p,cache),p,s)
        results[family+'_combined']={split:engine.simulate(bars,base,entries,opposite,funding,plans,0,a,b)['metrics'] for split,(a,b) in SPLITS.items()}
    # All FUSION ablations stay frozen; never choose a new family from these TEST rows.
    results['fusion_ablation']={}
    for side in (1,-1):
        parent=make_candidate(lock['classic'][str(side)]['selected']); rows={}
        for i,addition in enumerate(FUSIONS):
            p=replace(parent,name=f'F{i:02}',fusion=addition)
            rows['_'.join(addition) or 'CLASSIC']=run_candidate(bars,base,cache,p,side,funding,*SPLITS['TEST'])['metrics']
        results['fusion_ablation'][str(side)]=rows
    results['annual_walk_forward']=walk_forward(bars,funding)
    results['classification']='PROMISING' if any(r['classification']=='PROMISING' for r in results['configurations'].values()) else 'INCONCLUSIVE' if any(r['classification']=='INCONCLUSIVE' for r in results['configurations'].values()) else 'REJECT'
    save('test_results.json',results)
    print('BITMAN_STUDY_CLASSIFICATION',results['classification'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['develop','evaluate'])
    args=parser.parse_args(); develop() if args.phase=='develop' else evaluate()
