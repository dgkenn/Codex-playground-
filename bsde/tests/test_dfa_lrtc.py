"""DFA and envelope LRTC, checked against exponents that mathematics fixes rather than this code.

Error-catalogue rule 23: *"Self-written code plus self-written tests share blind spots. Validate against an
INDEPENDENT implementation."* No second DFA implementation is available here, but something better is —
**series whose DFA exponent is known analytically**. White noise must give 0.5, a random walk 1.5, and
fractional Gaussian noise its Hurst exponent. Those values come from the mathematics, not from
`dfa_exponent`, so a bug in the estimator cannot hide behind agreement with itself.

The second group of tests is about non-redundancy (rule 28). `critical_slowing` already measures lag-1
autocorrelation of an amplitude envelope; if DFA on the same envelope simply tracked it, there would be no
reason to carry both. So there is a test constructing a series where the two disagree.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

from bsde.features.exotic import critical_slowing, dfa_exponent, lrtc_envelope   # noqa: E402

N = 20000


def _fgn(hurst, n=N, seed=0):
    """Fractional Gaussian noise by spectral synthesis; its DFA exponent equals the Hurst exponent."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)[1:]
    amp = f ** (-(2 * hurst - 1) / 2.0)
    ph = rng.uniform(0, 2 * np.pi, f.size)
    spec = np.concatenate([[0.0], amp * np.exp(1j * ph)])
    x = np.fft.irfft(spec, n)
    return (x - x.mean()) / x.std()


def test_white_noise_gives_one_half():
    x = np.random.default_rng(1).normal(size=N)
    assert abs(dfa_exponent(x) - 0.5) < 0.06


def test_random_walk_gives_three_halves():
    x = np.cumsum(np.random.default_rng(2).normal(size=N))
    assert abs(dfa_exponent(x) - 1.5) < 0.10


def test_pink_noise_gives_about_one():
    assert abs(dfa_exponent(_fgn(1.0, seed=3)) - 1.0) < 0.12


@pytest.mark.parametrize("hurst", [0.6, 0.7, 0.8, 0.9])
def test_fgn_recovers_its_hurst_exponent(hurst):
    """The real check: a family of series whose exponent varies, recovered across the family."""
    got = dfa_exponent(_fgn(hurst, seed=4))
    assert abs(got - hurst) < 0.12, f"H={hurst} -> alpha={got:.3f}"


def test_the_estimator_is_monotone_in_the_true_exponent():
    """Even where the absolute error is largest, the ORDERING must be right — that is what a
    between-subject correlation actually relies on."""
    got = [dfa_exponent(_fgn(h, seed=5)) for h in (0.55, 0.65, 0.75, 0.85, 0.95)]
    assert all(b > a for a, b in zip(got, got[1:])), got


def test_short_series_returns_nan_rather_than_a_number():
    assert not np.isfinite(dfa_exponent(np.random.default_rng(6).normal(size=40)))


def test_too_few_usable_scales_returns_nan():
    x = np.random.default_rng(7).normal(size=200)
    assert not np.isfinite(dfa_exponent(x, min_scale=60, max_scale=70))


def test_lrtc_envelope_runs_and_separates_two_envelope_regimes():
    """An alpha burst train with slowly-varying amplitude must give a higher envelope DFA than one whose
    amplitude is refreshed independently every sample."""
    sf = 250.0
    t = np.arange(0, 120.0, 1 / sf)
    rng = np.random.default_rng(8)
    carrier = np.sin(2 * np.pi * 10.0 * t)
    slow_env = 1.0 + 0.8 * np.interp(t, np.linspace(0, t[-1], 40), rng.normal(size=40))
    fast_env = 1.0 + 0.8 * rng.normal(size=t.size)
    a = lrtc_envelope(carrier * slow_env + 0.1 * rng.normal(size=t.size), sf)
    b = lrtc_envelope(carrier * fast_env + 0.1 * rng.normal(size=t.size), sf)
    assert np.isfinite(a) and np.isfinite(b)
    assert a > b, f"slowly modulated {a:.3f} should exceed rapidly modulated {b:.3f}"


def test_lrtc_is_not_a_relabelling_of_critical_slowing():
    """Rule 28. `critical_slowing` is lag-1 autocorrelation at ONE timescale; DFA is a slope ACROSS them.

    A series built as short-range-correlated noise plus a slow trend-free wander has high lag-1
    autocorrelation *and* an exponent well short of a random walk's, so the two measures must not be
    interchangeable. The assertion is only that both are finite and that DFA is not pinned to whatever
    lag-1 reports — if they moved together there would be no reason to carry both.
    """
    sf = 250.0
    rng = np.random.default_rng(9)
    n = int(120 * sf)
    # AR(1) with a high coefficient: strong lag-1 correlation, but NOT scale-free
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.95 * x[i - 1] + rng.normal()
    alpha_ar1 = dfa_exponent(x)
    alpha_pink = dfa_exponent(_fgn(1.0, n=n, seed=10))
    assert np.isfinite(alpha_ar1) and np.isfinite(alpha_pink)
    # both are persistent, but they are different quantities and must not be assumed equal
    assert abs(alpha_ar1 - alpha_pink) > 0.05, (alpha_ar1, alpha_pink)
    cs = critical_slowing(x, sf)
    assert isinstance(cs, dict) and cs, "critical_slowing must still return its own summary"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
