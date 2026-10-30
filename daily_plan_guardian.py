"""Passive private HTTP bridge. No bot token, second poller or trading client."""
import os
import queue
import threading
import time
from urllib.parse import urlsplit
import requests

COMMANDS = ('/diario','/resumen','/niveles','/alertas','/silencio')
HELP = ''.join(command+'\n→ plan diario experimental, solo consulta\n\n' for command in COMMANDS)
UNAVAILABLE = '📊 I-GOD | PLAN DIARIO BTCUSDT\n🟡 ESPERAR\n⚠️ Planificador no disponible; sin datos fiables.\nSHADOW ONLY. TRADE AUTHORITY: NONE.'


class DailyPlanBridge:
    def __init__(self, reply, url=None, transport=None, clock=time.time):
        url = os.getenv('IGOD_DAILY_PLAN_URL','') if url is None else url
        self.url = ''
        if url:
            parts=urlsplit(url)
            if (parts.scheme,parts.hostname,parts.port,parts.path.rstrip('/')) != ('http','igod-daily-plan.railway.internal',8080,'') or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError('DAILY_PRIVATE_URL_INVALID')
            self.url=url.rstrip('/')
        self.reply,self.clock=reply,clock
        self.http=transport or requests.Session()
        self.http.trust_env=False
        self.http.auth=None
        self.http.headers.clear()
        self.queue=queue.Queue(maxsize=8)
        self.stopped=threading.Event()
        self.thread=None

    def start(self):
        if not self.url or self.thread is not None:
            return
        self.thread=threading.Thread(target=self._run,daemon=True,name='daily-plan-private-bridge')
        self.thread.start()

    def request(self, command, identifier):
        parts=command.split(maxsplit=1)
        name=parts[0].split('@')[0] if parts else ''
        if name not in COMMANDS:
            return False
        command=name+(' '+parts[1] if len(parts)>1 else '')
        if not self.url or type(identifier) is not int:
            return bool(self.reply(UNAVAILABLE))
        self.start()
        try:
            self.queue.put_nowait((command,identifier))
            return True
        except queue.Full:
            return bool(self.reply('⏳ Plan diario ocupado; vuelve a consultar en unos segundos.'))

    def exchange(self, path, body):
        if path not in ('/command','/notifications'):
            raise ValueError('DAILY_PATH_DENIED')
        response=self.http.post(self.url+path,json=body,timeout=(2,60),allow_redirects=False)
        if response.status_code!=200 or len(response.content)>30_000:
            raise ValueError('DAILY_RESPONSE_UNAVAILABLE')
        value=response.json()
        if not isinstance(value,dict):
            raise ValueError('DAILY_RESPONSE_SCHEMA')
        if value.get('deliver') is True:
            text=value.get('text')
            if not isinstance(text,str) or not text or len(text)>3900:
                raise ValueError('DAILY_TEXT_INVALID')
            if not self.stopped.is_set():
                accepted=bool(self.reply(text))
                try:
                    print('IGOD_DAILY_REPLY_QUEUED' if accepted else 'IGOD_DAILY_REPLY_NOT_QUEUED',flush=True)
                except Exception:
                    pass
        return value

    def _run(self):
        due=0
        while not self.stopped.is_set():
            try:
                command,identifier=self.queue.get(timeout=1)
            except queue.Empty:
                if self.clock()>=due:
                    try:
                        self.exchange('/notifications',{})
                    except Exception:
                        pass
                    due=self.clock()+30
                continue
            try:
                self.exchange('/command',dict(command=command,update_id=identifier))
            except Exception:
                if not self.stopped.is_set():
                    self.reply(UNAVAILABLE)
            finally:
                self.queue.task_done()

    def stop(self):
        self.stopped.set()
