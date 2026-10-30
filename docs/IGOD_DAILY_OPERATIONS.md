# I-GOD Plan Diario — operación experimental

SHADOW ONLY. TRADE AUTHORITY: NONE. No es un motor de ejecución.

## Un bot, un receptor, un sender

Guardian conserva su único `getUpdates`, owner policy y sender/retry.
Solo añade cinco rutas pasivas; el bridge consulta por HTTP privado el
servicio `igod-daily-plan.railway.internal:8080`. El hilo del bridge no
bloquea el ciclo de protección. No hay segundo bot, webhook, token ni
credenciales de cuenta en el planificador.

El servicio nuevo vive en Amsterdam, dentro del proyecto/environment de
Guardian para poder usar su red privada. Lleva volumen propio de 500 MB
en `/daily-plan-data`, nunca `/data`. Sin dominio público ni TCP proxy.
PAPER permanece en su servicio/proyecto independiente.

## Uso desde el chat actual

| Comando | Resultado |
|---|---|
| `/diario` | Recalcula el plan; muestra fuente, hora y antigüedad de datos |
| `/resumen` | Recalcula y muestra una lectura breve |
| `/niveles` | Recalcula soportes, resistencias y niveles condicionales |
| `/alertas` | Consulta preferencias persistentes de este plan |
| `/alertas diario on` / `off` | Resumen diario, 08:00 Europe/Madrid por defecto |
| `/alertas hora 08:00` | Cambia la hora; admitidas 08:00–21:59 |
| `/alertas cambios on` / `off` | Cambios semánticos; máximo 2/24h y separación 6h |
| `/alertas criticas on` / `off` | Cancelación de escenario al perder su invalidación |
| `/alertas noche on` / `off` | Permiso nocturno solo para avisos críticos habilitados |
| `/alertas on` | Activa solo el resumen diario y levanta el silencio |
| `/alertas off` | Desactiva todos los automáticos del plan |
| `/silencio` | Silencia indefinidamente los avisos no críticos del plan |
| `/silencio 120` / `/silencio off` | Silencio temporal / quitar silencio |

Todos los avisos automáticos empiezan OFF. La franja nocturna es 22:00–08:00
Europe/Madrid, incluidos cambios de horario de verano. Nunca se silencian
Guardian, V8 o ML RSI con estos comandos. Las consultas manuales siguen
disponibles durante el silencio. No hay resumen atrasado fuera de los
primeros diez minutos de la hora elegida.

Una prueba técnica opcional de instalación, expresamente autorizada, se
identifica como tal, se reclama una sola vez en SQLite y solo puede salir
entre 08:00 y 22:00. No contiene una señal inventada.

## Qué significa el resultado

ESPERAR cuando faltan datos, confluencia o geometría. Datos retrasados una
vela respecto al último cierre esperado fallan cerrados. La caché expira
en 15 minutos; una representación con más de 20 minutos no muestra niveles.

LONG/SHORT son escenarios condicionales del core adjunto, nunca órdenes.
El ciclo diario es una hipótesis diagnóstica separada. ADX mide fuerza;
no determina el lado. Un rebote contra tendencia no confirma reversión.
La reconfirmación futura 15m no está formalizada por el ZIP y permanece
PENDIENTE. No hay permiso de entrada implícito.

Se conserva el core original. Su BBWP CLOSE13/252/SMA5 difiere del BBWP del
motor Bitman congelado: paridad exacta NO PROVEN. Los TP se etiquetan por
tramo A/B, sin afirmar que TP1 sea necesariamente el más cercano. El riesgo
0,5% conjunto es un cálculo sobre 140 USDT DE EJEMPLO, nunca saldo real;
gaps, funding y ejecución no garantizan ese máximo.

## Persistencia y evidencia

SQLite WAL/FULL guarda preferencias, claims de entrega, observaciones
públicas y eventos/resultados prospectivos. Observaciones y resultados se
añaden con IDs únicos. No es el journal semanal V1 ni comparte su protocolo.
El hash de core/cycle/analysis/state queda fijado al primer arranque; un
cambio posterior exige un almacenamiento/protocolo nuevo.

El calentamiento histórico no genera eventos forward. Los eventos nuevos
requieren un cierre diario posterior a la activación y un cambio de fase.
Los horizontes 1/3/5 días parten del timestamp REAL observado y de su precio
15m ya cerrado, nunca de un precio diario anterior que no se podía ejecutar.
Son observaciones direccionales, no fills ni PnL del plan A/B. Con muestra
cero: FORWARD EVIDENCE INSUFFICIENT.

La prueba histórica y sus pérdidas/costes/drawdowns están en
`research/results/IGOD_DAILY_CYCLE_VALIDATION.md`. No hay holdout virgen ni
validación del plan con dos entradas. No se ajustaron parámetros tras ver
los resultados. Conclusión: INCONCLUSIVE — FORWARD OBSERVATION REQUIRED.

Los claims se confirman ANTES de devolver un mensaje: ante fallo ambiguo
puede perderse un aviso; no se reencola tras reinicio. El sender existente
conserva sus retries, por lo que no se promete entrega exactly-once frente
a timeouts de Telegram. `IGOD_DAILY_REPLY_QUEUED` solo confirma encolado.

## Rollout y rollback

1. Suite completa, audits y CI verdes; publicar branch y PR DRAFT, sin merge.
2. Crear únicamente el servicio privado experimental y volumen propio.
   Dockerfile `igod_daily_plan/Dockerfile`, start explícito
   `python -m igod_daily_plan.service`, PORT=8080, health `/health`.
   Sin config heredada de `railway.json`, claves ni variables compartidas.
3. Esperar SUCCESS y log sanitario real `IGOD_DAILY_STATUS`, con fuente,
   fase, hora y autoridad NONE. No interpretar health HTTP como señal válida.
4. Revalidar Guardian sano y no cambios staged ajenos. Staged diff exclusivo:
   source pin al commit probado + `IGOD_DAILY_PLAN_URL` al hostname privado.
   Conservar claves Bitunix ACTUALES, todos los flags, start, región y volumen.
5. Esperar Guardian SUCCESS/1 réplica, mismos controles de capital y
   protección, ML RSI fresh. V8, PAPER y market-data no se redeployan.
6. El propietario prueba `/diario`, `/resumen`, `/niveles`, `/alertas`,
   `/silencio` y un comando antiguo como `/help` en el chat existente.
   Una respuesta por consulta; ninguna orden ni nuevo receptor.

Ante regresión: restaurar SOLO el source pin anterior `fc211d8...` y quitar
SOLO `IGOD_DAILY_PLAN_URL`; conservar variables/claves actuales. No restaurar
snapshots históricos que puedan recuperar claves revocadas. No borrar
volúmenes, observaciones ni preferencias para solucionar un fallo.

## Limitaciones explícitas

No hay evidencia prospectiva de rentabilidad. El benchmark histórico no
simula funding, stops, objetivos ni ejecuciones de dos tramos. Las pruebas
sintéticas validan software, no edge. El registro de cola no sustituye la
confirmación humana de recepción Telegram. Este piloto no toca readiness,
el simulador PAPER, V8, ML RSI o BITMAN_WEEKLY_FORWARD_V1.
