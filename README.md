# Lagged Backtest

**A small backtester whose signal timing and trading costs are inspectable.**

[中文说明](README.zh-CN.md) · [Timing and mathematics](docs/design.md) · [Contributing](CONTRIBUTING.md)

A dependency-free, single-asset long/cash research backtester. It applies an
explicit signal lag, proportional trading costs, and rebalancing turnover
from drifted holdings. Each output row records the signal index, position,
turnover, cost fraction, return, wealth, and frictionless buy-and-hold baseline.

Default `lag=2`: a signal observed at close t executes at close t+1 and first
earns the return ending at close t+2. This timing avoids granting the strategy
the return before its next-close execution. `lag=1` is an explicitly
optimistic same-close assumption and must be justified by the researcher.

## Quick start

Python 3.10+; no runtime dependencies:

```sh
python -m pip install .
lagged-backtest examples/prices.csv --cost-bps 10
lagged-backtest examples/prices.csv --window 3 --lag 2 --cost-bps 10
python -m unittest discover -s tests -v
```

All sample prices and signals are synthetic, not market data or evidence of
a profitable strategy. The first command uses provided signals. The second
generates strictly trailing moving-average signals. Both report the checked
input's SHA-256 and the exact execution assumptions.

```python
from lagged_backtest.core import backtest
result = backtest(
    ["2026-01-01", "2026-01-02", "2026-01-03"],
    [100, 200, 300], [1, 0, 0], lag=2, cost_bps=0,
)
assert result["metrics"]["total_return"] == 0.5
```

The strategy earns no 100→200 return: its first position starts at the second
close and earns 200→300. Metrics include total return, annualized return and
sample volatility, zero-risk-free Sharpe, maximum drawdown, and turnover.
Annualization uses the explicitly assumed bar frequency (252 by default),
not elapsed calendar time. Undefined Sharpe/volatility return JSON `null`.

`--output report.json` saves the full deterministic report; `--periods-per-year`
changes the frequency assumption. CLI exits 0 on success and 2 on invalid input.

## Research scope

This controls execution timing; it **cannot detect future information already
embedded in user-provided signals**. Supplied signals are labelled unverified.
It has no corporate-action handling, tax, borrow fees, market impact, risk-free
interest, intraday execution, or final liquidation. Fractional positions are
abstract target weights in [0,1]; repeated targets rebalance drift each bar.
Fees are charged proportionally against wealth before each earning interval.
Use appropriately adjusted, rights-cleared prices for real research.

Initial version 0.1.0, MIT licensed. AI assisted development and testing.
No live trading support or performance claims. [Roadmap](docs/roadmap.md).
