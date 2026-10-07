# ML RSI PINE_PARITY: source exacto y contraste con TradingView

El usuario ha aportado el Pine **directamente de la pestaña Source Code** de
[Machine Learning RSI, BackQuant, DKa7Dmc5](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/)
y diez filas de la Vista de tabla. Es la autoridad primaria de esta enmienda.
Está conservado, con licencia MPL-2.0 y atribución, en
`tests/fixtures/backquant_user_source.pine`. Los defaults del source se preservan;
el preset del usuario LOW29/EMA4 se registra por separado. Los fallos HTTP del
intento anterior no invalidan este material suministrado directamente.

**Las diez filas coinciden en RSI y ambos thresholds a los dos decimales
mostrados por TradingView.** No equivale a certificar todos los históricos,
timeframes, ticks abiertos o decimales internos del motor. **Exact BackQuant
TradingView parity is NOT proven.** No se ha ejecutado el diagnóstico Pine en
TradingView durante esta tarea ni se ha desplegado el observer corregido.

## Diferencia encontrada: constructores, NA, igualdad y orden del break

El commit `7659f8dbb9616136e43cf24531076b42f7c9ef82` interpretaba el clustering
como k-means convencional de tres elementos. El source exacto no hace eso:

1. `var centroids = array.new_float(3)` comienza con tres slots NA.
2. El loop se ejecuta incluso en barras anteriores al gate del histórico.
   `new_centroids = array.new_float(3)` seguido de tres push produce seis
   slots. En la primera barra cambian los tamaños; el carry crece a seis NA.
3. En barras maduras, array.set escribe p25/p50/p75 únicamente en posiciones
   0/1/2. Los slots 3/4/5 siguen siendo NA.
4. `distances = array.new_float(3)` también antepone tres NA. El primer mínimo
   finito está en índice >=3. El source envía esos índices a cluster3.
   Se mantiene la selección del primer índice en empate.
5. El array nuevo contiene `[NA, NA, NA, NA, NA, media]`. En cada pareja
   comparada con el carry hay al menos un NA. En Pine v5, NA != valor no
   produce un true que entre en el if. Por tanto f_arrays_equal devuelve
   true, aunque Python consideraría distintas esas listas.
6. El break sucede ANTES de `centroids := new_centroids`. Los percentiles
   originales permanecen en posiciones 0/1/2. Los thresholds visibles son
   p25 y p75 en este recorrido normal, no las medias finales de Lloyd.

Esta explicación deriva del source y de la semántica documentada de
[arrays Pine v5](https://www.tradingview.com/pine-script-docs/v5/language/arrays/),
[operadores](https://www.tradingview.com/pine-script-docs/v5/language/operators/)
y [bool NA en condicionales](https://www.tradingview.com/pine-script-docs/v5/language/type-system/).
Los constructores no son un «defecto del mirror»; estaban en la fuente exacta.
No se corrigen por intuición Python. El port ejecuta sus pasos literalmente;
no sustituye thresholds por constantes ni por una regla simplificada p75/p25.
`converged` refleja la salida de f_arrays_equal, no convergencia de k-means.
La referencia independiente de listas/loops no importa el cálculo optimizado.

## Percentiles: qué está medido y qué falta medir directamente

Se implementa interpolación lineal sobre estadísticas de orden:
`rank=(n-1)*p/100`. No depende de numpy.quantile. Pine no llama array.sort
en el source del indicador. Las diez observaciones reales apoyan la alternativa
A, cálculo de percentiles ordenados internamente: p25/p75 ordenados coinciden
en todos los registros. Interpolar por posición del array cronológico no
explica esos datos. Para la vela 10:30 daría p75≈50.06, no56.15.

El manual describe interpolación lineal, pero no documenta aquí todos los
detalles internos ni efectos sobre el array original. No se afirma haber
medido si el builtin reordena el array en sitio. El diagnóstico compara un
array separado `[30,10,40,20]` con una copia ordenada y muestra su primer
elemento antes/después. No ordena ni modifica rsi_values para medirlo.
Tampoco se ha observado directamente array.indexof(allNA,NA) en este motor;
su resultado no cambia las medias NA del warmup ni los thresholds maduros
demostrados. El diagnóstico también expone ese caso.

## Fixture real y resultado reproducible

`mlrsi_tradingview_fixture_20261004.json` almacena observaciones del usuario,
precisión de pantalla, hora local/UTC y source checksum. La fecha de TradingView
es la apertura, no el cierre. `mlrsi_binance_low_20261004.json` conserva
4002 LOWs públicos cerrados contiguos, URLs/checksums de descargas, rango y
checksum de los LOWs. Ningún test usa red.

Se conserva el comienzo y ancla3999 del replay anterior a08:49UTC; las
barras posteriores modelan append realtime. No se selecciona otro histórico
para mejorar el match. La última fila de09:30UTC todavía abierta se excluye de
los LOWs de evaluación. Los valores finales de una vela posteriormente cerrada
no se presentan como un tick histórico anterior de esa vela.

| Apertura Madrid | RSI calculado | Upper calculado | Lower calculado | TV RSI / Long / Short |
|---|---:|---:|---:|---|
|09:00|58.776219|56.112908|45.538807|58.78 /56.11 /45.54|
|09:15|58.048673|56.118000|45.540678|58.05 /56.12 /45.54|
|09:30|57.364640|56.124125|45.542550|57.36 /56.12 /45.54|
|09:45|57.885155|56.139170|45.544421|57.89 /56.14 /45.54|
|10:00|60.280689|56.139612|45.544879|60.28 /56.14 /45.54|
|10:15|62.131463|56.143336|45.545337|62.13 /56.14 /45.55|
|10:30|60.960127|56.148568|45.545795|60.96 /56.15 /45.55|
|10:45|60.945948|56.153534|45.546253|60.95 /56.15 /45.55|
|11:00|60.493526|56.166808|45.547712|60.49 /56.17 /45.55|
|11:15|61.277709|56.171850|45.549171|61.28 /56.17 /45.55|

Las diez filas calculadas son GREEN. Las cuatro últimas incluyen color GREEN
explícitamente observado por el usuario; las primeras tienen RSI>Long según
su propia tabla. En10:30 el resultado previo era upper68.4705299/lower42.5126098,
NEUTRAL; RSI60.9601268 y sample count3000 permanecen idénticos. Se descartan
RSI/EMA/source/timezone y la ventana por sí sola como causa de este mismatch.
`mlrsi_public_case_manifest.json` conserva esos cálculos V3 como evidencia
anterior, ahora enlazada al fixture observado. No se borra el desacuerdo previo.

## Histórico, confirmed, provisional y límites

`CONFIG_VERSION=CAPTURE_LOW29_EMA4_PINE_PARITY_V4`.
LOW, Wilder29 y EMA4 permanecen sin cambios. El source construye factors
10..90 step5 pero no lo usa después; tampoco usa perfAlpha. Sigma1 no afecta
EMA. No se inventa una optimización dependiente de esa metadata.

En bootstrap el último índice disponible, incluida la vela abierta, es fijo.
last_bar_index-bar_index<=3000 incluye3001 índices: con vela abierta suelen
ser3000 samples confirmed +1 provisional; sin ella3001 confirmed. Las nuevas
barras realtime incrementan el array sin evicción. En este fixture el contador
va de2994 a3003 en las diez filas; en10:30 es3000.

La copia provisional clona el carry y hace rollback después de cada cálculo;
no suma ticks al histórico ni confirma color. Confirmed exige timestamp UTC de
cierre real. Los tres TF son independientes. Una recarga limpia cambia el ancla
y puede cambiar thresholds; una historia/Pine session diferente sigue siendo
un posible motivo de desacuerdo futuro. Prefix invariance solo se afirma con
la misma ancla, no al reconstruir charts con distinto último índice.

Se conserva el loop inclusivo0..1000 (hasta1001 intentos), media de clusters
vacíos NA y primer índice en empate. La primera barra normal tarda2 intentos
por3→6 slots; las maduras salen en1 por la igualdad descrita. La autoridad del
color sigue siendo RSI>centroid[2] / RSI<centroid[0], sin histéresis.
Cuando no hay RSI/thresholds finitos, el observer muestra UNKNOWN; el ternario
Pine puede mostrar gris. Esa divergencia de warmup se mantiene explícita para
evitar presentar datos inválidos como confirmación. El límite100000 slots
falla sin evicción ni cambio parcial de carry, siempre fuera de Guardian.

## Diagnóstico Pine para contrastar directamente el motor

Pegar `tests/fixtures/mlrsi_backquant_diagnostic.pine` como indicador Pine v5
en BINANCE:BTCUSDT15m. Defaults LOW29/EMA4/sigma1 y configuración capturada.
Contiene el core exacto del autor, con instrumentación de solo lectura:

- sample count, last_bar_index, bar_index, diferencia;
- RSI suavizado, percentiles25/50/75, centroides finales0/1/2;
- tamaño del array de centroides, intentos, igualdad previa al break;
- tamaños de clusters, constructor+push, mínimos/índices conNA, medias vacías;
- percentiles del array desordenado y copia ordenada, primer elemento antes/después.

Ver esos valores en Data Window/Vista de tabla para04/10/2026 10:30 Madrid
(08:30UTC, apertura). Un script recién añadido puede usar otra ancla que el
indicador que llevaba tiempo ejecutándose; comparar también sample count y
last_bar_index. El archivo viejo mlrsi_pine_validation.pine queda identificado
como harness del contrato V3 anterior; no es el diagnóstico literal actual.
El nuevo script no ha sido compilado/ejecutado en TradingView aquí.
No hace falta escoger otra aproximación para reproducir la tabla aportada;
este diagnóstico permite validar detalles internos y una próxima comparación.

## Estado, regresión y seguridad

V4 persiste pine_centroids completo, incluidos los tres slots NA finales.
EstadosV1/V2/V3 incompatibles hacen una reconstrucción limpia y silenciosa;
journals originales conservan su config_version. RestartV4 conserva array,
ancla, seed y carry sin duplicar CROSS/RESUME/confluencias antiguas.
/mlrsi sigue leyendo exclusivamente cache y mostrando valores/contador.

Los tests comparan todas las barras de3436 LOWs sintéticos y4002 LOWs públicos
contra la traducción independiente, además de las diez filas de TradingView.
Se comprueban gate2999/3000/3001, ticks provisionales, restart y migración.
Research RSI27/CROSS/RESUME, Guardian, poller, host y V8 mantienen hashes/AST.
Este cambio de semántica no modifica ni reinterpreta el resultado congelado
15mNO EDGE /1HGREEN_RESUME inconclusive; no demuestra edge del nuevo observer.

SHADOW ONLY — trade_authority=false — NO REAL ORDER — NO MERGE — NO DEPLOY.
