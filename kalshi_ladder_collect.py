"""kalshi_ladder_collect.py -- shadow collector for MULTI-STRIKE LADDER consistency dislocations.

WHY (KALSHI_GOLD_CANDIDATES.md #3): on a strike ladder ("price > X" for ascending X), monotonicity
requires P(>X_lo) >= P(>X_hi). A CROSSABLE violation -- yes_bid(hi) > yes_ask(lo) -- is a true lock:
buy YES(lo) at the ask + buy NO(hi) at (1 - bid(hi)); payoff is $1 outside (lo,hi] and $2 inside,
cost < $1. The TAKER race for these is dead (our scan: all phantom); the candidate strategy is the
MAKER version (rest orders that only fill at violating prices). This collector measures the
PREREQUISITE: how often crossable / near-crossable states appear, on which ladders, how deep.
Two weeks of this answers "is there a strategy here?" before any building.

Cheap by design: ONE /markets call per series per poll returns every strike's top-of-book.
    python kalshi_ladder_collect.py [duration_s] [out_dir] [tag]
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ["KXBTCD", "KXETHD", "KXINXU", "KXNASDAQ100U"]   # live hourly/daily ladders (probed 2026-06-12)
POLL_S = 45.0          # maker-capturable states persist; no need to race
NEAR_C = 0.01          # record "near-violations" within 1c of crossing (how close does it get?)


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def scan_series(sess, series):
    """One API call -> per-event ladder summary + any (near-)violations at top-of-book."""
    d = sess.get(f"{B}/markets", params={"series_ticker": series, "status": "open", "limit": 200},
                 timeout=10).json()
    events = {}
    for m in d.get("markets") or []:
        if m.get("strike_type") not in ("greater", "greater_or_equal"):
            continue                                   # ladder rungs only (skip ranges/categoricals)
        ev = m.get("event_ticker")
        st = f(m.get("floor_strike"))
        bid, ask = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars"))
        if ev is None or st is None:
            continue
        events.setdefault(ev, []).append((st, bid, ask, m.get("ticker")))
    out = []
    for ev, rungs in events.items():
        rungs.sort()                                   # ascending strike
        viol, near = [], []
        # adjacent AND skip-level pairs: lock iff bid(hi) > ask(lo) (monotonicity crossed at touch)
        for i in range(len(rungs)):
            for j in range(i + 1, min(i + 4, len(rungs))):   # up to 3 strikes apart (wider = rarer)
                (slo, blo, alo, tlo), (shi, bhi, ahi, thi) = rungs[i], rungs[j]
                if alo is None or bhi is None or alo >= 0.995 or bhi <= 0.005:
                    continue                           # dead rungs (0/1 bids) aren't opportunities
                gap = round(bhi - alo, 4)              # > 0 = crossable lock of `gap` dollars
                if gap > 0:
                    viol.append({"lo": tlo, "hi": thi, "gap": gap})
                elif gap > -NEAR_C:
                    near.append({"lo": tlo, "hi": thi, "gap": gap})
        live = [r for r in rungs if r[1] is not None and r[2] is not None
                and 0.01 <= (r[1] + r[2]) / 2 <= 0.99]
        out.append({"event": ev, "n_strikes": len(rungs), "n_live": len(live),
                    "viol": viol[:10], "near": near[:10],
                    "n_viol": len(viol), "n_near": len(near)})
    return out


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"ld{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, f"ladders_{tag}.jsonl.gz")
    fh = gzip.open(fp, "at")
    sess = requests.Session()
    end = time.time() + dur
    n_polls = n_viol = 0
    print(f"ladder_collect: {dur}s, {len(SERIES)} series -> {fp}", flush=True)
    while time.time() < end:
        t0 = time.time()
        for s in SERIES:
            try:
                evs = scan_series(sess, s)
            except Exception as e:
                print(f"  {s}: ERR {str(e)[:60]}", flush=True)
                continue
            for e in evs:
                if e["n_viol"] or e["n_near"]:
                    fh.write(json.dumps({"t": round(time.time(), 1), "series": s, **e}) + "\n")
                    n_viol += e["n_viol"]
            time.sleep(0.3)
        # heartbeat line per poll cycle even when quiet (so absence-of-violations is ALSO data)
        fh.write(json.dumps({"t": round(time.time(), 1), "hb": 1,
                             "polled": len(SERIES)}) + "\n")
        fh.flush()
        n_polls += 1
        time.sleep(max(0.0, POLL_S - (time.time() - t0)))
    fh.close()
    print(f"done: {n_polls} polls, {n_viol} crossable violations seen", flush=True)


if __name__ == "__main__":
    main()
