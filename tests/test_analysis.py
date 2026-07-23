from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from qqq_opening_bias import (
    BacktestConfig,
    bootstrap_sharpe_ci,
    per_trade_t_test,
    run_backtest,
    run_placebo,
    slippage_sensitivity,
    trades_frame,
    yearly_breakdown,
)


def _two_sessions() -> pd.DataFrame:
    """Two bullish long-winning sessions on consecutive days."""

    def day(d: str, base: float) -> list[dict]:
        return [
            {"date": f"{d} 09:25:00", "open": base - 0.2, "high": base + 0.1,
             "low": base - 0.3, "close": base},                # bullish pre-market (placebo)
            {"date": f"{d} 09:30:00", "open": base, "high": base + 0.5,
             "low": base - 1.0, "close": base + 0.5},          # bullish signal
            {"date": f"{d} 09:35:00", "open": base + 0.5, "high": base + 0.6,
             "low": base + 0.4, "close": base + 0.5},          # entry
            {"date": f"{d} 09:40:00", "open": base + 0.5, "high": base + 20.0,
             "low": base + 0.4, "close": base + 3.0},          # hits +10R target
            {"date": f"{d} 15:55:00", "open": base + 3.0, "high": base + 3.2,
             "low": base + 2.8, "close": base + 3.0},
        ]

    return pd.DataFrame(day("2024-01-02", 100.0) + day("2024-01-03", 101.0))


def _nq_confirm(days: list[str], directions: list[int]) -> pd.DataFrame:
    rows = []
    for d, sign in zip(days, directions):
        o, c = (100.0, 100.5) if sign > 0 else (100.5, 100.0)
        rows.append({"date": f"{d} 09:25:00", "open": o, "high": max(o, c) + 1,
                     "low": min(o, c) - 1, "close": c})
    return pd.DataFrame(rows)


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = run_backtest(_two_sessions())

    def test_trades_frame_shape_and_columns(self) -> None:
        frame = trades_frame(self.result)
        self.assertEqual(len(frame), 2)
        self.assertIn("pnl_per_share", frame.columns)
        self.assertIn("r_multiple", frame.columns)

    def test_t_test_positive_for_winning_edge(self) -> None:
        edge = per_trade_t_test(self.result)
        self.assertEqual(edge.n, 2)
        self.assertGreater(edge.mean_per_share, 0)

    def test_t_test_handles_single_trade(self) -> None:
        one = run_backtest(_two_sessions().iloc[:4].reset_index(drop=True))
        edge = per_trade_t_test(one)
        self.assertEqual(edge.n, 1)
        self.assertTrue(np.isnan(edge.t_stat))

    def test_bootstrap_ci_is_ordered(self) -> None:
        equity = pd.Series(
            [25_000, 25_500, 26_010, 25_800, 26_500, 27_000],
            index=pd.date_range("2024-01-01", periods=6, freq="D"),
        )
        lo, hi = bootstrap_sharpe_ci(equity, n_boot=500)
        self.assertLessEqual(lo, hi)

    def test_yearly_breakdown_groups_by_year(self) -> None:
        table = yearly_breakdown(self.result)
        self.assertIn(2024, table.index)
        self.assertEqual(int(table.loc[2024, "trades"]), 2)

    def test_slippage_sensitivity_is_monotone_non_increasing(self) -> None:
        grid = np.array([0.0, 0.02, 0.04])
        table = slippage_sensitivity(_two_sessions(), grid=grid)
        pnl = table["net_pnl"].to_numpy()
        self.assertTrue(np.all(np.diff(pnl) <= 1e-9))

    def test_placebo_uses_qqq_own_bar(self) -> None:
        # QQQ signal is bullish; a bullish 09:30 bar is its own confirmation,
        # so the placebo keeps both trades.
        placebo = run_placebo(_two_sessions(), config=BacktestConfig())
        self.assertEqual(len(placebo.trades), 2)

    def test_nq_filter_rejects_disagreeing_day(self) -> None:
        bars = _two_sessions()
        nq = _nq_confirm(["2024-01-02", "2024-01-03"], [1, -1])  # 2nd day disagrees
        result = run_backtest(
            bars, config=BacktestConfig(require_nq_confirmation=True), nq_bars=nq
        )
        self.assertEqual(len(result.trades), 1)


if __name__ == "__main__":
    unittest.main()
