"""Reproduce every number and figure in the README from the raw CSVs.

Unlike a naive runner, the replication and slippage scenarios run on the full
set of complete QQQ sessions -- they are NOT pre-intersected with NQ -- so the
paper's trade count (~1,795) is recovered instead of the NQ-conditioned ~1,771.
Only the cross-asset scenarios consult NQ, per-session, inside the engine.
"""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np
import pandas as pd

from qqq_opening_bias import (
    BacktestConfig,
    bootstrap_sharpe_ci,
    compute_performance,
    equity_series,
    load_nq_bars,
    load_qqq_bars,
    per_trade_t_test,
    run_backtest,
    run_placebo,
    slippage_sensitivity,
    yearly_breakdown,
)

COMMISSION = 0.0005  # paper's $0.0005/share/side
SLIPPAGE = dict(entry_slippage_per_share=0.02, additional_stop_slippage_per_share=0.04)
BASE = dict(commission_per_share_per_side=COMMISSION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qqq", required=True, help="Path to QQQ 5-minute CSV")
    parser.add_argument("--nq", required=True, help="Path to NQ 1-minute CSV")
    parser.add_argument("--start", default=None, help="First session (YYYY-MM-DD); default = loader default")
    parser.add_argument("--end", default=None, help="Last session (YYYY-MM-DD); default = loader default")
    parser.add_argument(
        "--equity-out",
        default=None,
        help="Optional path to write daily equity curves as CSV (for the README chart)",
    )
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
    trading_dates = pd.to_datetime(qqq["date"]).dt.normalize().unique()

    results = {
        "Replication (no slippage)": run_backtest(qqq, config=BacktestConfig(**BASE)),
        "With slippage": run_backtest(qqq, config=BacktestConfig(**BASE, **SLIPPAGE)),
        "Slippage + NQ 09:25 filter": run_backtest(
            qqq,
            config=BacktestConfig(**BASE, require_nq_confirmation=True, **SLIPPAGE),
            nq_bars=nq,
        ),
        "Slippage + QQQ 09:25 placebo": run_placebo(
            qqq, config=BacktestConfig(**BASE, **SLIPPAGE)
        ),
    }

    # --- scenario table --------------------------------------------------------
    rows = []
    for name, result in results.items():
        equity = equity_series(result, trading_dates)
        perf = compute_performance(equity)
        edge = per_trade_t_test(result)
        lo, hi = bootstrap_sharpe_ci(equity)
        rows.append(
            {
                "scenario": name,
                "trades": len(result.trades),
                "net_pnl": round(result.cumulative_pnl, 0),
                "pnl_per_share": round(result.mean_pnl_per_share, 4),
                "t_stat": round(edge.t_stat, 2),
                "sharpe": round(perf.sharpe, 2),
                "sharpe_ci": f"[{lo:.2f}, {hi:.2f}]",
                "cagr": round(perf.cagr, 3),
                "max_dd": round(perf.max_drawdown, 3),
            }
        )
    # buy & hold benchmark
    close = qqq.groupby(pd.to_datetime(qqq["date"]).dt.normalize())["close"].last()
    bh = 25_000.0 * close / close.iloc[0]
    bh_perf = compute_performance(bh)
    bh_lo, bh_hi = bootstrap_sharpe_ci(bh)
    rows.append(
        {
            "scenario": "QQQ buy & hold",
            "trades": np.nan,
            "net_pnl": np.nan,
            "pnl_per_share": np.nan,
            "t_stat": np.nan,
            "sharpe": round(bh_perf.sharpe, 2),
            "sharpe_ci": f"[{bh_lo:.2f}, {bh_hi:.2f}]",
            "cagr": round(bh_perf.cagr, 3),
            "max_dd": round(bh_perf.max_drawdown, 3),
        }
    )

    with pd.option_context("display.max_columns", None, "display.width", 200):
        print("\n=== Scenario comparison ===")
        print(pd.DataFrame(rows).set_index("scenario"))

        print("\n=== Per-year breakdown: NQ filter ===")
        print(yearly_breakdown(results["Slippage + NQ 09:25 filter"]).round(3))

        print("\n=== Slippage sensitivity (replication) ===")
        print(
            slippage_sensitivity(qqq, base_config=BacktestConfig(**BASE))
            .round(4)
            .to_string(index=False)
        )

        print("\n=== Exit-reason mix ===")
        mix = {
            name: pd.Series([t.exit_reason for t in r.trades]).value_counts(normalize=True)
            for name, r in results.items()
        }
        print(pd.DataFrame(mix).round(3))

    if args.equity_out:
        from qqq_opening_bias import equity_curves

        equity_curves(qqq, nq).to_csv(args.equity_out)
        print(f"\nwrote {args.equity_out}")


if __name__ == "__main__":
    main()
