"""Nonblocking, disabled-by-default facade around the EXISTING Telegram sender."""
from collections import deque
import json
import os
from pathlib import Path
import queue
import threading
import time
from .policy import Policy,render
from .adapters import guardian_alert,capital_message,event,copilot_snapshot

_host=None


def enabled():
    return os.getenv('IGOD_NOTIFICATION_RADAR_ENABLED','false').lower()=='true'


def diagnostic(code):
    try:print(code,flush=True)
    except Exception:pass


class Host:
    def __init__(self,original,directory,clock=time.time):
        self.original=original;self.directory=Path(directory)/'notification_radar_v1';self.clock=clock
        self.queue=queue.Queue(maxsize=512);self.stop=threading.Event();self.ready=threading.Event()
        self.failed=False;self.policy=None;self.server=None;self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True,name='igod-notification-radar')
        self.thread.start()

    def submit(self,value):
        try:
            if self.failed:raise ValueError('NOTIFICATION_STORE_UNAVAILABLE')
            self.queue.put_nowait(('event',value,None));return True
        except Exception:
            diagnostic('IGOD_NOTIFICATION_FALLBACK' if value.get('kind') in ('CRITICAL','RECOVERED') else 'IGOD_NOTIFICATION_NOT_QUEUED')
            if value.get('kind') in ('CRITICAL','RECOVERED'):
                return bool(self.original.send(value.get('text') or value['what_changed']))
            return False

    def snapshot(self,value):
        try:self.queue.put_nowait(('snapshot',value,None))
        except Exception:diagnostic('IGOD_NOTIFICATION_SNAPSHOT_SKIPPED')

    def rpc(self,kind,value,timeout=2):
        response=queue.Queue(maxsize=1)
        self.queue.put_nowait((kind,value,response))
        result=response.get(timeout=timeout)
        if isinstance(result,Exception):raise ValueError('NOTIFICATION_REQUEST_FAILED')
        return result

    def _deliver(self,row,now):
        value=json.loads(row['payload']);success=True
        self.policy.db.execute('CREATE TABLE IF NOT EXISTS delivered(event_id TEXT,recipient TEXT,PRIMARY KEY(event_id,recipient))')
        self.policy.db.commit()
        for recipient in self.original._recipients:
            done=self.policy.db.execute('SELECT 1 FROM delivered WHERE event_id=? AND recipient=?',(row['id'],recipient)).fetchone()
            if done:continue
            try:ok=self.original._deliver(recipient,render(value))
            except Exception:ok=False
            if ok:
                with self.policy.db:self.policy.db.execute('INSERT OR IGNORE INTO delivered VALUES(?,?)',(row['id'],recipient))
            success=bool(ok) and success
        self.policy.finish(row,success and bool(self.original._recipients),now)

    def run(self):
        try:
            self.policy=Policy(self.directory)
            key=os.getenv('IGOD_NOTIFICATION_INGEST_KEY','')
            if key:
                from .server import start
                self.server=start(self,key)
            self.ready.set()
            while not self.stop.is_set():
                try:kind,value,response=self.queue.get(timeout=.1)
                except queue.Empty:kind=None
                if kind:
                    try:
                        now=int(self.clock()*1000)
                        if kind=='event':result=self.policy.ingest(value,now)
                        elif kind=='snapshot':
                            result=[self.policy.ingest(e,now) for e in copilot_snapshot(self.policy,value,now)]
                        elif kind=='settings':
                            if value is not None:self.policy.setting('silent',value)
                            result=self.policy.setting('silent')
                        else:raise ValueError('UNSUPPORTED_NOTIFICATION_REQUEST')
                        diagnostic('IGOD_NOTIFICATION_PROCESSED')
                        if response:response.put_nowait(result)
                    except Exception as error:
                        diagnostic('IGOD_NOTIFICATION_REJECTED')
                        if response:response.put_nowait(error)
                        elif kind=='event' and value.get('kind') in ('CRITICAL','RECOVERED'):
                            self.original.send(value.get('text') or value['what_changed'])
                    finally:self.queue.task_done()
                row=self.policy.next(int(self.clock()*1000))
                if row:self._deliver(row,int(self.clock()*1000))
        except Exception:
            self.failed=True;self.ready.set();diagnostic('IGOD_NOTIFICATION_DEGRADED')
            while True:
                try:kind,value,response=self.queue.get_nowait()
                except queue.Empty:break
                if kind=='event' and value.get('kind') in ('CRITICAL','RECOVERED'):
                    self.original.send(value.get('text') or value['what_changed'])
                if response:response.put_nowait(ValueError('NOTIFICATION_UNAVAILABLE'))
                self.queue.task_done()
        finally:
            if self.server:self.server.shutdown()
            if self.policy:self.policy.close()


class Proxy:
    def __init__(self,original,host):self.original=original;self.host=host
    def send_owner(self,text):return self.original.send_owner(text)
    def send(self,text):return self.host.submit(capital_message(text,int(self.host.clock()*1000)))
    def send_observation(self,text):
        return self.host.submit(event('mlrsi','OBSERVATION',int(self.host.clock()*1000),'Actualización ML RSI conservada internamente',reason='INDICATOR_ONLY'))
    def alert(self,key,text,notice=None):return self.host.submit(guardian_alert(key,text,int(self.host.clock()*1000),notice))


def install(guardian):
    global _host
    if not enabled():return
    try:
        if _host is not None:raise ValueError('NOTIFICATION_ALREADY_INSTALLED')
        instance=Host(guardian.telegram,guardian.config.state_dir)
        instance.start();guardian.telegram=Proxy(guardian.telegram,instance);_host=instance
    except Exception:diagnostic('IGOD_NOTIFICATION_INSTALL_FAILED')


def emit(telegram,key,text,notice=None):
    method=getattr(telegram,'alert',None)
    return method(key,text,notice) if method else telegram.send(text)


def observer_sender(telegram):
    return getattr(telegram,'send_observation',telegram.send)


def after_cycle(guardian):
    if _host is not None and not _host.failed:
        value=guardian.command_snapshot.read()
        if value is not None:_host.snapshot({'data':value.get('data',{})})


def shutdown():
    global _host
    if _host:_host.stop.set()
    _host=None


def daily_automatic(reply,text):
    if not enabled():return reply(text)
    if _host:
        return _host.submit(event('daily_plan','OBSERVATION',int(_host.clock()*1000),'Plan diario automático conservado internamente',reason='ROUTINE_PLAN'))
    diagnostic('IGOD_NOTIFICATION_DAILY_ROUTINE_SUPPRESSED');return True


def settings(command,reply):
    parts=command.split()
    if not enabled() or not parts or parts[0] not in ('/alertas','/silencio'):return False
    if _host is None:
        reply('📡 Radar no disponible. Consultas manuales disponibles; alertas críticas no se silencian.');return True
    try:
        value=None
        if parts==['/silencio'] or parts==['/alertas','off']:value=True
        elif parts in (['/alertas','on'],['/silencio','off']):value=False
        elif parts!=['/alertas']:
            reply('📡 Usa /alertas, /alertas on, /alertas off, /silencio o /silencio off.\nLas alertas críticas permanecen activas.');return True
        silent=_host.rpc('settings',value)
        reply('📡 I-GOD · RADAR SILENCIOSO\nOportunidades: '+('SILENCIADAS' if silent else 'ACTIVAS')+
              '\nSolo PRE-LONG / PRE-SHORT / CONFIRMED / INVALIDATED.\nSeguridad crítica: SIEMPRE ACTIVA, con deduplicación por incidente.'+
              '\nSin WAIT, heartbeats ni indicadores rutinarios.\nLos comandos manuales siguen disponibles.\nSHADOW ONLY · TRADE AUTHORITY: NONE')
    except Exception:reply('📡 No se pudo confirmar el cambio de notificaciones. Las alertas críticas conservan su ruta de seguridad.')
    return True
