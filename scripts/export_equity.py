"""Export daily equity curves to assets/equity_curves.csv (README hero chart).

Thin wrapper over qqq_opening_bias.equity_curves. Run from the repository root:

    python3 scripts/export_equity.py --qqq data/QQQ_5min_10years_UTC.csv \
                                     --nq  data/nq-10y-1min.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import os

from qqq_opening_bias import equity_curves, load_nq_bars, load_qqq_bars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qqq", default="data/QQQ_5min_10years_UTC.csv")
    parser.add_argument("--nq", default="data/nq-10y-1min.csv")
    parser.add_argument("--out", default="assets/equity_curves.csv")
    parser.add_argument("--start", default=None, help="First session (YYYY-MM-DD); default = loader default")
    parser.add_argument("--end", default=None, help="Last session (YYYY-MM-DD); default = loader default")
    return parser.parse_args()



def _window(args) -> dict:
    """Only override the loaders' defaults when the user supplies a bound."""
    bounds = {}
    if args.start:
        bounds["start"] = dt.date.fromisoformat(args.start)
    if args.end:
        bounds["end"] = dt.date.fromisoformat(args.end)
    return bounds



def _check_loaded(qqq, nq, args) -> None:
    """Fail with a useful message when the date window excludes the data."""
    for name, frame, path in (("QQQ", qqq, args.qqq), ("NQ", nq, args.nq)):
        if frame.empty:
            raise SystemExit(
                f"No {name} bars in range from {path}.\n"
                "The loaders default to the paper's window (2016-01-01 to "
                "2023-02-17); pass --start/--end to analyse a different period, "
                "e.g. --start 2023-02-01 --end 2026-01-01"
            )


def main() -> None:
    args = parse_args()
    window = _window(args)
    qqq = load_qqq_bars(args.qqq, **window)
    nq = load_nq_bars(args.nq, **window)
    _check_loaded(qqq, nq, args)

    frame = equity_curves(qqq, nq)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    frame.to_csv(args.out)
    print(f"wrote {args.out}  shape={frame.shape}")
    print(frame.tail(3).round(0).to_string())


if __name__ == "__main__":
    main()
