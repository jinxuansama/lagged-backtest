"""Single-asset, long/cash backtests with explicit close-to-close timing."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import math
import statistics
from pathlib import Path


def _number(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} cannot be boolean")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be numeric") from None
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def moving_average_signals(prices, window=3):
    """Trailing-only signals observed at each close; execution is separate."""
    if type(window) is not int or window < 1:
        raise ValueError("window must be a positive integer")
    clean = [_number(p, "price") for p in prices]
    if any(p <= 0 for p in clean):
        raise ValueError("prices must be positive")
    return [0.0 if i + 1 < window else float(clean[i] > statistics.mean(clean[i-window+1:i+1]))
            for i in range(len(clean))]


def backtest(dates, prices, signals, *, lag=2, cost_bps=10.0, periods_per_year=252):
    """At interval ending t, hold target signal[t-lag], or cash if unavailable.

    Default lag=2: signal at close t executes at close t+1, earns the return
    from close t+1 to close t+2. Lag=1 is an optimistic same-close assumption.
    Rebalance from the drifted previous end weight. Fees reduce portfolio wealth
    proportionally before the interval; cash earns zero, no final liquidation.
    """
    dates, prices, signals = list(dates), list(prices), list(signals)
    if len(dates) != len(prices) or len(prices) != len(signals) or len(prices) < 2:
        raise ValueError("dates, prices, signals need equal lengths of at least two")
    if type(lag) is not int or lag < 1:
        raise ValueError("lag must be an integer >= 1")
    cost_bps = _number(cost_bps, "cost_bps")
    periods_per_year = _number(periods_per_year, "periods_per_year")
    if not 0 <= cost_bps < 10000 or periods_per_year <= 0:
        raise ValueError("cost_bps must be in [0,10000); periods_per_year must be positive")
    try:
        parsed = [dt.date.fromisoformat(d) if isinstance(d, str) else None for d in dates]
    except ValueError:
        raise ValueError("dates must be ISO calendar dates") from None
    if any(d is None for d in parsed) or any(a >= b for a, b in zip(parsed, parsed[1:])):
        raise ValueError("dates must be valid and strictly increasing")
    prices = [_number(p, "price") for p in prices]
    signals = [_number(s, "signal") for s in signals]
    if any(p <= 0 for p in prices) or any(not 0 <= s <= 1 for s in signals):
        raise ValueError("prices must be positive and signals in [0,1]")

    equity, peak, drawdown, end_weight = 1.0, 1.0, 0.0, 0.0
    returns, records = [], []
    total_turnover = 0.0
    for t in range(len(prices)):
        price_ratio = prices[t] / prices[t-1] if t else 1.0
        if not math.isfinite(price_ratio) or price_ratio <= 0:
            raise ValueError("price ratio overflow/underflow; exceeds floating-point range")
        buy_hold_equity = prices[t] / prices[0]
        if not math.isfinite(buy_hold_equity) or buy_hold_equity <= 0:
            raise ValueError("buy-and-hold ratio overflow/underflow; exceeds floating-point range")
        if t == 0:
            position = turnover = fee = gross = net = 0.0
        else:
            position = signals[t-lag] if t >= lag else 0.0
            turnover = abs(position - end_weight)
            fee = turnover * cost_bps / 10000
            gross = position * (price_ratio - 1)
            # Preserve tiny positive ratios that would disappear in 1 + return.
            growth = (1-position) + position * price_ratio
            net_growth = (1-fee) * growth
            net = net_growth - 1
            equity *= net_growth
            if not math.isfinite(equity) or equity <= 0:
                raise ValueError("equity overflow/underflow; rescale input or shorten the run")
            end_weight = position * price_ratio / growth
            # Clamp round-off only; target positions are constrained to [0,1].
            end_weight = min(1.0, max(0.0, end_weight))
            returns.append(net)
            total_turnover += turnover
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
        records.append(dict(date=parsed[t].isoformat(), close=prices[t], signal=signals[t],
                            signal_index=t-lag if t >= lag and t > 0 else None,
                            position=position, turnover=turnover, cost_fraction=fee,
                            gross_return=gross, net_return=net, equity=equity,
                            buy_hold_equity=buy_hold_equity))
    deviation = statistics.stdev(returns) if len(returns) >= 2 else None
    sharpe = statistics.mean(returns) / deviation * math.sqrt(periods_per_year) if deviation else None
    if sharpe is not None and not math.isfinite(sharpe):
        sharpe = None
    volatility = deviation * math.sqrt(periods_per_year) if deviation is not None else None
    if volatility is not None and not math.isfinite(volatility):
        volatility = None
    try:
        annualized = math.expm1(math.log(equity) * periods_per_year / len(returns))
    except OverflowError:
        annualized = None
    if annualized is not None and not math.isfinite(annualized):
        annualized = None
    return dict(version=1, assumptions=dict(lag=lag, cost_bps=cost_bps, periods_per_year=periods_per_year,
                cash_return=0, terminal_liquidation=False, fees="proportional at rebalance", annualization="by bar count"),
                metrics=dict(total_return=equity-1, annualized_return=annualized,
                annualized_volatility=volatility,
                sharpe_zero_risk_free=sharpe, max_drawdown=drawdown,
                total_turnover=total_turnover, return_periods=len(returns)), rows=records)


def from_csv(path, *, window=None, **options):
    path = Path(path)
    blob = path.read_bytes()
    import io
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    required = {"date", "close"} | ({"signal"} if window is None else set())
    if len(set(fields)) != len(fields) or not required <= set(fields):
        raise ValueError(f"CSV requires unique headers including {sorted(required)}")
    records = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in records):
        raise ValueError("CSV row width does not match header width")
    prices = [r["close"] for r in records]
    signals = moving_average_signals(prices, window) if window is not None else [r["signal"] for r in records]
    result = backtest([r["date"] for r in records], prices, signals, **options)
    result["input_sha256"] = hashlib.sha256(blob).hexdigest()
    result["signal_method"] = f"trailing_ma_{window}" if window is not None else "provided_unverified"
    return result
