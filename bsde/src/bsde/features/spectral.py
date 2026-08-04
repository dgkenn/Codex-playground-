"""Band-limited spectral summaries built on top of `welch_psd`.

CONVENTION, matching `aperiodic.py`: every function takes a `(freqs, psd)` pair already produced by
`welch_psd` — no function here re-estimates a PSD from raw samples. `psd` is a one-sided power spectral
density (µV²/Hz for EEG in µV), and every integral over frequency uses `np.trapezoid` (with a `np.trapz`
fallback for older numpy, since `trapezoid` only replaced the deprecated `trapz` in numpy 2.0).

Degenerate-input policy: if the requested `[lo_hz, hi_hz]` range contains fewer than 2 PSD bins (too narrow
a band for the frequency resolution of the PSD, or a range entirely outside `freqs`), every function here
returns `float("nan")` rather than raising. A silent zero would be mistaken for "no power in that band";
NaN correctly propagates as "not measurable at this resolution".
"""
from __future__ import annotations

import numpy as np

_trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz

# Standard clinical EEG band edges, in Hz, [lo, hi).
BANDS = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}


def _band_mask(freqs: np.ndarray, lo_hz: float, hi_hz: float) -> np.ndarray:
    return (freqs >= lo_hz) & (freqs <= hi_hz)


def band_power(freqs: np.ndarray, psd: np.ndarray, lo_hz: float, hi_hz: float) -> float:
    """Integral of `psd` over `[lo_hz, hi_hz]` via the trapezoidal rule."""
    freqs = np.asarray(freqs, float)
    psd = np.asarray(psd, float)
    m = _band_mask(freqs, lo_hz, hi_hz)
    if m.sum() < 2:
        return float("nan")
    return float(_trapz(psd[m], freqs[m]))


def relative_band_power(freqs: np.ndarray, psd: np.ndarray, lo_hz: float, hi_hz: float,
                        total_lo: float = 1.0, total_hi: float = 45.0) -> float:
    """`band_power(lo, hi) / band_power(total_lo, total_hi)`."""
    num = band_power(freqs, psd, lo_hz, hi_hz)
    den = band_power(freqs, psd, total_lo, total_hi)
    if not np.isfinite(num) or not np.isfinite(den) or den <= 0:
        return float("nan")
    return float(num / den)


def spectral_edge(freqs: np.ndarray, psd: np.ndarray, pct: float = 95.0,
                  lo_hz: float = 1.0, hi_hz: float = 45.0) -> float:
    """Frequency below which `pct` percent of the power in `[lo_hz, hi_hz]` lies.

    Built from the cumulative trapezoidal power curve, then linearly interpolated between the two
    bracketing bins so the result is not quantised to the PSD's frequency resolution.
    """
    freqs = np.asarray(freqs, float)
    psd = np.asarray(psd, float)
    m = _band_mask(freqs, lo_hz, hi_hz)
    if m.sum() < 2:
        return float("nan")
    f = freqs[m]
    p = psd[m]
    # Cumulative trapezoidal integral, same convention as band_power: cum[0] = 0.
    cum = np.concatenate(([0.0], np.cumsum((p[1:] + p[:-1]) / 2.0 * np.diff(f))))
    total = cum[-1]
    if total <= 0:
        return float("nan")
    target = pct / 100.0 * total
    idx = np.searchsorted(cum, target)
    if idx <= 0:
        return float(f[0])
    if idx >= len(cum):
        return float(f[-1])
    c0, c1 = cum[idx - 1], cum[idx]
    f0, f1 = f[idx - 1], f[idx]
    if c1 == c0:
        return float(f1)
    frac = (target - c0) / (c1 - c0)
    return float(f0 + frac * (f1 - f0))


def median_frequency(freqs: np.ndarray, psd: np.ndarray, lo_hz: float = 1.0, hi_hz: float = 45.0) -> float:
    """`spectral_edge` at 50 %."""
    return spectral_edge(freqs, psd, pct=50.0, lo_hz=lo_hz, hi_hz=hi_hz)


def spectral_entropy(freqs: np.ndarray, psd: np.ndarray, lo_hz: float = 1.0, hi_hz: float = 45.0,
                     normalize: bool = True) -> float:
    """Shannon entropy (base 2) of the power distribution over `[lo_hz, hi_hz]`, normalised to sum 1.

    With `normalize=True` the result is divided by log2(n_bins), giving a value in [0, 1]: exactly 1.0 for
    a perfectly flat spectrum (maximum entropy) and near 0 for power concentrated in a single bin.
    """
    freqs = np.asarray(freqs, float)
    psd = np.asarray(psd, float)
    m = _band_mask(freqs, lo_hz, hi_hz)
    n = int(m.sum())
    if n < 2:
        return float("nan")
    p = psd[m]
    total = p.sum()
    if not np.isfinite(total) or total <= 0:
        return float("nan")
    p = p / total
    nz = p > 0
    ent = float(-np.sum(p[nz] * np.log2(p[nz])))
    if normalize:
        ent = ent / np.log2(n)
    return ent
