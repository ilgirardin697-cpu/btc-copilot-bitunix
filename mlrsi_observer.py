"""Passive public-market worker, wholly separate from executor authorization.

Exact BackQuant TradingView parity is NOT proven. No reference to an account,
plan, trading client or operational state is accepted by this component.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import math
import os
from itertools import groupby
import threading
import time
from mlrsi_math import CAPTURED_CONFIG, CONFIG_VERSION, TIMEFRAMES, CausalSeries, ResearchEvents
from mlrsi_public import PublicHistory, atomic_json, validate_candles
import mlrsi_telegram as presentation

OBSERVER_VERSION = 'V7.3.8.7_MLRSI_1'
EVENT_NAMES = {'GREEN_CROSS', 'RED_CROSS', 'GREEN_RESUME', 'RED_RESUME', 'COLOR_CHANGE',
               'APPROACHING_GREEN', 'APPROACHING_RED', 'PROVISIONAL_GREEN', 'PROVISIONAL_RED',
               'CONFLUENCE_3OF3_GREEN', 'CONFLUENCE_3OF3_RED', 'CONFLUENCE_EXIT_GREEN', 'CONFLUENCE_EXIT_RED'}


def utc(stamp):
    return datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()


@dataclass(frozen=True)
class ObserverConfig:
    enabled: bool = True
    telegram_alerts: bool = True
    approaching_enabled: bool = True
    approach_distance: float = 1.0
    rearm_distance: float = 1.5
    provisional_alerts: bool = True

    @classmethod
    def from_env(cls, environ=None, logger=print):
        env = os.environ if environ is None else environ
        def flag(name):
            value = str(env.get(name, 'true')).lower()
            if value not in ('true', 'false'):
                logger('MLRSI_CONFIG_INVALID_DEFAULT_USED')
                return True
            return value == 'true'
        def distance(name, default):
            try:
                value = float(env.get(name, default))
                if not math.isfinite(value) or value <= 0:
                    raise ValueError
                return value
            except (ValueError, TypeError):
                logger('MLRSI_CONFIG_INVALID_DEFAULT_USED')
                return default
        approach = distance('MLRSI_APPROACH_DISTANCE', 1.0)
        rearm = distance('MLRSI_APPROACH_REARM_DISTANCE', 1.5)
        if rearm <= approach:
            logger('MLRSI_CONFIG_INVALID_DEFAULT_USED')
            approach, rearm = 1.0, 1.5
        return cls(flag('MLRSI_OBSERVER_ENABLED'), flag('MLRSI_TELEGRAM_ALERTS'),
                   flag('MLRSI_APPROACHING_ENABLED'), approach, rearm, flag('MLRSI_PROVISIONAL_ALERTS'))


def empty_frame():
    return dict(last_closed_timestamp=None, confirmed_color='UNKNOWN', previous_confirmed_color='UNKNOWN',
                last_confirmed_event=None, last_event_timestamp=None, latest_confirmed_values={},
                latest_provisional_values={}, approaching_state='NO', approaching_green_latched=False,
                approaching_red_latched=False, provisional_green_latched=False, provisional_red_latched=False,
                provisional_candle_timestamp=None, last_successful_read=None, fresh=False)


class MLRSIObserver:
    shadow_only = True
    trade_authority = False

    def __init__(self, storage_dir, send=None, provider=None, config=None, logger=print, clock=time.time):
        self.folder = Path(storage_dir)
        self.state_path = self.folder / 'igod_mlrsi_state.json'
        self.journal_path = self.folder / 'igod_mlrsi_events.jsonl'
        self.config = config or ObserverConfig.from_env(logger=logger)
        self.log, self.clock, self.send = logger, clock, send
        self.provider = provider or PublicHistory(self.folder)
        self.series = {tf: CausalSeries() for tf in TIMEFRAMES}
        self.events = {tf: ResearchEvents(interval) for tf, interval in TIMEFRAMES.items()}
        self.frames = {tf: empty_frame() for tf in TIMEFRAMES}
        self.previous_3of3_green = self.previous_3of3_red = False
        self.primed = set()
        self.startup_sent = False
        self.price = None
        self.pending_journal_records = []
        self.journal_keys = set()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self._cached = None
        if self.config.enabled:
            self._restore()
        self._publish(int(self.clock() * 1000))

    def _restore(self):
        try:
            d = json.loads(self.state_path.read_text('utf-8'))
            if (d['config_version'] != CONFIG_VERSION or d['config'] != CAPTURED_CONFIG or d['symbol'] != 'BTCUSDT'
                    or d['venue'] != 'BINANCE_SPOT' or d['shadow_only'] is not True
                    or d['trade_authority'] is not False or set(d['timeframes']) != set(TIMEFRAMES)):
                raise ValueError
            series, events, frames = {}, {}, {}
            for tf, interval in TIMEFRAMES.items():
                p = d['timeframes'][tf]
                frames[tf] = p['observation']
                if set(frames[tf]) != set(empty_frame()) or frames[tf]['confirmed_color'] not in presentation.ICONS:
                    raise ValueError
                if (frames[tf]['previous_confirmed_color'] not in presentation.ICONS
                        or frames[tf]['last_confirmed_event'] not in (None, 'GREEN_CROSS', 'RED_CROSS', 'GREEN_RESUME', 'RED_RESUME')
                        or frames[tf]['approaching_state'] not in ('NO', 'APPROACHING_GREEN', 'APPROACHING_RED', 'APPROACHING_GREEN + APPROACHING_RED')):
                    raise ValueError
                for k in ('approaching_green_latched', 'approaching_red_latched', 'provisional_green_latched', 'provisional_red_latched', 'fresh'):
                    if not isinstance(frames[tf][k], bool):
                        raise ValueError
                for k in ('latest_confirmed_values', 'latest_provisional_values'):
                    v = frames[tf][k]
                    if v:
                        if v['color'] not in presentation.ICONS:
                            raise ValueError
                        for key, value in v.items():
                            if key != 'color' and value is not None and (not isinstance(value, (float, int, bool)) or not math.isfinite(value)):
                                raise ValueError
                timestamp = frames[tf]['last_closed_timestamp']
                if timestamp is not None and (not isinstance(timestamp, int) or timestamp % interval):
                    raise ValueError
                series[tf], events[tf] = CausalSeries(p['series']), ResearchEvents(interval, p['events'])
                frames[tf]['fresh'] = False  # disk is not a fresh market verification
                frames[tf]['latest_provisional_values'] = {}
            if not all(isinstance(d[k], bool) for k in ('previous_3of3_green', 'previous_3of3_red')):
                raise ValueError
            pending = d.get('pending_journal_records', [])
            for row in pending:
                self._validate_record(row)
            self.series, self.events, self.frames = series, events, frames
            self.previous_3of3_green = d['previous_3of3_green']
            self.previous_3of3_red = d['previous_3of3_red']
            self.pending_journal_records = pending
        except FileNotFoundError:
            pass
        except Exception:
            self.log('MLRSI_STATE_INVALID_REBOOTSTRAP')
            # Rebuild silently; never convert old historical events into new alerts.
        try:
            self.journal_keys = self._read_journal_keys()
        except FileNotFoundError:
            pass
        except Exception:
            self.log('MLRSI_JOURNAL_INVALID')
            # Refuse to append to an unverifiable journal until it is repaired.
            self.journal_keys = None

    def _persist(self):
        atomic_json(self.state_path, dict(config_version=CONFIG_VERSION, observer_version=OBSERVER_VERSION,
                    config=CAPTURED_CONFIG, symbol='BTCUSDT', venue='BINANCE_SPOT', shadow_only=True,
                    trade_authority=False, previous_3of3_green=self.previous_3of3_green,
                    previous_3of3_red=self.previous_3of3_red,
                    pending_journal_records=self.pending_journal_records,
                    timeframes={tf: dict(observation=self.frames[tf], series=self.series[tf].dump(),
                                        events=self.events[tf].dump()) for tf in TIMEFRAMES}))

    def _publish(self, now_ms):
        view = dict(enabled=self.config.enabled, approaching_enabled=self.config.approaching_enabled,
                    provisional_alerts=self.config.provisional_alerts, price=self.price,
                    snapshot_timestamp=now_ms, timeframes=copy.deepcopy(self.frames),
                    shadow_only=True, trade_authority=False)
        with self.lock:
            self._cached = view

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self._cached)
        now_ms = int(self.clock() * 1000)
        for p in result['timeframes'].values():
            p['public_read_age_seconds'] = max(0, (now_ms - p['last_successful_read']) // 1000) if p['last_successful_read'] is not None else None
            if p['last_successful_read'] is None or now_ms - p['last_successful_read'] > 90000:
                p['fresh'] = False
        return result

    def status_text(self):
        return presentation.status(self.snapshot())

    def start(self):
        if not self.config.enabled or self.thread is not None:
            return
        self.thread = threading.Thread(target=self._worker, name='mlrsi-shadow', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()  # never join/block the operational loop

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                self.cycle()
            except Exception:
                self.log('MLRSI_OBSERVER_ERROR_IGNORED')
            self.stop_event.wait(30)

    def cycle(self):
        if not self.config.enabled:
            return
        now_ms = int(self.clock() * 1000)
        frames = {}
        for tf in TIMEFRAMES:
            try:
                frames[tf] = self.provider.fetch(tf, now_ms)
            except Exception:
                self.log('MLRSI_PUBLIC_READ_FAILED')
        self.observe(frames, now_ms)

    @staticmethod
    def _distances(values):
        v, hi, lo = values['mlrsi_smoothed'], values['upper_threshold'], values['lower_threshold']
        values['distance_to_green'] = hi - v if hi is not None and v is not None else None
        values['distance_to_red'] = v - lo if lo is not None and v is not None else None
        return values

    def _closed(self, tf, row, emit):
        p = self.frames[tf]
        values = self._distances(self.series[tf].push(row['low']))
        timestamp = row['time'] + TIMEFRAMES[tf]
        event = self.events[tf].step(timestamp, values)
        old = p['confirmed_color']
        color = values['color'] if values['valid'] else 'UNKNOWN'
        p.update(last_closed_timestamp=timestamp, confirmed_color=color, previous_confirmed_color=old,
                 latest_confirmed_values=dict(values, source_low=row['low'], close=row['close']))
        changes = []
        if emit and color != old and color != 'UNKNOWN':
            changes.append(('COLOR_CHANGE', tf, True))
        if event and emit:
            p.update(last_confirmed_event=event, last_event_timestamp=timestamp)
            changes.append((event, tf, True))
        return changes

    def _open(self, tf, row, emit):
        p = self.frames[tf]
        if p['provisional_candle_timestamp'] != row['time']:
            p.update(provisional_candle_timestamp=row['time'], provisional_green_latched=False,
                     provisional_red_latched=False)
        values = self._distances(self.series[tf].provisional(row['low']))
        p['latest_provisional_values'] = dict(values, source_low=row['low'], close=row['close'])
        p['approaching_state'] = 'NO'
        changes = []
        if not values['valid']:
            return changes
        for color in ('GREEN', 'RED'):
            lower = color.lower()
            distance = values['distance_to_' + lower]
            latch = 'approaching_' + lower + '_latched'
            if distance > self.config.rearm_distance:
                p[latch] = False
            # Strictly below/above the threshold; a tie stays neutral.
            near = values['color'] != color and 0 < distance <= self.config.approach_distance
            if near and self.config.approaching_enabled:
                state = 'APPROACHING_' + color
                p['approaching_state'] = state if p['approaching_state'] == 'NO' else p['approaching_state'] + ' + ' + state
                if not p[latch]:
                    p[latch] = True
                    if emit:
                        changes.append(('APPROACHING_' + color, tf, False))
            provisional_latch = 'provisional_' + lower + '_latched'
            if values['color'] == color and p['confirmed_color'] != color and not p[provisional_latch]:
                p[provisional_latch] = True
                if emit:
                    changes.append(('PROVISIONAL_' + color, tf, False))
        return changes

    def observe(self, frames, now_ms):
        """Only the worker/test harness writes observations; commands read cache.

        First successful history per TF is silent, including restart catch-up.
        Storage must succeed before any outbound event: failures remain nonfatal.
        """
        if not self.config.enabled:
            return
        records, alerts, prepared, pending = [], [], {}, []
        for tf, interval in TIMEFRAMES.items():
            p = self.frames[tf]
            p['fresh'] = False
            p['latest_provisional_values'] = {}
            p['approaching_state'] = 'NO'
            if tf not in frames:
                continue
            try:
                rows = validate_candles(frames[tf], tf, now_ms)
                closed = [r for r in rows if r['time'] + interval <= now_ms]
                if not closed or closed[-1]['time'] + interval <= now_ms - interval:
                    raise ValueError
                new = [r for r in closed if p['last_closed_timestamp'] is None or r['time'] + interval > p['last_closed_timestamp']]
                if any(b['time'] - a['time'] != interval for a, b in zip(new, new[1:])):
                    raise ValueError
                if p['last_closed_timestamp'] is not None and new and new[0]['time'] != p['last_closed_timestamp']:
                    raise ValueError
                prepared[tf] = (rows, closed, tf in self.primed)
                pending.extend((row['time'] + interval, tf, row) for row in new)
            except Exception:
                self.log('MLRSI_TIMEFRAME_UNAVAILABLE')
        # Advance all coincident closes before journaling their shared MTF context.
        # Catch-up is journaled with its original closed timestamp, never resent as live.
        for timestamp, group in groupby(sorted(pending, key=lambda item: (item[0], item[1])), key=lambda item: item[0]):
            changes = []
            for _, tf, row in group:
                changes.extend(self._closed(tf, row, prepared[tf][2]))
            for change in changes:
                record = self._record(*change, now_ms)
                records.append(record)
                tf = change[1]
                if timestamp == now_ms // TIMEFRAMES[tf] * TIMEFRAMES[tf]:
                    alerts.append(record)
        for tf, (rows, closed, emit) in prepared.items():
            interval, p = TIMEFRAMES[tf], self.frames[tf]
            try:
                if len(self.series[tf].history) < 3000 or not p['latest_confirmed_values'].get('valid'):
                    raise ValueError
                p.update(fresh=True, last_successful_read=now_ms)
                open_rows = [r for r in rows if r['time'] <= now_ms < r['time'] + interval]
                if open_rows:
                    for change in self._open(tf, open_rows[-1], emit):
                        record = self._record(*change, now_ms)
                        records.append(record)
                        alerts.append(record)
                    if tf == '15m':
                        self.price = open_rows[-1]['close']
                elif tf == '15m':
                    self.price = closed[-1]['close']
                self.primed.add(tf)
            except Exception:
                self.log('MLRSI_TIMEFRAME_UNAVAILABLE')
        ready = all(p['fresh'] for p in self.frames.values()) and len(self.primed) == 3
        first_ready = ready and not self.startup_sent
        if ready:
            green = all(p['confirmed_color'] == 'GREEN' for p in self.frames.values())
            red = all(p['confirmed_color'] == 'RED' for p in self.frames.values())
            if not first_ready:
                if green and not self.previous_3of3_green:
                    record = self._record('CONFLUENCE_3OF3_GREEN', '15m', True, now_ms)
                    records.append(record)
                    alerts.append(record)
                if red and not self.previous_3of3_red:
                    record = self._record('CONFLUENCE_3OF3_RED', '15m', True, now_ms)
                    records.append(record)
                    alerts.append(record)
                if self.previous_3of3_green and not green:
                    records.append(self._record('CONFLUENCE_EXIT_GREEN', '15m', True, now_ms))
                if self.previous_3of3_red and not red:
                    records.append(self._record('CONFLUENCE_EXIT_RED', '15m', True, now_ms))
            self.previous_3of3_green, self.previous_3of3_red = green, red
        # Missing market data cannot rearm an existing confluence episode.
        self._publish(now_ms)
        try:
            # Durable outbox: recover journal writes after a crash, never resend alerts.
            known = {r['dedupe_key'] for r in self.pending_journal_records}
            self.pending_journal_records.extend(r for r in records if r['dedupe_key'] not in known)
            self._persist()
            if self.pending_journal_records:
                self._flush_journal()
                self.pending_journal_records = []
                self._persist()
            if first_ready:
                self.startup_sent = True
                self._notify(presentation.startup(self.snapshot()))
            permitted = [] if first_ready else [r for r in alerts if not r['event'].startswith('PROVISIONAL_') or self.config.provisional_alerts]
            if permitted:
                self._notify(presentation.alert(self.snapshot(), permitted))
        except Exception:
            self.log('MLRSI_STORAGE_OR_PRESENTATION_FAILED')

    def _flush_journal(self):
        if self.journal_keys is None:
            raise ValueError('MLRSI_JOURNAL_INVALID')
        # Reconcile actual bytes after an ambiguous append/fsync, not just RAM.
        self.journal_keys = self._read_journal_keys()
        new = [r for r in self.pending_journal_records if r['dedupe_key'] not in self.journal_keys]
        if new:
            with self.journal_path.open('a', encoding='utf-8') as f:
                for record in new:
                    f.write(json.dumps(record, allow_nan=False, separators=(',', ':')) + '\n')
                f.flush()
                os.fsync(f.fileno())
            self.journal_keys.update(r['dedupe_key'] for r in new)

    @staticmethod
    def _validate_record(row):
        if (row['symbol'] != 'BTCUSDT' or row['source'] != 'LOW' or row['timeframe'] not in TIMEFRAMES
                or row['event'] not in EVENT_NAMES or row['shadow_only'] is not True
                or row['trade_authority'] is not False or row['config_version'] != CONFIG_VERSION):
            raise ValueError('MLRSI_JOURNAL_INVALID')
        for k in ('recorded_at_utc', 'candle_timestamp_utc'):
            if datetime.fromisoformat(row[k]).utcoffset().total_seconds() != 0:
                raise ValueError('MLRSI_JOURNAL_INVALID')
        if not isinstance(row['dedupe_key'], str):
            raise ValueError('MLRSI_JOURNAL_INVALID')

    def _read_journal_keys(self):
        keys = set()
        try:
            with self.journal_path.open(encoding='utf-8') as f:
                for line in f:
                    row = json.loads(line)
                    self._validate_record(row)
                    keys.add(row['dedupe_key'])
        except FileNotFoundError:
            pass
        return keys

    def _record(self, event, tf, complete, now_ms):
        p = self.frames[tf]
        v = p['latest_confirmed_values'] if complete else p['latest_provisional_values']
        stamp = p['last_closed_timestamp'] if complete else p['provisional_candle_timestamp']
        return dict(recorded_at_utc=utc(now_ms), candle_timestamp_utc=utc(stamp), timeframe=tf,
                    symbol='BTCUSDT', candle_complete=complete, source='LOW', source_low=v.get('source_low'),
                    close=v.get('close'), mlrsi_raw=v.get('mlrsi_raw'), mlrsi_smoothed=v.get('mlrsi_smoothed'),
                    lower_threshold=v.get('lower_threshold'), middle_centroid=v.get('middle_centroid'),
                    upper_threshold=v.get('upper_threshold'), distance_to_green=v.get('distance_to_green'),
                    distance_to_red=v.get('distance_to_red'), confirmed_color=p['confirmed_color'],
                    provisional_color=p['latest_provisional_values'].get('color', 'UNKNOWN'),
                    previous_confirmed_color=p['previous_confirmed_color'], event=event,
                    approaching_state=p['approaching_state'],
                    **{'confirmed_state_' + k: q['confirmed_color'] if not complete or q['last_closed_timestamp'] is None
                       or q['last_closed_timestamp'] <= stamp else 'UNKNOWN' for k, q in self.frames.items()},
                    **{'provisional_state_' + k: q['latest_provisional_values'].get('color', 'UNKNOWN') for k, q in self.frames.items()},
                    config_version=CONFIG_VERSION, observer_version=OBSERVER_VERSION, shadow_only=True,
                    trade_authority=False, dedupe_key='BTCUSDT|' + tf + '|' + str(stamp) + '|' + event)

    def _notify(self, text):
        if not self.config.telegram_alerts or self.send is None:
            return
        try:
            if self.send(text) is False:
                self.log('MLRSI_TELEGRAM_FAILED')
        except Exception:
            self.log('MLRSI_TELEGRAM_FAILED')
