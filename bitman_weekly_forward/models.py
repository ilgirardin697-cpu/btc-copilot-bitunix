"""Audited causal state rules from PR31 772446d; no research dependency."""
import numpy as np
from types import SimpleNamespace
LAGS=(0,1,2)
SIGNALS=('REACCELERATION_UP', 'REACCELERATION_DOWN', 'ZERO_CROSS_UP_EXPANSION', 'ZERO_CROSS_DOWN_EXPANSION')
def safe_sequence(f,a,b): return []
sm=SimpleNamespace(SIGNALS=SIGNALS,iso=lambda t:str(int(t)),sequence=safe_sequence)
def classify(f):
    """Single forward pass; only current/previous fully closed observations."""
    n = len(f['ao'])
    states, durations = (np.full(n, 'UNKNOWN', dtype='U40'), np.zeros(n, int))
    up_run = down_run = 0
    for i in range(n):
        if not f['valid'][i]:
            up_run = down_run = 0
            continue
        a, color, slope = (f['ao'][i], f['color'][i], f['bbwp_slope'][i])
        state = 'OTHER'
        if a > 0 and color == 'GREEN' and (slope > 0):
            state = 'REACCELERATION_UP' if up_run else 'IMPULSE_UP'
            if up_run:
                durations[i] = up_run
        elif a < 0 and color == 'RED' and (slope > 0):
            state = 'REACCELERATION_DOWN' if down_run else 'IMPULSE_DOWN'
            if down_run:
                durations[i] = down_run
        elif a > 0 and color == 'RED' and (slope <= 0):
            state = 'PULLBACK_UP'
        elif a < 0 and color == 'GREEN' and (slope <= 0):
            state = 'PULLBACK_DOWN'
        if not state.startswith('REACCELERATION'):
            previous = f['ao'][i - 1] if i and f['valid'][i - 1] else np.nan
            if slope > 0 and previous < 0 < a:
                state = 'ZERO_CROSS_UP_EXPANSION'
                durations[i] = down_run
            elif slope > 0 and previous > 0 > a:
                state = 'ZERO_CROSS_DOWN_EXPANSION'
                durations[i] = up_run
        states[i] = state
        up_run = up_run + 1 if state == 'PULLBACK_UP' else 0
        down_run = down_run + 1 if state == 'PULLBACK_DOWN' else 0
    return (states, durations)

def resolve(f, max_lag):
    """One chronological pass, no outcome access or retrospective matching."""
    if type(max_lag) is not int or max_lag not in LAGS:
        raise ValueError('ONLY_LAG_0_1_2_ALLOWED')
    n = len(f['ao'])
    states = np.full(n, 'UNKNOWN', dtype='U60')
    side = np.zeros(n, int)
    pending_log, audit, events = ([], [], [])
    pending = None
    up_run = down_run = 0

    def record(action, i, candidate, reason):
        audit.append(dict(action=action, index=int(i), activation_index=candidate['activation_index'], kind=candidate['kind'], reason=reason))
    for i in range(n):
        if not f['valid'][i]:
            if pending is not None:
                record('CANCELLED', i, pending, 'INVALID_WEEK')
            pending = None
            up_run = down_run = 0
            pending_log.append(None)
            continue
        ao, color, slope = (f['ao'][i], f['color'][i], f['bbwp_slope'][i])
        base = str(f['state'][i])
        states[i] = ('IMPULSE_UP' if ao > 0 else 'IMPULSE_DOWN') if base in sm.SIGNALS else base
        if pending is not None:
            aligned_color = 'GREEN' if pending['side'] == 1 else 'RED'
            reason = 'ZERO_OR_OPPOSITE_SIGN' if ao * pending['side'] <= 0 else 'NEW_CORRECTION' if pending['kind'].startswith('REACCELERATION') and color != aligned_color else 'DEADLINE_EXPIRED' if i - pending['activation_index'] > max_lag else None
            if reason:
                record('CANCELLED' if reason != 'DEADLINE_EXPIRED' else 'EXPIRED', i, pending, reason)
                pending = None
        previous = f['ao'][i - 1] if i and f['valid'][i - 1] else np.nan
        kind = None
        duration = 0
        if previous < 0 < ao:
            kind, direction, duration = ('ZERO_CROSS_UP_EXPANSION', 1, down_run)
        elif previous > 0 > ao:
            kind, direction, duration = ('ZERO_CROSS_DOWN_EXPANSION', -1, up_run)
        elif up_run and ao > 0 and (color == 'GREEN'):
            kind, direction, duration = ('REACCELERATION_UP', 1, up_run)
        elif down_run and ao < 0 and (color == 'RED'):
            kind, direction, duration = ('REACCELERATION_DOWN', -1, down_run)
        if kind:
            candidate = dict(kind=kind, side=direction, activation_index=int(i), pullback_weeks=int(duration), start_index=int(i - duration if duration else max(0, i - 1)))
            if pending is None:
                pending = candidate
                record('ACTIVATED', i, pending, 'OSCILLATOR_CHANGE_OBSERVED')
            else:
                record('IGNORED', i, candidate, 'EXISTING_SEQUENCE_OWNS_RESOLUTION')
        if pending is not None:
            age = i - pending['activation_index']
            if age == 0 and slope > 0 or (age > 0 and f['turn'][i]):
                episode = dict(pending, index=int(i), lag=int(age), episode_id='O' + str(int(f['frame'][pending['activation_index'], 0])) + '_' + pending['kind'], activation_at=sm.iso(f['available_at'][pending['activation_index']]), confirmed_at=sm.iso(f['available_at'][i]), resolution_color=str(color), sequence=sm.sequence(f, pending['start_index'], i))
                events.append(episode)
                states[i], side[i] = (pending['kind'], pending['side'])
                record('CONFIRMED', i, pending, 'IMMEDIATE_RISING' if age == 0 else 'DELAYED_TURN_UP')
                pending = None
            elif age >= max_lag:
                record('EXPIRED', i, pending, 'DEADLINE_WITHOUT_VOLATILITY_CONFIRMATION')
                pending = None
            else:
                states[i] = 'PENDING_' + pending['kind']
        pending_log.append(dict(pending) if pending is not None else None)
        up_run = up_run + 1 if ao > 0 and color == 'RED' and (slope <= 0) else 0
        down_run = down_run + 1 if ao < 0 and color == 'GREEN' and (slope <= 0) else 0
    signal = side != 0
    if max_lag == 0:
        if not np.array_equal(signal, f['signal']) or not np.array_equal(side, f['side']):
            raise ValueError('LAG_ZERO_MUST_REPRODUCE_STRICT')
        if not np.array_equal(states[signal], f['state'][signal]):
            raise ValueError('LAG_ZERO_TYPE_MISMATCH')
    return dict(events=events, audit=audit, states=states, signal=signal, side=side, pending_by_week=pending_log)

def calculate_models(f):
    f=dict(f)
    f['state'],f['pullback_weeks']=classify(f)
    f['signal']=np.isin(f['state'],SIGNALS)
    f['side']=np.where(np.isin(f['state'],(SIGNALS[0],SIGNALS[2])),1,
                       np.where(np.isin(f['state'],(SIGNALS[1],SIGNALS[3])),-1,0))
    from .protocol import MODELS
    return {name:resolve(f,i) for i,name in enumerate(MODELS)}
