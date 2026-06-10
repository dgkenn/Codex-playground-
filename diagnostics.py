"""Round-5 DIAGNOSTICS on the new data. Don't test a pre-baked thesis -- look at
structure first, then let it suggest one.

D1 cross-asset token correlation + lead-lag (BTC token vs ETH/SOL/XRP tokens),
   fine-grained (10s returns). Does the most-liquid market lead the others?
D2 microstructure over window life: spread, mid-vol, trade intensity by tau.
D3 cross-sectional dislocation dispersion + reversion (stat-arb scope).
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import run_real as rr
from fairvalue import fair_up

STEP = 10
SPOT = {"btc": "btc.npz", "eth": "ETHUSDT.npz", "sol": "SOLUSDT.npz", "xrp": "XRPUSDT.npz"}


def mids(con, book, aid, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(aid, str), "t_ms": np.asarray(t_ms, np.int64),
                       "r": np.arange(len(aid))})
    con.register("tg", tg)
    o = con.execute(f"""SELECT tg.r,(CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2 mid,
        CAST(b.best_ask AS DOUBLE)-CAST(b.best_bid AS DOUBLE) spr
        FROM tg ASOF LEFT JOIN read_parquet('{book}') b
        ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg")
    return o["mid"].to_numpy(), o["spr"].to_numpy()


def panel():
    con = duckdb.connect()
    btc = pd.read_parquet("up_windows.parquet")[["window_start", "asset_id"]].assign(coin="btc")
    alt = pd.read_parquet("alt_windows.parquet")[["window_start", "asset_id", "coin"]]
    toks = pd.concat([btc, alt], ignore_index=True)
    # common windows across all coins
    cnt = toks.groupby("window_start")["coin"].nunique()
    commons = cnt[cnt == 4].index
    toks = toks[toks["window_start"].isin(commons)]
    print(f"common windows with all 4 coins: {len(commons)}")
    rows = []
    for ws in commons:
        for k in range(STEP, 900, STEP):
            rows.append((ws, ws + k))
    grid = pd.DataFrame(rows, columns=["ws", "t"])
    out = {}
    for coin in ["btc", "eth", "sol", "xrp"]:
        sub = toks[toks["coin"] == coin].set_index("window_start")["asset_id"]
        g = grid.copy()
        g["asset_id"] = g["ws"].map(sub).astype(str)
        book = "up_book.parquet" if coin == "btc" else "alt_book.parquet"
        m, spr = mids(con, book, g["asset_id"].to_numpy(), (g["t"] * 1000).to_numpy())
        out[coin] = m; out[coin + "_spr"] = spr
    g = grid.copy()
    for k, v in out.items():
        g[k] = v
    return g


def main():
    g = panel()
    # 10s log-ish returns within each window per coin
    for c in ["btc", "eth", "sol", "xrp"]:
        g[c + "_ret"] = g.groupby("ws")[c].diff()
    print("\n=== D1: cross-asset TOKEN correlation (10s mid changes) ===")
    R = g[[c + "_ret" for c in ["btc", "eth", "sol", "xrp"]]].dropna()
    print(R.corr().round(3).to_string())

    print("\n=== D1b: lead-lag  alt_ret(t) ~ btc_ret(t), btc_ret(t-1), btc_ret(t-2) ===")
    for c in ["eth", "sol", "xrp"]:
        d = g.copy()
        d["b0"] = d["btc_ret"]
        d["b1"] = d.groupby("ws")["btc_ret"].shift(1)
        d["b2"] = d.groupby("ws")["btc_ret"].shift(2)
        d = d.dropna(subset=[c + "_ret", "b0", "b1", "b2"])
        X = np.column_stack([np.ones(len(d)), d["b0"], d["b1"], d["b2"]])
        y = d[c + "_ret"].to_numpy()
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        # window-clustered se
        XtXi = np.linalg.inv(X.T @ X); meat = np.zeros((4, 4))
        for w in d["ws"].unique():
            m = (d["ws"] == w).to_numpy(); s = X[m].T @ resid[m]; meat += np.outer(s, s)
        se = np.sqrt(np.diag(XtXi @ meat @ XtXi))
        tv = beta / se
        print(f"  {c}: contemp b0={beta[1]:+.2f}(t{tv[1]:+.1f}) "
              f"lag1 b1={beta[2]:+.3f}(t{tv[2]:+.1f}) lag2 b2={beta[3]:+.3f}(t{tv[3]:+.1f})")

    print("\n=== D2: microstructure over window life (BTC) ===")
    g["tau"] = (g["ws"] + 900) - g["t"]
    g["btc_absret"] = g["btc_ret"].abs()
    for lo, hi in [(0, 120), (120, 300), (300, 600), (600, 840), (840, 900)]:
        m = (g["tau"] >= lo) & (g["tau"] < hi)
        print(f"  tau {lo:3d}-{hi:3d}s: spread={np.nanmean(g.loc[m,'btc_spr'])*100:.2f}c  "
              f"mid_vol(10s)={np.nanstd(g.loc[m,'btc_ret']):.4f}  "
              f"mean|mid-0.5|={np.nanmean((g.loc[m,'btc']-0.5).abs()):.3f}")

    print("\n=== D3: cross-sectional dislocation dispersion + reversion ===")
    spots = {c: rr.load_spot(p) for c, p in SPOT.items()}
    for c in ["btc", "eth", "sol", "xrp"]:
        ts_, px_ = spots[c]; sig = rr.realized_vol_per_s(px_, 1.0)
        s0 = rr.spot_at(ts_, px_, g["ws"].to_numpy() * 1000)
        st = rr.spot_at(ts_, px_, g["t"].to_numpy() * 1000)
        g[c + "_disloc"] = g[c].to_numpy() - fair_up(st, s0, sig, g["tau"].to_numpy())
    dis = g[[c + "_disloc" for c in ["btc", "eth", "sol", "xrp"]]]
    print(f"  mean |dislocation| by coin: " +
          ", ".join(f"{c}={g[c+'_disloc'].abs().mean():.3f}" for c in ["btc", "eth", "sol", "xrp"]))
    # cross-sectional: demeaned dislocation predict next 10s token return (reversion?)
    xs = dis.sub(dis.mean(axis=1), axis=0)
    fut = {c: g.groupby("ws")[c].shift(-1) - g[c] for c in ["btc", "eth", "sol", "xrp"]}
    X = np.concatenate([xs[c + "_disloc"].to_numpy() for c in ["btc", "eth", "sol", "xrp"]])
    Y = np.concatenate([fut[c].to_numpy() for c in ["btc", "eth", "sol", "xrp"]])
    ok = np.isfinite(X) & np.isfinite(Y)
    b = np.polyfit(X[ok], Y[ok], 1)
    print(f"  cross-sectional: next_ret ~ demeaned_disloc slope={b[0]:+.3f} "
          f"(n={ok.sum()}; <0 => XS reversion)")


if __name__ == "__main__":
    main()
