"""test_vasoactive_pd.py -- Offline unit tests for the vasoactive-PD biomarkers.

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built series with KNOWN expected
direction (escalating multi-pressor vs none; responsiveness slope sign;
empty -> None).  Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_vasoactive_pd -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.vasoactive_pd import (
    SPECS,
    PRESSORS,
    VASODILATORS,
    # Pure helpers under test
    _agents_used,
    _frac_time_any_running,
    _max_infusion_norm,
    _responsiveness,
    _ols_slope,
    _time_to_first,
)
from vitaldb_aki.features.base import audit_specs


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

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in vasoactive_pd SPECS")

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "vaso_available",
                         "First spec must be vaso_available")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "vaso_available",
            "vaso_n_agents",
            "vaso_pressor_duration_frac",
            "vaso_max_infusion_norm",
            "vaso_responsiveness",
            "vaso_time_to_first_pressor_min",
        }
        self.assertFalse(required - names, f"Missing specs: {required - names}")

    def test_all_comprehensive(self):
        for s in SPECS:
            self.assertEqual(s.fset, "comprehensive", msg=f"{s.name} fset={s.fset!r}")


# ===========================================================================
# 2. _agents_used -- escalating multi-pressor case vs none
# ===========================================================================

class TestAgentsUsed(unittest.TestCase):
    def _running(self, n: int = 10, dt: float = 30.0, rate: float = 0.1):
        return [(i * dt, rate) for i in range(n)]

    def _idle(self, n: int = 10, dt: float = 30.0):
        return [(i * dt, 0.0) for i in range(n)]

    def test_no_pumps_no_flags_is_zero(self):
        self.assertEqual(_agents_used({}, None), 0)
        self.assertEqual(_agents_used({}, {}), 0)

    def test_idle_pump_does_not_count(self):
        pumps = {"Orchestra/PHEN_RATE": self._idle()}
        self.assertEqual(_agents_used(pumps, None), 0,
                         "Pump present but rate always 0 => no agent running")

    def test_single_running_pump(self):
        pumps = {"Orchestra/NEPI_RATE": self._running()}
        self.assertEqual(_agents_used(pumps, None), 1)

    def test_multi_pressor_case_counts_distinct(self):
        """Escalating multi-pressor case: 3 distinct pumps running."""
        pumps = {
            "Orchestra/PHEN_RATE": self._running(rate=0.2),
            "Orchestra/NEPI_RATE": self._running(rate=0.05),
            "Orchestra/VASO_RATE": self._running(rate=2.0),
            "Orchestra/DOPA_RATE": self._idle(),  # present but never ran
        }
        self.assertEqual(_agents_used(pumps, None), 3,
                         "Three running pumps => 3 distinct agents (idle one excluded)")

    def test_non_pressor_track_ignored(self):
        """A vasodilator pump must not be counted as a pressor agent."""
        pumps = {
            "Orchestra/NTG_RATE": self._running(),   # vasodilator, not a pressor
            "Orchestra/PHEN_RATE": self._running(),
        }
        self.assertEqual(_agents_used(pumps, None), 1)

    def test_case_flag_phe_merges_with_pump(self):
        """intraop_phe>0 maps onto the PHEN pump identity (counted once)."""
        pumps = {"Orchestra/PHEN_RATE": self._running()}
        self.assertEqual(_agents_used(pumps, {"phe": True}), 1,
                         "PHE bolus + PHEN pump = one agent, not two")

    def test_case_flag_phe_adds_when_no_pump(self):
        self.assertEqual(_agents_used({}, {"phe": True}), 1)

    def test_ephedrine_bolus_is_distinct_agent(self):
        """Ephedrine has no pump track => its flag adds a distinct agent."""
        pumps = {"Orchestra/PHEN_RATE": self._running()}
        self.assertEqual(_agents_used(pumps, {"phe": True, "eph": True}), 2,
                         "PHEN pump + ephedrine bolus = 2 distinct agents")

    def test_escalating_vs_none(self):
        """Direction check: multi-pressor escalation > none."""
        none_case = _agents_used({"Orchestra/PHEN_RATE": self._idle()}, None)
        escalating = _agents_used({
            "Orchestra/PHEN_RATE": self._running(),
            "Orchestra/NEPI_RATE": self._running(),
            "Orchestra/EPI_RATE": self._running(),
        }, {"eph": True})
        self.assertEqual(none_case, 0)
        self.assertGreater(escalating, none_case)


# ===========================================================================
# 3. _frac_time_any_running -- union of pump rates>0
# ===========================================================================

class TestFracTimeAnyRunning(unittest.TestCase):
    def test_none_when_no_pumps(self):
        self.assertIsNone(_frac_time_any_running({}, (0.0, 600.0)))

    def test_none_when_single_sample(self):
        pumps = {"Orchestra/PHEN_RATE": [(0.0, 0.1)]}
        self.assertIsNone(_frac_time_any_running(pumps, (0.0, 600.0)))

    def test_zero_when_never_running(self):
        pumps = {"Orchestra/PHEN_RATE": [(i * 5.0, 0.0) for i in range(10)]}
        result = _frac_time_any_running(pumps, (0.0, 50.0))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_one_when_always_running(self):
        pumps = {"Orchestra/NEPI_RATE": [(i * 5.0, 0.1) for i in range(10)]}
        result = _frac_time_any_running(pumps, (0.0, 50.0))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 1.0, places=4)

    def test_half_when_running_half(self):
        """Running for the first half of the grid => fraction ~0.5."""
        # dt=5s (<= gap cap 10s) so each interval is fully charged.
        rates = [0.1] * 10 + [0.0] * 10
        pumps = {"Orchestra/PHEN_RATE": [(i * 5.0, r) for i, r in enumerate(rates)]}
        result = _frac_time_any_running(pumps, (0.0, 100.0))
        self.assertIsNotNone(result)
        self.assertGreater(result, 0.3)
        self.assertLess(result, 0.7)

    def test_union_across_two_pumps(self):
        """Two pumps each running a disjoint half => union ~ full coverage."""
        a = [(i * 5.0, 0.1 if i < 10 else 0.0) for i in range(20)]
        b = [(i * 5.0, 0.0 if i < 10 else 0.1) for i in range(20)]
        pumps = {"Orchestra/PHEN_RATE": a, "Orchestra/NEPI_RATE": b}
        result = _frac_time_any_running(pumps, (0.0, 100.0))
        self.assertIsNotNone(result)
        self.assertGreater(result, 0.8,
                           "Union of two disjoint-half pumps should cover most of the case")


# ===========================================================================
# 4. _max_infusion_norm -- escalation height proxy
# ===========================================================================

class TestMaxInfusionNorm(unittest.TestCase):
    def test_none_when_no_pumps(self):
        self.assertIsNone(_max_infusion_norm({}))

    def test_zero_when_pumps_never_run(self):
        pumps = {"Orchestra/PHEN_RATE": [(i * 5.0, 0.0) for i in range(5)]}
        result = _max_infusion_norm(pumps)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_single_pump_peaks_at_one(self):
        """One pump normalised to its own max peaks at exactly 1.0."""
        pumps = {"Orchestra/PHEN_RATE": [(i * 5.0, float(i)) for i in range(1, 6)]}
        result = _max_infusion_norm(pumps)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 1.0, places=4)

    def test_two_simultaneous_pumps_peak_near_two(self):
        """Two pumps both at their own max at the same instant => ~2.0."""
        a = [(i * 5.0, float(i)) for i in range(1, 6)]   # max at last sample
        b = [(i * 5.0, float(i) * 10.0) for i in range(1, 6)]  # different units, max at last
        pumps = {"Orchestra/PHEN_RATE": a, "Orchestra/NEPI_RATE": b}
        result = _max_infusion_norm(pumps)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 2.0, places=4,
                               msg="Two pumps simultaneously at own-max => 2.0 (units-robust)")

    def test_escalation_height_orders_correctly(self):
        """A 3-drug simultaneous peak scores higher than a single drug."""
        single = {"Orchestra/PHEN_RATE": [(i * 5.0, float(i)) for i in range(1, 6)]}
        triple = {
            "Orchestra/PHEN_RATE": [(i * 5.0, float(i)) for i in range(1, 6)],
            "Orchestra/NEPI_RATE": [(i * 5.0, float(i)) for i in range(1, 6)],
            "Orchestra/EPI_RATE": [(i * 5.0, float(i)) for i in range(1, 6)],
        }
        self.assertLess(_max_infusion_norm(single), _max_infusion_norm(triple))


# ===========================================================================
# 5. _responsiveness -- MAP vs pressor slope sign (vasoplegia)
# ===========================================================================

class TestResponsiveness(unittest.TestCase):
    def test_none_when_no_pump(self):
        mp = [(i * 30.0, 70.0) for i in range(10)]
        self.assertIsNone(_responsiveness({}, mp))

    def test_none_when_too_few_map(self):
        pumps = {"Orchestra/PHEN_RATE": [(i * 30.0, float(i)) for i in range(10)]}
        mp = [(0.0, 70.0), (30.0, 72.0)]
        self.assertIsNone(_responsiveness(pumps, mp))

    def test_positive_slope_healthy_response(self):
        """MAP rises as pressor rises => positive slope (healthy)."""
        n = 20
        pumps = {"Orchestra/PHEN_RATE": [(i * 30.0, 1.0 + i) for i in range(n)]}
        mp = [(i * 30.0, 60.0 + 1.5 * i) for i in range(n)]  # MAP climbs with dose
        slope = _responsiveness(pumps, mp)
        self.assertIsNotNone(slope)
        self.assertGreater(slope, 0.0,
                           "MAP rising with pressor => positive responsiveness slope")

    def test_negative_slope_vasoplegia(self):
        """MAP falls despite rising pressor => negative slope (vasoplegia)."""
        n = 20
        pumps = {"Orchestra/NEPI_RATE": [(i * 30.0, 0.05 + 0.05 * i) for i in range(n)]}
        mp = [(i * 30.0, 80.0 - 1.0 * i) for i in range(n)]  # MAP keeps falling
        slope = _responsiveness(pumps, mp)
        self.assertIsNotNone(slope)
        self.assertLess(slope, 0.0,
                        "MAP falling under rising pressor => negative slope (vasoplegia)")


# ===========================================================================
# 6. _ols_slope (copied helper)
# ===========================================================================

class TestOlsSlope(unittest.TestCase):
    def test_none_when_too_few(self):
        self.assertIsNone(_ols_slope([0.0, 1.0], [0.0, 1.0]))

    def test_none_when_no_x_variance(self):
        self.assertIsNone(_ols_slope([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]))

    def test_unit_slope(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.0, 1.0, 2.0, 3.0]
        self.assertAlmostEqual(_ols_slope(xs, ys), 1.0, places=6)

    def test_negative_slope(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [3.0, 2.0, 1.0, 0.0]
        self.assertAlmostEqual(_ols_slope(xs, ys), -1.0, places=6)


# ===========================================================================
# 7. _time_to_first -- onset of first pressor infusion
# ===========================================================================

class TestTimeToFirst(unittest.TestCase):
    def test_none_when_never_running(self):
        pumps = {"Orchestra/PHEN_RATE": [(i * 30.0, 0.0) for i in range(5)]}
        self.assertIsNone(_time_to_first(pumps, 0.0))

    def test_none_when_empty(self):
        self.assertIsNone(_time_to_first({}, 0.0))

    def test_minutes_from_t_start(self):
        """First rate>0 at t=300s with t_start=0 => 5.0 minutes."""
        pumps = {"Orchestra/PHEN_RATE":
                 [(i * 30.0, 0.0 if i < 10 else 0.1) for i in range(20)]}
        result = _time_to_first(pumps, 0.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 5.0, places=3)

    def test_relative_to_nonzero_t_start(self):
        """Onset at t=360 with t_start=60 => (360-60)/60 = 5.0 min."""
        pumps = {"Orchestra/NEPI_RATE": [(360.0, 0.1), (390.0, 0.1)]}
        result = _time_to_first(pumps, 60.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 5.0, places=3)

    def test_earliest_across_pumps(self):
        """Returns the earliest onset across multiple pumps."""
        pumps = {
            "Orchestra/PHEN_RATE": [(600.0, 0.1)],
            "Orchestra/NEPI_RATE": [(120.0, 0.05)],   # earlier onset
        }
        result = _time_to_first(pumps, 0.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 2.0, places=3)

    def test_clamps_negative_to_zero(self):
        """Onset just before nominal t_start => clamped to 0.0, not negative."""
        pumps = {"Orchestra/PHEN_RATE": [(10.0, 0.1)]}
        result = _time_to_first(pumps, 60.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_vasodilator_does_not_trigger(self):
        """A vasodilator infusion must not count as a pressor onset."""
        pumps = {"Orchestra/NTG_RATE": [(30.0, 0.1), (60.0, 0.1)]}
        self.assertIsNone(_time_to_first(pumps, 0.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
