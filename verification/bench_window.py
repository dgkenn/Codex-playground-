#!/usr/bin/env python3
"""Windowed segment-verification benchmark (Step 4 pricing seed data).

A full RH verification run always starts at height 0, but production
verification work is dispatched as windows [T, T+W] at increasing T.
This measures the per-zero cost of certified sign-change scanning in such
a window, at increasing T, so pricing can be seeded from real numbers
instead of guesses.

Reuses rs_verify's certified_sign/count_sign_changes (ball-certified signs;
Gram-point grid placement is heuristic, as there) and rs_verify.gram_point
(fast asymptotic-Newton Gram point, microseconds per call) for the window's
Gram-point grid -- mpmath.siegeltheta is still used to locate the starting
Gram index and to compute the main-term expectation
(theta(T+W)-theta(T))/pi, but mpmath.grampoint itself is not used since it
gets prohibitively slow once the Gram index needs to reach into the
billions.

Design note (fixed after a T=1e5 failure): a window's boundaries [T, T+W]
are not aligned to anything -- they are not themselves Gram points -- so
the true certified sign-change count in a window can legitimately differ
from the real-valued expectation (theta(T+W)-theta(T))/pi by +-1. Passing
that rounded expectation into count_sign_changes(expected=...) makes the
hunt escalate its bisection depth chasing an unreachable exact match on
every equal-sign interval, blowing the time budget for no benefit. We now
call count_sign_changes with expected=None and a fixed hunt_depth (no
escalation), and instead judge the result against the expectation with a
+-1 boundary tolerance (boundary_consistent).

Usage: python3 bench_window.py
"""

import json
import math
import os
import sys
import time

import mpmath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rs_verify import certified_sign, count_sign_changes, gram_point, Z_IMPL  # noqa: F401

HUNT_DEPTH = 4  # fixed, no escalation -- see module docstring


def _first_gram_at_or_above(T):
    """Smallest Gram index n with gram_point(n) >= T, found by walking from
    a siegeltheta(T)/pi starting guess (gram_point is monotone in n).
    Uses rs_verify's fast asymptotic-Newton gram_point, not mpmath.grampoint."""
    mpmath.mp.dps = 30
    g = gram_point
    n = max(0, int(mpmath.siegeltheta(T) / mpmath.pi))
    while g(n) < T:
        n += 1
    while n > 0 and g(n - 1) >= T:
        n -= 1
    return n


def window_gram_points(T, W):
    """Gram points g_n with T <= g_n <= T+W (heuristic placement, fast
    gram_point from rs_verify)."""
    g = gram_point
    n = _first_gram_at_or_above(T)
    pts = []
    while True:
        gv = g(n)
        if gv > T + W:
            break
        pts.append(gv)
        n += 1
    return pts


def window_report(T, W, prec=96, budget_sec=300):
    """Certify sign changes of Z across [T, T+W]; return timing/cost stats.

    Grid = [T] + (Gram points strictly inside the window) + [T+W], so the
    certified count covers the exact window, comparable to the real-valued
    main-term expectation (theta(T+W)-theta(T))/pi -- but not required to
    match it exactly, since T and T+W are not themselves Gram points (see
    module docstring). count_sign_changes is called per Gram interval with
    expected=None and a fixed hunt_depth (no escalation); wall time is
    checked between intervals so a height that runs long aborts cleanly
    with partial data instead of blowing the budget mid-hunt.
    """
    mpmath.mp.dps = 30
    t0 = time.time()
    gpts = window_gram_points(T, W)
    grid = [T] + gpts + [T + W]

    expected = float((mpmath.siegeltheta(T + W) - mpmath.siegeltheta(T)) / mpmath.pi)

    total_changes = 0
    total_evals = 0
    all_brackets = []
    intervals_total = len(grid) - 1
    intervals_done = 0
    aborted = False

    for a, b in zip(grid, grid[1:]):
        if time.time() - t0 > budget_sec:
            aborted = True
            break
        changes, brackets, evals, _exhausted = count_sign_changes(
            [a, b], prec=prec, hunt_depth=HUNT_DEPTH, expected=None)
        total_changes += changes
        total_evals += evals
        all_brackets.extend(brackets)
        intervals_done += 1

    elapsed = time.time() - t0

    lo = math.floor(expected) - 1
    hi = math.ceil(expected) + 1
    boundary_consistent = (not aborted) and (lo <= total_changes <= hi)

    return {
        "T": T,
        "W": W,
        "gram_intervals": intervals_total,
        "gram_intervals_completed": intervals_done,
        "expected_zeros": expected,
        "found_zeros": total_changes,
        "boundary_consistent": boundary_consistent,
        "zeta_evaluations": total_evals,
        "elapsed_sec": round(elapsed, 4),
        "evals_per_zero": (round(total_evals / total_changes, 4)
                           if total_evals and total_changes else None),
        "sec_per_zero": (round(elapsed / total_changes, 6)
                         if total_changes and not aborted else None),
        "aborted": aborted,
        "z_impl": Z_IMPL,
    }


def loglog_fit(reports):
    """Least-squares slope of log10(sec_per_zero) vs log10(T) over reports
    with T >= 1e5 that actually completed (not aborted, sec_per_zero set)."""
    xs, ys = [], []
    for r in reports:
        if r["T"] >= 1e5 and not r.get("aborted") and r.get("sec_per_zero"):
            xs.append(math.log10(r["T"]))
            ys.append(math.log10(r["sec_per_zero"]))
    if len(xs) < 2:
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    slope = num / den if den else float("nan")
    intercept = my - slope * mx
    return {"exponent": round(slope, 4), "log10_intercept": round(intercept, 4),
            "n_points": n}


def main():
    heights = [1e4, 1e5, 1e6, 1e7, 1e8, 1e9]
    W = 200.0
    reports = []

    for T in heights:
        r = window_report(T, W, budget_sec=300)
        print(json.dumps(r, indent=2))
        reports.append(r)

    fit = loglog_fit(reports)

    print("\nT           gram_ivals  found  expected   bnd_ok  evals   sec      evals/zero  sec/zero")
    for r in reports:
        print(f"{r['T']:<11.0e} {r['gram_intervals']:<11d}"
              f"{r['found_zeros']!s:<7}{r['expected_zeros']:<10.2f}"
              f"{str(r['boundary_consistent']):<7}"
              f"{r['zeta_evaluations']!s:<8}{r['elapsed_sec']:<9.4f}"
              f"{r['evals_per_zero']!s:<12}{r['sec_per_zero']!s}"
              f"{'  ABORTED' if r['aborted'] else ''}")
    print(f"\nlog-log fit (T>=1e5, completed heights): {fit}")

    out = {"windows": reports, "loglog_fit_sec_per_zero_vs_T": fit}
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "results", "bench_window.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
