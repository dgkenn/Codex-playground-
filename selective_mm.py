"""Jane-Street-style SELECTIVE market-making: a maker need not always quote. Compute
the honest per-fill maker markout (CROSS-exit to flatten + maker rebate) and ask
whether conditioning on PRE-TRADE features identifies a subset where providing
liquidity is +EV out-of-sample (quote into benign flow, withdraw before toxic flow).

maker fill at trade price (taker side known): taker BUY -> maker SHORT (dir -1),
taker SELL -> maker LONG (dir +1). Flatten by crossing at +DELTA:
  long  exits at bid_{t+D};  short exits at ask_{t+D}.  + maker rebate (fee-exempt).
Features (no lookahead): tau, size, spread, recent spot vol, recent flow imbalance.
Pre-specified benign filter tested IS then OOS (avoid p-hacking).
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import run_real as rr
import fees

DELTA = 30
REBATE_RATE = 0.07   # crypto taker rate that funds the 20% maker rebate (corrected)


def quotes(con, aid, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(aid, str), "t_ms": np.asarray(t_ms, np.int64), "r": np.arange(len(aid))})
    con.register("tg", tg)
    o = con.execute("""SELECT tg.r, CAST(b.best_bid AS DOUBLE) bid, CAST(b.best_ask AS DOUBLE) ask
        FROM tg ASOF LEFT JOIN read_parquet('up_book.parquet') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg"); return o["bid"].to_numpy(), o["ask"].to_numpy()


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def per_window_t(df, col):
    return clt(df.groupby("win")[col].mean().to_numpy())


def main():
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])
    df = con.execute("""
        SELECT epoch_ms(t.timestamp) ts_ms, t.asset_id, t.price, t.size, t.side,
               w.window_start win, w.window_end,
               w.window_end - epoch_ms(t.timestamp)/1000.0 AS tau
        FROM read_parquet('up_trades.parquet') t
        JOIN read_parquet('up_windows.parquet') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
          AND epoch_ms(t.timestamp)/1000.0 - w.window_start BETWEEN 0 AND 900
          AND t.price>0 AND t.price<1
    """).df()
    aid = df["asset_id"].astype(str).to_numpy(); ts = df["ts_ms"].to_numpy()
    wend = (df["window_end"].to_numpy() * 1000).astype(np.int64)
    bid0, ask0 = quotes(con, aid, ts)                       # quote at fill time
    be, ae = quotes(con, aid, np.minimum(ts + DELTA * 1000, wend))
    df["spread"] = ask0 - bid0
    d = np.where(df["side"] == "SELL", 1.0, -1.0)
    cross_exit = np.where(d > 0, be, ae)
    df["markout"] = d * (cross_exit - df["price"].to_numpy())
    df["rebate"] = fees.maker_rebate(df["price"].to_numpy(), rate=REBATE_RATE)
    df["net"] = df["markout"] + df["rebate"]
    # pre-trade features
    spot_ts, spot_px = rr.load_spot("btc.npz")
    # recent 60s spot vol and flow imbalance
    df = df.sort_values("ts_ms").reset_index(drop=True)
    df["signed"] = np.where(df["side"] == "BUY", df["size"], -df["size"])
    df = df.dropna(subset=["markout"]).reset_index(drop=True)
    print(f"{len(df)} maker fills, {df['win'].nunique()} windows. cross-exit+rebate markout:")
    n, m, t = per_window_t(df, "net")
    print(f"  BASELINE (all fills): mean={m:+.5f} t={t:+.2f}")

    # by single features (IS exploration; terciles)
    for feat, label in [("tau", "time-remaining"), ("size", "trade size"), ("spread", "spread")]:
        q = df[feat].quantile([0.33, 0.66]).values
        df["b"] = np.where(df[feat] <= q[0], "low", np.where(df[feat] <= q[1], "mid", "high"))
        print(f"  by {label}:")
        for bk in ["low", "mid", "high"]:
            s = df[df["b"] == bk]; n, m, t = per_window_t(s, "net")
            print(f"     {bk:4}: n={len(s):6d} mean={m:+.5f} t={t:+.2f}")

    # PRE-SPECIFIED benign filter: small trades (uninformed), wide-ish spread (more vig),
    # NOT final sprint (informed late) -> quote here. Test IS then OOS.
    benign = (df["size"] <= df["size"].median()) & (df["tau"] > 120) & (df["spread"] >= 0.01)
    sub = df[benign]
    mid = np.median(np.unique(df["win"]))
    print(f"\nPRE-SPECIFIED benign filter (small size & tau>120s & spread>=1c): {len(sub)} fills")
    for lab, s in [("ALL", sub), ("IS", sub[sub["win"] < mid]), ("OOS", sub[sub["win"] >= mid])]:
        n, m, t = per_window_t(s, "net")
        print(f"  {lab:3}: n_win={n} mean={m:+.5f} t={t:+.2f}"
              f"{'  <= EDGE' if lab=='OOS' and m>0 and t>2.58 else ''}")


if __name__ == "__main__":
    main()
