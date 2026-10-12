"""Layer-1 (computational) ground truth for `exponent_gamma`, and for the mechanism it exists to escape.

THE TEST THAT MATTERS is `test_a_spectral_peak_inflates_the_2040_exponent_while_the_true_exponent_is_fixed`.
It builds 1/f^2 noise — true aperiodic exponent exactly 2.0, known by construction — and adds a Gaussian
spectral peak at 20 Hz. The aperiodic component never changes. `exponent_high` (fitted 20-40 Hz) climbs from
~2.0 to ~10; `exponent_gamma` (fitted 50-90 Hz) does not move.

WHAT THAT DOES AND DOES NOT ESTABLISH, because the distinction decides how the result may be reported.

    IT ESTABLISHES that the beta-hump mechanism is REAL AND SUFFICIENT: a spectral peak sitting near the low
    edge of a fit window can inflate the fitted slope enormously without any change in the underlying
    aperiodic process. The magnitude here dwarfs anything needed to explain E08's Chennu result.

    IT DOES NOT ESTABLISH that E08's 0.863 IS such an artefact. Demonstrating that a mechanism CAN produce an
    effect is not evidence that it DID. That question needs the fit band moved off the hump on real data
    (E12, blocked on the deposit host) or a band above the hump on a deposit that retains one (E15,
    ds005620 at 5 kHz), and this file is the machinery check that both of those rest on.

Propofol is known to increase beta power at moderate sedation (Xi et al., PLoS One 2018;13(6):e0199120, PMID
29920532, verified from the MEDLINE record), which is what makes a 20 Hz hump the relevant thing to plant
rather than an arbitrary one.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.seed import _f_subband, f_exponent_gamma

SF = 1000.0


def synth(sfreq, seconds, exponent, beta_amp=0.0, peak_hz=20.0, width=4.0, seed=0):
    """1/f^exponent noise with an optional Gaussian spectral peak. The aperiodic part is identical across
    `beta_amp` values by construction — the same amplitude envelope, multiplied by a bump."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sfreq)
    f = np.fft.rfftfreq(n, 1.0 / sfreq)
    f[0] = f[1]
    amp = f ** (-exponent / 2.0)
    if beta_amp > 0:
        amp = amp * (1.0 + beta_amp * np.exp(-0.5 * ((f - peak_hz) / width) ** 2))
    spec = (rng.normal(size=f.size) + 1j * rng.normal(size=f.size)) * amp
    return np.fft.irfft(spec, n) * 1e3


def _rec(beta_amp, sfreq=SF, exponent=2.0, n_ch=4, seconds=120.0):
    return np.vstack([synth(sfreq, seconds, exponent, beta_amp, seed=s) for s in range(n_ch)])


exp_high = _f_subband("exponent_high")


# --- the mechanism ---------------------------------------------------------------------------------

def test_a_spectral_peak_inflates_the_2040_exponent_while_the_true_exponent_is_fixed():
    clean, humped = _rec(0.0), _rec(8.0)
    e_clean, e_humped = exp_high(clean, None, SF), exp_high(humped, None, SF)
    assert e_clean == pytest.approx(2.0, abs=0.3), f"the no-hump control must recover the true 2.0: {e_clean}"
    assert e_humped > 3.0 * e_clean, (
        f"a 20 Hz peak failed to inflate the 20-40 Hz fit ({e_clean:.3f} -> {e_humped:.3f}); if this is "
        "genuinely the case the beta-hump explanation is much weaker than the project currently records")


def test_the_5090_exponent_is_untouched_by_the_same_peak():
    vals = [f_exponent_gamma(_rec(a), None, SF) for a in (0.0, 3.0, 8.0)]
    assert all(np.isfinite(v) for v in vals), vals
    assert max(vals) - min(vals) < 0.05, f"exponent_gamma moved with a 20 Hz hump it should not see: {vals}"
    assert all(v == pytest.approx(2.0, abs=0.3) for v in vals), vals


def test_the_inflation_grows_with_peak_amplitude():
    """Monotone, so the effect is the peak rather than an incidental property of one amplitude."""
    vals = [exp_high(_rec(a), None, SF) for a in (0.0, 1.0, 3.0, 8.0)]
    assert vals == sorted(vals), f"not monotone in peak amplitude: {vals}"


def test_both_bands_agree_when_there_is_no_peak_to_disagree_about():
    """The control that keeps the above from being a statement about the two bands differing in general."""
    d = _rec(0.0)
    assert exp_high(d, None, SF) == pytest.approx(f_exponent_gamma(d, None, SF), abs=0.35)


def test_a_peak_inside_the_gamma_band_inflates_gamma_instead():
    """The mechanism is about WHERE the peak sits relative to the window, not about the 20-40 band being
    special. Planting the peak at 60 Hz must move gamma and leave 20-40 alone — the mirror image."""
    d = np.vstack([synth(SF, 120.0, 2.0, 8.0, peak_hz=60.0, width=6.0, seed=s) for s in range(4)])
    clean = _rec(0.0)
    assert f_exponent_gamma(d, None, SF) > 2.0 * f_exponent_gamma(clean, None, SF)
    assert exp_high(d, None, SF) == pytest.approx(exp_high(clean, None, SF), abs=0.5)


# --- graceful degradation where the band does not exist ---------------------------------------------

def test_returns_nan_below_nyquist_rather_than_a_fabricated_number():
    """Sleep-EDF is 100 Hz, so 50-90 Hz does not exist there. NaN is the only honest answer and it must
    arrive without an exception, because the streaming runner turns exceptions into error rows."""
    assert np.isnan(f_exponent_gamma(_rec(0.0, sfreq=100.0, seconds=60.0), None, 100.0))


def test_returns_nan_on_a_45hz_filtered_recording():
    """Chennu arrives filtered 0.5-45 Hz. Sampling rate alone does not tell you the band is present."""
    from scipy.signal import butter, filtfilt
    d = _rec(0.0, sfreq=250.0, seconds=60.0)
    b, a = butter(4, 45.0 / 125.0, btype="low")
    filt = filtfilt(b, a, d, axis=1)
    v = f_exponent_gamma(filt, None, 250.0)
    assert np.isnan(v) or v > 5.0, (
        f"a 45 Hz-filtered recording returned a plausible-looking 50-90 Hz exponent ({v}); it must be NaN or "
        "obviously absurd, never a value a reader could mistake for a measurement")


# --- the declaration ---------------------------------------------------------------------------------

def test_the_declaration_says_it_was_written_before_any_value_existed():
    from bsde.candidates.registry import REGISTRY
    from bsde.candidates.seed import seed_registry
    seed_registry()
    c = REGISTRY.get("exponent_gamma")
    assert "BEFORE ANY VALUE EXISTED" in c.notes
    assert c.predicted("unconscious_vs_awake") == "higher"
    assert any("emg" in f.lower() for f in c.failure_conditions), (
        "50-90 Hz is squarely where surface muscle lives; the candidate must declare that an EMG result "
        "there makes it an EMG measure")
