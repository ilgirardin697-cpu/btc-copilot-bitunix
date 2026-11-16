"""Provisional60s wait; cannot qualify without reviewed real revision measurements."""
import hashlib,json
from ..market import candle_key,HOUR

OFFSETS=(0,15,30,60,120,240)

def schedule(now_ms):
    close=now_ms//HOUR*HOUR;delay=now_ms-close
    return dict(close_ms=close,open_ms=close-HOUR,delay_ms=delay,status='WAIT_PUBLICATION' if delay<60000 else 'WITHIN_TIMELY_WINDOW' if delay<=300000 else 'LATE_NOT_PRIMARY',
                provisional_wait_ms=60000,qualified_for_continuous_capture=False)

def revision_report(samples):
    groups={};real=True
    for sample in samples:
        real &= sample['origin']=='LIVE_PUBLIC_HTTPS';groups.setdefault(sample['close_ms'],[]).append(sample)
    complete=0;late_revisions=[];first_valid=[]
    for close,rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda r:r['received_ms']);offsets={r['offset_seconds'] for r in rows}
        if set(OFFSETS)<=offsets:complete+=1
        valid=[r for r in rows if r.get('valid',True)]
        first_valid.append(min((r['received_ms']-close for r in valid),default=float('inf')))
        previous=None
        for row in valid:
            current=candle_key(row['raw_candle'])
            if previous is not None and current!=previous and row['received_ms']-close>=60000:late_revisions.append(dict(close_ms=close,at_ms=row['received_ms']))
            previous=current
    qualified=bool(real and complete>=48 and not late_revisions and len(first_valid)>=48 and max(first_valid)<=60000)
    return dict(real_network_measurements=real and bool(samples),complete_closed_hours=complete,late_numeric_revisions=late_revisions,
                proposed_wait_ms=60000,qualification='OBSERVED_WINDOW_STABLE_REQUIRES_AUDIT' if qualified else 'NOT_QUALIFIED',
                continuous_capture_authorized=False,no_future_revision_guarantee=True,
                sample_sha256=hashlib.sha256(json.dumps(samples,sort_keys=True).encode()).hexdigest())
