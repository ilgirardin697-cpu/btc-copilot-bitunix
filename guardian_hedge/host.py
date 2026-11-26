"""Passive, bounded reader. Never receives a trading client or journal writer."""
import copy
import hashlib
import json
import os
import queue
import re
import threading
import time
from .client import Reader
from .model import ERROR_CODES,Unverified

_host=None

def eligible(config):
    return (os.getenv('GUARDIAN_HEDGE_READONLY_ENABLED','false')=='true' and config.mode=='SHADOW'
        and config.allow_sl is False and config.allow_close is False
        and all(os.getenv(k,'false').lower()=='false' for k in ('GUARDIAN_CAPITAL_V2_ENABLED','GUARDIAN_CAPITAL_V2_EXECUTION','V8_LIVE_EXECUTION')))

class Host:
    def __init__(self,reader,clock=time.time):
        self.reader,self.clock=reader,clock;self.lock=threading.Lock();self.stop=threading.Event()
        self.value=None;self.invalidated=0;self.legacy_cause=None;self.error='READ_PENDING'
        self.coherent_count=0;self.coherent_key=None;self.coherent_at=0
        self.started=False
        self.thread=threading.Thread(target=self.run,daemon=True,name='guardian-hedge-readonly')

    def read(self):
        with self.lock:
            value=copy.deepcopy(self.value);error=self.error
        if value and value.get('read_complete') is True and 0<=self.clock()-value['completed_at']<=30:return value
        return dict(read_complete=False,completed_at=self.clock(),error=error if error else 'READ_STALE')

    def legacy(self,cause):
        with self.lock:
            self.legacy_cause=cause
            if cause not in ('AMBIGUOUS_POSITIONS',None):
                self.invalidated=self.clock();self.value=None;self.error='LEGACY_PRIVATE_READ_FAILED';self.coherent_count=0

    def refresh(self):
        try:
            value=self.reader.collect()
            with self.lock:
                if value['started_at']<self.invalidated:raise Unverified('READ_INVALIDATED_DURING_COLLECTION')
                key=json.dumps([(p['position_id'],str(p['qty']),str(p['entry']),p['coverage']) for p in value['positions']],sort_keys=True,default=str)
                if not value.get('pnl_reconciled'):self.coherent_count=0
                elif value['completed_at']>self.coherent_at:
                    self.coherent_count=self.coherent_count+1 if key==self.coherent_key else 1
                self.coherent_key=key;self.coherent_at=value['completed_at']
                value['consistency_confirmed']=value.get('pnl_reconciled') is True and self.coherent_count>=2
                self.value=copy.deepcopy(value);self.error=None
        except Exception as error:
            code=str(error)
            with self.lock:
                self.value=None;self.coherent_count=0;self.error=code if isinstance(error,Unverified) and code in ERROR_CODES else 'READ_UNAVAILABLE'

    def run(self):
        while not self.stop.is_set():
            self.refresh();self.stop.wait(15)

def install(guardian):
    global _host
    if not eligible(guardian.config):return
    # Fresh, independent session. No reuse of a client with POST capabilities.
    try:
        if _host is None:_host=Host(Reader(os.getenv('BITUNIX_API_KEY',''),os.getenv('BITUNIX_API_SECRET','')))
    except Exception:_host=None  # Cannot interrupt the existing protection path.

def intercept_ambiguous(guardian,key,notice):
    try:return _intercept_ambiguous(guardian,key,notice)
    except Exception:return False  # A read-view failure must retain the old alert.

def _intercept_ambiguous(guardian,key,notice):
    if _host is None or not eligible(guardian.config) or not key.startswith('blind:'):return False
    cause=notice.get('cause') if isinstance(notice,dict) else None
    _host.legacy(cause)
    coordinator=getattr(guardian.telegram,'host',None)
    if cause!='AMBIGUOUS_POSITIONS' or coordinator is None or coordinator.failed or not coordinator.ready.is_set():return False
    value=_host.read()
    return (value.get('read_complete') is True and value.get('consistency_confirmed') is True and len(value['positions'])>1
        and all(p['position_mode']=='HEDGE' for p in value['positions']))

def after_cycle(guardian):
    if _host is None or not eligible(guardian.config):return
    if not _host.started:
        _host.started=True
        try:
            if _host.thread.ident is None:_host.thread.start()
        except Exception:
            with _host.lock:_host.error='READ_UNAVAILABLE';_host.value=None
    value=_host.read();guardian.command_snapshot.publish_readonly(value)
    coordinator=getattr(guardian.telegram,'host',None)
    if coordinator is None:return  # Original critical route is still untouched.
    from igod_notifications.policy import identity
    facts=dict(verified=value.get('read_complete') is True,at=int(value['completed_at']*1000),legacy_cause=_host.legacy_cause)
    if facts['verified']:
        facts['managed']=any(p['position_mode']=='HEDGE' for p in value['positions']) and len(value['positions'])>1
        facts['account_confirmed']=value.get('consistency_confirmed') is True
        facts['positions']=[dict(ref=identity(p['position_id']),side=p['side'],symbol=p['symbol'],coverage=p['coverage']['status'],
            coverage_fingerprint=hashlib.sha256(json.dumps(dict(qty=str(p['qty']),orders=p['coverage']['sl']),sort_keys=True,default=str).encode()).hexdigest()) for p in value['positions']]
        facts['risk_reasons']=value['risk']['reasons']
    try:coordinator.queue.put_nowait(('hedge',facts,None))
    except Exception:
        from igod_notifications.adapters import event
        coordinator.fallback.submit(event('guardian','CRITICAL',int(_host.clock()*1000),'Lectura HEDGE/CROSS no verificable',
            incident_id='guardian:hedge-notifications',severity=3,material={'code':'HEDGE_NOTIFICATION_UNVERIFIABLE'},text='No se pudo reconciliar la notificación HEDGE/CROSS. Protección no verificable.'))

def shutdown():
    global _host
    if _host is not None:_host.stop.set()
    _host=None
