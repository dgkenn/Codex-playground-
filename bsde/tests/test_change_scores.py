"""The coupling trap, and proof that the corrected statistics have the null they claim.

Every assertion here is against a value that probability theory fixes, not against this implementation —
the same discipline `test_dfa_lrtc.py` uses. Under a pure null, `corr(before, after - before)` is
`-sd_b / sqrt(sd_a^2 + sd_b^2)`, which is `-1/sqrt(2)` at equal spreads. `oldham` and `on_value` are zero.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

from bsde.verifier.change_scores import (analyse, expected_coupled_null,   # noqa: E402
                                         expected_oldham_null, report)

N = 4000


def _pair(rho_true=0.0, sd_after=1.0, n=N, seed=0):
    rng = np.random.default_rng(seed)
    b = rng.normal(0, 1.0, n)
    a = rho_true * (sd_after / 1.0) * b + np.sqrt(max(0.0, 1 - rho_true ** 2)) * rng.normal(0, sd_after, n)
    return b, a


def test_the_coupled_statistic_is_minus_root_half_under_a_pure_null():
    """The headline fact: no relationship whatever, and the correlation is -0.71."""
    b, a = _pair(0.0, 1.0, seed=1)
    res = analyse(b, a)
    assert abs(res["pearson_coupled"] - (-1 / np.sqrt(2))) < 0.03
    assert abs(res["expected_coupled_null"] - (-1 / np.sqrt(2))) < 0.03


def test_compressed_after_values_push_the_null_to_minus_zero_point_eight_two():
    """The specific case that matters: an intervention that compresses variance.

    This is the row that reproduces a reported -0.81 from nothing at all.
    """
    b, a = _pair(0.0, 0.7, seed=2)
    res = analyse(b, a)
    assert abs(res["pearson_coupled"] - (-0.819)) < 0.03
    assert abs(expected_coupled_null(1.0, 0.7) - (-0.819)) < 0.01


def test_a_genuine_positive_relationship_makes_the_coupled_number_LESS_negative():
    """The direction that makes the artefact dangerous: real signal weakens the headline."""
    vals = [analyse(*_pair(r, 1.0, seed=3))["pearson_coupled"] for r in (0.0, 0.2, 0.4, 0.6)]
    assert all(y > x for x, y in zip(vals, vals[1:])), vals
    assert vals[0] < -0.65 and vals[-1] > -0.50


@pytest.mark.parametrize("sd_after", [0.6, 1.0, 1.6])
def test_only_on_value_is_zero_under_the_null_at_every_spread(sd_after):
    """**The correction this module needed before it shipped.**

    The first draft asserted Oldham's null was zero. It is not: under the null it equals
    `(var_after - var_before)/(var_after + var_before)`, so it is zero only when the variances match.
    `on_value` is the one that holds at every spread, which is why it is what `report()` tells you to use.
    """
    b, a = _pair(0.0, sd_after, seed=4)
    res = analyse(b, a)
    assert abs(res["on_value"]) < 0.05, res["on_value"]
    assert abs(res["oldham"] - res["expected_oldham_null"]) < 0.06, (res["oldham"],
                                                                    res["expected_oldham_null"])
    if abs(sd_after - 1.0) > 0.2:
        assert abs(res["oldham"]) > 0.15, "Oldham is NOT null when the variances differ"


@pytest.mark.parametrize("sd_after,want", [(0.6, -0.4706), (1.0, 0.0), (1.6, +0.4382)])
def test_the_oldham_null_matches_its_closed_form(sd_after, want):
    assert abs(expected_oldham_null(1.0, sd_after) - want) < 0.001


def test_oldham_recovers_a_real_effect_that_the_coupled_statistic_hides():
    """The point of the correction: when something IS there, the corrected statistic sees it.

    Constructed so the change genuinely depends on the underlying level — subjects starting higher change
    more — which is the substantive hypothesis a baseline-predicts-response claim is making.
    """
    rng = np.random.default_rng(5)
    b = rng.normal(0, 1.0, N)
    a = b + 0.8 * b + rng.normal(0, 0.4, N)          # change = 0.8*b + noise: a REAL dependence
    res = analyse(b, a)
    assert res["on_value"] > 0.5, res["on_value"]
    assert res["oldham"] - res["expected_oldham_null"] > 0.3, (res["oldham"],
                                                               res["expected_oldham_null"])


def test_the_report_shows_the_null_beside_the_coupled_value():
    b, a = _pair(0.0, 0.7, seed=6)
    lines = "\n".join(report(analyse(b, a)))
    assert "not zero" in lines
    assert "excess over the null" in lines
    assert "NULL IS ZERO AT EVERY SPREAD" in lines, "on_value must be flagged as the one to report"
    assert "zero only if the variances match" in lines, "Oldham's own null must be shown too"


def test_mismatched_lengths_raise_rather_than_silently_truncate():
    with pytest.raises(ValueError):
        analyse(np.zeros(10), np.zeros(9))


def test_too_few_pairs_reports_an_error_rather_than_a_number():
    assert analyse([1.0, 2.0], [1.0, 2.0]).get("error")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
