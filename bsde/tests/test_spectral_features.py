"""Ground-truth checks for bsde.features.spectral.

Every test targets an analytically known answer on a constructed PSD, not merely "it runs".
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.spectral import (
    band_power, relative_band_power, spectral_edge, median_frequency,
    spectral_entropy, BANDS,
)


def _flat_psd(lo=0.0, hi=60.0, n=601, height=2.0):
    """A perfectly flat PSD of constant height `height` over [lo, hi]."""
    freqs = np.linspace(lo, hi, n)
    psd = np.full(n, height)
    return freqs, psd


def test_band_power_of_flat_psd_equals_height_times_width():
    freqs, psd = _flat_psd(height=3.0)
    got = band_power(freqs, psd, 10.0, 20.0)
    expected = 3.0 * 10.0
    assert abs(got - expected) / expected < 0.01


def test_band_power_nan_when_range_too_narrow():
    freqs, psd = _flat_psd(n=61)  # 1 Hz spacing
    # a range narrower than one bin should yield fewer than 2 points
    got = band_power(freqs, psd, 10.0, 10.05)
    assert np.isnan(got)


def test_relative_band_power_of_flat_psd_is_ratio_of_widths():
    freqs, psd = _flat_psd(lo=1.0, hi=45.0, n=441, height=5.0)
    got = relative_band_power(freqs, psd, 8.0, 13.0, total_lo=1.0, total_hi=45.0)
    expected = (13.0 - 8.0) / (45.0 - 1.0)
    assert abs(got - expected) < 0.01


def test_spectral_edge_on_flat_band_matches_analytic_frequency():
    """For a flat PSD over [lo, hi], cumulative power is linear in frequency, so the pct-edge is exactly
    lo + pct/100 * (hi - lo). Check within one bin width.
    """
    lo, hi, n = 1.0, 45.0, 441
    freqs, psd = _flat_psd(lo=lo, hi=hi, n=n, height=1.0)
    bin_width = (hi - lo) / (n - 1)
    for pct in (25.0, 50.0, 95.0):
        got = spectral_edge(freqs, psd, pct=pct, lo_hz=lo, hi_hz=hi)
        expected = lo + pct / 100.0 * (hi - lo)
        assert abs(got - expected) <= bin_width, f"pct={pct}: got {got}, expected {expected}"


def test_median_frequency_matches_spectral_edge_50():
    freqs, psd = _flat_psd(lo=1.0, hi=45.0, n=441)
    assert median_frequency(freqs, psd) == pytest.approx(spectral_edge(freqs, psd, pct=50.0), abs=1e-9)


def test_spectral_edge_nan_on_degenerate_range():
    freqs, psd = _flat_psd(n=61)
    assert np.isnan(spectral_edge(freqs, psd, lo_hz=10.0, hi_hz=10.05))


def test_spectral_entropy_of_flat_psd_is_exactly_one():
    freqs, psd = _flat_psd(lo=1.0, hi=45.0, n=441, height=7.0)
    got = spectral_entropy(freqs, psd, lo_hz=1.0, hi_hz=45.0, normalize=True)
    assert abs(got - 1.0) < 1e-9


def test_spectral_entropy_concentrated_in_one_bin_is_near_zero():
    freqs = np.linspace(1.0, 45.0, 441)
    psd = np.full(441, 1e-12)
    psd[200] = 1.0     # nearly all power in a single bin
    got = spectral_entropy(freqs, psd, lo_hz=1.0, hi_hz=45.0, normalize=True)
    assert got < 0.05


def test_spectral_entropy_nan_on_degenerate_range():
    freqs, psd = _flat_psd(n=61)
    assert np.isnan(spectral_entropy(freqs, psd, lo_hz=10.0, hi_hz=10.05))


def test_bands_constant_covers_standard_edges():
    assert BANDS["delta"] == (1.0, 4.0)
    assert BANDS["theta"] == (4.0, 8.0)
    assert BANDS["alpha"] == (8.0, 13.0)
    assert BANDS["beta"] == (13.0, 30.0)
    assert BANDS["gamma"] == (30.0, 45.0)


def test_band_power_on_real_welch_psd_of_known_sinusoid():
    """Sanity check against welch_psd on a real signal: power should concentrate near the sinusoid freq."""
    from bsde.features.aperiodic import welch_psd
    sfreq = 250.0
    t = np.arange(int(60 * sfreq)) / sfreq
    rng = np.random.default_rng(0)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.01 * rng.normal(size=t.size)
    freqs, psd = welch_psd(x, sfreq, window_s=4.0, overlap=0.5)
    alpha_power = band_power(freqs, psd, 8.0, 13.0)
    gamma_power = band_power(freqs, psd, 30.0, 45.0)
    assert alpha_power > 50 * gamma_power
