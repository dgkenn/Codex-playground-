#!/usr/bin/env python3
"""kalshi_overround_scan.py -- NEW structural edge: multi-outcome event OVERROUND (Dutch book).

A "who will win X" event has N mutually-exclusive legs; exactly one resolves YES, so true
sum(YES)=1. Recreational longshot overpricing pushes sum(YES) > 1 (an overround). Harvest =
SELL every leg's YES (equiv. BUY every NO): you collect on the N-1 losing legs and lose the
1 winner; net edge per event ~ (sum(yes_entry) - 1) - fees. This is the favorite-longshot bias
expressed at the EVENT level -- potentially BIGGER (whole-event) and LOWER-variance (diversified
across legs, you ALWAYS win N-1 of N) than single-longshot selling. Soft cats = zero maker fee.

Two reads:
  (A) CURRENT harvestable overround on OPEN exhaustive multi-leg soft events (what you'd trade now).
  (B) SETTLED realized P&L of the buy-all-NO basket (did it actually pay, net of taker cost?).

Rate-limited (sleeps + 429 backoff). Public API, no auth.  python kalshi_overround_scan.py
"""
import urllib.request, json, time, urllib.parse, sys

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATS = ["Politics", "Entertainment", "Science and Technology", "Climate and Weather"]
FEE = lambda p: 0.07 * p * (1 - p)
SLEEP = 0.35


def get(path, params=""):
    u = f"{BASE}{path}" + ("?" + params if params else "")
    for a in range(6):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research"}), timeout=25))
            time.sleep(SLEEP)
            return r
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2.0 * (a + 1)); continue
            if a == 5:
                return {}
            time.sleep(1.0 * (a + 1))
        except Exception:
            if a == 5:
                return {}
            time.sleep(1.0 * (a + 1))
    return {}


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def series_for(cat, cap=50):
    out, cur = [], ""
    while len(out) < cap:
        d = get("/series", f"category={urllib.parse.quote(cat)}&limit=100" + (f"&cursor={cur}" if cur else ""))
        out += [s["ticker"] for s in d.get("series", []) if s.get("ticker")]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out[:cap]


def events(series_ticker, status):
    out, cur = [], ""
    while True:
        d = get("/events", f"series_ticker={series_ticker}&status={status}&with_nested_markets=true&limit=50" + (f"&cursor={cur}" if cur else ""))
        out += d.get("events", [])
        cur = d.get("cursor") or ""
        if not cur or len(out) > 200:
            break
    return out


def main():
    open_over, settled_res = [], []   # (cat, ev, n, sum_bid, sum_ask) ; (cat, ev, n, basket_pnl, cost)
    nA = nB = 0
    for cat in CATS:
        for st in series_for(cat):
            # (A) OPEN exhaustive multi-leg overround
            for e in events(st, "open"):
                mk = e.get("markets", [])
                if len(mk) < 3:
                    continue
                yb = ya = 0.0; ok = True
                for m in mk:
                    b = fnum(m.get("yes_bid_dollars")); a = fnum(m.get("yes_ask_dollars"))
                    if b is None or a is None or not (0 < b <= a < 1):
                        ok = False; break
                    yb += b; ya += a
                if ok:
                    nA += 1
                    open_over.append((cat, e.get("event_ticker"), len(mk), yb, ya))
            # (B) SETTLED basket realized P&L (need mid-life leg prices -> use last settled snapshot proxy)
            for e in events(st, "settled"):
                mk = e.get("markets", [])
                if len(mk) < 3:
                    continue
                # exactly-one-YES exhaustiveness check
                results = [(m.get("result") or "").lower() for m in mk]
                if results.count("yes") != 1 or any(r not in ("yes", "no") for r in results):
                    continue
                # buy 1 NO per leg at the leg's pre-settle NO ask = 1 - previous_yes_bid
                cost = 0.0; payoff = 0.0; valid = True
                for m, r in zip(mk, results):
                    yb = fnum(m.get("previous_yes_bid_dollars"))
                    if yb is None or not (0 < yb < 1):
                        valid = False; break
                    no_cost = 1 - yb                       # taker buy-NO price
                    cost += no_cost + FEE(no_cost)
                    payoff += 1.0 if r == "no" else 0.0
                if valid and cost > 0:
                    nB += 1
                    settled_res.append((cat, e.get("event_ticker"), len(mk), payoff - cost, cost))
        if nA > 250 and nB > 120:
            break

    # ---- (A) current overround ----
    print(f"(A) OPEN exhaustive multi-leg soft events scanned: {nA}")
    if open_over:
        bids = sorted(x[3] for x in open_over)
        asks = sorted(x[4] for x in open_over)
        med_b = bids[len(bids)//2]; med_a = asks[len(asks)//2]
        print(f"    median sum(YES_bid)={med_b:.3f}  median sum(YES_ask)={med_a:.3f}")
        print(f"    sell-all-YES at the BID harvests sum(bid)-1 = {(med_b-1)*100:+.1f}% median "
              f"(needs sum(bid)>1); buy-all-NO at ask harvests 1-sum(ask) when sum(ask)<1")
        big = sorted(open_over, key=lambda x: -(x[3]-1))[:10]
        print("    biggest sell-all-YES overrounds (sum_bid-1):")
        for c, ev, n, b, a in big:
            print(f"      {str(ev)[:38]:38s} legs={n:3d} sumBid={b:.3f} ({(b-1)*100:+.1f}%) sumAsk={a:.3f}")
    # ---- (B) settled realized basket ----
    print(f"\n(B) SETTLED exhaustive multi-leg events (buy-all-NO basket, net of taker fee): {nB}")
    if settled_res:
        pnls = [x[3] for x in settled_res]
        costs = [x[4] for x in settled_res]
        tot = sum(pnls); avg = tot/len(pnls)
        roi = tot/sum(costs)*100
        wins = sum(1 for p in pnls if p > 0)/len(pnls)
        print(f"    n={len(pnls)} baskets | mean basket P&L=${avg:+.3f} | ROI on cost={roi:+.2f}% | win%={wins:.2f}")
        import statistics
        sd = statistics.pstdev(pnls); t = avg/(sd/len(pnls)**0.5) if sd else 0
        print(f"    basket P&L sd=${sd:.3f}  t-stat={t:+.2f}")
        print("    NOTE: buy-all-NO basket harvests the event overround; +ROI net of fee => tradable Dutch-book.")
    else:
        print("    none (no exhaustive settled multi-leg events with usable pre-settle quotes)")


if __name__ == "__main__":
    main()
