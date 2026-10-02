# I-GOD Early Breakout Shadow

This separate public-market observer issues early warnings. It never grants entry permission, never receives Bitunix account credentials, and has no account client, order endpoint or Guardian risk/execution dependency. V8 and Guardian decisions remain independent. Run `python early_breakout_shadow.py`; this PR does not deploy it.

The frozen parameters are in [frozen_parameters.json](research/early_breakout_artifacts/frozen_parameters.json), selected from TRAIN 2020–2021 and VALIDATION 2022–2023. TEST 2024 onward cannot select parameters. The later-closed-candle hold is mandatory in the forward observer; the zero-hold research control is rejected. Full research methods, historical counts, five MFE/MAE horizons, barrier outcomes, yearly/regime/side results, block bootstrap and neighboring parameter checks are in [EARLY_BREAKOUT_RESULTS.md](research/early_breakout_artifacts/EARLY_BREAKOUT_RESULTS.md) and its reproducible JSON artifacts. A research label does not turn this observer into a trading strategy.

The only market endpoint is `GET https://data-api.binance.vision/api/v3/klines`, without API headers or credentials. Closed 15m candles define every signal. Causal ATR14 percentile uses the **prior** 100 closed ATR observations; current ATR is excluded from that reference. Volume20 z-score and EMA12/26/9 MACD acceleration match the main bot formulas. Higher/lower range boundaries belong only to the current consecutive compression episode. Breakout tests the previously known range, then freezes it, so the breakout candle cannot widen the level it is breaking.

States are NONE, SQUEEZE WATCH (direction unknown), DEVELOPING LONG/SHORT, LONG/SHORT CONFIRMING after a later closed-candle hold, or RELEASE FAILED. Compression that ends without a qualifying release expires after four closed candles; a held release expires four closed candles after confirming. Volume/momentum gate failure is recorded separately from return inside range after a qualified developing event. A new compression episode is required for a new direction. Every Telegram alert says `NO ENTRAR` and `SHADOW / NO ES UNA ORDEN DE ENTRADA`.

The observer polls every 45 seconds and updates signals only on new closed candles. `EARLY_BREAKOUT_STATE_DIR` defaults to `/data/early_breakout`. It maintains `state.json`, `events.jsonl`, `outcomes.jsonl`, and `snapshots.jsonl`, plus a process lock. State replacement is atomic; journal appends and state writes fsync. On restart it restores indicator history and episode boundaries; duplicate candle IDs do not replay alerts. An event is journaled before alert enqueue. A crash in between can lose an alert, but cannot intentionally enqueue that same event twice after restart. Historical warm-up transitions do not flood Telegram; delayed replay is labeled and journaled without stale alerts. Corrupt/torn state or a second process fails safe. No trading recovery action exists.

After 48h, forward outcomes use closed public 5m candles. They record both hypothetical directions for a nondirectional squeeze and the observed developing direction otherwise. All 1/4/12/24/48h paths start after the signal closes. Same-bar double touches count adverse first; missing/gapped or over-seven-day unrecoverable paths are censored, never invented. A market outage produces fresh=false/NONE with no new signals; Telegram failures are nonfatal. Polling resumes public reads only.

Telegram uses `TELEGRAM_BOT_TOKEN`, optional `TELEGRAM_CHAT_ID` and comma-separated `TELEGRAM_ALERT_CHAT_ID`, with the same unique-recipient outbound queue as Guardian. It never imports the command module or calls getUpdates. No Bitunix key or secret is read. The snapshot schema is `state.json["latest"]`; times are Unix milliseconds:

```json
{
  "state": "NONE",
  "timestamp": 1790956800000,
  "compression_high": null,
  "compression_low": null,
  "atr_percentile": null,
  "vol_z": null,
  "fresh": false,
  "entry_permission": false
}
```

This is an unavailable-data example. Real boundaries are validated candle prices; unavailable fields are null. Public states are SQUEEZE_WATCH, DEVELOPING_LONG/SHORT, CONFIRMING_LONG/SHORT or NONE. A failed release exposes public state NONE with `event_state=RELEASE_FAILED`; the journal retains the terminal diagnostic. Fresh means the latest expected closed 15m candle was verified. Guardian may consume this copied public schema in a later PR; it does not depend on it now.

Historical spot archives and their official SHA256 sidecars stay in ignored `research/cache/early_breakout`; the tracked manifest includes exact URLs, dates, rows, checksums and REST parameters. The 2025 microsecond archive timestamp change is normalized explicitly. The ~82.6k→~84k motivating move is diagnostic only and requires a precise dated window; no arbitrary lookalike is cherry-picked and no parameter is changed to capture it.

`EARLY BREAKOUT DOES NOT GRANT ENTRY PERMISSION`

`GUARDIAN AUTO-CLOSE REMAINS EMERGENCY-ONLY`

`PROTECT REMAINS DISARMED`

`V8 WAS NOT MODIFIED`
