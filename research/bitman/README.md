# BITMAN Phase 2 — isolated, frozen research

**REJECT. PUBLIC BITMAN-INSPIRED PROXY, not OFFICIAL BITMAN.**

Full results: [BITMAN_RESULTS.md](BITMAN_RESULTS.md). Primary publications and
attribution limits: [SOURCES.md](SOURCES.md). Audit base remains immutable:
`c1e015802f59baafbf04ee52228f216a391ead93`.

This directory has no operational integration. It cannot trade. No deployment,
credentials, Telegram polling, account access or production-variable change is
needed. CLASSIC and FUSION are research hypotheses, not replacements for Copilot,
Guardian, V8, ML RSI or Early Breakout.

## PRE_BITMAN constraints carried forward

- Confluence D60 had a positive archived TEST, but 55%/65% neighbors were negative;
  archived 2026 return was **−7.33%, PF 0.755**. It is a comparator, never a BITMAN
  rule. The new common-ledger/cutoff D60 numbers do not replace that old result.
  No new TEST selection among 55/60/65 is performed.
- Historical LOW27 ML RSI 1H GREEN_RESUME remains **INTERESTING BUT INCONCLUSIVE**.
  Only veto/confluence diagnostics are tried; no standalone mandatory generator.
  LOW29 is kept distinct and cannot inherit a LOW27 edge claim.
- ML RSI 15m hypothesis: **NO EDGE**. It is not an entry generator or timing layer
  in Phase 2; adding 15m without incremental evidence would broaden the search.
- Early Breakout: **NO EDGE**, excluded and unchanged. No automatic feature reuse.
- V8 BEAR SHORT A–G: **REJECT**, not reused. New bearish cloud/EMA/DMI hypotheses
  are independently developed and reported. None qualified in development.
- Real forward journals are pending. Neither historical performance nor a public
  source, a rendered SHADOW message or a unit test establishes live validation.

## What is frozen

- `artifacts/preregistered.json`: 18 one-factor CLASSIC candidates; two public
  cloud families; side-independent development selection; up to 14 active
  one-factor neighbors; eight subsequent FUSION additions; promotion gates.
- `classic_lock.json`, then `selection_lock.json`: selected using only physically
  truncated 2020–2023 inputs, before this experiment evaluated 2024–cutoff.
- Six source files are hashed by the lock: `spec.py`, `core.py`, `engine.py`,
  `run.py`, `mlrsi.py`, `data.py`. Do not edit them to improve TEST.
- `test_results.json` and four compressed JSONL trade ledgers: primary results.
  `serialization_receipt.json` records an export-only NumPy integer adapter.
- `comparison_correction.json`: canonical V8 reproduction using the last CLOSED
  4H close versus SMA200. The initial raw V8 comparator mistakenly used each 1H
  price against the 4H SMA. That raw comparator is deprecated, retained for audit;
  the correction does not change any BITMAN selection, trade or primary metric.
- `supplemental_diagnostics.json`, `fusion_walk_forward.json`: yearly, paired
  bootstrap and prior-data-only anchored annual walk-forward diagnostics.

Artifact JSON bytes are preserved across platforms, including original CRLF in
the pre-TEST preregistration. The local attributes recognize CRLF as line endings
for whitespace checks while retaining checks for trailing spaces/blank lines and
spaces before tabs. Checksums are not rewritten to accommodate checkout changes.

The audit and other experiments had already exposed results on 2024–2026. These
are **reused chronological OOS**, not a new untouched market sample. Public proxy
presets published in 2026 may also embody their authors' historical optimization.
Negative results are retained; exploratory TEST ablations must not select a new
strategy. CLASSIC/FUSION being identical is not independent confirmation.

## Data and accounting

61,723 complete UTC 1H candles including warmup from 2019-10-01; evaluation starts
2020-01-01 and ends **2026-10-15 19:00 UTC**. Venue: **Binance USD-M BTCUSDT
perpetual**, not Bitunix fills. 7,440 historical funding rows. The old verified 5m
archive is aggregated only to complete 1H groups; it is not a 5m trigger or fill
model. Additional data use public 1H klines. No interpolation across gaps.
`artifacts/data_manifest.json` records inherited source commit, URLs, query
parameters, timestamps, rows, payload checksums and normalized-array checksum.
Large raw data and numerical caches stay in ignored `research/cache/`.

1x nominal at entry, fixed quantity thereafter; no pyramiding, same-bar reverse,
leverage optimization or rebalancing. Signals at a closed 1H candle, entry at the
next open with adverse slippage. Stop/gap precedence is conservative. Initial
stop and trailing ATR are frozen from the signal; trailing updates take effect
only on the next bar. Fees apply to every partial fill. Historical signed funding
uses remaining quantity and hourly open as a settlement-mark proxy; funding
timestamps are preserved, but this does not model actual exchange fills/margin
or liquidation. Drawdown is hourly close mark-to-market, not worst intrabar DD.
Fixed quantity plus funding can exhaust equity even at initial 1x; the ledger
records insolvency rather than claiming a viable funded buy-and-hold account.
The separate no-funding buy-and-hold control is not a perpetual account result.

TRAIN 2020–2021; VALIDATION 2022–2023; TEST 2024–cutoff. Periods start flat and
liquidate at the boundary. Annual flat runs do not compound to the continuous
TEST result. Annual walk-forward can learn from earlier years once they are
past; it never updates the globally frozen TEST selection.

## Reproduction

Recorded runtime: Python 3.12.12, NumPy 2.3.5, requests 2.32.5. Use
`requirements-study.txt` for the numerical environment. Git history must contain
the audit, Confluence and observer commits pinned in `spec.py` (a full fetch).

With the existing verified `research/cache/confluence/data.npz`:

```text
python -m research.bitman.data
python -m research.bitman.reproduce --output-dir research/cache/bitman-replay
```

The data builder is an acquisition tool: it writes a manifest. On a clean clone,
run acquisition in a separate disposable checkout, never over the frozen
artifacts. To obtain the inherited archive, use the downloader at pinned
Confluence commit `6f83f9ab2451dd3ef33e9ca7ab90b2d15dd95258` in that separate
checkout (`python -m research.confluence_engine_backtest --download`). Its old
manifest, not an arbitrary newly extended dataset, must match the expected
checksum. Copy only that verified cache into the Phase 2 checkout. Then run the
Phase 2 data builder there. Fail closed on a checksum mismatch; do not silently
accept a revised public archive. Compare both manifest hashes and normalized
arrays with the frozen manifest before using the resulting cache.

`reproduce` writes only into a new separate output directory, uses the original
locks, re-evaluates the primary experiment and checks exact JSON equality. The
same recorded runtime is required for bit-exact comparison; platform/library
rounding differences are not permission to change parameters. Add
`--verify-development` to rerun TRAIN/VALIDATION selection in that separate
directory before TEST. It must reproduce selected parameters and eligibility.

The original chronological acquisition/experiment commands were:

```text
python -m research.bitman.data
python -m research.bitman.run develop
python -m research.bitman.evaluate
python -m research.bitman.report
```

Before `develop`, `preregistered.json` was explicitly written from `spec.protocol()`
and its checksum recorded. There is deliberately no implicit preregistration
rewrite in the experiment CLI.

Do not rewrite the preregistration or rerun `develop`, `evaluate` or `report` over committed
artifacts as a way to retune or replace this result. `evaluate` is the documented
JSON-scalar export adapter; it changes no numerical logic. `report` adds a
separate, explicitly documented comparator correction and diagnostics only.

## Frozen ML RSI dependency

`vendor/mlrsi_math.py` is a byte-identical copy of the existing frozen
LOW29 / Wilder RSI / EMA4 / PINE_PARITY_V4 observer module; see `SOURCE.json` and
its MPL notice. Existing observer/research files are untouched. No thresholds,
RSI seeds, recovery code or live state are changed. Exact TradingView parity is
**NOT proven**. The older LOW27 GREEN_RESUME finding cannot be assumed to transfer
to LOW29 on perpetual candles. The adapter uses causal calendar-year sessions,
bootstrapping only already-known bars, rather than anchoring thresholds at a
future end-of-TEST bar.

## SHADOW architecture and Telegram renderer

`core.py` is pure market computation; `engine.py` is an academic simulation.
`telegram.py` renders all six visual states but contains no Telegram transport,
bot token, polling or trading capability. Exact illustrative LONG/SHORT/SETUP/
WAIT/BLOCKED/ERROR messages are in `artifacts/telegram_samples.json` and the report.
Actual data source and theoretical 1x risk are shown honestly, not a fictitious
Bitunix source or 0.50% position-risk allocation.

`shadow.py` is an **unstarted, file-fed observer**, separate from all production
processes. It reads a locally supplied public 1H CSV with fields
`time,open,high,low,close,volume,taker_buy_volume`, UTC opening timestamps in
milliseconds. It filters unfinished candles, rejects gaps/stale/schema errors,
and emits transitions only. Its optional output callback receives text only.
No Telegram sender is configured in this PR.

Separate storage: `bitman_state.json` (atomic replace), `bitman_signals.jsonl`
(fsync), `bitman_snapshots.jsonl` (fsync). Initial/recovery context is not a new
signal; durable event IDs prevent restart duplicates. One writer per directory;
no claim of multi-writer coordination or hosting-volume durability. MLRSI-gated
future configurations require a separately supplied observational cache and
currently fail closed; the actually selected F00 configuration needs none.
No service is started by the backtest, import, CI, or this PR.

## Future evidence

`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`.

The accepted `research/import_forward_journals.py` remains unchanged. It can
analyze future exported copies of Copilot/ML RSI journals. `forward.py` is a
read-only adapter for future **BITMAN** signal exports using the same evaluator:

```text
python -m research.bitman.forward --input-dir exported-bitman --output-dir research/cache/forward-report --as-of 2026-12-01T00:00:00Z --market-csv exported-public-5m.csv
```

The optional 5m file is post-signal outcome measurement only, not a strategy
timeframe. Missing future candles stay censored. Original exports and historical
artifacts are not modified. Imported evidence could change which hypotheses
deserve a newly registered study; it cannot rewrite this frozen negative TEST.
No existing live journal is reconstructed or claimed FORWARD VALIDATED.

## Verification

```text
python -m compileall -q research/bitman test_bitman.py
python -m unittest test_bitman -v
python -m research.bitman.safety
python -m unittest discover -v
git diff --check
```

V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI MATH UNCHANGED.
ML RSI RECOVERY UNCHANGED. EARLY BREAKOUT UNCHANGED. MANUAL COPILOT UNCHANGED.

**NO MERGE. NO REAL ORDER. NO RAILWAY DEPLOY.**
