"""Deep dive on the live paper data + cross-check vs historical archive.

Two jobs:
  (1) DECOMPOSE the live edge: where does net P&L come from (vig/gross vs rebate)? fill-side
      asymmetry? markout by side/horizon? -> improvement angles.
  (2) INTEGRITY: compare live-collected stats to the historical backtest data, to catch any
      convention/data drift that would mean we've been validating on inaccurate data
      (overround level, resolved-up rate, price/size distributions, rebate formula).

    python deepdive.py
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict

import numpy as np
import pandas as pd

import fees

REBATE = 0.07


def load(path):
    out = []
    try:
        for l in open(path):
            l = l.strip()
            if l:
                out.append(json.loads(l))
    except FileNotFoundError:
        pass
    return out


def main():
    W = load("audit_windows.jsonl")
    F = load("audit_fills.jsonl")
    B = load("audit_book.jsonl")
    T = load("audit_trades.jsonl")
    print(f"LIVE data: {len(W)} windows, {len(F)} fills, {len(B)} book snaps, {len(T)} trades\n")

    # ---------- (1) P&L decomposition ----------
    net = sum(w["net"] for w in W); gross = sum(w["gross"] for w in W); reb = sum(w["rebate"] for w in W)
    gs = [w["gross"] for w in W]; rs = [w["rebate"] for w in W]; ns = [w["net"] for w in W]
    print("=== P&L DECOMPOSITION (where the money is) ===")
    print(f"  net=${net:+.2f} = gross=${gross:+.2f} + rebate=${reb:+.2f}")
    print(f"  per-window: gross {st.mean(gs):+.3f}±{st.pstdev(gs):.2f} | rebate {st.mean(rs):+.3f}±{st.pstdev(rs):.2f}"
          f" | net {st.mean(ns):+.3f}±{st.pstdev(ns):.2f}")
    print(f"  -> rebate is {reb/net*100:.0f}% of net; gross (vig+settlement) is {gross/net*100:.0f}%")
    print(f"  gross-positive windows: {sum(1 for g in gs if g>0)}/{len(gs)}  "
          f"(if gross<=0 mostly, the edge is rebate-dependent)")

    # ---------- fill-side asymmetry ----------
    mb = sum(w.get("mk_buy",0) for w in W); ms = sum(w.get("mk_sell",0) for w in W)
    print("\n=== FILL-SIDE ASYMMETRY ===")
    print(f"  maker SELL fills={ms} ({ms/(mb+ms):.0%})  vs  maker BUY fills={mb} ({mb/(mb+ms):.0%})")
    print("  (heavy SELL = takers overwhelmingly BUY lottery tickets; we're the bookmaker selling vig)")

    # ---------- resolution balance + net by outcome ----------
    up = sum(w.get("resolved_up",0) for w in W)
    print(f"\n=== RESOLUTION BALANCE ===  resolved_up={up}/{len(W)} ({up/len(W):.0%}) "
          f"(historical ~50%; far off => biased sample/bug)")
    nu = [w["net"] for w in W if w.get("resolved_up",0) == 1]; nd = [w["net"] for w in W if w.get("resolved_up",0) == 0]
    if nu and nd:
        print(f"  net | UP windows {st.mean(nu):+.3f} (n={len(nu)})  DOWN windows {st.mean(nd):+.3f} (n={len(nd)})"
              f"  (big gap => directional leak)")

    # ---------- markout by side & horizon (fills vs book mid) ----------
    bypfx = defaultdict(list)
    for b in B:
        if b.get("bb") is not None and b.get("ba") is not None:
            bypfx[b["token"]].append((pd.Timestamp(b["ts"]).timestamp(), (b["bb"] + b["ba"]) / 2))
    for k in bypfx:
        bypfx[k].sort()

    def mid_at(pfx, t):
        arr = bypfx.get(pfx)
        if not arr:
            return None
        import bisect
        i = bisect.bisect_left(arr, (t, -1))
        return arr[i][1] if i < len(arr) else (arr[-1][1] if arr else None)

    print("\n=== MARKOUT (fill vs future mid; the adverse-selection check) ===")
    for h in (5, 30):
        buy_mo, sell_mo = [], []
        for f in F:
            pfx = f.get("token")
            m = mid_at(pfx, pd.Timestamp(f["ts"]).timestamp() + h)
            if m is None:
                continue
            # taker BUY => we SOLD: favorable if mid rises is BAD for us; markout = fill - mid
            if f["taker_side"] == "BUY":
                sell_mo.append(f["fill_price"] - m)
            else:
                buy_mo.append(m - f["fill_price"])
        allmo = buy_mo + sell_mo
        if allmo:
            print(f"  +{h:>2}s: all {np.mean(allmo):+.5f} (n={len(allmo)}) | "
                  f"our-SELL {np.mean(sell_mo) if sell_mo else float('nan'):+.5f} | "
                  f"our-BUY {np.mean(buy_mo) if buy_mo else float('nan'):+.5f}")

    # ---------- (2) INTEGRITY: live overround vs historical ----------
    print("\n=== INTEGRITY: live vs historical ===")
    # live overround: per window, two token prefixes; mean(ba1+ba2)-1 and 1-mean(bb1+bb2)
    perwin = defaultdict(lambda: defaultdict(list))
    for b in B:
        if b.get("ba") is not None and b.get("bb") is not None:
            perwin[b["ws"]][b["token"]].append((b["bb"], b["ba"]))
    ov_ask, ov_bid = [], []
    for ws, toks in perwin.items():
        ks = list(toks)
        if len(ks) != 2:
            continue
        a = [np.mean([x[1] for x in toks[ks[0]]]), np.mean([x[1] for x in toks[ks[1]]])]
        bd = [np.mean([x[0] for x in toks[ks[0]]]), np.mean([x[0] for x in toks[ks[1]]])]
        ov_ask.append(a[0] + a[1] - 1.0); ov_bid.append(1.0 - (bd[0] + bd[1]))
    if ov_ask:
        print(f"  LIVE overround: ask-sum-1 = {np.mean(ov_ask):+.4f}, 1-bid-sum = {np.mean(ov_bid):+.4f} "
              f"(the vig we sell into; historical ~+0.01)")

    # historical overround from up_book + down_book (sample) -- align is heavy, use per-window means
    try:
        ub = pd.read_parquet("up_book.parquet", columns=["timestamp", "asset_id", "best_bid", "best_ask"]).head(200000)
        print(f"  HISTORICAL up_book sample: best_ask range [{ub.best_ask.min():.2f},{ub.best_ask.max():.2f}] "
              f"mean {ub.best_ask.astype(float).mean():.3f}; rows checked={len(ub)}")
    except Exception as e:  # noqa: BLE001
        print(f"  (historical book read skipped: {str(e)[:50]})")

    # rebate formula identity check (live uses fees.maker_rebate(price, rate=0.07))
    print("\n=== REBATE FORMULA identity (live == backtest) ===")
    for p in (0.5, 0.3, 0.1):
        r = fees.maker_rebate(p, rate=REBATE)
        print(f"  maker_rebate(p={p}) = {r:.5f}/share  (peaks at 0.5; = 0.20*0.07*p*(1-p) for crypto)")
    # cross-check vs the rebate booked in live fills
    fr = [f["rebate"] / f["fill_size"] for f in F if f.get("fill_size")]
    if fr:
        print(f"  live booked rebate/share: mean {np.mean(fr):.5f}  (should match formula at the fill prices)")

    # ---------- live fill-price vs historical trade-price distribution ----------
    lf = [f["fill_price"] for f in F]
    try:
        ht = pd.read_parquet("up_trades.parquet", columns=["price"]).price.astype(float)
        print("\n=== price distribution: live fills vs historical trades ===")
        for q in (0.1, 0.5, 0.9):
            print(f"  q{int(q*100):>2}: live={np.quantile(lf,q):.2f}  hist={ht.quantile(q):.2f}")
    except Exception as e:  # noqa: BLE001
        print(f"  (historical trades read skipped: {str(e)[:50]})")


if __name__ == "__main__":
    main()
