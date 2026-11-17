"""Causal, offline slope timing; subsequent price descriptions never feed events."""
from pathlib import Path
import hashlib
import numpy as np
from research.confluence_1h.indicators import calculate, roll, bbwp

HERE = Path(__file__).resolve().parent
H = 3600000
SERIES = ('ao', 'adx', 'pececillos', 'bbwp_7_100', 'bbwp_13_252')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def features(bars):
    f = calculate(bars)
    width = 2 * roll(bars[:, 4], 13, 'std') / roll(bars[:, 4], 13)
    return dict(ao=f['ao'], adx=f['adx'], pececillos=f['minnows'],
                bbwp_7_100=f['bbwp'], bbwp_13_252=bbwp(width, 252, 13),
                plus_di=f['plus_di'], minus_di=f['minus_di'], atr=f['atr'],
                tendencia=f['kon_trend'], roja=f['kon_signal'], tiburones=f['sharks'])


def detect(times, values, name):
    """Only known closes. Separate immutable starts/resolutions, no backdating."""
    x = np.asarray(values, float)
    times = np.asarray(times, dtype=np.int64)
    if len(x) != len(times) or (len(times) > 1 and np.any(np.diff(times) <= 0)):
        raise ValueError('TIME_ORDER_OR_LENGTH')
    alerts, turns, resolutions, hourly = [], [], [], []
    pending = None
    leg_sign, leg_start, was_decelerating = 0, 0, False
    for i, value in enumerate(x):
        finite_pair = i >= 1 and times[i] - times[i-1] == H and np.isfinite(x[i-1:i+1]).all()
        d = float(x[i]-x[i-1]) if finite_pair else np.nan
        valid = i >= 2 and finite_pair and times[i-1]-times[i-2] == H and np.isfinite(x[i-2:i+1]).all()
        prev = float(x[i-1]-x[i-2]) if valid else np.nan
        acceleration = d-prev if valid else np.nan
        sign = int(np.sign(d)) if np.isfinite(d) else 0
        turn = bool(valid and d*prev < 0)
        decelerating = bool(valid and d*prev > 0 and abs(d) < abs(prev))
        associated = None
        if pending is not None:
            age = (int(times[i])-pending['available_at'])//H
            reason = None
            if not valid:
                reason = 'INVALID_DATA'
            elif turn and sign == pending['expected_slope'] and 0 < age <= 2:
                reason = 'CONFIRMED'
                associated = pending['alert_id']
            elif d == 0:
                reason = 'INVALID_FLAT'
            elif sign == -pending['expected_slope'] and abs(d) >= abs(prev):
                reason = 'INVALID_REACCELERATION'
            elif age >= 2:
                reason = 'EXPIRED_2H'
            if reason is not None:
                resolutions.append(dict(alert_id=pending['alert_id'], status=reason,
                                        resolution_i=i, resolved_at=int(times[i]), hours=age))
                pending = None
        if not finite_pair or sign == 0:
            leg_sign, leg_start = 0, i
        elif sign != leg_sign:
            leg_sign, leg_start = sign, i-1
        if turn:
            turns.append(dict(turn_id=f'{name}:TURN:{int(times[i])}', series=name, i=i,
                              available_at=int(times[i]), slope_direction=sign,
                              value=float(value), slope=d, acceleration=acceleration,
                              prior_alert_id=associated))
        new = None
        if decelerating and not was_decelerating and pending is None:
            new = dict(alert_id=f'{name}:PRE:{int(times[i])}', series=name, i=i,
                       available_at=int(times[i]), expected_slope=-sign,
                       value=float(value), slope=d, acceleration=acceleration,
                       known_leg_start_i=leg_start)
            alerts.append(new)
            pending = new
        state = 'UNKNOWN' if not valid else 'FLAT' if sign == 0 else (
            'TURN_' if turn else 'DECELERATING_' if decelerating else 'CONTINUING_') + ('UP' if sign > 0 else 'DOWN')
        hourly.append(dict(i=i, available_at=int(times[i]), value=float(value), slope=d,
                           acceleration=acceleration, state=state, is_prealert=new is not None,
                           is_turn=turn, pending_id=None if pending is None else pending['alert_id']))
        was_decelerating = decelerating
    return dict(alerts=alerts, turns=turns, resolutions=resolutions, hourly=hourly)


def price_description(bars, alert, resolution):
    """Diagnostic distances, not entries/returns. Same frozen anchor/horizon."""
    p = alert['i']
    c = resolution.get('resolution_i') if resolution.get('status') == 'CONFIRMED' else None
    end = p+4
    complete = end < len(bars) and np.array_equal(bars[p:end+1, 0], bars[p, 0]+np.arange(5)*H)
    out = dict(price_horizon_complete=bool(complete), next_open_prealert_reference=float(bars[p+1, 1]) if p+1 < len(bars) and bars[p+1, 0] == bars[p, 0]+H else None,
               next_open_confirm_reference=float(bars[c+1, 1]) if c is not None and c+1 < len(bars) and bars[c+1, 0] == bars[c, 0]+H else None)
    for side, label in [(1, 'up'), (-1, 'down')]:
        prior = bars[alert['known_leg_start_i']:p+1]
        anchor = float(prior[:, 3].min() if side == 1 else prior[:, 2].max())
        def distance(price):
            return side*(float(price)-anchor)/anchor*100
        out[label+'_known_anchor'] = anchor
        out[label+'_consumed_pre_pct'] = distance(bars[p, 4])
        out[label+'_consumed_confirm_pct'] = None if c is None else distance(bars[c, 4])
        out[label+'_close_drift_pre_confirm_pct'] = None if c is None else side*(bars[c, 4]/bars[p, 4]-1)*100
        for k in ('remaining_pre_pct', 'remaining_confirm_pct', 'consumed_share_pre', 'consumed_share_confirm'):
            out[label+'_'+k] = None
        if not complete:
            continue
        all_prices = bars[p+1:end+1, 2 if side == 1 else 3]
        target = float(all_prices.max() if side == 1 else all_prices.min())
        total = distance(target)
        out[label+'_remaining_pre_pct'] = side*(target/bars[p, 4]-1)*100
        out[label+'_consumed_share_pre'] = distance(bars[p, 4])/total if total > 0 else None
        if c is not None and c < end:
            later = bars[c+1:end+1, 2 if side == 1 else 3]
            target_c = float(later.max() if side == 1 else later.min())
            out[label+'_remaining_confirm_pct'] = side*(target_c/bars[c, 4]-1)*100
            out[label+'_consumed_share_confirm'] = distance(bars[c, 4])/total if total > 0 else None
    return out


def episodes(bars, detection):
    lookup = {r['alert_id']: r for r in detection['resolutions']}
    rows = []
    for a in detection['alerts']:
        r = lookup.get(a['alert_id'], dict(status='CENSORED_END_OF_FILE', resolution_i=None,
                                           resolved_at=None, hours=None))
        rows.append(dict(**a, **{k:v for k,v in r.items() if k != 'alert_id'},
                         **price_description(bars, a, r)))
    return rows


def confirmation_stability(values, times, turn):
    i, side = turn['i'], turn['slope_direction']
    end = i+2
    if end >= len(values) or np.any(np.diff(times[i:end+1]) != H) or not np.isfinite(values[i:end+1]).all():
        return dict(stability='CENSORED', unstable_after_hours=None)
    for j in range(i+1, end+1):
        if side*(values[j]-values[j-1]) <= 0:
            return dict(stability='FLAT_OR_REVERSED_WITHIN_2H', unstable_after_hours=j-i)
    return dict(stability='SAME_SLOPE_THROUGH_2H', unstable_after_hours=None)
