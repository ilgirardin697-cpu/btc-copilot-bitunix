# BITMAN weekly state-machine research

**INCONCLUSIVE — NO RUNTIME INTEGRATION.**

The predeclared sequential proxy rules produce **7 episodes**, not 263 independent signals. The main large-breakout label occurs in 1/7 episodes (14.29%), versus 128/259 weekly opportunities (49.42%). Anchor-level recall 0.78%; lift 0.289. **INSUFFICIENT FOR CONCLUSION.** These historical results do not establish or refute the creator's private indicators.

**NO VIRGIN HOLDOUT. HYPOTHESIS FOR FORWARD OBSERVATION only.**

**EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN**

**EXACT BITMAN VOLATILITY PARITY: NOT PROVEN**

## 1. Source: what was reported and what was independently verified

[Primary video](https://www.youtube.com/watch?v=v8d3OxE1-_c), approximately minute20 onward. The owner reports a weekly sequence: same-side oscillator corrections with contracting volatility, followed by renewed momentum/expansion, or a zero crossing and expansion in the new direction. This report formalizes that supplied account. It does not treat the relationship as a rule for lower timeframes.

The public YouTube watch and oEmbed endpoints returned200; the player title is “CUANDO SALDRÁ de ese RANGO BITCOIN..???” and playability is OK. Spanish captions were advertised, but both the advertised track request and plain timedtext returned200 with **zero bytes**. Web retrieval also failed. The four previously cached transcripts are different videos. No new vidIQ credits, login, hidden formula retrieval or paid service was used. An independent transcript of this segment and visual chart dates were **not recovered**. See [source audit](bitman_weekly_state_machine/source_audit.json).

## 2. What is approximated, and unknown modified indicators

AO is **OSCILLATOR_PROXY**. The production frozen BBWP formula is **BITMAN_VOLATILITY_PROXY**. The owner reports that Bitman describes his volatility indicator as modified. Exact settings/formula are unknown. Neither visual similarity, the public video title, nor another video naming AO proves parity for this chart. No values or parameters were adjusted to fit examples. Statistical conclusions below concern these proxies only.

## 3. Dataset provenance and independence from PR #30

Base `9c660035f912be4640f09cf6e2d4c48583c20b04`. Reuse only the public data snapshot, audit manifest, aggregation/validation helpers and immutable indicator function from [PR #30](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/30), commit `c1c56bd1c4c87ad0f279616970ec9f13ae373302`. Its outputs/conclusion are unchanged. No new market download, outcome extension or venue substitution. The new episode labels/outcomes/results are independent files.

Venue **BTCUSDT / BINANCE_USDM_PERPETUAL**. Source official [USD-M `/fapi/v1/klines`](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/market-data/rest-api/Kline-Candlestick-Data). Acquired2026-10-20T10:28:43.290321Z:15,584 closed4H bars, first2019-09-08T16:00Z, last close2026-10-18T23:59:59.999Z. Aggregate exactly42 contiguous4H bars per Monday00:00UTC week. Drop the first partial week; exclude the currently open week.371 complete weeks open2019-09-09 through2026-10-12. Common warmup/lag eligibility leaves 263 weeks; first available 2021-10-11T00:00:00+00:00. Matured opportunities at1/2/3/4W:262/261/260/259. This is reconstructed historical market data, **not real forward observed signal journals**.

The inherited full comparison manifest is retained. All371 native REST1W H/L/C/timestamps match the4H weekly aggregation. One old open (2019-09-23:8061.98 vs10027.69) and five weeks of volume/taker fields differ:11 field differences total. Seven checksum-verified [official Vision USD-M](https://github.com/binance/binance-public-data) months/1,2784H bars match OHLC/times; four bars have volume-only differences. No discrepancy was silently repaired or blended. All eight AO/BBWP/ADX/DI arrays used in the prior audit were exactly identical between the native/aggregated series. The new study recalculates frozen math and checks all reused feature arrays/signs. ATR depends on matching H/L/C as well. Interval data consistency is not Bitman indicator parity.

RAW4H SHA256 `ea8954f95f15f67eff041e506fc9e0539d5adb7422632b5f7d8246e88704e050`; aggregated weekly JSON SHA256 `8278c1f44c250c7073c0bb912533a335325cd7109a2a10af59227f2d68a811bc`. RAW files stay local/ignored. Versioned weekly CSVs, original request/checksum metadata and source hashes are public-only.

## 4. Exact proxy formulas

Unchanged `bitman_manual.frozen.indicators.calculate`: AO=SMA5((H+L)/2)−SMA34((H+L)/2); GREEN iff AO−previousAO>0, RED iff<0, FLAT iff=0. Zero sign is separate from color. BBwidth=4×population_std(close,7)/SMA(close,7). BBWP counts the100 prior widths strictly below current in a complete101-width window, producing0–100. Volatility slope=one-week difference. ATR=existing Wilder14 true-range average, fixed at signal time for outcomes. No fitted lengths/thresholds.

## 5. Causal states, volatility turns and precedence

[Protocol committed before new episode outcomes](BITMAN_WEEKLY_STATE_MACHINE_PROTOCOL.md), commit `60ddd9a`. Known history from PR #30 means this ordering is procedural discipline, **not** a virgin holdout.

| State | Closed-week conditions | Weeks |
| --- | --- | --- |
| IMPULSE_UP | AO>0, GREEN, vol rising | 28 |
| PULLBACK_UP | AO>0, RED, vol non-rising | 35 |
| IMPULSE_DOWN | AO<0, RED, vol rising | 21 |
| PULLBACK_DOWN | AO<0, GREEN, vol non-rising | 32 |
| REACCELERATION_UP | Unbroken PULLBACK_UP run; RED→GREEN and non-rising→rising, no zero cross | 2 |
| REACCELERATION_DOWN | Mirror of UP | 2 |
| ZERO_CROSS_UP_EXPANSION | PreviousAO<0/currentAO>0; current vol rising | 2 |
| ZERO_CROSS_DOWN_EXPANSION | PreviousAO>0/currentAO<0; current vol rising | 1 |
| OTHER | Valid but no defined combination | 140 |

Reacceleration/zero-cross override base impulse labels. Exact zero is not a strict cross. An invalid/OTHER/opposite-sign week interrupts the immediate pullback run. Cross and expansion must coincide; no retrospectively matched delayed expansion. Uninterrupted corrective weeks, their resolution and frozen range form one episode. No requirement for an immediately preceding impulse was added: metadata records its presence, and none of these seven has an immediate same-side IMPULSE before its pullback/start. Older same-side impulse timestamps and all base-state runs are published. This is a limitation of correspondence to an ideal IMPULSE→PULLBACK→REACCELERATION illustration.

ACTIVE_RISING: slope>0. TURN_UP: previous<=0/current>0. SUSTAINED_TURN: at least2 consecutive prior non-rising weeks/current>0. COOLING:<0; FLAT:=0. TURN flags nest inside ACTIVE_RISING. Level50 flags are reported for all opportunities and signal episodes; falling-through50 equals the predeclared downward cross plus negative slope, so it is deliberately redundant.

## 6. Frozen range, breakout, important move and censoring

Main range=last4 completely closed weekly highs/lows **including signal week**, frozen before future weeks. SensitivityN=2/8, all reported without choosing a winner. Including the signal candle ensures the anchor is inside and avoids credit for movement already completed before availability. It is a rolling range, not proof of congestion. Width/causalATR and descriptive width<=2ATR congestion are recorded; no fitted congestion filter.

Primary breakout=first future weekly **close** strictly outside the range. Wicks are separate. If both boundaries are touched in one weekly candle, wick order is BOTH/ORDER_UNKNOWN. Primary large-breakout label=close breakout plus >=10% excursion from signal close in the same breaking direction within horizon. The threshold excursion can precede/follow the close breakout within that horizon; intrahorizon order is not asserted. This measures an event, not tradable returns or execution. All5/10/15/20% and1/1.5/2ATR excursion thresholds are retained.

No break by4W is administratively censored for time-to-event; a not-yet-complete horizon is missing, not a failure. Report later close reentry/opposite-side return, end-close outside, and no-reentry persistence only with >=1 followup week. A breakout on the final horizon week cannot establish persistence.

## 7. Individual sequential episodes

| Available UTC | State | Pullback weeks | 4W close break / time | Max excursion | Signed terminal | Large10 |
| --- | --- | --- | --- | --- | --- | --- |
| 2022-09-19 | REACCELERATION_DOWN | 1 | CENSORED / 4W | 7.662% | 0.786% | 0 |
| 2023-06-26 | REACCELERATION_UP | 1 | CENSORED / 4W | 4.570% | -1.271% | 0 |
| 2023-10-23 | ZERO_CROSS_UP_EXPANSION | 1 | UP / 1W | 28.412% | 24.663% | 1 |
| 2025-10-06 | REACCELERATION_UP | 1 | CENSORED / 4W | 17.752% | -10.477% | 0 |
| 2025-11-24 | ZERO_CROSS_DOWN_EXPANSION | 0 | CENSORED / 4W | 8.925% | -2.089% | 0 |
| 2026-06-08 | REACCELERATION_DOWN | 3 | CENSORED / 4W | 8.752% | -0.503% | 0 |
| 2026-09-07 | ZERO_CROSS_UP_EXPANSION | 0 | UP / 3W | 8.822% | 7.698% | 0 |

Full `analysis.json` contains episode IDs, start/end, sign/color/proxy sequences, prior impulse metadata, range, all4W outcomes, and contiguous descriptive runs. `observations.csv` contains all3range×4horizon outcomes for every matured opportunity, including1/2/3W episode followup. No persistent expansion was counted as repeated signals.

## 8. Magnitude, base rate, precision, recall and lift

Precision=large labels at signal opportunities/signals. Recall=those true positives/all large-label opportunities. Base rate=large labels/all eligible opportunities in the same scope. These are **anchor-level**, not unique-market-move recall: nearby weekly anchors can reference the same future move. No independence or operational coverage claim.

| Horizon | Signals n | Large precision | Base rate | Recall | Lift | Close break | Wick break | Mean/median max % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7 | 14.29% | 13.36% | 2.86% | 1.069 | 14.29% | 42.86% | 9.202 / 6.804 |
| 2 | 7 | 14.29% | 27.20% | 1.41% | 0.525 | 14.29% | 57.14% | 9.962 / 6.804 |
| 3 | 7 | 14.29% | 38.46% | 1.00% | 0.371 | 28.57% | 85.71% | 11.944 / 8.822 |
| 4 | 7 | 14.29% | 49.42% | 0.78% | 0.289 | 28.57% | 85.71% | 12.128 / 8.822 |

| Control (4W) | n | Large10 rate | Mean max % | Median max % | Mean max ATR | Signed mean % |
| --- | --- | --- | --- | --- | --- | --- |
| SIGNALS | 7 | 14.29% | 12.128 | 8.822 | 1.426 | 2.687 |
| ALL | 259 | 49.42% | 17.763 | 15.611 | 1.669 | 1.082 |
| VOL_TURN | 50 | 54.00% | 19.307 | 16.856 | 1.808 | 2.121 |
| VOL_RISING | 127 | 44.09% | 16.255 | 14.457 | 1.546 | 2.252 |
| VOL_FALLING | 118 | 54.24% | 18.908 | 16.837 | 1.760 | 0.813 |
| SIGN_POS | 151 | 47.68% | 16.823 | 14.425 | 1.835 | 2.284 |
| SIGN_NEG | 108 | 51.85% | 19.077 | 17.129 | 1.437 | -0.598 |
| COLOR_GREEN | 135 | 54.07% | 18.084 | 15.866 | 1.798 | 1.190 |
| COLOR_RED | 124 | 44.35% | 17.414 | 15.523 | 1.529 | 0.964 |
| PULLBACK_NO_REACCEL | 67 | 67.16% | 21.093 | 19.990 | 1.954 | -0.970 |

The pooled main signal is weaker than all-weeks and volatility-turn magnitude controls in this sample; the rarity of the sequence cannot be repaired by loosening its definition after seeing outcomes.

| 4W metric | Signals | All weeks | Vol TURN_UP |
| --- | --- | --- | --- |
| up excursion mean % | 9.268 | 11.904 | 13.718 |
| down excursion mean % | 6.887 | 10.477 | 10.215 |
| distance beyond range mean ATR | 0.798 | 0.945 | 1.140 |
| max excursion >= 5% | 85.71% | 98.84% | 98.00% |
| max excursion >= 10% | 28.57% | 79.15% | 78.00% |
| max excursion >= 15% | 28.57% | 54.05% | 70.00% |
| max excursion >= 20% | 14.29% | 31.27% | 42.00% |
| max excursion >= 1 ATR | 42.86% | 72.59% | 78.00% |
| max excursion >= 1.5 ATR | 28.57% | 47.10% | 50.00% |
| max excursion >= 2 ATR | 28.57% | 27.80% | 34.00% |
| close breakout + >= 5% | 28.57% | 57.14% | 64.00% |
| close breakout + >= 10% | 14.29% | 49.42% | 54.00% |
| close breakout + >= 15% | 14.29% | 40.15% | 52.00% |
| close breakout + >= 20% | 14.29% | 28.96% | 36.00% |

Only2/7 have a4W close breakout (UP,1W and3W);5 are censored. Both observed close breaks remain outside with 3 and1 subsequent closed weeks, respectively, and no close reentry; **n=2**, not a persistence claim. Six have a wick breakout. The weekly OHLC cannot tell the order of same-week double touches.

## 9. Direction is a separate endpoint

| Group | n | Signed mean % | Signed median % | Terminal hit | Correct first close-break / all | Conditional direction n / rate |
| --- | --- | --- | --- | --- | --- | --- |
| SIGNALS | 7 | 2.687 | -0.503 | 42.86% | 28.57% | 2 / 100.00% |
| SIGNAL_UP | 4 | 5.153 | 3.213 | 50.00% | 50.00% | 2 / 100.00% |
| SIGNAL_DOWN | 3 | -0.602 | -0.503 | 33.33% | 0.00% | 0 / NA |
| REACCELERATION_UP | 2 | -5.874 | -5.874 | 0.00% | 0.00% | 0 / NA |
| REACCELERATION_DOWN | 2 | 0.142 | 0.142 | 50.00% | 0.00% | 0 / NA |
| ZERO_CROSS_UP_EXPANSION | 2 | 16.181 | 16.181 | 100.00% | 100.00% | 2 / 100.00% |
| ZERO_CROSS_DOWN_EXPANSION | 1 | -2.089 | -2.089 | 0.00% | 0.00% | 0 / NA |

Direction uses episode side (equal to current oscillator sign for these states), not isolated GREEN/RED. Summary-table signed returns use current oscillator sign for every opportunity control, including color-only groups; the separate per-side comparisons instead fix UP or DOWN for both signal and matching-sign/color control. The2/2 conditional UP breaks omit five no-break outcomes and are not a100% directional success claim. Signed mean is driven by the2023-10 episode; pooled signed median is negative. Per-side paired contrasts versus same-sign, same-color, vol-turn and pullback controls are in `comparisons.csv`. Their episode n is below10: no reliable incremental directional conclusion or published bootstrap CI.

## 10. Pullback duration and level50 — all predeclared cells

| Duration group | n | Large10 | Mean max % | Signed mean % |
| --- | --- | --- | --- | --- |
| REACC_GE1 | 4 | 0.00% | 9.684 | -2.866 |
| REACC_GE2 | 1 | 0.00% | 8.752 | -0.503 |
| REACC_GE3 | 1 | 0.00% | 8.752 | -0.503 |
| REACC_EXACT_1 | 3 | 0.00% | 9.994 | -3.654 |
| REACC_EXACT_2 | 0 | NA | NA | NA |
| REACC_EXACT_3 | 1 | 0.00% | 8.752 | -0.503 |
| REACC_EXACT_GE4 | 0 | NA | NA | NA |

Duration buckets above concern reacceleration, not zero-cross metadata. Empty cells stay NA. No duration or level50 cell is promoted to a rule.

| Level condition | All n / large10 | Signal n / large10 |
| --- | --- | --- |
| GT50 | 106 / 36.79% | 3 / 0.00% |
| LE50 | 153 / 58.17% | 4 / 25.00% |
| CROSS_UP50 | 21 / 52.38% | 1 / 0.00% |
| CROSS_DOWN50 | 20 / 50.00% | 0 / NA |
| FALL_THROUGH50 | 20 / 50.00% | 0 / NA |
| TURN_LE50 | 36 / 61.11% | 4 / 25.00% |
| TURN_GT50 | 14 / 35.71% | 1 / 0.00% |

## 11. Falsification: failures and missed events

| Predeclared counterexample category | Count at4W/N4 |
| --- | --- |
| VOL_TURN_NO_LARGE | 23 |
| VOL_TURN_NO_MOVE10 | 11 |
| REACC_UP_NEGATIVE | 2 |
| REACC_DOWN_POSITIVE | 1 |
| REACC_UP_OPPOSITE | 0 |
| REACC_DOWN_OPPOSITE | 0 |
| LARGE_WHILE_VOL_FALLING | 64 |
| MOVE10_WHILE_VOL_FALLING | 101 |
| LARGE_WITHOUT_SETUP | 127 |
| SETUP_FALSE_POSITIVE | 6 |

VOL_TURN_NO_LARGE means no close-range-exit plus10% label; VOL_TURN_NO_MOVE10 specifically means no10% excursion in either direction, regardless of range exit. These are different falsifications.

Both UP reaccelerations finish lower at4W: available2023-06-26 and2025-10-06. The DOWN reacceleration available2026-06-08 finishes higher. These are terminal wrong-side outcomes; neither side has an opposite **close** breakout in its two reacceleration episodes, primarily because these four episodes have no close breakout at all. Zero opposite breaks therefore is not evidence of predictive direction.

The2025-10-06 UP setup has17.752% downside excursion and a−10.477% terminal return: a large move can occur in the wrong direction and only via wick exit under the fixed range. The2022-09-19 DOWN reacceleration has max7.662% and no close exit. Every counterexample timestamp and measurement is published in `falsification.csv`; no cherry-picked success gallery. The128 overlapping positive-label opportunities include127 without a setup: these are anchor-level false negatives, not127 distinct crashes/rallies. Full falsification lists retain that distinction.

## 12. Robustness, distributions and influence

Fixed2,000 circular moving-block replicates, seed20261020, block8weeks. Calendar blocks include all weekly opportunities, not IID resampling of the seven episode rows. Paired contrasts preserve shared calendar draws. Block4/12 sensitivities are published in `analysis.json`. CI requires n>=10 and>=95% finite bootstrap replicates; therefore all main episode CIs are **NA / INSUFFICIENT FOR CONCLUSION**, not spuriously precise intervals. Baseline CIs and all unadjusted contrasts are in CSVs. n<30 cells are explicitly insufficient. Mean/median/sd/p10/p25/p75/p90 and best-event exclusions are published; these descriptive multiple comparisons have no virgin holdout or confirmatory significance.

| Baseline max % | Mean CI95 | Median CI95 | Large10 CI95 |
| --- | --- | --- | --- |
| ALL | 15.959 / 19.743 | 13.775 / 17.313 | 41.70% / 56.37% |
| VOL_TURN | 16.620 / 22.182 | 15.915 / 21.691 | 40.38% / 67.50% |
| VOL_FALLING | 16.405 / 21.448 | 13.905 / 19.021 | 43.09% / 65.46% |

| Removed by | k | n | Max mean % | Signed mean % | Precision | Excluded availability dates |
| --- | --- | --- | --- | --- | --- | --- |
| max_move | 0 | 7 | 12.128 | 2.687 | 14.29% | none |
| max_move | 1 | 6 | 9.414 | -0.976 | 0.00% | 2023-10-23 |
| max_move | 3 | 4 | 7.451 | 1.677 | 0.00% | 2023-10-23, 2025-10-06, 2025-11-24 |
| signed | 0 | 7 | 12.128 | 2.687 | 14.29% | none |
| signed | 1 | 6 | 9.414 | -0.976 | 0.00% | 2023-10-23 |
| signed | 3 | 4 | 10.000 | -3.585 | 0.00% | 2023-10-23, 2026-09-07, 2022-09-19 |

Removing the best event reverses the pooled signed mean. Removing best3 leaves only4 episodes. This sensitivity is adverse evidence, not grounds to recalibrate a proxy or redefine the sequence.

| Range N | Horizon | n | Precision | Base | Lift | Close break |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 1 | 7 | 14.29% | 13.36% | 1.069 | 14.29% |
| 4 | 2 | 7 | 14.29% | 27.20% | 0.525 | 14.29% |
| 4 | 3 | 7 | 14.29% | 38.46% | 0.371 | 28.57% |
| 4 | 4 | 7 | 14.29% | 49.42% | 0.289 | 28.57% |
| 2 | 1 | 7 | 14.29% | 16.41% | 0.870 | 14.29% |
| 2 | 2 | 7 | 14.29% | 31.03% | 0.460 | 14.29% |
| 2 | 3 | 7 | 14.29% | 46.15% | 0.310 | 28.57% |
| 2 | 4 | 7 | 14.29% | 59.85% | 0.239 | 28.57% |
| 8 | 1 | 7 | 14.29% | 11.45% | 1.248 | 14.29% |
| 8 | 2 | 7 | 14.29% | 20.69% | 0.690 | 14.29% |
| 8 | 3 | 7 | 14.29% | 30.77% | 0.464 | 28.57% |
| 8 | 4 | 7 | 14.29% | 39.77% | 0.359 | 28.57% |

Greedy first-event windows reject subsequent signals within4weeks; all seven already satisfy this separation (zero overlapping signal windows). Opportunity labels still overlap. Four fixed calendar phases and one-per-run same-sign/color/pullback controls are published. This is not equivalent to seven independent market regimes.

## 13. Temporal stability and existing causal regimes

| Scope | Signal n | Large10 precision | Local base | Lift | Signed mean % | Mean max % |
| --- | --- | --- | --- | --- | --- | --- |
| 2020-2022 | 1 | 0.00% | 53.12% | 0.000 | 0.786 | 7.662 |
| 2023-2024 | 2 | 50.00% | 53.33% | 0.938 | 11.696 | 16.491 |
| 2025-2026 | 4 | 0.00% | 42.22% | 0.000 | -1.343 | 11.063 |
| BULL | 4 | 25.00% | 50.79% | 0.492 | 5.153 | 14.889 |
| BEAR | 3 | 0.00% | 48.12% | 0.000 | -0.602 | 8.446 |

Regime is the frozen causal4H close versus SMA200 observed at weekly availability, not retrospective bull/bear labels. Warmup removes2020 and most2021; the first requested era is substantially truncated. Each era has very few episodes. The sole large success is in2023–2024; no stability conclusion is supported.

| Horizon | Past-matured control pairs | Mean max-move difference pp | Mean large-label difference |
| --- | --- | --- | --- |
| 1 | 7 | 0.911 | 0.015 |
| 2 | 7 | -1.693 | -0.106 |
| 3 | 7 | -2.325 | -0.230 |
| 4 | 7 | -4.399 | -0.329 |

Temporal controls use only trailing52weekly anchors whose complete forward horizon was already known at signal availability (at least12controls). No future outcome matching. Their dependent small pair count does not warrant an IID CI.

## 14. POST-HOC VISUAL CONSISTENCY CHECK

**NOT ASSESSABLE.** No independently verified on-screen dates or indicator settings were recovered from the supplied video. The episodes in section7 are auditable proxy sequences but are **not asserted to be Bitman's shown examples**. Exact-video dates/screenshots plus reproducible public settings are missing. Source access limitations do not demonstrate PROXY MISMATCH, and no visual parity claim is made. Future dated comparisons must stay post-hoc and cannot calibrate these parameters.

## 15. Comparison with PR #30

PR #30 tested AO color×BBWP rising/falling snapshots and concluded **EXPANSION EFFECT FRAGILE**. That conclusion remains unchanged, including its positive descriptive expansion-start2W return finding. This study asks a different sequential, zero-sign-conditioned question and uses frozen-range/close-breakout targets. Seven sparse sequence signals cannot replace127 rising-volatility opportunities or be pooled with them to enlarge n. The prior market history was already inspected: **NO VIRGIN HOLDOUT**.

## 16. Proxy and statistical limitations

Unknown private oscillator/modified-volatility settings; unavailable independent target-video captions/visual dates; only seven episodes; no adequate era/side/duration sample; long BBWP warmup; strict simultaneous cross/expansion definition; signal-week range inclusion can absorb the large move already occurring on a weekly signal candle; historical API revisions; OHLC cannot resolve intrabar order; overlapping target opportunities; unadjusted multiple comparisons; no untouched test set. A range-close endpoint differs from a discretionary chart reading. Neither insufficient evidence nor proxy failures establish that the creator's undisclosed rule is false.

## 17. CURRENT WEEKLY STATE — CURRENT OBSERVATION — NOT PART OF VALIDATION

Last fully closed week: 2026-10-12T00:00:00+00:00 → 2026-10-19T00:00:00+00:00. Open week excluded.

```text
Oscillator proxy: ABOVE ZERO / GREEN
AO: 10698.622; slope: 348.994
Volatility proxy: 41.000 → 30.000; slope: -11.000
Volatility state: COOLING
TURN_UP: False; SUSTAINED_TURN: False
Sequence: OTHER
Frozen4W range: 79732.300 → 87385.100
Large move watch: NOT VALIDATED
CURRENT OBSERVATION ONLY
```

Positive AO/GREEN with falling volatility is OTHER under the declared machine; it is not forced into IMPULSE_UP or PULLBACK_UP. The last six weekly states are OTHER. No current directional or operational signal is inferred.

## 18. Conclusion and review artifacts

**INCONCLUSIVE**

No robust incremental magnitude or direction evidence is established. **Do not integrate into runtime.** Any future specification remains HYPOTHESIS FOR FORWARD OBSERVATION; first obtain dated source/proxy evidence and a prospectively fixed observation protocol, without changing this historical study after outcomes.

Artifacts: `analysis.json` (episodes/runs/current/influence/overlap), `states.csv`, `observations.csv`, `summaries.csv`, `comparisons.csv`, `temporal_controls.csv`, `falsification.csv`, source/data/artifact manifests under `research/results/bitman_weekly_state_machine/`. Offline replay: `python -m research.bitman_state_analysis`; report: `python -m research.bitman_state_reporting`. Artifact hashes normalize CRLF→LF only. All reused inputs have fixed hashes. No raw transcripts or sensitive exports committed.

Only isolated research, new tests and a new research workflow are added. Frozen indicators/engine, operational gates, Guardian, acquisition service, V8, ML RSI, risk/execution, Telegram and Railway remain untouched. No automatic alerts. No orders. **TRADE AUTHORITY: NONE.**
