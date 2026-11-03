# OWNER_C_STRESS_40X_NO_SL — evaluación bloqueada

**INCONCLUSIVE / BLOCKED_NOT_EVALUABLE. No se han fabricado liquidaciones, PnL,
drawdown o probabilidades de ruina. Campos numéricos históricos: null, no0.**

## Escenario solicitado, separado de OWNER_B

Se conservan sesiones, fórmulas, cuerpo completo, primer evento y TP±200. No SL
voluntario y NO filtro1.5R. Capital inicial10000 solo escala; cada operación
utilizaría margen inicial del50% del equity restante, 40x, aislado sin auto-add.
Cross sería una corrida independiente, con toda la cuenta respaldando una única
posición. No se abren otras mientras una siga activa; los ciclos se registran
como POSITION_ACTIVE. Sin aportaciones externas ni reset después de pérdidas.

Un stop voluntario ausente no impide liquidación. El fin de datos censuraría
una posición abierta con su pasivo/MTM, no la declararía ganadora o inmortal.
El escenario no se ha ejecutado porque falla el gate de procedencia/riesgo.

## Exchange elegido y motivo exacto del bloqueo

Candidato: Binance USD-M BTCUSDT, distinto de la serie Binance Spot usada para
señales. La liquidación depende del MARK y del margen de mantenimiento vigente,
no del último precio Spot. Los precios Spot no se usan como proxy del mark.

No se dispone de una tabla oficial VERIFICADA con vigencias completas de tiers,
maintenance amounts, límites de40x y reglas/comisiones de liquidación para
2025-11→2026-10. La API oficial de leverage brackets es USER_DATA firmada y
devuelve brackets del usuario actuales, no una historia completa con vigencias.
No se solicitaron credenciales ni se llamó a cuentas privadas. Una tabla actual
o el anuncio de2021 no demuestra que los tiers fueran esos durante todo el año.

Existen fuentes públicas oficiales de mark/trades/funding, pero no se descargan
para producir resultados falsamente exactos mientras el requisito anterior falla.
Además harían falta: sincronización intrabar trade/mark, funding real y su mark,
fee/clearance rules, lot/min-notional, modo de cuenta y resolución TP/liquidación.
Si ambos eventos estuvieran en el mismo intervalo sin secuencia fiable, el caso
seguiría ambiguo. No asumir liquidation=1/40 ni que28 SL de B equivalen a28
liquidaciones C. Tampoco106 visitas Spot al target equivalen a106 TP apalancados.

Fuentes oficiales:

- [Brackets (USER_DATA)](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/account).
- [Liquidación y mark](https://www.binance.com/en-KZ/support/faq/detail/360033525271).
- [Ejemplo oficial de cambio de tiers,2021](https://www.binance.com/en/support/announcement/detail/f55d25695ca8453ab4c132c1fd4dc36a).

## Lo que sí puede calcularse sin inventar un modelo de exchange

40×50% del equity = nominal20 veces el equity. Con equity10000, margen5000
y nominal200000, un movimiento adverso del1% implica−2000 de PnL bruto,
un20% de la cuenta, antes de costes. Una comisión r cuesta20r del equity por lado.

Ignorando mantenimiento, fees y funding, agotar el margen aislado corresponde
a un movimiento adverso bruto del2.5%; agotar toda la cuenta con esa misma
posición cross,5%. **Son distancias algebraicas de insolvencia bruta, NO precios
de liquidación.** Mantenimiento y costes cambian el umbral y pueden activarlo antes.

Si hipotéticamente cada pérdida consumiera exactamente50% del equity total:

| Pérdidas hipotéticas50% | Equity restante de10000 |
|---:|---:|
|0|10000|
|1|5000|
|2|2500|
|3|1250|
|5|312.50|
|10|9.765625|

Esta tabla recalcula desde capital restante y no es una simulación histórica de
liquidaciones, no incluye fees y NO asigna probabilidad. La probabilidad de ruina
no puede inferirse ni de esta identidad ni de un único camino histórico sin
definir modelo y costes. El cierre práctico por mínimos de negociación también
requeriría las reglas verificadas del contrato.

## Comparación solicitada

| Métrica | OWNER_B Spot, escenario sin apalancamiento | C aislado40x | C cross40x |
|---|---|---|---|
|TP / liquidaciones|6 TP PAPER de 36 operaciones; liquidación no aplica al modelo B sin apalancamiento|NO EVALUABLE|NO EVALUABLE|
|PnL neto / drawdown MTM1m|-298.8466 USDT / 3.3268%|NO EVALUABLE|NO EVALUABLE|
|Riesgo de ruina|No inferir garantía de la muestra B|NO EVALUABLE|NO EVALUABLE|

El modelo C queda bloqueado, separado y sin botón, runner o integración. No se
ha suavizado el gate ni sustituido mark por Spot para conseguir una tabla numérica.

SHADOW ONLY. TRADE AUTHORITY: NONE.
