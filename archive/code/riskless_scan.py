#!/usr/bin/env python3
"""riskless_scan.py -- scan LIVE markets for genuinely-riskless arbitrage (node RISKLESS). READ-ONLY.

Structures (all require EXECUTABLE, non-stale quotes):
  (1) K1 YES+NO underpricing: one binary mkt, yes_ask + no_ask + fees < 1 -> buy both, one pays $1.
  (2) K4 ladder MONOTONICITY: yes(above X) is NON-INCREASING in X. Real arb = a HIGHER strike x2 priced
      MORE likely than lower x1: bid(x2) > ask(x1) net fees. Buy yes(x1)@ask, sell yes(x2)@bid -> paid
      upfront AND settlement out(x1)-out(x2) >= 0 always. (This is the correct direction; the inverse is
      the NORMAL monotone ladder, NOT an arb.)
  (3) P2/P3 Polymarket exclusive-bucket set: only for TRUE exhaustive buckets (sum of mids ~1, so cumulative
      'above X' ladders are excluded). sum(asks)<1 -> buy all; sum(bids)>1 -> sell all. Zero fee.
Executability filters: Kalshi require volume_fp>0 and 0<bid<=ask<1 (drop stale 0/1 default quotes).
"""
import urllib.request, urllib.parse, json, math
from collections import defaultdict

KFEE = lambda p: math.ceil(0.07 * p * (1 - p) * 100) / 100
KB = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"


def get(url):
    try:
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
    except Exception:
        return None


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def scan_kalshi(series_list):
    hits, checked = [], 0
    for s in series_list:
        d = get(f"{KB}/markets?series_ticker={s}&status=open&limit=1000")
        if not d:
            continue
        byev = defaultdict(list)
        for m in d.get("markets", []):
            byev[m.get("event_ticker")].append(m)
        for et, mkts in byev.items():
            # executable markets only
            live = []
            for m in mkts:
                b, a, v = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars")), f(m.get("volume_fp"))
                st = f(m.get("floor_strike"))
                if b is None or a is None or (v or 0) <= 0:
                    continue
                if not (0 < b < 1 and 0 < a < 1 and b <= a + 0.001):   # non-crossed, non-stale
                    continue
                na = f(m.get("no_ask_dollars"))
                # (1) yes+no
                if na and 0 < na < 1 and a + na + KFEE(a) + KFEE(na) < 1.0:
                    hits.append(("K1 yes+no", et, m.get("ticker"), round(1 - a - na - KFEE(a) - KFEE(na), 4)))
                if st is not None:
                    live.append((st, b, a))
            checked += len(live)
            # (2) ladder monotonicity — CORRECT direction
            live.sort(key=lambda x: x[0])
            for i in range(len(live) - 1):
                (x1, b1, a1), (x2, b2, a2) = live[i], live[i + 1]
                if b2 - KFEE(b2) - KFEE(a1) > a1:      # higher strike BID > lower strike ASK
                    hits.append(("K4 ladder-mono", et, f"{x1:.0f}<{x2:.0f} buy@{a1} sell@{b2}",
                                 round(b2 - a1 - KFEE(b2) - KFEE(a1), 4)))
    return hits, checked


def scan_polymarket(queries):
    hits, checked, seen = [], 0, set()
    for q in queries:
        d = get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&events_status=active&limit=25")
        if not d:
            continue
        for ev in d.get("events", []):
            if ev.get("id") in seen:
                continue
            seen.add(ev.get("id"))
            mkts = ev.get("markets", [])
            if len(mkts) < 2:
                continue
            asks, bids, ok = [], [], True
            for m in mkts:
                ba, bb = f(m.get("bestAsk")), f(m.get("bestBid"))
                if ba is None or bb is None or not (0 < ba < 1) or not (0 <= bb < 1):
                    ok = False
                    break
                asks.append(ba)
                bids.append(bb)
            if not ok:
                continue
            mids = [(a + b) / 2 for a, b in zip(asks, bids)]
            if not (0.85 <= sum(mids) <= 1.20):        # exclusive-exhaustive bucket set only
                continue
            checked += 1
            if sum(asks) < 0.999:
                hits.append(("P2 buy-all", ev.get("title", "")[:38], f"sum_ask={sum(asks):.3f}", round(1 - sum(asks), 4)))
            if sum(bids) > 1.001:
                hits.append(("P3 sell-all", ev.get("title", "")[:38], f"sum_bid={sum(bids):.3f}", round(sum(bids) - 1, 4)))
    return hits, checked


if __name__ == "__main__":
    kh, kc = scan_kalshi(["KXBTC", "KXETH", "KXBTCD", "KXETHD", "KXBTCMAXMON", "KXBTCMAXY"])
    print(f"=== KALSHI ({kc} executable ladder rungs checked) ===")
    for h in kh:
        print("  ARB", h)
    if not kh:
        print("  (no executable riskless violation)")
    ph, pc = scan_polymarket(["CPI", "inflation", "PPI", "jobs", "Fed decision", "GDP", "unemployment",
                              "earnings", "IPO", "market cap", "recession", "rate cut"])
    print(f"\n=== POLYMARKET ({pc} exclusive-bucket events checked) ===")
    for h in ph:
        print("  ARB", h)
    if not ph:
        print("  (no exclusive-bucket riskless violation)")
    print("\nBase rate from ONE snapshot. Real value = a CONTINUOUS scanner firing the instant a violation appears,"
          " which must then be hit on ALL legs before it's arbed away.")
