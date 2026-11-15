"""Provisional event proximity ledger; no entry, fill, price target or order."""
import numpy as np
import hashlib
import json
from research.confluence_1h.indicators import calculate
from ..semantics import HOUR, SERIES, events

MAX_AGE = 2


def detect(bars, features=None):
    """Replay in order; cancelled/expired/consumed events cannot be resurrected.

    Two ADX contexts and three area channels are diagnostics, never independent
    trade opportunities. Persistent AO state contributes only its START event.
    """
    a = np.asarray(bars, float)
    if a.ndim != 2 or a.shape[1] != 6 or (np.diff(a[:, 0]) <= 0).any():
        raise ValueError('ORDERED_UNIQUE_OHLCV_REQUIRED')
    f = calculate(a) if features is None else features
    e = events(f)
    out = []
    channels = {(area, side, force): {} for area in ('pececillos','tendencia','tiburones')
                for side in ('UP','DOWN') for force in ('PEAK_DECELERATION','TROUGH_BUILDING')}
    valid_streak = 0
    previous_ao = {'UP': False, 'DOWN': False}
    def emit(kind, key, i, tokens, reason=None):
        area, side, force = key
        row = dict(record_type=kind, area=area, side_hypothesis=side, adx_context=force,
                   bar_open_ms=int(a[i, 0]), available_at=int(a[i, 0]+HOUR),
                   event_id=':'.join((kind,area,side,force,str(int(a[i, 0]+HOUR)))),
                   tokens=dict(tokens), reason=reason, trade_authority='NONE')
        row['evidence_mode'] = 'RETROSPECTIVE_DIAGNOSTIC_REPLAY_NOT_FORWARD'
        # An old bundle and a newly invalid bundle may be cancelled at one close.
        # Distinguish their identities without changing states/times/rules.
        identity = json.dumps(dict(tokens=tokens,reason=reason),sort_keys=True,separators=(',',':'))
        row['event_id'] += ':'+hashlib.sha256(identity.encode()).hexdigest()[:16]
        out.append(row)
    for i in range(len(a)):
        finite = np.isfinite(a[i]).all() and all(np.isfinite(f[k][i]) for k in ('minnows','kon_trend','kon_signal','sharks','ao','adx'))
        gap = i > 0 and a[i, 0]-a[i-1, 0] != HOUR
        if not finite or gap:
            for key, tokens in channels.items():
                if tokens:emit('INVALIDATED',key,i,tokens,'DATA_UNAVAILABLE_OR_GAP')
                tokens.clear()
            valid_streak = 0
            previous_ao = {'UP': False, 'DOWN': False}
            continue
        valid_streak += 1
        if valid_streak < 3:
            previous_ao = {'UP':bool(e['ao_negative_two_rising'][i]),'DOWN':bool(e['ao_positive_two_falling'][i])}
            continue
        ao = float(f['ao'][i]); aos = float(f['ao'][i]-f['ao'][i-1]); ads = float(f['adx'][i]-f['adx'][i-1])
        ao_state = {'UP':bool(e['ao_negative_two_rising'][i]), 'DOWN':bool(e['ao_positive_two_falling'][i])}
        for key, tokens in channels.items():
            area, side, force = key
            up = side == 'UP'; x = f[SERIES[area]][i]; red = f['kon_signal'][i]
            aligned = x > red if up else x < red
            recovering = ao < 0 and aos > 0 if up else ao > 0 and aos < 0
            force_ok = ads <= 0 if force == 'PEAK_DECELERATION' else ads >= 0
            if tokens and i-min(tokens.values()) > MAX_AGE:
                emit('EXPIRED',key,i,tokens,'OLDEST_EVENT_OLDER_THAN_2_CLOSES');tokens.clear()
            reason = None
            if 'area_cross' in tokens and not aligned:reason='AREA_ALIGNMENT_LOST'
            if ('ao_confirm' in tokens or 'area_cross' in tokens) and not recovering:reason='AO_SIGN_OR_RECOVERY_INVALID'
            if 'adx_turn' in tokens and not force_ok:reason='ADX_CONTEXT_REVERSED'
            if reason:
                emit('INVALIDATED',key,i,tokens,reason);tokens.clear()
            fresh = {}
            if e[area+'_cross_'+('up' if up else 'down')][i]:fresh['area_cross']=i
            if ao_state[side] and not previous_ao[side]:fresh['ao_confirm']=i
            if e['adx_turn_down' if force=='PEAK_DECELERATION' else 'adx_turn_up'][i]:fresh['adx_turn']=i
            tokens.update(fresh)
            if ('ao_confirm' in tokens or 'area_cross' in tokens) and not recovering:
                emit('INVALIDATED',key,i,tokens,'AO_SIGN_OR_RECOVERY_INVALID');tokens.clear();continue
            if fresh:emit('PENDING',key,i,tokens)
            if len(tokens)==3 and aligned and recovering and force_ok:
                emit('PROXIMITY_OBSERVED',key,i,tokens)
                tokens.clear()  # all three tokens consumed; no rolling replay signal
        previous_ao = ao_state
    return out
