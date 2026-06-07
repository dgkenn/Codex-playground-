"""TIER 1: fair-value-GATED 2-sided maker.

The reviewer's #1 idea: build a probability model from a low-latency SPOT feed and
let it drive quoting, instead of pegging to the book. The structural-vig maker
(vig_hedged.py) takes the opposite of every taker within an inventory cap. Its one
real risk is ADVERSE SELECTION: an informed taker hits our stale quote the instant
BTC ticks, before the book reprices.

Here we test whether an EXTERNAL fair value catches those pickoffs. For each fill we
compute, from the BTC spot tape, the model probability the window resolves Up:

    fair_up = Phi( log(St/S0) / (sigma*sqrt(tau)) )          [fairvalue.fair_up]

and the fair price of the traded token (Up -> fair_up, Down -> 1-fair_up). Our edge
on a fill is (price - fair) when we SELL the token, (fair - price) when we BUY. The
GATE skips a fill whose fair-value edge is worse than -thresh: i.e. spot already says
this taker is on the right side of us beyond a threshold => toxic, get out of the way.

CRITICAL CONTRAST: book-mid markout toxicity filtering was already tested and HURTS
(refine/combo_maker: it overfits noise and cuts the structural vig). The open question
is whether the spot feed -- the ACTUAL resolution driver, not a noisy book echo -- is
better information. We report it honestly either way: baseline vs gated, window-
clustered t, OOS halves, fills retained, $ total.

    python fv_maker.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import fees
from fairvalue import fair_up, realized_vol_per_s

REBATE_RATE = 0.07


def clt(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    n = len(a); m = a.mean() if n else np.nan
    s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def load_spot():
    z = np.load("btc.npz")
    ts = np.asarray(z["ts"], dtype=np.int64)              # ms
    px = np.asarray(z["price"], dtype=float)
    o = np.argsort(ts)
    return ts[o], px[o]


def spot_at(ts_ms, px, t_ms):
    """Last spot at-or-before t_ms (step-left). Array-safe."""
    i = np.searchsorted(ts_ms, t_ms, side="right") - 1
    i = np.clip(i, 0, len(px) - 1)
    return px[i]


def load_trades():
    o = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "window_end", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    o = o.merge(pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]], on="window_start")
    if os.path.exists("ext_windows.parquet"):
        e = pd.read_parquet("ext_windows.parquet")[["window_start", "up_asset", "down_asset", "resolved_up"]]
        e = e.merge(o[["window_start", "window_end"]], on="window_start", how="left")
        o = pd.concat([o, e], ignore_index=True).drop_duplicates("window_start")
    o = o.dropna(subset=["window_end"])
    up_a = dict(zip(o.up_asset.astype(str), o.window_start))
    dn_a = dict(zip(o.down_asset.astype(str), o.window_start))
    res = dict(zip(o.window_start, o.resolved_up))
    wend = dict(zip(o.window_start, o.window_end))

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
    allt["t_ms"] = pd.to_datetime(allt["timestamp"], utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    return res, wend, allt


def sim(allt, res, wend, ts_ms, px, sigma, cap, gate=None,
        tau_lo=0.0, tau_hi=1e9, edge_floor=-1e9):
    """One pass. gate=None -> baseline (take everything within cap). gate=thr ->
    skip fills whose fair-value edge to us < -thr. The TARGETED variant only gates
    inside a trust regime: tau in [tau_lo,tau_hi] (model not saturated, window under
    way) and edge >= edge_floor (exclude the saturated extremes that the hard gate
    over-cut). Returns per-window per-share pnl plus retention / skipped-edge diag."""
    out = []
    kept = skipped = 0
    skip_edge = []        # fair-edge of the fills the gate threw away (should be very negative)
    for win, g in allt.groupby("win"):
        we = wend[win]
        s0 = float(spot_at(ts_ms, px, int(win) * 1000))
        delta = 0.0; cash = 0.0; reb = 0.0; up_inv = 0.0; dn_inv = 0.0
        arr = g[["tok", "side", "price", "size", "t_ms"]].to_numpy()
        for tok, side, price, size, t_ms in arr:
            tau = max(float(we) - t_ms / 1000.0, 0.0)
            st = float(spot_at(ts_ms, px, int(t_ms)))
            fu = fair_up(st, s0, sigma, tau)
            fair_tok = fu if tok == "U" else (1.0 - fu)
            maker_sells = (side == "BUY")           # taker buys => maker sells the token
            # our fair-value edge per share on this fill
            edge = (price - fair_tok) if maker_sells else (fair_tok - price)
            in_regime = (tau_lo <= tau <= tau_hi) and (edge >= edge_floor)
            if gate is not None and in_regime and edge < -gate:
                skipped += 1; skip_edge.append(edge)
                continue
            kept += 1
            if tok == "U":
                d_delta = -size if side == "BUY" else size
            else:
                d_delta = size if side == "BUY" else -size
            if abs(delta + d_delta) > cap:
                room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else size
                fill = min(size, room)
            else:
                fill = size
            if fill <= 0:
                continue
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
    diag = (kept, skipped, float(np.mean(skip_edge)) if skip_edge else float("nan"))
    return pd.DataFrame(out, columns=["unit_id", "pnl_abs", "vol"]), diag


def report(tag, d):
    d = d.copy(); d["pnl"] = d["pnl_abs"] / d["vol"]
    n, m, t = clt(d["pnl"].to_numpy())
    mid = np.median(d["unit_id"])
    _, _, ti = clt(d[d.unit_id < mid]["pnl"].to_numpy())
    _, _, to = clt(d[d.unit_id >= mid]["pnl"].to_numpy())
    tot = d["pnl_abs"].sum()
    print(f"  {tag:22}: per-share mean={m:+.5f} t={t:+.2f} | IS t={ti:+.2f} OOS t={to:+.2f} "
          f"| total=${tot:+,.0f}")
    return m, t, to, tot


def main():
    ts_ms, px = load_spot()
    sigma = realized_vol_per_s(px, 1.0)
    res, wend, allt = load_trades()
    nwin = allt["win"].nunique()
    print(f"windows={nwin}  trades={len(allt)}  sigma_per_s={sigma:.3e}  "
          f"spot {pd.to_datetime(ts_ms[0],unit='ms'):%Y-%m-%d}..{pd.to_datetime(ts_ms[-1],unit='ms'):%Y-%m-%d}")
    for cap in [50, 100]:
        print(f"cap={cap}")
        base, _ = sim(allt, res, wend, ts_ms, px, sigma, cap, gate=None)
        report("baseline (no gate)", base)
        for thr in [0.02, 0.05, 0.10]:
            d, (kept, skp, se) = sim(allt, res, wend, ts_ms, px, sigma, cap, gate=thr)
            keep_pct = kept / max(kept + skp, 1)
            report(f"gate thr={thr:.2f}", d)
            print(f"      -> kept {keep_pct:.1%} of fills, skipped {skp} "
                  f"(mean fair-edge of skipped={se:+.4f})")
    # TARGETED gate: only where the model is trustworthy (mid-window) and edge is a
    # moderate mispricing, not a saturated extreme. Best case for the reviewer's idea.
    print("cap=50 TARGETED (tau 120-720s, -0.15<=edge<-thr)")
    base, _ = sim(allt, res, wend, ts_ms, px, sigma, 50, gate=None)
    report("baseline (no gate)", base)
    for thr in [0.02, 0.03, 0.05]:
        d, (kept, skp, se) = sim(allt, res, wend, ts_ms, px, sigma, 50, gate=thr,
                                 tau_lo=120, tau_hi=720, edge_floor=-0.15)
        keep_pct = kept / max(kept + skp, 1)
        report(f"targeted thr={thr:.2f}", d)
        print(f"      -> kept {keep_pct:.1%} of fills, skipped {skp} "
              f"(mean fair-edge of skipped={se:+.4f})")


if __name__ == "__main__":
    main()
