"""Optional diagnostics outside immutable V1; no trading or protocol decisions."""
import json
import os
import queue
import re
import subprocess
import sys
import threading

from bitman_weekly_forward import host as frozen_host
from bitman_weekly_forward.host import ROOT,TIMEOUT
from bitman_weekly_forward.protocol import VERSION,SCHEMA,MODELS,MONDAY,WEEK

STATUS_PREFIX='BITMAN_WEEKLY_FORWARD_STATUS='
FETCH_PREFIX='BITMAN_WEEKLY_FORWARD_FETCH='
ERRORS={'DEGRADED':'BITMAN_WEEKLY_FORWARD_DEGRADED',
        'OBSERVER_JOURNAL_INVALID':'BITMAN_WEEKLY_FORWARD_JOURNAL_INVALID'}
STATES={'OTHER','UNKNOWN','IMPULSE_UP','IMPULSE_DOWN','PULLBACK_UP','PULLBACK_DOWN',
        'REACCELERATION_UP','REACCELERATION_DOWN','ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION'}
STATES.update('PENDING_'+kind for kind in ('REACCELERATION_UP','REACCELERATION_DOWN',
                                        'ZERO_CROSS_UP_EXPANSION','ZERO_CROSS_DOWN_EXPANSION'))


def number(value):
    return value if type(value) is int and 0<=value<2**63 else None


def status_projection(value):
    """Construct a fresh allowlisted object; never serialize worker payloads."""
    value=value if type(value) is dict else {}
    raw_status=value.get('status')
    status=raw_status if raw_status=='HEALTHY' else ERRORS.get(raw_status,ERRORS['DEGRADED']) if type(raw_status) is str else ERRORS['DEGRADED']
    tip=value.get('journal_tip')
    tip=tip if type(tip) is str and re.fullmatch('[0-9a-f]{64}',tip) else None
    records=number(value.get('journal_records'))
    s=value.get('snapshot');s=s if type(s) is dict else {}
    models=s.get('models');models=models if type(models) is dict else {}
    horizons=value.get('horizons');horizons=horizons if type(horizons) is dict else {}
    result=dict(status=status,protocol_version=VERSION,schema_version=SCHEMA,
                journal_records=records,journal_tip_prefix=tip[:12] if tip else None,
                week_open=number(value.get('week_open')),available_at=number(s.get('available_at')))
    for name,label in zip(MODELS,('strict','lag1','lag2')):
        model=models.get(name);model=model if type(model) is dict else {}
        state=model.get('state')
        result[label+'_state']=state if type(state) is str and state in STATES else None
        result[label+'_pending']=model.get('pending') is not None
    result.update((key,number(value.get(key))) for key in ('forward_events','active','matured'))
    result.update(('h'+str(h),number(horizons.get(str(h)))) for h in (1,2,3,4))
    result['evidence']='INSUFFICIENT' if value.get('evidence')=='INSUFFICIENT' else None
    result['next_due']=number(value.get('next_due'))
    return (status,tip,records),result


def valid_fetch(value):
    if type(value) is not str or not re.fullmatch('[0-9]{1,16}',value):return None
    stamp=int(value)
    return stamp if stamp<2**63 and (stamp-MONDAY)%WEEK==0 else None


def write_stdout(line):
    # Avoid holding Python's shared stdout TextIO lock in the logging thread.
    os.write(1,(line+'\n').encode('ascii'))


class Diagnostics:
    """Bounded, lossy diagnostic queue; a blocked sink cannot block observation."""
    def __init__(self,writer=write_stdout):
        self._queue=queue.Queue(maxsize=32);self._writer=writer;self._last=None
        self._lock=threading.Lock();self._thread=None

    def start(self):
        try:
            if self._thread is None:
                self._thread=threading.Thread(target=self._loop,daemon=True,name='weekly-forward-diagnostics')
                self._thread.start()
        except Exception:pass

    def _loop(self):
        while True:
            try:line=self._queue.get()
            except Exception:return
            try:self._writer(line)
            except Exception:pass
            finally:
                try:self._queue.task_done()
                except Exception:pass

    def status(self,value):
        try:
            key,result=status_projection(value)
            line=STATUS_PREFIX+json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)
            with self._lock:
                if key==self._last:return
                self._queue.put_nowait(line);self._last=key
        except Exception:pass

    def fetch(self,stamp):
        try:
            value=valid_fetch(str(stamp))
            if value is not None:self._queue.put_nowait(FETCH_PREFIX+str(value))
        except Exception:pass


def forward_fetches(output,diagnostics,seen):
    """Recover complete attempt markers even after a worker timeout or crash."""
    try:
        if type(output) is bytes:output=output.decode('ascii',errors='replace')
        if type(output) is not str:return
        for line in output[:65536].splitlines(keepends=True):
            if not line.endswith('\n') or not line.startswith(FETCH_PREFIX):continue
            stamp=valid_fetch(line[len(FETCH_PREFIX):].rstrip('\r\n'))
            if stamp is None or stamp in seen or len(seen)>=4:continue
            seen.add(stamp)
            try:diagnostics.fetch(stamp)
            except Exception:pass
    except Exception:pass


class LoggingHost(frozen_host.WeeklyHost):
    def __init__(self,*args,diagnostics=None,**kwargs):
        super().__init__(*args,**kwargs)
        try:self._diagnostics=diagnostics if diagnostics is not None else Diagnostics()
        except Exception:self._diagnostics=None

    def start(self):
        super().start()
        try:self._diagnostics.start()
        except Exception:pass

    # once is the reviewed V1 IO boundary with only an external worker launcher,
    # marker decoding and an asynchronous status sink. AST parity is enforced.
    def once(self):
        process=None
        attempts=set()
        try:
            env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
            env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
            request=dict(storage_path=self.folder,market_data_url=self.url,source_sha=self.source_sha)
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            process=subprocess.Popen([sys.executable,'-B','-m','bitman_weekly_forward_log_worker'],cwd=ROOT,env=env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=flags)
            with self._lock:self._process=process
            if self._stop.is_set():
                process.kill();return
            output,stderr_output=process.communicate(json.dumps(request),timeout=TIMEOUT)
            forward_fetches(stderr_output,self._diagnostics,attempts)
            if process.returncode!=0 or len(output)>32768: raise ValueError
            result=json.loads(output)
            if not isinstance(result,dict) or result.get('status') not in ('HEALTHY','DEGRADED','OBSERVER_JOURNAL_INVALID'):
                raise ValueError
        except Exception as error:
            forward_fetches(getattr(error,'stderr',None),self._diagnostics,attempts)
            result=dict(status='DEGRADED')
            if process is not None and process.poll() is None:
                try:
                    process.kill();_,stderr_output=process.communicate(timeout=2)
                    forward_fetches(stderr_output,self._diagnostics,attempts)
                except Exception:pass
        finally:
            with self._lock:self._process=None
        with self._lock:self._value=result
        try:self._diagnostics.status(result)
        except Exception:pass


def after_cycle():
    if not frozen_host.enabled():return
    if frozen_host._HOST is None:
        folder=os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or '/data'
        candidate=LoggingHost(folder,os.environ.get('BITMAN_MARKET_DATA_URL',''),os.environ.get('RAILWAY_GIT_COMMIT_SHA',''))
        candidate.start()
        frozen_host._HOST=candidate
