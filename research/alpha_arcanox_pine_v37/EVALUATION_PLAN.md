# Siguiente evaluación histórica y prospectiva — preparada, no activada

La paridad matemática pasa en33 filas/2 pares reales PINE_A. Permite investigar
la hipótesis OWNER_B; NO acredita edge ni ejecución segura. Los64 registros
seleccionados por el propietario son ejemplos exploratorios ya vistos, nunca
holdout ni observaciones forward. Los dos eventos OWNER_B de esta ventana no
se usan para escoger parámetros.

## Hipótesis fija y dos preguntas separadas

Hipótesis descriptiva: tras la primera vela H1 cuyo CUERPO completo queda fuera
del rango OWNER_B, ¿visita posteriormente el precio el target proyectado?

Hipótesis operativa PAPER: después de esa confirmación y de una primera entrada
posterior, ¿produce el TP adelantado200 frente al SL estructural0.20 ATR14 una
expectativa neta defendible después de costes y del filtro1.5R?

No son equivalentes. Los dos ejemplos revisados llegan después al target,
pero antes al SL. Ambos se rechazaron por R/R neto: no se contabilizan como
operaciones ganadoras, perdedoras realizadas ni beneficios.

## Parámetros que se conservan

OWNER_B: UTC−4 fijo; Asia20–00 incluidas, Londres01–04 incluidas; las cuatro
fórmulas Pine3%; solo primera confirmación del par; LONG min(O,C)>HIGH,
SHORT max(O,C)<LOW; TP_SUPERIOR−200/INFERIOR+200; SL_HIGH−0.20 ATR14 /
LOW+0.20 ATR14; mínimo1.5R neto; riesgo simulado máximo0.25% y nominal<=cash.
No usar niveles A en B, ni cambiar un rechazo a aceptación buscando otra vela.
No añadir filtros de indicadores, overrides de confirmación ni offsets nuevos.

La caducidad y convención stop-first conservan el protocolo previo. El rango
se conoce tras Londres; la confirmación solo al cierre de la vela ajena.
La propia vela confirmadora nunca sirve para acreditar un TP/SL posterior.

## Historia: pasos antes de medir resultados amplios

1. Congelar fechas, fuente Spot BTCUSDT que corresponda al ticker, scripts y
   hashes antes de descargar/evaluar outcomes. No usar el fixture USD-M previo
   como sustituto Spot; una investigación USD-M requeriría dataset/protocolo
   separado, con funding real. No prometer un holdout histórico virgen.
2. Incorporar un prefijo OHLC amplio de warmup ATR con fecha inicial fija,
   validar contigüidad H1 y SHA256. La revisión64 usa el seed de sus primeros14
   TR: no presume reproducir ATR14 calculado con todo el historial TradingView.
   No escoger duración de warmup según rentabilidad o si cambia un rechazo.
3. Congelar tabla de costes y escenarios antes del estudio. La revisión actual
   usa referencia Spot regular0.1%/lado y slippage2bps/ lado predeclarados, no
   comisiones de la cuenta. No bajarlos para que estos dos ejemplos pasen1.5R.
4. Registrar TODOS los ciclos y clasificar completos, incompletos, sin señal,
   primera confirmación, rechazo al cierre, rechazo en apertura posterior,
   entrada hipotética, SL, TP, timeout y censura. Sin selección manual de días.
5. Entrada al cierre se conserva como referencia, nunca fill garantizado.
   Usar primera apertura posterior con escenario de ejecución adversa; si se
   desea resolución adicional, preregistrar y conservar datos intrabar públicos.
   Los OHLC H1 actuales no prueban una cotización realmente ejecutable tras
   latencia. SHORT en Spot sin inventario/borrow sigue siendo exposición
   direccional hipotética, no un producto ejecutable sin préstamo.
6. Medir hitos separados: franja500, TP adelantado200, target exacto, SL, y
   cronología stop/TP. Un target posterior a SL nunca genera beneficio del trade.
7. Informar bruto/neto, fees/slippage/funding aplicable, R, drawdown, exposición,
   MAE/MFE, duración, frecuencia, rechazo por motivo, LONG/SHORT, meses y tipos
   de cajas. Sin entradas aceptadas, expectativa/PF/win rate no son estimables.
8. Incertidumbre mediante bloques semanales y estabilidad temporal; evitar
   contar varias confirmaciones persistentes como trades independientes.
   Un control con close-only debe mantener las MISMAS sesiones y niveles B:
   comparar A contra B cambia varias cosas a la vez y no aísla el efecto cuerpo.
   Este es un control estadístico, no una nueva regla de trading.

No se ha lanzado aquí un backtest masivo ni un proceso continuo. `paper_review`
prepara y prueba el motor acotado de revisión de la muestra recibida, con
revalidación de primera apertura, SL-first en ambigüedad, gaps adversos y censura.

## Prospectivo: activación futura independiente

Solo tras revisión se fijará timestamp REAL futuro y commit/hash del protocolo.
Se empezará con la siguiente Asia completa posterior; el historial previo será
warmup y no señales forward. Dataset/journal propios de research, append-only,
IDs deterministas por par, snapshot de condiciones y registros de outcome
posteriores a su maduración; reinicios no reescriben ni duplican señales.
No compartir, modificar o refreezar BITMAN_WEEKLY_FORWARD_V1.

Registrar cambios adversos, datos faltantes, rechazos y campañas sin señal.
La interpretación de la evidencia seguirá siendo manual; ningún N automático
validará la hipótesis. Ni el protocolo ni un resultado PROMISING concederían
autoridad para órdenes, Guardian, V8, Telegram o producción.

SHADOW ONLY. TRADE AUTHORITY: NONE.
