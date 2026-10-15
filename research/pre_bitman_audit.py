"""Read frozen Git research artifacts. No strategy, selection, network or account API.

Run once with --freeze to record branch tips; later runs use those exact commits.
Outputs are derived evidence, never rewritten research results.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research' / 'pre_bitman_artifacts'
BRANCHES = ('confluence-engine-research', 'mlrsi-1h-research', 'mlrsi-pattern-research',
            'early-breakout-shadow', 'v8-bear-research', 'mlrsi-mtf-observer',
            'main', 'v8-real-executor', 'confluence-exact-mlrsi')
PATHS = {
    'confluence': ('confluence-engine-research', 'research/confluence_artifacts/results.json'),
    'exact': ('confluence-exact-mlrsi', 'research/exact_mlrsi_artifacts/results.json'),
    'one_hour': ('mlrsi-1h-research', 'research/mlrsi_1h/test_results.json'),
    'one_hour_development': ('mlrsi-1h-research', 'research/mlrsi_1h/development_results.json'),
    'pattern': ('mlrsi-pattern-research', 'research/mlrsi_pattern/test_results.json'),
    'bear': ('v8-bear-research', 'research/artifacts/results.json'),
    'early': ('early-breakout-shadow', 'research/early_breakout_artifacts/results.json'),
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def blob(sha, path):
    return git('show', sha + ':' + path)


def selected_metrics(result):
    selected = result['selected']
    key = selected['key'] if isinstance(selected, dict) else selected
    metrics = result['models'][key]['TEST']
    return key, metrics.get('metrics', metrics)


def build(refs):
    provenance, inventory, data = [], [], {}
    for branch, sha in refs.items():
        files = git('ls-tree', '-r', '--name-only', sha).decode().splitlines()
        research = [p for p in files if p.startswith('research/')]
        main_files = set(git('ls-tree', '-r', '--name-only', refs['main']).decode().splitlines())
        inventory.append(dict(branch=branch, sha=sha, research_files=len(research),
                              research_missing_from_main=[p for p in research if p not in main_files],
                              commit_time=git('show', '-s', '--format=%cI', sha).decode().strip()))
        # Hash reports, code, manifests and artifacts, including compressed ledgers.
        for path in research:
            raw = blob(sha, path)
            provenance.append(dict(branch=branch, sha=sha, path=path, bytes=len(raw),
                                   sha256=hashlib.sha256(raw).hexdigest()))
    for name, (branch, path) in PATHS.items():
        data[name] = json.loads(blob(refs[branch], path))
    c, h, p, e, b = (data[k] for k in ('confluence', 'one_hour', 'pattern', 'early', 'bear'))
    event_summary = {}
    for name, study in (('one_hour', h), ('pattern', p)):
        event_summary[name] = {}
        for event, result in study['results'].items():
            key, metrics = selected_metrics(result)
            event_summary[name][event] = dict(selected_before_TEST=key, metrics=metrics,
                yearly=result['yearly'], bootstrap=result['bootstrap'],
                classification=result.get('classification', study['classification']))
            if name == 'one_hour':
                event_summary[name][event].update(
                    alignment=result['alignment'], volatility=result['volatility'],
                    regime4=result['regime4'], paired_control=result['paired_control_advantage'],
                    neighbors=result['neighbors'], stress=result['stress'],
                    promotion_gates=result['promotion_gates'], forward=result['forward'])
    annual = {}
    for year, metrics in c['by_year'].items():
        # Cash attribution in initial-equity units, NOT a no-cost rerun/strategy.
        annual[year] = dict(metrics, gross_price_cash_attribution=metrics['total_return'] +
                           metrics['fees'] + metrics['slippage'] + metrics['funding'])
    raw = blob(refs['confluence-engine-research'],
               'research/confluence_artifacts/selected_trades.csv.gz')
    trades = list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode())))
    trade_years = {}
    for row in trades:
        year = str(datetime.fromtimestamp(int(row['entry_time']) / 1000, timezone.utc).year)
        trade_years.setdefault(year, []).append(float(row['return']))
    result = dict(schema=1, source='HISTORICAL_BACKTEST_ARTIFACTS', refs=refs,
                  forward_volume_data='PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR',
                  inventory=inventory, provenance=provenance,
                  confluence={k: v for k, v in c.items() if k != 'all_candidates'},
                  confluence_trade_counts_by_entry_year={y: len(v) for y, v in trade_years.items()},
                  confluence_annual_cash_attribution=annual,
                  events=event_summary, exact={k: v for k, v in data['exact'].items() if k != 'rows'},
                  early={k: v for k, v in e.items() if k != 'candidates'},
                  early_selected=e['candidates'][e['selected']['selected_id']], bear=b)
    protected = {
        'main': ('trade_guardian.py', 'guardian_risk.py', 'guardian_bitunix.py',
                 'guardian_commands.py', 'guardian_signals.py', 'copilot_audit.py',
                 'live_auto.py', 'early_breakout_core.py', 'early_breakout_shadow.py'),
        'v8-real-executor': ('v8_executor.py', 'v8_bitunix.py', 'trend_v8.py'),
        'mlrsi-mtf-observer': ('mlrsi_math.py', 'mlrsi_observer.py', 'mlrsi_guardian_host.py'),
    }
    result['protected_source_hashes'] = [
        dict(branch=branch, sha=refs[branch], path=path,
             sha256=hashlib.sha256(blob(refs[branch], path)).hexdigest())
        for branch, paths in protected.items() for path in paths]
    return result


def pct(value):
    return 'NA' if value is None else f'{value * 100:.2f}%'


def tables(evidence):
    c = evidence['confluence']
    lines = ['# Tablas extraídas de artefactos congelados', '',
             'No selección nueva. No métricas forward-live. Ratios de carteras y medias por evento no son intercambiables.', '',
             '| Sistema/split | Return | CAGR | Sharpe | Sortino | MaxDD | PF | Expectancy | Trades |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, system in [('D_60m_R60_1_opposite', c['best']), *c['benchmarks'].items()]:
        for split in ('TRAIN', 'VALIDATION', 'TEST', 'ALL'):
            m = system[split]
            pf = m.get('profit_factor')
            pf_text = 'NA' if pf is None else f'{pf:.3f}'
            lines.append(f"| {name}/{split} | {pct(m['total_return'])} | {pct(m['CAGR'])} | "
                         f"{m['Sharpe']:.3f} | {m['Sortino']:.3f} | {pct(m['MaxDD'])} | "
                         f"{pf_text} | "
                         f"{pct(m.get('expectancy'))} | {m.get('trades', 'NA')} |")
    lines += ['', '| Año D (flat anual) | Return | Sharpe | PF | Expectancy | n | Fees | Slip | Funding | Precio bruto: contribución cash |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for y, m in evidence['confluence_annual_cash_attribution'].items():
        lines.append(f"| {y} | {pct(m['total_return'])} | {m['Sharpe']:.3f} | {m['profit_factor']:.3f} | "
                     f"{pct(m['expectancy'])} | {m['trades']} | {pct(m['fees'])} | {pct(m['slippage'])} | "
                     f"{pct(m['funding'])} | {pct(m['gross_price_cash_attribution'])} |")
    for study, events in evidence['events'].items():
        lines += ['', f'## {study}', '',
                  '| Evento:confirmación | Modelo congelado | TEST n | TEST mean net | PF | 2026 n | 2026 mean net |',
                  '|---|---|---:|---:|---:|---:|---:|']
        for event, r in events.items():
            m, y = r['metrics'], r['yearly']['2026']
            lines.append(f"| {event} | {r['selected_before_TEST']} | {m['trades']} | {pct(m['mean_net'])} | "
                         f"{m['profit_factor']:.3f} | {y['trades']} | {pct(y['mean_net'])} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', help='Record current remote tips once, without selection')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'refs.json'
    if args.freeze:
        if path.exists():
            raise SystemExit('REFS_ALREADY_FROZEN')
        refs = {b: git('rev-parse', 'origin/' + b).decode().strip() for b in BRANCHES}
        path.write_text(json.dumps(refs, indent=2) + '\n', encoding='utf-8')
    refs = json.loads(path.read_text(encoding='utf-8'))
    result = build(refs)
    (OUT / 'historical_evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                           allow_nan=False) + '\n', encoding='utf-8')
    (OUT / 'TABLES.md').write_text(tables(result), encoding='utf-8')
    print('PRE_BITMAN_HISTORICAL_EXTRACTION_OK', len(result['inventory']), 'branches')


if __name__ == '__main__':
    main()
