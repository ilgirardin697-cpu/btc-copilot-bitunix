"""Async V8 notification relay; local durable spool, private URL allowlist only."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
from urllib.parse import urlsplit
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from .adapters import v8_event
from .policy import packed,identity

URL='http://igod-trade-guardian.railway.internal:8091/events'
_client=None
_fallback_queue=queue.Queue(maxsize=256)
_fallback_thread=None
_fallback_seen={}
_fallback_lock=threading.Lock()


def fallback_async(value,legacy):
    """Last-resort critical delivery is never a network wait on the caller."""
    global _fallback_thread
    try:
        now=int(time.time()*1000)
        key=identity(value.get('incident_id'),value.get('severity'),value.get('material'))
        with _fallback_lock:
            if key in _fallback_seen and now-_fallback_seen[key]<3600000:return True
            if _fallback_thread is None:
                def run():
                    while True:
                        callback,text=_fallback_queue.get()
                        try:callback(text)
                        except Exception:
                            try:print('IGOD_NOTIFICATION_CRITICAL_FALLBACK_FAILED',flush=True)
                            except Exception:pass
                        finally:_fallback_queue.task_done()
                _fallback_thread=threading.Thread(target=run,daemon=True,name='igod-critical-notification-fallback')
                _fallback_thread.start()
            _fallback_queue.put_nowait((legacy,value.get('text') or value['what_changed']))
            _fallback_seen[key]=now
        return True
    except Exception:
        try:print('IGOD_NOTIFICATION_CRITICAL_FALLBACK_NOT_QUEUED',flush=True)
        except Exception:pass
        return False


def valid_url(value):
    p=urlsplit(value)
    if (p.scheme,p.hostname,p.port,p.path)!=('http','igod-trade-guardian.railway.internal',8091,'/events') or p.username or p.password or p.query or p.fragment:
        raise ValueError('NOTIFICATION_PRIVATE_URL_REQUIRED')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Client:
    def __init__(self,url,key,directory,fallback,clock=time.time):
        self.url=valid_url(url);self.key=key;self.directory=Path(directory)
        self.fallback=fallback;self.clock=clock;self.queue=queue.Queue(maxsize=256)
        self.stop=threading.Event();self.failed=False
        self.http=build_opener(ProxyHandler({}),NoRedirect())
        self.thread=threading.Thread(target=self.run,daemon=True,name='v8-notification-relay')
        self.thread.start()

    def submit(self,event):
        if event['kind']=='OBSERVATION':
            try:print('IGOD_V8_NOTIFICATION_OBSERVATION',flush=True)
            except Exception:pass
            return True
        try:
            if self.failed:raise ValueError('RELAY_UNAVAILABLE')
            self.queue.put_nowait(event);return True
        except Exception:
            return fallback_async(event,self.fallback)

    def post(self,value):
        body=packed(value).encode()
        signed=hmac.new(self.key.encode(),body,hashlib.sha256).hexdigest()
        req=Request(self.url,data=body,headers={'Content-Type':'application/json','X-IGOD-Signature':signed},method='POST')
        with self.http.open(req,timeout=3) as response:
            if response.status!=200:raise ValueError('NOTIFICATION_NOT_ACKNOWLEDGED')
            ack=json.loads(response.read(4096))
            if ack.get('ok') is not True or ack.get('record_id')!=value['id']:
                raise ValueError('NOTIFICATION_ACK_INVALID')

    def run(self):
        db=None
        try:
            self.directory.mkdir(parents=True,exist_ok=True)
            db=sqlite3.connect(self.directory/'notification_spool.sqlite3')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS spool(id TEXT PRIMARY KEY,payload TEXT,acked INTEGER DEFAULT 0,fallback_at INTEGER DEFAULT 0,next_due INTEGER DEFAULT 0,severity INTEGER)')
            db.commit()
            while not self.stop.is_set():
                batch=[]
                try:batch.append(self.queue.get(timeout=.1))
                except queue.Empty:pass
                for _ in range(63):
                    try:batch.append(self.queue.get_nowait())
                    except queue.Empty:break
                with db:
                    for value in batch:
                        slot=identity(value['incident_id'],value['severity'],value.get('material'),value['at']//3600000)
                        db.execute('INSERT OR IGNORE INTO spool(id,payload,severity) VALUES(?,?,?)',(slot,packed(value),value['severity']))
                for _ in batch:self.queue.task_done()
                now=int(self.clock()*1000)
                row=db.execute('SELECT id,payload,fallback_at FROM spool WHERE acked=0 AND next_due<=? ORDER BY severity DESC,next_due,rowid LIMIT 1',(now,)).fetchone()
                if not row:continue
                try:
                    self.post(json.loads(row[1]))
                    with db:db.execute('UPDATE spool SET acked=1 WHERE id=?',(row[0],))
                except Exception:
                    now=int(self.clock()*1000)
                    if not row[2] or now-row[2]>=3600000:
                        # Critical-only fallback. An unreachable coordinator may
                        # cause a duplicate across paths; never drop a new crisis.
                        value=json.loads(row[1]);fallback_async(value,self.fallback)
                        with db:db.execute('UPDATE spool SET fallback_at=? WHERE id=?',(now,row[0]))
                    with db:db.execute('UPDATE spool SET next_due=? WHERE id=?',(now+5000,row[0]))
        except Exception:
            self.failed=True
            try:print('IGOD_V8_NOTIFICATION_RELAY_DEGRADED',flush=True)
            except Exception:pass
            while True:
                try:value=self.queue.get_nowait()
                except queue.Empty:break
                fallback_async(value,self.fallback);self.queue.task_done()
        finally:
            if db:db.close()


def dispatch_v8(message,legacy):
    global _client
    if os.getenv('IGOD_NOTIFICATION_RADAR_ENABLED','false').lower()!='true':
        return legacy(message)
    value=v8_event(message,int(time.time()*1000))
    if value['kind']=='OBSERVATION':
        try:print('IGOD_V8_NOTIFICATION_OBSERVATION',flush=True)
        except Exception:pass
        return True
    if _client is None:
        try:
            key=os.getenv('IGOD_NOTIFICATION_INGEST_KEY','')
            if not key:raise ValueError('NOTIFICATION_KEY_REQUIRED')
            _client=Client(os.getenv('IGOD_NOTIFICATION_URL',URL),key,
                Path(os.getenv('V8_DATA_DIR',os.getenv('RAILWAY_VOLUME_MOUNT_PATH','.')))/'v8',legacy)
        except Exception:
            return fallback_async(value,legacy)
    return _client.submit(value)
