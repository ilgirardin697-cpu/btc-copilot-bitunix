# ML RSI PINE_PARITY: contrato y evidencia pendiente

La observación del usuario a las 10:49 Europe/Madrid del 04/10/2026 es
**TradingView GREEN frente a observer NEUTRAL**. LOW29 no resolvió el desacuerdo.
Este cambio elimina diferencias conocidas de la implementación, pero **no declara
resuelta esa validación real** ni autoriza trading.

## Autoridad principal y acceso a fuente

Indicador: [Machine Learning RSI, BackQuant, DKa7Dmc5](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/).
La página oficial lo marca open-source y describe tres clusters con el centroide
alto como threshold LONG y el bajo como threshold SHORT. El HTML público
identifica el Pine `USER;d581ed0024f6459aa8c889950373508c`, versión `25.0`.
La descarga pública de su fuente devuelve **HTTP401**. El identificador alternativo
PUB devuelve404. No se usa sesión TradingView ajena, no se extraen cookies y
no se decompila el código compilado. La pestaña Source code legible sigue faltando.
Se pidió al usuario su texto para poder contrastarlo literalmente.

La [copia atribuida](https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html)
crea arrays de tres slots vacíos y luego añade distancias/medias. Según la
semántica documentada, esos slots contienen NA y los índices de las distancias
finitas dejan de ser0/1/2; los primeros thresholds también quedan NA. No se
adopta esa copia como fuente válida ni se corrige para llamarla Pine original.

## Qué se implementa y qué se verifica

`CONFIG_VERSION=CAPTURE_LOW29_EMA4_PINE_PARITY_V3`, `Math mode: PINE_PARITY`.
El nombre identifica el **contrato solicitado**; no constituye certificación
de paridad BackQuant. Source LOW, Wilder29, EMA4, tres centroides,
maxData3000, maxIter1000. Range10–90, step5, memory10 y sigma1 conservan su
metadata; no se inventa una función adicional.

Los [índices oficiales Pine](https://www.tradingview.com/pine-script-docs/concepts/chart-information/)
distinguen bar_index de last_bar_index: el último índice disponible es conocido
durante toda la carga histórica. Python fija ese índice por TF al cargar la lista,
incluyendo su vela abierta. Calcula RSI desde el comienzo, pero añade únicamente
las barras que cumplen `last_bar_index-bar_index<=3000`. La desigualdad incluye
3001 índices, no3000. Con una barra abierta en el bootstrap hay normalmente
3000 muestras cerradas, más una en la evaluación provisional. Sin barra abierta,
3001 muestras cerradas. Cada barra realtime siguiente añade una; no existe shift.
No se modifica el ancla al recuperar el mismo estado V3.

Los [arrays y su persistencia](https://www.tradingview.com/pine-script-docs/language/arrays/)
explican que `var` conserva el array, que la inicialización sin valor usa NA y
que la media vacía devuelve NA. Se representa el array mediante lista persistida;
no se conserva una deque acotada. Los slots NA de warmup se cuentan si cumplen
el gate. El límite de100000 elementos falla sin descartar muestras. La copia
provisional aplica [rollback a lo comprometido al cierre](https://www.tradingview.com/pine-script-docs/language/execution-model/):
cada tick vuelve a clonar la misma serie cerrada, sin acumular ticks ni afectar
confirmed. Un reload limpio puede cambiar la selección histórica; esta matemática
no sustituye el research causal rolling ni garantiza prefix invariance entre
anclas diferentes.

Wilder seed: SMA de29 cambios LOW válidos; recurrencia alpha1/29. EMA4 seed:
primer RSI finito y alpha2/5. Fórmula RSI y seeds siguen el contrato de las
[funciones built-in Pine](https://www.tradingview.com/pine-script-reference/v5/).
Los tests validan fixtures deterministas, pero no son capturas de built-ins
ejecutados en TradingView. El histórico inicial del gráfico aún puede diferir.

Percentiles25/50/75 usan interpolación explícita `(n-1)*p/100`. Se verifican
vectores con resultado conocido y equivalencia numérica con NumPy linear;
**no se asume que esto demuestre identidad con el builtin de TradingView**.
El [manual de referencia](https://www.tradingview.com/pine-script-reference/v6/)
describe interpolación lineal, sin permitirnos comprobar aquí cada caso del
motor. El harness propio `tests/fixtures/mlrsi_pine_validation.pine` permite
capturar percentiles/RSI/EMA/centroides reales. **No es fuente BackQuant y no se
ha ejecutado en TradingView durante esta tarea.**

Clustering: p25/p50/p75 nuevos por barra, distancias absolutas, primer índice
en empate, media por cluster sumada en orden de inserción, igualdad exacta.
El [loop Pine](https://www.tradingview.com/pine-script-docs/language/loops/)
incluye el límite:0..1000 permite1001 intentos. Agotarlo deja los últimos
centroides finitos; `converged=false` no fuerza UNKNOWN. RSI>upper es GREEN,
RSI<lower es RED; igualdad es NEUTRAL. No se introduce histéresis.

**Divergencia patológica declarada:** un cluster vacío devuelve NA y no retiene
su centroide previo. Python termina ese cálculo como UNKNOWN en vez de seguir
repartiendo con centroides NA o publicar el NEUTRAL de una comparación inválida.
El comportamiento exacto de ese caso en la versión del autor sigue sin verificar.

## Replay del caso real: sigue sin cumplir GREEN

Se consultaron exclusivamente klines públicos de Binance spot15m con
`endTime=2026-10-04T08:49:00Z`; se usaron3999 velas cerradas y el índice de la
vela abierta para anclar. **El OHLC final histórico de esa vela abierta NO se
usa para reconstruir un tick provisional de08:49**, porque eso introduciría
información posterior. Solo se utiliza su existencia/timestamp en el ancla.

Última vela cerrada: open08:30UTC, close08:45UTC (10:45 Europe/Madrid).

| Valor | PINE_PARITY | Rolling anterior |
|---|---:|---:|
| RSI suavizado | 60.9601267869 | 60.9601267869 |
| Lower | 42.5126097870 | 42.5126097870 |
| Middle | 53.2857514782 | 53.2857514782 |
| Upper | 68.4705298745 | 68.4705298745 |
| Color | NEUTRAL | NEUTRAL |
| Threshold samples | 3000 closed | 3000 rolling |

Las seis últimas velas cerradas del replay también son NEUTRAL. Esto demuestra
que **el cambio de ventana por sí solo no explica el GREEN mostrado por el usuario**.
Un observer arrancado antes tendría más muestras, pero no conocemos el momento
de recarga del gráfico ni sus valores para emparejarlo. No se ajusta el historial
o los thresholds para fabricar un match. La evidencia reproducible resumida y
los checksums públicos están en `tests/fixtures/mlrsi_public_case_manifest.json`.

Para cerrar la validación faltan el Pine oficial legible y RSI/upper/lower de
esa misma vela en TradingView. Después deben compararse venue, LOW, timestamps,
histórico inicial, ancla, contador y resultados. No basta con el color aislado.

## Tests y límites de la afirmación

La referencia independiente `pine_reference_mlrsi` no importa NumPy ni cálculo
de producción. La fixture de3436 LOWs sintéticos permite comparar cada barra
antes/durante/después del bootstrap, índices2999/3000/3001,36 cierres realtime,
RSI, EMA, los tres centroides, color, iteraciones y contador. Es evidencia del
contrato Python, **no fixtures oficiales ejecutadas por TradingView**.

Estado V1/V2 incompatible: una reconstrucción silenciosa; journals anteriores
conservados con sus versiones. Restart V3 mantiene ancla/array sin duplicar
eventos. `/mlrsi` lee cache y muestra mode, muestras y centroides de las dos capas.

Guardian, V8, poller, host y research congelado conservan hashes/AST. El observer
permanece SHADOW ONLY, `trade_authority=false`. Ningún resultado modifica
protección, riesgo, dirección, sizing o entradas. Sin merge, deploy u órdenes.
