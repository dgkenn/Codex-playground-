"""test_fluid_responsiveness.py -- Offline unit tests for the advanced-hemodynamic
fluid-responsiveness / vasoplegia / low-output biomarker family (all fset="pk").

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built series with KNOWN expected direction
(high-SVV occult-hypovolemia case vs low; SVR decline / vasoplegia; empty -> None).

Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_fluid_responsiveness -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.fluid_responsiveness import (
    # Module-level constants
    SPECS,
    SVV_RESPONSIVE_THR, SVR_VASOPLEGIA_THR,
    SVV_MIN, SVV_MAX, SVR_MIN, SVR_MAX, CO_MIN, CO_MAX, CI_MIN, CI_MAX,
    # Pure helpers under test
    _time_weighted_mean,
    _frac_time_above,
    _frac_time_below,
    _min_gated,
    _max_gated,
    _filter_physiologic,
    _clip_to_window,
    _intraop_window,
)
from vitaldb_aki.features.base import audit_specs


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_audit_passes(self):
        """audit_specs() must not raise (no postop feature)."""
        audit_specs(SPECS)  # raises on violation

    def test_no_postop_timing(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop",
                                msg=f"{s.name} has postop timing -- leakage!")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop",
                             msg=f"{s.name} timing={s.timing!r}")

    def test_all_pk_tier(self):
        """Whole family is the advanced-hemodynamics subgroup => all fset='pk'."""
        for s in SPECS:
            self.assertEqual(s.fset, "pk",
                             msg=f"{s.name} fset={s.fset!r}; expected 'pk'")

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "fluid_available",
                         "First spec must be fluid_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "fluid_available",
            "fluid_svv_mean", "fluid_svv_max", "fluid_svv_high_frac",
            "fluid_svr_mean", "fluid_svr_min", "fluid_svr_low_frac",
            "fluid_co_mean", "fluid_ci_min",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 9, "Expected exactly 9 feature specs")


# ===========================================================================
# 2. _time_weighted_mean
# ===========================================================================

class TestTimeWeightedMean(unittest.TestCase):
    def test_constant_series(self):
        """Constant value => time-weighted mean equals that value."""
        s = [(i * 30.0, 7.0) for i in range(10)]
        self.assertAlmostEqual(_time_weighted_mean(s), 7.0, places=6)

    def test_none_when_too_few_samples(self):
        self.assertIsNone(_time_weighted_mean([(0.0, 5.0)]))
        self.assertIsNone(_time_weighted_mean([]))

    def test_high_svv_case_vs_low(self):
        """High-SVV (occult hypovolemia) case has a larger mean than a low case."""
        high = [(i * 30.0, 18.0) for i in range(10)]  # all fluid-responsive
        low = [(i * 30.0, 6.0) for i in range(10)]    # well-filled
        m_high = _time_weighted_mean(high)
        m_low = _time_weighted_mean(low)
        self.assertIsNotNone(m_high)
        self.assertIsNotNone(m_low)
        self.assertGreater(m_high, m_low,
                           "Occult-hypovolemia case should have higher mean SVV")

    def test_gap_cap_weights_later_value(self):
        """A huge final gap is capped, so the early value dominates as expected."""
        # value 10 held briefly, then value 20 with a giant (capped) gap
        s = [(0.0, 10.0), (5.0, 20.0), (100000.0, 20.0)]
        m = _time_weighted_mean(s)
        # first interval dt=5 (val 10); second interval capped to 10 (val 20)
        # mean = (10*5 + 20*10) / 15
        self.assertAlmostEqual(m, (10 * 5 + 20 * 10) / 15.0, places=6)


# ===========================================================================
# 3. _frac_time_above (SVV high fraction -- occult hypovolemia burden)
# ===========================================================================

class TestFracTimeAbove(unittest.TestCase):
    def test_all_above(self):
        """SVV always > 13 % => fraction ~ 1.0."""
        s = [(i * 30.0, 20.0) for i in range(10)]
        self.assertAlmostEqual(_frac_time_above(s, SVV_RESPONSIVE_THR), 1.0, places=4)

    def test_none_above(self):
        """SVV always below threshold => fraction 0.0."""
        s = [(i * 30.0, 5.0) for i in range(10)]
        self.assertAlmostEqual(_frac_time_above(s, SVV_RESPONSIVE_THR), 0.0, places=4)

    def test_half_above(self):
        """First half above 13, second half below => ~0.5."""
        s = [(i * 30.0, 20.0 if i < 10 else 5.0) for i in range(20)]
        frac = _frac_time_above(s, SVV_RESPONSIVE_THR)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.3)
        self.assertLess(frac, 0.7)

    def test_high_case_greater_than_low_case(self):
        high = [(i * 30.0, 20.0) for i in range(10)]
        low = [(i * 30.0, 5.0) for i in range(10)]
        self.assertGreater(_frac_time_above(high, SVV_RESPONSIVE_THR),
                           _frac_time_above(low, SVV_RESPONSIVE_THR))

    def test_strict_inequality_at_threshold(self):
        """Exactly 13 is NOT above 13 (strict)."""
        s = [(i * 30.0, SVV_RESPONSIVE_THR) for i in range(10)]
        self.assertAlmostEqual(_frac_time_above(s, SVV_RESPONSIVE_THR), 0.0, places=4)

    def test_none_when_too_few_samples(self):
        self.assertIsNone(_frac_time_above([(0.0, 20.0)], SVV_RESPONSIVE_THR))
        self.assertIsNone(_frac_time_above([], SVV_RESPONSIVE_THR))


# ===========================================================================
# 4. _frac_time_below (SVR low fraction -- vasoplegia burden / SVR decline)
# ===========================================================================

class TestFracTimeBelow(unittest.TestCase):
    def test_all_below(self):
        """SVR always < 800 => vasoplegia fraction ~ 1.0."""
        s = [(i * 30.0, 600.0) for i in range(10)]
        self.assertAlmostEqual(_frac_time_below(s, SVR_VASOPLEGIA_THR), 1.0, places=4)

    def test_none_below(self):
        """SVR always above threshold => fraction 0.0."""
        s = [(i * 30.0, 1200.0) for i in range(10)]
        self.assertAlmostEqual(_frac_time_below(s, SVR_VASOPLEGIA_THR), 0.0, places=4)

    def test_svr_decline_raises_low_fraction(self):
        """A case whose SVR declines into vasoplegia has a higher low-fraction
        than one that stays high."""
        # Declining: starts 1200, ends 500 (second half below 800)
        declining = [(i * 30.0, 1200.0 if i < 10 else 500.0) for i in range(20)]
        # Stable high: always 1200
        stable = [(i * 30.0, 1200.0) for i in range(20)]
        f_decl = _frac_time_below(declining, SVR_VASOPLEGIA_THR)
        f_stable = _frac_time_below(stable, SVR_VASOPLEGIA_THR)
        self.assertIsNotNone(f_decl)
        self.assertIsNotNone(f_stable)
        self.assertGreater(f_decl, f_stable,
                           "SVR decline into vasoplegia should raise low-time fraction")

    def test_strict_inequality_at_threshold(self):
        """Exactly 800 is NOT below 800 (strict)."""
        s = [(i * 30.0, SVR_VASOPLEGIA_THR) for i in range(10)]
        self.assertAlmostEqual(_frac_time_below(s, SVR_VASOPLEGIA_THR), 0.0, places=4)

    def test_none_when_too_few_samples(self):
        self.assertIsNone(_frac_time_below([(0.0, 600.0)], SVR_VASOPLEGIA_THR))
        self.assertIsNone(_frac_time_below([], SVR_VASOPLEGIA_THR))


# ===========================================================================
# 5. _min_gated (vasoplegia depth / low-output depth) and _max_gated
# ===========================================================================

class TestMinMaxGated(unittest.TestCase):
    def test_min_picks_lowest(self):
        s = [(0.0, 1200.0), (30.0, 500.0), (60.0, 900.0)]
        self.assertAlmostEqual(_min_gated(s), 500.0, places=6)

    def test_max_picks_highest(self):
        s = [(0.0, 6.0), (30.0, 22.0), (60.0, 11.0)]
        self.assertAlmostEqual(_max_gated(s), 22.0, places=6)

    def test_min_none_when_empty(self):
        self.assertIsNone(_min_gated([]))

    def test_max_none_when_empty(self):
        self.assertIsNone(_max_gated([]))

    def test_min_single_sample(self):
        """A single sample is enough for a minimum."""
        self.assertAlmostEqual(_min_gated([(0.0, 2.1)]), 2.1, places=6)

    def test_deeper_vasoplegia_lower_min(self):
        """A more vasoplegic case has a lower SVR minimum."""
        mild = [(i * 30.0, 900.0) for i in range(5)] + [(150.0, 750.0)]
        severe = [(i * 30.0, 900.0) for i in range(5)] + [(150.0, 350.0)]
        self.assertLess(_min_gated(severe), _min_gated(mild))


# ===========================================================================
# 6. Physiologic gating + window clipping (artifact rejection / leakage)
# ===========================================================================

class TestGatingAndClipping(unittest.TestCase):
    def test_svv_gate_drops_artifacts(self):
        """SVV above 50 % is artifact and dropped."""
        s = [(0.0, 10.0), (30.0, 99.0), (60.0, 12.0)]
        gated = _filter_physiologic(s, SVV_MIN, SVV_MAX)
        self.assertEqual([v for _, v in gated], [10.0, 12.0])

    def test_svr_gate_bounds(self):
        s = [(0.0, 50.0), (30.0, 600.0), (60.0, 9000.0)]
        gated = _filter_physiologic(s, SVR_MIN, SVR_MAX)
        self.assertEqual([v for _, v in gated], [600.0])

    def test_co_gate_bounds(self):
        s = [(0.0, 0.2), (30.0, 5.0), (60.0, 99.0)]
        gated = _filter_physiologic(s, CO_MIN, CO_MAX)
        self.assertEqual([v for _, v in gated], [5.0])

    def test_ci_gate_bounds(self):
        s = [(0.0, 0.1), (30.0, 3.0), (60.0, 12.0)]
        gated = _filter_physiologic(s, CI_MIN, CI_MAX)
        self.assertEqual([v for _, v in gated], [3.0])

    def test_clip_excludes_post_opend(self):
        """No sample at t > opend survives clipping (leakage firewall)."""
        opend = 600.0
        s = [(0.0, 10.0), (300.0, 12.0), (601.0, 99.0), (900.0, 99.0)]
        clipped = _clip_to_window(s, 0.0, opend)
        self.assertTrue(all(t <= opend for t, _ in clipped))
        self.assertEqual([v for _, v in clipped], [10.0, 12.0])

    def test_clip_excludes_pre_start(self):
        s = [(-50.0, 5.0), (0.0, 10.0), (30.0, 12.0)]
        clipped = _clip_to_window(s, 0.0, 600.0)
        self.assertEqual([v for _, v in clipped], [10.0, 12.0])


# ===========================================================================
# 7. _intraop_window (copied verbatim from pfds)
# ===========================================================================

class TestIntraopWindow(unittest.TestCase):
    def test_anestart_preferred(self):
        case = {"anestart": 10.0, "opstart": 20.0, "opend": 600.0}
        self.assertEqual(_intraop_window(case), (10.0, 600.0))

    def test_opstart_fallback(self):
        case = {"opstart": 20.0, "opend": 600.0}
        self.assertEqual(_intraop_window(case), (20.0, 600.0))

    def test_none_start_when_only_opend(self):
        case = {"opend": 600.0}
        self.assertEqual(_intraop_window(case), (None, 600.0))

    def test_none_when_no_opend(self):
        case = {"anestart": 10.0}
        self.assertEqual(_intraop_window(case), (None, None))


# ===========================================================================
# 8. Empty / missing series -> None across all helpers (missingness contract)
# ===========================================================================

class TestEmptyToNone(unittest.TestCase):
    def test_all_helpers_none_on_empty(self):
        self.assertIsNone(_time_weighted_mean([]))
        self.assertIsNone(_frac_time_above([], SVV_RESPONSIVE_THR))
        self.assertIsNone(_frac_time_below([], SVR_VASOPLEGIA_THR))
        self.assertIsNone(_min_gated([]))
        self.assertIsNone(_max_gated([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
