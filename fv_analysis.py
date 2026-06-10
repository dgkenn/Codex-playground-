"""TIER 1 (rigorous): does spot-implied fair value actually identify fills that hurt
the maker AT THE HORIZON WE HOLD TO (resolution), risk-adjusted?

Reviewer's correction to fv_maker.py: a t-stat is the wrong yardstick for a gate. A
gate's whole job is to trade less, and t ~ (mean/std)*sqrt(n), so cutting fills drops
t mechanically through n -- "14.6 -> 3.5" can't separate "cut edge" from "cut volume".
What discriminates instead:

  (1) The risk unit is the WINDOW (fills within a window are correlated). Window-level
      Sharpe = mean/std of per-window P&L over n=288 windows -- n is FIXED whether or
      not we gate, so it pays no n-reduction tax. This is the honest gate metric.
  (2) Score each fill by its RESOLUTION-HORIZON P&L (what we actually earn holding to
      settlement), not the short-horizon fair-value flag. A fill flagged "29c toxic"
      at fill time can settle flat/positive if the move was noise (within-window mean
      reversion -- the regime a passive maker is structurally long).
  (3) Show the DISTRIBUTION: per-fill resolution-P&L by fair-edge decile (does the flag
      predict true P&L at all?), and whether the targeted band even BITES.

Per-fill resolution P&L (marginal, uncapped -- the per-trade view the reviewer asked
for): maker takes the opposite of the taker.
    settle = resolved_up (Up token) or 1-resolved_up (Down token)
    sells  = (taker side == BUY)
    pnl/sh = (price - settle if sells else settle - price) + maker_rebate(price)
    fair_edge/sh = (price - fair_tok if sells else fair_tok - price)

    python fv_analysis.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import fees
from fairvalue import fair_up, realized_vol_per_s

REBATE_RATE = 0.07


def load_spot():
    z = np.load("btc.npz")
    ts = np.asarray(z["ts"], dtype=np.int64); px = np.asarray(z["price"], dtype=float)
    o = np.argsort(ts); return ts[o], px[o]


def load_trades():
    o = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "window_end", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    o = o.merge(pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]], on="window_start")
    up_a = dict(zip(o.up_asset.astype(str), o.window_start))
    dn_a = dict(zip(o.down_asset.astype(str), o.window_start))
    res = dict(zip(o.window_start, o.resolved_up)); wend = dict(zip(o.window_start, o.window_end))

    def trades(paths, amap, tok):
        dfs = [pd.read_parquet(p) for p in paths if os.path.exists(p)]
        if not dfs:
            return pd.DataFrame()
        d = pd.concat(dfs, ignore_index=True)
        d["win"] = d.asset_id.astype(str).map(amap); d["tok"] = tok
        return d.dropna(subset=["win"])
    up = trades(["up_trades.parquet"], up_a, "U")
    dn = trades(["down_trades.parquet"], dn_a, "D")
    allt = pd.concat([up, dn], ignore_index=True)
    # timestamp dtype is datetime64[us]; convert to ms robustly (astype int64 gives us,
    # not ns -- the source of the earlier tau bug). Go via datetime64[ms].
    allt["t_ms"] = pd.to_datetime(allt["timestamp"], utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    allt["res"] = allt.win.map(res); allt["wend"] = allt.win.map(wend)
    return allt.dropna(subset=["res", "wend"]).reset_index(drop=True)


def build(allt, ts_ms, px, sigma):
    """Vectorized per-fill: fair_edge (short horizon) and res_pnl (resolution horizon)."""
    win = allt.win.to_numpy(); t_ms = allt.t_ms.to_numpy(np.int64)
    tok_u = (allt.tok.to_numpy() == "U"); sells = (allt.side.to_numpy() == "BUY")
    price = allt.price.to_numpy(float); size = allt["size"].to_numpy(float)
    res = allt.res.to_numpy(float); wend = allt.wend.to_numpy(float)
    s0 = px[np.clip(np.searchsorted(ts_ms, win.astype(np.int64) * 1000, "right") - 1, 0, len(px) - 1)]
    st = px[np.clip(np.searchsorted(ts_ms, t_ms, "right") - 1, 0, len(px) - 1)]
    tau = np.maximum(wend - t_ms / 1000.0, 0.0)
    fu = fair_up(st, s0, sigma, tau)
    fair_tok = np.where(tok_u, fu, 1.0 - fu)
    settle = np.where(tok_u, res, 1.0 - res)
    reb = fees.maker_rebate(price, rate=REBATE_RATE)
    res_pnl = np.where(sells, price - settle, settle - price) + reb        # per-share, to resolution
    fair_edge = np.where(sells, price - fair_tok, fair_tok - price)         # per-share, at fill
    out = pd.DataFrame({"win": win, "size": size, "tau": tau, "fair_edge": fair_edge,
                        "res_pnl": res_pnl})
    return out[(out.tau >= 0) & (out.tau <= 900)].reset_index(drop=True)  # in-window fills only


def sharpe(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 2:
        return (len(x), np.nan, np.nan, np.nan)
    m, s = x.mean(), x.std(ddof=1)
    return (len(x), m, s, (m / s if s > 0 else np.nan))


def window_pnl(df, mask):
    """Per-window per-share P&L over the fills in mask. n_windows is FIXED."""
    d = df[mask]
    g = d.groupby("win").apply(lambda x: (x.res_pnl * x["size"]).sum() / x["size"].sum(),
                               include_groups=False)
    return g.to_numpy()


def win_sharpe_line(tag, df, mask):
    g = window_pnl(df, mask)
    n, m, s, sh = sharpe(g)
    tot = (df[mask].res_pnl * df[mask]["size"]).sum()
    print(f"    {tag:26}: windows={n} per-win mean={m:+.5f} std={s:.5f} Sharpe={sh:+.3f} "
          f"| total=${tot:+,.0f} | fills={mask.sum():,}")
    return sh, m


def main():
    ts_ms, px = load_spot()
    sigma = realized_vol_per_s(px, 1.0)
    allt = load_trades()
    df = build(allt, ts_ms, px, sigma)
    n = len(df)
    print(f"fills={n:,}  windows={df.win.nunique()}  sigma={sigma:.3e}")
    print(f"per-fill resolution P&L: mean={df.res_pnl.mean():+.5f} "
          f"(this is the maker edge; large variance is expected -- it's a 0/1 bet)")
    print(f"corr(fair_edge, res_pnl) = {np.corrcoef(df.fair_edge, df.res_pnl)[0,1]:+.4f}  "
          f"(if the flag predicted toxicity, MORE-negative fair_edge -> MORE-negative res_pnl)")

    # --- (3) DISTRIBUTION: per-fill resolution P&L by fair-edge decile ---
    print("\n[decile of fair_edge -> resolution-horizon P&L per fill]  "
          "(does 'toxic' (low edge) actually settle worse?)")
    df["bk"] = pd.qcut(df.fair_edge, 10, labels=False, duplicates="drop")
    print(f"    {'decile':6} {'mean_fair_edge':>14} {'n':>9} {'mean_resPnL':>12} {'std':>8} {'Sharpe':>8}")
    for b, g in df.groupby("bk"):
        nn, m, s, sh = sharpe(g.res_pnl)
        print(f"    {int(b):6d} {g.fair_edge.mean():>14.4f} {nn:>9,} {m:>12.5f} {s:>8.4f} {sh:>8.3f}")

    # --- (1)+(2) GATE on the right metric: window Sharpe (n fixed) at resolution horizon ---
    print("\n[binary gate -- window-level Sharpe, n=288 FIXED so no n-reduction tax]")
    all_mask = pd.Series(True, index=df.index)
    win_sharpe_line("baseline (keep all)", df, all_mask)
    for thr in [0.02, 0.05, 0.10]:
        win_sharpe_line(f"global gate thr={thr}", df, df.fair_edge >= -thr)

    # --- targeted band: does it even BITE? gated-vs-kept WITHIN the band ---
    print("\n[targeted band tau in 120-720s AND -0.15<=fair_edge<-thr: bite + within-band P&L]")
    band = (df.tau >= 120) & (df.tau <= 720)
    for thr in [0.02, 0.03, 0.05]:
        cut = band & (df.fair_edge >= -0.15) & (df.fair_edge < -thr)
        nb, mb, sb, shb = sharpe(df[cut].res_pnl)
        comp = band & ~cut
        nc, mc, _, shc = sharpe(df[comp].res_pnl)
        print(f"    thr={thr}: gates {cut.sum():,} fills ({cut.sum()/n:.2%}) | "
              f"gated res_pnl mean={mb:+.5f} Sharpe={shb:+.3f} vs kept-in-band mean={mc:+.5f}")
        win_sharpe_line(f"  targeted thr={thr}", df, ~cut)

    # --- IS/OOS split (pre-registered: first vs second half of windows by time) ---
    print("\n[OOS: split windows by median start; same gates evaluated on each half]")
    med = df.win.median()
    for half, hm in (("IS (early)", df.win < med), ("OOS (late)", df.win >= med)):
        print(f"  {half}:")
        win_sharpe_line("baseline", df[hm], pd.Series(True, index=df[hm].index))
        for thr in [0.05, 0.10]:
            sub = df[hm]
            win_sharpe_line(f"global gate thr={thr}", sub, sub.fair_edge >= -thr)

    # --- (alt use) continuous SIZING instead of binary skip ---
    print("\n[continuous sizing w=clip(1+k*fair_edge,0,2): does scaling beat skipping?]")
    for k in [2.0, 5.0, 10.0]:
        w = np.clip(1.0 + k * df.fair_edge.to_numpy(), 0.0, 2.0)
        d2 = df.copy(); d2["size"] = d2["size"] * w
        g = d2.groupby("win").apply(lambda x: (x.res_pnl * x["size"]).sum() / max(x["size"].sum(), 1e-9),
                                    include_groups=False).to_numpy()
        nn, m, s, sh = sharpe(g)
        tot = (d2.res_pnl * d2["size"]).sum()
        print(f"    k={k:>4}: per-win mean={m:+.5f} Sharpe={sh:+.3f} total=${tot:+,.0f}")


if __name__ == "__main__":
    main()
