"""Download QQQ and NQ 5-minute bars from Interactive Brokers (TWS / IB Gateway).

Writes CSVs in exactly the schema the loaders in `qqq_opening_bias.data` expect,
so extending the sample needs no code changes:

  QQQ -> date (ISO, UTC), open, high, low, close, volume
  NQ  -> Date (dd/mm/YYYY, Chicago), Time (HH:MM:SS), Open, High, Low, Close,
         TotalVolume

Requirements
------------
* TWS or IB Gateway running locally with "Enable ActiveX and Socket Clients"
  ticked (API > Settings). Default ports: 7497 TWS paper, 7496 TWS live,
  4002 Gateway paper, 4001 Gateway live.
* Market-data permissions for US equities (QQQ) and CME futures (NQ). Without
  them IB returns error 162 "No market data permissions".
* pip install ib_async

Notes
-----
* IB timestamps label the START of each bar, matching this project's convention.
* Pre-market bars are required (the 09:25 signal), so useRTH=False throughout.
* NQ is requested as a continuous front-month contract. Only the SIGN of the
  09:25 bar is used, so roll adjustment is immaterial to the strategy.
* IB paces historical requests (~60 per 10 minutes); --sleep spaces them out.

Examples
--------
    # extend the sample past the original study window
    python scripts/download_ib.py --start 2023-02-01 --end 2026-01-01

    # paper-trading gateway on a non-default port
    python scripts/download_ib.py --start 2023-02-01 --end 2026-01-01 \
        --port 4002 --client-id 7
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd

BAR_SIZE = "5 mins"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", required=True, help="First session to fetch (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Last session (YYYY-MM-DD, default: today)")
    parser.add_argument("--out-dir", default="data", help="Directory for the CSVs")
    parser.add_argument("--qqq-out", default="QQQ_5min_ib.csv")
    parser.add_argument("--nq-out", default="nq-5min-ib.csv")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497,
                        help="7497 TWS paper, 7496 TWS live, 4002/4001 Gateway")
    parser.add_argument("--client-id", type=int, default=17)
    parser.add_argument("--chunk", default="1 M",
                        help='Duration per request ("1 M" or "1 W" if IB rejects it)')
    parser.add_argument("--sleep", type=float, default=11.0,
                        help="Seconds between requests (IB paces ~60 per 10 min)")
    parser.add_argument("--only", choices=["qqq", "nq"], default=None,
                        help="Fetch just one instrument")
    return parser.parse_args()


def _chunk_ends(start: dt.date, end: dt.date, chunk: str) -> list[dt.datetime]:
    """End timestamps to walk the window forward, one request per chunk."""
    step = pd.DateOffset(months=1) if chunk.strip().upper().endswith("M") else pd.DateOffset(weeks=1)
    ends, cursor = [], pd.Timestamp(start)
    final = pd.Timestamp(end)
    while cursor < final:
        cursor = min(cursor + step, final)
        ends.append(cursor.to_pydatetime())
    return ends


def fetch(ib, contract, ends: list[dt.datetime], chunk: str, sleep_s: float, label: str) -> pd.DataFrame:
    """Request one chunk per end-timestamp and concatenate the bars."""
    from ib_async import util

    frames = []
    for i, end in enumerate(ends, 1):
        stamp = end.strftime("%Y%m%d-%H:%M:%S")
        print(f"[{label}] {i}/{len(ends)}  up to {end:%Y-%m-%d} ...", flush=True)
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=stamp,
                durationStr=chunk,
                barSizeSetting=BAR_SIZE,
                whatToShow="TRADES",
                useRTH=False,        # the 09:25 pre-market bar is part of the signal
                formatDate=2,        # epoch seconds (UTC) -- unambiguous
            )
        except Exception as exc:  # noqa: BLE001 - surface IB errors without aborting the run
            print(f"    request failed: {exc}", file=sys.stderr)
            bars = None

        if bars:
            frames.append(util.df(bars))
        else:
            print("    no data returned (permissions, holiday range, or pacing)", file=sys.stderr)

        if i < len(ends):
            time.sleep(sleep_s)

    if not frames:
        raise SystemExit(f"[{label}] no data downloaded -- check market-data permissions")

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], utc=True)
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def write_qqq(bars: pd.DataFrame, path: str) -> None:
    """UTC ISO timestamps -- matches load_qqq_bars."""
    frame = pd.DataFrame(
        {
            "date": bars["date"].dt.strftime("%Y-%m-%d %H:%M:%S%z"),
            "open": bars["open"],
            "high": bars["high"],
            "low": bars["low"],
            "close": bars["close"],
            "volume": bars["volume"],
        }
    )
    frame.to_csv(path, index=False)
    print(f"wrote {path}  rows={len(frame):,}")


def write_nq(bars: pd.DataFrame, path: str) -> None:
    """Chicago wall-clock Date/Time columns -- matches load_nq_bars."""
    local = bars["date"].dt.tz_convert("America/Chicago")
    frame = pd.DataFrame(
        {
            "Date": local.dt.strftime("%d/%m/%Y"),
            "Time": local.dt.strftime("%H:%M:%S"),
            "Open": bars["open"],
            "High": bars["high"],
            "Low": bars["low"],
            "Close": bars["close"],
            "TotalVolume": bars["volume"],
        }
    )
    frame.to_csv(path, index=False)
    print(f"wrote {path}  rows={len(frame):,}")


def main() -> None:
    args = parse_args()
    try:
        from ib_async import IB, ContFuture, Stock
    except ImportError:  # pragma: no cover - environment-dependent
        raise SystemExit("ib_async is required:  pip install ib_async")

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    if end <= start:
        raise SystemExit("--end must be after --start")
    ends = _chunk_ends(start, end, args.chunk)
    os.makedirs(args.out_dir, exist_ok=True)

    ib = IB()
    print(f"connecting to {args.host}:{args.port} (clientId={args.client_id}) ...")
    ib.connect(args.host, args.port, clientId=args.client_id)
    try:
        if args.only != "nq":
            qqq = ib.qualifyContracts(Stock("QQQ", "SMART", "USD"))[0]
            write_qqq(
                fetch(ib, qqq, ends, args.chunk, args.sleep, "QQQ"),
                os.path.join(args.out_dir, args.qqq_out),
            )
        if args.only != "qqq":
            nq = ib.qualifyContracts(ContFuture("NQ", "CME"))[0]
            write_nq(
                fetch(ib, nq, ends, args.chunk, args.sleep, "NQ"),
                os.path.join(args.out_dir, args.nq_out),
            )
    finally:
        ib.disconnect()

    print("\nNext: point the analysis at the new files, e.g.")
    print(f"  python scripts/run_analysis.py --qqq {args.out_dir}/{args.qqq_out} "
          f"--nq {args.out_dir}/{args.nq_out} --start {args.start} --end {end}")


if __name__ == "__main__":
    main()
