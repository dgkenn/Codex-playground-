"""The four EEG subparameters BIS is built from, implemented from the published descriptions.

WHY THIS MODULE EXISTS. `bsde/docs/QUEUE.md` Q22: BIS is the incumbent Challenge C actually needs, and it
exists only where a monitor recorded it -- which is why E26, E34 and E37 all fell back on SEF95 as a proxy
and scoped themselves "never ahead of BIS". A computable BIS turns it into a universal comparator.

Q22's feasibility probe established the target: features this repo already computes reach a case-grouped
median absolute error of **5.01 BIS units** against device BIS, versus **4.1** published by Lee et al.
(PMID 31551487) using purpose-built subparameters -- and ours were missing three of the four real
ingredients. This module adds them.

WHAT BIS IS MADE OF. Lee et al., quoting the prior literature: *"BIS values are known to be calculated from
four EEG subparameters, burst suppression ratio (BSR), QUAZI suppression index, relative beta ratio (RBR),
and SyncFastSlow (SFS), using multiple regression equations with different weights according to the depth
of anaesthesia."* The canonical description of each is Rampil, *Anesthesiology* 1998 (PMID 9772278).

PROVENANCE AND WHAT THESE ARE NOT. These are implementations of PUBLISHED DESCRIPTIONS of the
subparameters, not the proprietary BIS algorithm and not Connor's emulator (PMID 35767469), which was
recovered by forensic disassembly. **A composite built from these is a BIS-LIKE INDEX and must never be
called BIS.** Its agreement with device BIS is an empirical question, measured on paired data, and reported
PER BIS RANGE -- Lee et al. fit range-specific models precisely because one relationship does not hold
across depth, and the extremes are where a depth monitor's disagreements matter most.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


def relative_beta_ratio(freqs: np.ndarray, psd: np.ndarray) -> float:
    """RBR = log(P[30-47 Hz] / P[11-20 Hz]).

    Rampil's description. It dominates BIS in the LIGHT sedation range, where beta activation from
    low-dose anaesthetic is the salient change. Returns NaN when either band carries no power rather than
    a signed infinity.
    """
    freqs = np.asarray(freqs, float)
    psd = np.asarray(psd, float)
    hi = psd[(freqs >= 30.0) & (freqs <= 47.0)]
    lo = psd[(freqs >= 11.0) & (freqs <= 20.0)]
    hi = hi[np.isfinite(hi) & (hi > 0)]
    lo = lo[np.isfinite(lo) & (lo > 0)]
    if hi.size < 2 or lo.size < 2:
        return float("nan")
    a, b = float(hi.sum()), float(lo.sum())
    if a <= 0 or b <= 0:
        return float("nan")
    return float(np.log(a / b))


def burst_suppression_ratio(x: np.ndarray, sfreq: float, thresh_uv: float = 5.0,
                            min_dur_s: float = 0.5) -> float:
    """BSR = fraction of the epoch spent in suppression.

    Rampil's definition: suppressed means the signal stays within +/- `thresh_uv` of baseline for at least
    `min_dur_s`. **`x` must be in MICROVOLTS** -- the 5 uV threshold is absolute, so passing volts returns
    1.0 and passing an unscaled integer returns 0.0, both silently. The repo convention is microvolts
    everywhere downstream of `features_from_raw`, and this function cannot detect a violation.

    The duration requirement is what makes this BSR rather than "fraction of samples below 5 uV": brief
    low-amplitude excursions occur constantly in normal EEG and are not suppression.

    Non-finite samples are treated as NOT suppressed, which BREAKS a run rather than joining the segments
    on either side of it (rule 27: a mask that compresses out bad samples glues time together, and run
    length is exactly the quantity gluing would corrupt).
    """
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if x.size < int(min_dur_s * sfreq) or not ok.any():
        return float("nan")
    x = x - float(np.median(x[ok]))
    low = ok & (np.abs(x) < thresh_uv)
    need = max(1, int(round(min_dur_s * sfreq)))
    # mark runs of `low` at least `need` samples long
    supp = np.zeros(x.size, bool)
    i = 0
    n = x.size
    while i < n:
        if not low[i]:
            i += 1
            continue
        j = i
        while j < n and low[j]:
            j += 1
        if (j - i) >= need:
            supp[i:j] = True
        i = j
    return float(supp.mean())


def quazi_suppression(x: np.ndarray, sfreq: float, thresh_uv: float = 5.0,
                      min_dur_s: float = 0.5, hp_hz: float = 1.0) -> float:
    """QUAZI: suppression detected AFTER removing baseline drift.

    Rampil's QUAZI exists because BSR misses suppression when a slow wave rides under it -- the raw signal
    never comes within 5 uV of baseline even though the fast activity is flat, so BSR reads 0 while the
    brain is suppressed. Detrending the slow component first recovers those periods.

    Implemented as BSR on a high-passed copy. Returns the DIFFERENCE from plain BSR, so it carries the
    information BSR misses rather than duplicating it -- two near-identical columns would be a redundancy
    the verifier would have to strip later (rule 28: two measurements are not thereby measuring different
    things).
    """
    x = np.asarray(x, float)
    if x.size < int(4 * sfreq):
        return float("nan")
    try:
        from scipy.signal import butter, filtfilt
        b, a = butter(2, hp_hz / (sfreq / 2.0), btype="highpass")
        xd = filtfilt(b, a, x)
    except Exception:                                                        # noqa: BLE001
        return float("nan")
    base = burst_suppression_ratio(x, sfreq, thresh_uv, min_dur_s)
    drift = burst_suppression_ratio(xd, sfreq, thresh_uv, min_dur_s)
    if not (np.isfinite(base) and np.isfinite(drift)):
        return float("nan")
    return float(drift - base)


def sync_fast_slow(x: np.ndarray, sfreq: float, nfft: int = 256,
                   lo_hz: float = 0.5, mid_hz: float = 40.0, hi_hz: float = 47.0) -> float:
    """SFS = log(sum of bispectrum over 0.5-47 Hz / sum of bispectrum over 40-47 Hz).

    **This is the only genuinely bispectral quantity in BIS, and the one this repo did not have.** The
    bispectrum B(f1, f2) = E[X(f1) X(f2) X*(f1+f2)] measures phase coupling between a pair of frequencies
    and their sum; a signal whose components are phase-independent has a bispectrum near zero regardless of
    how much power it carries. That is what distinguishes it from every spectral measure already here, and
    it is why the index is called BIspectral.

    Estimated by segment-averaging (Welch-style) over 50 %-overlapping windows, which is what makes the
    expectation meaningful -- a single-segment bispectrum is pure noise, because |B| of one segment is large
    whether or not the phases are related; only the AVERAGE of the complex value cancels for unrelated
    phases. The complex accumulation before `abs` is therefore load-bearing and must not be reordered.

    Segments containing any non-finite sample are SKIPPED whole rather than the bad samples being dropped
    (rule 27) -- compressing them out would splice unrelated phase across the join, which is precisely the
    quantity being measured.

    Both regions are defined on the sum frequency: the numerator is the whole bispectral triangle with
    f1, f2 >= `lo_hz` and f1 + f2 <= `hi_hz`; the denominator is its sub-region with f1 + f2 in
    [`mid_hz`, `hi_hz`]. The denominator is thus contained in the numerator and the ratio is >= 1, so SFS is
    non-negative by construction. Returns NaN when either region has no support or fewer than 4 usable
    segments survive.
    """
    x = np.asarray(x, float)
    if x.size < 4 * nfft:
        return float("nan")
    step = nfft // 2
    freqs = np.fft.rfftfreq(nfft, 1.0 / sfreq)
    nf = freqs.size
    i = np.arange(nf)
    i1, i2 = np.meshgrid(i, i, indexing="ij")
    s12 = i1 + i2
    valid = s12 < nf
    iv1, iv2, ivs = i1[valid], i2[valid], s12[valid]
    acc = np.zeros((nf, nf), complex)
    n_seg = 0
    win = np.hanning(nfft)
    for s in range(0, x.size - nfft + 1, step):
        seg = x[s:s + nfft]
        if not np.isfinite(seg).all():
            continue
        seg = (seg - seg.mean()) * win
        X = np.fft.rfft(seg)
        # B(f1,f2) = X(f1) X(f2) conj(X(f1+f2)); f1+f2 must stay inside the rfft grid
        acc[valid] += X[iv1] * X[iv2] * np.conj(X[ivs])
        n_seg += 1
    if n_seg < 4:
        return float("nan")
    B = np.abs(acc / n_seg)
    f1, f2 = np.meshgrid(freqs, freqs, indexing="ij")
    fs = f1 + f2
    full = (fs <= hi_hz) & (f1 >= lo_hz) & (f2 >= lo_hz)
    band = full & (fs >= mid_hz)
    a, c = float(B[full].sum()), float(B[band].sum())
    if a <= 0 or c <= 0:
        return float("nan")
    return float(np.log(a / c))


def bis_subparams(x: np.ndarray, sfreq: float, freqs=None, psd=None) -> Dict[str, float]:
    """All four subparameters for one channel. `x` in MICROVOLTS."""
    if freqs is None or psd is None:
        from bsde.features.aperiodic import welch_psd
        try:
            freqs, psd = welch_psd(x, sfreq)
        except Exception:                                                    # noqa: BLE001
            freqs, psd = np.array([]), np.array([])
    return {"bis_rbr": relative_beta_ratio(freqs, psd) if len(freqs) else float("nan"),
            "bis_bsr": burst_suppression_ratio(x, sfreq),
            "bis_quazi": quazi_suppression(x, sfreq),
            "bis_sfs": sync_fast_slow(x, sfreq)}
