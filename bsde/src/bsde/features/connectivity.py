"""Phase-lag connectivity between a pair of 1-D signals: (debiased) weighted phase-lag index.

CONVENTION, matching `aperiodic.py`: plain numpy, no scipy/sklearn, functions not classes.

An earlier wPLI implementation lives at `pipeline/features.py::_compute_wpli`. It operates on
already-epoched, multi-channel mne-derived arrays (fixed non-overlapping windows supplied by the caller,
all channel pairs at once) and pools the cross-spectrum's imaginary part jointly across windows *and*
frequency bins within a band. This module keeps its spirit — Im(cross-spectrum) is the fundamental
quantity, `wPLI = |E[Im(S)]| / E[|Im(S)|]` is the same statistic — but is written for a plain pair of 1-D
arrays with its own Welch-style overlapping Hann-windowed segmentation (no mne, no caller-supplied epochs),
and it pools the imaginary part of the cross-spectrum jointly across segments *and* the frequency bins
inside the requested band before forming a single ratio -- exactly the pooling `_compute_wpli` uses, and
for the same reason: a per-frequency ratio averaged equally across bins would let bins with negligible
cross-power (pure leakage/noise, phase essentially random) dilute a genuine narrowband effect one-for-one
with the bin that actually carries it; pooling the raw sums lets each bin contribute in proportion to its
own cross-spectral magnitude instead.

Sign convention: the debiased estimator can be (and, for a pair of unrelated signals, often is) mildly
negative — that is the bias correction working as intended, not a bug. It is returned signed, not clipped
to zero.
"""
from __future__ import annotations

import numpy as np


def wpli(x: np.ndarray, y: np.ndarray, sfreq: float, lo_hz: float, hi_hz: float,
        window_s: float = 2.0, overlap: float = 0.5, debias: bool = True) -> float:
    """(Debiased) weighted phase-lag index between `x` and `y` over `[lo_hz, hi_hz]`.

    Segments both signals identically (Welch-style, Hann-windowed, `window_s` long, `overlap` fraction
    overlapping), forms the cross-spectrum `X * conj(Y)` per segment via `np.fft.rfft`, and reduces its
    imaginary part per frequency bin across segments:

        wPLI  = | E[Im(S)] | / E[|Im(S)|]
        dWPLI = ( (sum Im(S))^2 - sum Im(S)^2 ) / ( (sum |Im(S)|)^2 - sum Im(S)^2 )

    where the sums/expectations run over every (segment, frequency-bin) pair inside `[lo_hz, hi_hz]`.
    (`dWPLI` is the standard debiased estimator: both numerator and denominator are the "square of a sum
    minus sum of squares" identity for `sum_{j != k} a_j a_k`, applied to the raw and absolute imaginary
    parts respectively -- this removes the same-observation self-product that biases the plain estimator
    towards nonzero values under the null.)

    Returns `float("nan")` if there are fewer than 2 complete segments, or if no frequency bin in the band
    has a usable (nonzero) denominator.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = min(x.size, y.size)
    x, y = x[:n], y[:n]
    nper = int(round(window_s * sfreq))
    if nper < 8 or n < nper:
        return float("nan")
    step = max(1, int(nper * (1.0 - overlap)))
    win = np.hanning(nper)
    starts = list(range(0, n - nper + 1, step))
    if len(starts) < 2:
        return float("nan")

    freqs = np.fft.rfftfreq(nper, 1.0 / sfreq)
    band = (freqs >= lo_hz) & (freqs <= hi_hz)
    if band.sum() < 1:
        return float("nan")

    Xs = np.empty((len(starts), band.sum()), complex)
    Ys = np.empty((len(starts), band.sum()), complex)
    for row, st in enumerate(starts):
        xs = (x[st:st + nper] - x[st:st + nper].mean()) * win
        ys = (y[st:st + nper] - y[st:st + nper].mean()) * win
        Xs[row] = np.fft.rfft(xs)[band]
        Ys[row] = np.fft.rfft(ys)[band]

    S = Xs * np.conj(Ys)
    Im = np.imag(S).ravel()               # pooled across segments AND frequency bins in the band

    sum_im = Im.sum()
    sum_im2 = (Im ** 2).sum()
    sum_absim = np.abs(Im).sum()

    if debias:
        denom = sum_absim ** 2 - sum_im2
        numer = sum_im ** 2 - sum_im2
        if denom <= 1e-30:
            return float("nan")
        return float(numer / denom)
    else:
        if sum_absim <= 1e-30:
            return float("nan")
        return float(abs(sum_im) / sum_absim)
