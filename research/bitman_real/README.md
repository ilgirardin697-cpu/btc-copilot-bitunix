# I-GOD BITMAN REAL OBSERVER v0.1

**INCONCLUSIVE — KONKORDE_PROXY, SHADOW ONLY, trade_authority=false.**

This is a new independent observer. BITMAN Phase2 stays **REJECT**, PR #22 at
`44029b4768e2b4bc47643bb51bf8a28432623a39`. Its strategy is not imported, rewritten
or reused. Only its verified public-market dataset and archived benchmark are
referenced. Production systems receive no new hook or dependency.

- [Results](BITMAN_REAL_OBSERVER_RESULTS.md)
- [Exact formula, sources, parameters and known differences](SOURCES.md)
- [Legacy signal recommendations — no cleanup executed](LEGACY_SIGNAL_AUDIT.md)

## Architecture and capabilities

`indicators.py`: clean-room brown mountain/EMA15, ADX/DI14, AO5/34, BBWP CLOSE/
SMA7/prior100. `events.py`: ENTRY/EXIT/REENTRY plus descriptive direction.
`outcomes.py`: separately measures future public prices; never a dependency of
event generation. `study.py`: frozen descriptive methodology, not an optimizer
or executable strategy. `telegram.py`: pure renderer, no sender or bot.
`observer.py`: file-fed, unstarted standalone SHADOW observation.

The new namespace contains **no HTTP transport**, authenticated endpoint, account
client, order method, credentials, Telegram token reader or Telegram poller.
Optional callback receives rendered text only; no sender is configured here.
The CLI prints to stdout. No command is added to production; the existing command
poller is unchanged. There are no production environment variables to configure.

## State vocabulary and limits

- `LONG`: mountain>0, MA inside, +DI>−DI. This is an explained **observational
  context**, not permission to enter or evidence of profitability.
- `SETUP_FORMING`: positive mountain/inside without DI agreement, or positive
  rising mountain while MA is outside.
- `WAIT`: no complete observed LONG context.
- `BLOCKED`: insufficient indicator data or bearish mountain/DI/AO context whose
  trading interpretation is not proven.
- `SHORT` is reserved, **cannot be emitted in v0.1**. The renderer also blocks a
  fabricated SHORT input. `SHORT_LOGIC_NOT_PROVEN` remains explicit.

ADX has no absolute entry threshold. AO/BBWP remain displayed context, not required
directional filters. No score, hidden optimization or arbitrary indicator votes.
EXIT is a technical MA-outside event: it cannot close a position or open SHORT.

All 1H/4H/1D features and events use fully closed UTC candles. There are no 15m
Bitman signals. `distance_to_zero` is continuous abs(MA); separation is distance
to the outer brown mountain edge while inside. Contraction does not create an
extra exit. N for reentry is **required explicitly**; historical N=1/2/3/5 are all
reported without picking the best. N is measured in that TF's bars, not hours.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN. Original Micro Finanzas Personales2.0
formula/normalization remain unavailable. Trend Speed original source was not
reliably verified: NOT IMPLEMENTED / FORMULA NOT VERIFIED. Its captured inputs
117/2.7/150/100/From start are metadata only. Production LOW29/EMA4 ML RSI stays
untouched; LOW27/SMA4 is separate unimplemented research metadata.

## Frozen historical evidence

Dataset: 61,723 complete public Binance USD-M perpetual 1H bars including warmup
2019-10 onward. Cutoff **2026-10-15 19:00 UTC**. `artifacts/data_manifest.json`
retains inherited source URLs/queries/checksums, ranges, rows, venue and pinned
commit. No raw market dataset is committed. This is not Bitunix venue parity or
the unknown chart venue/settings of the video.

TRAIN2020–2021; VALIDATION2022–2023; TEST2024–cutoff. Prior research already saw
these dates: chronological reused OOS, not a new virgin sample. Protocol, primary
endpoint and rule hashes were frozen before this study measured outcomes.
There is no parameter selection. TRAIN-only descriptive tertiles are not entry
rules. Matched non-event controls and weekly bootstrap help distinguish BTC drift,
but do not establish a causal effect or eliminate multiple testing/dependence.

Reference is the actual closed signal candle price. Outcomes use subsequent
**complete public1H** candles, including after a4H/1D signal. Horizons1/4/12/24/
48/72h. Raw directional BTC return, MFE/MAE, independent first+1/−1/+2/−2 hit times,
and ambiguous/unresolved barrier races are retained. EXIT returns are raw BTC
returns, not invented short profits. Missing futures and split-end overlap stay
incomplete. These are gross price statistics, **not entries/exits/fills, net
strategy PnL or Igor's returns**. Fees, funding and liquidation are not claimed.

REENTRY counts are subsets of ENTRY; directional LONG episodes and inside-state
bar cohorts are separate. Never sum them as independent observations. State-bar
outcomes overlap heavily. `events_and_outcomes.jsonl.gz` stores reproducible event
records, not a market dataset. Complementary conditional groups are exploratory
distributions, not permission to create a TEST-selected strategy.

Historical base snapshots are calculated with an explicit N=1 only to obtain a
single underlying event stream. Their `technical_event` and `exit_age_bars` plus
the recorded `reentry_windows` list are authoritative for all four reported
subsets; a snapshot's individual `reentry` flag is not a selected/recommended N.
No primary outcome, direction rule or classification depends on choosing N=1.

## Reproduce without rewriting the study

Python3.12, NumPy2.3.5, requests2.32.5. `requirements-study.txt` records dependencies
for the full repository suite (this observer itself uses no requests).
Full Git history is required for pinned provenance/source audits.

Use the already verified ignored cache `research/cache/bitman/hourly.npz`, or pass
a copied cache path to `market.verified_cache(path)`. The checksum must match the
manifest pinned in commit44029b4; no silent substitute or refreshed dataset.
Acquisition instructions for that public dataset remain in the immutable Phase2
README. No production service or volume needs to be accessed to run this study.

```text
python -m research.bitman_real.study evaluate --output-dir research/cache/bitman-real-replay
```

The output must be new/empty. Existing `results.json` is never overwritten. The
locked protocol and code hash are checked first. For exact comparison use the
recorded dependency versions. `study freeze` was executed once before evaluation;
it intentionally refuses to replace the existing protocol. `report` regenerates
presentation/supplementary V8 comparison only, never rules or primary results.

## SHADOW telemetry proposal — not started or deployed

If reviewed later, an independent process can read a separately supplied public
CSV (`time,open,high,low,close,volume,taker_buy_volume`; UTC1H opening ms). It can
be instantiated with a text-only sink. No live downloader/sender is installed in
this phase. A manual file-fed run would use:

```text
python -m research.bitman_real.observer --input-csv exported-public-1h.csv --state-dir research/cache/bitman-real-shadow --reentry-max-bars 3 --once
```

This is documentation, **not a command executed in this delivery**. The3 is merely
an explicit example, not a selected/default threshold. Default loop checks every
60s and computes only on a new closed TF candle. WAIT is not sent every bar.
Technical or directional transitions are grouped into one message per TF/candle.
First bootstrap/restart/gap catch-up is status only and sends no historical alert.
Identical candle/event IDs dedupe across restart. Failures are static/nonfatal;
one timeframe failure is isolated. Failed delivery cannot trigger any account
action. One writer per storage directory; no multi-writer guarantee.

Separate namespace/files: `bitman_real_state.json`, `bitman_real_events.jsonl`,
`bitman_real_snapshots.jsonl`. JSONL fsync; state atomic replace/file fsync and
directory fsync where supported. Refuses directories named for existing Guardian,
ML RSI, V8, Copilot Audit or Early Breakout stores. No secrets/account/chat data.
No claim that a persistent hosting volume is configured or disaster-proof.

Future actual event telemetry is `source=FORWARD_LIVE`; startup/recovery snapshots
are `FORWARD_LIVE_CONTEXT`. This study's reconstructed historical observations
are `HISTORICAL_BACKTEST`, never relabeled forward. Existing forward journals:
**PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR**. No reconstruction substitutes
for their prospective records.

## Verification and invariants

```text
python -m compileall -q research/bitman_real test_bitman_real.py
python -m unittest test_bitman_real -v
python -m research.bitman_real.safety
python -m unittest discover -v
git diff --check
```

Exact counts: `artifacts/validation.json`. Dedicated CI installs explicit numerical
dependencies and full Git history. Existing V8 CI gets the same infrastructure
needed to run repository tests; its strategy/execution source does not change.

V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED.
MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.

**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS. NO CLEANUP.**
