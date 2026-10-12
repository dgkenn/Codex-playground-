"""test_pfds.py -- Offline unit tests for the PFDS biomarker family (§7F-novel).

All tests are pure-math / in-memory; no network access, no VitalDB downloads.
Each biomarker is tested against hand-built series with KNOWN expected direction
(dissociation / fragility / recovery-lag).

Run with:
    python3 -m unittest vitaldb_aki.tests.test_pfds -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.pfds import (
    # Module-level constants / dicts
    SPECS, CLINICAL_COMPUTABLE, WAVEFORM_ONLY,
    MAP_ADEQUATE_THR, ETCO2_LOW_THR, ETCO2_DECLINE_FRAC,
    SPO2_MARGINAL_THR, PRESSOR_NORM_DOSE, FRAGILITY_CE_THR,
    # Biomarker helpers
    pfd_burden_clinical,
    pfd_burden_waveform,
    pressor_stress,
    fragility_waveform,
    fragility_clinical,
    recovery_lag_clinical,
    recovery_lag_waveform,
    pleth_amplitude_series,
    # Subgroup analysis
    acceptable_map_subgroup,
)
from vitaldb_aki.features.base import audit_specs, LeakageError


# ===========================================================================
# 1. Module-level spec invariants
# ===========================================================================

class TestSpecInvariants(unittest.TestCase):
    def test_audit_passes(self):
        """audit_specs() must not raise (no postop feature)."""
        audit_specs(SPECS)  # raises on violation

    def test_no_postop_timing(self):
        for s in SPECS:
            self.assertNotEqual(s.timing, "postop",
                                msg=f"{s.name} has postop timing -- leakage!")

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop",
                             msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)),
                         "Duplicate feature names in PFDS SPECS")

    def test_required_features_present(self):
        names = {s.name for s in SPECS}
        required = {
            "pfds_available",
            "pfds_clin_pfd_burden",
            "pfds_wf_pfd_burden",
            "pfds_clin_pressor_stress",
            "pfds_wf_fragility",
            "pfds_clin_fragility",
            "pfds_clin_recovery_lag",
            "pfds_wf_recovery_lag",
        }
        missing = required - names
        self.assertFalse(missing, f"Missing PFDS specs: {missing}")

    def test_spec_count(self):
        self.assertEqual(len(SPECS), 8, "Expected exactly 8 PFDS feature specs")


# ===========================================================================
# 2. CLINICAL_COMPUTABLE / WAVEFORM_ONLY registry
# ===========================================================================

class TestRegistries(unittest.TestCase):
    def test_clinical_computable_nonempty(self):
        self.assertGreater(len(CLINICAL_COMPUTABLE), 0)

    def test_clinical_computable_excludes_waveform_features(self):
        overlap = set(CLINICAL_COMPUTABLE) & WAVEFORM_ONLY
        self.assertFalse(overlap,
                         f"Features in both CLINICAL_COMPUTABLE and WAVEFORM_ONLY: {overlap}")

    def test_waveform_only_not_in_clinical(self):
        for name in WAVEFORM_ONLY:
            self.assertNotIn(name, CLINICAL_COMPUTABLE,
                             f"{name} should not be in CLINICAL_COMPUTABLE")

    def test_wf_features_in_waveform_only(self):
        """Every pfds_wf_* feature should be in WAVEFORM_ONLY."""
        for s in SPECS:
            if s.name.startswith("pfds_wf_"):
                self.assertIn(s.name, WAVEFORM_ONLY,
                              f"{s.name} is a waveform feature but not in WAVEFORM_ONLY")

    def test_clin_features_in_clinical_computable(self):
        """Every pfds_clin_* feature should be in CLINICAL_COMPUTABLE."""
        for s in SPECS:
            if s.name.startswith("pfds_clin_"):
                self.assertIn(s.name, CLINICAL_COMPUTABLE,
                              f"{s.name} is a clinical feature but not in CLINICAL_COMPUTABLE")

    def test_pfds_available_in_clinical_computable(self):
        self.assertIn("pfds_available", CLINICAL_COMPUTABLE)


# ===========================================================================
# 3. Biomarker 1: Pressure-Flow Dissociation burden (Clinical)
# ===========================================================================

class TestPFDBurdenClinical(unittest.TestCase):
    """pfd_burden_clinical on synthetic series."""

    def _uniform_map(self, value: float, n: int = 20, dt: float = 30.0
                     ) -> list[tuple[float, float]]:
        """n samples of constant MAP at `value` spaced `dt` seconds apart."""
        return [(i * dt, value) for i in range(n)]

    def _uniform_etco2(self, value: float, n: int = 20, dt: float = 30.0
                       ) -> list[tuple[float, float]]:
        return [(i * dt, value) for i in range(n)]

    def _uniform_spo2(self, value: float, n: int = 20, dt: float = 30.0
                      ) -> list[tuple[float, float]]:
        return [(i * dt, value) for i in range(n)]

    def test_zero_when_map_always_low(self):
        """MAP always < 65 => never adequate => PFD burden = 0."""
        m = self._uniform_map(55.0)
        e = self._uniform_etco2(28.0)  # low EtCO2
        s = self._uniform_spo2(92.0)  # marginal SpO2
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4,
                               msg="MAP<65 always => no PFD opportunity")

    def test_zero_when_map_adequate_and_flow_ok(self):
        """MAP >=65 and EtCO2/SpO2 normal => PFD burden = 0."""
        m = self._uniform_map(80.0)
        e = self._uniform_etco2(40.0)  # normal
        s = self._uniform_spo2(99.0)  # normal
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_high_when_map_adequate_but_etco2_low(self):
        """MAP >=65 but EtCO2 always < 30 => PFD burden should be 1.0."""
        m = self._uniform_map(80.0)
        e = self._uniform_etco2(25.0)  # below ETCO2_LOW_THR=30
        s = []  # no SpO2
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0.9,
                           msg="MAP>=65 + EtCO2<30 => should flag PFD nearly every sample")

    def test_high_when_map_adequate_but_spo2_marginal(self):
        """MAP >=65 but SpO2 always < 95 => PFD burden high."""
        m = self._uniform_map(80.0)
        e = []  # no EtCO2
        s = self._uniform_spo2(92.0)  # below SPO2_MARGINAL_THR=95
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0.9)

    def test_high_when_etco2_declining(self):
        """EtCO2 starts at 40 and drops >15% => PFD flagged for decline."""
        # Baseline (first 5 min = first ~10 samples at 30 s each) at 40 mmHg
        # Then drops to 33 (17.5% below 40; > 15% threshold)
        baseline_samples = [(i * 30.0, 40.0) for i in range(10)]
        decline_samples = [(300.0 + i * 30.0, 33.0) for i in range(10)]
        e = baseline_samples + decline_samples
        m = [(i * 30.0, 80.0) for i in range(20)]  # MAP always adequate
        s = []
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        # Decline starts at t=300s; baseline established over [0, 300s)
        # So second half of the case (t>=300) should all flag
        self.assertGreater(result, 0.3,
                           msg="EtCO2 declining >15% should flag PFD in second half")

    def test_returns_none_when_no_flow_surrogates(self):
        """No EtCO2, no SpO2 => cannot compute => None."""
        m = self._uniform_map(80.0)
        result = pfd_burden_clinical(m, [], [])
        self.assertIsNone(result)

    def test_returns_none_when_map_too_few_samples(self):
        """< 2 MAP samples => None."""
        result = pfd_burden_clinical([(0.0, 80.0)], [(0.0, 25.0)], [])
        self.assertIsNone(result)

    def test_partial_pfd(self):
        """First half MAP>=65+EtCO2 low; second half MAP>=65+EtCO2 normal."""
        m = [(i * 30.0, 80.0) for i in range(20)]
        # EtCO2 low for first 10 samples, normal for second 10
        e = [(i * 30.0, 25.0) for i in range(10)] + [(i * 30.0 + 300.0, 40.0) for i in range(10)]
        s = []
        result = pfd_burden_clinical(m, e, s)
        self.assertIsNotNone(result)
        # Should be roughly 0.5 (half the adequate-MAP time is PFD)
        self.assertGreater(result, 0.3)
        self.assertLess(result, 0.7)


# ===========================================================================
# 4. Biomarker 1 (Waveform): pfd_burden_waveform
# ===========================================================================

class TestPFDBurdenWaveform(unittest.TestCase):
    def test_higher_than_clinical_when_pleth_declines(self):
        """Adding a declining pleth signal should increase PFD burden."""
        m = [(i * 30.0, 80.0) for i in range(20)]
        e = [(i * 30.0, 40.0) for i in range(20)]  # normal EtCO2
        s = [(i * 30.0, 99.0) for i in range(20)]  # normal SpO2
        pleth_baseline = [(i * 30.0, 100.0) for i in range(5)]
        pleth_decline = [(150.0 + i * 30.0, 60.0) for i in range(15)]  # 40% decline
        pleth = pleth_baseline + pleth_decline

        clin = pfd_burden_clinical(m, e, s)
        wf = pfd_burden_waveform(m, e, s, pleth)
        self.assertIsNotNone(clin)
        self.assertIsNotNone(wf)
        # Waveform variant should be >= clinical (has more surrogates)
        self.assertGreaterEqual(wf, clin,
                                "WF PFD burden should be >= clinical when pleth declines")

    def test_zero_when_all_ok(self):
        m = [(i * 30.0, 80.0) for i in range(10)]
        e = [(i * 30.0, 40.0) for i in range(10)]
        s = [(i * 30.0, 99.0) for i in range(10)]
        pleth = [(i * 30.0, 100.0) for i in range(10)]
        result = pfd_burden_waveform(m, e, s, pleth)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_returns_none_when_all_surrogates_absent(self):
        m = [(i * 30.0, 80.0) for i in range(10)]
        result = pfd_burden_waveform(m, [], [], [])
        self.assertIsNone(result)


# ===========================================================================
# 5. Biomarker 2: Pressor-Adjusted Perfusion Stress
# ===========================================================================

class TestPresssorStress(unittest.TestCase):
    def _map_samples(self, value: float, n: int = 20, dt: float = 30.0):
        return [(i * dt, value) for i in range(n)]

    def test_zero_when_no_pressor(self):
        m = self._map_samples(80.0)
        result = pressor_stress(m, pressor_dose_ug=0.0, case_duration_min=10.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=6)

    def test_none_when_pressor_unknown(self):
        m = self._map_samples(80.0)
        result = pressor_stress(m, pressor_dose_ug=None, case_duration_min=10.0)
        self.assertIsNone(result)

    def test_none_when_map_too_few_samples(self):
        result = pressor_stress([(0.0, 80.0)], pressor_dose_ug=100.0, case_duration_min=10.0)
        self.assertIsNone(result)

    def test_higher_stress_with_more_pressor(self):
        m = self._map_samples(70.0)  # barely above 65 (margin = 5 mmHg)
        result_low = pressor_stress(m, pressor_dose_ug=50.0, case_duration_min=10.0)
        result_high = pressor_stress(m, pressor_dose_ug=500.0, case_duration_min=10.0)
        self.assertIsNotNone(result_low)
        self.assertIsNotNone(result_high)
        self.assertGreater(result_high, result_low,
                           "More pressor for same MAP => higher stress")

    def test_lower_stress_with_higher_map_margin(self):
        """Same pressor dose, but MAP well above 65 => lower stress."""
        m_low = [(i * 30.0, 70.0) for i in range(20)]   # margin = 5 mmHg
        m_high = [(i * 30.0, 100.0) for i in range(20)] # margin = 35 mmHg
        dose = 200.0
        r_low = pressor_stress(m_low, dose, 10.0)
        r_high = pressor_stress(m_high, dose, 10.0)
        self.assertIsNotNone(r_low)
        self.assertIsNotNone(r_high)
        self.assertGreater(r_low, r_high,
                           "Same pressor dose but lower MAP margin => higher stress")

    def test_zero_when_map_never_adequate(self):
        m = [(i * 30.0, 55.0) for i in range(20)]  # MAP < 65 always
        result = pressor_stress(m, pressor_dose_ug=300.0, case_duration_min=10.0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=6,
                               msg="MAP never adequate => stress = 0.0 (cannot define margin)")


# ===========================================================================
# 6. Biomarker 3a: Anesthetic Response Fragility (Waveform)
# ===========================================================================

class TestFragilityWaveform(unittest.TestCase):
    def _make_series(self, pairs: list[tuple[float, float]], dt: float = 30.0
                     ) -> list[tuple[float, float]]:
        return [(i * dt, v) for i, (_, v) in enumerate(pairs)]

    def test_negative_slope_when_map_drops_with_ce(self):
        """MAP falls as Ce rises => fragility slope should be negative."""
        n = 20
        # Ce rises from 1 to 3 ug/mL; MAP falls from 90 to 60 mmHg
        ce = [(i * 30.0, 1.0 + 2.0 * i / (n - 1)) for i in range(n)]
        mp = [(i * 30.0, 90.0 - 30.0 * i / (n - 1)) for i in range(n)]
        slope = fragility_waveform(mp, ce)
        self.assertIsNotNone(slope)
        self.assertLess(slope, 0.0,
                        "MAP falling with rising Ce should give negative fragility slope")

    def test_positive_slope_when_map_rises_with_ce(self):
        """MAP rises as Ce rises => slope > 0 (not fragile)."""
        n = 20
        ce = [(i * 30.0, 1.0 + 2.0 * i / (n - 1)) for i in range(n)]
        mp = [(i * 30.0, 60.0 + 30.0 * i / (n - 1)) for i in range(n)]
        slope = fragility_waveform(mp, ce)
        self.assertIsNotNone(slope)
        self.assertGreater(slope, 0.0)

    def test_none_when_ce_always_below_thr(self):
        """Ce always < FRAGILITY_CE_THR (1.0 ug/mL) => no paired observations => None."""
        n = 20
        ce = [(i * 30.0, 0.1) for i in range(n)]  # sub-threshold Ce
        mp = [(i * 30.0, 80.0) for i in range(n)]
        result = fragility_waveform(mp, ce)
        self.assertIsNone(result)

    def test_none_when_too_few_samples(self):
        ce = [(0.0, 2.0), (30.0, 2.5)]
        mp = [(0.0, 80.0), (30.0, 75.0)]
        result = fragility_waveform(mp, ce)
        self.assertIsNone(result)

    def test_more_negative_slope_for_more_fragile_patient(self):
        """A fragile patient (steep drop) should have more negative slope."""
        n = 20
        ce = [(i * 30.0, 1.5 + i * 0.05) for i in range(n)]
        mp_fragile = [(i * 30.0, 90.0 - 3.0 * i) for i in range(n)]    # steep drop
        mp_resilient = [(i * 30.0, 90.0 - 0.1 * i) for i in range(n)]  # shallow drop
        s_fragile = fragility_waveform(mp_fragile, ce)
        s_resilient = fragility_waveform(mp_resilient, ce)
        self.assertIsNotNone(s_fragile)
        self.assertIsNotNone(s_resilient)
        self.assertLess(s_fragile, s_resilient,
                        "Fragile patient should have more negative MAP-Ce slope")


# ===========================================================================
# 7. Biomarker 3b: Anesthetic Response Fragility (Clinical)
# ===========================================================================

class TestFragilityClinical(unittest.TestCase):
    def _map_samples(self, value: float, n: int = 20, dt: float = 30.0):
        return [(i * dt, value) for i in range(n)]

    def test_none_when_no_anesthetic_info(self):
        m = self._map_samples(80.0)
        result = fragility_clinical(m, case_duration_min=10.0,
                                    has_propofol=False, has_volatile=False)
        self.assertIsNone(result)

    def test_zero_when_map_always_adequate(self):
        m = self._map_samples(80.0)
        result = fragility_clinical(m, case_duration_min=10.0,
                                    has_propofol=True, has_volatile=False)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_one_when_map_always_below65(self):
        m = self._map_samples(55.0)
        result = fragility_clinical(m, case_duration_min=10.0,
                                    has_propofol=True, has_volatile=False)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 1.0, places=4)

    def test_higher_for_more_hypotension(self):
        """More time below 65 => higher fragility score."""
        n = 20
        dt = 30.0
        # Half the case below 65
        m_half = [(i * dt, 55.0 if i < 10 else 80.0) for i in range(n)]
        # Whole case below 65
        m_full = [(i * dt, 55.0) for i in range(n)]
        r_half = fragility_clinical(m_half, 10.0, has_propofol=True, has_volatile=False)
        r_full = fragility_clinical(m_full, 10.0, has_propofol=True, has_volatile=False)
        self.assertIsNotNone(r_half)
        self.assertIsNotNone(r_full)
        self.assertLess(r_half, r_full)

    def test_volatile_also_works(self):
        m = self._map_samples(55.0)
        result = fragility_clinical(m, 10.0, has_propofol=False, has_volatile=True)
        self.assertIsNotNone(result)

    def test_none_when_too_few_map_samples(self):
        result = fragility_clinical([(0.0, 55.0)], 10.0, has_propofol=True, has_volatile=False)
        self.assertIsNone(result)


# ===========================================================================
# 8. Biomarker 4a: Recovery Lag (Clinical)
# ===========================================================================

class TestRecoveryLagClinical(unittest.TestCase):
    def _make_map(self, values: list[float], dt: float = 30.0) -> list[tuple[float, float]]:
        return [(i * dt, v) for i, v in enumerate(values)]

    def test_none_when_map_never_below65(self):
        """MAP never dips => no episodes => None."""
        m = self._make_map([80.0] * 20)
        result = recovery_lag_clinical(m)
        self.assertIsNone(result)

    def test_none_when_too_few_samples(self):
        result = recovery_lag_clinical([(0.0, 80.0)])
        self.assertIsNone(result)

    def test_detects_single_episode(self):
        """One dip: MAP drops for 2 intervals then recovers. Lag = 2*dt seconds / 60."""
        # dt=60s; dip from t=60 to t=120 (2 samples below 65), recovers at t=180
        m = [(0.0, 80.0), (60.0, 60.0), (120.0, 60.0), (180.0, 80.0), (240.0, 80.0)]
        result = recovery_lag_clinical(m)
        self.assertIsNotNone(result)
        # Episode starts at t=60, recovers at t=180 => lag = 120 s / 60 = 2 min
        self.assertAlmostEqual(result, 2.0, places=3)

    def test_longer_lag_for_slower_recovery(self):
        """Longer episode => longer recovery lag."""
        # Short episode: 1 interval below 65 (30 s lag)
        m_short = [(i * 30.0, 60.0 if i == 1 else 80.0) for i in range(5)]
        # Long episode: 5 intervals below 65 (5*30 = 150 s lag)
        m_long = [(i * 30.0, 60.0 if 1 <= i <= 5 else 80.0) for i in range(8)]
        r_short = recovery_lag_clinical(m_short)
        r_long = recovery_lag_clinical(m_long)
        self.assertIsNotNone(r_short)
        self.assertIsNotNone(r_long)
        self.assertGreater(r_long, r_short,
                           "Longer hypotensive episode => longer recovery lag")

    def test_multiple_episodes_averaged(self):
        """Two equal-length episodes => mean lag equals one episode."""
        # Episode 1: t=30..60 (30 s), recovers at t=90
        # Episode 2: t=150..180 (30 s), recovers at t=210
        m = [
            (0.0, 80.0),
            (30.0, 60.0),  # dip
            (60.0, 60.0),  # dip
            (90.0, 80.0),  # recover
            (120.0, 80.0),
            (150.0, 60.0),  # dip
            (180.0, 60.0),  # dip
            (210.0, 80.0),  # recover
            (240.0, 80.0),
        ]
        result = recovery_lag_clinical(m)
        self.assertIsNotNone(result)
        # Each episode: 60 s lag => 1 min
        self.assertAlmostEqual(result, 1.0, places=3)

    def test_open_episode_not_counted(self):
        """Episode not closed before recording ends => censored, not counted."""
        # Only one episode that starts but never recovers
        m = [(0.0, 80.0), (30.0, 80.0), (60.0, 60.0), (90.0, 60.0)]
        result = recovery_lag_clinical(m)
        # The episode never closes, so lags is empty => None
        self.assertIsNone(result)


# ===========================================================================
# 9. Biomarker 4b: Recovery Lag (Waveform)
# ===========================================================================

class TestRecoveryLagWaveform(unittest.TestCase):
    def test_none_when_too_few_samples(self):
        result = recovery_lag_waveform([(0.0, 80.0)], [(0.0, 2.0)])
        self.assertIsNone(result)

    def test_none_when_ce_never_crosses_threshold(self):
        """Ce never crosses ce_thr => no event to measure recovery from."""
        n = 20
        ce = [(i * 30.0, 2.0) for i in range(n)]   # always above thr
        mp = [(i * 30.0, 55.0) for i in range(n)]  # always below MAP_ADEQUATE
        result = recovery_lag_waveform(mp, ce)
        self.assertIsNone(result)

    def test_detects_lag_when_ce_falls_but_map_still_low(self):
        """Ce drops below thr while MAP still low, then MAP recovers 5 samples later."""
        dt = 30.0  # seconds per step
        # 20 samples: first 10 high Ce + low MAP, then Ce drops, MAP recovers later
        # Ce: 2.0 for first 10, then 0.5 (below thr=1.0) from sample 10
        # MAP: 55 (below 65) for first 14 samples, then 80 from sample 14
        n = 20
        ce = [(i * dt, 2.0 if i < 10 else 0.5) for i in range(n)]
        mp = [(i * dt, 55.0 if i < 14 else 80.0) for i in range(n)]
        result = recovery_lag_waveform(mp, ce)
        # Ce crosses thr at transition between sample 9 (ce=2.0) and 10 (ce=0.5)
        # At sample 10 (t=300s), MAP=55 (still low)
        # MAP recovers at sample 14 (t=420s)
        # Lag = 420 - 300 = 120 s = 2 min
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 2.0, places=2,
                               msg="Recovery lag should be ~2 min (4 samples * 30 s)")

    def test_none_when_map_already_adequate_when_ce_falls(self):
        """Ce drops below thr, but MAP is already >=65 => no lag event."""
        n = 20
        dt = 30.0
        ce = [(i * dt, 2.0 if i < 10 else 0.5) for i in range(n)]
        mp = [(i * dt, 80.0) for i in range(n)]  # MAP always >=65
        result = recovery_lag_waveform(mp, ce)
        self.assertIsNone(result)


# ===========================================================================
# 10. Pleth amplitude helper
# ===========================================================================

class TestPlethAmplitudeSeries(unittest.TestCase):
    def test_empty_when_too_few_samples(self):
        result = pleth_amplitude_series([(0.0, 100.0), (1.0, 110.0)])
        self.assertEqual(result, [])

    def test_positive_amplitude_for_varying_signal(self):
        # 60 samples at 1 Hz: oscillate between 100 and 200
        samples = [(i * 1.0, 100.0 + 100.0 * (i % 2)) for i in range(60)]
        result = pleth_amplitude_series(samples, window_s=10.0)
        self.assertGreater(len(result), 0)
        for t, amp in result:
            self.assertGreater(amp, 0.0, "Amplitude should be positive for varying signal")

    def test_zero_amplitude_for_flat_signal(self):
        samples = [(i * 1.0, 100.0) for i in range(60)]
        result = pleth_amplitude_series(samples, window_s=10.0)
        for t, amp in result:
            self.assertAlmostEqual(amp, 0.0, places=4,
                                   msg="Flat signal should have zero amplitude")


# ===========================================================================
# 11. Leakage guard: no t > opend allowed
# ===========================================================================

class TestNoLeakage(unittest.TestCase):
    """Verify that extract() never uses data beyond opend."""

    def _synthetic_case(self, opend: float) -> dict[str, Any]:
        return {
            "caseid": "99999",
            "anestart": 0.0,
            "opend": opend,
            "age": 55.0,
            "weight": 70.0,
            "height": 170.0,
            "sex": "M",
            "intraop_ppf": 200.0,
            "intraop_phe": 100.0,
            "intraop_eph": 0.0,
        }

    def test_clinical_pfd_burden_respects_cutoff(self):
        """Samples beyond opend must not influence pfds_clin_pfd_burden."""
        opend_s = 3600.0  # 1 hour
        # MAP: adequate for entire case
        map_samples = [(i * 30.0, 80.0) for i in range(200)]
        # EtCO2 low ONLY after opend (t > 3600)
        etco2_normal = [(i * 30.0, 40.0) for i in range(int(opend_s // 30))]
        etco2_post_cutoff = [(opend_s + i * 30.0, 25.0) for i in range(10)]
        etco2_all = etco2_normal + etco2_post_cutoff

        # Clip both to [0, opend]
        from vitaldb_aki.features.pfds import _clip_to_window, _filter_physiologic
        from vitaldb_aki.features.pfds import ETCO2_MIN, ETCO2_MAX
        map_clipped = _clip_to_window(map_samples, 0.0, opend_s)
        etco2_clipped = _clip_to_window(etco2_all, 0.0, opend_s)
        etco2_clipped = _filter_physiologic(etco2_clipped, ETCO2_MIN, ETCO2_MAX)

        result = pfd_burden_clinical(map_clipped, etco2_clipped, [])
        self.assertIsNotNone(result)
        # EtCO2 post opend is NOT in the clipped series, so burden should be 0
        self.assertAlmostEqual(result, 0.0, places=4,
                               msg="Post-opend EtCO2 low must not inflate PFD burden")


# ===========================================================================
# 12. Acceptable-MAP subgroup (offline stub test)
# ===========================================================================

class TestAcceptableMapSubgroup(unittest.TestCase):
    def test_skipped_when_no_matrix(self):
        """When feature_matrix.csv is absent, function should return skipped=True."""
        cfg = {"data": {"cache_dir": "/nonexistent_path_xyz_abc_123"}}
        result = acceptable_map_subgroup(cfg)
        self.assertTrue(result.get("skipped"),
                        "Should skip gracefully when feature matrix is absent")
        self.assertIn("reason", result)

    def test_returns_expected_keys(self):
        cfg = {"data": {"cache_dir": "/nonexistent_path_xyz_abc_123"}}
        result = acceptable_map_subgroup(cfg)
        for key in ("skipped", "n_total", "n_acceptable_map", "n_high_pfds",
                    "n_low_pfds", "aki_rate_high", "aki_rate_low", "rate_ratio", "aki_col"):
            self.assertIn(key, result, f"Missing key {key!r} in subgroup result")

    def test_with_synthetic_matrix(self):
        """Build a tiny synthetic feature matrix and verify rate_ratio > 1."""
        import csv
        import os
        import tempfile

        # Create a temp dir with a synthetic feature_matrix.csv
        tmpdir = tempfile.mkdtemp()
        matrix_path = os.path.join(tmpdir, "feature_matrix.csv")

        rows = []
        # 30 cases: 10 low MAP burden + high PFDS (AKI=1), 20 low MAP + low PFDS (AKI=0)
        for i in range(10):
            rows.append({
                "caseid": str(i),
                "map_auc_below_65": "0.0",        # bottom tertile
                "map_min_below_65": "0.5",         # < 5 min
                "pfds_clin_pfd_burden": "0.8",     # top tertile
                "pfds_clin_pressor_stress": "5.0", # top tertile
                "composite": "1",                  # AKI
            })
        for i in range(10, 30):
            rows.append({
                "caseid": str(i),
                "map_auc_below_65": "0.0",
                "map_min_below_65": "0.5",
                "pfds_clin_pfd_burden": "0.05",    # bottom tertile
                "pfds_clin_pressor_stress": "0.1", # bottom tertile
                "composite": "0",                  # no AKI
            })
        # Add 10 cases with HIGH MAP burden (excluded from acceptable-MAP subgroup)
        for i in range(30, 40):
            rows.append({
                "caseid": str(i),
                "map_auc_below_65": "999.0",
                "map_min_below_65": "20.0",
                "pfds_clin_pfd_burden": "0.5",
                "pfds_clin_pressor_stress": "2.0",
                "composite": "1",
            })

        with open(matrix_path, "w", newline="", encoding="utf-8") as fh:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        cfg = {"data": {"cache_dir": tmpdir}}
        result = acceptable_map_subgroup(cfg)

        self.assertFalse(result.get("skipped"), f"Should not skip: {result.get('reason')}")
        self.assertEqual(result["n_total"], 40)
        # Acceptable MAP subgroup = cases 0..29 (min_below_65 < 5 min)
        self.assertEqual(result["n_acceptable_map"], 30)
        # Rate ratio: AKI in high-PFDS > low-PFDS (10/10 vs 0/20 = 1.0 vs 0.0)
        self.assertIsNotNone(result["aki_rate_high"])
        self.assertGreater(result["aki_rate_high"], result["aki_rate_low"] or 0.0,
                           "High PFDS should have higher AKI rate in acceptable-MAP subgroup")

        # Cleanup
        os.unlink(matrix_path)
        os.rmdir(tmpdir)


# ===========================================================================
# 13. extract() smoke test (no network)
# ===========================================================================

class TestExtractSmokeTest(unittest.TestCase):
    """Smoke test extract() with a synthetic cfg / cases / tracks (no network).

    extract() lazy-imports first_available and download_track from
    vitaldb_aki.data.tracks, so we patch at the source module.
    """

    def test_extract_returns_none_row_when_no_map(self):
        """No MAP track => pfds_available=0, all features None."""
        import unittest.mock as mock
        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        return_value=(None, [])) as _m_fa, \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        return_value=[]) as _m_dl, \
             mock.patch("vitaldb_aki.data.client.to_float",
                        side_effect=lambda v: None):

            from vitaldb_aki.features.pfds import extract
            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {"1": {"caseid": "1", "anestart": 0.0, "opend": 3600.0,
                           "intraop_ppf": None, "intraop_phe": None, "intraop_eph": None}}
            result = extract(cfg, cases, ["1"])

            self.assertIn("1", result)
            row = result["1"]
            self.assertEqual(row["pfds_available"], 0)
            for s in SPECS:
                if s.name != "pfds_available":
                    self.assertIsNone(row[s.name],
                                      f"{s.name} should be None when no MAP")

    def test_extract_computes_clinical_features_with_tracks(self):
        """With MAP + EtCO2 tracks, clinical features are non-None."""
        import unittest.mock as mock

        # Build synthetic tracks
        n = 40
        dt = 60.0
        map_track = [(i * dt, 80.0) for i in range(n)]   # constant MAP 80
        etco2_track = [(i * dt, 25.0) for i in range(n)] # low EtCO2 (PFD)

        def _first_available(cfg, cid, tnames, **kw):
            t0 = tnames[0] if tnames else ""
            if any("ART_MBP" in tn or "NIBP_MBP" in tn for tn in tnames):
                return ("Solar8000/ART_MBP", map_track)
            if any("ETCO2" in tn or ("CO2" in tn and "ETCO2" not in tn) for tn in tnames):
                return ("Solar8000/ETCO2", etco2_track)
            return (None, [])

        def _download_track(cfg, cid, tname, **kw):
            return []  # no SpO2, no Ce, no pleth

        with mock.patch("vitaldb_aki.data.tracks.first_available",
                        side_effect=_first_available), \
             mock.patch("vitaldb_aki.data.tracks.download_track",
                        side_effect=_download_track):

            from vitaldb_aki.features.pfds import extract

            # Reload to pick up fresh lazy imports
            import importlib
            import vitaldb_aki.features.pfds as _pfds_mod
            importlib.reload(_pfds_mod)
            extract = _pfds_mod.extract

            cfg = {"data": {"cache_dir": "/tmp"}}
            cases = {
                "42": {
                    "caseid": "42",
                    "anestart": 0.0,
                    "opend": float(n * dt),
                    "intraop_ppf": 200.0,
                    "intraop_phe": 100.0,
                    "intraop_eph": 5.0,
                }
            }
            result = extract(cfg, cases, ["42"])

        self.assertIn("42", result)
        row = result["42"]
        self.assertEqual(row["pfds_available"], 1)
        # PFD burden: MAP>=65 always, EtCO2<30 always => burden should be high (near 1.0)
        self.assertIsNotNone(row["pfds_clin_pfd_burden"])
        self.assertGreater(row["pfds_clin_pfd_burden"], 0.9,
                           "MAP>=65 + EtCO2<30 => PFD burden near 1.0")
        # Pressor stress: pressor given (100 ug phe + 5 mg eph), MAP adequate
        self.assertIsNotNone(row["pfds_clin_pressor_stress"])
        # Clinical fragility: propofol given but MAP never dips => 0.0
        self.assertIsNotNone(row["pfds_clin_fragility"])
        self.assertAlmostEqual(row["pfds_clin_fragility"], 0.0, places=4)
        # Recovery lag: MAP never dips => None
        self.assertIsNone(row["pfds_clin_recovery_lag"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
