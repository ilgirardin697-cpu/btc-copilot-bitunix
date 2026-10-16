"""Frozen directional evaluation. No parameter ranking or executable trade model."""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from research.bitman_real.market import verified_cache,ROOT
from research.bitman_real.indicators import roll
from . import core,evaluation as ev,noise
from .spec import (BASE_SHA,VERSION,CUTOFF,HOUR,TIMEFRAMES,HORIZONS,PRIMARY_HORIZON,FROZEN_FILES,protocol)

ART=Path(__file__).parent/'artifacts'
STATES=('UP','DOWN','TRANSITION','UNCLEAR','CONFLICT')


def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)
SPLITS={'TRAIN':(stamp('2020-01-01T00:00:00Z'),stamp('2022-01-01T00:00:00Z')),
    'VALIDATION':(stamp('2022-01-01T00:00:00Z'),stamp('2024-01-01T00:00:00Z')),
    'TEST':(stamp('2024-01-01T00:00:00Z'),stamp(CUTOFF))}


def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def code_hash():return hashlib.sha256(b''.join((Path(__file__).parent/p).read_bytes().replace(b'\r\n',b'\n') for p in FROZEN_FILES)).hexdigest()


def calibrate(data,start,end):
    ratio=data['aligned']['1H']['atr']/data['bars'][:,4];mask=(data['times']>=start)&(data['times']<end)&np.isfinite(ratio)
    if mask.sum()<100:raise ValueError('MATCH_CALIBRATION_INSUFFICIENT')
    return np.quantile(ratio[mask],[.25,.5,.75]).tolist()


def freeze():
    ART.mkdir(exist_ok=True)
    if (ART/'protocol.json').exists():raise ValueError('PROTOCOL_ALREADY_FROZEN')
    bars,manifest=verified_cache();write(ART/'data_manifest.json',manifest)
    dev=bars[bars[:,0]+HOUR<SPLITS['TRAIN'][1]]
    data=core.prepare(dev,SPLITS['TRAIN'][1]);vol=calibrate(data,*SPLITS['TRAIN'])
    write(ART/'calibration_lock.json',dict(matching_volatility_quartiles=vol,source='TRAIN_ONLY',
        end=SPLITS['TRAIN'][1],purpose='Evaluation controls only; never engine decisions',no_parameter_selection=True))
    write(ART/'protocol.json',dict(protocol=protocol(),code_sha256=code_hash(),data_manifest_sha256=sha(ART/'data_manifest.json'),
        calibration_sha256=sha(ART/'calibration_lock.json'),primary_sources_sha256=sha(ROOT/'research/bitman_phase4/artifacts/primary_sources.json'),
        frozen_at=datetime.now(timezone.utc).isoformat()))
    print('DIRECTION_PROTOCOL_FROZEN',code_hash(),flush=True)


def check():
    p=json.loads((ART/'protocol.json').read_text(encoding='utf-8'))
    if p['code_sha256']!=code_hash() or p['data_manifest_sha256']!=sha(ART/'data_manifest.json') or p['calibration_sha256']!=sha(ART/'calibration_lock.json'):
        raise ValueError('FROZEN_INPUT_CHANGED')
    if p['protocol']!=json.loads(json.dumps(protocol())):raise ValueError('PROTOCOL_CHANGED')
    if p['primary_sources_sha256']!=sha(ROOT/'research/bitman_phase4/artifacts/primary_sources.json'):raise ValueError('PRIMARY_PROVENANCE_CHANGED')


def mapped_tf_episodes(data,tf):
    f=data['frames'][tf];bias=f['features']['bias'];state=np.where(np.isin(bias,['UP','DOWN','TRANSITION']),bias,'UNCLEAR')
    lean=np.where(f['features']['momentum']=='BULLISH_MOMENTUM',1,np.where(f['features']['momentum']=='BEARISH_MOMENTUM',-1,0))
    rows=ev.episodes(state,f['closes'],f['frame'][:,4],lean,tf)
    for r in rows:r['index']=int(np.searchsorted(data['times'],r['timestamp']))
    return rows


def grouped(rows,horizons):return {s:ev.group_summary([r for r in rows if r['state']==s],horizons) for s in STATES}


def cohort_filters(data,r):
    i=r['index'];a=data['aligned']['4H'];side=r['direction']
    adx=bool(a['adx_slope'][i]>0);bbwp=bool(a['bbwp_slope'][i]>0)
    k=a['konkorde'][i]
    kon=bool(k in ('KONKORDE_BULLISH_ENTRY_CONTEXT','KONKORDE_BULLISH_INSIDE','KONKORDE_REENTRY')) if side==1 else bool(k in ('KONKORDE_EXIT_CONTEXT','KONKORDE_BEARISH_CONTEXT'))
    tested=False
    for tf in ('4H','1D'):
        if not i:continue
        value=data['levels'][tf]['resistance' if side==1 else 'support'][i-1]
        if not np.isfinite(value):continue
        tested|=bool(data['bars'][i,2]>=value and data['bars'][i,4]<=value) if side==1 else bool(data['bars'][i,3]<=value and data['bars'][i,4]>=value)
    return dict(AO_DI=True,AO_DI_ADX=adx,AO_DI_ADX_BBWP=adx and bbwp,
        AO_DI_ADX_BBWP_KONKORDE=adx and bbwp and kon,
        AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML=adx and bbwp and kon and not tested)


def annotate(data,rows,series):
    for r in rows:
        i=r['index'];r['strength']=str(series['strength'][i]);r['detail']=str(series['detail'][i])
        r['macro_bias']=str(data['aligned']['1D']['bias'][i]);r['swing_bias']=str(data['aligned']['4H']['bias'][i])
        r['adx4h']=float(data['aligned']['4H']['adx'][i]) if np.isfinite(data['aligned']['4H']['adx'][i]) else None
        r['bbwp4h']=float(data['aligned']['4H']['bbwp'][i]) if np.isfinite(data['aligned']['4H']['bbwp'][i]) else None
        r['konkorde4h']=str(data['aligned']['4H']['konkorde'][i])
        r['mlrsi_confirmed']='PENDING_ACTUAL_CONFIRMED_EXPORT_NOT_RECONSTRUCTED'


def without_top3(rows,h):
    q=[r for r in rows if r['outcomes'][str(h)]['complete'] and r['outcomes'][str(h)]['signed_return'] is not None]
    kept=sorted(q,key=lambda r:r['outcomes'][str(h)]['signed_return'],reverse=True)[3:]
    excess=[r['paired_excess'][str(h)] for r in kept if r['paired_excess'][str(h)] is not None]
    return dict(n=len(kept),signed_mean=float(np.mean([r['outcomes'][str(h)]['signed_return'] for r in kept])) if kept else None,
        paired_mean=float(np.mean(excess)) if excess else None)


def evaluate(output_dir=None):
    check();out=Path(output_dir) if output_dir else ART;out.mkdir(exist_ok=True,parents=True)
    if (out/'results.json').exists():raise ValueError('RESULTS_ALREADY_EXIST')
    bars,_=verified_cache();data=core.prepare(bars,stamp(CUTOFF));public=core.series(data,True);base=core.series(data,False);ao=core.series(data,False,True)
    rows_by_stream={tf:mapped_tf_episodes(data,tf) for tf in TIMEFRAMES}
    for name,stream in (('MTF',public),('AO_DI',base),('AO_ONLY',ao)):
        rows_by_stream[name]=ev.episodes(stream['state'],data['times'],bars[:,4],stream['direction'],'MTF')
        annotate(data,rows_by_stream[name],stream)
    h4=data['frames']['4H']['frame'];sma=roll(h4[:,4],200)
    v8=core.align(h4[:,0],np.where(np.isfinite(sma),(h4[:,4]>sma).astype(float),np.nan),4*HOUR,data['times'])
    v8state=np.where(v8==1,'UP','UNCLEAR')
    rows_by_stream['V8']=ev.episodes(v8state,data['times'],bars[:,4],stream='MTF')
    lock=json.loads((ART/'calibration_lock.json').read_text());keys=ev.control_keys(data,lock['matching_volatility_quartiles'])
    result=dict(version=VERSION,source='HISTORICAL_DIRECTIONAL_SIMULATION_NOT_STRATEGY',code_sha256=code_hash(),
        protocol_sha256=sha(ART/'protocol.json'),calibration_sha256=sha(ART/'calibration_lock.json'),splits={},ablation={},yearly={},walk_forward={},
        mlrsi_ablation=dict(status='PENDING_ACTUAL_CONFIRMED_EXPORT',computed=False,rows=0,unsupported_1d=True,
            reason='No actual journals accessible; no recomputation/substitution of production ML RSI'),
        forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',trade_authority=False)
    evaluated={};all_rows=[]
    for name,rows in rows_by_stream.items():
        horizons=HORIZONS.get(name,HORIZONS['MTF']);interval=TIMEFRAMES.get(name,HOUR)
        result['splits'][name]={};evaluated[name]={}
        for period,(start,end) in SPLITS.items():
            q=ev.evaluate_rows(rows,data,horizons,start,end,keys,interval);evaluated[name][period]=q
            result['splits'][name][period]=grouped(q,horizons)
            all_rows.extend(dict(r,stream=name,period=period) for r in q)
        print('DIRECTION_STREAM_EVALUATED',name,flush=True)
    for period,q in evaluated['AO_DI'].items():
        result['ablation'][period]={}
        for stage in ('AO_DI','AO_DI_ADX','AO_DI_ADX_BBWP','AO_DI_ADX_BBWP_KONKORDE','AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML'):
            selected=[r for r in q if r['state'] in ('UP','DOWN') and cohort_filters(data,r)[stage]]
            result['ablation'][period][stage]=grouped(selected,HORIZONS['MTF'])
    for year in range(2020,2027):
        start=stamp(f'{year}-01-01T00:00:00Z');end=min(stamp(f'{year+1}-01-01T00:00:00Z'),stamp(CUTOFF))
        q=ev.evaluate_rows(rows_by_stream['MTF'],data,HORIZONS['MTF'],start,end,keys)
        result['yearly'][str(year)]=grouped(q,HORIZONS['MTF'])
        if year>=2022:
            cut=calibrate(data,SPLITS['TRAIN'][0],start);past_keys=ev.control_keys(data,cut)
            trial=ev.evaluate_rows(rows_by_stream['MTF'],data,HORIZONS['MTF'],start,end,past_keys)
            result['walk_forward'][str(year)]=dict(last_calibration_data_before=start,vol_cutpoints=cut,parameter_selection=False,
                states=grouped(trial,HORIZONS['MTF']))
    result['structure_context']={}
    for state in STATES:
        q=[r for r in evaluated['MTF']['TEST'] if r['state']==state]
        distances=[]
        for r in q:
            s=core.snapshot(data,r['index'])['structure']
            distances.append(dict(timestamp=r['timestamp'],support=s['nearest_support'],resistance=s['nearest_resistance'],
                support_distance_pct=s['support_distance_pct'],resistance_distance_pct=s['resistance_distance_pct'],
                support_distance_atr=s['support_distance_atr'],resistance_distance_atr=s['resistance_distance_atr'],context=s['state']))
        result['structure_context'][state]=distances
    start,end=SPLITS['TEST'];mask=(data['times']>=start)&(data['times']<end)
    engine_up=[r for r in evaluated['MTF']['TEST'] if r['state']=='UP'];v8up=[r for r in evaluated['V8']['TEST'] if r['state']=='UP']
    result['noise']=dict(engine_frequency=noise.frequency(public['state'][mask],data['times'][mask]),
        engine_material_signature_frequency=noise.frequency(np.array(['|'.join(str(public[k][i]) for k in ('state','detail','strength','evidence_grade')) for i in np.flatnonzero(mask)]),data['times'][mask]),
        v8_frequency=noise.frequency(v8state[mask],data['times'][mask]),engine_v8_up=noise.compare(engine_up,v8up),
        engine_up_while_v8_long_fraction=float(np.mean(v8[mask][public['state'][mask]=='UP']==1)) if np.any(public['state'][mask]=='UP') else None,
        actual_delivered_alerts='PENDING_REAL_JOURNALS',mlrsi_increment='PENDING_REAL_CONFIRMED_JOURNALS')
    result['cohorts']={}
    for tag in ('UP_CONFIRMED','UP_WITH_1H_PULLBACK','DOWN_CONFIRMED','DOWN_WITH_1H_PULLBACK','POSSIBLE_BULLISH_TRANSITION','POSSIBLE_BEARISH_TRANSITION'):
        # Onset cohorts only. Timing changes within an ongoing direction do not manufacture new episodes.
        q=[r for r in evaluated['MTF']['TEST'] if r['detail']==tag];result['cohorts'][tag]=ev.group_summary(q,HORIZONS['MTF'])
    for strength in ('WEAK','BUILDING','STRONG'):
        result['cohorts'][strength]={state:ev.group_summary([r for r in evaluated['MTF']['TEST'] if r['strength']==strength and r['state']==state],HORIZONS['MTF']) for state in ('UP','DOWN')}
    result['gates']={};result['without_top3']={}
    for state in ('UP','DOWN'):
        q=[r for r in evaluated['MTF']['TEST'] if r['state']==state];s=result['splits']['MTF']['TEST'][state];m=s['matched']['72'];h=s['horizons']['72']
        removed=without_top3(q,72);result['without_top3'][state]=removed
        result['gates'][state]=dict(sample_at_least50=h['n_directional']>=50,
            signed_mean_positive=h.get('signed_return',{}).get('mean',-1)>0,paired_excess_positive=(m['mean'] or -1)>0,
            ci_lower_positive=m['ci95'][0] is not None and m['ci95'][0]>0,
            positive_test_years_at_least2=sum(result['yearly'][str(y)][state]['horizons']['72'].get('signed_return',{}).get('mean',-1)>0 for y in (2024,2025,2026))>=2,
            positive_walkforward_years_at_least3=sum(result['walk_forward'][str(y)]['states'][state]['horizons']['72'].get('signed_return',{}).get('mean',-1)>0 for y in range(2022,2027))>=3,
            without_top3_positive=removed['signed_mean'] is not None and removed['signed_mean']>0 and removed['paired_mean'] is not None and removed['paired_mean']>0,
            actual_confirmed_ml_evaluation=False)
    useful=all(all(g.values()) for g in result['gates'].values())
    negative=all(g['sample_at_least50'] and not g['signed_mean_positive'] and not g['paired_excess_positive'] for g in result['gates'].values())
    result['classification']='USEFUL DIRECTION ENGINE' if useful else 'NO DIRECTIONAL VALUE' if negative else 'INCONCLUSIVE DIRECTION ENGINE'
    result['latest_public_snapshot']=core.snapshot(data,len(data['times'])-1)
    with gzip.open(out/'episodes_and_outcomes.jsonl.gz','wt',encoding='utf-8') as stream:
        for r in all_rows:stream.write(json.dumps(r,allow_nan=False)+'\n')
    write(out/'results.json',result);print('DIRECTION_CLASSIFICATION',result['classification'],flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('freeze','evaluate'));p.add_argument('--output-dir')
    args=p.parse_args();freeze() if args.phase=='freeze' else evaluate(args.output_dir)
