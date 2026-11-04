"""Causal minute prefixes and independent post-London labels, never a trading simulator."""
from datetime import date, datetime, time, timedelta, timezone
import json
from zoneinfo import ZoneInfo
import numpy as np
from ..alpha_arcanox_pine_v37.core import project
from bitman_manual.frozen.indicators import calculate
from .data import CACHE, HOUR, MINUTE, HERE, protocol_hash

NY = ZoneInfo('America/New_York')
CLASSES = ['SUPERIOR_FIRST', 'INFERIOR_FIRST', 'NEITHER']
FEATURES = ['minute_fraction', 'position', 'london_return', 'london_width', 'asia_return',
            'combined_width_atr', 'ao_atr', 'ao_slope_atr', 'adx', 'adx_slope', 'di_balance',
            'bbwp', 'bbwp_slope', 'confirmed_4h_change']


def stamp(d, hour):
    return int(datetime.combine(d, time(hour), NY).timestamp()*1000)


def window(rows, begin, end):
    return rows[np.searchsorted(rows[:, 0], begin):np.searchsorted(rows[:, 0], end)]


def contiguous(rows, begin, end, step):
    return len(rows) == (end-begin)//step and np.array_equal(rows[:, 0], np.arange(begin, end, step))


def schedule(d):
    return dict(asia=stamp(d-timedelta(days=1), 20), asia_end=stamp(d, 0),
                london=stamp(d, 2), radar=stamp(d, 5), close=stamp(d, 6), end=stamp(d, 20))


def features(asia, london3, prefix, static, minute):
    if minute not in range(60) or len(asia) != 4 or len(london3) != 3 or len(prefix) != minute:
        raise ValueError('INCOMPLETE_FEATURE_PREFIX')
    ah, al = max(asia[:, 2]), min(asia[:, 3]); aw = ah-al
    if aw <= 0 or static[0] <= 0:
        raise ValueError('ZERO_RANGE_OR_ATR')
    lh, ll = max(london3[:, 2]), min(london3[:, 3]); price = london3[-1, 4]
    if minute:
        lh, ll = max(lh, max(prefix[:, 2])), min(ll, min(prefix[:, 3]))
        price = prefix[-1, 4]
    hi, lo = max(ah, lh), min(al, ll)
    atr, ao, aos, adx, adxs, dip, dim, bbwp, bbwps, h4 = static
    x = np.array([minute/60, (price-lo)/(hi-lo), (price-london3[0, 1])/aw,
                  (lh-ll)/aw, (asia[-1, 4]-asia[0, 1])/aw, (hi-lo)/atr,
                  ao/atr, aos/atr, adx/100, adxs/100, (dip-dim)/100,
                  bbwp/100, bbwps/100, h4/aw])
    if not np.isfinite(x).all():
        raise ValueError('FEATURE_UNAVAILABLE')
    return x


def label(rows, top, bottom):
    """No access to predictors. A first simultaneous touch cannot be ordered from 1m OHLC."""
    if not len(rows) or not top > bottom:
        raise ValueError('INVALID_LABEL_INPUT')
    up = np.flatnonzero(rows[:, 2] >= top); down = np.flatnonzero(rows[:, 3] <= bottom)
    u = int(up[0]) if len(up) else len(rows); d = int(down[0]) if len(down) else len(rows)
    if u == d == len(rows):
        return 2, None
    if u == d:
        return -1, int(rows[u, 0])
    return (0, int(rows[u, 0])) if u < d else (1, int(rows[d, 0]))


def indicators(h):
    keys = ['atr', 'ao', 'ao_slope', 'adx', 'adx_slope', 'di_plus', 'di_minus', 'bbwp', 'bbwp_slope']
    out = np.full((len(h), len(keys)), np.nan)
    cuts = np.r_[0, np.flatnonzero(np.diff(h[:, 0]) != HOUR)+1, len(h)]
    for left, right in zip(cuts[:-1], cuts[1:]):
        b = h[left:right]
        # Public OHLC formulas reused read-only. Volume is not used by the selected series.
        f = calculate(np.column_stack([b, np.ones(len(b)), b[:, 0]+HOUR-1]))
        out[left:right] = np.column_stack([f[k] for k in keys])
    return out


def build(h, m, first=date(2022, 1, 1), last=date(2026, 10, 31)):
    static_h = indicators(h)
    records, X, Y, days = [], [], [], []
    four = {}
    for t in h[:, 0].astype(np.int64):
        if t % (4*HOUR) == 0:
            b = window(h, t, t+4*HOUR)
            if contiguous(b, t, t+4*HOUR, HOUR):
                four[t+4*HOUR] = float(b[-1, 4])
    d = first
    while d <= last:
        s = schedule(d); row = dict(cycle=d.isoformat(), **s, status='INCOMPLETE', label=None)
        a = window(h, s['asia'], s['asia_end']); l = window(h, s['london'], s['close'])
        if s['close']-s['london'] != 4*HOUR:
            row['reason'] = 'DST_MISSING_02_LONDON_NOT_FOUR_H1'
        elif not contiguous(a, s['asia'], s['asia_end'], HOUR) or not contiguous(l, s['london'], s['close'], HOUR):
            row['reason'] = 'MISSING_SESSION_H1'
        else:
            live = window(m, s['radar'], s['close']); after = window(m, s['close'], s['end'])
            if not contiguous(live, s['radar'], s['close'], MINUTE) or not contiguous(after, s['close'], s['end'], MINUTE):
                row['reason'] = 'MISSING_INTRABAR_DO_NOT_IMPUTE'
            else:
                # Every intrabar hour used for labels/features must exactly agree with public H1.
                mm = np.concatenate([live, after]); agrees = True
                for start in range(0, len(mm), 60):
                    b = mm[start:start+60]; hh = window(h, b[0, 0], b[0, 0]+HOUR)
                    agg = np.array([b[0, 1], max(b[:, 2]), min(b[:, 3]), b[-1, 4]])
                    agrees &= len(hh) == 1 and np.array_equal(hh[0, 1:5], agg)
                if not agrees:
                    row['reason'] = 'H1_1M_OHLC_MISMATCH'
                else:
                    at = np.searchsorted(h[:, 0], s['radar'])-1
                    end4 = (s['radar']//(4*HOUR))*(4*HOUR)
                    change4 = four.get(end4, np.nan)-four.get(end4-4*HOUR, np.nan)
                    static = np.r_[static_h[at], change4]
                    levels = project(max(a[:, 2]), min(a[:, 3]), max(l[:, 2]), min(l[:, 3]))
                    top, bot = levels['newTopTarget'], levels['newBottomTarget']
                    outcome, touch = label(after, top, bot)
                    row.update(final_top=top, final_bottom=bot, first_touch_minute_open=touch)
                    try:
                        xx = np.array([features(a, l[:3], live[:minute], static, minute) for minute in range(60)])
                        row['status'] = 'AMBIGUOUS' if outcome == -1 else 'COMPLETE'
                        row['label'] = 'AMBIGUOUS' if outcome == -1 else CLASSES[outcome]
                        if outcome != -1:
                            X.append(xx); Y.append(outcome); days.append(d.isoformat())
                    except ValueError as exc:
                        row['reason'] = str(exc)
        records.append(row); d += timedelta(days=1)
    return np.array(X), np.array(Y), np.array(days), records


def main():
    h = np.load(CACHE/'1h.npy', mmap_mode='r'); m = np.load(CACHE/'1m.npy', mmap_mode='r')
    X, Y, days, records = build(h, m)
    np.savez_compressed(CACHE/'dataset.npz', X=X, Y=Y, days=days)
    (CACHE/'cycles.json').write_text(json.dumps(dict(protocol_hash=protocol_hash(), cycles=records), indent=2)+'\n')
    print(json.dumps(dict(cycles=len(records), usable=len(Y), prediction_rows=len(Y)*60,
                         incomplete=sum(r['status']=='INCOMPLETE' for r in records),
                         ambiguous=sum(r['status']=='AMBIGUOUS' for r in records))))


if __name__ == '__main__':
    main()
