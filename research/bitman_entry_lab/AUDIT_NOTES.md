# Audit and interpretation notes

This package is offline research. Production sources were not edited. No Railway,
Telegram, account, order or deployment operation was performed for this study.

## Predeclared history
- Specification committed at 6eaf1dd638ddaa4e22771a924ee12548b1fb9bc2 before outcomes.
- Data and evaluation implementation committed at 53e9242 before outcomes.
- No new virgin holdout: all years overlap prior BTC studies.
- No entry, indicator filter, threshold, exit, cost or classification was retuned.

## Explicit implementation erratum
After the first evaluation, a review found that target-exit candles omitted their
possible adverse excursion from MAE. The diagnostic now retains that candle's
known adverse bound (when the stop was not hit). This does not change entries,
stops, targets, gross/net returns, control selection or classifications.

The research lock retains the previous simulation hash, initial results hash and
a financial projection hash. The correction is explicitly recorded under
implementation_errata. It is not a silent rewrite of predeclared history.
audit.py requires identical replay of every trade field except mae_R.
This is a diagnostic correction, not a second strategy fit.

A separate earlier report-prose amendment removed the reserved lower-case gate
token from Python string constants so the existing architectural canary could
remain unchanged. It occurred before outcomes and is retained in the lock.

The BITMAN_WEEKLY_FORWARD_V1 protocol/hash was never changed or refrozen.

## Counts and artifacts
simulated_trades.jsonl.gz contains variant/exit scenario rows. Rows across nested
variants are duplicates of the same underlying opportunity, not independent trades.
audit.json reports distinct anchor IDs separately. matched_controls.csv permits
inspection of actual matched dates, sides, regimes and BASE outcomes.
Regime/fee/annual distributions and uncertainty are in results.json and metrics.csv.

The report's exposure/frequency uses first entry to last exit within each cohort,
with denominator hours explicitly exported. It is not full-calendar utilization.
MAE/MFE bounds cannot recover the exact path within a 5m candle.
Funding uses actual rates but a public candle-price proxy for the unavailable mark.

Distinct anchors across different families and timeframes may still overlap; the
5529 distinct IDs must not be interpreted as 5529 independent replications.
Nonoverlap applies within each prespecified family's timeframe/variant experiment.
The root AO-only baseline compares with itself for the additional parent gate,
so cannot receive PROMISING from that gate. All current root baselines are already
NO EDGE under net/conservative costs, independently of this restrictive criterion.

## Reproduction
Use Python3.12 and the existing requirements.txt. No new dependency is required.

1. Download official archives explicitly, or reuse checksum-verified local files:
   python -m research.bitman_entry_lab.data --download --cache research/cache/entry_public_data
2. Verify the existing lock and run:
   python -m research.bitman_entry_lab.study run --cache research/cache/entry_public_data
3. Export matched controls and verify deterministic financial replay:
   python -m research.bitman_entry_lab.audit --cache research/cache/entry_public_data
4. Run python -m unittest test_bitman_entry_lab -v and repository audits.

The optional --reference-npz argument to audit compares arrays against the earlier
audited research data cache. Reproduction does not require this private local path;
the official public archives and published checksums are authoritative inputs.
The auxiliary audit is diagnostic, not a model dependency.

## Decision
No comparison qualifies as PROMISING FOR FORWARD VALIDATION.
Seven inconclusive comparisons do not establish incremental entry quality.
No observer or integration is authorized or implemented.
Any future prospective study needs a new approval and append-only protocol.

SHADOW ONLY. TRADE AUTHORITY: NONE.
