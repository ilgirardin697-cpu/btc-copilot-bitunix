"""Render every prespecified candidate, including failures; no ranking."""
import csv
import json
from .data import iso
def num(v):return 'NA' if v is None else f'{v:.3f}'
def ci(v):return '['+', '.join(num(x) for x in v)+']'

def report(results,rows,manifest,path):
    lines=['# BITMAN_ENTRY_RESEARCH_V0','',
        '**OFFLINE RESEARCH / SHADOW ONLY / TRADE AUTHORITY: NONE**','',
        '**NO VIRGIN HOLDOUT. No candidate is prospectively validated. NO RUNTIME INTEGRATION.**','',
        '## Protocol and source audit','',
        'Specification committed before outcomes; protocol_lock.json binds it and the analysis sources. '
        'Development2020–2021; validation2022–2023; reused evaluation2024–2026-08-31. '
        'Fixed annual walk-forward from2022, expanding available history, no fitted or selected parameters. '
        'Embargo48h primary/12h secondary at both year boundaries. Earlier research already examined these dates.',
        '', 'Frozen AO5/34 median, Wilder ATR14/DMI14/ADX14, BBWP7/rank101 and confirmed2L/2R pivot helpers '
        'are reused read-only. 1D/4H close availability is enforced. ADX measures strength, never direction. '
        'ML RSI is UNAVAILABLE: there is no multi-year same-venue confirmed production journal; nothing is reconstructed. '
        'Direction Engine and operability gates are not entry filters. Early Breakout remains NO EDGE; its selected parameters are not reused.',
        '', '**EXACT BITMAN INDICATOR PARITY: NOT PROVEN. EXACT BITMAN FE PARITY: NOT PROVEN.**',
        '', 'FE_PRC_NICOLAS_20170323_N13_V0 uses only raw13-bar gamma from '
        '[Nicolas’s public2017 implementation](https://www.prorealcode.com/prorealtime-indicators/rsi-laguerre-adjusting-gamma-fractals-energy/). '
        'The scalar formula is independently tested. No Gaussian/Laguerre variant or private Bitman equivalence is claimed. '
        'Falling FE is a predeclared congestion-filter hypothesis, not an author’s entry recommendation.',
        '', '## Dataset','',
        f'BTCUSDT / BINANCE_USDM_PERPETUAL: {manifest["first_open"]} → {manifest["last_close"]}. '
        f'{manifest["rows_5m"]:,} closed5m bars; {manifest["funding_rows"]:,} funding rates; {len(manifest["gaps"])} gaps.',
        '[Official USD-M archives](https://github.com/binance/binance-public-data); every ZIP verified against its SHA256 checksum. '
        'artifacts/data_manifest.json retains URL/size/rows/checksum per archive plus normalized array hashes. '
        'Raw market files remain local-only. No Spot, Bitunix, account access or production data request.',
        '', '## Simulation and cost assumptions','',
        'Signal close → next bar opening, refined with5m OHLC. Stop first if both barriers hit in one5m candle. '
        'ATR_2R:1.5ATR stop/2R target/24 bars. STRUCTURE_2R:prior6-bar extreme ±0.25ATR, '
        'risk0.5–4ATR/2R target/48 bars. Full maximum window must have complete data/funding. '
        'No re-entry, trailing stop or optimized exit. Shared48h anchors (12h for15m) avoid overlapping observations; '
        'different variants are never pooled as independent trades.',
        '', 'BASE fee5bp+slip1bp/side; CONSERVATIVE7.5+3; STRESS10+5. These are assumptions, not verified account fees. '
        'Funding rates are historical; funding mark price uses5m opening proxy. Boundary ownership debits adverse funding '
        'without awarding ambiguous credits. Thus net returns remain estimates. MAE/MFE on filled exit candles are '
        'conservative partial-path measures. Stop/target price and exit timing remain limited by5m resolution.',
        '', '## All reused-evaluation comparisons','',
        '| TF | Family | Variant | Exit | n | Net R | CI95 R | PF | Random ΔR | Parent ΔR | Classification |',
        '|---|---|---|---|---:|---:|---|---:|---:|---:|---|']
    for key,c in results['candidates'].items():
        s=c['splits']['REUSED_EVALUATION']
        lines.append(f'| {c["timeframe"]} | {c["family"]} | {c["variant"]} | {c["exit_kind"]} | {s["n"]} | {num(s["mean_R"])} | {ci(s["ci95_R"])} | {num(s.get("profit_factor"))} | {num(c["matched_control"]["mean_delta_R"])} | {num(c["incremental"]["mean_delta_R"])} | {c["classification"]} |')
    lines+=['','A=continuation/saucer; B=AO zero-cross; C=momentum reversal with known six-bar structure break. '
        'AO_DMI/FE include context. Proper parent for each single-indicator effect is AO_CONTEXT; '
        'DMI_FE is compared with DMI and additionally FE. 15m B is secondary and cannot replace a failed primary.',
        '', '## Costs, side and best-event sensitivity','',
        '| Candidate | BASE n/R | Conservative R | Stress R | LONG n/R | SHORT n/R | ex-best1 R | ex-best3 R |',
        '|---|---|---:|---:|---|---|---:|---:|']
    for key,c in results['candidates'].items():
        s=c['costs']['BASE'];lo=c['side']['1'];sh=c['side']['-1']
        lines.append(f'| {key} | {s["n"]}/{num(s["mean_R"])} | {num(c["costs"]["CONSERVATIVE"]["mean_R"])} | {num(c["costs"]["STRESS"]["mean_R"])} | {lo["n"]}/{num(lo["mean_R"])} | {sh["n"]}/{num(sh["mean_R"])} | {num(s.get("ex_best1_mean_R"))} | {num(s.get("ex_best3_mean_R"))} |')
    lines+=['','## Temporal stability / fixed walk-forward','',
        '| Candidate | Dev n/R | Validation n/R | 2024 n/R | 2025 n/R | 2026 partial n/R |',
        '|---|---|---|---|---|---|']
    for key,c in results['candidates'].items():
        ss=[c['splits']['DEVELOPMENT'],c['splits']['VALIDATION']]+[c['annual'][str(y)] for y in (2024,2025,2026)]
        lines.append('| '+key+' | '+' | '.join(f'{s["n"]}/{num(s["mean_R"])}' for s in ss)+' |')
    lines+=['','2022 and2023 are the first fixed expanding-history folds. All annual results2020–2026, '
        'regimes, LONG/SHORT, costs, win rate, quantiles, gross/net returns, R, profit factor, drawdown, '
        'exposure, MAE/MFE, duration, first5m adverse rate and entry drift are in results.json and metrics.csv. '
        'R drawdown is cumulative risk-unit diagnostic; unit-notional drawdown is separate. Neither is account equity. '
        'Exposure/frequency denominators span first entry through last exit in each reported cohort, explicitly recorded; '
        'they are descriptive active-span rates, not full-calendar capital utilization.',
        '', '## Attrition and exclusions','', '~~~json',
        json.dumps(dict(primary=results['quality_1H'],secondary=results['quality_15m']),indent=2),'~~~',
        '', 'Per-candidate attrition records all anchors, surviving trades and removed observations. '
        'Technical exclusions are distinct from indicator removals. Controls unmatched or with invalid outcomes '
        'are omitted from paired comparisons, never assigned zero profit. Matching uses year-month, side and '
        'causal4H SMA200 regime, with fixed seed and nonoverlap. It does not match future outcomes.',
        '', '## Objectively selected examples','',
        'Earliest chronological positive and negative evaluation trade, per family, fixed full-filter ATR exit. '
        'No replacement example is selected when a category is empty. These examples cannot calibrate rules.',
        '', '| Family/outcome | Signal available UTC | Entry UTC | Side | Entry | Stop | Target | Exit UTC/reason | Net R |',
        '|---|---|---|---|---:|---:|---:|---|---:|']
    for fam in ('A','B','C'):
        cohort=sorted([r for r in rows if r['timeframe']=='1H' and r['family']==fam and r['variant']=='AO_DMI_FE' and r['exit_kind']=='ATR_2R' and r['split']=='REUSED_EVALUATION'],key=lambda x:x['signal_time'])
        for sign,label in ((1,'positive'),(-1,'negative')):
            r=next((r for r in cohort if sign*r['costs']['BASE']['net_R']>0),None)
            if r:
                lines.append(f'| {fam}/{label} | {iso(r["signal_time"])} | {iso(r["entry_time"])} | {"LONG" if r["side"]==1 else "SHORT"} | {r["entry"]:.2f} | {r["stop"]:.2f} | {r["target"]:.2f} | {iso(r["exit_time"])}/{r["reason"]} | {r["costs"]["BASE"]["net_R"]:.3f} |')
            else:lines.append(f'| {fam}/{label} | No eligible example | — | — | — | — | — | — | — |')
    lines+=['','## Uncertainty, decision criteria and limitations','',
        'Seeded5000-draw calendar30-day block bootstrap, joint for paired/nested comparisons;95% intervals. '
        'Promising additionally requires one-sided0.05/35 adjusted lower bound>0, evaluation n>=100 and each side>=30, '
        'positive conservative lower95 bound and control/incremental lower95 bounds, PF>1, positive validation, '
        'positive every evaluation year and positive after removing best3. Single-block uncertainty is unavailable, not zero. '
        'Net/conservative/control-negative candidates are NO EDGE; remaining insufficient evidence is INCONCLUSIVE. '
        'These classifications were fixed before outcomes.',
        '', 'Historical reuse, cross-variant dependence, residual matched-control confounding, sparse strict gates, '
        'gap resets and fixed-spacing opportunity loss limit inference. No exact liquidity, latency, funding mark price, '
        'Bitunix execution or prospective profitability is demonstrated. No automatic observer is created.',
        '', '## Conclusions','',
        'All35 comparisons: '+json.dumps(results['classification_counts'],sort_keys=True)+'. No best exit is selected.','']
    for fam in ('A','B','C'):
        cc=[c for c in results['candidates'].values() if c['family']==fam and c['timeframe']=='1H']
        status='PROMISING FOR FORWARD VALIDATION' if any(c['classification']=='PROMISING FOR FORWARD VALIDATION' for c in cc) else 'INCONCLUSIVE' if any(c['classification']=='INCONCLUSIVE' for c in cc) else 'NO EDGE'
        lines.append(f'- Hypothesis {fam}: **{status}**. Individual NO EDGE variants are retained explicitly.')
    lines+=['','**DO NOT INTEGRATE into operability gates, Guardian or V8.** Any future observer requires a separately '
        'approved protocol and prospective append-only signals/outcomes. Historical positives alone do not authorize it.',
        '', 'Reproduce: python -m research.bitman_entry_lab.data --download --cache research/cache/entry_public_data; '
        'python -m research.bitman_entry_lab.study run --cache research/cache/entry_public_data. '
        'Published lock must be verified, not refrozen to fit another dataset.',
        '', 'TRADE AUTHORITY: NONE.']
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    flat=[]
    for key,c in results['candidates'].items():
        for section,groups in (('split',c['splits']),('annual',c['annual']),('side',c['side']),('regime',c['regime']),('cost',c['costs'])):
            for label,s in groups.items():flat.append(dict(candidate=key,section=section,label=label,**s))
    fields=sorted({k for row in flat for k in row})
    with (path.parent/'artifacts/metrics.csv').open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(flat)

