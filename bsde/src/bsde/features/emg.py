"""EMG contamination indices. NOT brain-state markers — measures of muscle, built to be used against a result.

WHY THIS MODULE EXISTS. `ANALYSIS_PLAN.md` §3 committed to this before any data was processed: *"EMG index is
a predictor of interest, not only a nuisance. If it predicts the outcome as well as the aperiodic exponent
does, the exponent result is an EMG result."* It was never implemented, and E05/E06 made that gap load-bearing:
Lempel-Ziv orders propofol dose in 90 % of subjects, and the effect is frontally dominant (frontal single
electrodes median 0.950 against posterior 0.700). Facial muscle is frontal, EMG adds broadband high-frequency
content that RAISES binarised complexity, and propofol RELAXES muscle — so progressive facial-muscle relaxation
reproduces that finding exactly, with no cortical content. This module is what lets the claim be attacked.

THE CONSTRAINT THAT SHAPES EVERYTHING HERE, stated plainly because it limits what any of this can conclude.
A proper EMG index uses **65–95 Hz**, where scalp muscle dominates and cortical contribution is minimal. The
Chennu deposit is **filtered 0.5–45 Hz**, so that band does not exist in the data. The high-frequency evidence
that would settle the question has already been removed by the depositors' preprocessing.

What remains is a **proxy**, and it is a weak one:

  * `emg_beta_gamma_fraction` — the share of 1–45 Hz power sitting in 20–45 Hz. Muscle raises it. So does
    genuine cortical beta/gamma, and propofol has real beta effects, so this proxy CANNOT separate muscle from
    cortex. It is an upper bound on how much of a result could be muscle, not a measurement of muscle.
  * `emg_kurtosis` — excess kurtosis of the time series. Motor-unit firing is spiky and non-Gaussian while
    background EEG is closer to Gaussian, and spikiness survives a 45 Hz low-pass better than the spectral
    signature does. This is the more independent of the two.
  * `emg_index` — the mean of the two after each is rank-transformed within the cohort, so neither dominates
    by scale. Reported alongside its components, never instead of them.

**HOW A NEGATIVE MUST BE READ.** If these proxies fail to explain the Lempel-Ziv result, that does NOT clear
it of muscle. It means the available band could not detect the muscle if it were there. Clearing the finding
requires a deposit retaining 65–95 Hz — which is a data-acquisition requirement, not an analysis one, and is
recorded as such in `MASTER_PLAN.md` §9.11.

None of these is a candidate brain-state measure and none should ever be registered as competing with one.
They exist to be probed against.
"""
from __future__ import annotations

import numpy as np

from bsde.features.aperiodic import welch_psd
from bsde.features.spectral import relative_band_power

EMG_BAND = (20.0, 45.0)      # the highest band this deposit retains; a real EMG index would use 65-95 Hz
TOTAL_BAND = (1.0, 45.0)


def emg_beta_gamma_fraction(data: np.ndarray, sfreq: float, window_s: float = 4.0) -> float:
    """Share of 1-45 Hz power in 20-45 Hz, averaged over channels.

    Rises with muscle AND with genuine cortical beta/gamma, so a high value does not establish muscle. Its
    value is as an upper bound: a result that survives conditioning on this has survived conditioning on
    everything muscle could contribute *within the retained band*.
    """
    d = np.asarray(data, float)
    vals = []
    for ch in d:
        try:
            f, p = welch_psd(ch, sfreq, window_s=window_s, overlap=0.5)
            v = relative_band_power(f, p, EMG_BAND[0], EMG_BAND[1], TOTAL_BAND[0], TOTAL_BAND[1])
            if np.isfinite(v):
                vals.append(v)
        except Exception:
            continue
    return float(np.mean(vals)) if vals else float("nan")


def emg_kurtosis(data: np.ndarray, sfreq: float = 0.0) -> float:
    """Median excess kurtosis across channels. Motor-unit activity is spiky; background EEG is nearer Gaussian.

    Computed on the raw time series rather than a filtered band, because spikiness is what survives a 45 Hz
    low-pass — a burst of motor-unit firing still leaves a heavy-tailed amplitude distribution after its
    high-frequency content is removed. Excess kurtosis, so 0 is Gaussian.

    Median rather than mean across channels: a single bridged or flat electrode can produce an enormous
    kurtosis and would otherwise dominate the whole recording's value.
    """
    d = np.asarray(data, float)
    out = []
    for ch in d:
        x = ch[np.isfinite(ch)]
        if x.size < 100:
            continue
        s = x.std()
        if s < 1e-12:
            continue
        z = (x - x.mean()) / s
        out.append(float((z ** 4).mean() - 3.0))
    return float(np.median(out)) if out else float("nan")


def emg_index(data: np.ndarray, sfreq: float, window_s: float = 4.0) -> float:
    """Composite: the mean of the two proxies after each is scaled to a comparable range.

    Scaling is by a FIXED transform, not by cohort statistics, so the value of one recording does not depend
    on which other recordings happen to be in the batch — a cohort-relative z-score would make the feature
    non-deterministic per recording and would break the streaming layer's byte-identical-rerun guarantee.

    beta/gamma fraction is already in [0, 1]. Kurtosis is unbounded above, so it is squashed with
    `k / (1 + |k|)`, which is monotone, maps 0 to 0, and saturates rather than letting one spiky channel
    dominate the composite.
    """
    bg = emg_beta_gamma_fraction(data, sfreq, window_s)
    ku = emg_kurtosis(data, sfreq)
    if not np.isfinite(bg) and not np.isfinite(ku):
        return float("nan")
    parts = []
    if np.isfinite(bg):
        parts.append(bg)
    if np.isfinite(ku):
        parts.append(ku / (1.0 + abs(ku)))
    return float(np.mean(parts))
