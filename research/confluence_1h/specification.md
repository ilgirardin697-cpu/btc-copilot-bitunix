# I-GOD Confluencia 1H V0 — reglas antes de resultados

SHADOW ONLY. TRADE AUTHORITY: NONE. El protocolo ejecutable es `protocol.json`.
Se congela en Git antes de descargar el dataset/evaluar outcomes. No se elige
un ganador entre 2R y 3R ni entre vecinos de sensibilidad.

Fuente principal: BTCUSDT Binance USD-M perpetual, 01/11/2022–31/10/2026
inclusive; septiembre–octubre 2022 solo warmup. Elegimos el contrato público
para investigar LONG y SHORT con funding explícito, no simular ventas Spot
como si fueran futuros. No representa Bitunix. Datos y checksums oficiales.

Las reglas de coincidencia son las del paquete adjunto, no una interpretación
posterior más permisiva: cruce tendencia/EMA15 del Koncorde con signo previo,
caída ADX pasada desde >40, AO al otro lado de cero con dos pendientes en la
dirección esperada y BBWP >85. DMI se registra pero no filtra la dirección.
El ADX no demuestra por sí mismo reversión ni un suelo actual.

El BBWP adjunto devuelve un **índice** mediante binary_search_rightmost.
En empates devuelve el índice del último igual, no el número de muestras <=.
Conservamos esa semántica literal y documentamos la diferencia con el ZIP.
No se cambian los indicadores congelados de I-GOD para hacerlo.

Entrada a apertura posterior, ATR conocido del cierre de señal, SL 1,5ATR,
TP 2R/3R, salida después de 24 velas completas a la siguiente apertura.
Comisiones 0,1% por lado y slip adverso 0,05% por lado son supuestos fijados.
Funding histórico separado; no tarifas autenticadas ni fills garantizados.
Una sola posición, capital inicial 200 USDT y nominal más fee <= equity.
El 1% es riesgo proyectado al stop, no garantía frente a gaps/funding futuro.

70/30 cronológico con purga y embargo; cuatro ventanas expansivas sin ajuste;
controles aleatorios por mes/dirección/régimen; sensibilidad de un factor sin
selección. Todo histórico puede haber sido visto en otras investigaciones:
**NO VIRGIN HOLDOUT**. El incidente del 15/11/2026 02:00 Madrid es una
observación post-hoc separada. No se incorpora a la evaluación principal.

Sin logs/exportaciones reales del Pine nuevo, solo podemos acreditar traducción
matemática y pruebas locales; compilación y paridad TradingView siguen pendientes.
Ningún resultado histórico de este estudio basta para EDGE DEMOSTRADO.
