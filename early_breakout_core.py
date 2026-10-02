"""Pure closed-candle early warnings. No account, execution or Guardian dependencies."""
from dataclasses import dataclass, asdict
from collections import deque
import math
import numpy as np

STEP = 900000
STATES = ('NONE', 'SQUEEZE_WATCH', 'DEVELOPING_LONG', 'DEVELOPING_SHORT',
          'CONFIRMING_LONG', 'CONFIRMING_SHORT', 'RELEASE_FAILED')
HORIZONS = (1, 4, 12, 24, 48)
PASSAGES = ((.005, .005), (.01, .005), (.01, .01), (.02, .01), (.03, .01))


@dataclass(frozen=True)
class Parameters:
    percentile: float = .20
    duration: int = 3
    volume_z: float = 1.5
    hold: int = 1
    acceleration: bool = True

    def __post_init__(self):
        if self.percentile not in (.15, .20, .25) or self.duration not in (2, 3, 4):
            raise ValueError('PARAMETERS_INVALID')
        if self.volume_z not in (1., 1.5, 2.) or self.hold not in (0, 1) or type(self.acceleration) is not bool:
            raise ValueError('PARAMETERS_INVALID')


def validate_rows(rows, interval, now_ms=None):
    a = np.asarray(rows, dtype=float)
    if a.ndim != 2 or a.shape[1] != 7 or not len(a) or not np.all(np.isfinite(a)):
        raise ValueError('MARKET_DATA_INVALID')
    if np.any(a[:, 0] % interval) or np.any(np.diff(a[:, 0]) <= 0):
        raise ValueError('MARKET_TIMESTAMPS_INVALID')
    if (np.any(a[:, 3] <= 0) or np.any(a[:, 2] < np.maximum(a[:, 1], a[:, 4]))
            or np.any(a[:, 3] > np.minimum(a[:, 1], a[:, 4])) or np.any(a[:, 5:] < 0)
            or np.any(a[:, 6] > a[:, 5])):
        raise ValueError('MARKET_RANGE_INVALID')
    if now_ms is not None:
        a = a[a[:, 0] + interval <= now_ms]
    return a


def aggregate(rows, interval):
    """Only complete groups of closed 5m bars; incomplete/gapped groups disappear."""
    a = validate_rows(rows, 300000)
    groups = a[:, 0].astype(np.int64) // interval * interval
    starts = np.r_[0, np.flatnonzero(np.diff(groups)) + 1]
    ends = np.r_[starts[1:], len(a)]
    result = []
    for first, end in zip(starts, ends):
        part = a[first:end]
        if len(part) != interval // 300000 or part[0, 0] != groups[first] or np.any(np.diff(part[:, 0]) != 300000):
            continue
        result.append([groups[first], part[0, 1], part[:, 2].max(), part[:, 3].min(),
                       part[-1, 4], part[:, 5].sum(), part[:, 6].sum()])
    return np.asarray(result, float).reshape(-1, 7)


class Indicators:
    """main.py formulas: first-TR RMA14, EMA12/26/9, volume20 sample std (ddof=1)."""
    def __init__(self, state=None):
        state = state or {}
        self.previous_close = state.get('previous_close')
        self.atr = state.get('atr')
        self.count = state.get('count', 0)
        self.ema12, self.ema26, self.signal = [state.get(key) for key in ('ema12', 'ema26', 'signal')]
        self.previous_hist = state.get('previous_hist')
        self.previous_slope = state.get('previous_slope')
        self.history = deque(state.get('history', []), maxlen=100)
        self.volume = deque(state.get('volume', []), maxlen=20)

    def step(self, bar):
        close, high, low, volume = bar[4], bar[2], bar[3], bar[5]
        tr = high - low if self.previous_close is None else max(high-low, abs(high-self.previous_close), abs(low-self.previous_close))
        self.atr = tr if self.atr is None else (13*self.atr + tr)/14
        self.count += 1
        atr = self.atr if self.count >= 14 and self.atr > 0 else None
        rank = sum(value <= atr for value in self.history)/100 if atr is not None and len(self.history) == 100 else None
        if atr is not None:
            self.history.append(atr)  # rank NEVER includes the current observation
        self.ema12 = close if self.ema12 is None else 2/13*close + 11/13*self.ema12
        self.ema26 = close if self.ema26 is None else 2/27*close + 25/27*self.ema26
        macd = self.ema12 - self.ema26
        self.signal = macd if self.signal is None else .2*macd + .8*self.signal
        hist = macd - self.signal
        slope = None if self.previous_hist is None else hist - self.previous_hist
        acceleration = None if slope is None or self.previous_slope is None else slope - self.previous_slope
        self.previous_hist, self.previous_slope, self.previous_close = hist, slope, close
        self.volume.append(volume)
        vol_z = 0.
        if len(self.volume) == 20 and min(self.volume) > 0:
            std = float(np.std(self.volume, ddof=1))
            if std > 0:
                vol_z = (volume - float(np.mean(self.volume)))/std
        return dict(atr=atr, atr_percentile=rank, vol_z=float(vol_z), macd_hist=float(hist),
                    macd_slope=slope, macd_acceleration=acceleration)

    def export(self):
        return {key: list(value) if isinstance(value, deque) else value for key, value in vars(self).items()}


class Engine:
    """One isolated episode. Freeze the PRIOR range before testing any breakout."""
    def __init__(self, parameters=None, state=None):
        self.parameters = parameters or Parameters()
        state = state or {}
        self.indicators = Indicators(state.get('indicators'))
        self.last_time = state.get('last_time')
        self.state = state.get('state', 'NONE')
        self.episode = state.get('episode')
        self.developing = state.get('developing')
        self.frozen_at = state.get('frozen_at')
        self.confirmed_at = state.get('confirmed_at')
        self.latest = state.get('latest', {})
        if self.state not in STATES or (self.last_time is not None and (type(self.last_time) is not int or self.last_time % STEP)):
            raise ValueError('ENGINE_STATE_INVALID')
        if self.episode is not None:
            fields = ('start_time', 'high', 'low', 'duration')
            if (not isinstance(self.episode, dict) or any(key not in self.episode for key in fields)
                    or not all(math.isfinite(self.episode[key]) for key in fields)
                    or self.episode['low'] <= 0 or self.episode['high'] < self.episode['low']
                    or type(self.episode['duration']) is not int or self.episode['duration'] < 1):
                raise ValueError('ENGINE_EPISODE_INVALID')
        if self.state == 'SQUEEZE_WATCH' or self.state.startswith(('DEVELOPING', 'CONFIRMING')):
            if self.episode is None or self.last_time is None:
                raise ValueError('ENGINE_EPISODE_MISSING')
        if self.state.startswith('DEVELOPING'):
            if not isinstance(self.developing, dict) or type(self.developing.get('direction')) is not int or self.developing['direction'] not in (-1, 1):
                raise ValueError('ENGINE_RELEASE_INVALID')

    def export(self):
        return dict(version=1, parameters=asdict(self.parameters), indicators=self.indicators.export(),
                    last_time=self.last_time, state=self.state, episode=self.episode,
                    developing=self.developing, frozen_at=self.frozen_at,
                    confirmed_at=self.confirmed_at, latest=self.latest)

    def step(self, bar, metrics=None):
        bar = np.asarray(bar, float)
        if (bar.shape != (7,) or not all(math.isfinite(value) for value in bar)
                or bar[0] % STEP or bar[3] <= 0 or bar[2] < max(bar[1], bar[4])
                or bar[3] > min(bar[1], bar[4]) or min(bar[5], bar[6]) < 0 or bar[6] > bar[5]):
            raise ValueError('MARKET_CANDLE_INVALID')
        timestamp = int(bar[0] + STEP)
        if self.last_time is not None and timestamp <= self.last_time:
            return []
        gap = self.last_time is not None and timestamp - self.last_time != STEP
        if gap:
            self.indicators = Indicators()
            self.episode = self.developing = self.frozen_at = self.confirmed_at = None
            self.state = 'NONE'
        metrics = self.indicators.step(bar) if metrics is None else metrics
        # Offline sweeps share precomputed CAUSAL metrics; live always maintains its indicator state.
        self.last_time = timestamp
        old = self.state
        close = float(bar[4])
        rank = metrics['atr_percentile']
        squeezed = rank is not None and rank <= self.parameters.percentile
        cause = None
        if self.state == 'RELEASE_FAILED':
            self.state = 'NONE'
            self.episode = self.developing = self.frozen_at = self.confirmed_at = None
        elif self.state.startswith('CONFIRMING'):
            side = 1 if self.state.endswith('LONG') else -1
            boundary = self.episode['high'] if side == 1 else self.episode['low']
            if side*(close-boundary) <= 0:
                self.state, cause = 'RELEASE_FAILED', 'CONFIRMED_RELEASE_RETURNED_INSIDE'
            elif timestamp - self.confirmed_at >= 4*STEP:
                self.state, cause = 'NONE', 'RELEASE_COMPLETED_EXPIRY'
                self.episode = self.developing = self.frozen_at = self.confirmed_at = None
        elif self.state.startswith('DEVELOPING'):
            side = self.developing['direction']
            boundary = self.episode['high'] if side == 1 else self.episode['low']
            if side*(close-boundary) > 0:
                self.state = 'CONFIRMING_LONG' if side == 1 else 'CONFIRMING_SHORT'
                self.confirmed_at = timestamp
                cause = 'LATER_CLOSED_CANDLE_HOLD'
            else:
                self.state, cause = 'RELEASE_FAILED', 'BREAKOUT_RETURNED_INSIDE'
        elif self.episode is not None and self.episode['duration'] >= self.parameters.duration:
            side = 1 if close > self.episode['high'] else -1 if close < self.episode['low'] else 0
            if side:
                self.frozen_at = self.frozen_at or self.last_time - STEP
                accel = metrics['macd_acceleration']
                compatible = not self.parameters.acceleration or (accel is not None and side*accel > 0)
                if metrics['vol_z'] >= self.parameters.volume_z and compatible:
                    self.developing = dict(timestamp=timestamp, direction=side, reference_price=close)
                    self.state = 'DEVELOPING_LONG' if side == 1 else 'DEVELOPING_SHORT'
                    cause = 'FROZEN_RANGE_BREAKOUT'
                    if self.parameters.hold == 0:  # research control only; live observer rejects it
                        self.state = 'CONFIRMING_LONG' if side == 1 else 'CONFIRMING_SHORT'
                        self.confirmed_at = timestamp
                        cause = 'ZERO_HOLD_RESEARCH_CONTROL'
                else:
                    self.state, cause = 'RELEASE_FAILED', 'BREAKOUT_DIAGNOSTICS_FAILED'
            elif squeezed and self.frozen_at is None:
                self._extend(bar)
            else:
                self.frozen_at = self.frozen_at or timestamp
                if timestamp - self.frozen_at >= 4*STEP:
                    self.state, cause = 'NONE', 'SQUEEZE_EXPIRED_WITHOUT_BREAKOUT'
                    self.episode = self.frozen_at = None
        else:
            if squeezed:
                if self.episode is None:
                    self.episode = dict(start_time=timestamp, high=float(bar[2]), low=float(bar[3]), duration=1)
                else:
                    self._extend(bar)
                if self.episode['duration'] >= self.parameters.duration:
                    self.state, cause = 'SQUEEZE_WATCH', 'COMPRESSION_EPISODE'
            else:
                self.episode = None  # short, interrupted episodes never pool observations
        side = 1 if self.state.endswith('LONG') else -1 if self.state.endswith('SHORT') else 0
        self.latest = dict(state=self.state, timestamp=timestamp, price=close, direction=side,
                           squeeze_start_time=self.episode['start_time'] if self.episode else None,
                           compression_high=self.episode['high'] if self.episode else None,
                           compression_low=self.episode['low'] if self.episode else None,
                           duration=self.episode['duration'] if self.episode else 0,
                           breakout_level=(self.episode['high'] if side == 1 else self.episode['low']) if side and self.episode else None,
                           **metrics)
        if self.state != old or gap:
            event = dict(self.latest, cause=cause or 'DATA_GAP_RESET',
                         event_id=f'{self.state}:{timestamp}',
                         episode_id=self.episode['start_time'] if self.episode else None,
                         developing=self.developing)
            return [event]
        return []

    def _extend(self, bar):
        self.episode['high'] = max(self.episode['high'], float(bar[2]))
        self.episode['low'] = min(self.episode['low'], float(bar[3]))
        self.episode['duration'] += 1


def render_early(data):
    labels = {'NONE': '⚪ NONE', 'SQUEEZE_WATCH': '🟣⚡ SQUEEZE WATCH — MOVIMIENTO EN PREPARACIÓN',
              'DEVELOPING_LONG': '🟠👀 DEVELOPING LONG', 'DEVELOPING_SHORT': '🟠👀 DEVELOPING SHORT',
              'CONFIRMING_LONG': '🟢🔎 LONG CONFIRMING', 'CONFIRMING_SHORT': '🔴🔎 SHORT CONFIRMING',
              'RELEASE_FAILED': '⚪ FALSE BREAKOUT / RELEASE FAILED'}
    def number(key, percent=False):
        value = data.get(key)
        if value is None or not math.isfinite(value):
            return 'Sin datos'
        return f'{value:.1%}' if percent else f'{value:,.2f}'
    from datetime import datetime, timezone
    timestamp = datetime.fromtimestamp(data['timestamp']/1000, timezone.utc).isoformat()
    lines = [labels.get(data.get('state'), '⚪ NONE'), timestamp, 'BTC: '+number('price'),
             '📦 Compresión: '+number('compression_low')+' — '+number('compression_high'),
             f'Duración: {data.get("duration", 0)} velas cerradas',
             'ATR percentile: '+number('atr_percentile', True), 'Volume z: '+number('vol_z'),
             'MACD acceleration: '+number('macd_acceleration'), 'Breakout: '+number('breakout_level')]
    if data.get('state') == 'SQUEEZE_WATCH':
        lines += ['❓ Dirección todavía desconocida', '👀 Arriba: '+number('compression_high'),
                  '👀 Abajo: '+number('compression_low')]
    if data.get('state', '').startswith('CONFIRMING'):
        lines.append('✅ Breakout sostenido en vela cerrada posterior')
    lines += ['🚫 NO ENTRAR — esperar decisión independiente del Manual Copilot',
              '🔬 EARLY BREAKOUT SHADOW / NO ES UNA ORDEN DE ENTRADA']
    return '\n'.join(lines)


def event_outcome(rows, event, direction, cutoff=None, *, validated=False):
    """Descriptive next CLOSED 5m paths; same-bar double touches are adverse first."""
    if direction not in (-1, 1):
        raise ValueError('OUTCOME_DIRECTION_INVALID')
    rows = np.asarray(rows, float) if validated else validate_rows(rows, 300000)
    timestamp, price = event['timestamp'], event['price']
    start = int(np.searchsorted(rows[:, 0], timestamp))
    result = {}
    for hours in HORIZONS:
        end_time = timestamp + hours*3600000
        end = int(np.searchsorted(rows[:, 0], end_time))
        window = rows[start:end]
        if (not len(window) or window[0, 0] != timestamp or window[-1, 0]+300000 != end_time
                or np.any(np.diff(window[:, 0]) != 300000) or (cutoff is not None and end_time > cutoff)):
            result[str(hours)] = None  # censored; never pretend missing paths are failures
            continue
        favorable = window[:, 2]/price-1 if direction == 1 else 1-window[:, 3]/price
        adverse = 1-window[:, 3]/price if direction == 1 else window[:, 2]/price-1
        passages = {}
        for target, barrier in PASSAGES:
            favorable_hits = np.flatnonzero(favorable >= target)
            adverse_hits = np.flatnonzero(adverse >= barrier)
            f = int(favorable_hits[0]) if len(favorable_hits) else len(window)
            a = int(adverse_hits[0]) if len(adverse_hits) else len(window)
            passages[f'{target:g}/{barrier:g}'] = dict(success=f < a,
                resolution='FAVORABLE' if f < a else 'ADVERSE' if a < len(window) else 'UNRESOLVED',
                minutes=5*(min(f, a)+1) if min(f, a) < len(window) else None)
        result[str(hours)] = dict(mfe=float(max(0, favorable.max())), mae=float(max(0, adverse.max())),
                                 signed_return=float(direction*(window[-1, 4]/price-1)), passages=passages)
    return result
