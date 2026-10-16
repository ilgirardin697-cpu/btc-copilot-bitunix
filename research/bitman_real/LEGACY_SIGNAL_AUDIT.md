# LEGACY SIGNAL AUDIT — proposal only

Date: 2026-10-16. No service, variable, alert routing, source, artifact or Railway
setting is changed by this document. These are recommendations for later review,
not an executed cleanup. `DISABLE_ALERTS` never means delete code or evidence.

Primary repository evidence:

- Accepted PRE_BITMAN audit commit
  [`c1e015802f59baafbf04ee52228f216a391ead93`](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/c1e015802f59baafbf04ee52228f216a391ead93/PRE_BITMAN_AUDIT.md).
- Phase2 rejected, frozen PR #22 / commit
  [`44029b4768e2b4bc47643bb51bf8a28432623a39`](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/44029b4768e2b4bc47643bb51bf8a28432623a39/research/bitman/BITMAN_RESULTS.md).
- Current production forward-volume journals remain **PENDING / NOT ACCESSIBLE
  FROM CURRENT CONNECTOR**. Runtime health/logs are not substituted for outcomes.

| System / layer | Recommendation | Reason and boundary |
|---|---|---|
| **Trade Guardian** | **KEEP_ACTIVE** | Capital/liquidation protection, not an alpha signal. Preserve configured SHADOW/arming state; this audit neither enables PROTECT nor disables protection. Never remove it based on signal PnL. |
| **V8 SMA200 4H** | **KEEP_ACTIVE** | Retains positive historical OOS evidence. Accepted audit TEST +69.83%, Sharpe0.767; Phase2 common-ledger/later-cutoff comparator +66.55%, Sharpe0.732. Significant drawdown remains. Preserve its existing authorization, executor and notifications. KEEP_ACTIVE does not request enabling execution. No automatic replacement by this proxy. |
| **Manual Copilot** | **KEEP_AS_CONTEXT** | Human decision context and causal levels; no established prospective edge available to this audit. Distinguish direction from timing and from V8. Do not change commands/rules or automatically suppress its current messages. |
| **Copilot Forward Audit** | **KEEP_ACTIVE** | Prospective evidence collection is necessary. It is telemetry, not entry authority. Continue retaining confirmed episodes and mature/censored outcomes. No fabricated backfill. |
| **ML RSI LOW29/EMA4 MTF confirmed observer** | **RESEARCH_ONLY** | Exact TV parity is not universally proven; old LOW27 results do not validate this configuration. Preserve math/recovery/journals; do not grant entry authority. Confirmed events are useful data collection, not proven alpha. |
| **ML RSI APPROACHING / PROVISIONAL duplicate-style notifications** | **DISABLE_ALERTS** (proposal for review) | They are not closed confirmations or demonstrated incremental edge. If they mainly repeat direction context, retain telemetry/manual status but consider suppressing outbound noise. No actual flag or alert change is made here. |
| **ML RSI 1H historical LOW27 GREEN_RESUME** | **RESEARCH_ONLY** | INTERESTING BUT INCONCLUSIVE; not a universal standalone signal or evidence for LOW29. Require exact-version forward cohorts. |
| **ML RSI 15m tested management hypothesis** | **ARCHIVE** | Frozen NO EDGE. Keep study/data/artifacts; do not revive as a generator without a new preregistered hypothesis. |
| **Early Breakout automatic notifications** | **DISABLE_ALERTS** (proposal only, if running) | Existing research result NO EDGE. No established incremental information. Preserve observer source and outcomes; no service is stopped in this delivery. |
| **Early Breakout historical artifacts** | **ARCHIVE** | Preserve negative evidence. Do not silently reuse its features as BITMAN gates. |
| **Confluence D60** | **RESEARCH_ONLY** | Positive archived TEST +68.76%, but 55%/65% neighbors negative; archived2026 −7.33%, PF0.755. Not robust enough to replace V8. Later-cutoff common-ledger results do not erase fragility. |
| **BITMAN Phase2 CLASSIC / FUSION** | **ARCHIVE** | Official REJECT. LONG TEST −14.43%; SHORT −68.34%; all28 neighbors negative expectancy. Keep PR #22 unmerged and all artifacts immutable. Data reuse here does not reuse its strategy. |
| **V8 BEAR SHORT A–G** | **ARCHIVE** | Rejected independent historical hypotheses. Do not relabel their inversion as a new SHORT. |
| **DATA / visibility telemetry observers** | **KEEP_AS_CONTEXT** | Availability/freshness/correctness diagnostics can add operational value without forecasting price. Keep them separate from alpha claims; no production-hook changes. |
| **Other generic SHADOW/paper strategy alerts without demonstrated edge** | **RESEARCH_ONLY** | Inventory and evaluate exact config-version journals first. If messages merely duplicate existing context, propose DISABLE_ALERTS after measuring that duplication; do not presume every observer is redundant. |
| **BITMAN REAL OBSERVER v0.1** | **RESEARCH_ONLY** | New public-proxy event study, not private-indicator parity or a trading replacement. SHORT_LOGIC_NOT_PROVEN. No integration/deployment/sending here. |

## How to assess incremental information later

Import copies of actual journals, retaining config version, TF, confirmed versus
provisional, observation time and mature horizons. Measure: paired event-minus-
control outcomes, overlap with Copilot/V8 confirmations, lead/lag, distinct events
per day and repeated alerts per episode. Keep pending outcomes censored.

Only then can a low-value alert be distinguished from useful lead information.
Without these journals, the table's noise recommendations are proposals grounded
in historical failures or lack of verified confirmation, not claims that live
incrementality has already been measured.

## V8 comparison before any replacement

The BITMAN report includes the archived common-data V8 benchmark and a fresh
descriptive V8 closed4H signal-event table. Price-event returns are **not** the
same quantity as a net funded strategy return. This observer has no executable
entry/exit/cost/margin model; it cannot claim to outperform or replace V8. Positive
V8 historical evidence is retained, with its drawdown and forward limitations.

**No cleanup performed. NO MERGE. NO DEPLOY. NO REAL ORDER.**
