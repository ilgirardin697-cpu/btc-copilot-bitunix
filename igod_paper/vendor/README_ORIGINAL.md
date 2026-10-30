# I-GOD — Shadow Paper Execution v0 (research-only)

**Never places real orders.** Standalone offline simulation engine. No network,
Bitunix account client, secrets, Telegram, Railway changes or production imports.

This is a technical building block, **not** a profitable trading strategy.
It uses 5m candles and externally provided confirmed Copilot signals; it **does not**
create or validate such signals. Backtest results must not be advertised as live results.

Run `python -m unittest -v test_paper_engine.py` from this directory.

To simulate with authentic data:

```bash
python paper_engine.py confirmed_5m_bars_with_copilot_signals.csv > paper_results.json
```

Input CSV: `ts,open,high,low,close,atr,signal,quality`; `ts` is a UTC
Unix timestamp for the 5m candle open; rows must have no gaps. `atr` and
`signal` are features **known only at this row's close**, therefore entries
are submitted at the **next** 5m open, not at the signal close. Values must
come from the same venue and have verified historical availability. Live signal
observation after bar close introduces additional delay, not yet modeled.

Rules: only signal `LONG_ALLOWED` / `SHORT_ALLOWED` together with `GOOD`;
position size capped by conservative estimated stop risk and notional exposure,
trades/day and daily realized loss; one paper position at a time. ATR14 is an
INPUT and must be computed causally and consistently upstream. 1.5×ATR
stop and 1.5R target are **illustrative defaults**, not validated thresholds.
Worst-case stop first on same-bar stop/target collision. Gap-through-stop
uses adverse next open. Costs are assumptions (6bps fee +3bps slippage/side)
and may underestimate real fills. Entry fees are deducted even for open trades.
Remaining open positions are not force-closed at the end of a file.

Important limitations: no liquidation simulation; no funding, spreads, venue
min-size validation, liquidation rules, variable fee tiers, delayed observation,
retries, exchange order reconciliation, downtime modeling or actual live feed.
The daily loss guard does not guarantee maximum realized or intraday loss.
Never enable live trading on the basis of this module alone.

**Promotion gates before considering live trading:** real forward collection,
correct data parity, multi-regime out-of-sample evaluation after real costs,
minimum sample size, maximum drawdown, account reconciliation, emergency stop,
permissions review, human approval and independent safety review.

`TRADE AUTHORITY: NONE` — does not touch V8, Guardian or any Railway service.
