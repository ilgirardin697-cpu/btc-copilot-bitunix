"""V1 identity and integrity checks. A rule change requires a separate version."""
import hashlib
import json
from pathlib import Path
import re

VERSION = 'BITMAN_WEEKLY_FORWARD_V1'
SCHEMA = 1
HOUR = 3600000
WEEK = 168*HOUR
MONDAY = 4*24*HOUR
MARGIN = 5*60*1000
MODELS = ('STRICT_SAME_WEEK','SOURCE_ALIGNED_LAG_LE1','SOURCE_ALIGNED_LAG_LE2')
KINDS = ('REACCELERATION_UP','REACCELERATION_DOWN','ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION')
VENUE = 'BINANCE_USDM_PERPETUAL'
ROOT = Path(__file__).resolve().parent
EXPECTED_HASH = 'd4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    data=Path(path).read_bytes().replace(b'\r\n',b'\n')
    if Path(path).name=='protocol.py':
        # Bind the verifier itself without a circular embedded-hash dependency.
        data=re.sub(rb"(?m)^EXPECTED_HASH = '[0-9a-f]{64}'$",b"EXPECTED_HASH = '<PROTOCOL_HASH>'",data)
    return hashlib.sha256(data).hexdigest()


def verify():
    definition=json.loads((ROOT/'protocol_v1.json').read_text('utf-8'))
    if digest(definition)!=EXPECTED_HASH or definition['protocol_version']!=VERSION:
        raise ValueError('OBSERVER_PROTOCOL_INVALID')
    for name,expected in definition['sources'].items():
        if file_hash(ROOT/name)!=expected:
            raise ValueError('OBSERVER_PROTOCOL_INVALID')
    for name,expected in definition['dependencies'].items():
        if file_hash(ROOT.parent/name)!=expected:
            raise ValueError('OBSERVER_PROTOCOL_INVALID')
    return definition


def week_start(stamp):
    return (int(stamp)-MONDAY)//WEEK*WEEK+MONDAY
