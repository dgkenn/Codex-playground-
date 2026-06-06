"""The decisive discriminator: is the edge the late fill-at-quote spread artifact,
or is there a non-mechanical residual?

Three read-outs (threshold 0.005):
  1. Exclude the final 180s of every window, then test in/out-of-sample. If the
     edge vanishes once the late sprint is removed -> it was the spread artifact.
  2. Isolate the mid-window / mid-price cell (180<=tau<600s, 0.4<=entry<0.6),
     out-of-sample. Only a survivor HERE is non-mechanical (weak fair/label
     correlation, small spread at 5-10 min out).
  3. Vol-sensitivity of the late bucket (tau<180) vs the rest. Late staying
     vol-insensitive while the rest moves = the pinning fingerprint, not alpha.
"""
from __future__ import annotations

import numpy as np

import run_real as rr

THR = 0.005
FEE = 1000.0


def stt(df):
    if len(df) < 2:
        return len(df), float("nan"), float("nan")
    s = rr.summary_stats(df)
    return s["n"], s["mean"], s["tstat"]


def splits(trades, label):
    print(f"  {label}")
    uniq = np.sort(trades["win_start"].unique())
    if len(uniq) == 0:
        print("    (no trades)"); return
    mid = uniq[len(uniq) // 2]
    rankmap = {w: i for i, w in enumerate(uniq)}
    parity = trades["win_start"].map(rankmap) % 2
    masks = [("full", np.ones(len(trades), bool)),
             ("first-half (OOS)", (trades["win_start"] < mid).to_numpy()),
             ("second-half (OOS)", (trades["win_start"] >= mid).to_numpy()),
             ("even windows", (parity == 0).to_numpy()),
             ("odd windows", (parity == 1).to_numpy())]
    for nm, m in masks:
        n, mean, t = stt(trades[m])
        print(f"    {nm:20} n={n:5d}  mean={mean:+.4f}  t={t:+.2f}")


def main():
    spot_ts, spot_px = rr.load_spot("btc.npz")
    book = rr.load_book("up_book.parquet", "timestamp", "best_bid", "best_ask", "ms")
    sigma = rr.realized_vol_per_s(spot_px, rr._median_dt_s(spot_ts))
    print(f"base sigma/s={sigma:.3e}  threshold={THR}  fee_bps={FEE}\n")

    tr = rr.backtest(spot_ts, spot_px, book, 900, THR, 60, FEE, sigma)["trades"]

    print("=" * 70)
    print("(1) FINAL 180s EXCLUDED  (tau >= 180s) -- in/out-of-sample")
    print("=" * 70)
    splits(tr[tr["tau"] >= 180], "truncated edge:")

    print("\n" + "=" * 70)
    print("(2) MID-WINDOW / MID-PRICE  (180<=tau<600s, 0.4<=entry<0.6) -- the only")
    print("    cell where a survivor would be non-mechanical")
    print("=" * 70)
    mid = tr[(tr["tau"] >= 180) & (tr["tau"] < 600) &
             (tr["entry_up"] >= 0.4) & (tr["entry_up"] < 0.6)]
    splits(mid, "mid/mid edge:")

    print("\n" + "=" * 70)
    print("(3) VOL SENSITIVITY: late (tau<180) vs rest (tau>=180)")
    print("=" * 70)
    print(f"  {'sigma':>9} | {'late: n  mean   t':28} | rest: n  mean   t")
    for m in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        t2 = rr.backtest(spot_ts, spot_px, book, 900, THR, 60, FEE, sigma * m)["trades"]
        late = t2[t2["tau"] < 180]; rest = t2[t2["tau"] >= 180]
        ln, lm, lt = stt(late); rn, rm, rt = stt(rest)
        print(f"  x{m:<7} | n={ln:4d} mean={lm:+.4f} t={lt:+5.2f}    | "
              f"n={rn:4d} mean={rm:+.4f} t={rt:+5.2f}")


if __name__ == "__main__":
    main()
