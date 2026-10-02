"""Prospective signal statistics only. No account client or trading capability."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import statistics
import subprocess
import threading
import time
from datetime import datetime, timezone
import requests

SOURCE = 'FORWARD_LIVE'
BASE = 'https://data-api.binance.vision/api/v3/klines'
STEP = 300000
HORIZONS = (1, 4, 12, 24, 48)
PAIRS = ((.005, .005), (.01, .005), (.01, .01), (.02, .01), (.03, .01))
QUALITIES = ('GOOD', 'CAUTION', 'POOR')
REASONS = ('CONFIRMED_RECLAIM', 'NEAR_RESISTANCE', 'NEAR_SUPPORT', 'EXTENDED',
           'WAIT_RECLAIM', 'INSUFFICIENT_EVIDENCE')


def runtime_git_sha():
    value = os.getenv('RAILWAY_GIT_COMMIT_SHA', '')
    if re.fullmatch('[0-9a-f]{40}', value):
        return value
    try:
        value = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL,
                                        timeout=2, text=True).strip()
        return value if re.fullmatch('[0-9a-f]{40}', value) else None
    except Exception:
        return None


def finite(value, positive=False):
    try:
        value = float(value)
        return value if math.isfinite(value) and (not positive or value > 0) else None
    except (TypeError, ValueError, OverflowError):
        return None


def packet(data, now_ms, mark=None):
    """Whitelist, copy and validate market fields; arbitrary payloads are ignored."""
    bias = data.get('bias')
    if bias not in ('WAIT', 'LONG_ALLOWED', 'SHORT_ALLOWED'):
        return None
    levels = data.get('market_levels') or {}
    closed = finite(levels.get('reference_time'))
    reference = finite(levels.get('reference_price'), True)
    if closed is None or reference is None or not 0 <= now_ms - closed < 900000:
        return None
    if data.get('trend4') not in ('BULL', 'BEAR') or data.get('trend1') not in ('BULL', 'BEAR'):
        return None
    if data.get('momentum') not in ('GREEN', 'NEUTRAL', 'RED') or data.get('structure') not in ('BULLISH', 'BEARISH', 'MIXED'):
        return None
    ratio = finite(data.get('taker_buy'))
    if ratio is None or not 0 <= ratio <= 1:
        return None
    structural = levels.get('structural') or {}
    return dict(bias=bias, signal_time=int(now_ms), closed_15m_time=int(closed), reference_price=reference,
                public_mark=finite(mark, True), trend4=data['trend4'], trend1=data['trend1'],
                ml_rsi=data['momentum'], taker_buy=ratio, structure=data['structure'],
                volatility=data.get('volatility') if data.get('volatility') in ('NORMAL', 'ELEVATED', 'HIGH') else 'UNKNOWN',
                entry_quality=data.get('entry_quality') if data.get('entry_quality') in QUALITIES else 'CAUTION',
                entry_reason=data.get('entry_reason') if data.get('entry_reason') in REASONS else 'INSUFFICIENT_EVIDENCE',
                R1=finite(levels.get('resistance'), True), S1=finite(levels.get('support'), True),
                R2=finite(structural.get('resistance'), True), S2=finite(structural.get('support'), True),
                atr_1h=finite(levels.get('atr_1h'), True))


def evaluate(signal, rows, hours, now_ms):
    """Closed 5m OHLC, strictly after observation; same-bar touches are censored."""
    start = ((signal['signal_time'] + STEP - 1) // STEP) * STEP
    end = ((signal['signal_time'] + hours * 3600000) // STEP) * STEP
    result = dict(event_id=signal['event_id'], hours=hours, source=SOURCE,
                  status='PENDING', coverage_start=start, coverage_end=end)
    if now_ms < signal['signal_time'] + hours * 3600000:
        return result
    expected = list(range(start, end, STEP))
    selected = [r for r in rows if start <= r[0] < end and r[0] + STEP <= now_ms]
    if [r[0] for r in selected] != expected or not selected:
        return dict(result, status='INCOMPLETE', reason='MISSING_CLOSED_CANDLES')
    for row in selected:
        if len(row) != 5 or any(finite(v) is None for v in row) or row[0] % STEP or not (
                0 < row[3] <= min(row[1], row[4]) <= max(row[1], row[4]) <= row[2]):
            return dict(result, status='INCOMPLETE', reason='INVALID_CANDLES')
    reference = signal['reference_price']
    long = signal['side'] == 'LONG'
    favorable = [(r[2] / reference - 1) if long else (1 - r[3] / reference) for r in selected]
    adverse = [(r[3] / reference - 1) if long else (1 - r[2] / reference) for r in selected]
    passages = {}
    for up, down in PAIRS:
        outcome = 'NEITHER'
        for good, bad in zip(favorable, adverse):
            hit_up, hit_down = good >= up - 1e-12, bad <= -down + 1e-12
            if hit_up or hit_down:
                outcome = 'AMBIGUOUS' if hit_up and hit_down else 'WIN' if hit_up else 'LOSS'
                break
        passages[f'{up:g}/{down:g}'] = outcome
    close = selected[-1][4]
    return dict(result, status='COMPLETE', directional_return=close / reference - 1 if long else 1 - close / reference,
                mfe=max(0., max(favorable)), mae=min(0., min(adverse)), first_passage=passages,
                candles=len(selected))


class AuditStore:
    """Local fsync/atomic replace, process lock and append-before-state recovery.

    This does not establish that a hosting volume survives container replacement.
    A torn final JSONL fragment is truncated; complete records remain immutable.
    """
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = (self.root / 'audit.lock').open('a+b')
        self.lock.seek(0)
        self.lock.write(b'0')
        self.lock.flush()
        self.lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = self.root / 'state.json'
            self.state = json.loads(path.read_text('utf-8')) if path.exists() else {
                'schema': 1, 'episode': 'UNOBSERVED', 'sequence': 0, 'last_observation': -1}
            self.signals = self.read('signals')
            self.outcomes = {}
            for row in self.read('outcomes'):
                self.outcomes[(row['event_id'], row['hours'])] = row
            self.snapshots = self.read('snapshots')
            for row in self.signals:
                if row['state_after']['last_observation'] > self.state['last_observation']:
                    self.state.update(row['state_after'])
            if len({row['event_id'] for row in self.signals}) != len(self.signals):
                raise ValueError('AUDIT_DUPLICATE_EVENT')
        except Exception:
            self.close()
            raise RuntimeError('AUDIT_STORAGE_UNAVAILABLE') from None

    def close(self):
        if not self.lock.closed:
            self.lock.close()

    def read(self, name):
        path = self.root / (name + '.jsonl')
        if not path.exists():
            return []
        raw = path.read_bytes()
        if raw and not raw.endswith(b'\n'):
            end = raw.rfind(b'\n') + 1
            with path.open('r+b') as stream:
                stream.truncate(end)
                stream.flush()
                os.fsync(stream.fileno())
            raw = raw[:end]
        return [json.loads(line) for line in raw.decode('utf-8').splitlines()]

    def append(self, name, row):
        if name not in ('signals', 'outcomes', 'snapshots'):
            raise ValueError('AUDIT_JOURNAL_INVALID')
        with (self.root / (name + '.jsonl')).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        self.sync_directory()

    def save(self):
        path = self.root / 'state.json.tmp'
        with path.open('w', encoding='utf-8') as stream:
            json.dump(self.state, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.root / 'state.json')
        self.sync_directory()

    def sync_directory(self):
        if os.name != 'nt':
            descriptor = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


class PublicFiveMinuteData:
    def __init__(self, transport=None):
        self.http = transport or requests.Session()

    def candles(self, signal, now_ms):
        start = ((signal['signal_time'] + STEP - 1) // STEP) * STEP
        end = min(now_ms, signal['signal_time'] + 48 * 3600000)
        response = self.http.get(BASE, params={'symbol': 'BTCUSDT', 'interval': '5m',
                                               'startTime': start, 'endTime': end, 'limit': 1000},
                                 timeout=(2, 4), allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError('AUDIT_PUBLIC_DATA_UNAVAILABLE')
        raw = response.json()
        if not isinstance(raw, list):
            raise RuntimeError('AUDIT_PUBLIC_DATA_INVALID')
        rows = []
        for row in raw:
            if not isinstance(row, list) or len(row) < 7:
                raise RuntimeError('AUDIT_PUBLIC_DATA_INVALID')
            if int(row[6]) != int(row[0]) + STEP - 1:
                raise RuntimeError('AUDIT_PUBLIC_DATA_INVALID')
            if int(row[0]) + STEP <= now_ms:
                rows.append([float(value) for value in row[:5]])
        return rows


class StatsCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.value = None

    def publish(self, value):
        with self.lock:
            self.value = copy.deepcopy(value)

    def read(self):
        with self.lock:
            return copy.deepcopy(self.value)


def statistics_snapshot(store, now_ms):
    def cohort(signals):
        completed = [store.outcomes[(s['event_id'], 24)] for s in signals
                     if store.outcomes.get((s['event_id'], 24), {}).get('status') == 'COMPLETE']
        incomplete = sum(store.outcomes.get((s['event_id'], 24), {}).get('status') == 'INCOMPLETE' for s in signals)
        pairs = {}
        for up, down in PAIRS:
            key = f'{up:g}/{down:g}'
            observations = [row['first_passage'][key] for row in completed]
            pairs[key] = dict(wins=observations.count('WIN'), eligible=len(observations) - observations.count('AMBIGUOUS'),
                              ambiguous=observations.count('AMBIGUOUS'))
        return dict(n=len(signals), mature=len(completed), incomplete=incomplete,
                    pending=len(signals) - len(completed) - incomplete, pairs=pairs,
                    median_return=statistics.median(r['directional_return'] for r in completed) if completed else None,
                    median_mfe=statistics.median(r['mfe'] for r in completed) if completed else None,
                    median_mae=statistics.median(r['mae'] for r in completed) if completed else None)
    windows = {}
    for window, days in (('all', None), ('30d', 30), ('90d', 90)):
        signals = [s for s in store.signals if s['source'] == SOURCE and s['signal_time'] <= now_ms
                   and (days is None or s['signal_time'] >= now_ms - days * 86400000)]
        windows[window] = {'ALL': cohort(signals)}
        for quality in QUALITIES:
            windows[window][quality] = cohort([s for s in signals if s['entry_quality'] == quality])
        for side in ('LONG', 'SHORT'):
            windows[window][side] = cohort([s for s in signals if s['side'] == side])
    return dict(timestamp=now_ms, source=SOURCE, windows=windows,
                lost_observations=store.state.get('lost_observations', 0),
                period_start=min((s['signal_time'] for s in store.signals if s['source'] == SOURCE), default=None),
                completed_horizons={str(h): sum(row['hours'] == h and row['status'] == 'COMPLETE'
                                               for row in store.outcomes.values() if row['source'] == SOURCE) for h in HORIZONS},
                durability='LOCAL_FSYNC_ONLY_HOST_VOLUME_UNVERIFIED')


class ForwardAudit:
    """A separate worker: observation/outcomes never run inside capital protection."""
    def __init__(self, directory, public_data=None, clock=time.time, git_sha=None):
        self.store = AuditStore(directory)
        self.public_data = public_data or PublicFiveMinuteData()
        self.clock = clock
        self.git_sha = git_sha if isinstance(git_sha, str) and re.fullmatch('[0-9a-f]{40}', git_sha) else None
        self.stats_cache = StatsCache()
        self.queue = queue.Queue(maxsize=256)
        self.stop_event = threading.Event()
        self.worker = None
        self.health_lock = threading.Lock()
        self.lost_observations = self.store.state.get('lost_observations', 0)
        self.gap_after = self.store.state.get('observation_gap_after', -1)
        self.gap_pending = self.store.state.get('gap_pending', False)
        self.stats_cache.publish(statistics_snapshot(self.store, int(self.clock() * 1000)))

    def observe(self, value):
        """Single-worker operation. Episode identity is durable before state save."""
        if value is None or value['signal_time'] <= self.store.state['last_observation']:
            return None
        old = self.store.state['episode']
        new = value['bias']
        after = dict(episode=new, sequence=self.store.state['sequence'], last_observation=value['signal_time'])
        event = None
        # Initial already-active direction is not an observed transition.
        if new != 'WAIT' and old in ('WAIT', 'LONG_ALLOWED', 'SHORT_ALLOWED') and old != new:
            after['sequence'] += 1
            identity = f"{after['sequence']}:{value['signal_time']}:{new}"
            event = dict(value, event_id=hashlib.sha256(identity.encode()).hexdigest(), source=SOURCE,
                         side='LONG' if new == 'LONG_ALLOWED' else 'SHORT',
                         software_version='MANUAL_COPILOT_V1', git_sha=self.git_sha,
                         explanation=f"4H {value['trend4']}; 1H {value['trend1']}; ML RSI {value['ml_rsi']}; "
                                     f"taker buy {value['taker_buy']:.1%}; 15m {value['structure']}; "
                                     f"entry {value['entry_quality']} / {value['entry_reason']}",
                         state_after=after)
            self.store.append('signals', event)
            self.store.signals.append(copy.deepcopy(event))
        self.store.state.update(after)
        self.store.save()
        return copy.deepcopy(event)

    def refresh(self, now_ms):
        pending = [s for s in self.store.signals if now_ms >= s['signal_time'] + 3600000
                   and any(self.store.outcomes.get((s['event_id'], h), {}).get('status') != 'COMPLETE' for h in HORIZONS)]
        # Bounded round robin prevents a missing ancient gap starving new events.
        offset = self.store.state.get('outcome_cursor', 0) % max(1, len(pending))
        ordered = pending[offset:] + pending[:offset]
        for signal in ordered[:20]:
            try:
                rows = self.public_data.candles(signal, now_ms)
            except Exception:
                continue  # unavailable is not a loss; retry later
            for hours in HORIZONS:
                key = (signal['event_id'], hours)
                prior = self.store.outcomes.get(key)
                if prior and prior['status'] == 'COMPLETE':
                    continue
                outcome = evaluate(signal, rows, hours, now_ms)
                if outcome['status'] != 'PENDING' and outcome != prior:
                    self.store.append('outcomes', outcome)
                    self.store.outcomes[key] = outcome
        self.store.state['outcome_cursor'] = offset + 20
        summary = statistics_snapshot(self.store, now_ms)
        day = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime('%Y-%m-%d')
        if not any(row['day'] == day for row in self.store.snapshots):
            row = dict(day=day, statistics=summary)
            self.store.append('snapshots', row)
            self.store.snapshots.append(row)
        self.store.save()
        self.stats_cache.publish(summary)

    def submit(self, data, now_ms, mark=None):
        value = packet(data, now_ms, mark)
        if value is not None:
            try:
                self.queue.put_nowait(value)
                return True
            except queue.Full:
                with self.health_lock:
                    self.lost_observations += 1
                    self.gap_after, self.gap_pending = int(now_ms), True
                self.stats_cache.publish(None)
                print('COPILOT_AUDIT_QUEUE_FULL', flush=True)
        return False

    def start(self):
        if self.worker is None:
            self.worker = threading.Thread(target=self._run, daemon=True, name='copilot-forward-audit')
            self.worker.start()

    def close(self):
        self.stop_event.set()
        if self.worker is not None:
            self.worker.join(timeout=6)
        if self.worker is None or not self.worker.is_alive():
            self.store.close()

    def _run(self):
        due = 0
        try:
            while not self.stop_event.is_set():
                value = None
                try:
                    value = self.queue.get(timeout=.5)
                except queue.Empty:
                    pass
                with self.health_lock:
                    self.store.state.update(lost_observations=self.lost_observations,
                                            observation_gap_after=self.gap_after)
                    if self.gap_pending and value is not None and value['signal_time'] > self.gap_after:
                        self.store.state['episode'] = 'UNOBSERVED'
                        self.gap_pending = False
                    self.store.state['gap_pending'] = self.gap_pending
                self.observe(value)
                now = int(self.clock() * 1000)
                if now >= due:
                    self.refresh(now)
                    due = now + STEP
                else:
                    self.stats_cache.publish(statistics_snapshot(self.store, now))
        except Exception:
            self.stats_cache.publish(None)
            print('COPILOT_AUDIT_UNAVAILABLE', flush=True)
        finally:
            self.store.close()


def render_stats(snapshot, window='all', now_ms=None):
    if not snapshot or window not in ('all', '30d', '90d'):
        return ('📊 COPILOT — RESULTADOS FORWARD\nSin registro forward verificado disponible.\n'
                'Esto mide señales, NO tu rentabilidad real.\nNo permite abrir ni cerrar operaciones.')
    lines = ['📊 COPILOT — RESULTADOS FORWARD', '⚠️ Esto mide señales del sistema. NO es tu rentabilidad real.',
             'Fuente: FORWARD_LIVE | Ventana: ' + window]
    if snapshot.get('lost_observations', 0):
        lines.append(f"⚠️ Cobertura incompleta: {snapshot['lost_observations']} observaciones perdidas; no asumir registro de todas las señales.")
    if snapshot['period_start'] is not None:
        lines.append('Registro desde: ' + datetime.fromtimestamp(snapshot['period_start'] / 1000, timezone.utc).strftime('%d/%m/%Y'))
    else:
        lines.append('Todavía no hay transiciones confirmadas registradas.')
    age = max(0, ((now_ms or snapshot['timestamp']) - snapshot['timestamp']) / 1000)
    lines.append(f'Estadísticas actualizadas hace: {age:.0f} s')
    if age > 600:
        lines.append('⚠️ Auditoría desactualizada; no usar para una decisión de entrada.')
    for name, title in (('ALL', '🧭 TODAS LAS DIRECCIONES CONFIRMADAS'), ('GOOD', '🎯 ENTRY QUALITY = GOOD'),
                        ('CAUTION', '🟠 ENTRY QUALITY = CAUTION'), ('POOR', '🔴 ENTRY QUALITY = POOR'),
                        ('LONG', '🟢 LONG'), ('SHORT', '🔴 SHORT')):
        row = snapshot['windows'][window][name]
        lines += ['\n' + title, f"n={row['n']} | 24h maduros: {row['mature']} | pendientes: {row['pending']} | incompletos: {row['incomplete']}"]
        if row['mature'] < 10:
            lines.append('⚠️ Muy pocos casos para sacar conclusiones')
        elif row['mature'] < 20:
            lines.append('⚠️ Muestra todavía pequeña')
        for key, caption in (('0.01/0.01', '+1% antes de -1%'), ('0.02/0.01', '+2% antes de -1%')):
            pair = row['pairs'][key]
            result = f"{pair['wins'] / pair['eligible']:.1%} (n={pair['eligible']})" if pair['eligible'] else 'Sin casos evaluables (n=0)'
            lines.append(caption + ': ' + result)
        if name == 'ALL':
            for key, caption in (('median_return', 'Mediana retorno direccional 24h'),
                                 ('median_mfe', 'Mediana MFE 24h'), ('median_mae', 'Mediana MAE 24h')):
                lines.append(caption + ': ' + (f"{row[key]:+.2%}" if row[key] is not None else 'Sin datos maduros'))
    lines += ['\nToques simultáneos en una vela: ambiguos, excluidos del denominador.',
              'No alcanzar ninguna barrera dentro de 24h no cuenta como éxito.',
              'Estadísticas descriptivas; no incluyen entradas/salidas, costes ni rentabilidad de cuenta.',
              'Persistencia del volumen de alojamiento NO verificada.']
    return '\n'.join(lines)
