#!/usr/bin/env python3
"""kalshi_boxwide_report.py -- the GO-LIVE readout for the wide-box (W=15c, minute-2 anchor,
60s-managed-disposal) market-making sleeve on Kalshi's 15-min crypto binaries.

Reads the forward paper-track state (kalshi_boxwide_paper.py output: boxwide_settled.csv +
boxwide_pending.json) and reports per-day and per-asset EV/window, the day-clustered t-stat, the
fraction of days positive, an outcome breakdown (locked/disposed/neither/ride_forced), and a
verdict line against the PRE-REGISTERED PROMOTION BAR from kalshi_boxwide_paper.py's module
docstring:

    >= 14 forward calendar days AND day-clustered t >= 3.0 on realized per-window P&L (net of the
    disposal taker fee) vs a null of 0 AND positive days >= 80% AND per-asset sign consistent with
    the 33-day simulation (an asset whose forward sign flips is DROPPED, not averaged away).

    python kalshi_boxwide_report.py <state_dir>     # dir holding boxwide_settled.csv / _pending.json
"""
import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict

MIN_FORWARD_DAYS = 14
T_BAR = 3.0
POS_DAY_BAR = 0.80
STUDY_ASSETS = ("BTC", "ETH", "SOL", "XRP")   # all 4 were pooled-positive in the simulation


def to_date(ts):
    return (ts or "")[:10] or None


def day_cluster(rows, value_key):
    by_day = defaultdict(list)
    for r in rows:
        d = to_date(r.get("settle_ts"))
        v = r.get(value_key)
        if d is None or v in (None, ""):
            continue
        by_day[d].append(float(v))
    return {d: statistics.mean(vs) for d, vs in by_day.items()}


def day_clustered_verdict(rows, value_key="pnl", null=0.0,
                           min_days=MIN_FORWARD_DAYS, t_bar=T_BAR, pos_bar=POS_DAY_BAR):
    means = day_cluster(rows, value_key)
    n_days = len(means)
    out = {"n_rows": len(rows), "n_days": n_days, "null": null}
    if n_days == 0:
        out.update(verdict="WAIT", reason="0 forward days settled yet")
        return out
    xs = list(means.values())
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if n_days > 1 else 0.0
    se = sd / math.sqrt(n_days) if n_days > 1 else float("nan")
    t = (m - null) / se if se and se == se and se > 0 else float("nan")
    pct_pos = sum(1 for x in xs if x > null) / n_days
    out.update(mean_day=m, stdev_day=sd, t=t, pct_positive=pct_pos)
    if n_days < min_days:
        out.update(verdict="WAIT", reason=f"only {n_days} forward days (<{min_days} required)")
    elif not math.isnan(t) and t >= t_bar and pct_pos >= pos_bar:
        out.update(verdict="PASS (bar cleared -- still requires per-asset sign check + manual "
                            "review before any live step)",
                   reason=f"t={t:.2f}>={t_bar}, %pos={pct_pos:.0%}>={pos_bar:.0%}")
    else:
        tt = f"{t:.2f}" if not math.isnan(t) else "n/a"
        out.update(verdict="FAIL", reason=f"t={tt} (need >={t_bar}), %pos={pct_pos:.0%} (need >={pos_bar:.0%})")
    return out


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    settled_p = os.path.join(d, "boxwide_settled.csv")
    pend_p = os.path.join(d, "boxwide_pending.json")

    rows = list(csv.DictReader(open(settled_p))) if os.path.exists(settled_p) else []
    pend = json.load(open(pend_p)) if os.path.exists(pend_p) else []

    print("=" * 72)
    print("WIDE-BOX (W=15c, minute-2 anchor, 60s managed disposal) -- forward paper-track readout")
    print("=" * 72)

    by_asset_pend = defaultdict(lambda: defaultdict(int))
    for p in pend:
        by_asset_pend[p.get("asset", "?")][p.get("state", "?")] += 1
    print(f"\nOPEN paper positions: {len(pend)}  " +
          (", ".join(f"{a}:{dict(s)}" for a, s in sorted(by_asset_pend.items())) if pend else ""))

    expired = [r for r in rows if r.get("status") == "expired_unscored"]
    rows = [r for r in rows if r.get("status") != "expired_unscored"]
    if expired:
        print(f"\n(expired_unscored, excluded from stats below: {len(expired)})")
    if not rows:
        print("\nNo SETTLED paper windows yet. These are 15-minute markets so settlement should")
        print("be fast once entries start accruing -- re-run after a few windows have resolved.")
        return

    n = len(rows)
    pnl = [float(r["pnl"]) for r in rows]
    print(f"\nSETTLED paper windows: {n}")
    print(f"  realized edge : {sum(pnl)/n*100:+.2f} c/window   (win rate {sum(1 for x in pnl if x>0)/n:.3f})")

    outcomes = defaultdict(int)
    for r in rows:
        outcomes[r["outcome"]] += 1
    print(f"  outcome breakdown: {dict(outcomes)}  "
          f"(locked=both legs filled, disposed=managed-strand taker cross, "
          f"neither=no fill, ride_forced=rare settlement-fallback edge case)")

    day_means = day_cluster(rows, "pnl")
    print(f"\n  per-day mean P&L/window ({len(day_means)} forward day(s)):")
    for day in sorted(day_means):
        print(f"    {day}: {day_means[day]*100:+.2f}c")

    by_asset = defaultdict(list)
    for r in rows:
        by_asset[r["asset"]].append(r)
    print("\n  by asset (realized c/window):")
    dropped_assets = []
    for a in sorted(by_asset):
        ar = by_asset[a]
        av = [float(r["pnl"]) for r in ar]
        mean_a = sum(av) / len(av) * 100
        flag = ""
        if a in STUDY_ASSETS and mean_a < 0:
            flag = "  <-- SIGN FLIP vs simulation: DROP from go-live consideration"
            dropped_assets.append(a)
        elif a not in STUDY_ASSETS:
            flag = "  <-- NOT one of the simulated assets (BTC/ETH/SOL/XRP) -- should not appear"
        print(f"    {a:>4}: n={len(ar):>4}  mean={mean_a:+.2f}c{flag}")

    v = day_clustered_verdict(rows, "pnl")

    print("\n" + "-" * 72)
    print("PRE-REGISTERED PROMOTION BAR (kalshi_boxwide_paper.py docstring):")
    print(f"  >= {MIN_FORWARD_DAYS} forward calendar days AND day-clustered t >= {T_BAR} vs a null "
          f"of 0 (net of fees) AND")
    print(f"  positive days >= {POS_DAY_BAR:.0%} AND per-asset sign consistent with the simulation "
          f"(flipped assets dropped).")
    print("-" * 72)
    tt = f"{v['t']:.2f}" if isinstance(v.get("t"), float) and not math.isnan(v["t"]) else "n/a"
    print(f"  n_days={v['n_days']}  t={tt}  %pos={v.get('pct_positive', 0):.0%}  "
          f"VERDICT={v['verdict']} ({v['reason']})")
    if dropped_assets:
        print(f"\n  ASSETS DROPPED by the per-asset sign-consistency rule: {', '.join(dropped_assets)} "
              f"-- the aggregate verdict above must be re-run excluding them before it can be read "
              f"as a go-live signal (this report does not auto-recompute the aggregate excluding a "
              f"dropped asset; that is a deliberate manual step).")
    print("\nNo live consideration of any kind before the bar clears in full.")


if __name__ == "__main__":
    main()
