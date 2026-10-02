# I-GOD CONFLUENCE ENGINE

**PROMISING — MORE RESEARCH**

Frozen best LONG: `D_60m_R60_1_opposite`. SHORT evaluated independently: `C_15m_R240_-1_atr`.

Research only. No executor imports, private endpoints, orders, Railway changes, deployment or merge.

Binance BTCUSDT USD-M perpetual, 710,208 closed 5m candles, 2020-01-01 through 2026-10-02T00:00:00+00:00; 7,398 historical funding events. No spot/perp price splice.

## Metrics

| System / split | CAGR | Sharpe | MaxDD | Return | Trades | Expectancy |
|---|---:|---:|---:|---:|---:|---:|
| Selected TRAIN | 38.09% | 1.697 | -12.43% | 90.77% | 30 | 2.3751% |
| Selected VALIDATION | 18.92% | 1.395 | -10.36% | 41.39% | 23 | 1.6821% |
| Selected TEST | 20.95% | 1.121 | -15.58% | 68.76% | 96 | 0.5906% |
| Selected ALL | 25.17% | 1.362 | -15.58% | 355.17% | 149 | 1.1184% |
| V8 SMA200 4H TRAIN | 65.88% | 1.186 | -54.07% | 175.35% | 65 | 2.2231% |
| V8 SMA200 4H VALIDATION | 16.11% | 0.618 | -35.21% | 34.78% | 63 | 0.7313% |
| V8 SMA200 4H TEST | 21.22% | 0.767 | -33.43% | 69.83% | 82 | 0.9698% |
| V8 SMA200 4H ALL | 31.39% | 0.875 | -54.07% | 531.60% | 209 | 1.2943% |
| Buy & hold TRAIN | 152.65% | 1.583 | -56.24% | 539.14% | 1 | 539.1361% |
| Buy & hold VALIDATION | -4.41% | 0.179 | -67.28% | -8.62% | 1 | -8.6238% |
| Buy & hold TEST | 28.69% | 0.775 | -53.47% | 100.18% | 1 | 100.1760% |
| Buy & hold ALL | 44.01% | 0.913 | -77.09% | 1073.36% | 1 | 1073.3577% |
| SHORT TRAIN | -23.79% | -2.165 | -43.63% | -41.95% | 146 | -0.3657% |
| SHORT VALIDATION | 8.41% | 0.767 | -13.51% | 17.52% | 159 | 0.1129% |
| SHORT TEST | -16.36% | -1.884 | -40.86% | -38.84% | 250 | -0.1926% |
| SHORT ALL | -12.14% | -1.141 | -59.15% | -58.27% | 555 | -0.1506% |

## Signal outcomes

TEST 24h: +1% before -1% = 0.531578947368421; +2% before -1% = 0.29473684210526313; n=190. All signals, overlapping included. Executed next open. Same 5m candle both levels => adverse first. Unresolved paths count as failures. Price probabilities exclude transaction costs; trading metrics include them.

Longest losing streak: 7. Without best trade total return: 268.71%; without best three: 154.52%. Without entries in 2021/2022: 366.02%.

## Causality and frozen definitions

Signals at completed candle close, fill next open. SMA200 uses only completed regime bars. HH/HL and divergences use strict 2-left/2-right pivots with confirmation delayed two trigger bars; no backdated signal. Sweep lookbacks are 12/24/48 closed 1H bars, reclaim within three following bars; sweep validity three 1H bars. Divergence validity 3h. MACD 12/26/9, RSI14 crosses 55/45, momentum12 and volume20 1.5x/2x are computed controls. Main candidates use the predefined A–F families. E uses R2 plus confirmed 1H swing breakout; other entries use R1. R3 is an exploratory structural feature, not a tuned candidate.

ML RSI exact TradingView version was NOT reproducible: script identity/source unspecified. Approximation is Wilder RSI14 with EMA5 smoothing and fixed neutral [45,55], green >55, red <45. Neutral transitions only, no direct red-to-green transition trigger. This is NOT a trained machine learning model. No future labels or learned coefficients.

Four exits: opposite state or regime invalidation; 2 ATR14 stop with trailing updated after close; confirmed pivot invalidation at following open; 2 ATR risk / 4 ATR target (1:2). Stop first on ambiguous intrabar touch. Positions are fixed quantities sized at entry equity, no pyramiding. Period boundaries force flat and costs on both sides. Warmup features may use prior periods; holdings cannot cross split boundaries.

Primary 1x nominal, no liquidation; quantities are fixed until exit. Costs per side 5/10/20 bps total, half fees and half slippage, market taker assumption; not a claim of exchange fee tier. Funding signed and historical at event boundary on current notional. Turnover and costs in units of initial equity. Funding at aligned boundary charged on opening position; exact sequence within nonaligned 5m intervals is conservative. FUNDED_HOLD includes funding; BUY_HOLD is an unfunded underlying-price proxy. Higher leverage evaluated only if all promotion gates survive; isolated margin approximation uses 0.5% maintenance, no claim of exact exchange tiers.

## Statistical checks and limitations

Selection uses TRAIN through 2021, VALIDATION 2022–2023, minimum 20 trades each, ranked validation Sharpe then train Sharpe. Selection lock is persisted before TEST evaluation. TEST starts 2024 and never reranks candidates. 352 initial candidates (timeframe/regime/side/exit); no claim that these tests are independent. 7-day block bootstrap 500 repetitions seed773, parameter neighbors and ablation are diagnostics, not new selection. Daily dependence and selection bias remain; no corrected statistical significance claimed. The headline annual table resets positions; per-candidate annual equity slices retain positions at year boundaries. Regime results are descriptive conditional bar returns, with compressed time Sharpe, not standalone tradable strategies. Walk-forward is fixed-parameter annual forward evaluation in 2024, 2025 and 2026; no annual retuning. No higher leverage research if primary system fails gates.

The ablation uses identical regime/sweep/smoothed momentum building blocks and chosen exit; it evaluates states rather than A/B transition events. Therefore it directly tests the three-block RLM construction; if the selected family differs, it is a diagnostic and cannot establish that family’s incremental contribution. Promotion requires all conservative gates including improvement over every two-block ablation.

## Real liquidity data available

L1/L2 swing sweep and reclaim, L4 volume spikes, and L3 historical taker-buy base volume / total base volume from official kline files. These are reproducible proxies, not resting orderbook liquidity or an Aggr.Trade heatmap. Raw aggTrades were not downloaded because official klines contain the required historical taker volumes. L5 OI and L6 liquidations are excluded: no continuous verified 2020–2026 dataset acquired. This does not assert such archives cannot exist. No current OI, liquidation feed or orderbook used to infer past values.

Sources: [Binance public data schema](https://github.com/binance/binance-public-data), [funding history](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History). Exact archive URLs, dates, rows, checksums and public REST parameters are in `confluence_artifacts/data_manifest.json`. Datasets cached outside Git; reproduce with `python -m research.confluence_engine_backtest --download`, then offline `python -m research.confluence_engine_backtest`. All metrics, costs, year/regime results, bootstrap, neighbors, ablation, cost sensitivity and five MFE/MAE horizons with all target/barrier pairs are in `results.json`.

## Promotion gates

- beats_V8: True
- positive_test: True
- net_expectancy: True
- sharpe: True
- drawdown: True
- remove_best: True
- neighbors: False
- 20bps: True
- 1x: True
- ablation: True

## Validation

`python -m unittest research.test_confluence_engine -v` and `git diff --check`.

## Decision evidence

A positive TEST and better Sharpe/drawdown do not establish robust incremental edge. The selected 60% taker threshold has negative TEST neighbors at 55% and 65%. For family D, sweep-window neighbors are identical because sweep is absent; these are not independent stability tests. No parameters were revised after viewing TEST.

| Taker buy threshold | VALIDATION Sharpe | TEST return | TEST expectancy |
|---|---:|---:|---:|
| 55% | -0.247 | -20.23% | -0.0566% |
| 60% | 1.395 | 68.76% | 0.5906% |
| 65% | 1.929 | -1.82% | -0.0998% |

| Ablation | VALIDATION Sharpe | TEST return | TEST expectancy |
|---|---:|---:|---:|
| R | -3.547 | -95.97% | -0.1659% |
| L | 0.151 | -4.45% | 0.0026% |
| M | -3.450 | -95.71% | -0.1689% |
| RL | 0.927 | 21.25% | 0.1371% |
| RM | -0.466 | -14.28% | -0.0102% |
| LM | 1.274 | 77.84% | 0.4771% |
| RLM | 1.395 | 68.76% | 0.5906% |

| Ablation with common ATR exit | VALIDATION Sharpe | TEST return | TEST expectancy |
|---|---:|---:|---:|
| R | -1.714 | -79.23% | -0.1649% |
| L | -2.462 | 0.27% | 0.0162% |
| M | -1.214 | -73.84% | -0.1827% |
| RL | -1.913 | -14.81% | -0.0579% |
| RM | -0.837 | -57.51% | -0.1417% |
| LM | -0.996 | 2.32% | 0.0353% |
| RLM | -0.793 | 20.17% | 0.1696% |

The common selected exit itself includes momentum/regime invalidation. Removing a block from entries does not remove it from this exit. In particular, regime-only and momentum-only state entries can repeatedly reenter while the common exit is invalidated, inflating turnover. This ablation is an entry-filter diagnostic, not proof of fully independent complete systems. RLM improves expectancy but does not beat LM on TEST total return. Its mechanical ablation gate must not be interpreted as statistical significance.

| Year | Selected return (flat at year boundary) |
|---|---:|
| 2020 | 85.23% |
| 2021 | 2.99% |
| 2022 | -5.16% |
| 2023 | 49.08% |
| 2024 | 65.11% |
| 2025 | 10.29% |
| 2026 | -7.33% |

| Cost per side | Full return | TEST return |
|---|---:|---:|
| 5 bps | 428.01% | 85.73% |
| 10 bps | 355.17% | 68.76% |
| 20 bps | 238.10% | 39.28% |

Paired daily 7-day-block bootstrap versus V8: annual log-growth difference -4.85%, 95% interval [-0.3342702226891655, 0.23567561710612772], probability positive 35.8%. Includes zero, and does not correct selection multiplicity. Expectancy block-bootstrap interval: [0.0047867559201274145, 0.018195944398013898].

Third confirmation paired bootstrap, TEST versus LM chosen using VALIDATION: annual log-growth difference -1.91%, 95% interval [-0.1110693496140804, 0.03407626969141969], probability positive 32.4%. Common ATR exit control above avoids keeping RSI/regime in the exit while removing it from entries. No new entry or exit parameters were selected from these diagnostics.

Archive availability probes (samples, not verified continuous history):
- metrics 2020-01-01: HTTP 404, rows 0, used in signals: false.
- metrics 2021-12-01: HTTP 200, rows 288, used in signals: false.
- metrics 2022-01-01: HTTP 200, rows 288, used in signals: false.
- metrics 2026-09-01: HTTP 200, rows 288, used in signals: false.
- liquidationSnapshot 2020-01-01: HTTP 404, rows 0, used in signals: false.
- liquidationSnapshot 2021-12-01: HTTP 404, rows 0, used in signals: false.
- liquidationSnapshot 2022-01-01: HTTP 404, rows 0, used in signals: false.
- liquidationSnapshot 2026-09-01: HTTP 404, rows 0, used in signals: false.

## Benchmark and risk interpretation

BUY_HOLD is the unfunded underlying-price control using perpetual OHLC as a price proxy, not a downloaded spot portfolio. FUNDED_HOLD separately models perpetual fixed-quantity holding and all funding. A fixed quantity sized 1x at entry does not maintain constant 1x equity exposure: funding can exhaust collateral and effective leverage can drift. Insolvency floors equity at zero and is recorded; no exchange liquidation is simulated in the primary run. This interpretation also applies to V8 and all candidate trades. Drawdown uses candle-close equity, not intrabar worst equity. These limitations restrict promotion and must be reviewed before a shadow specification.

All frozen entry configurations have TRAIN/VALIDATION/TEST forward-outcome summaries in `all_signal_outcomes.json.gz`. The selected entry has individual signal MFE/MAE in `selected_signal_excursions.csv.gz`. Forward windows cannot cross split boundaries. The selected actual fills are in `selected_trades.csv.gz`; outcomes are not conditioned on a trade being executed. Diagnostics-only reproduction: `python -m research.confluence_engine_backtest --diagnostics-only`; entry-outcome reproduction: `python -m research.confluence_engine_backtest --signals-only`.
