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

PRE-REGISTERED PRIMARY vs P300 CHALLENGER: the bar above is defined, and stays defined, on the
P60 (60s disposal) policy ONLY -- that is what was pre-registered from the width simulation
before any of this forward data existed, and this report's verdict/go-live gate never moves off
of it. kalshi_boxwide_paper.py additionally tracks a P300 (300s, DP-study-informed) disposal
policy in PARALLEL off the same fills/tape (see that module's "P300 PARALLEL CHALLENGER TRACK"
docstring section). This report prints P60's and P300's per-day EV side by side purely for
comparison, plus the PAIRED per-box delta (P300 - P60) with its own day-clustered t -- that
paired delta, not either policy's raw EV, is the right statistic to decide whether P300 is worth
separately pre-registering later: it isolates the disposal-policy effect box-by-box instead of
comparing two differently-sized, differently-timed samples. Until/unless that delta clears its
own bar and gets pre-registered, P300 is informational only and changes no live/promotion
decision here.

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


def to_float_or_none(v):
    """Numeric coercion that tolerates the blank/"" markers this module and kalshi_boxwide_paper.py
    both use for "not applicable" cells (e.g. an old settled row with no p300_pnl column at all,
    or a "neither"/expired row's blank fee_c) -- returns None instead of raising, so callers can
    filter rather than crash on backward-compat gaps."""
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def day_cluster(rows, value_key):
    by_day = defaultdict(list)
    for r in rows:
        d = to_date(r.get("settle_ts"))
        v = r.get(value_key)
        if d is None or v in (None, ""):
            continue
        by_day[d].append(float(v))
    return {d: statistics.mean(vs) for d, vs in by_day.items()}


def day_clustered_stats(rows, value_key, null=0.0):
    """Bare day-clustered mean/t-stat (no promotion-bar verdict logic) -- shared by the P300
    per-day printout and the paired P300-P60 delta below. One mean-per-day observation, t computed
    across those day-means, same discipline as day_clustered_verdict (rows within a day are not
    independent draws)."""
    means = day_cluster(rows, value_key)
    n_days = len(means)
    out = {"n_rows": len(rows), "n_days": n_days, "null": null}
    if n_days == 0:
        out.update(mean_day=float("nan"), stdev_day=float("nan"), t=float("nan"),
                    pct_positive=float("nan"))
        return out
    xs = list(means.values())
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if n_days > 1 else 0.0
    se = sd / math.sqrt(n_days) if n_days > 1 else float("nan")
    t = (m - null) / se if se and se == se and se > 0 else float("nan")
    pct_pos = sum(1 for x in xs if x > null) / n_days
    out.update(mean_day=m, stdev_day=sd, t=t, pct_positive=pct_pos)
    return out


def paired_delta_rows(rows):
    """One row per settled box that has BOTH a P60 pnl and a P300 pnl available (drops rows from
    an old pre-P300 settled CSV that lack the p300_pnl column entirely, and non-scoring outcomes
    like "neither"/expired where pnl is blank for one or both) -- delta = P300 pnl - P60 pnl,
    keyed to the row's settle_ts so day_clustered_stats can cluster it the same way."""
    out = []
    for r in rows:
        p60_pnl = to_float_or_none(r.get("pnl"))
        p300_pnl = to_float_or_none(r.get("p300_pnl"))
        if p60_pnl is None or p300_pnl is None:
            continue
        out.append({"settle_ts": r.get("settle_ts"), "delta": p300_pnl - p60_pnl})
    return out


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

    # ------------------------------------------------------------------------------------------
    # P300 CHALLENGER TRACK -- informational, does NOT move the verdict above. Rows from an old
    # pre-P300 settled CSV (no p300_pnl column) simply drop out of both the P300-only stats and
    # the paired delta below; they still count fully toward the P60 verdict printed above.
    # ------------------------------------------------------------------------------------------
    p300_rows = [r for r in rows if to_float_or_none(r.get("p300_pnl")) is not None]
    n_missing_p300 = n - len(p300_rows)
    print("\n" + "=" * 72)
    print("P300 CHALLENGER (300s disposal deadline, or window_close-45s if sooner) -- DP-study-")
    print("informed, tracked in PARALLEL off the same fills/tape as P60. Informational only: the")
    print("pre-registered PRIMARY policy remains P60 (60s) above; this section never changes that")
    print("verdict. See kalshi_boxwide_paper.py's \"P300 PARALLEL CHALLENGER TRACK\" docstring.")
    print("=" * 72)
    if n_missing_p300:
        print(f"\n  ({n_missing_p300} of {n} settled rows predate the P300 columns and are excluded "
              f"from the P300/delta stats below -- they still count toward the P60 verdict above.)")
    if not p300_rows:
        print("\n  No settled rows with P300 data yet.")
    else:
        p60_ev = sum(to_float_or_none(r["pnl"]) for r in p300_rows) / len(p300_rows) * 100
        p300_ev = sum(to_float_or_none(r["p300_pnl"]) for r in p300_rows) / len(p300_rows) * 100
        print(f"\n  side-by-side realized edge (n={len(p300_rows)} rows with both policies scored):")
        print(f"    P60  (primary)  : {p60_ev:+.2f} c/window")
        print(f"    P300 (challenger): {p300_ev:+.2f} c/window")
        print(f"    raw difference   : {p300_ev - p60_ev:+.2f} c/window  (NOT day-clustered -- see "
              f"the paired delta below for the decision-grade statistic)")

        p60_days = day_cluster(p300_rows, "pnl")
        p300_days = day_cluster(p300_rows, "p300_pnl")
        all_days = sorted(set(p60_days) | set(p300_days))
        print(f"\n  per-day mean P&L/window, P60 vs P300 ({len(all_days)} day(s)):")
        for day in all_days:
            p60_c = p60_days.get(day)
            p300_c = p300_days.get(day)
            p60_s = f"{p60_c*100:+.2f}c" if p60_c is not None else "n/a"
            p300_s = f"{p300_c*100:+.2f}c" if p300_c is not None else "n/a"
            print(f"    {day}: P60={p60_s:>8}  P300={p300_s:>8}")

        # paired per-box delta (P300 - P60), day-clustered t -- THE decision metric for whether
        # P300 is worth separately pre-registering later (isolates the disposal-policy effect
        # box-by-box instead of comparing two differently-timed/differently-sized raw samples).
        delta_rows = paired_delta_rows(p300_rows)
        ds = day_clustered_stats(delta_rows, "delta")
        dt_ = f"{ds['t']:.2f}" if isinstance(ds.get("t"), float) and not math.isnan(ds["t"]) else "n/a"
        dmean = f"{ds['mean_day']*100:+.2f}c" if isinstance(ds.get("mean_day"), float) \
            and not math.isnan(ds["mean_day"]) else "n/a"
        print(f"\n  PAIRED per-box delta (P300 - P60), day-clustered (the decision metric):")
        print(f"    n_days={ds['n_days']}  mean_delta/day={dmean}  t={dt_}  "
              f"%days_delta_positive={ds.get('pct_positive', float('nan')):.0%}" if ds['n_days']
              else f"    n_days=0  (no paired day yet)")
        print(f"    DP-study prior (pooled, pre-forward): +0.32 to +0.51 c/leg favoring the 300s "
              f"deadline, p=0.015 -- this is the forward check of that finding, not a substitute "
              f"for it; treat any single early day-clustered t here as low-powered until "
              f"n_days grows (same >=14-day discipline as the P60 bar above is the reasonable "
              f"floor before reading this delta as decision-grade either).")


if __name__ == "__main__":
    main()
