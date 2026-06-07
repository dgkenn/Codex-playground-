"""Root-cause WHY each trade wins/loses, from the per-fill markout log (fills_*.jsonl).

Each row is one simulated fill with REAL markout (live mids): side, price, mid, microprice,
top-of-book imbalance (imb = bid share, 0..1), signed micro-deviation toxicity (tox), and
markout to +5s/+30s and to resolution (mo5/mo30/mo_res; >0 == favorable to us).

The decisive view: bucket fills by the toxicity signal available AT QUOTE TIME (imbalance)
and read the mean markout per bucket. If the loss is adverse selection, markout should fall
monotonically as the book leans against our side -- and micro_gate should be missing exactly
the toxic bucket that baseline keeps. Clustered by window (the unit of inference).

    python analyze_fills.py
HONEST LIMIT: paper models queue position; the markout itself is real, so this measures
toxicity-conditional adverse selection given a fill -- the live pilot adds real queue rank.
"""
from __future__ import annotations
import glob, json, math
from collections import defaultdict


def load():
    files = sorted(glob.glob("gha_data/fills_r*.jsonl")) or sorted(glob.glob("fills*.jsonl"))
    rows = []
    for fp in files:
        for ln in open(fp):
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    return rows, files


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def wcluster_mean(rows, key):
    """Mean of per-window means (clustered by ws) + a crude t vs 0."""
    byw = defaultdict(list)
    for r in rows:
        if r.get(key) is not None:
            byw[r["ws"]].append(r[key])
    wm = [sum(v) / len(v) for v in byw.values() if v]
    if not wm:
        return float("nan"), float("nan"), 0
    m = sum(wm) / len(wm)
    if len(wm) >= 2:
        sd = (sum((x - m) ** 2 for x in wm) / (len(wm) - 1)) ** 0.5
        t = m / (sd / math.sqrt(len(wm))) if sd > 0 else float("nan")
    else:
        t = float("nan")
    return m, t, len(wm)


def report(rows, var):
    rv = [r for r in rows if r["var"] == var]
    if not rv:
        print(f"  ({var}: no fills yet)"); return
    asks = [r for r in rv if r["side"] == "ASK"]
    bids = [r for r in rv if r["side"] == "BID"]
    print(f"\n=== {var}: {len(rv)} fills ({len(asks)} sells / {len(bids)} buys) over "
          f"{len(set(r['ws'] for r in rv))} windows ===")
    for label, mo in (("mo5", "mo5"), ("mo30", "mo30"), ("mo_res(decision)", "mo_res")):
        m, t, nw = wcluster_mean(rv, mo)
        print(f"  mean {label:18}= {m:+.4f}  (window-clustered t={t:+.2f}, {nw}w)")
    # toxicity curve: bucket SELLS by book imbalance (bid share); high imb = buy pressure = adverse sell
    print("  SELL markout by book-imbalance bucket (imb=bid share; high => buy pressure on our ask):")
    buckets = [(0.0, 0.4, "ask-heavy <0.4"), (0.4, 0.6, "balanced .4-.6"),
               (0.6, 0.8, "bid-lean .6-.8"), (0.8, 1.01, "bid-HEAVY >0.8")]
    for lo, hi, name in buckets:
        b = [r for r in asks if r.get("imb") is not None and lo <= r["imb"] < hi]
        if not b:
            print(f"    {name:16}: (none)"); continue
        print(f"    {name:16}: n={len(b):5d}  mo30={mean([r['mo30'] for r in b]):+.4f}  "
              f"mo_res={mean([r['mo_res'] for r in b]):+.4f}")


def main():
    rows, files = load()
    print(f"per-fill markout: {len(rows)} fills from {len(files)} file(s)")
    if not rows:
        print("no fills yet -- the instrumented collector emits fills_*.jsonl at each window settle.")
        return
    for var in ("baseline", "micro_gate"):
        report(rows, var)
    print("\nRead: if loss is adverse selection, SELL mo_res should fall as imbalance rises "
          "(buy pressure), and micro_gate should hold far fewer fills in the bid-HEAVY bucket.")


if __name__ == "__main__":
    main()
