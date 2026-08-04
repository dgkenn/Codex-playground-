"""test_autonomic.py -- Offline unit tests for the Autonomic Reserve family (UNMINED axis).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
They exercise the Tier-A coarse-HRV pure helpers (_hr_to_rr_ms, _sdnn, _rmssd,
_cv) against hand-built series with KNOWN expected direction/value, plus the
module-level spec invariants and the deferred Tier-B stubs.  Mirrors
tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_autonomic -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.autonomic import (
    SPECS,
    HR_MIN, HR_MAX, MIN_HR_SAMPLES,
    _hr_to_rr_ms,
    _sdnn,
    _rmssd,
    _cv,
    _detect_r_peaks,
    _hrv_from_rr_ms,
    _brs_sequence_method,
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
                         "Duplicate feature names in autonomic SPECS")

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "auto_available",
                         "First spec must be auto_available (contract)")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "auto_available",
            "auto_hr_sdnn_coarse",
            "auto_hr_rmssd_coarse",
            "auto_hr_cv_coarse",
            "auto_hrv_rmssd",
            "auto_hrv_sdnn",
            "auto_hrv_lfhf",
            "auto_brs_seq",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing autonomic specs: {missing}")

    def test_coarse_features_are_comprehensive(self):
        comp = {s.name for s in SPECS if s.fset == "comprehensive"}
        for n in ("auto_available", "auto_hr_sdnn_coarse",
                  "auto_hr_rmssd_coarse", "auto_hr_cv_coarse"):
            self.assertIn(n, comp, f"{n} should be in fset=comprehensive")

    def test_raw_tier_features_are_pk(self):
        pk = {s.name for s in SPECS if s.fset == "pk"}
        for n in ("auto_hrv_rmssd", "auto_hrv_sdnn", "auto_hrv_lfhf", "auto_brs_seq"):
            self.assertIn(n, pk, f"{n} (raw tier) should be in fset=pk")


# ===========================================================================
# 2. _hr_to_rr_ms : HR (bpm) -> RR_ms proxy
# ===========================================================================

class TestHrToRrMs(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(_hr_to_rr_ms([]), [])

    def test_known_conversion_60bpm(self):
        """HR=60 bpm => RR = 1000 ms exactly."""
        self.assertEqual(_hr_to_rr_ms([60.0]), [1000.0])

    def test_known_conversion_multiple(self):
        """60->1000, 120->500, 75->800."""
        out = _hr_to_rr_ms([60.0, 120.0, 75.0])
        self.assertAlmostEqual(out[0], 1000.0)
        self.assertAlmostEqual(out[1], 500.0)
        self.assertAlmostEqual(out[2], 800.0)

    def test_drops_nonpositive_hr(self):
        """HR <= 0 cannot be inverted and is skipped."""
        out = _hr_to_rr_ms([60.0, 0.0, -10.0, 120.0])
        self.assertEqual(out, [1000.0, 500.0])

    def test_skips_none(self):
        out = _hr_to_rr_ms([60.0, None, 120.0])
        self.assertEqual(out, [1000.0, 500.0])


# ===========================================================================
# 3. _sdnn : SD of the RR_ms proxy
# ===========================================================================

class TestSdnn(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(_sdnn([]))

    def test_single_value_returns_none(self):
        self.assertIsNone(_sdnn([1000.0]))

    def test_constant_series_zero(self):
        """No variability => SD = 0."""
        result = _sdnn([1000.0] * 10)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=9)

    def test_known_sd(self):
        """Population SD of [800, 1200] = 200."""
        result = _sdnn([800.0, 1200.0])
        self.assertAlmostEqual(result, 200.0, places=6)

    def test_low_variability_less_than_high(self):
        """A low-variability RR series has smaller SDNN than a high-variability one."""
        # Low-variability HR (tight around 80 bpm) vs high-variability HR.
        low_rr = _hr_to_rr_ms([79.0, 80.0, 81.0, 80.0, 79.0, 81.0, 80.0])
        high_rr = _hr_to_rr_ms([55.0, 110.0, 60.0, 130.0, 50.0, 120.0, 70.0])
        s_low = _sdnn(low_rr)
        s_high = _sdnn(high_rr)
        self.assertIsNotNone(s_low)
        self.assertIsNotNone(s_high)
        self.assertLess(s_low, s_high,
                        "Low HR variability should give smaller coarse SDNN")


# ===========================================================================
# 4. _rmssd : RMS of successive differences of the RR_ms proxy
# ===========================================================================

class TestRmssd(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(_rmssd([]))

    def test_single_value_returns_none(self):
        self.assertIsNone(_rmssd([1000.0]))

    def test_constant_series_zero(self):
        result = _rmssd([1000.0] * 8)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=9)

    def test_known_sequence(self):
        """RR = [1000, 1010, 990, 1000]: diffs = [10, -20, 10];
        sum of squares = 100 + 400 + 100 = 600; mean over (n-1)=3 = 200;
        sqrt(200) ~= 14.142135623."""
        result = _rmssd([1000.0, 1010.0, 990.0, 1000.0])
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, math.sqrt(200.0), places=6)

    def test_alternating_known(self):
        """RR alternating [1000, 1100, 1000, 1100]: every diff magnitude = 100;
        diffs=[100,-100,100]; mean square = 10000; sqrt = 100."""
        result = _rmssd([1000.0, 1100.0, 1000.0, 1100.0])
        self.assertAlmostEqual(result, 100.0, places=6)

    def test_low_variability_less_than_high(self):
        low_rr = _hr_to_rr_ms([80.0, 80.0, 81.0, 80.0, 80.0])
        high_rr = _hr_to_rr_ms([60.0, 120.0, 55.0, 130.0, 50.0])
        r_low = _rmssd(low_rr)
        r_high = _rmssd(high_rr)
        self.assertIsNotNone(r_low)
        self.assertIsNotNone(r_high)
        self.assertLess(r_low, r_high,
                        "Low beat-to-beat HR change should give smaller coarse RMSSD")


# ===========================================================================
# 5. _cv : coefficient of variation of HR
# ===========================================================================

class TestCv(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(_cv([]))

    def test_single_value_returns_none(self):
        self.assertIsNone(_cv([80.0]))

    def test_constant_series_zero(self):
        result = _cv([80.0] * 10)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=9)

    def test_nonpositive_mean_returns_none(self):
        """Mean <= 0 makes CV undefined (guard); use a series averaging to 0."""
        self.assertIsNone(_cv([-5.0, 5.0]))

    def test_known_cv(self):
        """[60, 100]: mean=80, pop SD=20 => CV = 0.25."""
        result = _cv([60.0, 100.0])
        self.assertAlmostEqual(result, 0.25, places=6)

    def test_low_variability_less_than_high(self):
        low = [80.0, 81.0, 79.0, 80.0, 80.0]
        high = [55.0, 120.0, 60.0, 130.0, 50.0]
        c_low = _cv(low)
        c_high = _cv(high)
        self.assertIsNotNone(c_low)
        self.assertIsNotNone(c_high)
        self.assertLess(c_low, c_high,
                        "Low HR variability should give smaller coarse CV")


# ===========================================================================
# 6. Tier-B deferred stubs (default OFF)
# ===========================================================================

class TestDeferredRawTier(unittest.TestCase):
    def test_r_peak_detector_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            _detect_r_peaks([(0.0, 0.1), (0.002, 0.2)])

    def test_hrv_from_rr_ms_returns_all_none(self):
        out = _hrv_from_rr_ms([800.0, 810.0, 790.0])
        self.assertEqual(set(out.keys()), {"rmssd", "sdnn", "lfhf"})
        for k, v in out.items():
            self.assertIsNone(v, f"deferred HRV {k} should be None")

    def test_brs_sequence_method_returns_none(self):
        self.assertIsNone(_brs_sequence_method([], []))


# ===========================================================================
# 7. Range-gate constants sanity
# ===========================================================================

class TestConstants(unittest.TestCase):
    def test_hr_gate_bounds(self):
        self.assertEqual(HR_MIN, 20.0)
        self.assertEqual(HR_MAX, 220.0)
        self.assertLess(HR_MIN, HR_MAX)

    def test_min_samples_positive(self):
        self.assertGreaterEqual(MIN_HR_SAMPLES, 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
