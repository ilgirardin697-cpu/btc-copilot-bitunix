"""Local adapter for independently stored versioned backups and trusted anchors."""
from pathlib import Path
import hashlib,io,json,os,zipfile
from ..journal import canonical,digest,JournalError

def backup(ledger,destination,now):
    # The adapter is offline. A distinct path does NOT prove independent hardware.
    dest=Path(destination).resolve();root=ledger.root.resolve()
    if dest==root or root in dest.parents:raise ValueError('BACKUP_MUST_BE_OUTSIDE_WRITER_ROOT')
    dest.mkdir(parents=True,exist_ok=True);payload={'ledger.jsonl':ledger.path.read_bytes()}
    for sha in sorted(ledger.refs):payload['blobs/'+sha]=ledger.read_blob(sha)
    manifest=dict(registry=ledger.registry,count=ledger.count,tip=ledger.tip,created_at_ms=now,
                  entries={k:hashlib.sha256(v).hexdigest() for k,v in payload.items()})
    first=next((r['payload'] for r in ledger.records() if r['kind']=='SESSION_START'),{})
    cohort_hash=first.get('cohort',{}).get('cohort_hash') if first.get('cohort') else None
    manifest['cohort_hash']=cohort_hash
    payload['manifest.json']=canonical(manifest);buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(payload.items()):
            item=zipfile.ZipInfo(name,(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,raw)
    raw=buffer.getvalue();sha=hashlib.sha256(raw).hexdigest();name=str(now)+'-'+sha+'.zip';path=dest/name
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return dict(registry=ledger.registry,count=ledger.count,tip=ledger.tip,cohort_hash=cohort_hash,snapshot_sha256=sha,snapshot_name=name,created_at_ms=now,
                anchor_status='EXPORT_ONLY_REQUIRES_INDEPENDENT_TRUSTED_STORE_ACK')

def verify_archive(raw,anchor):
    if hashlib.sha256(raw).hexdigest()!=anchor['snapshot_sha256']:raise JournalError('EXTERNAL_BACKUP_HASH_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        if len(set(names))!=len(names) or any(n.startswith(('/', '\\')) or '\\' in n or ':' in n or '..' in Path(n).parts for n in names):raise JournalError('UNSAFE_BACKUP_PATH')
        if sum(i.file_size for i in z.infolist())>2_000_000_000:raise JournalError('BACKUP_SIZE_LIMIT')
        manifest=json.loads(z.read('manifest.json'))
        if any(manifest[k]!=anchor[k] for k in ('registry','tip','count','cohort_hash')):raise JournalError('BACKUP_ANCHOR_MISMATCH')
        if set(names)!=set(manifest['entries'])|{'manifest.json'}:raise JournalError('BACKUP_INVENTORY_CHANGED')
        out={n:z.read(n) for n in manifest['entries']}
        if any(hashlib.sha256(out[n]).hexdigest()!=h for n,h in manifest['entries'].items()):raise JournalError('BACKUP_ENTRY_CHANGED')
    return out

def restore(raw,anchor,destination):
    out=verify_archive(raw,anchor);dest=Path(destination)
    if dest.exists() and any(dest.iterdir()):raise ValueError('RESTORE_TO_EMPTY_NEW_ROOT_ONLY')
    dest.mkdir(parents=True,exist_ok=True)
    for name,body in out.items():
        path=dest/name;path.parent.mkdir(exist_ok=True,parents=True)
        with path.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    return dict(restored=True,source_anchor=anchor,never_modified_old_root=True)
