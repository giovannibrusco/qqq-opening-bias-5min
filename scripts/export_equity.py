#!/usr/bin/env python3
"""Export the daily equity curves of every scenario to assets/equity_curves.csv.

Reproduces section 3 of notebooks/QQQ_bias_v2.ipynb as a standalone script so
the equity data can be regenerated (and the README chart rebuilt) without a live
Jupyter kernel. Run from the repository root:

    python3 scripts/export_equity.py
"""

import datetime as dt
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import backtest as bt  # noqa: E402

CAPITAL = 25_000.0
SLIP = dict(entry_slippage=0.02, stop_slippage=0.04)


def main() -> None:
    qqq = bt.load_qqq("data/QQQ_5min_10years_UTC.csv")
    nq = bt.load_nq("data/nq-10y-1min.csv")

    qqq_days = bt.complete_days(qqq)
    both_days = qqq_days & bt.complete_days(nq)
    qqq_full = bt.restrict_to_days(qqq, qqq_days)
    qqq_both = bt.restrict_to_days(qqq, both_days)
    nq_both = bt.restrict_to_days(nq, both_days)

    nq_confirm = bt.bar_direction_by_day(nq_both, dt.time(9, 25))
    qqq_confirm = bt.bar_direction_by_day(qqq_full, dt.time(9, 25))

    trades = {
        "replication": bt.run_backtest(qqq_full),
        "slippage": bt.run_backtest(qqq_full, **SLIP),
        "nq_filter": bt.run_backtest(qqq_both, confirm_dir=nq_confirm, **SLIP),
        "placebo_qqq925": bt.run_backtest(qqq_full, confirm_dir=qqq_confirm, **SLIP),
    }

    days_full = qqq_full["day"].unique()
    days_both = qqq_both["day"].unique()
    equities = {
        k: bt.equity_curve(v, days_both if k == "nq_filter" else days_full, CAPITAL)
        for k, v in trades.items()
    }

    px = qqq_full.groupby("day")["close"].last()
    bh = CAPITAL * px / px.iloc[0]
    bh.index = pd.to_datetime(bh.index)
    equities["buy_hold"] = bh

    eq_df = pd.DataFrame(equities).sort_index().ffill()
    eq_df.index.name = "date"

    os.makedirs("assets", exist_ok=True)
    out = "assets/equity_curves.csv"
    eq_df.to_csv(out)
    print(f"wrote {out}  shape={eq_df.shape}")
    print(eq_df.tail(3).round(0).to_string())


if __name__ == "__main__":
    main()
