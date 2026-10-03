"""Reproducible phase-separated 1H study; TEST cannot choose parameters."""
import argparse
from dataclasses import asdict
import json
import hashlib
import numpy as np
from research import mlrsi_1h_core as s


def code_hash():
    paths = (s.__file__, __file__, 'guardian_signals.py')
    return hashlib.sha256(''.join(s.digest(p) for p in paths).encode()).hexdigest()


def forward_all(base, events, costs, cutoff, close_fill=False):
    return {str(h): [s.forward(base, e, h, costs, cutoff, close_fill) for e in events] for h in s.HORIZONS}


def cohort_forward(events, rows):
    return {cohort: {h: s.forward_summary([r for e, r in zip(events, group) if s.aligned(e, cohort)])
        for h, group in rows.items()} for cohort in ('UNFILTERED', '4H', '1D', 'BOTH')}


def cohorts(events, rows):
    return {c: s.summarize([r for e, r in zip(events, rows) if s.aligned(e, c)])
            for c in ('UNFILTERED', '4H', '1D', 'BOTH')}


def neighbor_keys(chosen):
    models = s.candidates()
    if chosen.exit.startswith('fixed'):
        return [m.key() for m in models if m.exit.startswith('fixed')]
    return [m.key() for m in models if m.exit == chosen.exit and m.economic_be]


def promotion_gates(selection, metrics, stress, advantage, confidence, yearly, neighbors):
    ci = confidence['mean_ci95'] if confidence else [None, None]
    uplift_ci = advantage['bootstrap']['mean_ci95'] if advantage['bootstrap'] else [None, None]
    year_means = [r['mean_net'] for r in yearly.values() if r['mean_net'] is not None]
    valid_neighbors = [r['mean_net'] for r in neighbors.values() if r['mean_net'] is not None]
    return dict(
        adequate_sample=metrics['trades'] >= 100,
        development_positive=selection['min_dev_mean'] is not None and selection['min_dev_mean'] > 0,
        test_positive=metrics['mean_net'] is not None and metrics['mean_net'] > 0,
        profit_factor=metrics['profit_factor'] is not None and metrics['profit_factor'] >= 1.1,
        stressed_positive=stress['mean_net'] is not None and stress['mean_net'] > 0,
        without_best3_positive=metrics.get('without_best3_mean_net') is not None and metrics['without_best3_mean_net'] > 0,
        bootstrap_positive=ci[0] is not None and ci[0] > 0,
        control_advantage=advantage['mean_advantage'] is not None and advantage['mean_advantage'] > 0,
        paired_bootstrap_positive=uplift_ci[0] is not None and uplift_ci[0] > 0,
        yearly_stable=sum(v > 0 for v in year_means) >= 2 and all(v >= -.0025 for v in year_means),
        neighbor_stable=bool(len(valid_neighbors) >= 2 and np.mean([v > 0 for v in valid_neighbors]) >= .75))


def run(phase, data, cutoff, fee_bps=5.):
    s.CACHE.mkdir(parents=True, exist_ok=True)
    code, spec = code_hash(), s.digest(s.ROOT / 'preregistered.json')
    data_hash = s.digest(data)
    costs, stress_costs = s.Costs(fee_bps), s.Costs(max(6., fee_bps + 1), 5, 10)
    frozen_path = s.ROOT / 'frozen_selection.json'
    if phase == 'test':
        frozen = json.loads(frozen_path.read_text('utf-8'))
        if (frozen['code_sha256'] != code or frozen['spec_sha256'] != spec or
                frozen['dataset_sha256'] != data_hash or frozen['fee_bps'] != fee_bps or frozen['cutoff'] != cutoff):
            raise ValueError('FROZEN_SPEC_CHANGED')
    raw = s.validate(np.load(data)['bars'], cutoff=cutoff)
    base = raw[raw[:, 0] + s.STEP <= s.VALID_END] if phase == 'development' else raw
    cache = s.CACHE / f'features-{data_hash[:12]}-{code[:12]}-{phase}.npz'
    if cache.exists():
        f = dict(np.load(cache))
    else:
        print('Causal LOW/RSI27/EMA4 1H feature calculation:', phase, flush=True)
        f = s.features(base)
        np.savez_compressed(cache, **f)
    if phase == 'development':
        frozen = dict(code_sha256=code, spec_sha256=spec, dataset_sha256=data_hash,
            cutoff=cutoff, fee_bps=fee_bps, development_data_end_exclusive=s.VALID_END,
            volatility_cutpoints=s.volatility_boundaries(f), selections={}, filters_selected=False)
    boundaries = frozen['volatility_cutpoints']
    event_sets = {c: s.event_rows(f, c, boundaries) for c in (1, 2)}
    all_events = event_sets[1] + event_sets[2]
    output = dict(phase=phase, code_sha256=code, spec_sha256=spec, dataset_sha256=data_hash,
        cutoff=cutoff, base_costs=asdict(costs), stress_costs=asdict(stress_costs),
        volatility_cutpoints=boundaries, parity='Exact BackQuant TradingView parity is NOT proven.',
        results={}, feature_counts=dict(hourly=len(f['h']), valid=int(np.sum(f['valid'])),
            nonconverged=int(np.sum(f['valid'] & ~f['converged']))))
    combined = {c: [] for c in (1, 2)}
    for c in (1, 2):
        events = event_sets[c]
        control_events = s.matched_controls(f, events, all_events, boundaries) if phase == 'test' else []
        for name in s.EVENTS:
            sample = [e for e in events if e['event'] == name and (phase != 'test' or e['period'] == 'TEST')]
            controls = [e for e in control_events if e['event'] == name and e['period'] == 'TEST']
            key = f'{name}:{c}'
            entry = dict(signals=len(sample), models={}, forward={})
            # FIRST question: raw directional evidence, independent of management.
            raw_forward = forward_all(base, sample, costs, cutoff)
            for p in (('TRAIN', 'VALIDATION') if phase == 'development' else ('TEST',)):
                group = [e for e in sample if e['period'] == p]
                rows = {h: [r for e, r in zip(sample, path) if e['period'] == p] for h, path in raw_forward.items()}
                entry['forward'][p] = cohort_forward(group, rows)
            for m in s.candidates():
                rows = s.evaluate(base, f, sample, m, costs, cutoff)
                record = dict(parameters=asdict(m))
                for p in (('TRAIN', 'VALIDATION') if phase == 'development' else ('TEST',)):
                    subset = [r for e, r in zip(sample, rows) if e['period'] == p]
                    record[p] = dict(period=p, parameters=asdict(m), metrics=s.summarize(subset))
                entry['models'][m.key()] = record
            if phase == 'development':
                frozen['selections'][key] = s.choose({k: v['TRAIN'] for k, v in entry['models'].items()},
                                                   {k: v['VALIDATION'] for k, v in entry['models'].items()})
            else:
                selection = frozen['selections'][key]
                chosen = next(m for m in s.candidates() if m.key() == selection['key'])
                rows = s.evaluate(base, f, sample, chosen, costs, cutoff)
                combined[c].extend(rows)
                controls_rows = s.evaluate(base, f, controls, chosen, costs, cutoff)
                control_forward = forward_all(base, controls, costs, cutoff)
                ci = s.bootstrap(rows)
                advantage = s.pair_advantage(sample, controls, rows, controls_rows)
                stress = s.summarize(s.evaluate(base, f, sample, chosen, stress_costs, cutoff))
                yearly = {str(y): s.summarize([r for e, r in zip(sample, rows) if e['year'] == y]) for y in (2024, 2025, 2026)}
                neighbors = {k: entry['models'][k]['TEST']['metrics'] for k in neighbor_keys(chosen)}
                primary, naive = s.Management(), s.Management(economic_be=False)
                primary_rows = s.evaluate(base, f, sample, primary, costs, cutoff)
                naive_rows = s.evaluate(base, f, sample, naive, costs, cutoff)
                entry.update(selected=selection, bootstrap=ci, stress=stress,
                    close_fill=s.summarize(s.evaluate(base, f, sample, chosen, costs, cutoff, True)),
                    controls=s.summarize(controls_rows), control_match=dict(requested=len(sample), matched=len(controls),
                        unique_control_timestamps=len({e['timestamp'] for e in controls})),
                    paired_control_advantage=advantage, alignment=cohorts(sample, rows), yearly=yearly,
                    volatility={str(q): s.summarize([r for e, r in zip(sample, rows) if e['volatility'] == q]) for q in (1, 2, 3, 4)},
                    regime4={label: s.summarize([r for e, r in zip(sample, rows) if e['known4'] and e['trend4'] == trend])
                             for label, trend in (('BULL', 1), ('BEAR', -1))},
                    neighbors=neighbors, economic_vs_naive=dict(economic=s.summarize(primary_rows), naive=s.summarize(naive_rows)),
                    forward_controls=cohort_forward(controls, control_forward),
                    forward_advantage={h: s.pair_advantage(sample, controls, raw_forward[h], control_forward[h], 'directional_return')
                                       for h in raw_forward},
                    forward_close_fill={h: s.forward_summary(path) for h, path in forward_all(base, sample, costs, cutoff, True).items()},
                    forward_yearly={str(y): {h: s.forward_summary([r for e, r in zip(sample, path) if e['year'] == y])
                                           for h, path in raw_forward.items()} for y in (2024, 2025, 2026)},
                    forward_volatility={str(q): {h: s.forward_summary([r for e, r in zip(sample, path) if e['volatility'] == q])
                                               for h, path in raw_forward.items()} for q in (1, 2, 3, 4)},
                    recent_descriptive=s.summarize([r for e, r in zip(sample, rows) if e['timestamp'] >= 1759276800000]))
                gates = promotion_gates(selection, entry['models'][chosen.key()]['TEST']['metrics'], stress,
                                        advantage, ci, yearly, neighbors)
                entry['promotion_gates'] = gates
                entry['classification'] = ('PROMISING — SHADOW ONLY' if all(gates.values()) else
                    'INTERESTING BUT INCONCLUSIVE' if gates['test_positive'] else 'NO EDGE')
                np.savez_compressed(s.CACHE / f'outcomes-{name}-{c}.npz',
                    events=np.array([json.dumps(e) for e in sample]),
                    trades=np.array([json.dumps(r) for r in rows]),
                    forward=np.array([json.dumps(dict(r, horizon=int(h))) for h, path in raw_forward.items() for r in path]))
            output['results'][key] = entry
            print(phase, key, 'n', len(sample), 'selection', frozen['selections'][key]['key'], flush=True)
    if phase == 'development':
        s.save(frozen_path, frozen)
    else:
        output['combined'] = {str(c): {label: s.summarize([r for r in combined[c] if side is None or r['side'] == side])
                                     for label, side in (('LONG', 1), ('SHORT', -1), ('LONG_SHORT', None))} for c in (1, 2)}
        classes = [r['classification'] for r in output['results'].values()]
        output['classification'] = ('PROMISING — SHADOW ONLY' if 'PROMISING — SHADOW ONLY' in classes else
            'INTERESTING BUT INCONCLUSIVE' if 'INTERESTING BUT INCONCLUSIVE' in classes else 'NO EDGE')
    s.save(s.ROOT / f'{phase}_results.json', output)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=('development', 'test'), required=True)
    p.add_argument('--data', default='research/cache/mlrsi_1h/spot_5m.npz')
    p.add_argument('--cutoff', required=True, type=int)
    p.add_argument('--fee-bps', default=5., type=float)
    a = p.parse_args()
    run(a.phase, a.data, a.cutoff, a.fee_bps)
