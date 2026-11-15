"""Offline predeclared three-pattern study. No downloads or account calls."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from research.confluence_1h.data import load, stamp, iso
from .detect import features, detect, PATTERNS, STRATA, HOUR
from .outcomes import outcome
from .inference import assess, holm, required_n

HERE = Path(__file__).resolve().parent
DAY = 24*HOUR


def clean(value):
    if isinstance(value, dict):
        return {k:clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(path, value):
    path.write_text(json.dumps(clean(value), indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline=''); w = csv.DictWriter(stream, keys, lineterminator='\n'); w.writeheader()
    for row in rows:
        row = clean(row)
        w.writerow({k:json.dumps(v, sort_keys=True, separators=(',',':')) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    raw = stream.getvalue().encode('utf-8')
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def intervals(bars):
    def locate(s): return int(np.searchsorted(bars[:,0], stamp(s)))
    return dict(DEVELOPMENT=(locate('2022-11-01T00:00:00Z'), locate('2025-01-01T00:00:00Z')-24),
                EVALUATION=(locate('2025-01-01T00:00:00Z')+24, locate('2026-10-01T00:00:00Z')-24))


def match_controls(bars, f, events, start, end, seed=20261115):
    """Match time/side/closed regime/volatility, never returns or direction outcomes."""
    a = bars
    months = np.array([iso(t)[:7] for t in a[:,0]])
    rank = f['vol_rank']; regime = f['regime4h']
    buckets = np.minimum(2, np.floor(3*np.nan_to_num(rank, nan=-1))).astype(int)
    eligible = np.arange(start, max(start, end-25))
    eligible = eligible[np.isfinite(regime[eligible]) & np.isfinite(rank[eligible]) & (f['atr'][eligible] > 0)]
    # Exclude overlapping real episodes using only timing, not their outcomes.
    forbidden = np.zeros(len(a), bool)
    for event in events:
        i = event['i']; forbidden[max(0,i-24):i+25] = True
    eligible = eligible[~forbidden[eligible]]
    used = []
    rng = np.random.default_rng(seed)
    out = []
    for event in sorted(events, key=lambda e:e['i']):
        i = event['i']
        pool = eligible[(months[eligible] == months[i]) & (regime[eligible] == regime[i]) & (buckets[eligible] == buckets[i])]
        pool = np.array([int(k) for k in pool if all(abs(int(k)-j) >= 25 for j in used)], int)
        selected = []
        for k in rng.permutation(pool):
            if all(abs(int(k)-j) >= 25 for j in selected):
                selected.append(int(k))
            if len(selected) == 3:
                break
        if len(selected) == 3:
            used.extend(selected)
            out.append(dict(event_id=event['event_id'], i=i, side=event['side'], controls=selected, matched=True,
                            month=months[i], regime=int(regime[i]), vol_bucket=int(buckets[i])))
        else:
            out.append(dict(event_id=event['event_id'], i=i, side=event['side'], controls=[], matched=False,
                            reason='MATCH_STRATUM_INSUFFICIENT_NO_FALLBACK'))
    return out


def evaluate(cache, out):
    p = json.loads((HERE/'protocol.json').read_text())
    a, funding, manifest = load(cache)
    if hashlib.sha256((cache/'validated_market.npz').read_bytes()).hexdigest() != p['data']['npz_sha256']:
        raise ValueError('FROZEN_DATASET_MISMATCH')
    out.mkdir(parents=True, exist_ok=True)
    f = features(a); events, audit = detect(a, f); windows = intervals(a)
    cells = []; all_outcomes = []; control_rows = []; power = []; secondary = []; summaries = []
    cache_outcomes = {}
    def get(i, side, h):
        key = (int(i), int(side), h)
        if key not in cache_outcomes:
            cache_outcomes[key] = outcome(a, funding, i, side, f['atr'][i], h)
        return cache_outcomes[key]
    # Conservative fallback variance uses DEVELOPMENT ONLY, fixed before evaluation inference.
    lo, hi = windows['DEVELOPMENT']
    series = [get(i, side, 12)['net_fraction'] for side in (1,-1) for i in range(lo,hi-25) if get(i,side,12)]
    fallback = np.sqrt(2)*float(np.std(series, ddof=1))
    for pattern in PATTERNS:
        for side in (1,-1):
            sigma = fallback
            for stratum in STRATA:
                for stage, (start, end) in windows.items():
                    subset = [e for e in events if e['pattern'] == pattern and e['side'] == side and stratum in e['strata'] and start <= e['i'] < end-25]
                    matched = match_controls(a, f, subset, start, end)
                    pairs = {m['event_id']:m for m in matched}
                    for e in subset:
                        for h in (4,12,24):
                            o = get(e['i'], side, h)
                            all_outcomes.append(dict(stage=stage, pattern=pattern, side=side, stratum=stratum,
                                                     event_id=e['event_id'], signal_available=iso(e['available_at']), **o))
                    for h in (4,12,24):
                        diffs, days, net, net_atr, obs = [], [], [], [], []
                        for e in subset:
                            o = get(e['i'], side, h); m = pairs[e['event_id']]
                            if not m['matched']:
                                continue
                            controls = [get(i,side,h) for i in m['controls']]
                            if not all(controls):
                                raise ValueError('CONTROL_OUTCOME_UNAVAILABLE')
                            delta = o['net_fraction']-float(np.mean([v['net_fraction'] for v in controls]))
                            diffs.append(delta); days.append(int(a[e['i'],0]//DAY))
                            net.append(o['net_fraction']); net_atr.append(o['net_atr'])
                            obs.append(dict(event_id=e['event_id'], net=o['net_fraction'], excess=delta, year=iso(a[e['i'],0])[:4]))
                            for j,v in zip(m['controls'],controls):
                                control_rows.append(dict(stage=stage, pattern=pattern, side=side, stratum=stratum, h=h,
                                                         event_id=e['event_id'], control_i=j, control_available=iso(a[j,0]+HOUR),
                                                         matched_regime=m['regime'], matched_vol_bucket=m['vol_bucket'], control_side=side, **v))
                        if stage == 'DEVELOPMENT' and stratum == 'Q75' and h == 12:
                            sigma = float(np.std(diffs, ddof=1)) if len(diffs) >= 2 else fallback
                            power.append(dict(pattern=pattern, side=side, sigma=sigma, paired_development_n=len(diffs),
                                              fallback_used=len(diffs)<2, minimum_effect=.001, required_effective_n=required_n(sigma)))
                        minimum = required_n(sigma)
                        stat = assess(diffs, days, int(a[start,0]//DAY), int(a[end-1,0]//DAY), minimum)
                        row = dict(stage=stage, pattern=pattern, side=side, stratum=stratum, horizon=h,
                                   valid_episodes=len(subset), matched=len(diffs), unmatched=len(subset)-len(diffs),
                                   net_mean=float(np.mean(net)) if net else None,
                                   net_median=float(np.median(net)) if net else None,
                                   net_atr_mean=float(np.mean(net_atr)) if net_atr else None, **stat)
                        summaries.append(row)
                        if stage == 'EVALUATION' and stratum == 'Q75' and h == 12:
                            cells.append(row)
                        if stratum == 'Q75' and h == 12:
                            ordered = sorted(obs, key=lambda r:r['excess'], reverse=True)
                            for remove in (0,1,3):
                                kept = ordered[remove:]
                                secondary.append(dict(stage=stage, pattern=pattern, side=side, kind='EX_BEST', remove=remove,
                                                      n=len(kept), net_mean=float(np.mean([r['net'] for r in kept])) if kept else None,
                                                      excess_mean=float(np.mean([r['excess'] for r in kept])) if kept else None))
                    for m in matched:
                        if not m['matched']:
                            control_rows.append(dict(stage=stage,pattern=pattern,side=side,stratum=stratum,**m))
    if len(cells) != 6:
        raise ValueError('PRIMARY_SIX_CELL_FAMILY_MISSING')
    adjusted = holm([r['p_for_holm'] for r in cells])
    for row,p_adj in zip(cells,adjusted):
        row['holm_adjusted_p'] = p_adj
        row['classification'] = 'NO TESTABLE' if not row['testable'] else ('PROMISING FOR FORWARD VALIDATION' if p_adj <= .05 and row['mean'] >= .001 and row['net_mean'] > 0 else 'INCONCLUSO')
    annual = []
    for stage in windows:
        for pattern in PATTERNS:
            for side in (1,-1):
                rows = [r for r in all_outcomes if r['stage']==stage and r['pattern']==pattern and r['side']==side and r['stratum']=='Q75' and r['hours']==12]
                for month in sorted(set(r['signal_available'][:7] for r in rows)):
                    rr = [r for r in rows if r['signal_available'][:7]==month]
                    annual.append(dict(stage=stage,pattern=pattern,side=side,month=month,n=len(rr),net_mean=np.mean([r['net_fraction'] for r in rr])))
    context = []
    for e in events:
        if e['pattern'] != PATTERNS[2] or 'Q75' not in e['strata']:
            continue
        stage = next((s for s,(lo,hi) in windows.items() if lo<=e['i']<hi-25),None)
        if stage:
            context.append(dict(event_id=e['event_id'],stage=stage,side=e['side'],four_h=e['four_h'],daily=e['daily'],
                                aligned=bool(e['four_h']==e['side'] and e['daily']==e['side']),**get(e['i'],e['side'],12)))
    result = dict(protocol_version=p['version'], protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest(),
                  data_sha256=p['data']['npz_sha256'], data_rows=len(a), raw_sources_checked=len(manifest['sources']) if 'sources' in manifest else len(manifest.get('files',[])),
                  no_virgin_holdout=True, forward_running=False, historical_events=len(events),
                  primary=cells, power=power, conclusion='NO TESTABLE' if not any(r['testable'] for r in cells) else 'INCONCLUSO',
                  phase2_management_backtest='NOT_RUN_PENDING_PHASE1_AND_SEPARATE_STOP_SPEC',
                  historical_bitunix_liquidation='NOT_VERIFIED_NO_EXACT_SIMULATION',
                  october_november_outcomes_evaluated=False)
    write_json(out/'results.json',result); write_json(out/'power_frozen_from_development.json',power)
    write_json(out/'data_manifest.json',manifest)
    for name, rows in [('episodes.csv.gz',events),('event_audit.csv.gz',audit),('outcomes.csv.gz',all_outcomes),
                       ('matched_controls.csv.gz',control_rows),('comparisons.csv',summaries),('monthly.csv',annual),
                       ('sensitivity_ex_best.csv',secondary),('p3_context_secondary.csv',context)]:
        write_csv(out/name,rows)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--out',type=Path,default=HERE/'artifacts')
    args=parser.parse_args();r=evaluate(args.cache,args.out)
    print(json.dumps(clean(dict(primary=r['primary'],conclusion=r['conclusion'])),indent=2))
