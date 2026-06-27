"""test_capnogram.py -- Offline unit tests for the capnogram EtCO2-dynamics family.

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built series with KNOWN expected
direction (a falling-EtCO2 case vs a stable one; low-EtCO2 fraction; baseline
vs late decline; empty -> None).  Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_capnogram -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.capnogram import (
    # Module-level constants
    SPECS,
    ETCO2_LOW_THR, ETCO2_MIN, ETCO2_MAX,
    BASELINE_WINDOW_S, SUSTAINED_WINDOW_S, MIN_USABLE_SAMPLES,
    # Pure helpers under test
    _time_weighted_mean,
    _sd,
    _frac_time_below,
    _baseline_median,
    _min_sustained,
    _etco2_decline,
    _phase3_slope_stub,
    # Window helpers
    _intraop_window,
    _clip_to_window,
    _filter_physiologic,
)
from vitaldb_aki.features.base import audit_specs, LeakageError


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
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in capnogram SPECS")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "capno_available",
                         "First spec must be capno_available")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "capno_available",
            "capno_etco2_mean",
            "capno_etco2_min",
            "capno_etco2_decline",
            "capno_etco2_variability",
            "capno_etco2_low_frac",
            "capno_phase3_slope_available",
        }
        self.assertFalse(required - names, f"Missing capnogram specs: {required - names}")

    def test_comprehensive_features_are_comprehensive(self):
        for s in SPECS:
            if s.name != "capno_phase3_slope_available":
                self.assertEqual(s.fset, "comprehensive", f"{s.name} fset={s.fset!r}")

    def test_deferred_feature_is_pk(self):
        deferred = [s for s in SPECS if s.name == "capno_phase3_slope_available"]
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0].fset, "pk",
                         "capno_phase3_slope_available must be in the pk tier")


# ===========================================================================
# 2. _time_weighted_mean
# ===========================================================================

class TestTimeWeightedMean(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_time_weighted_mean([]))
        self.assertIsNone(_time_weighted_mean([(0.0, 35.0)]))

    def test_constant_series(self):
        s = [(i * 5.0, 40.0) for i in range(10)]
        self.assertAlmostEqual(_time_weighted_mean(s), 40.0, places=6)

    def test_weights_by_dwell_time(self):
        """A value held for longer dominates the mean."""
        # 35 held 5 s, then 20 held 100 s (capped at MAX_INTER_SAMPLE_DT_S).
        s = [(0.0, 35.0), (5.0, 20.0), (105.0, 20.0)]
        m = _time_weighted_mean(s)
        self.assertIsNotNone(m)
        # Closer to 20 than to 35 because 20 dwells longer.
        self.assertLess(m, 30.0)


# ===========================================================================
# 3. _sd
# ===========================================================================

class TestSD(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_sd([]))
        self.assertIsNone(_sd([(0.0, 35.0)]))

    def test_zero_for_flat(self):
        s = [(i * 5.0, 40.0) for i in range(10)]
        self.assertAlmostEqual(_sd(s), 0.0, places=6)

    def test_higher_for_more_variable(self):
        stable = [(i * 5.0, 40.0 + (0.5 if i % 2 else -0.5)) for i in range(20)]
        labile = [(i * 5.0, 40.0 + (10.0 if i % 2 else -10.0)) for i in range(20)]
        self.assertLess(_sd(stable), _sd(labile),
                        "A more variable EtCO2 series must have higher SD")

    def test_known_value(self):
        # values 10, 20, 30 -> sample sd (ddof=1) = 10.0
        s = [(0.0, 10.0), (5.0, 20.0), (10.0, 30.0)]
        self.assertAlmostEqual(_sd(s), 10.0, places=6)


# ===========================================================================
# 4. _frac_time_below (low-EtCO2 fraction)
# ===========================================================================

class TestFracTimeBelow(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_frac_time_below([], ETCO2_LOW_THR))
        self.assertIsNone(_frac_time_below([(0.0, 20.0)], ETCO2_LOW_THR))

    def test_zero_when_all_above(self):
        s = [(i * 5.0, 40.0) for i in range(10)]  # all >= 30
        self.assertAlmostEqual(_frac_time_below(s, ETCO2_LOW_THR), 0.0, places=6)

    def test_one_when_all_below(self):
        s = [(i * 5.0, 20.0) for i in range(10)]  # all < 30
        self.assertAlmostEqual(_frac_time_below(s, ETCO2_LOW_THR), 1.0, places=6)

    def test_half_when_half_below(self):
        """First half < 30, second half >= 30 => fraction ~0.5."""
        # 5 s spacing keeps every gap under the cap so each interval weighs equally.
        low = [(i * 5.0, 25.0) for i in range(10)]
        high = [(50.0 + i * 5.0, 40.0) for i in range(10)]
        s = low + high
        frac = _frac_time_below(s, ETCO2_LOW_THR)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.4)
        self.assertLess(frac, 0.6)

    def test_returns_in_unit_interval(self):
        s = [(i * 5.0, 28.0 if i % 3 == 0 else 35.0) for i in range(30)]
        frac = _frac_time_below(s, ETCO2_LOW_THR)
        self.assertIsNotNone(frac)
        self.assertGreaterEqual(frac, 0.0)
        self.assertLessEqual(frac, 1.0)


# ===========================================================================
# 5. _baseline_median
# ===========================================================================

class TestBaselineMedian(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(_baseline_median([]))

    def test_median_of_first_window_only(self):
        """Only the first BASELINE_WINDOW_S seconds count toward the baseline."""
        # Baseline region (t <= 300): values 40; later region: values 20.
        base = [(i * 30.0, 40.0) for i in range(10)]      # t = 0..270 (<=300)
        late = [(330.0 + i * 30.0, 20.0) for i in range(10)]
        s = base + late
        self.assertAlmostEqual(_baseline_median(s, BASELINE_WINDOW_S), 40.0, places=6)

    def test_median_value(self):
        s = [(0.0, 30.0), (10.0, 40.0), (20.0, 50.0)]  # all within 300 s
        self.assertAlmostEqual(_baseline_median(s, BASELINE_WINDOW_S), 40.0, places=6)


# ===========================================================================
# 6. _min_sustained (artifact-robust low)
# ===========================================================================

class TestMinSustained(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_min_sustained([]))
        self.assertIsNone(_min_sustained([(0.0, 40.0)]))

    def test_ignores_single_sample_dip(self):
        """A lone one-sample dip must NOT become the sustained minimum."""
        # Mostly 40, with a single isolated 5 mmHg artifact spike-down.
        s = [(i * 30.0, 40.0) for i in range(20)]
        s[10] = (300.0, 5.0)  # single-sample artifact
        m = _min_sustained(s, SUSTAINED_WINDOW_S)
        self.assertIsNotNone(m)
        # The sustained min should stay well above the artifact value of 5.
        self.assertGreater(m, 30.0,
                           "A single-sample dip must not drive the sustained min")

    def test_captures_sustained_low_plateau(self):
        """A genuine sustained low plateau should be reflected in the minimum."""
        # First 600 s at 40, then a sustained 600 s plateau at 22.
        high = [(i * 30.0, 40.0) for i in range(20)]      # t = 0..570
        low = [(600.0 + i * 30.0, 22.0) for i in range(20)]  # sustained low
        s = high + low
        m = _min_sustained(s, SUSTAINED_WINDOW_S)
        self.assertIsNotNone(m)
        self.assertLess(m, 25.0,
                        "A sustained low plateau must lower the sustained minimum")
        self.assertGreater(m, 20.0)


# ===========================================================================
# 7. _etco2_decline (the headline trajectory metric)
# ===========================================================================

class TestEtco2Decline(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(_etco2_decline([]))

    def test_zero_for_stable_case(self):
        """A stable EtCO2 case has ~no decline."""
        stable = [(i * 30.0, 38.0) for i in range(40)]
        d = _etco2_decline(stable)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.0, places=4,
                               msg="Stable EtCO2 should have ~zero decline")

    def test_positive_for_falling_case(self):
        """A falling-EtCO2 case (baseline 40 -> sustained 20) declines ~0.5."""
        base = [(i * 30.0, 40.0) for i in range(20)]          # baseline window
        fall = [(600.0 + i * 30.0, 20.0) for i in range(20)]  # sustained drop
        s = base + fall
        d = _etco2_decline(s)
        self.assertIsNotNone(d)
        self.assertGreater(d, 0.3,
                           "Baseline 40 -> sustained 20 should be a clear decline")
        self.assertLessEqual(d, 1.0)

    def test_falling_exceeds_stable(self):
        """A falling case must report a larger decline than a stable one."""
        stable = [(i * 30.0, 38.0) for i in range(40)]
        base = [(i * 30.0, 40.0) for i in range(20)]
        fall = [(600.0 + i * 30.0, 22.0) for i in range(20)]
        falling = base + fall
        d_stable = _etco2_decline(stable)
        d_falling = _etco2_decline(falling)
        self.assertIsNotNone(d_stable)
        self.assertIsNotNone(d_falling)
        self.assertGreater(d_falling, d_stable,
                           "Falling-EtCO2 case must out-decline the stable case")

    def test_clamped_to_unit_interval(self):
        """Even an extreme drop is clamped into [0, 1]."""
        base = [(i * 30.0, 60.0) for i in range(20)]
        fall = [(600.0 + i * 30.0, 6.0) for i in range(20)]
        d = _etco2_decline(base + fall)
        self.assertIsNotNone(d)
        self.assertGreaterEqual(d, 0.0)
        self.assertLessEqual(d, 1.0)

    def test_no_decline_when_rising(self):
        """A rising EtCO2 (baseline low, later high) clamps to 0 (no decline)."""
        base = [(i * 30.0, 25.0) for i in range(20)]
        rise = [(600.0 + i * 30.0, 45.0) for i in range(20)]
        d = _etco2_decline(base + rise)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.0, places=4,
                               msg="A rising EtCO2 should clamp to zero decline")


# ===========================================================================
# 8. Window helpers + leakage cutoff
# ===========================================================================

class TestWindowHelpers(unittest.TestCase):
    def test_intraop_window_prefers_anestart(self):
        case = {"anestart": 100.0, "opstart": 200.0, "opend": 3600.0}
        self.assertEqual(_intraop_window(case), (100.0, 3600.0))

    def test_intraop_window_falls_back_to_opstart(self):
        case = {"opstart": 200.0, "opend": 3600.0}
        self.assertEqual(_intraop_window(case), (200.0, 3600.0))

    def test_intraop_window_none_without_opend(self):
        self.assertEqual(_intraop_window({"anestart": 0.0}), (None, None))

    def test_clip_respects_cutoff(self):
        """No sample at t > opend survives clipping (leakage firewall)."""
        opend = 300.0
        s = [(i * 60.0, 35.0) for i in range(10)]  # t = 0..540, some > opend
        clipped = _clip_to_window(s, 0.0, opend)
        self.assertTrue(all(t <= opend for t, _ in clipped))
        self.assertTrue(len(clipped) < len(s))

    def test_filter_physiologic_drops_artifacts(self):
        s = [(0.0, 40.0), (5.0, 0.0), (10.0, 90.0), (15.0, 35.0)]
        kept = _filter_physiologic(s, ETCO2_MIN, ETCO2_MAX)
        self.assertEqual(kept, [(0.0, 40.0), (15.0, 35.0)])


# ===========================================================================
# 9. Deferred phase-III stub
# ===========================================================================

class TestPhase3Stub(unittest.TestCase):
    def test_stub_raises_not_implemented(self):
        """The deferred phase-III slope must be an explicit NotImplemented stub."""
        with self.assertRaises(NotImplementedError):
            _phase3_slope_stub([(0.0, 0.0), (0.1, 38.0)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
