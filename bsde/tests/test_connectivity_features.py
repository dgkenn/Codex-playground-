"""Ground-truth checks for bsde.features.connectivity.wpli.

wPLI is near-zero (in expectation) for two independent signals and only close to its magnitude limit for
a consistent, non-zero-and-non-pi phase lag -- a 0 or pi lag gives ~0 by construction (that is the entire
point of the measure: it is a phase-LAG index, not a phase-locking index, so it must be blind to the
zero-lag case that volume conduction produces).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.connectivity import wpli

SF = 250.0
DUR = 60.0


def test_wpli_independent_white_noise_is_low():
    rng = np.random.default_rng(10)
    x = rng.normal(size=int(DUR * SF))
    y = rng.normal(size=int(DUR * SF))
    got = wpli(x, y, SF, 8.0, 13.0, window_s=2.0, overlap=0.5)
    assert abs(got) < 0.3, f"got {got}"


def test_wpli_zero_phase_lag_sinusoid_is_near_zero():
    """A zero-lag copy of itself must NOT read as high wPLI -- that is the measure's whole purpose."""
    n = int(DUR * SF)
    t = np.arange(n) / SF
    rng = np.random.default_rng(11)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.05 * rng.normal(size=n)
    y = np.sin(2 * np.pi * 10.0 * t) + 0.05 * rng.normal(size=n)  # zero lag, independent noise only
    got = wpli(x, y, SF, 8.0, 13.0, window_s=2.0, overlap=0.5)
    assert abs(got) < 0.3, f"got {got}"


def test_wpli_pi_phase_lag_sinusoid_is_near_zero():
    n = int(DUR * SF)
    t = np.arange(n) / SF
    rng = np.random.default_rng(12)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.05 * rng.normal(size=n)
    y = np.sin(2 * np.pi * 10.0 * t + np.pi) + 0.05 * rng.normal(size=n)
    got = wpli(x, y, SF, 8.0, 13.0, window_s=2.0, overlap=0.5)
    assert abs(got) < 0.3, f"got {got}"


def test_wpli_quarter_pi_phase_lag_sinusoid_is_high():
    n = int(DUR * SF)
    t = np.arange(n) / SF
    rng = np.random.default_rng(13)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.05 * rng.normal(size=n)
    y = np.sin(2 * np.pi * 10.0 * t + np.pi / 4.0) + 0.05 * rng.normal(size=n)
    got = wpli(x, y, SF, 8.0, 13.0, window_s=2.0, overlap=0.5)
    assert got > 0.7, f"got {got}"


def test_wpli_nan_on_too_short_signal():
    x = np.random.default_rng(0).normal(size=100)
    y = np.random.default_rng(1).normal(size=100)
    got = wpli(x, y, SF, 8.0, 13.0, window_s=2.0, overlap=0.5)
    assert np.isnan(got)


def test_wpli_non_debiased_and_debiased_both_high_for_consistent_lag():
    n = int(DUR * SF)
    t = np.arange(n) / SF
    rng = np.random.default_rng(14)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.05 * rng.normal(size=n)
    y = np.sin(2 * np.pi * 10.0 * t + np.pi / 4.0) + 0.05 * rng.normal(size=n)
    got_debiased = wpli(x, y, SF, 8.0, 13.0, debias=True)
    got_plain = wpli(x, y, SF, 8.0, 13.0, debias=False)
    assert got_debiased > 0.7
    assert got_plain > 0.7
