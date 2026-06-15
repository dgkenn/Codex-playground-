#!/usr/bin/env python3
"""Probe Kalshi for ACTIVELY IN-PLAY sports games: a game is 'live' when its
expected start time has passed but it hasn't closed/settled yet. For such markets,
measure spread/depth and how fast top-of-book moves over a short polling window
(a proxy for whether a slow/soft maker opportunity exists vs a fast MM).
Public API, no auth."""
import requests, time, json, datetime, statistics

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

def markets(st, status="open", limit=200):
    out, cur = [], None
    while True:
        p = {"series_ticker": st, "status": status, "limit": limit}
        if cur: p["cursor"] = cur
        d = get("/markets", **p); out += d.get("markets", [])
        cur = d.get("cursor")
        if not cur or len(out) >= 800: break
    return out

def book(tk):
    d = get(f"/markets/{tk}/orderbook", depth=10)
    ob = d.get("orderbook_fp") or d.get("orderbook") or {}
    yes = [(fl(p), fl(s)) for p, s in (ob.get("yes_dollars") or ob.get("yes") or [])]
    no  = [(fl(p), fl(s)) for p, s in (ob.get("no_dollars")  or ob.get("no")  or [])]
    bb = max((p for p, s in yes), default=None)            # best yes bid
    ba = (1 - max((p for p, s in no), default=None)) if no else None  # yes ask = 1-best no bid
    spr = round((ba - bb) * 100, 1) if (bb and ba) else None
    return bb, ba, spr

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    nowiso = now.isoformat()
    series = ["KXMLBGAME", "KXNBA", "KXNHLGAME", "KXWNBAGAME", "KXWTAMATCH", "KXATPMATCH"]
    inplay = []
    for st in series:
        for m in markets(st):
            exp = m.get("expected_expiration_time") or ""
            opent = m.get("open_time") or ""
            close = m.get("close_time") or ""
            # 'in-play' heuristic: opened in past, not yet closed, has meaningful volume
            vol = fl(m.get("volume_fp")) or 0
            if opent and opent < nowiso and close > nowiso and vol > 1000:
                inplay.append((st, m))
    print(f"now={nowiso}  candidate open-and-not-closed markets w/ vol>1k: {len(inplay)}")
    # Take-2 snapshots ~20s apart to see top-of-book motion (live game = moving)
    sample = sorted(inplay, key=lambda x: fl(x[1].get("volume_fp")) or 0, reverse=True)[:12]
    snaps = {}
    for label in ("t0", "t1"):
        for st, m in sample:
            tk = m["ticker"]
            snaps.setdefault(tk, {})[label] = book(tk)
            time.sleep(0.05)
        if label == "t0":
            time.sleep(20)
    print(f"\n{'ticker':40s} {'vol':>9} {'spr0':>5} {'bb0':>6} {'bb1':>6} {'movedC':>7}")
    moves = []
    for st, m in sample:
        tk = m["ticker"]; vol = int(fl(m.get("volume_fp")) or 0)
        bb0, ba0, spr0 = snaps[tk]["t0"]; bb1, ba1, spr1 = snaps[tk]["t1"]
        moved = round(abs((bb1 - bb0) * 100), 2) if (bb0 and bb1) else None
        if moved is not None: moves.append(moved)
        print(f"{tk[:40]:40s} {vol:>9} {str(spr0):>5} {str(bb0):>6} {str(bb1):>6} {str(moved):>7}")
    if moves:
        print(f"\nTop-of-book |move| over ~20s: n={len(moves)} med={statistics.median(moves):.2f}c "
              f"max={max(moves):.2f}c  (high move => live/active & repricing fast)")
    json.dump([{"series": s, "ticker": m["ticker"], "title": m.get("title"),
                "vol": fl(m.get("volume_fp")), "open": m.get("open_time"),
                "close": m.get("close_time")} for s, m in sample],
              open("/tmp/_kalshi_inplay.json", "w"), indent=2, default=str)

if __name__ == "__main__":
    main()
