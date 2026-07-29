"""GATE A: does the aperiodic estimator recover a KNOWN exponent from simulated EEG?

Every claim in this project inherits the accuracy of this estimator, and on real EEG there is nothing to check
it against. These tests are the check. A failure here invalidates everything downstream, so they are written
to be strict about the things that actually bias an exponent fit:

  1. clean recovery across the physiological range
  2. recovery when oscillatory peaks sit inside the fit range   (peaks bias OLS upward in power -> flatter)
  3. the DIRECTION of EMG bias is measured, not assumed
  4. line noise inside the fit range, with and without notch exclusion
  5. sensitivity to the fit range itself, which is the project's most influential free parameter
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from uce.synth import simulate_channel
from uce.features.aperiodic import welch_psd, fit_aperiodic

SF = 250.0
DUR = 120.0
TOL = 0.15          # absolute tolerance on the recovered exponent, pre-set


def _fit(x, **kw):
    f, p = welch_psd(x, SF, window_s=4.0, overlap=0.5)
    return fit_aperiodic(f, p, **kw)


@pytest.mark.parametrize("true_exp", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
def test_recovers_clean_exponent(true_exp):
    x = simulate_channel(DUR, SF, true_exp, np.random.default_rng(1))
    got = _fit(x, fit_lo_hz=1.0, fit_hi_hz=40.0)["exponent"]
    assert abs(got - true_exp) < TOL, f"true {true_exp}, got {got:.3f}"


def test_r2_is_high_on_clean_pink_noise():
    x = simulate_channel(DUR, SF, 1.5, np.random.default_rng(2))
    assert _fit(x, fit_lo_hz=1.0, fit_hi_hz=40.0)["r2"] > 0.95


def test_alpha_peak_biases_ols_and_robust_mode_helps():
    """A strong alpha peak inside the fit range biases a plain OLS fit; robust mode must reduce that bias."""
    true_exp = 1.5
    x = simulate_channel(DUR, SF, true_exp, np.random.default_rng(3), peaks=[(10.0, 3.0)])
    e_ols = _fit(x, fit_lo_hz=1.0, fit_hi_hz=40.0, mode="loglog_ols")["exponent"]
    e_rob = _fit(x, fit_lo_hz=1.0, fit_hi_hz=40.0, mode="loglog_robust")["exponent"]
    assert abs(e_rob - true_exp) <= abs(e_ols - true_exp) + 1e-9, (
        f"robust mode did not help: ols {e_ols:.3f}, robust {e_rob:.3f}, true {true_exp}")


def test_emg_flattens_the_spectrum_downward():
    """EMG adds high-frequency power, so it must bias the exponent DOWNWARD (flatter spectrum).

    This is asserted rather than assumed because the sign of the bias determines how to read any
    UCE difference between moving and paralysed patients (RESEARCH_STRATEGY.md §4).
    """
    true_exp = 2.0
    clean = simulate_channel(DUR, SF, true_exp, np.random.default_rng(4))
    dirty = simulate_channel(DUR, SF, true_exp, np.random.default_rng(4), emg_amp=1.0)
    e_clean = _fit(clean, fit_lo_hz=1.0, fit_hi_hz=40.0)["exponent"]
    e_dirty = _fit(dirty, fit_lo_hz=1.0, fit_hi_hz=40.0)["exponent"]
    assert e_dirty < e_clean, f"EMG did not flatten: clean {e_clean:.3f}, dirty {e_dirty:.3f}"


def test_line_noise_exclusion_recovers_accuracy():
    """A 50 Hz line spike inside a wide fit range must be excludable, and exclusion must help."""
    true_exp = 1.5
    x = simulate_channel(DUR, SF, true_exp, np.random.default_rng(5), line_hz=50.0, line_amp=4.0)
    e_incl = _fit(x, fit_lo_hz=1.0, fit_hi_hz=60.0)["exponent"]
    e_excl = _fit(x, fit_lo_hz=1.0, fit_hi_hz=60.0, exclude_line_hz=50.0)["exponent"]
    assert abs(e_excl - true_exp) <= abs(e_incl - true_exp) + 1e-9


def test_fit_range_sensitivity_is_bounded_on_clean_data():
    """On CLEAN 1/f the recovered exponent must be near-invariant to the fit range.

    If it is not even here, then range-dependence on real data cannot be attributed to physiology.
    """
    true_exp = 1.5
    x = simulate_channel(DUR, SF, true_exp, np.random.default_rng(6))
    got = [_fit(x, fit_lo_hz=lo, fit_hi_hz=hi)["exponent"]
           for lo, hi in [(1, 40), (2, 40), (1, 30), (3, 45), (0.5, 20)]]
    assert max(got) - min(got) < 0.25, f"range-dependent on clean data: {np.round(got, 3)}"
    assert all(abs(g - true_exp) < 0.25 for g in got)


def test_negative_exponent_is_surfaced_not_clipped():
    """A rising spectrum must report a negative exponent -- it is a data-quality signal, not a value to hide."""
    n = int(DUR * SF)
    rng = np.random.default_rng(7)
    x = simulate_channel(DUR, SF, -1.0, rng)      # deliberately inverted
    assert _fit(x, fit_lo_hz=1.0, fit_hi_hz=40.0)["exponent"] < 0
