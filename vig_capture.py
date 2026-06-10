"""Jane-Street-style VIG capture: be the bookmaker. Two readouts:

(1) FULL-FLOW maker: counterparty to EVERY taker trade on both Up and Down, held to
    resolution, fee-exempt + maker rebate. = the realistic "I make all the markets"
    PnL (includes adverse selection on net imbalance).
(2) RISKLESS matched vig: selling 1 Up + 1 Down simultaneously locks Up_ask+Down_ask-1
    (>=0 overround) with zero directional risk. Per window the matched, risk-free
    amount = min(up_buy_shares, down_buy_shares) * mean_overround. This is the prize a
    queue-winning 2-sided MM extracts; we report its size (capture still needs queue).
All window-clustered; corrected crypto rebate (0.07 basis).
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
        ["window_start", "window_end", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    dmap = pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]]
    w = w.merge(dmap, on="window_start", how="inner")
    up_a = dict(zip(w["up_asset"].astype(str), w["window_start"]))
    dn_a = dict(zip(w["down_asset"].astype(str), w["window_start"]))
    res = dict(zip(w["window_start"], w["resolved_up"]))

    up = pd.read_parquet("up_trades.parquet")
    dn = pd.read_parquet("down_trades.parquet")
    up["win"] = up["asset_id"].astype(str).map(up_a)
    dn["win"] = dn["asset_id"].astype(str).map(dn_a)
    up = up.dropna(subset=["win"]); dn = dn.dropna(subset=["win"])

    rows = []
    for win, ug in up.groupby("win"):
        dg = dn[dn["win"] == win]
        r = res[win]
        # cash & position from being counterparty to all flow (maker)
        # Up: taker BUY -> maker sells Up (+cash, short Up); taker SELL -> maker buys Up (-cash, long Up)
        def cashpos(g, token_pays):
            buy = g["side"] == "BUY"
            cash = np.sum(np.where(buy, g["price"] * g["size"], -g["price"] * g["size"]))
            pos = np.sum(np.where(buy, -g["size"], g["size"]))   # shares of token held by maker
            payout = pos * token_pays
            shares = g["size"].sum()
            rebate = np.sum(fees.maker_rebate(g["price"].to_numpy(), rate=REBATE_RATE) * g["size"].to_numpy())
            return cash + payout, shares, rebate
        up_pnl, up_sh, up_reb = cashpos(ug, r)
        dn_pnl, dn_sh, dn_reb = cashpos(dg, 1 - r)
        full_pnl = up_pnl + dn_pnl + up_reb + dn_reb
        total_sh = up_sh + dn_sh
        # riskless matched vig
        up_buy = ug.loc[ug["side"] == "BUY", "size"].sum()
        dn_buy = dg.loc[dg["side"] == "BUY", "size"].sum()
        up_buy_px = np.average(ug.loc[ug["side"] == "BUY", "price"], weights=ug.loc[ug["side"] == "BUY", "size"]) if up_buy > 0 else np.nan
        dn_buy_px = np.average(dg.loc[dg["side"] == "BUY", "price"], weights=dg.loc[dg["side"] == "BUY", "size"]) if dn_buy > 0 else np.nan
        overround = (up_buy_px + dn_buy_px - 1) if (up_buy > 0 and dn_buy > 0) else np.nan
        matched = min(up_buy, dn_buy)
        vig = matched * overround if np.isfinite(overround) else 0.0
        rows.append((win, full_pnl, total_sh, vig, matched, overround))
    d = pd.DataFrame(rows, columns=["win", "full_pnl", "shares", "vig", "matched", "overround"])

    print(f"=== VIG capture across {len(d)} windows ===")
    # full-flow maker per-share PnL
    per_share = (d["full_pnl"] / d["shares"]).to_numpy()
    n, m, t = clt(per_share)
    print(f"(1) FULL-FLOW maker (counterparty to all flow + rebate, hold to resolution):")
    print(f"    per-share: mean={m:+.5f} t={t:+.2f}  | total PnL={d['full_pnl'].sum():+,.0f} over {d['shares'].sum():,.0f} shares")
    print(f"(2) RISKLESS matched vig (queue-winning 2-sided MM):")
    print(f"    mean overround={np.nanmean(d['overround']):+.4f}  total matched shares={d['matched'].sum():,.0f}")
    print(f"    total risk-free vig=${d['vig'].sum():+,.0f}  (~{d['vig'].sum()/d['matched'].sum()*100:.2f}c per matched pair)")
    nb, mb, tb = clt((d["vig"] / d["matched"].replace(0, np.nan)).to_numpy())
    print(f"    per-window vig/pair: mean={mb:+.4f} t={tb:+.2f} (always >=0 by construction)")


if __name__ == "__main__":
    main()
