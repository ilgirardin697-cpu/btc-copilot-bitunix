"""Bounded credential-free child host, started only after the capital cycle."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

FLAG='BITMAN_WEEKLY_FORWARD_OBSERVER_ENABLED'
ROOT=Path(__file__).resolve().parents[1]
TIMEOUT=60
_HOST=None


def enabled():
    return os.environ.get(FLAG,'false').lower()=='true'


class WeeklyHost:
    def __init__(self,folder,url,source_sha,clock=time.time):
        self.folder,self.url,self.source_sha=str(folder),url,source_sha
        self.clock=clock;self._stop=threading.Event();self._lock=threading.Lock()
        self._thread=None;self._process=None;self._value=dict(status='STARTING')

    def start(self):
        if self._thread is None and not self._stop.is_set():
            self._thread=threading.Thread(target=self._loop,daemon=True,name='weekly-forward-passive')
            self._thread.start()

    def read(self):
        with self._lock:
            value=copy.deepcopy(self._value)
        if value.get('status')=='HEALTHY' and int(self.clock()*1000)-value.get('updated_at',0)>660000:
            return dict(status='DEGRADED')
        return value

    def once(self):
        process=None
        try:
            env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
            env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
            request=dict(storage_path=self.folder,market_data_url=self.url,source_sha=self.source_sha)
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            process=subprocess.Popen([sys.executable,'-B','-m','bitman_weekly_forward.worker'],cwd=ROOT,env=env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=flags)
            with self._lock:self._process=process
            if self._stop.is_set():
                process.kill();return
            output,_=process.communicate(json.dumps(request),timeout=TIMEOUT)
            if process.returncode!=0 or len(output)>32768: raise ValueError
            result=json.loads(output)
            if not isinstance(result,dict) or result.get('status') not in ('HEALTHY','DEGRADED','OBSERVER_JOURNAL_INVALID'):
                raise ValueError
        except Exception:
            result=dict(status='DEGRADED')
            if process is not None and process.poll() is None:
                try:process.kill();process.communicate(timeout=2)
                except Exception:pass
        finally:
            with self._lock:self._process=None
        with self._lock:self._value=result

    def _loop(self):
        while not self._stop.is_set():
            self.once()
            value=self.read();now=int(self.clock()*1000)
            delay=max(60,min(300,(value.get('next_due',now+60000)-now)/1000))
            self._stop.wait(delay)

    def stop(self):
        self._stop.set()
        with self._lock:process=self._process
        if process is not None and process.poll() is None:
            try:process.kill()
            except Exception:pass


def after_cycle():
    global _HOST
    if not enabled():return
    if _HOST is None:
        folder=os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or '/data'
        candidate=WeeklyHost(folder,os.environ.get('BITMAN_MARKET_DATA_URL',''),os.environ.get('RAILWAY_GIT_COMMIT_SHA',''))
        candidate.start()
        _HOST=candidate


def manual_context():
    if not enabled():return None
    return _HOST.read() if _HOST is not None else dict(status='STARTING')


def shutdown():
    if _HOST is not None:_HOST.stop()
