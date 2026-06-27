"""test_venous_congestion.py -- Offline unit tests for the venous-congestion family.

UNMINED axis: central venous pressure / renal venous congestion (mechanistically
distinct from the PFDS low-flow / arterial axis).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is tested against hand-built series with KNOWN expected direction
(a high-CVP congested case vs a normal case; AUC above threshold; empty -> None).

Run with:
    python3 -m unittest vitaldb_aki.tests.test_venous_congestion -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.venous_congestion import (
    # Module-level constants
    SPECS,
    CVP_MIN, CVP_MAX,
    CVP_CONGESTION_THR, CVP_MILD_THR,
    MIN_USABLE_SAMPLES, MAX_INTER_SAMPLE_DT_S,
    CVP_TRACK_CANDIDATES,
    USES_TRACKS,
    # Pure helpers under test
    _intraop_window,
    _filter_physiologic,
    _clip_to_window,
    _time_weighted_mean,
    _frac_time_above,
    _auc_above,
)
from vitaldb_aki.features.base import audit_specs


def _uniform(value: float, n: int = 20, dt: float = 30.0) -> list[tuple[float, float]]:
    """n samples of constant `value` spaced `dt` seconds apart from t=0."""
    return [(i * dt, value) for i in range(n)]


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_uses_tracks_true(self):
        self.assertTrue(USES_TRACKS)

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
            self.assertEqual(s.fset, "comprehensive",
                             msg=f"{s.name} fset={s.fset!r} (expected comprehensive)")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in venous_congestion SPECS")

    def test_availability_first(self):
        self.assertEqual(SPECS[0].name, "vcong_available",
                         "vcong_available must be the FIRST spec")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "vcong_available",
            "vcong_cvp_mean",
            "vcong_cvp_max",
            "vcong_cvp_above12_frac",
            "vcong_cvp_above8_frac",
            "vcong_cvp_auc_above12",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing venous_congestion specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 6, "Expected exactly 6 venous-congestion specs")

    def test_track_priority(self):
        self.assertEqual(CVP_TRACK_CANDIDATES, ["Solar8000/CVP", "SNUADC/CVP"])

    def test_thresholds(self):
        self.assertEqual(CVP_CONGESTION_THR, 12.0)
        self.assertEqual(CVP_MILD_THR, 8.0)
        self.assertEqual(CVP_MIN, -5.0)
        self.assertEqual(CVP_MAX, 40.0)


# ===========================================================================
# 2. _intraop_window (windowing / leakage cutoff)
# ===========================================================================

class TestIntraopWindow(unittest.TestCase):
    def test_anestart_preferred(self):
        case = {"anestart": 100.0, "opstart": 200.0, "opend": 3600.0}
        self.assertEqual(_intraop_window(case), (100.0, 3600.0))

    def test_opstart_fallback(self):
        case = {"opstart": 200.0, "opend": 3600.0}
        self.assertEqual(_intraop_window(case), (200.0, 3600.0))

    def test_none_when_no_opend(self):
        case = {"anestart": 100.0}
        self.assertEqual(_intraop_window(case), (None, None))

    def test_start_none_when_only_opend(self):
        case = {"opend": 3600.0}
        self.assertEqual(_intraop_window(case), (None, 3600.0))


# ===========================================================================
# 3. _filter_physiologic / _clip_to_window (artifact + leakage gates)
# ===========================================================================

class TestGates(unittest.TestCase):
    def test_physiologic_drops_out_of_range(self):
        s = [(0.0, -50.0), (1.0, 10.0), (2.0, 99.0), (3.0, 35.0)]
        out = _filter_physiologic(s, CVP_MIN, CVP_MAX)
        self.assertEqual(out, [(1.0, 10.0), (3.0, 35.0)],
                         "Drop CVP < -5 and CVP > 40 (artifact)")

    def test_physiologic_keeps_negative_within_gate(self):
        """CVP_MIN is -5, so mild negatives (-3) are physiologic and kept."""
        s = [(0.0, -3.0), (1.0, 0.0), (2.0, 5.0)]
        out = _filter_physiologic(s, CVP_MIN, CVP_MAX)
        self.assertEqual(out, s)

    def test_clip_respects_cutoff(self):
        s = [(0.0, 10.0), (3600.0, 12.0), (3630.0, 99.0)]
        out = _clip_to_window(s, 0.0, 3600.0)
        self.assertEqual(out, [(0.0, 10.0), (3600.0, 12.0)],
                         "Sample at t > opend must be dropped (leakage)")


# ===========================================================================
# 4. _time_weighted_mean
# ===========================================================================

class TestTimeWeightedMean(unittest.TestCase):
    def test_constant(self):
        s = _uniform(10.0, n=20, dt=30.0)
        self.assertAlmostEqual(_time_weighted_mean(s), 10.0, places=6)

    def test_high_cvp_case_above_normal(self):
        """A congested case (CVP 16) has a higher mean than a normal case (CVP 5)."""
        congested = _uniform(16.0)
        normal = _uniform(5.0)
        self.assertGreater(_time_weighted_mean(congested), _time_weighted_mean(normal))

    def test_none_when_too_few(self):
        self.assertIsNone(_time_weighted_mean([(0.0, 10.0)]))
        self.assertIsNone(_time_weighted_mean([]))

    def test_gap_cap_weighting(self):
        """A huge final gap is capped at max_dt_s; the long-held value is
        down-weighted relative to an uncapped average."""
        # value 0 held for 1 step, value 20 held across a 10000 s gap (capped @ 10s)
        s = [(0.0, 0.0), (30.0, 20.0), (10030.0, 20.0)]
        m = _time_weighted_mean(s, max_dt_s=MAX_INTER_SAMPLE_DT_S)
        self.assertIsNotNone(m)
        # interval0: dt=10 (cap), v=0 ; interval1: dt=10 (cap), v=20 -> mean 10
        self.assertAlmostEqual(m, 10.0, places=6)


# ===========================================================================
# 5. _frac_time_above  (vcong_cvp_above12_frac / above8_frac engine)
# ===========================================================================

class TestFracTimeAbove(unittest.TestCase):
    def test_all_above(self):
        s = _uniform(16.0)  # CVP 16 > 12 always
        self.assertAlmostEqual(_frac_time_above(s, CVP_CONGESTION_THR), 1.0, places=6)

    def test_none_above(self):
        s = _uniform(5.0)   # CVP 5, never above 12 or 8
        self.assertAlmostEqual(_frac_time_above(s, CVP_CONGESTION_THR), 0.0, places=6)
        self.assertAlmostEqual(_frac_time_above(s, CVP_MILD_THR), 0.0, places=6)

    def test_high_case_vs_normal(self):
        """Congested case spends fraction-of-time above 12 > normal case."""
        congested = _uniform(16.0)
        normal = _uniform(5.0)
        self.assertGreater(
            _frac_time_above(congested, CVP_CONGESTION_THR),
            _frac_time_above(normal, CVP_CONGESTION_THR),
        )

    def test_partial(self):
        """Half the (weighted) time above threshold => ~0.5."""
        # 20 intervals: first 10 at CVP 16 (>12), last 10 at CVP 5 (<12).
        # The forward-dt attribution uses samples[i] for interval i, i in [0,18].
        s = [(i * 30.0, 16.0 if i < 10 else 5.0) for i in range(20)]
        f = _frac_time_above(s, CVP_CONGESTION_THR)
        self.assertIsNotNone(f)
        self.assertGreater(f, 0.4)
        self.assertLess(f, 0.6)

    def test_mild_threshold_catches_more_than_congestion(self):
        """At CVP 10: above the mild (8) threshold but not the congestion (12) one."""
        s = _uniform(10.0)
        self.assertAlmostEqual(_frac_time_above(s, CVP_MILD_THR), 1.0, places=6)
        self.assertAlmostEqual(_frac_time_above(s, CVP_CONGESTION_THR), 0.0, places=6)

    def test_none_when_too_few(self):
        self.assertIsNone(_frac_time_above([(0.0, 16.0)], CVP_CONGESTION_THR))
        self.assertIsNone(_frac_time_above([], CVP_CONGESTION_THR))


# ===========================================================================
# 6. _auc_above  (vcong_cvp_auc_above12 engine; returns mmHg*minutes)
# ===========================================================================

class TestAucAbove(unittest.TestCase):
    def test_zero_when_never_above(self):
        s = _uniform(5.0)
        self.assertAlmostEqual(_auc_above(s, CVP_CONGESTION_THR), 0.0, places=6)

    def test_positive_when_above(self):
        s = _uniform(16.0)  # 4 mmHg above 12
        auc = _auc_above(s, CVP_CONGESTION_THR)
        self.assertIsNotNone(auc)
        self.assertGreater(auc, 0.0)

    def test_known_value_in_minutes(self):
        """Six samples 10 s apart at CVP 22: 5 intervals * (22-12) * 10 s
        = 500 mmHg*s = 500/60 mmHg*min. (10 s spacing == gap cap, no clipping.)"""
        s = [(i * 10.0, 22.0) for i in range(6)]
        auc = _auc_above(s, CVP_CONGESTION_THR)
        self.assertIsNotNone(auc)
        self.assertAlmostEqual(auc, 500.0 / 60.0, places=6,
                               msg="5 * (22-12) mmHg * 10 s = 500 mmHg*s = 500/60 mmHg*min")

    def test_high_case_above_threshold(self):
        """A congested case yields AUC above a meaningful threshold; normal yields 0."""
        # 721 samples 10 s apart (2 h) at CVP 18 -> 720 intervals * (18-12) * 10 s
        #   = 720 * 6 * 10 = 43200 mmHg*s = 720 mmHg*min.  10 s == gap cap (no clip).
        congested = [(i * 10.0, 18.0) for i in range(721)]
        normal = [(i * 10.0, 5.0) for i in range(721)]
        auc_c = _auc_above(congested, CVP_CONGESTION_THR)
        auc_n = _auc_above(normal, CVP_CONGESTION_THR)
        self.assertIsNotNone(auc_c)
        self.assertGreater(auc_c, 50.0, "Congested AUC should clear a 50 mmHg*min threshold")
        self.assertAlmostEqual(auc_c, 720.0, places=4)
        self.assertAlmostEqual(auc_n, 0.0, places=6)

    def test_higher_cvp_higher_auc(self):
        higher = _uniform(20.0)
        lower = _uniform(14.0)
        self.assertGreater(
            _auc_above(higher, CVP_CONGESTION_THR),
            _auc_above(lower, CVP_CONGESTION_THR),
        )

    def test_gap_capped(self):
        """A long inter-sample gap is capped at max_dt_s, bounding the AUC."""
        # value 22 (10 above thr) held across a 10000 s gap, capped at 10 s.
        s = [(0.0, 22.0), (10000.0, 22.0)]
        auc = _auc_above(s, CVP_CONGESTION_THR, max_dt_s=MAX_INTER_SAMPLE_DT_S)
        self.assertIsNotNone(auc)
        # (22-12) * 10 s = 100 mmHg*s = 100/60 mmHg*min
        self.assertAlmostEqual(auc, 100.0 / 60.0, places=6)

    def test_none_when_too_few(self):
        self.assertIsNone(_auc_above([(0.0, 22.0)], CVP_CONGESTION_THR))
        self.assertIsNone(_auc_above([], CVP_CONGESTION_THR))


# ===========================================================================
# 7. Missingness contract: extract() emits 0/None for absent or unusable CVP
# ===========================================================================

class TestExtractMissingness(unittest.TestCase):
    """extract() lazy-imports first_available/download_track from
    vitaldb_aki.data.tracks, so we patch at the source module."""

    def test_none_row_when_no_cvp(self):
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.venous_congestion import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])

        self.assertIn("1", result)
        row = result["1"]
        self.assertEqual(row["vcong_available"], 0, "Missing CVP => vcong_available=0")
        for s in SPECS:
            if s.name != "vcong_available":
                self.assertIsNone(row[s.name],
                                  f"{s.name} must be None (NOT 0) when CVP absent")

    def test_none_row_when_too_few_samples(self):
        """CVP present but < MIN_USABLE_SAMPLES physiologic samples => available=0."""
        import unittest.mock as mock
        # Only 3 in-range samples (< MIN_USABLE_SAMPLES=10).
        short_cvp = [(0.0, 10.0), (30.0, 11.0), (60.0, 12.0)]
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=("Solar8000/CVP", short_cvp)), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=short_cvp):
            from vitaldb_aki.features.venous_congestion import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"7": {"caseid": "7", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["7"])

        row = result["7"]
        self.assertEqual(row["vcong_available"], 0)
        for s in SPECS:
            if s.name != "vcong_available":
                self.assertIsNone(row[s.name])

    def test_computes_when_cvp_usable(self):
        """A congested CVP track => available=1 and physiologic biomarkers populated."""
        import unittest.mock as mock
        # 40 samples at CVP 16 (congested; > MIN_USABLE_SAMPLES, all in-range).
        cvp = [(i * 60.0, 16.0) for i in range(40)]
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=("Solar8000/CVP", cvp)), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=cvp):
            from vitaldb_aki.features.venous_congestion import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"9": {"caseid": "9", "anestart": 0.0, "opend": float(40 * 60)}}
            result = extract(cfg, cases, ["9"])

        row = result["9"]
        self.assertEqual(row["vcong_available"], 1)
        self.assertAlmostEqual(row["vcong_cvp_mean"], 16.0, places=4)
        self.assertAlmostEqual(row["vcong_cvp_max"], 16.0, places=4)
        self.assertAlmostEqual(row["vcong_cvp_above12_frac"], 1.0, places=4)
        self.assertAlmostEqual(row["vcong_cvp_above8_frac"], 1.0, places=4)
        self.assertIsNotNone(row["vcong_cvp_auc_above12"])
        self.assertGreater(row["vcong_cvp_auc_above12"], 0.0)

    def test_missing_case_yields_none_row(self):
        """A caseid absent from cases_by_id => default none-row."""
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.venous_congestion import extract
            result = extract({"data": {"cache_dir": "/tmp"}}, {}, ["404"])
        row = result["404"]
        self.assertEqual(row["vcong_available"], 0)
        self.assertIsNone(row["vcong_cvp_mean"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
