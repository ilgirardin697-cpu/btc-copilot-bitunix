# BITMAN INTRADAY ENTRY RESEARCH V0 — preregistered offline protocol

SHADOW ONLY. TRADE AUTHORITY: NONE. Base fc211d8e36c6db55185efa8309eb8f980beab2ea.
NO VIRGIN HOLDOUT: all dates overlap earlier research. These hypotheses are new,
not prospectively validated. PR30/31 and weekly protocol V1 remain unchanged.

## Lock before outcomes
This specification is committed before computing this study's outcomes. No parameter
selection, winner selection, re-entry optimization or rule changes after evaluation.
Primary history: 2020-01-01 <= signal < 2026-09-01 UTC (complete archived months).
Development 2020–2021; validation 2022–2023; reused evaluation 2024–cutoff.
A 48-hour embargo at both ends of every calendar year applies to primary signals,
12 hours for secondary 15m; discard incomplete or split-crossing outcome windows.
Expanding annual walk-forward from 2022, always identical rules; no fitted parameters.
2019 is not required. First available 2020 data provides warmup, never fabricated.
All 1H/4H/1D bars formed from complete, closed USD-M 5m groups; reset indicators
at gaps and never fill candles. Context latest higher-timeframe close <= signal time.

## Indicators and provenance
Read-only reuse of bitman_manual.frozen.indicators.calculate, core.align and
levels.scale (confirmed strict2L/2R within220, delayed availability). AO SMA5−SMA34
of median(high,low); slope one-bar difference. ATR14 Wilder RMA seeded simple mean;
DM14/+DI/−DI and ADX14 exactly frozen implementation; BBWP close7 width4σ/SMA7,
rank against100 previous widths (101 total observations). Context AO sign/slope,
4H close versus causal SMA200 regime; 1D sign always recorded, never future aligned.
ML RSI historical reconstruction forbidden: confirmed production journals cover a
different venue/short period and are not used as a filter. ML RSI = UNAVAILABLE here.
Konkorde and Direction Engine/readiness are not entry criteria. Their math is unchanged.
EXACT BITMAN INDICATOR PARITY: NOT PROVEN.

FE variant FE_PRC_NICOLAS_20170323_N13_V0: only the raw gamma curve in Nicolas's
2017-03-23 public ProRealCode translation, published 2017-03-26, attributed to Mobius.
FE = ln(sum13(max(high,previous_close)−min(low,previous_close)) /
(highest13(high)−lowest13(low))) / ln(13). No Gaussian filter, Laguerre RSI, clipping
or mixing variants. Undefined/nonfinite/zero denominator => unavailable.
Research FE gate = current FE < previous FE, a predeclared test of falling congestion,
not an author's entry recommendation and not a directional measure.
Source: https://www.prorealcode.com/prorealtime-indicators/rsi-laguerre-adjusting-gamma-fractals-energy/
EXACT BITMAN FE PARITY: NOT PROVEN.

## Three symmetric event families (side s=+1 LONG, −1 SHORT)
A PULLBACK: s*AO positive at t,t−1,t−2; s*slope[t]>0; s*slope[t−1]<0
and s*slope[t−2]<0 (two corrective bars then recovery; no zero crossing).
Context: 4H and1D AO sign s; signal close beyond prior three signal-bars' high
(LONG) / low (SHORT), all known before t.
DMI/ADX gate: s*(+DI−−DI)>0, ADX slope[t]>0, previous ADX slope<=0.

B ZERO_CROSS: s*AO[t]>0 and s*AO[t−1]<=0.
Context: 4H AO slope sign s and1D AO sign s.
DMI/ADX gate: current DI dominance s, dominance crossed from non-s within last
three signal bars including t, and current ADX slope>0.

C REVERSAL: s*AO[t]<0; s*slope[t]>0; previous two signed slopes<0;
close beyond prior six signal-bars' high/low (mandatory structural confirmation).
Context: 4H AO sign −s and 4H AO slope sign s. Daily AO sign is descriptive.
DMI/ADX gate: current DI dominance s and previous ADX slope<0 (weakening old
trend). Falling ADX never chooses direction; direction comes from symmetric event.

Each family has five prespecified ablations: AO_ONLY; AO_CONTEXT;
AO_DMI (=context+DMI/ADX); AO_FE (=context+FE); AO_DMI_FE (=context+DMI/ADX+FE).
Direct indicator incremental comparisons use AO_CONTEXT as parent; DMI_FE also
compares with DMI and FE. No confounding claim that context is an indicator effect.
Reject nonfinite mandatory features. Freeze signal-time prior6-bar structure and
latest confirmed pivot support/resistance for diagnostics. No future pivots.
Thin AO anchor events chronologically with 48-hour spacing per family, regardless
of actual exit; all filters share those exact anchors. This intentionally forgoes
opportunities to ensure nested attrition comparisons, not maximum trading frequency.

## Fixed exits and timing
Signal at closed bar t. Entry at next signal bar open; exact corresponding 5m open,
never signal close. Constant unit notional; no leverage or compounding.
ATR_2R: stop distance1.5*signal ATR14; target2R; max24 signal bars.
STRUCTURE_2R: stop prior6 signal-bar low−0.25ATR (LONG), high+0.25ATR (SHORT);
distance must be between0.5ATR and4ATR, else invalidate; target2R; max48 signal bars.
No trailing, breakeven or discretionary exits. Execute paths on closed5m OHLC.
Gap through stop fills adverse opening; target gap fills target without improvement.
If5m bar hits both stop and target => stop first. Exit ambiguity counted.
MAE/MFE on exit candle are conservatively limited: adverse-first ambiguous candle
does not contribute favorable excursion. Stop/target exit price bounds excursions;
full high/low path beyond a filled barrier is not credited. Time-exit at last close.
No trade across gaps. Required full maximum holding window even if an early stop
might have happened; unavailable windows censored independently of performance.
Funding: actual archived USD-M rate at scheduled timestamps while held;
mark price unavailable => 5m opening price proxy, explicitly an estimate. At entry
timestamp or ambiguous exit candle boundary charge adverse rates, never award
favorable funding credits for ambiguous ownership. No assumed zero funding.
Funding missing expected8h schedule => censor affected maximum outcome window.

## Costs (assumptions, not account fee claims)
BASE fee5bp/side + slippage1bp/side (12bp round trip at unchanged price).
CONSERVATIVE fee7.5bp/side + slip3bp/side (21bp).
STRESS fee10bp/side + slip5bp/side (30bp).
Fees/slippage on entry and actual exit notional; funding actual rates with price
proxy. BASE is primary; all scenarios mandatory. Spread/impact beyond assumptions
and liquidation/margin execution cannot be proven from OHLC data.

## Controls / uncertainty
One matched random closed timestamp per eligible AO anchor; same UTC year-month,
side and causal4H SMA200 regime; same valid closed features and exit framework.
Seed20261021. Matching excludes future returns. Enforce same maximum spacing within
each family's control set; report unmatched events, never impute matches.
Retain controls after filtering, paired to exact signal IDs. Also compare raw AO
and context ablations; simple benchmark: signed buy/short at the matched timestamps.
No pool of overlapping variants as independent trades. Comparisons descriptive.
Calendar30-day block bootstrap, seed20261021, 5000 draws. Joint resampling of
paired signal/control differences. Report95% intervals, mean/median/quantiles,
ex-best1/ex-best3, years, LONG/SHORT, regime, fees, exposure, drawdown, PF, R,
MAE/MFE, duration, immediate adverse first5m and entry-vs-signal-close.
Classification family size30 (3*5*2); no best exit chosen. Multiplicity-adjusted
one-sided lower quantile0.05/30 also required for promising. Secondary15m:
B only, same five variants, ATR_2R only,24*15m hold,12h anchor spacing;
not selectable as primary and multiplicity family total35 for any promising claim.

PROMISING FOR FORWARD VALIDATION requires reused evaluation n>=100, each side>=30,
net expectancy BASE andCONSERVATIVE lower95 bound>0, adjusted lower bound>0,
paired-control advantage lower95 bound>0, PF>1, positive mean after removing best3,
positive BASE mean in every evaluation year, positive validation mean, and positive
incremental difference against parent ablation with lower95 bound>0.
Otherwise NO EDGE if reused evaluation mean BASE<=0 or conservative mean<=0
or paired-control advantage<=0. Otherwise INCONCLUSIVE (including insufficient n).
None means validated. No automatic forward observer implementation.

## Reporting / tests
Every hypothesis/variant/exit, including failures and attrition, must be reported.
Objective examples: earliest chronological positive and negative BASE trade per
family in evaluation, with actual signal availability, entry, invalidation and exit.
Include exclusion counts, raw/checksum/data hashes, costs known vs estimated,
deterministic fixtures, prefix/future perturbation, HTF closed alignment, stop-first,
funding sign, gaps, split embargo, no execution imports, protected source hashes.
No production dependency on this package. Research workflow only.
