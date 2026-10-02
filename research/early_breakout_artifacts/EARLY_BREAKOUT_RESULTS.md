# I-GOD EARLY BREAKOUT SHADOW

**NO EDGE**

Public event research, not a traded strategy. No entry permission, private account API, execution or Guardian risk dependency.

Selected: `p0.2_n2_v1.5_h1_a1`. Nine initial one-factor candidates; neighbors frozen before TEST, 14 total evaluations.
BTCUSDT spot: 753,855 closed 5m rows, 251,281 complete 15m rows; 18 historical gaps. As of 2026-10-02T16:05:00+00:00.

| Period | Squeezes | Developing | +1% before -1%, 24h | +2% before -1%, 24h | False breakout | Hold | Matched lead median |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 3155 | 838 | 47.4% (n=820) | 30.1% | 48.1% | 80.0% | 1417.5 min (matches=2) |
| VALIDATION | 3095 | 795 | 42.6% (n=791) | 22.8% | 55.1% | 74.8% | 1140.0 min (matches=85) |
| TEST | 4429 | 891 | 44.1% (n=891) | 24.0% | 53.0% | 78.1% | 930.0 min (matches=153) |

## Frozen methodology

ATR14 matches main.py first-TR RMA initialization. ATR percentile is count(prior 100 ATR <= current ATR)/100; ties use inclusive rank, current observation excluded. Volume z matches main.py rolling20 mean/sample std including current closed volume; zero-volume windows yield zero. MACD is EMA12/26 with EMA9 signal, acceleration the second histogram difference.
A squeeze is consecutive qualifying closed candles; range uses only its episode candles. A breakout checks the prior range before considering the current candle for extension. After compression ends, the frozen range expires after four closed candles. Qualifying release needs volume and optional signed acceleration; it holds on a later closed candle, fails on return to/inside boundary, and confirmed releases expire after four more candles. Gate failures are distinct from false breakouts of qualified developing events. Fresh episodes are required before direction changes.
Selection uses only TRAIN 2020–2021 and VALIDATION 2022–2023, maximizing the lower 24h +1/-1 favorable-first frequency (minimum 30 developed events each), then validation mean signed close return. Hold=0 is diagnostic only and cannot be selected or used live. The selected parameters and all diagnostics are written before TEST evaluation. TEST begins 2024. No parameter change follows TEST. Neighbors are one-factor diagnostics, not another selection pass.
Reference price is signal close. Descriptive paths start with the next 5m candle; no executions, fees or PnL model. Same 5m candle hitting both barriers is adverse first. Unresolved observations are failures for favorable-first frequency but counted separately. Every horizon has its own complete-path denominator; missing/gapped paths and split-crossing horizons are censored. All signals can overlap; block bootstrap resamples seven-day event groups, seed773, 1000 repetitions.
Squeeze has no direction. Its LONG/SHORT paths in the event artifact are hypothetical diagnostics, not directional accuracy. Developing LONG/SHORT are evaluated separately. Lead compares with the first independently GOOD Manual Copilot setup since compression began, at most 48h after signal. Negative lead means that system confirmed before the early alert; unmatched events are explicitly excluded from the conditional median and counted.
Historical Manual Copilot comparison reuses its pure LOW/RSI27/EMA4 causal rolling 3000-cluster code and frozen SMA200/flow/confirmed pivot/entry-quality logic. It reproduces closed-price confirmation, not live Bitunix mark or venue volatility. Spot native timeframe candles are reconstructed only from complete 5m groups; missing groups conservatively invalidate live-sized lookbacks. RSI is seeded from full available causal segment history, which can differ slightly from the live 3200-candle initialization; this is a rule reproduction, not claimed perfect replay of a deployed alert.

## TEST neighbors

| Parameters | n | +1/-1, 24h | Signed close return mean, 24h |
|---|---:|---:|---:|
| `p0.2_n2_v1.5_h1_a1` | 891 | 44.1% | 0.0220% |
| `p0.15_n2_v1.5_h1_a1` | 798 | 45.1% | 0.0032% |
| `p0.25_n2_v1.5_h1_a1` | 1026 | 45.4% | 0.0154% |
| `p0.2_n3_v1.5_h1_a1` | 790 | 45.2% | 0.0170% |
| `p0.2_n4_v1.5_h1_a1` | 699 | 44.1% | -0.0165% |
| `p0.2_n2_v1_h1_a1` | 1128 | 44.8% | 0.0334% |
| `p0.2_n2_v2_h1_a1` | 656 | 44.2% | -0.0422% |
| `p0.2_n2_v1.5_h1_a0` | 941 | 44.0% | 0.0243% |

ATR 15/20/25% at the selected other settings: p0.2_n2_v1.5_h1_a1 = 44.1%; p0.15_n2_v1.5_h1_a1 = 45.1%; p0.25_n2_v1.5_h1_a1 = 45.4%. No post-TEST parameter change.

## TEST by year, direction and regime

| Slice | Developing | 24h n | +1/-1 24h | +2/-1 24h | False breakout | Median matched lead |
|---|---:|---:|---:|---:|---:|---:|
| YEAR 2024 | 349 | 349 | 45.0% | 26.4% | 55.0% | 1140.0 min (n=48) |
| YEAR 2025 | 330 | 330 | 42.4% | 21.8% | 54.5% | 975.0 min (n=62) |
| YEAR 2026 | 212 | 212 | 45.3% | 23.6% | 47.2% | 780.0 min (n=43) |
| LONG | 455 | 455 | 42.4% | 22.0% | 54.1% | 1065.0 min (n=58) |
| SHORT | 436 | 436 | 45.9% | 26.1% | 51.8% | 870.0 min (n=95) |
| REGIME -1 | 306 | 306 | 44.1% | 28.4% | 51.6% | 750.0 min (n=66) |
| REGIME 0 | 236 | 236 | 46.6% | 26.3% | 48.3% | 1515.0 min (n=41) |
| REGIME 1 | 349 | 349 | 42.4% | 18.6% | 57.3% | 795.0 min (n=46) |

## Concentration / uncertainty

Without best/top3 is ranked by 24h directional close return, not MFE or a realized trade. Full distributions, both directions, all five target/barrier pairs and 1/4/12/24/48h MFE/MAE are in results.json and selected_events.jsonl.gz.
Bootstrap 95% interval for TEST +1/-1 (24h): [0.40955385366352925, 0.4748616886459942].
Matched random closed-timestamp control uses the same year, causal SMA regime and signal side, seed994. TEST control +1/-1 24h: 46.6%. Seven-day joint block bootstrap CI95 for signal minus control: [-0.0717393069939442, 0.024744823165214307].
Predeclared ROBUST requires TEST frequency above 50% and matched control, a >=5 percentage-point control improvement with block CI lower bound >0, positive mean signed return, every neighbor above 50% and control, at least 200 developed TEST events, bootstrap lower bound above 50%, positive return without top3 and false-breakout rate <=35%. Otherwise positive evidence is PROMISING-BUT-FRAGILE, or NO EDGE. These are research labels, not profitability claims or corrected significance after selection.

| Removed events | n | Mean signed close return 24h | +1/-1 24h |
|---|---:|---:|---:|
| 0 | 891 | 0.0220% | 44.1% |
| 1 | 890 | 0.0103% | 44.0% |
| 3 | 888 | -0.0100% | 43.9% |

## Incident 82.6k → 84k

{"status": "UNIDENTIFIED_DATE_NOT_PROVIDED", "price_description": "82.6k -> 84k", "used_for_selection": false, "reason": "Price endpoints do not uniquely identify an incident; no cherry-picked match."}

The motivating price move is excluded from parameter selection. A precise dated window is required before matching it; no arbitrary historical price match is substituted.

## Reproduction

`python -m research.early_breakout_data --as-of 2026-10-02T16:05:00+00:00`
`python -m research.early_breakout_research --as-of 2026-10-02T16:05:00+00:00`
Archives are outside Git. data_manifest.json stores URLs, archive SHA256 checksums, row counts, timestamps and REST parameters; canonical array checksum prevents silent data changes. Binance [official public schema/checksums](https://github.com/binance/binance-public-data) documents the 2025 spot microsecond timestamp switch. No earlier research artifacts are changed.
