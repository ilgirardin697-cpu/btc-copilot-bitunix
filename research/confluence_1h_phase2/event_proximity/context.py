"""Closed public Spot context; descriptive AO/DMI, not a strategy filter."""
import numpy as np
from research.confluence_1h.indicators import calculate, roll
from ..semantics import HOUR, iso, validate_bars

DAY = 24 * HOUR
INTERVALS = {'4H': (4*HOUR, 0), '1D': (DAY, 0), '1W': (7*DAY, 4*DAY)}


def aggregate(bars, interval, offset=0):
    a = validate_bars(bars)
    keys = ((a[:, 0]-offset)//interval)*interval+offset
    out = []
    for t in np.unique(keys):
        group = a[keys == t]
        if len(group) != interval//HOUR or group[0, 0] != t or group[-1, 0]+HOUR != t+interval:
            continue  # partial boundary group, never filled or treated as closed
        out.append([t, group[0, 1], max(group[:, 2]), min(group[:, 3]), group[-1, 4], sum(group[:, 5])])
    return np.asarray(out, float).reshape(-1, 6)


def context_at(bars, available_at):
    # Cut hourly input BEFORE aggregation and feature computation.
    closed = np.asarray(bars)[np.asarray(bars)[:, 0]+HOUR <= available_at]
    result = {}
    for name, (interval, offset) in INTERVALS.items():
        a = aggregate(closed, interval, offset)
        if not len(a):
            result[name] = {'status': 'INSUFFICIENT_CLOSED_HISTORY'}
            continue
        f = calculate(a)
        get = lambda k: float(f[k][-1]) if np.isfinite(f[k][-1]) else None
        ao, p, m = get('ao'), get('plus_di'), get('minus_di')
        comparable = ao is not None and p is not None and m is not None
        # Existing Bitman sign/DMI agreement convention, diagnostic only on Spot.
        bias = 'UNKNOWN' if not comparable else 'DOWN' if ao < 0 and m > p else 'UP' if ao > 0 and p > m else 'TRANSITION'
        sma = roll(a[:, 4], 200)[-1]
        result[name] = dict(status='CLOSED', open_utc=iso(int(a[-1, 0])),
                            available_at=iso(int(a[-1, 0]+interval)), bars=len(a),
                            ao=ao, ao_slope=get('ao_slope'), adx=get('adx'),
                            plus_di=p, minus_di=m, bias_ao_dmi=bias,
                            close=float(a[-1, 4]), sma200=float(sma) if np.isfinite(sma) else None,
                            full_bbwp_history_available=len(a)>=108,
                            source='BINANCE_SPOT', usage='DESCRIPTIVE_NOT_AN_ENTRY_FILTER')
    return result
