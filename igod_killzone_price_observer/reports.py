"""Descriptive cycle-clustered monitoring; never self-publishes validated odds."""
from datetime import date,datetime
import numpy as np
from .features import NY,schedule
from .frozen import ANCHORS,CLASSES,scores,interval,class_calibration,ece_upper
from .observer import days,settings
from .journal import EvidenceError


def derive(records,now):
    protocol=settings()
    first,last=protocol['first_cycle'],protocol['last_cycle']
    calendar=list(days(first,last)); matured=[d for d in calendar if now>=schedule(d)['end']]
    ps={};outcomes={};receipts={};missed=[];failures=[]
    for r in records:
        if r.get('origin')!='PYTHON_BINANCE_SPOT_LIVE' or r.get('protocol_version')!=protocol['protocol']:
            raise EvidenceError('MIXED_COHORT_REJECTED')
        data=r['data'];kind=r['record_type']
        if kind=='PREDICTION':ps.setdefault(data['cycle'],{})[data['minute']]=r
        elif kind=='DURABILITY':receipts[data['prediction_id']]=r
        elif kind=='OUTCOME':outcomes[data['cycle']]=data
        elif kind=='MISSED':missed.append(data)
        elif kind=='FAILURE':failures.append(data)
    complete=[];excluded=[];price=[];prior=[];structure=[];labels=[]
    for d in matured:
        key=d.isoformat(); s=schedule(d);p=ps.get(key,{});o=outcomes.get(key)
        reasons=[]
        if any(m not in p for m in ANCHORS):reasons.append('MISSING_ANCHORS')
        if o is None:reasons.append('OUTCOME_PENDING_OR_UNAVAILABLE')
        elif o['outcome']['class_index']<0:reasons.append('AMBIGUOUS_TARGET_ORDER')
        elif not o['quality_pass']:reasons.append('SOURCE_REVISION_OR_MARKET_PARITY_FAILED')
        if not reasons:
            for m in ANCHORS:
                row=p[m];data=row['data'];receipt=receipts.get(row['record_id'])
                deadline=min(data['available_at']+120000,s['close']-1)
                if (receipt is None or not receipt['data']['eligible']
                    or receipt['data']['prediction_durable_at']>deadline
                    or receipt['data']['server_utc_upper_at_fsync']>deadline):
                    reasons.append('NO_TIMELY_DURABILITY_WITNESS');break
        if reasons:
            excluded.append(dict(cycle=key,reasons=reasons));continue
        complete.append(key);labels.append(o['outcome']['class_index'])
        price.append([p[m]['data']['probabilities'] for m in ANCHORS])
        prior.append([p[m]['data']['prior'] for m in ANCHORS])
        structure.append([p[m]['data']['structure'] for m in ANCHORS])
    n=len(complete);planned=len(calendar)
    result=dict(service=protocol['service'],protocol_version=protocol['protocol'],origin=protocol['origin'],
        generated_at=now,model_version=protocol['model_version'],trade_authority='NONE',mode='SHADOW_ONLY',
        probabilities_validated=False,tradingview_validation='NOT_ESTABLISHED_BY_THIS_BINANCE_COHORT',
        first_cycle=first,last_cycle=last,planned_cycles=planned,matured_calendar_cycles=len(matured),
        complete_cycles=n,coverage_planned=n/planned,coverage_matured=n/len(matured) if matured else None,
        prediction_records=sum(len(p) for p in ps.values()),durable_prediction_records=len(receipts),
        missed_anchors=len(missed),failed_attempt_records=len(failures),missed_details=missed,
        outcome_records=len(outcomes),ambiguous_cycles=sum(o['outcome']['class_index']<0 for o in outcomes.values()),
        revised_cycles=sum(not o['quality_pass'] for o in outcomes.values()),excluded=excluded,
        evidence='INSUFFICIENT',status='COHORT_NOT_FINISHED_NO_EARLY_APPROVAL',gate_failures=[],
        class_counts=[0,0,0],metrics=None,comparisons={},by_anchor=[],by_month=[])
    if not n:return result
    p=np.asarray(price); y=np.asarray(labels,int); refs={'PRIOR':np.asarray(prior),'STRUCTURE':np.asarray(structure)}
    b,ll=scores(p,y);cal=class_calibration(p,y)
    result['class_counts']=np.bincount(y,minlength=3).tolist()
    result['metrics']=dict(brier=float(b.mean()),logloss=float(ll.mean()),calibration=cal,
                           uncertainty_unit='CYCLE_BLOCK7_NOT5_INDEPENDENT_ANCHORS',
                           interval_status='DEFERRED_UNTIL_FIXED_COHORT_END_NO_REPEATED_TESTING')
    result['metrics']['by_class']=[dict(class_name=CLASSES[k],observed_cycles=int((y==k).sum()),
          brier=float(((p[:,:,k]-(y[:,None]==k))**2).mean()),
          conditional_logloss=float(ll[y==k].mean()) if (y==k).any() else None) for k in range(3)]
    for name,ref in refs.items():
        rb,rl=scores(ref,y);delta=(rb-b).mean(axis=1);ld=(rl-ll).mean(axis=1)
        result['comparisons'][name]=dict(brier=float(rb.mean()),logloss=float(rl.mean()),
            brier_gain=float(delta.mean()),brier_gain_ci97_5=None,
            logloss_gain=float(ld.mean()),logloss_gain_ci95=None)
    for i,minute in enumerate(ANCHORS):
        result['by_anchor'].append(dict(minute=minute,cycles=n,brier=float(b[:,i].mean()),logloss=float(ll[:,i].mean()),
              gains={name:float((scores(ref,y)[0][:,i]-b[:,i]).mean()) for name,ref in refs.items()}))
    for month in sorted(set(day[:7] for day in complete)):
        mask=np.array([day.startswith(month) for day in complete]);month_n=int(mask.sum())
        result['by_month'].append(dict(month=month,cycles=month_n,brier=float(b[mask].mean()),
           logloss=float(ll[mask].mean()),eligible_month=month_n>=10,
           gains={name:float((scores(ref[mask],y[mask])[0]-b[mask]).mean()) for name,ref in refs.items()}))
    final_time=schedule(date.fromisoformat(last))['end']
    if now<final_time:return result
    if n<150 or min(result['class_counts'])<30 or n<.95*planned:
        result['status']='INSUFFICIENT_SAMPLE_OR_COVERAGE';return result
    failures=[]
    result['metrics']['interval_status']='FIXED_COHORT_FINAL_CYCLE_BLOCK_INTERVALS'
    for name,ref in refs.items():
        comparison=result['comparisons'][name]
        rb,rl=scores(ref,y)
        comparison['brier_gain_ci97_5']=interval((rb-b).mean(axis=1),.975)
        comparison['logloss_gain_ci95']=interval((rl-ll).mean(axis=1))
        if comparison['brier_gain_ci97_5'][0]<=0:failures.append(name+':BRIER')
        if comparison['logloss_gain']<0 or comparison['logloss_gain_ci95'][0]<-.01:failures.append(name+':LOGLOSS')
        if any(a['gains'][name]<0 for a in result['by_anchor']):failures.append(name+':ANCHOR_STABILITY')
        for k in range(3):
            truth=y[:,None]==k
            delta=((ref[:,:,k]-truth)**2-(p[:,:,k]-truth)**2).mean(axis=1)
            if delta.mean()<0 or interval(delta)[0]<-.01:failures.append(name+':CLASS_'+str(k))
    upper=ece_upper(p,y);result['metrics']['calibration']['class_ece_upper95']=upper
    if cal['macro_ece']>.05 or max(cal['class_ece'])>.08 or max(upper)>.10:failures.append('CALIBRATION')
    eligible=[m for m in result['by_month'] if m['eligible_month']]
    good=sum(all(v>0 for v in m['gains'].values()) for m in eligible)
    if len(eligible)<5 or good<2*len(eligible)/3:failures.append('MONTHLY_STABILITY')
    result['gate_failures']=failures
    result['evidence']='SUFFICIENT_FIXED_COHORT_FOR_REVIEW'
    result['status']='FIXED_COHORT_FAILED' if failures else 'STATISTICAL_PASS_INDEPENDENT_REVIEW_REQUIRED'
    return result
