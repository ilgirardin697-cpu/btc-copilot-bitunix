# Derived from the user-supplied BackQuant Pine source; MPL-2.0, © BackQuant.
"""LOW29/EMA4 PINE_PARITY, with literal source array/NA equality semantics.

Exact BackQuant TradingView parity is NOT proven. Historical research is frozen;
The source supplied directly by the user is authoritative. Paired TradingView
table values are regression evidence, not proof for every dataset/runtime.
"""
import copy
import math
import numpy as np

CAPTURED_CONFIG = {
    'source': 'LOW', 'rsi_length': 29, 'smooth': True, 'ma_type': 'EMA',
    'smoothing_period': 4, 'alma_sigma': 1, 'threshold_range_min': 10,
    'threshold_range_max': 90, 'step': 5, 'performance_memory': 10,
    'max_clustering_steps': 1000, 'max_data_points': 3000, 'clusters': 3,
    'wait_for_timeframe_close': True,
}
CONFIG_VERSION = 'CAPTURE_LOW29_EMA4_PINE_PARITY_V4'
MATH_MODE = 'PINE_PARITY'
RSI_LENGTH = CAPTURED_CONFIG['rsi_length']
PINE_ARRAY_LIMIT = 100000
TIMEFRAMES = {'15m': 900000, '1h': 3600000, '4h': 14400000}
COLORS = {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}


def pine_percentile(values, percentage):
    """Explicit linear interpolation: sorted finite samples, rank=(n-1)*p/100.

    No np.quantile dependency. All ten user-observed TV rows agree at two
    displayed decimals; positional interpolation of unsorted data does not.
    Whether the builtin mutates its array remains a separate diagnostic.
    Pine array statistics ignore missing elements unless all are missing.
    """
    if not 0 <= percentage <= 100:
        raise ValueError('MLRSI_PERCENTILE_INVALID')
    a = sorted(v for v in values if v is not None and math.isfinite(v))
    if not a:
        return None
    rank = (len(a) - 1) * percentage / 100
    left = math.floor(rank)
    right = math.ceil(rank)
    return a[left] + (a[right] - a[left]) * (rank - left)


def pine_arrays_equal(left, right):
    """Literal f_arrays_equal: NA != value is bool NA, hence false in Pine v5 IF.

    This is deliberately not Python list equality nor an improved equality.
    """
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a is not None and b is not None and a != b:
            return False
    return True


def pine_cluster_three(values, max_iter=1000, centroids=None):
    """Execute the author's constructors, NA slots, IF equality and break order.

    VAR carry starts with three NA slots, grows to six on the first bar (even
    with an empty array), then persists. Percentiles overwrite indices0..2.
    Three leading NA DISTANCES shift finite minima to indices>=3: all finite
    samples therefore reach cluster3. New centroids have three leading NA too.
    f_arrays_equal can return true BEFORE assigning these means. Do not turn
    this into conventional k-means: the normal source retains p25/p50/p75.
    """
    if not isinstance(max_iter, int) or max_iter < 0:
        raise ValueError('MLRSI_MAX_ITER_INVALID')
    data = np.asarray([v for v in values if v is not None], dtype=float)
    if not np.all(np.isfinite(data)):
        raise ValueError('MLRSI_CLUSTER_INPUT_INVALID')
    c = [None, None, None] if centroids is None else list(centroids)
    if len(values) > 3:
        c[:3] = [pine_percentile(values, p) for p in (25, 50, 75)]
    for iteration in range(max_iter + 1):
        # Ignore NA samples for array.avg; their membership cannot affect means.
        if len(data):
            centers = np.asarray([np.nan if x is None else x for x in c])
            distances = np.concatenate((np.full((len(data), 3), np.nan),
                                        np.abs(data[:, None] - centers[None, :])), axis=1)
            assignment = np.argmin(np.where(np.isnan(distances), np.inf, distances), axis=1)
            groups = np.where(assignment == 0, 0, np.where(assignment == 1, 1, 2))
            counts = np.bincount(groups, minlength=3)
            sums = np.bincount(groups, weights=data, minlength=3)
            means = [float(sums[i] / counts[i]) if counts[i] else None for i in range(3)]
        else:
            means = [None, None, None]
        updated = [None, None, None] + means  # array.new_float(3), THEN push
        if pine_arrays_equal(updated, c):
            return c, iteration + 1, True  # BREAK before centroids := new_centroids
        c = updated
    return c, max_iter + 1, False


class CausalSeries:
    """Committed LOW series plus Pine `var` array, never a rolling deque.

    Bootstrap caller supplies the LAST AVAILABLE bar index, including the open
    bar when present. RSI/EMA run on every bar; only bars satisfying the fixed
    bootstrap gate append. Subsequent realtime bars append without eviction.
    Default anchor zero models starting a chart with one available bar.
    Provisional clones implement rollback to the previous committed close.
    """
    def __init__(self, state=None):
        self.previous_low = None
        self.seed = []
        self.up = self.down = self.smoothed = None
        self.history = []
        self.pine_centroids = [None, None, None]
        self.bootstrap_last_bar_index = 0
        self.count = 0
        if state is not None:
            self.previous_low = state['previous_low']
            self.seed = state['seed']
            self.up, self.down, self.smoothed = state['up'], state['down'], state['smoothed']
            self.history.extend(state['history'])
            self.count = state['count']
            self.bootstrap_last_bar_index = state['bootstrap_last_bar_index']
            self.pine_centroids = list(state['pine_centroids'])
            values = [self.previous_low, self.up, self.down, self.smoothed, *self.history, *self.pine_centroids]
            if (state.get('rsi_length') != RSI_LENGTH or state.get('math_mode') != MATH_MODE
                    or len(state['history']) > PINE_ARRAY_LIMIT or len(self.seed) > RSI_LENGTH or self.count < 0
                    or type(self.bootstrap_last_bar_index) is not int or self.bootstrap_last_bar_index < 0
                    or len(self.pine_centroids) != (3 if self.count == 0 else 6)
                    or any(v is not None and not math.isfinite(v) for v in values)
                    or not isinstance(self.count, int)
                    or any(len(pair) != 2 or any(not math.isfinite(v) or v < 0 for v in pair) for pair in self.seed)
                    or any(v is not None and v < 0 for v in (self.up, self.down))):
                raise ValueError('MLRSI_SERIES_STATE_INVALID')

    def dump(self):
        return dict(rsi_length=RSI_LENGTH, math_mode=MATH_MODE,
                    bootstrap_last_bar_index=self.bootstrap_last_bar_index,
                    pine_centroids=list(self.pine_centroids),
                    previous_low=self.previous_low, seed=self.seed, up=self.up, down=self.down,
                    smoothed=self.smoothed, history=list(self.history), count=self.count)

    def configure_bootstrap(self, last_bar_index):
        if self.count or type(last_bar_index) is not int or last_bar_index < 0:
            raise ValueError('MLRSI_BOOTSTRAP_INVALID')
        self.bootstrap_last_bar_index = last_bar_index

    def push(self, low):
        low = float(low)
        if not math.isfinite(low) or low <= 0:
            raise ValueError('MLRSI_LOW_INVALID')
        bar_index = self.count
        eligible = max(self.bootstrap_last_bar_index, bar_index) - bar_index <= CAPTURED_CONFIG['max_data_points']
        if eligible and len(self.history) >= PINE_ARRAY_LIMIT:
            raise ValueError('MLRSI_PINE_ARRAY_LIMIT')
        self.count += 1
        raw = None
        if self.previous_low is not None:
            change = low - self.previous_low
            gain, loss = max(change, 0.), max(-change, 0.)
            if self.up is None:
                self.seed.append([gain, loss])
                if len(self.seed) == RSI_LENGTH:
                    # Same Wilder seed policy, now the first 29 LOW differences.
                    self.up = sum(p[0] for p in self.seed) / RSI_LENGTH
                    self.down = sum(p[1] for p in self.seed) / RSI_LENGTH
            else:
                alpha = 1 / RSI_LENGTH  # documented ta.rma recurrence
                self.up = alpha * gain + (1 - alpha) * self.up
                self.down = alpha * loss + (1 - alpha) * self.down
            if self.up is not None and self.up + self.down:
                raw = 100. if self.down == 0 else 100 - 100 / (1 + self.up / self.down)
        self.previous_low = low
        if raw is not None:
            alpha = 2 / (CAPTURED_CONFIG['smoothing_period'] + 1)
            self.smoothed = raw if self.smoothed is None else alpha * raw + (1 - alpha) * self.smoothed
        # Literal <= gate, including NA slots during seed if they are eligible.
        # On new realtime bars last_bar_index == bar_index; no shift/remove.
        if eligible:
            self.history.append(self.smoothed if raw is not None else None)
        result = dict(mlrsi_raw=raw, mlrsi_smoothed=self.smoothed if raw is not None else None,
                      valid=False, converged=False, window_count=len(self.history),
                      threshold_sample_count=len(self.history), iterations=0,
                      lower_threshold=None, middle_centroid=None, upper_threshold=None, color='UNKNOWN')
        # Source clustering executes EVERY bar, including empty/NA warmup. That
        # first execution is essential to the persistent three -> six carry.
        c, iterations, converged = pine_cluster_three(self.history, CAPTURED_CONFIG['max_clustering_steps'], self.pine_centroids)
        self.pine_centroids = c
        result.update(converged=bool(converged), iterations=int(iterations))
        if raw is not None and len(self.history) >= 4:
            valid = all(v is not None and math.isfinite(v) for v in c[:3])
            color = ('GREEN' if self.smoothed > c[2] else 'RED' if self.smoothed < c[0] else 'NEUTRAL') if valid else 'UNKNOWN'
            result.update(lower_threshold=c[0], middle_centroid=c[1], upper_threshold=c[2], color=color,
                          valid=valid, converged=bool(converged), iterations=int(iterations))
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
