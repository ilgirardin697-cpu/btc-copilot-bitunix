"""Explicit offline research entrypoint. Reads local historical files only."""
from pathlib import Path
from datetime import datetime,timezone
from itertools import product
from collections import defaultdict
import argparse,csv,gzip,hashlib,json,time,sys
import numpy as np
from research.confluence_1h.indicators import calculate,roll
from research.confluence_1h_phase2.semantics import validate_bars
from .detector import HERE,features,detect,atomics,plan_hash
from .simulator import Config,Minutes,run,metrics,H

START=1667260800000;END=1793491200000
def iso(t):return datetime.fromtimestamp(int(t)/1000,timezone.utc).isoformat().replace('+00:00','Z')
def clean(x):
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    return x
def dump(path,value):path.write_text(json.dumps(clean(value),indent=2)+'\n',encoding='utf-8',newline='\n')
def checksum(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sourcehash(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def verify_seal():
    seal=json.loads((HERE/'seal.json').read_text());assert seal['plan_hash']==plan_hash()
    expected=dict(seal['sources']);amendment=HERE/'export_amendment.json'
    if amendment.exists():
        fix=json.loads(amendment.read_text());assert fix['source']=='study.py' and fix['previous_sha256']==expected['study.py'] and fix['before_trade_results'] is True
        expected['study.py']=fix['corrected_sha256'];seal=dict(seal,transparent_export_amendment=fix)
    for name,value in expected.items():assert sourcehash(HERE/name)==value,('SEALED_SOURCE_CHANGED',name)
    for name,value in seal['audited_sources'].items():assert sourcehash(HERE.parents[7]/name)==value,('AUDITED_FORMULA_CHANGED',name)
    return seal
def csvrow(row):return {k:json.dumps(clean(v),sort_keys=True) if isinstance(v,(dict,list)) else clean(v) for k,v in row.items()}
def write_csv(path,rows):
    rows=list(rows)
    if not rows:path.write_text('',newline='\n');return
    columns=list(dict.fromkeys(k for row in rows for k in row))
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader()
        for row in rows:w.writerow(csvrow(row))
def aggregate(a,size):
    offset=4*24*H if size==7*24*H else 0;ids=((a[:,0]-offset)//size).astype(int);out=[]
    for key in np.unique(ids):
        t=key*size+offset;b=a[ids==key]
        if len(b)==size//H and np.array_equal(b[:,0],t+np.arange(len(b))*H):out.append([t,b[0,1],b[:,2].max(),b[:,3].min(),b[-1,4],b[:,5].sum()])
    return np.asarray(out,float).reshape(-1,6)
def add_context(a,signals):
    for label,size in [('h4',4*H),('daily',24*H),('weekly',7*24*H)]:
        b=aggregate(a,size);f=calculate(b);price=b[:,4]-roll(b[:,4],200);closes=b[:,0]+size
        for s in signals:
            k=int(np.searchsorted(closes,s['available_at'],side='right')-1)
            s[label]={}
            if k<0:continue
            assert closes[k]<=s['available_at']
            s[label]['available_at']=int(closes[k])
            for name,key,warm in [('ao','ao',34),('adx','adx',28),('plus_di','plus_di',28),('minus_di','minus_di',28),('pececillos','minnows',90),('bbwp','bbwp',108)]:
                s[label][name]=float(f[key][k]) if k+1>=warm and np.isfinite(f[key][k]) else None
            s[label]['ao_slope']=float(f['ao'][k]-f['ao'][k-1]) if k>=34 and np.isfinite(f['ao'][k-1:k+1]).all() else None
            s[label]['price_regime']=int(np.sign(price[k])) if np.isfinite(price[k]) else None
def cells(a,f):
    out=[]
    for i,t in enumerate(a[:,0]+H):
        r=f['regime4h'][i];v=f['vol_rank'][i]
        out.append((iso(t)[:7],int(r) if np.isfinite(r) else None,min(2,int(v*3)) if np.isfinite(v) else None))
    return out
def reference(signals,universe,cell,seed):
    counts=defaultdict(int);pool=defaultdict(list);rng=np.random.default_rng(seed)
    for s in signals:counts[cell[s['i']],s['side']]+=1
    for i in universe:pool[cell[i]].append(int(i))
    result=[]
    for (key,side),n in sorted(counts.items(),key=lambda x:str(x[0])):
        if len(pool[key])<n:raise ValueError('REFERENCE_CELL_INSUFFICIENT')
        for i in rng.choice(pool[key],n,replace=False):result.append(dict(i=int(i),side=side,signal_id='REF:'+str(seed)+':'+str(i)+':'+str(side),regime4h=key[1]))
    return sorted(result,key=lambda x:(x['i'],x['side']))
def diagnostic(a,folder,out):
    path=folder/'diagnostic_H1.json'
    if not path.exists():return dict(available=False,reason='NO_PUBLIC_DIAGNOSTIC')
    raw=json.loads(path.read_text());b=np.array([[r[0],*map(float,r[1:6])] for r in raw],float)
    validate_bars(b);prefix=a[a[:,0]<b[0,0]];extended=validate_bars(np.r_[prefix,b]);f=features(extended);ss,trace=detect(extended,f,True);ev=atomics(f)
    from zoneinfo import ZoneInfo
    zone=ZoneInfo('Europe/Madrid');rows=[]
    for i in range(len(extended)):
        madrid=datetime.fromtimestamp((extended[i,0]+H)/1000,zone).isoformat()
        if not '2026-11-16T18'<=madrid<'2026-11-17T07':continue
        row=dict(open_utc=iso(extended[i,0]),available_utc=iso(extended[i,0]+H),open_madrid=datetime.fromtimestamp(extended[i,0]/1000,zone).isoformat(),available_madrid=madrid,close=float(extended[i,4]))
        for name,key in [('ao','ao'),('pece','minnows'),('adx','adx'),('bbwp','bbwp')]:row[name]=f[key][i];row[name+'_slope']=ev[name]['slope'][i];row[name+'_turn']=1 if ev[name]['up'][i] else -1 if ev[name]['down'][i] else 0
        row.update(plus_di=f['plus_di'][i],minus_di=f['minus_di'][i],red=f['kon_signal'][i],confluence_side=next((s['side'] for s in ss if s['i']==i),0));rows.append(row)
    write_csv(out/'diagnostic_20261116.csv',rows)
    overlap=a[np.isin(a[:,0],b[:,0])];matched=b[np.isin(b[:,0],a[:,0])]
    meta=dict(available=True,venue='BINANCE_USDM_PERPETUAL',reference_chart_ticker_unverified=True,visual_parity=False,already_selected_diagnostic=True,used_for_parameter_choice=False,
              raw_sha256=checksum(path),unchanged_overlap=bool(np.array_equal(overlap,matched)),signals_in_diagnostic_window=[s for s in ss if any(r['available_utc']==iso(s['available_at']) for r in rows)],
              interpretation='23Madrid may label bar open or close. Compare UTC21/22/23 and surrounding hours. No source-image/export available; do not claim exact visual parity.')
    dump(out/'diagnostic_provenance.json',meta);(out/'diagnostic_raw.json').write_bytes(path.read_bytes());(out/'diagnostic_receipt.json').write_bytes((folder/'diagnostic_receipt.json').read_bytes());return meta
def run_study(data,minutes_path,market_folder,out):
    out.mkdir(exist_ok=True,parents=True);seal=verify_seal();plan=json.loads((HERE/'plan.json').read_text());assert checksum(data)==plan['history']['data_sha256']
    with np.load(data,allow_pickle=False) as z:a=validate_bars(z['bars']);fund=z['funding'];marks=z['marks']
    with np.load(minutes_path,allow_pickle=False) as z:m=z['bars']
    minute_meta=json.loads((market_folder/'minute_manifest.json').read_text());assert checksum(minutes_path)==minute_meta['npz_sha256']
    tape=Minutes(m,a);f=features(a);signals,audit=detect(a,f,True);signals=[s for s in signals if START<=s['available_at']<END];add_context(a,signals)
    write_csv(out/'signals.csv',signals);write_csv(out/'detector_audit.csv.gz',audit);print('FROZEN_SIGNALS',len(signals),flush=True)
    diag=diagnostic(a,market_folder,out);cell=cells(a,f)
    eligible=np.flatnonzero((a[:,0]+H>=START)&(a[:,0]+H<END)&np.isfinite(f['atr'])&(f['atr']>0))
    references=[reference(signals,eligible,cell,plan['references']['first_seed']+k) for k in range(plan['references']['replicates'])]
    write_csv(out/'reference_schedules.csv.gz',(dict(seed=plan['references']['first_seed']+k,**s) for k,ss in enumerate(references) for s in ss))
    all_trades=[];fills=[];updates=[];opps=[];curves=[];summaries=[];subsets=[];refs=[];account_years=[];start=time.perf_counter()
    with gzip.open(out/'reference_trades.csv.gz','wt',encoding='utf-8',newline='') as control_file:
        cw=None
        for tp,stop,risk in product(plan['management']['tp1_price_fractions'],plan['management']['stop_atr_multipliers'],plan['management']['risk_equity_fractions']):
            cfg=Config(tp,stop,risk);actual=run(a,fund,f['atr'],signals,cfg,tape,marks)
            summaries.append(actual['summary']);print('ACTUAL',cfg.key,actual['summary']['n'],actual['summary']['expectancy_R'],flush=True)
            bysignal={s['signal_id']:s for s in signals}
            for t in actual['trades']:
                tr=dict(t);ff=tr.pop('fills');uu=tr.pop('stop_updates');tr['config']=cfg.key;all_trades.append(tr)
                fills.extend(dict(config=cfg.key,signal_id=t['signal_id'],**v) for v in ff);updates.extend(dict(config=cfg.key,signal_id=t['signal_id'],**v) for v in uu)
            opps.extend(dict(config=cfg.key,**v) for v in actual['opportunities']);curves.extend(dict(config=cfg.key,**v) for v in actual['equity'])
            groups=defaultdict(list)
            for t in actual['trades']:
                s=bysignal[t['signal_id']];groups['side',str(t['side'])].append(t);groups['year_entry',iso(t['entry_at'])[:4]].append(t)
                groups['regime4h',str(t['regime4h'])].append(t);groups['ADX_BBWP_phase',str(t['adx_phase'])+':'+str(t['bbwp_phase'])].append(t)
                for ctx in ('h4','daily','weekly'):groups[ctx+'_price_regime',str(s[ctx].get('price_regime'))].append(t)
            for (kind,label),tt in groups.items():subsets.append(dict(config=cfg.key,group=kind,value=label,**metrics(tt)))
            last=10000.
            for year in ('2022','2023','2024','2025','2026'):
                yy=[r['equity'] for r in actual['equity'] if iso(r['open_ms'])[:4]==year]
                if not yy:continue
                peak=last;dd=0.
                for v in yy:peak=max(peak,v);dd=max(dd,100*(peak-v)/peak)
                account_years.append(dict(config=cfg.key,year=year,equity_before=last,equity_end=yy[-1],return_pct=100*(yy[-1]/last-1),max_close_drawdown_pct=dd));last=yy[-1]
            for k,ss in enumerate(references):
                rr=run(a,fund,f['atr'],ss,cfg,tape,marks,False);refs.append(dict(seed=plan['references']['first_seed']+k,**rr['summary']))
                for trade in rr['trades']:
                    row=csvrow(dict(seed=plan['references']['first_seed']+k,config=cfg.key,**trade))
                    if cw is None:cw=csv.DictWriter(control_file,fieldnames=list(row),lineterminator='\n');cw.writeheader()
                    cw.writerow(row)
            print('REFERENCES_DONE',cfg.key,flush=True)
    write_csv(out/'summary.csv',summaries);write_csv(out/'trades.csv',all_trades);write_csv(out/'fills.csv',fills);write_csv(out/'stop_updates.csv',updates)
    write_csv(out/'opportunities.csv',opps);write_csv(out/'equity.csv.gz',curves);write_csv(out/'subgroups.csv',subsets);write_csv(out/'calendar_account.csv',account_years);write_csv(out/'references.csv',refs)
    comparisons=[]
    for actual in summaries:
        rr=[r for r in refs if r['config']==actual['config']];row=dict(config=actual['config'])
        for key in ('n','expectancy_R','net_expectancy','profit_factor','account_return_pct','max_close_drawdown_pct','exposure_hours'):
            vals=[r[key] for r in rr if r[key] is not None];row[key+'_actual']=actual[key]
            for q in (.05,.5,.95):row[key+'_reference_q'+str(int(q*100))]=float(np.quantile(vals,q)) if vals else None
        comparisons.append(row)
    write_csv(out/'comparisons.csv',comparisons)
    meta=dict(study=plan['study'],plan_hash=plan_hash(),seal=seal,venue='BINANCE_USDM_PERPETUAL',history_sha256=checksum(data),rows=len(a),study_hours=len(eligible),raw_signals=len(signals),long_signals=sum(s['side']==1 for s in signals),short_signals=sum(s['side']==-1 for s in signals),
              minute_rows=len(m),minute_npz_sha256=checksum(minutes_path),verified_minute_hours=len(tape.good),minute_requests_used=tape.calls,
              reference_replicates=100,configurations=12,prospective_observations=0,new_indicator_formulas=0,parameter_search=False,diagnostic=diag,
              seconds=time.perf_counter()-start,python=sys.version,numpy=np.__version__,conclusion='EXPLORATORY_NOT_VALIDATED',trade_authority='NONE')
    dump(out/'results.json',meta);dump(out/'minute_manifest.json',minute_meta);return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--minutes',type=Path,required=True);p.add_argument('--market-folder',type=Path,required=True);p.add_argument('--out',type=Path,default=HERE/'results');v=p.parse_args();print(json.dumps(clean(run_study(v.data,v.minutes,v.market_folder,v.out))))
