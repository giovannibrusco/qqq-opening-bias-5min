"""Input loading and timestamp alignment for QQQ and NQ bars."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd

SESSION_START = time(9, 25)
SESSION_END = time(15, 55)


def load_qqq_bars(
    path: str | Path,
    start: date = date(2016, 1, 1),
    end: date = date(2023, 2, 17),
) -> pd.DataFrame:
    """Load QQQ 5-minute bars whose source timestamps are in UTC."""

    bars = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"QQQ file is missing columns: {sorted(missing)}")

    bars["date"] = (
        pd.to_datetime(bars["date"], utc=True)
        .dt.tz_convert("America/New_York")
        .dt.tz_localize(None)
    )
    bars["session_date"] = bars["date"].dt.date
    bars["clock_time"] = bars["date"].dt.time

    keep = (
        bars["session_date"].between(start, end)
        & (bars["clock_time"] >= SESSION_START)
        & (bars["clock_time"] <= SESSION_END)
    )
    return bars.loc[keep].sort_values("date").reset_index(drop=True)


def load_nq_bars(
    path: str | Path,
    start: date = date(2016, 1, 1),
    end: date = date(2023, 2, 17),
) -> pd.DataFrame:
    """Load Central-time NQ 1-minute bars and aggregate them to 5 minutes."""

    raw = pd.read_csv(path)
    required = {"Date", "Time", "Open", "High", "Low", "Close", "TotalVolume"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"NQ file is missing columns: {sorted(missing)}")

    timestamps = pd.to_datetime(
        raw["Date"].astype(str) + " " + raw["Time"].astype(str),
        format="%d/%m/%Y %H:%M:%S",
    )
    raw["date"] = (
        timestamps.dt.tz_localize("America/Chicago")
        .dt.tz_convert("America/New_York")
        .dt.tz_localize(None)
    )

    bars = (
        raw.sort_values("date")
        .set_index("date")
        .resample("5min")
        .agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "TotalVolume": "sum",
            }
        )
        .dropna(subset=["Open", "High", "Low", "Close"])
        .rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "TotalVolume": "volume",
            }
        )
        .reset_index()
    )
    bars["session_date"] = bars["date"].dt.date
    bars["clock_time"] = bars["date"].dt.time

    keep = (
        bars["session_date"].between(start, end)
        & (bars["clock_time"] >= SESSION_START)
        & (bars["clock_time"] <= SESSION_END)
    )
    return bars.loc[keep].sort_values("date").reset_index(drop=True)


def align_bars(
    qqq_bars: pd.DataFrame,
    nq_bars: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align NQ timestamps to QQQ and remove timestamps missing from either set."""

    qqq = qqq_bars.sort_values("date").drop_duplicates("date").set_index("date")
    nq = nq_bars.sort_values("date").drop_duplicates("date").set_index("date")

    common = qqq.index.intersection(nq.index)
    if common.empty:
        raise ValueError("QQQ and NQ files have no common timestamps")

    qqq = qqq.loc[common].reset_index()
    nq = nq.loc[common].reset_index()
    return qqq, nq
