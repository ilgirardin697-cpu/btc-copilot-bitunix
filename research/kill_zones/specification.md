# I-GOD Kill Zones research V0 — pre-outcome specification

Protocol KILL_ZONES_RESEARCH_V0. Written before computing strategy outcomes.
Base: 9d40020d539033cefb8f01734db8c6a6fdbba2e3. SHADOW ONLY. TRADE AUTHORITY: NONE.
No production import, deployment, bot message, private API or execution adapter.

## Source and uncertainty
Owner-supplied account of a 16:28 video, with segment map:
00:00–03:33 sessions; 03:33–05:30 bullish diagonals/projection;
06:14–08:40 bearish case; 09:27–11:24 bullish case;
11:47–13:10 wick is insufficient; 13:10–16:20 indicator combinations.
Descript: https://web.descript.com/fa46b015-7440-4d90-af6d-de39f4b34a1a/9faf8
Telegram: https://t.me/c/2809916373/79146
Both links were inaccessible to the available web reader. No Descript connector
or authenticated video viewer is available. The transcript and drawn anchors have
NOT been independently inspected. The user's segment summary is not a transcript.
EXACT VIDEO DIAGONAL / PROJECTION PARITY: NOT PROVEN.
Do not attribute the two formalizations below to the video's author.
Unresolved: exact ticker/venue, anchors and ties, diagonal direction, translation
vector, moving vs fixed target, entry expiry, stop, retry and exit conventions.
If source access later resolves these, use a new protocol; do not refit this run.

## Data and chronology
BTCUSDT BINANCE_USDM_PERPETUAL, official Binance Vision USD-M monthly 5m klines
and funding-rate files. September 2023–September 2026 inclusive, closed months.
5m used only for more conservative fill chronology; signals are exclusively 1H.
Aggregate only complete contiguous hours; never interpolate/fill missing bars.
Each ZIP must match its official .CHECKSUM; record URLs, bytes, hashes, ranges,
gaps, duplicates, normalization and funding coverage. Never substitute Spot.
Warmup: 2023-09-01–2024-01-01. Development: calendar 2024.
Validation: calendar 2025. Chronological evaluation: 2026-01-01–2026-10-01.
Exclude entries in the first/last 48 hours of each split; no trade spans a split.
Rules are NOT selected on validation or evaluation. Report all cells.
NO VIRGIN HOLDOUT: this price history has been used by other I-GOD research;
the final interval is held back for this fixed hypothesis, not untouched globally.
No causal bull/bear optimization and no future-derived regime labels.

## Sessions and daylight saving
Trading date d is the local date of London.
Asia: [d-1 20:00, d 00:00), London: [d 02:00, d 05:00).
Primary: IANA America/New_York. Comparator: fixed UTC-04:00.
Use UTC instants, half-open intervals and physical elapsed hours.
Spring DST Sunday has only two physical London hours (02:00 is skipped, start
normalizes to 03:00); record this, do not manufacture a third hour.
All days, including weekends; report weekends separately.
Freeze the two boxes only at London end. Their highs/lows cannot change later.
Earliest extreme wins tied highs/lows. Wick extremes define the boxes.
Signal hours OPEN at/after 05:00 and CLOSE at/before 12:00 local.
One first valid closed-hour crossing per day/model, at most one active position.
No intrabar entries, no second attempt that day, no pyramiding.

## Exactly three geometry models
Let AH/AL be Asia high/low; LH/LL London high/low.
H=max(AH,LH), L=min(AL,LL), W=H-L >0.
For each line D(t)=pA+(pL-pA)*(t-tA)/(tL-tA).
1. EXTREME_TIMES: resistance connects AH and LH at their earliest 1H candle CLOSE
timestamps; support connects AL and LL likewise.
2. BOX_ENDS: same prices, but anchors are Asia END and London END respectively.
3. RANGE baseline: horizontal resistance H and support L; no diagonal.
The two diagonals are deliberately plausible alternatives to unresolved anchors.
They are not an exhaustive search and not a proven reproduction.
If resistance <= support at the current/prior test instant, reject that hour.
LONG: previous closed price <= previous resistance AND current 1H CLOSE >
current resistance. SHORT is symmetric. A wick beyond a line cannot confirm.
Do not infer directional information from ADX. Do not require a minimum ADX.
If both directions qualify, reject as ambiguous.
Record crossings caused only by movement of the line as a diagnostic; no
post-outcome exclusion of these cases.

## Projection, stops and entry
Full target at SIGNAL time:
diagonals: crossed line at signal close + side*W (a parallel vertical copy).
RANGE: H+W for LONG / L-W for SHORT.
Freeze this numeric target; do not move it using future timestamps/prices.
Two fixed target-distance fractions: 1.00 and 0.95, measured from signal close.
The latter is the predeclared "slightly before" comparator, not optimized.
This particular copy/translation is a research definition, NOT verified video parity.
Stop before entry: L for LONG, H for SHORT; frozen, no later tightening.
Entry: next real 5m open, which is the open of the next 1H candle, plus adverse
slippage. Reject if this actual entry is already at/beyond stop or target.
Maximum holding time: 24 physical hours after entry, close at that boundary.
All entry, target, stop and expiry rejection reasons must be retained.

## Costs and simulation
Base assumptions: taker commission 0.06% EACH leg; adverse slippage 0.05% EACH
leg including target exits. Stress: same commission, slippage 0.10% EACH leg.
These are conservative assumptions, not a verified account fee tier or fill.
Funding: actual archived signed rate and timestamp; quote notional uses the
last completed 5m trade close as an explicitly labeled MARK-PRICE PROXY.
No claim of exact funding cashflow without actual historical settlement marks.
Hold entry<t<=exit funding; exactly-at-entry charges only adverse funding,
never grants a same-instant credit. Include actual signed income otherwise.
Funding must cover the complete simulated period, no missing 8h records.
An exit gap through stop fills at the worse open, then adverse slippage.
A favorable target gap gets only target price, then adverse slippage.
If stop and target touch the same 5m bar: stop first, flag ambiguous.
No invented intrabar price path. Excursions use completed pre-exit 5m bars plus
the actual exit fill; they omit unknown intra-exit-bar peaks (lower-bound metric).
R denominator is absolute slipped entry minus frozen structural stop.
Paper equity starts at 10000 USDT, sizes to <=1% equity planned stop loss
including reserved exit slippage and both fees, capped at 1x entry notional.
No leverage, liquidation model, live order or exchange credentials.
One active trade per model; overlapping raw candidates are logged but not traded.

## Fixed experiment family
3 geometries x 2 clocks x 2 target fractions = 12 cells; report every one.
Primary predeclared cell: EXTREME_TIMES / New York / TP95.
No winner is promoted merely for ranking first among twelve.
Frozen indicator ablations ONLY for this primary cell: ALL, AO, DMI_ADX,
KONKORDE_PROXY, AO_DMI_KONKORDE. Same entries/stops/exits when a candidate passes.
AO gate: side*ao_slope >0. DMI_ADX: side*(+DI--DI)>0 AND adx_slope>0.
Konkorde: existing frozen bullish entry/inside/reentry context for LONG,
existing bearish context for SHORT. AO and Konkorde exact private parity NOT PROVEN.
Read frozen 1H indicators unchanged; 4H/1D already-confirmed context is descriptive,
not an added entry gate. No recomputation or substitution of historical ML RSI.
Real confirmed journal coverage available locally is October 2026, outside this
study cutoff: ML RSI incremental value is UNAVAILABLE, not zero or manufactured.
No combination/threshold search. These 5 ablations are descriptive; they cannot
create a PROMISING classification independently.

## Statistics, robustness, objective examples
Per split, year, side and weekend: n, win%, gross/net returns, net expectancy R,
profit factor, realized drawdown, exposure, duration, conservative MAE/MFE,
target hit%, same-bar ambiguity and costs including funding proxy.
95% block-bootstrap CI of mean net R: 14-calendar-day blocks, 5000 resamples,
fixed seed 20261031. Report median/p10/p90 and ex-best-1/ex-best-3.
Paired daily net-R difference vs corresponding RANGE comparator (zeros on no
trade days) uses same calendar-block resamples. Also show familywise 99.5833%
interval (Bonferroni, twelve cells), descriptive not proof of independent trials.
No serially-overlapping signals counted as independent positions.
Validation and evaluation each subdivided by calendar half-year; no refitting.
Objective plots: first chronologically profitable and first losing evaluation
trade in the PRIMARY cell, LONG and SHORT separately where available.
Use all losers in tables, not manually selected attractive charts.

## Classification fixed before outcomes
PROMISING only if evaluation n>=100 (each side>=30), mean net R 95% CI lower>0,
PF>1.1, stress mean>0, validation mean>0, every evaluation half-year mean>0,
ex-best-3 mean>0 AND paired improvement over RANGE familywise lower bound>0.
NO EDGE if base evaluation mean<=0 and PF<=1, or its 95% upper bound<=0.
Otherwise INCONCLUSIVE. n<30 is always INCONCLUSIVE (insufficient sample).
Overall PROMISING requires the primary cell passes AND both geometry definitions
in New York have positive evaluation/stress means at both target fractions;
else overall NO EDGE when all four New York diagonal cells are NO EDGE;
otherwise INCONCLUSIVE. Missing source parity separately prevents a claim about
the exact video. Historical PROMISING would only motivate a new shadow-forward
protocol; never runtime/readiness integration or trading authority.

## Sources
Official archive/schema/checksums: https://github.com/binance/binance-public-data
Official klines/funding docs:
https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
NY DST: https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst
