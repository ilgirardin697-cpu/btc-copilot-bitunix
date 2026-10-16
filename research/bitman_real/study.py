"""Frozen descriptive event study, no trading simulation or parameter ranking."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from .config import Config,HOUR,TIMEFRAMES,HORIZONS,REENTRY_WINDOWS,CUTOFF,protocol
from .events import analyze
from .market import verified_cache
from .outcomes import measure,summarize,block_bootstrap

ART=Path(__file__).parent/'artifacts'
RULE_FILES=('config.py','indicators.py','events.py','outcomes.py','market.py','study.py')


def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_hash():return hashlib.sha256(b''.join((Path(__file__).parent/p).read_bytes().replace(b'\r\n',b'\n') for p in RULE_FILES)).hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def freeze():
    ART.mkdir(exist_ok=True,parents=True)
    if (ART/'protocol.json').exists():raise ValueError('PROTOCOL_ALREADY_FROZEN')
    bars,manifest=verified_cache()
    write(ART/'data_manifest.json',manifest)
    write(ART/'protocol.json',dict(protocol=protocol(),code_sha256=code_hash(),
        data_manifest_sha256=digest(ART/'data_manifest.json'),
        frozen_at=datetime.now(timezone.utc).isoformat()))
    print('BITMAN_REAL_PROTOCOL_FROZEN',code_hash(),flush=True)


def split(timestamp):
    if timestamp<stamp('2022-01-01T00:00:00Z'):return 'TRAIN',stamp('2022-01-01T00:00:00Z')
    if timestamp<stamp('2024-01-01T00:00:00Z'):return 'VALIDATION',stamp('2024-01-01T00:00:00Z')
    return 'TEST',stamp(CUTOFF)


def fit_bins(rows):
    out={}
    for tf in TIMEFRAMES:
        sample=[s for s in rows[tf] if stamp('2020-01-01T00:00:00Z')<=s['candle_close']<stamp('2022-01-01T00:00:00Z') and s['technical_event']=='KONKORDE_ENTRY']
        out[tf]={}
        for name in ('distance_to_zero','separation'):
            values=[s[name] for s in sample if s[name] is not None]
            out[tf][name]=dict(train_n=len(values),tertiles=np.quantile(values,[1/3,2/3]).tolist() if values else None)
    return out


def group(value,bounds):
    if value is None or bounds is None:return 'UNAVAILABLE'
    return 'LOW' if value<=bounds[0] else 'MID' if value<=bounds[1] else 'HIGH'


def match_keys(rows):
    keys=[]
    for i,s in enumerate(rows):
        d=datetime.fromtimestamp(s['candle_close']/1000,timezone.utc)
        trend=0 if i<24 else int(np.sign(s['close']-rows[i-24]['close']))
        keys.append((d.year,d.month,d.hour,trend))
    return keys


def controls(rows):
    """Matching uses calendar/context only, never subsequent returns."""
    keys=match_keys(rows);pools=defaultdict(list)
    for i,s in enumerate(rows):
        _,end=split(s['candle_close'])
        directional_event=bool(i and s['state']=='LONG' and rows[i-1]['state']!='LONG')
        if (s['technical_event'] is None and not directional_event and s['inside'] is not None
                and s['candle_close']+72*HOUR<=end and s['candle_close']>=stamp('2020-01-01T00:00:00Z')):
            pools[keys[i]].append(i)
    return keys,pools


def labels(s,bins):
    # Fixed cohort definitions, not entry/exit filters.
    expected=-1 if s['technical_event']=='KONKORDE_EXIT' else 1
    di=s['di_plus']-s['di_minus'] if s['di_plus'] is not None and s['di_minus'] is not None else None
    return dict(zero=group(s['distance_to_zero'],bins['distance_to_zero']['tertiles']),
        separation=group(s['separation'],bins['separation']['tertiles']),strength=s['strength'],
        adx='RISING' if s['adx_slope'] is not None and s['adx_slope']>0 else 'NON_RISING' if s['adx_slope'] is not None else 'UNAVAILABLE',
        di='ALIGNED' if di is not None and di*expected>0 else 'NON_ALIGNED' if di is not None else 'UNAVAILABLE',
        ao='ALIGNED' if s['ao'] is not None and s['ao']*expected>0 else 'NON_ALIGNED' if s['ao'] is not None else 'UNAVAILABLE',
        bbwp='EXPANDING' if s['bbwp_slope'] is not None and s['bbwp_slope']>0 else 'NON_EXPANDING' if s['bbwp_slope'] is not None else 'UNAVAILABLE')


def summary(records,groups):
    result={}
    for key,subset in groups.items():
        result[key]=dict(n_events=len(subset),horizons={str(h):summarize([r['outcomes'][str(h)] for r in subset]) for h in HORIZONS})
    return result


def paired(records,kind):
    values=[];times=[];raw=[]
    for r in records:
        a=r['outcomes']['24'];b=r['control_outcomes'].get('24')
        if not a['complete'] or not b or not b['complete']:continue
        delta=a['forward_return']-b['forward_return']
        values.append(delta*(-1 if kind=='KONKORDE_EXIT' else 1));raw.append(delta);times.append(r['candle_close'])
    output=block_bootstrap(values,times);output['raw_event_minus_control_mean']=float(np.mean(raw)) if raw else None
    output['hypothesis']='EXIT lower BTC returns than matched controls; NOT SHORT trading' if kind=='KONKORDE_EXIT' else 'Higher BTC returns than matched controls'
    return output


def classification(primary):
    useful=[];adequate={}
    for tf in TIMEFRAMES:
        r=primary[tf];adequate[tf]=all(r[k]['TEST']['n']>=100 for k in ('KONKORDE_ENTRY','KONKORDE_EXIT'))
        good=adequate[tf]
        for k in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            ci=r[k]['TEST']['ci95'];good &= ci[0] is not None and ci[0]>0
            good &= all(r[k][str(y)]['mean'] is not None and r[k][str(y)]['mean']>0 for y in (2024,2025,2026))
        if good:useful.append(tf)
    if len(useful)>=2:return 'USEFUL OBSERVER'
    signs=[]
    for tf in ('1H','4H'):
        signs.append(adequate[tf] and all(primary[tf][k]['TEST']['mean'] is not None and primary[tf][k]['TEST']['mean']>0 for k in ('KONKORDE_ENTRY','KONKORDE_EXIT')))
    return 'NO EDGE' if adequate['1H'] and adequate['4H'] and not any(signs) else 'INCONCLUSIVE'


def run(output_dir=None):
    frozen=json.loads((ART/'protocol.json').read_text(encoding='utf-8'))
    if code_hash()!=frozen['code_sha256'] or json.dumps(protocol(),sort_keys=True)!=json.dumps(frozen['protocol'],sort_keys=True):raise ValueError('FROZEN_PROTOCOL_CHANGED')
    if digest(ART/'data_manifest.json')!=frozen['data_manifest_sha256']:raise ValueError('FROZEN_MANIFEST_CHANGED')
    out=Path(output_dir) if output_dir else ART
    out.mkdir(parents=True,exist_ok=True)
    if (out/'results.json').exists():raise ValueError('RESULTS_ALREADY_EXIST_USE_NEW_DIRECTORY')
    hourly,manifest=verified_cache();end=stamp(CUTOFF)
    hourly=hourly[hourly[:,0]+HOUR<=end]
    # All reentry ages computed once; no return-ranked reentry window.
    rows={tf:analyze(hourly,tf,end,Config(1)) for tf in TIMEFRAMES}
    bins=fit_bins(rows);write(out/'train_descriptive_bins.json',bins)
    records=[];state_rows=[];primaries={};counts={};conditional={};state_summary={}
    for tf,series in rows.items():
        keys,pools=controls(series);local=[];states=[]
        for i,s in enumerate(series):
            if s['candle_close']<stamp('2020-01-01T00:00:00Z'):continue
            period,period_end=split(s['candle_close'])
            if s['technical_event'] is None and not (i and s['state']=='LONG' and series[i-1]['state']!='LONG') and not s['inside']:continue
            r=dict(s,source='HISTORICAL_BACKTEST',period=period,
                year=datetime.fromtimestamp(s['candle_close']/1000,timezone.utc).year,
                cohorts=labels(s,bins[tf]),
                outcomes={str(h):measure(hourly,s['candle_close'],s['close'],h,period_end) for h in HORIZONS})
            # This study reports every configured subset; never a selected REENTRY rule.
            r['reentry_windows']=[w for w in REENTRY_WINDOWS if s['technical_event']=='KONKORDE_ENTRY' and s['exit_age_bars'] is not None and s['exit_age_bars']<=w]
            if s['technical_event'] is not None or i and s['state']=='LONG' and series[i-1]['state']!='LONG':
                pool=pools.get(keys[i],[]);chosen=pool[int(hashlib.sha256(str(s['candle_close']).encode()).hexdigest()[:16],16)%len(pool)] if pool else None
                ref=series[chosen] if chosen is not None else None
                r['control_timestamp']=ref['candle_close'] if ref else None
                r['control_outcomes']={str(h):measure(hourly,ref['candle_close'],ref['close'],h,period_end) for h in HORIZONS} if ref else {}
                if s['technical_event'] is not None:local.append(r)
                if i and s['state']=='LONG' and series[i-1]['state']!='LONG':
                    identity=hashlib.sha256(f'{s["version"]}|{tf}|{s["candle_close"]}|DIRECTION_LONG'.encode()).hexdigest()
                    states.append(dict(r,technical_event='DIRECTION_LONG',event='DIRECTION_LONG',event_id=identity))
            if s['inside']:state_rows.append(r)
        records+=local;groups={}
        for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            for period in ('TRAIN','VALIDATION','TEST','ALL'):
                groups[kind+'/'+period]=[r for r in local if r['technical_event']==kind and (period=='ALL' or r['period']==period)]
        for w in REENTRY_WINDOWS:
            for period in ('TRAIN','VALIDATION','TEST','ALL'):
                groups[f'KONKORDE_REENTRY_{w}/'+period]=[r for r in local if w in r['reentry_windows'] and (period=='ALL' or r['period']==period)]
        counts[tf]=summary(local,groups)
        primaries[tf]={k:{period:paired([r for r in local if r['technical_event']==k and (r['period']==period or str(r['year'])==period)],k) for period in ('TRAIN','VALIDATION','TEST','2024','2025','2026')} for k in ('KONKORDE_ENTRY','KONKORDE_EXIT')}
        conditional[tf]={}
        for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            cohort_groups={}
            for period in ('TRAIN','VALIDATION','TEST'):
                for field in ('zero','separation','adx','di','ao','bbwp'):
                    for tag in sorted(set(r['cohorts'][field] for r in local)):
                        cohort_groups[f'{period}/{field}/{tag}']=[r for r in local if r['technical_event']==kind and r['period']==period and r['cohorts'][field]==tag]
            conditional[tf][kind]=summary(local,cohort_groups)
        inside=[r for r in state_rows if r['timeframe']==tf]
        state_summary[tf]=dict(long_episode=summary(states,{p:[r for r in states if r['period']==p] for p in ('TRAIN','VALIDATION','TEST')}),
            inside_bar_separation=summary(inside,{f'{p}/{tag}':[r for r in inside if r['period']==p and r['cohorts']['separation']==tag] for p in ('TRAIN','VALIDATION','TEST') for tag in ('LOW','MID','HIGH')}))
        records+=states
        print('BITMAN_REAL_MEASURED',tf,len(local),'technical events',flush=True)
    yearly={tf:{str(y):{kind:summarize([r['outcomes']['24'] for r in records if r['timeframe']==tf and r['year']==y and r['technical_event']==kind]) for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT','DIRECTION_LONG')} for y in range(2020,2027)} for tf in TIMEFRAMES}
    result=dict(version=protocol()['version'],classification=classification(primaries),
        source='HISTORICAL_BACKTEST',cutoff=CUTOFF,protocol_sha256=digest(ART/'protocol.json'),code_sha256=code_hash(),
        exact_bitman_konkorde_parity='NOT PROVEN',short_logic='SHORT_LOGIC_NOT_PROVEN',
        forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
        summaries=counts,primary24h_matched=primaries,yearly=yearly,conditional=conditional,states=state_summary,
        phase2_status='REJECT',trade_authority=False,
        notes=['Raw price returns, not strategy PnL; no fees/funding/assumed orders.',
               'REENTRY subsets overlap ENTRY; state-bar samples strongly overlap.',
               'No TEST ranking or selection. Descriptive groups not hard directional gates.'])
    with gzip.open(out/'events_and_outcomes.jsonl.gz','wt',encoding='utf-8') as stream:
        for r in records:stream.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    write(out/'results.json',result)
    print('BITMAN_REAL_CLASSIFICATION',result['classification'],flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','evaluate']);p.add_argument('--output-dir')
    a=p.parse_args();freeze() if a.phase=='freeze' else run(a.output_dir)
