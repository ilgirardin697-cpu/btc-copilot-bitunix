"""Private planner API. No Telegram token, message sender, poller or account client."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from zoneinfo import ZoneInfo

from .analysis import calculate
from .render import render
from .state import State

COMMANDS = ('/diario', '/resumen', '/niveles', '/alertas', '/silencio')


class Planner:
    def __init__(self, directory, clock=time.time, calculator=calculate, diagnostic=False):
        if Path(directory).resolve() == Path('/data').resolve():
            raise ValueError('DAILY_OWN_STORAGE_REQUIRED')
        self.clock, self.calculator = clock, calculator
        self.state = State(directory, int(clock()*1000))
        root=Path(__file__).parent
        protocol=hashlib.sha256(b''.join((root/name).read_bytes().replace(b'\r\n',b'\n') for name in ('core.py','cycle.py','analysis.py','state.py'))).hexdigest()
        old=self.state.get('protocol_hash')
        if old is not None and old!=protocol:
            self.state.close()
            raise ValueError('DAILY_PROTOCOL_CHANGED_USE_NEW_STORE')
        self.state.put('protocol_hash',protocol)
        self.calculation_lock = threading.Lock()
        self.diagnostic = diagnostic

    def plan(self, refresh=False):
        now = int(self.clock()*1000)
        plan = self.state.get('plan')
        if plan:
            age = now - int(datetime.fromisoformat(plan['asof_utc']).timestamp()*1000)
            if not refresh and 0 <= age < 900_000:
                return plan
        with self.calculation_lock:
            now = int(self.clock()*1000)
            value = self.calculator(now)
            self.state.observe(value, now)
            try:
                print('IGOD_DAILY_STATUS=' + json.dumps(dict(status='HEALTHY' if value.get('bias')!='UNKNOWN' else 'DEGRADED',
                    bias=value.get('bias'), phase=(value.get('cycle') or {}).get('phase'), source=value.get('source'),
                    asof=value.get('asof_utc'), trade_authority='NONE'), separators=(',',':')), flush=True)
            except Exception:
                pass
            return value

    def command(self, command, identifier):
        now = int(self.clock()*1000)
        if not isinstance(command, str) or len(command)>100 or command.split()[0] not in COMMANDS:
            raise ValueError('DAILY_COMMAND_DENIED')
        if type(identifier) is not int or identifier<0:
            raise ValueError('DAILY_ID_INVALID')
        if not self.state.claim('command:'+str(identifier), now, 'manual'):
            return dict(deliver=False)
        name = command.split()[0]
        if name in ('/alertas','/silencio'):
            text = self.state.settings(command, now)
        else:
            plan = self.plan(refresh=True)
            text = render(plan, {'/diario':'full','/resumen':'summary','/niveles':'levels'}[name], int(self.clock()*1000))
        return dict(deliver=True, text=text, mode='SHADOW_ONLY', trade_authority='NONE')

    def notification(self):
        now = int(self.clock()*1000)
        hour=datetime.fromtimestamp(now/1000,timezone.utc).astimezone(ZoneInfo('Europe/Madrid')).hour
        if self.diagnostic and 8<=hour<22 and self.state.claim('DEPLOYMENT_TEST_V1',now,'technical'):
            return dict(deliver=True,id='DEPLOYMENT_TEST_V1',
                text='🧪 I-GOD | PRUEBA TÉCNICA PLAN DIARIO\nUn solo receptor: Guardian.\nPlanificador privado conectado. Prueba /diario, /resumen y /alertas.\nNo es una señal ni una orden.\nSHADOW ONLY. TRADE AUTHORITY: NONE.')
        plan = self.plan()
        key = self.state.due(plan, now)
        if not key:
            return dict(deliver=False)
        prefix = '⚠️ CANCELACIÓN DEL ESCENARIO ANTERIOR\nNo significa cierre de una posición real.\n' if key.startswith('critical:') else '🔔 RESUMEN PROGRAMADO\n'
        return dict(deliver=True, id=key, text=prefix+render(plan,'summary',now))


def handler(planner):
    class PrivateAPI(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, value, status=200, content_type='application/json'):
            body = value.encode() if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path=='/health':
                return self.respond(dict(alive=True,mode='SHADOW_ONLY',trade_authority='NONE'))
            if self.path=='/plan.json':
                return self.respond(planner.state.get('plan'))
            if self.path=='/':
                text=render(planner.state.get('plan'))
                return self.respond('<meta charset="utf-8"><title>I-GOD Diario</title><pre>'+html.escape(text)+'</pre>',content_type='text/html; charset=utf-8')
            self.send_error(404)

        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>2048:
                    raise ValueError
                data=json.loads(self.rfile.read(size))
                if self.path=='/command' and set(data)=={'command','update_id'}:
                    return self.respond(planner.command(data['command'],data['update_id']))
                if self.path=='/notifications' and data=={}:
                    return self.respond(planner.notification())
            except Exception:
                return self.respond(dict(deliver=False,error='DAILY_REQUEST_UNAVAILABLE'),503)
            self.send_error(404)
    return PrivateAPI


def main():
    if any(value and ('BITUNIX' in name or 'TELEGRAM' in name) for name,value in os.environ.items()):
        raise RuntimeError('DAILY_FORBIDDEN_CREDENTIALS')
    directory=os.getenv('DAILY_STATE_DIR','/daily-plan-data')
    planner=Planner(directory,diagnostic=os.getenv('DAILY_DEPLOY_TEST','false')=='true')
    class Server(ThreadingHTTPServer):
        address_family=socket.AF_INET6
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
            super().server_bind()
    server=Server(('::',8080),handler(planner))
    def refresh():
        while True:
            try:
                planner.plan()
            except Exception:
                try:
                    print('IGOD_DAILY_DEGRADED',flush=True)
                except Exception:
                    pass
            time.sleep(30)
    threading.Thread(target=refresh,daemon=True,name='daily-public-context').start()
    server.serve_forever()


if __name__=='__main__':
    main()
