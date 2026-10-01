# V8 BEAR ENGINE — investigación independiente

Solo research/backtest. Sin ejecución, API privada ni cambios V8 REAL/Railway.

## Datos y diseño

Snapshot UTC: 2026-10-01T14:02:56+00:00. Principal: Binance BTCUSDT perpetual (minimum 2020-2026; no imputed pre-launch data): 2020-01-01T00:00:00+00:00 a 2026-10-01T12:00:00+00:00. Perpetual: 2020-01-01T00:00:00+00:00 a 2026-10-01T12:00:00+00:00. TRAIN hasta 2022-12-31; TEST desde 2023-01-01. Velas 4H UTC cerradas, sin huecos ni imputación. Indicadores precalentados con datos anteriores al inicio de evaluación.

Se reproduce exactamente la regla de señal del baseline SMA200 LONG/FLAT. No hay una curva ni cifras del backtest anterior incluidas en main con las que certificar coincidencia numérica. El control sin funding permite comparar resultados de precio; el principal incorpora financiación real.

Auditoría y fallback: {'binance_spot_rejected': 'Not a completely closed UTC 4H candle', 'binance_spot_nonstandard_close_times': 19, 'binance_spot_gaps': [[1504699200000, 1504728000000], [1518048000000, 1518163200000], [1529971200000, 1530014400000], [1530662400000, 1530691200000], [1542153600000, 1542182400000], [1552348800000, 1552377600000], [1557878400000, 1557921600000], [1565827200000, 1565856000000], [1582099200000, 1582128000000]], 'coinbase_rejected': "Coinbase missing 45 hourly candles; first=['2017-09-25T09:00:00+00:00', '2017-09-25T10:00:00+00:00', '2017-12-01T07:00:00+00:00', '2017-12-12T06:00:00+00:00', '2018-02-01T05:00:00+00:00'], last=['2026-05-08T02:00:00+00:00', '2026-05-08T03:00:00+00:00', '2026-05-08T04:00:00+00:00', '2026-05-08T05:00:00+00:00', '2026-05-08T06:00:00+00:00']"}. No se inventan velas para ampliar el histórico.

Fuente: [Binance public data](https://github.com/binance/binance-public-data), [klines públicas](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints), [funding público](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History). [Coinbase candles públicas](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles). ZIP comprobados contra SHA256 oficial; REST para meses aún sin publicar. Manifest y snapshots gzip incluidos.

Señal al cierre t, aplicación al open t+1. Retorno de open a siguiente open; último periodo se marca al close cerrado. Coste = 0.001 * abs(cambio de exposición), descontado antes del retorno. Reverse LONG/SHORT paga ambas unidades. HOLD no paga turnover. Cartera académica con pesos objetivo por periodo; no reproduce fills, borrow, liquidación, market impact ni costes de rebalanceo por deriva dentro de HOLD. Exposición máxima 1x, sin apalancamiento alto. La fórmula de pesos difiere ligeramente del sizing financiado de SHADOW: 1-c frente a 1/(1+c) en entrada.

Principal: incluye funding real cuando hay cobertura completa del mercado perpetual, como en esta ejecución. Control: mismas velas sin funding. Sensibilidad adversa: SHORT paga un coste ADICIONAL de 10% y 25% APR prorrateados sobre su exposición, sin modificar las tasas históricas. LONG paga funding positivo; SHORT lo recibe. La liquidación de funding en frontera 8H se aplica a la exposición previa a la orden de ese instante.

Cobertura funding perpetual 2020+: {'expected_settlements': 7397, 'available_settlements': 7397, 'missing_settlements': 0, 'missing_first': []}.

Sharpe/Sortino sobre retornos 4H, anualización sqrt(365.25*6), libre de riesgo cero. Max DD al cierre de periodo (no intrabar). Trades cerrados íntegramente dentro de cada segmento para win/PF; las curvas TRAIN/TEST conservan exposición, no fuerzan cierre en la frontera. Coste acumulado en unidades de equity inicial, no porcentaje fijo del equity final. Trades abiertos se marcan en equity pero se excluyen de win/PF.

C usa slope de 10 velas y Donchian 20/10; D Donchian 55/20. Los canales usan low/high de velas anteriores, excluyendo la actual. En C/D el régimen filtra la entrada; la salida sigue exclusivamente el canal superior. G agrega cierres diarios UTC: señal de un día solo disponible tras 24:00 y aplicada al periodo 4H siguiente.

## Selección congelada antes de TEST

Dos candidatos elegidos por TRAIN: **F, C**. Regla fija: mejora de Sharpe + 0.5 * mejora de Calmar del combinado SHORT 0.25x frente al baseline, en TRAIN de precios+turnover SIN créditos funding. Es una selección conservadora independiente de créditos de financiación. No se usa CAGR máximo ni TEST para escoger parámetros. Los vecindarios autorizados se muestran completos; ninguna variante sustituye retrospectivamente la configuración base.

F conserva siempre momentum 504: no se autorizó un grid de lookbacks momentum. Se muestran únicamente filtros estructurales adicionales slope SMA200 5/10/20; no se presentan como prueba de vecindad del parámetro 504. E tampoco recibe parámetros inventados.

## Tabla final — principal, histórico completo

| Sistema | CAGR | Retorno | Sharpe | Sortino | Max DD | Calmar | Trades | Win | Avg win | Avg loss | PF | % LONG | % SHORT | Turnover | Coste / equity inicial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMBO_C_0.25 | 37.34% | 751.58% | 0.98 | 1.43 | -54.30% | 0.69 | 306 | 18.95% | 10.43% | -1.33% | 1.40 | 54.12% | 15.74% | 466.00 | 2.05 |
| V8_LONG_FLAT | 36.10% | 700.81% | 0.96 | 1.41 | -52.50% | 0.69 | 208 | 13.94% | 18.78% | -1.55% | 1.45 | 54.12% | 0.00% | 417.00 | 1.77 |
| COMBO_F_0.25 | 36.79% | 728.70% | 0.96 | 1.41 | -51.46% | 0.71 | 333 | 16.82% | 10.55% | -1.15% | 1.42 | 54.12% | 27.67% | 479.50 | 2.05 |
| COMBO_C_0.50 | 37.76% | 769.10% | 0.95 | 1.41 | -56.42% | 0.67 | 306 | 18.95% | 11.46% | -1.55% | 1.35 | 54.12% | 15.74% | 515.00 | 2.28 |
| COMBO_B_0.25 | 36.14% | 702.40% | 0.95 | 1.39 | -53.49% | 0.68 | 345 | 18.26% | 9.55% | -1.18% | 1.39 | 54.12% | 36.65% | 485.50 | 2.04 |
| COMBO_G_0.25 | 36.15% | 702.95% | 0.95 | 1.39 | -52.44% | 0.69 | 339 | 15.04% | 11.75% | -1.15% | 1.39 | 54.12% | 40.02% | 482.50 | 2.02 |
| COMBO_D_0.25 | 35.20% | 665.62% | 0.94 | 1.37 | -57.16% | 0.62 | 311 | 18.33% | 10.49% | -1.32% | 1.37 | 54.12% | 21.79% | 468.50 | 1.94 |
| COMBO_F_0.50 | 36.39% | 712.60% | 0.92 | 1.35 | -51.01% | 0.71 | 333 | 16.52% | 11.54% | -1.30% | 1.38 | 54.12% | 27.67% | 542.00 | 2.24 |
| COMBO_A_0.25 | 34.21% | 628.58% | 0.91 | 1.33 | -58.41% | 0.59 | 417 | 13.67% | 10.70% | -0.97% | 1.35 | 54.12% | 45.88% | 521.50 | 2.02 |
| COMBO_E_0.25 | 33.01% | 585.82% | 0.89 | 1.31 | -52.64% | 0.63 | 475 | 16.21% | 7.95% | -0.90% | 1.30 | 54.12% | 29.03% | 550.50 | 2.23 |
| COMBO_B_0.50 | 34.82% | 651.44% | 0.89 | 1.30 | -55.11% | 0.63 | 345 | 18.26% | 10.40% | -1.38% | 1.32 | 54.12% | 36.65% | 554.00 | 2.19 |
| COMBO_G_0.50 | 34.78% | 650.07% | 0.88 | 1.30 | -53.09% | 0.66 | 339 | 15.04% | 12.75% | -1.33% | 1.33 | 54.12% | 40.02% | 548.00 | 2.15 |
| COMBO_D_0.50 | 33.36% | 598.09% | 0.88 | 1.29 | -61.77% | 0.54 | 311 | 18.33% | 11.40% | -1.54% | 1.29 | 54.12% | 21.79% | 520.00 | 2.03 |
| COMBO_C_1.00 | 36.11% | 701.28% | 0.86 | 1.27 | -61.36% | 0.59 | 306 | 18.30% | 13.96% | -1.97% | 1.26 | 54.12% | 15.74% | 613.00 | 2.50 |
| COMBO_A_0.50 | 30.81% | 512.89% | 0.81 | 1.19 | -64.23% | 0.48 | 417 | 13.43% | 12.01% | -1.18% | 1.27 | 54.12% | 45.88% | 626.00 | 2.09 |
| COMBO_E_0.50 | 28.92% | 455.44% | 0.79 | 1.16 | -53.30% | 0.54 | 475 | 16.21% | 8.81% | -1.11% | 1.20 | 54.12% | 29.03% | 684.00 | 2.51 |
| COMBO_F_1.00 | 32.41% | 565.21% | 0.79 | 1.16 | -51.69% | 0.63 | 333 | 16.52% | 13.03% | -1.62% | 1.28 | 54.12% | 27.67% | 667.00 | 2.31 |
| COMBO_B_1.00 | 28.33% | 438.69% | 0.72 | 1.06 | -59.96% | 0.47 | 345 | 18.26% | 11.93% | -1.78% | 1.21 | 54.12% | 36.65% | 691.00 | 2.08 |
| COMBO_D_1.00 | 27.08% | 404.10% | 0.72 | 1.06 | -70.49% | 0.38 | 311 | 18.01% | 13.37% | -1.99% | 1.18 | 54.12% | 21.79% | 623.00 | 1.97 |
| COMBO_G_1.00 | 28.02% | 429.86% | 0.72 | 1.05 | -56.16% | 0.50 | 339 | 15.04% | 14.56% | -1.72% | 1.21 | 54.12% | 40.02% | 679.00 | 2.02 |
| COMBO_A_1.00 | 20.04% | 243.07% | 0.60 | 0.88 | -74.84% | 0.27 | 417 | 13.43% | 14.04% | -1.60% | 1.14 | 54.12% | 45.88% | 835.00 | 1.78 |
| COMBO_E_1.00 | 18.16% | 208.47% | 0.58 | 0.85 | -59.83% | 0.30 | 475 | 16.00% | 10.60% | -1.53% | 1.08 | 54.12% | 29.03% | 951.00 | 2.58 |
| SHORT_C | 0.59% | 4.02% | 0.17 | 0.27 | -51.34% | 0.01 | 89 | 29.21% | 9.05% | -3.31% | 1.02 | 0.00% | 15.87% | 178.00 | 0.18 |
| SHORT_G | -5.03% | -29.40% | 0.09 | 0.13 | -70.99% | -0.07 | 67 | 17.91% | 14.00% | -3.26% | 0.79 | 0.00% | 44.86% | 134.00 | 0.10 |
| SHORT_B | -5.70% | -32.72% | 0.05 | 0.08 | -68.66% | -0.08 | 137 | 24.82% | 6.08% | -2.19% | 0.81 | 0.00% | 36.65% | 274.00 | 0.20 |
| SHORT_D | -7.42% | -40.55% | -0.06 | -0.08 | -72.76% | -0.10 | 74 | 33.78% | 8.17% | -4.73% | 0.77 | 0.00% | 22.79% | 148.00 | 0.11 |
| SHORT_A | -11.80% | -57.14% | -0.08 | -0.11 | -81.87% | -0.14 | 209 | 12.92% | 8.95% | -1.65% | 0.67 | 0.00% | 45.88% | 418.00 | 0.24 |
| SHORT_E | -14.70% | -65.81% | -0.25 | -0.37 | -80.14% | -0.18 | 268 | 17.91% | 5.49% | -1.57% | 0.72 | 0.00% | 29.67% | 536.00 | 0.35 |
| SHORT_F | -19.38% | -76.63% | -0.32 | -0.46 | -81.33% | -0.24 | 89 | 22.47% | 5.22% | -3.06% | 0.25 | 0.00% | 42.47% | 178.00 | 0.06 |

## TRAIN

| Sistema | CAGR | Retorno | Sharpe | Sortino | Max DD | Calmar | Trades | Win | Avg win | Avg loss | PF | % LONG | % SHORT | Turnover | Coste / equity inicial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMBO_B_0.25 | 39.36% | 170.72% | 0.91 | 1.33 | -53.49% | 0.74 | 160 | 18.12% | 11.33% | -1.38% | 1.36 | 51.86% | 40.43% | 225.50 | 0.55 |
| COMBO_F_0.25 | 39.04% | 168.88% | 0.91 | 1.32 | -51.46% | 0.76 | 156 | 18.59% | 11.16% | -1.40% | 1.37 | 51.86% | 30.63% | 223.75 | 0.54 |
| COMBO_D_0.25 | 38.86% | 167.80% | 0.91 | 1.32 | -57.16% | 0.68 | 143 | 18.88% | 12.21% | -1.58% | 1.35 | 51.86% | 22.69% | 217.00 | 0.53 |
| COMBO_G_0.25 | 39.06% | 168.96% | 0.91 | 1.32 | -52.44% | 0.74 | 160 | 16.25% | 12.59% | -1.35% | 1.35 | 51.86% | 43.95% | 225.75 | 0.56 |
| COMBO_C_0.25 | 38.60% | 166.28% | 0.90 | 1.32 | -54.30% | 0.71 | 151 | 19.21% | 11.45% | -1.53% | 1.32 | 51.86% | 17.88% | 221.00 | 0.56 |
| COMBO_D_0.50 | 39.35% | 170.64% | 0.89 | 1.30 | -61.77% | 0.64 | 143 | 18.88% | 13.49% | -1.84% | 1.32 | 51.86% | 22.69% | 240.00 | 0.57 |
| COMBO_F_0.50 | 39.53% | 171.72% | 0.89 | 1.29 | -51.01% | 0.77 | 156 | 17.95% | 12.57% | -1.58% | 1.35 | 51.86% | 30.63% | 253.50 | 0.59 |
| COMBO_C_0.50 | 38.99% | 168.59% | 0.89 | 1.30 | -56.42% | 0.69 | 151 | 19.21% | 12.75% | -1.80% | 1.27 | 51.86% | 17.88% | 248.00 | 0.65 |
| V8_LONG_FLAT | 36.79% | 156.02% | 0.89 | 1.29 | -52.50% | 0.70 | 97 | 14.43% | 20.99% | -1.85% | 1.38 | 51.86% | 0.00% | 194.00 | 0.47 |
| COMBO_A_0.25 | 37.59% | 160.50% | 0.88 | 1.29 | -58.41% | 0.64 | 194 | 15.46% | 11.21% | -1.18% | 1.34 | 51.86% | 48.14% | 242.75 | 0.55 |
| COMBO_B_0.50 | 39.72% | 172.82% | 0.88 | 1.29 | -55.11% | 0.72 | 160 | 18.12% | 12.44% | -1.60% | 1.33 | 51.86% | 40.43% | 257.00 | 0.60 |
| COMBO_G_0.50 | 39.05% | 168.89% | 0.87 | 1.28 | -53.09% | 0.74 | 160 | 16.25% | 13.79% | -1.56% | 1.31 | 51.86% | 43.95% | 257.50 | 0.62 |
| COMBO_E_0.25 | 36.17% | 152.55% | 0.87 | 1.26 | -52.64% | 0.69 | 218 | 16.97% | 9.06% | -1.08% | 1.29 | 51.86% | 32.15% | 254.75 | 0.64 |
| COMBO_A_0.50 | 35.88% | 150.93% | 0.83 | 1.21 | -64.23% | 0.56 | 194 | 14.95% | 12.98% | -1.42% | 1.29 | 51.86% | 48.14% | 291.50 | 0.60 |
| COMBO_E_0.50 | 33.75% | 139.32% | 0.81 | 1.18 | -53.30% | 0.63 | 218 | 16.97% | 10.15% | -1.32% | 1.21 | 51.86% | 32.15% | 315.50 | 0.80 |
| COMBO_C_1.00 | 35.63% | 149.54% | 0.80 | 1.18 | -61.36% | 0.58 | 151 | 18.54% | 15.79% | -2.34% | 1.19 | 51.86% | 17.88% | 302.00 | 0.77 |
| COMBO_D_1.00 | 35.64% | 149.61% | 0.79 | 1.18 | -70.49% | 0.51 | 143 | 18.18% | 16.52% | -2.36% | 1.24 | 51.86% | 22.69% | 286.00 | 0.61 |
| COMBO_F_1.00 | 35.24% | 147.41% | 0.79 | 1.15 | -51.69% | 0.68 | 156 | 17.95% | 14.43% | -1.99% | 1.28 | 51.86% | 30.63% | 313.00 | 0.64 |
| COMBO_B_1.00 | 33.92% | 140.21% | 0.76 | 1.13 | -59.96% | 0.57 | 160 | 18.12% | 14.38% | -2.05% | 1.25 | 51.86% | 40.43% | 320.00 | 0.64 |
| COMBO_G_1.00 | 32.36% | 131.92% | 0.75 | 1.10 | -56.16% | 0.58 | 160 | 16.25% | 15.84% | -2.00% | 1.22 | 51.86% | 43.95% | 321.00 | 0.68 |
| COMBO_A_1.00 | 25.50% | 97.70% | 0.67 | 0.99 | -74.84% | 0.34 | 194 | 14.95% | 15.45% | -1.92% | 1.18 | 51.86% | 48.14% | 389.00 | 0.60 |
| COMBO_E_1.00 | 24.01% | 90.72% | 0.65 | 0.97 | -59.63% | 0.40 | 218 | 16.51% | 12.56% | -1.80% | 1.11 | 51.86% | 32.15% | 437.00 | 1.01 |
| SHORT_C | 1.40% | 4.27% | 0.23 | 0.36 | -51.34% | 0.03 | 45 | 28.89% | 11.30% | -3.94% | 1.03 | 0.00% | 18.11% | 90.00 | 0.09 |
| SHORT_G | -2.85% | -8.31% | 0.21 | 0.31 | -60.39% | -0.05 | 27 | 22.22% | 16.87% | -4.46% | 0.89 | 0.00% | 50.09% | 55.00 | 0.05 |
| SHORT_B | -2.10% | -6.17% | 0.21 | 0.32 | -64.90% | -0.03 | 63 | 23.81% | 8.21% | -2.40% | 0.93 | 0.00% | 40.43% | 126.00 | 0.10 |
| SHORT_A | -8.25% | -22.76% | 0.11 | 0.16 | -79.05% | -0.10 | 97 | 15.46% | 10.29% | -2.00% | 0.77 | 0.00% | 48.14% | 195.00 | 0.13 |
| SHORT_D | -6.20% | -17.48% | 0.07 | 0.11 | -66.05% | -0.09 | 33 | 36.36% | 11.31% | -6.53% | 0.85 | 0.00% | 23.75% | 66.00 | 0.05 |
| SHORT_E | -12.15% | -32.21% | -0.05 | -0.07 | -64.15% | -0.19 | 121 | 19.01% | 6.92% | -1.87% | 0.79 | 0.00% | 32.97% | 243.00 | 0.21 |
| SHORT_F | -25.45% | -58.58% | -0.31 | -0.44 | -75.97% | -0.34 | 38 | 18.42% | 9.32% | -4.39% | 0.21 | 0.00% | 46.90% | 77.00 | 0.03 |

## TEST 2023–2026

| Sistema | CAGR | Retorno | Sharpe | Sortino | Max DD | Calmar | Trades | Win | Avg win | Avg loss | PF | % LONG | % SHORT | Turnover | Coste / equity inicial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMBO_C_0.25 | 36.35% | 219.80% | 1.11 | 1.64 | -33.09% | 1.10 | 155 | 18.71% | 9.41% | -1.14% | 1.44 | 55.93% | 14.02% | 245.00 | 1.49 |
| V8_LONG_FLAT | 35.55% | 212.79% | 1.10 | 1.63 | -33.14% | 1.07 | 111 | 13.51% | 16.73% | -1.30% | 1.50 | 55.93% | 0.00% | 223.00 | 1.30 |
| COMBO_C_0.50 | 36.78% | 223.58% | 1.09 | 1.62 | -34.68% | 1.06 | 155 | 18.71% | 10.17% | -1.30% | 1.40 | 55.93% | 14.02% | 267.00 | 1.63 |
| COMBO_F_0.25 | 35.01% | 208.21% | 1.07 | 1.59 | -30.47% | 1.15 | 176 | 15.34% | 9.89% | -0.95% | 1.44 | 55.93% | 25.30% | 255.75 | 1.51 |
| COMBO_G_0.25 | 33.87% | 198.54% | 1.04 | 1.54 | -30.88% | 1.10 | 178 | 14.04% | 10.87% | -0.97% | 1.41 | 55.93% | 36.87% | 256.75 | 1.47 |
| COMBO_B_0.25 | 33.61% | 196.40% | 1.04 | 1.54 | -32.54% | 1.03 | 185 | 18.38% | 8.03% | -1.00% | 1.40 | 55.93% | 33.61% | 260.00 | 1.49 |
| COMBO_D_0.25 | 32.33% | 185.89% | 1.01 | 1.50 | -37.07% | 0.87 | 168 | 17.86% | 8.95% | -1.09% | 1.37 | 55.93% | 21.08% | 251.50 | 1.42 |
| COMBO_F_0.50 | 33.93% | 199.06% | 1.01 | 1.50 | -29.46% | 1.15 | 176 | 15.34% | 10.48% | -1.06% | 1.39 | 55.93% | 25.30% | 288.50 | 1.65 |
| COMBO_C_1.00 | 36.50% | 221.11% | 1.00 | 1.49 | -38.75% | 0.94 | 155 | 18.06% | 12.12% | -1.61% | 1.32 | 55.93% | 14.02% | 311.00 | 1.72 |
| COMBO_A_0.25 | 31.56% | 179.69% | 0.99 | 1.46 | -32.54% | 0.97 | 222 | 12.16% | 10.14% | -0.81% | 1.36 | 55.93% | 44.07% | 278.75 | 1.47 |
| COMBO_E_0.25 | 30.53% | 171.56% | 0.97 | 1.44 | -38.77% | 0.79 | 256 | 15.23% | 7.10% | -0.76% | 1.31 | 55.93% | 26.54% | 295.75 | 1.58 |
| COMBO_G_0.50 | 31.47% | 178.95% | 0.94 | 1.39 | -31.93% | 0.99 | 178 | 14.04% | 11.67% | -1.14% | 1.34 | 55.93% | 36.87% | 290.50 | 1.53 |
| COMBO_B_0.50 | 31.02% | 175.43% | 0.94 | 1.38 | -33.91% | 0.91 | 185 | 18.38% | 8.66% | -1.19% | 1.32 | 55.93% | 33.61% | 297.00 | 1.59 |
| COMBO_D_0.50 | 28.75% | 157.94% | 0.90 | 1.34 | -42.29% | 0.68 | 168 | 17.86% | 9.52% | -1.28% | 1.28 | 55.93% | 21.08% | 280.00 | 1.46 |
| COMBO_F_1.00 | 30.18% | 168.86% | 0.84 | 1.24 | -32.46% | 0.93 | 176 | 15.34% | 11.58% | -1.30% | 1.29 | 55.93% | 25.30% | 354.00 | 1.67 |
| COMBO_A_0.50 | 26.89% | 144.25% | 0.84 | 1.23 | -33.83% | 0.79 | 222 | 12.16% | 10.96% | -0.98% | 1.26 | 55.93% | 44.07% | 334.50 | 1.49 |
| COMBO_E_0.50 | 25.18% | 132.09% | 0.82 | 1.20 | -44.47% | 0.57 | 256 | 15.23% | 7.75% | -0.94% | 1.20 | 55.93% | 26.54% | 368.50 | 1.71 |
| COMBO_G_1.00 | 24.65% | 128.46% | 0.72 | 1.05 | -38.18% | 0.65 | 178 | 14.04% | 13.22% | -1.48% | 1.21 | 55.93% | 36.87% | 358.00 | 1.34 |
| COMBO_B_1.00 | 24.04% | 124.26% | 0.71 | 1.04 | -38.45% | 0.63 | 185 | 18.38% | 9.84% | -1.56% | 1.19 | 55.93% | 33.61% | 371.00 | 1.44 |
| COMBO_D_1.00 | 20.62% | 101.96% | 0.67 | 0.98 | -52.46% | 0.39 | 168 | 17.86% | 10.65% | -1.67% | 1.14 | 55.93% | 21.08% | 337.00 | 1.36 |
| COMBO_A_1.00 | 15.84% | 73.53% | 0.55 | 0.80 | -42.73% | 0.37 | 222 | 12.16% | 12.53% | -1.34% | 1.10 | 55.93% | 44.07% | 446.00 | 1.18 |
| COMBO_E_1.00 | 13.68% | 61.74% | 0.52 | 0.75 | -55.67% | 0.25 | 256 | 15.23% | 9.04% | -1.31% | 1.05 | 55.93% | 26.54% | 514.00 | 1.56 |
| SHORT_C | -0.07% | -0.25% | 0.10 | 0.15 | -31.76% | -0.00 | 44 | 29.55% | 6.80% | -2.66% | 1.00 | 0.00% | 14.07% | 88.00 | 0.09 |
| SHORT_G | -6.73% | -23.00% | -0.07 | -0.10 | -52.34% | -0.13 | 39 | 15.38% | 11.13% | -2.56% | 0.67 | 0.00% | 40.67% | 79.00 | 0.05 |
| SHORT_B | -8.49% | -28.30% | -0.16 | -0.23 | -51.15% | -0.17 | 74 | 25.68% | 4.41% | -2.01% | 0.66 | 0.00% | 33.61% | 148.00 | 0.10 |
| SHORT_D | -8.37% | -27.96% | -0.25 | -0.35 | -54.29% | -0.15 | 41 | 31.71% | 5.26% | -3.39% | 0.62 | 0.00% | 22.02% | 82.00 | 0.05 |
| SHORT_A | -14.54% | -44.51% | -0.34 | -0.48 | -59.59% | -0.24 | 111 | 10.81% | 7.28% | -1.38% | 0.52 | 0.00% | 44.07% | 223.00 | 0.11 |
| SHORT_F | -14.16% | -43.58% | -0.38 | -0.54 | -53.49% | -0.26 | 50 | 26.00% | 3.02% | -2.01% | 0.40 | 0.00% | 38.92% | 101.00 | 0.03 |
| SHORT_E | -16.69% | -49.56% | -0.57 | -0.81 | -55.76% | -0.30 | 146 | 16.44% | 4.30% | -1.34% | 0.56 | 0.00% | 27.03% | 293.00 | 0.14 |

## Años 2021–2026 YTD

| Sistema | 2021 | 2022 bear | 2023 | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|
| COMBO_C_0.25 | -2.21% | -23.22% | 84.40% | 73.70% | -17.01% | 20.30% |
| V8_LONG_FLAT | 3.99% | -27.54% | 86.06% | 70.04% | -14.16% | 15.17% |
| COMBO_C_0.50 | -9.03% | -19.48% | 82.57% | 76.88% | -20.07% | 25.36% |
| COMBO_F_0.25 | 6.25% | -19.19% | 78.89% | 67.56% | -12.25% | 17.18% |
| COMBO_G_0.25 | 4.73% | -22.57% | 80.16% | 62.37% | -15.42% | 20.67% |
| COMBO_B_0.25 | 2.36% | -20.00% | 79.36% | 64.20% | -15.47% | 19.06% |
| COMBO_D_0.25 | -2.31% | -19.77% | 82.14% | 63.37% | -21.15% | 21.84% |
| COMBO_F_0.50 | 7.22% | -11.41% | 71.90% | 64.49% | -10.88% | 18.68% |
| COMBO_C_1.00 | -23.83% | -14.15% | 78.39% | 81.73% | -26.71% | 35.14% |
| COMBO_A_0.25 | -4.88% | -16.50% | 73.81% | 61.14% | -16.68% | 19.84% |
| COMBO_E_0.25 | 6.75% | -31.11% | 82.03% | 64.13% | -22.46% | 17.22% |
| COMBO_G_0.50 | 3.42% | -18.68% | 73.95% | 54.12% | -17.32% | 25.85% |
| COMBO_B_0.50 | -1.19% | -13.06% | 72.40% | 57.73% | -17.37% | 22.59% |
| COMBO_D_0.50 | -9.41% | -12.18% | 78.01% | 56.34% | -27.87% | 28.51% |
| COMBO_F_1.00 | 5.23% | 1.14% | 58.48% | 56.73% | -9.86% | 20.09% |
| COMBO_A_0.50 | -15.00% | -5.48% | 61.83% | 51.62% | -19.79% | 24.11% |
| COMBO_E_0.50 | 7.89% | -35.40% | 77.74% | 57.80% | -30.36% | 18.83% |
| COMBO_G_1.00 | -4.88% | -14.80% | 60.78% | 36.37% | -22.86% | 35.09% |
| COMBO_B_1.00 | -13.16% | -2.06% | 57.88% | 43.25% | -22.76% | 28.37% |
| COMBO_D_1.00 | -25.07% | 1.58% | 69.19% | 41.45% | -40.42% | 41.65% |
| COMBO_A_1.00 | -36.74% | 14.76% | 38.89% | 31.36% | -27.52% | 31.22% |
| COMBO_E_1.00 | 5.25% | -45.53% | 68.48% | 44.14% | -44.81% | 20.68% |
| SHORT_C | -25.16% | 20.91% | -4.12% | 6.88% | -17.04% | 17.34% |
| SHORT_G | 6.54% | 3.73% | -9.49% | -25.96% | -0.08% | 14.99% |
| SHORT_B | -16.49% | 35.17% | -15.14% | -15.75% | -10.01% | 11.46% |
| SHORT_D | -34.61% | 34.42% | -7.81% | -13.03% | -28.08% | 24.93% |
| SHORT_A | -39.16% | 58.39% | -25.35% | -22.74% | -15.56% | 13.94% |
| SHORT_F | -15.66% | 42.81% | -28.14% | -22.38% | 5.03% | -3.71% |
| SHORT_E | 1.83% | -26.56% | -8.07% | -15.23% | -36.00% | 1.14% |

## Vecindarios pequeños — candidatos TRAIN

| Candidato | Variante | SHORT x | CAGR total | Sharpe total | DD total | CAGR TEST | Sharpe TEST | DD TEST | SHORT aislado retorno TEST |
|---|---|---|---|---|---|---|---|---|---|
| F | F_504_plus_sma_slope_5 | 0.25 | 36.35% | 0.96 | -51.46% | 34.59% | 1.06 | -31.98% | -14.25% |
| F | F_504_plus_sma_slope_5 | 0.5 | 35.58% | 0.91 | -51.01% | 33.16% | 1.00 | -31.50% | -14.25% |
| F | F_504_plus_sma_slope_5 | 1.0 | 31.10% | 0.77 | -51.80% | 28.91% | 0.83 | -33.35% | -14.25% |
| F | F_504_plus_sma_slope_10 | 0.25 | 35.92% | 0.95 | -51.60% | 34.92% | 1.07 | -30.80% | -17.62% |
| F | F_504_plus_sma_slope_10 | 0.5 | 34.74% | 0.90 | -51.28% | 33.81% | 1.01 | -29.38% | -17.62% |
| F | F_504_plus_sma_slope_10 | 1.0 | 29.49% | 0.75 | -52.36% | 30.17% | 0.85 | -32.58% | -17.62% |
| F | F_504_plus_sma_slope_20 | 0.25 | 36.75% | 0.96 | -51.46% | 35.32% | 1.08 | -30.11% | -9.12% |
| F | F_504_plus_sma_slope_20 | 0.5 | 36.39% | 0.92 | -51.01% | 34.60% | 1.03 | -29.11% | -9.12% |
| F | F_504_plus_sma_slope_20 | 1.0 | 32.72% | 0.80 | -51.69% | 31.73% | 0.88 | -33.87% | -9.12% |
| C | C_donchian_15_7 | 0.25 | 35.01% | 0.93 | -56.20% | 36.04% | 1.10 | -32.58% | -5.62% |
| C | C_donchian_15_7 | 0.5 | 33.16% | 0.88 | -59.90% | 36.18% | 1.07 | -34.14% | -5.62% |
| C | C_donchian_15_7 | 1.0 | 27.36% | 0.73 | -74.41% | 35.35% | 0.98 | -40.46% | -5.62% |
| C | C_donchian_20_10 | 0.25 | 37.34% | 0.98 | -54.30% | 36.35% | 1.11 | -33.09% | -0.25% |
| C | C_donchian_20_10 | 0.5 | 37.76% | 0.95 | -56.42% | 36.78% | 1.09 | -34.68% | -0.25% |
| C | C_donchian_20_10 | 1.0 | 36.11% | 0.86 | -61.36% | 36.50% | 1.00 | -38.75% | -0.25% |
| C | C_donchian_30_15 | 0.25 | 34.66% | 0.93 | -55.09% | 33.75% | 1.05 | -35.43% | -26.02% |
| C | C_donchian_30_15 | 0.5 | 32.41% | 0.86 | -57.90% | 31.60% | 0.97 | -39.16% | -26.02% |
| C | C_donchian_30_15 | 1.0 | 25.66% | 0.70 | -63.91% | 26.33% | 0.79 | -46.84% | -26.02% |
| C | C_donchian_55_20 | 0.25 | 36.01% | 0.95 | -55.86% | 33.21% | 1.04 | -33.65% | -28.21% |
| C | C_donchian_55_20 | 0.5 | 35.10% | 0.91 | -59.34% | 30.57% | 0.95 | -35.72% | -28.21% |
| C | C_donchian_55_20 | 1.0 | 30.92% | 0.78 | -66.40% | 24.42% | 0.76 | -40.55% | -28.21% |
| C | C_slope_5 | 0.25 | 36.70% | 0.96 | -55.03% | 35.61% | 1.09 | -33.79% | -8.17% |
| C | C_slope_5 | 0.5 | 36.46% | 0.93 | -57.80% | 35.29% | 1.05 | -36.05% | -8.17% |
| C | C_slope_5 | 1.0 | 33.49% | 0.82 | -63.79% | 33.52% | 0.94 | -41.33% | -8.17% |
| C | C_slope_20 | 0.25 | 36.20% | 0.96 | -54.30% | 32.97% | 1.03 | -36.22% | -31.05% |
| C | C_slope_20 | 0.5 | 35.51% | 0.92 | -56.42% | 30.11% | 0.94 | -40.62% | -31.05% |
| C | C_slope_20 | 1.0 | 31.87% | 0.80 | -61.36% | 23.65% | 0.75 | -49.32% | -31.05% |

## Sensibilidad funding y mercado perpetual

| Sistema | CAGR sin fund | Retorno TEST sin fund | CAGR +extra SHORT 10% APR | Retorno TEST +10% | CAGR +extra SHORT 25% APR | Retorno TEST +25% | CAGR perp+fund real | Retorno TEST perp+fund real |
|---|---|---|---|---|---|---|---|---|
| V8_LONG_FLAT | 49.57% | 279.50% | 36.10% | 212.79% | 36.10% | 212.79% | 36.10% | 212.79% |
| SHORT_A | -13.79% | -48.69% | -15.75% | -52.96% | -21.35% | -63.29% | -11.80% | -44.51% |
| COMBO_A_0.25 | 46.65% | 232.76% | 32.68% | 168.37% | 30.41% | 152.24% | 34.21% | 179.69% |
| COMBO_A_0.50 | 42.13% | 184.97% | 27.84% | 124.88% | 23.52% | 98.67% | 30.81% | 144.25% |
| COMBO_A_1.00 | 28.93% | 94.69% | 14.65% | 47.10% | 7.03% | 14.81% | 20.04% | 73.53% |
| SHORT_B | -7.21% | -32.31% | -9.10% | -36.79% | -13.96% | -47.68% | -5.70% | -28.30% |
| COMBO_B_0.25 | 49.02% | 254.47% | 34.90% | 187.21% | 33.06% | 173.95% | 36.14% | 196.40% |
| COMBO_B_0.50 | 46.98% | 224.68% | 32.37% | 158.61% | 28.78% | 135.28% | 34.82% | 175.43% |
| COMBO_B_1.00 | 38.79% | 156.84% | 23.72% | 97.70% | 17.10% | 63.64% | 28.33% | 124.26% |
| SHORT_C | 0.10% | -2.50% | -1.00% | -5.37% | -3.33% | -12.57% | 0.59% | -0.25% |
| COMBO_C_0.25 | 50.77% | 285.81% | 36.80% | 215.63% | 36.00% | 209.47% | 37.34% | 219.80% |
| COMBO_C_0.50 | 51.05% | 288.15% | 36.68% | 215.19% | 35.07% | 203.00% | 37.76% | 223.58% |
| COMBO_C_1.00 | 48.90% | 280.82% | 33.98% | 204.66% | 30.86% | 181.56% | 36.11% | 221.11% |
| SHORT_D | -8.32% | -30.74% | -9.50% | -33.67% | -12.54% | -41.39% | -7.42% | -27.96% |
| COMBO_D_0.25 | 48.24% | 243.58% | 34.46% | 180.30% | 33.37% | 172.11% | 35.20% | 185.89% |
| COMBO_D_0.50 | 45.89% | 207.05% | 31.91% | 147.94% | 29.77% | 133.67% | 33.36% | 157.94% |
| COMBO_D_1.00 | 38.39% | 135.88% | 24.34% | 86.61% | 20.34% | 65.74% | 27.08% | 101.96% |
| SHORT_E | -15.66% | -51.74% | -17.19% | -54.42% | -20.80% | -60.85% | -14.70% | -49.56% |
| COMBO_E_0.25 | 45.77% | 225.88% | 32.05% | 164.88% | 30.62% | 155.18% | 33.01% | 171.56% |
| COMBO_E_0.50 | 40.89% | 175.49% | 27.06% | 120.82% | 24.32% | 104.94% | 28.92% | 132.09% |
| COMBO_E_1.00 | 28.41% | 87.82% | 14.78% | 46.42% | 9.89% | 26.11% | 18.16% | 61.74% |
| SHORT_F | -20.54% | -46.04% | -22.73% | -51.24% | -27.50% | -60.83% | -19.38% | -43.58% |
| COMBO_F_0.25 | 50.09% | 271.05% | 35.85% | 200.98% | 34.45% | 190.46% | 36.79% | 208.21% |
| COMBO_F_0.50 | 49.41% | 257.26% | 34.52% | 185.20% | 31.76% | 165.61% | 36.39% | 199.06% |
| COMBO_F_1.00 | 44.58% | 216.25% | 28.80% | 144.53% | 23.56% | 112.09% | 32.41% | 168.86% |
| SHORT_G | -6.89% | -27.78% | -9.19% | -33.89% | -15.10% | -47.41% | -5.03% | -23.00% |
| COMBO_G_0.25 | 48.99% | 256.77% | 34.80% | 188.40% | 32.79% | 173.82% | 36.15% | 198.54% |
| COMBO_G_0.50 | 46.85% | 228.35% | 32.11% | 160.31% | 28.21% | 134.67% | 34.78% | 178.95% |
| COMBO_G_1.00 | 38.27% | 160.91% | 23.00% | 98.96% | 15.83% | 61.69% | 28.02% | 128.46% |

## Concentración y contribución SHORT

| SHORT | Retorno total aislado | Retorno TEST aislado | 2022 aislado | Mayor trade / ganancias positivas | CAGR combinado 0.25x sin mejor trade SHORT de 2022 |
|---|---|---|---|---|---|
| A | -57.14% | -44.51% | 58.39% | 16.09% | 32.62% |
| B | -32.72% | -28.30% | 35.17% | 18.58% | 34.53% |
| C | 4.02% | -0.25% | 20.91% | 13.75% | 35.74% |
| D | -40.55% | -27.96% | 34.42% | 19.65% | 33.76% |
| E | -65.81% | -49.56% | -26.56% | 16.85% | 31.45% |
| F | -76.63% | -43.58% | 42.81% | 54.61% | 35.17% |
| G | -29.40% | -23.00% | 3.73% | 29.38% | 34.54% |

## Conclusión y criterio de promoción

**C) REJECT SHORT ENGINE — las reglas A–G actuales no justifican promoción a SHADOW.**

No se rechaza la posibilidad de investigar otras hipótesis bajistas; se rechaza promover este conjunto con la evidencia disponible. La selección TRAIN y los parámetros base se mantienen aunque una variante haya obtenido más CAGR después de mirar TEST.

Baseline neto de turnover y funding real: CAGR **36.10%**, Sharpe **0.96**, DD **-52.50%**. Sin funding: CAGR 49.57%. Esto explica por qué no deben mezclarse simulaciones de precio con resultados de perpetual financiado.

El espejo A a 0.25x reduce CAGR a 34.21%, Sharpe a 0.91 y DD a -58.41%; por tanto no aporta una mejora robusta.

C 20/10 con slope 10, combinado 0.25x, es el caso más cercano: CAGR 37.34%, Sharpe 0.98, DD -54.30%. SHORT_C aislado solo devuelve 4.02% acumulado y -0.25% en TEST. El combinado TEST pasa de CAGR 35.55% a 36.35%; Sharpe de 1.10 a 1.11. Es una ventaja pequeña, no un ganador por CAGR.

Bootstrap pareado TEST, 1.000 muestras y bloques fijos de siete días: crecimiento anual relativo C/baseline 0.59%, IC95% [-3.96%, 5.73%]; frecuencia positiva 62.40%. El intervalo incluye cero: no demuestra una contribución robusta. Es un diagnóstico condicional sobre el mismo TEST, no otro periodo independiente ni corrección completa por múltiples pruebas.

Vecinos C a 0.25x: 3/6 superan el CAGR TEST del baseline; 0/6 SHORT aislados son positivos en TEST. No se escoge retrospectivamente el vecino más favorable.

Quitando el mejor trade SHORT de 2022 del combinado C, CAGR 35.74% y Sharpe 0.95, frente a 36.10% y 0.96 del baseline: la ventaja de CAGR desaparece. SHORT_C gana 20.91% en 2022, pero eso no basta para el TEST posterior.

F fue primero en la selección TRAIN conservadora, pero su SHORT aislado pierde -76.63% acumulado. El combinado F 0.25x tiene CAGR TEST 35.01% frente a 35.55%; DD TEST -30.47% frente a -33.14%. La reducción de drawdown no demuestra una contribución positiva suficiente para compensar menor rentabilidad y Sharpe. Los filtros slope son sensibilidad estructural, no validación de vecinos del momentum 504.

Con funding adverso ADICIONAL de 25% APR sobre SHORT, C 0.25x queda en CAGR 36.00% y CAGR TEST 35.16%. La ventaja tampoco es estable ante ese estrés; no se trata de una predicción de funding futuro.

Los seis requisitos no se cumplen conjuntamente: standalone/contribución marginal, mejora combinada pequeña con DD global peor, TEST no concluyente, vecinos débiles y dependencia de una operación de 2022 para el incremento de CAGR. El requisito de no usar leverage alto sí se cumple: todo <=1x. No se añade código SHADOW nuevo ni ejecución SHORT, y no se promociona ningún parámetro.


## Reproducibilidad

```sh
python -m research.v8_bear_backtest
python -m unittest discover -s research -p 'test_*.py' -v
```

Resultados íntegros, métricas por segmento/año y sensibilidades en artifacts/results.json y metrics.csv. Ledger de trades del principal en artifacts/trades.csv.gz. Datos congelados y SHA256 en data_manifest.json. Los reruns usan snapshots locales; --download consulta exclusivamente endpoints públicos. La conclusión editorial pertenece exclusivamente al snapshot fechado anterior y exige nueva revisión al actualizar datos.
