# Guardian — rollout propuesto exclusivamente de lectura (NO EJECUTADO)

Requiere revisión del nuevo HEAD exacto de PR61 y autorización posterior. Esta entrega no es permiso para aceptar staged changes, desplegar o crear flags. El descuadre financiero actual y las modalidades no verificadas deben aceptarse como limitaciones visibles del piloto, nunca como protección efectiva.

## Baseline comprobado el 27/11/2026

Proyecto `victorious-energy` / production: `6c6bb439-74e8-44f8-9af8-3777e38ada89` / `16363ee1-7337-4d0f-a168-63a88d00dbe8`.

| Recurso | Referencia que se conserva |
|---|---|
| Guardian | Servicio `0d3dceaa-b523-4ad8-b8c3-48e421af8f97`, deployment `81e7adc5-b106-48cd-a2df-4fe5f7de8c4f`, SUCCESS/Online1/1, SFO |
| Source pin Guardian | `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad`; branch y start command existentes, `python trade_guardian.py` |
| Volumen Guardian | `igod-guardian-data`, `e83778fa-bae1-48f3-8cb6-b53fbb57dfed`, `/data`, 500MB |
| V8 intacto | Deployment `16d80b60-5092-4e8b-acc6-23977d70fa23`, SUCCESS/Online1/1; SHA revisado del rollout `2475daea09a96c301db22b6e4736c150ab358194` |
| Market-data intacto | `85ab6fa8-80cd-49f4-ac84-617c2aa418fa` |
| Daily Plan intacto | `3203c66a-8ad5-417f-a4ee-696a9f0b7b65` |

Railway informa cero incidencias de plataforma y ningún trabajo staged/applying. Esto no resuelve las incidencias de lectura/cobertura de Bitunix. Metadata/config son lecturas de control, no una nueva inspección SSH del contenedor. No se registró ninguna clave SSH.

Flags renderizados leídos a las 10:13:44 UTC: GUARDIAN_MODE=SHADOW; GUARDIAN_ALLOW_PLACE_SL=false; GUARDIAN_ALLOW_FLASH_CLOSE=false; GUARDIAN_CAPITAL_V2_ENABLED y GUARDIAN_CAPITAL_V2_EXECUTION ausentes→false; GUARDIAN_HEDGE_READONLY_ENABLED ausente→false; V8_LIVE_EXECUTION=false. Es configuración renderizada, no una lectura independiente del entorno del proceso. No se modificó ningún valor ni credencial.

## Procedimiento tras autorización separada

1. Verificar PR61 OPEN/DRAFT, HEAD exacto revisado y todos los workflows de ese HEAD. Repetir lectura de flags, pin, deployment, volumen, staged changes y salud; detenerse si el baseline cambió. Conservar SHA de rollback y referencias de journals/store antes del cambio, sin escribir campañas nuevas ni exportar secretos.
2. Desplegar SOLO Guardian al SHA revisado con GUARDIAN_HEDGE_READONLY_ENABLED ausente/false. No merge, cambio de rama, configuración de Bitunix, V8, shared SDK, HMAC, bot/poller, ML RSI, mercado o weekly V1. Usar deploy explícito por commit y verificar el SHA real según el procedimiento del [rollout cerrado](NOTIFICATION_ROLLOUT_20261126.md), sin confiar solo en el pin almacenado. Esperar SUCCESS/Online1/1 y mismo `/data`.
3. Verificar salud del ciclo y comandos existentes con el lector OFF. No debe haber actividad nueva del lector. No enviar comandos en nombre del propietario. Si hay una regresión, rollback inmediato del Guardian, no tocar V8.
4. Solo si se aprobó expresamente el piloto de lectura, establecer únicamente GUARDIAN_HEDGE_READONLY_ENABLED=true en Guardian; ningún permiso de protección/ejecución. Desplegar SOLO Guardian, esperar SUCCESS y verificar variables antes/después, credenciales preservadas mediante comparación no reveladora, mismo volumen y stores. No activar otras funciones para facilitar la prueba.
5. Verificar respuesta fresca de los cinco endpoints GET autorizados: cuenta, posiciones, ticker, TP/SL y órdenes ordinarias. Confirmar ambos positionId, timestamps por componente, ticker final y asociación local de TP/SL. Esperar que el cuadre financiero continúe marcado NO VERIFICADO si persiste; AMBIGUOUS_POSITIONS y los avisos de cobertura no se deben recuperar sin evidencia. No probar colocando/cancelando órdenes ni fabricando incidentes.
6. El propietario prueba `/position` y `/risk`; deben mostrar ambos lados, exposición bruta/neta, margen, PnL y estimación de equity etiquetada, referencias CROSS y alcance de los stops. Confirmar que `/diario`, `/resumen`, `/niveles`, `/alertas`, `/bitman` y otros comandos siguen con una única respuesta. Silencio automático conservado: sin snapshots rutinarios, dedupe persistente, críticas por pérdida de cobertura o proximidad real sin silenciar. Las pruebas de fallo y100evaluaciones son offline; no se fabrican señales de producción para demostrarlas.
7. Cerrar el piloto solo con logs de salud, flags/SHA/volumen preservados y limitaciones documentadas. La protección automática sigue DESARMADA. Cualquier ampliación de autoridad necesita otra revisión.

## Rollback

Ante crash, bloqueo/degradación del ciclo, errores de comandos, pérdida de datos, flags efectivos inesperados o falsa recuperación/silenciamiento de una incidencia: desactivar el nuevo flag de lectura, desplegar explícitamente Guardian `5c6cc6a78a16520deda2d21f562fa6cf0a4cbaad` con variables/credenciales actuales, esperar SUCCESS y verificar SHA/Online1/1 y `/data`. No restaurar snapshots antiguos de credenciales ni borrar SQLite, journals o campañas. V8 y los demás servicios permanecen en sus deployments originales. La reversión del radar completo es otro alcance, con referencias conservadas en el informe del rollout.

Un descuadre que se conserva visible no es una falsa reconciliación. Si se busca certificar riesgo global o ausencia absoluta de stops, **STOP**: el piloto no proporciona esa garantía. No activar por ese motivo ejecución, una reparación de órdenes ni reequilibrios.

SHADOW ONLY. TRADE AUTHORITY: NONE.
