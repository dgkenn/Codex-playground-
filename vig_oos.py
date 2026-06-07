"""Dig into the 2-sided (Up+Down) maker: is it robustly positive? Decompose
gross vs rebate, OOS halves, bootstrap CI, and emit a per-window edge series for the
portfolio combiner.
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


def main():
    con = duckdb.connect()
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    dmap = pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]]
    w = w.merge(dmap, on="window_start", how="inner")
    up_a = dict(zip(w["up_asset"].astype(str), w["window_start"]))
    dn_a = dict(zip(w["down_asset"].astype(str), w["window_start"]))
    res = dict(zip(w["window_start"], w["resolved_up"]))
    up = pd.read_parquet("up_trades.parquet"); dn = pd.read_parquet("down_trades.parquet")
    up["win"] = up["asset_id"].astype(str).map(up_a); dn["win"] = dn["asset_id"].astype(str).map(dn_a)
    up = up.dropna(subset=["win"]); dn = dn.dropna(subset=["win"])

    def cashpos(g, pays):
        buy = g["side"] == "BUY"
        cash = np.sum(np.where(buy, g["price"] * g["size"], -g["price"] * g["size"]))
        pos = np.sum(np.where(buy, -g["size"], g["size"]))
        reb = np.sum(fees.maker_rebate(g["price"].to_numpy(), rate=REBATE_RATE) * g["size"].to_numpy())
        return cash + pos * pays, g["size"].sum(), reb

    rows = []
    for win, ug in up.groupby("win"):
        dg = dn[dn["win"] == win]; r = res[win]
        upg, ush, urb = cashpos(ug, r); dng, dsh, drb = cashpos(dg, 1 - r)
        gross = upg + dng; reb = urb + drb; sh = ush + dsh
        rows.append((win, gross, reb, sh))
    d = pd.DataFrame(rows, columns=["unit_id", "gross", "rebate", "shares"])
    d["ps_gross"] = d["gross"] / d["shares"]
    d["ps_net"] = (d["gross"] + d["rebate"]) / d["shares"]
    d["pnl"] = d["ps_net"]   # for portfolio combiner

    print(f"=== 2-sided (Up+Down) maker, {len(d)} windows ===")
    for col, lab in [("ps_gross", "GROSS (no rebate)"), ("ps_net", "NET (+rebate)")]:
        n, m, t = clt(d[col].to_numpy())
        print(f"  {lab:18} per-share mean={m:+.5f} t={t:+.2f}")
    mid = np.median(d["unit_id"])
    for lab, s in [("IS (first half)", d[d.unit_id < mid]), ("OOS (second half)", d[d.unit_id >= mid])]:
        n, m, t = clt(s["ps_net"].to_numpy())
        print(f"  {lab:18} NET per-share mean={m:+.5f} t={t:+.2f}")
    # size-weighted economic + bootstrap CI over windows
    rng = np.random.default_rng(0)
    num = d["gross"].to_numpy() + d["rebate"].to_numpy(); den = d["shares"].to_numpy()
    boot = [num[i].sum() / den[i].sum() for i in (rng.integers(0, len(num), len(num)) for _ in range(2000))]
    lo, hi = np.percentile(boot, [2.5, 97.5]); pooled = num.sum() / den.sum()
    print(f"  size-weighted NET per-share={pooled:+.5f}  bootstrap 95% CI=[{lo:+.5f},{hi:+.5f}]"
          f"  {'<= CI>0' if lo>0 else ''}")
    d[["unit_id", "pnl"]].to_parquet("edge_2sided_maker.parquet", index=False)
    print("  -> wrote edge_2sided_maker.parquet for portfolio combiner")


if __name__ == "__main__":
    main()
