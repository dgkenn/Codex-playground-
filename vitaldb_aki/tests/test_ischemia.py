"""test_ischemia.py -- Offline unit tests for the ST-ischemia feature module.

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built series with a KNOWN expected
direction (sustained depression vs flat; multi-lead max deviation; empty->None).

Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_ischemia -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.ischemia import (
    # Module-level constants
    SPECS, ABN, ST_PHYS_MIN, ST_PHYS_MAX, ST_LEADS,
    # Pure helpers
    _max_abs_dev,
    _burden_beyond,
    _frac_time_abnormal,
)
from vitaldb_aki.features.base import audit_specs


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_audit_passes(self):
        """audit_specs() must not raise (no postop feature)."""
        audit_specs(SPECS)

    def test_no_postop_timing(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop",
                                msg=f"{s.name} has postop timing -- leakage!")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop",
                             msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in ischemia SPECS")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "isch_available",
                         "isch_available must be the FIRST spec")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "isch_available",
            "isch_st_max_dev",
            "isch_st_depression_burden",
            "isch_st_elevation_burden",
            "isch_st_time_abnormal_frac",
            "isch_n_leads",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing ischemia specs: {missing}")

    def test_all_comprehensive(self):
        for s in SPECS:
            self.assertEqual(s.fset, "comprehensive",
                             msg=f"{s.name} fset={s.fset!r}")


# ===========================================================================
# 2. _max_abs_dev -- multi-lead / per-lead max deviation
# ===========================================================================

class TestMaxAbsDev(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(_max_abs_dev([]))

    def test_picks_largest_magnitude(self):
        # Largest |ST| is the -0.4 depression sample.
        s = [(0.0, 0.05), (30.0, 0.2), (60.0, -0.4), (90.0, 0.1)]
        self.assertAlmostEqual(_max_abs_dev(s), 0.4, places=6)

    def test_handles_negative_and_positive(self):
        # +0.3 elevation is the max magnitude.
        s = [(0.0, -0.1), (30.0, 0.3), (60.0, -0.2)]
        self.assertAlmostEqual(_max_abs_dev(s), 0.3, places=6)

    def test_multi_lead_max_via_aggregation(self):
        """Aggregating per-lead maxima takes the cross-lead maximum."""
        lead_a = [(0.0, 0.1), (30.0, -0.2)]   # max |ST| = 0.2
        lead_b = [(0.0, 0.6), (30.0, 0.1)]    # max |ST| = 0.6  (winner)
        per_lead = [_max_abs_dev(lead_a), _max_abs_dev(lead_b)]
        self.assertAlmostEqual(max(per_lead), 0.6, places=6)


# ===========================================================================
# 3. _burden_beyond -- sustained depression vs flat
# ===========================================================================

class TestBurdenBeyond(unittest.TestCase):
    def test_flat_normal_lead_zero_burden(self):
        """A flat lead at 0 mV (well within +-ABN) has zero burden."""
        s = [(i * 30.0, 0.0) for i in range(20)]
        self.assertAlmostEqual(_burden_beyond(s, ABN, sign=-1), 0.0, places=9)
        self.assertAlmostEqual(_burden_beyond(s, ABN, sign=+1), 0.0, places=9)

    def test_sustained_depression_positive_burden(self):
        """A lead held at -0.3 mV (below -ABN) accrues depression burden."""
        # 11 samples at -0.3 mV, 30 s apart => 10 forward intervals, each dt
        # capped at MAX_INTER_SAMPLE_DT_S = 10 s.
        # excursion = (-(-0.3)) - 0.1 = 0.2 mV; dt = 10 s each (capped).
        # total = 0.2 * 10 * 10 = 20 mV.s = 0.333333 mV.min
        s = [(i * 30.0, -0.3) for i in range(11)]
        depr = _burden_beyond(s, ABN, sign=-1)
        self.assertAlmostEqual(depr, (0.2 * 10.0 * 10) / 60.0, places=6)
        # No elevation burden for a depressed lead.
        self.assertAlmostEqual(_burden_beyond(s, ABN, sign=+1), 0.0, places=9)

    def test_depression_beats_flat(self):
        """Sustained depression has strictly greater burden than a flat lead."""
        flat = [(i * 30.0, 0.0) for i in range(11)]
        depressed = [(i * 30.0, -0.3) for i in range(11)]
        self.assertGreater(
            _burden_beyond(depressed, ABN, sign=-1),
            _burden_beyond(flat, ABN, sign=-1),
        )

    def test_elevation_symmetric(self):
        """A lead held at +0.3 mV accrues the symmetric elevation burden."""
        s = [(i * 30.0, 0.3) for i in range(11)]
        elev = _burden_beyond(s, ABN, sign=+1)
        self.assertAlmostEqual(elev, (0.2 * 10.0 * 10) / 60.0, places=6)
        self.assertAlmostEqual(_burden_beyond(s, ABN, sign=-1), 0.0, places=9)

    def test_at_threshold_contributes_zero(self):
        """ST exactly at -ABN gives zero excursion (not abnormal beyond)."""
        s = [(i * 30.0, -ABN) for i in range(11)]
        self.assertAlmostEqual(_burden_beyond(s, ABN, sign=-1), 0.0, places=9)

    def test_gap_capped(self):
        """A huge inter-sample gap is capped at MAX_INTER_SAMPLE_DT_S (10 s)."""
        # Two samples 1000 s apart at -0.3 mV; dt capped to 10 s.
        # excursion 0.2 mV * 10 s = 2 mV.s = 0.033333 mV.min
        s = [(0.0, -0.3), (1000.0, -0.3)]
        depr = _burden_beyond(s, ABN, sign=-1)
        self.assertAlmostEqual(depr, (0.2 * 10.0) / 60.0, places=6)

    def test_too_few_samples_zero(self):
        self.assertEqual(_burden_beyond([(0.0, -0.5)], ABN, sign=-1), 0.0)
        self.assertEqual(_burden_beyond([], ABN, sign=-1), 0.0)


# ===========================================================================
# 4. _frac_time_abnormal -- union across leads
# ===========================================================================

class TestFracTimeAbnormal(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(_frac_time_abnormal([]))
        self.assertIsNone(_frac_time_abnormal([[]]))

    def test_none_when_single_sample(self):
        """A single time point gives no interval to integrate."""
        self.assertIsNone(_frac_time_abnormal([[(0.0, -0.5)]]))

    def test_zero_when_all_normal(self):
        """A flat normal lead => no abnormal time."""
        lead = [(i * 5.0, 0.0) for i in range(20)]
        self.assertAlmostEqual(_frac_time_abnormal([lead], ABN), 0.0, places=6)

    def test_one_when_single_lead_always_abnormal(self):
        """A lead held at -0.5 mV (|ST|>ABN) => abnormal nearly the whole time."""
        lead = [(i * 5.0, -0.5) for i in range(20)]
        frac = _frac_time_abnormal([lead], ABN)
        self.assertIsNotNone(frac)
        self.assertAlmostEqual(frac, 1.0, places=6)

    def test_union_across_leads(self):
        """Two leads, each abnormal on disjoint halves => union covers ~all time."""
        # Lead A abnormal in first half, normal in second.
        lead_a = [(i * 10.0, -0.5 if i < 10 else 0.0) for i in range(20)]
        # Lead B normal in first half, abnormal in second.
        lead_b = [(i * 10.0, 0.0 if i < 10 else -0.5) for i in range(20)]
        # Single-lead fractions are each ~0.5; the union should be ~1.0.
        frac_a = _frac_time_abnormal([lead_a], ABN)
        frac_union = _frac_time_abnormal([lead_a, lead_b], ABN)
        self.assertIsNotNone(frac_a)
        self.assertIsNotNone(frac_union)
        self.assertLess(frac_a, 0.6)
        self.assertGreater(frac_union, frac_a,
                           "Union of two leads must cover more time than one")
        self.assertGreater(frac_union, 0.9)

    def test_partial_fraction(self):
        """A lead abnormal for half its samples => ~0.5 abnormal fraction."""
        lead = [(i * 5.0, -0.5 if i < 10 else 0.0) for i in range(20)]
        frac = _frac_time_abnormal([lead], ABN)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.3)
        self.assertLess(frac, 0.7)


# ===========================================================================
# 5. Constants sanity
# ===========================================================================

class TestConstants(unittest.TestCase):
    def test_abn_is_one_mm(self):
        self.assertAlmostEqual(ABN, 0.1, places=6)  # 0.1 mV == 1 mm

    def test_phys_gate_symmetric(self):
        self.assertAlmostEqual(ST_PHYS_MIN, -2.0, places=6)
        self.assertAlmostEqual(ST_PHYS_MAX, 2.0, places=6)

    def test_st_leads_nonempty(self):
        self.assertGreater(len(ST_LEADS), 0)
        for lead in ST_LEADS:
            self.assertTrue(lead.startswith("Solar8000/ST_"),
                            f"{lead} is not a Solar8000 ST lead")


if __name__ == "__main__":
    unittest.main(verbosity=2)
