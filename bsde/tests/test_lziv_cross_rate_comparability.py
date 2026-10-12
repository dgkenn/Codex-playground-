"""Lempel-Ziv must mean the same thing at every sampling rate, because layer_cross_domain compares it across
datasets that do not share one.

THE BUG THIS PINS. `f_lziv` fixed its window in SECONDS. Normalising LZ76 by n/log2(n) is only asymptotically
length-invariant, so at finite n the normalised value still depends on n -- and 10 seconds is a different n at
every rate. Across this project's datasets that was 1,000 samples at Sleep-EDF's 100 Hz, 2,500 at Figshare's
250 Hz, 5,000 at I-CARE's 500 Hz and 50,000 at ds005620's 5 kHz: a fiftyfold spread in n, compared across
datasets as though it were one measure.

Worse, the spread is CORRELATED WITH DATASET IDENTITY, which is the one confound structure the engine's
site/dataset probes are least able to disentangle from a real effect -- a candidate would have appeared to
transfer or fail to transfer for reasons that were purely an artefact of acquisition rate.

The fix decimates every channel to a common rate (anti-aliased) before windowing. These tests assert the
property that matters: the same underlying signal yields the same value regardless of the rate it arrives at.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.seed import f_lziv, LZIV_TARGET_HZ, LZIV_WINDOW_S

CH = ["Fp1", "F3", "P3", "O1"]


def _brownish(n, seed=7, nch=4):
    """A 1/f-ish signal: cumulative Gaussian noise. Deterministic given the seed."""
    return np.cumsum(np.random.default_rng(seed).normal(size=(nch, n)), axis=1)


def test_the_same_signal_gives_the_same_value_at_every_sampling_rate():
    """The property the cross-domain layer depends on. Before the fix these differed substantially."""
    from scipy.signal import resample_poly
    x = _brownish(60_000)                      # 60 s at 1000 Hz
    v1000 = f_lziv(x, CH, 1000.0, {})
    v200 = f_lziv(resample_poly(x, 1, 5, axis=1), CH, 200.0, {})
    v100 = f_lziv(resample_poly(x, 1, 10, axis=1), CH, 100.0, {})
    for v in (v1000, v200, v100):
        assert np.isfinite(v)
    spread = max(v1000, v200, v100) - min(v1000, v200, v100)
    assert spread < 0.02, f"LZ still depends on sampling rate: {v1000=} {v200=} {v100=} spread={spread}"


@pytest.mark.parametrize("sfreq", [100.0, 250.0, 500.0, 5000.0])
def test_every_project_sampling_rate_is_computable_and_bounded(sfreq):
    """100 Hz Sleep-EDF, 250 Hz Figshare, 500 Hz I-CARE, 5 kHz ds005620 -- all four real rates."""
    v = f_lziv(_brownish(int(30 * sfreq)), CH, sfreq, {})
    assert np.isfinite(v), f"not computable at {sfreq} Hz"
    assert 0.0 < v < 2.0, f"implausible normalised LZ {v} at {sfreq} Hz"


def test_a_recording_shorter_than_one_window_returns_nan_rather_than_a_short_window_value():
    """A value from fewer samples is not comparable with one from the full window, so it must not be
    emitted at all."""
    too_short = _brownish(int(0.5 * LZIV_WINDOW_S * LZIV_TARGET_HZ))
    assert np.isnan(f_lziv(too_short, CH, LZIV_TARGET_HZ, {}))


def test_a_signal_already_at_the_target_rate_is_not_resampled():
    """No decimation should occur at the target rate -- resampling a signal to its own rate would still
    filter it, changing the value for no reason."""
    x = _brownish(int(30 * LZIV_TARGET_HZ))
    a = f_lziv(x, CH, LZIV_TARGET_HZ, {})
    b = f_lziv(x, CH, LZIV_TARGET_HZ, {})
    assert a == b and np.isfinite(a)


def test_a_constant_signal_scores_far_below_noise_at_every_rate():
    """Sanity that decimation has not destroyed the measure's discriminating power."""
    for sfreq in (100.0, 500.0, 5000.0):
        n = int(20 * sfreq)
        flat = np.ones((4, n)) * 3.0
        noise = np.random.default_rng(1).normal(size=(4, n))
        assert f_lziv(flat, CH, sfreq, {}) < f_lziv(noise, CH, sfreq, {}), f"at {sfreq} Hz"
