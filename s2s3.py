"""S2 cross-sectional relative-value reversal (market-neutral stat-arb across coins)
S3 market-to-market lead-lag (does the BTC token lead the alt tokens?)

Uses token mids (up_book.parquet for BTC, alt_book.parquet for ETH/SOL/XRP) and
per-coin spot. Window-clustered; one pooled regression with clustered t.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import run_real as rr
from fairvalue import fair_up

WINDOW_S = 900
DELTA = 60
TAUS = [600, 480, 360, 240, 120]
SPOT = {"btc": "btc.npz", "eth": "ETHUSDT.npz", "sol": "SOLUSDT.npz", "xrp": "XRPUSDT.npz"}


def mids(con, book, asset_ids, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(asset_ids, str), "t_ms": np.asarray(t_ms, np.int64),
                       "r": np.arange(len(asset_ids))})
    con.register("tg", tg)
    out = con.execute(f"""SELECT tg.r, (CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2 mid
        FROM tg ASOF LEFT JOIN read_parquet('{book}') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg")
    return out["mid"].to_numpy()


def clustered_slope(y, x, win):
    """OLS slope of y~x with window-clustered SE (cluster on win)."""
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    meat = np.zeros((2, 2))
    for w in np.unique(win):
        m = win == w
        Xg = X[m]; ug = resid[m]
        s = Xg.T @ ug
        meat += np.outer(s, s)
    cov = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(cov))
    return beta[1], beta[1] / se[1], len(np.unique(win))


def build():
    con = duckdb.connect()
    spots = {c: rr.load_spot(p) for c, p in SPOT.items()}
    # BTC tokens from up_windows; alts from alt_windows
    btc = pd.read_parquet("up_windows.parquet")[["window_start", "asset_id"]].assign(coin="btc")
    alt = pd.read_parquet("alt_windows.parquet")[["window_start", "asset_id", "coin"]]
    toks = pd.concat([btc, alt], ignore_index=True)
    recs = []
    for tau in TAUS:
        sub = toks.copy()
        sub["t"] = sub["window_start"] + (WINDOW_S - tau)
        sub["tau"] = tau
        recs.append(sub)
    g = pd.concat(recs, ignore_index=True)
    # token mids at t-DELTA, t, t+DELTA
    for coin, book in [("btc", "up_book.parquet"), ("eth", "alt_book.parquet"),
                       ("sol", "alt_book.parquet"), ("xrp", "alt_book.parquet")]:
        pass
    # need per-row book: BTC rows use up_book, alt rows use alt_book
    g["mid_t"] = np.nan; g["mid_tm"] = np.nan; g["mid_tp"] = np.nan; g["fair"] = np.nan
    for coin in ["btc", "eth", "sol", "xrp"]:
        m = (g["coin"] == coin).to_numpy()
        book = "up_book.parquet" if coin == "btc" else "alt_book.parquet"
        aid = g.loc[m, "asset_id"].astype(str).to_numpy()
        t = g.loc[m, "t"].to_numpy()
        g.loc[m, "mid_t"] = mids(con, book, aid, t * 1000)
        g.loc[m, "mid_tm"] = mids(con, book, aid, (t - DELTA) * 1000)
        g.loc[m, "mid_tp"] = mids(con, book, aid, (t + DELTA) * 1000)
        ts_, px_ = spots[coin]
        s0 = rr.spot_at(ts_, px_, (g.loc[m, "window_start"].to_numpy()) * 1000)
        st = rr.spot_at(ts_, px_, t * 1000)
        sig = rr.realized_vol_per_s(px_, 1.0)
        g.loc[m, "fair"] = fair_up(st, s0, sig, g.loc[m, "tau"].to_numpy())
    return g.dropna(subset=["mid_t", "mid_tm", "mid_tp", "fair"]).reset_index(drop=True)


def main():
    g = build()
    print(f"=== S2/S3 panel: {len(g)} (coin,window,tau) rows ===")

    # S2 cross-sectional reversal: within each (window,tau), demean dislocation across coins;
    # does demeaned dislocation predict future token return (negative=reversion)?
    g["disloc"] = g["mid_t"] - g["fair"]
    g["fut"] = g["mid_tp"] - g["mid_t"]
    g["key"] = g["window_start"].astype(str) + "_" + g["tau"].astype(str)
    g["x_demean"] = g["disloc"] - g.groupby("key")["disloc"].transform("mean")
    g["y_demean"] = g["fut"] - g.groupby("key")["fut"].transform("mean")
    cnt = g.groupby("key")["coin"].transform("count")
    s2 = g[cnt >= 3]
    b, t, nw = clustered_slope(s2["y_demean"].to_numpy(), s2["x_demean"].to_numpy(),
                               s2["window_start"].to_numpy())
    print(f"\nS2 cross-sectional RV: fut_ret ~ demeaned_dislocation  slope={b:+.3f} "
          f"clustered t={t:+.2f} (n={len(s2)}, {nw} windows)  "
          f"-> {'reversion edge' if b<0 and abs(t)>2.58 else 'no clean edge'}")

    # S3 market lead-lag: does BTC token past return predict alt token future return?
    btc = g[g["coin"] == "btc"][["key", "window_start"]].copy()
    btc["btc_past"] = (g[g["coin"] == "btc"]["mid_t"].to_numpy() -
                       g[g["coin"] == "btc"]["mid_tm"].to_numpy())
    alt = g[g["coin"] != "btc"].copy()
    alt["alt_fut"] = alt["mid_tp"] - alt["mid_t"]
    m = alt.merge(btc[["key", "btc_past"]], on="key", how="inner").dropna(subset=["btc_past", "alt_fut"])
    b, t, nw = clustered_slope(m["alt_fut"].to_numpy(), m["btc_past"].to_numpy(),
                               m["window_start"].to_numpy())
    print(f"S3 BTC-token -> alt-token lead-lag: alt_fut ~ btc_past  slope={b:+.3f} "
          f"clustered t={t:+.2f} (n={len(m)}, {nw} windows)  "
          f"-> {'lead-lag edge' if abs(t)>2.58 else 'no clean lead-lag'}")


if __name__ == "__main__":
    main()
