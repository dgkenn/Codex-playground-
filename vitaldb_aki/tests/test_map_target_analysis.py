"""test_map_target_analysis.py -- stdlib-light tests for the PURE helpers of
vitaldb_aki/analysis/map_target_analysis.py.

These deliberately avoid sklearn/pandas so they run fast and green in the
integrity-core environment. They cover the load-bearing pure logic:

  - e_value / e_value_ci          (VanderWeele; RR=2 -> ~3.41, CI-crossing -> 1)
  - incremental_band              (band = below_high - below_low, clamped >= 0)
  - top_tertile_mask              (>= 2/3 quantile; NaN excluded; ties -> top)
  - threshold_pairs               (consecutive (low, high) pairs)
  - import-safety without sklearn (run_map_target_analysis importable)

Run with:
    python3 -m unittest vitaldb_aki.tests.test_map_target_analysis -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from vitaldb_aki.analysis import map_target_analysis as mt


class TestEValue(unittest.TestCase):

    def test_rr_two_gives_341(self):
        self.assertAlmostEqual(mt.e_value(2.0), 3.4142, places=3)

    def test_protective_symmetry(self):
        self.assertAlmostEqual(mt.e_value(0.5), mt.e_value(2.0), places=6)

    def test_null_and_nonfinite(self):
        self.assertEqual(mt.e_value(1.0), 1.0)
        self.assertEqual(mt.e_value(0.0), 1.0)
        self.assertEqual(mt.e_value(-3.0), 1.0)
        self.assertEqual(mt.e_value(float("nan")), 1.0)

    def test_rr_15_known(self):
        self.assertAlmostEqual(mt.e_value(1.5), 1.5 + math.sqrt(0.75), places=6)

    def test_ci_crossing_null_is_one(self):
        # CI spans 1 -> not significant -> E-value of CI is 1.0
        self.assertEqual(mt.e_value_ci(1.3, 0.8, 2.0), 1.0)

    def test_ci_harmful_uses_lower_bound(self):
        # Harmful point (RR>1), CI entirely >1 -> nearest-null bound is the lower.
        self.assertAlmostEqual(mt.e_value_ci(2.0, 1.2, 3.0), mt.e_value(1.2), places=6)

    def test_ci_protective_uses_upper_bound(self):
        # Protective point (RR<1), CI entirely <1 -> nearest-null bound is the upper.
        self.assertAlmostEqual(mt.e_value_ci(0.5, 0.3, 0.8), mt.e_value(0.8), places=6)


class TestIncrementalBand(unittest.TestCase):

    def test_band_is_difference(self):
        # below-75 always >= below-65; band = below_75 - below_65.
        bmin, bauc = mt.incremental_band(
            min_below_low=10.0, min_below_high=18.0,
            auc_below_low=120.0, auc_below_high=200.0)
        self.assertEqual(bmin, 8.0)
        self.assertEqual(bauc, 80.0)

    def test_band_clamped_nonnegative(self):
        # float noise can make high < low by a hair -> clamp to 0, never negative.
        bmin, bauc = mt.incremental_band(5.0, 4.999, 50.0, 49.0)
        self.assertEqual(bmin, 0.0)
        self.assertEqual(bauc, 0.0)

    def test_zero_band_when_equal(self):
        bmin, bauc = mt.incremental_band(7.0, 7.0, 7.0, 7.0)
        self.assertEqual(bmin, 0.0)
        self.assertEqual(bauc, 0.0)


class TestTopTertile(unittest.TestCase):

    def test_top_tertile_selects_upper_third(self):
        vals = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        mask = list(mt.top_tertile_mask(vals))
        # 2/3 quantile of 0..8 is ~5.33; >= cut flags the top ~third.
        flagged = [v for v, m in zip(vals, mask) if m]
        self.assertTrue(all(v >= 5 for v in flagged))
        self.assertGreaterEqual(len(flagged), 2)
        self.assertLess(len(flagged), len(vals))

    def test_nan_excluded(self):
        vals = [1.0, float("nan"), 9.0, 2.0]
        mask = list(mt.top_tertile_mask(vals))
        self.assertFalse(mask[1])   # NaN never flagged

    def test_all_nan_empty(self):
        vals = [float("nan"), float("nan")]
        mask = list(mt.top_tertile_mask(vals))
        self.assertFalse(any(mask))


class TestThresholdPairs(unittest.TestCase):

    def test_consecutive_pairs(self):
        pairs = mt.threshold_pairs((50, 55, 60, 65))
        self.assertEqual(pairs, [(50, 55), (55, 60), (60, 65)])

    def test_default_includes_65_75(self):
        pairs = mt.threshold_pairs()
        self.assertIn((65, 70), pairs)
        self.assertIn((70, 75), pairs)


class TestImportSafety(unittest.TestCase):

    def test_public_entry_importable(self):
        # Module + entry point import without sklearn/pandas loaded eagerly.
        self.assertTrue(callable(mt.run_map_target_analysis))
        self.assertTrue(callable(mt.incremental_band_test))
        self.assertTrue(callable(mt.modifiable_exposure_iptw))

    def test_constants_documented(self):
        self.assertEqual(mt.PRIMARY_OUTCOME, "organ_renal")
        self.assertEqual(mt.NEGATIVE_CONTROL_OUTCOME, "organ_cholestatic")
        self.assertIn("cum_vasopressor_dose", mt.CONFOUNDERS)
        self.assertEqual(mt.UNDERPOWERED_EVENTS, 15)


if __name__ == "__main__":
    unittest.main()
