"""Tests for `features/quality.py`.

The behaviours worth pinning are the ones that were wrong in the pipeline before this module existed, and
the one that would be worst to get wrong now: judging amplitude on data whose units are not microvolts.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bsde.features.quality import (MAX_SD_UV, MIN_SD_UV, channel_quality,   # noqa: E402
                                   summarise)


def _sig(rng, sd, n=3000):
    return rng.normal(0.0, sd, n)


def test_keeps_ordinary_eeg_amplitudes():
    rng = np.random.default_rng(0)
    x = np.vstack([_sig(rng, s) for s in (10.0, 25.0, 40.0, 90.0)])
    q = channel_quality(x, units="microvolts")
    assert q["n_kept"] == 4
    assert q["frac_kept"] == 1.0
    assert all(r == "" for r in q["reasons"])


def test_rejects_the_ds004541_pattern_where_the_median_channel_is_bad():
    """The case a robust aggregator cannot handle: the BAD channels are the majority.

    Two good channels and five enormous ones, which is the shape measured on ds004541 (23 of 62 plausible).
    A per-frequency median across channels would have sat inside the bad population; rejection does not.
    """
    rng = np.random.default_rng(1)
    good = [_sig(rng, 20.0), _sig(rng, 35.0)]
    bad = [_sig(rng, s) for s in (1600.0, 4.2e4, 6.6e4, 9.0e4, 1.5e5)]
    q = channel_quality(np.vstack(good + bad), units="microvolts")
    assert q["n_kept"] == 2
    assert q["reasons"][2:] == ["amplitude"] * 5
    assert q["below_min_kept_fraction"] is True


def test_flat_channel_is_rejected_without_units():
    """A constant is not a measurement in any unit, so this test runs even when amplitude cannot."""
    rng = np.random.default_rng(2)
    x = np.vstack([_sig(rng, 20.0), np.zeros(3000)])
    q = channel_quality(x, units="uncalibrated")
    assert q["units_judged"] is False
    assert q["reasons"] == ["", "flat"]
    assert q["n_kept"] == 1


def test_amplitude_is_not_judged_when_units_are_not_microvolts():
    """HBN declares `uncalibrated`. Rejecting its channels on a microvolt band would be nonsense, and
    silently keeping them while reporting a clean pass would hide that the test never ran."""
    rng = np.random.default_rng(3)
    x = np.vstack([_sig(rng, 1e-5), _sig(rng, 1e4)])       # both wildly outside the band, in µV terms
    q = channel_quality(x, units="uncalibrated")
    assert q["units_judged"] is False
    assert q["n_kept"] == 2
    assert "amplitude NOT tested" in summarise(q)


def test_nonfinite_channel_is_rejected_before_amplitude():
    rng = np.random.default_rng(4)
    ch = _sig(rng, 20.0)
    ch[: int(0.2 * ch.size)] = np.nan
    q = channel_quality(np.vstack([_sig(rng, 20.0), ch]), units="microvolts")
    assert q["reasons"] == ["", "nonfinite"]


def test_a_small_nonfinite_run_is_tolerated():
    rng = np.random.default_rng(5)
    ch = _sig(rng, 20.0)
    ch[:30] = np.nan                                        # 1 % of 3000 samples
    q = channel_quality(np.vstack([ch]), units="microvolts")
    assert q["n_kept"] == 1


@pytest.mark.parametrize("sd,expected", [(MIN_SD_UV - 0.1, 0), (MIN_SD_UV + 0.1, 1),
                                         (MAX_SD_UV - 0.1, 1), (MAX_SD_UV + 0.1, 0)])
def test_band_edges_are_inclusive_and_are_not_knife_edge_on_a_quantised_statistic(sd, expected):
    """Deliberately probed just inside and just outside. Three separate results in this project have turned
    on a threshold landing exactly on a quantised value, so the edges get an explicit test."""
    rng = np.random.default_rng(6)
    x = rng.normal(0.0, 1.0, 200000)
    x = (x - x.mean()) / x.std() * sd                        # standard deviation is exactly `sd`
    q = channel_quality(x[None, :], units="microvolts")
    assert q["n_kept"] == expected


def test_single_channel_input_is_accepted_as_1d():
    rng = np.random.default_rng(7)
    q = channel_quality(_sig(rng, 18.0), units="microvolts")
    assert q["n_channels"] == 1 and q["n_kept"] == 1
