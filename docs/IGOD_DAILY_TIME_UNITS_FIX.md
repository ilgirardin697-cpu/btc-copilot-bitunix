# Plan Diario: corrección de antigüedad, 2026-10-30

SHADOW ONLY. TRADE AUTHORITY: NONE.

`render.py` restaba timestamps en milisegundos pero dividía por 60 para
mostrar minutos. Un cálculo de 30 segundos se representaba como 500 minutos
y fallaba el control de plan desactualizado aunque el feed fuese HEALTHY.
La corrección es exclusivamente dividir por 60_000. Se conservan el umbral
y redondeo a minutos enteros existentes, los niveles y las reglas del plan.

## Revisión de unidades

| Superficie | Unidad / conversión verificada | Cambio |
|---|---|---|
| Edad del cálculo en render | ms / 60_000 → minutos enteros | BUG corregido |
| Edad del último cierre 15m | ms / 60000 → minutos | Ninguno |
| TTL del servicio | diferencia ms frente a 900_000 (15 min) | Ninguno |
| Timestamps Python / UTC | segundos ×1000 al almacenar; ms /1000 al interpretar | Ninguno |
| Velas / frescura / weekly UTC | pasos en ms; lunes 00:00 UTC | Ninguno |
| Silencio | minutos ×60_000; comparación con now ms | Ninguno |
| Límite de avisos | 6×3_600_000; ventana 86_400_000 ms | Ninguno |
| Horarios Europe/Madrid | hora×60+minuto, minutos locales; zona con DST | Ninguno |
| Outcomes descriptivos | observed_at ms + horizonte×86_400_000 | Ninguno |
| Bridge / sleeps / timeouts | reloj en segundos, 30 s de sondeo; timeouts en segundos | Ninguno |

## Regresiones

Casos explícitos 30 s, 1 min, 19 min y 21 min para full/summary/levels.
Incluyen indicadores y soportes/resistencias de fixture: visibles únicamente
en planes disponibles/no caducados, ocultos para UNKNOWN, futuro o caducado.
Estos fixtures son pruebas de software, no evidencia de mercado independiente.

Un test recorre `/diario`, `/resumen`, `/niveles` y `/alertas` con una demora
de cálculo de 30 segundos; también comprueba dedupe del update. Pruebas
adicionales verifican TTL 14:59.999/15:00 y silencio de dos minutos.
Los casos de plan fresco fallan con la división anterior y pasan con el fix.

## Aislamiento y despliegue

Rama de fix separada desde 395acc1c86ca7e9ff58ae874700b5e8ed1dbe18e para
evitar que un push a la rama compartida vuelva a desplegar Guardian.
Solo el source branch/pin del servicio experimental `igod-daily-plan`
cambia tras CI. Guardian sigue en su deployment y SHA anteriores; no se
modifican claves, bot, poller, permisos, estrategias, fórmulas ni flags.
El hash de protocolo diario no incluye render y permanece inalterado.
BITMAN_WEEKLY_FORWARD_V1 también permanece inalterado.

Se conserva el volumen `/daily-plan-data`, su SQLite y preferencias/claims.
El diagnóstico técnico inicial no se repite porque su claim es persistente.
Rollback, si procede: SOLO source branch/pin del planificador a
igod-daily-plan-v1 / 395acc1c86ca7e9ff58ae874700b5e8ed1dbe18e; nunca borrar
datos ni restaurar claves históricas. No merge.

La verificación visual final de las respuestas Telegram requiere los
comandos del propietario en el bot existente. Tests y logs de cola no se
presentan como confirmación humana de recepción ni como atribución de entrega.
