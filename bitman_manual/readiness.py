"""Pure snapshot-only technical gates. No execution or trade authority.

READY means that the five user-defined predicates match, never validated edge.
Missing/unknown gate values fail closed to WAIT; no input is reconstructed.
"""

VALUES = {
    'state': ('UP', 'DOWN', 'TRANSITION', 'UNCLEAR', 'CONFLICT'),
    'strength': ('WEAK', 'BUILDING', 'STRONG'),
    'evidence_grade': ('A', 'B', 'C'),
    'timing_state': ('impulse_up', 'impulse_down', 'transition', 'no_impulse', 'pullback'),
    'mlrsi_confirmation': ('SUPPORTING', 'NEUTRAL', 'UNAVAILABLE', 'OPPOSING'),
}


def evaluate(snapshot):
    """Read only five existing fields; return fresh, sanitized explanation data."""
    source = snapshot if isinstance(snapshot, dict) else {}
    values = {}
    for field, allowed in VALUES.items():
        value = source.get(field)
        values[field] = value if type(value) is str and value in allowed else 'UNKNOWN'
    state, strength, grade, timing, ml = (values[field] for field in VALUES)
    side = {'UP': 'LONG', 'DOWN': 'SHORT'}.get(state)
    expected_timing = {'UP': 'impulse_up', 'DOWN': 'impulse_down'}.get(state)
    missing, codes = [], []

    def failed(field, required, code):
        codes.append(code)
        missing.append(dict(field=field, actual=values[field], required=required))

    if side is None:
        failed('state', 'UP / DOWN', 'DIRECTION_' + state)
    if strength != 'STRONG':
        failed('strength', 'STRONG', 'STRENGTH_' + strength)
    if grade != 'A':
        failed('evidence_grade', 'A', 'EVIDENCE_' + grade)
    if expected_timing is None or timing != expected_timing:
        failed('timing_state', expected_timing or 'ALIGNED_WITH_CONFIRMED_DIRECTION',
               'TIMING_UNCONFIRMED_DIRECTION' if expected_timing is None else
               'TIMING_PULLBACK' if timing == 'pullback' else 'TIMING_NOT_ALIGNED')
    if ml != 'SUPPORTING':
        failed('mlrsi_confirmation', 'SUPPORTING', 'MLRSI_' + ml)

    blocked = (side is None or strength == 'WEAK' or grade == 'C' or ml == 'OPPOSING'
               or 'UNKNOWN' in values.values())
    if blocked:
        return dict(gates_ready=False, status='WAIT', side=None, reason_codes=codes, missing_conditions=missing)
    if missing:
        return dict(gates_ready=False, status='WATCH_' + side, side=side, reason_codes=codes, missing_conditions=missing)
    return dict(gates_ready=True, status='READY_' + side, side=side, reason_codes=[], missing_conditions=[])
