"""Every gate added by E36-E39 must be shown to FAIL on an input designed to fail it.

Error-catalogue rule 40, in its own words: *"A GATE THAT CANNOT FAIL IS NOT A GATE, and this project shipped
two."* E22 selected epochs by a column its adapter never emitted, so the gate saw 0 of 0 cases; E29 checked
that pairs spanned both dose directions while its own constructor oriented every pair the same way. Both
printed confidently. The rule's prescription is to **construct the input that should fail the gate and check
that it does**, and `test_e28_paths.py` is the pattern.

Four gated experiments were registered and run on 2026-07-30/31 without that check:

    E36  G1  both measure families must be capable        P2  the exhaustive 4/8-split placebo
    E37  G1  five parts, including (e) the EWS statistics vary and (f) the coverage exclusion is not
             outcome-related — (f) was added mid-file and has never been seen to fire
    E38  G1  the trial cache must reproduce the stored label — and its floor was ALREADY found to be
             unreachable once (rule 40 committed by that file), so the corrected version needs the test
             more than any other gate here
    E39  G2  both contrasts must be detectable            P4  the rule-48 NOT-INFORMATIVE branch

These tests carry **no claim about any candidate**. Every fixture is synthetic and constructed to make a
specific branch reachable; the assertions are about control flow, not about EEG.
"""
from __future__ import annotations

import csv
import importlib.util
import itertools
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))
EXP = os.path.abspath(os.path.join(HERE, "..", "src", "bsde", "experiments"))


def _load(stem):
    path = os.path.join(EXP, stem)
    spec = importlib.util.spec_from_file_location(stem[:-3] + "_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------------------
# E36 — the family-capability gate and the exhaustive-split placebo
# --------------------------------------------------------------------------------------------------

def _krause_rows(rng, n_patients=20, per_block=12, phase_state=0.0, amp_state=2.0, drug_gap=0.0):
    """A synthetic Krause-shaped table.

    `phase_state` and `amp_state` set how strongly each family separates wake from unresponsive;
    `drug_gap` shifts the amplitude features between the two drug arms only.
    """
    mod = _load("e36_family_split_probe.py")
    rows = []
    for p in range(n_patients):
        dex = p >= n_patients // 2
        for label in (("WA_dex", "U_dex") if dex else ("WA", "U")):
            unresp = label.startswith("U")
            for _ in range(per_block):
                r = {"patientID": f"P{p}", "label": label,
                     "pctGoodSamples": f"{rng.uniform(0.9, 1.0)}", "Subdural": "1"}
                for f in mod.PHASE:
                    r[f] = f"{rng.normal(phase_state if unresp else 0.0, 1.0)}"
                for f in mod.AMPLITUDE:
                    shift = (amp_state if unresp else 0.0) + (drug_gap if dex and unresp else 0.0)
                    r[f] = f"{rng.normal(shift, 1.0)}"
                r["frontBias"] = r[mod.PHASE[0]]
                rows.append(r)
    return mod, rows


def _write_krause(tmp_path, rows, mod):
    path = tmp_path / "krause.csv"
    fields = ["patientID", "label", "pctGoodSamples", "Subdural"] + list(mod.PHASE) + \
             list(mod.AMPLITUDE) + ["frontBias"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return str(path)


def test_e36_g1_fails_when_a_family_cannot_track_state(tmp_path, monkeypatch, capsys):
    """PHASE separates nothing -> G1 must refuse, and nothing downstream may be reported."""
    rng = np.random.default_rng(0)
    mod, rows = _krause_rows(rng, phase_state=0.0, amp_state=3.0)
    monkeypatch.setattr(mod, "TABLE", _write_krause(tmp_path, rows, mod))
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "out.json"))
    monkeypatch.setattr(mod, "REPS", 20)
    monkeypatch.setattr(mod, "PERMS", 20)
    rc = mod.main([])
    out = capsys.readouterr().out
    assert rc == 1, "a family that tracks nothing must not reach the primary"
    assert "G1 *** FAILED" in out
    assert "ABSENT, not negative" in out
    assert "P1 — THE PRIMARY" not in out, "nothing downstream may be printed after a failed gate"


def test_e36_g1_passes_when_both_families_are_capable(tmp_path, monkeypatch, capsys):
    """The complement of the test above: the gate must also be passable, or it is a wall."""
    rng = np.random.default_rng(1)
    mod, rows = _krause_rows(rng, phase_state=2.5, amp_state=2.5)
    monkeypatch.setattr(mod, "TABLE", _write_krause(tmp_path, rows, mod))
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "out.json"))
    monkeypatch.setattr(mod, "REPS", 20)
    monkeypatch.setattr(mod, "PERMS", 20)
    mod.main([])
    out = capsys.readouterr().out
    assert "G1 PASSED" in out
    assert "P1 — THE PRIMARY" in out


def test_e36_placebo_fails_when_the_real_split_is_not_extreme():
    """The exhaustive 4/8 placebo must NOT pass a partition that is ordinary among the 495.

    Built directly on `_delta` so the arithmetic is tested rather than the plumbing: with every feature
    drawn from one distribution, the declared split is just another split and must land near the middle.
    """
    mod = _load("e36_family_split_probe.py")
    rng = np.random.default_rng(3)
    drug = {n: float(rng.uniform(0.1, 0.3)) for n in mod.PRIMARY}
    state = {n: float(rng.uniform(0.2, 0.4)) for n in mod.PRIMARY}
    real, _, _ = mod._delta(drug, state, mod.PHASE, mod.AMPLITUDE)
    null = []
    for combo in itertools.combinations(mod.PRIMARY, len(mod.PHASE)):
        other = tuple(n for n in mod.PRIMARY if n not in combo)
        v, _, _ = mod._delta(drug, state, combo, other)
        null.append(v)
    null = np.asarray(null, float)
    assert null.size == 495, "the enumeration must be exhaustive, not sampled"
    thresh = float(np.percentile(null, mod.PLACEBO_PERCENTILE))
    assert real < thresh, "an exchangeable split must not clear the 97.5th percentile"


def test_e36_placebo_passes_only_for_a_genuinely_extreme_split():
    """And it must pass when the declared split really is the maximum — a gate must be able to do both."""
    mod = _load("e36_family_split_probe.py")
    drug = {n: (0.0 if n in mod.PHASE else 0.35) for n in mod.PRIMARY}
    state = {n: 0.30 for n in mod.PRIMARY}
    real, _, _ = mod._delta(drug, state, mod.PHASE, mod.AMPLITUDE)
    null = [mod._delta(drug, state, c, tuple(n for n in mod.PRIMARY if n not in c))[0]
            for c in itertools.combinations(mod.PRIMARY, len(mod.PHASE))]
    assert real >= float(np.percentile(np.asarray(null, float), mod.PLACEBO_PERCENTILE))
    assert sum(1 for v in null if v >= real) == 1, "the declared split should be the unique maximum here"


# --------------------------------------------------------------------------------------------------
# E37 — the EWS estimator, and G1(f), the exclusion-is-not-outcome-related check
# --------------------------------------------------------------------------------------------------

def test_e37_ews_never_forms_a_pair_across_a_hole():
    """Rule 27 in code: a lag-1 term must not be accumulated across a missing sample.

    A series that alternates present/absent has NO adjacent both-present pair, so the estimator must refuse
    to issue an autocorrelation however long the window is.
    """
    mod = _load("e37_challenge_c_critical_slowing.py")
    x = np.arange(400.0)
    x[1::2] = np.nan
    var, ar1 = mod._ews(x, 120, 0.4, 5)
    assert np.all(~np.isfinite(ar1)), "no both-present adjacent pair exists; ar1 must be NaN throughout"
    assert np.any(np.isfinite(var)), "variance over present samples is still defined"


def test_e37_ews_tolerates_scattered_holes_but_honours_the_coverage_floor():
    """The corrected estimator's two halves: it must survive sparse holes and refuse dense ones."""
    mod = _load("e37_challenge_c_critical_slowing.py")
    rng = np.random.default_rng(5)
    x = rng.normal(size=1000)
    sparse = x.copy()
    sparse[rng.choice(1000, 80, replace=False)] = np.nan
    _, ar1_sparse = mod._ews(sparse, 60, 0.80, 30)
    assert np.isfinite(ar1_sparse).sum() > 500, "8 % holes must not destroy the series"
    dense = x.copy()
    dense[rng.choice(1000, 700, replace=False)] = np.nan
    _, ar1_dense = mod._ews(dense, 60, 0.80, 30)
    assert np.isfinite(ar1_dense).sum() == 0, "70 % holes must fail the 80 % coverage floor everywhere"


def test_e37_g1f_fires_when_the_exclusion_is_outcome_related():
    """G1(f) must detect missingness that tracks the label — the check added after the estimator fix.

    Constructed directly against the statistic G1(f) computes, because the gate is one line inside `main`
    and the point of the test is that the line can fire, not that the file runs.
    """
    from bsde.verifier.stats import auc
    rng = np.random.default_rng(7)
    y = (rng.random(4000) < 0.2).astype(float)
    benign = (rng.random(4000) < 0.4).astype(float)
    assert abs(auc(y, benign) - 0.5) <= 0.10, "missingness unrelated to the label must pass"
    malign = np.where(y > 0, (rng.random(4000) < 0.85), (rng.random(4000) < 0.15)).astype(float)
    assert abs(auc(y, malign) - 0.5) > 0.10, "missingness concentrated near the label must FAIL G1(f)"


# --------------------------------------------------------------------------------------------------
# E38 — the cache-fidelity gate whose floor was already once unreachable
# --------------------------------------------------------------------------------------------------

def test_e38_loo_auc_is_deterministic():
    """The declared within-half estimator must have no RNG in it — that was the reason for choosing it."""
    mod = _load("e38_bci_label_reliability.py")
    rng = np.random.default_rng(11)
    X = rng.normal(size=(24, 6))
    y = np.r_[np.zeros(12), np.ones(12)]
    X[y == 1] += 0.8
    a, b = mod._auc_loo(X, y), mod._auc_loo(X, y)
    assert a == b, "leave-one-out must be reproducible without a seed"
    assert np.isfinite(a)


def test_e38_g1_statistic_separates_a_faithful_cache_from_a_corrupted_one():
    """The gate must distinguish a cache that reproduces the label from one that does not.

    This is the gate that was already shipped with an unreachable floor, so both directions are asserted:
    a faithful cache clears 0.90 once the 9-draw averaging is applied, and a shuffled one does not.
    """
    mod = _load("e38_bci_label_reliability.py")
    rng = np.random.default_rng(13)
    n = 80
    truth = rng.uniform(0.35, 0.85, n)
    faithful = truth + rng.normal(0, 0.012, n)
    assert mod.spearman(truth, faithful) >= mod.MIN_AGREEMENT
    assert float(np.median(np.abs(truth - faithful))) <= mod.MAX_MEDIAN_DIFF
    corrupted = rng.permutation(truth)
    assert mod.spearman(truth, corrupted) < mod.MIN_AGREEMENT, "a shuffled cache must FAIL G1"


def test_e38_split_half_is_degenerate_when_a_class_is_too_small():
    """`_split_half` must refuse rather than return a number built from three trials."""
    mod = _load("e38_bci_label_reliability.py")
    rng = np.random.default_rng(17)
    X = rng.normal(size=(14, 6))
    y = np.r_[np.zeros(11), np.ones(3)]
    a, b = mod._split_half(X, y, rng)
    assert not np.isfinite(a) and not np.isfinite(b)


# --------------------------------------------------------------------------------------------------
# E39 — the detectability gate, and the rule-48 branch
# --------------------------------------------------------------------------------------------------

def _e39_cohort(tmp_path, mod, name, rng, n_sub=12, per_sub=16, emg_effect=1.5, state_effect=1.5):
    fields = ["recording_id", "status", "subject", "meta_phase",
              mod.ARTEFACT, mod.PLACEBO_ARTEFACT, mod.PHASE] + list(mod.AMPLITUDE)
    path = tmp_path / f"{name}.csv"
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for s in range(n_sub):
            for k in range(per_sub):
                emg = rng.normal()
                phase = "awake_pre_drug" if k < per_sub // 2 else "post_loc"
                r = {"recording_id": f"{s}_{k}", "status": "ok", "subject": f"S{s}",
                     "meta_phase": phase, mod.ARTEFACT: f"{emg}", mod.PLACEBO_ARTEFACT: f"{emg + 0.01}"}
                for f in (mod.PHASE,) + mod.AMPLITUDE:
                    v = rng.normal()
                    v += emg_effect * emg
                    v += state_effect * (1.0 if phase == "post_loc" else 0.0)
                    r[f] = f"{v}"
                w.writerow(r)
    return str(path)


def test_e39_g2_fails_when_the_artefact_contrast_separates_nothing(tmp_path, monkeypatch, capsys):
    """Rule 32: with no artefact signal in any feature there is nothing to be robust TO, and G2 must say so."""
    mod = _load("e39_wpli_artefact_robustness.py")
    rng = np.random.default_rng(19)
    cfg = {}
    for name in list(mod.COHORTS):
        p = _e39_cohort(tmp_path, mod, name, rng, emg_effect=0.0, state_effect=2.0)
        cfg[name] = dict(mod.COHORTS[name], file=os.path.basename(p),
                         state_col="meta_phase", state_a="awake_pre_drug", state_b="post_loc")
    monkeypatch.setattr(mod, "RESULTS", str(tmp_path))
    monkeypatch.setattr(mod, "COHORTS", cfg)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "out.json"))
    monkeypatch.setattr(mod, "REPS", 20)
    rc = mod.main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "G2 FAIL" in out
    assert "ABSENT, not negative" in out


def test_e39_placebo_declares_itself_not_informative_under_a_null_primary(tmp_path, monkeypatch, capsys):
    """Rule 48: a placebo cannot validate a null, and must not print a pass beneath one.

    Every feature is built the same way here, so `Contrast` is zero by construction and its interval spans
    zero. The placebo branch must refuse rather than compare.
    """
    mod = _load("e39_wpli_artefact_robustness.py")
    rng = np.random.default_rng(23)
    cfg = {}
    for name in list(mod.COHORTS):
        p = _e39_cohort(tmp_path, mod, name, rng, emg_effect=1.2, state_effect=1.2)
        cfg[name] = dict(mod.COHORTS[name], file=os.path.basename(p),
                         state_col="meta_phase", state_a="awake_pre_drug", state_b="post_loc")
    monkeypatch.setattr(mod, "RESULTS", str(tmp_path))
    monkeypatch.setattr(mod, "COHORTS", cfg)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "out.json"))
    monkeypatch.setattr(mod, "REPS", 50)
    mod.main([])
    out = capsys.readouterr().out
    assert "NOT INFORMATIVE" in out
    assert "P4 PASSED" not in out, "a placebo must never report a pass under a null primary"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
