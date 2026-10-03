# BackQuant parity gate

Exact TradingView parity is **not established**. The author publishes an [open-source indicator](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/), but the accessible page exposes its description and compiled metadata, not the full Pine. The unauthenticated source request for the page's public script ID/version returned **401**. No login, cookies or private API was attempted. The study must not promote a system under this uncertainty.

Missing material: the complete Pine exported from the user's installed version, its version identifier, chart symbol/venue and history origin, and a closed-bar export of source LOW, smoothed RSI, thresholds and colors from that exact TradingView chart. Independent mathematical fixtures are not TradingView parity fixtures.

The repository already points to a [copy attributed to BackQuant](https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html). Its hash/provenance is recorded as **unverified third-party material**, not authoritative evidence of the installed implementation. Its literal array construction/push code can introduce leading unavailable elements and unexpected cluster indices. It cannot safely be silently repaired and called the original. No source copy is republished as verified BackQuant code.

| Item | Existing causal port / diagnostic study | Exact parity gate |
| --- | --- | --- |
| RSI | Wilder RMA seeded on first 27 price changes; LOW source | Needs TradingView numeric fixture, especially zero-gain/loss cases |
| EMA4 | First finite RSI seed; alpha 2/5 | Config agrees; numeric fixture absent |
| Percentiles | Linear p25/p50/p75 each candle | Description confirms percentiles, exact implementation unavailable |
| Assignment/update | Three absolute-distance clusters, centroid means; lower index on distance tie | Literal attributed copy contains array-size/push ambiguity |
| Empty cluster | Retain prior centroid, finite samples only | Deliberate port policy; not verified Pine behavior |
| maxData | Trailing 3000 available RSI samples at each candle | Attributed code anchors to last visible bar and uses inclusive <=3000, not a prefix-invariant rolling window |
| maxIter | At most 1000 passes | Attributed inclusive 0..1000 allows 1001 passes |
| Thresholds | High centroid = long, low = short | Author description agrees |
| Color | >high GREEN; <low RED; equality NEUTRAL | Author description agrees broadly; exact fixture absent |
| Bar close | Only complete closed 15m aggregates, next-bar execution | User close setting honored; no intrabar signal/fill |
| 10/90/5, memory10 | Present in supplied configuration, no assumed effect | Attributed copy leaves factor array/memory unused; cannot assert original does |
| ALMA sigma1 | Irrelevant to chosen EMA4 | User-confirmed selection |

This study evaluates the existing finite-sample causal port without modifying it or any operational module. CROSS includes RED→GREEN/GREEN→RED as well as NEUTRAL transitions; these study events are intentionally separate from Guardian's existing neutral-only events. RESUME requires the same color on the preceding and current candle and a slope reset inside that continuous color episode. The two-bar variant fires only on the second confirming slope bar, after close.

Fees are configurable. The [official fee table](https://www.bitunix.com/service/handling-fee), accessed for this study, lists VIP1 futures taker 0.0500% (5 bps). This is a dated modeling assumption, not a verified account tier or permanent rate. Funding and cross-venue basis are excluded from underlying-return results; they are not an executable Bitunix futures performance claim.
