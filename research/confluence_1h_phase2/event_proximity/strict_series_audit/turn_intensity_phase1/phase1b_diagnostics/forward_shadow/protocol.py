"""Independent V1 registry. Existing frozen protocols are never refrozen here."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EXPECTED='6619b8ad176737de7b75c8d297ae7ab14b771879b8ad969161ba6b155ad325b9'
FILES=('protocols.json','protocol.py','models.py','observations.py','market.py','journal.py','observer.py','report.py')


def file_hash(path):
    raw=path.read_bytes().replace(b'\r\n',b'\n')
    if path.name=='protocol.py':
        import re
        raw=re.sub(rb"(?m)^EXPECTED='[^']+'$",b"EXPECTED='<REGISTRY_HASH>'",raw)
    return hashlib.sha256(raw).hexdigest()


def verify():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('PROTOCOL_MANIFEST_INVALID')
    for name in FILES:
        if file_hash(ROOT/name)!=manifest['files'][name]:raise ValueError('PROTOCOL_SOURCE_CHANGED')
    for name,checksum in manifest['dependencies'].items():
        if file_hash(ROOT.parents[6]/name)!=checksum:raise ValueError('FROZEN_DEPENDENCY_CHANGED')
    return EXPECTED


def config():return json.loads((ROOT/'protocols.json').read_text())
