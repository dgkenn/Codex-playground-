"""Frozen UCE v1: constant integrity, montage handling, and the PCA algebra that defines what it is.

The last two tests are unusual for a unit-test file and are here deliberately. They encode, as executable
assertions, the claim in RESEARCH_STRATEGY.md §0 that the published weights and the "96.8 % variance
explained" figure are consequences of two-variable PCA algebra rather than empirical findings. If anyone later
disputes that section, these tests are the demonstration.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.uce_v1 import (W_FRONTAL, W_POSTERIOR, UCE_V1_VERSION, group_indices,
                               regional_exponents, uce_v1_from_z, uce_v1_with_baseline)


def test_frozen_constants_are_exact():
    """The brief freezes these. An accidental edit must fail the suite, not silently change every result."""
    assert W_FRONTAL == 0.696
    assert W_POSTERIOR == 0.718
    assert UCE_V1_VERSION == "uce_v1.0-frozen"


def test_weights_are_a_unit_vector_with_mean_at_one_over_sqrt2():
    """Unit-norm to the precision the weights are quoted at (3 decimals): ||w|| = 0.99997.

    Tolerance is 1e-4 rather than 1e-6 because 0.696 and 0.718 are rounded values; demanding exactness
    would be testing the rounding, not the claim. The claim is that they lie on the unit circle at
    45 degrees, which is what PC1 of two standardized variables always is.
    """
    w = np.array([W_FRONTAL, W_POSTERIOR])
    assert abs(np.linalg.norm(w) - 1.0) < 1e-4, f"||w|| = {np.linalg.norm(w):.6f}"
    assert abs(w.mean() - 1 / np.sqrt(2)) < 1e-3


def test_channel_grouping_handles_case_and_ref_suffixes():
    g = group_indices(["Fp1", "F3-REF", "C3", "P4", "o1", "T5", "EKG", "Cz"])
    assert 0 in g["frontal"] and 1 in g["frontal"]
    assert 3 in g["posterior"] and 4 in g["posterior"] and 5 in g["posterior"]
    # C3, Cz and EKG belong to neither group and must not be silently absorbed
    assert 2 not in g["frontal"] + g["posterior"]
    assert 6 not in g["frontal"] + g["posterior"]
    assert 7 not in g["frontal"] + g["posterior"]


def test_missing_region_yields_nan_not_a_substitute():
    """A montage with no posterior channels cannot yield UCE v1; it must say so."""
    out = regional_exponents([1.0, 1.2, 1.1], ["Fp1", "F3", "Fz"])
    assert np.isfinite(out["frontal"])
    assert np.isnan(out["posterior"])
    assert out["n_posterior"] == 0


def test_regional_exponents_length_mismatch_raises():
    with pytest.raises(ValueError):
        regional_exponents([1.0, 2.0], ["Fp1", "F3", "Pz"])


def test_equation_matches_hand_computation():
    got = uce_v1_from_z(1.0, -1.0)
    assert abs(float(got) - (0.696 - 0.718)) < 1e-12


# --------------------------------------------------------------------------------------------------------
# The algebra behind RESEARCH_STRATEGY.md §0
# --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("r", [0.05, 0.3, 0.6, 0.85, 0.936, 0.99])
def test_pc1_loadings_are_always_equal_for_two_standardized_variables(r):
    """PC1 of two z-scored variables has equal loadings for EVERY r -- so the published weights are not a
    finding about frontal vs posterior cortex."""
    rng = np.random.default_rng(0)
    n = 200_000
    a = rng.normal(size=n)
    b = r * a + np.sqrt(max(1 - r ** 2, 0.0)) * rng.normal(size=n)
    X = np.column_stack([(a - a.mean()) / a.std(), (b - b.mean()) / b.std()])
    C = np.cov(X, rowvar=False)
    vals, vecs = np.linalg.eigh(C)
    pc1 = vecs[:, np.argmax(vals)]
    assert abs(abs(pc1[0]) - 1 / np.sqrt(2)) < 0.01, f"r={r}: loadings {pc1}"
    assert abs(abs(pc1[1]) - 1 / np.sqrt(2)) < 0.01, f"r={r}: loadings {pc1}"


@pytest.mark.parametrize("r", [0.3, 0.6, 0.936])
def test_variance_explained_is_exactly_one_plus_r_over_two(r):
    """So '96.8 % explained' is a restatement of r = 0.936, not independent evidence."""
    rng = np.random.default_rng(1)
    n = 400_000
    a = rng.normal(size=n)
    b = r * a + np.sqrt(max(1 - r ** 2, 0.0)) * rng.normal(size=n)
    X = np.column_stack([(a - a.mean()) / a.std(), (b - b.mean()) / b.std()])
    vals = np.linalg.eigvalsh(np.cov(X, rowvar=False))
    ve = vals.max() / vals.sum()
    assert abs(ve - (1 + r) / 2) < 0.01, f"r={r}: VE {ve:.4f} vs predicted {(1+r)/2:.4f}"


def test_with_baseline_reports_the_redundancy_diagnostics():
    """The API must hand back the one-feature baseline and the frontal/posterior correlation together with
    the score, so the comparison required by strategy R-01 cannot be quietly skipped."""
    rng = np.random.default_rng(2)
    fr = rng.normal(size=300)
    po = 0.936 * fr + np.sqrt(1 - 0.936 ** 2) * rng.normal(size=300)
    wh = (fr + po) / 2
    out = uce_v1_with_baseline(fr, po, wh)
    assert "uce_v1" in out and "baseline_whole_head_z" in out
    assert abs(out["r_frontal_posterior"] - 0.936) < 0.03
    assert abs(out["implied_pc1_variance_explained"] - 0.968) < 0.02
    # And with r this high, UCE v1 must be nearly identical to the one-feature baseline.
    assert abs(np.corrcoef(out["uce_v1"], out["baseline_whole_head_z"])[0, 1]) > 0.99
