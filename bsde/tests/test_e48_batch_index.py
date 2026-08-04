"""E48's batch index and its sham gate must both be constructible into failure.

Rule 49, learned from E46 hours earlier: a gate test that only exercises the auxiliary gates is not a
rule-40 test. The PRIMARY is where the claim lives. These build the cohorts on which E48 should say
HARMONISES and the cohorts on which it should say REFUTED, and check it says each.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np

_p = os.path.join(os.path.dirname(__file__), "..", "..", "analysis", "normative_multicohort.py")
_spec = importlib.util.spec_from_file_location("nmc", os.path.abspath(_p))
nmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nmc)


def _rows(n_per=40, cohort_offset=(0.0, 0.0, 0.0), seed=0):
    """Three cohorts. `cohort_offset` shifts each cohort's APERIODIC OFFSET -- i.e. a pure amplifier/gain
    style batch effect that lives entirely in the aperiodic background and not in the oscillation."""
    rng = np.random.default_rng(seed)
    out = []
    for ci, off in enumerate(cohort_offset):
        for i in range(n_per):
            age = float(rng.uniform(20, 70))
            expo = 1.5 + rng.normal(0, 0.15)
            offset = 1.0 + off + rng.normal(0, 0.1)
            # true alpha bump above the background, identical in distribution across cohorts
            bump = 0.8 + rng.normal(0, 0.2)
            m = nmc._model_band(offset, expo, 8.0, 13.0)
            out.append({"_cohort": f"c{ci}", "_subject": f"c{ci}/s{i}", "age": str(age),
                        "sex": "M" if i % 2 else "F", "group": "",
                        "aperiodic_offset": str(offset), "whole_head_exponent": str(expo),
                        "abs_alpha": str(np.log10(m) + bump),
                        "rel_alpha": str(0.3 + rng.normal(0, 0.05))})
    return out


def test_batch_index_is_large_when_cohorts_are_offset_and_small_when_they_are_not():
    coh = ["c0", "c1", "c2"]
    same = _rows(cohort_offset=(0.0, 0.0, 0.0), seed=1)
    diff = _rows(cohort_offset=(0.0, 0.6, 1.2), seed=1)
    b_same = nmc._batch_index(same, [float(r["abs_alpha"]) for r in same], coh)
    b_diff = nmc._batch_index(diff, [float(r["abs_alpha"]) for r in diff], coh)
    assert b_diff > b_same * 3, (b_same, b_diff)


def test_correction_removes_a_batch_effect_that_lives_in_the_aperiodic_background():
    """The case E48 should call HARMONISES: the cohorts differ ONLY in aperiodic offset, and the alpha
    bump above background is identical. Correction must collapse the batch index."""
    coh = ["c0", "c1", "c2"]
    rows = _rows(cohort_offset=(0.0, 0.6, 1.2), seed=2)
    b_abs = nmc._batch_index(rows, [float(r["abs_alpha"]) for r in rows], coh)
    b_res = nmc._batch_index(rows, nmc._corrected(rows, "alpha"), coh)
    assert b_res < b_abs, (b_abs, b_res)


def test_correction_does_NOT_help_when_the_batch_effect_is_in_the_oscillation():
    """The case E48 must call REFUTED. If cohorts differ in the alpha bump itself rather than in the
    background, subtracting the background cannot help -- and a statistic that 'helped' here would be
    responding to something other than harmonisation."""
    coh = ["c0", "c1", "c2"]
    rng = np.random.default_rng(5)
    rows = []
    for ci, bump_shift in enumerate((0.0, 0.6, 1.2)):
        for i in range(40):
            expo = 1.5 + rng.normal(0, 0.15)
            offset = 1.0 + rng.normal(0, 0.1)
            m = nmc._model_band(offset, expo, 8.0, 13.0)
            rows.append({"_cohort": f"c{ci}", "_subject": f"c{ci}/s{i}",
                         "age": str(float(rng.uniform(20, 70))), "sex": "M" if i % 2 else "F",
                         "group": "", "aperiodic_offset": str(offset),
                         "whole_head_exponent": str(expo),
                         "abs_alpha": str(np.log10(m) + 0.8 + bump_shift + rng.normal(0, 0.2))})
    b_abs = nmc._batch_index(rows, [float(r["abs_alpha"]) for r in rows], coh)
    b_res = nmc._batch_index(rows, nmc._corrected(rows, "alpha"), coh)
    assert b_res > b_abs * 0.6, (b_abs, b_res)


def test_a_WITHIN_cohort_sham_is_the_wrong_gate_and_this_records_why():
    """The first version of the sham drew donors WITHIN cohort and the real correction LOST to it.

    Two things were wrong and both are worth keeping visible. (1) Everyone in a cohort shares that cohort's
    background, so a within-cohort donor removes the batch effect just as well -- the gate tested nothing.
    (2) With a per-arm denominator, the sham won by INFLATING its own within-cohort SD with the noise of
    using someone else's fit, because batch = between/within. A gate that rewards adding noise is worse
    than no gate. This test pins the diagnosis: with a per-arm denominator the within-cohort sham scores
    LOWER (looks better) than the real correction."""
    coh = ["c0", "c1", "c2"]
    rows = _rows(cohort_offset=(0.0, 0.6, 1.2), seed=3)
    rng = np.random.default_rng(0)
    perm = np.arange(len(rows))
    for c in coh:
        idx = np.flatnonzero(np.array([r["_cohort"] == c for r in rows]))
        perm[idx] = rng.permutation(idx)
    b_res = nmc._batch_index(rows, nmc._corrected(rows, "alpha"), coh)
    b_sham = nmc._batch_index(rows, nmc._corrected(rows, "alpha", sham_perm=perm), coh)
    assert b_sham < b_res, "the historical defect: within-cohort sham beats the real correction"


def test_cross_cohort_sham_with_a_fixed_denominator_is_a_gate_that_works():
    """The corrected gate. Donors come from a DIFFERENT cohort, so the borrowed curve carries no
    information about this cohort's background; and every arm shares one denominator computed from the
    uncorrected measure, so no arm can win by adding noise. The real correction must now beat the sham."""
    coh = ["c0", "c1", "c2"]
    rows = _rows(cohort_offset=(0.0, 0.6, 1.2), seed=3)
    rng = np.random.default_rng(0)
    coh_of = np.array([r["_cohort"] for r in rows])
    perm = np.arange(len(rows))
    for c in coh:
        idx = np.flatnonzero(coh_of == c)
        other = np.flatnonzero(coh_of != c)
        perm[idx] = rng.choice(other, size=idx.size, replace=True)
    abs_v = [float(r["abs_alpha"]) for r in rows]
    den = nmc._within_spread(rows, abs_v, coh)
    b_res = nmc._batch_index(rows, nmc._corrected(rows, "alpha"), coh, denom=den)
    b_sham = nmc._batch_index(rows, nmc._corrected(rows, "alpha", sham_perm=perm), coh, denom=den)
    assert b_res < b_sham, f"real correction {b_res} must beat cross-cohort sham {b_sham}"


def test_fixed_denominator_cannot_be_gamed_by_adding_noise():
    """Directly: adding pure noise to a measure must not IMPROVE its batch index."""
    coh = ["c0", "c1", "c2"]
    rows = _rows(cohort_offset=(0.0, 0.6, 1.2), seed=4)
    abs_v = np.array([float(r["abs_alpha"]) for r in rows])
    den = nmc._within_spread(rows, abs_v, coh)
    clean = nmc._batch_index(rows, abs_v, coh, denom=den)
    noisy = nmc._batch_index(rows, abs_v + np.random.default_rng(1).normal(0, 0.5, len(rows)),
                             coh, denom=den)
    assert noisy >= clean * 0.9, (clean, noisy)
