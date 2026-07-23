#!/usr/bin/env python3
"""Windowed segment-verification benchmark (Step 4 pricing seed data).

A full RH verification run always starts at height 0, but production
verification work is dispatched as windows [T, T+W] at increasing T.
This measures the per-zero cost of certified sign-change scanning in such
a window, at increasing T, so pricing can be seeded from real numbers
instead of guesses.

Reuses rs_verify's certified_sign/count_sign_changes (ball-certified signs;
Gram-point grid placement is heuristic, as there). Only the window's Gram
points are generated locally, by walking forward from a
siegeltheta(T)/pi starting guess -- rs_verify.gram_points(n_max) always
starts counting from n=0, which is wasteful once T needs Gram index in the
billions.

Usage: python3 bench_window.py
"""

import json
import math
import os
import signal
import sys
import time

import mpmath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rs_verify import certified_sign, count_sign_changes, Z_IMPL  # noqa: F401


class _WindowTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise _WindowTimeout()


def _first_gram_at_or_above(T):
    """Smallest Gram index n with grampoint(n) >= T, found by walking from
    a siegeltheta(T)/pi starting guess (grampoint is monotone in n)."""
    mpmath.mp.dps = 30
    g = lambda n: float(mpmath.grampoint(n))
    n = max(0, int(mpmath.siegeltheta(T) / mpmath.pi))
    while g(n) < T:
        n += 1
    while n > 0 and g(n - 1) >= T:
        n -= 1
    return n


def window_gram_points(T, W):
    """Gram points g_n with T <= g_n <= T+W (heuristic placement)."""
    mpmath.mp.dps = 30
    g = lambda n: float(mpmath.grampoint(n))
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
    main-term expectation (theta(T+W)-theta(T))/pi. Hunt escalation (as in
    rs_verify.count_sign_changes) is driven by that same expectation.
    """
    mpmath.mp.dps = 30
    t0 = time.time()
    gpts = window_gram_points(T, W)
    grid = [T] + gpts + [T + W]

    expected = float((mpmath.siegeltheta(T + W) - mpmath.siegeltheta(T)) / mpmath.pi)

    old_handler = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(budget_sec))
    timed_out = False
    try:
        changes, brackets, evals, exhausted = count_sign_changes(
            grid, prec=prec, expected=round(expected))
    except _WindowTimeout:
        changes, evals, exhausted = None, None, True
        timed_out = True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    elapsed = time.time() - t0
    return {
        "T": T,
        "W": W,
        "gram_intervals": len(grid) - 1,
        "expected_zeros": expected,
        "found_zeros": changes,
        "matches_expected": (changes is not None and changes == round(expected)),
        "hunt_exhausted": exhausted,
        "zeta_evaluations": evals,
        "elapsed_sec": round(elapsed, 4),
        "evals_per_zero": (round(evals / changes, 4)
                           if evals and changes else None),
        "sec_per_zero": (round(elapsed / changes, 6) if changes else None),
        "timed_out": timed_out,
        "z_impl": Z_IMPL,
    }


def loglog_fit(reports):
    """Least-squares slope of log10(sec_per_zero) vs log10(T) over reports
    with T >= 1e5 that actually completed."""
    xs, ys = [], []
    for r in reports:
        if r["T"] >= 1e5 and r.get("sec_per_zero"):
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
    budget_exceeded = False

    for T in heights:
        if budget_exceeded:
            reports.append({"T": T, "skipped": True,
                             "reason": "prior height exceeded 300s budget"})
            continue
        r = window_report(T, W, budget_sec=300)
        print(json.dumps(r, indent=2))
        reports.append(r)
        if r.get("timed_out") or r["elapsed_sec"] > 300:
            budget_exceeded = True

    fit = loglog_fit([r for r in reports if not r.get("skipped")])

    print("\nT           gram_ivals  found  expected   evals   sec      evals/zero  sec/zero")
    for r in reports:
        if r.get("skipped"):
            print(f"{r['T']:<11.0e} SKIPPED ({r['reason']})")
            continue
        print(f"{r['T']:<11.0e} {r['gram_intervals']:<11d}"
              f"{r['found_zeros']!s:<7}{r['expected_zeros']:<10.2f}"
              f"{r['zeta_evaluations']!s:<8}{r['elapsed_sec']:<9.4f}"
              f"{r['evals_per_zero']!s:<12}{r['sec_per_zero']!s}")
    print(f"\nlog-log fit (T>=1e5): {fit}")

    out = {"windows": reports, "loglog_fit_sec_per_zero_vs_T": fit}
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "results", "bench_window.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
