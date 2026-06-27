"""test_drug_brain_circ.py -- Offline unit tests for the drug->brain->circ triad.

All tests are pure-math / in-memory; no network access, no VitalDB downloads,
stdlib only (no numpy).  Each pure helper (_align_grid, _ols_slope, _ols2) and
the case-level compute_triad() is tested against hand-built series with KNOWN
expected direction (cerebral potency, circulatory effect, fragility ratio,
residual instability).  Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_drug_brain_circ -v
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.drug_brain_circ import (
    # Module-level constants
    SPECS,
    ALIGN_DT_S, MAX_STALE_S, MIN_JOINT_POINTS, SLOPE_EPS,
    CE_MIN, CE_MAX, BIS_MIN, BIS_MAX, MAP_MIN, MAP_MAX,
    # Pure helpers
    _align_grid,
    _ols_slope,
    _ols2,
    # Case-level
    compute_triad,
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
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_all_pk_tier(self):
        """Whole triad is pk-tier (needs BIS + propofol Ce pump)."""
        for s in SPECS:
            self.assertEqual(s.fset, "pk", msg=f"{s.name} fset={s.fset!r}")

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "drugbrain_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)), "Duplicate feature names")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "drugbrain_available",
            "drugbrain_ce_bis_slope",
            "drugbrain_ce_map_slope",
            "drugbrain_map_per_bis_suppression",
            "drugbrain_resid_instability",
        }
        self.assertFalse(required - names, f"Missing specs: {required - names}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 5, "Expected exactly 5 triad feature specs")


# ===========================================================================
# 2. Pure helper: _align_grid
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def test_perfectly_synchronized_signals(self):
        """Three signals on identical timestamps align 1:1."""
        n = 10
        ce = [(i * 10.0, float(i)) for i in range(n)]
        bis = [(i * 10.0, 100.0 - i) for i in range(n)]
        mp = [(i * 10.0, 80.0 - i) for i in range(n)]
        out = _align_grid({"ce": ce, "bis": bis, "map": mp},
                          0.0, 90.0, dt=10.0, max_stale=15.0)
        self.assertEqual(len(out["ce"]), n)
        self.assertEqual(len(out["bis"]), n)
        self.assertEqual(len(out["map"]), n)
        # Index-aligned: ce[3] from t=30 etc.
        self.assertEqual(out["ce"][3], 3.0)
        self.assertEqual(out["bis"][3], 97.0)
        self.assertEqual(out["map"][3], 77.0)

    def test_output_lists_equal_length(self):
        ce = [(i * 10.0, float(i)) for i in range(20)]
        bis = [(i * 7.0, 100.0 - i) for i in range(30)]   # off-grid
        mp = [(i * 13.0, 80.0 - i) for i in range(15)]    # off-grid
        out = _align_grid({"ce": ce, "bis": bis, "map": mp}, 0.0, 100.0)
        lengths = {k: len(v) for k, v in out.items()}
        self.assertEqual(len(set(lengths.values())), 1,
                         f"Aligned lists must be equal length: {lengths}")

    def test_last_value_hold(self):
        """Sparse signal held forward up to max_stale; index reflects held value."""
        # ce updates every 10s; bis only at t=0 (value 50) then t=40 (value 60)
        ce = [(i * 10.0, float(i)) for i in range(6)]   # t=0..50
        bis = [(0.0, 50.0), (40.0, 60.0)]
        mp = [(i * 10.0, 80.0) for i in range(6)]
        out = _align_grid({"ce": ce, "bis": bis, "map": mp},
                          0.0, 50.0, dt=10.0, max_stale=15.0)
        # At t=0,10 bis held=50 (fresh within 15s); t=20 stale (20>15) => drop grid pt;
        # t=30 stale; t=40 bis=60 fresh; t=50 held=60 (10s old, fresh)
        # So kept grid points: t=0,10,40,50 => 4 points
        self.assertEqual(len(out["bis"]), 4)
        self.assertEqual(out["bis"], [50.0, 50.0, 60.0, 60.0])

    def test_staleness_drops_grid_point(self):
        """A grid time where any signal is stale is dropped from ALL signals."""
        ce = [(0.0, 1.0), (100.0, 2.0)]   # huge gap
        bis = [(i * 10.0, 50.0) for i in range(11)]
        mp = [(i * 10.0, 80.0) for i in range(11)]
        out = _align_grid({"ce": ce, "bis": bis, "map": mp},
                          0.0, 100.0, dt=10.0, max_stale=15.0)
        # ce fresh only near t=0 (t=0,10) and t=100; t=20..90 ce stale => dropped
        self.assertEqual(len(out["ce"]), len(out["bis"]))
        self.assertEqual(len(out["ce"]), len(out["map"]))
        # Kept: t=0, t=10, t=100 => 3 points
        self.assertEqual(len(out["ce"]), 3)

    def test_missing_signal_returns_empty(self):
        """If any signal has no samples at all, all outputs are empty."""
        ce = [(i * 10.0, float(i)) for i in range(10)]
        bis: list[tuple[float, float]] = []
        mp = [(i * 10.0, 80.0) for i in range(10)]
        out = _align_grid({"ce": ce, "bis": bis, "map": mp}, 0.0, 90.0)
        self.assertEqual(out["ce"], [])
        self.assertEqual(out["bis"], [])
        self.assertEqual(out["map"], [])

    def test_empty_window_returns_empty(self):
        ce = [(i * 10.0, float(i)) for i in range(10)]
        out = _align_grid({"ce": ce}, 50.0, 40.0)  # t_end < t_start
        self.assertEqual(out["ce"], [])

    def test_never_exceeds_t_end(self):
        """Grid stops at t_end; signal data beyond t_end is not sampled."""
        ce = [(i * 10.0, float(i)) for i in range(20)]   # extends to t=190
        bis = [(i * 10.0, 50.0) for i in range(20)]
        mp = [(i * 10.0, 80.0) for i in range(20)]
        out = _align_grid({"ce": ce, "bis": bis, "map": mp},
                          0.0, 50.0, dt=10.0, max_stale=15.0)
        # grid: t=0,10,20,30,40,50 => 6 points max; ce values are indices 0..5
        self.assertLessEqual(len(out["ce"]), 6)
        self.assertTrue(all(v <= 5.0 for v in out["ce"]),
                        "Must not sample ce beyond t_end=50 (value>5)")


# ===========================================================================
# 3. Pure helper: _ols_slope
# ===========================================================================

class TestOlsSlope(unittest.TestCase):
    def test_known_positive_slope(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 5.0, 7.0, 9.0]   # y = 1 + 2x
        slope = _ols_slope(xs, ys)
        self.assertIsNotNone(slope)
        self.assertAlmostEqual(slope, 2.0, places=6)

    def test_known_negative_slope(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 8.0, 6.0, 4.0]   # y = 12 - 2x
        slope = _ols_slope(xs, ys)
        self.assertIsNotNone(slope)
        self.assertAlmostEqual(slope, -2.0, places=6)

    def test_none_when_too_few_points(self):
        self.assertIsNone(_ols_slope([1.0, 2.0], [3.0, 4.0]))

    def test_none_when_no_x_variance(self):
        xs = [5.0, 5.0, 5.0, 5.0]
        ys = [1.0, 2.0, 3.0, 4.0]
        self.assertIsNone(_ols_slope(xs, ys))

    def test_none_when_length_mismatch(self):
        self.assertIsNone(_ols_slope([1.0, 2.0, 3.0], [1.0, 2.0]))


# ===========================================================================
# 4. Pure helper: _ols2 (two-regressor OLS + residual SD)
# ===========================================================================

class TestOls2(unittest.TestCase):
    def test_exact_plane_zero_residual(self):
        """y = 1 + 2*x1 - 3*x2 exactly => residual SD ~ 0, coefficients recovered."""
        x1 = [0.0, 1.0, 2.0, 0.0, 3.0, 1.0]
        x2 = [0.0, 0.0, 1.0, 2.0, 1.0, 3.0]
        y = [1.0 + 2.0 * a - 3.0 * b for a, b in zip(x1, x2)]
        res = _ols2(y, x1, x2)
        self.assertIsNotNone(res)
        b0, b1, b2, sd = res
        self.assertAlmostEqual(b0, 1.0, places=5)
        self.assertAlmostEqual(b1, 2.0, places=5)
        self.assertAlmostEqual(b2, -3.0, places=5)
        self.assertAlmostEqual(sd, 0.0, places=5)

    def test_nonzero_residual_detected(self):
        """Adding noise off the plane yields a positive residual SD."""
        x1 = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        x2 = [0.0, 2.0, 1.0, 4.0, 2.0, 5.0]   # not collinear with x1
        base = [1.0 + 2.0 * a - 1.0 * b for a, b in zip(x1, x2)]
        # Perturb y so it doesn't lie exactly on a plane
        y = [v + (1.0 if i % 2 == 0 else -1.0) for i, v in enumerate(base)]
        res = _ols2(y, x1, x2)
        self.assertIsNotNone(res)
        _, _, _, sd = res
        self.assertGreater(sd, 0.0, "Off-plane data must have positive residual SD")

    def test_none_when_too_few_points(self):
        x1 = [0.0, 1.0, 2.0, 3.0]
        x2 = [1.0, 2.0, 3.0, 4.0]
        y = [1.0, 2.0, 3.0, 4.0]
        self.assertIsNone(_ols2(y, x1, x2))   # only 4 points (< 5)

    def test_none_when_collinear_regressors(self):
        """x2 == 2*x1 => singular normal equations => None."""
        x1 = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        x2 = [2.0 * a for a in x1]
        y = [1.0, 2.0, 1.5, 3.0, 2.5, 4.0]
        self.assertIsNone(_ols2(y, x1, x2))

    def test_none_when_no_variance(self):
        """Constant regressors => singular => None."""
        x1 = [1.0] * 6
        x2 = [2.0] * 6
        y = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        self.assertIsNone(_ols2(y, x1, x2))

    def test_none_when_length_mismatch(self):
        self.assertIsNone(_ols2([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0], [3.0, 4.0]))


# ===========================================================================
# 5. Case-level compute_triad
# ===========================================================================

class TestComputeTriad(unittest.TestCase):
    def _grid_series(self, fn, n: int, dt: float = 10.0) -> list[tuple[float, float]]:
        return [(i * dt, fn(i)) for i in range(n)]

    def test_available_and_directions(self):
        """Ce rises; BIS falls (negative cerebral slope); MAP falls (negative)."""
        n = 40  # >= MIN_JOINT_POINTS
        ce = self._grid_series(lambda i: 1.0 + 2.0 * i / (n - 1), n)
        bis = self._grid_series(lambda i: 90.0 - 40.0 * i / (n - 1), n)   # falls
        mp = self._grid_series(lambda i: 85.0 - 20.0 * i / (n - 1), n)    # falls
        row = compute_triad(ce, bis, mp, 0.0, (n - 1) * 10.0)
        self.assertEqual(row["drugbrain_available"], 1)
        self.assertIsNotNone(row["drugbrain_ce_bis_slope"])
        self.assertLess(row["drugbrain_ce_bis_slope"], 0.0,
                        "BIS falls as Ce rises => negative cerebral slope")
        self.assertIsNotNone(row["drugbrain_ce_map_slope"])
        self.assertLess(row["drugbrain_ce_map_slope"], 0.0,
                        "MAP falls as Ce rises => negative circulatory slope")

    def test_fragility_ratio_sign_and_magnitude(self):
        """Both slopes negative => ratio positive; fragile patient => larger ratio."""
        n = 40
        ce = self._grid_series(lambda i: 1.0 + 2.0 * i / (n - 1), n)
        bis = self._grid_series(lambda i: 90.0 - 40.0 * i / (n - 1), n)  # same depth
        # Fragile: MAP collapses a lot; resilient: MAP barely moves
        mp_fragile = self._grid_series(lambda i: 90.0 - 40.0 * i / (n - 1), n)
        mp_resilient = self._grid_series(lambda i: 90.0 - 2.0 * i / (n - 1), n)
        r_fragile = compute_triad(ce, bis, mp_fragile, 0.0, (n - 1) * 10.0)
        r_resil = compute_triad(ce, bis, mp_resilient, 0.0, (n - 1) * 10.0)
        rf = r_fragile["drugbrain_map_per_bis_suppression"]
        rr = r_resil["drugbrain_map_per_bis_suppression"]
        self.assertIsNotNone(rf)
        self.assertIsNotNone(rr)
        # Both cerebral & circulatory slopes negative => ratio positive
        self.assertGreater(rf, 0.0)
        self.assertGreater(rr, 0.0)
        # Fragile patient collapses MORE MAP per unit BIS suppression
        self.assertGreater(rf, rr,
                           "Fragile patient => larger MAP-per-BIS-suppression ratio")

    def test_fragility_ratio_none_when_bis_flat(self):
        """No cerebral response (BIS flat) => |ce_bis_slope|<eps => ratio None."""
        n = 40
        ce = self._grid_series(lambda i: 1.0 + 2.0 * i / (n - 1), n)
        bis = self._grid_series(lambda i: 50.0, n)          # flat BIS
        mp = self._grid_series(lambda i: 85.0 - 20.0 * i / (n - 1), n)
        row = compute_triad(ce, bis, mp, 0.0, (n - 1) * 10.0)
        # ce_bis_slope ~ 0 => ratio guarded to None
        self.assertIsNone(row["drugbrain_map_per_bis_suppression"])

    def test_resid_instability_present(self):
        n = 40
        ce = self._grid_series(lambda i: 1.0 + 2.0 * i / (n - 1), n)
        bis = self._grid_series(lambda i: 90.0 - 40.0 * i / (n - 1), n)
        # MAP with structure + alternating perturbation off the plane
        mp = self._grid_series(
            lambda i: 85.0 - 0.3 * i + (2.0 if i % 2 == 0 else -2.0), n
        )
        row = compute_triad(ce, bis, mp, 0.0, (n - 1) * 10.0)
        self.assertIsNotNone(row["drugbrain_resid_instability"])
        self.assertGreater(row["drugbrain_resid_instability"], 0.0,
                           "Off-plane MAP lability => positive residual instability")

    def test_unavailable_when_too_few_joint_points(self):
        """Fewer than MIN_JOINT_POINTS aligned points => available=0, rest None."""
        n = 10  # < 30
        ce = self._grid_series(lambda i: 1.0 + 0.1 * i, n)
        bis = self._grid_series(lambda i: 90.0 - i, n)
        mp = self._grid_series(lambda i: 85.0 - i, n)
        row = compute_triad(ce, bis, mp, 0.0, (n - 1) * 10.0)
        self.assertEqual(row["drugbrain_available"], 0)
        for s in SPECS:
            if s.name != "drugbrain_available":
                self.assertIsNone(row[s.name], f"{s.name} must be None when unavailable")

    def test_unavailable_when_signal_missing(self):
        """Missing BIS entirely => nothing aligns => available=0, rest None."""
        n = 40
        ce = self._grid_series(lambda i: 1.0 + 0.1 * i, n)
        bis: list[tuple[float, float]] = []   # missing brain signal
        mp = self._grid_series(lambda i: 85.0 - 0.1 * i, n)
        row = compute_triad(ce, bis, mp, 0.0, (n - 1) * 10.0)
        self.assertEqual(row["drugbrain_available"], 0)
        for s in SPECS:
            if s.name != "drugbrain_available":
                self.assertIsNone(row[s.name])

    def test_empty_all_signals(self):
        row = compute_triad([], [], [], 0.0, 100.0)
        self.assertEqual(row["drugbrain_available"], 0)
        self.assertIsNone(row["drugbrain_ce_bis_slope"])
        self.assertIsNone(row["drugbrain_resid_instability"])


# ===========================================================================
# 6. Leakage discipline: alignment never crosses t_end
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    def test_align_grid_respects_t_end_cutoff(self):
        """Aberrant values placed AFTER t_end must not enter the aligned series."""
        n = 40
        # Normal Ce/BIS/MAP for t in [0, 390], then poisoned values after t_end
        ce = [(i * 10.0, 2.0) for i in range(n)] + [(500.0 + i * 10.0, 99.0) for i in range(5)]
        bis = [(i * 10.0, 50.0) for i in range(n)] + [(500.0 + i * 10.0, 1.0) for i in range(5)]
        mp = [(i * 10.0, 80.0) for i in range(n)] + [(500.0 + i * 10.0, 199.0) for i in range(5)]
        t_end = (n - 1) * 10.0  # 390
        out = _align_grid({"ce": ce, "bis": bis, "map": mp}, 0.0, t_end,
                          dt=10.0, max_stale=15.0)
        # Poisoned post-cutoff values (99/1/199) must never appear
        self.assertTrue(all(v == 2.0 for v in out["ce"]),
                        "Post-cutoff Ce=99 leaked into aligned grid")
        self.assertTrue(all(v == 50.0 for v in out["bis"]))
        self.assertTrue(all(v == 80.0 for v in out["map"]))


# ===========================================================================
# 7. extract() smoke test (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """extract() lazy-imports first_available/download_track from
    vitaldb_aki.data.tracks, so we patch at the source module."""

    def test_extract_none_row_when_no_ce(self):
        """No propofol Ce track => available=0, all others None."""
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.drug_brain_circ import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])
            row = result["1"]
            self.assertEqual(row["drugbrain_available"], 0)
            for s in SPECS:
                if s.name != "drugbrain_available":
                    self.assertIsNone(row[s.name])

    def test_extract_computes_triad_with_tracks(self):
        """With Ce + BIS + MAP tracks, triad features are non-None."""
        import unittest.mock as mock

        n = 40
        dt = 10.0
        ce_track = [(i * dt, 1.0 + 2.0 * i / (n - 1)) for i in range(n)]
        bis_track = [(i * dt, 90.0 - 40.0 * i / (n - 1)) for i in range(n)]
        map_track = [(i * dt, 85.0 - 20.0 * i / (n - 1)) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("PPF20_CE" in tn for tn in tnames):
                return ("Orchestra/PPF20_CE", ce_track)
            if any("BIS" in tn for tn in tnames):
                return ("BIS/BIS", bis_track)
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.drug_brain_circ import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {
                "42": {"caseid": "42", "anestart": 0.0, "opend": float(n * dt)}
            }
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["drugbrain_available"], 1)
        self.assertIsNotNone(row["drugbrain_ce_bis_slope"])
        self.assertLess(row["drugbrain_ce_bis_slope"], 0.0)
        self.assertIsNotNone(row["drugbrain_ce_map_slope"])
        self.assertLess(row["drugbrain_ce_map_slope"], 0.0)
        self.assertIsNotNone(row["drugbrain_map_per_bis_suppression"])
        self.assertGreater(row["drugbrain_map_per_bis_suppression"], 0.0)
        self.assertIsNotNone(row["drugbrain_resid_instability"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
