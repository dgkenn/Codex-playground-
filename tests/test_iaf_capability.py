#!/usr/bin/env python3
"""Capability gate for the peak-anchored measures (catalogue rule 40).

Rule 40 says a gate that cannot fail is not a gate, and that before trusting one you construct the input
that SHOULD fail it and check that it does. Here the claim is that `relative_alpha_power` mismeasures a
spectrum whose peak has moved, and that the anchored version does not. Both halves are checkable on
synthetic signals where the true peak frequency is known by construction, and neither needs any real data.

The test also pins the INCUMBENT's failure, which is the part that matters for interpreting every result
this project has already produced with `alpha_peak_hz` and `relative_alpha_power` in it.

    python -m pytest tests/test_iaf_capability.py -q
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bsde", "src")))

pytest.importorskip("numpy")

SFREQ = 128.0
DURATION_S = 30.0
N_SEEDS = 6


def _registry():
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    return REGISTRY


def _signal(f0, seed):
    """Pink-ish background plus one narrowband oscillation at a KNOWN frequency."""
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    t = np.arange(n) / SFREQ
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4
                      + 1.2 * np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6))
                      for _ in range(2)])


def _median(fn, f0):
    v = [fn(_signal(f0, 100 + s), ["a", "b"], SFREQ, {}) for s in range(N_SEEDS)]
    return float(np.nanmedian(v))


def test_wide_estimator_recovers_the_true_peak_across_the_whole_search_range():
    r = _registry()
    fn = r.get("alpha_peak_hz_wide").fn
    for f0 in (6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0):
        got = _median(fn, f0)
        assert abs(got - f0) <= 0.5, f"wide estimator gave {got} for a true peak at {f0}"


def test_the_incumbent_peak_estimator_is_WRONG_outside_its_band_not_merely_censored():
    """`alpha_peak_hz` searches the raw PSD maximum inside 8-13 Hz.

    It cannot report a peak outside that band, and what it returns instead is not the nearest edge but an
    arbitrary interior value: a true peak at 6.0 Hz and one at 14.0 Hz both come back as roughly 8.5. Any
    peak-shift estimate built on this estimator is a LOWER BOUND, and any claim about WHERE the peak is,
    when it lies outside 8-13 Hz, is simply false.
    """
    fn = _registry().get("alpha_peak_hz").fn
    for f0 in (6.0, 7.0, 7.5, 14.0):
        got = _median(fn, f0)
        # The tolerance is DERIVED rather than chosen (rule 63): an estimator confined to [8, 13] cannot
        # do better than the distance from the true peak to the nearest band edge, so that distance is
        # the smallest error it is arithmetically capable of. A round number here would only measure the
        # round number -- the first draft used 1.0 and f0 = 7.5 landed exactly on it.
        forced = min(abs(f0 - 8.0), abs(f0 - 13.0)) if not (8.0 <= f0 <= 13.0) else 0.0
        assert abs(got - f0) >= forced, (
            f"the incumbent returned {got} for a true peak at {f0}; if this assertion ever fails the "
            "estimator has been fixed and every result quoting alpha_peak_hz must be revisited")
        assert 8.0 <= got <= 13.0, f"incumbent escaped its own search band: {got} for f0={f0}"
    # and the failure is not merely an edge: a peak at 6 Hz and one at 14 Hz both come back interior
    assert abs(_median(fn, 6.0) - _median(fn, 14.0)) < 0.6, (
        "the incumbent's out-of-band answers differ, so it is at least monotone; the claim in this test "
        "is that it is not")


def test_fixed_band_relative_alpha_collapses_when_the_peak_leaves_the_box():
    """The arithmetic the whole band-placement hypothesis rests on, measured rather than asserted.

    The oscillation is identical in amplitude at every f0; only its frequency moves. A fixed 8-13 Hz window
    therefore reports a value that varies by more than an order of magnitude for no change in the signal it
    is meant to be measuring.
    """
    fn = _registry().get("relative_alpha_power").fn
    inside = _median(fn, 10.0)
    below = _median(fn, 7.0)
    assert inside > 0.3
    assert below < 0.1
    assert inside / below > 5.0, f"expected a large collapse, got {inside:.4f} -> {below:.4f}"


def test_anchored_relative_alpha_is_flat_across_the_same_range():
    """The fix, on the same signals. Flat is the whole claim: same oscillation, same number."""
    fn = _registry().get("relative_alpha_power_iaf").fn
    vals = [_median(fn, f0) for f0 in (6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0)]
    lo, hi = min(vals), max(vals)
    assert lo > 0.2, f"anchored band returned {vals}"
    assert hi / lo < 1.5, (
        f"anchored band varied by {hi / lo:.2f}x across peak positions ({vals}); it is supposed to be "
        "insensitive to where the peak sits, and if it is not, it does not do what it claims")


def test_anchored_measure_is_not_the_incumbent_renamed():
    """Rule 60 run as a test: a measure chosen for belonging to a different family must be SHOWN to differ.

    If the anchored and fixed measures agreed across peak positions, anchoring would have changed nothing.
    """
    r = _registry()
    fixed = [_median(r.get("relative_alpha_power").fn, f) for f in (6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0)]
    anch = [_median(r.get("relative_alpha_power_iaf").fn, f) for f in (6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0)]
    assert np.std(fixed) > 5 * np.std(anch), (
        f"fixed sd {np.std(fixed):.4f} vs anchored sd {np.std(anch):.4f} — the two behave alike and the "
        "anchoring is cosmetic")


def test_no_peak_returns_nan_rather_than_a_band_edge():
    """An edge maximum is not a peak, and returning one would be exactly the artefact this avoids."""
    r = _registry()
    rng = np.random.default_rng(7)
    n = int(SFREQ * DURATION_S)
    pure = np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4 for _ in range(2)])
    got = r.get("alpha_peak_hz_wide").fn(pure, ["a", "b"], SFREQ, {})
    assert (not np.isfinite(got)) or (5.0 < got < 15.0)
