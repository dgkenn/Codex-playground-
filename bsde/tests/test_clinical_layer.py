"""Ground-truth tests for verifier layer 7 (clinical).

THE TEST THAT JUSTIFIES THE LAYER is `test_a_strong_auc_can_have_a_useless_ppv_at_real_prevalence`. It builds
a measure with AUC around 0.86 — better than anything this project has produced on real data — and shows its
positive predictive value collapsing to near-uselessness once the prevalence is the one a clinic would see
rather than the 50/50 every cohort here has by construction. Nothing in layers 2 through 6 can see that,
because AUC is prevalence-free by definition.

The second test that earns its place is `test_net_benefit_can_fail_for_a_measure_with_good_discrimination`:
a measure can discriminate and still be worse than treating everyone, at the threshold probability where a
clinician would actually act. That is a real failure mode and no AUC reveals it.

The rest pin the arithmetic (Bayes, the decision curve, MDC) and the refusals — every check must return
NOT_RUN rather than a guess when the caller has not supplied a prevalence or a harm ratio, because those are
clinical facts and not statistical ones.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.verifier.clinical import (layer_clinical, minimum_detectable_change, net_benefit, ppv_npv,
                                    threshold_for_target)
from bsde.verifier.report import FAIL, NOT_RUN, PASS


def _separable(n=200, gap=1.5, seed=0):
    """A two-class sample with controllable separation; `p` stands in for calibrated probabilities."""
    rng = np.random.default_rng(seed)
    y = np.r_[np.zeros(n // 2), np.ones(n // 2)]
    x = rng.normal(0.0, 1.0, size=n) + gap * y
    p = 1.0 / (1.0 + np.exp(-(x - gap / 2.0)))
    return y, p


# --- the tests the layer exists for ------------------------------------------------------------------

def test_a_strong_auc_can_have_a_useless_ppv_at_real_prevalence():
    """AUC is prevalence-free. Clinical use is not, and this is the gap the layer closes."""
    from bsde.verifier.stats import auc
    y, p = _separable(gap=1.5, seed=1)
    assert auc(y, p) > 0.80, "the setup must be a genuinely good discriminator"

    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0),
                                             prevalences=(0.5, 0.05, 0.01))}
    by_prev = ev["prevalence_sensitivity"].values["by_prevalence"]
    ppv_balanced = by_prev["0.5"]["at_target_spec"]["ppv"]
    ppv_rare = by_prev["0.01"]["at_target_spec"]["ppv"]
    assert ppv_balanced > 0.7, by_prev
    assert ppv_rare < 0.25, (
        f"PPV at 1 % prevalence was {ppv_rare:.3f}; if a strong discriminator really does keep a high PPV "
        "at that prevalence, this test's premise is wrong and the layer needs rethinking")
    assert ppv_balanced > 4 * ppv_rare


def test_net_benefit_can_fail_for_a_measure_with_good_discrimination():
    """A measure that discriminates but never beats treat-all/treat-none in the declared range."""
    y, p = _separable(gap=0.35, seed=2)          # weak but real separation
    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0),
                                             prevalences=(0.02,), threshold_probs=(0.3, 0.5))}
    nb = ev["net_benefit"]
    assert nb.status == FAIL, nb.values
    assert nb.fatal, "a measure that never beats both defaults is a refutation, not a note"


def test_net_benefit_passes_for_a_measure_that_helps():
    y, p = _separable(gap=2.5, seed=3)
    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0),
                                             prevalences=(0.3,), threshold_probs=(0.1, 0.2, 0.3))}
    assert ev["net_benefit"].status == PASS, ev["net_benefit"].values


# --- refusals: clinical facts are supplied, never guessed ---------------------------------------------

def test_without_a_declared_prevalence_the_ppv_check_refuses():
    y, p = _separable(seed=4)
    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0))}
    e = ev["prevalence_sensitivity"]
    assert e.status == NOT_RUN
    assert "design choice" in e.reason.lower(), (
        "the refusal must say WHY the sample prevalence cannot be used, or a reader will supply it")
    assert e.values["sample_prevalence"] == pytest.approx(0.5, abs=0.02)


def test_mdc_refuses_without_layer_five_inputs():
    y, p = _separable(seed=5)
    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0), prevalences=(0.1,))}
    e = ev["minimum_detectable_change"]
    assert e.status == NOT_RUN
    assert "layer 5" in e.reason or "temporal" in e.reason


def test_too_few_rows_gives_NOT_RUN_across_the_board():
    y = np.r_[np.zeros(5), np.ones(5)]
    p = np.linspace(0, 1, 10)
    ev = {e.check: e for e in layer_clinical(None, y, p, np.random.default_rng(0), prevalences=(0.1,))}
    for check in ("prevalence_sensitivity", "operating_point", "net_benefit"):
        assert ev[check].status == NOT_RUN, check


# --- the arithmetic ------------------------------------------------------------------------------------

def test_ppv_npv_is_bayes_and_not_a_confusion_matrix_count():
    """Worked by hand: sens 0.9, spec 0.9, prevalence 0.01 -> PPV = .009/(.009+.099) = 0.0833."""
    r = ppv_npv(0.9, 0.9, 0.01)
    assert r["ppv"] == pytest.approx(0.0833, abs=1e-3)
    assert r["npv"] == pytest.approx(0.9989, abs=1e-3)


def test_ppv_rises_monotonically_with_prevalence():
    v = [ppv_npv(0.9, 0.9, q)["ppv"] for q in (0.01, 0.05, 0.2, 0.5, 0.8)]
    assert v == sorted(v)


def test_treat_all_net_benefit_matches_the_closed_form():
    """NB(treat all) = prev - (1-prev)*pt/(1-pt), independent of the measure."""
    y, p = _separable(seed=6)
    nb = net_benefit(y, p, pt=0.2, prevalence=0.1)
    assert nb["treat_all"] == pytest.approx(0.1 - 0.9 * (0.2 / 0.8), abs=1e-9)
    assert nb["treat_none"] == 0.0


def test_net_benefit_uses_the_declared_prevalence_not_the_sample():
    y, p = _separable(seed=7)                      # sample prevalence is 0.5
    a = net_benefit(y, p, pt=0.2, prevalence=0.02)
    b = net_benefit(y, p, pt=0.2, prevalence=None)
    assert a["prevalence_used"] == pytest.approx(0.02)
    assert b["prevalence_used"] == pytest.approx(0.5, abs=0.02)
    assert a["model"] < b["model"], "a rare condition must yield lower net benefit at the same threshold"


def test_threshold_rule_meets_its_target_and_is_not_youden():
    y, p = _separable(gap=1.5, seed=8)
    r = threshold_for_target(y, p, 0.90, "sens")
    assert r["sens"] >= 0.90 - 1e-9, r
    r2 = threshold_for_target(y, p, 0.90, "spec")
    assert r2["spec"] >= 0.90 - 1e-9, r2
    assert r["threshold"] < r2["threshold"], "a high-sensitivity cut-off must sit below a high-specificity one"


def test_threshold_reports_unreachable_targets_rather_than_the_closest_miss():
    y = np.r_[np.zeros(50), np.ones(50)]
    p = np.r_[np.full(50, 0.5), np.full(50, 0.5)]     # no separation at all
    r = threshold_for_target(y, p, 0.999, "spec")
    assert not np.isfinite(r["threshold"])
    assert "reaches" in r.get("reason", "")


def test_mdc_is_1_96_root_two_sigma():
    m = minimum_detectable_change(within_scatter=2.0, between_difference=10.0)
    assert m["mdc95"] == pytest.approx(1.96 * np.sqrt(2) * 2.0, rel=1e-9)
    assert m["ratio"] == pytest.approx(10.0 / m["mdc95"], rel=1e-9)


def test_mdc_fails_when_noise_swamps_the_effect_it_must_detect():
    ev = {e.check: e for e in layer_clinical(None, *_separable(seed=9), rng=np.random.default_rng(0),
                                             prevalences=(0.1,),
                                             within_scatter=5.0, between_difference=1.0)}
    e = ev["minimum_detectable_change"]
    assert e.status == FAIL and e.fatal
    assert "one patient" in e.reason.lower()


def test_mdc_passes_when_the_effect_clears_the_noise():
    ev = {e.check: e for e in layer_clinical(None, *_separable(seed=10), rng=np.random.default_rng(0),
                                             prevalences=(0.1,),
                                             within_scatter=0.1, between_difference=5.0)}
    assert ev["minimum_detectable_change"].status == PASS
