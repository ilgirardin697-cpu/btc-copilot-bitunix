"""Independent process, disabled by default. Only private read-only health/report."""
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import threading

from .clock import Clock
from .features import MINUTE,schedule
from .frozen import verify_freeze
from .journal import Store,EvidenceError,safe_error
from .market import PublicSpot
from .observer import Observer,days,settings
from .reports import derive


@dataclass(frozen=True)
class Config:
    enabled: bool=False
    data_dir: Path=Path('/price-observer-data')
    source_sha: str=''
    port: int=8080

    @classmethod
    def from_env(cls,env):
        # Explicit gets only. Never enumerate or consume account/Telegram secrets.
        flag=env.get('PRICE_OBSERVER_ENABLED','false').lower()
        if flag not in ('true','false'):raise EvidenceError('INVALID_ENABLED_FLAG')
        source=env.get('RAILWAY_GIT_COMMIT_SHA','') or env.get('PRICE_OBSERVER_SOURCE_SHA','')
        try:port=int(env.get('PORT','8080'))
        except (TypeError,ValueError):raise EvidenceError('INVALID_PORT') from None
        if not 1<=port<=65535:raise EvidenceError('INVALID_PORT')
        if flag=='true' and not re.fullmatch('[0-9a-f]{40}',source):raise EvidenceError('REVIEWED_SOURCE_SHA_REQUIRED')
        return cls(enabled=flag=='true',source_sha=source,port=port)


class Application:
    def __init__(self,config,clock=None,market_factory=PublicSpot,mount_check=None,sink=None):
        self.config=config;self.clock=clock or Clock();self.store=None;self.observer=None
        self.status='DISABLED';self.error=None;self.report=None;self.last_log=None
        self.sink=sink or (lambda s:print(s,flush=True));self.mutex=threading.RLock()
        self.last_report=0;self.last_tip=None;self.next_work=0
        self.mount_check=mount_check or (lambda p:os.path.ismount(p))
        verify_freeze()
        if config.enabled:
            try:
                if not self.mount_check(config.data_dir):raise EvidenceError('INDEPENDENT_PERSISTENT_VOLUME_REQUIRED')
                self.store=Store(config.data_dir/'IGOD_PRICE_BINANCE_FORWARD_V1',self.clock)
                self.observer=Observer(self.store,market_factory(self.store,self.clock),self.clock,config.source_sha)
                self.status='HEALTHY'
            except Exception as error:
                self.error=self.safe_code(error);self.status='JOURNAL_INVALID' if self.error=='JOURNAL_INVALID_NO_REPAIR' else 'DEGRADED'
                if self.store:self.store.close();self.store=None
        self.refresh_report()

    @staticmethod
    def safe_code(error):
        return safe_error(error)

    def refresh_report(self):
        rows=self.store.snapshot() if self.store else []
        report=derive(rows,self.clock.now_ms())
        report.update(service_status=self.status,last_error_code=self.error)
        if self.config.enabled and self.store is None:
            report.update(prediction_records=None,durable_prediction_records=None,complete_cycles=None,
                          outcome_records=None,evidence='UNAVAILABLE',status='EVIDENCE_UNAVAILABLE')
        with self.mutex:self.report=report
        self.last_report=self.clock.now_ms();self.last_tip=rows[-1]['record_hash'] if rows else None
        if self.store:
            try:self.store.write_report(report)
            except OSError:self.error='DERIVED_REPORT_WRITE_FAILED'

    def public_status(self):
        rows=self.store.snapshot() if self.store else []
        now=self.clock.now_ms();p=settings();future=[]
        for d in days(p['first_cycle'],p['last_cycle']):
            s=schedule(d)
            for m in p['anchors']:
                t=s['radar']+m*MINUTE+2000
                if t>now:future.append(t)
            if s['end']+2000>now:future.append(s['end']+2000)
        with self.mutex:
            report=self.report or {}
            return dict(service=p['service'],status=self.status,error_code=self.error,
                protocol_version=p['protocol'],origin=p['origin'],trade_authority='NONE',
                model_version=p['model_version'],model_hash_prefix=p['model_sha256'][:12],
                journal_records=None if self.config.enabled and self.store is None else len(rows),
                journal_tip_prefix=rows[-1]['record_hash'][:12] if rows else None,
                predictions=report.get('prediction_records',0),durable_predictions=report.get('durable_prediction_records',0),
                complete_cycles=report.get('complete_cycles',0),missed_anchors=report.get('missed_anchors',0),
                outcome_records=report.get('outcome_records',0),next_due=min(future) if future else None,
                revised_cycles=report.get('revised_cycles',0),ambiguous_cycles=report.get('ambiguous_cycles',0),
                evidence=report['evidence'] if report.get('evidence') in ('INSUFFICIENT','UNAVAILABLE') else 'REVIEW_REQUIRED',
                report_generated_at=report.get('generated_at'),probabilities_validated=False,
                coverage_matured=report.get('coverage_matured'),
                brier=(report.get('metrics') or {}).get('brier'),logloss=(report.get('metrics') or {}).get('logloss'),
                macro_ece=((report.get('metrics') or {}).get('calibration') or {}).get('macro_ece'))

    def emit_status(self):
        value=self.public_status()
        key=(value['status'],value['error_code'],value['journal_records'],value['journal_tip_prefix'])
        if key!=self.last_log:
            try:self.sink('IGOD_PRICE_OBSERVER_STATUS='+json.dumps(value,separators=(',',':')))
            except Exception:pass
            self.last_log=key

    def tick(self):
        if not self.config.enabled:return
        if not self.observer:
            self.emit_status();return
        now=self.clock.now_ms()
        if now<self.next_work:return
        try:
            self.observer.tick();self.status=self.observer.status;self.error=self.observer.last_code
            self.next_work=now+1000
        except Exception as error:
            self.status='DEGRADED';self.error=self.safe_code(error);self.next_work=self.clock.now_ms()+60000
            if self.store and not self.store.poisoned:
                try:
                    meta=getattr(error,'meta',None)
                    self.store.append('FAILURE','SERVICE_FAILURE:'+str(self.clock.now_ms()),
                        dict(phase='SCHEDULER',code=self.error,raw_refs=[meta['raw_sha256']] if meta else []))
                except Exception:pass
        tip=self.store.rows[-1]['record_hash'] if self.store and self.store.rows else None
        if tip!=self.last_tip or now-self.last_report>=3600000:
            try:self.refresh_report()
            except Exception:self.error='DERIVED_REPORT_UNAVAILABLE'
        self.emit_status()

    def close(self):
        if self.store:self.store.close()


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/health':
                body=dict(service='igod-killzone-price-observer',alive=True,status=app.status,trade_authority='NONE')
            elif self.path=='/status':body=app.public_status()
            elif self.path=='/report':
                with app.mutex:body=app.report
            else:
                self.send_error(404);return
            raw=json.dumps(body,allow_nan=False,separators=(',',':')).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def do_POST(self):self.send_error(405)
        def do_PUT(self):self.send_error(405)
        def do_DELETE(self):self.send_error(405)
    return Handler


def main():
    # Default service startup is OFF and has no network/storage activity.
    if len(sys.argv)!=1:raise SystemExit('NO_MANUAL_CAPTURE_OR_CLOCK_OVERRIDE_SUPPORTED')
    app=Application(Config.from_env(os.environ));stop=threading.Event()
    class DualServer(ThreadingHTTPServer):
        address_family=socket.AF_INET6
        daemon_threads=True
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
            super().server_bind()
    server=DualServer(('::',app.config.port),handler_for(app))
    def loop():
        while not stop.is_set():
            app.tick();stop.wait(1)
    worker=threading.Thread(target=loop,name='price-observer',daemon=True);worker.start()
    def shutdown(*args):
        stop.set();threading.Thread(target=server.shutdown,daemon=True).start()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,shutdown)
    try:server.serve_forever(poll_interval=.5)
    finally:stop.set();worker.join(timeout=35);server.server_close();app.close()
