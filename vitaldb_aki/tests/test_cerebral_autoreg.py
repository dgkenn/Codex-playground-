"""test_cerebral_autoreg.py -- Offline unit tests for cerebral-autoregulation (§7F-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads,
stdlib only (no numpy/scipy). Each PURE helper is exercised on hand-built
synthetic series with a KNOWN expected direction:

  * _align_grid          -- last-value-hold; jointly-valid = all signals fresh
  * _pearson             -- correlation sign / magnitude / undefined cases
  * _partial_corr        -- deconfounding (drug-driven coupling removed)
  * _windowed_corr_mean  -- Mx/COx index + impaired fraction over 5-min windows

Plus spec invariants, empty/missing -> None behaviour, leakage (no t>opend),
and a network-free extract() smoke test.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_cerebral_autoreg -v
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.cerebral_autoreg import (
    # Module-level constants
    SPECS,
    ALIGN_DT_S, MAX_STALE_S, MIN_JOINT_POINTS,
    COX_WINDOW_S, COX_MIN_WINDOWS, IMPAIRED_CORR_THR,
    MAP_TRACK_CANDIDATES, SEF_TRACK, BIS_TRACK, PPF_CE_PUMP_TRACK,
    # Pure helpers
    _align_grid,
    _joint_valid,
    _pearson,
    _partial_corr,
    _windowed_corr_mean,
    _intraop_window,
    _clip_to_window,
    _filter_physiologic,
    # Case-level pure compute
    compute_cerebral_autoreg,
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
        """Every cerebral-autoreg feature requires the BIS monitor -> pk tier."""
        for s in SPECS:
            self.assertEqual(s.fset, "pk", msg=f"{s.name} fset={s.fset!r} (expected pk)")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)), "Duplicate feature names")

    def test_first_spec_is_available(self):
        self.assertEqual(SPECS[0].name, "cautoreg_available")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "cautoreg_available",
            "cautoreg_eeg_map_corr",
            "cautoreg_eeg_map_partial_ce",
            "cautoreg_cox_index",
            "cautoreg_impaired_frac",
        }
        self.assertFalse(required - names, f"Missing specs: {required - names}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 5, "Expected exactly 5 feature specs")


# ===========================================================================
# 2. _pearson
# ===========================================================================

class TestPearson(unittest.TestCase):
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, -1.0, places=6)

    def test_zero_for_independent(self):
        # Symmetric V-shape vs ramp => near-zero linear correlation.
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 1.0, 0.0, 1.0, 2.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 0.0, places=6)

    def test_none_when_too_few_points(self):
        self.assertIsNone(_pearson([1.0, 2.0], [1.0, 2.0]))

    def test_none_when_length_mismatch(self):
        self.assertIsNone(_pearson([1.0, 2.0, 3.0], [1.0, 2.0]))

    def test_none_when_constant(self):
        self.assertIsNone(_pearson([5.0, 5.0, 5.0, 5.0], [1.0, 2.0, 3.0, 4.0]))

    def test_clamped_to_unit_range(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.0, 1.0, 2.0, 3.0]
        r = _pearson(xs, ys)
        self.assertIsNotNone(r)
        self.assertLessEqual(r, 1.0)
        self.assertGreaterEqual(r, -1.0)


# ===========================================================================
# 3. _partial_corr -- the deconfounding core
# ===========================================================================

class TestPartialCorr(unittest.TestCase):
    def test_removes_common_driver(self):
        """EEG and MAP both driven by Ce (plus independent noise) => raw corr high,
        but the MAP-EEG partial corr collapses toward 0 once Ce is removed.

        c (Ce) is a ramp; e and m are each c plus their OWN independent wobble
        (so neither is perfectly collinear with c -- the partial corr is defined).
        Because their only shared driver is c, conditioning on c removes most of
        the raw association.
        """
        n = 30
        c = [float(i) for i in range(n)]
        # Independent zero-mean wobbles, uncorrelated with each other and with c.
        e_noise = [(-1.0) ** i for i in range(n)]          # +/-1 alternating
        m_noise = [1.0 if (i // 2) % 2 == 0 else -1.0 for i in range(n)]
        e = [100.0 - 2.0 * c[i] + 1.5 * e_noise[i] for i in range(n)]
        m = [90.0 - 1.0 * c[i] + 1.5 * m_noise[i] for i in range(n)]
        raw = _pearson(e, m)
        partial = _partial_corr(e, m, c)
        self.assertIsNotNone(raw)
        self.assertIsNotNone(partial)
        self.assertGreater(abs(raw), 0.9, "raw corr should be high via shared Ce")
        self.assertLess(abs(partial), 0.4,
                        "conditioning on the common driver collapses the coupling")

    def test_keeps_genuine_coupling(self):
        """EEG tracks MAP for a reason INDEPENDENT of Ce => partial corr stays high.

        Ce is independent noise-free constant-ish driver; the EEG-MAP coupling is
        injected directly (e = m + small) so it survives conditioning on Ce.
        """
        n = 30
        # MAP wanders; EEG tracks it tightly; Ce is an unrelated slow ramp.
        m = [70.0 + 10.0 * ((i % 7) - 3) for i in range(n)]
        e = [val * 0.3 for val in m]          # EEG tracks MAP directly
        c = [0.5 + 0.01 * i for i in range(n)]  # unrelated drug ramp
        partial = _partial_corr(e, m, c)
        self.assertIsNotNone(partial)
        self.assertGreater(partial, 0.8,
                           "genuine pressure-passive coupling survives Ce control")

    def test_none_when_too_few(self):
        self.assertIsNone(_partial_corr([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]))

    def test_none_when_length_mismatch(self):
        self.assertIsNone(_partial_corr([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0]))

    def test_none_when_control_constant(self):
        """Constant Ce => r_ec / r_mc undefined => partial corr None."""
        n = 10
        e = [float(i) for i in range(n)]
        m = [float(i) * 2 for i in range(n)]
        c = [3.0] * n
        self.assertIsNone(_partial_corr(e, m, c))


# ===========================================================================
# 4. _align_grid -- last-value-hold + joint validity
# ===========================================================================

class TestAlignGrid(unittest.TestCase):
    def test_empty_when_window_degenerate(self):
        grid, cols = _align_grid({"a": [(0.0, 1.0)]}, t_start=10.0, t_end=10.0)
        self.assertEqual(grid, [])
        self.assertEqual(cols, {"a": []})

    def test_grid_spacing_and_bounds(self):
        sig = {"a": [(t, float(t)) for t in range(0, 101, 5)]}
        grid, cols = _align_grid(sig, t_start=0.0, t_end=100.0, dt=10.0, max_stale=15.0)
        # Grid: 0,10,...,100 => 11 points
        self.assertEqual(len(grid), 11)
        self.assertAlmostEqual(grid[0], 0.0)
        self.assertAlmostEqual(grid[-1], 100.0)
        self.assertTrue(all(grid[i + 1] - grid[i] == 10.0 for i in range(len(grid) - 1)))

    def test_last_value_hold(self):
        # One sample at t=0; grid step 10. With max_stale=15, holds at t=10 only.
        sig = {"a": [(0.0, 42.0)]}
        grid, cols = _align_grid(sig, 0.0, 30.0, dt=10.0, max_stale=15.0)
        col = cols["a"]
        self.assertEqual(col[0], 42.0)   # t=0
        self.assertEqual(col[1], 42.0)   # t=10, age 10 <= 15 -> held
        self.assertIsNone(col[2])        # t=20, age 20 > 15 -> stale
        self.assertIsNone(col[3])        # t=30, stale

    def test_no_value_before_first_sample(self):
        sig = {"a": [(50.0, 7.0)]}
        grid, cols = _align_grid(sig, 0.0, 50.0, dt=10.0, max_stale=15.0)
        col = cols["a"]
        # Before t=50 nothing held; at t=50 the sample lands.
        self.assertIsNone(col[0])
        self.assertIsNone(col[3])  # t=30
        self.assertEqual(col[-1], 7.0)  # t=50

    def test_missing_signal_all_none(self):
        sig = {"present": [(t, 1.0) for t in range(0, 31, 10)], "absent": []}
        grid, cols = _align_grid(sig, 0.0, 30.0, dt=10.0, max_stale=15.0)
        self.assertTrue(all(v is None for v in cols["absent"]))
        self.assertTrue(all(v is not None for v in cols["present"]))

    def test_joint_valid_requires_all_fresh(self):
        # MAP dense everywhere; EEG only fresh for the first half.
        map_s = [(float(t), 70.0) for t in range(0, 101, 5)]
        eeg_s = [(float(t), 12.0) for t in range(0, 51, 5)]  # stops at t=50
        grid, cols = _align_grid({"map": map_s, "eeg": eeg_s},
                                 0.0, 100.0, dt=10.0, max_stale=15.0)
        kept_t, kept = _joint_valid(grid, cols, ["map", "eeg"])
        # EEG goes stale shortly after t=50 -> joint points only in early window.
        self.assertGreater(len(kept_t), 0)
        self.assertTrue(all(t <= 65.0 for t in kept_t),
                        "joint-valid points should not extend past EEG freshness")
        self.assertEqual(len(kept["map"]), len(kept["eeg"]))


# ===========================================================================
# 5. _windowed_corr_mean -- Mx/COx index + impaired fraction
# ===========================================================================

class TestWindowedCorrMean(unittest.TestCase):
    def _grid(self, n: int, dt: float = 10.0) -> list[float]:
        return [i * dt for i in range(n)]

    def test_none_when_single_window(self):
        # 300 s window; only ~30 points spanning <2 windows.
        n = 20
        times = self._grid(n, dt=10.0)  # spans 0..190 s -> 1 window
        eeg = [float(i) for i in range(n)]
        mp = [float(i) for i in range(n)]
        cox, frac = _windowed_corr_mean(times, eeg, mp, win_s=300.0)
        self.assertIsNone(cox)
        self.assertIsNone(frac)

    def test_high_index_when_eeg_tracks_map_everywhere(self):
        """EEG == MAP in every window => per-window corr ~ +1 => cox_index ~ +1, frac=1."""
        # 3 windows of 300 s, points every 10 s.
        n = 90
        times = self._grid(n, dt=10.0)  # 0..890 s -> windows 0,1,2
        # MAP wanders within each window; EEG tracks it exactly.
        mp = [70.0 + 10.0 * ((i % 5) - 2) for i in range(n)]
        eeg = [v * 0.3 for v in mp]
        cox, frac = _windowed_corr_mean(times, eeg, mp, win_s=300.0)
        self.assertIsNotNone(cox)
        self.assertIsNotNone(frac)
        self.assertGreater(cox, 0.9, "sustained MAP-EEG coupling => high COx index")
        self.assertAlmostEqual(frac, 1.0, places=6,
                               msg="every window impaired => frac == 1.0")

    def test_low_index_when_decoupled(self):
        """EEG independent of MAP per window => corr ~ 0 => cox_index ~ 0, frac=0."""
        n = 90
        times = self._grid(n, dt=10.0)
        mp = [70.0 + 10.0 * ((i % 5) - 2) for i in range(n)]
        # EEG: a different within-window pattern uncorrelated with MAP's pattern.
        eeg = [12.0 + 3.0 * ((i % 3) - 1) for i in range(n)]
        cox, frac = _windowed_corr_mean(times, eeg, mp, win_s=300.0)
        self.assertIsNotNone(cox)
        self.assertIsNotNone(frac)
        self.assertLess(abs(cox), 0.5, "decoupled => COx index near 0")
        self.assertLess(frac, 0.5, "few/no impaired windows")

    def test_impaired_frac_partial(self):
        """Some windows coupled (+1), some decoupled => frac strictly between 0 and 1."""
        n = 90
        times = self._grid(n, dt=10.0)
        mp = [70.0 + 10.0 * ((i % 5) - 2) for i in range(n)]
        eeg: list[float] = []
        for i in range(n):
            w = i // 30  # window index 0,1,2
            if w == 0:
                eeg.append(mp[i] * 0.3)              # coupled (impaired)
            else:
                eeg.append(12.0 + 3.0 * ((i % 3) - 1))  # decoupled
        cox, frac = _windowed_corr_mean(times, eeg, mp, win_s=300.0)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.0)
        self.assertLess(frac, 1.0)

    def test_empty_inputs(self):
        cox, frac = _windowed_corr_mean([], [], [])
        self.assertIsNone(cox)
        self.assertIsNone(frac)


# ===========================================================================
# 6. compute_cerebral_autoreg -- case-level assembly (pure)
# ===========================================================================

class TestComputeCase(unittest.TestCase):
    def _series(self, vals: list[float], dt: float = 10.0) -> list[tuple[float, float]]:
        return [(i * dt, v) for i, v in enumerate(vals)]

    def test_unavailable_when_eeg_missing(self):
        """No EEG => available=0, all others None."""
        n = 60
        mp = self._series([70.0 + (i % 5) for i in range(n)])
        row = compute_cerebral_autoreg(mp, [], [], t_start=0.0, t_end=600.0)
        self.assertEqual(row["cautoreg_available"], 0)
        for s in SPECS:
            if s.name != "cautoreg_available":
                self.assertIsNone(row[s.name], f"{s.name} should be None when no EEG")

    def test_unavailable_when_too_few_joint_points(self):
        """Fewer than MIN_JOINT_POINTS aligned MAP+EEG points => available=0."""
        # Only ~5 points -> below the 30-point gate.
        mp = self._series([70.0, 72.0, 68.0, 74.0, 71.0])
        eeg = self._series([12.0, 13.0, 11.0, 14.0, 12.5])
        row = compute_cerebral_autoreg(mp, eeg, [], t_start=0.0, t_end=40.0)
        self.assertEqual(row["cautoreg_available"], 0)
        self.assertIsNone(row["cautoreg_eeg_map_corr"])

    def test_available_and_partial_none_without_ce(self):
        """MAP+EEG present, no Ce => available=1, raw corr computed, partial=None."""
        n = 60
        mp = self._series([70.0 + 10.0 * ((i % 5) - 2) for i in range(n)])
        eeg = self._series([v * 0.3 for (_, v) in mp])
        row = compute_cerebral_autoreg(mp, eeg, [], t_start=0.0, t_end=600.0)
        self.assertEqual(row["cautoreg_available"], 1)
        self.assertIsNotNone(row["cautoreg_eeg_map_corr"])
        self.assertIsNone(row["cautoreg_eeg_map_partial_ce"],
                          "partial-Ce must be None when Ce track absent")

    def test_partial_computed_with_ce(self):
        """With a Ce track present, the partial-Ce feature is computed (non-None)."""
        n = 60
        mp = self._series([70.0 + 10.0 * ((i % 5) - 2) for i in range(n)])
        eeg = self._series([v * 0.3 for (_, v) in mp])
        ce = self._series([1.0 + 0.01 * i for i in range(n)])
        row = compute_cerebral_autoreg(mp, eeg, ce, t_start=0.0, t_end=600.0)
        self.assertEqual(row["cautoreg_available"], 1)
        self.assertIsNotNone(row["cautoreg_eeg_map_partial_ce"])

    def test_degenerate_window(self):
        row = compute_cerebral_autoreg(
            self._series([70.0] * 60), self._series([12.0] * 60), [],
            t_start=10.0, t_end=10.0,
        )
        self.assertEqual(row["cautoreg_available"], 0)


# ===========================================================================
# 7. Window / clip helpers + leakage (no t > opend)
# ===========================================================================

class TestWindowHelpers(unittest.TestCase):
    def test_intraop_window_prefers_anestart(self):
        case = {"opend": 3600.0, "anestart": 100.0, "opstart": 200.0}
        self.assertEqual(_intraop_window(case), (100.0, 3600.0))

    def test_intraop_window_falls_back_to_opstart(self):
        case = {"opend": 3600.0, "opstart": 200.0}
        self.assertEqual(_intraop_window(case), (200.0, 3600.0))

    def test_intraop_window_none_without_opend(self):
        self.assertEqual(_intraop_window({"anestart": 0.0}), (None, None))

    def test_clip_excludes_post_opend(self):
        opend = 100.0
        samples = [(t, float(t)) for t in range(0, 161, 10)]
        clipped = _clip_to_window(samples, 0.0, opend)
        self.assertTrue(all(t <= opend for t, _ in clipped),
                        "no sample beyond opend (leakage cutoff)")
        self.assertNotIn((110.0, 110.0), clipped)

    def test_filter_physiologic(self):
        samples = [(0.0, 5.0), (1.0, 70.0), (2.0, 250.0)]
        out = _filter_physiologic(samples, 20.0, 200.0)
        self.assertEqual(out, [(1.0, 70.0)])


class TestNoLeakage(unittest.TestCase):
    """Samples beyond opend must never influence the coupling features."""

    def test_post_opend_eeg_excluded(self):
        opend = 600.0
        # MAP & EEG strongly coupled ONLY after opend; flat (uncoupled) before.
        n_pre = 70
        pre_t = [i * 10.0 for i in range(n_pre)]          # 0..690 -> trimmed at 600
        map_pre = [(t, 70.0 + 0.001 * (t % 3)) for t in pre_t]   # ~flat
        eeg_pre = [(t, 12.0) for t in pre_t]                      # flat
        # Post-opend strong coupling (must be excluded by the clip).
        map_post = [(opend + i * 10.0, 50.0 + i) for i in range(30)]
        eeg_post = [(opend + i * 10.0, 5.0 + i) for i in range(30)]

        map_all = map_pre + map_post
        eeg_all = eeg_pre + eeg_post

        map_clip = _clip_to_window(map_all, 0.0, opend)
        eeg_clip = _clip_to_window(eeg_all, 0.0, opend)
        row = compute_cerebral_autoreg(map_clip, eeg_clip, [], t_start=0.0, t_end=opend)
        # All retained samples are pre-opend & flat -> no spurious coupling.
        # Either available with ~undefined/near-zero corr, but crucially NOT the
        # strong post-opend coupling. We assert no sample leaked past opend.
        for t, _ in map_clip:
            self.assertLessEqual(t, opend)
        for t, _ in eeg_clip:
            self.assertLessEqual(t, opend)


# ===========================================================================
# 8. extract() smoke test (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """extract() lazy-imports first_available/download_track from
    vitaldb_aki.data.tracks, so we patch at the source module."""

    def test_none_row_when_no_map(self):
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track", return_value=[]):
            from vitaldb_aki.features.cerebral_autoreg import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])
            row = result["1"]
            self.assertEqual(row["cautoreg_available"], 0)
            for s in SPECS:
                if s.name != "cautoreg_available":
                    self.assertIsNone(row[s.name])

    def test_computes_with_map_and_sef(self):
        """MAP + SEF (no Ce) => available=1, raw corr set, partial-Ce None."""
        import unittest.mock as mock

        n = 80
        dt = 10.0
        opend = n * dt
        map_track = [(i * dt, 70.0 + 10.0 * ((i % 5) - 2)) for i in range(n)]
        sef_track = [(i * dt, max(0.0, (70.0 + 10.0 * ((i % 5) - 2)) * 0.3)) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        def _download_track(cfg, cid, tname, **kw):
            if tname == SEF_TRACK:
                return sef_track
            return []  # no BIS index, no Ce

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track):
            from vitaldb_aki.features.cerebral_autoreg import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(opend)}}
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["cautoreg_available"], 1)
        self.assertIsNotNone(row["cautoreg_eeg_map_corr"])
        self.assertIsNone(row["cautoreg_eeg_map_partial_ce"],
                          "no Ce track => partial-Ce None")

    def test_uses_bis_fallback_when_no_sef(self):
        """No SEF, but BIS index present => still available=1."""
        import unittest.mock as mock

        n = 80
        dt = 10.0
        opend = n * dt
        map_track = [(i * dt, 70.0 + 10.0 * ((i % 5) - 2)) for i in range(n)]
        bis_track = [(i * dt, 40.0 + 5.0 * ((i % 5) - 2)) for i in range(n)]

        def _first_available(cfg, cid, tnames, **kw):
            if any("MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            return (None, [])

        def _download_track(cfg, cid, tname, **kw):
            if tname == BIS_TRACK:
                return bis_track
            return []  # no SEF, no Ce

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track):
            from vitaldb_aki.features.cerebral_autoreg import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"7": {"caseid": "7", "anestart": 0.0, "opend": float(opend)}}
            result = extract(cfg, cases, ["7"])

        row = result["7"]
        self.assertEqual(row["cautoreg_available"], 1,
                         "BIS index fallback should make the case usable")

    def test_missing_case_yields_none_row(self):
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track", return_value=[]):
            from vitaldb_aki.features.cerebral_autoreg import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            result = extract(cfg, {}, ["nope"])
            self.assertEqual(result["nope"]["cautoreg_available"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
