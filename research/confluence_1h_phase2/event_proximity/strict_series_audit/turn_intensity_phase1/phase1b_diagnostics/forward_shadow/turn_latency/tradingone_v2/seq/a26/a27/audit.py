"""Independent mathematical diagnostics; never imports or executes APK/JavaScript.

Existing public-source ports retain their original notices. New comparisons are
not platform parity certification, a strategy or an execution implementation.
"""
from bisect import insort
from dataclasses import dataclass
import importlib
import math
import numpy as np
from research.confluence_1h.indicators import roll, smooth, bbwp

TV2 = ('research.confluence_1h_phase2.event_proximity.strict_series_audit.'
       'turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2')
original = importlib.import_module(TV2 + '.backquant')
profile = importlib.import_module(TV2 + '.profile')
HOUR = 3_600_000


def checked_bars(bars, timeframe_ms, cutoff):
    a = np.asarray(bars, float)
    if a.ndim != 2 or a.shape[1] != 6 or not len(a) or not np.isfinite(a).all():
        raise ValueError('OHLCV_REQUIRED')
    t, o, h, l, c, v = a.T
    if np.any(t != t.astype(np.int64)) or np.any(np.diff(t) != timeframe_ms):
        raise ValueError('CHRONOLOGY')
    if np.any(t + timeframe_ms > cutoff):
        raise ValueError('CLOSED_ONLY')
    if np.any(l <= 0) or np.any(l > np.minimum(o, c)) or np.any(h < np.maximum(o, c)) or np.any(v < 0):
        raise ValueError('OHLCV_RANGE')
    return a


def rsi(values, length):
    """Wilder RSI. Explicit zero-denominator policy, matching APK's stated branch."""
    x = np.asarray(values, float)
    d = np.r_[np.nan, np.diff(x)]
    gain = smooth(np.maximum(d, 0), length, 'rma')
    loss = smooth(np.maximum(-d, 0), length, 'rma')
    out = np.full(len(x), np.nan)
    for i, (u, v) in enumerate(zip(gain, loss)):
        if np.isfinite(u) and np.isfinite(v):
            out[i] = 100 if v == 0 else 0 if u == 0 else 100 * u / (u + v)
    return out


def smoothed_rsi(low, length=27, method='SMA'):
    raw = rsi(low, length)
    if method == 'SMA':
        return roll(raw, 4)
    if method == 'EMA':
        return smooth(raw, 4, 'ema')
    if method == 'ALMA':
        weights = np.exp(-np.arange(4, dtype=float)**2 / 32)  # offset0, sigma1
        out = np.full(len(raw), np.nan)
        if len(raw) >= 4:
            out[3:] = np.lib.stride_tricks.sliding_window_view(raw, 4) @ weights / weights.sum()
        return out
    raise ValueError('AUDITED_PROFILE_ONLY')


def percentile_thresholds(values, anchor, *, finite_only=False):
    """Compare literal source membership with APK's finite-value compaction.

    Fixed load anchor, no rolling eviction. Realtime append keeps the anchor;
    reloading with a new anchor is a different experiment, not prefix invariance.
    """
    if type(anchor) is not int or anchor < 0:
        raise ValueError('LOAD_ANCHOR_REQUIRED')
    result = np.full((len(values), 3), np.nan)
    ordered = []
    members = 0
    for i, x in enumerate(values):
        if max(anchor, i) - i > 3000:
            continue
        finite = np.isfinite(x)
        if finite:
            insort(ordered, float(x))
        if finite or not finite_only:
            members += 1
        if members > 3 and ordered:
            result[i] = [original.percentile(ordered, p) for p in (25, 50, 75)]
    return result


def lloyd_diagnostic(values, max_iterations=1000):
    """Conventional three-means, diagnostic alternative only, never a replacement."""
    a = np.asarray(values, float)
    a = a[np.isfinite(a)]
    if len(a) <= 3:
        return np.full(3, np.nan)
    centres = np.array([original.percentile(a, p) for p in (25, 50, 75)])
    for _ in range(max_iterations + 1):
        group = np.abs(a[:, None] - centres[None, :]).argmin(axis=1)
        new = np.array([a[group == j].mean() if np.any(group == j) else np.nan for j in range(3)])
        if np.array_equal(new, centres):
            break
        centres = new
        if not np.isfinite(centres).all():
            break
    return centres


def crosses(value, lower, upper):
    result = np.zeros(len(value), int)
    for i in range(1, len(value)):
        if not np.isfinite([value[i], value[i-1], lower[i], lower[i-1], upper[i], upper[i-1]]).all():
            continue
        if value[i] > upper[i] and value[i-1] <= upper[i-1]:
            result[i] = 1
        elif value[i] < lower[i] and value[i-1] >= lower[i-1]:
            result[i] = -1
    return result


def fractal_energy(bars):
    """Loren's declared CHOP27/HMA5 formula. Not a private Bitman parity claim.

    HMA5 uses WMA2(2*WMA2(raw)-WMA5(raw)); no clipping of its overshoot.
    Undefined log(0) remains unavailable. The source's zero-range guard is kept.
    """
    a = np.asarray(bars, float)
    h, l, c = a[:, 2], a[:, 3], a[:, 4]
    tr = h - l
    tr[1:] = np.maximum(tr[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    total = roll(tr, 27, 'sum')
    span = roll(h, 27, 'max') - roll(l, 27, 'min')
    ratio = total / np.where(span == 0, 1, span)
    raw = np.full(len(a), np.nan)
    good = np.isfinite(ratio) & (ratio > 0)
    raw[good] = 100 * np.log10(ratio[good]) / math.log10(27)
    return raw, profile.wma(2 * profile.wma(raw, 2) - profile.wma(raw, 5), 2)


@dataclass
class SharedCooldown:
    last: int = -9999

    def accept(self, index, cross, fe_now, fe_previous, recent_max, trend_ok=True):
        if cross not in (-1, 0, 1):
            raise ValueError('CROSS_REQUIRED')
        valid = (cross != 0 and np.isfinite([fe_now, fe_previous, recent_max]).all()
                 and fe_now < fe_previous and fe_now > 38.2 and recent_max >= 50
                 and trend_ok and index - self.last > 10)
        if valid:
            self.last = index
        return int(cross) if valid else 0


def trend_mean_reference(close, length, accel):
    """Scalar math check of Zeiierman's CC BY-NC-SA4.0 mean, not speed histogram.

    Original source/notice retained in TradingOne profile; noncommercial research.
    """
    out = []
    deltas = []
    for i, c in enumerate(close):
        deltas.append(abs(c - (close[i-1] if i else 0)))
        max_price = max(abs(x) for x in close[max(0, i-199):i+1])
        norm = (c + max_price) / (2 * max_price) if max_price else .5
        dynamic = 5 + norm * (length - 5)
        alpha = min(1, 2 / (dynamic + 1) * (1 + deltas[-1] / (max(deltas[-200:]) or 1) * accel))
        out.append(c if not out else alpha*c + (1-alpha)*out[-1])
    return np.array(out)


def apk_bbwp_reference(close, period=13, lookback=252):
    """Independent math of generic APK BBWP: includes current width in its rank."""
    mean = roll(close, period)
    width = 4 * roll(close, period, 'std') / mean
    out = np.full(len(close), np.nan)
    for i in range(period-1, len(close)):
        window = width[max(period-1, i-lookback+1):i+1]
        out[i] = 100 * np.count_nonzero(window <= width[i]) / len(window)
    return out


def tradingone_bbwp(close):
    width = 2 * roll(close, 13, 'std') / roll(close, 13)
    return bbwp(width, 252, 13)


def rejection_observations(bars, mean):
    """Descriptive closed-bar touch/rejection. Own definition, not Bitman signal."""
    a = np.asarray(bars, float)
    down = (a[:, 2] >= mean) & (a[:, 1] < mean) & (a[:, 4] < mean)
    up = (a[:, 3] <= mean) & (a[:, 1] > mean) & (a[:, 4] > mean)
    return np.where(down, -1, np.where(up, 1, 0))
