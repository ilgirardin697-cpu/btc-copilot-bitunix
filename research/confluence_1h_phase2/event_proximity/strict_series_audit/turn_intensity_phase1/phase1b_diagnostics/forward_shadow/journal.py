"""Single-writer fsync hash chain and immutable content-addressed public blobs."""
import hashlib,json,os
from pathlib import Path


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


class JournalError(RuntimeError):pass


class Journal:
    def __init__(self,root,registry_hash):
        self.root=Path(root);self.registry=registry_hash;self.records=[];self.ids={};self.failed=False;self.lock=None
        self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'observations.jsonl';self.blobs=self.root/'blobs';self.blobs.mkdir(exist_ok=True)
        try:
            self.lock=os.open(self.root/'writer.lock',os.O_RDWR|os.O_CREAT,0o600)
            if os.fstat(self.lock).st_size==0:os.write(self.lock,b'0');os.fsync(self.lock)
            os.lseek(self.lock,0,os.SEEK_SET)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.reload()
        except Exception:
            if self.lock is not None:os.close(self.lock);self.lock=None
            raise JournalError('JOURNAL_INVALID_OR_WRITER_BUSY') from None

    def reload(self):
        rows=[];ids={};previous='0'*64
        raw=self.path.read_bytes() if self.path.exists() else b''
        if raw and not raw.endswith(b'\n'):raise JournalError('JOURNAL_TRUNCATED_NO_REPAIR')
        for line in raw.splitlines():
            row=json.loads(line)
            checksum=row.pop('record_hash',None)
            if row.get('prev_hash')!=previous or digest(row)!=checksum or row.get('registry_hash')!=self.registry or row.get('schema_version')!=1:
                raise JournalError('JOURNAL_CHAIN_INVALID')
            if row['record_id'] in ids or (rows and row['created_at_ms']<rows[-1]['created_at_ms']):raise JournalError('JOURNAL_ORDER_OR_DUPLICATE')
            row['record_hash']=checksum;rows.append(row);ids[row['record_id']]=row;previous=checksum
        # A prior complete write with uncertain sync is accepted only after sync.
        if self.path.exists():
            with self.path.open('ab') as stream:stream.flush();os.fsync(stream.fileno())
        self.records,self.ids=rows,ids

    @property
    def tip(self):return self.records[-1]['record_hash'] if self.records else '0'*64

    def blob(self,raw):
        if self.failed:raise JournalError('JOURNAL_REOPEN_REQUIRED')
        checksum=hashlib.sha256(raw).hexdigest();path=self.blobs/(checksum+'.json')
        if path.exists():
            if path.read_bytes()!=raw:raise JournalError('PUBLIC_BLOB_TAMPERED')
        else:
            try:
                with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            except Exception:self.failed=True;raise JournalError('PUBLIC_BLOB_WRITE_FAILED') from None
        return checksum

    def read_blob(self,checksum):
        if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):raise JournalError('INVALID_BLOB_HASH')
        raw=(self.blobs/(checksum+'.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=checksum:raise JournalError('PUBLIC_BLOB_TAMPERED')
        return raw

    def append(self,kind,record_id,payload,now):
        if self.failed:raise JournalError('JOURNAL_REOPEN_REQUIRED')
        if record_id in self.ids:
            old=self.ids[record_id]
            if old['kind']!=kind or old['payload']!=payload:raise JournalError('IMMUTABLE_RECORD_CONFLICT')
            return False
        if self.records and now<self.records[-1]['created_at_ms']:raise JournalError('CLOCK_MOVED_BACKWARD')
        row=dict(schema_version=1,registry_hash=self.registry,kind=kind,record_id=record_id,
                 created_at_ms=int(now),prev_hash=self.tip,payload=payload)
        row['record_hash']=digest(row);raw=canonical(row)+b'\n'
        try:
            with self.path.open('ab') as stream:
                if stream.write(raw)!=len(raw):raise OSError('SHORT_WRITE')
                stream.flush();os.fsync(stream.fileno())
        except Exception:self.failed=True;raise JournalError('JOURNAL_WRITE_OR_SYNC_FAILED') from None
        self.records.append(row);self.ids[record_id]=row;return True

    def verify_anchor(self,tip):
        if tip not in {r['record_hash'] for r in self.records}:raise JournalError('EXTERNAL_ANCHOR_MISMATCH')
        return True

    def close(self):
        if self.lock is None:return
        os.lseek(self.lock,0,os.SEEK_SET)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(self.lock,msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.lock,fcntl.LOCK_UN)
        os.close(self.lock);self.lock=None
