#!/usr/bin/env python3
"""pmkt_econ_paper.py -- FORWARD paper sleeve #2: Polymarket ECON macro-release longshot premium
(node MULTISTRAT-ECON). READ-ONLY Polymarket public API, NO orders, NO capital. PROPOSE-ONLY.

Edge (confirmed backtest, my recompute matches): SELLING far-from-consensus BUCKETS of recurring
multi-strike MACRO-RELEASE events (CPI / PPI / jobs / unemployment / JOLTS / Fed / GDP) earns the same
longshot risk premium as the crypto sleeve, but on events UNCORRELATED with crypto (weekly-PnL corr -0.01)
-> it DIVERSIFIES the short-vol tail. Equal-wt t=3.09, YES-buy-share-wt t=3.77, 55 weeks. CAVEATS baked in:
wider spread (~2c) and a capacity limit (dollar-wt t=1.90) -> size SMALLER than crypto, sell into small buyers.

POPULATION MATCH (critical): the edge lives in RECURRING multi-outcome bucket releases, NOT long-dated econ
one-offs. This harness discovers active macro-release EVENTS with >=4 mutually-exclusive bucket markets and
sells the longshot buckets (mid in [0.10,0.35]) during the event's first half. Frozen rule; PMKT_SHORTVOL.md
sibling. Gate + tail metrics mirror the crypto sleeve.

Usage: python pmkt_econ_paper.py snapshot | settle | report   (no arg = all three)
"""
import urllib.request, urllib.parse, json, math, time, os, sys
from datetime import datetime, timezone
from collections import defaultdict
import statistics as st

GAMMA = "https://gamma-api.polymarket.com"
POS = "pmkt_econ_positions.jsonl"
SET = "pmkt_econ_settled.jsonl"
BAND = (0.10, 0.35)
# recurring macro-release families (the edge's population). NOT long-dated one-offs.
QUERIES = ["CPI", "inflation", "PPI", "jobs report", "unemployment", "JOLTS",
           "Fed decision", "GDP", "nonfarm", "core PCE", "retail sales"]


def _get(url, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except Exception:
            time.sleep(1 + i)
    return None


def _load(fn):
    out = []
    if os.path.exists(fn):
        with open(fn) as f:
            for l in f:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def _iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def snapshot():
    have = {p["market_id"] for p in _load(POS)}
    now = time.time()
    n = 0
    seen_events = set()
    with open(POS, "a") as fh:
        for q in QUERIES:
            d = _get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&events_status=active&limit=20")
            if not d:
                continue
            for ev in d.get("events", []):
                et = ev.get("id") or ev.get("slug")
                if et in seen_events:
                    continue
                seen_events.add(et)
                mkts = ev.get("markets", [])
                if len(mkts) < 4:            # need a real bucket structure (mutually-exclusive outcomes)
                    continue
                ev_end = _iso(ev.get("endDate") or "")
                ev_start = _iso(ev.get("startDate") or ev.get("createdAt") or "")
                if not ev_end or ev_end <= now:
                    continue
                # first half of the event's life (uncertain window)
                if ev_start and now > ev_start + 0.5 * (ev_end - ev_start):
                    continue
                for m in mkts:
                    mid_ = m.get("id")
                    if mid_ in have:
                        continue
                    bb, ba = _f(m.get("bestBid")), _f(m.get("bestAsk"))
                    if bb is None or ba is None or bb <= 0:
                        continue
                    mid = (bb + ba) / 2
                    if not (BAND[0] <= mid <= BAND[1]):
                        continue
                    rec = dict(market_id=mid_, event=str(et), event_title=ev.get("title", "")[:80],
                               question=m.get("question", "")[:100], ts=round(now, 1),
                               sell_price=bb, best_bid=bb, best_ask=ba, mid=mid,
                               half_spread=round((ba - bb) / 2, 4),
                               end=ev.get("endDate"))
                    fh.write(json.dumps(rec) + "\n")
                    have.add(mid_)
                    n += 1
    print(f"[econ snapshot] {len(seen_events)} macro-release events scanned, {n} new bucket-longshot paper-sells")


def settle():
    done = {s["market_id"] for s in _load(SET)}
    openp = [p for p in _load(POS) if p["market_id"] not in done]
    n = 0
    with open(SET, "a") as fh:
        for p in openp:
            m = _get(f"{GAMMA}/markets/{p['market_id']}")
            if isinstance(m, list):
                m = m[0] if m else None
            if not m:
                continue
            closed = m.get("closed") or m.get("umaResolutionStatus") == "resolved"
            op = m.get("outcomePrices")
            if not closed or not op:
                continue
            try:
                prices = json.loads(op) if isinstance(op, str) else op
                yes_out = 1.0 if float(prices[0]) > 0.5 else 0.0
            except Exception:
                continue
            pnl = p["sell_price"] - yes_out
            day = (p.get("end") or "")[:10]
            fh.write(json.dumps(dict(p, outcome=yes_out, pnl=round(pnl, 4), close_date=day)) + "\n")
            n += 1
    print(f"[econ settle] {len(openp)} open checked, {n} newly settled")


def report():
    s = _load(SET)
    if not s:
        print("[econ report] no settled econ paper positions yet — CLOCK-NOT-STARTED")
        return
    byday = defaultdict(list)
    for r in s:
        byday[r["close_date"]].append(r["pnl"])
    dm = {d: st.mean(v) for d, v in byday.items() if v}
    days = sorted(dm)
    xs = [dm[d] for d in days]
    n = len(xs)
    t = st.mean(xs) / (st.stdev(xs) / math.sqrt(n)) if n > 1 and st.stdev(xs) > 0 else float("nan")
    worst = min(xs) if xs else float("nan")
    status = ("PASS" if (n >= 8 and t >= 2 and st.mean(xs) > 0 and worst >= -0.60)
              else "KILL" if (n >= 8 and t < 0) else "ACCRUING")
    allp = [r["pnl"] for r in s]
    print(f"[econ report] PMKT-ECON forward paper gate: status={status}")
    print(f"  settled={len(s)}  resolution-periods={n}  mean=${st.mean(allp):+.4f}/ct  "
          f"period-clustered t={t:.2f}  worst-period={worst:+.3f}  win%={sum(1 for p in allp if p>0)/len(allp)*100:.0f}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("snapshot", "all"):
        snapshot()
    if mode in ("settle", "all"):
        settle()
    if mode in ("report", "all"):
        report()
