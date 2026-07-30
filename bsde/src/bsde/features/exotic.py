"""Five features borrowed from outside EEG/anaesthesia research, each smuggled in because a specific gap in
this project's existing candidates cannot be closed by anything already here. Every one of them is a genuine
import from another field's toolbox, not a relabelling of something already computed.

CONVENTION, matching `aperiodic.py`/`complexity.py`: `from __future__ import annotations`, numpy at module
level, plain functions not classes. Two of the five (`phase_amplitude_coupling`, `critical_slowing`) need a
zero-phase bandpass filter and the analytic-signal envelope; hand-rolling a stable Butterworth+filtfilt would
be reinventing a delicate piece of numerical code that scipy already gets right, so — matching how
`candidates/seed.py` and `test_emg_index.py::_lowpass` already do it in this repo — `scipy.signal` is
imported LAZILY, inside the functions that need it, not at module level. This keeps the integrity-core-only
import chain the project relies on elsewhere unaffected, while still letting these two functions use the
already-declared scipy dependency instead of a hand-rolled filter.

WHAT EACH ONE IS FOR:

  spatial_participation_ratio   — every existing candidate is a per-channel spectral summary averaged across
                                  channels, discarding spatial structure entirely. Tests whether spatial
                                  information is genuinely absent or merely thrown away. From systems
                                  neuroscience dimensionality analysis.
  multiscale_entropy_slope      — the project's single-timescale Lempel-Ziv result rises with anaesthetic
                                  dose, opposite to the complexity literature. A slope across timescales says
                                  AT WHICH timescale complexity changes, which one number at one scale cannot.
  phase_amplitude_coupling      — a genuinely cross-frequency quantity; no band-power or spectral-slope
                                  measure can express it. Propofol has a documented slow-wave-to-alpha PAC
                                  signature. From hippocampal memory research.
  subband_exponents             — Colombo et al. (PMID 30639334) find the drug dissociation in the aperiodic
                                  exponent lives specifically in 20-40 Hz, not 1-20 Hz. This project fits a
                                  single 1-40 Hz exponent, which averages that away.
  critical_slowing              — rising lag-1 autocorrelation and rising variance are the canonical
                                  early-warning signals for an approaching tipping point, from ecology and
                                  climate-system science. A prior experiment here found no pre-awakening
                                  precursor using conventional features; these are what that field would use.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from bsde.features.aperiodic import fit_aperiodic, welch_psd


# =========================================================================================================
# 1. Spatial participation ratio
# =========================================================================================================

def spatial_participation_ratio_raw(data: np.ndarray) -> float:
    """Effective dimensionality of the multichannel state, UNNORMALISED: `(sum lambda)^2 / sum(lambda^2)`
    over the eigenvalues of the channel covariance matrix. Ranges from 1 (all channels perfectly correlated,
    a single effective dimension) to n_channels (fully independent channels).

    `data` is `[n_channels, n_samples]`. Returns NaN for fewer than 2 channels, fewer than 2 samples, any
    non-finite sample, or a degenerate (all-zero / flat) covariance matrix — a flat signal has no spatial
    structure to measure, and dividing by a near-zero `sum(lambda^2)` would otherwise produce a meaningless
    huge or undefined ratio rather than an honest "not measurable".
    """
    d = np.atleast_2d(np.asarray(data, float))
    n_channels, n_samples = d.shape
    if n_channels < 2 or n_samples < 2:
        return float("nan")
    if not np.all(np.isfinite(d)):
        return float("nan")
    cov = np.cov(d)
    eigvals = np.linalg.eigvalsh(cov)
    # Numerical noise can make a nominally-zero eigenvalue slightly negative; clip before summing squares.
    eigvals = np.clip(eigvals, 0.0, None)
    s1 = float(eigvals.sum())
    s2 = float((eigvals ** 2).sum())
    if s1 <= 1e-24 or s2 <= 1e-24:
        return float("nan")
    return (s1 ** 2) / s2


def spatial_participation_ratio(data: np.ndarray) -> float:
    """`spatial_participation_ratio_raw` divided by `n_channels`, so the result is comparable across
    montages with different electrode counts. Lands in `(0, 1]`: near 0 for a highly redundant array (one
    effective dimension out of many channels), 1.0 for fully independent channels.
    """
    raw = spatial_participation_ratio_raw(data)
    if not np.isfinite(raw):
        return float("nan")
    n_channels = np.atleast_2d(np.asarray(data, float)).shape[0]
    return float(raw / n_channels)


# =========================================================================================================
# 2. Multiscale entropy slope
# =========================================================================================================

def _count_chebyshev_matches(emb: np.ndarray, r: float) -> float:
    """Count ordered pairs `(i, j)`, `i != j`, of embedding vectors within Chebyshev distance `r`.

    Vectorised one embedding-dimension at a time (dimension is small: `m` or `m+1`, never more than a few)
    rather than materialising a full `(n_vec, n_vec, dim)` array, which for `n_vec` ~ 4000 would need several
    hundred MB per call; this way only one `(n_vec, n_vec)` matrix is live at a time.
    """
    n_vec, dim = emb.shape
    max_diff = np.zeros((n_vec, n_vec))
    for k in range(dim):
        col = emb[:, k]
        d = np.abs(col[:, None] - col[None, :])
        if k == 0:
            max_diff = d
        else:
            np.maximum(max_diff, d, out=max_diff)
    matches = max_diff <= r
    return float(matches.sum() - n_vec)     # subtract the diagonal (i == j is always a "match")


def sample_entropy(x: np.ndarray, m: int = 2, r: float | None = None, r_frac: float = 0.2) -> float:
    """Sample entropy (Richman & Moorman 2000): `-log(A / B)`, where `B` counts template matches of length
    `m` and `A` counts matches of length `m + 1`, both using Chebyshev distance and tolerance `r`, both
    counted over the SAME index range so the two counts are directly comparable (a length-`(m+1)` template
    needs a point a length-`m` template does not, so both use only the first `n - m` starting indices).

    `r`: absolute tolerance. If not given, computed as `r_frac * std(x)` from THIS series — for
    `multiscale_entropy_slope` the caller instead fixes `r` once from the original series and passes it
    unchanged at every scale (see that function's docstring for why this matters).

    Returns NaN — never `inf` or a divide-by-zero — when `B` or `A` is zero (the series is too short, too
    tolerant a threshold matches nothing, or a too-tight one matches everything into zero countable pairs).
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = x.size
    if r is None:
        sd = x.std()
        if sd <= 0:
            return float("nan")
        r = r_frac * sd
    if r <= 0 or n < m + 2:
        return float("nan")
    n_vec = n - m
    if n_vec < 2:
        return float("nan")
    # length-m templates: first n_vec of the (n - m + 1) possible windows, dropping the final one (it has
    # no length-(m+1) counterpart within the series).
    emb_m = np.lib.stride_tricks.sliding_window_view(x, m)[:n_vec]
    emb_m1 = np.lib.stride_tricks.sliding_window_view(x, m + 1)          # exactly n_vec windows
    b_count = _count_chebyshev_matches(emb_m, r)
    a_count = _count_chebyshev_matches(emb_m1, r)
    if a_count <= 0 or b_count <= 0:
        return float("nan")
    return float(-np.log(a_count / b_count))


def _coarse_grain(x: np.ndarray, scale: int) -> np.ndarray:
    """Non-overlapping block-average coarse-graining (Costa et al. 2002), scale in SAMPLES."""
    n = x.size
    n_blocks = n // scale
    if n_blocks < 1:
        return np.array([])
    return x[:n_blocks * scale].reshape(n_blocks, scale).mean(axis=1)


def multiscale_entropy_slope(x: np.ndarray, sfreq: float, scales: tuple = (1, 2, 4, 8, 16),
                             m: int = 2, r_frac: float = 0.2, max_samples: int = 4000) -> float:
    """Slope (least squares) of sample entropy against `log2(scale)` across `scales`, `scale` in samples of
    the coarse-grained series (the standard multiscale-entropy convention counts scale in samples, not
    seconds — `sfreq` is accepted for API consistency with the rest of this module and is not otherwise
    used; nothing here needs a physical time unit).

    `r` — the tolerance used for sample entropy at EVERY scale — is computed ONCE from the std of the
    ORIGINAL (scale-1) series and held FIXED. This is the Costa et al. convention, and it is not an arbitrary
    choice: recomputing `r` per scale would rescale the tolerance to the coarse-grained series' own,
    shrinking, variance, and the resulting "entropy" would then be measuring how the series' variance falls
    with coarse-graining rather than how its irregularity falls — a different quantity with the same name.

    Returns NaN if fewer than 2 scales yield a usable (finite) sample entropy, or if the input is too short
    or has zero variance (a flat signal has no entropy at any scale to slope between).
    """
    # LENGTH IS PART OF THE DEFINITION, not a performance knob. Sample entropy's value depends on series
    # length, so computing it on whatever number of samples a recording happens to supply makes the measure
    # partly a function of recording duration -- and duration is outcome-related in clinical cohorts, which
    # buries a confound inside the feature where no probe can see it. This is the same defect that was found
    # and fixed in Lempel-Ziv (MASTER_PLAN section 9 / the LZ decimation commit); capping the length here
    # applies that lesson rather than rediscovering it.
    #
    # It is also what makes the feature computable at all: sample entropy is quadratic in n, so 10,000
    # samples cost about 28 s per channel, i.e. 56 hours for one 80-recording 91-channel dataset. 4,000
    # samples is within the range this measure is conventionally used on and costs a small fraction of that.
    x = np.asarray(x, float).ravel()
    if max_samples and x.size > max_samples:
        x = x[:max_samples]
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 50:
        return float("nan")
    sd = x.std()
    if sd <= 0:
        return float("nan")
    r = r_frac * sd
    log2_scales, sampens = [], []
    for s in scales:
        cg = _coarse_grain(x, s)
        if cg.size < m + 2:
            continue
        se = sample_entropy(cg, m=m, r=r)
        if np.isfinite(se):
            log2_scales.append(np.log2(s))
            sampens.append(se)
    if len(sampens) < 2:
        return float("nan")
    A = np.vstack([log2_scales, np.ones(len(log2_scales))]).T
    coef, *_ = np.linalg.lstsq(A, np.array(sampens), rcond=None)
    return float(coef[0])


# =========================================================================================================
# 3. Phase-amplitude coupling (Tort et al. modulation index)
# =========================================================================================================

def _bandpass_filtfilt(x: np.ndarray, sfreq: float, lo_hz: float, hi_hz: float, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth bandpass. Raises (caller catches) if the signal is too short for `filtfilt`'s
    padding or the band is not a valid sub-Nyquist range — both are "not measurable", not a crash worth
    surfacing past this module.
    """
    from scipy.signal import butter, filtfilt
    nyq = sfreq / 2.0
    lo_n, hi_n = lo_hz / nyq, hi_hz / nyq
    if not (0.0 < lo_n < hi_n < 1.0):
        raise ValueError(f"band [{lo_hz}, {hi_hz}] Hz is not a valid sub-Nyquist range at sfreq={sfreq}")
    b, a = butter(order, [lo_n, hi_n], btype="band")
    return filtfilt(b, a, x)


def phase_amplitude_coupling(x: np.ndarray, sfreq: float, phase_band: tuple = (0.5, 2.0),
                             amp_band: tuple = (8.0, 13.0), n_bins: int = 18) -> float:
    """Tort et al. (2010) modulation index between `phase_band`'s phase and `amp_band`'s envelope.

    Bandpass to `phase_band`, take the Hilbert phase; bandpass to `amp_band`, take the Hilbert envelope; bin
    the mean envelope by phase into `n_bins` equal bins over `[-pi, pi]`; the modulation index is the
    Kullback-Leibler divergence of the normalised binned-envelope distribution from uniform, divided by
    `log(n_bins)` so the result lands in `[0, 1]` — 0 for an envelope uniformly distributed across phase (no
    coupling), approaching 1 as the envelope concentrates into a single phase bin.

    Returns NaN if the input is too short to filter, has zero variance, or if the filtered signal ends up
    with no power in some intermediate step (all degenerate-input cases collapse to "not measurable").
    """
    from scipy.signal import hilbert
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < int(4 * sfreq) or x.std() <= 0:
        return float("nan")
    try:
        phase_sig = _bandpass_filtfilt(x, sfreq, phase_band[0], phase_band[1])
        amp_sig = _bandpass_filtfilt(x, sfreq, amp_band[0], amp_band[1])
    except Exception:
        return float("nan")
    if not (np.all(np.isfinite(phase_sig)) and np.all(np.isfinite(amp_sig))):
        return float("nan")
    phase = np.angle(hilbert(phase_sig))
    amp = np.abs(hilbert(amp_sig))

    bin_edges = np.linspace(-np.pi, np.pi, n_bins + 1)
    bin_idx = np.clip(np.digitize(phase, bin_edges) - 1, 0, n_bins - 1)
    mean_amp = np.zeros(n_bins)
    for b in range(n_bins):
        mask = bin_idx == b
        if mask.any():
            mean_amp[b] = amp[mask].mean()
    total = mean_amp.sum()
    if total <= 0:
        return float("nan")
    p = mean_amp / total
    nz = p > 0
    h = float(-np.sum(p[nz] * np.log(p[nz])))
    mi = (np.log(n_bins) - h) / np.log(n_bins)
    return float(np.clip(mi, 0.0, 1.0))


# =========================================================================================================
# 4. Sub-band aperiodic exponents
# =========================================================================================================

def subband_exponents(x: np.ndarray, sfreq: float) -> Dict[str, float]:
    """Aperiodic exponent fit separately over 1-20 Hz and 20-40 Hz, reusing `welch_psd`/`fit_aperiodic` from
    `aperiodic.py` rather than reimplementing either — this is deliberately the SAME estimator the project's
    single-band (1-40 Hz) exponent uses, applied twice, so a difference between `exponent_low` and
    `exponent_high` can only reflect the spectrum, not a different fitting method.

    Colombo et al. (PMID 30639334) report the drug dissociation lives specifically in 20-40 Hz; a single
    1-40 Hz fit averages the two bands together and would wash that out. Returns
    `{"exponent_low": ..., "exponent_high": ...}`, each NaN if `welch_psd` cannot run (signal too short) or
    `fit_aperiodic` finds too few usable points in that sub-band (e.g. an all-zero signal has zero power
    everywhere, which `fit_aperiodic` already treats as unfittable).
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    try:
        freqs, psd = welch_psd(x, sfreq)
    except Exception:
        return {"exponent_low": float("nan"), "exponent_high": float("nan")}
    low = fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=20.0)
    high = fit_aperiodic(freqs, psd, fit_lo_hz=20.0, fit_hi_hz=40.0)
    return {"exponent_low": low["exponent"], "exponent_high": high["exponent"]}


# =========================================================================================================
# 5. Critical slowing down
# =========================================================================================================

CS_MAX_HZ = 250.0
"""Rate above which a recording is DECIMATED before the envelope is computed. Purely a numerical-conditioning
bound -- a 1-45 Hz Butterworth at 5 kHz is ill-conditioned. Recordings at or below this rate are left alone;
nothing is ever upsampled. See `critical_slowing`."""

CS_LAG_S = 0.02
"""The autocorrelation lag, in SECONDS. This is the part of the definition that makes the measure comparable
across deposits, and it is 20 ms rather than something shorter because 20 ms must be RESOLVABLE at the lowest
sampling rate this project reads: 2 samples at Sleep-EDF's 100 Hz, 5 at Chennu's 250 Hz, 100 at ds005620's
5 kHz (before decimation). A shorter lag would round to zero samples at 100 Hz and return a trivial 1.0."""


def critical_slowing(x: np.ndarray, sfreq: float, env_band: tuple = (1.0, 45.0),
                     window_s: float = 2.0) -> Dict[str, float]:
    """Lag-1 autocorrelation and variance of the broadband amplitude envelope, the two canonical
    early-warning signals for an approaching critical transition (bifurcation theory / ecology / climate
    tipping points): as a system's relaxation rate slows on approach to a transition, both its
    autocorrelation and its variance rise.

    Bandpass to `env_band`, take the Hilbert envelope, split into non-overlapping `window_s`-long windows,
    compute the autocorrelation at a lag of CS_LAG_S SECONDS -- not one sample -- and the variance PER
    WINDOW, then return the mean of each across windows. The lag is in seconds because the whole point of a
    cross-deposit comparison is that the same physical dynamics give the same number; see the block comment
    in the body for what happened when it was in samples.
    Per-window rather than one autocorrelation over the whole series so the result reflects LOCAL dynamics
    (what the early-warning-signal literature actually tracks) rather than one number dominated by whatever
    slow drift happens to span the longest stretch.

    Returns `{"ar1": nan, "envelope_variance": nan}` if the input is too short for even 2 windows, has zero
    variance, or a window's envelope is itself flat (no variance to correlate).
    """
    from scipy.signal import hilbert
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]

    # TWO SEPARATE RATE DEFECTS, TWO SEPARATE REMEDIES. This is the THIRD time this project has hit the same
    # bug class (Lempel-Ziv's window in seconds, multiscale entropy's series length, now this), and the first
    # attempt at fixing it conflated the two problems into one resample, which fixed only half.
    #
    # DEFECT 1 -- the lag was lag-1 in SAMPLES, so it measured a different physical interval at every rate:
    #   0.2 ms at ds005620's 5 kHz against 10 ms at Sleep-EDF's 100 Hz. The envelope of ordinary EEG is
    #   almost perfectly autocorrelated at 0.2 ms and only moderately so at 10 ms, so the SAME signal
    #   returns ~0.9999 at one rate and far less at another. `layer_cross_domain` compares deposits, so this
    #   would have compared acquisition systems and called the difference biology.
    #   REMEDY: the lag is CS_LAG_S SECONDS, converted to samples per recording. Not a resample -- a
    #   definition. Resampling to a common rate would have fixed this only for rates ABOVE the target and
    #   would have had to UPSAMPLE 100 Hz to 250 Hz, manufacturing a 4 ms correlation that the recording
    #   never observed. Interpolation cannot supply information the sampler did not capture, and an
    #   interpolated autocorrelation reports the interpolator's smoothness, not the brain's.
    #
    # DEFECT 2 -- a 1-45 Hz Butterworth at 5 kHz sits at 0.0004-0.018 of Nyquist, where the filter is
    #   numerically ill-conditioned; on real ds005620 data the envelope variance overflowed to ~1e37. Not a
    #   subtle bias, a broken filter, and invisible at Chennu's 250 Hz.
    #   REMEDY: decimate to CS_MAX_HZ, and ONLY downward. This is about conditioning, nothing else, and it
    #   discards no envelope information: a 1-45 Hz signal's envelope is bandlimited well inside 250 Hz.
    if sfreq > CS_MAX_HZ * 1.01:
        from math import gcd
        up, down = int(round(CS_MAX_HZ)), int(round(sfreq))
        g = gcd(up, down)
        try:
            from scipy.signal import resample_poly
            x = resample_poly(x, up // g, down // g)
        except Exception:
            return {"ar1": float("nan"), "envelope_variance": float("nan")}
        sfreq = CS_MAX_HZ

    lag = int(round(CS_LAG_S * sfreq))
    nper = int(round(window_s * sfreq))
    if lag < 1 or nper < lag * 4 or x.size < nper * 2 or x.std() <= 0:
        return {"ar1": float("nan"), "envelope_variance": float("nan")}
    try:
        filt = _bandpass_filtfilt(x, sfreq, env_band[0], env_band[1])
    except Exception:
        return {"ar1": float("nan"), "envelope_variance": float("nan")}
    if not np.all(np.isfinite(filt)):
        return {"ar1": float("nan"), "envelope_variance": float("nan")}
    env = np.abs(hilbert(filt))

    n_wins = env.size // nper
    if n_wins < 2:
        return {"ar1": float("nan"), "envelope_variance": float("nan")}
    ar1s, variances = [], []
    for i in range(n_wins):
        w = env[i * nper:(i + 1) * nper]
        v = float(w.var())
        variances.append(v)
        w0 = w[:-lag] - w[:-lag].mean()
        w1 = w[lag:] - w[lag:].mean()
        denom = np.sqrt((w0 ** 2).sum() * (w1 ** 2).sum())
        if denom > 1e-20:
            ar1s.append(float((w0 * w1).sum() / denom))
    if not ar1s:
        return {"ar1": float("nan"), "envelope_variance": float("nan")}
    return {"ar1": float(np.mean(ar1s)), "envelope_variance": float(np.mean(variances))}
