# I-GOD Killzone Optimal Entry Research V0

**No hay método de entrada con ventaja neta demostrada en esta comparación.**
Resultado de la familia: **INCONCLUSIVE**; dos brazos LONG son **NO EDGE**.
No se recomienda activar señales, PAPER continuo ni integración operativa.

## Qué se fijó antes de evaluar

Protocolo commiteado en `cc74bb5`, antes de calcular los nuevos outcomes.
SHA256 del protocolo: `525d73e8f3982430c9d0c1cc199693a21504eaf93a5c074c7a89fd13e4b88237`.
Se comparan cuatro candidatos y BASELINE, sin optimización o selección posterior.
Nombre «Optimal» no significa que se haya encontrado un óptimo. PRICE no participa.
Fechas, stop, 1,5R, latencia, costes y caducidad son convenciones de investigación predeclaradas.

## Fuente y temporalidad

BTCUSDT **BINANCE SPOT**, 2025-11-01T00:00:00Z → 2026-11-01T00:00:00Z exclusivo.
9504 H1 incluyendo octubre de 2025 para warmup; 525600 minutos; 8760 agregaciones H1/60m exactas.
Se releen 25 ZIP oficiales previamente auditados de PR #41 y se comprueban otra vez sus hashes locales contra los manifests preservados.
No se descarga ningún dataset nuevo ni se reconsulta el checksum remoto actual. Sin gaps, duplicados, imputación o reparaciones.
365 ciclos de calendario; 364 completos. El 08/03/2026 es incompleto: 02:00 NY no existe por DST.
Timestamps del archive Spot en microsegundos → milisegundos enteros; no se redondea OHLC.
[Fuente pública y convenciones de timestamps Binance](https://github.com/binance/binance-public-data).

**NO VIRGIN HOLDOUT.** Esta historia ya se vio. Noviembre–febrero, marzo–junio y julio–octubre
son particiones descriptivas cronológicas, no un nuevo test independiente. No hay reentrenamiento.
Los 20 brazos método×lado×coste repiten los mismos ciclos; no son 7.300 observaciones independientes.

## Geometría PINE_A y nuestras hipótesis separadas

America/New_York con DST; Asia 20/21/22/23, Londres 02/03/04/05. Cuatro velas cerradas en cada sesión.
Se reutiliza byte-a-byte `project`/ATR de PR #41. Tres registros reales Pine ya auditados se conservan como golden de fórmula;
esto NO añade evidencia independiente nueva de TradingView ni valida entradas.
HIGH=max(aHigh,lHigh); LOW=min(aLow,lLow); amplitud=HIGH−LOW.
SUPERIOR=min(aHigh,lHigh)−0,03×altura_caja_superior+amplitud;
INFERIOR=max(aLow,lLow)+0,03×altura_caja_inferior−amplitud.
Se respetan empates, cajas solapadas y contenidas. No se usan diagonales ni extrapolaciones.
Los niveles se calculan al disponer de las cuatro Londres a 06:00. Es un cálculo causal independiente;
no se afirma identidad de la actualización visual `endLondon` del Pine, que puede esperar al cierre de la barra exterior.
Paridad aquí significa fórmula auditada, no reproducción exacta del momento de dibujo de TradingView.

| Método | Regla congelada |
|---|---|
| BASELINE | Dirección del cuerpo agregado Londres a 06:00; entrada siguiente minuto |
| AFTER_LONDON | Cierre Londres fuera del rango Asia y cuerpo Londres alineado |
| BREAKOUT | Primera H1 posterior con cuerpo completo estrictamente fuera de HIGH/LOW |
| RETEST | Primera ruptura, después otra H1 toca su nivel y cierra del lado roto |
| LIMIT_ZONE | Límite en midpoint Londres, conocido a 06:00, colocado 06:01 y sin repricing |
| NO ENTRAR | Cero exposición y cero PnL |

La confirmación por cuerpo completo y primera oportunidad por ciclo son nuestras convenciones, no las alertas originales close-only de PINE_A.
TP = target teórico; **no** adelanto 200 OWNER_B ni franja visual 500.
SL común = extremo opuesto Londres ±0,20 ATR14 congelado a 06:00. Nunca se amplía.
Riesgo máximo estimado 0,25 %; R/R neto mínimo 1,5; nominal+fee dentro del equity; sin apalancamiento.
Cada método/lado/coste mantiene su cuenta independiente desde 10.000, sin reinicios mensuales.

## Resultados primarios, por lado

Coste supuesto: 10 bps de comisión por lado; 2 bps adversos de mercado por lado.
El límite se llena a su precio máximo/mínimo, sin slippage que viole ese límite. Son escenarios, no fees o fills de cuenta verificados.

| Método | Lado | n | Neto USDT | Retorno % | Media R | IC95 R | PF | DD MTM % | Clasificación |
|---|---|---:|---:|---:|---:|---|---:|---:|---|
|BASELINE|LONG|49|-616.17|-6.16|-0.518|[-0.776; -0.227]|0.333|6.40|NO EDGE|
|BASELINE|SHORT*|51|-42.93|-0.43|-0.032|[-0.431; 0.348]|0.941|2.37|INCONCLUSIVE|
|AFTER_LONDON|LONG|8|-144.05|-1.44|-0.725|[-1.000; -0.250]|0.041|1.68|INCONCLUSIVE|
|AFTER_LONDON|SHORT*|13|-108.57|-1.09|-0.334|[-0.930; 0.427]|0.535|2.13|INCONCLUSIVE|
|BREAKOUT|LONG|1|-7.39|-0.07|-0.295|[-0.295; -0.295]|0.000|0.45|INCONCLUSIVE|
|BREAKOUT|SHORT*|0|0.00|0.00|—|[—; —]|—|0.00|INCONCLUSIVE|
|RETEST|LONG|0|0.00|0.00|—|[—; —]|—|0.00|INCONCLUSIVE|
|RETEST|SHORT*|0|0.00|0.00|—|[—; —]|—|0.00|INCONCLUSIVE|
|LIMIT_ZONE|LONG|74|-862.01|-8.62|-0.486|[-0.672; -0.281]|0.329|8.68|NO EDGE|
|LIMIT_ZONE|SHORT*|86|-407.82|-4.08|-0.192|[-0.492; 0.107]|0.705|5.11|INCONCLUSIVE|

*SHORT representa exposición hipotética al precio Spot. No es una venta Spot ejecutable sin inventario/préstamo ni Binance/Bitunix Futures.
No hay serie de funding/mark, borrow, spread/cola o reglas de contrato verificados; ese bloqueo impide declarar un SHORT prometedor ejecutable.
Funding LONG Spot: no aplica. Funding de futuros: desconocido/no modelado, nunca asumido cero.

## Activación, rechazos y TP frente a resultado neto

| Método | Lado | Señales técnicas | Operaciones | Sin fill | Rechazadas | Neto positivo % | TP % | Ambiguas |
|---|---|---:|---:|---:|---:|---:|---:|---:|
|BASELINE|LONG|184|49|0|135|18.4|10.2|0|
|BASELINE|SHORT*|180|51|0|129|37.3|19.6|0|
|AFTER_LONDON|LONG|81|8|0|73|12.5|0.0|0|
|AFTER_LONDON|SHORT*|72|13|0|59|23.1|15.4|0|
|BREAKOUT|LONG|135|1|0|134|0.0|0.0|0|
|BREAKOUT|SHORT*|132|0|0|132|—|—|0|
|RETEST|LONG|63|0|0|63|—|—|0|
|RETEST|SHORT*|63|0|0|63|—|—|0|
|LIMIT_ZONE|LONG|184|74|14|96|23.0|6.8|0|
|LIMIT_ZONE|SHORT*|180|86|21|73|29.1|16.3|0|

Hay 267 primeras rupturas técnicas (135 UP,132 DOWN), pero solo una entrada pasa el stop/RR predeclarado.
Hay 126 retests confirmados (63/63), pero ninguna entrada aceptada. No equivalen a inexistencia de rupturas o retests.
Las causas exactas por método/lado están en summary.json: R/R insuficiente, target detrás, límite no pasivo o precio posterior ya inválido.
RETEST no confirma en 141 de las secuencias con ruptura (72/69). No se cambió el nivel ni se buscó una segunda oportunidad.
LIMIT_ZONE: 88 órdenes LONG que superan los filtros, 74 fills (84,09 %); 107 SHORT,86 fills (80,37 %).
Las 35 órdenes sin activación caducan; no se imputan a ganadoras. Los fills no prueban ejecución en cola.
Por tanto sí se puede calcular una zona antes de llegar, pero esta zona midpoint NO demuestra utilidad económica.

## Ejecución y riesgo temporal

Mercado: primer precio de apertura 1m un minuto después de conocer la señal, más slippage adverso; se revalida R/R sin mover SL/TP.
Límite: orden fijada a 06:01, requiere penetración mínima de un tick (0,01), nunca solo toque; precio congelado.
No se cuenta el TP de la vela confirmadora. En fill limitado con TP en el mismo minuto y orden desconocido no se acredita ese TP.
SL/TP en la misma 1m: stop primero. Gap a través de límite/stop: no se omite la pérdida, se toma el precio adverso.
Caducidad/salida temporal al open de 19:59 NY, antes de la siguiente Asia20:00. El high/low/close posterior de esa 1m no modifica el trade.
MAE/MFE son cotas basadas en OHLC1m: el extremo puede anteceder al fill o suceder después de la salida intraminuto.
Los límites de riesgo son estimaciones al stop, no garantía frente a gaps ni prioridad en el libro.

Auditoría de ejecutabilidad: 71/160 límites llenados tienen midpoint aritmético fuera del tick de referencia 0,01 de los logs Pine.
No se redondean después de ver outcomes para rescatar la estrategia. Son fills de escenario, no órdenes probadas en exchange.
Tampoco se cuantiza cantidad con filtros históricos de lot/minNotional ni se verifica cola. Esto limita cualquier afirmación de ejecutabilidad real, incluso LONG.
El detalle está en execution_limitations.json. Una evaluación exacta de órdenes exigiría otro protocolo previo; no se modifica el actual retrospectivamente.

## Incertidumbre, controles y estabilidad

Bootstrap circular de 7 días, 2.000 réplicas, semilla fija. Días sin entrada mantienen cero.
Se informa IC95 descriptivo e IC98,75 para cuatro comparaciones contra BASELINE, sin elegir al ganador.
Métrica incremental: R sobre el presupuesto diario de equity emparejado por fecha/lado. Se separa de la media R condicional por trade.
Menos pérdidas que un baseline perdedor NO prueba ventaja frente a NO ENTRAR.
Con un único trade, el IC condicional puede colapsar: no es precisión estadística; el clasificador conserva INCONCLUSIVE por n insuficiente.

| Método | Lado | Δ R/ciclo vs BASELINE | IC98,75 Δ | ex-best1 R | ex-best3 R | Neto stress USDT |
|---|---|---:|---|---:|---:|---:|
|BASELINE|LONG|0.0000|[0.000; 0.000]|-0.583|-0.705|-530.07|
|BASELINE|SHORT*|0.0000|[0.000; 0.000]|-0.097|-0.209|-40.83|
|AFTER_LONDON|LONG|0.0536|[0.009; 0.095]|-0.864|-1.000|-130.23|
|AFTER_LONDON|SHORT*|-0.0074|[-0.063; 0.044]|-0.608|-0.937|-12.45|
|BREAKOUT|LONG|0.0687|[0.019; 0.115]|—|—|0.00|
|BREAKOUT|SHORT*|0.0044|[-0.067; 0.067]|—|—|0.00|
|RETEST|LONG|0.0695|[0.020; 0.116]|—|—|0.00|
|RETEST|SHORT*|0.0044|[-0.067; 0.067]|—|—|0.00|
|LIMIT_ZONE|LONG|-0.0290|[-0.083; 0.026]|-0.540|-0.613|-639.61|
|LIMIT_ZONE|SHORT*|-0.0407|[-0.110; 0.031]|-0.233|-0.313|-270.09|

STRESS = 15 bps fee/lado y 5 bps slippage de mercado/lado; vuelve a aplicar exactamente el mismo filtro, por lo que puede cambiar n.
No se elige el escenario más favorable. La expectativa primaria de los diez brazos es negativa o no estimable por ausencia de trades.
Meses completos, distribución de R, MAE/MFE, duración y todas las particiones se conservan en monthly.csv y summary.json.

## Particiones descriptivas

| Método | Lado | Nov–Feb n / neto | Mar–Jun n / neto | Jul–Oct n / neto |
|---|---|---|---|---|
|BASELINE|LONG|21 / -260.58|17 / -230.97|11 / -124.62|
|BASELINE|SHORT*|23 / 169.09|18 / -136.12|10 / -75.90|
|AFTER_LONDON|LONG|1 / -25.00|5 / -100.52|2 / -18.53|
|AFTER_LONDON|SHORT*|7 / -60.53|4 / -61.43|2 / 13.38|
|BREAKOUT|LONG|0 / 0.00|1 / -7.39|0 / 0.00|
|BREAKOUT|SHORT*|0 / 0.00|0 / 0.00|0 / 0.00|
|RETEST|LONG|0 / 0.00|0 / 0.00|0 / 0.00|
|RETEST|SHORT*|0 / 0.00|0 / 0.00|0 / 0.00|
|LIMIT_ZONE|LONG|26 / -349.70|28 / -291.15|20 / -221.17|
|LIMIT_ZONE|SHORT*|29 / -47.46|29 / -230.51|28 / -129.84|

## Comparación con OWNER_B, sin reinterpretarlo

PR #41 original: 365 ciclos,36 trades,−298,85 USDT; media −0,335R, IC95[−0,755;+0,114], INCONCLUSIVE.
Su control close-only:63 trades,−817,69 USDT, NO EDGE. Se conservan sus resultados.
OWNER_B usa UTC−4 fijo, Asia20–00/Londres01–04, TP±200 y stop junto a HIGH/LOW.
Este estudio usa PINE_A con DST, Asia20–23/Londres02–05, TP teórico y stop opuesto de Londres.
No son estrategias intercambiables ni un experimento que aísle un único cambio frente a OWNER_B.
No se retocan sus reglas ni se presentan retornos cruzados como prueba de mejora causal.

## Respuestas y decisión

- ¿Hay entrada con ventaja demostrable? **No**. Ningún candidato supera el protocolo completo.
- ¿Cuándo LONG/SHORT? Las condiciones técnicas están definidas, pero ninguna está validada como recomendación de entrada.
- ¿NO ENTRAR? Es la decisión operativa prudente fuera de este laboratorio; las variantes no justifican activación.
- ¿Zona calculable antes? **Sí, matemáticamente**: midpoint Londres y su zona están congelados a06:00. **No se ha probado ventaja**.
- ¿Qué falta? Evidencia forward independiente, costes/fills/cola y una serie de futuros apropiada antes de interpretar SHORT ejecutables.
- **NO-GO** para señales fiables o integración. Diseño de I-GOD Killzone Entry Radar solo como instrumentación research NO VALIDADA.

No se construye ni activa un capturador forward, Pine operativo, Telegram, cliente exchange o nuevo servicio.
Revisar primero estos resultados; cualquier futuro protocolo requiere aprobación separada y no puede importar esta historia como forward.

## Evidencias consultables

- cycles.csv: todos los ciclos, métodos, lados y costes, incluidos NO_SIGNAL, incompletos, rechazos y sin fill.
- trades.csv y results.json.gz: cada fill simulado, TP/SL/tiempo, costes, cantidades y equity cronológico.
- frozen_levels.csv: niveles y disponibilidad causal por ciclo; monthly.csv y summary.json: resultados completos.
- equity.svg y example_manifest.json: primeros ganadores/perdedores cronológicos, no ejemplos escogidos por beneficio.
- freeze_manifest.json y manifest de artifacts: procedencia y hashes; pruebas de aislamiento y causalidad.

**SHADOW ONLY. TRADE AUTHORITY: NONE.**
