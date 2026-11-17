# TRADINGONE_V2 — reproducción offline de fuente y ajustes activos

Referencia exclusiva: los seis scripts activos y sus inputs del JSON TradingOne2.3.21, SHA en `profile.json`. No se usan defaults cuando existe input activo. No se modifica el indicador original, el bot ni los estudios anteriores.

Mercado público Binance Spot BTCUSDT H1. AO HL2 5/34; ADX14/14; Koncorde público con pececillos, tendencia, tiburones y roja EMA15(tendencia); BBWP CLOSE/SMA13 con ranking literal previo252 y señal SMA5; ML RSI LOW27/ALMA4/sigma1/offset0 con arrays y semántica del original BackQuantV5; TSA119/2.8 y restantes inputs activos. Las áreas ocultas se calculan, pero no se inventa que estén visibles.

El caso16–17Nov es diagnóstico previamente observado. No se eligen parámetros por sus movimientos. No hay backtest de rentabilidad, órdenes, entradas, TP/SL o selección de variantes.

Se fija un corte de velas cerradas17Nov19UTC antes de solicitar mercado;17Nov estará incompleto. Se guardan bytes originales, parámetros, timestamps y hashes. Se descarga un máximo de3200H1 cerradas y se separa la única vela pública aún abierta como provisional. No se rellena ningún hueco.

La ventana principal controla la hipótesis de que3200 barras incluyen una abierta:3199 cerradas y `last_bar_index=3199`. El JSON no contiene su prefijo real; esta inicialización NO queda certificada. Se compara también una barra adicional de calentamiento, sin escoger el ajuste que mejor encaje.

Se distinguen:

- Carga/reload con `last_bar_index` fijo conocido al cargar. El gate original ML RSI depende de ese índice; una recarga puede cambiar el histórico dibujado.
- Sesión iniciada causalmente antes del16NovMadrid, luego append por cierre, sin eliminar el array persistente. Nunca se finge que la historia recargada son predicciones emitidas entonces.
- Actualización provisional del último H1 desde un GET real del mercado, separada de confirmados. La previsualización no confirma ni altera estado. No es una observación del motor TradingOne.

Se auditan pendientes, cambios de pendiente, cruces y colores de cada serie. ADX y BBWP siguen sin proporcionar dirección de precio por sí solos. La comparación matemática con I-GOD utiliza las MISMAS velas Spot; no se la presenta como lectura del bot desplegado, que puede usar otra venue o timeframe.

La fidelidad al código no certifica los built-ins ni el intérprete externo: arrays/NA, percentiles, redondeos/gradientes, `fixnan` y HMA5 deben contrastarse contra valores reales de TradingOne. Se conserva la literalidad del original; no se importa ni se sustituye por una versión OPT.

SHADOW ONLY. TRADE AUTHORITY: NONE.
