"""test_aline_morphology.py -- Unit tests for beat-level A-line morphology (§7C/§7F).

All tests are offline / synthetic: we build an arterial pressure waveform from a
known beat template at a known HR with known SBP/DBP, add respiratory modulation to
inject a known PPV, and verify beat detection + aggregation recover those values
within tolerance. We also verify artefact rejection and the §11 post-opend exclusion.

No network access. The real-data validation lives under the main-guard of
features/aline_morphology.py (and a deletable scratch script); never in this suite.

Run:
    python3 -m unittest vitaldb_aki.tests.test_aline_morphology -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import numpy as np
    _HAVE_NUMPY = True
except Exception:
    _HAVE_NUMPY = False

from vitaldb_aki.features.aline_morphology import (
    SPECS,
    HR_MIN_BPM, HR_MAX_BPM, SBP_MIN, SBP_MAX, DBP_MIN, DBP_MAX,
    ANALYSIS_WINDOW_S, RESP_BLOCK_S, MAX_ANALYSIS_WINDOWS,
    ART_FS_HZ_NOMINAL,
    TAU_MIN_S, TAU_MAX_S,
    PPV_HIGH_THR, PP_LOW_THR, DPDT_LOW_THR, DBP_LOW_THR, MAP_ADEQUATE_THR,
    BURDEN_MAX_INTER_SAMPLE_DT_S,
    detect_beats,
    beat_features,
    ppv_for_block,
    estimate_fs,
    extract_case_from_track,
    tau_decay_for_beat,
    aug_index_for_beat,
    vascular_tone_features,
    _state_burden_minutes,
    burden_from_beat_series,
    _intraop_window,
)
from vitaldb_aki.features.base import audit_specs


# ---------------------------------------------------------------------------
# Synthetic arterial waveform generator.
# ---------------------------------------------------------------------------

def _beat_shape(phase: "np.ndarray") -> "np.ndarray":
    """Normalized arterial pulse shape in [0,1] over one cycle phase in [0,1).

    Fast systolic upstroke + slower diastolic runoff. Peak ~0.18 into the cycle.
    """
    out = np.zeros_like(phase)
    up = phase < 0.18
    out[up] = np.sin(phase[up] / 0.18 * (np.pi / 2.0))         # 0 -> 1 quarter sine
    down = ~up
    # exponential-ish runoff from 1 down toward ~0.05
    x = (phase[down] - 0.18) / (1.0 - 0.18)
    out[down] = (1.0 - 0.95 * x) * np.exp(-1.2 * x)
    return out


def synth_art(fs=ART_FS_HZ_NOMINAL, duration_s=20.0, hr_bpm=75.0,
              sbp=120.0, dbp=70.0, t0=0.0, resp_ppv_pct=0.0, resp_rate_bpm=12.0):
    """Build (times, values) for a synthetic arterial waveform.

    PP modulation injects a known PPV: PP oscillates +/- (resp_ppv_pct/2)% of the
    mean PP at the respiratory frequency, so peak-to-trough PP variation == the
    target PPV over a respiratory cycle.
    """
    n = int(round(fs * duration_s))
    t = t0 + np.arange(n) / fs
    cycle_s = 60.0 / hr_bpm
    phase = np.mod(t - t0, cycle_s) / cycle_s
    base = _beat_shape(phase)

    pp_mean = sbp - dbp
    if resp_ppv_pct > 0:
        resp_f = resp_rate_bpm / 60.0
        # amplitude such that (max-min)/mean = resp_ppv_pct/100  => half-amp = ppv/200
        amp = (resp_ppv_pct / 200.0) * pp_mean
        pp_t = pp_mean + amp * np.sin(2 * np.pi * resp_f * (t - t0))
    else:
        pp_t = np.full_like(t, pp_mean)

    v = dbp + base * pp_t
    return t, v


# ---------------------------------------------------------------------------
# 1. Spec invariants (run even without numpy).
# ---------------------------------------------------------------------------

class TestSpecs(unittest.TestCase):
    def test_audit_passes(self):
        audit_specs(SPECS)  # must not raise

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_expected_features_present(self):
        names = {s.name for s in SPECS}
        for required in (
            "aline_available", "aline_n_beats",
            "art_sbp_mean", "art_dbp_mean", "art_map_mean",
            "art_pulse_pressure_mean", "art_pulse_pressure_sd",
            "art_dpdt_max_mean", "art_dpdt_max_min",
            "art_ppv_mean", "art_hr_mean", "art_hr_sd",
            "art_systolic_auc_mean",
            # vascular-tone additions
            "art_tau_decay_mean", "art_aug_index_mean", "art_aug_index_quality",
            # burden (cumulative-dose) additions
            "art_ppv_burden_min", "art_narrow_pp_burden_min",
            "art_low_dpdt_burden_min", "art_low_dbp_burden_min",
            "art_perfusion_failure_burden_min",
            "art_perfusion_failure_burden_auc",
        ):
            self.assertIn(required, names)

    def test_fset_membership(self):
        # All beat-summary features are comprehensive; the vascular-tone markers
        # (tau, AIx) and the burden biomarkers are the pk refinement -- allow both,
        # forbid anything else (e.g. an accidental "standard"/"postop").
        for s in SPECS:
            self.assertIn(s.fset, ("comprehensive", "pk"),
                          msg=f"{s.name} fset={s.fset!r}")
        pk_names = {s.name for s in SPECS if s.fset == "pk"}
        self.assertEqual(
            pk_names,
            {"art_tau_decay_mean", "art_aug_index_mean", "art_aug_index_quality",
             "art_ppv_burden_min", "art_narrow_pp_burden_min",
             "art_low_dpdt_burden_min", "art_low_dbp_burden_min",
             "art_perfusion_failure_burden_min",
             "art_perfusion_failure_burden_auc"},
        )

    def test_burden_specs_all_intraop(self):
        burden_names = {
            "art_ppv_burden_min", "art_narrow_pp_burden_min",
            "art_low_dpdt_burden_min", "art_low_dbp_burden_min",
            "art_perfusion_failure_burden_min",
            "art_perfusion_failure_burden_auc",
        }
        for s in SPECS:
            if s.name in burden_names:
                self.assertEqual(s.timing, "intraop")
                self.assertEqual(s.fset, "pk")


# ---------------------------------------------------------------------------
# 2. Window helper (§11 intraop window).
# ---------------------------------------------------------------------------

class TestIntraopWindow(unittest.TestCase):
    def test_anestart_opend(self):
        ts, te = _intraop_window({"anestart": "100", "opstart": "200", "opend": "5000"})
        self.assertEqual((ts, te), (100.0, 5000.0))

    def test_fallback_opstart(self):
        ts, te = _intraop_window({"opstart": "200", "opend": "5000"})
        self.assertEqual((ts, te), (200.0, 5000.0))

    def test_no_opend_returns_none(self):
        ts, te = _intraop_window({"anestart": "100"})
        self.assertEqual((ts, te), (None, None))


@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestEstimateFs(unittest.TestCase):
    def test_recovers_500hz(self):
        t = np.arange(0, 10, 1 / 500.0)
        self.assertAlmostEqual(estimate_fs(t), 500.0, delta=1.0)

    def test_robust_to_gap(self):
        t = np.concatenate([np.arange(0, 5, 1 / 500.0),
                             np.arange(20, 25, 1 / 500.0)])  # big gap
        self.assertAlmostEqual(estimate_fs(t), 500.0, delta=1.0)


# ---------------------------------------------------------------------------
# 3. Beat detection recovers known HR / SBP / DBP / PP.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestBeatDetection(unittest.TestCase):
    def test_recovers_hr_sbp_dbp(self):
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=16.0, hr_bpm=75.0, sbp=120.0, dbp=70.0)
        beats = detect_beats(v, fs)
        self.assertGreater(len(beats), 10)  # ~20 beats in 16 s at 75 bpm

        sbp = float(np.mean(beats[:, 0]))
        dbp = float(np.mean(beats[:, 1]))
        pp = float(np.mean(beats[:, 2]))
        interval = beats[:, 4]
        hr = float(np.mean(60.0 / interval[interval > 0]))

        self.assertAlmostEqual(sbp, 120.0, delta=4.0)
        self.assertAlmostEqual(dbp, 70.0, delta=4.0)
        self.assertAlmostEqual(pp, 50.0, delta=5.0)
        self.assertAlmostEqual(hr, 75.0, delta=4.0)

    def test_dpdt_positive(self):
        fs = 500.0
        _, v = synth_art(fs=fs, duration_s=12.0, hr_bpm=80.0, sbp=130.0, dbp=60.0)
        beats = detect_beats(v, fs)
        self.assertGreater(len(beats), 5)
        self.assertTrue(np.all(beats[:, 3] > 0))  # dP/dt_max strictly positive

    def test_systolic_auc_in_unit_range(self):
        fs = 500.0
        _, v = synth_art(fs=fs, duration_s=12.0, hr_bpm=70.0, sbp=120.0, dbp=70.0)
        beats = detect_beats(v, fs)
        auc = beats[:, 5]
        auc = auc[np.isfinite(auc)]
        self.assertTrue(np.all(auc > 0))
        self.assertTrue(np.all(auc <= 1.5))  # normalized shape index, ~<=1

    def test_different_hr_recovered(self):
        for hr_target in (50.0, 100.0, 120.0):
            _, v = synth_art(fs=500.0, duration_s=16.0, hr_bpm=hr_target,
                             sbp=115.0, dbp=65.0)
            beats = detect_beats(v, 500.0)
            interval = beats[:, 4]
            hr = float(np.mean(60.0 / interval[interval > 0]))
            self.assertAlmostEqual(hr, hr_target, delta=5.0,
                                   msg=f"HR target {hr_target} -> {hr}")


# ---------------------------------------------------------------------------
# 4. PPV recovery.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestPPV(unittest.TestCase):
    def test_ppv_for_block_basic(self):
        # PP values 45..55, mean 50, (max-min)/mean = 10/50 = 20%
        pp = np.array([45.0, 47.0, 50.0, 53.0, 55.0])
        ppv = ppv_for_block(pp)
        self.assertAlmostEqual(ppv, 20.0, delta=0.01)

    def test_ppv_none_too_few(self):
        self.assertIsNone(ppv_for_block(np.array([50.0, 50.0])))

    def test_known_ppv_recovered_end_to_end(self):
        # Inject a 15% PPV via respiratory modulation; recover within tolerance.
        fs = 500.0
        target_ppv = 15.0
        t, v = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=80.0,
                         sbp=120.0, dbp=70.0, resp_ppv_pct=target_ppv,
                         resp_rate_bpm=12.0)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 1)
        self.assertIsNotNone(row["art_ppv_mean"])
        # PPV recovery is approximate (block boundaries, beat sampling); allow +/-6%.
        self.assertAlmostEqual(row["art_ppv_mean"], target_ppv, delta=6.0)

    def test_low_ppv_when_no_modulation(self):
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=80.0,
                         sbp=120.0, dbp=70.0, resp_ppv_pct=0.0)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 1)
        if row["art_ppv_mean"] is not None:
            self.assertLess(row["art_ppv_mean"], 5.0)


# ---------------------------------------------------------------------------
# 5. Artefact rejection.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestArtefactRejection(unittest.TestCase):
    def test_flush_artifact_beats_rejected(self):
        # Build a clean waveform, then splice in a flush artefact (pressure spikes
        # to ~280, then a zeroed flat run). Physiologic beats must survive; the
        # artefact must not create non-physiologic beats in the output.
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=16.0, hr_bpm=75.0, sbp=120.0, dbp=70.0)
        v = v.copy()
        # zeroing artefact: 1.5 s flatlined near 0 (line open to atmosphere)
        z0, z1 = int(4 * fs), int(5.5 * fs)
        v[z0:z1] = 0.5
        # flush spike: 0.3 s saturated high (off the top of the gate)
        s0, s1 = int(9 * fs), int(9.3 * fs)
        v[s0:s1] = 290.0
        beats = detect_beats(v, fs)
        self.assertGreater(len(beats), 5)
        # Every surviving beat must be physiologic.
        self.assertTrue(np.all(beats[:, 0] >= SBP_MIN) and np.all(beats[:, 0] <= SBP_MAX))
        self.assertTrue(np.all(beats[:, 1] >= DBP_MIN) and np.all(beats[:, 1] <= DBP_MAX))
        self.assertTrue(np.all(beats[:, 0] > beats[:, 1]))  # SBP > DBP

    def test_nonphysiologic_hr_rejected(self):
        # A 300 bpm "waveform" should yield no physiologic beats (HR gate).
        fs = 500.0
        _, v = synth_art(fs=fs, duration_s=8.0, hr_bpm=300.0, sbp=120.0, dbp=70.0)
        beats = detect_beats(v, fs)
        # Either no beats, or none with HR > HR_MAX.
        if len(beats):
            interval = beats[:, 4]
            hr = 60.0 / interval[interval > 0]
            self.assertTrue(np.all(hr <= HR_MAX_BPM + 1e-6))

    def test_pure_noise_no_beats(self):
        fs = 500.0
        rng = np.random.RandomState(0)
        v = rng.normal(0.0, 0.3, int(fs * 8))  # tiny noise near 0, no pulse
        beats = detect_beats(v, fs)
        self.assertEqual(len(beats), 0)


# ---------------------------------------------------------------------------
# 6. §11 post-opend exclusion.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestLeakageWindow(unittest.TestCase):
    def test_postop_samples_excluded(self):
        # Intraop part: normal BP. Post-opend part (t > opend): a high-BP signal
        # that, if leaked, would raise art_sbp_mean. Both segments sit inside the
        # first analysis window so the §11 clip is the only thing that removes the
        # post-opend portion. Verify it is excluded.
        fs = 500.0
        t1, v1 = synth_art(fs=fs, duration_s=8.0, hr_bpm=75.0, sbp=120.0, dbp=70.0, t0=0.0)
        opend = float(t1[-1]) + 1.0 / fs
        # post-opend: a much higher-pressure segment, contiguous right after opend
        t2, v2 = synth_art(fs=fs, duration_s=8.0, hr_bpm=75.0, sbp=200.0, dbp=120.0,
                           t0=opend)
        t = np.concatenate([t1, t2])
        v = np.concatenate([v1, v2])
        raw = list(zip(t.tolist(), v.tolist()))

        # With t_end = opend, only the first (normal) segment is used.
        row_clipped = extract_case_from_track(raw, t_start=0.0, t_end=opend)
        self.assertEqual(row_clipped["aline_available"], 1)
        self.assertAlmostEqual(row_clipped["art_sbp_mean"], 120.0, delta=6.0)

        # Sanity: if we (wrongly) included everything, SBP mean would climb well
        # above the clipped value -- confirming the clip is doing real work.
        row_all = extract_case_from_track(raw, t_start=0.0, t_end=None)
        self.assertGreater(row_all["art_sbp_mean"], row_clipped["art_sbp_mean"] + 10.0)


# ---------------------------------------------------------------------------
# 7. Missingness contract.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestMissingness(unittest.TestCase):
    def test_empty_track_all_none(self):
        row = extract_case_from_track([], t_start=0.0, t_end=100.0)
        self.assertEqual(row["aline_available"], 0)
        for s in SPECS:
            if s.name == "aline_available":
                continue
            self.assertIsNone(row[s.name], msg=f"{s.name} should be None when no waveform")

    def test_unusable_track_no_fabricated_zeros(self):
        # All-flatline (zeroed line) -> no physiologic beats -> available=0,
        # n_beats=0, morphology None (NOT zeros).
        fs = 500.0
        t = np.arange(0, 16, 1 / fs)
        v = np.full_like(t, 0.5)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 0)
        self.assertEqual(row["aline_n_beats"], 0)
        self.assertIsNone(row["art_sbp_mean"])
        self.assertIsNone(row["art_ppv_mean"])


# ---------------------------------------------------------------------------
# 8. Aggregation: art_map_mean ~ DBP + PP/3; dpdt_min <= dpdt_mean.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestAggregation(unittest.TestCase):
    def test_map_relation_and_counts(self):
        fs = 500.0
        # Two windows worth of beats via a long-enough trace (one period apart not
        # needed for aggregation test; just feed multiple windows directly).
        _, v1 = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=75.0, sbp=120.0, dbp=70.0)
        b1 = detect_beats(v1, fs)
        _, v2 = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=90.0, sbp=110.0, dbp=60.0)
        b2 = detect_beats(v2, fs)
        feats = beat_features([b1, b2], ppv_values=[12.0, 14.0])

        self.assertEqual(feats["aline_n_beats"], len(b1) + len(b2))
        expected_map = feats["art_dbp_mean"] + feats["art_pulse_pressure_mean"] / 3.0
        self.assertAlmostEqual(feats["art_map_mean"], expected_map, delta=1.5)
        self.assertLessEqual(feats["art_dpdt_max_min"], feats["art_dpdt_max_mean"] + 1e-6)
        self.assertAlmostEqual(feats["art_ppv_mean"], 13.0, delta=0.01)


# ---------------------------------------------------------------------------
# 9. Vascular tone: tau (diastolic decay) core recovers a known exponential.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestTauDecay(unittest.TestCase):
    def _exp_beat(self, fs, tau_true, p0=50.0, pinf=70.0, upstroke_s=0.10,
                  diastole_s=0.70):
        """One synthetic beat: fast linear upstroke to a peak, then a clean
        P(t)=p0*exp(-t/tau)+pinf diastolic decay. Peak = pinf+p0."""
        up_n = int(round(fs * upstroke_s))
        peak = pinf + p0
        up = np.linspace(pinf, peak, up_n, endpoint=False)
        td = np.arange(int(round(fs * diastole_s))) / fs
        down = p0 * np.exp(-td / tau_true) + pinf
        return np.concatenate([up, down])

    def test_recovers_known_tau(self):
        fs = 500.0
        for tau_true in (0.3, 0.6, 1.2):
            beat = self._exp_beat(fs, tau_true)
            tau = tau_decay_for_beat(beat, fs)
            self.assertIsNotNone(tau, msg=f"tau None for true={tau_true}")
            self.assertAlmostEqual(tau, tau_true, delta=0.08,
                                   msg=f"true {tau_true} -> {tau}")
            self.assertGreaterEqual(tau, TAU_MIN_S)
            self.assertLessEqual(tau, TAU_MAX_S)

    def test_flat_segment_returns_none(self):
        fs = 500.0
        beat = np.concatenate([np.linspace(70, 120, 50), np.full(300, 120.0)])
        self.assertIsNone(tau_decay_for_beat(beat, fs))

    def test_out_of_range_tau_rejected(self):
        # A decay far too slow to be physiologic (tau >> 3 s over the window):
        fs = 500.0
        beat = self._exp_beat(fs, tau_true=10.0, diastole_s=0.7)
        # tau may be estimated > TAU_MAX_S and must then be rejected (None).
        tau = tau_decay_for_beat(beat, fs)
        self.assertTrue(tau is None or TAU_MIN_S <= tau <= TAU_MAX_S)

    def test_aggregate_tau_mean(self):
        out = vascular_tone_features([
            ([0.5, 0.7], 0, 0, []),
            ([0.6], 0, 0, []),
        ])
        self.assertAlmostEqual(out["art_tau_decay_mean"], 0.6, delta=1e-6)


# ---------------------------------------------------------------------------
# 10. Vascular tone: augmentation-index core + quality gate.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestAugIndex(unittest.TestCase):
    def _shoulder_beat(self, fs, p_dia=70.0, p_sys=120.0, p_infl=100.0):
        """Beat whose upstroke has a clear inflection (shoulder) at p_infl: a
        steep rise to the shoulder, a brief plateau (curvature sign change),
        then a second rise to the systolic peak, then a decay."""
        seg1 = np.linspace(p_dia, p_infl, int(fs * 0.05))           # forward wave
        seg2 = np.linspace(p_infl, p_infl + 2.0, int(fs * 0.03))    # shoulder/plateau
        seg3 = np.linspace(p_infl + 2.0, p_sys, int(fs * 0.05))     # reflected wave
        down = np.linspace(p_sys, p_dia, int(fs * 0.6))
        return np.concatenate([seg1, seg2, seg3, down])

    def test_inflection_recovered_in_range(self):
        fs = 500.0
        beat = self._shoulder_beat(fs, p_dia=70.0, p_sys=120.0, p_infl=100.0)
        aix = aug_index_for_beat(beat, fs)
        self.assertIsNotNone(aix)
        # Expected AIx ~ (100-70)/(120-70) = 0.6; allow tolerance for smoothing.
        self.assertAlmostEqual(aix, 0.6, delta=0.2)
        self.assertGreaterEqual(aix, -1.0)
        self.assertLessEqual(aix, 1.5)

    def test_smooth_triangle_no_false_inflection(self):
        # A pure single-rise triangle has no curvature sign change on the
        # upstroke -> no usable inflection -> None.
        fs = 500.0
        up = np.linspace(70.0, 120.0, int(fs * 0.12))
        down = np.linspace(120.0, 70.0, int(fs * 0.6))
        beat = np.concatenate([up, down])
        self.assertIsNone(aug_index_for_beat(beat, fs))

    def test_quality_gate_none_when_too_few(self):
        # Only 2 usable AIx beats (< AIX_MIN_QUALITY_BEATS) -> mean None, but
        # quality fraction is still reported.
        out = vascular_tone_features([([], 4, 2, [0.5, 0.6])])
        self.assertIsNone(out["art_aug_index_mean"])
        self.assertAlmostEqual(out["art_aug_index_quality"], 0.5, delta=1e-6)

    def test_quality_and_mean_reported_when_enough(self):
        out = vascular_tone_features([([], 5, 4, [0.4, 0.5, 0.6, 0.5])])
        self.assertAlmostEqual(out["art_aug_index_mean"], 0.5, delta=1e-6)
        self.assertAlmostEqual(out["art_aug_index_quality"], 0.8, delta=1e-6)

    def test_no_attempts_quality_none(self):
        out = vascular_tone_features([([0.5], 0, 0, [])])
        self.assertIsNone(out["art_aug_index_quality"])
        self.assertIsNone(out["art_aug_index_mean"])


# ---------------------------------------------------------------------------
# 11. End-to-end: vascular-tone keys present and gated on a synthetic case.
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestVascularToneEndToEnd(unittest.TestCase):
    def test_keys_present_and_typed(self):
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=75.0,
                         sbp=120.0, dbp=70.0)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 1)
        for k in ("art_tau_decay_mean", "art_aug_index_mean",
                  "art_aug_index_quality"):
            self.assertIn(k, row)
        # tau should be in physiologic range when present (the synth beat decays).
        if row["art_tau_decay_mean"] is not None:
            self.assertGreaterEqual(row["art_tau_decay_mean"], TAU_MIN_S)
            self.assertLessEqual(row["art_tau_decay_mean"], TAU_MAX_S)
        # AIx is None or a float; quality is None or a fraction in [0,1].
        q = row["art_aug_index_quality"]
        if q is not None:
            self.assertGreaterEqual(q, 0.0)
            self.assertLessEqual(q, 1.0)

    def test_empty_case_vtone_none(self):
        row = extract_case_from_track([], t_start=0.0, t_end=100.0)
        self.assertIsNone(row["art_tau_decay_mean"])
        self.assertIsNone(row["art_aug_index_mean"])
        self.assertIsNone(row["art_aug_index_quality"])


# ---------------------------------------------------------------------------
# 12. BURDEN cores (stdlib-only -- no numpy needed).
# ---------------------------------------------------------------------------

class TestStateBurdenMinutes(unittest.TestCase):
    """_state_burden_minutes: time-in-abnormal-state, gap-capped, in minutes."""

    def test_known_duration_recovered(self):
        # 1 Hz epochs (every 1 s). 30 consecutive abnormal epochs -> each owns the
        # 1 s forward interval -> ~30 s = 0.5 min in the abnormal state.
        series = [(float(i), True) for i in range(30)] + [(30.0, False), (31.0, False)]
        burden = _state_burden_minutes(series)
        self.assertAlmostEqual(burden, 30.0 / 60.0, delta=1e-6)

    def test_never_abnormal_is_zero(self):
        series = [(float(i), False) for i in range(10)]
        self.assertEqual(_state_burden_minutes(series), 0.0)

    def test_single_epoch_zero(self):
        # One epoch has no forward interval -> 0 burden.
        self.assertEqual(_state_burden_minutes([(0.0, True)]), 0.0)

    def test_empty_zero(self):
        self.assertEqual(_state_burden_minutes([]), 0.0)

    def test_gap_cap_respected(self):
        # Two abnormal epochs separated by a 1000 s recording break: the first
        # epoch's interval is capped at 10 s, NOT 1000 s.
        series = [(0.0, True), (1000.0, True), (1001.0, False)]
        burden = _state_burden_minutes(series)
        # epoch0: min(1000,10)=10 s abnormal; epoch1: min(1,10)=1 s abnormal.
        self.assertAlmostEqual(burden, (10.0 + 1.0) / 60.0, delta=1e-6)

    def test_severity_weighting(self):
        # Each abnormal 1 s epoch weighted by severity -> AUC-style minutes.
        series = [(0.0, True), (1.0, True), (2.0, False)]
        sev = [2.0, 3.0, 0.0]
        burden = _state_burden_minutes(series, severity=sev)
        # epoch0: 1 s * 2 = 2; epoch1: 1 s * 3 = 3 -> 5 s.
        self.assertAlmostEqual(burden, 5.0 / 60.0, delta=1e-6)


class TestBurdenFromBeatSeries(unittest.TestCase):
    """burden_from_beat_series: per-case waveform burdens with missingness."""

    def _normal_beat(self, t):
        # PP=50 (>30), dP/dt=900 (>400), DBP=70 (>50), MAP=70+50/3~86.7 (>=65).
        return (t, {"sbp": 120.0, "dbp": 70.0, "pp": 50.0, "dpdt": 900.0,
                    "map": 70.0 + 50.0 / 3.0})

    def _narrow_pp_beat(self, t):
        # PP=20 (<30); MAP still adequate (DBP 60 + 20/3 ~66.7 >= 65).
        return (t, {"sbp": 80.0, "dbp": 60.0, "pp": 20.0, "dpdt": 900.0,
                    "map": 60.0 + 20.0 / 3.0})

    def test_no_beats_returns_none(self):
        out = burden_from_beat_series([], [])
        for k in ("art_ppv_burden_min", "art_narrow_pp_burden_min",
                  "art_low_dpdt_burden_min", "art_low_dbp_burden_min",
                  "art_perfusion_failure_burden_min",
                  "art_perfusion_failure_burden_auc"):
            self.assertIsNone(out[k], msg=f"{k} should be None with no beats")

    def test_single_beat_none(self):
        out = burden_from_beat_series([self._normal_beat(0.0)], [])
        self.assertIsNone(out["art_narrow_pp_burden_min"])

    def test_all_normal_zero_not_none(self):
        # >=2 beats but never abnormal -> 0.0 (signal present), NOT None.
        beats = [self._normal_beat(float(i)) for i in range(20)]
        out = burden_from_beat_series(beats, [])
        self.assertEqual(out["art_narrow_pp_burden_min"], 0.0)
        self.assertEqual(out["art_low_dpdt_burden_min"], 0.0)
        self.assertEqual(out["art_low_dbp_burden_min"], 0.0)
        self.assertEqual(out["art_perfusion_failure_burden_min"], 0.0)
        self.assertEqual(out["art_perfusion_failure_burden_auc"], 0.0)

    def test_narrow_pp_known_minutes(self):
        # 60 consecutive narrow-PP beats at 1 Hz -> ~60 s = 1.0 min narrow PP.
        beats = [self._narrow_pp_beat(float(i)) for i in range(60)]
        beats.append(self._normal_beat(60.0))  # closing normal beat
        out = burden_from_beat_series(beats, [])
        self.assertAlmostEqual(out["art_narrow_pp_burden_min"], 60.0 / 60.0,
                               delta=0.05)

    def test_perfusion_failure_adequate_map_abnormal_flag(self):
        # Narrow-PP beats at ADEQUATE MAP -> perfusion-failure burden accrues
        # (the headline: occult failure despite adequate pressure).
        beats = [self._narrow_pp_beat(float(i)) for i in range(30)]
        beats.append(self._normal_beat(30.0))
        out = burden_from_beat_series(beats, [])
        self.assertGreater(out["art_perfusion_failure_burden_min"], 0.0)
        # AUC (severity-weighted) >= the plain minutes when >=1 flag tripped.
        self.assertGreaterEqual(out["art_perfusion_failure_burden_auc"],
                                out["art_perfusion_failure_burden_min"] - 1e-9)

    def test_perfusion_failure_zero_when_map_inadequate(self):
        # Narrow PP but INADEQUATE MAP (<65) -> NOT perfusion failure (that is
        # plain hypotension, captured by the hypotension dose, not occult failure).
        low_map_beats = [
            (float(i), {"sbp": 60.0, "dbp": 40.0, "pp": 20.0, "dpdt": 900.0,
                        "map": 40.0 + 20.0 / 3.0})  # MAP ~46.7 < 65
            for i in range(20)
        ]
        low_map_beats.append((20.0, {"sbp": 60.0, "dbp": 40.0, "pp": 20.0,
                                     "dpdt": 900.0, "map": 46.7}))
        out = burden_from_beat_series(low_map_beats, [])
        self.assertEqual(out["art_perfusion_failure_burden_min"], 0.0)

    def test_ppv_burden_from_ppv_series(self):
        # PPV series: high PPV (>13%) for 40 s at 1 Hz -> ~40 s = 0.667 min.
        ppv_series = [(float(i), 20.0) for i in range(40)] + [(40.0, 5.0)]
        out = burden_from_beat_series([], ppv_series)
        self.assertAlmostEqual(out["art_ppv_burden_min"], 40.0 / 60.0, delta=0.05)

    def test_ppv_burden_none_when_no_series(self):
        out = burden_from_beat_series([], [])
        self.assertIsNone(out["art_ppv_burden_min"])

    def test_ppv_burden_zero_when_all_low(self):
        ppv_series = [(float(i), 5.0) for i in range(10)]
        out = burden_from_beat_series([], ppv_series)
        self.assertEqual(out["art_ppv_burden_min"], 0.0)


@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestBurdenEndToEnd(unittest.TestCase):
    def test_keys_present_and_none_when_empty(self):
        row = extract_case_from_track([], t_start=0.0, t_end=100.0)
        for k in ("art_ppv_burden_min", "art_narrow_pp_burden_min",
                  "art_low_dpdt_burden_min", "art_low_dbp_burden_min",
                  "art_perfusion_failure_burden_min",
                  "art_perfusion_failure_burden_auc"):
            self.assertIn(k, row)
            self.assertIsNone(row[k])

    def test_normal_case_burdens_zero_or_none(self):
        # A clean normal-BP case: narrow-PP / low-DBP / low-dPdt burdens should be
        # ~0 (signal present, never abnormal), NOT None.
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=75.0,
                         sbp=120.0, dbp=70.0)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 1)
        # DBP 70 > 50, PP 50 > 30 -> these burdens are 0.0 (defined, not None).
        self.assertEqual(row["art_narrow_pp_burden_min"], 0.0)
        self.assertEqual(row["art_low_dbp_burden_min"], 0.0)

    def test_low_bp_case_accrues_burden(self):
        # A low-DBP case (DBP 40 < 50) should accrue a positive low-DBP burden.
        fs = 500.0
        t, v = synth_art(fs=fs, duration_s=ANALYSIS_WINDOW_S, hr_bpm=75.0,
                         sbp=90.0, dbp=40.0)
        row = extract_case_from_track(list(zip(t.tolist(), v.tolist())),
                                      t_start=None, t_end=None)
        self.assertEqual(row["aline_available"], 1)
        self.assertIsNotNone(row["art_low_dbp_burden_min"])
        self.assertGreater(row["art_low_dbp_burden_min"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
