"""Causal numerical conventions frozen in protocol.json; no account access."""
from bisect import bisect_left, bisect_right, insort
from collections import deque
import numpy as np
from research.confluence_1h.indicators import calculate, lag, regime

HOUR = 3600000
PATTERNS = ('P1_PEAK_EXHAUSTION', 'P2_TROUGH_ONSET', 'P3_FAILED_RECOVERY')
STRATA = {'ALL': 0., 'Q75': .75, 'Q90': .9}


def prior_rank(values, window=720):
    """Midrank against exactly window earlier slots; no current/future samples."""
    values = np.asarray(values, float)
    out = np.full(len(values), np.nan)
    raw, ordered = deque(), []
    for i, x in enumerate(values):
        if len(raw) == window and len(ordered) == window and np.isfinite(x):
            out[i] = (bisect_left(ordered, x) + bisect_right(ordered, x))/(2*window)
        raw.append(x)
        if np.isfinite(x):
            insort(ordered, float(x))
        if len(raw) > window:
            old = raw.popleft()
            if np.isfinite(old):
                ordered.pop(bisect_left(ordered, old))
    return out


def two_turn(x, side):
    d = np.asarray(x)-lag(x)
    return ((side*d > 0) & (side*lag(d) > 0) &
            (side*lag(d, 2) < 0) & (side*lag(d, 3) < 0))


def features(bars):
    a = np.asarray(bars, float)
    f = calculate(a)
    f['pece_slope'] = f['minnows']-lag(f['minnows'])
    d = f['adx_slope']
    f['adx_curve'] = abs((d+lag(d)-lag(d, 2)-lag(d, 3))/2)
    f['ao_intensity'] = abs(f['ao']-lag(f['ao'], 2))/a[:, 4]
    f['ao_level_normalized'] = abs(f['ao'])/a[:, 4]
    f['ao_slope_normalized'] = f['ao_slope']/a[:, 4]
    f['pece_intensity'] = abs(f['minnows']-lag(f['minnows'], 2))
    for name in ('adx', 'adx_curve', 'ao_intensity', 'pece_intensity'):
        f[name+'_rank'] = prior_rank(f[name])
    f['vol_rank'] = prior_rank(f['atr']/a[:, 4])
    f['regime4h'] = regime(a)
    # Daily close/SMA200, aligned only after all24 hourly candles close.
    daily, times = [], []
    for i in range(0, len(a)-23):
        if a[i, 0] % (24*HOUR) == 0 and np.array_equal(a[i:i+24, 0], a[i, 0]+np.arange(24)*HOUR):
            daily.append(a[i+23, 4]); times.append(a[i, 0]+24*HOUR)
    r = np.full(len(a), np.nan)
    if len(daily) >= 200:
        ds = np.asarray(daily)
        means = np.full(len(ds), np.nan)
        means[199:] = np.lib.stride_tricks.sliding_window_view(ds, 200).mean(axis=1)
        ix = np.searchsorted(times, a[:, 0]+HOUR, side='right')-1
        ok = ix >= 0
        r[ok] = np.sign(ds-means)[ix[ok]]
    f['regime1d'] = r
    return f


def detect(bars, f=None):
    """One consumed bundle per episode; intensity never chooses a new entry."""
    a = np.asarray(bars, float)
    if a.ndim != 2 or a.shape[1] != 6 or (np.diff(a[:, 0]) <= 0).any():
        raise ValueError('ORDERED_UNIQUE_H1_REQUIRED')
    f = features(a) if f is None else f
    ao, pece, adx = f['ao'], f['minnows'], f['adx']
    turns = {('ao', side): two_turn(ao, side) for side in (1, -1)}
    turns.update({('pece', side): two_turn(pece, side) for side in (1, -1)})
    peak, trough = two_turn(adx, -1), two_turn(adx, 1)
    pending = {(p, side): {} for p in PATTERNS for side in (1, -1)}
    last = {k: -1000 for k in pending}
    episodes, audit = [], []
    valid_run = 0
    for i in range(len(a)):
        finite = np.isfinite(a[i]).all() and all(np.isfinite(f[k][i]) for k in
                     ('ao', 'minnows', 'adx', 'plus_di', 'minus_di', 'atr'))
        candle = finite and min(a[i, 1:5]) > 0 and a[i, 2] >= max(a[i, 1], a[i, 3], a[i, 4]) and a[i, 3] <= min(a[i, 1], a[i, 4])
        if not candle or (i and a[i, 0]-a[i-1, 0] != HOUR):
            for k, tokens in pending.items():
                if tokens:
                    audit.append(dict(i=i, pattern=k[0], side=k[1], status='DATA_INVALIDATED'))
                tokens.clear()
            valid_run = 0
            continue
        valid_run += 1
        if valid_run < 5:
            continue
        for key, tokens in pending.items():
            p, side = key
            pece_ok = side*(pece[i]-pece[i-1]) > 0
            ao_ok = side*(ao[i]-ao[i-1]) > 0
            if p == PATTERNS[0]:
                ao_ok &= side*ao[i] < 0
                adx_ok = adx[i] < adx[i-1]
                ao_event = turns['ao', side][i] and np.all(side*ao[i-3:i+1] < 0)
                adx_event = peak[i]
            elif p == PATTERNS[1]:
                adx_ok = adx[i] > adx[i-1]
                adx_ok &= (f['plus_di'][i] > f['minus_di'][i] if side == 1 else f['minus_di'][i] > f['plus_di'][i])
                ao_event, adx_event = turns['ao', side][i], trough[i]
            else:
                ao_ok &= side*ao[i] > 0
                ao_event = turns['ao', side][i] and np.all(side*ao[i-4:i+1] > 0)
                adx_ok, adx_event = True, False
            if tokens and i-min(t['i'] for t in tokens.values()) > 2:
                audit.append(dict(i=i, pattern=p, side=side, status='EXPIRED')); tokens.clear()
            if tokens and not (pece_ok and ao_ok and adx_ok):
                audit.append(dict(i=i, pattern=p, side=side, status='ALIGNMENT_INVALIDATED')); tokens.clear()
            # An event is a two-before/two-after turn, never a persistent state.
            if ao_event:
                tokens['ao'] = dict(i=i, rank=float(f['ao_intensity_rank'][i]))
            if turns['pece', side][i]:
                tokens['pece'] = dict(i=i, rank=float(f['pece_intensity_rank'][i]))
            if adx_event:
                level = f['adx_rank'][i-2]
                tail = level if p == PATTERNS[0] else 1-level
                tokens['adx'] = dict(i=i, rank=float(min(tail, f['adx_curve_rank'][i]))
                                     if np.isfinite([tail, f['adx_curve_rank'][i]]).all() else float('nan'))
            needed = {'ao', 'pece'} if p == PATTERNS[2] else {'ao', 'pece', 'adx'}
            if needed.issubset(tokens) and pece_ok and ao_ok and adx_ok:
                values = [tokens[n]['rank'] for n in needed]
                score = min(values) if np.isfinite(values).all() else np.nan
                state = 'COOLDOWN' if i-last[key] < 25 else 'EPISODE'
                audit.append(dict(i=i, pattern=p, side=side, status=state))
                if state == 'EPISODE':
                    last[key] = i
                    row = dict(i=i, pattern=p, side=side, available_at=int(a[i, 0]+HOUR),
                               event_id=f'{p}:{side}:{int(a[i,0]+HOUR)}', intensity=score,
                               ao=float(ao[i]), ao_normalized=float(f['ao_level_normalized'][i]),
                               ao_slope_normalized=float(f['ao_slope_normalized'][i]),
                               adx=float(adx[i]), adx_curve=float(f['adx_curve'][i]),
                               pececillos=float(pece[i]), pece_turn=float(f['pece_intensity'][i]),
                               bbwp=float(f['bbwp'][i]), tokens={n:t['i'] for n,t in tokens.items()},
                               four_h=f['regime4h'][i], daily=f['regime1d'][i])
                    row['strata'] = [s for s,q in STRATA.items() if q == 0 or (np.isfinite(score) and score >= q)]
                    episodes.append(row)
                tokens.clear()
    return episodes, audit
