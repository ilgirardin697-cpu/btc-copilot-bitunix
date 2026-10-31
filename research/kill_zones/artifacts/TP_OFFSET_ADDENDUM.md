# Conservative TP offsets — requested post-hoc addendum

**POST-HOC. NO INDEPENDENT HOLDOUT.**
Four offsets were fixed before their own calculations, after the original twelve-cell result was known. Original rules, data, stops, costs, splits and outputs are unchanged. All four offsets are reported; none is selected for deployment.

Only NY / EXTREME_TIMES / original full geometric target. LONG subtracts the offset, SHORT adds it. ATR14 is calculated by the unchanged frozen public formula, using only the confirmation close. Fixed offsets: 0.10 ATR, 0.25 ATR, 5 bps and 10 bps of the confirmation close. Targets already behind the actual slipped entry are rejected rather than forced.

| Offset | Split | n | Net R mean | 95% block CI | PF | TP % | Net % | DD % | Stress R | Classification |
|---|---|---|---|---|---|---|---|---|---|---|
| ATR010 | DEVELOPMENT | 273 | -0.254 | [-0.458, -0.007] | 0.636 | 41.0 | -38.35 | 39.91 | -0.373 | DESCRIPTIVE |
| ATR010 | VALIDATION | 267 | -1.011 | [-2.034, -0.34] | 0.261 | 37.5 | -36.50 | 38.43 | -0.566 | DESCRIPTIVE |
| ATR010 | EVALUATION | 203 | -0.287 | [-0.449, -0.127] | 0.522 | 44.8 | -24.18 | 25.86 | -0.366 | NO EDGE |
| ATR025 | DEVELOPMENT | 266 | -0.265 | [-0.465, -0.022] | 0.615 | 42.1 | -37.58 | 38.93 | -0.385 | DESCRIPTIVE |
| ATR025 | VALIDATION | 266 | -0.975 | [-1.966, -0.312] | 0.269 | 41.0 | -32.37 | 34.93 | -0.534 | DESCRIPTIVE |
| ATR025 | EVALUATION | 202 | -0.274 | [-0.429, -0.122] | 0.520 | 47.5 | -21.99 | 24.68 | -0.360 | NO EDGE |
| BPS5 | DEVELOPMENT | 273 | -0.250 | [-0.456, -0.002] | 0.641 | 40.7 | -37.83 | 39.43 | -0.369 | DESCRIPTIVE |
| BPS5 | VALIDATION | 267 | -1.011 | [-2.035, -0.34] | 0.261 | 37.5 | -36.39 | 38.35 | -0.567 | DESCRIPTIVE |
| BPS5 | EVALUATION | 203 | -0.279 | [-0.443, -0.115] | 0.532 | 45.3 | -22.90 | 24.83 | -0.359 | NO EDGE |
| BPS10 | DEVELOPMENT | 270 | -0.258 | [-0.459, -0.014] | 0.628 | 41.9 | -37.80 | 39.27 | -0.378 | DESCRIPTIVE |
| BPS10 | VALIDATION | 266 | -0.987 | [-1.987, -0.321] | 0.265 | 39.8 | -33.94 | 36.69 | -0.543 | DESCRIPTIVE |
| BPS10 | EVALUATION | 202 | -0.272 | [-0.424, -0.117] | 0.527 | 47.0 | -22.21 | 25.18 | -0.357 | NO EDGE |

| Offset | vs TP100 daily R | 95% CI | vs RANGE daily R | 95% CI |
|---|---|---|---|---|
| ATR010 | -0.009 | [-0.022501645496347054, 0.008792162181326177] | -0.127 | [-0.23232360241902936, -0.013476688037836328] |
| ATR025 | 0.002 | [-0.028790201117912837, 0.035100328633836365] | -0.117 | [-0.2214974630039111, -0.010221832127031852] |
| BPS5 | -0.003 | [-0.020751396866626852, 0.017426684962203964] | -0.122 | [-0.2291206493383834, -0.0070240857115907935] |
| BPS10 | 0.003 | [-0.02872082943874875, 0.03990299501144912] | -0.115 | [-0.21985115273745076, -0.0065346361107966695] |

Rejections: {"ENTRY_AT_OR_BEYOND_STOP": 24, "ENTRY_AT_OR_BEYOND_TARGET": 70, "OVERLAPPING_POSITION": 124}.

## Future informative alert — not implemented
No robust advantage was demonstrated by the original protocol. No Telegram integration, emitter, scheduler, daily signal requirement or operational payload was added. A future independently approved protocol could describe a hypothetical side, next executable entry/zone, geometric and conservative TP, structural SL, estimated net RR, confirmation/expiry and missing conditions. Estimated RR must include both commission/slippage legs; future funding is UNKNOWN at confirmation and cannot be filled using future outcomes. LONG conservative TP is below the full target, SHORT is above. No guarantee that either is reached.

**RECOMMENDATION: DO NOT INTEGRATE. SHADOW ONLY. TRADE AUTHORITY: NONE.**
