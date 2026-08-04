"""test_perfusion_cascade.py -- Offline unit tests for the perfusion-cascade family (§7F-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
The THREE-WITNESS occult-hypoperfusion signature triangulates MAP -> EtCO2 ->
SpO2.  Each pure helper (alignment, correlation, lagged-corr, joint-condition
fraction, tri-witness co-drop, 3-way trend concordance) is tested against
hand-built synthetic series with a KNOWN expected direction, mirroring
test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_perfusion_cascade -v
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.perfusion_cascade import (
    # Module-level constants
    SPECS,
    MAP_ADEQUATE, SPO2_MARGINAL, ETCO2_LOW,
    GRID_DT_S, MAX_STALE_S, MIN_JOINT_POINTS,
    # Pure helpers
    _align_grid,
    _jointly_valid_indices,
    _pearson,
    _lagged_max_corr,
    _frac_joint_condition,
    _slope_sign,
    _trend_sign_concordance,
    # Case-level
    compute_cascade_features,
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
            self.assertNotEqual(s.timing, "postop", msg=f"{s.name} has postop timing!")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "pcasc_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "pcasc_available",
            "pcasc_map_etco2_corr",
            "pcasc_map_etco2_lagcorr",
            "pcasc_downstream_decouple_frac",
            "pcasc_tri_codrop_frac",
            "pcasc_perfusion_coherence",
        }
        self.assertFalse(required - names, f"Missing: {required - names}")

    def test_coherence_is_pk_tier(self):
        by_name = {s.name: s for s in SPECS}
        self.assertEqual(by_name["pcasc_perfusion_coherence"].fset, "pk")
        # The rest are comprehensive.
        for s in SPECS:
            if s.name != "pcasc_perfusion_coherence":
                self.assertEqual(s.fset, "comprehensive", msg=f"{s.name} fset={s.fset!r}")


# ===========================================================================
# 2. _align_grid -- the multi-signal common-grid helper
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def test_grid_times_spacing_and_bounds(self):
        sig = {"a": [(0.0, 1.0)]}
        grid, aligned = _align_grid(sig, 0.0, 20.0, dt=5.0, max_stale=100.0)
        self.assertEqual(grid, [0.0, 5.0, 10.0, 15.0, 20.0])
        # Never exceeds t_end.
        self.assertLessEqual(max(grid), 20.0)

    def test_last_value_hold(self):
        # Sample at t=0 (v=10), t=10 (v=20). Grid step 5.
        sig = {"a": [(0.0, 10.0), (10.0, 20.0)]}
        grid, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        # t=0 -> 10 (exact), t=5 -> hold 10 (most recent <=5), t=10 -> 20.
        self.assertEqual(aligned["a"], [10.0, 10.0, 20.0])

    def test_none_before_first_sample(self):
        # First sample at t=10; grid starts at 0 => first two points None.
        sig = {"a": [(10.0, 5.0)]}
        grid, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        self.assertEqual(aligned["a"], [None, None, 5.0])

    def test_stale_sample_becomes_none(self):
        # Sample at t=0 only; max_stale=10. Grid out to 30.
        sig = {"a": [(0.0, 7.0)]}
        grid, aligned = _align_grid(sig, 0.0, 30.0, dt=5.0, max_stale=10.0)
        # t=0 ->7, t=5 ->7, t=10 ->7 (age 10, == max_stale, allowed),
        # t=15 ->None (age 15 > 10), t=20,25,30 -> None.
        self.assertEqual(aligned["a"], [7.0, 7.0, 7.0, None, None, None, None])

    def test_multiple_signals_aligned(self):
        sig = {
            "map": [(0.0, 80.0), (10.0, 70.0)],
            "etco2": [(0.0, 40.0), (10.0, 25.0)],
        }
        grid, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        self.assertEqual(aligned["map"], [80.0, 80.0, 70.0])
        self.assertEqual(aligned["etco2"], [40.0, 40.0, 25.0])

    def test_empty_signal(self):
        sig: dict[str, list[tuple[float, float]]] = {"a": []}
        grid, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0)
        self.assertEqual(aligned["a"], [None, None, None])

    def test_jointly_valid_indices(self):
        aligned = {
            "map": [80.0, None, 70.0, 75.0],
            "etco2": [40.0, 30.0, None, 25.0],
        }
        idxs = _jointly_valid_indices(aligned, ["map", "etco2"])
        self.assertEqual(idxs, [0, 3])


# ===========================================================================
# 3. _pearson
# ===========================================================================

class TestPearson(unittest.TestCase):
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [2.0, 4.0, 6.0, 8.0]
        self.assertAlmostEqual(_pearson(xs, ys), 1.0, places=6)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [8.0, 6.0, 4.0, 2.0]
        self.assertAlmostEqual(_pearson(xs, ys), -1.0, places=6)

    def test_none_when_too_few(self):
        self.assertIsNone(_pearson([1.0], [2.0]))

    def test_none_when_zero_variance(self):
        self.assertIsNone(_pearson([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]))

    def test_clamped_to_unit_range(self):
        r = _pearson([1.0, 2.0, 3.0], [3.0, 6.0, 9.0])
        self.assertLessEqual(r, 1.0)
        self.assertGreaterEqual(r, -1.0)


# ===========================================================================
# 4. _lagged_max_corr -- does EtCO2 FOLLOW MAP?
# ===========================================================================

class TestLaggedMaxCorr(unittest.TestCase):
    def test_zero_lag_perfect(self):
        # Identical aligned series => peak corr 1.0 (at lag 0).
        x = [float(i) for i in range(20)]
        y = list(x)
        r = _lagged_max_corr(x, y, dt=5.0, lags_s=(0.0, 5.0, 10.0))
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_follower_signal_peaks_at_lag(self):
        # y is x shifted LATER by 2 grid points (10 s at dt=5): y[i] = x[i-2].
        # So x(t) vs y(t+lag) correlates best at lag = 10 s.
        base = [float((i * 7) % 13) for i in range(40)]  # non-monotone pattern
        x = base
        y = [None, None] + base[:-2]  # type: ignore[list-item]
        r = _lagged_max_corr(x, y, dt=5.0, lags_s=(0.0, 5.0, 10.0, 15.0))
        self.assertIsNotNone(r)
        # At lag=10s (shift=2): x[i] vs y[i+2]=x[i] => perfect.
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_none_when_no_overlap(self):
        x = [None, None]  # type: ignore[list-item]
        y = [None, None]  # type: ignore[list-item]
        self.assertIsNone(_lagged_max_corr(x, y, dt=5.0, lags_s=(0.0,)))


# ===========================================================================
# 5. _frac_joint_condition -- downstream decoupling fraction
# ===========================================================================

class TestFracJointCondition(unittest.TestCase):
    def _decouple_pred(self, vals: dict[str, float]) -> bool:
        if vals.get("map", -1.0) < MAP_ADEQUATE:
            return False
        etco2_bad = vals.get("etco2") is not None and vals["etco2"] < ETCO2_LOW
        spo2_bad = "spo2" in vals and vals["spo2"] < SPO2_MARGINAL
        return etco2_bad or spo2_bad

    def test_all_decoupled(self):
        # MAP adequate everywhere, EtCO2 always low => fraction 1.0.
        aligned = {
            "map": [80.0, 80.0, 80.0, 80.0],
            "etco2": [25.0, 25.0, 25.0, 25.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertAlmostEqual(f, 1.0, places=6)

    def test_none_decoupled_when_flow_ok(self):
        aligned = {
            "map": [80.0, 80.0, 80.0],
            "etco2": [40.0, 40.0, 40.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertAlmostEqual(f, 0.0, places=6)

    def test_map_low_excludes_point(self):
        # MAP < 65 => not "pressure fine" => never counted even if EtCO2 low.
        aligned = {
            "map": [55.0, 55.0, 55.0],
            "etco2": [25.0, 25.0, 25.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertAlmostEqual(f, 0.0, places=6)

    def test_half(self):
        aligned = {
            "map": [80.0, 80.0, 80.0, 80.0],
            "etco2": [25.0, 25.0, 40.0, 40.0],  # first half low
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertAlmostEqual(f, 0.5, places=6)

    def test_spo2_triggers_decouple(self):
        # EtCO2 fine but SpO2 marginal => still decoupled.
        aligned = {
            "map": [80.0, 80.0],
            "etco2": [40.0, 40.0],
            "spo2": [92.0, 92.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertAlmostEqual(f, 1.0, places=6)

    def test_none_when_no_joint_points(self):
        aligned = {
            "map": [None, None],  # type: ignore[list-item]
            "etco2": [40.0, 40.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2"], self._decouple_pred)
        self.assertIsNone(f)


# ===========================================================================
# 6. Tri-witness co-drop fraction (the triangulated signature)
# ===========================================================================

class TestTriCodrop(unittest.TestCase):
    def _tri_pred(self, vals: dict[str, float]) -> bool:
        return (
            vals.get("map", -1.0) >= MAP_ADEQUATE
            and vals.get("etco2", 1e9) < ETCO2_LOW
            and vals.get("spo2", 1e9) < SPO2_MARGINAL
        )

    def test_all_three_bad_under_adequate_pressure(self):
        aligned = {
            "map": [80.0, 80.0, 80.0],
            "etco2": [25.0, 25.0, 25.0],
            "spo2": [90.0, 90.0, 90.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2", "spo2"], self._tri_pred)
        self.assertAlmostEqual(f, 1.0, places=6)

    def test_zero_when_only_two_witnesses_bad(self):
        # SpO2 fine => not a tri co-drop.
        aligned = {
            "map": [80.0, 80.0, 80.0],
            "etco2": [25.0, 25.0, 25.0],
            "spo2": [99.0, 99.0, 99.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2", "spo2"], self._tri_pred)
        self.assertAlmostEqual(f, 0.0, places=6)

    def test_partial_tri_codrop(self):
        # Only the first point has all three bad.
        aligned = {
            "map": [80.0, 80.0, 80.0, 80.0],
            "etco2": [25.0, 40.0, 25.0, 25.0],
            "spo2": [90.0, 90.0, 99.0, 99.0],
        }
        f = _frac_joint_condition(aligned, ["map", "etco2", "spo2"], self._tri_pred)
        self.assertAlmostEqual(f, 0.25, places=6)


# ===========================================================================
# 7. Trend-sign concordance (3-way co-deterioration / co-recovery)
# ===========================================================================

class TestTrendConcordance(unittest.TestCase):
    def test_slope_sign(self):
        self.assertEqual(_slope_sign([1.0, 2.0, 3.0], dt=5.0), 1)
        self.assertEqual(_slope_sign([3.0, 2.0, 1.0], dt=5.0), -1)
        self.assertEqual(_slope_sign([2.0, 2.0, 2.0], dt=5.0), 0)
        self.assertIsNone(_slope_sign([1.0], dt=5.0))

    def test_all_co_declining_concordant(self):
        # 24 points, window 60s @ dt5 => 12 pts/window => 2 windows.
        # All three signals monotonically DOWN => every window concordant.
        n = 24
        aligned: dict[str, list[Any]] = {
            "map": [100.0 - i for i in range(n)],
            "etco2": [50.0 - 0.5 * i for i in range(n)],
            "spo2": [99.0 - 0.1 * i for i in range(n)],
        }
        f = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"],
                                    dt=5.0, window_s=60.0)
        self.assertAlmostEqual(f, 1.0, places=6)

    def test_discordant_signals(self):
        # MAP up, EtCO2 down, SpO2 up => signs disagree => 0 concordance.
        n = 24
        aligned: dict[str, list[Any]] = {
            "map": [50.0 + i for i in range(n)],
            "etco2": [50.0 - i for i in range(n)],
            "spo2": [90.0 + 0.1 * i for i in range(n)],
        }
        f = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"],
                                    dt=5.0, window_s=60.0)
        self.assertAlmostEqual(f, 0.0, places=6)

    def test_flat_breaks_concordance(self):
        # One flat signal (sign 0) => no co-trend to agree on => not concordant.
        n = 24
        aligned: dict[str, list[Any]] = {
            "map": [100.0 - i for i in range(n)],
            "etco2": [50.0 - 0.5 * i for i in range(n)],
            "spo2": [95.0 for _ in range(n)],  # flat
        }
        f = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"],
                                    dt=5.0, window_s=60.0)
        self.assertAlmostEqual(f, 0.0, places=6)

    def test_none_when_window_has_missing(self):
        # A None in every window => no usable window => None.
        n = 24
        aligned: dict[str, list[Any]] = {
            "map": [None if i % 12 == 0 else 100.0 - i for i in range(n)],
            "etco2": [50.0 - 0.5 * i for i in range(n)],
            "spo2": [99.0 - 0.1 * i for i in range(n)],
        }
        f = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"],
                                    dt=5.0, window_s=60.0)
        self.assertIsNone(f)

    def test_none_when_too_short(self):
        aligned: dict[str, list[Any]] = {
            "map": [100.0, 99.0],
            "etco2": [50.0, 49.0],
            "spo2": [99.0, 98.0],
        }
        f = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"],
                                    dt=5.0, window_s=60.0)
        self.assertIsNone(f)


# ===========================================================================
# 8. compute_cascade_features -- case-level integration (pure, no network)
# ===========================================================================

class TestComputeCascadeFeatures(unittest.TestCase):
    def _series(self, value: float, n: int, dt: float = 5.0, t0: float = 0.0):
        return [(t0 + i * dt, value) for i in range(n)]

    def test_unavailable_when_map_absent(self):
        etco2 = self._series(40.0, 60)
        row = compute_cascade_features([], etco2, [], 0.0, 300.0)
        self.assertEqual(row["pcasc_available"], 0)
        for s in SPECS:
            if s.name != "pcasc_available":
                self.assertIsNone(row[s.name])

    def test_unavailable_when_etco2_absent(self):
        m = self._series(80.0, 60)
        row = compute_cascade_features(m, [], [], 0.0, 300.0)
        self.assertEqual(row["pcasc_available"], 0)

    def test_unavailable_when_too_few_joint_points(self):
        # Only ~5 jointly-valid grid points (< MIN_JOINT_POINTS=30).
        m = self._series(80.0, 5, dt=5.0)
        e = self._series(40.0, 5, dt=5.0)
        row = compute_cascade_features(m, e, [], 0.0, 20.0)
        self.assertEqual(row["pcasc_available"], 0)
        self.assertIsNone(row["pcasc_map_etco2_corr"])

    def test_available_and_decouple_high(self):
        # MAP adequate, EtCO2 low throughout, dense enough for >=30 joint pts.
        n = 60
        m = self._series(80.0, n, dt=5.0)
        e = self._series(25.0, n, dt=5.0)   # below ETCO2_LOW everywhere
        row = compute_cascade_features(m, e, [], 0.0, float((n - 1) * 5.0))
        self.assertEqual(row["pcasc_available"], 1)
        self.assertIsNotNone(row["pcasc_downstream_decouple_frac"])
        self.assertGreater(row["pcasc_downstream_decouple_frac"], 0.9,
                           "MAP>=65 + EtCO2<30 => near-total downstream decouple")

    def test_tri_and_coherence_none_without_spo2(self):
        n = 60
        m = self._series(80.0, n, dt=5.0)
        e = self._series(25.0, n, dt=5.0)
        row = compute_cascade_features(m, e, [], 0.0, float((n - 1) * 5.0))
        self.assertEqual(row["pcasc_available"], 1)
        self.assertIsNone(row["pcasc_tri_codrop_frac"],
                          "tri-witness co-drop needs SpO2")
        self.assertIsNone(row["pcasc_perfusion_coherence"],
                          "3-way coherence needs SpO2")

    def test_tri_codrop_high_with_all_three_bad(self):
        n = 60
        m = self._series(80.0, n, dt=5.0)
        e = self._series(25.0, n, dt=5.0)   # low EtCO2
        s = self._series(90.0, n, dt=5.0)   # marginal SpO2
        row = compute_cascade_features(m, e, s, 0.0, float((n - 1) * 5.0))
        self.assertEqual(row["pcasc_available"], 1)
        self.assertIsNotNone(row["pcasc_tri_codrop_frac"])
        self.assertGreater(row["pcasc_tri_codrop_frac"], 0.9,
                           "MAP>=65 + EtCO2<30 + SpO2<95 => near-total tri co-drop")

    def test_corr_positive_when_map_etco2_comove(self):
        # MAP and EtCO2 rise together => positive instantaneous correlation.
        n = 60
        m = [(i * 5.0, 60.0 + 0.5 * i) for i in range(n)]
        e = [(i * 5.0, 20.0 + 0.3 * i) for i in range(n)]
        row = compute_cascade_features(m, e, [], 0.0, float((n - 1) * 5.0))
        self.assertEqual(row["pcasc_available"], 1)
        self.assertIsNotNone(row["pcasc_map_etco2_corr"])
        self.assertGreater(row["pcasc_map_etco2_corr"], 0.9)


# ===========================================================================
# 9. Leakage guard: clipping to opend keeps post-cutoff samples out
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    def test_align_grid_never_exceeds_t_end(self):
        # Even with samples past t_end, the grid stops at t_end.
        sig = {
            "map": [(t * 1.0, 80.0) for t in range(0, 400)],
            "etco2": [(t * 1.0, 25.0) for t in range(0, 400)],
        }
        grid, aligned = _align_grid(sig, 0.0, 100.0, dt=5.0, max_stale=10.0)
        self.assertLessEqual(max(grid), 100.0)

    def test_compute_uses_only_window(self):
        # EtCO2 goes low ONLY after t_end; clipping happens upstream in extract,
        # so here we pass already-clipped series and confirm the post-cutoff
        # samples (not present) cannot inflate the decouple fraction.
        from vitaldb_aki.features.perfusion_cascade import _clip_to_window
        t_end = 300.0
        n_pre = 61
        m = [(i * 5.0, 80.0) for i in range(n_pre)]            # within window
        e_pre = [(i * 5.0, 40.0) for i in range(n_pre)]        # normal in window
        e_post = [(t_end + 5.0 + i * 5.0, 25.0) for i in range(10)]  # low strictly AFTER cutoff
        e_all = e_pre + e_post
        e_clipped = _clip_to_window(e_all, 0.0, t_end)
        row = compute_cascade_features(m, e_clipped, [], 0.0, t_end)
        self.assertEqual(row["pcasc_available"], 1)
        # Post-cutoff low EtCO2 is clipped out => decouple fraction stays 0.
        self.assertAlmostEqual(row["pcasc_downstream_decouple_frac"], 0.0, places=4)


# ===========================================================================
# 10. extract() smoke test (no network; patches the data layer)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    def test_extract_none_row_when_no_map(self):
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.perfusion_cascade import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])
            row = result["1"]
            self.assertEqual(row["pcasc_available"], 0)
            for s in SPECS:
                if s.name != "pcasc_available":
                    self.assertIsNone(row[s.name])

    def test_extract_computes_with_map_and_etco2(self):
        import importlib
        import unittest.mock as mock

        n = 60
        dt = 5.0
        map_track = [(i * dt, 80.0) for i in range(n)]
        etco2_track = [(i * dt, 25.0) for i in range(n)]  # low EtCO2 => decouple

        def _first_available(cfg, cid, tnames, **kw):
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            if any("ETCO2" in tn for tn in tnames):
                return ("Solar8000/ETCO2", etco2_track)
            return (None, [])

        def _download_track(cfg, cid, tname, **kw):
            return []  # no SpO2

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track):
            import vitaldb_aki.features.perfusion_cascade as _mod
            importlib.reload(_mod)
            extract = _mod.extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(n * dt)}}
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["pcasc_available"], 1)
        self.assertIsNotNone(row["pcasc_downstream_decouple_frac"])
        self.assertGreater(row["pcasc_downstream_decouple_frac"], 0.9)
        # SpO2 absent => tri-witness + coherence None.
        self.assertIsNone(row["pcasc_tri_codrop_frac"])
        self.assertIsNone(row["pcasc_perfusion_coherence"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
