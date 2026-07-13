#!/usr/bin/env python3
"""box_shadow_report.py -- risk-benchmark aggregator for box_shadow.py's forward-arm output.
stdlib + numpy ONLY (collector env; same constraint as box_shadow.py, matched deliberately so this
can run in the same daily cycle that runs box_shadow.py itself).

Reads the ACCUMULATED, day-partitioned gha_data/<day>/box_shadow_<asset>15m.jsonl rows written by
box_shadow.py and prints a per-arm risk-benchmark table. Per the operator's explicit requirement,
risk metrics are FIRST-CLASS here, not an afterthought bolted onto an EV number -- this is what the
daily cycle runs to fill FORWARD_LEDGER.md.

Per-arm metrics (all computed on the FULL population of settled windows the arm was scored on,
INCLUDING vetoed windows at locked=0.0 -- this is deliberate: box_shadow.py always writes one row
per (ws,asset,arm) even when an arm's entry veto fires, so a veto arm's EV already nets out its own
opportunity cost of skipped volume. This is NOT the "kept-only" convention some of the underlying
layer studies use; it is the correct like-for-like comparison against the always-participates
'live' arm):
  n_days, n_windows       -- population size
  EV/window (c)           -- mean(locked)*100, full population
  strand_rate             -- mean(stranded)
  pnl_var (c^2)           -- event-level variance of locked*100 (ddof=1)
  CVaR5(event) (c)        -- mean of the worst 5% of individual-window locked*100 outcomes
                             (tail/expected-shortfall risk, NOT a day-level number)
  worst_window (c)        -- min single-window locked*100
  day_sharpe              -- mean(day_ev_series) / stdev(day_ev_series), where day_ev_series[day] =
                             mean(locked*100) over that day's windows for the arm (the SAME
                             day-clustering convention the layer0/1/2 studies use for their t-stats,
                             just repurposed as a Sharpe-style ratio here)
  worst_day (c)           -- min(day_ev_series)
  max_drawdown (c)        -- largest peak-to-trough decline of cumsum(day_ev_series) in day order
                             (a day-level, not per-window, risk measure)
  d_EV vs live (c), t      -- day-clustered mean/t of (arm.locked - live.locked) on windows where
                             BOTH the arm and 'live' have a row for the same (day,ws) -- i.e. the
                             live-comparable forward edge, day-clustered exactly like the layer
                             studies' day_stats()
  d_strand vs live (pp), t -- same day-clustering, on (arm.stranded - live.stranded)*100
  mean_give (c)            -- mean(dispose_give) over rows where it is not None (bonus: not in the
                             mandatory spec but cheap and directly useful for L3 give-cap comparisons)

Usage: python box_shadow_report.py [--data-dir gha_data] [--asset btc] [--days D1 D2 ...]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics

import numpy as np

try:
    import avseq   # always-valid confidence sequence for early-promotion (Factory V2)
except Exception:
    avseq = None


def load_rows(data_dir, asset, days=None):
    """Load all box_shadow_<asset>15m.jsonl rows from day-partitioned subdirectories of data_dir.
    Only directories named YYYY-MM-DD are treated as day partitions (matches box_shadow.py's own
    --day output convention); a flat/live-mode data_dir (no day subdirs) yields zero rows here by
    design -- this report is for the ACCUMULATED archive, not a single live cycle's flat output."""
    rows = []
    day_dirs = sorted(glob.glob(os.path.join(data_dir, "*")))
    for day_dir in day_dirs:
        if not os.path.isdir(day_dir):
            continue
        day = os.path.basename(day_dir)
        if not (len(day) == 10 and day[4] == "-" and day[7] == "-"):
            continue
        if days and day not in days:
            continue
        fp = os.path.join(day_dir, f"box_shadow_{asset}15m.jsonl")
        if not os.path.isfile(fp):
            continue
        with open(fp) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                d["day"] = day
                rows.append(d)
    return rows


def day_cluster_stats(day_values):
    """day_values: dict day -> list of per-window values. Returns (mean, se, t, n_days) of the
    across-day distribution of per-day means -- identical convention to the layer0/1/2 studies'
    day_stats(): cluster first (protects against within-day autocorrelation), then t-test the
    day-level means against zero."""
    day_means = [statistics.mean(v) for v in day_values.values() if v]
    n = len(day_means)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    m = statistics.mean(day_means)
    if n > 1:
        se = statistics.stdev(day_means) / math.sqrt(n)
        t = m / se if se > 0 else float("nan")
    else:
        se, t = float("nan"), float("nan")
    return m, se, t, n


def cvar5(vals):
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = max(1, int(math.ceil(0.05 * len(s))))
    return statistics.mean(s[:k])


def max_drawdown(series):
    """series: list of per-day values in day order. Drawdown is measured on the CUMULATIVE SUM
    (as if each day's mean-per-window EV were that day's realized total) -- a day-level risk
    measure, documented explicitly since it is a judgment call (box_shadow.py's rows carry
    per-window, not per-day-total, P&L; see module docstring)."""
    if not series:
        return float("nan")
    cum = np.cumsum(np.asarray(series, dtype=float))
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    return float(dd.max())


def build_arm_stats(rows_by_arm, days_sorted):
    stats = {}
    for arm, rows in rows_by_arm.items():
        locked_c = [r["locked"] * 100.0 for r in rows]
        stranded = [1.0 if r.get("stranded") else 0.0 for r in rows]
        gives = [r["dispose_give"] * 100.0 for r in rows if r.get("dispose_give") is not None]

        day_locked = {}
        for r in rows:
            day_locked.setdefault(r["day"], []).append(r["locked"] * 100.0)
        day_ev_series = [statistics.mean(day_locked[d]) for d in days_sorted if d in day_locked]

        n = len(rows)
        ev = statistics.mean(locked_c) if locked_c else float("nan")
        strand_rate = statistics.mean(stranded) if stranded else float("nan")
        pnl_var = statistics.variance(locked_c) if len(locked_c) > 1 else float("nan")
        worst_window = min(locked_c) if locked_c else float("nan")
        if len(day_ev_series) > 1:
            d_mean = statistics.mean(day_ev_series)
            d_sd = statistics.stdev(day_ev_series)
            sharpe = d_mean / d_sd if d_sd > 0 else float("nan")
        else:
            sharpe = float("nan")
        worst_day = min(day_ev_series) if day_ev_series else float("nan")
        mdd = max_drawdown(day_ev_series)
        mean_give = statistics.mean(gives) if gives else float("nan")

        stats[arm] = dict(n_days=len(day_locked), n_windows=n, ev=ev, strand_rate=strand_rate,
                           pnl_var=pnl_var, cvar5=cvar5(locked_c), worst_window=worst_window,
                           day_sharpe=sharpe, worst_day=worst_day, max_drawdown=mdd,
                           mean_give=mean_give)
    return stats


def build_vs_live(rows_by_arm, live_by_key):
    """live_by_key: dict (day,ws) -> live row. Returns per-arm day-clustered delta stats vs live."""
    out = {}
    for arm, rows in rows_by_arm.items():
        ev_by_day = {}
        strand_by_day = {}
        for r in rows:
            key = (r["day"], r["ws"])
            lv = live_by_key.get(key)
            if lv is None:
                continue
            ev_by_day.setdefault(r["day"], []).append(r["locked"] * 100.0 - lv["locked"] * 100.0)
            strand_by_day.setdefault(r["day"], []).append(
                (1.0 if r.get("stranded") else 0.0) - (1.0 if lv.get("stranded") else 0.0))
        ev_m, ev_se, ev_t, ev_nd = day_cluster_stats(ev_by_day)
        st_m, st_se, st_t, st_nd = day_cluster_stats(strand_by_day)
        # ALWAYS-VALID early-promotion (avseq): the per-day EV-delta means, in day order, fed to a
        # time-uniform confidence sequence. av_promote=True <=> the lower CS bound cleared 0 with
        # Type-I error controlled across ALL daily peeks (NOT the invalid "first day t>2"). This is
        # reported ALONGSIDE the standard fixed-horizon gate (t>=2 over >=10 days), never replacing
        # it -- and for a stack-strength effect it typically fires LATER than day 10, so the fixed
        # gate remains the primary path; av only shortcuts a dramatically-stronger-than-replay edge.
        av_promote, av_lb = False, float("nan")
        if avseq is not None and ev_by_day:
            daily = [statistics.mean(ev_by_day[d]) for d in sorted(ev_by_day) if ev_by_day[d]]
            dec = avseq.promote_decision(daily)
            av_promote, av_lb = dec["promote"], dec["lb"]
        out[arm] = dict(d_ev=ev_m, d_ev_t=ev_t, d_strand_pp=st_m * 1.0, d_strand_t=st_t, nd=ev_nd,
                        av_promote=av_promote, av_lb=av_lb)
    return out


def fmt(x, w, p=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a".rjust(w)
    return f"{x:.{p}f}".rjust(w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="gha_data")
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--days", nargs="+", default=None, help="restrict to these YYYY-MM-DD day dirs")
    args = ap.parse_args()

    rows = load_rows(args.data_dir, args.asset, days=set(args.days) if args.days else None)
    if not rows:
        print(f"[box_shadow_report] no rows found under {args.data_dir!r} for asset={args.asset!r}")
        return

    days_sorted = sorted(set(r["day"] for r in rows))
    arms = sorted(set(r["arm"] for r in rows))
    rows_by_arm = {}
    for r in rows:
        rows_by_arm.setdefault(r["arm"], []).append(r)

    live_by_key = {(r["day"], r["ws"]): r for r in rows_by_arm.get("live", [])}

    stats = build_arm_stats(rows_by_arm, days_sorted)
    vs_live = build_vs_live(rows_by_arm, live_by_key)

    print(f"[box_shadow_report] asset={args.asset} data_dir={args.data_dir} "
          f"days={days_sorted[0]}..{days_sorted[-1]} (n={len(days_sorted)}) arms={arms}")
    print()
    hdr = (f"{'arm':<14}{'n_days':>7}{'n_win':>7}{'EV/win(c)':>11}{'strand%':>9}"
           f"{'pnl_var':>10}{'CVaR5(c)':>10}{'worst_win(c)':>13}{'day_sharpe':>11}"
           f"{'worst_day(c)':>13}{'max_dd(c)':>11}{'give(c)':>9}"
           f"{'dEV~live(c)':>13}{'dEV_t':>8}{'dStrand(pp)':>12}{'dStr_t':>8}")
    print(hdr)
    print("-" * len(hdr))
    for arm in arms:
        s = stats[arm]
        v = vs_live.get(arm, {})
        line = (f"{arm:<14}{s['n_days']:>7d}{s['n_windows']:>7d}"
                f"{fmt(s['ev'], 11)}{fmt(s['strand_rate']*100, 9, 2)}"
                f"{fmt(s['pnl_var'], 10, 1)}{fmt(s['cvar5'], 10)}{fmt(s['worst_window'], 13)}"
                f"{fmt(s['day_sharpe'], 11, 3)}{fmt(s['worst_day'], 13)}{fmt(s['max_drawdown'], 11)}"
                f"{fmt(s['mean_give'], 9, 2)}"
                f"{fmt(v.get('d_ev'), 13)}{fmt(v.get('d_ev_t'), 8, 2)}"
                f"{fmt(v.get('d_strand_pp'), 12, 2)}{fmt(v.get('d_strand_t'), 8, 2)}")
        print(line)
    print()
    print("day-clustered deltas are vs the 'live' arm, matched by (day,ws); n_days for the delta "
          "columns = number of days with >=1 matched window (see 'nd' if needed -- printed below).")
    for arm in arms:
        v = vs_live.get(arm, {})
        print(f"  {arm:<14} nd={v.get('nd')}")
    # ALWAYS-VALID early-promotion flags (avseq): eligible arms have cleared the time-uniform
    # lower confidence bound above 0 -- promotable NOW under alpha control even before the 10-day
    # fixed gate. Absent any flag, keep waiting for the standard gate. See avseq.py for the method.
    print()
    if avseq is None:
        print("early-promotion (always-valid): avseq module unavailable -> skipped")
    else:
        flagged = [a for a in arms if vs_live.get(a, {}).get("av_promote")]
        print(f"early-promotion (always-valid, alpha=0.05, min_days={avseq.MIN_DAYS}): "
              f"{'ELIGIBLE -> ' + ', '.join(flagged) if flagged else 'none yet (keep to the 10-day fixed gate)'}")
        for arm in arms:
            v = vs_live.get(arm, {})
            if v.get("av_promote"):
                print(f"  {arm:<14} always-valid LB(dEV)={fmt(v.get('av_lb'), 8, 3)}c > 0 "
                      f"-> forward edge real under time-uniform control; prepare deploy proposal")


if __name__ == "__main__":
    main()
