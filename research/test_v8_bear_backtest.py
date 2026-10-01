"""Numerical and causality checks; no network used."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import numpy as np

from research import v8_bear_backtest as bt


def bars(closes):
    closes = np.array(closes, dtype=float)
    return np.column_stack((np.arange(len(closes)) * bt.H4, closes,
                            closes + 1, closes - 1, closes, np.ones(len(closes))))


class ResearchTests(unittest.TestCase):
    def test_position_applied_only_next_bar(self):
        data = bars([100, 100, 100])
        data[0, 1] = 50  # huge first candle return cannot belong to first signal
        run = bt.backtest(data, [1, 0, 0], start=0, cost=0)
        np.testing.assert_array_equal(run["weights"], [0, 1, 0])
        self.assertAlmostEqual(run["equity"][-1], 1)

    def test_turnover_entry_exit_and_hold_mathematically(self):
        run = bt.backtest(bars([100] * 5), [1, 1, 0, 0, 0], start=0)
        np.testing.assert_array_equal(run["turnover"], [0, 1, 0, 1, 0])
        self.assertAlmostEqual(run["equity"][-1], (1 - bt.COST) ** 2)
        self.assertAlmostEqual(sum(run["costs"]), 0.001 + 0.999 * 0.001)
        self.assertEqual(len(run["trades"]), 1)
        self.assertAlmostEqual(run["trades"][0]["net_return"], 0.998001 - 1)

    def test_reverse_pays_both_units_not_one(self):
        run = bt.backtest(bars([100] * 4), [1, -1, 0, 0], start=0)
        np.testing.assert_array_equal(run["turnover"], [0, 1, 2, 1])
        self.assertAlmostEqual(run["equity"][-1], 0.999 * 0.998 * 0.999)

    def test_short_025_return_is_quarter_nominal(self):
        data = bars([100, 100, 90])
        data[2, 1] = 100
        data[1, 1] = 100
        run = bt.backtest(data, [-0.25, -0.25, 0], start=0, cost=0)
        self.assertAlmostEqual(run["equity"][-1], 1.025)

    def test_previous_donchian_excludes_current_low_high(self):
        np.testing.assert_allclose(bt.previous_extreme(np.array([5, 4, 3, 2]), 2, True)[2:], [4, 3])
        np.testing.assert_allclose(bt.previous_extreme(np.array([5, 4, 100, 2]), 2, False)[2:], [5, 100])

    def test_every_signal_is_prefix_invariant_no_lookahead(self):
        rng = np.random.default_rng(8)
        data = bars(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 800))))
        for family in "ABCDEFG":
            full = bt.short_signal(data, family)
            for length in (200, 360, 505, 650):
                prefix = bt.short_signal(data[:length], family)
                np.testing.assert_array_equal(full[:length], prefix, err_msg=family)

    def test_daily_signal_waits_for_daily_close_and_next_open(self):
        data = bars([100] * (51 * 6 + 1))
        data[50 * 6 + 5, 4] = 50
        signal = bt.daily_short(data, 50)
        self.assertFalse(np.any(signal[50 * 6:50 * 6 + 5]))
        self.assertTrue(signal[50 * 6 + 5])
        weights = bt.lag_target(-signal.astype(float))
        self.assertEqual(weights[50 * 6 + 5], 0)
        self.assertEqual(weights[51 * 6], -1)

    def test_channels_exit_only_by_prior_upper_channel(self):
        data = bars([100] * 300 + [90, 102, 121])
        data[300, 2] = 120  # previous high retains position despite loss of SMA regime
        for family in ("C", "D"):
            signal = bt.short_signal(data, family)
            self.assertTrue(signal[300])
            self.assertTrue(signal[301])
            self.assertFalse(signal[302])

    def test_long_priority_no_simultaneous_long_short(self):
        long = np.array([True, False, True, False])
        shorts = {"A": np.array([True, True, False, False])}
        systems = dict(bt.portfolios(long, shorts))
        np.testing.assert_array_equal(systems["COMBO_A_0.25"], [1, -0.25, 1, 0])
        self.assertTrue(np.all(np.abs(systems["COMBO_A_1.00"]) <= 1))

    def test_funding_sign_and_settlement_before_new_order(self):
        data = bars([100] * 4)
        funding = {0: 0.01, 2 * bt.H4: 0.01}
        short = bt.backtest(data, [-1] * 4, start=0, cost=0, funding=funding)
        long = bt.backtest(data, [1] * 4, start=0, cost=0, funding=funding)
        self.assertAlmostEqual(short["equity"][-1], 1.01)
        self.assertAlmostEqual(long["equity"][-1], 0.99)
        self.assertEqual(short["funding_costs"][0], 0)

    def test_adverse_funding_only_penalizes_short(self):
        data = bars([100] * 4)
        base = bt.backtest(data, [-0.25] * 4, start=0, cost=0)
        stress = bt.backtest(data, [-0.25] * 4, start=0, cost=0, short_funding_apr=0.25)
        self.assertLess(stress["equity"][-1], base["equity"][-1])
        long = bt.backtest(data, [1] * 4, start=0, cost=0, short_funding_apr=0.25)
        self.assertEqual(long["equity"][-1], 1)

    def test_train_selection_cannot_use_test_results(self):
        rows = [{"system": "V8_LONG_FLAT", "train": {"sharpe": 1, "calmar": 1}, "test": {}}]
        for index, family in enumerate("ABCDEFG"):
            rows.append({"system": f"COMBO_{family}_0.25", "train": {"sharpe": index, "calmar": index},
                         "test": {"sharpe": 1000 - index}})
        selected, _ = bt.select_train(rows)
        changed = deepcopy(rows)
        for row in changed:
            row["test"] = {"sharpe": -999999, "cagr": 999999}
        self.assertEqual(bt.select_train(changed)[0], selected)
        self.assertEqual(selected, ["G", "F"])

    def test_only_small_authorized_neighborhoods(self):
        self.assertEqual(len(list(bt.variants("B"))), 3)
        self.assertEqual(len(list(bt.variants("C"))), 6)
        self.assertEqual(len(list(bt.variants("D"))), 4)
        self.assertEqual(len(list(bt.variants("G"))), 3)
        self.assertEqual(list(bt.variants("E")), [])
        self.assertEqual(len(list(bt.variants("F"))), 3)

    def test_sharpe_drawdown_include_initial_equity(self):
        run = bt.backtest(bars([100] * 4), [1, 0, 0, 0], start=0)
        m = bt.metrics(run)
        self.assertAlmostEqual(m["max_drawdown"], 0.998001 - 1)
        self.assertAlmostEqual(m["total_return"], 0.998001 - 1)

    def test_invalid_exposure_or_bankruptcy_rejected(self):
        with self.assertRaises(ValueError):
            bt.backtest(bars([100] * 3), [2, 0, 0], start=0)
        data = bars([100, 100, 210])
        data[2, 1] = 100
        with self.assertRaises(ValueError):
            bt.backtest(data, [-1] * 3, start=0, cost=0)

    def test_no_private_endpoints_or_orders_allowed(self):
        with patch("research.v8_bear_backtest.requests.get") as network:
            for url in ("https://fapi.binance.com/fapi/v1/order", "https://fapi.bitunix.com/api/v1/futures/account",
                        "https://api.exchange.coinbase.com/accounts"):
                with self.assertRaises(ValueError):
                    bt.public_get(url)
            network.assert_not_called()

    def test_timestamp_microseconds_and_incomplete_candle(self):
        self.assertEqual(bt.timestamp_ms(1735689600000000), 1735689600000)
        rows = [[i * bt.H4, 100, 101, 99, 100, 1, (i + 1) * bt.H4 - 1] for i in range(1002)]
        parsed = bt.validate_bars(rows, 1001 * bt.H4)
        self.assertEqual(len(parsed), 1001)
        self.assertEqual(parsed[-1, 0], 1000 * bt.H4)
        del rows[600]
        with self.assertRaises(ValueError):
            bt.validate_bars(rows, 1001 * bt.H4)


if __name__ == "__main__":
    unittest.main()
