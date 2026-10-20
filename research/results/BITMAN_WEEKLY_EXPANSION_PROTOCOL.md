# Weekly AO × BBWP — protocol fixed before outcome analysis

Recorded 2026-10-20, before downloading/evaluating the study history.
Production base: `9c660035f912be4640f09cf6e2d4c48583c20b04`.
RESEARCH ONLY. Historical public candles, not observed forward signal journals.
No runtime changes, parameter selection, orders, alerts or trade authority.

## Data and causality

- BTCUSDT / BINANCE_USDM_PERPETUAL only. Official `/fapi/v1/klines`.
- Acquire all available closed 4H history, requesting from timestamp zero;
  record first available response, exact request params, response SHA256/size,
  acquisition time, gaps and source schema. Never interpolate or fill gaps.
- Aggregate 42 contiguous closed 4H bars into Monday 00:00 UTC weeks. Drop an
  incomplete initial week. Cutoff is 2026-10-19T00:00:00Z; the week beginning
  on that date is excluded. The last eligible week opens 2026-10-12.
- Compare all complete weekly bars against native REST `1w` timestamps and
  eight requested fields; preserve/report numerical differences rather than
  silently changing data. An official Vision USD-M sample with CHECKSUM will
  also be compared if available, explicitly separate from REST acquisition.
- Call the existing frozen `indicators.calculate` on weekly OHLCV. AO is
  SMA5(hl2)-SMA34(hl2), green iff delta AO >0, red iff <0. Zero slope is FLAT,
  never assigned to green/red. Separate positive/negative AO from bar color.
- BB width = 4*population_std(close,7)/SMA(close,7); BBWP counts strictly smaller
  widths in the preceding 100 values within 101 finite observations. Its range
  is 0..100. Preserve strict ties and the full warmup; delta BBWP is one week.
- No future pivots, weekly open candle, resampled indicator shortcuts or
  shorter rolling windows. Reuse the frozen 4H close-vs-SMA200 causal regime
  for BULL/BEAR context only, aligned at the weekly close.

## Event grid — all reported, none selected after observing results

Base universe: weeks with finite current/prior AO and BBWP slopes. A forward
horizon is eligible only if every one of its future weeks is closed/available.

- A: BBWP slope >0; B: BBWP slope <0. Report GREEN and RED separately.
- C: prior slope <=0 and current slope >0 (EXPANSION START).
- D2/D3/D4: C after at least 2/3/4 consecutive preceding non-increasing weeks.
  These masks are nested, not mutually exclusive; all three are reported.
- E: C by previous BBWP in [0,10], (10,20], (20,30], (30,50], (50,100].
- F: current BBWP >50 and previous <=50; current <50 and rising; current >50
  and rising. Exactly 50 is separately counted, never rounded across a gate.
- Every event is tabulated without AO filtering, by GREEN/RED, and by the four
  AO sign × color quadrants. FLAT/zero/unknown counts remain explicit.
- Secondary only: GREEN/RED × BBWP rising/falling × ADX rising/falling × DI
  bullish/bearish/neutral. No ADX/DI condition enters the primary hypotheses.

## Outcomes, baselines and controls

Horizons: 1, 2, 4 weeks. Anchor = event week's final close (not an executable
fill); excursions use only subsequent weeks. Terminal return = future close /
anchor -1. Signed return = return × AO color sign. Hit = signed return >0;
ties are not wins. Report raw terminal direction UP/DOWN/FLAT independently.
Favorable/adverse excursions are nonnegative and oriented to AO; maximum
absolute move is max(upward excursion, downward excursion). Report both
absolute terminal return and maximum absolute excursion, with >=3/5/10/15%
frequencies for each. No trading returns, costs, leverage or order simulation.

Baselines: all valid weeks, falling BBWP, rising BBWP without AO filtering,
same AO color without BBWP filtering, and expansion-start without AO. Paired
contrast CIs compare on a common horizon/eligible-week grid. Constant-side
comparisons against all rising weeks test whether AO adds direction beyond
unconditional drift; same-color and falling-color controls test interaction.

Epochs: 2020–2022, 2023–2024, 2025–cutoff, based on information-availability
time at Monday close. Empty early periods/warmup are explicit. Also report
causal BULL/BEAR regimes. Do not call any of these eras a virgin holdout:
2024+ historical data were already reused by earlier Bitman research.

Temporal controls: show all four fixed non-overlapping phases (weekly index
modulo 4), never select a phase. Also compare each event with at least 12
matured outcomes from the preceding 52 weeks, requiring control j+h<=event i;
this baseline uses no future-observable control outcome at event availability.

## Uncertainty, influence and decision discipline

- Fixed RNG seed 20261020; 2,000 circular moving-block bootstrap replicates,
  block length 8 weeks, preserving horizon overlap and clustered events.
  Resample original week/outcome pairs, not fabricated candle sequences.
- Show n, annual frequency, contiguous event episodes, mean, median, standard
  deviation, min/max, p10/p25/p75/p90. Bootstrap 95% intervals are descriptive,
  not multiplicity-adjusted or prospective validation. Suppress intervals for
  n<10 or <95% finite bootstrap replicates; flag small cells explicitly.
- For signed return, absolute terminal return and maximum absolute excursion,
  remove best 1 and best 3 observations separately for that metric. Record the
  removed dates and compare event-only trimmed effects with unchanged controls.
- Robust magnitude requires positive 95% lower bounds for rising-vs-falling
  lifts in BOTH mean absolute terminal return and mean max-absolute excursion
  at ALL three horizons, >=30 observations in both arms, >=10 per arm in EACH
  era, positive lifts in every era, and positive lifts after dropping best 3.
- Robust AO direction additionally requires BOTH colors to have positive signed
  mean and directional-hit lift over constant-side rising controls AND positive
  signed lift over same-color unfiltered controls, with positive 95% lower
  bounds at all three horizons, >=30 event observations and >=10 in each era,
  era-consistent signs and survival after dropping best 3 signed events.
- Failure after removing extreme events or contradictory eras is FRAGILE when
  an apparent positive primary lift exists. Otherwise insufficient/imprecise
  evidence is INCONCLUSIVE. No post-hoc best N/bucket/threshold is promoted.
- Allowed conclusions: ROBUST EXPANSION EFFECT — DIRECTION EFFECT ROBUST;
  ROBUST EXPANSION EFFECT — DIRECTION INCONCLUSIVE; EXPANSION EFFECT FRAGILE;
  INCONCLUSIVE — DO NOT INTEGRATE. Even robust retrospective evidence would
  justify only a separate manual context specification and later forward audit.
- Latest closed-week reading is CURRENT OBSERVATION — NOT PART OF VALIDATION.
  Its future outcomes are censored normally. No READY, orders or runtime change.
