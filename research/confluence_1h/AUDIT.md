# Auditoría del paquete y fuentes originales

Las fuentes recibidas se conservan sin modificar. El ZIP **no** se aceptó como
una implementación correcta por defecto. No se ejecuta su optimizador.

## Repositorio: cálculos reutilizables y límites

| Componente existente revisado | Reutilización razonable |
|---|---|
| `bitman_manual/frozen/indicators.py` | AO5/34, Wilder RMA, ATR14 y tendencia pública Koncorde como referencia matemática; su BBWP no tiene la misma convención de empates que el adjunto |
| `bitman_manual/frozen/core.py` | Alineación causal y régimen SMA200 del último4H cerrado; no se usa su decisión como una entrada nueva |
| `bitman_manual/frozen/market.py` | Validación y agregación de bloques completos, sin imputación |
| `guardian_signals.py` | Contraste ATR14 y separación de pivote/instante de confirmación; no se ejecuta su cliente ni se añade ML RSI al experimento |
| `main.py` Manual Copilot | Arquitectura de análisis/representación separada de permisos; sus parámetros no se importan como reglas de esta estrategia |
| `trend_v8.py` y referencias V8 | Closed-candle/estado/idempotencia como garantías existentes; no se reutilizan señales o ejecución V8 |
| `research/early_breakout_artifacts/EARLY_BREAKOUT_RESULTS.md` | Evidencia negativa NO EDGE; no se adoptan sus parámetros elegidos como edge |

Se hace inventario de los módulos productivos mediante AST y hashes, además
de revisar las fórmulas relevantes. Esto no se presenta como una nueva auditoría
operativa de una cuenta o del estado desplegado en Railway. No se leen secretos,
posiciones privadas ni órdenes. El port queda aislado bajo research para no
cambiar kernels congelados que tienen convenciones de arranque/ranking propias.

## Fórmulas verificables y alcance

| Cálculo | Fuente adjunta / port auditado | Hallazgo |
|---|---|---|
| Precio Koncorde | OHLC4 para RSI/BB/Stoch; HLC3 para MFI | No usar close para todos |
| RSI14 | RMA de subidas/bajadas, semilla SMA | Ratios matemáticamente indefinidos quedan desconocidos; el ZIP asigna valores artificiales en casos planos |
| MFI14 | Money flow HLC3×base volume por signo de cambio | Mismo n14; no flujo de cuentas/ballenas observado |
| BB Koncorde | (OHLC4−SMA25)/(4×STD poblacional25)×100 | BB mult2; no STD muestral |
| Estocástico | (OHLC4−low21)/(high21−low21)×100, SMA3 | El divisor3 vuelve a entrar en la mezcla original |
| Tendencia | (RSI+MFI+BB+Stoch/3)/2 | Es la serie cruzada, no las capas PVI/NVI |
| Señal roja | EMA15(tendencia) | Semilla primer valor válido |
| PVI/NVI | Cambios relativos close condicionados a volumen, EMA15, min/max90 | Inicio1; capas calculadas, no filtros añadidos |
| AO | SMA5(HL2)−SMA34(HL2) | Pendiente y signo son distintos |
| DMI/ADX | len14 y suavizado14, Wilder RMA | DMI TR inicial desconocido; ATR permite primer high−low; DI inicial del ZIP difiere, ADX prácticamente igual |
| ATR14 | RMA(TR), primer high−low | Distancia del stop fijada en señal |
| BBWP | close/SMA7, width2×STD/SMA; previas100, current excluida | Puerto literal de la búsqueda por índice, no conteo inclusivo en empates |

Se revisaron los defaults calculados de las fuentes. Las numerosas medias
opcionales, paneles y alertas del Koncorde no se presentan como implementadas
ni se conectan a la estrategia. Los headers MPL-2.0 y atribuciones se conservan.

### Diferencia BBWP demostrable en la especificación pública

`array.binary_search_rightmost([4,5,5,5],5)` devuelve3: índice del último igual.
Un conteo de valores<=5 devuelve4. La fuente multiplica el índice por100/n.
No son el mismo estimador. Si no hay igualdad, devuelve la posición del primer
elemento mayor. Además, la fuente empieza a insertar en bar_index>=7, no en6.
La primera división con array vacío es desconocida, no una observación válida.

[Referencia oficial TradingView](https://www.tradingview.com/pine-script-reference/v6/#fun_array.binary_search_rightmost).

La diferencia persiste en8 barras después del warmup del dataset; máximo global
incluyendo arranque50 puntos. No cambia ninguna señal completa en esta muestra.
No se altera el BBWP congelado de Bitman, que usa otra convención de empates.

### Diferencias numéricas y niveles de evidencia

`artifacts/indicator_audit.json` conserva máximos por campo y disponibilidades:
el port escalar independiente local pasa AO, ATR, ADX/DI, RSI, MFI, BB,
estocástico, tendencia, EMA y BBWP. Las pequeñas diferencias de tendencia
frente al ZIP (máximo~4,14e-7) son de aritmética rolling/STD; no se fuerzan valores.
Las diferencias DI iniciales son de semilla, no de cambio de parámetros.

Esto es una **verificación matemática local**, no compilación/ejecución Pine.
No existen nuevos registros TradingView proporcionados para estos indicadores.
No se declaran valores equivalentes en una plataforma real sin esa prueba.
El comparador `compare_pine.py` exige ticker perpetuo correcto, parámetros,
H1, timestamps y OHLCV coincidentes; no admite Spot como la misma serie.

## Condiciones ensayadas

LONG: tendencia cruza EMA15 al alza con tendencia previa<0; AO<0 y dos cambios
ascendentes; ADX[t−1]<ADX[t−2], ADX[t−2]>40; BBWP>85.

SHORT: cruce inverso con tendencia previa>0; AO>0 y dos cambios descendentes;
mismo ADX pasado y BBWP. DMI **no** determina dirección en esas reglas.
ADX descendente por sí mismo no es SHORT. No hay búsqueda de coincidencias
dentro de una ventana de varias velas: todos los gates deben coincidir en t.

El nombre `adxTurn` del ZIP es engañoso: no exige giro actual al alza, ni un
techo confirmado. Se conserva la condición exacta y se renombra descriptivamente.
No se inventa una nueva estrategia para capturar el rebote del15/11.

## Lookahead y motores de simulación

- Todas las señales se conocen al cierre; primera entrada modelada en apertura
  posterior. No se usan high/low futuros para tamaño, stop, filtro o señal.
- Señales se conservan aunque una posición ya esté abierta; el ledger registra
  por qué no sería una nueva operación. Una sola posición por libro.
- SL/TP anclados al fill simulado. Tamaño usa la referencia de apertura y slip
  supuesto; no representa un market order con fill real garantizado.
- Gaps contra stop se llenan adversamente. Doble toque H1 sin orden conocido:
  stop primero. Apertura ya fuera del target se procesa antes de wicks posteriores.
- Tiempo24H: el ZIP usa el cierre de la barra24; el port usa la siguiente
  apertura, sin afirmar un fill conocido solo después del cierre.
- Pine original usa slip3000 ticks, no0,05% variable; redondea distancias a ticks
  y calcula qty al cierre previo. No puede prometer igualdad de operaciones con
  Python. El Pine nuevo es **diagnóstico**, sin strategy.* ni alertas.
- El motor original no descuenta entry fees mientras la operación sigue abierta
  en su curva MTM; el port sí. El DD incluye initial equity como primer pico.
- El comparador opcional backtesting.py del ZIP ancla brackets al cierre y usa
  otro spread/time exit. **No ejecutado** como prueba de paridad: no sería exacto.
- El selector `_choose` de18 combinaciones del ZIP no se ejecuta. Aquí no se
  seleccionan umbrales ni un TP ganador, ni se reutiliza NO EDGE de Early Breakout
  como señal positiva.

## Datos, temporalidad y riesgo

Binance USD-M y Bitunix son venues distintas. No se accede a cuentas privadas.
Se verifica cada archive y checksum oficial; no se repara un gap con interpolación.
Los archivos actuales pueden contener revisiones: no hay publicación histórica
point-in-time independiente ni holdout virgen.

Regímenes: último cierre4H confirmado frente a SMA200, convención causal ya
usada por el engine congelado. No se usa futuro para etiquetar bull/bear.

Las comisiones y slips son supuestos pedidos, no costes de cuenta verificados.
Funding rates públicos y marcas exactas faltantes están explícitos; las cotas de
mark no son fills ni liquidaciones verificadas. Sin apalancamiento multiplicativo,
pero no se afirma que el contrato real carezca de reglas de margen/liquidación.
Faltan filtros históricos de tick/lot/minimum notional, profundidad y latencia.

## Aislamiento y protección de investigaciones anteriores

El laboratorio únicamente importa módulos estándar, NumPy/Pandas/Matplotlib y
requests público. Ningún runtime productivo importa `research.confluence_1h`.
Los tests verifican hashes de151 archivos base; Guardian, V8, ML RSI, readiness,
market-data, sender y protocolo semanal no cambian. No se tocan PR41–45.

Pruebas sintéticas validan invariantes, nunca rentabilidad o señales forward.
La suite de Python3.13 detectó dos hashes AST distintos; ambos fallan también
en la base9d40020 intacta. Son dependencias del formato AST de Python, no permiso
para refreezar. Se repite la validación con Python3.12, versión de CI.

SHADOW ONLY. TRADE AUTHORITY: NONE.
