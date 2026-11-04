# I-GOD Killzone Optimal Entry Research V0

**OFFLINE / SHADOW ONLY. TRADE AUTHORITY: NONE.** No runtime consumer, network
client, probabilities from PRICE, orders, Telegram or deployment instructions.

Read [the complete report](artifacts/KILLZONE_OPTIMAL_ENTRY_RESEARCH.md),
[predeclared rules](SPECIFICATION.md), [immutable JSON](specification.json),
and [future research-only Pine design](ENTRY_RADAR_DESIGN.md).

New branch starts at reviewed Guardian base `9d40020`, not at an open research
PR. The reference geometry is copied byte-for-byte from PR #41 `3d3ca0b`.
PR #41/#42/#43 and all 162 tracked base files outside research remain unchanged.
The protocol was committed as `cc74bb5` before the new entry outcomes.

## Reproduce

Python 3.12+, numpy and tzdata. Matplotlib is required only for producing plots.
Tests and CI do not download market data or start any service.

```text
python -m unittest research.killzone_optimal_entry.test_research -v
python -m research.killzone_optimal_entry.evaluate --cache PATH_TO_AUDITED_PR41_CACHE --out research/cache/entry_reproduction
python -m research.killzone_optimal_entry.report --results research/cache/entry_reproduction --cache PATH_TO_AUDITED_PR41_CACHE
```

The cache contains the 25 official monthly archives and two frozen manifests
enumerated in freeze_manifest.json. Reuse the existing audited data or acquire
those exact public URLs/checksums outside CI. Different manifests/ZIP hashes,
missing rows or inconsistent H1 vs 1m aggregation fail closed.

The original first evaluation is retained locally in ignored
`research/cache/optimal_entry_first_run/`. The versioned results.json.gz is its
exact copy; no thresholds or trades were changed after examining outcomes.

LONG and hypothetical SHORT use separate cash-budget accounts per method/cost,
so SHORT profits cannot fund the LONG result. The SHORT ledger is price-only,
not an executable unborrowed Spot sale and not Binance/Bitunix futures.

The source hash distinguishes exact original Windows bytes from canonical Git
blob bytes solely to support Windows CRLF and Linux LF. This does not normalize
strategy behavior or refreeze any existing protocol.

The three reused real Pine geometry fixtures are regression evidence from PR #41;
unit fixtures do not constitute new independent platform parity or profitability.

## Artifact glossary

- cycles.csv: every planned method/side/cost/cycle, including missing/no trade.
- frozen_levels.csv: causal six-o'clock geometry, with UTC epoch availability.
- trades.csv: theoretical entry vs delayed reference/fill, SL/TP, costs and equity.
- summary.json / monthly.csv: side/partition/month/cost metrics and block CIs.
- results.json.gz: full deterministically compressed first results, including MTM.
- example_manifest.json: objective selection and exact UTC example timestamps.
- artifact_manifest.json: file sizes and SHA256.

MAE/MFE are explicit one-minute OHLC bounds, not an exactly observed trade path.
An empty sample stays INCONCLUSIVE; a zero return from not trading is not edge.
No history is called a virgin holdout or imported as forward evidence.
