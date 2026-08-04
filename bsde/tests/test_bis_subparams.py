"""Behavioural tests for the four BIS subparameters.

WHAT THESE TESTS ARE FOR. `bis_subparams.py` implements published DESCRIPTIONS of proprietary quantities.
There is no reference implementation to diff against (rule 23 would demand one if there were), so the only
available check is that each subparameter responds to the thing it is supposed to respond to and does NOT
respond to the thing it is supposed to ignore. Every test below is of that form, and each states which
confusion it would catch.

The SyncFastSlow tests are the important ones. SFS is the only genuinely bispectral quantity here, and a
bispectrum implemented wrongly -- taking `abs` before averaging instead of after, or dropping the conjugate
-- still produces plausible finite numbers that correlate with power. `test_sfs_ignores_power` and
`test_sfs_detects_quadratic_phase_coupling` are constructed so that the WRONG implementation fails them:
the two signals carry identical power at identical frequencies and differ only in phase.
"""
from __future__ import annotations

import numpy as np
import pytest

from bsde.features.bis_subparams import (bis_subparams, burst_suppression_ratio,
                                         quazi_suppression, relative_beta_ratio,
                                         sync_fast_slow)

SF = 250.0


def _psd_with(power_by_band):
    """Synthetic PSD: flat within each named band, tiny elsewhere."""
    freqs = np.arange(0.0, 60.0, 0.25)
    psd = np.full(freqs.size, 1e-9)
    for (lo, hi), p in power_by_band.items():
        psd[(freqs >= lo) & (freqs <= hi)] = p
    return freqs, psd


# --------------------------------------------------------------------------- relative beta ratio

def test_rbr_positive_when_beta_gamma_dominates():
    """RBR rises with high-frequency activation -- the change BIS reads as lightening."""
    freqs, psd = _psd_with({(30.0, 47.0): 10.0, (11.0, 20.0): 1.0})
    assert relative_beta_ratio(freqs, psd) > 0


def test_rbr_negative_when_low_beta_dominates():
    freqs, psd = _psd_with({(30.0, 47.0): 1.0, (11.0, 20.0): 10.0})
    assert relative_beta_ratio(freqs, psd) < 0


def test_rbr_is_scale_invariant():
    """A ratio of two band powers must not move when the amplifier gain changes."""
    freqs, psd = _psd_with({(30.0, 47.0): 4.0, (11.0, 20.0): 1.0})
    assert relative_beta_ratio(freqs, psd) == pytest.approx(
        relative_beta_ratio(freqs, psd * 1e6), abs=1e-9)


def test_rbr_nan_when_a_band_is_empty():
    """Catches a silent -inf leaking into a regression design matrix."""
    freqs = np.arange(0.0, 10.0, 0.25)          # no support above 20 Hz at all
    assert np.isnan(relative_beta_ratio(freqs, np.ones(freqs.size)))


# --------------------------------------------------------------------------- burst suppression ratio

def test_bsr_one_on_flat_signal():
    assert burst_suppression_ratio(np.zeros(int(10 * SF)), SF) == pytest.approx(1.0)


def test_bsr_zero_on_normal_amplitude_eeg():
    rng = np.random.default_rng(0)
    x = rng.normal(0.0, 30.0, int(10 * SF))     # 30 uV RMS: ordinary awake EEG
    assert burst_suppression_ratio(x, SF) < 0.05


def test_bsr_recovers_a_known_suppressed_fraction():
    """Half the epoch flat, half at normal amplitude -> BSR near 0.5."""
    rng = np.random.default_rng(1)
    n = int(10 * SF)
    x = rng.normal(0.0, 30.0, n)
    x[: n // 2] = 0.0
    assert burst_suppression_ratio(x, SF) == pytest.approx(0.5, abs=0.05)


def test_bsr_ignores_excursions_shorter_than_the_duration_rule():
    """This is the whole difference between BSR and 'fraction of samples under 5 uV'.

    A 0.2 s flat gap is below `min_dur_s`; without the run-length rule the naive fraction would count it.
    """
    rng = np.random.default_rng(2)
    n = int(10 * SF)
    x = rng.normal(0.0, 30.0, n)
    for start in range(0, n - int(0.2 * SF), int(1.0 * SF)):
        x[start: start + int(0.2 * SF)] = 0.0   # 20 % of samples are flat, none for long enough
    naive = float(np.mean(np.abs(x - np.median(x)) < 5.0))
    assert naive > 0.15
    assert burst_suppression_ratio(x, SF) < 0.02


def test_bsr_nonfinite_breaks_a_run_rather_than_joining_it():
    """Rule 27. Two 0.3 s flat stretches separated by a bad sample are not one 0.6 s suppression."""
    n = int(10 * SF)
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 30.0, n)
    k = int(0.3 * SF)
    x[1000: 1000 + k] = 0.0
    x[1000 + k] = np.nan
    x[1000 + k + 1: 1000 + 2 * k + 1] = 0.0
    assert burst_suppression_ratio(x, SF, min_dur_s=0.5) < 0.01


def test_bsr_microvolt_hazard_is_real_and_silent():
    """Documents the failure the docstring warns about: volts in -> 1.0 out, no error.

    Asserted rather than merely commented so that anyone who later 'fixes' the scaling by normalising
    inside this function breaks a test instead of silently changing every BSR in the repo.
    """
    rng = np.random.default_rng(4)
    x_uv = rng.normal(0.0, 30.0, int(10 * SF))
    assert burst_suppression_ratio(x_uv, SF) < 0.05
    assert burst_suppression_ratio(x_uv * 1e-6, SF) == pytest.approx(1.0)


# --------------------------------------------------------------------------- QUAZI

def test_quazi_finds_suppression_that_bsr_misses_under_a_slow_wave():
    """The exact case QUAZI was invented for.

    Fast activity is flat for the second half, but a 0.3 Hz, 40 uV wave rides underneath, so the raw
    signal never comes within 5 uV of baseline and plain BSR reads ~0. After high-pass detrending the
    suppression is visible, so QUAZI (defined here as the increment over BSR) is clearly positive.
    """
    rng = np.random.default_rng(5)
    n = int(20 * SF)
    t = np.arange(n) / SF
    fast = rng.normal(0.0, 25.0, n)
    fast[n // 2:] = 0.0
    x = fast + 40.0 * np.sin(2 * np.pi * 0.3 * t)
    assert burst_suppression_ratio(x, SF) < 0.10
    assert quazi_suppression(x, SF) > 0.25


def test_quazi_near_zero_when_bsr_already_sees_everything():
    """No slow wave to remove -> QUAZI adds nothing, which is what the increment definition should give."""
    rng = np.random.default_rng(6)
    n = int(20 * SF)
    x = rng.normal(0.0, 25.0, n)
    x[n // 2:] = 0.0
    assert abs(quazi_suppression(x, SF)) < 0.10


# --------------------------------------------------------------------------- SyncFastSlow

def _coupled(n, sf, rng, coupled: bool):
    """f1=10 Hz, f2=16 Hz and their sum 26 Hz, with the sum's phase either locked or independent.

    Identical amplitude at identical frequencies in both arms. Only the phase of the 26 Hz component
    differs, and it is re-randomised per segment in the uncoupled arm so that segment averaging can tell
    them apart.
    """
    t = np.arange(n) / sf
    p1, p2 = rng.uniform(0, 2 * np.pi, 2)
    x = np.sin(2 * np.pi * 10.0 * t + p1) + np.sin(2 * np.pi * 16.0 * t + p2)
    if coupled:
        x = x + np.sin(2 * np.pi * 26.0 * t + p1 + p2)
    else:
        x = x + np.sin(2 * np.pi * 26.0 * t + rng.uniform(0, 2 * np.pi))
    return x


def _sfs_over_segments(sf, coupled, seed, n_blocks=40, block_s=1.024):
    """Concatenate independently-phased blocks so the averaging in `sync_fast_slow` has something to average."""
    rng = np.random.default_rng(seed)
    n = int(block_s * sf)
    return sync_fast_slow(np.concatenate([_coupled(n, sf, rng, coupled) for _ in range(n_blocks)]), sf)


SFS_COUPLING_MARGIN = 0.5


def test_sfs_detects_quadratic_phase_coupling():
    """Coupled and uncoupled signals have IDENTICAL power spectra; only SFS can separate them.

    A bispectrum that takes |B| per segment before averaging would score these the same, because the
    magnitude of a single segment's triple product does not depend on whether the phases are related.

    THE MARGIN IS NOT DECORATION (rule 40). Measured over eight seeds, the correct implementation separates
    the two arms by 1.19-1.81 log units; the magnitude-first version separates them by at most 0.23 and
    goes the WRONG WAY on three of the eight. A bare `hi > lo` would therefore pass the broken
    implementation most of the time, so the margin is set at 0.5 -- above everything the broken version
    achieves, far below everything the correct one does.
    """
    for seed in (10, 11, 12):
        lo = _sfs_over_segments(SF, coupled=False, seed=seed)
        hi = _sfs_over_segments(SF, coupled=True, seed=seed)
        assert np.isfinite(lo) and np.isfinite(hi)
        assert hi - lo > SFS_COUPLING_MARGIN, (seed, lo, hi)


def test_sfs_ignores_power():
    """Scaling the whole signal scales every bispectral value by the same factor, so a RATIO must not move."""
    rng = np.random.default_rng(11)
    x = np.concatenate([_coupled(int(1.024 * SF), SF, rng, True) for _ in range(40)])
    assert sync_fast_slow(x, SF) == pytest.approx(sync_fast_slow(x * 7.0, SF), abs=1e-6)


def test_sfs_is_non_negative_by_construction():
    """The denominator region is contained in the numerator region, so the ratio cannot fall below 1."""
    rng = np.random.default_rng(12)
    for seed_scale in (1.0, 50.0):
        x = rng.normal(0.0, seed_scale, int(30 * SF))
        v = sync_fast_slow(x, SF)
        assert np.isnan(v) or v >= -1e-9


def test_sfs_nan_when_too_short():
    assert np.isnan(sync_fast_slow(np.zeros(100), SF))


def test_sfs_skips_bad_segments_without_gluing():
    """Rule 27 again. A short burst of NaN must not splice phase across the gap.

    With the segments dropped, the surviving estimate stays close to the clean one; a `x[isfinite(x)]`
    compression would shift every later segment's phase alignment and move the value substantially.
    """
    rng = np.random.default_rng(13)
    x = np.concatenate([_coupled(int(1.024 * SF), SF, rng, True) for _ in range(60)])
    clean = sync_fast_slow(x, SF)
    holed = x.copy()
    holed[5000:5030] = np.nan
    assert sync_fast_slow(holed, SF) == pytest.approx(clean, abs=0.15 * max(1.0, abs(clean)))


# --------------------------------------------------------------------------- wrapper

def test_bis_subparams_returns_all_four_and_computes_its_own_psd():
    rng = np.random.default_rng(14)
    x = rng.normal(0.0, 30.0, int(30 * SF))
    out = bis_subparams(x, SF)
    assert set(out) == {"bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs"}
    assert all(np.isfinite(v) for v in out.values()), out
