"""Ground-truth checks for bsde.features.exotic. Matching the project's rule: every assertion here targets a
KNOWN answer built by construction, not merely "it ran and produced a finite number".
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.features.exotic import (
    spatial_participation_ratio, spatial_participation_ratio_raw,
    multiscale_entropy_slope, sample_entropy,
    phase_amplitude_coupling,
    subband_exponents,
    critical_slowing,
)
from bsde.synth import pink_noise, simulate_channel

SF = 250.0


# =========================================================================================================
# 1. spatial_participation_ratio
# =========================================================================================================

def test_pr_identical_channels_is_exactly_one():
    rng = np.random.default_rng(0)
    ch = rng.normal(size=5000)
    data = np.tile(ch, (8, 1))          # 8 perfectly correlated (identical) channels -> one effective dim
    raw = spatial_participation_ratio_raw(data)
    assert raw == pytest.approx(1.0, abs=1e-6), raw


def test_pr_independent_channels_close_to_n():
    rng = np.random.default_rng(1)
    n_ch = 20
    data = rng.normal(size=(n_ch, 20000))          # independent white noise per channel
    raw = spatial_participation_ratio_raw(data)
    assert raw > 0.7 * n_ch, f"raw PR {raw} not close to n_channels={n_ch}"


def test_pr_normalised_is_in_zero_one_range():
    rng = np.random.default_rng(2)
    data = rng.normal(size=(10, 5000))
    norm = spatial_participation_ratio(data)
    assert 0.0 < norm <= 1.0, norm
    raw = spatial_participation_ratio_raw(data)
    assert norm == pytest.approx(raw / 10, rel=1e-9)


def test_pr_single_channel_is_nan():
    data = np.random.default_rng(3).normal(size=(1, 5000))
    assert np.isnan(spatial_participation_ratio_raw(data))
    assert np.isnan(spatial_participation_ratio(data))


def test_pr_flat_and_too_short_are_nan():
    flat = np.zeros((4, 5000))
    assert np.isnan(spatial_participation_ratio_raw(flat))
    too_short = np.random.default_rng(4).normal(size=(4, 1))
    assert np.isnan(spatial_participation_ratio_raw(too_short))


# =========================================================================================================
# 2. multiscale_entropy_slope
# =========================================================================================================
#
# Expected sign, stated before the run: white noise loses entropy as it is coarse-grained (each averaged
# block washes out the sample-to-sample unpredictability that IS the noise, so SampEn falls with scale ->
# NEGATIVE slope). A 1/f signal is correlated across scales (that correlation is what 1/f MEANS), so its
# structure -- and therefore its entropy -- survives coarse-graining much better; the literature's usual
# framing is that such signals retain complexity across scales, i.e. a much-less-negative or flat slope
# relative to white noise. The test below only requires the two slopes to differ and states the direction
# actually observed; see the report for whether it matched this reasoning.

def test_mse_slope_differs_for_white_noise_vs_1_over_f():
    rng_w = np.random.default_rng(10)
    white = rng_w.normal(size=4000)
    rng_p = np.random.default_rng(11)
    pink = pink_noise(4000, SF, exponent=1.5, rng=rng_p)

    slope_white = multiscale_entropy_slope(white, SF)
    slope_pink = multiscale_entropy_slope(pink, SF)
    assert np.isfinite(slope_white) and np.isfinite(slope_pink)
    assert slope_white != pytest.approx(slope_pink, abs=1e-3), (slope_white, slope_pink)
    # White noise is expected to be the more negative of the two (entropy falls fastest with coarse-graining).
    assert slope_white < slope_pink, (
        f"expected white-noise slope ({slope_white}) < 1/f slope ({slope_pink}); "
        "if this fails, the sign reasoning in the module docstring does not hold for this implementation"
    )


def test_sample_entropy_basic_sanity():
    rng = np.random.default_rng(12)
    x = rng.normal(size=2000)
    se = sample_entropy(x, m=2)
    assert np.isfinite(se) and se > 0


def test_mse_slope_flat_and_too_short_are_nan():
    flat = np.zeros(4000)
    assert np.isnan(multiscale_entropy_slope(flat, SF))
    too_short = np.random.default_rng(13).normal(size=10)
    assert np.isnan(multiscale_entropy_slope(too_short, SF))


def test_sample_entropy_flat_is_nan():
    assert np.isnan(sample_entropy(np.zeros(1000)))


# =========================================================================================================
# 3. phase_amplitude_coupling
# =========================================================================================================

def _pac_signal(n_seconds, sfreq, coupled, seed=0):
    """coupled=True: a 10 Hz oscillation whose amplitude is modulated by the SAME 1 Hz phase that is also
    present as a low-frequency component (genuine, known PAC).

    coupled=False: the two oscillations are present together with INDEPENDENT random phases and NO
    amplitude modulation of one by the other -- a constant-envelope 10 Hz oscillation plus a separate 1 Hz
    oscillation. This, not "modulated by a different but still-fixed phase", is the correct negative
    control: two sinusoids at the SAME frequency with any fixed (even independently-drawn) phase offset are
    still perfectly phase-locked to each other for the whole recording, just shifted, and still produce
    high MI -- that construction was tried first and rejected because it does not actually test "no
    coupling", only "coupling with an unknown lag". A genuinely uncoupled amplitude has no phase-dependence
    at all, which requires no modulation, not merely a different modulating phase.
    """
    rng = np.random.default_rng(seed)
    n = int(n_seconds * sfreq)
    t = np.arange(n) / sfreq
    low_phase_offset = rng.uniform(0, 2 * np.pi)
    low = np.sin(2 * np.pi * 1.0 * t + low_phase_offset)
    high_phase_offset = rng.uniform(0, 2 * np.pi)
    if coupled:
        env = 1.0 + 0.9 * np.cos(2 * np.pi * 1.0 * t + low_phase_offset)
    else:
        env = 1.0                                   # no amplitude modulation at all -> no PAC by construction
    high = env * np.sin(2 * np.pi * 10.0 * t + high_phase_offset)
    x = 1.0 * low + 1.0 * high + 0.05 * rng.normal(size=n)
    return x


def test_pac_high_for_known_coupled_signal():
    x = _pac_signal(60.0, SF, coupled=True, seed=20)
    mi = phase_amplitude_coupling(x, SF)
    assert np.isfinite(mi)
    assert 0.0 <= mi <= 1.0
    assert mi > 0.05, f"MI too low for a constructed, strongly-coupled signal: {mi}"


def test_pac_low_for_independent_phases():
    mis = []
    for seed in range(21, 26):
        x = _pac_signal(60.0, SF, coupled=False, seed=seed)
        mi = phase_amplitude_coupling(x, SF)
        assert np.isfinite(mi)
        assert 0.0 <= mi <= 1.0
        mis.append(mi)
    assert np.mean(mis) < 0.01, f"MI too high for independent-phase signals: {mis}"


def test_pac_flat_and_too_short_are_nan():
    flat = np.zeros(int(60 * SF))
    assert np.isnan(phase_amplitude_coupling(flat, SF))
    too_short = np.random.default_rng(27).normal(size=50)
    assert np.isnan(phase_amplitude_coupling(too_short, SF))


# =========================================================================================================
# 4. subband_exponents
# =========================================================================================================

def _two_slope_signal(n, sfreq, exp_low, exp_high, crossover_hz=20.0, seed=0):
    """Constructed directly in the frequency domain: amplitude spectrum shaped as f^(-exp_low/2) below
    `crossover_hz` and, continuously at the crossover, f^(-exp_high/2) above it -- i.e. PSD ~ 1/f^exp_low
    below the crossover and ~ 1/f^exp_high above.
    """
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(n, 1.0 / sfreq)
    spec = rng.normal(size=freqs.size) + 1j * rng.normal(size=freqs.size)
    scale = np.zeros_like(freqs)
    nz = freqs > 0
    lo = freqs <= crossover_hz
    hi = freqs > crossover_hz
    scale[nz & lo] = freqs[nz & lo] ** (-exp_low / 2.0)
    # continuous at the crossover: match the low-branch value there, then continue with the high exponent.
    c = crossover_hz ** (-exp_low / 2.0) / (crossover_hz ** (-exp_high / 2.0))
    scale[nz & hi] = c * freqs[nz & hi] ** (-exp_high / 2.0)
    x = np.fft.irfft(spec * scale, n=n)
    sd = x.std()
    return x / (sd if sd > 0 else 1.0)


def test_subband_exponents_recovers_both_slopes():
    sfreq = 250.0
    n = int(120 * sfreq)
    x = _two_slope_signal(n, sfreq, exp_low=1.0, exp_high=3.0, seed=30)
    out = subband_exponents(x, sfreq)
    assert np.isfinite(out["exponent_low"]) and np.isfinite(out["exponent_high"])
    assert abs(out["exponent_low"] - 1.0) < 0.5, out
    assert abs(out["exponent_high"] - 3.0) < 0.5, out
    # the whole point of the feature: the two bands must differ from each other, not report the same number twice
    assert out["exponent_high"] - out["exponent_low"] > 1.0, out


def test_subband_exponents_flat_and_too_short_are_nan():
    out = subband_exponents(np.zeros(int(120 * SF)), SF)
    assert np.isnan(out["exponent_low"]) and np.isnan(out["exponent_high"])
    out2 = subband_exponents(np.random.default_rng(31).normal(size=10), SF)
    assert np.isnan(out2["exponent_low"]) and np.isnan(out2["exponent_high"])


# =========================================================================================================
# 5. critical_slowing
# =========================================================================================================

def test_critical_slowing_smooth_signal_has_higher_ar1_than_white_noise():
    sfreq = 250.0
    n = int(20 * sfreq)
    t = np.arange(n) / sfreq
    slow_env = 1.0 + 0.9 * np.sin(2 * np.pi * 0.05 * t)          # 20 s period: very slow envelope
    smooth = slow_env * np.sin(2 * np.pi * 10.0 * t)
    rng = np.random.default_rng(40)
    noise = rng.normal(size=n)

    r_smooth = critical_slowing(smooth, sfreq)
    r_noise = critical_slowing(noise, sfreq)
    for r in (r_smooth, r_noise):
        assert -1.0 <= r["ar1"] <= 1.0, r
    assert r_smooth["ar1"] > r_noise["ar1"], (r_smooth, r_noise)


def test_critical_slowing_flat_and_too_short_are_nan():
    flat = np.zeros(int(20 * SF))
    out = critical_slowing(flat, SF)
    assert np.isnan(out["ar1"]) and np.isnan(out["envelope_variance"])
    too_short = np.random.default_rng(41).normal(size=50)
    out2 = critical_slowing(too_short, SF)
    assert np.isnan(out2["ar1"]) and np.isnan(out2["envelope_variance"])
