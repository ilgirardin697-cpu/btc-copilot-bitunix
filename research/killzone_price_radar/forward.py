"""Local manual capture and append-only outcomes. No receiver, scheduler or live service."""
import argparse
from datetime import date,datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from .core import HERE,ANCHORS,canonical,read_json,verify_freeze,predict,structure_predict,scores,interval,class_calibration,ece_upper,block_indices
from .features import NY,schedule,reference_vectors,final_label

PREFIX='IGOD_PRICE_RADAR_V1='


def now_ms():return time.time_ns()//1000000


def digest(r):return hashlib.sha256(canonical(r)).hexdigest()


def validate_payload(p):
    fields={'protocol','protocol_hash','version','available_at','emitted_at','minute','status','origin','features','research_probabilities'}
    if set(p)!=fields:raise ValueError('UNEXPECTED_FIELDS_NO_SECRET_PAYLOAD_ACCEPTED')
    frozen=verify_freeze()
    if p['protocol']!='IGOD_KILLZONE_PRICE_FORWARD_V1' or p['protocol_hash']!=frozen['protocol_sha256'] or p['version']!=frozen['model_version']:
        raise ValueError('WRONG_PROTOCOL_OR_MODEL')
    if p['status']!='EXPERIMENTAL_NOT_VALIDATED' or p['origin']!='PINE_REALTIME_UNATTESTED':
        raise ValueError('WRONG_RESEARCH_SEMANTICS')
    if type(p['available_at']) is not int or type(p['emitted_at']) is not int or type(p['minute']) is not int:
        raise ValueError('TIMESTAMP_TYPE')
    t=datetime.fromtimestamp(p['available_at']/1000,timezone.utc).astimezone(NY)
    if t.hour!=5 or t.minute!=p['minute'] or t.second or t.microsecond or p['emitted_at']<p['available_at']:
        raise ValueError('NOT_A_CLOSED_FORECAST_MINUTE')
    x=np.asarray(p['features'],float);prob=np.asarray(p['research_probabilities'],float)
    if x.shape!=(6,) or not np.isfinite(x).all() or abs(x[0]-p['minute']/60)>1e-12 or not 0<=x[1]<=1 or x[3]<0 or x[5]<=0:
        raise ValueError('FEATURE_SCHEMA')
    if prob.shape!=(3,) or not np.isfinite(prob).all() or np.any(prob<0) or np.any(prob>1) or abs(prob.sum()-1)>1e-10:
        raise ValueError('PROBABILITY_SCHEMA')
    canonical(p)
    return t.date().isoformat()


def read(path):
    p=Path(path)
    if not p.exists():return []
    raw=p.read_bytes()
    if raw and not raw.endswith(b'\n'):raise ValueError('JOURNAL_INVALID_NO_REPAIR')
    result=[];tip='0'*64;ids=set();last_received=0
    for line in raw.splitlines():
        r=json.loads(line);stored=r.pop('record_hash')
        if r['record_type'] not in ('PREDICTION','OUTCOME') or r['prev_hash']!=tip or digest(r)!=stored or r['record_id'] in ids or r['received_at']<last_received:
            raise ValueError('JOURNAL_INVALID_NO_REPAIR')
        if r['record_type']=='PREDICTION':validate_payload(r['payload'])
        r['record_hash']=stored;result.append(r);ids.add(r['record_id']);tip=stored;last_received=r['received_at']
    return result


def append_record(path,row,existing):
    row=dict(row,prev_hash=existing[-1]['record_hash'] if existing else '0'*64)
    row['record_hash']=digest(row)
    with Path(path).open('ab') as f:
        f.write(canonical(row)+b'\n');f.flush();os.fsync(f.fileno())
    return row


def capture(path,payload):
    day=validate_payload(payload);received=now_ms();records=read(path)
    if payload['emitted_at']>received:raise ValueError('FUTURE_EMISSION')
    rid=payload['version']+':'+str(payload['available_at'])
    for old in records:
        if old['record_id']==rid:
            a=dict(old['payload']);b=dict(payload);a.pop('emitted_at');b.pop('emitted_at')
            if canonical(a)!=canonical(b):raise ValueError('CONFLICTING_FORECAST_NO_REWRITE')
            return False
    s=schedule(date.fromisoformat(day));protocol=read_json('protocol.json');cohort=protocol['prospective'];reasons=[]
    if not cohort['first_cycle']<=day<=cohort['last_cycle']:reasons.append('OUTSIDE_FROZEN_COHORT')
    if received>=s['close']:reasons.append('CAPTURE_AFTER_LABEL_WINDOW_STARTED')
    if received-payload['available_at']>cohort['capture_latency_ms_max']:reasons.append('LATE_CAPTURE_NOT_FORWARD')
    expected=predict(payload['features']);error=float(abs(expected-payload['research_probabilities']).max())
    if error>1e-10:reasons.append('ACTUAL_PROBABILITY_PARITY_MISMATCH')
    row=dict(record_type='PREDICTION',record_id=rid,cycle=day,received_at=received,payload=payload,
        eligible_capture=not reasons,ineligible_reasons=reasons,probability_parity_max_error=error,
        python_probabilities=expected.tolist(),prior_probabilities=read_json('frozen_PRIOR.json'),
        structure_probabilities=structure_predict(np.array(payload['features']),read_json('artifacts/frozen_STRUCTURE.json')).tolist(),
        origin_assurance='LOCAL_CAPTURE_OF_UNATTESTED_PINE_LOG_EXTERNAL_REVIEW_REQUIRED',
        model_sha256=verify_freeze()['model_sha256'])
    append_record(path,row,records);return True


def settle(path,day,h,m,source_hashes):
    records=read(path);rid=verify_freeze()['model_version']+':OUTCOME:'+day
    if any(r['record_id']==rid for r in records):return False
    outcome=final_label(date.fromisoformat(day),h,m,now_ms())
    ref=reference_vectors(date.fromisoformat(day),h,m);rows=[r for r in records if r['record_type']=='PREDICTION' and r['cycle']==day]
    if not rows:raise ValueError('NO_CAPTURED_PREDICTIONS')
    errors={r['record_id']:float(abs(ref[r['payload']['minute']]-r['payload']['features']).max()) for r in rows}
    verified={r['record_id']:bool(np.allclose(ref[r['payload']['minute']],r['payload']['features'],rtol=1e-8,atol=1e-8)) for r in rows}
    row=dict(record_type='OUTCOME',record_id=rid,cycle=day,received_at=now_ms(),outcome=outcome,
        source_hashes=source_hashes,feature_errors=errors,feature_verified=verified,
        authority='NONE',label_role='OBSERVED_POST06_FIRST_TOUCH_NOT_TRADING_RESULT')
    append_record(path,row,records);return True


def cohort(records):
    p=read_json('protocol.json')['prospective'];predictions={};outcomes={}
    for r in records:
        if not p['first_cycle']<=r['cycle']<=p['last_cycle']:continue
        if r['record_type']=='PREDICTION':predictions.setdefault(r['cycle'],{})[r['payload']['minute']]=r
        else:outcomes[r['cycle']]=r
    days=[];y=[];price=[];prior=[];structure=[];excluded=[]
    for day,rows in sorted(predictions.items()):
        label=outcomes.get(day)
        if label is None or label['outcome']['class_index']<0:
            excluded.append(dict(cycle=day,reason='NO_MATURED_VERIFIED_UNAMBIGUOUS_LABEL'));continue
        if not all(i in rows for i in ANCHORS):
            excluded.append(dict(cycle=day,reason='MISSING_ANCHORS'));continue
        if not all(rows[i]['eligible_capture'] and label['feature_verified'].get(rows[i]['record_id'],False) for i in ANCHORS):
            excluded.append(dict(cycle=day,reason='INELIGIBLE_OR_MARKET_PARITY_FAILED'));continue
        days.append(day);y.append(label['outcome']['class_index'])
        price.append([rows[i]['python_probabilities'] for i in ANCHORS])
        prior.append([rows[i]['prior_probabilities'] for i in ANCHORS])
        structure.append([rows[i]['structure_probabilities'] for i in ANCHORS])
    return days,np.array(y),np.array(price),np.array(prior),np.array(structure),excluded


def evaluate(records):
    days,y,p,prior,structure,excluded=cohort(records);protocol=read_json('protocol.json');co=protocol['prospective']
    result=dict(decision='B',conclusion='PROMETEDOR PERO PENDIENTE DE DATOS PROSPECTIVOS',
        captured_records=sum(r['record_type']=='PREDICTION' for r in records),eligible_complete_cycles=len(y),
        excluded=excluded,gate_failures=[],prospective_window=[co['first_cycle'],co['last_cycle']],
        publication_enabled=False,actual_tv_compile_realtime_reload='REQUIRES_INDEPENDENT_REVIEW')
    if len(y):
        b,l=scores(p,y);result.update(brier=float(b.mean()),logloss=float(l.mean()),calibration=class_calibration(p,y))
    if now_ms()<schedule(date.fromisoformat(co['last_cycle']))['end']:
        result['status']='COHORT_NOT_FINISHED_NO_EARLY_APPROVAL';return result
    planned=(date.fromisoformat(co['last_cycle'])-date.fromisoformat(co['first_cycle'])).days+1
    if len(y)<co['minimum_complete_cycles'] or (np.bincount(y,minlength=3).min() if len(y) else 0)<co['minimum_per_outcome_class'] or len(y)<.95*planned:
        result['status']='INSUFFICIENT_PROSPECTIVE_SAMPLE_OR_COVERAGE';return result
    ownb,ownl=scores(p,y);refs={'PRIOR':prior,'STRUCTURE':structure}
    result['comparisons']={}
    for name,ref in refs.items():
        rb,rl=scores(ref,y);gain=(rb-ownb).mean(axis=1);lgain=(rl-ownl).mean(axis=1)
        bci=interval(gain,.975);lci=interval(lgain)
        result['comparisons'][name]=dict(brier_gain=float(gain.mean()),brier_ci97_5=bci,logloss_gain=float(lgain.mean()),logloss_ci95=lci)
        if bci[0]<=0:result['gate_failures'].append(name+':BRIER_PRIMARY')
        if lgain.mean()<0 or lci[0]<-.01:result['gate_failures'].append(name+':LOGLOSS')
        if np.any((rb-ownb).mean(axis=0)<0):result['gate_failures'].append(name+':ANCHOR_INSTABILITY')
        for k in range(3):
            truth=y[:,None]==k;d=((ref[:,:,k]-truth)**2-(p[:,:,k]-truth)**2).mean(axis=1)
            if d.mean()<0 or interval(d)[0]<-.01:result['gate_failures'].append(name+':CLASS_'+str(k))
    cal=class_calibration(p,y);upper=ece_upper(p,y)
    if cal['macro_ece']>.05 or max(cal['class_ece'])>.08 or max(upper)>.10:result['gate_failures'].append('CALIBRATION')
    result['class_ece_upper95']=upper
    months=sorted(set(d[:7] for d in days));eligible=positive=0
    for month in months:
        mask=np.array([d.startswith(month) for d in days])
        if mask.sum()<10:continue
        eligible+=1
        positive+=all(float((scores(ref[mask],y[mask])[0]-ownb[mask]).mean())>0 for ref in refs.values())
    if eligible<5 or positive<2*eligible/3:result['gate_failures'].append('MONTHLY_STABILITY')
    result['status']='FIXED_COHORT_FAILED' if result['gate_failures'] else 'STATISTICAL_GATES_PASSED_PARITY_REVIEW_STILL_REQUIRED'
    if result['gate_failures']:
        result['decision']='C';result['conclusion']='DESCARTADO POR CRITERIOS PROSPECTIVOS PREDECLARADOS'
    # A cannot be self-certified by an untrusted input file or a switch; reviewed release needed.
    return result


def load_archives(manifest_path):
    from ..killzone_probability_radar.data import archive_rows
    path=Path(manifest_path);manifest=json.loads(path.read_text(encoding='utf-8'));groups={'1h':[],'1m':[]};hashes={}
    for row in manifest['archives']:
        interval=row['interval'];month=row['month'];name=f'BTCUSDT-{interval}-{month}.zip'
        expected_url=f'https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/{interval}/{name}'
        if interval not in groups or row['filename']!=name or row['url']!=expected_url or Path(name).name!=name:
            raise ValueError('OFFICIAL_PUBLIC_SOURCE_REQUIRED')
        raw=(path.parent/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('OFFICIAL_SOURCE_HASH_MISMATCH')
        groups[interval].append(archive_rows(path.parent/name,interval,month));hashes[name]=row['sha256']
    arrays=[]
    for key in ('1h','1m'):
        if not groups[key]:raise ValueError('MISSING_SOURCE_INTERVAL')
        a=np.concatenate(groups[key]);a=a[np.argsort(a[:,0])]
        if np.any(np.diff(a[:,0])<=0):raise ValueError('DUPLICATE_SOURCE')
        arrays.append(a)
    return *arrays,hashes


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    for cmd in ('capture','status','settle'):
        q=sub.add_parser(cmd);q.add_argument('--journal',required=True)
        if cmd=='capture':q.add_argument('--logs',required=True)
        if cmd=='settle':q.add_argument('--date',required=True);q.add_argument('--manifest',required=True)
    args=p.parse_args();destination=Path(args.journal).resolve();root=HERE.parent/'cache'
    if not destination.is_relative_to(root.resolve()):raise ValueError('LOCAL_RESEARCH_CACHE_ONLY_NO_PRODUCTION_STORAGE')
    if args.command=='capture':
        destination.parent.mkdir(parents=True,exist_ok=True);n=0
        for line in Path(args.logs).read_text(encoding='utf-8-sig').splitlines():
            if PREFIX in line:n+=capture(destination,json.loads(line.split(PREFIX,1)[1]))
        print(json.dumps(dict(added=n,records=len(read(destination)))))
    elif args.command=='settle':
        h,m,hashes=load_archives(args.manifest);print(json.dumps(dict(added=settle(destination,args.date,h,m,hashes))))
    else:print(json.dumps(evaluate(read(destination)),ensure_ascii=False))


if __name__=='__main__':main()
