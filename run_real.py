"""Backtest the fair-value-vs-quote gap on real (or demo) 15-minute Up/Down books.

READ-ONLY. This never places an order and needs no trading credentials -- it only
reads a spot price series and a top-of-book series for the "Up" token and asks:
if at instant t I had taken the resting quote (fill-at-quote) whenever my model
disagreed with the market by more than ``--threshold``, and held to the window's
resolution, what would have happened?

Pipeline per evaluation point:
  * window      = floor(t / window_s) * window_s   (UTC, 900-s aligned)
  * S0          = spot at window open
  * S_close     = spot at window end -> outcome_up = S_close > S0
  * S_now, tau  = spot at t, seconds remaining
  * fair        = fairvalue.fair_up(S_now, S0, sigma, tau)
  * if fair - ask > threshold: BUY Up  at ask, settle 1{up}
    if bid - fair > threshold: SELL Up at bid  (= buy Down at 1-bid), settle 1{down}
  * pnl = payoff - entry - fee_per_share(entry, fee_bps)

We evaluate on a fixed grid of times-remaining within each window (``--eval_step``)
rather than on every tick, so trades are spread across the window and the
by-time-remaining / by-book-price tables are meaningful. Trades inside one window
overlap in time, so this is an edge-detection panel, NOT a compounding portfolio
sim. Fill-at-quote (no slippage, no queue) makes every number an OPTIMISTIC upper
bound on realed edge.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from fairvalue import fair_up, realized_vol_per_s, fee_per_share


# --------------------------------------------------------------------------- io
def load_spot(path):
    """Load spot npz -> (ts_ms int64 sorted, price float64)."""
    z = np.load(path)
    keys = set(z.files)
    ts = z["ts"] if "ts" in keys else z[[k for k in z.files if "ts" in k or "time" in k][0]]
    price = z["price"] if "price" in keys else z["close"]
    ts = np.asarray(ts, dtype=np.int64)
    price = np.asarray(price, dtype=float)
    order = np.argsort(ts)
    return ts[order], price[order]


def load_book(path, ts_col, bid_col, ask_col, ts_unit):
    df = pd.read_parquet(path)
    out = pd.DataFrame({
        "ts_ms": _to_ms(df[ts_col], ts_unit),
        "bid": pd.to_numeric(df[bid_col], errors="coerce").astype(float),
        "ask": pd.to_numeric(df[ask_col], errors="coerce").astype(float),
    })
    if "fee_rate_bps" in df.columns:
        out["fee_rate_bps"] = pd.to_numeric(df["fee_rate_bps"], errors="coerce")
    if "asset_id" in df.columns:
        out["asset_id"] = df["asset_id"].astype(str)
    out = out.dropna(subset=["ts_ms", "bid", "ask"]).sort_values("ts_ms").reset_index(drop=True)
    return out


def _to_ms(s, unit):
    if np.issubdtype(np.asarray(s).dtype, np.datetime64) or str(s.dtype).startswith("datetime"):
        return pd.to_datetime(s, utc=True).view("int64") // 1_000_000
    v = pd.to_numeric(s, errors="coerce").astype("float64")
    return (v * {"s": 1000.0, "ms": 1.0, "us": 1e-3, "ns": 1e-6}[unit]).astype("int64")


def spot_at(ts_ms, price, query_ms):
    """Value of `price` at-or-before each query time (step-function hold)."""
    i = np.searchsorted(ts_ms, query_ms, side="right") - 1
    valid = i >= 0
    out = np.full(np.shape(query_ms), np.nan)
    out[valid] = price[i[valid]]
    return out


# --------------------------------------------------------------- backtest core
def backtest(spot_ts, spot_px, book, window_s, threshold, eval_step, fee_bps, sigma):
    # Evaluation grid: for every window touched by the book, evaluate at
    # wstart + eval_step, 2*eval_step, ... < window_s  (i.e. tau from window_s-step..step).
    book_ws = (book["ts_ms"].to_numpy() // 1000 // window_s) * window_s   # window start (s, UTC)
    windows = np.unique(book_ws)

    ks = np.arange(eval_step, window_s, eval_step)
    grid_ws = np.repeat(windows, len(ks))
    grid_t = grid_ws + np.tile(ks, len(windows))         # eval time (s, UTC)

    # latest book quote at-or-before each grid time, *within the same window*
    g = pd.DataFrame({"win": grid_ws, "t_s": grid_t, "ts_ms": grid_t * 1000})
    g = pd.merge_asof(g.sort_values("ts_ms"), book[["ts_ms", "bid", "ask"]],
                      on="ts_ms", direction="backward")
    # drop quotes that belong to an earlier window than the eval point
    g["q_win"] = (g["ts_ms"] // 1000 // window_s) * window_s
    g = g[g["q_win"] == g["win"]].dropna(subset=["bid", "ask"]).reset_index(drop=True)
    if g.empty:
        return _empty_result(window_s, threshold, fee_bps, sigma)

    t_s = g["t_s"].to_numpy()
    win = g["win"].to_numpy()
    tau = (win + window_s) - t_s

    s0 = spot_at(spot_ts, spot_px, win * 1000)
    sclose = spot_at(spot_ts, spot_px, (win + window_s) * 1000)
    snow = spot_at(spot_ts, spot_px, t_s * 1000)

    ok = np.isfinite(s0) & np.isfinite(sclose) & np.isfinite(snow) & (tau > 0)
    g, t_s, win, tau = g[ok].reset_index(drop=True), t_s[ok], win[ok], tau[ok]
    s0, sclose, snow = s0[ok], sclose[ok], snow[ok]
    if len(g) == 0:
        return _empty_result(window_s, threshold, fee_bps, sigma)

    outcome_up = (sclose > s0).astype(float)
    fair = fair_up(snow, s0, sigma, tau)
    bid = g["bid"].to_numpy()
    ask = g["ask"].to_numpy()

    buy = (fair - ask > threshold) & (ask > 0) & (ask < 1)
    sell = (bid - fair > threshold) & (bid > 0) & (bid < 1) & ~buy

    # entry price expressed on the UP scale (for bucketing); pnl is signed money.
    entry_up = np.where(buy, ask, np.where(sell, bid, np.nan))
    pnl = np.full(len(g), np.nan)
    # BUY Up at ask: payoff 1 if up
    pnl[buy] = outcome_up[buy] - ask[buy] - fee_per_share(ask[buy], fee_bps)
    # SELL Up at bid == BUY Down at (1-bid): payoff 1 if down
    down_entry = 1.0 - bid[sell]
    pnl[sell] = (1.0 - outcome_up[sell]) - down_entry - fee_per_share(bid[sell], fee_bps)

    # cost actually paid, fee paid, payoff -- on the side traded (for the identity
    # mean_pnl == win_rate - mean_cost - mean_fee).
    cost = np.where(buy, ask, np.where(sell, 1.0 - bid, np.nan))
    fee_paid = np.where(buy, fee_per_share(ask, fee_bps),
                        np.where(sell, fee_per_share(bid, fee_bps), np.nan))
    payoff = np.where(buy, outcome_up, np.where(sell, 1.0 - outcome_up, np.nan))

    trade = buy | sell
    res = pd.DataFrame({
        "win_start": win[trade], "t_s": t_s[trade], "tau": tau[trade],
        "side": np.where(buy[trade], "BUY_UP", "SELL_UP"),
        "entry_up": entry_up[trade], "outcome_up": outcome_up[trade],
        "cost": cost[trade], "fee": fee_paid[trade], "payoff": payoff[trade],
        "pnl": pnl[trade],
    })

    return {
        "trades": res,
        "n_eval": int(len(g)),
        "n_windows": int(len(windows)),
        "window_s": window_s, "threshold": threshold,
        "fee_bps": fee_bps, "sigma": sigma,
    }


def _empty_result(window_s, threshold, fee_bps, sigma):
    return {"trades": pd.DataFrame(columns=["win_start", "t_s", "tau", "side",
            "entry_up", "outcome_up", "pnl"]), "n_eval": 0, "n_windows": 0,
            "window_s": window_s, "threshold": threshold, "fee_bps": fee_bps, "sigma": sigma}


# ------------------------------------------------------------------ reporting
def _agg(df):
    return pd.Series({"n": len(df), "win_rate": (df["pnl"] > 0).mean() if len(df) else float("nan"),
                      "avg_pnl": df["pnl"].mean() if len(df) else float("nan"),
                      "total_pnl": df["pnl"].sum() if len(df) else 0.0})


def summary_stats(tr):
    """Lead metrics + gate diagnostics for a set of trades."""
    n = len(tr)
    pnl = tr["pnl"].to_numpy()
    mean = float(pnl.mean()); std = float(pnl.std(ddof=1)) if n > 1 else float("nan")
    sharpe = mean / std if std and std > 0 else float("nan")
    tstat = sharpe * np.sqrt(n) if np.isfinite(sharpe) else float("nan")
    win_rate = float((pnl > 0).mean())
    mean_cost = float(tr["cost"].mean()); mean_fee = float(tr["fee"].mean())
    identity = win_rate - mean_cost - mean_fee        # ~= mean (uses win_rate, not mean payoff)
    mean_entry_up = float(tr["entry_up"].mean())
    # concentration: largest single trade as share of |total|; drawdown over time order.
    total = float(pnl.sum())
    top_share = float(np.max(np.abs(pnl)) / abs(total)) if total != 0 else float("nan")
    seq = tr.sort_values("t_s")["pnl"].to_numpy()
    cum = np.cumsum(seq); dd = float(np.max(np.maximum.accumulate(cum) - cum)) if n else 0.0
    dd_share = dd / abs(total) if total != 0 else float("nan")
    return dict(n=n, mean=mean, std=std, sharpe=sharpe, tstat=tstat, win_rate=win_rate,
                mean_cost=mean_cost, mean_fee=mean_fee, identity=identity, total=total,
                mean_entry_up=mean_entry_up, top_share=top_share, dd_share=dd_share)


def report(r):
    tr = r["trades"]
    print(f"\n--- threshold = {r['threshold']:.4f}  (fee_bps={r['fee_bps']}, "
          f"sigma/s={r['sigma']:.2e}, window={r['window_s']}s) ---")
    print(f"  eval points: {r['n_eval']}   windows: {r['n_windows']}   trades: {len(tr)}")
    if len(tr) == 0:
        print("  no trades fired at this threshold.")
        return
    nb = int((tr["side"] == "BUY_UP").sum()); ns = int((tr["side"] == "SELL_UP").sum())
    s = summary_stats(tr)
    print(f"  BUY_UP: {nb}   SELL_UP: {ns}")
    print(f"  LEAD: mean_pnl/share={s['mean']:+.5f}  sharpe/trade={s['sharpe']:+.4f}  "
          f"t-stat={s['tstat']:+.2f}  (n={s['n']})")
    print(f"  win_rate={s['win_rate']:.3f}  mean_entry_up={s['mean_entry_up']:.3f}  "
          f"mean_cost={s['mean_cost']:.3f}  mean_fee={s['mean_fee']:.4f}  total_pnl={s['total']:+.2f}")
    print(f"  identity win_rate-cost-fee = {s['identity']:+.5f}  (should ~= mean_pnl)")
    print(f"  concentration: top trade = {s['top_share']:.1%} of |total|   "
          f"max drawdown = {s['dd_share']:.1%} of |total|")

    # by time remaining
    edges = [0, 60, 180, 300, 450, 600, 900]
    lab = [f"{edges[i]}-{edges[i+1]}s" for i in range(len(edges) - 1)]
    tr = tr.assign(taubin=pd.cut(tr["tau"], bins=edges, labels=lab, right=False))
    print("  by time-remaining:")
    g = tr.groupby("taubin", observed=True).apply(_agg, include_groups=False)
    for k, row in g.iterrows():
        print(f"    tau {str(k):>9}: n={int(row['n']):5d}  win={row['win_rate']:.3f}  "
              f"avg_pnl={row['avg_pnl']:+.4f}  total={row['total_pnl']:+.2f}")

    # by book price (UP-token entry price)
    pedges = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0]
    plab = [f"{pedges[i]:.1f}-{pedges[i+1]:.1f}" for i in range(len(pedges) - 1)]
    tr = tr.assign(pbin=pd.cut(tr["entry_up"], bins=pedges, labels=plab, right=False))
    print("  by book-price (UP entry):")
    g = tr.groupby("pbin", observed=True).apply(_agg, include_groups=False)
    for k, row in g.iterrows():
        print(f"    price {str(k):>9}: n={int(row['n']):5d}  win={row['win_rate']:.3f}  "
              f"avg_pnl={row['avg_pnl']:+.4f}  total={row['total_pnl']:+.2f}")


def verify_labels(r, spot_ts, spot_px, windows_path):
    """Step 6b: compare spot-derived UP labels to the market resolution outcomes."""
    try:
        w = pd.read_parquet(windows_path)
    except Exception as e:
        print(f"\n[verify] resolution file not available ({e}); skipping label cross-check.")
        return
    w = w.dropna(subset=["resolved_up"]).copy()
    if w.empty:
        print("\n[verify] no resolved windows to cross-check.")
        return
    ws = w["window_start"].to_numpy().astype(np.int64)
    we = w["window_end"].to_numpy().astype(np.int64)
    s0 = spot_at(spot_ts, spot_px, ws * 1000)
    sc = spot_at(spot_ts, spot_px, we * 1000)
    ok = np.isfinite(s0) & np.isfinite(sc)
    spot_up = (sc[ok] > s0[ok]).astype(int)
    res_up = w["resolved_up"].to_numpy()[ok].astype(int)
    n = ok.sum()
    disagree = float((spot_up != res_up).mean()) if n else float("nan")
    print(f"\n[verify 6b] spot-label vs market-resolution: {n} windows, "
          f"disagreement = {disagree:.3%}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", required=True)
    ap.add_argument("--spot", required=True)
    ap.add_argument("--ts_col", default="timestamp")
    ap.add_argument("--bid_col", default="best_bid")
    ap.add_argument("--ask_col", default="best_ask")
    ap.add_argument("--ts_unit", default="ms", choices=["s", "ms", "us", "ns"])
    ap.add_argument("--window_s", type=int, default=900)
    ap.add_argument("--threshold", type=float, default=0.0)
    ap.add_argument("--eval_step", type=int, default=60)
    ap.add_argument("--fee_bps", type=float, default=None,
                    help="override; default reads fee_rate_bps from the book, else 1000")
    ap.add_argument("--sigma", type=float, default=None, help="override per-second sigma")
    ap.add_argument("--windows", default=None, help="parquet with resolution for label check")
    args = ap.parse_args()

    spot_ts, spot_px = load_spot(args.spot)
    book = load_book(args.book, args.ts_col, args.bid_col, args.ask_col, args.ts_unit)

    sigma = args.sigma if args.sigma is not None else realized_vol_per_s(spot_px, _median_dt_s(spot_ts))
    if args.fee_bps is not None:
        fee_bps = args.fee_bps
    elif "fee_rate_bps" in book.columns and book["fee_rate_bps"].notna().any():
        fee_bps = float(book["fee_rate_bps"].dropna().median())
    else:
        fee_bps = 1000.0

    print("=== run_real.py ===")
    print(f"  spot points: {len(spot_ts)}   book rows: {len(book)}")
    print(f"  spot range : {pd.to_datetime(spot_ts.min(),unit='ms',utc=True)} .. "
          f"{pd.to_datetime(spot_ts.max(),unit='ms',utc=True)}")
    print(f"  sigma/s    : {sigma:.3e}   fee_bps: {fee_bps}")

    # Step 6a: show reconstructed UTC window boundaries.
    sample_ws = np.unique((book["ts_ms"].to_numpy() // 1000 // args.window_s) * args.window_s)[:3]
    print("  [verify 6a] first reconstructed UTC windows (start -> end):")
    for s in sample_ws:
        print(f"     {pd.to_datetime(s,unit='s',utc=True)} -> "
              f"{pd.to_datetime(s+args.window_s,unit='s',utc=True)}  (start%900={s%900})")

    r = backtest(spot_ts, spot_px, book, args.window_s, args.threshold,
                 args.eval_step, fee_bps, sigma)
    report(r)
    if args.windows:
        verify_labels(r, spot_ts, spot_px, args.windows)


def _median_dt_s(ts_ms):
    d = np.diff(np.sort(ts_ms))
    d = d[d > 0]
    return float(np.median(d) / 1000.0) if d.size else 1.0


if __name__ == "__main__":
    main()
