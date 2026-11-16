"""New registry only; V1 and both signal implementations stay byte-identical."""
from pathlib import Path
from datetime import datetime,timezone
import calendar,hashlib,json,sys
import numpy as np
from ..journal import canonical,digest

ROOT=Path(__file__).resolve().parent
VERSION='IGOD_H1_FORWARD_AUDIT_V2'
EXPECTED='df5476bbd984dd7f2dd23d52eaa956c9adc0429b7f785782a880cf4de99e4c10'
FILES=('registry.py','policy.json','incremental.py','codec.py','ledger.py','core.py','statistics.py','integrity.py','market.py','volume_probe.py')

def file_hash(path):
    raw=path.read_bytes().replace(b'\r\n',b'\n')
    if path.name=='registry.py':
        import re
        raw=re.sub(rb"(?m)^EXPECTED='[^']+'$",b"EXPECTED='<REGISTRY_HASH>'",raw)
    return hashlib.sha256(raw).hexdigest()

def qualified_environment():return sys.version_info[:3]==(3,12,12) and np.__version__=='2.3.5'

def verify(check_environment=False):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    if digest(manifest)!=EXPECTED:raise ValueError('V2_MANIFEST_INVALID')
    for name,sha in manifest['files'].items():
        if file_hash(ROOT/name)!=sha:raise ValueError('V2_SOURCE_CHANGED')
    for name,sha in manifest['dependencies'].items():
        if file_hash(ROOT.parents[7]/name)!=sha:raise ValueError('OLD_SOURCE_CHANGED')
    if check_environment and not qualified_environment():raise ValueError('PINNED_NUMERICAL_ENVIRONMENT_REQUIRED')
    return EXPECTED

def policy():return json.loads((ROOT/'policy.json').read_text())

def cohort(start_ms,approved_at_ms,approval_ref,source_sha,writer_id):
    if (type(start_ms) is not int or start_ms%3600000 or start_ms<=approved_at_ms or
        not approval_ref or not writer_id or len(source_sha)!=40 or any(c not in '0123456789abcdef' for c in source_sha)):
        raise ValueError('PRE_ACTIVATION_COHORT_APPROVAL_REQUIRED')
    dt=datetime.fromtimestamp(start_ms/1000,timezone.utc)
    end=dt.replace(year=dt.year+1,day=min(dt.day,calendar.monthrange(dt.year+1,dt.month)[1]))
    p=dict(registry=VERSION,registry_hash=EXPECTED,start_ms=start_ms,end_exclusive_ms=int(end.timestamp()*1000),
           approved_at_ms=approved_at_ms,approval_ref=approval_ref,source_sha=source_sha,writer_id=writer_id,
           window_basis='CONFIRMATION_CLOSE_UTC',duration='12_CALENDAR_MONTHS',activation_not_granted_by_tests=True)
    return dict(p,cohort_hash=digest(p))

def validate_cohort(value):
    p=dict(value);checksum=p.pop('cohort_hash',None)
    if digest(p)!=checksum or p['registry_hash']!=EXPECTED or p['registry']!=VERSION:raise ValueError('COHORT_SEAL_INVALID')
    expected=cohort(p['start_ms'],p['approved_at_ms'],p['approval_ref'],p['source_sha'],p['writer_id'])
    if expected!=value:raise ValueError('COHORT_WINDOW_CHANGED')
    return value

def eligible(close_ms,recorded_ms,activated_ms,cohort_value,pre_tokens=False,mode='OFFLINE_TEST'):
    # The first expected candle CLOSE is start_ms; no hidden open-time offset.
    return bool(mode=='FORWARD_SHADOW' and cohort_value['start_ms']<=close_ms<cohort_value['end_exclusive_ms'] and
                close_ms>activated_ms and 0<=recorded_ms-close_ms<=300000 and not pre_tokens)
