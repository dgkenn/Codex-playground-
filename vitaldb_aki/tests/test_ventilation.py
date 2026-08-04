"""test_ventilation.py -- Offline unit tests for the VILI biomarker family (Sec 7F-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each pure helper is exercised against hand-built series with a KNOWN expected
direction (driving pressure, mechanical power, compliance decline) plus the
clear-positive / clear-negative / empty-input -> None edge cases.

Mirrors tests/test_pfds.py.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_ventilation -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.ventilation import (
    # Module-level constants
    SPECS,
    DRIVING_PRESSURE_HIGH_THR, MECH_POWER_COEF, BASELINE_WINDOW_S,
    PPLAT_MIN, PPLAT_MAX, PEEP_MIN, PEEP_MAX,
    # Pure helpers under test
    _intraop_window,
    _filter_physiologic,
    _clip_to_window,
    _time_weighted_mean,
    _last_val,
    driving_pressure_series,
    series_max,
    fraction_above,
    mech_power_series,
    compliance_decline,
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

    def test_all_comprehensive(self):
        for s in SPECS:
            self.assertEqual(s.fset, "comprehensive", msg=f"{s.name} fset={s.fset!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in ventilation SPECS")

    def test_first_spec_is_availability(self):
        self.assertEqual(SPECS[0].name, "ventilation_available")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "ventilation_available",
            "vent_driving_pressure_mean",
            "vent_driving_pressure_max",
            "vent_driving_pressure_high_frac",
            "vent_mech_power",
            "vent_compliance_mean",
            "vent_compliance_decline",
            "vent_peep_mean",
        }
        self.assertFalse(required - names, f"Missing specs: {required - names}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 8, "Expected exactly 8 ventilation feature specs")


# ===========================================================================
# 2. Generic helpers: window / filter / clip / time-weighted mean / last-val
# ===========================================================================

class TestIntraopWindow(unittest.TestCase):
    def test_anestart_preferred(self):
        ts, te = _intraop_window({"anestart": 10.0, "opstart": 20.0, "opend": 3600.0})
        self.assertEqual((ts, te), (10.0, 3600.0))

    def test_opstart_fallback(self):
        ts, te = _intraop_window({"opstart": 20.0, "opend": 3600.0})
        self.assertEqual((ts, te), (20.0, 3600.0))

    def test_no_opend_gives_none_none(self):
        self.assertEqual(_intraop_window({"anestart": 10.0}), (None, None))


class TestFilterClip(unittest.TestCase):
    def test_filter_drops_out_of_range(self):
        s = [(0.0, 3.0), (1.0, 30.0), (2.0, 70.0)]  # PPLAT gate 5..60
        out = _filter_physiologic(s, PPLAT_MIN, PPLAT_MAX)
        self.assertEqual(out, [(1.0, 30.0)])

    def test_clip_excludes_after_cutoff(self):
        s = [(0.0, 30.0), (100.0, 30.0), (200.0, 30.0)]
        out = _clip_to_window(s, 0.0, 150.0)
        self.assertEqual(out, [(0.0, 30.0), (100.0, 30.0)])
        self.assertTrue(all(t <= 150.0 for t, _ in out), "no sample past cutoff")


class TestTimeWeightedMean(unittest.TestCase):
    def test_constant_series(self):
        s = [(i * 30.0, 12.0) for i in range(10)]
        self.assertAlmostEqual(_time_weighted_mean(s), 12.0, places=6)

    def test_none_when_fewer_than_two(self):
        self.assertIsNone(_time_weighted_mean([(0.0, 12.0)]))
        self.assertIsNone(_time_weighted_mean([]))

    def test_gap_cap_weights_long_gap_like_max_dt(self):
        # Two intervals: a 5 s interval at value 10, then a huge gap (capped to 10 s)
        # at value 20.  Weights: 5 s @ 10, 10 s @ 20 -> mean = (50 + 200)/15.
        s = [(0.0, 10.0), (5.0, 20.0), (10000.0, 99.0)]
        self.assertAlmostEqual(_time_weighted_mean(s), (50.0 + 200.0) / 15.0, places=6)


class TestLastVal(unittest.TestCase):
    def test_holds_most_recent(self):
        s = [(0.0, 5.0), (10.0, 6.0), (20.0, 7.0)]
        self.assertEqual(_last_val(s, 15.0, lookback_s=10.0), 6.0)

    def test_none_before_first(self):
        s = [(10.0, 6.0)]
        self.assertIsNone(_last_val(s, 5.0, lookback_s=10.0))

    def test_none_when_stale(self):
        s = [(0.0, 6.0)]
        self.assertIsNone(_last_val(s, 100.0, lookback_s=10.0),
                          "value older than lookback is stale -> None")


# ===========================================================================
# 3. Driving-pressure series builder (PPLAT - PEEP on PPLAT grid)
# ===========================================================================

class TestDrivingPressureSeries(unittest.TestCase):
    def test_aligned_difference(self):
        # PPLAT=25 throughout, PEEP=5 throughout -> dP = 20 everywhere.
        pplat = [(i * 10.0, 25.0) for i in range(10)]
        peep = [(i * 10.0, 5.0) for i in range(10)]
        dp = driving_pressure_series(pplat, peep)
        self.assertEqual(len(dp), 10)
        for _, v in dp:
            self.assertAlmostEqual(v, 20.0, places=6)

    def test_last_value_hold_alignment(self):
        # PEEP only sampled at t=0 (value 8); PPLAT at t=0 and t=5 (within lookback).
        pplat = [(0.0, 25.0), (5.0, 30.0)]
        peep = [(0.0, 8.0)]
        dp = driving_pressure_series(pplat, peep, lookback_s=10.0)
        self.assertEqual(dp, [(0.0, 17.0), (5.0, 22.0)])

    def test_skips_pplat_with_no_aligned_peep(self):
        # PEEP at t=0 only; second PPLAT at t=100 is past lookback -> skipped.
        pplat = [(0.0, 25.0), (100.0, 25.0)]
        peep = [(0.0, 5.0)]
        dp = driving_pressure_series(pplat, peep, lookback_s=10.0)
        self.assertEqual(dp, [(0.0, 20.0)])

    def test_empty_inputs_give_empty(self):
        self.assertEqual(driving_pressure_series([], [(0.0, 5.0)]), [])
        self.assertEqual(driving_pressure_series([(0.0, 25.0)], []), [])


# ===========================================================================
# 4. series_max / fraction_above
# ===========================================================================

class TestSeriesMax(unittest.TestCase):
    def test_returns_max(self):
        self.assertEqual(series_max([(0.0, 10.0), (1.0, 22.0), (2.0, 15.0)]), 22.0)

    def test_none_when_empty(self):
        self.assertIsNone(series_max([]))


class TestFractionAbove(unittest.TestCase):
    def test_all_above_is_one(self):
        # Clear positive: dP=20 (>= 15) throughout -> high_frac = 1.0
        s = [(i * 10.0, 20.0) for i in range(10)]
        self.assertAlmostEqual(fraction_above(s, DRIVING_PRESSURE_HIGH_THR), 1.0, places=6)

    def test_all_below_is_zero(self):
        # Clear negative: dP=8 (< 15) throughout -> high_frac = 0.0
        s = [(i * 10.0, 8.0) for i in range(10)]
        self.assertAlmostEqual(fraction_above(s, DRIVING_PRESSURE_HIGH_THR), 0.0, places=6)

    def test_half_above(self):
        # First half >=15, second half <15, uniform spacing -> ~0.5.
        s = [(i * 10.0, 20.0 if i < 10 else 8.0) for i in range(20)]
        frac = fraction_above(s, DRIVING_PRESSURE_HIGH_THR)
        self.assertIsNotNone(frac)
        self.assertGreater(frac, 0.4)
        self.assertLess(frac, 0.6)

    def test_none_when_fewer_than_two(self):
        self.assertIsNone(fraction_above([(0.0, 20.0)], DRIVING_PRESSURE_HIGH_THR))
        self.assertIsNone(fraction_above([], DRIVING_PRESSURE_HIGH_THR))


# ===========================================================================
# 5. Mechanical-power series (Gattinoni simplified)
# ===========================================================================

class TestMechPowerSeries(unittest.TestCase):
    def test_known_value(self):
        # RR=12, TV=500 mL (TV_L=0.5), PIP=30, PPLAT=25, PEEP=5 -> dP=20.
        # MP = 0.098 * 12 * 0.5 * (30 - 0.5*20) = 0.098 * 12 * 0.5 * 20 = 11.76 J/min
        pplat = [(0.0, 25.0), (10.0, 25.0)]
        peep = [(0.0, 5.0), (10.0, 5.0)]
        pip = [(0.0, 30.0), (10.0, 30.0)]
        tv = [(0.0, 500.0), (10.0, 500.0)]
        rr = [(0.0, 12.0), (10.0, 12.0)]
        mp = mech_power_series(pplat, peep, pip, tv, rr)
        self.assertEqual(len(mp), 2)
        expected = MECH_POWER_COEF * 12.0 * 0.5 * (30.0 - 0.5 * 20.0)
        for _, v in mp:
            self.assertAlmostEqual(v, expected, places=6)
        self.assertAlmostEqual(mp[0][1], 11.76, places=5)

    def test_higher_power_for_higher_rr(self):
        pplat = [(0.0, 25.0), (10.0, 25.0)]
        peep = [(0.0, 5.0), (10.0, 5.0)]
        pip = [(0.0, 30.0), (10.0, 30.0)]
        tv = [(0.0, 500.0), (10.0, 500.0)]
        rr_low = [(0.0, 8.0), (10.0, 8.0)]
        rr_high = [(0.0, 20.0), (10.0, 20.0)]
        mp_low = mech_power_series(pplat, peep, pip, tv, rr_low)
        mp_high = mech_power_series(pplat, peep, pip, tv, rr_high)
        self.assertGreater(mp_high[0][1], mp_low[0][1],
                           "Higher respiratory rate => higher mechanical power")

    def test_empty_when_any_track_absent(self):
        pplat = [(0.0, 25.0), (10.0, 25.0)]
        peep = [(0.0, 5.0), (10.0, 5.0)]
        pip = [(0.0, 30.0), (10.0, 30.0)]
        tv = [(0.0, 500.0), (10.0, 500.0)]
        # RR absent -> empty
        self.assertEqual(mech_power_series(pplat, peep, pip, tv, []), [])
        # PIP absent -> empty
        self.assertEqual(mech_power_series(pplat, peep, [], tv, [(0.0, 12.0)]), [])


# ===========================================================================
# 6. Compliance decline (baseline vs late)
# ===========================================================================

class TestComplianceDecline(unittest.TestCase):
    def _series(self, baseline_v: float, late_v: float,
                window_s: float = BASELINE_WINDOW_S) -> list:
        # Baseline epoch in first window_s, late epoch in last window_s, separated.
        early = [(i * 30.0, baseline_v) for i in range(int(window_s // 30) + 1)]
        t0_late = window_s + 600.0
        late = [(t0_late + i * 30.0, late_v) for i in range(int(window_s // 30) + 1)]
        return early + late

    def test_positive_decline(self):
        # Clear positive: compliance falls 50 -> 25 => decline = 0.5
        s = self._series(50.0, 25.0)
        d = compliance_decline(s)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.5, places=3)

    def test_no_decline_clamped_to_zero(self):
        # Clear negative: compliance IMPROVES 25 -> 50 => negative -> clamped 0.0
        s = self._series(25.0, 50.0)
        d = compliance_decline(s)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.0, places=6)

    def test_none_when_single_epoch(self):
        # All samples within one window_s span -> only one epoch -> None
        s = [(i * 10.0, 40.0) for i in range(10)]  # spans 90 s < 300 s window
        self.assertIsNone(compliance_decline(s))

    def test_none_when_fewer_than_two_samples(self):
        self.assertIsNone(compliance_decline([(0.0, 40.0)]))

    def test_empty_input_gives_none(self):
        self.assertIsNone(compliance_decline([]))


# ===========================================================================
# 7. Leakage guard: no t > opend allowed
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    """Verify clip removes post-opend samples so they cannot influence stats."""

    def test_driving_pressure_respects_cutoff(self):
        opend_s = 3600.0
        # PPLAT normal (25) up to opend; a spike of 55 STRICTLY after opend
        # (opend itself is inclusive, so start the spike at opend + 30 s).
        pplat_all = ([(i * 30.0, 25.0) for i in range(int(opend_s // 30))]
                     + [(opend_s + (i + 1) * 30.0, 55.0) for i in range(10)])
        peep_all = [(i * 30.0, 5.0) for i in range(int(opend_s // 30) + 20)]

        pplat_clipped = _filter_physiologic(
            _clip_to_window(pplat_all, 0.0, opend_s), PPLAT_MIN, PPLAT_MAX)
        peep_clipped = _filter_physiologic(
            _clip_to_window(peep_all, 0.0, opend_s), PEEP_MIN, PEEP_MAX)

        dp = driving_pressure_series(pplat_clipped, peep_clipped)
        mx = series_max(dp)
        self.assertIsNotNone(mx)
        # Post-opend PPLAT=55 (dP=50) must NOT appear; max dP should be 20.
        self.assertAlmostEqual(mx, 20.0, places=4,
                               msg="Post-opend spike must not leak into driving pressure")


# ===========================================================================
# 8. extract() smoke tests (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """extract() lazy-imports first_available/download_track from
    vitaldb_aki.data.tracks, so we patch at the source module."""

    def test_extract_none_row_when_no_pplat(self):
        """No PPLAT/PEEP => ventilation_available=0, all other features None."""
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]):
            from vitaldb_aki.features.ventilation import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0}}
            result = extract(cfg, cases, ["1"])

            self.assertIn("1", result)
            row = result["1"]
            self.assertEqual(row["ventilation_available"], 0)
            for s in SPECS:
                if s.name != "ventilation_available":
                    self.assertIsNone(row[s.name],
                                      f"{s.name} should be None when no PPLAT/PEEP")

    def test_extract_computes_driving_pressure_with_tracks(self):
        """With PPLAT + PEEP tracks, driving-pressure features are non-None."""
        import importlib
        import unittest.mock as mock

        n = 40
        dt = 60.0
        pplat_track = [(i * dt, 30.0) for i in range(n)]  # PPLAT 30
        peep_track = [(i * dt, 10.0) for i in range(n)]   # PEEP 10 -> dP = 20 (>=15)

        def _first_available(cfg, cid, tnames, **kw):
            if any("PPLAT" in tn for tn in tnames):
                return ("Primus/PPLAT_MBAR", pplat_track)
            if any("PEEP" in tn for tn in tnames):
                return ("Primus/PEEP_MBAR", peep_track)
            return (None, [])

        def _download_track(cfg, cid, tname, **kw):
            return []

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track):
            import vitaldb_aki.features.ventilation as _vent_mod
            importlib.reload(_vent_mod)
            extract = _vent_mod.extract

            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"42": {"caseid": "42", "anestart": 0.0, "opend": float(n * dt)}}
            result = extract(cfg, cases, ["42"])

        self.assertIn("42", result)
        row = result["42"]
        self.assertEqual(row["ventilation_available"], 1)
        # dP = 20 throughout
        self.assertIsNotNone(row["vent_driving_pressure_mean"])
        self.assertAlmostEqual(row["vent_driving_pressure_mean"], 20.0, places=3)
        self.assertAlmostEqual(row["vent_driving_pressure_max"], 20.0, places=3)
        # dP >= 15 always -> high_frac == 1.0
        self.assertAlmostEqual(row["vent_driving_pressure_high_frac"], 1.0, places=4)
        self.assertAlmostEqual(row["vent_peep_mean"], 10.0, places=3)
        # No PIP/TV/RR -> mech power None; no compliance track -> compliance None
        self.assertIsNone(row["vent_mech_power"])
        self.assertIsNone(row["vent_compliance_mean"])
        self.assertIsNone(row["vent_compliance_decline"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
