"""Reusable components for the QQQ opening-bias research project."""

from .analysis import (
    EdgeTest,
    bootstrap_sharpe_ci,
    equity_curves,
    per_trade_t_test,
    run_placebo,
    slippage_sensitivity,
    trades_frame,
    yearly_breakdown,
)
from .backtest import BacktestConfig, BacktestResult, Trade, run_backtest
from .data import align_bars, load_nq_bars, load_qqq_bars
from .metrics import PerformanceMetrics, compute_performance, equity_series

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "EdgeTest",
    "PerformanceMetrics",
    "Trade",
    "align_bars",
    "bootstrap_sharpe_ci",
    "compute_performance",
    "equity_curves",
    "equity_series",
    "load_nq_bars",
    "load_qqq_bars",
    "per_trade_t_test",
    "run_backtest",
    "run_placebo",
    "slippage_sensitivity",
    "trades_frame",
    "yearly_breakdown",
]
