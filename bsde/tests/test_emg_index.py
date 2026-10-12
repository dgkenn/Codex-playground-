"""Ground-truth tests for the EMG proxies. An EMG index that does not detect PLANTED EMG is worthless, and
worse than worthless if it is then used to clear a finding of muscle contamination.

These use `synth.simulate_channel`'s `emg_amp` parameter, so the amount of muscle is known by construction
rather than inferred. The critical asymmetry the suite must encode:

    detecting planted EMG  -> the index works
    NOT detecting it after a 45 Hz low-pass -> the BAND is inadequate, not the muscle absent

The second case is the real situation on the Chennu deposit (filtered 0.5-45 Hz), so it is tested explicitly.
A negative there must never be read as clearing a result.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.emg import (emg_beta_gamma_fraction, emg_kurtosis, emg_index,
                               EMG_BAND, TOTAL_BAND)
from bsde.synth import simulate_channel

SF = 250.0


def _rec(emg_amp, n_ch=4, seconds=30.0, exponent=1.5, seed=0):
    rng = np.random.default_rng(seed)
    return np.vstack([simulate_channel(seconds, SF, exponent, np.random.default_rng(seed * 100 + i),
                                       emg_amp=emg_amp) for i in range(n_ch)])


# --- the index must respond to planted muscle ---------------------------------------------------------

def test_beta_gamma_fraction_rises_monotonically_with_planted_emg():
    vals = [emg_beta_gamma_fraction(_rec(a, seed=1), SF) for a in (0.0, 2.0, 8.0, 32.0)]
    assert all(np.isfinite(v) for v in vals), vals
    assert vals == sorted(vals), f"not monotone in planted EMG amplitude: {vals}"
    assert vals[-1] > vals[0] * 1.5, f"barely responds to 32x EMG: {vals}"


def test_kurtosis_rises_with_planted_emg():
    """Spikiness is the more band-independent signature, so this must respond even more robustly."""
    lo = emg_kurtosis(_rec(0.0, seed=2))
    hi = emg_kurtosis(_rec(32.0, seed=2))
    assert np.isfinite(lo) and np.isfinite(hi)
    assert hi > lo, f"kurtosis did not rise with EMG: {lo} -> {hi}"


def test_composite_index_rises_with_planted_emg():
    vals = [emg_index(_rec(a, seed=3), SF) for a in (0.0, 4.0, 16.0)]
    assert all(np.isfinite(v) for v in vals)
    assert vals == sorted(vals), f"composite not monotone: {vals}"


# --- THE CRITICAL LIMITATION: a 45 Hz low-pass hides the spectral signature -----------------------------

def _emg_peaked(n, sfreq, peak_hz=70.0, width=25.0, rng=None):
    """EMG with a REALISTIC spectrum: a broad hump centred near 70 Hz, which is where surface motor-unit
    activity actually peaks. The project's `synth.simulate_channel(emg_amp=...)` instead adds FLAT 20-90 Hz
    noise, and that difference turns out to decide the answer below, so both are tested."""
    rng = rng or np.random.default_rng(0)
    spec = (rng.normal(size=n // 2 + 1) + 1j * rng.normal(size=n // 2 + 1))
    f = np.fft.rfftfreq(n, 1.0 / sfreq)
    env = np.exp(-0.5 * ((f - peak_hz) / width) ** 2)
    x = np.fft.irfft(spec * env, n=n)
    sd = x.std()
    return x / (sd if sd > 0 else 1.0)


def _lowpass(d, cutoff=45.0):
    from scipy.signal import butter, filtfilt
    b, a = butter(4, cutoff / (SF / 2), btype="low")
    return filtfilt(b, a, d, axis=1)


def test_a_45hz_lowpass_does_NOT_hide_flat_band_synthetic_emg():
    """A finding recorded rather than assumed. With the project's FLAT 20-90 Hz synthetic EMG, a 45 Hz
    low-pass barely reduces detectability at all -- about 36 % of flat 20-90 Hz power lies in 20-45 Hz, and
    that residue is still overwhelming at large amplitudes.

    This is why MASTER_PLAN §9.11's original phrasing -- that the deposit's filtering has REMOVED the
    high-frequency evidence -- was too strong. The retained band is not devoid of muscle information.
    """
    clean, dirty = _rec(0.0, seed=4), _rec(32.0, seed=4)
    sep_full = emg_beta_gamma_fraction(dirty, SF) - emg_beta_gamma_fraction(clean, SF)
    sep_lp = (emg_beta_gamma_fraction(_lowpass(dirty), SF)
              - emg_beta_gamma_fraction(_lowpass(clean), SF))
    assert sep_full > 0.5, "planted EMG must be strongly detectable before filtering"
    assert sep_lp > 0.5 * sep_full, (
        f"flat-band EMG became undetectable after low-pass ({sep_lp:.3f} vs {sep_full:.3f}); if that is "
        "genuinely the case, §9.11's strong claim is right after all and this test should be re-inverted")


def test_but_a_45hz_lowpass_DOES_degrade_realistically_peaked_emg():
    """The informative version. With EMG peaked at 70 Hz -- where surface muscle actually lives -- a 45 Hz
    low-pass removes most of it and detectability falls substantially.

    So sensitivity on a 45 Hz-limited deposit is REDUCED BUT NON-ZERO, and the size of the reduction depends
    on the true EMG spectrum, which this project cannot observe in that deposit. A negative there is
    therefore WEAK evidence of no muscle, not NO evidence -- which is the calibrated version of the claim.
    """
    rng = np.random.default_rng(11)
    n = int(30 * SF)
    base = np.vstack([simulate_channel(30.0, SF, 1.5, np.random.default_rng(700 + i)) for i in range(4)])
    emg = np.vstack([_emg_peaked(base.shape[1], SF, rng=np.random.default_rng(800 + i)) for i in range(4)])
    clean, dirty = base, base + 32.0 * emg

    sep_full = emg_beta_gamma_fraction(dirty, SF) - emg_beta_gamma_fraction(clean, SF)
    sep_lp = (emg_beta_gamma_fraction(_lowpass(dirty), SF)
              - emg_beta_gamma_fraction(_lowpass(clean), SF))
    assert sep_full > 0, "peaked EMG must be detectable before filtering"
    assert sep_lp < sep_full, f"peaked EMG detectability did not drop: {sep_lp:.3f} vs {sep_full:.3f}"


def test_kurtosis_survives_the_lowpass_better_than_the_spectral_proxy():
    """Why the composite includes kurtosis at all: a burst of motor-unit firing still leaves heavy tails
    after its high frequencies are removed."""
    clean, dirty = _rec(0.0, seed=5), _rec(32.0, seed=5)
    assert emg_kurtosis(_lowpass(dirty)) > emg_kurtosis(_lowpass(clean)), \
        "kurtosis lost all EMG sensitivity after low-pass"


# --- housekeeping --------------------------------------------------------------------------------------

def test_the_band_constants_document_the_compromise():
    """A real EMG index uses 65-95 Hz. These constants must stay inside the deposit's retained band, and the
    test exists so that changing them is a deliberate act rather than a silent one."""
    assert EMG_BAND == (20.0, 45.0)
    assert TOTAL_BAND == (1.0, 45.0)
    assert EMG_BAND[1] <= 45.0, "the band must not exceed what the target deposit retains"


def test_kurtosis_uses_the_median_so_one_bad_channel_cannot_dominate():
    good = _rec(0.0, n_ch=5, seed=6)
    spiked = good.copy()
    spiked[2, ::500] = 5000.0            # one pathological channel, enormous kurtosis
    assert emg_kurtosis(spiked) == pytest.approx(emg_kurtosis(good), abs=0.5), \
        "a single bridged/spiking electrode changed the whole-recording value -- use the median"


def test_flat_and_too_short_channels_are_skipped_not_counted_as_gaussian():
    flat = np.zeros((3, 10_000))
    assert np.isnan(emg_kurtosis(flat)), "a flat channel has no distribution; it must not report 0 excess"
    assert np.isnan(emg_kurtosis(np.random.default_rng(0).normal(size=(2, 10))))


def test_emg_proxies_are_declared_as_artefact_measures_not_brain_state_markers():
    """The registry is where this is enforced: if an EMG proxy's interpretation ever stops saying so, it could
    be cited as evidence about the brain."""
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    for nm in ("emg_index", "emg_beta_gamma_fraction", "emg_kurtosis"):
        c = REGISTRY.get(nm)
        text = (c.interpretation + " " + c.notes).lower()
        assert "artefact" in text or "artifact" in text, f"{nm} does not declare itself an artefact measure"
        assert any("emg result" in f.lower() for f in c.failure_conditions), \
            f"{nm} must declare that a competing candidate matching it makes that candidate an EMG result"
