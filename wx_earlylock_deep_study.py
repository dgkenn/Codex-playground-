#!/usr/bin/env python3
"""wx_earlylock_deep_study.py -- reproducible harness for the EARLY-LOCK fleet deep study.

Reads the committed compact dataset (wx_earlylock_deep_data.json, ~1.2MB, sits beside this file) and
reproduces every headline number in wx_earlylock_deep_study.md from scratch: the PRIMARY tail-only EV
grid (settlement-truth-corrected per the verifier panel's binding FATAL finding), the SECONDARY
tail+bracket grid, the day-clustered and Bonferroni-corrected significance checks, and the temporal
stability split that the verifier panel used to kill the "decision-grade positive EV" claim.

This script does NOT touch kwx_runner.py / kwx_paper_gate.py / kalshi_exec.py / kwx_daily_digest.py, does
not place orders, and makes no network calls -- it is pure recomputation over the committed dataset.

Usage:
    python3 wx_earlylock_deep_study.py            # print all tables
    python3 wx_earlylock_deep_study.py --json      # dump every table as JSON (for downstream tooling)
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "wx_earlylock_deep_data.json")

THRESHOLDS = (0.95, 0.97, 0.99)
DELAYS = (0, 5, 15)
CAPS = (93, 95, 95.3, 97)
DELAY_FIELD = {0: "ask0", 5: "ask5", 15: "ask15"}
BASELINE_EV_C = 1.1  # deployed mechanical-lock taker EV yardstick (el_scout.md sec3; not recomputed here)
Z_995 = 2.807  # two-sided z at alpha=0.05/9 (Bonferroni over 9 threshold x delay groups, capped-nested)


def load_data():
    with open(DATA) as f:
        return json.load(f)


def fee_c(price_c):
    p = price_c / 100.0
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt((ph * (1 - ph) + z * z / (4 * n)) / n) / den
    return max(0.0, c - h), min(1.0, c + h)


def cell(rows, th, dl, cap, win_key="win_new"):
    field = DELAY_FIELD[dl]
    el = [r for r in rows if r["th"] == th and r.get(field) is not None and r[field] <= cap and r.get(win_key) is not None]
    n = len(el)
    if n == 0:
        return None
    k = sum(1 for r in el if r[win_key])
    w = k / n
    ma = sum(r[field] for r in el) / n
    f = fee_c(ma)
    lo, hi = wilson(k, n)
    return dict(n=n, wins=k, win=w, ask=ma, fee=f, taker=w * 100 - ma - f, maker=w * 100 - ma,
                lo=lo * 100 - ma - f, hi=hi * 100 - ma - f, rows=el)


def day_clustered_t(rows, dl, taker_ev_of_cell, breakeven_frac=None):
    """Cluster by (station, date); t-test of cluster win-rate means against the cell's own breakeven win
    rate (mean_ask+fee)/100, mirroring aggregate.md's day-clustered t and the verifier's secondary-pool
    check."""
    field = DELAY_FIELD[dl]
    cl = defaultdict(list)
    for r in rows:
        cl[(r["stn"], r["date"])].append(1.0 if r["win_new"] else 0.0)
    means = [sum(v) / len(v) for v in cl.values()]
    n = len(means)
    if n < 2:
        return dict(clusters=n, t=float("nan"))
    mean = sum(means) / n
    var = sum((x - mean) ** 2 for x in means) / (n - 1)
    se = math.sqrt(var / n) if var > 0 else 0.0
    if breakeven_frac is None or se == 0:
        return dict(clusters=n, mean=mean, t=float("nan"))
    t = (mean - breakeven_frac) / se
    return dict(clusters=n, mean=mean, t=t)


def build_primary_grid(tail_rows):
    out = []
    for th in THRESHOLDS:
        for dl in DELAYS:
            for cap in CAPS:
                old = cell(tail_rows, th, dl, cap, win_key="win_old")
                new = cell(tail_rows, th, dl, cap, win_key="win_new")
                if new is None or new["n"] < 5:
                    continue
                out.append(dict(th=th, delay=dl, cap=cap, old=old, new=new))
    return out


def build_secondary_cell(matched_rows, th=0.95, dl=0, cap=93):
    c = cell(matched_rows, th, dl, cap, win_key="win_new")
    be = (c["ask"] + c["fee"]) / 100.0
    dc = day_clustered_t(c["rows"], dl, None, breakeven_frac=be)
    return c, dc, be


def temporal_split(tail_rows, th=0.95, dl=0, cap=97, split_date="2026-06-16"):
    field = DELAY_FIELD[dl]
    el = [r for r in tail_rows if r["th"] == th and r.get(field) is not None and r[field] <= cap and r.get("win_new") is not None]
    early = [r for r in el if r["date"] < split_date]
    late = [r for r in el if r["date"] >= split_date]

    def summarize(sub):
        if not sub:
            return None
        n = len(sub)
        k = sum(1 for r in sub if r["win_new"])
        ma = sum(r[field] for r in sub) / n
        f = fee_c(ma)
        return dict(n=n, wins=k, win=k / n, ask=ma, taker=k / n * 100 - ma - f)

    return dict(early=summarize(early), late=summarize(late), split_date=split_date)


def bonferroni_note(n_effective_cells=27, alpha=0.05):
    """27 = 36 nominal (th x delay x cap) cells minus the 9 cap-95/cap-95.3 duplicate pairs (byte-identical
    since Kalshi asks are integer cents -- 95 and 95.3 always classify the same rows)."""
    # two-sided normal critical value via bisection on the standard normal CDF approx (no scipy dependency)
    from math import erf, sqrt
    target = 1 - alpha / (2 * n_effective_cells)  # two-sided per-test alpha after Bonferroni split

    def phi(x):
        return 0.5 * (1 + erf(x / sqrt(2)))

    lo, hi = 0.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if phi(mid) < target:
            lo = mid
        else:
            hi = mid
    return dict(n_effective_cells=n_effective_cells, alpha=alpha, required_abs_z=round((lo + hi) / 2, 3))


def main():
    as_json = "--json" in sys.argv
    data = load_data()
    events = data["events"]
    meta = data["meta"]
    tail = [r for r in events if r["rt"] == "tail"]
    bracket = [r for r in events if r["rt"] == "bracket"]
    matched = tail + bracket

    report = {}
    report["meta"] = meta
    report["pool_sizes"] = dict(
        signals_total=meta["signals_total"], matched=len(matched), tail=len(tail), bracket=len(bracket),
        tail_by_chunk=dict(Counter(r["chunk"] for r in tail)),
        tail_by_side=dict(Counter(str(r.get("side")) for r in tail)),
    )

    primary = build_primary_grid(tail)
    report["primary_grid"] = [
        dict(th=c["th"], delay=c["delay"], cap=c["cap"], n=c["new"]["n"],
             win_old=round(c["old"]["win"], 4), taker_old=round(c["old"]["taker"], 2),
             win_new=round(c["new"]["win"], 4), taker_new=round(c["new"]["taker"], 2),
             ci_new=[round(c["new"]["lo"], 1), round(c["new"]["hi"], 1)])
        for c in primary
    ]

    headline = cell(tail, 0.95, 0, 97, win_key="win_new")
    headline_old = cell(tail, 0.95, 0, 97, win_key="win_old")
    headline_be = (headline["ask"] + headline["fee"]) / 100.0
    headline_dc = day_clustered_t(headline["rows"], 0, None, breakeven_frac=headline_be)
    report["headline_cell"] = dict(
        th=0.95, delay=0, cap=97, n=headline["n"], wins=headline["wins"],
        win_new=round(headline["win"], 4), win_old=round(headline_old["win"], 4),
        taker_ev_new=round(headline["taker"], 2), taker_ev_old=round(headline_old["taker"], 2),
        ci95_new=[round(headline["lo"], 1), round(headline["hi"], 1)],
        day_clustered_t=round(headline_dc["t"], 2), day_clusters=headline_dc["clusters"],
        vs_deployed_baseline_c=round(headline["taker"] - BASELINE_EV_C, 2),
    )

    best_primary = max(primary, key=lambda c: c["new"]["taker"])
    report["best_primary_cell"] = dict(
        th=best_primary["th"], delay=best_primary["delay"], cap=best_primary["cap"],
        n=best_primary["new"]["n"], win=round(best_primary["new"]["win"], 4),
        taker_ev=round(best_primary["new"]["taker"], 2),
        ci95=[round(best_primary["new"]["lo"], 1), round(best_primary["new"]["hi"], 1)],
    )

    sec_c, sec_dc, sec_be = build_secondary_cell(matched, 0.95, 0, 93)
    report["secondary_best_cell"] = dict(
        th=0.95, delay=0, cap=93, n=sec_c["n"], win=round(sec_c["win"], 4),
        taker_ev=round(sec_c["taker"], 2), ci95=[round(sec_c["lo"], 1), round(sec_c["hi"], 1)],
        breakeven_win=round(sec_be, 4), day_clusters=sec_dc["clusters"], day_clustered_t=round(sec_dc["t"], 2),
        pool="tail+bracket (NOT decision-grade for the intended single-sided-tail bet -- see caveat)",
    )

    report["multiplicity"] = bonferroni_note()

    report["temporal_split_headline_cell"] = temporal_split(tail, 0.95, 0, 97)

    pos_cells = [c for c in primary if c["new"]["taker"] > 0]
    report["positive_point_ev_cells_n_ge5"] = [
        dict(th=c["th"], delay=c["delay"], cap=c["cap"], n=c["new"]["n"], taker_ev=round(c["new"]["taker"], 2))
        for c in pos_cells
    ]

    unfiltered = [r for r in tail if r.get("win_new") is not None]
    report["unfiltered_tail_win_rate"] = dict(
        n=len(unfiltered), wins=sum(1 for r in unfiltered if r["win_new"]),
        by_kind={k: dict(n=len(sub := [r for r in unfiltered if r["kind"] == k]),
                          wins=sum(1 for r in sub if r["win_new"]))
                 for k in ("max", "min")},
    )

    if as_json:
        print(json.dumps(report, indent=2, default=str))
        return

    print("=" * 78)
    print("EARLY-LOCK deep study -- reproduced from wx_earlylock_deep_data.json")
    print("=" * 78)
    m = meta
    print(f"\nEval window {m['eval_window'][0]}..{m['eval_window'][1]} ({m['n_calendar_days']} LST days)")
    print(f"Station-day-kind combos: {m['station_day_kind_combos']}  Signals fired: {m['signals_total']}")
    print(f"Signals by threshold: {m['signals_by_threshold']}")
    print(f"chunk1 Kalshi-settlement-vs-IEM disagreements (the FATAL bug fixed here): "
          f"{m['chunk1_settlement_vs_iem_disagreements']}  ({m['chunk1_settlement_vs_iem_disagreement_direction']})")

    ps = report["pool_sizes"]
    print(f"\nMatched: {ps['matched']}  tail(PRIMARY): {ps['tail']}  bracket(SECONDARY): {ps['bracket']}")
    print(f"tail pool by chunk: {ps['tail_by_chunk']}   by side: {ps['tail_by_side']}")

    print("\n--- PRIMARY tail grid, n>=5 cells: pre-fix (win_old, chunk1=strict-IEM) vs corrected (win_new, settlement-preferred) ---")
    print(f"{'th':>5} {'dl':>3} {'cap':>6} {'n':>4}   {'OLD win':>8} {'OLD EV':>8}   {'NEW win':>8} {'NEW EV':>8}   {'NEW 95%CI':>16}")
    for c in report["primary_grid"]:
        print(f"{c['th']:>5} {c['delay']:>3} {c['cap']:>6} {c['n']:>4}   "
              f"{c['win_old']*100:>7.1f}% {c['taker_old']:>+8.2f}   "
              f"{c['win_new']*100:>7.1f}% {c['taker_new']:>+8.2f}   [{c['ci_new'][0]:+.1f},{c['ci_new'][1]:+.1f}]")

    h = report["headline_cell"]
    print(f"\nHeadline cell th=0.95 delay=+0 cap=97c: n={h['n']} wins={h['wins']}")
    print(f"  win_old(pre-fix)={h['win_old']*100:.1f}%  EV_old={h['taker_ev_old']:+.2f}c")
    print(f"  win_new(corrected)={h['win_new']*100:.1f}%  EV_new={h['taker_ev_new']:+.2f}c  95%CI=[{h['ci95_new'][0]:+.1f},{h['ci95_new'][1]:+.1f}]")
    print(f"  day-clustered t={h['day_clustered_t']:.2f} (dof~{h['day_clusters']-1})  vs deployed baseline (+{BASELINE_EV_C}c): {h['vs_deployed_baseline_c']:+.2f}c")

    b = report["best_primary_cell"]
    print(f"\nBest PRIMARY n>=5 cell by point EV: th={b['th']} delay=+{b['delay']} cap={b['cap']}c "
          f"n={b['n']} win={b['win']*100:.1f}% EV={b['taker_ev']:+.2f}c CI=[{b['ci95'][0]:+.1f},{b['ci95'][1]:+.1f}]")

    s = report["secondary_best_cell"]
    print(f"\nSECONDARY (tail+bracket, NOT decision-grade) best cell th={s['th']} delay=+{s['delay']} cap={s['cap']}c: "
          f"n={s['n']} win={s['win']*100:.1f}% EV={s['taker_ev']:+.2f}c CI=[{s['ci95'][0]:+.1f},{s['ci95'][1]:+.1f}]")
    print(f"  day-clustered ({s['day_clusters']} station-date clusters) t={s['day_clustered_t']:.2f} vs breakeven win {s['breakeven_win']*100:.1f}%")

    bf = report["multiplicity"]
    print(f"\nMultiplicity: {bf['n_effective_cells']} effectively distinct (th x delay x cap) cells "
          f"(95/95.3 caps are byte-identical -- integer-cent asks). Bonferroni alpha={bf['alpha']} requires |z| >= {bf['required_abs_z']}.")
    print(f"  Headline cell |t|={abs(h['day_clustered_t']):.2f}, secondary best |t|={abs(s['day_clustered_t']):.2f} -- both far below the bar.")

    ts = report["temporal_split_headline_cell"]
    e, l = ts["early"], ts["late"]
    print(f"\nTemporal stability of headline cell (split {ts['split_date']}):")
    if e:
        print(f"  {ts['split_date'] and 'early'} (< {ts['split_date']}): n={e['n']} win={e['win']*100:.1f}% ({e['wins']}/{e['n']}) EV={e['taker']:+.2f}c")
    if l:
        print(f"  late (>= {ts['split_date']}): n={l['n']} win={l['win']*100:.1f}% ({l['wins']}/{l['n']}) EV={l['taker']:+.2f}c")

    print(f"\nPositive point-EV PRIMARY cells (n>=5): {len(report['positive_point_ev_cells_n_ge5'])} / {len(primary)}")
    for c in report["positive_point_ev_cells_n_ge5"]:
        print(f"  th={c['th']} delay=+{c['delay']} cap={c['cap']}c n={c['n']} EV={c['taker_ev']:+.2f}c")

    u = report["unfiltered_tail_win_rate"]
    print(f"\nUnfiltered tail win rate (any ask price, sanity check): {u['wins']}/{u['n']} = {u['wins']/u['n']*100:.1f}%")
    for k, v in u["by_kind"].items():
        print(f"  {k}: {v['wins']}/{v['n']} = {v['wins']/v['n']*100 if v['n'] else 0:.1f}%")

    print("\n" + "=" * 78)
    print("VERDICT: settlement-truth correction flips the sign of every PRIMARY n>=5 cell's point")
    print("estimate from negative to near-zero-to-slightly-positive, but NO cell clears Bonferroni")
    print("significance and the headline cell is temporally unstable (see split above). No")
    print("decision-grade positive-EV cell exists in either pool. See wx_earlylock_deep_study.md.")
    print("=" * 78)


if __name__ == "__main__":
    main()
