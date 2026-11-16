"""Atomic immutable raw-receipt spool; independent future storage only."""
from pathlib import Path
import hashlib,json,os,sqlite3
from ..journal import canonical,digest

class Spool:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=os.open(self.root/'writer.lock',os.O_CREAT|os.O_RDWR,0o600)
        if not os.fstat(self.lock).st_size:os.write(self.lock,b'0');os.fsync(self.lock)
        os.lseek(self.lock,0,0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.db=sqlite3.connect(self.root/'public_receipts.sqlite');self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            self.db.executescript('''CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY,metadata TEXT NOT NULL,body BLOB NOT NULL,previous_hash TEXT NOT NULL,record_hash TEXT UNIQUE NOT NULL);
CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON receipts BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON receipts BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;''')
            self.tip='0'*64;self.count=0;self.verify()
        except Exception:os.close(self.lock);self.lock=None;raise
    def verify(self):
        previous='0'*64;count=0
        for index,text,raw,prev,sha in self.db.execute('SELECT id,metadata,body,previous_hash,record_hash FROM receipts ORDER BY id'):
            meta=json.loads(text);expected=digest(dict(id=index,metadata=meta,body_sha256=hashlib.sha256(raw).hexdigest(),previous_hash=prev))
            if prev!=previous or expected!=sha or index!=count+1:raise ValueError('SPOOL_INTEGRITY_INVALID')
            previous=sha;count+=1
        self.tip=previous;self.count=count;return True
    def append(self,metadata,body):
        index=self.count+1;raw=bytes(body);meta=dict(metadata,body_sha256=hashlib.sha256(raw).hexdigest(),body_bytes=len(raw))
        sha=digest(dict(id=index,metadata=meta,body_sha256=meta['body_sha256'],previous_hash=self.tip))
        with self.db:self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(index,canonical(meta).decode(),raw,self.tip,sha))
        self.count=index;self.tip=sha;return dict(record_id=index,record_hash=sha,metadata=meta,body=raw)
    def close(self):
        if getattr(self,'db',None):self.db.close();self.db=None
        if self.lock is not None:os.close(self.lock);self.lock=None
