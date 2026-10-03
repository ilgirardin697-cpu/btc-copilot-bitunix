# ML RSI 15m LOW27 EMA4 — estudio congelado

**Clasificación: NO EDGE.** El runner TP1→breakeven→$500 no tiene expectativa neta positiva fuera de muestra. La falta de paridad exacta con BackQuant bloquea además toda promoción. No se creó un observer SHADOW.

## 1. Paridad y alcance

No existe paridad numérica verificada. La fuente oficial devolvió HTTP 401; la copia atribuida no prueba la versión instalada. Ver [PARITY_AUDIT.md](PARITY_AUDIT.md) y [source_manifest.json](source_manifest.json). Los fixtures son matemáticos independientes, **no exports de TradingView**. El estudio usa el port causal existente sin modificarlo: LOW, RSI27, EMA4, tres clusters, rolling 3000, máximo 1000 iteraciones.

## 2. Datos y metodología

BTCUSDT **Binance spot**, 754,190 velas 5m, 2019-08-01T00:00:00+00:00 → 2026-10-03T20:00:00+00:00.

Se verificaron los checksums de archivos públicos. Hay 18 huecos entre velas; no se interpolan. Solo se agregan grupos completos 15m/1H. Un trade que cruza un hueco se censura, no se convierte en éxito. Manifest con URLs, hashes, filas y timestamps en [data_manifest.json](data_manifest.json). Datasets y caches grandes quedan fuera de Git.

TRAIN 2020–2021; VALIDATION 2022–2023; TEST 2024–último cierre verificado. Se fuerza cierre/censura en límites de split, sin usar resultados del siguiente período. El protocolo, código y selección quedan unidos por hashes. Solo tres runners con stop 0.30% eran elegibles para selección: $500, 0.75 ATR1H, 1 ATR1H; score mínimo de expectativa TRAIN/VALIDATION con n≥100 en ambos. TEST no entra en `choose()`. Los restantes stops/exits son controles vecinos predefinidos, no candidatos elegidos usando TEST. Ver [preregistered.json](preregistered.json) y [frozen_selection.json](frozen_selection.json).

CROSS dispara una vez al cambiar al color (incluye transición directa desde color opuesto). RESUME exige el mismo color en ambas velas y reset de pendiente dentro de ese episodio; luego un solo impulso. Dos barras: CROSS espera dos pendientes del signo nuevo dentro del mismo episodio; RESUME espera dos tras el reset. Un cambio de color o hueco cancela la confirmación pendiente.

Entrada principal: siguiente apertura 15m con slippage adverso. Close-fill es sensibilidad separada y nunca rellena dentro de la vela de señal. Gestión simulada sobre 5m cerradas: stop primero si se tocan stop y TP; TP1/BE ambiguo sale el runner a BE conservador. El trailing se actualiza al cierre 5m y se aplica desde la próxima barra, nunca retroactivamente. ATR1H se congela al señal. Stop nunca se amplía. Todos los modelos tienen límite predefinido 48h; el runner control sale por color opuesto/48h tras TP1 y BE. La salida simple por color no tiene el stop porcentual y no es comparable en riesgo.

Base: taker **5 bps por fill**, slippage 2 bps, stop slippage 5 bps. Stress: 6/5/10 bps. Entrada, TP parcial y runner pagan costes proporcionales. Supuesto VIP1 publicado en la [tabla oficial](https://www.bitunix.com/service/handling-fee), no una afirmación del tier real del usuario. Se puede configurar fee en CLI, congelando el mismo coste en desarrollo y TEST. **Funding, basis spot/perpetual y fills reales Bitunix no están incluidos**: son retornos teóricos del subyacente con fees/slippage, no rentabilidad ejecutable de una cuenta futures. Gross retira fricciones del mismo camino/targets, no vuelve a simular un camino de órdenes distinto.

Métricas por evento pueden solaparse; MaxDD/retorno secuencial usan separadamente 1x, una sola posición simulada y rechazan entradas mientras está ocupada. No hay leverage ni modelo de liquidación. Win/loss/BE neto usa ±1 bp; precio BE no significa BE neto. MFE/MAE son excursiones conservadoras de las barras completadas antes de la salida más sus fills; no se atribuyen extremos posteriores al cierre intrabar.

## 3. Expectativa por split ($500 / stop 0.30%)

| Evento:barras | TRAIN n / net medio | VALIDATION n / net medio | TEST n / net medio |
| --- | --- | --- | --- |
| GREEN_CROSS:1 | 507 / -0.234% | 385 / -0.178% | 745 / -0.187% |
| GREEN_RESUME:1 | 604 / -0.198% | 426 / -0.153% | 850 / -0.179% |
| RED_CROSS:1 | 867 / -0.235% | 856 / -0.191% | 1084 / -0.200% |
| RED_RESUME:1 | 854 / -0.231% | 816 / -0.182% | 980 / -0.199% |
| GREEN_CROSS:2 | 398 / -0.179% | 318 / -0.155% | 603 / -0.195% |
| GREEN_RESUME:2 | 358 / -0.228% | 266 / -0.197% | 552 / -0.190% |
| RED_CROSS:2 | 682 / -0.268% | 629 / -0.166% | 864 / -0.192% |
| RED_RESUME:2 | 545 / -0.256% | 521 / -0.213% | 644 / -0.201% |

## 4. TEST neto y bruto por evento (gestión primaria)

| Evento:barras | Señales/trades | Gross medio | Net medio | Net mediano | R | PF | MaxDD 1x | Hold h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | 745/745 | -0.022% | -0.187% | -0.450% | -0.625 | 0.240 | +73.405% | 1.529 |
| GREEN_RESUME:1 | 850/850 | -0.013% | -0.179% | -0.450% | -0.596 | 0.295 | +66.023% | 1.533 |
| RED_CROSS:1 | 1084/1084 | -0.034% | -0.200% | -0.450% | -0.667 | 0.218 | +86.710% | 1.176 |
| RED_RESUME:1 | 980/980 | -0.033% | -0.199% | -0.450% | -0.664 | 0.223 | +80.536% | 1.057 |
| GREEN_CROSS:2 | 603/603 | -0.029% | -0.195% | -0.450% | -0.649 | 0.202 | +66.675% | 1.552 |
| GREEN_RESUME:2 | 552/552 | -0.024% | -0.190% | -0.450% | -0.634 | 0.292 | +57.478% | 1.229 |
| RED_CROSS:2 | 864/864 | -0.027% | -0.192% | -0.450% | -0.641 | 0.242 | +80.920% | 1.212 |
| RED_RESUME:2 | 644/644 | -0.035% | -0.201% | -0.450% | -0.668 | 0.209 | +68.449% | 0.969 |

| Evento:barras | Win | Loss | BE neto | TP1 / move BE | Stop antes TP1 | Salida precio BE | Trailing | MFE med | MAE med | Fees/gross profit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | +16.376% | +82.819% | +0.805% | +48.725% | +51.275% | +30.470% | +18.255% | +0.284% | -0.300% | +82.095% |
| GREEN_RESUME:1 | +16.353% | +82.353% | +1.294% | +46.824% | +53.176% | +26.824% | +20.000% | +0.264% | -0.300% | +73.594% |
| RED_CROSS:1 | +12.546% | +86.808% | +0.646% | +46.863% | +53.137% | +32.288% | +14.576% | +0.261% | -0.300% | +87.425% |
| RED_RESUME:1 | +12.551% | +86.735% | +0.714% | +46.837% | +53.163% | +32.041% | +14.796% | +0.267% | -0.300% | +86.505% |
| GREEN_CROSS:2 | +15.423% | +83.748% | +0.829% | +49.420% | +50.580% | +31.675% | +17.745% | +0.294% | -0.300% | +88.858% |
| GREEN_RESUME:2 | +13.587% | +85.688% | +0.725% | +43.478% | +56.522% | +26.087% | +17.391% | +0.228% | -0.300% | +74.502% |
| RED_CROSS:2 | +13.310% | +85.185% | +1.505% | +47.222% | +52.778% | +30.440% | +16.782% | +0.252% | -0.300% | +82.517% |
| RED_RESUME:2 | +13.354% | +85.404% | +1.242% | +47.360% | +52.640% | +31.056% | +16.304% | +0.260% | -0.300% | +88.794% |

## 5. LONG / SHORT combinados (primario)

| Barras | Cohorte | Eventos | Net medio | R | PF | Trades secuenciales | Retorno secuencial | MaxDD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | LONG | 1595 | -0.183% | -0.609 | 0.270 | 1154 | -87.401% | +87.850% |
| 1 | SHORT | 2064 | -0.200% | -0.666 | 0.221 | 1669 | -96.701% | +96.701% |
| 1 | LONG_SHORT | 3659 | -0.192% | -0.641 | 0.242 | 2823 | -99.584% | +99.595% |
| 2 | LONG | 1155 | -0.192% | -0.642 | 0.247 | 921 | -81.372% | +81.553% |
| 2 | SHORT | 1508 | -0.196% | -0.653 | 0.228 | 1253 | -92.250% | +92.275% |
| 2 | LONG_SHORT | 2663 | -0.194% | -0.648 | 0.236 | 2174 | -98.556% | +98.574% |

## 6. Baselines y controles emparejados

Un timestamp cerrado no-evento por señal, emparejado por mes/año, tendencia 1H, volatilidad y hora UTC; seed773, con reemplazo. Los denominadores evaluables pueden variar por huecos/fin de datos. No se interpreta una media positiva como edge frente a drift.

| Evento:barras | Salida | Señal n/net | Control n/net | Diferencia descriptiva |
| --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | opposite_0.003 | 745 / +0.099% | 745 / +0.088% | +0.011% |
| GREEN_CROSS:1 | fixed500_0.003 | 745 / -0.187% | 745 / -0.184% | -0.004% |
| GREEN_CROSS:1 | atr_0.003_0.75 | 745 / -0.183% | 745 / -0.189% | +0.006% |
| GREEN_CROSS:1 | atr_0.003_1 | 745 / -0.183% | 745 / -0.186% | +0.003% |
| GREEN_CROSS:1 | fixed1r_0.003 | 745 / -0.143% | 745 / -0.151% | +0.008% |
| GREEN_CROSS:1 | fixed2r_0.003 | 745 / -0.138% | 745 / -0.165% | +0.027% |
| GREEN_CROSS:1 | runner_0.003 | 745 / -0.160% | 745 / -0.174% | +0.014% |
| GREEN_RESUME:1 | opposite_0.003 | 850 / +0.216% | 850 / -0.113% | +0.329% |
| GREEN_RESUME:1 | fixed500_0.003 | 850 / -0.179% | 850 / -0.165% | -0.014% |
| GREEN_RESUME:1 | atr_0.003_0.75 | 850 / -0.183% | 850 / -0.164% | -0.019% |
| GREEN_RESUME:1 | atr_0.003_1 | 850 / -0.182% | 850 / -0.165% | -0.016% |
| GREEN_RESUME:1 | fixed1r_0.003 | 850 / -0.155% | 850 / -0.145% | -0.010% |
| GREEN_RESUME:1 | fixed2r_0.003 | 850 / -0.145% | 850 / -0.151% | +0.007% |
| GREEN_RESUME:1 | runner_0.003 | 850 / -0.138% | 850 / -0.150% | +0.012% |
| RED_CROSS:1 | opposite_0.003 | 1083 / -0.246% | 1083 / -0.273% | +0.027% |
| RED_CROSS:1 | fixed500_0.003 | 1084 / -0.200% | 1084 / -0.167% | -0.034% |
| RED_CROSS:1 | atr_0.003_0.75 | 1084 / -0.199% | 1084 / -0.155% | -0.044% |
| RED_CROSS:1 | atr_0.003_1 | 1084 / -0.200% | 1084 / -0.158% | -0.042% |
| RED_CROSS:1 | fixed1r_0.003 | 1084 / -0.155% | 1084 / -0.134% | -0.020% |
| RED_CROSS:1 | fixed2r_0.003 | 1084 / -0.152% | 1084 / -0.131% | -0.021% |
| RED_CROSS:1 | runner_0.003 | 1083 / -0.204% | 1083 / -0.142% | -0.062% |
| RED_RESUME:1 | opposite_0.003 | 977 / -0.386% | 978 / -0.186% | -0.200% |
| RED_RESUME:1 | fixed500_0.003 | 980 / -0.199% | 980 / -0.169% | -0.030% |
| RED_RESUME:1 | atr_0.003_0.75 | 980 / -0.201% | 980 / -0.161% | -0.040% |
| RED_RESUME:1 | atr_0.003_1 | 980 / -0.209% | 980 / -0.163% | -0.046% |
| RED_RESUME:1 | fixed1r_0.003 | 980 / -0.155% | 980 / -0.138% | -0.017% |
| RED_RESUME:1 | fixed2r_0.003 | 980 / -0.154% | 980 / -0.136% | -0.018% |
| RED_RESUME:1 | runner_0.003 | 980 / -0.173% | 980 / -0.165% | -0.008% |
| GREEN_CROSS:2 | opposite_0.003 | 603 / +0.156% | 603 / -0.122% | +0.277% |
| GREEN_CROSS:2 | fixed500_0.003 | 603 / -0.195% | 603 / -0.203% | +0.009% |
| GREEN_CROSS:2 | atr_0.003_0.75 | 603 / -0.186% | 603 / -0.206% | +0.020% |
| GREEN_CROSS:2 | atr_0.003_1 | 603 / -0.192% | 603 / -0.197% | +0.006% |
| GREEN_CROSS:2 | fixed1r_0.003 | 603 / -0.139% | 603 / -0.170% | +0.031% |
| GREEN_CROSS:2 | fixed2r_0.003 | 603 / -0.158% | 603 / -0.178% | +0.020% |
| GREEN_CROSS:2 | runner_0.003 | 603 / -0.194% | 603 / -0.226% | +0.032% |
| GREEN_RESUME:2 | opposite_0.003 | 552 / +0.225% | 552 / -0.041% | +0.266% |
| GREEN_RESUME:2 | fixed500_0.003 | 552 / -0.190% | 552 / -0.183% | -0.007% |
| GREEN_RESUME:2 | atr_0.003_0.75 | 552 / -0.199% | 552 / -0.169% | -0.029% |
| GREEN_RESUME:2 | atr_0.003_1 | 552 / -0.197% | 552 / -0.176% | -0.022% |
| GREEN_RESUME:2 | fixed1r_0.003 | 552 / -0.176% | 552 / -0.155% | -0.021% |
| GREEN_RESUME:2 | fixed2r_0.003 | 552 / -0.167% | 552 / -0.180% | +0.013% |
| GREEN_RESUME:2 | runner_0.003 | 552 / -0.164% | 552 / -0.118% | -0.047% |
| RED_CROSS:2 | opposite_0.003 | 863 / -0.261% | 863 / -0.390% | +0.128% |
| RED_CROSS:2 | fixed500_0.003 | 864 / -0.192% | 864 / -0.185% | -0.007% |
| RED_CROSS:2 | atr_0.003_0.75 | 864 / -0.186% | 864 / -0.188% | +0.001% |
| RED_CROSS:2 | atr_0.003_1 | 864 / -0.187% | 864 / -0.188% | +0.001% |
| RED_CROSS:2 | fixed1r_0.003 | 864 / -0.153% | 864 / -0.168% | +0.015% |
| RED_CROSS:2 | fixed2r_0.003 | 864 / -0.140% | 864 / -0.169% | +0.029% |
| RED_CROSS:2 | runner_0.003 | 863 / -0.174% | 863 / -0.180% | +0.006% |
| RED_RESUME:2 | opposite_0.003 | 642 / -0.327% | 643 / -0.088% | -0.239% |
| RED_RESUME:2 | fixed500_0.003 | 644 / -0.201% | 644 / -0.164% | -0.036% |
| RED_RESUME:2 | atr_0.003_0.75 | 644 / -0.201% | 644 / -0.167% | -0.033% |
| RED_RESUME:2 | atr_0.003_1 | 644 / -0.209% | 644 / -0.168% | -0.041% |
| RED_RESUME:2 | fixed1r_0.003 | 644 / -0.152% | 644 / -0.141% | -0.011% |
| RED_RESUME:2 | fixed2r_0.003 | 644 / -0.138% | 644 / -0.134% | -0.004% |
| RED_RESUME:2 | runner_0.003 | 644 / -0.185% | 644 / -0.156% | -0.029% |

La salida por color tiene otro perfil de riesgo: no usa SL .30%. Sus medias positivas GREEN son un resultado descriptivo del port causal, no validación del Pine del usuario ni del runner. Se auditan también por año, stress y bootstrap para no ocultar esta diferencia.

| Evento:barras | Color 2024 net | 2025 net | 2026 net | Stress net | Color bootstrap 95% net |
| --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | +0.690% | -0.235% | -0.121% | +0.019% | -0.172% / +0.401% |
| GREEN_RESUME:1 | +0.823% | -0.151% | +0.061% | +0.136% | -0.170% / +0.668% |
| RED_CROSS:1 | -0.491% | -0.253% | +0.098% | -0.326% | -0.540% / +0.078% |
| RED_RESUME:1 | -0.495% | -0.720% | +0.103% | -0.466% | -0.725% / -0.021% |
| GREEN_CROSS:2 | +0.785% | -0.176% | -0.137% | +0.075% | -0.142% / +0.476% |
| GREEN_RESUME:2 | +0.672% | -0.079% | +0.119% | +0.145% | -0.250% / +0.725% |
| RED_CROSS:2 | -0.600% | -0.204% | +0.140% | -0.342% | -0.587% / +0.070% |
| RED_RESUME:2 | -0.505% | -0.702% | +0.289% | -0.407% | -0.761% / +0.129% |

## 7. Robustez, costes y concentración

| Evento:barras | Stop .25% | .30% | .40% | .50% | ATR .75, stop .30% | ATR1, stop .30% |
| --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | -0.193% | -0.187% | -0.188% | -0.177% | -0.183% | -0.183% |
| GREEN_RESUME:1 | -0.181% | -0.179% | -0.160% | -0.154% | -0.183% | -0.182% |
| RED_CROSS:1 | -0.200% | -0.200% | -0.179% | -0.159% | -0.199% | -0.200% |
| RED_RESUME:1 | -0.201% | -0.199% | -0.205% | -0.182% | -0.201% | -0.209% |
| GREEN_CROSS:2 | -0.202% | -0.195% | -0.174% | -0.167% | -0.186% | -0.192% |
| GREEN_RESUME:2 | -0.191% | -0.190% | -0.169% | -0.141% | -0.199% | -0.197% |
| RED_CROSS:2 | -0.191% | -0.192% | -0.168% | -0.159% | -0.186% | -0.187% |
| RED_RESUME:2 | -0.196% | -0.201% | -0.204% | -0.213% | -0.201% | -0.209% |

| Evento:barras | Stress primario net | Close-fill net | Sin top3 R | Sin worst3 R | Top3/ganancias netas | Bootstrap semanal 95% net |
| --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | -0.285% | -0.187% | -0.654 | -0.621 | +13.605% | -0.210% / -0.161% |
| GREEN_RESUME:1 | -0.264% | -0.179% | -0.629 | -0.593 | +12.539% | -0.211% / -0.144% |
| RED_CROSS:1 | -0.294% | -0.201% | -0.687 | -0.665 | +9.640% | -0.222% / -0.178% |
| RED_RESUME:1 | -0.297% | -0.199% | -0.689 | -0.661 | +12.346% | -0.226% / -0.170% |
| GREEN_CROSS:2 | -0.283% | -0.195% | -0.676 | -0.645 | +14.577% | -0.219% / -0.168% |
| GREEN_RESUME:2 | -0.290% | -0.190% | -0.681 | -0.629 | +16.516% | -0.227% / -0.153% |
| RED_CROSS:2 | -0.283% | -0.192% | -0.668 | -0.638 | +12.044% | -0.215% / -0.168% |
| RED_RESUME:2 | -0.297% | -0.201% | -0.696 | -0.665 | +14.039% | -0.231% / -0.168% |

Todos los vecinos runner siguen negativos. Dos pendientes, ATR y close-fill no rescatan la hipótesis primaria. Quitar los mejores o peores tres no la vuelve rentable. El resultado no es una dependencia de un ganador enorme: es una gestión con expectativa negativa. Los intervalos bootstrap son descriptivos de eventos por bloques semanales, no una prueba de paridad ni corrección exhaustiva por comparaciones múltiples.

La gestión no mejora de manera robusta los baselines. Tomar 30% en +0.30% y salir el 70% al precio de entrada produce aproximadamente +0.09% bruto; los fees roundtrip rondan 0.10% antes del slippage de salida. Por eso precio BE puede producir una pérdida neta. Los baselines GREEN por color opuesto tienen medias positivas, pero distinta exposición/riesgo. En GREEN el año 2025 es negativo y los intervalos bootstrap del baseline por color incluyen cero: no hay estabilidad suficiente para afirmar edge. No justifican el runner propuesto ni automatización.

## 8. Año, tendencia y volatilidad; reciente descriptivo

Diagnósticos de contexto sin gating: SMA200 1H ±1% define BULL/BEAR/SIDEWAYS; ATR1H/close define LOW<0.5%, HIGH≥1%, MEDIUM entre ambos. No se añaden indicadores a sistemas operativos. Desde 2025-10-01 es una vista reciente descriptiva, no reemplaza TEST ni selecciona parámetros.

### Año

| Evento:barras | 2024 n / net | 2025 n / net | 2026 n / net |
| --- | --- | --- | --- |
| GREEN_CROSS:1 | 241 / -0.191% | 279 / -0.169% | 225 / -0.206% |
| GREEN_RESUME:1 | 266 / -0.155% | 333 / -0.180% | 251 / -0.203% |
| RED_CROSS:1 | 414 / -0.227% | 366 / -0.184% | 304 / -0.183% |
| RED_RESUME:1 | 368 / -0.203% | 313 / -0.219% | 299 / -0.174% |
| GREEN_CROSS:2 | 201 / -0.208% | 225 / -0.145% | 177 / -0.242% |
| GREEN_RESUME:2 | 182 / -0.181% | 213 / -0.203% | 157 / -0.184% |
| RED_CROSS:2 | 331 / -0.218% | 295 / -0.187% | 238 / -0.164% |
| RED_RESUME:2 | 246 / -0.224% | 202 / -0.205% | 196 / -0.166% |

### Tendencia

| Evento:barras | BULL n / net | BEAR n / net | SIDEWAYS n / net |
| --- | --- | --- | --- |
| GREEN_CROSS:1 | 393 / -0.205% | 154 / -0.181% | 198 / -0.157% |
| GREEN_RESUME:1 | 548 / -0.175% | 110 / -0.193% | 192 / -0.181% |
| RED_CROSS:1 | 279 / -0.227% | 523 / -0.186% | 282 / -0.200% |
| RED_RESUME:1 | 148 / -0.179% | 604 / -0.196% | 228 / -0.220% |
| GREEN_CROSS:2 | 322 / -0.191% | 115 / -0.172% | 166 / -0.217% |
| GREEN_RESUME:2 | 365 / -0.173% | 73 / -0.203% | 114 / -0.236% |
| RED_CROSS:2 | 195 / -0.247% | 431 / -0.184% | 238 / -0.163% |
| RED_RESUME:2 | 88 / -0.238% | 412 / -0.183% | 144 / -0.228% |

### Volatilidad

| Evento:barras | LOW n / net | MEDIUM n / net | HIGH n / net |
| --- | --- | --- | --- |
| GREEN_CROSS:1 | 247 / -0.170% | 430 / -0.188% | 68 / -0.243% |
| GREEN_RESUME:1 | 207 / -0.188% | 563 / -0.170% | 80 / -0.215% |
| RED_CROSS:1 | 331 / -0.182% | 636 / -0.203% | 117 / -0.240% |
| RED_RESUME:1 | 244 / -0.173% | 568 / -0.198% | 168 / -0.241% |
| GREEN_CROSS:2 | 190 / -0.188% | 353 / -0.184% | 60 / -0.276% |
| GREEN_RESUME:2 | 123 / -0.173% | 371 / -0.188% | 58 / -0.237% |
| RED_CROSS:2 | 260 / -0.147% | 500 / -0.208% | 104 / -0.232% |
| RED_RESUME:2 | 168 / -0.162% | 365 / -0.201% | 111 / -0.259% |

| Evento:barras | Reciente n | Net medio |
| --- | --- | --- |
| GREEN_CROSS:1 | 285 | -0.204% |
| GREEN_RESUME:1 | 319 | -0.199% |
| RED_CROSS:1 | 386 | -0.181% |
| RED_RESUME:1 | 376 | -0.172% |
| GREEN_CROSS:2 | 227 | -0.215% |
| GREEN_RESUME:2 | 201 | -0.186% |
| RED_CROSS:2 | 305 | -0.167% |
| RED_RESUME:2 | 247 | -0.167% |

## 9. Capturas: sanity checks, nunca etiquetas de entrenamiento

Interpretación Europe/Madrid (CEST=UTC+2). «Evening» no identifica una vela única: se muestra 20:00 como referencia descriptiva, sin reclamar que sea la captura exacta. Sin símbolo/venue/export del usuario no se atribuyen coincidencias al Pine real.

- Oct1 evening CEST (representative 20:00): port causal NEUTRAL, RSI=60.85; eventos cercanos: ninguno ±1h.
- Oct2 03:45 CEST: port causal NEUTRAL, RSI=54.51; eventos cercanos: ninguno ±1h.
- Oct2 17:00 CEST: port causal NEUTRAL, RSI=48.62; eventos cercanos: RED_CROSS 16:00 UTC.

## Reproducción y seguridad

```powershell
python -m research.mlrsi_pattern_data --cutoff 1791057600000 --refresh
python -m research.mlrsi_pattern_backtest --phase development --cutoff 1791057600000
python -m research.mlrsi_pattern_backtest --phase test --cutoff 1791057600000
python -m research.mlrsi_pattern_report
python -m unittest research.test_mlrsi_pattern -v
```

Para un clon sin caches, reconstruir el dataset original con el downloader público ya existente `python -m research.early_breakout_data --as-of 2026-10-02T16:05:00+00:00`, sin arrancar Early Breakout. Luego el script de datos de este estudio verifica archives y añade su cola congelada. REST histórico puede cambiar: comparar el manifest; si difiere, no afirmar reproducción de los mismos bytes. Dependencias explícitas: numpy y requests. No hay APIs de cuenta, credenciales, funciones de órdenes, POST o observer desplegado. Manual Copilot, Guardian, forward audit, V8 y Early Breakout no se modificaron. El runner usa solamente el módulo matemático puro existente; no depende de mutaciones Guardian.

Métricas completas y conteos de censura para todos los vecinos: [development_results.json](development_results.json), [test_results.json](test_results.json), [diagnostics.json](diagnostics.json). El bootstrap no crea probabilidades de éxito inventadas. **NO EDGE significa que no se cumple el estándar de promoción; no demuestra que toda posible versión del Pine original carezca de información.**
