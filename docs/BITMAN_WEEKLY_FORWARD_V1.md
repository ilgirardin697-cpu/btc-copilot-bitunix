# Bitman weekly forward observer V1

Status: implementation for review; disabled by default; no rollout performed.
Authority: **NONE**. OBSERVER ONLY / SHADOW ONLY / MANUAL research display.
No orders, account clients, automatic Telegram alerts, or changes to operability.

## Protocol and reference

Protocol: `BITMAN_WEEKLY_FORWARD_V1`, journal schema `1`.
Release protocol SHA256:
`d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8`.
The release hash is pinned in `bitman_weekly_forward/protocol.py`,
`protocol_v1.json` and the test fixture `weekly_forward_protocol.sha256`.
It covers the source hashes (including the verifier and its frozen indicator
dependency), bootstrap and manifest, fixed lags, range, horizons
and outcome thresholds. Startup verifies these before opening storage or network.
Any future rule change requires a separate V2 identity, bootstrap and journal;
do not refreeze V1 in response to forward results.

Production base: `9c660035f912be4640f09cf6e2d4c48583c20b04`.
Audited rule reference: PR #31,
`772446da2b7e045483c2e1d9a5c0acc185c47fe4`. Neither research PR is merged here.
No runtime module imports research. The exact `classify`, `resolve`,
`causal_range` and `outcomes` equations were transcribed from that reference.
The test-only reference fixture preserves the two state functions for AST and
fixture equivalence. Narrative historical sequences are not copied into runtime.

This remains **HYPOTHESIS FOR FORWARD OBSERVATION**, with **NO VIRGIN HOLDOUT**
for the preceding historical research. No historical edge is upgraded by this PR.

- `EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN`
- `EXACT BITMAN VOLATILITY PARITY: NOT PROVEN`
- AO is `OSCILLATOR_PROXY`; BBWP is `BITMAN_VOLATILITY_PROXY`.

## Frozen causal definitions

Only complete Monday 00:00 UTC to next Monday 00:00 UTC weeks are used.
AO = SMA5 of `(high + low)/2` minus SMA34; color GREEN iff its one-week
change is positive, RED iff negative, FLAT otherwise. Sign is independent.
BB width = `4 * population_std(close, 7) / SMA(close, 7)`.
BBWP counts strictly smaller widths in the preceding 100 values of a complete
101-observation window. Its range is 0–100. Slope is one-week difference;
TURN_UP requires previous slope <=0 and current slope >0.

The three independent, permanently fixed models are:

| Model | Maximum lag |
|---|---:|
| STRICT_SAME_WEEK | 0 weeks |
| SOURCE_ALIGNED_LAG_LE1 | 1 week |
| SOURCE_ALIGNED_LAG_LE2 | 2 weeks |

Above-zero RED/non-rising volatility is PULLBACK_UP; below-zero
GREEN/non-rising is PULLBACK_DOWN. Return to impulse color without crossing
zero activates reacceleration. A sign crossing activates a zero-cross candidate.
At activation, positive slope confirms immediately. A delayed confirmation
requires a subsequent TURN_UP within the model deadline. Zero/opposite sign
cancels; a new opposing color cancels reacceleration. Invalid observations reset
pending state. Zero-cross candidates retain sequence ownership; they do not
acquire a new color filter absent from PR #31. Existing pending candidates own
resolution over new candidates. Expired/cancelled candidates cannot resurrect.
Persistent expansion is not a repeated signal. Lags beyond 2 are rejected.

The exact functions and explicit cancellation, expiry, ownership, no-duplicate
and prefix-invariance tests are the controlling specification.

## Minimal public bootstrap

`bootstrap_v1.csv` contains **120** weekly rows, OHLC and open time only:
2024-07-01 through 2026-10-12; last available close 2026-10-19 00:00 UTC.
The open week is excluded. No outcomes, future labels, optimized signals or
research result tables are included.

Symbol: BTCUSDT. Venue: **BINANCE_USDM_PERPETUAL**.
Source: the audited PR #31 USD-M REST 4H dataset aggregated to closed weeks.
Audited weekly CSV SHA256:
`1f542daea1af9fe43a83994d0dc4f282bd770f54b0c00de99258e2c8db9cbdc6`.
Bootstrap SHA256 (UTF-8, canonical LF):
`b1b0757caffdaf306620d9446d2e8ef785cf6a19fd9d1a1f36c9eb78d587a1cf`.

The manifest includes a **causal Wilder14 ATR checkpoint** immediately before
the first bootstrap week and the preceding close. ATR has infinite recursive
memory; 120 rows alone cannot exactly reproduce a full-history ATR seed.
This checkpoint preserves the audited outcome normalizer without copying
years of unnecessary candles. Weekly live input requires no volume in the
formula. Hourly volume and taker-buy base volume are still validated.

The native-weekly/4H discrepancy caveat inherited from research is recorded in
the manifest. The old discrepant OHLC week lies outside this bootstrap window;
native-volume differences do not enter these OHLC-only formulas.

Startup golden check uses the complete manifest values, absolute tolerance
1e-9 for float fields, exact categorical equality:

| Available at 2026-10-19 00:00 UTC | Value |
|---|---|
| AO | 10698.622352941165 |
| AO slope | 348.99441176469554 |
| Sign / color | ABOVE ZERO / GREEN |
| BBWP previous → current | 41 → 30 |
| BBWP slope / volatility | -11 / COOLING |
| ATR | 6175.9111711882015 |
| Strict / lag≤1 / lag≤2 | OTHER / OTHER / OTHER |
| Pending | NONE |

Any mismatch stops the observer before storage or network, while Guardian
continues. Golden parity is technical equivalence, not validation of an edge.

## Runtime isolation and data transport

`Guardian.cycle()` and the Guardian class are unchanged. Only after the full
cycle returns does a guarded main-loop hook start the passive daemon host.
The main thread never waits for weekly data, calculations, fsync or replay.
Its exception boundary preserves Guardian operation even if startup fails.
Shutdown signals the thread and kills its child without joining it.

The host starts a bounded, credential-free subprocess (60-second lifetime,
one child at a time). Its explicit request contains only storage directory,
market-data URL and deployment source SHA. Environment allowlist:
PATH, SYSTEMROOT, WINDIR, TEMP, TMP, and Python encoding/no-bytecode settings.
No inherited exchange, Telegram, proxy, account or trading configuration.
No shared exchange client. Worker errors return sanitized status only.

The only transport accepted by this observer is:
`http://bitman-market-data.railway.internal:8080/fapi/v1/klines`.
It reuses the existing private gateway and never changes that service.
GET only; no ambient proxy; no redirects; 8-second timeout; bounded response.
Exactly BTCUSDT/1h/168 rows for a completed UTC week are required. Every row
must have 12 fields, exact open/close timestamps, continuity, finite positive
consistent OHLC, nonnegative volume and 0 <= taker-buy base <= base volume.
No partial data, venue fallback, new gateway or credentials.

Aggregation preserves first open, maximum high, minimum low, last close using
decimal parsing; no price rounding, interpolation or reconstruction from trades.
The journal stores the normalized weekly candle and a hash of the complete
validated hourly page. Hourly rows are not redundantly stored in this journal.

The background worker checks/replays at intervals of 1–5 minutes. It downloads
**nothing until a new closed week plus five minutes is due**. Manual `/bitman`
reads only the host's copied in-memory view; it never starts weekly work.
Healthy views older than 11 minutes become unavailable locally.

## Forward start, recovery and honest observation time

The first authoritative record is `FORWARD_OBSERVATION_START`, with real
activation timestamp, deployment source SHA, protocol and bootstrap hash and
last known close. BOOTSTRAP follows with the golden snapshot. No historical
model events are inserted.

On every restart, bootstrap plus the validated journal reconstruct all state;
the derived state file is not read as authority. Missing weeks are fetched in
chronological order, at most four per invocation. Each prefix is processed
before fetching its successor. A missing/unavailable/invalid page stops progress
as DEGRADED; the gap is retried, never skipped or fabricated.

If activation happens after the bootstrap cutoff, already-closed missing weeks
are `RECOVERY / PRE_ACTIVATION_WARMUP`, not forward observations. Setups
activated before the real activation timestamp are never promoted to forward
events, including delayed confirmations after activation.

`created_at` always records actual append time. `observed_at` for an event is
the durable confirmation WEEK_SNAPSHOT observation time. If a crash occurred
after that snapshot but before its MODEL_EVENT, replay completes the missing
record from that exact prefix without pretending the event was already stored.

If an outage delays observation until after the confirmation week's +1W
boundary, its record is explicitly `LATE_RECOVERY_NOT_PROSPECTIVE`; it and its
outcomes are excluded from prospective counters. Recovery is not allowed to
manufacture a forward track record from already elapsed periods.

## Journal schema and durability

Authoritative file: `/data/bitman_weekly_forward_v1.jsonl`.
Derived file: `/data/bitman_weekly_forward_v1_state.json`.
All tests use temporary directories, never the real volume.

Each record contains schema_version, protocol_version, protocol_hash,
record_type, deterministic record_id, created_at, week_open, available_at,
source_venue, source_timeframe, source_hash, weekly_candle_hash, payload,
prev_hash and record_hash. IDs bind type/protocol/model/week/kind or
event/horizon; duplicates do not write. `record_id` is the event identifier
referenced by OUTCOME records.

| Record | Payload |
|---|---|
| FORWARD_OBSERVATION_START | Real activation, source SHA, bootstrap identity, hypothesis |
| BOOTSTRAP | Bootstrap hash and full golden snapshot, no historical events |
| WEEK_SNAPSHOT | One new completed week's OHLC, indicators, all models and pending state |
| MODEL_EVENT | Model/type/side, activation/confirmation, actual lag/pullback length, proxies, frozen range, confirmation close/ATR, actual observation classification |
| OUTCOME | Event ID, matured horizon, maturation time and frozen descriptive metrics |
| RECOVERY | Pre-activation missing weekly warmup, explicitly not a forward event |

The record hash is SHA256 of canonical sorted compact UTF-8 JSON excluding
record_hash; prev_hash binds the preceding record. First prev_hash is 64 zeroes.
The entire chain and deterministic IDs are checked, then semantic replay
checks snapshots/events/outcomes and contiguous weeks. Exclusive OS file lock
prevents concurrent writers. Complete append is flushed and fsynced before
in-memory acknowledgement; Linux additionally fsyncs the directory.

A write/fsync failure poisons that writer and cannot report success. On restart,
an intact complete record is accepted only after a new successful fsync.
Truncated lines, hash mismatch, duplicates, reordering or impossible semantic
records produce `OBSERVER_JOURNAL_INVALID`. No truncation, repair, rewrite or
silent regeneration occurs. A missing journal with an existing state file is
also rejected. Derived state uses fsync and atomic replacement and can be rebuilt.

**Integrity limit:** a local hash chain is not signed WORM storage. It detects
edits and broken/reordered records against its retained chain, but cannot prove
that an attacker with full write access did not remove a complete valid suffix,
rewrite the whole chain, or delete both journal and derived state. External
trusted anchoring/backups would be required for that stronger guarantee; this
PR creates no external service and does not claim cryptographic authorship.
The 16 MiB journal size limit fails closed rather than silently rotating history.

## Outcomes and counters

Outcomes append independently at +1/+2/+3/+4 complete weeks from **confirmation**,
not activation. The causal four-week range is frozen at confirmation (including
that closed week). Wilder14 ATR is also frozen there. A move during the lag or
inside the confirmation candle is not credited as subsequent performance.

Frozen PR #31 metrics include return and AO-signed return, up/down/maximum
excursion, close/wick range breakout and direction, first-break week, distance
beyond range, reentry/persistence, thresholds >=5/10/15/20% and >=1/1.5/2 ATR.
The historical primary label remains close breakout plus >=10% same-side
excursion. These are descriptive mature outcomes, never WIN/LOSS labels or
orders. An incomplete horizon has no outcome record; IDs dedupe H1–H4.

Counters are derived from the journal: prospective records, active and H4
matured events and each matured horizon. Counts are **per model**; the same
market sequence in three models is not three independent market observations.
Late recovery counters remain separate. `FORWARD EVIDENCE: INSUFFICIENT` and
`LARGE MOVE WATCH: NOT VALIDATED` stay explicit; no automatic sample-size
threshold upgrades the hypothesis to a validated signal.

## Feature flag and manual display

`BITMAN_WEEKLY_FORWARD_OBSERVER_ENABLED` defaults to `false`.
Disabled means no background thread, child, network, storage writes or optional
panel. This PR does not define or enable the flag in Railway.
If later authorized, enabled runtime requires the existing validated
BITMAN_MARKET_DATA_URL and a valid RAILWAY_GIT_COMMIT_SHA; missing values
fail closed, with no fallback.

Manual `/bitman` appends a separate optional research block after the existing
operability section and before its unchanged complete safety footer. Its cache
can show proxies, model states/pending and event/outcome counts. It never uses
LONG/SHORT, BUY/SELL, entry prices or readiness recommendations. An invalid
journal displays only the requested local unavailability warning. Missing,
stale, disabled or failed weekly state never replaces the main Bitman result.
Oversized optional content is compacted or omitted under the Telegram limit.

The only changes to existing runtime sources are the exact passive main-loop
and shutdown hooks, and the optional manual response append. Original source
hashes/AST remain enforced after removing only these literal audited additions;
no old safety baseline is replaced. ML RSI audit adaptation is CI-only.

## Verification and boundaries

Dedicated workflow: **Bitman weekly forward observer**, full Git history.
An offline audit against the full 371-week PR #31 input reproduced all model
states, sides, pending/cancellation logs and the same 7/11/13 reference events.
All outcome arrays at horizons 1–4 matched with absolute tolerance 1e-12.
Only the small function-AST hashes and comparison summary are retained in a
test fixture; no research event or outcome was written into an observer journal.
This is implementation equivalence, not a new historical performance study.
Offline tests cover all four event types at lags 0/1/2, rejected lag3+, cancel/
expiry/ownership, prefix invariance, golden parity, malformed market data,
durable restart/fsync/interrupted writes, corrupt journals, replay, causal gap
recovery, all outcome maturities and late recovery exclusion.

An AST/source allowlist scans all current and newly added runtime modules.
Only the fixed weekly package and exact passive hook fragments are allowed
consumers. Execution, risk, readiness, V8, position/SL/TP paths, indirect helpers,
dynamic imports and weekly-key/state consumers outside that boundary fail CI.
Negative mutation fixtures demonstrate rejection. This is a conservative CI
source guard, not a sandbox against arbitrary hostile Python.

The existing approved 900-result readiness hash is retained, with WAIT 780,
WATCH_LONG 59, WATCH_SHORT 59, READY_LONG 1, READY_SHORT 1. Frozen engine,
readiness/render rules, market-data service, V8, ML RSI mathematics, Guardian
class/protections/execution and Telegram routing/sender remain unchanged.

No Railway operation, deployment, flag change, production volume write,
Telegram message or runtime activation is part of this change.

## Sanitized deployment-log verification

The logging addendum preserves every protocol-bound source **byte-for-byte**
against reviewed HEAD `3127ec40742feaf77c2b19d7150057c290c85c0e`.
The V1 hash remains
`d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8`.
Host, worker and market transport were already protocol-bound; none is edited
or refrozen to add diagnostics. Models, journal format/durability, outcomes,
bootstrap and readiness remain unchanged.

The separate `bitman_weekly_forward_logging.py` adapter selects a logging host
at the existing post-cycle hook. It inherits the original scheduling, cache,
read and shutdown behavior. Its child IO method retains the original AST except
for the external worker entrypoint, strict diagnostic-marker decoding and the
asynchronous status sink. CI proves this exact normalization. The shared
original host instance remains the source for manual display and shutdown.

`bitman_weekly_forward_log_worker.py` installs a worker-local Python audit hook,
then invokes the **original worker main**. It never replaces computation,
request validation, market acquisition, recovery or persistence. The hook sees
`urllib.Request` immediately before the original opener handles its GET. It
emits only `BITMAN_WEEKLY_FORWARD_FETCH=<week_open>` for the exact private
BTCUSDT/1h/168-row weekly request. Bootstrap/replay without a GET emits no marker.
A failed GET is still an attempt and is logged. No extra market request is made.

Worker markers are emitted before the GET into the existing stderr
pipe. The parent validates and relays them when that bounded worker completes;
Railway visibility can therefore lag the attempt by the worker lifetime, up to
the existing 60-second timeout and bounded cleanup. Complete markers are also
recovered from timeout output and drained crash output, with per-attempt dedupe.
Raw stderr and unrecognized output are
never relayed. This is an attempt marker, not a successful-download claim.
The worker's stdout remains the original single JSON result, untouched by
logging. A malformed/partial diagnostic line cannot corrupt that result.

On the first worker result, and only when status, **full** journal tip or record
count changes, the host queues one compact line:
`BITMAN_WEEKLY_FORWARD_STATUS=<json>`. The diagnostic queue is bounded to 32
entries and never blocks observation or the Guardian thread. A separate daemon
writes to stdout FD 1 without holding Python's shared TextIO lock. Sink errors,
queue saturation and logger startup failure cannot change the observer result.
Diagnostics may be dropped on failure; they are not authoritative evidence in
place of the journal and do not prove that a missing line was never attempted.

Allowed fields only: status, protocol_version, schema_version, journal_records,
journal_tip_prefix (12 hex characters maximum), week_open, available_at,
strict_state, lag1_state, lag2_state, strict_pending, lag1_pending, lag2_pending,
forward_events, active, matured, h1, h2, h3, h4, evidence and next_due.
Enums, integers, booleans and the hash prefix are allowlisted; malformed/missing
values become null. No full hash, source SHA, path, exception text, raw candles,
event payload, account, Telegram, credentials or environment is logged.

The JSON status is `HEALTHY`, or one of the static diagnostic codes
`BITMAN_WEEKLY_FORWARD_DEGRADED` and `BITMAN_WEEKLY_FORWARD_JOURNAL_INVALID`.
These telemetry labels do not alter the original internal status used by
manual display. Unknown errors use only the static degraded code.

Before the first new closed week, the expected successful startup diagnostic
has journal_records=2, all three states OTHER, no pending, zero events and
zero H1/H2/H3/H4, evidence INSUFFICIENT, and next_due at the following Monday
00:05 UTC. It has no FETCH marker. This describes a future rollout check;
no activation or production observation has occurred during this addendum.

The feature flag still defaults to false. Disabled means no logging host,
diagnostic thread, worker, network, writes or diagnostic output. Existing
Guardian safety baselines are retained: CI reverses only the exact logging
import substitution before applying the original frozen passive-hook guard.
The new adapters are the only extra allowlisted passive consumers and are
included in the no-execution/no-trading/no-Telegram source audit.
