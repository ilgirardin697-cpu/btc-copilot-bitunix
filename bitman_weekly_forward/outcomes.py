"""Frozen descriptive outcome equations from PR31, not execution performance."""
import numpy as np
PCTS=(5,10,15,20)
ATRS=(1,1.5,2)
def causal_range(frame, i, length):
    if i + 1 < length:
        return (np.nan, np.nan)
    past = frame[i - length + 1:i + 1]
    return (float(np.max(past[:, 2])), float(np.min(past[:, 3])))

def outcomes(f, length, horizon):
    """Frozen-range forward measurements; incomplete horizons remain missing."""
    frame, n = (f['frame'], len(f['frame']))
    keys = ('forward', 'absolute', 'up', 'down', 'max_move', 'max_atr', 'breakout', 'wick_breakout', 'first_side', 'first_week', 'wick_side', 'beyond_up', 'beyond_down', 'beyond_atr', 'reentered', 'end_outside', 'sustained', 'persistence_followup', 'range_atr', 'congestion', *('large_' + str(p) for p in PCTS), *('move_' + str(p) for p in PCTS), *('atr_' + str(t) for t in ATRS))
    out = {k: np.full(n, np.nan) for k in keys}
    for i in range(length - 1, n - horizon):
        if not f['valid'][i]:
            continue
        anchor, atr = (frame[i, 4], f['atr'][i])
        high, low = causal_range(frame, i, length)
        future = frame[i + 1:i + horizon + 1]
        up, down = (max(0.0, float(np.max(future[:, 2]) - anchor)), max(0.0, float(anchor - np.min(future[:, 3]))))
        maximum = max(up, down)
        close_up, close_down = (future[:, 4] > high, future[:, 4] < low)
        broke = np.flatnonzero(close_up | close_down)
        touched_up, touched_down = (future[:, 2] > high, future[:, 3] < low)
        wick = np.flatnonzero(touched_up | touched_down)
        first = int(broke[0]) if len(broke) else None
        side = (1 if close_up[first] else -1) if first is not None else 0
        wick_side = 0 if not len(wick) else 2 if touched_up[wick[0]] and touched_down[wick[0]] else 1 if touched_up[wick[0]] else -1
        reentered = bool(np.any(future[first + 1:, 4] <= high) if side == 1 else np.any(future[first + 1:, 4] >= low)) if side else False
        followup = horizon - first - 1 if first is not None else 0
        values = dict(forward=100 * (future[-1, 4] / anchor - 1), absolute=100 * abs(future[-1, 4] / anchor - 1), up=100 * up / anchor, down=100 * down / anchor, max_move=100 * maximum / anchor, max_atr=maximum / atr, breakout=float(bool(len(broke))), wick_breakout=float(bool(len(wick))), first_side=side, first_week=first + 1 if first is not None else np.nan, wick_side=wick_side, beyond_up=100 * max(0.0, np.max(future[:, 2]) - high) / anchor, beyond_down=100 * max(0.0, low - np.min(future[:, 3])) / anchor, beyond_atr=max(0.0, np.max(future[:, 2]) - high, low - np.min(future[:, 3])) / atr, reentered=float(reentered) if side else np.nan, end_outside=float(future[-1, 4] > high if side == 1 else future[-1, 4] < low) if side else np.nan, sustained=float(not reentered) if side and followup else np.nan, persistence_followup=followup, range_atr=(high - low) / atr, congestion=float(high - low <= 2 * atr))
        for p in PCTS:
            values['move_' + str(p)] = float(100 * maximum / anchor >= p)
            values['large_' + str(p)] = float(np.any(close_up) and 100 * up / anchor >= p or (np.any(close_down) and 100 * down / anchor >= p))
        for t in ATRS:
            values['atr_' + str(t)] = float(maximum / atr >= t)
        for name, value in values.items():
            out[name][i] = value
    return out
