"""depth_adaptive_validation.py -- resolve the last IN-VALIDATION item in RESEARCH_LEDGER.md.

THE PRE-REGISTERED QUESTION (RESEARCH_LEDGER.md §4, July 2026):
  "Depth_adaptive sizing -- IN-VALIDATION (1/15 distinct-calendar-day gate ...). Review at ~15-day
   mark; if station-median depth swings >=2x sweep-to-sweep, do NOT adopt -- stay on fixed
   DEPTH_CAP=25 permanently; else adopt alpha=0.25 vs pessimistic depth measure."

In July the data was pseudo-replicated (86 rows = 3 sweeps of ~29 markets on ONE day), so the gate
could not be evaluated. As of 2026-09-30 `wx_book_snapshots.jsonl` carries 4,396 snapshots spanning
15 distinct `lst_date` values (2026-09-15 .. 2026-09-29) -- the gate is met, and the frozen rule can
finally be applied.

This script applies it verbatim. No bar is moved: the rule was written before the data existed.

Input: venue_expansion/paper5/wx_book_snapshots.jsonl, a snapshot of the live branch's
       wx_book_snapshots.jsonl (reproduce with:
       git show origin/claude/coding-bot-ab-test-results-ffmhxw:wx_book_snapshots.jsonl)
Usage: python venue_expansion/depth_adaptive_validation.py
"""
from __future__ import annotations

import collections
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(HERE, "paper5", "wx_book_snapshots.jsonl")
OUT = os.path.join(HERE, "out", "depth_adaptive_validation.json")
GATE_DAYS = 15
SWING_THRESHOLD = 2.0


def station_of(row):
    """Series ticker is the station proxy the deployed sizing code keys on."""
    et = row.get("event_ticker") or ""
    return et.split("-")[0] if et else "?"


def main():
    rows = [json.loads(l) for l in open(SNAPS) if l.strip()]
    days = sorted({r.get("lst_date") for r in rows if r.get("lst_date")})
    gate_met = len(days) >= GATE_DAYS
    print(f"snapshots={len(rows):,}  distinct days={len(days)} ({days[0]} .. {days[-1]})  "
          f"gate(>={GATE_DAYS}) {'MET' if gate_met else 'NOT MET'}")
    if not gate_met:
        print("gate not met -- the frozen rule is not yet evaluable; do not improvise a verdict.")
        return

    # Per (station, day) median of the pessimistic depth measure the rule names.
    per = collections.defaultdict(list)
    for r in rows:
        d = r.get("depth_at_or_below_98c")
        if isinstance(d, (int, float)) and d > 0:
            per[(station_of(r), r["lst_date"])].append(float(d))
    by_station = collections.defaultdict(dict)
    for (s, day), v in per.items():
        by_station[s][day] = st.median(v)

    ratios, detail = [], []
    for s, v in sorted(by_station.items()):
        if len(v) < 2:
            continue
        ms = list(v.values())
        lo, hi = min(ms), max(ms)
        ratio = (hi / lo) if lo > 0 else float("inf")
        ratios.append(ratio)
        detail.append({"station": s, "days": len(v), "min_median": lo, "max_median": hi,
                       "swing_ratio": round(ratio, 2), "swings_ge_2x": ratio >= SWING_THRESHOLD})

    n_swing = sum(1 for r in ratios if r >= SWING_THRESHOLD)
    frac = n_swing / len(ratios) if ratios else 0.0
    adopt = frac < 0.5
    alld = [d for v in per.values() for d in v]

    print(f"\nstations with >=2 days: {len(ratios)}")
    print(f"stations swinging >={SWING_THRESHOLD:g}x: {n_swing}/{len(ratios)} ({100*frac:.0f}%)  "
          f"median swing ratio={st.median(ratios):.2f}  max={max(ratios):.1f}")
    print(f"\nFROZEN RULE: swings >={SWING_THRESHOLD:g}x => DO NOT ADOPT (keep fixed DEPTH_CAP=25); "
          f"else adopt alpha=0.25")
    print(f"=> VERDICT: {'ADOPT alpha=0.25' if adopt else 'DO NOT ADOPT -- keep fixed DEPTH_CAP=25 permanently'}")
    print(f"\nside finding (depth is NOT scarce): contracts at/below 98c -- "
          f"median={st.median(alld):.0f} p25={st.quantiles(alld,n=4)[0]:.0f} "
          f"p75={st.quantiles(alld,n=4)[2]:.0f} max={max(alld):.0f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"snapshots": len(rows), "distinct_days": len(days),
               "day_range": [days[0], days[-1]], "gate_met": gate_met,
               "stations_evaluated": len(ratios), "stations_swinging_ge_2x": n_swing,
               "fraction_swinging": round(frac, 4),
               "median_swing_ratio": round(st.median(ratios), 2),
               "max_swing_ratio": round(max(ratios), 2),
               "verdict": "ADOPT_alpha_0.25" if adopt else "DO_NOT_ADOPT_keep_fixed_DEPTH_CAP_25",
               "depth_at_or_below_98c": {"median": st.median(alld),
                                         "p25": st.quantiles(alld, n=4)[0],
                                         "p75": st.quantiles(alld, n=4)[2],
                                         "max": max(alld)},
               "per_station": detail}, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
