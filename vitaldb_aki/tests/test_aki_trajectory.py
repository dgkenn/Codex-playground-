"""test_aki_trajectory.py -- unit tests for classify_trajectory (stdlib only, no network).

Tests cover: transient recovery, persistent sustained elevation, indeterminate (no late
measurement), boundary cases (exactly at threshold, edge of recovery window), and
invalid inputs. No VitalDB creds or data required.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.cohort.aki_trajectory import (
    RECOVERY_EARLY_H,
    RECOVERY_LATE_H,
    KDIGO_WINDOW_H,
    classify_trajectory,
)

H = 3600.0  # seconds per hour


class TestTransient(unittest.TestCase):
    """Cases where creatinine rises then clearly recovers within 24-72h."""

    def test_clear_transient_recovery(self):
        """Peak at 24h, recovers to baseline at 48h -> transient."""
        baseline = 1.0
        series = [
            (6 * H, 1.2),     # rising
            (24 * H, 1.7),    # peak (1.7x >= 1.5x, so AKI)
            (48 * H, 1.1),    # recovery: < 1.5x and < baseline+0.3 (1.3)
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")
        self.assertAlmostEqual(result.peak_cr, 1.7)
        self.assertAlmostEqual(result.recovery_cr, 1.1)
        self.assertIn("recovered", result.reason)

    def test_transient_at_recovery_window_boundary(self):
        """Recovery measured exactly at RECOVERY_LATE_H (72h) -> still transient."""
        baseline = 1.0
        series = [
            (10 * H, 1.6),              # AKI peak
            (RECOVERY_LATE_H * H, 1.1), # recovery at exactly 72h boundary
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")

    def test_transient_at_early_window_boundary(self):
        """Recovery measured at exactly RECOVERY_EARLY_H (24h) -> counts as recovery window."""
        baseline = 1.0
        series = [
            (12 * H, 1.6),
            (RECOVERY_EARLY_H * H, 1.0),  # exactly at 24h lower bound
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")

    def test_transient_abs_rise_recovers(self):
        """AKI triggered by absolute rise (0.3), then creatinine falls back to baseline level."""
        baseline = 0.9
        series = [
            (20 * H, 1.22),   # +0.32 within 48h -> AKI
            (36 * H, 0.95),   # < 1.5x (1.35) and < 1.2 (0.9+0.3) -> recovery
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")

    def test_transient_multiple_recovery_window_measurements_first_qualifies(self):
        """Multiple measurements in recovery window; first qualifying one is used."""
        baseline = 1.0
        series = [
            (6 * H, 1.6),     # AKI peak
            (25 * H, 1.1),    # first qualifying recovery (in window)
            (50 * H, 1.0),    # second, also qualifying
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")
        # Should pick earliest qualifying measurement
        self.assertAlmostEqual(result.recovery_dt_h, 25.0)


class TestPersistent(unittest.TestCase):
    """Cases where creatinine remains elevated within the recovery window."""

    def test_clear_persistent(self):
        """Peak at 12h, still elevated at 48h and 72h -> persistent."""
        baseline = 1.0
        series = [
            (12 * H, 2.0),    # AKI (2x)
            (48 * H, 1.7),    # still >= 1.5x baseline
            (72 * H, 1.6),    # still >= 1.5x
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "persistent")
        self.assertAlmostEqual(result.peak_cr, 2.0)

    def test_persistent_abs_criteria_not_met(self):
        """Creatinine drops but only to baseline+0.31 -> still above threshold -> persistent."""
        baseline = 1.0
        series = [
            (10 * H, 1.6),      # AKI
            (40 * H, 1.31),     # < 1.5x BUT still >= 1.0+0.3=1.30 (1.31 >= 1.30)
        ]
        result = classify_trajectory(baseline, series)
        # 1.31 < 1.5 but >= 1.3, so the abs criterion fails -> NOT recovered
        self.assertEqual(result.label, "persistent")

    def test_persistent_rel_criteria_not_met(self):
        """Creatinine drops to just under baseline+0.30 but still >=1.5x -> persistent."""
        baseline = 1.0
        series = [
            (10 * H, 1.6),      # AKI
            (40 * H, 1.5),      # exactly 1.5x baseline -> not < 1.5x -> persistent
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "persistent")

    def test_persistent_only_rise_no_fall(self):
        """One measurement in recovery window and still very elevated."""
        baseline = 0.8
        series = [
            (30 * H, 1.4),   # AKI (1.75x)
            (48 * H, 1.3),   # 1.3/0.8 = 1.625x >= 1.5 -> persistent
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "persistent")

    def test_persistent_recovery_outside_window_does_not_count(self):
        """Recovery measurement exists but AFTER 72h -> cannot be used, window only has elevated values."""
        baseline = 1.0
        series = [
            (10 * H, 1.6),       # AKI peak
            (48 * H, 1.55),      # still elevated in recovery window
            (100 * H, 1.0),      # late recovery, but outside 72h window
        ]
        result = classify_trajectory(baseline, series)
        # 48h measurement in window is 1.55 >= 1.5x -> persistent (late measurement not counted for recovery)
        self.assertEqual(result.label, "persistent")


class TestIndeterminate(unittest.TestCase):
    """Cases where AKI is confirmed but no measurement exists in the recovery window."""

    def test_no_late_measurement_only_early(self):
        """All measurements before 24h -> no recovery-window data -> indeterminate."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),    # AKI, but only early measurement
            (10 * H, 1.7),
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "indeterminate")
        self.assertEqual(result.n_in_recovery_window, 0)
        self.assertIn("cannot adjudicate", result.reason)

    def test_no_postop_measurements_at_all(self):
        """Empty series -> indeterminate."""
        result = classify_trajectory(1.0, [])
        self.assertEqual(result.label, "indeterminate")

    def test_measurement_exactly_outside_early_boundary(self):
        """Measurement at 23.9h -> just before RECOVERY_EARLY_H (24h) -> indeterminate."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (23.9 * H, 1.1),  # just before the 24h window, doesn't count for recovery
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "indeterminate")
        self.assertEqual(result.n_in_recovery_window, 0)

    def test_only_very_late_measurement_beyond_window(self):
        """Measurement only at 100h (beyond 72h recovery window but < 168h) -> indeterminate."""
        baseline = 1.0
        series = [
            (8 * H, 1.6),     # AKI peak
            (100 * H, 1.0),   # after recovery window
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "indeterminate")
        self.assertEqual(result.n_in_recovery_window, 0)

    def test_invalid_baseline(self):
        """Zero or None baseline -> indeterminate with explanation."""
        r1 = classify_trajectory(0.0, [(10 * H, 1.5)])
        self.assertEqual(r1.label, "indeterminate")
        r2 = classify_trajectory(None, [(10 * H, 1.5)])
        self.assertEqual(r2.label, "indeterminate")


class TestBoundaryCases(unittest.TestCase):
    """Boundary arithmetic: exactly-at-threshold values for both criteria."""

    def test_recovery_threshold_just_below_rel(self):
        """cr = 1.499x baseline in recovery window -> < 1.5x (passes rel check)."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (30 * H, 0.5),     # well below both thresholds
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")

    def test_recovery_threshold_exactly_at_abs(self):
        """cr = exactly baseline + 0.3 in recovery window -> NOT recovered (must be strictly less)."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (30 * H, 1.3),   # exactly baseline+0.3 -> NOT < threshold -> persistent
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "persistent")

    def test_outside_7d_window_ignored(self):
        """Measurement at 200h (>168h) is outside KDIGO outer window and ignored."""
        baseline = 1.0
        series = [
            (8 * H, 1.6),     # AKI
            (48 * H, 1.7),    # elevated in recovery window -> persistent
            (200 * H, 0.5),   # outside outer 168h window, excluded
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "persistent")

    def test_peak_determined_correctly(self):
        """Peak creatinine is the global max across all in-window measurements."""
        baseline = 1.0
        series = [
            (12 * H, 2.5),   # global peak
            (30 * H, 1.7),
            (50 * H, 1.2),   # recovery measurement
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")
        self.assertAlmostEqual(result.peak_cr, 2.5)

    def test_earliest_recovery_chosen_over_later(self):
        """When multiple measurements qualify as recovery, the EARLIEST is reported."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (25 * H, 1.1),   # first qualifying
            (60 * H, 1.0),   # also qualifying but later
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.label, "transient")
        self.assertAlmostEqual(result.recovery_dt_h, 25.0)

    def test_cfg_override_window(self):
        """Passing cfg with aki_trajectory block overrides window constants."""
        # Use a very narrow early window so the 30h measurement is excluded
        cfg = {"aki_trajectory": {"recovery_early_h": 35.0, "recovery_late_h": 72.0,
                                   "kdigo_window_h": 168.0}}
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (30 * H, 1.0),   # would qualify with default 24h window, but not with 35h
            (50 * H, 1.6),   # in window but elevated
        ]
        result = classify_trajectory(baseline, series, cfg)
        # 30h is excluded (< 35h); 50h is in window but 1.6 >= 1.5x -> persistent
        self.assertEqual(result.label, "persistent")

    def test_n_in_recovery_window_reported(self):
        """n_in_recovery_window is accurately counted."""
        baseline = 1.0
        series = [
            (5 * H, 1.6),
            (25 * H, 1.5),   # boundary: exactly 1.5x -> persistent
            (60 * H, 1.5),   # also in window
        ]
        result = classify_trajectory(baseline, series)
        self.assertEqual(result.n_in_recovery_window, 2)
        self.assertEqual(result.n_postop_cr, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
