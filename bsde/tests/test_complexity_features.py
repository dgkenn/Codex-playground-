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


# =========================================================================================================
# lempel_ziv_complexity_fast must be BIT-IDENTICAL to the reference, not merely close.
#
# Added 2026-07-31. The fast path exists because the reference is O(n^2/log n) and costs ~4-13 s on a
# 184 s / 250 Hz channel, which put a 4,864-recording extraction out of reach. A faster estimator that
# returned slightly different numbers would silently break comparability with every LZ result already in
# the ledger, so the acceptance test is exact equality, and the first version of the fast path FAILED it
# on 121,410 of 131,070 sequences (it read a phrase as the longest match rather than the longest match
# plus one new symbol). Error-catalogue rules 20 and 23.
# =========================================================================================================

def test_fast_lz_matches_reference_on_ground_truth():
    from bsde.features.complexity import lempel_ziv_complexity_fast as fast
    assert fast([0, 0, 0, 0]) == 2
    assert fast([int(c) for c in "0001101001000101"]) == 6


def test_fast_lz_matches_reference_exhaustively_to_length_14():
    from bsde.features.complexity import (lempel_ziv_complexity as ref,
                                          lempel_ziv_complexity_fast as fast)
    for n in range(1, 15):
        for v in range(1 << n):
            b = [(v >> i) & 1 for i in range(n)]
            assert ref(b) == fast(b), (n, v, ref(b), fast(b))


def test_fast_lz_matches_reference_on_structured_and_random_sequences():
    import numpy as np
    from bsde.features.complexity import (lempel_ziv_complexity as ref,
                                          lempel_ziv_complexity_fast as fast)
    rng = np.random.default_rng(7)
    for t in range(60):
        n = int(rng.integers(2, 2000))
        p = float(rng.uniform(0.05, 0.95))
        b = (rng.random(n) < p).astype(np.int8)
        if t % 4 == 1:                              # periodic: the low-complexity extreme
            b = np.tile(b[:max(1, n // 10)], 10)[:n]
        if t % 4 == 2:                              # long-memory random walk sign
            b = (np.cumsum(rng.standard_normal(n)) > 0).astype(np.int8)
        if t % 4 == 3:                              # constant: the degenerate case
            b = np.zeros(n, dtype=np.int8)
        assert ref(b) == fast(b), (n, p, t)


def test_fast_lz_is_actually_faster_on_a_realistic_channel():
    """A guard against the fast path silently regressing to the reference's complexity class."""
    import time
    import numpy as np
    from bsde.features.complexity import (lempel_ziv_complexity as ref,
                                          lempel_ziv_complexity_fast as fast, binarize)
    b = binarize(np.cumsum(np.random.default_rng(0).standard_normal(20000)))
    t0 = time.time(); cf = fast(b); tf = time.time() - t0
    t0 = time.time(); cr = ref(b);  tr = time.time() - t0
    assert cr == cf
    assert tf * 10 < tr, f"fast path only {tr / max(tf, 1e-9):.1f}x faster; expected >10x"
