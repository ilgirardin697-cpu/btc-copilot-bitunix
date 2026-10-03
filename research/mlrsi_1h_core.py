"""Independent, offline BTC 1H event research. No account/execution client.

Exact BackQuant TradingView parity is NOT proven. Only the existing pure
LOW/RSI27/EMA4 causal mathematical port is reused. No operational module changes.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from guardian_signals import rolling_mlrsi

STEP = 300000
HOUR = 3600000
DAY = 24 * HOUR
START = 1577836800000
TRAIN_END = 1640995200000
VALID_END = 1704067200000
EVENTS = ('GREEN_CROSS', 'GREEN_RESUME', 'RED_CROSS', 'RED_RESUME')
HORIZONS = (1, 2, 4, 8, 12, 24, 48, 72)
PASSAGES = ((.005, .005), (.01, .01), (.02, .01), (.03, .015), (.05, .02))
ROOT = Path('research/mlrsi_1h')
CACHE = Path('research/cache/mlrsi_1h')
SEED = 773


def digest(path):
    p = Path(path)
    raw = p.read_text('utf-8').encode() if p.suffix in ('.py', '.json') else p.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def validate(rows, interval=STEP, cutoff=None):
    a = np.asarray(rows, float)
    if a.ndim != 2 or a.shape[1] != 7 or not len(a) or not np.all(np.isfinite(a)):
        raise ValueError('DATA_INVALID')
    if np.any(a[:, 0] % interval) or np.any(np.diff(a[:, 0]) <= 0):
        raise ValueError('TIME_INVALID')
    if (np.any(a[:, 3] <= 0) or np.any(a[:, 2] < np.maximum(a[:, 1], a[:, 4]))
            or np.any(a[:, 3] > np.minimum(a[:, 1], a[:, 4])) or np.any(a[:, 5:] < 0)
            or np.any(a[:, 6] > a[:, 5])):
        raise ValueError('OHLC_INVALID')
    return a if cutoff is None else a[a[:, 0] + interval <= cutoff]


def aggregate(base, interval=HOUR):
    """Aggregate complete, contiguous CLOSED 5m groups; never fill gaps."""
    a = validate(base)
    if interval < STEP or interval % STEP:
        raise ValueError('INTERVAL_INVALID')
    groups = a[:, 0].astype(np.int64) // interval * interval
    starts = np.r_[0, np.flatnonzero(np.diff(groups)) + 1]
    ends = np.r_[starts[1:], len(a)]
    out = []
    for first, end in zip(starts, ends):
        p = a[first:end]
        if len(p) != interval // STEP or p[0, 0] != groups[first] or np.any(np.diff(p[:, 0]) != STEP):
            continue
        out.append([groups[first], p[0, 1], p[:, 2].max(), p[:, 3].min(), p[-1, 4],
                    p[:, 5].sum(), p[:, 6].sum()])
    return np.asarray(out, float).reshape(-1, 7)


def detect_events(rsi, states, valid=None, confirmations=1, timestamps=None):
    """PR #19 definitions, but contiguity and confirmation use 1H only.

    CROSS fires once on a color transition. RESUME requires a non-favorable
    slope reset in the same color. Two-bar versions wait for two favorable
    slopes; timestamps identify the later close, never the earlier setup.
    """
    if confirmations not in (1, 2):
        raise ValueError('CONFIRMATION_INVALID')
    rsi, states = np.asarray(rsi, float), np.asarray(states)
    valid = np.isfinite(rsi) if valid is None else np.asarray(valid, bool) & np.isfinite(rsi)
    if len(states) != len(rsi) or len(valid) != len(rsi):
        raise ValueError('SIGNAL_INPUT_INVALID')
    output = {name: [] for name in EVENTS}
    armed, resume_run, pending, cross_run = False, 0, False, 0
    for i in range(1, len(rsi)):
        contiguous = timestamps is None or timestamps[i] - timestamps[i - 1] == HOUR
        if not valid[i] or not valid[i - 1] or not contiguous:
            armed, resume_run, pending, cross_run = False, 0, False, 0
            continue
        state = int(states[i])
        slope = rsi[i] - rsi[i - 1]
        if state == 0:
            armed, resume_run, pending, cross_run = False, 0, False, 0
            continue
        name = 'GREEN' if state == 1 else 'RED'
        good = slope * state > 0
        changed = state != states[i - 1]
        if changed:
            armed, resume_run, pending, cross_run = not good, 0, True, 0
            if confirmations == 1:
                output[name + '_CROSS'].append(i)
                pending = False
        if pending:
            cross_run = cross_run + 1 if good else 0
            if cross_run >= confirmations:
                output[name + '_CROSS'].append(i)
                pending = False
        if not good:
            armed, resume_run = True, 0
        elif armed and not changed:
            resume_run += 1
            if resume_run >= confirmations:
                output[name + '_RESUME'].append(i)
                armed, resume_run = False, 0
    return {k: np.asarray(v, int) for k, v in output.items()}


def atr14(h):
    result = np.full(len(h), np.nan)
    tr = np.r_[h[0, 2] - h[0, 3], np.maximum(h[1:, 2] - h[1:, 3],
               np.maximum(abs(h[1:, 2] - h[:-1, 4]), abs(h[1:, 3] - h[:-1, 4])))]
    if len(h) >= 14:
        result[13] = tr[:14].mean()
        for i in range(14, len(h)):
            result[i] = (13 * result[i - 1] + tr[i]) / 14
    return result


def closed_trend(h, context, interval):
    """SMA200 diagnostic alignment, never a Copilot gate."""
    if not len(context):
        return np.zeros(len(h), np.int8), np.zeros(len(h), bool)
    sma = np.full(len(context), np.nan)
    if len(context) >= 200:
        cumulative = np.r_[0., np.cumsum(context[:, 4])]
        sma[199:] = (cumulative[200:] - cumulative[:-200]) / 200
    i = np.searchsorted(context[:, 0] + interval, h[:, 0] + HOUR, side='right') - 1
    clipped = np.maximum(i, 0)
    delta = context[clipped, 4] - sma[clipped]
    trend = np.where(delta > 0, 1, np.where(delta < 0, -1, 0)).astype(np.int8)
    known = (i >= 0) & np.isfinite(delta)
    trend[~known] = 0
    return trend, known


def features(base):
    h = aggregate(base)
    ml = rolling_mlrsi(h[:, 3], length=27, max_data=3000, max_iter=1000)
    trend4, known4 = closed_trend(h, aggregate(base, 4 * HOUR), 4 * HOUR)
    trend_d, known_d = closed_trend(h, aggregate(base, DAY), DAY)
    atr = atr14(h)
    return dict(h=h, rsi=ml['rsi'], state=ml['state'], valid=ml['valid'],
                converged=ml['converged'], atr=atr, atr_pct=atr / h[:, 4],
                trend4=trend4, known4=known4, trend_d=trend_d, known_d=known_d)


def volatility_boundaries(f):
    mask = ((f['h'][:, 0] + HOUR >= START) & (f['h'][:, 0] + HOUR < TRAIN_END)
            & np.isfinite(f['atr_pct']))
    if not np.any(mask):
        raise ValueError('TRAIN_VOLATILITY_MISSING')
    return np.quantile(f['atr_pct'][mask], [.25, .5, .75]).tolist()


def period(stamp):
    return ('TRAIN' if START <= stamp < TRAIN_END else 'VALIDATION' if TRAIN_END <= stamp < VALID_END
            else 'TEST' if stamp >= VALID_END else 'WARMUP')


def event_rows(f, confirmation, boundaries):
    h = f['h']
    detected = detect_events(f['rsi'], f['state'], f['valid'] & f['converged'], confirmation, h[:, 0])
    result = []
    for name, indexes in detected.items():
        for i in indexes:
            stamp = int(h[i, 0] + HOUR)
            if stamp < START or not np.isfinite(f['atr'][i]) or f['atr'][i] <= 0:
                continue
            date = datetime.fromtimestamp(stamp / 1000, timezone.utc)
            result.append(dict(index=int(i), event=name, side=1 if name.startswith('GREEN') else -1,
                timestamp=stamp, period=period(stamp), year=date.year, month=date.strftime('%Y-%m'),
                hour=date.hour, trend4=int(f['trend4'][i]), known4=bool(f['known4'][i]),
                trend_d=int(f['trend_d'][i]), known_d=bool(f['known_d'][i]),
                volatility=int(np.searchsorted(boundaries, f['atr_pct'][i], side='right') + 1),
                atr=float(f['atr'][i]), reference=float(h[i, 4])))
    return sorted(result, key=lambda e: (e['timestamp'], e['event']))


@dataclass(frozen=True)
class Costs:
    fee_bps: float = 5.
    slippage_bps: float = 2.
    stop_slippage_bps: float = 5.

    def __post_init__(self):
        if not all(math.isfinite(v) and 0 <= v < 100 for v in asdict(self).values()):
            raise ValueError('COST_INVALID')


@dataclass(frozen=True)
class Management:
    exit: str = 'atr_runner'
    stop_atr: float = 1.
    trail_atr: float = 1.5
    economic_be: bool = True

    def __post_init__(self):
        if self.exit not in ('atr_runner', 'color', 'color_runner', 'fixed1r', 'fixed2r', 'fixed3r'):
            raise ValueError('EXIT_INVALID')
        if self.stop_atr not in (0., .75, 1., 1.25, 1.5) or self.trail_atr not in (1., 1.5, 2.):
            raise ValueError('PARAMETER_INVALID')
        if self.stop_atr == 0 and self.exit != 'color':
            raise ValueError('STOP_REQUIRED')

    def key(self):
        base = f'{self.exit}:sl{self.stop_atr:g}'
        if self.exit == 'atr_runner':
            base += f':trail{self.trail_atr:g}'
        if self.exit in ('atr_runner', 'color_runner'):
            base += ':economic' if self.economic_be else ':naive'
        return base


def candidates():
    """One-factor neighbors, NOT the 4x3 Cartesian product."""
    result = [Management('atr_runner', stop, 1.5) for stop in (.75, 1., 1.25, 1.5)]
    result += [Management('atr_runner', 1., trail) for trail in (1., 2.)]
    result += [Management('atr_runner', 1., 1.5, False)]
    result += [Management('color', stop) for stop in (0., .75, 1., 1.25, 1.5)]
    result += [Management(exit) for exit in ('fixed1r', 'fixed2r', 'fixed3r', 'color_runner')]
    return result


def economic_breakeven(entry, tp1_actual, side, costs, weight=.3):
    """Trigger solving WHOLE-trade net PnL=0, including realized TP1.

    Entry/TP1/runner fees and expected adverse stop slippage are included.
    Positive TP1 may finance a trigger below entry for LONG (above for SHORT).
    This is total-trade economic BE, not runner-only BE or a guaranteed fill.
    """
    if entry <= 0 or side not in (-1, 1) or not 0 < weight < 1:
        raise ValueError('BE_INPUT_INVALID')
    fee = costs.fee_bps / 10000
    total_ratio = (side + fee) / (side - fee)
    exit_actual = entry * (total_ratio - weight * tp1_actual / entry) / (1 - weight)
    return exit_actual / (1 - side * costs.stop_slippage_bps / 10000)


def split_cutoff(e, cutoff):
    return min(cutoff, TRAIN_END if e['period'] == 'TRAIN' else VALID_END if e['period'] == 'VALIDATION' else cutoff)


def simulate(base, entry_time, side, atr, management, costs=Costs(), opposite_times=(),
             cutoff=None, close_fill=None, entry_index=None):
    """Independent 1x hypothetical trade; closed 5m conservative execution.

    Gap censors. Stop precedes TP in ambiguous OHLC. A trailing update applies
    only from the next 5m candle. All stops/trails use ATR frozen at the signal.
    """
    first = int(np.searchsorted(base[:, 0], entry_time)) if entry_index is None else int(entry_index)
    result = dict(status='INCOMPLETE', entry_time=int(entry_time), side=side,
                  management=management.key(), ambiguity=False)
    if (first >= len(base) or base[first, 0] != entry_time or side not in (-1, 1)
            or not math.isfinite(atr) or atr <= 0):
        return result
    cutoff = int(base[-1, 0] + STEP) if cutoff is None else cutoff
    ref = float(base[first, 1] if close_fill is None else close_fill)
    entry = ref * (1 + side * costs.slippage_bps / 10000)
    risk = (management.stop_atr or 1.) * atr
    stop_active = management.stop_atr > 0
    stop = entry - side * risk
    multiple = int(management.exit[5]) if management.exit.startswith('fixed') else 1
    target = entry + side * risk * multiple
    distance = management.trail_atr * atr
    remaining, tp1, best, mfe, mae = 1., False, entry, 0., 0.
    be_trigger = None
    fills = []
    fees = costs.fee_bps / 10000
    opposite_times = np.asarray(opposite_times)
    oi = np.searchsorted(opposite_times, entry_time, side='right')
    opposite = opposite_times[oi] if oi < len(opposite_times) else math.inf

    def fill(price, weight, reason, when, stop_fill=False):
        nonlocal fees, mfe, mae
        slip = costs.stop_slippage_bps if stop_fill else costs.slippage_bps
        actual = price * (1 - side * slip / 10000)
        fees += weight * costs.fee_bps / 10000 * actual / entry
        excursion = side * (price / entry - 1)
        mfe, mae = max(mfe, excursion), min(mae, excursion)
        fills.append(dict(raw=float(price), price=float(actual), qty=weight, reason=reason, time=int(when)))

    def stop_reason():
        if not tp1:
            return 'INITIAL_STOP'
        return 'ECONOMIC_BE' if management.economic_be and stop == be_trigger else 'PRICE_BE' if stop == entry else 'TRAIL'

    for i in range(first, len(base)):
        stamp, opened, high, low, close = base[i, :5]
        if stamp + STEP > cutoff or (i > first and stamp - base[i - 1, 0] != STEP):
            return result
        if stop_active and (opened <= stop if side == 1 else opened >= stop):
            fill(opened, remaining, stop_reason(), stamp, True)
            break
        if management.exit in ('color', 'color_runner') and stamp >= opposite:
            fill(opened, remaining, 'OPPOSITE', stamp)
            break
        if stamp >= entry_time + 72 * HOUR:
            fill(opened, remaining, 'TIMEOUT', stamp)
            break
        hit_stop = stop_active and (low <= stop if side == 1 else high >= stop)
        hit_target = management.exit != 'color' and not tp1 and (high >= target if side == 1 else low <= target)
        if hit_stop:
            result['ambiguity'] |= bool(hit_target)
            fill(min(opened, stop) if side == 1 else max(opened, stop), remaining, stop_reason(), stamp + STEP, True)
            break
        if hit_target:
            if management.exit.startswith('fixed'):
                fill(target, 1., 'TARGET', stamp + STEP)
                break
            fill(target, .3, 'TP1', stamp + STEP)
            remaining, tp1 = .7, True
            be_trigger = economic_breakeven(entry, fills[-1]['price'], side, costs) if management.economic_be else entry
            stop = max(stop, be_trigger) if side == 1 else min(stop, be_trigger)
            # A target beyond the current TP1 price cannot be assumed filled.
            if side * (stop - target) >= 0:
                fill(target, remaining, 'BE_UNREACHABLE', stamp + STEP, True)
                result['ambiguity'] = True
                break
            if low <= stop if side == 1 else high >= stop:
                result['ambiguity'] = True
                fill(stop, remaining, stop_reason(), stamp + STEP, True)
                break
        mfe = max(mfe, side * ((high if side == 1 else low) / entry - 1))
        mae = min(mae, side * ((low if side == 1 else high) / entry - 1))
        best = max(best, high) if side == 1 else min(best, low)
        if tp1 and management.exit == 'atr_runner':
            proposed = best - side * distance
            stop = max(stop, proposed) if side == 1 else min(stop, proposed)
    else:
        return result
    gross = side * (sum(f['qty'] * f['raw'] / ref for f in fills) - 1)
    before_fees = side * (sum(f['qty'] * f['price'] / entry for f in fills) - 1)
    return dict(result, status='COMPLETE', reference=ref, entry=entry, gross=gross,
                net=before_fees - fees, fees=fees, slippage=gross - before_fees,
                expectancy_r=(before_fees - fees) / (risk / entry),
                mfe=max(0., mfe), mae=min(0., mae), tp1=tp1, moved_be=tp1,
                be_trigger=be_trigger, exit_reason=fills[-1]['reason'], exit_time=fills[-1]['time'],
                hold_hours=(fills[-1]['time'] - entry_time) / HOUR, fills=fills)


def passage_key(up, down):
    return f'+{100 * up:g}/-{100 * down:g}'


def forward(base, e, hours, costs=Costs(), cutoff=None, close_fill=False):
    """Directional evidence before choosing exits; complete closed 5m only.

    Both barriers in one 5m candle count conservatively as failure, and the
    ambiguity is disclosed. Neither touched is censored, not a success.
    """
    t, side = e['timestamp'], e['side']
    cutoff = int(base[-1, 0] + STEP) if cutoff is None else cutoff
    end = t + hours * HOUR
    result = dict(status='INCOMPLETE', entry_time=t, side=side, horizon=hours)
    if end > split_cutoff(e, cutoff):
        return result
    i = int(np.searchsorted(base[:, 0], t))
    path = base[i:i + hours * 12]
    if len(path) != hours * 12 or path[0, 0] != t or path[-1, 0] + STEP != end or np.any(np.diff(path[:, 0]) != STEP):
        return result
    ref = e['reference'] if close_fill else float(path[0, 1])
    entry = ref * (1 + side * costs.slippage_bps / 10000)
    favorable = side * ((path[:, 2] if side == 1 else path[:, 3]) / entry - 1)
    adverse = side * ((path[:, 3] if side == 1 else path[:, 2]) / entry - 1)
    ret = side * (path[-1, 4] / entry - 1)
    actual_exit = path[-1, 4] * (1 - side * costs.slippage_bps / 10000)
    net = side * (actual_exit / entry - 1) - costs.fee_bps / 10000 * (1 + actual_exit / entry)
    first_passage = {}
    for up, down in PASSAGES:
        positive, negative = np.flatnonzero(favorable >= up), np.flatnonzero(adverse <= -down)
        p = int(positive[0]) if len(positive) else math.inf
        n = int(negative[0]) if len(negative) else math.inf
        first_passage[passage_key(up, down)] = dict(success=bool(p < n),
            ambiguous=bool(p == n and math.isfinite(p)), neither=bool(not math.isfinite(min(p, n))))
    return dict(result, status='COMPLETE', reference=ref, entry=entry, directional_return=float(ret),
                net=float(net), mfe=float(max(0., favorable.max())), mae=float(min(0., adverse.min())),
                passages=first_passage)


def sequential(rows):
    selected, free = [], -1
    for r in sorted(rows, key=lambda r: (r['entry_time'], r.get('event', ''))):
        if r['entry_time'] >= free:
            selected.append(r)
            free = r['exit_time']
    return selected


def summarize(rows):
    a = [r for r in rows if r['status'] == 'COMPLETE']
    if not a:
        return dict(signals=len(rows), trades=0, incomplete=len(rows), mean_net=None,
                    expectancy_r=None, profit_factor=None, max_dd=None)
    x = np.array([r['net'] for r in a])
    gross = np.array([r['gross'] for r in a])
    seq = sequential(a)
    equity = np.r_[1., np.cumprod(1 + np.array([r['net'] for r in seq]))]
    ordered = sorted(a, key=lambda r: r['net'])
    profit, loss = x[x > 0].sum(), -x[x < 0].sum()
    trim = lambda z: float(np.mean([r['net'] for r in z])) if z else None
    return dict(signals=len(rows), trades=len(a), incomplete=len(rows) - len(a),
        small_sample=len(a) < 100, win_rate=float(np.mean(x > .0001)), loss_rate=float(np.mean(x < -.0001)),
        breakeven_rate=float(np.mean(abs(x) <= .0001)), mean_gross=float(gross.mean()), mean_net=float(x.mean()),
        median_net=float(np.median(x)), expectancy_r=float(np.mean([r['expectancy_r'] for r in a])),
        profit_factor=float(profit / loss) if loss else None,
        max_dd=float(-(equity / np.maximum.accumulate(equity) - 1).min()), sequential_trades=len(seq),
        sequential_net_return=float(equity[-1] - 1), median_mfe=float(np.median([r['mfe'] for r in a])),
        median_mae=float(np.median([r['mae'] for r in a])), tp1_rate=float(np.mean([r['tp1'] for r in a])),
        stopped_before_tp1=float(np.mean([r['exit_reason'] == 'INITIAL_STOP' for r in a])),
        moved_be_rate=float(np.mean([r['moved_be'] for r in a])),
        be_exit_rate=float(np.mean([r['exit_reason'] in ('ECONOMIC_BE', 'PRICE_BE') for r in a])),
        trailing_exit_rate=float(np.mean([r['exit_reason'] == 'TRAIL' for r in a])),
        average_hold_hours=float(np.mean([r['hold_hours'] for r in a])),
        mean_fees=float(np.mean([r['fees'] for r in a])), mean_slippage=float(np.mean([r['slippage'] for r in a])),
        fees_pct_gross_profit=float(sum(r['fees'] for r in a) / gross[gross > 0].sum()) if np.any(gross > 0) else None,
        ambiguous_trades=sum(r['ambiguity'] for r in a), without_best3_mean_net=trim(ordered[:-3]),
        without_worst3_mean_net=trim(ordered[3:]),
        top3_share_positive=float(sum(max(0, r['net']) for r in ordered[-3:]) / profit) if profit else None)


def bootstrap(rows, field='net'):
    groups = {}
    for r in rows:
        if r['status'] == 'COMPLETE':
            groups.setdefault(r['entry_time'] // (7 * DAY), []).append(r[field])
    if not groups:
        return None
    sums = np.array([sum(g) for g in groups.values()])
    counts = np.array([len(g) for g in groups.values()])
    rng = np.random.default_rng(SEED)
    indexes = rng.integers(0, len(groups), size=(1000, len(groups)))
    samples = sums[indexes].sum(axis=1) / counts[indexes].sum(axis=1)
    return dict(blocks=len(groups), seed=SEED, repetitions=1000,
                mean_ci95=np.quantile(samples, [.025, .975]).tolist())


def forward_summary(rows):
    complete = [r for r in rows if r['status'] == 'COMPLETE']
    out = dict(signals=len(rows), complete=len(complete), incomplete=len(rows) - len(complete),
               small_sample=len(complete) < 100)
    if not complete:
        return dict(out, mean=None, median=None, mean_net=None, median_mfe=None, median_mae=None, passages={})
    passages = {}
    for up, down in PASSAGES:
        key = passage_key(up, down)
        p = [r['passages'][key] for r in complete]
        passages[key] = dict(probability=float(np.mean([v['success'] for v in p])), n=len(p),
            successes=sum(v['success'] for v in p), ambiguous=sum(v['ambiguous'] for v in p),
            neither=sum(v['neither'] for v in p))
    return dict(out, mean=float(np.mean([r['directional_return'] for r in complete])),
        median=float(np.median([r['directional_return'] for r in complete])),
        mean_net=float(np.mean([r['net'] for r in complete])),
        median_mfe=float(np.median([r['mfe'] for r in complete])),
        median_mae=float(np.median([r['mae'] for r in complete])), passages=passages,
        bootstrap=bootstrap(complete, 'directional_return'))


def matched_controls(f, events, all_events, boundaries):
    """One non-event per event; exact month/hour/4H regime/TRAIN-vol quartile.

    Deterministic replacement sampling. All one/two-bar event timestamps are
    excluded. Missing strata stay unmatched; never relax matching after TEST.
    """
    forbidden = {e['index'] for e in all_events}
    pools = {}
    for i, stamp in enumerate(f['h'][:, 0] + HOUR):
        if stamp < START or i in forbidden or not np.isfinite(f['atr'][i]) or f['atr'][i] <= 0:
            continue
        date = datetime.fromtimestamp(stamp / 1000, timezone.utc)
        vol = int(np.searchsorted(boundaries, f['atr_pct'][i], side='right') + 1)
        key = (date.strftime('%Y-%m'), date.hour, int(f['trend4'][i]), bool(f['known4'][i]), vol)
        pools.setdefault(key, []).append(i)
    rng, result = np.random.default_rng(SEED), []
    for e in events:
        pool = pools.get((e['month'], e['hour'], e['trend4'], e['known4'], e['volatility']), [])
        if not pool:
            continue
        i = int(rng.choice(pool))
        result.append(dict(e, paired_timestamp=e['timestamp'], index=i,
            timestamp=int(f['h'][i, 0] + HOUR), reference=float(f['h'][i, 4]), atr=float(f['atr'][i]),
            trend_d=int(f['trend_d'][i]), known_d=bool(f['known_d'][i])))
    return result


def aligned(e, cohort):
    four = e['known4'] and e['trend4'] == e['side']
    daily = e['known_d'] and e['trend_d'] == e['side']
    return cohort == 'UNFILTERED' or cohort == '4H' and four or cohort == '1D' and daily or cohort == 'BOTH' and four and daily


def choose(training, validation):
    if any(r['period'] != 'TRAIN' for r in training.values()) or any(r['period'] != 'VALIDATION' for r in validation.values()):
        raise ValueError('TEST_SELECTION_BLOCKED')
    eligible = []
    for k, t in training.items():
        v, m = validation[k], t['parameters']
        if not m['economic_be'] or m['exit'] == 'color' and m['stop_atr'] not in (0., 1.):
            continue
        if min(t['metrics']['trades'], v['metrics']['trades']) < 100:
            continue
        eligible.append((min(t['metrics']['mean_net'], v['metrics']['mean_net']), k))
    if not eligible:
        return dict(key=Management().key(), eligible=0, min_dev_mean=None, fallback=True)
    score, k = max(eligible)
    return dict(key=k, eligible=len(eligible), min_dev_mean=score, fallback=False)


def pair_advantage(events, controls, event_rows, control_rows, field='net'):
    """Pair controls using the original signal timestamps for block inference."""
    originals = {(e['event'], e['timestamp']): r for e, r in zip(events, event_rows)}
    paired = []
    for e, r in zip(controls, control_rows):
        source = originals.get((e['event'], e['paired_timestamp']))
        if source and source['status'] == r['status'] == 'COMPLETE':
            paired.append(dict(status='COMPLETE', entry_time=e['paired_timestamp'],
                               net=source[field] - r[field]))
    return dict(n=len(paired), mean_advantage=float(np.mean([r['net'] for r in paired])) if paired else None,
                bootstrap=bootstrap(paired))


def evaluate(base, f, events, management, costs, cutoff, close_fill=False):
    detected = detect_events(f['rsi'], f['state'], f['valid'] & f['converged'], 1, f['h'][:, 0])
    opposite = {1: f['h'][detected['RED_CROSS'], 0] + HOUR,
                -1: f['h'][detected['GREEN_CROSS'], 0] + HOUR}
    indexes = np.searchsorted(base[:, 0], [e['timestamp'] for e in events])
    out = []
    for e, index in zip(events, indexes):
        r = simulate(base, e['timestamp'], e['side'], e['atr'], management, costs, opposite[e['side']],
                     split_cutoff(e, cutoff), e['reference'] if close_fill else None, int(index))
        out.append(dict(r, event=e['event'], year=e['year'], trend4=e['trend4'], volatility=e['volatility']))
    return out
