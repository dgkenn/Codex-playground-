#!/usr/bin/env python3
"""kalshi_favlong_scan.py -- empirical favorite-longshot calibration on Kalshi's
SOFT (non-crypto) settled markets, net of the taker fee.

Crypto 15m already tested dead (ETH_FAVLONG, XRP_15M, PROJECT_VERDICT): bias absent
or < spread. The academic evidence (GWU 300k contracts, Becker, weather calibration)
is from the SOFT categories -- entertainment / world / politics / weather -- never
tested empirically here. This screens whether a TAKER value edge (queue/latency-free,
the thing that survives every wall that killed the box) exists there.

Method: for each settled binary market with a real pre-settlement price `p` and a
yes/no result, bin by `p`; realized WR vs `p` is the calibration. Net-of-fee taker EV
of buying the cheaper actionable side at touch, with Kalshi quadratic fee 0.07*p*(1-p).
Public API, no auth. SCREEN: settle-snapshot price is an upper-ish bound on tradability
(real entry would be earlier/worse); treat a POSITIVE result as necessary-not-sufficient.

    python kalshi_favlong_scan.py
"""
import urllib.request, json, time, sys
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATS = ["Entertainment", "Politics", "World", "Climate and Weather",
        "Science and Technology", "Companies", "Sports", "Economics"]
FEE = lambda p: 0.07 * p * (1 - p)            # per-contract Kalshi taker fee (quadratic, mult=1)
BANDS = [(i/20, (i+1)/20) for i in range(20)]  # 0.05-wide price buckets


def get(path, params=""):
    u = f"{BASE}{path}" + ("?" + params if params else "")
    for attempt in range(4):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "research"})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def series_for(cat, cap=60):
    out = []
    cur = ""
    while len(out) < cap:
        p = f"category={urllib.parse.quote(cat)}&limit=100" + (f"&cursor={cur}" if cur else "")
        d = get("/series", p)
        out += [s["ticker"] for s in d.get("series", []) if s.get("ticker")]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out[:cap]


def settled_markets(series_ticker, cap=120):
    out, cur = [], ""
    while len(out) < cap:
        p = f"series_ticker={series_ticker}&status=settled&limit=100" + (f"&cursor={cur}" if cur else "")
        d = get("/markets", p)
        ms = d.get("markets", [])
        out += ms
        cur = d.get("cursor") or ""
        if not cur or not ms:
            break
    return out[:cap]


MAXSPREAD = 0.15   # require a genuinely liquid two-sided quote


def quote(m):
    """Return (yes_bid, yes_ask) from the pre-settlement snapshot, or None.
    Require a real two-sided book with a sane spread -- this removes the
    default/stale 0.5 and 0/1 quotes that contaminate settled-market snapshots."""
    yb = fnum(m.get("previous_yes_bid_dollars")); ya = fnum(m.get("previous_yes_ask_dollars"))
    if yb is None or ya is None:
        yb = fnum(m.get("yes_bid_dollars")); ya = fnum(m.get("yes_ask_dollars"))
    if yb is None or ya is None:
        return None
    if not (0 < yb < ya < 1):           # strict two-sided, ask>bid, inside (0,1)
        return None
    if (ya - yb) > MAXSPREAD:           # illiquid -> untradable, drop
        return None
    return (yb, ya)


def main():
    import urllib.parse  # noqa
    rows = []  # (cat, bid, ask, mid, win)
    seen = set()
    for cat in CATS:
        try:
            sers = series_for(cat)
        except Exception as e:
            print(f"[{cat}] series fetch failed: {e}"); continue
        n0 = len(rows)
        for st in sers:
            if len(rows) - n0 > 4000:
                break
            try:
                ms = settled_markets(st, cap=120)
            except Exception:
                continue
            for m in ms:
                tk = m.get("ticker")
                if tk in seen:
                    continue
                seen.add(tk)
                res = (m.get("result") or "").lower()
                if res not in ("yes", "no"):
                    continue
                if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type") != "binary"):
                    continue                               # drop multi-leg / non-binary collections
                if (fnum(m.get("volume_fp")) or 0) < 200:  # require real volume
                    continue
                q = quote(m)
                if q is None:
                    continue
                bid, ask = q
                rows.append((cat, bid, ask, (bid+ask)/2, 1 if res == "yes" else 0))
        print(f"[{cat}] series={len(sers)} usable_settled_markets={len(rows)-n0}")
    print(f"\nTOTAL usable settled binary markets: {len(rows)}\n")
    if len(rows) < 50:
        print("too few; aborting."); return

    sp = sorted(a-b for _, b, a, _, _ in rows)
    print(f"spread (ask-bid): median={sp[len(sp)//2]*100:.1f}c  p90={sp[int(len(sp)*0.9)]*100:.1f}c\n")

    # ---- calibration by MID-price band; taker EV at the ASK of the actioned side ----
    print("CALIBRATION (pooled soft cats, liquid binary only): realized YES-rate vs mid")
    print(f"{'band':>12} {'n':>5} {'mid':>6} {'realWR':>7} {'bias_pp':>8} "
          f"{'EV_takeYES':>11} {'EV_takeNO':>10} {'best_net':>9}")
    for lo, hi in BANDS:
        b = [(bid, ask, w) for c, bid, ask, mid, w in rows if lo <= mid < hi]
        if len(b) < 25:
            continue
        n = len(b); mmid = sum((bd+ak)/2 for bd, ak, _ in b)/n; wr = sum(w for _, _, w in b)/n
        # buy YES at ask: pay ask, win 1 if YES. fee on the fill price.
        ev_yes = sum(w - ak - FEE(ak) for bd, ak, w in b)/n
        # buy NO at no_ask=(1-bid): pay (1-bid), win 1 if NO. fee on (1-bid).
        ev_no = sum((1-w) - (1-bd) - FEE(1-bd) for bd, ak, w in b)/n
        best = max(ev_yes, ev_no)
        flag = "  <== +EV" if best > 0 else ""
        print(f"{lo:.2f}-{hi:.2f} {n:>5} {mmid:>6.3f} {wr:>7.3f} {(wr-mmid)*100:>+8.1f} "
              f"{ev_yes*100:>+10.2f}c {ev_no*100:>+9.2f}c {best*100:>+8.2f}c{flag}")

    # ---- per-category headline bias ----
    print("\nPER-CATEGORY mean bias (realWR - mid), liquid binary only:")
    bycat = defaultdict(list)
    for c, bid, ask, mid, w in rows:
        bycat[c].append((mid, w))
    for c in CATS:
        b = bycat.get(c, [])
        if len(b) < 30:
            print(f"  {c:>26}: n={len(b)} (too few)"); continue
        mp = sum(p for p, _ in b)/len(b); wr = sum(w for _, w in b)/len(b)
        print(f"  {c:>26}: n={len(b):>5} mid={mp:.3f} realWR={wr:.3f} bias={ (wr-mp)*100:+.1f}pp")
    print("\nRead: bias>0 in a band => favorites underpriced there (buy YES); bias<0 => longshots "
          "overpriced (buy NO). EV columns are NET of the quadratic taker fee at the snapshot price. "
          "Positive best_net is necessary-not-sufficient (snapshot price flatters a real earlier entry).")


if __name__ == "__main__":
    import urllib.parse
    main()
