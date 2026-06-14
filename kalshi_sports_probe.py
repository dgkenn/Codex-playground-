#!/usr/bin/env python3
"""Inventory Kalshi sports markets + characterize live order books.
Public API, no auth. Correct field: /orderbook returns 'orderbook_fp' with
'yes_dollars'/'no_dollars' = [price_str, size_str] resting-bid ladders.
YES ask = 1 - best NO bid. Judges spread/depth and whether structure is HFT-MM (crypto)
or slower/softer (sports)."""
import requests, time, json, datetime
from collections import Counter

BASE = "https://api.elections.kalshi.com/trade-api/v2"
S = requests.Session(); S.headers.update({"Accept": "application/json"})

def get(path, **p):
    for a in range(4):
        try:
            r = S.get(BASE+path, params=p, timeout=20)
            if r.status_code == 200: return r.json()
            if r.status_code == 429: time.sleep(2**a); continue
            return {"_err": r.status_code}
        except Exception: time.sleep(2**a)
    return {"_err": "fail"}

def fl(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def open_markets(st, limit=200):
    out, cur = [], None
    while True:
        p = {"series_ticker": st, "status": "open", "limit": limit}
        if cur: p["cursor"] = cur
        d = get("/markets", **p); out += d.get("markets", [])
        cur = d.get("cursor")
        if not cur or len(out) >= 800: break
    return out

def book(tk):
    d = get(f"/markets/{tk}/orderbook", depth=30)
    ob = d.get("orderbook_fp") or d.get("orderbook") or {}
    yes = [(fl(p), fl(s)) for p, s in (ob.get("yes_dollars") or ob.get("yes") or [])]
    no  = [(fl(p), fl(s)) for p, s in (ob.get("no_dollars") or ob.get("no") or [])]
    yb = max((p for p, s in yes), default=None)
    nb = max((p for p, s in no), default=None)
    ya = round(1 - nb, 2) if nb is not None else None
    spr = round((ya - yb) * 100, 1) if (yb and ya) else None
    # depth in CONTRACTS within 5c of touch
    dbid = sum(s for p, s in yes if yb and p >= yb - 0.05)
    dask = sum(s for p, s in no if nb and p >= nb - 0.05)
    bestbid_sz = sum(s for p, s in yes if p == yb)
    bestask_sz = sum(s for p, s in no if p == nb)
    return dict(yb=yb, ya=ya, spr=spr, nlv=len(yes)+len(no),
                bestbid_sz=bestbid_sz, bestask_sz=bestask_sz,
                dbid5=dbid, dask5=dask)

if __name__ == "__main__":
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    targets = ["KXMLBGAME","KXNBA","KXNHLGAME","KXWNBAGAME","KXWTAMATCH","KXATPMATCH",
               "KXNFLGAME","KXMLB"]
    summary, books = [], []
    for t in targets:
        ms = open_markets(t)
        fut = [m for m in ms if (m.get("close_time") or "") > now]
        # quoted spread from market objects
        spreads = []
        for m in fut:
            yb, ya = fl(m.get("yes_bid_dollars")), fl(m.get("yes_ask_dollars"))
            if yb and ya and ya > 0 and yb > 0: spreads.append((ya - yb) * 100)
        med = round(sorted(spreads)[len(spreads)//2], 1) if spreads else None
        vols = sorted([fl(m.get("volume_fp")) or 0 for m in fut], reverse=True)
        print(f"{t:12s} open={len(ms):3d} future={len(fut):3d} mktQuotedMedSpread={med}c "
              f"topVols={[int(v) for v in vols[:3]]}")
        summary.append(dict(series=t, n_open=len(ms), n_future=len(fut),
                            med_spread_c=med, top_vols=[int(v) for v in vols[:5]]))
        # live books on top-traded FUTURE games
        fut.sort(key=lambda m: fl(m.get("volume_fp")) or 0, reverse=True)
        for m in fut[:4]:
            b = book(m["ticker"])
            rec = dict(series=t, ticker=m["ticker"], title=m.get("title"),
                       vol=int(fl(m.get("volume_fp")) or 0),
                       oi=int(fl(m.get("open_interest_fp")) or 0), **b)
            books.append(rec)
            time.sleep(0.08)

    print("\n=== Live order books (top future games) ===")
    print(f"{'ticker':36s} {'vol':>9} {'spr':>5} {'lv':>3} {'bbSz':>7} {'baSz':>7} {'d5bid':>8} {'d5ask':>8}")
    for r in books:
        print(f"{r['ticker'][:36]:36s} {r['vol']:>9} {str(r['spr']):>5} {r['nlv']:>3} "
              f"{int(r['bestbid_sz']):>7} {int(r['bestask_sz']):>7} {int(r['dbid5']):>8} {int(r['dask5']):>8}")
    # aggregate spread stats on liquid games (vol>50k)
    liq = [r for r in books if r["vol"] > 50000 and r["spr"] is not None]
    if liq:
        sp = sorted(r["spr"] for r in liq)
        print(f"\nLiquid games (vol>50k, n={len(liq)}): touch spread "
              f"min={sp[0]} med={sp[len(sp)//2]} max={sp[-1]}c; "
              f"med top-of-book depth bid={sorted(r['bestbid_sz'] for r in liq)[len(liq)//2]:.0f} "
              f"ask={sorted(r['bestask_sz'] for r in liq)[len(liq)//2]:.0f} contracts")
    json.dump(dict(summary=summary, books=books), open("/tmp/sports/_kalshi_inv.json","w"), indent=2)
    print("\nSaved _kalshi_inv.json")
