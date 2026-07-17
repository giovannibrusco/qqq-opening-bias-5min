"""Opening-range-bias backtest engine for QQQ (SSRN 4416622 replication).

Replaces the three copy-pasted notebook loops with a single parameterised
engine, and fixes the data-pipeline issues found in review:

- the replication no longer depends on NQ data availability;
- incomplete sessions are dropped as whole days, never as single bars;
- NQ timestamps are localised DST-safely (ambiguous/nonexistent -> dropped);
- the 09:35 entry bar is verified to exist before indexing past 09:30;
- commissions are modelled ($0.0005/share/side as in the paper).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

SESSION_FIRST = dt.time(9, 25)
SESSION_LAST = dt.time(15, 55)
SIGNAL_TIME = dt.time(9, 30)
ENTRY_TIME = dt.time(9, 35)


# --------------------------------------------------------------------------- data

def _clip_window(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    df = df[(df["day"] >= start) & (df["day"] <= end)]
    df = df[(df["time"] >= SESSION_FIRST) & (df["time"] <= SESSION_LAST)]
    return df.sort_values("date").reset_index(drop=True)


def load_qqq(path: str, start=dt.date(2016, 1, 1), end=dt.date(2023, 2, 17)) -> pd.DataFrame:
    """QQQ 5-min bars, UTC timestamps -> America/New_York (naive)."""
    df = pd.read_csv(path)
    df["date"] = (
        pd.to_datetime(df["date"], utc=True)
        .dt.tz_convert("America/New_York")
        .dt.tz_localize(None)
    )
    df["day"] = df["date"].dt.date
    df["time"] = df["date"].dt.time
    return _clip_window(df, start, end)


def load_nq(path: str, start=dt.date(2016, 1, 1), end=dt.date(2023, 2, 17)) -> pd.DataFrame:
    """NQ 1-min CME bars (Chicago exchange time) -> NY-naive 5-min bars.

    DST transitions are handled explicitly: ambiguous fall-back stamps and
    nonexistent spring-forward stamps become NaT and are dropped rather than
    raising or being silently shifted.
    """
    df = pd.read_csv(path)
    ts = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        format="%d/%m/%Y %H:%M:%S",
    )
    ts = ts.dt.tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT")
    df["date"] = ts.dt.tz_convert("America/New_York").dt.tz_localize(None)
    df = df.dropna(subset=["date"])

    bars = (
        df.sort_values("date")
        .set_index("date")
        .resample("5min")
        .agg({"Open": "first", "High": "max", "Low": "min",
              "Close": "last", "TotalVolume": "sum"})
        .dropna(subset=["Open", "High", "Low", "Close"])
        .reset_index()
        .rename(columns={"Open": "open", "High": "high", "Low": "low",
                         "Close": "close", "TotalVolume": "volume"})
    )
    bars["day"] = bars["date"].dt.date
    bars["time"] = bars["date"].dt.time
    return _clip_window(bars, start, end)


def complete_days(df: pd.DataFrame) -> set:
    """Days with a full regular session: 09:30 and 09:35 bars present and the
    last bar at 15:55 (drops early closes and data holes as whole days)."""
    ok = set()
    for day, g in df.groupby("day"):
        times = set(g["time"])
        if SIGNAL_TIME in times and ENTRY_TIME in times and g["time"].max() == SESSION_LAST:
            ok.add(day)
    return ok


def restrict_to_days(df: pd.DataFrame, days: set) -> pd.DataFrame:
    return df[df["day"].isin(days)].reset_index(drop=True)


def bar_direction_by_day(df: pd.DataFrame, bar_time: dt.time = SESSION_FIRST) -> dict:
    """Sign of (close - open) of the bar at `bar_time`, per day.

    Used as the confirmation signal: NQ's 09:25 bar, or — for the placebo
    test — QQQ's own 09:25 pre-market bar.
    """
    sel = df[df["time"] == bar_time]
    return {
        d: int(np.sign(c - o))
        for d, o, c in zip(sel["day"], sel["open"], sel["close"])
    }


# ----------------------------------------------------------------------- engine

def run_backtest(
    qqq: pd.DataFrame,
    confirm_dir: dict | None = None,
    entry_slippage: float = 0.0,
    stop_slippage: float = 0.0,
    commission: float = 0.0005,
    tp_mult: float = 10.0,
    risk_pct: float = 0.01,
    max_leverage: float = 4.0,
    capital: float = 25_000.0,
) -> pd.DataFrame:
    """One trade per day, evaluated day-by-day (no cross-day index arithmetic).

    Long if the 09:30 bar closes above its open (short if below); skipped on a
    doji or when `confirm_dir` disagrees. Entry at the 09:35 open; stop at the
    09:30 bar's extreme; target at +tp_mult*R; otherwise flat on the 15:55 bar
    close. Stops are checked before targets within a bar (conservative).
    """
    account = capital
    rows = []

    for day, g in qqq.groupby("day", sort=True):
        g = g.reset_index(drop=True)
        sig = g.index[g["time"] == SIGNAL_TIME]
        if len(sig) == 0:
            continue
        i = int(sig[0])
        if i + 1 >= len(g) or g["time"].iloc[i + 1] != ENTRY_TIME:
            continue  # no tradable 09:35 bar -> skip the day entirely

        o, c = g["open"].iloc[i], g["close"].iloc[i]
        if o == c:
            continue
        side = 1 if c > o else -1
        if confirm_dir is not None and confirm_dir.get(day, 0) != side:
            continue

        entry = g["open"].iloc[i + 1]
        stop = g["low"].iloc[i] if side == 1 else g["high"].iloc[i]
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        target = round(entry + side * tp_mult * risk, 2)

        shares = int(min(account * risk_pct / risk, max_leverage * account / entry))
        if shares <= 0:
            continue

        exit_price, reason, slip = g["close"].iloc[-1], "eod", entry_slippage
        for j in range(i + 1, len(g)):
            lo, hi = g["low"].iloc[j], g["high"].iloc[j]
            if side == 1:
                if lo <= stop:
                    exit_price, reason, slip = stop, "stop", slip + stop_slippage
                    break
                if hi >= target:
                    exit_price, reason = target, "target"
                    break
            else:
                if hi >= stop:
                    exit_price, reason, slip = stop, "stop", slip + stop_slippage
                    break
                if lo <= target:
                    exit_price, reason = target, "target"
                    break

        pnl = side * (exit_price - entry) * shares - (slip + 2 * commission) * shares
        account += pnl
        rows.append({
            "day": day, "side": side, "entry": entry, "exit": exit_price,
            "stop": stop, "target": target, "risk": risk, "shares": shares,
            "notional": shares * entry, "reason": reason, "pnl": pnl,
            "pnl_per_share": pnl / shares, "r_multiple": pnl / (risk * shares),
            "account": account,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------- metrics

def equity_curve(trades: pd.DataFrame, trading_days, capital: float = 25_000.0) -> pd.Series:
    """Daily end-of-day equity over all trading days (flat days included)."""
    idx = pd.DatetimeIndex(pd.to_datetime(sorted(set(trading_days))))
    eq = pd.Series(np.nan, index=idx, name="equity")
    if len(trades):
        eq.loc[pd.to_datetime(trades["day"].values)] = trades["account"].values
    eq.iloc[0] = eq.iloc[0] if pd.notna(eq.iloc[0]) else capital
    return eq.ffill().fillna(capital)


def compute_metrics(equity: pd.Series, periods_per_year: int = 252, rf_annual: float = 0.0) -> pd.Series:
    returns = equity.pct_change().dropna()
    rf_daily = (1 + rf_annual) ** (1 / periods_per_year) - 1
    excess = returns - rf_daily
    sd = excess.std(ddof=1)
    sharpe = np.sqrt(periods_per_year) * excess.mean() / sd if sd > 0 else np.nan
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    dd = (equity / equity.cummax() - 1).min()
    return pd.Series({
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": dd,
        "Vol": returns.std(ddof=1) * np.sqrt(periods_per_year),
    })


def trade_tstat(trades: pd.DataFrame, col: str = "pnl_per_share") -> pd.Series:
    """t-stat of the mean per-trade edge (H0: zero edge)."""
    x = trades[col].values
    n = len(x)
    t = x.mean() / (x.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
    return pd.Series({"n": n, "mean": x.mean(), "t_stat": t})


def bootstrap_sharpe_ci(equity: pd.Series, n_boot: int = 5000, ci: float = 0.95,
                        periods_per_year: int = 252, seed: int = 42) -> pd.Series:
    """IID bootstrap CI on the annualised Sharpe of daily returns."""
    r = equity.pct_change().dropna().values
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n_boot):
        s = rng.choice(r, size=len(r), replace=True)
        sd = s.std(ddof=1)
        if sd > 0:
            stats.append(np.sqrt(periods_per_year) * s.mean() / sd)
    lo, hi = np.percentile(stats, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return pd.Series({"sharpe_lo": lo, "sharpe_hi": hi, "ci": ci, "n_boot": n_boot})


def yearly_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    t["year"] = pd.to_datetime(t["day"]).dt.year
    return t.groupby("year").agg(
        trades=("pnl", "size"),
        net_pnl=("pnl", "sum"),
        pnl_per_share=("pnl_per_share", "mean"),
        win_rate=("pnl", lambda s: (s > 0).mean()),
        avg_r=("r_multiple", "mean"),
    )


def slippage_sensitivity(qqq: pd.DataFrame, grid=None, stop_ratio: float = 2.0,
                         trading_days=None, capital: float = 25_000.0, **kw) -> pd.DataFrame:
    """Net PnL / Sharpe / edge as entry slippage sweeps a grid (stop slippage
    scales at `stop_ratio`x, matching the 0.02/0.04 baseline assumption)."""
    if grid is None:
        grid = np.round(np.arange(0.0, 0.051, 0.005), 3)
    days = trading_days if trading_days is not None else qqq["day"].unique()
    out = []
    for s in grid:
        tr = run_backtest(qqq, entry_slippage=s, stop_slippage=stop_ratio * s,
                          capital=capital, **kw)
        eq = equity_curve(tr, days, capital)
        out.append({
            "entry_slippage": s,
            "net_pnl": tr["pnl"].sum() if len(tr) else 0.0,
            "pnl_per_share": tr["pnl_per_share"].mean() if len(tr) else np.nan,
            "sharpe": compute_metrics(eq)["Sharpe"],
        })
    return pd.DataFrame(out)
