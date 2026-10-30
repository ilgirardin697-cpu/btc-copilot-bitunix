"""Causal experimental impulse/exhaustion context; never an order decision."""
from .core import ao_series, adx_series, bbwp_series

PROTOCOL = 'IGOD_DAILY_CYCLE_V1_HYPOTHESIS'
FALLING_DAYS = 3  # Declared before new outcome evaluation; never searched.


def cycle_series(rows):
    ao, adx, bbwp = ao_series(rows), adx_series(rows), bbwp_series(rows)
    result, down_run, last_impulse, exhausted = [], 0, None, False
    resistance = support = None
    for i, row in enumerate(rows):
        if i >= 4:
            window = rows[i-4:i+1]
            pivot = window[2]
            if pivot['h'] == max(x['h'] for x in window) and sum(x['h'] == pivot['h'] for x in window) == 1:
                resistance = pivot['h']
            if pivot['l'] == min(x['l'] for x in window) and sum(x['l'] == pivot['l'] for x in window) == 1:
                support = pivot['l']
        if i < 2 or any(x is None for x in (ao[i], ao[i-1], adx[i], adx[i-1], adx[i-2], bbwp[i][0], bbwp[i-1][0])):
            result.append(None)
            continue
        slope = ao[i] - ao[i-1]
        strength = adx[i]['adx'] - adx[i-1]['adx']
        prior_strength = adx[i-1]['adx'] - adx[i-2]['adx']
        volatility = bbwp[i][0] - bbwp[i-1][0]
        side = 1 if adx[i]['plus_di'] > adx[i]['minus_di'] else -1 if adx[i]['minus_di'] > adx[i]['plus_di'] else 0
        breaks = 1 if resistance is not None and row['c'] > resistance else -1 if support is not None and row['c'] < support else 0
        turn_up = strength > 0 and prior_strength <= 0 and down_run >= FALLING_DAYS
        turn_down = strength < 0 and prior_strength >= 0
        aligned = side != 0 and side * slope > 0 and volatility > 0
        rebound = bool(last_impulse and last_impulse * slope < 0 and strength < 0)
        reversal = bool(exhausted and last_impulse and side == -last_impulse and breaks == side and side * slope > 0)
        if reversal:
            phase = 'POSIBLE REVERSIÓN'
        elif turn_down or (exhausted and strength < 0):
            phase = 'AGOTAMIENTO'
            exhausted = True
        elif turn_up and aligned and breaks == side:
            phase = 'POSIBLE INICIO'
            last_impulse, exhausted = side, False
        elif strength > 0 and aligned:
            phase = 'ACELERACIÓN'
            last_impulse, exhausted = side, False
        else:
            phase = 'COMPRESIÓN' if bbwp[i][0] <= 20 and volatility <= 0 else 'INDETERMINADO'
        result.append(dict(protocol=PROTOCOL, phase=phase, available_at=row['close_ts'],
                           ao=ao[i], ao_slope=slope, ao_sign='ABOVE ZERO' if ao[i] > 0 else 'BELOW ZERO' if ao[i] < 0 else 'ZERO',
                           ao_color='GREEN' if slope > 0 else 'RED' if slope < 0 else 'FLAT',
                           adx=adx[i]['adx'], adx_slope=strength, prior_adx_slope=prior_strength,
                           prior_nonrising_days=down_run, adx_turn_up=turn_up, adx_turn_down=turn_down,
                           plus_di=adx[i]['plus_di'], minus_di=adx[i]['minus_di'],
                           pressure='LONG' if side == 1 else 'SHORT' if side == -1 else 'UNKNOWN',
                           bbwp=bbwp[i][0], bbwp_previous=bbwp[i-1][0], bbwp_slope=volatility,
                           volatility_compressed=bbwp[i][0] <= 20 and volatility <= 0,
                           structural_break='UP' if breaks == 1 else 'DOWN' if breaks == -1 else 'NONE',
                           confirmed_support=support, confirmed_resistance=resistance,
                           countertrend_rebound=rebound and not reversal,
                           reversal_price_confirmation=reversal,
                           interpretation='HYPOTHESIS — NOT VALIDATED'))
        down_run = down_run + 1 if strength <= 0 else 0
    return result
