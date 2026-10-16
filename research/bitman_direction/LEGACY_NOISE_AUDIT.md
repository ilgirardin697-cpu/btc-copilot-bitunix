# Eficiencia / ruido — propuesta documental, no limpieza

**Direction Engine: INCONCLUSIVE DIRECTION ENGINE.** No sustituir ni silenciar
sistemas útiles por estética. No se ha cambiado ninguna alerta, servicio,
variable, código de producción o poller, y no se ha borrado evidencia.

## Qué se pudo medir

Simulación pública congelada, TEST2024–2026-10-15T19:00UTC. No son mensajes
realmente entregados por Telegram. En el mismo reloj cerrado1H:

| Serie | Cambios | Cambios/día | Interpretación |
|---|---:|---:|---|
| Estado principal Direction Engine | 5.236 | 5,14 | UP/DOWN/TRANSITION/UNCLEAR/CONFLICT; cambio solo con estado distinto. |
| Firma material del prototipo | 8.040 | 7,89 | Estado+detalle+strength+grade; incluso con dedupe puede generar demasiado ruido. |
| V8 LONG/FLAT cerrado4H/SMA200 | 167 | 0,164 | FLAT no significa DOWN. No se usa como un SHORT invertido. |

El99,92% de las horas clasificadas UP por el engine coinciden con V8 LONG. Esto
indica gran solapamiento **de estado**, no prueba igualdad de sistemas ni alpha
incremental. Los83 onsets V8 UP y702 onsets engine UP solo producen8 pares
temporales a±24h mediante emparejamiento uno-a-uno por menor distancia absoluta.
Mediana `engine_time - V8_time`: **+12h** en esos8 pares; no una ventaja temprana
generalizable. Overlap de onsets:1,14% del engine y9,64% de V8.

Las dos medidas no se contradicen: el engine cambia muchas veces dentro de un
contexto que V8 ya mantiene LONG. Describir ese contexto repetidamente puede
añadir ruido sin anticipar un cambio nuevo. Los cambios estructurales/timing no
son operaciones ni falsas alarmas automáticamente; requieren outcomes y journals.

A72h: engine UP50,85% de acierto direccional (n702), DOWN44,76% (n697).
V8 UP53,66% (n82 maduros de83). Estos samples no son iguales y la comparación
simple no establece superioridad. Los controles emparejados no demuestran
ventaja robusta del engine. No se elige una política nueva después de TEST.

## Qué NO se pudo medir

**FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR.**

No hay copias disponibles de journals entregados de Guardian/Copilot, ML RSI o
Early Breakout. Por tanto no se puede cuantificar honestamente: mensajes reales
por día, duplicación entre bots, tasa de anticipaciones ML falsas, lead/lag de
confirmaciones realmente observadas, entregas fallidas ni utilidad incremental
forward. Logs parciales y backfill no sustituyen esos journals.

La aportación de ML RSI confirmado al engine está **PENDING**, no cero y no
validada. No se recalculó su matemática para fabricar historia. El adaptador
read-only queda preparado para copias futuras, preservando config y hora real de
disponibilidad. La instrumentación existente no tiene ML RSI1D.

## Clasificación por módulo / alerta

Son recomendaciones para revisión futura; **ninguna se ejecuta en esta fase**.
Estado real de despliegue/flags no se presupone por encontrar código en una rama.

| Módulo/alerta | Propuesta | Información distinta y evidencia / límite |
|---|---|---|
| **Guardian capital/liquidación/protección** | **KEEP_VISIBLE / KEEP_ACTIVE** | Infraestructura crítica, no alpha. Riesgo, pérdida de datos y protección son distintos de dirección. No reducir visibilidad por resultados de señales. |
| **V8 señales de estrategia / estado de ejecución** | **KEEP_VISIBLE** | Evidencia histórica positiva conservada. Independiente del Copilot/engine; no demostrado valor superior del nuevo engine. No habilitar ni aumentar ejecución/riesgo. Información de órdenes/posición real no debe confundirse con contexto direccional. |
| **ML RSI confirmed** | **KEEP_AS_CONTEXT** | Aportación incremental actual desconocida. No suprimirlo automáticamente. Si futuros journals prueban que aporta confirmación distinta, usar KEEP_INTERNAL dentro del engine; si solo duplica dirección sin lead/valor incremental, proponer DISABLE_ALERTS de duplicados conservando telemetry/status. |
| **ML RSI provisional / approaching** | **DISABLE_ALERTS (propuesta condicionada a revisión)** | No son confirmaciones ni evidencia de entrada. No se ha medido su tasa real de falsos/repetidos en esta tarea. Conservar datos KEEP_INTERNAL; antes de actuar, comprobar si aportan lead útil que compense ruido. Ningún flag cambia. |
| **Early Breakout** | **ARCHIVE; DISABLE_ALERTS si estuviera emitiendo** | Investigación previa NO EDGE. Preservar código/artifacts. No iniciar, detener ni alterar servicio. |
| **Confluence D60** | **ARCHIVE / RESEARCH_ONLY** | Fragilidad55/60/65 y deterioro2026 ya documentados. No competir visualmente como señal principal sin nueva evidencia independiente. |
| **BITMAN Phase2** | **ARCHIVE** | REJECT inmutable. No reactivar reglas ni notificaciones. |
| **BITMAN REAL v0.1** | **ARCHIVE / RESEARCH_ONLY** | INCONCLUSIVE, proxy no privado; conservar toda evidencia, no alertas nuevas de producción. |
| **BITMAN REAL Phase4** | **ARCHIVE / RESEARCH_ONLY** | INCONCLUSIVE y LONG4H concentrado; no alertas nuevas. |
| **Manual Copilot** | **KEEP_AS_CONTEXT** | Niveles, explicación y consultas manuales útiles; no demostrado que el nuevo engine lo reemplace. No cambiar reglas, comandos ni avisos actuales. |
| **Copilot Forward Audit /stats** | **KEEP_INTERNAL** | Recopilación prospectiva y estadísticas consultables, no señal. Preservar sin informes automáticos repetidos. |
| **DATA / SHADOW PassiveObserver y visibility en live_auto.py** | **KEEP_INTERNAL / KEEP_AS_CONTEXT** | Telemetría y auditoría pueden ser distintas de alpha. Código presente no demuestra que ese proceso esté desplegado. Avisos repetitivos sin utilidad serían candidatos DISABLE_ALERTS tras medir journals; no se actúa. |
| **Confluence Shadow y otros observers experimentales** | **KEEP_INTERNAL / RESEARCH_ONLY** | No asumir edge ni actividad real por existir una rama. Inventariar versiones/journals antes de recomendar cambios operativos. |
| **Mensajes manuales importantes / comandos owner-only** | **KEEP_VISIBLE** | Respuesta solicitada por el usuario, no spam automático. No cambian autenticación, comandos ni poller. |
| **BTC Direction Engine nuevo** | **KEEP_INTERNAL — RESEARCH ONLY** | INCONCLUSIVE; no Telegram real. Mayor frecuencia y escaso incremento medido no justifican convertirlo en fuente visible principal. |

`RESEARCH_ONLY` describe el uso, no una acción de limpieza. `ARCHIVE` conserva
código, informes, datasets, tests y artifacts; no significa borrar. No se cambian
los criterios ni las notificaciones operativas de ningún sistema.

## Arquitectura que podría revisarse, no se activa

Como el resultado actual es INCONCLUSIVE, **no se prepara una sustitución
operativa**. Guardian y V8 conservan visibilidad; Copilot/consultas permanecen;
el nuevo engine queda interno en research, sin sender. Telemetría y estadísticas
deben seguir independientes de ejecución.

Solo si una nueva revisión concluyera USEFUL DIRECTION ENGINE con evidencia
incremental/estabilidad y journals suficientes, tendría sentido proponer:
VISIBLE=engine direccional agrupado + Guardian riesgo + V8 cuando aporta algo
distinto + mensajes manuales; INTERNAL=confirmaciones/forward audit;
SILENT=notificaciones duplicadas demostradas; ARCHIVED=hipótesis rechazadas.
Eso requiere otra autorización y un diseño concreto basado en evidencia nueva,
no una limpieza automática ni una promesa de despliegue de este prototipo.

**NO CLEANUP. NO MERGE. NO DEPLOY. NO REAL ORDERS. NO TELEGRAM PRODUCTION CHANGES.**
