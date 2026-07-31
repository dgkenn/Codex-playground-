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
    # SECOND WARNING, ADDED 2026-07-30 (MASTER_PLAN §9.16) AND MORE DAMAGING THAN THE FIRST. Every Chennu
    # experiment in this project scores candidates against this contrast, and THE CHENNU COHORT IS NOT
    # UNCONSCIOUS AT ANY LEVEL. At level 3 ("moderate sedation", plasma 803 ug/L) the median subject gets 35
    # of 40 correct on the behavioural task, 14 of 20 score at or above 20/40, and only 2 of 20 stop
    # responding at all. Level 1 vs level 3 is fully awake versus mostly still awake.
    #
    # Consequences, which are about INTERPRETATION and not about any computed value:
    #   - E05, E07, E08, E09 and E10 measure MILD-TO-MODERATE SEDATION IN RESPONSIVE VOLUNTEERS.
    #   - The recurring finding that "most candidates score below 0.5 on Chennu" is largely this mismatch:
    #     their directions were declared for unconsciousness and the cohort is not unconscious. The same
    #     measures reach 0.99+ in their declared direction on Sleep-EDF W vs N3 (E11), which does reach it.
    #   - `exponent_high`'s 0.863 is a SEDATION-DEPTH discrimination. Possibly a good one; not evidence
    #     about consciousness.
    #
    # THE FIX IS A SEPARATE `sedated_vs_awake` CONTRAST, and it is deliberately NOT added here yet, because
    # every direction I could write for it would be contaminated: the Chennu results have already been seen,
    # so a declaration written now cannot be a pre-registration. When it is added, each direction must cite
    # the literature it came from, must be flagged as declared post-exposure, and can only be tested cleanly
    # on a DIFFERENT sedation dataset. See the queue entry.
    "unconscious_vs_awake",        # anaesthetic LOC, or sleep N3 vs wake -- see BOTH warnings above
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



# ---------------------------------------------------------------------------------------------------
# Exotic features borrowed from other fields (features/exotic.py). Each declares a SIGNED direction,
# reasoned per measure -- the standing rule added after `lempel_ziv` was reported as the best candidate
# across three experiments while pointing opposite to its own declaration (MASTER_PLAN section 9.12).
# ---------------------------------------------------------------------------------------------------

EXPENSIVE_CHANNEL_CAP = 8
"""Channel budget for the quadratic exotic features.

JUSTIFIED BY MEASUREMENT, not convenience. E06 swept all 91 electrodes individually and found channel count
barely matters for these measures: the 19-channel 10-20 subset scored identically to all 91 for Lempel-Ziv
(0.900 both), and the MEDIAN single electrode retained about 89 %. So averaging over a declared handful loses
very little, while multiscale entropy at 91 channels costs roughly 42 minutes per recording.

The subset is the FIRST `EXPENSIVE_CHANNEL_CAP` channels in the recording's own order, which is deterministic
and adapter-defined rather than chosen by looking at results. It is deliberately NOT the best-performing
electrodes from E06 -- selecting those would import that search's winners into a new feature's definition.
"""


def _subset(data):
    import numpy as _np
    d = _np.asarray(data, float)
    return d[:EXPENSIVE_CHANNEL_CAP] if d.shape[0] > EXPENSIVE_CHANNEL_CAP else d


def f_spatial_pr(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.exotic import spatial_participation_ratio
    return float(spatial_participation_ratio(data))


def f_mse_slope(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.exotic import multiscale_entropy_slope
    import numpy as _np
    v = [multiscale_entropy_slope(ch, sfreq) for ch in _subset(data)]
    v = [x for x in v if _np.isfinite(x)]
    return float(_np.mean(v)) if v else float("nan")


def f_pac_slow_alpha(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.exotic import phase_amplitude_coupling
    import numpy as _np
    v = [phase_amplitude_coupling(ch, sfreq) for ch in _subset(data)]
    v = [x for x in v if _np.isfinite(x)]
    return float(_np.mean(v)) if v else float("nan")


def _f_subband(key):
    def fn(data, ch_names, sfreq, meta=None) -> float:
        from bsde.features.exotic import subband_exponents
        import numpy as _np
        v = [subband_exponents(ch, sfreq).get(key, float("nan")) for ch in _np.asarray(data, float)]
        v = [x for x in v if _np.isfinite(x)]
        return float(_np.mean(v)) if v else float("nan")
    fn.__name__ = f"f_{key}"
    return fn


def f_exponent_gamma(data, ch_names, sfreq, meta=None) -> float:
    """Aperiodic exponent over 50-90 Hz — ABOVE the propofol beta hump, and reachable on almost nothing.

    Deliberately identical machinery to `_exponents`, differing only in the band, so any difference from
    `exponent_high` reflects the spectrum and not the estimator (the same discipline `subband_exponents`
    states for the 1-20/20-40 split).

    Returns NaN wherever the band is unreachable, which is most of this project's data: Sleep-EDF is sampled
    at 100 Hz (Nyquist 50) and Chennu arrives filtered 0.5-45 Hz. `fit_aperiodic` already returns NaN when it
    finds no usable points in the requested band, so that degradation is graceful and silent by design rather
    than by exception handling. That scarcity is the point of the candidate: ds005620 at 5 kHz is one of the
    few reachable deposits where this band exists at all.
    """
    v = _exponents(data, sfreq, lo=50.0, hi=90.0)
    v = v[np.isfinite(v)]
    return float(np.mean(v)) if v.size else float("nan")


def f_critical_ar1(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.exotic import critical_slowing
    import numpy as _np
    v = [critical_slowing(ch, sfreq).get("ar1", float("nan")) for ch in _np.asarray(data, float)]
    v = [x for x in v if _np.isfinite(x)]
    return float(_np.mean(v)) if v else float("nan")


def f_emg_index(data, ch_names, sfreq, meta=None) -> float:
    """Composite EMG-contamination proxy. NOT a brain-state marker -- see features/emg.py."""
    from bsde.features.emg import emg_index
    return float(emg_index(data, sfreq))


def f_emg_beta_gamma(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.emg import emg_beta_gamma_fraction
    return float(emg_beta_gamma_fraction(data, sfreq))


def f_emg_kurtosis(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.emg import emg_kurtosis
    return float(emg_kurtosis(data, sfreq))


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


def f_lrtc_alpha(data, ch_names, sfreq, meta=None) -> float:
    """Mean DFA exponent of the 8-13 Hz amplitude envelope across channels — the LRTC of alpha."""
    from bsde.features.exotic import lrtc_envelope
    vals = []
    for ch in _subset(data):
        v = lrtc_envelope(np.asarray(ch, float), sfreq, band=(8.0, 13.0))
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
        name="lrtc_alpha", version="1.0", fn=f_lrtc_alpha,
        interpretation="DFA exponent of the 8-13 Hz amplitude envelope, averaged across channels. "
                       "Long-range temporal correlation: how far the persistence of an alpha burst "
                       "reaches across timescales, as opposed to how large the bursts are.",
        predictions={"unconscious_vs_awake": "higher",
                     "command_following": "higher"},
        failure_conditions=[
            "it is redundant with critical_slowing_ar1 -- both summarise an amplitude envelope, and if "
            "they correlate above 0.9 across recordings this candidate adds nothing (rule 28, which this "
            "project has already paid for three times)",
            "it is redundant with relative_alpha_power -- the whole claim is that the TEMPORAL STRUCTURE "
            "of alpha carries what its MAGNITUDE does not, and a high correlation with power refutes that",
            "it depends on recording length rather than on the subject, which a duration-stratified check "
            "must expose: DFA scales are anchored in seconds precisely so this can be tested",
        ],
        requires=_CORE, complexity=4, min_channels=1, min_duration_s=120.0,
        prior_art="Ruiz-Rizzo et al., Eur J Neurosci 2021 (PMID 34618375) report that resting ALPHA POWER "
                  "was NOT associated with an individual behavioural ability while resting ALPHA LRTC WAS "
                  "-- the exact shape Challenge B needs. Thul et al., NeuroImage 2018 (PMID 29885482) "
                  "report LRTC in beta amplitude rising under sevoflurane unconsciousness, with beta LRTC "
                  "plus alpha amplitude classifying state above 80%. Both verified through E-utilities.",
        notes="Imported from statistical physics rather than from EEG research: scale-free temporal "
              "structure, the machinery behind self-organised criticality. Registered because E41 found "
              "the incumbent (relative_alpha_power) beating all fourteen existing candidates, so the "
              "refinement worth trying is a DIFFERENT PROPERTY OF THE SAME RHYTHM rather than another "
              "spectral summary. The prediction for unconscious_vs_awake is signed from PMID 29885482 and "
              "is the falsifiable half: if LRTC does not rise, that paper does not transfer here.")

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

    # --- EMG proxies. Registered so they are streamed, versioned, hashed and probed like anything else, and
    # --- so the reported search space includes them. They are declared as ARTEFACT measures: the
    # --- interpretation says so, and nothing may cite them as evidence about brain state.
    for nm, fn, interp in (
        ("emg_index", f_emg_index,
         "Composite muscle-contamination proxy: mean of a 20-45 Hz power fraction and a squashed excess "
         "kurtosis. An ARTEFACT measure, not a brain-state marker. Exists to be probed against other "
         "candidates, per ANALYSIS_PLAN.md section 3."),
        ("emg_beta_gamma_fraction", f_emg_beta_gamma,
         "Share of 1-45 Hz power in 20-45 Hz. Rises with muscle AND with genuine cortical beta/gamma, so it "
         "is an UPPER BOUND on possible muscle contribution rather than a measurement of muscle. An artefact "
         "measure."),
        ("emg_kurtosis", f_emg_kurtosis,
         "Median excess kurtosis of the time series across channels. Motor-unit firing is spiky and "
         "non-Gaussian, and that spikiness survives a 45 Hz low-pass better than the spectral signature, so "
         "this is the more band-independent of the two proxies. An artefact measure."),
    ):
        register(
            name=nm, version="1.0", fn=fn, interpretation=interp,
            predictions={"unconscious_vs_awake": "lower"},
            failure_conditions=[
                "it tracks the state contrast as well as any brain-state candidate does, in which case that "
                "candidate's result is an EMG result and must be reported that way",
                "it is uninformative because the recording was low-passed below the muscle band, in which "
                "case a NEGATIVE says nothing and must not be read as clearing anything",
            ],
            requires=("computational", "statistical"), complexity=2,
            prior_art="Muscle contamination of EEG spectra is long established; the standard 65-95 Hz index "
                      "is NOT computable on a deposit filtered to 45 Hz.",
            notes="Predicted LOWER under anaesthesia because neuromuscular tone falls with GABAergic agents. "
                  "That is the same direction a real complexity marker moves, which is precisely why the two "
                  "must be separated by conditioning rather than by comparing directions.")
    # --- exotic candidates, each with a signed direction and the reasoning for that sign ------------
    register(
        name="spatial_participation_ratio", version="1.0", fn=f_spatial_pr,
        interpretation="Effective dimensionality of the multichannel state: (sum of covariance eigenvalues)^2 "
                       "/ sum of their squares, normalised by channel count. 1/n means every channel carries "
                       "the same signal; 1 means they are independent. Borrowed from dimensionality analysis "
                       "in systems neuroscience.",
        predictions={"unconscious_vs_awake": "lower"},
        failure_conditions=[
            "it is redundant with any per-channel measure, which would mean it is not reading spatial "
            "structure at all",
            "it is not computable on the reduced montages the project must support",
        ],
        requires=("computational", "statistical", "adversarial", "cross_domain"),
        complexity=3, min_channels=4,
        prior_art="Participation ratio is standard in population-activity analysis; its application to "
                  "anaesthetic depth is not something this project has verified in the literature.",
        notes="Direction LOWER because anaesthetic slow-wave activity is spatially coherent, so channels "
              "should become more redundant and effective dimensionality should fall. THIS IS THE ONLY "
              "CANDIDATE THAT READS BETWEEN CHANNELS -- every other one is a per-channel summary averaged "
              "across channels, and a channel sweep found one electrode nearly as good as 91. If spatial "
              "information matters at all, this is where it shows up; if this is redundant with the "
              "per-channel measures, that is itself the answer.")

    register(
        name="multiscale_entropy_slope", version="1.0", fn=f_mse_slope,
        interpretation="Slope of sample entropy against log2(coarse-graining scale), scales 1-16, with the "
                       "tolerance r held fixed at 0.2 x the original standard deviation across all scales "
                       "(the Costa convention). Positive means entropy is retained or gained at coarser "
                       "timescales. Borrowed from heart-rate-variability analysis.",
        predictions={"unconscious_vs_awake": "higher"},
        failure_conditions=[
            "it is redundant with single-scale Lempel-Ziv or permutation entropy, which would mean the "
            "multiscale structure adds nothing",
            "it fails to distinguish white noise from 1/f, which would mean the implementation is broken",
        ],
        requires=("computational", "statistical", "adversarial", "cross_domain"), complexity=4,
        min_duration_s=60.0,
        prior_art="Costa, Goldberger & Peng multiscale entropy; widely used in physiology.",
        notes="Direction HIGHER because anaesthesia shifts power to slow activity, and slow structure "
              "survives coarse-graining, so entropy should hold up better at coarse scales. Verified on "
              "synthetic signals: white noise gives -0.326 and 1/f gives +0.123, so the measure separates "
              "them decisively and in the expected order. EXISTS TO INTERROGATE THE LEMPEL-ZIV ANOMALY: LZ "
              "rises with propofol dose at a single timescale, and this says at WHICH timescale.")

    register(
        name="pac_slow_alpha", version="1.0", fn=f_pac_slow_alpha,
        interpretation="Tort modulation index coupling 0.5-2 Hz phase to 8-13 Hz amplitude, normalised to "
                       "[0,1]. A genuinely cross-frequency quantity that no band power or spectral slope can "
                       "express. Borrowed from hippocampal memory research.",
        predictions={"unconscious_vs_awake": "higher"},
        failure_conditions=[
            "it is redundant with alpha power, which would mean it is measuring amount rather than coupling",
            "it does not exceed its own surrogate null built by phase-randomising the amplitude series",
        ],
        requires=("computational", "statistical", "adversarial", "cross_domain"), complexity=5,
        min_duration_s=60.0,
        prior_art="Tort et al. modulation index. Slow-wave-to-alpha phase-amplitude coupling is a documented "
                  "propofol signature (Purdon and colleagues), which makes this the best literature-grounded "
                  "candidate in the seed set for the anaesthesia application.",
        notes="Direction HIGHER because strong slow-alpha coupling is a hallmark of propofol-induced "
              "unconsciousness rather than of wakefulness. Verified on synthetic signals: a 1 Hz-modulated "
              "10 Hz oscillation gives 0.079 while a constant-envelope 10 Hz oscillation alongside an "
              "independent 1 Hz oscillation gives 0.0000.")

    register(
        name="exponent_gamma", version="1.0", fn=f_exponent_gamma,
        interpretation="Aperiodic exponent fitted over 50-90 Hz only, positive for a falling spectrum. The "
                       "band sits ABOVE the propofol beta hump, which is the entire reason it exists: if "
                       "`exponent_high` (20-40 Hz) is tracking a spectral PEAK near the low edge of its own "
                       "fit window rather than a broadband aperiodic change, then a fit placed well above "
                       "that peak must NOT show the same effect.",
        predictions={"unconscious_vs_awake": "higher",
                     "anaesthetic_drug_identity": "unchanged"},
        failure_conditions=[
            "it is redundant with `exponent_high`, which would mean the 20-40 Hz result was never specific "
            "to that band and the beta-hump explanation is dead for a different reason",
            "it tracks an EMG proxy, which is the standing risk for ANY high-frequency measure and is more "
            "acute here than anywhere else in this registry: 50-90 Hz is squarely where surface motor-unit "
            "activity lives, so an EMG result here makes this candidate an EMG measure",
        ],
        requires=("computational", "statistical", "adversarial", "cross_domain"), complexity=2,
        prior_art="Colombo et al., PMID 30639334, for the band-splitting logic. The specific 50-90 Hz "
                  "placement is this project's, motivated by Xi et al. (PMID 29920532) reporting propofol "
                  "beta/gamma power increases at moderate sedation, and is not taken from a source.",
        notes="DECLARED BEFORE ANY VALUE EXISTED for it on any deposit. Direction HIGHER is inherited from "
              "the exponent family's convention rather than independently motivated, and that is stated "
              "rather than dressed up: the informative comparison is not this candidate's own direction but "
              "whether it AGREES with `exponent_high`. NaN on Sleep-EDF (Nyquist 50) and on Chennu "
              "(filtered to 45 Hz) by construction -- ds005620 at 5 kHz is the reachable test.")

    for key, direction in (("exponent_low", "higher"), ("exponent_high", "higher")):
        band = "1-20 Hz" if key == "exponent_low" else "20-40 Hz"
        register(
            name=key, version="1.0", fn=_f_subband(key),
            interpretation=f"Aperiodic exponent fitted over {band} only, positive for a falling spectrum. "
                           "Colombo et al. fit these two bands separately and locate the drug dissociation "
                           "specifically in 20-40 Hz; this project's single 1-40 Hz fit averages that away.",
            predictions={"unconscious_vs_awake": direction,
                         "anaesthetic_drug_identity": "unchanged"},
            failure_conditions=[
                "it is redundant with the 1-40 Hz whole-band exponent, which would mean the band split adds "
                "nothing",
                "the two sub-band exponents are redundant with EACH OTHER, which would mean the spectrum is "
                "a single power law and splitting it is meaningless",
            ],
            requires=("computational", "statistical", "adversarial", "cross_domain"), complexity=2,
            prior_art="Colombo et al., PMID 30639334, verified via E-utilities (LITERATURE_MAP section 0).",
            notes="Direction HIGHER (steeper) under unconsciousness, inheriting this project's sign "
                  "convention. Verified on a synthetic two-slope signal built to be 1/f^1 below 20 Hz and "
                  "1/f^3 above: recovered 1.011 and 2.942. Control: a single-slope 1/f^2 signal returns "
                  "2.018 and 1.942, i.e. the bands agree when the spectrum really is one power law, which is "
                  "what rules out a spurious split.")

    register(
        name="critical_slowing_ar1", version="1.0", fn=f_critical_ar1,
        interpretation="Lag-1 autocorrelation of the 1-45 Hz amplitude envelope, averaged over 2 s windows "
                       "and channels. Rising lag-1 autocorrelation is the canonical early-warning signal for "
                       "an approaching tipping point. Borrowed from ecology and climate-system science.",
        predictions={"unconscious_vs_awake": "higher"},
        failure_conditions=[
            "it is redundant with delta power or the aperiodic exponent, both of which already encode how "
            "slow the signal is",
            "it shows no change approaching a state transition, which is the only claim it is really for",
        ],
        requires=("computational", "statistical", "adversarial", "cross_domain", "temporal"), complexity=3,
        min_duration_s=60.0,
        prior_art="Critical-slowing-down early-warning indicators (Scheffer and colleagues). Their "
                  "application to anaesthetic state transitions is not something this project has verified.",
        notes="Direction HIGHER because anaesthetic EEG is dominated by slow rhythms, giving a more "
              "autocorrelated envelope. IT REQUIRES THE TEMPORAL LAYER, which is not built, so it cannot be "
              "reported as surviving -- deliberately, because its real claim is about transitions and a "
              "state-contrast result would not test that. E04 found no pre-awakening precursor using "
              "conventional features; this is the measure that field would actually use.")

    return REGISTRY.all()
