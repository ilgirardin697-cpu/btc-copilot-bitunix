"""Comparison for genuine future Pine Logs. A scalar mirror is never platform evidence."""
import argparse
from datetime import date
import json
from pathlib import Path
import numpy as np
from .core import predict
from .forward import PREFIX,validate_payload,load_archives
from .features import reference_vectors,NY
from datetime import datetime,timezone


def compare(text,h=None,m=None):
    rows=[];cache={}
    for line in text.splitlines():
        if PREFIX not in line:continue
        payload=json.loads(line.split(PREFIX,1)[1]);day=validate_payload(payload)
        expected=predict(payload['features']);pe=float(abs(expected-payload['research_probabilities']).max())
        row=dict(cycle=day,available_at=payload['available_at'],minute=payload['minute'],
                 probability_max_error=pe,probability_pass=pe<=1e-10,market_feature_pass=None)
        if h is not None and m is not None:
            try:
                if day not in cache:cache[day]=reference_vectors(date.fromisoformat(day),h,m)
                ref=cache[day][payload['minute']];actual=np.array(payload['features'])
                row['market_feature_error']=abs(ref-actual).tolist()
                row['market_feature_pass']=bool(np.allclose(ref,actual,rtol=1e-8,atol=1e-8))
            except ValueError as exc:row['market_feature_status']=str(exc)
        rows.append(row)
    complete=[]
    for day in sorted(set(r['cycle'] for r in rows)):
        anchors={r['minute'] for r in rows if r['cycle']==day and r['probability_pass'] and r['market_feature_pass'] is True}
        if all(i in anchors for i in (0,15,30,45,59)):complete.append(day)
    return dict(origin='USER_PROVIDED_PINE_LOGS_NOT_CRYPTOGRAPHICALLY_ATTESTED',actual_log_records=len(rows),
        complete_five_anchor_cycles=complete,rows=rows,compilation='REQUIRES_OWNER_REVIEW',
        realtime_reload_comparison='REQUIRES_SEPARATE_CAPTURE_AND_REVIEW',publication_enabled=False,
        status='NO_ACTUAL_PRICE_PINE_LOGS' if not rows else 'EXTERNAL_REVIEW_REQUIRED_NO_AUTOMATIC_PARITY_CERTIFICATION')


def main():
    p=argparse.ArgumentParser();p.add_argument('logs');p.add_argument('--manifest');p.add_argument('--out',required=True);args=p.parse_args()
    h=m=None
    if args.manifest:h,m,_=load_archives(args.manifest)
    r=compare(Path(args.logs).read_text(encoding='utf-8-sig'),h,m)
    Path(args.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in r.items() if k!='rows'}))


if __name__=='__main__':main()
