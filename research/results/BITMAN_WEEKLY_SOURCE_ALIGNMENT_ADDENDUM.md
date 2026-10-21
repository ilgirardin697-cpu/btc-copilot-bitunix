# BITMAN weekly source-alignment addendum

**POST-HOC SOURCE ALIGNMENT — NOT PREDECLARED VALIDATION. NO VIRGIN HOLDOUT.**

**INDEPENDENT TRANSCRIPT REVIEWED EXTERNALLY AFTER PREDECLARED ANALYSIS**

**SOURCE-ALIGNED SENSITIVITY STILL INCONCLUSIVE**

The original **PREDECLARED STRICT SAME-WEEK MODEL** remains intact with its original **INCONCLUSIVE** conclusion. This addendum reports all requested lag windows (0, <=1, <=2), without selecting a winner or recommending runtime integration.

## 1. Corrected source audit and limits of access

After the original analysis, the owner reports recovering an independent transcript of [the source video](https://www.youtube.com/watch?v=v8d3OxE1-_c), especially from approximately minute20 onward. This agent has **no direct access** to that recovered transcript. The following points are attributed to the owner's external review; they are paraphrases, not invented quotations or independent verification by this agent.

- The explanation applies specifically to WEEKLY candles and centers on oscillator plus volatility.
- ADX is set aside in this explanation; volatility may help anticipate an ADX turn. That is a reported conceptual claim, not an ADX lead/lag result measured here. No ADX gate was added.
- Above zero, GREEN with growing volatility describes impulse; RED with falling volatility describes correction.
- Below zero, RED with growing volatility describes bearish impulse; GREEN with falling volatility describes correction.
- After corrective weeks, momentum can resume without crossing zero, or zero can be crossed before expansion in the new direction.
- The review reports approximately1–2 weeks between oscillator change and volatility recovery, motivating this timing sensitivity.

The source audit now marks transcript recovery as **external**, with `agent_direct_transcript_access=false`, `part_of_predeclared_protocol=false`, and the exact external-review status above. It retains the original audit's false recovery flag inside `predeclared_audit_state`, rather than rewriting what was known then. No full transcript, long quotes, new paid retrieval or vidIQ credits. Verbal alignment can now be assessed against the supplied external review; on-screen dates/settings and private formulas still cannot.

**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**

**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**

The oscillator remains AO as OSCILLATOR_PROXY; frozen BBWP remains BITMAN_VOLATILITY_PROXY. The transcript review does not establish formula equivalence, statistical predictive value, or an untouched holdout.

## 2. What changed, and the fixed causal interpretation

[Post-hoc definitions](BITMAN_WEEKLY_SOURCE_ALIGNMENT_PROTOCOL.md) were recorded before calculating these new lag outcomes, after the original history/results were already known. That does **not** make this a predeclared out-of-sample experiment.

At an observed oscillator color return after a pullback or strict zero crossing, latch one candidate. If volatility already meets the original condition at that close, emit immediately. Otherwise wait at most1or2 subsequent closed weeks for the first TURN_UP. A delayed event is timestamped at that confirmation, with its range, close and ATR frozen then. Price movement during the wait is excluded from forward outcomes. This is oscillator-first, non-negative lag; no symmetric retrospective match or event backdating.

A reacceleration candidate must keep its zero sign and returned impulse color; a new correction cancels that return. A zero-cross candidate must retain its new strict zero sign. No independent color gate is added to zero-cross resolution because the original zero-cross definition did not have one; its resolution color is published. Invalid weeks, zero/opposite sign and expiry cancel pending candidates. An expired candidate is never reanimated. A pending zero-cross owns its resolution over a same-side color-return activation, preventing duplicate episodes. These are explicit formalization choices, not claimed transcript-exact private rules.

Lag0 is tested against the original seven timestamps, sides and types. The original zero-cross accepts already ACTIVE_RISING at the cross even without a fresh TURN_UP; this is preserved. Only delayed resolution requires a fresh TURN_UP. No lag3/4/5, new lengths, thresholds, indicator fitting, or winning-window selection.

## 3. Same dataset and unchanged outcomes

Reuse the same audited BTCUSDT BINANCE_USDM_PERPETUAL snapshot:371 closed Monday-UTC weekly candles,263 eligible weeks, first eligible availability2021-10-11, cutoff2026-10-19T00:00UTC. No new market data or venue substitution. The original strict protocol, classifier, outcome math and numerical artifacts are hash-frozen (14files in `bitman_weekly_source_alignment/strict_baseline.json`). Only source documentation/metadata and separate addendum outputs change.

Primary endpoint remains N=4 trailing closed weeks including the confirmation candle, horizon4W, weekly CLOSE exit plus >=10% excursion from confirmation close in the same breaking direction. All original N=2/4/8 and1/2/3/4W combinations are published, with the existing5/10/15/20% and ATR outcome fields. No endpoint recalibration. Partial forward horizons stay missing. Recall/false negatives concern overlapping weekly **anchors**, not distinct market moves.

## 4. Episode counts — why the strict model found only seven

| Model | Total | REACC_UP | REACC_DOWN | ZERO_CROSS_UP | ZERO_CROSS_DOWN | Actual lag0/1/2 |
| --- | --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | 7 | 2 | 2 | 2 | 1 | 7/0/0 |
| LAG_LE1 | 11 | 3 | 4 | 2 | 2 | 7/4/0 |
| LAG_LE2 | 13 | 3 | 4 | 3 | 3 | 7/4/2 |

The strict timing requirement does exclude additional proxy episodes: four first confirm one week after oscillator activation and two first confirm two weeks after. It is therefore part of the reason for n=7, but it does not by itself explain missing private-indicator examples or establish that a longer lag predicts better. All strict events are retained in both sensitivities on this dataset. Counts from separate models must never be pooled into31 independent signals.

| Sensitivity | New confirmation UTC | Family |
| --- | --- | --- |
| LAG_LE1 | 2022-01-24 | ZERO_CROSS_DOWN_EXPANSION |
| LAG_LE1 | 2022-03-21 | REACCELERATION_DOWN |
| LAG_LE1 | 2022-05-09 | REACCELERATION_DOWN |
| LAG_LE1 | 2025-04-28 | REACCELERATION_UP |
| LAG_LE2 | 2022-01-24 | ZERO_CROSS_DOWN_EXPANSION |
| LAG_LE2 | 2022-03-21 | REACCELERATION_DOWN |
| LAG_LE2 | 2022-05-09 | REACCELERATION_DOWN |
| LAG_LE2 | 2024-09-23 | ZERO_CROSS_DOWN_EXPANSION |
| LAG_LE2 | 2024-11-11 | ZERO_CROSS_UP_EXPANSION |
| LAG_LE2 | 2025-04-28 | REACCELERATION_UP |

Each activation/confirmation pair, actual lag, correction duration, complete proxy sequence, cancellation/expiry and ignored duplicate activation is in `analysis.json`. Every model has one event per resolved sequence and no same-timestamp duplicates. Greedy non-overlap4W counts are STRICT_SAME_WEEK:7, LAG_LE1:11, LAG_LE2:13. Opportunity labels still overlap.

## 5. All three models — primary4W results

| Model | n | Precision | Base rate | Lift | Recall | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | 7 | 14.29% | 49.42% | 0.289 | 0.78% | 1 | 6 | 127 |
| LAG_LE1 | 11 | 36.36% | 49.42% | 0.736 | 3.12% | 4 | 7 | 124 |
| LAG_LE2 | 13 | 38.46% | 49.42% | 0.778 | 3.91% | 5 | 8 | 123 |

| Model | Max mean/median % | Signed mean/median % | Terminal directional hit | Conditional first-break accuracy (n) | Unconditional correct break |
| --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | 12.128 / 8.822 | 2.687 / -0.503 | 42.86% | 100.00% (2) | 28.57% |
| LAG_LE1 | 15.409 / 16.817 | 4.110 / 0.786 | 54.55% | 80.00% (5) | 36.36% |
| LAG_LE2 | 16.065 / 16.817 | 4.805 / 0.786 | 53.85% | 71.43% (7) | 38.46% |

Direction is measured separately from magnitude. Conditional first-break accuracy excludes no-close-break observations and must be read with its small denominator; the unconditional rate includes those censored/non-breaking opportunities. A large move in the wrong direction can satisfy the magnitude label without directional success.

| Model | Precision CI95 | Signed mean CI95 % | Signed median % | Sample status |
| --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | NA / NA | NA / NA | -0.503 | INSUFFICIENT FOR CONCLUSION |
| LAG_LE1 | 8.33% / 66.67% | -1.974 / 10.267 | 0.786 | INSUFFICIENT FOR CONCLUSION |
| LAG_LE2 | 11.08% / 66.67% | -1.434 / 11.052 | 0.786 | INSUFFICIENT FOR CONCLUSION |

Original2000 circular8-week calendar-block bootstrap retained, root seed20261020 plus horizon. Shared calendar draws are used for each model; no IID resampling of episode rows. Main strict n7 intervals remain NA under the original minimum n10 rule. Both sensitivity signed-return intervals include zero; all model n are below30. Intervals are descriptive/unadjusted, not post-hoc validation.

## 6. UP/DOWN and family results

| Model | Group | n | Precision | Signed mean % | Terminal hit |
| --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | UP | 4 | 25.00% | 5.153 | 50.00% |
| STRICT_SAME_WEEK | DOWN | 3 | 0.00% | -0.602 | 33.33% |
| STRICT_SAME_WEEK | REACCELERATION_UP | 2 | 0.00% | -5.874 | 0.00% |
| STRICT_SAME_WEEK | REACCELERATION_DOWN | 2 | 0.00% | 0.142 | 50.00% |
| STRICT_SAME_WEEK | ZERO_CROSS_UP_EXPANSION | 2 | 50.00% | 16.181 | 100.00% |
| STRICT_SAME_WEEK | ZERO_CROSS_DOWN_EXPANSION | 1 | 0.00% | -2.089 | 0.00% |
| LAG_LE1 | UP | 5 | 40.00% | 7.380 | 60.00% |
| LAG_LE1 | DOWN | 6 | 33.33% | 1.385 | 50.00% |
| LAG_LE1 | REACCELERATION_UP | 3 | 33.33% | 1.512 | 33.33% |
| LAG_LE1 | REACCELERATION_DOWN | 4 | 50.00% | 4.076 | 75.00% |
| LAG_LE1 | ZERO_CROSS_UP_EXPANSION | 2 | 50.00% | 16.181 | 100.00% |
| LAG_LE1 | ZERO_CROSS_DOWN_EXPANSION | 2 | 0.00% | -3.995 | 0.00% |
| LAG_LE2 | UP | 6 | 50.00% | 10.459 | 66.67% |
| LAG_LE2 | DOWN | 7 | 28.57% | -0.040 | 42.86% |
| LAG_LE2 | REACCELERATION_UP | 3 | 33.33% | 1.512 | 33.33% |
| LAG_LE2 | REACCELERATION_DOWN | 4 | 50.00% | 4.076 | 75.00% |
| LAG_LE2 | ZERO_CROSS_UP_EXPANSION | 3 | 66.67% | 19.405 | 100.00% |
| LAG_LE2 | ZERO_CROSS_DOWN_EXPANSION | 3 | 0.00% | -5.528 | 0.00% |

## 7. Best-event influence — both fixed criteria

| Model | Rank by | Remove | n left | Max mean % | Signed mean % | Precision | Removed confirmation dates |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | max_move | 0 | 7 | 12.128 | 2.687 | 14.29% | [] |
| STRICT_SAME_WEEK | max_move | 1 | 6 | 9.414 | -0.976 | 0.00% | ['2023-10-23T00:00:00+00:00'] |
| STRICT_SAME_WEEK | max_move | 3 | 4 | 7.451 | 1.677 | 0.00% | ['2023-10-23T00:00:00+00:00', '2025-10-06T00:00:00+00:00', '2025-11-24T00:00:00+00:00'] |
| STRICT_SAME_WEEK | signed | 0 | 7 | 12.128 | 2.687 | 14.29% | [] |
| STRICT_SAME_WEEK | signed | 1 | 6 | 9.414 | -0.976 | 0.00% | ['2023-10-23T00:00:00+00:00'] |
| STRICT_SAME_WEEK | signed | 3 | 4 | 10.000 | -3.585 | 0.00% | ['2023-10-23T00:00:00+00:00', '2026-09-07T00:00:00+00:00', '2022-09-19T00:00:00+00:00'] |
| LAG_LE1 | max_move | 0 | 11 | 15.409 | 4.110 | 36.36% | [] |
| LAG_LE1 | max_move | 1 | 10 | 14.108 | 2.055 | 30.00% | ['2023-10-23T00:00:00+00:00'] |
| LAG_LE1 | max_move | 3 | 8 | 11.599 | 1.792 | 25.00% | ['2023-10-23T00:00:00+00:00', '2022-01-24T00:00:00+00:00', '2022-05-09T00:00:00+00:00'] |
| LAG_LE1 | signed | 0 | 11 | 15.409 | 4.110 | 36.36% | [] |
| LAG_LE1 | signed | 1 | 10 | 14.108 | 2.055 | 30.00% | ['2023-10-23T00:00:00+00:00'] |
| LAG_LE1 | signed | 3 | 8 | 12.481 | -0.981 | 12.50% | ['2023-10-23T00:00:00+00:00', '2025-04-28T00:00:00+00:00', '2022-05-09T00:00:00+00:00'] |
| LAG_LE2 | max_move | 0 | 13 | 16.065 | 4.805 | 38.46% | [] |
| LAG_LE2 | max_move | 1 | 12 | 14.894 | 3.051 | 33.33% | ['2024-11-11T00:00:00+00:00'] |
| LAG_LE2 | max_move | 3 | 10 | 12.377 | 1.785 | 30.00% | ['2024-11-11T00:00:00+00:00', '2023-10-23T00:00:00+00:00', '2022-01-24T00:00:00+00:00'] |
| LAG_LE2 | signed | 0 | 13 | 16.065 | 4.805 | 38.46% | [] |
| LAG_LE2 | signed | 1 | 12 | 14.894 | 3.051 | 33.33% | ['2024-11-11T00:00:00+00:00'] |
| LAG_LE2 | signed | 3 | 10 | 13.082 | -0.433 | 20.00% | ['2024-11-11T00:00:00+00:00', '2023-10-23T00:00:00+00:00', '2025-04-28T00:00:00+00:00'] |

Both magnitude-ranked and signed-return-ranked best1/best3 exclusions are reported, including their dates; none is selected as a preferred interpretation. Per-era/per-regime influence rows are also published.

## 8. Eras and original causal regimes

| Model | Scope | n | Precision | Local base | Lift | Signed mean % | Max mean % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | 2020-2022 | 1 | 0.00% | 53.12% | 0.000 | 0.786 | 7.662 |
| STRICT_SAME_WEEK | 2023-2024 | 2 | 50.00% | 53.33% | 0.938 | 11.696 | 16.491 |
| STRICT_SAME_WEEK | 2025-2026 | 4 | 0.00% | 42.22% | 0.000 | -1.343 | 11.063 |
| STRICT_SAME_WEEK | BULL | 4 | 25.00% | 50.79% | 0.492 | 5.153 | 14.889 |
| STRICT_SAME_WEEK | BEAR | 3 | 0.00% | 48.12% | 0.000 | -0.602 | 8.446 |
| LAG_LE1 | 2020-2022 | 4 | 50.00% | 53.12% | 0.941 | 2.726 | 18.193 |
| LAG_LE1 | 2023-2024 | 2 | 50.00% | 53.33% | 0.938 | 11.696 | 16.491 |
| LAG_LE1 | 2025-2026 | 5 | 20.00% | 42.22% | 0.474 | 2.183 | 12.748 |
| LAG_LE1 | BULL | 6 | 50.00% | 50.79% | 0.984 | 6.801 | 15.977 |
| LAG_LE1 | BEAR | 5 | 20.00% | 48.12% | 0.416 | 0.881 | 14.726 |
| LAG_LE2 | 2020-2022 | 4 | 50.00% | 53.12% | 0.941 | 2.726 | 18.193 |
| LAG_LE2 | 2023-2024 | 4 | 50.00% | 53.33% | 0.938 | 10.163 | 18.084 |
| LAG_LE2 | 2025-2026 | 5 | 20.00% | 42.22% | 0.474 | 2.183 | 12.748 |
| LAG_LE2 | BULL | 8 | 50.00% | 50.79% | 0.984 | 7.258 | 16.902 |
| LAG_LE2 | BEAR | 5 | 20.00% | 48.12% | 0.416 | 0.881 | 14.726 |

The first era is truncated by long weekly warmup (no eligible2020 and only late2021 onward). Bull/bear remains the original last closed4H close versus causal SMA200 at confirmation time, not retrospective market labels. Small side/era cells cannot establish stable predictive value.

## 9. Horizon/range sensitivity — no winning cell

| Model | N | Horizon W | n | Precision | Base | Lift | Max mean % | Signed mean % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STRICT_SAME_WEEK | 4 | 1 | 7 | 14.29% | 13.36% | 1.069 | 9.202 | -0.046 |
| STRICT_SAME_WEEK | 4 | 2 | 7 | 14.29% | 27.20% | 0.525 | 9.962 | 0.372 |
| STRICT_SAME_WEEK | 4 | 3 | 7 | 14.29% | 38.46% | 0.371 | 11.944 | 3.585 |
| STRICT_SAME_WEEK | 4 | 4 | 7 | 14.29% | 49.42% | 0.289 | 12.128 | 2.687 |
| STRICT_SAME_WEEK | 2 | 1 | 7 | 14.29% | 16.41% | 0.870 | 9.202 | -0.046 |
| STRICT_SAME_WEEK | 2 | 2 | 7 | 14.29% | 31.03% | 0.460 | 9.962 | 0.372 |
| STRICT_SAME_WEEK | 2 | 3 | 7 | 14.29% | 46.15% | 0.310 | 11.944 | 3.585 |
| STRICT_SAME_WEEK | 2 | 4 | 7 | 14.29% | 59.85% | 0.239 | 12.128 | 2.687 |
| STRICT_SAME_WEEK | 8 | 1 | 7 | 14.29% | 11.45% | 1.248 | 9.202 | -0.046 |
| STRICT_SAME_WEEK | 8 | 2 | 7 | 14.29% | 20.69% | 0.690 | 9.962 | 0.372 |
| STRICT_SAME_WEEK | 8 | 3 | 7 | 14.29% | 30.77% | 0.464 | 11.944 | 3.585 |
| STRICT_SAME_WEEK | 8 | 4 | 7 | 14.29% | 39.77% | 0.359 | 12.128 | 2.687 |
| LAG_LE1 | 4 | 1 | 11 | 27.27% | 13.36% | 2.042 | 10.359 | -0.891 |
| LAG_LE1 | 4 | 2 | 11 | 36.36% | 27.20% | 1.337 | 12.555 | -0.424 |
| LAG_LE1 | 4 | 3 | 11 | 36.36% | 38.46% | 0.945 | 14.775 | 3.086 |
| LAG_LE1 | 4 | 4 | 11 | 36.36% | 49.42% | 0.736 | 15.409 | 4.110 |
| LAG_LE1 | 2 | 1 | 11 | 27.27% | 16.41% | 1.662 | 10.359 | -0.891 |
| LAG_LE1 | 2 | 2 | 11 | 36.36% | 31.03% | 1.172 | 12.555 | -0.424 |
| LAG_LE1 | 2 | 3 | 11 | 36.36% | 46.15% | 0.788 | 14.775 | 3.086 |
| LAG_LE1 | 2 | 4 | 11 | 36.36% | 59.85% | 0.608 | 15.409 | 4.110 |
| LAG_LE1 | 8 | 1 | 11 | 27.27% | 11.45% | 2.382 | 10.359 | -0.891 |
| LAG_LE1 | 8 | 2 | 11 | 36.36% | 20.69% | 1.758 | 12.555 | -0.424 |
| LAG_LE1 | 8 | 3 | 11 | 36.36% | 30.77% | 1.182 | 14.775 | 3.086 |
| LAG_LE1 | 8 | 4 | 11 | 36.36% | 39.77% | 0.914 | 15.409 | 4.110 |
| LAG_LE2 | 4 | 1 | 13 | 30.77% | 13.36% | 2.303 | 10.360 | -0.089 |
| LAG_LE2 | 4 | 2 | 13 | 38.46% | 27.20% | 1.414 | 12.918 | 1.413 |
| LAG_LE2 | 4 | 3 | 13 | 38.46% | 38.46% | 1.000 | 14.907 | 4.310 |
| LAG_LE2 | 4 | 4 | 13 | 38.46% | 49.42% | 0.778 | 16.065 | 4.805 |
| LAG_LE2 | 2 | 1 | 13 | 30.77% | 16.41% | 1.875 | 10.360 | -0.089 |
| LAG_LE2 | 2 | 2 | 13 | 38.46% | 31.03% | 1.239 | 12.918 | 1.413 |
| LAG_LE2 | 2 | 3 | 13 | 38.46% | 46.15% | 0.833 | 14.907 | 4.310 |
| LAG_LE2 | 2 | 4 | 13 | 38.46% | 59.85% | 0.643 | 16.065 | 4.805 |
| LAG_LE2 | 8 | 1 | 13 | 30.77% | 11.45% | 2.687 | 10.360 | -0.089 |
| LAG_LE2 | 8 | 2 | 13 | 38.46% | 20.69% | 1.859 | 12.918 | 1.413 |
| LAG_LE2 | 8 | 3 | 13 | 38.46% | 30.77% | 1.250 | 14.907 | 4.310 |
| LAG_LE2 | 8 | 4 | 13 | 38.46% | 39.77% | 0.967 | 16.065 | 4.805 |

All outcome fields and cohort counts are available in `metrics.csv` and per-episode `observations.csv`. Original proxy and range-definition limitations remain; no open weeks, future pivots or forward-filled candles.

## 10. Current closed-week classification — no signal

**CURRENT OBSERVATION — NOT PART OF VALIDATION**

Last closed week remains2026-10-12 →2026-10-19UTC. The current open week is excluded. AO above zero/GREEN10698.622, slope+348.994; volatility proxy41→30, slope−11, COOLING/noTURN_UP. The fixed4W range remains79732.3–87385.1.

| Model | Current state | Pending candidate | LARGE MOVE WATCH |
| --- | --- | --- | --- |
| STRICT_SAME_WEEK | OTHER | NONE | NOT VALIDATED |
| LAG_LE1 | OTHER | NONE | NOT VALIDATED |
| LAG_LE2 | OTHER | NONE | NOT VALIDATED |

**LARGE MOVE WATCH: NOT VALIDATED**. No directional, operational or trade signal is emitted.

## 11. Interpretation and preserved strict result

**SOURCE-ALIGNED SENSITIVITY STILL INCONCLUSIVE**

Temporal tolerance recovers additional historically observed proxy configurations and improves the descriptive precision versus strict. It remains below the same four-week base rate for both sensitivity models, with small n and signed-return intervals spanning zero. The source review improves fidelity to the reported verbal timing, not evidence of private formula parity or validated prediction. No best lag is recommended.

The original strict conclusion remains **INCONCLUSIVE** and all strict numerical files are unchanged. **POST-HOC SOURCE ALIGNMENT. NO VIRGIN HOLDOUT.** Any further step would require a separately fixed forward observation protocol, not runtime integration from these historical outcomes.

Reproduce offline: `python -m research.bitman_state_source_alignment`, then `python -m research.bitman_source_alignment_reporting`. Original report/source-audit metadata updates can be regenerated with `python -m research.bitman_state_reporting`; the old strict numerical analysis need not be rerun.

No changes to production modules, frozen engine, operational gates, renderer, Guardian, V8, ML RSI, market data, Telegram, risk/execution or Railway. No merge. No deployment. No orders. **TRADE AUTHORITY: NONE.**
