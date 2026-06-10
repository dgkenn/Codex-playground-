"""Refine the inventory-capped 2-sided maker before paper trading. Adjacent ideas:
  - per-quote SIZE LIMIT (post only S shares at the touch): a large/toxic order only
    fills your S and walks past -> less adverse selection -> better GROSS (a cushion
    beyond the rebate).
  - STOP quoting in the final informed sprint (tau < cutoff).
  - inventory CAP sweep (risk/Sharpe knob).
Report GROSS (no rebate) and NET (+rebate), IS/OOS, and a drawdown/Sharpe view.
Pre-specified configs (no grid-search cherry-picking).
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
    up_a = dict(zip(o.up_asset.astype(str), o.window_start)); dn_a = dict(zip(o.down_asset.astype(str), o.window_start))
    res = dict(zip(o.window_start, o.resolved_up))
    up = pd.read_parquet("up_trades.parquet"); up["win"] = up.asset_id.astype(str).map(up_a); up["tok"] = "U"
    dn = pd.read_parquet("down_trades.parquet"); dn["win"] = dn.asset_id.astype(str).map(dn_a); dn["tok"] = "D"
    allt = pd.concat([up, dn], ignore_index=True).dropna(subset=["win"]).sort_values(["win", "timestamp"])
    ts = allt["timestamp"]
    if pd.api.types.is_datetime64_any_dtype(ts):
        allt["tsec"] = pd.to_datetime(ts, utc=True).to_numpy().astype("datetime64[s]").view("int64").astype(float)
    else:
        allt["tsec"] = ts.astype(float) / 1000.0
    allt["tau"] = (allt["win"] + 900) - allt["tsec"]
    return allt, res


def sim(allt, res, post_size=np.inf, cap=np.inf, stop_tau=0.0, rebate_rate=REBATE_RATE):
    out = []
    for win, g in allt.groupby("win"):
        delta = up_inv = dn_inv = cash = reb = 0.0
        arr = g[["tok", "side", "price", "size", "tau"]].to_numpy()
        for tok, side, price, size, tau in arr:
            if tau < stop_tau:                       # stop quoting late
                continue
            fill = min(size, post_size)              # posted depth limit
            d_per = (-1.0 if (tok == "U") == (side == "BUY") else 1.0)  # Up-delta sign per share maker takes
            # cap net delta
            if abs(delta + d_per * fill) > cap:
                room = max(0.0, cap - abs(delta)) if (delta + d_per * fill) * d_per > 0 else fill
                fill = min(fill, room)
            if fill <= 0:
                continue
            maker_sells = (side == "BUY")
            cash += (price if maker_sells else -price) * fill
            if tok == "U":
                up_inv += (-fill if maker_sells else fill)
            else:
                dn_inv += (-fill if maker_sells else fill)
            delta += d_per * fill
            reb += fees.maker_rebate(price, rate=rebate_rate) * fill
        r = res[win]
        settle = up_inv * r + dn_inv * (1 - r)
        vol = g["size"].sum()
        out.append((win, cash + settle, reb, vol))
    d = pd.DataFrame(out, columns=["unit_id", "gross", "rebate", "vol"])
    d = d[d["vol"] > 0]
    d["ps_gross"] = d["gross"] / d["vol"]; d["ps_net"] = (d["gross"] + d["rebate"]) / d["vol"]
    return d


def report(name, d):
    mid = np.median(d["unit_id"])
    ng, mg, tg = clt(d["ps_gross"].to_numpy())
    nn, mn, tn = clt(d["ps_net"].to_numpy())
    _, _, to = clt(d[d.unit_id >= mid]["ps_net"].to_numpy())
    # drawdown / sharpe on per-window net $ ordered by time
    seq = d.sort_values("unit_id")["gross"].to_numpy() + d.sort_values("unit_id")["rebate"].to_numpy()
    cum = np.cumsum(seq); dd = np.max(np.maximum.accumulate(cum) - cum) if len(seq) else 0
    sharpe = mn / d["ps_net"].std(ddof=1) if d["ps_net"].std() > 0 else np.nan
    print(f"  {name:34} GROSS t={tg:+5.2f}({mg:+.5f}) | NET t={tn:+5.2f} OOS={to:+5.2f} ps={mn:+.5f} "
          f"| $tot={seq.sum():+,.0f} maxDD=${dd:,.0f}")


def main():
    allt, res = load()
    print(f"trades={len(allt)} windows={allt['win'].nunique()}\n")
    print("BASELINE & inventory-cap sweep (post_size=inf):")
    for cap in [25, 100, 400]:
        report(f"cap={cap}", sim(allt, res, cap=cap))
    print("\nREFINEMENT 1 - per-quote SIZE LIMIT (cap=100):")
    for ps in [10, 25, 50, 100]:
        report(f"post_size={ps}", sim(allt, res, post_size=ps, cap=100))
    print("\nREFINEMENT 2 - stop quoting late + small post (cap=100, post_size=25):")
    for st in [0, 60, 120, 180]:
        report(f"stop_tau<{st}s", sim(allt, res, post_size=25, cap=100, stop_tau=st))
    print("\nREFINEMENT 3 - GROSS cushion check (post_size=25, cap=50, stop<120):")
    report("refined combo", sim(allt, res, post_size=25, cap=50, stop_tau=120))


if __name__ == "__main__":
    main()
