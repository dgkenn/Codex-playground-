#!/usr/bin/env python3
"""wx_cushion_optimize.py -- where does the CUSHION optimum sit, on the full metric set, at real latency?

The half-life study found a tension: SMALL cushion (obs barely cleared the strike) = the gap persists longer
(slow repricing) so at a realistic feed latency we can still enter CHEAP -> more EV/ct; but small cushion also
= higher loss rate (a late CLI revision can flip it). BIG cushion = safe but reprices fast, so by the time a
slow feed sees it the gap is gone (dead on arrival, no EV). So cushion trades RETURN against RISK, and the
answer depends on latency. This finds the optimum on EV / Sharpe / Sortino / profit-factor / worst, per
cushion, AT each latency -- so we can pick the cushion policy that maximizes risk-adjusted return (operator:
"ok taking on some risk if the return is there").

cushion = highest strategy-margin m in {1,2,3} whose m_3 cell fired = degF the obs cleared the strike.
At latency L we enter at price = 1 - gap(L); a fire is TRADEABLE only if that price < 0.99 (else the gap is
gone). EV/ct = outcome - entry - fee. Metrics computed per EXACT cushion and per THRESHOLD (cushion>=k).

Usage: python wx_cushion_optimize.py
"""
import json, os, math, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
LATS = [0, 1, 2, 5, 10, 30]


def fee(p):
    p = min(0.99, max(0.01, p))
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def cushion_of(rec):
    hi = 0
    for m in (1, 2, 3):
        if rec["cells"].get(f"{m}_3", {}).get("fired"):
            hi = m
    return hi


def load():
    raw = json.load(open(RAW))
    out = []
    for r in raw:
        c = r["cells"].get("1_3")
        if not c or not c.get("fired") or not c.get("exec_price") or c["exec_price"] >= 0.99:
            continue
        decay = {int(k): v for k, v in c.get("decay_gap_by_min", {}).items()}
        out.append({"cushion": cushion_of(r), "outcome": c.get("outcome", 1 if c["pnl"] > 0 else 0),
                    "decay": decay, "date": r["date"], "g0": decay.get(0, 1 - c["exec_price"])})
    return out


def entry_at(f, lat):
    """Entry price at latency `lat` (1 - gap). None if the gap is gone (price>=0.99) -> not tradeable."""
    gap = f["decay"].get(lat)
    if gap is None:
        return None
    price = 1.0 - gap
    return price if price < 0.99 else None


def metrics(fires, lat):
    """Metric set for a fire subset at latency lat, over the fires still TRADEABLE then."""
    rows = []
    for f in fires:
        p = entry_at(f, lat)
        if p is None:
            continue
        rows.append((f, p, f["outcome"] - p - fee(p)))
    if len(rows) < 15:
        return None
    pnls = [x[2] for x in rows]
    n = len(pnls)
    ev = st.mean(pnls)
    sd = st.stdev(pnls) if n > 1 else 0.0
    dd = math.sqrt(st.mean([min(0.0, x) ** 2 for x in pnls]))
    wins = [p for p in pnls if p > 0]
    loss = [p for p in pnls if p < 0]
    fill = n / len(fires)          # fraction of this cushion's fires still catchable at this latency
    return {"n": n, "fill": fill, "win": len(wins) / n, "entry": st.mean([x[1] for x in rows]),
            "ev": ev, "sd": sd, "sharpe": ev / sd if sd else float("nan"),
            "sortino": ev / dd if dd else float("inf"), "worst": min(pnls),
            "pf": sum(wins) / (-sum(loss)) if loss else float("inf"),
            "ev_per_fire": ev * fill}   # EV weighted by catch rate = expected value per DETECTED fire


def show(title, groups, lat):
    print(f"\n=== {title} @ latency {lat} min ===")
    print(f"{'cushion':>9}{'n':>6}{'fill%':>7}{'win%':>7}{'entry':>7}{'EV/ct':>8}{'Sharpe':>8}"
          f"{'Sortino':>9}{'worst':>8}{'PF':>7}{'EV*fill':>9}")
    for label, fires in groups:
        m = metrics(fires, lat)
        if not m:
            print(f"{label:>9}   (too few tradeable)"); continue
        srt = "inf" if m["sortino"] == float("inf") else f"{m['sortino']:.2f}"
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.1f}"
        print(f"{label:>9}{m['n']:>6}{100*m['fill']:>6.0f}%{100*m['win']:>6.1f}%{m['entry']:>7.2f}"
              f"{m['ev']:>+8.3f}{m['sharpe']:>8.2f}{srt:>9}{m['worst']:>+8.3f}{pf:>7}{m['ev_per_fire']:>+9.3f}")


def main():
    fires = load()
    byc = defaultdict(list)
    for f in fires:
        byc[f["cushion"]].append(f)
    print(f"cushion optimization | {len(fires)} deployable fires | "
          f"counts by cushion: " + ", ".join(f"{k}F={len(byc[k])}" for k in sorted(byc)))
    print("EV*fill = EV/ct weighted by the fraction still catchable at that latency = expected value per fire "
          "our feed DETECTS.\nloss rate rises as cushion shrinks (barely-cleared can revise); entry gets cheaper "
          "as cushion shrinks (slower repricing).")

    exact = [(f"={k}F", byc[k]) for k in sorted(byc) if byc[k]]
    thresh = [(f">={k}F", [f for f in fires if f["cushion"] >= k]) for k in (1, 2, 3)]

    for lat in (2, 5, 10):
        show("EXACT cushion", exact, lat)
    print("\n" + "-" * 70)
    for lat in (2, 5, 10):
        show("THRESHOLD cushion>=k (the actual policy knob)", thresh, lat)

    print("\nread: pick the cushion policy that maximizes the risk-adjusted metric you care about AT the latency "
          "your feed actually runs (free/MADIS ~10 min; Synoptic ~1-2 min). 'EV*fill' is the bottom line -- EV per\n"
          "fire the feed detects, after both the cheaper-entry benefit and the higher-loss-rate cost of a smaller "
          "cushion. If small-cushion EV*fill dominates with an acceptable Sortino/worst, taking that risk pays.")


if __name__ == "__main__":
    main()
