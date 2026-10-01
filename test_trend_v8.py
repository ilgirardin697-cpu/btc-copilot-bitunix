import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import trend_v8 as v8


def candles(count=300, last=101):
    rows = [{"time": i * v8.FOUR_HOURS, "close": 100} for i in range(count)]
    rows[-1]["close"] = last
    return rows, count * v8.FOUR_HOURS + 1500


class TrendTests(unittest.TestCase):
    def test_long_flat_equality_and_closed_only(self):
        for price, direction in ((101, "LONG"), (99, "FLAT"), (100, "FLAT")):
            rows, now = candles(last=price)
            rows.append({"time": 300 * v8.FOUR_HOURS, "close": 999999})
            self.assertEqual(v8.signal(rows, now)["direction"], direction)
        rows, now = candles()
        self.assertEqual(v8.signal(rows, now - 1)["candle_time"], rows[-2]["time"])

    def test_insufficient_missing_stale_invalid_and_conflicting(self):
        rows, now = candles()
        variants = [rows[:199], rows[:-1], rows[:20] + rows[21:],
                    rows + [{"time": 0, "close": 200}],
                    rows[:-1] + [{"time": rows[-1]["time"], "close": float("nan")}]]
        for variant in variants:
            with self.assertRaises(ValueError):
                v8.signal(variant, now)

    def test_telemetry_never_changes_sma200(self):
        rows, now = candles(last=110)
        for row in rows[-125:-1]:
            row["close"] = 115
        decision = v8.signal(rows, now)
        self.assertEqual(decision["direction"], "LONG")
        self.assertEqual(decision["comparison"]["125"]["direction"], "FLAT")
        self.assertEqual(set(decision["comparison"]), set(map(str, v8.PERIODS)))
        self.assertEqual(v8.signal(rows[::-1] + rows[:1], now), decision)

    def test_shadow_sizing_restart_close_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            core = v8.ShadowCore(folder)
            rows, now = candles()
            first = core.step(v8.signal(rows, now), {"positions": [{"positionId": "manual"}]})
            self.assertEqual(first["action"], "BOOTSTRAP_LONG")
            self.assertAlmostEqual(first["target_notional"], 1000 / 1.001)
            self.assertAlmostEqual(core.state["qty"] * 101, core.state["equity_net"])
            self.assertIsNone(core.step(v8.signal(rows, now), {}))
            restarted = v8.ShadowCore(folder)
            rows.append({"time": 300 * v8.FOUR_HOURS, "close": 90})
            event = restarted.step(v8.signal(rows, now + v8.FOUR_HOURS), {})
            self.assertEqual(event["action"], "SIMULATED_FLAT")
            self.assertEqual(restarted.state["qty"], 0)
            self.assertAlmostEqual(restarted.state["realized_gross"], 1000 / 1.001 / 101 * (90 - 101))
            self.assertEqual(len(Path(restarted.journal).read_text().splitlines()), 2)

    def test_recovery_after_state_write_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            core = v8.ShadowCore(folder)
            rows, now = candles()
            with patch.object(core, "save", side_effect=OSError):
                with self.assertRaises(OSError):
                    core.step(v8.signal(rows, now), {})
            restored = v8.ShadowCore(folder)
            restored.recover()
            self.assertGreater(restored.state["qty"], 0)
            self.assertIsNone(restored.step(v8.signal(rows, now), {}))

    def test_transport_rejects_every_v7_mutation_before_network(self):
        with patch.dict(os.environ, {"LIVE_EXECUTION": "true", "LIVE_AUTO_START": "true"}):
            api = v8.BitunixReadOnly()
            with patch("trend_v8.urlopen") as network:
                for path in ("trade/place_order", "trade/cancel_orders", "trade/close_positions",
                             "tpsl/place_order", "tpsl/modify_order", "tpsl/position/place_order",
                             "tpsl/position/modify_order", "account/change_leverage"):
                    with self.assertRaises(PermissionError):
                        api.get("/api/v1/futures/" + path, {})
                network.assert_not_called()

    def test_allowed_transport_is_get(self):
        with patch("trend_v8.urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = b'{"code":0,"data":[]}'
            v8.BitunixReadOnly().get("/api/v1/futures/market/kline", {"symbol": "BTCUSDT"})
            self.assertEqual(network.call_args.args[0].get_method(), "GET")

    def test_real_pnl_observation_does_not_mutate_account(self):
        api = v8.BitunixReadOnly()
        api.key, api.secret = "test", "test"
        with patch.object(api, "get", side_effect=[
            {"available": "100", "margin": "20", "crossUnrealizedPNL": "5"},
            [{"positionId": "manual"}], {"positionList": [{"positionId": "old", "funding": "2"}]},
            {"tradeList": [{"realizedPNL": "10", "fee": "-1"}]}]):
            observation = api.observe()
        self.assertEqual(observation["equity_estimate"], 125)
        self.assertEqual(observation["reconciled"][0]["net"], 11)
        self.assertEqual(observation["ownership"], "EXTERNAL_TO_V8")

    def test_live_mode_refused(self):
        with patch.dict(os.environ, {"V8_MODE": "LIVE"}):
            with self.assertRaises(RuntimeError):
                v8.run()

    def test_round_trip_costs_mathematically(self):
        for exit_price in (100, 120, 80):
            with self.subTest(exit_price=exit_price), tempfile.TemporaryDirectory() as folder:
                core = v8.ShadowCore(folder, initial_equity=1000, turnover_cost=0.001)
                def decision(i, price, direction):
                    return {"candle_time": i * v8.FOUR_HOURS, "close": price,
                            "direction": direction, "comparison": {}}
                entry = core.step(decision(0, 100, "LONG"), {})
                quantity = (1000 / 1.001) / 100
                entry_cost = quantity * 100 * 0.001
                hold = core.step(decision(1, 100, "LONG"), {})
                exit_event = core.step(decision(2, exit_price, "FLAT"), {})
                exit_cost = quantity * exit_price * 0.001
                gross = quantity * (exit_price - 100)
                net = gross - entry_cost - exit_cost
                self.assertAlmostEqual(entry["turnover_cost"], entry_cost)
                self.assertEqual(hold["turnover_cost"], 0)
                self.assertAlmostEqual(exit_event["turnover_cost"], exit_cost)
                self.assertAlmostEqual(core.state["costs_accumulated"], entry_cost + exit_cost)
                self.assertAlmostEqual(core.state["equity_net"], 1000 + net)
                self.assertAlmostEqual(core.state["realized_net"], net)
                self.assertAlmostEqual(core.state["pnl_net"], net)
                self.assertAlmostEqual(core.state["pnl_gross"], gross)
                self.assertAlmostEqual(exit_event["pnl_net"], net)

    def test_downtime_replay_matches_realtime_without_lookahead(self):
        rows, now = candles(last=100)  # bootstrap FLAT
        future = [110, 90, 120]  # LONG -> FLAT -> LONG
        with tempfile.TemporaryDirectory() as live_dir, tempfile.TemporaryDirectory() as replay_dir:
            live, delayed = v8.ShadowCore(live_dir), v8.ShadowCore(replay_dir)
            live.replay(rows, now, {})
            delayed.replay(rows, now, {})
            for price in future:
                rows.append({"time": len(rows) * v8.FOUR_HOURS, "close": price})
                now += v8.FOUR_HOURS
                live.replay(rows, now, {})
            restarted = v8.ShadowCore(replay_dir)
            events = restarted.replay(rows, now, {})
            self.assertEqual([e["action"] for e in events],
                             ["SIMULATED_LONG", "SIMULATED_FLAT", "SIMULATED_LONG"])
            self.assertEqual(live.state, restarted.state)
            self.assertEqual(live.journal.read_text(), restarted.journal.read_text())
            quantity = 1000 / 1.001 / 110
            after_exit = quantity * 90 * 0.999
            self.assertAlmostEqual(restarted.state["equity_net"], after_exit / 1.001)
            self.assertEqual(restarted.replay(rows, now, {}), [])

    def test_replay_rejects_gaps_or_missing_warmup_before_mutation(self):
        rows, now = candles(last=100)
        with tempfile.TemporaryDirectory() as folder:
            core = v8.ShadowCore(folder)
            core.replay(rows, now, {})
            baseline = dict(core.state)
            journal = core.journal.read_text()
            rows.extend([{"time": 300 * v8.FOUR_HOURS, "close": 110},
                         {"time": 301 * v8.FOUR_HOURS, "close": 90}])
            for variant in (rows[:250] + rows[251:], rows[102:], rows[:300] + rows[301:]):
                with self.assertRaises(ValueError):
                    core.replay(variant, now + 2 * v8.FOUR_HOURS, {})
                self.assertEqual(core.state, baseline)
                self.assertEqual(core.journal.read_text(), journal)

    def test_full_available_history_replay(self):
        rows, now = candles(count=200, last=100)
        with tempfile.TemporaryDirectory() as folder:
            core = v8.ShadowCore(folder)
            core.replay(rows, now, {})
            for i in range(200, 400):
                rows.append({"time": i * v8.FOUR_HOURS, "close": 110 if i % 2 == 0 else 90})
            events = core.replay(rows, 400 * v8.FOUR_HOURS + 1500, {})
            self.assertEqual(len(events), 200)
            self.assertEqual(core.state["last_candle"], 399 * v8.FOUR_HOURS)

    def test_cost_configuration_and_legacy_state_rejected(self):
        for cost in (-0.001, 1, float("nan")):
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                v8.ShadowCore(folder, turnover_cost=cost)
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"V8_SHADOW_TURNOVER_COST": "0.002"}):
                core = v8.ShadowCore(folder)
                self.assertEqual(core.turnover_cost, 0.002)
                rows, now = candles()
                core.replay(rows, now, {})
            with self.assertRaises(ValueError):
                v8.ShadowCore(folder, turnover_cost=0.001)
            legacy = dict(core.state)
            legacy.pop("schema")
            core.path.write_text(json.dumps(legacy))
            with self.assertRaises(ValueError):
                v8.ShadowCore(folder, turnover_cost=0.002)

    def test_all_bitunix_endpoints_are_get_even_with_live_flags(self):
        with patch.dict(os.environ, {"LIVE_EXECUTION": "true", "LIVE_AUTO_START": "true"}), \
                patch("trend_v8.urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = b'{"code":0,"data":[]}'
            api = v8.BitunixReadOnly()
            api.key, api.secret = "test", "test"
            for path in v8.READ_PATHS:
                api.get(path, {"symbol": "BTCUSDT"})
            self.assertEqual(network.call_count, len(v8.READ_PATHS))
            for call in network.call_args_list:
                request = call.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertIsNone(request.data)

    def test_short_and_skipped_decisions_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            core = v8.ShadowCore(folder)
            rows, now = candles()
            decision = v8.signal(rows, now)
            with self.assertRaises(ValueError):
                core.step(dict(decision, direction="SHORT"), {})
            core.step(decision, {})
            with self.assertRaises(ValueError):
                core.step(dict(decision, candle_time=decision["candle_time"] + 2 * v8.FOUR_HOURS), {})


if __name__ == "__main__":
    unittest.main()
