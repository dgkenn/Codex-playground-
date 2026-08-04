"""THE PRIMARY ACCEPTANCE TEST FOR THE ENGINE.

A verifier that never rejects is worthless, and a verifier that rejects everything is worse than worthless
because it looks rigorous. This file plants confounds with known structure and asserts that the engine
rejects each one FOR THE RIGHT REASON, and — equally important — that a clean, genuinely predictive candidate
is NOT rejected.

The four planted cases:

  1. PURE SITE EFFECT     the candidate is a site indicator plus noise; the outcome rate differs by site.
                          Nothing about the brain is being measured. Must REJECT via `probe:site`.
  2. PURE EMG             the candidate is the EMG index plus noise; EMG is associated with the outcome.
                          Must REJECT via `probe:emg_index`.
  3. LABEL LEAKAGE        the candidate is the outcome plus a little noise. Must REJECT via `label_leakage`.
  4. DIRECTION INVERSION  a real signal in dataset A that inverts in dataset B. Must not be reported as
                          surviving; the per-dataset breakdown must show the inversion.

And two cases that must NOT be rejected:

  5. CLEAN SIGNAL         a genuine effect, correlated with age but surviving age strata. Age is a nuisance
                          the candidate tracks, so clause 1 of the confound rule fires — and clause 2 does
                          not. The engine must let it through. This is the test that stops the verifier from
                          being a machine that says no.
  6. BROKEN HARNESS       when the permutation null is not centred at chance, the verdict must be
                          INDETERMINATE, never a clean-looking negative (error-catalogue rule 31).

Each case fixes its own seed and is constructed so the ground truth is known by construction, not by
inspecting the output afterwards.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.registry import Candidate
from bsde.verifier.engine import Cohort, verify, stratified_auc, _strata_of
from bsde.verifier.report import REJECT, SURVIVE, REVISE, INDETERMINATE, INCOMPLETE, FAIL, PASS


def _cand(name="planted", complexity=3, requires=("computational", "statistical", "adversarial")):
    """A minimal, valid declaration. Cross-domain is deliberately NOT required for the single-dataset
    cases, so that INCOMPLETE from an unrunnable layer cannot be mistaken for a real rejection."""
    return Candidate(
        name=name, version="1.0", fn=lambda *a, **k: 0.0,
        interpretation="a planted quantity used to test the verifier, with no physiological claim",
        predictions={"outcome": "higher"},
        failure_conditions=["fails a confound probe", "does not beat the trivial baseline"],
        requires=requires, complexity=complexity)


def _computational_pass():
    from bsde.verifier.report import Evidence
    return [Evidence("synthetic_ground_truth", "computational", PASS,
                     "stand-in for the layer-1 synthetic recovery tests, which pass in this suite")]


def _reasons(rep):
    return " ".join(rep.verdict_reasons).lower()


def _ev(rep, check):
    hits = [e for e in rep.evidence if e.check == check]
    assert hits, f"no evidence named {check!r}; have {[e.check for e in rep.evidence]}"
    return hits[0]


# ------------------------------------------------------------------------------------------------------
# 1. pure site effect
# ------------------------------------------------------------------------------------------------------

def test_rejects_a_candidate_that_is_purely_a_site_effect():
    """Site drives both the candidate and the outcome. Within a site the candidate is pure noise, so the
    stratified AUC must collapse to chance while the marginal AUC does not."""
    rng = np.random.default_rng(11)
    n_per = 90
    sites, vals, ys = [], [], []
    # three sites with different candidate offsets AND different outcome rates -- the classic fingerprint
    for site, offset, prate in [("A", 0.0, 0.20), ("B", 2.0, 0.55), ("C", 4.0, 0.85)]:
        sites += [site] * n_per
        vals.append(offset + rng.normal(0, 0.5, n_per))
        ys.append(rng.binomial(1, prate, n_per).astype(float))
    coh = Cohort(values=np.concatenate(vals), y=np.concatenate(ys),
                 subject=np.arange(3 * n_per), contrast="outcome",
                 nuisance={"site": np.array(sites)},
                 baseline=rng.normal(size=3 * n_per), dataset="planted")

    rep = verify(_cand(), [coh], np.random.default_rng(0), extra_evidence=_computational_pass())
    assert rep.verdict == REJECT, rep.verdict_reasons
    assert "probe:site" in _reasons(rep), rep.verdict_reasons
    e = _ev(rep, "probe:site")
    assert e.status == FAIL and e.values["clause1"] and e.values["clause2"]
    # by construction: the candidate knows site perfectly, and knows nothing within a site
    assert e.values["probe_auc"] > 0.95
    assert e.values["cond_lo"] <= 0.5 <= e.values["cond_hi"]


# ------------------------------------------------------------------------------------------------------
# 2. pure EMG
# ------------------------------------------------------------------------------------------------------

def test_rejects_a_candidate_that_is_purely_muscle():
    """A continuous confound. The candidate is EMG plus a little noise; EMG causes the outcome."""
    rng = np.random.default_rng(12)
    n = 300
    emg = rng.normal(size=n)
    values = emg + rng.normal(0, 0.15, n)          # the candidate IS the EMG index
    p = 1.0 / (1.0 + np.exp(-2.2 * emg))           # the outcome is driven by EMG, not by the candidate
    y = rng.binomial(1, p).astype(float)
    coh = Cohort(values=values, y=y, subject=np.arange(n), contrast="outcome",
                 nuisance={"emg_index": emg}, baseline=rng.normal(size=n), dataset="planted")

    rep = verify(_cand(), [coh], np.random.default_rng(1), extra_evidence=_computational_pass())
    assert rep.verdict == REJECT, rep.verdict_reasons
    assert "probe:emg_index" in _reasons(rep), rep.verdict_reasons
    e = _ev(rep, "probe:emg_index")
    assert e.values["probe_auc"] > e.values["outcome_auc"]
    assert e.values["cond_lo"] <= 0.5 <= e.values["cond_hi"]


# ------------------------------------------------------------------------------------------------------
# 3. label leakage
# ------------------------------------------------------------------------------------------------------

def test_rejects_implausibly_perfect_discrimination_as_leakage():
    rng = np.random.default_rng(13)
    n = 240
    y = rng.binomial(1, 0.5, n).astype(float)
    values = y + rng.normal(0, 0.05, n)            # the label itself, lightly blurred
    coh = Cohort(values=values, y=y, subject=np.arange(n), contrast="outcome",
                 baseline=rng.normal(size=n), dataset="planted")

    rep = verify(_cand(), [coh], np.random.default_rng(2), extra_evidence=_computational_pass())
    assert rep.verdict == REJECT, rep.verdict_reasons
    assert "label_leakage" in _reasons(rep), rep.verdict_reasons
    assert _ev(rep, "label_leakage").values["auc"] >= 0.98


# ------------------------------------------------------------------------------------------------------
# 4. direction inversion across datasets
# ------------------------------------------------------------------------------------------------------

def test_a_candidate_that_inverts_across_datasets_does_not_survive():
    """Pooling would report a mediocre positive AUC and hide the inversion entirely."""
    rng = np.random.default_rng(14)
    cand = _cand(requires=("computational", "statistical", "adversarial", "cross_domain"))
    cohorts = []
    for name, sign in [("dsA", +1.0), ("dsB", -1.0)]:
        n = 200
        y = rng.binomial(1, 0.5, n).astype(float)
        values = sign * (y * 1.1) + rng.normal(0, 1.0, n)
        cohorts.append(Cohort(values=values, y=y, subject=np.arange(n), contrast="outcome",
                              baseline=rng.normal(size=n), dataset=name))

    rep = verify(cand, cohorts, np.random.default_rng(3), extra_evidence=_computational_pass())
    assert rep.verdict != SURVIVE, rep.verdict_reasons
    e = _ev(rep, "leave_one_dataset_out")
    assert e.status == FAIL
    assert e.values["per_dataset"]["dsA"] > 0.5 > e.values["per_dataset"]["dsB"]


def test_a_single_dataset_cannot_satisfy_a_cross_domain_requirement():
    """Silence is not evidence: one dataset must yield INCOMPLETE, not a pass, for a candidate whose own
    declaration says it needs cross-domain transfer."""
    rng = np.random.default_rng(15)
    n = 200
    y = rng.binomial(1, 0.5, n).astype(float)
    coh = Cohort(values=y * 1.2 + rng.normal(0, 1.0, n), y=y, subject=np.arange(n),
                 contrast="outcome", baseline=rng.normal(size=n), dataset="only_one")
    cand = _cand(requires=("computational", "statistical", "adversarial", "cross_domain"))
    rep = verify(cand, [coh], np.random.default_rng(4), extra_evidence=_computational_pass())
    assert rep.verdict == INCOMPLETE, rep.verdict_reasons
    assert "cross_domain" in _reasons(rep) or "leave_one_dataset_out" in _reasons(rep)


# ------------------------------------------------------------------------------------------------------
# 5. THE CLEAN CASE -- the engine must not reject this
# ------------------------------------------------------------------------------------------------------

def test_a_clean_signal_survives_even_though_it_tracks_a_nuisance():
    """The candidate is strongly correlated with age (clause 1 fires) but its outcome association is
    generated INDEPENDENTLY of age, so it survives age strata (clause 2 does not fire).

    This is the discriminating case. A verifier that rejects here would reject every real physiological
    marker, since real markers correlate with age, sex, and recording length.
    """
    rng = np.random.default_rng(16)
    n = 500
    age = rng.normal(0, 1, n)
    signal = rng.normal(0, 1, n)                    # the part that carries the outcome
    values = 1.5 * age + signal                     # dominated by age -> probe strength will be high
    p = 1.0 / (1.0 + np.exp(-4.0 * signal))         # outcome depends ONLY on the age-independent part
    y = rng.binomial(1, p).astype(float)
    coh = Cohort(values=values, y=y, subject=np.arange(n), contrast="outcome",
                 nuisance={"age": age}, baseline=rng.normal(size=n), dataset="planted")

    rep = verify(_cand(), [coh], np.random.default_rng(5), extra_evidence=_computational_pass())
    e = _ev(rep, "probe:age")
    assert e.values["clause1"], "the candidate should track age more strongly than the outcome here"
    assert not e.values["clause2"], "the outcome association must survive age strata by construction"
    assert e.status == PASS
    assert rep.verdict == SURVIVE, rep.verdict_reasons


def test_the_engine_can_return_survive_at_all():
    """A minimal well-behaved candidate: real signal, no confounds supplied, beats the baseline."""
    rng = np.random.default_rng(17)
    n = 300
    y = rng.binomial(1, 0.5, n).astype(float)
    coh = Cohort(values=y * 1.3 + rng.normal(0, 1.0, n), y=y, subject=np.arange(n),
                 contrast="outcome", baseline=rng.normal(size=n), dataset="planted",
                 nuisance={"age": rng.normal(size=n)})
    rep = verify(_cand(), [coh], np.random.default_rng(6), extra_evidence=_computational_pass())
    assert rep.verdict == SURVIVE, rep.verdict_reasons


# ------------------------------------------------------------------------------------------------------
# 6. the verdict must be withheld, not negative, when the harness is broken
# ------------------------------------------------------------------------------------------------------

def test_a_broken_machinery_gate_yields_indeterminate_not_a_negative():
    """Rule 31: when a check fails its own gate, the downstream verdict is ABSENT, not negative."""
    from bsde.verifier.report import Evidence, VerifierReport, decide
    rep = VerifierReport(candidate="x", candidate_version="1.0", declaration_hash="0" * 16,
                         search_space_size=1, required_layers=["computational", "statistical"])
    rep.add(Evidence("permutation_null_is_centred", "statistical", FAIL,
                     "null mean 0.71, nowhere near chance", machinery_gate=True))
    rep.add(Evidence("directional_discrimination", "statistical", FAIL, "AUC 0.51 [0.44, 0.58]"))
    rep.add(Evidence("synthetic_ground_truth", "computational", PASS, "ok"))
    decide(rep)
    assert rep.verdict == INDETERMINATE
    assert "machinery gate failed" in _reasons(rep)
    # and crucially it must NOT read as a refutation of the candidate
    assert rep.verdict not in (REJECT, REVISE)


def test_a_refutation_is_not_softened_by_an_incomplete_run():
    """Order matters the other way too: a fatal confound must REJECT even though other layers never ran."""
    from bsde.verifier.report import Evidence, VerifierReport, decide
    rep = VerifierReport(candidate="x", candidate_version="1.0", declaration_hash="0" * 16,
                         search_space_size=1,
                         required_layers=["computational", "statistical", "cross_domain"])
    rep.add(Evidence("probe:site", "adversarial", FAIL, "carried by site", fatal=True))
    rep.add(Evidence("leave_one_dataset_out", "cross_domain", "not_run", "only one dataset"))
    decide(rep)
    assert rep.verdict == REJECT


# ------------------------------------------------------------------------------------------------------
# the stratified statistic itself, against a hand-computable case
# ------------------------------------------------------------------------------------------------------

def test_stratified_auc_excludes_cross_stratum_pairs():
    """Two strata, each internally perfectly discriminating, but with offsets that make the POOLED
    comparison misleading. Stratified AUC must be 1.0; the marginal AUC must not be."""
    from bsde.verifier.stats import auc
    y = np.array([0., 1., 0., 1.])
    score = np.array([0.0, 1.0, 10.0, 11.0])
    strata = np.array(["a", "a", "b", "b"])
    assert stratified_auc(y, score, strata) == pytest.approx(1.0)
    # marginal: pairs are (1 vs 0)=win, (1 vs 10)=loss, (11 vs 0)=win, (11 vs 10)=win -> 3/4
    assert auc(y, score) == pytest.approx(0.75)


def test_stratified_auc_counts_ties_as_half():
    y = np.array([0., 1., 0., 1.])
    score = np.array([1.0, 1.0, 0.0, 5.0])
    strata = np.array(["a", "a", "b", "b"])
    # stratum a: tie -> 0.5 of 1 pair; stratum b: win -> 1 of 1 pair; pooled 1.5/2
    assert stratified_auc(y, score, strata) == pytest.approx(0.75)


def test_continuous_nuisances_stratify_by_tertile():
    v = np.arange(300, dtype=float)
    s = _strata_of(v)
    assert set(np.unique(s)) == {"t1", "t2", "t3"}
    assert abs((s == "t1").sum() - 100) <= 2


def test_categorical_nuisances_stratify_by_level():
    v = np.array(["A", "B", "A", "C"])
    assert set(np.unique(_strata_of(v))) == {"A", "B", "C"}


# ------------------------------------------------------------------------------------------------------
# the label-free redundancy check -- the only layer that runs on a dataset with no labels
# ------------------------------------------------------------------------------------------------------

def test_a_near_perfect_copy_of_a_simpler_measure_is_refuted():
    """The E01 situation in miniature: a complex candidate that is a monotone rescaling of a simple one."""
    from bsde.verifier.engine import check_redundancy
    rng = np.random.default_rng(21)
    base = rng.normal(size=200)
    cand_vals = 3.7 * base + 0.4                      # a pure affine rescaling -- identical information
    e = check_redundancy(_cand(complexity=4), cand_vals, base, "z(mean exponent)", baseline_complexity=2)
    assert e.status == FAIL and e.fatal
    assert e.values["abs_spearman"] > 0.99


def test_redundancy_is_judged_on_ranks_so_a_monotone_transform_does_not_hide_it():
    """Pearson would be misled by a strong nonlinearity; Spearman is not, and a weighted mean of two
    standardised variables is exactly the kind of monotone rescaling that must be caught."""
    from bsde.verifier.engine import check_redundancy
    rng = np.random.default_rng(22)
    base = rng.uniform(0.1, 3.0, size=300)
    cand_vals = np.exp(base * 2.0)                    # wildly nonlinear, perfectly rank-preserving
    e = check_redundancy(_cand(complexity=4), cand_vals, base, "baseline", baseline_complexity=2)
    assert e.values["abs_spearman"] == pytest.approx(1.0, abs=1e-9)
    assert e.status == FAIL and e.fatal


def test_a_distinguishable_measure_passes_redundancy():
    from bsde.verifier.engine import check_redundancy
    rng = np.random.default_rng(23)
    base = rng.normal(size=300)
    cand_vals = 0.5 * base + rng.normal(size=300)     # shares variance but is not the same number
    e = check_redundancy(_cand(complexity=4), cand_vals, base, "baseline", baseline_complexity=2)
    assert e.status == PASS
    assert e.values["abs_spearman"] < 0.9


def test_redundancy_is_not_applicable_when_no_simpler_alternative_exists():
    """Two identical measures where the candidate is no more complex than the alternative: there is nothing
    to demote. Firing here would reject the trivial baseline for being redundant with itself.

    The status must be NOT_APPLICABLE rather than PASS. A PASS would carry the prose "below the
    near-redundancy threshold", which is a FALSE statement when r is 1.0 -- and that is exactly the line
    E02 printed for whole_head_exponent before this was fixed. A check that cannot be asked must say so.
    """
    from bsde.verifier.engine import check_redundancy
    from bsde.verifier.report import NOT_APPLICABLE
    rng = np.random.default_rng(24)
    base = rng.normal(size=200)
    e = check_redundancy(_cand(complexity=2), base.copy(), base, "an equally simple measure",
                         baseline_complexity=2)
    assert e.status == NOT_APPLICABLE and not e.fatal
    assert e.values["abs_spearman"] == pytest.approx(1.0, abs=1e-9)
    assert "below the" not in e.reason, "must not claim a threshold was cleared when r is 1.0"
