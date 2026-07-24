#!/usr/bin/env python3
"""M5 factory, first run: re-derive Trudgian T11 (arXiv:0903.1885) Theorem 2.2
from its own proof (Lemmas 2.4-2.11 -> Theorem 2.12, section 2.2-2.3) and
search the free parameters (c, d) for slack beyond the author's 2009 hand
grid, at heights relevant to this project.

STATUS: this is the "candidate search" stage of M5's loop only (see
docs/M5_FACTORY.md sec 2) -- floating-point mpmath, not Arb ball arithmetic.
A winning candidate must still be re-verified in ball arithmetic (rigor
requires that pass; a float optimum is a lead, not a certificate) before it
can replace anything in rs_verify.py or formal/LehmanBrent.lean.

Equations transcribed directly from the fetched PDF (arXiv:0903.1885v3,
pages 9-10, section 2.2-2.3):

  pi*a = d^2*log(4)*{ -zeta'(1/2+d)/zeta(1/2+d) - (1/2)log(2*pi) + 1/4 }
         + (d^2/2)*log(pi)
         - (1/2) * I(1+2d, inf)
         +         I(1/2+d, inf)
         - (1/2) * I(1+2d, 1+4d)
         +         I(1/2+d, 1/2+2d)
         + (1/2)(c-1/2)*log(K*zeta(c))
         +         I(c, inf)
         + mu                                                    (2.15)

  2*pi*b = theta*(c - 1/2) + d^2*(log(4) - 1)                    (2.16)

where I(x,y) = integral_x^y log(zeta(sigma)) dsigma, mu = 3e-6.

CALIBRATION NOTE: the (c-1/2)log(K zeta(c)) term in the fetched image of
(2.15) renders without a visible (1/2) prefactor. Implementing it literally
as printed reproduces b exactly but overshoots a by a roughly-constant
offset at both of Trudgian's own worked instantiations (section 2.3: (c,d)
= (5/4,1) and (11/10,3/4)). Restoring the (1/2) prefactor -- which matches
Lemma 2.8's a1 = ... + (1/2)(c-1/2)log{K zeta(c)} + delta, the piece this
term descends from -- reproduces both published (a,b) pairs to 4 significant
figures (see the validation block below). This is exactly the kind of
transcription risk M5's review gate exists to catch; flagged here rather
than silently fixed.

Because (2.15)/(2.16) contain no cross terms in (c,d), Trudgian's own
section 2.3 notes F(c,d) = Fc(c) + Fd(d) separates additively -- so each
parameter is optimized independently (two 1D scans) rather than over a 2D
grid, which is both faster and mirrors the paper's own approach exactly.
"""
import math

import mpmath as mp

mp.mp.dps = 30
MU = mp.mpf("3e-6")


def logzeta_integral(x, y):
    """integral_x^y log(zeta(sigma)) dsigma for real sigma > 1/2 (all call
    sites here use x > 1/2, where zeta is real and positive). Converges
    quickly for y = inf since zeta(sigma) -> 1 there."""
    f = lambda s: mp.log(mp.zeta(s))
    if y == mp.inf:
        return mp.quad(f, [x, x + 5, x + 20, mp.inf])
    return mp.quad(f, [x, y])


def Fc(c, theta, K, L):
    """The c-only piece of F(c,d) = a(c,d) + b(c,d)*L, L = log(gp/2pi)."""
    c = mp.mpf(c)
    a_part = (mp.mpf("0.5") * (c - mp.mpf("0.5")) * mp.log(K * mp.zeta(c))
              + logzeta_integral(c, mp.inf)) / mp.pi
    b_part = theta * (c - mp.mpf("0.5")) / (2 * mp.pi)
    return a_part + b_part * L, a_part, b_part


def Fd(d, L):
    """The d-only piece of F(c,d) = a(c,d) + b(c,d)*L."""
    d = mp.mpf(d)
    d2 = d * d
    zp_over_z = mp.zeta(mp.mpf("0.5") + d, derivative=1) / mp.zeta(mp.mpf("0.5") + d)
    term1 = d2 * mp.log(4) * (-zp_over_z - mp.mpf("0.5") * mp.log(2 * mp.pi) + mp.mpf("0.25"))
    term2 = d2 / 2 * mp.log(mp.pi)
    I1 = -mp.mpf("0.5") * logzeta_integral(1 + 2 * d, mp.inf)
    I2 = logzeta_integral(mp.mpf("0.5") + d, mp.inf)
    I3 = -mp.mpf("0.5") * logzeta_integral(1 + 2 * d, 1 + 4 * d)
    I4 = logzeta_integral(mp.mpf("0.5") + d, mp.mpf("0.5") + 2 * d)
    a_part = (term1 + term2 + I1 + I2 + I3 + I4 + MU) / mp.pi
    b_part = d2 * (mp.log(4) - 1) / (2 * mp.pi)
    return a_part + b_part * L, a_part, b_part


def optimize_1d(func, lo, hi, n, *extra):
    best = None
    for i in range(n + 1):
        x = lo + (hi - lo) * i / n
        val, a_part, b_part = func(x, *extra)
        val = float(val)
        if best is None or val < best[0]:
            best = (val, x, float(a_part), float(b_part))
    return best


def full_search(theta, K, gp, n=100):
    """Independently optimize c over (1, 5/4] and d over (1/2, 1] to
    minimize F(c,d) = a + b*log(gp/2pi), the quantity Theorem 2.1's block
    count is built from at Gram point gp."""
    L = mp.log(gp / (2 * mp.pi))
    bc = optimize_1d(Fc, 1.0005, 1.25, n, theta, K, L)
    bd = optimize_1d(Fd, 0.5005, 1.0, n, L)
    return bc[0] + bd[0], bc[1], bd[1], bc[2] + bd[2], bc[3] + bd[3]


def blocks_needed(a, b, gp):
    """Corollary-2.3-shaped block count N >= (b/6pi) log^2(gp) +
    ((a - b log 2pi)/6pi) log(gp), from T11 Theorem 2.1."""
    lg = float(mp.log(gp))
    return b / (6 * math.pi) * lg ** 2 + (a - b * math.log(2 * math.pi)) / (6 * math.pi) * lg


if __name__ == "__main__":
    theta, K = mp.mpf("0.25"), mp.mpf("2.53")  # Trudgian's own growth-bound pair

    print("=== Validation: reproduce Trudgian's own instantiations (sec 2.3) ===")
    L0 = mp.mpf(0)
    for (c, d, ref_a, ref_b) in [(1.25, 1.0, 1.61, 0.0914), (1.1, 0.75, 2.0666, 0.0585)]:
        _, ac, bc_ = Fc(c, theta, K, L0)
        _, ad, bd_ = Fd(d, L0)
        a, b = ac + ad, bc_ + bd_
        print(f"c={c:<6} d={d:<6} a={float(a):.4f} (paper {ref_a})  "
              f"b={float(b):.4f} (paper {ref_b})")

    print("\n=== Legacy height gp = 2*pi*1e12 (Trudgian's own target, Cor 2.3) ===")
    gp_legacy = 2 * mp.pi * mp.mpf("1e12")
    f, c, d, a, b = full_search(theta, K, gp_legacy)
    print(f"factory optimum: F={f:.6f} at c={c:.4f} d={d:.4f}  a={a:.4f} b={b:.4f}")
    print("Trudgian's 2009 hand grid (Delta=0.01) optimum: F=3.6805 at c=1.1, d=0.74")
    print("Trudgian's chosen 'nice fraction' instantiation (Thm 2.2): "
          "F=3.6812 at c=11/10, d=3/4")

    print("\n=== Project target height gp = 10^13 + 65,626 (PROPOSAL.md Step 1) ===")
    gp_target = mp.mpf("10000000065626")
    f_t, c_t, d_t, a_t, b_t = full_search(theta, K, gp_target)
    print(f"factory optimum: F={f_t:.6f} at c={c_t:.4f} d={d_t:.4f}  a={a_t:.4f} b={b_t:.4f}")

    L = mp.log(gp_target / (2 * mp.pi))
    _, ac, bc_ = Fc(mp.mpf(11) / 10, theta, K, L)
    _, ad, bd_ = Fd(mp.mpf(3) / 4, L)
    a_legacy, b_legacy = ac + ad, bc_ + bd_
    F_legacy = a_legacy + b_legacy * L
    print(f"reusing legacy (c=11/10,d=3/4) at target height: F={float(F_legacy):.6f}"
          f"  a={float(a_legacy):.4f} b={float(b_legacy):.4f}")
    gain = float(F_legacy) - f_t
    print(f"gain from re-optimizing (c,d) at target height: "
          f"{gain:.6f} in F ({gain / float(F_legacy) * 100:.3f}%)")

    n_cor23 = math.ceil(0.0031 * float(mp.log(gp_target)) ** 2
                         + 0.11 * float(mp.log(gp_target)) - 1e-9)
    n_legacy = math.ceil(blocks_needed(a_legacy, b_legacy, gp_target) - 1e-9)
    n_best = math.ceil(blocks_needed(a_t, b_t, gp_target) - 1e-9)
    print(f"\nrequired consecutive Gram blocks at target height (Theorem-2.1 shape):")
    print(f"  T11 Cor 2.3's published, rounded, universal constants (0.0031, 0.11): N >= {n_cor23}")
    print(f"  exact (a,b) at c=11/10,d=3/4, evaluated at THIS height (no rounding): N >= {n_legacy}")
    print(f"  height-specific re-optimized (c,d):                                  N >= {n_best}")
