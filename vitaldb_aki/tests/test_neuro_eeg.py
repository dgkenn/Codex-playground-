"""test_neuro_eeg.py -- Offline unit tests for the neuro-EEG biomarker family (§7-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
The pure helpers (_frac_time_above, _frac_time_below, _time_weighted_mean, _sd)
are tested against hand-built series with KNOWN expected values (a case with
sustained suppression vs none; SEF stats; empty -> None). Mirrors test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_neuro_eeg -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.neuro_eeg import (
    # Module-level constants
    SPECS,
    SR_ANY_THR, DEEP_SUPP_THR, BIS_DEEP_THR, SQI_MIN_THR,
    SR_MIN, SR_MAX, BIS_MIN, BIS_MAX, SEF_MIN, SEF_MAX,
    # Pure helpers
    _frac_time_above,
    _frac_time_below,
    _time_weighted_mean,
    _sd,
    _filter_physiologic,
    _clip_to_window,
    _intraop_window,
    _sqi_gate,
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

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "neuro_available",
                         "First spec must be neuro_available (contract)")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in neuro-EEG SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "neuro_available",
            "neuro_burst_supp_frac",
            "neuro_burst_supp_burden",
            "neuro_deep_supp_frac",
            "neuro_bis_below40_frac",
            "neuro_bis_mean",
            "neuro_bis_variability",
            "neuro_sef_mean",
            "neuro_sef_sd",
            "neuro_eeg_embed_available",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing neuro specs: {missing}")

    def test_embedding_feature_is_pk_tier(self):
        embed = [s for s in SPECS if s.name == "neuro_eeg_embed_available"]
        self.assertEqual(len(embed), 1)
        self.assertEqual(embed[0].fset, "pk",
                         "neuro_eeg_embed_available must be in the pk set")

    def test_non_embedding_features_are_comprehensive(self):
        for s in SPECS:
            if s.name != "neuro_eeg_embed_available":
                self.assertEqual(s.fset, "comprehensive",
                                 f"{s.name} should be in the comprehensive set")


# ===========================================================================
# 2. _time_weighted_mean
# ===========================================================================

class TestTimeWeightedMean(unittest.TestCase):
    def test_none_when_too_few_samples(self):
        self.assertIsNone(_time_weighted_mean([]))
        self.assertIsNone(_time_weighted_mean([(0.0, 50.0)]))

    def test_constant_series(self):
        s = [(i * 1.0, 42.0) for i in range(10)]
        self.assertAlmostEqual(_time_weighted_mean(s), 42.0, places=6)

    def test_two_levels_equal_weight(self):
        """Half at 20, half at 80 (equal dt) => mean ~50 over the weighted span."""
        # 5 samples at value 20 then 5 at 80, dt=1s. Forward-dt weights the first
        # 9 intervals: 4 intervals @20, 1 transition interval @20, 4 @80.
        s = [(i * 1.0, 20.0) for i in range(5)] + [(5.0 + i * 1.0, 80.0) for i in range(5)]
        m = _time_weighted_mean(s)
        self.assertIsNotNone(m)
        # 5 intervals weight value 20 (indices 0..4), 4 weight value 80 (5..8)
        # => (5*20 + 4*80) / 9 = (100 + 320)/9 = 46.666...
        self.assertAlmostEqual(m, (5 * 20 + 4 * 80) / 9.0, places=4)

    def test_gap_cap_applied(self):
        """A huge gap is capped at max_dt_s so it cannot dominate the mean."""
        s = [(0.0, 0.0), (1.0, 0.0), (10000.0, 100.0), (10001.0, 100.0)]
        m = _time_weighted_mean(s, max_dt_s=10.0)
        self.assertIsNotNone(m)
        # intervals: (0->1)=1s@0 ; (1->10000) capped 10s@0 ; (10000->10001)=1s@100
        # => (1*0 + 10*0 + 1*100) / 12 = 8.333
        self.assertAlmostEqual(m, 100.0 / 12.0, places=4)


# ===========================================================================
# 3. _frac_time_above (the suppression-fraction primitive)
# ===========================================================================

class TestFracTimeAbove(unittest.TestCase):
    def test_none_when_too_few_samples(self):
        self.assertIsNone(_frac_time_above([], SR_ANY_THR))
        self.assertIsNone(_frac_time_above([(0.0, 50.0)], SR_ANY_THR))

    def test_sustained_suppression_all_above_zero(self):
        """SR>0 the entire case => burst-supp fraction ~1.0."""
        sr = [(i * 1.0, 25.0) for i in range(20)]  # SR=25% throughout
        frac = _frac_time_above(sr, SR_ANY_THR)  # thr=0, strict >
        self.assertIsNotNone(frac)
        self.assertAlmostEqual(frac, 1.0, places=6)

    def test_no_suppression_all_zero(self):
        """SR==0 throughout => fraction above 0 is 0.0 (NOT None)."""
        sr = [(i * 1.0, 0.0) for i in range(20)]
        frac = _frac_time_above(sr, SR_ANY_THR)
        self.assertIsNotNone(frac)
        self.assertAlmostEqual(frac, 0.0, places=6)

    def test_half_suppression(self):
        """First half SR>0, second half SR==0 => fraction ~0.5."""
        sr = [(i * 1.0, 30.0) for i in range(10)] + [(10.0 + i * 1.0, 0.0) for i in range(10)]
        frac = _frac_time_above(sr, SR_ANY_THR)
        self.assertIsNotNone(frac)
        # 10 intervals above (indices 0..9), 9 intervals at 0 (10..18) => 10/19
        self.assertAlmostEqual(frac, 10.0 / 19.0, places=4)

    def test_inclusive_deep_suppression_threshold(self):
        """SR>=10 with inclusive flag: a series exactly at 10 counts fully."""
        sr = [(i * 1.0, 10.0) for i in range(20)]
        frac_incl = _frac_time_above(sr, DEEP_SUPP_THR, inclusive=True)
        self.assertAlmostEqual(frac_incl, 1.0, places=6)
        # strict > 10 would exclude the boundary
        frac_strict = _frac_time_above(sr, DEEP_SUPP_THR, inclusive=False)
        self.assertAlmostEqual(frac_strict, 0.0, places=6)

    def test_deep_vs_any_ordering(self):
        """deep_supp_frac (SR>=10) <= burst_supp_frac (SR>0) for the same series."""
        # Mix: some samples 5% (any but not deep), some 30% (both)
        sr = [(i * 1.0, 5.0 if i % 2 == 0 else 30.0) for i in range(20)]
        any_frac = _frac_time_above(sr, SR_ANY_THR)
        deep_frac = _frac_time_above(sr, DEEP_SUPP_THR, inclusive=True)
        self.assertIsNotNone(any_frac)
        self.assertIsNotNone(deep_frac)
        self.assertGreaterEqual(any_frac, deep_frac)
        self.assertGreater(any_frac, deep_frac)  # 5% counts for any, not deep


# ===========================================================================
# 4. _frac_time_below (deep-hypnosis BIS<40 primitive)
# ===========================================================================

class TestFracTimeBelow(unittest.TestCase):
    def test_none_when_too_few_samples(self):
        self.assertIsNone(_frac_time_below([], BIS_DEEP_THR))
        self.assertIsNone(_frac_time_below([(0.0, 30.0)], BIS_DEEP_THR))

    def test_all_below_threshold(self):
        """BIS=30 throughout (<40) => fraction below ~1.0."""
        bis = [(i * 1.0, 30.0) for i in range(20)]
        frac = _frac_time_below(bis, BIS_DEEP_THR)
        self.assertAlmostEqual(frac, 1.0, places=6)

    def test_none_below_when_all_adequate(self):
        """BIS=50 throughout (>=40) => fraction below is 0.0 (NOT None)."""
        bis = [(i * 1.0, 50.0) for i in range(20)]
        frac = _frac_time_below(bis, BIS_DEEP_THR)
        self.assertIsNotNone(frac)
        self.assertAlmostEqual(frac, 0.0, places=6)

    def test_boundary_excluded(self):
        """BIS exactly 40 is NOT < 40 => fraction below is 0."""
        bis = [(i * 1.0, 40.0) for i in range(20)]
        frac = _frac_time_below(bis, BIS_DEEP_THR)
        self.assertAlmostEqual(frac, 0.0, places=6)


# ===========================================================================
# 5. _sd (instability primitive; SEF / BIS variability)
# ===========================================================================

class TestSd(unittest.TestCase):
    def test_none_when_too_few_samples(self):
        self.assertIsNone(_sd([]))
        self.assertIsNone(_sd([(0.0, 13.0)]))

    def test_zero_for_constant(self):
        s = [(i * 1.0, 13.0) for i in range(10)]
        self.assertAlmostEqual(_sd(s), 0.0, places=6)

    def test_known_sd(self):
        """Values [2, 4, 4, 4, 5, 5, 7, 9] have sample SD = sqrt(32/7)."""
        vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        s = [(i * 1.0, v) for i, v in enumerate(vals)]
        expected = (32.0 / 7.0) ** 0.5  # = 2.13808...
        self.assertAlmostEqual(_sd(s), round(expected, 6), places=5)

    def test_sef_stats_combined(self):
        """A SEF series: mean and SD are both computable and physiologic."""
        sef = [(i * 1.0, 12.0 + (i % 4)) for i in range(20)]  # SEF wobbling 12..15 Hz
        m = _time_weighted_mean(sef)
        sd = _sd(sef)
        self.assertIsNotNone(m)
        self.assertIsNotNone(sd)
        self.assertGreater(m, SEF_MIN)
        self.assertLess(m, SEF_MAX)
        self.assertGreater(sd, 0.0)  # there IS spectral wobble


# ===========================================================================
# 6. Suppression vs none -- the headline biomarker contrast
# ===========================================================================

class TestSuppressionContrast(unittest.TestCase):
    """A case with sustained suppression vs a case with none."""

    def test_sustained_suppression_case(self):
        # Deep, sustained suppression: SR=40% throughout
        sr = [(i * 1.0, 40.0) for i in range(60)]
        burst_frac = _frac_time_above(sr, SR_ANY_THR)
        burden = _time_weighted_mean(sr)
        deep_frac = _frac_time_above(sr, DEEP_SUPP_THR, inclusive=True)
        self.assertAlmostEqual(burst_frac, 1.0, places=6)
        self.assertAlmostEqual(burden, 40.0, places=4)
        self.assertAlmostEqual(deep_frac, 1.0, places=6)

    def test_no_suppression_case(self):
        # No suppression at all: SR=0% throughout
        sr = [(i * 1.0, 0.0) for i in range(60)]
        burst_frac = _frac_time_above(sr, SR_ANY_THR)
        burden = _time_weighted_mean(sr)
        deep_frac = _frac_time_above(sr, DEEP_SUPP_THR, inclusive=True)
        self.assertAlmostEqual(burst_frac, 0.0, places=6)
        self.assertAlmostEqual(burden, 0.0, places=6)
        self.assertAlmostEqual(deep_frac, 0.0, places=6)

    def test_suppressed_case_has_higher_burden(self):
        sr_supp = [(i * 1.0, 40.0) for i in range(60)]
        sr_none = [(i * 1.0, 0.0) for i in range(60)]
        self.assertGreater(
            _time_weighted_mean(sr_supp), _time_weighted_mean(sr_none)
        )


# ===========================================================================
# 7. Range gates and window helpers (mirrors pfds usage)
# ===========================================================================

class TestGatesAndWindow(unittest.TestCase):
    def test_filter_physiologic_sr(self):
        s = [(0.0, -5.0), (1.0, 50.0), (2.0, 150.0), (3.0, 100.0)]
        kept = _filter_physiologic(s, SR_MIN, SR_MAX)
        self.assertEqual(kept, [(1.0, 50.0), (3.0, 100.0)])

    def test_filter_physiologic_sef(self):
        """SEF gate is 0..30 Hz; a 99 Hz artifact is dropped."""
        s = [(0.0, 12.0), (1.0, 99.0), (2.0, 8.0)]
        kept = _filter_physiologic(s, SEF_MIN, SEF_MAX)
        self.assertEqual(kept, [(0.0, 12.0), (2.0, 8.0)])

    def test_clip_to_window_respects_opend(self):
        """No sample at t > t_end (the leakage cutoff) survives clipping."""
        s = [(i * 10.0, 50.0) for i in range(20)]  # t in [0, 190]
        clipped = _clip_to_window(s, 0.0, 100.0)
        self.assertTrue(all(t <= 100.0 for t, _ in clipped))
        self.assertFalse(any(t > 100.0 for t, _ in clipped))

    def test_intraop_window_priority(self):
        case = {"opend": 3600.0, "anestart": 60.0, "opstart": 120.0}
        self.assertEqual(_intraop_window(case), (60.0, 3600.0))

    def test_intraop_window_falls_back_to_opstart(self):
        case = {"opend": 3600.0, "opstart": 120.0}
        self.assertEqual(_intraop_window(case), (120.0, 3600.0))

    def test_intraop_window_none_without_opend(self):
        self.assertEqual(_intraop_window({"anestart": 0.0}), (None, None))


# ===========================================================================
# 8. SQI gating
# ===========================================================================

class TestSqiGate(unittest.TestCase):
    def test_no_sqi_keeps_all(self):
        s = [(i * 1.0, 25.0) for i in range(5)]
        self.assertEqual(_sqi_gate(s, []), s)

    def test_low_sqi_drops_samples(self):
        """Samples whose preceding SQI < 50 are dropped."""
        s = [(0.0, 25.0), (1.0, 25.0), (2.0, 25.0)]
        # SQI good at t=0 (90), poor from t=1 (10)
        sqi = [(0.0, 90.0), (1.0, 10.0)]
        kept = _sqi_gate(s, sqi)
        # t=0 -> sqi 90 (keep); t=1 -> sqi 10 (drop); t=2 -> sqi 10 (drop)
        self.assertEqual(kept, [(0.0, 25.0)])

    def test_high_sqi_keeps_all(self):
        s = [(i * 1.0, 25.0) for i in range(3)]
        sqi = [(i * 1.0, 95.0) for i in range(3)]
        self.assertEqual(_sqi_gate(s, sqi), s)


# ===========================================================================
# 9. extract() smoke tests (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """extract() lazy-imports download_track/first_available/tid_for from
    vitaldb_aki.data.tracks, so we patch at the source module."""

    def test_extract_none_row_when_no_bis(self):
        """No SR and no BIS track => neuro_available=0, all others None."""
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.download_track", return_value=[]), \
             mock.patch("vitaldb_aki.data.tracks.first_available", return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.tid_for", return_value=None):
            from vitaldb_aki.features.neuro_eeg import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])

        self.assertIn("1", result)
        row = result["1"]
        self.assertEqual(row["neuro_available"], 0)
        self.assertEqual(row["neuro_eeg_embed_available"], 0)
        for s in SPECS:
            if s.name not in ("neuro_available", "neuro_eeg_embed_available"):
                self.assertIsNone(row[s.name], f"{s.name} should be None when no BIS")

    def test_extract_computes_features_with_tracks(self):
        """With SR + BIS + SEF tracks, features are non-None and correct-direction."""
        import unittest.mock as mock

        n = 60
        dt = 5.0
        sr_track = [(i * dt, 40.0) for i in range(n)]   # sustained suppression
        bis_track = [(i * dt, 30.0) for i in range(n)]  # deep hypnosis (<40)
        sef_track = [(i * dt, 12.0) for i in range(n)]  # SEF 12 Hz

        def _download_track(cfg, cid, tname, **kw):
            if tname == "BIS/SR":
                return sr_track
            if tname == "BIS/BIS":
                return bis_track
            if tname == "BIS/SEF":
                return sef_track
            return []  # no SQI, no raw EEG

        with mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track), \
             mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.tid_for", return_value=None):
            import importlib
            import vitaldb_aki.features.neuro_eeg as _mod
            importlib.reload(_mod)
            extract = _mod.extract

            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(n * dt)}}
            result = extract(cfg, cases, ["42"])

        row = result["42"]
        self.assertEqual(row["neuro_available"], 1)
        self.assertAlmostEqual(row["neuro_burst_supp_frac"], 1.0, places=4)
        self.assertAlmostEqual(row["neuro_burst_supp_burden"], 40.0, places=2)
        self.assertAlmostEqual(row["neuro_deep_supp_frac"], 1.0, places=4)
        self.assertAlmostEqual(row["neuro_bis_below40_frac"], 1.0, places=4)
        self.assertAlmostEqual(row["neuro_bis_mean"], 30.0, places=2)
        self.assertAlmostEqual(row["neuro_bis_variability"], 0.0, places=4)
        self.assertAlmostEqual(row["neuro_sef_mean"], 12.0, places=2)
        self.assertAlmostEqual(row["neuro_sef_sd"], 0.0, places=4)
        # Embedding off by default
        self.assertEqual(row["neuro_eeg_embed_available"], 0)

    def test_embedding_flag_off_by_default(self):
        """Even with a raw EEG track present, flag stays 0 unless cfg opts in."""
        import unittest.mock as mock

        n = 20
        sr_track = [(i * 5.0, 10.0) for i in range(n)]

        def _download_track(cfg, cid, tname, **kw):
            return sr_track if tname == "BIS/SR" else []

        with mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track), \
             mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.tid_for", return_value="tid_eeg1"):
            import importlib
            import vitaldb_aki.features.neuro_eeg as _mod
            importlib.reload(_mod)
            extract = _mod.extract

            cfg = {"data": {"cache_dir": "/tmp"}}  # no features.neuro_eeg_embedding
            cases = {"7": {"caseid": "7", "anestart": 0.0, "opend": 100.0}}
            result = extract(cfg, cases, ["7"])

        self.assertEqual(result["7"]["neuro_eeg_embed_available"], 0,
                         "Embedding flag must stay 0 on the default path")

    def test_embedding_flag_set_when_opted_in_and_track_exists(self):
        """cfg flag True + raw EEG track present => flag becomes 1 (stub)."""
        import unittest.mock as mock

        n = 20
        sr_track = [(i * 5.0, 10.0) for i in range(n)]

        def _download_track(cfg, cid, tname, **kw):
            return sr_track if tname == "BIS/SR" else []

        with mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track), \
             mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.tid_for", return_value="tid_eeg1"):
            import importlib
            import vitaldb_aki.features.neuro_eeg as _mod
            importlib.reload(_mod)
            extract = _mod.extract

            cfg = {"data": {"cache_dir": "/tmp"},
                   "features": {"neuro_eeg_embedding": True}}
            cases = {"7": {"caseid": "7", "anestart": 0.0, "opend": 100.0}}
            result = extract(cfg, cases, ["7"])

        self.assertEqual(result["7"]["neuro_eeg_embed_available"], 1,
                         "Flag should be 1 when opted-in AND raw track exists")

    def test_leakage_no_sample_beyond_opend(self):
        """Samples beyond opend must not influence burst-supp burden."""
        import unittest.mock as mock

        opend_s = 300.0
        # SR=0 within window, then SR=80 ONLY after opend
        sr_in = [(i * 5.0, 0.0) for i in range(int(opend_s // 5))]
        sr_post = [(opend_s + 5.0 + i * 5.0, 80.0) for i in range(20)]
        sr_track = sr_in + sr_post

        def _download_track(cfg, cid, tname, **kw):
            return sr_track if tname == "BIS/SR" else []

        with mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track), \
             mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.tid_for", return_value=None):
            import importlib
            import vitaldb_aki.features.neuro_eeg as _mod
            importlib.reload(_mod)
            extract = _mod.extract

            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"5": {"caseid": "5", "anestart": 0.0, "opend": opend_s}}
            result = extract(cfg, cases, ["5"])

        row = result["5"]
        self.assertEqual(row["neuro_available"], 1)
        # Post-opend SR=80 is clipped out => burden stays 0, burst frac 0
        self.assertAlmostEqual(row["neuro_burst_supp_burden"], 0.0, places=4)
        self.assertAlmostEqual(row["neuro_burst_supp_frac"], 0.0, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
