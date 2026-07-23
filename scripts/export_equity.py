"""Export daily equity curves to assets/equity_curves.csv (README hero chart).

Thin wrapper over qqq_opening_bias.equity_curves. Run from the repository root:

    python3 scripts/export_equity.py --qqq data/QQQ_5min_10years_UTC.csv \
                                     --nq  data/nq-10y-1min.csv
"""

from __future__ import annotations

import argparse
import os

from qqq_opening_bias import equity_curves, load_nq_bars, load_qqq_bars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qqq", default="data/QQQ_5min_10years_UTC.csv")
    parser.add_argument("--nq", default="data/nq-10y-1min.csv")
    parser.add_argument("--out", default="assets/equity_curves.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    qqq = load_qqq_bars(args.qqq)
    nq = load_nq_bars(args.nq)

    frame = equity_curves(qqq, nq)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    frame.to_csv(args.out)
    print(f"wrote {args.out}  shape={frame.shape}")
    print(frame.tail(3).round(0).to_string())


if __name__ == "__main__":
    main()
