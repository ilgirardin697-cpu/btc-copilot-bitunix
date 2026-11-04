# I-GOD Killzone Probability Radar — entrenamiento y validación

**Resultado: NO VALIDADO. SIN PROBABILIDADES VALIDADAS.**
El indicador se entrega con panel y publicación cerrada. No se cambia Killzone V3.7 Lite.
Modelo seleccionado únicamente en validación: **PRICE_4H**. Versión `KZR_V1_b3e7f819bb07`.
Fallos del gate predeclarado: `['validation:NO_INCREMENTAL_PRICE_GAIN', 'test:NO_INCREMENTAL_PRICE_GAIN']`. No se cambia de candidato después del test.

## Protocolo, mercado y tiempo

Congelado en affca18 antes de descargar/calcular outcomes. SHA256 `23e8d5ce83b0fae2ace74dcc1e789d27cb1e6764b513ecb059911268fb6edad1`.
Binance Spot BTCUSDT, no Futures/Bitunix. Train 2022–2023; validación 2024;
test posterior enero2025–octubre2026. Diciembre2021 inicializa indicadores.
Último día de train/validación excluido como embargo. NO VIRGIN HOLDOUT.
La historia de mercado ya apareció en otras investigaciones; esto no es validación prospectiva.

PINE_A: America/New_York con DST, Asia20–23 (4 H1), Londres02–05 (4 H1).
Cada ciclo tiene 60 estimaciones as-of05:00,05:01,…05:59. A05:00 se conocen solo
las H1 anteriores; a05:mm solo se añaden mm minutos cerrados de la última H1.
No hay nueva predicción a06:00: entonces se fijan los targets y comienza el outcome.
El primer toque se busca entre06:00 inclusive y20:00 exclusivo, con1m; ambos en la misma
primera barra1m sería AMBIGUO, no NINGUNO. Las franjas500 y TP±200 no forman parte del label.
No se usan targets definitivos ni el high/low/close final de05H1 como variables predictoras.

## Datos y exclusiones

117 ZIP oficiales con SHA256 comparado con CHECKSUM oficial. Raw local/ignorado.
43101 H1 válidas,2541519 minutos válidos. Tres registros con closeTime anticipado
quedan documentados y excluidos sin modificar el original; dejan gaps explícitos.
También hay huecos de mercado. Se reinicia el warmup tras discontinuidad H1 y se exige
igualdad exacta OHLC entre1m y H1 en todas las horas usadas para predicción/outcome.
1765 ciclos de calendario;1755 utilizables;10 incompletos;
0 ambiguos. Las cinco fechas DST de primavera no tienen02 local
y NO se convierten artificialmente en cuatro velas. Todos los rechazos están en cycles.csv.
105300 filas de estimación NO son105300 observaciones independientes: la unidad es el ciclo.

## Modelos sin búsqueda de parámetros

PRIOR: frecuencias de clase de train con Laplace1. PRICE: seis variables de precio/rangos parciales.
PRICE_MOMENTUM añade AO5/34, slope, ADX14/14, slope y balanceDI. PRICE_BBWP añade
BBWP7/ranking101 y slope. PRICE_4H añade variación de los dos últimos cierres4H confirmados.
H1 AO/ADX/DMI/ATR/BBWP se congelan al cierre05:00 durante la hora predictiva; precio parcial sí cambia.
No se calcula con una4H abierta. El engine congelado se importa solo para fórmulas públicas offline,
sin cambiarlo; no se afirma paridad propietaria de Bitman.
Softmax lineal L2=.01, z-score solo train, clip±8; Adam determinista lr=.03, máximo3000 pasos,
tolgrad1e-7. Sin calibrador posterior, búsqueda de umbrales ni combinaciones exhaustivas.

## Resultados por partición

Multiclass Brier=sum de tres errores cuadrados (menor es mejor); log-loss natural.
IC95: diferencias emparejadas con2000 bootstraps circulares por bloques de7 ciclos.
Calibración: macroECE,10 bins por clase; todos los bins con sus n en model_validation.json.
Las filas/minutos del mismo ciclo mantienen el mismo peso. No se estima n efectivo como60×días.

| Partición | Modelo | Ciclos | Brier | Log-loss | MacroECE | Ganancia Brier vs PRIOR [IC95] |
|---|---|---:|---:|---:|---:|---|
|train|PRIOR|722|0.645925|1.068798|0.000322|0.000000 [0.0, 0.0]|
|train|PRICE|722|0.604123|1.001953|0.013471|0.041802 [0.02705796934781261, 0.056779057806788484]|
|train|PRICE_MOMENTUM|722|0.594546|0.985412|0.022371|0.051378 [0.03549155411306774, 0.06862156746431015]|
|train|PRICE_BBWP|722|0.602422|0.998722|0.016955|0.043502 [0.02811618864312105, 0.059200357318698216]|
|train|PRICE_4H|722|0.602327|0.998634|0.020005|0.043598 [0.029499748728896758, 0.05868880657507305]|
|validation|PRIOR|364|0.652972|1.078538|0.014056|0.000000 [0.0, 0.0]|
|validation|PRICE|364|0.602932|1.001285|0.036413|0.050041 [0.028233708182455748, 0.07218135459847072]|
|validation|PRICE_MOMENTUM|364|0.608992|1.006460|0.034737|0.043980 [0.022082150704189146, 0.06740457610003867]|
|validation|PRICE_BBWP|364|0.604315|1.002576|0.036879|0.048657 [0.02669330676832226, 0.07092912914596383]|
|validation|PRICE_4H|364|0.601601|0.997499|0.033214|0.051371 [0.029113788847988542, 0.07441872247950024]|
|test|PRIOR|667|0.640150|1.060809|0.012074|0.000000 [0.0, 0.0]|
|test|PRICE|667|0.598303|0.990154|0.028397|0.041847 [0.025717441863898453, 0.058583268159621865]|
|test|PRICE_MOMENTUM|667|0.596394|0.984349|0.028569|0.043756 [0.026235424969800598, 0.06321940811138176]|
|test|PRICE_BBWP|667|0.602318|0.994704|0.031691|0.037832 [0.02065775375842858, 0.0555112077992919]|
|test|PRICE_4H|667|0.597252|0.990312|0.026797|0.042897 [0.027306466807364652, 0.06058587328759877]|

## Incremento sobre precio, estabilidad y limitaciones

- validation: PRICE_4H−PRICE, ganancia Brier 0.001330; IC95 [-0.0030251097441866374, 0.00617330145871793].
- test: PRICE_4H−PRICE, ganancia Brier 0.001051; IC95 [-0.002487848966469498, 0.00480813854222029].

Meses de test con mejora vs PRIOR:18/22.
- 2025H1: n=180; ganancia Brier vs PRIOR=0.025985.
- 2025H2: n=184; ganancia Brier vs PRIOR=0.049850.
- 2026JAN_OCT: n=303; ganancia Brier vs PRIOR=0.048722.

monthly.csv contiene los cinco modelos en cada mes y per_minute_test.csv los60 minutos;
no se selecciona retrospectivamente el minuto mejor. La comparación por eras usa el MISMO
fit congelado: es una evaluación walk-forward sin actualización, no múltiples retrainings.
La selección entre cuatro candidatos usa2024; la incertidumbre de esa selección y la reutilización
de la historia limitan la evidencia. Un resultado histórico favorable tampoco verifica el feed Pine.

## Python frente a Pine — alcance exacto

El exportador escribe los mismos coeficientes de64bits en Pine. Un espejo escalar comprueba
la aritmética softmax con vectores históricos; NO es ejecución de Pine ni evidencia independiente.
Registros numéricos REALES de este radar en TradingView comparados: **0**.
Compilación en TradingView y pruebas reales de actualización/reload: **PENDIENTES**.
El comparador parity.py admite Pine Logs reales para detectar diferencias por feature y timestamp.
Los64 registros anteriores validan Killzone, NO este nuevo radar. No se reutilizan como paridad del radar.

## Entrega, no repainting y fiabilidad

Pine procesa request.security_lower_tf("1") con tiempos y prefijos contiguos; no incorpora
minutos abiertos. Histórico se reconstruye desde arrays sin leer el final de Londres como predictor.
En tiempo real solo se registra la última información realmente disponible, no se emiten60 registros
retroactivos al conectar. El reloj no dispara Pine: hace falta un update/tick; puede haber retraso.
Si hay huecos se muestra incompleto/última información; no se inventan minutos.
No hay ausencia absoluta de repainting: feeds revisados, arrays limitados, distinta profundidad y
reload pueden cambiar reconstrucciones. varip/Pine Logs no son un journal durable. Se facilita
captura offline append-only/hash-chain de logs entregados por el propietario; nunca se mezcla replay
histórico con observación forward. No existe receptor/webhook, alertas ni despliegue de esa captura.

## Ejemplos

example_SUPERIOR_FIRST.svg, example_INFERIOR_FIRST.svg y example_NEITHER.svg son los primeros
ciclos de test de cada clase, elegidos para auditoría, NO una muestra aleatoria de rendimiento.
closed_minute_examples.json contiene features reales a05:00/15/30/59 y el panel sin porcentajes.
Son reconstrucciones offline, no capturas de TradingView ni predicciones forward observadas.

**Decisión: NO PUBLICAR PROBABILIDADES.** Mantener NO VALIDADO. No hay permiso de trading.
No se retocan reglas ni se sustituye el candidato elegido para obtener un resultado positivo.
Fórmulas, sesiones y niveles originales, OWNER_B/C y producción permanecen intactos.

Documentación oficial consultada:
- [Arrays LTF y datos confirmados](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).
- [Límites por plan](https://www.tradingview.com/pine-script-docs/writing/limitations/).
- [Repainting y revisiones](https://www.tradingview.com/pine-script-docs/concepts/repainting/).
- [Formato público Binance](https://github.com/binance/binance-public-data/blob/master/README.md).

SHADOW ONLY. TRADE AUTHORITY: NONE.
