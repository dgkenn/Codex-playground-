"""Magnitude-squared coherence, and the one property it is added for: it is NOT wPLI.

`connectivity.py` deliberately uses volume-conduction-resistant estimators for every claim in this project.
`coherence` is the exception, added to test a published finding stated in that quantity (Akeju et al.,
Anesthesiology 2014, PMID 25233374 — sevoflurane separated from propofol by a theta coherence signature).

The tests that matter are the last two: a zero-lag common source must give HIGH coherence and NEAR-ZERO
wPLI, and a phase-lagged coupling must give high wPLI. That contrast is the whole reason both are computed
on the same segments — coherence high with wPLI low means amplitude or a common reference, not phase
coupling, and without the pair a coherence result cannot be told apart from volume conduction.
"""
from __future__ import annotations

import numpy as np
import pytest

from bsde.features.connectivity import coherence, wpli

SF = 128.0
N = int(30 * SF)


def test_identical_signals_are_perfectly_coherent():
    rng = np.random.default_rng(0)
    x = rng.normal(size=N)
    assert coherence(x, x, SF, 8.0, 12.0) == pytest.approx(1.0, abs=1e-9)


def test_independent_noise_is_near_zero():
    rng = np.random.default_rng(1)
    x, y = rng.normal(size=N), rng.normal(size=N)
    assert coherence(x, y, SF, 8.0, 12.0) < 0.15


def test_coherence_is_amplitude_scale_invariant():
    """A coherence is normalised by both auto-spectra, so a gain change must not move it."""
    rng = np.random.default_rng(2)
    t = np.arange(N) / SF
    s = np.sin(2 * np.pi * 10.0 * t)
    a = s + 0.5 * rng.normal(size=N)
    b = s + 0.5 * rng.normal(size=N)
    assert coherence(a, b, SF, 8.0, 12.0) == pytest.approx(
        coherence(a * 17.0, b * 0.03, SF, 8.0, 12.0), abs=1e-9)


def test_coherence_sees_a_zero_lag_common_source_that_wpli_rejects():
    """THE VOLUME-CONDUCTION CASE, and the reason both estimators are reported together.

    Two sensors picking up one source with no phase lag: coherence is substantial, wPLI is near zero
    because there is no consistent nonzero phase difference to detect.
    """
    rng = np.random.default_rng(3)
    t = np.arange(N) / SF
    s = np.sin(2 * np.pi * 10.0 * t)
    a = s + 0.5 * rng.normal(size=N)
    b = s + 0.5 * rng.normal(size=N)
    c, w = coherence(a, b, SF, 8.0, 12.0), wpli(a, b, SF, 8.0, 12.0)
    assert c > 0.25
    assert abs(w) < 0.25
    assert c > abs(w)


def test_phase_lagged_coupling_raises_wpli_while_coherence_stays_similar():
    """The complement. A quarter-cycle lag is the case wPLI is built to find, and it must separate them."""
    rng = np.random.default_rng(4)
    t = np.arange(N) / SF
    a = np.sin(2 * np.pi * 10.0 * t) + 0.5 * rng.normal(size=N)
    b = np.sin(2 * np.pi * 10.0 * (t - 0.025)) + 0.5 * rng.normal(size=N)
    assert wpli(a, b, SF, 8.0, 12.0) > 0.8
    assert coherence(a, b, SF, 8.0, 12.0) > 0.25


def test_band_average_is_over_bins_not_a_single_loud_bin():
    """Averaging per-bin coherences, not coherence of summed cross-spectra.

    One perfectly coherent bin inside an otherwise incoherent band must NOT drive the band value to ~1;
    with 0.5 Hz bins over 8-12 Hz there are about nine, so a single coherent bin should land well below 0.5.
    """
    rng = np.random.default_rng(5)
    t = np.arange(N) / SF
    s = np.sin(2 * np.pi * 10.0 * t)
    a = 20.0 * s + rng.normal(size=N)
    b = 20.0 * s + rng.normal(size=N)
    assert coherence(a, b, SF, 8.0, 12.0) < 0.5


def test_nan_when_too_short_or_band_empty():
    assert np.isnan(coherence(np.zeros(10), np.zeros(10), SF, 8.0, 12.0))
    rng = np.random.default_rng(6)
    x, y = rng.normal(size=N), rng.normal(size=N)
    assert np.isnan(coherence(x, y, SF, 200.0, 300.0))      # above Nyquist: no bins in band
