# Data requirements

The historical files used in the original research are not included because
market-data redistribution rights depend on the user's vendor agreement.

## QQQ input

The original notebook expects:

```text
Data/QQQ_5min_10years_UTC.csv
```

Required columns:

```text
date, open, high, low, close
```

The `date` field must contain UTC timestamps. The preprocessing code converts
them to `America/New_York` and retains bars from 09:25 through 15:55 ET.
Additional columns are allowed and ignored by the reusable engine.

## NQ input

The original notebook expects:

```text
Data/nq-10y-1min.csv
```

Required columns:

```text
Date, Time, Open, High, Low, Close, TotalVolume
```

The source timestamps are interpreted as `America/Chicago`. The data is
converted to `America/New_York`, resampled from 1-minute to 5-minute OHLCV bars
and aligned to the QQQ timestamps.

## Reproducibility boundary

The repository provides:

- preprocessing code;
- a reusable backtest engine;
- synthetic unit tests;
- stored outputs from the original executed notebook;
- exact strategy and cost assumptions.

A bit-for-bit rerun of the historical results additionally requires the same
underlying data files and vendor revisions.
