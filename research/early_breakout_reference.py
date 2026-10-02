"""Offline reproduction of existing pure MANUAL_COPILOT_V1 rules, never a client."""
from collections import deque
import numpy as np
from guardian_signals import rolling_mlrsi, direction, current_entry_quality
from early_breakout_core import aggregate, STEP


def segmented(rows, step):
    cuts = np.r_[0, np.flatnonzero(np.diff(rows[:, 0]) != step)+1, len(rows)]
    return list(zip(cuts[:-1], cuts[1:]))


def hourly_features(h):
    trend, momentum, atr, age = np.zeros(len(h), int), np.zeros(len(h), int), np.full(len(h), np.nan), np.zeros(len(h), int)
    for start, end in segmented(h, 3600000):
        part = h[start:end]
        count = end-start
        age[start:end] = np.arange(1, count+1)
        if count >= 200:
            means = np.convolve(part[:, 4], np.ones(200)/200, mode='valid')
            trend[start+199:end] = np.where(part[199:, 4] > means, 1, -1)
        ml = rolling_mlrsi(part[:, 3], length=27, max_data=3000, max_iter=1000)
        momentum[start:end] = ml['state']
        previous = np.r_[part[0, 4], part[:-1, 4]]
        tr = np.maximum(part[:, 2]-part[:, 3], np.maximum(abs(part[:, 2]-previous), abs(part[:, 3]-previous)))
        if count >= 15:
            value = float(tr[:14].mean())
            atr[start+13] = value
            for i in range(14, count):
                value = (13*value+tr[i])/14
                atr[start+i] = value
    return trend, momentum, atr, age


def manual_reference(base, q):
    h, f = aggregate(base, 3600000), aggregate(base, 14400000)
    trend1, momentum, atr, age_h = hourly_features(h)
    trend4, age_f = np.zeros(len(f), int), np.zeros(len(f), int)
    for start, end in segmented(f, 14400000):
        age_f[start:end] = np.arange(1, end-start+1)
        if end-start >= 200:
            mean = np.convolve(f[start:end, 4], np.ones(200)/200, mode='valid')
            trend4[start+199:end] = np.where(f[start+199:end, 4] > mean, 1, -1)
    hi = np.searchsorted(h[:, 0]+3600000, q[:, 0]+STEP, side='right')-1
    fi = np.searchsorted(f[:, 0]+14400000, q[:, 0]+STEP, side='right')-1
    confirmations = {1: [], -1: []}
    regimes = np.zeros(len(q), int)
    highs, lows = deque(), deque()
    start = 0
    for i, bar in enumerate(q):
        if i and bar[0]-q[i-1, 0] != STEP:
            start, highs, lows = i, deque(), deque()
        if i-start >= 4:
            pivot = q[i-2]
            window = q[i-4:i+1]
            if pivot[2] == window[:, 2].max() and np.count_nonzero(window[:, 2] == pivot[2]) == 1:
                highs.append((i, float(pivot[2])))
            if pivot[3] == window[:, 3].min() and np.count_nonzero(window[:, 3] == pivot[3]) == 1:
                lows.append((i, float(pivot[3])))
        while highs and highs[0][0] < i-215:
            highs.popleft()
        while lows and lows[0][0] < i-215:
            lows.popleft()
        j, k = hi[i], fi[i]
        if j < 0 or k < 0 or not trend1[j] or not trend4[k]:
            continue
        if trend1[j] == trend4[k]:
            regimes[i] = trend1[j]
        # Match native live fetch freshness/window constraints conservatively after gaps.
        if (i-start+1 < 220 or age_h[j] < 3200 or age_f[k] < 220
                or bar[0]+STEP-(h[j, 0]+3600000) >= 3600000
                or bar[0]+STEP-(f[k, 0]+14400000) >= 14400000 or h[j, 5] <= 0):
            continue
        structure = 'MIXED'
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]:
                structure = 'BULLISH'
            elif highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]:
                structure = 'BEARISH'
        moment = {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[int(momentum[j])]
        bias, _ = direction('BULL' if trend4[k] == 1 else 'BEAR', 'BULL' if trend1[j] == 1 else 'BEAR',
                            moment, float(h[j, 6]/h[j, 5]), structure)
        if bias not in ('LONG_ALLOWED', 'SHORT_ALLOWED') or len(highs) < 2 or len(lows) < 2 or not np.isfinite(atr[j]):
            continue
        price = bar[4]
        resistance = min((level for _, level in highs if level >= price), default=None)
        support = max((level for _, level in lows if level <= price), default=None)
        long = bias == 'LONG_ALLOWED'
        opposing = resistance if long else support
        pivots = highs if long else lows
        broken = [level for confirmation, level in pivots if confirmation < i and (level < price if long else level > price)]
        level = (max(broken) if long else min(broken)) if broken else None
        near = opposing is not None and abs(opposing-price) <= .5*atr[j]
        extended = level is not None and abs(price-level) > 2*atr[j]
        reclaim = level is not None and (bar[3] <= level < price if long else bar[2] >= level > price)
        aligned = moment == ('GREEN' if long else 'RED') and structure == ('BULLISH' if long else 'BEARISH')
        good = not near and not extended and reclaim and aligned and opposing is not None
        data = dict(bias=bias, entry_quality='GOOD' if good else 'CAUTION', entry_level=level,
                    resistance=resistance, support=support, entry_atr_1h=float(atr[j]))
        if current_entry_quality(data, price)['entry_quality'] == 'GOOD':
            confirmations[1 if long else -1].append(int(bar[0]+STEP))
    return {side: np.asarray(stamps, dtype=np.int64) for side, stamps in confirmations.items()}, regimes
