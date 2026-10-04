"""Research mathematical policies with the current LOW29/EMA4 observer preset.

Exact BackQuant TradingView parity is NOT proven. The unchanged research port
supplies the percentile clustering, tie and empty-cluster policies.
"""
from collections import deque
import copy
import math
import numpy as np
from guardian_signals import cluster_three, pine_ema

CAPTURED_CONFIG = {
    'source': 'LOW', 'rsi_length': 29, 'smooth': True, 'ma_type': 'EMA',
    'smoothing_period': 4, 'alma_sigma': 1, 'threshold_range_min': 10,
    'threshold_range_max': 90, 'step': 5, 'performance_memory': 10,
    'max_clustering_steps': 1000, 'max_data_points': 3000, 'clusters': 3,
    'wait_for_timeframe_close': True,
}
CONFIG_VERSION = 'CAPTURE_LOW29_EMA4_CAUSAL_V2'
RSI_LENGTH = CAPTURED_CONFIG['rsi_length']
TIMEFRAMES = {'15m': 900000, '1h': 3600000, '4h': 14400000}
COLORS = {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}


class CausalSeries:
    """Carry Wilder/EMA seed across restarts instead of reseeding a moving tail.

    Only CLOSED observations enter this instance. An open candle is evaluated
    on a disposable clone, including its own causal rolling centroid update.
    """
    def __init__(self, state=None):
        self.previous_low = None
        self.seed = []
        self.up = self.down = self.smoothed = None
        self.history = deque(maxlen=3000)
        self.count = 0
        if state is not None:
            self.previous_low = state['previous_low']
            self.seed = state['seed']
            self.up, self.down, self.smoothed = state['up'], state['down'], state['smoothed']
            self.history.extend(state['history'])
            self.count = state['count']
            values = [self.previous_low, self.up, self.down, self.smoothed, *self.history]
            if (state.get('rsi_length') != RSI_LENGTH
                    or len(state['history']) > 3000 or len(self.seed) > RSI_LENGTH or self.count < 0
                    or any(v is not None and not math.isfinite(v) for v in values)
                    or not isinstance(self.count, int)
                    or any(len(pair) != 2 or any(not math.isfinite(v) or v < 0 for v in pair) for pair in self.seed)
                    or any(v is not None and v < 0 for v in (self.up, self.down))):
                raise ValueError('MLRSI_SERIES_STATE_INVALID')

    def dump(self):
        return dict(rsi_length=RSI_LENGTH, previous_low=self.previous_low, seed=self.seed, up=self.up, down=self.down,
                    smoothed=self.smoothed, history=list(self.history), count=self.count)

    def push(self, low):
        low = float(low)
        if not math.isfinite(low) or low <= 0:
            raise ValueError('MLRSI_LOW_INVALID')
        self.count += 1
        raw = None
        if self.previous_low is not None:
            change = low - self.previous_low
            gain, loss = max(change, 0.), max(-change, 0.)
            if self.up is None:
                self.seed.append([gain, loss])
                if len(self.seed) == RSI_LENGTH:
                    # Same Wilder seed policy, now the first 29 LOW differences.
                    a = np.asarray(self.seed)
                    self.up, self.down = float(a[:, 0].mean()), float(a[:, 1].mean())
            else:
                self.up = (self.up * (RSI_LENGTH - 1) + gain) / RSI_LENGTH
                self.down = (self.down * (RSI_LENGTH - 1) + loss) / RSI_LENGTH
            if self.up is not None and self.up + self.down:
                raw = 100 * self.up / (self.up + self.down)
        self.previous_low = low
        if raw is not None:
            # Use the original finite-value EMA seed/update, not pandas ewm.
            values = [raw] if self.smoothed is None else [self.smoothed, raw]
            self.smoothed = float(pine_ema(values, 4)[-1])
            self.history.append(self.smoothed)
        result = dict(mlrsi_raw=raw, mlrsi_smoothed=self.smoothed if raw is not None else None,
                      valid=False, converged=False, window_count=len(self.history), iterations=0,
                      lower_threshold=None, middle_centroid=None, upper_threshold=None, color='UNKNOWN')
        if raw is not None and len(self.history) >= 4:
            c, iterations, converged = cluster_three(self.history, 1000)
            state = 1 if self.smoothed > c[2] else -1 if self.smoothed < c[0] else 0
            result.update(lower_threshold=float(c[0]), middle_centroid=float(c[1]),
                          upper_threshold=float(c[2]), color=COLORS[state],
                          valid=bool(converged), converged=bool(converged), iterations=int(iterations))
        return result

    def provisional(self, low):
        return copy.deepcopy(self).push(low)


class ResearchEvents:
    """Exactly PR19/20 one-bar CROSS/RESUME state machine, any fixed TF.

    The research two-bar variants are diagnostic only, not this observer's
    default. A gap/invalid RSI clears rearm; it never invents a transition.
    """
    def __init__(self, interval, state=None):
        self.interval = interval
        self.previous = None
        self.armed = False
        if state:
            self.previous = state['previous']
            if not isinstance(state['armed'], bool):
                raise ValueError('MLRSI_EVENTS_STATE_INVALID')
            self.armed = state['armed']
            if self.previous is not None:
                p = self.previous
                if (p['color'] not in ('GREEN', 'RED', 'NEUTRAL', 'UNKNOWN')
                        or not isinstance(p['valid'], bool) or not isinstance(p['timestamp'], int)
                        or p['timestamp'] % interval or (p['rsi'] is not None and not math.isfinite(p['rsi']))):
                    raise ValueError('MLRSI_EVENTS_STATE_INVALID')

    def dump(self):
        return dict(previous=self.previous, armed=self.armed)

    def step(self, timestamp, values):
        old = self.previous
        self.previous = dict(timestamp=timestamp, color=values['color'],
                             rsi=values['mlrsi_smoothed'], valid=values['valid'])
        if (not values['valid'] or not old or not old['valid']
                or timestamp - old['timestamp'] != self.interval):
            self.armed = False
            return None
        color = values['color']
        if color == 'NEUTRAL':
            self.armed = False
            return None
        side = 1 if color == 'GREEN' else -1
        good = (values['mlrsi_smoothed'] - old['rsi']) * side > 0
        changed = color != old['color']
        event = None
        if changed:
            self.armed = not good
            event = color + '_CROSS'
        if not good:
            self.armed = True
        elif self.armed and not changed:
            event = color + '_RESUME'
            self.armed = False
        return event
