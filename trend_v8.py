"""I-GOD V8 Trend Core: independent SHADOW worker; no execution capability."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SYMBOL = "BTCUSDT"
FOUR_HOURS = 14_400_000
PERIODS = (125, 150, 175, 200, 225, 250, 300)
BASE = "https://fapi.bitunix.com"
READ_PATHS = frozenset({
    "/api/v1/futures/market/kline",
    "/api/v1/futures/account",
    "/api/v1/futures/position/get_pending_positions",
    "/api/v1/futures/position/get_history_positions",
    "/api/v1/futures/trade/get_history_trades",
})


def fingerprint(decision):
    """Canonical identity shared by SHADOW and REAL; contains no account data."""
    return hashlib.sha256(json.dumps(decision, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class BitunixReadOnly:
    """Exact endpoint allowlist and GET-only transport, including with live keys."""

    def __init__(self):
        self.key = os.getenv("BITUNIX_API_KEY", "").strip()
        self.secret = os.getenv("BITUNIX_SECRET_KEY", "").strip()

    def get(self, path, params):
        if path not in READ_PATHS:
            raise PermissionError("V8 SHADOW permits only allowlisted reads")
        headers = {}
        if path != "/api/v1/futures/market/kline":
            if not self.key or not self.secret:
                raise RuntimeError("Private observation requires Bitunix credentials")
            nonce, ts = secrets.token_hex(16), str(int(time.time() * 1000))
            query_sig = "".join(f"{k}{v}" for k, v in sorted(params.items()))
            digest = hashlib.sha256((nonce + ts + self.key + query_sig).encode()).hexdigest()
            sign = hashlib.sha256((digest + self.secret).encode()).hexdigest()
            headers = {"api-key": self.key, "nonce": nonce, "timestamp": ts,
                       "sign": sign, "language": "en-US"}
        request = Request(BASE + path + "?" + urlencode(params), headers=headers, method="GET")
        with urlopen(request, timeout=12) as response:
            payload = json.load(response)
        if payload.get("code") != 0:
            raise RuntimeError(f"Bitunix read failed: code={payload.get('code')}")
        return payload.get("data")

    def candles(self, now_ms):
        rows, end = [], now_ms
        for _ in range(3):
            batch = self.get("/api/v1/futures/market/kline", {
                "symbol": SYMBOL, "interval": "4h", "endTime": end,
                "limit": 200, "type": "LAST_PRICE"}) or []
            if not batch:
                break
            rows.extend(batch)
            oldest = min(int(r["time"]) for r in batch)
            if oldest >= end:
                break
            end = oldest - 1
            if len(rows) >= 301:
                break
        return rows

    def observe(self):
        if not self.key and not self.secret:
            return {"status": "NO_CREDENTIALS", "positions": [], "reconciled": []}
        account = self.get("/api/v1/futures/account", {"marginCoin": "USDT"}) or {}
        if isinstance(account, list):
            account = account[0] if account else {}
        equity = sum(float(account.get(k, 0)) for k in (
            "available", "frozen", "margin", "crossUnrealizedPNL", "isolationUnrealizedPNL"))
        positions = self.get("/api/v1/futures/position/get_pending_positions", {"symbol": SYMBOL}) or []
        if isinstance(positions, dict):
            positions = positions.get("positionList", [])
        history = self.get("/api/v1/futures/position/get_history_positions", {
            "symbol": SYMBOL, "limit": 100}) or {}
        history = history if isinstance(history, list) else history.get("positionList", [])
        reconciled = []
        for row in history:
            pid = row.get("positionId")
            if not pid:
                continue
            trades = self.get("/api/v1/futures/trade/get_history_trades", {
                "symbol": SYMBOL, "positionId": pid, "limit": 100}) or {}
            trades = trades if isinstance(trades, list) else trades.get("tradeList", [])
            # Never label missing/truncated fills as a fully reconciled result.
            if not trades or len(trades) >= 100:
                reconciled.append({"position_id": pid, "status": "INCOMPLETE"})
                continue
            gross = sum(float(t.get("realizedPNL", 0)) for t in trades)
            fee = sum(abs(float(t.get("fee", 0))) for t in trades)
            funding = float(row.get("funding", 0))
            reconciled.append({"position_id": pid, "status": "OBSERVED_FILLS",
                               "gross": gross, "fee": fee, "funding": funding,
                               "net": gross - fee + funding})
        return {"status": "READ_ONLY", "equity_estimate": equity,
                "positions": positions, "reconciled": reconciled,
                "ownership": "EXTERNAL_TO_V8", "history_limit": 100}


def closed_candles(rows, now_ms):
    closed = {}
    for row in rows:
        timestamp, close = int(row["time"]), float(row["close"])
        if timestamp < 0 or timestamp % FOUR_HOURS or not math.isfinite(close) or close <= 0:
            raise ValueError("Invalid 4H candle")
        if timestamp + FOUR_HOURS <= now_ms - 1500:
            if timestamp in closed and closed[timestamp] != close:
                raise ValueError("Conflicting duplicate candle")
            closed[timestamp] = close
    times = sorted(closed)
    if len(times) < 200:
        raise ValueError("Need at least 200 completely closed 4H candles")
    expected = ((now_ms - 1500) // FOUR_HOURS - 1) * FOUR_HOURS
    if times[-1] != expected or any(b - a != FOUR_HOURS for a, b in zip(times, times[1:])):
        raise ValueError("Stale or discontinuous 4H candles")
    return [{"time": t, "close": closed[t]} for t in times]


def decision_at(rows):
    """Rows end at the decision candle; no future information is visible."""
    closes = [row["close"] for row in rows[-300:]]
    telemetry = {}
    for period in PERIODS:
        average = sum(closes[-period:]) / period if len(closes) >= period else None
        telemetry[str(period)] = {"sma": average, "direction": (
            "LONG" if closes[-1] > average else "FLAT") if average is not None else None}
    return {"candle_time": rows[-1]["time"], "close": closes[-1],
            "direction": telemetry["200"]["direction"], "comparison": telemetry}


def signal(rows, now_ms):
    return decision_at(closed_candles(rows, now_ms))


def pending_decisions(rows, now_ms, last_candle):
    """Validate the entire replay before allowing any state mutation."""
    closed = closed_candles(rows, now_ms)
    if last_candle == -1:
        return [decision_at(closed)]  # bootstrap, not a historical crossover
    if last_candle > closed[-1]["time"]:
        raise ValueError("Persisted candle is ahead of available data")
    pending = [i for i, row in enumerate(closed) if row["time"] > last_candle]
    if not pending:
        return []
    first = pending[0]
    if closed[first]["time"] != last_candle + FOUR_HOURS or first < 199:
        raise ValueError("Insufficient history for complete SMA200 replay")
    return [decision_at(closed[:i + 1]) for i in pending]


class ShadowCore:
    def __init__(self, directory, initial_equity=1000.0, turnover_cost=None):
        if not math.isfinite(initial_equity) or initial_equity <= 0:
            raise ValueError("Initial shadow equity must be positive and finite")
        if turnover_cost is None:
            turnover_cost = float(os.getenv("V8_SHADOW_TURNOVER_COST", "0.001"))
        if not math.isfinite(turnover_cost) or not 0 <= turnover_cost < 1:
            raise ValueError("Turnover cost must be finite and in [0, 1)")
        self.turnover_cost = turnover_cost
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "igod_v8_shadow_state.json"
        self.journal = self.directory / "igod_v8_shadow_journal.jsonl"
        self.state = {"version": "V8", "mode": "SHADOW", "last_candle": -1,
                      "cash": initial_equity, "qty": 0.0, "entry": 0.0,
                      "schema": 2, "initial_equity": initial_equity,
                      "turnover_cost": turnover_cost, "costs_accumulated": 0.0,
                      "entry_cost": 0.0, "realized_gross": 0.0, "realized_net": 0.0,
                      "equity_net": initial_equity, "pnl_net": 0.0, "pnl_gross": 0.0}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.state["mode"] != "SHADOW" or self.state["version"] != "V8":
                raise ValueError("Invalid V8 SHADOW state")
            self.validate_state(self.state)

    def validate_state(self, state):
        if state.get("schema") != 2:
            raise ValueError("Legacy gross state requires a separate directory; cannot invent past costs")
        if state.get("turnover_cost") != self.turnover_cost:
            raise ValueError("Cannot change turnover cost for an existing simulation")

    def step(self, decision, observation):
        self.recover()
        if decision["candle_time"] <= self.state["last_candle"]:
            return None
        if decision["direction"] not in ("LONG", "FLAT"):
            raise ValueError("V8 never permits SHORT")
        if self.state["last_candle"] != -1 and decision["candle_time"] != self.state["last_candle"] + FOUR_HOURS:
            raise ValueError("Shadow decisions must be sequential")
        state = dict(self.state)
        price = decision["close"]
        equity = state["cash"] + state["qty"] * price
        action = "HOLD"
        cost = notional = 0.0
        if decision["direction"] == "LONG" and state["qty"] == 0 and equity > 0:
            # Fund the actual 1x position AND its fee without borrowing cash.
            notional = equity / (1 + self.turnover_cost)
            cost = notional * self.turnover_cost
            state.update(qty=notional / price, cash=0.0, entry=price, entry_cost=cost)
            action = "BOOTSTRAP_LONG" if state["last_candle"] == -1 else "SIMULATED_LONG"
        elif decision["direction"] == "FLAT" and state["qty"] > 0:
            notional = state["qty"] * price
            cost = notional * self.turnover_cost
            state["realized_gross"] += state["qty"] * (price - state["entry"])
            state["realized_net"] += state["qty"] * (price - state["entry"]) - state["entry_cost"] - cost
            state.update(cash=equity - cost, qty=0.0, entry=0.0, entry_cost=0.0)
            action = "SIMULATED_FLAT"
        state["costs_accumulated"] += cost
        state["equity_net"] = state["cash"] + state["qty"] * price
        state["pnl_net"] = state["equity_net"] - state["initial_equity"]
        state["pnl_gross"] = state["pnl_net"] + state["costs_accumulated"]
        state["last_candle"] = decision["candle_time"]
        event = {"version": "V8", "mode": "SHADOW", "symbol": SYMBOL,
                 "event_id": f"v8-{decision['candle_time']}", "action": action,
                 "fingerprint": fingerprint(decision),
                 "decision": decision, "shadow_equity": state["equity_net"],
                 "equity_net": state["equity_net"], "pnl_net": state["pnl_net"],
                 "pnl_gross": state["pnl_gross"], "realized_net": state["realized_net"],
                 "realized_gross": state["realized_gross"],
                 "costs_accumulated": state["costs_accumulated"],
                 "turnover_notional": notional, "turnover_cost": cost,
                 "target_notional": state["equity_net"] if decision["direction"] == "LONG" else 0,
                 "exposure_multiple": 1.0, "state_after": state,
                 "account_observation": observation,
                 "pnl_model": "NET: turnover notional * configured cost on entry and exit; HOLD zero"}
        # Journal is the recovery source if the process stops before state replacement.
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.save(state)
        return event

    def save(self, state):
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(state, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.state = state

    def recover(self):
        if self.journal.exists():
            with self.journal.open(encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    self.validate_state(event["state_after"])
                    if event["state_after"]["last_candle"] > self.state["last_candle"]:
                        self.save(event["state_after"])

    def replay(self, rows, now_ms, observation):
        self.recover()
        decisions = pending_decisions(rows, now_ms, self.state["last_candle"])
        events = []
        for decision in decisions:
            events.append(self.step(decision, observation))
        return events


def notify(event):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    recipients = {os.getenv(k, "").strip() for k in ("TELEGRAM_CHAT_ID", "TELEGRAM_ALERT_CHAT_ID")}
    if not token:
        return
    for chat in recipients - {""}:
        body = urlencode({"chat_id": chat, "text": (
            f"I-GOD V8 SHADOW BTCUSDT 4H: {event['decision']['direction']}\n"
            f"{event['action']} | exposición objetivo 1x | simulación sin órdenes reales\n"
            f"Equity NETO: {event['equity_net']:.4f} USDT | PnL NETO: {event['pnl_net']:.4f} USDT")}).encode()
        with urlopen(Request(f"https://api.telegram.org/bot{token}/sendMessage",
                             data=body, method="POST"), timeout=12) as response:
            if not json.load(response).get("ok"):
                raise RuntimeError("Telegram notification failed")


def run():
    if os.getenv("V8_MODE", "SHADOW").upper() != "SHADOW":
        raise RuntimeError("V8 only supports SHADOW")
    directory = Path(os.getenv("V8_DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."))) / "v8"
    core = ShadowCore(directory, float(os.getenv("V8_SHADOW_INITIAL_EQUITY", "1000")))
    core.recover()
    api = BitunixReadOnly()
    while True:
        try:
            core.recover()
            now = int(time.time() * 1000)
            rows = api.candles(now)
            decisions = pending_decisions(rows, now, core.state["last_candle"])
            if decisions:
                try:
                    observation = api.observe()
                except Exception:
                    observation = {"status": "READ_ERROR"}
                # Current account observation is explicitly separate from historical decisions.
                observation["observed_at_ms"] = int(time.time() * 1000)
                events = core.replay(rows, now, observation)
                for event in events:
                    notify(event)
        except Exception as exc:
            # Never print credentials or Telegram URLs from transport exceptions.
            print(f"V8 SHADOW cycle failed: {type(exc).__name__}", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    run()
