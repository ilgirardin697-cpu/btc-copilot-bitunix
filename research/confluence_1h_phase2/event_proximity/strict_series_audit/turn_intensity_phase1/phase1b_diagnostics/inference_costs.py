"""Reconstruct original variance and report assumption sensitivities, not winners."""
import csv,gzip,io,json
from collections import defaultdict
import numpy as np
from ..evaluate import HERE as PARENT
from ..inference import required_n
from ..outcomes import outcome


def read_csv(name):
    raw=(PARENT/'artifacts'/name).read_bytes()
    if name.endswith('.gz'):raw=gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode())))


def diagnose(a,f,funding):
    originals=read_csv('outcomes.csv.gz'); controls=read_csv('matched_controls.csv.gz')
    paired=defaultdict(list)
    for row in controls:
        if not row.get('h'):continue
        key=(row['stage'],row['pattern'],row['side'],row['stratum'],row['event_id'],row['h'])
        paired[key].append(row)
    power=json.loads((PARENT/'artifacts/power_frozen_from_development.json').read_text())
    development=[];sensitivity=[]
    for cell in power:
        xs=[]
        for row in originals:
            if row['stage']!='DEVELOPMENT' or row['stratum']!='Q75' or row['hours']!='12' or row['pattern']!=cell['pattern'] or int(row['side'])!=cell['side']:continue
            key=(row['stage'],row['pattern'],row['side'],row['stratum'],row['event_id'],row['hours'])
            match=paired.get(key,[])
            if not match:continue
            if len(match)!=3:raise ValueError('ORIGINAL_THREE_CONTROLS_MISSING')
            mean=float(np.mean([float(v['net_fraction']) for v in match]));delta=float(row['net_fraction'])-mean;xs.append(delta)
            development.append(dict(pattern=cell['pattern'],side=cell['side'],event_id=row['event_id'],
                                    signal_available=row['signal_available'],event_net=float(row['net_fraction']),
                                    controls_net=[float(v['net_fraction']) for v in match],control_mean=mean,paired_excess=delta))
        if len(xs)>=2:
            sigma=float(np.std(xs,ddof=1))
            if not np.isclose(sigma,cell['sigma'],rtol=0,atol=1e-14):raise ValueError('FROZEN_SIGMA_NOT_REPRODUCED')
        else:
            sigma=cell['sigma']  # original explicitly flagged fallback, not evaluation data
        for effect in (.001,.003,.005):
            n=required_n(sigma,effect)
            if effect==.001 and n!=cell['required_effective_n']:raise ValueError('PRIMARY_POWER_NOT_REPRODUCED')
            sensitivity.append(dict(pattern=cell['pattern'],side=cell['side'],development_matched_n=len(xs),
                                    sigma_sample_ddof1=sigma,variance=sigma**2,MDE_pp=effect*100,
                                    required_effective_n=n,primary_unchanged=effect==.001,
                                    fallback_used=cell['fallback_used'],unit='net_fraction',
                                    note='Plug-in variance from2-7 sparse development pairs is very uncertain; sensitivity does not replace primary'))
    cache={}
    def get(i,side,h,fee):
        key=(i,side,h,fee)
        if key not in cache:cache[key]=outcome(a,funding,i,side,f['atr'][i],h,fee=fee,slip=.0005)
        if cache[key] is None:raise ValueError('ORIGINAL_OUTCOME_UNAVAILABLE')
        return cache[key]
    rows=[];groups=defaultdict(list)
    for original in originals:
        i=int(original['entry_i'])-1;side=int(original['side']);h=int(original['hours'])
        key=(original['stage'],original['pattern'],original['side'],original['stratum'],original['event_id'],str(h))
        match=paired.get(key,[])
        for scenario,fee in [('CONSERVATIVE',.001),('BITUNIX_VIP0_TAKER_ASSUMPTION',.0006)]:
            r=get(i,side,h,fee)
            if fee==.001 and not np.isclose(r['net_fraction'],float(original['net_fraction']),rtol=0,atol=1e-14):raise ValueError('ORIGINAL_NET_CHANGED')
            entry_ref=float(a[r['entry_i'],1]);exit_ref=float(a[r['exit_i'],1])
            control_values=[get(int(v['control_i']),side,h,fee)['net_fraction'] for v in match]
            row=dict(scenario=scenario,stage=original['stage'],pattern=original['pattern'],side=side,stratum=original['stratum'],horizon=h,
                     event_id=original['event_id'],available_at=original['signal_available'],fee_per_side=fee,slip_per_side=.0005,
                     raw_price_fraction=side*(exit_ref-entry_ref)/entry_ref,fill_gross_fraction=r['gross_fraction'],
                     net_conservative_funding=r['net_fraction'],net_optimistic_funding=r['optimistic_fraction'],
                     exact_net_fraction=r['exact_net_fraction'],funding_low_per_btc=r['funding_low_per_btc'],
                     funding_high_per_btc=r['funding_high_per_btc'],missing_marks=r['missing_marks'],boundary_settlements=r['boundary_settlements'],
                     fees_per_btc=r['fees_per_btc'],entry=r['entry'],exit=r['exit'],
                     matched=bool(match),matched_control_mean=float(np.mean(control_values)) if match else None,
                     matched_excess=r['net_fraction']-float(np.mean(control_values)) if match else None,
                     statistical_status='PR50_NO_TESTABLE_UNCHANGED',funding_venue='BINANCE_USDM_PERPETUAL_NOT_BITUNIX')
            rows.append(row);groups[(scenario,original['stage'],original['pattern'],side,original['stratum'],h)].append(row)
    summaries=[]
    for key,rr in groups.items():
        scenario,stage,p,side,s,h=key;mm=[v for v in rr if v['matched']]
        summaries.append(dict(scenario=scenario,stage=stage,pattern=p,side=side,stratum=s,horizon=h,n=len(rr),matched=len(mm),
                              raw_gross_mean=np.mean([v['raw_price_fraction'] for v in rr]),
                              gross_after_slip_mean=np.mean([v['fill_gross_fraction'] for v in rr]),
                              net_all_mean=np.mean([v['net_conservative_funding'] for v in rr]),
                              net_paired_mean=np.mean([v['net_conservative_funding'] for v in mm]) if mm else None,
                              excess_paired_mean=np.mean([v['matched_excess'] for v in mm]) if mm else None,
                              interpretation='EXPLORATORY_NO_PRIMARY_REPLACEMENT' if s!='Q75' or h!=12 else 'PRIMARY_COHORT_COST_ASSUMPTION_ONLY'))
    return development,sensitivity,rows,summaries
