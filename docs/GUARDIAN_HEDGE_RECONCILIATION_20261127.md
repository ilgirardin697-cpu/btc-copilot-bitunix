# PR61 — reconciliación HEDGE/CROSS de solo lectura, 27/11/2026

Revisión del HEAD auditado `e50f3680fd0866322fd1ef310a4356bcbaf2580e`, en la misma PR y rama. **No activado, no desplegado.** Ninguna orden, cambio de variables, credenciales, volumen, campaña o journal financiero. V8 y el ejecutor/protector de Guardian permanecen intactos. Las comprobaciones del 26/11 se conservan como evidencia de ese día.

## 1. PnL: hecho observado y causa todavía no certificada

Tres secuencias GET originales del 27/11/2026, 10:05:04.711–10:05:17.666 UTC; ocho respuestas por secuencia. Los originales están fuera de Git, con ACL restrictiva, sin cabeceras de autenticación ni credenciales; se comprobó el SHA256 de las 24 respuestas antes del análisis offline. El JSON adjunto contiene solo tiempos, conteos, hashes y comparaciones, sin IDs ni balances.

| Captura | Duración | Tamaño/entrada/costes y componentes de saldo estables | PnL flotante de cuenta cambió | Cuadre CROSS exacto | PnL de ambos lados implica el mismo mark |
|---|---:|---|---|---|---|
| 1 | 2,861 s | Sí | Sí | No | Sí |
| 2 | 2,355 s | Sí | Sí | No | Sí |
| 3 | 3,723 s | Sí | Sí | No | Sí |

La lista completa solicitó cuenta principal, todas las posiciones USDT y ambos libros de órdenes BTCUSDT. Devuelve dos IDs distintos, HEDGE/CROSS, LONG y SHORT. El saldo sin PnL, cantidades, entradas, realizado, comisiones y funding permanecieron estables en cada secuencia. El PnL aislado sí cuadra (sin posiciones aisladas en las capturas); el CROSS no cuadra exactamente.

Como diagnóstico de contratos lineales, se calculó `mark_implícito = entrada + signo × unrealizedPNL / cantidad`. Los dos lados producen exactamente el mismo mark en cada captura. Ese mark coincide con el ticker inicial en una captura y con el final en las otras dos. En cambio, el mark implícito del PnL agregado de cuenta queda fuera del intervalo entre esos dos marks muestreados en las tres capturas; tampoco coincide exactamente con el last inicial/final. En dos capturas cae dentro del intervalo de last, lo que es compatibilidad parcial, no prueba de la referencia usada.

La diferencia tampoco es exactamente la suma de fees, funding o realizado. **No queda demostrado que la causa sea solo latencia**, ni que `crossUnrealizedPNL` deba corregirse con esos conceptos. Dos precios muestreados no delimitan todo el recorrido intermedio y REST no ofrece aquí un identificador de snapshot atómico. No se ajustaron cifras ni se agregó tolerancia, redondeo o sustitución por PnL recalculado. AMBIGUOUS_POSITIONS permanece sin recuperación: la condición sigue siendo dos lecturas completas distintas con cuadre exacto. Si Bitunix no ofrece una explicación/lectura sincronizada, se conserva esta limitación.

La [API de posiciones](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html) documenta el PnL realizado separado de fees/funding y el flotante por posición; no publica un contrato de sincronización con el agregado de cuenta. `mtime` es última modificación de posición, no timestamp certificado del mark usado para el flotante. Una explicación adicional del exchange debe precisar esa sincronización o referencia; no se contactó a terceros ni se cambiaron preferencias de la cuenta.

## 2. Componentes de cuenta, sin doble contabilización

La [API de cuenta](https://www.bitunix.com/api-docs/futures/account/get_single_account.html) distingue disponible, fondos bloqueados en órdenes (`frozen`), margen bloqueado de posiciones (`margin`) y flotante CROSS/aislado. Documenta `available + crossUnrealizedPNL` para la capacidad máxima de apertura; esto **no es** un permiso para abrir ni una medida de capital protegible. `transfer` es transferible, no otra partida a sumar.

| Magnitud mostrada | Tratamiento |
|---|---|
| `available`, `margin`, `frozen` | Campos informados de una cuenta USDT, mostrados por separado; no se replica el margen de cuenta por cada lado |
| `available + margin + frozen` | Componente derivado de saldo según la partición documentada, sin sumar otra vez los márgenes de las posiciones |
| `crossUnrealizedPNL`, `isolationUnrealizedPNL` | Se muestran como informados; se comparan exactamente con sus respectivas posiciones |
| Equity por componentes | Suma anterior más ambos flotantes una vez; **estimación no certificada**, porque este REST no devuelve un campo equity autoritativo ni snapshot atómico |
| Realizado, fees y funding | Se muestran separados; no se vuelven a añadir/descontar de los componentes de saldo/equity |

Se conserva la fórmula anterior, pero su condición de estimación queda explícita en el modelo y `/risk`. Bonus distinto de cero sigue sin reconciliación admitida. No se ajustó el equity para hacer cuadrar el PnL y no se usa este módulo para asignar presupuestos o ejecutar protección. Los tests incluyen diferencias de 0,000000001 USDT: siguen siendo descuadres.

## 3. Liquidación CROSS del SHORT

Las dos referencias positivas devueltas están por debajo de ambos marks observados, y **son diferentes entre sí**. La exposición neta BTC de las capturas tiene signo positivo: una caída empeora el flotante agregado aunque favorezca al SHORT aislado. Esto es compatible con dependencia de cuenta; no valida las dos fórmulas concretas del exchange.

Bitunix documenta [colateral compartido en CROSS](https://www.bitunix.com/hub/helpcenter/article/futures-margin-modes-cross-margin-vs-isolated-margin?id=155) y [cálculo conjunto del margen en Cross Multi-Trade](https://www.bitunix.com/hub/helpcenter/article/how-to-use-the-multi-trade-feature-on-bitunix-app?id=220). No basta para reconstruir por nuestra cuenta las referencias HEDGE, los tiers o el procedimiento de liquidación. No se afirma tampoco que la cuenta tenga Multi-Trade activado solo por disponer de dos lados HEDGE.

Cada valor se conserva por positionId como `CROSS_ACCOUNT_REFERENCE`, con alcance/liquidación global no certificados. No se declara que el SHORT esté ya liquidado, ni se inventa un único precio global, ni se acepta/rechaza su SL comparándolo con una frontera de liquidación aislada. La regla del 2% del protector productivo no se toca; el lector conserva el aviso de proximidad absoluta como referencia observacional. En ISOLATION permanece la comprobación direccional existente. El límite estático de alcance CROSS queda en el panel/log, no genera mensajes rutinarios por sí solo; una proximidad crítica real o pérdida de cobertura sigue notificándose.

## 4. Frescura del ticker y de la captura

El lector anterior obtenía el ticker antes de la segunda lectura de posiciones, órdenes y cuenta. En las tres capturas de diagnóstico, el ticker inicial tenía 2,05–2,88 segundos al finalizar. No es un snapshot atómico ni prueba un fallo del feed, pero no convenía presentarlo como la última referencia.

Ahora la secuencia es cuenta/posiciones/ticker inicial, ambos libros de órdenes, segunda lectura de posiciones y de ambos libros, cuenta final y **ticker final nuevo**. El dato final se usa para exposición, distancia a referencias y evaluación de triggers; no recalcula ni reemplaza el PnL informado.

La comprobación real del lector final hizo diez GET en 4,196 segundos. El ticker final se recibió después de la cuenta y las órdenes finales, aproximadamente 1,923 segundos después de las posiciones finales. Se conservan tiempos de solicitud/recepción y HTTP Date por componente. El [ticker REST](https://www.bitunix.com/api-docs/futures/market/get_tickers.html) no documenta timestamp del evento de mercado: `ticker_event_time_verified=false`. HTTP Date no certifica esa fecha y no se presenta como tal.

La vigencia de 30 segundos se cuenta ahora desde la solicitud más antigua, tanto en caché/panel como al conciliar notificaciones tras una cola. No se rejuvenece una lectura porque el último GET haya terminado recientemente. Si falla el ticker final, no se rescata el primero. El presupuesto de captura de 15 segundos y los rechazos de cambios de posiciones/órdenes/componentes de saldo permanecen estrictos. Las respuestas privadas siguen siendo no atómicas y se indica en el panel.

## 5. Stops: qué cubren las consultas y qué no

La [guía oficial de cuatro modalidades](https://www.bitunix.com/hub/helpcenter/article/bitunix-futures-position-a-guide-to-four-take-profit-and-stop-loss-methods-web?id=290) incluye TP/SL de posición, parcial, trailing y de cuenta. La [API de TP/SL de posición](https://www.bitunix.com/api-docs/futures/tp_sl/place_position_tp_sl_order.html), leída solo como documentación, describe cierre por cantidad vigente al dispararse; no prueba que un `slQty=0` de una respuesta sin discriminador sea esa modalidad.

Se consulta y pagina además [órdenes ordinarias pendientes](https://www.bitunix.com/api-docs/futures/trade/get_pending_orders.html), que pueden incluir un SL adjunto a una orden. Esa protección puede depender de un fill futuro: no se suma a cobertura de una posición actual ni se asigna a LONG/SHORT sin binding verificable. Un SL adjunto o tipo desconocido sin SL por positionId deja la cobertura no verificable. Ambos libros se releen para detectar cambios durante la captura. No se invocó ningún endpoint de colocación/modificación/cancelación.

Los tres diagnósticos y la comprobación final devuelven **tres TP (dos LONG, uno SHORT), ningún SL en el libro TP/SL y cero órdenes ordinarias pendientes**. Confirma ausencia de SL en ese ámbito consultado, **no ausencia absoluta** de stops de cuenta, trailing u otra modalidad no expuesta/documentada por esos GET. La documentación pública revisada no especifica una consulta que certifique exhaustivamente todos esos productos, ni mapea inequívocamente todos ellos al libro TP/SL. No se probaron URLs privadas no documentadas.

El panel/los avisos usan `SIN SL EN TP/SL CONSULTADOS`, con otras modalidades no verificadas. Se conservan los estados de cobertura por ID: ABSENT en el ámbito consultado, INSUFFICIENT, UNVERIFIABLE y FULL_REGISTERED (registro de cantidad, nunca fill garantizado ni certificación global). No se silencian avisos reales de falta de cobertura ni se coloca un stop para probar el sistema.

## Resultado y siguiente paso

**Revisión de interpretación y temporalidad completada; reconciliación financiera/alcance global de stops todavía NO CERTIFICADOS.** No se relajan tolerancias. GO técnico para presentar un piloto exclusivamente de lectura a revisión, con limitaciones visibles; NO-GO para afirmar protección efectiva, resolver AMBIGUOUS_POSITIONS con las capturas actuales o habilitar ejecución. El [rollout propuesto](GUARDIAN_HEDGE_READONLY_ROLLOUT.md) no se ha ejecutado.

Después se retoma el trabajo existente de PR58 sobre impulso confirmado 1H, continuidad 4H, AO/ADX/Konkorde y BBWP >50. Las confirmaciones originales que sigan sin definición verificable se mantienen como hipótesis; ADX no define dirección y BBWP no la predice por sí solo. No se abre otra estrategia, se optimiza el histórico ni se alteran los resultados negativos anteriores.

## Verificación final de código

1217 tests globales /0 fallos; 74 específicos HEDGE incluidos. Guard de protección Guardian/ML RSI, 47 archivos protegidos, V8, readiness900 (780/59/59/1/1) y hash semanalV1 intactos. Los paneles reconstruidos offline con las tres capturas privadas muestran ambos IDs completos y quedan en 2.121/2.132 caracteres sin enviarse a Telegram. El chequeo de ticker final incluye además sus tiempos por componente. [Resultados reproducibles](GUARDIAN_HEDGE_READONLY_VALIDATION_20261127.json). Estos tests no son evidencia de rentabilidad o protección del exchange.
