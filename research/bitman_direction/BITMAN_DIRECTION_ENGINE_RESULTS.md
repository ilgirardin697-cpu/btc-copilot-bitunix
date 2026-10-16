# I-GOD BITMAN BTC DIRECTION ENGINE v0.1

**INCONCLUSIVE DIRECTION ENGINE**

Esta investigación pregunta si BTC se desplaza después en la dirección anunciada; no prueba entradas/salidas ni maximiza PnL. No ha demostrado utilidad incremental suficientemente robusta. No recomendar Telegram de producción ni sustituir/silenciar V8 con este resultado.

Base: `7fc762522be9bae6bd1ac799dbcc2a9ab9e512c7`; cutoff `2026-10-15T19:00:00Z`; versión `BITMAN_BTC_DIRECTION_ENGINE_0_1`.
Phase2=REJECT; BITMAN REALv0.1=INCONCLUSIVE; Phase4=INCONCLUSIVE: todos intactos. Esto no pretende reparar esos resultados ni replicar toda la metodología privada de Bitman.

## Respuesta práctica

TEST72h, núcleo público MTF: **UP n702, acierto50,85%, media firmada+0,591%, mediana+0,093%**. Exceso contra control−0,122pp, IC95[−0,920,+0,626]pp. **DOWN n697, acierto44,76%, media+0,009%, mediana−0,377%**; exceso+0,086pp, IC95[−0,643,+0,773]pp. No ventaja robusta. Muchos outcomes se solapan; n no es número de apuestas independientes.

Sin los mejores3 retornos72h: UP media+0,509% pero exceso−0,182pp; DOWN media−0,048% con exceso+0,035pp. No se rearman episodios para rellenar observaciones retiradas. No se interpretan medias brutas como dinero ganado ni como razón para entrar.

**ML RSI confirmado: PENDING_ACTUAL_CONFIRMED_EXPORT.** No se recomputó el port ni se sustituyó por RSI clásico/research. El observer actual produce15m/1H/4H, no1D;15m no participa y1DML permaneceUNKNOWN. Por ello el histórico mide el **núcleo público sin confirmación ML real**, no una validación del motor completo.

Ruido histórico: **5,14 cambios de estado/día;7,89 firmas materiales/día**, frente0,164 de V8LONG/FLAT. El99,92% de las horas UP coinciden con V8LONG. No se demuestra información temporal distinta que justifique hacer visible este prototipo. No se cambia dedupe/reglas después de ver estos resultados.

## Provenance / datos / metodología

[SOURCES.md](SOURCES.md) reutiliza las cuatro transcripciones vidIQ de Phase4, con hashes originales. **Cero llamadas/cargos nuevos vidIQ**. Los vídeos fundamentan conceptos, no constantes privadas, la jerarquía exacta ni un porcentaje de aciertos. KONKORDE_PROXY público; **EXACT BITMAN KONKORDE PARITY: NOT PROVEN**. RSI privado adaptado y Trend Speed no se inventan.

Binance USD-M perpetual público,61.723 velas1H completas con warmup2019-10, mismo checksum/manifiesto que el estudio previo.1D/4H agregados completos UTC, sin interpolación. MLcache existente es BinanceSPOT: diferencia de venue explícita. No acceso privado Bitunix/volúmenesRailway.

TRAIN2020–21; VALIDATION2022–23; TEST2024–cutoff, **reused OOS, NOT virgin**. Protocolo/código/calibración de controles congelados antes del análisis. No candidatos optimizados ni reglas seleccionadas por TEST. Cuartiles ATR1H/precio TRAIN sirven solo para matching. Walk-forward2022–26 mantiene reglas y usa calibración de matching previa a cada año.

## Definiciones exactas y jerarquía

| Bloque | Función / definición |
|---|---|
| AO | SMA5(HL2)−SMA34(HL2). Contexto de signo; momentum requiere2 pendientes consecutivas del mismo signo O cruce de cero cerrado. Valor, pendiente, aceleración y acercamiento/alejamiento de cero visibles. |
| ADX/DI | Wilder14/14. ADX_TURN_UP: pendiente previa<=0, actual>0. ACCELERATING: pendiente>0 y segunda diferencia>0. DI confirma sentido. ADX no asigna UP/DOWN. |
| Koncorde | Proxy PR23 sin cambios. ENTRY/INSIDE positivos, EXIT, REENTRY<=3TFbars, contexto bajista PROXY. Distancia cero/separación continuas. EXIT no significa SHORT. |
| ML RSI | Solo color confirmado de cache/export validadoLOW29/EMA4/PINE_PARITY_V4. Sin aproximación, provisional ni approaching. Lectura<=90s, vela cerrada válida. Opuesto4H conocido=>CONFLICT; ausente=>UNKNOWN. |
| BBWP | CLOSE/SMA7/prior100. Percentil/subida/bajada/aceleración,cruce50 y distancia50; no puertas45/47/52 ni zonas optimizadas. |
| Niveles | Helper puro Copilot2L/2R; ventana220TFbars, timestamps de confirmación, 1H/4H/1D independientes. Día/semanaUTCprevios completos. No modificar Copilot. |
| 1D MACRO_BIAS | UP siAO>0 y+DI>−DI; DOWN siAO<0 y−DI>+DI; TRANSITION si desacuerdo; NEUTRAL si empate; UNKNOWN sin datos. |
| 4H SWING_BIAS | Misma definición de contexto, confirma/contradice al diario; no voto equivalente. |
| 1H TIMING_STATE | Impulso sostenido AO/cero conDIcorrespondiente: impulse_up/down; desacuerdo:transition; resto:no_impulse. Contra contextoD/4H alineado=>pullback, no giro macro. |

| Estado principal | Regla / detalle conservado |
|---|---|
| UP | 1DUP y4HUP. 1HUP=>UP_CONFIRMED;1HDOWN=>UP_WITH_1H_PULLBACK. No se invierte macro por una vela. |
| DOWN | 1DDOWN y4HDOWN. 1HDOWN=>DOWN_CONFIRMED;1HUP=>DOWN_WITH_1H_PULLBACK. |
| TRANSITION | 4H contradice macro y1H apoya al swing nuevo=>POSSIBLE_BULLISH/BEARISH_TRANSITION. Transición parcial con impulso1H=>EARLY_TRANSITION con lean explícito. |
| UNCLEAR | Falta macro/swing verificable o no hay jerarquía confirmada. No se asigna artificialmente sentido. |
| CONFLICT | Macro/swing opuestos sin timing que apoye transición, o prueba cerrada fallida de nivel mayor opuesto, oML4Hconfirmado opuesto. No es una orden. |

Un test estructural requiere nivel4H/1D **ya conocido al cierre1H anterior**, rango1H tocándolo y cierre del lado original. Ningún live mark crea pivots/autoridad; un nivel cruzado por1H mientras4H/1D no ha cerrado conserva su tipo y muestra confirmación pendiente. No se usa distancia rentable optimizada.

STRONG: contexto1D/4Halineado yADX+BBWPsubiendo enambos. BUILDING: presión direccional con4HADX+BBWP subiendo, o impulso1Halineado congiroADX1H+BBWPsubiendo. RestoWEAK. GradeA: UP/DOWN alineado,STRONG y confirmaciónML4Hapoyando; B:direcciónUP/DOWN restante; C:transición/unclear/conflict. Es **coherencia visual**, no evidence grade estadístico, probabilidad, sizing ni permiso de entrada.

## Episodios / métricas

Una dirección continua=un episodio aunque cambie strength/timing. Evento nuevo solo al cambiar estado. No evento artificial al empezar un split. TRANSITION conserva lean inicial cuando existe; UNCLEAR no tiene dirección y se describe en retorno BTCraw. CONFLICT puede conservar un lean para diagnóstico, nunca equivale aUP/DOWN.

Referencia=precio conocido al cierre; medir solo futuros1H completamente cerrados. LONGdir=futuro/ref−1; DOWNdir=1−futuro/ref. Acierto=retorno firmado>0 entre maduros, no tasa de trades ganadores. Sin entradas/salidas/fees/funding/margen: no se evalúa aquí rentabilidad de estrategia. MFE/MAE y barreras usan extremos OHLC cerrados; mismahoraambasbarreras=AMBIGUOUS, no éxito. No interpolar gaps; futuros/splits insuficientes permanecen incompletos.

Controles: hasta3 timestamps no-onset por año/mes/horaUTC, régimen4HSMA200 y cuartilvolatilidad. Misma madurez/split, selección por hash sin conocer outcomes. Bootstrap1000 bloques semanales,seed8192; solapamiento/multiplicidad/reutilizaciónTEST impiden afirmar prueba estadística definitiva.

### Nota de agregación descriptiva

El artefacto primario se conserva. Para estados con mezcla de lean0 y±1, su campo matched agregado mezcla retorno BTCraw y retorno firmado y **no debe usarse como evidencia direccional**. [canonical_control_reporting.json](artifacts/canonical_control_reporting.json) separa ambos desde los mismos registros inmutables. Es una corrección de presentación, sin cambiar señales, outcomes, resultados primariosUP/DOWN ni clasificación. Las tablas siguientes usan controles lean solo en el subgrupo firmado; paraUNCLEAR usan raw.

## MTF TRAIN / VALIDATION / TEST,72h

| Split | Estado | maduros | pendientes | con lean | acierto | media firmada | mediana firmada | media BTCraw | exceso control | IC95 exceso |
|---|---|---|---|---|---|---|---|---|---|---|
| TRAIN | UP | 542 | 0 | 542 | 62.36% | +2.065% | +1.838% | +2.065% | +0.031% | -1.536% / +1.363% |
| TRAIN | DOWN | 411 | 8 | 411 | 41.36% | -0.581% | -0.817% | +0.581% | -0.664% | -2.154% / +1.002% |
| TRAIN | TRANSITION | 814 | 0 | 814 | 49.75% | -0.382% | -0.034% | +0.887% | -0.076% | -0.593% / +0.484% |
| TRAIN | UNCLEAR | 529 | 0 | 0 | NA | NA | NA | +1.007% | -0.043% | -1.175% / +1.095% |
| TRAIN | CONFLICT | 1171 | 8 | 845 | 53.02% | +0.903% | +0.354% | +1.213% | -0.452% | -1.599% / +0.685% |
| VALIDATION | UP | 442 | 0 | 442 | 48.42% | +0.126% | -0.139% | +0.126% | -0.532% | -1.614% / +0.602% |
| VALIDATION | DOWN | 628 | 0 | 628 | 45.06% | -0.197% | -0.258% | +0.197% | -0.142% | -1.046% / +0.720% |
| VALIDATION | TRANSITION | 892 | 12 | 892 | 53.81% | +0.301% | +0.224% | -0.241% | +0.342% | -0.087% / +0.794% |
| VALIDATION | UNCLEAR | 597 | 11 | 0 | NA | NA | NA | -0.540% | -0.157% | -0.935% / +0.673% |
| VALIDATION | CONFLICT | 1279 | 0 | 970 | 46.29% | -0.089% | -0.196% | +0.243% | -0.450% | -1.133% / +0.205% |
| TEST | UP | 702 | 0 | 702 | 50.85% | +0.591% | +0.093% | +0.591% | -0.122% | -0.920% / +0.626% |
| TEST | DOWN | 697 | 0 | 697 | 44.76% | +0.009% | -0.377% | -0.009% | +0.086% | -0.643% / +0.773% |
| TEST | TRANSITION | 1273 | 7 | 1273 | 47.05% | -0.120% | -0.188% | +0.288% | -0.013% | -0.288% / +0.261% |
| TEST | UNCLEAR | 860 | 7 | 0 | NA | NA | NA | +0.259% | +0.079% | -0.394% / +0.555% |
| TEST | CONFLICT | 1687 | 3 | 1251 | 48.04% | +0.257% | -0.172% | +0.283% | +0.034% | -0.500% / +0.554% |

### Todos los horizontes MTF en TEST

| Estado | h | n maduros/total | acierto | media firmada | mediana | MFE mediana | MAE mediana |
|---|---|---|---|---|---|---|---|
| UP | 12 | 702/702 | 49.43% | +0.129% | -0.019% | +0.859% | -0.808% |
| UP | 24 | 702/702 | 50.71% | +0.256% | +0.026% | +1.311% | -1.273% |
| UP | 48 | 702/702 | 53.13% | +0.456% | +0.176% | +2.087% | -1.704% |
| UP | 72 | 702/702 | 50.85% | +0.591% | +0.093% | +2.548% | -2.070% |
| UP | 168 | 700/702 | 47.71% | +0.283% | -0.151% | +3.695% | -3.612% |
| UP | 336 | 690/702 | 52.61% | +1.198% | +0.233% | +5.860% | -4.824% |
| DOWN | 12 | 697/697 | 44.76% | -0.063% | -0.117% | +0.959% | -0.918% |
| DOWN | 24 | 697/697 | 45.48% | -0.036% | -0.208% | +1.418% | -1.348% |
| DOWN | 48 | 697/697 | 49.50% | +0.117% | -0.032% | +2.341% | -2.191% |
| DOWN | 72 | 697/697 | 44.76% | +0.009% | -0.377% | +3.050% | -2.738% |
| DOWN | 168 | 697/697 | 43.62% | -0.751% | -0.909% | +4.770% | -4.068% |
| DOWN | 336 | 697/697 | 42.18% | -0.607% | -1.586% | +6.245% | -6.057% |
| TRANSITION | 12 | 1280/1280 | 48.05% | +0.014% | -0.054% | +0.926% | -0.830% |
| TRANSITION | 24 | 1279/1280 | 47.30% | -0.059% | -0.117% | +1.279% | -1.243% |
| TRANSITION | 48 | 1275/1280 | 48.86% | -0.051% | -0.088% | +1.858% | -1.839% |
| TRANSITION | 72 | 1273/1280 | 47.05% | -0.120% | -0.188% | +2.289% | -2.250% |
| TRANSITION | 168 | 1268/1280 | 47.16% | -0.443% | -0.304% | +3.557% | -3.720% |
| TRANSITION | 336 | 1264/1280 | 49.29% | -0.325% | -0.071% | +5.115% | -5.605% |
| UNCLEAR | 12 | 867/867 | NA | NA | NA | NA | NA |
| UNCLEAR | 24 | 867/867 | NA | NA | NA | NA | NA |
| UNCLEAR | 48 | 864/867 | NA | NA | NA | NA | NA |
| UNCLEAR | 72 | 860/867 | NA | NA | NA | NA | NA |
| UNCLEAR | 168 | 858/867 | NA | NA | NA | NA | NA |
| UNCLEAR | 336 | 858/867 | NA | NA | NA | NA | NA |
| CONFLICT | 12 | 1689/1690 | 47.56% | +0.015% | -0.070% | +0.925% | -0.902% |
| CONFLICT | 24 | 1688/1690 | 48.76% | +0.132% | -0.044% | +1.377% | -1.341% |
| CONFLICT | 48 | 1688/1690 | 51.00% | +0.299% | +0.073% | +2.249% | -1.977% |
| CONFLICT | 72 | 1687/1690 | 48.04% | +0.257% | -0.172% | +2.859% | -2.431% |
| CONFLICT | 168 | 1682/1690 | 45.76% | -0.347% | -0.587% | +4.370% | -3.931% |
| CONFLICT | 336 | 1670/1690 | 46.90% | +0.150% | -0.512% | +5.988% | -5.575% |

## Contexto1D / swing4H / timing1H: endpoints propios

| TF | Split | Estado | h | n maduros/total | acierto | media firmada | mediana | MFE mediana | MAE mediana |
|---|---|---|---|---|---|---|---|---|---|
| 1H | TRAIN | UP | 12 | 547/547 | 49.18% | +0.128% | -0.019% | +1.321% | -1.338% |
| 1H | TRAIN | DOWN | 12 | 489/490 | 45.40% | +0.110% | -0.206% | +1.352% | -1.340% |
| 1H | VALIDATION | UP | 12 | 553/553 | 46.47% | -0.057% | -0.055% | +0.923% | -0.868% |
| 1H | VALIDATION | DOWN | 12 | 538/538 | 45.54% | -0.100% | -0.057% | +0.857% | -0.900% |
| 1H | TEST | UP | 4 | 765/765 | 49.41% | +0.035% | -0.008% | +0.467% | -0.445% |
| 1H | TEST | UP | 12 | 765/765 | 48.76% | +0.041% | -0.029% | +0.856% | -0.848% |
| 1H | TEST | UP | 24 | 765/765 | 50.98% | +0.162% | +0.125% | +1.270% | -1.152% |
| 1H | TEST | DOWN | 4 | 686/686 | 46.94% | -0.043% | -0.075% | +0.447% | -0.473% |
| 1H | TEST | DOWN | 12 | 686/686 | 47.08% | -0.123% | -0.100% | +0.851% | -0.851% |
| 1H | TEST | DOWN | 24 | 686/686 | 47.67% | -0.218% | -0.074% | +1.267% | -1.388% |
| 4H | TRAIN | UP | 24 | 133/133 | 54.14% | +0.173% | +0.276% | +2.120% | -1.880% |
| 4H | TRAIN | DOWN | 24 | 104/104 | 52.88% | +0.055% | +0.114% | +2.033% | -1.738% |
| 4H | VALIDATION | UP | 24 | 119/119 | 44.54% | -0.012% | -0.219% | +1.409% | -1.538% |
| 4H | VALIDATION | DOWN | 24 | 128/128 | 52.34% | +0.196% | +0.049% | +1.461% | -1.261% |
| 4H | TEST | UP | 12 | 186/186 | 48.92% | +0.014% | -0.017% | +1.006% | -0.910% |
| 4H | TEST | UP | 24 | 186/186 | 48.39% | -0.038% | -0.094% | +1.397% | -1.240% |
| 4H | TEST | UP | 48 | 186/186 | 50.54% | +0.304% | +0.128% | +1.990% | -1.902% |
| 4H | TEST | UP | 72 | 186/186 | 52.69% | +0.682% | +0.263% | +2.681% | -2.334% |
| 4H | TEST | DOWN | 12 | 182/182 | 48.35% | -0.066% | -0.040% | +1.029% | -0.882% |
| 4H | TEST | DOWN | 24 | 181/182 | 45.30% | -0.133% | -0.161% | +1.397% | -1.264% |
| 4H | TEST | DOWN | 48 | 181/182 | 46.96% | -0.194% | -0.236% | +1.997% | -1.923% |
| 4H | TEST | DOWN | 72 | 180/182 | 45.00% | -0.414% | -0.612% | +2.311% | -2.495% |
| 1D | TRAIN | UP | 72 | 22/22 | 68.18% | +1.028% | +2.026% | +4.503% | -2.392% |
| 1D | TRAIN | DOWN | 72 | 14/14 | 42.86% | +0.500% | -0.393% | +3.352% | -3.158% |
| 1D | VALIDATION | UP | 72 | 18/18 | 55.56% | +1.022% | +0.561% | +3.552% | -1.595% |
| 1D | VALIDATION | DOWN | 72 | 21/21 | 57.14% | +2.382% | +0.656% | +2.660% | -1.737% |
| 1D | TEST | UP | 24 | 30/30 | 53.33% | +0.249% | +0.122% | +1.537% | -1.110% |
| 1D | TEST | UP | 72 | 30/30 | 46.67% | +0.590% | -0.190% | +2.817% | -1.849% |
| 1D | TEST | UP | 168 | 30/30 | 60.00% | +1.763% | +1.443% | +5.015% | -2.532% |
| 1D | TEST | UP | 336 | 30/30 | 60.00% | +1.971% | +0.891% | +8.208% | -4.246% |
| 1D | TEST | DOWN | 24 | 29/29 | 48.28% | -0.155% | -0.160% | +1.373% | -1.336% |
| 1D | TEST | DOWN | 72 | 29/29 | 41.38% | -0.955% | -0.161% | +1.924% | -2.160% |
| 1D | TEST | DOWN | 168 | 29/29 | 58.62% | -0.630% | +1.016% | +4.016% | -4.053% |
| 1D | TEST | DOWN | 336 | 29/29 | 44.83% | -1.116% | -0.316% | +6.425% | -4.053% |

Muestras diarias pequeñas (TEST30UP/29DOWN); no promoción ni conclusiones fuertes de subgrupos pequeños. Los JSON conservan todos los estados/horizontes y las dos versiones de controles.

## DIRECTIONAL_10PCT_EXTENSION —2/5/10%, no take profit

| Estado | h | objetivo | n | toca favorable | toca adverso | favorable antes adverso | ambiguo | no resuelto | horas mediana si toca | adverso previo seguro | adverso incl.hora toque |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UP | 24 | 2% | 702 | 35.19% | 27.78% | 33.05% | 0.00% | 40.88% | 12.00 | +0.461% | +0.463% |
| UP | 24 | 5% | 702 | 7.55% | 4.70% | 7.55% | 0.00% | 87.75% | 16.00 | +0.284% | +0.284% |
| UP | 24 | 10% | 702 | 0.28% | 0.28% | 0.28% | 0.00% | 99.43% | 20.50 | +0.337% | +0.337% |
| UP | 72 | 2% | 702 | 59.26% | 51.14% | 51.57% | 0.00% | 7.26% | 18.00 | +0.752% | +0.756% |
| UP | 72 | 5% | 702 | 25.93% | 15.38% | 25.78% | 0.00% | 59.69% | 37.00 | +0.801% | +0.801% |
| UP | 72 | 10% | 702 | 2.14% | 2.56% | 2.14% | 0.00% | 95.30% | 43.00 | +0.644% | +0.644% |
| UP | 168 | 2% | 700 | 71.57% | 65.71% | 55.14% | 0.00% | 0.29% | 25.00 | +1.043% | +1.043% |
| UP | 168 | 5% | 700 | 40.86% | 36.71% | 39.29% | 0.00% | 28.00% | 56.00 | +1.199% | +1.199% |
| UP | 168 | 10% | 700 | 9.86% | 7.57% | 9.86% | 0.00% | 82.57% | 104.00 | +0.827% | +0.827% |
| UP | 336 | 2% | 690 | 83.77% | 74.78% | 55.07% | 0.00% | 0.00% | 33.00 | +1.348% | +1.348% |
| UP | 336 | 5% | 690 | 57.54% | 48.84% | 54.78% | 0.00% | 5.94% | 81.00 | +1.632% | +1.632% |
| UP | 336 | 10% | 690 | 24.64% | 17.68% | 24.64% | 0.00% | 57.68% | 213.00 | +1.649% | +1.649% |
| DOWN | 24 | 2% | 697 | 40.60% | 36.59% | 37.73% | 0.00% | 29.84% | 9.00 | +0.530% | +0.537% |
| DOWN | 24 | 5% | 697 | 9.76% | 5.74% | 9.76% | 0.00% | 84.51% | 15.00 | +0.487% | +0.487% |
| DOWN | 24 | 10% | 697 | 0.43% | 0.29% | 0.43% | 0.00% | 99.28% | 18.00 | +0.333% | +0.333% |
| DOWN | 72 | 2% | 697 | 65.14% | 62.27% | 51.51% | 0.00% | 2.01% | 17.00 | +0.799% | +0.799% |
| DOWN | 72 | 5% | 697 | 28.55% | 19.51% | 28.26% | 0.00% | 53.80% | 33.00 | +0.772% | +0.772% |
| DOWN | 72 | 10% | 697 | 6.31% | 2.58% | 6.31% | 0.00% | 91.10% | 45.00 | +0.486% | +0.486% |
| DOWN | 168 | 2% | 697 | 75.75% | 74.18% | 52.08% | 0.00% | 0.14% | 21.00 | +1.025% | +1.029% |
| DOWN | 168 | 5% | 697 | 48.35% | 39.74% | 45.62% | 0.00% | 20.23% | 58.00 | +1.294% | +1.294% |
| DOWN | 168 | 10% | 697 | 19.08% | 14.63% | 19.08% | 0.00% | 66.28% | 103.00 | +1.161% | +1.161% |
| DOWN | 336 | 2% | 697 | 80.77% | 82.64% | 52.08% | 0.00% | 0.00% | 24.00 | +1.179% | +1.211% |
| DOWN | 336 | 5% | 697 | 58.39% | 58.97% | 50.93% | 0.00% | 5.02% | 76.00 | +1.568% | +1.568% |
| DOWN | 336 | 10% | 697 | 29.41% | 25.11% | 29.27% | 0.00% | 45.62% | 140.00 | +1.521% | +1.521% |

Tocar+10% en algún momento no equivale a cerrar+10%, hacerlo antes de−10%, hacerlo antes de un stop pequeño ni capturarlo en una operación. Adverso anterior al target se da como intervalo: solo barras anteriores son seguras; la hora del toque puede incluir una excursión de orden desconocido. El tracker runtime usa únicamente barras ya observadas. **NOT A GUARANTEE.**

### Fuerza al inicio del episodio: extensión y retorno72h

| Strength | Lado | n | acierto | media | 10% observado | adverso10% | MFE mediana | MAE mediana |
|---|---|---|---|---|---|---|---|---|
| WEAK | UP | 516 | 49.22% | +0.537% | 2.52% | 3.10% | +2.466% | -2.142% |
| WEAK | DOWN | 509 | 45.38% | -0.052% | 5.30% | 2.95% | +2.951% | -2.607% |
| BUILDING | UP | 137 | 56.93% | +0.827% | 0.73% | 1.46% | +2.819% | -1.801% |
| BUILDING | DOWN | 130 | 43.08% | +0.263% | 11.54% | 1.54% | +3.269% | -2.722% |
| STRONG | UP | 49 | 51.02% | +0.502% | 2.04% | 0.00% | +3.167% | -2.194% |
| STRONG | DOWN | 58 | 43.10% | -0.025% | 3.45% | 1.72% | +3.703% | -3.205% |

## Persistencia y false reversal

False reversal evaluativo: nuevo episodio direccional precedido por sentido opuesto y posterior vuelta al anterior dentro de3velasTF(1H3h/4H12h/1D72h; MTF24h). Etiqueta futura separada, nunca entrada del motor. Borde derecho censurado; no es tasa de trades perdedores ni prueba de giro estructural verdadero.

| Stream | Estado | episodios | persistencia mediana horas | n evaluable reversal | false reversal |
|---|---|---|---|---|---|
| 1H | UP | 765 | 7.00 | 765 | 2.61% |
| 1H | DOWN | 686 | 8.00 | 686 | 4.37% |
| 4H | UP | 186 | 28.00 | 186 | 0.54% |
| 4H | DOWN | 182 | 28.00 | 182 | 2.75% |
| 1D | UP | 30 | 192.00 | 30 | 3.33% |
| 1D | DOWN | 29 | 216.00 | 29 | 10.34% |
| MTF | UP | 702 | 4.00 | 702 | 0.00% |
| MTF | DOWN | 697 | 3.00 | 697 | 0.00% |

### Pullback vs transición: diagnóstico temporal suplementario

Los cohorts primarios conservan el detalle al INICIO del episodio. Para no confundir eso con todos los pullbacks, [timing_diagnostics.json](artifacts/timing_diagnostics.json) mide además entradas en etiquetas de timing ya congeladas dentro de episodios. Son observaciones anidadas/solapadas, no nuevos episodios UP/DOWN, y no cambian reglas, selección o clasificación. Análisis descriptivo suplementario posterior a la evaluación primaria; no se usa para elegir una regla rentable.

| Etiqueta | h | n | acierto según lean | media firmada | mediana | MFE mediana | MAE mediana |
|---|---|---|---|---|---|---|---|
| UP_WITH_1H_PULLBACK | 4 | 368 | 48.37% | -0.046% | -0.008% | +0.410% | -0.452% |
| UP_WITH_1H_PULLBACK | 12 | 368 | 53.53% | +0.048% | +0.055% | +0.744% | -0.873% |
| UP_WITH_1H_PULLBACK | 24 | 368 | 51.63% | +0.226% | +0.036% | +1.203% | -1.229% |
| UP_WITH_1H_PULLBACK | 72 | 368 | 49.73% | +0.534% | -0.013% | +2.347% | -2.142% |
| DOWN_WITH_1H_PULLBACK | 4 | 274 | 49.64% | -0.083% | -0.009% | +0.461% | -0.550% |
| DOWN_WITH_1H_PULLBACK | 12 | 274 | 45.62% | -0.203% | -0.170% | +0.802% | -1.013% |
| DOWN_WITH_1H_PULLBACK | 24 | 274 | 48.18% | -0.238% | -0.098% | +1.214% | -1.483% |
| DOWN_WITH_1H_PULLBACK | 72 | 274 | 43.80% | -0.161% | -0.453% | +2.702% | -2.956% |
| POSSIBLE_BULLISH_TRANSITION | 4 | 212 | 50.47% | +0.076% | +0.007% | +0.509% | -0.470% |
| POSSIBLE_BULLISH_TRANSITION | 12 | 212 | 48.11% | -0.043% | -0.057% | +0.915% | -0.827% |
| POSSIBLE_BULLISH_TRANSITION | 24 | 212 | 51.89% | +0.020% | +0.138% | +1.437% | -1.117% |
| POSSIBLE_BULLISH_TRANSITION | 72 | 212 | 46.70% | +0.002% | -0.159% | +2.633% | -2.321% |
| POSSIBLE_BEARISH_TRANSITION | 4 | 174 | 40.80% | -0.116% | -0.161% | +0.434% | -0.548% |
| POSSIBLE_BEARISH_TRANSITION | 12 | 174 | 42.53% | -0.094% | -0.144% | +0.971% | -0.944% |
| POSSIBLE_BEARISH_TRANSITION | 24 | 172 | 42.44% | -0.156% | -0.274% | +1.201% | -1.296% |
| POSSIBLE_BEARISH_TRANSITION | 72 | 172 | 46.51% | -0.625% | -0.309% | +2.382% | -2.491% |

| Etiqueta | n maduros72h | impulso1H alineado en72h | horas mediana | macro cambia lado en72h |
|---|---|---|---|---|
| UP_WITH_1H_PULLBACK | 368 | 98.10% | 12.00 | 1.09% |
| DOWN_WITH_1H_PULLBACK | 274 | 95.62% | 10.00 | 1.09% |
| POSSIBLE_BULLISH_TRANSITION | 212 | 99.53% | 1.00 | 13.68% |
| POSSIBLE_BEARISH_TRANSITION | 172 | 100.00% | 1.00 | 6.98% |

El engine distingue semánticamente pullback de transición, pero estas etiquetas no garantizan continuación ni giro posterior. No ajustar sus definiciones para mejorar estas distribuciones.

## Ablation informacional, sin estrategia ganadora

AO_ONLY yAO_DI recomputan jerarquía; ADX/BBWP/K son subgrupos condicionados de los mismos onsetsAO_DI, con los mismos controles originales. No son backtests ni se elige la fila de mayor retorno. ADX yBBWP no tienen autoridad para dar sentido contrario. El contextoK bajista es proxy, no EXIT=SHORT. La cadena+MLconfirmed está PENDING. La filaSTRUCTURE_NO_ML no pretende sustituir esa confirmación.

| Split | Stage | Lado | n72h | acierto | media | exceso control |
|---|---|---|---|---|---|---|
| TRAIN | AO_DI | UP | 84 | 63.10% | +1.619% | -0.385% |
| TRAIN | AO_DI | DOWN | 49 | 44.90% | -0.646% | -0.437% |
| TRAIN | AO_DI_ADX | UP | 28 | 71.43% | +2.796% | +0.307% |
| TRAIN | AO_DI_ADX | DOWN | 29 | 37.93% | -0.426% | -0.835% |
| TRAIN | AO_DI_ADX_BBWP | UP | 23 | 65.22% | +1.895% | -0.756% |
| TRAIN | AO_DI_ADX_BBWP | DOWN | 20 | 30.00% | -1.228% | -0.871% |
| TRAIN | AO_DI_ADX_BBWP_KONKORDE | UP | 23 | 65.22% | +1.895% | -0.756% |
| TRAIN | AO_DI_ADX_BBWP_KONKORDE | DOWN | 20 | 30.00% | -1.228% | -0.871% |
| TRAIN | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | UP | 20 | 60.00% | +1.517% | -1.305% |
| TRAIN | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | DOWN | 20 | 30.00% | -1.228% | -0.871% |
| VALIDATION | AO_DI | UP | 61 | 55.74% | +0.361% | +0.044% |
| VALIDATION | AO_DI | DOWN | 79 | 50.63% | +0.506% | +0.525% |
| VALIDATION | AO_DI_ADX | UP | 24 | 62.50% | -0.016% | +0.309% |
| VALIDATION | AO_DI_ADX | DOWN | 38 | 44.74% | +0.697% | -0.413% |
| VALIDATION | AO_DI_ADX_BBWP | UP | 17 | 64.71% | +0.607% | +0.387% |
| VALIDATION | AO_DI_ADX_BBWP | DOWN | 28 | 46.43% | +0.874% | -0.036% |
| VALIDATION | AO_DI_ADX_BBWP_KONKORDE | UP | 17 | 64.71% | +0.607% | +0.387% |
| VALIDATION | AO_DI_ADX_BBWP_KONKORDE | DOWN | 24 | 37.50% | +0.468% | -0.179% |
| VALIDATION | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | UP | 15 | 66.67% | +0.427% | +0.650% |
| VALIDATION | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | DOWN | 20 | 25.00% | -0.798% | -1.188% |
| TEST | AO_DI | UP | 106 | 50.00% | +0.651% | -0.061% |
| TEST | AO_DI | DOWN | 89 | 43.82% | -0.497% | -0.893% |
| TEST | AO_DI_ADX | UP | 42 | 54.76% | +1.011% | +0.458% |
| TEST | AO_DI_ADX | DOWN | 41 | 43.90% | -0.801% | -0.946% |
| TEST | AO_DI_ADX_BBWP | UP | 23 | 52.17% | +0.537% | -0.307% |
| TEST | AO_DI_ADX_BBWP | DOWN | 27 | 40.74% | -0.435% | -0.866% |
| TEST | AO_DI_ADX_BBWP_KONKORDE | UP | 21 | 57.14% | +1.172% | +0.082% |
| TEST | AO_DI_ADX_BBWP_KONKORDE | DOWN | 25 | 40.00% | -0.702% | -1.155% |
| TEST | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | UP | 19 | 57.89% | +1.039% | -0.182% |
| TEST | AO_DI_ADX_BBWP_K_STRUCTURE_NO_ML | DOWN | 24 | 41.67% | -0.400% | -0.907% |

| Jerarquía TEST | Lado | n72h | acierto | media | exceso |
|---|---|---|---|---|---|
| AO_ONLY | UP | 88 | 52.27% | +0.467% | +0.076% |
| AO_ONLY | DOWN | 71 | 46.48% | -0.283% | -0.983% |
| AO_DI | UP | 106 | 50.00% | +0.651% | -0.061% |
| AO_DI | DOWN | 89 | 43.82% | -0.497% | -0.893% |
| MTF | UP | 702 | 50.85% | +0.591% | -0.122% |
| MTF | DOWN | 697 | 44.76% | +0.009% | +0.086% |
| V8 | UP | 82 | 53.66% | +0.655% | +1.685% |
| V8 | DOWN | 0 | NA | NA | NA |

Masks/no-ops idénticos no son replicaciones independientes. El contraste jerarquía vs subgrupo no estima por sí solo un efecto causal. V8FLAT no se convierte enDOWN.

## Year-by-year /2026 y walk-forward fijo

| Año | Estado | n72h | acierto | media | mediana | exceso |
|---|---|---|---|---|---|---|
| 2020 | UP | 317 | 62.46% | +2.163% | +1.238% | -0.250% |
| 2020 | DOWN | 148 | 35.81% | +0.174% | -0.959% | +0.031% |
| 2021 | UP | 224 | 62.05% | +1.908% | +2.623% | +0.602% |
| 2021 | DOWN | 263 | 44.49% | -1.005% | -0.743% | -1.052% |
| 2022 | UP | 130 | 40.77% | -1.692% | -1.967% | -1.128% |
| 2022 | DOWN | 415 | 45.54% | +0.271% | -0.254% | -0.220% |
| 2023 | UP | 312 | 51.60% | +0.883% | +0.093% | -0.286% |
| 2023 | DOWN | 199 | 45.23% | -1.142% | -0.177% | +0.033% |
| 2024 | UP | 299 | 54.85% | +0.857% | +0.694% | -0.165% |
| 2024 | DOWN | 197 | 59.39% | +0.314% | +0.957% | +0.927% |
| 2025 | UP | 195 | 50.26% | +0.605% | +0.022% | +0.222% |
| 2025 | DOWN | 318 | 38.05% | -0.199% | -0.693% | -0.204% |
| 2026 | UP | 208 | 45.67% | +0.197% | -0.302% | -0.381% |
| 2026 | DOWN | 171 | 42.69% | +0.228% | -0.414% | -0.293% |

2026 sigue separado y sin retuning. Mediana negativa aunque la media sea positiva puede mostrar asimetría/concentración, no una dirección fiable en la mayoría de ocasiones.

| Fold | Estado | n72h | acierto | media | exceso | IC95 exceso |
|---|---|---|---|---|---|---|
| 2022 | UP | 130 | 40.77% | -1.692% | -1.128% | -4.128% / +1.227% |
| 2022 | DOWN | 415 | 45.54% | +0.271% | -0.220% | -1.502% / +1.035% |
| 2023 | UP | 312 | 51.60% | +0.883% | -0.266% | -1.334% / +0.913% |
| 2023 | DOWN | 199 | 45.23% | -1.142% | -0.072% | -1.518% / +1.037% |
| 2024 | UP | 299 | 54.85% | +0.857% | +0.112% | -1.171% / +1.211% |
| 2024 | DOWN | 197 | 59.39% | +0.314% | +1.048% | -0.854% / +2.418% |
| 2025 | UP | 195 | 50.26% | +0.605% | -0.117% | -1.430% / +0.971% |
| 2025 | DOWN | 318 | 38.05% | -0.199% | -0.165% | -1.043% / +0.796% |
| 2026 | UP | 208 | 45.67% | +0.197% | -0.221% | -1.679% / +0.975% |
| 2026 | DOWN | 171 | 42.69% | +0.228% | -0.299% | -1.697% / +1.434% |

## Soportes/resistencias

Se reutiliza read-only `guardian_signals.confirmed_structure` y se verifica equivalencia de la búsqueda bounded220 con `confirmed_level_scale`. Pivots se publican después de2velasderechas. Día/semana anteriores son periodosUTC completos; semana lunes. % usa precio cerrado conocido; ATR se expresa enATR1H.
Las escalas conservan referenciaTF y timestamps de pivot/confirmación. R cruzada solo por1H durante4H/1D abierta no se relabela soporte. Falta deR/S no prueba espacio abierto. AT_SUPPORT/AT_RESISTANCE requieren toque real de rango cerrado a nivel ya conocido, no proximidad ajustada conTEST.

| Estado | n conS | n conR | distS mediana | distR mediana | S ATRmediana | R ATRmediana |
|---|---|---|---|---|---|---|
| UP | 702 | 681 | -0.336% | +0.159% | 0.59 | 0.28 |
| DOWN | 683 | 697 | -0.199% | +0.311% | 0.30 | 0.43 |
| TRANSITION | 1274 | 1273 | -0.165% | +0.152% | 0.28 | 0.25 |
| UNCLEAR | 866 | 867 | -0.151% | +0.140% | 0.25 | 0.25 |
| CONFLICT | 1690 | 1690 | -0.165% | +0.138% | 0.27 | 0.24 |

Detalle por episodio en JSON; no umbral de distancia seleccionado ni permisos de entrada.

## Ruido / eficiencia / arquitectura

[LEGACY_NOISE_AUDIT.md](LEGACY_NOISE_AUDIT.md) distingue overlap de estado(99,92%UPconV8LONG) de overlap de onsets(8pares, mediana engine12hposterior aV8, muestra pequeña). Guardian KEEP_VISIBLE/KEEP_ACTIVE; V8 KEEP_VISIBLE; engine KEEP_INTERNAL research. No se silencian sistemas útiles por estética. ML/otros: duplicación real ylead/lagforwardPENDING. No cambios de alertas, servicios, variables ni producción.

## Gates / clasificación

| Lado | Gates no superados |
|---|---|
| UP | paired_excess_positive, ci_lower_positive, without_top3_positive, actual_confirmed_ml_evaluation |
| DOWN | ci_lower_positive, without_top3_positive, actual_confirmed_ml_evaluation |

USEFUL exigía ambos lados con>=50episodiosTEST, media/exceso positivos eICsemanal inferior>0 a72h, estabilidad entre años/folds, sin dependencia mejores3 y evaluación realMLconfirmado disponible. No se cumplen. USEFUL tampoco significaría estrategia rentable, señal live ni autorización.

## Telegram: muestras sintéticas, no enviadas

Renderer puro sin token, sender ni poller. Prototipo file-fed retorna strings y conserva estado/dedupe separado; bootstrap/restart/catch-up silenciosos. No está integrado ni arrancado en producción.
### UP — ILLUSTRATIVE

```text
🟢 BTC DIRECTION: UP
💪 STRENGTH: BUILDING
🏷️ GRADE: B · coherencia visual, no probabilidad
₿ BTCUSDT · contexto1D / confirmación4H / timing1H
Referencia cerrada: 82,000.000
Fuente: BINANCE PUBLIC / SYNTHETIC FIXTURE
Cierre conocido: 2026-10-15 00:00 UTC
Lectura: UP_CONFIRMED
🧱 R confirmada: 86,000.000 · 4.88%
🧱 S confirmado: 80,000.000 · -2.44%

📅 1D · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · FALLING · TURN_UP False
ADX delta: -0.100 · aceleración: 0.200
ML RSI CONFIRMED: UNKNOWN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕓 4H · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: GREEN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 1H · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: GREEN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 TIMING: impulse_up
🧱 STRUCTURE
Soporte: 80,000.000
Resistencia: 86,000.000
Room upward: 4.88% · 2.000 ATR1H
Room downward: 2.44% · 1.000 ATR1H
Contexto: BETWEEN_LEVELS

📈 LARGE MOVE TRACKER
DIRECTIONAL_10PCT_EXTENSION
Status: PENDING_OBSERVATION
NOT A GUARANTEE · no es take profit
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
GradeA/B/C no es evidencia estadística ni sizing.
ML RSI1D: no existe en el observer actual. No se ha fabricado.
👻 DIRECTIONAL RESEARCH ONLY
🚫 NOT A TRADE SIGNAL
🚫 TRADE AUTHORITY: NONE
```

### DOWN — ILLUSTRATIVE

```text
🔴 BTC DIRECTION: DOWN
💪 STRENGTH: BUILDING
🏷️ GRADE: B · coherencia visual, no probabilidad
₿ BTCUSDT · contexto1D / confirmación4H / timing1H
Referencia cerrada: 82,000.000
Fuente: BINANCE PUBLIC / SYNTHETIC FIXTURE
Cierre conocido: 2026-10-15 00:00 UTC
Lectura: DOWN_CONFIRMED
🧱 R confirmada: 86,000.000 · 4.88%
🧱 S confirmado: 80,000.000 · -2.44%

📅 1D · 2026-10-15 00:00 UTC
Direction: DOWN
AO: -150.000 · BEARISH_MOMENTUM
Pendiente: -25.000 · aceleración: -5.000
Zero cross UP/DOWN: False/True · AWAY_FROM_ZERO
DI: BEARISH · +DI 15.000 / -DI 28.000
ADX: 24.000 · FALLING · TURN_UP False
ADX delta: -0.100 · aceleración: 0.200
ML RSI CONFIRMED: UNKNOWN (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕓 4H · 2026-10-15 00:00 UTC
Direction: DOWN
AO: -150.000 · BEARISH_MOMENTUM
Pendiente: -25.000 · aceleración: -5.000
Zero cross UP/DOWN: False/True · AWAY_FROM_ZERO
DI: BEARISH · +DI 15.000 / -DI 28.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: RED (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 1H · 2026-10-15 00:00 UTC
Direction: DOWN
AO: -150.000 · BEARISH_MOMENTUM
Pendiente: -25.000 · aceleración: -5.000
Zero cross UP/DOWN: False/True · AWAY_FROM_ZERO
DI: BEARISH · +DI 15.000 / -DI 28.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: RED (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 TIMING: impulse_down
🧱 STRUCTURE
Soporte: 80,000.000
Resistencia: 86,000.000
Room upward: 4.88% · 2.000 ATR1H
Room downward: 2.44% · 1.000 ATR1H
Contexto: BETWEEN_LEVELS

📈 LARGE MOVE TRACKER
DIRECTIONAL_10PCT_EXTENSION
Status: PENDING_OBSERVATION
NOT A GUARANTEE · no es take profit
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
GradeA/B/C no es evidencia estadística ni sizing.
ML RSI1D: no existe en el observer actual. No se ha fabricado.
👻 DIRECTIONAL RESEARCH ONLY
🚫 NOT A TRADE SIGNAL
🚫 TRADE AUTHORITY: NONE
```

### TRANSITION — ILLUSTRATIVE

```text
🟡 BTC DIRECTION: TRANSITION
💪 STRENGTH: BUILDING
🏷️ GRADE: C · coherencia visual, no probabilidad
₿ BTCUSDT · contexto1D / confirmación4H / timing1H
Referencia cerrada: 82,000.000
Fuente: BINANCE PUBLIC / SYNTHETIC FIXTURE
Cierre conocido: 2026-10-15 00:00 UTC
Lectura: POSSIBLE_BULLISH_TRANSITION
🧱 R confirmada: 86,000.000 · 4.88%
🧱 S confirmado: 80,000.000 · -2.44%

📅 1D · 2026-10-15 00:00 UTC
Direction: DOWN
AO: -150.000 · BEARISH_MOMENTUM
Pendiente: -25.000 · aceleración: -5.000
Zero cross UP/DOWN: False/True · AWAY_FROM_ZERO
DI: BEARISH · +DI 15.000 / -DI 28.000
ADX: 24.000 · FALLING · TURN_UP False
ADX delta: -0.100 · aceleración: 0.200
ML RSI CONFIRMED: UNKNOWN (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕓 4H · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: GREEN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 1H · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: GREEN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 TIMING: impulse_up
🧱 STRUCTURE
Soporte: 80,000.000
Resistencia: 86,000.000
Room upward: 4.88% · 2.000 ATR1H
Room downward: 2.44% · 1.000 ATR1H
Contexto: BETWEEN_LEVELS

📈 LARGE MOVE TRACKER
DIRECTIONAL_10PCT_EXTENSION
Status: PENDING_OBSERVATION
NOT A GUARANTEE · no es take profit
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
GradeA/B/C no es evidencia estadística ni sizing.
ML RSI1D: no existe en el observer actual. No se ha fabricado.
👻 DIRECTIONAL RESEARCH ONLY
🚫 NOT A TRADE SIGNAL
🚫 TRADE AUTHORITY: NONE
```

### UNCLEAR — ILLUSTRATIVE

```text
⚪ BTC DIRECTION: UNCLEAR
💪 STRENGTH: WEAK
🏷️ GRADE: C · coherencia visual, no probabilidad
₿ BTCUSDT · contexto1D / confirmación4H / timing1H
Referencia cerrada: 82,000.000
Fuente: BINANCE PUBLIC / SYNTHETIC FIXTURE
Cierre conocido: 2026-10-15 00:00 UTC
Lectura: NO_CONFIRMED_HIERARCHY
🧱 R confirmada: 86,000.000 · 4.88%
🧱 S confirmado: 80,000.000 · -2.44%

📅 1D · 2026-10-15 00:00 UTC
Direction: NEUTRAL
AO: 0.000 · MIXED
Pendiente: 0.000 · aceleración: 0.000
Zero cross UP/DOWN: False/False · STABLE
DI: NEUTRAL · +DI 20.000 / -DI 20.000
ADX: 24.000 · FALLING · TURN_UP False
ADX delta: -0.100 · aceleración: 0.200
ML RSI CONFIRMED: UNKNOWN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕓 4H · 2026-10-15 00:00 UTC
Direction: NEUTRAL
AO: 0.000 · MIXED
Pendiente: 0.000 · aceleración: 0.000
Zero cross UP/DOWN: False/False · STABLE
DI: NEUTRAL · +DI 20.000 / -DI 20.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: RED (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 1H · 2026-10-15 00:00 UTC
Direction: NEUTRAL
AO: 0.000 · MIXED
Pendiente: 0.000 · aceleración: 0.000
Zero cross UP/DOWN: False/False · STABLE
DI: NEUTRAL · +DI 20.000 / -DI 20.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: RED (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 TIMING: no_impulse
🧱 STRUCTURE
Soporte: 80,000.000
Resistencia: 86,000.000
Room upward: 4.88% · 2.000 ATR1H
Room downward: 2.44% · 1.000 ATR1H
Contexto: BETWEEN_LEVELS

📈 LARGE MOVE TRACKER
DIRECTIONAL_10PCT_EXTENSION
Status: PENDING_OBSERVATION
NOT A GUARANTEE · no es take profit
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
GradeA/B/C no es evidencia estadística ni sizing.
ML RSI1D: no existe en el observer actual. No se ha fabricado.
👻 DIRECTIONAL RESEARCH ONLY
🚫 NOT A TRADE SIGNAL
🚫 TRADE AUTHORITY: NONE
```

### CONFLICT — ILLUSTRATIVE

```text
🛑 BTC DIRECTION: CONFLICT
💪 STRENGTH: WEAK
🏷️ GRADE: C · coherencia visual, no probabilidad
₿ BTCUSDT · contexto1D / confirmación4H / timing1H
Referencia cerrada: 82,000.000
Fuente: BINANCE PUBLIC / SYNTHETIC FIXTURE
Cierre conocido: 2026-10-15 00:00 UTC
Lectura: MACRO_SWING_CONFLICT
🧱 R confirmada: 86,000.000 · 4.88%
🧱 S confirmado: 80,000.000 · -2.44%

📅 1D · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · FALLING · TURN_UP False
ADX delta: -0.100 · aceleración: 0.200
ML RSI CONFIRMED: UNKNOWN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕓 4H · 2026-10-15 00:00 UTC
Direction: DOWN
AO: -150.000 · BEARISH_MOMENTUM
Pendiente: -25.000 · aceleración: -5.000
Zero cross UP/DOWN: False/True · AWAY_FROM_ZERO
DI: BEARISH · +DI 15.000 / -DI 28.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: RED (solo cache; no provisional)
Konkorde: KONKORDE_BEARISH_CONTEXT
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 1H · 2026-10-15 00:00 UTC
Direction: UP
AO: 150.000 · BULLISH_MOMENTUM
Pendiente: 25.000 · aceleración: 5.000
Zero cross UP/DOWN: True/False · AWAY_FROM_ZERO
DI: BULLISH · +DI 28.000 / -DI 15.000
ADX: 24.000 · RISING · TURN_UP True
ADX delta: 0.800 · aceleración: 0.200
ML RSI CONFIRMED: GREEN (solo cache; no provisional)
Konkorde: KONKORDE_BULLISH_INSIDE
Separación: 4.000 · delta 1.000
Distancia cero: 40.000
BBWP: 56.000% · RISING · distancia50 6.000

🕐 TIMING: impulse_up
🧱 STRUCTURE
Soporte: 80,000.000
Resistencia: 86,000.000
Room upward: 4.88% · 2.000 ATR1H
Room downward: 2.44% · 1.000 ATR1H
Contexto: BETWEEN_LEVELS

📈 LARGE MOVE TRACKER
DIRECTIONAL_10PCT_EXTENSION
Status: PENDING_OBSERVATION
NOT A GUARANTEE · no es take profit
EXACT BITMAN KONKORDE PARITY: NOT PROVEN
GradeA/B/C no es evidencia estadística ni sizing.
ML RSI1D: no existe en el observer actual. No se ha fabricado.
👻 DIRECTIONAL RESEARCH ONLY
🚫 NOT A TRADE SIGNAL
🚫 TRADE AUTHORITY: NONE
```

## Validación / límites

Resultados congelados y replay reproducible, sin datasets grandes enGit. Ver [validation.json](artifacts/validation.json), [safety_audit.json](artifacts/safety_audit.json) y[README](README.md). No dependencias de ejecutores ni privateAPI, no MLmath nuevo, no mensajes reales. Forward real sigue PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR. La integración completa con confirmaciones reales debe evaluarse con sus timestamps de disponibilidad, sin backdating ni sustituir datos ausentes.

**V8 UNCHANGED. GUARDIAN UNCHANGED. ML RSI MATH UNCHANGED. MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.**

**NO MERGE. NO DEPLOY. NO REAL ORDERS. TRADE AUTHORITY: NONE.**

INCONCLUSIVE DIRECTION ENGINE
