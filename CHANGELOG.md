# Changelog

## Unreleased

- Preserve small positive price multipliers when computing wealth and drift.
- Reject unrepresentable adjacent and buy-and-hold price ratios explicitly.
- Return null for non-finite annualized metrics so valid reports remain JSON
  serializable; add numerical boundary and CLI regression tests.
- Retry standard deviation with scaled returns when Python 3.10 overflows
  the intermediate variance, preserving finite volatility and Sharpe values.

## 0.1.0 — 2026-09-30

Initial implementation with a Python API, command-line interface,
synthetic examples, regression tests, and a GitHub Actions test workflow.
This is an early release; community adoption has not been measured.
