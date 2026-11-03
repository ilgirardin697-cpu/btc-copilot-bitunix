# Killzone H1 V3.7 Lite: traducción de fuente y dos perfiles

SHADOW ONLY. TRADE AUTHORITY: NONE. Sin backtest de rentabilidad, ejecución,
Telegram, Railway ni cambios en Guardian/V8. Base independiente:
`9d40020d539033cefb8f01734db8c6a6fdbba2e3`.

**Resultado: las fórmulas del archivo adjunto ya son implementables. La paridad
numérica independiente con TradingView y con el indicador de Alpha sigue
PENDIENTE. PAPER operativo: NO-GO hasta completar esa comprobación.**

## Fuente auditada

Se leyó el archivo completo: 317 líneas, 26550 bytes. Se conserva byte a byte en
[source/Killzone_H1_v3_7_Lite.txt](source/Killzone_H1_v3_7_Lite.txt).
SHA256: `058532c5c7964eefa3993b8aae761aef7598a542c7e43c7469ad0531f39e03a7`.
Sus comentarios lo llaman **adaptación educativa**, no código autenticado del
indicador privado. No hay licencia pública/autorización de autoría verificadas.
No se supone que este texto explique por sí solo los píxeles de otros gráficos.

[source_audit.json](artifacts/source_audit.json) enumera TODOS los inputs y las
líneas de fórmulas. Nombres Pine conservados en Python para revisión.

La revisión visual previa (`be475d5`) verificó un segmento vertical y una copia
superior de igual altura en las DOS capturas nuevas. El Pine es cualitativamente
compatible con proyectar esa amplitud desde un anclaje interior; eso NO prueba
que use los mismos extremos ni el mismo inset. En aquellas fotos el centro de
apoyo aparecía 10px dentro de la caja: no se convierte ese margen de pantalla
en el 3% por defecto de este archivo. Tampoco había una copia inferior observada
con sus dos círculos. Faltan el setup, escala/ticker/configuración y precios
completos para comparar numéricamente ambas evidencias. No se reetiqueta la
auditoría anterior como paridad de V3.7, ni se ajusta el inset a sus píxeles.

## Fórmulas reproducidas

`aHigh/aLow` son máximo/mínimo de las velas de Asia; `lHigh/lLow`, los de Londres.
Los acumuladores se actualizan cronológicamente y se reinician según las mismas
transiciones de sesión del Pine. Londres pertenece a la Asia anterior que haya
completado el número esperado de velas. No se agregan velas abiertas.

Con AH/AL/LH/LL ya conocidos al completar las sesiones:

```
amplitude = max(AH,LH) - min(AL,LL)
topInAsia = AH <= LH
bottomInAsia = AL >= LL
topBoxHeight = (AH-AL) si topInAsia, en otro caso (LH-LL)
bottomBoxHeight = (AH-AL) si bottomInAsia, en otro caso (LH-LL)
topAnchor = min(AH,LH) - topBoxHeight * 3/100
bottomAnchor = max(AL,LL) + bottomBoxHeight * 3/100
SUPERIOR = topAnchor + amplitude
INFERIOR = bottomAnchor - amplitude
HIGH = max(AH,LH)
LOW = min(AL,LL)
```

El 3% se aplica a la ALTURA de la caja seleccionada, no al precio BTC. Las
igualdades de extremos seleccionan Asia (`<=`/`>=`). Solapamiento, contención
y cajas de altura cero NO se rechazan por geometría: el Pine las calcula.
Si una contiene a la otra, ambos anclajes pueden pertenecer a la interior.

No hay dos diagonales HH/LL ni prolongación infinita de un segmento. El texto
define dos proyecciones verticales de igual amplitud, cada una desde su anclaje.
La posición horizontal de cada medición es el centro temporal de la caja
seleccionada; los bordes de dibujo se desplazan media vela. Esto no cambia las
velas que participan en cada sesión.

## Perfiles que NO se mezclan

| Propiedad | PINE_A: original | OWNER_B: reglas del propietario |
|---|---|---|
| Zona de ambas sesiones | America/New_York, DST | UTC−4 fijo |
| Asia, aperturas locales | 20,21,22,23 | 20,21,22,23,00 |
| Londres, aperturas locales | 02,03,04,05 | 01,02,03,04 |
| Fin Londres | 06:00 local | 05:00 UTC−4 |
| Confirmación HIGH | close > HIGH | min(open,close) > HIGH |
| Confirmación LOW | close < LOW | max(open,close) < LOW |
| Frecuencia por par | una por cada lado | primera confirmación únicamente |
| Seguimiento de franja | lado de primera ruptura | lado de primera confirmación |
| Proyección / inset | fórmula fuente / 3% y 3% | idéntica fórmula / 3% y 3% |
| Entrada, stop, sizing, R/R | NO definidos por indicador | reglas PAPER abajo |

En A, `highConfirmed` y `lowConfirmed` son alertas independientes y pueden
aparecer ambas en el mismo ciclo, una cada una. `longBreak/shortBreak` y la
dirección de seguimiento se fijan SOLO con la primera. No suprimir la segunda
alerta al afirmar reproducción del Pine. En B se aplica la convención de una
sola confirmación del propietario, aunque esa oportunidad sea rechazada por riesgo.

Todos los defaults restantes, incluidos colores/transparencias, historial de 7
ciclos y longitud gráfica de 24 barras, quedan en la fuente y el inventario de
inputs. Python reproduce la matemática y las señales, no la API de objetos de
TradingView. Los SVG son gráficos de diagnóstico propios, no un clon de su UI.

## Disponibilidad temporal y detalles de estado

`measureNow` ocurre en la **primera barra fuera de Londres**, no en la última
barra londinense. Las velas del rango ya están cerradas en su apertura. Las
señales esperan `barstate.isconfirmed`: pueden confirmarse al cierre de esa
misma primera barra ajena. El replay solo compromete barras cerradas, registra
por separado `levels_available_at` y `available_at` de la confirmación, sin
anticipar la segunda al inicio de la hora.

Matiz literal: fuera de `measureNow`, `amplitude=na` y `newTopTarget=topAnchor`
por `nz(amplitude,0)`; no son el objetivo congelado. El seguimiento usa
`targetTop/targetBottom`, fijados al completar el par. La traducción y el
comparador mantienen esta distinción.

Los 24 periodos de línea dibujada NO son caducidad del trigger. La elegibilidad
se reinicia en el siguiente `startAsia`. `latest/withinHistory` dependen del
último dato del gráfico para VISIBILIDAD, no para confirmar. No se usa
`last_bar_time` para tomar decisiones retrospectivas.

IANA New York cambia el horario de las sesiones respecto a UTC; la zona visual
del gráfico no cambia el input `asiaTZ/londonTZ`. En el salto de primavera, la
sesión original 02–06 contiene solo 3 barras reales H1: el chequeo `lCount==4`
impide medir. Se reproduce, sin inventar una cuarta vela. En UTC−4 fijo no ocurre.
Véase [sesiones oficiales](https://www.tradingview.com/pine-script-docs/concepts/sessions/)
y [tiempo y zonas](https://www.tradingview.com/pine-script-docs/concepts/time/).

El Python referencia conserva el comportamiento literal ante gaps; una bandera
separada de integridad impide aceptar PAPER con huecos aunque los contadores de
sesión del Pine llegasen a coincidir. No se altera la fórmula para esconderlo.
Para ejecución realtime del indicador, las variables/dibujos intrabar pueden
recalcularse; los cierres confirmados son el punto de comparación. Véase
[modelo de ejecución](https://www.tradingview.com/pine-script-docs/language/execution-model/).

## TP adelantado 200: SOLO investigación PAPER B

Actualización solicitada expresamente por el propietario:

```
TP_LONG  = SUPERIOR - 200
TP_SHORT = INFERIOR + 200
SL_LONG  = HIGH - 0.20 * ATR14_H1
SL_SHORT = LOW  + 0.20 * ATR14_H1
```

200 son **unidades de PRECIO BTCUSDT**, nunca beneficio de cuenta. Se guardan
por separado `theoretical_target` y `advanced_tp`. Entrada de referencia =
cierre confirmador; no se promete ejecutar a ese precio ya conocido al cerrar.
ATR14 = TR con Wilder RMA14, seed SMA14, solo datos cerrados; no existe ATR en
el Pine original ni se le atribuye esta regla de riesgo.

Se rechaza un TP adelantado detrás/igual a la entrada o un orden SL/entrada/TP
incoherente. Con dirección d=+1 LONG/−1 SHORT y tasas explícitas:

```
e = cierre * (1 + d*slippage_entrada)
s = SL * (1 - d*slippage_salida)
t = TP_adelantado * (1 - d*slippage_salida)
riesgo/BTC = d*(e-s) + fee_entrada*e + fee_salida*s + reserva_funding
recompensa/BTC = d*(t-e) - fee_entrada*e - fee_salida*t - reserva_funding
R/R neto = recompensa / riesgo
```

Se exige R/R neto >=1.5 con el TP ADELANTADO; costes/funding requieren un
escenario identificado, sin default de coste cero. Tamaño <=0.25% del capital
simulado / riesgo neto por BTC y nominal <=capital. No hay apalancamiento,
modelo de préstamo ni promesa de un máximo de pérdida durante un gap. El
campo `accepted` de `paper_plan` significa SOLO que pasa la aritmética del
filtro en un test offline: no activa PAPER, no envía ni autoriza nada.

## Franjas de 500: no son objetivos exactos ni TP de 200

La franja superior dibujada es `[SUPERIOR-500, SUPERIOR]`; la inferior,
`[INFERIOR, INFERIOR+500]`. Tras la primera ruptura, SOLO en barras posteriores,
el Pine alerta una vez si `high >= SUPERIOR-500` o `low <= INFERIOR+500`.
Estas desigualdades también se cumplen si el precio salta MÁS ALLÁ del target;
no exigen que cierre dentro de la franja ni un cruce desde fuera. Alcanzar
ese umbral NO demuestra tocar el target exacto. El replay separa `upperTouch/
lowerTouch` de `exactTopTouch/exactBottomTouch`, estos últimos diagnósticos propios.

## Pruebas y evidencia real disponible

Pruebas propias de fórmulas, empates, contención, solapamiento, cierres estrictos,
wick-only, doble lado A/primer lado B, reset, DST, datos parciales, causabilidad,
ATR, redondeo de etiquetas, TP200, costes, 1.5R y sizing sin apalancamiento.
Las pruebas sintéticas y el roundtrip del comparador NO son evidencia externa.

[Galería](artifacts/index.html) / [casos numéricos](artifacts/geometry_cases.json).
Se reutilizan 72 velas públicas USD-M de 2026-09-01 a 2026-09-04 exclusivamente
para mecánica. Checksum y linaje están en
[public_data_manifest.json](fixtures/public_data_manifest.json). Fuente:
Binance Vision USD-M mensual 5m, agregado previamente a H1 sin huecos. Es un
fixture ya visto, NO holdout ni captura Alpha, ni Spot. No se mide PnL con él.

**Registros numéricos reales TradingView recuperados en esta tarea: 0.** No hay
herramienta de navegador/sesión TradingView conectada ni exportación/logs
del indicador adjuntos. Por tanto no se ha ejecutado el Pine en TradingView
ni se declara que compile la copia diagnóstica. El ticker/exchange de las
capturas Alpha sigue desconocido; el setup HIGH=78285.00, LOW=77517.20,
SUPERIOR=78653.44, INFERIOR=77095.25 NO se usa para calibración o comparación.

## Cómo completar la paridad sin suscripción

Se genera una [COPIA diagnóstica](artifacts/Killzone_H1_v3_7_Lite_DIAGNOSTIC.pine)
cuyo prefijo contiene TODOS los bytes originales; el original permanece intacto.
Solo añade Pine Logs opt-in (default OFF) para barras H1 cerradas en una ventana
UTC acotada. No añade alertas. Puede usarse con cualquier ticker exacto que
se declare, sin asumir equivalencia de Spot/perpetuo. Registrar también versión
de fuente, exchange/ticker completo, chart normal OHLC H1, parámetros, fechas,
tick mínimo y zona visual. No usar Heikin Ashi u OHLC transformado.

1. Compilar la copia en TradingView y conservar errores si los hubiera.
2. Con perfil A exacto, activar solo el LOG de un intervalo corto que empiece
   antes de una Asia completa; incluir varias sesiones, ambos lados, contención
   y DST si están en el histórico disponible. Conservar todas las filas.
3. Guardar las líneas `KZ_PARITY_V37=` con OHLC y valores sin redondear.
4. Ejecutar `python -m research.alpha_arcanox_pine_v37.parity <logs.txt>
   --out <nuevo_resultado.json>`. No sobrescribe las fuentes y registra SHA256.
5. El comparador exige ticker/config homogéneos y una sesión fresca completa;
   compara cronológicamente decenas de campos, tolerancia absoluta 1e-7.
   Un mismatch se investiga, no se ajustan las fórmulas al resultado.

El formato `mintick` solo redondea etiquetas; los niveles sin redondear se
conservan para cálculo. La precisión del log y el tick del símbolo se auditan
aparte. [Documentación oficial](https://www.tradingview.com/pine-script-docs/faq/functions/).
No se ha añadido redondeo para forzar ninguna captura.

## Aislamiento y decisión

El laboratorio no importa runtime, clientes, sockets, requests, Telegram ni
subprocess; la suite protege 95 archivos de fuente/datos de runtime mediante
hash normalizado únicamente CRLF→LF para checkouts Git multiplataforma. No hay
modificaciones de esos archivos ni de protocolos/journals. La nueva investigación
no está importada por producción; ramas/resultados anteriores no se reescriben.

**GO para revisión de implementación y captura de paridad. NO-GO para PAPER
operativo hasta obtener registros independientes.** La ambigüedad matemática
de los cuatro niveles queda resuelta respecto a ESTE archivo, no respecto a la
autoría del indicador privado. Rentabilidad: NO EVALUADA. Si la paridad con
la fuente se verifica, ejecutar primero el [protocolo PAPER](PAPER_PROTOCOL.md),
sin mezclar perfiles ni modificar parámetros después de mirar resultados.
