#!/usr/bin/env python3
"""Stage A prototype for windowed multi-evaluation of Hardy's Z (H3 on-ramp).

NOT RIGOROUS: a fast float approximation of Z(t), not a ball computation --
no error bounds are carried through the arithmetic below, and it must never
replace rs_verify.certified_sign in any certification path. Its only job is
to demonstrate the core idea behind Platt-Trudgian-style multi-evaluation
(windowed sums amortized across many nearby t) and have that idea
*validated numerically* against rs_verify's certified z_ball values -- that
comparison, not any claim about this script's own error, is what makes it
trustworthy for planning. See verification/windowed/DESIGN.md for how this
differs from a rigorous Stage B/C implementation.

Method: Z(t) = Re[ exp(i*theta(t)) * zeta(1/2+it) ], zeta via
Euler-Maclaurin summation:
    zeta(s) = sum_{n=1}^{N-1} n^-s + N^(1-s)/(s-1) + N^-s/2
              + sum_{k=1}^{M} B_2k/(2k)! * (s)_(2k-1) * N^(-s-2k+1)

Amortization: n^-1/2 and log(n) for n=1..N-1 are the main sum's "per-term
data" -- computed ONCE, shared by every lattice point t in the window.
Each point then only pays for N complex phases (exp(-i*t*log n)) plus O(M)
tail terms, skipping the pow()/log() setup. A real pipeline (Stage B)
replaces that per-point O(N) phase sweep with one O(N log N) FFT for the
*entire* lattice; Stage A stops short of that (see DESIGN.md).

theta(t) uses rs_verify.theta_asym (asymptotic, already ~1e-15 accurate
at t~1e4). Usage: python3 prototype.py
"""

import cmath
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from flint import acb, arb, ctx, dirichlet_char  # noqa: E402
from rs_verify import theta_asym  # noqa: E402

_CHI = dirichlet_char(1, 1)

# Bernoulli numbers B_2k used in the Euler-Maclaurin tail correction.
_BERN = {2: 1 / 6, 4: -1 / 30, 6: 1 / 42, 8: -1 / 30, 10: 5 / 66, 12: -691 / 2730}

T0 = 10000.0       # window center
HALF_WIDTH = 2.0   # window is [T0 - HALF_WIDTH, T0 + HALF_WIDTH]
N_TERMS = 5000     # main-sum truncation (per-term data computed once)
M_CORR = 6         # number of Euler-Maclaurin correction terms
LATTICE_POINTS = 50
CERT_PREC = 128    # bits for the rs_verify reference (certified) ball


def precompute_main_sum_data(n_terms):
    """Compute per-term amplitude/log data ONCE, shared across the window."""
    inv_sqrt_n = [0.0] * n_terms
    log_n = [0.0] * n_terms
    for n in range(1, n_terms):
        inv_sqrt_n[n] = n ** -0.5
        log_n[n] = math.log(n)
    return inv_sqrt_n, log_n


def zeta_windowed(t, inv_sqrt_n, log_n, n_terms, m_corr):
    """Euler-Maclaurin zeta(1/2+it), reusing precomputed per-term data."""
    s = 0.5 + 1j * t
    total = 0j
    for n in range(1, n_terms):
        total += inv_sqrt_n[n] * cmath.exp(-1j * t * log_n[n])
    total += n_terms ** (1 - s) / (s - 1)
    total += 0.5 * n_terms ** (-s)
    for k in range(1, m_corr + 1):
        b = _BERN[2 * k]
        fact = math.factorial(2 * k)
        rising = 1 + 0j
        for j in range(2 * k - 1):
            rising *= (s + j)
        total += (b / fact) * rising * n_terms ** (-s - 2 * k + 1)
    return total


def z_approx(t, inv_sqrt_n, log_n, n_terms, m_corr):
    """Fast, non-rigorous Z(t) approximation (see module docstring)."""
    z = zeta_windowed(t, inv_sqrt_n, log_n, n_terms, m_corr)
    theta = theta_asym(t)
    return (cmath.exp(1j * theta) * z).real


def certified_z(t, prec):
    """Reference value from rs_verify's rigorous ball computation (midpoint
    only -- we discard the ball radius here since this script only checks
    numeric agreement, not rigor)."""
    ctx.prec = prec
    return float(_CHI.hardy_z(acb(arb(t))).real)


def main():
    t_start = time.time()
    inv_sqrt_n, log_n = precompute_main_sum_data(N_TERMS)
    setup_time = time.time() - t_start

    lattice = [T0 - HALF_WIDTH + 2 * HALF_WIDTH * i / (LATTICE_POINTS - 1)
               for i in range(LATTICE_POINTS)]

    t_eval = time.time()
    deviations = []
    for t in lattice:
        approx = z_approx(t, inv_sqrt_n, log_n, N_TERMS, M_CORR)
        exact = certified_z(t, CERT_PREC)
        deviations.append(abs(approx - exact))
    eval_time = time.time() - t_eval

    max_dev = max(deviations)
    mean_dev = sum(deviations) / len(deviations)

    print(f"window center t0={T0}, half-width={HALF_WIDTH}, "
          f"lattice points={LATTICE_POINTS}")
    print(f"main-sum terms N={N_TERMS}, correction terms M={M_CORR}, "
          f"cert prec={CERT_PREC} bits")
    print(f"per-term data setup time: {setup_time:.4f}s (once, shared "
          f"across all lattice points)")
    print(f"lattice evaluation + certified comparison time: "
          f"{eval_time:.4f}s ({eval_time / LATTICE_POINTS * 1000:.3f} "
          f"ms/point)")
    print(f"max |Z_approx - Z_certified| over window: {max_dev:.3e}")
    print(f"mean |Z_approx - Z_certified| over window: {mean_dev:.3e}")
    print(f"PASS (<1e-6): {max_dev < 1e-6}")


if __name__ == "__main__":
    main()
