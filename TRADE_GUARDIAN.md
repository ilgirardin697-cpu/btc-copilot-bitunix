# I-GOD Trade Guardian + Manual Copilot

Independent service, separate from V7, V8 and Confluence Shadow. V1 watches BTCUSDT only. It reads a single BTC position and its pending position TP/SL, reports a market bias, warns about risk, and can place one catastrophic exchange stop or close the identified position in a capital emergency. It never opens, adds, averages, reverses, changes leverage or margin mode, transfers or withdraws funds, or closes other symbols. The directional opinion never closes a position.

`AUTO-CLOSE IS LIQUIDATION-EMERGENCY-ONLY IN V1`.

## Read-only defaults and arming

Default mode is `SHADOW`. Missing keys leave the private position guard disabled while public Manual Copilot can start. With keys and any disarmed setting the guard is read-only. The placement and close actions are separately armed. Each action requires all three conditions: `GUARDIAN_MODE=PROTECT`, its own flag set to `true`, and `GUARDIAN_ARM_PHRASE=PROTECT_CAPITAL_ONLY`. There is no API route outside the explicit Bitunix allowlist. `python trade_guardian.py` runs the independent 10 second risk cycle.

Disarm by setting `GUARDIAN_MODE=SHADOW`, setting both action flags to `false`, or clearing the phrase; restart the process and verify its read-only startup message. Keep API keys restricted to the necessary futures account and never place them in state files, Telegram or logs. The arm phrase enables API mutations, so protect it like an operational credential.

## Endpoints and sources

Official API documentation was checked 2026-10-02:

- Signature: [Bitunix REST signature](https://www.bitunix.com/api-docs/futures/common/sign.html). Query names are sorted in ASCII order and concatenated with values (no separators); body bytes are compact JSON. The digest is SHA256 of nonce + millisecond timestamp + API key + canonical query + body, then SHA256 of digest + secret.
- Private reads: `GET /api/v1/futures/position/get_pending_positions` with BTCUSDT and subaccounts disabled; `GET /api/v1/futures/tpsl/get_pending_orders` with BTCUSDT, position ID and bounded pagination. [Pending positions](https://www.bitunix.com/api-docs/futures/position/get_pending_positions.html), [pending position TP/SL](https://www.bitunix.com/api-docs/futures/tp_sl/get_pending_tp_sl_order.html).
- Public reads: `GET /api/v1/futures/market/tickers`, `GET /api/v1/futures/market/kline`, and `GET /api/v1/futures/market/trading_pairs`, all BTCUSDT only. Kline source is Bitunix MARK_PRICE, with LAST_PRICE fallback for venue ATR; quote precision controls stop rounding. [Tickers](https://www.bitunix.com/api-docs/futures/market/get_tickers.html), [klines](https://www.bitunix.com/api-docs/futures/market/get_kline), [pair metadata](https://www.bitunix.com/api-docs/futures/market/get_trading_pairs.html).
- Public directional data: Binance public BTCUSDT klines only. Taker buy base volume is read from the documented kline field; no private Binance API is used.
- The only Bitunix POSTs are `POST /api/v1/futures/tpsl/position/place_order` with exactly BTCUSDT, positionId, slPrice and `slStopType=MARK_PRICE`, and `POST /api/v1/futures/trade/flash_close_position` with only positionId. Official docs say a position TP/SL closes at market and only one such order may exist per position ([position TP/SL](https://www.bitunix.com/api-docs/futures/tp_sl/place_position_tp_sl_order.html)); the emergency close endpoint closes by position ID ([flash close](https://www.bitunix.com/api-docs/futures/trade/flash_close_position.html)).

The position API may return subaccounts. V1 requires `includeSubAccounts=false` in its exact GET schema. A returned nonzero `subAccountId` is a position account identifier, not evidence of a subaccount; nonnegative integers and ASCII decimal integer strings are accepted, while malformed/present null, boolean, floating or non-finite IDs fail closed. Only the transport aliases LONG/BUY -> LONG and SHORT/SELL -> SHORT are accepted after uppercase conversion, without trimming or inference. Internal positions always use LONG/SHORT. Other scope/ID/quantity/leverage checks, duplicate/hedge ambiguity and liquidation sanity remain strict. Invalid fields produce static field-specific diagnostics, never raw payloads. The client does not call any trading order, bulk order, close-all, leverage, margin, transfer or withdrawal route.

## Manual Copilot V1

Only closed candles are used. Four-hour and one-hour trend are close versus SMA200. Primary momentum is `ML_RSI27_REAL`: LOW source, RSI27 (Wilder RMA seed), EMA4, a causal rolling window of up to 3000 available smoothed RSI samples, and a maximum of 1000 clustering iterations. Three clusters initialize at p25/p50/p75, with absolute-distance assignments and arithmetic-mean centers. Green/red state compares RSI with high/low center; events are transitions from a valid neutral candle. The source is the LOW of each closed Binance 1H candle, independently of the CLOSE-based trend. Snapshots persist preset name, source and parameters; Telegram identifies LOW/RSI27/EMA4 explicitly. Empty clusters retain their prior center.

### TradingView source correction (2026-10-02)

The user's actual TradingView input display is `Low 27 Ema 4 ... 1.000 3.000 3`. The earlier Guardian used CLOSE; it is now explicitly corrected to LOW. This is the user's selected preset, not the public default. No CLOSE diagnostic participates in the primary momentum gate. Historical CLOSE-based research code, artifacts and reported metrics are unchanged; they must not be described as results for this LOW configuration.

The [author's TradingView description](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/) confirms configurable RSI source/smoothing and three clusters. Its fetched page does not expose the complete Pine inputs. The [public Pine copy attributed to BackQuant](https://tradingmike.blogspot.com/2025/06/2025-06-13rsi.html) provides the following additional mapping; it is not proof of the user's installed version:

| Display/input | Verification and Guardian behavior |
| --- | --- |
| LOW / 27 / Ema / 4 | User-confirmed selection; copy defaults are CLOSE / 14 / Ema / 4. |
| Smooth RSI? | Enabled as explicitly requested; the abbreviated display alone does not verify its checkbox. |
| 1.000 / 3.000 | Consistent with Max Clustering Steps 1000 and Max Data Points 3000; both explicitly requested. |
| Final 3 | Matches Signal Line Width default 3 in the copy. Cluster count is hardcoded to three, not a count input there. |
| Sigma 6 | ALMA-only; does not affect EMA. |
| Threshold range 10 / 90 / step 5 | Copy defaults; its factors array is unused in the shown clustering. Actual user values unconfirmed. |
| Performance Memory 10 | Copy default; unused in the shown calculation. Actual user value unconfirmed. |
| Threshold lines, bar colors, plot colors/width | Display settings; actual user values unconfirmed. |

Exact TradingView parity is not claimed. The copy uses `last_bar_index - bar_index <= maxData`, whereas Guardian uses only the trailing available samples at each closed candle. Its array initialization/push patterns contain leading unavailable elements; Guardian uses a deterministic finite-sample/empty-cluster policy. Pine's inclusive `0 to maxIter` loop can permit 1001 passes; Guardian caps at the requested 1000. Chart symbol/venue, timeframe, warm-up/history and the installed script version also require confirmation before any numerical parity claim.

Flow classifies closed 1h Binance taker-buy base-volume ratio: at least 60% strong buy, 55–60% buy, 45–55% neutral, 40–45% sell and at most 40% strong sell. A 15m structure uses unique two-left/two-right pivots only after both right candles have closed. It requires two higher highs and higher lows for bullish, or lower highs and lower lows for bearish; otherwise mixed.

Frozen `MANUAL_COPILOT_V1` permits LONG only when 4H and 1H are both bullish and at least two of ML green, flow at least 55%, and bullish 15m structure agree. SHORT mirrors that condition in jointly bearish regimes. Disagreeing trends produce WAIT; insufficient data produces UNKNOWN. Volatility is risk context, never a directional vote. For display only, ATR1H/mark below 2% is NORMAL, 2–4% is ELEVATED and at least 4% is HIGH; these bands do not change liquidation thresholds. Koncorde is `UNAVAILABLE_NOT_REPRODUCIBLE` and is not used as a gate.

## Position and risk states

### Telegram decisions and entry quality

Human messages lead with a Spanish decision banner: seek LONG/SHORT only when the unchanged directional bias allows it and `entry_quality=GOOD`; otherwise wait for a better entry, do not trade (WAIT), or do not trade because fresh evidence is missing (UNKNOWN). Evidence shows trend, ML RSI27 LOW EMA4 state/events, taker flow, confirmed 15m structure and volatility. Current manual positions are compared with bias; a prominent countertrend warning remains advice only. Risk banners and actual triple-arm/credential status are separate, with SHADOW explicitly disarmed. Startup and decision/quality changes send deduplicated alerts; the five-minute local snapshot stores the same human-readable presentation. Telegram rendering uses explicit numeric/enum fields and never echoes arbitrary exchange text, credentials or the arm phrase.

Entry quality is a conservative display heuristic, not a measured edge or a trading/protection gate. It uses the latest closed Binance 15m price, Binance closed 1H ATR14 and confirmed two-left/two-right 15m pivots. Frozen rules: POOR within 0.5 hourly ATR of opposing confirmed resistance/support, or more than 2 ATR beyond the nearest broken pivot. GOOD requires an actual wick-and-close reclaim of a pivot confirmed before that latest 15m candle, matching momentum and structure, and complete pivot/ATR evidence including an opposing level. Everything else is CAUTION. Levels and suggested pullback/breakout references come only from those confirmed pivots. No parameters were searched or fitted to TEST. Direction/entry snapshots refresh on closed 15m boundaries; risk polling and venue ATR remain unchanged. Entry quality never controls an exchange stop or flash close.

The current Bitunix mark already read for the risk cycle can only downgrade that closed-bar entry assessment: POOR for the same proximity/extension bounds, CAUTION if the confirmed interval has been invalidated or fresh mark/level evidence is missing. It never upgrades an unconfirmed setup or changes bias. This avoids displaying a green entry after price runs away between 15m closes; no extra endpoint or request is added.

One BTCUSDT position is analyzed. Leverage below 2x receives advice only. The risk engine compares absolute liquidation distance, percent of mark and ATR1H multiple. Liquidation must be below mark for a long and above mark for a short; otherwise no mutation occurs. A current successful venue mark/position response is required before mutation. Venue ATR reads closed Bitunix mark-price hourly candles and falls back to last-price candles. When ATR is missing, percent thresholds still operate and the stop buffer uses its percentage floor.

Thresholds are frozen defaults, configurable through the documented environment variables:

- NORMAL: both distance measures exceed 3 ATR and 3%.
- WARNING: either measure is at or inside 3 ATR or 3%; send a warning.
- DANGER: either is at or inside 2 ATR or 2%; high-priority warning and ensure an exchange SL where safely possible.
- EMERGENCY: either is at or inside 1.25 ATR or 1.25%; after a fresh position, TP/SL and mark preflight, a fully armed Guardian journals an intent then calls the one-position flash close. It does not wait for directional confirmation.

Equality enters the closer risk state. Normalized measures are evaluated emergency first. A failed Binance direction download sets bias UNKNOWN but does not disable the independent Bitunix percentage risk layer. Missing/stale Bitunix mark or private reads block all mutations and raise GUARDIAN BLIND.

## Catastrophic stop and manual order handling

The buffer is `max(0.75 * ATR1H, 0.005 * mark)`. A long stop target is `liqPrice + buffer`; a short target is `liqPrice - buffer`. The target is rounded away from liquidation at the pair's quote precision and must remain strictly between mark and liquidation, with at least two price ticks to mark. Invalid metadata, price direction or bounds mean no placement and an alert.

Before placement the service reads all pending position TP/SL pages. Any existing TP/SL is left untouched; this includes a safer manual SL, a weaker SL, TP-only, partial or unverified stop. Weaker/unverified stops trigger an alert and rely on the emergency monitor. No cancel/replace endpoint is used. Guardian ownership is recorded only from a successful returned orderId linked to that position; V1 never modifies an owned stop.

## Emergency and restart behavior

The emergency preflight re-reads the same single position and verifies unchanged positionId, side, quantity and leverage, reads pending TP/SL, then fetches a fresh mark and recomputes emergency state. If the risk has improved, it cancels the intent. Before a POST, `actions.jsonl` receives and fsyncs an INTENT. Response is stored in sanitized form, then fresh position reads confirm disappearance. Only disappearance confirms close and starts a 120 minute local Guardian lockout. That lockout is an alerting feature; it cannot prevent opening through Bitunix app.

On restart, the process loads state and journal before private reads and reconciles pending intents first. An unresolved close with the position still present is not POSTed again; alerts continue while the exchange state is read. Ambiguous timeouts never trigger blind retry. A stop intent with any existing order is reconciled without claiming ownership. Corrupt state, partial journal records or a second process fail closed. Manual disappearance is logged as `MANUAL_CLOSE_DETECTED`, with no new trade.

State defaults to `/data/guardian`: `state.json`, `actions.jsonl`, `positions.jsonl`, `bias.jsonl`, `alerts.jsonl`. State replacement is atomic and action appends use fsync. Do not share the same state directory between multiple service instances.

Telegram sends only outbound `sendMessage`; it never polls. Recipient routing matches the main bot: `TELEGRAM_BOT_TOKEN` enables delivery to the optional owner `TELEGRAM_CHAT_ID` and every non-empty comma-separated `TELEGRAM_ALERT_CHAT_ID`, stripping whitespace and deduplicating in order. Alert recipients alone are sufficient. Tokens and recipient IDs are never logged or persisted.

Every process announces startup and sends `💼 POSICIÓN ABIERTA DETECTADA` with the current verified human snapshot if a position already exists, including one recorded before restart. This position announcement happens once per process after a successful private read and risk assessment; an initial read failure defers it until recovery. Later new positions, manual closes, direction conflicts, material decision/entry changes, WARNING/DANGER/EMERGENCY, GUARDIAN BLIND and protection action intent/results retain deduplicated outbound alerts. There is no ten-second Telegram heartbeat.

Delivery uses a bounded background queue. Each recipient gets an initial attempt plus at most two retries, with 0.2/0.4-second backoff and bounded HTTP timeouts. Enqueueing does not claim delivery success. Logs report only `TELEGRAM_SEND_OK`, `TELEGRAM_DISABLED_NO_TOKEN`, `TELEGRAM_DISABLED_NO_RECIPIENT`, `TELEGRAM_SEND_TIMEOUT`, `TELEGRAM_SEND_HTTP_ERROR`, `TELEGRAM_SEND_NOT_OK` or `TELEGRAM_QUEUE_FULL`; no response body, URL, headers, token or recipient is exposed. Telegram failures remain nonfatal and never retry Bitunix actions or change risk/mutation rules. Heartbeat logs retain timestamp, mark, bias, position presence, risk, armed status and last successful reads, never API credentials.

## Failure limits

### Optional owner queries

`GUARDIAN_ENABLE_COMMANDS=false` is the default. Only the exact value `true` (case-insensitive) opts into a separate Telegram `getUpdates` worker. Only `TELEGRAM_CHAT_ID` can issue `/status`, `/why`, `/position`, `/risk`, `/levels` and `/help`; alert recipients cannot issue commands. Replies go only to the owner. Unknown commands return help; incoming content, chat IDs and Telegram responses are never logged or persisted. The worker reads a copied in-memory snapshot published by normal Guardian cycles, not the Bitunix client or control files. Commands cannot trade, arm, change leverage/margin, or trigger any private request. An unverified position is not reported as absent. Snapshot age is shown; over 30 seconds displays `DATOS DESACTUALIZADOS — NO TOMAR DECISIÓN`, and missing data says `SIN DATOS SUFICIENTES — NO OPERAR`. Command failures cannot stop risk cycles. Outbound-only operation remains the default.

Telegram's [official getUpdates contract](https://core.telegram.org/bots/api#getupdates) uses update offsets and allowed update types. This opt-in reader requests only ordinary messages, advances its in-memory offset and ignores unauthorized chats. Use a dedicated Guardian bot token if another process consumes updates for the main bot; Telegram polling consumers sharing one token compete for the same update stream. No Railway variables or deployment are changed by this PR.

### Consultas claras y niveles durante WAIT

Los niveles tienen dos escalas independientes: **R1/S1 locales 15m** y **R2/S2 estructurales 1H**, con la misma referencia 15m cerrada. Ambas usan pivotes estrictos de dos velas a cada lado; la segunda vela derecha debe haber cerrado. `/levels` muestra precios, distancias, timestamps de pivote/confirmación y ausencia de evidencia por escala; `/status` resume solo las escalas disponibles. La etiqueta «Muy cercano — nivel local/timing» aparece si un nivel local está a ≤0.15 ATR1H. Es presentación: nunca cambia dirección, entrada o protección. Cruzar un nivel por sí solo no confirma LONG/SHORT. `/why` puede mencionar esta proximidad como contexto.

Telegram muestra **DIRECCIÓN**: LONG CONFIRMADO, SHORT CONFIRMADO, SIN DIRECCIÓN CONFIRMADA o DATOS INSUFICIENTES. Una dirección confirmada sigue necesitando una entrada GOOD para mostrar permiso de buscar entrada. Las reglas de dirección, entrada, ML RSI27 LOW EMA4, flujo y estructura no cambian. La relación con una posición es informativa; una dirección opuesta no recomienda automáticamente cerrar ni activa el cierre.

`/status` añade un bloque compacto R/S cuando hay pivotes verificados. `/why` explica por separado las tendencias 4H/1H, momentum, flujo y estructura, qué confirmaciones faltan y qué evidencia cambiaría la decisión. `/position` muestra posición, PnL, liquidación y relación con la dirección. `/risk` distingue el stop verificado de un objetivo catastrófico **teórico** y en SHADOW dice expresamente que Guardian no lo colocará automáticamente. `/help` explica los seis comandos en español: solo consulta; nunca abren ni cierran operaciones.

`confirmed_market_levels(..., now_ms=...)` calcula niveles independientemente de la dirección y de la evaluación de entrada. El cutoff explícito excluye velas abiertas y futuras. Solo utiliza pivotes 15m estrictos de dos velas a izquierda/derecha, disponibles al cierre de la segunda vela de confirmación. La referencia es el último cierre 15m; el mark vivo no redefine niveles ni distancias. El soporte más cercano está estrictamente por debajo de esa referencia y la resistencia por encima. Los niveles previos son los últimos pivotes confirmados elegibles con precio distinto del más cercano. Se registran timestamps de pivote y confirmación, distancia porcentual y distancia en ATR14 **Binance 1H cerrado**. Esa distancia es contexto de mercado; el riesgo de liquidación continúa usando el ATR de Bitunix. Sin pivotes o ATR suficientes se muestra la ausencia de evidencia, sin inventar niveles.

`/levels` funciona también en WAIT. Muestra cierres 15m a vigilar sobre resistencia/bajo soporte y recuerda que aún hacen falta las confirmaciones habituales. En dirección confirmada puede mostrar el reclaim ya calculado y su invalidación técnica. Ningún nivel concede entrada ni se convierte en una orden. Los snapshots y la antigüedad de 30 segundos conservan su comportamiento anterior; no se añaden peticiones de mercado.

### Avisos TP/SL y fallos transitorios

Los avisos idénticos de TP/SL existente se agrupan y se envían al detectarlos. La memoria de notificaciones en `state.json` evita repetirlos por el cooldown general de cinco minutos, incluso dentro de mensajes de riesgo/contexto. Se vuelve a avisar al cambiar posición, estado TP/SL, desaparecer y reaparecer el aviso, escalar el riesgo, cambiar materialmente el objetivo, o cumplirse 60 minutos. Un cambio material del objetivo es al menos `max(0.25 ATR1H, 0.1% mark)` desde el último aviso; **solo** afecta a notificaciones, nunca al stop calculado o a una actuación. Las consultas mantienen el estado y el aviso completo, sin líneas duplicadas. Las órdenes manuales siguen sin cancelarse ni reemplazarse.

La **primera** verificación fallida sigue bloqueando inmediatamente cualquier mutación. Solo cambia el mensaje: primer fallo consecutivo amarillo (DATOS TEMPORALMENTE NO VERIFICABLES), segundo naranja (DATOS DEGRADADOS), tercero y posteriores rojo (GUARDIAN SIN DATOS FIABLES). Al recuperarse la verificación se envía una sola CONEXIÓN RECUPERADA y se reinicia el contador. El diagnóstico `GUARDIAN_BLIND_CODE` continúa siendo un código estático, sin payloads ni secretos. Una recuperación no arma Guardian ni cambia su modo. Los umbrales de riesgo y el cierre exclusivo por emergencia permanecen intactos.

El renderizador de V8 está en su propio código; este cambio de UX lo deja intacto, igual que su estrategia, ejecución y la investigación Early Breakout. No se modifican variables ni se despliega Railway. El modo predeterminado sigue siendo SHADOW/desarmado.

This version has no private subaccount enumeration, market-time endpoint, direct order cancellation, or recovery for a permanently ambiguous exchange response. Bitunix ticker responses document mark and last prices but no quote timestamp; freshness is therefore bounded by a successful current HTTP response, its server Date header and request latency, rather than an exchange quote timestamp. Check the Bitunix account and exchange orders manually after an unresolved emergency alert. A stale or invalid datum blocks mutations. The emergency endpoint gets at most one automatic call per position ID in v1; if a successful response leaves the position open, the Guardian escalates and waits for human/exchange resolution rather than sending blind duplicates.

`Guardian does not guarantee prevention of liquidation during gaps, outages, exchange failures or extreme slippage.`
