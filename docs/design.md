# Timing and arithmetic

For the interval from close t-1 to close t, target weight is
`w_t = signal[t-lag]` if that index exists, and zero otherwise. Initial
wealth is one and initial holdings are cash. At default lag=2, the trade
for signal k takes place at close k+1; the position earns interval k+1→k+2.

| Quantity | Formula |
| --- | --- |
| Asset return | r_t = P_t / P_(t-1) - 1 |
| Previous drifted end weight | h_(t-1) |
| Turnover | u_t = abs(w_t - h_(t-1)) |
| Fee fraction | f_t = u_t × cost_bps / 10000 |
| Gross portfolio return | g_t = w_t × r_t |
| Net portfolio return | n_t = (1-f_t) × (1+g_t) - 1 |
| Wealth | V_t = V_(t-1) × (1+n_t) |
| Drifted end weight | h_t = w_t × (1+r_t) / (1+g_t) |

Fees reduce wealth proportionally before the interval. Turnover is measured
against the drifted pretrade fraction; target allocation occurs after fees.
This is an abstract accounting convention, not an exchange fill simulator.
There is no forced terminal sale. Buy-and-hold is `P_t / P_0` without costs,
so it is a labelled frictionless baseline, not a like-for-like net strategy.

All post-initial intervals, including initial cash intervals, enter metrics.
Annualized return is `exp(log(V_last)*periods_per_year/N)-1`; annualized
volatility is sample standard deviation × sqrt(periods_per_year); Sharpe
assumes zero risk-free rate. Undefined values are null. Drawdown includes
the initial wealth point. N is the number of return intervals, not rows.

The moving-average signal is one when the current price is strictly above
the mean of the last `window` closes, zero otherwise. Incomplete windows
produce zero; all inputs come from the current or earlier rows.

Dates must increase strictly, prices must be finite and positive, weights
finite in [0,1], lag an integer ≥1, and cost_bps in [0,10000). Irregular bars
are permitted; the caller chooses an appropriate annualization assumption.
Input signal causality, adjusted prices, and data provenance remain the
caller's responsibility. Future-shock regression tests verify that the
built-in signal generator and backtester preserve historical prefixes.
