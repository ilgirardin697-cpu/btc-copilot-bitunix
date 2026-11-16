# Frozen candidate specification for prospective review

Status: PREPARED / NOT ACTIVATED. HYPOTHESIS FOR FORWARD OBSERVATION.
NO VIRGIN HOLDOUT in the inspected 2022–2026 history. No profitability claim.
Other-chat/Telegram commentary is unverified external narrative, not certified
indicator data, training labels or prospective observations.

## 1. Protocols and causal indexing

The venue is BTCUSDT **BINANCE_USDM_PERPETUAL**, never Spot or Bitunix by
substitution. Reuse the audited public indicator calculations: ADX/DMI14,
AO5/34, pececillos, tendencia, tiburones, red EMA15(**tendencia**), BBWP7/100,
ATR14 and their causal slopes. Full external platform parity is not certified.

Let `d[t]=x[t]-x[t-1]`, `s` be the hypothesis side (+1 or -1), and `n` be
2 for TURN22 or 1 for TURN11. A turn requires strictly `s*d>0` for the last
n slopes and strictly `s*d<0` for the preceding n slopes. Flat slopes fail.
The vertex is `t-n`; availability is the close of confirmation candle t.

| Gate | P1 exhaustion and mirror | P2 onset and mirror | P3 failed recovery and mirror |
|---|---|---|---|
| Primary hypothesis | LONG | SHORT | SHORT |
| AO turn | toward s, opposite zero side over last 2n values | toward s, either zero side | toward s, same zero side over last 2n+1 values |
| Pececillos | turn toward s; current slope aligned | same | same |
| ADX | peak, currently falling | trough, currently rising | no ADX emission gate |
| DMI | no emission gate | +DI leads LONG / -DI leads SHORT | no emission gate |

No red-line cross or BBWP condition is added to these protocols. Three mirrors
are controls/hypotheses, never automatically authorized signals. Preserve the
original 2h token coincidence window, cancellation on sign/alignment/DMI loss,
invalid-data reset, expiry, consumed tokens/no resurrection, and 25h cooldown
per pattern and side before intensity filtering.

The 1+1 adaptations are mathematical, not return-selected: valid streak 3 rather
than 5; vertex t-1 rather than t-2; curvature `abs(dADX[t]-dADX[t-1])` rather than
the difference of two 2-slope means; AO/pececillos post-turn magnitude over one
slope rather than two; zero-side spans 2/3 rather than 4/5. Everything else is
preserved. Original 2+2 events and audit statuses are tested exactly against
PR #50, not merely compared on a profitable episode.

Intensity uses 720 strictly prior hourly observations and empirical midranks.
P1 uses a high ADX vertex percentile; P2 uses its **low** percentile tail and a
high curvature percentile. AO magnitude is normalized by current closed price.
The minimum applicable rank freezes into each token. ALL, Q75 and Q90 remain
separate, with Q75 the original primary; no quota filling or threshold relaxation.

## 2. Independent comparative measurements

These explicit **new, unvalidated measurement conventions** are not new gates:

- Record individual AO/ADX 1+1 and 2+2 turns and their vertex/detection times.
  Record each distinct AO/ADX component pair within 2h without suppressing the
  original protocols. ADX turn direction is never treated as price direction.
- Record pececillos slope separately from its crossing of the red line. The red
  line is EMA15(tendencia), not EMA15(pececillos). Record zero crosses with the
  exact series: AO, pececillos, tendencia, tiburones or ma_trend.
- Record BBWP level and slope independently, including non-rising-to-rising and
  non-falling-to-falling transitions. High BBWP is not a direction or probability.
- 1H/4H/1D/1W use complete contiguous UTC buckets. Weeks begin Monday00UTC.
  Only buckets closed by the H1 observation are available. State is the explicit
  AO zero-side plus public indicator facts and a close/SMA200 proxy, **not** the
  frozen Direction Engine. Insufficient timeframe-specific warmup is UNKNOWN.
- Prior20H high/low excludes the current candle. A closed close strictly outside
  is a structure break; a wick through with the entire body back inside is a
  rejection. Store each broken level unchanged for four subsequent closed bars.
  A close crossing back is recovery; a recross within four bars of recovery is
  failed rebound (or the symmetric failed pullback). Expirations are retained.
- WATCH_REBOUND: AO<0 and AO/pececillos slopes positive. WATCH_SHORT: AO<0,
  -DI leads and AO slope negative or a new downside structure break.
  WATCH_SHORT_REENTRY: WATCH_REBOUND occurred in the previous4h, followed by
  AO<0, both slopes negative and -DI dominance; takes precedence over WATCH_SHORT.
  Otherwise null. Labels are observations, not entry instructions or gates.

Models run first and cannot import/use these comparative facts. The sidecar gets
read-only array views. A sidecar exception preserves the model snapshot and
records COMPARATIVE_UNAVAILABLE rather than inventing facts.

## 3. Receipts, timestamps and activation boundary

No HTTP client or scheduler is provided. A future approved collector must supply
original public response bytes plus URL, exact bounded query, actual request
start, receipt time, exchange time, status and SHA256. Only the exact unsigned
USD-M klines/fundingRate endpoints and BTCUSDT are accepted. There is no account,
order, arbitrary-host, credential or Telegram path.

Validate exact closed H1 schema, contiguous timestamps, OHLCV and taker volume.
Bootstrap at least6000 complete hours for technical warmup only. Record actual
activation, source SHA, registry hash and separate approval reference. No warmup
signals, model events or outcomes enter the forward sample. The first eligible
bar opens on/after the UTC hour boundary strictly after activation.

Each later observation stores candle open, earliest data availability at close,
actual source receipt and actual journal time. On-time means recorded within
five minutes after close. OFFLINE_TEST is always excluded. Late recovery is
stored with its real late timestamp, never backdated or relabelled as timely.
Missing hours block advancement; replay/backfill must restore them in order.
Changed source data appends a revision notice and degrades the session; no past
candle, feature, event or outcome is silently rewritten.

## 4. Append-only audit and recovery

Independent future storage contains `observations.jsonl`, content-addressed
original public blobs and an OS-held single-writer lock. Nothing uses Guardian's
or the weekly observer's storage. Record types are SESSION_START, PUBLIC_SOURCE,
CANDLE, COLLECTION_FAILURE, DATA_GAP, SOURCE_REVISION, FUNDING_COVERAGE,
FUNDING_REVISION, PRICE_OUTCOME and COSTED_OUTCOME.

Every record has schema1, registry hash, deterministic ID, actual created_at_ms,
previous hash and current hash over canonical JSON. Flush+fsync precede commit.
Duplicate identical IDs do not write; conflicting IDs fail. Uncertain writes
require reopen/replay. Truncation, tampering, reordering or semantic mismatch
fail closed without truncating, repairing or rebuilding existing history.
Replay verifies original blobs and recomputes indicators/models from their
chronological prefixes; a correctly rehashed but altered indicator still fails.

Hash chains are **tamper-evident, not physically immutable/WORM**. An attacker
controlling the whole store could regenerate a chain or remove a valid tail.
Keep independently trusted external tip checkpoints and versioned backups before
activation. Tests demonstrate that a retained external tip detects tail removal.
Crash/OS durability is bounded by the volume/filesystem's fsync semantics; an
incomplete final line requires review, never automatic repair.

## 5. Outcomes, duplicates and comparison population

Use one observation ID per venue/symbol/hour. Preserve every model claim, failed
candidate and sidecar fact as labels. Same-time same-side groups and AO-vertex
episode anchors identify duplicates within/across patterns and protocols. Do
not add label counts to obtain a larger independent n. Retain fixed UTC7day
block IDs for temporal dependence and overlapping outcomes.

For every observed hour, preserve LONG and SHORT **hypothetical** price outcomes
at +4/+12/+24h from the next H1 open after signal close. This is the frozen
research reference, **not an observed fill**: receipt usually follows that open.
Store that latency explicitly. With closed-H1 receipts, the endpoint open is
known only when its H1 closes, so outcome publication waits one additional hour.
Never claim live executability or profitable fills from these reference prices.

Price outcomes are immutable records; costed outcomes append separately. Fees
0.1% per side and adverse slippage0.05% per side remain research assumptions,
not claimed current Bitunix rates. Full public funding coverage and settlement
marks are required. Missing funding is UNKNOWN, never zero. Settlement exactly
on an entry/exit boundary preserves conservative/optimistic ordering bounds;
exact net remains null when ambiguous. No SL, TP, R-metric or leveraged account
simulation is introduced in this phase.

The baseline is the census of **all** eligible observed hours, including event
hours and their neighbors, matched by side, month, last closed4H close/SMA200,
and causal ATR/close720h-rank tercile. No event-centered exclusion, selected
random controls or outcome-dependent matching is used. Baseline and event
outcomes must both be mature and comparably complete; missing funding/coverage
is published, not imputed. Compare each atomic/composite event's availability,
actual detection time and +4/+12/+24 price outcome; show both sides for ADX facts.

## 6. Evaluation and fixed prospective cohort

Original constants remain Q75/12h, six pattern/side comparisons with Holm,
alpha0.05, MDE0.10percentage points, power goal0.8,2000 calendar-block bootstrap
replicates, seed20261115 and minimum20 occupied blocks. ALL/Q90, other horizons,
1+1 and all new comparative labels remain exploratory, never substitute winners.

The new inclusive comparison changes the paired-excess estimand and variance.
Old development sigma/required-effective-n figures are retained as planning
references/minimum floors, **not transferable proof of adequate power**. Final
independent statistical review must address effective n, shared baseline
uncertainty, overlap and six-test multiplicity. This core intentionally reports
descriptive means/excess and never assigns VALIDATED, profitable or operational
status. Insufficient coverage/sample remains NO TESTABLE.

Planned window remains [2026-11-17,2027-11-17)UTC; activation is null. Fixed12
months, no outcome-driven early stop, tuning or extension. Final read waits for
all +24h endpoints plus closed-data delay. Require>=95% expected hourly coverage
and auditable primary events. Missed start hours and late captures remain losses
of coverage; dates cannot be moved silently. Supply actual review time to
`summarize(...,as_of_ms=...)` so downtime at the tail is counted as missing.

## 7. Decision before any continuous capture

GO for independent review of this disabled research core. **NO-GO for activation
under this PR.** A later explicit authorization must approve collector transport,
source/clock verification, isolated storage/costs, external checkpoints, real
restart/recovery/load tests and the exact activation timestamp. No trading
execution, Telegram, Railway or Bitunix changes are authorized here.

Pin and record the collector's Python/NumPy versions and operating environment
before activation. Semantic replay is deliberately strict about numerical
values; cross-platform/library floating-point differences may stop replay and
must be reviewed, never resolved by silently changing the sealed rules or old
records. Local verification used Python3.12 and NumPy2.3.5. No historical dataset
or claimed live prediction is shipped as prospective evidence.

SHADOW ONLY. TRADE AUTHORITY: NONE.
