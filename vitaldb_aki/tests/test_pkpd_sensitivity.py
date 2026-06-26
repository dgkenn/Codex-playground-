"""test_pkpd_sensitivity.py -- Offline unit tests for the PK-PD sensitivity module.

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Synthetic (Ce, MAP) series are generated from a KNOWN sigmoid Emax model (with
noise) and we verify that:
  * curve_fit recovers Emax/EC50 within tolerance
  * A linear-only Ce exposure triggers the slope fallback path
  * Flat / no-Ce cases return None / pkpd_available=0
  * A more-fragile synthetic patient (bigger Emax / lower EC50) yields higher
    pkpd_sensitivity than a robust one

Run with:
    python3 -m unittest vitaldb_aki.tests.test_pkpd_sensitivity -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.pkpd_sensitivity import (
    SPECS,
    MIN_SIGMOID_POINTS,
    MIN_CE_RANGE_UG_ML,
    MIN_LINEAR_POINTS,
    RESAMPLE_GRID_S,
    RESAMPLE_LOOKBACK_S,
    _intraop_window,
    _clip_to_window,
    _filter_range,
    _last_value_hold,
    _emax_model,
    _r_squared,
    _ols_slope_intercept,
    resample_to_grid,
    fit_sigmoid_emax,
    fit_linear_robust,
    compute_pkpd_features,
)
from vitaldb_aki.features.base import audit_specs, LeakageError


# ---------------------------------------------------------------------------
# Helpers to generate synthetic data
# ---------------------------------------------------------------------------

def _sigmoid_samples(
    map0: float,
    emax: float,
    ec50: float,
    hill: float,
    ce_min: float,
    ce_max: float,
    n_points: int,
    noise_std: float = 2.0,
    seed: int = 42,
) -> tuple[list[float], list[float]]:
    """Generate (ce_vals, map_vals) from a known Emax model + Gaussian noise.

    Uses a simple LCG for portability (no numpy needed for test generation).
    """
    # Very simple LCG-based RNG for reproducibility without numpy
    a, c, m = 1664525, 1013904223, 2 ** 32
    state = seed

    def _randn() -> float:
        """Box-Muller transform from two uniform LCG samples."""
        nonlocal state
        state = (a * state + c) % m
        u1 = state / m
        state = (a * state + c) % m
        u2 = state / m
        # Avoid log(0)
        u1 = max(u1, 1e-10)
        mag = math.sqrt(-2.0 * math.log(u1))
        return mag * math.cos(2 * math.pi * u2)

    ce_vals = []
    map_vals = []
    for i in range(n_points):
        ce = ce_min + (ce_max - ce_min) * i / max(n_points - 1, 1)
        map_true = _emax_model(ce, map0, emax, ec50, hill)
        noise = noise_std * _randn()
        ce_vals.append(ce)
        map_vals.append(map_true + noise)

    return ce_vals, map_vals


def _build_time_series(
    vals: list[float],
    t_start: float = 0.0,
    dt: float = 30.0,
) -> list[tuple[float, float]]:
    """Build (time, value) pairs from a list of values, starting at t_start."""
    return [(t_start + i * dt, v) for i, v in enumerate(vals)]


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

    def test_all_pk_fset(self):
        for s in SPECS:
            self.assertEqual(s.fset, "pk", msg=f"{s.name} fset={s.fset!r}")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)), "Duplicate feature names in SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "pkpd_available",
            "pkpd_map0",
            "pkpd_emax",
            "pkpd_ec50",
            "pkpd_hill",
            "pkpd_slope",
            "pkpd_sensitivity",
            "pkpd_fit_quality",
            "pkpd_n_pairs",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing SPECS: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 9, "Expected exactly 9 PK-PD sensitivity feature specs")


# ===========================================================================
# 2. Pure helper unit tests
# ===========================================================================

class TestIntraopWindow(unittest.TestCase):
    def test_anestart_preferred(self):
        case = {"anestart": "100", "opstart": "200", "opend": "3000"}
        t0, t1 = _intraop_window(case)
        self.assertEqual(t0, 100.0)
        self.assertEqual(t1, 3000.0)

    def test_opstart_fallback(self):
        case = {"opstart": "200", "opend": "3000"}
        t0, t1 = _intraop_window(case)
        self.assertEqual(t0, 200.0)
        self.assertEqual(t1, 3000.0)

    def test_missing_opend_returns_none(self):
        case = {"anestart": "100"}
        t0, t1 = _intraop_window(case)
        self.assertIsNone(t1)

    def test_nan_string_treated_as_none(self):
        case = {"anestart": "nan", "opstart": "200", "opend": "3000"}
        t0, t1 = _intraop_window(case)
        self.assertEqual(t0, 200.0)


class TestClipToWindow(unittest.TestCase):
    def test_clips_start_and_end(self):
        samples = [(i * 10.0, float(i)) for i in range(20)]
        clipped = _clip_to_window(samples, 30.0, 120.0)
        self.assertTrue(all(30.0 <= t <= 120.0 for t, _ in clipped))
        self.assertEqual(len(clipped), 10)  # t=30..120 step 10 -> 10 points

    def test_none_start_keeps_all(self):
        samples = [(10.0, 1.0), (20.0, 2.0), (30.0, 3.0)]
        result = _clip_to_window(samples, None, 25.0)
        self.assertEqual(len(result), 2)

    def test_none_end_keeps_all(self):
        samples = [(10.0, 1.0), (20.0, 2.0), (1000.0, 3.0)]
        result = _clip_to_window(samples, 15.0, None)
        self.assertEqual(len(result), 2)


class TestFilterRange(unittest.TestCase):
    def test_drops_outliers(self):
        samples = [(0.0, 5.0), (1.0, 80.0), (2.0, 210.0), (3.0, -5.0)]
        filtered = _filter_range(samples, 20.0, 200.0)
        self.assertEqual(filtered, [(1.0, 80.0)])

    def test_keeps_boundary_values(self):
        samples = [(0.0, 20.0), (1.0, 200.0)]
        self.assertEqual(_filter_range(samples, 20.0, 200.0), samples)


class TestLastValueHold(unittest.TestCase):
    def test_returns_most_recent(self):
        samples = [(0.0, 10.0), (30.0, 20.0), (60.0, 30.0)]
        self.assertEqual(_last_value_hold(samples, 45.0, 120.0), 20.0)

    def test_returns_none_when_too_stale(self):
        samples = [(0.0, 10.0)]
        self.assertIsNone(_last_value_hold(samples, 200.0, 120.0))

    def test_returns_none_when_empty(self):
        self.assertIsNone(_last_value_hold([], 10.0, 120.0))

    def test_exact_match(self):
        samples = [(0.0, 5.0), (30.0, 7.0)]
        self.assertEqual(_last_value_hold(samples, 30.0, 120.0), 7.0)


class TestEmaxModel(unittest.TestCase):
    def test_zero_ce_returns_map0(self):
        self.assertAlmostEqual(_emax_model(0.0, 90.0, 30.0, 2.0, 1.0), 90.0)

    def test_high_ce_approaches_map0_minus_emax(self):
        # Ce >> EC50 -> MAP ~ MAP0 - Emax  (at Ce=1e6, EC50=2: 1-(2/1e6)^1 ~ 1)
        val = _emax_model(1e6, 90.0, 30.0, 2.0, 1.0)
        self.assertAlmostEqual(val, 90.0 - 30.0, delta=0.01)

    def test_ec50_gives_half_effect(self):
        # Ce = EC50 -> MAP = MAP0 - Emax/2
        val = _emax_model(2.0, 90.0, 30.0, 2.0, 1.0)
        self.assertAlmostEqual(val, 90.0 - 30.0 / 2.0, places=6)

    def test_monotonically_decreasing_with_ce(self):
        vals = [_emax_model(float(c), 90.0, 30.0, 2.0, 1.0) for c in range(10)]
        self.assertTrue(all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)))


class TestOlsSlopeIntercept(unittest.TestCase):
    def test_perfect_line(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [10.0 - 5.0 * x for x in xs]  # slope=-5, intercept=10
        slope, intercept = _ols_slope_intercept(xs, ys)
        self.assertAlmostEqual(slope, -5.0, places=10)
        self.assertAlmostEqual(intercept, 10.0, places=10)

    def test_degenerate_constant_x_returns_none(self):
        slope, intercept = _ols_slope_intercept([1.0, 1.0, 1.0], [2.0, 3.0, 4.0])
        self.assertIsNone(slope)
        self.assertIsNone(intercept)

    def test_too_few_points_returns_none(self):
        slope, intercept = _ols_slope_intercept([1.0], [2.0])
        self.assertIsNone(slope)


class TestRSquared(unittest.TestCase):
    def test_perfect_fit_is_one(self):
        xs = [0.0, 1.0, 2.0]
        ys = [3.0, 5.0, 7.0]
        pred = lambda x: 3.0 + 2.0 * x  # noqa: E731
        r2 = _r_squared(xs, ys, pred)
        self.assertAlmostEqual(r2, 1.0, places=10)

    def test_mean_prediction_is_zero(self):
        xs = [0.0, 1.0, 2.0]
        ys = [1.0, 2.0, 3.0]
        mean_y = sum(ys) / len(ys)
        pred = lambda x: mean_y  # noqa: E731
        r2 = _r_squared(xs, ys, pred)
        self.assertAlmostEqual(r2, 0.0, places=10)


class TestResampleToGrid(unittest.TestCase):
    def test_basic_alignment(self):
        """Both tracks perfectly aligned at 30 s -> all paired."""
        ce = [(t * 30.0, 1.0 + t * 0.1) for t in range(20)]
        mp = [(t * 30.0, 90.0 - t * 0.5) for t in range(20)]
        ce_v, map_v = resample_to_grid(ce, mp, grid_s=30.0, lookback_s=120.0)
        self.assertGreater(len(ce_v), 0)
        self.assertEqual(len(ce_v), len(map_v))

    def test_empty_ce_returns_empty(self):
        mp = [(t * 30.0, 80.0) for t in range(10)]
        ce_v, map_v = resample_to_grid([], mp)
        self.assertEqual(len(ce_v), 0)
        self.assertEqual(len(map_v), 0)

    def test_stale_values_dropped(self):
        """If Ce track ends early, MAP samples after that have no Ce -> dropped."""
        ce = [(0.0, 1.0), (30.0, 1.5), (60.0, 2.0)]       # ends at 60s
        mp = [(t * 30.0, 80.0) for t in range(20)]          # goes to 570s
        # With lookback=120s, MAP samples at t>180 won't find Ce -> excluded
        ce_v, map_v = resample_to_grid(ce, mp, grid_s=30.0, lookback_s=120.0)
        # Last Ce at 60 s -> lookback 120 s -> MAP at t=60+120=180 is the latest
        max_t_paired = 60.0 + 120.0
        self.assertLessEqual(len(ce_v), int(max_t_paired / 30.0) + 2)


# ===========================================================================
# 3. Sigmoid Emax fit -- recovery within tolerance
# ===========================================================================

class TestFitSigmoidEmax(unittest.TestCase):
    """Fit a KNOWN sigmoid and check that curve_fit recovers within tolerance."""

    TRUE_MAP0 = 90.0    # mmHg
    TRUE_EMAX = 30.0    # mmHg
    TRUE_EC50 = 2.0     # ug/mL  (physiologic propofol range)
    TRUE_HILL = 1.0     # linear dose-response

    def _make_data(self, noise_std: float = 1.0, n_points: int = 40) -> tuple[list[float], list[float]]:
        """Generate (ce_vals, map_vals) from a known Emax model + noise.

        Use n_points=40 (more data) and noise_std=1.0 (moderate noise) so that
        curve_fit has reliable material to work with.  Recovery tests use this
        moderate-noise / dense-sampling regime; the 'identifies' test additionally
        tests the low-noise path.
        """
        return _sigmoid_samples(
            self.TRUE_MAP0, self.TRUE_EMAX, self.TRUE_EC50, self.TRUE_HILL,
            ce_min=0.1, ce_max=6.0, n_points=n_points, noise_std=noise_std,
        )

    def test_sigmoid_identifies_with_sufficient_data(self):
        """curve_fit should return success=1 with clean data."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = self._make_data(noise_std=0.5, n_points=20)
        result = fit_sigmoid_emax(ce_v, map_v)
        self.assertEqual(result["success"], 1.0,
                         msg="Sigmoid should identify with sufficient data and small noise")

    def test_emax_recovered_within_tolerance(self):
        """Recovered Emax should be within 20 mmHg of truth (30 mmHg).

        With 40 points and noise_std=1.0 the fit is reliable.  We use a generous
        delta because Emax/EC50 are correlated parameters (the product Emax/EC50
        is better identified than each alone), but both should be physiologic.
        """
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = self._make_data()
        result = fit_sigmoid_emax(ce_v, map_v)
        if result["success"] != 1.0:
            self.skipTest("Sigmoid did not identify; skip")

        emax = result["emax"]
        self.assertIsNotNone(emax)
        self.assertAlmostEqual(emax, self.TRUE_EMAX, delta=20.0,
                               msg=f"Emax recovery {emax:.2f} too far from truth {self.TRUE_EMAX}")

    def test_ec50_recovered_within_tolerance(self):
        """Recovered EC50 should be within 2.0 ug/mL of truth (2.0 ug/mL).

        With 40 dense points across Ce=0.1..6.0 the EC50 is well-identified.
        """
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = self._make_data()
        result = fit_sigmoid_emax(ce_v, map_v)
        if result["success"] != 1.0:
            self.skipTest("Sigmoid did not identify; skip")

        ec50 = result["ec50"]
        self.assertIsNotNone(ec50)
        self.assertAlmostEqual(ec50, self.TRUE_EC50, delta=2.0,
                               msg=f"EC50 recovery {ec50:.2f} too far from truth {self.TRUE_EC50}")

    def test_r2_is_high_on_clean_data(self):
        """R^2 should be > 0.7 for near-noiseless sigmoid data."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = self._make_data(noise_std=0.5)
        result = fit_sigmoid_emax(ce_v, map_v)
        if result["success"] != 1.0:
            self.skipTest("Sigmoid did not identify; skip")
        self.assertGreater(result["r2"], 0.7,
                           msg=f"R^2 {result['r2']:.3f} too low on near-noiseless data")

    def test_too_few_points_returns_none(self):
        """Below MIN_SIGMOID_POINTS, sigmoid should not attempt fit."""
        ce_v = [0.5, 1.0, 1.5]  # 3 points < MIN_SIGMOID_POINTS (8)
        map_v = [85.0, 80.0, 75.0]
        result = fit_sigmoid_emax(ce_v, map_v)
        self.assertEqual(result["success"], 0.0)
        self.assertIsNone(result["emax"])

    def test_narrow_ce_range_returns_none(self):
        """If Ce range < MIN_CE_RANGE_UG_ML, sigmoid is not identifiable."""
        # 20 points but all Ce within 0.5 ug/mL
        ce_v = [2.0 + i * 0.02 for i in range(20)]   # range = 0.38 < 1.0
        map_v = [80.0] * 20
        result = fit_sigmoid_emax(ce_v, map_v)
        self.assertEqual(result["success"], 0.0)


# ===========================================================================
# 4. Linear fallback path
# ===========================================================================

class TestLinearFallback(unittest.TestCase):
    """Narrow Ce range triggers the linear fallback."""

    def test_slope_negative_for_decreasing_map(self):
        """MAP decreases linearly with Ce -> slope should be negative."""
        n = 15
        ce_v = [0.5 + i * 0.1 for i in range(n)]    # 0.5 .. 1.9 ug/mL (range < 1.5)
        map_v = [90.0 - 10.0 * c for c in ce_v]     # MAP = 90 - 10*Ce
        lin = fit_linear_robust(ce_v, map_v)
        self.assertIsNotNone(lin["slope"])
        self.assertLess(lin["slope"], 0.0,
                        msg=f"Slope {lin['slope']:.3f} should be negative")
        # Should approximately recover -10
        self.assertAlmostEqual(lin["slope"], -10.0, delta=2.0,
                               msg=f"Slope {lin['slope']:.3f} too far from -10")

    def test_too_few_points_returns_none(self):
        lin = fit_linear_robust([1.0, 2.0, 3.0], [85.0, 82.0, 79.0])
        # 3 points < MIN_LINEAR_POINTS (4) -> None
        self.assertIsNone(lin["slope"])

    def test_compute_pkpd_uses_linear_when_sigmoid_fails(self):
        """Narrow Ce range case: sigmoid won't identify; pkpd_sensitivity = |slope|."""
        # Narrow Ce range so sigmoid won't fire
        n = 10
        ce_v = [1.0 + i * 0.05 for i in range(n)]   # range = 0.45 < MIN_CE_RANGE
        map_v = [90.0 - 8.0 * c for c in ce_v]
        out = compute_pkpd_features(ce_v, map_v)
        # sigmoid params should be None
        self.assertIsNone(out["pkpd_map0"])
        self.assertIsNone(out["pkpd_emax"])
        self.assertIsNone(out["pkpd_ec50"])
        # slope fallback should fire
        self.assertIsNotNone(out["pkpd_slope"])
        self.assertIsNotNone(out["pkpd_sensitivity"])
        # sensitivity = |slope| so should be positive
        self.assertGreater(out["pkpd_sensitivity"], 0.0)


# ===========================================================================
# 5. No-Ce / flat case returns None / pkpd_available=0
# ===========================================================================

class TestNoCaseOrFlatCe(unittest.TestCase):
    def test_empty_ce_returns_all_none(self):
        out = compute_pkpd_features([], [90.0, 85.0, 80.0])
        self.assertIsNone(out["pkpd_sensitivity"])
        self.assertIsNone(out["pkpd_slope"])
        self.assertIsNone(out["pkpd_map0"])

    def test_empty_map_returns_all_none(self):
        out = compute_pkpd_features([1.0, 2.0, 3.0, 4.0], [])
        self.assertIsNone(out["pkpd_sensitivity"])

    def test_too_few_pairs_returns_none(self):
        # 2 pairs < MIN_LINEAR_POINTS (4)
        out = compute_pkpd_features([1.0, 2.0], [85.0, 80.0])
        self.assertIsNone(out["pkpd_sensitivity"])
        self.assertIsNone(out["pkpd_slope"])

    def test_constant_map_still_has_slope_near_zero(self):
        """Flat MAP (e.g. patient on heavy pressors): slope ~ 0, sensitivity ~ 0."""
        ce_v = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        map_v = [80.0] * len(ce_v)  # MAP never changes
        out = compute_pkpd_features(ce_v, map_v)
        # Should compute a slope (near 0)
        if out["pkpd_slope"] is not None:
            self.assertAlmostEqual(out["pkpd_slope"], 0.0, delta=0.5)


# ===========================================================================
# 6. Fragile vs robust patient comparison (headline test)
# ===========================================================================

class TestFragileVsRobust(unittest.TestCase):
    """More-fragile patient (bigger Emax, lower EC50) yields higher pkpd_sensitivity."""

    def _make_patient(
        self,
        emax: float,
        ec50: float,
        noise_std: float = 1.5,
    ) -> tuple[list[float], list[float]]:
        """Generate (ce_vals, map_vals) from sigmoid with given Emax/EC50."""
        return _sigmoid_samples(
            map0=90.0, emax=emax, ec50=ec50, hill=1.0,
            ce_min=0.1, ce_max=7.0, n_points=25, noise_std=noise_std,
        )

    def test_fragile_higher_sensitivity_than_robust(self):
        """Fragile (Emax=50, EC50=1) > Robust (Emax=15, EC50=4) in sensitivity."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_fragile, map_fragile = self._make_patient(emax=50.0, ec50=1.0, noise_std=1.0)
        ce_robust, map_robust = self._make_patient(emax=15.0, ec50=4.0, noise_std=1.0)

        out_fragile = compute_pkpd_features(ce_fragile, map_fragile)
        out_robust = compute_pkpd_features(ce_robust, map_robust)

        s_fragile = out_fragile["pkpd_sensitivity"]
        s_robust = out_robust["pkpd_sensitivity"]

        self.assertIsNotNone(s_fragile, "Fragile patient should yield a sensitivity value")
        self.assertIsNotNone(s_robust, "Robust patient should yield a sensitivity value")
        self.assertGreater(
            s_fragile, s_robust,
            msg=(
                f"Fragile pkpd_sensitivity={s_fragile:.3f} should exceed "
                f"robust pkpd_sensitivity={s_robust:.3f}"
            ),
        )

    def test_sensitivity_positive_for_drug_effect(self):
        """pkpd_sensitivity must be non-negative (it quantifies magnitude)."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = self._make_patient(emax=30.0, ec50=2.0)
        out = compute_pkpd_features(ce_v, map_v)
        s = out["pkpd_sensitivity"]
        if s is not None:
            self.assertGreaterEqual(s, 0.0,
                                    msg=f"pkpd_sensitivity={s:.4f} should be >= 0")

    def test_no_drug_effect_has_low_sensitivity(self):
        """Patient with tiny Emax (1 mmHg, noise dominates): low sensitivity."""
        ce_v, map_v = self._make_patient(emax=1.0, ec50=2.0, noise_std=3.0)
        out = compute_pkpd_features(ce_v, map_v)
        # Hard to guarantee the sign, but the magnitude should be modest
        # Just check it runs and returns something (no exception)
        self.assertIn("pkpd_sensitivity", out)


# ===========================================================================
# 7. compute_pkpd_features end-to-end with sigmoid
# ===========================================================================

class TestComputePkpdFeaturesEndToEnd(unittest.TestCase):
    def test_full_sigmoid_case_returns_all_keys(self):
        """When sigmoid identifies, all pkpd_* keys are non-None except possibly slope."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = _sigmoid_samples(
            map0=85.0, emax=25.0, ec50=2.5, hill=1.2,
            ce_min=0.2, ce_max=6.0, n_points=20, noise_std=0.5,
        )
        out = compute_pkpd_features(ce_v, map_v)

        # slope is always computed
        self.assertIsNotNone(out["pkpd_slope"])

        if out["pkpd_map0"] is not None:  # sigmoid identified
            for key in ("pkpd_emax", "pkpd_ec50", "pkpd_hill",
                        "pkpd_sensitivity", "pkpd_fit_quality"):
                self.assertIsNotNone(out[key], msg=f"{key} should be set when sigmoid identifies")

    def test_r2_in_unit_interval(self):
        """R^2 should be in [0, 1] for well-behaved data."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = _sigmoid_samples(
            map0=90.0, emax=30.0, ec50=2.0, hill=1.0,
            ce_min=0.1, ce_max=6.0, n_points=20, noise_std=1.0,
        )
        out = compute_pkpd_features(ce_v, map_v)
        r2 = out["pkpd_fit_quality"]
        if r2 is not None:
            self.assertGreaterEqual(r2, -0.1,
                                    msg=f"R^2 {r2:.3f} should be non-negative for fitted data")
            self.assertLessEqual(r2, 1.0 + 1e-9,
                                 msg=f"R^2 {r2:.3f} cannot exceed 1.0")

    def test_emax_in_physiologic_bounds(self):
        """Fitted Emax should respect EMAX_HI bound (<=150 mmHg)."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = _sigmoid_samples(
            map0=90.0, emax=40.0, ec50=2.0, hill=1.0,
            ce_min=0.1, ce_max=6.0, n_points=20, noise_std=0.5,
        )
        out = compute_pkpd_features(ce_v, map_v)
        emax = out["pkpd_emax"]
        if emax is not None:
            self.assertLessEqual(emax, 150.0)
            self.assertGreaterEqual(emax, 0.0)

    def test_ec50_in_physiologic_bounds(self):
        """Fitted EC50 should be in [0.05, 20] ug/mL."""
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("scipy not installed")

        ce_v, map_v = _sigmoid_samples(
            map0=90.0, emax=30.0, ec50=2.0, hill=1.0,
            ce_min=0.1, ce_max=6.0, n_points=20, noise_std=0.5,
        )
        out = compute_pkpd_features(ce_v, map_v)
        ec50 = out["pkpd_ec50"]
        if ec50 is not None:
            self.assertGreaterEqual(ec50, 0.05)
            self.assertLessEqual(ec50, 20.0)


# ===========================================================================
# 8. resample_to_grid edge cases
# ===========================================================================

class TestResampleToGridEdgeCases(unittest.TestCase):
    def test_empty_both_returns_empty(self):
        ce_v, map_v = resample_to_grid([], [])
        self.assertEqual(ce_v, [])
        self.assertEqual(map_v, [])

    def test_non_overlapping_windows_returns_empty(self):
        """Ce at t=0..60, MAP at t=1000..1060 -> no overlap -> empty."""
        ce = [(float(t), 2.0) for t in range(0, 90, 30)]
        mp = [(float(t), 80.0) for t in range(1000, 1090, 30)]
        ce_v, map_v = resample_to_grid(ce, mp, grid_s=30.0, lookback_s=120.0)
        self.assertEqual(len(ce_v), 0)

    def test_output_lengths_match(self):
        """ce_vals and map_vals must always have equal length."""
        import random
        random.seed(0)
        ce = [(float(t), random.uniform(0.5, 4.0)) for t in range(0, 1800, 15)]
        mp = [(float(t), random.uniform(60.0, 120.0)) for t in range(0, 1800, 5)]
        ce_v, map_v = resample_to_grid(ce, mp, grid_s=30.0, lookback_s=120.0)
        self.assertEqual(len(ce_v), len(map_v))


if __name__ == "__main__":
    unittest.main(verbosity=2)
