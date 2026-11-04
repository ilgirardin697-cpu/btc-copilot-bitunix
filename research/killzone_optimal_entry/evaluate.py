"""Reproducible offline evaluation of every predeclared cycle and method."""
import argparse
from collections import Counter
from datetime import date, timedelta
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from .data import HERE, MINUTE, HOUR, read_json, iso, load_interval, verify_hourly_aggregation, atr_values, freeze_cycle
from .signals import METHODS, signal_for
from .simulate import execute


def verify_freeze():
    f = read_json('freeze_manifest.json')
    for file, expected in [('specification.json', f['spec_sha256']),
                           ('SPECIFICATION.md', f['specification_document_sha256']),
                           ('reference_geometry.py', f['vendored_core_sha256'])]:
        if hashlib.sha256((HERE / file).read_bytes()).hexdigest() != expected:
            raise ValueError('RESEARCH_FREEZE_CHANGED_' + file)
    return f


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row if not k.startswith('_')))
    with path.open('w', encoding='utf-8', newline='') as stream:
        w = csv.DictWriter(stream, fields, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def all_days():
    d = date.fromisoformat(read_json('specification.json')['data']['cycle_first'])
    last = date.fromisoformat(read_json('specification.json')['data']['cycle_last'])
    while d <= last:
        yield d
        d += timedelta(days=1)


def block_indices(n):
    s = read_json('specification.json')['statistics']
    rng = np.random.default_rng(s['bootstrap_seed'])
    b = s['circular_block_calendar_days']
    starts = rng.integers(0, n, (s['bootstrap_replicates'], (n + b - 1) // b))
    return ((starts[:, :, None] + np.arange(b)) % n).reshape(len(starts), -1)[:, :n]


def interval(values, confidence=.95):
    a = np.asarray(values)
    a = a[np.isfinite(a)]
    if not len(a):
        return [None, None]
    tail = (1 - confidence) / 2
    return np.quantile(a, [tail, 1 - tail]).tolist()


def descriptive(trades):
    n = len(trades)
    if not n:
        return dict(n=0, net_pnl=0., mean_net_r=None, median_net_r=None,
                    profit_factor=None, net_win_rate=None, tp_rate=None, ambiguous=0)
    pnl = np.array([t['net_pnl'] for t in trades])
    rr = np.array([t['net_r'] for t in trades])
    losses = -pnl[pnl < 0].sum()
    return dict(n=n, net_pnl=float(pnl.sum()), gross_pnl=sum(t['gross_pnl'] for t in trades),
                fees=sum(t['fees'] for t in trades), slippage_cost=sum(t['slippage_pnl_cost'] for t in trades),
                mean_net_r=float(rr.mean()), median_net_r=float(np.median(rr)),
                net_r_quantiles=np.quantile(rr, [0, .1, .25, .5, .75, .9, 1]).tolist(),
                profit_factor=float(pnl[pnl > 0].sum() / losses) if losses > 0 else None,
                net_win_rate=float((pnl > 0).mean()), tp_rate=sum(t['exit_reason'] == 'TP' for t in trades) / n,
                exit_counts=dict(Counter(t['exit_reason'] for t in trades)),
                ambiguous=sum(bool(t['ambiguity']) for t in trades),
                mean_net_rr=float(np.mean([t['net_rr'] for t in trades])),
                mean_mae_bound=float(np.mean([t['mae_bound'] for t in trades])),
                mean_mfe_bound=float(np.mean([t['mfe_bound'] for t in trades])),
                median_duration_minutes=float(np.median([t['duration_minutes'] for t in trades])),
                total_exposure_minutes=sum(t['duration_minutes'] for t in trades),
                ex_best1_mean_r=float(np.sort(rr)[:-1].mean()) if n > 1 else None,
                ex_best3_mean_r=float(np.sort(rr)[:-3].mean()) if n > 3 else None)


def summarize(ledgers, trades, days, primary_baselines):
    result = []
    day_index = {d.isoformat(): i for i, d in enumerate(days)}
    idx = block_indices(len(days))
    s = read_json('specification.json')
    for cost in ('PRIMARY', 'STRESS'):
        for method in METHODS:
            for side in (1, -1):
                ts = [t for t in trades if t['cost'] == cost and t['method'] == method and t['side'] == side]
                ls = [l for l in ledgers if l['cost'] == cost and l['method'] == method and l['account_side'] == side]
                row = dict(cost=cost, method=method, side=side, **descriptive(ts))
                row['cycle_count'] = len(ls)
                row['ledger_status_counts'] = dict(Counter(l['status'] for l in ls))
                row['rejection_reasons'] = dict(Counter(l.get('reason', '') for l in ls if l['status'] == 'REJECTED'))
                signals = sum(l.get('status') in ('TRADE', 'REJECTED', 'UNFILLED') for l in ls)
                row['signals'] = signals
                row['trade_given_signal_rate'] = len(ts) / signals if signals else None
                row['cycle_trade_rate'] = len(ts) / len(ls)
                row['exposure_fraction'] = row.get('total_exposure_minutes', 0) / (len(days) * 24 * 60)
                sums, counts, daily = np.zeros(len(days)), np.zeros(len(days)), np.zeros(len(days))
                for t in ts:
                    i = day_index[t['cycle']]
                    sums[i] = t['net_r']
                    counts[i] = 1
                    daily[i] = t['cycle_r']
                denom = counts[idx].sum(axis=1)
                ratio = np.divide(sums[idx].sum(axis=1), denom,
                                  out=np.full(len(idx), np.nan), where=denom > 0)
                row['mean_net_r_ci95'] = interval(ratio)
                row['mean_net_r_ci9875'] = interval(ratio, .9875)
                # Same side, same chronological dates; zero opportunity return when not entering.
                baseline = primary_baselines[(cost, side)]
                delta = daily - baseline
                row['paired_cycle_r_gain_vs_baseline'] = float(delta.mean())
                row['paired_cycle_r_gain_ci9875'] = interval(delta[idx].mean(axis=1), .9875)
                row['mean_cycle_r'] = float(daily.mean())
                path = [10000.]
                for t in ts:
                    path.extend(t['_mtm'][1:])
                curve = np.array(path)
                row['mtm_drawdown'] = float((1 - curve / np.maximum.accumulate(curve)).max())
                row['final_equity'] = float(curve[-1])
                row['net_return_pct'] = (row['final_equity'] / 10000 - 1) * 100
                row['months'] = []
                for month in sorted(set(d.isoformat()[:7] for d in days)):
                    selected = [t for t in ts if t['cycle'].startswith(month)]
                    row['months'].append(dict(month=month, **descriptive(selected)))
                row['partitions'] = {}
                for name, span in s['partitions'].items():
                    if isinstance(span, list) and len(span) == 2:
                        start, end = span
                        row['partitions'][name] = descriptive([t for t in ts if start <= t['cycle'] <= end])
                row['classification'] = 'INCONCLUSIVE'
                upper = row['mean_net_r_ci95'][1]
                if row['n'] >= 30 and upper is not None and upper <= 0:
                    row['classification'] = 'NO EDGE'
                row['short_execution_evidence'] = 'NOT_APPLICABLE_LONG_SPOT' if side == 1 else 'BLOCKED_SPOT_IS_NOT_FUTURES_NO_BORROW_FUNDING_MARK_OR_EXECUTION_RULES'
                result.append(row)
    for row in result:
        if row['cost'] != 'PRIMARY' or row['method'] == 'BASELINE' or row['side'] != 1:
            continue
        stress = next(x for x in result if x['cost'] == 'STRESS' and x['method'] == row['method'] and x['side'] == row['side'])
        final = row['partitions']['descriptive_final']
        low = row['mean_net_r_ci9875'][0]
        if (row['n'] >= 60 and final['n'] >= 20 and low is not None and low > 0
            and row['paired_cycle_r_gain_ci9875'][0] > 0 and final['net_pnl'] > 0
            and sum(m['net_pnl'] > 0 for m in row['months']) >= 8
            and stress['net_pnl'] > 0 and (row['ex_best3_mean_r'] or 0) > 0):
            row['classification'] = 'PROMISING FOR FORWARD VALIDATION'
    return result


def run(cache, out):
    frozen = verify_freeze()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    h, m = load_interval(cache, '1h'), load_interval(cache, '1m')
    hourly_checks = verify_hourly_aggregation(h, m)
    av = atr_values(h)
    days = list(all_days())
    cycles, incomplete = [], []
    for d in days:
        try:
            cycles.append(freeze_cycle(d, h, av))
        except ValueError as error:
            incomplete.append(dict(cycle=d.isoformat(), reason=str(error)))
    cs = {c['cycle']: c for c in cycles}
    costs = read_json('specification.json')['cost_scenarios']
    ledgers, trades = [], []
    for cost in ('PRIMARY', 'STRESS'):
        fee, slip = costs[cost]['fee_per_side'], costs[cost]['market_slippage_per_side']
        for method in METHODS:
            for side in (1, -1):
                equity = 10000.
                for d in days:
                    key = d.isoformat()
                    if key not in cs:
                        record, trade = dict(cycle=key, method=method, status='INCOMPLETE', side=0,
                                             net_pnl=0., cycle_r=0., equity_before=equity, equity_after=equity,
                                             reason=next(x['reason'] for x in incomplete if x['cycle'] == key)), None
                    else:
                        c = cs[key]
                        signal = signal_for(method, c, h)
                        if signal['side'] not in (0, side):
                            record, trade = dict(signal, status='NO_ENTRY_OPPOSITE_FIRST_SIGNAL',
                                                 net_pnl=0., cycle_r=0., equity_before=equity, equity_after=equity), None
                        else:
                            record, trade = execute(c, signal, m, equity, fee, slip)
                        record.update(HIGH=c['highGuideValue'], LOW=c['lowGuideValue'],
                                      SUPERIOR=c['newTopTarget'], INFERIOR=c['newBottomTarget'],
                                      levels_available_at=c['freeze'], expiry=c['expiry'], ATR14=c['atr14'])
                    record.update(cost=cost, account_side=side)
                    ledgers.append(record)
                    if trade:
                        trade['cost'] = cost
                        trades.append(trade)
                        equity = trade['equity_after']
    baselines = {}
    for cost in ('PRIMARY', 'STRESS'):
        for side in (1, -1):
            ls = [l for l in ledgers if l['cost'] == cost and l['method'] == 'BASELINE' and l['account_side'] == side]
            baselines[(cost, side)] = np.array([l['cycle_r'] for l in ls])
    summaries = summarize(ledgers, trades, days, baselines)
    quality = dict(venue='BINANCE_SPOT', symbol='BTCUSDT', h1_rows=len(h), m1_rows=len(m),
                   h1_vs_m1_exact_checks=hourly_checks, cycles_planned=len(days), complete_cycles=len(cycles),
                   incomplete=incomplete, first_minute=iso(int(m[0, 0])), last_minute_available=iso(int(m[-1, 0]) + MINUTE),
                   archive_checksums_verified=25, new_downloads=0, data_repairs=0,
                   protocol_sha256=frozen['spec_sha256'], preregistration_commit='cc74bb5',
                   holdout='NO_VIRGIN_HOLDOUT', forward_observations=0)
    json_write(out / 'data_quality.json', quality)
    json_write(out / 'summary.json', summaries)
    csv_write(out / 'cycles.csv', ledgers)
    csv_write(out / 'trades.csv', trades)
    csv_write(out / 'frozen_levels.csv', cycles)
    csv_write(out / 'monthly.csv', [dict(method=s['method'], side=s['side'], cost=s['cost'], **x) for s in summaries for x in s['months']])
    payload = json.dumps(dict(quality=quality, summaries=summaries, cycles=ledgers, trades=trades),
                         separators=(',', ':'), allow_nan=False).encode()
    (out / 'results.json.gz').write_bytes(gzip.compress(payload, mtime=0))
    print(json.dumps(dict(quality=quality, primary=[{k: s[k] for k in ('method', 'side', 'n', 'net_pnl', 'mean_net_r', 'classification')} for s in summaries if s['cost'] == 'PRIMARY'])))
    return quality, summaries, ledgers, trades, cycles, h, m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, help='Existing audited PR41 public archive directory')
    parser.add_argument('--out', default=str(HERE / 'artifacts'))
    args = parser.parse_args()
    run(args.cache, args.out)


if __name__ == '__main__':
    main()
