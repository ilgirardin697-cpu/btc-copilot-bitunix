"""Run the frozen offline protocol. Never select a best threshold or target."""
import argparse
import csv
from dataclasses import replace
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

from .data import HERE,HOUR,load,stamp,iso
from .engine import Assumptions,simulate,metrics
from .indicators import calculate,signals,regime
from .reference import calculate_scalar
from .statistics import daily,ratio_ci,random_controls
from .diagnostics import gate_funnel,rejection_plots


def json_write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def csv_write(path,rows):
    if not rows:
        header=('target_r,book,window,signal_open,available_at,side,entry_time,exit_bar_open,entry,exit,stop,target,qty_btc,net_usdt,net_r,reason' if path.name.startswith('trades') else 'status,reason')
        path.write_text(header+'\n',encoding='utf-8');return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def gz_write(path,rows):
    lines=''.join(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for row in rows).encode()
    path.write_bytes(gzip.compress(lines,mtime=0))


def classification(m,ci,side):
    n=30 if side else 60
    if m['n']<n or ci['ci'] is None:return 'INCONCLUSO'
    if m['expectancy_r']<=0 or ci['ci'][1]<=0:return 'NO EDGE'
    return 'INCONCLUSO' # All positive robustness/control gates assessed below; never early-promote.


def parity_audit(bars,f):
    ref=calculate_scalar(bars[:1000]);mathdiff={}
    for key,r in ref.items():
        current=f[key][:len(r)];valid=np.isfinite(r)&np.isfinite(current)
        mathdiff[key]=dict(n=int(valid.sum()),max_absolute_difference=float(abs(current[valid]-r[valid]).max()) if valid.any() else None,
            same_availability=bool(np.array_equal(np.isfinite(r),np.isfinite(current))),
            passed=bool(np.allclose(current,r,rtol=1e-9,atol=1e-8,equal_nan=True)))
    return dict(local_independent_scalar=mathdiff,actual_tradingview_records=0,
        tradingview_compiled=False,real_python_pine_parity='NOT_VERIFIED_NO_ACTUAL_LOGS',
        bitman_private_parity='NOT_PROVEN',source='SUPPLIED_PUBLIC_DEFAULTS_MPL2; AO5_34_DMI14_14_ATR14',
        warning='LOCAL_REFERENCE_IS_NOT_PINE_EXECUTION_OR_INDEPENDENT_MARKET_EVIDENCE')


def package_audit(bars,f):
    # Import the fully reviewed supplied module under a private name; __main__
    # never runs. Its downloader/simulator/selector are deliberately not called.
    import importlib.util
    from importlib.machinery import SourceFileLoader
    import pandas as pd
    path=HERE/'reference_sources/package_igod_confluencia_backtest.py.txt'
    loader=SourceFileLoader('_supplied_confluence_reference',str(path))
    spec=importlib.util.spec_from_loader(loader.name,loader);module=importlib.util.module_from_spec(spec)
    sys.modules[loader.name]=module;loader.exec_module(module)
    frame=pd.DataFrame(bars[:,1:],columns=['open','high','low','close','volume'],index=pd.to_datetime(bars[:,0],unit='ms',utc=True))
    original=module.compute_indicators(frame);sig=module.make_signals(original,module.Params())
    corrected=signals(f);delta={}
    for k in original:
        a=original[k].to_numpy();b=f[k];valid=np.isfinite(a)&np.isfinite(b)
        delta[k]=dict(max_absolute_difference=float(abs(a[valid]-b[valid]).max()) if valid.any() else None,
            different_after_warmup=int((abs(a[1000:]-b[1000:])>1e-8).sum()),
            different_availability=int((np.isfinite(a)!=np.isfinite(b)).sum()))
    return dict(indicator_differences=delta,
        long_flags_changed=int((sig['long'].to_numpy()!=corrected['long']).sum()),
        short_flags_changed=int((sig['short'].to_numpy()!=corrected['short']).sum()),
        selection_function_run=False,original_backtestingpy_run=False,
        explanation='Original index-rank ties and DMI first-TR seed differ; original driver also searches18 settings, omits funding and entry fees in open equity; its optional broker comparison has explicitly different brackets/time exits.')


def evaluate(cache,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bars,funding,manifest=load(cache)
    protocol=json.loads((HERE/'protocol.json').read_text())
    assert manifest['protocol_sha256']==hashlib.sha256((HERE/'protocol.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    start=int(np.searchsorted(bars[:,0],stamp(protocol['data']['evaluation_start'])));end=len(bars)
    n=end-start;cut=start+int(.70*n)
    f=calculate(bars);sig=signals(f);r=regime(bars)
    audit=parity_audit(bars,f);audit['supplied_zip_comparison']=package_audit(bars,f)
    if not all(v['passed'] for v in audit['local_independent_scalar'].values()):raise ValueError('LOCAL_FORMULA_PARITY_FAILED')
    json_write(out/'indicator_audit.json',audit);json_write(out/'data_manifest.json',manifest)
    windows={'FULL':(start,end),'DEVELOPMENT':(start,cut-24),'TEST':(cut+24,end)}
    borders=[start+int(n*x) for x in (.30,.40,.50,.60,.70)]
    for i in range(4):windows['WF'+str(i+1)]=(borders[i]+24,borders[i+1]-24)
    allsignals=[]
    for i in range(start,end):
        row=dict(signal_i=i,open_time=iso(bars[i,0]),available_at=iso(bars[i,0]+HOUR),
            long=bool(sig['long'][i]),short=bool(sig['short'][i]),regime=int(r[i]) if np.isfinite(r[i]) else None,
            open=bars[i,1],high=bars[i,2],low=bars[i,3],close=bars[i,4])
        for key in ('kon_trend','kon_signal','adx','adx_slope','plus_di','minus_di','ao','ao_slope','bbwp','bbwp_slope','atr'):
            row[key]=float(f[key][i]) if np.isfinite(f[key][i]) else None
        for key in ('kon_long','kon_short','adx_lagged_decline','ao_long','ao_short','bbwp_above'):row[key]=bool(sig[key][i])
        allsignals.append(row)
    csv_write(out/'signals_all.csv',allsignals)
    gz_write(out/'signals_all.jsonl.gz',allsignals)
    csv_write(out/'signal_funnel.csv',gate_funnel(bars,f,sig,start,end))
    rejection_examples=rejection_plots(bars,f,sig,start,end,out)
    json_write(out/'rejected_examples.json',dict(selection='POST_HOC_DIAGNOSTIC_FIRST_CHRONOLOGICAL_NO_OUTCOME_SELECTION',examples=rejection_examples))
    results=[];ledger=[];equity_rows=[];decisions=[];random_rows=[];slices=[];sensitivity=[];curves={};sensitivity_ledger=[]
    for target in (2.,3.):
        p=Assumptions(target_r=target)
        for side,book in ((0,'COMBINED'),(1,'LONG_ONLY'),(-1,'SHORT_ONLY')):
            for name,(lo,hi) in windows.items():
                trades,eq,notes=simulate(bars,f['atr'],sig['long'],sig['short'],funding,lo,hi,side,p)
                m=metrics(trades,eq);ds,dc=daily(trades,bars,lo,hi);ci=ratio_ci(ds,dc)
                row=dict(target_r=target,book=book,window=name,from_utc=iso(bars[lo,0]),end_exclusive=iso(bars[hi-1,0]+HOUR),
                    candidate_signals=len(notes),net_r_ci97_5=ci['ci'],bootstrap_valid_replicates=ci['valid_replicates'],
                    exact_funding_mark_source_status=('NO_TRADES_NO_PERFORMANCE_ESTIMATE' if not m['n'] else 'ALL_TRADED_MARKS_VERIFIED' if not m['funding_missing_marks_used'] else 'POINT_NET_BLOCKED_SCENARIO_BOUND_ONLY'),
                    exact_net_usdt=m['net_usdt'] if m['n'] and not m['funding_missing_marks_used'] and not m['funding_timing_ambiguities'] else None,
                    funding_mode=p.funding_mode,classification=classification(m,ci,side),**m)
                if name=='TEST':
                    controls,refdaily=random_controls(bars,f,sig,r,funding,lo,hi,side,p)
                    random_rows.extend(dict(target_r=target,book=book,**c) for c in controls)
                    delta=ratio_ci(ds,dc,reference=refdaily)
                    exps=[c['expectancy_r'] for c in controls if c['expectancy_r'] is not None]
                    row.update(control_mean_expectancy_r=float(np.mean(exps)) if exps else None,
                        control_mean_executed=float(np.mean([c['n'] for c in controls])),
                        control_gain_ci97_5=delta['ci'],control_warning='CANDIDATE_STRATA_MATCH_EXECUTED_COUNT_CAN_DIFFER; NOT_A_FORMAL_PERMUTATION_P_VALUE')
                results.append(row)
                if name in ('FULL','DEVELOPMENT','TEST'):
                    ledger.extend(dict(target_r=target,book=book,window=name,**t) for t in trades)
                    decisions.extend(dict(target_r=target,book=book,window=name,**d) for d in notes)
                if side==0 and name in ('FULL','DEVELOPMENT','TEST'):
                    curves[(target,name)]=eq
                    equity_rows.extend(dict(target_r=target,window=name,timestamp=iso(x[0]),equity_close=x[1],adverse_whole_bar_bound=x[2]) for x in eq)
                if name=='FULL':
                    for grouping in ('year','side','regime'):
                        labels=[iso(bars[t['entry_i'],0])[:4] if grouping=='year' else str(t['side']) if grouping=='side' else str(int(r[t['signal_i']])) for t in trades]
                        keys=sorted(set(iso(t)[:4] for t in bars[lo:hi,0])) if grouping=='year' else ['-1','1'] if grouping=='side' else ['-1','0','1']
                        for key in keys:
                            subset=[t for t,label in zip(trades,labels) if label==key]
                            slices.append(dict(target_r=target,book=book,grouping=grouping,value=key,
                                assignment='ENTRY_YEAR_OR_SIGNAL_CAUSAL_REGIME; TRADE_ATTRIBUTION_NOT_A_NEW_PORTFOLIO',
                                **metrics(subset,None,hours=hi-lo)))
                    opt=replace(p,funding_mode='OPTIMISTIC_MARK_BOUND')
                    other,_,_=simulate(bars,f['atr'],sig['long'],sig['short'],funding,lo,hi,side,opt,False)
                    sensitivity.append(dict(target_r=target,book=book,window='FULL',variant='OPTIMISTIC_MISSING_MARK_BOUND',**metrics(other,None,hours=hi-lo)))
            for adx,bbwp,label in ((40,85,'BASE'),(35,85,'ADX35'),(45,85,'ADX45'),(40,80,'BBWP80'),(40,90,'BBWP90')):
                ss=signals(f,adx,bbwp)
                for name in ('DEVELOPMENT','TEST'):
                    lo,hi=windows[name]
                    trades,_,_=simulate(bars,f['atr'],ss['long'],ss['short'],funding,lo,hi,side,p,False)
                    sensitivity.append(dict(target_r=target,book=book,window=name,variant=label,**metrics(trades,None,hours=hi-lo)))
                    sensitivity_ledger.extend(dict(target_r=target,book=book,window=name,variant=label,**t) for t in trades)
            lo,hi=windows['TEST'];stress=replace(p,fee=.0015,slippage=.001)
            trades,eq,_=simulate(bars,f['atr'],sig['long'],sig['short'],funding,lo,hi,side,stress)
            sensitivity.append(dict(target_r=target,book=book,window='TEST',variant='COST_STRESS_15_10_BPS',**metrics(trades,eq)))
    for row in results:
        if row['window']!='TEST' or row['classification']=='NO EDGE':continue
        side=0 if row['book']=='COMBINED' else 1
        sufficient=row['n']>=(60 if not side else 30)
        folds=[x for x in results if x['book']==row['book'] and x['target_r']==row['target_r'] and x['window'].startswith('WF')]
        other=[x for x in results if x['book']==row['book'] and x['window']=='TEST']
        neighbors=[x for x in sensitivity if x['book']==row['book'] and x['window']=='TEST' and x['variant'] in ('BASE','ADX35','ADX45','BBWP80','BBWP90')]
        gates=[sufficient,row['net_r_ci97_5'] is not None and row['net_r_ci97_5'][0]>0,
            row.get('control_gain_ci97_5') is not None and row['control_gain_ci97_5'][0]>0,
            row['profit_factor'] is not None and row['profit_factor']>1,
            sum(x['expectancy_r'] is not None and x['expectancy_r']>0 for x in folds)>=3,
            row['ex_best3_mean_r'] is not None and row['ex_best3_mean_r']>0,
            all(x['expectancy_r'] is not None and x['expectancy_r']>0 for x in other+neighbors),
            not row['funding_missing_marks_used']]
        if all(gates):row['classification']='PROMETEDOR PERO NO VALIDADO'
        row['promising_gates_passed']=gates
    # CSV encodes nested CIs explicitly rather than hiding them in a text repr.
    csv_write(out/'metrics.csv',[{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in x.items()} for x in results])
    csv_write(out/'trades_all.csv',ledger);gz_write(out/'trades_all.jsonl.gz',ledger)
    csv_write(out/'signal_dispositions.csv',decisions);csv_write(out/'equity_all.csv',equity_rows)
    for filename in ('signals_all.csv','equity_all.csv'):
        (out/(filename+'.gz')).write_bytes(gzip.compress((out/filename).read_bytes(),mtime=0))
    csv_write(out/'random_controls.csv',random_rows);csv_write(out/'sensitivity.csv',sensitivity);csv_write(out/'year_side_regime.csv',slices)
    csv_write(out/'sensitivity_trades.csv',sensitivity_ledger)
    summary=dict(protocol=protocol['protocol'],protocol_sha256=manifest['protocol_sha256'],
        freeze_commit='4896dee9b9ae4bc28c05e479562a1511f48cd972',
        data_addenda_commits=['fe29923bf3fa5f4b1a59d95566e77d0f1feae3ce','a077a0b','85ec9ba'],
        evaluation_bars=n,warmup_bars=start,split_at_utc=iso(bars[cut,0]),long_signals=int(sig['long'][start:].sum()),
        short_signals=int(sig['short'][start:].sum()),metrics=results,
        evidence='RETROSPECTIVE_NO_VIRGIN_HOLDOUT',actual_forward_events=0,actual_pine_logs=0,
        outcome_distribution_status='NOT_ESTIMABLE_NO_PRIMARY_TRADES' if not ledger else 'AVAILABLE_IN_TRADE_CSV',
        no_trade_zero_equity_change='MECHANICAL_NO_ACTIVITY_NOT_EVIDENCE_OF_SAFETY_OR_PROFITABILITY',
        python=platform.python_version(),numpy=np.__version__,implementation_commit_at_run=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha_note='Run commit is a source reference; uncommitted implementation/source hashes are captured below before results are versioned.',
        source_sha256={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in HERE.glob('*.py')},
        generated_at=datetime.now(timezone.utc).isoformat(),trade_authority='NONE',deployed=False)
    json_write(out/'results.json',summary)
    make_plots(bars,f,sig,ledger,curves,out,start,end)
    json_write(out/'artifact_checksums.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='artifact_checksums.json'})
    print(json.dumps({k:summary[k] for k in ('evaluation_bars','warmup_bars','split_at_utc','long_signals','short_signals')}))
    print(json.dumps([r for r in results if r['window']=='TEST'],allow_nan=False))


def make_plots(bars,f,sig,ledger,curves,out,start,end):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    times=np.array([datetime.fromtimestamp(t/1000,timezone.utc) for t in bars[:,0]])
    fig,axs=plt.subplots(2,1,figsize=(15,8),sharex=True)
    axs[0].plot(times[start:end],bars[start:end,4],lw=.5,color='#334155',label='BTCUSDT Binance USD-M H1')
    for side,key,color,mark in ((1,'long','#16a34a','^'),(-1,'short','#dc2626','v')):
        ids=np.flatnonzero(sig[key]);ids=ids[(ids>=start)&(ids<end)]
        axs[0].scatter(times[ids],bars[ids,4],c=color,marker=mark,s=20,label=key.upper()+' confirmed close')
        for i in ids:axs[0].axvline(times[i],color=color,alpha=.12,lw=.4)
    for target in (2.,3.):
        eq=curves[(target,'FULL')];t=[datetime.fromtimestamp(x/1000,timezone.utc) for x in eq[:,0]]
        axs[1].plot(t,eq[:,1],label=f'{target:g}R combined, conservative funding scenario')
    axs[0].legend(fontsize=8);axs[1].legend(fontsize=8);axs[1].set_ylabel('Simulated USDT; initial 200')
    fig.suptitle('OFFLINE SHADOW — all confirmed signals; no runtime or real fills');fig.tight_layout();fig.savefig(out/'all_signals_equity.png',dpi=150);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(12,7))
    for a,target in enumerate((2.,3.)):
        for b,period in enumerate(('DEVELOPMENT','TEST')):
            eq=curves[(target,period)];axs[a,b].plot(eq[:,1]);axs[a,b].set_title(f'{target:g}R {period} (not virgin holdout)');axs[a,b].set_ylabel('USDT')
    fig.tight_layout();fig.savefig(out/'development_test.png',dpi=140);plt.close(fig)
    chosen=[];base=[t for t in ledger if t['window']=='FULL' and t['book']=='COMBINED' and t['target_r']==2]
    for side in (1,-1):
        for win in (True,False):
            found=[t for t in base if t['side']==side and (t['net_usdt']>0)==win]
            if found:chosen.append(found[0])
    for k,t in enumerate(chosen):
        s=t['signal_i'];lo=max(start,s-36);hi=min(end,t['exit_i']+20)
        fig,axs=plt.subplots(3,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1,1]})
        for j in range(lo,hi):
            color='#16a34a' if bars[j,4]>=bars[j,1] else '#dc2626';x=times[j]
            axs[0].vlines(x,bars[j,3],bars[j,2],color=color,lw=.7);axs[0].plot([x,x],[bars[j,1],bars[j,4]],color=color,lw=4)
        axs[0].axvline(times[s],color='#8b5cf6',ls=':',label='signal candle; available one hour later')
        for name,color in [('entry','#2563eb'),('stop','#dc2626'),('target','#16a34a')]:
            axs[0].hlines(t[name],times[t['entry_i']],times[t['exit_i']],color=color,label=name)
        axs[1].plot(times[lo:hi],f['kon_trend'][lo:hi],label='Koncorde trend');axs[1].plot(times[lo:hi],f['kon_signal'][lo:hi],label='EMA15');axs[1].axhline(0,color='gray',lw=.5)
        axs[2].plot(times[lo:hi],f['adx'][lo:hi],label='ADX14/14');axs[2].plot(times[lo:hi],f['bbwp'][lo:hi],label='BBWP literal')
        for ax in axs:ax.legend(fontsize=7);ax.grid(alpha=.15)
        axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=timezone.utc))
        fig.suptitle(f'First chronological {"LONG" if t["side"]==1 else "SHORT"} {"winner" if t["net_usdt"]>0 else "loser"}: {t["reason"]}; {t["net_r"]:.3f}R; UTC')
        fig.tight_layout();fig.savefig(out/f'example_{k+1}.png',dpi=150);plt.close(fig)
    json_write(out/'example_selection.json',dict(rule='FIRST_CHRONOLOGICAL_WINNER_AND_LOSER_PER_SIDE_2R_COMBINED; NO_BEST_EXAMPLE_SELECTION',examples=chosen))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',default='research/cache/confluence_1h_market_data');p.add_argument('--out',default=str(HERE/'artifacts'))
    a=p.parse_args();evaluate(a.cache,a.out)
