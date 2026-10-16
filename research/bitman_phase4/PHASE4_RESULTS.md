# BITMAN REAL — PHASE4: DIRECTIONAL CONFLUENCE

**Resultado: INCONCLUSIVE. Evidencia C; no recomendar Telegram automático con estas reglas.**

PR23 permanece **INCONCLUSIVE** e inmutable. Este resultado corresponde exclusivamente a las familias públicas/proxy aquí preregistradas; no rechaza la metodología completa ni demuestra paridad privada.

Base exacta: `ee4e59016220ec733b19a37d14429f8fdde6d348`. Versión: `BITMAN_REAL_PHASE4_V1`. Cutoff: `2026-10-15T19:00:00Z`.
Histórico público Binance USD-M perpetual: 61,723 velas 1H completas desde octubre2019 (warmup), 7,440 registros históricos de settlement funding. Datos verificados por checksum heredado. 1H/4H señales, 1D contexto causal; ningún 15m/5m/1m. No son datos privados Bitunix.

**FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR**. No hay validación forward, uso de PnL del usuario ni reconstrucción de eventos de producción.

## Lectura práctica

El caso LONG4H con separación Konkorde creciente registra TEST +59.80%, PF1.680, Sharpe0.928 y DD−25.07%, pero solo53 trades. Sin sus mejores3: −8.32% compuesto, expectancy−0.085%/trade. IC95 semanal de expectancy: −0.583% a +2.685%. Exceso de evento24h contra control: −0.288 puntos porcentuales (57 pares); no aporta ventaja de evento demostrada. Ninguno de sus vecinos es un nuevo ganador seleccionado.

En TEST quitar Konkorde a ese caso baja el retorno de59.80% a29.27%; quitar ADX/DI lo baja a32.19%, quitar BBWP a35.08%, quitar AO a53.12%. Es evidencia descriptiva incremental en este intervalo, **insuficiente**: el incremento frente C0 no fue positivo en ambos DEV y el resultado depende de pocos ganadores. El benchmark V8 conserva +66.55%, Sharpe0.732, DD−32.01%; no se ha demostrado sustitución superior.

2026 del padre LONG4H: +17.41%, PF2.037,13 trades; muy pocos casos. No se optimizó para 2026. Los SHORT diagnósticos1H/4H registran −41.90%/−16.92% en TEST. El LONG1H registra −9.85%. No existe una justificación para activar SHORT ni promocionar toda la confluencia.

## Evidencia nueva y protocolo

[SOURCES.md](SOURCES.md) separa las cuatro transcripciones primarias de las decisiones numéricas del experimento. Se realizaron cuatro llamadas vidIQ (5 créditos nominales cada una, máximo autorizado20); cargo efectivo no devuelto. No se publican las transcripciones completas ni se afirma haber verificado visualmente sus gráficos.

Protocolo y código congelados **antes** de DEV/TEST; selección de eventos bloqueada antes del chequeo neto. TRAIN2020–2021; VALIDATION2022–2023; TEST2024–cutoff **OOS reutilizado, no virgin**. Ninguna familia resultó elegible en TRAIN/VALIDATION. Los cuatro casos siguientes son fallbacks diagnósticos deterministas, **no ganadores ni candidatos promocionables**. No se hizo reranking tras ver el neto.

### Reglas exactas

Ancla AO5/34: cruce de cero o reanudación dentro del mismo signo tras reinicio genuino de pendiente. LONG: cruce `prev<=0, now>0` o pendiente `prev<=0, now>0` con AO positivo continuo. SHORT: cruce `prev>=0, now<0` o pendiente `prev>=0, now<0` con AO negativo continuo. Después del ancla, ADX14 debe girar de pendiente no positiva a positiva entre edades0..6 velas TF. DI puede alinearse posteriormente dentro de esa ventana mientras ADX sube. Al disparar, AO debe conservar signo y mejorar en esa dirección. Ancla consumida una vez antes de los filtros BBWP/K; sin señal en cada vela.

| Familia | LONG | SHORT |
|---|---|---|
| C0_IMPULSE | Secuencia AO→ADX/+DI y BBWP creciente | Secuencia AO→ADX/-DI y BBWP creciente |
| C1_BBWP50 | C0 + BBWP>=50 | C0 + BBWP>=50 |
| C2_K_CONTEXT | C0 + montaña positiva/MA dentro | C0 + EXIT reciente<=6, fuera y montaña decreciente |
| C3_K_TRANSITION | C0 + ENTRY reciente<=6, montaña positiva/dentro | C0 + EXIT en la misma vela cerrada |
| C4_K_SEPARATION | C0 + dentro de montaña positiva, separación creciente | NO IMPLEMENTADO: geometría no justificada |
| C5_K_REENTRY | C0 + REENTRY reciente<=6, salida/entrada<=3 velas | NO IMPLEMENTADO: geometría no justificada |

BBWP es el proxy congelado CLOSE/SMA7/prior100; no paridad demostrada con la volatilidad privada del vídeo. 50 es la única referencia candidata explícita; vecinos40/60 son diagnóstico, no selección. Las ventanas6/3 son hipótesis de implementación declaradas, no constantes reveladas por Bitman.

KONKORDE_PROXY no cambia: OHLC4; WilderRSI14; HLC3-MFI14; BB25/SMA/std poblacional; stochastic21/SMA3; montaña=(RSI+MFI+BollOsc+Stoch/3)/2; mediaEMA15; dentro estrictamente entre cero y montaña. ENTRY fuera→dentro; EXIT dentro→fuera. Fórmula/provenance completa: [PR23](../bitman_real/SOURCES.md). **EXACT BITMAN KONKORDE PARITY: NOT PROVEN**. RSI privado excluido; Trend Speed NOT IMPLEMENTED / FORMULA NOT VERIFIED.

Selección porTF/lado: >=30 eventos24h emparejados tanto TRAIN como VALIDATION; media direccional y exceso contra control positivos ambos. Ranking por peor exceso de ambos periodos, luego n y nombre. Control determinista no-evento emparejado por año/mes/horaUTC y signo de tendencia24 velasTF; sin elegir retornos futuros, excluyendo unión de eventos candidatos. No reemplaza un ensayo aleatorio; hay solapamiento/selección múltiple y reutilización OOS. IC bootstrap semanal500, seed6241, descriptivos.

## Estudio de eventos (antes de gestionar salidas)

Cada celda: n eventos / media direccional24h / exceso24h contra control. Brutos de mercado, sin costes; no son rentabilidad de estrategia. Horizonte incompleto censurado. SHORT reflejado correctamente.

| TF/lado/familia | TRAIN | VALIDATION | TEST |
|---|---|---|---|
| 1H_1/C0_IMPULSE | 275 / +0.56% / +0.47% | 277 / +0.20% / -0.14% | 396 / +0.13% / +0.09% |
| 1H_1/C1_BBWP50 | 174 / +0.61% / +0.38% | 169 / +0.21% / -0.27% | 229 / +0.10% / -0.01% |
| 1H_1/C2_K_CONTEXT | 256 / +0.55% / +0.43% | 256 / +0.14% / -0.22% | 364 / +0.15% / +0.10% |
| 1H_1/C3_K_TRANSITION | 187 / +0.59% / +0.19% | 181 / +0.33% / -0.16% | 243 / +0.30% / +0.22% |
| 1H_1/C4_K_SEPARATION | 172 / +0.82% / +0.92% | 163 / -0.17% / -0.34% | 248 / +0.06% / +0.08% |
| 1H_1/C5_K_REENTRY | 71 / +0.23% / +0.27% | 77 / +0.04% / -0.65% | 97 / +0.37% / +0.18% |
| 1H_-1/C0_IMPULSE | 213 / -0.43% / -0.17% | 259 / +0.03% / +0.14% | 329 / -0.01% / +0.22% |
| 1H_-1/C1_BBWP50 | 131 / -0.37% / -0.16% | 160 / -0.01% / -0.01% | 218 / -0.22% / +0.14% |
| 1H_-1/C2_K_CONTEXT | 126 / -0.56% / -0.53% | 179 / +0.03% / +0.01% | 190 / +0.06% / +0.38% |
| 1H_-1/C3_K_TRANSITION | 49 / -1.09% / -1.42% | 82 / +0.47% / +0.16% | 87 / +0.27% / +0.91% |
| 4H_1/C0_IMPULSE | 79 / -0.03% / -0.40% | 53 / +1.01% / +1.27% | 82 / +0.22% / +0.08% |
| 4H_1/C1_BBWP50 | 50 / -0.15% / -0.63% | 34 / +1.49% / +1.65% | 56 / +0.03% / -0.19% |
| 4H_1/C2_K_CONTEXT | 68 / -0.04% / -0.38% | 48 / +1.06% / +1.34% | 79 / +0.21% / +0.05% |
| 4H_1/C3_K_TRANSITION | 44 / -0.17% / -0.85% | 36 / +0.56% / +0.64% | 50 / +0.33% / +0.10% |
| 4H_1/C4_K_SEPARATION | 44 / -0.13% / +0.16% | 27 / +0.19% / +0.96% | 57 / +0.11% / -0.29% |
| 4H_1/C5_K_REENTRY | 17 / -0.62% / -1.05% | 13 / -0.39% / -0.77% | 21 / +0.98% / +0.03% |
| 4H_-1/C0_IMPULSE | 41 / -0.38% / -0.11% | 76 / -0.29% / -0.50% | 80 / -0.51% / -0.61% |
| 4H_-1/C1_BBWP50 | 27 / +0.09% / -0.21% | 42 / -0.20% / -0.69% | 49 / -0.57% / -1.43% |
| 4H_-1/C2_K_CONTEXT | 25 / +0.01% / +0.42% | 49 / -0.47% / -0.95% | 46 / -0.47% / -0.42% |
| 4H_-1/C3_K_TRANSITION | 9 / +0.95% / +2.78% | 22 / +0.09% / -0.39% | 22 / -0.26% / -0.01% |

### Selecciones diagnósticas congeladas: horizontes TEST

| Caso | h | n maduro/total | retorno medio | mediana | MFE mediana | MAE mediana | +1 antes -1 | +2 antes -2 |
|---|---|---|---|---|---|---|---|---|
| 1H_1 | 1 | 396/396 | +0.00% | -0.03% | +0.25% | -0.25% | +9.85% | +2.53% |
| 1H_1 | 4 | 396/396 | +0.03% | -0.05% | +0.42% | -0.45% | +25.51% | +7.32% |
| 1H_1 | 12 | 396/396 | +0.07% | -0.06% | +0.86% | -0.85% | +40.40% | +19.19% |
| 1H_1 | 24 | 396/396 | +0.13% | -0.14% | +1.27% | -1.15% | +48.23% | +31.82% |
| 1H_1 | 48 | 396/396 | +0.38% | +0.26% | +1.97% | -1.85% | +53.54% | +42.68% |
| 1H_1 | 72 | 396/396 | +0.44% | +0.07% | +2.39% | -2.17% | +53.54% | +46.46% |
| 1H_-1 | 1 | 218/218 | +0.04% | +0.01% | +0.39% | -0.37% | +15.14% | +4.13% |
| 1H_-1 | 4 | 218/218 | -0.03% | -0.20% | +0.64% | -0.63% | +34.86% | +14.68% |
| 1H_-1 | 12 | 218/218 | -0.12% | -0.21% | +1.15% | -1.05% | +45.87% | +27.06% |
| 1H_-1 | 24 | 218/218 | -0.22% | -0.04% | +1.50% | -1.61% | +50.92% | +35.78% |
| 1H_-1 | 48 | 217/218 | -0.21% | -0.26% | +2.10% | -2.24% | +51.15% | +43.78% |
| 1H_-1 | 72 | 217/218 | -0.43% | -0.61% | +2.52% | -2.72% | +51.15% | +46.54% |
| 4H_1 | 1 | 57/57 | +0.09% | +0.08% | +0.36% | -0.19% | +5.26% | +0.00% |
| 4H_1 | 4 | 57/57 | +0.34% | +0.27% | +0.63% | -0.40% | +33.33% | +5.26% |
| 4H_1 | 12 | 57/57 | +0.28% | +0.21% | +1.40% | -0.63% | +54.39% | +22.81% |
| 4H_1 | 24 | 57/57 | +0.11% | +0.32% | +1.67% | -1.04% | +63.16% | +33.33% |
| 4H_1 | 48 | 57/57 | +0.55% | -0.12% | +2.48% | -1.71% | +66.67% | +54.39% |
| 4H_1 | 72 | 57/57 | +1.08% | +0.90% | +2.80% | -2.05% | +66.67% | +59.65% |
| 4H_-1 | 1 | 22/22 | +0.04% | +0.01% | +0.43% | -0.20% | +9.09% | +0.00% |
| 4H_-1 | 4 | 22/22 | +0.03% | +0.02% | +0.66% | -0.46% | +22.73% | +0.00% |
| 4H_-1 | 12 | 22/22 | +0.27% | +0.15% | +1.33% | -0.77% | +45.45% | +27.27% |
| 4H_-1 | 24 | 22/22 | -0.26% | +0.56% | +2.04% | -1.36% | +54.55% | +45.45% |
| 4H_-1 | 48 | 22/22 | +0.38% | +0.30% | +2.42% | -1.92% | +54.55% | +54.55% |
| 4H_-1 | 72 | 22/22 | -0.62% | -0.20% | +2.56% | -2.27% | +54.55% | +59.09% |

Ambas barreras tocadas dentro de una misma vela1H = AMBIGUOUS, nunca victoria. UP_FIRST se divide por todos los casos maduros, incluidos no resueltos/ambiguos. Los JSON conservan también horas/alcances individuales, datos BTC sin reflejar y dirección reflejada.

### Referencias de eventos TEST

| Caso/control | n | media24h | exceso24h | IC95 exceso |
|---|---|---|---|---|
| 1H_1/AO_ADX | 944 | +0.07% | -0.07% | -0.30% / +0.16% |
| 1H_1/EMA_TREND | 299 | +0.04% | +0.06% | -0.32% / +0.40% |
| 1H_1/AO_ONLY | 1349 | +0.18% | -0.01% | -0.22% / +0.20% |
| 1H_1/KONKORDE_ENTRY | 1633 | +0.16% | +0.14% | -0.05% / +0.34% |
| 1H_-1/AO_ADX | 925 | -0.11% | -0.02% | -0.32% / +0.25% |
| 1H_-1/EMA_TREND | 300 | -0.18% | -0.02% | -0.37% / +0.36% |
| 1H_-1/AO_ONLY | 1263 | -0.11% | -0.13% | -0.34% / +0.07% |
| 4H_1/AO_ADX | 210 | +0.14% | +0.07% | -0.35% / +0.51% |
| 4H_1/EMA_TREND | 75 | -0.62% | -0.85% | -1.70% / -0.05% |
| 4H_1/AO_ONLY | 337 | +0.12% | -0.16% | -0.46% / +0.17% |
| 4H_1/KONKORDE_ENTRY | 391 | -0.06% | -0.07% | -0.36% / +0.25% |
| 4H_-1/AO_ADX | 220 | -0.08% | +0.03% | -0.42% / +0.52% |
| 4H_-1/EMA_TREND | 75 | +0.15% | +0.18% | -0.43% / +0.77% |
| 4H_-1/AO_ONLY | 306 | +0.01% | -0.07% | -0.45% / +0.27% |

## Simulación neta de las selecciones congeladas

Libro académico1x nominal al abrir, cantidad fija; LONG/SHORT separados, no sumar curvas1x. Entrada en siguiente apertura TF después del cierre conocido, slippage adverso. Stop inicial2ATR14 del TF de señal, congelado; salida en apertura tras AO contrario confirmado o máximo168h. Stops/gaps comprobados en1H, prioridad conservadora; no TP ni pirámides. Cierre forzado al final de cada split. Base: taker5bps/fill, slip2bps, stopslip5bps. Stress:6/5/10bps. Funding histórico firmado sobre cantidad fija y precio de apertura1H proxy; holdings previos al settlement antes de entrada/salida de frontera. No simulación exacta de Bitunix, margen/liquidación ni basis entre venues. Insolvencia académica queda a cero y se declara.

PF = suma de retornos porcentuales positivos por trade / abs(suma negativos), no PF monetario ponderado por equity. CAGR/Sharpe/Sortino/DD usan equity horaria marcada a mercado y anualización365.25d. Expectancy/media de trade y retorno compuesto son cantidades distintas.

| Caso/familia | Split | retorno | CAGR | Sharpe | Sortino | MaxDD | PF | n | expectancy | win | payoff |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1H_1/C0_IMPULSE | TRAIN | +98.84% | +40.98% | 1.070 | 1.597 | -33.22% | 1.404 | 185 | +0.45% | +32.97% | 2.855 |
| 1H_1/C0_IMPULSE | VALIDATION | -36.85% | -20.54% | -0.717 | -1.041 | -41.75% | 0.815 | 209 | -0.18% | +23.92% | 2.592 |
| 1H_1/C0_IMPULSE | TEST | -9.85% | -3.65% | -0.044 | -0.065 | -41.97% | 0.990 | 277 | -0.01% | +31.41% | 2.162 |
| 1H_-1/C1_BBWP50 | TRAIN | -55.81% | -33.51% | -1.327 | -1.877 | -58.13% | 0.567 | 111 | -0.68% | +26.13% | 1.603 |
| 1H_-1/C1_BBWP50 | VALIDATION | -6.16% | -3.13% | -0.004 | -0.006 | -31.34% | 1.016 | 132 | +0.02% | +28.79% | 2.514 |
| 1H_-1/C1_BBWP50 | TEST | -41.90% | -17.69% | -0.809 | -1.168 | -49.94% | 0.703 | 182 | -0.27% | +28.57% | 1.757 |
| 4H_1/C4_K_SEPARATION | TRAIN | +5.16% | +2.54% | 0.236 | 0.326 | -42.98% | 1.162 | 40 | +0.48% | +25.00% | 3.487 |
| 4H_1/C4_K_SEPARATION | VALIDATION | +14.91% | +7.20% | 0.465 | 0.701 | -20.61% | 1.414 | 27 | +0.71% | +22.22% | 4.948 |
| 4H_1/C4_K_SEPARATION | TEST | +59.80% | +18.30% | 0.928 | 1.341 | -25.07% | 1.680 | 53 | +1.07% | +35.85% | 3.006 |
| 4H_-1/C3_K_TRANSITION | TRAIN | -2.64% | -1.33% | 0.045 | 0.069 | -21.41% | 1.049 | 9 | +0.14% | +11.11% | 8.392 |
| 4H_-1/C3_K_TRANSITION | VALIDATION | -18.91% | -9.96% | -0.685 | -0.915 | -27.94% | 0.379 | 19 | -1.07% | +31.58% | 0.820 |
| 4H_-1/C3_K_TRANSITION | TEST | -16.92% | -6.43% | -0.478 | -0.664 | -24.93% | 0.618 | 21 | -0.79% | +19.05% | 2.625 |

### Benchmark común TEST

| Caso/control | retorno | Sharpe | MaxDD | PF | n | expectancy |
|---|---|---|---|---|---|---|
| 1H_1/AO_ADX | -33.82% | -0.399 | -53.45% | 0.911 | 409 | -0.07% |
| 1H_1/EMA_TREND | -30.53% | -0.481 | -38.11% | 0.866 | 292 | -0.10% |
| 1H_1/AO_ONLY | -31.16% | -0.276 | -55.67% | 0.944 | 565 | -0.04% |
| 1H_1/KONKORDE_ENTRY | -72.34% | -1.678 | -77.34% | 0.734 | 1241 | -0.10% |
| 1H_1/KONKORDE_NATIVE | -83.91% | -1.806 | -86.31% | 0.794 | 1633 | -0.10% |
| 1H_1/V8 | +66.55% | 0.732 | -32.01% | 1.849 | 84 | +0.91% |
| 1H_-1/AO_ADX | -50.54% | -0.710 | -55.68% | 0.828 | 432 | -0.14% |
| 1H_-1/EMA_TREND | -50.99% | -1.014 | -52.84% | 0.711 | 292 | -0.23% |
| 1H_-1/AO_ONLY | -60.51% | -0.902 | -64.25% | 0.806 | 560 | -0.14% |
| 4H_1/AO_ADX | +21.59% | 0.396 | -28.63% | 1.204 | 108 | +0.30% |
| 4H_1/EMA_TREND | +22.99% | 0.494 | -33.29% | 1.349 | 75 | +0.37% |
| 4H_1/AO_ONLY | -4.86% | 0.094 | -53.74% | 1.043 | 156 | +0.06% |
| 4H_1/KONKORDE_ENTRY | -34.52% | -0.541 | -62.80% | 0.844 | 316 | -0.10% |
| 4H_1/KONKORDE_NATIVE | -20.13% | -0.091 | -56.46% | 0.981 | 391 | -0.02% |
| 4H_1/V8 | +66.55% | 0.732 | -32.01% | 1.849 | 84 | +0.91% |
| 4H_-1/AO_ADX | -39.26% | -0.510 | -46.84% | 0.806 | 117 | -0.34% |
| 4H_-1/EMA_TREND | -4.61% | 0.013 | -26.53% | 0.987 | 71 | -0.01% |
| 4H_-1/AO_ONLY | -25.99% | -0.201 | -45.64% | 0.909 | 151 | -0.13% |

AO_ADX: primer estado AO con signo, ADX creciente, DI alineado. EMA_TREND: cruceEMA10/55. AO_ONLY: anclas AO. KONKORDE_ENTRY: entrada con salida común AO/stop/168h; KONKORDE_NATIVE: ENTRY/EXIT propios, mismo stop2ATR/168h. Ambos LONG exclusivamente; no se inventa SHORT aislado. V8: último4H cerrado close>SMA200 LONG/FLAT, sin stopATR/168h, mismos costes/funding. V81H/4H debe ser idéntico (comprobación de benchmark).

## Aportación incremental / ablation TEST

Eliminar AO suprime ancla/signo y usa giroADX+DI. Eliminar ADX_DI usa anclasAO sin ese filtro. Eliminar BBWP suprime subida y referencia50; eliminarK solo la geometríaK. Salidas idénticas. QuitarK a C0/C1 es **no-op**, no evidencia independiente.

| Caso/ablación | n | retorno | Sharpe | PF | expectancy |
|---|---|---|---|---|---|
| 1H_1/sin AO | 404 | -6.52% | 0.039 | 1.015 | +0.01% |
| 1H_1/sin ADX_DI | 423 | -28.43% | -0.300 | 0.931 | -0.05% |
| 1H_1/sin BBWP | 320 | -23.66% | -0.269 | 0.931 | -0.06% |
| 1H_1/sin KONKORDE | 277 | -9.85% | -0.044 | 0.990 | -0.01% |
| 1H_-1/sin AO | 325 | -65.21% | -1.392 | 0.620 | -0.31% |
| 1H_-1/sin ADX_DI | 301 | -36.13% | -0.481 | 0.855 | -0.12% |
| 1H_-1/sin BBWP | 314 | -34.18% | -0.463 | 0.863 | -0.11% |
| 1H_-1/sin KONKORDE | 182 | -41.90% | -0.809 | 0.703 | -0.27% |
| 4H_1/sin AO | 82 | +53.12% | 0.826 | 1.554 | +0.64% |
| 4H_1/sin ADX_DI | 79 | +32.19% | 0.547 | 1.342 | +0.48% |
| 4H_1/sin BBWP | 69 | +35.08% | 0.596 | 1.377 | +0.59% |
| 4H_1/sin KONKORDE | 68 | +29.27% | 0.529 | 1.318 | +0.54% |
| 4H_-1/sin AO | 40 | -29.25% | -0.819 | 0.515 | -0.81% |
| 4H_-1/sin ADX_DI | 31 | -27.74% | -0.646 | 0.527 | -0.97% |
| 4H_-1/sin BBWP | 22 | -17.17% | -0.486 | 0.613 | -0.77% |
| 4H_-1/sin KONKORDE | 66 | -38.73% | -0.698 | 0.680 | -0.64% |

## Robustez: vecinos, concentración, costes

Vecinos son diagnóstico de padres congelados, nunca se elige un nuevo ganador con TEST. Máscaras idénticas se deduplican y no cuentan como validaciones independientes. **Muestra pequeña:** LONG4H tiene53 trades y SHORT4H21; no se promocionan subgrupos pequeños.

| Caso/vecino | n | expectancy | retorno | MaxDD |
|---|---|---|---|---|
| 1H_1/{'family': 'C0_IMPULSE', 'lag': 3, 'bb_reference': 50.0, 'reentry_bars': 3} | 254 | -0.02% | -11.96% | -41.09% |
| 1H_1/{'family': 'C0_IMPULSE', 'lag': 9, 'bb_reference': 50.0, 'reentry_bars': 3} | 281 | +0.01% | -5.59% | -39.12% |
| 1H_1/stopATR=1.6 | 294 | -0.06% | -21.04% | -47.76% |
| 1H_1/stopATR=2.4 | 269 | +0.04% | +1.89% | -36.27% |
| 1H_-1/{'family': 'C1_BBWP50', 'lag': 3, 'bb_reference': 50.0, 'reentry_bars': 3} | 174 | -0.33% | -45.80% | -50.83% |
| 1H_-1/{'family': 'C1_BBWP50', 'lag': 9, 'bb_reference': 50.0, 'reentry_bars': 3} | 187 | -0.28% | -43.28% | -50.92% |
| 1H_-1/{'family': 'C1_BBWP50', 'lag': 6, 'bb_reference': 40.0, 'reentry_bars': 3} | 193 | -0.22% | -37.87% | -46.69% |
| 1H_-1/{'family': 'C1_BBWP50', 'lag': 6, 'bb_reference': 60.0, 'reentry_bars': 3} | 161 | -0.20% | -30.82% | -41.52% |
| 1H_-1/stopATR=1.6 | 187 | -0.25% | -39.55% | -46.25% |
| 1H_-1/stopATR=2.4 | 175 | -0.20% | -32.95% | -41.49% |
| 4H_1/{'family': 'C4_K_SEPARATION', 'lag': 3, 'bb_reference': 50.0, 'reentry_bars': 3} | 48 | +1.07% | +52.02% | -24.76% |
| 4H_1/{'family': 'C4_K_SEPARATION', 'lag': 9, 'bb_reference': 50.0, 'reentry_bars': 3} | 54 | +1.04% | +58.42% | -25.07% |
| 4H_1/stopATR=1.6 | 54 | +0.65% | +31.93% | -22.20% |
| 4H_1/stopATR=2.4 | 53 | +1.08% | +59.74% | -24.68% |
| 4H_-1/stopATR=1.6 | 21 | -0.47% | -10.84% | -20.56% |
| 4H_-1/stopATR=2.4 | 20 | -0.86% | -17.54% | -25.15% |

| Caso | duplicados excluidos | sin mejor: exp/ret | sin mejores3: exp/ret | IC95 expectancy | stress exp/ret | trail3ATR exp/ret |
|---|---|---|---|---|---|---|
| 1H_1 | 0 | -0.08% / -24.05% | -0.16% / -38.29% | -0.29% / +0.31% | -0.10% / -29.68% | -0.08% / -25.04% |
| 1H_-1 | 0 | -0.36% / -50.06% | -0.46% / -57.38% | -0.56% / +0.05% | -0.37% / -51.12% | -0.30% / -46.53% |
| 4H_1 | 0 | +0.67% / +30.88% | -0.09% / -8.32% | -0.58% / +2.68% | +1.00% / +53.63% | +0.51% / +25.92% |
| 4H_-1 | 2 | -1.49% / -26.49% | -2.27% / -34.00% | -2.48% / +0.87% | -0.87% / -18.24% | +0.04% / -1.16% |

Quitar trades anula sus intervalos originales, sin volver a entrar oportunistamente. El trail3ATR alternativo usa ATR de entrada congelado y se actualiza después del cierre1H para la siguiente vela; diagnóstico no seleccionado y no rescata el modelo primario.

| Caso | fee/fill bps | retorno | expectancy | fees equity inicial | slippage | funding firmado | turnover |
|---|---|---|---|---|---|---|---|
| 1H_1 | 5 | -9.85% | -0.01% | 0.278 | 0.152 | 0.059 | 556.878 |
| 1H_1 | 10 | -31.69% | -0.11% | 0.488 | 0.133 | 0.053 | 487.904 |
| 1H_1 | 20 | -60.81% | -0.31% | 0.762 | 0.104 | 0.045 | 381.115 |
| 1H_-1 | 5 | -41.90% | -0.27% | 0.127 | 0.069 | -0.021 | 253.360 |
| 1H_-1 | 10 | -51.61% | -0.37% | 0.234 | 0.064 | -0.019 | 233.890 |
| 1H_-1 | 20 | -66.46% | -0.57% | 0.402 | 0.055 | -0.017 | 200.938 |
| 4H_1 | 5 | +59.80% | +1.07% | 0.069 | 0.039 | 0.066 | 138.486 |
| 4H_1 | 10 | +51.57% | +0.97% | 0.135 | 0.038 | 0.065 | 134.811 |
| 4H_1 | 20 | +36.34% | +0.77% | 0.256 | 0.036 | 0.063 | 127.826 |
| 4H_-1 | 5 | -16.92% | -0.79% | 0.018 | 0.010 | -0.008 | 36.056 |
| 4H_-1 | 10 | -18.68% | -0.90% | 0.036 | 0.010 | -0.008 | 35.704 |
| 4H_-1 | 20 | -22.07% | -1.10% | 0.070 | 0.010 | -0.008 | 35.013 |

### Año por año, incluido2026 (padres globales congelados)

| Caso | Año | n | retorno | Sharpe | MaxDD | PF | expectancy |
|---|---|---|---|---|---|---|---|
| 1H_1 | 2020 | 98 | +127.55% | 2.332 | -21.34% | 1.978 | +0.93% |
| 1H_1 | 2021 | 87 | -12.62% | -0.137 | -33.22% | 0.926 | -0.10% |
| 1H_1 | 2022 | 93 | -32.53% | -1.208 | -33.51% | 0.645 | -0.39% |
| 1H_1 | 2023 | 116 | -6.40% | -0.145 | -40.15% | 0.996 | -0.00% |
| 1H_1 | 2024 | 109 | +24.88% | 0.970 | -17.78% | 1.296 | +0.24% |
| 1H_1 | 2025 | 102 | -24.48% | -1.178 | -25.15% | 0.685 | -0.26% |
| 1H_1 | 2026 | 66 | -4.42% | -0.179 | -22.70% | 0.958 | -0.03% |
| 1H_-1 | 2020 | 46 | -27.45% | -1.317 | -35.35% | 0.511 | -0.66% |
| 1H_-1 | 2021 | 65 | -39.09% | -1.370 | -47.14% | 0.598 | -0.70% |
| 1H_-1 | 2022 | 63 | +24.38% | 0.862 | -31.34% | 1.350 | +0.46% |
| 1H_-1 | 2023 | 69 | -24.56% | -1.597 | -27.30% | 0.552 | -0.39% |
| 1H_-1 | 2024 | 71 | -24.32% | -1.018 | -30.81% | 0.645 | -0.37% |
| 1H_-1 | 2025 | 60 | -26.19% | -1.586 | -32.53% | 0.481 | -0.49% |
| 1H_-1 | 2026 | 51 | +4.01% | 0.344 | -17.52% | 1.157 | +0.11% |
| 4H_1 | 2020 | 23 | +36.80% | 1.097 | -22.93% | 1.790 | +1.67% |
| 4H_1 | 2021 | 17 | -24.12% | -0.874 | -42.98% | 0.705 | -1.22% |
| 4H_1 | 2022 | 11 | -19.71% | -1.286 | -20.51% | 0.176 | -1.95% |
| 4H_1 | 2023 | 16 | +43.13% | 1.811 | -10.59% | 3.008 | +2.53% |
| 4H_1 | 2024 | 17 | +34.71% | 1.397 | -25.07% | 2.167 | +2.07% |
| 4H_1 | 2025 | 23 | +1.04% | 0.149 | -13.78% | 1.082 | +0.13% |
| 4H_1 | 2026 | 13 | +17.41% | 1.221 | -13.75% | 2.037 | +1.44% |
| 4H_-1 | 2020 | 2 | -1.92% | -0.302 | -6.10% | 0.000 | -0.96% |
| 4H_-1 | 2021 | 7 | -0.73% | 0.124 | -21.41% | 1.132 | +0.46% |
| 4H_-1 | 2022 | 8 | -9.47% | -0.495 | -20.41% | 0.378 | -1.19% |
| 4H_-1 | 2023 | 11 | -9.66% | -1.009 | -12.75% | 0.399 | -0.90% |
| 4H_-1 | 2024 | 7 | -6.41% | -0.693 | -14.96% | 0.540 | -0.89% |
| 4H_-1 | 2025 | 8 | -15.05% | -1.176 | -16.34% | 0.152 | -1.99% |
| 4H_-1 | 2026 | 6 | +6.06% | 0.585 | -16.26% | 1.650 | +1.16% |

### Walk-forward anual separado

Cada fold selecciona usando únicamente pasado: TRAIN anclado2020..año-2; VALIDATIONaño-1. La elegibilidad neta DEV no provoca reranking. Los folds pueden incorporar años antes usados como OOS cuando ya son pasado; no cambian la selección global TEST. No desplegar los fallbacks no elegibles.

| Año | Caso | Familia | DEV elegible | n | retorno | Sharpe | MaxDD | expectancy |
|---|---|---|---|---|---|---|---|---|
| 2022 | 1H_1 | C4_K_SEPARATION | True | 65 | -36.56% | -1.673 | -36.56% | -0.67% |
| 2022 | 1H_-1 | C2_K_CONTEXT | False | 61 | +55.16% | 1.587 | -23.34% | +0.84% |
| 2022 | 4H_1 | C2_K_CONTEXT | False | 15 | -9.96% | -0.428 | -15.73% | -0.62% |
| 2022 | 4H_-1 | C3_K_TRANSITION | False | 8 | -9.47% | -0.495 | -20.41% | -1.19% |
| 2023 | 1H_1 | C3_K_TRANSITION | False | 85 | -8.58% | -0.330 | -36.31% | -0.05% |
| 2023 | 1H_-1 | C1_BBWP50 | False | 69 | -24.56% | -1.597 | -27.30% | -0.39% |
| 2023 | 4H_1 | C2_K_CONTEXT | False | 26 | +42.61% | 1.499 | -15.77% | +1.59% |
| 2023 | 4H_-1 | C0_IMPULSE | False | 30 | -24.45% | -1.516 | -35.19% | -0.89% |
| 2024 | 1H_1 | C4_K_SEPARATION | False | 84 | +1.47% | 0.179 | -21.43% | +0.05% |
| 2024 | 1H_-1 | C0_IMPULSE | False | 97 | -20.08% | -0.692 | -30.98% | -0.21% |
| 2024 | 4H_1 | C4_K_SEPARATION | False | 17 | +34.71% | 1.397 | -25.07% | +2.07% |
| 2024 | 4H_-1 | C3_K_TRANSITION | False | 7 | -6.41% | -0.693 | -14.96% | -0.89% |
| 2025 | 1H_1 | C4_K_SEPARATION | True | 75 | -18.78% | -1.123 | -21.71% | -0.26% |
| 2025 | 1H_-1 | C0_IMPULSE | False | 82 | -14.66% | -0.663 | -29.46% | -0.17% |
| 2025 | 4H_1 | C0_IMPULSE | True | 26 | -4.13% | -0.110 | -14.73% | -0.09% |
| 2025 | 4H_-1 | C3_K_TRANSITION | False | 8 | -15.05% | -1.176 | -16.34% | -1.99% |
| 2026 | 1H_1 | C3_K_TRANSITION | False | 43 | +16.82% | 1.239 | -11.08% | +0.41% |
| 2026 | 1H_-1 | C2_K_CONTEXT | False | 48 | -2.54% | -0.077 | -15.25% | -0.03% |
| 2026 | 4H_1 | C0_IMPULSE | False | 16 | +11.58% | 0.828 | -16.62% | +0.86% |
| 2026 | 4H_-1 | C3_K_TRANSITION | False | 6 | +6.06% | 0.585 | -16.26% | +1.16% |

### Regímenes de operaciones TEST

BULL/BEAR: último4H cerrado contraSMA200; RANGE:ADX<20, solo descriptivo. HIGH/LOW_VOL: mediana TRAIN del ATR/precioTF; no cuantiles elegidos para rentabilidad. Alineación1D usa su SMA200 cerrada; warmup desconocido no se trata como BEAR.

| Caso/cohorte | n | expectancy | win |
|---|---|---|---|
| 1H_1/RANGE | 168 | -0.09% | +28.57% |
| 1H_1/LOW_VOL | 252 | +0.05% | +31.75% |
| 1H_1/DAY_ALIGNED | 176 | -0.02% | +28.41% |
| 1H_1/BULL | 60 | +0.50% | +35.00% |
| 1H_1/HIGH_VOL | 25 | -0.63% | +28.00% |
| 1H_1/BEAR | 49 | -0.34% | +36.73% |
| 1H_1/DAY_OPPOSED | 101 | +0.01% | +36.63% |
| 1H_-1/BULL | 49 | -0.27% | +32.65% |
| 1H_-1/HIGH_VOL | 22 | -1.27% | +22.73% |
| 1H_-1/DAY_OPPOSED | 108 | -0.36% | +25.93% |
| 1H_-1/BEAR | 52 | +0.04% | +32.69% |
| 1H_-1/LOW_VOL | 160 | -0.14% | +29.38% |
| 1H_-1/RANGE | 81 | -0.47% | +23.46% |
| 1H_-1/DAY_ALIGNED | 74 | -0.14% | +32.43% |
| 4H_1/RANGE | 28 | +0.68% | +35.71% |
| 4H_1/LOW_VOL | 50 | +1.33% | +36.00% |
| 4H_1/DAY_ALIGNED | 29 | +1.51% | +37.93% |
| 4H_1/BEAR | 4 | -2.50% | +25.00% |
| 4H_1/BULL | 21 | +2.28% | +38.10% |
| 4H_1/DAY_OPPOSED | 24 | +0.54% | +33.33% |
| 4H_1/HIGH_VOL | 3 | -3.21% | +33.33% |
| 4H_-1/BULL | 2 | -2.54% | +0.00% |
| 4H_-1/HIGH_VOL | 6 | -2.52% | +16.67% |
| 4H_-1/DAY_OPPOSED | 14 | -1.37% | +14.29% |
| 4H_-1/RANGE | 8 | -1.42% | +12.50% |
| 4H_-1/LOW_VOL | 15 | -0.10% | +20.00% |
| 4H_-1/BEAR | 11 | -0.02% | +27.27% |
| 4H_-1/DAY_ALIGNED | 7 | +0.35% | +28.57% |

### Cercanía a cero, separación y divergencias (eventos TEST24h)

Los límites LOW/MID/HIGH son los terciles TRAIN **heredados de PR23**, sin ajustarlos. No son umbrales de entrada. Divergencias AO se detectan con pivots estrictos2izquierda/2derecha y solo aparecen en la vela de confirmación. Se registran como contexto, no familias elegibles.

| Caso/cohorte | n | media | mediana |
|---|---|---|---|
| 1H_1/distance_to_zero/MID | 114 | -0.08% | -0.16% |
| 1H_1/separation/HIGH | 316 | +0.17% | -0.13% |
| 1H_1/regime/RANGE | 209 | +0.01% | -0.17% |
| 1H_1/divergence/False | 393 | +0.12% | -0.14% |
| 1H_1/daily_divergence/False | 392 | +0.15% | -0.13% |
| 1H_1/distance_to_zero/HIGH | 282 | +0.22% | -0.14% |
| 1H_1/regime/BULL | 123 | +0.40% | +0.04% |
| 1H_1/regime/BEAR | 64 | +0.02% | -0.26% |
| 1H_1/separation/LOW | 13 | +0.02% | -0.41% |
| 1H_1/separation/MID | 35 | +0.08% | -0.14% |
| 1H_1/daily_divergence/True | 4 | -1.91% | -2.63% |
| 1H_1/divergence/True | 3 | +1.30% | +1.10% |
| 1H_-1/distance_to_zero/MID | 135 | -0.21% | +0.07% |
| 1H_-1/regime/BULL | 59 | -0.46% | -0.04% |
| 1H_-1/divergence/True | 8 | +0.20% | -0.45% |
| 1H_-1/daily_divergence/False | 215 | -0.22% | -0.04% |
| 1H_-1/separation/MID | 5 | +0.74% | +0.20% |
| 1H_-1/regime/BEAR | 76 | +0.07% | -0.03% |
| 1H_-1/divergence/False | 210 | -0.24% | -0.03% |
| 1H_-1/regime/RANGE | 83 | -0.32% | -0.20% |
| 1H_-1/distance_to_zero/LOW | 77 | -0.19% | -0.13% |
| 1H_-1/separation/HIGH | 3 | -4.21% | -3.28% |
| 1H_-1/distance_to_zero/HIGH | 6 | -0.85% | -0.76% |
| 1H_-1/separation/LOW | 6 | -0.34% | -0.58% |
| 1H_-1/daily_divergence/True | 3 | -0.48% | -1.56% |
| 4H_1/distance_to_zero/MID | 30 | -0.61% | -0.73% |
| 4H_1/separation/HIGH | 55 | +0.11% | +0.32% |
| 4H_1/regime/RANGE | 28 | +0.50% | +0.32% |
| 4H_1/divergence/False | 57 | +0.11% | +0.32% |
| 4H_1/daily_divergence/False | 57 | +0.11% | +0.32% |
| 4H_1/distance_to_zero/HIGH | 27 | +0.91% | +0.94% |
| 4H_1/regime/BEAR | 4 | -2.29% | -0.81% |
| 4H_1/regime/BULL | 25 | +0.07% | +0.53% |
| 4H_1/separation/LOW | 1 | -1.82% | -1.82% |
| 4H_1/separation/MID | 1 | +2.50% | +2.50% |
| 4H_-1/distance_to_zero/MID | 16 | +0.04% | +0.56% |
| 4H_-1/regime/BULL | 2 | -0.19% | -0.19% |
| 4H_-1/divergence/False | 21 | -0.28% | +0.69% |
| 4H_-1/daily_divergence/False | 22 | -0.26% | +0.56% |
| 4H_-1/regime/RANGE | 8 | +0.06% | +0.32% |
| 4H_-1/regime/BEAR | 12 | -0.49% | +0.56% |
| 4H_-1/divergence/True | 1 | +0.15% | +0.15% |
| 4H_-1/distance_to_zero/LOW | 6 | -1.07% | +0.49% |

## Gates y decisión

| Caso | Clasificación | Gates fallidos |
|---|---|---|
| 1H_1 | REJECT | development_eligible, expectancy_positive, pf_gt1_20, sharpe_gt0_75, maxdd_lt25pct, neighbors_positive, stress_positive, without_best3_positive, yearly_at_least2, walk_forward_at_least3 |
| 1H_-1 | REJECT | development_eligible, expectancy_positive, pf_gt1_20, sharpe_gt0_75, maxdd_lt25pct, neighbors_positive, stress_positive, without_best3_positive, yearly_at_least2, walk_forward_at_least3 |
| 4H_1 | INCONCLUSIVE | development_eligible, maxdd_lt25pct, sample_at_least100, without_best3_positive, matched_event_advantage, incremental_k_development |
| 4H_-1 | REJECT | development_eligible, expectancy_positive, pf_gt1_20, sharpe_gt0_75, sample_at_least100, neighbors_positive, stress_positive, without_best3_positive, yearly_at_least2, matched_event_advantage, walk_forward_at_least3 |

PROMISING FOR SHADOW requería elegibilidadDEV, expectancyTEST positiva,PF>1.20,Sharpe>0.75,DD<25%,n>=100, >=75% vecinos positivos,stress positivo,sin mejores3 positivo,>=2 añosTEST positivos,ventaja contra control, >=3 folds positivos y ventaja frente AO_ADX; una familiaK debía mejorar el exceso de C0 en ambos DEV. Ninguna supera todo. Una submuestra rentable no justifica cambiar la clasificación ni limpiar sistemas existentes.

## Telegram preparado, sin envío ni integración

Ejemplos **sintéticos**, no señales históricas ni permiso de entrada. A requiere forward independiente no disponible; B solo si todos los gates históricos se superan; C en el resultado actual. El grade no es probabilidad ni controla sizing. Renderer puro sin token, transporte ni poller. No se inicia ningún observer ni se cambia dedupe/Telegram de producción.
### LONG (fixture)

```text
🟢 BITMAN LONG
₿ BTCUSDT · 4H
🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH
Familia: C4_K_SEPARATION

📦 Konkorde
KONKORDE_PROXY: dentro de montaña positiva; separación aumentando
EXACT BITMAN KONKORDE PARITY: NOT PROVEN

⚡ Oscillator
AO: 141.000 · pendiente: 24.000
Ancla: ZERO_CROSS · retraso ADX: 2 velas

💪 ADX / DI
ADX14: 24.100 · pendiente: 0.700
+DI: 27.200 · -DI: 16.400

🌡️ BBWP
CLOSE/SMA7/100: 55.000% · pendiente: 3.000
50 es referencia pública; paridad del indicador privado de volatilidad NO probada.

🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO
🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED

📚 EVIDENCE GRADE: C
B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.
A requiere validación forward independiente: NO DISPONIBLE.
El grade NO es probabilidad y NO controla sizing.

👀 RAZONES
Hipótesis LONG: ancla AO alcista seguida por giro ADX; +DI apoya.
BBWP aumenta; separación Konkorde positiva en expansión.

Resultado research: INCONCLUSIVE
No es la decisión del Manual Copilot ni una señal V8.
👻 SHADOW ONLY · NO permiso de entrada
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### SHORT (fixture)

```text
🔴 BITMAN SHORT
₿ BTCUSDT · 4H
🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH
Familia: C2_K_CONTEXT

📦 Konkorde
KONKORDE_PROXY: EXIT reciente; fuera y montaña decreciente
EXACT BITMAN KONKORDE PARITY: NOT PROVEN

⚡ Oscillator
AO: -141.000 · pendiente: -24.000
Ancla: ZERO_CROSS · retraso ADX: 2 velas

💪 ADX / DI
ADX14: 24.100 · pendiente: 0.700
+DI: 16.400 · -DI: 27.200

🌡️ BBWP
CLOSE/SMA7/100: 55.000% · pendiente: 3.000
50 es referencia pública; paridad del indicador privado de volatilidad NO probada.

🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO
🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED

📚 EVIDENCE GRADE: C
B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.
A requiere validación forward independiente: NO DISPONIBLE.
El grade NO es probabilidad y NO controla sizing.

👀 RAZONES
Hipótesis SHORT independiente: AO negativo empeora; ADX gira; -DI apoya.
No se invierte la geometría inside LONG.

Resultado research: INCONCLUSIVE
No es la decisión del Manual Copilot ni una señal V8.
👻 SHADOW ONLY · NO permiso de entrada
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### FORMING (fixture)

```text
🟡 BITMAN FORMING
₿ BTCUSDT · 4H
🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH
Familia: C4_K_SEPARATION

📦 Konkorde
KONKORDE_PROXY: dentro de montaña positiva; separación aumentando
EXACT BITMAN KONKORDE PARITY: NOT PROVEN

⚡ Oscillator
AO: 141.000 · pendiente: 24.000
Ancla: ZERO_CROSS · retraso ADX: 2 velas

💪 ADX / DI
ADX14: 24.100 · pendiente: 0.700
+DI: 27.200 · -DI: 16.400

🌡️ BBWP
CLOSE/SMA7/100: 55.000% · pendiente: 3.000
50 es referencia pública; paridad del indicador privado de volatilidad NO probada.

🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO
🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED

📚 EVIDENCE GRADE: C
B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.
A requiere validación forward independiente: NO DISPONIBLE.
El grade NO es probabilidad y NO controla sizing.

👀 RAZONES
AO ha cruzado cero; aún falta giro posterior ADX/confirmación DI.

Resultado research: INCONCLUSIVE
No es la decisión del Manual Copilot ni una señal V8.
👻 SHADOW ONLY · NO permiso de entrada
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### WAIT (fixture)

```text
⚪ BITMAN WAIT
₿ BTCUSDT · 4H
🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH
Familia: C4_K_SEPARATION

📦 Konkorde
KONKORDE_PROXY: dentro de montaña positiva; separación aumentando
EXACT BITMAN KONKORDE PARITY: NOT PROVEN

⚡ Oscillator
AO: 141.000 · pendiente: 24.000
Ancla: ZERO_CROSS · retraso ADX: 2 velas

💪 ADX / DI
ADX14: 24.100 · pendiente: 0.700
+DI: 27.200 · -DI: 16.400

🌡️ BBWP
CLOSE/SMA7/100: 55.000% · pendiente: 3.000
50 es referencia pública; paridad del indicador privado de volatilidad NO probada.

🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO
🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED

📚 EVIDENCE GRADE: C
B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.
A requiere validación forward independiente: NO DISPONIBLE.
El grade NO es probabilidad y NO controla sizing.

👀 RAZONES
No existe una secuencia completa nueva en velas cerradas.

Resultado research: INCONCLUSIVE
No es la decisión del Manual Copilot ni una señal V8.
👻 SHADOW ONLY · NO permiso de entrada
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

### BLOCKED (fixture)

```text
🛑 BITMAN BLOCKED
₿ BTCUSDT · 4H
🧪 DIRECTIONAL CONFLUENCE · HIPÓTESIS RESEARCH
Familia: C4_K_SEPARATION

📦 Konkorde
KONKORDE_PROXY: dentro de montaña positiva; separación aumentando
EXACT BITMAN KONKORDE PARITY: NOT PROVEN

⚡ Oscillator
AO: 141.000 · pendiente: 24.000
Ancla: ZERO_CROSS · retraso ADX: 2 velas

💪 ADX / DI
ADX14: 24.100 · pendiente: 0.700
+DI: 27.200 · -DI: 16.400

🌡️ BBWP
CLOSE/SMA7/100: 55.000% · pendiente: 3.000
50 es referencia pública; paridad del indicador privado de volatilidad NO probada.

🧠 RSI: PRIVATE / PARITY NOT PROVEN · EXCLUIDO
🧭 Trend Speed: NOT IMPLEMENTED / FORMULA NOT VERIFIED

📚 EVIDENCE GRADE: C
B = evidencia histórica que supera gates; C = evidencia insuficiente/rechazada.
A requiere validación forward independiente: NO DISPONIBLE.
El grade NO es probabilidad y NO controla sizing.

👀 RAZONES
Datos insuficientes/no verificados; no emitir nueva observación.

Resultado research: INCONCLUSIVE
No es la decisión del Manual Copilot ni una señal V8.
👻 SHADOW ONLY · NO permiso de entrada
🚫 REAL ORDER: NO
🚫 TRADE AUTHORITY: NONE
```

## Reproducción y validación

Ver [README.md](README.md), [validation.json](artifacts/validation.json) y [safety_audit.json](artifacts/safety_audit.json). Datos grandes fuera de Git. Artefactos: protocolo/hash, manifiesto, locksDEV, resultados, eventos/outcomes comprimidos y trades netos. Reejecución determinista compara JSON descomprimidos, no cabeceras gzip con timestamps.

**V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED. MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.**

**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS. NO production Telegram changes.**
