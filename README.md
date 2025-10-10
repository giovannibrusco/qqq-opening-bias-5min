# QQQ Opening Range Bias

Replication and extension of the **“QQQ Intraday Bias”** study (SSRN 4416622) with additional execution stress tests. The notebook rebuilds the paper’s 9:30 breakout tactic on QQQ, adds realistic slippage, then coordinates entries with CME NQ futures to restore edge. The goal is to showcase the research process for a prop-trading seat.

## Project Flow
- **Paper replication** — reproduce the published rules to confirm the dataset and sizing logic (1% of equity risk, capped at 4× notional leverage).
- **Execution reality check** — inject \$0.02/share entry slippage and an extra \$0.04/share if the stop is triggered. The unfiltered strategy trades ~1.3k shares per signal; without slippage the curve is overstated.
- **NQ confirmation filter** — require the 09:25 ET NQ 5-minute bar to agree with the QQQ signal before entering at 09:35. The filter halves trade count while lifting per-share economics.

## Strategy Overview
- **Universe & Horizon**: QQQ 5-minute bars (Jan 2016 – Feb 2023), aligned with NQ 5-minute bars built from raw 1-minute CME data.
- **Signal Window**: Evaluate the 09:30 ET bar; trades enter on the 09:35 open.
- **Direction Filter**:
  - Long if the 09:30 QQQ bar closes above its open *and* the prior NQ bar (09:25) closed above its open.
  - Short if both bars close below their opens.
- **Risk Management**:
  - Stop loss at the 09:30 bar low (for longs) or high (for shorts); take-profit at **+10R**, forcing asymmetric payoff.
  - Position size = min(1% equity / \$risk, 4×equity / entry price), matching the capital usage in the paper.
  - Slippage: \$0.02/share on entry; additional \$0.04/share if a stop is hit.
  - Positions are flattened by the next session open if neither stop nor target is reached.

## Backtest Progression
| Scenario | Net PnL (USD) | Trades | Avg Shares | Avg PnL / Share (USD) |
|---------:|--------------:|-------:|-----------:|----------------------:|
| Paper replication (no slippage) | 139,127 | 1,771 | 1,314 | 0.072 |
| With slippage only | 5,068 | 1,771 | 489 | 0.022 |
| Slippage + NQ filter | 45,317 | 844 | 667 | 0.126 |

| Scenario | Sharpe | CAGR | Max Drawdown | Volatility |
|---------:|-------:|-----:|-------------:|-----------:|
| Paper replication (no slippage) | 1.06 | 30.43% | 22.32% | 28.90% |
| With slippage only | 0.24 | 2.80% | 43.19% | 29.26% |
| Slippage + NQ filter | 0.78 | 15.82% | 31.03% | 21.98% |
| QQQ buy & hold | 0.72 | 15.25% | 35.63% | 23.41% |

**Interpretation**:
- The published rules overstate performance because sizing drives >\$300k notional per trade with no execution costs.
- Adding realistic slippage collapses edge and exposes the drawdown profile.
- Coordinating entries with NQ restores a Sharpe of ~0.78, doubles per-share profitability (0.022 ➝ 0.126), and halves the trade count, making the tactic more scalable.

## Data & Preprocessing
- `Data/QQQ_5min_10years_UTC.csv` — 5-minute OHLCV in UTC.
- `Data/nq-10y-1min.csv` — raw 1-minute CME data, resampled to 5-minute bars inside the notebook.
- The notebook converts timestamps to **America/New_York**, removes early-close sessions (506 missing bars), and realigns both instruments to the same 5-minute index before testing.
- `ssrn-4416622.pdf` — reference paper archived with the repo.

## Repository Structure
- `QQQ_bias.ipynb` — full replication, slippage experiment, and NQ-filtered backtest with visual diagnostics.
- `NQ_breakout.ipynb` — complementary futures breakout research used as a regime filter sandbox.
- `requirements.txt` — dependencies used for the notebooks (`pandas`, `numpy`, `matplotlib`, `tqdm`, `nbformat`).
- `Data/` *(local only)* — place the CSV files here before running the notebooks.
- `ssrn-4416622.pdf` — original research inspiration.

## Reproduction Guide
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
jupyter lab
```
Launch `QQQ_bias.ipynb`, ensure the `Data/` directory contains the two CSVs above, and execute the notebook top-to-bottom. Assertions will flag any timestamp misalignment or missing columns.

## Interview Talking Points
1. **Execution realism** — discuss how the slippage assumptions relate to QQQ depth, and how you would migrate toward order-book or micro-price simulations.
2. **Cross-asset confirmation** — the NQ filter shows how futures lead ETF flows; outline other lead-lag or regime signals you would prototype.
3. **Capital efficiency** — extend risk sizing with intraday VAR or broker margin schedules to present return-on-capital instead of nominal PnL.
4. **Edge durability** — stress-test the strategy around macro events (FOMC, CPI) or volatility regimes to demonstrate robustness under prop-style risk reviews.

## Disclaimers
- Historical results do not guarantee future performance; the analysis assumes continuous liquidity and no exchange halts.
- Market data stems from historical downloads; reconcile against proprietary feeds before committing capital.
- The notebook is a research artifact, not a production trading system.
