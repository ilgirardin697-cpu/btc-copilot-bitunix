"""Single-writer, append-only journal and original public response byte storage."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading

from .frozen import canonical, verify_freeze


class EvidenceError(Exception):
    """Static safe code only, never exception text, request headers or paths."""


SAFE_CODES=frozenset('''STORE_ALREADY_LOCKED JOURNAL_INVALID_NO_REPAIR INVALID_RAW_REFERENCE
RAW_HASH_MISMATCH STORAGE_LOW RAW_CONFLICT RAW_DURABILITY_UNCERTAIN STORE_UNCERTAIN
CLOCK_WENT_BACKWARDS ACTIVATION_REQUIRED CONFLICTING_RECORD_NO_REWRITE JOURNAL_DURABILITY_UNCERTAIN
PUBLIC_NETWORK_UNAVAILABLE PUBLIC_RESPONSE_TOO_LARGE PUBLIC_JSON_INVALID PUBLIC_CLOCK_SCHEMA CLOCK_UNVERIFIED
PUBLIC_RANGE_REJECTED PUBLIC_KLINES_NOT_LIST PUBLIC_KLINE_SCHEMA_OR_TIME PUBLIC_NUMERIC_SCHEMA
PUBLIC_VOLUME_INVALID PUBLIC_GAP_DUPLICATE_OR_OHLC PUBLIC_PATH_REJECTED PUBLIC_PARAMETERS_REJECTED
CLOCK_NOT_AT_ANCHOR OUTCOME_NOT_MATURE_SERVER_CLOCK DST_INCOMPLETE_CYCLE REVIEWED_SOURCE_SHA_REQUIRED
INVALID_ENABLED_FLAG INVALID_PORT INDEPENDENT_PERSISTENT_VOLUME_REQUIRED
MISSING_OR_DUPLICATE_CLOSED_CANDLES INVALID_OHLC INVALID_CAUSAL_PREFIX PRICE_SCALE_UNAVAILABLE
OUTCOME_NOT_MATURE DST_LONDON_NOT_FOUR_H1 PUBLIC_H1_1M_MISMATCH NO_CONFIRMED_ATR_CONTEXT
PRICE_MODEL_CHANGED PRIOR_CHANGED FROZEN_ASSET_CHANGED OBSERVER_PROTOCOL_CHANGED MIXED_COHORT_REJECTED'''.split())


def safe_error(error):
    code=error.args[0] if len(error.args)==1 and isinstance(error.args[0],str) else ''
    return code if code in SAFE_CODES or re.fullmatch('PUBLIC_HTTP_[1-5][0-9]{2}',code) else 'INTERNAL_ERROR'


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class Store:
    @classmethod
    def inspect(cls,root):
        """Read an existing evidence COPY without mkdir, lock writes or repairs."""
        obj=object.__new__(cls)
        obj.root=Path(root);obj.path=obj.root/'events.jsonl';obj.freeze=verify_freeze()
        if not obj.path.is_file():raise EvidenceError('EVIDENCE_COPY_NOT_FOUND')
        try:return obj._read()
        except Exception:raise EvidenceError('JOURNAL_INVALID_NO_REPAIR') from None

    def __init__(self, root, clock):
        self.root, self.clock = Path(root), clock
        self.root.mkdir(parents=True, exist_ok=True)
        self.mutex = threading.RLock()
        self.poisoned = False
        self.lock_file = (self.root / '.writer.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if self.lock_file.tell() == 0:
                    self.lock_file.write(b'0'); self.lock_file.flush()
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            self.lock_file.close()
            raise EvidenceError('STORE_ALREADY_LOCKED') from None
        self.freeze = verify_freeze()
        self.path = self.root / 'events.jsonl'
        try:
            self.rows = self._read()
        except Exception:
            self.close()
            raise EvidenceError('JOURNAL_INVALID_NO_REPAIR') from None
        self.by_id = {r['record_id']: r for r in self.rows}

    def close(self):
        if getattr(self, 'lock_file', None) is not None and not self.lock_file.closed:
            if os.name == 'nt':
                import msvcrt
                self.lock_file.seek(0)
                try:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            self.lock_file.close()

    def _sync_dir(self, directory):
        if os.name != 'nt':
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _read(self):
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b'\n'):
            raise EvidenceError('TRUNCATED_JOURNAL')
        rows, ids, tip, last = [], set(), '0'*64, 0
        by_id={}
        allowed = {'ACTIVATION','RECOVERY','CONTEXT','ATTEMPT','PREDICTION','DURABILITY','MISSED','FAILURE','OUTCOME'}
        checked = set()
        for line in raw.splitlines():
            r = json.loads(line)
            fields = {'schema_version','protocol_version','origin','model_sha256','protocol_sha256',
                      'record_type','record_id','created_at','prev_hash','record_hash','data'}
            unsigned = {k:v for k,v in r.items() if k!='record_hash'}
            if (set(r)!=fields or r['record_hash']!=digest(unsigned) or r['prev_hash']!=tip
                or r['record_id'] in ids or r['record_type'] not in allowed
                or r['schema_version']!=1 or r['protocol_version']!='IGOD_PRICE_BINANCE_FORWARD_V1'
                or r['origin']!='PYTHON_BINANCE_SPOT_LIVE'
                or r['model_sha256']!=self.freeze['model_sha256']
                or r['protocol_sha256']!=self.freeze['protocol_sha256']
                or type(r['created_at']) is not int or r['created_at']<last):
                raise EvidenceError('INVALID_CHAIN')
            if not rows and r['record_type']!='ACTIVATION':
                raise EvidenceError('MISSING_ACTIVATION')
            if rows and r['record_type']=='ACTIVATION':
                raise EvidenceError('SECOND_ACTIVATION')
            if r['record_type']=='PREDICTION':
                d=r['data']
                if d['context_id'] not in ids or d['emitted_at']>r['created_at'] or d['available_at']>d['emitted_at']:
                    raise EvidenceError('PREDICTION_SEMANTICS')
                from datetime import datetime,timezone
                import numpy as np
                from .features import NY
                from .frozen import predict,read_json,structure_predict
                t=datetime.fromtimestamp(d['available_at']/1000,timezone.utc).astimezone(NY)
                if (t.hour!=5 or t.minute!=d['minute'] or t.second or t.microsecond
                    or d['minute'] not in (0,15,30,45,59) or t.date().isoformat()!=d['cycle']
                    or d['model_version']!=self.freeze['model_version']
                    or by_id[d['context_id']]['record_type']!='CONTEXT'
                    or not np.allclose(predict(d['features']),d['probabilities'],rtol=0,atol=1e-12)
                    or canonical(d['prior'])!=canonical(read_json('frozen_PRIOR.json'))
                    or not np.allclose(structure_predict(d['features'],read_json('frozen_STRUCTURE.json')),d['structure'],rtol=0,atol=1e-12)):
                    raise EvidenceError('PREDICTION_FROZEN_MODEL_MISMATCH')
                for source in d['sources']:
                    if source['params']['endTime']>=d['available_at'] or source['received_at']>d['emitted_at']:
                        raise EvidenceError('FUTURE_SOURCE_IN_PREDICTION')
            if r['record_type']=='DURABILITY':
                d=r['data']
                if (d['prediction_id'] not in ids or d['prediction_durable_at']>r['created_at']
                    or by_id[d['prediction_id']]['record_type']!='PREDICTION'
                    or d['prediction_durable_at']<by_id[d['prediction_id']]['created_at']):
                    raise EvidenceError('DURABILITY_SEMANTICS')
            if r['record_type']=='OUTCOME':
                from datetime import date
                from .features import schedule
                outcome=r['data']['outcome'];s=schedule(date.fromisoformat(r['data']['cycle']))
                if (outcome['class_index'] not in (-1,0,1,2) or outcome['label_available_at']!=s['end']
                    or r['created_at']<s['end'] or type(r['data']['quality_pass']) is not bool):
                    raise EvidenceError('OUTCOME_SEMANTICS')
            for ref in r['data'].get('raw_refs', []):
                if ref not in checked:
                    self.read_raw(ref); checked.add(ref)
            rows.append(r); ids.add(r['record_id']); by_id[r['record_id']]=r;tip=r['record_hash'];last=r['created_at']
        return rows

    def read_raw(self, sha):
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise EvidenceError('INVALID_RAW_REFERENCE')
        raw = (self.root / 'raw' / (sha + '.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:
            raise EvidenceError('RAW_HASH_MISMATCH')
        return raw

    def archive(self, raw):
        if self.poisoned:
            raise EvidenceError('STORE_UNCERTAIN')
        if shutil.disk_usage(self.root).free < 33_554_432:
            raise EvidenceError('STORAGE_LOW')
        sha=hashlib.sha256(raw).hexdigest()
        folder=self.root/'raw'; folder.mkdir(exist_ok=True)
        path=folder/(sha+'.json')
        if path.exists():
            if path.read_bytes()!=raw:
                raise EvidenceError('RAW_CONFLICT')
            return sha
        try:
            with path.open('xb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            self._sync_dir(folder)
        except OSError:
            self.poisoned=True
            raise EvidenceError('RAW_DURABILITY_UNCERTAIN') from None
        return sha

    def append(self, kind, rid, data):
        with self.mutex:
            if self.poisoned:
                raise EvidenceError('STORE_UNCERTAIN')
            if rid in self.by_id:
                old=self.by_id[rid]
                if old['record_type']!=kind or canonical(old['data'])!=canonical(data):
                    raise EvidenceError('CONFLICTING_RECORD_NO_REWRITE')
                return old
            created=self.clock.now_ms()
            if self.rows and created<self.rows[-1]['created_at']:
                raise EvidenceError('CLOCK_WENT_BACKWARDS')
            if not self.rows and kind!='ACTIVATION':
                raise EvidenceError('ACTIVATION_REQUIRED')
            for ref in data.get('raw_refs', []):
                self.read_raw(ref)
            r=dict(schema_version=1,protocol_version='IGOD_PRICE_BINANCE_FORWARD_V1',
                   origin='PYTHON_BINANCE_SPOT_LIVE',model_sha256=self.freeze['model_sha256'],
                   protocol_sha256=self.freeze['protocol_sha256'],record_type=kind,record_id=rid,
                   created_at=created,prev_hash=self.rows[-1]['record_hash'] if self.rows else '0'*64,data=deepcopy(data))
            r['record_hash']=digest(r)
            try:
                with self.path.open('ab') as f:
                    f.write(canonical(r)+b'\n'); f.flush(); os.fsync(f.fileno())
                self._sync_dir(self.root)
            except OSError:
                self.poisoned=True
                raise EvidenceError('JOURNAL_DURABILITY_UNCERTAIN') from None
            self.rows.append(r); self.by_id[rid]=r
            return deepcopy(r)

    def snapshot(self):
        with self.mutex:
            return deepcopy(self.rows)

    def write_report(self, report):
        raw=canonical(report)+b'\n'
        temporary=self.root/'report.json.tmp'
        with temporary.open('wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(temporary,self.root/'report.json')
        self._sync_dir(self.root)
