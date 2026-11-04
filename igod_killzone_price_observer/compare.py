"""Offline comparison of actual exports, never ingestion into the Binance cohort."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import numpy as np

from .frozen import predict,verify_freeze
from .journal import EvidenceError

PREFIX='IGOD_PRICE_RADAR_V1='


def compare_export(raw,binance_records):
    frozen=verify_freeze();parsed=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    lookup={r['data']['available_at']:r['data'] for r in binance_records if r['record_type']=='PREDICTION'}
    rows=[];seen=set()
    fields={'protocol','protocol_hash','version','available_at','emitted_at','minute','status','origin','features','research_probabilities'}
    for r in parsed:
        if set(r)=={'Fecha','Mensaje'}:external,message=r['Fecha'],r['Mensaje']
        elif set(r)=={'Date','Message'}:external,message=r['Date'],r['Message']
        else:raise EvidenceError('TV_CSV_SCHEMA_REJECTED')
        if PREFIX not in message:raise EvidenceError('TV_UNEXPECTED_MESSAGE_REJECTED')
        p=json.loads(message.split(PREFIX,1)[1])
        if (set(p)!=fields or p['protocol']!='IGOD_KILLZONE_PRICE_FORWARD_V1'
            or p['protocol_hash']!=frozen['original_tv_protocol_sha256'] or p['version']!=frozen['model_version']
            or p['origin']!='PINE_REALTIME_UNATTESTED' or p['status']!='EXPERIMENTAL_NOT_VALIDATED'
            or any(type(p[k]) is not int for k in ('available_at','emitted_at','minute'))
            or len(p['features'])!=6 or len(p['research_probabilities'])!=3
            or any(type(v) not in (int,float) for v in p['features']+p['research_probabilities'])):
            raise EvidenceError('TV_PAYLOAD_SCHEMA_REJECTED')
        x=np.array(p['features'],float);prob=np.array(p['research_probabilities'],float)
        if not np.isfinite(x).all() or not np.isfinite(prob).all() or np.any(prob<0) or np.any(prob>1) or abs(prob.sum()-1)>1e-10:
            raise EvidenceError('TV_NUMERIC_SCHEMA_REJECTED')
        t=datetime.fromisoformat(external)
        outside_ms=int(t.timestamp()*1000) if t.utcoffset() is not None else None
        reference=lookup.get(p['available_at'])
        inferred=predict(x);row=dict(available_at=p['available_at'],emitted_at=p['emitted_at'],
            external_original=external,external_utc_ms=outside_ms,minute=p['minute'],
            external_before_available=None if outside_ms is None else outside_ms<p['available_at'],
            emission_before_available=p['emitted_at']<p['available_at'],
            conditional_inference_error=float(abs(inferred-prob).max()),
            binance_overlap=reference is not None,duplicate_asof=p['available_at'] in seen)
        if reference:
            row.update(feature_error=float(abs(x-reference['features']).max()),
                feature_match=bool(np.allclose(x,reference['features'],rtol=1e-8,atol=1e-8)),
                probability_error=float(abs(prob-reference['probabilities']).max()),
                binance_emitted_at=reference['emitted_at'])
        seen.add(p['available_at']);rows.append(row)
    return dict(source='ACTUAL_OWNER_PROVIDED_TRADINGVIEW_EXPORT_UNATTESTED',
        original_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,actual_pine_records=len(rows),
        overlapping_binance_predictions=sum(r['binance_overlap'] for r in rows),
        feature_mismatches=sum(r.get('feature_match') is False for r in rows),
        timestamp_anomalies=sum(bool(r['external_before_available']) or r['emission_before_available'] for r in rows),
        conditional_inference_passes=sum(r['conditional_inference_error']<=1e-10 for r in rows),
        status='INSUFFICIENT_OVERLAP' if not any(r['binance_overlap'] for r in rows) else 'COMPARISON_ONLY_EXTERNAL_REVIEW_REQUIRED',
        tradingview_cohort_imported=False,binance_cohort_modified=False,platform_parity_certified=False)


def save_comparison(raw,records,directory,clock):
    # Validate all fields before retaining a copy; no arbitrary CSV/secret payload.
    result=compare_export(raw,records)
    folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
    sha=result['original_sha256'];original=folder/(sha+'.csv')
    if original.exists() and original.read_bytes()!=raw:raise EvidenceError('TV_EXPORT_CONFLICT')
    if not original.exists():
        import os
        with original.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    result['imported_at']=clock.now_ms()
    # Imported_at is NOT a historical emission/receipt timestamp.
    return result


def main():
    import argparse
    from .clock import Clock
    from .journal import Store
    p=argparse.ArgumentParser(description='Offline actual TV export comparison, never forward ingestion')
    p.add_argument('--logs',required=True);p.add_argument('--evidence-copy',required=True);p.add_argument('--out-dir',required=True)
    args=p.parse_args();records=Store.inspect(Path(args.evidence_copy))
    result=save_comparison(Path(args.logs).read_bytes(),records,Path(args.out_dir),Clock())
    out=Path(args.out_dir)/(result['original_sha256']+'.comparison.json')
    if not out.exists():
        with out.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],actual_pine_records=result['actual_pine_records'],
        overlap=result['overlapping_binance_predictions'],feature_mismatches=result['feature_mismatches'],
        platform_parity_certified=False,binance_cohort_modified=False)))


if __name__=='__main__':main()
