"""Offline weekly sequential oscillator/volatility proxy experiment. No authority."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from bitman_manual.frozen.indicators import calculate, lag
from research.bitman_state_data import WEEK, MONDAY, CUTOFF

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'research/results/bitman_weekly_state_machine'
SIGNALS = ('REACCELERATION_UP', 'REACCELERATION_DOWN',
           'ZERO_CROSS_UP_EXPANSION', 'ZERO_CROSS_DOWN_EXPANSION')
STATES = ('IMPULSE_UP', 'PULLBACK_UP', 'IMPULSE_DOWN', 'PULLBACK_DOWN',
          *SIGNALS, 'OTHER', 'UNKNOWN')
RANGES = (4, 2, 8)
HORIZONS = (1, 2, 3, 4)
PCTS = (5, 10, 15, 20)
ATRS = (1, 1.5, 2)
INPUT_HASHES = {
    'weekly_bars.csv': '1f542daea1af9fe43a83994d0dc4f282bd770f54b0c00de99258e2c8db9cbdc6',
    'input_features.csv': '2dc954d530520007f74f2f1510d3a151e614f218ae42c11e3bd0917e82b99b44',
    'data_manifest.json': '30d81220e377d022badcdaf005db30116741998265a5dbbcdd93af249f5c486e',
}


def iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)/1000, timezone.utc).isoformat()


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def load_inputs(directory=DEST):
    """Verify reused public snapshot, recompute frozen math, audit regime alignment."""
    directory = Path(directory)
    for name, expected in INPUT_HASHES.items():
        if checksum(directory/name) != expected:
            raise ValueError('REUSED_INPUT_HASH_MISMATCH:' + name)
    manifest = json.loads((directory/'data_manifest.json').read_text('utf-8'))
    if (manifest['venue'], manifest['symbol'], manifest['cutoff']) != ('BINANCE_USDM_PERPETUAL', 'BTCUSDT', CUTOFF):
        raise ValueError('SOURCE_MISMATCH')
    with (directory/'weekly_bars.csv').open(newline='', encoding='utf-8') as stream:
        frame = np.asarray([[float(row[k]) for k in ('open_time', 'open', 'high', 'low', 'close',
                                                   'base_volume', 'taker_buy_base_volume')]
                            for row in csv.DictReader(stream)])
    if len(frame) != manifest['weeks'] or np.any(np.diff(frame[:, 0]) != WEEK):
        raise ValueError('WEEKLY_GAP')
    if np.any((frame[:, 0]-MONDAY) % WEEK) or np.any(frame[:, 0]+WEEK > CUTOFF):
        raise ValueError('OPEN_OR_MISALIGNED_WEEK')
    if not np.all(np.isfinite(frame)) or np.any(frame[:, 1:5] <= 0):
        raise ValueError('BAD_MARKET_VALUE')
    if (np.any(frame[:, 2] < np.maximum(frame[:, 1], frame[:, 4])) or
        np.any(frame[:, 3] > np.minimum(frame[:, 1], frame[:, 4])) or
        np.any(frame[:, 6] < 0) or np.any(frame[:, 5] < frame[:, 6])):
        raise ValueError('BAD_OHLCV')
    f = features(frame)
    with (directory/'input_features.csv').open(newline='', encoding='utf-8') as stream:
        source = list(csv.DictReader(stream))
    if len(source) != len(frame):
        raise ValueError('INPUT_FEATURE_LENGTH')
    for name in ('ao', 'ao_slope', 'bbwp', 'bbwp_slope', 'adx', 'adx_slope', 'di_plus', 'di_minus'):
        reference = np.asarray([float(r[name]) if r[name] else np.nan for r in source])
        if not np.allclose(f[name], reference, rtol=0, atol=1e-10, equal_nan=True):
            raise ValueError('FROZEN_FORMULA_MISMATCH:' + name)
        if name.endswith('slope') and not np.array_equal(np.sign(f[name]), np.sign(reference), equal_nan=True):
            raise ValueError('SLOPE_SIGN_MISMATCH')
    f['regime'] = np.asarray([r['regime'] for r in source])
    for i, r in enumerate(source):
        if float(r['regime_available_at']) != f['available_at'][i]:
            raise ValueError('REGIME_LOOKAHEAD')
        close, sma = float(r['regime_4h_close']), float(r['regime_sma200'] or 'nan')
        expected = 'UNKNOWN' if not np.isfinite(sma) else 'BULL' if close > sma else 'BEAR' if close < sma else 'FLAT'
        if f['regime'][i] != expected:
            raise ValueError('REGIME_MISMATCH')
    return f


def features(frame):
    f = calculate(frame)
    f['frame'] = np.asarray(frame, float).copy()
    f['available_at'] = f['frame'][:, 0] + WEEK
    f['prior_ao'] = lag(f['ao'])
    f['prior_ao_slope'] = lag(f['ao_slope'])
    f['prior_vol_slope'] = lag(f['bbwp_slope'])
    f['prior_bbwp'] = lag(f['bbwp'])
    f['valid'] = np.logical_and.reduce([np.isfinite(f[k]) for k in
        ('ao', 'ao_slope', 'prior_ao', 'prior_ao_slope', 'bbwp', 'bbwp_slope', 'prior_vol_slope', 'atr')]) & (f['atr'] > 0)
    f['color'] = np.where(f['ao_slope'] > 0, 'GREEN', np.where(f['ao_slope'] < 0, 'RED', 'FLAT'))
    f['sign'] = np.where(f['ao'] > 0, 'ABOVE', np.where(f['ao'] < 0, 'BELOW', 'ZERO'))
    f['vol'] = np.where(f['bbwp_slope'] > 0, 'ACTIVE_RISING', np.where(f['bbwp_slope'] < 0, 'COOLING', 'FLAT'))
    f['vol'][~np.isfinite(f['bbwp_slope'])] = 'UNKNOWN'
    run, prior_run = 0, []
    for slope in f['bbwp_slope']:
        prior_run.append(run)
        run = run+1 if np.isfinite(slope) and slope <= 0 else 0
    f['prior_nonrising'] = np.asarray(prior_run)
    f['turn'] = (f['bbwp_slope'] > 0) & (f['prior_vol_slope'] <= 0) & f['valid']
    f['sustained_turn'] = f['turn'] & (f['prior_nonrising'] >= 2)
    years = np.asarray([datetime.fromtimestamp(t/1000, timezone.utc).year for t in f['available_at']])
    f['era'] = np.where(years <= 2022, '2020-2022', np.where(years <= 2024, '2023-2024', '2025-2026'))
    f['regime'] = np.asarray(['UNKNOWN']*len(frame))
    state, duration = classify(f)
    f['state'], f['pullback_weeks'] = state, duration
    f['signal'] = np.isin(state, SIGNALS)
    f['side'] = np.where(np.isin(state, (SIGNALS[0], SIGNALS[2])), 1,
                         np.where(np.isin(state, (SIGNALS[1], SIGNALS[3])), -1, 0))
    return f


def classify(f):
    """Single forward pass; only current/previous fully closed observations."""
    n = len(f['ao'])
    states, durations = np.full(n, 'UNKNOWN', dtype='U40'), np.zeros(n, int)
    up_run = down_run = 0
    for i in range(n):
        if not f['valid'][i]:
            up_run = down_run = 0
            continue
        a, color, slope = f['ao'][i], f['color'][i], f['bbwp_slope'][i]
        state = 'OTHER'
        if a > 0 and color == 'GREEN' and slope > 0:
            state = 'REACCELERATION_UP' if up_run else 'IMPULSE_UP'
            if up_run:
                durations[i] = up_run
        elif a < 0 and color == 'RED' and slope > 0:
            state = 'REACCELERATION_DOWN' if down_run else 'IMPULSE_DOWN'
            if down_run:
                durations[i] = down_run
        elif a > 0 and color == 'RED' and slope <= 0:
            state = 'PULLBACK_UP'
        elif a < 0 and color == 'GREEN' and slope <= 0:
            state = 'PULLBACK_DOWN'
        if not state.startswith('REACCELERATION'):
            previous = f['ao'][i-1] if i and f['valid'][i-1] else np.nan
            if slope > 0 and previous < 0 < a:
                state = 'ZERO_CROSS_UP_EXPANSION'
                durations[i] = down_run
            elif slope > 0 and previous > 0 > a:
                state = 'ZERO_CROSS_DOWN_EXPANSION'
                durations[i] = up_run
        states[i] = state
        up_run = up_run+1 if state == 'PULLBACK_UP' else 0
        down_run = down_run+1 if state == 'PULLBACK_DOWN' else 0
    return states, durations


def causal_range(frame, i, length):
    if i+1 < length:
        return np.nan, np.nan
    past = frame[i-length+1:i+1]
    return float(np.max(past[:, 2])), float(np.min(past[:, 3]))


def sequence(f, start, end):
    return [dict(open_time=int(f['frame'][j, 0]), available_at=iso(f['available_at'][j]),
                 state=str(f['state'][j]), sign=str(f['sign'][j]), color=str(f['color'][j]),
                 oscillator=float(f['ao'][j]), oscillator_slope=float(f['ao_slope'][j]),
                 volatility=float(f['bbwp'][j]), volatility_slope=float(f['bbwp_slope'][j]))
            for j in range(start, end+1)]


def episodes(f):
    result = []
    for i in np.flatnonzero(f['signal']):
        duration = int(f['pullback_weeks'][i])
        start = i-duration if duration else i-1
        prior = start-1
        same_impulse = 'IMPULSE_UP' if f['side'][i] == 1 else 'IMPULSE_DOWN'
        earlier = np.flatnonzero(f['state'][:start] == same_impulse)
        high, low = causal_range(f['frame'], i, 4)
        result.append(dict(episode_id='W'+str(int(f['frame'][i, 0])), index=int(i),
            start_at=iso(f['available_at'][start]), end_at=iso(f['available_at'][i]),
            signal_open=iso(f['frame'][i, 0]), state=str(f['state'][i]), side=int(f['side'][i]),
            pullback_weeks=duration, preceding_state=str(f['state'][prior]) if prior >= 0 else 'UNKNOWN',
            immediate_prior_impulse=bool(prior >= 0 and f['state'][prior] == same_impulse),
            last_same_side_impulse_at=iso(f['available_at'][earlier[-1]]) if len(earlier) else None,
            turn_up=bool(f['turn'][i]), sustained_turn=bool(f['sustained_turn'][i]),
            era=str(f['era'][i]), regime=str(f['regime'][i]),
            range_high=high, range_low=low, range_width_atr=(high-low)/f['atr'][i],
            sequence=sequence(f, start, i)))
    return result


def descriptive_runs(f):
    result, start = [], None
    for i in range(len(f['state'])+1):
        if start is not None and (i == len(f['state']) or f['state'][i] != f['state'][start]):
            result.append(dict(state=str(f['state'][start]), start_index=start, end_index=i-1,
                               start_at=iso(f['available_at'][start]), end_at=iso(f['available_at'][i-1]),
                               weeks=i-start, unresolved=bool(i == len(f['state']) and
                                   str(f['state'][start]).startswith('PULLBACK'))))
            start = None
        if i < len(f['state']) and start is None and f['valid'][i]:
            start = i
    return result


def outcomes(f, length, horizon):
    """Frozen-range forward measurements; incomplete horizons remain missing."""
    frame, n = f['frame'], len(f['frame'])
    keys = ('forward', 'absolute', 'up', 'down', 'max_move', 'max_atr', 'breakout', 'wick_breakout',
            'first_side', 'first_week', 'wick_side', 'beyond_up', 'beyond_down', 'beyond_atr',
            'reentered', 'end_outside', 'sustained', 'persistence_followup', 'range_atr', 'congestion',
            *('large_'+str(p) for p in PCTS), *('move_'+str(p) for p in PCTS),
            *('atr_'+str(t) for t in ATRS))
    out = {k: np.full(n, np.nan) for k in keys}
    for i in range(length-1, n-horizon):
        if not f['valid'][i]:
            continue
        anchor, atr = frame[i, 4], f['atr'][i]
        high, low = causal_range(frame, i, length)
        future = frame[i+1:i+horizon+1]
        up, down = max(0., float(np.max(future[:, 2])-anchor)), max(0., float(anchor-np.min(future[:, 3])))
        maximum = max(up, down)
        close_up, close_down = future[:, 4] > high, future[:, 4] < low
        broke = np.flatnonzero(close_up | close_down)
        touched_up, touched_down = future[:, 2] > high, future[:, 3] < low
        wick = np.flatnonzero(touched_up | touched_down)
        first = int(broke[0]) if len(broke) else None
        side = (1 if close_up[first] else -1) if first is not None else 0
        wick_side = 0 if not len(wick) else (2 if touched_up[wick[0]] and touched_down[wick[0]] else
                                             1 if touched_up[wick[0]] else -1)
        reentered = bool(np.any(future[first+1:, 4] <= high) if side == 1 else
                         np.any(future[first+1:, 4] >= low)) if side else False
        followup = horizon-first-1 if first is not None else 0
        values = dict(forward=100*(future[-1, 4]/anchor-1), absolute=100*abs(future[-1, 4]/anchor-1),
            up=100*up/anchor, down=100*down/anchor, max_move=100*maximum/anchor, max_atr=maximum/atr,
            breakout=float(bool(len(broke))), wick_breakout=float(bool(len(wick))), first_side=side,
            first_week=first+1 if first is not None else np.nan, wick_side=wick_side,
            beyond_up=100*max(0.,np.max(future[:, 2])-high)/anchor,
            beyond_down=100*max(0.,low-np.min(future[:, 3]))/anchor,
            beyond_atr=max(0.,np.max(future[:, 2])-high, low-np.min(future[:, 3]))/atr,
            reentered=float(reentered) if side else np.nan,
            end_outside=float(future[-1,4] > high if side == 1 else future[-1,4] < low) if side else np.nan,
            sustained=float(not reentered) if side and followup else np.nan,
            persistence_followup=followup, range_atr=(high-low)/atr, congestion=float(high-low <= 2*atr))
        for p in PCTS:
            values['move_'+str(p)] = float(100*maximum/anchor >= p)
            values['large_'+str(p)] = float((np.any(close_up) and 100*up/anchor >= p) or
                                           (np.any(close_down) and 100*down/anchor >= p))
        for t in ATRS:
            values['atr_'+str(t)] = float(maximum/atr >= t)
        for name, value in values.items():
            out[name][i] = value
    return out


def nonoverlap(mask, gap=4):
    result, previous = np.zeros(len(mask), bool), -gap-1
    for i in np.flatnonzero(mask):
        if i-previous > gap:
            result[i], previous = True, i
    return result


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        Path(path).write_text('', encoding='utf-8')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, keys, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: '' if v is None or isinstance(v, (float, np.floating)) and not np.isfinite(v)
                             else v for k, v in row.items()})


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value
