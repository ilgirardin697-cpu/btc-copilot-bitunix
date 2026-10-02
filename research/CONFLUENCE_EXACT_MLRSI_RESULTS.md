# I-GOD CONFLUENCE ENGINE — segunda pasada ML RSI

**PROMISING — MORE RESEARCH**

Selección bloqueada antes de TEST: `RSI27_STATE_M_0.60_opposite_1`. Exclusivamente trigger/régimen 1H; no búsqueda de nuevos timeframes.

## Reproducción del indicador

Implementación independiente del algoritmo solicitado: RSI Wilder con semilla SMA de las primeras 14 o 27 variaciones, EMA4, últimos 3000 RSI suavizados finitos disponibles, tres centroides reinicializados p25/p50/p75 en cada cierre, asignación por distancia absoluta y actualización por media. Máximo 1000 iteraciones. GREEN estrictamente sobre el centroide alto; RED estrictamente bajo el bajo; igualdad es NEUTRAL. EVENT requiere una barra previa válida NEUTRAL y la actual GREEN/RED, excluyendo saltos directos RED↔GREEN.

La ventana contiene el RSI de la vela actual cerrada. Se recalcula en cada vela desde cero, sin warm-start ni centroides del futuro. Usamos cuatro observaciones válidas como mínimo; no exigimos 3000 para arrancar. Empates van al cluster de menor índice; los clusters vacíos conservan su centroide anterior. La partición ordenada y sumas acumuladas son equivalentes matemáticamente a asignar cada observación, con diferencias de redondeo posibles frente a Pine.

Adaptación CAUSAL rolling de BackQuant, no paridad literal con TradingView: se elimina la condición dependiente de last_bar_index y su ventana anclada al final del gráfico. La copia pública tiene arrays de tamaño 3 seguidos de push y una función ma ausente; no se ejecutan esas anomalías. La página oficial confirma el método, pero no hemos validado una exportación numérica del indicador desde TradingView. Para comprobar tu configuración concreta faltan confirmación de fuente close, smooth=true/EMA, maxData=3000, maxIter=1000 y timeframe 1H; en ambos presets se asumen estos valores. No hay thresholds RSI fijos 55/45 en este experimento.

Fuentes: [BackQuant oficial](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/), [copia pública atribuida](https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html), [semántica de arrays Pine](https://www.tradingview.com/pine-script-docs/language/arrays/). No redistribuimos el Pine. Fuente de parámetros: instrucciones del usuario y copia atribuida, con las reservas anteriores.

## Diseño cerrado y contabilidad

Cuatro entradas LONG: M, RM, LM, RLM. STATE o NEUTRAL→GREEN; RSI14 o RSI27; taker 55/60/65 solo en sistemas que lo utilizan. Dos salidas: estado ML RSI contrario (y régimen invalidado cuando la entrada incorpora R), o ATR14 2x trailing. NEUTRAL no es señal contraria. SHORT únicamente RLM espejo diagnóstico, sin promoción. Las estrategias M/LM no incorporan un filtro de régimen oculto en su salida.

TRAIN 2020–2021, VALIDATION 2022–2023, TEST 2024–2026 hasta 2026-10-02 UTC. 710.208 velas cerradas 5m y 7.398 funding históricos del cache verificado del PR #4, agregadas a 59.184 velas 1H. Sin descarga ni uso de datos actuales. Taker comprador es volumen base taker buy / volumen total; vendedor es su complemento. El nuevo código conserva intactos V8, Railway, el backtest anterior y los artefactos del PR #4.

Selección LONG solamente entre variantes al 60%, con >=20 trades en TRAIN y VALIDATION y expectancy TRAIN positiva, usando Sharpe VALIDATION y desempates predefinidos. 55/65 son vecinos diagnósticos, nunca seleccionables. La selección se persiste antes de calcular métricas TEST; TEST no participa. Si no hay elegibles, se informa una combinación fija RSI14/STATE/RLM/60%/opposite como diagnóstico, sin seleccionar desde TEST.

Ejecutamos en apertura siguiente al cierre de señal. Capital 1x al entrar, cantidades fijas, sin rebalanceo ni liquidación de exchange: el funding puede hacer variar la exposición efectiva. Coste taker+slippage de 5/10/20 bps por lado, mitad fees y mitad slippage; funding firmado histórico. Stops ya conocidos al inicio de la vela y trailing actualizado al cierre para la vela siguiente; gap ejecutado conservadoramente. DD sobre equity al cierre. Los splits cierran posiciones y no comparten holdings; los indicadores sí pueden utilizar historia causal anterior al split.

Probabilidades y MFE/MAE usan todas las señales, incluso solapadas, con entrada a siguiente apertura 1H y recorrido real de velas 5m. Si ambos niveles se tocan en la misma vela 5m se cuenta primero adverso; no alcanzar el objetivo dentro del horizonte es fallo. Los recorridos no cruzan splits. Probabilidades de precio excluyen costes; métricas de trading los incluyen. Un 50% no es automáticamente el azar de BTC a horizonte finito: incluimos además un control de todas las aperturas 1H de TEST. El bootstrap de calendario conserva dependencia local, pero no corrige toda la multiplicidad de selección.

## Resultados completos por preset/sistema/modo/salida

| Preset | Modo | Sistema | Taker | Salida | L/S | CAGR ALL | Sharpe ALL | MaxDD ALL | Expectancy ALL | PF ALL | Trades ALL | Streak ALL | TEST return | TEST expectancy |
|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RSI14 | STATE | M | 60% | opposite | L | 26.29% | 0.798 | -57.59% | 0.8172% | 1.459 | 257 | 10 | 43.57% | 0.4856% |
| RSI14 | STATE | M | 60% | atr | L | -4.67% | -0.075 | -59.00% | -0.0198% | 0.977 | 636 | 17 | -35.95% | -0.1337% |
| RSI14 | STATE | RM | 60% | opposite | L | 15.85% | 0.602 | -52.36% | 0.4350% | 1.329 | 327 | 15 | 13.24% | 0.1770% |
| RSI14 | STATE | RM | 60% | atr | L | -4.40% | -0.075 | -52.86% | -0.0193% | 0.977 | 597 | 16 | -22.69% | -0.0752% |
| RSI14 | STATE | LM | 55% | opposite | L | 20.56% | 0.726 | -51.42% | 0.8657% | 1.474 | 194 | 9 | 22.92% | 0.3826% |
| RSI14 | STATE | LM | 55% | atr | L | 1.75% | 0.187 | -37.39% | 0.0621% | 1.081 | 354 | 10 | -19.78% | -0.1015% |
| RSI14 | STATE | LM | 60% | opposite | L | 19.47% | 1.054 | -37.52% | 1.9788% | 2.465 | 69 | 7 | 38.91% | 0.8824% |
| RSI14 | STATE | LM | 60% | atr | L | 5.54% | 0.706 | -15.42% | 0.4504% | 1.747 | 88 | 7 | 15.93% | 0.2645% |
| RSI14 | STATE | LM | 65% | opposite | L | 0.73% | 0.216 | -7.49% | 1.0212% | 2.523 | 5 | 1 | 5.35% | 1.3514% |
| RSI14 | STATE | LM | 65% | atr | L | 0.17% | 0.104 | -3.18% | 0.1989% | 1.497 | 6 | 2 | 0.15% | 0.0357% |
| RSI14 | STATE | RLM | 55% | opposite | L | 11.58% | 0.517 | -45.12% | 0.4882% | 1.321 | 219 | 10 | 8.78% | 0.1954% |
| RSI14 | STATE | RLM | 55% | atr | L | 2.40% | 0.226 | -32.94% | 0.0787% | 1.103 | 330 | 9 | -11.46% | -0.0514% |
| RSI14 | STATE | RLM | 60% | opposite | L | 18.78% | 1.123 | -19.16% | 2.0267% | 3.036 | 63 | 7 | 65.16% | 1.2967% |
| RSI14 | STATE | RLM | 60% | atr | L | 5.60% | 0.744 | -13.21% | 0.5104% | 1.872 | 78 | 7 | 19.59% | 0.3508% |
| RSI14 | STATE | RLM | 65% | opposite | L | 1.15% | 0.340 | -5.40% | 1.5698% | 13.861 | 5 | 1 | 8.33% | 2.0372% |
| RSI14 | STATE | RLM | 65% | atr | L | 0.17% | 0.104 | -3.18% | 0.1989% | 1.497 | 6 | 2 | 0.15% | 0.0357% |
| RSI14 | STATE | RLM | 55% | opposite | S | -7.54% | -0.093 | -67.12% | -0.1129% | 0.931 | 229 | 18 | -36.86% | -0.3738% |
| RSI14 | STATE | RLM | 55% | atr | S | -8.45% | -0.333 | -55.60% | -0.1498% | 0.835 | 333 | 18 | -31.01% | -0.2096% |
| RSI14 | STATE | RLM | 60% | opposite | S | -7.95% | -0.626 | -52.76% | -0.9022% | 0.507 | 57 | 10 | -13.99% | -0.3477% |
| RSI14 | STATE | RLM | 60% | atr | S | -2.30% | -0.338 | -25.67% | -0.2310% | 0.692 | 64 | 12 | -2.67% | -0.0480% |
| RSI14 | STATE | RLM | 65% | opposite | S | 0.08% | 0.042 | -7.51% | 0.1153% | 1.123 | 6 | 2 | 0.55% | 0.1153% |
| RSI14 | STATE | RLM | 65% | atr | S | -0.48% | -0.551 | -3.66% | -0.5433% | 0.050 | 6 | 2 | -3.22% | -0.5433% |
| RSI14 | EVENT | M | 60% | opposite | L | 26.29% | 0.798 | -57.59% | 0.8172% | 1.459 | 257 | 10 | 43.57% | 0.4856% |
| RSI14 | EVENT | M | 60% | atr | L | -2.10% | 0.021 | -57.08% | 0.0054% | 1.007 | 561 | 16 | -33.92% | -0.1408% |
| RSI14 | EVENT | RM | 60% | opposite | L | 14.70% | 0.577 | -49.60% | 0.4490% | 1.320 | 293 | 13 | 14.96% | 0.2069% |
| RSI14 | EVENT | RM | 60% | atr | L | -2.28% | -0.001 | -51.39% | 0.0011% | 1.001 | 498 | 13 | -20.70% | -0.0815% |
| RSI14 | EVENT | LM | 55% | opposite | L | 24.13% | 0.906 | -38.06% | 1.3310% | 1.786 | 132 | 6 | 25.67% | 0.5466% |
| RSI14 | EVENT | LM | 55% | atr | L | 1.93% | 0.219 | -28.60% | 0.0904% | 1.125 | 194 | 14 | -17.17% | -0.1691% |
| RSI14 | EVENT | LM | 60% | opposite | L | 9.10% | 0.822 | -20.42% | 2.3661% | 2.894 | 28 | 5 | 53.71% | 2.5474% |
| RSI14 | EVENT | LM | 60% | atr | L | 1.75% | 0.464 | -6.64% | 0.4109% | 1.896 | 30 | 7 | 9.47% | 0.4703% |
| RSI14 | EVENT | LM | 65% | opposite | L | 0.20% | 0.080 | -6.54% | 0.4939% | 1.442 | 3 | 1 | 1.63% | 0.8908% |
| RSI14 | EVENT | LM | 65% | atr | L | 0.30% | 0.212 | -2.19% | 0.6788% | 3.184 | 3 | 1 | 1.00% | 0.5108% |
| RSI14 | EVENT | RLM | 55% | opposite | L | 14.79% | 0.691 | -38.15% | 0.8713% | 1.594 | 132 | 9 | 1.63% | 0.1546% |
| RSI14 | EVENT | RLM | 55% | atr | L | 3.34% | 0.345 | -20.32% | 0.1529% | 1.214 | 174 | 19 | -8.06% | -0.0770% |
| RSI14 | EVENT | RLM | 60% | opposite | L | 6.75% | 0.685 | -14.48% | 1.9027% | 2.685 | 26 | 4 | 30.57% | 1.6679% |
| RSI14 | EVENT | RLM | 60% | atr | L | 1.77% | 0.473 | -6.43% | 0.4604% | 1.945 | 27 | 7 | 8.93% | 0.4951% |
| RSI14 | EVENT | RLM | 65% | opposite | L | 0.61% | 0.229 | -4.72% | 1.4083% | 7.923 | 3 | 1 | 4.51% | 2.2624% |
| RSI14 | EVENT | RLM | 65% | atr | L | 0.30% | 0.212 | -2.19% | 0.6788% | 3.184 | 3 | 1 | 1.00% | 0.5108% |
| RSI14 | EVENT | RLM | 55% | opposite | S | -9.92% | -0.281 | -67.83% | -0.3945% | 0.762 | 145 | 15 | -37.10% | -0.5662% |
| RSI14 | EVENT | RLM | 55% | atr | S | -4.89% | -0.319 | -43.03% | -0.1665% | 0.811 | 178 | 14 | -16.47% | -0.1840% |
| RSI14 | EVENT | RLM | 60% | opposite | S | -1.21% | -0.129 | -25.03% | -0.3290% | 0.816 | 19 | 9 | -4.12% | -0.2698% |
| RSI14 | EVENT | RLM | 60% | atr | S | -0.61% | -0.179 | -10.45% | -0.1966% | 0.744 | 19 | 9 | -1.79% | -0.1362% |
| RSI14 | EVENT | RLM | 65% | opposite | S | 0.00% | 0.000 | 0.00% | 0.0000% | NA | 0 | 0 | 0.00% | 0.0000% |
| RSI14 | EVENT | RLM | 65% | atr | S | 0.00% | 0.000 | 0.00% | 0.0000% | NA | 0 | 0 | 0.00% | 0.0000% |
| RSI27 | STATE | M | 60% | opposite | L | 25.49% | 0.805 | -44.38% | 1.3363% | 1.612 | 156 | 12 | 24.01% | 0.6734% |
| RSI27 | STATE | M | 60% | atr | L | -1.34% | 0.050 | -41.36% | 0.0154% | 1.019 | 514 | 14 | -13.09% | -0.0384% |
| RSI27 | STATE | RM | 60% | opposite | L | 16.97% | 0.640 | -46.53% | 0.7001% | 1.437 | 209 | 17 | 10.71% | 0.2341% |
| RSI27 | STATE | RM | 60% | atr | L | -1.52% | 0.041 | -41.51% | 0.0128% | 1.015 | 508 | 14 | -13.76% | -0.0420% |
| RSI27 | STATE | LM | 55% | opposite | L | 15.85% | 0.612 | -44.25% | 1.0923% | 1.487 | 133 | 10 | 10.97% | 0.5355% |
| RSI27 | STATE | LM | 55% | atr | L | 1.56% | 0.177 | -34.47% | 0.0663% | 1.084 | 300 | 10 | -12.86% | -0.0683% |
| RSI27 | STATE | LM | 60% | opposite | L | 17.63% | 0.982 | -25.66% | 2.8528% | 2.810 | 45 | 5 | 54.88% | 1.7019% |
| RSI27 | STATE | LM | 60% | atr | L | 4.41% | 0.624 | -20.59% | 0.4420% | 1.700 | 73 | 8 | 3.46% | 0.0876% |
| RSI27 | STATE | LM | 65% | opposite | L | -2.07% | -0.607 | -15.43% | -3.4500% | 0.000 | 4 | 4 | -9.17% | -4.6907% |
| RSI27 | STATE | LM | 65% | atr | L | 0.04% | 0.039 | -1.94% | 0.0766% | 1.230 | 4 | 1 | 0.19% | 0.0977% |
| RSI27 | STATE | RLM | 55% | opposite | L | 10.09% | 0.470 | -42.12% | 0.5961% | 1.339 | 162 | 8 | -2.30% | 0.1149% |
| RSI27 | STATE | RLM | 55% | atr | L | 1.01% | 0.142 | -35.10% | 0.0543% | 1.068 | 298 | 10 | -13.14% | -0.0705% |
| RSI27 | STATE | RLM | 60% | opposite | L | 11.72% | 0.761 | -26.57% | 1.5934% | 2.362 | 52 | 9 | 34.26% | 0.9086% |
| RSI27 | STATE | RLM | 60% | atr | L | 3.90% | 0.569 | -20.34% | 0.4125% | 1.639 | 70 | 8 | 3.05% | 0.0820% |
| RSI27 | STATE | RLM | 65% | opposite | L | -0.80% | -0.283 | -9.26% | -1.7952% | 0.000 | 3 | 3 | -3.85% | -1.9364% |
| RSI27 | STATE | RLM | 65% | atr | L | 0.18% | 0.140 | -1.94% | 0.4034% | 3.813 | 3 | 1 | 0.19% | 0.0977% |
| RSI27 | STATE | RLM | 55% | opposite | S | -4.44% | 0.012 | -60.21% | -0.0197% | 0.989 | 183 | 12 | -21.84% | -0.2233% |
| RSI27 | STATE | RLM | 55% | atr | S | -7.19% | -0.255 | -51.79% | -0.1318% | 0.862 | 305 | 10 | -33.39% | -0.2496% |
| RSI27 | STATE | RLM | 60% | opposite | S | -5.80% | -0.423 | -46.31% | -0.7158% | 0.594 | 50 | 12 | -3.60% | -0.0125% |
| RSI27 | STATE | RLM | 60% | atr | S | -3.08% | -0.477 | -25.97% | -0.3283% | 0.572 | 62 | 14 | -3.28% | -0.0680% |
| RSI27 | STATE | RLM | 65% | opposite | S | -0.33% | -0.087 | -9.62% | -0.3524% | 0.700 | 6 | 2 | -2.22% | -0.3524% |
| RSI27 | STATE | RLM | 65% | atr | S | -0.48% | -0.551 | -3.66% | -0.5433% | 0.050 | 6 | 2 | -3.22% | -0.5433% |
| RSI27 | EVENT | M | 60% | opposite | L | 25.47% | 0.804 | -44.38% | 1.3357% | 1.611 | 156 | 12 | 24.01% | 0.6734% |
| RSI27 | EVENT | M | 60% | atr | L | -1.29% | 0.027 | -45.70% | 0.0093% | 1.011 | 401 | 15 | -4.48% | -0.0003% |
| RSI27 | EVENT | RM | 60% | opposite | L | 14.95% | 0.588 | -47.80% | 0.6571% | 1.396 | 202 | 17 | 9.30% | 0.2298% |
| RSI27 | EVENT | RM | 60% | atr | L | -2.42% | -0.037 | -50.82% | -0.0109% | 0.987 | 391 | 15 | -6.13% | -0.0106% |
| RSI27 | EVENT | LM | 55% | opposite | L | 27.92% | 1.064 | -30.12% | 2.4490% | 2.293 | 82 | 6 | 85.40% | 2.1128% |
| RSI27 | EVENT | LM | 55% | atr | L | 2.03% | 0.245 | -16.61% | 0.1176% | 1.164 | 150 | 9 | -6.87% | -0.0808% |
| RSI27 | EVENT | LM | 60% | opposite | L | 11.70% | 0.982 | -14.05% | 4.9590% | 5.929 | 17 | 2 | 44.13% | 3.1425% |
| RSI27 | EVENT | LM | 60% | atr | L | -0.19% | -0.042 | -9.92% | -0.0497% | 0.914 | 21 | 6 | -4.11% | -0.2525% |
| RSI27 | EVENT | LM | 65% | opposite | L | -0.43% | -0.218 | -6.89% | -2.8361% | 0.000 | 1 | 1 | 0.00% | 0.0000% |
| RSI27 | EVENT | LM | 65% | atr | L | 0.15% | 0.137 | -1.52% | 1.0148% | NA | 1 | 0 | 0.00% | 0.0000% |
| RSI27 | EVENT | RLM | 55% | opposite | L | 13.91% | 0.684 | -24.89% | 1.1428% | 1.716 | 94 | 8 | 7.02% | 0.2947% |
| RSI27 | EVENT | RLM | 55% | atr | L | 1.85% | 0.230 | -17.56% | 0.1130% | 1.157 | 145 | 9 | -7.25% | -0.0872% |
| RSI27 | EVENT | RLM | 60% | opposite | L | 4.63% | 0.505 | -18.41% | 1.8223% | 2.595 | 19 | 4 | 6.16% | 0.5512% |
| RSI27 | EVENT | RLM | 60% | atr | L | -0.81% | -0.269 | -9.64% | -0.2807% | 0.562 | 19 | 6 | -4.49% | -0.2960% |
| RSI27 | EVENT | RLM | 65% | opposite | L | -0.23% | -0.115 | -5.63% | -1.5127% | 0.000 | 1 | 1 | 0.00% | 0.0000% |
| RSI27 | EVENT | RLM | 65% | atr | L | 0.15% | 0.137 | -1.52% | 1.0148% | NA | 1 | 0 | 0.00% | 0.0000% |
| RSI27 | EVENT | RLM | 55% | opposite | S | -6.68% | -0.158 | -59.35% | -0.3128% | 0.832 | 110 | 13 | -6.82% | -0.0367% |
| RSI27 | EVENT | RLM | 55% | atr | S | -2.17% | -0.112 | -30.14% | -0.0841% | 0.900 | 136 | 10 | -17.99% | -0.3184% |
| RSI27 | EVENT | RLM | 60% | opposite | S | -0.83% | -0.098 | -18.52% | -0.2466% | 0.815 | 17 | 10 | 2.31% | 0.3286% |
| RSI27 | EVENT | RLM | 60% | atr | S | -0.53% | -0.180 | -7.27% | -0.2042% | 0.653 | 17 | 6 | -2.06% | -0.1839% |
| RSI27 | EVENT | RLM | 65% | opposite | S | 0.00% | 0.000 | 0.00% | 0.0000% | NA | 0 | 0 | 0.00% | 0.0000% |
| RSI27 | EVENT | RLM | 65% | atr | S | 0.00% | 0.000 | 0.00% | 0.0000% | NA | 0 | 0 | 0.00% | 0.0000% |

## Probabilidades TEST a 24h, todas las entradas

| Preset | Modo | Sistema | Taker | L/S | n | +0.5/-0.5 | +1/-0.5 | +1/-1 | +2/-1 | +3/-1 |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| RSI14 | STATE | M | 60% | L | 2724 | 50.84% | 34.43% | 50.37% | 27.68% | 15.64% |
| RSI14 | STATE | RM | 60% | L | 2551 | 50.57% | 34.42% | 50.80% | 27.71% | 15.76% |
| RSI14 | STATE | LM | 55% | L | 477 | 52.83% | 35.22% | 50.52% | 26.21% | 15.30% |
| RSI14 | STATE | LM | 60% | L | 79 | 51.90% | 34.18% | 51.90% | 30.38% | 17.72% |
| RSI14 | STATE | LM | 65% | L | 5 | 40.00% | 40.00% | 60.00% | 60.00% | 40.00% |
| RSI14 | STATE | RLM | 55% | L | 448 | 52.68% | 35.49% | 51.12% | 26.56% | 15.85% |
| RSI14 | STATE | RLM | 60% | L | 71 | 47.89% | 30.99% | 50.70% | 30.99% | 18.31% |
| RSI14 | STATE | RLM | 65% | L | 5 | 40.00% | 40.00% | 60.00% | 60.00% | 40.00% |
| RSI14 | STATE | RLM | 55% | S | 435 | 49.43% | 34.48% | 51.95% | 30.57% | 20.00% |
| RSI14 | STATE | RLM | 60% | S | 55 | 40.00% | 30.91% | 43.64% | 21.82% | 12.73% |
| RSI14 | STATE | RLM | 65% | S | 6 | 33.33% | 33.33% | 50.00% | 0.00% | 0.00% |
| RSI14 | EVENT | M | 60% | L | 334 | 51.20% | 32.04% | 47.60% | 26.35% | 15.27% |
| RSI14 | EVENT | RM | 60% | L | 290 | 50.69% | 32.07% | 48.97% | 26.90% | 16.21% |
| RSI14 | EVENT | LM | 55% | L | 116 | 56.90% | 37.93% | 49.14% | 27.59% | 16.38% |
| RSI14 | EVENT | LM | 60% | L | 21 | 66.67% | 47.62% | 57.14% | 28.57% | 19.05% |
| RSI14 | EVENT | LM | 65% | L | 2 | 50.00% | 50.00% | 50.00% | 50.00% | 50.00% |
| RSI14 | EVENT | RLM | 55% | L | 103 | 58.25% | 38.83% | 49.51% | 29.13% | 18.45% |
| RSI14 | EVENT | RLM | 60% | L | 19 | 63.16% | 42.11% | 52.63% | 31.58% | 21.05% |
| RSI14 | EVENT | RLM | 65% | L | 2 | 50.00% | 50.00% | 50.00% | 50.00% | 50.00% |
| RSI14 | EVENT | RLM | 55% | S | 100 | 56.00% | 43.00% | 59.00% | 39.00% | 26.00% |
| RSI14 | EVENT | RLM | 60% | S | 11 | 45.45% | 36.36% | 45.45% | 27.27% | 18.18% |
| RSI14 | EVENT | RLM | 65% | S | 0 | NA | NA | NA | NA | NA |
| RSI27 | STATE | M | 60% | L | 2748 | 49.64% | 33.81% | 51.49% | 26.75% | 15.10% |
| RSI27 | STATE | RM | 60% | L | 2725 | 49.32% | 33.50% | 51.23% | 26.57% | 15.01% |
| RSI27 | STATE | LM | 55% | L | 462 | 50.43% | 34.85% | 52.16% | 25.32% | 15.58% |
| RSI27 | STATE | LM | 60% | L | 75 | 49.33% | 33.33% | 53.33% | 28.00% | 14.67% |
| RSI27 | STATE | LM | 65% | L | 2 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% |
| RSI27 | STATE | RLM | 55% | L | 460 | 50.22% | 34.57% | 51.96% | 25.43% | 15.65% |
| RSI27 | STATE | RLM | 60% | L | 73 | 47.95% | 31.51% | 52.05% | 28.77% | 15.07% |
| RSI27 | STATE | RLM | 65% | L | 2 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% |
| RSI27 | STATE | RLM | 55% | S | 470 | 51.91% | 36.17% | 53.19% | 31.06% | 21.49% |
| RSI27 | STATE | RLM | 60% | S | 62 | 45.16% | 33.87% | 50.00% | 22.58% | 14.52% |
| RSI27 | STATE | RLM | 65% | S | 7 | 28.57% | 28.57% | 57.14% | 0.00% | 0.00% |
| RSI27 | EVENT | M | 60% | L | 226 | 50.44% | 36.28% | 56.64% | 24.34% | 13.27% |
| RSI27 | EVENT | RM | 60% | L | 222 | 49.55% | 35.59% | 55.86% | 23.87% | 12.61% |
| RSI27 | EVENT | LM | 55% | L | 89 | 55.06% | 38.20% | 57.30% | 25.84% | 14.61% |
| RSI27 | EVENT | LM | 60% | L | 16 | 50.00% | 31.25% | 50.00% | 25.00% | 12.50% |
| RSI27 | EVENT | LM | 65% | L | 0 | NA | NA | NA | NA | NA |
| RSI27 | EVENT | RLM | 55% | L | 88 | 54.55% | 37.50% | 56.82% | 26.14% | 14.77% |
| RSI27 | EVENT | RLM | 60% | L | 15 | 46.67% | 26.67% | 46.67% | 26.67% | 13.33% |
| RSI27 | EVENT | RLM | 65% | L | 0 | NA | NA | NA | NA | NA |
| RSI27 | EVENT | RLM | 55% | S | 72 | 54.17% | 40.28% | 62.50% | 34.72% | 23.61% |
| RSI27 | EVENT | RLM | 60% | S | 13 | 53.85% | 46.15% | 61.54% | 30.77% | 15.38% |
| RSI27 | EVENT | RLM | 65% | S | 0 | NA | NA | NA | NA | NA |

## Comparaciones emparejadas, sin cambiar selección

| Variante | TEST CAGR | TEST Sharpe | TEST DD | TEST return | +1/-1 24h | +2/-1 24h |
|---|---:|---:|---:|---:|---:|---:|
| RSI14_STATE_M_0.60_opposite_1 | 14.05% | 0.581 | -41.74% | 43.57% | 50.37% | 27.68% |
| RSI27_STATE_M_0.60_opposite_1 | 8.13% | 0.411 | -44.38% | 24.01% | 51.49% | 26.75% |
| RSI27_STATE_RM_0.60_opposite_1 | 3.77% | 0.272 | -46.53% | 10.71% | 51.23% | 26.57% |
| RSI27_STATE_LM_0.60_opposite_1 | 17.23% | 0.864 | -25.66% | 54.88% | 53.33% | 28.00% |
| RSI27_STATE_RLM_0.55_opposite_1 | -0.84% | 0.092 | -42.12% | -2.30% | 51.96% | 25.43% |
| RSI27_STATE_RLM_0.60_opposite_1 | 11.30% | 0.676 | -26.57% | 34.26% | 52.05% | 28.77% |
| RSI27_STATE_RLM_0.65_opposite_1 | -1.42% | -0.435 | -5.55% | -3.85% | 100.00% | 100.00% |
| RSI27_EVENT_M_0.60_opposite_1 | 8.13% | 0.411 | -44.38% | 24.01% | 56.64% | 24.34% |

## Señales TEST: cinco horizontes

| Horas | n | MFE media | MAE media | +0.5/-0.5 | +1/-0.5 | +1/-1 | +2/-1 | +3/-1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2748 | 0.37% | -0.35% | 22.16% | 5.71% | 6.04% | 1.24% | 0.40% |
| 4 | 2748 | 0.77% | -0.67% | 42.21% | 20.45% | 23.76% | 7.31% | 2.66% |
| 12 | 2748 | 1.36% | -1.15% | 48.94% | 31.04% | 42.14% | 19.18% | 8.81% |
| 24 | 2748 | 1.98% | -1.67% | 49.64% | 33.81% | 51.49% | 26.75% | 15.10% |
| 48 | 2748 | 2.97% | -2.28% | 49.64% | 34.17% | 54.51% | 34.68% | 21.65% |

## Robustez del seleccionado

Sin mejor trade: 216.52%; sin tres mejores: 73.83%. Bootstrap CAGR: {'CAGR_95_interval': [-0.05862312610276509, 0.6533016756014348], 'probability_CAGR_positive': 0.946}.

Bootstrap +1% antes de -1% en 24h TEST: {'n': 2748, 'probability': 0.514919941775837, '95_interval': [0.4656289098296517, 0.5573060471619803], 'method': '500 circular 7-day calendar block resamples; overlapping signals remain dependent; no multiplicity correction'}. Control todas las horas: {'n': 24097, 'probability': 0.4609702452587459, '95_interval': [0.4421955342842919, 0.48203215207937566], 'method': '500 circular 7-day calendar block resamples; overlapping signals remain dependent; no multiplicity correction'}.

| Año | Return | Expectancy | DD |
|---|---:|---:|---:|
| 2024 | 56.97% | 2.8129% | -22.50% |
| 2025 | -18.62% | -0.6882% | -35.17% |
| 2026 | -5.27% | -0.0619% | -25.82% |

La tabla anterior son ejecuciones anuales independientes, flat en sus límites; no se debe multiplicar sus returns para reconstruir TEST.

| Año, equity continua de TEST | Return | Sharpe | DD |
|---|---:|---:|---:|
| 2024 | 56.97% | 1.535 | -22.50% |
| 2025 | -18.54% | -0.617 | -35.17% |
| 2026 | -3.02% | 0.002 | -25.83% |

| Bps/lado | ALL return | TEST return | TEST expectancy |
|---|---:|---:|---:|
| 5 | 441.22% | 32.21% | 0.7739% |
| 10 | 363.15% | 24.01% | 0.6734% |
| 20 | 239.01% | 9.07% | 0.4723% |

Gates predefinidos:

- selection_eligible: True
- TEST_positive: True
- TEST_expectancy_positive: True
- without_top1_top3: True
- taker_stability: True
- RSI14_RSI27_stability: True
- STATE_EVENT_stability: True
- 1_before_1: False
- drawdown: False
- 20bps: True

## Artefactos y reproducción

`python -m research.confluence_exact_mlrsi`; `python -m unittest discover -v`; `git diff --check`.

`exact_mlrsi_artifacts/results.json` incluye todos los splits, probabilidades de las cinco combinaciones solicitadas, MFE/MAE de cinco horizontes, vecinos, costes, años, bootstrap y eliminación de trades para cada configuración. `hourly_centroids.csv.gz` conserva RSI, los tres centroides, states/events, tamaño de ventana y timestamp de disponibilidad para ambos presets. `selection_lock.json` no contiene TEST. Reutilizamos el manifest/checksum de datos del primer PR y guardamos su hash en los resultados. No API privada, órdenes, merge ni deploy.

El seleccionado no utiliza taker: su gate de estabilidad taker es vacuo, no evidencia de liquidez/orderflow. La tabla emparejada muestra separadamente RLM con 55/60/65 y las cuatro entradas al preset/modo/salida seleccionados. No se atribuye a confluencia el rendimiento del ML RSI solo.

**Dependencia de TEST: sin su mejor operación, return -15.25%; sin sus tres mejores, -46.44%.** El gate inicial de eliminación de operaciones corresponde a ALL; esta comprobación adicional TEST tiene prioridad en la interpretación. No hay promoción.

Con ML RSI solo y salida opposite, STATE y EVENT producen el mismo P&L TEST: las señales repetidas GREEN llegan con una posición ya abierta. Sus probabilidades posteriores no son iguales porque STATE incluye cada cierre verde y EVENT solamente el cambio NEUTRAL→GREEN. No puede atribuirse una ventaja económica al evento a partir de una tasa de acierto por señal más alta; las cohortes y tamaños son diferentes. En RLM, STATE permite confirmar taker durante un tramo verde posterior, mientras EVENT exige coincidencia en la barra de transición.

STATE/EVENT también empatan en Sharpe VALIDATION en el seleccionado: STATE se informa por desempate determinista del ID, no porque haya demostrado un Sharpe superior a EVENT.

Bootstrap CAGR TEST del seleccionado: {'CAGR_95_interval': [-0.27025158792160175, 0.5804719212640469], 'probability_CAGR_positive': 0.596}.
