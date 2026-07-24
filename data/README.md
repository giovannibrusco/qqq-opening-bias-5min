# 📁 Data directory

The raw market data is **not versioned** (see `.gitignore`). Place the two CSV
files below in this folder before running the notebook.

## Expected files

### `QQQ_5min_10years_UTC.csv`
QQQ 5-minute OHLCV bars, timestamps in **UTC**, bar-open labelled.

| column | type | notes |
|---|---|---|
| `date` | ISO datetime (UTC) | converted to `America/New_York` in the notebook |
| `open`, `high`, `low`, `close` | float | regular + pre-market session |
| `volume` | int | |

### `nq-10y-1min.csv`
CME NQ futures 1-minute bars (continuous front contract), timestamps in
**America/Chicago** exchange time, resampled to 5-minute bars inside the notebook.

| column | type | notes |
|---|---|---|
| `Date` | `dd/mm/yyyy` | |
| `Time` | `HH:MM:SS` | assumed bar-open labelled, Chicago time |
| `Open`, `High`, `Low`, `Close` | float | |
| `TotalVolume` | int | |

## 📡 Fetching data from Interactive Brokers

`scripts/download_ib.py` writes both files in exactly the schemas above, so
extending the sample needs no code changes.

```bash
pip install ib_async
# TWS or IB Gateway must be running with the API enabled
python scripts/download_ib.py --start 2023-02-01 --end 2026-01-01
python scripts/run_analysis.py --qqq data/QQQ_5min_ib.csv --nq data/nq-5min-ib.csv \
                               --start 2023-02-01 --end 2026-01-01
```

Prerequisites and gotchas:

- **API access** — in TWS/Gateway, *API > Settings > Enable ActiveX and Socket
  Clients*. Ports: `7497` TWS paper, `7496` TWS live, `4002`/`4001` Gateway.
- **Market-data permissions** for US equities (QQQ) and CME futures (NQ).
  Without them IB returns `error 162: No market data permissions` — this is the
  most common failure.
- **Pacing** — IB throttles historical requests (~60 per 10 minutes). The script
  sleeps between chunks; a multi-year pull takes minutes, not seconds.
- **Extended hours** — the 09:25 bar is part of the signal, so requests use
  `useRTH=False`. Verify the pre-market bars actually arrive.
- **Bar labelling** — IB timestamps mark the bar's *start*, which matches this
  project's convention. NQ is fetched as a continuous front-month contract;
  only the sign of the 09:25 bar is used, so roll adjustment is immaterial.
- The analysis scripts default to the paper's window (2016-01-01 → 2023-02-17).
  **Pass `--start`/`--end` or newer data will be silently filtered out** (the
  scripts now fail with an explicit message instead).

## ⚠️ Integrity checks worth running before any backtest

- Confirm the vendor's **bar-labelling convention** (bar-open vs bar-close): a
  close-labelled feed shifts every session bar by one slot and silently changes
  the signal definition.
- Confirm the NQ timestamps are truly exchange (Chicago) time and handle DST
  transitions explicitly (`tz_localize(..., ambiguous=..., nonexistent=...)`).
- Verify the first regular-session QQQ bar of each day is exactly `09:30`.
