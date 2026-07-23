#!/usr/bin/env python3
"""Prototype rigorous RH verification on a low-height segment (Gate Step 3 warm-up).

Certifies sign changes of Hardy's Z(t) using ball arithmetic (python-flint / Arb):
every reported sign is backed by an acb enclosure whose real part excludes 0 and
whose imaginary part contains 0. Grid placement (Gram points, refinement) is
heuristic and does not affect rigor -- only the certified signs do.

Completeness accounting in this prototype compares the certified sign-change
count against round(theta(T)/pi + 1) at a good endpoint. That equals N(T) only
under a bound on S(T); wiring in the full Turing-method certificate (see
docs/TURING_SPEC.md) is the remaining work to upgrade this from prototype to
proof-grade, and is tracked as Step 3 completion criterion.

Usage: python3 rs_verify.py [T] [--check-odlyzko FILE] [--json OUT]
"""

import json
import math
import sys
import time

import mpmath
from flint import acb, arb, ctx, dirichlet_char

# module-level switch: "native" uses FLINT's acb_dirichlet Hardy Z directly;
# "construction" builds Z = exp(i theta) zeta from lgamma+zeta balls. The two
# are independent code paths inside FLINT and agree ball-for-ball; keeping
# both enables cross-validation runs.
Z_IMPL = "native"
_CHI = dirichlet_char(1, 1)


def theta_ball(t, prec):
    """Riemann-Siegel theta(t) as a rigorous arb ball.

    theta(t) = Im lgamma(1/4 + i t/2) - (t/2) log pi
    """
    ctx.prec = prec
    tt = arb(t)
    z = acb(arb(1) / 4, tt / 2)
    return z.lgamma().imag - tt / 2 * arb.pi().log()


def z_ball(t, prec):
    """Hardy Z(t) as an acb ball (implementation per Z_IMPL)."""
    ctx.prec = prec
    if Z_IMPL == "native":
        return _CHI.hardy_z(acb(arb(t)))
    tt = arb(t)
    th = theta_ball(t, prec)
    return acb(0, th).exp() * acb(arb(1) / 2, tt).zeta()


def certified_sign(t, prec=96, max_prec=768):
    """Return (+1|-1, prec_used) for sign of Z(t), certified by a ball
    excluding 0; raises if certification fails up to max_prec (e.g. t is
    indistinguishable from a zero at this precision)."""
    p = prec
    while p <= max_prec:
        z = z_ball(t, p)
        if not (arb(0) in z.imag):
            raise AssertionError(f"Z({t}) imaginary ball excludes 0 -- bug")
        re = z.real
        if arb(0) not in re:
            return (1 if re > 0 else -1), p
        p *= 2
    raise ValueError(f"cannot certify sign of Z({t}) up to {max_prec} bits")


def gram_points(n_max):
    """Heuristic Gram points g_0..g_{n_max} via mpmath (placement need not be
    rigorous)."""
    mpmath.mp.dps = 30
    return [float(mpmath.grampoint(n)) for n in range(n_max + 1)]


def count_sign_changes(points, prec=96, hunt_depth=3, max_hunt_depth=12,
                       expected=None):
    """Certify Z's sign at each grid point and count sign changes.

    Intervals with equal endpoint signs are bisected to `hunt_depth` looking
    for hidden zero pairs. If `expected` is given and the count falls short,
    the hunt escalates (depth +2 each round, capped at max_hunt_depth) on the
    still-empty equal-sign intervals until the count matches or the cap hits.
    Returns (total_changes, brackets, evals, exhausted) where brackets are
    (a, b) intervals each containing an odd number (>= 1) of certified sign
    changes, and exhausted flags a hunt that hit the depth cap while short.
    """
    evals = 0
    signs = {}

    def sgn(t):
        nonlocal evals
        if t not in signs:
            signs[t], _ = certified_sign(t, prec)
            evals += 1
        return signs[t]

    brackets = []

    def count_in(a, b, depth_left):
        """Count sign changes in [a, b]; on sign difference with no budget,
        record one bracket (odd count >= 1)."""
        if sgn(a) != sgn(b):
            if depth_left <= 0 or (b - a) < 1e-4:
                brackets.append((a, b))
                return 1
            m = (a + b) / 2
            return count_in(a, m, depth_left - 1) + count_in(m, b, depth_left - 1)
        if depth_left <= 0:
            return 0
        m = (a + b) / 2
        return count_in(a, m, depth_left - 1) + count_in(m, b, depth_left - 1)

    total = 0
    equal_intervals = []
    for a, b in zip(points, points[1:]):
        if sgn(a) != sgn(b):
            brackets.append((a, b))
            total += 1
        else:
            equal_intervals.append((a, b))

    depth = hunt_depth
    exhausted = False
    while True:
        found_now = []
        for a, b in equal_intervals:
            c = count_in(a, b, depth)
            if c:
                found_now.append(((a, b), c))
                total += c
        equal_intervals = [iv for iv in equal_intervals
                           if iv not in [f[0] for f in found_now]]
        if expected is None or total >= expected:
            break
        if depth >= max_hunt_depth:
            exhausted = True
            break
        depth += 2
    return total, sorted(brackets), evals, exhausted


def is_good_gram(n, g, prec=96):
    """Certified check that g_n is a good Gram point: (-1)^n Z(g_n) > 0."""
    try:
        s, _ = certified_sign(g, prec)
    except ValueError:
        return False
    return (s > 0) == (n % 2 == 0)


def required_blocks(g_p, prec=128):
    """Ball-safe evaluation of T11 Corollary 2.3's block requirement
    N >= 0.0031 log^2(g_p) + 0.11 log(g_p), rounded up from the enclosure's
    upper bound."""
    ctx.prec = prec
    lg = arb(g_p).log()
    rhs = arb("0.0031") * lg * lg + arb("0.11") * lg
    upper = float(rhs.mid() + rhs.rad())
    return max(1, math.ceil(upper - 1e-12))


def turing_certificate(n_end, prec=96, max_blocks=64):
    """Certify N(g_{n_end}) <= n_end + 1 via Lehman--Brent (T11 Thm 2.1 with
    Corollary 2.3 constants; valid since our heights exceed 168*pi).

    Requires g_{n_end} to be a good Gram point (caller ensures). Scans Gram
    blocks upward from n_end until enough consecutive Rosser-conforming
    blocks accumulate. Returns a report dict."""
    mpmath.mp.dps = 30
    g = lambda m: float(mpmath.grampoint(m))

    if g(n_end) <= 168 * math.pi:
        return {"certified": False,
                "reason": "T11 Cor 2.3 constants require t1 > 168*pi"}

    blocks = []
    m = n_end
    g_m = g(m)
    while len(blocks) < max_blocks:
        # find next good Gram point above m
        j = m + 1
        while not is_good_gram(j, g(j), prec):
            j += 1
            if j - m > 50:
                return {"certified": False,
                        "reason": f"no good Gram point in ({m}, {m+50}]"}
        p = j - m  # block length
        # certify exactly p sign changes in (g_m, g_j]
        pts = [g(k) for k in range(m, j + 1)]
        cnt, _, _, _ = count_sign_changes(pts, prec=prec, hunt_depth=3,
                                          max_hunt_depth=12, expected=p)
        if cnt != p:
            return {"certified": False,
                    "reason": f"block ({m},{j}] has {cnt} certified sign "
                              f"changes, expected {p}"}
        blocks.append((m, j))
        m, g_m = j, g(j)
        need = required_blocks(g_m)
        if len(blocks) >= need:
            return {
                "certified": True,
                "statement": f"N(g_{n_end}) <= {n_end + 1}",
                "blocks_used": len(blocks),
                "blocks_required_at_gp": need,
                "g_p_index": m,
                "g_p": g_m,
                "basis": "T11 Thm 2.1 + Cor 2.3 (0.0031 log^2 + 0.11 log)",
            }
    return {"certified": False, "reason": f"exceeded {max_blocks} blocks"}


def main():
    args = sys.argv[1:]
    T = 2000.0
    odlyzko_file = None
    json_out = None
    it = iter(range(len(args)))
    i = 0
    while i < len(args):
        if args[i] == "--check-odlyzko":
            odlyzko_file = args[i + 1]
            i += 2
        elif args[i] == "--json":
            json_out = args[i + 1]
            i += 2
        else:
            T = float(args[i])
            i += 1

    t0 = time.time()
    # choose last Gram index with g_n <= T, then walk down to a good Gram
    # point (the Turing certificate anchors there)
    mpmath.mp.dps = 30
    n_guess = int(mpmath.siegeltheta(T) / mpmath.pi) + 1
    pts = gram_points(n_guess)
    pts = [p for p in pts if p <= T]
    n_end = len(pts) - 1  # pts[i] is Gram point g_i
    while n_end >= 0 and not is_good_gram(n_end, pts[n_end]):
        n_end -= 1
        pts.pop()
    # prepend a start point below the first zero
    grid = [9.0] + pts

    # main-term expectation at the endpoint g_N (a Gram point)
    g_end = grid[-1]
    th = theta_ball(g_end, 128)
    expected = float(th / arb.pi() + 1)

    changes, brackets, evals, exhausted = count_sign_changes(
        grid, expected=round(expected))

    turing = turing_certificate(n_end)
    rh_certified = bool(turing.get("certified")) and changes == n_end + 1
    # zeros below the first grid point: none (first zero at 14.13 > 9)
    report = {
        "T_endpoint": g_end,
        "certified_sign_changes": changes,
        "theta_over_pi_plus_1": expected,
        "count_matches_main_term": changes == round(expected),
        "hunt_exhausted_while_short": exhausted,
        "turing_certificate": turing,
        "rh_certified_to_endpoint": rh_certified,
        "certified_statement": (
            f"all {changes} zeros of zeta with 0 < Im s <= {g_end:.6f} lie "
            f"on the critical line" if rh_certified else "NOT certified"
        ),
        "zeta_evaluations": evals,
        "elapsed_sec": round(time.time() - t0, 2),
        "rigor_note": (
            "signs ball-certified via Arb; completeness via Lehman-Brent / "
            "Trudgian Cor 2.3 (docs/TURING_SPEC.md); Gram-point placement "
            "heuristic (soundness unaffected); prototype-grade pending "
            "independent review"
        ),
    }

    if odlyzko_file:
        with open(odlyzko_file) as f:
            ref = []
            for line in f:
                parts = line.split()
                if parts:
                    ref.append(float(parts[-1]))
                if ref and ref[-1] > g_end:
                    break
        ref = [r for r in ref if r <= g_end]
        matched = 0
        unmatched_refs = []
        bi = 0
        for r in ref:
            while bi < len(brackets) and brackets[bi][1] < r:
                bi += 1
            if bi < len(brackets) and brackets[bi][0] <= r <= brackets[bi][1]:
                matched += 1
                bi += 1
            else:
                unmatched_refs.append(r)
        report["odlyzko_zeros_below_T"] = len(ref)
        report["odlyzko_matched_to_brackets"] = matched
        report["odlyzko_unmatched"] = unmatched_refs[:10]

    print(json.dumps(report, indent=2))
    if json_out:
        with open(json_out, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
