from __future__ import annotations

import unittest

import pandas as pd

from qqq_opening_bias import BacktestConfig, run_backtest


def qqq_session(
    *,
    signal_open: float = 99.50,
    signal_close: float = 100.00,
    signal_high: float = 100.50,
    signal_low: float = 99.00,
    entry_open: float = 100.00,
    entry_high: float = 100.50,
    entry_low: float = 99.50,
    later_high: float = 111.00,
    later_low: float = 99.50,
    final_close: float = 103.00,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-01-02 09:30:00",
                "open": signal_open,
                "high": signal_high,
                "low": signal_low,
                "close": signal_close,
            },
            {
                "date": "2024-01-02 09:35:00",
                "open": entry_open,
                "high": entry_high,
                "low": entry_low,
                "close": entry_open,
            },
            {
                "date": "2024-01-02 09:40:00",
                "open": entry_open,
                "high": later_high,
                "low": later_low,
                "close": final_close,
            },
            {
                "date": "2024-01-02 15:55:00",
                "open": final_close,
                "high": final_close + 0.25,
                "low": final_close - 0.25,
                "close": final_close,
            },
        ]
    )


def nq_confirmation(open_price: float, close_price: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-01-02 09:25:00",
                "open": open_price,
                "high": max(open_price, close_price) + 1,
                "low": min(open_price, close_price) - 1,
                "close": close_price,
            }
        ]
    )


class BacktestTests(unittest.TestCase):
    def test_long_trade_hits_target(self) -> None:
        result = run_backtest(qqq_session())

        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.shares, 250)
        self.assertAlmostEqual(trade.net_pnl, 2_500.0)

    def test_short_trade_hits_target(self) -> None:
        bars = qqq_session(
            signal_open=100.50,
            signal_close=100.00,
            signal_high=101.00,
            signal_low=99.50,
            entry_open=100.00,
            entry_high=100.50,
            entry_low=99.50,
            later_high=100.50,
            later_low=89.00,
            final_close=97.00,
        )
        result = run_backtest(bars)

        trade = result.trades[0]
        self.assertEqual(trade.direction, "short")
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.shares, 250)
        self.assertAlmostEqual(trade.net_pnl, 2_500.0)

    def test_static_slippage_is_charged_on_stop(self) -> None:
        bars = qqq_session(entry_low=98.50, later_high=100.0, later_low=98.50)
        config = BacktestConfig(
            entry_slippage_per_share=0.02,
            additional_stop_slippage_per_share=0.04,
        )
        result = run_backtest(bars, config=config)

        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "stop")
        self.assertAlmostEqual(trade.gross_pnl, -250.0)
        self.assertAlmostEqual(trade.costs, 15.0)
        self.assertAlmostEqual(trade.net_pnl, -265.0)

    def test_nq_confirmation_rejects_opposite_direction(self) -> None:
        config = BacktestConfig(require_nq_confirmation=True)
        result = run_backtest(
            qqq_session(),
            config=config,
            nq_bars=nq_confirmation(100.0, 99.0),
        )

        self.assertEqual(len(result.trades), 0)

    def test_nq_confirmation_accepts_matching_direction(self) -> None:
        config = BacktestConfig(require_nq_confirmation=True)
        result = run_backtest(
            qqq_session(),
            config=config,
            nq_bars=nq_confirmation(99.0, 100.0),
        )

        self.assertEqual(len(result.trades), 1)

    def test_position_closes_at_session_end(self) -> None:
        bars = qqq_session(later_high=105.0, later_low=99.50, final_close=103.0)
        result = run_backtest(bars)

        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "session_close")
        self.assertAlmostEqual(trade.net_pnl, 750.0)

    def test_stop_has_priority_if_one_bar_touches_both_levels(self) -> None:
        bars = qqq_session(entry_high=111.0, entry_low=98.0)
        result = run_backtest(bars)

        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, "stop")
        self.assertAlmostEqual(trade.net_pnl, -250.0)

    def test_leverage_cap_limits_position_size(self) -> None:
        bars = qqq_session(
            signal_low=99.99,
            signal_high=100.01,
            entry_high=101.0,
            entry_low=99.99,
            later_high=101.0,
            later_low=99.99,
        )
        result = run_backtest(bars)

        self.assertEqual(result.trades[0].shares, 1_000)

    def test_missing_nq_data_raises_when_filter_is_enabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "nq_bars is required"):
            run_backtest(
                qqq_session(),
                config=BacktestConfig(require_nq_confirmation=True),
            )


if __name__ == "__main__":
    unittest.main()
