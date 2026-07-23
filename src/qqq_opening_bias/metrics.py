"""Performance metrics used by the research runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .backtest import BacktestResult


@dataclass(frozen=True)
class PerformanceMetrics:
    sharpe: float
    cagr: float
    max_drawdown: float
    volatility: float


def equity_series(
    result: BacktestResult,
    trading_dates: Iterable[pd.Timestamp],
) -> pd.Series:
    """Create a daily close-to-close equity series from completed trades."""

    dates = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
    dates = dates.sort_values()
    if dates.empty:
        raise ValueError("trading_dates cannot be empty")

    updates = {dates[0]: result.config.initial_equity}
    for trade in result.trades:
        updates[pd.Timestamp(trade.session_date).normalize()] = trade.equity_after

    series = pd.Series(updates, dtype=float).sort_index()
    return series.reindex(dates).ffill()


def compute_performance(
    equity: pd.Series,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    """Compute annualized Sharpe, CAGR, drawdown and volatility."""

    clean = equity.dropna().astype(float)
    if len(clean) < 2 or (clean <= 0).any():
        raise ValueError("equity must contain at least two positive observations")

    returns = clean.pct_change().dropna()
    standard_deviation = returns.std(ddof=1)
    sharpe = (
        np.sqrt(periods_per_year) * returns.mean() / standard_deviation
        if standard_deviation > 0
        else float("nan")
    )

    years = (clean.index[-1] - clean.index[0]).days / 365.25
    cagr = (clean.iloc[-1] / clean.iloc[0]) ** (1 / years) - 1
    drawdown = clean / clean.cummax() - 1
    volatility = standard_deviation * np.sqrt(periods_per_year)

    return PerformanceMetrics(
        sharpe=float(sharpe),
        cagr=float(cagr),
        max_drawdown=float(drawdown.min()),
        volatility=float(volatility),
    )
