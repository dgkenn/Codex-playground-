#!/usr/bin/env python3
"""GRH prototype, Milestone M3 step 1: certified sign scan of the Dirichlet
Hardy Z-function for the real primitive characters mod 3, 5, 7 up to height
T = 200.

This mirrors rs_verify.py's certification discipline (ball arithmetic via
python-flint / Arb: a reported sign is only accepted once an acb enclosure's
real part excludes 0 and its imaginary part contains 0) but applied to
L(s, chi) instead of zeta(s), via ``dirichlet_char(q, i).hardy_z(s)``.

WHY ONLY REAL PRIMITIVE CHARACTERS
-----------------------------------
Arb's hardy_z implements Z(t, chi) = e^{i*theta(t,chi)} * L(1/2+it, chi),
built from L(s,chi)'s own functional equation
    Lambda(s,chi) = eps(chi) * Lambda(1-s, chi-bar),   Lambda = (q/pi)^{(s+a)/2}
                                                         Gamma((s+a)/2) L(s,chi)
Conjugating and comparing at s = 1/2+it shows Lambda(1/2+it,chi) has constant
argument (mod pi) equal to (1/2) arg(eps(chi)) for *every* primitive chi, real
or complex -- so Z(t,chi) is real-valued on the real line regardless. That is
NOT the subtlety.

The actual asymmetry: conjugating the Dirichlet series gives
    conj(L(s, chi)) = L(conj(s), chi-bar),
so a zero rho = beta + i*gamma of L(s,chi) forces a zero of L(s, chi-bar) at
beta - i*gamma -- NOT a zero of L(s,chi) itself. For a REAL character
(chi = chi-bar) this makes L(s,chi)'s own zero set symmetric about the real
axis, exactly like zeta(s), so a one-sided sign scan over 0 < t <= T and the
one-sided counting formula N(T,chi) below are the direct analogue of the
Riemann-Siegel picture. For a COMPLEX chi, L(s,chi)'s zeros are generally
NOT symmetric about the real axis (chi's zeros with gamma>0 mirror chi-bar's
zeros with gamma<0, not chi's own); a naive one-sided sign scan of a single
complex chi would silently miss this asymmetry and any "N(T,chi) counts
zeros of this one L-function symmetrically" reasoning would be unsound. That
is why this prototype restricts to the unique non-principal real primitive
character mod each of q = 3, 5, 7 (the quadratic / Legendre-type character;
verified programmatically below via chi.is_real() and chi.is_primitive()),
sidestepping the issue entirely rather than resolving it.

COMPLETENESS FORMULA (main term only, no rigorous error bound wired in)
------------------------------------------------------------------------
For primitive chi mod q, the one-sided count N(T,chi) = #{rho = beta+i*gamma :
L(rho,chi)=0, 0<beta<1, 0<gamma<=T} obeys the Riemann-von Mangoldt-type
asymptotic

    N(T,chi) ~ (T / 2*pi) * log( q*T / (2*pi*e) )        (+ O(log(qT)))

Source: this is the classical generalization of the Riemann-von Mangoldt
formula to Dirichlet L-functions, derived exactly as for zeta(s) via the
argument principle applied to the completed Lambda(s,chi); see Davenport,
*Multiplicative Number Theory*, 3rd ed. (rev. Montgomery), ch. 16. The
two-sided form N(T,chi) [|gamma|<T] = (T/pi) log(qT/(2 pi e)) - chi(-1)/4 +
O(log(q(T+2))), with fully explicit constants, is given in Bennett, Martin,
O'Bryant & Rechnitzer, "Counting zeros of Dirichlet L-functions," Math.
Comp. 90 (2021) 1455-1482, arXiv:2005.02989; halving it recovers the
one-sided main term used here. This prototype only checks the certified
sign-change count against this asymptotic main term (rounded to the nearest
integer) -- it does NOT wire in the explicit error bound or a Turing-style
completeness certificate (that is future M3 work, analogous to
turing_certificate() in rs_verify.py); a match is reassuring, not a proof
that no zero pair was missed.

GRID / HUNTING
---------------
Grid placement uses a heuristic step (a fraction of the asymptotic average
zero gap 2*pi/log(q*t/(2*pi))); intervals with equal endpoint signs are
bisected (escalating depth if the running total falls short of the
expected count) hunting for missed close zero pairs, exactly as in
rs_verify.count_sign_changes. As there, grid/hunt heuristics affect only
how many zeros get found, never the soundness of a reported sign.

Usage: python3 grh_prototype.py [T] [--json OUT]
"""

import json
import math
import sys
import time

from flint import acb, arb, ctx, dirichlet_char

MODULI = (3, 5, 7)


def find_real_primitive_chars(q):
    """All non-principal primitive real characters mod q (there is exactly
    one for q in {3,5,7}: the quadratic/Legendre-type character), found by
    direct enumeration + is_primitive()/is_real() checks rather than
    hardcoding character indices."""
    out = []
    for i in range(1, q):
        chi = dirichlet_char(q, i)
        if chi.is_primitive() and chi.is_real() and not chi.is_principal():
            out.append(chi)
    return out


def certified_sign(chi, t, prec=96, max_prec=768):
    """Return (+1|-1, prec_used) for the certified sign of Z(t,chi), backed
    by an acb ball whose real part excludes 0 and imaginary part contains 0.
    Raises if certification fails up to max_prec (t indistinguishable from a
    zero at this precision, or chi.hardy_z violates the real-valuedness
    guarantee -- would indicate a bug or a non-primitive/non-real chi)."""
    p = prec
    while p <= max_prec:
        ctx.prec = p
        z = chi.hardy_z(acb(arb(t)))
        if not (arb(0) in z.imag):
            raise AssertionError(
                f"Z(t={t}; chi mod {chi.modulus()}) imaginary ball excludes "
                "0 -- chi may not be real/primitive, or this is a bug")
        re = z.real
        if arb(0) not in re:
            return (1 if re > 0 else -1), p
        p *= 2
    raise ValueError(
        f"cannot certify sign of Z(t={t}; chi mod {chi.modulus()}) up to "
        f"{max_prec} bits")


def local_step(t, q, safety=8.0, min_step=0.02, max_step=0.3):
    """Heuristic grid spacing: a fraction of the asymptotic average zero gap
    2*pi/log(q*t/(2*pi)) (derivative of the N(T,chi) main term below).
    Purely a placement heuristic -- soundness rests only on certified signs
    and the escalating bisection hunt, never on this step size."""
    tt = max(t, 5.0)
    log_arg = max(math.log(q * tt / (2 * math.pi)), 0.3)
    density = log_arg / (2 * math.pi)
    spacing = 1.0 / density
    return min(max(spacing / safety, min_step), max_step)


def build_grid(T, q, start=0.0):
    pts = [start]
    t = start
    while t < T:
        t = min(t + local_step(t, q), T)
        pts.append(t)
    return pts


def count_sign_changes(chi, points, prec=96, hunt_depth=4, max_hunt_depth=20,
                        expected=None):
    """Certify Z(.,chi)'s sign at each grid point and count sign changes,
    escalating a bisection hunt on equal-sign intervals (depth +2 each
    round, capped at max_hunt_depth) when `expected` is given and the
    running total falls short. Returns (total, brackets, evals, exhausted)
    where brackets are (a,b) each certified to contain an odd (>=1) number
    of sign changes, and exhausted flags hitting the depth cap while short."""
    evals = 0
    signs = {}

    def sgn(t):
        nonlocal evals
        if t not in signs:
            signs[t], _ = certified_sign(chi, t, prec)
            evals += 1
        return signs[t]

    brackets = []

    def count_in(a, b, depth_left):
        if sgn(a) != sgn(b):
            if depth_left <= 0 or (b - a) < 1e-6:
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
        found_set = {f[0] for f in found_now}
        equal_intervals = [iv for iv in equal_intervals if iv not in found_set]
        if expected is None or total >= expected:
            break
        if depth >= max_hunt_depth:
            exhausted = True
            break
        depth += 2

    return total, sorted(brackets), evals, exhausted


def expected_N(T, q):
    """Main-term estimate of N(T,chi), the number of zeros of L(s,chi)
    (primitive chi mod q) with 0 < Im(rho) <= T. See module docstring for
    the formula's source (Davenport ch.16; Bennett-Martin-O'Bryant-
    Rechnitzer arXiv:2005.02989 for the explicit-error two-sided version).
    Main term only -- the O(log(qT)) error is dropped."""
    return (T / (2 * math.pi)) * math.log(q * T / (2 * math.pi * math.e))


def scan_modulus(q, T, prec=96):
    chars = find_real_primitive_chars(q)
    if len(chars) != 1:
        raise AssertionError(
            f"expected exactly 1 non-principal real primitive character mod "
            f"{q}, found {len(chars)}")
    chi = chars[0]

    grid = build_grid(T, q, start=0.0)
    exp_N = expected_N(T, q)
    t0 = time.time()
    changes, brackets, evals, exhausted = count_sign_changes(
        chi, grid, prec=prec, expected=round(exp_N))
    elapsed = time.time() - t0

    return {
        "modulus": q,
        "chi_index_l": chi.number(),
        "chi_conductor": chi.conductor(),
        "chi_order": chi.order(),
        "chi_parity": "odd" if chi.parity() else "even",
        "T": T,
        "grid_points": len(grid),
        "zeta_evaluations": evals,
        "certified_sign_changes": changes,
        "expected_N_T_chi": exp_N,
        "expected_N_T_chi_rounded": round(exp_N),
        "difference_certified_minus_expected": changes - exp_N,
        "hunt_exhausted_while_short": exhausted,
        "brackets": brackets,
        "elapsed_sec": round(elapsed, 3),
    }


def main():
    args = sys.argv[1:]
    T = 200.0
    json_out = None
    i = 0
    while i < len(args):
        if args[i] == "--json":
            json_out = args[i + 1]
            i += 2
        else:
            T = float(args[i])
            i += 1

    t0 = time.time()
    results = {}
    for q in MODULI:
        results[str(q)] = scan_modulus(q, T)

    report = {
        "T": T,
        "formula": "N(T,chi) ~ (T/2*pi) * log(q*T/(2*pi*e))  [main term only]",
        "formula_source": (
            "Davenport, Multiplicative Number Theory 3rd ed. ch.16 "
            "(Riemann-von Mangoldt analogue for Dirichlet L-functions); "
            "explicit two-sided error bound in Bennett, Martin, O'Bryant, "
            "Rechnitzer, arXiv:2005.02989 (Math. Comp. 90 (2021) 1455-1482)"
        ),
        "note_complex_chi_asymmetry": (
            "Restricted to the unique non-principal real primitive "
            "character mod each of 3,5,7. hardy_z(t) is real-valued for ANY "
            "primitive chi (real or complex) because Lambda(1/2+it,chi) has "
            "constant argument mod pi -- that is not the issue. The issue: "
            "conj(L(s,chi)) = L(conj s, chi-bar), so zeros of a complex "
            "chi's own L(s,chi) are generally NOT symmetric about the real "
            "t-axis (chi's zeros with gamma>0 mirror chi-bar's zeros with "
            "gamma<0, not chi's own); only for real chi (chi=chi-bar) is "
            "L(s,chi)'s zero set self-symmetric, matching the zeta(s) "
            "picture this one-sided scan and counting formula assume."
        ),
        "per_modulus": results,
        "elapsed_sec_total": round(time.time() - t0, 2),
    }

    print(json.dumps(report, indent=2))
    if json_out:
        with open(json_out, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
