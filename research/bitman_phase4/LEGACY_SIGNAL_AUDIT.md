# Legacy / ruido — propuesta Phase4, sin acciones

No se ha cambiado ningún servicio, variable, alerta, código de producción ni
artifact anterior. DISABLE_ALERTS/ARCHIVE son propuestas para revisión, nunca
borrado. El resultado de esta fase es INCONCLUSIVE para las familias examinadas,
no un rechazo de toda la metodología Bitman.

| Sistema | Propuesta | Evidencia y límite |
|---|---|---|
| **Guardian** | **KEEP_ACTIVE** | Protección de capital, no señal de alpha. Preservar su modo y autorizaciones existentes; no habilitar PROTECT. |
| **V8** | **KEEP_ACTIVE** | Sigue con evidencia positiva. Comparador común TEST +66.55%, Sharpe0.732, DD−32.01%. BITMAN LONG4H no prueba superioridad estable ni justifica sustituirlo. KEEP_ACTIVE no significa habilitar ejecución ni cambiar sus permisos. |
| Manual Copilot | KEEP_AS_CONTEXT | Reglas humanas y niveles causales intactos. Sin journals reales accesibles no se declara edge forward. |
| Forward Audit | KEEP_ACTIVE | Telemetría necesaria para distinguir hipótesis de resultados prospectivos. No es una estrategia. |
| ML RSI confirmado LOW29/EMA4 | RESEARCH_ONLY / KEEP_AS_CONTEXT | Preservar matemática, recuperación y telemetry. El RSI privado adaptado de Bitman no es este indicador y permanece excluido. |
| ML RSI approaching/provisional | DISABLE_ALERTS, candidato para revisión | Si solo repite contexto sin incremento comprobado, conservar logs/status y reducir ruido. Aún no hay journals para medir incremento real; no se desactiva nada aquí. |
| ML RSI1H LOW27 GREEN_RESUME histórico | RESEARCH_ONLY | INTERESTING BUT INCONCLUSIVE no valida producción LOW29 ni una señal única. No incorporado a Phase4. |
| ML RSI15m hipótesis histórica | ARCHIVE | NO EDGE para las reglas probadas; preservar evidencia. |
| Early Breakout | ARCHIVE / DISABLE_ALERTS, propuesta | NO EDGE. No integrado, iniciado, detenido ni modificado. |
| Confluence D60 | RESEARCH_ONLY | Vecinos55/65 negativos, deterioro2026; el60 no se reutiliza como regla mágica. |
| BITMAN Phase2 | **ARCHIVE** | REJECT oficial, PR22 inmutable. No se reutilizan sus reglas. |
| V8 BEAR A–G | ARCHIVE | SHORT rechazados; Phase4 plantea hipótesis nuevas sin reutilizar esos motores. |
| BITMAN REAL v0.1 / PR23 | RESEARCH_ONLY | INCONCLUSIVE inmutable. Su proxy/eventos aislados no cubrían toda la nueva secuencia AO→ADX. |
| BITMAN REAL Phase4 | RESEARCH_ONLY | INCONCLUSIVE. LONG4H neto positivo pero dependiente de mejores3, sin elegibilidadDEV/ventaja contra control; SHORT negativos. No activar nuevas alertas automáticas. |
| DATA / freshness / visibility | KEEP_AS_CONTEXT | Valor operativo independiente de predecir precio; sin cambios. |

Los journals de `/data/copilot_audit`, `/data/mlrsi`, `/data/early_breakout` siguen
**PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR**. No se sustituyen por logs
incompletos. Una futura importación read-only debe conservar versión/config y
fuente FORWARD_LIVE, medir overlap, lead/lag, resultados maduros/censurados y
duplicación entre señales. Podría cambiar las recomendaciones de ruido o la
prioridad de una nueva investigación; no reescribiría este backtest congelado.

No realizar limpieza hasta medir información incremental y revisar los resultados.
**NO MERGE. NO DEPLOY. NO REAL ORDER. No production Telegram changes.**
