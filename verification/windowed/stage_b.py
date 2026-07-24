#!/usr/bin/env python3
"""Stage B: FFT-based lattice evaluation of the windowed Hardy Z sum (H3 on-ramp).

BALL-RIGOR NOTE (read before using any output of this file for certification):
Only ONE thing here is a rigorous ball end-to-end: the `acb.dft` call itself --
Arb propagates interval error through the transform correctly (per DESIGN.md
(c), confirmed by its own round-trip doctest). Everything else is NOT rigorous:
(1) the main-sum truncation at N_TERMS terms, (2) the Euler-Maclaurin tail
correction, (3) the Gaussian-gridding NUFFT used to turn the nonuniform
frequencies log(n) into a uniform lattice suitable for one `acb.dft` pass
(gridding kernel width/oversampling is tuned empirically here, not bounded by
a proof), and (4) the theta-phase reconstruction of real-valued Z from complex
zeta. None of DESIGN.md's five rigor obligations (main-sum tail bound, Gaussian
window tail bound, aliasing bound, ball-propagation-through-orchestration
composition lemma, Whittaker-Shannon upsampling bound) are discharged here --
this is Stage B exactly as DESIGN.md scopes it: "a fast heuristic oracle...
not itself a certificate," validated the same way as Stage A, by numeric
comparison against rs_verify.z_ball, not by a proven error bound. Stage C is
where a self-contained rigorous radius would have to be derived and wired in.

Method: reuses Stage A's (prototype.py) per-term data (n^-1/2, log n) and its
Euler-Maclaurin windowed-zeta construction unchanged. The one thing Stage B
replaces is Stage A's per-lattice-point O(N_TERMS) phase-sweep loop for the
*main sum* term with a single-shot evaluation of all K lattice points at once:

  main_sum(t) = sum_n n^-1/2 exp(-i*t*log n)  is a sum of complex exponentials
  at NONUNIFORM frequencies s_n = log(n). Evaluating it at a UNIFORM lattice
  of K output points t_k = t0 + u_k is a textbook "type-2 NUFFT" problem
  (nonuniform frequency -> uniform samples), solved via Gaussian-kernel
  gridding (Dutt & Rokhlin 1993 / Greengard-Lee 2004): spread each term onto a
  fine uniform grid over s (an oversampled acb vector of size M), push that
  ONE vector through ONE `acb.dft` call, then divide by the kernel's known
  Fourier transform (deconvolution) to read off all K lattice values at once.
  This is the orchestration DESIGN.md's Stage B section calls for -- built on
  top of `acb.dft` as the DFT engine -- standing in for the paper's exact
  8-step dyadic-block/Taylor-convolution procedure (not reproduced here).
  Cost: O(N_TERMS + M log M), roughly independent of K, vs Stage A's
  O(N_TERMS * K); the win only shows up once K is large enough to amortize
  the gridding/DFT setup (see benchmark output for the actual crossover).

Usage: python3 stage_b.py
"""

import cmath
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from flint import acb, arb, ctx  # noqa: E402
from rs_verify import theta_asym  # noqa: E402
from prototype import (  # noqa: E402
    _BERN, N_TERMS, M_CORR, T0, HALF_WIDTH, precompute_main_sum_data,
    zeta_windowed, z_approx, certified_z,
)

K = 64            # lattice points (validation + benchmark)
PREC_B = 64       # bits for the acb.dft pass (fast path, not full rigor)
OVERSAMPLE = 1.5  # FFT grid size relative to N_TERMS
PTS_PER_STD = 3   # Gaussian gridding kernel resolution


def grid_params(n_terms, h, k, oversample=OVERSAMPLE, ppstd=PTS_PER_STD):
    """One-time (t0-independent) NUFFT grid setup: oversampled DFT size M,
    frequency-grid spacing ds, Gaussian kernel width tau, and a boundary
    margin s0 so the kernel is never truncated at the s=0 edge (log 1 = 0)."""
    s_max = math.log(n_terms - 1)
    du = 2 * h / (k - 1)
    half_supp = int(math.ceil(8 * ppstd))
    m = max(k, int(math.ceil(oversample * n_terms)))
    while True:
        ds = 2 * math.pi / (du * m)
        margin = (half_supp + 2) * ds
        if ds * m >= s_max + 2 * margin:
            break
        m += 2000
    tau = (ppstd * ds) ** 2 / 2
    return dict(M=m, ds=ds, tau=tau, half_supp=half_supp, s0=-margin, du=du)


def euler_maclaurin_tail(t, n_terms, m_corr):
    """The N^(1-s)/(s-1) + tail-correction part of zeta_windowed -- cheap,
    O(m_corr) per point, kept as a per-point loop (only the O(N_TERMS) main
    sum is worth batching)."""
    s = 0.5 + 1j * t
    tot = n_terms ** (1 - s) / (s - 1) + 0.5 * n_terms ** (-s)
    for kk in range(1, m_corr + 1):
        b, fact = _BERN[2 * kk], math.factorial(2 * kk)
        rising = 1 + 0j
        for j in range(2 * kk - 1):
            rising *= (s + j)
        tot += (b / fact) * rising * n_terms ** (-s - 2 * kk + 1)
    return tot


def stage_b_lattice(t0, inv_sqrt_n, log_n, n_terms, m_corr, h, k, grid):
    """Evaluate Z(t) at all k lattice points around t0 via ONE acb.dft pass
    for the main sum, replacing Stage A's per-point O(N_TERMS) loop."""
    m, ds, tau, half_supp, s0, du = (grid["M"], grid["ds"], grid["tau"],
                                      grid["half_supp"], grid["s0"], grid["du"])
    u0 = -h
    g = [0j] * m
    for n in range(1, n_terms):
        sn = log_n[n]
        dn = inv_sqrt_n[n] * cmath.exp(-1j * (t0 + u0) * sn)
        mfrac = (sn - s0) / ds
        m0 = int(round(mfrac))
        for mm in range(max(0, m0 - half_supp), min(m, m0 + half_supp + 1)):
            x = (s0 + mm * ds) - sn
            g[mm] += dn * math.exp(-x * x / (4 * tau))
    ctx.prec = PREC_B
    freq = acb.dft([acb(v.real, v.imag) for v in g])  # the one shared DFT pass
    out = []
    for kk in range(k):
        fk = complex(float(freq[kk].real), float(freq[kk].imag))
        phi_hat = math.sqrt(4 * math.pi * tau) * math.exp(-tau * (kk * du) ** 2)
        main = ds * fk / phi_hat * cmath.exp(-1j * (kk * du) * s0)
        t = t0 + u0 + kk * du
        z = main + euler_maclaurin_tail(t, n_terms, m_corr)
        theta = theta_asym(t)
        out.append((cmath.exp(1j * theta) * z).real)
    return out


def main():
    grid = grid_params(N_TERMS, HALF_WIDTH, K)
    inv_sqrt_n, log_n = precompute_main_sum_data(N_TERMS)
    u0, du = -HALF_WIDTH, 2 * HALF_WIDTH / (K - 1)
    lattice = [T0 + u0 + kk * du for kk in range(K)]

    b_vals = stage_b_lattice(T0, inv_sqrt_n, log_n, N_TERMS, M_CORR,
                              HALF_WIDTH, K, grid)
    devs = [abs(b_vals[i] - certified_z(lattice[i], 128)) for i in range(K)]
    print(f"window t0={T0}, h={HALF_WIDTH}, K={K}, N_TERMS={N_TERMS}, "
          f"NUFFT grid M={grid['M']}")
    print(f"Stage B max |Z_approx - Z_certified|: {max(devs):.3e}  "
          f"mean: {sum(devs)/len(devs):.3e}  PASS(<1e-6): {max(devs) < 1e-6}")

    print("\n=== benchmark: per-point time, N=64 lattice points ===")
    print(f"{'t0':>10} {'StageA ms/pt':>13} {'StageB ms/pt':>13} "
          f"{'native ms/pt':>13} {'A/B speedup':>12} {'native/B':>10}")
    for t0 in (1e4, 1e6, 1e8):
        ta = time.time()
        isn, ln = precompute_main_sum_data(N_TERMS)
        for kk in range(K):
            z_approx(t0 + u0 + kk * du, isn, ln, N_TERMS, M_CORR)
        per_a = (time.time() - ta) / K

        tb = time.time()
        isn, ln = precompute_main_sum_data(N_TERMS)
        stage_b_lattice(t0, isn, ln, N_TERMS, M_CORR, HALF_WIDTH, K, grid)
        per_b = (time.time() - tb) / K

        tn = time.time()
        for kk in range(K):
            certified_z(t0 + u0 + kk * du, 96)
        per_n = (time.time() - tn) / K

        print(f"{t0:10.0e} {per_a*1000:13.4f} {per_b*1000:13.4f} "
              f"{per_n*1000:13.4f} {per_a/per_b:11.2f}x {per_n/per_b:9.2f}x")


if __name__ == "__main__":
    main()
