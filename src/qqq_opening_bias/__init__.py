"""Reusable components for the QQQ opening-bias research project."""

from .backtest import BacktestConfig, BacktestResult, Trade, run_backtest
from .data import align_bars, load_nq_bars, load_qqq_bars
from .metrics import PerformanceMetrics, compute_performance, equity_series

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "PerformanceMetrics",
    "Trade",
    "align_bars",
    "compute_performance",
    "equity_series",
    "load_nq_bars",
    "load_qqq_bars",
    "run_backtest",
]
