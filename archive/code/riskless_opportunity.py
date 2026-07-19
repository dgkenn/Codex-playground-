#!/usr/bin/env python3
"""riskless_opportunity.py -- measure the TRUE, EXECUTABLE size of riskless bucket/within-market arbitrage
across Polymarket + Kalshi, using real order-book depth (NOT stale summary fields).

Structures scanned (all net fees, all executable top-of-book):
  P) Polymarket exclusive-EXHAUSTIVE bucket set (negRisk multi-outcome partition, mids sum ~1):
     - one bucket pays $1. sum(best executable ask) < 1 -> BUY ALL, locked = 1 - sum_ask.
       sum(best executable bid) > 1 -> SELL ALL, locked = sum_bid - 1. Zero fee.
     - executable quotes + DEPTH come from clob.polymarket.com/book?token_id= (top-of-book price+size).
       gamma bestAsk/bestBid used only to PREFILTER candidates; every reported arb is CLOB-confirmed.
     - exhaustiveness gate: negRisk True (Polymarket's own mutually-exclusive-exhaustive mechanism) AND
       gamma mids sum within band. Cumulative 'above X' ladders (mids sum way off) rejected.
  K1) Kalshi within-market YES+NO: yes_ask + no_ask + fees < 1 -> buy both, exactly one pays $1.
      Kalshi live orderbook: yes_dollars/no_dollars = resting BIDS. yes_ask = 1 - best_no_bid,
      no_ask = 1 - best_yes_bid; depth = size resting at that opposing bid. (Summary yes_ask_dollars
      is stale on thin mkts -> we use ONLY the live orderbook.)
  K2) Kalshi within-EVENT bucket (mutually_exclusive series): sum(best exec yes_ask)+fees < 1 -> buy all;
      sum(best exec yes_bid)-fees > 1 -> sell all.
  Kalshi fee per contract per leg = ceil(0.07 * p * (1-p) * 100)/100, p = execution price.

capturable $ per arb = edge(net fees, $/set) * (min executable depth across all legs, in sets/contracts).
Snapshot total = sum of capturable $ over all live arbs. READ-ONLY. No trading, no commits.
"""
import urllib.request, urllib.parse, json, math, time, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

KB = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
KFEE = lambda p: math.ceil(0.07 * p * (1 - p) * 100) / 100  # $/contract/leg
THRESH = 0.005          # min locked edge ($/set) to report a real arb (0.5c)
PM_PAGES = 6            # /events pages (100 each) to enumerate
PM_MID_LO, PM_MID_HI = 0.90, 1.10   # gamma-mid partition sanity band (prefilter)
PM_STRICT_LO, PM_STRICT_HI = 0.95, 1.06  # non-negRisk exhaustiveness gate


def get(url, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(0.6 * (i + 1))
        except Exception:
            time.sleep(0.6 * (i + 1))
    return None


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- Polymarket
def pm_book_top(token_id):
    """Return (best_ask_price, ask_size, best_bid_price, bid_size) from live CLOB book. Sizes in shares."""
    b = get(f"{CLOB}/book?token_id={token_id}")
    if not b:
        return None
    asks = b.get("asks") or []   # ascending price; best (lowest) ask is LAST
    bids = b.get("bids") or []   # ascending price; best (highest) bid is LAST
    ba = (f(asks[-1]["price"]), f(asks[-1]["size"])) if asks else (None, None)
    bb = (f(bids[-1]["price"]), f(bids[-1]["size"])) if bids else (None, None)
    return (ba[0], ba[1], bb[0], bb[1])


def pm_discover():
    """Enumerate active multi-outcome candidate partitions. Return list of events (gamma dicts)."""
    seen, cands = set(), []
    # broad enumeration
    urls = [f"{GAMMA}/events?closed=false&limit=100&offset={o*100}&order=volume24hr&ascending=false"
            for o in range(PM_PAGES)]
    # macro public-search
    for q in ["CPI", "inflation", "PPI", "Fed decision", "rate cut", "GDP", "jobs", "unemployment",
              "recession", "core PCE", "nonfarm", "interest rate"]:
        urls.append(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&events_status=active&limit=25")
    for u in urls:
        d = get(u)
        if not d:
            continue
        evs = d if isinstance(d, list) else d.get("events", [])
        for ev in evs:
            eid = ev.get("id")
            if eid in seen:
                continue
            seen.add(eid)
            mkts = ev.get("markets", [])
            if len(mkts) < 3:
                continue
            # gamma-mid prefilter for a partition
            asks, bids, ok = [], [], True
            for m in mkts:
                ba, bb = f(m.get("bestAsk")), f(m.get("bestBid"))
                if ba is None and bb is None:
                    ok = False
                    break
                asks.append(ba if ba is not None else 1.0)
                bids.append(bb if bb is not None else 0.0)
            if not ok:
                continue
            summid = sum((a + b) / 2 for a, b in zip(asks, bids))
            negrisk = bool(ev.get("negRisk"))
            if not (PM_MID_LO <= summid <= PM_MID_HI):
                continue
            if not negrisk and not (PM_STRICT_LO <= summid <= PM_STRICT_HI):
                continue  # only trust non-negRisk if mids sum very close to 1
            cands.append(ev)
    return cands, len(seen)


def pm_scan():
    cands, n_seen = pm_discover()
    arbs = []
    for ev in cands:
        mkts = ev.get("markets", [])
        toks = []
        for m in mkts:
            try:
                tid = json.loads(m.get("clobTokenIds") or "[]")[0]
            except Exception:
                tid = None
            toks.append(tid)
        if any(t is None for t in toks):
            continue
        with ThreadPoolExecutor(max_workers=12) as ex:
            books = list(ex.map(pm_book_top, toks))
        if any(b is None for b in books):
            continue
        # executable top-of-book
        ask_p = [b[0] for b in books]
        ask_s = [b[1] for b in books]
        bid_p = [b[2] for b in books]
        bid_s = [b[3] for b in books]
        title = (ev.get("title") or "")[:60]
        negrisk = bool(ev.get("negRisk"))
        # BUY ALL (underround): need every leg to have an executable ask
        if all(p is not None and 0 < p < 1 for p in ask_p):
            suma = sum(ask_p)
            if suma < 1 - THRESH:
                edge = 1 - suma
                depth = min(ask_s)  # sets assemblable
                arbs.append(dict(venue="POLY", kind="bucket buy-all", title=title, n=len(mkts),
                                 negrisk=negrisk, edge=round(edge, 4), sum=round(suma, 4),
                                 depth_sets=round(depth, 1), capturable=round(edge * depth, 2)))
        # SELL ALL (overround)
        if all(p is not None and 0 < p < 1 for p in bid_p):
            sumb = sum(bid_p)
            if sumb > 1 + THRESH:
                edge = sumb - 1
                depth = min(bid_s)
                arbs.append(dict(venue="POLY", kind="bucket sell-all", title=title, n=len(mkts),
                                 negrisk=negrisk, edge=round(edge, 4), sum=round(sumb, 4),
                                 depth_sets=round(depth, 1), capturable=round(edge * depth, 2)))
    return arbs, n_seen, len(cands)


# ----------------------------------------------------------------------------- Kalshi
def k_book(ticker):
    d = get(f"{KB}/markets/{ticker}/orderbook")
    if not d:
        return None
    ob = d.get("orderbook_fp") or d.get("orderbook") or {}
    yes = ob.get("yes_dollars") or ob.get("yes") or []
    no = ob.get("no_dollars") or ob.get("no") or []

    def best(side):  # ascending; best (highest) bid is LAST
        if not side:
            return (None, None)
        p, s = side[-1]
        return (f(p), f(s))
    yb, ybs = best(yes)  # best YES bid + size
    nb, nbs = best(no)   # best NO bid + size
    # executable asks: buy YES = take best NO bid -> pay 1 - nb, depth = nbs
    yes_ask = (1 - nb) if nb is not None else None
    no_ask = (1 - yb) if yb is not None else None
    return dict(yes_bid=yb, yes_bid_sz=ybs, no_bid=nb, no_bid_sz=nbs,
                yes_ask=yes_ask, yes_ask_sz=nbs, no_ask=no_ask, no_ask_sz=ybs)


def k_scan(series_list):
    arbs = []
    n_ev, n_mkt = 0, 0
    for s in series_list:
        d = get(f"{KB}/markets?series_ticker={s}&status=open&limit=1000")
        if not d:
            continue
        byev = defaultdict(list)
        for m in d.get("markets", []):
            byev[m.get("event_ticker")].append(m)
        for et, mkts in byev.items():
            n_ev += 1
            tickers = [m.get("ticker") for m in mkts]
            with ThreadPoolExecutor(max_workers=12) as ex:
                books = list(ex.map(k_book, tickers))
            n_mkt += len(tickers)
            legs = {}
            for m, b in zip(mkts, books):
                if b is None:
                    continue
                legs[m.get("ticker")] = (m, b)
                # K1 within-market YES+NO
                ya, na = b["yes_ask"], b["no_ask"]
                if ya is not None and na is not None and 0 < ya < 1 and 0 < na < 1:
                    fee = KFEE(ya) + KFEE(na)
                    cost = ya + na + fee
                    if cost < 1 - THRESH:
                        edge = 1 - cost
                        depth = min(b["yes_ask_sz"] or 0, b["no_ask_sz"] or 0)
                        if depth > 0:
                            arbs.append(dict(venue="KALSHI", kind="within yes+no", title=m.get("ticker"),
                                             n=1, edge=round(edge, 4),
                                             sum=round(ya + na, 4), fee=round(fee, 4),
                                             depth_ct=round(depth, 0), capturable=round(edge * depth, 2)))
            # K2 within-event bucket (mutually exclusive series only)
            me = mkts[0].get("mutually_exclusive") if mkts else False
            if me and len(legs) >= 3 and len(legs) == len(mkts):
                bs = [b for (_, b) in legs.values()]
                if all(b["yes_ask"] is not None and 0 < b["yes_ask"] < 1 for b in bs):
                    suma = sum(b["yes_ask"] for b in bs)
                    fee = sum(KFEE(b["yes_ask"]) for b in bs)
                    if suma + fee < 1 - THRESH:
                        edge = 1 - suma - fee
                        depth = min(b["yes_ask_sz"] or 0 for b in bs)
                        if depth > 0:
                            arbs.append(dict(venue="KALSHI", kind="bucket buy-all", title=et,
                                             n=len(bs), edge=round(edge, 4), sum=round(suma, 4),
                                             fee=round(fee, 4), depth_ct=round(depth, 0),
                                             capturable=round(edge * depth, 2)))
                if all(b["yes_bid"] is not None and 0 < b["yes_bid"] < 1 for b in bs):
                    sumb = sum(b["yes_bid"] for b in bs)
                    fee = sum(KFEE(b["yes_bid"]) for b in bs)
                    if sumb - fee > 1 + THRESH:
                        edge = sumb - fee - 1
                        depth = min(b["yes_bid_sz"] or 0 for b in bs)
                        if depth > 0:
                            arbs.append(dict(venue="KALSHI", kind="bucket sell-all", title=et,
                                             n=len(bs), edge=round(edge, 4), sum=round(sumb, 4),
                                             fee=round(fee, 4), depth_ct=round(depth, 0),
                                             capturable=round(edge * depth, 2)))
    return arbs, n_ev, n_mkt


KSERIES = ["KXCPI", "KXCPIYOY", "KXFED", "KXFEDDECISION", "KXPCE", "KXCOREPCE", "KXGDP", "KXNFP",
           "KXPAYROLLS", "KXU3", "KXUNRATE", "KXJOLTS", "KXPPI", "KXRECESSION", "KXRATECUT",
           "KXBTC", "KXBTCD", "KXETH", "KXETHD", "KXBTCMAXMON", "KXBTCMAXY", "KXETHMAXY", "KXBTCMINMON"]

if __name__ == "__main__":
    t0 = time.time()
    print("Scanning Polymarket ...", flush=True)
    pa, pm_seen, pm_cand = pm_scan()
    print(f"  {pm_seen} events enumerated, {pm_cand} partition candidates CLOB-confirmed, {len(pa)} arbs", flush=True)
    print("Scanning Kalshi ...", flush=True)
    ka, k_ev, k_mkt = k_scan(KSERIES)
    print(f"  {k_ev} bucket events / {k_mkt} markets orderbook-checked, {len(ka)} arbs", flush=True)

    allarbs = pa + ka
    total = sum(a["capturable"] for a in allarbs)
    out = dict(ts=time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
               pm_events=pm_seen, pm_candidates=pm_cand, k_events=k_ev, k_markets=k_mkt,
               n_arbs=len(allarbs), total_capturable=round(total, 2), arbs=allarbs,
               elapsed_s=round(time.time() - t0, 1))
    with open("riskless_opportunity_result.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("\n=== LIVE EXECUTABLE ARBS ===")
    for a in sorted(allarbs, key=lambda x: -x["capturable"]):
        print(" ", json.dumps(a))
    if not allarbs:
        print("  (none)")
    print(f"\nTOTAL snapshot capturable $ = {total:.2f}   (n_arbs={len(allarbs)}, {round(time.time()-t0,1)}s)")
