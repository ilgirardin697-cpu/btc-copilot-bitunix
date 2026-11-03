# OWNER_B: revisión offline de los 64 registros reales

**POST-HOC. NO VIRGIN HOLDOUT. NO FORWARD OBSERVATIONS. NO PROFITABILITY CONCLUSION.**

Se conserva el primer ciclo parcial como EXCLUIDO; no se recupera Asia desde agregados PINE_A.
Hay2 pares OWNER_B completos,2 primeras confirmaciones con cuerpo completo y0 entradas aceptadas.
Se han usado sus horarios UTC−4, Asia20–00 (5), Londres01–04 (4), y fórmulas fuente3%.

## Escenario congelado antes de outcomes

Checkpoint Git4e070b4. TP±200, SL±0.20 ATR14, mínimo1.5R, riesgo máximo0.25%, nominal<=capital.
Hash del escenario: `6ae03fc0315cf5ad81d4bdb47690518140ebb8f21c6ea1893313f63261e127dc`.
Capital10000 es escala de simulación, NO saldo del propietario. Comisión0.1% por lado como referencia
Spot regular sin descuento; slippage2bps por lado como SUPUESTO, no observado.
[Referencia de tarifas](https://www.binance.com/en/fee/trading). No son las comisiones del usuario ni de Bitunix.
Funding0 pertenece a esta serie SPOT; no se importa a USD-M. SHORT es exposición direccional
hipotética: no hay inventario/borrow verificados y no se afirma ejecución al contado sin ellos.
ATR14 usa el seed SMA de los primeros14 TR de ESTE export y RMA posterior. No hay ATR de TradingView
en el Pine diagnóstico; la equivalencia de su ATR no se ha demostrado. Para estudio largo debe congelarse
un histórico previo amplio con manifiesto/seed, sin seleccionar el warmup por sus resultados.

## Primeras confirmaciones y filtro

| Lado | Vela abre UTC | Disponible al cerrar UTC | Cierre referencia | TP teórico | TP adelantado | SL | R/R neto cierre | Decisión |
|---|---|---|---:|---:|---:|---:|---:|---|
| SHORT | 2026-11-02T12:00:00Z | 2026-11-02T13:00:00Z | 77808.01 | 77117.817000 | 77317.817000 | 77982.507046 | 0.841183 | RECHAZADA, &lt;1.5R |
| LONG | 2026-11-03T13:00:00Z | 2026-11-03T14:00:00Z | 77400.01 | 77886.785300 | 77686.785300 | 77236.200185 | 0.288148 | RECHAZADA, &lt;1.5R |

Los ejemplos de12:00Z/13:00Z se refieren a APERTURAS. Solo son confirmaciones al cierre13:00Z/14:00Z.
Aquí sí aparecen bajo OWNER_B, comprobado por separado; no se ha inferido a partir de PINE_A.

## Primera entrada posterior y secuencia de precio

| Lado | Siguiente apertura de referencia UTC | Precio sin slippage | R/R neto allí | Primer SL (barra UTC) | TP adelantado (barra UTC) | Target original (barra UTC) |
|---|---|---:|---:|---|---|---|
| SHORT | 2026-11-02T13:00:00Z | 77808.0 | 0.841132 | 2026-11-02T13:00:00Z | 2026-11-02T15:00:00Z | 2026-11-02T17:00:00Z |
| LONG | 2026-11-03T14:00:00Z | 77400.0 | 0.288185 | 2026-11-03T14:00:00Z | 2026-11-03T15:00:00Z | 2026-11-03T18:00:00Z |

Las aperturas posteriores existen en los datos, pero OHLC no acredita una cotización ejecutable
tras latencia ni un fill real. Solo permite simular un escenario de apertura+slippage.
Ambas señales YA se rechazaron al confirmar; la revisión de la apertura no las resucita.
**En ambos recorridos se toca SL antes del TP adelantado y del target original.**
Los hitos posteriores son contrafactuales de precio, no operaciones ganadoras.
Se excluye totalmente la vela confirmadora. Los tiempos de hit tienen resolución de barra H1,
conocidos al cierre posterior; no se inventa el minuto/segundo intrabar.
Si una barra toca ambos extremos se aplica SL primero y se marca ambigüedad; los gaps al stop
usan la apertura peor. El horizonte es el siguiente inicio de Asia, ya descrito en el protocolo previo.
El 3-Nov termina la cobertura a20:00Z, antes de caducidad00:00Z; los hits listados sí constan,
pero una ausencia posterior de evento quedaría censurada, no se contaría como fracaso.

## Evidencia e interpretación

2/2 recorridos alcanzan después el target en esta muestra seleccionada; también2/2 tocan primero
el SL propuesto. Ningún porcentaje con n=2 demuestra la hipótesis de que "suele buscar" el target.
Entradas aceptadas0, operaciones maduras0, PnL de operaciones0 porque NO HUBO OPERACIONES.
Win rate, profit factor, drawdown de una estrategia invertida y esperanza: NO ESTIMABLES con0 entradas.
No presentar el capital simulado sin cambios como evidencia de seguridad o edge.

## Siguiente evaluación, sin optimización

GO a preparar historia más amplia y observación prospectiva offline con protocolo/hash fijados,
sin usar estos2 casos para variar horarios, TP200, buffer0.20, 1.5R o costes hasta que pase el filtro.
Registrar TODOS los ciclos, sin señal, descartes, pérdidas, targets no alcanzados y censura.
Mantener por separado entrada al cierre (referencia), primera entrada posterior, escenarios de coste,
fills hipotéticos y targets observados. Para datos intrabar conservar procedencia y resolver cronología
sin usar futuro. El diseño forward no importa estos ejemplos como señales prospectivas.
No se crea ni activa observer; no Railway/Telegram/cuentas/órdenes. Guardian y V8 intactos.

SHADOW ONLY. TRADE AUTHORITY: NONE.
