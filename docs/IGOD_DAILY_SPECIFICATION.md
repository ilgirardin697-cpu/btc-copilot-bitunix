# I-GOD Plan Diario V1 — especificación experimental

SHADOW ONLY. TRADE AUTHORITY: NONE. No órdenes ni conexiones a cuentas.

Base fc211d8e36c6db55185efa8309eb8f980beab2ea. El core del ZIP se conserva
sin cambios; este plan no modifica PAPER, V8, las protecciones de Guardian,
ML RSI, el motor congelado o el protocolo semanal V1.

Fuente única BTCUSDT BINANCE_USDM_PERPETUAL, REST público oficial. Diario
y semanal completamente cerrados; semana lunes 00:00 UTC. AO 5/34 HL2,
ADX/DMI Wilder14 y BBWP CLOSE13/252/SMA5 del ZIP. Este BBWP difiere del
Bitman congelado. Paridad propietaria Bitman y TradingView: NOT PROVEN.

## Detector de ciclo — declarado antes de evaluar nuevos outcomes

Versión IGOD_DAILY_CYCLE_V1_HYPOTHESIS. Principal 1D; 1W solo contexto.

- COMPRESIÓN: BBWP <=20 y pendiente no positiva, sin otro estado prioritario.
- POSIBLE INICIO: ADX gira positivo después de >=3 pendientes diarias no
  crecientes; AO slope alineado con DMI, BBWP rising y cierre rompe el último
  pivote confirmado en esa dirección. Signo AO y color se guardan separados.
- ACELERACIÓN: ADX rising, AO slope alineado con DMI y BBWP rising.
- AGOTAMIENTO: primera pendiente ADX negativa tras pendiente no negativa,
  o continuación descendente de un episodio agotado. No significa SHORT.
- POSIBLE REVERSIÓN: tras agotamiento, DMI cambia al contrario del impulso
  registrado, AO slope se alinea y el cierre rompe estructura contraria.
- INDETERMINADO: evidencia insuficiente para los cinco estados; nunca
  etiquetar compresión por eliminación.

AO recuperándose contra el impulso mientras ADX cae se marca como posible
rebote contra tendencia; no cambio de tendencia. Confirmación del precio
diario y posteriores 4H/1H/15m son requisitos independientes.

No se buscan otros N, thresholds, combinaciones o parámetros para mejorar
resultados. Tres días y BBWP20 son formalizaciones experimentales explícitas,
no parámetros del indicador privado ni reglas con edge validado.

El ciclo se muestra como diagnóstico y no concede permiso de ejecución.
Las entradas y niveles A/B y TP de ambos tramos siguen el core adjunto:
solo escenarios con confluencia, estructura confirmada y geometría válida.
Sin esos datos: ESPERAR, sin precios inventados. El rechazo/reconfirmación
15m posterior sigue PENDIENTE; no se declara implementado un trigger
ejecutable que el ZIP no define matemáticamente.

## Validación

Historia pública causal: estudio descriptivo de episodios de fase, retornos
posteriores 1/3/5 días y benchmark direccional a cinco días sin solapamiento,
entrada a siguiente open; costes supuestos 18/36 bps ida y vuelta,
falsas señales (retorno firmado no positivo), equity normalizada y drawdown.
No es un backtest del plan de dos tramos con órdenes/funding/fills.
Se informa n, resultados por época y dirección. NO VIRGIN HOLDOUT.
Esto no valida automáticamente la hipótesis ni los precios condicionales.

Prospectivo: almacenamiento independiente desde activación, observaciones
con timestamp real, hashes de inputs y ciclo del día cerrado; warmup no son
eventos forward. Ningún outcome futuro puede registrarse como maduro antes
de su cierre. Con n=0: FORWARD EVIDENCE INSUFFICIENT.

## Telegram y despliegue

Guardian es el ÚNICO receptor y conserva sender/retry, autorización y
comandos anteriores. Su adaptador de comandos solo consulta un hostname
privado exacto. Ningún otro poller, webhook, token ni sender.

Servicio nuevo igod-daily-plan, Amsterdam, en el MISMO proyecto/environment
que Guardian para private networking. Sin dominio, TCP proxy, claves,
variables compartidas ni acceso al volumen de Guardian. Volumen propio
/daily-plan-data. PAPER en igod-research-lab permanece intacto.

Auto diario default OFF; hora 08:00 Europe/Madrid. Cambios default OFF.
Quiet hours 22:00–08:00, excepto cancelaciones importantes habilitadas
expresamente junto con permiso nocturno. Silencio afecta solo avisos de
este plan; nunca Guardian, V8 o ML RSI.

Claves de entrega se reclaman persistentemente ANTES de encolar el aviso.
La política evita reencolar la misma respuesta/update tras restart, pero
el sender compartido ya tiene retries: no se promete exactly-once Telegram
ante timeout ambiguo. No se modifica ese retry.

Datos y comandos se prueban offline, incluida regresión de los comandos
previos. Solo después se despliega el servicio y la ampliación mínima del
router, conservando variables, SHA revisado, región y /data de Guardian.
