"""test_thermoregulation.py -- Offline unit tests for the thermoregulation family.

UNMINED AXIS: intraoperative temperature dysregulation (hypothermia depth /
duration / cold-dose AUC / rewarming recovery).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Every pure helper is tested against hand-built series with a KNOWN expected
direction (a hypothermic case vs a normothermic one; cold-dose AUC; rewarming
slope; empty -> None).  Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_thermoregulation -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.thermoregulation import (
    # Module-level constants
    SPECS, NORMO_THR, TEMP_MIN, TEMP_MAX, MIN_USABLE_SAMPLES,
    # Pure helpers
    _time_weighted_mean,
    _min_gated,
    _frac_time_below,
    _auc_below,
    _sd,
    _rewarming_rate,
)
from vitaldb_aki.features.base import audit_specs


# ---------------------------------------------------------------------------
# Series builders
# ---------------------------------------------------------------------------

def _uniform(value: float, n: int = 20, dt: float = 30.0) -> list[tuple[float, float]]:
    """n samples of constant `value` spaced `dt` seconds apart."""
    return [(i * dt, value) for i in range(n)]


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_audit_passes(self):
        audit_specs(SPECS)  # raises on violation

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_postop_timing(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop",
                                msg=f"{s.name} has postop timing -- leakage!")

    def test_all_comprehensive(self):
        for s in SPECS:
            self.assertEqual(s.fset, "comprehensive", msg=f"{s.name} fset={s.fset!r}")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "thermo_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "thermo_available",
            "thermo_min_temp",
            "thermo_mean_temp",
            "thermo_hypothermia_frac",
            "thermo_hypothermia_auc",
            "thermo_temp_variability",
            "thermo_rewarming_rate",
        }
        self.assertFalse(required - names, f"Missing specs: {required - names}")

    def test_constants(self):
        self.assertEqual(NORMO_THR, 36.0)
        self.assertEqual(TEMP_MIN, 30.0)
        self.assertEqual(TEMP_MAX, 42.0)
        self.assertEqual(MIN_USABLE_SAMPLES, 10)


# ===========================================================================
# 2. _time_weighted_mean
# ===========================================================================

class TestTimeWeightedMean(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_time_weighted_mean([]))
        self.assertIsNone(_time_weighted_mean([(0.0, 36.5)]))

    def test_constant_series(self):
        m = _uniform(36.5, n=10, dt=30.0)
        self.assertAlmostEqual(_time_weighted_mean(m), 36.5, places=5)

    def test_hypothermic_below_normothermic(self):
        cold = _uniform(34.0, n=10, dt=30.0)
        warm = _uniform(36.8, n=10, dt=30.0)
        self.assertLess(_time_weighted_mean(cold), _time_weighted_mean(warm))


# ===========================================================================
# 3. _min_gated
# ===========================================================================

class TestMinGated(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(_min_gated([]))

    def test_finds_minimum(self):
        s = [(0.0, 36.5), (30.0, 34.2), (60.0, 35.8), (90.0, 36.0)]
        self.assertAlmostEqual(_min_gated(s), 34.2, places=5)

    def test_hypothermic_lower_min(self):
        cold = [(0.0, 36.5), (30.0, 33.5), (60.0, 34.0)]   # dips to 33.5
        warm = [(0.0, 36.8), (30.0, 36.6), (60.0, 37.0)]   # stays normothermic
        self.assertLess(_min_gated(cold), _min_gated(warm))
        self.assertLess(_min_gated(cold), NORMO_THR)
        self.assertGreater(_min_gated(warm), NORMO_THR)


# ===========================================================================
# 4. _frac_time_below
# ===========================================================================

class TestFracTimeBelow(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_frac_time_below([], NORMO_THR))
        self.assertIsNone(_frac_time_below([(0.0, 34.0)], NORMO_THR))

    def test_all_below(self):
        cold = _uniform(34.0, n=10, dt=30.0)  # entirely hypothermic
        self.assertAlmostEqual(_frac_time_below(cold, NORMO_THR), 1.0, places=4)

    def test_none_below(self):
        warm = _uniform(36.8, n=10, dt=30.0)
        self.assertAlmostEqual(_frac_time_below(warm, NORMO_THR), 0.0, places=4)

    def test_half_below(self):
        # First half (indices 0..9) hypothermic, second half normothermic.
        # Interval weight is attributed to the LEFT sample; index 9 -> 10 is the
        # boundary interval and its left value (34.0) counts as below.
        s = [(i * 30.0, 34.0 if i < 10 else 36.8) for i in range(20)]
        frac = _frac_time_below(s, NORMO_THR)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.4)
        self.assertLess(frac, 0.6)

    def test_hypothermic_higher_fraction(self):
        cold = _uniform(34.5, n=10, dt=30.0)
        warm = _uniform(36.6, n=10, dt=30.0)
        self.assertGreater(_frac_time_below(cold, NORMO_THR),
                           _frac_time_below(warm, NORMO_THR))


# ===========================================================================
# 5. _auc_below  (C * minutes)
# ===========================================================================

class TestAucBelow(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_auc_below([], NORMO_THR))
        self.assertIsNone(_auc_below([(0.0, 34.0)], NORMO_THR))

    def test_zero_when_never_below(self):
        warm = _uniform(36.8, n=10, dt=30.0)
        self.assertAlmostEqual(_auc_below(warm, NORMO_THR), 0.0, places=6)

    def test_known_auc_value(self):
        # Constant 34.0 C (2.0 C below 36.0) for 6 intervals of 10 s each.
        # dt == the 10 s gap cap, so no capping occurs:
        #   deficit 2.0 C * (6 * 10 s) = 120 C*s = 2.0 C*min
        cold = _uniform(34.0, n=7, dt=10.0)
        auc = _auc_below(cold, NORMO_THR)
        self.assertIsNotNone(auc)
        self.assertAlmostEqual(auc, 2.0, places=4)

    def test_deeper_hypothermia_higher_auc(self):
        mild = _uniform(35.5, n=11, dt=30.0)   # 0.5 C deficit
        severe = _uniform(33.0, n=11, dt=30.0)  # 3.0 C deficit
        self.assertGreater(_auc_below(severe, NORMO_THR), _auc_below(mild, NORMO_THR))

    def test_hypothermic_vs_normothermic(self):
        cold = _uniform(34.0, n=11, dt=30.0)
        warm = _uniform(36.5, n=11, dt=30.0)
        self.assertGreater(_auc_below(cold, NORMO_THR), 0.0)
        self.assertAlmostEqual(_auc_below(warm, NORMO_THR), 0.0, places=6)


# ===========================================================================
# 6. _sd
# ===========================================================================

class TestSd(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_sd([]))
        self.assertIsNone(_sd([(0.0, 36.0)]))

    def test_zero_for_flat(self):
        flat = _uniform(36.5, n=10, dt=30.0)
        self.assertAlmostEqual(_sd(flat), 0.0, places=6)

    def test_positive_for_varying(self):
        s = [(0.0, 34.0), (30.0, 36.0), (60.0, 38.0)]
        sd = _sd(s)
        self.assertIsNotNone(sd)
        self.assertGreater(sd, 0.0)

    def test_more_variable_higher_sd(self):
        steady = [(i * 30.0, 36.0 + 0.1 * (i % 2)) for i in range(10)]
        swingy = [(i * 30.0, 36.0 + 2.0 * (i % 2)) for i in range(10)]
        self.assertGreater(_sd(swingy), _sd(steady))


# ===========================================================================
# 7. _rewarming_rate  (C / hour)
# ===========================================================================

class TestRewarmingRate(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_rewarming_rate([]))
        self.assertIsNone(_rewarming_rate([(0.0, 36.0)]))

    def test_positive_when_rewarming_after_nadir(self):
        # Drop to a nadir at index 2, then rewarm steadily.
        s = [
            (0.0, 36.0),
            (1800.0, 35.0),
            (3600.0, 34.0),   # nadir at t=3600
            (5400.0, 35.0),
            (7200.0, 36.0),
            (9000.0, 37.0),
        ]
        rate = _rewarming_rate(s)
        self.assertIsNotNone(rate)
        self.assertGreater(rate, 0.0, "Temperature recovering after nadir => positive slope")

    def test_known_two_point_slope(self):
        # Nadir 34.0 at t=0, single post-nadir point 37.0 at t=3600 (1 hour).
        # Two-point fallback => (37 - 34) / 1 h = 3.0 C/hour.
        s = [(0.0, 34.0), (3600.0, 37.0)]
        rate = _rewarming_rate(s)
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 3.0, places=4)

    def test_none_when_nadir_is_last_sample(self):
        # Monotonically cooling -- nadir is the final sample, no recovery segment.
        s = [(0.0, 37.0), (1800.0, 36.0), (3600.0, 35.0), (5400.0, 34.0)]
        self.assertIsNone(_rewarming_rate(s))

    def test_negative_when_still_cooling_after_local_min_absent(self):
        # Falls then keeps falling: global nadir is last point => None
        s = [(0.0, 36.0), (1800.0, 35.0), (3600.0, 34.0)]
        self.assertIsNone(_rewarming_rate(s))

    def test_ols_used_for_three_plus_post_nadir(self):
        # Nadir at index 0; >=3 post-nadir points, perfectly linear rewarm.
        # +1.0 C every 3600 s => slope 1.0 C/hour.
        s = [(i * 3600.0, 34.0 + 1.0 * i) for i in range(5)]
        rate = _rewarming_rate(s)
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 1.0, places=4)

    def test_faster_recovery_higher_rate(self):
        slow = [(0.0, 34.0), (3600.0, 34.5), (7200.0, 35.0), (10800.0, 35.5)]
        fast = [(0.0, 34.0), (3600.0, 35.5), (7200.0, 37.0), (10800.0, 38.5)]
        self.assertGreater(_rewarming_rate(fast), _rewarming_rate(slow))


# ===========================================================================
# 8. Integrated hypothermic-vs-normothermic case contrast
# ===========================================================================

class TestHypothermicVsNormothermicCase(unittest.TestCase):
    """A hypothermic case should show: lower min, lower mean, higher below-frac,
    higher cold-dose AUC than a normothermic case -- and rewarm after its nadir."""

    def _hypothermic_case(self) -> list[tuple[float, float]]:
        # Cools to a 34.0 C nadir mid-case, then rewarms toward 36.0 C.
        vals = [37.0, 36.0, 35.0, 34.5, 34.0, 34.0, 34.5, 35.0, 35.5, 36.0, 36.2, 36.4]
        return [(i * 300.0, v) for i, v in enumerate(vals)]

    def _normothermic_case(self) -> list[tuple[float, float]]:
        vals = [36.8, 36.9, 37.0, 36.9, 36.8, 36.9, 37.0, 36.9, 36.8, 36.9, 37.0, 36.9]
        return [(i * 300.0, v) for i, v in enumerate(vals)]

    def test_contrast(self):
        cold = self._hypothermic_case()
        warm = self._normothermic_case()

        # min
        self.assertLess(_min_gated(cold), _min_gated(warm))
        self.assertLess(_min_gated(cold), NORMO_THR)

        # mean
        self.assertLess(_time_weighted_mean(cold), _time_weighted_mean(warm))

        # fraction below 36
        self.assertGreater(_frac_time_below(cold, NORMO_THR),
                           _frac_time_below(warm, NORMO_THR))

        # cold-dose AUC
        self.assertGreater(_auc_below(cold, NORMO_THR), _auc_below(warm, NORMO_THR))
        self.assertAlmostEqual(_auc_below(warm, NORMO_THR), 0.0, places=6)

        # rewarming slope (cold case rewarms after nadir => positive)
        rate = _rewarming_rate(cold)
        self.assertIsNotNone(rate)
        self.assertGreater(rate, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
