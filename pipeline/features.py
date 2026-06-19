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
    total = np.trapz(psd, freqs, axis=-1) + 1e-12
    for band, (lo, hi) in f["bands"].items():
        mask = (freqs >= lo) & (freqs < hi)
        bp = np.trapz(psd[:, mask], freqs[mask], axis=-1)
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

    # Remaining feature families (wPLI, entropy, microstates) are computed by
    # dedicated routines in production; emit NaN so the schema stays aligned.
    for col in feature_schema(cfg):
        out.setdefault(col, float("nan"))
    return out
