# I-GOD Killzone PRICE observer — prepared, NOT DEPLOYED

Independent service: **igod-killzone-price-observer**.
**SHADOW ONLY. TRADE AUTHORITY: NONE.** No orders, leverage, trading clients,
Telegram, new indicator/model, training, Guardian integration or execution path.

## What is frozen

- PRICE from PR #43 `3f0e5e94e8fc5ee2e06af50ce8d8aa11882c5bb0`.
- Model canonical SHA256:
  `db59d952e6c79da87adb7a31cba41a6ee3a5879a8e0c57638336e58f7be6a6d9`.
- Same coefficients, means/scales, clipping, softmax and six PRICE features.
- Same fixed PRIOR and STRUCTURE references; no fitting functions in the service.
- `features.py` is the reviewed calculation, changing only its project import.
  The function source hashes are checked against PR #43 in tests.
- PINE_A: New York/DST, Asia20–23, London02–05. Four H1 bars in each session.
  Do not mix with OWNER_B. No TP advance200, visual tolerance500 or trading PnL.

## Separate prospective cohort

Protocol **IGOD_PRICE_BINANCE_FORWARD_V1**, schema1, origin
**PYTHON_BINANCE_SPOT_LIVE**. TradingView's protocol/journal/PR remain unchanged.
The same 2026-11-05→2027-05-04 fixed calendar is explicitly chosen for comparison,
with independent storage and acceptance. Activation is a real deployment event.
Late activation loses anchors; the dates never silently move.

Five anchors: **05:00,05:15,05:30,05:45,05:59 America/New_York**. Two-second closed
bar propagation margin, at most120s to capture, always before06:00. The last
anchor therefore has less than one minute. Scheduler uses IANA time, not fixed
Madrid or UTC hours. The 14/03/2027 missing02 cycle stays incomplete.

Every prediction uses four CLOSED Asia H1, three CLOSED London H1 and only the
closed1m prefix before its anchor. The completed final London bar and targets
never feed features. ATR14 is the existing OHLC scale, not a new filter.
The 1000 CLOSED H1 warmup is verified against the longer audited public history;
it never creates historical forward predictions.

Raw public HTTP response bytes, request/receipt UTC, monotonic timing, serverTime,
source hashes, features and probabilities are retained. Only official public
Binance Spot GET `/api/v3/time` and `/api/v3/klines` are allowed. No arbitrary
host, credentials, proxy environment, redirects, venue fallback or gap filling.

The host clock is checked against Binance; a conservative server-time/RTT/
monotonic upper bound must precede the capture deadline. A separate DURABILITY
record witnesses the real time after prediction fsync. A crash before that
witness never manufactures a timely receipt during recovery.

## Persistence and recovery

New independent volume mount **/price-observer-data**, never Guardian `/data`
or PAPER `/paper-data`. Single replica and OS writer lock.

```text
/price-observer-data/IGOD_PRICE_BINANCE_FORWARD_V1/
    events.jsonl               append-only authority
    raw/<sha256>.json           original HTTP response bytes, exclusive creation
    report.json                derived, atomically replaceable
    comparisons/<sha256>.csv    optional original owner-supplied TV exports
```

Record types: ACTIVATION, RECOVERY, CONTEXT, ATTEMPT, PREDICTION, DURABILITY,
MISSED, FAILURE, OUTCOME. Records include schema/protocol/origin/model hashes,
deterministic logical IDs, actual created_at, previous hash and record hash.
Prediction/outcome IDs are deduplicated; lifecycle/recovery records are distinct.
Writes flush+fsync; directory entries are fsynced on Linux. Hash-chain and raw
hashes are replay-verified before new acquisition. Corruption is never repaired,
truncated, regenerated or reset. Ambiguous durability stops writing until replay.
This is application append-only evidence, not protection against an administrator
rewriting the entire filesystem and all hashes; externally retained log tips
provide another audit reference. No absolute tamper-proof claim is made.

Missing predictions stay MISSED. Outcomes may be recovered later for forecasts
that actually exist. At20:00 NY the service fetches the closed final H1 and1m
data. It compares H1/60m OHLC, uses the frozen PINE_A targets and records first
touch06:00≤t<20:00. Both targets first touched in one1m is AMBIGUOUS, not a win.
Data revisions are appended/flagged; original forecasts and raw bodies remain.

## Reports and operational visibility

- `GET /health`: process liveness, including DISABLED/DEGRADED. HTTP200 alone
  does not assert usable evidence; require `/status` HEALTHY separately.
- `GET /status`: sanitized journal counts/tip, next due, coverage and quality.
- `GET /report`: cached coverage, exclusions, class counts, Brier/log-loss,
  fixed-bin calibration, per-anchor/month comparisons with both frozen baselines.
- `IGOD_PRICE_OBSERVER_STATUS=<JSON>`: sanitized change-only Railway logs;
  includes descriptive Brier/log-loss/ECE when data exists. No SSH prerequisite
  for status verification. Logs are observability, not the persistent authority.

Endpoints are private-only in the deployment plan; no domain/TCP proxy is created.
Incoming write methods are rejected. Health/report requests never fetch market
data or trigger predictions. Reports are reproducible from journal+raw evidence.

The unit of uncertainty is a cycle, not five independent anchors. Daily reports
are descriptive; confirmatory block7 CIs and fixed gates are evaluated only after
the cohort ends and minimum sample/coverage/classes are met. Minimum150 complete
cycles does not override95% coverage:181 planned requires172; the DST gap leaves
only8 other allowable lost cycles. No auto-validation or Pine publication switch.

## TradingView differences

`compare.compare_export`/`save_comparison` accept actual original exported logs
offline, preserve the original CSV and compare matching as-of/model observations.
No synthetic or historical replay is labelled live. External log timestamps are
reported separately from available_at/emitted_at, not rewritten. Imported_at is
the time of import, not historical receipt. No TV rows enter the Binance cohort.
Missing TV exports mean **INSUFFICIENT OVERLAP**, never fabricated parity.
The12 reused real Pine inference fixtures test arithmetic only; prior market
parity remained9/12, and timestamp/reload/source identity issues remain open.

```text
python -m igod_killzone_price_observer.inspect --evidence-copy PATH_TO_EXPORTED_EVIDENCE_DIRECTORY
python -m igod_killzone_price_observer.compare --logs ACTUAL_TV.csv --evidence-copy PATH_TO_EXPORTED_EVIDENCE_DIRECTORY --out-dir LOCAL_COMPARISON_DIRECTORY
```

These offline commands inspect a copied journal plus its raw directory. They
do not query Binance or append forecasts/outcomes. The comparator retains the
original validated TV CSV in the separately specified output directory.

## Preparation and tests

Runtime dependencies are pinned to the versions used for preparation:
NumPy2.3.5 and tzdata2026.6. The Docker image uses the packaged IANA database
instead of a different OS timezone release. This does not change model rules.

```text
python -m pip install -r igod_killzone_price_observer/requirements.txt
python -m unittest test_killzone_price_observer -v
python -B -m igod_killzone_price_observer
```

Default `PRICE_OBSERVER_ENABLED=false`: no observer writes, no market queries,
no activation journal. Only the separate health/report process is available.
Enabling additionally requires the new persistent mount and a valid reviewed
source SHA from RAILWAY_GIT_COMMIT_SHA or PRICE_OBSERVER_SOURCE_SHA. Only these
nonsecret fields and PORT are read from the environment; no credential scan.

See [deployment and cost plan](DEPLOYMENT_PLAN.md). It is a future procedure,
not authorization or an executable rollout script. No Railway resource, flag,
domain or service is created/changed by this PR. PR #41/#42/#43/#44 stay intact.
