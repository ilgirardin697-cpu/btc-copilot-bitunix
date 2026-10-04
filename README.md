# BTCUSDT COPILOT — BITUNIX + TELEGRAM

The existing V8/V7 copilot is an analysis/alert bot. The separate I-GOD Trade Guardian described in [TRADE_GUARDIAN.md](TRADE_GUARDIAN.md) is a new optional service with a restricted Bitunix private read and capital protection client; it starts in SHADOW and is not deployed by this repository's Railway entrypoint.

`trade_guardian.py` hosts a [passive ML RSI 15m/1H/4H observer](docs/MLRSI_MTF_OBSERVER.md) using the current **LOW / Wilder RSI29 / EMA4** captured preset and explicit **PINE_PARITY persistent-array contract**, automatic observational Telegram alerts and cached `/mlrsi` through the existing `guardian_commands.py` poller. It always has `trade_authority=false`, uses separate `/data/mlrsi` storage and cannot affect protection or execution decisions. Frozen RSI27 research remains unchanged. The real V8 service continues on `v8-real-executor` with `python v8_executor.py`, unchanged. `live_auto.py` has no ML RSI hooks. Exact BackQuant TradingView parity is NOT proven. No deployment configuration is changed.

## What it does

- Source: Bitunix BTCUSDT Futures.
- Closed-candle analysis: 1W, 1D, 4H, 1H, 15m, 5m.
- Real-time public WebSocket: market price, 15-level order book and public trades.
- Indicators: EMA 20/50/200, RSI, MACD, AO, ATR, ADX/+DI/-DI, rolling VWAP, volume z-score, Donchian, pivots/structure and RSI divergences.
- Separates **bias** from **entry permission**.
- States:
  - ENTER LONG NOW
  - ENTER SHORT NOW
  - WAIT
  - TOO LATE
  - NO TRADE
- Sends Telegram alerts on confirmed entries, bias changes and a daily plan.
- Telegram commands: `/status`, `/plan`, `/pause`, `/resume`, `/help`.

## Important design rule

A bearish 1H RSI cannot, by itself, turn a bullish 1D/4H context into a SHORT. Higher-timeframe structure has priority.

## Secrets

Never commit your Telegram token to GitHub. Put it only in Railway Variables.

Required Railway variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional variables are documented in `.env.example`.

## Railway

`railway.json` starts the persistent worker with:

`python main.py`

No public domain is required because Telegram messages are sent outbound and Bitunix data is read outbound.

## I-GOD Trade Guardian

Consulta el [mapa operativo de I-GOD](docs/I_GOD_OPERATING_MAP.md) para distinguir Manual Copilot, Guardian, auditoría forward, V8 y Early Breakout, y entender las consultas Telegram.

The independent manual position risk monitor is started explicitly with `python trade_guardian.py`. It is disarmed by default; see [TRADE_GUARDIAN.md](TRADE_GUARDIAN.md) and [.env.example](.env.example) for its endpoint allowlist, risk behavior and arming requirements. Railway continues to run `main.py`.
