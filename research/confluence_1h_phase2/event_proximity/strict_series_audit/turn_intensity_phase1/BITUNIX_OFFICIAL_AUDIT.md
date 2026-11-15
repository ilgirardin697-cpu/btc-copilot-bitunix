# Bitunix: documentación oficial y límites de la prueba de estrés

Revisado el 15/11/2026. Solo se efectuaron **dos GET públicos sin firma ni credenciales**. Los cuerpos originales y recibos UTC/SHA256 están en `public_metadata/`. No se consultó ninguna cuenta, posición u orden. Ningún módulo evaluador realiza llamadas de red.

## Qué está verificado actualmente

| Materia | Evidencia oficial | Alcance y limitación |
|---|---|---|
| Tamaño mínimo BTCUSDT | [Trading pairs API](https://www.bitunix.com/api-docs/futures/market/get_trading_pairs.html) y `pairs.json` | Respuesta real HTTP200/code0: `minTradeVolume=0.0001 BTC`, `basePrecision=4`, `quotePrecision=1`; valores actuales, no reglas históricas ni garantía de ejecución. |
| Mantenimiento escalonado | [Position tiers API](https://www.bitunix.com/api-docs/futures/position/get_position_tiers.html) y `tiers.json` | HTTP200/code0: primer tramo nocional0–100000, MMR0.003; siguiente100000–400000, MMR0.004. No se sustituyen por los números de ejemplo de la documentación. |
| Comisión publicada | [Tabla oficial de tarifas](https://www.bitunix.com/service/handling-fee) | Futuros VIP0 maker0.02%, taker0.06%, por lado. No se verificó el nivel personal ni promociones. La investigación mantiene el supuesto conservador heredado de0.10% por lado; no lo presenta como tarifa personal. |
| Base de la comisión | [Explicación oficial de comisiones](https://www.bitunix.com/hub/helpcenter/article/trading-fees-explanation-calculation-bitunix-futures?id=224) | Depende de precio ejecutado × cantidad × tarifa tanto al abrir como al cerrar, no solo del margen. |
| Liquidación | [Reglas y ejemplo oficial](https://www.bitunix.com/hub/helpcenter/article/forced-liquidation-in-futures-trading-and-its-calculation-rules?id=151) | Liquidación parcial/total cuando falta mantenimiento; aislamiento no equivale a stop garantizado. El ejemplo excluye costes/funding y contiene una incoherencia: su expresión numérica conduce a99500 mientras muestra99505. No se resuelve inventando una fórmula propietaria exacta. |
| Funding | [Explicación oficial](https://www.bitunix.com/hub/helpcenter/article/introduction-to-futures-funding-rate?id=79) | Puede alterar el balance; en aislado se cobra primero del balance de futuros y puede alcanzar margen de posición si es insuficiente. Horarios pueden variar. No se impone funding de Binance como si fuera histórico observado de Bitunix. |
| Protección de posición | [Position TP/SL API](https://www.bitunix.com/api-docs/futures/tp_sl/place_position_tp_sl_order.html) | Un TP/SL de posición; dispara cierre a mercado por la cantidad de entonces, con referencia LAST_PRICE/MARK_PRICE. No se llamó ese endpoint. |
| Protección parcial | [TP/SL por cantidad](https://www.bitunix.com/api-docs/futures/tp_sl/place_tp_sl_order.html) | La documentación distingue cantidades TP/SL y ejecuciones MARKET/LIMIT. Un disparo no garantiza fill exacto ni permite suponer una secuencia intrabar desconocida. No se implementa un cliente de órdenes. |

## Aritmética condicional, no simulador certificado de liquidaciones

La ilustración usa `MM = entry × qty × mmr` como en el ejemplo publicado. Si los costes debitados del margen son `C`, el espacio de pérdida es `M − MM − C`; la referencia condicional es `entry − side × espacio/qty`. **No constituye cotización verificable de liquidación**: faltan la trayectoria de mark price, reglas históricas, deducciones por tramo, localización real de cada cargo, reservas y ejecución del proceso de liquidación.

Para equity ilustrativo10000, margen5000,10x, entrada100000 y0.5BTC, el nocional es50000 (5×equity). Con MMR actual0.003 y50 de costes debitados del margen, esa convención da90400 LONG /109600 SHORT. Un stop10% alejado quedaría después de esa referencia. No se afirma que esos precios sean los que devolvería una cuenta Bitunix real.

Una oscilación adversa de5% sobre5×equity implica25% del equity de pérdida bruta, más costes. Pueden perderse los5000 de margen asignado y además existir cargos contra el balance restante. Gaps, liquidez y mark price impiden deducir una pérdida garantizada del precio de stop. No se simulan probabilidades de ruina ni secuencias de liquidación con un modelo no certificado.

## Gestión principal y orden de fases

La gestión principal propuesta reserva1% de equity simulado; dimensiona cantidad desde un stop estructural conocido, costes de ambos lados y reservas explícitas, redondeando hacia abajo. No usa50% de margen como presupuesto de pérdida. Un gap o funding superior a la reserva puede superar esa pérdida planificada.

`risk_stress.py` y su CSV son **aritmética ilustrativa**, no operaciones históricas ni evidencia de una estrategia. Stop estructural exacto, TP1, break-even neto y trailing no están congelados: la Fase2 queda bloqueada hasta resolver Fase1 y aprobar su especificación independiente. No se prueban variaciones para rescatar los resultados de entrada.

**SHADOW ONLY · TRADE AUTHORITY: NONE.**
