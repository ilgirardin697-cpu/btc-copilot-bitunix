"""Verifier for this unactivated research design; no shared live protocol state."""
import hashlib
import json
from pathlib import Path
PACKAGE=Path(__file__).parent
ROOT=PACKAGE.parents[1]
def normalized_hash(path):return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def verify():
    raw=(PACKAGE/'protocol_manifest.json').read_bytes().replace(b'\r\n',b'\n')
    expected=(PACKAGE/'protocol_manifest.sha256').read_text('ascii').strip()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('RESEARCH_PROTOCOL_MANIFEST_CHANGED')
    value=json.loads(raw)
    if value['protocol_version']!='BITMAN_ENTRY_FORWARD_RESEARCH_V0_DESIGN' or value['activation_at'] is not None:
        raise ValueError('RESEARCH_DESIGN_NOT_INACTIVE')
    for name,digest in value['sources'].items():
        if normalized_hash(PACKAGE/name)!=digest:raise ValueError('RESEARCH_DESIGN_SOURCE_CHANGED')
    for name,digest in value['inherited_math'].items():
        if normalized_hash(ROOT/name)!=digest:raise ValueError('INHERITED_MATH_CHANGED')
    return value
