# BITMAN — Weekly AO × BBWP expansion research

**EXPANSION EFFECT FRAGILE — RECOMENDACIÓN: NO INTEGRAR.**

RESEARCH ONLY · HISTORICAL BACKTEST / EVENT STUDY · NO REAL FORWARD OBSERVED SIGNALS.
No estrategia de trading, órdenes, automatización ni cambios del motor. TRADE AUTHORITY: NONE.

## 1. Hipótesis y protocolo previo

Se separan dos preguntas: (A) si la expansión de BBWP anticipa magnitud futura y (B) si el color del AO añade dirección incremental. ADX/DI es exclusivamente secundario. Ningún N, bucket o porcentaje se eligió por sus resultados.

El [protocolo](BITMAN_WEEKLY_EXPANSION_PROTOCOL.md) se fijó en el commit `a9d428e` antes de descargar/evaluar el histórico completo; solo hubo una petición mínima previa de conectividad/boundary, sin outcomes. SHA256 del protocolo normalizado: `5513195a7b1cdc99ee5f8502f9f2da9b342f79f378d581f28956e2b4d19cf954`. Base exacta: `9c660035f912be4640f09cf6e2d4c48583c20b04`.

## 2. Provenance y auditoría de datos

Venue invariable: **BTCUSDT BINANCE_USDM_PERPETUAL**. Fuente principal: GET público [Binance USD-M REST `/fapi/v1/klines`](https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/market.py), desde el PC autorizado; no Railway, Spot, proxy, VPN ni credenciales. Vision se usa solo como contraste independiente, nunca para rellenar o sustituir filas.

| Campo | Valor |
| --- | --- |
| Descarga UTC | 2026-10-20T10:28:43.290321+00:00 |
| Primer open 4H REST | 2019-09-08T16:00:00+00:00 |
| Último close 4H incluido | 2026-10-18T23:59:59.999000+00:00 |
| Filas 4H | 15584 |
| Semanas completas | 371 |
| Primera semana completa | 2019-09-09T00:00:00+00:00 |
| Último close semanal | 2026-10-18T23:59:59.999000+00:00 |
| Cutoff exclusivo | 2026-10-19T00:00:00+00:00 |
| SHA256 dataset 4H JSON | ea8954f95f15f67eff041e506fc9e0539d5adb7422632b5f7d8246e88704e050 |
| SHA256 dataset semanal JSON | 8278c1f44c250c7073c0bb912533a335325cd7109a2a10af59227f2d68a811bc |

El [manifest](bitman_weekly_expansion/data_manifest.json) conserva URLs, parámetros exactos, status, bytes y SHA256 de cada respuesta/ZIP, además de las diferencias numéricas completas. Las respuestas RAW quedan local-only/gitignored. Los CSV versionados contienen solo mercado público y permiten reproducción offline de los resultados.

| Campo solicitado | Filas comparadas 1w | Diferencias exactas 4H→1W vs REST 1w |
| --- | --- | --- |
| open_time | 371 | 0 |
| open | 371 | 1 |
| high | 371 | 0 |
| low | 371 | 0 |
| close | 371 | 0 |
| base_volume | 371 | 5 |
| close_time | 371 | 0 |
| taker_buy_base_volume | 371 | 5 |

No se afirma paridad de los ocho campos. Una apertura de 2019-09-23 difiere (REST 1w 8,061.98; agregado 4H 10,027.69), y cinco semanas presentan diferencias de volumen/taker. No se atribuye una causa no verificada. **High, low, close y timestamps coinciden en las 371 semanas**. Los ocho arrays utilizados (AO, delta AO, BBWP, delta BBWP, ADX, delta ADX, +DI, −DI) resultan exactamente iguales, NaN incluidos, al calcularlos por separado sobre ambas series. No dependen de open ni volumen. No se mezclaron las fuentes.

El repositorio oficial [Binance Public Data](https://github.com/binance/binance-public-data#klines-1) identifica los klines USD-M de Vision con `/fapi/v1/klines` y documenta CHECKSUM y posibles revisiones posteriores. Se compararon todos los campos solicitados en siete meses disponibles (2019-09 no disponible), con CHECKSUM verificado:

| Mes Vision | Status | Filas | Campos diferentes | Barras diferentes |
| --- | --- | --- | --- | --- |
| 2019-09 | NOT_AVAILABLE | 0 | 0 | 0 |
| 2020-03 | COMPARED | 186 | 0 | 0 |
| 2021-11 | COMPARED | 180 | 0 | 0 |
| 2022-11 | COMPARED | 180 | 0 | 0 |
| 2023-06 | COMPARED | 180 | 0 | 0 |
| 2024-03 | COMPARED | 186 | 6 | 3 |
| 2025-01 | COMPARED | 186 | 2 | 1 |
| 2026-09 | COMPARED | 180 | 0 | 0 |

Son 1,278 barras de contraste. Solo hay diferencias en volumen/taker: tres barras de marzo 2024 y una de enero 2025; cero diferencias de OHLC/timestamps. Se documentan los deltas exactos en el manifest. Histórico recuperado hoy puede contener revisiones: no equivale a datos point-in-time ni a alertas realmente observadas en esas fechas.

## 3. Definición semanal causal

Semana = lunes 00:00 UTC → siguiente lunes 00:00 UTC, anclada a 1970-01-05 (no al jueves del Unix epoch). Requiere 42 barras 4H contiguas, ordenadas y cerradas; open primero, high máximo, low mínimo, close último, volúmenes sumados con Decimal. Se excluye la semana inicial parcial del 2019-09-02, que solo tiene dos barras 4H. No se rellenan huecos.
Las 15,584 filas REST pasan schema de 12 columnas, OHLC/volúmenes finitos válidos, closeTime=openTime+4H−1, orden y contigüidad: cero gaps o duplicados en la serie descargada.

La semana abierta 2026-10-19 no está descargada ni calculada. La última cerrada abre 2026-10-12 y finaliza 2026-10-18 23:59:59.999 UTC; su información está disponible en el límite 2026-10-19 00:00 UTC. Las épocas se asignan por ese tiempo de disponibilidad.

## 4. Fórmulas exactas, eventos y outcomes

Se reutiliza sin editar `bitman_manual/frozen/indicators.py::calculate`: AO = SMA5((H+L)/2) − SMA34((H+L)/2), ao_slope = AO[t]−AO[t−1]. GREEN iff slope>0; RED iff slope<0; cero es FLAT. Color no equivale al signo del AO ni a la clasificación multibarra del motor de dirección.

BBW = 4×std poblacional(C,7)/SMA(C,7). BBWP[t] = número de los 100 BBW anteriores estrictamente menores que BBW[t], dentro de 101 valores finitos. Empates no suman; rango 0..100. bbwp_slope = BBWP[t]−BBWP[t−1]. El primer BBWP necesita 107 semanas; la pendiente 108; la cohorte común que requiere la pendiente previa para START necesita 109. Se excluyen 108 semanas iniciales de la cohorte común. No se acorta el ranking.

A: slope>0; B: slope<0; C: slope previo<=0 → actual>0. D: C después de >=2/3/4 slopes previos consecutivos<=0 (subconjuntos anidados). E: C según BBWP previo [0,10], (10,20], (20,30], (30,50], >50. F: cruce estricto actual>50/previo<=50, actual<50 rising y actual>50 rising. Exactamente 50 no se redondea a ninguno de estos dos últimos lados.

Ancla de evaluación = close de la semana del evento, sin afirmar un fill ejecutable. R[h]=100×(C[t+h]/C[t]−1). Signed=R para GREEN, −R para RED. Hit=signed>0; empates no ganan. MFE/MAE son excursiones favorables/adversas no negativas relativas al AO, usando exclusivamente máximos/mínimos de las semanas futuras t+1..t+h. Max abs=max(excursión arriba, excursión abajo). **|R terminal| y max abs intrahorizonte son métricas diferentes**, ambas con frecuencias >=3/5/10/15%. No se incluyen high/low de la propia semana del evento.
En stratum ALL, firmado sigue el color AO de cada observación, no un lado fijo universal; los retornos raw y las excursiones sin dirección se publican por separado. BBWP es un ranking relativo: su subida/bajada no garantiza por identidad matemática que suba/baje la anchura absoluta de bandas. STARTING/ACTIVE/COOLING describen los eventos BBWP definidos, no una medición causal de volatilidad absoluta.

ADX/DI: TR y DM direccional de H/L/C, Wilder RMA14, ±DI=100×RMA14(±DM)/ATR14; DX=100×|+DI−−DI|/(+DI+−DI); ADX=RMA14(DX). Semilla y NaN iniciales son exactamente los del frozen source. Contexto bull/bear = signo(close 4H−SMA200 4H) de la última 4H cerrada al cierre semanal, igual que el régimen causal existente; no se recalcula usando precios futuros.

IC95 = bootstrap circular de bloques de 8 semanas, 2,000 réplicas, seed 20261020+h. Se remuestrean pares originales semana/outcome, no secuencias de velas inventadas. Intervalos descriptivos, sin corrección por multiplicidad. n<10 o <95% réplicas finitas → IC omitido; n<30 → **INSUFFICIENT FOR CONCLUSION**. El denominador anual usa semanas elegibles de la época/régimen; las fases no solapadas usan la duración calendario completa.
Entorno de cálculo: Python 3.12.10, NumPy 2.5.3. Los CSV incluyen también IC por época/régimen cuando la muestra lo permite; las cuatro fases temporales se muestran como control descriptivo.

## 5. Número de observaciones y cobertura útil

| Dato | Valor |
| --- | --- |
| Semanas completas | 371 |
| Semanas con BBWP, slope y slope previo válidos | 263 |
| Primer BBWP disponible | 2021-09-27T00:00:00+00:00 |
| Primer evento común disponible | 2021-10-11T00:00:00+00:00 |
| Semanas AO FLAT / AO exactamente cero | 0 / 0 |
| Semanas BBWP slope=0 | 14 |
| Observaciones con futuro 1/2/4 semanas | 262 / 261 / 259 |

2020 y los cierres hasta el disponible el 2021-10-04 son warmup para la cohorte común, no evidencia evaluable. No se introduce Spot para alargarlo. Una semana con varios eventos aparece en varias tablas, no representa observaciones independientes adicionales. Los últimos horizontes incompletos se censuran, nunca se convierten en retornos cero.

## 6. AO solo y sus cuatro cuadrantes

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | GREEN | 1 | 138 | 0.80 | 0.80 | [-0.47, 1.93] | 50.0% | 4.66 | 7.92 | 5.38 | 4.61 | 27.48 |
| ALL | GREEN | 2 | 137 | 1.37 | 1.37 | [-1.14, 3.66] | 52.6% | 7.40 | 11.63 | 8.11 | 6.54 | 27.39 |
| ALL | GREEN | 4 | 135 | 2.39 | 2.39 | [-2.25, 7.16] | 50.4% | 12.23 | 18.08 | 12.75 | 9.71 | 27.20 |
| ALL | RED | 1 | 124 | -0.07 | 0.07 | [-1.26, 1.23] | 51.6% | 5.22 | 9.28 | 6.10 | 5.44 | 24.69 |
| ALL | RED | 2 | 124 | 0.11 | -0.11 | [-2.56, 2.07] | 50.8% | 7.54 | 13.06 | 8.54 | 7.82 | 24.79 |
| ALL | RED | 4 | 124 | 0.70 | -0.70 | [-4.99, 2.90] | 46.0% | 9.93 | 17.41 | 11.31 | 10.98 | 24.98 |
| ALL | GREEN_POS | 1 | 77 | 1.30 | 1.30 | [-0.27, 2.65] | 51.9% | 4.46 | 8.06 | 5.60 | 4.63 | 15.33 |
| ALL | GREEN_POS | 2 | 76 | 2.35 | 2.35 | [-0.37, 5.06] | 53.9% | 6.57 | 11.29 | 8.27 | 6.14 | 15.19 |
| ALL | GREEN_POS | 4 | 74 | 3.26 | 3.26 | [-1.74, 7.90] | 52.7% | 9.81 | 16.06 | 12.14 | 8.57 | 14.91 |
| ALL | RED_POS | 1 | 77 | 0.13 | -0.13 | [-1.85, 1.26] | 51.9% | 5.19 | 8.71 | 5.86 | 4.99 | 15.33 |
| ALL | RED_POS | 2 | 77 | 0.26 | -0.26 | [-3.17, 2.45] | 49.4% | 7.52 | 12.69 | 8.36 | 7.33 | 15.39 |
| ALL | RED_POS | 4 | 77 | 1.34 | -1.34 | [-7.40, 3.20] | 50.6% | 10.43 | 17.56 | 11.50 | 10.91 | 15.51 |
| ALL | GREEN_NEG | 1 | 61 | 0.17 | 0.17 | [-1.80, 2.09] | 47.5% | 4.92 | 7.75 | 5.11 | 4.58 | 12.15 |
| ALL | GREEN_NEG | 2 | 61 | 0.16 | 0.16 | [-3.42, 4.11] | 50.8% | 8.43 | 12.06 | 7.90 | 7.05 | 12.19 |
| ALL | GREEN_NEG | 4 | 61 | 1.32 | 1.32 | [-6.59, 9.94] | 47.5% | 15.16 | 20.54 | 13.48 | 11.10 | 12.29 |
| ALL | RED_NEG | 1 | 47 | -0.41 | 0.41 | [-1.90, 2.61] | 51.1% | 5.27 | 10.22 | 6.48 | 6.19 | 9.36 |
| ALL | RED_NEG | 2 | 47 | -0.14 | 0.14 | [-3.85, 4.10] | 53.2% | 7.58 | 13.66 | 8.84 | 8.61 | 9.40 |
| ALL | RED_NEG | 4 | 47 | -0.34 | 0.34 | [-5.18, 6.50] | 38.3% | 9.10 | 17.17 | 11.00 | 11.11 | 9.47 |

Se mantienen por separado AO>0 GREEN, AO>0 RED, AO<0 GREEN y AO<0 RED. Las medias/hits son condicionamientos históricos; no se equipara AO<0 GREEN con una orden alcista. Las distribuciones completas (p10/p25/mediana/p75/p90, sd, extremos) están en `summaries.csv`.

## 7. BBWP solo: magnitud, no dirección

| Grupo | h | n | µ |R| | Mediana |R| | IC95 µ |R| | µ max abs | IC95 µ max abs | P(up) | P(down) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 262 | 4.93 | 3.44 | [4.40, 5.41] | 8.57 | [7.83, 9.29] | 49.2% | 50.8% |
| ALL | 2 | 261 | 7.47 | 5.97 | [6.54, 8.36] | 12.31 | [11.23, 13.38] | 51.0% | 49.0% |
| ALL | 4 | 259 | 11.13 | 8.56 | [9.39, 12.99] | 17.76 | [15.96, 19.74] | 52.1% | 47.9% |
| A_RISING | 1 | 127 | 4.78 | 3.42 | [4.16, 5.46] | 8.66 | [7.79, 9.57] | 53.5% | 46.5% |
| A_RISING | 2 | 127 | 7.22 | 5.98 | [6.17, 8.37] | 11.83 | [10.65, 13.17] | 52.0% | 48.0% |
| A_RISING | 4 | 127 | 9.74 | 7.33 | [8.07, 11.54] | 16.26 | [14.46, 18.25] | 56.7% | 43.3% |
| B_FALLING | 1 | 121 | 4.96 | 3.45 | [4.10, 5.87] | 8.43 | [7.32, 9.59] | 42.1% | 57.9% |
| B_FALLING | 2 | 120 | 7.36 | 5.68 | [5.89, 8.87] | 12.54 | [10.85, 14.32] | 49.2% | 50.8% |
| B_FALLING | 4 | 118 | 12.02 | 9.48 | [9.68, 14.55] | 18.91 | [16.40, 21.45] | 46.6% | 53.4% |
| C_START | 1 | 50 | 5.06 | 2.84 | [3.68, 6.82] | 9.68 | [7.93, 11.62] | 62.0% | 38.0% |
| C_START | 2 | 50 | 9.29 | 7.99 | [7.62, 10.90] | 13.60 | [11.92, 15.34] | 52.0% | 48.0% |
| C_START | 4 | 50 | 12.27 | 10.53 | [9.60, 15.30] | 19.31 | [16.62, 22.18] | 58.0% | 42.0% |

| Rising − falling | h | n rising/falling | Lift pp | IC95 lift | Ex mejor 1 | Ex mejores 3 |
| --- | --- | --- | --- | --- | --- | --- |
| absolute | 1 | 127/121 | -0.18 | [-1.38, 0.96] | -0.36 | -0.64 |
| max_move | 1 | 127/121 | 0.24 | [-1.05, 1.52] | 0.08 | -0.19 |
| absolute | 2 | 127/120 | -0.13 | [-2.02, 1.70] | -0.34 | -0.63 |
| max_move | 2 | 127/120 | -0.71 | [-2.67, 1.23] | -0.90 | -1.22 |
| absolute | 4 | 127/118 | -2.28 | [-4.58, 0.08] | -2.55 | -2.89 |
| max_move | 4 | 127/118 | -2.65 | [-5.06, -0.12] | -2.89 | -3.31 |

No se demuestra que rising anticipe más magnitud que falling. A 1 semana el pequeño lift de max abs (+0.24 pp) tiene IC cruzando cero y pasa a −0.19 pp al excluir los mejores tres. A 4 semanas, max abs medio es 16.26% rising frente a 18.91% falling; esto contradice la generalización visual, sin justificar una regla inversa nueva. La conclusión FRAGILE describe ese indicio positivo débil, no un efecto expansivo validado.

### Frecuencias de movimiento fuerte: ambas definiciones, todos los umbrales

| Evento | AO | h | n | |R|≥3 | ≥5 | ≥10 | ≥15 | max≥3 | ≥5 | ≥10 | ≥15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | ALL | 1 | 262 | 55.3% | 35.1% | 13.7% | 3.8% | 96.2% | 74.8% | 27.5% | 10.7% |
| ALL | ALL | 2 | 261 | 67.8% | 53.3% | 26.8% | 13.0% | 99.6% | 92.7% | 49.8% | 28.4% |
| ALL | ALL | 4 | 259 | 77.2% | 64.5% | 44.4% | 29.7% | 100.0% | 98.8% | 79.2% | 54.1% |
| ALL | GREEN | 1 | 138 | 53.6% | 31.9% | 12.3% | 4.3% | 97.1% | 70.3% | 21.7% | 8.7% |
| ALL | GREEN | 2 | 137 | 68.6% | 51.8% | 24.1% | 13.9% | 99.3% | 90.5% | 43.8% | 21.9% |
| ALL | GREEN | 4 | 135 | 80.0% | 65.2% | 48.9% | 38.5% | 100.0% | 97.8% | 80.0% | 53.3% |
| ALL | RED | 1 | 124 | 57.3% | 38.7% | 15.3% | 3.2% | 95.2% | 79.8% | 33.9% | 12.9% |
| ALL | RED | 2 | 124 | 66.9% | 54.8% | 29.8% | 12.1% | 100.0% | 95.2% | 56.5% | 35.5% |
| ALL | RED | 4 | 124 | 74.2% | 63.7% | 39.5% | 20.2% | 100.0% | 100.0% | 78.2% | 54.8% |
| A_RISING | ALL | 1 | 127 | 54.3% | 33.1% | 10.2% | 3.1% | 96.1% | 78.0% | 28.3% | 11.8% |
| A_RISING | ALL | 2 | 127 | 67.7% | 52.8% | 27.6% | 11.8% | 100.0% | 94.5% | 49.6% | 26.8% |
| A_RISING | ALL | 4 | 127 | 74.0% | 60.6% | 40.9% | 24.4% | 100.0% | 99.2% | 74.0% | 48.8% |
| A_RISING | GREEN | 1 | 61 | 50.8% | 32.8% | 13.1% | 4.9% | 95.1% | 70.5% | 23.0% | 9.8% |
| A_RISING | GREEN | 2 | 61 | 65.6% | 52.5% | 27.9% | 14.8% | 100.0% | 90.2% | 44.3% | 21.3% |
| A_RISING | GREEN | 4 | 61 | 77.0% | 62.3% | 49.2% | 34.4% | 100.0% | 98.4% | 75.4% | 50.8% |
| A_RISING | RED | 1 | 66 | 57.6% | 33.3% | 7.6% | 1.5% | 97.0% | 84.8% | 33.3% | 13.6% |
| A_RISING | RED | 2 | 66 | 69.7% | 53.0% | 27.3% | 9.1% | 100.0% | 98.5% | 54.5% | 31.8% |
| A_RISING | RED | 4 | 66 | 71.2% | 59.1% | 33.3% | 15.2% | 100.0% | 100.0% | 72.7% | 47.0% |
| B_FALLING | ALL | 1 | 121 | 55.4% | 35.5% | 16.5% | 4.1% | 95.9% | 71.1% | 27.3% | 9.9% |
| B_FALLING | ALL | 2 | 120 | 67.5% | 52.5% | 25.0% | 13.3% | 99.2% | 90.0% | 50.8% | 30.0% |
| B_FALLING | ALL | 4 | 118 | 79.7% | 68.6% | 47.5% | 33.1% | 100.0% | 98.3% | 85.6% | 59.3% |
| B_FALLING | GREEN | 1 | 69 | 53.6% | 29.0% | 10.1% | 2.9% | 98.6% | 68.1% | 20.3% | 7.2% |
| B_FALLING | GREEN | 2 | 68 | 70.6% | 50.0% | 19.1% | 10.3% | 98.5% | 89.7% | 42.6% | 20.6% |
| B_FALLING | GREEN | 4 | 66 | 80.3% | 65.2% | 45.5% | 37.9% | 100.0% | 97.0% | 83.3% | 53.0% |
| B_FALLING | RED | 1 | 52 | 57.7% | 44.2% | 25.0% | 5.8% | 92.3% | 75.0% | 36.5% | 13.5% |
| B_FALLING | RED | 2 | 52 | 63.5% | 55.8% | 32.7% | 17.3% | 100.0% | 90.4% | 61.5% | 42.3% |
| B_FALLING | RED | 4 | 52 | 78.8% | 73.1% | 50.0% | 26.9% | 100.0% | 100.0% | 88.5% | 67.3% |
| C_START | ALL | 1 | 50 | 48.0% | 32.0% | 14.0% | 6.0% | 96.0% | 72.0% | 34.0% | 22.0% |
| C_START | ALL | 2 | 50 | 76.0% | 68.0% | 44.0% | 20.0% | 100.0% | 94.0% | 62.0% | 44.0% |
| C_START | ALL | 4 | 50 | 84.0% | 66.0% | 54.0% | 34.0% | 100.0% | 98.0% | 78.0% | 70.0% |
| C_START | GREEN | 1 | 20 | 50.0% | 40.0% | 20.0% | 10.0% | 95.0% | 60.0% | 30.0% | 25.0% |
| C_START | GREEN | 2 | 20 | 80.0% | 70.0% | 50.0% | 25.0% | 100.0% | 85.0% | 65.0% | 35.0% |
| C_START | GREEN | 4 | 20 | 90.0% | 70.0% | 70.0% | 55.0% | 100.0% | 95.0% | 80.0% | 80.0% |
| C_START | RED | 1 | 30 | 46.7% | 26.7% | 10.0% | 3.3% | 96.7% | 80.0% | 36.7% | 20.0% |
| C_START | RED | 2 | 30 | 73.3% | 66.7% | 40.0% | 16.7% | 100.0% | 100.0% | 60.0% | 50.0% |
| C_START | RED | 4 | 30 | 80.0% | 63.3% | 43.3% | 20.0% | 100.0% | 100.0% | 76.7% | 63.3% |

Todos los demás eventos/buckets también incluyen las ocho frecuencias en el CSV completo; no se selecciona un porcentaje objetivo.

## 8. Interacción AO × BBWP y valor incremental

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A_RISING | GREEN | 1 | 61 | 0.89 | 0.89 | [-1.06, 2.60] | 52.5% | 4.76 | 7.88 | 5.26 | 4.62 | 12.15 |
| A_RISING | GREEN | 2 | 61 | 1.84 | 1.84 | [-1.45, 4.77] | 55.7% | 7.50 | 11.33 | 8.15 | 6.18 | 12.19 |
| A_RISING | GREEN | 4 | 61 | 3.00 | 3.00 | [-2.11, 7.86] | 57.4% | 11.07 | 16.65 | 12.39 | 8.20 | 12.29 |
| A_RISING | RED | 1 | 66 | 0.68 | -0.68 | [-2.57, 0.84] | 45.5% | 4.79 | 9.39 | 6.03 | 5.82 | 13.14 |
| A_RISING | RED | 2 | 66 | 0.29 | -0.29 | [-2.66, 1.85] | 51.5% | 6.96 | 12.29 | 7.77 | 7.93 | 13.19 |
| A_RISING | RED | 4 | 66 | 1.10 | -1.10 | [-4.93, 1.90] | 43.9% | 8.50 | 15.89 | 10.25 | 10.98 | 13.30 |
| B_FALLING | GREEN | 1 | 69 | 0.19 | 0.19 | [-1.39, 1.83] | 43.5% | 4.34 | 7.75 | 5.11 | 4.91 | 13.74 |
| B_FALLING | GREEN | 2 | 68 | -0.27 | -0.27 | [-2.88, 2.41] | 48.5% | 6.63 | 11.16 | 7.04 | 7.33 | 13.59 |
| B_FALLING | GREEN | 4 | 66 | 0.88 | 0.88 | [-4.17, 6.44] | 43.9% | 11.98 | 18.22 | 12.01 | 11.14 | 13.30 |
| B_FALLING | RED | 1 | 52 | -1.25 | 1.25 | [-1.43, 3.77] | 59.6% | 5.78 | 9.32 | 6.50 | 4.88 | 10.36 |
| B_FALLING | RED | 2 | 52 | -0.59 | 0.59 | [-3.01, 4.01] | 50.0% | 8.30 | 14.34 | 10.03 | 7.58 | 10.40 |
| B_FALLING | RED | 4 | 52 | -0.23 | 0.23 | [-5.70, 5.70] | 50.0% | 12.07 | 19.78 | 13.11 | 10.97 | 10.48 |

| AO | h | Referencia | Métrica | n evento/control | Lift | IC95 | Ex mejores 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN | 1 | A_RISING_CONSTANT_SIDE | signed | 61/127 | 0.11 | [-1.25, 1.31] | -0.71 |
| GREEN | 1 | A_RISING_CONSTANT_SIDE | hit | 61/127 | -1.08 | [-10.83, 7.34] | -3.54 |
| GREEN | 1 | SAME_COLOR | signed | 61/138 | 0.09 | [-1.22, 1.40] | -0.72 |
| GREEN | 1 | SAME_COLOR | hit | 61/138 | 2.46 | [-8.39, 12.06] | 0.00 |
| GREEN | 1 | FALLING_SAME_COLOR | signed | 61/69 | 0.70 | [-1.85, 2.95] | -0.11 |
| GREEN | 1 | FALLING_SAME_COLOR | hit | 61/69 | 8.98 | [-11.05, 26.67] | 6.52 |
| RED | 1 | A_RISING_CONSTANT_SIDE | signed | 66/127 | 0.10 | [-1.19, 1.19] | -0.49 |
| RED | 1 | A_RISING_CONSTANT_SIDE | hit | 66/127 | -1.00 | [-9.79, 7.17] | -3.60 |
| RED | 1 | SAME_COLOR | signed | 66/124 | -0.76 | [-2.16, 0.60] | -1.35 |
| RED | 1 | SAME_COLOR | hit | 66/124 | -6.16 | [-16.14, 3.52] | -8.76 |
| RED | 1 | FALLING_SAME_COLOR | signed | 66/52 | -1.93 | [-5.13, 1.25] | -2.52 |
| RED | 1 | FALLING_SAME_COLOR | hit | 66/52 | -14.16 | [-35.41, 7.92] | -16.76 |
| GREEN | 2 | A_RISING_CONSTANT_SIDE | signed | 61/127 | 0.81 | [-1.26, 2.78] | -0.41 |
| GREEN | 2 | A_RISING_CONSTANT_SIDE | hit | 61/127 | 3.77 | [-6.49, 12.98] | 1.48 |
| GREEN | 2 | SAME_COLOR | signed | 61/137 | 0.47 | [-1.51, 2.52] | -0.75 |
| GREEN | 2 | SAME_COLOR | hit | 61/137 | 3.18 | [-5.61, 11.30] | 0.89 |
| GREEN | 2 | FALLING_SAME_COLOR | signed | 61/68 | 2.11 | [-1.43, 5.65] | 0.89 |
| GREEN | 2 | FALLING_SAME_COLOR | hit | 61/68 | 7.21 | [-10.61, 22.42] | 4.92 |
| RED | 2 | A_RISING_CONSTANT_SIDE | signed | 66/127 | 0.75 | [-1.04, 2.56] | -0.03 |
| RED | 2 | A_RISING_CONSTANT_SIDE | hit | 66/127 | 3.48 | [-5.76, 12.62] | 1.17 |
| RED | 2 | SAME_COLOR | signed | 66/124 | -0.18 | [-1.72, 1.36] | -0.96 |
| RED | 2 | SAME_COLOR | hit | 66/124 | 0.71 | [-8.27, 9.16] | -1.60 |
| RED | 2 | FALLING_SAME_COLOR | signed | 66/52 | -0.88 | [-4.28, 2.51] | -1.65 |
| RED | 2 | FALLING_SAME_COLOR | hit | 66/52 | 1.52 | [-17.50, 20.95] | -0.79 |
| GREEN | 4 | A_RISING_CONSTANT_SIDE | signed | 61/127 | 0.99 | [-2.00, 3.73] | -0.43 |
| GREEN | 4 | A_RISING_CONSTANT_SIDE | hit | 61/127 | 0.68 | [-10.67, 9.98] | -1.52 |
| GREEN | 4 | SAME_COLOR | signed | 61/135 | 0.62 | [-2.47, 3.47] | -0.80 |
| GREEN | 4 | SAME_COLOR | hit | 61/135 | 7.01 | [-1.52, 15.75] | 4.80 |
| GREEN | 4 | FALLING_SAME_COLOR | signed | 61/66 | 2.12 | [-3.27, 7.08] | 0.70 |
| GREEN | 4 | FALLING_SAME_COLOR | hit | 61/66 | 13.44 | [-3.18, 30.38] | 11.23 |
| RED | 4 | A_RISING_CONSTANT_SIDE | signed | 66/127 | 0.91 | [-1.76, 3.67] | -0.14 |
| RED | 4 | A_RISING_CONSTANT_SIDE | hit | 66/127 | 0.63 | [-8.38, 9.63] | -2.04 |
| RED | 4 | SAME_COLOR | signed | 66/124 | -0.40 | [-2.16, 1.53] | -1.45 |
| RED | 4 | SAME_COLOR | hit | 66/124 | -2.03 | [-8.57, 4.91] | -4.70 |
| RED | 4 | FALLING_SAME_COLOR | signed | 66/52 | -1.33 | [-5.15, 2.89] | -2.39 |
| RED | 4 | FALLING_SAME_COLOR | hit | 66/52 | -6.06 | [-19.44, 8.05] | -8.73 |

Los controles CONSTANT_SIDE usan el mismo lado fijo (+R GREEN, −R RED) en todas las semanas rising; así no se confunde drift alcista con información del AO. SAME_COLOR elimina la condición BBWP. Las diferencias de hit están en pp; las demás, pp de retorno. Ningún lift firmado AO-vs-constant-side tiene IC95 positivo a los tres horizontes. El caso RED+rising tiene medias firmadas negativas en 1/2/4 semanas, con IC amplios: no se concluye valor direccional bajista.

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A_RISING | GREEN_POS | 1 | 32 | 2.46 | 2.46 | [-0.30, 4.58] | 59.4% | 4.70 | 8.24 | 6.27 | 4.12 | 6.37 |
| A_RISING | GREEN_POS | 2 | 32 | 4.47 | 4.47 | [0.19, 8.26] | 62.5% | 6.92 | 11.09 | 9.14 | 4.86 | 6.40 |
| A_RISING | GREEN_POS | 4 | 32 | 6.18 | 6.18 | [0.23, 11.20] | 65.6% | 10.17 | 15.62 | 13.43 | 5.84 | 6.45 |
| A_RISING | RED_POS | 1 | 42 | 0.97 | -0.97 | [-3.39, 1.14] | 45.2% | 4.96 | 8.87 | 5.82 | 5.52 | 8.36 |
| A_RISING | RED_POS | 2 | 42 | 0.63 | -0.63 | [-3.82, 2.40] | 45.2% | 7.59 | 12.35 | 7.68 | 7.93 | 8.40 |
| A_RISING | RED_POS | 4 | 42 | 1.74 | -1.74 | [-6.97, 2.12] | 45.2% | 9.21 | 16.10 | 10.20 | 11.14 | 8.46 |
| A_RISING | GREEN_NEG | 1 | 29 | -0.84 | -0.84 | [-3.76, 1.28] | 44.8% | 4.82 | 7.48 | 4.15 | 5.16 | 5.78 |
| A_RISING | GREEN_NEG | 2 | 29 | -1.06 | -1.06 | [-5.92, 2.77] | 48.3% | 8.14 | 11.59 | 7.05 | 7.64 | 5.80 |
| A_RISING | GREEN_NEG | 4 | 29 | -0.50 | -0.50 | [-7.68, 7.07] | 48.3% | 12.06 | 17.78 | 11.25 | 10.81 | 5.84 |
| A_RISING | RED_NEG | 1 | 24 | 0.19 | -0.19 | [-3.33, 2.05] | 45.8% | 4.50 | 10.30 | 6.41 | 6.34 | 4.78 |
| A_RISING | RED_NEG | 2 | 24 | -0.30 | 0.30 | [-4.18, 3.59] | 62.5% | 5.87 | 12.19 | 7.94 | 7.93 | 4.80 |
| A_RISING | RED_NEG | 4 | 24 | -0.02 | 0.02 | [-5.04, 5.06] | 41.7% | 7.27 | 15.52 | 10.34 | 10.70 | 4.83 |
| B_FALLING | GREEN_POS | 1 | 43 | 0.62 | 0.62 | [-0.78, 2.12] | 46.5% | 4.35 | 7.95 | 5.21 | 4.96 | 8.56 |
| B_FALLING | GREEN_POS | 2 | 42 | 0.87 | 0.87 | [-2.00, 4.17] | 50.0% | 6.60 | 11.61 | 7.84 | 7.12 | 8.40 |
| B_FALLING | GREEN_POS | 4 | 40 | 1.40 | 1.40 | [-4.66, 7.56] | 45.0% | 9.70 | 16.72 | 11.55 | 10.70 | 8.06 |
| B_FALLING | RED_POS | 1 | 32 | -1.21 | 1.21 | [-1.55, 4.36] | 62.5% | 5.38 | 8.50 | 6.14 | 4.20 | 6.37 |
| B_FALLING | RED_POS | 2 | 32 | -0.85 | 0.85 | [-2.92, 4.58] | 56.2% | 7.09 | 13.10 | 9.73 | 6.28 | 6.40 |
| B_FALLING | RED_POS | 4 | 32 | 0.47 | -0.47 | [-8.51, 5.74] | 56.2% | 12.04 | 19.39 | 13.36 | 10.30 | 6.45 |
| B_FALLING | GREEN_NEG | 1 | 26 | -0.53 | -0.53 | [-3.26, 2.98] | 38.5% | 4.31 | 7.42 | 4.94 | 4.82 | 5.18 |
| B_FALLING | GREEN_NEG | 2 | 26 | -2.10 | -2.10 | [-5.76, 2.06] | 46.2% | 6.69 | 10.44 | 5.75 | 7.67 | 5.20 |
| B_FALLING | GREEN_NEG | 4 | 26 | 0.08 | 0.08 | [-8.07, 10.44] | 42.3% | 15.50 | 20.53 | 12.72 | 11.82 | 5.24 |
| B_FALLING | RED_NEG | 1 | 20 | -1.31 | 1.31 | [-3.53, 5.75] | 55.0% | 6.42 | 10.65 | 7.08 | 5.96 | 3.98 |
| B_FALLING | RED_NEG | 2 | 20 | -0.15 | 0.15 | [-7.41, 7.07] | 40.0% | 10.24 | 16.34 | 10.52 | 9.66 | 4.00 |
| B_FALLING | RED_NEG | 4 | 20 | -1.34 | 1.34 | [-7.60, 11.02] | 40.0% | 12.10 | 20.40 | 12.72 | 12.03 | 4.03 |


## 9. Expansion start

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C_START | ALL | 1 | 50 | 1.50 | -0.68 | [-2.73, 1.26] | 42.0% | 5.06 | 9.68 | 6.13 | 5.64 | 9.96 |
| C_START | ALL | 2 | 50 | 1.75 | 0.80 | [-2.34, 3.77] | 52.0% | 9.29 | 13.60 | 9.16 | 7.87 | 10.00 |
| C_START | ALL | 4 | 50 | 3.66 | 0.80 | [-4.00, 5.53] | 50.0% | 12.27 | 19.31 | 13.00 | 10.93 | 10.07 |
| C_START | GREEN | 1 | 20 | 1.03 | 1.03 | [-2.80, 4.53] | 55.0% | 5.72 | 9.23 | 5.79 | 4.60 | 3.98 |
| C_START | GREEN | 2 | 20 | 3.19 | 3.19 | [-2.05, 7.70] | 55.0% | 9.90 | 13.51 | 10.01 | 6.14 | 4.00 |
| C_START | GREEN | 4 | 20 | 5.58 | 5.58 | [-3.38, 14.07] | 60.0% | 14.81 | 20.16 | 15.31 | 8.35 | 4.03 |
| C_START | RED | 1 | 30 | 1.81 | -1.81 | [-4.48, 0.53] | 33.3% | 4.62 | 9.98 | 6.36 | 6.33 | 5.97 |
| C_START | RED | 2 | 30 | 0.79 | -0.79 | [-4.57, 2.99] | 50.0% | 8.88 | 13.66 | 8.59 | 9.01 | 6.00 |
| C_START | RED | 4 | 30 | 2.38 | -2.38 | [-8.02, 2.39] | 43.3% | 10.58 | 18.74 | 11.46 | 12.66 | 6.04 |

| h | Métrica de magnitud | Referencia | n | Lift | IC95 | Ex mejores 3 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | absolute | ALL | 50 | 0.14 | [-1.23, 1.87] | -0.91 |
| 1 | max_move | ALL | 50 | 1.11 | [-0.44, 2.83] | 0.09 |
| 1 | absolute | B_FALLING | 50 | 0.10 | [-1.75, 2.25] | -0.94 |
| 1 | max_move | B_FALLING | 50 | 1.25 | [-0.85, 3.53] | 0.24 |
| 2 | absolute | ALL | 50 | 1.82 | [0.23, 3.46] | 0.90 |
| 2 | max_move | ALL | 50 | 1.29 | [-0.35, 2.98] | 0.43 |
| 2 | absolute | B_FALLING | 50 | 1.93 | [-0.40, 4.14] | 1.01 |
| 2 | max_move | B_FALLING | 50 | 1.06 | [-1.16, 3.34] | 0.20 |
| 4 | absolute | ALL | 50 | 1.14 | [-0.88, 3.33] | -0.24 |
| 4 | max_move | ALL | 50 | 1.54 | [-0.31, 3.59] | 0.18 |
| 4 | absolute | B_FALLING | 50 | 0.25 | [-2.53, 3.25] | -1.13 |
| 4 | max_move | B_FALLING | 50 | 0.40 | [-2.28, 3.40] | -0.96 |

Hay 50 starts con futuro completo; GREEN 20 y RED 30. GREEN START tiene media firmada 4W +5.58%, pero IC95 [−3.38,+14.07] y n=20: **INSUFFICIENT FOR CONCLUSION**. RED START no valida dirección bajista. Las comparaciones por color contra START sin AO y SAME_COLOR, con todos sus IC, están en `contrasts.csv`; una diferencia positiva de magnitud en un horizonte no satisface los criterios robustos del protocolo ni valida dirección.
Indicio exploratorio que sí aparece: START a 2W tiene |R| medio 9.29% frente a 7.47% en ALL; lift +1.82 pp, IC95 [0.23,3.46]. Frente a falling, su IC cruza cero; tampoco se reproduce en todos los horizontes ni en max abs. Es una comparación nominal entre muchas, no evidencia suficiente para STRONG MOVE WATCH. Se conserva como hallazgo descriptivo, sin seleccionar una regla 2W.

## 10. Contracción previa: N=2, 3 y 4 sin elegir ganador

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D_PRIOR_2 | ALL | 1 | 30 | 1.53 | -1.95 | [-5.04, 0.71] | 36.7% | 5.73 | 10.24 | 5.60 | 6.45 | 5.97 |
| D_PRIOR_2 | ALL | 2 | 30 | 0.42 | 0.90 | [-3.29, 4.74] | 56.7% | 9.19 | 13.58 | 8.45 | 7.97 | 6.00 |
| D_PRIOR_2 | ALL | 4 | 30 | 4.04 | 0.05 | [-7.00, 6.22] | 50.0% | 13.75 | 20.04 | 12.60 | 11.45 | 6.04 |
| D_PRIOR_2 | GREEN | 1 | 11 | -0.58 | -0.58 | [-6.12, 4.05] | 54.5% | 6.04 | 9.14 | 4.77 | 5.52 | 2.19 |
| D_PRIOR_2 | GREEN | 2 | 11 | 1.79 | 1.79 | [-5.99, 8.77] | 54.5% | 10.57 | 13.75 | 9.15 | 7.27 | 2.20 |
| D_PRIOR_2 | GREEN | 4 | 11 | 5.57 | 5.57 | [-7.98, 18.68] | 63.6% | 18.95 | 24.07 | 17.11 | 10.77 | 2.22 |
| D_PRIOR_2 | RED | 1 | 19 | 2.75 | -2.75 | [-6.61, 0.51] | 26.3% | 5.55 | 10.87 | 6.08 | 6.98 | 3.78 |
| D_PRIOR_2 | RED | 2 | 19 | -0.38 | 0.38 | [-4.91, 5.00] | 57.9% | 8.40 | 13.49 | 8.05 | 8.38 | 3.80 |
| D_PRIOR_2 | RED | 4 | 19 | 3.15 | -3.15 | [-10.48, 3.22] | 42.1% | 10.73 | 17.70 | 9.99 | 11.84 | 3.83 |
| D_PRIOR_3 | ALL | 1 | 20 | 1.54 | -1.23 | [-5.10, 1.97] | 40.0% | 5.50 | 10.70 | 6.48 | 5.99 | 3.98 |
| D_PRIOR_3 | ALL | 2 | 20 | 0.25 | -0.03 | [-4.92, 4.66] | 50.0% | 8.92 | 13.57 | 8.00 | 8.14 | 4.00 |
| D_PRIOR_3 | ALL | 4 | 20 | 4.12 | -1.90 | [-10.39, 5.64] | 50.0% | 14.22 | 19.95 | 11.14 | 12.13 | 4.03 |
| D_PRIOR_3 | GREEN | 1 | 6 | 0.51 | 0.51 | — | 50.0% | 4.84 | 7.50 | 4.65 | 4.09 | 1.19 |
| D_PRIOR_3 | GREEN | 2 | 6 | 0.38 | 0.38 | — | 50.0% | 8.97 | 12.16 | 7.94 | 7.30 | 1.20 |
| D_PRIOR_3 | GREEN | 4 | 6 | 3.71 | 3.71 | — | 66.7% | 17.12 | 22.34 | 15.15 | 10.98 | 1.21 |
| D_PRIOR_3 | RED | 1 | 14 | 1.98 | -1.98 | [-7.01, 2.07] | 35.7% | 5.78 | 12.08 | 7.26 | 6.80 | 2.79 |
| D_PRIOR_3 | RED | 2 | 14 | 0.20 | -0.20 | [-6.43, 5.52] | 50.0% | 8.90 | 14.18 | 8.03 | 8.50 | 2.80 |
| D_PRIOR_3 | RED | 4 | 14 | 4.30 | -4.30 | [-14.20, 4.27] | 42.9% | 12.97 | 18.92 | 9.42 | 12.62 | 2.82 |
| D_PRIOR_4 | ALL | 1 | 14 | 3.12 | -2.68 | [-7.67, 1.35] | 28.6% | 6.11 | 10.11 | 5.53 | 6.49 | 2.79 |
| D_PRIOR_4 | ALL | 2 | 14 | 3.03 | -2.70 | [-8.66, 3.05] | 42.9% | 9.44 | 13.51 | 7.13 | 9.24 | 2.80 |
| D_PRIOR_4 | ALL | 4 | 14 | 7.29 | -4.11 | [-14.31, 5.94] | 42.9% | 15.37 | 21.13 | 10.22 | 14.57 | 2.82 |
| D_PRIOR_4 | GREEN | 1 | 6 | 0.51 | 0.51 | — | 50.0% | 4.84 | 7.50 | 4.65 | 4.09 | 1.19 |
| D_PRIOR_4 | GREEN | 2 | 6 | 0.38 | 0.38 | — | 50.0% | 8.97 | 12.16 | 7.94 | 7.30 | 1.20 |
| D_PRIOR_4 | GREEN | 4 | 6 | 3.71 | 3.71 | — | 66.7% | 17.12 | 22.34 | 15.15 | 10.98 | 1.21 |
| D_PRIOR_4 | RED | 1 | 8 | 5.08 | -5.08 | — | 12.5% | 7.07 | 12.07 | 6.18 | 8.29 | 1.59 |
| D_PRIOR_4 | RED | 2 | 8 | 5.02 | -5.02 | — | 37.5% | 9.79 | 14.52 | 6.52 | 10.69 | 1.60 |
| D_PRIOR_4 | RED | 4 | 8 | 9.97 | -9.97 | — | 25.0% | 14.06 | 20.21 | 6.52 | 17.26 | 1.61 |

Los tres N se muestran siempre. Son subconjuntos anidados del start; no se suman sus n. Las celdas pequeñas no permiten seleccionar el mejor N ni sugerir que su media establezca una regla. Comparaciones completas contra ALL/falling, mismo color y evento sin AO: `contrasts.csv`.

## 11. Expansion start por BBWP previo

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E_0_10 | ALL | 1 | 19 | -0.13 | -3.11 | [-7.33, 0.49] | 36.8% | 5.71 | 9.58 | 4.38 | 6.87 | 3.78 |
| E_0_10 | ALL | 2 | 19 | 2.60 | -1.61 | [-7.71, 4.53] | 47.4% | 11.61 | 14.25 | 7.31 | 9.29 | 3.80 |
| E_0_10 | ALL | 4 | 19 | 3.90 | -3.63 | [-12.74, 4.76] | 47.4% | 14.64 | 19.75 | 9.35 | 13.40 | 3.83 |
| E_0_10 | GREEN | 1 | 10 | -3.08 | -3.08 | [-7.77, 1.48] | 40.0% | 5.36 | 8.83 | 3.05 | 7.18 | 1.99 |
| E_0_10 | GREEN | 2 | 10 | 0.94 | 0.94 | [-7.87, 8.93] | 60.0% | 11.54 | 14.17 | 8.16 | 8.37 | 2.00 |
| E_0_10 | GREEN | 4 | 10 | 0.26 | 0.26 | [-11.70, 11.90] | 50.0% | 14.59 | 20.17 | 11.67 | 11.88 | 2.01 |
| E_0_10 | RED | 1 | 9 | 3.14 | -3.14 | — | 33.3% | 6.10 | 10.41 | 5.86 | 6.52 | 1.79 |
| E_0_10 | RED | 2 | 9 | 4.44 | -4.44 | — | 33.3% | 11.68 | 14.34 | 6.36 | 10.32 | 1.80 |
| E_0_10 | RED | 4 | 9 | 7.95 | -7.95 | — | 44.4% | 14.69 | 19.28 | 6.78 | 15.10 | 1.81 |
| E_10_20 | ALL | 1 | 10 | 5.43 | 0.99 | [-4.49, 6.68] | 50.0% | 6.52 | 10.45 | 7.53 | 4.52 | 1.99 |
| E_10_20 | ALL | 2 | 10 | 5.57 | 0.80 | [-5.44, 7.00] | 50.0% | 8.02 | 12.93 | 9.22 | 7.55 | 2.00 |
| E_10_20 | ALL | 4 | 10 | 3.54 | 4.82 | [-2.57, 13.31] | 60.0% | 10.45 | 17.91 | 14.60 | 9.37 | 2.01 |
| E_10_20 | GREEN | 1 | 5 | 6.42 | 6.42 | — | 80.0% | 7.53 | 11.05 | 10.20 | 1.89 | 1.00 |
| E_10_20 | GREEN | 2 | 5 | 6.37 | 6.37 | — | 60.0% | 9.55 | 14.01 | 12.82 | 4.55 | 1.00 |
| E_10_20 | GREEN | 4 | 5 | 8.35 | 8.35 | — | 60.0% | 15.37 | 21.11 | 19.71 | 6.04 | 1.01 |
| E_10_20 | RED | 1 | 5 | 4.44 | -4.44 | — | 20.0% | 5.50 | 9.84 | 4.86 | 7.15 | 1.00 |
| E_10_20 | RED | 2 | 5 | 4.77 | -4.77 | — | 40.0% | 6.48 | 11.86 | 5.62 | 10.54 | 1.00 |
| E_10_20 | RED | 4 | 5 | -1.28 | 1.28 | — | 60.0% | 5.54 | 14.71 | 9.49 | 12.70 | 1.01 |
| E_20_30 | ALL | 1 | 9 | 2.70 | 0.47 | — | 55.6% | 4.72 | 10.23 | 7.25 | 5.33 | 1.79 |
| E_20_30 | ALL | 2 | 9 | 4.41 | 1.98 | — | 66.7% | 10.68 | 15.84 | 10.38 | 8.34 | 1.80 |
| E_20_30 | ALL | 4 | 9 | 7.03 | 1.78 | — | 44.4% | 11.26 | 20.15 | 13.11 | 11.03 | 1.81 |
| E_20_30 | GREEN | 1 | 2 | 7.14 | 7.14 | — | 100.0% | 7.14 | 11.55 | 11.55 | 1.03 | 0.40 |
| E_20_30 | GREEN | 2 | 2 | 14.36 | 14.36 | — | 100.0% | 14.36 | 18.71 | 18.71 | 1.03 | 0.40 |
| E_20_30 | GREEN | 4 | 2 | 19.83 | 19.83 | — | 100.0% | 19.83 | 22.64 | 22.64 | 1.03 | 0.40 |
| E_20_30 | RED | 1 | 7 | 1.43 | -1.43 | — | 42.9% | 4.02 | 9.86 | 6.02 | 6.56 | 1.39 |
| E_20_30 | RED | 2 | 7 | 1.56 | -1.56 | — | 57.1% | 9.63 | 15.02 | 8.00 | 10.43 | 1.40 |
| E_20_30 | RED | 4 | 7 | 3.37 | -3.37 | — | 28.6% | 8.81 | 19.43 | 10.38 | 13.89 | 1.41 |
| E_30_50 | ALL | 1 | 5 | -0.78 | -0.01 | — | 20.0% | 3.20 | 8.12 | 6.04 | 3.89 | 1.00 |
| E_30_50 | ALL | 2 | 5 | -5.83 | 4.43 | — | 60.0% | 5.83 | 11.57 | 10.78 | 4.27 | 1.00 |
| E_30_50 | ALL | 4 | 5 | 4.98 | 5.90 | — | 40.0% | 11.05 | 18.67 | 17.32 | 5.39 | 1.01 |
| E_30_50 | GREEN | 1 | 2 | -0.99 | -0.99 | — | 0.0% | 0.99 | 4.10 | 0.73 | 4.10 | 0.40 |
| E_30_50 | GREEN | 2 | 2 | -1.75 | -1.75 | — | 0.0% | 1.75 | 5.66 | 3.70 | 5.05 | 0.40 |
| E_30_50 | GREEN | 4 | 2 | 13.60 | 13.60 | — | 50.0% | 16.65 | 20.43 | 18.01 | 5.51 | 0.40 |
| E_30_50 | RED | 1 | 3 | -0.63 | 0.63 | — | 33.3% | 4.67 | 10.79 | 9.57 | 3.75 | 0.60 |
| E_30_50 | RED | 2 | 3 | -8.55 | 8.55 | — | 100.0% | 8.55 | 15.51 | 15.51 | 3.75 | 0.60 |
| E_30_50 | RED | 4 | 3 | -0.77 | 0.77 | — | 33.3% | 7.31 | 17.49 | 16.86 | 5.31 | 0.60 |
| E_GT50 | ALL | 1 | 7 | 0.40 | 1.60 | — | 42.9% | 2.99 | 9.26 | 7.50 | 5.53 | 1.39 |
| E_GT50 | ALL | 2 | 7 | -3.99 | 3.25 | — | 42.9% | 5.49 | 11.38 | 11.35 | 6.41 | 1.40 |
| E_GT50 | ALL | 4 | 7 | -2.09 | 2.20 | — | 57.1% | 10.60 | 19.47 | 17.40 | 10.30 | 1.41 |
| E_GT50 | GREEN | 1 | 1 | 6.98 | 6.98 | — | 100.0% | 6.98 | 9.71 | 9.71 | 0.55 | 0.20 |
| E_GT50 | GREEN | 2 | 1 | -2.59 | -2.59 | — | 0.0% | 2.59 | 9.71 | 9.71 | 4.27 | 0.20 |
| E_GT50 | GREEN | 4 | 1 | 0.39 | 0.39 | — | 100.0% | 0.39 | 9.71 | 9.71 | 4.91 | 0.20 |
| E_GT50 | RED | 1 | 6 | -0.70 | 0.70 | — | 33.3% | 2.32 | 9.18 | 7.13 | 6.35 | 1.19 |
| E_GT50 | RED | 2 | 6 | -4.22 | 4.22 | — | 50.0% | 5.98 | 11.66 | 11.62 | 6.76 | 1.20 |
| E_GT50 | RED | 4 | 6 | -2.50 | 2.50 | — | 50.0% | 12.30 | 21.09 | 18.68 | 11.20 | 1.21 |

Buckets disjuntos del BBWP **anterior**, con extremos documentados en §4. Todos se publican, incluidos n=0 e IC omitidos; ninguna ausencia de outcome se trata como fallo direccional. No se elige un bucket por rentabilidad aparente.

## 12. Zona 50, descriptiva

| Evento | AO | h semanas | n | µ R | µ firmado | IC95 firmado | Hit | µ abs | µ max abs | MFE | MAE | Observaciones/año |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_CROSS50 | ALL | 1 | 21 | 1.02 | 1.07 | [-1.57, 3.55] | 47.6% | 4.52 | 8.99 | 7.33 | 3.94 | 4.18 |
| F_CROSS50 | ALL | 2 | 21 | 4.50 | 2.88 | [-1.87, 7.08] | 66.7% | 7.44 | 12.34 | 9.98 | 5.49 | 4.20 |
| F_CROSS50 | ALL | 4 | 21 | 4.31 | 7.12 | [2.55, 12.06] | 66.7% | 9.27 | 17.09 | 14.79 | 6.79 | 4.23 |
| F_CROSS50 | GREEN | 1 | 12 | 1.83 | 1.83 | [-0.55, 4.31] | 50.0% | 3.16 | 6.79 | 5.24 | 3.27 | 2.39 |
| F_CROSS50 | GREEN | 2 | 12 | 6.46 | 6.46 | [2.57, 10.90] | 75.0% | 6.61 | 10.34 | 9.76 | 3.59 | 2.40 |
| F_CROSS50 | GREEN | 4 | 12 | 10.00 | 10.00 | [2.51, 18.06] | 75.0% | 11.39 | 17.03 | 16.74 | 4.25 | 2.42 |
| F_CROSS50 | RED | 1 | 9 | -0.05 | 0.05 | — | 44.4% | 6.33 | 11.93 | 10.12 | 4.84 | 1.79 |
| F_CROSS50 | RED | 2 | 9 | 1.89 | -1.89 | — | 55.6% | 8.54 | 15.02 | 10.28 | 8.02 | 1.80 |
| F_CROSS50 | RED | 4 | 9 | -3.27 | 3.27 | — | 55.6% | 6.44 | 17.18 | 12.20 | 10.19 | 1.81 |
| F_BELOW50_RISING | ALL | 1 | 62 | 0.40 | -0.88 | [-2.97, 1.08] | 45.2% | 5.19 | 8.79 | 5.06 | 5.69 | 12.35 |
| F_BELOW50_RISING | ALL | 2 | 62 | -0.21 | -0.39 | [-3.28, 2.59] | 48.4% | 8.54 | 12.63 | 7.43 | 8.03 | 12.39 |
| F_BELOW50_RISING | ALL | 4 | 62 | 1.43 | -1.99 | [-6.13, 2.36] | 43.5% | 10.85 | 16.65 | 9.74 | 10.93 | 12.49 |
| F_BELOW50_RISING | GREEN | 1 | 28 | -0.54 | -0.54 | [-3.57, 2.33] | 46.4% | 5.59 | 8.59 | 5.02 | 5.47 | 5.58 |
| F_BELOW50_RISING | GREEN | 2 | 28 | -0.67 | -0.67 | [-5.29, 4.09] | 46.4% | 9.56 | 12.94 | 7.78 | 7.92 | 5.60 |
| F_BELOW50_RISING | GREEN | 4 | 28 | -0.61 | -0.61 | [-7.85, 7.30] | 46.4% | 12.69 | 18.08 | 10.83 | 10.72 | 5.64 |
| F_BELOW50_RISING | RED | 1 | 34 | 1.17 | -1.17 | [-4.12, 1.30] | 44.1% | 4.86 | 8.97 | 5.09 | 5.88 | 6.77 |
| F_BELOW50_RISING | RED | 2 | 34 | 0.16 | -0.16 | [-3.98, 3.78] | 50.0% | 7.71 | 12.37 | 7.14 | 8.13 | 6.80 |
| F_BELOW50_RISING | RED | 4 | 34 | 3.12 | -3.12 | [-8.61, 1.35] | 41.2% | 9.33 | 15.47 | 8.83 | 11.11 | 6.85 |
| F_ABOVE50_RISING | ALL | 1 | 63 | 1.30 | 0.91 | [-0.72, 2.37] | 52.4% | 4.41 | 8.59 | 6.23 | 4.88 | 12.55 |
| F_ABOVE50_RISING | ALL | 2 | 63 | 2.26 | 1.88 | [-0.70, 4.49] | 58.7% | 6.12 | 11.18 | 8.51 | 6.25 | 12.59 |
| F_ABOVE50_RISING | ALL | 4 | 63 | 2.78 | 3.32 | [-0.17, 7.51] | 55.6% | 8.56 | 15.90 | 12.67 | 8.53 | 12.69 |
| F_ABOVE50_RISING | GREEN | 1 | 32 | 2.17 | 2.17 | [0.14, 4.14] | 59.4% | 4.18 | 7.35 | 5.53 | 3.87 | 6.37 |
| F_ABOVE50_RISING | GREEN | 2 | 32 | 4.08 | 4.08 | [0.61, 7.74] | 62.5% | 5.92 | 10.11 | 8.59 | 4.69 | 6.40 |
| F_ABOVE50_RISING | GREEN | 4 | 32 | 6.00 | 6.00 | [0.07, 11.85] | 65.6% | 9.74 | 15.57 | 13.80 | 6.09 | 6.45 |
| F_ABOVE50_RISING | RED | 1 | 31 | 0.40 | -0.40 | [-2.77, 1.60] | 45.2% | 4.65 | 9.86 | 6.96 | 5.93 | 6.17 |
| F_ABOVE50_RISING | RED | 2 | 31 | 0.39 | -0.39 | [-3.94, 2.44] | 54.8% | 6.33 | 12.29 | 8.42 | 7.86 | 6.20 |
| F_ABOVE50_RISING | RED | 4 | 31 | -0.55 | 0.55 | [-4.00, 5.07] | 45.2% | 7.34 | 16.25 | 11.51 | 11.05 | 6.25 |

Semanas válidas exactamente BBWP=50 y rising: 2. Se conserva el cruce estricto >50 del frozen feature. No se interpreta 50 como predictivo sin evidencia incremental estable.

## 13. ADX/DI secundario — no entra en la hipótesis principal

| AO | BBWP / ADX / DI | h | n | µ firmado | IC95 | Hit | µ max abs | P(max≥10) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN | A_RISING / ADX_RISING / DI_BULLISH | 1 | 26 | 2.37 | [-0.68, 4.95] | 57.7% | 8.29 | 26.9% |
| GREEN | A_RISING / ADX_RISING / DI_BEARISH | 1 | 9 | 2.26 | — | 66.7% | 5.79 | 0.0% |
| GREEN | A_RISING / ADX_RISING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| GREEN | A_RISING / ADX_FALLING / DI_BULLISH | 1 | 14 | 1.21 | [-2.67, 4.32] | 50.0% | 7.29 | 21.4% |
| GREEN | A_RISING / ADX_FALLING / DI_BEARISH | 1 | 12 | -3.71 | [-10.54, 0.89] | 33.3% | 9.23 | 33.3% |
| GREEN | A_RISING / ADX_FALLING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_RISING / DI_BULLISH | 1 | 32 | -0.17 | [-1.41, 1.12] | 43.8% | 7.42 | 18.8% |
| GREEN | B_FALLING / ADX_RISING / DI_BEARISH | 1 | 11 | 1.43 | [-3.89, 7.31] | 54.5% | 7.31 | 9.1% |
| GREEN | B_FALLING / ADX_RISING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_FALLING / DI_BULLISH | 1 | 11 | 1.99 | [-1.51, 6.09] | 45.5% | 8.63 | 18.2% |
| GREEN | B_FALLING / ADX_FALLING / DI_BEARISH | 1 | 15 | -1.27 | [-4.33, 3.13] | 33.3% | 8.13 | 33.3% |
| GREEN | B_FALLING / ADX_FALLING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_RISING / DI_BULLISH | 1 | 4 | -2.92 | — | 25.0% | 9.26 | 25.0% |
| RED | A_RISING / ADX_RISING / DI_BEARISH | 1 | 20 | 0.69 | [-2.34, 2.90] | 50.0% | 10.96 | 45.0% |
| RED | A_RISING / ADX_RISING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_FALLING / DI_BULLISH | 1 | 19 | -1.72 | [-5.94, 1.59] | 42.1% | 8.89 | 31.6% |
| RED | A_RISING / ADX_FALLING / DI_BEARISH | 1 | 23 | -0.64 | [-3.15, 1.67] | 47.8% | 8.47 | 26.1% |
| RED | A_RISING / ADX_FALLING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_RISING / DI_BULLISH | 1 | 5 | -2.57 | — | 40.0% | 7.97 | 20.0% |
| RED | B_FALLING / ADX_RISING / DI_BEARISH | 1 | 10 | 3.38 | [-4.09, 9.41] | 60.0% | 12.25 | 50.0% |
| RED | B_FALLING / ADX_RISING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_FALLING / DI_BULLISH | 1 | 23 | 0.73 | [-2.11, 4.28] | 65.2% | 8.51 | 26.1% |
| RED | B_FALLING / ADX_FALLING / DI_BEARISH | 1 | 14 | 1.94 | [-1.89, 6.04] | 57.1% | 9.07 | 50.0% |
| RED | B_FALLING / ADX_FALLING / DI_NEUTRAL | 1 | 0 | — | — | — | — | — |
| GREEN | A_RISING / ADX_RISING / DI_BULLISH | 2 | 26 | 4.28 | [-0.73, 8.98] | 57.7% | 10.90 | 38.5% |
| GREEN | A_RISING / ADX_RISING / DI_BEARISH | 2 | 9 | 3.97 | — | 66.7% | 10.95 | 55.6% |
| GREEN | A_RISING / ADX_RISING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| GREEN | A_RISING / ADX_FALLING / DI_BULLISH | 2 | 14 | 2.35 | [-3.48, 6.66] | 64.3% | 10.54 | 42.9% |
| GREEN | A_RISING / ADX_FALLING / DI_BEARISH | 2 | 12 | -5.63 | [-15.94, 1.50] | 33.3% | 13.47 | 50.0% |
| GREEN | A_RISING / ADX_FALLING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_RISING / DI_BULLISH | 2 | 32 | -0.74 | [-2.56, 1.30] | 43.8% | 9.73 | 37.5% |
| GREEN | B_FALLING / ADX_RISING / DI_BEARISH | 2 | 11 | 1.93 | [-2.66, 6.57] | 63.6% | 9.05 | 18.2% |
| GREEN | B_FALLING / ADX_RISING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_FALLING / DI_BULLISH | 2 | 10 | 4.64 | [-6.89, 16.75] | 60.0% | 16.66 | 70.0% |
| GREEN | B_FALLING / ADX_FALLING / DI_BEARISH | 2 | 15 | -4.15 | [-8.34, 2.38] | 40.0% | 12.11 | 53.3% |
| GREEN | B_FALLING / ADX_FALLING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_RISING / DI_BULLISH | 2 | 4 | -1.53 | — | 50.0% | 11.51 | 50.0% |
| RED | A_RISING / ADX_RISING / DI_BEARISH | 2 | 20 | 0.99 | [-4.06, 4.73] | 65.0% | 12.91 | 60.0% |
| RED | A_RISING / ADX_RISING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_FALLING / DI_BULLISH | 2 | 19 | -1.05 | [-6.28, 5.22] | 42.1% | 12.82 | 57.9% |
| RED | A_RISING / ADX_FALLING / DI_BEARISH | 2 | 23 | -0.57 | [-4.35, 3.27] | 47.8% | 11.45 | 47.8% |
| RED | A_RISING / ADX_FALLING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_RISING / DI_BULLISH | 2 | 5 | -4.18 | — | 20.0% | 12.52 | 40.0% |
| RED | B_FALLING / ADX_RISING / DI_BEARISH | 2 | 10 | 3.75 | [-5.00, 12.06] | 50.0% | 16.82 | 60.0% |
| RED | B_FALLING / ADX_RISING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_FALLING / DI_BULLISH | 2 | 23 | -0.01 | [-4.01, 3.42] | 56.5% | 12.47 | 47.8% |
| RED | B_FALLING / ADX_FALLING / DI_BEARISH | 2 | 14 | 0.99 | [-6.07, 8.87] | 50.0% | 16.31 | 92.9% |
| RED | B_FALLING / ADX_FALLING / DI_NEUTRAL | 2 | 0 | — | — | — | — | — |
| GREEN | A_RISING / ADX_RISING / DI_BULLISH | 4 | 26 | 6.32 | [-0.72, 12.59] | 61.5% | 15.35 | 69.2% |
| GREEN | A_RISING / ADX_RISING / DI_BEARISH | 4 | 9 | 2.49 | — | 55.6% | 14.28 | 77.8% |
| GREEN | A_RISING / ADX_RISING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| GREEN | A_RISING / ADX_FALLING / DI_BULLISH | 4 | 14 | 6.83 | [-1.97, 14.93] | 78.6% | 17.21 | 78.6% |
| GREEN | A_RISING / ADX_FALLING / DI_BEARISH | 4 | 12 | -8.25 | [-19.64, 2.30] | 25.0% | 20.60 | 83.3% |
| GREEN | A_RISING / ADX_FALLING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_RISING / DI_BULLISH | 4 | 30 | -2.56 | [-7.49, 1.21] | 33.3% | 14.37 | 73.3% |
| GREEN | B_FALLING / ADX_RISING / DI_BEARISH | 4 | 11 | 0.11 | [-10.13, 10.07] | 36.4% | 14.99 | 81.8% |
| GREEN | B_FALLING / ADX_RISING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| GREEN | B_FALLING / ADX_FALLING / DI_BULLISH | 4 | 10 | 13.13 | [-3.43, 33.74] | 80.0% | 24.11 | 90.0% |
| GREEN | B_FALLING / ADX_FALLING / DI_BEARISH | 4 | 15 | 0.16 | [-12.48, 19.71] | 46.7% | 24.38 | 100.0% |
| GREEN | B_FALLING / ADX_FALLING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_RISING / DI_BULLISH | 4 | 4 | -8.38 | — | 50.0% | 20.80 | 100.0% |
| RED | A_RISING / ADX_RISING / DI_BEARISH | 4 | 20 | 0.94 | [-6.07, 6.91] | 45.0% | 16.70 | 70.0% |
| RED | A_RISING / ADX_RISING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| RED | A_RISING / ADX_FALLING / DI_BULLISH | 4 | 19 | -2.41 | [-7.72, 3.91] | 42.1% | 16.16 | 84.2% |
| RED | A_RISING / ADX_FALLING / DI_BEARISH | 4 | 23 | -0.53 | [-4.61, 4.18] | 43.5% | 14.11 | 60.9% |
| RED | A_RISING / ADX_FALLING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_RISING / DI_BULLISH | 4 | 5 | -15.73 | — | 40.0% | 23.86 | 100.0% |
| RED | B_FALLING / ADX_RISING / DI_BEARISH | 4 | 10 | 5.01 | [-8.18, 19.38] | 50.0% | 21.80 | 80.0% |
| RED | B_FALLING / ADX_RISING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |
| RED | B_FALLING / ADX_FALLING / DI_BULLISH | 4 | 23 | 1.25 | [-5.24, 6.88] | 52.2% | 17.16 | 82.6% |
| RED | B_FALLING / ADX_FALLING / DI_BEARISH | 4 | 14 | 0.83 | [-8.84, 12.01] | 50.0% | 21.18 | 100.0% |
| RED | B_FALLING / ADX_FALLING / DI_NEUTRAL | 4 | 0 | — | — | — | — | — |

Foco solicitado: RED+rising BBWP+−DI leads+ADX falling y el equivalente GREEN/+DI. El lift firmado respecto al mismo AO/BBWP, y respecto a ADX rising con el mismo DI, es:

| AO | h | Referencia | n evento/control | Lift firmado | IC95 | Ex mejores 3 |
| --- | --- | --- | --- | --- | --- | --- |
| GREEN | 1 | SAME_AO_BBWP | 14/61 | 0.32 | [-3.39, 3.52] | -2.23 |
| GREEN | 1 | OTHER_ADX_SAME_DI | 14/26 | -1.15 | [-6.00, 3.59] | -3.71 |
| RED | 1 | SAME_AO_BBWP | 23/66 | 0.05 | [-1.71, 1.95] | -1.61 |
| RED | 1 | OTHER_ADX_SAME_DI | 23/20 | -1.33 | [-4.55, 1.97] | -2.98 |
| GREEN | 2 | SAME_AO_BBWP | 14/61 | 0.51 | [-4.77, 5.14] | -2.30 |
| GREEN | 2 | OTHER_ADX_SAME_DI | 14/26 | -1.92 | [-9.53, 4.64] | -4.73 |
| RED | 2 | SAME_AO_BBWP | 23/66 | -0.28 | [-3.55, 3.44] | -2.51 |
| RED | 2 | OTHER_ADX_SAME_DI | 23/20 | -1.56 | [-7.35, 4.82] | -3.79 |
| GREEN | 4 | SAME_AO_BBWP | 14/61 | 3.82 | [-3.13, 12.03] | -0.87 |
| GREEN | 4 | OTHER_ADX_SAME_DI | 14/26 | 0.51 | [-9.32, 10.02] | -4.18 |
| RED | 4 | SAME_AO_BBWP | 23/66 | 0.57 | [-2.96, 5.51] | -1.64 |
| RED | 4 | OTHER_ADX_SAME_DI | 23/20 | -1.47 | [-8.98, 6.66] | -3.68 |

Esto admite observar movimientos mientras ADX cae sin convertir ADX en dirección. La tabla no prueba precedencia causal de ADX ni una nueva condición: cohortes pequeñas, solapamiento y múltiples comparaciones. No se optimiza ni se añade ADX a la regla.

## 14. Robustez temporal, régimen y controles causales

| Época | h | n rising/falling | Lift |R| | Lift max abs | GREEN rising n / µ firmado | RED rising n / µ firmado |
| --- | --- | --- | --- | --- | --- | --- |
| 2020-2022 | 1 | 31/31 | -0.56 | -0.83 | 15 / -0.58 | 16 / -1.79 |
| 2020-2022 | 2 | 31/31 | -2.64 | -3.67 | 15 / -2.34 | 16 / 0.01 |
| 2020-2022 | 4 | 31/31 | -7.88 | -7.87 | 15 / -4.88 | 16 / 1.56 |
| 2023-2024 | 1 | 48/50 | -0.31 | -0.04 | 25 / 2.87 | 23 / -2.05 |
| 2023-2024 | 2 | 48/50 | 0.08 | -0.63 | 25 / 5.08 | 23 / -2.24 |
| 2023-2024 | 4 | 48/50 | 0.20 | -0.77 | 25 / 8.95 | 23 / -5.53 |
| 2025-2026 | 1 | 48/40 | 0.35 | 1.53 | 21 / -0.42 | 27 / 1.13 |
| 2025-2026 | 2 | 48/39 | 1.69 | 1.69 | 21 / 0.98 | 27 / 1.19 |
| 2025-2026 | 4 | 48/37 | -0.53 | -0.27 | 21 / 1.56 | 27 / 1.10 |

2020–2022 significa realmente desde 2021-10-11 en esta cohorte. Los signos de las diferencias cambian entre épocas. 2024+ fue reutilizado en estudios previos: **TEST REUSED / NO VIRGIN HOLDOUT**. Ninguna regla se selecciona mirando una supuesta muestra test nueva.

| Régimen causal 4H | h | n rising/falling | Lift |R| | Lift max abs | GREEN n / firmado | RED n / firmado |
| --- | --- | --- | --- | --- | --- | --- |
| BULL | 1 | 64/59 | 0.56 | 0.36 | 52 / 0.87 | 12 / -1.96 |
| BULL | 2 | 64/58 | 0.22 | -0.62 | 52 / 1.94 | 12 / -0.42 |
| BULL | 4 | 64/56 | 1.41 | 0.09 | 52 / 4.00 | 12 / -2.98 |
| BEAR | 1 | 63/62 | -0.89 | 0.17 | 9 / 0.99 | 54 / -0.40 |
| BEAR | 2 | 63/62 | -0.49 | -0.75 | 9 / 1.26 | 54 / -0.26 |
| BEAR | 4 | 63/62 | -5.79 | -5.19 | 9 / -2.76 | 54 / -0.68 |

Fases de observaciones no solapadas: las cuatro se publican, sin elegir la más favorable. La fase se fija por índice semanal desde la primera semana completa. Para h<=4, cada fase usa anclas separadas por cuatro semanas.

| Fase | h | n all / rising / falling | Lift |R| | Lift max abs | GREEN rising firmado | RED rising firmado |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 66 / 32 / 31 | 0.06 | 1.18 | -1.00 | 0.26 |
| 0 | 2 | 66 / 32 / 31 | 2.02 | 1.51 | -0.51 | 3.43 |
| 0 | 4 | 65 / 32 / 30 | -1.99 | -2.44 | 2.03 | 2.03 |
| 1 | 1 | 66 / 28 / 32 | -0.59 | 0.56 | 1.43 | 2.94 |
| 1 | 2 | 65 / 28 / 31 | -1.47 | -0.38 | 3.26 | 5.35 |
| 1 | 4 | 65 / 28 / 31 | -1.47 | -1.27 | 4.44 | 2.85 |
| 2 | 1 | 65 / 34 / 27 | -1.27 | -0.35 | 2.96 | -3.01 |
| 2 | 2 | 65 / 34 / 27 | -1.10 | -2.85 | 4.73 | -4.01 |
| 2 | 4 | 65 / 34 / 27 | -0.34 | -1.85 | 6.82 | -5.61 |
| 3 | 1 | 65 / 33 / 31 | 0.82 | -0.55 | 0.41 | -2.64 |
| 3 | 2 | 65 / 33 / 31 | 0.04 | -1.15 | 0.35 | -5.00 |
| 3 | 4 | 64 / 33 / 30 | -5.25 | -5.03 | -1.20 | -3.01 |

Control local sin lookahead: media de >=12 outcomes ya maduros de las 52 semanas previas (j+h<=i). Exceso del evento frente a esa media observable en su cierre:

| Evento | AO | h | Métrica | n | Exceso medio pp | IC95 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | ALL | 1 | absolute | 250 | -0.20 | [-0.70, 0.27] |
| ALL | ALL | 1 | max_move | 250 | -0.45 | [-1.14, 0.20] |
| ALL | ALL | 1 | signed | 250 | 0.44 | [-0.42, 1.26] |
| A_RISING | ALL | 1 | absolute | 121 | -0.33 | [-0.97, 0.36] |
| A_RISING | ALL | 1 | max_move | 121 | -0.29 | [-1.24, 0.63] |
| A_RISING | ALL | 1 | signed | 121 | 0.06 | [-1.18, 1.14] |
| B_FALLING | ALL | 1 | absolute | 115 | -0.22 | [-1.07, 0.70] |
| B_FALLING | ALL | 1 | max_move | 115 | -0.72 | [-1.67, 0.20] |
| B_FALLING | ALL | 1 | signed | 115 | 0.60 | [-0.83, 2.05] |
| C_START | ALL | 1 | absolute | 48 | -0.19 | [-1.53, 1.52] |
| C_START | ALL | 1 | max_move | 48 | 0.51 | [-1.24, 2.37] |
| C_START | ALL | 1 | signed | 48 | -0.70 | [-2.87, 1.14] |
| A_RISING | GREEN | 1 | absolute | 58 | -0.34 | [-1.36, 0.73] |
| A_RISING | GREEN | 1 | max_move | 58 | -1.17 | [-2.45, 0.13] |
| A_RISING | GREEN | 1 | signed | 58 | 0.54 | [-1.32, 1.95] |
| A_RISING | RED | 1 | absolute | 63 | -0.32 | [-1.20, 0.86] |
| A_RISING | RED | 1 | max_move | 63 | 0.51 | [-0.70, 1.81] |
| A_RISING | RED | 1 | signed | 63 | -0.38 | [-2.47, 1.25] |
| ALL | ALL | 2 | absolute | 248 | -0.28 | [-1.22, 0.62] |
| ALL | ALL | 2 | max_move | 248 | -0.66 | [-1.70, 0.38] |
| ALL | ALL | 2 | signed | 248 | 0.73 | [-0.78, 2.27] |
| A_RISING | ALL | 2 | absolute | 121 | -0.33 | [-1.55, 1.05] |
| A_RISING | ALL | 2 | max_move | 121 | -0.92 | [-2.34, 0.65] |
| A_RISING | ALL | 2 | signed | 121 | 0.79 | [-1.02, 2.58] |
| B_FALLING | ALL | 2 | absolute | 113 | -0.66 | [-2.07, 0.76] |
| B_FALLING | ALL | 2 | max_move | 113 | -0.77 | [-2.16, 0.66] |
| B_FALLING | ALL | 2 | signed | 113 | 0.10 | [-1.67, 2.01] |
| C_START | ALL | 2 | absolute | 48 | 1.53 | [-0.24, 3.38] |
| C_START | ALL | 2 | max_move | 48 | 0.50 | [-1.30, 2.30] |
| C_START | ALL | 2 | signed | 48 | 1.01 | [-2.27, 4.09] |
| A_RISING | GREEN | 2 | absolute | 58 | -0.17 | [-2.26, 2.18] |
| A_RISING | GREEN | 2 | max_move | 58 | -1.51 | [-3.76, 1.32] |
| A_RISING | GREEN | 2 | signed | 58 | 1.41 | [-1.67, 4.03] |
| A_RISING | RED | 2 | absolute | 63 | -0.48 | [-1.94, 1.09] |
| A_RISING | RED | 2 | max_move | 63 | -0.38 | [-1.93, 1.19] |
| A_RISING | RED | 2 | signed | 63 | 0.23 | [-2.55, 2.59] |
| ALL | ALL | 4 | absolute | 244 | -0.33 | [-2.21, 1.75] |
| ALL | ALL | 4 | max_move | 244 | -0.90 | [-2.80, 1.15] |
| ALL | ALL | 4 | signed | 244 | 1.33 | [-1.38, 4.32] |
| A_RISING | ALL | 4 | absolute | 120 | -1.41 | [-3.40, 0.67] |
| A_RISING | ALL | 4 | max_move | 120 | -1.96 | [-4.10, 0.33] |
| A_RISING | ALL | 4 | signed | 120 | 1.25 | [-1.48, 4.12] |
| B_FALLING | ALL | 4 | absolute | 110 | 0.14 | [-2.20, 2.87] |
| B_FALLING | ALL | 4 | max_move | 110 | -0.42 | [-2.61, 2.04] |
| B_FALLING | ALL | 4 | signed | 110 | 0.98 | [-2.32, 4.73] |
| C_START | ALL | 4 | absolute | 47 | 1.07 | [-1.97, 4.54] |
| C_START | ALL | 4 | max_move | 47 | 0.74 | [-2.20, 4.03] |
| C_START | ALL | 4 | signed | 47 | 1.83 | [-3.29, 6.45] |
| A_RISING | GREEN | 4 | absolute | 58 | -0.07 | [-3.35, 3.21] |
| A_RISING | GREEN | 4 | max_move | 58 | -1.47 | [-4.87, 2.22] |
| A_RISING | GREEN | 4 | signed | 58 | 2.73 | [-2.06, 6.83] |
| A_RISING | RED | 4 | absolute | 62 | -2.67 | [-4.63, -0.27] |
| A_RISING | RED | 4 | max_move | 62 | -2.41 | [-4.53, -0.00] |
| A_RISING | RED | 4 | signed | 62 | -0.13 | [-4.99, 3.69] |

Los CSV contienen además cada evento/bucket por todas las épocas y ambos regímenes; no se extrapola una celda de época/régimen al conjunto del mercado.

## 15. Sensitivity: ex-best-1 y ex-best-3

| Evento | AO | h | n | Firmado mediana / p10 / p90 | |R| mediana / p10 / p90 | Max abs mediana / p10 / p90 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | ALL | 1 | 262 | 0.13 / -7.78 / 9.12 | 3.44 / 0.52 / 11.07 | 7.27 / 3.51 / 15.15 |
| ALL | ALL | 2 | 261 | 0.32 / -11.50 / 12.40 | 5.97 / 0.85 / 17.07 | 9.94 / 5.28 / 22.43 |
| ALL | ALL | 4 | 259 | -0.55 / -16.89 / 20.95 | 8.56 / 1.22 / 24.29 | 15.61 / 7.69 / 30.55 |
| ALL | GREEN | 1 | 138 | 0.04 / -5.82 / 9.16 | 3.20 / 0.52 / 10.49 | 6.70 / 3.42 / 13.43 |
| ALL | GREEN | 2 | 137 | 0.69 / -10.12 / 12.15 | 5.32 / 0.81 / 18.00 | 9.43 / 5.05 / 22.69 |
| ALL | GREEN | 4 | 135 | 0.12 / -18.05 / 24.76 | 9.54 / 1.50 / 24.92 | 15.87 / 7.29 / 32.69 |
| ALL | RED | 1 | 124 | 0.31 / -8.71 / 8.71 | 3.85 / 0.53 / 11.38 | 8.05 / 3.75 / 16.04 |
| ALL | RED | 2 | 124 | 0.12 / -11.98 / 12.29 | 6.05 / 1.06 / 16.23 | 10.67 / 6.16 / 22.11 |
| ALL | RED | 4 | 124 | -0.59 / -15.74 / 14.47 | 7.75 / 1.07 / 23.32 | 15.52 / 8.01 / 28.56 |
| A_RISING | ALL | 1 | 127 | -0.03 / -8.02 / 8.37 | 3.42 / 0.51 / 10.17 | 7.23 / 3.64 / 15.99 |
| A_RISING | ALL | 2 | 127 | 0.74 / -10.82 / 11.95 | 5.98 / 0.80 / 16.86 | 9.92 / 5.44 / 21.27 |
| A_RISING | ALL | 4 | 127 | 0.12 / -15.44 / 16.24 | 7.33 / 1.18 / 22.36 | 14.46 / 7.54 / 28.01 |
| A_RISING | GREEN | 1 | 61 | 0.51 / -6.91 / 9.14 | 3.07 / 0.48 / 11.19 | 5.64 / 3.26 / 14.62 |
| A_RISING | GREEN | 2 | 61 | 0.95 / -10.00 / 12.92 | 6.26 / 0.77 / 18.86 | 9.70 / 5.22 / 22.64 |
| A_RISING | GREEN | 4 | 61 | 1.54 / -15.78 / 23.79 | 8.76 / 1.27 / 24.66 | 15.16 / 6.04 / 29.03 |
| A_RISING | RED | 1 | 66 | -0.53 / -8.40 / 7.32 | 3.70 / 0.57 / 9.50 | 8.31 / 4.60 / 16.00 |
| A_RISING | RED | 2 | 66 | 0.12 / -10.85 / 11.33 | 5.98 / 0.91 / 14.70 | 10.33 / 6.40 / 20.72 |
| A_RISING | RED | 4 | 66 | -0.84 / -14.13 / 13.14 | 6.19 / 1.17 / 17.33 | 14.24 / 8.42 / 26.03 |
| B_FALLING | ALL | 1 | 121 | 0.02 / -7.54 / 10.05 | 3.45 / 0.53 / 11.18 | 7.30 / 3.45 / 14.43 |
| B_FALLING | ALL | 2 | 120 | -0.06 / -11.93 / 10.82 | 5.68 / 1.22 / 17.07 | 10.29 / 5.04 / 23.75 |
| B_FALLING | ALL | 4 | 118 | -1.68 / -18.23 / 22.53 | 9.48 / 1.51 / 24.47 | 16.84 / 8.83 / 31.35 |
| B_FALLING | GREEN | 1 | 69 | -0.53 / -5.59 / 6.24 | 3.19 / 0.54 / 9.88 | 7.06 / 3.52 / 12.10 |
| B_FALLING | GREEN | 2 | 68 | -0.38 / -10.45 / 8.16 | 4.99 / 1.28 / 14.44 | 8.89 / 5.03 / 19.66 |
| B_FALLING | GREEN | 4 | 66 | -2.52 / -19.19 / 22.78 | 8.87 / 1.79 / 23.53 | 16.05 / 8.80 / 31.67 |
| B_FALLING | RED | 1 | 52 | 0.77 / -8.46 / 11.44 | 4.35 / 0.39 / 13.27 | 7.92 / 3.28 / 16.25 |
| B_FALLING | RED | 2 | 52 | 0.07 / -11.99 / 13.83 | 7.15 / 1.25 / 18.42 | 12.61 / 5.30 / 26.46 |
| B_FALLING | RED | 4 | 52 | -0.26 / -16.02 / 21.34 | 9.87 / 1.10 / 25.37 | 18.20 / 9.07 / 30.70 |
| C_START | ALL | 1 | 50 | -0.86 / -7.52 / 8.03 | 2.84 / 0.62 / 11.88 | 7.67 / 3.65 / 18.86 |
| C_START | ALL | 2 | 50 | 0.61 / -16.99 / 14.67 | 7.99 / 0.99 / 18.02 | 12.01 / 5.89 / 22.45 |
| C_START | ALL | 4 | 50 | -0.06 / -16.54 / 23.88 | 10.53 / 1.27 / 25.92 | 16.86 / 8.06 / 30.38 |
| C_START | GREEN | 1 | 20 | 0.54 / -6.97 / 11.88 | 2.93 / 0.51 / 12.82 | 6.21 / 3.36 / 17.98 |
| C_START | GREEN | 2 | 20 | 5.11 / -12.60 / 17.12 | 9.26 / 0.99 / 20.01 | 12.01 / 4.79 / 22.88 |
| C_START | GREEN | 4 | 20 | 4.33 / -15.52 / 25.57 | 15.49 / 2.88 / 25.92 | 19.59 / 5.84 / 30.64 |
| C_START | RED | 1 | 30 | -1.49 / -8.10 / 4.86 | 2.82 / 0.76 / 9.02 | 8.09 / 4.35 / 18.89 |
| C_START | RED | 2 | 30 | -0.09 / -16.99 / 13.55 | 7.85 / 1.13 / 16.99 | 13.04 / 6.38 / 21.59 |
| C_START | RED | 4 | 30 | -1.17 / -17.15 / 12.33 | 8.21 / 1.21 / 24.72 | 16.19 / 8.69 / 28.70 |

| Evento | AO | h | n | Firmado all / ex1 / ex3 | |R| all / ex1 / ex3 | Max abs all / ex1 / ex3 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | ALL | 1 | 262 | 0.46 / 0.37 / 0.20 | 4.93 / 4.84 / 4.70 | 8.57 / 8.47 / 8.31 |
| ALL | ALL | 2 | 261 | 0.67 / 0.54 / 0.30 | 7.47 / 7.37 / 7.18 | 12.31 / 12.20 / 12.01 |
| ALL | ALL | 4 | 259 | 0.91 / 0.74 / 0.42 | 11.13 / 10.98 / 10.73 | 17.76 / 17.63 / 17.41 |
| ALL | GREEN | 1 | 138 | 0.80 / 0.63 / 0.32 | 4.66 / 4.52 / 4.27 | 7.92 / 7.79 / 7.52 |
| ALL | GREEN | 2 | 137 | 1.37 / 1.14 / 0.68 | 7.40 / 7.21 / 6.84 | 11.63 / 11.45 / 11.09 |
| ALL | GREEN | 4 | 135 | 2.39 / 2.07 / 1.47 | 12.23 / 11.99 / 11.53 | 18.08 / 17.87 / 17.47 |
| ALL | RED | 1 | 124 | 0.07 / -0.11 / -0.36 | 5.22 / 5.04 / 4.81 | 9.28 / 9.08 / 8.75 |
| ALL | RED | 2 | 124 | -0.11 / -0.37 / -0.70 | 7.54 / 7.35 / 7.04 | 13.06 / 12.83 / 12.50 |
| ALL | RED | 4 | 124 | -0.70 / -1.00 / -1.52 | 9.93 / 9.62 / 9.13 | 17.41 / 17.14 / 16.70 |
| A_RISING | ALL | 1 | 127 | 0.07 / -0.10 / -0.34 | 4.78 / 4.60 / 4.32 | 8.66 / 8.50 / 8.23 |
| A_RISING | ALL | 2 | 127 | 0.73 / 0.48 / 0.14 | 7.22 / 7.02 / 6.73 | 11.83 / 11.64 / 11.32 |
| A_RISING | ALL | 4 | 127 | 0.87 / 0.63 / 0.15 | 9.74 / 9.47 / 9.13 | 16.26 / 16.02 / 15.60 |
| A_RISING | GREEN | 1 | 61 | 0.89 / 0.54 / 0.08 | 4.76 / 4.47 / 3.98 | 7.88 / 7.58 / 7.07 |
| A_RISING | GREEN | 2 | 61 | 1.84 / 1.32 / 0.62 | 7.50 / 7.07 / 6.56 | 11.33 / 10.92 / 10.31 |
| A_RISING | GREEN | 4 | 61 | 3.00 / 2.53 / 1.58 | 11.07 / 10.74 / 10.07 | 16.65 / 16.22 / 15.44 |
| A_RISING | RED | 1 | 66 | -0.68 / -0.92 / -1.27 | 4.79 / 4.45 / 4.15 | 9.39 / 9.09 / 8.68 |
| A_RISING | RED | 2 | 66 | -0.29 / -0.56 / -1.07 | 6.96 / 6.65 / 6.24 | 12.29 / 12.00 / 11.66 |
| A_RISING | RED | 4 | 66 | -1.10 / -1.56 / -2.16 | 8.50 / 7.97 / 7.32 | 15.89 / 15.43 / 14.76 |
| B_FALLING | ALL | 1 | 121 | 0.64 / 0.45 / 0.13 | 4.96 / 4.80 / 4.55 | 8.43 / 8.21 / 7.89 |
| B_FALLING | ALL | 2 | 120 | 0.10 / -0.16 / -0.63 | 7.36 / 7.16 / 6.80 | 12.54 / 12.30 / 11.92 |
| B_FALLING | ALL | 4 | 118 | 0.59 / 0.22 / -0.44 | 12.02 / 11.71 / 11.17 | 18.91 / 18.63 / 18.16 |
| B_FALLING | GREEN | 1 | 69 | 0.19 / -0.15 / -0.59 | 4.34 / 4.05 / 3.71 | 7.75 / 7.47 / 7.11 |
| B_FALLING | GREEN | 2 | 68 | -0.27 / -0.73 / -1.40 | 6.63 / 6.27 / 5.79 | 11.16 / 10.79 / 10.20 |
| B_FALLING | GREEN | 4 | 66 | 0.88 / 0.22 / -0.99 | 11.98 / 11.49 / 10.64 | 18.22 / 17.78 / 17.02 |
| B_FALLING | RED | 1 | 52 | 1.25 / 0.83 / 0.24 | 5.78 / 5.45 / 5.03 | 9.32 / 8.85 / 8.19 |
| B_FALLING | RED | 2 | 52 | 0.59 / -0.02 / -0.82 | 8.30 / 7.85 / 7.18 | 14.34 / 13.82 / 13.07 |
| B_FALLING | RED | 4 | 52 | 0.23 / -0.46 / -1.72 | 12.07 / 11.35 / 10.44 | 19.78 / 19.17 / 18.25 |
| C_START | ALL | 1 | 50 | -0.68 / -1.00 / -1.56 | 5.06 / 4.61 / 4.02 | 9.68 / 9.28 / 8.66 |
| C_START | ALL | 2 | 50 | 0.80 / 0.37 / -0.39 | 9.29 / 8.92 / 8.36 | 13.60 / 13.24 / 12.74 |
| C_START | ALL | 4 | 50 | 0.80 / 0.20 / -0.95 | 12.27 / 11.64 / 10.88 | 19.31 / 18.77 / 17.94 |
| C_START | GREEN | 1 | 20 | 1.03 / 0.29 / -1.11 | 5.72 / 4.87 / 3.82 | 9.23 / 8.35 / 7.11 |
| C_START | GREEN | 2 | 20 | 3.19 / 2.21 / 0.32 | 9.90 / 9.26 / 7.90 | 13.51 / 12.85 / 11.62 |
| C_START | GREEN | 4 | 20 | 5.58 / 4.28 / 1.76 | 14.81 / 13.99 / 12.56 | 20.16 / 19.32 / 17.74 |
| C_START | RED | 1 | 30 | -1.81 / -2.24 / -2.90 | 4.62 / 3.84 / 3.23 | 9.98 / 9.32 / 8.45 |
| C_START | RED | 2 | 30 | -0.79 / -1.38 / -2.57 | 8.88 / 8.25 / 7.40 | 13.66 / 13.05 / 12.38 |
| C_START | RED | 4 | 30 | -2.38 / -3.45 / -4.91 | 10.58 / 9.46 / 8.04 | 18.74 / 17.81 / 16.43 |

Cada métrica elimina sus propios mejores eventos; no se elige una fecha conveniente para todas. Los controles permanecen sin recortar en los lifts de `contrasts.csv`. `analysis.json::influence` publica fechas y valores de los mejores tres en **todos** los eventos y cuadrantes. Las demás celdas contienen ambas sensibilidades en `summaries.csv`. Un n pequeño tras recortar sigue siendo insuficiente, no una estimación estable.
La columna n es la muestra completa; ex1 y ex3 usan n−1 y n−3 observaciones finitas respectivamente. Si n<=k, el resultado ex-best-k es UNKNOWN (—), no un cero.

## 16. Limitaciones y reproducción

Validación software local (Python 3.12): **797 tests passed, 0 failed, 0 skipped** en discovery completo; **43 tests research** pasan también por separado. Audit existente: `MLRSI_SAFETY_AUDIT_OK`. El guard compara 61 fuentes/configs existentes con su SHA256 de producción y rechaza imports directos, relativos, alias o referencias dinámicas a este research desde cualquier módulo productivo. Se añade un workflow offline sin cambiar los siete anteriores.

- 371 semanas de mercado, pero solo 263 semanas con todos los lags; 262/261/259 outcomes maduros. La muestra efectiva es menor por solapamiento y episodios persistentes. Muchos starts/buckets/ADX tienen n<30 o n<10.
- Solo una venue/instrumento y un histórico revisable. Source disagreements documentados: no se afirma equivalencia de open/volume ni disponibilidad histórica point-in-time. No eventos forward observados, ML RSI ni ejecución simulada.
- La observación visual original pudo estar influida por este histórico: análisis descriptivo, no confirmación independiente. TEST reutilizado, sin holdout virgen; no search, retuning ni reglas seleccionadas.
- Bootstrap de bloques de longitud fija es aproximado: no estacionariedad, dependencia más larga y colas gruesas pueden afectar cobertura. IC no simultáneos/multiplicidad; una celda favorable no demuestra significancia general.
- Medir magnitud desde el close no predice disponibilidad de un fill, recorridos intravela ni first-touch. Max move usa extremos semanales, no orden temporal de hits. Sin costes/PnL porque esto estudia información direccional y magnitud.
- Un movimiento ocurrido dentro de la propia semana que hace girar AO/BBWP no cuenta como anticipación: ya pasó al cerrar el evento. La lectura visual puede incluir ese tramo; este estudio exige movimiento posterior.
- N/D/E se reportan completos; las diferencias entre grupos no son una prueba de causalidad económica. ADX falling no equivale a ausencia de movimiento ni determina por sí mismo el lado.
- Retroceso/corrección no tiene una etiqueta causal congelada adicional en este estudio. B identifica contracción de BBWP, no demuestra por sí solo que toda corrección reduzca volatilidad; no se inventó una definición usando el futuro.

Reproducción con RAW locales o nueva descarga explícita (podría cambiar por revisiones de fuente):

```text
python -m research.bitman_weekly_data --cache research/cache/new_weekly_download
python -m research.bitman_weekly_expansion --cache research/cache/new_weekly_download
python -m research.bitman_weekly_reporting
python -m unittest test_bitman_weekly_expansion test_bitman_weekly_boundary -v
```

Reproducción offline sin RAW, red, escrituras ni cuenta: `python -m research.bitman_weekly_expansion --replay research/results/bitman_weekly_expansion`. Recalcula los indicadores frozen desde `weekly_bars.csv`, verifica su coincidencia y consume el contexto 4H versionado (close, SMA200 y timestamp de disponibilidad; verifica la etiqueta y que no haya lookahead). La procedencia completa de ese contexto se verifica con el RAW 4H y su hash. Los tests reproducen todas las tablas, n, medias e intervalos con tolerancia numérica 1e-8. El generador de narrativa está fijado al hash de este snapshot; una revisión de fuente obliga a revisar el texto, no reutiliza conclusiones silenciosamente.

## 17. Conclusión y recomendación de integración

**EXPANSION EFFECT FRAGILE**

**NO INTEGRAR.** No se demuestra valor incremental robusto de magnitud para BBWP rising ni dirección incremental para AO. El pequeño indicio positivo de excursión 1W depende de extremos y contradice épocas; el resto no convierte esta hipótesis en una señal validada. Los starts merecen como máximo observación research, sin promover un N, bucket ni dirección favorable.

No se propone un bloque semanal para runtime ni una nueva condición de READY_LONG/READY_SHORT. Tampoco procede activar STRONG MOVE WATCH, ni siquiera con dirección UNKNOWN, porque el efecto expansivo robusto requerido no ha quedado demostrado. En investigación, STARTING=C, ACTIVE=A fuera de C, COOLING=B son etiquetas descriptivas; COMPRESSION necesita una definición independiente previamente fijada y validada, no un umbral inventado en este estudio.

## Último cierre: CURRENT OBSERVATION — NOT PART OF VALIDATION

```text
WEEK OPEN: 2026-10-12T00:00:00+00:00
CLOSED / AVAILABLE: 2026-10-19T00:00:00+00:00
WEEKLY AO: GREEN
AO LEVEL: 10698.62 (>0)
AO SLOPE: 348.99
BBWP: 41.00 → 30.00
BBWP SLOPE: -11.00 (FALLING)
EXPANSION: COOLING
STRONG MOVE WATCH: UNKNOWN — NOT VALIDATED
CURRENT OBSERVATION ONLY
NOT AN ORDER
TRADE AUTHORITY: NONE
```

GREEN aquí significa que AO sube, mientras BBWP cae: **no hay expansión start ni active** en el último cierre. COOLING no afirma volatilidad absoluta baja: solo describe slope negativo. La semana abierta no se usa. Este punto no tiene outcomes futuros completos en ninguno de los tres horizontes y no entra en validación.

Production unchanged: frozen engine, indicadores/thresholds, gates, Guardian, market-data, V8, ML RSI, risk/execution y Telegram. NO MERGE · NO DEPLOY · NO RAILWAY CHANGES.
