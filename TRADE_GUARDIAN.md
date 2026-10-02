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

The position API may return subaccounts. V1 explicitly disables subaccounts and rejects any returned nonzero `subAccountId`, multiple positions, hedge ambiguity, unsupported position mode, invalid quantity/side/leverage or invalid liquidation price. API schema or exchange behavior changes fail closed. The client does not call any trading order, bulk order, close-all, leverage, margin, transfer or withdrawal route.

## Manual Copilot V1

Only closed candles are used. Four-hour and one-hour trend are close versus SMA200. Momentum ports the causal rolling BackQuant-style ML RSI calculation from the prior research into a pure module: RSI27 (Wilder RMA seed), EMA4, up to 3000 available smoothed RSI samples, three clusters initialized at p25/p50/p75, absolute distance assignments and arithmetic-mean centers. Green/red state compares RSI with high/low center; events are transitions from a valid neutral candle. RSI14 is not a directional gate. This is a causal algorithm implementation, not an assertion of byte-for-byte TradingView parity; empty clusters retain their prior center.

Flow classifies closed 1h Binance taker-buy base-volume ratio: at least 60% strong buy, 55–60% buy, 45–55% neutral, 40–45% sell and at most 40% strong sell. A 15m structure uses unique two-left/two-right pivots only after both right candles have closed. It requires two higher highs and higher lows for bullish, or lower highs and lower lows for bearish; otherwise mixed.

Frozen `MANUAL_COPILOT_V1` permits LONG only when 4H and 1H are both bullish and at least two of ML green, flow at least 55%, and bullish 15m structure agree. SHORT mirrors that condition in jointly bearish regimes. Disagreeing trends produce WAIT; insufficient data produces UNKNOWN. Volatility is risk context, never a directional vote. For display only, ATR1H/mark below 2% is NORMAL, 2–4% is ELEVATED and at least 4% is HIGH; these bands do not change liquidation thresholds. Koncorde is `UNAVAILABLE_NOT_REPRODUCIBLE` and is not used as a gate.

## Position and risk states

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

Telegram sends only outbound `sendMessage`; it never polls. Startup, new position, direction conflict, risk escalation, lockout, blind state and emergency confirmation are deduplicated. Telegram failure cannot stop the risk loop. Logs/heartbeat expose timestamp, mark, bias, position presence, risk, armed status and last successful reads, never API credentials.

## Failure limits

This version has no private subaccount enumeration, market-time endpoint, direct order cancellation, or recovery for a permanently ambiguous exchange response. Bitunix ticker responses document mark and last prices but no quote timestamp; freshness is therefore bounded by a successful current HTTP response, its server Date header and request latency, rather than an exchange quote timestamp. Check the Bitunix account and exchange orders manually after an unresolved emergency alert. A stale or invalid datum blocks mutations. The emergency endpoint gets at most one automatic call per position ID in v1; if a successful response leaves the position open, the Guardian escalates and waits for human/exchange resolution rather than sending blind duplicates.

`Guardian does not guarantee prevention of liquidation during gaps, outages, exchange failures or extreme slippage.`
