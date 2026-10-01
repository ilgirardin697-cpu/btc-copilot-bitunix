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
            self.assertEqual(first["target_notional"], 1000)
            self.assertAlmostEqual(core.state["qty"] * 101, 1000)
            self.assertIsNone(core.step(v8.signal(rows, now), {}))
            restarted = v8.ShadowCore(folder)
            rows.append({"time": 300 * v8.FOUR_HOURS, "close": 90})
            event = restarted.step(v8.signal(rows, now + v8.FOUR_HOURS), {})
            self.assertEqual(event["action"], "SIMULATED_FLAT")
            self.assertEqual(restarted.state["qty"], 0)
            self.assertAlmostEqual(restarted.state["realized_gross"], 1000 / 101 * (90 - 101))
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


if __name__ == "__main__":
    unittest.main()
