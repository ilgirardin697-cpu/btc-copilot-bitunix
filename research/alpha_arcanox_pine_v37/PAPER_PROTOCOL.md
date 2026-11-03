# Protocolo candidato PAPER — no activado

Actualización de evidencia:64 logs reales permiten comprobar33 filas/2 pares
PINE_A, sin inyectar el primer ciclo incompleto. GO para evaluación OFFLINE.
La revisión acotada OWNER_B fija su escenario en `OWNER_B_REVIEW_SPEC.json`
(checkpoint4e070b4); no cambia las reglas siguientes ni activa observación
forward. Ver `EVALUATION_PLAN.md` y los resultados separados de ambos perfiles.

SHADOW ONLY. TRADE AUTHORITY: NONE. Requiere revisión independiente y logs
TradingView reales antes de congelar su hash/fecha de activación. Este documento
no otorga permiso de ejecución ni integra un observer.

## Especificación previa

- Reportar PINE_A y OWNER_B por separado. A evalúa confirmaciones y objetivos
  del indicador, sin atribuirle una estrategia de riesgo inexistente. B evalúa
  la primera confirmación del par con las reglas expresas del propietario.
- Sin variar sesiones, insets 3%, ATR14, buffer 0.20, TP advance 200, 1.5R o
  riesgo 0.25% después de consultar outcomes. No probar offsets alternativos
  ni seleccionar el mejor perfil por el resultado final.
- Elegir y congelar venue/ticker ANTES del análisis: BTCUSDT USD-M y Spot son
  datasets independientes. Sus OHLC no se sustituyen ni se mezclan.
- Rango congelado tras Londres; cierre H1 confirma. Caducidad para señales:
  siguiente inicio de Asia. La primera confirmación consume la oportunidad B
  aunque riesgo la rechace. Registrar días sin par y sin confirmación.
- Entrada teórica al cierre es SOLO referencia. Entrada simulable = primera
  apertura posterior disponible con latencia/slippage predeclarados. Si allí
  TP adelantado/SL/RR no son válidos, registrar rechazo, nunca fill retroactivo.
- SL y TP congelados al confirmar. No ampliar SL. B usa TP adelantado; el
  target original y la franja de500 se registran como hitos separados, nunca
  como ganancias realizadas. Stop/TP mismo intervalo: resultado adverso primero,
  salvo secuencia intrabar pública causal y comprobable para resolverlo.
- Salida temporal propuesta FIJA: cierre de la barra inmediatamente anterior
  al siguiente inicio de Asia; una única exposición B simultánea. Es una regla
  de simulación añadida, NO del Pine. Congelarla antes de ejecutar el estudio.
- B: máximo0.25% de capital simulado por exposición incluyendo costes al stop;
  nominal <=cash simulado. Sin apalancamiento ni capital infinito. Si existe
  exposición previa o caja insuficiente, registrar rechazo por solapamiento/capital.
- Comisiones: tabla pública/versionada de la venue con fecha; escenarios de
  slippage predeclarados. Funding USD-M: liquidaciones históricas reales en
  timestamps de exposición; si faltan, marcar NO EVALUABLE, no cero silencioso.
  No usar las comisiones de Bitunix para simular la venue Binance.

## Registro completo y prospectivo

Conservar dataset RAW público, manifest SHA256, gaps, normalización de tiempos
y data_cutoff. Solo H1 cerradas; warmup suficiente para ATR con seed explícita.
Si hay huecos, el rango afectado no genera aceptación. Nada de rellenar OHLC.

Registrar por ciclo y perfil: sesiones incluidas y disponibles, cuatro extremos,
amplitud, caja elegida por anclaje, alturas, insets, anclajes, cuatro niveles,
confirmación/vela/available_at, body/close, ATR, lado, todas las razones de rechazo,
entrada teórica y primer precio simulable, SL, target teórico, TP adelantado,
costes/funding, R/R antes/después de coste y ejecución, cantidad, capital.

Registrar después: MAE/MFE, tiempo a cada hito (franja/target/TP adelantado),
stop/timeout, resultado bruto y neto, R, drawdown, duración y ambigüedades.
Nunca descartar perdedoras ni días sin señal. IDs deterministas para evitar
contar la misma vela de confirmación varias veces. Cada outcome tiene su
timestamp de maduración; no se actualiza una señal original retrospectivamente.

Una futura observación forward comenzará con timestamp real/commit/hash de
reglas y journal append-only NUEVO. Warmup anterior no es señal forward.
Reinicios no reinventan señales ni reinician capital. No reutilizar el journal
BITMAN_WEEKLY_FORWARD_V1 ni sus identificadores/protocolo.

## Evaluación y controles

No hay holdout virgen garantizado: septiembre y los históricos previos ya se
han visto. Declarar los tramos reutilizados. Separar desarrollo/verificación
de fórmula, evaluación cronológica congelada y periodo prospectivo aún no visto.
Embargo mínimo una sesión/ciclo entre splits, acorde al máximo holding anterior.

Reportar TODOS los ciclos, confirmaciones por lado, descartes por motivo, fills
simulables, target exacto/franja/TP adelantado por separado, bruto/neto, win rate,
expectativa neta/R, profit factor, drawdown, exposición, MAE/MFE y duración.
Resultados mensuales/anuales, LONG/SHORT, DST y tipo de cajas. Comparar por
fechas/lados con ruptura simple del mismo rango, y B con/sin filtro1.5R, sin
presentar el control como una regla nueva validada.

Incertidumbre: bootstrap por bloques de semanas y sensibilidad de costes
predeclarada, sin escoger escenarios rentables. Mostrar n e intervalos amplios;
ningún N automático acredita rentabilidad. Conclusiones: NO EDGE, INCONCLUSIVE
o PROMISING FOR FORWARD VALIDATION. Ninguna permite operar en real.
