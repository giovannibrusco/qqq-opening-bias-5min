"""Statistical analysis on top of the backtest engine.

These helpers answer the questions the original notebook never asked: is the
per-trade edge distinguishable from zero, does a cross-asset filter add
information beyond the instrument's own pre-open momentum, and where in time
(and at what execution cost) does the edge actually live.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, BacktestResult, run_backtest


def trades_frame(result: BacktestResult) -> pd.DataFrame:
    """Tabulate completed trades with per-trade P&L, per-share P&L and R-multiple."""

    rows = []
    for t in result.trades:
        risk = abs(t.entry_price - t.stop_price) * t.shares
        rows.append(
            {
                "session_date": pd.Timestamp(t.session_date).normalize(),
                "direction": t.direction,
                "shares": t.shares,
                "exit_reason": t.exit_reason,
                "net_pnl": t.net_pnl,
                "pnl_per_share": t.pnl_per_share,
                "r_multiple": t.net_pnl / risk if risk > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class EdgeTest:
    n: int
    mean_per_share: float
    t_stat: float


def per_trade_t_test(result: BacktestResult) -> EdgeTest:
    """One-sample t-test of the mean per-share edge against a zero-edge null."""

    x = np.array([t.pnl_per_share for t in result.trades], dtype=float)
    n = x.size
    if n == 0:
        return EdgeTest(n=0, mean_per_share=0.0, t_stat=float("nan"))
    sd = x.std(ddof=1) if n >= 2 else 0.0
    if n < 2 or sd == 0:
        return EdgeTest(n=n, mean_per_share=float(x.mean()), t_stat=float("nan"))
    t_stat = x.mean() / (sd / np.sqrt(n))
    return EdgeTest(n=n, mean_per_share=float(x.mean()), t_stat=float(t_stat))


def bootstrap_sharpe_ci(
    equity: pd.Series,
    confidence: float = 0.95,
    n_boot: int = 5000,
    periods_per_year: int = 252,
    seed: int = 42,
) -> tuple[float, float]:
    """IID bootstrap confidence interval for the annualised Sharpe of an equity curve."""

    returns = equity.dropna().astype(float).pct_change().dropna().to_numpy()
    if returns.size < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n_boot):
        sample = rng.choice(returns, size=returns.size, replace=True)
        sd = sample.std(ddof=1)
        if sd > 0:
            stats.append(np.sqrt(periods_per_year) * sample.mean() / sd)
    if not stats:
        return (float("nan"), float("nan"))
    lo = (1 - confidence) / 2 * 100
    hi = (1 + confidence) / 2 * 100
    return (float(np.percentile(stats, lo)), float(np.percentile(stats, hi)))


def yearly_breakdown(result: BacktestResult) -> pd.DataFrame:
    """Per-calendar-year trade count, net P&L, per-share edge, win rate and mean R."""

    frame = trades_frame(result)
    if frame.empty:
        return frame
    frame = frame.assign(year=frame["session_date"].dt.year)
    return frame.groupby("year").agg(
        trades=("net_pnl", "size"),
        net_pnl=("net_pnl", "sum"),
        pnl_per_share=("pnl_per_share", "mean"),
        win_rate=("net_pnl", lambda s: float((s > 0).mean())),
        avg_r=("r_multiple", "mean"),
    )


def slippage_sensitivity(
    qqq_bars: pd.DataFrame,
    grid: np.ndarray | None = None,
    stop_ratio: float = 2.0,
    base_config: BacktestConfig | None = None,
) -> pd.DataFrame:
    """Net P&L, per-share edge and Sharpe as entry slippage sweeps a grid.

    Stop slippage scales at ``stop_ratio`` times the entry slippage, matching the
    0.02 / 0.04 baseline assumption. Sharpe is intentionally omitted here (needs a
    trading-date index); callers that want it should build the equity series with
    :func:`qqq_opening_bias.metrics.equity_series`.
    """

    from .metrics import compute_performance, equity_series  # local import avoids cycle

    if grid is None:
        grid = np.round(np.arange(0.0, 0.0501, 0.005), 3)
    base = base_config or BacktestConfig()
    dates = pd.to_datetime(qqq_bars["date"]).dt.normalize().unique()

    rows = []
    for s in grid:
        cfg = BacktestConfig(
            initial_equity=base.initial_equity,
            risk_fraction=base.risk_fraction,
            leverage_cap=base.leverage_cap,
            reward_to_risk=base.reward_to_risk,
            entry_slippage_per_share=float(s),
            additional_stop_slippage_per_share=float(stop_ratio * s),
            commission_per_share_per_side=base.commission_per_share_per_side,
        )
        result = run_backtest(qqq_bars, config=cfg)
        try:
            sharpe = compute_performance(equity_series(result, dates)).sharpe
        except ValueError:
            sharpe = float("nan")
        rows.append(
            {
                "entry_slippage": float(s),
                "net_pnl": result.cumulative_pnl,
                "pnl_per_share": result.mean_pnl_per_share,
                "sharpe": sharpe,
            }
        )
    return pd.DataFrame(rows)


def equity_curves(
    qqq_bars: pd.DataFrame,
    nq_bars: pd.DataFrame,
    initial_equity: float = 25_000.0,
    slippage: dict | None = None,
    commission: float = 0.0005,
) -> pd.DataFrame:
    """Daily equity for every scenario plus buy & hold, indexed by session date.

    Column set matches assets/equity_curves.csv, the source for the README's
    hero equity-curve chart. Commission defaults to the paper's $0.0005/side.
    """

    from .metrics import equity_series  # local import avoids cycle

    slip = slippage or dict(
        entry_slippage_per_share=0.02, additional_stop_slippage_per_share=0.04
    )
    common = dict(initial_equity=initial_equity, commission_per_share_per_side=commission)
    dates = pd.to_datetime(qqq_bars["date"]).dt.normalize().unique()

    results = {
        "replication": run_backtest(qqq_bars, config=BacktestConfig(**common)),
        "slippage": run_backtest(qqq_bars, config=BacktestConfig(**common, **slip)),
        "nq_filter": run_backtest(
            qqq_bars,
            config=BacktestConfig(**common, require_nq_confirmation=True, **slip),
            nq_bars=nq_bars,
        ),
        "placebo_qqq925": run_placebo(
            qqq_bars, config=BacktestConfig(**common, **slip)
        ),
    }
    frame = pd.DataFrame({k: equity_series(r, dates) for k, r in results.items()})

    close = qqq_bars.groupby(pd.to_datetime(qqq_bars["date"]).dt.normalize())["close"].last()
    frame["buy_hold"] = initial_equity * close / close.iloc[0]
    frame.index.name = "date"
    return frame.sort_index().ffill()


def run_placebo(
    qqq_bars: pd.DataFrame,
    config: BacktestConfig,
) -> BacktestResult:
    """Confirmation filter using QQQ's *own* 09:25 pre-market bar instead of NQ.

    Control experiment for the NQ filter: if the NQ result is merely two-bar
    momentum, this placebo matches it. It reuses the engine's confirmation path
    by feeding QQQ back in as the confirmation instrument.
    """

    placebo_config = BacktestConfig(
        initial_equity=config.initial_equity,
        risk_fraction=config.risk_fraction,
        leverage_cap=config.leverage_cap,
        reward_to_risk=config.reward_to_risk,
        entry_slippage_per_share=config.entry_slippage_per_share,
        additional_stop_slippage_per_share=config.additional_stop_slippage_per_share,
        commission_per_share_per_side=config.commission_per_share_per_side,
        require_nq_confirmation=True,
    )
    return run_backtest(qqq_bars, config=placebo_config, nq_bars=qqq_bars)
