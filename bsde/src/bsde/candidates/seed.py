"""The seeded candidate set — the measures the engine starts with, and what each one is committed to.

THIS FILE IS A PRE-REGISTRATION. Every `predictions` entry below was written before the candidate was run
against any labelled dataset, and each is hashed into the candidate's declaration. Changing a prediction
after seeing a result changes the hash, which is visible in the record; that is the tripwire, and it is the
whole reason the declaration format exists.

SIGN CONVENTION, stated once and inherited by everything here. `fit_aperiodic` returns a POSITIVE exponent
for a falling spectrum, so a steeper spectrum means a LARGER number. Colombo et al. (PMID 30639334) report
the same quantity as a negative decay rate. Translated into this project's convention their finding is
**unconsciousness = HIGHER exponent**, and every declaration below follows that. A result whose sign
disagrees is a bug until proven otherwise (LITERATURE_MAP.md §0).

WHY `anaesthetic_drug_identity: unchanged` APPEARS ON THE CONSCIOUSNESS CANDIDATES. It is the single most
informative prediction in this file and the one most likely to fail. Discovery Challenge A asks for a
representation that predicts loss and recovery of responsiveness across anaesthetics *while minimising the
information it carries about which drug was used*. A marker that silently encodes the drug is a
pharmacology detector wearing a consciousness label, and declaring `unchanged` here means the engine's
`probe:drug` is a registered test the candidate can fail rather than a diagnostic printed afterwards.

COMPLEXITY is free parameters plus distinct transformations, counted by hand:
    z(mean exponent)           2   (one fit, one standardisation)
    UCE v1                     4   (two regional fits, two standardisations, two weights, one sum -- the
                                    weights are fixed so they cost 1 between them, not 2)
    band power                 2   (one PSD, one integration)
    Lempel-Ziv                 3   (one binarisation threshold, one parse, one normalisation)
    debiased wPLI (alpha)      4   (segmentation, cross-spectrum, band selection, debiasing)
A gain that does not exceed the complexity penalty is not a discovery; `complexity_is_earned` in the
adversarial layer is where that is enforced.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from bsde.candidates.registry import REGISTRY, Candidate, register
from bsde.candidates.uce_v1 import regional_exponents, uce_v1_from_z, W_FRONTAL, W_POSTERIOR

# Contrast names used across the project. A candidate earns nothing for a contrast it does not name.
CONTRASTS = (
    # WARNING (added 2026-07-29 after adversarial review; see docs/MASTER_PLAN.md §9.3). This contrast MERGES
    # anaesthetic loss of consciousness with sleep N3-vs-wake, and those are exactly the two states that H4 --
    # "the marker is an arousal index" -- predicts should behave alike. A cross-domain PASS spanning only
    # sleep and anaesthesia is therefore NEUTRAL between H4 and the capacity hypothesis, not evidence for
    # either, and must never be reported as "cross-domain validated". The informative domains are the ones
    # that dissociate arousal from experience: ds005620 (unresponsive with vs without later reported
    # experience), ketamine, and locked-in syndrome.
    "unconscious_vs_awake",        # anaesthetic LOC, or sleep N3 vs wake -- see warning above
    "anaesthetic_drug_identity",   # propofol vs sevoflurane vs ketamine -- SHOULD be unchanged
    "mcs_vs_uws",                  # behavioural DoC category, an imperfect reference standard
    "command_following",           # the CMD endpoint; a failed task is indeterminate, never negative
    "emergence_within_subject",    # transition from unresponsive to responsive in the same person
)


# ---------------------------------------------------------------------------------------------------
# feature adapters: (data, ch_names, sfreq, meta) -> scalar
# ---------------------------------------------------------------------------------------------------

def _exponents(data: np.ndarray, sfreq: float, lo: float = 1.0, hi: float = 40.0,
               window_s: float = 4.0) -> np.ndarray:
    from bsde.features.aperiodic import welch_psd, fit_aperiodic
    out = []
    for ch in np.asarray(data, float):
        try:
            f, p = welch_psd(ch, sfreq, window_s=window_s, overlap=0.5)
            out.append(fit_aperiodic(f, p, lo, hi, "loglog_robust")["exponent"])
        except Exception:
            out.append(float("nan"))
    return np.asarray(out, float)


def _mean_psd(data: np.ndarray, sfreq: float, window_s: float = 4.0):
    from bsde.features.aperiodic import welch_psd
    acc, freqs = None, None
    for ch in np.asarray(data, float):
        f, p = welch_psd(ch, sfreq, window_s=window_s, overlap=0.5)
        acc = p if acc is None else acc + p
        freqs = f
    return freqs, acc / len(data)


def f_whole_head_exponent(data, ch_names, sfreq, meta=None) -> float:
    """The trivial baseline. E01 showed UCE v1 correlates with this at 0.9952 on real EEG."""
    e = _exponents(data, sfreq)
    e = e[np.isfinite(e)]
    return float(e.mean()) if e.size else float("nan")


def f_uce_v1(data, ch_names, sfreq, meta=None) -> float:
    """Frozen UCE v1 on ONE recording, standardised against the reference in `meta` if supplied.

    Without a training-fold reference this returns the unstandardised weighted combination, which is
    monotone in the standardised score for fixed weights and therefore gives identical AUCs. It is NOT
    interchangeable with the standardised score for calibration, and `meta['uce_ref']` must be supplied
    whenever a probability is to be reported.
    """
    reg = regional_exponents(_exponents(data, sfreq), ch_names)
    fr, po = reg["frontal"], reg["posterior"]
    if not (np.isfinite(fr) and np.isfinite(po)):
        return float("nan")   # a montage lacking a region cannot yield UCE v1; never substitute
    ref = (meta or {}).get("uce_ref")
    if ref:
        fr = (fr - ref["frontal"][0]) / ref["frontal"][1]
        po = (po - ref["posterior"][0]) / ref["posterior"][1]
    return float(uce_v1_from_z(fr, po))


def _band(name):
    from bsde.features.spectral import BANDS
    lo, hi = BANDS[name]

    def fn(data, ch_names, sfreq, meta=None) -> float:
        from bsde.features.spectral import relative_band_power
        f, p = _mean_psd(data, sfreq)
        return float(relative_band_power(f, p, lo, hi))
    fn.__name__ = f"f_relative_{name}"
    return fn


def f_spectral_edge_95(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.spectral import spectral_edge
    f, p = _mean_psd(data, sfreq)
    return float(spectral_edge(f, p, 95.0))


def f_spectral_entropy(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.spectral import spectral_entropy
    f, p = _mean_psd(data, sfreq)
    return float(spectral_entropy(f, p))


LZIV_WINDOW_S = 10.0
LZIV_TARGET_HZ = 100.0   # every dataset is decimated to this before LZ -- see f_lziv's docstring


def f_lziv(data, ch_names, sfreq, meta=None) -> float:
    """Mean normalised LZ76 over fixed-length windows, then over channels.

    WHY FIXED WINDOWS RATHER THAN THE WHOLE RECORDING. LZ76 complexity normalised by n/log2(n) is only
    asymptotically length-invariant; at finite n the normalised value still drifts with n. Computing it on
    whole recordings would therefore make the measure partly a function of RECORDING DURATION, and duration
    is outcome-related in every clinical EEG cohort this project touches -- sicker patients are monitored
    longer. That is a confound built into the feature definition, where no probe can see it.

    A fixed 10 s window makes every recording contribute values on the same scale regardless of its length.
    It also happens to be far cheaper: LZ76 is quadratic in n, so windowing turned ~250 s per 62-channel
    recording into a few seconds. The scientific reason is the governing one; the speed is a side effect.

    Windows are non-overlapping and any trailing partial window is dropped, so every value averaged here
    comes from exactly the same number of samples.
    """
    from bsde.features.complexity import lziv
    d = np.asarray(data, float)
    sf = float(sfreq)
    if sf > LZIV_TARGET_HZ * 1.01:
        from math import gcd
        up, down = int(round(LZIV_TARGET_HZ)), int(round(sf))
        g = gcd(up, down)
        try:
            from scipy.signal import resample_poly
            d = resample_poly(d, up // g, down // g, axis=1)
        except Exception:
            return float("nan")   # refuse rather than compare an undecimated value against decimated ones
        sf = LZIV_TARGET_HZ
    w = int(round(LZIV_WINDOW_S * sf))
    if w < 256 or d.shape[1] < w:
        return float("nan")     # too short to yield a comparable value; say so rather than improvise
    n_win = d.shape[1] // w
    vals = []
    for ch in d:
        for k in range(n_win):
            v = lziv(ch[k * w:(k + 1) * w])
            if np.isfinite(v):
                vals.append(v)
    return float(np.mean(vals)) if vals else float("nan")


def f_wpli_alpha(data, ch_names, sfreq, meta=None) -> float:
    """Mean debiased wPLI over channel pairs in 8-13 Hz. Capped at 300 pairs, sampled deterministically."""
    from bsde.features.connectivity import wpli
    d = np.asarray(data, float)
    n = len(d)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if len(pairs) > 300:
        step = len(pairs) / 300.0
        pairs = [pairs[int(k * step)] for k in range(300)]
    vals = [wpli(d[i], d[j], sfreq, 8.0, 13.0) for i, j in pairs]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else float("nan")


# ---------------------------------------------------------------------------------------------------
# the declarations
# ---------------------------------------------------------------------------------------------------

_CORE = ("computational", "statistical", "adversarial", "cross_domain")


def seed_registry() -> Sequence[Candidate]:
    """Register the seed set. Idempotent: re-registering an identical declaration is a no-op."""

    register(
        name="whole_head_exponent", version="1.0", fn=f_whole_head_exponent,
        interpretation="Mean aperiodic (1/f) exponent of the resting PSD across all available channels. "
                       "Interpreted as a summary of the excitation/inhibition balance of cortical "
                       "background activity (Gao 2017, PMID 28676297); a steeper spectrum means "
                       "inhibition-dominated dynamics.",
        predictions={"unconscious_vs_awake": "higher",
                     "anaesthetic_drug_identity": "unchanged",
                     "mcs_vs_uws": "lower"},
        failure_conditions=[
            "the direction inverts between any two datasets",
            "it predicts EMG index, recording site or artifact burden better than it predicts the state, "
            "and the state association does not survive holding that nuisance constant",
            "it separates anaesthetic drugs -- that would make it a pharmacology detector",
        ],
        requires=_CORE, complexity=2, min_channels=1, min_duration_s=60.0,
        prior_art="Colombo et al., NeuroImage, PMID 30639334 — the spectral exponent already indexes the "
                  "presence of consciousness across propofol, xenon and ketamine at n=5 per group. This "
                  "candidate is NOT a new construct; its contribution would be validation at scale.",
        notes="THE TRIVIAL BASELINE. Every other candidate must beat this one. E01 established that UCE v1 "
              "correlates with it at 0.9952 on 96 real recordings.")

    register(
        name="uce_v1", version="1.0-frozen", fn=f_uce_v1,
        interpretation="0.696*z(frontal exponent) + 0.718*z(posterior exponent). Claimed as a "
                       "two-dimensional anteroposterior construct. RESEARCH_STRATEGY.md §0 shows the "
                       "weights are PC1 of two standardised variables and therefore carry no information; "
                       "E01 confirmed r(frontal, posterior) = 0.9326 on real EEG.",
        predictions={"unconscious_vs_awake": "higher",
                     "anaesthetic_drug_identity": "unchanged",
                     "mcs_vs_uws": "lower"},
        failure_conditions=[
            "it fails to beat whole_head_exponent -- which E01 makes the expected outcome",
            "a montage lacking either region makes it incomputable while the baseline remains computable",
            "the same nuisance-probe failures as the baseline",
        ],
        requires=_CORE, complexity=4, min_channels=4, min_duration_s=60.0,
        required_regions=("frontal", "posterior"),
        prior_art="The investigator's own prior derivation, preserved verbatim in RESEARCH_PROGRAM_BRIEF.md.",
        notes="FROZEN. Registered as one candidate among many, held to the same bar, and expected on "
              "present evidence to be REVISEd in favour of the one-feature baseline. Kept because a locked "
              "baseline that the platform's own engine demotes is more credible than one quietly dropped.")

    register(
        name="relative_alpha_power", version="1.0", fn=_band("alpha"),
        interpretation="Fraction of 1-45 Hz power in 8-13 Hz. Frontal alpha is the classic propofol "
                       "signature; posterior alpha dominates relaxed wakefulness.",
        predictions={"unconscious_vs_awake": "higher", "anaesthetic_drug_identity": "higher"},
        failure_conditions=["fails to beat whole_head_exponent",
                            "the direction inverts between anaesthesia and disorders of consciousness"],
        requires=_CORE, complexity=2, min_duration_s=60.0,
        prior_art="Frontal alpha under propofol is long established; included as a strong conventional "
                  "baseline, not as a discovery.",
        notes="Deliberately declares 'higher' for drug identity — it is a KNOWN pharmacological signature "
              "and pretending otherwise would be dishonest. That is precisely why it is a poor "
              "consciousness marker and a good baseline.")

    register(
        name="relative_delta_power", version="1.0", fn=_band("delta"),
        interpretation="Fraction of 1-45 Hz power in 1-4 Hz. Slow-wave dominance.",
        predictions={"unconscious_vs_awake": "higher", "mcs_vs_uws": "lower"},
        failure_conditions=["fails to beat whole_head_exponent",
                            "it is redundant with the aperiodic exponent (|rank correlation| > 0.9), in "
                            "which case it is the same measurement under another name"],
        requires=_CORE, complexity=2, min_duration_s=60.0,
        prior_art="Standard clinical EEG grading.",
        notes="Rule 28 of the sibling project's catalogue applies: two measurements separated in frequency "
              "are not thereby measuring different things. Delta power and a steep 1/f slope are close "
              "relatives and the redundancy check is registered above as a failure condition.")

    register(
        name="spectral_edge_95", version="1.0", fn=f_spectral_edge_95,
        interpretation="Frequency below which 95 % of 1-45 Hz power lies. A depth-of-anaesthesia summary "
                       "used by commercial monitors.",
        predictions={"unconscious_vs_awake": "lower", "anaesthetic_drug_identity": "unchanged"},
        failure_conditions=["fails to beat whole_head_exponent"],
        requires=_CORE, complexity=2, min_duration_s=60.0,
        prior_art="A component of several commercial depth indices; the established comparator.")

    register(
        name="spectral_entropy", version="1.0", fn=f_spectral_entropy,
        interpretation="Shannon entropy of the normalised 1-45 Hz power distribution, in bits, scaled to "
                       "[0,1]. Flat spectra score 1; peaked spectra score low.",
        predictions={"unconscious_vs_awake": "lower", "anaesthetic_drug_identity": "unchanged"},
        failure_conditions=["fails to beat whole_head_exponent",
                            "it is an algebraic restatement of the aperiodic exponent -- a pure power law "
                            "has entropy determined by its exponent alone, so on clean data these two "
                            "cannot be independent"],
        requires=_CORE, complexity=2, min_duration_s=60.0,
        prior_art="Entropy modules in commercial anaesthesia monitors.",
        notes="The second failure condition is a mathematical near-certainty, registered in advance so that "
              "a high correlation with the exponent is recorded as a prediction met rather than presented "
              "as convergent validation.")

    register(
        name="lempel_ziv", version="1.0", fn=f_lziv,
        interpretation="Median-binarised LZ76 complexity per channel, normalised by n/log2(n), averaged "
                       "across channels. A signal-diversity measure and the spontaneous-EEG relative of "
                       "the perturbational complexity index.",
        predictions={"unconscious_vs_awake": "lower",
                     "anaesthetic_drug_identity": "unchanged",
                     "mcs_vs_uws": "higher",
                     "command_following": "higher"},
        failure_conditions=[
            "fails to beat whole_head_exponent",
            "it tracks the aperiodic exponent so closely that it adds nothing -- binarised complexity of a "
            "power-law signal is largely determined by its slope",
            "it tracks EMG index better than state, since muscle broadens the spectrum and raises LZ",
        ],
        requires=_CORE, complexity=3, min_duration_s=120.0,
        prior_art="Casali et al. PCI, PMID 23946194 (perturbational); Sarasso et al., PMID 26752078.",
        notes="Declares four predictions, the most in the seed set, and is therefore the candidate with the "
              "most ways to be wrong. That is a feature of the declaration, not a liability.")

    register(
        name="wpli_alpha", version="1.0", fn=f_wpli_alpha,
        interpretation="Mean debiased weighted phase lag index across channel pairs in 8-13 Hz. A "
                       "volume-conduction-resistant measure of alpha-band phase coupling.",
        predictions={"unconscious_vs_awake": "lower",
                     "mcs_vs_uws": "higher",
                     "command_following": "higher"},
        failure_conditions=[
            "fails to beat whole_head_exponent",
            "it depends on channel count or montage more than on state -- a reduced montage changes the "
            "pair set and therefore the measure, which the reduced-channel check must expose",
        ],
        requires=_CORE, complexity=4, min_channels=8, min_duration_s=120.0,
        prior_art="King et al. wSMI, PMID 24076243, is the reference connectivity marker; wPLI is the "
                  "phase-based comparator. wSMI itself is not yet implemented.",
        notes="By construction wPLI is near zero for zero and pi phase lags. That is the point of the "
              "measure and it is verified in tests/test_connectivity_features.py.")

    return REGISTRY.all()
