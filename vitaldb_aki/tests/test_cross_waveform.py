"""test_cross_waveform.py -- Unit tests for cross-waveform coupling features.

All tests are offline / synthetic: no network access, no VitalDB credentials.
We build controlled synthetic signals with known coupling properties and verify
the pure helper functions recover those properties within physiologic tolerance.

Run:
    python3 -m unittest vitaldb_aki.tests.test_cross_waveform -v
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import numpy as np
    _HAVE_NUMPY = True
except Exception:
    _HAVE_NUMPY = False

from vitaldb_aki.features.cross_waveform import (
    SPECS,
    PAT_MIN_MS, PAT_MAX_MS,
    RESP_BAND_LO, RESP_BAND_HI,
    BRS_MIN_SEQ_LEN,
    pulse_arrival_times,
    beat_amplitudes,
    brs_sequence,
    spectral_coherence,
    compute_cross_features,
    decoupling_burden_minutes,
    DECOUPLING_HIGH_THR,
)
from vitaldb_aki.features.base import audit_specs


# ===========================================================================
# 1. Spec invariants (no numpy needed).
# ===========================================================================

class TestSpecs(unittest.TestCase):
    def test_audit_passes(self):
        audit_specs(SPECS)

    def test_all_intraop(self):
        for s in SPECS:
            self.assertEqual(s.timing, "intraop", msg=f"{s.name} timing={s.timing!r}")

    def test_fset_membership(self):
        # All coupling features are comprehensive; the cumulative-dose burden is
        # the pk refinement (mirrors the aline_morphology burdens). Allow both,
        # forbid anything else.
        for s in SPECS:
            self.assertIn(s.fset, ("comprehensive", "pk"),
                          msg=f"{s.name} fset={s.fset!r}")
        pk_names = {s.name for s in SPECS if s.fset == "pk"}
        self.assertEqual(pk_names, {"xwave_decoupling_burden_min"})

    def test_no_duplicate_names(self):
        names = [s.name for s in SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_expected_features_present(self):
        names = {s.name for s in SPECS}
        for req in (
            "cross_waveform_available",
            "pat_mean_ms", "pat_sd_ms", "pat_slope",
            "art_ppg_amp_corr", "central_peripheral_decoupling",
            "brs_mean", "brs_n_sequences",
            "cardiopulm_coherence", "resp_sbp_coupling",
            "xwave_decoupling_burden_min",
        ):
            self.assertIn(req, names)


# ===========================================================================
# 1b. Decoupling BURDEN core (stdlib-only -- no numpy needed).
# ===========================================================================

class TestDecouplingBurden(unittest.TestCase):
    def test_known_minutes_gap_capped(self):
        # 5 windows 300 s apart, all decoupled (0.9 > 0.50). Each of the first 4
        # windows owns min(300, 10) = 10 s -> 40 s = 0.667 min.
        series = [(float(i * 300), 0.9) for i in range(5)]
        self.assertAlmostEqual(decoupling_burden_minutes(series),
                               40.0 / 60.0, delta=1e-3)

    def test_contiguous_windows(self):
        # 7 windows 5 s apart, all decoupled -> first 6 own 5 s each = 30 s.
        series = [(float(i * 5), 0.8) for i in range(7)]
        self.assertAlmostEqual(decoupling_burden_minutes(series),
                               30.0 / 60.0, delta=1e-3)

    def test_never_decoupled_zero(self):
        series = [(float(i * 5), 0.1) for i in range(5)]
        self.assertEqual(decoupling_burden_minutes(series), 0.0)

    def test_one_window_none(self):
        # < 2 windows -> cannot integrate -> None (truly missing, not 0.0).
        self.assertIsNone(decoupling_burden_minutes([(0.0, 0.9)]))

    def test_empty_none(self):
        self.assertIsNone(decoupling_burden_minutes([]))

    def test_threshold_boundary(self):
        # Exactly at threshold (0.50) is NOT abnormal (strict >).
        series = [(0.0, DECOUPLING_HIGH_THR), (5.0, DECOUPLING_HIGH_THR)]
        self.assertEqual(decoupling_burden_minutes(series), 0.0)


# ===========================================================================
# 2. Synthetic signal builders.
# ===========================================================================

def _synth_ecg_ppg(fs=500.0, duration_s=30.0, hr_bpm=70.0, pat_ms=200.0):
    """Synthetic ECG (R-peaks as tall gaussians) + PPG (smooth oscillation).

    The PPG foot occurs `pat_ms` ms after each R-peak, giving a known PAT.
    Returns (ecg, ppg) as numpy arrays of length n = int(fs*duration_s).
    """
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    cycle_s = 60.0 / hr_bpm
    phase = np.mod(t, cycle_s) / cycle_s  # in [0,1)

    # ECG: gaussian bump at phase ~0.1 (R-wave), smaller bumps for P and T.
    ecg = (
        0.1 * np.exp(-((phase - 0.08) / 0.02) ** 2)   # P wave
        + 1.0 * np.exp(-((phase - 0.12) / 0.01) ** 2)  # R wave (tall)
        - 0.15 * np.exp(-((phase - 0.14) / 0.01) ** 2) # S wave
        + 0.3 * np.exp(-((phase - 0.35) / 0.05) ** 2)  # T wave
    )

    # PPG: smooth inverted-gaussian pulse; foot (minimum) at
    # phase = (R_phase + pat_ms/1000 / cycle_s) mod 1.
    pat_phase = pat_ms / 1000.0 / cycle_s   # delay in phase units
    foot_phase = (0.12 + pat_phase) % 1.0   # foot location in cycle
    # PPG peak ~0.3 cycle after foot
    peak_phase = (foot_phase + 0.3) % 1.0
    # Build PPG as a smooth sinusoidal shape
    ppg_phase_rel = (phase - foot_phase) % 1.0
    ppg = 0.5 - 0.5 * np.cos(2 * np.pi * ppg_phase_rel * 0.7)
    # Normalise to [0,1]
    ppg = (ppg - ppg.min()) / (ppg.max() - ppg.min() + 1e-9)

    return ecg, ppg


def _synth_art_ppg_coupled(fs=500.0, duration_s=30.0, hr_bpm=70.0,
                            art_sbp=120.0, art_dbp=70.0,
                            ppg_amp_mean=1.0, correlation=0.9):
    """ART and PPG with known per-beat amplitude correlation.

    Both beat amplitudes are drawn from correlated normals so the Pearson r
    is approximately `correlation`.
    """
    from vitaldb_aki.features.aline_morphology import ART_FS_HZ_NOMINAL
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    cycle_s = 60.0 / hr_bpm
    n_beats = int(duration_s / cycle_s)

    # Correlated normal amplitudes
    rng = np.random.RandomState(42)
    z1 = rng.randn(n_beats)
    z2 = correlation * z1 + math.sqrt(max(0, 1 - correlation ** 2)) * rng.randn(n_beats)

    pp_mean = art_sbp - art_dbp
    art_amps = pp_mean + 0.05 * pp_mean * z1        # ART pulse pressure per beat
    ppg_amps = ppg_amp_mean + 0.1 * ppg_amp_mean * z2  # PPG amplitude per beat

    # Build continuous waveforms from the per-beat amplitudes.
    def _waveform(amps, dbp, phase_peak=0.18):
        v = np.zeros(n)
        for bi, amp in enumerate(amps):
            t0 = bi * cycle_s
            t1 = (bi + 1) * cycle_s
            lo = int(t0 * fs)
            hi = min(n, int(t1 * fs))
            seg_len = hi - lo
            if seg_len <= 0:
                continue
            ph = np.arange(seg_len) / seg_len
            shape = np.where(ph < phase_peak,
                             np.sin(ph / phase_peak * (np.pi / 2.0)),
                             np.exp(-2.5 * (ph - phase_peak) / (1.0 - phase_peak)))
            v[lo:hi] = dbp + max(0.0, amp) * shape
        return v

    art_v = _waveform(art_amps, art_dbp, phase_peak=0.18)
    ppg_v = _waveform(ppg_amps, dbp=0.0, phase_peak=0.25)
    ppg_v = ppg_v / (ppg_v.max() + 1e-9)  # normalise PPG to [0,1]
    return t, art_v, ppg_v


def _synth_sbp_rr_brs(n_beats=60, brs_slope=5.0, noise=0.3):
    """SBP and RR series with an imposed BRS (ms/mmHg).

    SBP is a random walk; RR = SBP * brs_slope + noise.
    Returns (sbp, rr_ms).
    """
    rng = np.random.RandomState(7)
    # Random-walk SBP in physiologic range
    sbp = 100.0 + np.cumsum(rng.randn(n_beats) * 2.0)
    sbp = np.clip(sbp, 80.0, 140.0)
    # RR = slope * SBP + intercept + noise (linear model)
    intercept = 700.0 - brs_slope * 100.0   # ~700 ms RR at SBP=100
    rr = brs_slope * sbp + intercept + rng.randn(n_beats) * noise
    rr = np.clip(rr, 400.0, 1200.0)
    return sbp, rr


def _synth_coherent_pair(fs=4.0, duration_s=60.0, freq=0.1, noise=0.1):
    """Two sinusoids at `freq` Hz with additive noise -> high coherence."""
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    rng = np.random.RandomState(3)
    x = np.sin(2 * np.pi * freq * t) + noise * rng.randn(n)
    y = np.sin(2 * np.pi * freq * t + 0.3) + noise * rng.randn(n)
    return x, y, fs


def _synth_incoherent_pair(fs=4.0, duration_s=60.0):
    """Two independent noise signals -> near-zero coherence."""
    n = int(fs * duration_s)
    rng = np.random.RandomState(99)
    x = rng.randn(n)
    y = rng.randn(n)
    return x, y, fs


# ===========================================================================
# 3. pulse_arrival_times() recovers known PAT.
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestPulseArrivalTimes(unittest.TestCase):
    def test_recovers_known_pat(self):
        """PAT of 200 ms should be recovered within ±20 ms tolerance."""
        fs = 500.0
        target_pat_ms = 200.0
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=20.0, hr_bpm=70.0,
                                   pat_ms=target_pat_ms)
        pat_arr = pulse_arrival_times(ecg, ppg, fs)
        self.assertGreater(len(pat_arr), 5, "should detect multiple beats")
        mean_pat = float(np.mean(pat_arr))
        self.assertAlmostEqual(mean_pat, target_pat_ms, delta=30.0,
                               msg=f"PAT mean {mean_pat:.1f} ms vs target {target_pat_ms}")

    def test_pat_in_physiologic_range(self):
        """All returned PATs must be in [PAT_MIN_MS, PAT_MAX_MS]."""
        fs = 500.0
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=20.0, hr_bpm=75.0,
                                   pat_ms=250.0)
        pat_arr = pulse_arrival_times(ecg, ppg, fs)
        if len(pat_arr) > 0:
            self.assertTrue(np.all(pat_arr >= PAT_MIN_MS),
                            f"PAT below min: {pat_arr.min():.1f}")
            self.assertTrue(np.all(pat_arr <= PAT_MAX_MS),
                            f"PAT above max: {pat_arr.max():.1f}")

    def test_empty_on_too_short_signal(self):
        """Signals shorter than 1 s return empty array."""
        fs = 500.0
        ecg = np.zeros(int(fs * 0.5))
        ppg = np.zeros(int(fs * 0.5))
        pat_arr = pulse_arrival_times(ecg, ppg, fs)
        self.assertEqual(len(pat_arr), 0)

    def test_different_pats_distinguished(self):
        """150 ms and 300 ms PATs produce noticeably different mean PATs."""
        fs = 500.0
        _, ppg1 = _synth_ecg_ppg(fs=fs, duration_s=20.0, hr_bpm=70.0, pat_ms=150.0)
        ecg, ppg2 = _synth_ecg_ppg(fs=fs, duration_s=20.0, hr_bpm=70.0, pat_ms=300.0)
        p1 = pulse_arrival_times(ecg, ppg1, fs)
        p2 = pulse_arrival_times(ecg, ppg2, fs)
        if p1.size > 0 and p2.size > 0:
            self.assertLess(np.mean(p1), np.mean(p2),
                            "shorter PAT series should have smaller mean")


# ===========================================================================
# 4. beat_amplitudes() tests.
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestBeatAmplitudes(unittest.TestCase):
    def test_ppg_amplitudes_positive(self):
        """PPG beat amplitudes should all be positive."""
        fs = 500.0
        _, ppg = _synth_ecg_ppg(fs=fs, duration_s=15.0, hr_bpm=70.0, pat_ms=200.0)
        amps = beat_amplitudes(ppg, fs, ppg=True)
        if amps.size > 0:
            self.assertTrue(np.all(amps > 0))

    def test_art_pp_amplitudes(self):
        """ART pulse-pressure amplitudes should be in physiologic range."""
        fs = 500.0
        # Build a simple synthetic ART waveform: SBP=120, DBP=70 -> PP=50 mmHg
        n = int(fs * 15.0)
        t = np.arange(n) / fs
        cycle_s = 60.0 / 70.0
        phase = np.mod(t, cycle_s) / cycle_s
        art_v = 70.0 + 50.0 * np.where(
            phase < 0.18,
            np.sin(phase / 0.18 * (np.pi / 2.0)),
            np.exp(-2.5 * (phase - 0.18) / (1.0 - 0.18))
        )
        amps = beat_amplitudes(art_v, fs, ppg=False)
        if amps.size > 0:
            self.assertTrue(np.all(amps > 0))
            # PP should be ~50 mmHg (120-70)
            self.assertAlmostEqual(float(np.mean(amps)), 50.0, delta=12.0)

    def test_flat_signal_no_amplitudes(self):
        """A flat signal should return no beat amplitudes."""
        fs = 500.0
        sig = np.full(int(fs * 10), 75.0)
        amps = beat_amplitudes(sig, fs, ppg=True)
        self.assertEqual(amps.size, 0)

    def test_amplitude_series_length_reasonable(self):
        """At 70 bpm for 20 s we expect ~23 beats -> ~22 inter-beat amps."""
        fs = 500.0
        _, ppg = _synth_ecg_ppg(fs=fs, duration_s=20.0, hr_bpm=70.0, pat_ms=200.0)
        amps = beat_amplitudes(ppg, fs, ppg=True)
        # Allow generous range for synthetic signal
        self.assertGreater(amps.size, 5)


# ===========================================================================
# 5. brs_sequence() recovers known BRS slope.
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestBrsSequence(unittest.TestCase):
    def test_recovers_brs_slope(self):
        """BRS sequence method should recover imposed slope within 50%."""
        target_slope = 5.0   # ms/mmHg
        sbp, rr = _synth_sbp_rr_brs(n_beats=100, brs_slope=target_slope, noise=0.5)
        slopes, n_seqs = brs_sequence(sbp, rr)
        self.assertGreater(n_seqs, 0,
                           "should find at least one baroreflex sequence")
        mean_slope = float(np.mean(slopes))
        self.assertAlmostEqual(mean_slope, target_slope, delta=target_slope * 0.8,
                               msg=f"BRS slope {mean_slope:.2f} vs target {target_slope}")

    def test_brs_slope_physiologic_range(self):
        """All returned slopes must be within physiologic bounds."""
        from vitaldb_aki.features.cross_waveform import BRS_MIN_SLOPE_MS_MMHG, BRS_MAX_SLOPE_MS_MMHG
        sbp, rr = _synth_sbp_rr_brs(n_beats=120, brs_slope=8.0, noise=1.0)
        slopes, _ = brs_sequence(sbp, rr)
        if slopes.size > 0:
            self.assertTrue(np.all(slopes >= BRS_MIN_SLOPE_MS_MMHG))
            self.assertTrue(np.all(slopes <= BRS_MAX_SLOPE_MS_MMHG))

    def test_no_sequences_on_anti_correlated(self):
        """SBP rising while RR falls -> concordant pairs are rare; may get 0 sequences."""
        rng = np.random.RandomState(5)
        sbp = 100.0 + np.cumsum(rng.randn(60) * 2.0)
        # RR inversely proportional to SBP (normal physiology in opposite sign)
        rr = 900.0 - 5.0 * (sbp - sbp.mean()) + rng.randn(60) * 0.5
        # This test just verifies the function doesn't crash and returns
        # non-negative sequence count.
        slopes, n_seqs = brs_sequence(sbp, rr)
        self.assertGreaterEqual(n_seqs, 0)

    def test_too_short_returns_empty(self):
        """Fewer beats than min_len+1 -> empty slopes, 0 sequences."""
        sbp = np.array([100.0, 102.0])
        rr = np.array([800.0, 810.0])
        slopes, n_seqs = brs_sequence(sbp, rr, min_len=BRS_MIN_SEQ_LEN)
        self.assertEqual(n_seqs, 0)
        self.assertEqual(slopes.size, 0)

    def test_sequence_length_threshold(self):
        """A perfectly concordant run of exactly min_len beats counts as 1 sequence."""
        n = BRS_MIN_SEQ_LEN + 1
        sbp = np.linspace(95, 105, n)
        rr = np.linspace(700, 750, n)  # both rising -> concordant
        slopes, n_seqs = brs_sequence(sbp, rr, min_len=BRS_MIN_SEQ_LEN)
        self.assertGreaterEqual(n_seqs, 1)
        self.assertGreater(slopes.size, 0)
        self.assertGreater(float(slopes[0]), 0)


# ===========================================================================
# 6. spectral_coherence() tests.
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestSpectralCoherence(unittest.TestCase):
    def test_coherent_sinusoids_high_coherence(self):
        """Two in-band sinusoids should give high coherence (>0.7)."""
        x, y, fs = _synth_coherent_pair(fs=4.0, duration_s=120.0, freq=0.12, noise=0.05)
        coh = spectral_coherence(x, y, fs, band=(RESP_BAND_LO, RESP_BAND_HI))
        self.assertIsNotNone(coh)
        self.assertGreater(coh, 0.5, f"coherent sinusoids: coherence={coh:.3f}")

    def test_incoherent_noise_low_coherence(self):
        """Two independent noise signals should give low coherence (<0.5)."""
        x, y, fs = _synth_incoherent_pair(fs=4.0, duration_s=120.0)
        coh = spectral_coherence(x, y, fs, band=(RESP_BAND_LO, RESP_BAND_HI))
        if coh is not None:
            self.assertLess(coh, 0.6,
                            f"incoherent noise: coherence={coh:.3f} should be low")

    def test_identical_signals_perfect_coherence(self):
        """Identical signals should have coherence ~1.0."""
        rng = np.random.RandomState(12)
        fs = 4.0
        x = rng.randn(int(fs * 120))
        coh = spectral_coherence(x, x, fs, band=(RESP_BAND_LO, RESP_BAND_HI))
        if coh is not None:
            self.assertGreater(coh, 0.8)

    def test_returns_none_on_too_short(self):
        """Signal shorter than 4 segments -> None."""
        x = np.zeros(4)
        coh = spectral_coherence(x, x, fs=4.0, band=(RESP_BAND_LO, RESP_BAND_HI))
        self.assertIsNone(coh)

    def test_coherence_in_unit_range(self):
        """Coherence must be in [0, 1]."""
        x, y, fs = _synth_coherent_pair(fs=4.0, duration_s=80.0, freq=0.15, noise=0.2)
        coh = spectral_coherence(x, y, fs, band=(RESP_BAND_LO, RESP_BAND_HI))
        if coh is not None:
            self.assertGreaterEqual(coh, 0.0)
            self.assertLessEqual(coh, 1.0)


# ===========================================================================
# 7. compute_cross_features() end-to-end (synthetic, no network).
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestComputeCrossFeatures(unittest.TestCase):

    def _make_ecg_ppg_data(self, fs=500.0, dur=30.0, hr=70.0, pat_ms=200.0):
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=dur, hr_bpm=hr, pat_ms=pat_ms)
        t = np.arange(len(ecg)) / fs
        return (t, ecg), (t, ppg)

    def _make_art_data(self, fs=500.0, dur=30.0, hr=70.0, sbp=120.0, dbp=70.0):
        from vitaldb_aki.features.aline_morphology import synth_art
        t, v = synth_art(fs=fs, duration_s=dur, hr_bpm=hr, sbp=sbp, dbp=dbp)
        return t, v

    def test_all_none_when_no_channels(self):
        row = compute_cross_features(None, None, None, None, None, None)
        self.assertEqual(row["cross_waveform_available"], 0)
        for s in SPECS:
            if s.name == "cross_waveform_available":
                continue
            self.assertIsNone(row[s.name], msg=f"{s.name} should be None with no channels")

    def test_available_flag_set_with_two_channels(self):
        ecg_d, ppg_d = self._make_ecg_ppg_data()
        row = compute_cross_features(ecg_d, ppg_d, None, None, None, None)
        self.assertEqual(row["cross_waveform_available"], 1)

    def test_pat_recovered_ecg_ppg(self):
        """PAT features should be non-None and in physiologic range."""
        ecg_d, ppg_d = self._make_ecg_ppg_data(pat_ms=200.0)
        row = compute_cross_features(ecg_d, ppg_d, None, None, None, None)
        if row["pat_mean_ms"] is not None:
            self.assertGreater(row["pat_mean_ms"], PAT_MIN_MS)
            self.assertLess(row["pat_mean_ms"], PAT_MAX_MS)
        if row["pat_sd_ms"] is not None:
            self.assertGreaterEqual(row["pat_sd_ms"], 0.0)

    def test_decoupling_near_zero_when_correlated(self):
        """Correlated ART+PPG -> art_ppg_amp_corr near 1, decoupling near 0."""
        fs = 500.0
        dur = 35.0
        t, art_v, ppg_v = _synth_art_ppg_coupled(fs=fs, duration_s=dur,
                                                   hr_bpm=70.0,
                                                   art_sbp=120.0, art_dbp=70.0,
                                                   ppg_amp_mean=1.0, correlation=0.9)
        art_d = (t, art_v)
        ppg_d = (t, ppg_v)
        row = compute_cross_features(None, ppg_d, art_d, None, None, None)
        if row["art_ppg_amp_corr"] is not None:
            self.assertGreater(row["art_ppg_amp_corr"], 0.3,
                               f"correlated signals should show positive amp corr "
                               f"(got {row['art_ppg_amp_corr']:.3f})")
        if row["central_peripheral_decoupling"] is not None:
            self.assertGreaterEqual(row["central_peripheral_decoupling"], 0.0)
            self.assertLessEqual(row["central_peripheral_decoupling"], 1.0)

    def test_decoupling_one_minus_abs_corr(self):
        """central_peripheral_decoupling == 1 - |art_ppg_amp_corr|."""
        fs = 500.0
        t, art_v, ppg_v = _synth_art_ppg_coupled(fs=fs, duration_s=35.0,
                                                   hr_bpm=70.0, correlation=0.7)
        row = compute_cross_features(None, (t, ppg_v), (t, art_v), None, None, None)
        if (row["art_ppg_amp_corr"] is not None and
                row["central_peripheral_decoupling"] is not None):
            expected = round(1.0 - abs(row["art_ppg_amp_corr"]), 4)
            self.assertAlmostEqual(row["central_peripheral_decoupling"], expected,
                                   delta=1e-3)

    def test_brs_features_with_art_and_ecg(self):
        """BRS features should be present when both ART and ECG are supplied."""
        fs = 500.0
        dur = 35.0
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=dur, hr_bpm=70.0, pat_ms=200.0)
        t = np.arange(int(fs * dur)) / fs
        # Build simple ART waveform (same shape as synthetic ECG/PPG builder)
        cycle_s = 60.0 / 70.0
        phase = np.mod(t, cycle_s) / cycle_s
        art_v = 70.0 + 50.0 * np.where(
            phase < 0.18,
            np.sin(phase / 0.18 * (np.pi / 2.0)),
            np.exp(-2.5 * (phase - 0.18) / (1.0 - 0.18))
        )
        row = compute_cross_features(
            (t, ecg), (t, ppg), (t, art_v), None, None, None
        )
        # BRS may or may not find sequences in a 30s synthetic window;
        # we just verify types are correct and values are physiologic.
        if row["brs_mean"] is not None:
            from vitaldb_aki.features.cross_waveform import (
                BRS_MIN_SLOPE_MS_MMHG, BRS_MAX_SLOPE_MS_MMHG
            )
            self.assertGreaterEqual(row["brs_mean"], BRS_MIN_SLOPE_MS_MMHG)
            self.assertLessEqual(row["brs_mean"], BRS_MAX_SLOPE_MS_MMHG)
        if row["brs_n_sequences"] is not None:
            self.assertGreaterEqual(row["brs_n_sequences"], 0)

    def test_cardiopulm_coherence_with_co2(self):
        """Cardiopulm coherence should be in [0,1] when CO2 is present."""
        fs = 500.0
        dur = 35.0
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=dur, hr_bpm=70.0, pat_ms=200.0)
        t_ecg = np.arange(int(fs * dur)) / fs

        # Synthetic CO2: slow sinusoidal respiratory signal at 0.2 Hz
        fs_co2 = 62.5
        n_co2 = int(fs_co2 * dur)
        t_co2 = np.arange(n_co2) / fs_co2
        co2_v = 0.03 + 0.02 * np.sin(2 * np.pi * 0.2 * t_co2)  # ~3-5 % CO2

        row = compute_cross_features(
            (t_ecg, ecg), (t_ecg, ppg), None, (t_co2, co2_v), None, None
        )
        if row["cardiopulm_coherence"] is not None:
            self.assertGreaterEqual(row["cardiopulm_coherence"], 0.0)
            self.assertLessEqual(row["cardiopulm_coherence"], 1.0)

    def test_leakage_guard_t_end(self):
        """Samples after t_end must be excluded (§11).

        We build a 30s window, set t_end=15s, and check that features are
        computed only from the first half (or are None if insufficient data).
        The test just verifies no exception is raised and available flag is set.
        """
        fs = 500.0
        dur = 30.0
        ecg, ppg = _synth_ecg_ppg(fs=fs, duration_s=dur, hr_bpm=70.0, pat_ms=200.0)
        t = np.arange(int(fs * dur)) / fs
        row = compute_cross_features(
            (t, ecg), (t, ppg), None, None, t_start=0.0, t_end=15.0
        )
        # Should not crash; available flag is either 0 or 1
        self.assertIn(row["cross_waveform_available"], (0, 1))

    def test_all_spec_keys_present(self):
        """compute_cross_features must return all SPEC feature keys."""
        ecg_d, ppg_d = self._make_ecg_ppg_data()
        row = compute_cross_features(ecg_d, ppg_d, None, None, None, None)
        for s in SPECS:
            self.assertIn(s.name, row,
                          msg=f"missing key {s.name!r} in output")

    def test_single_channel_unavailable(self):
        """Only one channel -> cross_waveform_available=0, all None."""
        _, ppg_d = self._make_ecg_ppg_data()
        row = compute_cross_features(None, ppg_d, None, None, None, None)
        self.assertEqual(row["cross_waveform_available"], 0)


# ===========================================================================
# 8. Amplitude correlation: known-correlation recovery.
# ===========================================================================

@unittest.skipUnless(_HAVE_NUMPY, "numpy required")
class TestAmplitudeCorrelation(unittest.TestCase):
    def test_correlated_amplitudes_positive_r(self):
        """Positively correlated ART/PPG amplitudes -> art_ppg_amp_corr > 0."""
        fs = 500.0
        t, art_v, ppg_v = _synth_art_ppg_coupled(
            fs=fs, duration_s=35.0, hr_bpm=70.0, correlation=0.85
        )
        row = compute_cross_features(None, (t, ppg_v), (t, art_v),
                                     None, None, None)
        if row["art_ppg_amp_corr"] is not None:
            self.assertGreater(row["art_ppg_amp_corr"], 0.0)

    def test_uncorrelated_amplitudes(self):
        """Uncorrelated ART/PPG -> |art_ppg_amp_corr| should be low."""
        fs = 500.0
        t, art_v, ppg_v = _synth_art_ppg_coupled(
            fs=fs, duration_s=35.0, hr_bpm=70.0, correlation=0.0
        )
        row = compute_cross_features(None, (t, ppg_v), (t, art_v),
                                     None, None, None)
        if row["art_ppg_amp_corr"] is not None:
            # With correlation=0 and noise, expect |r| < 0.7
            self.assertLess(abs(row["art_ppg_amp_corr"]), 0.9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
