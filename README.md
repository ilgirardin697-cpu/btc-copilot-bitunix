# BTCUSDT COPILOT — BITUNIX + TELEGRAM

This project is an analysis/alert bot. It **does not place orders** and does not use Bitunix private API keys.

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
