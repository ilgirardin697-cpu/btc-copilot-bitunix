"""Pure causal ML RSI math port; no TradingView chart parity claim."""
from collections import deque
import numpy as np

RULE_VERSION = 'MANUAL_COPILOT_V1'
ML_RSI27_REAL = {
    'name': 'ML_RSI27_REAL', 'source': 'LOW', 'rsi_length': 27,
    'smoothing': 'EMA', 'smoothing_length': 4, 'smooth': True,
    'max_iter': 1000, 'max_data': 3000, 'clusters': 3,
}


def closed_bars(rows, now_ms, interval_ms):
    """Schema: open_time,open,high,low,close,volume,taker_buy."""
    a = np.asarray(rows, float)
    if a.ndim != 2 or a.shape[1] != 7 or not np.all(np.isfinite(a)):
        raise ValueError('INVALID_CANDLES')
    a = a[np.argsort(a[:, 0])]
    if np.any(np.diff(a[:, 0]) <= 0) or np.any(a[:, 0] % interval_ms != 0):
        raise ValueError('CANDLE_TIMESTAMPS_INVALID')
    if np.any(a[:, 3] <= 0) or np.any(a[:, 2] < a[:, 3]) or np.any(a[:, 4] < a[:, 3]) or np.any(a[:, 4] > a[:, 2]):
        raise ValueError('CANDLE_RANGE_INVALID')
    return a[a[:, 0] + interval_ms <= now_ms]


def atr14(rows):
    a = np.asarray(rows, float)
    if len(a) < 15:
        return None
    prev = np.r_[a[0, 4], a[:-1, 4]]
    tr = np.maximum(a[:, 2] - a[:, 3], np.maximum(abs(a[:, 2] - prev), abs(a[:, 3] - prev)))
    result = float(tr[:14].mean())
    for value in tr[14:]:
        result = (13 * result + value) / 14
    return result if result > 0 and np.isfinite(result) else None


def volatility_state(atr, mark):
    if atr is None or not np.isfinite(atr) or mark <= 0:
        return 'UNKNOWN'
    ratio = atr / mark
    return 'HIGH' if ratio >= .04 else 'ELEVATED' if ratio >= .02 else 'NORMAL'


def latest_mlrsi(values, length=27, max_data=3000, max_iter=1000):
    """Calculate only current and prior causal states; live-cycle cost stays bounded."""
    source = np.asarray(values, float)
    smoothed = pine_ema(pine_rsi(source, length), 4)
    indexes = np.flatnonzero(np.isfinite(smoothed))[-2:]
    if len(indexes) < 2:
        raise ValueError('MOMENTUM_WARMUP')
    states, thresholds = [], []
    for index in indexes:
        history = smoothed[:index + 1]
        history = history[np.isfinite(history)][-max_data:]
        if len(history) < 4:
            raise ValueError('MOMENTUM_WARMUP')
        centers, _, converged = cluster_three(history, max_iter)
        if not converged:
            raise ValueError('MOMENTUM_NOT_CONVERGED')
        value = smoothed[index]
        states.append(1 if value > centers[2] else -1 if value < centers[0] else 0)
        thresholds.append(centers)
    prior, current = states
    return dict(rsi=float(smoothed[indexes[-1]]), state=current,
                green_event=prior == 0 and current == 1,
                red_event=prior == 0 and current == -1,
                long_threshold=float(thresholds[-1][2]), short_threshold=float(thresholds[-1][0]),
                window_count=min(max_data, int(np.isfinite(smoothed).sum())), converged=True)


def confirmed_structure(rows, left=2, right=2):
    highs, lows = [], []
    for confirmation in range(left + right, len(rows)):
        pivot = confirmation - right
        neighborhood = rows[pivot-left:pivot+right+1]
        h, l = rows[pivot, 2], rows[pivot, 3]
        if h == max(neighborhood[:, 2]) and np.count_nonzero(neighborhood[:, 2] == h) == 1:
            highs.append((confirmation, h))
        if l == min(neighborhood[:, 3]) and np.count_nonzero(neighborhood[:, 3] == l) == 1:
            lows.append((confirmation, l))
    state = 'MIXED'
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]:
            state = 'BULLISH'
        elif highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]:
            state = 'BEARISH'
    return state, highs, lows


def flow_state(ratio):
    if not np.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('FLOW_INVALID')
    if ratio >= .60:
        return 'STRONG BUY'
    if ratio >= .55:
        return 'BUY'
    if ratio <= .40:
        return 'STRONG SELL'
    if ratio <= .45:
        return 'SELL'
    return 'NEUTRAL'


def direction(trend4, trend1, momentum, ratio, structure):
    if 'UNKNOWN' in (trend4, trend1, momentum, structure) or ratio is None:
        return 'UNKNOWN', 'Insufficient closed market data'
    if trend4 != trend1:
        return 'WAIT', '4H and 1H regimes disagree'
    long_votes = sum((momentum == 'GREEN', ratio >= .55, structure == 'BULLISH'))
    short_votes = sum((momentum == 'RED', ratio <= .45, structure == 'BEARISH'))
    if trend4 == trend1 == 'BULL' and long_votes >= 2:
        return 'LONG_ALLOWED', 'Both trends bullish; two confirmations. WHY NOT SHORT: 4H/1H bullish'
    if trend4 == trend1 == 'BEAR' and short_votes >= 2:
        return 'SHORT_ALLOWED', 'Both trends bearish; two confirmations. WHY NOT LONG: 4H/1H bearish'
    return 'WAIT', 'Fewer than two matching momentum/flow/structure confirmations'


def entry_quality(bias, hourly, quarter_hourly, momentum, structure):
    """Display only: closed-price timing, never a direction or capital-risk gate.

    Frozen V1: within 0.5 hourly ATR of an opposing pivot or more than 2 ATR
    beyond the nearest reclaimed pivot is POOR. GOOD requires an actual closed
    15m reclaim of a previously confirmed pivot, matching momentum/structure,
    and complete pivot/ATR evidence. Otherwise CAUTION. No parameter search.
    """
    result = dict(entry_quality='CAUTION', entry_reason='INSUFFICIENT_EVIDENCE',
                  entry_level=None, resistance=None, support=None, entry_atr_1h=None,
                  entry_reference_price=None)
    if bias not in ('LONG_ALLOWED', 'SHORT_ALLOWED'):
        return result
    atr = atr14(hourly)
    _, highs, lows = confirmed_structure(quarter_hourly)
    if atr is None or len(highs) < 2 or len(lows) < 2:
        return result
    price = float(quarter_hourly[-1, 4])
    resistance = min((float(level) for _, level in highs if level >= price), default=None)
    support = max((float(level) for _, level in lows if level <= price), default=None)
    result.update(entry_reference_price=price, entry_atr_1h=atr,
                  resistance=resistance, support=support)
    long = bias == 'LONG_ALLOWED'
    opposing = resistance if long else support
    pivots = highs if long else lows
    # Reclaim must use a pivot already confirmed before the latest closed bar.
    broken = [float(level) for confirmation, level in pivots
              if confirmation < len(quarter_hourly) - 1
              and (level < price if long else level > price)]
    level = (max(broken) if long else min(broken)) if broken else None
    result['entry_level'] = level
    if opposing is not None and abs(opposing - price) <= .5 * atr:
        result.update(entry_quality='POOR', entry_reason='NEAR_RESISTANCE' if long else 'NEAR_SUPPORT')
    elif level is not None and abs(price - level) > 2 * atr:
        result.update(entry_quality='POOR', entry_reason='EXTENDED')
    else:
        reclaim = level is not None and (quarter_hourly[-1, 3] <= level < price if long
                                        else quarter_hourly[-1, 2] >= level > price)
        aligned = momentum == ('GREEN' if long else 'RED') and structure == ('BULLISH' if long else 'BEARISH')
        if reclaim and aligned and opposing is not None:
            result.update(entry_quality='GOOD', entry_reason='CONFIRMED_RECLAIM')
        else:
            result['entry_reason'] = 'WAIT_RECLAIM'
    return result


def snapshot(hourly, four_hourly, quarter_hourly, now_ms):
    h = closed_bars(hourly, now_ms, 3600000)
    f = closed_bars(four_hourly, now_ms, 14400000)
    q = closed_bars(quarter_hourly, now_ms, 900000)
    for rows, interval in ((h, 3600000), (f, 14400000), (q, 900000)):
        if len(rows) < 200 or now_ms - (rows[-1, 0] + interval) >= interval:
            raise ValueError('DIRECTION_DATA_INSUFFICIENT_OR_STALE')
        if np.any(np.diff(rows[:, 0]) != interval):
            raise ValueError('DIRECTION_DATA_GAP')
    trend1 = 'BULL' if h[-1, 4] > np.mean(h[-200:, 4]) else 'BEAR'
    trend4 = 'BULL' if f[-1, 4] > np.mean(f[-200:, 4]) else 'BEAR'
    # User-confirmed TradingView calculation source is LOW (column 3).
    # SMA trend continues to use CLOSE; historical CLOSE research is unchanged.
    ml = latest_mlrsi(h[:, 3], length=ML_RSI27_REAL['rsi_length'],
                      max_data=ML_RSI27_REAL['max_data'], max_iter=ML_RSI27_REAL['max_iter'])
    if h[-1, 5] <= 0:
        raise ValueError('MOMENTUM_OR_FLOW_UNAVAILABLE')
    momentum = {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[int(ml['state'])]
    ratio = float(h[-1, 6] / h[-1, 5])
    structure = confirmed_structure(q)[0]
    bias, why = direction(trend4, trend1, momentum, ratio, structure)
    return dict(version=RULE_VERSION, bias=bias, why=why, trend4=trend4, trend1=trend1,
                momentum_preset=ML_RSI27_REAL['name'], momentum_source=ML_RSI27_REAL['source'],
                momentum_parameters=dict(ML_RSI27_REAL),
                momentum=momentum, green_event=bool(ml['green_event']), red_event=bool(ml['red_event']),
                rsi27=float(ml['rsi']), long_threshold=float(ml['long_threshold']),
                short_threshold=float(ml['short_threshold']), window_count=int(ml['window_count']),
                flow=flow_state(ratio), taker_buy=ratio, structure=structure,
                last_closed_1h=int(h[-1, 0] + 3600000),
                **entry_quality(bias, h, q, momentum, structure))

def pine_rsi(close, length):
    """Wilder RMA seeded by the first length price changes, not the first bar."""
    close = np.asarray(close, float)
    result = np.full(len(close), np.nan)
    if len(close) <= length:
        return result
    changes = np.diff(close)
    gain = np.maximum(changes, 0)
    loss = np.maximum(-changes, 0)
    up, down = float(gain[:length].mean()), float(loss[:length].mean())
    for i in range(length, len(close)):
        if i > length:
            up = (up * (length - 1) + gain[i - 1]) / length
            down = (down * (length - 1) + loss[i - 1]) / length
        result[i] = 100 * up / (up + down) if up + down else np.nan
    return result


def pine_ema(values, length=4):
    """First finite value initializes EMA; unavailable leading values stay NaN."""
    result = np.full(len(values), np.nan)
    previous = np.nan
    alpha = 2 / (length + 1)
    for i, value in enumerate(values):
        if np.isfinite(value):
            previous = value if not np.isfinite(previous) else alpha * value + (1 - alpha) * previous
            result[i] = previous
    return result


def cluster_three(values, max_iter=1000):
    """Lloyd iteration for 1D absolute-distance assignment and mean update.

    Sorted partitions and prefix sums are mathematically equivalent to assigning
    every sample individually. Every candle REINITIALIZES at p25/p50/p75.
    Summation order can differ from Pine by machine precision. Empty clusters
    retain their prior centroid (explicit deterministic degenerate-data policy).
    """
    values = np.sort(np.asarray(values, float))
    if len(values) < 4 or not np.all(np.isfinite(values)):
        raise ValueError('Need at least four finite RSI observations')
    if max_iter < 1:
        raise ValueError('maxIter must be positive')
    centers = np.quantile(values, [.25, .5, .75], method='linear')
    sums = np.r_[0., np.cumsum(values)]
    previous_boundaries = None
    for iteration in range(max_iter):
        # Midpoint belongs to earlier/lower centroid on an exact distance tie.
        boundaries = tuple(np.searchsorted(values, (centers[:-1] + centers[1:]) / 2, side='right'))
        if boundaries == previous_boundaries:
            return centers, iteration, True
        limits = (0, *boundaries, len(values))
        updated = centers.copy()
        for k in range(3):
            start, end = limits[k:k + 2]
            if end > start:
                updated[k] = (sums[end] - sums[start]) / (end - start)
        if np.array_equal(updated, centers):
            return updated, iteration + 1, True
        centers = updated
        previous_boundaries = boundaries
    return centers, max_iter, False


def states_and_events(rsi, short_threshold, long_threshold):
    valid = np.isfinite(rsi) & np.isfinite(short_threshold) & np.isfinite(long_threshold)
    state = np.zeros(len(rsi), np.int8)
    state[valid & (rsi > long_threshold)] = 1
    state[valid & (rsi < short_threshold)] = -1
    prior_valid = np.r_[False, valid[:-1]]
    prior_neutral = np.r_[False, state[:-1] == 0] & prior_valid
    return state, valid & prior_neutral & (state == 1), valid & prior_neutral & (state == -1), valid


def rolling_mlrsi(close, length=14, max_data=3000, max_iter=1000):
    if max_data < 4:
        raise ValueError('maxData must be at least four')
    smoothed = pine_ema(pine_rsi(close, length), 4)
    centers = np.full((len(close), 3), np.nan)
    counts = np.zeros(len(close), int)
    iterations = np.zeros(len(close), int)
    converged = np.zeros(len(close), bool)
    history = deque(maxlen=max_data)
    for i, value in enumerate(smoothed):
        if np.isfinite(value):
            history.append(value)
        counts[i] = len(history)
        if len(history) >= 4 and np.isfinite(value):
            centers[i], iterations[i], converged[i] = cluster_three(history, max_iter)
    state, green, red, valid = states_and_events(smoothed, centers[:, 0], centers[:, 2])
    return {'rsi': smoothed, 'centroids': centers, 'short_threshold': centers[:, 0],
            'long_threshold': centers[:, 2], 'state': state, 'green_event': green,
            'red_event': red, 'valid': valid, 'window_count': counts,
            'iterations': iterations, 'converged': converged}
