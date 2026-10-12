"""Tests for verifier layer 2's multiplicity correction.

The behaviours pinned here are the ones that would make the correction useless rather than merely wrong: an
adjusted p smaller than its raw p, a step-down that is not monotone, and — the one this module exists for —
a Westfall-Young null built with per-candidate relabellings, which silently degenerates to Bonferroni while
still returning plausible numbers.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bsde.verifier.multiplicity import (benjamini_hochberg, holm, report,        # noqa: E402
                                        westfall_young_maxt)


def test_holm_matches_the_hand_computed_case():
    p = [0.01, 0.02, 0.03]
    adj = holm(p, ["a", "b", "c"])
    assert adj["a"] == pytest.approx(0.03)          # 3 * 0.01
    assert adj["b"] == pytest.approx(0.04)          # 2 * 0.02
    assert adj["c"] == pytest.approx(0.04)          # 1 * 0.03, raised to the running max


def test_bh_matches_the_hand_computed_case():
    p = [0.01, 0.02, 0.03]
    adj = benjamini_hochberg(p, ["a", "b", "c"])
    assert adj["c"] == pytest.approx(0.03)          # 0.03 * 3/3
    assert adj["b"] == pytest.approx(0.03)          # 0.02 * 3/2 = 0.03
    assert adj["a"] == pytest.approx(0.03)          # 0.01 * 3/1 = 0.03


def test_no_adjusted_p_is_ever_below_its_raw_p():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 25)
    names = [f"c{i}" for i in range(25)]
    for adj in (holm(p, names), benjamini_hochberg(p, names)):
        for i, k in enumerate(names):
            assert adj[k] >= p[i] - 1e-12, f"{k}: adjusted {adj[k]} < raw {p[i]}"
            assert adj[k] <= 1.0


def test_both_procedures_are_monotone_in_the_raw_ordering():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 20)
    names = [f"c{i}" for i in range(20)]
    order = np.argsort(p)
    for adj in (holm(p, names), benjamini_hochberg(p, names)):
        seq = [adj[names[i]] for i in order]
        assert all(seq[i] <= seq[i + 1] + 1e-12 for i in range(len(seq) - 1))


def _null_matrix(n_perm, n_cand, rho, rng):
    """Permutation nulls with a controllable correlation between candidates.

    `rho = 1` is the fully-redundant case this project actually has (E01 measured 0.9952 between two of
    them); `rho = 0` is the independent case.
    """
    shared = rng.normal(size=(n_perm, 1))
    own = rng.normal(size=(n_perm, n_cand))
    return np.abs(rho * shared + np.sqrt(max(0.0, 1 - rho ** 2)) * own)


def test_westfall_young_sees_correlation_where_bonferroni_cannot():
    """The design decision, made checkable: 18 near-identical candidates must not be priced as 18 tests."""
    rng = np.random.default_rng(2)
    n_cand = 18
    corr = _null_matrix(4000, n_cand, 0.99, rng)
    indep = _null_matrix(4000, n_cand, 0.0, rng)
    obs = np.full(n_cand, 2.5)
    wy_corr = westfall_young_maxt(obs, corr)
    wy_indep = westfall_young_maxt(obs, indep)
    assert wy_corr["effective_tests"] < wy_indep["effective_tests"]
    assert wy_corr["effective_tests"] < 6.0, wy_corr["effective_tests"]
    assert wy_indep["effective_tests"] > 10.0, wy_indep["effective_tests"]


def test_westfall_young_adjusted_never_below_raw_and_is_monotone():
    rng = np.random.default_rng(3)
    null = _null_matrix(2000, 10, 0.5, rng)
    obs = rng.uniform(1.0, 3.0, 10)
    wy = westfall_young_maxt(obs, null)
    names = list(wy["adjusted"])
    for k in names:
        assert wy["adjusted"][k] >= wy["raw"][k] - 1e-12
    order = sorted(names, key=lambda k: -obs[int(k)])
    seq = [wy["adjusted"][k] for k in order]
    assert all(seq[i] <= seq[i + 1] + 1e-12 for i in range(len(seq) - 1))


def test_a_null_matrix_of_the_wrong_width_is_refused():
    with pytest.raises(ValueError):
        westfall_young_maxt([1.0, 2.0], np.zeros((100, 3)))


def test_report_says_so_when_nothing_can_be_corrected():
    """Absence has to be visible. A missing correction that prints nothing reads as a correction that
    passed — the same failure mode as a silently-empty filter (rule 5)."""
    lines = report({"a": 1.0, "b": 2.0})
    assert any("NOTHING is corrected" in ln for ln in lines)


def test_report_prints_the_family_size_first():
    lines = report({"a": 0.9, "b": 0.8}, pvalues={"a": 0.01, "b": 0.4})
    assert "2 candidates in this family" in lines[0]
    assert any("Holm (FWER)" in ln for ln in lines)
