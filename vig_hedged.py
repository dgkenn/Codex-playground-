"""Inventory-capped 2-sided market maker (the paper-tradeable bookmaker).

Quote both Up and Down near the touch; take the other side of each taker trade ONLY
while net delta stays within a cap (else skip = withdraw that side). Net delta is in
Up-equivalent units (long Up = +, long Down = -, since Up+Down=1). Capping bounds the
directional risk -> lower variance -> sharper edge. PnL = cash + settle + maker rebate.

Window-clustered + OOS + bootstrap. Emits per-window edge for the portfolio combiner.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import fees

REBATE_RATE = 0.07


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def load():
    o = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    o = o.merge(pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]], on="window_start")
    parts = [o]
    if os.path.exists("ext_windows.parquet"):
        parts.append(pd.read_parquet("ext_windows.parquet")[["window_start", "up_asset", "down_asset", "resolved_up"]])
    w = pd.concat(parts, ignore_index=True).drop_duplicates("window_start")
    up_a = dict(zip(w.up_asset.astype(str), w.window_start)); dn_a = dict(zip(w.down_asset.astype(str), w.window_start))
    res = dict(zip(w.window_start, w.resolved_up))

    def trades(paths, amap, tok):
        dfs = [pd.read_parquet(p) for p in paths if os.path.exists(p)]
        if not dfs:
            return pd.DataFrame()
        d = pd.concat(dfs, ignore_index=True)
        d["win"] = d.asset_id.astype(str).map(amap); d["tok"] = tok
        return d.dropna(subset=["win"])
    up = trades(["up_trades.parquet", "up_trades_ext.parquet"], up_a, "U")
    dn = trades(["down_trades.parquet", "down_trades_ext.parquet"], dn_a, "D")
    allt = pd.concat([up, dn], ignore_index=True).sort_values(["win", "timestamp"])
    return w, res, allt


def sim(allt, res, cap):
    out = []
    for win, g in allt.groupby("win"):
        delta = 0.0; cash = 0.0; reb = 0.0; up_inv = 0.0; dn_inv = 0.0
        gp = g[["tok", "side", "price", "size"]].to_numpy()
        for tok, side, price, size in gp:
            # maker takes opposite of taker; delta sign in Up-equivalent
            if tok == "U":
                d_delta = -size if side == "BUY" else size      # taker buys Up -> maker short Up
            else:
                d_delta = size if side == "BUY" else -size       # taker buys Down -> maker short Down = +Up delta
            # cap: only fill the portion keeping |delta|<=cap
            if abs(delta + d_delta) > cap:
                room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else size
                fill = min(size, room)
            else:
                fill = size
            if fill <= 0:
                continue
            f = fill / size
            # maker cash: sells (+price), buys (-price)
            maker_sells = (side == "BUY")
            sign = 1.0 if maker_sells else -1.0
            cash += sign * price * fill
            if tok == "U":
                up_inv += (-fill if maker_sells else fill)
            else:
                dn_inv += (-fill if maker_sells else fill)
            delta += (d_delta / size) * fill
            reb += fees.maker_rebate(price, rate=REBATE_RATE) * fill
        r = res[win]
        pnl = cash + up_inv * r + dn_inv * (1 - r) + reb
        vol = g["size"].sum()
        out.append((win, pnl, vol))
    return pd.DataFrame(out, columns=["unit_id", "pnl_abs", "vol"])


def main():
    w, res, allt = load()
    print(f"windows={len(allt['win'].unique())}  trades={len(allt)}")
    for cap in [25, 100, 400, 1e9]:
        d = sim(allt, res, cap)
        d["pnl"] = d["pnl_abs"] / d["vol"]            # per-share
        n, m, t = clt(d["pnl"].to_numpy())
        mid = np.median(d["unit_id"])
        _, mi, ti = clt(d[d.unit_id < mid]["pnl"].to_numpy())
        _, mo, to = clt(d[d.unit_id >= mid]["pnl"].to_numpy())
        tot = d["pnl_abs"].sum()
        label = "no cap" if cap > 1e8 else f"cap={int(cap)}"
        print(f"  {label:9}: per-share mean={m:+.5f} t={t:+.2f} | IS t={ti:+.2f} OOS t={to:+.2f} "
              f"| total=${tot:+,.0f}")
        if cap == 100:
            d[["unit_id", "pnl"]].to_parquet("edge_2sided_maker.parquet", index=False)


if __name__ == "__main__":
    main()
