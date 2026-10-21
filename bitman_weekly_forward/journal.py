"""Single-writer append-only hash chain; never repair, truncate or rewrite it."""
import json
import os
from pathlib import Path
from .protocol import VERSION, SCHEMA, VENUE, EXPECTED_HASH, canonical, digest

NAME='bitman_weekly_forward_v1.jsonl'
STATE='bitman_weekly_forward_v1_state.json'
ZERO='0'*64
MAX_BYTES=16*1024*1024
TYPES={'FORWARD_OBSERVATION_START','BOOTSTRAP','WEEK_SNAPSHOT','MODEL_EVENT','OUTCOME','RECOVERY'}


class JournalInvalid(ValueError):
    def __init__(self):
        super().__init__('OBSERVER_JOURNAL_INVALID')


def identifier(kind,week,payload):
    if kind in ('FORWARD_OBSERVATION_START','BOOTSTRAP'):
        return kind+':'+VERSION
    if kind=='WEEK_SNAPSHOT':
        return 'WEEK:'+VERSION+':'+str(week)
    if kind=='MODEL_EVENT':
        return 'EVENT:'+VERSION+':'+payload['model']+':'+str(week)+':'+payload['kind']
    if kind=='OUTCOME':
        return 'OUTCOME:'+payload['event_id']+':H'+str(payload['horizon'])
    if kind=='RECOVERY':
        return 'RECOVERY:'+VERSION+':'+payload['role']+':'+str(week)
    raise JournalInvalid()


def sync_directory(folder):
    if os.name!='nt':
        fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class Journal:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.path=self.folder/NAME
        self.records=[]
        self.ids=set()
        self.poisoned=False
        self._lock=None

    def __enter__(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        if any((self.folder/name).is_symlink() for name in (NAME,STATE,STATE+'.tmp','bitman_weekly_forward_v1.lock')):
            raise JournalInvalid()
        self._lock=(self.folder/'bitman_weekly_forward_v1.lock').open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.load()
            return self
        except Exception:
            self._lock.close()
            raise

    def __exit__(self,*args):
        if self._lock:
            self._lock.close()

    def load(self):
        self.records=[]; self.ids=set()
        if not self.path.exists():
            if (self.folder/STATE).exists():
                raise JournalInvalid()
            return
        if self.path.stat().st_size>MAX_BYTES:
            raise JournalInvalid()
        raw=self.path.read_bytes()
        if not raw or not raw.endswith(b'\n'):
            raise JournalInvalid()
        previous=ZERO
        try:
            for line in raw.splitlines():
                row=json.loads(line)
                expected_keys={'schema_version','protocol_version','protocol_hash','record_type','record_id','created_at',
                    'week_open','available_at','source_venue','source_timeframe','source_hash','weekly_candle_hash',
                    'prev_hash','record_hash','payload'}
                if set(row)!=expected_keys or row['record_type'] not in TYPES:
                    raise JournalInvalid()
                if (type(row['schema_version']) is not int or type(row['payload']) is not dict
                    or row['schema_version']!=SCHEMA or row['protocol_version']!=VERSION or row['protocol_hash']!=EXPECTED_HASH
                    or row['source_venue']!=VENUE or row['source_timeframe']!='1W' or row['prev_hash']!=previous):
                    raise JournalInvalid()
                if any(type(row[k]) is not int for k in ('created_at','week_open','available_at')) or row['created_at']<row['available_at']:
                    raise JournalInvalid()
                if any(type(row[k]) is not str or len(row[k])!=64 or any(c not in '0123456789abcdef' for c in row[k])
                       for k in ('source_hash','weekly_candle_hash','record_hash')):
                    raise JournalInvalid()
                if self.records and row['created_at']<self.records[-1]['created_at']:
                    raise JournalInvalid()
                checksum=row['record_hash']
                if checksum!=digest({k:v for k,v in row.items() if k!='record_hash'}):
                    raise JournalInvalid()
                if row['record_id']!=identifier(row['record_type'],row['week_open'],row['payload']) or row['record_id'] in self.ids:
                    raise JournalInvalid()
                self.ids.add(row['record_id']);self.records.append(row);previous=checksum
            if self.records[0]['record_type']!='FORWARD_OBSERVATION_START':
                raise JournalInvalid()
        except JournalInvalid:
            raise
        except Exception:
            raise JournalInvalid() from None
        # A prior complete write with uncertain fsync is accepted only after a new successful sync.
        with self.path.open('ab') as stream:
            stream.flush();os.fsync(stream.fileno())

    def append(self,kind,week,available,payload,now,source_hash,candle_hash):
        if self.poisoned:
            raise ValueError('OBSERVER_DURABILITY_UNCONFIRMED')
        rid=identifier(kind,week,payload)
        if rid in self.ids:
            return False
        if type(now) is not int or now<available or self.records and now<self.records[-1]['created_at']:
            raise ValueError('RECORD_NOT_YET_AVAILABLE')
        row=dict(schema_version=SCHEMA,protocol_version=VERSION,protocol_hash=EXPECTED_HASH,record_type=kind,
            record_id=rid,created_at=now,week_open=int(week),available_at=int(available),source_venue=VENUE,
            source_timeframe='1W',source_hash=source_hash,weekly_candle_hash=candle_hash,
            prev_hash=self.records[-1]['record_hash'] if self.records else ZERO,payload=payload)
        row['record_hash']=digest(row)
        try:
            fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
            with os.fdopen(fd,'ab') as stream:
                stream.write(canonical(row)+b'\n');stream.flush();os.fsync(stream.fileno())
            sync_directory(self.folder)
        except Exception:
            self.poisoned=True
            raise ValueError('OBSERVER_DURABILITY_UNCONFIRMED') from None
        self.records.append(row);self.ids.add(rid)
        return True

    def save_state(self,value):
        target=self.folder/STATE
        temporary=self.folder/(STATE+'.tmp')
        with temporary.open('wb') as stream:
            stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
        sync_directory(self.folder)
