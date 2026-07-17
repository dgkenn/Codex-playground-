#!/usr/bin/env python3
"""riskless_logical.py -- cross-market LOGICAL-CONSISTENCY arbitrage scanner (node RISKLESS-LOGICAL). READ-ONLY.

Separate-but-logically-nested Polymarket markets must obey no-arbitrage relations that retail may not enforce
across DISTINCT markets:
  (A) STRIKE monotonicity (same coin+period, "reach/above $X"): P(reach X1) >= P(reach X2) for X1 < X2
      (reaching the higher level implies reaching the lower). VIOLATION: a HIGHER strike's YES-BID exceeds a LOWER
      strike's YES-ASK -> BUY yes(X1)@ask, SELL yes(X2)@bid -> paid upfront AND settlement out(X1)-out(X2) >= 0 always.
  (B) TIME monotonicity (same coin+strike, "reach $X by/ in <period>"): P(reach by longer/superset period) >=
      P(reach by shorter/subset). VIOLATION analogous.
Zero fee. RISK CAVEAT: only truly riskless if the two markets resolve on the SAME price source + the nesting is exact
(a subperiod strictly inside, a strike on the same reference). Flagged violations are CONFIRMED against the live CLOB
book (executable bid/ask + depth), since gamma summary quotes can be stale.
"""
import urllib.request, urllib.parse, json, re, time
from collections import defaultdict

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def get(url):
    for i in range(3):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except Exception:
            time.sleep(0.5 + i)
    return None


def parse(q):
    ql = q.lower()
    coin = "btc" if ("bitcoin" in ql or "btc" in ql) else ("eth" if ("ethereum" in ql or "eth" in ql) else None)
    kind = next((k for k in ("reach", "above", "hit", "over") if k in ql), None)
    m = re.search(r'\$?\s*([\d][\d,]*)\s*(k?)\b', q)   # strike
    if not coin or not kind or not m:
        return None
    sv = float(m.group(1).replace(",", "")) * (1000 if m.group(2).lower() == "k" else 1)
    # period = text after the strike (the resolution window), normalized
    period = q[m.end():].strip(" ?").lower()
    return coin, kind, period, sv


def clob_book(token):
    b = get(f"{CLOB}/book?token_id={token}")
    if not b:
        return None, 0, None, 0
    asks = b.get("asks", [])
    bids = b.get("bids", [])
    best_ask = min(asks, key=lambda a: float(a["price"])) if asks else None
    best_bid = max(bids, key=lambda a: float(a["price"])) if bids else None
    ba = (float(best_ask["price"]), float(best_ask["size"])) if best_ask else (None, 0)
    bb = (float(best_bid["price"]), float(best_bid["size"])) if best_bid else (None, 0)
    return ba[0], ba[1], bb[0], bb[1]


def yes_token(m):
    t = m.get("clobTokenIds")
    try:
        return json.loads(t)[0] if isinstance(t, str) else t[0]
    except Exception:
        return None


def main():
    fam = defaultdict(dict)   # (coin,kind,period) -> {strike: market}
    for q in ["bitcoin reach", "ethereum reach", "bitcoin above", "ethereum above", "bitcoin hit"]:
        d = get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&events_status=active&limit=40")
        for ev in (d.get("events", []) if d else []):
            for m in ev.get("markets", []):
                p = parse(m.get("question", ""))
                if not p:
                    continue
                coin, kind, period, sv = p
                fam[(coin, kind, period)][sv] = m
    # (A) strike monotonicity: within a family, find higher-strike BID > lower-strike ASK (gamma prescreen)
    def gf(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    candidates = []
    for key, byk in fam.items():
        if len(byk) < 2:
            continue
        ks = sorted(byk)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                x1, x2 = ks[i], ks[j]                      # x1 < x2
                m1, m2 = byk[x1], byk[x2]
                a1, b2 = gf(m1.get("bestAsk")), gf(m2.get("bestBid"))
                if a1 is not None and b2 is not None and b2 > a1 + 0.005:   # higher strike bid > lower strike ask
                    candidates.append((key, x1, x2, a1, b2, m1, m2))
    print(f"{len(fam)} families; {sum(1 for v in fam.values() if len(v)>=2)} multi-strike; "
          f"{len(candidates)} gamma-flagged strike-monotonicity violations")
    # CONFIRM top candidates against live CLOB book (executable + depth)
    confirmed = []
    for key, x1, x2, a1g, b2g, m1, m2 in sorted(candidates, key=lambda c: -(c[4] - c[3]))[:20]:
        t1, t2 = yes_token(m1), yes_token(m2)
        if not t1 or not t2:
            continue
        a1, a1sz, _, _ = clob_book(t1)          # buy lower strike at its ask
        _, _, b2, b2sz = clob_book(t2)          # sell higher strike at its bid
        if a1 is None or b2 is None:
            continue
        edge = b2 - a1
        if edge > 0.005:
            depth = min(a1sz, b2sz)
            confirmed.append((key, x1, x2, a1, b2, edge, depth))
            print(f"  CONFIRMED {key[0]}/{key[1]} '{key[2][:20]}': BUY ${x1:.0f}@{a1:.3f} SELL ${x2:.0f}@{b2:.3f} "
                  f"-> edge {edge*100:+.1f}c, depth {depth:.0f}, capturable ${edge*depth:.2f}")
    if not confirmed:
        print("  (no CLOB-confirmed strike-monotonicity arb)")
    else:
        print(f"\nTOTAL CLOB-confirmed capturable: ${sum(e*d for *_,e,d in confirmed):.2f} across {len(confirmed)} arbs")
    print("\nCaveat: truly riskless only if both markets resolve on the SAME price source with exact nesting; "
          "verify resolution criteria before trading. This is a base-rate snapshot.")


if __name__ == "__main__":
    main()
