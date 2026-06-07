"""TRUE queue-model fill backtest using MEASURED touch depth (fetch_depth.py).

Replaces the phi assumption with measured queue dynamics: when a taker trade of size S hits
our side, the displayed depth D ahead of us is consumed first; we fill min(max(S - alpha*D, 0), Q),
where Q is our quote size and alpha in [0,1] is our position within the displayed queue (the one
small, BOUNDED remaining assumption -- alpha=1 = we just joined / back of touch; alpha=0 = front).

Special cases tie it to prior work:
  alpha=0, Q=inf  ==  the offline replay (win the whole trade)  -> sanity-check vs +64/win
  alpha=1, Q=20   ==  realistic: behind the measured depth, live post size
We sweep alpha and Q and report the MEASURED fill rate + net/gross/rebate -- no phi guess.

    python queue_sim.py
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

import fees

REBATE = 0.07
INF = 10**9


def load_depth():
    """Per-asset touch-size series: dict asset_id -> (ts_ms[], bid_size[], ask_size[]) forward-filled."""
    files = glob.glob("depth_parts/depth_*.parquet")
    if not files:
        return {}
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["ts_ms"] = pd.to_datetime(df["timestamp"], utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    df["asset_id"] = df.asset_id.astype(str)
    # a row is a bid-touch update if side BUY & price==best_bid; ask-touch update if SELL & price==best_ask
    bidupd = (df.side == "BUY") & (np.isclose(df.price, df.best_bid))
    askupd = (df.side == "SELL") & (np.isclose(df.price, df.best_ask))
    df["bid_size"] = np.where(bidupd, df["size"], np.nan)
    df["ask_size"] = np.where(askupd, df["size"], np.nan)
    df = df.sort_values(["asset_id", "ts_ms"])
    df["bid_size"] = df.groupby("asset_id")["bid_size"].ffill()
    df["ask_size"] = df.groupby("asset_id")["ask_size"].ffill()
    df["best_bid"] = df.groupby("asset_id")["best_bid"].ffill()
    df["best_ask"] = df.groupby("asset_id")["best_ask"].ffill()
    out = {}
    for a, g in df.groupby("asset_id"):
        out[a] = (g.ts_ms.to_numpy(), g.bid_size.to_numpy(), g.ask_size.to_numpy(),
                  g.best_bid.to_numpy(), g.best_ask.to_numpy())
    return out


def load_trades_with_assets():
    """Trades with asset_id kept, mapped to window/res/tok/wend. April-14 windows w/ depth."""
    o = pd.read_parquet("up_windows.parquet").dropna(subset=["resolved_up"])[
        ["window_start", "window_end", "asset_id", "resolved_up"]].rename(columns={"asset_id": "up_asset"})
    o = o.merge(pd.read_parquet("down_map.parquet")[["window_start", "down_asset"]], on="window_start")
    up_a = dict(zip(o.up_asset.astype(str), o.window_start)); dn_a = dict(zip(o.down_asset.astype(str), o.window_start))
    res = dict(zip(o.window_start, o.resolved_up)); wend = dict(zip(o.window_start, o.window_end))

    def trades(path, amap, tok):
        if not os.path.exists(path):
            return pd.DataFrame()
        d = pd.read_parquet(path); d["win"] = d.asset_id.astype(str).map(amap); d["tok"] = tok
        return d.dropna(subset=["win"])
    up = trades("up_trades.parquet", up_a, "U"); dn = trades("down_trades.parquet", dn_a, "D")
    allt = pd.concat([up, dn], ignore_index=True)
    allt["asset_id"] = allt.asset_id.astype(str)
    allt["t_ms"] = pd.to_datetime(allt["timestamp"], utc=True).to_numpy().astype("datetime64[ms]").view("int64")
    allt["res"] = allt.win.map(res); allt["wend"] = allt.win.map(wend)
    return allt.dropna(subset=["res"]).sort_values(["win", "t_ms"])


def depth_at(depth, asset, t_ms, which):
    """Return (touch_size, touch_price) on the given side, as-of t_ms."""
    arr = depth.get(asset)
    if arr is None:
        return None, None
    ts, bsz, asz, bb, ba = arr
    i = np.searchsorted(ts, t_ms, "right") - 1
    if i < 0:
        return None, None
    v = (bsz[i] if which == "bid" else asz[i]); p = (bb[i] if which == "bid" else ba[i])
    return (float(v) if np.isfinite(v) else None), (float(p) if np.isfinite(p) else None)


def sim(allt, depth, alpha, Q, cap=50, skew=0.25, d_max=float("inf"), tau_lo=0.0, tau_hi=float("inf"),
        persist=False, reprice_tol=0.0, spread_boost=1.0, cont_skew=False):
    """Queue-model maker. d_max/tau = thin-book/early 'fixes'. persist=True models PERSISTENT
    resting with FIFO advancement: our queue-ahead = running-MIN displayed depth since we joined
    the level (we advance as orders ahead fill/cancel, and don't fall back when new orders queue
    behind us) -- the realistic case between static-back (alpha=1) and full-depletion."""
    out = {}; fv = tv = 0.0
    for win, g in allt.groupby("win"):
        delta = cash = reb = up_inv = dn_inv = 0.0
        r = float(g.res.iloc[0]); we = float(g.wend.iloc[0]); skcap = skew * cap
        runmin = {}; lastpx = {}             # (asset,which) -> running-min depth; last touch price
        arr = g[["asset_id", "tok", "side", "price", "size", "t_ms"]].to_numpy()
        for asset, tok, side, price, size, t_ms in arr:
            tv += size
            tau = we - int(t_ms) / 1000.0
            if not (tau_lo <= tau <= tau_hi):
                continue
            # taker BUY hits the ASK (we rest selling); taker SELL hits the BID (we rest buying)
            which = "ask" if side == "BUY" else "bid"
            D, tpx = depth_at(depth, asset, int(t_ms), which)
            if D is None:
                D = 0.0
            if D > d_max:                       # too much competition ahead -> don't quote here
                continue
            # spread-responsive sizing (causal): quote bigger when spread > 1 tick (lit: 2-tick
            # spread pays far more than rebate-only 1-tick). spread from measured touch prices.
            Qeff = Q
            if spread_boost != 1.0:
                _, bb_p = depth_at(depth, asset, int(t_ms), "bid")
                _, ba_p = depth_at(depth, asset, int(t_ms), "ask")
                if bb_p is not None and ba_p is not None and (ba_p - bb_p) > 0.015:
                    Qeff = Q * spread_boost
            if persist:                         # FIFO advancement, but a touch-price MOVE resets us
                k = (asset, which)              # to the back (we must cancel+reprice -> lose priority)
                moved = (tpx is not None and lastpx.get(k) is not None
                         and abs(tpx - lastpx[k]) > reprice_tol + 1e-9)
                if moved:
                    runmin[k] = D               # repriced: back of the new queue (sticky if tol>0)
                else:
                    runmin[k] = min(runmin.get(k, D), D)
                lastpx[k] = tpx if tpx is not None else lastpx.get(k)
                ahead = alpha * runmin[k]
            else:
                ahead = alpha * D
            passthrough = max(size - ahead, 0.0)
            fill = min(passthrough, Qeff)
            if fill <= 0:
                continue
            is_up = (tok == "U"); sells = (side == "BUY")
            dsign = (-1.0 if sells else 1.0) if is_up else (1.0 if sells else -1.0)
            if cont_skew:                       # Avellaneda-Stoikov: taper leaning-side size
                if delta * dsign > 0 and skcap > 0:   # continuously vs the hard binary cap
                    fill *= max(0.0, 1.0 - abs(delta) / skcap)
                if fill <= 0:
                    continue
            elif abs(delta) >= skcap and delta * dsign > 0:   # binary skew (baseline)
                continue
            d_delta = dsign * fill
            if abs(delta + d_delta) > cap:
                room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else fill
                fill = min(fill, room)
            if fill <= 0:
                continue
            fv += fill
            sign = 1.0 if sells else -1.0
            cash += sign * price * fill
            if is_up:
                up_inv += (-fill if sells else fill)
            else:
                dn_inv += (-fill if sells else fill)
            delta += (1 if (d_delta > 0) else -1) * fill
            reb += fees.maker_rebate(price, rate=REBATE) * fill
        out[win] = (cash + up_inv * r + dn_inv * (1 - r), reb)
    return out, fv, tv


def report(tag, res, fv, tv, nwin):
    G = np.array([v[0] for v in res.values()]); R = np.array([v[1] for v in res.values()])
    N = G + R
    print(f"  {tag:28} fill_rate={fv/tv:6.1%} | net/win={N.mean():+8.3f} gross={G.mean():+8.3f} "
          f"rebate={R.mean():+7.3f} | net t={N.mean()/(N.std(ddof=1)/np.sqrt(len(N))):+5.1f}")


def main():
    depth = load_depth()
    if not depth:
        print("no depth_parts yet -- wait for fetch_depth.py"); return
    allt = load_trades_with_assets()
    # restrict to windows we have depth for
    have = set(allt.asset_id) & set(depth)
    allt = allt[allt.asset_id.isin(depth)]
    nwin = allt.win.nunique()
    print(f"depth assets={len(depth)} | trades={len(allt)} windows={nwin} "
          f"(median touch sizes: bid={np.nanmedian([np.nanmedian(d[1]) for d in depth.values()]):.0f})\n")
    print("QUEUE-MODEL fill backtest (measured depth; alpha=queue position, Q=our quote size):")
    configs = [
        ("alpha=0 Q=inf (==offline replay)", 0.0, INF),
        ("alpha=0.5 Q=20", 0.5, 20),
        ("alpha=1.0 Q=20 (realistic)", 1.0, 20),
        ("alpha=1.0 Q=inf (back, any size)", 1.0, INF),
        ("alpha=1.0 Q=5 (small clip)", 1.0, 5),
    ]
    for tag, a, q in configs:
        res, fv, tv = sim(allt, depth, a, q)
        report(tag, res, fv, tv, nwin)
    print("\nReads: alpha=0/Q=inf reproduces the optimistic replay; alpha=1 (behind measured depth)")
    print("is the realistic fill rate -- compare to live ~8% and the phi-sensitivity conservative case.")


if __name__ == "__main__":
    main()
