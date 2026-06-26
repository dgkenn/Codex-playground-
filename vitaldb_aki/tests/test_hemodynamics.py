"""test_hemodynamics.py -- Unit tests for the intraoperative hemodynamics module (§7C).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Run with:
    python3 -m unittest vitaldb_aki.tests.test_hemodynamics -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.hemodynamics import (
    MAP_MIN, MAP_MAX, HR_MIN, HR_MAX,
    MAP_HYPO_THRESHOLDS, MAX_INTER_SAMPLE_DT_S, BASELINE_WINDOW_S,
    SPECS,
    _filter_physiologic,
    _clip_to_window,
    _time_weighted_mean,
    _intraop_window,
    baseline_map,
    relative_drop_pct,
    hypotension_summaries,
    hypertensive_burden_min,
    hr_summaries,
)
from vitaldb_aki.features.base import audit_specs, LeakageError


# ---------------------------------------------------------------------------
# 1.  Module-level spec invariants
# ---------------------------------------------------------------------------

class TestSpecs(unittest.TestCase):
    def test_audit_passes(self):
        """All specs must pass the leakage audit (no postop timing)."""
        audit_specs(SPECS)   # must not raise

    def test_no_postop_timing(self):
        """Confirm no spec has timing='postop'."""
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop", msg=f"{s.name} has postop timing")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_map_available_is_standard(self):
        d = {s.name: s.fset for s in SPECS}
        self.assertEqual(d["map_available"], "standard")
        self.assertEqual(d["map_mean"], "standard")

    def test_expected_feature_count(self):
        # 19 features as designed
        self.assertEqual(len(SPECS), 19)

    def test_all_expected_names_present(self):
        names = {s.name for s in SPECS}
        required = {
            "map_available", "map_invasive",
            "map_mean", "map_lowest", "map_sd",
            "map_min_below_65", "map_min_below_60", "map_min_below_55", "map_min_below_50",
            "map_auc_below_65", "map_auc_below_60", "map_auc_below_55", "map_auc_below_50",
            "map_frac_below_65", "map_rel_drop_pct", "map_min_above_120",
            "hr_mean", "hr_min_tachy_gt100", "hr_min_brady_lt50",
        }
        self.assertEqual(names, required)


# ---------------------------------------------------------------------------
# 2.  Artifact filtering
# ---------------------------------------------------------------------------

class TestFilterPhysiologic(unittest.TestCase):
    SAMPLES = [
        (0.0,  -70.0),   # arterial flush artefact -- below MAP_MIN
        (2.0,   40.0),   # valid
        (4.0,   65.0),   # valid
        (6.0,   90.0),   # valid
        (8.0,  346.0),   # spike artefact -- above MAP_MAX
        (10.0, 120.0),   # valid
        (12.0,  -8.0),   # clamp / flush artefact
    ]

    def test_removes_artifact_low(self):
        out = _filter_physiologic(self.SAMPLES, MAP_MIN, MAP_MAX)
        values = [v for _, v in out]
        self.assertNotIn(-70.0, values)
        self.assertNotIn(-8.0,  values)

    def test_removes_artifact_high(self):
        out = _filter_physiologic(self.SAMPLES, MAP_MIN, MAP_MAX)
        values = [v for _, v in out]
        self.assertNotIn(346.0, values)

    def test_retains_valid(self):
        out = _filter_physiologic(self.SAMPLES, MAP_MIN, MAP_MAX)
        values = [v for _, v in out]
        self.assertIn(40.0, values)
        self.assertIn(65.0, values)
        self.assertIn(90.0, values)
        self.assertIn(120.0, values)

    def test_correct_count(self):
        # 4 valid out of 7
        out = _filter_physiologic(self.SAMPLES, MAP_MIN, MAP_MAX)
        self.assertEqual(len(out), 4)

    def test_boundary_inclusive(self):
        samples = [(0.0, MAP_MIN), (2.0, MAP_MAX)]
        out = _filter_physiologic(samples, MAP_MIN, MAP_MAX)
        self.assertEqual(len(out), 2)  # boundaries are kept


# ---------------------------------------------------------------------------
# 3.  Window clipping
# ---------------------------------------------------------------------------

class TestClipToWindow(unittest.TestCase):
    SAMPLES = [(float(t), 70.0) for t in range(0, 100, 5)]   # t = 0,5,10,...,95

    def test_lower_bound(self):
        out = _clip_to_window(self.SAMPLES, t_start=20.0, t_end=None)
        self.assertTrue(all(t >= 20.0 for t, _ in out))

    def test_upper_bound_is_opend(self):
        # CRITICAL: samples after opend must be excluded (leakage guard §11)
        out = _clip_to_window(self.SAMPLES, t_start=None, t_end=50.0)
        self.assertTrue(all(t <= 50.0 for t, _ in out))
        self.assertNotIn(55.0, [t for t, _ in out])

    def test_both_bounds(self):
        out = _clip_to_window(self.SAMPLES, t_start=20.0, t_end=50.0)
        self.assertTrue(all(20.0 <= t <= 50.0 for t, _ in out))

    def test_none_bounds_returns_all(self):
        out = _clip_to_window(self.SAMPLES, t_start=None, t_end=None)
        self.assertEqual(len(out), len(self.SAMPLES))


# ---------------------------------------------------------------------------
# 4.  Intraop window extraction
# ---------------------------------------------------------------------------

class TestIntraopWindow(unittest.TestCase):
    def _case(self, **kw):
        return {k: str(v) for k, v in kw.items()}

    def test_anestart_opend(self):
        c = self._case(anestart=100, opend=5000)
        t0, t1 = _intraop_window(c)
        self.assertEqual(t0, 100.0)
        self.assertEqual(t1, 5000.0)

    def test_fallback_to_opstart(self):
        c = self._case(opstart=200, opend=5000)
        t0, t1 = _intraop_window(c)
        self.assertEqual(t0, 200.0)
        self.assertEqual(t1, 5000.0)

    def test_no_opend_returns_none(self):
        c = self._case(anestart=100)
        t0, t1 = _intraop_window(c)
        self.assertIsNone(t1)

    def test_anestart_takes_priority_over_opstart(self):
        c = self._case(anestart=100, opstart=200, opend=5000)
        t0, _ = _intraop_window(c)
        self.assertEqual(t0, 100.0)


# ---------------------------------------------------------------------------
# 5.  Time-weighted mean
# ---------------------------------------------------------------------------

class TestTimeWeightedMean(unittest.TestCase):
    def test_constant_series(self):
        # All MAP = 80, evenly spaced 2 s -> mean should be 80
        samples = [(float(i * 2), 80.0) for i in range(20)]
        m = _time_weighted_mean(samples)
        self.assertAlmostEqual(m, 80.0, places=4)

    def test_two_level_series(self):
        # First 10 s at MAP=60, next 10 s at MAP=100 -> weighted mean = 80
        # samples: (0,60), (10,100), (20,100)
        # dt1 = min(10,10)=10 @ 60; dt2 = min(10,10)=10 @ 100 -> mean=(600+1000)/20=80
        samples = [(0.0, 60.0), (10.0, 100.0), (20.0, 100.0)]
        m = _time_weighted_mean(samples)
        self.assertAlmostEqual(m, 80.0, places=4)

    def test_gap_capped(self):
        # Large gap (100 s) between samples should be capped at MAX_INTER_SAMPLE_DT_S
        # (0,60) -> (100,90) -> (102,90)
        # dt1 = min(100,10)=10 @ 60; dt2 = min(2,10)=2 @ 90
        # weighted mean = (10*60 + 2*90) / 12 = (600+180)/12 = 65.0
        samples = [(0.0, 60.0), (100.0, 90.0), (102.0, 90.0)]
        m = _time_weighted_mean(samples, max_dt_s=10.0)
        self.assertAlmostEqual(m, 65.0, places=4)

    def test_single_sample_returns_none(self):
        self.assertIsNone(_time_weighted_mean([(0.0, 75.0)]))

    def test_empty_returns_none(self):
        self.assertIsNone(_time_weighted_mean([]))


# ---------------------------------------------------------------------------
# 6.  Hypotension summaries (AUC / minutes / fraction) -- core §7C math
# ---------------------------------------------------------------------------

class TestHypotensionSummaries(unittest.TestCase):
    """
    Construction note: to get EXACTLY N seconds below a threshold with uniform
    2-second sampling, build samples at t=0,2,...,2*(N//2) at the low value, then
    t=2*(N//2)+2, ... at the high value.  The inter-sample dt for the last low
    sample -> first high sample also counts, so the total below-threshold dt is
    the sum of N//2 intervals * 2s.

    For a clean 60 s (30 intervals of 2 s):
      low_samples = [(0,v),(2,v),...,(58,v)]  -- 30 points, 29 intervals
      Then the 30th interval is (58->60) = dt 2s at v=low -> +2s
      Achieved by appending (60, high_val) as the "bridge" sample.
    We use explicit construction below to be precise.
    """

    def _build_segment(self, t_start, duration_s, value, step=2.0):
        """Build samples for a duration_s segment starting at t_start.

        The last sample is at t_start + duration_s (inclusive), acting as the
        right endpoint of the final interval.
        """
        samples = []
        t = t_start
        while t <= t_start + duration_s + 1e-9:
            samples.append((t, value))
            t = round(t + step, 9)
        return samples

    def test_known_minutes_below_65(self):
        # Exactly 60 s at MAP=50 (below 65), then 60 s at MAP=80 (above 65)
        # Build: low segment [0,60], high segment [60,120]
        # The sample at t=60 belongs to both ends; we use it once via the bridge.
        samples_low  = [(float(t), 50.0) for t in range(0, 60, 2)]   # t=0..58 (30 pts)
        bridge       = [(60.0, 80.0)]                                  # bridge ends low interval
        samples_high = [(float(t), 80.0) for t in range(62, 122, 2)] # t=62..120 (30 pts)
        samples = samples_low + bridge + samples_high
        # Interval (58->60) = dt 2s at MAP=50 (< 65): counted below
        # So: 30 intervals of 2s = 60 s below 65
        res = hypotension_summaries(samples, thresholds=(65,))
        self.assertAlmostEqual(res["min_below_65"], 1.0, places=3)

    def test_known_auc_below_65(self):
        # 60 s at MAP=50, threshold=65 -> AUC = (65-50)*60s = 900 mmHg·s = 15 mmHg·min
        samples_low  = [(float(t), 50.0) for t in range(0, 60, 2)]
        bridge       = [(60.0, 80.0)]
        samples_high = [(float(t), 80.0) for t in range(62, 122, 2)]
        samples = samples_low + bridge + samples_high
        res = hypotension_summaries(samples, thresholds=(65,))
        self.assertAlmostEqual(res["auc_below_65"], 15.0, places=2)

    def test_zero_when_above_threshold(self):
        # All MAP = 90 -> nothing below 65
        samples = [(float(t), 90.0) for t in range(0, 100, 2)]
        res = hypotension_summaries(samples, thresholds=(65, 60, 55, 50))
        self.assertEqual(res["min_below_65"], 0.0)
        self.assertEqual(res["auc_below_65"], 0.0)
        self.assertEqual(res["frac_below_65"], 0.0)

    def test_frac_below_65(self):
        # Exactly half the time below 65: 120 s below, 120 s above
        # low segment: 60 intervals of 2s = 120s
        samples_low  = [(float(t), 50.0) for t in range(0, 120, 2)]   # t=0..118
        bridge       = [(120.0, 80.0)]                                  # bridge completes 60th interval
        samples_high = [(float(t), 80.0) for t in range(122, 242, 2)] # t=122..240
        samples = samples_low + bridge + samples_high
        # below: 60 intervals * 2s = 120s; above: 60 intervals * 2s = 120s; total = 240s
        res = hypotension_summaries(samples, thresholds=(65,))
        self.assertAlmostEqual(res["frac_below_65"], 0.5, places=3)

    def test_gap_capped_in_auc(self):
        # samples: (0, MAP=50), (100, MAP=50), (102, MAP=80)
        # With max_dt_s=10: dt1=min(100,10)=10 at v=50 (below 65);
        #                   dt2=min(2,10)=2   at v=50 (ALSO below 65 since 50<65)
        # seconds_below = 10+2 = 12s; minutes_below = 12/60 = 0.2
        # auc = (65-50)*(10+2)/60 = 15*12/60 = 3.0 mmHg·min
        samples = [(0.0, 50.0), (100.0, 50.0), (102.0, 80.0)]
        res = hypotension_summaries(samples, thresholds=(65,), max_dt_s=10.0)
        self.assertAlmostEqual(res["min_below_65"], 12.0 / 60.0, places=4)
        self.assertAlmostEqual(res["auc_below_65"], 15.0 * 12.0 / 60.0, places=4)

    def test_gap_cap_inflates_nothing(self):
        # Without capping, a 1000s gap at MAP=40 would give 1000s of AUC
        # With cap=10s, it gives only 10s
        samples = [(0.0, 40.0), (1000.0, 40.0), (1002.0, 90.0)]
        res_capped   = hypotension_summaries(samples, thresholds=(65,), max_dt_s=10.0)
        # Capped: dt1=10, dt2=2 (1002->end but only 2 samples after -> dt=min(2,10)=2)
        # seconds_below = 10+2=12 (both values=40 < 65)
        self.assertAlmostEqual(res_capped["min_below_65"], 12.0 / 60.0, places=4)

        # Without cap: dt1=1000 (uncapped), dt2=2 -> total=1002s of below-65 time
        res_uncapped = hypotension_summaries(samples, thresholds=(65,), max_dt_s=1e9)
        self.assertAlmostEqual(res_uncapped["min_below_65"], 1002.0 / 60.0, places=3)

    def test_multiple_thresholds(self):
        # MAP=40: below all thresholds 65/60/55/50
        samples = [(float(t), 40.0) for t in range(0, 60, 2)] + [(60.0, 40.0)]
        res = hypotension_summaries(samples, thresholds=(65, 60, 55, 50))
        # All four should have the same non-zero minutes
        self.assertGreater(res["min_below_65"], 0)
        self.assertGreater(res["min_below_50"], 0)
        # Deeper thresholds accumulate less AUC per unit time (smaller gap to value)
        self.assertGreater(res["auc_below_65"], res["auc_below_60"])
        self.assertGreater(res["auc_below_60"], res["auc_below_55"])
        self.assertGreater(res["auc_below_55"], res["auc_below_50"])

    def test_empty_samples(self):
        res = hypotension_summaries([], thresholds=(65,))
        self.assertEqual(res["min_below_65"], 0.0)
        self.assertEqual(res["total_recording_min"], 0.0)


# ---------------------------------------------------------------------------
# 7.  Hypertensive burden
# ---------------------------------------------------------------------------

class TestHypertensiveBurden(unittest.TestCase):
    def test_known_minutes_above_120(self):
        # 60 s at MAP=130, then 60 s at MAP=80
        samples_high = [(float(t), 130.0) for t in range(0, 60, 2)]
        bridge       = [(60.0, 80.0)]
        samples_norm = [(float(t), 80.0) for t in range(62, 122, 2)]
        samples = samples_high + bridge + samples_norm
        result = hypertensive_burden_min(samples, threshold=120.0)
        self.assertAlmostEqual(result, 1.0, places=3)

    def test_zero_when_below_threshold(self):
        samples = [(float(i * 2), 80.0) for i in range(20)]
        result = hypertensive_burden_min(samples, threshold=120.0)
        self.assertEqual(result, 0.0)


# ---------------------------------------------------------------------------
# 8.  Baseline MAP and relative drop
# ---------------------------------------------------------------------------

class TestRelativeDrop(unittest.TestCase):
    def test_baseline_is_median_of_first_5_min(self):
        # First 5 min (300 s): MAP=100; then MAP=60
        # baseline_map uses samples[0][0] as anchor -> first 300s from t=0
        samples_early = [(float(t), 100.0) for t in range(0, 300, 5)]
        samples_late  = [(float(t), 60.0)  for t in range(300, 600, 5)]
        samples = samples_early + samples_late
        base = baseline_map(samples, window_s=BASELINE_WINDOW_S)
        self.assertAlmostEqual(base, 100.0, places=2)

    def test_relative_drop_computation(self):
        # Baseline = 100 mmHg, lowest = 60 mmHg -> drop = (100-60)/100*100 = 40%
        samples_early = [(float(t), 100.0) for t in range(0, 300, 5)]
        samples_late  = [(float(t), 60.0)  for t in range(300, 600, 5)]
        samples = samples_early + samples_late
        drop = relative_drop_pct(samples, baseline_window_s=BASELINE_WINDOW_S)
        self.assertAlmostEqual(drop, 40.0, places=2)

    def test_no_drop_when_lowest_equals_baseline(self):
        # Constant MAP -> no drop
        samples = [(float(t), 80.0) for t in range(0, 600, 5)]
        drop = relative_drop_pct(samples, baseline_window_s=BASELINE_WINDOW_S)
        self.assertAlmostEqual(drop, 0.0, places=4)

    def test_none_when_no_baseline_samples(self):
        # baseline_map uses t0 = samples[0][0] as anchor; use a very small window
        # so only the first sample is in the window -> median is still 80
        # To get None, we need empty input to baseline_map.
        base = baseline_map([], window_s=300.0)
        self.assertIsNone(base)

    def test_baseline_anchors_to_first_sample(self):
        # Samples start at t=1000 (not 0); first-5-min window is [1000, 1300]
        samples_early = [(float(t), 90.0)  for t in range(1000, 1300, 5)]
        samples_late  = [(float(t), 50.0)  for t in range(1300, 1600, 5)]
        samples = samples_early + samples_late
        base = baseline_map(samples, window_s=300.0)
        self.assertAlmostEqual(base, 90.0, places=2)
        drop = relative_drop_pct(samples, baseline_window_s=300.0)
        expected_drop = 100.0 * (90.0 - 50.0) / 90.0
        self.assertAlmostEqual(drop, expected_drop, places=2)


# ---------------------------------------------------------------------------
# 9.  HR summaries
# ---------------------------------------------------------------------------

class TestHRSummaries(unittest.TestCase):
    def test_known_tachy_minutes(self):
        # 60 s at HR=110 (tachy) then 60 s at HR=70
        s1 = [(float(t), 110.0) for t in range(0, 60, 2)]
        bridge = [(60.0, 70.0)]
        s2 = [(float(t), 70.0) for t in range(62, 122, 2)]
        samples = s1 + bridge + s2
        res = hr_summaries(samples)
        self.assertAlmostEqual(res["hr_min_tachy_gt100"], 1.0, places=3)
        self.assertEqual(res["hr_min_brady_lt50"], 0.0)

    def test_known_brady_minutes(self):
        # 60 s at HR=40 (brady) then 60 s at HR=70
        s1 = [(float(t), 40.0) for t in range(0, 60, 2)]
        bridge = [(60.0, 70.0)]
        s2 = [(float(t), 70.0) for t in range(62, 122, 2)]
        samples = s1 + bridge + s2
        res = hr_summaries(samples)
        self.assertAlmostEqual(res["hr_min_brady_lt50"], 1.0, places=3)
        self.assertEqual(res["hr_min_tachy_gt100"], 0.0)

    def test_hr_mean(self):
        # Constant HR=75 -> mean = 75
        samples = [(float(i * 2), 75.0) for i in range(20)]
        res = hr_summaries(samples)
        self.assertAlmostEqual(res["hr_mean"], 75.0, places=2)

    def test_single_sample_returns_none(self):
        res = hr_summaries([(0.0, 70.0)])
        self.assertIsNone(res["hr_mean"])
        self.assertIsNone(res["hr_min_tachy_gt100"])

    def test_empty_returns_none(self):
        res = hr_summaries([])
        self.assertIsNone(res["hr_mean"])


# ---------------------------------------------------------------------------
# 10.  Extract() end-to-end using pure helpers (no network; no mock needed)
# ---------------------------------------------------------------------------

class TestExtractPipeline(unittest.TestCase):
    """
    We test the end-to-end pipeline logic by calling the pure helper functions
    in the same sequence as extract() does, feeding synthetic series.  This
    avoids any network I/O (first_available / download_track) while still
    covering the full computation path.
    """

    def _make_case(self, anestart=0.0, opend=3600.0, opstart=0.0):
        return {
            "caseid": "42",
            "anestart": str(anestart),
            "opstart": str(opstart),
            "opend": str(opend),
        }

    def _pipeline(self, map_series, hr_series=None, case=None):
        """Run the extract logic on synthetic series and return the feature row."""
        if case is None:
            case = self._make_case()
        t_start, t_end = _intraop_window(case)

        if map_series is None:
            return {"map_available": 0, "map_invasive": None}

        clipped = _clip_to_window(map_series, t_start, t_end)
        filtered = _filter_physiologic(clipped, MAP_MIN, MAP_MAX)

        if not filtered:
            return {"map_available": 0, "map_invasive": None}

        hypo = hypotension_summaries(filtered)
        hyper = hypertensive_burden_min(filtered)
        drop = relative_drop_pct(filtered)
        tw_mean = _time_weighted_mean(filtered)
        vals = [v for _, v in filtered]
        mean_v = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / len(vals)) if len(vals) >= 2 else None

        hr_res: dict = {"hr_mean": None, "hr_min_tachy_gt100": None, "hr_min_brady_lt50": None}
        if hr_series is not None:
            hr_clip = _clip_to_window(hr_series, t_start, t_end)
            hr_filt = _filter_physiologic(hr_clip, HR_MIN, HR_MAX)
            hr_res = hr_summaries(hr_filt)

        return {
            "map_available":      1,
            "map_invasive":       1,
            "map_mean":           round(tw_mean, 4) if tw_mean is not None else None,
            "map_lowest":         round(min(v for _, v in filtered), 4),
            "map_sd":             round(sd, 4) if sd is not None else None,
            "map_min_below_65":   hypo["min_below_65"],
            "map_min_below_60":   hypo["min_below_60"],
            "map_min_below_55":   hypo["min_below_55"],
            "map_min_below_50":   hypo["min_below_50"],
            "map_auc_below_65":   hypo["auc_below_65"],
            "map_auc_below_60":   hypo["auc_below_60"],
            "map_auc_below_55":   hypo["auc_below_55"],
            "map_auc_below_50":   hypo["auc_below_50"],
            "map_frac_below_65":  hypo["frac_below_65"],
            "map_rel_drop_pct":   drop,
            "map_min_above_120":  hyper,
            "hr_mean":            hr_res["hr_mean"],
            "hr_min_tachy_gt100": hr_res["hr_min_tachy_gt100"],
            "hr_min_brady_lt50":  hr_res["hr_min_brady_lt50"],
        }

    def test_no_map_track_signals_unavailable(self):
        row = self._pipeline(map_series=None)
        self.assertEqual(row["map_available"], 0)
        self.assertIsNone(row["map_invasive"])

    def test_valid_map_stable(self):
        # Steady MAP = 75 over 3600 s: never below 65, never above 120
        samples = [(float(t), 75.0) for t in range(0, 3600, 2)]
        row = self._pipeline(samples)
        self.assertEqual(row["map_available"], 1)
        self.assertAlmostEqual(row["map_mean"], 75.0, places=2)
        self.assertEqual(row["map_min_below_65"], 0.0)
        self.assertEqual(row["map_auc_below_65"], 0.0)
        self.assertAlmostEqual(row["map_lowest"], 75.0, places=1)

    def test_artifact_removal_pipeline(self):
        # Inject flush artefact (-70) and spike (350) flanked by valid samples
        samples = [(0.0, -70.0), (2.0, 75.0), (4.0, 350.0), (6.0, 80.0), (8.0, 80.0)]
        row = self._pipeline(samples)
        # After filtering, lowest should be 75 (not -70)
        self.assertGreaterEqual(row["map_lowest"], MAP_MIN)
        self.assertAlmostEqual(row["map_lowest"], 75.0, places=1)

    def test_all_artifacts_gives_unavailable(self):
        # All samples are artifacts -> pipeline marks as unavailable
        samples = [(0.0, -70.0), (2.0, -8.0), (4.0, 346.0)]
        row = self._pipeline(samples)
        self.assertEqual(row["map_available"], 0)

    def test_post_opend_samples_excluded(self):
        # opend = 600 s; low MAP only appears after opend
        case = self._make_case(anestart=0.0, opend=600.0)
        samples_intraop = [(float(t), 80.0) for t in range(0, 600, 2)]
        samples_postop  = [(float(t), 20.0) for t in range(602, 1200, 2)]
        samples = samples_intraop + samples_postop
        row = self._pipeline(samples, case=case)
        # map_lowest should be 80 (post-opend MAP=20 excluded)
        self.assertAlmostEqual(row["map_lowest"], 80.0, places=1)
        # map_min_below_65 should be 0 (no sub-65 in intraop window)
        self.assertEqual(row["map_min_below_65"], 0.0)

    def test_hr_none_when_no_hr_series(self):
        samples = [(float(t), 75.0) for t in range(0, 100, 2)]
        row = self._pipeline(samples, hr_series=None)
        self.assertIsNone(row["hr_mean"])
        self.assertIsNone(row["hr_min_tachy_gt100"])

    def test_hr_features_populated(self):
        map_s = [(float(t), 75.0) for t in range(0, 3600, 2)]
        hr_s  = [(float(t), 70.0) for t in range(0, 3600, 2)]
        row = self._pipeline(map_s, hr_series=hr_s)
        self.assertAlmostEqual(row["hr_mean"], 70.0, places=2)
        self.assertEqual(row["hr_min_tachy_gt100"], 0.0)
        self.assertEqual(row["hr_min_brady_lt50"], 0.0)

    def test_hr_artifact_filter_in_pipeline(self):
        # HR artifacts (>220 or <20) filtered before hr_summaries
        map_s = [(float(t), 75.0) for t in range(0, 200, 2)]
        hr_s  = [(0.0, 300.0), (2.0, 70.0), (4.0, 0.0), (6.0, 70.0), (8.0, 70.0)]
        row = self._pipeline(map_s, hr_series=hr_s)
        # After filtering: [(2,70),(6,70),(8,70)] -> mean=70, no tachy, no brady
        self.assertAlmostEqual(row["hr_mean"], 70.0, places=2)
        self.assertEqual(row["hr_min_tachy_gt100"], 0.0)
        self.assertEqual(row["hr_min_brady_lt50"], 0.0)


# ---------------------------------------------------------------------------
# 11.  Post-opend leakage guard (samples after opend must NOT be used)
# ---------------------------------------------------------------------------

class TestPostOpendLeakage(unittest.TestCase):
    def test_opend_is_hard_cutoff(self):
        """No sample timestamped after opend may contribute to features (§11)."""
        case = {"caseid": "99", "anestart": "0", "opend": "1800", "opstart": "0"}
        t_start, t_end = _intraop_window(case)
        self.assertEqual(t_end, 1800.0)

        # Low MAP only in post-op period
        samples_intraop = [(float(t), 80.0) for t in range(0, 1800, 2)]
        samples_postop  = [(float(t), 20.0) for t in range(1802, 3000, 2)]
        samples = samples_intraop + samples_postop

        clipped = _clip_to_window(samples, t_start, t_end)
        post_times = [t for t, _ in clipped if t > 1800.0]
        self.assertEqual(post_times, [], msg="No samples after opend should survive clipping")

        filtered = _filter_physiologic(clipped, MAP_MIN, MAP_MAX)
        lowest = min(v for _, v in filtered)
        # Without post-op data, lowest MAP is 80 (not 20)
        self.assertAlmostEqual(lowest, 80.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
