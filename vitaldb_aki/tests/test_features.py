"""Tests for the feature contract + tabular extraction (Sec 7, 11) -- stdlib only."""
from __future__ import annotations
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from vitaldb_aki.features.base import FeatureSpec, audit_specs, names_for_set, LeakageError
from vitaldb_aki.features import tabular


class TestContract(unittest.TestCase):
    def test_postop_timing_is_rejected(self):
        with self.assertRaises(LeakageError):
            audit_specs([FeatureSpec("icu_days", "comprehensive", "postop")])

    def test_nested_sets(self):
        std = set(names_for_set(tabular.SPECS, "standard"))
        comp = set(names_for_set(tabular.SPECS, "comprehensive"))
        self.assertTrue(std.issubset(comp))        # nested (Sec 9)
        self.assertIn("age", std)
        self.assertIn("preop_alb", comp)
        self.assertNotIn("preop_alb", std)

    def test_specs_pass_leakage_audit(self):
        audit_specs(tabular.SPECS)                  # no postop feature ships


class TestCKDEPI(unittest.TestCase):
    def test_known_value(self):
        # 60yo male, Scr 0.9 -> ~98-100; female same -> a bit lower (x1.012, kappa shift)
        m = tabular.ckd_epi_2021(0.9, 60, 1)
        f = tabular.ckd_epi_2021(0.9, 60, 0)
        self.assertTrue(95 <= m <= 103, m)
        self.assertTrue(f < m)
        self.assertIsNone(tabular.ckd_epi_2021(None, 60, 1))


class TestExtract(unittest.TestCase):
    def test_extract_minimal_case(self):
        cases = {"7": {"caseid": "7", "age": "55", "sex": "M", "bmi": "24",
                       "asa": "2", "emop": "0", "preop_cr": "1.0", "preop_hb": "10.5",
                       "preop_alb": "3.0", "opstart": "1000", "opend": "8200",
                       "preop_htn": "1", "preop_dm": "0", "intraop_ebl": "300"}}
        f = tabular.extract({}, cases, ["7"])["7"]
        self.assertEqual(f["sex_male"], 1)
        self.assertEqual(f["anemia_flag"], 1)            # Hb 10.5 < 13 (M)
        self.assertEqual(f["hypoalbuminemia_flag"], 1)   # alb 3.0 < 3.5
        self.assertEqual(f["surgery_duration_min"], 120.0)
        self.assertEqual(f["intraop_ebl"], 300.0)
        self.assertIsNotNone(f["egfr_ckdepi"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
