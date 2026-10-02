"""Independent public market observer. No account client or entry permission."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import numpy as np
import requests
from early_breakout_core import Engine, Parameters, STEP, validate_rows, render_early, event_outcome
from guardian_telegram import Telegram  # outbound transport only; commands are a separate module

PUBLIC_KLINES = 'https://data-api.binance.vision/api/v3/klines'
FROZEN = Path(__file__).parent/'research/early_breakout_artifacts/frozen_parameters.json'


class PublicMarket:
    def __init__(self, transport=None, clock=time.time):
        self.http, self.clock = transport or requests.Session(), clock

    def bars(self, interval='15m', start=None):
        if interval not in ('15m', '5m'):
            raise ValueError('PUBLIC_INTERVAL_BLOCKED')
        step = STEP if interval == '15m' else 300000
        end = int(self.clock()*1000)//step*step
        result = []
        cursor = start
        for _ in range(12):
            params = dict(symbol='BTCUSDT', interval=interval, limit=1000, endTime=end-1)
            if cursor is not None:
                params['startTime'] = cursor
            response = self.http.get(PUBLIC_KLINES, params=params, timeout=(3, 5), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('PUBLIC_MARKET_UNAVAILABLE')
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                raise ValueError('PUBLIC_MARKET_INVALID')
            rows = validate_rows([[r[0], r[1], r[2], r[3], r[4], r[5], r[9]] for r in payload], step, end)
            if not len(rows):
                raise ValueError('PUBLIC_CANDLES_INCOMPLETE')
            result.extend(rows.tolist())
            if start is None or rows[-1, 0]+step >= end:
                break
            cursor = int(rows[-1, 0])+step
        return validate_rows(result, step, end)


class ShadowStore:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = (self.root/'observer.lock').open('a+b')
        self._lock.write(b'0')
        self._lock.flush()
        self._lock.seek(0)
        self._locked = False
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locked = True
            self.state = json.loads((self.root/'state.json').read_text(encoding='utf-8')) if (self.root/'state.json').exists() else {}
            if not isinstance(self.state, dict):
                raise ValueError('OBSERVER_STATE_INVALID')
            self.events = self.read('events')
            for name in ('events', 'outcomes', 'snapshots'):
                if not (self.root/(name+'.jsonl')).exists():
                    with (self.root/(name+'.jsonl')).open('a', encoding='utf-8') as stream:
                        stream.flush()
                        os.fsync(stream.fileno())
            self.event_ids = {entry['event_id'] for entry in self.events}
            self.outcome_ids = {entry['event_id'] for entry in self.read('outcomes')}
        except Exception:
            self.close()
            raise ValueError('OBSERVER_STORE_UNVERIFIED') from None

    def close(self):
        if not self._lock.closed:
            if os.name == 'nt' and self._locked:
                import msvcrt
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
            self._lock.close()

    def read(self, name):
        path = self.root/(name+'.jsonl')
        if not path.exists():
            return []
        text = path.read_text(encoding='utf-8')
        if text and not text.endswith('\n'):
            raise ValueError('OBSERVER_JOURNAL_INCOMPLETE')
        return [json.loads(line) for line in text.splitlines()]

    def append(self, name, value):
        if name not in ('events', 'outcomes', 'snapshots'):
            raise ValueError('OBSERVER_JOURNAL_BLOCKED')
        with (self.root/(name+'.jsonl')).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, allow_nan=False, separators=(',', ':'))+'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def save(self, value):
        target = self.root/'state.json.tmp'
        with target.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, allow_nan=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(target, self.root/'state.json')
        if os.name != 'nt':
            descriptor = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        self.state = value


def load_parameters(path=FROZEN):
    if path.exists():
        parameters = Parameters(**json.loads(path.read_text(encoding='utf-8'))['parameters'])
    else:
        parameters = Parameters()
    if parameters.hold != 1:
        raise ValueError('LIVE_OBSERVER_REQUIRES_LATER_CLOSED_HOLD')
    return parameters


class Observer:
    def __init__(self, market, store, telegram, parameters=None, clock=time.time):
        self.market, self.store, self.telegram, self.clock = market, store, telegram, clock
        self.parameters = parameters or load_parameters()
        if self.parameters.hold != 1:
            raise ValueError('LIVE_OBSERVER_REQUIRES_LATER_CLOSED_HOLD')
        saved = store.state.get('engine')
        if saved and saved['parameters'] != asdict(self.parameters):
            raise ValueError('OBSERVER_PARAMETER_CHANGE_REQUIRES_NEW_STATE')
        self.engine = Engine(self.parameters, saved)

    def cycle(self):
        now = int(self.clock()*1000)
        try:
            rows = self.market.bars()
            rows = validate_rows(rows, STEP, now)
            if not len(rows) or now - (rows[-1, 0]+STEP) >= STEP:
                raise ValueError('PUBLIC_DATA_STALE')
            initial = self.engine.last_time is None
            changed = False
            for bar in rows:
                before = self.engine.last_time
                events = self.engine.step(bar)
                changed = changed or self.engine.last_time != before
                for event in events:
                    if initial and event['timestamp'] < rows[-1, 0]+STEP:
                        continue  # prime warm-up, never flood Telegram with historical alerts
                    if event['event_id'] in self.store.event_ids:
                        continue
                    event['replayed'] = now-event['timestamp'] >= STEP
                    self.store.append('events', event)  # durable dedupe BEFORE enqueueing any alert
                    self.store.event_ids.add(event['event_id'])
                    self.store.events.append(event)
                    if not event['replayed']:
                        try:
                            self.telegram.send(render_early(event))
                        except Exception:
                            print('EARLY_TELEGRAM_UNAVAILABLE', flush=True)
            public = dict(self.engine.latest, fresh=True, source='BINANCE_SPOT_PUBLIC',
                          entry_permission=False, observed_at=now)
            public['event_state'] = public['state']
            if public['state'] == 'RELEASE_FAILED':
                public['state'] = 'NONE'  # public consumer enum; terminal diagnostic remains in event_state/journal
            self.store.save(dict(engine=self.engine.export(), latest=public))
            if changed:
                self.store.append('snapshots', public)
            self._outcomes(now)
            return public
        except Exception:
            print('EARLY_PUBLIC_DATA_UNAVAILABLE', flush=True)
            public = dict(state='NONE', timestamp=self.engine.last_time, fresh=False,
                          compression_high=None, compression_low=None, atr_percentile=None, vol_z=None,
                          source='BINANCE_SPOT_PUBLIC', entry_permission=False, observed_at=now)
            self.store.save(dict(engine=self.engine.export(), latest=public))
            return public

    def _outcomes(self, now):
        pending = [event for event in self.store.events if event['event_id'] not in self.store.outcome_ids
                   and (event['state'] == 'SQUEEZE_WATCH' or event['state'].startswith('DEVELOPING'))
                   and now-event['timestamp'] >= 48*3600000]
        if not pending:
            return
        try:
            first = max(min(event['timestamp'] for event in pending), now-7*86400000)
            rows = self.market.bars('5m', first)
            for event in pending:
                directions = (1, -1) if event['direction'] == 0 else (event['direction'],)
                outcome = dict(event_id=event['event_id'], timestamp=now,
                               descriptive_only=True,
                               paths={str(side): event_outcome(rows, event, side, now) for side in directions})
                self.store.append('outcomes', outcome)
                self.store.outcome_ids.add(event['event_id'])
        except Exception:
            print('EARLY_OUTCOME_DATA_UNAVAILABLE', flush=True)


def main():
    store = None
    try:
        store = ShadowStore(os.getenv('EARLY_BREAKOUT_STATE_DIR', '/data/early_breakout'))
        observer = Observer(PublicMarket(), store, Telegram(os.getenv('TELEGRAM_BOT_TOKEN', ''),
                            os.getenv('TELEGRAM_CHAT_ID', ''), alert_chat_id=os.getenv('TELEGRAM_ALERT_CHAT_ID', '')))
        print('EARLY BREAKOUT SHADOW — ENTRY PERMISSION DISABLED', flush=True)
        while True:
            observer.cycle()
            time.sleep(45)
    except KeyboardInterrupt:
        pass
    except Exception:
        print('EARLY_OBSERVER_STOPPED_SAFE', flush=True)
        raise SystemExit(1) from None
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    main()
