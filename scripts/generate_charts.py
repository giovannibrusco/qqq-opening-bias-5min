"""Regenerate every README chart from the raw QQQ and NQ CSV files.

Run from the repository root after installing the package:

    python scripts/generate_charts.py \
        --qqq data/QQQ_5min_10years_UTC.csv \
        --nq data/nq-10y-1min.csv

The script deliberately computes every plotted value through the packaged
backtest and analysis functions.  No published result is hard-coded here.
Both SVG and 2x PNG variants are written for light and dark GitHub themes.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["svg.hashsalt"] = "qqq-opening-bias"

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

from qqq_opening_bias import (
    BacktestConfig,
    BacktestResult,
    compute_performance,
    equity_curves,
    equity_series,
    load_nq_bars,
    load_qqq_bars,
    per_trade_t_test,
    run_backtest,
    run_placebo,
    slippage_sensitivity,
    yearly_breakdown,
)

COMMISSION = 0.0005
SLIPPAGE = {
    "entry_slippage_per_share": 0.02,
    "additional_stop_slippage_per_share": 0.04,
}
BASE = {"commission_per_share_per_side": COMMISSION}

SCENARIO_LABELS = {
    "replication": "Paper replication\n(no slippage)",
    "slippage": "With $0.02/share\nslippage",
    "nq_filter": "Slippage + NQ\n09:25 filter",
    "placebo": "Slippage + QQQ\n09:25 placebo",
    "buy_hold": "QQQ buy & hold",
}

EQUITY_LABELS = {
    "replication": "Paper (no slippage)",
    "slippage": "Slippage only",
    "nq_filter": "NQ filter",
    "placebo": "QQQ placebo",
    "buy_hold": "Buy & hold",
}


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    foreground: str
    muted: str
    grid: str
    neutral: str
    accent: str
    green: str
    red: str


THEMES = (
    Theme(
        name="light",
        background="#fcfcfb",
        foreground="#0b0b0b",
        muted="#66645f",
        grid="#e1e0d9",
        neutral="#c9c8c1",
        accent="#2a78d6",
        green="#0a8f3c",
        red="#c83b3b",
    ),
    Theme(
        name="dark",
        background="#1a1a19",
        foreground="#ffffff",
        muted="#a09e97",
        grid="#343431",
        neutral="#55534d",
        accent="#3987e5",
        green="#2aad61",
        red="#e05252",
    ),
)


@dataclass(frozen=True)
class ChartData:
    curves: pd.DataFrame
    results: dict[str, BacktestResult]
    metrics: pd.DataFrame
    sensitivity: pd.DataFrame
    yearly_replication: pd.DataFrame
    yearly_nq: pd.DataFrame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qqq", default="data/QQQ_5min_10years_UTC.csv")
    parser.add_argument("--nq", default="data/nq-10y-1min.csv")
    parser.add_argument("--out-dir", default="assets")
    parser.add_argument(
        "--equity-out",
        default="assets/equity_curves.csv",
        help="CSV written from the same freshly computed equity curves",
    )
    parser.add_argument("--start", default=None, help="First session (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Last session (YYYY-MM-DD)")
    parser.add_argument("--dpi", type=int, default=200, help="PNG resolution")
    return parser.parse_args()


def _window(args: argparse.Namespace) -> dict[str, dt.date]:
    bounds: dict[str, dt.date] = {}
    if args.start:
        bounds["start"] = dt.date.fromisoformat(args.start)
    if args.end:
        bounds["end"] = dt.date.fromisoformat(args.end)
    return bounds


def _check_loaded(
    qqq: pd.DataFrame, nq: pd.DataFrame, args: argparse.Namespace
) -> None:
    for name, frame, path in (("QQQ", qqq, args.qqq), ("NQ", nq, args.nq)):
        if frame.empty:
            raise SystemExit(f"No {name} bars found in the requested window: {path}")


def compute_chart_data(
    qqq: pd.DataFrame,
    nq: pd.DataFrame,
) -> ChartData:
    """Run the canonical scenarios once and derive every chart input."""

    results = {
        "replication": run_backtest(qqq, config=BacktestConfig(**BASE)),
        "slippage": run_backtest(
            qqq, config=BacktestConfig(**BASE, **SLIPPAGE)
        ),
        "nq_filter": run_backtest(
            qqq,
            config=BacktestConfig(
                **BASE, **SLIPPAGE, require_nq_confirmation=True
            ),
            nq_bars=nq,
        ),
        "placebo": run_placebo(
            qqq, config=BacktestConfig(**BASE, **SLIPPAGE)
        ),
    }

    curves = equity_curves(qqq, nq, commission=COMMISSION)
    curves = curves.rename(columns={"placebo_qqq925": "placebo"})
    rows: list[dict[str, float | str]] = []
    for key, result in results.items():
        performance = compute_performance(curves[key])
        edge = per_trade_t_test(result)
        rows.append(
            {
                "scenario": key,
                "net_pnl": result.cumulative_pnl,
                "sharpe": performance.sharpe,
                "cagr": performance.cagr,
                "max_drawdown": abs(performance.max_drawdown),
                "pnl_per_share": edge.mean_per_share,
            }
        )

    buy_hold = compute_performance(curves["buy_hold"])
    rows.append(
        {
            "scenario": "buy_hold",
            "net_pnl": curves["buy_hold"].iloc[-1] - curves["buy_hold"].iloc[0],
            "sharpe": buy_hold.sharpe,
            "cagr": buy_hold.cagr,
            "max_drawdown": abs(buy_hold.max_drawdown),
            "pnl_per_share": np.nan,
        }
    )

    return ChartData(
        curves=curves,
        results=results,
        metrics=pd.DataFrame(rows).set_index("scenario"),
        sensitivity=slippage_sensitivity(
            qqq, base_config=BacktestConfig(**BASE)
        ),
        yearly_replication=yearly_breakdown(results["replication"]),
        yearly_nq=yearly_breakdown(results["nq_filter"]),
    )


def _apply_theme(fig: plt.Figure, axes: list[plt.Axes], theme: Theme) -> None:
    fig.patch.set_facecolor(theme.background)
    for ax in axes:
        ax.set_facecolor(theme.background)
        ax.tick_params(colors=theme.muted, labelsize=9)
        ax.xaxis.label.set_color(theme.muted)
        ax.yaxis.label.set_color(theme.muted)
        for spine in ax.spines.values():
            spine.set_visible(False)


def _title(
    fig: plt.Figure,
    theme: Theme,
    heading: str,
    subtitle: str,
) -> None:
    height = float(fig.get_size_inches()[1])
    fig.text(
        0.02,
        1 - 0.10 / height,
        heading,
        color=theme.foreground,
        fontsize=11.5,
        fontweight="bold",
        ha="left",
        va="top",
    )
    fig.text(
        0.02,
        1 - 0.34 / height,
        subtitle,
        color=theme.muted,
        fontsize=8.2,
        ha="left",
        va="top",
    )


def _save(fig: plt.Figure, out_dir: Path, stem: str, theme: Theme, dpi: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {"Creator": "scripts/generate_charts.py", "Date": None}
    svg_path = out_dir / f"{stem}_{theme.name}.svg"
    fig.savefig(
        svg_path,
        facecolor=theme.background,
        metadata=metadata,
    )
    svg = "\n".join(line.rstrip() for line in svg_path.read_text().splitlines())
    svg_path.write_text(f"{svg}\n")
    fig.savefig(
        out_dir / f"{stem}_{theme.name}.png",
        facecolor=theme.background,
        dpi=dpi,
        metadata={"Software": "scripts/generate_charts.py"},
    )
    plt.close(fig)


def _money(value: float, _: float | None = None) -> str:
    sign = "−" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.0f}k"
    return f"{sign}${value:.0f}"


def render_equity(data: ChartData, out_dir: Path, theme: Theme, dpi: int) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    _apply_theme(fig, [ax], theme)
    _title(
        fig,
        theme,
        "Equity curves — $25k account, log scale",
        "The realistic NQ-filtered strategy is shown after slippage; "
        "the replication is the no-slippage ceiling",
    )
    fig.subplots_adjust(left=0.09, right=0.79, top=0.80, bottom=0.14)

    styles = {
        "replication": (theme.neutral, 1.7, 0.9),
        "slippage": (theme.red, 1.5, 0.9),
        "nq_filter": (theme.accent, 2.4, 1.0),
        "placebo": (theme.muted, 1.5, 0.9),
        "buy_hold": (theme.green, 1.8, 0.9),
    }
    for key, (color, width, alpha) in styles.items():
        ax.plot(
            data.curves.index,
            data.curves[key],
            color=color,
            linewidth=width,
            alpha=alpha,
            label=SCENARIO_LABELS[key].replace("\n", " "),
        )

    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator([25_000, 50_000, 100_000, 200_000]))
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", color=theme.grid, linewidth=0.8)
    ax.set_axisbelow(True)

    endpoints = {key: float(data.curves[key].iloc[-1]) for key in styles}
    label_positions: dict[str, float] = {}
    prior_log: float | None = None
    for key, ending in sorted(endpoints.items(), key=lambda item: item[1]):
        position = np.log(ending)
        if prior_log is not None:
            position = max(position, prior_log + 0.30)
        label_positions[key] = float(np.exp(position))
        prior_log = position

    upper_log = np.log(ax.get_ylim()[1])
    overflow = max(np.log(value) for value in label_positions.values()) - upper_log
    if overflow > 0:
        label_positions = {
            key: float(np.exp(np.log(value) - overflow))
            for key, value in label_positions.items()
        }

    for key, (color, _, _) in styles.items():
        ending = endpoints[key]
        multiple = ending / 25_000.0
        ax.annotate(
            f"{EQUITY_LABELS[key]}\n${ending / 1000:.0f}k · {multiple:.1f}x",
            xy=(data.curves.index[-1], ending),
            xycoords="data",
            xytext=(1.015, label_positions[key]),
            textcoords=("axes fraction", "data"),
            color=color,
            fontsize=8.4,
            va="center",
            annotation_clip=False,
            arrowprops={
                "arrowstyle": "-",
                "color": color,
                "linewidth": 0.7,
                "alpha": 0.7,
            },
        )

    _save(fig, out_dir, "equity", theme, dpi)


def render_pnl_stress(
    data: ChartData, out_dir: Path, theme: Theme, dpi: int
) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 2.5))
    _apply_theme(fig, [ax], theme)
    _title(
        fig,
        theme,
        "Net PnL under execution stress",
        "Same signal, escalating cost realism — $25k starting capital, USD",
    )
    fig.subplots_adjust(left=0.34, right=0.94, top=0.72, bottom=0.10)

    keys = ["replication", "slippage", "nq_filter", "placebo"]
    values = [data.metrics.loc[key, "net_pnl"] for key in keys]
    colors = [theme.neutral, theme.neutral, theme.accent, theme.neutral]
    y = np.arange(len(keys))
    ax.barh(y, values, color=colors, height=0.48)
    ax.set_yticks(y, [SCENARIO_LABELS[key].replace("\n", " ") for key in keys])
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.22)
    ax.set_xticks([])
    ax.tick_params(axis="y", colors=theme.muted, length=0)
    for index, value in enumerate(values):
        ax.text(
            value + max(values) * 0.018,
            index,
            f"${value:,.0f}",
            color=theme.foreground,
            fontsize=10.5,
            fontweight="bold",
            va="center",
        )

    _save(fig, out_dir, "pnl_stress", theme, dpi)


def _break_even(sensitivity: pd.DataFrame) -> float:
    values = sensitivity[["entry_slippage", "net_pnl"]].to_numpy(dtype=float)
    for (x0, y0), (x1, y1) in zip(values, values[1:]):
        if y0 == 0:
            return float(x0)
        if y0 > 0 >= y1:
            return float(x0 + (0 - y0) * (x1 - x0) / (y1 - y0))
    return float("nan")


def render_slippage(
    data: ChartData, out_dir: Path, theme: Theme, dpi: int
) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.3))
    _apply_theme(fig, [ax], theme)
    break_even = _break_even(data.sensitivity)
    _title(
        fig,
        theme,
        "Edge vs execution cost",
        "Net PnL as entry slippage sweeps 0–5¢/share "
        f"(stop slippage = 2×) — break-even near {break_even * 100:.1f}¢",
    )
    fig.subplots_adjust(left=0.12, right=0.95, top=0.79, bottom=0.15)

    x = data.sensitivity["entry_slippage"].to_numpy() * 100
    y = data.sensitivity["net_pnl"].to_numpy()
    ax.axhline(0, color=theme.muted, linewidth=1.2)
    ax.grid(axis="y", color=theme.grid, linewidth=0.8)
    ax.plot(x, y, color=theme.accent, linewidth=2.2)
    ax.scatter(
        x,
        y,
        color=np.where(y >= 0, theme.green, theme.red),
        edgecolor=theme.background,
        linewidth=1.5,
        s=38,
        zorder=3,
    )
    if np.isfinite(break_even):
        break_even_cents = break_even * 100
        ax.axvline(
            break_even_cents,
            color=theme.red,
            linewidth=1,
            linestyle=(0, (4, 3)),
        )
        ax.text(
            break_even_cents + 0.08,
            ax.get_ylim()[1] * 0.90,
            f"break-even ≈ {break_even_cents:.1f}¢",
            color=theme.red,
            fontsize=9,
            fontweight="bold",
            va="top",
        )
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax.set_xlabel("entry slippage (¢ / share)")
    ax.set_xlim(float(x.min()), float(x.max()))
    ax.margins(y=0.12)

    ax.annotate(
        f"${y[0]:,.0f}",
        (x[0], y[0]),
        xytext=(8, -14),
        textcoords="offset points",
        color=theme.foreground,
        fontsize=9,
        fontweight="bold",
    )
    ax.annotate(
        f"−${abs(y[-1]):,.0f}" if y[-1] < 0 else f"${y[-1]:,.0f}",
        (x[-1], y[-1]),
        xytext=(-8, -16),
        textcoords="offset points",
        color=theme.foreground,
        fontsize=9,
        fontweight="bold",
        ha="right",
    )

    _save(fig, out_dir, "slippage_sensitivity", theme, dpi)


def render_metrics(data: ChartData, out_dir: Path, theme: Theme, dpi: int) -> None:
    fig = plt.figure(figsize=(9.3, 5.7))
    axes = [
        fig.add_axes((0.25, 0.55, 0.22, 0.25)),
        fig.add_axes((0.74, 0.55, 0.22, 0.25)),
        fig.add_axes((0.25, 0.09, 0.22, 0.25)),
        fig.add_axes((0.74, 0.09, 0.22, 0.25)),
    ]
    _apply_theme(fig, axes, theme)
    first_year = int(data.curves.index.min().year)
    last_year = int(data.curves.index.max().year)
    _title(
        fig,
        theme,
        "Risk-adjusted comparison across scenarios",
        f"Daily-equity metrics, {first_year}–{last_year} — "
        "highlighted: slippage-aware strategy "
        "with NQ confirmation",
    )

    specs = [
        ("sharpe", "Sharpe ratio", lambda value: f"{value:.2f}"),
        ("cagr", "CAGR", lambda value: f"{value:.1%}"),
        (
            "max_drawdown",
            "Max drawdown · lower is better",
            lambda value: f"{value:.1%}",
        ),
        ("pnl_per_share", "Avg PnL per share", lambda value: f"${value:.3f}"),
    ]
    keys = ["replication", "slippage", "nq_filter", "placebo", "buy_hold"]

    for ax, (column, heading, formatter) in zip(axes, specs):
        panel_keys = [
            key for key in keys if np.isfinite(data.metrics.loc[key, column])
        ]
        values = [float(data.metrics.loc[key, column]) for key in panel_keys]
        colors = [
            theme.accent if key == "nq_filter" else theme.neutral
            for key in panel_keys
        ]
        y = np.arange(len(panel_keys))
        ax.barh(y, values, color=colors, height=0.50)
        ax.set_yticks(
            y, [SCENARIO_LABELS[key].replace("\n", " ") for key in panel_keys]
        )
        ax.invert_yaxis()
        ax.tick_params(axis="y", labelsize=7.4, length=0, pad=4)
        ax.set_xticks([])
        ax.set_title(
            heading,
            color=theme.foreground,
            fontsize=10.5,
            fontweight="bold",
            loc="left",
            pad=7,
        )
        upper = max(values) * 1.24
        ax.set_xlim(0, upper if upper > 0 else 1)
        for index, value in enumerate(values):
            ax.text(
                value + upper * 0.018,
                index,
                formatter(value),
                color=theme.foreground,
                fontsize=8.5,
                fontweight="bold",
                va="center",
            )

    _save(fig, out_dir, "metrics", theme, dpi)


def render_yearly(data: ChartData, out_dir: Path, theme: Theme, dpi: int) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.3))
    _apply_theme(fig, [ax], theme)

    years = sorted(
        set(data.yearly_replication.index).union(data.yearly_nq.index)
    )
    replication = data.yearly_replication["net_pnl"].reindex(years, fill_value=0.0)
    nq_filter = data.yearly_nq["net_pnl"].reindex(years, fill_value=0.0)
    rep_concentration = replication.max() / replication.sum()
    nq_concentration = nq_filter.max() / nq_filter.sum()
    _title(
        fig,
        theme,
        "Where the PnL comes from — net PnL by year",
        f"{replication.idxmax()} is {rep_concentration:.0%} of replication PnL "
        f"and {nq_concentration:.0%} of NQ-filtered PnL",
    )
    fig.subplots_adjust(left=0.11, right=0.97, top=0.76, bottom=0.14)

    x = np.arange(len(years))
    width = 0.36
    ax.bar(
        x - width / 2,
        replication,
        width,
        label="Replication (no slippage)",
        color=theme.neutral,
    )
    ax.bar(
        x + width / 2,
        nq_filter,
        width,
        label="NQ 09:25 filter (+slippage)",
        color=theme.accent,
    )
    ax.axhline(0, color=theme.muted, linewidth=1.2)
    ax.grid(axis="y", color=theme.grid, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xticks(x, [str(year) for year in years])
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    legend = ax.legend(
        loc="upper left",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0, 1.02),
        fontsize=8.5,
    )
    for text in legend.get_texts():
        text.set_color(theme.muted)

    _save(fig, out_dir, "yearly_pnl", theme, dpi)


def main() -> None:
    args = parse_args()
    window = _window(args)
    qqq = load_qqq_bars(args.qqq, **window)
    nq = load_nq_bars(args.nq, **window)
    _check_loaded(qqq, nq, args)

    print("Computing canonical scenarios and chart inputs...")
    data = compute_chart_data(qqq, nq)

    equity_out = Path(args.equity_out)
    equity_out.parent.mkdir(parents=True, exist_ok=True)
    data.curves.rename(columns={"placebo": "placebo_qqq925"}).to_csv(equity_out)
    print(f"wrote {equity_out}")

    out_dir = Path(args.out_dir)
    renderers = (
        ("equity", render_equity),
        ("pnl_stress", render_pnl_stress),
        ("slippage_sensitivity", render_slippage),
        ("metrics", render_metrics),
        ("yearly_pnl", render_yearly),
    )
    for theme in THEMES:
        for stem, renderer in renderers:
            renderer(data, out_dir, theme, args.dpi)
            print(f"wrote {stem}_{theme.name}.svg/.png")


if __name__ == "__main__":
    main()
