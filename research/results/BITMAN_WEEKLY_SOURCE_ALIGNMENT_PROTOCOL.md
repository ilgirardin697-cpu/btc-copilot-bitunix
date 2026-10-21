# POST-HOC SOURCE ALIGNMENT — fixed addendum definitions

Date: 2026-10-21. Existing reviewed PR #31 HEAD: `06b58f013137f3af10619eafccb8f5a6dcc3ce4c`.
This document fixes the requested addendum implementation before calculating its outcomes. It is **POST-HOC**, not predeclared validation. **NO VIRGIN HOLDOUT**. The original protocol, strict classifier, outcome functions and strict numerical artifacts remain unchanged.

## Source correction and attribution

**INDEPENDENT TRANSCRIPT REVIEWED EXTERNALLY AFTER PREDECLARED ANALYSIS**

The owner reports that an independently recovered transcript of https://www.youtube.com/watch?v=v8d3OxE1-_c (about minute 20 onward) confirms the weekly-only oscillator/volatility explanation, sign-conditioned impulse/correction colors, reacceleration without a zero crossing, and continuation in the new direction after a zero crossing. In that explanation ADX is set aside; volatility may help anticipate an ADX turn. The external review reports approximately 1–2 weeks between oscillator change and volatility recovery. These are user-supplied paraphrases of an external review, **not quotations or text directly inspected by this agent**. No full transcript is stored. No new vidIQ credits or source download.

The review improves verbal alignment assessment only. It was not available to the original predeclared analysis and cannot validate its results or recover private formulas/settings. Dated visual examples remain unverified.

**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**

**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**

## Only three fixed temporal models

- `PREDECLARED STRICT SAME-WEEK MODEL`: original classifier, unchanged; lag 0 reference must reproduce all seven event timestamps, sides and types exactly.
- `POST_HOC_SOURCE_ALIGNED_LAG_SENSITIVITY`, maximum lag <=1 week.
- Same post-hoc sensitivity, maximum lag <=2 weeks.

Lag 0 is both the original reference and an exact replay check. Never test lag 3/4/5 or choose a winning lag. These windows are oscillator-first and forward-only, not a symmetric retrospective match. An expansion already active at a zero crossing remains eligible at lag 0 exactly as in the original model; a delayed confirmation requires a fresh volatility TURN_UP, not a historical turn selected afterward.

## Causal pending-candidate machine

Use only existing weekly closed features, common eligibility and frozen formulas. Build uninterrupted PULLBACK_UP / PULLBACK_DOWN runs using the original positive/negative oscillator sign, corrective color and non-rising volatility definition.

Reacceleration activation: after >=1 immediately preceding pullback weeks, the oscillator returns to its impulse color while retaining its zero sign, independent of current volatility. At activation, rising volatility confirms immediately (the preceding pullback slope guarantees TURN_UP). Otherwise latch a pending candidate until at most L subsequent closed weeks. Confirm at the first TURN_UP in that window. No zero crossing or loss of the returned impulse color is allowed while pending; a new correction cancels that return and can form a new distinct pullback sequence. No later reanimation of an expired return.

Zero-cross activation: strict previous/current opposite oscillator signs, independent of current volatility. If volatility is rising at that close, confirm immediately (including ACTIVE_RISING without TURN_UP, preserving the strict model). Otherwise await the first TURN_UP within L future closed weeks while the oscillator stays strictly on the new side of zero. Do not add an extra color gate for delayed zero-cross resolution: the original zero-cross rule had no independent color gate. Record resolution color for transparency. An exact zero, opposite cross, invalid week or deadline expiry cancels the candidate. A new opposite crossing may start its own candidate at the current close.

At most one pending sequence and one emitted episode at a timestamp. A pending zero-cross owns its resolution until confirmed/cancelled/expired; a same-side color return during that pending sequence is not a second episode. Record ignored activations, cancellations, expiries and the unresolved final candidate. No repeated notifications or runtime state is involved. Model counts need not be monotone or per-type nested because latching can attribute a resolution differently; publish activation/resolution identities, not just counts.

Signals are timestamped **at confirmation**, never at oscillator activation. Freeze range, anchor close and causal ATR at that confirmation. Do not credit price movement during the waiting period. Retain explicit activation timestamp, confirmation timestamp, actual lag, full sequence and state side. No future observation is used to backdate, decide whether to emit, or choose a lag. A final unresolved candidate is pending/censored, not a confirmed event.

## Unchanged outcomes and reporting

Reuse exactly the audited BTCUSDT BINANCE_USDM_PERPETUAL snapshot with cutoff 2026-10-19 00:00 UTC. No new market data. Last complete week remains 2026-10-12 -> 2026-10-19; on 2026-10-21 no newer complete week exists. Original 371 weeks / 263 eligible weeks, common matured opportunity denominators.

Primary: original frozen four-week range including confirmation candle, four-week forward horizon, weekly CLOSE breakout plus >=10% excursion in the same breaking direction. Keep original 2/8-week range sensitivities and all 1/2/3/4-week horizons; no new thresholds or optimized cell. Report the same <=5/10/15/20% and ATR fields already defined by the original outcomes; do not alter outcome mathematics. Precision, recall and false negatives remain anchor-level quantities with overlapping opportunity labels, not unique market-move counts.

For every temporal model: total and matured episode count; all four signal-family counts; precision, base rate, lift, recall, max excursion mean/median, signed return mean/median, terminal directional hit and first-close-break conditional/unconditional accuracy, false positives/negatives, best1/best3 influence by signed return and magnitude, eras, existing causal bull/bear regime, non-overlap counts and actual lag distribution. Publish dated new/changed/absent event identities relative to strict, and all episodes with outcomes. Bootstrap retains the original full-calendar block approach (2,000 draws, block8; original root seed plus horizon), minimum n10 for intervals, n30 for conclusion sufficiency. No independent-IID-event significance claim.

## Interpretation ceiling

The original conclusion remains **INCONCLUSIVE** for the **PREDECLARED STRICT SAME-WEEK MODEL**.
The addendum can conclude only one of:

- SOURCE-ALIGNED SENSITIVITY STILL INCONCLUSIVE
- SOURCE-ALIGNED SENSITIVITY SUGGESTIVE — FORWARD TEST REQUIRED
- SOURCE-ALIGNED SENSITIVITY WEAKER THAN STRICT MODEL
- PROXY LIMITATION DOMINATES

No `ROBUST` or validation designation, regardless of retrospective improvement. All three lags must be reported; no winner recommendation. Small n or inconsistent side/era/influence results require an inconclusive interpretation. The source review confirms reported verbal logic, not private-indicator parity or predictive value.

Current classifications for strict/<=1/<=2 use only the last complete week; include pending state if present. **CURRENT OBSERVATION — NOT PART OF VALIDATION**. **LARGE MOVE WATCH: NOT VALIDATED**. No runtime integration, production changes, Railway calls, merge, deployment or orders. **TRADE AUTHORITY: NONE**.
