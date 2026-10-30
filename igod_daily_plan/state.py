"""Independent durable preferences, observations and at-most-once dispatch claims."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from zoneinfo import ZoneInfo

DEFAULTS = dict(daily=False, hour='08:00', changes=False, critical=False,
                night=False, silent_until=0, baseline=None, last_change=0)


def signature(plan):
    cycle = plan.get('cycle') or {}
    return str((plan.get('bias'), cycle.get('phase'), cycle.get('pressure'), plan.get('reason_no_trade')))


class State:
    def __init__(self, directory, now):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(Path(directory) / 'daily.sqlite3'), check_same_thread=False)
        self.lock = threading.RLock()
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, claimed_at INTEGER, kind TEXT);
          CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, observed_at INTEGER, payload TEXT);
          CREATE TABLE IF NOT EXISTS phase_events(id INTEGER PRIMARY KEY, observed_at INTEGER, payload TEXT);
          CREATE TABLE IF NOT EXISTS phase_outcomes(event_id INTEGER, horizon INTEGER, observed_at INTEGER, payload TEXT,
            PRIMARY KEY(event_id,horizon));
        ''')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('preferences', json.dumps(DEFAULTS)))
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('started_at', str(now)))

    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def close(self):
        self.db.close()

    def put(self, key, value):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, json.dumps(value, allow_nan=False)))

    def claim(self, key, now, kind):
        with self.lock, self.db:
            return self.db.execute('INSERT OR IGNORE INTO claims VALUES (?,?,?)', (key, now, kind)).rowcount == 1

    def observe(self, plan, now):
        payload = json.dumps(plan, sort_keys=True, allow_nan=False)
        identifier = hashlib.sha256(payload.encode()).hexdigest()
        with self.lock, self.db:
            previous = self.get('plan')
            if previous:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('prior_plan', json.dumps(previous)))
            self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?)', (identifier, now, payload))
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('plan', payload))
            cycle=plan.get('cycle')
            recent=plan.get('daily_recent_closed') or []
            if cycle and recent:
                available=cycle['available_at']
                last=self.get('last_cycle')
                start=self.get('started_at')
                if available>start and (last is None or last.get('available_at')!=available) and last and last.get('phase')!=cycle['phase']:
                    event=dict(cycle=cycle, reference=plan.get('reference_close_15m'),
                               observed_at=now, framework='DIRECTIONAL_OBSERVATION_NOT_EXECUTION')
                    self.db.execute('INSERT OR IGNORE INTO phase_events VALUES (?,?,?)',(available,now,json.dumps(event)))
                self.put('last_cycle',cycle)
                reference=plan.get('reference_close_15m')
                reference_time=plan.get('reference_closed_at_utc')
                market_time=int(datetime.fromisoformat(reference_time).timestamp()*1000) if reference_time else 0
                for event_id,event_json in self.db.execute('SELECT id,payload FROM phase_events').fetchall():
                    event=json.loads(event_json)
                    for horizon in (1,3,5):
                        target=event['observed_at']+horizon*86400_000
                        if now>=target and market_time>=target and reference and event['reference']:
                            terminal=reference/event['reference']-1
                            feature=event['cycle']
                            side=feature['pressure'] if feature['phase'] in ('POSIBLE INICIO','ACELERACIÓN','POSIBLE REVERSIÓN') else (
                                'LONG' if feature.get('ao_slope',0)>0 else 'SHORT') if feature.get('countertrend_rebound') else None
                            signed=terminal*(1 if side=='LONG' else -1) if side in ('LONG','SHORT') else None
                            value=dict(forward_return=terminal,signed_return=signed,
                                       observed_at=now,market_close_used=market_time,
                                       reference_not_executable=True,costs_not_execution_results=True)
                            self.db.execute('INSERT OR IGNORE INTO phase_outcomes VALUES (?,?,?,?)',(event_id,horizon,now,json.dumps(value)))

    def due(self, plan, now):
        if not plan or plan.get('bias') == 'UNKNOWN':
            return None
        prefs = self.get('preferences')
        local = datetime.fromtimestamp(now / 1000, timezone.utc).astimezone(ZoneInfo('Europe/Madrid'))
        hour, minute = map(int, prefs['hour'].split(':'))
        quiet = local.hour >= 22 or local.hour < 8
        silent = prefs['silent_until'] == -1 or prefs['silent_until'] > now
        previous = self.get('prior_plan') or {}
        stop = (previous.get('invalidation') or {}).get('hard_stop_both_legs')
        price = plan.get('reference_close_15m')
        invalid = stop is not None and price is not None and (
            previous.get('bias') == 'SCENARIO_LONG' and price <= stop or
            previous.get('bias') == 'SCENARIO_SHORT' and price >= stop)
        if invalid and prefs['critical'] and (not quiet or prefs['night']):
            count = self.db.execute("SELECT count(*) FROM claims WHERE kind='critical' AND claimed_at>=?", (now-86400_000,)).fetchone()[0]
            key = 'critical:' + previous.get('asof_utc', '') + ':' + str(stop)
            if count < 2 and self.claim(key, now, 'critical'):
                return key
        minutes = local.hour * 60 + local.minute
        if prefs['daily'] and not quiet and not silent and 0 <= minutes - hour * 60 - minute < 10:
            key = 'daily:' + str(local.date())
            if self.claim(key, now, 'daily'):
                return key
        old = self.get('auto_baseline')
        current = signature(plan)
        if old is None:
            self.put('auto_baseline', current)
            return None
        if old == current:
            return None
        self.put('auto_baseline', current)
        if not prefs['changes'] or quiet or silent or now - prefs['last_change'] < 6 * 3600_000:
            return None
        count = self.db.execute("SELECT count(*) FROM claims WHERE kind='scenario' AND claimed_at>=?", (now-86400_000,)).fetchone()[0]
        if count >= 2:
            return None
        key = 'scenario:' + str(local.date()) + ':' + hashlib.sha256(current.encode()).hexdigest()
        if self.claim(key, now, 'scenario'):
            prefs['last_change'] = now
            self.put('preferences', prefs)
            return key
        return None

    def settings(self, command, now):
        p = self.get('preferences')
        parts = command.split()
        if parts[0] == '/silencio':
            if len(parts) == 1:
                p['silent_until'] = -1
            elif parts[1] == 'off':
                p['silent_until'] = 0
            elif parts[1].isdigit() and 1 <= int(parts[1]) <= 10080:
                p['silent_until'] = now + int(parts[1]) * 60_000
            else:
                return 'Uso: /silencio [minutos|off]'
        elif len(parts) == 2 and parts[1] in ('on', 'off'):
            p.update(daily=parts[1] == 'on', changes=False, critical=False, night=False)
            if parts[1] == 'on':
                p['silent_until'] = 0
        elif len(parts) == 3 and parts[1] == 'hora':
            try:
                hour, minute = map(int, parts[2].split(':'))
                assert 8 <= hour < 22 and 0 <= minute < 60
                p['hour'] = f'{hour:02}:{minute:02}'
            except (ValueError, AssertionError):
                return 'Hora inválida. Usa /alertas hora HH:MM, entre 08:00 y 21:59 Europe/Madrid.'
        elif len(parts) == 3 and parts[1] in ('diario', 'cambios', 'criticas', 'noche') and parts[2] in ('on', 'off'):
            p[dict(diario='daily', cambios='changes', criticas='critical', noche='night')[parts[1]]] = parts[2] == 'on'
        elif len(parts) > 1:
            return 'Uso: /alertas [on|off|diario on/off|cambios on/off|criticas on/off|noche on/off|hora HH:MM]'
        self.put('preferences', p)
        return ('🔔 AVISOS DEL PLAN DIARIO\n'
                f"Diario: {'ON' if p['daily'] else 'OFF'} · {p['hour']} Europe/Madrid\n"
                f"Cambios: {'ON' if p['changes'] else 'OFF'} · máximo 2/día, separación 6h\n"
                f"Críticos: {'ON' if p['critical'] else 'OFF'} · permiso nocturno: {'ON' if p['night'] else 'OFF'}\n"
                f"Silencio: {'ON' if p['silent_until'] == -1 or p['silent_until'] > now else 'OFF'}\n"
                'No afecta las protecciones ni alertas de Guardian/V8/ML RSI.\n'
                '/alertas diario on · /alertas cambios on · /alertas hora 08:00\n/silencio · /silencio off')
