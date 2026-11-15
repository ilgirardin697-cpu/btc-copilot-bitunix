"""Frozen F4A offline evaluation; original engine/statistics, no parameter search."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import numpy as np

from research.confluence_1h.data import load, stamp, iso, HOUR
from research.confluence_1h.indicators import calculate, regime
from research.confluence_1h.engine import Assumptions, simulate, metrics
from research.confluence_1h.statistics import daily, ratio_ci, random_controls
from research.confluence_1h.diagnostics import gate_funnel
from research.confluence_1h_phase2.compare import load_market
from .variants import flags, VARIANTS

HERE=Path(__file__).resolve().parent
FREEZE='e626d46d278f115947a5ae69a2e8b6999401a272'


def jwrite(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def cwrite(path,rows,empty_fields=('status','reason')):
    fields=list(dict.fromkeys(k for row in rows for k in row)) if rows else list(empty_fields)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n');w.writeheader()
    for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
    raw=buf.getvalue().encode();path.write_bytes(gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw)


def windows(start,end):
    n=end-start;cut=start+int(.70*n)
    result={'FULL':(start,end),'DEVELOPMENT':(start,cut-24),'TEST':(cut+24,end)}
    edges=[start+int(n*p) for p in (.30,.40,.50,.60,.70)]
    for i in range(4):result['WF'+str(i+1)]=(edges[i]+24,edges[i+1]-24)
    return result


def exact_net(m):
    if not m['n']:return None
    return m['net_usdt'] if not m['funding_missing_marks_used'] and not m['funding_timing_ambiguities'] else None


def incident(out):
    result=[]
    for venue,name in [('BINANCE_SPOT','SPOT_H1_FOCUS'),('BINANCE_USDM_PERPETUAL','USDM_H1_FOCUS')]:
        folder=HERE.parent/'fixtures';meta=json.loads((folder/(name+'.json')).read_text())
        a=load_market(folder/(name+'.csv.gz'),meta);f=calculate(a)
        for variant in VARIANTS:
            sig=flags(f,variant);i=int(np.flatnonzero(a[:,0]==stamp('2026-11-15T03:00:00Z'))[0])
            side=1 if sig['long'][i] else -1 if sig['short'][i] else 0
            row=dict(venue=venue,variant=variant,signal_bar_open=iso(a[i,0]),available_at=iso(a[i,0]+HOUR),
                available_madrid='2026-11-15T05:00:00+01:00',long=bool(sig['long'][i]),short=bool(sig['short'][i]),
                main_series=float(f['kon_trend' if variant=='BASE' else 'minnows'][i]),
                previous_main=float(f['kon_trend' if variant=='BASE' else 'minnows'][i-1]),
                red_ema_tendencia=float(f['kon_signal'][i]),previous_red=float(f['kon_signal'][i-1]),
                adx_tminus1=float(f['adx'][i-1]),adx_tminus2=float(f['adx'][i-2]),
                ao_current=float(f['ao'][i]),ao_previous=float(f['ao'][i-1]),ao_tminus2=float(f['ao'][i-2]),
                bbwp=float(f['bbwp'][i]),atr=float(f['atr'][i]),
                gate_cross_and_sign=bool(sig['kon_long' if side>=0 else 'kon_short'][i]),
                gate_lagged_adx=bool(sig['adx_lagged_decline'][i]),
                gate_ao=bool(sig['ao_long' if side>=0 else 'ao_short'][i]),gate_bbwp=bool(sig['bbwp_above'][i]),
                first_next_open_time=iso(a[i+1,0]) if side else None,
                next_open_reference=float(a[i+1,1]) if side else None,
                model_entry_with_original_slip=float(a[i+1,1]*(1+side*.0005)) if side else None,
                fill_status='NEXT_OPEN_MODEL_REFERENCE_NOT_ATTESTED_LIVE_FILL' if side else 'NO_SIGNAL',
                held_out_validation=False,performance_scored=False,
                note='POST_HOC_ILLUSTRATION_OUTSIDE_2022_2026_EVALUATION; NO_SPOT_SHORT_OR_INCIDENT_PNL')
            result.append(row)
    jwrite(out/'november_incident.json',result)
    return result


def evaluate(cache,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((HERE/'protocol.json').read_text())
    a,funding,manifest=load(cache)
    if manifest['npz_sha256']!=protocol['data']['npz_sha256']:raise ValueError('NOT_ORIGINAL_DATASET')
    start=int(np.searchsorted(a[:,0],stamp(protocol['data']['evaluation_start'])));end=len(a)
    if a[-1,0]+HOUR!=stamp(protocol['data']['end_exclusive']):raise ValueError('EVALUATION_END_CHANGED')
    f=calculate(a);r=regime(a);ws=windows(start,end)
    jwrite(out/'data_manifest.json',manifest)
    all_metrics=[];all_deals=[];all_notes=[];annual=[];control_rows=[];funding_bounds=[];equities=[];funnels=[];signals_rows=[]
    summary_counts={}
    for variant in VARIANTS:
        sig=flags(f,variant)
        summary_counts[variant]=dict(long=int(sig['long'][start:end].sum()),short=int(sig['short'][start:end].sum()))
        print(json.dumps(dict(stage='FLAGS',variant=variant,**summary_counts[variant])),flush=True)
        funnels.extend(dict(variant=variant,**row) for row in gate_funnel(a,f,sig,start,end))
        for i in range(start,end):
            row=dict(variant=variant,open_time=iso(a[i,0]),available_at=iso(a[i,0]+HOUR),long=bool(sig['long'][i]),short=bool(sig['short'][i]),
                main_series=float(f['kon_trend' if variant=='BASE' else 'minnows'][i]),red_ema_tendencia=float(f['kon_signal'][i]),
                original_tendencia=float(f['kon_trend'][i]),pececillos=float(f['minnows'][i]),
                adx=float(f['adx'][i]),ao=float(f['ao'][i]),bbwp=float(f['bbwp'][i]),atr=float(f['atr'][i]),
                causal_regime=int(r[i]) if np.isfinite(r[i]) else None)
            row.update({k:bool(sig[k][i]) for k in ('kon_long','kon_short','adx_lagged_decline','ao_long','ao_short','bbwp_above')})
            signals_rows.append(row)
        for target in (2.,3.):
            p=Assumptions(target_r=target)
            for side,book in ((0,'COMBINED'),(1,'LONG_ONLY'),(-1,'SHORT_ONLY')):
                for label,(lo,hi) in ws.items():
                    deals,eq,notes=simulate(a,f['atr'],sig['long'],sig['short'],funding,lo,hi,side,p)
                    m=metrics(deals,eq);sums,counts=daily(deals,a,lo,hi);ci=ratio_ci(sums,counts)
                    row=dict(variant=variant,target_r=target,book=book,window=label,from_utc=iso(a[lo,0]),end_exclusive=iso(a[hi-1,0]+HOUR),
                        candidate_decisions=len(notes),net_r_ci97_5=ci['ci'],bootstrap_replicates_valid=ci['valid_replicates'],
                        exact_net_usdt=exact_net(m),funding_mode=p.funding_mode,
                        classification='INCONCLUSO',**m)
                    if label in ('FULL','TEST'):
                        controls,ref=random_controls(a,f,sig,r,funding,lo,hi,side,p)
                        control_rows.extend(dict(variant=variant,target_r=target,book=book,window=label,**c) for c in controls)
                        exps=[x['expectancy_r'] for x in controls if x['expectancy_r'] is not None]
                        row.update(control_trials=len(controls),control_mean_expectancy_r=float(np.mean(exps)) if exps else None,
                            control_mean_executed=float(np.mean([x['n'] for x in controls])),
                            control_executed_min=min(x['n'] for x in controls),control_executed_max=max(x['n'] for x in controls),
                            controls_missing_mark_scenarios=sum(x['funding_missing_marks_used']>0 for x in controls),
                            control_gain_ci97_5=ratio_ci(sums,counts,reference=ref)['ci'],
                            control_caveat='MONTH_SIDE_CAUSAL_REGIME_CANDIDATE_MATCH; EXECUTED_COUNTS_CAN_DIFFER; NO_FORMAL_PERMUTATION_P_VALUE')
                    all_metrics.append(row)
                    if label in ('FULL','DEVELOPMENT','TEST'):
                        all_deals.extend(dict(variant=variant,target_r=target,book=book,window=label,**d) for d in deals)
                        all_notes.extend(dict(variant=variant,target_r=target,book=book,window=label,**n) for n in notes)
                    if label=='FULL':
                        # Bound missing marks using unchanged alternative Assumptions.
                        alt=replace(p,funding_mode='OPTIMISTIC_MARK_BOUND')
                        optimistic,_,_=simulate(a,f['atr'],sig['long'],sig['short'],funding,lo,hi,side,alt,False)
                        funding_bounds.append(dict(variant=variant,target_r=target,book=book,funding_mode=alt.funding_mode,**metrics(optimistic,None,hours=hi-lo)))
                        years=np.array([iso(t)[:4] for t in a[:,0]])
                        for year in sorted(set(years[lo:hi])):
                            cohort=[d for d in deals if years[d['entry_i']]==year]
                            im=np.flatnonzero(years[lo:hi]==year);curve=eq[im]
                            begin=float(eq[im[0]-1,1]) if im[0] else p.initial
                            path=np.r_[begin,curve[:,1]];peaks=np.maximum.accumulate(path)
                            annual.append(dict(variant=variant,target_r=target,book=book,year=year,
                                trade_assignment='ENTRY_YEAR_COHORT; NO_EQUITY_RESET',
                                calendar_equity_start=begin,calendar_equity_end=float(curve[-1,1]),
                                calendar_net_change_usdt=float(curve[-1,1]-begin),calendar_dd_close_pct=float((1-path/peaks).max()*100),
                                **metrics(cohort,None,hours=len(im))))
                    if side==0 and label in ('FULL','DEVELOPMENT','TEST'):
                        equities.extend(dict(variant=variant,target_r=target,window=label,timestamp=iso(t),equity=close,adverse_bound=adverse) for t,close,adverse in eq)
                print(json.dumps(dict(stage='BOOK_DONE',variant=variant,target=target,book=book)),flush=True)
    # Preserve original sample gates. No positive promotion from re-used history.
    for row in all_metrics:
        if row['window']!='TEST':continue
        enough=row['n']>=(60 if row['book']=='COMBINED' else 30)
        if enough and row['exact_net_usdt'] is not None and (row['expectancy_r']<=0 or row['net_r_ci97_5'] is not None and row['net_r_ci97_5'][1]<=0):
            row['classification']='NO EDGE'
    incidents=incident(out)
    cwrite(out/'signal_funnel.csv',funnels)
    cwrite(out/'signals_all.csv.gz',signals_rows)
    cwrite(out/'metrics.csv',all_metrics)
    cwrite(out/'trades_all.csv',all_deals,('variant','target_r','book','window','signal_open','available_at','side','entry_time','net_usdt','net_r','reason'))
    cwrite(out/'signal_dispositions.csv',all_notes)
    cwrite(out/'annual.csv',annual)
    cwrite(out/'random_controls.csv.gz',control_rows)
    cwrite(out/'funding_bounds.csv',funding_bounds)
    cwrite(out/'equity.csv.gz',equities)
    summary=dict(protocol=protocol['protocol'],protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest(),freeze_commit=FREEZE,
        source_reference_at_run=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha256={k:hashlib.sha256((HERE/k).read_bytes()).hexdigest() for k in ('variants.py','evaluate.py')},
        original_data_sha256=manifest['npz_sha256'],raw_inputs_checked=len(manifest['archives']),
        evaluation_bars=end-start,warmup_bars=start,signals=summary_counts,
        full_combined=[x for x in all_metrics if x['window']=='FULL' and x['book']=='COMBINED'],
        test_results=[x for x in all_metrics if x['window']=='TEST'],
        november_signal_rows=len(incidents),november_performance_scored=False,
        base_matches_pr46_zero_signals=summary_counts['BASE']==dict(long=0,short=0),
        historical_evidence='POST_HOC_SERIES_IDENTIFICATION_COMPARISON_NO_VIRGIN_HOLDOUT',
        new_windows_or_filters_tested=False,initial_equity=200,
        actual_external_visual_points=1,actual_platform_export_rows=0,
        python=platform.python_version(),numpy=np.__version__,trade_authority='NONE',deployed=False)
    if not summary['base_matches_pr46_zero_signals']:raise ValueError('BASE_DOES_NOT_REPRODUCE_PR46')
    jwrite(out/'results.json',summary)
    print(json.dumps(dict(stage='FINISHED',signals=summary_counts,books=summary['full_combined'])),flush=True)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    evaluate(args.cache,args.out)
