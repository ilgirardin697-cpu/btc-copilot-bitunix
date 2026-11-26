# Revisión previa al rollout de notificaciones — 26 de noviembre de 2026

Estado: PR #59 y PR #60 DRAFT. Sin merge, despliegue, cambio de variables ni mensajes reales de prueba. SHADOW ONLY. TRADE AUTHORITY: NONE.

## Defectos corregidos

1. `copilot_snapshot` ahora es un planificador puro. No escribe memoria. La aceptación de eventos, oportunidades, outbox y memoria del productor ocurre en una única transacción SQLite con savepoints anidados. Una validación fallida, error de escritura o salida abrupta antes del commit revierte todo. Una aceptación comprometida conserva el PRE pendiente después del reinicio. Una propuesta calculada con memoria antigua se rechaza para recalcularla, no sobrescribe el estado nuevo.
2. El fallback de `Host.submit` solo hace un enqueue acotado y no bloqueante. No llama al sender, logger, red ni SQLite en el hilo de protección. Un worker separado envía y coalesce la misma incidencia; las excepciones del sender quedan aisladas. La cola llena se contabiliza desde el worker, sin esperar en el caller.
3. Riesgo `NORMAL` es recuperación, no una nueva crisis activa. Además, copias frescas del snapshot existente permiten resolver avisos de riesgo/TP-SL cuando la lectura privada confirma normalización, posición ausente o cambio de posición. No se resuelve nada por datos ausentes, ambiguos, stale o malformados. Un aviso TP/SL resuelto según el evaluador existente no certifica por sí solo la cobertura real del exchange.
4. Al recuperar una incidencia, se suprimen reintentos críticos pendientes de esa incidencia. Un ACK tardío o paquete anterior no puede reactivarlos. Los mensajes que Telegram ya recibió no pueden retirarse retroactivamente.

La aceptación significa commit de la política y outbox, no recepción de una observación en una cola RAM ni entrega confirmada por Telegram. No se promete registrar mercados durante una caída del servicio. La indisponibilidad de red puede retrasar avisos y el fallback puede duplicar mensajes críticos ante una entrega ambigua; se prioriza seguridad frente a una falsa promesa de exactly-once.

## Pruebas añadidas

- Validación fallida sin consumir el candidato; reintento posterior válido.
- Escritura de outbox denegada, fallo después de escribir memoria y crash real de un proceso con `os._exit` antes del commit.
- Reinicio después de commit: una oportunidad pendiente, sin duplicación en 100 evaluaciones.
- Fallback deliberadamente lento: 100 llamadas no esperan al sender; ninguna llamada al logger/sender desde el caller.
- Error de fallback aislado y sanitizado.
- Recuperación persistente, posición cerrada/cambiada, evidencia no verificable, reintento antiguo y timestamp empatado.
- 100 errores `AMBIGUOUS_POSITIONS`: una notificación estable, incidencia todavía activa, ninguna recuperación ficticia y recordatorio si sigue sin resolver.

No cambia ningún indicador, estrategia, acción de capital, permiso, journal de trading, protocolo semanal V1 ni readiness. Los hashes modificados pertenecen exclusivamente al SDK de notificaciones todavía no desplegado; el hash V1 semanal sigue intacto.

## Causa comprobada de AMBIGUOUS_POSITIONS

Consulta privada autorizada de solo lectura del 26/11/2026 a las 10:43 UTC desde el auditor local, no desde el contenedor. La pasada completa hizo dos GET idénticos de posiciones, sin POST a Bitunix ni cambios de cuenta. Autenticación correcta: HTTP 200, código API 0.

El endpoint devolvió dos registros BTCUSDT con IDs distintos, uno BUY y otro SELL, ambos HEDGE/CROSS, mismo ámbito de cuenta, cantidades positivas y estables entre lecturas. Cada registro pasa por separado el parser actual. La lista completa falla porque `guardian_risk.parse_positions` exige como máximo un registro. No es un diagnóstico de credencial inválida ni de filas duplicadas.

La [documentación oficial de posiciones](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html) admite una lista, modo HEDGE y filtro `positionId`. El cliente congelado de Guardian autoriza un scope más estrecho; no lo ampliamos. Un intento diagnóstico de añadir el filtro fue bloqueado localmente antes de salir a red. No se elige el registro mayor, el primero ni un lado arbitrario.

El runtime desplegado `79d03f47-07e0-49aa-9e6b-54635b42577c` también registró ese código: una muestra acotada de 51 entradas entre 10:39:16 y 10:47:36 UTC. Es una muestra limitada, no el total de errores ni el número de mensajes Telegram.

**NO se ha certificado la cobertura real de los stops de ninguna de las dos posiciones.** Este cambio deduplica el aviso, mantiene la incidencia activa y conserva logs; no repara el soporte HEDGE ni convierte a Guardian en protector verificado. Adaptar protección agregada y por posición requiere una revisión específica, no un cambio escondido en notificaciones. No cambiar modo de cuenta, órdenes ni exposición para evitar el error.

## Baseline de configuración para el futuro rollout

Valores de variables renderizadas leídos mediante consultas Railway; no es una inspección independiente de `os.environ` dentro del proceso:

| Ajuste | Estado leído | Acción propuesta ahora |
|---|---|---|
| `GUARDIAN_MODE` | `SHADOW` | Ninguna |
| `GUARDIAN_CAPITAL_V2_ENABLED` | Ausente, efectivo false | Ninguna |
| `GUARDIAN_CAPITAL_V2_EXECUTION` | Ausente, efectivo false | Ninguna |
| `GUARDIAN_ALLOW_PLACE_SL` | false | Ninguna |
| `GUARDIAN_ALLOW_FLASH_CLOSE` | false | Ninguna |
| `V8_LIVE_EXECUTION` | false | Ninguna |
| `IGOD_NOTIFICATION_RADAR_ENABLED` | Ausente en ambos | Mantener OFF durante revisión |
| `BITMAN_WEEKLY_FORWARD_OBSERVER_ENABLED` | true | Preservar; no lo activamos ni modificamos |

Credenciales solo en memoria del auditor; no se publican claves, balances, precios medios, cantidades ni IDs privados. Guardian base 9d40020, V8 base 724f14f; confirmar de nuevo deployments, pins, regiones, volúmenes y ausencia de staged changes inmediatamente antes de un rollout autorizado.

## Procedimiento preparado, NO ejecutado

1. Revisión independiente de los HEAD finales de PR #59/#60 y todos sus workflows. Confirmar que los archivos de riesgo/ejecución y flags anteriores siguen iguales. Detenerse si hay cambios ajenos al alcance.
2. Leer configuración antes de cada cambio y comparar después en memoria, sin exportar secretos. Conservar credenciales y todas las variables existentes. Usar cambios parciales de variables; nunca reemplazar el mapa completo.
3. Desplegar únicamente los SHA revisados de Guardian y V8 con el radar OFF. Esperar SUCCESS de ambos. Mantener V8 real false y capital V2 OFF; ningún otro servicio se despliega. Verificar comandos manuales, ciclo de protección, volumen y ausencia de errores nuevos.
4. Crear solo una clave HMAC nueva para notificaciones, sin reutilizar claves de trading o Telegram. Configurar en ambos `IGOD_NOTIFICATION_INGEST_KEY`; en V8 puede usarse el default exacto `http://igod-trade-guardian.railway.internal:8091/events`. No crear dominio público, TCP proxy, bot, volumen compartido ni servicio adicional.
5. Activar primero `IGOD_NOTIFICATION_RADAR_ENABLED=true` solo en Guardian. Esperar SUCCESS y comprobar `/health` privado y almacenamiento en el mismo volumen, bajo `<GUARDIAN_STATE_DIR>/notification_radar_v1`. Un solo escritor; no restaurar archivos ni borrar el estado si falla.
6. Validar el relay con una OBSERVATION firmada y su reenvío idéntico: ACK persistente y dedupe, cero Telegram automático. No fabricar PRE, CONFIRMED ni alertas críticas. Si DNS, HMAC, writer lock o persistencia fallan, abortar.
7. Activar el mismo flag solo en V8, esperar SUCCESS y verificar que sus snapshots quedan en logs. Observar al menos 100 ciclos de Guardian (unos 17 minutos) y una hora para el recordatorio de incidencia real no resuelta. Registrar cobertura de logs y límites de las consultas; no inventar conteos completos si la respuesta está truncada.
8. El propietario comprueba consultas manuales y preferencias. Una señal nueva experimental solo se notifica si surge naturalmente. `AMBIGUOUS_POSITIONS` debe seguir visible como incidencia real, sin repetirse cada ciclo; no declarar protección mientras persista.

### Rollback exclusivamente de notificaciones

Ante regresión, desactivar primero el relay de V8 y después el radar de Guardian; esperar SUCCESS. Restaurar el pin anterior del servicio afectado solo si el nuevo código no queda sano. Se recuperará el routing antiguo y puede volver el ruido: eso es preferible a ocultar seguridad.

No tocar V8 live, permisos de capital, ML RSI, market-data, daily planner, campañas ni órdenes. Conservar los nuevos stores para auditoría; no limpiar `/data`, no reparar journals ni reiniciar presupuestos. Comparar todas las demás variables con el baseline leído justo antes del rollout. No realizar este procedimiento sin autorización posterior expresa.
