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

## ⚠️ Integrity checks worth running before any backtest

- Confirm the vendor's **bar-labelling convention** (bar-open vs bar-close): a
  close-labelled feed shifts every session bar by one slot and silently changes
  the signal definition.
- Confirm the NQ timestamps are truly exchange (Chicago) time and handle DST
  transitions explicitly (`tz_localize(..., ambiguous=..., nonexistent=...)`).
- Verify the first regular-session QQQ bar of each day is exactly `09:30`.
