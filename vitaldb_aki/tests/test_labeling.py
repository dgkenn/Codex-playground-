"""Unit tests for KDIGO labeling + eligibility (Sec 5/6) -- stdlib only, no network."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.cohort.eligibility import check_eligibility
from vitaldb_aki.cohort.labeling import label_case

H = 3600.0
KCFG = {"abs_rise_mgdl": 0.3, "abs_window_h": 48, "rel_ratio": 1.5, "rel_window_h": 168}


def _label(baseline, postop):
    return label_case("c", baseline, "preop_cr", postop, KCFG)


class TestKDIGO(unittest.TestCase):
    def test_no_aki_small_rise(self):
        r = _label(0.82, [(1 * H, 0.88), (160 * H, 0.91)])  # case 1 from real data
        self.assertEqual(r.aki, 0)
        self.assertEqual(r.stage, 0)

    def test_abs_rise_within_48h(self):
        r = _label(1.0, [(10 * H, 1.35)])      # +0.35 >= 0.3 within 48h
        self.assertEqual(r.aki, 1)
        self.assertEqual(r.stage, 1)

    def test_abs_rise_outside_48h_does_not_fire_abs(self):
        # +0.35 but at 72h -> abs criterion (48h) misses; 1.35x < 1.5x so no rel.
        r = _label(1.0, [(72 * H, 1.35)])
        self.assertEqual(r.aki, 0)

    def test_rel_15x_within_7d(self):
        r = _label(1.0, [(100 * H, 1.6)])      # 1.6x >= 1.5x within 7d
        self.assertEqual(r.aki, 1)
        self.assertEqual(r.stage, 1)

    def test_rel_outside_7d_misses(self):
        r = _label(1.0, [(200 * H, 1.6)])      # 8.3 days -> outside 7d window
        self.assertEqual(r.aki, 0)

    def test_stage2_and_stage3(self):
        self.assertEqual(_label(1.0, [(24 * H, 2.2)]).stage, 2)   # 2.2x
        self.assertEqual(_label(1.0, [(24 * H, 3.5)]).stage, 3)   # 3.5x
        self.assertEqual(_label(1.0, [(24 * H, 4.1)]).stage, 3)   # >=4.0 absolute

    def test_unlabelable_no_baseline(self):
        self.assertIsNone(_label(None, [(10 * H, 2.0)]).aki)

    def test_unlabelable_no_postop(self):
        self.assertIsNone(_label(1.0, []).aki)


class TestEligibility(unittest.TestCase):
    CFG = {"cohort": {"min_age_years": 18, "exclude_cardiac": True, "exclude_obstetric": True,
                      "exclude_transplant": True, "exclude_av_fistula": True,
                      "exclude_preexisting_esrd": True, "esrd_baseline_cr_mgdl": 4.0}}

    def _case(self, **kw):
        base = {"age": "50", "optype": "General surgery", "opname": "x", "dx": "", "department": "GS", "preop_cr": "0.9"}
        base.update(kw)
        return base

    def test_adult_general_eligible(self):
        ok, _ = check_eligibility(self._case(), self.CFG)
        self.assertTrue(ok)

    def test_minor_excluded(self):
        ok, why = check_eligibility(self._case(age="15"), self.CFG)
        self.assertFalse(ok); self.assertIn("age", why)

    def test_cardiac_excluded(self):
        ok, why = check_eligibility(self._case(optype="Cardiac surgery", opname="CABG"), self.CFG)
        self.assertFalse(ok); self.assertIn("cardiac", why)

    def test_esrd_proxy_excluded(self):
        ok, why = check_eligibility(self._case(preop_cr="5.2"), self.CFG)
        self.assertFalse(ok); self.assertIn("ESRD", why)

    def test_obstetric_excluded(self):
        ok, why = check_eligibility(self._case(opname="Cesarean section"), self.CFG)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
