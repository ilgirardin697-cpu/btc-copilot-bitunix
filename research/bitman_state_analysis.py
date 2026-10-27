"""Independent sequential-episode outcomes and blocked descriptive inference."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from research import bitman_weekly_state_machine as sm

SEED, REPLICATES, BLOCK = 20261020, 2000, 8
ERAS = ('2020-2022', '2023-2024', '2025-2026')


def block_weights(n, replicates=REPLICATES, block=BLOCK, seed=SEED):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, (replicates, (n+block-1)//block))
    draws = ((starts[:, :, None]+np.arange(block)) % n).reshape(replicates, -1)[:, :n]
    return np.asarray([np.bincount(row, minlength=n) for row in draws], dtype=np.int16)


def boot_mean(values, mask, weights):
    ids = mask & np.isfinite(values)
    selected = weights[:, ids]
    denominator = selected.sum(axis=1)
    numerator = (selected*values[ids]).sum(axis=1)
    return np.divide(numerator, denominator, out=np.full(len(weights), np.nan), where=denominator > 0)


def boot_median(values, mask, weights):
    ids = np.flatnonzero(mask & np.isfinite(values))
    if not len(ids):
        return np.full(len(weights), np.nan)
    ids = ids[np.argsort(values[ids], kind='stable')]
    counts = weights[:, ids]
    total, cumulative = counts.sum(axis=1), np.cumsum(counts, axis=1)
    lo = np.argmax(cumulative > ((total-1)//2)[:, None], axis=1)
    hi = np.argmax(cumulative > (total//2)[:, None], axis=1)
    out = (values[ids[lo]]+values[ids[hi]])/2
    out[total == 0] = np.nan
    return out


def ci(samples, n):
    good = samples[np.isfinite(samples)]
    return list(np.quantile(good, [.025, .975])) if n >= 10 and len(good) >= .95*len(samples) else [None, None]


def mean(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return float(np.mean(values)) if len(values) else None


def groups(f):
    valid, sig, states = f['valid'], f['signal'], f['state']
    rising, falling, turn = f['bbwp_slope'] > 0, f['bbwp_slope'] < 0, f['turn']
    g = dict(SIGNALS=sig, SIGNAL_UP=sig & (f['side'] == 1), SIGNAL_DOWN=sig & (f['side'] == -1),
             ALL=valid, SIGN_POS=f['ao'] > 0, SIGN_NEG=f['ao'] < 0,
             COLOR_GREEN=f['color'] == 'GREEN', COLOR_RED=f['color'] == 'RED',
             VOL_TURN=turn, VOL_SUSTAINED_TURN=f['sustained_turn'], VOL_RISING=rising, VOL_FALLING=falling,
             PULLBACK_NO_REACCEL=np.isin(states, ('PULLBACK_UP', 'PULLBACK_DOWN')),
             IMPULSE_ENTRY=np.isin(states, ('IMPULSE_UP', 'IMPULSE_DOWN')) &
                 ~np.r_[False, np.isin(states[:-1], ('IMPULSE_UP', 'IMPULSE_DOWN'))],
             SIGNAL_NONOVERLAP=sm.nonoverlap(sig), ALL_CONGESTION=valid,
             SIGNAL_TURN=sig & turn, SIGNAL_ACTIVE_NOT_TURN=sig & rising & ~turn)
    for state in sm.STATES[:-2]:
        g[state] = states == state
    reacc = np.isin(states, sm.SIGNALS[:2])
    for n in (1, 2, 3):
        g['REACC_GE'+str(n)] = reacc & (f['pullback_weeks'] >= n)
    for n in (1, 2, 3, 4):
        g['REACC_EXACT_'+('GE4' if n == 4 else str(n))] = reacc & ((f['pullback_weeks'] >= 4) if n == 4 else (f['pullback_weeks'] == n))
    levels = dict(GT50=f['bbwp'] > 50, LE50=f['bbwp'] <= 50,
                  CROSS_UP50=(f['prior_bbwp'] <= 50) & (f['bbwp'] > 50),
                  CROSS_DOWN50=(f['prior_bbwp'] >= 50) & (f['bbwp'] < 50),
                  FALL_THROUGH50=(f['prior_bbwp'] >= 50) & (f['bbwp'] < 50) & falling,
                  TURN_LE50=turn & (f['bbwp'] <= 50), TURN_GT50=turn & (f['bbwp'] > 50))
    for name, mask in levels.items():
        g['LEVEL_'+name], g['SIGNAL_LEVEL_'+name] = mask, sig & mask
    for phase in range(4):
        g['CALENDAR_PHASE_'+str(phase)] = np.arange(len(valid)) % 4 == phase
        g['SIGNAL_PHASE_'+str(phase)] = sig & g['CALENDAR_PHASE_'+str(phase)]
    # A run-entry control does not sample every week of a persistent expansion.
    for name in ('SIGN_POS', 'SIGN_NEG', 'COLOR_GREEN', 'COLOR_RED', 'VOL_TURN', 'PULLBACK_NO_REACCEL'):
        mask = g[name] & valid
        g[name+'_RUN_ENTRY'] = mask & ~np.r_[False, mask[:-1]]
    return {k: v & valid for k, v in g.items()}


def summary(f, out, grid, weights, mask, name, scope, length, horizon, infer=False):
    local = mask[grid]
    ids = grid[local]
    side = np.where(f['ao'] > 0, 1., np.where(f['ao'] < 0, -1., np.nan))
    signed = out['forward']*side
    directional = np.where(out['breakout'] == 1, (out['first_side'] == side).astype(float), np.nan)
    correct = ((out['breakout'] == 1) & (out['first_side'] == side)).astype(float)
    values = dict(out, signed=signed, directional=directional, correct_breakout=correct,
                  terminal_hit=np.where(np.isfinite(signed), (signed > 0).astype(float), np.nan),
                  favorable=np.where(side == 1, out['up'], out['down']),
                  adverse=np.where(side == 1, out['down'], out['up']))
    n = len(ids)
    row = dict(group=name, scope=scope, range_weeks=length, horizon=horizon, n=n,
               exposure=len(grid), n_per_year=n/(len(grid)/52.1775) if len(grid) else None,
               sample_status='INSUFFICIENT FOR CONCLUSION' if n < 30 else 'DESCRIPTIVE / NO VIRGIN HOLDOUT')
    for key, array in values.items():
        row[key+'_n'] = int(np.isfinite(array[ids]).sum())
        row[key+'_mean'] = mean(array[ids])
        if key in ('max_move', 'max_atr', 'signed', 'forward', 'first_week', 'beyond_atr', 'up', 'down', 'favorable', 'adverse'):
            finite = array[ids][np.isfinite(array[ids])]
            for label, val in (('median', np.median(finite) if len(finite) else None),
                               ('sd', np.std(finite) if len(finite) else None)):
                row[key+'_'+label] = val
            for p in (10, 25, 75, 90):
                row[key+'_p'+str(p)] = np.percentile(finite, p) if len(finite) else None
            for k in (1, 3):
                row[key+'_ex_best'+str(k)] = mean(np.sort(finite)[:-k]) if len(finite) > k else None
        if infer and key in ('max_move', 'max_atr', 'signed', 'directional', 'terminal_hit', 'large_10'):
            row[key+'_ci_low'], row[key+'_ci_high'] = ci(boot_mean(array[grid], local, weights), row[key+'_n'])
            if key in ('max_move', 'signed'):
                row[key+'_median_ci_low'], row[key+'_median_ci_high'] = ci(boot_median(array[grid], local, weights), row[key+'_n'])
    label = out['large_10'][grid]
    positives = float(np.sum(label))
    true_positive = float(np.sum(label[local]))
    base = mean(label)
    row.update(base_rate=base, precision=mean(label[local]), recall=true_positive/positives if positives else None,
               true_positive=int(true_positive), false_positive=int(n-true_positive),
               false_negative=int(positives-true_positive), positives=int(positives),
               lift=(true_positive/n/base) if n and base else None,
               missed_breakout_censored=int(np.count_nonzero(out['breakout'][ids] == 0)))
    if infer:
        sample_precision = boot_mean(label, local, weights)
        sample_base = boot_mean(label, np.ones(len(grid), bool), weights)
        tps = (weights[:, local]*label[local]).sum(axis=1)
        totals = (weights*label).sum(axis=1)
        recall = np.divide(tps, totals, out=np.full(len(weights), np.nan), where=totals > 0)
        row['precision_ci_low'], row['precision_ci_high'] = ci(sample_precision, n)
        row['recall_ci_low'], row['recall_ci_high'] = ci(recall, n)
        row['lift_ci_low'], row['lift_ci_high'] = ci(np.divide(sample_precision, sample_base,
            out=np.full(len(weights), np.nan), where=sample_base > 0), n)
    return row


def comparison(out, grid, weights, event, reference, metric, side):
    values = out['forward']*side if metric == 'signed' else (
        np.where(out['breakout'] == 1, (out['first_side'] == side).astype(float), np.nan)
        if metric == 'directional' else out[metric])
    a, b = event[grid] & np.isfinite(values[grid]), reference[grid] & np.isfinite(values[grid])
    av, bv = values[grid][a], values[grid][b]
    ac, bc = len(av), len(bv)
    diff = mean(av)-mean(bv) if ac and bc else None
    low, high = ci(boot_mean(values[grid], a, weights)-boot_mean(values[grid], b, weights), min(ac, bc))
    result = dict(metric=metric, n_event=ac, n_reference=bc, difference=diff, ci_low=low, ci_high=high)
    for k in (1, 3):
        result['ex_best'+str(k)+'_difference'] = mean(np.sort(av)[:-k])-mean(bv) if ac > k and bc else None
    return result


def influence(f, out, selected, reference):
    ids = np.flatnonzero(selected & np.isfinite(out['forward']))
    rows = []
    for criterion in ('max_move', 'signed'):
        values = out['max_move'] if criterion == 'max_move' else out['forward']*f['side']
        order = ids[np.argsort(-values[ids], kind='stable')]
        for k in (0, 1, 3):
            removed, retained = order[:k], order[k:]
            rows.append(dict(criterion=criterion, excluded=k, n=len(retained),
                removed=[sm.iso(f['available_at'][i]) for i in removed],
                max_move=mean(out['max_move'][retained]), signed=mean((out['forward']*f['side'])[retained]),
                precision=mean(out['large_10'][retained]), base_rate=mean(out['large_10'][reference]),
                magnitude_difference=(mean(out['max_move'][retained])-mean(out['max_move'][reference])) if len(retained) else None))
    return rows


def temporal_control(f, out, sig, horizon):
    rows = []
    for i in np.flatnonzero(sig & np.isfinite(out['forward'])):
        ids = np.flatnonzero(f['valid'] & np.isfinite(out['forward']) & (np.arange(len(sig)) >= i-52) &
                             (np.arange(len(sig))+horizon <= i))
        if len(ids) < 12:
            continue
        rows.append(dict(index=int(i), signal_at=sm.iso(f['available_at'][i]), horizon=horizon,
                         n_past=len(ids), latest_control_mature_at=sm.iso(f['available_at'][ids[-1]+horizon]),
                         max_move_difference=float(out['max_move'][i]-np.mean(out['max_move'][ids])),
                         large_difference=float(out['large_10'][i]-np.mean(out['large_10'][ids]))))
    return rows


def analyze(f, replicates=REPLICATES):
    g = groups(f)
    tables, contrasts, raw, sensitivity, temporal = [], [], [], [], []
    event_names = ('SIGNALS', 'SIGNAL_UP', 'SIGNAL_DOWN', *sm.SIGNALS, 'SIGNAL_NONOVERLAP')
    episodes = sm.episodes(f)
    for length in sm.RANGES:
        for horizon in sm.HORIZONS:
            out = sm.outcomes(f, length, horizon)
            grid = np.flatnonzero(f['valid'] & np.isfinite(out['forward']))
            weights = block_weights(len(grid), replicates, seed=SEED+horizon)
            scope_masks = dict(FULL=np.ones(len(f['valid']), bool), **{era: f['era'] == era for era in ERAS},
                               BULL=f['regime'] == 'BULL', BEAR=f['regime'] == 'BEAR')
            for scope, scope_mask in scope_masks.items():
                local_grid = grid[scope_mask[grid]]
                # Full-timeline weights preserve gaps between eras/conditional controls.
                for name, mask in g.items():
                    if scope != 'FULL' and name not in (*event_names, 'ALL', 'VOL_TURN', 'VOL_FALLING'):
                        continue
                    selected = mask & scope_mask
                    if name == 'ALL_CONGESTION':
                        selected = selected & (out['congestion'] == 1)
                    row = summary(f, out, grid, weights, selected, name, scope, length, horizon,
                                  infer=length == 4 and (scope == 'FULL' or name in event_names) and name not in ('ALL_CONGESTION',))
                    # Recall/base rate use opportunities in the same era/regime, not all eras.
                    label = out['large_10'][local_grid]
                    selected_local = selected[local_grid]
                    base = mean(label)
                    precision = mean(label[selected_local])
                    total = int(label.sum())
                    tp = int(label[selected_local].sum())
                    row.update(exposure=len(local_grid), base_rate=base, precision=precision,
                        recall=tp/total if total else None, lift=precision/base if precision is not None and base else None,
                        positives=total, false_negative=total-tp,
                        n_per_year=row['n']/(len(local_grid)/52.1775) if len(local_grid) else None)
                    # Ratio CIs must use the same scoped denominator.
                    if scope != 'FULL':
                        local = selected[grid]
                        scoped = scope_mask[grid]
                        precision_samples = boot_mean(out['large_10'][grid], local, weights)
                        base_samples = boot_mean(out['large_10'][grid], scoped, weights)
                        total_samples = (weights[:, scoped]*out['large_10'][grid][scoped]).sum(axis=1)
                        tp_samples = (weights[:, local]*out['large_10'][grid][local]).sum(axis=1)
                        row['recall_ci_low'], row['recall_ci_high'] = ci(np.divide(tp_samples, total_samples,
                            out=np.full(len(weights), np.nan), where=total_samples > 0), row['n'])
                        row['lift_ci_low'], row['lift_ci_high'] = ci(np.divide(precision_samples, base_samples,
                            out=np.full(len(weights), np.nan), where=base_samples > 0), row['n'])
                    tables.append(row)
            for name in event_names:
                event = g[name]
                directions = (('UP', 1, 'SIGN_POS', 'COLOR_GREEN'), ('DOWN', -1, 'SIGN_NEG', 'COLOR_RED'))
                for direction, side, sign_group, color_group in directions:
                    selected = event & (f['side'] == side)
                    if name == 'SIGNALS' or np.any(selected):
                        for ref in ('ALL', sign_group, color_group, 'VOL_TURN', 'PULLBACK_NO_REACCEL', sign_group+'_RUN_ENTRY', color_group+'_RUN_ENTRY'):
                            for metric in ('max_move', 'large_10', 'signed', 'directional'):
                                contrasts.append(dict(group=name, direction=direction, reference=ref, range_weeks=length,
                                    horizon=horizon, **comparison(out, grid, weights, selected, g[ref], metric, side)))
                # Pooled magnitude uses both directions; never substitute UP-only lift.
                for ref in ('ALL', 'VOL_TURN', 'VOL_FALLING', 'PULLBACK_NO_REACCEL'):
                    for metric in ('max_move', 'large_10'):
                        contrasts.append(dict(group=name, direction='POOLED', reference=ref, range_weeks=length,
                            horizon=horizon, **comparison(out, grid, weights, event, g[ref], metric, 1)))
            for i in grid:
                high, low = sm.causal_range(f['frame'], i, length)
                raw.append(dict(index=int(i), signal_at=sm.iso(f['available_at'][i]), state=str(f['state'][i]),
                    signal=bool(f['signal'][i]), side=int(f['side'][i]), range_weeks=length, horizon=horizon,
                    range_high=high, range_low=low, atr=float(f['atr'][i]),
                    **{key: float(values[i]) for key, values in out.items()}))
            if length == 4:
                temporal += temporal_control(f, out, f['signal'], horizon)
            if length == 4 and horizon == 4:
                primary = out
                full_grid = grid
                main_influence = influence(f, out, f['signal'], grid)
                for block in (4, 8, 12):
                    w = block_weights(len(grid), replicates, block)
                    sensitivity.append(dict(block_weeks=block, **comparison(out, grid, w, f['signal'], g['ALL'], 'large_10', 1)))
                for episode in episodes:
                    i = episode['index']
                    episode['mature_4w'] = bool(np.isfinite(out['forward'][i]))
                    episode['outcome'] = {k: v[i] for k, v in out.items()}
    primary_eligible = np.isfinite(primary['forward']) & f['valid']
    categories = dict(
        VOL_TURN_NO_LARGE=f['turn'] & (primary['large_10'] == 0),
        VOL_TURN_NO_MOVE10=f['turn'] & (primary['move_10'] == 0),
        REACC_UP_NEGATIVE=(f['state'] == sm.SIGNALS[0]) & (primary['forward'] < 0),
        REACC_DOWN_POSITIVE=(f['state'] == sm.SIGNALS[1]) & (primary['forward'] > 0),
        REACC_UP_OPPOSITE=(f['state'] == sm.SIGNALS[0]) & (primary['first_side'] == -1),
        REACC_DOWN_OPPOSITE=(f['state'] == sm.SIGNALS[1]) & (primary['first_side'] == 1),
        LARGE_WHILE_VOL_FALLING=(f['bbwp_slope'] < 0) & (primary['large_10'] == 1),
        MOVE10_WHILE_VOL_FALLING=(f['bbwp_slope'] < 0) & (primary['move_10'] == 1),
        LARGE_WITHOUT_SETUP=~f['signal'] & (primary['large_10'] == 1),
        SETUP_FALSE_POSITIVE=f['signal'] & (primary['large_10'] == 0))
    falsification = []
    for name, mask in categories.items():
        for i in np.flatnonzero(mask & primary_eligible):
            falsification.append(dict(category=name, index=int(i), at=sm.iso(f['available_at'][i]),
                state=str(f['state'][i]), ao=f['ao'][i], ao_slope=f['ao_slope'][i], bbwp=f['bbwp'][i],
                bbwp_slope=f['bbwp_slope'][i], forward=primary['forward'][i], max_move=primary['max_move'][i],
                first_side=primary['first_side'][i], first_week=primary['first_week'][i]))
    overlap = []
    previous = None
    cluster = 0
    for i in np.flatnonzero(f['signal']):
        if previous is None or i-previous > 4:
            cluster += 1
        overlap.append(dict(index=int(i), at=sm.iso(f['available_at'][i]), cluster=cluster,
                            overlaps_previous=bool(previous is not None and i-previous <= 4)))
        previous = i
    last = len(f['frame'])-1
    current = dict(available_at=sm.iso(f['available_at'][last]), open_time=sm.iso(f['frame'][last, 0]),
        oscillator=f['ao'][last], oscillator_slope=f['ao_slope'][last], sign=str(f['sign'][last]),
        color=str(f['color'][last]), volatility_previous=f['prior_bbwp'][last], volatility=f['bbwp'][last],
        volatility_slope=f['bbwp_slope'][last], volatility_state=str(f['vol'][last]),
        turn_up=f['turn'][last], sustained_turn=f['sustained_turn'][last], state=str(f['state'][last]),
        ranges={str(n): dict(zip(('high', 'low'), sm.causal_range(f['frame'], last, n))) for n in sm.RANGES},
        sequence=sm.sequence(f, max(0, last-5), last), large_move_watch='NOT VALIDATED',
        disclaimer='CURRENT OBSERVATION — NOT PART OF VALIDATION')
    return sm.clean(dict(state_counts=Counter(str(s) for s in f['state'][f['valid']]),
        valid_weeks=int(f['valid'].sum()), first_eligible=sm.iso(f['available_at'][np.flatnonzero(f['valid'])[0]]),
        episode_count=len(episodes), episodes=episodes, runs=sm.descriptive_runs(f),
        summaries=tables, comparisons=contrasts, observations=raw, bootstrap_sensitivity=sensitivity,
        influence=main_influence, temporal_controls=temporal, falsification=falsification,
        falsification_counts={name: int(np.count_nonzero(mask & primary_eligible)) for name, mask in categories.items()},
        overlap=overlap, current=current, no_virgin_holdout=True))


def run(destination=sm.DEST, replicates=REPLICATES):
    destination = Path(destination)
    f = sm.load_inputs(destination)
    result = analyze(f, replicates)
    # Small metadata JSON plus full public per-opportunity and result tables.
    table_names = ('summaries', 'comparisons', 'observations', 'falsification', 'temporal_controls')
    for name in table_names:
        sm.write_csv(destination/(name+'.csv'), result[name])
    compact = {k: v for k, v in result.items() if k not in table_names}
    compact['method'] = dict(seed=SEED, replicates=replicates, block_weeks=BLOCK,
        protocol_sha256=sm.checksum(sm.ROOT/'research/results/BITMAN_WEEKLY_STATE_MACHINE_PROTOCOL.md'),
        reused_commit='c1c56bd1c4c87ad0f279616970ec9f13ae373302', input_sha256=sm.INPUT_HASHES)
    (destination/'analysis.json').write_text(json.dumps(compact, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    feature_rows = []
    for i in range(len(f['state'])):
        feature_rows.append(dict(open_time=int(f['frame'][i,0]), available_at=sm.iso(f['available_at'][i]),
            valid=bool(f['valid'][i]), state=str(f['state'][i]), signal=bool(f['signal'][i]),
            ao=f['ao'][i], ao_slope=f['ao_slope'][i], bbwp=f['bbwp'][i], bbwp_slope=f['bbwp_slope'][i],
            atr=f['atr'][i], turn_up=bool(f['turn'][i]), sustained_turn=bool(f['sustained_turn'][i]),
            pullback_weeks=int(f['pullback_weeks'][i]), era=str(f['era'][i]), regime=str(f['regime'][i])))
    sm.write_csv(destination/'states.csv', feature_rows)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=sm.DEST)
    args = parser.parse_args()
    result = run(args.destination)
    print(json.dumps({k: result[k] for k in ('state_counts', 'valid_weeks', 'episode_count', 'current')}))
