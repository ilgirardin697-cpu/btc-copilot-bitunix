"""Local historical diagnostic only: no market calls, fills, equity or selection."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from research.confluence_1h_phase2.semantics import validate_bars
from .diagnostic import HERE, H, SERIES, features, detect, episodes, confirmation_stability, sha

START = 1667260800000
END = 1793491200000


def iso(t, zone=timezone.utc):
    return datetime.fromtimestamp(int(t)/1000,zone).isoformat().replace('+00:00','Z')


def clean(x):
    if isinstance(x, np.generic): x=x.item()
    if isinstance(x, float) and not np.isfinite(x): return None
    if isinstance(x, dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    return x


def dump(path, value):
    path.write_text(json.dumps(clean(value),indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def csvout(path, rows):
    rows=list(rows)
    if not rows:
        path.write_text('',encoding='utf-8');return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for r in rows: w.writerow(clean(r))


def distribution(values):
    v=[float(v) for v in values if v is not None and np.isfinite(v)]
    if not v:return dict(n=0,mean=None,median=None,p10=None,p25=None,p75=None,p90=None)
    return dict(n=len(v),mean=float(np.mean(v)),median=float(np.median(v)),
                **dict(zip(('p10','p25','p75','p90'),map(float,np.percentile(v,[10,25,75,90])))))


def summarize(name, aa, turns, group='ALL', label='ALL'):
    counts=Counter(a['status'] for a in aa)
    resolved=[a for a in aa if a['status']!='CENSORED_END_OF_FILE']
    confirmed=[a for a in aa if a['status']=='CONFIRMED']
    false=sum(a['status']!='CONFIRMED' for a in resolved)
    return dict(series=name,group=group,label=label,prealerts=len(aa),confirmed=len(confirmed),
                false=false,censored=len(aa)-len(resolved),false_pct=100*false/len(resolved) if resolved else None,
                invalid_reacceleration=counts['INVALID_REACCELERATION'],invalid_flat=counts['INVALID_FLAT'],
                expired=counts['EXPIRED_2H'],invalid_data=counts['INVALID_DATA'],
                all_confirmed_turns=len(turns),turns_with_prealert=sum(t['prior_alert_id'] is not None for t in turns),
                unstable_turns=sum(t['stability']=='FLAT_OR_REVERSED_WITHIN_2H' for t in turns),
                stable_turns=sum(t['stability']=='SAME_SLOPE_THROUGH_2H' for t in turns),
                **{'delay_'+k:v for k,v in distribution([a['hours'] for a in confirmed]).items()})


def source_audit(root):
    original=root/'research/confluence_1h/reference_sources'
    bb=(original/'bbwp_original.pine.txt').read_text('utf-8-sig')
    kon=(original/'koncorde_original.pine.txt').read_text('utf-8-sig')
    assert 'input.int    ( 7,' in bb and 'input.int    ( 100,' in bb
    assert 'array.binary_search_rightmost' in bb
    return dict(platform='TradingOne',external_machine_readable_records=0,external_parity='NOT_ESTABLISHED',
                source_defaults=dict(bbwp_basis=7,bbwp_lookback=100,bbwp_ma='SMA',bbwp_source='close'),
                requested_comparison=dict(bbwp_basis=13,bbwp_lookback=252,status='SEPARATE_SETTINGS_NOT_CERTIFIED_AS_PLATFORM'),
                audited_python_sha256=sha(root/'research/confluence_1h/indicators.py'),
                supplied_bbwp_sha256=sha(original/'bbwp_original.pine.txt'),
                supplied_koncorde_sha256=sha(original/'koncorde_original.pine.txt'),
                previous_visual_point=json.loads((root/'research/confluence_1h_phase2/event_proximity/visual_evidence.json').read_text('utf-8'))['case_1'],
                series_status={k:'PUBLIC_FORMULA_REUSED_EXTERNAL_PARITY_NOT_ESTABLISHED' for k in ('AO','ADX_DMI','KONCORDE','BBWP')},
                missing=['real named-series closed-bar export','full ticker/venue','indicator identities/version and actual inputs',
                         'same OHLCV/volume and initialization prefix','open/close/available timestamp meanings and precision'],
                caution='one rounded owner-reported Spot pececillos point supports identity only; no synthetic test is independent platform evidence')


def run(data, diagnostic_path, output):
    output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((HERE/'protocol.json').read_text('utf-8'))
    assert sha(data)==plan['history']['data_sha256']
    with np.load(data,allow_pickle=False) as z: a=validate_bars(z['bars'])
    a=a[a[:,0]+H<END]
    f=features(a); times=a[:,0].astype(np.int64)+H
    all_alerts, all_turns, all_lifecycle, summary, hourly=[],[],[],[],[]
    price_stats=[]
    prefix_checks=[]
    for name in SERIES:
        det=detect(times,f[name],name)
        aa=[r for r in episodes(a,det) if START<=r['available_at']<END]
        turns=[dict(t,**confirmation_stability(f[name],times,t)) for t in det['turns'] if START<=t['available_at']<END]
        all_alerts.extend(aa); all_turns.extend(turns)
        for kind in ('alerts','resolutions'):
            all_lifecycle.extend(dict(record_type=kind,**r) for r in det[kind])
        summary.append(summarize(name,aa,turns))
        for side in (-1,1):
            summary.append(summarize(name,[r for r in aa if r['expected_slope']==side],
                                     [r for r in turns if r['slope_direction']==side],'INDICATOR_SLOPE','UP' if side==1 else 'DOWN'))
        for year in ('2022','2023','2024','2025','2026'):
            summary.append(summarize(name,[r for r in aa if iso(r['available_at']).startswith(year)],
                                     [r for r in turns if iso(r['available_at']).startswith(year)],'YEAR',year))
        for group,rows in [('ALL',aa),('CONFIRMED',[r for r in aa if r['status']=='CONFIRMED']),
                           ('FALSE',[r for r in aa if r['status'] not in ('CONFIRMED','CENSORED_END_OF_FILE')])]:
            sides=('up','down') if name.startswith('bbwp') or name=='adx' else ('EXPECTED_DIRECTION',)
            for side in sides:
                for field in ('consumed_pre_pct','consumed_confirm_pct','close_drift_pre_confirm_pct',
                              'remaining_pre_pct','remaining_confirm_pct','consumed_share_pre','consumed_share_confirm'):
                    vals=[r[('up' if r['expected_slope']>0 else 'down')+'_'+field] if side=='EXPECTED_DIRECTION' else r[side+'_'+field] for r in rows]
                    price_stats.append(dict(series=name,group=group,price_reference=side,metric=field,**distribution(vals)))
        for cut in (1000,16000,len(a)-1):
            prefix=detect(times[:cut],f[name][:cut],name)
            for key,idx in [('alerts','i'),('turns','i'),('resolutions','resolution_i'),('hourly','i')]:
                assert clean(prefix[key])==clean([r for r in det[key] if r[idx]<cut]),(name,cut,key)
            prefix_checks.append(dict(series=name,cut=cut,exact=True))
    for i in np.flatnonzero(times>=START):
        row=dict(open_utc=iso(a[i,0]),available_utc=iso(times[i]),open_time_ms=int(a[i,0]),available_at_ms=int(times[i]),
                 **dict(zip(('open','high','low','close','volume'),a[i,1:])))
        for name in f:
            row[name]=f[name][i]
            row[name+'_slope']=f[name][i]-f[name][i-1] if i else None
            row[name+'_acceleration']=f[name][i]-2*f[name][i-1]+f[name][i-2] if i>=2 else None
        hourly.append(row)
    mask=times>=START
    b7,b13=f['bbwp_7_100'][mask],f['bbwp_13_252'][mask]
    d7,d13=np.diff(f['bbwp_7_100'])[mask[1:]],np.diff(f['bbwp_13_252'])[mask[1:]]
    finite=np.isfinite(b7)&np.isfinite(b13)
    slope_finite=np.isfinite(d7)&np.isfinite(d13)
    bbcompare=dict(n=int(finite.sum()),exact_level_matches=int(np.sum(abs(b7[finite]-b13[finite])<=1e-10)),
                   mean_absolute_level_difference=float(np.mean(abs(b7[finite]-b13[finite]))),
                   median_absolute_level_difference=float(np.median(abs(b7[finite]-b13[finite]))),
                   pearson_level_correlation=float(np.corrcoef(b7[finite],b13[finite])[0,1]),
                   slope_sign_agreement_pct=float(np.mean(np.sign(d7[slope_finite])==np.sign(d13[slope_finite]))*100),
                   note='two different settings, never an external platform comparison; no optimized time shift')
    raw=Path(diagnostic_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='e5cb4c2bd439b74066846e4a8076cc1c1aeea1e4fc91cb433810b51a77ea29e8'
    rawrows=json.loads(raw); b=validate_bars(np.array([[r[0],*map(float,r[1:6])] for r in rawrows],float))
    ext=validate_bars(np.r_[a[a[:,0]<b[0,0]],b]); ef=features(ext); et=ext[:,0].astype(np.int64)+H
    ed={k:detect(et,ef[k],k) for k in SERIES}; madrid=ZoneInfo('Europe/Madrid'); diagnostic=[]
    for i in range(len(ext)):
        stamp=iso(et[i],madrid)
        if not '2026-11-16T18'<=stamp<'2026-11-17T07':continue
        r=dict(open_utc=iso(ext[i,0]),available_utc=iso(et[i]),open_madrid=iso(ext[i,0],madrid),available_madrid=stamp,
               open=float(ext[i,1]),high=float(ext[i,2]),low=float(ext[i,3]),close=float(ext[i,4]))
        for k in ef:
            r[k]=ef[k][i];r[k+'_slope']=ef[k][i]-ef[k][i-1];r[k+'_acceleration']=ef[k][i]-2*ef[k][i-1]+ef[k][i-2]
        for k in SERIES:
            h=ed[k]['hourly'][i]
            r[k+'_state']=h['state'];r[k+'_prealert']=h['is_prealert'];r[k+'_confirmed_turn']=h['is_turn']
        diagnostic.append(r)
    diag_episodes=[]
    for k in SERIES:
        diag_episodes.extend(r for r in episodes(ext,ed[k]) if '2026-11-16T18'<=iso(r['available_at'],madrid)<'2026-11-17T07')
    csvout(output/'hourly_values.csv.gz',hourly)
    csvout(output/'prealerts.csv.gz',all_alerts)
    csvout(output/'lifecycle.csv.gz',all_lifecycle)
    csvout(output/'confirmations.csv.gz',all_turns)
    csvout(output/'event_summary.csv',summary)
    csvout(output/'price_distances.csv',price_stats)
    csvout(output/'diagnostic_20261116.csv',diagnostic)
    csvout(output/'diagnostic_episodes.csv',diag_episodes)
    dump(output/'source_audit.json',source_audit(HERE.parents[7]))
    dump(output/'bbwp_comparison.json',bbcompare)
    dump(output/'reproduction.json',dict(protocol_sha256=sha(HERE/'protocol.json'),data_sha256=sha(data),
        diagnostic_sha256=hashlib.sha256(raw).hexdigest(),history_hours=len(hourly),prefix_checks=prefix_checks,
        full_formula_sources_unchanged=True,no_trade_results_calculated=True,original_pr55_untouched=True))
    return summary,bbcompare


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True)
    p.add_argument('--diagnostic',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();summary,bb=run(args.data,args.diagnostic,args.out)
    print(json.dumps(dict(summary=[x for x in summary if x['group']=='ALL'],bbwp=bb),indent=2))
