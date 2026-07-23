"""Run the three documented QQQ opening-bias scenarios."""

from __future__ import annotations

import argparse

import pandas as pd

from qqq_opening_bias import (
    BacktestConfig,
    align_bars,
    compute_performance,
    equity_series,
    load_nq_bars,
    load_qqq_bars,
    run_backtest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qqq", required=True, help="Path to QQQ 5-minute CSV")
    parser.add_argument("--nq", required=True, help="Path to NQ 1-minute CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    qqq, nq = align_bars(load_qqq_bars(args.qqq), load_nq_bars(args.nq))
    trading_dates = pd.to_datetime(qqq["date"]).dt.normalize().unique()

    scenarios = {
        "Replication before costs": BacktestConfig(),
        "Static slippage": BacktestConfig(
            entry_slippage_per_share=0.02,
            additional_stop_slippage_per_share=0.04,
        ),
        "Static slippage plus NQ confirmation": BacktestConfig(
            entry_slippage_per_share=0.02,
            additional_stop_slippage_per_share=0.04,
            require_nq_confirmation=True,
        ),
    }

    rows = []
    for name, config in scenarios.items():
        result = run_backtest(qqq, config=config, nq_bars=nq)
        performance = compute_performance(equity_series(result, trading_dates))
        rows.append(
            {
                "scenario": name,
                "trades": len(result.trades),
                "cumulative_pnl": result.cumulative_pnl,
                "average_shares": result.average_shares,
                "mean_pnl_per_share": result.mean_pnl_per_share,
                "sharpe": performance.sharpe,
                "cagr": performance.cagr,
                "max_drawdown": performance.max_drawdown,
                "volatility": performance.volatility,
            }
        )

    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(pd.DataFrame(rows).set_index("scenario").round(4))


if __name__ == "__main__":
    main()
