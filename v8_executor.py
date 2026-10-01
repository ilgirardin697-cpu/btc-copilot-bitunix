"""Independent opt-in V8 REAL worker. Decisions come only from trend_v8."""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import json
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from execution_guard import ExecutionLease
import trend_v8 as trend
from v8_bitunix import BitunixV8


class Blocked(RuntimeError):
    pass


def positive(value):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise Blocked("Non-positive or invalid numeric field")
    return number


def finite(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise Blocked("Invalid numeric field")
    return number


def telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chats = {os.getenv(k, "").strip() for k in ("TELEGRAM_CHAT_ID", "TELEGRAM_ALERT_CHAT_ID")}
    if not token:
        return
    for chat in chats - {""}:
        try:
            body = urlencode({"chat_id": chat, "text": message}).encode()
            with urlopen(Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 method="POST"), timeout=12) as response:
                json.load(response)
        except Exception:
            print("V8 notification unavailable", flush=True)


class LiveExecutor:
    def __init__(self, directory, shadow, lease, api=None, clock=None, notify=telegram):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "igod_v8_live_state.json"
        self.journal = self.directory / "igod_v8_live_journal.jsonl"
        self.disarm_path = self.directory / "V8_DISARM"
        self.shadow, self.lease = shadow, lease
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.notify = notify
        self.exposure = positive(os.getenv("V8_LIVE_EXPOSURE", "0.25"))
        if self.exposure > 1:
            raise Blocked("Exposure must be <= 1x")
        self.reserve = finite(os.getenv("V8_LIVE_RESERVE", "0.002"))
        if not Decimal("0.001") <= self.reserve < 1:
            raise Blocked("Fee/slippage reserve must be at least 10 bps and below 100%")
        self.state = {"schema": 1, "version": "V8", "mode": "REAL", "revision": 0,
                      "armed_at": None, "last_candle": -1, "last_target": None,
                      "position": None, "intent": None, "blocked": "",
                      "exposure": str(self.exposure)}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            self.validate_state(self.state)
        self.recover()
        self.api = api or BitunixV8(self.gate)
        self.context = None

    def validate_state(self, state):
        if (state.get("schema") != 1 or state.get("version") != "V8" or
                state.get("mode") != "REAL" or state.get("exposure") != str(self.exposure)):
            raise Blocked("Incompatible persistent REAL state")

    def recover(self):
        if self.journal.exists():
            revision = 0
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                snapshot = event["state_after"]
                self.validate_state(snapshot)
                if snapshot["revision"] != revision + 1:
                    raise Blocked("Non-sequential REAL journal")
                revision = snapshot["revision"]
                if snapshot["revision"] == self.state["revision"] and snapshot != self.state:
                    raise Blocked("State/journal mismatch")
                if snapshot["revision"] > self.state["revision"]:
                    self.write_state(snapshot)
            if revision != self.state["revision"]:
                raise Blocked("State ahead of durable journal")
        elif self.state["revision"] != 0:
            raise Blocked("Persistent state has no journal")

    def write_state(self, state):
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(state, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.state = state

    def record(self, event, state=None, **details):
        state = deepcopy(self.state if state is None else state)
        state["revision"] = self.state["revision"] + 1
        payload = {"event": event, "time_ms": self.clock(), "state_after": state, **details}
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.write_state(state)

    def enabled(self):
        return os.getenv("V8_LIVE_EXECUTION", "false").lower() == "true" and not self.disarm_path.exists()

    def start(self):
        self.recover()
        state = deepcopy(self.state)
        # Every process start creates a NEW ARM barrier, including restarts.
        state["armed_at"] = self.clock() if self.enabled() else None
        message = "V8 REAL ARMED" if self.enabled() else "V8 REAL DISARMED"
        self.record(message, state)
        self.notify(message)

    def check_shadow(self, decision, event):
        identity = trend.fingerprint(decision)
        if (event.get("mode") != "SHADOW" or event.get("symbol") != trend.SYMBOL or
                event.get("event_id") != f"v8-{decision['candle_time']}" or
                event.get("decision") != decision or event.get("fingerprint") != identity):
            raise Blocked("SHADOW/REAL fingerprint mismatch")
        # A caller-provided event is insufficient: it must already be durable in SHADOW.
        if not self.shadow.journal.exists():
            raise Blocked("SHADOW journal unavailable")
        persisted = [json.loads(line) for line in self.shadow.journal.read_text(encoding="utf-8").splitlines()]
        if not any(row == event for row in persisted):
            raise Blocked("SHADOW decision not persisted")
        return identity

    def gate(self):
        if not self.enabled():
            raise Blocked("V8_LIVE_EXECUTION=false or DISARM")
        if not self.lease.held:
            raise Blocked("Exclusive execution lease missing")
        if self.state["armed_at"] is None or self.context is None:
            raise Blocked("REAL is not armed for a decision")
        decision, event = self.context
        self.check_shadow(decision, event)
        timestamp = decision["candle_time"]
        close_time = timestamp + trend.FOUR_HOURS
        now = self.clock()
        if (timestamp % trend.FOUR_HOURS or close_time > now - 1500 or
                close_time <= self.state["armed_at"] or now - close_time > 300_000):
            raise Blocked("Candle unclosed, stale or before ARM")
        if decision["direction"] not in ("LONG", "FLAT"):
            raise Blocked("SHORT forbidden")
        sma = positive(decision["comparison"]["200"]["sma"])
        expected = "LONG" if positive(decision["close"]) > sma else "FLAT"
        if decision["direction"] != expected:
            raise Blocked("Decision inconsistent with SMA200")
        if json.loads(self.path.read_text(encoding="utf-8")) != self.state:
            raise Blocked("Persistent state mismatch")

    def owned(self, positions):
        owner = self.state["position"]
        if owner is None:
            if positions:
                raise Blocked("Manual/external BTCUSDT position")
            return
        if len(positions) != 1:
            raise Blocked("Exchange/state position mismatch")
        position = positions[0]
        if (str(position.get("positionId")) != owner["position_id"] or
                position.get("symbol") != trend.SYMBOL or position.get("side") != "LONG" or
                position.get("positionMode") != "ONE_WAY" or finite(position.get("leverage")) != 1 or
                positive(position.get("qty")) != positive(owner["qty"])):
            raise Blocked("Position ownership/quantity changed")
        order = self.api.order(owner["client_id"])
        self.validate_order(order, owner["client_id"], "OPEN", owner["qty"])
        if str(order["orderId"]) != owner["order_id"]:
            raise Blocked("Opening order identity changed")
        fills = self.api.fills(position_id=owner["position_id"])
        if not fills or any(str(f.get("orderId")) != owner["order_id"] for f in fills):
            raise Blocked("Position contains unowned fills")
        self.fill_metrics(fills, owner["qty"], order, Decimal("1"))

    def preflight(self, require_leverage=True):
        self.gate()
        account = self.api.account()
        if account.get("positionMode") != "ONE_WAY":
            raise Blocked("ONE_WAY required")
        equity = sum(finite(account[k]) for k in (
            "available", "frozen", "margin", "crossUnrealizedPNL", "isolationUnrealizedPNL"))
        equity = positive(equity)
        positions = self.api.positions()
        self.owned(positions)
        if self.api.orders():
            # V8 creates no protective orders. Any such order is unexplained: never cancel it.
            raise Blocked("Ambiguous/orphan BTCUSDT orders")
        if require_leverage and finite(self.api.leverage()) != 1:
            raise Blocked("Leverage 1x verification failed")
        rules = self.api.rules()
        if (rules.get("symbol") != trend.SYMBOL or rules.get("symbolStatus") != "OPEN" or
                rules.get("isApiSupported") is not True or positive(rules["minLeverage"]) > 1):
            raise Blocked("BTCUSDT cannot trade at 1x")
        price = positive(self.api.price())
        intent = self.state["intent"]
        if intent:
            quantity = self.valid_qty(intent["qty"], rules)
            if intent["kind"] == "OPEN":
                if (quantity * price > equity * self.exposure or
                        quantity * price * (1 + self.reserve) > positive(account["available"])):
                    raise Blocked("Exposure or cash changed before submission")
            elif (self.state["position"] is None or
                  quantity != positive(self.state["position"]["qty"])):
                raise Blocked("Closing quantity no longer owned")
        return equity, account, rules, price

    @staticmethod
    def valid_qty(quantity, rules):
        precision = int(rules["basePrecision"])
        if not 0 <= precision <= 12:
            raise Blocked("Invalid quantity precision")
        step = Decimal(1).scaleb(-precision)
        quantity = positive(quantity)
        if (quantity.quantize(step) != quantity or quantity < positive(rules["minTradeVolume"]) or
                quantity > positive(rules["maxMarketOrderVolume"])):
            raise Blocked("Quantity outside Bitunix restrictions")
        return quantity

    @staticmethod
    def validate_order(order, client_id, kind, quantity):
        if (not client_id.startswith("igodv8-") or order.get("clientId") != client_id or
                order.get("symbol") != trend.SYMBOL or order.get("status") != "FILLED" or
                order.get("side") != ("BUY" if kind == "OPEN" else "SELL") or
                order.get("reduceOnly") is not (kind == "CLOSE") or
                order.get("positionMode") != "ONE_WAY" or finite(order.get("leverage")) != 1 or
                positive(order.get("tradeQty")) != positive(quantity) or not order.get("orderId")):
            raise Blocked("Order fill/ownership not conclusively verified")

    @staticmethod
    def fill_metrics(fills, quantity, order, close_price):
        if not fills or len(fills) >= 100:
            raise Blocked("Missing/truncated fills")
        if any(str(f.get("orderId")) != str(order["orderId"]) or
               f.get("clientId") != order["clientId"] or f.get("symbol") != trend.SYMBOL or
               f.get("side") != order["side"] or f.get("reduceOnly") is not order["reduceOnly"] or
               f.get("positionMode") != "ONE_WAY" or finite(f.get("leverage")) != 1 for f in fills):
            raise Blocked("Fill ownership inconsistent")
        if len({f["tradeId"] for f in fills}) != len(fills):
            raise Blocked("Duplicate fills")
        qty = sum(positive(f["qty"]) for f in fills)
        if qty != positive(quantity):
            raise Blocked("Fill quantity mismatch")
        notional = sum(positive(f["qty"]) * positive(f["price"]) for f in fills)
        price = notional / qty
        gross = sum(finite(f["realizedPNL"]) for f in fills)
        fees = sum(abs(finite(f["fee"])) for f in fills)
        return {"fill_price": float(price), "qty": str(qty), "notional": float(notional),
                "fee": float(fees), "realized_gross": float(gross),
                "slippage_vs_4h": float(price / positive(close_price) - 1),
                "slippage_bps": float((price / positive(close_price) - 1) * 10000)}

    def reconcile_intent(self):
        """Read-only resolution. An uncertain intent is NEVER sent again."""
        intent = self.state["intent"]
        if not intent:
            return
        order = self.api.order(intent["client_id"])
        self.validate_order(order, intent["client_id"], intent["kind"], intent["qty"])
        metrics = self.fill_metrics(self.api.fills(order_id=order["orderId"]),
                                    intent["qty"], order, Decimal(str(intent["decision"]["close"])))
        positions = self.api.positions()
        if self.api.orders():
            raise Blocked("Pending orders after mutation")
        state = deepcopy(self.state)
        if intent["kind"] == "OPEN":
            if len(positions) != 1:
                raise Blocked("Opening position not confirmed")
            pos = positions[0]
            if (pos.get("symbol") != trend.SYMBOL or pos.get("side") != "LONG" or
                    pos.get("positionMode") != "ONE_WAY" or finite(pos.get("leverage")) != 1 or
                    positive(pos.get("qty")) != positive(intent["qty"]) or
                    int(pos["ctime"]) < intent["sent_at"] or not pos.get("positionId")):
                raise Blocked("New position cannot be proven V8-owned")
            owner = {"position_id": str(pos["positionId"]), "qty": intent["qty"],
                     "client_id": intent["client_id"], "order_id": str(order["orderId"]),
                     "entry_metrics": metrics}
            # Query by position ID as well as order ID: any other fills mean no adoption.
            linked = self.api.fills(position_id=owner["position_id"])
            self.fill_metrics(linked, intent["qty"], order, Decimal(str(intent["decision"]["close"])))
            state["position"] = owner
            metrics.update(funding=float(finite(pos["funding"])),
                           realized_net=metrics["realized_gross"] - metrics["fee"] + float(finite(pos["funding"])))
            message = "V8 REAL LONG OPENED"
        else:
            if positions:
                raise Blocked("Close not verified: BTCUSDT position remains")
            owner = state["position"]
            if owner is None or owner["position_id"] != intent["position_id"]:
                raise Blocked("Closing ownership state missing")
            hist = self.api.history_position(owner["position_id"])
            funding = float(finite(hist["funding"]))
            fills = self.api.fills(position_id=owner["position_id"])
            expected_ids = {owner["order_id"], str(order["orderId"])}
            if {str(f["orderId"]) for f in fills} != expected_ids:
                raise Blocked("Closed position contains unknown trades")
            entry = [f for f in fills if str(f["orderId"]) == owner["order_id"]]
            opened = self.api.order(owner["client_id"])
            self.validate_order(opened, owner["client_id"], "OPEN", owner["qty"])
            entry_metrics = self.fill_metrics(entry, owner["qty"], opened, Decimal("1"))
            exit_fills = [f for f in fills if str(f["orderId"]) == str(order["orderId"])]
            self.fill_metrics(exit_fills, intent["qty"], order, Decimal(str(intent["decision"]["close"])))
            gross = entry_metrics["realized_gross"] + metrics["realized_gross"]
            fees = entry_metrics["fee"] + metrics["fee"]
            metrics.update(funding=funding, fee_total=fees, realized_gross=gross,
                           realized_net=gross - fees + funding)
            state["position"] = None
            message = "V8 REAL POSITION CLOSED"
        state["intent"], state["blocked"] = None, ""
        self.record(message, state, metrics=metrics, decision=intent["decision"],
                    fingerprint=intent["fingerprint"], shadow_expected=intent["shadow_expected"])
        self.notify(message)

    def process(self, decision, shadow_event):
        self.recover()
        if self.state["intent"]:
            try:
                self.reconcile_intent()
            except Exception:
                self.notify("V8 REAL BLOCKED — unresolved order; read-only reconciliation required")
                return
        if decision["candle_time"] <= self.state["last_candle"]:
            return
        self.context = (decision, shadow_event)
        state = deepcopy(self.state)
        previous = state["last_target"]
        try:
            identity = self.check_shadow(decision, shadow_event)
            self.gate()
            equity, account, rules, price = self.preflight(require_leverage=False)
            kind = None
            if decision["direction"] == "FLAT" and state["position"]:
                kind = "CLOSE"
            elif decision["direction"] == "LONG" and previous == "FLAT" and not state["position"]:
                kind = "OPEN"
            if kind:
                if kind == "OPEN":
                    nominal = equity * self.exposure * (1 - self.reserve)
                    step = Decimal(1).scaleb(-int(rules["basePrecision"]))
                    quantity = (nominal / price).quantize(step, rounding=ROUND_DOWN)
                    self.valid_qty(quantity, rules)
                    if quantity * price > equity * self.exposure or quantity * price * (1 + self.reserve) > positive(account["available"]):
                        raise Blocked("Exposure or cash reserve exceeded")
                    if finite(self.api.leverage()) != 1:
                        self.preflight(require_leverage=False)
                        self.api.set_leverage_one()  # fixed 1, never inherits V7 leverage
                    self.preflight()  # verify 1x and ownership again before the entry
                else:
                    quantity = self.valid_qty(state["position"]["qty"], rules)
                    self.preflight()  # close never changes leverage on an existing position
                cid = f"igodv8-{decision['candle_time']}-{'o' if kind == 'OPEN' else 'c'}"
                state.update(last_candle=decision["candle_time"], last_target=decision["direction"])
                state["intent"] = {"kind": kind, "qty": str(quantity), "client_id": cid,
                                   "sent_at": self.clock(), "decision": decision, "fingerprint": identity,
                                   "position_id": state["position"]["position_id"] if state["position"] else None,
                                   "shadow_expected": {k: shadow_event[k] for k in (
                                       "equity_net", "pnl_net", "turnover_notional", "turnover_cost")}}
                # Persist BEFORE POST. A crash after this point requires reads, never resubmission.
                self.record("ORDER_INTENT", state, equity_before=float(equity),
                            target_notional=float(equity * self.exposure) if kind == "OPEN" else 0,
                            exposure=float(self.exposure), reserve_fraction=float(self.reserve),
                            quoted_price=float(price))
                self.preflight()
                if kind == "OPEN":
                    self.api.open_long(str(quantity), cid)
                else:
                    self.api.close_long(str(quantity), cid)
                self.reconcile_intent()
            else:
                state.update(last_candle=decision["candle_time"], last_target=decision["direction"], blocked="")
                self.record("NO_ORDER", state, decision=decision, fingerprint=identity)
        except Exception as exc:
            # Recover a durable intent before recording an error. Otherwise a failed
            # state replacement could overwrite that intent with an older snapshot.
            self.recover()
            # Only our fixed messages can enter the journal; transport errors may contain secrets.
            reason = str(exc) if isinstance(exc, Blocked) else "API/persistence uncertainty"
            state = deepcopy(self.state)
            if not state["intent"]:
                state["last_candle"] = decision["candle_time"]
                if decision["direction"] in ("LONG", "FLAT"):
                    state["last_target"] = decision["direction"]
            state["blocked"] = reason
            self.record("V8 REAL BLOCKED", state, reason=reason)
            self.notify("V8 REAL BLOCKED — " + reason)
        finally:
            self.context = None


def data_directory():
    return Path(os.getenv("V8_DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."))) / "v8"


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--disarm", action="store_true")
    args = parser.parse_args()
    directory = data_directory()
    if args.status:
        print((directory / "igod_v8_live_state.json").read_text(encoding="utf-8"))
        return
    if args.disarm:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "V8_DISARM").write_text("DISARM\n", encoding="utf-8")
        telegram("V8 REAL DISARMED")
        return
    with ExecutionLease() as lease:
        shadow = trend.ShadowCore(directory, float(os.getenv("V8_SHADOW_INITIAL_EQUITY", "1000")))
        shadow.recover()
        executor = LiveExecutor(directory, shadow, lease)
        executor.start()
        public = trend.BitunixReadOnly()
        try:
            while True:
                try:
                    executor.recover()
                    if not executor.enabled() and executor.state["armed_at"] is not None:
                        state = deepcopy(executor.state)
                        state["armed_at"] = None
                        executor.record("V8 REAL DISARMED", state)
                        executor.notify("V8 REAL DISARMED")
                    if executor.state["intent"]:
                        executor.reconcile_intent()  # reads only, even while disarmed
                    now = executor.clock()
                    rows = public.candles(now)
                    shadow.recover()
                    for decision in trend.pending_decisions(rows, now, shadow.state["last_candle"]):
                        shadow.step(decision, {"status": "REAL_WORKER"})
                    # Recover a crash between SHADOW append and REAL consumption without
                    # recalculating a second decision. Old/pre-ARM events remain non-tradable.
                    events = [json.loads(line) for line in shadow.journal.read_text(encoding="utf-8").splitlines()]
                    for event in events:
                        decision = event["decision"]
                        if decision["candle_time"] <= executor.state["last_candle"]:
                            continue
                        executor.notify("V8 SIGNAL " + decision["direction"])
                        executor.process(decision, event)
                except Exception:
                    executor.notify("V8 REAL BLOCKED — cycle uncertainty; no automatic order retry")
                time.sleep(60)
        finally:
            state = deepcopy(executor.state)
            state["armed_at"] = None
            executor.record("V8 REAL DISARMED", state)
            executor.notify("V8 REAL DISARMED")


if __name__ == "__main__":
    run()
