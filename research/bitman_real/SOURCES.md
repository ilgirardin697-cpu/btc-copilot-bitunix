# Provenance and exact scope

This is **I-GOD BITMAN REAL OBSERVER v0.1**, `KONKORDE_PROXY`.
**EXACT BITMAN KONKORDE PARITY: NOT PROVEN.** The name does not certify official
Bitman software, private-indicator parity or profitability.

## Primary evidence and what was actually accessible

- [Bitman video tDnUVybgL20](https://www.youtube.com/watch?v=tDnUVybgL20): the
  user's direct viewing supplied the primary observations about Micro Finanzas
  Personales Koncorde 2.0, MA entering/leaving the mountain, zero proximity and
  quick reentry. Automated video retrieval failed on 2026-10-16. We do not claim
  to have independently watched it or invent a transcript/timecoded quotations.
  These user-supplied qualitative rules are distinguished from the public proxy
  formula and our numerical geometry choices below.
- [Blai5's own basic rules](https://www.blai5.net/category/docs/faqs/): original
  author distinguishes the brown trend area/red MA from the blue/green volume
  areas; says Koncorde is an auxiliary tool, not a complete trading system, and
  notes limitations of attributing trades to participant groups. No inferred
  real institutional order flow is claimed here.
- [manboto, public TradingView adaptation](https://www.tradingview.com/script/lLFiT3av/):
  original publication by this adapter's author, marked open-source. It describes
  the brown-area/EMA crossings, but its source tab was not extracted by the web
  parser. We do not claim to have audited that specific Pine source.
- [Hábil Inversor's published Pine implementation](https://stackoverflow.com/questions/65187539/i-have-problems-using-pine-script-v3-in-version-4-koncorde-indicator):
  primary publication of the adapter's code, dated 2020-12-07; original question's
  mountain/MA block is visible. This is the reproducible numerical source used
  for the clean-room proxy. It uses OHLC4, RSI14, HLC3 MFI14, BB25 with multiplier2,
  Stochastic21/SMA3 and EMA15. Its PVI/NVI plotting/conversion issues do not enter
  the brown mountain formula used here. We do not copy those sections or their
  code. Attribution is retained; source material published in 2020 is subject to
  Stack Overflow's CC BY-SA terms. This Python implementation is independently
  written from the mathematical definitions, not a republished Pine script.
- [Original author Zeiierman, Trend Speed Analyzer](https://in.tradingview.com/script/YUAV6jit-Trend-Speed-Analyzer-Zeiierman/):
  public page lists the matching input names and is marked open-source. The
  original algorithm source was not reliably extracted. Third-party translated
  forum copies were found but not used as authority. Status remains **NOT
  IMPLEMENTED / FORMULA NOT VERIFIED**. Metadata: 117/2.7/150/100/From start.
- [Original BBWP publication](https://www.tradingview.com/script/tqitSsyG-Bollinger-Band-Width-Percentile/):
  percentile-of-width concept. Our explicit prior-100 rank and population STD
  are a reproducible definition, not a claim of exact private TV preset parity.
- [TradingView AO definition](https://www.tradingview.com/support/solutions/43000501826-awesome-oscillator-ao/)
  and [ADX definition](https://www.tradingview.com/support/solutions/43000589099-average-directional-index-adx/):
  standard AO5/34 and Wilder ADX/DI14, not fitted filters.

## Exact mountain formula

For each complete candle, `P=(O+H+L+C)/4`, `T=(H+L+C)/3`:

```text
RSI = 100*RMA14(max(delta(P),0)) /
             (RMA14(max(delta(P),0))+RMA14(max(-delta(P),0)))
MF+ = SUM14(T*V when delta(T)>0, otherwise0)
MF- = SUM14(T*V when delta(T)<0, otherwise0)
MFI = 100*MF+/(MF++MF-)
Basis = SMA25(P)
BB upper/lower = Basis +/- 2*populationSTD25(P)
BollOsc = 100*(P-Basis)/(4*populationSTD25(P))
K = 100*(P-LOWEST21(L))/(HIGHEST21(H)-LOWEST21(L))
Stoch = SMA3(K)
mountain = (RSI+MFI+BollOsc+Stoch/3)/2
MA = EMA15(mountain)
zero = 0
```

Wilder RMA seeds with the SMA of 14 valid observations; RSI needs 14 price changes.
EMA starts at the first finite mountain value with alpha2/16. No interpolation
over absent candles. Undefined ratios remain unavailable; no invented neutral
mountain on constant/zero-volume data. Missing values reset state and suppress
an event at the next first valid observation.

This is the **brown mountain only**, not the green PVI-enhanced area. PVI/NVI
participant classifications are intentionally absent. A brown trend mountain
contains volume indirectly through MFI, but is not a direct volume/orderbook map.
The private 2.0 implementation, its normalization/parameters, seeds and plotting
geometry are unknown. Zero proximity scales may differ materially. Negative
mountains are handled geometrically, without inventing a bearish trading rule.

## Explicit observational definitions

Inside means strictly between zero and mountain: `min(0,M)<MA<max(0,M)`.
Equality is a touch/outside, not a new confirmed entry. The first valid state is
context only. ENTRY is outside→inside; EXIT is inside→outside. REENTRY is an ENTRY
with a prior EXIT 1..N same-timeframe bars earlier. No separate additional entry
is counted for it. N must be passed explicitly to the observer; historical tables
report 1,2,3,5 without selecting a winner.

`distance_to_zero=abs(MA)` in indicator units, plus `abs(mountain)`.
`separation=abs(mountain-MA)` while inside, to the outer brown edge. Strength
is its change across consecutive inside bars; a first inside observation has no
comparable previous separation and is `NEW_INSIDE`. These are measurements, not
new stops/exits. Near/far tertiles are fitted on TRAIN for description only.

BBWP: CLOSE/SMA7, width `4*populationSTD7(C)/SMA7(C)`, count of PRIOR100 widths
strictly below the current width (0..100). Equal widths do not rank below.
Rising/falling describes percentile slope; no compression/extreme threshold is
chosen. This differs from implementations that include the current observation,
use a different tie rule or provide partially filled lookbacks.

ADX has smoothing14 and DI length14, without an absolute required threshold.
AO is SMA5(HL2)−SMA34(HL2); value, zero side and slope are shown. All are calculated
independently per 1H/4H/1D, from closed candles only.

## Direction vocabulary, not execution

LONG describes positive mountain, MA inside and +DI>−DI. No ADX magnitude, AO
sign or BBWP level is mandatory; those are contextual observations as requested.
This is a predeclared visual interpretation, **not a claim of validated LONG
profitability or entry permission**. It is evaluated separately as a directional
episode, not selected from TEST combinations. A missing DI agreement or a rising
positive mountain still outside is SETUP_FORMING. Other non-bearish contexts WAIT.
Negative mountain with bearish DI/AO is BLOCKED/SHORT_LOGIC_NOT_PROVEN. SHORT
is reserved in the display vocabulary but cannot be emitted by v0.1.

The current production LOW29/EMA4 ML RSI is untouched. LOW27/SMA4 is merely a
SEPARATE RESEARCH CONFIGURATION; it is not implemented or imported in this study.
BITMAN Phase2 remains REJECT and contributes **data only**, never its rules.
