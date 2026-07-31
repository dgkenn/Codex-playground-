#!/usr/bin/env python3
"""ONE feature path, used by every cohort extractor. Cross-cohort comparison is meaningless otherwise.

WHY THIS MODULE EXISTS. The multi-cohort normative work compares an age/sex curve fitted in one deposit
against the same curve fitted in another. If the two were computed by even slightly different code, a
difference between cohorts would be uninterpretable -- it could be the population, the hardware, or the
pipeline, and nothing in the output would say which. Error-catalogue rule 20 ("when two scripts compute the
same quantity, diff them") applied before the fact: there is only one script.

WHAT IS DELIBERATELY *NOT* HARMONISED HERE, AND WHY THAT IS THE POINT
--------------------------------------------------------------------
The reachable cohorts use three different references -- ds005385 is FCz, ds003775 is average, ds004504 is
linked-ears -- along with different amplifiers, sampling rates and durations. It is tempting to re-reference
everything to a common average and make the problem go away.

**That would pre-empt the experiment.** The question being asked is whether aperiodic correction reduces
between-cohort disagreement, i.e. whether it *harmonises*. Removing the batch effects by construction
leaves nothing for the correction to fix and guarantees a null. So the batch effects are left IN, recorded
as cohort-level metadata, and the correction is asked to earn its place against them. A common-average arm
is a legitimate later comparison, not a precondition.

WHAT *IS* FIXED, IDENTICALLY, EVERYWHERE
----------------------------------------
* the ten-channel 10-20 montage (`MONTAGE`), matched case-insensitively, present in every cohort checked;
* resample to 250 Hz -- anti-alias corner near 125 Hz, far above the 45 Hz top of the widest fit, so no
  filter rolloff can steepen a slope (`NORMAL_REFERENCE_COVARIATES.md` §4's most likely spurious result);
* volts -> microvolts (mne reads EDF in volts; repo convention);
* no notch, no high-pass, no re-reference, no ICA, no epoch rejection. Each of those is a choice that would
  be frozen permanently into a reference. The EMG proxies are emitted as COLUMNS so that gating can be
  registered separately rather than baked in silently.
* per-channel features reduced across channels by MEDIAN, with `n_<feature>` recording how many channels
  contributed so a shortfall is visible rather than silent (rule 5).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "bsde", "src"))

TARGET_SFREQ = 250.0

ANALYSIS_S = 180.0
"""Every recording is truncated to its FIRST 180 seconds, in every cohort.

**Duration is a batch effect, and it is one we would have manufactured ourselves.** The reachable cohorts
run 184 s (ds005385), 240 s (ds003775) and 307-793 s in ds004504 -- which is not only longer but VARIABLE
WITHIN the cohort. Several measures here are length-dependent: `lziv`'s n/log2(n) normalisation is only
asymptotically length-invariant, and DFA and the LRTC envelope depend directly on the range of scales the
record affords. Left alone, a cohort would differ from another partly because its recordings are longer,
and E48's batch index would score that as hardware.

180 s is the largest round value that fits inside the shortest cohort. It is also comfortably above what
the literature says is needed: PMID 38820994 reports 2-3 minutes sufficient for stable aperiodic estimates
(ICC 0.77-0.88) and PMID 32425762 gets stable FOOOF parameters from 2 minutes. So this costs nothing in
estimate quality and removes a confound.

Recordings shorter than `MIN_DURATION_S` are REJECTED rather than analysed short, because a handful of
truncated-to-90 s rows would reintroduce exactly the dependence this removes. They surface as extraction
failures, which are counted and printed, rather than as quietly shorter rows (rule 5)."""

MIN_DURATION_S = 150.0

MONTAGE = ("Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2")
"""The ten channels every feature is computed on, in every cohort.

The classic 10-20 subset, so a reference built on it transfers to a clinical montage --
`REFERENCE_AGAINST_ALL_THREE.md` §4(b) names montage transfer as the second-biggest risk to the whole idea.
Using ONE channel set for every measure also avoids a trap: a row whose spectral columns came from 64
channels and whose complexity columns came from 10 would not be internally comparable and nothing in the
output would show it. Verified present in ds005385 (64ch BrainAmp), ds003775 (64ch BioSemi) and ds004504
(19ch 10-20)."""

FEATURE_KEYS = ("exponent_low", "exponent_high", "whole_head_exponent",
                "exponent_low_robust", "whole_head_robust",
                "aperiodic_offset", "aperiodic_r2",
                "lempel_ziv", "perm_entropy", "dfa_exponent", "lrtc_alpha",
                "rel_delta", "rel_theta", "rel_alpha", "rel_beta",
                "abs_delta", "abs_theta", "abs_alpha", "abs_beta",
                "resid_delta", "resid_theta", "resid_alpha", "resid_beta",
                "alpha_peak_hz", "sef95", "median_freq")

BANDS = (("delta", 1.0, 4.0), ("theta", 4.0, 8.0), ("alpha", 8.0, 13.0), ("beta", 13.0, 30.0))


def _resid_band_power(freqs, psd, ap, lo, hi):
    """APERIODIC-CORRECTED band power: log10 band power minus the log10 power the fitted aperiodic
    component alone predicts over the same band.

    This is the quantity the whole harmonisation question turns on. Absolute band power carries the
    aperiodic background, and the background is exactly what differs between amplifiers, references and
    ages -- so two cohorts can disagree on alpha power while agreeing perfectly on how much alpha sits
    ABOVE their own backgrounds. Relative power does not fix it either: the four relative bands are closed
    (they sum to ~1), so a change in one mechanically moves the others.

    Returns NaN when the aperiodic fit failed, rather than silently returning the uncorrected value --
    a correction that quietly does nothing on failure would make the E48 comparison meaningless.
    """
    import numpy as np
    from bsde.features.spectral import band_power
    if not (np.isfinite(ap.get("exponent", np.nan)) and np.isfinite(ap.get("offset", np.nan))):
        return float("nan")
    obs = band_power(freqs, psd, lo, hi)
    m = (freqs >= lo) & (freqs <= hi) & (freqs > 0)
    if m.sum() < 2 or obs <= 0:
        return float("nan")
    model = 10.0 ** (ap["offset"] - ap["exponent"] * np.log10(freqs[m]))
    pred = float(np.mean(model))
    if pred <= 0:
        return float("nan")
    return float(np.log10(obs) - np.log10(pred))


def _alpha_peak(freqs, psd, lo=6.0, hi=14.0):
    """Individual alpha peak frequency, as the maximum of the psd over 6-14 Hz AFTER removing the fitted
    aperiodic component.

    THIS IS THE BRIDGE QUANTITY and it is here for a specific reason. There is no published normative model
    for the aperiodic exponent (`EXISTING_NORMATIVE_MODELS.md`), so our exponent norms have nothing external
    to be checked against. IAPF does have external truth -- its decline with age in adults is among the most
    replicated results in quantitative EEG. Computing it through THIS pipeline, on THESE rows, means that if
    our IAPF-vs-age slope reproduces the literature then the pipeline is calibrated, and the exponent norms
    coming out of the same code on the same samples inherit that credibility. Validation is transferred from
    a quantity with external truth to one without.

    Returns NaN when no interior maximum exists (a flat or monotone residual has no peak, and returning an
    edge value would silently manufacture one).
    """
    import numpy as np
    from bsde.features.aperiodic import fit_aperiodic
    m = (freqs >= lo) & (freqs <= hi) & (psd > 0) & np.isfinite(psd)
    if m.sum() < 5:
        return float("nan")
    ap = fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=45.0)
    if not np.isfinite(ap["exponent"]):
        return float("nan")
    resid = np.log10(psd[m]) - (ap["offset"] - ap["exponent"] * np.log10(freqs[m]))
    i = int(np.argmax(resid))
    if i == 0 or i == resid.size - 1:
        return float("nan")
    return float(freqs[m][i])


def features_from_raw(raw):
    """Compute the shared feature set from an already-loaded mne Raw. Returns a dict."""
    import numpy as np
    from bsde.features.aperiodic import welch_psd, fit_aperiodic
    from bsde.features.spectral import (relative_band_power, band_power, spectral_edge,
                                        median_frequency)
    from bsde.features.complexity import lziv, permutation_entropy
    from bsde.features.exotic import subband_exponents, dfa_exponent, lrtc_envelope
    from bsde.features.emg import emg_index, emg_beta_gamma_fraction, emg_kurtosis

    raw.pick("eeg")
    want = {c.lower() for c in MONTAGE}
    keep = [ch for ch in raw.ch_names if ch.lower() in want]
    if not keep:
        raise RuntimeError(f"none of {MONTAGE} present; channels are {raw.ch_names[:8]}...")
    raw.pick(keep)
    dur = raw.n_times / float(raw.info["sfreq"])
    if dur < MIN_DURATION_S:
        raise RuntimeError(f"recording is {dur:.1f} s, below the {MIN_DURATION_S:.0f} s floor; "
                           "rejected rather than analysed short (see ANALYSIS_S)")
    if raw.info["sfreq"] > TARGET_SFREQ:
        raw.resample(TARGET_SFREQ, verbose="ERROR")
    sf = float(raw.info["sfreq"])
    data = raw.get_data() * 1e6
    # Common analysis window, applied identically everywhere, so duration cannot enter as a batch effect.
    n_keep = int(round(ANALYSIS_S * sf))
    if data.shape[1] > n_keep:
        data = data[:, :n_keep]
    n_ch, n_s = data.shape

    per = {k: [] for k in FEATURE_KEYS}
    for ci in range(n_ch):
        x = data[ci]
        if not np.isfinite(x).all() or float(np.std(x)) < 1e-9:
            continue
        sb = subband_exponents(x, sf)
        per["exponent_low"].append(sb["exponent_low"])
        per["exponent_high"].append(sb["exponent_high"])
        freqs, psd = welch_psd(x, sf)
        ap = fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=45.0)
        per["whole_head_exponent"].append(ap["exponent"])
        per["aperiodic_offset"].append(ap["offset"])
        per["aperiodic_r2"].append(ap["r2"])
        per["exponent_low_robust"].append(
            fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=20.0, mode="loglog_robust")["exponent"])
        per["whole_head_robust"].append(
            fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=45.0, mode="loglog_robust")["exponent"])
        for nm, lo, hi in BANDS:
            per["rel_" + nm].append(relative_band_power(freqs, psd, lo, hi))
            # ABSOLUTE power too: relative power is closed (the four sum to ~1), so a change in one band
            # mechanically moves the others and a cross-cohort comparison of relative power alone cannot
            # tell which band actually moved.
            per["abs_" + nm].append(float(np.log10(max(band_power(freqs, psd, lo, hi), 1e-30))))
            per["resid_" + nm].append(_resid_band_power(freqs, psd, ap, lo, hi))
        per["alpha_peak_hz"].append(_alpha_peak(freqs, psd))
        per["sef95"].append(spectral_edge(freqs, psd))
        per["median_freq"].append(median_frequency(freqs, psd))
        per["lempel_ziv"].append(lziv(x))
        per["perm_entropy"].append(permutation_entropy(x))
        per["dfa_exponent"].append(dfa_exponent(x, min_scale=int(round(0.1 * sf)),
                                                max_scale=int(round(10.0 * sf))))
        per["lrtc_alpha"].append(lrtc_envelope(x, sf))

    out = {}
    for k, v in per.items():
        vv = [z for z in v if np.isfinite(z)]
        out[k] = float(np.median(vv)) if vv else float("nan")
        out["n_" + k] = len(vv)
    out["emg_index"] = float(emg_index(data, sf))
    out["emg_beta_gamma_fraction"] = float(emg_beta_gamma_fraction(data, sf))
    out["emg_kurtosis"] = float(emg_kurtosis(data, sf))
    out["n_channels"] = n_ch
    out["duration_s"] = round(n_s / sf, 2)
    out["sfreq"] = sf
    return out


def features_from_file(path):
    """Read one EEG file (.edf / .set / .bdf / .fif) and compute the shared feature set."""
    import mne
    ext = os.path.splitext(path)[1].lower()
    if ext == ".vhdr":
        # BrainVision is THREE files -- .vhdr (header), .eeg (data), .vmrk (markers) -- and the header
        # references the other two BY FILENAME. A download to a randomly-named temp file therefore reads
        # as a valid header pointing at files that do not exist. The caller must place all three in one
        # directory under their ORIGINAL basenames; see `_fetch_bundle` in openneuro_multicohort.py.
        raw = mne.io.read_raw_brainvision(path, preload=True, verbose="ERROR")
    elif ext == ".set":
        raw = mne.io.read_raw_eeglab(path, preload=True, verbose="ERROR")
    elif ext == ".bdf":
        raw = mne.io.read_raw_bdf(path, preload=True, verbose="ERROR")
    elif ext in (".fif", ".fif.gz"):
        raw = mne.io.read_raw_fif(path, preload=True, verbose="ERROR")
    else:
        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
    return features_from_raw(raw)
