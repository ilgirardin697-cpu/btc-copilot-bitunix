# BITMAN_ENTRY_RESEARCH_V0

**OFFLINE RESEARCH / SHADOW ONLY / TRADE AUTHORITY: NONE**

**NO VIRGIN HOLDOUT. No candidate is prospectively validated. NO RUNTIME INTEGRATION.**

## Protocol and source audit

Specification committed before outcomes; protocol_lock.json binds it and the analysis sources. Development2020–2021; validation2022–2023; reused evaluation2024–2026-08-31. Fixed annual walk-forward from2022, expanding available history, no fitted or selected parameters. Embargo48h primary/12h secondary at both year boundaries. Earlier research already examined these dates.

Frozen AO5/34 median, Wilder ATR14/DMI14/ADX14, BBWP7/rank101 and confirmed2L/2R pivot helpers are reused read-only. 1D/4H close availability is enforced. ADX measures strength, never direction. ML RSI is UNAVAILABLE: there is no multi-year same-venue confirmed production journal; nothing is reconstructed. Direction Engine and operability gates are not entry filters. Early Breakout remains NO EDGE; its selected parameters are not reused.

**EXACT BITMAN INDICATOR PARITY: NOT PROVEN. EXACT BITMAN FE PARITY: NOT PROVEN.**

FE_PRC_NICOLAS_20170323_N13_V0 uses only raw13-bar gamma from [Nicolas’s public2017 implementation](https://www.prorealcode.com/prorealtime-indicators/rsi-laguerre-adjusting-gamma-fractals-energy/). The scalar formula is independently tested. No Gaussian/Laguerre variant or private Bitman equivalence is claimed. Falling FE is a predeclared congestion-filter hypothesis, not an author’s entry recommendation.

## Dataset

BTCUSDT / BINANCE_USDM_PERPETUAL: 2020-01-01T00:00:00+00:00 → 2026-09-01T00:00:00+00:00. 701,280 closed5m bars; 7,305 funding rates; 0 gaps.
[Official USD-M archives](https://github.com/binance/binance-public-data); every ZIP verified against its SHA256 checksum. artifacts/data_manifest.json retains URL/size/rows/checksum per archive plus normalized array hashes. Raw market files remain local-only. No Spot, Bitunix, account access or production data request.

## Simulation and cost assumptions

Signal close → next bar opening, refined with5m OHLC. Stop first if both barriers hit in one5m candle. ATR_2R:1.5ATR stop/2R target/24 bars. STRUCTURE_2R:prior6-bar extreme ±0.25ATR, risk0.5–4ATR/2R target/48 bars. Full maximum window must have complete data/funding. No re-entry, trailing stop or optimized exit. Shared48h anchors (12h for15m) avoid overlapping observations; different variants are never pooled as independent trades.

BASE fee5bp+slip1bp/side; CONSERVATIVE7.5+3; STRESS10+5. These are assumptions, not verified account fees. Funding rates are historical; funding mark price uses5m opening proxy. Boundary ownership debits adverse funding without awarding ambiguous credits. Thus net returns remain estimates. MAE/MFE on filled exit candles are conservative partial-path measures. Stop/target price and exit timing remain limited by5m resolution.

## All reused-evaluation comparisons

| TF | Family | Variant | Exit | n | Net R | CI95 R | PF | Random ΔR | Parent ΔR | Classification |
|---|---|---|---|---:|---:|---|---:|---:|---:|---|
| 1H | A | AO_ONLY | ATR_2R | 359 | -0.112 | [-0.266, 0.037] | 0.836 | 0.007 | 0.000 | NO EDGE |
| 1H | A | AO_CONTEXT | ATR_2R | 57 | 0.028 | [-0.331, 0.413] | 1.042 | 0.269 | 0.139 | NO EDGE |
| 1H | A | AO_DMI | ATR_2R | 21 | -0.156 | [-0.694, 0.463] | 0.788 | -0.022 | -0.184 | NO EDGE |
| 1H | A | AO_FE | ATR_2R | 40 | -0.040 | [-0.434, 0.362] | 0.943 | 0.176 | -0.068 | NO EDGE |
| 1H | A | AO_DMI_FE | ATR_2R | 16 | -0.045 | [-0.682, 0.606] | 0.935 | 0.158 | 0.112 | NO EDGE |
| 1H | A | AO_ONLY | STRUCTURE_2R | 351 | -0.088 | [-0.244, 0.064] | 0.873 | 0.077 | 0.000 | NO EDGE |
| 1H | A | AO_CONTEXT | STRUCTURE_2R | 52 | 0.190 | [-0.207, 0.526] | 1.364 | 0.837 | 0.277 | INCONCLUSIVE |
| 1H | A | AO_DMI | STRUCTURE_2R | 18 | 0.308 | [-0.391, 0.967] | 1.634 | 1.155 | 0.118 | INCONCLUSIVE |
| 1H | A | AO_FE | STRUCTURE_2R | 35 | 0.326 | [-0.220, 0.775] | 1.655 | 1.109 | 0.137 | INCONCLUSIVE |
| 1H | A | AO_DMI_FE | STRUCTURE_2R | 13 | 0.710 | [-0.078, 1.360] | 3.111 | 1.346 | 0.403 | INCONCLUSIVE |
| 1H | B | AO_ONLY | ATR_2R | 337 | -0.159 | [-0.294, -0.032] | 0.763 | 0.052 | 0.000 | NO EDGE |
| 1H | B | AO_CONTEXT | ATR_2R | 74 | -0.305 | [-0.617, 0.014] | 0.596 | 0.143 | -0.146 | NO EDGE |
| 1H | B | AO_DMI | ATR_2R | 7 | -0.689 | [-1.234, 0.294] | 0.273 | -0.366 | -0.384 | NO EDGE |
| 1H | B | AO_FE | ATR_2R | 54 | -0.124 | [-0.481, 0.215] | 0.817 | 0.356 | 0.181 | NO EDGE |
| 1H | B | AO_DMI_FE | ATR_2R | 5 | -0.464 | [-1.207, 0.821] | 0.438 | 0.116 | 0.225 | NO EDGE |
| 1H | B | AO_ONLY | STRUCTURE_2R | 304 | -0.155 | [-0.275, -0.036] | 0.766 | 0.015 | 0.000 | NO EDGE |
| 1H | B | AO_CONTEXT | STRUCTURE_2R | 66 | -0.265 | [-0.581, 0.078] | 0.624 | 0.063 | -0.110 | NO EDGE |
| 1H | B | AO_DMI | STRUCTURE_2R | 4 | -0.366 | [-1.124, 1.838] | 0.557 | 0.163 | -0.101 | NO EDGE |
| 1H | B | AO_FE | STRUCTURE_2R | 47 | -0.192 | [-0.557, 0.154] | 0.719 | 0.192 | 0.072 | NO EDGE |
| 1H | B | AO_DMI_FE | STRUCTURE_2R | 3 | -0.113 | [-1.112, 1.838] | 0.844 | 0.263 | 0.253 | NO EDGE |
| 1H | C | AO_ONLY | ATR_2R | 149 | 0.028 | [-0.189, 0.231] | 1.045 | 0.172 | 0.000 | NO EDGE |
| 1H | C | AO_CONTEXT | ATR_2R | 39 | -0.175 | [-0.523, 0.173] | 0.756 | 0.351 | -0.203 | NO EDGE |
| 1H | C | AO_DMI | ATR_2R | 22 | -0.324 | [-0.785, 0.093] | 0.568 | 0.559 | -0.149 | NO EDGE |
| 1H | C | AO_FE | ATR_2R | 14 | -0.419 | [-0.964, 0.194] | 0.441 | 0.146 | -0.244 | NO EDGE |
| 1H | C | AO_DMI_FE | ATR_2R | 7 | -0.821 | [-1.195, -0.356] | 0.021 | 0.322 | -0.497 | NO EDGE |
| 1H | C | AO_ONLY | STRUCTURE_2R | 140 | -0.023 | [-0.216, 0.171] | 0.962 | 0.208 | 0.000 | NO EDGE |
| 1H | C | AO_CONTEXT | STRUCTURE_2R | 36 | -0.135 | [-0.502, 0.273] | 0.787 | 0.161 | -0.112 | NO EDGE |
| 1H | C | AO_DMI | STRUCTURE_2R | 20 | 0.170 | [-0.334, 0.719] | 1.358 | 0.571 | 0.305 | INCONCLUSIVE |
| 1H | C | AO_FE | STRUCTURE_2R | 12 | -0.422 | [-0.961, 0.205] | 0.388 | 0.497 | -0.287 | NO EDGE |
| 1H | C | AO_DMI_FE | STRUCTURE_2R | 6 | -0.431 | [-1.118, 0.272] | 0.303 | 0.927 | -0.601 | NO EDGE |
| 15m | B | AO_ONLY | ATR_2R | 1379 | -0.361 | [-0.445, -0.282] | 0.552 | 0.005 | 0.000 | NO EDGE |
| 15m | B | AO_CONTEXT | ATR_2R | 177 | -0.222 | [-0.427, -0.029] | 0.699 | 0.084 | 0.139 | NO EDGE |
| 15m | B | AO_DMI | ATR_2R | 26 | 0.264 | [-0.234, 0.771] | 1.464 | 0.779 | 0.486 | INCONCLUSIVE |
| 15m | B | AO_FE | ATR_2R | 103 | -0.203 | [-0.456, 0.078] | 0.724 | 0.249 | 0.020 | NO EDGE |
| 15m | B | AO_DMI_FE | ATR_2R | 18 | 0.461 | [-0.181, 1.040] | 2.011 | 1.154 | 0.197 | INCONCLUSIVE |

A=continuation/saucer; B=AO zero-cross; C=momentum reversal with known six-bar structure break. AO_DMI/FE include context. Proper parent for each single-indicator effect is AO_CONTEXT; DMI_FE is compared with DMI and additionally FE. 15m B is secondary and cannot replace a failed primary.

## Costs, side and best-event sensitivity

| Candidate | BASE n/R | Conservative R | Stress R | LONG n/R | SHORT n/R | ex-best1 R | ex-best3 R |
|---|---|---:|---:|---|---|---:|---:|
| 60m:A:AO_ONLY:ATR_2R | 359/-0.112 | -0.215 | -0.319 | 182/-0.147 | 177/-0.075 | -0.117 | -0.129 |
| 60m:A:AO_CONTEXT:ATR_2R | 57/0.028 | -0.069 | -0.165 | 31/-0.196 | 26/0.294 | -0.006 | -0.078 |
| 60m:A:AO_DMI:ATR_2R | 21/-0.156 | -0.260 | -0.364 | 12/-0.482 | 9/0.278 | -0.261 | -0.500 |
| 60m:A:AO_FE:ATR_2R | 40/-0.040 | -0.137 | -0.235 | 24/-0.103 | 16/0.054 | -0.090 | -0.198 |
| 60m:A:AO_DMI_FE:ATR_2R | 16/-0.045 | -0.155 | -0.266 | 10/-0.357 | 6/0.476 | -0.174 | -0.491 |
| 60m:A:AO_ONLY:STRUCTURE_2R | 351/-0.088 | -0.188 | -0.289 | 177/-0.117 | 174/-0.058 | -0.094 | -0.105 |
| 60m:A:AO_CONTEXT:STRUCTURE_2R | 52/0.190 | 0.120 | 0.051 | 27/0.191 | 25/0.188 | 0.155 | 0.083 |
| 60m:A:AO_DMI:STRUCTURE_2R | 18/0.308 | 0.240 | 0.173 | 10/0.148 | 8/0.507 | 0.212 | -0.016 |
| 60m:A:AO_FE:STRUCTURE_2R | 35/0.326 | 0.258 | 0.190 | 20/0.384 | 15/0.249 | 0.279 | 0.176 |
| 60m:A:AO_DMI_FE:STRUCTURE_2R | 13/0.710 | 0.640 | 0.569 | 8/0.457 | 5/1.115 | 0.609 | 0.346 |
| 60m:B:AO_ONLY:ATR_2R | 337/-0.159 | -0.264 | -0.369 | 157/-0.126 | 180/-0.188 | -0.165 | -0.178 |
| 60m:B:AO_CONTEXT:ATR_2R | 74/-0.305 | -0.427 | -0.549 | 40/-0.260 | 34/-0.358 | -0.336 | -0.400 |
| 60m:B:AO_DMI:ATR_2R | 7/-0.689 | -0.836 | -0.983 | 3/-1.222 | 4/-0.289 | -1.106 | -1.230 |
| 60m:B:AO_FE:ATR_2R | 54/-0.124 | -0.243 | -0.363 | 31/-0.142 | 23/-0.100 | -0.163 | -0.245 |
| 60m:B:AO_DMI_FE:ATR_2R | 5/-0.464 | -0.596 | -0.728 | 2/-1.205 | 3/0.030 | -1.032 | -1.207 |
| 60m:B:AO_ONLY:STRUCTURE_2R | 304/-0.155 | -0.239 | -0.324 | 141/-0.189 | 163/-0.125 | -0.162 | -0.176 |
| 60m:B:AO_CONTEXT:STRUCTURE_2R | 66/-0.265 | -0.363 | -0.461 | 36/-0.281 | 30/-0.244 | -0.299 | -0.370 |
| 60m:B:AO_DMI:STRUCTURE_2R | 4/-0.366 | -0.457 | -0.548 | 1/-1.112 | 3/-0.117 | -1.100 | -1.124 |
| 60m:B:AO_FE:STRUCTURE_2R | 47/-0.192 | -0.281 | -0.370 | 28/-0.268 | 19/-0.081 | -0.239 | -0.338 |
| 60m:B:AO_DMI_FE:STRUCTURE_2R | 3/-0.113 | -0.201 | -0.290 | 1/-1.112 | 2/0.387 | -1.088 | NA |
| 60m:C:AO_ONLY:ATR_2R | 149/0.028 | -0.082 | -0.192 | 73/0.062 | 76/-0.004 | 0.015 | -0.011 |
| 60m:C:AO_CONTEXT:ATR_2R | 39/-0.175 | -0.292 | -0.409 | 19/-0.062 | 20/-0.283 | -0.230 | -0.348 |
| 60m:C:AO_DMI:ATR_2R | 22/-0.324 | -0.436 | -0.548 | 11/0.025 | 11/-0.673 | -0.430 | -0.674 |
| 60m:C:AO_FE:ATR_2R | 14/-0.419 | -0.542 | -0.666 | 5/-0.136 | 9/-0.576 | -0.594 | -0.942 |
| 60m:C:AO_DMI_FE:ATR_2R | 7/-0.821 | -0.934 | -1.047 | 2/-1.100 | 5/-0.710 | -0.979 | -1.191 |
| 60m:C:AO_ONLY:STRUCTURE_2R | 140/-0.023 | -0.093 | -0.163 | 67/-0.006 | 73/-0.038 | -0.037 | -0.066 |
| 60m:C:AO_CONTEXT:STRUCTURE_2R | 36/-0.135 | -0.206 | -0.277 | 16/-0.412 | 20/0.086 | -0.195 | -0.323 |
| 60m:C:AO_DMI:STRUCTURE_2R | 20/0.170 | 0.106 | 0.043 | 9/0.013 | 11/0.299 | 0.076 | -0.141 |
| 60m:C:AO_FE:STRUCTURE_2R | 12/-0.422 | -0.506 | -0.590 | 3/-0.726 | 9/-0.321 | -0.631 | -0.896 |
| 60m:C:AO_DMI_FE:STRUCTURE_2R | 6/-0.431 | -0.503 | -0.576 | 1/-1.096 | 5/-0.298 | -0.696 | -1.121 |
| 15m:B:AO_ONLY:ATR_2R | 1379/-0.361 | -0.598 | -0.835 | 663/-0.343 | 716/-0.378 | -0.363 | -0.366 |
| 15m:B:AO_CONTEXT:ATR_2R | 177/-0.222 | -0.471 | -0.719 | 87/-0.282 | 90/-0.165 | -0.234 | -0.258 |
| 15m:B:AO_DMI:ATR_2R | 26/0.264 | 0.021 | -0.222 | 9/0.211 | 17/0.292 | 0.202 | 0.062 |
| 15m:B:AO_FE:ATR_2R | 103/-0.203 | -0.458 | -0.713 | 54/-0.351 | 49/-0.039 | -0.223 | -0.263 |
| 15m:B:AO_DMI_FE:ATR_2R | 18/0.461 | 0.210 | -0.040 | 5/0.243 | 13/0.544 | 0.381 | 0.192 |

## Temporal stability / fixed walk-forward

| Candidate | Dev n/R | Validation n/R | 2024 n/R | 2025 n/R | 2026 partial n/R |
|---|---|---|---|---|---|
| 60m:A:AO_ONLY:ATR_2R | 268/-0.154 | 270/-0.187 | 137/-0.018 | 132/-0.174 | 90/-0.162 |
| 60m:A:AO_CONTEXT:ATR_2R | 54/-0.111 | 35/-0.023 | 23/0.071 | 16/0.040 | 18/-0.038 |
| 60m:A:AO_DMI:ATR_2R | 22/-0.215 | 12/0.244 | 7/-0.269 | 6/-0.050 | 8/-0.137 |
| 60m:A:AO_FE:ATR_2R | 30/-0.371 | 22/-0.020 | 19/-0.065 | 10/-0.165 | 11/0.118 |
| 60m:A:AO_DMI_FE:ATR_2R | 14/-0.387 | 8/0.188 | 7/-0.269 | 4/-0.267 | 5/0.447 |
| 60m:A:AO_ONLY:STRUCTURE_2R | 264/-0.194 | 261/-0.173 | 135/0.012 | 127/-0.204 | 89/-0.072 |
| 60m:A:AO_CONTEXT:STRUCTURE_2R | 53/-0.102 | 33/0.022 | 22/0.325 | 13/0.135 | 17/0.056 |
| 60m:A:AO_DMI:STRUCTURE_2R | 22/-0.193 | 11/-0.029 | 6/0.286 | 4/0.422 | 8/0.267 |
| 60m:A:AO_FE:STRUCTURE_2R | 29/-0.233 | 20/0.096 | 18/0.327 | 7/0.397 | 10/0.275 |
| 60m:A:AO_DMI_FE:STRUCTURE_2R | 14/-0.103 | 7/-0.272 | 6/0.286 | 2/1.063 | 5/1.079 |
| 60m:B:AO_ONLY:ATR_2R | 244/-0.078 | 259/-0.072 | 131/-0.063 | 126/-0.281 | 80/-0.124 |
| 60m:B:AO_CONTEXT:ATR_2R | 43/-0.369 | 65/-0.116 | 27/-0.277 | 33/-0.269 | 14/-0.445 |
| 60m:B:AO_DMI:ATR_2R | 4/-0.225 | 6/0.516 | 2/-0.857 | 3/-0.199 | 2/-1.257 |
| 60m:B:AO_FE:ATR_2R | 24/-0.518 | 39/-0.076 | 22/-0.221 | 24/-0.001 | 8/-0.229 |
| 60m:B:AO_DMI_FE:ATR_2R | 4/-0.225 | 2/1.855 | 2/-0.857 | 2/0.325 | 1/-1.256 |
| 60m:B:AO_ONLY:STRUCTURE_2R | 229/-0.087 | 224/-0.101 | 120/-0.240 | 111/-0.181 | 73/0.024 |
| 60m:B:AO_CONTEXT:STRUCTURE_2R | 41/-0.377 | 58/-0.272 | 24/-0.206 | 29/-0.282 | 13/-0.335 |
| 60m:B:AO_DMI:STRUCTURE_2R | 2/-1.035 | 5/-0.227 | 1/-1.065 | 2/0.357 | 1/-1.112 |
| 60m:B:AO_FE:STRUCTURE_2R | 22/-0.622 | 33/-0.240 | 19/-0.172 | 20/-0.206 | 8/-0.207 |
| 60m:B:AO_DMI_FE:STRUCTURE_2R | 2/-1.035 | 1/1.570 | 1/-1.065 | 1/1.838 | 1/-1.112 |
| 60m:C:AO_ONLY:ATR_2R | 98/-0.046 | 107/-0.213 | 56/0.367 | 54/-0.194 | 39/-0.150 |
| 60m:C:AO_CONTEXT:ATR_2R | 22/-0.445 | 21/0.111 | 10/0.156 | 13/0.079 | 16/-0.589 |
| 60m:C:AO_DMI:ATR_2R | 11/-0.383 | 7/-0.386 | 5/-0.320 | 6/0.043 | 11/-0.526 |
| 60m:C:AO_FE:ATR_2R | 11/-0.759 | 16/0.176 | 5/0.042 | 4/-0.883 | 5/-0.509 |
| 60m:C:AO_DMI_FE:ATR_2R | 8/-0.621 | 6/-0.272 | 2/-1.100 | 2/-0.594 | 3/-0.787 |
| 60m:C:AO_ONLY:STRUCTURE_2R | 93/-0.032 | 96/-0.197 | 55/0.225 | 50/-0.134 | 35/-0.253 |
| 60m:C:AO_CONTEXT:STRUCTURE_2R | 21/-0.514 | 16/0.242 | 9/-0.168 | 12/0.140 | 15/-0.336 |
| 60m:C:AO_DMI:STRUCTURE_2R | 11/-0.622 | 7/0.385 | 4/0.269 | 6/0.535 | 10/-0.088 |
| 60m:C:AO_FE:STRUCTURE_2R | 10/-0.842 | 13/0.538 | 4/-0.392 | 3/-0.878 | 5/-0.172 |
| 60m:C:AO_DMI_FE:STRUCTURE_2R | 8/-0.788 | 6/0.625 | 1/-1.096 | 2/-0.744 | 3/-0.001 |
| 15m:B:AO_ONLY:ATR_2R | 990/-0.245 | 1069/-0.310 | 520/-0.296 | 514/-0.373 | 345/-0.443 |
| 15m:B:AO_CONTEXT:ATR_2R | 115/-0.170 | 118/-0.322 | 68/-0.128 | 75/-0.278 | 34/-0.289 |
| 15m:B:AO_DMI:ATR_2R | 21/-0.148 | 18/-0.060 | 12/0.297 | 10/0.236 | 4/0.233 |
| 15m:B:AO_FE:ATR_2R | 75/0.008 | 73/-0.290 | 40/-0.052 | 44/-0.210 | 19/-0.503 |
| 15m:B:AO_DMI_FE:ATR_2R | 14/0.161 | 13/-0.059 | 7/0.605 | 8/0.229 | 3/0.743 |

2022 and2023 are the first fixed expanding-history folds. All annual results2020–2026, regimes, LONG/SHORT, costs, win rate, quantiles, gross/net returns, R, profit factor, drawdown, exposure, MAE/MFE, duration, first5m adverse rate and entry drift are in results.json and metrics.csv. R drawdown is cumulative risk-unit diagnostic; unit-notional drawdown is separate. Neither is account equity. Exposure/frequency denominators span first entry through last exit in each reported cohort, explicitly recorded; they are descriptive active-span rates, not full-calendar capital utilization.

## Attrition and exclusions

~~~json
{
  "primary": {
    "A": {
      "raw_events": 2831,
      "ineligible": 69,
      "thinned": 1865,
      "anchors": 897,
      "random_timestamps_matched": 850,
      "excluded": {
        "STRUCTURE_2R:INVALID_STOP": 21
      }
    },
    "B": {
      "raw_events": 2669,
      "ineligible": 67,
      "thinned": 1762,
      "anchors": 840,
      "random_timestamps_matched": 814,
      "excluded": {
        "STRUCTURE_2R:INVALID_STOP": 83
      }
    },
    "C": {
      "raw_events": 492,
      "ineligible": 8,
      "thinned": 130,
      "anchors": 354,
      "random_timestamps_matched": 354,
      "excluded": {
        "STRUCTURE_2R:INVALID_STOP": 25
      }
    }
  },
  "secondary": {
    "B": {
      "raw_events": 11134,
      "ineligible": 181,
      "thinned": 7515,
      "anchors": 3438,
      "random_timestamps_matched": 3393,
      "excluded": {}
    }
  }
}
~~~

Per-candidate attrition records all anchors, surviving trades and removed observations. Technical exclusions are distinct from indicator removals. Controls unmatched or with invalid outcomes are omitted from paired comparisons, never assigned zero profit. Matching uses year-month, side and causal4H SMA200 regime, with fixed seed and nonoverlap. It does not match future outcomes.

## Objectively selected examples

Earliest chronological positive and negative evaluation trade, per family, fixed full-filter ATR exit. No replacement example is selected when a category is empty. These examples cannot calibrate rules.

| Family/outcome | Signal available UTC | Entry UTC | Side | Entry | Stop | Target | Exit UTC/reason | Net R |
|---|---|---|---|---:|---:|---:|---|---:|
| A/positive | 2024-07-07T22:00:00+00:00 | 2024-07-07T22:00:00+00:00 | SHORT | 56566.00 | 57206.40 | 55285.21 | 2024-07-08T00:45:00+00:00/TARGET | 1.902 |
| A/negative | 2024-02-11T04:00:00+00:00 | 2024-02-11T04:00:00+00:00 | LONG | 48517.60 | 48049.68 | 49453.43 | 2024-02-11T07:50:00+00:00/STOP | -1.124 |
| B/positive | 2025-03-16T03:00:00+00:00 | 2025-03-16T03:00:00+00:00 | SHORT | 83921.90 | 84424.95 | 82915.80 | 2025-03-16T11:20:00+00:00/TARGET | 1.808 |
| B/negative | 2024-05-14T09:00:00+00:00 | 2024-05-14T09:00:00+00:00 | SHORT | 61829.60 | 62459.25 | 60570.29 | 2024-05-15T09:00:00+00:00/TIME | -0.560 |
| C/positive | 2025-11-28T18:00:00+00:00 | 2025-11-28T18:00:00+00:00 | SHORT | 90621.20 | 91702.93 | 88457.74 | 2025-11-29T18:00:00+00:00/TIME | 0.124 |
| C/negative | 2024-04-19T07:00:00+00:00 | 2024-04-19T07:00:00+00:00 | LONG | 64595.90 | 63004.83 | 67778.05 | 2024-04-19T23:05:00+00:00/STOP | -1.053 |

## Uncertainty, decision criteria and limitations

Seeded5000-draw calendar30-day block bootstrap, joint for paired/nested comparisons;95% intervals. Promising additionally requires one-sided0.05/35 adjusted lower bound>0, evaluation n>=100 and each side>=30, positive conservative lower95 bound and control/incremental lower95 bounds, PF>1, positive validation, positive every evaluation year and positive after removing best3. Single-block uncertainty is unavailable, not zero. Net/conservative/control-negative candidates are NO EDGE; remaining insufficient evidence is INCONCLUSIVE. These classifications were fixed before outcomes.

Historical reuse, cross-variant dependence, residual matched-control confounding, sparse strict gates, gap resets and fixed-spacing opportunity loss limit inference. No exact liquidity, latency, funding mark price, Bitunix execution or prospective profitability is demonstrated. No automatic observer is created.

## Conclusions

All35 comparisons: {"INCONCLUSIVE": 7, "NO EDGE": 28}. No best exit is selected.

- Hypothesis A: **INCONCLUSIVE**. Individual NO EDGE variants are retained explicitly.
- Hypothesis B: **NO EDGE**. Individual NO EDGE variants are retained explicitly.
- Hypothesis C: **INCONCLUSIVE**. Individual NO EDGE variants are retained explicitly.

**DO NOT INTEGRATE into operability gates, Guardian or V8.** Any future observer requires a separately approved protocol and prospective append-only signals/outcomes. Historical positives alone do not authorize it.

Reproduce: python -m research.bitman_entry_lab.data --download --cache research/cache/entry_public_data; python -m research.bitman_entry_lab.study run --cache research/cache/entry_public_data. Published lock must be verified, not refrozen to fit another dataset.

TRADE AUTHORITY: NONE.
