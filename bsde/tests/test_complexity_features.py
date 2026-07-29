"""Ground-truth checks for bsde.features.complexity.

LZ76 complexity is checked against sequences whose parse is derived BY HAND from the Lempel-Ziv (1976)
exhaustive-history definition (see comments below and in complexity.py). Everything else is checked
against a known qualitative or quantitative bound (white noise vs. constant vs. monotonic ramp).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.complexity import (
    lempel_ziv_complexity, lziv, permutation_entropy, binarize,
)


# ---------------------------------------------------------------------------
# LZ76 exhaustive-history complexity: hand-derived reference values.
#
# Parsing rule: scan left to right; each new "phrase" is the shortest substring, starting right after the
# previous phrase boundary, that has not already occurred as a substring starting at or before the
# previous boundary (the "exhaustive history"). The complexity is the number of phrases produced.
# ---------------------------------------------------------------------------

def test_lz76_all_zeros_has_complexity_two():
    # '0000': phrase 1 = '0' (the very first symbol is always new).
    # Phrase 2 = '000' (positions 1-3): the whole remainder can be copied because prefix '00' already
    # occurred (as a substring of the history "0") extended one more time is still reproducible from the
    # history -- so no further phrase boundary is needed until the string ends.
    # Total phrases = 2.
    s = [0, 0, 0, 0]
    assert lempel_ziv_complexity(s) == 2


def test_lz76_all_zeros_various_lengths():
    for n in (2, 8, 16, 100):
        assert lempel_ziv_complexity([0] * n) == 2


def test_lz76_lempel_ziv_1976_paper_example():
    # '0001101001000101' from Lempel & Ziv (1976), hand-parsed as:
    #   0 . 001 . 10 . 100 . 1000 . 101
    # giving 6 phrases. Verified by hand-tracing the Kaspar-Schuster algorithm step by step (see the
    # derivation kept in the implementation's docstring) -- if the code disagrees with this, the code is
    # wrong, not this expected value.
    s = [int(c) for c in "0001101001000101"]
    assert lempel_ziv_complexity(s) == 6


def test_lz76_alternating_is_low_complexity():
    # A perfectly periodic sequence should have much lower complexity than its length.
    s = [0, 1] * 50
    c = lempel_ziv_complexity(s)
    assert c < 10


def test_lz76_accepts_various_iterable_types():
    s = "0001101001000101"
    as_list = [int(c) for c in s]
    as_array = np.array(as_list)
    assert lempel_ziv_complexity(as_list) == lempel_ziv_complexity(as_array) == 6


# ---------------------------------------------------------------------------
# binarize
# ---------------------------------------------------------------------------

def test_binarize_median_splits_around_the_median():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = binarize(x, method="median")
    assert b.dtype == np.int8
    # median is 3.0; values strictly greater than 3.0 are 1
    assert list(b) == [0, 0, 0, 1, 1]


def test_binarize_mean():
    x = np.array([0.0, 0.0, 0.0, 10.0])  # mean = 2.5
    b = binarize(x, method="mean")
    assert list(b) == [0, 0, 0, 1]


# ---------------------------------------------------------------------------
# lziv: normalised complexity of a real signal
# ---------------------------------------------------------------------------

def test_lziv_constant_signal_is_near_zero():
    x = np.ones(2048)
    assert lziv(x) < 0.1


def test_lziv_white_noise_is_near_one():
    rng = np.random.default_rng(42)
    x = rng.normal(size=4096)
    got = lziv(x)
    assert 0.8 < got < 1.3, f"got {got}"


def test_lziv_constant_much_lower_than_white_noise():
    rng = np.random.default_rng(43)
    const = np.ones(4096)
    noise = rng.normal(size=4096)
    assert lziv(const) < lziv(noise) / 4


# ---------------------------------------------------------------------------
# permutation_entropy
# ---------------------------------------------------------------------------

def test_permutation_entropy_white_noise_near_one():
    rng = np.random.default_rng(1)
    x = rng.normal(size=5000)
    got = permutation_entropy(x, order=3, delay=1, normalize=True)
    assert got > 0.95, f"got {got}"


def test_permutation_entropy_monotonic_ramp_near_zero():
    x = np.arange(5000, dtype=float)
    got = permutation_entropy(x, order=3, delay=1, normalize=True)
    assert got < 0.05, f"got {got}"


def test_permutation_entropy_constant_signal_is_zero():
    # every window has a tie -> argsort still returns a single deterministic pattern for a constant array,
    # so entropy must be exactly 0 (only one pattern ever appears).
    x = np.zeros(1000)
    got = permutation_entropy(x, order=3, delay=1, normalize=True)
    assert got == pytest.approx(0.0, abs=1e-9)


def test_permutation_entropy_unnormalized_matches_normalized_times_log2_factorial():
    import math
    rng = np.random.default_rng(2)
    x = rng.normal(size=2000)
    raw = permutation_entropy(x, order=3, delay=1, normalize=False)
    norm = permutation_entropy(x, order=3, delay=1, normalize=True)
    assert raw == pytest.approx(norm * math.log2(math.factorial(3)), rel=1e-9)
