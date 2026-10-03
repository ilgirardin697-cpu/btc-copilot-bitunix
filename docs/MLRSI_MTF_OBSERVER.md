# Observador pasivo ML RSI multitemporal — V7.3.8.7

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

`live_auto.py` únicamente crea un `MLRSIObserver` con un directorio observacional,
un callback del Telegram existente y un logger. Arranca un daemon independiente:
la descarga, el clustering, las escrituras y los avisos no se ejecutan dentro del
loop de gestión de posiciones. `/mlrsi` lee una copia pequeña de la última
fotografía publicada; no refresca APIs ni modifica estado operacional.

La autenticación de comandos y los destinatarios Telegram existentes no se
alteran. No se añade polling Telegram. No se conecta el observer a Guardian,
V8, Forward Audit ni Early Breakout. **El hook corresponde a `live_auto.py`**;
no cambia el entrypoint Railway ni inicia otro servicio. `/status` y su alias
`/live` reciben una sola línea `ML RSI MTF Observer: ON/OFF`.

Un fallo de init, arranque, cálculo, mercado, disco, comando o Telegram produce
un diagnóstico estático y no interrumpe la gestión real. La falta de datos
excluye ese TF de cualquier nueva confluencia. No se imprime el error externo,
response body, token, chat ID o credenciales en los logs del observer.
La entrega usa el Telegram existente; no se redefine su comportamiento.

## Configuración capturada y matemáticas

| Campo | Valor | Uso en este port |
|---|---|---|
| Calculation Source | LOW | Fuente efectiva del RSI |
| RSI Length | 27 | Wilder RMA, seed: primeras 27 diferencias |
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
un TF. Los tests comparan resultados completos con `rolling_mlrsi` de research
para el mismo LOW, desde el mismo inicio, y fixtures extraídos de ambos PRs.

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

Directorio: el mismo directorio observacional de `OBSERVER_STATE_FILE`, en el
volumen configurado por `RAILWAY_VOLUME_MOUNT_PATH` o local si no lo hay.
**Nunca `igod_live_state.json`.**

- `igod_mlrsi_state.json`: atomic replace, fsync archivo y directorio donde
  soportado. Config/version/venue/symbol, math carry por TF, últimos cierres,
  colores actual/anterior, último evento y timestamp, valores confirmed/open,
  latches approaching/provisional, confluencia anterior y outbox de journal.
- `igod_mlrsi_cache_15m.json`, `_1h.json`, `_4h.json`: OHLC público y última
  verificación; cache acotada e incremental, independiente del estado live.
- `igod_mlrsi_events.jsonl`: fsync append, campos forward descritos abajo.

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
vivo el executor. Un state corrupto fuerza bootstrap silencioso.

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
```

No hay nuevas variables obligatorias. Valores inválidos usan defaults y un log
estático; rearm debe superar approach o ambos vuelven a1.0/1.5. OFF no arranca
worker, no descarga ni escribe archivos. Telegram OFF no detiene telemetry;
provisional-alerts OFF mantiene el cálculo/journal pero no ese aviso.

## Auditoría y tests

`mlrsi_safety_audit.py` compara el AST completo de `live_auto.py` con main
`9d0024a45d8e40193162a3864a876ca5ab61d1da`, retirando solamente los hooks
especificados, ruta `/mlrsi`, línea `/status`, `/help` y versión de presentación.
Todo el AST operacional restante debe ser idéntico. También bloquea imports
operacionales, funciones de órdenes, mutating HTTP y rutas privadas en el
observer. La suite compara el dispatcher original y actual con observer
OFF/ON/excepción, LONG/SHORT/WAIT, posición abierta/cerrada y LIVE_EXECUTION=true,
usando únicamente fakes. Las pruebas no envían órdenes ni Telegram real.

```text
python -m py_compile mlrsi_math.py mlrsi_public.py mlrsi_observer.py mlrsi_telegram.py mlrsi_safety_audit.py live_auto.py test_mlrsi_observer.py test_mlrsi_integration.py
python -m unittest test_mlrsi_observer test_mlrsi_integration -v
python mlrsi_safety_audit.py
python -m unittest discover -v
git diff --check
```

CI dedicada instala todo `requirements.txt`, incluyendo numpy, requests,
pandas y websocket-client, y usa Python3.12 como la suite existente. Otras
jobs mínimas sin pandas omiten únicamente los tests de import dinámico RealAuto;
el job mínimo V8 sin numpy/requests omite los módulos observer, como ya hace
con los tests Guardian/research. La dedicada ejecuta todos. Los tests previos y reglas de otros módulos no se
reescriben. No se inicia observer de producción como parte de los tests.

**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDER. NO LIVE LOGIC CHANGE.**
