"""features.py -- interpretable feature vector, computed in the same Pass 1 (Sec 7.4).

This is the *characterization / probing* space (Sec 10): band powers, the
aperiodic exponent + offset (specparam), spectral edge frequency, connectivity
(wPLI), entropy/complexity, and microstate parameters. It is persisted alongside
the embedding so phenotypes can be described in human-readable terms without
re-touching raw signal.

NumPy/SciPy are imported lazily. `feature_schema` is pure so the persisted
table's columns are defined and hashable without any signal.
"""
from __future__ import annotations

from typing import Any


def feature_schema(cfg: dict[str, Any]) -> list[str]:
    """Deterministic ordered list of feature-column names from the config.

    Defining the schema independently of the data lets the feature table layout
    be frozen/hashed and keeps Pass-1 rows aligned across shards.
    """
    f = cfg["features"]
    chans = cfg["model"]["channels_10_20"]
    cols: list[str] = []
    # Per-channel absolute + relative band power.
    for band in f["bands"]:
        for ch in chans:
            cols.append(f"bp_{band}_{ch}")
            cols.append(f"bprel_{band}_{ch}")
    # Aperiodic (specparam) per channel.
    for ch in chans:
        cols.append(f"aperiodic_exponent_{ch}")
        cols.append(f"aperiodic_offset_{ch}")
        cols.append(f"spectral_edge_{ch}")
    # Connectivity: upper-triangular wPLI summarised per band (global mean).
    for band in f["bands"]:
        cols.append(f"wpli_{band}_globalmean")
    # Entropy / complexity per channel.
    for ent in f.get("entropy", []):
        for ch in chans:
            cols.append(f"{ent}_{ch}")
    # Microstate parameters.
    n_states = f.get("microstates", {}).get("n_states", 4)
    for s in range(n_states):
        cols.append(f"microstate{s}_coverage")
        cols.append(f"microstate{s}_meandur")
    return cols


def compute_features(windows, sfreq: float, cfg: dict[str, Any]) -> dict[str, float]:  # pragma: no cover - needs scipy
    """Compute the interpretable feature vector for one recording.

    `windows`: (n_windows, n_channels, n_samples), already harmonized in memory.
    Returns a dict keyed by `feature_schema(cfg)`. Heavy DSP imports are local.
    """
    import numpy as np
    from scipy import signal as sps

    f = cfg["features"]
    chans = cfg["model"]["channels_10_20"]
    # Average PSD across windows (Welch per channel).
    data = np.asarray(windows, dtype="float64")
    nwin, nch, nsamp = data.shape
    freqs, psd = sps.welch(data, fs=sfreq, axis=-1,
                           nperseg=min(nsamp, int(sfreq * 2)))
    psd = psd.mean(axis=0)  # (n_channels, n_freqs)

    out: dict[str, float] = {}
    # np.trapezoid is the NumPy 2.0+ name; np.trapz was removed in 2.0.
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    total = _trapz(psd, freqs, axis=-1) + 1e-12
    for band, (lo, hi) in f["bands"].items():
        mask = (freqs >= lo) & (freqs < hi)
        bp = _trapz(psd[:, mask], freqs[mask], axis=-1)
        for i, ch in enumerate(chans):
            out[f"bp_{band}_{ch}"] = float(bp[i])
            out[f"bprel_{band}_{ch}"] = float(bp[i] / total[i])

    # Aperiodic fit (specparam) -- delegated; placeholder loglog slope here.
    lo, hi = f["specparam"]["freq_range"]
    fm = (freqs >= lo) & (freqs <= hi)
    logf = np.log10(freqs[fm] + 1e-12)
    for i, ch in enumerate(chans):
        logp = np.log10(psd[i, fm] + 1e-24)
        slope, offset = np.polyfit(logf, logp, 1)
        out[f"aperiodic_exponent_{ch}"] = float(-slope)
        out[f"aperiodic_offset_{ch}"] = float(offset)
        # Spectral edge: frequency below which `pct` of power lies.
        cdf = np.cumsum(psd[i]) / (np.sum(psd[i]) + 1e-12)
        edge_idx = int(np.searchsorted(cdf, f["spectral_edge_pct"] / 100.0))
        out[f"spectral_edge_{ch}"] = float(freqs[min(edge_idx, len(freqs) - 1)])

    # ------------------------------------------------------------------
    # wPLI (weighted Phase Lag Index) per band, global mean over channel pairs.
    #
    # Algorithm:
    #   1. For each window, compute the FFT of every channel.
    #   2. For each unordered channel pair (i, j) and each frequency bin,
    #      accumulate Im(X_i * conj(X_j)) across windows.
    #   3. wPLI = |mean_over_windows(Im(Cxy))| / mean_over_windows(|Im(Cxy)|)
    #      per frequency bin, then average over the bins in the band.
    #   4. Average the per-pair wPLI over all pairs → global mean.
    # ------------------------------------------------------------------
    _compute_wpli(data, freqs, sfreq, nwin, nch, nsamp, chans, f, out, np)

    # ------------------------------------------------------------------
    # Entropy / complexity per channel.
    #
    # The signal per channel is formed by concatenating all windows along time,
    # giving a 1-D series of length nwin * nsamp. If that exceeds MAX_SEN_SAMPLES
    # the series is uniformly subsampled to keep SampEn tractable (O(n^2)).
    # ------------------------------------------------------------------
    _compute_entropy(data, sfreq, nwin, nch, nsamp, chans, f, out, np)

    # ------------------------------------------------------------------
    # Microstates: GFP-peak topography clustering.
    #
    # Algorithm:
    #   1. Concatenate all windows into a single (nch, total_samples) matrix.
    #   2. Compute GFP (global field power) = std across channels at each sample.
    #   3. Find local GFP maxima (peaks).
    #   4. Cluster the channel-topographies at peaks with KMeans via
    #      scipy.cluster.vq.kmeans2 (no sklearn dep). Seeded from cfg["seed"].
    #   5. Assign every timepoint to its nearest microstate (by max correlation).
    #   6. coverage_s = fraction of timepoints with assignment == s.
    #      meandur_s  = mean run-length (in seconds) of contiguous assignments to s.
    # ------------------------------------------------------------------
    _compute_microstates(data, sfreq, nwin, nch, nsamp, f, out, np)

    # Safety net: any schema column not yet filled gets NaN (preserves alignment
    # if a new family is added to the schema before its implementation lands).
    for col in feature_schema(cfg):
        out.setdefault(col, float("nan"))
    return out


# ---------------------------------------------------------------------------
# Private helpers — separated so compute_features stays readable.
# All helpers receive pre-imported np and operate in-place on `out`.
# ---------------------------------------------------------------------------

def _compute_wpli(data, freqs, sfreq, nwin, nch, nsamp, chans, f, out, np):  # pragma: no cover
    """Fill wpli_{band}_globalmean entries in `out`."""
    # FFT of every window: shape (nwin, nch, nfft//2+1)
    nfft = nsamp
    # Use real FFT; match the frequency axis to np.fft.rfftfreq
    fft_freqs = np.fft.rfftfreq(nfft, d=1.0 / sfreq)
    X = np.fft.rfft(data, n=nfft, axis=-1)  # (nwin, nch, nfft//2+1)

    pairs = [(i, j) for i in range(nch) for j in range(i + 1, nch)]
    n_pairs = len(pairs)

    for band, (lo, hi) in f["bands"].items():
        band_mask = (fft_freqs >= lo) & (fft_freqs < hi)
        if not band_mask.any() or n_pairs == 0:
            out[f"wpli_{band}_globalmean"] = 0.0
            continue

        pair_wpli = []
        for (ci, cj) in pairs:
            # Cross-spectrum imaginary part across windows: (nwin, n_band_bins)
            im_cxy = np.imag(X[:, ci, :][:, band_mask] * np.conj(X[:, cj, :][:, band_mask]))
            # Average over frequency bins first, then windows
            mean_im = np.mean(im_cxy)          # scalar E[Im]
            mean_abs_im = np.mean(np.abs(im_cxy))  # scalar E[|Im|]
            denom = mean_abs_im if mean_abs_im > 1e-30 else 1e-30
            pair_wpli.append(float(abs(mean_im) / denom))

        out[f"wpli_{band}_globalmean"] = float(np.mean(pair_wpli))


def _compute_entropy(data, sfreq, nwin, nch, nsamp, chans, f, out, np):  # pragma: no cover
    """Fill {entropy_name}_{ch} entries in `out`."""
    MAX_SEN_SAMPLES = 2000  # subsample ceiling for SampEn (O(n^2) cost)

    entropy_names = f.get("entropy", [])
    if not entropy_names:
        return

    # Concatenate windows along time for each channel: (nch, nwin*nsamp)
    # data shape: (nwin, nch, nsamp)
    concat = data.transpose(1, 0, 2).reshape(nch, -1)  # (nch, total_samples)

    for ent in entropy_names:
        for i, ch in enumerate(chans):
            sig = concat[i]
            try:
                if ent == "sample_entropy":
                    val = _sample_entropy(sig, m=2, r_factor=0.2,
                                          max_samples=MAX_SEN_SAMPLES, np=np)
                elif ent == "permutation_entropy":
                    val = _permutation_entropy(sig, order=3, delay=1, np=np)
                else:
                    val = float("nan")
            except Exception:
                val = 0.0
            out[f"{ent}_{ch}"] = float(val)


def _sample_entropy(sig, m, r_factor, max_samples, np):  # pragma: no cover
    """Standard SampEn with template length m and tolerance r = r_factor * std(sig).

    The series is uniformly subsampled to at most `max_samples` points before
    computation to keep the O(n^2) cost tractable.
    Returns 0.0 if the signal is constant or too short.
    """
    # Subsample if needed
    n = len(sig)
    if n > max_samples:
        idx = np.round(np.linspace(0, n - 1, max_samples)).astype(int)
        sig = sig[idx]
        n = max_samples

    if n <= m + 1:
        return 0.0

    std_sig = float(np.std(sig))
    if std_sig < 1e-10:
        return 0.0

    r = r_factor * std_sig

    def _count_matches(templates, m_len):
        # Count pairs (i, j), i != j, where max|x[i:i+m] - x[j:j+m]| < r
        count = 0
        for i in range(n - m_len):
            # Compare template starting at i against all others
            diffs = np.abs(templates[i] - templates)  # (n-m_len, m_len)
            chebyshev = diffs.max(axis=1)
            # Exclude self-match (i == i) and the boundary template at the end
            matches = (chebyshev < r)
            matches[i] = False
            count += int(matches.sum())
        return count

    # Build template matrices
    templates_m = np.array([sig[i:i + m] for i in range(n - m + 1 - 1)])      # exclude last
    templates_m1 = np.array([sig[i:i + m + 1] for i in range(n - m + 1 - 1)])

    A = _count_matches(templates_m1, m + 1)
    B = _count_matches(templates_m, m)

    if B == 0 or A == 0:
        return 0.0
    return float(-np.log(A / B))


def _permutation_entropy(sig, order, delay, np):  # pragma: no cover
    """Normalized permutation entropy for ordinal patterns of given order and delay.

    PE = -sum(p * log(p)) / log(order!) where p are the ordinal-pattern
    probabilities. Returns a value in [0, 1].
    """
    import math
    n = len(sig)
    run_length = order * delay
    if n < run_length + 1:
        return 0.0

    # Extract all overlapping ordinal patterns
    patterns = {}
    count = 0
    for i in range(n - run_length + delay):
        sub = sig[i:i + run_length:delay]
        if len(sub) < order:
            continue
        perm = tuple(np.argsort(sub))
        patterns[perm] = patterns.get(perm, 0) + 1
        count += 1

    if count == 0:
        return 0.0

    probs = np.array(list(patterns.values())) / count
    H = -float(np.sum(probs * np.log(probs + 1e-15)))
    H_max = math.log(math.factorial(order))
    if H_max < 1e-15:
        return 0.0
    return float(np.clip(H / H_max, 0.0, 1.0))


def _compute_microstates(data, sfreq, nwin, nch, nsamp, f, out, np):  # pragma: no cover
    """Fill microstate{s}_coverage and microstate{s}_meandur entries in `out`.

    Method:
      1. Concatenate windows → (nch, total_samples).
      2. GFP = std across channels at each sample.
      3. Find GFP local-maxima (peaks).
      4. Cluster topographies at peaks with scipy.cluster.vq.kmeans2.
      5. Assign every sample to nearest microstate by (absolute) spatial correlation.
      6. Compute coverage and mean run-length (in seconds) per state.
    """
    from scipy.cluster.vq import kmeans2, whiten
    from scipy.signal import find_peaks

    ms_cfg = f.get("microstates", {})
    n_states = ms_cfg.get("n_states", 4)
    seed = 0  # will be overridden below if available

    # data: (nwin, nch, nsamp) → (nch, total_samples)
    eeg = data.transpose(1, 0, 2).reshape(nch, -1)  # (nch, T)
    T = eeg.shape[1]

    if T < n_states or nch < 2:
        # Not enough data — fill zeros
        for s in range(n_states):
            out[f"microstate{s}_coverage"] = 0.0
            out[f"microstate{s}_meandur"] = 0.0
        return

    # GFP: std across channels at each time point (shape: T,)
    gfp = np.std(eeg, axis=0)  # (T,)

    # Find GFP peaks
    peak_indices, _ = find_peaks(gfp)
    if len(peak_indices) < n_states:
        # Fall back to evenly-spaced samples if too few peaks
        peak_indices = np.linspace(0, T - 1, max(n_states, 10), dtype=int)

    peak_topo = eeg[:, peak_indices].T  # (n_peaks, nch) — topographies at peaks

    # Normalize each topography to unit norm before clustering
    norms = np.linalg.norm(peak_topo, axis=1, keepdims=True)
    norms = np.where(norms < 1e-10, 1.0, norms)
    peak_topo_norm = peak_topo / norms

    # KMeans via scipy (no sklearn dep); seed for determinism
    # kmeans2 requires at least n_states distinct init points; if we have fewer
    # peaks than states, we already padded above. minit='points' picks random
    # rows as initial centroids.
    np.random.seed(seed)
    try:
        centroids, _ = kmeans2(peak_topo_norm, n_states, minit="points",
                               seed=seed, niter=100)
    except Exception:
        for s in range(n_states):
            out[f"microstate{s}_coverage"] = 0.0
            out[f"microstate{s}_meandur"] = 0.0
        return

    # Assign every timepoint: use max absolute spatial correlation with centroids.
    # eeg: (nch, T); centroids: (n_states, nch)
    eeg_norm = eeg / (np.linalg.norm(eeg, axis=0, keepdims=True) + 1e-10)  # (nch, T)
    cent_norm = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-10)  # (n_states, nch)
    # Correlation matrix: (n_states, T)
    corr = np.abs(cent_norm @ eeg_norm)  # (n_states, T)
    assignments = np.argmax(corr, axis=0)  # (T,)

    # Coverage and mean run-length per state
    for s in range(n_states):
        mask_s = (assignments == s)
        coverage = float(np.sum(mask_s)) / T
        out[f"microstate{s}_coverage"] = coverage

        # Mean run-length in seconds
        runs = _run_lengths(mask_s, np)
        if len(runs) == 0:
            meandur = 0.0
        else:
            meandur = float(np.mean(runs)) / sfreq
        out[f"microstate{s}_meandur"] = meandur


def _run_lengths(mask, np):  # pragma: no cover
    """Return array of run-lengths of True values in boolean mask."""
    if not mask.any():
        return np.array([], dtype=int)
    # Pad to detect edges
    padded = np.concatenate([[False], mask, [False]])
    diff = np.diff(padded.astype(int))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    return ends - starts
