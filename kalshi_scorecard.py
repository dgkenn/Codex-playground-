"""kalshi_scorecard.py -- the live-performance dashboard for the box-harvester.

Computes the headline metrics that matter for a hold-to-settlement passive maker, from the
local telemetry the trader writes continuously:

    kalshi_fees_<asset>15m.jsonl    every fill + decision context (mid/spread/depth/inventory)
    kalshi_markout.jsonl            markout curve per fill at 5s/30s/60s/300s
    live_metrics_<asset>15m.jsonl   window summaries, balance polls, place/cancel/reject events

plus settlement results fetched once per ticker from the public API (cached in
.scorecard_results.json) so settlement PnL, calibration, and box decomposition are exact.

The mental model (operator's framework): quote quality says whether we make markets well,
markouts say whether we get picked off, settlement PnL says whether hold-to-expiry works.
For THIS strategy the deepest split is paired (risk-free locked) vs unpaired (directional) PnL.

    python kalshi_scorecard.py [asset]
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
RES_CACHE = ".scorecard_results.json"


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        for ln in open(path):
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def results_for(tickers):
    cache = json.load(open(RES_CACHE)) if os.path.exists(RES_CACHE) else {}
    for tk in tickers:
        if tk in cache:
            continue
        try:
            m = requests.get(f"{B}/markets/{tk}", timeout=8).json().get("market", {})
            r = m.get("result")
            if r in ("yes", "no"):
                cache[tk] = 1 if r == "yes" else 0
        except Exception:
            pass
    json.dump(cache, open(RES_CACHE, "w"))
    return cache


def dd_stats(pnls):
    """(max drawdown, windows under water) on a per-window pnl sequence."""
    peak = cum = mdd = 0.0
    uw = 0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
        uw += cum < peak - 1e-9
    return mdd, uw


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else "btc"
    fills = load_jsonl(f"kalshi_fees_{asset}15m.jsonl")
    mos = load_jsonl("kalshi_markout.jsonl")
    lms = (load_jsonl(f"live_metrics_kalshi_{asset}15m.jsonl")
           or load_jsonl(f"live_metrics_{asset}15m.jsonl"))
    if not fills:
        print("no fills logged yet"); return
    res = results_for({f["ticker"] for f in fills})

    print("=" * 72)
    print(f"  KALSHI SCORECARD ({asset}) -- {len(fills)} fills, "
          f"{len({f['ticker'] for f in fills})} windows, {len(res)} resolved")
    print("=" * 72)

    # ---- 1/3/8: settlement PnL, per contract, box decomposition, tail ----
    by_w = defaultdict(lambda: {"yes": [], "no": []})
    fees_paid = 0.0
    for f in fills:
        by_w[f["ticker"]][f["side"]].append((f["price"], f["count"]))
        try:
            fees_paid += float(f.get("fee_reported") or 0)
        except Exception:
            pass
    win_pnl, locked_tot, resid_tot, peak_unpaired = {}, 0.0, 0.0, 0
    for tk, d in by_w.items():
        if tk not in res:
            continue
        r = res[tk]
        pnl = sum((r - p) * c for p, c in d["yes"]) + sum(((1 - r) - p) * c for p, c in d["no"])
        win_pnl[tk] = pnl
        ny, nn = sum(c for _, c in d["yes"]), sum(c for _, c in d["no"])
        bx = min(ny, nn)
        peak_unpaired = max(peak_unpaired, int(abs(ny - nn)))
        if bx > 0:
            cy = sorted(d["yes"]); cn = sorted(d["no"])
            def cheap(side, q):
                tot = 0.0; left = q
                for p, c in side:
                    take = min(c, left); tot += p * take; left -= take
                    if left <= 1e-9:
                        break
                return tot
            locked = bx - cheap(cy, bx) - cheap(cn, bx)
            locked_tot += locked
            resid_tot += pnl - locked
        else:
            resid_tot += pnl
    pnls = [win_pnl[k] for k in sorted(win_pnl)]
    ncon = sum(f["count"] for f in fills)
    # pairing efficiency (the dual-leg fill metric that matters for a single-book maker box:
    # NOT "opportunities detected" -- every spread>0 book is an "opportunity"; the game is
    # what fraction of our filled contracts end up settlement-locked pairs)
    tot_con = tot_boxed2 = 0.0
    win_boxed = 0
    for tk, d in by_w.items():
        ny, nn = sum(c for _, c in d["yes"]), sum(c for _, c in d["no"])
        tot_con += ny + nn
        tot_boxed2 += 2 * min(ny, nn)
        win_boxed += min(ny, nn) > 0
    print(f"\n[PnL]   net realized (resolved windows): ${sum(pnls):+.2f}   fees: ${fees_paid:.2f}")
    print(f"        per contract: {sum(pnls)/max(ncon,1)*100:+.2f}c   per window: "
          f"{sum(pnls)/max(len(pnls),1)*100:+.2f}c")
    print(f"[BOX]   locked (risk-free): ${locked_tot:+.2f}   directional residual: ${resid_tot:+.2f}"
          f"   locked share: {locked_tot/sum(pnls)*100:.0f}%" if pnls and sum(pnls) else "")
    ycon = sum(f["count"] for f in fills if f["side"] == "yes")
    ncon_no = ncon - ycon
    print(f"[PAIR]  pairing efficiency: {tot_boxed2/max(tot_con,1)*100:.0f}% of contracts locked"
          f"   windows completing >=1 box: {win_boxed}/{len(by_w)}"
          f"   leg imbalance yes:no = {ycon:.0f}:{ncon_no:.0f}")
    # maker slippage: lock you could see at fill time (the spread) vs lock realized at pairing
    sp_at_fill = [f["ctx"]["spread"] for f in fills
                  if f.get("ctx", {}).get("spread") is not None]
    if sp_at_fill and tot_boxed2:
        print(f"        spread at fill (expected lock): {sum(sp_at_fill)/len(sp_at_fill)*100:+.2f}c"
              f"   realized lock/pair: {locked_tot/(tot_boxed2/2)*100:+.2f}c"
              f"   (gap = completion slippage; n_ctx={len(sp_at_fill)})")
    mdd, uw = dd_stats(pnls)
    print(f"[RISK]  max drawdown: ${mdd:.2f}   windows under water: {uw}/{len(pnls)}"
          f"   worst window: ${min(pnls):+.2f}   peak unpaired inventory: {peak_unpaired}" if pnls else "")

    # ---- 2: markout curve (am I getting picked off?) ----
    if mos:
        print("\n[MARKOUT curve, c/fill -- negative = picked off]")
        for h in (5.0, 30.0, 60.0, 300.0):
            xs = [m["markout"] for m in mos if m.get("h", 5.0) == h]
            if xs:
                print(f"        {int(h):>3}s: {sum(xs)/len(xs)*100:+.2f}  (n={len(xs)})")

    # ---- 6: execution quality (effective spread, fill timing) ----
    ctxs = [f for f in fills if f.get("ctx", {}).get("mid") is not None]
    if ctxs:
        eff = []
        for f in ctxs:
            mid = f["ctx"]["mid"]
            mid_side = mid if f["side"] == "yes" else 1.0 - mid
            eff.append(mid_side - f["price"])   # bought below side-mid = captured half-spread
        print(f"\n[EXEC]  effective half-spread captured: {sum(eff)/len(eff)*100:+.2f}c/fill (n={len(eff)})")
        rs = [f["ctx"].get("resting_s") for f in ctxs if f["ctx"].get("resting_s") is not None]
        if rs:
            rs.sort()
            print(f"        time-to-fill: median {rs[len(rs)//2]:.0f}s  p90 {rs[int(len(rs)*0.9)]:.0f}s")
    places = sum(1 for e in lms if e.get("kind") == "place_ack")
    rejects = sum(1 for e in lms if e.get("kind") == "place_reject")
    cancels = sum(e.get("n", 1) for e in lms if e.get("kind") == "cancel_batch")
    if places:
        print(f"        places={places} rejects={rejects} cancels={cancels} "
              f"quote-to-trade={places/max(len(fills),1):.1f}")

    # ---- 7: calibration (do p-cent entries win p% of the time?) ----
    cal = defaultdict(lambda: [0, 0])
    for f in fills:
        if f["ticker"] in res:
            won = res[f["ticker"]] if f["side"] == "yes" else 1 - res[f["ticker"]]
            b = min(int(f["price"] * 5), 4)   # 20c buckets
            cal[b][0] += won * f["count"]; cal[b][1] += f["count"]
    if cal:
        print("\n[CALIB] entry price -> realized win rate (a maker wants win >= price):")
        for b in sorted(cal):
            w, n = cal[b]
            print(f"        {b*20:>3}-{b*20+20}c: {w/n*100:>5.1f}% over n={n:.0f}")

    # ---- 9: capital ----
    bals = [e for e in lms if e.get("kind") == "balance"]
    if bals:
        b0, b1 = bals[0].get("balance"), bals[-1].get("balance")
        if b0 is not None and b1 is not None:
            print(f"\n[CAP]   balance first->last poll: {b0} -> {b1}")

    print("\nread with: locked share high + markouts ~0 + calibration above-diagonal = the box")
    print("engine is working; unpaired residual growing = pairing discipline is leaking.")


if __name__ == "__main__":
    main()
