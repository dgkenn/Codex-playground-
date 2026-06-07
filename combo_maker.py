"""COMBINATION test: can we stack the discovered signals to make the fee-exempt
maker seat net-positive? Train a toxicity/edge model (IS) on per-fill maker markout
using all features, then QUOTE ONLY where predicted-positive, and measure realized
OOS markout (+ maker rebate) under both exit assumptions:
  MID-exit  = queue-favorable ceiling
  CROSS-exit = pay spread to flatten (realizable floor)
Window-clustered + bootstrap. If the CROSS-exit subset is robustly +OOS, combining
the signals beats adverse selection without needing queue magic.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy.special import expit

import run_real as rr
import fees

DELTA = 30
REBATE_RATE = 0.07


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


def per_window(df, col):
    return df.groupby("win")[col].mean().to_numpy()


def main():
    con = duckdb.connect()
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
    bid0, ask0 = quotes(con, aid, ts)
    be, ae = quotes(con, aid, np.minimum(ts + DELTA * 1000, wend))
    bm, am = quotes(con, aid, np.minimum(ts + DELTA * 1000, wend))  # same; mid below
    d = np.where(df["side"] == "SELL", 1.0, -1.0)
    mid_exit = (be + ae) / 2
    cross_exit = np.where(d > 0, be, ae)
    reb = fees.maker_rebate(df["price"].to_numpy(), rate=REBATE_RATE)
    df["net_mid"] = d * (mid_exit - df["price"].to_numpy()) + reb
    df["net_cross"] = d * (cross_exit - df["price"].to_numpy()) + reb
    df["spread"] = ask0 - bid0
    # features (pre-trade)
    bt, bp = rr.load_spot("btc.npz")
    mom60 = np.log(rr.spot_at(bt, bp, ts) / rr.spot_at(bt, bp, ts - 60000))
    def rvol(tend):
        out = np.full(len(tend), np.nan); i1 = np.searchsorted(bt, tend); i0 = np.searchsorted(bt, tend - 120000)
        for k in range(len(tend)):
            seg = bp[i0[k]:i1[k]]
            if len(seg) > 5: out[k] = np.std(np.diff(np.log(seg)))
        return out
    bmid_now = (bid0 + ask0) / 2
    bpast_b, bpast_a = quotes(con, aid, ts - 30000)
    tokmom = bmid_now - (bpast_b + bpast_a) / 2
    df["f_tau"] = df["tau"]; df["f_lsize"] = np.log1p(df["size"]); df["f_spread"] = df["spread"]
    df["f_mom60"] = mom60; df["f_rvol"] = rvol(ts); df["f_mid"] = bmid_now
    df["f_absmid"] = np.abs(bmid_now - 0.5); df["f_tokmom"] = tokmom
    feats = ["f_tau", "f_lsize", "f_spread", "f_mom60", "f_rvol", "f_mid", "f_absmid", "f_tokmom"]
    df = df.dropna(subset=feats + ["net_cross", "net_mid"]).reset_index(drop=True)

    midw = np.median(np.unique(df["win"]))
    IS = df[df["win"] < midw]; OOS = df[df["win"] >= midw]
    X = IS[feats].to_numpy(); Xm = X.mean(0); Xs = X.std(0) + 1e-9
    Xz = (X - Xm) / Xs
    # train to predict positive CROSS markout (classification on sign)
    y = (IS["net_cross"].to_numpy() > 0).astype(float)
    wv = np.zeros(len(feats)); b = 0.0; lam = 2.0
    for _ in range(4000):
        p = expit(Xz @ wv + b)
        wv -= 0.1 * (Xz.T @ (p - y) / len(y) + lam * wv / len(y))
        b -= 0.1 * np.mean(p - y)
    Xo = (OOS[feats].to_numpy() - Xm) / Xs
    pred = expit(Xo @ wv + b)
    print(f"{len(df)} fills; train {len(IS)} / test {len(OOS)}")
    for q in [0.5, 0.6, 0.7]:
        thr = np.quantile(pred, q)
        sel = OOS[pred >= thr]
        for exit_col, lbl in [("net_cross", "CROSS"), ("net_mid", "MID")]:
            n, m, t = clt(per_window(sel, exit_col))
            print(f"  quote top-{int((1-q)*100)}% predicted ({len(sel)} fills) {lbl}-exit+reb: "
                  f"n_win={n} mean={m:+.5f} t={t:+.2f}"
                  f"{'  <= EDGE' if exit_col=='net_cross' and m>0 and t>2.58 else ''}")
    # baseline all
    for exit_col, lbl in [("net_cross", "CROSS"), ("net_mid", "MID")]:
        n, m, t = clt(per_window(OOS, exit_col))
        print(f"  ALL OOS fills {lbl}-exit+reb: mean={m:+.5f} t={t:+.2f}")


if __name__ == "__main__":
    main()
