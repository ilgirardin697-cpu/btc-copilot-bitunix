# FORWARD SHADOW hardening V2 — prepared, not activated

SHADOW ONLY. TRADE AUTHORITY: NONE. Zero prospective observations.

New independent branch from PR #52 HEAD
`9f307fd9feda6279253c0a0813d49b47d3f1d9b2`. All prior sources, protocols,
hashes, indicators, TURN22 and TURN11 emitters remain unchanged. Only this new
directory is added. PR #52's V1 registry and its original 17 November window
remain intact; V2 does not shift them or reinterpret historical research.

## Five-blocker disposition

| Blocker | Prepared implementation | Still required before continuous capture |
|---|---|---|
| Window | Separate sealed V2 policy plus immutable cohort approval manifest; start currently null, fixed12 calendar months | Approve an actual future UTC start before activation |
| Revisions/recovery | Raw original/correction bytes, field deltas and real timestamps; parent quarantine and reviewed child link; atomic CAS; auditable orphan quarantine | Review procedure and independent parent anchor ACK |
| Performance | Incremental public-formula evaluation; original emitters reused; safe checkpoint codec; exact full-reference and restart tests on8760 hours | Qualify pinned Linux image and actual volume/host load |
| Statistics | Joint7day block bootstrap, inclusive regime census, six Holm contrasts, frozen power planning and minimum20 occupied blocks | Confirmatory power is infeasible under the fixed current12month design; no claim of edge |
| External integrity | Versioned export, trusted-anchor verification, empty-root restore, tail-loss/tamper tests and OS single writer | Configure independent storage/versioning/permissions and verify two writers on the real volume |

**Activation decision: NO-GO.** This PR supplies code and offline audit evidence;
it does not claim that unavailable real infrastructure tests passed.

## Immutable registration and clocks

`registry.py` / `manifest.json` seal the new implementation, policy, power plan
and unchanged old dependencies. Existing V1 hashes are never refrozen. The
actual cohort has its own hash, approval reference, source SHA and authorized
writer ID. Its start must be an explicitly approved future whole UTC hour;
end is12 calendar months later (February29 caps at the next February's last day).
Neither restarts nor child sessions can change that identity, including when
restoring from a checkpoint. A changed rule needs a new registry/journal.

Coverage uses **confirmation close timestamps** in `[start,end)`: the candle
opening one hour before start and closing at start is the first expected bar.
This removes V1's hidden extra open-time offset. Actual capture after activation
must be within300000ms of close; late recovery is preserved but excluded from
timely evidence. Missed hours are not recovered as original emissions.

Every unchanged model emission is stored. Primary inference excludes an event
if any token or AO vertex predates `max(session activation,cohort start)`.
This is an analysis-eligibility rule, not a change to emission, thresholds,
cooldown or mirrored hypotheses. Warmup is technical context only, never a
source of forward events or historical outcomes imported as observations.

The incremental port follows the existing MPL-2.0 public adapter (Koncorde
OskarGallard/Blai5 adaptation and The_Caretaker BBWP). Exact proprietary Bitman
indicator parity remains NOT PROVEN; source-formula equality is not that claim.

## Revision and crash policy

Every public receipt is content-addressed. Changed candle values append both
source references, twelve-column deltas and correction receipt/write times.
The parent becomes QUARANTINED; its original features/events/results stay intact.
The parent correction scope is disputed for primary analysis. After explicit
review, `child()` starts a new linked session using the accepted corrected
technical prefix. It keeps the same cohort window, imports zero old events and
excludes pre-child tokens. Original parent evidence must remain accessible.

Funding records retain original rate/mark/source and corrections/differences.
A previously absent mark becoming available with the same rate is an appended
completion, usable only for pending outcomes. A changed existing mark/rate is a
revision: quarantine/dispute, never silently replace an already published net
result. Unknown funding is not zero. Pending net outcomes are reconsidered only
on a new coverage generation, then become terminal UNKNOWN after48h from data
maturity. Future corrections require explicit amendment/review; they do not
automatically reopen favorable primary results. Final evaluation waits until
cohort end+73h to accommodate24h secondary outcomes, closed-H1 availability and
the48h funding deadline. Later evidence is a separate dated audit addendum.

The source-schema adapter also recognizes the documented optional
`rateType=Regular`, preserving original bytes. Special/unknown types fail closed;
no indicator or cashflow formula changes. See the
[official USD-M market-data reference](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data),
reviewed2026-11-16. V1's parser and hashes remain unchanged.

CAS writes use temporary files, file fsync and atomic rename. An incomplete
**uncommitted** blob can be moved into retained quarantine only after a valid
journal proves it is unreferenced, with an audit record. Committed bad/missing
blobs, broken chains or truncated JSONL are never repaired or truncated. Restore
a trusted independently versioned backup into a new empty root instead.

## Checkpoints and external trust

Weekly checkpoints bind the durable journal prefix/count/tip, session identity,
arrays and allowlisted state. Encoding is compressed JSON and float64 NPZ with
`allow_pickle=False`; no executable object loading. Source hashes and complete
chain/blob integrity are verified before restore. Prefix state restores exactly;
remaining records replay chronologically. Numerical arrays and both event streams
are compared against full frozen calculations in the load qualification.

An exported ZIP is **not an external ACK**. Real forward mode requires a reviewed
real-volume proof and independent-store ACK tied to the cohort hash. Anchors and
versioned backups must be outside the writer's failure/permission domain, at
least daily and after revisions/session forks/checkpoints. Local adapters/tests
do not establish cloud independence, IAM or WORM. An unanchored tail remains
exposed until the next independently retained anchor. Retain parents, revisions
and archived outcomes; do not silently purge history to save space.

`volume_probe.py` runs two separate Python processes only in an explicitly
approved empty scratch directory. No default `/data` path or remote command is
provided. The included result is LOCAL ONLY and always reports real-volume
attestation pending. No Railway/Bitunix/Telegram access occurred.

## Statistics and realistic sample limits

Primary: TURN22/Q75/net12h, three patterns and mirrors, six one-sided contrasts
with Holm, alpha0.05, MDE0.001 net fraction, power goal0.8. ALL/Q90, TURN11,
4/24h and observational facts remain exploratory. Never promote a better-looking
secondary result into the primary family.

For each primary event hour, subtract the mean of **all** eligible same-side
hours in its month/closed4H regime/causal volatility tercile, including events and
neighbors. Resample complete calendar7day blocks jointly for outcomes, labels
and that baseline; recompute means every replicate. This propagates shared
baseline uncertainty and overlapping-return dependence. Use effective n,
>=20 occupied blocks, >=95% valid replicates, >=24 baseline hours per cell,
>=95% capture/net coverage and auditable primary outcomes. Untestable cells keep
p=1 in the six-member Holm family. No automatic profitability/validation label.

The new power plan uses only already-inspected development data before2025,
not evaluation/November2026 outcomes or signal ranking. The audited dataset SHA
and exact selection recipe are recorded in `power.json` and `planning.py`.
Residual SD is about1.70/1.71percentage points; the predeclared conservative
planning sigma is4percentage points. This is a conditional noise/stress
assumption, not a guaranteed future variance bound. It requires16751 effective
events per contrast at the frozen MDE. A25h cooldown permits only351 events in
8760h (352 in a leap-year12month window), even before Q75. Therefore the fixed
design cannot become confirmatory in12months. **NO TESTABLE** is an expected
legitimate outcome; criteria/duration are not relaxed to manufacture power.

## Reproduction and qualification

Use Python3.12.12 and NumPy2.3.5 for numerical qualification. Generic inherited CI
is compatibility evidence, not a replacement for qualification in the pinned
deployment image. No deployment image or real volume has been exercised here.

```text
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.v2.test_v2 -v
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.v2.benchmark --out <new-output-directory>
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.v2.planning --npz <audited-5b2544c9-input> --out <new-planning-result>
```

The planning command refuses to overwrite sealed `power.json`. Load CSV/JSON are
**synthetic technical measurements**, not observations, trades or returns from
the market. See `REPORT.md`, `validation.json` and the reproducible audit package.

No merge. No deploy. No activation. No orders. Production remains untouched.
