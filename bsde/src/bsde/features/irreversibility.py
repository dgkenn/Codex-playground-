"""Time-irreversibility: the one measure family PROVABLY orthogonal to everything this project has run.

=========================================================================================================
WHY THIS EXISTS, AND WHY THE ORTHOGONALITY IS A THEOREM RATHER THAN A HOPE
=========================================================================================================
Rule 60 says a measure chosen for belonging to a different family must be SHOWN to differ from that family,
and this project has failed that test repeatedly: `uce_v1` was the whole-head exponent restated, E73's
graph measure correlated with mean connectivity at +0.9962, E104's perturbational contrast added nothing
over the spontaneous exponent. Every candidate so far has been some summary of AMPLITUDE or of the POWER
SPECTRUM, and they keep turning out to be each other.

**Time-irreversibility escapes that family by construction, not by inspection.**

The argument, and it is short. By Wiener-Khinchin the power spectral density is the Fourier transform of
the autocovariance, and the autocovariance is SYMMETRIC IN LAG: cov(x_t, x_{t+k}) = cov(x_t, x_{t-k}) for
any stationary process. Reversing time leaves the autocovariance exactly unchanged, and therefore leaves
the PSD exactly unchanged. So **every second-order spectral quantity -- the aperiodic exponent, every band
power, spectral entropy, spectral edge, the alpha peak -- is INVARIANT under time reversal.** A statistic
that measures time asymmetry can therefore only be reading structure those quantities cannot see.

Stronger still: any stationary GAUSSIAN process is time-reversible whatever its spectrum. So a
phase-randomised surrogate -- which preserves the PSD exactly and Gaussianises everything else -- has zero
irreversibility by construction. That gives a per-recording null for free (see `phase_randomise`), and it
is the same trick E104's sham arm played: the control is cut from the recording itself.

This is a measure from non-equilibrium statistical mechanics, where irreversibility is the signature of a
system driven away from thermodynamic equilibrium and is proportional to entropy production. Its use on
neural data is established (the broken-detailed-balance line, and irreversibility-and-consciousness work
following it); nothing here is novel as a measure, only as an application in this project.

=========================================================================================================
WHAT IS IMPLEMENTED
=========================================================================================================
`permutation_irreversibility` -- KL divergence between the ordinal-pattern distribution of x(t) and of
    x(-t). **Invariant to any monotone amplitude transform**, because it uses only orderings, so rule 57's
    trap (an amplitude in arbitrary units is not a magnitude; EMG gain varies per subject) cannot bite it.
    Zero for any reversible process. This is the primary.

`increment_asymmetry` -- normalised third moment of lagged increments, E[(x_{t+k}-x_t)^3] / E[(...)^2]^1.5.
    The classical Ramsey-Rothman statistic. Zero for any reversible process. NOT invariant to a monotone
    transform, so it is reported as a secondary and never as an effect size in raw units.

`phase_randomise` -- surrogate with the IDENTICAL power spectrum and randomised phases. The null.

CONVENTION, matching `aperiodic.py` and `complexity.py`: plain numpy, no scipy, functions not classes.
"""
from __future__ import annotations

import numpy as np


def _ordinal_counts(x: np.ndarray, order: int, delay: int):
    """Histogram of ordinal patterns AND of the same windows reversed, in one pass.

    The pattern distribution of the time-reversed SERIES equals the distribution of reversed PATTERNS in
    the forward series, so both histograms come from one sweep and are guaranteed to be built on exactly
    the same windows -- which matters, because a KL divergence between histograms with different supports
    is not a divergence at all.
    """
    x = np.asarray(x, float)
    n = x.size - delay * (order - 1)
    if n < 1:
        return None, None
    fwd: dict = {}
    rev: dict = {}
    for i in range(n):
        w = x[i:i + delay * order:delay]
        if not np.all(np.isfinite(w)):
            continue
        p = tuple(np.argsort(w, kind="quicksort"))
        q = tuple(np.argsort(w[::-1], kind="quicksort"))
        fwd[p] = fwd.get(p, 0) + 1
        rev[q] = rev.get(q, 0) + 1
    return fwd, rev


def permutation_irreversibility(x: np.ndarray, order: int = 3, delay: int = 1,
                                normalize: bool = True) -> float:
    """KL divergence D( forward ordinal patterns || time-reversed ordinal patterns ), base 2.

    Zero for any time-reversible process (in particular for any stationary Gaussian process, whatever its
    power spectrum). Positive when the signal's ordinal structure distinguishes past from future -- e.g. a
    sawtooth, a relaxation oscillator, or any system with asymmetric rise and fall.

    `normalize` divides by log2(order!), the maximum entropy of the pattern alphabet, so values from
    different embedding orders are on a comparable scale. It does NOT bound the result at 1; a KL
    divergence has no such bound, and pretending otherwise would be the kind of hardcoded convention
    rule 63 warns about.

    Symmetrised deliberately: D_KL is asymmetric in its arguments, and which series one calls "forward" is
    arbitrary for a recording with no privileged direction, so the Jeffreys form (D(f||r) + D(r||f)) / 2 is
    used. Any pattern with zero count in one histogram is dropped from BOTH, with the surviving mass
    renormalised -- an unseen pattern is missing data, not infinite divergence.
    """
    fwd, rev = _ordinal_counts(x, order, delay)
    if not fwd or not rev:
        return float("nan")
    keys = [k for k in fwd if k in rev and fwd[k] > 0 and rev[k] > 0]
    if len(keys) < 2:
        return float("nan")
    f = np.array([fwd[k] for k in keys], float)
    r = np.array([rev[k] for k in keys], float)
    f /= f.sum()
    r /= r.sum()
    d = 0.5 * (np.sum(f * np.log2(f / r)) + np.sum(r * np.log2(r / f)))
    if normalize:
        import math
        m = math.log2(math.factorial(order))
        d = d / m if m > 0 else float("nan")
    return float(d)


def increment_asymmetry(x: np.ndarray, lag: int = 1) -> float:
    """Normalised third moment of lagged increments: E[(x_{t+k}-x_t)^3] / E[(x_{t+k}-x_t)^2]^{3/2}.

    The classical time-reversibility statistic (Ramsey-Rothman). Exactly zero for any reversible process,
    because reversal negates the increment and an odd moment must then equal its own negative.

    Normalising by the second moment makes it invariant to a SCALE change but not to a general monotone
    transform, so unlike `permutation_irreversibility` it is not immune to rule 57's amplitude-gain trap.
    Secondary measure; never an effect size in raw units.
    """
    x = np.asarray(x, float)
    d = x[lag:] - x[:-lag]
    d = d[np.isfinite(d)]
    if d.size < 32:
        return float("nan")
    m2 = float(np.mean(d ** 2))
    if m2 <= 0:
        return float("nan")
    return float(np.mean(d ** 3) / m2 ** 1.5)


def phase_randomise(x: np.ndarray, rng) -> np.ndarray:
    """Surrogate with the IDENTICAL power spectrum and randomised Fourier phases.

    This is the null for every measure in this module: it preserves the autocovariance (and hence the PSD,
    the aperiodic exponent, every band power and every spectral summary) exactly, while destroying the
    higher-order structure that time asymmetry lives in. A stationary Gaussian process is time-reversible
    whatever its spectrum, so the surrogate's irreversibility is zero up to sampling noise.

    Conjugate symmetry is enforced so the inverse transform is real without taking a real part, and the DC
    and (for even n) Nyquist bins keep their original phases because they have no conjugate partner to
    pair with -- randomising them would change the mean or introduce a spurious alternation.
    """
    x = np.asarray(x, float)
    n = x.size
    if n < 8:
        return x.copy()
    X = np.fft.rfft(x)
    ph = rng.uniform(0, 2 * np.pi, X.size)
    ph[0] = 0.0
    if n % 2 == 0:
        ph[-1] = 0.0
    return np.fft.irfft(np.abs(X) * np.exp(1j * ph), n=n)
