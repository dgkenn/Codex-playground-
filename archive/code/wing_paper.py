#!/usr/bin/env python3
"""wing_paper.py -- FORWARD paper validation of the wing-overpricing (VRP) edge (node MULTISTRIKE-WING-VRP).

The edge (kalshi_wing_vrp.py + independent repro kalshi_wing_verify.py): on the hourly KXBTCD BTC ladder,
deep-OTM WING strikes are systematically OVERPRICED (favorite-longshot / variance risk premium). Selling YES on
4-15c wings during the event's uncertain first half nets ~+1-2c/contract net of fees, tradeable as a TAKER selling
into the real bid (measured wing half-spread 0.2-0.5c). This harness FORWARD-tests that with a FROZEN, conservative,
pre-registered rule -- the charter gate before any live sizing (tested must match live). PROPOSE-ONLY: paper only,
no orders, no live flag/switch/size touched.

FROZEN RULE (pre-registered; do not retune):
  Universe: KXBTCD (hourly BTC "greater than X" ladder).
  Entry: each run, for every OPEN market whose event is still in its FIRST HALF (now <= open + 0.5*(close-open)),
    if the YES mid (=(yes_bid+yes_ask)/2) is in [0.04, 0.15] AND yes_bid > 0 AND not already recorded:
    record a paper SELL of 1 YES contract at the executable price = yes_bid (conservative TAKER: hit the bid).
  Exit: hold to settlement. PnL/contract = sell_price - outcome - fee, outcome = 1 if result=='yes' else 0,
    fee = max(0.01, ceil(0.07*p*(1-p)*100)/100) at the sell price.
  Gate: pooled per-close-DATE day-clustered t of mean PnL. PASS = >=10 forward dates AND t>=2 AND mean>0;
    KILL = >=10 dates AND t<0. Wing bin 0.04-0.15 only (<=0.02 was taker-dead in the backtest).

Files (idempotent): wing_paper_positions.jsonl (open paper sells), wing_paper_settled.jsonl (resolved w/ PnL).
Usage: python wing_paper.py snapshot | settle | report   (a full run does snapshot then settle then report)
"""
import urllib.request, json, math, time, sys, os
from datetime import datetime, timezone
from collections import defaultdict
import statistics as st

B = "https://api.elections.kalshi.com/trade-api/v2"
POS = "wing_paper_positions.jsonl"
SET = "wing_paper_settled.jsonl"
WING_LO, WING_HI = 0.04, 0.15
FEE = lambda p: max(0.01, math.ceil(0.07 * p * (1 - p) * 100) / 100)


def get(url, tries=4):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except Exception:
            time.sleep(1 + i)
    return {}


def _paged(path, key, cap=100000):
    out, cur = [], None
    while len(out) < cap:
        d = get(path + (f"&cursor={cur}" if cur else ""))
        rows = d.get(key, [])
        out += rows
        cur = d.get("cursor")
        if not cur or not rows:
            break
    return out


def _load(fn):
    if not os.path.exists(fn):
        return []
    out = []
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


def snapshot():
    have = {p["ticker"] for p in _load(POS)}
    now = time.time()
    mkts = _paged(f"{B}/markets?series_ticker=KXBTCD&status=open&limit=400", "markets")
    n = 0
    with open(POS, "a") as f:
        for m in mkts:
            tkr = m.get("ticker")
            if tkr in have:
                continue
            ot, cl = _iso(m.get("open_time") or ""), _iso(m.get("close_time") or "")
            if not ot or not cl or cl <= now:
                continue
            if now > ot + 0.5 * (cl - ot):            # only the uncertain FIRST HALF
                continue
            try:
                yb = float(m.get("yes_bid_dollars")); ya = float(m.get("yes_ask_dollars"))
            except (TypeError, ValueError):
                continue
            mid = (yb + ya) / 2
            if not (WING_LO <= mid <= WING_HI) or yb <= 0:
                continue
            rec = dict(ticker=tkr, event=m.get("event_ticker"), ts=round(now, 1),
                       sell_price=yb, yes_bid=yb, yes_ask=ya, mid=mid,
                       floor_strike=m.get("floor_strike"), close_time=m.get("close_time"))
            f.write(json.dumps(rec) + "\n")
            have.add(tkr)
            n += 1
    print(f"[snapshot] {len(mkts)} open KXBTCD markets, {n} new wing paper-sells recorded")


def settle():
    done = {s["ticker"] for s in _load(SET)}
    open_pos = [p for p in _load(POS) if p["ticker"] not in done]
    n = 0
    with open(SET, "a") as f:
        for p in open_pos:
            m = get(f"{B}/markets/{p['ticker']}").get("market", {})
            res = m.get("result")
            if res not in ("yes", "no"):
                continue
            outcome = 1 if res == "yes" else 0
            sp = p["sell_price"]
            pnl = sp - outcome - FEE(sp)
            day = (p.get("close_time") or "")[:10]
            rec = dict(p, result=res, outcome=outcome, pnl=round(pnl, 4), close_date=day)
            f.write(json.dumps(rec) + "\n")
            n += 1
    print(f"[settle] {len(open_pos)} unresolved paper-sells checked, {n} newly settled")


def report():
    s = _load(SET)
    if not s:
        print("[report] no settled paper positions yet — CLOCK-NOT-STARTED")
        return
    byday = defaultdict(list)
    for r in s:
        byday[r["close_date"]].append(r["pnl"])
    dm = {d: st.mean(v) for d, v in byday.items() if v}
    days = sorted(dm)
    means = [dm[d] for d in days]
    n = len(means)
    allpnl = [r["pnl"] for r in s]
    if n >= 2 and st.stdev(means) > 0:
        t = st.mean(means) / (st.stdev(means) / math.sqrt(n))
    else:
        t = float("nan")
    status = ("PASS" if (n >= 10 and t >= 2 and st.mean(means) > 0)
              else "KILL" if (n >= 10 and t < 0) else "ACCRUING")
    print(f"[report] WING-VRP forward paper gate: status={status}")
    print(f"  settled paper-sells={len(s)}  forward-dates={n}  "
          f"mean=${st.mean(allpnl):+.4f}/ct  per-date day-clustered t={t:.2f}")
    print(f"  win rate (pnl>0)={sum(1 for p in allpnl if p>0)/len(allpnl):.3f}  "
          f"(a wing SELL wins when it settles NO)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("snapshot", "all"):
        snapshot()
    if mode in ("settle", "all"):
        settle()
    if mode in ("report", "all"):
        report()
