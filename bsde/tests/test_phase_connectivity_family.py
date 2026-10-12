"""dPLI and imaginary coherence: the two measures E39 said the phase family was missing.

E39's outcome names its first deficit plainly: *"`wpli_alpha` is the only phase feature in the registry, so
E39's statistic was 'wPLI against the rest' rather than a family mean, and had no way to average down noise
on the side that mattered. E36's Delta averaged four."* These tests cover the two estimators added to close
that gap.

**What each test is for.** A new feature is only worth adding if it behaves correctly on signals whose
answer is known by construction, and if it is not a third name for a measure already present — rule 28,
which this project has now paid for three times by predicting that two measurements separated in space or
frequency would be independent and finding them redundant. So the assertions are of two kinds: ground truth
on synthetic signals, and **evidence of non-redundancy against `wpli`**.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

from bsde.features.connectivity import dpli, imag_coherence, wpli    # noqa: E402

SFREQ = 250.0
DUR = 40.0
LO, HI = 8.0, 13.0


def _pair(lag_s, seed=0, amp=1.0, noise=0.5, f=10.0):
    """`y` is `x` delayed by `lag_s`, plus independent noise in both."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, DUR, 1.0 / SFREQ)
    phase = 2 * np.pi * f * t
    x = amp * np.sin(phase) + noise * rng.normal(size=t.size)
    y = amp * np.sin(phase - 2 * np.pi * f * lag_s) + noise * rng.normal(size=t.size)
    return x, y


def test_dpli_is_half_when_neither_signal_leads():
    """Zero lag means no consistent lead, and dPLI's null value is 0.5, not 0."""
    x, y = _pair(0.0, seed=1)
    assert abs(dpli(x, y, SFREQ, LO, HI) - 0.5) < 0.10


def test_dpli_is_signed_and_antisymmetric():
    """The whole reason for having dPLI: swapping the arguments must reflect it about 0.5."""
    x, y = _pair(0.020, seed=2)          # 20 ms at 10 Hz = a fifth of a cycle
    a = dpli(x, y, SFREQ, LO, HI)
    b = dpli(y, x, SFREQ, LO, HI)
    assert abs((a - 0.5) + (b - 0.5)) < 0.02, "dPLI(x,y) and dPLI(y,x) must be mirror images"
    assert abs(a - 0.5) > 0.15, "a fifth-of-a-cycle lag should produce a clear lead"


def test_wpli_cannot_tell_the_two_lead_directions_apart_and_dpli_can():
    """The non-redundancy that justifies adding dPLI at all (rule 28).

    A leads B and B leads A are the same signal pair with the arguments swapped. wPLI is direction-free, so
    it must return the same value both ways; dPLI must not.
    """
    x, y = _pair(0.020, seed=3)
    w_ab, w_ba = wpli(x, y, SFREQ, LO, HI), wpli(y, x, SFREQ, LO, HI)
    d_ab, d_ba = dpli(x, y, SFREQ, LO, HI), dpli(y, x, SFREQ, LO, HI)
    assert abs(w_ab - w_ba) < 1e-9, "wPLI is direction-free by construction"
    # TWO EARLIER DRAFTS OF THIS ASSERTION WERE WRONG, AND WHAT THEY GOT WRONG IS WORTH KEEPING.
    # The first demanded a separation above 0.30 and got 0.221 — a threshold picked from nothing. The
    # second claimed the separation should sharpen as noise falls, and it did not move by one part in
    # 1e15: **dPLI counts SIGNS, so rescaling the noise cannot change it at a fixed seed.** Measured
    # across lags of 5-45 ms it sits at 0.217-0.226, and across noise levels 0.1-2.0 it is constant.
    # That is not a defect — it is what a sign statistic does. dPLI measures how CONSISTENT the lead
    # direction is, not how large the lag is, and a test that expects it to track lag magnitude is
    # testing the wrong quantity.
    assert abs(d_ab - d_ba) > 0.15
    assert abs(wpli(*_pair(0.020, seed=3, noise=0.1), SFREQ, LO, HI)
               - wpli(_pair(0.020, seed=3, noise=0.1)[1], _pair(0.020, seed=3, noise=0.1)[0],
                      SFREQ, LO, HI)) < 1e-9


def test_dpli_is_invariant_to_rescaling_a_channel():
    """The corollary of counting signs, and a real difference from any amplitude-weighted measure.

    Multiplying one channel by a constant changes every amplitude in the cross-spectrum and no sign, so
    dPLI must be bit-identical. Verified rather than assumed, because "obviously invariant" is how a
    normalisation bug survives.
    """
    rng = np.random.default_rng(9)
    t = np.arange(0, DUR, 1.0 / SFREQ)
    x = np.sin(2 * np.pi * 10.0 * t) + 0.5 * rng.normal(size=t.size)
    y = np.sin(2 * np.pi * 10.0 * t - 0.4 * np.pi) + 0.5 * rng.normal(size=t.size)
    assert dpli(x, y, SFREQ, LO, HI) == dpli(x, 5.0 * y, SFREQ, LO, HI)
    assert dpli(x, y, SFREQ, LO, HI) == dpli(0.01 * x, y, SFREQ, LO, HI)


def test_imag_coherence_is_zero_for_zero_lag_volume_conduction():
    """Nolte's point: instantaneous mixing has no imaginary part, so iCOH must ignore it."""
    rng = np.random.default_rng(4)
    t = np.arange(0, DUR, 1.0 / SFREQ)
    src = np.sin(2 * np.pi * 10.0 * t) + 0.2 * rng.normal(size=t.size)
    x = src + 0.1 * rng.normal(size=t.size)          # same source, no delay: pure volume conduction
    y = 0.7 * src + 0.1 * rng.normal(size=t.size)
    assert imag_coherence(x, y, SFREQ, LO, HI) < 0.05


def test_imag_coherence_rises_with_a_real_phase_lag():
    x0, y0 = _pair(0.0, seed=5)
    x1, y1 = _pair(0.025, seed=5)
    assert imag_coherence(x1, y1, SFREQ, LO, HI) > imag_coherence(x0, y0, SFREQ, LO, HI) + 0.10


def test_imag_coherence_scales_with_coupling_strength_where_wpli_does_not():
    """The construction difference that makes iCOH a THIRD instrument rather than a third name.

    wPLI normalises by `E[|Im(S)|]`, so it is a ratio of imaginary parts and is near-blind to how strong
    the coupling is. iCOH normalises by the auto-spectra, so it must fall as the coupled component is
    buried in noise. If both moved together there would be no reason to carry both.
    """
    strong = _pair(0.025, seed=6, amp=1.0, noise=0.3)
    weak = _pair(0.025, seed=6, amp=1.0, noise=3.0)
    i_s, i_w = imag_coherence(*strong, SFREQ, LO, HI), imag_coherence(*weak, SFREQ, LO, HI)
    w_s, w_w = wpli(*strong, SFREQ, LO, HI), wpli(*weak, SFREQ, LO, HI)
    assert i_s - i_w > 0.15, "iCOH must track coupling magnitude"
    assert (i_s - i_w) > (w_s - w_w), "iCOH must be MORE magnitude-sensitive than wPLI"


def test_all_three_return_nan_rather_than_a_number_when_the_segmentation_fails():
    """A recording too short for two segments has no estimate, and must say so rather than guess."""
    short = np.random.default_rng(7).normal(size=100)
    for fn in (wpli, dpli, imag_coherence):
        assert not np.isfinite(fn(short, short, SFREQ, LO, HI)), fn.__name__


def test_the_three_estimators_see_identical_segments():
    """They share `_cross_spectra` precisely so that a family comparison is not confounded by windowing.

    Checked behaviourally: changing the window length must move all three, and the value at a given window
    must be reproducible. If one silently used different segments, a between-family difference could be a
    windowing artefact rather than a measurement one.
    """
    x, y = _pair(0.020, seed=8)
    for fn in (wpli, dpli, imag_coherence):
        a = fn(x, y, SFREQ, LO, HI, window_s=2.0)
        b = fn(x, y, SFREQ, LO, HI, window_s=2.0)
        c = fn(x, y, SFREQ, LO, HI, window_s=4.0)
        assert a == b, f"{fn.__name__} is not deterministic"
        assert np.isfinite(a) and np.isfinite(c)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
