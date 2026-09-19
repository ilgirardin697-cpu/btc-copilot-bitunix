#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I-GOD BTC Copilot V5 — REAL AUTO EXECUTOR for Bitunix
======================================================

WARNING: THIS FILE CAN PLACE REAL ORDERS when BOTH are true:
    LIVE_EXECUTION=true
    LIVE_AUTO_START=true

Design:
- Reuses main.py (V3 Planner) for analysis.
- ONE signal cycle = ONE real entry.
- Never re-enters while the same ENTER NOW cycle remains active.
- Checks Bitunix for an existing BTCUSDT position before every entry.
- Uses deterministic clientId and checks exchange order history for duplicates.
- Market entry, native protective SL, native partial TP1/TP2/TP3.
- After TP1 -> stop ~breakeven.
- After TP2 -> stop +1R.
- After TP3 -> stop +2R, then runner trailing.
- Verifies REAL leverage, margin mode, position mode, qty, margin and entry.
- If leverage/margin mode/position mode is wrong after entry: emergency close + lock.
- State persists to Railway Volume when mounted at /data.

This is intentionally strict because it can move real money.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

import main as C


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

API_KEY = os.getenv("BITUNIX_API_KEY", "").strip()
SECRET_KEY = os.getenv("BITUNIX_SECRET_KEY", "").strip()

LIVE_EXECUTION = os.getenv("LIVE_EXECUTION", "false").lower() == "true"
LIVE_AUTO_START = os.getenv("LIVE_AUTO_START", "false").lower() == "true"

# FIRST REAL RUN DEFAULTS ARE DELIBERATELY SMALL.
LIVE_MARGIN_USDT = float(os.getenv("LIVE_MARGIN_USDT", "2"))
LIVE_LEVERAGE = int(os.getenv("LIVE_LEVERAGE", "20"))
LIVE_MARGIN_MODE = os.getenv("LIVE_MARGIN_MODE", "CROSS").strip().upper()
LIVE_MAX_RISK_USDT = float(os.getenv("LIVE_MAX_RISK_USDT", "10"))

LIVE_MAX_TRADES_DAY = int(os.getenv("LIVE_MAX_TRADES_DAY", "2"))
LIVE_COOLDOWN_MIN = int(os.getenv("LIVE_COOLDOWN_MIN", "60"))
LIVE_MAX_DAILY_LOSS_USDT = float(os.getenv("LIVE_MAX_DAILY_LOSS_USDT", "2"))

LIVE_TP1_PCT = float(os.getenv("LIVE_TP1_PCT", "25")) / 100
LIVE_TP2_PCT = float(os.getenv("LIVE_TP2_PCT", "25")) / 100
LIVE_TP3_PCT = float(os.getenv("LIVE_TP3_PCT", "25")) / 100
LIVE_RUNNER_TRAIL_R = float(os.getenv("LIVE_RUNNER_TRAIL_R", "1.5"))
LIVE_BE_BUFFER_PCT = float(os.getenv("LIVE_BE_BUFFER_PCT", "0.0015"))

VERIFY_MARGIN_TOL_PCT = float(os.getenv("VERIFY_MARGIN_TOL_PCT", "35")) / 100
MANAGE_SECONDS = int(os.getenv("LIVE_MANAGE_SECONDS", "10"))

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()

volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
if volume:
    STATE_FILE = Path(volume) / "igod_live_state.json"
else:
    STATE_FILE = Path("igod_live_state.json")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def log(s: str):
    C.log("LIVE | " + s)


def sf(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def floor_prec(value: float, precision: int) -> float:
    fac = 10 ** precision
    return math.floor(value * fac) / fac


def fmt_qty(v: float, precision: int) -> str:
    return f"{v:.{precision}f}"


def fmt_price(v: float, precision: int) -> str:
    return f"{v:.{precision}f}"


def p(v) -> str:
    return f"{float(v):,.1f}"


class BitunixAPIError(RuntimeError):
    def __init__(self, code, msg, payload=None):
        self.code = code
        self.msg = msg
        self.payload = payload
        super().__init__(f"Bitunix code={code}: {msg}")


# ---------------------------------------------------------------------
# Private signed API
# ---------------------------------------------------------------------

class BitunixPrivate:
    BASE = "https://fapi.bitunix.com"

    def __init__(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "IGOD-BTC-Copilot-Live/5.0",
            "language": "en-US",
        })

    @staticmethod
    def _sha(s: str) -> str:
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _headers(self, params: Optional[dict], body_str: str) -> dict:
        nonce = secrets.token_hex(16)  # 32 chars
        ts = str(int(time.time() * 1000))

        params = params or {}
        query_sig = "".join(
            f"{k}{sf(v)}"
            for k, v in sorted(params.items(), key=lambda x: x[0])
            if v is not None
        )
        digest = self._sha(
            nonce + ts + self.api_key + query_sig + body_str
        )
        sign = self._sha(digest + self.secret)

        return {
            "api-key": self.api_key,
            "nonce": nonce,
            "timestamp": ts,
            "sign": sign,
            "Content-Type": "application/json",
            "language": "en-US",
        }

    def request(self, method: str, path: str, params=None, body=None):
        params = {
            k: sf(v) if isinstance(v, bool) else v
            for k, v in (params or {}).items()
            if v is not None
        }
        body_str = (
            json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            if body is not None else ""
        )
        headers = self._headers(params, body_str)

        if method == "GET":
            r = self.s.get(
                self.BASE + path,
                params=params,
                headers=headers,
                timeout=12,
            )
        else:
            r = self.s.post(
                self.BASE + path,
                params=params,
                data=body_str,
                headers=headers,
                timeout=12,
            )

        r.raise_for_status()
        payload = r.json()
        code = payload.get("code")
        if code != 0:
            raise BitunixAPIError(
                code,
                payload.get("msg", "Unknown error"),
                payload,
            )
        return payload.get("data")

    def positions(self, symbol=SYMBOL):
        return self.request(
            "GET",
            "/api/v1/futures/position/get_pending_positions",
            {"symbol": symbol},
        ) or []

    def position_by_id(self, position_id: str):
        data = self.request(
            "GET",
            "/api/v1/futures/position/get_pending_positions",
            {"symbol": SYMBOL, "positionId": position_id},
        ) or []
        return data[0] if data else None

    def history_position(self, position_id: str):
        d = self.request(
            "GET",
            "/api/v1/futures/position/get_history_positions",
            {
                "symbol": SYMBOL,
                "positionId": position_id,
                "limit": 10,
            },
        ) or {}
        rows = d.get("positionList", []) if isinstance(d, dict) else []
        return rows[0] if rows else None

    def pending_orders(self, client_id=None):
        d = self.request(
            "GET",
            "/api/v1/futures/trade/get_pending_orders",
            {
                "symbol": SYMBOL,
                "clientId": client_id,
                "limit": 100,
            },
        ) or {}
        return d.get("orderList", []) if isinstance(d, dict) else []

    def history_orders(self, client_id=None):
        d = self.request(
            "GET",
            "/api/v1/futures/trade/get_history_orders",
            {
                "symbol": SYMBOL,
                "clientId": client_id,
                "limit": 100,
            },
        ) or {}
        return d.get("orderList", []) if isinstance(d, dict) else []

    def order_detail(self, order_id=None, client_id=None):
        return self.request(
            "GET",
            "/api/v1/futures/trade/get_order_detail",
            {"orderId": order_id, "clientId": client_id},
        ) or {}

    def place_market(
        self,
        side: str,
        qty: str,
        client_id: str,
        sl_price: str,
    ):
        body = {
            "symbol": SYMBOL,
            "side": side,
            "qty": qty,
            "orderType": "MARKET",
            "clientId": client_id,
            "reduceOnly": False,
            # Immediate native protection.
            "slPrice": sl_price,
            "slStopType": "MARK_PRICE",
            "slOrderType": "MARKET",
        }
        return self.request(
            "POST",
            "/api/v1/futures/trade/place_order",
            body=body,
        ) or {}

    def close_all_btc(self):
        return self.request(
            "POST",
            "/api/v1/futures/trade/close_all_position",
            body={"symbol": SYMBOL},
        )

    def pending_tpsl(self, position_id: str):
        return self.request(
            "GET",
            "/api/v1/futures/tpsl/get_pending_orders",
            {
                "symbol": SYMBOL,
                "positionId": position_id,
                "limit": 100,
            },
        ) or []

    def place_partial_tp(
        self,
        position_id: str,
        tp_price: str,
        qty: str,
    ):
        return self.request(
            "POST",
            "/api/v1/futures/tpsl/place_order",
            body={
                "symbol": SYMBOL,
                "positionId": position_id,
                "tpPrice": tp_price,
                "tpStopType": "MARK_PRICE",
                "tpOrderType": "MARKET",
                "tpQty": qty,
            },
        ) or {}

    def place_position_stop(
        self,
        position_id: str,
        stop_price: str,
    ):
        return self.request(
            "POST",
            "/api/v1/futures/tpsl/position/place_order",
            body={
                "symbol": SYMBOL,
                "positionId": position_id,
                "slPrice": stop_price,
                "slStopType": "MARK_PRICE",
            },
        ) or {}

    def modify_position_stop(
        self,
        position_id: str,
        stop_price: str,
    ):
        return self.request(
            "POST",
            "/api/v1/futures/tpsl/position/modify_order",
            body={
                "symbol": SYMBOL,
                "positionId": position_id,
                "slPrice": stop_price,
                "slStopType": "MARK_PRICE",
            },
        ) or {}


# ---------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------

@dataclass
class LivePositionState:
    position_id: str
    client_id: str
    side: str
    entry: float
    qty_initial: float
    stop_initial: float
    r_value: float
    tp1: float
    tp2: float
    tp3: float
    stop_stage: int = 0
    current_stop: float = 0.0
    peak_price: float = 0.0
    opened_at: float = 0.0
    tp1_order_id: str = ""
    tp2_order_id: str = ""
    tp3_order_id: str = ""


class State:
    def __init__(self):
        self.auto_enabled = LIVE_AUTO_START
        self.entry_armed = True
        self.locked = False
        self.lock_reason = ""
        self.day = C.datetime.now(C.TZ).date().isoformat()
        self.trades_today = 0
        self.day_pnl = 0.0
        self.last_close_time = 0.0
        self.position: Optional[LivePositionState] = None
        self.consumed: List[str] = []
        self.load()

    def load(self):
        if not STATE_FILE.exists():
            return
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.auto_enabled = bool(d.get("auto_enabled", self.auto_enabled))
            self.entry_armed = bool(d.get("entry_armed", True))
            self.locked = bool(d.get("locked", False))
            self.lock_reason = str(d.get("lock_reason", ""))
            self.day = str(d.get("day", self.day))
            self.trades_today = int(d.get("trades_today", 0))
            self.day_pnl = float(d.get("day_pnl", 0))
            self.last_close_time = float(d.get("last_close_time", 0))
            self.consumed = list(d.get("consumed", []))[-100:]
            if d.get("position"):
                self.position = LivePositionState(**d["position"])
        except Exception as e:
            log(f"Could not load state: {e}")

    def save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        d = {
            "auto_enabled": self.auto_enabled,
            "entry_armed": self.entry_armed,
            "locked": self.locked,
            "lock_reason": self.lock_reason,
            "day": self.day,
            "trades_today": self.trades_today,
            "day_pnl": self.day_pnl,
            "last_close_time": self.last_close_time,
            "consumed": self.consumed[-100:],
            "position": asdict(self.position) if self.position else None,
        }
        STATE_FILE.write_text(
            json.dumps(d, indent=2),
            encoding="utf-8",
        )

    def new_day(self):
        today = C.datetime.now(C.TZ).date().isoformat()
        if today != self.day:
            self.day = today
            self.trades_today = 0
            self.day_pnl = 0.0
            self.save()


# ---------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------

class RealAuto:
    def __init__(self):
        if not API_KEY or not SECRET_KEY:
            raise RuntimeError(
                "Missing BITUNIX_API_KEY / BITUNIX_SECRET_KEY."
            )

        self.tg = C.Telegram(
            C.TELEGRAM_BOT_TOKEN,
            C.TELEGRAM_CHAT_ID,
        )
        self.pub = C.BitunixPublic()
        self.live = C.LiveMarket()
        self.analyzer = C.Analyzer(self.pub, self.live)
        self.api = BitunixPrivate(API_KEY, SECRET_KEY)
        self.state = State()

        self.base_precision = 4
        self.price_precision = 1
        self.min_qty = 0.0001
        self.max_leverage = LIVE_LEVERAGE

        self.last_analysis = 0.0
        self.plan = None
        self.last_block_notice = {}

        self.load_pair_rules()
        self.auth_preflight()

    def load_pair_rules(self):
        rows = self.pub.get(
            "/api/v1/futures/market/trading_pairs",
            {"symbols": SYMBOL},
        ) or []
        if not rows:
            raise RuntimeError("Could not load BTCUSDT trading rules.")

        x = rows[0]
        self.base_precision = int(x.get("basePrecision", 4))
        self.price_precision = int(x.get("quotePrecision", x.get("pricePrecision", 1)))
        self.min_qty = float(x.get("minTradeVolume", 0.0001))
        self.max_leverage = int(x.get("maxLeverage", LIVE_LEVERAGE))

        if LIVE_LEVERAGE > self.max_leverage:
            raise RuntimeError(
                f"LIVE_LEVERAGE={LIVE_LEVERAGE} > Bitunix maxLeverage "
                f"{self.max_leverage} for {SYMBOL}."
            )

    def auth_preflight(self):
        # Signed call proves auth/signing works.
        pos = self.api.positions(SYMBOL)
        log(f"Private API OK. Existing positions={len(pos)}")

        if pos and self.state.position is None:
            # We refuse to take control of a position we cannot prove is ours.
            self.state.auto_enabled = False
            self.state.locked = True
            self.state.lock_reason = (
                "Existing BTCUSDT position detected but no persisted bot state."
            )
            self.state.save()
            self.tg.send(
                "🛑 <b>LIVE AUTO BLOQUEADO</b>\n\n"
                "Hay una posición BTCUSDT real abierta que este bot no puede "
                "demostrar que sea suya. No abriré nada ni la modificaré.\n"
                "Cierra/revisa esa posición manualmente antes de reactivar."
            )

    def signal_id(self, plan) -> str:
        # Fingerprint uses the last CLOSED 15m candle.
        try:
            ts = int(self.analyzer.frames["15m"].iloc[-1]["time"])
        except Exception:
            ts = int(time.time() // 900 * 900_000)

        # One-shot fingerprint for the current 15m signal cycle.
        # Do NOT include live price: price changes every minute and would create
        # a different clientId for the same ENTER NOW cycle.
        raw = f"{ts}|{plan.action}|{plan.setup}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:6]
        side = "L" if "LONG" in plan.action else "S"
        dt = C.datetime.fromtimestamp(ts/1000, C.TZ)
        # <= 32 chars.
        return f"igod{dt:%y%m%d%H%M}{side}{h}"

    def exchange_has_signal(self, client_id: str) -> bool:
        """
        Return True only if Bitunix returns an order whose clientId EXACTLY
        matches this signal. Some API responses may contain rows even when a
        filter is not applied as expected, so a non-empty list alone is not
        sufficient evidence that this signal was already traded.
        """
        try:
            pending = self.api.pending_orders(client_id)
            if any(str(x.get("clientId", "")) == client_id for x in pending):
                return True
            if pending:
                log(
                    f"Pending-order response contained {len(pending)} row(s) "
                    f"but none matched clientId={client_id}; ignoring them."
                )

            history = self.api.history_orders(client_id)
            if any(str(x.get("clientId", "")) == client_id for x in history):
                return True
            if history:
                log(
                    f"History response contained {len(history)} row(s) "
                    f"but none matched clientId={client_id}; ignoring them."
                )

        except Exception as e:
            log(f"Signal-history check error: {e}")
            # Fail closed on a real API failure.
            return True

        return False

    def can_enter(self, plan, client_id):
        self.state.new_day()

        if not LIVE_EXECUTION:
            return False, "LIVE_EXECUTION=false"
        if not self.state.auto_enabled:
            return False, "auto disabled"
        if self.state.locked:
            return False, f"locked: {self.state.lock_reason}"
        if self.state.position is not None:
            return False, "bot position already active"
        if self.api.positions(SYMBOL):
            return False, "exchange BTCUSDT position already active"
        if self.api.pending_orders():
            return False, "pending BTCUSDT order exists"
        if not self.state.entry_armed:
            return False, "same ENTER cycle already consumed"
        if client_id in self.state.consumed:
            return False, "signal already consumed locally"
        if self.exchange_has_signal(client_id):
            return False, "signal already exists in Bitunix history"
        if self.state.trades_today >= LIVE_MAX_TRADES_DAY:
            return False, "daily trade limit reached"
        if self.state.day_pnl <= -abs(LIVE_MAX_DAILY_LOSS_USDT):
            return False, "daily loss limit reached"
        if (
            self.state.last_close_time
            and time.time() - self.state.last_close_time
            < LIVE_COOLDOWN_MIN * 60
        ):
            return False, "post-trade cooldown"

        return True, "ok"

    def calc_qty(self, price: float, stop: float):
        """
        Position sizing uses TWO caps:

        1) Exposure cap:
           LIVE_MARGIN_USDT * LIVE_LEVERAGE

        2) Stop-loss risk cap:
           LIVE_MAX_RISK_USDT / distance(entry, stop)

        The smaller quantity wins.

        In CROSS mode, LIVE_MARGIN_USDT is only a sizing basis, not a hard
        maximum loss. LIVE_MAX_RISK_USDT is the real per-trade SL risk cap
        used by this bot.
        """
        desired_notional = LIVE_MARGIN_USDT * LIVE_LEVERAGE
        qty_by_exposure = desired_notional / price

        stop_distance = abs(price - stop)
        if stop_distance <= 0:
            raise RuntimeError("Invalid stop distance; cannot size position.")

        qty_by_risk = LIVE_MAX_RISK_USDT / stop_distance

        raw_qty = min(qty_by_exposure, qty_by_risk)
        qty = floor_prec(raw_qty, self.base_precision)

        if qty < self.min_qty:
            raise RuntimeError(
                f"Calculated qty {qty} < minTradeVolume {self.min_qty}."
            )

        actual_notional = qty * price
        estimated_sl_risk = qty * stop_distance

        # Need enough size to preserve TP1/TP2/TP3 + runner.
        chunk = floor_prec(qty * 0.25, self.base_precision)
        if chunk < self.min_qty:
            raise RuntimeError(
                f"Position qty {qty} is too small for 25% partial TPs. "
                f"Each chunk={chunk}, minimum={self.min_qty}. "
                f"Increase LIVE_MARGIN_USDT, LIVE_LEVERAGE, or "
                f"LIVE_MAX_RISK_USDT."
            )

        return qty, actual_notional, chunk, estimated_sl_risk

    def wait_for_position(self, timeout=18):
        end = time.time() + timeout
        while time.time() < end:
            rows = self.api.positions(SYMBOL)
            if rows:
                return rows[0]
            time.sleep(1)
        return None

    def emergency_close_and_lock(self, reason):
        try:
            self.api.close_all_btc()
        except Exception as e:
            reason += f" | close error: {e}"

        self.state.auto_enabled = False
        self.state.locked = True
        self.state.lock_reason = reason
        self.state.save()

        self.tg.send(
            "🚨🛑 <b>EMERGENCY LIVE LOCK</b>\n\n"
            f"{C.html.escape(reason)}\n\n"
            "He desactivado nuevas entradas. Revisa Bitunix manualmente."
        )

    def ensure_stop(self, position_id: str, stop: float):
        stop_s = fmt_price(stop, self.price_precision)

        # If the SL attached to the entry became the position SL,
        # modify succeeds. If there isn't one, create it.
        try:
            self.api.modify_position_stop(position_id, stop_s)
            return
        except Exception:
            pass

        self.api.place_position_stop(position_id, stop_s)

        # Verify there is at least one SL in exchange TP/SL state.
        time.sleep(0.8)
        orders = self.api.pending_tpsl(position_id)
        if not any(str(x.get("slPrice", "")).strip() for x in orders):
            raise RuntimeError("Native stop not visible after placement.")

    def place_native_tps(self, pos_state: LivePositionState, chunk: float):
        ids = []
        for target in (pos_state.tp1, pos_state.tp2, pos_state.tp3):
            d = self.api.place_partial_tp(
                pos_state.position_id,
                fmt_price(target, self.price_precision),
                fmt_qty(chunk, self.base_precision),
            )
            ids.append(str(d.get("orderId", "")))
            time.sleep(0.35)

        pos_state.tp1_order_id = ids[0]
        pos_state.tp2_order_id = ids[1]
        pos_state.tp3_order_id = ids[2]

        # Verify 3 TP orders are visible.
        time.sleep(0.8)
        rows = self.api.pending_tpsl(pos_state.position_id)
        tp_rows = [x for x in rows if str(x.get("tpPrice", "")).strip()]
        if len(tp_rows) < 3:
            raise RuntimeError(
                f"Expected >=3 native TP orders, found {len(tp_rows)}."
            )

    def verify_real_position(self, pos: dict, qty_requested: float):
        problems = []

        lev = int(float(pos.get("leverage", 0) or 0))
        margin_mode = str(pos.get("marginMode", "")).upper()
        position_mode = str(pos.get("positionMode", "")).upper()
        qty_real = float(pos.get("qty", 0) or 0)
        margin_real = float(pos.get("margin", 0) or 0)

        if lev != LIVE_LEVERAGE:
            problems.append(
                f"leverage real {lev}x != requested {LIVE_LEVERAGE}x"
            )

        if margin_mode != LIVE_MARGIN_MODE:
            problems.append(
                f"marginMode real {margin_mode} != expected {LIVE_MARGIN_MODE}"
            )

        if position_mode != "ONE_WAY":
            problems.append(
                f"positionMode real {position_mode} != ONE_WAY"
            )

        qty_tol = max(self.min_qty, qty_requested * 0.08)
        if abs(qty_real - qty_requested) > qty_tol:
            problems.append(
                f"qty real {qty_real} differs from requested {qty_requested}"
            )

        # Only validate a fixed margin amount in ISOLATION.
        # In CROSS, margin is shared across the futures account and is not a
        # reliable hard-cap/target value for one position.
        if (
            LIVE_MARGIN_MODE == "ISOLATION"
            and LIVE_MARGIN_USDT > 0
            and margin_real > 0
        ):
            diff = abs(margin_real - LIVE_MARGIN_USDT) / LIVE_MARGIN_USDT
            if diff > VERIFY_MARGIN_TOL_PCT:
                problems.append(
                    f"margin real {margin_real:.3f} USDT differs too much "
                    f"from target {LIVE_MARGIN_USDT:.3f}"
                )

        if problems:
            raise RuntimeError("; ".join(problems))

    def notify_entry_blocked(self, plan, client_id: str, reason: str):
        # Avoid Telegram spam while the same ENTER NOW remains active.
        key = f"{client_id}|{reason}"
        now = time.time()
        if now - self.last_block_notice.get(key, 0) < 900:
            return
        self.last_block_notice[key] = now

        self.tg.send(
            "🚨 <b>ENTER NOW DETECTADO, PERO NO EJECUTADO</b>\n\n"
            f"Señal: <code>{client_id}</code>\n"
            f"Acción: <b>{C.html.escape(str(plan.action))}</b>\n"
            f"Setup: <b>{C.html.escape(str(plan.setup))}</b>\n"
            f"Precio: <b>{p(plan.price)}</b>\n"
            f"Motivo: <b>{C.html.escape(reason)}</b>"
        )

    def open_real(self, plan):
        client_id = self.signal_id(plan)
        ok, why = self.can_enter(plan, client_id)
        if not ok:
            log(f"Entry blocked: {why}")
            self.notify_entry_blocked(plan, client_id, why)
            return

        if None in (plan.stop, plan.tp1, plan.tp2, plan.tp3):
            reason = "incomplete SL/TP plan"
            log(f"Entry blocked: {reason}.")
            self.notify_entry_blocked(plan, client_id, reason)
            return

        side = "BUY" if plan.action == "ENTER LONG NOW" else "SELL"
        side_name = "LONG" if side == "BUY" else "SHORT"
        qty, intended_notional, chunk, estimated_sl_risk = self.calc_qty(
            float(plan.price), float(plan.stop)
        )

        # Consume/lock BEFORE sending. If request times out after exchange accepts it,
        # the bot will not submit a second order blindly.
        self.state.entry_armed = False
        self.state.consumed.append(client_id)
        self.state.save()

        self.tg.send(
            "⚠️🚨 <b>ENVIANDO ORDEN REAL</b>\n\n"
            f"{side_name} {SYMBOL}\n"
            f"Señal: <code>{client_id}</code>\n"
            f"Base sizing: <b>{LIVE_MARGIN_USDT:.2f} USDT</b>\n"
            f"Leverage esperado: <b>{LIVE_LEVERAGE}x</b>\n"
            f"Riesgo máx. por SL: <b>{LIVE_MAX_RISK_USDT:.2f} USDT</b>\n"
            f"Margin mode esperado: <b>{LIVE_MARGIN_MODE}</b>\n"
            f"Nominal calculado: <b>{intended_notional:.2f} USDT</b>\n"
            f"Riesgo aprox. al SL: <b>{estimated_sl_risk:.2f} USDT</b> "
            f"(máx. {LIVE_MAX_RISK_USDT:.2f})\n"
            f"Qty solicitada: <b>{fmt_qty(qty, self.base_precision)} BTC</b>\n"
            f"SL inicial: <b>{p(plan.stop)}</b>\n"
            f"TP1/2/3: <b>{p(plan.tp1)} / {p(plan.tp2)} / {p(plan.tp3)}</b>"
        )

        try:
            order = self.api.place_market(
                side=side,
                qty=fmt_qty(qty, self.base_precision),
                client_id=client_id,
                sl_price=fmt_price(plan.stop, self.price_precision),
            )
        except BitunixAPIError as e:
            # Duplicate client ID means exchange may already have accepted this signal.
            # Do NOT retry blindly.
            self.tg.send(
                "❌ <b>Bitunix rechazó/contestó la entrada</b>\n\n"
                f"code={e.code}\n{C.html.escape(e.msg)}\n"
                "No reenviaré automáticamente esta señal."
            )
            return

        order_id = str(order.get("orderId", ""))
        pos = self.wait_for_position()
        if not pos:
            detail = {}
            try:
                detail = self.api.order_detail(
                    order_id=order_id or None,
                    client_id=client_id,
                )
            except Exception:
                pass
            self.state.auto_enabled = False
            self.state.locked = True
            self.state.lock_reason = (
                "Order sent but position could not be verified."
            )
            self.state.save()
            self.tg.send(
                "🚨 <b>NO PUDE VERIFICAR LA POSICIÓN</b>\n\n"
                f"Order ID: {C.html.escape(order_id)}\n"
                f"Estado order: {C.html.escape(str(detail.get('status','?')))}\n"
                "He bloqueado nuevas entradas. Revisa Bitunix AHORA."
            )
            return

        try:
            self.verify_real_position(pos, qty)
        except Exception as e:
            self.emergency_close_and_lock(
                "POSITION VERIFICATION FAILED: " + str(e)
            )
            return

        position_id = str(pos["positionId"])
        real_entry = float(pos.get("avgOpenPrice", 0) or 0)
        real_qty = float(pos.get("qty", 0) or 0)
        real_margin = float(pos.get("margin", 0) or 0)
        liq = float(pos.get("liqPrice", 0) or 0)
        r_value = abs(real_entry - float(plan.stop))

        ps = LivePositionState(
            position_id=position_id,
            client_id=client_id,
            side=side_name,
            entry=real_entry,
            qty_initial=real_qty,
            stop_initial=float(plan.stop),
            r_value=r_value,
            tp1=float(plan.tp1),
            tp2=float(plan.tp2),
            tp3=float(plan.tp3),
            current_stop=float(plan.stop),
            peak_price=real_entry,
            opened_at=time.time(),
        )

        self.state.position = ps
        self.state.trades_today += 1
        self.state.save()

        try:
            # Native stop first.
            self.ensure_stop(position_id, float(plan.stop))
            # Native partial TPs after stop is confirmed.
            real_chunk = floor_prec(real_qty * 0.25, self.base_precision)
            if real_chunk < self.min_qty:
                raise RuntimeError(
                    f"Real filled qty too small for partial TP: chunk={real_chunk}"
                )
            self.place_native_tps(ps, real_chunk)
            self.state.save()
        except Exception as e:
            self.emergency_close_and_lock(
                "PROTECTION SETUP FAILED: " + str(e)
            )
            return

        self.tg.send(
            "✅🟢 <b>POSICIÓN REAL VERIFICADA Y PROTEGIDA</b>\n\n"
            f"{side_name} {SYMBOL}\n"
            f"Position ID: <code>{position_id}</code>\n"
            f"Entrada REAL: <b>{p(real_entry)}</b>\n"
            f"Qty REAL: <b>{fmt_qty(real_qty, self.base_precision)} BTC</b>\n"
            f"Margen REAL: <b>{real_margin:.3f} USDT</b>\n"
            f"Leverage REAL: <b>{pos.get('leverage')}x</b>\n"
            f"Modo REAL: <b>{pos.get('marginMode')} / {pos.get('positionMode')}</b>\n"
            f"Liquidación estimada: <b>{p(liq) if liq > 0 else '-'}</b>\n\n"
            f"SL nativo: <b>{p(plan.stop)}</b>\n"
            f"TP1 25%: <b>{p(plan.tp1)}</b>\n"
            f"TP2 25%: <b>{p(plan.tp2)}</b>\n"
            f"TP3 25%: <b>{p(plan.tp3)}</b>\n"
            "Runner restante: <b>~25%</b>\n\n"
            "No se abrirá otra operación mientras esta posición exista."
        )

    def safe_move_stop(self, new_stop: float, mark: float, stage: int):
        ps = self.state.position
        if not ps:
            return

        # Never loosen the stop.
        if ps.side == "LONG":
            if new_stop <= ps.current_stop:
                return
            # Stop for LONG must stay below current market.
            new_stop = min(new_stop, mark * 0.9985)
            if new_stop <= ps.current_stop:
                return
        else:
            if new_stop >= ps.current_stop:
                return
            new_stop = max(new_stop, mark * 1.0015)
            if new_stop >= ps.current_stop:
                return

        self.ensure_stop(ps.position_id, new_stop)
        ps.current_stop = new_stop
        ps.stop_stage = max(ps.stop_stage, stage)
        self.state.save()

        self.tg.send(
            "🔒 <b>SL REAL MODIFICADO</b>\n\n"
            f"{ps.side} {SYMBOL}\n"
            f"Nuevo SL: <b>{p(new_stop)}</b>\n"
            f"Etapa: <b>{ps.stop_stage}</b>"
        )

    def manage_real(self, mark: float):
        ps = self.state.position
        if not ps:
            return

        pos = self.api.position_by_id(ps.position_id)

        if pos is None:
            hist = None
            for _ in range(4):
                try:
                    hist = self.api.history_position(ps.position_id)
                    if hist:
                        break
                except Exception:
                    pass
                time.sleep(1)

            net = 0.0
            if hist:
                realized = float(hist.get("realizedPNL", 0) or 0)
                fee = float(hist.get("fee", 0) or 0)
                funding = float(hist.get("funding", 0) or 0)
                net = realized - fee + funding

            self.state.day_pnl += net
            self.state.last_close_time = time.time()
            self.state.position = None
            # Do NOT re-arm here. It re-arms only once ENTER NOW disappears.
            self.state.save()

            self.tg.send(
                "🏁 <b>POSICIÓN REAL CERRADA</b>\n\n"
                f"Position ID: <code>{ps.position_id}</code>\n"
                f"PnL neto registrado aprox.: <b>{net:+.4f} USDT</b>\n"
                f"PnL bot hoy: <b>{self.state.day_pnl:+.4f} USDT</b>\n\n"
                "La misma señal NO se volverá a ejecutar."
            )
            return

        qty_now = float(pos.get("qty", 0) or 0)
        ratio = qty_now / ps.qty_initial if ps.qty_initial > 0 else 1.0

        if ps.side == "LONG":
            ps.peak_price = max(ps.peak_price, mark)
        else:
            ps.peak_price = min(ps.peak_price, mark)

        # Infer partial TP milestones from actual position size at Bitunix.
        # This survives notification delays and does not depend on Telegram.
        if ratio <= 0.76 and ps.stop_stage < 1:
            if ps.side == "LONG":
                be = ps.entry * (1 + LIVE_BE_BUFFER_PCT)
            else:
                be = ps.entry * (1 - LIVE_BE_BUFFER_PCT)
            self.safe_move_stop(be, mark, 1)

        if ratio <= 0.51 and ps.stop_stage < 2:
            target = (
                ps.entry + ps.r_value
                if ps.side == "LONG"
                else ps.entry - ps.r_value
            )
            self.safe_move_stop(target, mark, 2)

        if ratio <= 0.26 and ps.stop_stage < 3:
            target = (
                ps.entry + 2 * ps.r_value
                if ps.side == "LONG"
                else ps.entry - 2 * ps.r_value
            )
            self.safe_move_stop(target, mark, 3)

        # Runner trailing only after the three partials.
        if ps.stop_stage >= 3 and ratio > 0:
            if ps.side == "LONG":
                trail = ps.peak_price - LIVE_RUNNER_TRAIL_R * ps.r_value
                improvement = trail - ps.current_stop
            else:
                trail = ps.peak_price + LIVE_RUNNER_TRAIL_R * ps.r_value
                improvement = ps.current_stop - trail

            if improvement >= 0.25 * ps.r_value:
                self.safe_move_stop(trail, mark, 4)

        self.state.save()

    def status(self):
        ps = self.state.position
        current_action = self.plan.action if self.plan is not None else "-"
        current_setup = self.plan.setup if self.plan is not None else "-"
        base = (
            "💰 <b>LIVE STATUS</b>\n"
            f"Ejecución real permitida: <b>{LIVE_EXECUTION}</b>\n"
            f"Auto entradas: <b>{self.state.auto_enabled}</b>\n"
            f"Entry armed: <b>{self.state.entry_armed}</b>\n"
            f"Bloqueado: <b>{self.state.locked}</b>\n"
            f"Señal actual: <b>{C.html.escape(str(current_action))}</b>\n"
            f"Setup actual: <b>{C.html.escape(str(current_setup))}</b>\n"
            f"Señales consumidas: <b>{len(self.state.consumed)}</b>\n"
            f"Base de sizing/trade: <b>{LIVE_MARGIN_USDT:.2f} USDT</b>\n"
            f"Leverage esperado: <b>{LIVE_LEVERAGE}x</b>\n"
            f"Margin mode esperado: <b>{LIVE_MARGIN_MODE}</b>\n"
            f"Trades hoy: <b>{self.state.trades_today}/{LIVE_MAX_TRADES_DAY}</b>\n"
            f"PnL bot hoy aprox.: <b>{self.state.day_pnl:+.4f} USDT</b>\n"
        )
        if not ps:
            return base + "Posición bot: <b>NINGUNA</b>"
        return (
            base
            + f"Posición bot: <b>{ps.side}</b>\n"
            + f"Entrada: <b>{p(ps.entry)}</b>\n"
            + f"SL actual: <b>{p(ps.current_stop)}</b>\n"
            + f"Etapa SL: <b>{ps.stop_stage}</b>"
        )

    def commands(self):
        for cmd in self.tg.poll_commands():
            if cmd in ("/status", "/live"):
                self.tg.send(self.status())
            elif cmd == "/live_off":
                self.state.auto_enabled = False
                self.state.save()
                self.tg.send(
                    "🔕 <b>NUEVAS ENTRADAS LIVE DESACTIVADAS</b>\n"
                    "Si hay una posición del bot, SEGUIRÁ gestionándose."
                )
            elif cmd == "/live_on":
                if not LIVE_EXECUTION:
                    self.tg.send(
                        "⛔ LIVE_EXECUTION=false en Railway. "
                        "No puedo activar dinero real desde Telegram."
                    )
                elif self.state.locked:
                    self.tg.send(
                        "⛔ El bot está BLOQUEADO por seguridad:\n"
                        + C.html.escape(self.state.lock_reason)
                    )
                else:
                    self.state.auto_enabled = True
                    self.state.save()
                    self.tg.send(
                        "🔴 <b>NUEVAS ENTRADAS LIVE ACTIVADAS</b>\n"
                        "El próximo ENTER NOW válido puede enviar una orden REAL."
                    )
            elif cmd == "/plan" and self.plan is not None:
                self.tg.send(
                    C.plan_message(self.plan, "📍 PLAN LIVE ACTUAL")
                )

    def run(self):
        self.live.start()

        self.tg.send(
            "🔴🤖 <b>I-GOD V5 REAL AUTO conectado</b>\n\n"
            f"BTCUSDT | base sizing {LIVE_MARGIN_USDT:.2f} USDT "
            f"| leverage esperado {LIVE_LEVERAGE}x\n"
            f"LIVE_EXECUTION: <b>{LIVE_EXECUTION}</b>\n"
            f"AUTO START: <b>{self.state.auto_enabled}</b>\n"
            f"State persistente: <b>{bool(volume)}</b>\n\n"
            "ONE SHOT: un ciclo ENTER NOW solo puede abrir UNA operación.\n"
            "Mientras haya posición, no abre otra."
        )

        while not C.STOP_EVENT.is_set():
            try:
                self.state.new_day()
                self.commands()

                now = time.time()
                if now - self.last_analysis >= C.ANALYSIS_SECONDS:
                    self.plan = self.analyzer.analyze()
                    log(
                        f"{self.plan.bias} | {self.plan.action} | "
                        f"{self.plan.setup} | {self.plan.price:.1f}"
                    )

                    is_enter = self.plan.action in (
                        "ENTER LONG NOW",
                        "ENTER SHORT NOW",
                    )

                    # Re-arm only after the signal leaves ENTER state.
                    if (
                        not is_enter
                        and self.state.position is None
                        and not self.state.entry_armed
                    ):
                        self.state.entry_armed = True
                        self.state.save()
                        log("Entry cycle re-armed.")

                    if is_enter and self.state.position is None:
                        self.open_real(self.plan)

                    self.last_analysis = now

                snap = self.live.snapshot()
                mark = snap.get("price")
                if mark is None and self.plan is not None:
                    mark = self.plan.price

                if mark is not None and self.state.position is not None:
                    self.manage_real(float(mark))

                C.STOP_EVENT.wait(MANAGE_SECONDS)

            except KeyboardInterrupt:
                break
            except Exception as e:
                log(f"Loop error: {type(e).__name__}: {e}")
                time.sleep(8)


if __name__ == "__main__":
    RealAuto().run()
