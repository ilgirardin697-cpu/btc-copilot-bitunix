# I-GOD BITMAN BTC DIRECTION ENGINE v0.1

Independent **directional information research**: “when it says UP/DOWN, what
happens later?” No entry, exit, sizing or strategy-PnL objective. Previous BITMAN
results are not changed or rescued. No production module depends on this package.

Branch starts at `7fc762522be9bae6bd1ac799dbcc2a9ab9e512c7`. A new PR must be
stacked against **bitman-real-phase4**, not main. PR22/23/24, their bases and
commits remain unchanged. The prior local closure document is left intact and
excluded from this new commit.

## Responsibilities, not votes

- **AO**: sign context, sustained two-slope momentum or closed zero crossing;
  raw slope/acceleration and toward/away-zero shown separately.
- **DI**: directional agreement. **ADX**: strength/turn/acceleration only, no
  direction assignment or fitted magnitude threshold.
- **Koncorde public proxy**: entry/inside/exit/reentry, participation context,
  continuous zero distance/separation. EXIT does not mean SHORT.
- **ML RSI**: read-only actual confirmed cache colors. No provisional/approaching
  direction authority, no math recomputation. Existing production observer has no
  daily output; this engine does not add one or substitute RSI27.
- **BBWP**: waking/expanding context. CLOSE/SMA7/prior100, slope/acceleration,
 50-cross/distance descriptive; no tuned45/47/52 gates or invented low-vol zones.
- **Levels**: read-only confirmed Copilot pivots, higher-TF confirmation preserved,
  previous full UTCday/week. Continuous distances%/ATR1H; closed range tests can
  expose a structural conflict, not an order.
- **MTF**:1D macro,4H swing,1H timing. Not three equal votes.

States UP / DOWN / TRANSITION / UNCLEAR / CONFLICT preserve explanatory detail
(e.g. UP_WITH_1H_PULLBACK vs POSSIBLE_BULLISH_TRANSITION). Strength is a logical
ADX/BBWP/MTF classification, not a sum of indicators. GradeA/B/C describes current
coherence, not statistical confidence/probability/sizing. Exact frozen rules are
in `artifacts/protocol.json` and the results report.

## Architecture and boundaries

`core.py`, `levels.py`: causal public features/hierarchy. `confirmed.py`: projects
only confirmed fields from a supplied copied observer export. `evaluation.py` is
the separate future-outcome evaluator; it is never imported by the core/observer.
`study.py` freezes/evaluates a fixed specification, no ranking or optimization.
`noise.py` measures historical overlap/latency; it cannot suppress an alert.
`telegram.py` renders text only. `observer.py` is **unstarted file-fed telemetry**
returning message strings; no sender/callback/token/poller/client is accepted.

One continuous state is one episode, regardless of detail/strength changes.
Prototype messages dedupe by state/detail/strength/grade and closed1H timestamp;
bootstrap/restart/offline catch-up is silent. State/events use separate atomic/
fsync storage. No existing store or environment variable is changed. Recovery
failures return a static error, never affect operational protection.

The optional cache reader opens a supplied file with `r` only. It validates
config/symbol/venue, confirmed validity/closed time and public-read age<=90s.
Known opposite4H confirmed ML is a conflict, not a trading action. Missing data
stays UNKNOWN. The copied-journal adapter retains actual recorded availability;
it never backdates a late observation to candle close. No actual export was
available or imported in this delivery.
ML RSI4H supplies the main confirmation;1H is displayed as timing context, not a
separate veto of the daily/swing direction.1D remains explicitly unsupported.

## Frozen evaluation

Verified ignored dataset `research/cache/bitman/hourly.npz`, SHA256
`e355d2dfe58f479a4c789e1ff6cdffceabcf4cb55ff5c5d0c7c465d9d59fee25`.
61,723 complete public Binance USD-M1H bars including warmup2019-10; cutoff
2026-10-15T19:00Z. Full metadata in inherited manifest; no giant market dataset
committed or downloaded anew. Original public acquisition remains documented at
Phase2's immutable data commit. No private Bitunix API needed.

TRAIN2020–21, VALIDATION2022–23, TEST2024–cutoff **reused OOS, not virgin**. No
rules selected on any split. The only fitted quantities are TRAIN volatility
quartiles for control matching, never signal decisions. Annual2022–26 walk-forward
uses fixed rules and matching cutpoints fitted only before each tested year.

Signal known at closed time, reference=closed price; future complete1H bars only.
No retrospective intrabar fill model. Directional returns, not PnL: costs/funding,
entries/exits/leverage are not modeled and cannot be inferred from accuracy.
Targets2/5/10% are observations, not TP. Simultaneous barriers are ambiguous.
Adverse-before-target is bounded because hourly OHLC cannot identify intrabar
order. Split ends/gaps/unmature outcomes are censored, never losses/successes.
Weekly block bootstrap is descriptive; overlapping episodes/outcomes and reused
TEST remain limitations. No multiplicity-corrected proof is claimed.

Public core and actual confirmed-ML incremental evaluation are separate. Without
real versioned confirmed journals, ML ablation remains PENDING, no substitute
mathematical port/backfill. A positive public-only row cannot validate the full
ML-confirmed engine. Forward volume data remains PENDING / NOT ACCESSIBLE FROM
CURRENT CONNECTOR. Live profitability and real alert usefulness are not claimed.

## Reproduce and verify

Python3.12, numpy2.3.5, requests2.32.5 (requests only needed by repository tests).
Full Git history for identity audits. Existing locked artifacts are immutable;
do not re-run freeze to change the protocol after TEST. With the exact cache and
an empty output destination:

```text
python -m research.bitman_direction.study evaluate --output-dir research/cache/bitman_direction_replay_new
python -m research.bitman_direction.reporting
python -m research.bitman_direction.timing_diagnostics
python -m research.bitman_direction.report
python -m compileall -q research/bitman_direction test_bitman_direction.py
python -m unittest test_bitman_direction -v
python -m research.bitman_direction.safety
python -m unittest discover -v
git diff --check
```

Compare JSON bytes and decompressed episode JSONL, not gzip creation timestamps.
CI uses offline fixtures/artifact checks; no transcripts or large data downloads.

`reporting` derives a canonical raw-versus-signed control supplement from the
published original rows; the frozen mixed matched aggregate for non-directional
states is not a meaningful single directional statistic. PrimaryUP/DOWN and
classification are unchanged (tested exactly). `timing_diagnostics` separately
measures existing detail transitions nested within episodes, without rearming
directional signals. Both are descriptive supplements, not parameter selection;
they regenerate their own presentation artifacts, never frozen primary results.

No cleanup is executed. See `LEGACY_NOISE_AUDIT.md` for historical measurement
versus missing delivered-alert evidence. An inconclusive engine cannot justify
silencing useful systems merely for visual simplicity.

**V8 UNCHANGED. GUARDIAN UNCHANGED. ML RSI MATH UNCHANGED.
MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.**

**NO MERGE. NO DEPLOY. NO REAL ORDERS. TRADE AUTHORITY: NONE.**
