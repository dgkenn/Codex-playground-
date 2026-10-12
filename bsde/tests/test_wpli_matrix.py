"""`wpli_matrix` must reproduce `wpli` pair by pair -- rule 23, applied to a fast reimplementation.

`wpli_matrix` exists because E73's Challenge B null was computed on a **10-channel** montage, where a
graph measure has almost no topology to express: on a near-complete 10-node weighted graph, global
efficiency correlated with mean degree at +0.9962. Widening to 62 channels means 1,891 pairs per epoch
instead of 45, which is only affordable vectorised -- and a vectorised estimator that quietly differs from
the tested pairwise one would put the whole successor experiment on an unvalidated instrument.

Every test below compares the two implementations on the SAME input rather than checking the matrix
against a hand-picked constant, because the pairwise function is the thing that has already been tested.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.connectivity import wpli, wpli_matrix


def _pairwise(X, sfreq, lo, hi, **kw):
    C = X.shape[0]
    M = np.full((C, C), np.nan)
    for i in range(C):
        for j in range(C):
            M[i, j] = 0.0 if i == j else wpli(X[i], X[j], sfreq, lo, hi, **kw)
    return M


def _signal(seed=0, C=6, n=2000):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(C, n))
    X[1] = 0.6 * np.roll(X[0], 3) + 0.4 * rng.normal(size=n)      # a genuinely lagged pair
    X[2] = 0.5 * X[0] + 0.5 * rng.normal(size=n)                  # zero-lag: wPLI should stay small
    return X


def test_matrix_reproduces_pairwise_debiased():
    X = _signal(1)
    got = wpli_matrix(X, 1000.0, 8.0, 13.0, window_s=0.5)
    ref = _pairwise(X, 1000.0, 8.0, 13.0, window_s=0.5)
    ok = np.isfinite(got) & np.isfinite(ref)
    assert ok.sum() > 0
    assert np.max(np.abs(got[ok] - ref[ok])) < 1e-12


def test_matrix_reproduces_pairwise_undebiased():
    X = _signal(2)
    got = wpli_matrix(X, 1000.0, 4.0, 8.0, window_s=0.5, debias=False)
    ref = _pairwise(X, 1000.0, 4.0, 8.0, window_s=0.5, debias=False)
    ok = np.isfinite(got) & np.isfinite(ref)
    assert np.max(np.abs(got[ok] - ref[ok])) < 1e-12


def test_matrix_is_symmetric_and_zero_on_the_diagonal():
    """The diagonal must be 0, not 1: a node's phase lag with itself is not connectivity, and a 1 there
    would inflate every strength and clustering coefficient built from the matrix."""
    M = wpli_matrix(_signal(3), 1000.0, 8.0, 13.0, window_s=0.5)
    assert np.allclose(np.diag(M), 0.0)
    ok = np.isfinite(M)
    assert np.max(np.abs(M - M.T)[ok]) < 1e-12


def test_matrix_finds_the_lagged_pair_and_not_the_zero_lag_pair():
    """A test that can fail: channel 1 is a lagged copy of 0, channel 2 an instantaneous mix of it."""
    M = wpli_matrix(_signal(4, C=4, n=6000), 1000.0, 8.0, 13.0, window_s=0.5)
    assert M[0, 1] > M[0, 2], f"lagged {M[0, 1]} should exceed zero-lag {M[0, 2]}"


def test_matrix_refuses_a_signal_shorter_than_one_window():
    M = wpli_matrix(np.zeros((3, 10)), 1000.0, 8.0, 13.0, window_s=0.5)
    assert M.shape == (3, 3) and np.isnan(M[0, 1])


def test_matrix_refuses_a_band_with_no_bins():
    M = wpli_matrix(_signal(5), 1000.0, 8.0, 8.0001, window_s=0.05)
    assert np.isnan(M[0, 1])


def test_matrix_rejects_a_one_dimensional_input():
    with pytest.raises(ValueError):
        wpli_matrix(np.zeros(1000), 1000.0, 8.0, 13.0)


def test_matrix_matches_pairwise_at_a_second_band_and_window():
    X = _signal(6, C=5, n=4000)
    got = wpli_matrix(X, 1000.0, 13.0, 30.0, window_s=1.0, overlap=0.25)
    ref = _pairwise(X, 1000.0, 13.0, 30.0, window_s=1.0, overlap=0.25)
    ok = np.isfinite(got) & np.isfinite(ref)
    assert np.max(np.abs(got[ok] - ref[ok])) < 1e-12
