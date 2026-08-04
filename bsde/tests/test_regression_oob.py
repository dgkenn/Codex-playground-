"""The regression twins of the OOB machinery, checked against the failures they exist to prevent.

`grouped_cv_predict` and `oob_regression_increment` were added for E58 and are the first REGRESSION
validation path in this repo -- every previous one was AUC-based. Three specific errors are in scope:

  * folds that split windows rather than cases, which puts a case on both sides and inflates fidelity;
  * standardisation computed before the split, which leaks the test fold's scale into the fit;
  * an increment bootstrapped from FIXED out-of-fold predictions, which ignores refit variance (rule 9).

The leakage test is the one that matters: it plants a feature that is perfectly predictive WITHIN a case
and carries no information across cases, so an honest grouped CV must score it at roughly zero while a
window-split CV would score it near perfect.
"""
from __future__ import annotations

import numpy as np
import pytest

from bsde.verifier.stats import (_standardise, grouped_cv_predict, oob_regression_increment,
                                 ridge_fit)


def _r2(y, p):
    ok = np.isfinite(p)
    return 1.0 - np.sum((y[ok] - p[ok]) ** 2) / np.sum((y[ok] - y[ok].mean()) ** 2)


# --------------------------------------------------------------------------- ridge

def test_ridge_recovers_known_coefficients():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 3))
    y = 2.0 + 1.5 * X[:, 0] - 0.5 * X[:, 1]
    D = np.column_stack([np.ones(len(X)), X])
    b = ridge_fit(D, y, lam=1e-8)
    assert b[:3] == pytest.approx([2.0, 1.5, -0.5], abs=1e-4)


def test_ridge_does_not_penalise_the_intercept():
    """A heavily penalised fit must still reproduce the mean, or every prediction is biased toward zero."""
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 2))
    y = 50.0 + 0.1 * X[:, 0]
    D = np.column_stack([np.ones(len(X)), X])
    assert ridge_fit(D, y, lam=1e6)[0] == pytest.approx(50.0, abs=0.5)


# --------------------------------------------------------------------------- standardisation

def test_standardise_uses_training_statistics_only():
    """Test rows must be scaled by the TRAINING mean and sd, not their own."""
    tr = np.array([[0.0], [2.0]])            # mean 1, sd 1
    te = np.array([[10.0], [12.0]])
    _, Zte = _standardise(tr, te)
    assert Zte[:, 1] == pytest.approx([9.0, 11.0])


def test_standardise_fills_nan_with_the_training_mean():
    tr = np.array([[0.0], [2.0]])
    _, Zte = _standardise(tr, np.array([[np.nan]]))
    assert Zte[0, 1] == pytest.approx(0.0)


def test_standardise_survives_a_constant_column():
    tr = np.array([[5.0], [5.0]])
    Ztr, _ = _standardise(tr, tr)
    assert np.isfinite(Ztr).all() and Ztr[:, 1] == pytest.approx([0.0, 0.0])


# --------------------------------------------------------------------------- grouped CV

def _within_case_only(n_cases=20, per_case=15, seed=0):
    """A feature perfectly predictive of y INSIDE each case, uninformative across cases.

    Each case gets its own random slope AND its own random offset, so knowing the feature tells you nothing
    about y unless you have already seen that case.
    """
    rng = np.random.default_rng(seed)
    x, y, case = [], [], []
    for c in range(n_cases):
        slope = rng.choice([-4.0, 4.0])
        off = rng.normal(50, 15)
        xi = rng.normal(size=per_case)
        x.append(xi)
        y.append(off + slope * xi)
        case += [f"c{c}"] * per_case
    return (np.concatenate(x)[:, None], np.concatenate(y), np.array(case))


def test_grouped_cv_does_not_leak_the_case():
    """Cases held out whole -> a within-case-only feature must score at or below zero out of fold."""
    X, y, case = _within_case_only()
    pred = grouped_cv_predict(X, y, case, np.random.default_rng(7))
    assert _r2(y, pred) < 0.10


def test_grouped_cv_still_learns_a_real_across_case_signal():
    """The complement of the leakage test: the machinery must not be inert (rule 40)."""
    rng = np.random.default_rng(3)
    case = np.repeat([f"c{i}" for i in range(20)], 15)
    X = rng.normal(size=(len(case), 1))
    y = 40.0 + 6.0 * X[:, 0] + rng.normal(0, 1.0, len(case))
    pred = grouped_cv_predict(X, y, case, np.random.default_rng(3))
    assert _r2(y, pred) > 0.90


def test_grouped_cv_covers_every_row():
    X, y, case = _within_case_only(n_cases=10, per_case=8)
    pred = grouped_cv_predict(X, y, case, np.random.default_rng(5))
    assert np.isfinite(pred).all()


# --------------------------------------------------------------------------- OOB increment

def _two_arms(n_cases=25, per_case=12, extra_beta=5.0, seed=0):
    rng = np.random.default_rng(seed)
    case = np.repeat([f"c{i}" for i in range(n_cases)], per_case)
    x1 = rng.normal(size=len(case))
    x2 = rng.normal(size=len(case))
    y = 45.0 + 4.0 * x1 + extra_beta * x2 + rng.normal(0, 2.0, len(case))
    return x1[:, None], np.column_stack([x1, x2]), y, case


def test_oob_increment_is_negative_when_the_bigger_model_is_better():
    """Sign convention: the statistic is an ERROR, so B better than A must come out NEGATIVE.

    Reading this backwards would invert E58's verdict, which is why it is asserted rather than commented.
    """
    Xa, Xb, y, case = _two_arms(extra_beta=6.0)
    mean, lo, hi, n = oob_regression_increment(Xa, Xb, y, case, np.random.default_rng(11), reps=120)
    assert n >= 30
    assert hi < 0, (mean, lo, hi)


def test_oob_increment_spans_zero_when_the_extra_column_is_noise():
    """The gate must be able to say 'no gain'. `x2` carries no signal here."""
    Xa, Xb, y, case = _two_arms(extra_beta=0.0)
    mean, lo, hi, n = oob_regression_increment(Xa, Xb, y, case, np.random.default_rng(12), reps=120)
    assert n >= 30
    assert lo < 0 < hi or abs(mean) < 0.5, (mean, lo, hi)


def test_oob_increment_evaluates_only_out_of_bag_rows():
    """A within-case-only feature cannot help an out-of-bag evaluation, however well it fits in-bag.

    An implementation that scored on the drawn rows would show a large improvement here.
    """
    rng = np.random.default_rng(13)
    Xw, y, case = _within_case_only(n_cases=25, per_case=12, seed=4)
    Xa = rng.normal(size=(len(y), 1))
    Xb = np.column_stack([Xa[:, 0], Xw[:, 0]])
    mean, lo, hi, n = oob_regression_increment(Xa, Xb, y, case, np.random.default_rng(14), reps=120)
    assert n >= 30
    assert mean > -1.0, (mean, lo, hi)


def test_oob_increment_returns_nan_rather_than_an_interval_from_a_handful_of_draws():
    """Two cases means almost every draw has too few out-of-bag subjects; refuse rather than invent."""
    y = np.array([1.0, 2.0, 3.0, 4.0])
    case = np.array(["a", "a", "b", "b"])
    X = np.arange(4.0)[:, None]
    mean, lo, hi, n = oob_regression_increment(X, X, y, case, np.random.default_rng(15), reps=50)
    assert np.isnan(mean) and n < 30
