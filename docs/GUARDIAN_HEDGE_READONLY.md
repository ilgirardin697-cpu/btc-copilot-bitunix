# Guardian HEDGE/CROSS — lectura para /position y /risk

Estado: **implementación para revisión, no desplegada**. Base productiva exacta: `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad` (radar PR59). V8 permanece en `2475daea09a96c301db22b6e4736c150ab358194` y no requiere cambios. Se conserva la rama existente del estudio de lectura; no se fusionan PR59/60 ni se crea otro servicio.

SHADOW ONLY. TRADE AUTHORITY: NONE. No reequilibrios, promediados, entradas, cierres, SL/TP operativos ni campañas nuevas.

## Límite de arquitectura

`guardian_hedge.client.Reader` solo tiene GET a un origen fijo y cuatro endpoints autorizados: cuenta USDT, posiciones de la cuenta principal, ticker y TP/SL pendientes. No importa ni reutiliza clientes con capacidad de órdenes. No permite URL arbitraria, proxy ambiental, redirecciones, datos de subcuentas, endpoints de trading ni reintentos de mutaciones. El transporte no contiene POST/PUT/PATCH/DELETE.

El host usa una sesión propia y un thread pasivo; nunca comparte el exchange client del protector. La instalación solo crea el lector: el thread y su primer GET arrancan después de completar un ciclo existente de protección. Refresca después de cada captura, con espera de 15 segundos. La captura completa tiene presupuesto de 15 segundos, límite de posiciones/páginas/bytes y un ritmo máximo propio de aproximadamente 6,7 GET/s. El caller del ciclo solo copia una caché y encola hechos de notificación; no espera red, SQLite ni logger. Un fallo no interrumpe Guardian.

El flag nuevo `GUARDIAN_HEDGE_READONLY_ENABLED` es **false por defecto**. No se ha creado en Railway. Además exige modo SHADOW, allow_sl=false, allow_close=false y Capital V2 ENABLED/EXECUTION desactivados. No habilita permisos ni sustituye controles. Si el radar no está disponible, no se oculta el aviso crítico antiguo. Un fallo de la conciliación de notificaciones tiene su incidencia independiente `guardian:hedge-notifications`; nunca renombra un error real de autenticación como AMBIGUOUS_POSITIONS.

El cliente/las reglas de protección antiguos permanecen congelados y seguirán rechazando una posición múltiple para cualquier mutación. El diagnóstico interno `GUARDIAN_BLIND_CODE=AMBIGUOUS_POSITIONS` de esa ruta antigua no se borra: no se finge que el ejecutor soporte HEDGE. Solo se retira la incidencia genérica del radar cuando la vía de lectura satisface todas las comprobaciones. La eliminación de fragmentos exactos en CI demuestra que el resto del AST de protección y los comandos antiguos sigue siendo el aprobado; no se refreezan hashes.

## Alcance y captura

1. Cuenta USDT inicial, todas las posiciones de cuenta principal (`includeSubAccounts=false`, sin seleccionar un símbolo).
2. Marcas/precios de todos los activos USDT presentes y BTCUSDT; nunca compensar BTC con ETH como si su neto fuese riesgo cero.
3. Todas las páginas TP/SL por símbolo. Se asocia **localmente por positionId**, sin confiar en el filtro opcional observado como ineficaz. IDs de orden duplicados, posiciones desconocidas, páginas incompletas o activos incoherentes rechazan la captura completa.
4. Segunda lectura de posiciones, TP/SL y cuenta. IDs, cantidades, precios medios, modo, margen, PnL realizado, comisiones y funding deben permanecer estables; las órdenes y los componentes de saldo deben coincidir. Un cambio durante la lectura exige otra captura, nunca mezclar estados.
5. Timestamps de solicitud/recepción/exchange y SHA256 de cada respuesta en la evidencia en RAM. No contienen cabeceras ni credenciales. No se registran balances ni payloads en stdout.

Las llamadas no son una transacción atómica del exchange. El PnL flotante puede actualizarse entre ellas. **No se atribuye automáticamente un descuadre a latencia**: se muestra `PNL_ACCOUNT_POSITION_MISMATCH`. No se introdujo tolerancia monetaria para hacer coincidir valores.

La caché caduca a los 30 segundos, sin usar datos anteriores como actuales tras fallos. Para retirar la incidencia genérica se necesitan **dos capturas distintas consecutivas** completas, estables y con cuadre exacto del PnL agregado. Cambios de cantidad/entrada/cobertura reinician esa comprobación. Datos viejos, incompletos, funding/comisiones tardíos, fallos de autenticación o un PnL sin cuadrar nunca autorizan retirar AMBIGUOUS_POSITIONS. Esto es una regla técnica de consistencia, no un filtro de señales de mercado.

## Paneles manuales

`/position` y `/risk` usan la vista copiada; no reciben credenciales ni clientes. Muestran cada LONG y SHORT BTCUSDT y cada positionId, incluidos múltiples IDs del mismo lado, con cantidad, precio medio, margen, apalancamiento, PnL realizado/flotante y liquidación informados, además de cada TP/SL con su ID, precio, cantidad, trigger y tipo.

La exposición bruta suma valores absolutos; la neta mantiene la dirección **por símbolo**. La cuenta muestra margen utilizado, órdenes congeladas y disponible informados por la API. El margen de posiciones se mantiene separado del margen de cuenta; no se duplica el colateral CROSS ni se asigna equity a cada lado.

Equity por componentes = available + frozen + margin + crossUnrealizedPNL + isolationUnrealizedPNL, misma convención del lector V2 auditado. Es una magnitud derivada y etiquetada, no un nuevo presupuesto. El realizado de las posiciones abiertas ya está en el saldo: no se suma de nuevo; comisiones y funding se presentan separados. No se afirma PnL neto de toda la cuenta a partir únicamente de posiciones abiertas. Bonus distinto de cero o un ámbito no compatible queda sin verificar.

## Cobertura y riesgo no son la misma cosa

| Estado | Evidencia |
|---|---|
| ABSENT | Respuesta completa sin SL registrado para ese positionId; TP no cuenta como stop |
| INSUFFICIENT | Cantidad explícita de SL válido menor que la posición |
| UNVERIFIABLE | Cantidad cero/ausente, trigger desconocido o pasado, LIMIT no garantizado, exceso/solapamiento no resuelto o datos incoherentes |
| FULL_REGISTERED | Cantidad explícita cubierta por órdenes MARKET registradas, triggers válidos y binding exacto por ID |

Se suman solo cantidades explícitas de SL por posición, sin duplicar IDs. Exceso de cobertura queda para revisión. FULL_REGISTERED no significa fill garantizado ni riesgo global normal; gaps/fallos de exchange siguen siendo posibles. No se mueven stops ni se cancelan órdenes manuales.

La referencia de liquidación ≤0 conserva la semántica oficial de no estimación actual; un dato ausente sigue siendo desconocido. Se muestra cada referencia positiva sin inventar una liquidación agregada. En CROSS una referencia al lado no esperado del mark no se trata como liquidación ya ocurrida. La proximidad absoluta del 2% se presenta como referencia crítica, sin cambiar el umbral del protector V2 ni autorizar cierres.

El riesgo agregado combina exposición bruta, disponible, equity por componentes, cobertura de todos los IDs, coherencia de la cuenta y referencias cercanas/no verificables. No se inventa margen de mantenimiento ni headroom: `liquidation_risk_certified=false` es explícito incluso con stops registrados. No se llama NORMAL a una cuenta solo por tener neto cero.

## Telegram y reinicios

Se reutiliza el único coordinador del radar desplegado, su writer lock, SQLite FULL/WAL y outbox. El reconciliador corre en el mismo worker escritor y confirma memoria, incidencias y outbox en una transacción. Su memoria persistente conserva únicamente referencias hash, timestamps y estados de notificación; no modifica journals financieros.

- AMBIGUOUS_POSITIONS se mantiene hasta contar con evidencia completa y consistente; no se resuelven otros errores privados por esa excepción.
- Cada stop ausente/insuficiente/no verificable tiene una incidencia propia con lado, símbolo y referencia. No se confunden las alertas LONG y SHORT ni se silencian con /silencio.
- Incidencias cerradas se resuelven únicamente con un snapshot completo. Tras reinicio se reconcilian los IDs persistidos; paquetes viejos no resucitan ni resuelven incidencias nuevas.
- Un antiguo aviso de riesgo del otro lado no se resuelve por seleccionar uno de los dos IDs. Si la posición sigue presente y su riesgo no está certificado, el aviso se conserva.
- Sin WAIT, heartbeats, porcentajes de PnL o snapshots rutinarios en Telegram. Prealertas/confirmaciones existentes siguen sin cambios. Los recordatorios críticos siguen siendo horarios y no se promete exactly-once ante fallos de red.

## Evidencia y pendientes

Fixtures con esquema observado/documentado, IDs e importes sustituidos; no son una reproducción pública de balances reales. Pruebas offline de cobertura, scopes, duplicados, ventanas inconsistentes, errores, persistencia, quietud, comandos y ausencia de autoridad.

El contraste local real fue exclusivamente GET y leyó LONG/SHORT HEDGE/CROSS, dos TP LONG y uno SHORT, sin SL devuelto. Aparecieron un descuadre del PnL cuenta/posiciones y una referencia de liquidación direccional no interpretable. **No se declara ese estado apto para retirar AMBIGUOUS_POSITIONS ni protegido.** No se ha activado este código en Guardian; no se ha hecho ninguna mutación Railway o Bitunix en esta fase.

Una revisión posterior debe evaluar el cuadre financiero real sin relajar criterios silenciosamente y aprobar cualquier rollout de lectura. No implica aprobación de protección automática. Para rollback de esta ampliación, desactivar solo su flag y volver al SHA `5c6cc6a…` con variables actuales; V8 permanece intacto. No usar snapshots que restauren credenciales antiguas ni borrar journals.

La segunda comprobación real finalizó a las 20:11:33 UTC del 26/11/2026, con siete GET y una captura de aproximadamente 2,54 segundos. Volvió a observar dos posiciones HEDGE/CROSS y el mismo resultado de cobertura: dos TP LONG, un TP SHORT y ningún SL devuelto. El PnL no cuadró y la referencia direccional CROSS del SHORT no se certificó. La evidencia sanitizada versionada incluye tiempos, códigos y hash de fuente; excluye todos los importes e IDs privados. Son observaciones de ese instante, no una afirmación permanente sobre la cuenta.

## Comprobación para un futuro rollout, no ejecutado en esta entrega

1. Revisar esta PR y confirmar que el despliegue de lectura sigue siendo el único alcance. Leer flags efectivos antes y después: SHADOW, SL/close OFF, Capital V2 OFF y V8_LIVE_EXECUTION=false. Conservar credenciales, start command, volúmenes y journals.
2. Desplegar únicamente Guardian en el SHA revisado con el nuevo flag ausente/false. Verificar SUCCESS y SHA real, salud de ciclos y comandos; no cambiar V8, Daily Plan ni market-data. Usar la lección del despliegue por SHA documentada en el [cierre del radar](NOTIFICATION_ROLLOUT_20261126.md).
3. Solo tras autorización, habilitar la lectura pasiva. Comprobar ambos IDs y la asociación de cada TP/SL con GET independientes, así como el cuadre financiero. Si el PnL sigue sin cuadrar, conservar el incidente privado; no ajustar fórmulas ni tolerancias para retirarlo. No generar incidentes ni señales falsas para probar Telegram.
4. El propietario consulta `/position` y `/risk`; deben mostrar ambos lados, fuentes/edad y stop ausente, insuficiente o no verificable según corresponda. El único poller y los demás comandos permanecen intactos. Cien capturas sin cambios no deben producir cien mensajes; una nueva pérdida real de cobertura sí debe mantener su incidencia crítica.
5. Ante regresión, desactivar únicamente esta capa y volver al SHA Guardian estable con las variables actuales. No borrar stores, resolver artificialmente incidentes ni reiniciar campañas. No se necesita desplegar V8 para este cambio.

Referencias oficiales consultadas:

- [Posiciones](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html).
- [TP/SL pendientes](https://www.bitunix.com/api-docs/futures/tp_sl/get_pending_tp_sl_order.html).
- [Componentes de cuenta](https://www.bitunix.com/api-docs/futures/account/get_single_account.html).
- [CROSS frente a ISOLATION](https://www.bitunix.com/hub/helpcenter/article/futures-margin-modes-cross-margin-vs-isolated-margin?id=155).

Pruebas técnicas no constituyen evidencia de rentabilidad ni cobertura efectiva futura.

## Resultado final reproducible

1205 tests de descubrimiento global, 0 fallos; 62 específicos HEDGE incluidos en ese total. Auditoría Guardian/ML RSI y hashes V8 OK; boundaries semanal 9/9 y readiness 7/7. Readiness conserva 900 estados (780/59/59/1/1) y hash `1ffcf53c6b056e7bdf3b780f1fc4ebce49616363a66467e573c5c1a2ef71f014`. V1 semanal conserva `d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8`. No hay refreeze.

Evidencia técnica y listado SHA256 de archivos protegidos sin cambios: [GUARDIAN_HEDGE_READONLY_VALIDATION.json](GUARDIAN_HEDGE_READONLY_VALIDATION.json). Los tests son offline y no certifican protección real ni rentabilidad.
