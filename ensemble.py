"""Two-Sigma/RenTec-style ML ensemble: combine many weak features to predict the
15m resolution and ask whether the model beats the MARKET PRICE out-of-sample by
more than the fee. Walk-forward (train first-half windows, test second-half),
one obs per (window, decision-time) clustered by window, net of corrected fee.

If the model's edge over the mid (model_prob - mid, traded when > fee) is positive
OOS with t>2.58, that's a real systematic edge. Otherwise price already spans the
signal set.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy.special import expit

import run_real as rr
from fairvalue import fair_up
import fees

TAUS = [600, 450, 300, 180]
SPOT = {"btc": "btc.npz", "eth": "ETHUSDT.npz", "sol": "SOLUSDT.npz", "xrp": "XRPUSDT.npz"}


def asof_mid(con, book, aid, t_ms):
    tg = pd.DataFrame({"asset_id": np.asarray(aid, str), "t_ms": np.asarray(t_ms, np.int64), "r": np.arange(len(aid))})
    con.register("tg", tg)
    o = con.execute(f"""SELECT tg.r,(CAST(b.best_bid AS DOUBLE)+CAST(b.best_ask AS DOUBLE))/2 mid,
       CAST(b.best_ask AS DOUBLE)-CAST(b.best_bid AS DOUBLE) spr
       FROM tg ASOF LEFT JOIN read_parquet('{book}') b
       ON tg.asset_id=b.asset_id AND tg.t_ms>=epoch_ms(b.timestamp) ORDER BY tg.r""").df()
    con.unregister("tg"); return o["mid"].to_numpy(), o["spr"].to_numpy()


def build():
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])
    spots = {c: rr.load_spot(p) for c, p in SPOT.items()}
    altw = pd.read_parquet("alt_windows.parquet")
    rows = []
    for tau in TAUS:
        g = w.copy(); g["t"] = g["window_start"] + (900 - tau); g["tau"] = tau
        rows.append(g)
    g = pd.concat(rows, ignore_index=True)
    aid = g["asset_id"].astype(str).to_numpy(); t = g["t"].to_numpy()
    mid, spr = asof_mid(con, "up_book.parquet", aid, t * 1000)
    g["mid"] = mid; g["spr"] = spr
    bt, bp = spots["btc"]
    s0 = rr.spot_at(bt, bp, g["window_start"].to_numpy() * 1000)
    st = rr.spot_at(bt, bp, t * 1000)
    sp1 = rr.spot_at(bt, bp, (t - 60) * 1000); sp3 = rr.spot_at(bt, bp, (t - 180) * 1000)
    sig = rr.realized_vol_per_s(bp, 1.0)
    g["fair"] = fair_up(st, s0, sig, g["tau"].to_numpy())
    g["ret_open"] = np.log(st / s0)
    g["ret_60"] = np.log(st / sp1); g["ret_180"] = np.log(st / sp3)
    # recent realized vol (60s)
    def rvol(tend):
        out = np.full(len(tend), np.nan)
        i1 = np.searchsorted(bt, tend * 1000); i0 = np.searchsorted(bt, (tend - 120) * 1000)
        for k in range(len(tend)):
            seg = bp[i0[k]:i1[k]]
            if len(seg) > 5:
                out[k] = np.std(np.diff(np.log(seg)))
        return out
    g["rvol"] = rvol(t)
    # flow imbalance up to t (up_trades)
    fl = con.execute("""SELECT w.window_start win, w.window_end,
          epoch_ms(t.timestamp)/1000.0 AS ts, CASE WHEN t.side='BUY' THEN t.size ELSE -t.size END sg, t.size sz
          FROM read_parquet('up_trades.parquet') t JOIN read_parquet('up_windows.parquet') w ON t.asset_id=w.asset_id
          WHERE w.resolved_up IS NOT NULL""").df()
    g["flow"] = np.nan
    for tau in TAUS:
        sel = g["tau"] == tau
        cut = g.loc[sel, "window_start"] + (900 - tau)
        agg = fl[fl["ts"] <= fl["win"] + (900 - tau)].groupby("win").apply(
            lambda x: x["sg"].sum() / max(x["sz"].sum(), 1), include_groups=False)
        g.loc[sel, "flow"] = g.loc[sel, "window_start"].map(agg).values
    # cross-asset: mean alt dislocation at t
    alt_disloc = []
    for coin in ["eth", "sol", "xrp"]:
        sub = altw[altw["coin"] == coin].set_index("window_start")["asset_id"]
        a = g["window_start"].map(sub).astype(str).to_numpy()
        m, _ = asof_mid(con, "alt_book.parquet", a, t * 1000)
        ts_, px_ = spots[coin]; s0a = rr.spot_at(ts_, px_, g["window_start"].to_numpy() * 1000); sta = rr.spot_at(ts_, px_, t * 1000)
        fa = fair_up(sta, s0a, rr.realized_vol_per_s(px_, 1.0), g["tau"].to_numpy())
        alt_disloc.append(m - fa)
    g["alt_disloc"] = np.nanmean(np.column_stack(alt_disloc), axis=1)
    g["mid_dev"] = g["mid"] - g["fair"]
    return g


def main():
    g = build()
    feats = ["mid", "fair", "ret_open", "ret_60", "ret_180", "rvol", "flow", "alt_disloc", "mid_dev", "spr", "tau"]
    g = g.dropna(subset=feats + ["resolved_up", "mid"]).reset_index(drop=True)
    g = g[(g["mid"] > 0.02) & (g["mid"] < 0.98)]
    midw = np.median(np.unique(g["window_start"]))
    tr = g[g["window_start"] < midw]; te = g[g["window_start"] >= midw]
    X = tr[feats].to_numpy(); y = tr["resolved_up"].to_numpy().astype(float)
    Xm = X.mean(0); Xs = X.std(0) + 1e-9
    Xz = (X - Xm) / Xs
    # ridge logistic via IRLS-free: simple regularized logistic (gradient)
    wv = np.zeros(Xz.shape[1]); b = 0.0; lam = 1.0; lr = 0.1
    for _ in range(3000):
        p = expit(Xz @ wv + b)
        gw = Xz.T @ (p - y) / len(y) + lam * wv / len(y)
        gb = np.mean(p - y)
        wv -= lr * gw; b -= lr * gb
    Xte = (te[feats].to_numpy() - Xm) / Xs
    pte = expit(Xte @ wv + b)
    yte = te["resolved_up"].to_numpy().astype(float)
    mid_te = te["mid"].to_numpy()
    brier_model = np.mean((pte - yte) ** 2); brier_mid = np.mean((mid_te - yte) ** 2)
    print(f"OOS Brier: model={brier_model:.4f}  vs  market mid={brier_mid:.4f}  "
          f"({'model better' if brier_model<brier_mid else 'mid better'})")
    # trading edge: buy up if model-mid>thr (taker, corrected crypto fee 0.07), hold to res
    def clt(a):
        a = a[np.isfinite(a)]; n = len(a); m = a.mean(); s = a.std(ddof=1); return n, m, m / s * np.sqrt(n)
    for thr in [0.0, 0.02, 0.05]:
        edge = pte - mid_te
        sidebuy = edge > thr; sidesell = edge < -thr
        pnl = np.full(len(te), np.nan)
        pnl[sidebuy] = yte[sidebuy] - mid_te[sidebuy] - np.array([fees.taker_fee(x, "crypto") for x in mid_te[sidebuy]])
        pnl[sidesell] = (1 - yte[sidesell]) - (1 - mid_te[sidesell]) - np.array([fees.taker_fee(x, "crypto") for x in mid_te[sidesell]])
        d = te.assign(pnl=pnl).dropna(subset=["pnl"])
        if len(d):
            per = d.groupby("window_start")["pnl"].mean().to_numpy()
            n, m, t = clt(per)
            print(f"  thr={thr:.2f}: trades={len(d)} n_win={n} net/trade={m:+.4f} t={t:+.2f}"
                  f"{'  <= EDGE' if m>0 and t>2.58 else ''}")


if __name__ == "__main__":
    main()
