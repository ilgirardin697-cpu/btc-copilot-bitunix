from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import ast
import tempfile
import unittest
from unittest.mock import patch

from execution_guard import ExecutionLease, v7_mutation_guard
import trend_v8 as trend
from v8_bitunix import BitunixV8
from v8_executor import Blocked, LiveExecutor


class FakeBitunix:
    def __init__(self, clock):
        self.clock, self.gate = clock, lambda: None
        self.lever = 1
        self.sticky_leverage = False
        self.price_value = "10000"
        self.equity = "200"
        self.mode = "ONE_WAY"
        self.position_rows, self.pending = [], []
        self.order_rows, self.trade_rows, self.history = {}, [], {}
        self.mutations, self.reads = [], []
        self.timeout_after_send = False
        self.timeout_before_send = False
        self.rules_row = {"symbol": "BTCUSDT", "symbolStatus": "OPEN", "isApiSupported": True,
                          "minLeverage": 1, "basePrecision": 6, "minTradeVolume": "0.000001",
                          "maxMarketOrderVolume": "100"}

    def account(self):
        self.reads.append("account")
        return {"available": self.equity, "frozen": "0", "margin": "0", "crossUnrealizedPNL": "0",
                "isolationUnrealizedPNL": "0", "positionMode": self.mode}

    def leverage(self):
        self.reads.append("leverage")
        return self.lever

    def set_leverage_one(self):
        self.gate()
        self.mutations.append(("leverage", 1))
        if not self.sticky_leverage:
            self.lever = 1

    def positions(self):
        self.reads.append("positions")
        return deepcopy(self.position_rows)

    def orders(self):
        self.reads.append("orders")
        return deepcopy(self.pending)

    def rules(self):
        return self.rules_row

    def price(self):
        return self.price_value

    def order(self, client_id):
        self.reads.append("order:" + client_id)
        if client_id not in self.order_rows:
            raise Blocked("Order not found; ambiguous result")
        return deepcopy(self.order_rows[client_id])

    def fills(self, position_id=None, order_id=None):
        self.reads.append("fills")
        return deepcopy([r for r in self.trade_rows if
                         (position_id is None or r["positionId"] == position_id) and
                         (order_id is None or r["orderId"] == order_id)])

    def history_position(self, position_id):
        return self.history[position_id]

    def trade(self, qty, cid, close):
        self.gate()
        self.mutations.append(("close" if close else "open", qty, cid))
        if self.timeout_before_send:
            raise TimeoutError("secret must never appear")
        oid = str(len(self.order_rows) + 1)
        order = {"clientId": cid, "orderId": oid, "symbol": "BTCUSDT", "status": "FILLED",
                 "side": "SELL" if close else "BUY", "reduceOnly": close,
                 "positionMode": "ONE_WAY", "leverage": 1, "tradeQty": qty}
        self.order_rows[cid] = order
        pid = "owned-position"
        gross = Decimal(qty) * (Decimal(self.price_value) - Decimal("10000")) if close else Decimal(0)
        self.trade_rows.append({**order, "tradeId": "fill-" + oid, "positionId": pid, "qty": qty,
                                "price": self.price_value, "fee": str(Decimal(qty) * Decimal(self.price_value) * Decimal("0.0006")),
                                "realizedPNL": str(gross)})
        if close:
            self.position_rows = []
            self.history[pid] = {"positionId": pid, "funding": "-0.01"}
        else:
            self.position_rows = [{"positionId": pid, "qty": qty, "side": "LONG", "symbol": "BTCUSDT",
                                   "positionMode": "ONE_WAY", "leverage": 1, "funding": "0",
                                   "ctime": self.clock(), "avgOpenPrice": self.price_value}]
        if self.timeout_after_send:
            raise TimeoutError("secret must never appear")
        return {"orderId": oid, "clientId": cid}

    def open_long(self, qty, cid):
        return self.trade(qty, cid, False)

    def close_long(self, qty, cid):
        return self.trade(qty, cid, True)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"V8_LIVE_EXECUTION": "true", "V8_LIVE_EXPOSURE": "0.25",
                                           "V8_LIVE_RESERVE": "0.002", "V8_SHADOW_TURNOVER_COST": "0.001",
                                           "LIVE_EXECUTION": "true", "LIVE_AUTO_START": "true"})
        self.env.start()
        self.lease = ExecutionLease(self.folder / "locks").__enter__()
        self.rows = [{"time": i * trend.FOUR_HOURS, "close": 10000} for i in range(300)]
        self.now = 300 * trend.FOUR_HOURS + 1500
        self.shadow = trend.ShadowCore(self.folder)
        self.api = FakeBitunix(lambda: self.now)
        self.messages = []
        self.executor = self.make_executor()
        self.executor.start()
        # Initial historical FLAT establishes baseline but cannot submit before ARM.
        decision = trend.signal(self.rows, self.now)
        event = self.shadow.step(decision, {})
        self.executor.process(decision, event)

    def tearDown(self):
        self.lease.__exit__()
        self.env.stop()
        self.tmp.cleanup()

    def make_executor(self):
        executor = LiveExecutor(self.folder, self.shadow, self.lease, api=self.api,
                                clock=lambda: self.now, notify=self.messages.append)
        self.api.gate = executor.gate
        return executor

    def next_signal(self, price=11000):
        self.rows.append({"time": len(self.rows) * trend.FOUR_HOURS, "close": price})
        self.now += trend.FOUR_HOURS
        decision = trend.signal(self.rows, self.now)
        return decision, self.shadow.step(decision, {})

    def enter(self):
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        self.assertIsNotNone(self.executor.state["position"], self.executor.state["blocked"])
        return decision, event

    def test_disabled_zero_mutations_even_with_v7_live_flags(self):
        decision, event = self.next_signal()
        with patch.dict(os.environ, {"V8_LIVE_EXECUTION": "false"}):
            self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_execution_defaults_false(self):
        decision, event = self.next_signal()
        with patch.dict(os.environ):
            os.environ.pop("V8_LIVE_EXECUTION", None)
            self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_short_impossible(self):
        decision, event = self.next_signal()
        decision = dict(decision, direction="SHORT")
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_025_exposure_200_equity_is_4990_not_margin(self):
        self.enter()
        quantity = Decimal(self.executor.state["position"]["qty"])
        self.assertEqual(quantity * Decimal("10000"), Decimal("49.9"))
        self.assertLessEqual(quantity * Decimal("10000"), Decimal("50"))

    def test_wrong_leverage_blocks(self):
        self.api.lever, self.api.sticky_leverage = 20, True
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [("leverage", 1)])
        self.assertIsNone(self.executor.state["position"])

    def test_leverage_configures_one_and_verifies_before_entry(self):
        self.api.lever = 20
        self.enter()
        self.assertEqual(self.api.mutations[0], ("leverage", 1))
        self.assertEqual(len([m for m in self.api.mutations if m[0] == "open"]), 1)
        self.assertEqual(self.api.lever, 1)

    def test_manual_position_blocks(self):
        self.api.position_rows = [{"positionId": "manual", "qty": "0.01"}]
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_old_before_arm_blocks(self):
        decision, event = self.next_signal()
        self.now += 1
        self.executor.start()
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_duplicate_candle_no_second_order(self):
        decision, event = self.enter()
        self.executor.process(decision, event)
        self.assertEqual(len(self.api.mutations), 1)

    def test_fingerprint_mismatch_blocks(self):
        decision, event = self.next_signal()
        self.executor.process(decision, dict(event, fingerprint="wrong"))
        self.assertEqual(self.api.mutations, [])

    def test_valid_long_exactly_one_order(self):
        self.enter()
        self.assertEqual([m[0] for m in self.api.mutations], ["open"])
        self.assertTrue(self.api.mutations[0][2].startswith("igodv8-"))
        self.assertIn("V8 REAL LONG OPENED", self.messages)

    def test_valid_flat_exactly_one_reduce_only_close(self):
        self.enter()
        owned_qty = self.executor.state["position"]["qty"]
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        self.assertEqual([m[0] for m in self.api.mutations], ["open", "close"])
        self.assertEqual(self.api.mutations[-1][1], owned_qty)
        closing = list(self.api.order_rows.values())[-1]
        self.assertEqual(closing["side"], "SELL")
        self.assertTrue(closing["reduceOnly"])
        self.assertIsNone(self.executor.state["position"])

    def test_flat_without_position_zero_mutations(self):
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_timeout_after_order_reconciles_without_resubmission(self):
        self.api.timeout_after_send = True
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        self.assertIsNotNone(self.executor.state["intent"])
        reads_before = len(self.api.reads)
        self.executor.process(decision, event)
        self.assertIsNone(self.executor.state["intent"])
        self.assertIsNotNone(self.executor.state["position"])
        self.assertGreater(len(self.api.reads), reads_before)
        self.assertEqual(len(self.api.mutations), 1)
        self.assertNotIn("secret must never appear", self.executor.journal.read_text())

    def test_uncertain_absent_order_is_never_retried(self):
        self.api.timeout_before_send = True
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        for _ in range(3):
            self.executor.process(decision, event)
        self.assertEqual(len(self.api.mutations), 1)
        self.assertIsNotNone(self.executor.state["intent"])

    def test_restart_does_not_duplicate(self):
        decision, event = self.enter()
        restarted = self.make_executor()
        restarted.start()
        restarted.process(decision, event)
        self.assertEqual(len(self.api.mutations), 1)
        self.assertIsNotNone(restarted.state["position"])

    def test_restart_recovers_uncertain_fill_read_only(self):
        self.api.timeout_after_send = True
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        restarted = self.make_executor()
        restarted.start()
        restarted.process(decision, event)
        self.assertIsNone(restarted.state["intent"])
        self.assertEqual(len(self.api.mutations), 1)

    def test_real_fees_funding_slippage_and_shadow_expected_recorded(self):
        self.enter()
        self.api.price_value = "9500"
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        journal = [json.loads(line) for line in self.executor.journal.read_text().splitlines()]
        metrics = journal[-1]["metrics"]
        quantity = Decimal("0.00499")
        gross = quantity * Decimal("-500")
        fees = quantity * Decimal("19500") * Decimal("0.0006")
        self.assertAlmostEqual(metrics["fill_price"], 9500)
        self.assertAlmostEqual(metrics["fee_total"], float(fees))
        self.assertAlmostEqual(metrics["funding"], -0.01)
        self.assertAlmostEqual(metrics["realized_gross"], float(gross))
        self.assertAlmostEqual(metrics["realized_net"], float(gross - fees) - 0.01)
        self.assertAlmostEqual(metrics["slippage_vs_4h"], 9500 / 9000 - 1)
        self.assertEqual(journal[-1]["fingerprint"], event["fingerprint"])
        self.assertEqual(journal[-1]["shadow_expected"]["pnl_net"], event["pnl_net"])

    def test_external_fill_or_quantity_change_prevents_close(self):
        self.enter()
        self.api.position_rows[0]["qty"] = "0.01"
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        self.assertEqual(len(self.api.mutations), 1)

    def test_external_fill_same_qty_prevents_close(self):
        self.enter()
        external = deepcopy(self.api.trade_rows[0])
        external.update(orderId="manual-order", tradeId="external-fill")
        self.api.trade_rows.append(external)
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        self.assertEqual(len(self.api.mutations), 1)

    def test_orphan_order_or_hedge_or_bad_equity_blocks(self):
        for field, value in (("pending", [{"orderId": "manual"}]), ("mode", "HEDGE"), ("equity", "nan")):
            previous = getattr(self.api, field)
            setattr(self.api, field, value)
            decision, event = self.next_signal(9000)
            self.executor.process(decision, event)
            setattr(self.api, field, previous)
        self.assertEqual(self.api.mutations, [])

    def test_disarm_file_prevents_all_mutations(self):
        decision, event = self.next_signal()
        self.executor.disarm_path.write_text("DISARM")
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_bootstrap_long_no_real_entry_or_late_hold_entry(self):
        decision, event = self.next_signal()
        self.executor.start()  # ARM after this LONG close
        self.executor.process(decision, event)
        decision, event = self.next_signal(12000)
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_durable_shadow_event_required(self):
        decision, event = self.next_signal()
        self.shadow.journal.write_text("")
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_missing_execution_lock_blocks(self):
        self.lease.__exit__()
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_partial_fill_does_not_retry_or_adopt(self):
        self.api.timeout_after_send = True
        decision, event = self.next_signal()
        self.executor.process(decision, event)
        order = next(iter(self.api.order_rows.values()))
        order["status"] = "PART_FILLED"
        self.executor.process(decision, event)
        self.assertIsNone(self.executor.state["position"])
        self.assertIsNotNone(self.executor.state["intent"])
        self.assertEqual(len(self.api.mutations), 1)

    def test_changed_equity_before_post_fails_closed(self):
        decision, event = self.next_signal()
        original = self.executor.record
        def record(*args, **kwargs):
            original(*args, **kwargs)
            if args[0] == "ORDER_INTENT":
                self.api.equity = "100"
        with patch.object(self.executor, "record", side_effect=record):
            self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])
        self.assertIsNotNone(self.executor.state["intent"])

    def test_intrabar_and_stale_candles_block(self):
        decision, event = self.next_signal()
        self.now = decision["candle_time"] + trend.FOUR_HOURS - 1
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])
        decision, event = self.next_signal(9000)
        self.executor.process(decision, event)
        decision, event = self.next_signal(11000)
        self.now += 300_000
        self.executor.process(decision, event)
        self.assertEqual(self.api.mutations, [])

    def test_no_averaging_or_exposure_increase_on_hold(self):
        self.enter()
        quantity = self.executor.state["position"]["qty"]
        self.api.equity = "100"
        decision, event = self.next_signal(12000)
        self.executor.process(decision, event)
        self.assertEqual(self.executor.state["position"]["qty"], quantity)
        self.assertEqual(len(self.api.mutations), 1)

    def test_persistent_state_write_failure_recovers_without_duplication(self):
        decision, event = self.next_signal()
        original = self.executor.write_state
        fail_once = [True]
        def save(state):
            if fail_once[0] and state["intent"]:
                fail_once[0] = False
                raise OSError("disk error")
            original(state)
        with patch.object(self.executor, "write_state", side_effect=save):
            self.executor.process(decision, event)
        restarted = self.make_executor()
        restarted.start()
        restarted.process(decision, event)
        self.assertEqual(self.api.mutations, [])
        self.assertIsNotNone(restarted.state["intent"])

    def test_state_journal_mismatch_fails_closed(self):
        saved = json.loads(self.executor.path.read_text())
        saved["last_target"] = "LONG"
        self.executor.path.write_text(json.dumps(saved))
        with self.assertRaises(Blocked):
            self.make_executor()
        self.assertEqual(self.api.mutations, [])

    def test_missing_real_journal_fails_closed(self):
        # Preserve file but model truncation/missing journal content.
        self.executor.journal.write_text("")
        with self.assertRaises(Blocked):
            self.make_executor()
        self.assertEqual(self.api.mutations, [])


class AdapterAndLeaseTests(unittest.TestCase):
    def test_transport_never_opens_short_or_uses_leverage_above_one(self):
        api = BitunixV8(lambda: None)
        with patch.dict(os.environ, {"V8_LIVE_EXECUTION": "true"}), patch.object(api.transport, "open") as network:
            for side, reduce in (("SELL", False), ("BUY", True)):
                with self.assertRaises(PermissionError):
                    api._request("POST", "trade/place_order", body={"symbol": "BTCUSDT", "side": side,
                                 "reduceOnly": reduce, "qty": "1", "orderType": "MARKET", "clientId": "igodv8-test"})
            for leverage in (0, 2, 20, 50):
                with self.assertRaises(PermissionError):
                    api._request("POST", "account/change_leverage", body={"symbol": "BTCUSDT", "marginCoin": "USDT", "leverage": leverage})
            with self.assertRaises(PermissionError):
                api._request("POST", "trade/flash_close_position", body={})
            network.assert_not_called()

    def test_reduce_only_wire_payload_and_fixed_leverage(self):
        api = BitunixV8(lambda: None)
        api.key, api.secret = "test", "test"
        with patch.dict(os.environ, {"V8_LIVE_EXECUTION": "true"}), patch.object(api.transport, "open") as network:
            network.return_value.__enter__.return_value.read.return_value = b'{"code":0,"data":{}}'
            api.open_long("0.001", "igodv8-open")
            api.close_long("0.001", "igodv8-close")
            api.set_leverage_one()
            bodies = [json.loads(call.args[0].data) for call in network.call_args_list]
            self.assertEqual(bodies[0]["side"], "BUY")
            self.assertFalse(bodies[0]["reduceOnly"])
            self.assertEqual(bodies[1]["side"], "SELL")
            self.assertTrue(bodies[1]["reduceOnly"])
            self.assertEqual(bodies[2]["leverage"], 1)

    def test_disabled_transport_gate_prevents_network(self):
        def disabled():
            raise Blocked("disabled")
        api = BitunixV8(disabled)
        with patch.dict(os.environ, {"V8_LIVE_EXECUTION": "true"}), patch.object(api.transport, "open") as network:
            for method, args in ((api.open_long, ("1", "igodv8-o")),
                                 (api.close_long, ("1", "igodv8-c")), (api.set_leverage_one, ())):
                with self.assertRaises(Blocked):
                    method(*args)
            network.assert_not_called()

    def test_adapter_itself_defaults_to_no_mutations(self):
        api = BitunixV8(lambda: None)
        with patch.dict(os.environ), patch.object(api.transport, "open") as network:
            os.environ.pop("V8_LIVE_EXECUTION", None)
            with self.assertRaises(PermissionError):
                api.open_long("1", "igodv8-test")
            network.assert_not_called()

    def test_actual_v7_transport_has_mutation_guard(self):
        tree = ast.parse(Path("live_auto.py").read_text(encoding="utf-8"))
        guarded = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "request"]
        self.assertEqual(len(guarded), 1)
        self.assertTrue(any(isinstance(d, ast.Name) and d.id == "v7_mutation_guard"
                            for d in guarded[0].decorator_list))

    def test_v7_reads_work_but_all_mutations_block_while_v8_lease_held(self):
        class V7Stub:
            @v7_mutation_guard
            def request(self, method, path):
                return "called"
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"V8_EXECUTION_LOCK_DIR": folder,
                                                                             "V8_LIVE_EXECUTION": "false"}):
            with ExecutionLease():
                self.assertEqual(V7Stub().request("GET", "account"), "called")
                with self.assertRaises(RuntimeError):
                    V7Stub().request("POST", "place_order")
                with self.assertRaises(RuntimeError):
                    V7Stub().request("POST", "change_leverage")
            self.assertEqual(V7Stub().request("POST", "place_order"), "called")

    def test_second_process_cannot_acquire_execution_lease(self):
        with tempfile.TemporaryDirectory() as folder, ExecutionLease(folder):
            code = "from execution_guard import ExecutionLease; import sys; ExecutionLease(sys.argv[1]).__enter__()"
            child = subprocess.run([sys.executable, "-c", code, folder], capture_output=True, text=True)
            self.assertNotEqual(child.returncode, 0)
            self.assertIn("Execution locked", child.stderr)


if __name__ == "__main__":
    unittest.main()
