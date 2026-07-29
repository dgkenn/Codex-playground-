"""Synthetic EEG with a KNOWN aperiodic exponent — the ground truth the pipeline is validated against.

WHY THIS IS THE FIRST MODULE WRITTEN. The project's central feature is the aperiodic exponent, and every
downstream claim inherits its accuracy. An exponent estimator can be wrong in ways that are invisible on real
data: it can be biased by the fit range, by oscillatory peaks sitting inside that range, by line noise, or by
broadband EMG. On real EEG there is nothing to check the answer against. Here there is.

`docs/RESEARCH_STRATEGY.md` §6 makes this Gate A: a pipeline that cannot recover a known exponent from
simulated data has no business estimating one from a patient.

WHAT IS SIMULATED, and each is a threat the estimator must survive:
  * a 1/f^beta aperiodic background with a specified beta            (the quantity to recover)
  * optional narrowband oscillatory peaks (alpha, beta)              (peaks bias a naive log-log fit)
  * optional broadband high-frequency noise standing in for EMG      (flattens the spectrum -> lowers beta)
  * optional 50/60 Hz line noise                                     (a spike inside a wide fit range)
  * optional burst-suppression gating                                (non-stationarity; ICU reality)

Everything is seeded and deterministic. No `hash()` is used for seeding anywhere in this project (Python salts
string hashes per process, which silently breaks reproducibility only on the randomised paths).
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def pink_noise(n: int, sfreq: float, exponent: float, rng: np.random.Generator) -> np.ndarray:
    """Gaussian noise whose PSD follows 1/f**exponent.

    Built by shaping the amplitude spectrum of white noise: PSD ∝ |A(f)|², so to obtain
    PSD ∝ f^-exponent the amplitude must be scaled by f^(-exponent/2).
    """
    if n < 8:
        raise ValueError("n too small")
    freqs = np.fft.rfftfreq(n, 1.0 / sfreq)
    spec = rng.normal(size=freqs.size) + 1j * rng.normal(size=freqs.size)
    scale = np.zeros_like(freqs)
    nz = freqs > 0
    scale[nz] = freqs[nz] ** (-exponent / 2.0)
    scale[0] = 0.0                      # no DC: a DC offset is not part of the aperiodic slope
    x = np.fft.irfft(spec * scale, n=n)
    sd = x.std()
    return x / (sd if sd > 0 else 1.0)


def add_oscillation(x: np.ndarray, sfreq: float, freq: float, amp: float,
                    rng: np.random.Generator, bandwidth: float = 2.0) -> np.ndarray:
    """Add a narrowband oscillatory bump (filtered noise, not a pure sinusoid — more realistic)."""
    n = len(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sfreq)
    spec = rng.normal(size=freqs.size) + 1j * rng.normal(size=freqs.size)
    env = np.exp(-0.5 * ((freqs - freq) / max(bandwidth, 1e-9)) ** 2)
    osc = np.fft.irfft(spec * env, n=n)
    sd = osc.std()
    return x + amp * osc / (sd if sd > 0 else 1.0)


def burst_suppression_gate(x: np.ndarray, sfreq: float, burden: float,
                           rng: np.random.Generator, mean_run_s: float = 2.0,
                           supp_amp: float = 0.03) -> np.ndarray:
    """Multiply by a two-state (burst / suppressed) envelope with the requested suppression burden."""
    if not 0.0 <= burden <= 1.0:
        raise ValueError("burden must be in [0, 1]")
    n = len(x)
    run = max(1, int(mean_run_s * sfreq))
    gate = np.ones(n)
    i = 0
    while i < n:
        L = max(1, int(rng.exponential(run)))
        if rng.random() < burden:
            gate[i:i + L] = supp_amp
        i += L
    return x * gate


def simulate_channel(n_seconds: float, sfreq: float, exponent: float, rng: np.random.Generator,
                     peaks: Sequence[tuple[float, float]] = (),
                     emg_amp: float = 0.0, line_hz: float | None = None,
                     line_amp: float = 0.0, bs_burden: float = 0.0) -> np.ndarray:
    """One synthetic channel with a known aperiodic `exponent`.

    peaks: sequence of (centre_hz, amplitude_in_sd_units).
    emg_amp: amplitude of broadband 20-90 Hz noise, the classic exponent contaminant.
    """
    n = int(round(n_seconds * sfreq))
    x = pink_noise(n, sfreq, exponent, rng)
    for f0, amp in peaks:
        x = add_oscillation(x, sfreq, f0, amp, rng)
    if emg_amp > 0:
        # EMG modelled as band-limited high-frequency noise: it raises the high-frequency floor and so
        # FLATTENS the log-log slope, biasing the estimated exponent DOWNWARD.
        n_f = np.fft.rfftfreq(n, 1.0 / sfreq)
        spec = rng.normal(size=n_f.size) + 1j * rng.normal(size=n_f.size)
        band = ((n_f >= 20) & (n_f <= min(90, sfreq / 2 - 1))).astype(float)
        emg = np.fft.irfft(spec * band, n=n)
        sd = emg.std()
        x = x + emg_amp * emg / (sd if sd > 0 else 1.0)
    if line_hz and line_amp > 0:
        t = np.arange(n) / sfreq
        x = x + line_amp * np.sin(2 * np.pi * line_hz * t + rng.uniform(0, 2 * np.pi))
    if bs_burden > 0:
        x = burst_suppression_gate(x, sfreq, bs_burden, rng)
    return x


def simulate_recording(n_channels: int = 8, n_seconds: float = 60.0, sfreq: float = 250.0,
                       exponent: float | Iterable[float] = 1.5, seed: int = 0,
                       ch_names: Sequence[str] | None = None, **kwargs) -> tuple[np.ndarray, list[str], float]:
    """Multi-channel synthetic recording. `exponent` may be a scalar or one value per channel.

    Returns (data[n_channels, n_samples], ch_names, sfreq).
    """
    rng = np.random.default_rng(seed)
    exps = ([float(exponent)] * n_channels if np.isscalar(exponent)
            else [float(e) for e in exponent])          # type: ignore[arg-type]
    if len(exps) != n_channels:
        raise ValueError("exponent must be scalar or length n_channels")
    if ch_names is None:
        default = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
                   "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6", "Fz", "Cz", "Pz"]
        ch_names = [default[i % len(default)] for i in range(n_channels)]
    data = np.vstack([simulate_channel(n_seconds, sfreq, e,
                                       np.random.default_rng(seed * 1000 + i), **kwargs)
                      for i, e in enumerate(exps)])
    return data, list(ch_names), sfreq
