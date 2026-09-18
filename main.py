#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BTCUSDT COPILOT V2 + TELEGRAM — Bitunix public data only.

IMPORTANT
---------
- Does NOT place orders.
- Does NOT use Bitunix API keys.
- Does NOT access your Bitunix account.
- Analyses BTCUSDT Futures public data.
- Uses higher-timeframe CLOSED candles for directional bias.
- Sends Telegram alerts only when a setup becomes actionable.
"""

from __future__ import annotations

import html
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import websocket


REST_BASE = "https://fapi.bitunix.com"
WS_PUBLIC = "wss://fapi.bitunix.com/public/"

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()
TZ_NAME = os.getenv("TIMEZONE", "Europe/Madrid")
TZ = ZoneInfo(TZ_NAME)

ANALYSIS_SECONDS = int(os.getenv("ANALYSIS_SECONDS", "60"))
LIVE_SECONDS = int(os.getenv("LIVE_SECONDS", "15"))
DAILY_PLAN_HOUR = int(os.getenv("DAILY_PLAN_HOUR", "8"))
MIN_RR_ENTER = float(os.getenv("MIN_RR_ENTER", "1.8"))
MIN_RR_LATE = float(os.getenv("MIN_RR_LATE", "1.2"))
MAX_EXTENSION_ATR = float(os.getenv("MAX_EXTENSION_ATR", "1.35"))
ALERT_COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "45"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

INTERVAL_MS = {
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
}

STOP_EVENT = threading.Event()


def log(msg: str) -> None:
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def num(v, default=np.nan) -> float:
    try:
        return float(v)
    except Exception:
        return default


def finite(v) -> bool:
    try:
        return bool(np.isfinite(float(v)))
    except Exception:
        return False


def price_fmt(v: Optional[float]) -> str:
    if v is None or not finite(v):
        return "-"
    return f"{float(v):,.1f}"


def pct_fmt(v: Optional[float]) -> str:
    if v is None or not finite(v):
        return "-"
    return f"{float(v)*100:+.4f}%"


# ---------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------

class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.offset = None
        self.base = f"https://api.telegram.org/bot{token}" if token else ""

    def ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def api(self, method: str, *, params=None, data=None, timeout=15):
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN no configurado")
        r = requests.post(
            f"{self.base}/{method}",
            params=params,
            data=data,
            timeout=timeout,
        )
        r.raise_for_status()
        payload = r.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram error: {payload}")
        return payload.get("result")

    def send(self, text: str, disable_notification=False) -> bool:
        if not self.ready():
            return False
        try:
            self.api(
                "sendMessage",
                data={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                    "disable_notification": "true" if disable_notification else "false",
                },
            )
            return True
        except Exception as e:
            log(f"Telegram send error: {e}")
            return False

    def poll_commands(self) -> List[str]:
        """Poll only this user's bot commands; never blocks the trading loop."""
        if not self.token:
            return []
        try:
            params = {"timeout": 0, "limit": 20}
            if self.offset is not None:
                params["offset"] = self.offset
            updates = self.api("getUpdates", params=params, timeout=10) or []
            commands = []
            for u in updates:
                uid = int(u.get("update_id", 0))
                self.offset = max(self.offset or 0, uid + 1)
                msg = u.get("message") or {}
                chat = msg.get("chat") or {}
                if self.chat_id and str(chat.get("id")) != str(self.chat_id):
                    continue
                txt = str(msg.get("text", "")).strip()
                if txt.startswith("/"):
                    commands.append(txt.split()[0].lower())
            return commands
        except Exception as e:
            log(f"Telegram getUpdates error: {e}")
            return []


# ---------------------------------------------------------------------
# Bitunix public REST
# ---------------------------------------------------------------------

class BitunixPublic:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "BTC-Copilot-Telegram/2.0"})
        self.last_req = 0.0

    def _throttle(self):
        # Public market endpoints are documented around 10 req/sec/IP.
        delta = time.time() - self.last_req
        if delta < 0.12:
            time.sleep(0.12 - delta)
        self.last_req = time.time()

    def get(self, path: str, params=None):
        self._throttle()
        r = self.s.get(REST_BASE + path, params=params, timeout=12)
        r.raise_for_status()
        p = r.json()
        if p.get("code") != 0:
            raise RuntimeError(f"Bitunix: {p}")
        return p.get("data")

    def ticker(self):
        d = self.get("/api/v1/futures/market/tickers", {"symbols": SYMBOL})
        return d[0] if d else {}

    def funding(self):
        d = self.get("/api/v1/futures/market/funding_rate", {"symbol": SYMBOL})
        return d[0] if isinstance(d, list) and d else (d or {})

    def depth(self, limit="15"):
        return self.get(
            "/api/v1/futures/market/depth",
            {"symbol": SYMBOL, "limit": str(limit)},
        ) or {}

    def klines(self, interval: str, needed=260) -> pd.DataFrame:
        rows = []
        end = int(time.time() * 1000)

        while len(rows) < needed:
            limit = min(200, needed - len(rows))
            d = self.get(
                "/api/v1/futures/market/kline",
                {
                    "symbol": SYMBOL,
                    "interval": interval,
                    "endTime": end,
                    "limit": limit,
                    "type": "LAST_PRICE",
                },
            ) or []
            if not d:
                break
            rows.extend(d)
            times = [int(x["time"]) for x in d if "time" in x]
            if not times:
                break
            oldest = min(times)
            if oldest >= end:
                break
            end = oldest - 1
            if len(d) < limit:
                break

        if not rows:
            raise RuntimeError(f"Sin datos {interval}")

        df = pd.DataFrame(rows)
        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        for c in ("open", "high", "low", "close", "baseVol", "quoteVol"):
            if c not in df.columns:
                df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = (
            df.dropna(subset=["time", "open", "high", "low", "close"])
            .drop_duplicates("time")
            .sort_values("time")
            .reset_index(drop=True)
        )

        # Only fully CLOSED candles may define trend/setup.
        now = int(time.time() * 1000) - 1500
        df = df[(df["time"] + INTERVAL_MS[interval]) <= now].copy()
        return df.tail(needed).reset_index(drop=True)


# ---------------------------------------------------------------------
# Real-time public WS: price + order book + public trades
# ---------------------------------------------------------------------

class LiveMarket:
    def __init__(self):
        self.lock = threading.Lock()
        self.price = None
        self.index_price = None
        self.funding = None
        self.bids = []
        self.asks = []
        self.buy_vol = 0.0
        self.sell_vol = 0.0
        self.last_trade_reset = time.time()
        self.connected = False
        self.last_message = 0.0
        self.error = ""

    def start(self):
        threading.Thread(target=self._run_forever, daemon=True).start()

    def _run_forever(self):
        while not STOP_EVENT.is_set():
            try:
                ws = websocket.WebSocketApp(
                    WS_PUBLIC,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                ws.run_forever(ping_interval=None)
            except Exception as e:
                self.error = str(e)
            self.connected = False
            if not STOP_EVENT.is_set():
                time.sleep(3)

    def _on_open(self, ws):
        self.connected = True
        self.error = ""
        ws.send(json.dumps({
            "op": "subscribe",
            "args": [
                {"symbol": SYMBOL, "ch": "price"},
                {"symbol": SYMBOL, "ch": "depth_book15"},
                {"symbol": SYMBOL, "ch": "trade"},
            ],
        }))

        def ping_loop():
            while self.connected and not STOP_EVENT.is_set():
                try:
                    ws.send(json.dumps({"op": "ping", "ping": int(time.time())}))
                except Exception:
                    return
                time.sleep(20)

        threading.Thread(target=ping_loop, daemon=True).start()

    def _on_message(self, ws, raw):
        try:
            p = json.loads(raw)
            ch = p.get("ch")
            d = p.get("data")
            with self.lock:
                self.last_message = time.time()

                if ch == "price" and isinstance(d, dict):
                    mp = num(d.get("mp"))
                    ip = num(d.get("ip"))
                    fr = num(d.get("fr"))
                    if finite(mp):
                        self.price = mp
                    if finite(ip):
                        self.index_price = ip
                    if finite(fr):
                        self.funding = fr

                elif ch == "depth_book15" and isinstance(d, dict):
                    self.bids = d.get("b", []) or []
                    self.asks = d.get("a", []) or []

                elif ch == "trade" and isinstance(d, list):
                    now = time.time()
                    if now - self.last_trade_reset >= 60:
                        self.buy_vol = 0.0
                        self.sell_vol = 0.0
                        self.last_trade_reset = now
                    for t in d:
                        p0 = num(t.get("p"))
                        v = num(t.get("v"), 0.0)
                        s = str(t.get("s", "")).lower()
                        if finite(p0):
                            self.price = p0
                        if v > 0:
                            if s == "buy":
                                self.buy_vol += v
                            elif s == "sell":
                                self.sell_vol += v
        except Exception as e:
            self.error = f"parse: {e}"

    def _on_error(self, ws, err):
        self.error = str(err)

    def _on_close(self, ws, *args):
        self.connected = False

    def snapshot(self):
        with self.lock:
            bq = sum(num(x[1], 0) for x in self.bids if len(x) >= 2)
            aq = sum(num(x[1], 0) for x in self.asks if len(x) >= 2)
            book = bq / (bq + aq) if bq + aq > 0 else None
            flow = (
                self.buy_vol / (self.buy_vol + self.sell_vol)
                if self.buy_vol + self.sell_vol > 0
                else None
            )
            return {
                "price": self.price,
                "funding": self.funding,
                "book": book,
                "flow": flow,
                "connected": self.connected,
                "age": time.time() - self.last_message if self.last_message else None,
                "error": self.error,
            }


# ---------------------------------------------------------------------
# Indicators / market structure
# ---------------------------------------------------------------------

def rma(s: pd.Series, n: int):
    return s.ewm(alpha=1/n, adjust=False, min_periods=n).mean()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c, h, l = d.close, d.high, d.low

    for n in (20, 50, 200):
        d[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()

    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = rma(gain, 14) / rma(loss, 14).replace(0, np.nan)
    d["rsi"] = (100 - 100/(1+rs)).fillna(50)

    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    d["macd"] = e12 - e26
    d["macd_sig"] = d.macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d.macd - d.macd_sig

    median = (h + l) / 2
    d["ao"] = median.rolling(5).mean() - median.rolling(34).mean()

    pc = c.shift(1)
    tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    d["atr"] = rma(tr, 14)

    up, down = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=d.index)
    mdm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=d.index)
    atr = d.atr.replace(0, np.nan)
    d["pdi"] = 100*rma(pdm, 14)/atr
    d["mdi"] = 100*rma(mdm, 14)/atr
    dx = 100*(d.pdi-d.mdi).abs()/(d.pdi+d.mdi).replace(0, np.nan)
    d["adx"] = rma(dx, 14).fillna(0)

    vol = d.baseVol.replace(0, np.nan)
    d["vol_z"] = ((vol-vol.rolling(20).mean())/vol.rolling(20).std().replace(0, np.nan)).fillna(0)

    tp = (h+l+c)/3
    d["vwap"] = (
        (tp*d.baseVol).rolling(96, min_periods=20).sum()
        / d.baseVol.rolling(96, min_periods=20).sum().replace(0, np.nan)
    ).fillna(d.ema20)

    d["don_hi"] = h.shift(1).rolling(20).max()
    d["don_lo"] = l.shift(1).rolling(20).min()
    return d


def pivots(df, kind, lookback=100, wing=2):
    col = df.high.to_numpy() if kind == "high" else df.low.to_numpy()
    out = []
    start = max(wing, len(df)-lookback)
    for i in range(start, len(df)-wing):
        w = col[i-wing:i+wing+1]
        if kind == "high" and col[i] >= np.nanmax(w):
            out.append(i)
        if kind == "low" and col[i] <= np.nanmin(w):
            out.append(i)
    return out


def structure(df):
    hi, lo = pivots(df, "high"), pivots(df, "low")
    if len(hi) < 2 or len(lo) < 2:
        return "RANGE"
    h0, h1 = df.iloc[hi[-2]].high, df.iloc[hi[-1]].high
    l0, l1 = df.iloc[lo[-2]].low, df.iloc[lo[-1]].low
    if h1 > h0 and l1 > l0:
        return "UP"
    if h1 < h0 and l1 < l0:
        return "DOWN"
    return "RANGE"


def divergence(df):
    hi, lo = pivots(df, "high", 90), pivots(df, "low", 90)
    bull = bear = False
    if len(lo) >= 2:
        a, b = lo[-2], lo[-1]
        bull = df.iloc[b].low < df.iloc[a].low and df.iloc[b].rsi > df.iloc[a].rsi + 1.5
    if len(hi) >= 2:
        a, b = hi[-2], hi[-1]
        bear = df.iloc[b].high > df.iloc[a].high and df.iloc[b].rsi < df.iloc[a].rsi - 1.5
    return bool(bull), bool(bear)


def trend(df):
    x = df.iloc[-1]
    s = structure(df)
    bull = x.close > x.ema50 and x.ema20 >= x.ema50 and x.pdi >= x.mdi
    bear = x.close < x.ema50 and x.ema20 <= x.ema50 and x.mdi >= x.pdi

    if bull and x.close > x.ema200 and x.ema50 > x.ema200 and x.adx >= 20 and s != "DOWN":
        return "BULL"
    if bear and x.close < x.ema200 and x.ema50 < x.ema200 and x.adx >= 20 and s != "UP":
        return "BEAR"
    if bull:
        return "BULL_SOFT"
    if bear:
        return "BEAR_SOFT"
    return "NEUTRAL"


def levels(frames, price):
    vals = []
    for tf, lb in (("4h", 120), ("1h", 140), ("15m", 120)):
        df = frames[tf]
        for i in pivots(df, "high", lb)[-10:]:
            vals.append(float(df.iloc[i].high))
        for i in pivots(df, "low", lb)[-10:]:
            vals.append(float(df.iloc[i].low))

    vals = sorted(v for v in vals if finite(v) and abs(v-price)/price < 0.10)
    clusters = []
    for v in vals:
        if not clusters:
            clusters.append([v])
            continue
        center = sum(clusters[-1])/len(clusters[-1])
        if abs(v-center)/center <= 0.0018:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c)/len(c) for c in clusters]


def below(xs, p):
    a = [x for x in xs if x < p*0.999]
    return max(a) if a else None


def above(xs, p):
    a = [x for x in xs if x > p*1.001]
    return min(a) if a else None


@dataclass
class Plan:
    created: datetime
    price: float
    macro_bias: str
    bias: str
    action: str
    setup: str
    context: str
    entry_low: Optional[float]
    entry_high: Optional[float]
    stop: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    breakout: Optional[float]
    pullback_low: Optional[float]
    pullback_high: Optional[float]
    rr2: Optional[float]
    why: List[str]
    wait: List[str]
    warnings: List[str]
    trends: Dict[str, str]
    rsi1h: float
    adx4h: float
    adx1h: float
    funding: Optional[float]
    book: Optional[float]
    flow: Optional[float]


def signed_trend_score(v: str, strong=2.0, soft=1.0) -> float:
    if v == "BULL":
        return strong
    if v == "BULL_SOFT":
        return soft
    if v == "BEAR":
        return -strong
    if v == "BEAR_SOFT":
        return -soft
    return 0.0


class Analyzer:
    """
    V2:
    - 1W = contexto macro, no veto automático.
    - 1D + 4H = sesgo operativo del día.
    - 1H = fase intradía.
    - 15m + 5m = permiso de entrada.
    """

    def __init__(self, api: BitunixPublic, live: LiveMarket):
        self.api = api
        self.live = live
        self.frames = {}
        self.last_frame_refresh = 0.0

    def refresh_frames(self, force=False):
        if not force and time.time() - self.last_frame_refresh < ANALYSIS_SECONDS:
            return
        new = {}
        for tf in ("1w", "1d", "4h", "1h", "15m", "5m"):
            raw = self.api.klines(tf, 260)
            if len(raw) < 80:
                raise RuntimeError(f"Solo {len(raw)} velas {tf}")
            new[tf] = indicators(raw)
        self.frames = new
        self.last_frame_refresh = time.time()

    def live_snapshot(self):
        ws = self.live.snapshot()
        tick = self.api.ticker()
        fund = self.api.funding()
        depth = self.api.depth("15")

        bids, asks = depth.get("bids", []), depth.get("asks", [])
        bq = sum(num(x[1], 0) for x in bids if len(x) >= 2)
        aq = sum(num(x[1], 0) for x in asks if len(x) >= 2)
        rest_book = bq/(bq+aq) if bq+aq > 0 else None

        ws_fresh = ws["connected"] and ws["age"] is not None and ws["age"] < 20
        price = ws["price"] if ws_fresh and finite(ws["price"]) else num(
            tick.get("lastPrice") or tick.get("last")
        )
        funding = ws["funding"] if ws_fresh and finite(ws["funding"]) else num(
            fund.get("fundingRate")
        )
        book = ws["book"] if ws_fresh and ws["book"] is not None else rest_book

        if not finite(price):
            raise RuntimeError("No pude obtener precio BTCUSDT de Bitunix.")

        return {
            "price": float(price),
            "funding": funding if finite(funding) else None,
            "book": book,
            "flow": ws["flow"],
            "ws": ws_fresh,
        }

    def make_targets(self, lev, entry, side, atr1h):
        if side == "LONG":
            candidates = sorted(x for x in lev if x > entry*1.0015)
            fallback = [entry + atr1h*m for m in (0.9, 1.8, 3.0)]
        else:
            candidates = sorted(
                (x for x in lev if x < entry*0.9985),
                reverse=True,
            )
            fallback = [entry - atr1h*m for m in (0.9, 1.8, 3.0)]

        out = []
        for x in candidates + fallback:
            if x > 0 and all(abs(x-y)/entry > 0.002 for y in out):
                out.append(float(x))
            if len(out) == 3:
                break
        return (out + [None, None, None])[:3]

    def macro_and_day_bias(self, t: Dict[str, str]):
        macro_score = (
            1.25 * signed_trend_score(t["1w"], 2.0, 1.0)
            + 1.00 * signed_trend_score(t["1d"], 2.0, 1.0)
        )

        if macro_score >= 3.0:
            macro = "BULLISH"
        elif macro_score >= 1.0:
            macro = "BULLISH LEAN"
        elif macro_score <= -3.0:
            macro = "BEARISH"
        elif macro_score <= -1.0:
            macro = "BEARISH LEAN"
        else:
            macro = "NEUTRAL"

        day_score = (
            2.2 * signed_trend_score(t["1d"], 2.0, 1.0)
            + 2.5 * signed_trend_score(t["4h"], 2.0, 1.0)
            + 0.7 * signed_trend_score(t["1h"], 2.0, 1.0)
            + 0.2 * signed_trend_score(t["1w"], 2.0, 1.0)
        )

        direct_conflict = (
            (t["1d"].startswith("BULL") and t["4h"].startswith("BEAR"))
            or (t["1d"].startswith("BEAR") and t["4h"].startswith("BULL"))
        )

        if direct_conflict:
            return macro, "NEUTRAL", day_score

        if day_score >= 7.0:
            day = "LONG STRONG"
        elif day_score >= 3.0:
            day = "LONG"
        elif day_score <= -7.0:
            day = "SHORT STRONG"
        elif day_score <= -3.0:
            day = "SHORT"
        else:
            day = "NEUTRAL"

        return macro, day, day_score

    def analyze(self) -> Plan:
        self.refresh_frames()
        snap = self.live_snapshot()
        price = float(snap["price"])

        f = self.frames
        t = {tf: trend(f[tf]) for tf in f}
        st = {tf: structure(f[tf]) for tf in f}
        b1h, s1h = divergence(f["1h"])
        b15, s15 = divergence(f["15m"])

        macro_bias, bias, day_score = self.macro_and_day_bias(t)

        x4 = f["4h"].iloc[-1]
        x1 = f["1h"].iloc[-1]
        x15 = f["15m"].iloc[-1]
        p15 = f["15m"].iloc[-2]
        x5 = f["5m"].iloc[-1]
        p5 = f["5m"].iloc[-2]

        lev = levels(f, price)
        sup, res = below(lev, price), above(lev, price)
        atr15 = float(x15.atr) if finite(x15.atr) else price*0.004
        atr1 = float(x1.atr) if finite(x1.atr) else price*0.009

        why, wait, warnings = [], [], []
        action, setup = "NO TRADE", "-"
        entry_low = entry_high = stop = breakout = pull_lo = pull_hi = None
        tp1 = tp2 = tp3 = rr2 = None

        if bias.startswith("LONG") and t["1h"].startswith("BEAR"):
            context = "1H correction/pullback inside a bullish day bias"
        elif bias.startswith("SHORT") and t["1h"].startswith("BULL"):
            context = "1H rebound inside a bearish day bias"
        elif bias.startswith("LONG"):
            context = "Intraday momentum aligned bullish"
        elif bias.startswith("SHORT"):
            context = "Intraday momentum aligned bearish"
        else:
            context = "1D and 4H are not aligned enough for a directional day bias"

        if bias == "NEUTRAL":
            wait.append(
                "1D and 4H do not agree enough yet. Wait for one side to take structure."
            )
            return Plan(
                datetime.now(TZ), price, macro_bias, bias, action, setup,
                context, None, None, None, None, None, None,
                None, None, None, None,
                why, wait, warnings, t,
                float(x1.rsi), float(x4.adx), float(x1.adx),
                snap["funding"], snap["book"], snap["flow"],
            )

        side = "LONG" if bias.startswith("LONG") else "SHORT"

        if side == "LONG":
            why += [
                f"Day score {day_score:.1f}: 1D {t['1d']} + 4H {t['4h']}",
                f"4H structure {st['4h']} | ADX {x4.adx:.1f} | +DI {x4.pdi:.1f} vs -DI {x4.mdi:.1f}",
            ]

            breakout = float(f["15m"].high.iloc[-17:-1].max())

            pull_candidates = [
                x for x in (
                    sup,
                    float(x15.ema20),
                    float(x15.vwap),
                )
                if finite(x) and x < price*1.004
            ]
            pull_center = max(
                pull_candidates,
                default=price - 0.65*atr15,
            )
            pull_lo = pull_center - 0.22*atr15
            pull_hi = pull_center + 0.22*atr15

            breakout_ok = (
                x15.close > breakout
                and x15.vol_z >= 0.25
                and 51 <= x15.rsi <= 76
                and x15.macd_hist >= p15.macd_hist
                and x5.close > x5.ema20
                and x5.rsi >= 50
            )

            pullback_ok = (
                x15.low <= max(x15.ema20, x15.vwap) + 0.20*atr15
                and x15.close > max(x15.ema20, x15.vwap)
                and x15.close > x15.open
                and 43 <= x15.rsi <= 69
                and x5.close > x5.ema20
                and x5.rsi >= 48
                and x5.macd_hist >= p5.macd_hist
            )

            continuation_ok = (
                t["1h"] in ("BULL", "BULL_SOFT")
                and x1.adx >= 22
                and x1.pdi >= x1.mdi
                and x15.close > x15.ema20
                and x15.ema20 >= x15.ema50
                and 52 <= x15.rsi <= 72
                and x15.macd_hist > 0
                and x15.macd_hist >= p15.macd_hist
                and x15.ao >= 0
                and x5.close > x5.ema20
                and x5.rsi >= 50
            )

            div_veto = bool(s1h and s15)

            if b1h or b15:
                why.append("Bullish RSI divergence detected")
            if s1h:
                warnings.append("1H bearish RSI divergence: LONG needs extra care")
            if div_veto:
                warnings.append("Bearish divergence on BOTH 1H and 15m: LONG veto")

            candidates = []
            if pullback_ok:
                candidates.append("PULLBACK / RECLAIM")
            if breakout_ok:
                candidates.append("BREAKOUT")
            if continuation_ok:
                candidates.append("CONTINUATION")

            if candidates and not div_veto:
                setup = candidates[0]
                entry_low = price - 0.10*atr15
                entry_high = price + 0.10*atr15

                recent_swing = float(f["15m"].low.iloc[-10:].min())

                if setup == "BREAKOUT":
                    structural_stop = max(
                        float(x15.ema20) - 0.25*atr15,
                        breakout - 0.55*atr15,
                    )
                    stop = min(price - 0.45*atr15, structural_stop)
                elif setup == "CONTINUATION":
                    structural_stop = max(
                        float(x15.ema20) - 0.35*atr15,
                        recent_swing,
                    )
                    stop = min(price - 0.40*atr15, structural_stop)
                else:
                    structural_stop = min(
                        float(x15.ema50),
                        recent_swing,
                    )
                    stop = structural_stop - 0.15*atr15

                tp1, tp2, tp3 = self.make_targets(
                    lev, price, "LONG", atr1
                )

                risk = max(price-stop, 1e-9)
                rr2 = (tp2-price)/risk if tp2 else None
                extension = (
                    price - float(x15.ema20)
                ) / max(atr15, 1e-9)

                if x1.rsi >= 80 and setup != "PULLBACK / RECLAIM":
                    action = "TOO LATE"
                    warnings.append(
                        f"RSI 1H {x1.rsi:.1f}: bullish but overextended; wait pullback"
                    )
                elif extension > MAX_EXTENSION_ATR:
                    action = "TOO LATE"
                    warnings.append(
                        f"Price is {extension:.2f} ATR15 above EMA20: do not chase"
                    )
                elif rr2 is not None and rr2 < MIN_RR_LATE:
                    action = "TOO LATE"
                    warnings.append(
                        f"Only {rr2:.2f}R left to TP2: poor remaining reward/risk"
                    )
                elif rr2 is not None and rr2 >= MIN_RR_ENTER:
                    action = "ENTER LONG NOW"
                else:
                    action = "WAIT"
                    wait.append(
                        "Direction is LONG, but wait for a better price / more room to TP2."
                    )
            else:
                action = "WAIT"
                wait.append(
                    f"Breakout LONG: 15m close above {price_fmt(breakout)} with momentum/volume"
                )
                wait.append(
                    f"Pullback LONG: reclaim around {price_fmt(pull_lo)}–{price_fmt(pull_hi)}"
                )
                if t["1h"] in ("BULL", "BULL_SOFT"):
                    wait.append(
                        "Continuation LONG allowed if 15m/5m stay aligned and price is not extended."
                    )
                elif t["1h"].startswith("BEAR"):
                    wait.append(
                        "1H is correcting; that alone is NOT permission to SHORT."
                    )

        else:
            why += [
                f"Day score {day_score:.1f}: 1D {t['1d']} + 4H {t['4h']}",
                f"4H structure {st['4h']} | ADX {x4.adx:.1f} | -DI {x4.mdi:.1f} vs +DI {x4.pdi:.1f}",
            ]

            breakout = float(f["15m"].low.iloc[-17:-1].min())

            pull_candidates = [
                x for x in (
                    res,
                    float(x15.ema20),
                    float(x15.vwap),
                )
                if finite(x) and x > price*0.996
            ]
            pull_center = min(
                pull_candidates,
                default=price + 0.65*atr15,
            )
            pull_lo = pull_center - 0.22*atr15
            pull_hi = pull_center + 0.22*atr15

            macro_short_ok = (
                t["1d"] in ("BEAR", "BEAR_SOFT")
                and t["4h"] in ("BEAR", "BEAR_SOFT")
                and x4.adx >= 22
                and x4.mdi > x4.pdi
            )

            breakout_ok = (
                macro_short_ok
                and x15.close < breakout
                and x15.vol_z >= 0.35
                and 26 <= x15.rsi <= 49
                and x15.macd_hist <= p15.macd_hist
                and x5.close < x5.ema20
                and x5.rsi <= 50
            )

            pullback_ok = (
                macro_short_ok
                and x15.high >= min(x15.ema20, x15.vwap) - 0.20*atr15
                and x15.close < min(x15.ema20, x15.vwap)
                and x15.close < x15.open
                and 33 <= x15.rsi <= 57
                and x5.close < x5.ema20
                and x5.rsi <= 52
                and x5.macd_hist <= p5.macd_hist
            )

            continuation_ok = (
                macro_short_ok
                and t["1h"] in ("BEAR", "BEAR_SOFT")
                and x1.adx >= 24
                and x1.mdi > x1.pdi
                and x15.close < x15.ema20
                and x15.ema20 <= x15.ema50
                and 28 <= x15.rsi <= 48
                and x15.macd_hist < 0
                and x15.macd_hist <= p15.macd_hist
                and x15.ao <= 0
                and x5.close < x5.ema20
                and x5.rsi <= 50
            )

            div_veto = bool(b1h or b15)

            if s1h or s15:
                why.append("Bearish RSI divergence detected")
            if div_veto:
                warnings.append("Bullish RSI divergence present: SHORT veto")

            candidates = []
            if pullback_ok:
                candidates.append("PULLBACK / REJECTION")
            if breakout_ok:
                candidates.append("BREAKDOWN")
            if continuation_ok:
                candidates.append("CONTINUATION")

            if candidates and not div_veto:
                setup = candidates[0]
                entry_low = price - 0.10*atr15
                entry_high = price + 0.10*atr15

                recent_swing = float(f["15m"].high.iloc[-10:].max())

                if setup == "BREAKDOWN":
                    structural_stop = min(
                        float(x15.ema20) + 0.25*atr15,
                        breakout + 0.55*atr15,
                    )
                    stop = max(price + 0.45*atr15, structural_stop)
                elif setup == "CONTINUATION":
                    structural_stop = min(
                        float(x15.ema20) + 0.35*atr15,
                        recent_swing,
                    )
                    stop = max(price + 0.40*atr15, structural_stop)
                else:
                    structural_stop = max(
                        float(x15.ema50),
                        recent_swing,
                    )
                    stop = structural_stop + 0.15*atr15

                tp1, tp2, tp3 = self.make_targets(
                    lev, price, "SHORT", atr1
                )

                risk = max(stop-price, 1e-9)
                rr2 = (price-tp2)/risk if tp2 else None
                extension = (
                    float(x15.ema20) - price
                ) / max(atr15, 1e-9)

                if x1.rsi <= 20 and setup != "PULLBACK / REJECTION":
                    action = "TOO LATE"
                    warnings.append(
                        f"RSI 1H {x1.rsi:.1f}: bearish but oversold; wait rebound/rejection"
                    )
                elif extension > MAX_EXTENSION_ATR:
                    action = "TOO LATE"
                    warnings.append(
                        f"Price is {extension:.2f} ATR15 below EMA20: do not chase"
                    )
                elif rr2 is not None and rr2 < MIN_RR_LATE:
                    action = "TOO LATE"
                    warnings.append(
                        f"Only {rr2:.2f}R left to TP2: poor remaining reward/risk"
                    )
                elif rr2 is not None and rr2 >= MIN_RR_ENTER:
                    action = "ENTER SHORT NOW"
                else:
                    action = "WAIT"
                    wait.append(
                        "Direction is SHORT, but wait for a better price / more room to TP2."
                    )
            else:
                action = "WAIT"
                wait.append(
                    f"Breakdown SHORT: 15m close below {price_fmt(breakout)} with momentum/volume"
                )
                wait.append(
                    f"Pullback SHORT: rejection around {price_fmt(pull_lo)}–{price_fmt(pull_hi)}"
                )
                if t["1h"] in ("BEAR", "BEAR_SOFT"):
                    wait.append(
                        "Continuation SHORT allowed if 15m/5m stay aligned and price is not extended."
                    )
                elif t["1h"].startswith("BULL"):
                    wait.append(
                        "1H is rebounding; do not chase SHORT until rejection confirms."
                    )

        if snap["book"] is not None:
            if side == "LONG" and snap["book"] >= 0.56:
                why.append(
                    f"Order-book bid share ~{snap['book']*100:.0f}% supports LONG"
                )
            elif side == "SHORT" and snap["book"] <= 0.44:
                why.append(
                    f"Order-book ask dominance ~{(1-snap['book'])*100:.0f}% supports SHORT"
                )

        if snap["flow"] is not None:
            if side == "LONG" and snap["flow"] >= 0.57:
                why.append(
                    f"Recent public trade buy flow ~{snap['flow']*100:.0f}%"
                )
            elif side == "SHORT" and snap["flow"] <= 0.43:
                why.append(
                    f"Recent public trade sell flow ~{(1-snap['flow'])*100:.0f}%"
                )

        return Plan(
            datetime.now(TZ), price, macro_bias, bias, action, setup,
            context, entry_low, entry_high, stop, tp1, tp2, tp3,
            breakout, pull_lo, pull_hi, rr2,
            why, wait, warnings, t,
            float(x1.rsi), float(x4.adx), float(x1.adx),
            snap["funding"], snap["book"], snap["flow"],
        )


# ---------------------------------------------------------------------
# Telegram formatting
# ---------------------------------------------------------------------

def icon_bias(bias):
    return {
        "LONG STRONG": "🟢🟢",
        "LONG": "🟢",
        "NEUTRAL": "⚪",
        "SHORT": "🔴",
        "SHORT STRONG": "🔴🔴",
    }.get(bias, "⚪")


def icon_macro(macro):
    if macro.startswith("BULLISH"):
        return "🟢"
    if macro.startswith("BEARISH"):
        return "🔴"
    return "⚪"


def icon_action(action):
    return {
        "ENTER LONG NOW": "🚨🟢",
        "ENTER SHORT NOW": "🚨🔴",
        "WAIT": "🟡",
        "TOO LATE": "⛔",
        "NO TRADE": "⚪",
    }.get(action, "⚪")


def plan_message(p: Plan, title="BTCUSDT COPILOT V2") -> str:
    lines = [
        f"<b>{html.escape(title)}</b>",
        f"Precio: <b>{price_fmt(p.price)} USDT</b>",
        "",
        f"{icon_macro(p.macro_bias)} Macro 1W/1D: <b>{html.escape(p.macro_bias)}</b>",
        f"{icon_bias(p.bias)} Sesgo DEL DÍA: <b>{html.escape(p.bias)}</b>",
        f"{icon_action(p.action)} Entrada AHORA: <b>{html.escape(p.action)}</b>",
        f"Setup: <b>{html.escape(p.setup)}</b>",
        "",
        f"1W {p.trends['1w']} | 1D {p.trends['1d']} | 4H {p.trends['4h']} | 1H {p.trends['1h']}",
        f"RSI 1H: {p.rsi1h:.1f} | ADX 4H: {p.adx4h:.1f} | ADX 1H: {p.adx1h:.1f}",
        f"Funding: {pct_fmt(p.funding)}",
        f"Contexto: {html.escape(p.context)}",
    ]

    if p.entry_low is not None:
        lines += [
            "",
            f"Entrada orientativa: <b>{price_fmt(p.entry_low)}–{price_fmt(p.entry_high)}</b>",
            f"Invalidación/SL técnico: <b>{price_fmt(p.stop)}</b>",
            f"TP1: <b>{price_fmt(p.tp1)}</b>",
            f"TP2: <b>{price_fmt(p.tp2)}</b>",
            f"TP3: <b>{price_fmt(p.tp3)}</b>",
            f"R:R restante a TP2: <b>{p.rr2:.2f}R</b>"
            if p.rr2 is not None else "",
        ]

    if p.wait:
        lines += ["", "<b>Qué espera exactamente:</b>"]
        lines += [f"• {html.escape(x)}" for x in p.wait[:5]]

    if p.why:
        lines += ["", "<b>Por qué:</b>"]
        lines += [f"• {html.escape(x)}" for x in p.why[:6]]

    if p.warnings:
        lines += ["", "<b>Avisos:</b>"]
        lines += [f"• {html.escape(x)}" for x in p.warnings[:5]]

    lines += [
        "",
        "<i>MACRO ≠ SESGO DEL DÍA ≠ ENTRADA.",
        "Solo ENTER NOW significa que las reglas de entrada están cumplidas.",
        "Es análisis técnico, no una garantía.</i>",
    ]
    return "\n".join(lines)[:4090]


def startup_message(p: Plan) -> str:
    return (
        "🤖 <b>BTC Copilot V2 conectado</b>\n\n"
        "Fuente: Bitunix BTCUSDT Futures\n"
        "Modo: SOLO análisis; no puede operar tu cuenta.\n"
        "V2: sesgo diario + pullback + breakout + continuation.\n"
        "Alertas: ENTER NOW + cambio de sesgo + plan diario.\n\n"
        + plan_message(p, "ESTADO INICIAL V2")
    )


# ---------------------------------------------------------------------
# Main loop / alerts
# ---------------------------------------------------------------------

class App:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("Falta TELEGRAM_BOT_TOKEN")
        if not TELEGRAM_CHAT_ID:
            raise RuntimeError(
                "Falta TELEGRAM_CHAT_ID. Ejecuta primero telegram_setup.py "
                "en tu PC y copia el número a Railway."
            )

        self.tg = Telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.api = BitunixPublic()
        self.live = LiveMarket()
        self.analyzer = Analyzer(self.api, self.live)
        self.plan = None
        self.last_action = None
        self.last_bias = None
        self.last_alert_at = {}
        self.last_daily_date = None
        self.paused = False

    def send_plan(self, title):
        if self.plan:
            self.tg.send(plan_message(self.plan, title))

    def alert_allowed(self, key):
        last = self.last_alert_at.get(key, 0)
        return time.time() - last >= ALERT_COOLDOWN_MIN*60

    def maybe_alert(self, p: Plan):
        actionable = p.action in ("ENTER LONG NOW", "ENTER SHORT NOW")

        if actionable:
            key = p.action
            if self.last_action != p.action or self.alert_allowed(key):
                self.tg.send(
                    plan_message(
                        p,
                        "🚨 SETUP CONFIRMADO — REVISA ENTRADA AHORA"
                    )
                )
                self.last_alert_at[key] = time.time()

        # Bias change matters, but notify quietly and never call it an entry.
        if self.last_bias is not None and p.bias != self.last_bias:
            self.tg.send(
                plan_message(p, "🔄 CAMBIO DE SESGO"),
                disable_notification=True,
            )

        self.last_action = p.action
        self.last_bias = p.bias

    def daily_plan(self, p):
        today = datetime.now(TZ).date()
        now = datetime.now(TZ)
        if now.hour >= DAILY_PLAN_HOUR and self.last_daily_date != today:
            self.tg.send(plan_message(p, "☀️ PLAN BTC DEL DÍA"))
            self.last_daily_date = today

    def commands(self):
        for cmd in self.tg.poll_commands():
            if cmd in ("/status", "/plan"):
                self.send_plan("📍 ESTADO AHORA")
            elif cmd == "/pause":
                self.paused = True
                self.tg.send("🔕 Alertas de setup pausadas. Usa /resume para reactivarlas.")
            elif cmd == "/resume":
                self.paused = False
                self.tg.send("🔔 Alertas de setup reactivadas.")
            elif cmd == "/help":
                self.tg.send(
                    "<b>Comandos</b>\n"
                    "/status — análisis actual\n"
                    "/plan — análisis actual\n"
                    "/pause — pausa alertas automáticas\n"
                    "/resume — reactiva alertas\n"
                    "/help — ayuda"
                )

    def run(self):
        self.live.start()
        log("Cargando mercado y análisis inicial...")
        self.plan = self.analyzer.analyze()
        self.last_action = self.plan.action
        self.last_bias = self.plan.bias
        self.tg.send(startup_message(self.plan))

        log(
            f"READY | {SYMBOL} {price_fmt(self.plan.price)} | "
            f"{self.plan.bias} | {self.plan.action}"
        )

        last_analysis = 0.0
        while not STOP_EVENT.is_set():
            try:
                self.commands()

                if time.time() - last_analysis >= ANALYSIS_SECONDS:
                    p = self.analyzer.analyze()
                    self.plan = p
                    log(
                        f"{SYMBOL} {price_fmt(p.price)} | "
                        f"bias={p.bias} | action={p.action} | setup={p.setup}"
                    )
                    self.daily_plan(p)
                    if not self.paused:
                        self.maybe_alert(p)
                    last_analysis = time.time()

                STOP_EVENT.wait(LIVE_SECONDS)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log(f"Loop error: {type(e).__name__}: {e}")
                time.sleep(10)


def stop_handler(*_):
    STOP_EVENT.set()


def main():
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    log("BTC COPILOT V2 TELEGRAM starting...")
    log("Public Bitunix data only — NO order execution.")
    App().run()
    log("Stopped.")


if __name__ == "__main__":
    main()
