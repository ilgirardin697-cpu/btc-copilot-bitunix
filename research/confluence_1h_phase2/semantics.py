"""Descriptive closed-bar events, never entries, recommendations or outcomes."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np
from research.confluence_1h.indicators import calculate, lag

HOUR = 3_600_000
SERIES = {'pececillos': 'minnows', 'tendencia': 'kon_trend',
          'tiburones': 'sharks', 'ma_trend': 'kon_signal'}


def iso(t):
    return datetime.fromtimestamp(int(t) / 1000, timezone.utc).isoformat().replace('+00:00', 'Z')


def timestamps(open_ms):
    """Earliest theoretical availability; actual reception remains unknown."""
    if type(open_ms) is not int or open_ms % HOUR:
        raise ValueError('H1_OPEN_REQUIRED')
    zone = ZoneInfo('Europe/Madrid')
    return dict(open_utc=iso(open_ms), close_utc=iso(open_ms + HOUR),
                earliest_available_at=iso(open_ms + HOUR),
                open_madrid=datetime.fromtimestamp(open_ms / 1000, zone).isoformat(),
                close_madrid=datetime.fromtimestamp((open_ms + HOUR) / 1000, zone).isoformat(),
                actual_received_at=None)


def validate_bars(bars):
    a = np.asarray(bars, float)
    if a.ndim != 2 or a.shape[1] != 6 or not len(a) or not np.isfinite(a).all():
        raise ValueError('FINITE_OHLCV_REQUIRED')
    t, o, h, l, c, v = a.T
    if (t % HOUR != 0).any() or (np.diff(t) != HOUR).any():
        raise ValueError('GAP_DUPLICATE_OR_ORDER')
    if (np.minimum.reduce([o, h, l, c]) <= 0).any() or (v < 0).any():
        raise ValueError('PRICE_VOLUME')
    if (h < np.maximum.reduce([o, c, l])).any() or (l > np.minimum.reduce([o, c, h])).any():
        raise ValueError('OHLC_ORDER')
    return a


def events(features):
    """Strict adjacent turns; flat plateaus separate; vertex t-1 known at close(t).

    No thresholds or entry rules. Undefined prior samples cannot emit crossings.
    """
    adx, ao = features['adx'], features['ao']
    ds, aos = adx - lag(adx), ao - lag(ao)
    prev_ds, prev_aos = lag(ds), lag(aos)
    out = dict(adx_turn_down=(prev_ds > 0) & (ds < 0),
               adx_turn_up=(prev_ds < 0) & (ds > 0), adx_flat=ds == 0,
               ao_negative_recovery_turn=(ao < 0) & (aos > 0) & (prev_aos <= 0),
               ao_negative_two_rising=(ao < 0) & (aos > 0) & (prev_aos > 0),
               ao_positive_deterioration_turn=(ao > 0) & (aos < 0) & (prev_aos >= 0),
               ao_positive_two_falling=(ao > 0) & (aos < 0) & (prev_aos < 0))
    for name in SERIES:
        x, red = features[SERIES[name]], features['kon_signal']
        slope = x - lag(x)
        out[name + '_slope_turn_up'] = (slope > 0) & (lag(slope) < 0)
        out[name + '_slope_turn_down'] = (slope < 0) & (lag(slope) > 0)
        out[name + '_slope_flat'] = slope == 0
        out[name + '_zero_cross_up'] = (x > 0) & (lag(x) <= 0)
        out[name + '_zero_cross_down'] = (x < 0) & (lag(x) >= 0)
        if name != 'ma_trend':
            out[name + '_cross_up'] = (x > red) & (lag(x) <= lag(red))
            out[name + '_cross_down'] = (x < red) & (lag(x) >= lag(red))
    return out


def descriptive_rows(bars):
    a = validate_bars(bars)
    f = calculate(a)
    ev = events(f)
    result, last = [], {}
    for i, bar in enumerate(a):
        row = dict(open_time_ms=int(bar[0]), **timestamps(int(bar[0])))
        for key in ('adx', 'adx_slope', 'plus_di', 'minus_di', 'ao', 'ao_slope', 'bbwp', 'atr', 'pvi_osc'):
            row[key] = float(f[key][i]) if np.isfinite(f[key][i]) else None
        for name, key in SERIES.items():
            row[name] = float(f[key][i]) if np.isfinite(f[key][i]) else None
            slope = f[key][i] - f[key][i-1] if i else np.nan
            row[name + '_slope'] = float(slope) if np.isfinite(slope) else None
        for key, values in ev.items():
            row[key] = bool(values[i])
            if values[i]:
                last[key] = i
            row[key + '_age_closed_bars'] = i - last[key] if key in last else None
        row['adx_vertex_open_utc'] = iso(int(a[i-1, 0])) if i and (ev['adx_turn_up'][i] or ev['adx_turn_down'][i]) else None
        result.append(row)
    return result
