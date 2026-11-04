"""One-position, unlevered cash-budget simulation, never an execution client."""
import numpy as np
from .data import MINUTE, window, validate_rows
from .signals import net_terms, stop_target


def adverse(price, side, slip):
    return price * (1 - side * slip)


def execute(c, signal, minutes, equity, fee, slip):
    record = dict(signal, equity_before=equity, equity_after=equity, net_pnl=0.0,
                  cycle_r=0.0, position_exposure='LONG_SPOT_ASSUMED_EXECUTION' if signal['side'] == 1 else
                  'SHORT_PRICE_ONLY_NOT_EXECUTABLE' if signal['side'] == -1 else 'NONE')
    if signal['status'] != 'SIGNAL':
        return record, None
    side = signal['side']
    stop, target = stop_target(c, side)
    start = signal['signal_at'] + MINUTE
    planned = signal['theoretical_entry']
    decision_entry = planned if signal['limit_price'] is not None else planned * (1 + side * slip)
    terms = net_terms(decision_entry, stop, target, side, fee, slip)
    record.update(stop=stop, target=target, earliest_execution_at=start,
                  decision_net_rr=terms.get('net_rr'), signal_price=planned)
    if not terms['valid']:
        return dict(record, status='REJECTED', reason=terms['reason']), None
    if start >= c['expiry']:
        return dict(record, status='REJECTED', reason='NO_EXECUTION_WINDOW'), None
    rows = window(minutes, start, c['expiry'] + MINUTE)
    if not len(rows) or rows[0, 0] != start or rows[-1, 0] != c['expiry']:
        return dict(record, status='REJECTED', reason='EXECUTION_DATA_UNAVAILABLE'), None
    try:
        validate_rows(rows, start, c['expiry'] + MINUTE, MINUTE)
    except ValueError:
        return dict(record, status='REJECTED', reason='EXECUTION_DATA_UNAVAILABLE'), None
    is_limit = signal['limit_price'] is not None
    fill_index = 0
    if is_limit:
        limit = signal['limit_price']
        if side * (c['l_close'] - limit) <= 0:
            return dict(record, status='REJECTED', reason='LIMIT_NOT_PASSIVE_AT_DECISION'), None
        # The last minute is the predeclared exit, never a new entry.
        candidates = np.flatnonzero(rows[:-1, 3] <= limit - .01 if side == 1 else rows[:-1, 2] >= limit + .01)
        if not len(candidates):
            return dict(record, status='UNFILLED', reason='EXPIRED_LIMIT'), None
        fill_index = int(candidates[0])
        entry_ref = entry = limit
    else:
        entry_ref = float(rows[0, 1])
        entry = entry_ref * (1 + side * slip)
    actual_terms = net_terms(entry, stop, target, side, fee, slip)
    if not actual_terms['valid']:
        return dict(record, status='REJECTED', reason='EXECUTION_' + actual_terms['reason'],
                    execution_reference_price=entry_ref, execution_entry=entry), None
    risk = actual_terms['risk_per_btc']
    qty = min(equity * .0025 / risk, equity / (entry * (1 + fee)))
    if qty <= 0:
        return dict(record, status='REJECTED', reason='NO_CAPITAL'), None
    held = rows[fill_index:]
    exit_i = len(held) - 1
    exit_ref = float(held[-1, 1])
    exit_reason = 'TIME'
    ambiguous = []
    marks = []
    for i, bar in enumerate(held[:-1]):
        t, o, high, low, close = bar
        hit_stop = low <= stop if side == 1 else high >= stop
        hit_tp = high >= target if side == 1 else low <= target
        if hit_stop:
            if hit_tp:
                ambiguous.append('STOP_AND_TP_SAME_MINUTE')
            if is_limit and i == 0:
                ambiguous.append('LIMIT_FILL_AND_STOP_SAME_MINUTE')
            exit_i = i
            exit_ref = float(min(o, stop) if side == 1 else max(o, stop))
            exit_reason = 'SL'
            break
        if hit_tp:
            if is_limit and i == 0:
                ambiguous.append('LIMIT_FILL_AND_TP_ORDER_UNKNOWN_NO_TP_CREDIT')
            else:
                exit_i, exit_ref, exit_reason = i, target, 'TP'
                break
        close_exit = adverse(close, side, slip)
        marks.append(equity + qty * (side * (close_exit - entry) - fee * (entry + close_exit)))
    exit_price = adverse(exit_ref, side, slip)
    fees = qty * fee * (entry + exit_price)
    gross = qty * side * (exit_ref - entry_ref)
    pnl = qty * side * (exit_price - entry) - fees
    marks.append(equity + pnl)
    path = held[:exit_i] if exit_reason == 'TIME' else held[:exit_i + 1]
    max_up = max(0., max(float(path[:, 2].max()) if len(path) else entry, exit_ref) / entry - 1)
    max_down = max(0., 1 - min(float(path[:, 3].min()) if len(path) else entry, exit_ref) / entry)
    mark_curve = np.array([equity, *marks])
    peak = np.maximum.accumulate(mark_curve)
    local_dd = float(np.max(1 - mark_curve / peak))
    trade = dict(cycle=c['cycle'], method=signal['method'], side=side, signal_at=signal['signal_at'],
                 theoretical_entry=planned, entry_at=int(held[0, 0]), entry_reference=entry_ref,
                 entry=entry, stop=stop, target=target, exit_at=int(held[exit_i, 0]),
                 exit_price=exit_price, exit_reason=exit_reason, quantity_btc=qty,
                 planned_risk=qty * risk, net_rr=actual_terms['net_rr'], gross_pnl=gross,
                 fees=fees, slippage_pnl_cost=gross - fees - pnl, net_pnl=pnl,
                 net_r=pnl / (qty * risk), cycle_r=pnl / (equity * .0025),
                 equity_before=equity, equity_after=equity + pnl,
                 mfe_bound=max_up if side == 1 else max_down,
                 mae_bound=max_down if side == 1 else max_up,
                 ambiguity=';'.join(ambiguous), is_limit=is_limit,
                 duration_minutes=(int(held[exit_i, 0]) - int(held[0, 0])) / MINUTE,
                 activation_delay_minutes=(int(held[0, 0]) - signal['signal_at']) / MINUTE,
                 local_mtm_drawdown=local_dd, mtm_min=float(mark_curve.min()),
                 mtm_max=float(mark_curve.max()), position_exposure=record['position_exposure'],
                 _mtm=mark_curve.tolist())
    return dict(record, status='TRADE', reason='ACCEPTED', **{k: trade[k] for k in
                ('equity_after', 'net_pnl', 'cycle_r', 'net_rr', 'entry_at', 'entry', 'exit_at', 'exit_reason')}), trade
