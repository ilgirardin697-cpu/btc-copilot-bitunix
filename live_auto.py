#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I-GOD BTC Copilot V7.3.3 — REAL AUTO EXECUTOR for Bitunix
======================================================

REAL MONEY CODE.

Key features:
- Reuses main.py planner/analyzer.
- One ENTER cycle -> at most one real entry.
- Exact clientId duplicate verification.
- Market entry + native SL + 2 partial TPs + larger runner.
- TP1 -> fee/funding-aware net-profit protection.
- TP2 -> 40% runner starts wide structural trailing; no TP3 order.
- Every SL move is re-read from Bitunix and must match before state advances.
- Dynamic leverage AUTO 20-50x by stop-risk need (exchange/tier capped).
- Runner stop never loosens and survives normal pullbacks better.
- Real Bitunix account/position status from private API.
- Distinguishes BOT position from MANUAL/EXTERNAL position.
- Net PnL from Bitunix realizedPNL - fee + funding.
- Fee/slippage guard before entry.
- Thesis invalidation exit.
- Confirmed opposite ENTER can close current bot position and reverse.
- Never adopts or modifies a manual position.
- Persistent state in Railway volume.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import main as C


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

API_KEY = os.getenv("BITUNIX_API_KEY", "").strip()
SECRET_KEY = os.getenv("BITUNIX_SECRET_KEY", "").strip()

LIVE_EXECUTION = os.getenv("LIVE_EXECUTION", "false").lower() == "true"
LIVE_AUTO_START = os.getenv("LIVE_AUTO_START", "false").lower() == "true"

LIVE_MARGIN_USDT = float(os.getenv("LIVE_MARGIN_USDT", "2"))
LIVE_LEVERAGE = int(os.getenv("LIVE_LEVERAGE", "20"))  # legacy/fallback fixed leverage
LIVE_DYNAMIC_LEVERAGE = os.getenv("LIVE_DYNAMIC_LEVERAGE", "true").lower() == "true"
LIVE_MIN_LEVERAGE = int(os.getenv("LIVE_MIN_LEVERAGE", "20"))
LIVE_MAX_LEVERAGE = int(os.getenv("LIVE_MAX_LEVERAGE", "50"))
LIVE_MARGIN_MODE = os.getenv("LIVE_MARGIN_MODE", "CROSS").strip().upper()
LIVE_MAX_RISK_USDT = float(os.getenv("LIVE_MAX_RISK_USDT", "10"))

# Keep explicit cash headroom for fees/slippage and exchange margin checks.
LIVE_EXECUTION_CASH_RESERVE_PCT = float(
    os.getenv("LIVE_EXECUTION_CASH_RESERVE_PCT", "5")
) / 100

# V7.2 dynamic equity compounding.
# EQUITY mode reinvests account growth automatically.
LIVE_SIZING_MODE = os.getenv("LIVE_SIZING_MODE", "EQUITY").strip().upper()
LIVE_EQUITY_ALLOC_PCT = float(
    os.getenv("LIVE_EQUITY_ALLOC_PCT", "95")
) / 100
LIVE_RISK_PCT = float(
    os.getenv("LIVE_RISK_PCT", "10")
) / 100

LIVE_MAX_TRADES_DAY = int(os.getenv("LIVE_MAX_TRADES_DAY", "3"))
LIVE_COOLDOWN_MIN = int(os.getenv("LIVE_COOLDOWN_MIN", "60"))
LIVE_MAX_DAILY_LOSS_USDT = float(os.getenv("LIVE_MAX_DAILY_LOSS_USDT", "2"))

# Exit distribution: 30% TP1 + 30% TP2 + 40% runner.
# TP3 from the planner is kept only as a market reference; no TP3 order is placed.
LIVE_TP1_PCT = float(os.getenv("LIVE_TP1_PCT", "30")) / 100
LIVE_TP2_PCT = float(os.getenv("LIVE_TP2_PCT", "30")) / 100
LIVE_RUNNER_PCT = max(0.0, 1.0 - LIVE_TP1_PCT - LIVE_TP2_PCT)

# Wide runner after TP2. Use the wider R/ATR distance and respect 15m structure.
LIVE_RUNNER_TRAIL_R = float(os.getenv("LIVE_RUNNER_TRAIL_R", "2.0"))
LIVE_RUNNER_TRAIL_ATR = float(os.getenv("LIVE_RUNNER_TRAIL_ATR", "1.25"))
LIVE_RUNNER_STRUCTURE_ATR = float(os.getenv("LIVE_RUNNER_STRUCTURE_ATR", "0.25"))
LIVE_TRAIL_STEP_R = float(os.getenv("LIVE_TRAIL_STEP_R", "0.25"))

# Net-profit protection after partials.
LIVE_TP1_NET_LOCK_USDT = float(os.getenv("LIVE_TP1_NET_LOCK_USDT", "0.25"))
LIVE_TP2_KEEP_REALIZED_PCT = float(os.getenv("LIVE_TP2_KEEP_REALIZED_PCT", "0.50"))
LIVE_STOP_MARK_BUFFER_PCT = float(os.getenv("LIVE_STOP_MARK_BUFFER_PCT", "0.0004"))

# Conservative cost assumptions for the PRE-TRADE guard.
# Actual PnL/fees after trading are read from Bitunix.
LIVE_TAKER_FEE_RATE = float(os.getenv("LIVE_TAKER_FEE_RATE", "0.0006"))
LIVE_SLIPPAGE_RATE = float(os.getenv("LIVE_SLIPPAGE_RATE", "0.00015"))

# Extra adverse-fill reserve for STOP-MARKET execution.
# 0.10% is deliberately wider than the generic slippage assumption because
# the stop is triggered first and then executed at market.
LIVE_STOP_SLIPPAGE_RATE = float(
    os.getenv("LIVE_STOP_SLIPPAGE_RATE", "0.0010")
)

LIVE_MIN_NET_RR = float(os.getenv("LIVE_MIN_NET_RR", "1.25"))

# PROFIT LOCK: el +10% diario NO apaga el bot.
LIVE_DAILY_PROFIT_TARGET_PCT = float(
    os.getenv("LIVE_DAILY_PROFIT_TARGET_PCT", "10")
) / 100
LIVE_PROFIT_LOCK_RISK_MULT = float(
    os.getenv("LIVE_PROFIT_LOCK_RISK_MULT", "0.50")
)
LIVE_PROFIT_LOCK_MIN_NET_RR = float(
    os.getenv("LIVE_PROFIT_LOCK_MIN_NET_RR", "1.75")
)
LIVE_PROFIT_LOCK_RETAIN_PCT = float(
    os.getenv("LIVE_PROFIT_LOCK_RETAIN_PCT", "0.75")
)
LIVE_PROFIT_LOCK_EXTRA_TRADES = int(
    os.getenv("LIVE_PROFIT_LOCK_EXTRA_TRADES", "1")
)
LIVE_PROFIT_LOCK_USE_ACCOUNT_DAY = (
    os.getenv("LIVE_PROFIT_LOCK_USE_ACCOUNT_DAY", "true").lower() == "true"
)

# Smart exit / reversal.
LIVE_EXIT_ON_THESIS_FLIP = (
    os.getenv("LIVE_EXIT_ON_THESIS_FLIP", "true").lower() == "true"
)
LIVE_REVERSE_ON_CONFIRMED = (
    os.getenv("LIVE_REVERSE_ON_CONFIRMED", "true").lower() == "true"
)
LIVE_EXIT_CONFIRM_CYCLES = int(os.getenv("LIVE_EXIT_CONFIRM_CYCLES", "2"))

VERIFY_MARGIN_TOL_PCT = float(os.getenv("VERIFY_MARGIN_TOL_PCT", "35")) / 100
MANAGE_SECONDS = int(os.getenv("LIVE_MANAGE_SECONDS", "10"))

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()
MARGIN_COIN = os.getenv("MARGIN_COIN", "USDT").upper()

volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
STATE_FILE = (
    Path(volume) / "igod_live_state.json"
    if volume
    else Path("igod_live_state.json")
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def log(s: str):
    C.log("LIVE | " + s)


def sf(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def fnum(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def floor_prec(value: float, precision: int) -> float:
    fac = 10 ** precision
    return math.floor(value * fac) / fac


def fmt_qty(v: float, precision: int) -> str:
    return f"{v:.{precision}f}"


def fmt_price(v: float, precision: int) -> str:
    return f"{v:.{precision}f}"


def p(v) -> str:
    return f"{float(v):,.1f}"


def money(v) -> str:
    return f"{float(v):+,.4f} USDT"


def side_icon(side: str) -> str:
    return "🟢" if str(side).upper() == "LONG" else "🔴"


class BitunixAPIError(RuntimeError):
    def __init__(self, code, msg, payload=None):
        self.code = code
        self.msg = msg
        self.payload = payload
        super().__init__(f"Bitunix code={code}: {msg}")


# ---------------------------------------------------------------------
# Private signed Bitunix API
# ---------------------------------------------------------------------

class BitunixPrivate:
    BASE = "https://fapi.bitunix.com"

    def __init__(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "IGOD-BTC-Copilot-Live/7.0",
            "language": "en-US",
        })

    @staticmethod
    def _sha(s: str) -> str:
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _headers(self, params: Optional[dict], body_str: str) -> dict:
        nonce = secrets.token_hex(16)
        ts = str(int(time.time() * 1000))
        params = params or {}

        query_sig = "".join(
            f"{k}{sf(v)}"
            for k, v in sorted(params.items(), key=lambda x: x[0])
            if v is not None
        )
        digest = self._sha(nonce + ts + self.api_key + query_sig + body_str)
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

    @staticmethod
    def _rows(data, key):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            v = data.get(key, [])
            return v if isinstance(v, list) else []
        return []

    @staticmethod
    def _one(data):
        """Normalize order responses that may be dict or one-element list."""
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    return x
            return {}
        return {}

    def account(self, margin_coin=MARGIN_COIN):
        d = self.request(
            "GET",
            "/api/v1/futures/account",
            {"marginCoin": margin_coin},
        ) or {}
        if isinstance(d, list):
            return d[0] if d else {}
        return d if isinstance(d, dict) else {}

    def positions(self, symbol=SYMBOL):
        d = self.request(
            "GET",
            "/api/v1/futures/position/get_pending_positions",
            {"symbol": symbol},
        ) or []
        return d if isinstance(d, list) else self._rows(d, "positionList")

    def position_by_id(self, position_id: str):
        data = self.request(
            "GET",
            "/api/v1/futures/position/get_pending_positions",
            {"symbol": SYMBOL, "positionId": position_id},
        ) or []
        rows = data if isinstance(data, list) else self._rows(data, "positionList")
        return rows[0] if rows else None

    def history_positions(self, limit=100):
        d = self.request(
            "GET",
            "/api/v1/futures/position/get_history_positions",
            {"symbol": SYMBOL, "limit": limit},
        ) or {}
        return self._rows(d, "positionList")

    def history_position(self, position_id: str):
        d = self.request(
            "GET",
            "/api/v1/futures/position/get_history_positions",
            {"symbol": SYMBOL, "positionId": position_id, "limit": 10},
        ) or {}
        rows = self._rows(d, "positionList")
        return rows[0] if rows else None

    def pending_orders(self, client_id=None):
        d = self.request(
            "GET",
            "/api/v1/futures/trade/get_pending_orders",
            {"symbol": SYMBOL, "clientId": client_id, "limit": 100},
        ) or {}
        return self._rows(d, "orderList")

    def history_orders(self, client_id=None):
        d = self.request(
            "GET",
            "/api/v1/futures/trade/get_history_orders",
            {"symbol": SYMBOL, "clientId": client_id, "limit": 100},
        ) or {}
        return self._rows(d, "orderList")

    def history_trades(self, position_id=None, limit=100):
        d = self.request(
            "GET",
            "/api/v1/futures/trade/get_history_trades",
            {
                "symbol": SYMBOL,
                "positionId": position_id,
                "limit": limit,
            },
        ) or {}
        return self._rows(d, "tradeList")

    def order_detail(self, order_id=None, client_id=None):
        return self._one(
            self.request(
                "GET",
                "/api/v1/futures/trade/get_order_detail",
                {"orderId": order_id, "clientId": client_id},
            )
        )

    def pending_tpsl(self, position_id: Optional[str] = None):
        d = self.request(
            "GET",
            "/api/v1/futures/tpsl/get_pending_orders",
            {
                "symbol": SYMBOL,
                "positionId": position_id,
                "limit": 100,
            },
        ) or []
        if isinstance(d, list):
            return d
        return self._rows(d, "orderList")

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
            "slPrice": sl_price,
            "slStopType": "MARK_PRICE",
            "slOrderType": "MARKET",
        }
        return self._one(
            self.request(
                "POST",
                "/api/v1/futures/trade/place_order",
                body=body,
            )
        )

    def flash_close_position(self, position_id: str):
        return self.request(
            "POST",
            "/api/v1/futures/trade/flash_close_position",
            body={"positionId": position_id},
        ) or {}

    def place_partial_tp(
        self,
        position_id: str,
        tp_price: str,
        qty: str,
    ):
        return self._one(
            self.request(
                "POST",
                "/api/v1/futures/tpsl/place_order",
                body={
                    "symbol": SYMBOL,
                    "positionId": position_id,
                    "tpPrice": tp_price,
                    "tpStopType": "LAST_PRICE",
                    "tpOrderType": "MARKET",
                    "tpQty": qty,
                },
            )
        )

    def place_position_stop(self, position_id: str, stop_price: str):
        return self._one(
            self.request(
                "POST",
                "/api/v1/futures/tpsl/position/place_order",
                body={
                    "symbol": SYMBOL,
                    "positionId": position_id,
                    "slPrice": stop_price,
                    "slStopType": "MARK_PRICE",
                },
            )
        )

    def modify_position_stop(self, position_id: str, stop_price: str):
        return self._one(
            self.request(
                "POST",
                "/api/v1/futures/tpsl/position/modify_order",
                body={
                    "symbol": SYMBOL,
                    "positionId": position_id,
                    "slPrice": stop_price,
                    "slStopType": "MARK_PRICE",
                },
            )
        )

    def modify_tpsl_stop(
        self,
        order_id: str,
        stop_price: str,
        qty: str,
    ):
        return self._one(
            self.request(
                "POST",
                "/api/v1/futures/tpsl/modify_order",
                body={
                    "orderId": order_id,
                    "slPrice": stop_price,
                    "slStopType": "MARK_PRICE",
                    "slOrderType": "MARKET",
                    "slQty": qty,
                },
            )
        )

    def change_leverage(self, leverage: int):
        data = self.request(
            "POST",
            "/api/v1/futures/account/change_leverage",
            body={
                "symbol": SYMBOL,
                "leverage": int(leverage),
                "marginCoin": MARGIN_COIN,
            },
        )
        rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            lev = int(fnum(row.get("leverage", leverage), leverage))
            if lev != int(leverage):
                raise RuntimeError(
                    f"Bitunix leverage response {lev}x != requested {leverage}x"
                )
        return rows

    def leverage_margin_mode(self):
        data = self.request(
            "GET",
            "/api/v1/futures/account/get_leverage_margin_mode",
            {
                "symbol": SYMBOL,
                "marginCoin": MARGIN_COIN,
            },
        ) or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        return data if isinstance(data, dict) else {}

    def change_leverage_verified(self, leverage: int):
        target = int(leverage)
        self.change_leverage(target)

        last = {}
        for _ in range(6):
            time.sleep(0.35)
            last = self.leverage_margin_mode()
            real_lev = int(fnum(last.get("leverage", 0)))
            real_mode = str(last.get("marginMode", "")).upper()
            if real_lev == target and (
                not real_mode or real_mode == LIVE_MARGIN_MODE
            ):
                return last

        raise RuntimeError(
            f"leverage NOT confirmed: requested {target}x; "
            f"exchange says leverage={last.get('leverage','?')} "
            f"marginMode={last.get('marginMode','?')}"
        )


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
    leverage: int = 0

    # Entry-time market thesis level ("LONG deteriorates below..." / inverse).
    thesis_invalidation: float = 0.0

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
        self.day_start_equity = 0.0
        self.day_peak_pnl = 0.0
        self.last_close_time = 0.0
        self.position: Optional[LivePositionState] = None
        self.consumed: List[str] = []
        self.bot_closed_position_ids: List[str] = []
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
            self.day_start_equity = float(d.get("day_start_equity", 0))
            self.day_peak_pnl = float(d.get("day_peak_pnl", self.day_pnl))
            self.last_close_time = float(d.get("last_close_time", 0))
            self.consumed = list(d.get("consumed", []))[-100:]
            self.bot_closed_position_ids = [
                str(x) for x in d.get("bot_closed_position_ids", [])
                if str(x)
            ][-50:]

            raw_pos = d.get("position")
            if raw_pos:
                allowed = {f.name for f in fields(LivePositionState)}
                clean = {k: v for k, v in raw_pos.items() if k in allowed}
                self.position = LivePositionState(**clean)
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
            "day_start_equity": self.day_start_equity,
            "day_peak_pnl": self.day_peak_pnl,
            "last_close_time": self.last_close_time,
            "consumed": self.consumed[-100:],
            "bot_closed_position_ids": self.bot_closed_position_ids[-50:],
            "position": asdict(self.position) if self.position else None,
        }
        STATE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

    def new_day(self):
        today = C.datetime.now(C.TZ).date().isoformat()
        if today != self.day:
            self.day = today
            self.trades_today = 0
            self.day_pnl = 0.0
            self.day_start_equity = 0.0
            self.day_peak_pnl = 0.0
            self.bot_closed_position_ids = []
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

        self.tg = C.Telegram(C.TELEGRAM_BOT_TOKEN, C.TELEGRAM_CHAT_ID)
        self.pub = C.BitunixPublic()
        self.live = C.LiveMarket()
        self.analyzer = C.Analyzer(self.pub, self.live)
        self.api = BitunixPrivate(API_KEY, SECRET_KEY)
        self.state = State()

        self.base_precision = 4
        self.price_precision = 1
        self.min_qty = 0.0001
        self.max_leverage = LIVE_MAX_LEVERAGE if LIVE_DYNAMIC_LEVERAGE else LIVE_LEVERAGE

        self.last_analysis = 0.0
        self.plan = None
        self.last_block_notice = {}
        self._closed_day_cache_at = 0.0
        self._closed_day_cache = None

        # Smart-exit confirmation state.
        self.flip_count = 0
        self.flip_key = ""

        self.load_pair_rules()
        self.auth_preflight()
        self.reconcile_bot_day_pnl_from_fills()

    # -----------------------------
    # Market / startup checks
    # -----------------------------

    def load_pair_rules(self):
        rows = self.pub.get(
            "/api/v1/futures/market/trading_pairs",
            {"symbols": SYMBOL},
        ) or []
        if not rows:
            raise RuntimeError("Could not load BTCUSDT trading rules.")

        x = rows[0]
        self.base_precision = int(x.get("basePrecision", 4))
        self.price_precision = int(
            x.get("quotePrecision", x.get("pricePrecision", 1))
        )
        self.min_qty = fnum(x.get("minTradeVolume", 0.0001), 0.0001)
        self.max_leverage = int(x.get("maxLeverage", LIVE_MAX_LEVERAGE))

        if LIVE_MIN_LEVERAGE <= 0 or LIVE_MAX_LEVERAGE <= 0:
            raise RuntimeError("Leverage bounds must be positive.")
        if LIVE_MIN_LEVERAGE > LIVE_MAX_LEVERAGE:
            raise RuntimeError(
                f"LIVE_MIN_LEVERAGE={LIVE_MIN_LEVERAGE} > "
                f"LIVE_MAX_LEVERAGE={LIVE_MAX_LEVERAGE}."
            )
        configured_max = LIVE_MAX_LEVERAGE if LIVE_DYNAMIC_LEVERAGE else LIVE_LEVERAGE
        configured_min = LIVE_MIN_LEVERAGE if LIVE_DYNAMIC_LEVERAGE else LIVE_LEVERAGE
        if configured_min > self.max_leverage:
            raise RuntimeError(
                f"Minimum/fixed leverage {configured_min}x > Bitunix maxLeverage "
                f"{self.max_leverage}x for {SYMBOL}."
            )
        if configured_max > self.max_leverage:
            log(
                f"Configured leverage max {configured_max}x exceeds pair max "
                f"{self.max_leverage}x; clamping to exchange max."
            )

        # Position tiers can impose a lower leverage cap as notional grows.
        self.position_tiers = []
        try:
            tiers = self.pub.get(
                "/api/v1/futures/position/get_position_tiers",
                {"symbol": SYMBOL},
            ) or []
            if isinstance(tiers, list):
                self.position_tiers = [t for t in tiers if isinstance(t, dict)]
        except Exception as e:
            log(f"Position tiers unavailable; using pair max leverage only: {e}")

    def auth_preflight(self):
        # Signed calls prove credentials/signature work.
        _ = self.api.account(MARGIN_COIN)
        pos = self.api.positions(SYMBOL)
        log(f"Private API OK. Existing positions={len(pos)}")

        if pos and self.state.position is None:
            self.state.auto_enabled = False
            self.state.locked = True
            self.state.lock_reason = (
                "Existing BTCUSDT position detected but no persisted bot state."
            )
            self.state.save()
            self.tg.send(
                "🛑 <b>LIVE AUTO BLOQUEADO</b>\n\n"
                "Hay una posición BTCUSDT real abierta que este bot no puede "
                "demostrar que sea suya.\n"
                "NO la adoptaré, NO la modificaré y NO abriré otra.\n\n"
                "Cuando ya no exista esa posición usa /unlock y después /live_on."
            )

    # -----------------------------
    # Signal one-shot / duplicate
    # -----------------------------

    def signal_id(self, plan) -> str:
        try:
            ts = int(self.analyzer.frames["15m"].iloc[-1]["time"])
        except Exception:
            ts = int(time.time() // 900 * 900_000)

        raw = f"{ts}|{plan.action}|{plan.setup}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:6]
        side = "L" if "LONG" in plan.action else "S"
        dt = C.datetime.fromtimestamp(ts / 1000, C.TZ)
        return f"igod{dt:%y%m%d%H%M}{side}{h}"

    def exchange_has_signal(self, client_id: str) -> bool:
        """
        Duplicate exists ONLY when returned clientId exactly equals ours.
        A non-empty API response by itself is NOT treated as a duplicate.
        """
        try:
            pending = self.api.pending_orders(client_id)
            if any(str(x.get("clientId", "")) == client_id for x in pending):
                return True
            if pending:
                log(
                    f"Pending response had {len(pending)} row(s) but none "
                    f"matched clientId={client_id}; ignored."
                )

            history = self.api.history_orders(client_id)
            if any(str(x.get("clientId", "")) == client_id for x in history):
                return True
            if history:
                log(
                    f"History response had {len(history)} row(s) but none "
                    f"matched clientId={client_id}; ignored."
                )
        except Exception as e:
            # Fail closed: if duplicate verification itself fails, do not trade.
            log(f"Signal-history check error: {e}")
            return True

        return False

    def closed_today_metrics_cached(self, ttl=30):
        now = time.time()
        if (
            self._closed_day_cache is not None
            and now - self._closed_day_cache_at < ttl
        ):
            return self._closed_day_cache
        d = self.closed_today_metrics()
        self._closed_day_cache = d
        self._closed_day_cache_at = now
        return d

    def profit_lock_day_pnl(self):
        if LIVE_PROFIT_LOCK_USE_ACCOUNT_DAY:
            try:
                return fnum(self.closed_today_metrics_cached().get("net"))
            except Exception as e:
                log(f"Account-day PnL unavailable for profit lock: {e}")
        return self.state.day_pnl

    def ensure_day_equity_baseline(self):
        if self.state.day_start_equity > 0:
            return self.state.day_start_equity
        try:
            a = self.account_snapshot()
            day_net = self.profit_lock_day_pnl()
            base = fnum(a.get("wallet_est")) - day_net
            if base <= 0:
                base = fnum(a.get("equity_est"))
            if base > 0:
                self.state.day_start_equity = base
                self.state.save()
                log(f"Day equity baseline estimated at {base:.4f} USDT")
                return base
        except Exception as e:
            log(f"Could not set day equity baseline: {e}")
        return 0.0

    def discover_bot_position_ids_today(self):
        """
        Recover closed I-GOD positionIds after a restart.

        Bitunix does not expose positionId on history-order rows. We therefore:
        1) query exact consumed I-GOD clientIds;
        2) keep FILLED opening orders;
        3) match them to history positions using creation time, direction,
           leverage and quantity.

        Matching is intentionally strict to avoid adopting manual trades.
        """
        now = C.datetime.now(C.TZ)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start.timestamp() * 1000)
        today_prefix = f"igod{now:%y%m%d}"

        positions = [
            x for x in self.api.history_positions(limit=100)
            if int(fnum(x.get("ctime"), 0)) >= start_ms
        ]

        found = set(self.state.bot_closed_position_ids)

        for client_id in self.state.consumed:
            client_id = str(client_id)
            if not client_id.startswith(today_prefix):
                continue

            try:
                orders = self.api.history_orders(client_id)
            except Exception as e:
                log(f"Bot-PnL recovery history order error {client_id}: {e}")
                continue

            exact = [
                o for o in orders
                if isinstance(o, dict)
                and str(o.get("clientId", "")) == client_id
                and str(o.get("status", "")).upper() == "FILLED"
                and not bool(o.get("reduceOnly", False))
            ]
            if not exact:
                continue

            # There should be only one opening order for our one-shot clientId.
            o = exact[0]
            oqty = fnum(o.get("tradeQty")) or fnum(o.get("qty"))
            octime = int(fnum(o.get("ctime"), 0))
            olev = int(fnum(o.get("leverage"), 0))
            oside = str(o.get("side", "")).upper()
            pside = "LONG" if oside == "BUY" else "SHORT"

            candidates = []
            for p0 in positions:
                pid = str(p0.get("positionId", ""))
                if not pid or pid in found:
                    continue
                if str(p0.get("side", "")).upper() != pside:
                    continue

                pctime = int(fnum(p0.get("ctime"), 0))
                dt = abs(pctime - octime)
                if octime <= 0 or dt > 180_000:
                    continue

                plev = int(fnum(p0.get("leverage"), 0))
                if olev > 0 and plev > 0 and olev != plev:
                    continue

                pqty = fnum(p0.get("maxQty"))
                if oqty > 0 and pqty > 0:
                    rel = abs(pqty - oqty) / max(oqty, 1e-9)
                    if rel > 0.08:
                        continue
                else:
                    rel = 1.0

                # Lower score is better; time dominates, qty breaks ties.
                score = dt + rel * 10_000
                candidates.append((score, pid))

            candidates.sort(key=lambda x: x[0])
            if candidates:
                pid = candidates[0][1]
                found.add(pid)
                log(
                    f"Recovered I-GOD closed position {pid} "
                    f"from clientId={client_id}."
                )

        return sorted(found)

    def reconcile_bot_day_pnl_from_fills(self):
        """
        Rebuild bot-only day PnL from confirmed I-GOD positionIds.

        This is independent from manual trades and is the value used by the
        bot's own daily-loss guard.
        """
        try:
            ids = self.discover_bot_position_ids_today()
            if not ids:
                log(
                    "No I-GOD closed position IDs recovered today; "
                    "keeping persisted bot day PnL."
                )
                return self.state.day_pnl, 0

            total = 0.0
            valid_ids = []
            for pid in ids:
                hist = self.api.history_position(pid)
                if not hist:
                    continue
                fm = self.trade_fill_metrics(
                    pid,
                    funding=fnum(hist.get("funding")),
                )
                total += fm["net"]
                valid_ids.append(pid)

            if not valid_ids:
                return self.state.day_pnl, 0

            if abs(self.state.day_pnl - total) > 1e-6:
                log(
                    f"Reconciled bot day PnL from confirmed positions: "
                    f"{self.state.day_pnl:+.4f} -> {total:+.4f}"
                )

            self.state.bot_closed_position_ids = valid_ids
            self.state.day_pnl = total
            self.state.save()
            return total, len(valid_ids)

        except Exception as e:
            log(f"Could not reconcile bot day PnL: {e}")
            return self.state.day_pnl, 0

    def daily_profit_target_usdt(self):
        eq = self.ensure_day_equity_baseline()
        return eq * LIVE_DAILY_PROFIT_TARGET_PCT if eq > 0 else 0.0

    def refresh_profit_lock_peak(self):
        pnl = self.profit_lock_day_pnl()
        if pnl > self.state.day_peak_pnl:
            self.state.day_peak_pnl = pnl
            self.state.save()
        return pnl

    def profit_lock_active(self):
        self.refresh_profit_lock_peak()
        target = self.daily_profit_target_usdt()
        return target > 0 and self.state.day_peak_pnl >= target

    def profit_lock_floor(self):
        return (
            self.state.day_peak_pnl * LIVE_PROFIT_LOCK_RETAIN_PCT
            if self.profit_lock_active()
            else 0.0
        )

    def profit_lock_guard(self, plan, net_rr):
        if not self.profit_lock_active():
            return True, "normal mode"

        needed_bias = (
            "LONG STRONG"
            if plan.action == "ENTER LONG NOW"
            else "SHORT STRONG"
        )
        if str(plan.bias).upper() != needed_bias:
            return False, (
                f"profit-lock: requires {needed_bias}, got {plan.bias}"
            )

        if net_rr < LIVE_PROFIT_LOCK_MIN_NET_RR:
            return False, (
                f"profit-lock: net R:R {net_rr:.2f} < "
                f"{LIVE_PROFIT_LOCK_MIN_NET_RR:.2f}"
            )

        floor = self.profit_lock_floor()
        day_pnl = self.profit_lock_day_pnl()
        if floor > 0 and day_pnl <= floor:
            return False, (
                f"profit-lock floor reached: {day_pnl:.2f} <= {floor:.2f}"
            )

        return True, "profit-lock A+ accepted"

    def account_position_mode(self) -> str:
        try:
            a = self.api.account(MARGIN_COIN)
            return str(a.get("positionMode", "")).upper()
        except Exception:
            return ""

    def can_enter(self, plan, client_id, bypass_cooldown=False):
        self.state.new_day()

        if not LIVE_EXECUTION:
            return False, "LIVE_EXECUTION=false"

        acct_mode = self.account_position_mode()
        if acct_mode != "ONE_WAY":
            return False, (
                f"account position mode {acct_mode or 'UNKNOWN'} != ONE_WAY"
            )
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
        if self.api.pending_tpsl():
            return False, "pending BTCUSDT TP/SL order exists"
        if not self.state.entry_armed:
            return False, "same ENTER cycle already consumed"
        if client_id in self.state.consumed:
            return False, "signal already consumed locally"
        if self.exchange_has_signal(client_id):
            return False, "signal already exists in Bitunix history"
        max_trades_now = LIVE_MAX_TRADES_DAY + (
            LIVE_PROFIT_LOCK_EXTRA_TRADES if self.profit_lock_active() else 0
        )
        if self.state.trades_today >= max_trades_now:
            return False, f"daily trade limit reached ({max_trades_now})"
        if self.state.day_pnl <= -abs(LIVE_MAX_DAILY_LOSS_USDT):
            return False, "daily loss limit reached"

        if self.profit_lock_active():
            floor = self.profit_lock_floor()
            day_pnl = self.profit_lock_day_pnl()
            if floor > 0 and day_pnl <= floor:
                return False, (
                    f"daily profit protected: {day_pnl:.2f} "
                    f"<= floor {floor:.2f}"
                )

        if (
            not bypass_cooldown
            and self.state.last_close_time
            and time.time() - self.state.last_close_time
                < LIVE_COOLDOWN_MIN * 60
        ):
            return False, "post-trade cooldown"

        return True, "ok"

    # -----------------------------
    # Sizing / cost guard
    # -----------------------------

    def sizing_budget(self, risk_multiplier: float = 1.0):
        """
        Dynamic per-entry budget.

        EQUITY:
          base margin = min(equity, available) * allocation %
          risk cap    = equity * risk %
          both are reduced by Profit Lock multiplier when active.

        FIXED:
          preserves legacy LIVE_MARGIN_USDT / LIVE_MAX_RISK_USDT.
        """
        risk_multiplier = max(0.05, min(1.0, float(risk_multiplier)))

        if LIVE_SIZING_MODE == "EQUITY":
            a = self.account_snapshot()
            equity = max(0.0, fnum(a.get("equity_est")))
            available = max(0.0, fnum(a.get("available")))

            if equity <= 0 or available <= 0:
                raise RuntimeError(
                    f"Invalid sizing data: equity={equity}, available={available}"
                )

            alloc = max(0.05, min(1.0, LIVE_EQUITY_ALLOC_PCT))
            risk_pct = max(0.001, min(0.50, LIVE_RISK_PCT))

            base_margin = min(equity, available) * alloc * risk_multiplier
            risk_cap = equity * risk_pct * risk_multiplier

            return {
                "mode": "EQUITY",
                "equity": equity,
                "available": available,
                "base_margin": base_margin,
                "risk_cap": risk_cap,
                "alloc_pct": alloc,
                "risk_pct": risk_pct,
            }

        return {
            "mode": "FIXED",
            "equity": 0.0,
            "available": 0.0,
            "base_margin": LIVE_MARGIN_USDT * risk_multiplier,
            "risk_cap": LIVE_MAX_RISK_USDT * risk_multiplier,
            "alloc_pct": 0.0,
            "risk_pct": 0.0,
        }

    def tier_leverage_cap(self, notional: float) -> int:
        cap = max(1, int(self.max_leverage))
        n = max(0.0, float(notional))
        for tier in getattr(self, "position_tiers", []):
            start = fnum(tier.get("startValue"), 0.0)
            end = fnum(tier.get("endValue"), 0.0)
            lev = int(fnum(tier.get("leverage"), cap))
            if n >= start and (end <= 0 or n <= end):
                cap = min(cap, max(1, lev))
                break
        return cap

    def choose_leverage(
        self,
        price: float,
        stop: float,
        base_margin: float,
        risk_cap: float,
    ):
        """
        Choose only as much leverage as is useful to express the configured
        stop-risk budget. Leverage is NOT a confidence score.
        """
        if not LIVE_DYNAMIC_LEVERAGE:
            lev = min(int(LIVE_LEVERAGE), int(self.max_leverage))
            if lev <= 0:
                raise RuntimeError("Invalid fixed leverage.")
            return lev, {
                "mode": "FIXED",
                "needed": lev,
                "tier_cap": int(self.max_leverage),
                "risk_notional": 0.0,
            }

        stop_distance = abs(float(price) - float(stop))
        if price <= 0 or stop_distance <= 0 or base_margin <= 0 or risk_cap <= 0:
            raise RuntimeError("Invalid inputs for dynamic leverage selection.")

        risk_qty = risk_cap / stop_distance
        risk_notional = risk_qty * price
        pair_cap = min(int(self.max_leverage), int(LIVE_MAX_LEVERAGE))
        target_notional = min(risk_notional, base_margin * pair_cap)
        tier_cap = min(pair_cap, self.tier_leverage_cap(target_notional))

        if tier_cap < LIVE_MIN_LEVERAGE:
            raise RuntimeError(
                f"Exchange/tier leverage cap {tier_cap}x is below configured "
                f"minimum {LIVE_MIN_LEVERAGE}x for this notional."
            )

        needed = int(math.ceil(risk_notional / max(base_margin, 1e-9)))
        selected = max(int(LIVE_MIN_LEVERAGE), needed)
        selected = min(selected, int(LIVE_MAX_LEVERAGE), int(tier_cap))

        return selected, {
            "mode": "AUTO",
            "needed": needed,
            "tier_cap": tier_cap,
            "risk_notional": risk_notional,
        }

    def execution_margin_cap(
        self,
        available: float,
        configured_base_margin: float,
        leverage: int,
    ):
        """
        Maximum margin we are willing to consume for this order.

        Reserve:
        - explicit wallet cash buffer;
        - estimated round-trip taker fee + slippage on the leveraged notional.

        This prevents high leverage from turning a 95% allocation into an
        exchange-side 'Insufficient balance' rejection.
        """
        available = max(0.0, float(available))
        configured_base_margin = max(0.0, float(configured_base_margin))
        lev = max(1, int(leverage))

        cash_keep = available * max(
            0.0, min(0.50, LIVE_EXECUTION_CASH_RESERVE_PCT)
        )
        roundtrip_rate = 2.0 * max(
            0.0, LIVE_TAKER_FEE_RATE + LIVE_SLIPPAGE_RATE
        )

        spendable_before_costs = max(0.0, available - cash_keep)
        safe_margin = spendable_before_costs / max(
            1.0 + lev * roundtrip_rate,
            1e-9,
        )
        safe_margin = min(configured_base_margin, safe_margin)

        return {
            "safe_margin": safe_margin,
            "cash_keep": cash_keep,
            "roundtrip_rate": roundtrip_rate,
            "available": available,
        }

    def calc_qty(
        self,
        price: float,
        stop: float,
        base_margin: float,
        risk_cap: float,
        leverage: int,
    ):
        desired_notional = base_margin * leverage
        qty_by_exposure = desired_notional / price

        stop_distance = abs(price - stop)
        if stop_distance <= 0:
            raise RuntimeError("Invalid stop distance; cannot size position.")

        # Risk cap is applied to an estimated NET stop-out, not only to the
        # chart distance. Include both taker fees, normal entry slippage and a
        # wider adverse-fill reserve for the stop-market execution.
        entry_cost_per_btc = (
            price * LIVE_TAKER_FEE_RATE
            + price * LIVE_SLIPPAGE_RATE
        )
        stop_cost_per_btc = (
            stop * LIVE_TAKER_FEE_RATE
            + stop * LIVE_STOP_SLIPPAGE_RATE
        )
        net_stop_risk_per_btc = (
            stop_distance + entry_cost_per_btc + stop_cost_per_btc
        )

        qty_by_risk = risk_cap / max(net_stop_risk_per_btc, 1e-9)
        raw_qty = min(qty_by_exposure, qty_by_risk)
        qty = floor_prec(raw_qty, self.base_precision)

        if qty < self.min_qty:
            raise RuntimeError(
                f"Calculated qty {qty} < minTradeVolume {self.min_qty}."
            )

        if LIVE_TP1_PCT <= 0 or LIVE_TP2_PCT <= 0 or LIVE_RUNNER_PCT <= 0:
            raise RuntimeError(
                "Invalid exit split: TP1 + TP2 must leave a positive runner."
            )

        actual_notional = qty * price
        estimated_price_sl_risk = qty * stop_distance
        estimated_net_sl_risk = qty * net_stop_risk_per_btc

        q1 = floor_prec(qty * LIVE_TP1_PCT, self.base_precision)
        q2 = floor_prec(qty * LIVE_TP2_PCT, self.base_precision)
        runner = floor_prec(qty - q1 - q2, self.base_precision)

        if q1 < self.min_qty or q2 < self.min_qty or runner < self.min_qty:
            raise RuntimeError(
                f"Position qty {qty} too small for exit split "
                f"TP1={q1}, TP2={q2}, runner={runner}, min={self.min_qty}."
            )

        return (
            qty,
            actual_notional,
            q1,
            q2,
            runner,
            estimated_price_sl_risk,
            estimated_net_sl_risk,
        )

    def net_rr_guard(self, plan, qty: float):
        """
        Conservative pre-trade estimate:
        whole position compared from entry to TP2 vs entry to SL,
        charging taker fee + slippage on both legs.
        This is only a guard. Actual PnL later comes from Bitunix.
        """
        entry = fnum(plan.price)
        stop = fnum(plan.stop)
        tp2 = fnum(plan.tp2)
        if entry <= 0 or stop <= 0 or tp2 <= 0:
            return False, "invalid prices for net-RR guard", {}

        side_long = plan.action == "ENTER LONG NOW"
        gross_reward = (
            (tp2 - entry) * qty
            if side_long else
            (entry - tp2) * qty
        )
        gross_risk = abs(entry - stop) * qty

        entry_notional = entry * qty
        tp_notional = tp2 * qty
        stop_notional = stop * qty

        reward_cost = (
            entry_notional * LIVE_TAKER_FEE_RATE
            + tp_notional * LIVE_TAKER_FEE_RATE
            + (entry_notional + tp_notional) * LIVE_SLIPPAGE_RATE
        )
        risk_cost = (
            entry_notional * LIVE_TAKER_FEE_RATE
            + stop_notional * LIVE_TAKER_FEE_RATE
            + (entry_notional + stop_notional) * LIVE_SLIPPAGE_RATE
        )

        net_reward = gross_reward - reward_cost
        net_risk = gross_risk + risk_cost
        net_rr = net_reward / max(net_risk, 1e-9)

        data = {
            "gross_reward": gross_reward,
            "gross_risk": gross_risk,
            "reward_cost": reward_cost,
            "risk_cost": risk_cost,
            "net_reward": net_reward,
            "net_risk": net_risk,
            "net_rr": net_rr,
        }

        if net_reward <= 0:
            return False, "expected TP2 reward is <= 0 after estimated costs", data
        if net_rr < LIVE_MIN_NET_RR:
            return (
                False,
                f"net R:R {net_rr:.2f} < minimum {LIVE_MIN_NET_RR:.2f}",
                data,
            )
        return True, "ok", data

    # -----------------------------
    # Position opening / protection
    # -----------------------------

    def wait_for_position(self, timeout=18):
        end = time.time() + timeout
        while time.time() < end:
            rows = self.api.positions(SYMBOL)
            if rows:
                return rows[0]
            time.sleep(1)
        return None

    def wait_position_gone(self, position_id: str, timeout=18):
        end = time.time() + timeout
        while time.time() < end:
            if self.api.position_by_id(position_id) is None:
                return True
            time.sleep(1)
        return False

    def emergency_close_and_lock(self, reason):
        ps = self.state.position
        if ps:
            try:
                self.api.flash_close_position(ps.position_id)
            except Exception as e:
                reason += f" | close error: {e}"

        self.state.auto_enabled = False
        self.state.locked = True
        self.state.lock_reason = reason
        self.state.save()

        self.tg.send(
            "🚨🛑 <b>EMERGENCY LIVE LOCK</b>\n\n"
            f"{C.html.escape(reason)}\n\n"
            "Nuevas entradas desactivadas. Revisa Bitunix."
        )

    def ensure_stop(self, position_id: str, stop: float):
        """
        Ensure the EXCHANGE itself shows the requested stop price.
        Never treat "some SL exists" as proof that the modification succeeded.
        """
        target = round(float(stop), self.price_precision)
        stop_s = fmt_price(target, self.price_precision)
        tol = max(10 ** (-self.price_precision) / 2, 1e-9)

        def read_stop_rows():
            rows = self.api.pending_tpsl(position_id)
            return [
                x for x in rows
                if isinstance(x, dict) and fnum(x.get("slPrice")) > 0
            ]

        def exact_row(rows):
            for row in rows:
                if abs(fnum(row.get("slPrice")) - target) <= tol:
                    return row
            return None

        # First try the documented position-level modify endpoint.
        first_error = None
        try:
            self.api.modify_position_stop(position_id, stop_s)
        except Exception as e:
            first_error = e

        for _ in range(4):
            time.sleep(0.45)
            rows = read_stop_rows()
            hit = exact_row(rows)
            if hit is not None:
                return fnum(hit.get("slPrice"))

        # If a concrete SL order exists, modify that exact order by its ID.
        rows = read_stop_rows()
        for row in rows:
            oid = str(row.get("id", row.get("orderId", ""))).strip()
            qty = fnum(row.get("slQty"))
            if oid and qty > 0:
                self.api.modify_tpsl_stop(
                    oid,
                    stop_s,
                    fmt_qty(qty, self.base_precision),
                )
                for _ in range(4):
                    time.sleep(0.45)
                    rows2 = read_stop_rows()
                    hit = exact_row(rows2)
                    if hit is not None:
                        return fnum(hit.get("slPrice"))

        # Only place a new position-level stop when there is no SL at all.
        rows = read_stop_rows()
        if not rows:
            self.api.place_position_stop(position_id, stop_s)
            for _ in range(4):
                time.sleep(0.45)
                rows2 = read_stop_rows()
                hit = exact_row(rows2)
                if hit is not None:
                    return fnum(hit.get("slPrice"))

        actual = sorted(
            {round(fnum(x.get("slPrice")), self.price_precision) for x in read_stop_rows()}
        )
        extra = f" | first modify error: {first_error}" if first_error else ""
        raise RuntimeError(
            f"Requested SL {stop_s} NOT confirmed on exchange; "
            f"exchange SL(s)={actual or 'NONE'}{extra}"
        )

    def place_native_tps(
        self,
        pos_state: LivePositionState,
        qty_tp1: float,
        qty_tp2: float,
    ):
        """Place exactly two native partial TPs. TP3 is reference only."""
        d1 = self.api.place_partial_tp(
            pos_state.position_id,
            fmt_price(pos_state.tp1, self.price_precision),
            fmt_qty(qty_tp1, self.base_precision),
        )
        time.sleep(0.35)
        d2 = self.api.place_partial_tp(
            pos_state.position_id,
            fmt_price(pos_state.tp2, self.price_precision),
            fmt_qty(qty_tp2, self.base_precision),
        )

        post_id1 = str(d1.get("orderId", d1.get("id", ""))) if isinstance(d1, dict) else ""
        post_id2 = str(d2.get("orderId", d2.get("id", ""))) if isinstance(d2, dict) else ""

        time.sleep(0.8)
        rows = self.api.pending_tpsl(pos_state.position_id)
        tp_rows = [
            x for x in rows
            if isinstance(x, dict) and str(x.get("tpPrice", "")).strip()
        ]
        if len(tp_rows) < 2:
            raise RuntimeError(
                f"Expected >=2 native TP orders, found {len(tp_rows)}."
            )

        def nearest_tp_id(target):
            candidates = []
            for row in tp_rows:
                try:
                    px = float(row.get("tpPrice"))
                except Exception:
                    continue
                oid = str(row.get("id", row.get("orderId", "")))
                candidates.append((abs(px - float(target)), oid))
            candidates.sort(key=lambda z: z[0])
            return candidates[0][1] if candidates else ""

        pos_state.tp1_order_id = nearest_tp_id(pos_state.tp1) or post_id1
        pos_state.tp2_order_id = nearest_tp_id(pos_state.tp2) or post_id2
        pos_state.tp3_order_id = ""

        if not pos_state.tp1_order_id or not pos_state.tp2_order_id:
            raise RuntimeError(
                "Native TPs visible but order IDs could not be resolved."
            )

    def verify_real_position(self, pos: dict, qty_requested: float, expected_leverage: int):
        problems = []

        lev = int(fnum(pos.get("leverage", 0)))
        margin_mode = str(pos.get("marginMode", "")).upper()
        position_mode = str(pos.get("positionMode", "")).upper()
        qty_real = fnum(pos.get("qty", 0))
        margin_real = fnum(pos.get("margin", 0))

        if lev != int(expected_leverage):
            problems.append(
                f"leverage real {lev}x != requested {expected_leverage}x"
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

        if (
            LIVE_MARGIN_MODE == "ISOLATION"
            and LIVE_MARGIN_USDT > 0
            and margin_real > 0
        ):
            diff = abs(margin_real - LIVE_MARGIN_USDT) / LIVE_MARGIN_USDT
            if diff > VERIFY_MARGIN_TOL_PCT:
                problems.append(
                    f"margin real {margin_real:.3f} differs too much "
                    f"from target {LIVE_MARGIN_USDT:.3f}"
                )

        if problems:
            raise RuntimeError("; ".join(problems))

    def notify_entry_blocked(self, plan, client_id: str, reason: str):
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

    def open_real(self, plan, bypass_cooldown=False, reversal=False):
        client_id = self.signal_id(plan)
        ok, why = self.can_enter(
            plan,
            client_id,
            bypass_cooldown=bypass_cooldown,
        )
        if not ok:
            log(f"Entry blocked: {why}")
            self.notify_entry_blocked(plan, client_id, why)
            return False

        if None in (plan.stop, plan.tp1, plan.tp2):
            reason = "incomplete SL/TP plan"
            log(f"Entry blocked: {reason}")
            self.notify_entry_blocked(plan, client_id, reason)
            return False

        side = "BUY" if plan.action == "ENTER LONG NOW" else "SELL"
        side_name = "LONG" if side == "BUY" else "SHORT"

        risk_mult = (
            LIVE_PROFIT_LOCK_RISK_MULT
            if self.profit_lock_active()
            else 1.0
        )
        sizing = self.sizing_budget(risk_mult)
        selected_leverage, lev_info = self.choose_leverage(
            fnum(plan.price),
            fnum(plan.stop),
            base_margin=sizing["base_margin"],
            risk_cap=sizing["risk_cap"],
        )

        margin_guard = self.execution_margin_cap(
            available=sizing.get("available", sizing["base_margin"]),
            configured_base_margin=sizing["base_margin"],
            leverage=selected_leverage,
        )
        execution_base_margin = margin_guard["safe_margin"]
        if execution_base_margin <= 0:
            reason = "no executable margin remains after fee/cash reserve"
            log(f"Entry blocked: {reason}")
            self.notify_entry_blocked(plan, client_id, reason)
            return False

        (
            qty,
            intended_notional,
            qty_tp1,
            qty_tp2,
            runner_qty,
            estimated_price_sl_risk,
            estimated_net_sl_risk,
        ) = self.calc_qty(
            fnum(plan.price),
            fnum(plan.stop),
            base_margin=execution_base_margin,
            risk_cap=sizing["risk_cap"],
            leverage=selected_leverage,
        )

        cost_ok, cost_reason, costs = self.net_rr_guard(plan, qty)
        if not cost_ok:
            reason = f"fees/slippage guard: {cost_reason}"
            log(f"Entry blocked: {reason}")
            self.notify_entry_blocked(plan, client_id, reason)
            return False

        lock_ok, lock_reason = self.profit_lock_guard(
            plan, costs["net_rr"]
        )
        if not lock_ok:
            log(f"Entry blocked: {lock_reason}")
            self.notify_entry_blocked(plan, client_id, lock_reason)
            return False

        try:
            lev_state = self.api.change_leverage_verified(selected_leverage)
            log(
                f"Leverage VERIFIED at {selected_leverage}x "
                f"(exchange={lev_state.get('leverage')}x, "
                f"mode={lev_state.get('marginMode','?')}, "
                f"needed={lev_info['needed']}x, tier_cap={lev_info['tier_cap']}x)."
            )
        except Exception as e:
            reason = f"could not set leverage {selected_leverage}x: {e}"
            log(f"Entry blocked: {reason}")
            self.notify_entry_blocked(plan, client_id, reason)
            return False

        self.state.entry_armed = False
        self.state.consumed.append(client_id)
        self.state.save()

        title = (
            "🔄🚨 <b>ENVIANDO REVERSAL REAL</b>"
            if reversal else
            "⚠️🚨 <b>ENVIANDO ORDEN REAL</b>"
        )
        self.tg.send(
            title + "\n\n"
            f"{side_name} {SYMBOL}\n"
            f"Señal: <code>{client_id}</code>\n"
            f"Sizing: <b>{sizing['mode']}</b>\n"
            f"Equity referencia: <b>{sizing['equity']:.2f} USDT</b>\n"
            f"Base margen dinámica: <b>{sizing['base_margin']:.2f} USDT</b>\n"
            f"Margen ejecutable tras reserva: <b>{execution_base_margin:.2f} USDT</b>\n"
            f"Reserva cash mínima: <b>{margin_guard['cash_keep']:.2f} USDT</b>\n"
            f"Risk cap dinámico: <b>{sizing['risk_cap']:.2f} USDT</b>\n"
            f"Leverage AUTO seleccionado y verificado: <b>{selected_leverage}x</b> "
            f"(rango {LIVE_MIN_LEVERAGE}–{min(LIVE_MAX_LEVERAGE, self.max_leverage)}x)\n"
            f"Nominal calculado: <b>{intended_notional:.2f} USDT</b>\n"
            f"Riesgo precio al SL: <b>{estimated_price_sl_risk:.2f} USDT</b>\n"
            f"Riesgo NETO estimado al SL: <b>{estimated_net_sl_risk:.2f} USDT</b> "
            f"(cap {sizing['risk_cap']:.2f})\n"
            f"Modo diario: <b>{'PROFIT LOCK' if self.profit_lock_active() else 'NORMAL'}</b>\n"
            f"Multiplicador riesgo: <b>{risk_mult:.2f}x</b>\n"
            f"R:R NETO estimado a TP2: <b>{costs['net_rr']:.2f}R</b>\n"
            f"Costes estimados ida/vuelta TP2: "
            f"<b>{costs['reward_cost']:.2f} USDT</b>\n"
            f"Qty: <b>{fmt_qty(qty, self.base_precision)} BTC</b>\n"
            f"SL: <b>{p(plan.stop)}</b>\n"
            f"TP1 {LIVE_TP1_PCT*100:.0f}%: <b>{p(plan.tp1)}</b>\n"
            f"TP2 {LIVE_TP2_PCT*100:.0f}%: <b>{p(plan.tp2)}</b>\n"
            f"Runner esperado: <b>{LIVE_RUNNER_PCT*100:.0f}%</b>\n"
            f"TP3 planner (solo referencia): <b>{p(plan.tp3) if plan.tp3 else '-'}</b>"
        )

        try:
            order = self.api.place_market(
                side=side,
                qty=fmt_qty(qty, self.base_precision),
                client_id=client_id,
                sl_price=fmt_price(plan.stop, self.price_precision),
            )
        except BitunixAPIError as e:
            self.tg.send(
                "❌ <b>Bitunix rechazó/contestó la entrada</b>\n\n"
                f"code={e.code}\n{C.html.escape(e.msg)}\n"
                "No reenviaré automáticamente esta señal."
            )
            return False
        except Exception as e:
            self.state.auto_enabled = False
            self.state.locked = True
            self.state.lock_reason = f"Order send uncertainty: {e}"
            self.state.save()
            self.tg.send(
                "🚨 <b>ERROR/INCERTIDUMBRE AL ENVIAR ORDEN</b>\n\n"
                f"{C.html.escape(str(e))}\n"
                "He bloqueado nuevas entradas para evitar duplicados."
            )
            return False

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
                f"Estado: {C.html.escape(str(detail.get('status','?')))}\n"
                "He bloqueado nuevas entradas. Revisa Bitunix."
            )
            return False

        try:
            self.verify_real_position(pos, qty, selected_leverage)
        except Exception as e:
            self.state.position = LivePositionState(
                position_id=str(pos.get("positionId", "")),
                client_id=client_id,
                side=side_name,
                entry=fnum(pos.get("avgOpenPrice")),
                qty_initial=fnum(pos.get("qty")),
                stop_initial=fnum(plan.stop),
                r_value=abs(fnum(pos.get("avgOpenPrice")) - fnum(plan.stop)),
                tp1=fnum(plan.tp1),
                tp2=fnum(plan.tp2),
                tp3=fnum(plan.tp3),
                leverage=selected_leverage,
            )
            self.state.save()
            self.emergency_close_and_lock(
                "POSITION VERIFICATION FAILED: " + str(e)
            )
            return False

        position_id = str(pos["positionId"])
        real_entry = fnum(pos.get("avgOpenPrice"))
        real_qty = fnum(pos.get("qty"))
        real_margin = fnum(pos.get("margin"))
        liq = fnum(pos.get("liqPrice"))
        r_value = abs(real_entry - fnum(plan.stop))

        invalidation = fnum(plan.stop)
        try:
            if (
                str(plan.primary_side).upper() == side_name
                and plan.primary_invalidation is not None
            ):
                invalidation = fnum(plan.primary_invalidation, fnum(plan.stop))
        except Exception:
            pass

        ps = LivePositionState(
            position_id=position_id,
            client_id=client_id,
            side=side_name,
            entry=real_entry,
            qty_initial=real_qty,
            stop_initial=fnum(plan.stop),
            r_value=r_value,
            tp1=fnum(plan.tp1),
            tp2=fnum(plan.tp2),
            tp3=fnum(plan.tp3),
            leverage=selected_leverage,
            thesis_invalidation=invalidation,
            current_stop=fnum(plan.stop),
            peak_price=real_entry,
            opened_at=time.time(),
        )

        self.state.position = ps
        self.state.trades_today += 1
        self.state.save()

        try:
            self.ensure_stop(position_id, fnum(plan.stop))
            real_tp1 = floor_prec(real_qty * LIVE_TP1_PCT, self.base_precision)
            real_tp2 = floor_prec(real_qty * LIVE_TP2_PCT, self.base_precision)
            real_runner = floor_prec(
                real_qty - real_tp1 - real_tp2,
                self.base_precision,
            )
            if min(real_tp1, real_tp2, real_runner) < self.min_qty:
                raise RuntimeError(
                    "Real filled qty too small for 2TP+runner split: "
                    f"tp1={real_tp1}, tp2={real_tp2}, runner={real_runner}"
                )
            self.place_native_tps(ps, real_tp1, real_tp2)
            self.state.save()
        except Exception as e:
            self.emergency_close_and_lock(
                "PROTECTION SETUP FAILED: " + str(e)
            )
            return False

        self.tg.send(
            "✅🟢 <b>POSICIÓN REAL VERIFICADA Y PROTEGIDA</b>\n\n"
            f"{side_name} {SYMBOL}\n"
            f"Position ID: <code>{position_id}</code>\n"
            f"Entrada REAL: <b>{p(real_entry)}</b>\n"
            f"Qty REAL: <b>{fmt_qty(real_qty, self.base_precision)} BTC</b>\n"
            f"Margen API: <b>{real_margin:.3f} USDT</b>\n"
            f"Leverage: <b>{pos.get('leverage')}x</b> (AUTO esperado {selected_leverage}x)\n"
            f"Modo: <b>{pos.get('marginMode')} / {pos.get('positionMode')}</b>\n"
            f"Liquidación: <b>{p(liq) if liq > 0 else '-'}</b>\n"
            f"Invalidación tesis: <b>{p(invalidation)}</b>\n\n"
            f"SL: <b>{p(plan.stop)}</b>\n"
            f"TP1 {LIVE_TP1_PCT*100:.0f}%: <b>{p(plan.tp1)}</b>\n"
            f"TP2 {LIVE_TP2_PCT*100:.0f}%: <b>{p(plan.tp2)}</b>\n"
            f"Runner tras TP2: <b>~{LIVE_RUNNER_PCT*100:.0f}%</b>\n"
            f"TP3 planner: <b>{p(plan.tp3) if plan.tp3 else '-'}</b> (referencia; SIN orden)\n\n"
            "A partir de aquí el bot gestiona SL/TP y vigila cambio de tesis."
        )
        return True

    # -----------------------------
    # Active bot-position management
    # -----------------------------

    def safe_move_stop(self, new_stop: float, mark: float, stage: int):
        ps = self.state.position
        if not ps:
            return False

        if ps.side == "LONG":
            if new_stop <= ps.current_stop:
                return False
            new_stop = min(new_stop, mark * (1 - LIVE_STOP_MARK_BUFFER_PCT))
            if new_stop <= ps.current_stop:
                return False
        else:
            if new_stop >= ps.current_stop:
                return False
            new_stop = max(new_stop, mark * (1 + LIVE_STOP_MARK_BUFFER_PCT))
            if new_stop >= ps.current_stop:
                return False

        try:
            verified_stop = self.ensure_stop(ps.position_id, new_stop)
        except Exception as e:
            # Keep the current position and its existing exchange SL, but stop
            # allowing new entries until the discrepancy is reviewed.
            self.state.auto_enabled = False
            self.state.locked = True
            self.state.lock_reason = "STOP MOVE NOT CONFIRMED: " + str(e)
            self.state.save()
            self.tg.send(
                "🚨🛡 <b>CAMBIO DE SL NO CONFIRMADO</b>\n\n"
                f"{ps.side} {SYMBOL}\n"
                f"SL solicitado: <b>{p(new_stop)}</b>\n"
                f"{C.html.escape(str(e))}\n\n"
                "NO actualizo el SL interno. Nuevas entradas quedan bloqueadas. "
                "La posición actual conserva la protección que siga visible en Bitunix."
            )
            return False

        ps.current_stop = verified_stop
        ps.stop_stage = max(ps.stop_stage, stage)
        self.state.save()

        self.tg.send(
            "🔒 <b>SL REAL MODIFICADO Y VERIFICADO</b>\n\n"
            f"{ps.side} {SYMBOL}\n"
            f"Nuevo SL exchange: <b>{p(verified_stop)}</b>\n"
            f"Etapa: <b>{ps.stop_stage}</b>"
        )
        return True

    def trade_fill_metrics(self, position_id: str, funding: float = 0.0):
        """
        Canonical PnL source for I-GOD.

        We deliberately calculate from actual trade fills because the live
        Bitunix position-history realizedPNL observed in production can differ
        from the semantics documented for that field. Fill rows expose PnL and
        fee separately and match the account transaction ledger.
        """
        rows = self.api.history_trades(position_id=position_id, limit=100)
        if not rows:
            raise RuntimeError(
                f"No trade fills returned for position {position_id}"
            )

        gross = 0.0
        fee = 0.0
        for row in rows:
            if not isinstance(row, dict):
                continue
            gross += fnum(row.get("realizedPNL"))
            fee += abs(fnum(row.get("fee")))

        net = gross - fee + float(funding)
        return {
            "gross": gross,
            "fee": fee,
            "funding": float(funding),
            "net": net,
            "fills": len(rows),
        }

    def close_metrics(self, ps: LivePositionState):
        hist = None
        for _ in range(5):
            try:
                hist = self.api.history_position(ps.position_id)
                if hist:
                    break
            except Exception:
                pass
            time.sleep(1)

        funding = fnum(hist.get("funding")) if hist else 0.0

        # Fill-level accounting is the source of truth for gross/fees/net.
        m = self.trade_fill_metrics(ps.position_id, funding=funding)
        return hist, m["gross"], m["fee"], m["funding"], m["net"]

    def finalize_closed_position(self, ps: LivePositionState, reason: str):
        hist, realized, fee, funding, net = self.close_metrics(ps)

        self.state.day_pnl += net
        self.state.day_peak_pnl = max(
            self.state.day_peak_pnl,
            self.state.day_pnl,
        )
        self.state.last_close_time = time.time()
        if ps.position_id not in self.state.bot_closed_position_ids:
            self.state.bot_closed_position_ids.append(ps.position_id)
        self.state.position = None
        self.state.save()

        self.tg.send(
            "🏁 <b>POSICIÓN REAL CERRADA</b>\n\n"
            f"Motivo: <b>{C.html.escape(reason)}</b>\n"
            f"Position ID: <code>{ps.position_id}</code>\n"
            f"PnL bruto realizado: <b>{money(realized)}</b>\n"
            f"Fees: <b>-{abs(fee):.4f} USDT</b>\n"
            f"Funding: <b>{money(funding)}</b>\n"
            f"NETO API: <b>{money(net)}</b>\n"
            f"PnL neto bot hoy: <b>{money(self.state.day_pnl)}</b>"
        )
        return net

    def position_closed_net_now(self, pos: dict) -> float:
        pid = str(pos.get("positionId", ""))
        if not pid:
            raise RuntimeError("Position has no positionId for fill PnL lookup.")
        funding = fnum(pos.get("funding"))
        return self.trade_fill_metrics(pid, funding=funding)["net"]

    def stop_for_target_net(
        self,
        ps: LivePositionState,
        pos: dict,
        target_net_usdt: float,
    ) -> float:
        """Estimate a stop targeting FINAL net PnL using actual fill accounting."""
        qty = fnum(pos.get("qty"))
        if qty <= 0:
            return ps.current_stop

        funding = fnum(pos.get("funding"))
        net_so_far = self.trade_fill_metrics(
            ps.position_id,
            funding=funding,
        )["net"]

        target = float(target_net_usdt)

        # Entry/partial-exit fees already exist inside net_so_far. Only reserve
        # the cost/slippage of closing the REMAINING quantity at the new stop.
        exit_c = max(
            0.0,
            LIVE_TAKER_FEE_RATE + LIVE_STOP_SLIPPAGE_RATE,
        )

        if ps.side == "LONG":
            denom = qty * max(1e-9, 1.0 - exit_c)
            return (
                target - net_so_far + qty * ps.entry
            ) / denom

        denom = qty * (1.0 + exit_c)
        return (
            net_so_far + qty * ps.entry - target
        ) / max(denom, 1e-9)

    def runner_trail_candidate(self, ps: LivePositionState):
        atr15 = 0.0
        ema20 = None
        try:
            row = self.analyzer.frames["15m"].iloc[-1]
            atr15 = fnum(row.get("atr"))
            ema20 = fnum(row.get("ema20"))
        except Exception:
            pass

        distance = LIVE_RUNNER_TRAIL_R * ps.r_value
        if atr15 > 0:
            distance = max(distance, LIVE_RUNNER_TRAIL_ATR * atr15)

        if ps.side == "LONG":
            peak_based = ps.peak_price - distance
            if ema20 and atr15 > 0:
                structural = ema20 - LIVE_RUNNER_STRUCTURE_ATR * atr15
                candidate = min(peak_based, structural)
            else:
                candidate = peak_based
            improvement = candidate - ps.current_stop
        else:
            peak_based = ps.peak_price + distance
            if ema20 and atr15 > 0:
                structural = ema20 + LIVE_RUNNER_STRUCTURE_ATR * atr15
                candidate = max(peak_based, structural)
            else:
                candidate = peak_based
            improvement = ps.current_stop - candidate

        return candidate, improvement, distance, atr15

    def manage_real(self, mark: float):
        ps = self.state.position
        if not ps:
            return

        pos = self.api.position_by_id(ps.position_id)
        if pos is None:
            self.finalize_closed_position(ps, "TP / SL / cierre en exchange")
            return

        qty_now = fnum(pos.get("qty"))
        ratio = qty_now / ps.qty_initial if ps.qty_initial > 0 else 1.0

        if ps.side == "LONG":
            ps.peak_price = max(ps.peak_price, mark)
        else:
            if ps.peak_price <= 0:
                ps.peak_price = ps.entry
            ps.peak_price = min(ps.peak_price, mark)

        after_tp1 = max(0.0, 1.0 - LIVE_TP1_PCT)
        runner_ratio = max(0.0, LIVE_RUNNER_PCT)
        ratio_tol = 0.025

        # TP1: try to protect a small NET profit using actual Bitunix fees/funding.
        if ratio <= after_tp1 + ratio_tol and ps.stop_stage < 1:
            target_net = max(0.0, LIVE_TP1_NET_LOCK_USDT)
            target_stop = self.stop_for_target_net(ps, pos, target_net)
            moved = self.safe_move_stop(target_stop, mark, 1)
            if self.state.locked:
                return
            ps.stop_stage = max(ps.stop_stage, 1)
            self.state.save()
            self.tg.send(
                "💰 <b>TP1 DETECTADO</b>\n"
                f"Qty restante: <b>{fmt_qty(qty_now, self.base_precision)} BTC</b>\n"
                f"Neto cerrado/API ahora: <b>{money(self.position_closed_net_now(pos))}</b>\n"
                f"Objetivo neto si salta SL restante: <b>~{target_net:.2f} USDT</b>\n"
                f"SL bot actual: <b>{p(ps.current_stop)}</b>\n"
                + ("Protección neta aplicada." if moved else
                   "El SL existente ya era igual/mejor o no podía apretarse más.")
            )

        # TP2: do NOT jump to +1R. Protect part of realized profit and let ~40% run.
        if ratio <= runner_ratio + ratio_tol and ps.stop_stage < 2:
            closed_net = self.position_closed_net_now(pos)
            target_net = max(
                LIVE_TP1_NET_LOCK_USDT,
                closed_net * LIVE_TP2_KEEP_REALIZED_PCT,
            )
            floor_stop = self.stop_for_target_net(ps, pos, target_net)
            self.safe_move_stop(floor_stop, mark, 2)
            if self.state.locked:
                return
            ps.stop_stage = max(ps.stop_stage, 2)
            self.state.save()
            self.tg.send(
                "💰💰 <b>TP2 DETECTADO — RUNNER ACTIVADO</b>\n"
                f"Qty runner: <b>{fmt_qty(qty_now, self.base_precision)} BTC</b> "
                f"(~{LIVE_RUNNER_PCT*100:.0f}%)\n"
                f"Neto cerrado/API: <b>{money(closed_net)}</b>\n"
                f"Objetivo de beneficio protegido: <b>~{target_net:.2f} USDT</b>\n"
                f"Trailing: <b>máx({LIVE_RUNNER_TRAIL_R:.2f}R, "
                f"{LIVE_RUNNER_TRAIL_ATR:.2f}×ATR15)</b>, respetando estructura.\n"
                f"TP3 {p(ps.tp3)} queda SOLO como referencia; no hay orden TP3."
            )

        # From TP2 onward, trail the runner. Never loosen the native stop.
        if ps.stop_stage >= 2 and ratio > 0:
            trail, improvement, distance, atr15 = self.runner_trail_candidate(ps)
            step = LIVE_TRAIL_STEP_R * ps.r_value
            if improvement >= step and self.safe_move_stop(trail, mark, 3):
                self.tg.send(
                    "🏃 <b>RUNNER TRAILING ACTUALIZADO</b>\n"
                    f"Peak favorable: <b>{p(ps.peak_price)}</b>\n"
                    f"Distancia trailing: <b>{distance:.1f} USDT</b>\n"
                    f"ATR15: <b>{atr15:.1f}</b>\n"
                    f"Nuevo SL: <b>{p(ps.current_stop)}</b>"
                )

        self.state.save()

    # -----------------------------
    # Thesis invalidation / reversal
    # -----------------------------

    def opposite_action_for(self, side: str) -> str:
        return (
            "ENTER SHORT NOW"
            if side == "LONG"
            else "ENTER LONG NOW"
        )

    def opposite_bias(self, side: str, bias: str) -> bool:
        bias = str(bias).upper()
        if side == "LONG":
            return bias in ("SHORT", "SHORT STRONG")
        return bias in ("LONG", "LONG STRONG")

    def thesis_invalidated(self, ps: LivePositionState, mark: float) -> bool:
        level = ps.thesis_invalidation
        if level <= 0:
            return False
        if ps.side == "LONG":
            return mark < level
        return mark > level

    def close_bot_position_for_thesis(self, reason: str):
        ps = self.state.position
        if not ps:
            return False

        self.tg.send(
            "⚠️🔄 <b>SALIDA ANTICIPADA POR CAMBIO DE TESIS</b>\n\n"
            f"{ps.side} {SYMBOL}\n"
            f"Motivo: <b>{C.html.escape(reason)}</b>\n"
            "Cierro por positionId y verificaré que quede a cero."
        )

        try:
            self.api.flash_close_position(ps.position_id)
        except Exception as e:
            self.emergency_close_and_lock(
                "THESIS EXIT FAILED TO SEND: " + str(e)
            )
            return False

        if not self.wait_position_gone(ps.position_id):
            self.emergency_close_and_lock(
                "THESIS EXIT SENT BUT POSITION STILL VISIBLE"
            )
            return False

        self.finalize_closed_position(ps, reason)
        return True

    def evaluate_thesis_change(self, mark: float):
        if not LIVE_EXIT_ON_THESIS_FLIP:
            return

        ps = self.state.position
        plan = self.plan
        if not ps or plan is None:
            self.flip_count = 0
            self.flip_key = ""
            return

        invalid = self.thesis_invalidated(ps, mark)
        opposite_action = str(plan.action) == self.opposite_action_for(ps.side)
        opp_bias = self.opposite_bias(ps.side, plan.bias)

        # Strongest case: opposite ENTER NOW is already a confirmed entry signal
        # AND the entry-time thesis invalidation level has been crossed.
        immediate_reverse = invalid and opposite_action

        key = f"{ps.side}|{plan.bias}|{invalid}"
        if invalid and opp_bias:
            if key == self.flip_key:
                self.flip_count += 1
            else:
                self.flip_key = key
                self.flip_count = 1
        else:
            self.flip_key = ""
            self.flip_count = 0

        confirmed_exit = self.flip_count >= max(1, LIVE_EXIT_CONFIRM_CYCLES)

        if not immediate_reverse and not confirmed_exit:
            return

        old_side = ps.side
        reason = (
            f"opposite ENTER confirmed + invalidation crossed "
            f"({ps.thesis_invalidation:.1f})"
            if immediate_reverse else
            f"thesis invalidated for {self.flip_count} analyses; "
            f"bias={plan.bias}"
        )

        if not self.close_bot_position_for_thesis(reason):
            return

        self.flip_count = 0
        self.flip_key = ""

        # Only reverse when the planner is currently giving the exact
        # opposite ENTER NOW. A mere bias flip is exit-only.
        if (
            LIVE_REVERSE_ON_CONFIRMED
            and str(plan.action) == self.opposite_action_for(old_side)
        ):
            # New opposite signal is a new signal cycle; allow its own one-shot.
            self.state.entry_armed = True
            self.state.save()

            self.tg.send(
                "🔄 <b>REVERSAL CONFIRMADO</b>\n\n"
                f"El {old_side} está cerrado.\n"
                f"Nueva señal: <b>{C.html.escape(str(plan.action))}</b>\n"
                "Verifico límites/riesgo/costes antes de abrir el lado contrario."
            )
            self.open_real(
                plan,
                bypass_cooldown=True,
                reversal=True,
            )
        else:
            self.tg.send(
                "🟡 <b>POSICIÓN CERRADA; NO HAY REVERSAL EJECUTABLE</b>\n"
                "Me quedo fuera hasta un nuevo ENTER NOW válido."
            )

    # -----------------------------
    # Real status / account
    # -----------------------------

    def get_mark(self) -> float:
        """
        Return Bitunix MARK_PRICE for stop/trailing risk management.

        Planner entries and TP levels use LAST_PRICE. Native SL orders use
        MARK_PRICE, so active-position stop management must compare against
        MARK_PRICE as well.
        """
        snap = self.live.snapshot()
        mark = fnum(snap.get("mark_price"))

        # REST fallback is explicit and authoritative for markPrice.
        if mark <= 0:
            try:
                tick = self.pub.ticker()
                mark = fnum(tick.get("markPrice"))
            except Exception as e:
                log(f"MARK_PRICE REST fallback failed: {e}")

        # Last-resort continuity fallback only. This should be rare.
        if mark <= 0 and self.plan is not None:
            log("MARK_PRICE unavailable; temporarily falling back to plan LAST_PRICE.")
            mark = fnum(self.plan.price)

        return mark

    def account_snapshot(self):
        a = self.api.account(MARGIN_COIN)
        available = fnum(a.get("available"))
        frozen = fnum(a.get("frozen"))
        margin = fnum(a.get("margin"))
        transfer = fnum(a.get("transfer"))
        cross_u = fnum(a.get("crossUnrealizedPNL"))
        iso_u = fnum(a.get("isolationUnrealizedPNL"))
        upnl = cross_u + iso_u
        bonus = fnum(a.get("bonus"))

        # Derived estimate from fields exposed by the account endpoint.
        wallet_est = available + frozen + margin
        equity_est = wallet_est + upnl

        return {
            "raw": a,
            "available": available,
            "frozen": frozen,
            "margin": margin,
            "transfer": transfer,
            "upnl": upnl,
            "bonus": bonus,
            "wallet_est": wallet_est,
            "equity_est": equity_est,
            "positionMode": str(a.get("positionMode", "-")),
        }

    def closed_today_metrics(self):
        now = C.datetime.now(C.TZ)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start.timestamp() * 1000)

        gross = fee = funding = 0.0
        n = 0

        try:
            for x in self.api.history_positions(limit=100):
                mtime = int(fnum(x.get("mtime"), 0))
                if mtime < start_ms:
                    continue

                pid = str(x.get("positionId", ""))
                if not pid:
                    continue

                fm = self.trade_fill_metrics(
                    pid,
                    funding=fnum(x.get("funding")),
                )
                n += 1
                gross += fm["gross"]
                fee += fm["fee"]
                funding += fm["funding"]
        except Exception as e:
            log(f"Could not build fill-based day metrics: {e}")

        return {
            "count": n,
            "realized": gross,
            "fee": fee,
            "funding": funding,
            "net": gross - fee + funding,
        }

    def tpsl_summary_lines(self, position_id: str, side: str):
        try:
            rows = self.api.pending_tpsl(position_id)
        except Exception as e:
            return [f"TP/SL API: error {C.html.escape(str(e))}"]

        tps = []
        sls = []
        for x in rows:
            tp = fnum(x.get("tpPrice"))
            sl = fnum(x.get("slPrice"))
            if tp > 0:
                tps.append((tp, fnum(x.get("tpQty"))))
            if sl > 0:
                sls.append((sl, fnum(x.get("slQty"))))

        reverse = str(side).upper() == "SHORT"
        tps.sort(key=lambda z: z[0], reverse=reverse)

        lines = []
        if sls:
            # Position SL usually has no qty; show every unique level.
            uniq = []
            for sl, qty in sls:
                if all(abs(sl - u[0]) > 1e-9 for u in uniq):
                    uniq.append((sl, qty))
            for i, (sl, qty) in enumerate(uniq[:3], 1):
                q = f" — {fmt_qty(qty, self.base_precision)} BTC" if qty > 0 else ""
                lines.append(f"SL{i if len(uniq)>1 else ''}: <b>{p(sl)}</b>{q}")
        else:
            lines.append("SL visible por API: <b>NO ENCONTRADO ⚠️</b>")

        for i, (tp, qty) in enumerate(tps[:5], 1):
            q = f" — {fmt_qty(qty, self.base_precision)} BTC" if qty > 0 else ""
            lines.append(f"TP{i}: <b>{p(tp)}</b>{q}")

        if not tps:
            lines.append("TP visibles por API: <b>NINGUNO</b>")

        return lines

    def position_message(self):
        rows = self.api.positions(SYMBOL)
        if not rows:
            return (
                "📈 <b>POSICIÓN REAL BITUNIX</b>\n\n"
                "BTCUSDT: <b>NINGUNA</b>\n"
                f"Posición registrada por bot: "
                f"<b>{'SÍ ⚠️' if self.state.position else 'NO ✅'}</b>"
            )

        pos = rows[0]
        pid = str(pos.get("positionId", ""))
        side = str(pos.get("side", "-")).upper()
        qty = fnum(pos.get("qty"))
        entry = fnum(pos.get("avgOpenPrice"))
        liq = fnum(pos.get("liqPrice"))
        margin = fnum(pos.get("margin"))
        upnl = fnum(pos.get("unrealizedPNL"))
        funding = fnum(pos.get("funding"))
        try:
            fm = self.trade_fill_metrics(pid, funding=funding)
            realized = fm["gross"]
            fee = fm["fee"]
            closed_net = fm["net"]
        except Exception:
            # Display fallback only. Trading protection does not rely on this
            # fallback because TP management uses fill-level accounting.
            realized = fnum(pos.get("realizedPNL"))
            fee = abs(fnum(pos.get("fee")))
            closed_net = realized
        net_now = closed_net + upnl
        mark = self.get_mark()

        owned = (
            self.state.position is not None
            and self.state.position.position_id == pid
        )
        origin = "BOT ✅" if owned else "MANUAL / EXTERNA ⚠️"
        management = "AUTOMÁTICA ✅" if owned else "NO ADOPTADA / NO TOCARÉ ⚠️"

        lines = [
            "📈 <b>POSICIÓN REAL BITUNIX</b>",
            "",
            f"{side_icon(side)} <b>{side} {SYMBOL}</b>",
            f"Origen: <b>{origin}</b>",
            f"Gestión I-GOD: <b>{management}</b>",
            f"Position ID: <code>{pid}</code>",
            "",
            f"Entrada: <b>{p(entry)}</b>",
            f"Mark/último: <b>{p(mark) if mark else '-'}</b>",
            f"Qty: <b>{fmt_qty(qty, self.base_precision)} BTC</b>",
            f"Nominal aprox.: <b>{qty*mark:,.2f} USDT</b>" if mark else "",
            f"Leverage: <b>{pos.get('leverage')}x</b>",
            f"Modo: <b>{pos.get('marginMode')} / {pos.get('positionMode')}</b>",
            f"Margen API: <b>{margin:.4f} USDT</b>",
            f"Liquidación: <b>{p(liq) if liq > 0 else '-'}</b>",
            "",
            f"PnL no realizado: <b>{money(upnl)}</b>",
            f"PnL realizado parcial: <b>{money(realized)}</b>",
            f"Fees acumuladas posición: <b>-{abs(fee):.4f} USDT</b>",
            f"Funding acumulado: <b>{money(funding)}</b>",
            f"Neto aprox. posición ahora: <b>{money(net_now)}</b>",
            "",
            "<b>🛡 PROTECCIONES EN EXCHANGE</b>",
        ]
        lines += self.tpsl_summary_lines(pid, side)

        if owned and self.state.position:
            ps = self.state.position
            lines += [
                "",
                "<b>🤖 GESTIÓN BOT</b>",
                f"SL interno actual: <b>{p(ps.current_stop)}</b>",
                f"Etapa SL: <b>{ps.stop_stage}</b>",
                f"Invalidación de tesis guardada: "
                f"<b>{p(ps.thesis_invalidation) if ps.thesis_invalidation else '-'}</b>",
                f"Runner trailing: <b>{LIVE_RUNNER_TRAIL_R:.2f}R / {LIVE_RUNNER_TRAIL_ATR:.2f}×ATR15</b> "
                "(desde TP2)",
            ]

        return "\n".join(x for x in lines if x != "")[:4090]

    def account_message(self):
        a = self.account_snapshot()
        d = self.closed_today_metrics()
        self.reconcile_bot_day_pnl_from_fills()

        return (
            "💰 <b>CUENTA FUTURES BITUNIX — EN VIVO</b>\n\n"
            f"Disponible: <b>{a['available']:,.4f} USDT</b>\n"
            f"Margen usado/API: <b>{a['margin']:,.4f} USDT</b>\n"
            f"Frozen: <b>{a['frozen']:,.4f} USDT</b>\n"
            f"PnL no realizado cuenta: <b>{money(a['upnl'])}</b>\n"
            f"Wallet estimada API: <b>{a['wallet_est']:,.4f} USDT</b>\n"
            f"Equity estimada API: <b>{a['equity_est']:,.4f} USDT</b>\n"
            f"Transferible API: <b>{a['transfer']:,.4f} USDT</b>\n"
            f"Bonus: <b>{a['bonus']:,.4f} USDT</b>\n"
            f"Position mode cuenta: <b>{C.html.escape(a['positionMode'])}</b>\n\n"
            "<b>📅 CIERRES DE HOY (API)</b>\n"
            f"Posiciones cerradas: <b>{d['count']}</b>\n"
            f"Realized bruto: <b>{money(d['realized'])}</b>\n"
            f"Fees: <b>-{abs(d['fee']):.4f} USDT</b>\n"
            f"Funding: <b>{money(d['funding'])}</b>\n"
            f"Neto cierres hoy: <b>{money(d['net'])}</b>\n\n"
            f"PnL NETO registrado por I-GOD hoy: "
            f"<b>{money(self.state.day_pnl)}</b>\n\n"
            "<i>Wallet/equity son estimaciones derivadas de los campos "
            "que devuelve la API; PnL/fees/funding de posiciones se leen "
            "directamente de Bitunix.</i>"
        )[:4090]

    def status(self):
        current_action = self.plan.action if self.plan is not None else "-"
        current_setup = self.plan.setup if self.plan is not None else "-"
        current_bias = self.plan.bias if self.plan is not None else "-"

        try:
            a = self.account_snapshot()
            rows = self.api.positions(SYMBOL)
            ex = rows[0] if rows else None
            ex_pid = str(ex.get("positionId", "")) if ex else ""
            bot_owned = (
                ex is not None
                and self.state.position is not None
                and self.state.position.position_id == ex_pid
            )
            ex_text = (
                f"{ex.get('side')} {ex.get('qty')} BTC "
                f"({'BOT' if bot_owned else 'MANUAL/EXTERNA'})"
                if ex else
                "NINGUNA"
            )
            acct_lines = (
                f"Equity est.: <b>{a['equity_est']:,.4f} USDT</b>\n"
                f"Disponible: <b>{a['available']:,.4f} USDT</b>\n"
                f"Margen API: <b>{a['margin']:,.4f} USDT</b>\n"
                f"uPnL cuenta: <b>{money(a['upnl'])}</b>\n"
            )
        except Exception as e:
            ex_text = "ERROR API"
            acct_lines = (
                f"Cuenta API: <b>ERROR {C.html.escape(str(e))}</b>\n"
            )

        ps = self.state.position
        bot_pos = "NINGUNA"
        if ps:
            bot_pos = (
                f"{ps.side} @ {p(ps.entry)} | "
                f"SL {p(ps.current_stop)} | stage {ps.stop_stage}"
            )

        lock_reason = (
            f"\nMotivo lock: <b>{C.html.escape(self.state.lock_reason)}</b>"
            if self.state.locked and self.state.lock_reason else ""
        )

        return (
            "📊 <b>I-GOD V7.3.4 — STATUS REAL</b>\n\n"
            "<b>💰 BITUNIX</b>\n"
            + acct_lines
            + f"Posición exchange: <b>{C.html.escape(ex_text)}</b>\n\n"
            "<b>🤖 BOT</b>\n"
            f"LIVE_EXECUTION: <b>{LIVE_EXECUTION}</b>\n"
            f"Auto entradas: <b>{self.state.auto_enabled}</b>\n"
            f"Entry armed: <b>{self.state.entry_armed}</b>\n"
            f"Bloqueado: <b>{self.state.locked}</b>"
            + lock_reason + "\n"
            f"Posición bot: <b>{C.html.escape(bot_pos)}</b>\n"
            f"Trades bot hoy: <b>{self.state.trades_today}/"
            f"{LIVE_MAX_TRADES_DAY + (LIVE_PROFIT_LOCK_EXTRA_TRADES if self.profit_lock_active() else 0)}</b>\n"
            f"PnL neto bot hoy: <b>{money(self.state.day_pnl)}</b>\n"
            f"Cierres I-GOD identificados hoy: <b>{len(self.state.bot_closed_position_ids)}</b>\n"
            f"Sizing mode: <b>{LIVE_SIZING_MODE}</b>\n"
            f"Equity allocation: <b>{LIVE_EQUITY_ALLOC_PCT*100:.0f}%</b>\n"
            f"Risk/trade: <b>{LIVE_RISK_PCT*100:.1f}% equity</b>\n"
            f"Leverage: <b>{'AUTO ' + str(LIVE_MIN_LEVERAGE) + '–' + str(min(LIVE_MAX_LEVERAGE, self.max_leverage)) + 'x' if LIVE_DYNAMIC_LEVERAGE else str(LIVE_LEVERAGE) + 'x fijo'}</b>\n"
            f"PnL cuenta hoy usado por Profit Lock: <b>{money(self.profit_lock_day_pnl())}</b>\n"
            f"Objetivo diario soft: <b>{money(self.daily_profit_target_usdt())}</b>\n"
            f"Profit lock: <b>{self.profit_lock_active()}</b>\n"
            f"Suelo protegido: <b>{money(self.profit_lock_floor())}</b>\n\n"
            "<b>🧠 MERCADO</b>\n"
            f"Sesgo: <b>{C.html.escape(str(current_bias))}</b>\n"
            f"Acción: <b>{C.html.escape(str(current_action))}</b>\n"
            f"Setup: <b>{C.html.escape(str(current_setup))}</b>\n"
            f"Señales consumidas: <b>{len(self.state.consumed)}</b>"
        )[:4090]

    def readiness_message(self):
        problems = []
        details = []

        try:
            a = self.api.account(MARGIN_COIN)
            details.append("✅ API privada / cuenta")
            account_mode = str(a.get("positionMode", "")).upper()
            if account_mode == "ONE_WAY":
                details.append("✅ Position mode ONE_WAY")
            else:
                problems.append(
                    f"Position mode cuenta = {account_mode or 'UNKNOWN'}; "
                    f"debe ser ONE_WAY"
                )
        except Exception as e:
            problems.append(f"API privada: {e}")

        try:
            positions = self.api.positions(SYMBOL)
            if positions:
                problems.append(
                    "hay una posición BTCUSDT real abierta"
                )
            else:
                details.append("✅ Sin posición BTCUSDT")
        except Exception as e:
            problems.append(f"consulta posiciones: {e}")

        try:
            pending = self.api.pending_orders()
            if pending:
                problems.append(
                    f"hay {len(pending)} orden(es) normal(es) pendientes"
                )
            else:
                details.append("✅ Sin órdenes normales pendientes")
        except Exception as e:
            problems.append(f"consulta órdenes: {e}")

        try:
            pending_tpsl = self.api.pending_tpsl()
            if pending_tpsl:
                problems.append(
                    f"hay {len(pending_tpsl)} TP/SL pendiente(s) en BTCUSDT"
                )
            else:
                details.append("✅ Sin TP/SL huérfanos pendientes")
        except Exception as e:
            problems.append(f"consulta TP/SL: {e}")

        if not LIVE_EXECUTION:
            problems.append("LIVE_EXECUTION=false")
        else:
            details.append("✅ LIVE_EXECUTION=true")

        if not self.state.auto_enabled:
            problems.append("AUTO desactivado")
        else:
            details.append("✅ AUTO activado")

        if self.state.locked:
            problems.append(f"LOCK: {self.state.lock_reason}")
        else:
            details.append("✅ Sin lock")

        if not self.state.entry_armed:
            problems.append("entry_armed=false (ciclo ENTER ya consumido)")
        else:
            details.append("✅ Entry armed")

        max_trades_now = LIVE_MAX_TRADES_DAY + (
            LIVE_PROFIT_LOCK_EXTRA_TRADES if self.profit_lock_active() else 0
        )
        if self.state.trades_today >= max_trades_now:
            problems.append(f"límite diario de trades alcanzado ({max_trades_now})")
        else:
            details.append(
                f"✅ Trades hoy {self.state.trades_today}/{max_trades_now}"
            )

        if self.state.day_pnl <= -abs(LIVE_MAX_DAILY_LOSS_USDT):
            problems.append("límite diario de pérdida alcanzado")
        else:
            details.append(
                f"✅ PnL bot hoy {self.state.day_pnl:+.4f} USDT"
            )

        target = self.daily_profit_target_usdt()
        lock_pnl = self.profit_lock_day_pnl()
        if self.profit_lock_active():
            floor = self.profit_lock_floor()
            if lock_pnl <= floor:
                problems.append(
                    f"profit-lock floor alcanzado ({floor:.2f} USDT)"
                )
            else:
                details.append(
                    f"🏆 Profit Lock: día {lock_pnl:+.2f}, target {target:.2f}, floor {floor:.2f}"
                )
        elif target > 0:
            details.append(
                f"✅ Profit Lock aún no activo: día {lock_pnl:+.2f} / target {target:.2f}"
            )

        try:
            preview_mult = (
                LIVE_PROFIT_LOCK_RISK_MULT
                if self.profit_lock_active()
                else 1.0
            )
            preview = self.sizing_budget(preview_mult)
            if preview["mode"] == "EQUITY":
                details.append(
                    f"✅ Sizing EQUITY: equity {preview['equity']:.2f} -> "
                    f"base {preview['base_margin']:.2f} USDT -> "
                    f"risk cap {preview['risk_cap']:.2f} USDT"
                )
                if LIVE_DYNAMIC_LEVERAGE:
                    details.append(
                        f"✅ Leverage AUTO {LIVE_MIN_LEVERAGE}–"
                        f"{min(LIVE_MAX_LEVERAGE, self.max_leverage)}x "
                        f"(pair max {self.max_leverage}x)"
                    )
                else:
                    details.append(f"✅ Leverage fijo {LIVE_LEVERAGE}x")
            else:
                details.append(
                    f"✅ Sizing FIXED: base {preview['base_margin']:.2f} -> "
                    f"risk cap {preview['risk_cap']:.2f} USDT"
                )
        except Exception as e:
            problems.append(f"sizing dinámico: {e}")

        plan_text = (
            f"{self.plan.bias} | {self.plan.action} | {self.plan.setup}"
            if self.plan is not None else
            "todavía sin análisis"
        )

        if problems:
            return (
                "🧪 <b>PRE-FLIGHT CHECK — NO READY</b>\n\n"
                + "\n".join(details)
                + "\n\n<b>Bloqueos:</b>\n"
                + "\n".join(
                    f"❌ {C.html.escape(x)}" for x in problems
                )
                + f"\n\nPlan actual: <b>{C.html.escape(plan_text)}</b>"
            )[:4090]

        return (
            "🧪✅ <b>PRE-FLIGHT CHECK — READY</b>\n\n"
            + "\n".join(details)
            + "\n\n"
            "El bot está preparado para que el próximo ENTER NOW válido "
            "pase por sizing + riesgo + fees/slippage y, si todo cumple, "
            "envíe una orden REAL.\n\n"
            f"Plan actual: <b>{C.html.escape(plan_text)}</b>"
        )[:4090]

    # -----------------------------
    # Telegram commands
    # -----------------------------

    def try_unlock(self):
        if self.api.positions(SYMBOL):
            return (
                "⛔ No desbloqueo: todavía existe una posición BTCUSDT real."
            )
        if self.api.pending_orders():
            return (
                "⛔ No desbloqueo: todavía existen órdenes normales pendientes."
            )

        self.state.locked = False
        self.state.lock_reason = ""
        self.state.auto_enabled = False
        self.state.entry_armed = True
        self.state.save()

        return (
            "🔓 <b>LOCK QUITADO</b>\n"
            "AUTO queda OFF por seguridad. Revisa /check y después usa /live_on."
        )

    def commands(self):
        for cmd in self.tg.poll_commands():
            if cmd in ("/status", "/live"):
                self.tg.send(self.status())

            elif cmd == "/account":
                try:
                    self.tg.send(self.account_message())
                except Exception as e:
                    self.tg.send(
                        "❌ Error leyendo cuenta Bitunix:\n"
                        + C.html.escape(str(e))
                    )

            elif cmd == "/position":
                try:
                    self.tg.send(self.position_message())
                except Exception as e:
                    self.tg.send(
                        "❌ Error leyendo posición Bitunix:\n"
                        + C.html.escape(str(e))
                    )

            elif cmd == "/check":
                try:
                    self.tg.send(self.readiness_message())
                except Exception as e:
                    self.tg.send(
                        "❌ Pre-flight falló:\n"
                        + C.html.escape(str(e))
                    )

            elif cmd == "/live_off":
                self.state.auto_enabled = False
                self.state.save()
                self.tg.send(
                    "🔕 <b>NUEVAS ENTRADAS LIVE DESACTIVADAS</b>\n"
                    "Una posición DEL BOT ya abierta seguirá gestionándose."
                )

            elif cmd == "/live_on":
                if not LIVE_EXECUTION:
                    self.tg.send(
                        "⛔ LIVE_EXECUTION=false en Railway."
                    )
                elif self.state.locked:
                    self.tg.send(
                        "⛔ Bot BLOQUEADO:\n"
                        + C.html.escape(self.state.lock_reason)
                    )
                elif self.account_position_mode() != "ONE_WAY":
                    self.tg.send(
                        "⛔ Position mode de Bitunix no es ONE_WAY. "
                        "Cámbialo antes de activar dinero real."
                    )
                elif self.api.positions(SYMBOL) and self.state.position is None:
                    self.tg.send(
                        "⛔ Hay una posición BTCUSDT manual/externa. "
                        "No activo nuevas entradas."
                    )
                else:
                    self.state.auto_enabled = True
                    self.state.save()
                    self.tg.send(
                        "🔴 <b>NUEVAS ENTRADAS LIVE ACTIVADAS</b>\n"
                        "El próximo ENTER NOW válido puede enviar una orden REAL."
                    )

            elif cmd == "/unlock":
                try:
                    self.tg.send(self.try_unlock())
                except Exception as e:
                    self.tg.send(
                        "❌ No pude comprobar si es seguro desbloquear:\n"
                        + C.html.escape(str(e))
                    )

            elif cmd == "/plan" and self.plan is not None:
                self.tg.send(
                    C.plan_message(self.plan, "📍 PLAN LIVE ACTUAL")
                )

            elif cmd == "/help":
                self.tg.send(
                    "<b>I-GOD V7.3.4 comandos</b>\n"
                    "/status — cuenta + bot + mercado\n"
                    "/account — cuenta Futures real\n"
                    "/position — posición/SL/TP reales\n"
                    "/check — pre-flight READY/NO READY\n"
                    "/plan — plan de mercado\n"
                    "/live_on — permitir nuevas entradas\n"
                    "/live_off — bloquear nuevas entradas\n"
                    "/unlock — quitar lock solo si no hay posición/órdenes\n"
                    "/help — ayuda"
                )

    # -----------------------------
    # Main loop
    # -----------------------------

    def run(self):
        self.live.start()

        self.tg.send(
            "🔴🤖 <b>I-GOD V7.3.4 REAL AUTO conectado</b>\n\n"
            f"{SYMBOL} | sizing {LIVE_SIZING_MODE} "
            f"{LIVE_EQUITY_ALLOC_PCT*100:.0f}% equity "
            f"| risk {LIVE_RISK_PCT*100:.1f}% "
            f"| leverage {'AUTO ' + str(LIVE_MIN_LEVERAGE) + '–' + str(min(LIVE_MAX_LEVERAGE, self.max_leverage)) + 'x' if LIVE_DYNAMIC_LEVERAGE else str(LIVE_LEVERAGE) + 'x fijo'}\n"
            f"LIVE_EXECUTION: <b>{LIVE_EXECUTION}</b>\n"
            f"AUTO: <b>{self.state.auto_enabled}</b>\n"
            f"State persistente: <b>{bool(volume)}</b>\n"
            f"Fee guard mínimo: <b>{LIVE_MIN_NET_RR:.2f}R neto</b>\n"
            f"Reserva cash ejecución: <b>{LIVE_EXECUTION_CASH_RESERVE_PCT*100:.1f}% + costes estimados</b>\n"
            f"Reserva slippage STOP: <b>{LIVE_STOP_SLIPPAGE_RATE*100:.2f}%</b>\n"
            f"Daily target soft: <b>{LIVE_DAILY_PROFIT_TARGET_PCT*100:.1f}%</b>\n"
            f"Profit-lock risk: <b>{LIVE_PROFIT_LOCK_RISK_MULT:.2f}x</b>\n"
            f"Salidas: <b>{LIVE_TP1_PCT*100:.0f}% TP1 + {LIVE_TP2_PCT*100:.0f}% TP2 + {LIVE_RUNNER_PCT*100:.0f}% runner</b>\n"
            f"Runner desde TP2: <b>{LIVE_RUNNER_TRAIL_R:.2f}R / {LIVE_RUNNER_TRAIL_ATR:.2f}×ATR15</b>\n"
            f"Exit thesis flip: <b>{LIVE_EXIT_ON_THESIS_FLIP}</b>\n"
            f"Reverse confirmed: <b>{LIVE_REVERSE_ON_CONFIRMED}</b>\n\n"
            "ONE SHOT activo. Posiciones manuales NO se adoptan.\n"
            "Usa /check para comprobar si está READY."
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

                    mark = fnum(self.plan.price)

                    # Existing BOT position: first evaluate whether the thesis
                    # changed enough to close/reverse.
                    if self.state.position is not None:
                        self.evaluate_thesis_change(mark)

                    is_enter = self.plan.action in (
                        "ENTER LONG NOW",
                        "ENTER SHORT NOW",
                    )

                    # Re-arm only after leaving ENTER when flat.
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

                mark = self.get_mark()
                if mark > 0 and self.state.position is not None:
                    self.manage_real(mark)

                C.STOP_EVENT.wait(MANAGE_SECONDS)

            except KeyboardInterrupt:
                break
            except Exception as e:
                log(f"Loop error: {type(e).__name__}: {e}")
                time.sleep(8)


if __name__ == "__main__":
    RealAuto().run()
