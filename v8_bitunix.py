"""Bitunix V8 adapter: fixed LONG entry, reduce-only exit, fixed leverage 1."""
import hashlib
import json
import os
import secrets
import time
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

from trend_v8 import BASE, SYMBOL


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Bitunix redirect rejected")


class BitunixV8:
    READS = frozenset({
        "account", "account/get_leverage_margin_mode",
        "position/get_pending_positions", "position/get_history_positions",
        "trade/get_pending_orders", "trade/get_order_detail", "trade/get_history_trades",
        "tpsl/get_pending_orders", "market/trading_pairs", "market/tickers",
    })

    def __init__(self, mutation_gate):
        self.key = os.getenv("BITUNIX_API_KEY", "").strip()
        self.secret = os.getenv("BITUNIX_SECRET_KEY", "").strip()
        self.mutation_gate = mutation_gate
        self.transport = build_opener(NoRedirect())

    def _request(self, method, endpoint, params=None, body=None):
        if method == "GET":
            if endpoint not in self.READS or body is not None:
                raise PermissionError("Read not allowed")
        elif method == "POST":
            if os.getenv("V8_LIVE_EXECUTION", "false").lower() != "true":
                raise PermissionError("V8 live mutations disabled")
            self.mutation_gate()
            if endpoint == "account/change_leverage":
                if body != {"symbol": SYMBOL, "marginCoin": "USDT", "leverage": 1}:
                    raise PermissionError("Only leverage 1 is permitted")
            elif endpoint == "trade/place_order":
                common = {"symbol", "side", "qty", "orderType", "clientId", "reduceOnly"}
                if (set(body) != common or body["symbol"] != SYMBOL or
                        body["orderType"] != "MARKET" or
                        not body["clientId"].startswith("igodv8-") or
                        not ((body["side"] == "BUY" and body["reduceOnly"] is False) or
                             (body["side"] == "SELL" and body["reduceOnly"] is True))):
                    raise PermissionError("Only LONG entry or reduce-only sell is permitted")
                quantity = Decimal(str(body["qty"]))
                if not quantity.is_finite() or quantity <= 0:
                    raise PermissionError("Positive finite quantity required")
            else:
                raise PermissionError("Mutation not allowed")
        else:
            raise PermissionError("Method not allowed")
        params = params or {}
        data = json.dumps(body, separators=(",", ":")) if body is not None else ""
        headers = {"Content-Type": "application/json", "language": "en-US"}
        if not endpoint.startswith("market/"):
            if not self.key or not self.secret:
                raise RuntimeError("Bitunix private credentials unavailable")
            nonce, ts = secrets.token_hex(16), str(int(time.time() * 1000))
            query = "".join(f"{k}{v}" for k, v in sorted(params.items()))
            digest = hashlib.sha256((nonce + ts + self.key + query + data).encode()).hexdigest()
            headers.update({"api-key": self.key, "nonce": nonce, "timestamp": ts,
                            "sign": hashlib.sha256((digest + self.secret).encode()).hexdigest()})
        url = BASE + "/api/v1/futures/" + endpoint
        if params:
            url += "?" + urlencode(params)
        request = Request(url, data=data.encode() if body is not None else None,
                          headers=headers, method=method)
        # No automatic retries, redirects, or logging of credential-bearing requests.
        with self.transport.open(request, timeout=12) as response:
            payload = json.load(response)
        if payload.get("code") != 0:
            raise RuntimeError(f"Bitunix error code {payload.get('code')}")
        return payload.get("data")

    @staticmethod
    def one(data):
        if isinstance(data, list) and len(data) == 1:
            return data[0]
        if isinstance(data, dict):
            return data
        raise RuntimeError("Ambiguous Bitunix response")

    @staticmethod
    def rows(data, key):
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get(key), list):
            rows = data[key]
            if int(data.get("total", len(rows))) > len(rows) or len(rows) >= 100:
                raise RuntimeError("Truncated Bitunix response")
            return rows
        raise RuntimeError("Missing Bitunix list")

    def account(self):
        return self.one(self._request("GET", "account", {"marginCoin": "USDT"}))

    def leverage(self):
        return self.one(self._request("GET", "account/get_leverage_margin_mode",
                                      {"symbol": SYMBOL, "marginCoin": "USDT"}))["leverage"]

    def positions(self):
        return self.rows(self._request("GET", "position/get_pending_positions",
                                       {"symbol": SYMBOL, "includeSubAccounts": "false"}), "positionList")

    def orders(self):
        ordinary = self.rows(self._request("GET", "trade/get_pending_orders",
                                           {"symbol": SYMBOL, "limit": 100}), "orderList")
        protective = self.rows(self._request("GET", "tpsl/get_pending_orders",
                                             {"symbol": SYMBOL, "limit": 100}), "orderList")
        return ordinary + protective

    def order(self, client_id):
        # Not-found/API errors are ambiguous; caller must block, never assume no order.
        return self.one(self._request("GET", "trade/get_order_detail", {"clientId": client_id}))

    def fills(self, position_id=None, order_id=None):
        params = {"symbol": SYMBOL, "limit": 100}
        if position_id:
            params["positionId"] = position_id
        if order_id:
            params["orderId"] = order_id
        return self.rows(self._request("GET", "trade/get_history_trades", params), "tradeList")

    def history_position(self, position_id):
        rows = self.rows(self._request("GET", "position/get_history_positions",
                                       {"symbol": SYMBOL, "positionId": position_id, "limit": 100}), "positionList")
        matches = [r for r in rows if str(r["positionId"]) == str(position_id)]
        if len(matches) != 1:
            raise RuntimeError("Closed position not confirmed")
        return matches[0]

    def rules(self):
        rows = self._request("GET", "market/trading_pairs", {"symbols": SYMBOL})
        matches = [r for r in rows if r.get("symbol") == SYMBOL]
        if len(matches) != 1:
            raise RuntimeError("BTCUSDT rules unavailable")
        return matches[0]

    def price(self):
        rows = self._request("GET", "market/tickers", {"symbols": SYMBOL})
        matches = [r for r in rows if r.get("symbol") == SYMBOL]
        if len(matches) != 1:
            raise RuntimeError("BTCUSDT price unavailable")
        return matches[0]["lastPrice"]

    def set_leverage_one(self):
        return self._request("POST", "account/change_leverage",
                             body={"symbol": SYMBOL, "marginCoin": "USDT", "leverage": 1})

    def open_long(self, quantity, client_id):
        return self._request("POST", "trade/place_order", body={
            "symbol": SYMBOL, "side": "BUY", "qty": quantity, "orderType": "MARKET",
            "clientId": client_id, "reduceOnly": False})

    def close_long(self, quantity, client_id):
        # ONE_WAY only. SELL can only reduce; never retry without exchange reconciliation.
        return self._request("POST", "trade/place_order", body={
            "symbol": SYMBOL, "side": "SELL", "qty": quantity, "orderType": "MARKET",
            "clientId": client_id, "reduceOnly": True})
