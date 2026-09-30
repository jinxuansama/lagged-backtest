import unittest

from lagged_backtest.core import backtest, moving_average_signals


class BacktestTests(unittest.TestCase):
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]

    def test_default_signal_executes_one_close_later(self):
        report = backtest(self.dates, [100, 200, 300, 300], [1, 0, 0, 0], cost_bps=0)
        self.assertEqual([r["position"] for r in report["rows"]], [0, 0, 1, 0])
        self.assertAlmostEqual(report["metrics"]["total_return"], 0.5)

    def test_no_signal_earns_no_return(self):
        result = backtest(self.dates, [100, 200, 50, 150], [0]*4)
        self.assertEqual(result["metrics"]["total_return"], 0)
        self.assertIsNone(result["metrics"]["sharpe_zero_risk_free"])

    def test_cost_on_entry_and_exit(self):
        r = backtest(self.dates, [100]*4, [1, 0, 0, 0], cost_bps=100)
        self.assertAlmostEqual(r["rows"][-1]["equity"], 0.99**2)
        self.assertEqual(r["metrics"]["total_turnover"], 2)

    def test_partial_weight_drift_rebalances(self):
        r = backtest(self.dates, [100, 100, 200, 200], [0.5]*4, cost_bps=0)
        self.assertAlmostEqual(r["rows"][2]["equity"], 1.5)
        self.assertAlmostEqual(r["rows"][3]["turnover"], 1/6)

    def test_buyhold_matches_lag1_without_costs(self):
        r = backtest(self.dates, [100, 90, 110, 121], [1]*4, lag=1, cost_bps=0)
        self.assertAlmostEqual(r["rows"][-1]["equity"], 1.21)
        self.assertAlmostEqual(r["metrics"]["max_drawdown"], -0.1)

    def test_future_change_does_not_change_past(self):
        a_prices, b_prices = [100, 110, 120, 130], [100, 110, 120, 1]
        a = backtest(self.dates, a_prices, moving_average_signals(a_prices, 2))
        b = backtest(self.dates, b_prices, moving_average_signals(b_prices, 2))
        self.assertEqual(a["rows"][:3], b["rows"][:3])

    def test_trailing_signal_warmup_and_tie(self):
        self.assertEqual(moving_average_signals([1, 2, 3, 3], 3), [0, 0, 1, 1])
        self.assertEqual(moving_average_signals([2, 2], 2), [0, 0])

    def test_duplicate_dates_rejected(self):
        with self.assertRaises(ValueError):
            backtest(["2026-01-01"]*2, [1, 2], [0, 1])

    def test_invalid_inputs_rejected(self):
        for prices, signals in (([1, 0], [0, 1]), ([1, float("nan")], [0, 1]), ([1, 2], [0, 2]), ([1, 2], [True, 0])):
            with self.subTest(prices=prices, signals=signals), self.assertRaises(ValueError):
                backtest(self.dates[:2], prices, signals)

    def test_zero_lag_and_excessive_cost_rejected(self):
        for options in ({"lag": 0}, {"cost_bps": 10000}, {"periods_per_year": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                backtest(self.dates[:2], [1, 2], [0, 1], **options)

    def test_terminal_liquidation_not_added(self):
        r = backtest(self.dates, [100]*4, [1]*4, cost_bps=100)
        self.assertAlmostEqual(r["rows"][-1]["equity"], 0.99)

    def test_lag_exceeds_history(self):
        r = backtest(self.dates, [1, 2, 3, 4], [1]*4, lag=10)
        self.assertEqual(r["metrics"]["total_return"], 0)


if __name__ == "__main__":
    unittest.main()
