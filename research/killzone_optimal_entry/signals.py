"""Predeclared deterministic price-only candidates. No outcomes are read here."""
import math
from .data import HOUR, MINUTE, window

METHODS = ('BASELINE', 'AFTER_LONDON', 'BREAKOUT', 'RETEST', 'LIMIT_ZONE')


def direction(o, c):
    return 1 if c > o else -1 if c < o else 0


def signal_for(method, c, closed_hours):
    if method not in METHODS:
        raise ValueError('UNKNOWN_METHOD')
    side = direction(c['l_open'], c['l_close'])
    base = dict(method=method, cycle=c['cycle'], status='NO_SIGNAL', side=0,
                signal_at=None, theoretical_entry=None, limit_price=None)
    if method in ('BASELINE', 'AFTER_LONDON', 'LIMIT_ZONE'):
        if side == 0:
            return base
        if method == 'AFTER_LONDON' and not (
            side == 1 and c['l_close'] > c['aHigh'] or
            side == -1 and c['l_close'] < c['aLow']
        ):
            return base
        limit = (c['lHigh'] + c['lLow']) / 2 if method == 'LIMIT_ZONE' else None
        return dict(base, status='SIGNAL', side=side, signal_at=c['freeze'],
                    theoretical_entry=c['l_close'] if limit is None else limit,
                    limit_price=limit, zone_low=min(limit, c['l_close']) if limit else None,
                    zone_high=max(limit, c['l_close']) if limit else None)

    first = None
    for bar in window(closed_hours, c['freeze'], c['expiry']):
        available = int(bar[0]) + HOUR
        # Do not use the open/current hour when called on an as-of prefix.
        if available > c['expiry']:
            continue
        o, high, low, close = bar[1:]
        if first is None:
            d = 1 if min(o, close) > c['highGuideValue'] else -1 if max(o, close) < c['lowGuideValue'] else 0
            if not d:
                continue
            first = dict(side=d, signal_at=available, theoretical_entry=float(close))
            if method == 'BREAKOUT':
                return dict(base, status='SIGNAL', **first)
        else:
            d = first['side']
            retest = (d == 1 and low <= c['highGuideValue'] and close > c['highGuideValue'] or
                      d == -1 and high >= c['lowGuideValue'] and close < c['lowGuideValue'])
            if retest:
                return dict(base, status='SIGNAL', side=d, signal_at=available,
                            theoretical_entry=float(close), breakout_at=first['signal_at'])
    if first is not None:
        return dict(base, status='RETEST_NOT_CONFIRMED', side=first['side'], breakout_at=first['signal_at'])
    return base


def stop_target(c, side):
    if side not in (-1, 1):
        raise ValueError('INVALID_SIDE')
    return ((c['lLow'] - .2 * c['atr14'], c['newTopTarget']) if side == 1 else
            (c['lHigh'] + .2 * c['atr14'], c['newBottomTarget']))


def net_terms(entry, stop, target, side, fee, slip):
    if (side not in (-1, 1) or not all(math.isfinite(x) for x in (entry, stop, target, fee, slip))
            or min(entry, stop, target) <= 0 or fee < 0 or not 0 <= slip < 1):
        return dict(valid=False, reason='INVALID_RISK_INPUT')
    if not side * (entry - stop) > 0:
        return dict(valid=False, reason='STOP_NOT_PROTECTIVE')
    if not side * (target - entry) > 0:
        return dict(valid=False, reason='TARGET_BEHIND_ENTRY')
    stop_fill = stop * (1 - side * slip)
    tp_fill = target * (1 - side * slip)
    risk = -side * (stop_fill - entry) + fee * (entry + stop_fill)
    reward = side * (tp_fill - entry) - fee * (entry + tp_fill)
    rr = reward / risk if risk > 0 else float('-inf')
    return dict(valid=rr >= 1.5, reason='ACCEPTABLE' if rr >= 1.5 else 'NET_RR_BELOW_1_5',
                risk_per_btc=risk, reward_per_btc=reward, net_rr=rr)
