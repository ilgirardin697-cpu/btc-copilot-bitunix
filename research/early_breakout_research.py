"""Finite preregistered public-market event research; TEST is evaluation only."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import gzip
import io
import hashlib
import json
from pathlib import Path
import numpy as np
from early_breakout_core import (Engine, Indicators, Parameters, STEP, HORIZONS, PASSAGES,
                                 aggregate, event_outcome)
from research.early_breakout_data import download
from research.early_breakout_reference import manual_reference

OUTPUT = Path('research/early_breakout_artifacts')
START = 1577836800000
TRAIN_END = 1640995200000
VALID_END = 1704067200000
WEEK = 7*86400000


def split(timestamp):
    if timestamp < START:
        return 'WARMUP'
    return 'TRAIN' if timestamp < TRAIN_END else 'VALIDATION' if timestamp < VALID_END else 'TEST'


def candidate_grid():
    baseline = Parameters()
    result = [baseline]
    for key, values in (('percentile', (.15, .25)), ('duration', (2, 4)),
                        ('volume_z', (1., 2.)), ('hold', (0,)), ('acceleration', (False,))):
        result += [replace(baseline, **{key: value}) for value in values]
    return result  # nine one-factor candidates, NEVER the 108-member Cartesian product


def parameter_id(p):
    return f'p{p.percentile:g}_n{p.duration}_v{p.volume_z:g}_h{p.hold}_a{int(p.acceleration)}'


def neighbors(p):
    result = [p]
    for key, values in (('percentile', (.15, .20, .25)), ('duration', (2, 3, 4)),
                        ('volume_z', (1., 1.5, 2.)), ('acceleration', (True, False))):
        result += [replace(p, **{key: value}) for value in values if value != getattr(p, key)]
    return result


def prepare_metrics(q):
    indicator = Indicators()
    result = []
    previous = None
    for bar in q:
        if previous is not None and bar[0]-previous != STEP:
            indicator = Indicators()
        result.append(indicator.step(bar))
        previous = bar[0]
    return result


def events_for(q, metrics, parameters, end=None):
    engine = Engine(parameters)
    result = []
    for bar, features in zip(q, metrics):
        if end is not None and bar[0]+STEP >= end:
            break
        result.extend(engine.step(bar, features))
    return result


def records(events, base, confirmations, cutoff, regime_times, regimes):
    watch = {event['episode_id']: event for event in events if event['state'] == 'SQUEEZE_WATCH'}
    grouped = {}
    for event in events:
        if event['episode_id'] is not None:
            grouped.setdefault(event['episode_id'], []).append(event)
    result = []
    for event in events:
        signal = event['state'] == 'SQUEEZE_WATCH' or event['state'].startswith('DEVELOPING') or event['cause'] == 'ZERO_HOLD_RESEARCH_CONTROL'
        if not signal or event['timestamp'] < START:
            continue
        period = split(event['timestamp'])
        limit = min(cutoff, TRAIN_END if period == 'TRAIN' else VALID_END if period == 'VALIDATION' else cutoff)
        if event['timestamp'] >= limit:
            continue
        row = dict(event, period=period, year=datetime.fromtimestamp(event['timestamp']/1000, timezone.utc).year)
        regime_index = np.searchsorted(regime_times, event['timestamp'], side='right')-1
        row['regime'] = int(regimes[regime_index]) if regime_index >= 0 else 0
        future = [child for child in grouped.get(event['episode_id'], [])
                  if event['timestamp'] <= child['timestamp'] < limit]
        if event['state'] == 'SQUEEZE_WATCH':
            releases = [child for child in future if child['cause'] in ('FROZEN_RANGE_BREAKOUT', 'BREAKOUT_DIAGNOSTICS_FAILED', 'ZERO_HOLD_RESEARCH_CONTROL')]
            row['time_to_breakout_minutes'] = (releases[0]['timestamp']-event['timestamp'])/60000 if releases else None
        else:
            row['time_to_breakout_minutes'] = 0
        row['time_from_watch_minutes'] = ((event['timestamp']-watch[event['episode_id']]['timestamp'])/60000
                                           if event['episode_id'] in watch else None)
        side = event['direction']
        directions = (1, -1) if side == 0 else (side,)
        row['paths'] = {str(direction): event_outcome(base, event, direction, limit, validated=True) for direction in directions}
        row['lead_minutes'] = {}
        for direction in directions:
            matches = confirmations[direction]
            # Do not call it early if the independent setup already confirmed during compression.
            reference_start = event['squeeze_start_time'] or event['timestamp']
            index = np.searchsorted(matches, reference_start, side='left')
            confirmation = int(matches[index]) if index < len(matches) else None
            if confirmation is not None and confirmation <= event['timestamp']+48*3600000 and confirmation < limit:
                row['lead_minutes'][str(direction)] = (confirmation-event['timestamp'])/60000
            else:
                row['lead_minutes'][str(direction)] = None
        maturity = event['timestamp']+STEP < limit
        row['hold_success'] = (any(child['state'].startswith('CONFIRMING') for child in future) if maturity and side else None)
        row['false_breakout'] = (any(child['state'] == 'RELEASE_FAILED' and child['developing'] is not None for child in future)
                                   if event['timestamp']+5*STEP < limit and side else None)
        row['gate_failed'] = any(child['cause'] == 'BREAKOUT_DIAGNOSTICS_FAILED' for child in future)
        result.append(row)
    return result


def describe(rows):
    directed = [row for row in rows if row['direction'] in (-1, 1)]
    result = dict(squeeze_count=sum(row['state'] == 'SQUEEZE_WATCH' for row in rows),
                  developing_count=len(directed), long_count=sum(row['direction'] == 1 for row in directed),
                  short_count=sum(row['direction'] == -1 for row in directed), horizons={})
    for hours in HORIZONS:
        eligible = [(row, row['paths'][str(row['direction'])][str(hours)]) for row in directed]
        eligible = [(row, path) for row, path in eligible if path is not None]
        paths = [path for _, path in eligible]
        passages = {}
        for target, barrier in PASSAGES:
            key = f'{target:g}/{barrier:g}'
            passages[key] = dict(n=len(paths), favorable_before_adverse=float(np.mean([path['passages'][key]['success'] for path in paths])) if paths else None,
                                  unresolved=sum(path['passages'][key]['resolution'] == 'UNRESOLVED' for path in paths))
        result['horizons'][str(hours)] = dict(n=len(paths), censored=len(directed)-len(paths), passages=passages,
            median_mfe=float(np.median([p['mfe'] for p in paths])) if paths else None,
            median_mae=float(np.median([p['mae'] for p in paths])) if paths else None,
            median_signed_return=float(np.median([p['signed_return'] for p in paths])) if paths else None,
            mean_signed_return=float(np.mean([p['signed_return'] for p in paths])) if paths else None,
            directional_accuracy=float(np.mean([p['signed_return'] > 0 for p in paths])) if paths else None)
    leads = [row['lead_minutes'][str(row['direction'])] for row in directed
             if row['lead_minutes'][str(row['direction'])] is not None]
    result['confirmation_matches'] = len(leads)
    result['confirmation_before_early_count'] = sum(value < 0 for value in leads)
    result['median_lead_minutes_matched_only'] = float(np.median(leads)) if leads else None
    for key in ('hold_success', 'false_breakout'):
        values = [row[key] for row in directed if row[key] is not None]
        result[key+'_rate'] = float(np.mean(values)) if values else None
        result[key+'_n'] = len(values)
    result['squeeze_gate_failed_count'] = sum(row['gate_failed'] for row in rows if row['state'] == 'SQUEEZE_WATCH')
    return result


def select_candidate(training, validation):
    """Arguments contain only pre-2024 aggregates. Hold zero is control, never deployable."""
    if any(row.get('period') != 'TRAIN' for row in training.values()) or any(row.get('period') != 'VALIDATION' for row in validation.values()):
        raise ValueError('TEST_SELECTION_BLOCKED')
    eligible = []
    for key in training:
        train, val = training[key], validation[key]
        if train['parameters']['hold'] != 1:
            continue
        a, b = train['metrics']['horizons']['24'], val['metrics']['horizons']['24']
        if min(a['n'], b['n']) < 30:
            continue
        score = min(a['passages']['0.01/0.01']['favorable_before_adverse'],
                    b['passages']['0.01/0.01']['favorable_before_adverse'])
        eligible.append((score, b['mean_signed_return'], key))
    if not eligible:
        return parameter_id(Parameters()), 'INSUFFICIENT_SELECTION_SAMPLE_BASELINE_FROZEN'
    return max(eligible)[2], 'MAX_MIN_TRAIN_VALIDATION_24H_FIRST_PASSAGE_THEN_VALIDATION_RETURN'


def concentration(rows):
    eligible = [row for row in rows if row['direction'] in (-1, 1)
                and row['paths'][str(row['direction'])]['24'] is not None]
    ordered = sorted(eligible, key=lambda row: row['paths'][str(row['direction'])]['24']['signed_return'], reverse=True)
    return {str(n): describe(ordered[n:]) for n in (0, 1, 3)}


def bootstrap(rows, repetitions=1000):
    eligible = [row for row in rows if row['direction'] in (-1, 1)
                and row['paths'][str(row['direction'])]['24'] is not None]
    groups = {}
    for row in eligible:
        groups.setdefault(row['timestamp']//WEEK, []).append(row['paths'][str(row['direction'])]['24']['passages']['0.01/0.01']['success'])
    if not groups:
        return dict(blocks=0, ci95=None)
    counts = np.array([len(group) for group in groups.values()])
    successes = np.array([sum(group) for group in groups.values()])
    rng = np.random.default_rng(773)
    estimates = []
    for _ in range(repetitions):
        indexes = rng.integers(0, len(groups), len(groups))
        estimates.append(float(successes[indexes].sum()/counts[indexes].sum()))
    return dict(blocks=len(groups), repetitions=repetitions, seed=773,
                ci95=np.quantile(estimates, [.025, .975]).tolist())


def matched_controls(rows, base, q, regimes, cutoff):
    """Random closed timestamps matched by year, side and causal SMA regime, seed994."""
    rng = np.random.default_rng(994)
    times = q[:, 0]+STEP
    years = np.array([datetime.fromtimestamp(stamp/1000, timezone.utc).year for stamp in times])
    pools, result = {}, []
    for event in rows:
        if event['direction'] not in (-1, 1):
            continue
        limit = min(cutoff, TRAIN_END if event['period'] == 'TRAIN' else VALID_END if event['period'] == 'VALIDATION' else cutoff)
        key = (event['year'], event['regime'])
        if key not in pools:
            pools[key] = np.flatnonzero((years == event['year']) & (regimes == event['regime'])
                                        & (times+48*3600000 <= limit) & (times >= START))
        if not len(pools[key]):
            continue
        index = int(rng.choice(pools[key]))
        control = dict(event, timestamp=int(times[index]), price=float(q[index, 4]),
                       event_id='CONTROL:'+str(times[index]), hold_success=None, false_breakout=None,
                       gate_failed=False, lead_minutes={str(event['direction']): None})
        control['paths'] = {str(event['direction']): event_outcome(base, control, event['direction'], limit, validated=True)}
        result.append(control)
    return result


def bootstrap_difference(signals, controls, repetitions=1000):
    groups = {}
    for column, rows in enumerate((signals, controls)):
        for row in rows:
            if row['direction'] not in (-1, 1):
                continue
            path = row['paths'][str(row['direction'])]['24']
            if path is None:
                continue
            group = groups.setdefault(row['timestamp']//WEEK, [0, 0, 0, 0])
            group[2*column] += 1
            group[2*column+1] += int(path['passages']['0.01/0.01']['success'])
    if not groups:
        return dict(blocks=0, ci95=None)
    totals = np.asarray(list(groups.values()))
    rng = np.random.default_rng(221)
    differences = []
    for _ in range(repetitions):
        sample = totals[rng.integers(0, len(totals), len(totals))].sum(axis=0)
        if sample[0] and sample[2]:
            differences.append(sample[1]/sample[0]-sample[3]/sample[2])
    return dict(blocks=len(groups), seed=221, repetitions=repetitions,
                ci95=np.quantile(differences, [.025, .975]).tolist() if differences else None)


def incident_diagnostic(events, confirmations, start=None, end=None):
    if start is None or end is None:
        return dict(status='UNIDENTIFIED_DATE_NOT_PROVIDED', price_description='82.6k -> 84k',
                    used_for_selection=False, reason='Price endpoints do not uniquely identify an incident; no cherry-picked match.')
    subset = [event for event in events if start-4*3600000 <= event['timestamp'] <= end]
    return dict(status='DATED_SANITY_CHECK_ONLY', used_for_selection=False, start=start, end=end,
                events=subset, confirming_times={str(side): values[(values >= start) & (values <= end)].tolist()
                                                  for side, values in confirmations.items()})


def load_frozen(path):
    selection = json.loads(Path(path).read_text(encoding='utf-8'))
    contents = {key: value for key, value in selection.items() if key != 'sha256'}
    checksum = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
    if (checksum != selection['sha256'] or selection['selection_periods'] != ['TRAIN', 'VALIDATION']
            or selection['test_selection'] is not False or selection['parameters']['hold'] != 1):
        raise ValueError('FROZEN_SELECTION_INVALID')
    return selection


def run(args):
    cache = Path(args.cache)
    cutoff = int(datetime.fromisoformat(args.as_of).timestamp()*1000)//300000*300000
    if args.download:
        base, sources = download(cache, cutoff)
    else:
        base = np.load(cache/'spot_5m.npz')['bars']
        manifest = json.loads((cache/'manifest.json').read_text(encoding='utf-8'))
        if manifest['as_of'] != cutoff:
            raise ValueError('CACHE_AS_OF_MISMATCH')
        sources = manifest['sources']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    q = aggregate(base, STEP)
    metrics = prepare_metrics(q)
    data_sha = hashlib.sha256(base.astype('<f8').tobytes()).hexdigest()
    if (OUTPUT/'data_manifest.json').exists():
        recorded = json.loads((OUTPUT/'data_manifest.json').read_text(encoding='utf-8'))
        if recorded['canonical_array_sha256'] != data_sha or recorded['as_of'] != cutoff:
            raise ValueError('DATASET_CHANGED_FROZEN_RESEARCH_STOPPED')
    reference_cache = cache/('reference-'+data_sha[:16]+'.npz')
    if reference_cache.exists():
        reference = np.load(reference_cache)
        confirmations, regimes = {1: reference['long'], -1: reference['short']}, reference['regimes']
    else:
        print('CALCULATING_CAUSAL_MANUAL_REFERENCE', flush=True)
        confirmations, regimes = manual_reference(base, q)
        np.savez_compressed(reference_cache, long=confirmations[1], short=confirmations[-1], regimes=regimes)
    frozen_path = OUTPUT/'frozen_parameters.json'
    if frozen_path.exists():
        selection = load_frozen(frozen_path)
        selected_id, selected = selection['selected_id'], Parameters(**selection['parameters'])
        frozen_candidates = {parameter_id(p): p for p in [Parameters(**value) for value in selection['frozen_candidates']]}
        print('USING_FROZEN_SELECTION_NO_RESELECTION', flush=True)
    else:
        training, validation = {}, {}
        for parameters in candidate_grid():
            key = parameter_id(parameters)
            print('TRAIN_VALIDATION '+key, flush=True)
            events = events_for(q, metrics, parameters, VALID_END)
            rows = records(events, base[base[:, 0] < VALID_END], confirmations, VALID_END, q[:, 0]+STEP, regimes)
            for period, target in (('TRAIN', training), ('VALIDATION', validation)):
                target[key] = dict(period=period, parameters=asdict(parameters),
                                   metrics=describe([row for row in rows if row['period'] == period]))
        selected_id, rule = select_candidate(training, validation)
        selected = Parameters(**training[selected_id]['parameters'])
        frozen_candidates = {parameter_id(p): p for p in candidate_grid()+neighbors(selected)}
        selection = dict(parameters=asdict(selected), selected_id=selected_id, selection_rule=rule,
                         selection_periods=['TRAIN', 'VALIDATION'], test_selection=False,
                         initial_candidates=len(candidate_grid()), frozen_candidates=[asdict(p) for p in frozen_candidates.values()])
        selection['sha256'] = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
        frozen_path.write_text(json.dumps(selection, indent=2), encoding='utf-8')
    # Above write is the immutable selection boundary; TEST results never feed back into it.
    all_results, selected_rows, selected_events = {}, None, None
    for key, parameters in frozen_candidates.items():
        print('FROZEN_EVALUATION '+key, flush=True)
        events = events_for(q, metrics, parameters)
        rows = records(events, base, confirmations, cutoff, q[:, 0]+STEP, regimes)
        all_results[key] = dict(parameters=asdict(parameters),
            periods={period: describe([row for row in rows if row['period'] == period]) for period in ('TRAIN', 'VALIDATION', 'TEST')})
        if key == selected_id:
            selected_rows, selected_events = rows, events
    test = [row for row in selected_rows if row['period'] == 'TEST']
    by_year = {str(year): describe([row for row in test if row['year'] == year]) for year in sorted({row['year'] for row in test})}
    by_regime = {str(regime): describe([row for row in test if row['regime'] == regime]) for regime in (-1, 0, 1)}
    by_side = {str(side): describe([row for row in test if row['direction'] == side]) for side in (1, -1)}
    headline = all_results[selected_id]['periods']['TEST']
    controls = matched_controls(test, base, q, regimes, cutoff)
    control_summary = describe(controls)
    difference = bootstrap_difference(test, controls)
    boot = bootstrap(test)
    neighbor_ids = [parameter_id(p) for p in neighbors(selected)]
    neighbor_probs = [all_results[key]['periods']['TEST']['horizons']['24']['passages']['0.01/0.01']['favorable_before_adverse'] for key in neighbor_ids]
    neighbor_probs = [value for value in neighbor_probs if value is not None]
    p = headline['horizons']['24']['passages']['0.01/0.01']['favorable_before_adverse']
    concentrated = concentration(test)
    control_p = control_summary['horizons']['24']['passages']['0.01/0.01']['favorable_before_adverse']
    positive = p is not None and control_p is not None and p > max(.5, control_p) and headline['horizons']['24']['mean_signed_return'] > 0
    stable = bool(neighbor_probs) and min(neighbor_probs) > max(.5, control_p or .5)
    robust = (positive and stable and headline['developing_count'] >= 200 and boot['ci95'][0] > .5
              and p-control_p >= .05 and difference['ci95'] is not None and difference['ci95'][0] > 0
              and concentrated['3']['horizons']['24']['mean_signed_return'] > 0
              and headline['false_breakout_rate'] is not None and headline['false_breakout_rate'] <= .35)
    conclusion = 'ROBUST' if robust else 'PROMISING-BUT-FRAGILE' if positive else 'NO EDGE'
    start = int(datetime.fromisoformat(args.incident_start).timestamp()*1000) if args.incident_start else None
    end = int(datetime.fromisoformat(args.incident_end).timestamp()*1000) if args.incident_end else None
    result = dict(conclusion=conclusion, selected=selection, as_of=cutoff, source='BINANCE_BTCUSDT_SPOT',
                  rows_5m=len(base), rows_15m=len(q), gap_count=int(np.count_nonzero(np.diff(base[:, 0]) != 300000)),
                  candidates=all_results, yearly_test=by_year, regime_test=by_regime, side_test=by_side,
                  concentration_test=concentrated, bootstrap_test=boot, neighbor_ids=neighbor_ids,
                  matched_control_test=control_summary, bootstrap_difference_test=difference,
                  incident=incident_diagnostic(selected_events, confirmations, start, end),
                  manual_reference_confirmation_count={str(side): len(values) for side, values in confirmations.items()})
    (OUTPUT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    (OUTPUT/'data_manifest.json').write_text(json.dumps(dict(as_of=cutoff, sources=sources,
          source_documentation='https://github.com/binance/binance-public-data', rows=len(base),
          first_timestamp=int(base[0, 0]), last_timestamp=int(base[-1, 0]),
          canonical_array_sha256=data_sha), indent=2), encoding='utf-8')
    with (OUTPUT/'selected_events.jsonl.gz').open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='\n') as stream:
                for row in selected_rows:
                    stream.write(json.dumps(row, allow_nan=False)+'\n')
    report(result)
    print(json.dumps({'conclusion': conclusion, 'selected': selected_id, 'TEST': headline}), flush=True)


def report(result):
    selected = result['selected']['selected_id']
    summaries = result['candidates'][selected]['periods']
    lines = ['# I-GOD EARLY BREAKOUT SHADOW', '', '**'+result['conclusion']+'**', '',
        'Public event research, not a traded strategy. No entry permission, private account API, execution or Guardian risk dependency.', '',
        f"Selected: `{selected}`. Nine initial one-factor candidates; neighbors frozen before TEST, {len(result['candidates'])} total evaluations.",
        f"BTCUSDT spot: {result['rows_5m']:,} closed 5m rows, {result['rows_15m']:,} complete 15m rows; {result['gap_count']} historical gaps. As of {datetime.fromtimestamp(result['as_of']/1000, timezone.utc).isoformat()}.", '',
        '| Period | Squeezes | Developing | +1% before -1%, 24h | +2% before -1%, 24h | False breakout | Hold | Matched lead median |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(value, percent=False):
        return 'n/a' if value is None else f'{value:.1%}' if percent else f'{value:.1f}'
    def returns(value):
        return 'n/a' if value is None else f'{value:.4%}'
    for period, summary in summaries.items():
        probabilities = summary['horizons']['24']['passages']
        lines.append(f"| {period} | {summary['squeeze_count']} | {summary['developing_count']} | {fmt(probabilities['0.01/0.01']['favorable_before_adverse'], True)} (n={summary['horizons']['24']['n']}) | {fmt(probabilities['0.02/0.01']['favorable_before_adverse'], True)} | {fmt(summary['false_breakout_rate'], True)} | {fmt(summary['hold_success_rate'], True)} | {fmt(summary['median_lead_minutes_matched_only'])} min (matches={summary['confirmation_matches']}) |")
    lines += ['', '## Frozen methodology', '',
        'ATR14 matches main.py first-TR RMA initialization. ATR percentile is count(prior 100 ATR <= current ATR)/100; ties use inclusive rank, current observation excluded. Volume z matches main.py rolling20 mean/sample std including current closed volume; zero-volume windows yield zero. MACD is EMA12/26 with EMA9 signal, acceleration the second histogram difference.',
        'A squeeze is consecutive qualifying closed candles; range uses only its episode candles. A breakout checks the prior range before considering the current candle for extension. After compression ends, the frozen range expires after four closed candles. Qualifying release needs volume and optional signed acceleration; it holds on a later closed candle, fails on return to/inside boundary, and confirmed releases expire after four more candles. Gate failures are distinct from false breakouts of qualified developing events. Fresh episodes are required before direction changes.',
        'Selection uses only TRAIN 2020–2021 and VALIDATION 2022–2023, maximizing the lower 24h +1/-1 favorable-first frequency (minimum 30 developed events each), then validation mean signed close return. Hold=0 is diagnostic only and cannot be selected or used live. The selected parameters and all diagnostics are written before TEST evaluation. TEST begins 2024. No parameter change follows TEST. Neighbors are one-factor diagnostics, not another selection pass.',
        'Reference price is signal close. Descriptive paths start with the next 5m candle; no executions, fees or PnL model. Same 5m candle hitting both barriers is adverse first. Unresolved observations are failures for favorable-first frequency but counted separately. Every horizon has its own complete-path denominator; missing/gapped paths and split-crossing horizons are censored. All signals can overlap; block bootstrap resamples seven-day event groups, seed773, 1000 repetitions.',
        'Squeeze has no direction. Its LONG/SHORT paths in the event artifact are hypothetical diagnostics, not directional accuracy. Developing LONG/SHORT are evaluated separately. Lead compares with the first independently GOOD Manual Copilot setup since compression began, at most 48h after signal. Negative lead means that system confirmed before the early alert; unmatched events are explicitly excluded from the conditional median and counted.',
        'Historical Manual Copilot comparison reuses its pure LOW/RSI27/EMA4 causal rolling 3000-cluster code and frozen SMA200/flow/confirmed pivot/entry-quality logic. It reproduces closed-price confirmation, not live Bitunix mark or venue volatility. Spot native timeframe candles are reconstructed only from complete 5m groups; missing groups conservatively invalidate live-sized lookbacks. RSI is seeded from full available causal segment history, which can differ slightly from the live 3200-candle initialization; this is a rule reproduction, not claimed perfect replay of a deployed alert.', '',
        '## TEST neighbors', '', '| Parameters | n | +1/-1, 24h | Signed close return mean, 24h |', '|---|---:|---:|---:|']
    for key in result['neighbor_ids']:
        horizon = result['candidates'][key]['periods']['TEST']['horizons']['24']
        lines.append(f"| `{key}` | {horizon['n']} | {fmt(horizon['passages']['0.01/0.01']['favorable_before_adverse'], True)} | {returns(horizon['mean_signed_return'])} |")
    pct_neighbors = [key for key in result['neighbor_ids']
                    if all(result['candidates'][key]['parameters'][name] == result['selected']['parameters'][name]
                           for name in ('duration', 'volume_z', 'hold', 'acceleration'))]
    lines += ['', 'ATR 15/20/25% at the selected other settings: ' + '; '.join(
        key + ' = ' + fmt(result['candidates'][key]['periods']['TEST']['horizons']['24']['passages']['0.01/0.01']['favorable_before_adverse'], True)
        for key in pct_neighbors) + '. No post-TEST parameter change.']
    lines += ['', '## TEST by year, direction and regime', '',
              '| Slice | Developing | 24h n | +1/-1 24h | +2/-1 24h | False breakout | Median matched lead |',
              '|---|---:|---:|---:|---:|---:|---:|']
    slices = [('YEAR '+key, value) for key, value in result['yearly_test'].items()]
    slices += [('LONG' if key == '1' else 'SHORT', value) for key, value in result['side_test'].items()]
    slices += [('REGIME '+key, value) for key, value in result['regime_test'].items()]
    for label, summary in slices:
        horizon = summary['horizons']['24']
        lines.append(f"| {label} | {summary['developing_count']} | {horizon['n']} | {fmt(horizon['passages']['0.01/0.01']['favorable_before_adverse'], True)} | {fmt(horizon['passages']['0.02/0.01']['favorable_before_adverse'], True)} | {fmt(summary['false_breakout_rate'], True)} | {fmt(summary['median_lead_minutes_matched_only'])} min (n={summary['confirmation_matches']}) |")
    lines += ['', '## Concentration / uncertainty', '',
        'Without best/top3 is ranked by 24h directional close return, not MFE or a realized trade. Full distributions, both directions, all five target/barrier pairs and 1/4/12/24/48h MFE/MAE are in results.json and selected_events.jsonl.gz.',
        'Bootstrap 95% interval for TEST +1/-1 (24h): '+str(result['bootstrap_test']['ci95'])+'.',
        'Matched random closed-timestamp control uses the same year, causal SMA regime and signal side, seed994. TEST control +1/-1 24h: '+fmt(result['matched_control_test']['horizons']['24']['passages']['0.01/0.01']['favorable_before_adverse'], True)+'. Seven-day joint block bootstrap CI95 for signal minus control: '+str(result['bootstrap_difference_test']['ci95'])+'.',
        'Predeclared ROBUST requires TEST frequency above 50% and matched control, a >=5 percentage-point control improvement with block CI lower bound >0, positive mean signed return, every neighbor above 50% and control, at least 200 developed TEST events, bootstrap lower bound above 50%, positive return without top3 and false-breakout rate <=35%. Otherwise positive evidence is PROMISING-BUT-FRAGILE, or NO EDGE. These are research labels, not profitability claims or corrected significance after selection.', '',
        '| Removed events | n | Mean signed close return 24h | +1/-1 24h |', '|---|---:|---:|---:|']
    for removed, summary in result['concentration_test'].items():
        horizon = summary['horizons']['24']
        lines.append(f"| {removed} | {horizon['n']} | {returns(horizon['mean_signed_return'])} | {fmt(horizon['passages']['0.01/0.01']['favorable_before_adverse'], True)} |")
    lines += ['', '## Incident 82.6k → 84k', '', json.dumps(result['incident'], ensure_ascii=False), '',
        'The motivating price move is excluded from parameter selection. A precise dated window is required before matching it; no arbitrary historical price match is substituted.', '',
        '## Reproduction', '',
        f"`python -m research.early_breakout_data --as-of {datetime.fromtimestamp(result['as_of']/1000, timezone.utc).isoformat()}`",
        f"`python -m research.early_breakout_research --as-of {datetime.fromtimestamp(result['as_of']/1000, timezone.utc).isoformat()}`",
        'Archives are outside Git. data_manifest.json stores URLs, archive SHA256 checksums, row counts, timestamps and REST parameters; canonical array checksum prevents silent data changes. Binance [official public schema/checksums](https://github.com/binance/binance-public-data) documents the 2025 spot microsecond timestamp switch. No earlier research artifacts are changed.']
    (OUTPUT/'EARLY_BREAKOUT_RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--cache', default='research/cache/early_breakout')
    parser.add_argument('--incident-start')
    parser.add_argument('--incident-end')
    run(parser.parse_args())
