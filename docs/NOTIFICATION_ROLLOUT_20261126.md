# Radar silencioso — verificación del rollout autorizado

**ROLLOUT TÉCNICO Y COMPROBACIÓN MANUAL SUPERADOS. Rollback: NO necesario.** Ventana de runtime: 26/11/2026 18:11:43–19:13:45 UTC. Cierre posterior tras verificar retirada de acceso SSH temporal y recibir la confirmación manual del propietario.

SHADOW ONLY. TRADE AUTHORITY: NONE. Ninguna orden ni modificación de posiciones, margen, apalancamiento o configuración Bitunix.

## Servicios autorizados

| Servicio | SHA aprobado y comprobado dentro del contenedor | Deployment activo |
|---|---|---|
| Guardian, PR59 | `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad` | `81e7adc5-b106-48cd-a2df-4fe5f7de8c4f` |
| V8, PR60 | `2475daea09a96c301db22b6e4736c150ab358194` | `16d80b60-5092-4e8b-acc6-23977d70fa23` |

Ambos SUCCESS / Online 1/1, SFO. PR59 y PR60 no se han fusionado. No se ha cambiado código durante el rollout.

Primero se comprobaron ambos SHA con radar OFF: Guardian `c7c3cfd4-f685-4ec8-a855-8d3d31c208e5`, V8 `95711bec-4934-42b5-b4ff-48c8f08dd17d`. Sin store de notificaciones ni diagnósticos del radar en esa fase. Después se configuró únicamente una clave HMAC exclusiva de notificaciones, sin exportarla a archivos locales, y se activó Guardian antes que V8.

Railway guardó inicialmente el pin pero el despliegue automático tomó la rama antigua. Se detectó por metadata y SSH **antes de activar**. Se utilizó la API oficial `serviceInstanceDeploy(commitSha: SHA_APROBADO)` y se verificaron SHA y archivos reales. Los pins configurados y los contenedores actuales coinciden con los SHA revisados. **Para futuros cambios no confiar únicamente en actualizar el campo del pin: especificar el SHA al desplegar y verificarlo nuevamente.** No se cambiaron ramas ni start commands.

## Seguridad y configuración

- Guardian SHADOW; Capital V2 ENABLED y EXECUTION ausentes, efectivos false; PLACE_SL=false; FLASH_CLOSE=false.
- V8_LIVE_EXECUTION=false, comprobado tanto por API como dentro del contenedor.
- LIVE_EXECUTION y LIVE_AUTO_START antiguos siguen true en V8. Pertenecen a `live_auto.py`, que no se importa ni ejecuta desde el `v8_executor.py` desplegado. Se conservaron sin modificarlos. No representan el gate efectivo actual, pero no se debe cambiar el start command al ejecutable antiguo.
- IGOD_NOTIFICATION_RADAR_ENABLED=true en Guardian y V8; claves HMAC iguales. Comparación por huellas: todas las variables ajenas a notificaciones permanecen idénticas al baseline, incluidas credenciales, flags ML RSI y weekly V1.
- Mismos volúmenes: Guardian `igod-guardian-data` (`e83778fa-bae1-48f3-8cb6-b53fbb57dfed`) y V8 `btc-copilot-bitunix-volume` (`b861b92f-ac38-4bbc-b4ae-6008e391d777`), ambos montados en `/data`.
- Journals presentes sin truncación observada. Prefijos de hasta 65.536 bytes conservados; el journal semanal completo de 8.771 bytes conserva su hash. Esto no se presenta como certificación byte a byte del historial completo de todos los journals grandes.
- Market-data sigue en deployment `85ab6fa8-80cd-49f4-ac84-617c2aa418fa`; Daily Plan sigue en `3203c66a-8ad5-417f-a4ee-696a9f0b7b65`. Ningún otro servicio se ha modificado.
- Ningún dominio público, TCP proxy, servicio, bot, poller o volumen nuevo.

## Verificaciones realizadas

- Salud privada HTTP200 desde Guardian y desde V8.
- Una OBSERVATION firmada, repetida: primer ACK no duplicado y siguientes ACK duplicate=true. Tras redeploy del mismo Guardian permanece un único registro. Cero outbox/Telegram para esa observación. No se fabricaron oportunidades ni incidentes críticos.
- SQLite quick_check=ok; lock de un único escritor ocupado por el host. No se abrió un segundo store escritor.
- Incidencia real AMBIGUOUS_POSITIONS activa: tres avisos iniciales de gravedad creciente y un recordatorio posterior; 14 equivalentes deduplicados. Cuatro outbox SENT, cero mensajes rutinarios. Ocho ACK por destinatario corresponden a dos chats distintos, verificados por GET getChat; no son ocho avisos al mismo chat.
- 371 ciclos reales en la ventana 18:11:43–19:13:45 UTC sin un aviso por ciclo. Mediana entre registros de ciclo: 9,997 segundos; máximo observado: 22,005 segundos. Esta medición no demuestra latencia cero. Logs revisados en seis intervalos, con 117/122/120/116/136/181 entradas, todos por debajo del límite 500: sin Traceback ni fallos de notificaciones nuevos.
- Recordatorio de la incidencia todavía activa registrado a las **19:12:51,950 UTC**, entregado y con ACK persistente en ambos chats. Se genera al recibir el siguiente aviso real del productor después de una hora desde el aviso anterior; no es un temporizador exacto al segundo. No se adelantó el reloj ni se cambió el intervalo para probarlo.
- getMe y getWebhookInfo correctos; sin webhook, mismo bot existente. El auditor no llamó a getUpdates ni envió comandos. El propietario confirmó expresamente que **/diario, /resumen, /niveles, /alertas y /bitman responden una sola vez y sin errores nuevos**.
- Readiness en runtime: WAIT780, WATCH_LONG59, WATCH_SHORT59, READY_LONG1, READY_SHORT1. Hash `1ffcf53c6b056e7bdf3b780f1fc4ebce49616363a66467e573c5c1a2ef71f014`.
- V1 semanal verificado en runtime: `d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8`. Sin cambios ni refreeze.
- Cachés ML RSI 15m/1H/4H continúan actualizando sus timestamps. No se cambió matemática ni flags.
- No ha surgido una oportunidad nueva que permita certificar PRE/CONFIRMED/INVALIDATED con un evento natural en este intervalo. Sus transiciones, errores y reinicios están cubiertos por los tests, no por señales inventadas.

## Pruebas y workflows

- Guardian: suite completa 1.108 passed /0 failed; suite específica 75/0 (incluida en la completa).
- V8: suite completa 83 passed /0 failed.
- Guards adicionales: readiness boundary 7/0, weekly boundary 9/0.
- CI para HEAD exactos: PR59 11/11 SUCCESS; PR60 2/2 SUCCESS; PR58 12/12 SUCCESS.

## HEDGE/CROSS, ampliación exclusivamente de lectura

Rama separada `guardian-hedge-cross-readonly-review`, commit `3110b72d414d885797b96ec360826eb0ed15d2ab`: cinco archivos nuevos bajo `research/guardian_hedge_readonly/`, 273 líneas, 35 tests passed /0 failed. Sin otra PR ni integración productiva.

El auditor GET-only encontró dos posiciones distintas LONG/SHORT HEDGE/CROSS. El parser productivo admite solo una y sigue fallando cerrado. Además, ambas consultas TP/SL por positionId devolvieron órdenes de ambos lados; esto explica ORDERS_SCOPE_INVALID. El auditor separado valida completitud y agrupa por ID, sin elegir arbitrariamente un lado ni ampliar capacidades del cliente productivo.

Corte privado actualizado a **19:09:58 UTC**: dos TP vinculados al LONG y un TP al SHORT, sin SL en el endpoint TP/SL completo. **Protección del exchange no certificada.** Esta afirmación se limita al endpoint revisado; no certifica otros mecanismos no inspeccionados. No se colocó, canceló ni sustituyó ninguna orden. Una referencia de liquidación del SHORT no permite aplicar sin más la fórmula direccional de una posición aislada; CROSS/HEDGE requiere reconciliación de cuenta. El estudio mantiene margen, exposición bruta/neta, PnL realizado sin costes, flotante, comisiones y funding separados, sin inventar equity ni una liquidación agregada. Detalle financiero local para el propietario: `research/cache/.hedge_private_20261126/HEDGE_CROSS_OWNER_REVIEW.md`, fuera de Git y con ACL restringida.

Los importes privados permanecen fuera de Git y con ACL local restringida. Los fixtures versionados sustituyen todos los IDs y valores financieros, manteniendo el esquema observado; son fixtures sintéticos de forma anonimizada, no snapshots certificados de cuenta.

PR58 permanece intacta: resultados negativos conservados; confirmaciones originales AO/Konkorde y continuidad4H incompletas. No nuevo backtest, optimización ni consumo vidIQ.

## Cierre y limitaciones pendientes

1. Recordatorio real y cobertura de logs: comprobados. Snapshot final: SQLite ok, un escritor, 4 críticos SENT, 14 equivalentes deduplicados, 0 rutinas, incidencia todavía activa.
2. Comprobación manual: confirmada por el propietario. Ningún comando simulado por el auditor.
3. **Clave SSH temporal retirada de Railway**, ausencia verificada mediante una consulta independiente; clave original conservada. Archivos de clave privada, pública y auxiliares temporales eliminados localmente; ausencia comprobada. No queda ese acceso autorizado de mantenimiento.
4. Rollback: **NO necesario**. Ambos servicios siguen SUCCESS/Online1/1; cero warnings/criticals de plataforma y ningún deployment de market-data/Daily Plan u otros servicios. La incidencia de aplicación AMBIGUOUS_POSITIONS sigue activa y no equivale a una incidencia de plataforma resuelta.
5. HEDGE/CROSS no está integrado ni autorizado para proteger automáticamente. Antes de ampliar producción requiere revisión del snapshot multiposición y reconciliación CROSS. El silencio de Telegram no demuestra protección del capital.
6. Aviso técnico del CLI: deprecación de Config as Code. No se ejecutó migración ni se modificó infraestructura para resolverlo.

Ante regresión: relay V8 OFF, Guardian radar OFF, deployment explícito del SHA estable con variables actuales. Nunca restaurar una snapshot antigua que pudiera reintroducir credenciales revocadas. No borrar stores, journals ni campañas.

## Consolidación final y referencias de rollback (26/11/2026)

El propietario da por cerrado el rollout y comunica una comprobación independiente de deployments y SHA realizada por ChatGPT. Es evidencia externa comunicada por el propietario, adicional a las comprobaciones técnicas documentadas arriba. Los cinco comandos manuales respondieron una sola vez, sin errores nuevos. No se requiere otro rollout ni otra clave SSH para cerrar esa intervención.

| Alcance | Referencia estable | Procedimiento sujeto a autorización |
|---|---|---|
| Volver desde la futura ampliación HEDGE solo lectura | Guardian `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad` | Desactivar únicamente `GUARDIAN_HEDGE_READONLY_ENABLED`; si hace falta volver al SHA con variables y credenciales actuales. V8 permanece en `2475daea09a96c301db22b6e4736c150ab358194`. |
| Rollback completo del radar de notificaciones | Guardian `9d40020d539033cefb8f01734db8c6a6fdbba2e3`; V8 `724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6` | Desactivar primero relay V8 y después radar Guardian. Desplegar explícitamente los SHA y verificar el runtime. Conservar variables actuales, ambos volúmenes, stores y journals. |

Estas referencias no son una orden de ejecutar rollback. No restaurar snapshots antiguos de variables: podrían reintroducir credenciales revocadas. No borrar notificaciones, journals financieros, campañas ni datos semanales. No confiar solo en el pin almacenado: la lección del rollout es verificar también el commit real del contenedor.

La clave temporal de esta intervención fue retirada y su ausencia comprobada; los archivos locales se eliminaron. La comprobación de retirada finalizó el 26/11/2026 a las 19:24:32.0328397 UTC. La clave original permanece intacta. No queda autorización reutilizable de ese acceso temporal.

El estudio HEDGE de `3110b72…` descrito arriba es el antecedente offline, no una ampliación ya desplegada. La implementación posterior está documentada en [GUARDIAN_HEDGE_READONLY.md](GUARDIAN_HEDGE_READONLY.md) y se entrega para revisión con flag false por defecto. No modifica el cierre de este rollout, los SHA productivos ni los resultados negativos de PR58.
