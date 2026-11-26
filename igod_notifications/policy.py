"""Durable opportunity/incident notification lifecycle; never an execution gate."""
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3

VERSION='IGOD_SILENT_RADAR_V1'
OPPORTUNITY_KINDS={'PRE_LONG','PRE_SHORT','CONFIRMED','INVALIDATED'}
KINDS=OPPORTUNITY_KINDS|{'OBSERVATION','CRITICAL','RECOVERED'}
SOURCES={'guardian','manual_copilot','mlrsi','daily_plan','v8','experimental_shadow'}


def packed(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def identity(*parts):
    return hashlib.sha256(packed(parts).encode()).hexdigest()


def validate(event,now):
    if not isinstance(event,dict) or event.get('kind') not in KINDS or event.get('source') not in SOURCES:
        raise ValueError('NOTIFICATION_SCHEMA')
    if set(event)-{'id','kind','source','at','opportunity_id','slot','side','timeframe','context','factors','pending','price_confirmed','closed','what_changed','text','incident_id','severity','material','reason'}:
        raise ValueError('NOTIFICATION_UNKNOWN_FIELD')
    for key in ('id','what_changed'):
        if not isinstance(event.get(key),str) or not 0<len(event[key])<=500:
            raise ValueError('NOTIFICATION_SCHEMA')
    if type(event.get('at')) is not int or event['at']>now+30000 or event['at']<0:
        raise ValueError('NOTIFICATION_TIME')
    if len(packed(event).encode())>16000:
        raise ValueError('NOTIFICATION_TOO_LARGE')
    if event['kind'] in OPPORTUNITY_KINDS:
        if now-event['at']>1800000:
            raise ValueError('STALE_OPPORTUNITY_NOT_A_LIVE_ALERT')
        if event.get('side') not in ('LONG','SHORT') or event.get('closed') is not True:
            raise ValueError('OPPORTUNITY_CLOSED_EVIDENCE_REQUIRED')
        for key in ('opportunity_id','slot','timeframe'):
            if not isinstance(event.get(key),str) or not 0<len(event[key])<=150:
                raise ValueError('OPPORTUNITY_ID_REQUIRED')
        if event['kind']!='INVALIDATED':
            factors=event.get('factors')
            if not isinstance(factors,list) or len(set(factors))<2:
                raise ValueError('ISOLATED_INDICATOR_NOT_CONFLUENCE')
        if event['kind']=='CONFIRMED' and event.get('price_confirmed') is not True:
            raise ValueError('PRICE_CONFIRMATION_REQUIRED')
        if event['kind'].startswith('PRE_') and event['kind']!='PRE_'+event['side']:
            raise ValueError('SIDE_MISMATCH')
    if event['kind'] in ('CRITICAL','RECOVERED'):
        if not isinstance(event.get('incident_id'),str) or not event['incident_id']:
            raise ValueError('INCIDENT_ID_REQUIRED')
        if type(event.get('severity')) is not int or event['severity'] not in (1,2,3):
            raise ValueError('INCIDENT_SEVERITY')
    return event


class WriterLock:
    def __init__(self,path):
        self.stream=Path(path).open('a+b')
        self.stream.seek(0);self.stream.write(b'0');self.stream.flush();self.stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise ValueError('NOTIFICATION_WRITER_ALREADY_ACTIVE') from None

    def close(self):
        if not self.stream.closed:
            if os.name=='nt':
                import msvcrt
                self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            self.stream.close()


class Policy:
    """Single SQLite writer. Caller runs it on the notification worker only."""
    def __init__(self,directory):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        self.lock=WriterLock(directory/'writer.lock')
        try:
            self.db=sqlite3.connect(directory/'radar.sqlite3',timeout=1)
            self.db.row_factory=sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,decision TEXT,received_at INTEGER);
                CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY,slot TEXT,side TEXT,phase TEXT,at INTEGER,last_event TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS active_slot ON opportunities(slot) WHERE phase IN ('PRE_LONG','PRE_SHORT','CONFIRMED');
                CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,active INTEGER,severity INTEGER,material TEXT,last_sent INTEGER,event_at INTEGER);
                CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,priority INTEGER,payload TEXT,state TEXT,attempts INTEGER DEFAULT 0,next_due INTEGER DEFAULT 0,dependency TEXT);
                CREATE TABLE IF NOT EXISTS prefs(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS producer(key TEXT PRIMARY KEY,value TEXT);
            ''')
            check=self.db.execute('PRAGMA quick_check').fetchone()[0]
            if check!='ok':raise ValueError('NOTIFICATION_DB_INVALID')
            # Telegram has no idempotency token. Critical ambiguous sends retry;
            # opportunities become UNCERTAIN, rather than repeated on each reboot.
            self.db.execute("UPDATE outbox SET state=CASE WHEN priority=0 THEN 'PENDING' ELSE 'UNCERTAIN' END WHERE state='SENDING'")
            self.db.commit()
        except Exception:
            if hasattr(self,'db'):self.db.close()
            self.lock.close();raise

    def close(self):
        self.db.close();self.lock.close()

    def setting(self,key,value=None):
        if value is not None:
            with self.db:self.db.execute('INSERT OR REPLACE INTO prefs VALUES(?,?)',(key,packed(value)))
        row=self.db.execute('SELECT value FROM prefs WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else False

    def producer(self,key,value=None):
        if value is not None:
            with self.db:self.db.execute('INSERT OR REPLACE INTO producer VALUES(?,?)',(key,packed(value)))
        row=self.db.execute('SELECT value FROM producer WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else {}

    def active(self,slot):
        row=self.db.execute("SELECT * FROM opportunities WHERE slot=? AND phase IN ('PRE_LONG','PRE_SHORT','CONFIRMED')",(slot,)).fetchone()
        return dict(row) if row else None

    def ingest(self,event,now):
        validate(event,now)
        with self.db:
            old=self.db.execute('SELECT payload,decision FROM events WHERE id=?',(event['id'],)).fetchone()
            if old:
                if old['payload']!=packed(event):raise ValueError('EVENT_ID_COLLISION')
                return dict(decision=old['decision'],duplicate=True)
            kind=event['kind'];decision='OBSERVATION_ONLY';dependency=None;priority=1
            if kind in OPPORTUNITY_KINDS:
                row=self.db.execute('SELECT * FROM opportunities WHERE id=?',(event['opportunity_id'],)).fetchone()
                if kind.startswith('PRE_'):
                    if row:decision='PRE_ALREADY_RECORDED'
                    elif self.active(event['slot']):decision='ACTIVE_OPPORTUNITY_EXISTS'
                    else:
                        self.db.execute('INSERT INTO opportunities VALUES(?,?,?,?,?,?)',(event['opportunity_id'],event['slot'],event['side'],kind,event['at'],event['id']))
                        decision='ENQUEUE'
                elif not row:decision='NO_PRIOR_PREALERT'
                elif row['side']!=event['side'] or row['slot']!=event['slot']:decision='OPPORTUNITY_MISMATCH'
                elif event['at']<=row['at']:decision='NOT_A_LATER_CONFIRMATION'
                elif row['phase']=='INVALIDATED':decision='TERMINAL_NO_RESURRECTION'
                elif kind=='CONFIRMED' and row['phase']=='CONFIRMED':decision='CONFIRMATION_ALREADY_RECORDED'
                else:
                    dependency=row['last_event']
                    self.db.execute('UPDATE opportunities SET phase=?,at=?,last_event=? WHERE id=?',(kind,event['at'],event['id'],event['opportunity_id']))
                    decision='ENQUEUE'
                if decision=='ENQUEUE' and self.setting('silent'):
                    decision='OPPORTUNITY_MUTED'
            elif kind in ('CRITICAL','RECOVERED'):
                priority=0
                row=self.db.execute('SELECT * FROM incidents WHERE id=?',(event['incident_id'],)).fetchone()
                material=packed(event.get('material',{}))
                if row and event['at']<row['event_at']:
                    decision='STALE_INCIDENT_NO_RESURRECTION'
                elif kind=='RECOVERED':
                    if row and row['active']:
                        decision='ENQUEUE'
                        self.db.execute('UPDATE incidents SET active=0,event_at=? WHERE id=?',(event['at'],event['incident_id']))
                    else:decision='NO_ACTIVE_INCIDENT'
                else:
                    changed=not row or not row['active'] or event['severity']>row['severity'] or material!=row['material']
                    reminder=bool(row and now-row['last_sent']>=3600000)
                    if changed or reminder:
                        decision='ENQUEUE'
                        severity=max(event['severity'],row['severity']) if row and row['active'] else event['severity']
                        self.db.execute('INSERT OR REPLACE INTO incidents VALUES(?,?,?,?,?,?)',(event['incident_id'],1,severity,material,now,event['at']))
                    else:
                        decision='SAME_CRITICAL_INCIDENT'
                        self.db.execute('UPDATE incidents SET event_at=? WHERE id=?',(event['at'],event['incident_id']))
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(event['id'],kind,packed(event),decision,now))
            if decision=='ENQUEUE':
                self.db.execute('INSERT INTO outbox(id,priority,payload,state,dependency) VALUES(?,?,?,?,?)',(event['id'],priority,packed(event),'PENDING',dependency))
        return dict(decision=decision,duplicate=False)

    def next(self,now):
        with self.db:
            rows=self.db.execute("SELECT * FROM outbox WHERE state='PENDING' AND next_due<=? ORDER BY priority,rowid",(now,)).fetchall()
            for row in rows:
                if row['priority']!=0 and now-json.loads(row['payload'])['at']>1800000:
                    self.db.execute("UPDATE outbox SET state='SUPPRESSED' WHERE id=?",(row['id'],));continue
                if row['dependency']:
                    dependency=self.db.execute('SELECT state FROM outbox WHERE id=?',(row['dependency'],)).fetchone()
                    if not dependency or dependency['state'] in ('UNCERTAIN','SUPPRESSED'):
                        self.db.execute("UPDATE outbox SET state='SUPPRESSED' WHERE id=?",(row['id'],));continue
                    if dependency['state']!='SENT':continue
                if row['priority']!=0 and self.setting('silent'):
                    self.db.execute("UPDATE outbox SET state='SUPPRESSED' WHERE id=?",(row['id'],));continue
                self.db.execute("UPDATE outbox SET state='SENDING',attempts=attempts+1 WHERE id=?",(row['id'],))
                return dict(row)
        return None

    def finish(self,row,success,now):
        attempts=row['attempts']+1
        # A failed/ambiguous opportunity is not a reason for a message storm.
        state='SENT' if success else 'PENDING' if row['priority']==0 else 'UNCERTAIN'
        with self.db:self.db.execute('UPDATE outbox SET state=?,next_due=? WHERE id=?',(state,now+min(300000,1000*2**min(attempts,8)),row['id']))


def render(event):
    kind=event['kind']
    if kind in ('CRITICAL','RECOVERED'):
        header='🚨 I-GOD · SEGURIDAD' if kind=='CRITICAL' else '🛡️ I-GOD · CAMBIO DE SEGURIDAD'
        text=event.get('text') or event['what_changed']
        return (header+'\n'+text+'\n\nUn aviso no verifica un stop en el exchange.')[:3900]
    side=event['side']
    header={'PRE_LONG':'🟢 PRE-LONG','PRE_SHORT':'🔴 PRE-SHORT','CONFIRMED':'✅ CONFIRMED','INVALIDATED':'⚪ INVALIDATED'}[kind]
    context=' · '.join(str(k)+': '+str(v) for k,v in event.get('context',{}).items()) or 'No disponible'
    factors=', '.join(event.get('factors',[])) or 'Sin confluencia nueva'
    pending='; '.join(event.get('pending',[])) or 'Ninguna condición pendiente declarada'
    return ('📡 I-GOD · RADAR EXPERIMENTAL\n'+header+' · '+side+' · '+event['timeframe']+
        '\nCambio: '+event['what_changed']+'\nContexto: '+context+'\nFactores: '+factors+
        '\nPendiente: '+pending+'\nID: '+event['opportunity_id'][:12]+
        '\n\nSHADOW ONLY · NO ES UNA ORDEN\nTRADE AUTHORITY: NONE')[:3900]
