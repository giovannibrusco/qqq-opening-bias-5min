# Figure map — what has to be updated together

Every published number is a maintenance obligation. This file lists each headline
figure and **every place it appears**, so that when results change nothing is
left contradicting something else.

Counts below were produced by grepping `README.md` and `assets/*.svg`. Charts are
generated, so a chart figure is edited in the generator, not in the SVG.

## Regenerating

Numbers originate from one command:

```bash
python scripts/run_analysis.py --qqq data/QQQ_5min_10years_UTC.csv --nq data/nq-10y-1min.csv
python scripts/export_equity.py            # refreshes assets/equity_curves.csv
```

Charts are then rebuilt from those outputs and re-rendered to PNG. **The chart
generators are not currently in the repo** — they live outside it, which means a
figure change requires regenerating charts by hand. *(Open item: vendor the
generators into `scripts/` so charts are reproducible like everything else.)*

## The map

| Figure | Value | Appears in |
|---|---|---|
| Replication net PnL | $138,639 | README ×4 (TL;DR-adjacent text, results table, "edge inside the spread" paragraph, 2 chart alt texts) · charts: cost ladder, slippage sensitivity (endpoint label) |
| Slippage net PnL | $4,860 | README ×2 (results table, chart alt text) · chart: cost ladder |
| NQ-filter net PnL | $44,332 | README ×2 (results table, chart alt text) · chart: cost ladder |
| Placebo net PnL | $25,191 | README ×2 (results table, chart alt text) · chart: cost ladder |
| Trade count | 1,775 | README ×4 (TL;DR, results table ×2 rows, "the replication is exact") |
| NQ-filter trade count | 844 | README (results table) |
| **Break-even slippage** | **~2.2¢** | README ×4 (opening questions, TL;DR, headline paragraph) · chart: slippage sensitivity (subtitle + dashed marker) · **GitHub repo description** |
| **NQ-filter t-stat** | **2.05** | README ×3 (TL;DR, results table, "more than a momentum proxy") · chart: metrics · **GitHub repo description** |
| **2022 concentration** | **76%** | README ×2 (TL;DR, "single-regime phenomenon") · chart: per-year PnL (subtitle) · **GitHub repo description** |
| NQ-filter edge | $0.125/share | README ×3 (TL;DR, results table, findings) · chart: metrics |
| Placebo edge / t-stat | $0.079 / 1.27 | README ×2 · chart: metrics |
| Replication Sharpe | 1.06 | README ×3 (TL;DR, results table, findings) · chart: metrics |
| NQ-filter Sharpe | 0.77 | README ×2 · chart: metrics |
| Buy & hold Sharpe | 0.72 | README ×2 · chart: metrics |
| Bootstrap CIs | [0.05, 1.41] / [−0.03, 1.47] | README (findings §3) — **depends on `bootstrap_sharpe_ci(seed=42)`**; changing the seed changes published numbers |
| Equity endpoints | $164k·6.5x / $69k·2.8x / $69k·2.7x / $50k·2.0x / $30k·1.2x | equity chart labels · README hero alt text |
| Exit-reason mix | ~2–3% / ~75% / ~22% | README (strategy rules paragraph) |
| Paper's own figures | 1,795 trades · Sharpe 1.12 | README ×2 (TL;DR, findings) — **static**, from SSRN 4416622; never changes with a re-run |

## Highest-risk items

Three figures are duplicated **outside the repository**, in the GitHub repo
description, where nothing will flag them as stale:

- break-even **~2.2¢/share**
- NQ-filter **t = 2.05**
- **76%** of PnL from 2022

If a re-run moves any of these, the repo description must be edited by hand in
the GitHub UI.

**Rename-dependent URLs.** Three references hard-code the repository name and
must be updated together if it changes again: the CI badge and its link in the
README, and `Repository` in `pyproject.toml`. README *images* use relative paths
and survive a rename untouched.

## Wording that is also a claim

- **"no slippage"**, not "no costs" / "cost-free": the paper's $0.0005/side
  commission *is* modelled in every scenario. Only slippage is zero in the
  replication row.
- **EoD exits** carry no *exit slippage*; commission still applies on both sides.
- Anything under **Roadmap → Open** must not appear in the description, badges,
  topics or TL;DR as though it were done.
