#!/usr/bin/env python3
"""kalshi_tailbias_report.py -- the GO-LIVE readout for the tail-bias (favorite-longshot bias)
paper sleeve on Kalshi's 15-min crypto binaries.

Reads the forward paper-track state (kalshi_tailbias_paper.py output: tailbias_settled.csv +
tailbias_pending.json) and reports per-day and per-asset EV/contract for BOTH execution variants
(taker/maker), the day-clustered t-stat, the fraction of days positive, and a verdict line against
the PRE-REGISTERED PROMOTION BAR from kalshi_tailbias_paper.py's module docstring:

    >= 14 forward calendar days AND day-clustered t >= 3.0 on the TAKER variant (net of fees) AND
    positive days >= 80% AND per-asset sign consistent with the calibration study (an asset whose
    forward sign flips is DROPPED, not averaged away).

The MAKER variant is reported for visibility only -- its fills are HYPOTHETICAL (no queue model
in the paper tracker); a maker-variant PASS can only justify piloting maker-style execution
INSIDE the live trader (kalshi_trader.py), never a standalone go-live decision. See
kalshi_tailbias_paper.py's module docstring for the full statement.

    python kalshi_tailbias_report.py <state_dir>     # dir holding tailbias_settled.csv / _pending.json
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
STUDY_ASSETS = ("BTC", "ETH", "XRP")   # SOL excluded by the calibration study -- never appears here


def to_date(ts):
    """First-10-chars ISO date out of an ISO8601 timestamp string (settle_ts)."""
    return (ts or "")[:10] or None


def day_cluster(rows, value_key):
    """{date: mean(value_key on that date)} -- one observation per day, so day-to-day
    correlation within a day (shared regime/vol) doesn't inflate the t-stat."""
    by_day = defaultdict(list)
    for r in rows:
        d = to_date(r.get("settle_ts"))
        v = r.get(value_key)
        if d is None or v in (None, ""):
            continue
        by_day[d].append(float(v))
    return {d: statistics.mean(vs) for d, vs in by_day.items()}


def day_clustered_verdict(rows, value_key="pnl_taker", null=0.0,
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
    settled_p = os.path.join(d, "tailbias_settled.csv")
    pend_p = os.path.join(d, "tailbias_pending.json")

    rows = list(csv.DictReader(open(settled_p))) if os.path.exists(settled_p) else []
    pend = json.load(open(pend_p)) if os.path.exists(pend_p) else []

    print("=" * 72)
    print("TAIL-BIAS (favorite-longshot bias, KX*15M crypto) -- forward paper-track readout")
    print("=" * 72)

    # ---- current open exposure ----
    by_asset_pend = defaultdict(int)
    for p in pend:
        by_asset_pend[p.get("asset", "?")] += 1
    print(f"\nOPEN paper positions: {len(pend)}  " +
          (", ".join(f"{k}:{v}" for k, v in sorted(by_asset_pend.items())) if pend else ""))

    # ---- realized results ----
    expired = [r for r in rows if r.get("status") == "expired_unscored"]
    rows = [r for r in rows if r.get("status") != "expired_unscored"]
    if expired:
        print(f"\n(expired_unscored, excluded from stats below: {len(expired)})")
    if not rows:
        print("\nNo SETTLED paper positions yet. These are 15-minute markets so settlement should")
        print("be fast once entries start accruing -- re-run after a few windows have resolved.")
        return

    n = len(rows)
    taker = [float(r["pnl_taker"]) for r in rows]
    maker = [float(r["pnl_maker"]) for r in rows]
    print(f"\nSETTLED paper positions: {n}")
    print(f"  taker  realized edge : {sum(taker)/n*100:+.2f} c/contract   "
          f"(win rate {sum(1 for x in taker if x>0)/n:.3f})")
    print(f"  maker* realized edge : {sum(maker)/n*100:+.2f} c/contract   "
          f"(win rate {sum(1 for x in maker if x>0)/n:.3f})   *HYPOTHETICAL fills, no queue model")

    # ---- per-day breakdown (taker variant, the one the bar governs) ----
    day_means_taker = day_cluster(rows, "pnl_taker")
    print(f"\n  per-day mean taker P&L/contract ({len(day_means_taker)} forward day(s)):")
    for day in sorted(day_means_taker):
        print(f"    {day}: {day_means_taker[day]*100:+.2f}c")

    # ---- per-asset breakdown, both variants + sign-consistency check ----
    by_asset = defaultdict(list)
    for r in rows:
        by_asset[r["asset"]].append(r)
    print("\n  by asset (realized c/contract, taker / maker*):")
    dropped_assets = []
    for a in sorted(by_asset):
        ar = by_asset[a]
        at = [float(r["pnl_taker"]) for r in ar]
        am = [float(r["pnl_maker"]) for r in ar]
        mean_t = sum(at) / len(at) * 100
        mean_m = sum(am) / len(am) * 100
        flag = ""
        if a in STUDY_ASSETS and mean_t < 0:
            flag = "  <-- SIGN FLIP vs calibration study: DROP from go-live consideration"
            dropped_assets.append(a)
        elif a not in STUDY_ASSETS:
            flag = "  <-- NOT one of the calibration-study assets (BTC/ETH/XRP) -- should not appear"
        print(f"    {a:>4}: n={len(ar):>4}  taker={mean_t:+.2f}c  maker*={mean_m:+.2f}c{flag}")

    # ---- day-clustered verdict vs the pre-registered bar (TAKER variant governs) ----
    v_taker = day_clustered_verdict(rows, "pnl_taker")
    v_maker = day_clustered_verdict(rows, "pnl_maker")

    print("\n" + "-" * 72)
    print("PRE-REGISTERED PROMOTION BAR (kalshi_tailbias_paper.py docstring):")
    print(f"  >= {MIN_FORWARD_DAYS} forward calendar days AND day-clustered t >= {T_BAR} on the "
          f"TAKER variant (net of fees) AND")
    print(f"  positive days >= {POS_DAY_BAR:.0%} AND per-asset sign consistent with the study "
          f"(flipped assets dropped).")
    print("-" * 72)
    tt = f"{v_taker['t']:.2f}" if isinstance(v_taker.get("t"), float) and not math.isnan(v_taker["t"]) else "n/a"
    print(f"  TAKER : n_days={v_taker['n_days']}  t={tt}  "
          f"%pos={v_taker.get('pct_positive', 0):.0%}  VERDICT={v_taker['verdict']} ({v_taker['reason']})")
    tm = f"{v_maker['t']:.2f}" if isinstance(v_maker.get("t"), float) and not math.isnan(v_maker["t"]) else "n/a"
    print(f"  MAKER*: n_days={v_maker['n_days']}  t={tm}  "
          f"%pos={v_maker.get('pct_positive', 0):.0%}  VERDICT={v_maker['verdict']} ({v_maker['reason']})"
          "   [HYPOTHETICAL fills -- see docstring: never a standalone go-live signal]")
    if dropped_assets:
        print(f"\n  ASSETS DROPPED by the per-asset sign-consistency rule: {', '.join(dropped_assets)} "
              f"-- the aggregate TAKER verdict above must be re-run excluding them before it can "
              f"be read as a go-live signal (this report does not auto-recompute the aggregate "
              f"excluding a dropped asset; that is a deliberate manual step).")
    print("\nNo live consideration of any kind before the TAKER bar clears in full.")


if __name__ == "__main__":
    main()
