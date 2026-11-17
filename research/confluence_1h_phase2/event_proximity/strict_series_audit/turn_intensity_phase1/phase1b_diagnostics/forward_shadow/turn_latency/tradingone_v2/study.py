"""One local source-profile comparison, never a profitability backtest."""
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import argparse,csv,gzip,hashlib,json,copy
import numpy as np
from mlrsi_math import CausalSeries
from bitman_manual.frozen.indicators import calculate as frozen
from research.confluence_1h.indicators import calculate as research,smooth,lag
from igod_daily_plan.core import bbwp_series
from .profile import HERE,H,calculate,settings
from .backquant import OriginalMLRSI


def clean(x):
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    return x
def dump(path,x):path.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def iso(t,zone=timezone.utc):return datetime.fromtimestamp(int(t)/1000,zone).isoformat().replace('+00:00','Z')
def csvout(path,rows):
    rows=list(rows);keys=list(dict.fromkeys(k for r in rows for k in r))
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(clean(rows))
def finite(v):return np.isfinite(np.asarray(v,float))


def run(folder,out):
    out.mkdir(parents=True,exist_ok=False)
    meta=json.loads((folder/'manifest.json').read_text('utf-8'))
    assert meta['venue']=='BINANCE_SPOT' and meta['rows']==3200
    assert sha(folder/'bars.csv.gz')==meta['bars_sha256']
    raw=[]
    for r in meta['receipts']:
        p=folder/r['file'];assert sha(p)==r['sha256']
        if r['file'].startswith('page_'):raw.extend(json.loads(p.read_text('utf-8')))
    entire=np.array([[r[0],*map(float,r[1:6])] for r in raw],float)
    assert len(entire)==3200 and np.array_equal(np.diff(entire[:,0]),np.full(3199,H))
    assert entire[-1,0]+H==meta['asof_closed']
    a=entire[1:];anchor=len(a);times=a[:,0].astype(np.int64)+H;zone=ZoneInfo('Europe/Madrid')
    f,ml=calculate(a,anchor);print('PROFILE_CALCULATED',len(a),flush=True)
    old=research(a)
    # Actual unused-in-this-calculator taker-buy column retained from public rows.
    same7=np.c_[a,[float(r[9]) for r in raw[1:]]]
    fr=frozen(same7)
    igod=CausalSeries();igod.configure_bootstrap(anchor)
    ir=[igod.push(v) for v in a[:,3]]
    ival=np.array([np.nan if r['mlrsi_smoothed'] is None else r['mlrsi_smoothed'] for r in ir])
    icolor=np.array([r['color'] for r in ir]);iupper=np.array([np.nan if r['upper_threshold'] is None else r['upper_threshold'] for r in ir])
    ilower=np.array([np.nan if r['lower_threshold'] is None else r['lower_threshold'] for r in ir])
    ema27=smooth(f['ml_raw'],4,'ema')
    daily=bbwp_series([dict(c=r[4]) for r in a])
    db=np.array([np.nan if r[0] is None else r[0] for r in daily]);ds=np.array([np.nan if r[1] is None else r[1] for r in daily])
    cmp=dict(igod_ao=fr['ao'],igod_adx=fr['adx'],igod_plus_di=fr['di_plus'],igod_minus_di=fr['di_minus'],
             igod_mountain=fr['mountain'],igod_red=fr['ma'],igod_bbwp7=fr['bbwp'],research_bbwp7=old['bbwp'],
             daily_bbwp13=db,daily_bbwp_signal=ds,igod_ml29=ival,igod_ml29_upper=iupper,igod_ml29_lower=ilower,
             igod_ml29_color=icolor,ema27_smoothing_only=ema27)
    focus=np.array(['2026-11-16'<=iso(t-H,zone)[:10]<='2026-11-17' for t in times])
    metrics=[]
    for name,other in [('ao','igod_ao'),('adx','igod_adx'),('plus_di','igod_plus_di'),('minus_di','igod_minus_di'),
                       ('roja','igod_red'),('pececillos','igod_mountain'),('bbwp','igod_bbwp7'),
                       ('bbwp','research_bbwp7'),('bbwp','daily_bbwp13'),('bbwp_signal','daily_bbwp_signal'),
                       ('ml_value','igod_ml29'),('ml_value','ema27_smoothing_only')]:
        x,y=f[name],cmp[other];dx=x-lag(x);dy=y-lag(y)
        for label,mask in [('FOCUS_16_17',focus),('COMMON_VALID_WARMED',np.arange(len(a))>=300)]:
            ok=mask&finite(x)&finite(y);sl=ok&finite(dx)&finite(dy)
            tx=np.where((dx>0)&(lag(dx)<=0),1,np.where((dx<0)&(lag(dx)>=0),-1,0))
            ty=np.where((dy>0)&(lag(dy)<=0),1,np.where((dy<0)&(lag(dy)>=0),-1,0))
            metrics.append(dict(profile_field=name,reference=other,window=label,n=int(ok.sum()),
                max_abs_error=float(np.max(abs(x[ok]-y[ok]))) if ok.any() else None,
                mean_abs_error=float(np.mean(abs(x[ok]-y[ok]))) if ok.any() else None,
                slope_sign_agreement_pct=float(np.mean(np.sign(dx[sl])==np.sign(dy[sl]))*100) if sl.any() else None,
                turns_profile=int(np.count_nonzero(tx[sl])),turns_reference=int(np.count_nonzero(ty[sl])),
                turn_direction_same_hour=int(np.sum((tx[sl]!=0)&(tx[sl]==ty[sl]))),
                note='pececillos/mountain deliberately DIFFERENT series, not an error tolerance test' if name=='pececillos' else 'common Spot H1 input; not deployed-bot or platform observations'))
    cut=int(np.searchsorted(times,1794783600000,side='right')) #16Nov00Madrid=15Nov23UTC, confirmed prefix
    assert iso(1794783600000)=='2026-11-15T23:00:00Z'
    live=OriginalMLRSI(cut);live_rows=[live.push(v) for v in a[:,3]]
    lv=np.array([np.nan if r['upper'] is None else r['upper'] for r in live_rows]);lc=np.array([r['color'] for r in live_rows])
    replay=OriginalMLRSI(anchor);again=[replay.push(v) for v in a[:,3]]
    assert np.array_equal(np.array([np.nan if r['value'] is None else r['value'] for r in again]),f['ml_value'],equal_nan=True)
    assert np.array_equal(np.array([np.nan if r['upper'] is None else r['upper'] for r in again]),f['ml_upper'],equal_nan=True)
    init_f,_=calculate(entire,len(entire));print('RELOAD_AND_INITIALIZATION_CALCULATED',flush=True)
    reload_rows=[]
    for i in np.flatnonzero(focus):
        reload_rows.append(dict(open_utc=iso(a[i,0]),available_utc=iso(times[i]),available_madrid=iso(times[i],zone),
             chart_reload_value=f['ml_value'][i],persisted_session_value=live_rows[i]['value'],
             chart_reload_upper=f['ml_upper'][i],persisted_session_upper=live_rows[i]['upper'],
             chart_reload_color=f['ml_color'][i],persisted_session_color=live_rows[i]['color'],
             requested_3200_closed_value=init_f['ml_value'][i+1],requested_3200_closed_upper=init_f['ml_upper'][i+1],
             chart_samples=int(f['ml_samples'][i]),live_samples=live_rows[i]['samples']))
    current=json.loads((folder/'forming.json').read_text('utf-8'))[0]
    assert current[0]==meta['asof_closed'] and current[6]+1>datetime.fromisoformat(meta['provisional_received_at']).timestamp()*1000
    state=ml.state();preview=ml.preview(float(current[3]));assert ml.state()==state
    anew=np.r_[a,[[current[0],*map(float,current[1:6])]]]
    # Only one appended live snapshot. Original chart history recomputed with SAME anchor;
    # it is never relabelled as closed or as a recorded TradingOne prediction.
    pf,pml=calculate(anew,anchor)
    for name in ('ao','adx','pececillos','bbwp','ml_value','ml_upper','tsa_trend','tsa_speed'):
        np.testing.assert_array_equal(pf[name][:-1],f[name])
    assert abs(preview['value']-pf['ml_value'][-1])<1e-10
    provisional=dict(source=meta['provisional_status'],received_at=meta['provisional_received_at'],open_time=iso(current[0]),
        closed=False,not_platform_observation=True,committed_state_unchanged=True,expected_available_at=iso(current[6]+1),
        values={k:clean(pf[k][-1]) for k in ('ao','ao_slope','adx','pececillos','bbwp','bbwp_signal','ml_value','ml_color','tsa_trend','tsa_speed')},
        warning='one actual public partial H1; future close unknown; not a live TradingOne execution or continuous capture')
    hourly=[];diagnostic=[]
    for i in range(len(a)):
        row=dict(open_utc=iso(a[i,0]),available_utc=iso(times[i]),open_madrid=iso(a[i,0],zone),available_madrid=iso(times[i],zone),
                 open=float(a[i,1]),high=float(a[i,2]),low=float(a[i,3]),close=float(a[i,4]),volume=float(a[i,5]),
                 status='CLOSED_SOURCE_REPLAY_NOT_PLATFORM_VALUES')
        row.update({k:v[i] for k,v in f.items()});row.update({k:v[i] for k,v in cmp.items()})
        hourly.append(row)
        if focus[i]:diagnostic.append(row)
    external_ok=focus&finite(f['ml_value'])&finite(ival)
    lmask=focus&finite(lv)&finite(f['ml_upper'])
    summary=dict(profile='TRADINGONE_V2',source_json_sha256=settings()['source_json_sha256'],
        primary_closed_rows=len(a),history_first_open=iso(a[0,0]),last_closed_available=iso(times[-1]),focus_rows=int(focus.sum()),
        focus_first_open=iso(a[np.flatnonzero(focus)[0],0]),focus_last_open=iso(a[np.flatnonzero(focus)[-1],0]),
        ml_profile_vs_igod_color_agreement_pct=float(np.mean(f['ml_color'][external_ok]==icolor[external_ok])*100),
        ml_colors_different=int(np.sum(f['ml_color'][external_ok]!=icolor[external_ok])),
        reload_vs_session_color_changes=int(np.sum(f['ml_color'][focus]!=lc[focus])),
        reload_vs_session_upper_max_abs_difference=float(np.max(abs(f['ml_upper'][lmask]-lv[lmask]))),
        same_prefix_repeat_exact=True,provisional_rollback_pass=True,actual_fixed_anchor_prefix_checks=8,
        chart_load_anchor=anchor,session_load_anchor=cut,session_load_known_available=iso(times[cut-1]),
        old_first_bar_extra_initialization='separate predeclared diagnostic only; no fit selection',
        external_tradingone_numeric_records=0,platform_numeric_parity='NOT_CERTIFIED',
        kernel_assumptions=['PineV5 NA conditions and percentile array behavior','all-NA array.indexof initial case','HMA5 integer half2/sqrt2','Pine dynamic speed expression read-before-write history','gradient channel rounding and renderer overrides'],
        profit_or_trade_results_computed=False,production_queried=False)
    csvout(out/'hourly.csv.gz',hourly);csvout(out/'nov16_17.csv',diagnostic);csvout(out/'comparison.csv',metrics);csvout(out/'reload.csv',reload_rows)
    dump(out/'provisional.json',provisional);dump(out/'summary.json',summary)
    dump(out/'input_manifest.json',meta)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.data,a.out)
