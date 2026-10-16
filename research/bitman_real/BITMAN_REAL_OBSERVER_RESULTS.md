# I-GOD BITMAN REAL OBSERVER v0.1

**INCONCLUSIVE**

KONKORDE_PROXY · SHADOW ONLY · trade_authority=false.
**EXACT BITMAN KONKORDE PARITY: NOT PROVEN. SHORT_LOGIC_NOT_PROVEN.**
BITMAN Phase2 remains officially **REJECT**, PR #22 / `44029b4768e2b4bc47643bb51bf8a28432623a39`.
Public-data cutoff: `2026-10-15T19:00:00Z`. Separate branch `bitman-real-observer`, from main `9d0024a45d8e40193162a3864a876ca5ab61d1da`.
`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`

## Scope and evidence

This measures post-event price distributions, not a complete strategy, actual fills or account profitability. All returns below are GROSS/raw BTC orientation, including EXIT. No commission/funding-adjusted PnL is claimed. No order, sizing, stop, take-profit, leverage or operational direction is changed.
Primary video observations were supplied by the user from direct viewing. Automated video retrieval failed; no invented transcript or independent viewing claim. The public Pine adapter is the numerical reference, not the private Micro Finanzas Personales Koncorde 2.0 formula. See [SOURCES.md](SOURCES.md).

## Exact public proxy formula

```text
P = OHLC4; T = HLC3
RSI = Wilder RSI14(P), SMA seed of14 changes
MF+ = SUM14(T*V where delta(T)>0); MF- = SUM14(T*V where delta(T)<0)
MFI = 100*MF+/(MF++MF-)
BollOsc = 100*(P-SMA25(P))/(4*populationSTD25(P))
K = 100*(P-lowest21(L))/(highest21(H)-lowest21(L))
Stoch = SMA3(K)
mountain = (RSI+MFI+BollOsc+Stoch/3)/2
MA = EMA15(mountain), alpha2/16, seed first finite value
```

Brown mountain only; no PVI/NVI hands segmentation. It is a composite trend area with volume through MFI, not direct institutional order flow. Private formula/normalization/parameters/plotting and TV parity are unknown. Zero denominators remain unavailable. No backfill or interpolation across gaps. See SOURCES for original public author links and licensing boundary.

## Events, direction and preregistration

Inside: `min(0,mountain)<MA<max(0,mountain)`. Touching boundary is outside. ENTRY outside→inside; EXIT inside→outside. First valid state/gap recovery is context, not a new event. REENTRY is an ENTRY subset after EXIT within N same-TF bars. All N=1/2/3/5 reported; no winner selected. Observer requires an explicit N; there is no hidden optimized default.
`distance_to_zero=abs(MA)`; also mountain distance. `separation=abs(mountain-MA)` while inside, to the outer brown edge; compare consecutive inside bars only. NEW_INSIDE has no prior inside comparison. Shrinkage is diagnostic, not a new exit rule.
Directional display: LONG = positive mountain + inside + +DI>−DI. No mandatory ADX magnitude/AO/BBWP gate, no score. This is a descriptive interpretation, not permission to trade or a statistical validation claim. Other forming positive cases are SETUP_FORMING; other contexts WAIT. Bearish mountain/DI/AO context is BLOCKED/SHORT_LOGIC_NOT_PROVEN. v0.1 cannot emit SHORT.
ADX smoothing14/DI14; AO SMA5−SMA34 of HL2. BBWP CLOSE/SMA7/popSTD, strictly-lower rank against PRIOR100 widths. EXPANDING means percentile slope>0; no fitted compression zones. Trend Speed117/2.7/150/100/From start remains NOT IMPLEMENTED / FORMULA NOT VERIFIED. Production ML RSI LOW29/EMA4 unchanged; LOW27/SMA4 is separate, unimplemented research metadata.
Protocol hash/source fingerprints locked before this study read outcomes. TRAIN2020–2021, VALIDATION2022–2023, TEST2024–cutoff, reused OOS. No parameter ranking/selection. Near/far and separation tertiles fit TRAIN only; these groups are not signal thresholds. Public hourly dataset reused from Phase2 only as data, never rules.

## Outcome methodology

Each signal is known at actual TF close. Reference is that closed candle price; future complete public1H candles start at/after the signal timestamp, even for4H/1D events. Thus1h and4h outcomes after a daily signal do not use unfinished daily data to generate it. Gaps and horizon/split boundaries are censored. MFE=max(0,max futureHigh/reference−1); MAE=min(0,min futureLow/reference−1). No retrospective intrabar fills.
Independent first +1/−1/+2/−2 hit times are retained. Same hourly candle touching both barriers is AMBIGUOUS, never an invented winning order; neither is UNRESOLVED. Percentages use mature observations including ambiguous/unresolved; not invented win probabilities.
Controls: deterministic non-event timestamps in the same UTC month/hour and same trailing24TFbar trend sign. Matching never inspects future returns. Missing exact matches are excluded from paired inference. Calendar-week block bootstrap500/seed9821; overlapping events, reused controls, selection exposure and secondary-table multiplicity limit inference. Primary endpoint is24h matched difference; EXIT is expected to precede lower BTC returns, not an automatically profitable SHORT.

## Frozen primary24h matched-control evidence

| TF | Event | Split | matched n | event−control raw | hypothesis-signed excess | signed CI95 |
|---|---|---|---:|---:|---:|---|
| 1H | KONKORDE_ENTRY | TRAIN | 1155 | -0.059% | -0.059% | [-0.442%, +0.344%] |
| 1H | KONKORDE_ENTRY | VALIDATION | 1223 | -0.038% | -0.038% | [-0.307%, +0.266%] |
| 1H | KONKORDE_ENTRY | TEST | 1629 | +0.024% | +0.024% | [-0.199%, +0.227%] |
| 1H | KONKORDE_ENTRY | 2024 | 573 | -0.157% | -0.157% | [-0.532%, +0.219%] |
| 1H | KONKORDE_ENTRY | 2025 | 583 | +0.045% | +0.045% | [-0.259%, +0.356%] |
| 1H | KONKORDE_ENTRY | 2026 | 473 | +0.218% | +0.218% | [-0.104%, +0.524%] |
| 1H | KONKORDE_EXIT | TRAIN | 1156 | -0.016% | +0.016% | [-0.396%, +0.454%] |
| 1H | KONKORDE_EXIT | VALIDATION | 1222 | -0.118% | +0.118% | [-0.141%, +0.389%] |
| 1H | KONKORDE_EXIT | TEST | 1630 | -0.054% | +0.054% | [-0.150%, +0.249%] |
| 1H | KONKORDE_EXIT | 2024 | 574 | +0.030% | -0.030% | [-0.377%, +0.348%] |
| 1H | KONKORDE_EXIT | 2025 | 583 | -0.103% | +0.103% | [-0.149%, +0.408%] |
| 1H | KONKORDE_EXIT | 2026 | 473 | -0.096% | +0.096% | [-0.295%, +0.469%] |
| 4H | KONKORDE_ENTRY | TRAIN | 289 | +0.320% | +0.320% | [-0.330%, +1.030%] |
| 4H | KONKORDE_ENTRY | VALIDATION | 305 | +0.131% | +0.131% | [-0.328%, +0.568%] |
| 4H | KONKORDE_ENTRY | TEST | 391 | -0.129% | -0.129% | [-0.442%, +0.213%] |
| 4H | KONKORDE_ENTRY | 2024 | 147 | -0.368% | -0.368% | [-0.839%, +0.156%] |
| 4H | KONKORDE_ENTRY | 2025 | 137 | -0.261% | -0.261% | [-0.726%, +0.183%] |
| 4H | KONKORDE_ENTRY | 2026 | 107 | +0.369% | +0.369% | [-0.340%, +1.124%] |
| 4H | KONKORDE_EXIT | TRAIN | 288 | -0.394% | +0.394% | [-0.294%, +1.009%] |
| 4H | KONKORDE_EXIT | VALIDATION | 305 | +0.133% | -0.133% | [-0.565%, +0.362%] |
| 4H | KONKORDE_EXIT | TEST | 392 | +0.038% | -0.038% | [-0.387%, +0.322%] |
| 4H | KONKORDE_EXIT | 2024 | 147 | +0.190% | -0.190% | [-0.838%, +0.481%] |
| 4H | KONKORDE_EXIT | 2025 | 138 | -0.070% | +0.070% | [-0.371%, +0.530%] |
| 4H | KONKORDE_EXIT | 2026 | 107 | -0.033% | +0.033% | [-0.582%, +0.717%] |
| 1D | KONKORDE_ENTRY | TRAIN | 53 | +0.224% | +0.224% | [-0.960%, +1.496%] |
| 1D | KONKORDE_ENTRY | VALIDATION | 44 | -1.254% | -1.254% | [-2.417%, -0.187%] |
| 1D | KONKORDE_ENTRY | TEST | 64 | -0.432% | -0.432% | [-1.253%, +0.418%] |
| 1D | KONKORDE_ENTRY | 2024 | 23 | -0.950% | -0.950% | [-2.443%, +0.389%] |
| 1D | KONKORDE_ENTRY | 2025 | 25 | -0.987% | -0.987% | [-2.283%, +0.289%] |
| 1D | KONKORDE_ENTRY | 2026 | 16 | +1.179% | +1.179% | [+0.058%, +2.456%] |
| 1D | KONKORDE_EXIT | TRAIN | 55 | +0.054% | -0.054% | [-1.451%, +1.448%] |
| 1D | KONKORDE_EXIT | VALIDATION | 44 | +0.232% | -0.232% | [-1.438%, +0.935%] |
| 1D | KONKORDE_EXIT | TEST | 64 | -0.382% | +0.382% | [-0.342%, +1.091%] |
| 1D | KONKORDE_EXIT | 2024 | 23 | -0.034% | +0.034% | [-1.468%, +1.743%] |
| 1D | KONKORDE_EXIT | 2025 | 24 | -1.055% | +1.055% | [+0.095%, +1.956%] |
| 1D | KONKORDE_EXIT | 2026 | 17 | +0.098% | -0.098% | [-1.322%, +0.810%] |

Signed excess flips EXIT only for its stated bearish-outcome hypothesis; the forward-return tables and independent hit times remain raw BTC orientation. This does NOT implement SHORT.

## Forward returns / MFE / MAE across horizons

### 1H

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KONKORDE_ENTRY/TRAIN/1h | 1157 | 1157 | +0.025% | +0.000% | +0.386% | -0.366% | +14.780% | +2.161% | +4.235% |
| KONKORDE_ENTRY/TRAIN/4h | 1157 | 1157 | +0.002% | -0.014% | +0.732% | -0.754% | +32.844% | +2.852% | +16.249% |
| KONKORDE_ENTRY/TRAIN/12h | 1157 | 1157 | +0.128% | +0.089% | +1.396% | -1.406% | +44.512% | +3.111% | +32.584% |
| KONKORDE_ENTRY/TRAIN/24h | 1157 | 1155 | +0.330% | +0.257% | +2.116% | -1.935% | +48.139% | +3.203% | +42.684% |
| KONKORDE_ENTRY/TRAIN/48h | 1157 | 1154 | +0.813% | +0.749% | +3.325% | -2.778% | +49.133% | +3.206% | +49.827% |
| KONKORDE_ENTRY/TRAIN/72h | 1157 | 1152 | +1.175% | +1.092% | +4.269% | -3.577% | +49.392% | +3.212% | +52.431% |
| KONKORDE_ENTRY/VALIDATION/1h | 1225 | 1225 | +0.008% | -0.023% | +0.224% | -0.229% | +10.041% | +0.816% | +2.122% |
| KONKORDE_ENTRY/VALIDATION/4h | 1225 | 1225 | -0.049% | -0.055% | +0.442% | -0.500% | +23.918% | +1.224% | +9.633% |
| KONKORDE_ENTRY/VALIDATION/12h | 1225 | 1224 | -0.012% | -0.064% | +0.900% | -0.940% | +39.461% | +1.634% | +22.794% |
| KONKORDE_ENTRY/VALIDATION/24h | 1225 | 1223 | +0.001% | -0.019% | +1.374% | -1.393% | +46.770% | +1.799% | +33.115% |
| KONKORDE_ENTRY/VALIDATION/48h | 1225 | 1220 | -0.026% | -0.041% | +2.101% | -2.062% | +49.262% | +1.885% | +42.459% |
| KONKORDE_ENTRY/VALIDATION/72h | 1225 | 1218 | +0.004% | +0.066% | +2.742% | -2.553% | +49.918% | +1.888% | +46.470% |
| KONKORDE_ENTRY/TEST/1h | 1633 | 1633 | +0.017% | -0.003% | +0.222% | -0.229% | +6.797% | +0.000% | +1.347% |
| KONKORDE_ENTRY/TEST/4h | 1633 | 1633 | +0.029% | +0.015% | +0.474% | -0.464% | +21.923% | +0.184% | +5.818% |
| KONKORDE_ENTRY/TEST/12h | 1633 | 1631 | +0.066% | +0.080% | +0.905% | -0.838% | +38.688% | +0.368% | +18.516% |
| KONKORDE_ENTRY/TEST/24h | 1633 | 1630 | +0.157% | +0.083% | +1.279% | -1.235% | +46.074% | +0.368% | +30.613% |
| KONKORDE_ENTRY/TEST/48h | 1633 | 1627 | +0.197% | +0.098% | +1.908% | -1.861% | +50.768% | +0.430% | +41.733% |
| KONKORDE_ENTRY/TEST/72h | 1633 | 1626 | +0.374% | +0.214% | +2.474% | -2.321% | +51.292% | +0.431% | +47.109% |
| KONKORDE_EXIT/TRAIN/1h | 1158 | 1158 | +0.053% | +0.065% | +0.369% | -0.375% | +12.176% | +2.504% | +4.318% |
| KONKORDE_EXIT/TRAIN/4h | 1158 | 1158 | +0.117% | +0.076% | +0.735% | -0.807% | +31.088% | +3.109% | +15.544% |
| KONKORDE_EXIT/TRAIN/12h | 1158 | 1157 | +0.091% | +0.150% | +1.386% | -1.392% | +42.092% | +3.457% | +32.498% |
| KONKORDE_EXIT/TRAIN/24h | 1158 | 1156 | +0.289% | +0.353% | +2.153% | -1.987% | +46.021% | +3.460% | +43.339% |
| KONKORDE_EXIT/TRAIN/48h | 1158 | 1155 | +0.706% | +0.765% | +3.326% | -2.740% | +46.753% | +3.463% | +50.563% |
| KONKORDE_EXIT/TRAIN/72h | 1158 | 1153 | +1.140% | +0.971% | +4.207% | -3.571% | +46.748% | +3.469% | +53.513% |
| KONKORDE_EXIT/VALIDATION/1h | 1225 | 1225 | -0.006% | +0.023% | +0.236% | -0.242% | +6.694% | +0.490% | +0.735% |
| KONKORDE_EXIT/VALIDATION/4h | 1225 | 1224 | -0.054% | +0.010% | +0.459% | -0.506% | +20.261% | +0.654% | +7.271% |
| KONKORDE_EXIT/VALIDATION/12h | 1225 | 1223 | -0.032% | +0.027% | +0.899% | -0.928% | +38.348% | +1.226% | +21.341% |
| KONKORDE_EXIT/VALIDATION/24h | 1225 | 1222 | -0.057% | +0.011% | +1.341% | -1.432% | +44.272% | +1.391% | +30.933% |
| KONKORDE_EXIT/VALIDATION/48h | 1225 | 1220 | -0.090% | +0.012% | +2.108% | -2.117% | +47.049% | +1.475% | +41.148% |
| KONKORDE_EXIT/VALIDATION/72h | 1225 | 1218 | +0.018% | +0.127% | +2.732% | -2.616% | +47.701% | +1.478% | +45.074% |
| KONKORDE_EXIT/TEST/1h | 1632 | 1632 | -0.015% | +0.011% | +0.238% | -0.236% | +5.392% | +0.245% | +0.797% |
| KONKORDE_EXIT/TEST/4h | 1632 | 1632 | -0.001% | +0.014% | +0.454% | -0.471% | +19.608% | +0.490% | +6.005% |
| KONKORDE_EXIT/TEST/12h | 1632 | 1631 | +0.029% | +0.060% | +0.831% | -0.861% | +36.297% | +0.552% | +17.351% |
| KONKORDE_EXIT/TEST/24h | 1632 | 1630 | +0.115% | +0.126% | +1.255% | -1.252% | +45.031% | +0.613% | +28.650% |
| KONKORDE_EXIT/TEST/48h | 1632 | 1627 | +0.152% | +0.187% | +1.918% | -1.874% | +49.109% | +0.615% | +40.996% |
| KONKORDE_EXIT/TEST/72h | 1632 | 1626 | +0.321% | +0.178% | +2.434% | -2.362% | +49.754% | +0.615% | +46.802% |
### 4H

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KONKORDE_ENTRY/TRAIN/1h | 289 | 289 | -0.031% | -0.022% | +0.425% | -0.364% | +11.073% | +3.806% | +3.460% |
| KONKORDE_ENTRY/TRAIN/4h | 289 | 289 | +0.127% | +0.046% | +0.776% | -0.679% | +31.834% | +4.498% | +15.917% |
| KONKORDE_ENTRY/TRAIN/12h | 289 | 289 | +0.317% | +0.121% | +1.407% | -1.289% | +44.637% | +4.844% | +30.450% |
| KONKORDE_ENTRY/TRAIN/24h | 289 | 289 | +0.344% | +0.099% | +1.995% | -1.998% | +47.059% | +4.844% | +39.100% |
| KONKORDE_ENTRY/TRAIN/48h | 289 | 288 | +0.707% | +0.516% | +3.143% | -2.853% | +47.917% | +4.861% | +46.528% |
| KONKORDE_ENTRY/TRAIN/72h | 289 | 288 | +0.883% | +0.903% | +3.644% | -3.626% | +48.264% | +4.861% | +47.222% |
| KONKORDE_ENTRY/VALIDATION/1h | 305 | 305 | +0.042% | -0.036% | +0.269% | -0.274% | +11.803% | +1.967% | +3.934% |
| KONKORDE_ENTRY/VALIDATION/4h | 305 | 305 | -0.011% | -0.042% | +0.547% | -0.537% | +27.541% | +2.295% | +9.508% |
| KONKORDE_ENTRY/VALIDATION/12h | 305 | 305 | +0.074% | -0.037% | +0.939% | -0.860% | +40.000% | +2.623% | +21.967% |
| KONKORDE_ENTRY/VALIDATION/24h | 305 | 305 | +0.217% | -0.046% | +1.529% | -1.273% | +48.197% | +2.951% | +35.082% |
| KONKORDE_ENTRY/VALIDATION/48h | 305 | 304 | +0.235% | +0.005% | +2.336% | -2.032% | +50.658% | +3.289% | +44.079% |
| KONKORDE_ENTRY/VALIDATION/72h | 305 | 303 | +0.219% | +0.203% | +2.721% | -2.522% | +52.805% | +3.300% | +49.175% |
| KONKORDE_ENTRY/TEST/1h | 391 | 391 | -0.006% | -0.007% | +0.238% | -0.241% | +6.650% | +0.512% | +1.023% |
| KONKORDE_ENTRY/TEST/4h | 391 | 391 | +0.025% | -0.031% | +0.557% | -0.500% | +22.506% | +0.767% | +6.905% |
| KONKORDE_ENTRY/TEST/12h | 391 | 391 | +0.051% | -0.021% | +0.911% | -0.799% | +38.875% | +0.767% | +18.159% |
| KONKORDE_ENTRY/TEST/24h | 391 | 391 | -0.063% | -0.199% | +1.259% | -1.422% | +46.803% | +0.767% | +27.621% |
| KONKORDE_ENTRY/TEST/48h | 391 | 390 | +0.166% | -0.061% | +1.838% | -2.032% | +50.513% | +0.769% | +38.462% |
| KONKORDE_ENTRY/TEST/72h | 391 | 389 | +0.389% | +0.019% | +2.384% | -2.545% | +50.900% | +0.771% | +43.445% |
| KONKORDE_EXIT/TRAIN/1h | 288 | 288 | -0.094% | -0.026% | +0.383% | -0.492% | +12.153% | +2.083% | +3.819% |
| KONKORDE_EXIT/TRAIN/4h | 288 | 288 | -0.007% | +0.065% | +0.736% | -0.893% | +27.083% | +2.431% | +11.806% |
| KONKORDE_EXIT/TRAIN/12h | 288 | 288 | -0.192% | -0.014% | +1.204% | -1.611% | +39.236% | +2.431% | +24.306% |
| KONKORDE_EXIT/TRAIN/24h | 288 | 288 | +0.088% | +0.136% | +1.856% | -2.401% | +44.444% | +2.778% | +36.111% |
| KONKORDE_EXIT/TRAIN/48h | 288 | 288 | +0.806% | +0.512% | +3.297% | -2.973% | +44.792% | +2.778% | +43.750% |
| KONKORDE_EXIT/TRAIN/72h | 288 | 288 | +0.781% | +0.754% | +3.824% | -3.552% | +44.792% | +2.778% | +45.139% |
| KONKORDE_EXIT/VALIDATION/1h | 305 | 305 | +0.092% | +0.079% | +0.274% | -0.262% | +8.525% | +0.656% | +2.295% |
| KONKORDE_EXIT/VALIDATION/4h | 305 | 305 | +0.134% | +0.101% | +0.539% | -0.502% | +24.918% | +0.984% | +10.164% |
| KONKORDE_EXIT/VALIDATION/12h | 305 | 305 | +0.106% | +0.120% | +0.968% | -0.949% | +40.984% | +1.311% | +22.295% |
| KONKORDE_EXIT/VALIDATION/24h | 305 | 305 | +0.298% | +0.198% | +1.525% | -1.268% | +48.525% | +2.295% | +36.721% |
| KONKORDE_EXIT/VALIDATION/48h | 305 | 305 | +0.388% | +0.256% | +2.304% | -1.851% | +50.164% | +2.295% | +46.557% |
| KONKORDE_EXIT/VALIDATION/72h | 305 | 304 | +0.569% | +0.382% | +2.827% | -2.319% | +50.329% | +2.303% | +50.987% |
| KONKORDE_EXIT/TEST/1h | 392 | 392 | -0.004% | +0.041% | +0.259% | -0.263% | +4.592% | +0.765% | +0.510% |
| KONKORDE_EXIT/TEST/4h | 392 | 392 | -0.007% | +0.002% | +0.496% | -0.506% | +20.663% | +0.765% | +5.102% |
| KONKORDE_EXIT/TEST/12h | 392 | 392 | -0.033% | +0.063% | +0.809% | -0.894% | +34.949% | +0.765% | +14.796% |
| KONKORDE_EXIT/TEST/24h | 392 | 392 | +0.087% | +0.006% | +1.315% | -1.329% | +43.367% | +0.765% | +28.316% |
| KONKORDE_EXIT/TEST/48h | 392 | 390 | +0.133% | +0.004% | +1.907% | -2.087% | +46.154% | +0.769% | +39.744% |
| KONKORDE_EXIT/TEST/72h | 392 | 390 | +0.369% | +0.121% | +2.264% | -2.407% | +47.179% | +0.769% | +44.615% |
### 1D

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KONKORDE_ENTRY/TRAIN/1h | 54 | 54 | +0.060% | +0.017% | +0.421% | -0.357% | +12.963% | +1.852% | +7.407% |
| KONKORDE_ENTRY/TRAIN/4h | 54 | 54 | +0.030% | -0.168% | +0.622% | -0.808% | +29.630% | +1.852% | +12.963% |
| KONKORDE_ENTRY/TRAIN/12h | 54 | 54 | +0.108% | -0.069% | +1.335% | -1.238% | +42.593% | +1.852% | +24.074% |
| KONKORDE_ENTRY/TRAIN/24h | 54 | 54 | +0.313% | -0.231% | +1.639% | -1.946% | +42.593% | +1.852% | +29.630% |
| KONKORDE_ENTRY/TRAIN/48h | 54 | 54 | +0.216% | +0.404% | +2.479% | -2.546% | +44.444% | +1.852% | +42.593% |
| KONKORDE_ENTRY/TRAIN/72h | 54 | 54 | +0.813% | +0.154% | +2.760% | -2.783% | +44.444% | +1.852% | +46.296% |
| KONKORDE_ENTRY/VALIDATION/1h | 44 | 44 | +0.045% | -0.073% | +0.258% | -0.317% | +11.364% | +0.000% | +2.273% |
| KONKORDE_ENTRY/VALIDATION/4h | 44 | 44 | -0.240% | -0.018% | +0.476% | -0.554% | +25.000% | +0.000% | +9.091% |
| KONKORDE_ENTRY/VALIDATION/12h | 44 | 44 | -0.307% | -0.273% | +0.771% | -0.919% | +31.818% | +0.000% | +20.455% |
| KONKORDE_ENTRY/VALIDATION/24h | 44 | 44 | -0.950% | -0.523% | +0.902% | -1.655% | +34.091% | +0.000% | +29.545% |
| KONKORDE_ENTRY/VALIDATION/48h | 44 | 44 | -0.342% | +0.150% | +2.027% | -2.060% | +40.909% | +0.000% | +38.636% |
| KONKORDE_ENTRY/VALIDATION/72h | 44 | 44 | -0.225% | +0.246% | +2.606% | -2.892% | +40.909% | +0.000% | +43.182% |
| KONKORDE_ENTRY/TEST/1h | 64 | 64 | +0.055% | -0.011% | +0.250% | -0.294% | +7.812% | +0.000% | +1.562% |
| KONKORDE_ENTRY/TEST/4h | 64 | 64 | +0.141% | +0.123% | +0.468% | -0.419% | +29.688% | +0.000% | +7.812% |
| KONKORDE_ENTRY/TEST/12h | 64 | 64 | +0.262% | +0.195% | +1.033% | -0.650% | +50.000% | +0.000% | +18.750% |
| KONKORDE_ENTRY/TEST/24h | 64 | 64 | +0.268% | +0.081% | +1.734% | -0.933% | +64.062% | +0.000% | +40.625% |
| KONKORDE_ENTRY/TEST/48h | 64 | 64 | +0.373% | +0.396% | +2.408% | -1.596% | +70.312% | +0.000% | +57.812% |
| KONKORDE_ENTRY/TEST/72h | 64 | 64 | +0.639% | +0.501% | +2.981% | -2.009% | +71.875% | +0.000% | +64.062% |
| KONKORDE_EXIT/TRAIN/1h | 55 | 55 | -0.051% | +0.029% | +0.494% | -0.467% | +20.000% | +1.818% | +3.636% |
| KONKORDE_EXIT/TRAIN/4h | 55 | 55 | -0.566% | +0.004% | +0.599% | -0.905% | +30.909% | +1.818% | +5.455% |
| KONKORDE_EXIT/TRAIN/12h | 55 | 55 | -0.570% | -0.013% | +1.629% | -1.476% | +40.000% | +1.818% | +23.636% |
| KONKORDE_EXIT/TRAIN/24h | 55 | 55 | +0.169% | +0.441% | +1.975% | -2.285% | +41.818% | +1.818% | +36.364% |
| KONKORDE_EXIT/TRAIN/48h | 55 | 55 | +0.695% | +0.776% | +3.397% | -2.361% | +45.455% | +1.818% | +43.636% |
| KONKORDE_EXIT/TRAIN/72h | 55 | 54 | +1.242% | +1.400% | +4.126% | -3.014% | +48.148% | +1.852% | +44.444% |
| KONKORDE_EXIT/VALIDATION/1h | 44 | 44 | -0.017% | +0.042% | +0.299% | -0.349% | +6.818% | +0.000% | +2.273% |
| KONKORDE_EXIT/VALIDATION/4h | 44 | 44 | -0.074% | -0.008% | +0.406% | -0.600% | +20.455% | +0.000% | +4.545% |
| KONKORDE_EXIT/VALIDATION/12h | 44 | 44 | +0.023% | -0.118% | +0.643% | -0.898% | +34.091% | +0.000% | +20.455% |
| KONKORDE_EXIT/VALIDATION/24h | 44 | 44 | +0.181% | -0.153% | +1.180% | -1.491% | +43.182% | +0.000% | +36.364% |
| KONKORDE_EXIT/VALIDATION/48h | 44 | 44 | -0.311% | +0.221% | +2.313% | -2.207% | +47.727% | +0.000% | +52.273% |
| KONKORDE_EXIT/VALIDATION/72h | 44 | 44 | -0.756% | +0.336% | +2.526% | -2.677% | +47.727% | +0.000% | +52.273% |
| KONKORDE_EXIT/TEST/1h | 64 | 64 | +0.075% | +0.073% | +0.258% | -0.222% | +6.250% | +0.000% | +0.000% |
| KONKORDE_EXIT/TEST/4h | 64 | 64 | -0.053% | +0.131% | +0.539% | -0.703% | +21.875% | +0.000% | +4.688% |
| KONKORDE_EXIT/TEST/12h | 64 | 64 | +0.079% | +0.174% | +1.009% | -0.852% | +40.625% | +0.000% | +18.750% |
| KONKORDE_EXIT/TEST/24h | 64 | 64 | -0.586% | -0.220% | +1.092% | -1.526% | +48.438% | +0.000% | +29.688% |
| KONKORDE_EXIT/TEST/48h | 64 | 64 | -0.386% | -0.094% | +1.975% | -2.070% | +53.125% | +0.000% | +43.750% |
| KONKORDE_EXIT/TEST/72h | 64 | 64 | -0.456% | -0.544% | +2.403% | -2.523% | +54.688% | +0.000% | +50.000% |

## Independent first-touch timing, TEST24h

| TF/event | mature n | hit+1 | first hour median | hit−1 | first hour median | hit+2 | first hour median | hit−2 | first hour median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/KONKORDE_ENTRY | 1630 | +59.387% | 6.0 | +57.423% | 6.0 | +33.252% | 11.0 | +33.681% | 11.0 |
| 1H/KONKORDE_EXIT | 1630 | +59.141% | 7.0 | +58.037% | 6.0 | +30.982% | 11.0 | +33.620% | 10.0 |
| 4H/KONKORDE_ENTRY | 391 | +57.033% | 6.0 | +60.358% | 7.0 | +29.923% | 9.0 | +35.806% | 11.0 |
| 4H/KONKORDE_EXIT | 392 | +58.163% | 6.0 | +58.929% | 5.0 | +32.908% | 13.0 | +34.949% | 9.0 |
| 1D/KONKORDE_ENTRY | 64 | +73.438% | 7.0 | +46.875% | 8.0 | +40.625% | 13.0 | +28.125% | 15.0 |
| 1D/KONKORDE_EXIT | 64 | +60.938% | 5.0 | +64.062% | 8.0 | +29.688% | 12.0 | +39.062% | 15.0 |

## REENTRY sensitivity — no selected N

Subsets of ENTRY, not independent events or additional trades. Do not add their sample counts together. The observer requires an explicit presentation window; sample messages using3 are illustrative, not a recommendation.

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/N1/TRAIN/24h | 194 | 193 | +0.270% | +0.215% | +2.184% | -2.008% | +47.150% | +4.145% | +42.487% |
| 1H/N1/VALIDATION/24h | 222 | 222 | +0.046% | -0.027% | +1.201% | -1.314% | +45.946% | +1.351% | +30.180% |
| 1H/N1/TEST/24h | 288 | 287 | +0.186% | +0.328% | +1.345% | -1.059% | +47.387% | +0.000% | +31.707% |
| 1H/N2/TRAIN/24h | 338 | 337 | +0.320% | +0.221% | +2.114% | -1.935% | +48.071% | +3.561% | +43.027% |
| 1H/N2/VALIDATION/24h | 370 | 370 | +0.015% | -0.053% | +1.317% | -1.242% | +48.108% | +1.351% | +31.622% |
| 1H/N2/TEST/24h | 504 | 502 | +0.127% | +0.173% | +1.306% | -1.096% | +47.410% | +0.199% | +30.080% |
| 1H/N3/TRAIN/24h | 452 | 451 | +0.229% | +0.215% | +2.041% | -2.008% | +48.115% | +3.104% | +41.685% |
| 1H/N3/VALIDATION/24h | 482 | 482 | -0.084% | -0.085% | +1.293% | -1.270% | +48.340% | +1.867% | +30.913% |
| 1H/N3/TEST/24h | 653 | 651 | +0.174% | +0.155% | +1.306% | -1.084% | +47.926% | +0.154% | +31.644% |
| 1H/N5/TRAIN/24h | 585 | 584 | +0.280% | +0.251% | +2.101% | -1.972% | +49.658% | +3.253% | +41.952% |
| 1H/N5/VALIDATION/24h | 664 | 662 | -0.038% | -0.062% | +1.381% | -1.279% | +48.792% | +1.662% | +32.779% |
| 1H/N5/TEST/24h | 846 | 844 | +0.164% | +0.145% | +1.300% | -1.134% | +47.630% | +0.118% | +31.043% |
| 4H/N1/TRAIN/24h | 46 | 46 | +0.166% | -0.180% | +1.796% | -2.018% | +47.826% | +8.696% | +34.783% |
| 4H/N1/VALIDATION/24h | 50 | 50 | +0.057% | -0.127% | +1.569% | -1.367% | +44.000% | +4.000% | +32.000% |
| 4H/N1/TEST/24h | 66 | 66 | -0.179% | -0.352% | +0.964% | -1.278% | +40.909% | +1.515% | +33.333% |
| 4H/N2/TRAIN/24h | 80 | 80 | +0.182% | -0.130% | +1.808% | -1.991% | +46.250% | +7.500% | +31.250% |
| 4H/N2/VALIDATION/24h | 99 | 99 | +0.118% | +0.008% | +1.587% | -1.373% | +47.475% | +4.040% | +35.354% |
| 4H/N2/TEST/24h | 116 | 116 | -0.190% | -0.303% | +1.300% | -1.490% | +43.103% | +0.862% | +31.897% |
| 4H/N3/TRAIN/24h | 101 | 101 | +0.098% | +0.027% | +1.840% | -1.983% | +45.545% | +6.931% | +34.653% |
| 4H/N3/VALIDATION/24h | 130 | 130 | +0.276% | +0.007% | +1.580% | -1.299% | +49.231% | +3.077% | +37.692% |
| 4H/N3/TEST/24h | 139 | 139 | -0.180% | -0.282% | +1.335% | -1.441% | +44.604% | +0.719% | +32.374% |
| 4H/N5/TRAIN/24h | 140 | 140 | +0.481% | +0.373% | +1.981% | -1.703% | +48.571% | +5.000% | +40.000% |
| 4H/N5/VALIDATION/24h | 174 | 174 | +0.157% | -0.011% | +1.567% | -1.232% | +50.575% | +2.299% | +36.782% |
| 4H/N5/TEST/24h | 198 | 198 | -0.079% | -0.184% | +1.280% | -1.505% | +45.960% | +0.505% | +30.303% |
| 1D/N1/TRAIN/24h | 14 | 14 | -0.222% | -0.627% | +1.368% | -1.870% | +35.714% | +0.000% | +21.429% |
| 1D/N1/VALIDATION/24h | 2 | 2 | -1.310% | -1.310% | +1.598% | -2.562% | +50.000% | +0.000% | +50.000% |
| 1D/N1/TEST/24h | 9 | 9 | -0.081% | -0.424% | +1.070% | -1.821% | +55.556% | +0.000% | +33.333% |
| 1D/N2/TRAIN/24h | 23 | 23 | +0.301% | -0.222% | +1.745% | -1.616% | +47.826% | +0.000% | +21.739% |
| 1D/N2/VALIDATION/24h | 9 | 9 | -0.270% | +0.568% | +1.590% | -1.041% | +44.444% | +0.000% | +33.333% |
| 1D/N2/TEST/24h | 15 | 15 | +0.642% | +1.043% | +2.020% | -0.527% | +73.333% | +0.000% | +53.333% |
| 1D/N3/TRAIN/24h | 29 | 29 | -0.090% | -0.386% | +1.424% | -1.681% | +44.828% | +3.448% | +20.690% |
| 1D/N3/VALIDATION/24h | 15 | 15 | -0.370% | -0.273% | +1.590% | -1.123% | +46.667% | +0.000% | +40.000% |
| 1D/N3/TEST/24h | 22 | 22 | -0.002% | -0.257% | +1.720% | -1.472% | +68.182% | +0.000% | +50.000% |
| 1D/N5/TRAIN/24h | 32 | 32 | -0.046% | -0.313% | +1.368% | -1.902% | +43.750% | +3.125% | +21.875% |
| 1D/N5/VALIDATION/24h | 21 | 21 | -1.080% | -0.505% | +0.848% | -1.613% | +33.333% | +0.000% | +28.571% |
| 1D/N5/TEST/24h | 27 | 27 | -0.129% | -0.424% | +1.747% | -1.495% | +62.963% | +0.000% | +48.148% |

## Events by year, including2026 separately

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/2020/KONKORDE_ENTRY/24h | 589 | 589 | +0.394% | +0.320% | +1.683% | -1.459% | +48.217% | +2.716% | +39.219% |
| 1H/2020/KONKORDE_EXIT/24h | 589 | 589 | +0.377% | +0.400% | +1.641% | -1.565% | +48.048% | +1.868% | +39.049% |
| 1H/2020/DIRECTION_LONG/24h | 473 | 473 | +0.456% | +0.257% | +1.807% | -1.440% | +46.723% | +2.960% | +42.495% |
| 1H/2021/KONKORDE_ENTRY/24h | 568 | 566 | +0.263% | +0.102% | +2.504% | -2.562% | +48.057% | +3.710% | +46.290% |
| 1H/2021/KONKORDE_EXIT/24h | 569 | 567 | +0.198% | +0.207% | +2.675% | -2.604% | +43.915% | +5.115% | +47.795% |
| 1H/2021/DIRECTION_LONG/24h | 414 | 412 | +0.072% | -0.207% | +2.345% | -2.564% | +51.942% | +3.641% | +45.631% |
| 1H/2022/KONKORDE_ENTRY/24h | 602 | 602 | -0.281% | -0.216% | +1.595% | -1.904% | +46.678% | +2.658% | +34.884% |
| 1H/2022/KONKORDE_EXIT/24h | 602 | 602 | -0.390% | -0.151% | +1.557% | -1.861% | +43.522% | +1.827% | +33.721% |
| 1H/2022/DIRECTION_LONG/24h | 465 | 465 | -0.227% | -0.322% | +1.703% | -1.848% | +49.677% | +2.151% | +37.634% |
| 1H/2023/KONKORDE_ENTRY/24h | 623 | 621 | +0.274% | +0.039% | +1.175% | -1.016% | +46.860% | +0.966% | +31.401% |
| 1H/2023/KONKORDE_EXIT/24h | 623 | 620 | +0.265% | +0.113% | +1.194% | -1.079% | +45.000% | +0.968% | +28.226% |
| 1H/2023/DIRECTION_LONG/24h | 478 | 476 | +0.360% | -0.083% | +1.280% | -1.036% | +48.529% | +1.471% | +32.353% |
| 1H/2024/KONKORDE_ENTRY/24h | 574 | 574 | +0.317% | +0.123% | +1.611% | -1.374% | +48.606% | +0.348% | +39.024% |
| 1H/2024/KONKORDE_EXIT/24h | 574 | 574 | +0.209% | +0.135% | +1.537% | -1.460% | +46.341% | +1.045% | +35.017% |
| 1H/2024/DIRECTION_LONG/24h | 470 | 470 | +0.222% | -0.005% | +1.479% | -1.291% | +50.213% | +0.213% | +37.234% |
| 1H/2025/KONKORDE_ENTRY/24h | 583 | 583 | +0.022% | +0.011% | +1.189% | -1.130% | +46.141% | +0.343% | +27.101% |
| 1H/2025/KONKORDE_EXIT/24h | 583 | 583 | +0.031% | +0.130% | +1.176% | -1.175% | +44.597% | +0.343% | +25.557% |
| 1H/2025/DIRECTION_LONG/24h | 462 | 462 | -0.041% | -0.048% | +1.261% | -1.108% | +46.970% | +0.649% | +27.706% |
| 1H/2026/KONKORDE_ENTRY/24h | 476 | 473 | +0.128% | +0.151% | +1.148% | -1.188% | +42.918% | +0.423% | +24.736% |
| 1H/2026/KONKORDE_EXIT/24h | 475 | 473 | +0.104% | +0.103% | +1.158% | -1.154% | +43.975% | +0.423% | +24.736% |
| 1H/2026/DIRECTION_LONG/24h | 351 | 350 | +0.219% | +0.095% | +1.141% | -1.089% | +46.857% | +0.571% | +25.429% |
| 4H/2020/KONKORDE_ENTRY/24h | 152 | 152 | +0.485% | +0.343% | +1.526% | -1.471% | +49.342% | +3.289% | +35.526% |
| 4H/2020/KONKORDE_EXIT/24h | 152 | 152 | +0.344% | +0.504% | +1.577% | -1.857% | +47.368% | +1.316% | +31.579% |
| 4H/2020/DIRECTION_LONG/24h | 112 | 112 | +0.548% | +0.386% | +1.561% | -1.439% | +50.893% | +1.786% | +37.500% |
| 4H/2021/KONKORDE_ENTRY/24h | 137 | 137 | +0.187% | +0.027% | +2.488% | -2.704% | +44.526% | +6.569% | +43.066% |
| 4H/2021/KONKORDE_EXIT/24h | 136 | 136 | -0.197% | -0.771% | +2.422% | -2.890% | +41.176% | +4.412% | +41.176% |
| 4H/2021/DIRECTION_LONG/24h | 111 | 111 | +0.192% | +0.027% | +2.363% | -2.131% | +49.550% | +6.306% | +47.748% |
| 4H/2022/KONKORDE_ENTRY/24h | 152 | 152 | +0.110% | -0.096% | +1.904% | -1.766% | +51.316% | +3.289% | +38.158% |
| 4H/2022/KONKORDE_EXIT/24h | 152 | 152 | +0.185% | +0.148% | +1.939% | -1.692% | +49.342% | +1.316% | +40.132% |
| 4H/2022/DIRECTION_LONG/24h | 95 | 95 | -0.110% | -0.443% | +1.890% | -1.695% | +63.158% | +0.000% | +42.105% |
| 4H/2023/KONKORDE_ENTRY/24h | 153 | 153 | +0.323% | +0.008% | +1.286% | -1.036% | +45.098% | +2.614% | +32.026% |
| 4H/2023/KONKORDE_EXIT/24h | 153 | 153 | +0.410% | +0.202% | +1.235% | -1.048% | +47.712% | +3.268% | +33.333% |
| 4H/2023/DIRECTION_LONG/24h | 125 | 125 | +0.262% | -0.126% | +1.321% | -1.216% | +52.000% | +2.400% | +36.800% |
| 4H/2024/KONKORDE_ENTRY/24h | 147 | 147 | +0.076% | -0.105% | +1.385% | -1.421% | +50.340% | +0.000% | +30.612% |
| 4H/2024/KONKORDE_EXIT/24h | 147 | 147 | +0.238% | +0.334% | +1.494% | -1.450% | +42.857% | +0.680% | +27.891% |
| 4H/2024/DIRECTION_LONG/24h | 118 | 118 | +0.007% | -0.233% | +1.403% | -1.417% | +51.695% | +0.000% | +33.898% |
| 4H/2025/KONKORDE_ENTRY/24h | 137 | 137 | -0.373% | -0.461% | +1.021% | -1.491% | +41.606% | +0.730% | +25.547% |
| 4H/2025/KONKORDE_EXIT/24h | 138 | 138 | +0.100% | -0.007% | +1.313% | -1.190% | +42.754% | +0.725% | +28.261% |
| 4H/2025/DIRECTION_LONG/24h | 109 | 109 | -0.299% | -0.455% | +1.228% | -1.391% | +44.954% | +0.000% | +24.771% |
| 4H/2026/KONKORDE_ENTRY/24h | 107 | 107 | +0.143% | +0.052% | +1.332% | -1.139% | +48.598% | +1.869% | +26.168% |
| 4H/2026/KONKORDE_EXIT/24h | 107 | 107 | -0.137% | -0.322% | +1.118% | -1.506% | +44.860% | +0.935% | +28.972% |
| 4H/2026/DIRECTION_LONG/24h | 87 | 87 | +0.182% | +0.166% | +1.421% | -1.037% | +57.471% | +1.149% | +33.333% |
| 1D/2020/KONKORDE_ENTRY/24h | 29 | 29 | -0.170% | -0.386% | +1.246% | -1.670% | +37.931% | +3.448% | +24.138% |
| 1D/2020/KONKORDE_EXIT/24h | 29 | 29 | +0.583% | +0.615% | +1.790% | -1.800% | +48.276% | +0.000% | +31.034% |
| 1D/2020/DIRECTION_LONG/24h | 25 | 25 | +0.137% | -0.050% | +1.613% | -1.670% | +40.000% | +4.000% | +24.000% |
| 1D/2021/KONKORDE_ENTRY/24h | 25 | 25 | +0.874% | +0.022% | +2.392% | -2.195% | +48.000% | +0.000% | +36.000% |
| 1D/2021/KONKORDE_EXIT/24h | 26 | 26 | -0.293% | +0.257% | +3.093% | -3.568% | +34.615% | +3.846% | +42.308% |
| 1D/2021/DIRECTION_LONG/24h | 12 | 12 | +1.330% | +0.057% | +2.273% | -1.708% | +50.000% | +0.000% | +41.667% |
| 1D/2022/KONKORDE_ENTRY/24h | 22 | 22 | -1.559% | -0.864% | +0.959% | -2.776% | +27.273% | +0.000% | +22.727% |
| 1D/2022/KONKORDE_EXIT/24h | 22 | 22 | -0.305% | -0.319% | +1.180% | -1.491% | +45.455% | +0.000% | +31.818% |
| 1D/2022/DIRECTION_LONG/24h | 14 | 14 | +0.078% | -0.155% | +2.181% | -1.666% | +42.857% | +0.000% | +50.000% |
| 1D/2023/KONKORDE_ENTRY/24h | 22 | 22 | -0.342% | -0.342% | +0.796% | -1.237% | +40.909% | +0.000% | +36.364% |
| 1D/2023/KONKORDE_EXIT/24h | 22 | 22 | +0.666% | -0.097% | +1.173% | -1.465% | +40.909% | +0.000% | +40.909% |
| 1D/2023/DIRECTION_LONG/24h | 19 | 19 | +0.016% | -0.448% | +1.313% | -1.432% | +47.368% | +0.000% | +42.105% |
| 1D/2024/KONKORDE_ENTRY/24h | 23 | 23 | +0.783% | +0.194% | +1.763% | -1.122% | +65.217% | +0.000% | +43.478% |
| 1D/2024/KONKORDE_EXIT/24h | 23 | 23 | -0.518% | -0.185% | +1.462% | -1.385% | +52.174% | +0.000% | +43.478% |
| 1D/2024/DIRECTION_LONG/24h | 20 | 20 | +1.026% | +0.647% | +2.167% | -1.517% | +45.000% | +0.000% | +45.000% |
| 1D/2025/KONKORDE_ENTRY/24h | 25 | 25 | -0.380% | -0.177% | +1.217% | -0.957% | +56.000% | +0.000% | +36.000% |
| 1D/2025/KONKORDE_EXIT/24h | 24 | 24 | -0.882% | -0.546% | +1.043% | -1.725% | +45.833% | +0.000% | +29.167% |
| 1D/2025/DIRECTION_LONG/24h | 17 | 17 | -0.040% | -0.177% | +1.096% | -1.376% | +58.824% | +0.000% | +17.647% |
| 1D/2026/KONKORDE_ENTRY/24h | 16 | 16 | +0.538% | +0.371% | +1.783% | -0.668% | +75.000% | +0.000% | +43.750% |
| 1D/2026/KONKORDE_EXIT/24h | 17 | 17 | -0.257% | -0.129% | +1.006% | -1.613% | +47.059% | +0.000% | +11.765% |
| 1D/2026/DIRECTION_LONG/24h | 13 | 13 | +1.060% | +0.448% | +1.980% | -0.870% | +53.846% | +0.000% | +46.154% |

### REENTRY by year, mature24h n

| TF/year | N1 | N2 | N3 | N5 |
|---|---:|---:|---:|---:|
| 1H/2020 | 95 | 168 | 230 | 306 |
| 1H/2021 | 98 | 169 | 221 | 278 |
| 1H/2022 | 118 | 178 | 236 | 325 |
| 1H/2023 | 104 | 192 | 246 | 337 |
| 1H/2024 | 101 | 172 | 223 | 289 |
| 1H/2025 | 101 | 175 | 228 | 304 |
| 1H/2026 | 85 | 155 | 200 | 251 |
| 4H/2020 | 26 | 50 | 60 | 82 |
| 4H/2021 | 20 | 30 | 41 | 58 |
| 4H/2022 | 26 | 51 | 68 | 89 |
| 4H/2023 | 24 | 48 | 62 | 85 |
| 4H/2024 | 26 | 44 | 52 | 79 |
| 4H/2025 | 20 | 37 | 46 | 69 |
| 4H/2026 | 20 | 35 | 41 | 50 |
| 1D/2020 | 6 | 13 | 17 | 19 |
| 1D/2021 | 8 | 10 | 12 | 13 |
| 1D/2022 | 0 | 4 | 7 | 12 |
| 1D/2023 | 2 | 5 | 8 | 9 |
| 1D/2024 | 3 | 4 | 7 | 10 |
| 1D/2025 | 3 | 4 | 8 | 10 |
| 1D/2026 | 3 | 7 | 7 | 7 |

Full raw outcomes per annual subset: reentry_by_year.json. No window selected.

## Zero proximity and separation

Values are continuous and shown in the live renderer. LOW/MID/HIGH are TRAIN distribution tertiles, not objectively close-to-zero zones or thresholds for an entry. No profitable cutoff was searched. EXIT separation is unavailable outside the mountain. Exact TRAIN boundaries:
```json
{
  "1H": {
    "distance_to_zero": {
      "train_n": 1157,
      "tertiles": [
        38.79545720283757,
        66.49284935896264
      ]
    },
    "separation": {
      "train_n": 1157,
      "tertiles": [
        2.4922295781839594,
        6.5237017662345425
      ]
    }
  },
  "4H": {
    "distance_to_zero": {
      "train_n": 289,
      "tertiles": [
        35.67120854364111,
        71.61368467059741
      ]
    },
    "separation": {
      "train_n": 289,
      "tertiles": [
        2.768680344259593,
        7.0057029598661416
      ]
    }
  },
  "1D": {
    "distance_to_zero": {
      "train_n": 54,
      "tertiles": [
        41.389203151716146,
        74.36232657103281
      ]
    },
    "separation": {
      "train_n": 54,
      "tertiles": [
        2.268780285598727,
        5.962960151034128
      ]
    }
  }
}
```
Continuous association with raw24h return is descriptive Spearman, not causal or a trading gate. Ranges/medians/n/correlations are retained in continuous_associations.json.

### 1H/KONKORDE_ENTRY TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 533 | 533 | +0.154% | -0.049% | +1.202% | -1.148% | +48.218% | +0.188% | +27.955% |
| TEST/zero/LOW | 634 | 631 | +0.091% | +0.121% | +1.346% | -1.498% | +42.631% | +0.634% | +31.696% |
| TEST/zero/MID | 466 | 466 | +0.248% | +0.216% | +1.313% | -1.013% | +48.283% | +0.215% | +32.189% |
| TEST/separation/HIGH | 587 | 585 | +0.191% | +0.073% | +1.399% | -1.257% | +47.009% | +0.171% | +34.530% |
| TEST/separation/LOW | 515 | 515 | +0.254% | +0.162% | +1.250% | -1.154% | +45.825% | +0.000% | +30.680% |
| TEST/separation/MID | 531 | 530 | +0.023% | +0.041% | +1.196% | -1.239% | +45.283% | +0.943% | +26.226% |
| TEST/separation/UNAVAILABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
### 1H/KONKORDE_EXIT TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 914 | 914 | +0.076% | +0.061% | +1.250% | -1.207% | +46.389% | +0.438% | +27.899% |
| TEST/zero/LOW | 317 | 315 | +0.301% | +0.288% | +1.504% | -1.600% | +46.667% | +1.270% | +32.698% |
| TEST/zero/MID | 401 | 401 | +0.058% | +0.184% | +1.154% | -1.174% | +40.648% | +0.499% | +27.182% |
| TEST/separation/HIGH | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/LOW | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/MID | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/UNAVAILABLE | 1632 | 1630 | +0.115% | +0.126% | +1.255% | -1.252% | +45.031% | +0.613% | +28.650% |
### 4H/KONKORDE_ENTRY TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 115 | 115 | -0.144% | -0.381% | +1.220% | -1.521% | +43.478% | +0.000% | +28.696% |
| TEST/zero/LOW | 134 | 134 | -0.029% | -0.140% | +1.336% | -1.500% | +45.522% | +0.746% | +26.866% |
| TEST/zero/MID | 142 | 142 | -0.029% | +0.008% | +1.249% | -1.020% | +50.704% | +1.408% | +27.465% |
| TEST/separation/HIGH | 132 | 132 | -0.083% | -0.432% | +1.363% | -1.512% | +47.727% | +1.515% | +28.788% |
| TEST/separation/LOW | 121 | 121 | +0.020% | +0.004% | +1.244% | -1.189% | +46.281% | +0.000% | +27.273% |
| TEST/separation/MID | 138 | 138 | -0.117% | -0.257% | +1.201% | -1.509% | +46.377% | +0.725% | +26.812% |
| TEST/separation/UNAVAILABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
### 4H/KONKORDE_EXIT TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 206 | 206 | +0.205% | +0.022% | +1.286% | -1.277% | +44.175% | +0.485% | +27.184% |
| TEST/zero/LOW | 56 | 56 | -0.105% | -0.065% | +1.528% | -2.191% | +32.143% | +3.571% | +26.786% |
| TEST/zero/MID | 130 | 130 | -0.017% | -0.008% | +1.228% | -1.166% | +46.923% | +0.000% | +30.769% |
| TEST/separation/HIGH | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/LOW | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/MID | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/UNAVAILABLE | 392 | 392 | +0.087% | +0.006% | +1.315% | -1.329% | +43.367% | +0.765% | +28.316% |
### 1D/KONKORDE_ENTRY TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 19 | 19 | +0.959% | +0.784% | +1.887% | -0.908% | +78.947% | +0.000% | +47.368% |
| TEST/zero/LOW | 24 | 24 | -0.714% | -0.389% | +1.421% | -1.561% | +62.500% | +0.000% | +33.333% |
| TEST/zero/MID | 21 | 21 | +0.763% | +0.447% | +1.934% | -0.681% | +52.381% | +0.000% | +42.857% |
| TEST/separation/HIGH | 19 | 19 | +0.284% | +0.028% | +1.321% | -1.255% | +52.632% | +0.000% | +31.579% |
| TEST/separation/LOW | 25 | 25 | +0.235% | -0.045% | +1.887% | -0.987% | +76.000% | +0.000% | +44.000% |
| TEST/separation/MID | 20 | 20 | +0.292% | +0.241% | +1.679% | -0.745% | +60.000% | +0.000% | +45.000% |
| TEST/separation/UNAVAILABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
### 1D/KONKORDE_EXIT TEST proximity/separation

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/zero/HIGH | 36 | 36 | -0.476% | -0.157% | +1.034% | -1.265% | +41.667% | +0.000% | +27.778% |
| TEST/zero/LOW | 12 | 12 | -0.383% | -0.846% | +1.904% | -3.192% | +66.667% | +0.000% | +41.667% |
| TEST/zero/MID | 16 | 16 | -0.983% | -0.245% | +1.059% | -1.518% | +50.000% | +0.000% | +25.000% |
| TEST/separation/HIGH | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/LOW | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/MID | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| TEST/separation/UNAVAILABLE | 64 | 64 | -0.586% | -0.220% | +1.092% | -1.526% | +48.438% | +0.000% | +29.688% |

### Separation while MA stays inside

Every closed inside-state bar is a state observation, not a new signal. These samples overlap heavily and must not be treated as independent trials. No exit is generated by contraction.

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/TEST/LOW/24h | 1140 | 1139 | +0.236% | +0.177% | +1.300% | -1.154% | +47.234% | +0.351% | +30.202% |
| 1H/TEST/MID/24h | 1791 | 1789 | +0.070% | +0.070% | +1.222% | -1.254% | +45.333% | +0.615% | +27.781% |
| 1H/TEST/HIGH/24h | 9365 | 9356 | +0.032% | +0.043% | +1.269% | -1.257% | +46.109% | +0.566% | +30.269% |
| 4H/TEST/LOW/24h | 289 | 289 | +0.117% | +0.041% | +1.351% | -1.091% | +49.827% | +0.346% | +32.526% |
| 4H/TEST/MID/24h | 487 | 487 | +0.046% | +0.035% | +1.220% | -1.320% | +44.559% | +0.616% | +29.363% |
| 4H/TEST/HIGH/24h | 2305 | 2305 | +0.165% | +0.084% | +1.372% | -1.230% | +48.069% | +0.390% | +31.063% |
| 1D/TEST/LOW/24h | 53 | 53 | -0.149% | -0.245% | +1.441% | -1.193% | +60.377% | +1.887% | +32.075% |
| 1D/TEST/MID/24h | 72 | 72 | +0.002% | +0.039% | +1.359% | -1.268% | +45.833% | +0.000% | +30.556% |
| 1D/TEST/HIGH/24h | 397 | 397 | +0.191% | +0.056% | +1.315% | -1.235% | +44.584% | +0.504% | +29.471% |

### Inside separation expanding/contracting, TEST24h

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/EXPANDING | 5138 | 5136 | +0.021% | +0.039% | +1.265% | -1.270% | +45.639% | +0.701% | +30.179% |
| 1H/STABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| 1H/CONTRACTING | 5525 | 5518 | +0.059% | +0.079% | +1.267% | -1.231% | +46.539% | +0.471% | +29.431% |
| 1H/NEW_INSIDE | 1633 | 1630 | +0.157% | +0.083% | +1.279% | -1.235% | +46.074% | +0.368% | +30.613% |
| 4H/EXPANDING | 1296 | 1296 | +0.180% | +0.131% | +1.387% | -1.199% | +48.148% | +0.540% | +31.790% |
| 4H/STABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| 4H/CONTRACTING | 1394 | 1394 | +0.163% | +0.051% | +1.339% | -1.224% | +47.489% | +0.215% | +31.062% |
| 4H/NEW_INSIDE | 391 | 391 | -0.063% | -0.199% | +1.259% | -1.422% | +46.803% | +0.767% | +27.621% |
| 1D/EXPANDING | 221 | 221 | +0.175% | -0.052% | +1.354% | -1.193% | +47.059% | +0.452% | +29.864% |
| 1D/STABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
| 1D/CONTRACTING | 237 | 237 | +0.051% | +0.009% | +1.238% | -1.326% | +40.928% | +0.844% | +27.004% |
| 1D/NEW_INSIDE | 64 | 64 | +0.268% | +0.081% | +1.734% | -0.933% | +64.062% | +0.000% | +40.625% |

## ADX / DI / AO / BBWP observational ablation

ADX favorable=rising, no absolute threshold. DI/AO alignment uses positive for ENTRY and negative for the EXIT downside hypothesis, without placing a SHORT. BBWP expanding=slope>0. These are marginal conditional distributions, NOT controlled causal effects or a new entry strategy. All TRAIN/VALIDATION tables and every horizon remain in results.json; the TEST24h display below cannot select new gates.

### 1H/KONKORDE_ENTRY

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 896 | 894 | +0.237% | +0.139% | +1.266% | -1.180% | +46.085% | +0.336% | +31.320% |
| TEST/adx/RISING | 737 | 736 | +0.059% | -0.007% | +1.297% | -1.294% | +46.060% | +0.408% | +29.755% |
| TEST/di/ALIGNED | 780 | 780 | +0.241% | +0.015% | +1.317% | -1.111% | +49.615% | +0.128% | +30.897% |
| TEST/di/NON_ALIGNED | 853 | 850 | +0.079% | +0.124% | +1.227% | -1.355% | +42.824% | +0.588% | +30.353% |
| TEST/ao/ALIGNED | 641 | 641 | +0.170% | +0.028% | +1.222% | -1.084% | +48.674% | +0.156% | +28.237% |
| TEST/ao/NON_ALIGNED | 992 | 989 | +0.148% | +0.120% | +1.319% | -1.302% | +44.388% | +0.506% | +32.154% |
| TEST/bbwp/EXPANDING | 886 | 885 | +0.256% | +0.094% | +1.284% | -1.188% | +46.780% | +0.113% | +30.621% |
| TEST/bbwp/NON_EXPANDING | 747 | 745 | +0.038% | +0.069% | +1.268% | -1.295% | +45.235% | +0.671% | +30.604% |
### 1H/KONKORDE_EXIT

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 908 | 908 | +0.248% | +0.157% | +1.274% | -1.169% | +46.256% | +0.551% | +28.524% |
| TEST/adx/RISING | 724 | 722 | -0.053% | +0.072% | +1.243% | -1.370% | +43.490% | +0.693% | +28.809% |
| TEST/di/ALIGNED | 820 | 818 | +0.149% | +0.184% | +1.291% | -1.363% | +43.032% | +0.733% | +29.951% |
| TEST/di/NON_ALIGNED | 812 | 812 | +0.080% | +0.081% | +1.235% | -1.204% | +47.044% | +0.493% | +27.340% |
| TEST/ao/ALIGNED | 552 | 550 | +0.187% | +0.234% | +1.283% | -1.523% | +42.909% | +0.909% | +31.091% |
| TEST/ao/NON_ALIGNED | 1080 | 1080 | +0.078% | +0.098% | +1.243% | -1.177% | +46.111% | +0.463% | +27.407% |
| TEST/bbwp/EXPANDING | 796 | 796 | +0.080% | +0.129% | +1.235% | -1.361% | +44.472% | +0.628% | +27.513% |
| TEST/bbwp/NON_EXPANDING | 836 | 834 | +0.148% | +0.125% | +1.280% | -1.190% | +45.564% | +0.600% | +29.736% |
### 4H/KONKORDE_ENTRY

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 226 | 226 | -0.067% | -0.132% | +1.294% | -1.440% | +46.018% | +0.885% | +27.434% |
| TEST/adx/RISING | 165 | 165 | -0.057% | -0.261% | +1.220% | -1.421% | +47.879% | +0.606% | +27.879% |
| TEST/di/ALIGNED | 194 | 194 | -0.107% | -0.316% | +1.313% | -1.474% | +49.485% | +0.515% | +29.381% |
| TEST/di/NON_ALIGNED | 197 | 197 | -0.020% | +0.012% | +1.207% | -1.371% | +44.162% | +1.015% | +25.888% |
| TEST/ao/ALIGNED | 163 | 163 | -0.051% | -0.288% | +1.220% | -1.481% | +46.012% | +0.613% | +28.834% |
| TEST/ao/NON_ALIGNED | 228 | 228 | -0.072% | -0.016% | +1.268% | -1.375% | +47.368% | +0.877% | +26.754% |
| TEST/bbwp/EXPANDING | 201 | 201 | -0.061% | -0.261% | +1.345% | -1.391% | +48.259% | +0.498% | +29.851% |
| TEST/bbwp/NON_EXPANDING | 190 | 190 | -0.065% | -0.081% | +1.232% | -1.498% | +45.263% | +1.053% | +25.263% |
### 4H/KONKORDE_EXIT

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 227 | 227 | +0.149% | +0.001% | +1.308% | -1.264% | +44.934% | +0.441% | +29.515% |
| TEST/adx/RISING | 165 | 165 | +0.002% | +0.017% | +1.333% | -1.487% | +41.212% | +1.212% | +26.667% |
| TEST/di/ALIGNED | 199 | 199 | +0.103% | +0.079% | +1.484% | -1.562% | +44.724% | +1.005% | +32.161% |
| TEST/di/NON_ALIGNED | 193 | 193 | +0.071% | -0.016% | +1.114% | -1.265% | +41.969% | +0.518% | +24.352% |
| TEST/ao/ALIGNED | 122 | 122 | -0.102% | +0.056% | +1.489% | -1.662% | +43.443% | +1.639% | +31.967% |
| TEST/ao/NON_ALIGNED | 270 | 270 | +0.173% | +0.002% | +1.206% | -1.277% | +43.333% | +0.370% | +26.667% |
| TEST/bbwp/EXPANDING | 193 | 193 | +0.144% | +0.079% | +1.419% | -1.435% | +44.041% | +1.036% | +31.606% |
| TEST/bbwp/NON_EXPANDING | 199 | 199 | +0.032% | +0.001% | +1.155% | -1.288% | +42.714% | +0.503% | +25.126% |
### 1D/KONKORDE_ENTRY

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 41 | 41 | -0.298% | -0.091% | +1.321% | -0.987% | +60.976% | +0.000% | +34.146% |
| TEST/adx/RISING | 23 | 23 | +1.276% | +1.043% | +2.137% | -0.681% | +69.565% | +0.000% | +52.174% |
| TEST/di/ALIGNED | 25 | 25 | +1.235% | +1.390% | +2.020% | -0.714% | +72.000% | +0.000% | +52.000% |
| TEST/di/NON_ALIGNED | 39 | 39 | -0.353% | -0.091% | +1.419% | -1.117% | +58.974% | +0.000% | +33.333% |
| TEST/ao/ALIGNED | 23 | 23 | +1.046% | +1.390% | +2.020% | -0.833% | +78.261% | +0.000% | +52.174% |
| TEST/ao/NON_ALIGNED | 41 | 41 | -0.169% | -0.080% | +1.419% | -1.117% | +56.098% | +0.000% | +34.146% |
| TEST/bbwp/EXPANDING | 28 | 28 | +0.695% | +0.244% | +1.534% | -0.811% | +60.714% | +0.000% | +32.143% |
| TEST/bbwp/NON_EXPANDING | 36 | 36 | -0.065% | -0.085% | +1.806% | -1.188% | +66.667% | +0.000% | +47.222% |
| TEST/bbwp/UNAVAILABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |
### 1D/KONKORDE_EXIT

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TEST/adx/NON_RISING | 37 | 37 | -0.344% | +0.188% | +1.462% | -1.052% | +54.054% | +0.000% | +43.243% |
| TEST/adx/RISING | 27 | 27 | -0.917% | -0.727% | +1.038% | -2.171% | +40.741% | +0.000% | +11.111% |
| TEST/di/ALIGNED | 34 | 34 | -0.596% | -0.607% | +1.191% | -1.796% | +52.941% | +0.000% | +32.353% |
| TEST/di/NON_ALIGNED | 30 | 30 | -0.574% | -0.012% | +1.054% | -1.265% | +43.333% | +0.000% | +26.667% |
| TEST/ao/ALIGNED | 21 | 21 | -0.891% | -0.920% | +1.610% | -2.943% | +52.381% | +0.000% | +33.333% |
| TEST/ao/NON_ALIGNED | 43 | 43 | -0.436% | -0.185% | +1.072% | -1.226% | +46.512% | +0.000% | +27.907% |
| TEST/bbwp/EXPANDING | 30 | 30 | -0.738% | -0.279% | +1.315% | -1.682% | +63.333% | +0.000% | +40.000% |
| TEST/bbwp/NON_EXPANDING | 34 | 34 | -0.451% | -0.115% | +1.000% | -1.372% | +35.294% | +0.000% | +20.588% |
| TEST/bbwp/UNAVAILABLE | 0 | 0 | NA | NA | NA | NA | NA | NA | NA |

###2026 conditional distributions, separate diagnostic

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/KONKORDE_ENTRY/zero/HIGH | 137 | 137 | +0.273% | +0.151% | +1.205% | -0.932% | +51.095% | +0.000% | +21.168% |
| 1H/KONKORDE_ENTRY/zero/LOW | 187 | 184 | +0.069% | +0.129% | +1.196% | -1.388% | +39.674% | +1.087% | +28.261% |
| 1H/KONKORDE_ENTRY/zero/MID | 152 | 152 | +0.069% | +0.161% | +0.933% | -0.998% | +39.474% | +0.000% | +23.684% |
| 1H/KONKORDE_ENTRY/separation/HIGH | 170 | 168 | +0.103% | +0.127% | +1.143% | -1.264% | +39.881% | +0.000% | +27.976% |
| 1H/KONKORDE_ENTRY/separation/LOW | 153 | 153 | +0.155% | +0.018% | +1.071% | -1.016% | +42.484% | +0.000% | +23.529% |
| 1H/KONKORDE_ENTRY/separation/MID | 153 | 152 | +0.129% | +0.240% | +1.268% | -1.181% | +46.711% | +1.316% | +22.368% |
| 1H/KONKORDE_ENTRY/adx/NON_RISING | 272 | 270 | +0.150% | +0.157% | +1.018% | -1.157% | +40.370% | +0.000% | +23.704% |
| 1H/KONKORDE_ENTRY/adx/RISING | 204 | 203 | +0.099% | +0.142% | +1.285% | -1.241% | +46.305% | +0.985% | +26.108% |
| 1H/KONKORDE_ENTRY/di/ALIGNED | 221 | 221 | +0.302% | +0.179% | +1.216% | -1.007% | +48.416% | +0.000% | +25.792% |
| 1H/KONKORDE_ENTRY/di/NON_ALIGNED | 255 | 252 | -0.024% | +0.116% | +1.099% | -1.289% | +38.095% | +0.794% | +23.810% |
| 1H/KONKORDE_ENTRY/ao/ALIGNED | 170 | 170 | +0.216% | +0.304% | +1.159% | -0.872% | +49.412% | +0.000% | +21.176% |
| 1H/KONKORDE_ENTRY/ao/NON_ALIGNED | 306 | 303 | +0.079% | +0.116% | +1.146% | -1.296% | +39.274% | +0.660% | +26.733% |
| 1H/KONKORDE_ENTRY/bbwp/EXPANDING | 266 | 265 | +0.154% | +0.138% | +1.157% | -1.185% | +44.151% | +0.000% | +21.509% |
| 1H/KONKORDE_ENTRY/bbwp/NON_EXPANDING | 210 | 208 | +0.095% | +0.156% | +1.147% | -1.211% | +41.346% | +0.962% | +28.846% |
| 1H/KONKORDE_EXIT/zero/HIGH | 238 | 238 | +0.037% | +0.022% | +1.216% | -1.161% | +46.639% | +0.420% | +23.109% |
| 1H/KONKORDE_EXIT/zero/LOW | 105 | 103 | +0.295% | +0.452% | +1.256% | -1.473% | +45.631% | +0.000% | +30.097% |
| 1H/KONKORDE_EXIT/zero/MID | 132 | 132 | +0.075% | +0.143% | +1.054% | -1.020% | +37.879% | +0.758% | +23.485% |
| 1H/KONKORDE_EXIT/separation/UNAVAILABLE | 475 | 473 | +0.104% | +0.103% | +1.158% | -1.154% | +43.975% | +0.423% | +24.736% |
| 1H/KONKORDE_EXIT/adx/NON_RISING | 269 | 269 | +0.276% | +0.110% | +1.255% | -1.132% | +46.840% | +0.743% | +25.651% |
| 1H/KONKORDE_EXIT/adx/RISING | 206 | 204 | -0.124% | +0.089% | +1.064% | -1.229% | +40.196% | +0.000% | +23.529% |
| 1H/KONKORDE_EXIT/di/ALIGNED | 251 | 249 | +0.068% | +0.110% | +1.113% | -1.173% | +41.365% | +0.000% | +25.301% |
| 1H/KONKORDE_EXIT/di/NON_ALIGNED | 224 | 224 | +0.144% | +0.088% | +1.245% | -1.153% | +46.875% | +0.893% | +24.107% |
| 1H/KONKORDE_EXIT/ao/ALIGNED | 187 | 185 | +0.124% | +0.184% | +1.127% | -1.344% | +41.081% | +0.541% | +27.568% |
| 1H/KONKORDE_EXIT/ao/NON_ALIGNED | 288 | 288 | +0.090% | +0.082% | +1.197% | -1.057% | +45.833% | +0.347% | +22.917% |
| 1H/KONKORDE_EXIT/bbwp/EXPANDING | 241 | 241 | +0.032% | +0.051% | +1.174% | -1.265% | +45.228% | +0.000% | +24.481% |
| 1H/KONKORDE_EXIT/bbwp/NON_EXPANDING | 234 | 232 | +0.178% | +0.166% | +1.156% | -1.020% | +42.672% | +0.862% | +25.000% |
| 4H/KONKORDE_ENTRY/zero/HIGH | 31 | 31 | +0.363% | +0.253% | +1.528% | -1.441% | +48.387% | +0.000% | +38.710% |
| 4H/KONKORDE_ENTRY/zero/LOW | 42 | 42 | +0.115% | -0.247% | +1.019% | -1.363% | +42.857% | +2.381% | +16.667% |
| 4H/KONKORDE_ENTRY/zero/MID | 34 | 34 | -0.024% | +0.023% | +1.336% | -0.823% | +55.882% | +2.941% | +26.471% |
| 4H/KONKORDE_ENTRY/separation/HIGH | 47 | 47 | +0.182% | -0.315% | +1.266% | -1.494% | +44.681% | +4.255% | +23.404% |
| 4H/KONKORDE_ENTRY/separation/LOW | 29 | 29 | +0.248% | +0.035% | +1.096% | -0.988% | +44.828% | +0.000% | +24.138% |
| 4H/KONKORDE_ENTRY/separation/MID | 31 | 31 | -0.014% | +0.327% | +1.336% | -0.968% | +58.065% | +0.000% | +32.258% |
| 4H/KONKORDE_ENTRY/adx/NON_RISING | 55 | 55 | -0.022% | -0.233% | +1.332% | -1.294% | +50.909% | +1.818% | +23.636% |
| 4H/KONKORDE_ENTRY/adx/RISING | 52 | 52 | +0.317% | +0.114% | +1.216% | -1.072% | +46.154% | +1.923% | +28.846% |
| 4H/KONKORDE_ENTRY/di/ALIGNED | 53 | 53 | +0.186% | +0.134% | +1.383% | -1.088% | +54.717% | +1.887% | +33.962% |
| 4H/KONKORDE_ENTRY/di/NON_ALIGNED | 54 | 54 | +0.101% | -0.135% | +1.019% | -1.217% | +42.593% | +1.852% | +18.519% |
| 4H/KONKORDE_ENTRY/ao/ALIGNED | 40 | 40 | +0.138% | +0.209% | +1.519% | -1.481% | +50.000% | +0.000% | +32.500% |
| 4H/KONKORDE_ENTRY/ao/NON_ALIGNED | 67 | 67 | +0.146% | -0.006% | +1.129% | -1.088% | +47.761% | +2.985% | +22.388% |
| 4H/KONKORDE_ENTRY/bbwp/EXPANDING | 61 | 61 | +0.132% | +0.134% | +1.470% | -1.093% | +50.820% | +1.639% | +32.787% |
| 4H/KONKORDE_ENTRY/bbwp/NON_EXPANDING | 46 | 46 | +0.157% | -0.135% | +1.132% | -1.408% | +45.652% | +2.174% | +17.391% |
| 4H/KONKORDE_EXIT/zero/HIGH | 56 | 56 | +0.173% | -0.048% | +1.164% | -1.335% | +46.429% | +0.000% | +26.786% |
| 4H/KONKORDE_EXIT/zero/LOW | 18 | 18 | -0.462% | +0.100% | +1.584% | -2.046% | +44.444% | +5.556% | +27.778% |
| 4H/KONKORDE_EXIT/zero/MID | 33 | 33 | -0.486% | -0.806% | +0.698% | -1.916% | +42.424% | +0.000% | +33.333% |
| 4H/KONKORDE_EXIT/separation/UNAVAILABLE | 107 | 107 | -0.137% | -0.322% | +1.118% | -1.506% | +44.860% | +0.935% | +28.972% |
| 4H/KONKORDE_EXIT/adx/NON_RISING | 58 | 58 | +0.074% | -0.255% | +0.993% | -1.359% | +46.552% | +0.000% | +31.034% |
| 4H/KONKORDE_EXIT/adx/RISING | 49 | 49 | -0.387% | -0.371% | +1.263% | -1.890% | +42.857% | +2.041% | +26.531% |
| 4H/KONKORDE_EXIT/di/ALIGNED | 51 | 51 | -0.381% | -0.322% | +1.257% | -1.995% | +43.137% | +1.961% | +31.373% |
| 4H/KONKORDE_EXIT/di/NON_ALIGNED | 56 | 56 | +0.085% | -0.279% | +1.116% | -1.322% | +46.429% | +0.000% | +26.786% |
| 4H/KONKORDE_EXIT/ao/ALIGNED | 33 | 33 | -0.240% | +0.257% | +1.675% | -1.346% | +48.485% | +3.030% | +36.364% |
| 4H/KONKORDE_EXIT/ao/NON_ALIGNED | 74 | 74 | -0.091% | -0.392% | +1.025% | -1.530% | +43.243% | +0.000% | +25.676% |
| 4H/KONKORDE_EXIT/bbwp/EXPANDING | 58 | 58 | -0.107% | -0.187% | +1.187% | -1.495% | +43.103% | +1.724% | +34.483% |
| 4H/KONKORDE_EXIT/bbwp/NON_EXPANDING | 49 | 49 | -0.173% | -0.371% | +1.039% | -1.515% | +46.939% | +0.000% | +22.449% |
| 1D/KONKORDE_ENTRY/zero/HIGH | 6 | 6 | +0.739% | +1.575% | +2.143% | -0.519% | +83.333% | +0.000% | +66.667% |
| 1D/KONKORDE_ENTRY/zero/LOW | 5 | 5 | +0.401% | -0.080% | +1.632% | -1.255% | +80.000% | +0.000% | +40.000% |
| 1D/KONKORDE_ENTRY/zero/MID | 5 | 5 | +0.434% | +0.294% | +1.324% | -0.809% | +60.000% | +0.000% | +20.000% |
| 1D/KONKORDE_ENTRY/separation/HIGH | 4 | 4 | +0.323% | +0.184% | +1.323% | -0.880% | +75.000% | +0.000% | +25.000% |
| 1D/KONKORDE_ENTRY/separation/LOW | 7 | 7 | +0.596% | +1.499% | +2.020% | -0.527% | +85.714% | +0.000% | +57.143% |
| 1D/KONKORDE_ENTRY/separation/MID | 5 | 5 | +0.629% | +0.294% | +1.632% | -0.809% | +60.000% | +0.000% | +40.000% |
| 1D/KONKORDE_ENTRY/adx/NON_RISING | 8 | 8 | +0.078% | +0.017% | +1.628% | -0.811% | +62.500% | +0.000% | +37.500% |
| 1D/KONKORDE_ENTRY/adx/RISING | 8 | 8 | +0.998% | +0.932% | +1.948% | -0.509% | +87.500% | +0.000% | +50.000% |
| 1D/KONKORDE_ENTRY/di/ALIGNED | 7 | 7 | +0.697% | +1.499% | +2.020% | -0.510% | +85.714% | +0.000% | +57.143% |
| 1D/KONKORDE_ENTRY/di/NON_ALIGNED | 9 | 9 | +0.414% | -0.080% | +1.632% | -0.814% | +66.667% | +0.000% | +33.333% |
| 1D/KONKORDE_ENTRY/ao/ALIGNED | 8 | 8 | +0.886% | +1.575% | +2.143% | -0.509% | +87.500% | +0.000% | +62.500% |
| 1D/KONKORDE_ENTRY/ao/NON_ALIGNED | 8 | 8 | +0.190% | -0.166% | +1.476% | -0.965% | +62.500% | +0.000% | +25.000% |
| 1D/KONKORDE_ENTRY/bbwp/EXPANDING | 8 | 8 | -0.142% | +0.017% | +1.323% | -0.811% | +62.500% | +0.000% | +25.000% |
| 1D/KONKORDE_ENTRY/bbwp/NON_EXPANDING | 8 | 8 | +1.217% | +1.533% | +2.394% | -0.509% | +87.500% | +0.000% | +62.500% |
| 1D/KONKORDE_EXIT/zero/HIGH | 12 | 12 | -0.525% | +0.033% | +0.691% | -1.248% | +41.667% | +0.000% | +8.333% |
| 1D/KONKORDE_EXIT/zero/LOW | 3 | 3 | -0.543% | -0.920% | +1.610% | -2.943% | +33.333% | +0.000% | +0.000% |
| 1D/KONKORDE_EXIT/zero/MID | 2 | 2 | +1.773% | +1.773% | +3.393% | -0.352% | +100.000% | +0.000% | +50.000% |
| 1D/KONKORDE_EXIT/separation/UNAVAILABLE | 17 | 17 | -0.257% | -0.129% | +1.006% | -1.613% | +47.059% | +0.000% | +11.765% |
| 1D/KONKORDE_EXIT/adx/NON_RISING | 6 | 6 | +0.082% | +0.271% | +0.913% | -0.826% | +50.000% | +0.000% | +33.333% |
| 1D/KONKORDE_EXIT/adx/RISING | 11 | 11 | -0.443% | -0.185% | +1.006% | -2.171% | +45.455% | +0.000% | +0.000% |
| 1D/KONKORDE_EXIT/di/ALIGNED | 7 | 7 | -0.180% | -0.185% | +1.381% | -2.483% | +42.857% | +0.000% | +14.286% |
| 1D/KONKORDE_EXIT/di/NON_ALIGNED | 10 | 10 | -0.312% | +0.033% | +0.936% | -1.248% | +50.000% | +0.000% | +10.000% |
| 1D/KONKORDE_EXIT/ao/ALIGNED | 3 | 3 | -0.543% | -0.920% | +1.610% | -2.943% | +33.333% | +0.000% | +0.000% |
| 1D/KONKORDE_EXIT/ao/NON_ALIGNED | 14 | 14 | -0.196% | +0.033% | +0.936% | -0.826% | +50.000% | +0.000% | +14.286% |
| 1D/KONKORDE_EXIT/bbwp/EXPANDING | 8 | 8 | -0.541% | -0.157% | +0.936% | -1.892% | +37.500% | +0.000% | +12.500% |
| 1D/KONKORDE_EXIT/bbwp/NON_EXPANDING | 9 | 9 | -0.005% | +0.196% | +1.108% | -0.883% | +55.556% | +0.000% | +11.111% |

## Descriptive LONG episodes

LONG is a display state, independent of technical ENTRY/REENTRY events. One transition into LONG is one observation; it is not repeated each bar. No SHORT episode is implemented. AO/ADX/BBWP remain context rather than mandatory gates. These raw outcomes do not validate an entry permission.

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1H/TRAIN/24h | 887 | 885 | +0.277% | +0.087% | +2.004% | -1.887% | +49.153% | +3.277% | +43.955% |
| 1H/VALIDATION/24h | 943 | 941 | +0.070% | -0.140% | +1.529% | -1.340% | +49.097% | +1.807% | +34.963% |
| 1H/TEST/24h | 1283 | 1282 | +0.126% | -0.021% | +1.275% | -1.186% | +48.128% | +0.468% | +30.577% |
| 4H/TRAIN/24h | 223 | 223 | +0.371% | +0.167% | +1.995% | -1.880% | +50.224% | +4.036% | +42.601% |
| 4H/VALIDATION/24h | 220 | 220 | +0.101% | -0.179% | +1.563% | -1.367% | +56.818% | +1.364% | +39.091% |
| 4H/TEST/24h | 314 | 314 | -0.051% | -0.147% | +1.346% | -1.302% | +50.955% | +0.318% | +30.573% |
| 1D/TRAIN/24h | 37 | 37 | +0.524% | +0.022% | +1.651% | -1.670% | +43.243% | +2.703% | +29.730% |
| 1D/VALIDATION/24h | 33 | 33 | +0.042% | -0.366% | +1.909% | -1.580% | +45.455% | +0.000% | +45.455% |
| 1D/TEST/24h | 50 | 50 | +0.672% | +0.362% | +1.673% | -1.381% | +52.000% | +0.000% | +36.000% |

## Comparison with V8 — retain existing evidence

No replacement is proposed. The archived common-data/cutoff funded V8 TEST remains +66.55%, Sharpe0.732, MaxDD−32.01%. That is a specified net strategy comparator in Phase2, not a return claim for this observer. Its original mechanical strategy is unchanged.
A fresh descriptive event table uses transitions of LAST CLOSED4H close>SMA200, with the same public hourly future measurements. Its gross event returns are not net strategy PnL and are not directly ranked against funded returns.

| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V8_LONG_SIGNAL/TRAIN/24h | 65 | 65 | -0.938% | -0.765% | +1.302% | -2.085% | +33.846% | +3.077% | +23.077% |
| V8_LONG_SIGNAL/VALIDATION/24h | 63 | 63 | +0.134% | -0.176% | +1.142% | -1.373% | +49.206% | +0.000% | +26.984% |
| V8_LONG_SIGNAL/TEST/24h | 83 | 83 | +0.167% | +0.277% | +1.347% | -1.072% | +54.217% | +1.205% | +27.711% |
| V8_FLAT_SIGNAL/TRAIN/24h | 65 | 65 | +0.058% | +0.235% | +1.805% | -1.995% | +52.308% | +9.231% | +38.462% |
| V8_FLAT_SIGNAL/VALIDATION/24h | 62 | 62 | -0.422% | +0.035% | +0.878% | -1.065% | +35.484% | +1.613% | +17.742% |
| V8_FLAT_SIGNAL/TEST/24h | 84 | 84 | +0.034% | +0.179% | +1.339% | -1.413% | +44.048% | +0.000% | +27.381% |

## Legacy signal audit

See [LEGACY_SIGNAL_AUDIT.md](LEGACY_SIGNAL_AUDIT.md): Guardian KEEP_ACTIVE, V8 KEEP_ACTIVE in its existing configured state, Copilot KEEP_AS_CONTEXT, unproven ML RSI RESEARCH_ONLY, negative studies ARCHIVE; selected noisy alerts DISABLE_ALERTS is a proposal only. No cleanup, deletion, service disablement, variable change or production Telegram alteration performed.

## Classification and limitations

**INCONCLUSIVE** under the predeclared matched-control/sample/yearly gates. A positive raw move in a bull market, a favorable secondary cohort or a tiny daily sample is insufficient. No robust cross-timeframe incremental edge is established. No exact-private-parity or forward validation claim. Do not reinterpret this conclusion as the private Bitman indicator being disproven: this is the documented proxy only.
Actual forward journals remain inaccessible. Future telemetry is separated by source/version and can motivate another preregistration; it cannot overwrite frozen results here.

## Telegram examples — ILLUSTRATIVE ONLY, not sent

### LONG_ENTRY
```text
🟢 LONG
🟢📊 BITMAN KONKORDE ENTRY

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: ENTERED MOUNTAIN ✅
Montaña: 12.0000 · EMA15: 10.0000
Distance to zero (EMA): 10.0000
Reentry: NO · ventana explícita: 3 velas
Mountain/MA separation: 2.0000
Strength: NEW_INSIDE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 30.0000 · -DI: 14.0000
DI direction: BULL
Slope: 0.6000

⚡ AO — CONTEXTO
Value: 450.0000
State: POSITIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Media dentro de montaña positiva
+DI supera -DI
Contexto observacional; NO permiso de entrada
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### EXIT
```text
⚪ WAIT
🔴📊 BITMAN KONKORDE EXIT

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: LEFT MOUNTAIN
Montaña: 12.0000 · EMA15: 13.0000
Distance to zero (EMA): 13.0000
Reentry: NO · ventana explícita: 3 velas
Mountain/MA separation: UNAVAILABLE
Strength: UNAVAILABLE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 30.0000 · -DI: 14.0000
DI direction: BULL
Slope: 0.6000

⚡ AO — CONTEXTO
Value: 450.0000
State: POSITIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Media fuera de la montaña
EXIT no equivale a señal SHORT
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### REENTRY
```text
🟢 LONG
🟡🔁 BITMAN KONKORDE REENTRY

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: ENTERED MOUNTAIN ✅
Montaña: 12.0000 · EMA15: 10.0000
Distance to zero (EMA): 10.0000
Reentry: YES · ventana explícita: 3 velas
Mountain/MA separation: 2.0000
Strength: NEW_INSIDE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 30.0000 · -DI: 14.0000
DI direction: BULL
Slope: 0.6000

⚡ AO — CONTEXTO
Value: 450.0000
State: POSITIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Media dentro de montaña positiva
+DI supera -DI
Contexto observacional; NO permiso de entrada
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### SETUP_FORMING
```text
🟡 SETUP FORMING
⚪ BITMAN WAIT

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: INSIDE MOUNTAIN
Montaña: 12.0000 · EMA15: 10.0000
Distance to zero (EMA): 10.0000
Reentry: NO · ventana explícita: 3 velas
Mountain/MA separation: 2.0000
Strength: NEW_INSIDE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 10.0000 · -DI: 20.0000
DI direction: BEAR
Slope: 0.6000

⚡ AO — CONTEXTO
Value: 450.0000
State: POSITIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Media dentro de montaña positiva
Falta alineación de DI
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### WAIT
```text
⚪ WAIT
⚪ BITMAN WAIT

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: OUTSIDE MOUNTAIN
Montaña: 12.0000 · EMA15: 13.0000
Distance to zero (EMA): 13.0000
Reentry: NO · ventana explícita: 3 velas
Mountain/MA separation: UNAVAILABLE
Strength: UNAVAILABLE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 30.0000 · -DI: 14.0000
DI direction: BULL
Slope: 0.6000

⚡ AO — CONTEXTO
Value: 450.0000
State: POSITIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Sin contexto LONG completo
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### BLOCKED_SHORT
```text
🛑 BLOCKED
⚪ BITMAN WAIT

₿ BTCUSDT · 4H
📡 BINANCE USD-M PERPETUAL · KONKORDE_PROXY
Cierre: 2026-10-15 16:00 UTC
Precio: 82,150.0000

📦 KONKORDE
Media: INSIDE MOUNTAIN
Montaña: -12.0000 · EMA15: -10.0000
Distance to zero (EMA): 10.0000
Reentry: NO · ventana explícita: 3 velas
Mountain/MA separation: 2.0000
Strength: NEW_INSIDE

💪 ADX / DI — CONTEXTO
ADX14: 28.4000
+DI: 10.0000 · -DI: 20.0000
DI direction: BEAR
Slope: 0.6000

⚡ AO — CONTEXTO
Value: -450.0000
State: NEGATIVE
Slope: 35.0000 (RISING)

🌡️ BBWP · CLOSE/SMA7/100
Value: 42.0000%
State: EXPANDING
Slope: 7.0000 · sin zonas optimizadas

🧭 Trend Speed
NOT IMPLEMENTED / FORMULA NOT VERIFIED

👀 RAZONES
Contexto bajista observado
SHORT_LOGIC_NOT_PROVEN
SHORT_LOGIC_NOT_PROVEN
LONG/SHORT aquí describen contexto; NO permiso de entrada.
EXIT no abre SHORT ni cierra ninguna posición.

EXACT BITMAN KONKORDE PARITY: NOT PROVEN
✅ CLOSED CANDLES ONLY
👻 MODE: SHADOW ONLY
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

## Tests / safety

Exact final counts and commands: artifacts/validation.json. No network in this observer or tests; read-only input files, pure renderer, separate storage, no account client or Telegram poller. Production file identity and pinned-source fingerprints: artifacts/safety_audit.json.
V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED. MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.
**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS.**

Dedicated: 68 passed; full repository: 447 passed; failed: 0; skipped: 0. Guardian: 311; V8: 16; Early Breakout: 52. Replay: BYTE_IDENTICAL; compile/safety: PASS.
