"""POST-HOC forward-only weekly timing sensitivity; no runtime authority."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from research import bitman_weekly_state_machine as sm
from research import bitman_state_analysis as original

LAGS = (0, 1, 2)
DEST = sm.ROOT/'research/results/bitman_weekly_source_alignment'
LABEL = 'POST_HOC_SOURCE_ALIGNED_LAG_SENSITIVITY'
STRICT_LABEL = 'PREDECLARED STRICT SAME-WEEK MODEL'
REVIEW_STATUS = 'INDEPENDENT TRANSCRIPT REVIEWED EXTERNALLY AFTER PREDECLARED ANALYSIS'


def model_name(lag):
    return 'STRICT_SAME_WEEK' if lag == 0 else 'LAG_LE'+str(lag)


def verify_strict(directory=DEST):
    baseline = json.loads((Path(directory)/'strict_baseline.json').read_text('utf-8'))
    for name, expected in baseline['sha256'].items():
        if sm.checksum(sm.ROOT/name) != expected:
            raise ValueError('STRICT_MODEL_CHANGED:'+name)
    return baseline


def resolve(f, max_lag):
    """One chronological pass, no outcome access or retrospective matching."""
    if type(max_lag) is not int or max_lag not in LAGS:
        raise ValueError('ONLY_LAG_0_1_2_ALLOWED')
    n = len(f['ao'])
    states = np.full(n, 'UNKNOWN', dtype='U60')
    side = np.zeros(n, int)
    pending_log, audit, events = [], [], []
    pending = None
    up_run = down_run = 0

    def record(action, i, candidate, reason):
        audit.append(dict(action=action, index=int(i), activation_index=candidate['activation_index'],
                          kind=candidate['kind'], reason=reason))

    for i in range(n):
        if not f['valid'][i]:
            if pending is not None:
                record('CANCELLED', i, pending, 'INVALID_WEEK')
            pending = None
            up_run = down_run = 0
            pending_log.append(None)
            continue
        ao, color, slope = f['ao'][i], f['color'][i], f['bbwp_slope'][i]
        base = str(f['state'][i])
        states[i] = ('IMPULSE_UP' if ao > 0 else 'IMPULSE_DOWN') if base in sm.SIGNALS else base
        if pending is not None:
            aligned_color = 'GREEN' if pending['side'] == 1 else 'RED'
            reason = ('ZERO_OR_OPPOSITE_SIGN' if ao*pending['side'] <= 0 else
                      'NEW_CORRECTION' if pending['kind'].startswith('REACCELERATION') and color != aligned_color else
                      'DEADLINE_EXPIRED' if i-pending['activation_index'] > max_lag else None)
            if reason:
                record('CANCELLED' if reason != 'DEADLINE_EXPIRED' else 'EXPIRED', i, pending, reason)
                pending = None
        previous = f['ao'][i-1] if i and f['valid'][i-1] else np.nan
        kind = None
        duration = 0
        if previous < 0 < ao:
            kind, direction, duration = 'ZERO_CROSS_UP_EXPANSION', 1, down_run
        elif previous > 0 > ao:
            kind, direction, duration = 'ZERO_CROSS_DOWN_EXPANSION', -1, up_run
        elif up_run and ao > 0 and color == 'GREEN':
            kind, direction, duration = 'REACCELERATION_UP', 1, up_run
        elif down_run and ao < 0 and color == 'RED':
            kind, direction, duration = 'REACCELERATION_DOWN', -1, down_run
        if kind:
            candidate = dict(kind=kind, side=direction, activation_index=int(i),
                             pullback_weeks=int(duration), start_index=int(i-duration if duration else max(0, i-1)))
            if pending is None:
                pending = candidate
                record('ACTIVATED', i, pending, 'OSCILLATOR_CHANGE_OBSERVED')
            else:
                record('IGNORED', i, candidate, 'EXISTING_SEQUENCE_OWNS_RESOLUTION')
        if pending is not None:
            age = i-pending['activation_index']
            if (age == 0 and slope > 0) or (age > 0 and f['turn'][i]):
                episode = dict(pending, index=int(i), lag=int(age),
                               episode_id='O'+str(int(f['frame'][pending['activation_index'], 0]))+'_'+pending['kind'],
                               activation_at=sm.iso(f['available_at'][pending['activation_index']]),
                               confirmed_at=sm.iso(f['available_at'][i]),
                               resolution_color=str(color),
                               sequence=sm.sequence(f, pending['start_index'], i))
                events.append(episode)
                states[i], side[i] = pending['kind'], pending['side']
                record('CONFIRMED', i, pending, 'IMMEDIATE_RISING' if age == 0 else 'DELAYED_TURN_UP')
                pending = None
            elif age >= max_lag:
                record('EXPIRED', i, pending, 'DEADLINE_WITHOUT_VOLATILITY_CONFIRMATION')
                pending = None
            else:
                states[i] = 'PENDING_'+pending['kind']
        pending_log.append(dict(pending) if pending is not None else None)
        up_run = up_run+1 if ao > 0 and color == 'RED' and slope <= 0 else 0
        down_run = down_run+1 if ao < 0 and color == 'GREEN' and slope <= 0 else 0
    signal = side != 0
    if max_lag == 0:
        if not np.array_equal(signal, f['signal']) or not np.array_equal(side, f['side']):
            raise ValueError('LAG_ZERO_MUST_REPRODUCE_STRICT')
        if not np.array_equal(states[signal], f['state'][signal]):
            raise ValueError('LAG_ZERO_TYPE_MISMATCH')
    return dict(events=events, audit=audit, states=states, signal=signal, side=side, pending_by_week=pending_log)


def summarize(f, model, out, grid, weights, selected, scope_mask, group, scope, length, horizon, lag):
    """Existing outcome math; scoped ratios use the same calendar opportunities."""
    selected = selected & scope_mask
    row = original.summary(f, out, grid, weights, selected, group, scope, length, horizon, infer=True)
    local, scoped = selected[grid], scope_mask[grid]
    labels = out['large_10'][grid]
    positives, tp = int(np.sum(labels[scoped])), int(np.sum(labels[local]))
    base = original.mean(labels[scoped])
    precision = original.mean(labels[local])
    row.update(model=model_name(lag), max_lag=lag, exposure=int(scoped.sum()),
               base_rate=base, precision=precision, true_positive=tp,
               false_negative=positives-tp, positives=positives,
               recall=tp/positives if positives else None,
               lift=precision/base if precision is not None and base else None,
               n_per_year=row['n']/(scoped.sum()/52.1775) if scoped.any() else None)
    sample_precision = original.boot_mean(labels, local, weights)
    sample_base = original.boot_mean(labels, scoped, weights)
    total_samples = (weights[:, scoped]*labels[scoped]).sum(axis=1)
    tp_samples = (weights[:, local]*labels[local]).sum(axis=1)
    row['recall_ci_low'], row['recall_ci_high'] = original.ci(np.divide(tp_samples, total_samples,
        out=np.full(len(weights), np.nan), where=total_samples > 0), row['n'])
    row['lift_ci_low'], row['lift_ci_high'] = original.ci(np.divide(sample_precision, sample_base,
        out=np.full(len(weights), np.nan), where=sample_base > 0), row['n'])
    # Conditional accuracy excludes censored no-break weeks; publish its n.
    row['direction_accuracy'] = row['directional_mean']
    row['direction_accuracy_n'] = row['directional_n']
    row['unconditional_direction_accuracy'] = row['correct_breakout_mean']
    return row


def analyze(f, replicates=original.REPLICATES):
    models = {lag: resolve(f, lag) for lag in LAGS}
    summaries, influence, observations = [], [], []
    for length in sm.RANGES:
        for horizon in sm.HORIZONS:
            out = sm.outcomes(f, length, horizon)
            grid = np.flatnonzero(f['valid'] & np.isfinite(out['forward']))
            weights = original.block_weights(len(grid), replicates, seed=original.SEED+horizon)
            for lag, model in models.items():
                context = dict(f, side=model['side'])
                scoped = dict(FULL=np.ones(len(f['valid']), bool),
                    **{era: f['era'] == era for era in original.ERAS},
                    BULL=f['regime'] == 'BULL', BEAR=f['regime'] == 'BEAR')
                groups = dict(ALL_SIGNALS=model['signal'], UP=model['side'] == 1, DOWN=model['side'] == -1,
                              **{kind: model['states'] == kind for kind in sm.SIGNALS})
                for scope, mask in scoped.items():
                    for group, selected in groups.items():
                        summaries.append(summarize(context, model, out, grid, weights, selected, mask,
                                                    group, scope, length, horizon, lag))
                if length == 4 and horizon == 4:
                    for scope, mask in scoped.items():
                        for row in original.influence(context, out, model['signal'] & mask, grid[mask[grid]]):
                            influence.append(dict(model=model_name(lag), scope=scope, **row))
                for episode in model['events']:
                    i = episode['index']
                    if not np.isfinite(out['forward'][i]):
                        continue
                    high, low = sm.causal_range(f['frame'], i, length)
                    observations.append(dict(model=model_name(lag), episode_id=episode['episode_id'],
                        kind=episode['kind'], activation_at=episode['activation_at'], confirmed_at=episode['confirmed_at'],
                        side=episode['side'], actual_lag=episode['lag'], horizon=horizon, range_weeks=length,
                        anchor=f['frame'][i,4], atr=f['atr'][i], range_high=high, range_low=low,
                        signed=episode['side']*out['forward'][i], **{k: v[i] for k,v in out.items()}))
    strict_identity = {(e['index'],e['kind']) for e in models[0]['events']}
    result_models = []
    for lag, model in models.items():
        identity = {(e['index'],e['kind']) for e in model['events']}
        result_models.append(dict(name=model_name(lag), max_lag=lag, episode_count=len(model['events']),
            family_counts={kind:sum(e['kind']==kind for e in model['events']) for kind in sm.SIGNALS},
            actual_lag_counts={str(k):sum(e['lag']==k for e in model['events']) for k in range(lag+1)},
            new_resolutions=[dict(confirmed_at=sm.iso(f['available_at'][i]),kind=kind) for i,kind in sorted(identity-strict_identity)],
            absent_strict_resolutions=[dict(confirmed_at=sm.iso(f['available_at'][i]),kind=kind) for i,kind in sorted(strict_identity-identity)],
            nonoverlap_count=int(sm.nonoverlap(model['signal']).sum()),
            events=model['events'], audit=model['audit'],
            current=dict(available_at=sm.iso(f['available_at'][-1]), state=str(model['states'][-1]),
                         pending=model['pending_by_week'][-1], signal=bool(model['signal'][-1]),
                         note='CURRENT OBSERVATION — NOT PART OF VALIDATION', large_move_watch='NOT VALIDATED')))
    return sm.clean(dict(label=LABEL, strict_label=STRICT_LABEL, transcript_review=REVIEW_STATUS,
        no_virgin_holdout=True, strict_conclusion='INCONCLUSIVE',
        conclusion='SOURCE-ALIGNED SENSITIVITY STILL INCONCLUSIVE',
        models=result_models, metrics=summaries, influence=influence, observations=observations,
        cutoff=1792368000000, data_reused=True, source_reported_by_owner=True,
        agent_direct_transcript_access=False,
        bootstrap=dict(replicates=replicates, block=original.BLOCK, root_seed=original.SEED,
                       seed_by_horizon={str(h):original.SEED+h for h in sm.HORIZONS})))


def run(directory=DEST):
    directory = Path(directory)
    verify_strict(directory)
    f = sm.load_inputs()
    result = analyze(f)
    for name in ('metrics', 'influence', 'observations'):
        sm.write_csv(directory/(name+'.csv'), result[name])
    compact = {k:v for k,v in result.items() if k not in ('metrics','influence','observations')}
    compact['protocol_sha256'] = sm.checksum(sm.ROOT/'research/results/BITMAN_WEEKLY_SOURCE_ALIGNMENT_PROTOCOL.md')
    (directory/'analysis.json').write_text(json.dumps(compact, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    verify_strict(directory)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    result = run()
    print(json.dumps(dict(conclusion=result['conclusion'],models=[{k:v for k,v in m.items() if k in
        ('name','episode_count','family_counts','actual_lag_counts','current')} for m in result['models']])))
