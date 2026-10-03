"""Independent public-data ML-RSI event study. No account or execution client.

This evaluates a documented causal port, NOT exact TradingView parity. Exit
levels are simulated numbers; they cannot be sent to an exchange.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import inspect
import json
import math
import numpy as np
from guardian_signals import rolling_mlrsi  # pure math only; operational file unchanged

STEP = 300000
QUARTER = 900000
HOUR = 3600000
START = 1577836800000
TRAIN_END = 1640995200000
VALID_END = 1704067200000
EVENTS = ('GREEN_CROSS', 'GREEN_RESUME', 'RED_CROSS', 'RED_RESUME')
ROOT = Path('research/mlrsi_pattern')
CACHE = Path('research/cache/mlrsi_pattern')


def digest(path):
    path = Path(path)
    # Git may check text out as CRLF on Windows; freeze canonical text content.
    raw = path.read_text('utf-8').encode('utf-8') if path.suffix in ('.py', '.json') else path.read_bytes()
    return hashlib.sha256(raw).hexdigest()


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


def aggregate(base, interval):
    a = validate(base)
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
    """Cross once per color episode; resume once per genuine slope reset.

    Two-bar CROSS waits for two slopes in its new color episode. Two-bar RESUME
    waits for two slopes after a reset, and is cancelled if the color changes.
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
        contiguous = timestamps is None or timestamps[i] - timestamps[i - 1] == QUARTER
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
    return {key: np.asarray(value, int) for key, value in output.items()}


def context(q, h):
    """Context diagnostics only; every 15m row sees a CLOSED 1H prefix."""
    tr = np.r_[h[0, 2] - h[0, 3], np.maximum(h[1:, 2] - h[1:, 3],
                   np.maximum(abs(h[1:, 2] - h[:-1, 4]), abs(h[1:, 3] - h[:-1, 4])))]
    atr = np.full(len(h), np.nan)
    if len(h) >= 14:
        atr[13] = tr[:14].mean()
        for i in range(14, len(h)):
            atr[i] = (13 * atr[i - 1] + tr[i]) / 14
    sma = np.full(len(h), np.nan)
    if len(h) >= 200:
        sums = np.r_[0., np.cumsum(h[:, 4])]
        sma[199:] = (sums[200:] - sums[:-200]) / 200
    indexes = np.searchsorted(h[:, 0] + HOUR, q[:, 0] + QUARTER, side='right') - 1
    clipped = np.maximum(indexes, 0)
    ratio = h[clipped, 4] / sma[clipped] - 1
    regime = np.where(ratio > .01, 'BULL', np.where(ratio < -.01, 'BEAR', 'SIDEWAYS'))
    regime[~np.isfinite(ratio) | (indexes < 0)] = 'UNKNOWN'
    pct = atr[clipped] / h[clipped, 4]
    volatility = np.where(pct < .005, 'LOW', np.where(pct >= .01, 'HIGH', 'MEDIUM'))
    volatility[~np.isfinite(pct) | (indexes < 0)] = 'UNKNOWN'
    available = atr[clipped].copy()
    available[indexes < 0] = np.nan
    return available, regime, volatility


@dataclass(frozen=True)
class Costs:
    fee_bps: float = 5.
    slippage_bps: float = 2.
    stop_slippage_bps: float = 5.

    def __post_init__(self):
        if not all(math.isfinite(x) and x >= 0 for x in asdict(self).values()):
            raise ValueError('COST_INVALID')


@dataclass(frozen=True)
class Management:
    exit: str = 'fixed500'
    stop_pct: float = .003
    trail_atr: float = 1.

    def __post_init__(self):
        if self.exit not in ('fixed500', 'atr', 'opposite', 'fixed1r', 'fixed2r', 'runner'):
            raise ValueError('EXIT_INVALID')
        if self.stop_pct not in (.0025, .003, .004, .005) or self.trail_atr not in (.75, 1.):
            raise ValueError('PARAMETER_INVALID')

    def key(self):
        return f'{self.exit}_{self.stop_pct:g}' + (f'_{self.trail_atr:g}' if self.exit == 'atr' else '')


def candidates():
    return [Management('opposite')] + [Management(exit, stop, factor)
        for stop in (.0025, .003, .004, .005)
        for exit, factor in (('fixed500', 1.), ('atr', .75), ('atr', 1.),
                             ('fixed1r', 1.), ('fixed2r', 1.), ('runner', 1.))]


def simulate(base, entry_time, side, atr, management, costs=Costs(),
             opposite_times=(), cutoff=None, close_fill=None, entry_index=None):
    """One independent 1x hypothetical event, on closed 5m data only.

    Same-bar ambiguity is conservative. New trailing levels apply NEXT bar,
    never retrospectively to an unknown high/low ordering inside this candle.
    """
    a = base
    first = int(np.searchsorted(a[:, 0], entry_time)) if entry_index is None else int(entry_index)
    result = dict(status='INCOMPLETE', entry_time=int(entry_time), side=side,
                  management=management.key(), ambiguity=False)
    if first >= len(a) or a[first, 0] != entry_time or side not in (-1, 1):
        return result
    if management.exit == 'atr' and (not math.isfinite(atr) or atr <= 0):
        return result
    end_time = entry_time + 48 * HOUR
    cutoff = int(a[-1, 0] + STEP) if cutoff is None else cutoff
    ref = float(a[first, 1] if close_fill is None else close_fill)
    entry = ref * (1 + side * costs.slippage_bps / 10000)
    stop = entry * (1 - side * management.stop_pct)
    risk = entry * management.stop_pct
    target = entry + side * risk * (2 if management.exit == 'fixed2r' else 1)
    distance = 500. if management.exit == 'fixed500' else management.trail_atr * atr
    remaining, tp1, best, mfe, mae = 1., False, entry, 0., 0.
    fills = []
    fees = costs.fee_bps / 10000
    opposite_times = np.asarray(opposite_times)
    opposite_index = int(np.searchsorted(opposite_times, entry_time, side='right'))
    opposite = opposite_times[opposite_index] if opposite_index < len(opposite_times) else math.inf
    def fill(price, weight, reason, when, stop_fill=False):
        nonlocal fees, mfe, mae
        actual = price * (1 - side * (costs.stop_slippage_bps if stop_fill else costs.slippage_bps) / 10000)
        fees += weight * costs.fee_bps / 10000 * actual / entry
        excursion = side * (price / entry - 1)
        mfe, mae = max(mfe, excursion), min(mae, excursion)
        fills.append(dict(raw=float(price), price=float(actual), qty=weight, reason=reason, time=int(when)))
    for i in range(first, len(a)):
        bar = a[i]
        stamp, opened, high, low, close = bar[:5]
        if stamp + STEP > cutoff or (i > first and stamp - a[i - 1, 0] != STEP):
            return result
        stop_active = management.exit != 'opposite'
        gap_stop = stop_active and (opened <= stop if side == 1 else opened >= stop)
        if gap_stop:
            reason = 'INITIAL_STOP' if not tp1 else 'BREAKEVEN' if stop == entry else 'TRAIL'
            fill(opened, remaining, reason, stamp, True)
            break
        if management.exit in ('opposite', 'runner') and stamp >= opposite:
            fill(opened, remaining, 'OPPOSITE', stamp)
            break
        if stamp >= end_time:
            fill(opened, remaining, 'TIMEOUT', stamp)
            break
        hit_stop = stop_active and (low <= stop if side == 1 else high >= stop)
        hit_target = (not tp1 and management.exit != 'opposite'
                      and (high >= target if side == 1 else low <= target))
        if hit_stop:
            price = min(opened, stop) if side == 1 else max(opened, stop)
            result['ambiguity'] |= bool(hit_target)
            reason = 'INITIAL_STOP' if not tp1 else 'BREAKEVEN' if stop == entry else 'TRAIL'
            fill(price, remaining, reason, stamp + STEP, True)
            break
        if hit_target:
            if management.exit in ('fixed1r', 'fixed2r'):
                fill(target, remaining, 'TARGET', stamp + STEP)
                break
            fill(target, .3, 'TP1', stamp + STEP)
            remaining, tp1 = .7, True
            stop = max(stop, entry) if side == 1 else min(stop, entry)
            if low <= stop if side == 1 else high >= stop:
                result['ambiguity'] = True
                fill(stop, remaining, 'BREAKEVEN', stamp + STEP, True)
                break
        # Only completed exposure candles contribute extrema; exit-candle fills
        # are included above without pretending its post-exit extreme was known.
        mfe = max(mfe, side * ((high if side == 1 else low) / entry - 1))
        mae = min(mae, side * ((low if side == 1 else high) / entry - 1))
        best = max(best, high) if side == 1 else min(best, low)
        if tp1 and management.exit in ('fixed500', 'atr'):
            proposed = best - side * distance
            stop = max(stop, proposed) if side == 1 else min(stop, proposed)
    else:
        return result
    gross = side * (sum(f['qty'] * f['raw'] / ref for f in fills) - 1)
    before_fees = side * (sum(f['qty'] * f['price'] / entry for f in fills) - 1)
    return dict(result, status='COMPLETE', reference=ref, entry=entry, gross=gross,
                net=before_fees - fees, fees=fees, slippage=gross - before_fees,
                expectancy_r=(before_fees - fees) / management.stop_pct,
                mfe=max(0., mfe), mae=min(0., mae), tp1=tp1,
                moved_be=tp1, exit_reason=fills[-1]['reason'], exit_time=fills[-1]['time'],
                hold_hours=(fills[-1]['time'] - entry_time) / HOUR, fills=fills)


def period(stamp):
    return 'TRAIN' if START <= stamp < TRAIN_END else 'VALIDATION' if TRAIN_END <= stamp < VALID_END else 'TEST' if stamp >= VALID_END else 'WARMUP'


def sequential(rows):
    selected, free = [], -1
    for row in sorted(rows, key=lambda x: (x['entry_time'], x.get('event', ''))):
        if row['entry_time'] >= free:
            selected.append(row)
            free = row['exit_time']
    return selected


def summarize(rows, signal_count=None):
    completed = [r for r in rows if r['status'] == 'COMPLETE']
    signal_count = len(rows) if signal_count is None else signal_count
    if not completed:
        return dict(signals=signal_count, trades=0, incomplete=len(rows), mean_net=None,
                    expectancy_r=None, max_dd=None)
    x = np.array([r['net'] for r in completed])
    gross = np.array([r['gross'] for r in completed])
    seq = sequential(completed)
    equity = np.r_[1., np.cumprod(1 + np.array([r['net'] for r in seq]))]
    ordered = sorted(completed, key=lambda r: r['net'])
    positive = gross[gross > 0].sum()
    profit = x[x > 0].sum()
    losses = -x[x < 0].sum()
    trim = lambda values: float(np.mean([r['expectancy_r'] for r in values])) if values else None
    return dict(signals=signal_count, trades=len(completed), incomplete=len(rows) - len(completed),
                win_rate=float(np.mean(x > .0001)), loss_rate=float(np.mean(x < -.0001)),
                breakeven_rate=float(np.mean(abs(x) <= .0001)), mean_gross=float(gross.mean()),
                mean_net=float(x.mean()), median_net=float(np.median(x)),
                expectancy_r=float(np.mean([r['expectancy_r'] for r in completed])),
                profit_factor=float(profit / losses) if losses else None,
                max_dd=float(-(equity / np.maximum.accumulate(equity) - 1).min()),
                sequential_trades=len(seq), sequential_net_return=float(equity[-1] - 1),
                median_mfe=float(np.median([r['mfe'] for r in completed])),
                median_mae=float(np.median([r['mae'] for r in completed])),
                tp1_rate=float(np.mean([r['tp1'] for r in completed])),
                stopped_before_tp1=float(np.mean([r['exit_reason'] == 'INITIAL_STOP' for r in completed])),
                moved_be_rate=float(np.mean([r['moved_be'] for r in completed])),
                price_be_exit_rate=float(np.mean([r['exit_reason'] == 'BREAKEVEN' for r in completed])),
                trailing_exit_rate=float(np.mean([r['exit_reason'] == 'TRAIL' for r in completed])),
                average_hold_hours=float(np.mean([r['hold_hours'] for r in completed])),
                fees_pct_gross_profit=float(sum(r['fees'] for r in completed) / positive) if positive else None,
                mean_fees=float(np.mean([r['fees'] for r in completed])),
                mean_slippage=float(np.mean([r['slippage'] for r in completed])),
                ambiguous_trades=sum(r['ambiguity'] for r in completed),
                without_top3_expectancy_r=trim(ordered[:-3]),
                without_worst3_expectancy_r=trim(ordered[3:]),
                top3_share_net_positive=float(sum(max(0, r['net']) for r in ordered[-3:]) / x[x > 0].sum()) if np.any(x > 0) else None)


def choose(training, validation):
    """TEST-shaped input is explicitly rejected. No TEST parameter selection."""
    if any(r['period'] != 'TRAIN' for r in training.values()) or any(r['period'] != 'VALIDATION' for r in validation.values()):
        raise ValueError('TEST_SELECTION_BLOCKED')
    eligible = []
    for key, row in training.items():
        val = validation[key]
        params = row['parameters']
        if params['stop_pct'] != .003 or params['exit'] not in ('fixed500', 'atr'):
            continue
        if min(row['metrics']['trades'], val['metrics']['trades']) < 100:
            continue
        eligible.append((min(row['metrics']['mean_net'], val['metrics']['mean_net']), key))
    return max(eligible)[1] if eligible else Management().key()


def bootstrap(rows):
    groups = {}
    for row in rows:
        if row['status'] == 'COMPLETE':
            groups.setdefault(row['entry_time'] // (7 * 24 * HOUR), []).append(row['net'])
    if not groups:
        return None
    sums = np.array([sum(g) for g in groups.values()])
    counts = np.array([len(g) for g in groups.values()])
    rng = np.random.default_rng(773)
    indexes = rng.integers(0, len(groups), size=(1000, len(groups)))
    values = sums[indexes].sum(axis=1) / counts[indexes].sum(axis=1)
    return dict(blocks=len(groups), seed=773, repetitions=1000,
                mean_net_ci95=np.quantile(values, [.025, .975]).tolist())


def features(base):
    q, h = aggregate(base, QUARTER), aggregate(base, HOUR)
    ml = rolling_mlrsi(q[:, 3], length=27, max_data=3000, max_iter=1000)
    atr, regimes, vols = context(q, h)
    return dict(q=q, rsi=ml['rsi'], state=ml['state'], valid=ml['valid'],
                converged=ml['converged'], atr=atr, regimes=regimes, vols=vols)


def feature_signature():
    pure = ''.join(inspect.getsource(fn) for fn in (validate, aggregate, context, features))
    pure += digest(Path(inspect.getsourcefile(rolling_mlrsi)))
    return hashlib.sha256(pure.encode()).hexdigest()[:16]


def event_rows(f, confirmation):
    q = f['q']
    events = detect_events(f['rsi'], f['state'], f['valid'] & f['converged'], confirmation, q[:, 0])
    result = []
    for name, indexes in events.items():
        for i in indexes:
            stamp = int(q[i, 0] + QUARTER)
            if stamp < START:
                continue
            date = datetime.fromtimestamp(stamp / 1000, timezone.utc)
            result.append(dict(index=int(i), event=name, side=1 if name.startswith('GREEN') else -1,
                               timestamp=stamp, period=period(stamp), year=date.year,
                               month=date.strftime('%Y-%m'), hour=date.hour, regime=str(f['regimes'][i]),
                               volatility=str(f['vols'][i]), atr=float(f['atr'][i]), reference=float(q[i, 4])))
    return sorted(result, key=lambda r: (r['timestamp'], r['event']))


def evaluate_events(base, f, events, management, costs, cutoff, close_fill=False):
    q = f['q']
    if '_opposite_times' not in f:
        crosses = detect_events(f['rsi'], f['state'], f['valid'] & f['converged'], 1, q[:, 0])
        f['_opposite_times'] = {1: q[crosses['RED_CROSS'], 0] + QUARTER,
                               -1: q[crosses['GREEN_CROSS'], 0] + QUARTER}
    opposite = f['_opposite_times']
    indexes = np.searchsorted(np.ascontiguousarray(base[:, 0]), [e['timestamp'] for e in events])
    rows = []
    for e, index in zip(events, indexes):
        end = min(cutoff, TRAIN_END if e['period'] == 'TRAIN' else VALID_END if e['period'] == 'VALIDATION' else cutoff)
        trade = simulate(base, e['timestamp'], e['side'], e['atr'], management, costs,
                         opposite[e['side']], end, e['reference'] if close_fill else None, index)
        rows.append(dict(trade, event=e['event'], year=e['year'], regime=e['regime'], volatility=e['volatility']))
    return rows


def controls(f, events):
    q = f['q']
    dates = [datetime.fromtimestamp(t / 1000, timezone.utc) for t in q[:, 0] + QUARTER]
    forbidden = {e['index'] for e in events}
    pools = {}
    for i, date in enumerate(dates):
        stamp = int(q[i, 0] + QUARTER)
        if stamp < START or i in forbidden or not np.isfinite(f['atr'][i]):
            continue
        key = (date.strftime('%Y-%m'), str(f['regimes'][i]), str(f['vols'][i]), date.hour)
        pools.setdefault(key, []).append(i)
    rng, matched = np.random.default_rng(773), []
    for e in events:
        pool = pools.get((e['month'], e['regime'], e['volatility'], e['hour']), [])
        if not pool:
            continue
        i = int(rng.choice(pool))
        matched.append(dict(e, index=i, timestamp=int(q[i, 0] + QUARTER),
                            atr=float(f['atr'][i]), reference=float(q[i, 4])))
    return matched


def run(phase, base_path, cutoff, fee_bps=5.):
    CACHE.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    prereg = ROOT / 'preregistered.json'
    code_hash, config_hash = digest(__file__), digest(prereg)
    base = validate(np.load(base_path)['bars'], cutoff=cutoff)
    if phase == 'development':
        base = base[base[:, 0] + STEP <= VALID_END]
    feature_path = CACHE / f'features-{digest(base_path)[:16]}-{phase}-{feature_signature()}.npz'
    if feature_path.exists():
        f = dict(np.load(feature_path))
    else:
        print('Computing causal LOW/27/EMA4 features; no outcome selection yet', flush=True)
        f = features(base)
        np.savez_compressed(feature_path, **f)
    output = dict(phase=phase, code_sha256=code_hash, prereg_sha256=config_hash,
                  dataset_sha256=digest(base_path), cutoff=cutoff, results={},
                  base_costs=asdict(Costs(fee_bps)), stress_costs=asdict(Costs(max(6, fee_bps + 1), 5, 10)))
    frozen_path = ROOT / 'frozen_selection.json'
    if phase == 'test':
        frozen = json.loads(frozen_path.read_text('utf-8'))
        if (frozen['code_sha256'] != code_hash or frozen['prereg_sha256'] != config_hash
                or frozen['base_fee_bps'] != fee_bps):
            raise ValueError('FROZEN_SPEC_CHANGED')
    else:
        frozen = dict(code_sha256=code_hash, prereg_sha256=config_hash, selections={},
                      development_data_end_exclusive=VALID_END, base_fee_bps=fee_bps)
    for confirm in (1, 2):
        events = event_rows(f, confirm)
        combined_primary, combined_selected = [], []
        for name in EVENTS:
            group = [e for e in events if e['event'] == name]
            key = f'{name}:{confirm}'
            models = {}
            chosen_rows = None
            for management in candidates():
                key_model = management.key()
                samples = group if phase == 'development' else [e for e in group if e['period'] == 'TEST']
                rows = evaluate_events(base, f, samples, management, Costs(fee_bps), cutoff)
                entry = dict(parameters=asdict(management))
                for p in (('TRAIN', 'VALIDATION') if phase == 'development' else ('TEST',)):
                    relevant = [r for r, e in zip(rows, samples) if e['period'] == p]
                    entry[p] = dict(period=p, parameters=asdict(management), metrics=summarize(relevant))
                models[key_model] = entry
                if phase == 'test' and key_model == frozen['selections'][key]:
                    chosen_rows = rows
            if phase == 'development':
                frozen['selections'][key] = choose({k: v['TRAIN'] for k, v in models.items()},
                                                   {k: v['VALIDATION'] for k, v in models.items()})
                extra = {}
            else:
                chosen = next(m for m in candidates() if m.key() == frozen['selections'][key])
                test_events = [e for e in group if e['period'] == 'TEST']
                control_events = [e for e in controls(f, events) if e['event'] == name and e['period'] == 'TEST']
                control_rows = evaluate_events(base, f, control_events, chosen, Costs(fee_bps), cutoff)
                primary = Management('fixed500', .003)
                primary_rows = evaluate_events(base, f, test_events, primary, Costs(fee_bps), cutoff)
                combined_primary.extend(primary_rows)
                combined_selected.extend(chosen_rows)
                extra = dict(selected=frozen['selections'][key], bootstrap=bootstrap(chosen_rows),
                    controls=summarize(control_rows), primary_bootstrap=bootstrap(primary_rows),
                    stress=summarize(evaluate_events(base, f, test_events, chosen, Costs(max(6, fee_bps + 1), 5, 10), cutoff)),
                    primary_stress=summarize(evaluate_events(base, f, test_events, primary, Costs(max(6, fee_bps + 1), 5, 10), cutoff)),
                    close_fill=summarize(evaluate_events(base, f, test_events, primary, Costs(fee_bps), cutoff, True)),
                    yearly={str(year): summarize([r for r in chosen_rows if r['year'] == year])
                            for year in sorted({r['year'] for r in chosen_rows})},
                    regimes={regime: summarize([r for r in chosen_rows if r['regime'] == regime])
                             for regime in ('BULL', 'BEAR', 'SIDEWAYS')},
                    volatility={vol: summarize([r for r in chosen_rows if r['volatility'] == vol])
                                for vol in ('LOW', 'MEDIUM', 'HIGH')},
                    recent_descriptive=summarize([r for r in chosen_rows if r['entry_time'] >= 1759276800000]))
                np.savez_compressed(CACHE / f'trades-{name}-{confirm}.npz', records=np.array([json.dumps(r) for r in chosen_rows]))
            output['results'][key] = dict(models=models, **extra)
            print(phase, key, 'selection', frozen['selections'][key], 'events', len(group), flush=True)
        if phase == 'test':
            output.setdefault('combined', {})[str(confirm)] = {
                label: {model: summarize([r for r in rows if side is None or r['side'] == side])
                        for model, rows in (('primary_fixed500', combined_primary), ('selected', combined_selected))}
                for label, side in (('LONG', 1), ('SHORT', -1), ('LONG_SHORT', None))}
    if phase == 'development':
        frozen_path.write_text(json.dumps(frozen, indent=2, allow_nan=False), encoding='utf-8')
    else:
        # Diagnostic screenshot windows only; never selection labels.
        times = f['q'][:, 0] + QUARTER
        observations = []
        for label, stamp in (('Oct1 evening CEST (representative 20:00)', 1790877600000),
                             ('Oct2 03:45 CEST', 1790905500000), ('Oct2 17:00 CEST', 1790953200000)):
            i = int(np.searchsorted(times, stamp, side='right') - 1)
            nearby = [e for e in event_rows(f, 1) if abs(e['timestamp'] - stamp) <= HOUR]
            observations.append(dict(label=label, requested_utc=stamp, actual_closed_time=int(times[i]),
                                     state=int(f['state'][i]), rsi=float(f['rsi'][i]), nearby_events=nearby))
        output['screenshots_diagnostic_only'] = observations
        output['classification'] = 'NO EDGE'  # exact parity gate fails; never inferred from a nice return
    (ROOT / (phase + '_results.json')).write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('development', 'test'), required=True)
    parser.add_argument('--data', default='research/cache/mlrsi_pattern/spot_5m.npz')
    parser.add_argument('--cutoff', type=int, required=True)
    parser.add_argument('--fee-bps', type=float, default=5.)
    args = parser.parse_args()
    run(args.phase, args.data, args.cutoff, args.fee_bps)
