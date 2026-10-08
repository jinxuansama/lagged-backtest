import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from lagged_backtest.cli import main
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

    def test_tiny_positive_price_ratio_preserves_equity_and_holdings(self):
        r = backtest(self.dates[:3], [1, 1e-17, 1], [1]*3, lag=1, cost_bps=100)
        self.assertTrue(math.isclose(r["rows"][1]["equity"], 0.99e-17, rel_tol=1e-15))
        self.assertTrue(math.isclose(r["rows"][2]["equity"], 0.99, rel_tol=1e-15))
        self.assertEqual(r["rows"][2]["turnover"], 0)

    def test_tiny_positive_price_ratio_preserves_fractional_drift(self):
        r = backtest(self.dates[:3], [1, 1e-17, 1e-17], [0.5, 1e-17, 0],
                     lag=1, cost_bps=0)
        self.assertEqual(r["rows"][2]["turnover"], 0)

    def test_unrepresentable_adjacent_price_ratios_rejected(self):
        for prices in ([1e-308, 1e308], [1e308, 1e-308]):
            with self.subTest(prices=prices), self.assertRaisesRegex(ValueError, "price ratio"):
                backtest(self.dates[:2], prices, [0]*2, cost_bps=0)

    def test_unrepresentable_buy_hold_ratios_rejected(self):
        for prices in ([1e-308, 1, 1e308], [1e308, 1, 1e-308]):
            with self.subTest(prices=prices), self.assertRaisesRegex(ValueError, "buy-and-hold"):
                backtest(self.dates[:3], prices, [0]*3, cost_bps=0)

    def test_overflowing_annualized_metrics_are_null(self):
        r = backtest(self.dates[:3], [1, 1e308, 1e308], [1]*3, lag=1, cost_bps=0)
        self.assertEqual(r["rows"][-1]["equity"], 1e308)
        self.assertIsNone(r["metrics"]["annualized_return"])
        self.assertIsNone(r["metrics"]["annualized_volatility"])
        self.assertTrue(math.isfinite(r["metrics"]["sharpe_zero_risk_free"]))
        json.dumps(r, allow_nan=False)

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


class CliNumericalTests(unittest.TestCase):
    def run_prices(self, prices):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            path.write_text("date,close,signal\n" + "".join(
                f"2026-01-{i:02d},{price},1\n" for i, price in enumerate(prices, 1)),
                encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([str(path), "--lag", "1", "--cost-bps", "0"])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_representable_extreme_prices_emit_strict_json(self):
        for prices in ([1, 1e-17, 1], [1, 1e308, 1e308]):
            with self.subTest(prices=prices):
                code, stdout, stderr = self.run_prices(prices)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(stderr, "")
                report = json.loads(stdout, parse_constant=lambda value: self.fail(value))
                self.assertEqual(report["rows"][-1]["equity"], prices[-1])

    def test_unrepresentable_price_ratios_exit_two_without_json(self):
        for prices, message in (
            ([1e-308, 1e308], "price ratio"),
            ([1e308, 1e-308], "price ratio"),
            ([1e-308, 1, 1e308], "buy-and-hold"),
            ([1e308, 1, 1e-308], "buy-and-hold"),
        ):
            with self.subTest(prices=prices):
                code, stdout, stderr = self.run_prices(prices)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn(message, stderr)


if __name__ == "__main__":
    unittest.main()
