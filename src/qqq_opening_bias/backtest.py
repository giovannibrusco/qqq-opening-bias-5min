"""Event-driven backtest for the documented QQQ opening-bias rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Literal

import pandas as pd

Direction = Literal["long", "short"]
ExitReason = Literal["stop", "target", "session_close"]

SIGNAL_TIME = time(9, 30)
ENTRY_TIME = time(9, 35)
NQ_CONFIRMATION_TIME = time(9, 25)
SESSION_END = time(15, 55)


@dataclass(frozen=True)
class BacktestConfig:
    """Parameters that define one backtest scenario."""

    initial_equity: float = 25_000.0
    risk_fraction: float = 0.01
    leverage_cap: float = 4.0
    reward_to_risk: float = 10.0
    entry_slippage_per_share: float = 0.0
    additional_stop_slippage_per_share: float = 0.0
    commission_per_share_per_side: float = 0.0
    require_nq_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if not 0 < self.risk_fraction <= 1:
            raise ValueError("risk_fraction must be in (0, 1]")
        if self.leverage_cap <= 0 or self.reward_to_risk <= 0:
            raise ValueError("leverage_cap and reward_to_risk must be positive")
        if min(
            self.entry_slippage_per_share,
            self.additional_stop_slippage_per_share,
            self.commission_per_share_per_side,
        ) < 0:
            raise ValueError("cost assumptions cannot be negative")


@dataclass(frozen=True)
class Trade:
    """One completed intraday trade."""

    session_date: pd.Timestamp
    direction: Direction
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    shares: int
    exit_reason: ExitReason
    gross_pnl: float
    costs: float
    net_pnl: float
    equity_after: float

    @property
    def pnl_per_share(self) -> float:
        return self.net_pnl / self.shares


@dataclass(frozen=True)
class BacktestResult:
    """Backtest output and convenience statistics."""

    config: BacktestConfig
    trades: tuple[Trade, ...]

    @property
    def final_equity(self) -> float:
        if not self.trades:
            return self.config.initial_equity
        return self.trades[-1].equity_after

    @property
    def cumulative_pnl(self) -> float:
        return self.final_equity - self.config.initial_equity

    @property
    def average_shares(self) -> float:
        if not self.trades:
            return 0.0
        return sum(trade.shares for trade in self.trades) / len(self.trades)

    @property
    def mean_pnl_per_share(self) -> float:
        if not self.trades:
            return 0.0
        return sum(trade.pnl_per_share for trade in self.trades) / len(self.trades)


def _prepare_bars(bars: pd.DataFrame, label: str) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"{label} is missing required columns: {sorted(missing)}")

    prepared = bars.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared = prepared.sort_values("date").reset_index(drop=True)

    if prepared["date"].duplicated().any():
        raise ValueError(f"{label} contains duplicate timestamps")
    if prepared[list(required - {"date"})].isna().any().any():
        raise ValueError(f"{label} contains missing OHLC values")
    if (prepared["high"] < prepared["low"]).any():
        raise ValueError(f"{label} contains bars with high below low")

    prepared["session_date"] = prepared["date"].dt.normalize()
    prepared["clock_time"] = prepared["date"].dt.time
    return prepared


def _row_at(session: pd.DataFrame, clock_time: time) -> pd.Series | None:
    rows = session.loc[session["clock_time"] == clock_time]
    if rows.empty:
        return None
    return rows.iloc[0]


def _direction(open_price: float, close_price: float) -> Direction | None:
    if close_price > open_price:
        return "long"
    if close_price < open_price:
        return "short"
    return None


def _position_size(
    equity: float,
    entry_price: float,
    risk_per_share: float,
    config: BacktestConfig,
) -> int:
    risk_budget_size = equity * config.risk_fraction / risk_per_share
    leverage_size = config.leverage_cap * equity / entry_price
    return max(0, int(min(risk_budget_size, leverage_size)))


def run_backtest(
    qqq_bars: pd.DataFrame,
    config: BacktestConfig | None = None,
    nq_bars: pd.DataFrame | None = None,
) -> BacktestResult:
    """Run the opening-bias backtest.

    The implementation follows the rules documented in the original notebook:
    one trade per eligible session, entry at the 09:35 QQQ open, stop-first
    treatment when a single bar touches both levels, and a same-session close.
    """

    config = config or BacktestConfig()
    qqq = _prepare_bars(qqq_bars, "qqq_bars")

    nq = None
    if config.require_nq_confirmation:
        if nq_bars is None:
            raise ValueError("nq_bars is required when NQ confirmation is enabled")
        nq = _prepare_bars(nq_bars, "nq_bars")

    equity = config.initial_equity
    completed: list[Trade] = []

    nq_sessions = (
        {day: frame for day, frame in nq.groupby("session_date", sort=True)}
        if nq is not None
        else {}
    )

    for session_date, session in qqq.groupby("session_date", sort=True):
        signal_bar = _row_at(session, SIGNAL_TIME)
        entry_bar = _row_at(session, ENTRY_TIME)
        if signal_bar is None or entry_bar is None:
            continue

        direction = _direction(float(signal_bar["open"]), float(signal_bar["close"]))
        if direction is None:
            continue

        if config.require_nq_confirmation:
            nq_session = nq_sessions.get(session_date)
            if nq_session is None:
                continue
            nq_bar = _row_at(nq_session, NQ_CONFIRMATION_TIME)
            if nq_bar is None:
                continue
            nq_direction = _direction(float(nq_bar["open"]), float(nq_bar["close"]))
            if nq_direction != direction:
                continue

        entry_price = float(entry_bar["open"])
        if direction == "long":
            stop_price = float(signal_bar["low"])
            risk_per_share = entry_price - stop_price
            target_price = entry_price + config.reward_to_risk * risk_per_share
        else:
            stop_price = float(signal_bar["high"])
            risk_per_share = stop_price - entry_price
            target_price = entry_price - config.reward_to_risk * risk_per_share

        if risk_per_share <= 0:
            continue

        shares = _position_size(equity, entry_price, risk_per_share, config)
        if shares < 1:
            continue

        path = session.loc[
            (session["date"] >= entry_bar["date"])
            & (session["clock_time"] <= SESSION_END)
        ]
        if path.empty:
            continue

        final_bar = path.iloc[-1]
        exit_price = float(final_bar["close"])
        exit_time = pd.Timestamp(final_bar["date"])
        exit_reason: ExitReason = "session_close"

        for _, bar in path.iterrows():
            if direction == "long":
                stop_hit = float(bar["low"]) <= stop_price
                target_hit = float(bar["high"]) >= target_price
            else:
                stop_hit = float(bar["high"]) >= stop_price
                target_hit = float(bar["low"]) <= target_price

            if stop_hit:
                exit_price = stop_price
                exit_time = pd.Timestamp(bar["date"])
                exit_reason = "stop"
                break
            if target_hit:
                exit_price = target_price
                exit_time = pd.Timestamp(bar["date"])
                exit_reason = "target"
                break

        if direction == "long":
            gross_pnl = (exit_price - entry_price) * shares
        else:
            gross_pnl = (entry_price - exit_price) * shares

        per_share_cost = (
            config.entry_slippage_per_share
            + 2 * config.commission_per_share_per_side
        )
        if exit_reason == "stop":
            per_share_cost += config.additional_stop_slippage_per_share

        costs = per_share_cost * shares
        net_pnl = gross_pnl - costs
        equity += net_pnl

        completed.append(
            Trade(
                session_date=pd.Timestamp(session_date),
                direction=direction,
                entry_time=pd.Timestamp(entry_bar["date"]),
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_price=stop_price,
                target_price=target_price,
                shares=shares,
                exit_reason=exit_reason,
                gross_pnl=gross_pnl,
                costs=costs,
                net_pnl=net_pnl,
                equity_after=equity,
            )
        )

    return BacktestResult(config=config, trades=tuple(completed))
