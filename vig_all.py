"""2-sided (Up+Down) maker over the COMBINED dataset (original Apr14-16 + extended
Apr17-27) to firm the bookmaker edge's significance. Gross vs +rebate, OOS halves,
window-clustered t, size-weighted bootstrap CI. Emits the per-window edge series.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import fees

REBATE_RATE = 0.07


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def load_windows():
    o = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    o = o.merge(pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]], on="window_start", how="inner")
    parts = [o]
    import os
    if os.path.exists("ext_windows.parquet"):
        e = pd.read_parquet("ext_windows.parquet")[["window_start", "up_asset", "down_asset", "resolved_up"]]
        parts.append(e)
    return pd.concat(parts, ignore_index=True).drop_duplicates("window_start")


def load_trades(paths):
    import os
    dfs = [pd.read_parquet(p) for p in paths if os.path.exists(p)]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def main():
    w = load_windows()
    up_a = dict(zip(w["up_asset"].astype(str), w["window_start"]))
    dn_a = dict(zip(w["down_asset"].astype(str), w["window_start"]))
    res = dict(zip(w["window_start"], w["resolved_up"]))
    up = load_trades(["up_trades.parquet", "up_trades_ext.parquet"])
    dn = load_trades(["down_trades.parquet", "down_trades_ext.parquet"])
    up["win"] = up["asset_id"].astype(str).map(up_a); dn["win"] = dn["asset_id"].astype(str).map(dn_a)
    up = up.dropna(subset=["win"]); dn = dn.dropna(subset=["win"])
    print(f"windows={len(w)}  up_trades={len(up)}  down_trades={len(dn)}")

    def cashpos(g, pays):
        buy = g["side"] == "BUY"
        cash = np.sum(np.where(buy, g["price"] * g["size"], -g["price"] * g["size"]))
        pos = np.sum(np.where(buy, -g["size"], g["size"]))
        reb = np.sum(fees.maker_rebate(g["price"].to_numpy(), rate=REBATE_RATE) * g["size"].to_numpy())
        return cash + pos * pays, g["size"].sum(), reb

    rows = []
    dn_by = dict(tuple(dn.groupby("win")))
    for win, ug in up.groupby("win"):
        dg = dn_by.get(win, ug.iloc[0:0]); r = res[win]
        upg, ush, urb = cashpos(ug, r); dng, dsh, drb = cashpos(dg, 1 - r)
        rows.append((win, upg + dng, urb + drb, ush + dsh))
    d = pd.DataFrame(rows, columns=["unit_id", "gross", "rebate", "shares"])
    d = d[d["shares"] > 0]
    d["ps_gross"] = d["gross"] / d["shares"]; d["ps_net"] = (d["gross"] + d["rebate"]) / d["shares"]
    d["pnl"] = d["ps_net"]

    print(f"=== 2-sided maker, COMBINED {len(d)} windows ===")
    for col, lab in [("ps_gross", "GROSS"), ("ps_net", "NET+rebate")]:
        n, m, t = clt(d[col].to_numpy()); print(f"  {lab:11} per-share mean={m:+.5f} t={t:+.2f}")
    mid = np.median(d["unit_id"])
    for lab, s in [("IS", d[d.unit_id < mid]), ("OOS", d[d.unit_id >= mid])]:
        n, m, t = clt(s["ps_net"].to_numpy()); print(f"  {lab:3} NET mean={m:+.5f} t={t:+.2f}")
    rng = np.random.default_rng(0)
    num = (d["gross"] + d["rebate"]).to_numpy(); den = d["shares"].to_numpy()
    boot = [num[i].sum() / den[i].sum() for i in (rng.integers(0, len(num), len(num)) for _ in range(2000))]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"  size-wtd NET={num.sum()/den.sum():+.5f}  95% CI=[{lo:+.5f},{hi:+.5f}] {'CI>0' if lo>0 else ''}")
    d[["unit_id", "pnl"]].to_parquet("edge_2sided_maker.parquet", index=False)


if __name__ == "__main__":
    main()
