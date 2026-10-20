# Weekly sequential proxy study — pre-analysis protocol

Protocol fixed before new episode/outcome analysis. This is a new study, not a revision of PR #30.
Base: `9c660035f912be4640f09cf6e2d4c48583c20b04`. No runtime changes, trading authority, merge, deployment or Railway changes.

## Source and what is unknown

Conceptual source: https://www.youtube.com/watch?v=v8d3OxE1-_c (owner review, approximately 20 minutes onward). The owner describes weekly positive-side impulse/correction/reacceleration, its negative-side mirror, and zero crossings accompanied by expansion. The owner reports that the volatility indicator is modified. This account is the source of the hypothesis; it is not independent verification of the video or a recovered formula. Public page/caption access and existing transcript caches will be audited separately. Existing four cached transcripts are other videos. No new vidIQ credits.

AO is **OSCILLATOR_PROXY**. Frozen weekly BBWP is **BITMAN_VOLATILITY_PROXY**.

**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**

**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**

No private parameters, visual fitting, parameter search or inference of hidden formulas. Visual examples require independently identifiable chart dates; otherwise mark NOT ASSESSABLE, not a successful parity check. A demonstrated mismatch permits PROXY MISMATCH; inability to obtain the source does not itself prove mismatch.

## Fixed data and formulas

Reuse the audited public USD-M snapshot of PR #30 (`c1c56bd1c4c87ad0f279616970ec9f13ae373302`), without altering that PR. BTCUSDT, BINANCE_USDM_PERPETUAL, official `/fapi/v1/klines`; cutoff 2026-10-19 00:00 UTC. No new history/outcomes are acquired to extend the sample. Monday 00:00 to Monday 00:00 UTC, complete closed weeks only, assembled from exactly 42 contiguous 4H candles. Drop the initial partial week. Preserve the original source discrepancy manifest.

Use unmodified `bitman_manual.frozen.indicators.calculate`: AO = SMA5((H+L)/2) - SMA34((H+L)/2); GREEN iff one-week AO difference >0, RED iff <0, FLAT iff =0. Sign and color are distinct. BB width = 4*population_std(C,7)/SMA(C,7); BBWP is the percentage of 100 prior widths strictly below the current width in a complete 101-observation window. Slopes are one-week differences. ATR is existing causal Wilder14 ATR, not a fitted parameter. Common eligible weeks require finite AO/current and prior AO slope, BBWP/current and prior slope, ATR and ranges. Warmup/unknowns never become states. No rounding before classifications.

Existing causal regime only: last closed 4H close versus its trailing SMA200 at the signal's weekly close. Unknown/flat remain separate. Eras by signal availability: through 2022, 2023–2024, 2025–cutoff. The first era has no usable 2020 and only late 2021 onward; disclose this.

## States and causal episodes

Base states: IMPULSE_UP = AO>0/GREEN/vol slope>0; PULLBACK_UP = AO>0/RED/vol slope<=0; IMPULSE_DOWN = AO<0/RED/vol slope>0; PULLBACK_DOWN = AO<0/GREEN/vol slope<=0. All other valid combinations are OTHER, with zero and flat explicitly retained.

REACCELERATION_UP requires an uninterrupted immediately preceding run of >=1 PULLBACK_UP weeks, positive AO throughout that run and signal, previous RED/current GREEN and previous vol slope<=0/current>0. Mirror for DOWN. No hidden requirement that a prior impulse was observed; record it as metadata. A gap, OTHER, zero, opposite sign or invalid week breaks the run. Duration >=1/2/3 and exact 1/2/3/>=4 are all reported, never selected.

ZERO_CROSS_UP_EXPANSION = previous AO<0/current>0 and current vol slope>0; DOWN mirrors. The cross and expansion must coincide at the same closed week. Report TURN_UP vs already ACTIVE_RISING separately. Zero equality is neither strict cross. No future delayed-expansion matching. State priority: reacceleration, zero-cross, base state, OTHER/UNKNOWN. A reacceleration also satisfies a base impulse; precedence prevents double counting.

The primary signal is the union of the four reacceleration/zero-cross states, each counted once at its closed-week timestamp. A pullback run plus its resolution is one episode. Persistent impulse weeks are not new signals. Record start/end, pullback count, full sign/color/volatility sequence, earlier impulse availability and range. Standalone contiguous base-state runs are descriptive episodes, not extra primary predictions. Unresolved pullbacks remain censored, not successes/failures.

Volatility flags: ACTIVE_RISING (>0), TURN_UP (prior<=0/current>0), SUSTAINED_TURN (>=2 immediately preceding non-rising weeks/current>0), COOLING (<0), FLAT (=0). Nested flags are intentional. Level50: >50, <=50, strict upward crossing (prior<=50/current>50), downward crossing (prior>=50/current<50), falling through50 (=downward cross plus falling), TURN_UP at current<=50 vs>50. Exact50 belongs below/equal; no winner selection.

## Frozen causal range and outcomes

Primary range: high/low of the **last 4 completely closed weekly candles including the signal candle**, frozen at signal availability. This is the prior range relative to the future observation window. It contains signal close and avoids counting a breakout already completed on the signal candle. Sensitivities N=2 and N=8 use exactly the same definition; report all, never pick a winner. This is a transparent rolling range, not a claim that congestion was present. Report range width/ATR and a descriptive congestion flag width<=2*ATR, without selecting it as a rule. No fitted ATR congestion or future-confirmed pivots.

Horizons 1/2/3/4 subsequent complete weeks. Entry/measurement anchor = signal weekly close; **not executable trade performance**. Main breakout is first subsequent weekly CLOSE strictly outside the frozen range; time-to-event is 1–4 weeks, censored at 4 if none. Wicks are secondary; same-week touches of both boundaries are BOTH/ORDER_UNKNOWN, never an invented order. Report end-close outside, any later close back inside (or opposite side), and no-reentry sustained breakout; a breakout on the horizon's last week has zero followup and cannot establish persistence.

Magnitude: terminal raw/signed return, up/down/max absolute high-low excursion from anchor, side-aligned favorable/adverse excursions, distance beyond frozen boundaries in percent of anchor and ATR, max excursion/ATR, and frequencies >=5/10/15/20 percent and >=1/1.5/2 ATR. ATR is fixed at signal. Do not infer intraweek first-touch ordering.

Primary binary label **large weekly breakout**: at least one future weekly CLOSE beyond a frozen boundary AND excursion from signal close >=10% in that same boundary's direction within the horizon. Both must occur by the horizon, but their intrahorizon order is not inferred. Also report every requested percentage and ATR threshold, and plain close/wick breakouts. No choice of best label. Direction success = first CLOSE breakout matches episode side; no breakout is a failure for unconditional precision and excluded only in the explicitly conditional directional rate. Signed terminal returns and opposite breakouts reported separately.

Primary pooled estimand N=4/horizon4; all other horizons/ranges are sensitivity, not tuning. Late unobserved horizons are censored (NaN), never negatives. Recall/base-rate denominator: all valid matured weekly opportunity timestamps, not only signal weeks. This is **anchor-level event recall**, not recall of unique market moves: overlapping targets can describe the same move. Publish additional chronological nonoverlap event windows and phase1-in4 opportunity controls. No claim of independent weekly observations.

## Controls, inference and falsification

Baselines: all valid weeks; same oscillator sign; same color; vol TURN_UP without oscillator condition; pullback weeks without reacceleration; same-sign/color separately. Report persistent-week exposure controls explicitly as opportunities, not independent episodes. Compare one signal per contiguous baseline run as an episode sensitivity. Fixed calendar phases index%4=0/1/2/3 are temporal controls. Trailing52-week control outcomes must be fully mature at signal time (>=12 available controls); no future matching. No random rule search.

Estimate n, mean, median, sd, quantiles, confidence intervals, frequency, precision/recall/base-rate/lift. Use paired circular moving-block bootstrap of the complete chronological opportunity grid, 2,000 replicates, seed20261020, block8 weeks. Sensitivity blocks4/12 (not selected). Resample calendar blocks, never treat episode rows as IID. If n<10 or fewer than95% replicates have a finite statistic, CI unavailable. n<30 = INSUFFICIENT FOR CONCLUSION. CIs descriptive/unadjusted across many comparisons; no confirmatory p-values.

Remove best1/best3 episodes by max excursion and separately by signed return; recompute signal metrics/contrasts and publish excluded dates. Record overlap clusters and greedy windows retaining the first signal and rejecting subsequent signals <=4 weeks apart. Report eras and frozen causal regimes. No optimized subset.

Mandatory falsifications: vol TURN_UP without large move; reacceleration UP followed by negative terminal return/opposite breakout; DOWN followed by positive/opposite; large moves during falling vol; large breakouts without a setup at that opportunity. Publish counts and dated cases, not only selected successes. False negative denominator is the same anchor-level label; unique future-market-event coverage cannot be inferred from overlapping weekly labels.

## Interpretation fixed before outcomes

NO VIRGIN HOLDOUT. PR #30 already exposed this history; committing this protocol now does not restore an untouched holdout. Historical re-downloads are not real forward observed signal journals.

Robust magnitude requires adequate pooled n>=30, positive paired lift CI against all-weeks and vol-turn controls, positive lift after best3 removal, no contradictory sufficiently populated era, and consistency over ranges/horizons/nonoverlap sensitivity. Robust direction additionally requires signed/conditional directional incremental evidence over same-sign and same-color controls with CIs excluding no effect, positive best3 result and temporal consistency. Insufficient precision/sample or contradictory periods prevents a robust designation. Proxy uncertainty remains even if statistics look strong.

Allowed conclusions only: STATE-MACHINE EFFECT ROBUST — FORWARD VALIDATION REQUIRED; MAGNITUDE EFFECT PRESENT — DIRECTION INCONCLUSIVE; STATE-MACHINE EFFECT FRAGILE; PROXY MISMATCH — CANNOT TEST BITMAN CLAIM; INCONCLUSIVE. A future rule is at most HYPOTHESIS FOR FORWARD OBSERVATION. **No historical result authorizes runtime integration.**

Latest closed week: separate CURRENT OBSERVATION — NOT PART OF VALIDATION; show proxy sign/color, volatility/turn, sequence, frozen ranges and Large move watch: NOT VALIDATED. Never use the open week.
