"""test_actionable_targets.py -- stdlib-only tests for the PURE helpers of
vitaldb_aki/analysis/actionable_targets.py.

These tests deliberately avoid numpy/pandas/sklearn so they run fast and green in
the integrity-core environment. They cover the parts of the module whose
correctness is load-bearing and that are pure Python:

  - e_value / e_value_ci         (VanderWeele formula; RR=2 -> ~3.41)
  - tertile_assign               (equal-frequency tertiles on a tiny frame)
  - exposure-rule helpers        (pressor_phe_equiv, any_vasopressor_flag,
                                  phenylephrine_predominant_flag)
  - time-to-treat lag core       (first_hypotension_onset, first_pressor_onset,
                                  treatment_lag_minutes on synthetic MAP+pump series)
  - benjamini_hochberg           (FDR mask)
  - import-safety without sklearn (run_actionable_targets is importable)

Run with:
    python3 -m unittest vitaldb_aki.tests.test_actionable_targets -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from vitaldb_aki.analysis import actionable_targets as at


class TestEValue(unittest.TestCase):

    def test_rr_two_gives_341(self):
        # Canonical VanderWeele example: RR=2 -> E-value ~ 3.41.
        self.assertAlmostEqual(at.e_value(2.0), 3.4142, places=3)

    def test_protective_rr_symmetry(self):
        # RR=0.5 maps to 1/0.5=2 -> same E-value as RR=2.
        self.assertAlmostEqual(at.e_value(0.5), at.e_value(2.0), places=6)

    def test_null_rr_is_one(self):
        self.assertEqual(at.e_value(1.0), 1.0)

    def test_nonfinite_and_nonpositive_are_one(self):
        self.assertEqual(at.e_value(0.0), 1.0)
        self.assertEqual(at.e_value(-3.0), 1.0)
        self.assertEqual(at.e_value(float("nan")), 1.0)

    def test_rr_value_known(self):
        # RR=1.5 -> 1.5 + sqrt(1.5*0.5) = 1.5 + sqrt(0.75) ~ 2.366
        self.assertAlmostEqual(at.e_value(1.5), 1.5 + math.sqrt(0.75), places=6)

    def test_ci_crossing_null_is_one(self):
        # CI spans 1 -> not significant -> E-value of CI is 1.
        self.assertEqual(at.e_value_ci(1.3, 0.8, 2.0), 1.0)

    def test_ci_harmful_uses_lower_bound(self):
        # Harmful point (RR>1), CI entirely > 1 -> E-value of lower bound.
        self.assertAlmostEqual(at.e_value_ci(2.0, 1.5, 3.0), at.e_value(1.5), places=6)

    def test_ci_protective_uses_upper_bound(self):
        # Protective point (RR<1), CI entirely < 1 -> E-value of upper bound.
        self.assertAlmostEqual(at.e_value_ci(0.5, 0.3, 0.8), at.e_value(0.8), places=6)


class TestTertileAssign(unittest.TestCase):

    def test_basic_equal_frequency(self):
        vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        t = at.tertile_assign(vals)
        # 6 values -> 2 per tertile.
        self.assertEqual(t, [0, 0, 1, 1, 2, 2])

    def test_three_levels_present(self):
        vals = list(range(9))
        t = at.tertile_assign([float(v) for v in vals])
        self.assertEqual(set(t), {0, 1, 2})

    def test_missing_values_map_to_none(self):
        vals = [1.0, None, float("nan"), 2.0, 3.0]
        t = at.tertile_assign(vals)
        self.assertIsNone(t[1])
        self.assertIsNone(t[2])
        # The three finite values get tertiles 0/1/2.
        finite = [t[0], t[3], t[4]]
        self.assertEqual(sorted(x for x in finite if x is not None), [0, 1, 2])

    def test_all_missing(self):
        self.assertEqual(at.tertile_assign([None, float("nan")]), [None, None])

    def test_ties_are_deterministic(self):
        # All-equal values: deterministic, all valid tertiles.
        t = at.tertile_assign([5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
        self.assertEqual(len(t), 6)
        self.assertTrue(all(x in (0, 1, 2) for x in t))


class TestExposureRules(unittest.TestCase):

    def test_pressor_phe_equiv(self):
        # phe=100ug, eph=2mg (->20 PHE-eq), epi=10ug -> 130
        self.assertAlmostEqual(at.pressor_phe_equiv(100.0, 2.0, 10.0), 130.0)

    def test_pressor_phe_equiv_handles_missing(self):
        self.assertEqual(at.pressor_phe_equiv(None, float("nan"), None), 0.0)

    def test_any_vasopressor_flag(self):
        self.assertEqual(at.any_vasopressor_flag(0, 0, 0), 0)
        self.assertEqual(at.any_vasopressor_flag(50.0, 0, 0), 1)
        self.assertEqual(at.any_vasopressor_flag(0, 0, 5.0), 1)
        self.assertEqual(at.any_vasopressor_flag(None, None, None), 0)

    def test_phenylephrine_predominant_flag(self):
        # phe=200ug vs eph=1mg (->10 PHE-eq): phe dominant -> 1
        self.assertEqual(at.phenylephrine_predominant_flag(200.0, 1.0), 1)
        # phe=50ug vs eph=10mg (->100 PHE-eq): ephedrine dominant -> 0
        self.assertEqual(at.phenylephrine_predominant_flag(50.0, 10.0), 0)
        # no phe at all -> 0
        self.assertEqual(at.phenylephrine_predominant_flag(0.0, 5.0), 0)


class TestTimeToTreatCore(unittest.TestCase):

    def test_first_hypotension_onset(self):
        # MAP dips below 65 first at t=30.
        series = [(0.0, 80.0), (10.0, 70.0), (30.0, 60.0), (40.0, 55.0)]
        self.assertEqual(at.first_hypotension_onset(series), 30.0)

    def test_hypotension_gate_rejects_artifact(self):
        # A 10 mmHg artifact (< MAP_MIN=20) must be ignored; real dip at t=50.
        series = [(0.0, 80.0), (20.0, 5.0), (50.0, 60.0)]
        self.assertEqual(at.first_hypotension_onset(series), 50.0)

    def test_no_hypotension_returns_none(self):
        series = [(0.0, 80.0), (10.0, 75.0)]
        self.assertIsNone(at.first_hypotension_onset(series))

    def test_first_pressor_onset(self):
        series = [(0.0, 0.0), (10.0, 0.0), (25.0, 5.0), (30.0, 8.0)]
        self.assertEqual(at.first_pressor_onset(series), 25.0)

    def test_pressor_never_runs(self):
        self.assertIsNone(at.first_pressor_onset([(0.0, 0.0), (10.0, 0.0)]))

    def test_treatment_lag_treated(self):
        r = at.treatment_lag_minutes(hypo_onset_s=120.0, pressor_onset_s=300.0)
        self.assertEqual(r["level"], "treated")
        self.assertAlmostEqual(r["lag_min"], 3.0)   # (300-120)/60

    def test_treatment_lag_preemptive_clamped_to_zero(self):
        r = at.treatment_lag_minutes(hypo_onset_s=300.0, pressor_onset_s=120.0)
        self.assertEqual(r["level"], "treated")
        self.assertEqual(r["lag_min"], 0.0)

    def test_treatment_lag_untreated(self):
        r = at.treatment_lag_minutes(hypo_onset_s=120.0, pressor_onset_s=None)
        self.assertEqual(r["level"], "untreated")
        self.assertIsNone(r["lag_min"])

    def test_treatment_lag_no_hypotension(self):
        r = at.treatment_lag_minutes(hypo_onset_s=None, pressor_onset_s=200.0)
        self.assertEqual(r["level"], "no_hypotension")
        self.assertIsNone(r["lag_min"])


class TestBenjaminiHochberg(unittest.TestCase):

    def test_all_significant(self):
        rej = at.benjamini_hochberg([0.001, 0.002, 0.003], alpha=0.05)
        self.assertTrue(all(rej))

    def test_none_significant(self):
        rej = at.benjamini_hochberg([0.9, 0.8, 0.95], alpha=0.05)
        self.assertFalse(any(rej))

    def test_handles_none_and_nonfinite(self):
        rej = at.benjamini_hochberg([None, float("nan"), 0.001], alpha=0.05)
        self.assertEqual(len(rej), 3)
        self.assertTrue(rej[2])
        self.assertFalse(rej[0])

    def test_empty(self):
        self.assertEqual(at.benjamini_hochberg([]), [])


class TestImportSafety(unittest.TestCase):
    """The module + run entry point must import without numpy/pandas/sklearn."""

    def test_run_entry_point_is_importable(self):
        self.assertTrue(callable(at.run_actionable_targets))
        self.assertTrue(callable(at.build_cohort))
        self.assertTrue(callable(at.define_exposures))

    def test_constants_present(self):
        self.assertEqual(at.MIN_EVENTS_FOR_POWER, 15)
        self.assertIn("phe_vs_norepi", at.ACTIONABLE_EXPOSURES)
        self.assertIn("slow_treat", at.ACTIONABLE_EXPOSURES)
        self.assertEqual(at.NEGATIVE_CONTROL_OUTCOME, "organ_hepatocellular")


if __name__ == "__main__":
    unittest.main(verbosity=2)
