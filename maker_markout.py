"""Proper market-making evaluation: MARKOUT PnL + maker rebate.

maker_sim.py measured hold-to-resolution PnL (= -taker gross), which bundles in
directional risk to expiry. A real MM captures the spread and FLATTENS, so the
right metric is the markout: after the maker is filled, does the mid move in their
favour over the next Delta seconds?

  maker fill: taker BUY  -> maker SOLD  (short, dir=-1)
              taker SELL -> maker BOUGHT (long,  dir=+1)
  markout(Delta) = dir * (mid_{t+Delta} - fill_price)
  net           = markout + rebate,  rebate = 0.20 * taker_fee  (crypto, 20% pool)

If short-horizon markouts (+rebate) are positive while the to-resolution markout
is negative, a spread-capturing/flattening MM wins where hold-to-resolution lost.
Everything window-clustered + size-weighted + OOS, Bonferroni-aware.
"""
from __future__ import annotations

import sys

import duckdb
import numpy as np
import pandas as pd

from fairvalue import fee_per_share

REBATE_SHARE = 0.20   # crypto: 20% of taker fees redistributed to makers
TAKER_BPS = 1000.0


def quotes_at(con, book_path, asset_ids, t_ms):
    """Return (mid, bid, ask) at-or-before t_ms for each (asset_id, t_ms)."""
    tg = pd.DataFrame({"asset_id": np.asarray(asset_ids, str), "t_ms": np.asarray(t_ms, np.int64)})
    con.register("tg", tg)
    df = con.execute(f"""
        SELECT (b.best_bid + b.best_ask)/2.0 AS mid, b.best_bid AS bid, b.best_ask AS ask
        FROM (SELECT *, row_number() OVER () AS r FROM tg) tg
        ASOF LEFT JOIN read_parquet('{book_path}') b
          ON tg.asset_id = b.asset_id AND tg.t_ms >= epoch_ms(b.timestamp)
        ORDER BY tg.r
    """).df()
    con.unregister("tg")
    return df["mid"].to_numpy(), df["bid"].to_numpy(), df["ask"].to_numpy()


def clustered(per):
    a = per[np.isfinite(per)]
    n = len(a)
    if n < 2:
        return n, np.nan, np.nan
    m = a.mean(); s = a.std(ddof=1)
    return n, m, (m / s * np.sqrt(n) if s > 0 else np.nan)


def per_window_sw(df, col):
    return df.groupby("win").apply(lambda x: np.average(x[col], weights=x["size"]),
                                   include_groups=False)


def boot_ci(df, col, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    g = df.groupby("win")
    num = g.apply(lambda x: np.sum(x[col] * x["size"]), include_groups=False).to_numpy()
    den = g.apply(lambda x: x["size"].sum(), include_groups=False).to_numpy()
    out = []
    for _ in range(n):
        i = rng.integers(0, len(num), len(num))
        out.append(num[i].sum() / den[i].sum())
    out = np.array(out)
    return num.sum() / den.sum(), np.percentile(out, 2.5), np.percentile(out, 97.5)


def oos_t(df, col):
    uniq = np.sort(df["win"].unique()); midw = uniq[len(uniq) // 2]
    _, _, tf = clustered(per_window_sw(df[df["win"] < midw], col).to_numpy())
    _, _, ts2 = clustered(per_window_sw(df[df["win"] >= midw], col).to_numpy())
    return tf, ts2


def run(tf, trades_path, book_path, win_path, wlen):
    con = duckdb.connect()
    print(f"\n########## {tf}: markout market-making (in-window trades only) ##########")
    df = con.execute(f"""
        SELECT epoch_ms(t.timestamp) AS ts_ms, t.asset_id, t.price, t.size, t.side,
               w.window_end, w.resolved_up, w.window_start AS win,
               epoch_ms(t.timestamp)/1000.0 - w.window_start AS t_into
        FROM read_parquet('{trades_path}') t
        JOIN read_parquet('{win_path}') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
    """).df()
    df = df[(df["price"] > 0) & (df["price"] < 1) &
            (df["t_into"] >= 0) & (df["t_into"] < wlen)].reset_index(drop=True)
    df["dir"] = np.where(df["side"] == "SELL", 1.0, -1.0)   # SELL=maker bought(long)
    df["rebate"] = REBATE_SHARE * fee_per_share(df["price"].to_numpy(), TAKER_BPS)
    print(f"  {len(df)} in-window maker fills, {df['win'].nunique()} windows; "
          f"mean rebate={df['rebate'].mean():.4f}/share")
    print("  MID-exit = optimistic (incl. mechanical half-spread); "
          "CROSS-exit = pay the spread to flatten (honest floor). Both +rebate.")
    print(f"  {'horizon':>9} | {'MID-exit+reb sw [CI]   OOS t/t':>40} | {'CROSS-exit+reb sw [CI]   OOS t/t':>40}")

    aid = df["asset_id"].to_numpy(); ts = df["ts_ms"].to_numpy()
    wend = df["window_end"].to_numpy().astype(np.int64); res = df["resolved_up"].to_numpy().astype(float)
    price = df["price"].to_numpy(); d = df["dir"].to_numpy(); reb = df["rebate"].to_numpy()
    for h in [1, 5, 30, 120, 300]:
        t_exit = np.minimum(ts + h * 1000, wend * 1000)
        mid, bid, ask = quotes_at(con, book_path, aid, t_exit)
        beyond = (ts + h * 1000) >= wend * 1000
        mid = np.where(beyond, res, mid); bid = np.where(beyond, res, bid); ask = np.where(beyond, res, ask)
        mk_mid = d * (mid - price) + reb
        # cross to flatten: long sells at bid, short buys at ask
        cross_exit = np.where(d > 0, bid, ask)
        mk_cross = d * (cross_exit - price) + reb
        df["a"] = mk_mid; df["b"] = mk_cross
        sub = df[np.isfinite(mid)]
        pa, la, ha = boot_ci(sub, "a"); pb, lb, hb = boot_ci(sub, "b")
        fa, sa = oos_t(sub, "a"); fb, sb = oos_t(sub, "b")
        print(f"  {h:>7}s | {pa:+.4f} [{la:+.4f},{ha:+.4f}] {fa:+.1f}/{sa:+.1f}"
              f"{'  +' if la>0 else '   '} | {pb:+.4f} [{lb:+.4f},{hb:+.4f}] {fb:+.1f}/{sb:+.1f}"
              f"{'  +' if lb>0 else ''}")

    mk = d * (res - price) + reb
    df["a"] = mk
    p, lo, hi = boot_ci(df, "a"); fa, sa = oos_t(df, "a")
    print(f"  {'resolution':>9} hold+rebate: {p:+.4f} [{lo:+.4f},{hi:+.4f}] OOS {fa:+.1f}/{sa:+.1f}")


def main():
    run("BTC-15m", "up_trades.parquet", "up_book.parquet", "up_windows.parquet", 900)
    import os
    if os.path.exists("up_book_5m.parquet"):
        run("BTC-5m", "up_trades_5m.parquet", "up_book_5m.parquet", "win_5m.parquet", 300)
    else:
        print("\n(5m markout skipped: need up_book_5m.parquet)")


if __name__ == "__main__":
    main()
