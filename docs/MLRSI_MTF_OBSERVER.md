# Observador pasivo ML RSI multitemporal — host Guardian

El observer recoge evidencia de BTCUSDT en **15m, 1H y 4H**. Siempre es
**SHADOW ONLY**, con **`trade_authority=false`**, incluso con
`LIVE_EXECUTION=true`. No afirma que sus señales tengan edge ni concede permiso
de entrada. No abre/cierra posiciones ni cambia SL, TP, leverage, sizing,
autorización, planner, fee guard, cooldown, daily risk, reversals o thesis exit.

**Exact BackQuant TradingView parity is NOT proven.** Se describe como
*Causal ML RSI port using captured BackQuant configuration*. El research 15m
de [PR #19](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/19)
concluyó **NO EDGE** para la hipótesis probada. El resultado 1H GREEN_RESUME
de [PR #20](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/pull/20)
es **interesting but inconclusive**. Esos PRs y resultados no se modifican.

## Arquitectura y límites

Topología de producción verificada del proyecto Railway `victorious-energy`:

| Servicio | Rama | Entrypoint | Responsabilidad |
|---|---|---|---|
| `btc-copilot-bitunix` | `v8-real-executor` | `python v8_executor.py` | Ejecución V8 REAL, **sin cambios** |
| `igod-trade-guardian` | `main` | `python trade_guardian.py` | Guardian, Copilot y host ML RSI pasivo |

`trade_guardian.py` crea `MLRSIHost` con **solo** un directorio observacional,
el callback `guardian.telegram.send` y un logger estático. El host importa,
inicializa y arranca `MLRSIObserver` en un daemon independiente: imports, disco,
descarga y clustering no bloquean el ciclo Guardian. No se le pasa Guardian,
Bitunix, Store, posiciones, permisos, credenciales ni callbacks de protección.
No hay código ML RSI en `Guardian.cycle`, `_act` o `reconcile`.

`guardian_commands.TelegramCommands` sigue siendo el **único consumidor de
`getUpdates` en este runtime**. Se añade `/mlrsi` al mismo handler owner-only;
recibe exclusivamente `StatusCache.read`, no el observer ni el host completo.
Esta cache independiente contiene solo texto renderizado y un flag ON/OFF.
El comando no descarga, recalcula ni escribe; lee la última publicación, cuya
fotografía incluye la antigüedad de los datos. No se habilitan comandos ni se
cambia `GUARDIAN_ENABLE_COMMANDS=false` por defecto.

Los destinatarios, token y autorización Telegram existentes se conservan.
Las alertas usan `Telegram.send` del Guardian; las respuestas de comandos,
`send_owner`. El adaptador elimina únicamente las etiquetas `<b>` porque el
transporte Guardian es texto plano. No se crea bot ni poller adicional.
`/status` recibe una sola línea `ML RSI MTF Observer: ON/OFF` y `/help` conserva
todo su contenido, añadiendo `/mlrsi`. `live_auto.py` vuelve íntegramente al
baseline main V7.3.8.6, sin hooks ML RSI. No se modifica ningún start command,
rama de servicio o archivo V8. La versión interna actual del observer es
`V7.3.8.7_MLRSI_LOW29_2`; no cambia la versión de un executor.

Un fallo de init, arranque, cálculo, mercado, disco, comando o Telegram produce
un diagnóstico estático y no interrumpe la gestión real. La falta de datos
excluye ese TF de cualquier nueva confluencia. No se imprime el error externo,
response body, token, chat ID o credenciales en los logs del observer.
La entrega usa el Telegram existente; no se redefine su comportamiento.

## Configuración actual capturada y matemáticas

La referencia actual confirmada es `ML RSI [BackQuant] low 29 Ema 4 1 10 90 5 10 1.000 3.000 3`.
El observer usa **LOW29_EMA4**, no el preset RSI27 de los estudios congelados.
`CONFIG_VERSION=CAPTURE_LOW29_EMA4_CAUSAL_V2`. RSI29 se aplica realmente a
bootstrap, cálculo incremental, confirmed y la copia provisional.

| Campo | Valor | Uso en este port |
|---|---|---|
| Calculation Source | LOW | Fuente efectiva del RSI |
| RSI Length | 29 | Wilder RMA, seed: primeras 29 diferencias LOW, 30 velas |
| Smooth RSI | ON | Activo |
| Moving Average Type / Period | EMA / 4 | Seed: primer RSI finito |
| Sigma ALMA | 1 | Metadata; no afecta EMA |
| Threshold Range Min / Max | 10 / 90 | Metadata capturada; no se inventa su función |
| Step | 5 | Metadata capturada |
| Performance Memory | 10 | Metadata capturada |
| Max Clustering Steps | 1000 | Máximo iteraciones |
| Max Data Points | 3000 | Últimas muestras RSI suavizadas finitas |
| Clusters | 3 | p25/p50/p75, percentiles lineales |
| Wait for timeframe close | ON | Confirmaciones al cierre real UTC |

Se reutilizan **sin editar** `guardian_signals.cluster_three` y `pine_ema`, las
mismas funciones puras usadas en #19/#20. Cada nuevo dato reinicializa los
centroides en p25/50/75; assignment por distancia absoluta, medias como update,
empates al cluster inferior y clusters vacíos conservando el centroide previo.
La convergencia y los valores finitos conservan la política existente. RSI
estrictamente superior al centroide alto es GREEN; estrictamente inferior al
bajo, RED; entre ambos e igualdad, NEUTRAL. Warmup o no convergencia: UNKNOWN.

`CausalSeries` conserva Wilder/EMA y la cola de 3000 muestras entre ciclos y
reinicios. Se exige una ventana madura de 3000 antes de declarar disponible
un TF. Los tests comparan resultados completos con la misma función pura
`rolling_mlrsi(length=29)` para el mismo LOW desde el mismo inicio. Los estudios
históricos RSI27 de #19/#20 y sus resultados/fixtures siguen intactos; cambiar
este observer no recalcula ni reinterpreta esos resultados como RSI29.
El primer RSI aparece tras exactamente 29 cambios; posteriores medias Wilder
usan `(media_anterior * 28 + cambio) / 29`. EMA4 mantiene su seed y política.

No se demuestra identidad visual con TradingView: el Pine exacto y la
semántica inequívoca de range/step/performance memory no están verificadas;
rolling causal difiere del recorte del histórico visible de TradingView;
el seed inicial depende del histórico público cargado. Venue, timezone, longitud
de histórico y redondeos pueden causar diferencias. No se fusionan datos entre
venues para disimularlas. La clasificación observada no demuestra rentabilidad.

## Datos públicos y cache

Analyzer dispone de 260 velas Bitunix por TF, insuficientes para maxData3000.
Se usa **Binance spot BTCUSDT**, la misma venue del research, mediante únicamente
`GET https://data-api.binance.vision/api/v3/klines`, sin credenciales ni netrc.
Referencia: [endpoint market-data-only oficial](https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only).
Se carga historia paginada pública (mínimo 3232 velas cerradas, normalmente
cuatro páginas de 1000) y se conserva una cache de precios por TF. Después se
solicita solamente desde la última vela cacheada, incluida la abierta. Cada
ciclo tiene un máximo de ocho páginas por TF para limitar la recuperación.

El worker comprueba datos cada 30 s. No descarga 3000 velas cada ciclo. Los
timestamps son open time UTC alineados al TF: **closed si `open_time + TF <= now`**;
open si `open_time <= now < open_time + TF`. OHLC inválidos, duplicados, datos
futuros, historia insuficiente o stale y discontinuidades se rechazan. No se
interpolan huecos. La cache no se presenta como lectura pública fresca tras
un fallo de red. Una revisión de una vela ya sellada se rechaza.

Un hueco irrecuperable deja el TF no disponible; no se reinicializa
silenciosamente Wilder/EMA a mitad de una serie. Se muestra la antigüedad de
la última lectura pública. Tras 90 s sin lectura satisfactoria el estado se
marca no actual y no cuenta como confluencia actual.

## Confirmed, CROSS y RESUME

Solo las velas completamente cerradas entran en la serie persistente.
Cada TF tiene historial y máquina de eventos independientes. Se usan exactamente
las definiciones research **one-bar**, sin añadir la variante two-bar:

- GREEN_CROSS: cualquier color distinto de GREEN → GREEN.
- RED_CROSS: cualquier color distinto de RED → RED.
- GREEN_RESUME: dentro del mismo episodio GREEN, pendiente no positiva rearma;
  la primera pendiente positiva posterior dispara una vez.
- RED_RESUME: dentro del mismo episodio RED, pendiente no negativa rearma;
  la primera pendiente negativa posterior dispara una vez.

Salir del color, dato inválido o discontinuidad cancela el rearm. La pendiente
es la diferencia entre RSI suavizados de dos cierres consecutivos. No se emite
RESUME en cada vela que continúa favorable. La vuelta confirmada a NEUTRAL
también alerta. Un timestamp cerrado ya procesado se ignora.

## Provisional y approaching

La LOW de la vela abierta se calcula sobre una **copia desechable** de la serie
cerrada: incluye su propia actualización causal de centroides. Nunca entra en
los seeds, histórico, color ni máquina CROSS/RESUME confirmed. Se etiqueta
**OPEN CANDLE / NOT CONFIRMED / PROVISIONAL** y puede desaparecer al cierre.
Solo se avisa una vez por lado y vela abierta, cuando el color provisional
GREEN/RED difiere del confirmado. Una nueva vela rearma esos latches.

APPROACHING es **nuestra capa observacional**, no comportamiento BackQuant
verificado. GREEN: RSI provisional todavía no GREEN, estrictamente debajo del
upper threshold y `0 < upper-RSI <= 1.0`. RED: simétrico por encima del lower.
Se manda una vez al entrar. Solo se rearma cuando la distancia correspondiente
es **estrictamente >1.5**; una distancia de 1.5 no rearma. El rearm persiste
entre velas y reinicios. Si ambas zonas se solapan pueden mostrarse ambas;
ninguna constituye confirmación ni CROSS.

## Confluencia y agrupación

3/3 exige tres colores **confirmed, maduros y actuales** iguales. Dos TF
confirmados y uno provisional nunca son 3/3. Se notifica una vez al entrar;
salir rearma, y volver permite otra notificación. Una pérdida de datos por sí
sola no rearma el episodio ni genera una nueva señal al recuperar conexión.
Las entradas/salidas de confluencia se registran en el journal.

Todos los avisos muestran 15m/1H/4H. En un mismo ciclo se agrupan eventos en
un mensaje con prioridad: 3/3, CROSS, RESUME, cambio color, PROVISIONAL,
APPROACHING. Un cierre CROSS más confluencia no manda tres mensajes. Un texto
demasiado largo se resume bajo el límite Telegram y remite a `/mlrsi`.

## Telegram y comandos

Avisos: startup CURRENT STATUS, cambios GREEN/RED/NEUTRAL, los cuatro eventos
research, aproximaciones, cruces provisionales y entrada en 3/3 GREEN/RED.

Ejemplo ilustrativo (no fotografía de mercado ni señal real):

```text
🟢🟢🟢 ML RSI — GREEN_CROSS + 3/3 GREEN CONFIRMED 15m
BTCUSDT
15m 🟢 GREEN
1H 🟢 GREEN
4H 🟢 GREEN
15m Event: GREEN_CROSS
ML RSI: 57.42
Upper: 57.18 | Middle: 50.21
Lower: 44.03
✅ CLOSED CANDLE
👀 SHADOW ONLY
🚫 TRADE AUTHORITY: NONE — NO AUTO TRADE
```

`/mlrsi` devuelve cada TF, valor confirmed y provisional, tres centroides,
distancias/approaching, último cierre/evento, antigüedad pública, confluencia,
configuración y leyenda. Funciona sin evento reciente y sin datos suficientes
devuelve UNKNOWN/no actual. Si está OFF también lo indica. El comando solo
consulta cache; no produce señales artificiales, solicitudes Bitunix ni
escrituras. `/help` conserva todos los comandos y añade una sola línea.
**No existe `/mlrsi_help`.**

## Persistencia y recuperación

Directorio independiente `MLRSI_STATE_DIR`. Si no se configura: se deriva como
`RAILWAY_VOLUME_MOUNT_PATH/mlrsi` cuando existe ese ajuste; en su ausencia,
`/data/mlrsi` si `/data` existe; como fallback local, `mlrsi_observations`.
Se rechazan el directorio de Guardian, Forward Audit o Early Breakout y sus
descendientes, así como la raíz del volumen. **Nunca Guardian Store, V8 state,
V8 journal ni `igod_live_state.json`.** Un path inválido deshabilita únicamente
el host ML RSI; Guardian continúa. El cierre usa señales de parada, sin `join`.

- `igod_mlrsi_state.json`: atomic replace, fsync archivo y directorio donde
  soportado. Config/version/venue/symbol, math carry por TF, últimos cierres,
  colores actual/anterior, último evento y timestamp, valores confirmed/open,
  latches approaching/provisional, confluencia anterior y outbox de journal.
- `igod_mlrsi_cache_15m.json`, `_1h.json`, `_4h.json`: OHLC público y última
  verificación; cache acotada e incremental, independiente del estado live.
- `igod_mlrsi_events.jsonl`: fsync append, campos forward descritos abajo.

Cada serie persistida incluye `rsi_length=29`. Un estado anterior LOW27 o sin
el marcador actual se rechaza y se reconstruye silenciosamente desde la cache
OHLC pública; no se mezclan seeds/medias RSI27 con RSI29. Un restart del mismo
preset conserva el seed parcial y las medias/EMA exactamente.
El journal anterior LOW27 permanece legible **sin reetiquetar sus registros**:
conserva `CAPTURE_LOW27_EMA4_CAUSAL_V1`; los nuevos usan LOW29_V2. Cualquier
comparación forward debe separar los presets por `config_version`, nunca
presentar resultados LOW27 como LOW29. Configuraciones de journal desconocidas
continúan rechazándose.

La carga inicial/restart catch-up es silenciosa: no reenvía CROSS, RESUME,
confluencias ni cambios antiguos. Puede emitir una fotografía explícita
**CURRENT STATUS**, nunca NEW SIGNAL. Mientras el worker ya esté activo,
recuperaciones de varias velas se journalizan por su verdadero cierre y valor;
solo el cierre actual puede alertar. Contexto de otro TF posterior a un evento
recuperado se marca UNKNOWN para evitar incorporar futuro.

La clave confirmed es `BTCUSDT|tf|closed_timestamp|event`; provisional y
approaching usan open timestamp más sus latches; confluencia se deduplica por
episodio. Un outbox durable conserva eventos antes de append. Tras un crash
se reconcilian claves ya escritas y se completa el journal sin alertar eventos
antiguos. Un journal corrupto bloquea nuevos append hasta reparación y deja
vivo Guardian. Un state corrupto fuerza bootstrap silencioso.

Entrega Telegram es **at-most-once en restart**, no garantía de recepción: un
crash entre persistencia y envío puede perder una notificación. No se afirma
durabilidad del hosting sin un volumen persistente y verificación operacional.
Este PR no configura ningún volumen ni Railway variable.

## Journal forward

Cada cambio/evento incluye `recorded_at_utc`, `candle_timestamp_utc`, `timeframe`,
`symbol`, `candle_complete`, `source=LOW`, `source_low`, `close`, `mlrsi_raw`,
`mlrsi_smoothed`, `lower_threshold`, `middle_centroid`, `upper_threshold`,
`distance_to_green`, `distance_to_red`, `confirmed_color`, `provisional_color`,
`previous_confirmed_color`, `event`, `approaching_state`, estados confirmed y
provisional 15m/1h/4h, `config_version`, `observer_version`, `dedupe_key`,
**`shadow_only=true`, `trade_authority=false`**. No guarda información de cuenta,
credenciales, chat IDs, señales de entrada operacional ni retornos futuros.

## Variables y defaults

```dotenv
MLRSI_OBSERVER_ENABLED=true
MLRSI_TELEGRAM_ALERTS=true
MLRSI_APPROACHING_ENABLED=true
MLRSI_APPROACH_DISTANCE=1.0
MLRSI_APPROACH_REARM_DISTANCE=1.5
MLRSI_PROVISIONAL_ALERTS=true
MLRSI_STATE_DIR=/data/mlrsi
```

No hay nuevas variables obligatorias. Valores inválidos usan defaults y un log
estático; rearm debe superar approach o ambos vuelven a1.0/1.5. OFF no arranca
worker, no descarga ni escribe archivos. Telegram OFF no detiene telemetry;
provisional-alerts OFF mantiene el cálculo/journal pero no ese aviso.

## Auditoría y tests

`mlrsi_safety_audit.py` compara con main inmutable
`9d0024a45d8e40193162a3864a876ca5ab61d1da`. `live_auto.py` debe estar íntegramente
restaurado. De los módulos Guardian/commands se retiran únicamente los nodos
AST exactos auditados de init/start/stop, callback de cache, ruta `/mlrsi`, línea
`/status` y entrada `/help`; todo lo restante debe coincidir. La clase Guardian
completa es idéntica, incluidos `_act`, `reconcile`, `cycle`, lockout y manejo
de posiciones. No se sustituyen los hashes de seguridad anteriores: su test
normaliza solo estos añadidos y exige también el nuevo audit completo.

`tests/fixtures/mlrsi_safety_baselines.json` fija blobs Git y SHA256 de los
módulos de riesgo/autorización y V8. Los archivos operativos V8 de la rama
`v8-real-executor` se verifican como objetos Git sin portarlos ni ejecutarlos.
El manifest conserva los hashes originales externamente validados del preset
LOW27. El bloque `live_observer_preset` registra únicamente los tres cambios
autorizados para LOW29: math, observer/versionado y renderer. Public data sigue
idéntico. Los hashes del host Guardian y su command poller se fijan al commit
`e1a11039d2171c90e7fac5a149095ba3b42a820f`, sin cambios en esta corrección.
La clase ResearchEvents se compara por AST con el port original; CROSS/RESUME
conservan exactamente sus definiciones. No se altera el research congelado.

Las pruebas ejecutan main y el motor real Guardian con transportes falsos.
Los traces de GET/POST y actions journal coinciden con baseline para observer
OFF/ON/excepción, LONG/SHORT, protección SL, EMERGENCY, respuesta ambigua,
reconciliación de INTENT y fallo privado. El caso explícito de error ML RSI
durante EMERGENCY llega al mismo flash-close simulado. SHADOW sigue produciendo
cero POST. El comando arbitrario no hace ningún HTTP, escritura o mutación.
Las pruebas no envían órdenes ni Telegram real.

```text
python -m py_compile mlrsi_math.py mlrsi_public.py mlrsi_observer.py mlrsi_telegram.py mlrsi_guardian_host.py mlrsi_safety_audit.py trade_guardian.py guardian_commands.py test_mlrsi_observer.py test_mlrsi_integration.py
python -m unittest test_mlrsi_observer test_mlrsi_integration -v
python -m unittest test_trade_guardian test_guardian_commands -v
python mlrsi_safety_audit.py
python -m unittest discover -v
git diff --check
```

CI dedicada instala todo `requirements.txt`, incluyendo numpy, requests,
pandas y websocket-client, y usa Python3.12 como la suite existente. La dedicada
y las jobs Guardian/Early ejecutan todos los tests observer/integration sin
skips. El job legado V8 sin numpy/requests mantiene la política existente de
module-level SkipTest para módulos Guardian/observer; no se cambia ese workflow.
No hay skips condicionales por pandas ni tests dependientes de RealAuto.
No se inicia observer de producción como parte de los tests.

Validación local del preset LOW29 (Python 3.12): 163 tests dedicados ML RSI e
integración, 311 Guardian/comandos/audit, 16 V8 y 52 Early Breakout; suite completa
542 tests. Todos pasan, cero fallos y cero skips con dependencias completas.
El ensayo separado de compatibilidad del job V8 sin dependencias ejecuta
25 tests con 9 skips de módulos que requieren numpy/requests, conforme a la
política previa; no se usa ese ensayo como sustituto de la regresión completa.

**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDER. NO LIVE LOGIC CHANGE.**
