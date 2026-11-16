"""Streaming append-only ledger and atomic public CAS; no silent journal repair."""
from pathlib import Path
import hashlib,json,os,uuid
from ..journal import canonical,digest,JournalError

class Ledger:
    def __init__(self,root,registry,writer_id):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.registry=registry;self.writer_id=writer_id
        self.path=self.root/'ledger.jsonl';self.blobs=self.root/'blobs';self.blobs.mkdir(exist_ok=True)
        self.quarantine=self.root/'quarantine';self.ids={};self.refs=set();self.count=0;self.tip='0'*64;self.last_time=0;self.failed=False
        self.lock=os.open(self.root/'writer.lock',os.O_RDWR|os.O_CREAT,0o600)
        if not os.fstat(self.lock).st_size:os.write(self.lock,b'0');os.fsync(self.lock)
        os.lseek(self.lock,0,0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for r in self.records():self._index(r)
            for sha in self.refs:self.read_blob(sha)
        except Exception:os.close(self.lock);self.lock=None;raise
    def records(self):
        previous='0'*64;seen=set();stamp=0
        if not self.path.exists():return
        with self.path.open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):raise JournalError('TRUNCATED_JOURNAL_NO_REPAIR')
                r=json.loads(line);checksum=r.pop('record_hash',None)
                if (r['schema']!=2 or r['registry']!=self.registry or r['writer_id']!=self.writer_id or r['prev_hash']!=previous or digest(r)!=checksum or
                    r['record_id'] in seen or r['created_at_ms']<stamp):raise JournalError('INVALID_CHAIN_NO_REPAIR')
                seen.add(r['record_id']);stamp=r['created_at_ms'];r['record_hash']=checksum;previous=checksum;yield r
    def _index(self,r):
        self.ids[r['record_id']]=(r['kind'],digest(r['payload']));self.tip=r['record_hash'];self.count+=1;self.last_time=r['created_at_ms']
        self.refs.update(r['blob_refs'])
    def append(self,kind,rid,payload,now,refs=()):
        if self.failed:raise JournalError('REOPEN_REQUIRED')
        signature=(kind,digest(payload))
        if rid in self.ids:
            if self.ids[rid]!=signature:raise JournalError('IMMUTABLE_ID_CONFLICT')
            return False
        if now<self.last_time:raise JournalError('CLOCK_BACKWARD')
        for sha in refs:self.read_blob(sha)
        r=dict(schema=2,registry=self.registry,writer_id=self.writer_id,kind=kind,record_id=rid,payload=payload,
               created_at_ms=int(now),prev_hash=self.tip,blob_refs=list(refs));r['record_hash']=digest(r);raw=canonical(r)+b'\n'
        try:
            with self.path.open('ab') as f:
                if f.write(raw)!=len(raw):raise OSError('SHORT_WRITE')
                f.flush();os.fsync(f.fileno())
        except Exception:self.failed=True;raise JournalError('SYNC_FAILED_REOPEN_REQUIRED') from None
        self._index(r);return True
    def read_blob(self,sha):
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise JournalError('BLOB_KEY_INVALID')
        raw=(self.blobs/sha).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise JournalError('REFERENCED_BLOB_INVALID_NO_REPAIR')
        return raw
    def put(self,raw,now):
        if self.failed:raise JournalError('REOPEN_REQUIRED')
        sha=hashlib.sha256(raw).hexdigest();path=self.blobs/sha
        if path.exists():
            original=path.read_bytes()
            if original==raw:return sha
            if sha in self.refs:raise JournalError('REFERENCED_BLOB_INVALID_NO_REPAIR')
            self.quarantine.mkdir(exist_ok=True);bad=hashlib.sha256(original).hexdigest();name=sha+'.'+uuid.uuid4().hex
            os.replace(path,self.quarantine/name)
            self.append('UNCOMMITTED_BLOB_QUARANTINED','ORPHAN:'+name,dict(expected=sha,fragment_sha=bad,bytes=len(original),quarantine_name=name),now)
        part=self.blobs/(sha+'.part.'+uuid.uuid4().hex)
        try:
            with part.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(part,path)
            if os.name!='nt':
                fd=os.open(self.blobs,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
        except Exception:self.failed=True;raise JournalError('BLOB_SYNC_FAILED') from None
        return sha
    def verify_anchor(self,anchor):
        if anchor['registry']!=self.registry or self.count<anchor['count']:raise JournalError('EXTERNAL_ANCHOR_TAIL_LOSS')
        if anchor['count']==0 and anchor['tip']=='0'*64:return True
        for i,r in enumerate(self.records(),1):
            if i==anchor['count']:
                if r['record_hash']!=anchor['tip']:raise JournalError('EXTERNAL_ANCHOR_CHANGED')
                return True
        raise JournalError('EXTERNAL_ANCHOR_MISSING')
    def quarantine_uncommitted_temps(self,now):
        for path in sorted(self.blobs.glob('*.part.*')):
            raw=path.read_bytes();name=path.name;self.quarantine.mkdir(exist_ok=True)
            os.replace(path,self.quarantine/name)
            self.append('UNCOMMITTED_TEMP_QUARANTINED','TEMP:'+name,dict(fragment_sha=hashlib.sha256(raw).hexdigest(),bytes=len(raw),quarantine_name=name),now)
    def close(self):
        if self.lock is not None:os.close(self.lock);self.lock=None
