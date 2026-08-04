"""test_temporal.py -- Unit tests for the intraop TEMPORAL-structure module (§7C/§7D).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Synthetic MAP / propofol-Ce series with hand-computed expectations exercise:
  * phase-thirds attribution (a known LATE hypotensive run lands in the LATE bucket),
  * nadir-time fraction, longest continuous run, MAP slope sign,
  * resample-to-grid (last-value hold + gap -> None),
  * the MAP x propofol-Ce coupling minutes under controlled overlap,
  * post-opend leakage exclusion (a sub-65 sample after opend must not count).

Run with:
    python3 -m unittest vitaldb_aki.tests.test_temporal -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.temporal import (
    MAP_MIN, MAP_MAX, MAP_HYPO_THRESHOLD, MAX_INTER_SAMPLE_DT_S,
    COUPLING_GRID_STEP_S, USES_TRACKS,
    SPECS,
    _intraop_window,
    _clip_to_window,
    _filter_physiologic,
    _effective_window,
    phase_thirds,
    _phase_thirds_for_window,
    hypotension_minutes_and_auc,
    time_to_first_below_frac,
    nadir_time_frac,
    longest_run_below,
    map_slope_per_hr,
    mean_value,
    resample_to_grid,
    minutes_below_during_high_signal,
    temporal_pearson_corr,
    _compute_row,
)
from vitaldb_aki.features.base import audit_specs, names_for_set


# ---------------------------------------------------------------------------
# 1.  Module-level spec invariants
# ---------------------------------------------------------------------------

class TestSpecs(unittest.TestCase):
    def test_audit_passes(self):
        audit_specs(SPECS)  # must not raise (no postop timing)

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_uses_tracks_flag(self):
        self.assertTrue(USES_TRACKS)

    def test_all_expected_names_present(self):
        names = {s.name for s in SPECS}
        required = {
            "map_below65_min_early", "map_below65_min_mid", "map_below65_min_late",
            "map_auc65_early", "map_auc65_mid", "map_auc65_late",
            "map_time_to_first_below65_frac", "map_nadir_time_frac",
            "map_longest_hypotension_run_min", "map_slope_per_hr",
            "map_early_vs_late_mean_delta",
            "map_below65_during_high_ppfce_min", "ppfce_map_temporal_corr",
            "temporal_available",
        }
        self.assertEqual(names, required)

    def test_set_membership(self):
        d = {s.name: s.fset for s in SPECS}
        # hemodynamic-only -> comprehensive
        self.assertEqual(d["map_below65_min_late"], "comprehensive")
        self.assertEqual(d["map_nadir_time_frac"], "comprehensive")
        self.assertEqual(d["temporal_available"], "comprehensive")
        # propofol-Ce dependent -> pk
        self.assertEqual(d["map_below65_during_high_ppfce_min"], "pk")
        self.assertEqual(d["ppfce_map_temporal_corr"], "pk")

    def test_pk_features_excluded_from_comprehensive_set(self):
        comp = set(names_for_set(SPECS, "comprehensive"))
        self.assertNotIn("ppfce_map_temporal_corr", comp)
        self.assertNotIn("map_below65_during_high_ppfce_min", comp)
        # but present in the +pk nested set
        pk = set(names_for_set(SPECS, "pk"))
        self.assertIn("ppfce_map_temporal_corr", pk)
        self.assertIn("map_below65_during_high_ppfce_min", pk)


# ---------------------------------------------------------------------------
# 2.  Phase thirds attribution
# ---------------------------------------------------------------------------

class TestPhaseThirds(unittest.TestCase):
    def test_basic_split(self):
        # window [0, 900]; thirds boundaries at 300 and 600
        samples = [(float(t), 80.0) for t in range(0, 901, 30)]
        early, mid, late = phase_thirds(samples, (0.0, 900.0))
        self.assertTrue(all(t < 300 for t, _ in early))
        self.assertTrue(all(300 <= t < 600 for t, _ in mid))
        self.assertTrue(all(t >= 600 for t, _ in late))

    def test_out_of_window_ignored(self):
        samples = [(-50.0, 80.0), (450.0, 80.0), (2000.0, 80.0)]
        early, mid, late = phase_thirds(samples, (0.0, 900.0))
        all_t = [t for t, _ in early + mid + late]
        self.assertEqual(all_t, [450.0])

    def test_late_hypotension_lands_in_late_bucket(self):
        # 900 s window. MAP=85 everywhere EXCEPT a hypotensive run (MAP=50)
        # placed in the LATE third [600,900]. The cumulative summary would only
        # report "some minutes below 65"; phase-thirds must localise it to LATE.
        samples = []
        for t in range(0, 901, 10):
            v = 50.0 if 660 <= t <= 720 else 85.0   # 60 s of MAP=50 in late third
            samples.append((float(t), v))
        win = (0.0, 900.0)
        early, mid, late = _phase_thirds_for_window(samples, win)
        e_min, _ = hypotension_minutes_and_auc(early)
        m_min, _ = hypotension_minutes_and_auc(mid)
        l_min, _ = hypotension_minutes_and_auc(late)
        self.assertEqual(e_min, 0.0)
        self.assertEqual(m_min, 0.0)
        self.assertGreater(l_min, 0.0)
        # MAP=50 at t=660,670,...,720 (7 left-endpoints below 65), each owning a
        # 10 s forward interval -> 70 s = 1.1667 min, all attributed to LATE.
        self.assertAlmostEqual(l_min, 70.0 / 60.0, places=3)

    def test_early_hypotension_lands_in_early_bucket(self):
        samples = []
        for t in range(0, 901, 10):
            v = 50.0 if 60 <= t <= 120 else 85.0
            samples.append((float(t), v))
        win = (0.0, 900.0)
        early, mid, late = _phase_thirds_for_window(samples, win)
        e_min, _ = hypotension_minutes_and_auc(early)
        l_min, _ = hypotension_minutes_and_auc(late)
        self.assertGreater(e_min, 0.0)
        self.assertEqual(l_min, 0.0)
        # same 7-interval accounting as the late-bucket test -> 70 s = 1.1667 min
        self.assertAlmostEqual(e_min, 70.0 / 60.0, places=3)


# ---------------------------------------------------------------------------
# 3.  Timing / dynamics
# ---------------------------------------------------------------------------

class TestTimingDynamics(unittest.TestCase):
    def test_time_to_first_below_frac(self):
        # window [0, 1000]; first dip below 65 at t=500 -> frac 0.5
        samples = [(float(t), 80.0) for t in range(0, 500, 10)]
        samples += [(float(t), 50.0) for t in range(500, 1001, 10)]
        frac = time_to_first_below_frac(samples, (0.0, 1000.0))
        self.assertAlmostEqual(frac, 0.5, places=3)

    def test_time_to_first_below_never(self):
        samples = [(float(t), 90.0) for t in range(0, 1000, 10)]
        frac = time_to_first_below_frac(samples, (0.0, 1000.0))
        self.assertEqual(frac, 1.0)

    def test_nadir_time_frac(self):
        # global min at t=750 within [0,1000] -> 0.75
        samples = [(float(t), 80.0) for t in range(0, 1001, 10)]
        samples = [(t, (40.0 if t == 750.0 else v)) for t, v in samples]
        frac = nadir_time_frac(samples, (0.0, 1000.0))
        self.assertAlmostEqual(frac, 0.75, places=3)

    def test_nadir_ties_pick_earliest(self):
        samples = [(0.0, 90.0), (250.0, 40.0), (750.0, 40.0), (1000.0, 90.0)]
        frac = nadir_time_frac(samples, (0.0, 1000.0))
        self.assertAlmostEqual(frac, 0.25, places=3)

    def test_longest_run_below(self):
        # two runs below 65: a short one (20 s) and a long one (100 s)
        samples = []
        for t in range(0, 1001, 10):
            if 100 <= t <= 120:        # 20 s run
                v = 50.0
            elif 400 <= t <= 500:      # 100 s run
                v = 50.0
            else:
                v = 85.0
            samples.append((float(t), v))
        longest = longest_run_below(samples)
        # MAP=50 at t=400,410,...,500 -> 11 left-endpoints below 65, each owning a
        # 10 s forward interval -> 110 s = 1.8333 min continuous run.
        self.assertAlmostEqual(longest, 110.0 / 60.0, places=3)

    def test_longest_run_gap_breaks_credit(self):
        # a 1000 s gap inside the low stretch must be capped, not credited fully
        samples = [(0.0, 50.0), (1000.0, 50.0), (1010.0, 90.0)]
        longest = longest_run_below(samples, cap_dt=MAX_INTER_SAMPLE_DT_S)
        # first interval capped at 10 s, second interval 10 s low -> 20 s total run
        self.assertAlmostEqual(longest, 20.0 / 60.0, places=4)

    def test_slope_sign_decreasing(self):
        # MAP falling over the case -> negative slope
        samples = [(float(t), 100.0 - 0.01 * t) for t in range(0, 1000, 10)]
        slope = map_slope_per_hr(samples)
        self.assertIsNotNone(slope)
        self.assertLess(slope, 0.0)
        # -0.01 mmHg/s * 3600 = -36 mmHg/hr
        self.assertAlmostEqual(slope, -36.0, places=1)

    def test_slope_sign_increasing(self):
        samples = [(float(t), 60.0 + 0.005 * t) for t in range(0, 1000, 10)]
        slope = map_slope_per_hr(samples)
        self.assertGreater(slope, 0.0)

    def test_slope_none_single_sample(self):
        self.assertIsNone(map_slope_per_hr([(0.0, 80.0)]))

    def test_early_vs_late_delta(self):
        # early third mean 90, late third mean 70 -> delta = -20
        samples = []
        for t in range(0, 901, 10):
            if t < 300:
                v = 90.0
            elif t < 600:
                v = 80.0
            else:
                v = 70.0
            samples.append((float(t), v))
        early, _mid, late = phase_thirds(samples, (0.0, 900.0))
        delta = mean_value(late) - mean_value(early)
        self.assertAlmostEqual(delta, -20.0, places=4)


# ---------------------------------------------------------------------------
# 4.  Resample to grid
# ---------------------------------------------------------------------------

class TestResampleToGrid(unittest.TestCase):
    def test_grid_points_and_step(self):
        samples = [(float(t), 80.0) for t in range(0, 121, 5)]
        grid = resample_to_grid(samples, (0.0, 120.0), step=30.0)
        times = [t for t, _ in grid]
        self.assertEqual(times, [0.0, 30.0, 60.0, 90.0, 120.0])

    def test_last_value_hold(self):
        # value steps 70 -> 90 at t=50; grid at 30 sees 70, grid at 60 sees 90
        samples = [(0.0, 70.0), (50.0, 90.0), (120.0, 90.0)]
        grid = resample_to_grid(samples, (0.0, 120.0), step=30.0, max_gap_s=60.0)
        gd = dict(grid)
        self.assertEqual(gd[30.0], 70.0)
        self.assertEqual(gd[60.0], 90.0)

    def test_gap_yields_none(self):
        # only one sample at t=0; grid points far past max_gap should be None
        samples = [(0.0, 80.0)]
        grid = resample_to_grid(samples, (0.0, 120.0), step=30.0,
                                max_gap_s=MAX_INTER_SAMPLE_DT_S)
        gd = dict(grid)
        self.assertEqual(gd[0.0], 80.0)        # within gap
        self.assertIsNone(gd[60.0])            # 60 s after last sample -> gap
        self.assertIsNone(gd[120.0])

    def test_unsorted_input_handled(self):
        samples = [(120.0, 90.0), (0.0, 70.0), (60.0, 80.0)]
        grid = resample_to_grid(samples, (0.0, 120.0), step=60.0, max_gap_s=60.0)
        gd = dict(grid)
        self.assertEqual(gd[0.0], 70.0)
        self.assertEqual(gd[60.0], 80.0)
        self.assertEqual(gd[120.0], 90.0)


# ---------------------------------------------------------------------------
# 5.  Cross-signal coupling (MAP x propofol Ce)
# ---------------------------------------------------------------------------

class TestCoupling(unittest.TestCase):
    def test_minutes_below_during_high_ppfce(self):
        # window [0, 600], 30 s grid -> 21 cells.
        # MAP < 65 for t in [300, 600] (late half); MAP=85 before.
        # Ce ramps so it is high (above its median) in the SECOND half.
        # => co-occurrence only in [300, 600].
        win = (0.0, 600.0)
        map_samples = []
        for t in range(0, 601, 10):
            v = 50.0 if t >= 300 else 85.0
            map_samples.append((float(t), v))
        # Ce: low (0.5) in first half, high (4.0) in second half -> median ~ mid
        ppf_samples = []
        for t in range(0, 601, 10):
            c = 4.0 if t >= 300 else 0.5
            ppf_samples.append((float(t), c))
        mins = minutes_below_during_high_signal(
            map_samples, ppf_samples, win, step=30.0,
            max_gap_s=MAX_INTER_SAMPLE_DT_S)
        self.assertIsNotNone(mins)
        # overlap region [300,600]: grid cells at 300,330,...,600 = 11 cells.
        # Each contributes 30 s -> but median of Ce on grid (0.5/4.0 mix) sits
        # between, so high cells are the 4.0 ones. Expect ~ 11*30/60 = 5.5 min,
        # allowing the median boundary cell either way.
        self.assertGreater(mins, 4.0)
        self.assertLess(mins, 6.5)

    def test_no_overlap_zero_minutes(self):
        # MAP low only in first half; Ce high only in second half -> no overlap
        win = (0.0, 600.0)
        map_samples = [(float(t), (50.0 if t < 300 else 85.0)) for t in range(0, 601, 10)]
        ppf_samples = [(float(t), (4.0 if t >= 300 else 0.5)) for t in range(0, 601, 10)]
        mins = minutes_below_during_high_signal(map_samples, ppf_samples, win, step=30.0)
        self.assertAlmostEqual(mins, 0.0, places=4)

    def test_coupling_none_when_no_ppf(self):
        win = (0.0, 600.0)
        map_samples = [(float(t), 50.0) for t in range(0, 601, 10)]
        mins = minutes_below_during_high_signal(map_samples, [], win, step=30.0)
        self.assertIsNone(mins)

    def test_temporal_corr_positive(self):
        # MAP and Ce move together -> positive correlation
        win = (0.0, 600.0)
        map_samples = [(float(t), 60.0 + 0.05 * t) for t in range(0, 601, 30)]
        ppf_samples = [(float(t), 1.0 + 0.01 * t) for t in range(0, 601, 30)]
        r = temporal_pearson_corr(map_samples, ppf_samples, win, step=30.0)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.9)

    def test_temporal_corr_negative(self):
        win = (0.0, 600.0)
        map_samples = [(float(t), 90.0 - 0.05 * t) for t in range(0, 601, 30)]
        ppf_samples = [(float(t), 1.0 + 0.01 * t) for t in range(0, 601, 30)]
        r = temporal_pearson_corr(map_samples, ppf_samples, win, step=30.0)
        self.assertLess(r, -0.9)

    def test_temporal_corr_none_too_few_points(self):
        win = (0.0, 60.0)
        map_samples = [(0.0, 80.0)]
        ppf_samples = [(0.0, 1.0)]
        self.assertIsNone(temporal_pearson_corr(map_samples, ppf_samples, win, step=30.0))


# ---------------------------------------------------------------------------
# 6.  Window helpers + post-opend leakage exclusion
# ---------------------------------------------------------------------------

class TestWindowAndLeakage(unittest.TestCase):
    def test_intraop_window_anestart_opend(self):
        c = {"anestart": "100", "opend": "5000"}
        t0, t1 = _intraop_window(c)
        self.assertEqual((t0, t1), (100.0, 5000.0))

    def test_effective_window_falls_back_to_span(self):
        samples = [(10.0, 80.0), (200.0, 80.0)]
        win = _effective_window(samples, None, None)
        self.assertEqual(win, (10.0, 200.0))

    def test_post_opend_sample_excluded(self):
        # opend = 600. A deep sub-65 dip exists ONLY after opend; it must not
        # affect any temporal feature (§11 leakage).
        case = {"anestart": "0", "opend": "600", "opstart": "0"}
        t_start, t_end = _intraop_window(case)
        intraop = [(float(t), 80.0) for t in range(0, 601, 10)]
        postop = [(float(t), 20.0) for t in range(610, 1200, 10)]
        raw = intraop + postop

        clipped = _clip_to_window(raw, t_start, t_end)
        self.assertEqual([t for t, _ in clipped if t > 600.0], [],
                         msg="no sample after opend may survive clipping")
        filtered = _filter_physiologic(clipped, MAP_MIN, MAP_MAX)
        win = _effective_window(filtered, t_start, t_end)
        self.assertIsNotNone(win)

        # nadir (min) over the intraop window is 80 (the post-op 20 is excluded)
        nadir_v = min(v for _, v in filtered)
        self.assertAlmostEqual(nadir_v, 80.0, places=1)

        # full row: no hypotension anywhere, no late dip from leaked post-op data
        row = _compute_row(filtered, win)
        self.assertEqual(row["map_below65_min_late"], 0.0)
        self.assertEqual(row["map_longest_hypotension_run_min"], 0.0)
        self.assertEqual(row["temporal_available"], 1)

    def test_compute_row_keys_match_specs(self):
        samples = [(float(t), 80.0) for t in range(0, 901, 10)]
        win = (0.0, 900.0)
        row = _compute_row(samples, win)
        spec_names = {s.name for s in SPECS}
        self.assertEqual(set(row.keys()), spec_names)

    def test_compute_row_pk_features_none_without_coupling(self):
        # _compute_row alone must leave pk features None (filled by extract())
        samples = [(float(t), 50.0) for t in range(0, 901, 10)]
        row = _compute_row(samples, (0.0, 900.0))
        self.assertIsNone(row["ppfce_map_temporal_corr"])
        self.assertIsNone(row["map_below65_during_high_ppfce_min"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
