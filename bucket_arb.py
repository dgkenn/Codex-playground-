#!/usr/bin/env python3
"""bucket_arb.py -- RISKLESS bucket-arbitrage scanner + paper sleeve #4 (node RISKLESS). READ-ONLY, PROPOSE-ONLY.

Polymarket exclusive-exhaustive bucket events (CPI/GDP/Fed/... with a full partition of outcomes): exactly ONE
bucket pays $1 at resolution. So:
  - UNDERROUND: sum(best asks) < 1 -> BUY every bucket for sum(asks), collect $1 -> locked +[1 - sum(asks)].
  - OVERROUND:  sum(best bids) > 1 -> SELL every bucket for sum(bids), pay $1 -> locked +[sum(bids) - 1].
Zero fee. The catch is LEG/STRAND RISK (must fill ALL legs) -> paper assumes atomic fill; the strand model (#2)
will estimate real fill prob. HONEST VALIDATION AT SETTLEMENT: a truly exclusive-exhaustive set has exactly ONE
YES winner; if the settled set has 0 or >=2 winners the "arb" was ILLUSORY (overlapping/incomplete) -> recorded as
NOT-EXHAUSTIVE, realized separately, so we never fool ourselves that an illusory arb was riskless.

snapshot: scan bucket events, record any underround/overround > THRESH with per-bucket entry prices.
settle:   at resolution, count YES winners; realized = locked profit if exactly-one-winner (real), else the true
          (possibly negative) outcome flagged not-exhaustive.
report:   n arbs, size distribution, realized-vs-theoretical, exhaustiveness hit rate, total locked $.
"""
import urllib.request, urllib.parse, json, math, time, os, sys
from datetime import datetime, timezone
import statistics as st

GAMMA = "https://gamma-api.polymarket.com"
POS = "bucket_arb_positions.jsonl"
SET = "bucket_arb_settled.jsonl"
THRESH = 0.01                 # min locked edge to record (>1c/$1)
QUERIES = ["CPI", "inflation", "PPI", "jobs", "unemployment", "JOLTS", "Fed decision", "GDP",
           "nonfarm", "core PCE", "rate cut", "recession", "market cap", "IPO"]


def get(url):
    for i in range(3):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except Exception:
            time.sleep(1 + i)
    return None


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _load(fn):
    out = []
    if os.path.exists(fn):
        with open(fn) as fh:
            for l in fh:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def snapshot():
    have = {p["event_id"] for p in _load(POS)}
    now = time.time()
    seen, n = set(), 0
    with open(POS, "a") as fh:
        for q in QUERIES:
            d = get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&events_status=active&limit=25")
            if not d:
                continue
            for ev in d.get("events", []):
                eid = ev.get("id")
                if eid in seen or eid in have:
                    continue
                seen.add(eid)
                mkts = ev.get("markets", [])
                if len(mkts) < 3:                       # a partition worth arbing
                    continue
                legs, ok = [], True
                for m in mkts:
                    ba, bb = f(m.get("bestAsk")), f(m.get("bestBid"))
                    if ba is None or bb is None or not (0 < ba < 1) or not (0 <= bb < 1):
                        ok = False
                        break
                    legs.append(dict(q=m.get("question", "")[:60], ask=ba, bid=bb,
                                     mid=(ba + bb) / 2, market_id=m.get("id")))
                if not ok:
                    continue
                summid = sum(l["mid"] for l in legs)
                if not (0.85 <= summid <= 1.20):        # exclusive-exhaustive proxy
                    continue
                suma, sumb = sum(l["ask"] for l in legs), sum(l["bid"] for l in legs)
                side = None
                if suma < 1 - THRESH:
                    side, locked = "buy_all", round(1 - suma, 4)
                elif sumb > 1 + THRESH:
                    side, locked = "sell_all", round(sumb - 1, 4)
                if side:
                    rec = dict(event_id=eid, title=ev.get("title", "")[:70], ts=round(now, 1),
                               side=side, n=len(legs), sum_ask=round(suma, 4), sum_bid=round(sumb, 4),
                               locked=locked, end=ev.get("endDate"),
                               legs=[{"market_id": l["market_id"], "ask": l["ask"], "bid": l["bid"]} for l in legs])
                    fh.write(json.dumps(rec) + "\n")
                    have.add(eid)
                    n += 1
    print(f"[bucket_arb snapshot] {len(seen)} bucket events scanned, {n} new riskless underround/overround recorded")


def settle():
    done = {s["event_id"] for s in _load(SET)}
    openp = [p for p in _load(POS) if p["event_id"] not in done]
    n = 0
    with open(SET, "a") as fh:
        for p in openp:
            outs, resolved = [], True
            for leg in p["legs"]:
                m = get(f"{GAMMA}/markets/{leg['market_id']}")
                if isinstance(m, list):
                    m = m[0] if m else None
                if not m or not (m.get("closed") or m.get("umaResolutionStatus") == "resolved"):
                    resolved = False
                    break
                op = m.get("outcomePrices")
                try:
                    pr = json.loads(op) if isinstance(op, str) else op
                    outs.append(1 if float(pr[0]) > 0.5 else 0)
                except Exception:
                    resolved = False
                    break
            if not resolved:
                continue
            winners = sum(outs)
            exhaustive = (winners == 1)               # exactly one bucket pays -> truly exclusive-exhaustive
            if p["side"] == "buy_all":
                realized = winners * 1.0 - p["sum_ask"]   # you paid sum_ask, receive $1 per winner
            else:
                realized = p["sum_bid"] - winners * 1.0   # you received sum_bid, pay $1 per winner
            rec = dict(event_id=p["event_id"], title=p["title"], side=p["side"], n=p["n"],
                       locked_theo=p["locked"], winners=winners, exhaustive=exhaustive,
                       pnl=round(realized, 4), close_date=(p.get("end") or "")[:10])
            fh.write(json.dumps(rec) + "\n")
            n += 1
    print(f"[bucket_arb settle] {len(openp)} open checked, {n} newly settled")


def report():
    s = _load(SET)
    o = _load(POS)
    if not s:
        print(f"[bucket_arb report] {len(o)} arbs recorded, none settled yet — CLOCK-NOT-STARTED")
        if o:
            locks = [p["locked"] for p in o]
            print(f"  recorded locked-edge: mean={st.mean(locks):+.4f} max={max(locks):+.4f} n={len(o)} "
                  f"({sum(1 for p in o if p['side']=='buy_all')} buy-all / {sum(1 for p in o if p['side']=='sell_all')} sell-all)")
        return
    real = [r for r in s if r["exhaustive"]]
    fake = [r for r in s if not r["exhaustive"]]
    print(f"[bucket_arb report] settled={len(s)}  truly-exhaustive(real arb)={len(real)}  "
          f"NOT-exhaustive(illusory)={len(fake)}")
    if real:
        pnls = [r["pnl"] for r in real]
        print(f"  REAL arbs: total locked=${sum(pnls):+.3f}  mean=${st.mean(pnls):+.4f}/arb  "
              f"all>=0? {all(p>=-1e-9 for p in pnls)}  (should be TRUE if truly riskless)")
    if fake:
        print(f"  ILLUSORY (not exhaustive): n={len(fake)} total=${sum(r['pnl'] for r in fake):+.3f} "
              f"-> these show the leg/exhaustiveness risk; NOT riskless")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("snapshot", "all"):
        snapshot()
    if mode in ("settle", "all"):
        settle()
    if mode in ("report", "all"):
        report()
