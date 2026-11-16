"""Preregistered inclusive census contrast; no model or threshold fitting."""
from statistics import NormalDist
import math,json
import numpy as np
from ....inference import holm
from .registry import policy,ROOT,validate_cohort,eligible

def required_effective_n(sigma,effect=.001):
    if not np.isfinite(sigma) or sigma<=0:return None
    return math.ceil(((NormalDist().inv_cdf(1-.05/6)+NormalDist().inv_cdf(.8))*sigma/effect)**2)

def contrasts(y,labels,cells,weights=None):
    y=np.asarray(y,float);labels=np.asarray(labels,bool);cells=np.asarray(cells,int)
    w=np.ones(len(y)) if weights is None else np.asarray(weights,float)
    if y.shape!=(len(cells),2) or labels.shape!=(len(cells),6):raise ValueError('FIXED_SIX_CONTRASTS')
    out=np.full(6,np.nan);residual=np.full((len(y),2),np.nan);ng=int(cells.max())+1 if len(cells) else 0
    for s in range(2):
        finite=np.isfinite(y[:,s]);den=np.bincount(cells,weights=w*finite,minlength=ng)
        num=np.bincount(cells,weights=w*np.where(finite,y[:,s],0),minlength=ng)
        means=np.divide(num,den,out=np.full(ng,np.nan),where=den>0);residual[:,s]=y[:,s]-means[cells]
    # Pattern1 LONG/SHORT, pattern2 LONG/SHORT, pattern3 LONG/SHORT.
    for k in range(6):
        mask=labels[:,k]&np.isfinite(residual[:,k%2]);den=np.sum(w[mask])
        if den:out[k]=np.sum(w[mask]*residual[mask,k%2])/den
    return out,residual

def assess(y,labels,cells,days,first_day,last_day,minimum_n=None,coverage=0.,all_primary_auditable=False,replicates=None):
    p=policy()['statistical'];replicates=replicates or p['replicates']
    frozen=json.loads((ROOT/'power.json').read_text())['conditional_required_effective_n']
    if minimum_n is None:minimum_n=frozen
    if minimum_n!=frozen:raise ValueError('FROZEN_POWER_TARGET_CANNOT_BE_RELAXED')
    if type(minimum_n) is not int or minimum_n<1:raise ValueError('FROZEN_POWER_TARGET_REQUIRED')
    y=np.asarray(y,float);labels=np.asarray(labels,bool);cells=np.asarray(cells,int);days=np.asarray(days,int)
    if (np.diff(days)<0).any() or np.any(days<first_day) or np.any(days>last_day):raise ValueError('CALENDAR_RANGE_INVALID')
    point,residual=contrasts(y,labels,cells);n_days=last_day-first_day+1;rng=np.random.default_rng(p['seed'])
    estimates=np.full((replicates,6),np.nan)
    for b in range(replicates):
        starts=rng.integers(0,n_days,(n_days+6)//7)
        sampled=((starts[:,None]+np.arange(7))%n_days).ravel()[:n_days]
        day_weights=np.bincount(sampled,minlength=n_days);weights=day_weights[days-first_day]
        estimates[b]=contrasts(y,labels,cells,weights)[0]
    cell_counts=np.bincount(cells) if len(cells) else np.array([]);rows=[];pvalues=[]
    for k in range(6):
        mask=labels[:,k];values=residual[mask,k%2];valid=estimates[np.isfinite(estimates[:,k]),k]
        variance=np.var(valid,ddof=1) if len(valid)>1 else np.nan
        ess=min(float(len(values)),float(np.var(values,ddof=1)/variance)) if len(values)>1 and variance>0 else 0.
        blocks=len(set((days[mask]-first_day)//7));complete=bool(np.isfinite(values).all())
        baseline_ok=bool(len(values) and np.all(cell_counts[cells[mask]]>=p['minimum_baseline_cell_hours']))
        testable=bool(coverage>=.95 and all_primary_auditable and complete and baseline_ok and blocks>=20 and ess>=minimum_n and len(valid)>=replicates*.95)
        raw=(1+int(np.count_nonzero(valid-point[k]>=point[k])))/(len(valid)+1) if testable else 1.
        rows.append(dict(contrast=k,n=int(mask.sum()),effective_n=ess,occupied_blocks=blocks,required_effective_n=minimum_n,
                         mean_excess=float(point[k]) if np.isfinite(point[k]) else None,
                         ci95=np.quantile(valid,[.025,.975]).tolist() if len(valid)>1 else None,
                         valid_replicates=len(valid),testable=testable,p_for_holm=raw,
                         classification='INCONCLUSO' if testable else 'NO TESTABLE',validated=False))
        pvalues.append(raw)
    for row,adjusted in zip(rows,holm(pvalues)):row['holm_adjusted_p']=adjusted
    return dict(primary=rows,method='JOINT_CALENDAR_7DAY_BOOTSTRAP_INCLUSIVE_BASELINE',exploratory_never_promoted=True,
                no_virgin_holdout=True,signal_or_profitability_validation=False)

def evaluate_ledgers(ledgers,cohort,as_of_ms,replicates=None):
    from datetime import datetime,timezone
    from ....detect import PATTERNS
    validate_cohort(cohort)
    hours={};net={};disputed=set();candle_disputes=[];funding_disputes=[]
    for session_index,ledger in enumerate(ledgers):
        if ledger.registry!=cohort['registry_hash']:raise ValueError('EVALUATION_REGISTRY_MISMATCH')
        header=None
        for r in ledger.records():
            p=r['payload']
            if r['created_at_ms']>as_of_ms:continue
            if r['kind']=='SESSION_START':
                header=p
                if p['cohort']!=cohort:raise ValueError('EVALUATION_COHORT_MISMATCH')
            elif r['kind']=='HOUR':
                if header is None:raise ValueError('MISSING_SESSION_IDENTITY')
                key=p['open_ms']
                if key in hours:raise ValueError('DUPLICATE_COHORT_HOUR_ACROSS_SESSIONS')
                checked=eligible(p['close_ms'],p['recorded_ms'],header['activation'],cohort,mode=p['mode'])
                hours[key]=dict(p,eligible=bool(p['eligible'] and checked),session_source=session_index)
            elif r['kind']=='COSTED_OUTCOME' and p['hours']==12:net[p['open_ms']]=p
            elif r['kind']=='CANDLE_REVISION':candle_disputes.append((session_index,p['dispute_from_close_ms']))
            elif r['kind']=='FUNDING_REVISION':funding_disputes.append((session_index,p['correction']['time']))
    selected={k:v for k,v in hours.items() if v['eligible'] and v['mode']=='FORWARD_SHADOW'}
    for k,o in selected.items():
        if any(o['session_source']==s and o['close_ms']>=t for s,t in candle_disputes):disputed.add(k)
        if k in net and any(o['session_source']==s and net[k]['entry_reference']<=t<=net[k]['endpoint_reference'] for s,t in funding_disputes):disputed.add(k)
    cutoff=min(as_of_ms+1,cohort['end_exclusive_ms']);expected=max(0,(cutoff-cohort['start_ms']-1)//3600000+1)
    rows=[];masks=[];cells=[];days=[];lookup={};all_auditable=True
    for k,o in sorted(selected.items()):
        labels=np.zeros(6,bool)
        for event in o['profiles']['TURN22_FORWARD_V1']['events']:
            if 'Q75' in event['strata'] and event['primary_token_eligible']:
                labels[PATTERNS.index(event['pattern'])*2+(0 if event['side']==1 else 1)]=True
        valid=k in net and k not in disputed and all(net[k]['sides'][str(s)]['net_fraction'] is not None for s in (1,-1))
        if labels.any() and not valid:all_auditable=False
        if not valid:continue
        month=datetime.fromtimestamp(o['close_ms']/1000,timezone.utc).strftime('%Y-%m');cell=(month,o['regime'],o['volatility'])
        cells.append(lookup.setdefault(cell,len(lookup)));days.append(o['close_ms']//86400000);masks.append(labels)
        rows.append([net[k]['sides'][str(s)]['net_fraction'] for s in (1,-1)])
    result=dict(expected_hours=expected,on_time_hours=len(selected),net_complete_undisputed_hours=len(rows),
                coverage=len(selected)/expected if expected else None,net_coverage=len(rows)/expected if expected else None,
                disputed_hours=len(disputed),prospective_samples=len(selected),validated=False,
                status='NOT_MATURE',exploratory_not_promoted=True)
    if as_of_ms<cohort['end_exclusive_ms']+73*3600000:return result
    if not rows:
        result.update(status='NO TESTABLE',primary=[dict(contrast=k,p_for_holm=1,holm_adjusted_p=1,classification='NO TESTABLE') for k in range(6)]);return result
    result.update(assess(rows,masks,cells,days,cohort['start_ms']//86400000,(cohort['end_exclusive_ms']-1)//86400000,
                         coverage=min(result['coverage'],result['net_coverage']),all_primary_auditable=all_auditable,replicates=replicates))
    result['status']='INCONCLUSO' if all(r['testable'] for r in result['primary']) else 'NO TESTABLE';return result

def freeze_power(y,cells,provenance):
    y=np.asarray(y,float);_,r=contrasts(y,np.zeros((len(y),6),bool),cells)
    sigmas=[float(np.std(r[np.isfinite(r[:,s]),s],ddof=1)) for s in range(2)]
    sigma=max(policy()['statistical']['planning_sigma_floor'],2*max(sigmas))
    return dict(version='INCLUSIVE_CENSUS_POWER_V2',source=provenance,development_residual_sigma=sigmas,
                planning_sigma=sigma,conditional_required_effective_n=required_effective_n(sigma),
                mde_fraction=.001,alpha=.05,power=.8,minimum_occupied_blocks=20,
                dependence='future ESS uses joint event+baseline bootstrap; raw labels never count as independent n',
                limitation='historical marginal noise proxy plus predeclared4pp stress floor; not a guaranteed future/event-conditional variance bound',
                theoretical_annual_event_limit_per_contrast=math.ceil(8760/25),leap_year_event_limit_per_contrast=math.ceil(8784/25),confirmatory_power_feasible_in_fixed_12months=False,
                selection_or_profitability_evidence=False,prospective_samples=0)
