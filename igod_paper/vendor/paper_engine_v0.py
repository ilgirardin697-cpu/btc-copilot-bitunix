"""Research-only I-GOD paper execution. No exchange, network, credentials, or live orders.

Uses signal known at bar close; executes at NEXT bar's open. All timestamps UTC;
regular 5-minute CLOSED bars only. A same-bar stop+target collision counts as STOP.
This prototype is deliberately not a validated profitable strategy.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Iterable
import csv
import json
import sys


@dataclass(frozen=True)
class Config:
    starting_equity: float = 140.0
    risk_pct: float = 0.005           # 0.5% of equity per trade, including assumed fees/slippage
    max_daily_loss_pct: float = 0.02  # no new trades after daily realized equity loss >= 2%
    max_trades_day: int = 2
    max_notional_multiple: float = 2.0  # max paper exposure / equity; NOT authorization for exchange leverage
    atr_stop_multiple: float = 1.5
    reward_to_risk: float = 1.5
    fee_bps_per_side: float = 6.0
    slippage_bps_per_side: float = 3.0
    qty_step: float = 0.0001
    minimum_notional: float = 5.0
    cooldown_bars: int = 2


@dataclass(frozen=True)
class Bar:
    ts: int                    # Unix seconds, UTC 5m open timestamp
    open: float
    high: float
    low: float
    close: float
    atr: float                 # ATR known at this candle's CLOSE
    signal: str = "WAIT"       # LONG_ALLOWED / SHORT_ALLOWED / WAIT / UNKNOWN
    quality: str = "CAUTION"  # GOOD / CAUTION / POOR


@dataclass
class Position:
    side: str
    qty: float
    entry_ts: int
    entry: float
    stop: float
    target: float
    entry_fee: float


def _validate(rows: list[Bar], cfg: Config) -> None:
    if not (0 < cfg.risk_pct <= .02 and 0 < cfg.max_daily_loss_pct <= .05):
        raise ValueError("Invalid risk limits")
    if not (0 < cfg.max_notional_multiple <= 3 and cfg.max_trades_day > 0):
        raise ValueError("Invalid exposure/trade limits")
    if min(cfg.starting_equity, cfg.atr_stop_multiple, cfg.reward_to_risk,
           cfg.qty_step, cfg.minimum_notional) <= 0:
        raise ValueError("Invalid configuration")
    if cfg.fee_bps_per_side < 0 or cfg.slippage_bps_per_side < 0:
        raise ValueError("Invalid estimated costs")
    for n, bar in enumerate(rows):
        if bar.ts % 300 or (n and bar.ts != rows[n - 1].ts + 300):
            raise ValueError("Unclosed, duplicated or gapped 5m timestamps; fail closed")
        if not (0 < bar.low <= min(bar.open,bar.close) <= max(bar.open,bar.close) <= bar.high):
            raise ValueError("Invalid OHLC; fail closed")
        if bar.atr <= 0:
            raise ValueError("Unknown ATR; fail closed")
        if bar.signal not in ("LONG_ALLOWED", "SHORT_ALLOWED", "WAIT", "UNKNOWN"):
            raise ValueError("Unknown signal")
        if bar.quality not in ("GOOD", "CAUTION", "POOR"):
            raise ValueError("Unknown quality")


def _floor_qty(q: float, step: float) -> float:
    return float((Decimal(str(q)) / Decimal(str(step))).to_integral_value(rounding=ROUND_DOWN) * Decimal(str(step)))


def run(bars: Iterable[Bar], config: Config = Config()) -> dict:
    """No external calls. Feeds verified closed OHLC and Copilot decisions as inputs."""
    rows = list(bars)
    _validate(rows, config)
    equity = config.starting_equity
    trades: list[dict] = []
    events: list[dict] = []
    pos: Position | None = None
    prev: Bar | None = None
    current_day = None
    day_equity = equity
    trades_today = 0
    cooldown_to = -1
    cost_rate = (config.fee_bps_per_side + config.slippage_bps_per_side) / 10000
    fee_rate = config.fee_bps_per_side / 10000
    slip_rate = config.slippage_bps_per_side / 10000
    for i, bar in enumerate(rows):
        day = datetime.fromtimestamp(bar.ts, tz=timezone.utc).date()
        if day != current_day:
            current_day = day
            day_equity = equity
            trades_today = 0
        # Previous confirmed bar authorizes only the NEXT bar's open.
        if pos is None and prev is not None and i > cooldown_to:
            direction = prev.signal
            if direction in ("LONG_ALLOWED", "SHORT_ALLOWED") and prev.quality == "GOOD":
                if equity <= day_equity * (1 - config.max_daily_loss_pct):
                    events.append({"ts":bar.ts,"event":"BLOCKED_DAILY_LOSS"})
                elif trades_today >= config.max_trades_day:
                    events.append({"ts":bar.ts,"event":"BLOCKED_TRADES_DAY"})
                else:
                    side = "LONG" if direction == "LONG_ALLOWED" else "SHORT"
                    execution_entry = bar.open * (1 + slip_rate if side == "LONG" else 1 - slip_rate)
                    stop_distance = prev.atr * config.atr_stop_multiple
                    # Conservative cost at both sides; fees and slippage reduce size.
                    per_unit_risk = stop_distance + (2 * execution_entry * cost_rate)
                    risk_cash = equity * config.risk_pct
                    qty = _floor_qty(min(risk_cash/per_unit_risk,
                                         config.max_notional_multiple*equity/execution_entry),config.qty_step)
                    if qty * execution_entry < config.minimum_notional or qty <= 0:
                        events.append({"ts":bar.ts,"event":"BLOCKED_MINIMUM_SIZE_OR_RISK"})
                    else:
                        stop = execution_entry - stop_distance if side == "LONG" else execution_entry + stop_distance
                        target = execution_entry + stop_distance*config.reward_to_risk if side == "LONG" else execution_entry - stop_distance*config.reward_to_risk
                        if stop <= 0 or target <= 0:
                            events.append({"ts":bar.ts,"event":"BLOCKED_INVALID_LEVELS"})
                        else:
                            entry_fee = qty*execution_entry*fee_rate
                            equity -= entry_fee
                            pos = Position(side,qty,bar.ts,execution_entry,stop,target,entry_fee)
                            trades_today += 1
                            events.append({"ts":bar.ts,"event":"PAPER_OPEN","side":side,"qty":qty})
        # Stop before target on collision, with adverse gap opening and slippage.
        if pos:
            hit_stop = bar.low <= pos.stop if pos.side == "LONG" else bar.high >= pos.stop
            hit_target = bar.high >= pos.target if pos.side == "LONG" else bar.low <= pos.target
            if hit_stop or hit_target:
                reason = "STOP" if hit_stop else "TARGET"
                raw = (min(bar.open,pos.stop) if pos.side=="LONG" else max(bar.open,pos.stop)) if hit_stop else pos.target
                fill = raw*(1-slip_rate if pos.side=="LONG" else 1+slip_rate)
                gross = (fill-pos.entry)*pos.qty*(1 if pos.side=="LONG" else -1)
                exit_fee = pos.qty*fill*fee_rate
                net = gross-pos.entry_fee-exit_fee
                equity += gross-exit_fee
                trades.append({"side":pos.side,"entry_ts":pos.entry_ts,"exit_ts":bar.ts,
                               "qty":pos.qty,"entry":pos.entry,"exit":fill,
                               "reason":reason,"gross_pnl":round(gross,6),
                               "fees":round(pos.entry_fee+exit_fee,6),"net_pnl":round(net,6),
                               "equity_after":round(equity,6)})
                events.append({"ts":bar.ts,"event":"PAPER_CLOSE","reason":reason})
                pos = None
                cooldown_to = i + config.cooldown_bars
        prev = bar
    last_close = rows[-1].close if rows else None
    unrealized = None if pos is None or last_close is None else (last_close-pos.entry)*pos.qty*(1 if pos.side=="LONG" else -1)
    return {"mode":"PAPER_ONLY_NO_LIVE_API", "starting_equity":config.starting_equity,
            "realized_equity":round(equity,6),"closed_trades":trades,"events":events,
            "open_paper_position":asdict(pos) if pos else None,
            "unrealized_pnl_before_costs":round(unrealized,6) if unrealized is not None else None,
            "limitations":"Requires authentic, closed, gap-free five-minute OHLC and causal confirmed signals; no Binance/Bitunix connectivity. Costs hypothetical, no live fills, no proof of profitability."}


def _read_csv(path: str) -> list[Bar]:
    with open(path, newline="",encoding="utf-8") as f:
        return [Bar(ts=int(d["ts"]),open=float(d["open"]),high=float(d["high"]),
                    low=float(d["low"]),close=float(d["close"]),atr=float(d["atr"]),
                    signal=d.get("signal") or "WAIT",quality=d.get("quality") or "CAUTION")
                for d in csv.DictReader(f)]

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python paper_engine.py confirmed_5m_bars_with_copilot_signals.csv")
    print(json.dumps(run(_read_csv(sys.argv[1])),indent=2,ensure_ascii=False))
