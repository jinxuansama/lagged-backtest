import argparse
import csv
import json
import sys
from pathlib import Path

from .core import from_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit-lag, long/cash research backtest")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--window", type=int, help="generate trailing moving-average signals")
    parser.add_argument("--lag", type=int, default=2)
    parser.add_argument("--cost-bps", type=float, default=10)
    parser.add_argument("--periods-per-year", type=float, default=252)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = from_csv(args.csv, window=args.window, lag=args.lag, cost_bps=args.cost_bps,
                          periods_per_year=args.periods_per_year)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    except (OSError, UnicodeError, ValueError, csv.Error, OverflowError) as exc:
        print(f"lagged-backtest: {exc}", file=sys.stderr)
        return 2
