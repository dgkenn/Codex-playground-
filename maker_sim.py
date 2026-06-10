"""H1: maker spread-capture, evaluated from REALIZED trade prints (no fill model).

Every executed trade had a maker on the other side. So the PnL of "provide
liquidity at the touch and hold the resulting inventory to resolution" is exact
on the historical tape -- no queue or fill assumptions, and adverse selection is
already baked in (the trades that happened are the ones takers chose to do):

    taker SELL (hit the bid)  -> maker BUYS  at price -> maker_pnl = settle - price
    taker BUY  (lift the ask) -> maker SELLS at price -> maker_pnl = price - settle

settle = resolved_up (1 if the window resolved Up, else 0) for the Up token.
Makers pay NO fee (docs); takers pay feeRate*p*(1-p). This is zero-sum on the
contract: taker_gross = -maker_pnl, taker_net = taker_gross - fee.

Caveats (stated, not hidden): assumes the maker holds to resolution (no hedging/
early exit) and would have been the counterparty (per-share PnL is the invariant;
real capture is a queue-dependent fraction of the size). Discriminators applied:
in/out-of-sample halves, by time-remaining, by price, and the final-180s
truncation (a real maker edge is broad/early, NOT concentrated in the late sprint
like the taker artifact).
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share

FEE_BPS = 1000.0


def load():
    con = duckdb.connect()
    df = con.execute("""
        SELECT epoch_ms(t.timestamp) AS ts_ms, t.asset_id, t.price, t.size, t.side,
               w.window_start, w.window_end, w.resolved_up,
               epoch_ms(t.timestamp)/1000.0 - w.window_start AS t_into,
               w.window_end - epoch_ms(t.timestamp)/1000.0 AS tau
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('up_windows.parquet') w ON t.asset_id = w.asset_id
        WHERE w.resolved_up IS NOT NULL
    """).df()
    df = df[(df["t_into"] >= 0) & (df["t_into"] < 900)].reset_index(drop=True)
    return df


def validate_side(df):
    """Confirm 'side' is the TAKER side: BUY prints should sit above the prevailing
    mid, SELL prints below. Returns True if semantics are as assumed."""
    con = duckdb.connect()
    res = con.execute("""
        SELECT t.side, count(*) n,
               avg(t.price - (CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2) px_vs_mid
        FROM read_parquet('up_trades.parquet') t
        ASOF JOIN read_parquet('up_book.parquet') b
          ON t.asset_id = b.asset_id AND t.timestamp >= b.timestamp
        GROUP BY t.side
    """).df()
    print("  side validation (price - mid, prevailing book):")
    print(res.to_string(index=False))
    buy = res[res["side"] == "BUY"]["px_vs_mid"]
    sell = res[res["side"] == "SELL"]["px_vs_mid"]
    ok = (len(buy) and buy.iloc[0] > 0) and (len(sell) and sell.iloc[0] < 0)
    print(f"  -> side = taker side: {'CONFIRMED' if ok else 'NOT as assumed (check!)'}")
    return ok


def stats(df, label, wcol="size"):
    pnl = df["maker_pnl"].to_numpy()
    w = df[wcol].to_numpy()
    n = len(df)
    mean = pnl.mean()
    std = pnl.std(ddof=1) if n > 1 else np.nan
    t = mean / std * np.sqrt(n) if std and std > 0 else np.nan
    wmean = np.average(pnl, weights=w) if w.sum() > 0 else np.nan
    print(f"  {label:24} n={n:7d}  per-share mean={mean:+.4f} t={t:+.2f}  "
          f"size-wtd mean={wmean:+.4f}  shares={w.sum():,.0f}")
    return t


def by_bucket(df, col, edges, labels, name):
    print(f"  by {name}:")
    b = pd.cut(df[col], bins=edges, labels=labels, right=False)
    for k, g in df.groupby(b, observed=True):
        pnl = g["maker_pnl"].to_numpy()
        t = pnl.mean() / pnl.std(ddof=1) * np.sqrt(len(g)) if len(g) > 1 and pnl.std() > 0 else np.nan
        print(f"    {str(k):>10}: n={len(g):7d}  mean={pnl.mean():+.4f}  t={t:+.2f}  "
              f"size-wtd={np.average(pnl, weights=g['size']):+.4f}")


def oos(df):
    uniq = np.sort(df["window_start"].unique())
    mid = uniq[len(uniq) // 2]
    rank = {w: i for i, w in enumerate(uniq)}
    par = df["window_start"].map(rank) % 2
    print("  in/out-of-sample:")
    stats(df, "  full")
    stats(df[df["window_start"] < mid], "  first-half (OOS)")
    stats(df[df["window_start"] >= mid], "  second-half (OOS)")
    stats(df[par == 0], "  even windows")
    stats(df[par == 1], "  odd windows")


def main():
    df = load()
    print(f"=== maker_sim.py : {len(df)} trade prints across "
          f"{df['asset_id'].nunique()} resolved Up tokens ===\n")
    side_ok = validate_side(df)

    sell = df["side"] == "SELL"
    df["maker_pnl"] = np.where(sell, df["resolved_up"] - df["price"],
                               df["price"] - df["resolved_up"])
    df["taker_gross"] = -df["maker_pnl"]
    df["taker_fee"] = fee_per_share(df["price"].to_numpy(), FEE_BPS)
    df["taker_net"] = df["taker_gross"] - df["taker_fee"]

    print("\n--- ground truth: do takers lose? (per share, size-weighted) ---")
    for nm, col in [("taker gross", "taker_gross"), ("taker net (fee)", "taker_net"),
                    ("MAKER (no fee)", "maker_pnl")]:
        v = np.average(df[col], weights=df["size"])
        print(f"  {nm:18}: {v:+.4f}/share   total={np.sum(df[col]*df['size']):+,.0f}")

    print("\n--- MAKER edge: in/out-of-sample ---")
    oos(df)

    print("\n--- MAKER: by time-remaining (real edge is broad/early, not late) ---")
    by_bucket(df, "tau", [0, 60, 180, 300, 450, 600, 900],
              ["0-60", "60-180", "180-300", "300-450", "450-600", "600-900"], "time-remaining")

    print("\n--- MAKER: by trade price ---")
    by_bucket(df, "price", [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0],
              [f"{i/10:.1f}-{(i+1)/10:.1f}" for i in range(10)], "price")

    print("\n--- MAKER: FINAL 180s EXCLUDED (tau>=180), in/out-of-sample ---")
    trunc = df[df["tau"] >= 180]
    oos(trunc)


if __name__ == "__main__":
    main()
