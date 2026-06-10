"""Robustness: does the apparent edge replicate out-of-sample, and is it just a
volatility-misspecification artifact?

Loads spot+book once, then re-runs the backtest on disjoint window subsets
(in/out-of-sample) and at scaled sigma. A real edge survives both; an artifact of
a too-low global sigma collapses when sigma is raised.
"""
from __future__ import annotations

import numpy as np

import run_real as rr

THR = 0.005
FEE = 1000.0


def line(name, spot_ts, spot_px, book, sigma):
    r = rr.backtest(spot_ts, spot_px, book, 900, THR, 60, FEE, sigma)
    tr = r["trades"]
    if len(tr) == 0:
        print(f"  {name:26} no trades"); return
    s = rr.summary_stats(tr)
    late = tr[tr["tau"] < 180]
    late_mean = late["pnl"].mean() if len(late) else float("nan")
    print(f"  {name:26} n={s['n']:5d}  mean={s['mean']:+.4f}  t={s['tstat']:+.2f}  "
          f"win={s['win_rate']:.3f}  | late(tau<180) n={len(late):4d} mean={late_mean:+.4f}")


def main():
    spot_ts, spot_px = rr.load_spot("btc.npz")
    book = rr.load_book("up_book.parquet", "timestamp", "best_bid", "best_ask", "ms")
    sigma = rr.realized_vol_per_s(spot_px, rr._median_dt_s(spot_ts))
    print(f"base sigma/s = {sigma:.3e}   threshold = {THR}   fee_bps = {FEE}\n")

    # window index for each row, for a clean 50/50 interleaved split
    ws = book["ts_ms"].to_numpy() // 1000 // 900
    uniq = np.unique(ws)
    rank = np.searchsorted(uniq, ws)
    even = book[rank % 2 == 0].reset_index(drop=True)
    odd = book[rank % 2 == 1].reset_index(drop=True)

    # time-based halves
    mid_w = uniq[len(uniq) // 2]
    first = book[ws < mid_w].reset_index(drop=True)
    second = book[ws >= mid_w].reset_index(drop=True)

    print("IN/OUT-OF-SAMPLE (sigma=base):")
    line("FULL", spot_ts, spot_px, book, sigma)
    line("even windows", spot_ts, spot_px, even, sigma)
    line("odd windows", spot_ts, spot_px, odd, sigma)
    line("first half (by time)", spot_ts, spot_px, first, sigma)
    line("second half (by time)", spot_ts, spot_px, second, sigma)

    print("\nVOL SENSITIVITY (full sample):")
    for m in (0.75, 1.0, 1.5, 2.0, 3.0):
        line(f"sigma x{m}", spot_ts, spot_px, book, sigma * m)


if __name__ == "__main__":
    main()
