"""verify_settlement_truth.py -- does the forecast paper sleeve score its trades against
the outcome Kalshi ACTUALLY settled?

The sleeve's `settle()` decides `yes_won` itself, by pulling the day's max/min from IEM ASOS and
testing it against the rung's own `lo`/`hi` bounds. That is a re-implementation of Kalshi's
settlement rule, not Kalshi's settlement. If the bracket-boundary convention is off (inclusive vs
exclusive edge, F rounding, local-day window), every trade in the log is scored against the wrong
answer and the whole P&L is fiction -- in a direction that has nothing to do with forecast skill.

Kalshi publishes the official settled outcome per market (`result`: "yes"/"no"). This script
compares the two, trade by trade, and re-derives the sleeve's P&L under the official outcome.

Read-only; public endpoint, no auth. Caches to venue_expansion/cache/official_results.json.
"""
from __future__ import annotations

import collections
import json
import math
import os
import statistics as st
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SETTLED = os.path.join(HERE, "paper", "wx_forecast_settled.jsonl")
AUDIT = os.path.join(HERE, "out", "forecast_paper_audit.json")
CACHE = os.path.join(HERE, "cache", "official_results.json")
OUT = os.path.join(HERE, "out", "settlement_truth.json")
API = "https://api.elections.kalshi.com/trade-api/v2"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return json.load(fh)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def _fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def day_clustered(rows, key):
    byday = collections.defaultdict(list)
    for r in rows:
        byday[r["date"]].append(key(r))
    dm = [st.mean(v) for v in byday.values()]
    if len(dm) < 2:
        return None, None, len(dm)
    m = st.mean(dm)
    se = st.stdev(dm) / math.sqrt(len(dm))
    return m, (m / se if se else float("nan")), len(dm)


def main():
    rows = [json.loads(l) for l in open(SETTLED) if l.strip()]
    # true executable costs measured in the previous step (candlestick bid/ask at signal)
    cost = {}
    if os.path.exists(AUDIT):
        for t in json.load(open(AUDIT))["trades"]:
            cost[(t["ticker"], t["side"], t["date"])] = t["true_cost"]

    tickers = sorted({r["ticker"] for r in rows})
    truth = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [t for t in tickers if t not in truth]
    print(f"tickers: {len(tickers)}  cached: {len(tickers)-len(todo)}  to fetch: {len(todo)}")
    for i, t in enumerate(todo, 1):
        try:
            m = get(f"{API}/markets/{t}").get("market", {})
            truth[t] = {"result": m.get("result"), "status": m.get("status")}
        except Exception as e:
            truth[t] = {"result": None, "status": f"ERR {type(e).__name__}"}
        time.sleep(0.12)
        if i % 50 == 0:
            print(f"  fetched {i}/{len(todo)}")
            json.dump(truth, open(CACHE, "w"))
    json.dump(truth, open(CACHE, "w"))
    print("official result values:", collections.Counter(v["result"] for v in truth.values()))

    agree = dis = nores = 0
    examples = []
    scored = []
    for r in rows:
        off = truth.get(r["ticker"], {}).get("result")
        if off not in ("yes", "no"):
            nores += 1
            continue
        off_yes = off == "yes"
        if off_yes == r["yes_won"]:
            agree += 1
        else:
            dis += 1
            if len(examples) < 10:
                examples.append({"ticker": r["ticker"], "lo": r["lo"], "hi": r["hi"],
                                 "iem_realized": r["realized"], "sleeve_yes_won": r["yes_won"],
                                 "official": off, "side": r["side"], "logged_pnl": r["pnl"]})
        c = cost.get((r["ticker"], r["side"], r["date"]))
        if c is not None:
            won_official = off_yes if r["side"] == "yes" else (not off_yes)
            scored.append({**r, "cost": c, "won_official": won_official,
                           "pnl_official": (1.0 - c - _fee(c)) if won_official else (-c - _fee(c))})

    n = agree + dis
    print(f"\nsleeve yes_won vs KALSHI OFFICIAL: agree={agree} DISAGREE={dis} no-result={nores}")
    if n:
        print(f"  -> {100*dis/n:.1f}% of scored paper trades used the WRONG outcome")
    for e in examples:
        print("   ", e)

    if scored:
        print(f"\nP&L at TRUE executable cost, scored on OFFICIAL Kalshi settlement (n={len(scored)}):")
        print(f"{'arm':28s} {'n':>4s} {'win%':>6s} {'EV/ct':>9s} {'day-clust t':>12s} {'days':>5s}")
        for label, sub in (("all", scored),
                           ("YES only", [r for r in scored if r["side"] == "yes"]),
                           ("NO only", [r for r in scored if r["side"] == "no"])):
            if not sub:
                continue
            m, t, d = day_clustered(sub, lambda r: r["pnl_official"])
            ev = st.mean([r["pnl_official"] for r in sub])
            w = 100 * sum(r["won_official"] for r in sub) / len(sub)
            print(f"{label:28s} {len(sub):4d} {w:5.1f}% {ev:+9.4f} {t:+12.2f} {d:5d}")

    json.dump({"agree": agree, "disagree": dis, "no_result": nores,
               "disagreement_pct": round(100 * dis / n, 2) if n else None,
               "examples": examples,
               "n_scored": len(scored),
               "ev_official": round(st.mean([r["pnl_official"] for r in scored]), 4) if scored else None},
              open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
