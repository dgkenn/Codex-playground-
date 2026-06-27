"""test_cardioresp_coupling.py -- Offline unit tests for the cardio-respiratory
triad module (§7F-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
The PURE helpers (_align_grid, _pearson, _detrend, _trend_concordance,
_windowed_metric, slope-sign concordance) are exercised on synthetic series with
KNOWN expected direction.  Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_cardioresp_coupling -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.cardioresp_coupling import (
    # specs / constants
    SPECS, REQUIRES_RR,
    ALIGN_DT_S, MAX_STALE_S, MIN_JOINT_POINTS,
    CONCORDANCE_WIN_S, CONCORDANCE_STEP_S, MIN_WIN_POINTS,
    HR_MIN, HR_MAX, RR_MIN, RR_MAX, MAP_MIN, MAP_MAX,
    # pure helpers
    _align_grid,
    _joint_valid,
    _pearson,
    _detrend,
    _slope_sign,
    _concordant_signs,
    _trend_concordance,
    _window_index_bounds,
    _windowed_metric,
    # case-level metric helpers
    hr_map_corr,
    hr_rr_corr,
    triple_concordance,
    rsa_coarse,
    rsa_beat_stub,
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

    def test_no_postop(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop", msg=f"{s.name} postop -- leakage!")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "cardioresp_available")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "cardioresp_available",
            "cardioresp_hr_map_corr",
            "cardioresp_hr_rr_corr",
            "cardioresp_triple_concordance",
            "cardioresp_rsa_coarse",
            "cardioresp_rsa_beat",
        }
        self.assertFalse(required - names, f"missing: {required - names}")

    def test_rsa_beat_is_pk_tier(self):
        beat = next(s for s in SPECS if s.name == "cardioresp_rsa_beat")
        self.assertEqual(beat.fset, "pk")

    def test_requires_rr_set(self):
        self.assertEqual(
            REQUIRES_RR,
            {"cardioresp_hr_rr_corr", "cardioresp_triple_concordance",
             "cardioresp_rsa_coarse"},
        )


# ===========================================================================
# 2. _pearson
# ===========================================================================

class TestPearson(unittest.TestCase):
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        self.assertAlmostEqual(_pearson(xs, ys), 1.0, places=6)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        self.assertAlmostEqual(_pearson(xs, ys), -1.0, places=6)

    def test_none_too_few(self):
        self.assertIsNone(_pearson([1.0, 2.0], [1.0, 2.0]))

    def test_none_zero_variance(self):
        self.assertIsNone(_pearson([5.0, 5.0, 5.0, 5.0], [1.0, 2.0, 3.0, 4.0]))

    def test_clamped_to_unit(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.0, 1.0, 2.0, 3.0]
        r = _pearson(xs, ys)
        self.assertLessEqual(r, 1.0)
        self.assertGreaterEqual(r, -1.0)

    def test_uncorrelated_near_zero(self):
        # symmetric V-shape vs line => near-zero correlation
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 1.0, 0.0, 1.0, 2.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 0.0, places=6)


# ===========================================================================
# 3. _detrend
# ===========================================================================

class TestDetrend(unittest.TestCase):
    def test_removes_linear_trend(self):
        series = [1.0, 2.0, 3.0, 4.0, 5.0]  # pure linear
        res = _detrend(series)
        for v in res:
            self.assertAlmostEqual(v, 0.0, places=6)

    def test_short_series_passthrough(self):
        self.assertEqual(_detrend([7.0]), [7.0])
        self.assertEqual(_detrend([]), [])

    def test_residual_mean_zero(self):
        series = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0]
        res = _detrend(series)
        self.assertAlmostEqual(sum(res) / len(res), 0.0, places=6)

    def test_oscillation_preserved(self):
        # linear ramp + oscillation: detrend should leave the oscillation
        osc = [math.sin(i) for i in range(20)]
        ramp = [2.0 * i for i in range(20)]
        series = [ramp[i] + osc[i] for i in range(20)]
        res = _detrend(series)
        # detrended should correlate strongly with the original oscillation
        r = _pearson(res, osc)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.9)


# ===========================================================================
# 4. _slope_sign / _concordant_signs / _trend_concordance
# ===========================================================================

class TestSlopeSign(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(_slope_sign([1.0, 2.0, 3.0]), 1)

    def test_negative(self):
        self.assertEqual(_slope_sign([3.0, 2.0, 1.0]), -1)

    def test_flat(self):
        self.assertEqual(_slope_sign([5.0, 5.0, 5.0]), 0)

    def test_too_short(self):
        self.assertEqual(_slope_sign([1.0]), 0)


class TestConcordantSigns(unittest.TestCase):
    def test_respiratory_mode_hr_tracks_rr(self):
        # HR and RR same sign (mode A); MAP unconstrained
        self.assertTrue(_concordant_signs(1, 1, -1))
        self.assertTrue(_concordant_signs(-1, -1, 1))

    def test_baroreflex_mode_hr_opposes_map(self):
        # HR up, MAP down (mode B); RR disagrees with HR (mode A fails)
        self.assertTrue(_concordant_signs(1, -1, -1))
        self.assertTrue(_concordant_signs(-1, 1, 1))

    def test_discordant_when_neither_mode(self):
        # HR != RR (no mode A) AND HR == MAP (no mode B) => discordant
        self.assertFalse(_concordant_signs(1, -1, 1))

    def test_flat_sign_not_concordant(self):
        self.assertFalse(_concordant_signs(0, 1, 1))
        self.assertFalse(_concordant_signs(1, 0, 1))
        self.assertFalse(_concordant_signs(1, 1, 0))


class TestTrendConcordance(unittest.TestCase):
    def test_all_concordant(self):
        wins = [(1, 1, -1), (-1, -1, 1), (1, -1, -1)]  # all match a mode
        self.assertAlmostEqual(_trend_concordance(wins), 1.0, places=6)

    def test_all_discordant(self):
        wins = [(1, -1, 1), (-1, 1, -1)]  # neither mode
        self.assertAlmostEqual(_trend_concordance(wins), 0.0, places=6)

    def test_half(self):
        wins = [(1, 1, 1), (1, -1, 1)]  # first concordant (mode A), second not
        self.assertAlmostEqual(_trend_concordance(wins), 0.5, places=6)

    def test_flat_windows_excluded(self):
        # second window has a flat sign -> excluded from numerator AND denominator
        wins = [(1, 1, 1), (0, 1, 1)]
        # only the first window is scorable, and it is concordant => 1.0
        self.assertAlmostEqual(_trend_concordance(wins), 1.0, places=6)

    def test_none_when_no_scorable(self):
        wins = [(0, 1, 1), (1, 0, 1)]
        self.assertIsNone(_trend_concordance(wins))

    def test_none_when_empty(self):
        self.assertIsNone(_trend_concordance([]))


# ===========================================================================
# 5. _align_grid (the core multi-signal alignment helper)
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def test_basic_grid_times(self):
        sig = {"A": [(0.0, 1.0), (5.0, 2.0), (10.0, 3.0)]}
        times, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        self.assertEqual(times, [0.0, 5.0, 10.0])
        self.assertEqual(aligned["A"], [1.0, 2.0, 3.0])

    def test_never_exceeds_t_end(self):
        sig = {"A": [(0.0, 1.0), (100.0, 9.0)]}
        times, _ = _align_grid(sig, 0.0, 12.0, dt=5.0, max_stale=1e9)
        self.assertTrue(all(t <= 12.0 + 1e-9 for t in times))
        # grid is 0,5,10 (15 would exceed 12)
        self.assertEqual(times, [0.0, 5.0, 10.0])

    def test_last_value_hold(self):
        # value sampled only at t=0, held forward within max_stale
        sig = {"A": [(0.0, 7.0)]}
        times, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        # t=0 fresh (7.0); t=5 fresh (stale 5<=10); t=10 fresh (stale 10<=10)
        self.assertEqual(aligned["A"], [7.0, 7.0, 7.0])

    def test_staleness_makes_none(self):
        sig = {"A": [(0.0, 7.0)]}
        times, aligned = _align_grid(sig, 0.0, 20.0, dt=5.0, max_stale=10.0)
        # t=0,5,10 fresh; t=15 stale (15>10) -> None; t=20 stale -> None
        self.assertEqual(aligned["A"], [7.0, 7.0, 7.0, None, None])

    def test_before_first_sample_is_none(self):
        sig = {"A": [(20.0, 5.0)]}
        _times, aligned = _align_grid(sig, 0.0, 20.0, dt=5.0, max_stale=10.0)
        # only the last grid point (t=20) sees the sample
        self.assertEqual(aligned["A"], [None, None, None, None, 5.0])

    def test_joint_valid_all_fresh(self):
        sig = {
            "HR": [(0.0, 60.0), (5.0, 62.0), (10.0, 64.0)],
            "MAP": [(0.0, 80.0), (10.0, 78.0)],  # gap from 0..10
        }
        times, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        idxs, vals = _joint_valid(aligned, ["HR", "MAP"])
        # all three grid points jointly fresh (MAP held from 0 within stale at t=5)
        self.assertEqual(idxs, [0, 1, 2])
        self.assertEqual(len(vals["HR"]), 3)
        self.assertEqual(len(vals["MAP"]), 3)

    def test_joint_valid_drops_stale(self):
        sig = {
            "HR": [(i * 5.0, 60.0) for i in range(5)],   # fresh throughout 0..20
            "MAP": [(0.0, 80.0)],                          # only at t=0
        }
        times, aligned = _align_grid(sig, 0.0, 20.0, dt=5.0, max_stale=10.0)
        idxs, _vals = _joint_valid(aligned, ["HR", "MAP"])
        # MAP fresh only at t=0,5,10 (stale beyond) => 3 jointly-valid points
        self.assertEqual(idxs, [0, 1, 2])

    def test_degenerate_window(self):
        sig = {"A": [(0.0, 1.0)]}
        times, aligned = _align_grid(sig, 10.0, 0.0, dt=5.0)  # t_end < t_start
        self.assertEqual(times, [])
        self.assertEqual(aligned["A"], [])

    def test_unsorted_input_handled(self):
        sig = {"A": [(10.0, 3.0), (0.0, 1.0), (5.0, 2.0)]}
        _times, aligned = _align_grid(sig, 0.0, 10.0, dt=5.0, max_stale=10.0)
        self.assertEqual(aligned["A"], [1.0, 2.0, 3.0])


# ===========================================================================
# 6. _window_index_bounds / _windowed_metric
# ===========================================================================

class TestWindowing(unittest.TestCase):
    def test_window_bounds_cover_grid(self):
        grid = [i * 5.0 for i in range(13)]  # 0..60 s at 5 s => 13 points
        bounds = _window_index_bounds(grid, win_s=60.0, step_s=30.0)
        self.assertTrue(bounds)
        # first window covers ~12 points (60s/5s)
        s0, e0 = bounds[0]
        self.assertEqual(s0, 0)
        self.assertEqual(e0, min(12, len(grid)))

    def test_window_bounds_empty(self):
        self.assertEqual(_window_index_bounds([]), [])

    def test_windowed_metric_skips_sparse(self):
        # only 2 jointly valid points per window, min_points=4 => no results
        aligned: dict[str, list[float | None]] = {
            "HR": [60.0, None, None, 62.0],
            "RR": [12.0, None, None, 13.0],
        }
        grid = [0.0, 5.0, 10.0, 15.0]
        res = _windowed_metric(
            aligned, grid, ["HR", "RR"], lambda sub: 1.0,
            win_s=60.0, step_s=30.0, min_points=4,
        )
        self.assertEqual(res, [])

    def test_windowed_metric_collects(self):
        aligned = {
            "HR": [60.0 + i for i in range(12)],
            "RR": [12.0 + 0.1 * i for i in range(12)],
        }
        grid = [i * 5.0 for i in range(12)]
        res = _windowed_metric(
            aligned, grid, ["HR", "RR"], lambda sub: len(sub["HR"]),
            win_s=60.0, step_s=30.0, min_points=4,
        )
        self.assertTrue(res)
        for v in res:
            self.assertGreaterEqual(v, 4)


# ===========================================================================
# 7. Case-level helpers: hr_map_corr / hr_rr_corr (need MIN_JOINT_POINTS)
# ===========================================================================

class TestCaseLevelCorr(unittest.TestCase):
    def _aligned_from(self, hr: list[float], mp: list[float],
                      rr: list[float] | None = None
                      ) -> tuple[dict[str, list[float | None]], list[float]]:
        n = len(hr)
        grid = [i * ALIGN_DT_S for i in range(n)]
        aligned: dict[str, list[float | None]] = {
            "HR": list(hr), "MAP": list(mp),
            "RR": list(rr) if rr is not None else [None] * n,
        }
        return aligned, grid

    def test_hr_map_negative_baroreflex(self):
        # HR rises as MAP falls -> negative corr (intact baroreflex)
        n = 40
        hr = [60.0 + i for i in range(n)]
        mp = [100.0 - i for i in range(n)]
        aligned, _g = self._aligned_from(hr, mp)
        r = hr_map_corr(aligned)
        self.assertIsNotNone(r)
        self.assertLess(r, 0.0)

    def test_hr_map_none_when_too_few(self):
        n = 10  # < MIN_JOINT_POINTS (30)
        hr = [60.0 + i for i in range(n)]
        mp = [100.0 - i for i in range(n)]
        aligned, _g = self._aligned_from(hr, mp)
        self.assertIsNone(hr_map_corr(aligned))

    def test_hr_rr_none_when_rr_absent(self):
        n = 40
        hr = [60.0 + i for i in range(n)]
        mp = [80.0] * n
        aligned, _g = self._aligned_from(hr, mp, rr=None)  # RR all None
        self.assertIsNone(hr_rr_corr(aligned))

    def test_hr_rr_positive_when_coupled(self):
        n = 40
        hr = [60.0 + math.sin(i / 2.0) for i in range(n)]
        rr = [12.0 + math.sin(i / 2.0) for i in range(n)]
        mp = [80.0] * n
        aligned, _g = self._aligned_from(hr, mp, rr=rr)
        r = hr_rr_corr(aligned)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.5)


# ===========================================================================
# 8. triple_concordance / rsa_coarse (3-way; need HR, RR, MAP)
# ===========================================================================

class TestTripleConcordance(unittest.TestCase):
    def _grid(self, n: int) -> list[float]:
        return [i * ALIGN_DT_S for i in range(n)]

    def test_high_when_coordinated(self):
        # HR tracks RR everywhere (mode A) -> high concordance
        n = 60
        hr = [60.0 + i for i in range(n)]
        rr = [12.0 + 0.1 * i for i in range(n)]
        mp = [90.0 - 0.2 * i for i in range(n)]
        aligned: dict[str, list[float | None]] = {"HR": hr, "RR": rr, "MAP": mp}
        grid = self._grid(n)
        c = triple_concordance(aligned, grid)
        self.assertIsNotNone(c)
        self.assertGreater(c, 0.9)

    def test_none_when_rr_absent(self):
        n = 60
        hr = [60.0 + i for i in range(n)]
        mp = [90.0 - 0.2 * i for i in range(n)]
        aligned: dict[str, list[float | None]] = {
            "HR": hr, "RR": [None] * n, "MAP": mp,
        }
        grid = self._grid(n)
        self.assertIsNone(triple_concordance(aligned, grid))

    def test_low_when_desynchronized(self):
        # Construct windows where HR != RR (no mode A) and HR == MAP (no mode B).
        # Use a sawtooth so per-window slopes flip into discordant patterns.
        n = 60
        hr = [60.0 + i for i in range(n)]          # rising
        rr = [40.0 - 0.5 * i for i in range(n)]    # falling (HR != RR)
        mp = [40.0 + i for i in range(n)]          # rising (HR == MAP) -> discordant
        aligned: dict[str, list[float | None]] = {"HR": hr, "RR": rr, "MAP": mp}
        grid = self._grid(n)
        c = triple_concordance(aligned, grid)
        self.assertIsNotNone(c)
        self.assertLess(c, 0.1)


class TestRsaCoarse(unittest.TestCase):
    def _grid(self, n: int) -> list[float]:
        return [i * ALIGN_DT_S for i in range(n)]

    def test_high_when_hr_co_oscillates_with_rr(self):
        n = 60
        # shared oscillation on top of independent linear drifts
        hr = [60.0 + 0.5 * i + 3.0 * math.sin(i / 2.0) for i in range(n)]
        rr = [12.0 - 0.2 * i + 2.0 * math.sin(i / 2.0) for i in range(n)]
        mp = [80.0] * n
        aligned: dict[str, list[float | None]] = {"HR": hr, "RR": rr, "MAP": mp}
        val = rsa_coarse(aligned, self._grid(n))
        self.assertIsNotNone(val)
        self.assertGreater(val, 0.7)
        self.assertLessEqual(val, 1.0)

    def test_low_when_hr_rr_independent(self):
        n = 60
        hr = [60.0 + 3.0 * math.sin(i / 2.0) for i in range(n)]
        # RR: deterministic pseudo-random jitter, independent of HR's oscillation.
        rr = [12.0 + 2.0 * (((i * 1103515245 + 12345) % 1000) / 500.0 - 1.0)
              for i in range(n)]
        mp = [80.0] * n
        aligned: dict[str, list[float | None]] = {"HR": hr, "RR": rr, "MAP": mp}
        val = rsa_coarse(aligned, self._grid(n))
        self.assertIsNotNone(val)
        self.assertLess(val, 0.7)

    def test_none_when_rr_absent(self):
        n = 60
        hr = [60.0 + i for i in range(n)]
        mp = [80.0] * n
        aligned: dict[str, list[float | None]] = {
            "HR": hr, "RR": [None] * n, "MAP": mp,
        }
        self.assertIsNone(rsa_coarse(aligned, self._grid(n)))


# ===========================================================================
# 9. Deferred beat-to-beat RSA stub (never downloads on default path)
# ===========================================================================

class TestRsaBeatStub(unittest.TestCase):
    def test_none_by_default(self):
        cfg: dict[str, Any] = {"data": {"cache_dir": "/tmp"}}
        self.assertIsNone(rsa_beat_stub(cfg, "1", 0.0, 3600.0))

    def test_none_even_when_enabled(self):
        # Flag on -> still None (documented placeholder), and importantly no I/O.
        cfg = {"data": {"cache_dir": "/tmp"}, "features": {"cardioresp_raw_ecg": True}}
        self.assertIsNone(rsa_beat_stub(cfg, "1", 0.0, 3600.0))


# ===========================================================================
# 10. extract() smoke tests (no network; helpers patched at source module)
# ===========================================================================

class TestExtractSmoke(unittest.TestCase):
    def test_none_row_when_no_map(self):
        import unittest.mock as mock
        # first_available returns HR but no MAP; download_track empty.
        hr_track = [(i * 5.0, 60.0 + (i % 5)) for i in range(50)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("HR" in tn for tn in tnames):
                return ("Solar8000/HR", hr_track)
            return (None, [])  # no MAP, no RR

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.cardioresp_coupling import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])

        row = result["1"]
        self.assertEqual(row["cardioresp_available"], 0)
        for s in SPECS:
            if s.name != "cardioresp_available":
                self.assertIsNone(row[s.name], f"{s.name} must be None when MAP absent")

    def test_hr_map_only_rr_features_none(self):
        """HR & MAP present, RR absent: available=1, hr_map_corr set, RR-features None."""
        import unittest.mock as mock
        n = 200
        hr_track = [(i * 5.0, 70.0 + 0.05 * i) for i in range(n)]   # slow rise
        map_track = [(i * 5.0, 90.0 - 0.05 * i) for i in range(n)]  # slow fall

        def _first_available(cfg, cid, tnames, **kw):
            if any("/HR" in tn or "PLETH_HR" in tn for tn in tnames):
                return ("Solar8000/HR", hr_track)
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])  # no RR

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.cardioresp_coupling import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"7": {"caseid": "7", "anestart": 0.0, "opend": float(n * 5.0)}}
            result = extract(cfg, cases, ["7"])

        row = result["7"]
        self.assertEqual(row["cardioresp_available"], 1)
        self.assertIsNotNone(row["cardioresp_hr_map_corr"])
        self.assertLess(row["cardioresp_hr_map_corr"], 0.0)  # HR up, MAP down
        # RR-dependent features must be None
        for name in REQUIRES_RR:
            self.assertIsNone(row[name], f"{name} must be None when RR absent")
        # beat RSA deferred -> None
        self.assertIsNone(row["cardioresp_rsa_beat"])

    def test_full_triad_features_populated(self):
        """HR, MAP and RR all present: 3-way features become non-None."""
        import unittest.mock as mock
        n = 200
        hr_track = [(i * 5.0, 70.0 + 3.0 * math.sin(i / 3.0)) for i in range(n)]
        rr_track = [(i * 5.0, 14.0 + 2.0 * math.sin(i / 3.0)) for i in range(n)]
        map_track = [(i * 5.0, 90.0 - 3.0 * math.sin(i / 3.0)) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("VENT_RR" in tn or "RR_CO2" in tn for tn in tnames):
                return ("Solar8000/VENT_RR", rr_track)
            if any("/HR" in tn or "PLETH_HR" in tn for tn in tnames):
                return ("Solar8000/HR", hr_track)
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.cardioresp_coupling import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"9": {"caseid": "9", "anestart": 0.0, "opend": float(n * 5.0)}}
            result = extract(cfg, cases, ["9"])

        row = result["9"]
        self.assertEqual(row["cardioresp_available"], 1)
        self.assertIsNotNone(row["cardioresp_hr_map_corr"])
        self.assertIsNotNone(row["cardioresp_hr_rr_corr"])
        self.assertIsNotNone(row["cardioresp_triple_concordance"])
        self.assertIsNotNone(row["cardioresp_rsa_coarse"])
        # HR and RR co-oscillate => coarse RSA should be high
        self.assertGreater(row["cardioresp_rsa_coarse"], 0.5)

    def test_leakage_no_sample_past_opend(self):
        """Samples after opend must not enter the alignment grid."""
        import unittest.mock as mock
        n = 200
        opend = 500.0  # only first 100 samples (0..500 @5s) are intraop
        # MAP is high+stable intraop, then crashes AFTER opend -> must be ignored
        hr_track = [(i * 5.0, 70.0) for i in range(n)]
        map_track = [(i * 5.0, 90.0 if i * 5.0 <= opend else 30.0) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("/HR" in tn or "PLETH_HR" in tn for tn in tnames):
                return ("Solar8000/HR", hr_track)
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.cardioresp_coupling import (
                extract, _intraop_window, _clip_to_window,
            )
            cfg = {"data": {"cache_dir": "/tmp"}}
            case = {"caseid": "5", "anestart": 0.0, "opend": opend}
            # Direct check on the clipper: no clipped sample exceeds opend.
            t_start, t_end = _intraop_window(case)
            clipped = _clip_to_window(map_track, t_start, t_end)
            self.assertTrue(all(t <= opend for t, _v in clipped))
            self.assertTrue(all(v == 90.0 for _t, v in clipped))  # no post-opend crash

            result = extract(cfg, {"5": case}, ["5"])
        # MAP intraop is constant 90 -> zero variance -> hr_map_corr None,
        # but availability is still 1 (HR & MAP jointly present >= MIN points).
        row = result["5"]
        self.assertEqual(row["cardioresp_available"], 1)
        self.assertIsNone(row["cardioresp_hr_map_corr"])  # constant MAP => no corr


if __name__ == "__main__":
    unittest.main(verbosity=2)
