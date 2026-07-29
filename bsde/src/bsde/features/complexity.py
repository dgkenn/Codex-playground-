"""Complexity measures: Lempel-Ziv (LZ76) and permutation entropy (Bandt-Pompe).

CONVENTION, matching `aperiodic.py`: plain numpy, no scipy/sklearn, functions not classes.

`lempel_ziv_complexity` is the classic Kaspar & Schuster (1976) "exhaustive history" implementation of the
Lempel-Ziv (1976) complexity count — the same algorithm used by `antropy`/`nolds` and the one hand-verified
against the two reference sequences below. It operates on a sequence of 0/1 symbols; `lziv` adds the
binarisation and normalisation needed to turn a real-valued signal into a bounded complexity score.
"""
from __future__ import annotations

import math

import numpy as np


def lempel_ziv_complexity(binary_seq) -> int:
    """LZ76 exhaustive-history complexity count of a 0/1 sequence.

    Kaspar & Schuster (1976) algorithm. `binary_seq` is any 0/1 iterable (list, tuple, ndarray).

    Hand-verified ground truth (see tests/test_complexity_features.py):
      '0000'                -> 2   (parses as 0 . 000, i.e. the single symbol then its own repeat)
      '0001101001000101'    -> 6   (parses as 0 . 001 . 10 . 100 . 1000 . 101 -- the Lempel & Ziv 1976 example)
    """
    # A PYTHON LIST, not the ndarray. The algorithm below indexes element-by-element in a Python loop, and
    # every `arr[i]` on an ndarray allocates a numpy scalar. On a 30,000-sample channel that overhead
    # dominated everything else in the pipeline -- the seed set took ~10 s per channel, i.e. ~17 hours for
    # one 98-recording dataset. Converting once up front is a pure constant-factor change: the algorithm,
    # and therefore the hand-verified ground truth below, is untouched.
    s = [int(v) for v in np.asarray(binary_seq).ravel()]
    n = len(s)
    if n == 0:
        return 0
    if n == 1:
        return 1
    i, k, l = 0, 1, 1
    c = 1
    k_max = 1
    while True:
        if s[i + k - 1] == s[l + k - 1]:
            k += 1
            if l + k > n:
                c += 1
                break
        else:
            if k > k_max:
                k_max = k
            i += 1
            if i == l:
                c += 1
                l += k_max
                if l + 1 > n:
                    break
                i = 0
                k = 1
                k_max = 1
            else:
                k = 1
    return int(c)


def binarize(x: np.ndarray, method: str = "median") -> np.ndarray:
    """Threshold a 1-D real signal to a 0/1 int8 array.

    method="median": 1 where x is strictly above the median, else 0.
    method="mean":   1 where x is strictly above the mean, else 0.
    """
    x = np.asarray(x, float)
    if method == "median":
        thr = np.median(x)
    elif method == "mean":
        thr = np.mean(x)
    else:
        raise ValueError(f"unknown method {method!r}")
    return (x > thr).astype(np.int8)


def lziv(x: np.ndarray, method: str = "median") -> float:
    """Normalised Lempel-Ziv complexity of a real-valued 1-D signal.

    Binarises `x` (median or mean threshold), runs LZ76, and divides by the asymptotic complexity of a
    random binary sequence of the same length, `n / log2(n)` (Kaspar & Schuster 1976). A random sequence
    therefore scores ~1.0; a constant or strongly periodic sequence scores near 0.
    """
    x = np.asarray(x, float)
    n = x.size
    if n < 2:
        return float("nan")
    b = binarize(x, method=method)
    c = lempel_ziv_complexity(b)
    denom = n / math.log2(n)
    if denom <= 0:
        return float("nan")
    return float(c / denom)


def permutation_entropy(x: np.ndarray, order: int = 3, delay: int = 1, normalize: bool = True) -> float:
    """Bandt-Pompe permutation entropy.

    Every length-`order` window (stepped by `delay` within the window, one sample at a time across the
    signal) is mapped to its ordinal pattern via `np.argsort`. Shannon entropy (base 2) of the resulting
    pattern distribution, optionally normalised by log2(order!) so the result lies in [0, 1]: ~1 for a
    signal whose amplitude ordering is unpredictable (white noise), ~0 for a signal whose ordinal pattern
    never changes (e.g. a monotonic ramp).
    """
    x = np.asarray(x, float)
    n = x.size
    if order < 2:
        raise ValueError("order must be >= 2")
    n_windows = n - delay * (order - 1)
    if n_windows < 1:
        return float("nan")
    counts: dict = {}
    for i in range(n_windows):
        window = x[i:i + delay * order:delay]
        pattern = tuple(np.argsort(window, kind="quicksort"))
        counts[pattern] = counts.get(pattern, 0) + 1
    total = float(sum(counts.values()))
    p = np.array([v / total for v in counts.values()])
    pe = float(-np.sum(p * np.log2(p)))
    if normalize:
        max_ent = math.log2(math.factorial(order))
        pe = pe / max_ent if max_ent > 0 else float("nan")
    return pe
