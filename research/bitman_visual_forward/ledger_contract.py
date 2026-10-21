"""In-memory append/replay contract only. No file journal, worker or live writer."""
import copy
import hashlib
import json
from .design import VERSION

TYPES={'ACTIVATION','WARMUP_ATTESTATION','BAR_ATTESTATION','SIGNAL_ASSESSMENT','ENTRY_PLAN',
    'PAPER_ENTRY','ENTRY_INVALIDATED','PAPER_EXIT','OUTCOME_MATURED','CENSORING','DATA_GAP','DATA_REVISION','RECOVERY','CONTROL_REFERENCE','COST_COMPLETION'}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def identifier(kind,activation_id,logical_key):return digest([VERSION,kind,activation_id,logical_key])
def verify(records,expected_tip=None):
    previous='0'*64;seen=set();created=-1
    for row in records:
        value={k:v for k,v in row.items() if k!='record_hash'}
        if (row.get('protocol_version')!=VERSION or row.get('schema_version')!=1 or row.get('record_type') not in TYPES
            or row.get('prev_hash')!=previous or row.get('record_hash')!=digest(value)
            or row.get('record_id')!=identifier(row.get('record_type'),row.get('activation_id'),row.get('logical_key'))
            or row.get('record_id') in seen or type(row.get('created_at')) is not int or row['created_at']<created):
            raise ValueError('RESEARCH_LEDGER_INVALID')
        seen.add(row['record_id']);previous=row['record_hash'];created=row['created_at']
    if expected_tip is not None and previous!=expected_tip:raise ValueError('RESEARCH_CHECKPOINT_MISMATCH')
    return previous

def append(records,kind,activation_id,logical_key,created_at,payload):
    tip=verify(records)
    if kind not in TYPES or type(created_at) is not int:raise ValueError('RESEARCH_RECORD_SCHEMA')
    body=copy.deepcopy(payload)
    rid=identifier(kind,activation_id,logical_key)
    for row in records:
        if row['record_id']==rid:
            if row['payload']!=body:raise ValueError('DUPLICATE_ID_CONFLICT')
            return copy.deepcopy(records)
    if records and created_at<records[-1]['created_at']:raise ValueError('CREATION_TIME_REGRESSION')
    row=dict(protocol_version=VERSION,schema_version=1,record_type=kind,record_id=rid,created_at=created_at,
        activation_id=activation_id,logical_key=logical_key,payload=body,prev_hash=tip)
    row['record_hash']=digest(row)
    return copy.deepcopy(records)+[row]
