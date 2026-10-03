# ML RSI 1H LOW27 EMA4 — investigación independiente

**Clasificación: INTERESTING BUT INCONCLUSIVE.**

**Exact BackQuant TradingView parity is NOT proven.** Se reutiliza sin cambios la función matemática `guardian_signals.rolling_mlrsi`: LOW/RSI27/EMA4, tres centroides inicializados p25/p50/p75, asignación por distancia absoluta, actualización por medias, últimos 3000 RSI finitos, máximo 1000 pasos. No se afirma reproducir la versión instalada en TradingView. Ver la auditoría de [PR #19](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/19). **15M = NO EDGE for tested hypothesis** permanece intacto.

El candidato más interesante es GREEN_RESUME de una barra con salida por color sin stop: TEST n=228, media neta +0.727%, PF1.534; tras eliminar las mejores3 queda +0.473%. Su ventaja frente al control es positiva, pero el IC95 semanal de su propia expectativa [-0.404%, +1.805%] incluye cero. El equity secuencial toma solo71 eventos no solapados: +7.183% total y MaxDD31.604% al cierre de trades. Los vecinos con stop cambian mucho el resultado. Por ello **no alcanza PROMISING** ni justifica una propuesta de observer todavía.

## Datos, protocolo y seguridad

754,202 velas BTCUSDT Binance **spot** públicas 5m desde 2019-08-01T00:00:00+00:00 hasta 2026-10-03T21:00:00+00:00; 62,843 horas completas. 18 huecos no interpolados. Se verificaron nuevamente todos los archivos de origen. Cada hora necesita doce barras contiguas y cerradas. Las horas/días/4H incompletos se descartan. Los indicadores avanzan sobre observaciones reales disponibles; no se sintetizan RSI ni precios de barras ausentes. Un hueco cancela un evento pendiente y censura cualquier horizonte/trade que lo atraviese.

TRAIN 2020–2021; VALIDATION 2022–2023; TEST 2024–cutoff congelado. El proceso development recorta físicamente las barras a 2024-01-01; fija selección, quartiles TRAIN y hashes antes del proceso TEST. TEST rechaza código/protocolo/dataset/costes/cutoff distintos. No se eligieron filtros usando TEST. Artefactos: [preregistered.json](preregistered.json), [frozen_selection.json](frozen_selection.json), [data_manifest.json](data_manifest.json). El hash del dataset incluye el archivo entero para identificarlo; ninguna etiqueta/estadística TEST entra en la selección. Los datasets grandes permanecen en cache ignorada.

Una primera ejecución no pudo serializar un booleano NumPy. Se cambió únicamente el tipo de salida a bool Python; se repitió desarrollo y se verificó igualdad exacta de selecciones y quartiles antes del TEST completado. [freeze_receipt.json](freeze_receipt.json) conserva ambas congelaciones. No cambió ninguna fórmula, modelo ni parámetro por este arreglo.

CROSS: estado previo distinto del color actual. RESUME: reset de pendiente dentro del mismo color y posterior pendiente favorable; una señal, no una por barra. Las variantes de dos barras requieren dos pendientes favorables consecutivas y disparan al cierre posterior. Las salidas por color usan el primer cierre 1H con color opuesto, independientemente de la confirmación de entrada.

Entrada: próxima apertura 1H más slippage adverso. Close-fill es sensibilidad separada al límite de vela, no una ejecución favorable dentro del pasado. Caminos simulados y horizontes usan 5m cerradas. Todos los modelos tienen límite predefinido 72h. Salida de color sin stop no tiene el mismo riesgo que la versión con stop. R en esa variante se normaliza por 1 ATR virtual, no por una pérdida máxima.

Gestión: 16 modelos, vecinos de un factor; seis runners económicos ATR, un control BE ingenuo, cinco color exits con/sin stop, tres R:R y un runner con salida por color. Se elige por evento/confirmación maximizando el mínimo retorno medio neto TRAIN/VALIDATION, con 100 trades completos en ambos. Solo color sin stop y color stop1 son elegibles de esa familia; otros stops y BE ingenuo son controles. Si falta muestra, se conserva el preset ATR1/trail1.5. Ningún modelo es una orden ni una estrategia aplicada a la cuenta.

ATR14 Wilder 1H congelado en el cierre de señal. TP1 +1R cierra 30%. Runner 70%. Trailing sobre extremo favorable de 5m cerrado, nivel nuevo activo desde la siguiente barra; nunca se amplía un stop. Si una 5m toca SL y TP, SL primero; si TP1 y BE pueden colisionar, se sale conservadoramente por BE. Un gap de precio llena el stop a la apertura adversa. No se asume un fill rentable cuando el BE calculado ya estaría por encima del TP1 LONG/por debajo SHORT.

**BE económico = PnL neto total de la operación igual a cero**, incluyendo TP1 ya cobrado, entrada/TP1/runner fees y slippage esperado de stop. Por acreditar el beneficio realizado de TP1 puede quedar debajo de entry LONG o encima SHORT. No es BE del runner aislado ni garantía de salir sin pérdidas durante gaps. Fórmula: con side s=±1, fee f, entry E, TP1 efectivo P, w=.3 y stop slip u: `BE_trigger = E * (((s+f)/(s-f) - w*P/E)/(1-w)) / (1-s*u)`. El stop nunca se amplía respecto al nivel inicial.

Costes base {'fee_bps': 5.0, 'slippage_bps': 2.0, 'stop_slippage_bps': 5.0}; stress {'fee_bps': 6.0, 'slippage_bps': 5, 'stop_slippage_bps': 10}. 5 bps taker es un supuesto configurable VIP1-like, no una certificación del tier del usuario. Fees parciales ponderadas por cantidad/notional. Gross elimina fricciones de ese mismo camino, no reoptimiza fills. **Funding, basis spot/perpetual y fills reales Bitunix excluidos**; no es rentabilidad ejecutable/realizada de futures ni retorno de la cuenta.

Los eventos pueden solaparse. MaxDD/retorno de gestión son aparte una equity 1x secuencial sin posiciones simultáneas, medida al cierre de trades; no incluyen drawdown intratrade marcado a mercado. MFE/MAE de gestión son extremos conservadores de barras completas antes de la salida y sus fills, no extremos posteriores al cierre intrabar. Win/loss/BE neto usan tolerancia ±1bp.

## 1. Señal antes de gestionar — TEST por horizonte

Retorno direccional desde entry con slippage: LONG=future/entry−1, SHORT=1−future/entry. La columna net añade salida taker/slippage normal a ese horizonte. MFE/MAE desde entry; no son pagos obtenibles simultáneamente. First passage: porcentaje sobre horizontes completos; si ambos límites tocan la misma 5m se cuenta fracaso conservador y se informa ambigüedad. Neither es censura dentro del horizonte, no éxito. Horizonte con falta de datos/split censurado completo.

### GREEN_CROSS:1

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 208 | 0 | +0.013% | -0.032% | -0.107% | +0.252% | -0.243% | 23.6% | 5.3% | 1.0% | 0.0% | 0.0% |
| 2 | 208 | 0 | -0.006% | -0.114% | -0.126% | +0.341% | -0.366% | 31.2% | 13.0% | 3.4% | 0.5% | 0.5% |
| 4 | 208 | 0 | -0.021% | -0.116% | -0.141% | +0.478% | -0.564% | 38.5% | 20.2% | 7.2% | 1.4% | 0.5% |
| 8 | 208 | 0 | -0.001% | -0.133% | -0.121% | +0.763% | -0.790% | 43.3% | 31.2% | 12.0% | 5.3% | 1.0% |
| 12 | 208 | 0 | +0.023% | -0.176% | -0.097% | +0.860% | -0.906% | 43.8% | 38.0% | 16.8% | 7.2% | 1.0% |
| 24 | 208 | 0 | -0.059% | -0.097% | -0.179% | +1.297% | -1.189% | 44.2% | 49.5% | 25.5% | 12.0% | 3.8% |
| 48 | 207 | 1 | +0.208% | -0.174% | +0.088% | +1.938% | -1.666% | 44.0% | 53.1% | 32.9% | 21.7% | 9.2% |
| 72 | 207 | 1 | +0.208% | -0.104% | +0.087% | +2.387% | -2.573% | 44.0% | 53.1% | 32.9% | 29.0% | 12.6% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 200 | +0.036% | 200 | -0.019% | [-0.098%, +0.060%] |
| 2 | 200 | +0.004% | 200 | +0.004% | [-0.124%, +0.144%] |
| 4 | 200 | +0.049% | 200 | -0.057% | [-0.215%, +0.142%] |
| 8 | 200 | +0.015% | 200 | -0.002% | [-0.236%, +0.279%] |
| 12 | 200 | +0.174% | 200 | -0.140% | [-0.427%, +0.180%] |
| 24 | 200 | +0.299% | 200 | -0.339% | [-0.818%, +0.144%] |
| 48 | 200 | +0.196% | 199 | +0.060% | [-0.705%, +0.864%] |
| 72 | 199 | +0.246% | 199 | -0.034% | [-0.938%, +0.900%] |

### GREEN_RESUME:1

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 228 | 0 | -0.018% | -0.054% | -0.138% | +0.183% | -0.249% | 15.8% | 4.4% | 1.3% | 0.4% | 0.0% |
| 2 | 228 | 0 | -0.021% | -0.047% | -0.141% | +0.282% | -0.338% | 25.9% | 11.8% | 3.1% | 0.9% | 0.0% |
| 4 | 228 | 0 | +0.022% | -0.088% | -0.098% | +0.398% | -0.522% | 35.5% | 19.3% | 5.7% | 3.5% | 0.4% |
| 8 | 228 | 0 | +0.123% | +0.062% | +0.003% | +0.674% | -0.671% | 43.0% | 33.3% | 13.6% | 7.0% | 1.3% |
| 12 | 228 | 0 | +0.223% | +0.083% | +0.103% | +0.917% | -0.793% | 45.6% | 40.8% | 18.9% | 10.1% | 3.1% |
| 24 | 228 | 0 | +0.355% | +0.051% | +0.235% | +1.315% | -1.077% | 46.9% | 50.4% | 25.0% | 17.5% | 7.9% |
| 48 | 228 | 0 | +0.913% | +0.680% | +0.793% | +2.209% | -1.625% | 46.9% | 54.8% | 36.0% | 28.1% | 13.2% |
| 72 | 228 | 0 | +0.994% | +0.460% | +0.874% | +2.974% | -2.232% | 46.9% | 54.8% | 38.6% | 36.0% | 21.9% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 216 | -0.033% | 216 | +0.014% | [-0.057%, +0.081%] |
| 2 | 216 | -0.063% | 216 | +0.044% | [-0.080%, +0.169%] |
| 4 | 216 | -0.051% | 216 | +0.084% | [-0.112%, +0.273%] |
| 8 | 216 | -0.074% | 216 | +0.221% | [-0.102%, +0.523%] |
| 12 | 216 | -0.062% | 216 | +0.315% | [-0.075%, +0.681%] |
| 24 | 216 | -0.053% | 216 | +0.418% | [-0.068%, +0.863%] |
| 48 | 216 | -0.329% | 216 | +1.285% | [+0.594%, +1.936%] |
| 72 | 216 | -0.181% | 216 | +1.231% | [+0.299%, +2.208%] |

### RED_CROSS:1

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 281 | 0 | -0.017% | -0.056% | -0.137% | +0.362% | -0.349% | 33.8% | 14.6% | 1.8% | 0.7% | 0.4% |
| 2 | 281 | 0 | +0.027% | -0.030% | -0.093% | +0.452% | -0.443% | 39.5% | 22.4% | 5.3% | 1.8% | 0.4% |
| 4 | 281 | 0 | -0.062% | -0.127% | -0.182% | +0.655% | -0.621% | 44.1% | 33.1% | 10.0% | 4.6% | 0.7% |
| 8 | 281 | 0 | -0.076% | -0.116% | -0.196% | +0.918% | -0.864% | 46.6% | 41.3% | 18.5% | 7.5% | 2.1% |
| 12 | 281 | 0 | -0.060% | -0.170% | -0.180% | +1.123% | -0.987% | 47.0% | 45.2% | 24.9% | 12.1% | 5.0% |
| 24 | 281 | 0 | -0.012% | -0.146% | -0.132% | +1.481% | -1.463% | 47.0% | 50.5% | 30.6% | 22.4% | 10.3% |
| 48 | 281 | 0 | -0.149% | -0.250% | -0.269% | +2.122% | -2.072% | 47.0% | 52.0% | 35.2% | 27.8% | 17.4% |
| 72 | 281 | 0 | -0.381% | -0.483% | -0.501% | +2.537% | -2.555% | 47.0% | 52.3% | 35.6% | 30.6% | 19.9% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 267 | +0.020% | 267 | -0.052% | [-0.193%, +0.081%] |
| 2 | 267 | -0.050% | 267 | +0.046% | [-0.167%, +0.250%] |
| 4 | 267 | -0.062% | 267 | -0.030% | [-0.271%, +0.191%] |
| 8 | 267 | -0.068% | 267 | -0.025% | [-0.329%, +0.270%] |
| 12 | 267 | -0.114% | 267 | +0.030% | [-0.331%, +0.399%] |
| 24 | 267 | +0.036% | 267 | -0.057% | [-0.597%, +0.533%] |
| 48 | 267 | +0.079% | 267 | -0.240% | [-0.909%, +0.415%] |
| 72 | 267 | -0.120% | 267 | -0.284% | [-1.147%, +0.533%] |

### RED_RESUME:1

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 266 | 0 | -0.061% | -0.089% | -0.181% | +0.292% | -0.424% | 34.2% | 15.8% | 3.8% | 2.3% | 0.0% |
| 2 | 266 | 0 | -0.095% | -0.140% | -0.215% | +0.452% | -0.513% | 41.0% | 22.6% | 7.5% | 3.8% | 1.1% |
| 4 | 266 | 0 | -0.188% | -0.241% | -0.308% | +0.636% | -0.756% | 45.5% | 30.1% | 11.3% | 6.4% | 2.3% |
| 8 | 266 | 0 | -0.184% | -0.353% | -0.304% | +0.889% | -1.047% | 49.2% | 38.7% | 16.9% | 10.9% | 3.0% |
| 12 | 266 | 0 | -0.348% | -0.496% | -0.468% | +1.094% | -1.288% | 49.6% | 41.4% | 22.9% | 14.3% | 4.1% |
| 24 | 266 | 0 | -0.378% | -0.512% | -0.498% | +1.559% | -1.738% | 50.0% | 46.6% | 27.4% | 22.6% | 9.8% |
| 48 | 266 | 0 | -0.336% | -0.385% | -0.456% | +2.033% | -2.139% | 50.0% | 49.6% | 29.7% | 25.9% | 16.9% |
| 72 | 266 | 0 | -0.226% | -0.264% | -0.346% | +2.522% | -2.788% | 50.0% | 49.6% | 30.5% | 28.6% | 18.0% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 245 | -0.010% | 245 | -0.030% | [-0.151%, +0.090%] |
| 2 | 245 | -0.021% | 245 | -0.056% | [-0.243%, +0.154%] |
| 4 | 245 | -0.044% | 245 | -0.111% | [-0.354%, +0.123%] |
| 8 | 245 | -0.001% | 245 | -0.131% | [-0.413%, +0.188%] |
| 12 | 245 | -0.052% | 245 | -0.242% | [-0.537%, +0.071%] |
| 24 | 245 | +0.079% | 245 | -0.382% | [-0.935%, +0.151%] |
| 48 | 245 | +0.232% | 245 | -0.437% | [-1.226%, +0.311%] |
| 72 | 245 | -0.105% | 245 | +0.038% | [-0.848%, +0.919%] |

### GREEN_CROSS:2

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 177 | 0 | -0.055% | -0.110% | -0.175% | +0.198% | -0.277% | 18.1% | 5.1% | 1.7% | 0.6% | 0.6% |
| 2 | 177 | 0 | -0.120% | -0.158% | -0.240% | +0.255% | -0.423% | 24.9% | 9.0% | 1.7% | 1.1% | 0.6% |
| 4 | 177 | 0 | -0.079% | -0.190% | -0.199% | +0.402% | -0.587% | 35.0% | 19.8% | 7.3% | 2.3% | 0.6% |
| 8 | 177 | 0 | -0.121% | -0.154% | -0.241% | +0.623% | -0.823% | 42.9% | 29.9% | 12.4% | 4.5% | 0.6% |
| 12 | 177 | 0 | -0.095% | -0.107% | -0.215% | +0.751% | -0.940% | 44.1% | 37.3% | 16.9% | 6.2% | 0.6% |
| 24 | 177 | 0 | -0.106% | -0.192% | -0.226% | +1.340% | -1.290% | 44.1% | 45.2% | 24.3% | 14.1% | 4.0% |
| 48 | 176 | 1 | +0.140% | -0.285% | +0.020% | +1.838% | -1.734% | 43.8% | 48.3% | 29.0% | 21.0% | 9.7% |
| 72 | 176 | 1 | +0.009% | -0.460% | -0.111% | +2.314% | -2.546% | 43.8% | 48.3% | 29.5% | 27.3% | 13.6% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 168 | -0.027% | 168 | -0.013% | [-0.123%, +0.103%] |
| 2 | 168 | -0.020% | 168 | -0.085% | [-0.207%, +0.050%] |
| 4 | 168 | +0.085% | 168 | -0.161% | [-0.380%, +0.057%] |
| 8 | 168 | -0.004% | 168 | -0.095% | [-0.356%, +0.171%] |
| 12 | 168 | +0.027% | 168 | -0.105% | [-0.440%, +0.241%] |
| 24 | 168 | +0.033% | 168 | -0.116% | [-0.627%, +0.402%] |
| 48 | 168 | +0.304% | 167 | -0.092% | [-0.816%, +0.695%] |
| 72 | 167 | +0.478% | 167 | -0.445% | [-1.363%, +0.516%] |

### GREEN_RESUME:2

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 141 | 0 | +0.007% | -0.028% | -0.113% | +0.193% | -0.248% | 20.6% | 6.4% | 1.4% | 0.0% | 0.0% |
| 2 | 141 | 0 | +0.000% | -0.062% | -0.120% | +0.295% | -0.346% | 29.8% | 14.9% | 3.5% | 0.0% | 0.0% |
| 4 | 141 | 0 | +0.102% | +0.021% | -0.018% | +0.562% | -0.488% | 43.3% | 24.8% | 7.8% | 2.8% | 0.0% |
| 8 | 141 | 0 | +0.259% | +0.077% | +0.139% | +0.879% | -0.638% | 44.7% | 41.1% | 18.4% | 9.2% | 2.1% |
| 12 | 141 | 0 | +0.209% | +0.111% | +0.089% | +1.141% | -0.801% | 46.8% | 46.1% | 24.1% | 12.8% | 3.5% |
| 24 | 141 | 0 | +0.443% | +0.002% | +0.323% | +1.406% | -1.152% | 47.5% | 51.8% | 25.5% | 19.1% | 10.6% |
| 48 | 141 | 0 | +1.106% | +0.801% | +0.985% | +2.233% | -1.596% | 47.5% | 54.6% | 32.6% | 31.9% | 17.0% |
| 72 | 141 | 0 | +1.228% | +0.763% | +1.108% | +2.901% | -1.989% | 47.5% | 54.6% | 36.9% | 38.3% | 24.1% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 136 | -0.079% | 136 | +0.088% | [-0.014%, +0.207%] |
| 2 | 136 | -0.091% | 136 | +0.074% | [-0.111%, +0.250%] |
| 4 | 136 | -0.085% | 136 | +0.188% | [-0.030%, +0.420%] |
| 8 | 136 | +0.026% | 136 | +0.263% | [-0.101%, +0.608%] |
| 12 | 136 | +0.004% | 136 | +0.240% | [-0.175%, +0.667%] |
| 24 | 136 | +0.137% | 136 | +0.344% | [-0.380%, +1.111%] |
| 48 | 136 | +0.353% | 136 | +0.846% | [-0.177%, +1.847%] |
| 72 | 136 | +0.369% | 136 | +0.951% | [-0.486%, +2.349%] |

### RED_CROSS:2

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 226 | 0 | +0.035% | +0.028% | -0.085% | +0.363% | -0.298% | 31.0% | 12.4% | 2.2% | 0.9% | 0.4% |
| 2 | 226 | 0 | +0.000% | -0.068% | -0.120% | +0.463% | -0.446% | 40.7% | 22.1% | 4.4% | 2.2% | 0.9% |
| 4 | 226 | 0 | +0.004% | -0.087% | -0.116% | +0.590% | -0.581% | 45.1% | 31.0% | 9.7% | 5.8% | 1.8% |
| 8 | 226 | 0 | +0.020% | -0.154% | -0.100% | +0.962% | -0.845% | 47.3% | 41.6% | 19.9% | 9.7% | 3.5% |
| 12 | 226 | 0 | +0.026% | -0.144% | -0.094% | +1.132% | -1.014% | 47.3% | 47.8% | 24.3% | 15.0% | 6.6% |
| 24 | 226 | 0 | -0.002% | -0.358% | -0.122% | +1.685% | -1.579% | 47.3% | 50.9% | 30.5% | 22.6% | 10.6% |
| 48 | 226 | 0 | -0.099% | -0.274% | -0.219% | +2.253% | -2.149% | 47.3% | 52.2% | 33.2% | 28.8% | 19.0% |
| 72 | 226 | 0 | -0.388% | -0.374% | -0.508% | +2.536% | -2.692% | 47.3% | 52.7% | 35.0% | 30.5% | 20.4% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 214 | -0.006% | 214 | +0.043% | [-0.059%, +0.149%] |
| 2 | 214 | -0.080% | 214 | +0.096% | [-0.036%, +0.226%] |
| 4 | 214 | -0.082% | 214 | +0.100% | [-0.138%, +0.332%] |
| 8 | 214 | -0.048% | 214 | +0.125% | [-0.210%, +0.462%] |
| 12 | 214 | -0.070% | 214 | +0.150% | [-0.218%, +0.531%] |
| 24 | 214 | +0.138% | 214 | -0.055% | [-0.527%, +0.441%] |
| 48 | 214 | +0.309% | 214 | -0.302% | [-1.070%, +0.447%] |
| 72 | 214 | +0.168% | 214 | -0.522% | [-1.551%, +0.431%] |

### RED_RESUME:2

| h | n | incomp. | media | mediana | net | MFE med. | MAE med. | +.5/-.5 | +1/-1 | +2/-1 | +3/-1.5 | +5/-2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 182 | 0 | -0.061% | -0.119% | -0.181% | +0.276% | -0.375% | 28.0% | 13.7% | 3.3% | 2.2% | 1.1% |
| 2 | 182 | 0 | -0.214% | -0.217% | -0.334% | +0.412% | -0.594% | 36.3% | 20.3% | 7.7% | 2.7% | 1.1% |
| 4 | 182 | 0 | -0.162% | -0.185% | -0.282% | +0.579% | -0.714% | 42.3% | 31.9% | 13.7% | 4.9% | 1.6% |
| 8 | 182 | 0 | -0.122% | -0.357% | -0.242% | +0.955% | -1.028% | 44.0% | 39.6% | 23.1% | 9.3% | 4.4% |
| 12 | 182 | 0 | -0.161% | -0.435% | -0.282% | +1.248% | -1.268% | 44.5% | 42.9% | 25.3% | 12.6% | 6.0% |
| 24 | 182 | 0 | -0.343% | -0.512% | -0.463% | +1.646% | -1.589% | 44.5% | 47.8% | 29.1% | 21.4% | 12.1% |
| 48 | 182 | 0 | -0.259% | -0.228% | -0.379% | +2.138% | -2.156% | 44.5% | 48.4% | 29.1% | 25.3% | 22.5% |
| 72 | 182 | 0 | -0.027% | +0.052% | -0.148% | +2.481% | -2.769% | 44.5% | 48.4% | 29.7% | 28.0% | 23.6% |

| h | control n | control media | ventaja pareada n | ventaja | IC95 semanal ventaja |
| --- | --- | --- | --- | --- | --- |
| 1 | 167 | +0.001% | 167 | -0.042% | [-0.173%, +0.113%] |
| 2 | 167 | -0.039% | 167 | -0.166% | [-0.310%, -0.042%] |
| 4 | 167 | +0.011% | 167 | -0.142% | [-0.381%, +0.075%] |
| 8 | 167 | +0.062% | 167 | -0.170% | [-0.496%, +0.147%] |
| 12 | 167 | -0.040% | 167 | -0.109% | [-0.470%, +0.238%] |
| 24 | 167 | -0.051% | 167 | -0.208% | [-0.852%, +0.418%] |
| 48 | 167 | -0.286% | 167 | +0.160% | [-0.680%, +0.972%] |
| 72 | 167 | -0.440% | 167 | +0.556% | [-0.554%, +1.640%] |

## 2. Gestión seleccionada ANTES de TEST

Estos son los modelos elegidos en desarrollo, no el mejor resultado descubierto en TEST.

| evento:confirm | modelo | n T/V/TEST | TRAIN net | VAL net | TEST gross | TEST net | R | PF | MaxDD sec. | IC95 media net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | color:sl0 | 141/101/207 | +0.824% | +0.933% | +0.184% | +0.044% | 0.502 | 1.031 | 34.1% | [-0.638%, +0.681%] |
| GREEN_RESUME:1 | color:sl0 | 152/140/228 | +1.178% | +0.574% | +0.868% | +0.727% | 2.036 | 1.534 | 31.6% | [-0.404%, +1.805%] |
| RED_CROSS:1 | color_runner:sl1:economic | 222/173/281 | -0.093% | +0.031% | -0.031% | -0.195% | -0.246 | 0.565 | 39.8% | [-0.358%, -0.016%] |
| RED_RESUME:1 | atr_runner:sl1:trail1:economic | 235/213/266 | -0.147% | +0.037% | -0.013% | -0.178% | -0.263 | 0.647 | 35.1% | [-0.320%, -0.039%] |
| GREEN_CROSS:2 | atr_runner:sl1:trail1.5:economic | 125/83/177 | +0.003% | -0.018% | -0.055% | -0.221% | -0.348 | 0.516 | 35.4% | [-0.342%, -0.080%] |
| GREEN_RESUME:2 | atr_runner:sl1:trail1.5:economic | 100/85/141 | -0.179% | -0.287% | +0.059% | -0.106% | -0.224 | 0.727 | 15.2% | [-0.249%, +0.047%] |
| RED_CROSS:2 | fixed1r:sl1 | 176/131/226 | -0.131% | -0.182% | +0.021% | -0.135% | -0.241 | 0.710 | 27.8% | [-0.246%, -0.028%] |
| RED_RESUME:2 | fixed2r:sl1 | 141/130/182 | +0.016% | +0.242% | -0.136% | -0.298% | -0.352 | 0.597 | 38.7% | [-0.512%, -0.102%] |

| confirm | lado | n | net medio | PF | MaxDD sec. | retorno sec. |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | LONG | 435 | +0.402% | 1.289 | 43.4% | -10.297% |
| 1 | SHORT | 547 | -0.187% | 0.608 | 50.0% | -48.804% |
| 1 | LONG_SHORT | 982 | +0.074% | 1.084 | 66.8% | -54.076% |
| 2 | LONG | 318 | -0.170% | 0.601 | 41.0% | -36.736% |
| 2 | SHORT | 408 | -0.208% | 0.646 | 53.2% | -53.250% |
| 2 | LONG_SHORT | 726 | -0.191% | 0.630 | 71.2% | -70.424% |

## 3. Alineación HTF, descriptiva: no filtro seleccionado

4H y 1D usan SOLO cierres completos y SMA200. Igualdad no cuenta como alineación. 1D tiene warmup insuficiente al inicio de TRAIN, marcado UNKNOWN. Quartiles de ATR/close se fijaron con TRAIN: +0.754%, +1.005%, +1.342%.

| evento:confirm | cohorte | n gestión | gestión net | PF | n 24h | 24h media | 24h +1/-1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | UNFILTERED | 207 | +0.044% | 1.031 | 208 | -0.059% | 49.5% |
| GREEN_CROSS:1 | 4H | 152 | +0.032% | 1.023 | 153 | +0.029% | 48.4% |
| GREEN_CROSS:1 | 1D | 115 | +0.034% | 1.023 | 116 | -0.054% | 52.6% |
| GREEN_CROSS:1 | BOTH | 97 | +0.108% | 1.078 | 98 | +0.086% | 52.0% |
| GREEN_RESUME:1 | UNFILTERED | 228 | +0.727% | 1.534 | 228 | +0.355% | 50.4% |
| GREEN_RESUME:1 | 4H | 183 | +0.992% | 1.794 | 183 | +0.466% | 47.5% |
| GREEN_RESUME:1 | 1D | 144 | +0.921% | 1.759 | 144 | +0.487% | 45.8% |
| GREEN_RESUME:1 | BOTH | 126 | +1.005% | 1.862 | 126 | +0.604% | 42.9% |
| RED_CROSS:1 | UNFILTERED | 281 | -0.195% | 0.565 | 281 | -0.012% | 50.5% |
| RED_CROSS:1 | 4H | 168 | -0.155% | 0.664 | 168 | +0.105% | 52.4% |
| RED_CROSS:1 | 1D | 101 | -0.240% | 0.502 | 101 | +0.120% | 43.6% |
| RED_CROSS:1 | BOTH | 77 | -0.274% | 0.470 | 77 | +0.144% | 45.5% |
| RED_RESUME:1 | UNFILTERED | 266 | -0.178% | 0.647 | 266 | -0.378% | 46.6% |
| RED_RESUME:1 | 4H | 205 | -0.140% | 0.722 | 205 | -0.278% | 48.3% |
| RED_RESUME:1 | 1D | 104 | -0.164% | 0.674 | 104 | -0.467% | 47.1% |
| RED_RESUME:1 | BOTH | 86 | -0.167% | 0.680 | 86 | -0.645% | 48.8% |
| GREEN_CROSS:2 | UNFILTERED | 177 | -0.221% | 0.516 | 177 | -0.106% | 45.2% |
| GREEN_CROSS:2 | 4H | 133 | -0.145% | 0.657 | 133 | +0.001% | 45.1% |
| GREEN_CROSS:2 | 1D | 99 | -0.228% | 0.501 | 99 | -0.116% | 49.5% |
| GREEN_CROSS:2 | BOTH | 82 | -0.179% | 0.602 | 82 | -0.009% | 47.6% |
| GREEN_RESUME:2 | UNFILTERED | 141 | -0.106% | 0.727 | 141 | +0.443% | 51.8% |
| GREEN_RESUME:2 | 4H | 115 | -0.104% | 0.737 | 115 | +0.551% | 48.7% |
| GREEN_RESUME:2 | 1D | 90 | -0.075% | 0.819 | 90 | +0.710% | 48.9% |
| GREEN_RESUME:2 | BOTH | 77 | -0.098% | 0.774 | 77 | +0.851% | 45.5% |
| RED_CROSS:2 | UNFILTERED | 226 | -0.135% | 0.710 | 226 | -0.002% | 50.9% |
| RED_CROSS:2 | 4H | 136 | -0.053% | 0.876 | 136 | +0.118% | 52.9% |
| RED_CROSS:2 | 1D | 84 | -0.148% | 0.691 | 84 | +0.428% | 47.6% |
| RED_CROSS:2 | BOTH | 65 | -0.108% | 0.779 | 65 | +0.490% | 49.2% |
| RED_RESUME:2 | UNFILTERED | 182 | -0.298% | 0.597 | 182 | -0.343% | 47.8% |
| RED_RESUME:2 | 4H | 140 | -0.197% | 0.726 | 140 | -0.225% | 50.7% |
| RED_RESUME:2 | 1D | 69 | -0.178% | 0.744 | 69 | -0.238% | 56.5% |
| RED_RESUME:2 | BOTH | 58 | -0.143% | 0.800 | 58 | -0.441% | 55.2% |

## 4. Robustez y efecto de costes/BE

| evento:confirm | n | stress net | close-fill net | sin mejores3 net | sin peores3 net | top3/beneficios | econ BE net | naive BE net | control net | ventaja pareada | IC95 ventaja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | 207 | -0.036% | +0.044% | -0.174% | +0.162% | 14.7% | -0.185% | -0.185% | +0.212% | -0.165% | [-1.027%, +0.690%] |
| GREEN_RESUME:1 | 228 | +0.647% | +0.727% | +0.473% | +0.860% | 12.5% | -0.146% | -0.148% | -0.325% | +1.094% | [+0.117%, +2.029%] |
| RED_CROSS:1 | 281 | -0.278% | -0.195% | -0.286% | -0.174% | 34.7% | -0.211% | -0.216% | -0.133% | -0.060% | [-0.328%, +0.219%] |
| RED_RESUME:1 | 266 | -0.287% | -0.178% | -0.225% | -0.158% | 13.5% | -0.188% | -0.225% | -0.125% | -0.062% | [-0.274%, +0.191%] |
| GREEN_CROSS:2 | 177 | -0.302% | -0.221% | -0.262% | -0.198% | 15.2% | -0.221% | -0.216% | -0.117% | -0.087% | [-0.285%, +0.133%] |
| GREEN_RESUME:2 | 141 | -0.207% | -0.106% | -0.161% | -0.081% | 18.2% | -0.106% | -0.103% | -0.218% | +0.103% | [-0.088%, +0.311%] |
| RED_CROSS:2 | 226 | -0.222% | -0.135% | -0.158% | -0.109% | 6.3% | -0.166% | -0.184% | -0.177% | +0.063% | [-0.086%, +0.218%] |
| RED_RESUME:2 | 182 | -0.388% | -0.298% | -0.356% | -0.265% | 11.9% | -0.250% | -0.255% | -0.209% | -0.039% | [-0.298%, +0.207%] |

### Una vs dos barras, MISMA gestión (diagnóstico, no reselección)

El preset de fallback GREEN de dos barras es ATR, por falta de n desarrollo. Compararlo directamente con la selección color de una barra confundiría gestión y confirmación. Esta tabla mantiene la misma gestión en ambos; GREEN_RESUME color de dos barras también es positivo, mientras sus runners ATR siguen negativos. Ver [diagnostics.json](diagnostics.json).

| evento:confirm | modelo fijo | n | net | PF | stress | IC95 net | ventaja control | IC95 ventaja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | color:sl0 | 207 | +0.044% | 1.031 | -0.036% | [-0.638%, +0.681%] | -0.165% | [-1.027%, +0.690%] |
| GREEN_CROSS:1 | color:sl1 | 208 | -0.183% | 0.739 | -0.313% | [-0.474%, +0.126%] | -0.093% | [-0.509%, +0.358%] |
| GREEN_CROSS:1 | atr_runner:sl1:trail1.5:economic | 208 | -0.185% | 0.578 | -0.333% | [-0.311%, -0.062%] | +0.021% | [-0.139%, +0.209%] |
| GREEN_RESUME:1 | color:sl0 | 228 | +0.727% | 1.534 | +0.647% | [-0.404%, +1.805%] | +1.094% | [+0.117%, +2.029%] |
| GREEN_RESUME:1 | color:sl1 | 228 | +0.055% | 1.081 | -0.017% | [-0.352%, +0.467%] | +0.237% | [-0.195%, +0.670%] |
| GREEN_RESUME:1 | atr_runner:sl1:trail1.5:economic | 228 | -0.146% | 0.646 | -0.258% | [-0.276%, -0.020%] | +0.071% | [-0.116%, +0.226%] |
| RED_CROSS:1 | color:sl0 | 281 | -0.473% | 0.748 | -0.553% | [-1.228%, +0.219%] | -0.403% | [-1.148%, +0.359%] |
| RED_CROSS:1 | color:sl1 | 281 | -0.317% | 0.596 | -0.397% | [-0.561%, -0.038%] | -0.188% | [-0.599%, +0.235%] |
| RED_CROSS:1 | atr_runner:sl1:trail1.5:economic | 281 | -0.211% | 0.530 | -0.306% | [-0.324%, -0.094%] | -0.036% | [-0.237%, +0.154%] |
| RED_RESUME:1 | color:sl0 | 266 | -0.391% | 0.776 | -0.471% | [-1.225%, +0.444%] | -0.077% | [-0.937%, +0.782%] |
| RED_RESUME:1 | color:sl1 | 266 | -0.447% | 0.496 | -0.518% | [-0.738%, -0.092%] | -0.272% | [-0.705%, +0.211%] |
| RED_RESUME:1 | atr_runner:sl1:trail1.5:economic | 266 | -0.188% | 0.628 | -0.315% | [-0.345%, -0.021%] | -0.034% | [-0.255%, +0.240%] |
| GREEN_CROSS:2 | color:sl0 | 176 | -0.178% | 0.887 | -0.257% | [-0.864%, +0.476%] | -0.514% | [-1.343%, +0.349%] |
| GREEN_CROSS:2 | color:sl1 | 177 | -0.141% | 0.806 | -0.231% | [-0.499%, +0.321%] | -0.229% | [-0.797%, +0.395%] |
| GREEN_CROSS:2 | atr_runner:sl1:trail1.5:economic | 177 | -0.221% | 0.516 | -0.302% | [-0.342%, -0.080%] | -0.087% | [-0.285%, +0.133%] |
| GREEN_RESUME:2 | color:sl0 | 141 | +0.915% | 1.669 | +0.835% | [-0.372%, +2.145%] | +0.690% | [-0.793%, +2.094%] |
| GREEN_RESUME:2 | color:sl1 | 141 | +0.353% | 1.551 | +0.255% | [-0.192%, +0.902%] | +0.541% | [-0.073%, +1.206%] |
| GREEN_RESUME:2 | atr_runner:sl1:trail1.5:economic | 141 | -0.106% | 0.727 | -0.207% | [-0.249%, +0.047%] | +0.103% | [-0.088%, +0.311%] |
| RED_CROSS:2 | color:sl0 | 226 | -0.553% | 0.716 | -0.633% | [-1.318%, +0.240%] | -0.669% | [-1.637%, +0.258%] |
| RED_CROSS:2 | color:sl1 | 226 | -0.257% | 0.676 | -0.359% | [-0.546%, +0.102%] | -0.384% | [-0.948%, +0.159%] |
| RED_CROSS:2 | atr_runner:sl1:trail1.5:economic | 226 | -0.166% | 0.642 | -0.275% | [-0.278%, -0.055%] | +0.081% | [-0.086%, +0.235%] |
| RED_RESUME:2 | color:sl0 | 182 | -0.233% | 0.865 | -0.313% | [-1.228%, +0.786%] | +0.458% | [-0.658%, +1.627%] |
| RED_RESUME:2 | color:sl1 | 182 | -0.381% | 0.579 | -0.475% | [-0.773%, +0.098%] | -0.140% | [-0.561%, +0.315%] |
| RED_RESUME:2 | atr_runner:sl1:trail1.5:economic | 182 | -0.250% | 0.552 | -0.363% | [-0.450%, -0.055%] | +0.018% | [-0.188%, +0.232%] |

### Todos los vecinos y baselines pre-registrados

| evento:confirm | modelo | n | net | PF | R |
| --- | --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | atr_runner:sl0.75:trail1.5:economic | 208 | -0.163% | 0.522 | -0.343 |
| GREEN_CROSS:1 | atr_runner:sl1:trail1.5:economic | 208 | -0.185% | 0.578 | -0.322 |
| GREEN_CROSS:1 | atr_runner:sl1.25:trail1.5:economic | 208 | -0.172% | 0.660 | -0.229 |
| GREEN_CROSS:1 | atr_runner:sl1.5:trail1.5:economic | 208 | -0.168% | 0.705 | -0.180 |
| GREEN_CROSS:1 | atr_runner:sl1:trail1:economic | 208 | -0.203% | 0.537 | -0.365 |
| GREEN_CROSS:1 | atr_runner:sl1:trail2:economic | 208 | -0.183% | 0.582 | -0.300 |
| GREEN_CROSS:1 | atr_runner:sl1:trail1.5:naive | 208 | -0.185% | 0.578 | -0.322 |
| GREEN_CROSS:1 | color:sl0 | 207 | +0.044% | 1.031 | 0.502 |
| GREEN_CROSS:1 | color:sl0.75 | 208 | -0.143% | 0.753 | -0.036 |
| GREEN_CROSS:1 | color:sl1 | 208 | -0.183% | 0.739 | -0.137 |
| GREEN_CROSS:1 | color:sl1.25 | 208 | -0.073% | 0.910 | 0.113 |
| GREEN_CROSS:1 | color:sl1.5 | 208 | -0.110% | 0.882 | 0.153 |
| GREEN_CROSS:1 | fixed1r:sl1 | 208 | -0.192% | 0.563 | -0.372 |
| GREEN_CROSS:1 | fixed2r:sl1 | 208 | -0.222% | 0.610 | -0.388 |
| GREEN_CROSS:1 | fixed3r:sl1 | 208 | -0.296% | 0.540 | -0.490 |
| GREEN_CROSS:1 | color_runner:sl1:economic | 208 | -0.115% | 0.739 | -0.090 |
| GREEN_RESUME:1 | atr_runner:sl0.75:trail1.5:economic | 228 | -0.169% | 0.495 | -0.390 |
| GREEN_RESUME:1 | atr_runner:sl1:trail1.5:economic | 228 | -0.146% | 0.646 | -0.253 |
| GREEN_RESUME:1 | atr_runner:sl1.25:trail1.5:economic | 228 | -0.150% | 0.695 | -0.225 |
| GREEN_RESUME:1 | atr_runner:sl1.5:trail1.5:economic | 228 | -0.122% | 0.787 | -0.131 |
| GREEN_RESUME:1 | atr_runner:sl1:trail1:economic | 228 | -0.140% | 0.660 | -0.240 |
| GREEN_RESUME:1 | atr_runner:sl1:trail2:economic | 228 | -0.150% | 0.637 | -0.265 |
| GREEN_RESUME:1 | atr_runner:sl1:trail1.5:naive | 228 | -0.148% | 0.642 | -0.255 |
| GREEN_RESUME:1 | color:sl0 | 228 | +0.727% | 1.534 | 2.036 |
| GREEN_RESUME:1 | color:sl0.75 | 228 | -0.004% | 0.994 | -0.030 |
| GREEN_RESUME:1 | color:sl1 | 228 | +0.055% | 1.081 | 0.107 |
| GREEN_RESUME:1 | color:sl1.25 | 228 | -0.010% | 0.988 | -0.018 |
| GREEN_RESUME:1 | color:sl1.5 | 228 | +0.087% | 1.099 | 0.154 |
| GREEN_RESUME:1 | fixed1r:sl1 | 228 | -0.149% | 0.639 | -0.239 |
| GREEN_RESUME:1 | fixed2r:sl1 | 228 | -0.099% | 0.812 | -0.185 |
| GREEN_RESUME:1 | fixed3r:sl1 | 228 | -0.014% | 0.976 | -0.047 |
| GREEN_RESUME:1 | color_runner:sl1:economic | 228 | -0.068% | 0.836 | -0.175 |
| RED_CROSS:1 | atr_runner:sl0.75:trail1.5:economic | 281 | -0.198% | 0.444 | -0.395 |
| RED_CROSS:1 | atr_runner:sl1:trail1.5:economic | 281 | -0.211% | 0.530 | -0.329 |
| RED_CROSS:1 | atr_runner:sl1.25:trail1.5:economic | 281 | -0.222% | 0.586 | -0.292 |
| RED_CROSS:1 | atr_runner:sl1.5:trail1.5:economic | 281 | -0.263% | 0.592 | -0.271 |
| RED_CROSS:1 | atr_runner:sl1:trail1:economic | 281 | -0.196% | 0.565 | -0.308 |
| RED_CROSS:1 | atr_runner:sl1:trail2:economic | 281 | -0.176% | 0.607 | -0.292 |
| RED_CROSS:1 | atr_runner:sl1:trail1.5:naive | 281 | -0.216% | 0.521 | -0.339 |
| RED_CROSS:1 | color:sl0 | 281 | -0.473% | 0.748 | -0.377 |
| RED_CROSS:1 | color:sl0.75 | 281 | -0.283% | 0.559 | -0.443 |
| RED_CROSS:1 | color:sl1 | 281 | -0.317% | 0.596 | -0.335 |
| RED_CROSS:1 | color:sl1.25 | 281 | -0.341% | 0.626 | -0.317 |
| RED_CROSS:1 | color:sl1.5 | 281 | -0.378% | 0.632 | -0.289 |
| RED_CROSS:1 | fixed1r:sl1 | 281 | -0.138% | 0.693 | -0.239 |
| RED_CROSS:1 | fixed2r:sl1 | 281 | -0.148% | 0.752 | -0.251 |
| RED_CROSS:1 | fixed3r:sl1 | 281 | -0.122% | 0.816 | -0.200 |
| RED_CROSS:1 | color_runner:sl1:economic | 281 | -0.195% | 0.565 | -0.246 |
| RED_RESUME:1 | atr_runner:sl0.75:trail1.5:economic | 266 | -0.224% | 0.408 | -0.367 |
| RED_RESUME:1 | atr_runner:sl1:trail1.5:economic | 266 | -0.188% | 0.628 | -0.270 |
| RED_RESUME:1 | atr_runner:sl1.25:trail1.5:economic | 266 | -0.261% | 0.601 | -0.283 |
| RED_RESUME:1 | atr_runner:sl1.5:trail1.5:economic | 266 | -0.321% | 0.591 | -0.274 |
| RED_RESUME:1 | atr_runner:sl1:trail1:economic | 266 | -0.178% | 0.647 | -0.263 |
| RED_RESUME:1 | atr_runner:sl1:trail2:economic | 266 | -0.228% | 0.549 | -0.318 |
| RED_RESUME:1 | atr_runner:sl1:trail1.5:naive | 266 | -0.225% | 0.555 | -0.301 |
| RED_RESUME:1 | color:sl0 | 266 | -0.391% | 0.776 | -0.278 |
| RED_RESUME:1 | color:sl0.75 | 266 | -0.449% | 0.381 | -0.680 |
| RED_RESUME:1 | color:sl1 | 266 | -0.447% | 0.496 | -0.494 |
| RED_RESUME:1 | color:sl1.25 | 266 | -0.487% | 0.526 | -0.398 |
| RED_RESUME:1 | color:sl1.5 | 266 | -0.500% | 0.565 | -0.335 |
| RED_RESUME:1 | fixed1r:sl1 | 266 | -0.156% | 0.691 | -0.229 |
| RED_RESUME:1 | fixed2r:sl1 | 266 | -0.264% | 0.624 | -0.331 |
| RED_RESUME:1 | fixed3r:sl1 | 266 | -0.278% | 0.643 | -0.376 |
| RED_RESUME:1 | color_runner:sl1:economic | 266 | -0.269% | 0.469 | -0.328 |
| GREEN_CROSS:2 | atr_runner:sl0.75:trail1.5:economic | 177 | -0.198% | 0.456 | -0.424 |
| GREEN_CROSS:2 | atr_runner:sl1:trail1.5:economic | 177 | -0.221% | 0.516 | -0.348 |
| GREEN_CROSS:2 | atr_runner:sl1.25:trail1.5:economic | 177 | -0.238% | 0.558 | -0.310 |
| GREEN_CROSS:2 | atr_runner:sl1.5:trail1.5:economic | 177 | -0.196% | 0.667 | -0.225 |
| GREEN_CROSS:2 | atr_runner:sl1:trail1:economic | 177 | -0.185% | 0.595 | -0.300 |
| GREEN_CROSS:2 | atr_runner:sl1:trail2:economic | 177 | -0.229% | 0.500 | -0.347 |
| GREEN_CROSS:2 | atr_runner:sl1:trail1.5:naive | 177 | -0.216% | 0.528 | -0.345 |
| GREEN_CROSS:2 | color:sl0 | 176 | -0.178% | 0.887 | -0.024 |
| GREEN_CROSS:2 | color:sl0.75 | 177 | -0.131% | 0.782 | 0.042 |
| GREEN_CROSS:2 | color:sl1 | 177 | -0.141% | 0.806 | 0.032 |
| GREEN_CROSS:2 | color:sl1.25 | 177 | -0.162% | 0.806 | -0.012 |
| GREEN_CROSS:2 | color:sl1.5 | 177 | -0.174% | 0.816 | -0.041 |
| GREEN_CROSS:2 | fixed1r:sl1 | 177 | -0.208% | 0.544 | -0.367 |
| GREEN_CROSS:2 | fixed2r:sl1 | 177 | -0.216% | 0.627 | -0.380 |
| GREEN_CROSS:2 | fixed3r:sl1 | 177 | -0.303% | 0.538 | -0.484 |
| GREEN_CROSS:2 | color_runner:sl1:economic | 177 | -0.220% | 0.519 | -0.247 |
| GREEN_RESUME:2 | atr_runner:sl0.75:trail1.5:economic | 141 | -0.077% | 0.741 | -0.250 |
| GREEN_RESUME:2 | atr_runner:sl1:trail1.5:economic | 141 | -0.106% | 0.727 | -0.224 |
| GREEN_RESUME:2 | atr_runner:sl1.25:trail1.5:economic | 141 | -0.050% | 0.891 | -0.110 |
| GREEN_RESUME:2 | atr_runner:sl1.5:trail1.5:economic | 141 | -0.034% | 0.937 | -0.069 |
| GREEN_RESUME:2 | atr_runner:sl1:trail1:economic | 141 | -0.089% | 0.771 | -0.199 |
| GREEN_RESUME:2 | atr_runner:sl1:trail2:economic | 141 | -0.128% | 0.672 | -0.269 |
| GREEN_RESUME:2 | atr_runner:sl1:trail1.5:naive | 141 | -0.103% | 0.736 | -0.218 |
| GREEN_RESUME:2 | color:sl0 | 141 | +0.915% | 1.669 | 2.456 |
| GREEN_RESUME:2 | color:sl0.75 | 141 | +0.303% | 1.577 | 0.598 |
| GREEN_RESUME:2 | color:sl1 | 141 | +0.353% | 1.551 | 0.743 |
| GREEN_RESUME:2 | color:sl1.25 | 141 | +0.488% | 1.666 | 0.950 |
| GREEN_RESUME:2 | color:sl1.5 | 141 | +0.393% | 1.468 | 0.693 |
| GREEN_RESUME:2 | fixed1r:sl1 | 141 | -0.109% | 0.721 | -0.224 |
| GREEN_RESUME:2 | fixed2r:sl1 | 141 | -0.014% | 0.972 | -0.066 |
| GREEN_RESUME:2 | fixed3r:sl1 | 141 | -0.013% | 0.978 | -0.069 |
| GREEN_RESUME:2 | color_runner:sl1:economic | 141 | +0.003% | 1.008 | -0.074 |
| RED_CROSS:2 | atr_runner:sl0.75:trail1.5:economic | 226 | -0.163% | 0.525 | -0.380 |
| RED_CROSS:2 | atr_runner:sl1:trail1.5:economic | 226 | -0.166% | 0.642 | -0.280 |
| RED_CROSS:2 | atr_runner:sl1.25:trail1.5:economic | 226 | -0.140% | 0.734 | -0.225 |
| RED_CROSS:2 | atr_runner:sl1.5:trail1.5:economic | 226 | -0.192% | 0.701 | -0.218 |
| RED_CROSS:2 | atr_runner:sl1:trail1:economic | 226 | -0.161% | 0.655 | -0.279 |
| RED_CROSS:2 | atr_runner:sl1:trail2:economic | 226 | -0.083% | 0.821 | -0.216 |
| RED_CROSS:2 | atr_runner:sl1:trail1.5:naive | 226 | -0.184% | 0.605 | -0.297 |
| RED_CROSS:2 | color:sl0 | 226 | -0.553% | 0.716 | -0.488 |
| RED_CROSS:2 | color:sl0.75 | 226 | -0.187% | 0.713 | -0.292 |
| RED_CROSS:2 | color:sl1 | 226 | -0.257% | 0.676 | -0.277 |
| RED_CROSS:2 | color:sl1.25 | 226 | -0.298% | 0.676 | -0.271 |
| RED_CROSS:2 | color:sl1.5 | 226 | -0.315% | 0.698 | -0.222 |
| RED_CROSS:2 | fixed1r:sl1 | 226 | -0.135% | 0.710 | -0.241 |
| RED_CROSS:2 | fixed2r:sl1 | 226 | -0.031% | 0.946 | -0.136 |
| RED_CROSS:2 | fixed3r:sl1 | 226 | -0.051% | 0.924 | -0.146 |
| RED_CROSS:2 | color_runner:sl1:economic | 226 | -0.183% | 0.606 | -0.208 |
| RED_RESUME:2 | atr_runner:sl0.75:trail1.5:economic | 182 | -0.191% | 0.511 | -0.329 |
| RED_RESUME:2 | atr_runner:sl1:trail1.5:economic | 182 | -0.250% | 0.552 | -0.303 |
| RED_RESUME:2 | atr_runner:sl1.25:trail1.5:economic | 182 | -0.291% | 0.557 | -0.281 |
| RED_RESUME:2 | atr_runner:sl1.5:trail1.5:economic | 182 | -0.253% | 0.660 | -0.202 |
| RED_RESUME:2 | atr_runner:sl1:trail1:economic | 182 | -0.235% | 0.579 | -0.311 |
| RED_RESUME:2 | atr_runner:sl1:trail2:economic | 182 | -0.290% | 0.480 | -0.348 |
| RED_RESUME:2 | atr_runner:sl1:trail1.5:naive | 182 | -0.255% | 0.543 | -0.317 |
| RED_RESUME:2 | color:sl0 | 182 | -0.233% | 0.865 | 0.003 |
| RED_RESUME:2 | color:sl0.75 | 182 | -0.338% | 0.543 | -0.348 |
| RED_RESUME:2 | color:sl1 | 182 | -0.381% | 0.579 | -0.318 |
| RED_RESUME:2 | color:sl1.25 | 182 | -0.320% | 0.691 | -0.178 |
| RED_RESUME:2 | color:sl1.5 | 182 | -0.325% | 0.716 | -0.173 |
| RED_RESUME:2 | fixed1r:sl1 | 182 | -0.218% | 0.609 | -0.287 |
| RED_RESUME:2 | fixed2r:sl1 | 182 | -0.298% | 0.597 | -0.352 |
| RED_RESUME:2 | fixed3r:sl1 | 182 | -0.365% | 0.559 | -0.450 |
| RED_RESUME:2 | color_runner:sl1:economic | 182 | -0.270% | 0.515 | -0.241 |

### Año, tendencia 4H y volatilidad (selección congelada)

| evento:confirm | desglose | n | net | PF |
| --- | --- | --- | --- | --- |
| GREEN_CROSS:1 | yearly:2024 | 70 | +0.408% | 1.321 |
| GREEN_CROSS:1 | yearly:2025 | 75 | -0.387% | 0.751 |
| GREEN_CROSS:1 | yearly:2026 | 62 | +0.155% | 1.108 |
| GREEN_CROSS:1 | regime4:BULL | 152 | +0.032% | 1.023 |
| GREEN_CROSS:1 | regime4:BEAR | 55 | +0.079% | 1.052 |
| GREEN_CROSS:1 | volatility:1 | 141 | +0.305% | 1.224 |
| GREEN_CROSS:1 | volatility:2 | 48 | -0.371% | 0.740 |
| GREEN_CROSS:1 | volatility:3 | 14 | -0.421% | 0.729 |
| GREEN_CROSS:1 | volatility:4 | 4 | -2.513% | 0.208 |
| GREEN_RESUME:1 | yearly:2024 | 76 | +1.185% | 1.939 |
| GREEN_RESUME:1 | yearly:2025 | 72 | +0.255% | 1.209 |
| GREEN_RESUME:1 | yearly:2026 | 80 | +0.718% | 1.454 |
| GREEN_RESUME:1 | regime4:BULL | 183 | +0.992% | 1.794 |
| GREEN_RESUME:1 | regime4:BEAR | 45 | -0.349% | 0.808 |
| GREEN_RESUME:1 | volatility:1 | 167 | +1.015% | 1.872 |
| GREEN_RESUME:1 | volatility:2 | 41 | +0.977% | 1.751 |
| GREEN_RESUME:1 | volatility:3 | 17 | -2.407% | 0.311 |
| GREEN_RESUME:1 | volatility:4 | 3 | -0.948% | 0.139 |
| RED_CROSS:1 | yearly:2024 | 117 | -0.090% | 0.793 |
| RED_CROSS:1 | yearly:2025 | 96 | -0.334% | 0.240 |
| RED_CROSS:1 | yearly:2026 | 68 | -0.181% | 0.631 |
| RED_CROSS:1 | regime4:BULL | 113 | -0.255% | 0.408 |
| RED_CROSS:1 | regime4:BEAR | 168 | -0.155% | 0.664 |
| RED_CROSS:1 | volatility:1 | 168 | -0.186% | 0.510 |
| RED_CROSS:1 | volatility:2 | 70 | -0.151% | 0.694 |
| RED_CROSS:1 | volatility:3 | 27 | -0.157% | 0.690 |
| RED_CROSS:1 | volatility:4 | 16 | -0.550% | 0.380 |
| RED_RESUME:1 | yearly:2024 | 98 | -0.078% | 0.849 |
| RED_RESUME:1 | yearly:2025 | 105 | -0.233% | 0.564 |
| RED_RESUME:1 | yearly:2026 | 63 | -0.244% | 0.448 |
| RED_RESUME:1 | regime4:BULL | 61 | -0.306% | 0.400 |
| RED_RESUME:1 | regime4:BEAR | 205 | -0.140% | 0.722 |
| RED_RESUME:1 | volatility:1 | 133 | -0.282% | 0.326 |
| RED_RESUME:1 | volatility:2 | 64 | +0.066% | 1.169 |
| RED_RESUME:1 | volatility:3 | 43 | +0.055% | 1.085 |
| RED_RESUME:1 | volatility:4 | 26 | -0.637% | 0.369 |
| GREEN_CROSS:2 | yearly:2024 | 65 | -0.312% | 0.431 |
| GREEN_CROSS:2 | yearly:2025 | 59 | -0.289% | 0.389 |
| GREEN_CROSS:2 | yearly:2026 | 53 | -0.034% | 0.894 |
| GREEN_CROSS:2 | regime4:BULL | 133 | -0.145% | 0.657 |
| GREEN_CROSS:2 | regime4:BEAR | 44 | -0.451% | 0.194 |
| GREEN_CROSS:2 | volatility:1 | 119 | -0.140% | 0.634 |
| GREEN_CROSS:2 | volatility:2 | 42 | -0.234% | 0.526 |
| GREEN_CROSS:2 | volatility:3 | 11 | -0.827% | 0.088 |
| GREEN_CROSS:2 | volatility:4 | 5 | -0.722% | 0.234 |
| GREEN_RESUME:2 | yearly:2024 | 50 | +0.018% | 1.043 |
| GREEN_RESUME:2 | yearly:2025 | 44 | -0.178% | 0.502 |
| GREEN_RESUME:2 | yearly:2026 | 47 | -0.172% | 0.541 |
| GREEN_RESUME:2 | regime4:BULL | 115 | -0.104% | 0.737 |
| GREEN_RESUME:2 | regime4:BEAR | 26 | -0.116% | 0.675 |
| GREEN_RESUME:2 | volatility:1 | 104 | -0.169% | 0.542 |
| GREEN_RESUME:2 | volatility:2 | 26 | +0.123% | 1.313 |
| GREEN_RESUME:2 | volatility:3 | 10 | -0.059% | 0.906 |
| GREEN_RESUME:2 | volatility:4 | 1 | -0.000% | 0.000 |
| RED_CROSS:2 | yearly:2024 | 92 | -0.162% | 0.689 |
| RED_CROSS:2 | yearly:2025 | 79 | -0.119% | 0.721 |
| RED_CROSS:2 | yearly:2026 | 55 | -0.112% | 0.735 |
| RED_CROSS:2 | regime4:BULL | 90 | -0.260% | 0.507 |
| RED_CROSS:2 | regime4:BEAR | 136 | -0.053% | 0.876 |
| RED_CROSS:2 | volatility:1 | 125 | -0.208% | 0.477 |
| RED_CROSS:2 | volatility:2 | 57 | +0.011% | 1.027 |
| RED_CROSS:2 | volatility:3 | 29 | -0.338% | 0.560 |
| RED_CROSS:2 | volatility:4 | 15 | +0.309% | 1.496 |
| RED_RESUME:2 | yearly:2024 | 66 | -0.275% | 0.658 |
| RED_RESUME:2 | yearly:2025 | 76 | -0.277% | 0.617 |
| RED_RESUME:2 | yearly:2026 | 40 | -0.375% | 0.435 |
| RED_RESUME:2 | regime4:BULL | 42 | -0.632% | 0.206 |
| RED_RESUME:2 | regime4:BEAR | 140 | -0.197% | 0.726 |
| RED_RESUME:2 | volatility:1 | 89 | -0.218% | 0.578 |
| RED_RESUME:2 | volatility:2 | 37 | -0.131% | 0.808 |
| RED_RESUME:2 | volatility:3 | 34 | -0.297% | 0.677 |
| RED_RESUME:2 | volatility:4 | 22 | -0.904% | 0.380 |

## 5. Controles y límites de inferencia

Un timestamp no-evento por señal, seed773, muestreo con reemplazo. Coincidencia exacta año/mes, hora UTC, régimen4H y quartil TRAIN. Se excluye unión de eventos de una/dos barras. No se relajan strata ausentes. Se informa número emparejado y timestamps únicos en JSON. Cada control recibe la misma dirección/modelo/calendario de futuros cambios de color que el evento. Los controles de alineación 1D no están emparejados por 1D: son descriptivos. Bootstrap semanal 1000 draws seed773, bloques que contienen señales; no hay ajuste por múltiples eventos/horizontes. Los resultados de controles tienen incertidumbre de una extracción fija; no son prueba definitiva de causalidad.

Regímenes, años, CROSS/RESUME, lados y horizontes completos están separados en JSON. Reciente desde 2025-10-01 es descriptivo, nunca reemplaza TEST. No se usan screenshots como etiquetas. Comparación con 15m: aquel experimento usaba SL0.30%/$500 y cap48h; éste ATR/cap72h. Una diferencia de retornos no prueba que cambiar únicamente el timeframe sea la causa.

## 6. Criterios y clasificación

Los criterios se fijaron antes de TEST en protocolo; basta un fallo para impedir PROMISING. INTERESTING significa retorno seleccionado positivo sin evidencia suficiente, no permiso de operar.

| evento:confirm | clasificación | criterios que FALLAN |
| --- | --- | --- |
| GREEN_CROSS:1 | INTERESTING BUT INCONCLUSIVE | profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, control_advantage, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| GREEN_RESUME:1 | INTERESTING BUT INCONCLUSIVE | bootstrap_positive, neighbor_stable |
| RED_CROSS:1 | NO EDGE | development_positive, test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, control_advantage, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| RED_RESUME:1 | NO EDGE | development_positive, test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, control_advantage, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| GREEN_CROSS:2 | NO EDGE | development_positive, test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, control_advantage, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| GREEN_RESUME:2 | NO EDGE | development_positive, test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| RED_CROSS:2 | NO EDGE | development_positive, test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, paired_bootstrap_positive, yearly_stable, neighbor_stable |
| RED_RESUME:2 | NO EDGE | test_positive, profit_factor, stressed_positive, without_best3_positive, bootstrap_positive, control_advantage, paired_bootstrap_positive, yearly_stable, neighbor_stable |

**Conclusión única del estudio: INTERESTING BUT INCONCLUSIVE.**

Sin órdenes, account APIs, secretos, leverage, deployment o habilitación. Manual Copilot, Guardian, Forward Audit, V8 y Early Breakout permanecen intactos. La incertidumbre de paridad sigue explícita; cualquier futuro shadow debe identificarse como port causal.

## Reproducción

```powershell
# Dataset PR19 verificado + tail público fijado; no datos gigantes en Git
python -m research.mlrsi_1h_data --cutoff 1791061200000 --refresh
python -m research.mlrsi_1h_run --phase development --cutoff 1791061200000
# frozen_selection.json queda escrito ANTES de TEST
python -m research.mlrsi_1h_run --phase test --cutoff 1791061200000
python -m research.mlrsi_1h_report
python -m unittest research.test_mlrsi_1h -v
python -m unittest discover -v
```

La preparación parte del dataset cache de PR19; en un checkout limpio reconstruir primero ese dataset siguiendo sus URLs/checksums. `input_manifest.json` conserva su provenance exacta. El manifest final identifica el tail fijado y su hash; se pueden reusar respuestas cacheadas para evitar depender de red. Ninguna CLI accede a cuentas.
