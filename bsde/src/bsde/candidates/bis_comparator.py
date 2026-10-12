"""The four BIS subparameters, registered as candidates so they can be streamed like any other feature.

WHY THEY ARE REGISTERED SEPARATELY FROM `seed.py`. The seeded candidates are consciousness measures, each
committed to a direction on `unconscious_vs_awake` AND to `anaesthetic_drug_identity: unchanged` -- the
drug-invariance claim that Discovery Challenge A turns on. **These four make no such claim and must not
appear to.** They are the ingredients of a depth-of-anaesthesia monitor, built by a manufacturer to track a
drug effect; declaring them drug-invariant would be asserting something nobody claims for BIS itself. The
contrast is therefore left UNDECLARED, which the verifier reports as `undeclared` and never as satisfied.

They are also kept out of `seed_registry()` for a mechanical reason: `stream_features` refuses to append to a
table whose column set has changed, so silently adding four names to `REGISTRY.all()` would break resumption
of every existing extraction. `seed_bis_comparator()` must be called deliberately, and the streaming script
that calls it writes to its own table.

WHAT THE PREDICTIONS BELOW ARE FOR. These are not discovery claims -- the implementation claim is
"this computes the published description", which is why `requires` is the computational layer alone. But a
registered measure must offer some way to be wrong, and the directions below are the ones the BIS literature
implies, so a subparameter that moves the other way on real anaesthesia data is either misimplemented or
misunderstood. That is exactly the tripwire wanted before any of them is fitted against device BIS.

REGISTERED BEFORE ANY OF THE FOUR HAS BEEN COMPUTED ON VITALDB. `results/vitaldb_grid.csv` is features-only
and carries none of them; the raw waveform has to be re-fetched to produce a single value.
"""
from __future__ import annotations

import numpy as np

from bsde.candidates.registry import REGISTRY, register


def _per_channel(data, sfreq, fn) -> float:
    """Mean of a per-channel scalar, matching the convention `f_whole_head_exponent` already uses."""
    out = []
    for ch in np.asarray(data, float):
        try:
            out.append(float(fn(ch, float(sfreq))))
        except Exception:                                                    # noqa: BLE001
            out.append(float("nan"))
    v = np.asarray(out, float)
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def f_bis_rbr(data, ch_names, sfreq, meta=None) -> float:
    from bsde.candidates.seed import _mean_psd
    from bsde.features.bis_subparams import relative_beta_ratio
    try:
        f, p = _mean_psd(data, sfreq)
    except Exception:                                                        # noqa: BLE001
        return float("nan")
    return relative_beta_ratio(f, p)


def f_bis_bsr(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.bis_subparams import burst_suppression_ratio
    return _per_channel(data, sfreq, burst_suppression_ratio)


def f_bis_quazi(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.bis_subparams import quazi_suppression
    return _per_channel(data, sfreq, quazi_suppression)


def f_bis_sfs(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.bis_subparams import sync_fast_slow
    return _per_channel(data, sfreq, sync_fast_slow)


def seed_bis_comparator() -> None:
    """Register the four. Idempotent — re-registering an identical declaration is a no-op."""

    register(
        name="bis_rbr", version="1", fn=f_bis_rbr, complexity=3,
        interpretation="Relative beta ratio, log(P[30-47 Hz] / P[11-20 Hz]). The BIS subparameter that "
                       "dominates in the LIGHT sedation range, where low-dose anaesthetic produces beta "
                       "activation.",
        predictions={"unconscious_vs_awake": "lower"},
        notes="THE DECLARED DIRECTION IS THE DEEP-END ONE AND THE MEASURE IS NON-MONOTONIC IN DEPTH. Beta "
              "activation RISES on the way down from awake to light sedation and then collapses as the "
              "spectrum slows, so a light-sedation cohort can legitimately show the opposite sign. That is "
              "not a licence to reinterpret afterwards: 'lower' is the claim for genuine loss of "
              "consciousness, and a light-sedation result showing 'higher' must be reported as the "
              "non-monotonicity it is, with the depth stated, not as a confirmation.",
        failure_conditions=(
            "RBR is not lower at loss of consciousness than awake in a cohort that actually reaches "
            "unconsciousness (Sleep-EDF N3-vs-W, or VitalDB windows at BIS < 40).",
            "RBR moves when the amplifier gain changes — it is a ratio and must be scale-invariant.",
        ),
        requires=("computational",),
        prior_art="Rampil, Anesthesiology 1998 (PMID 9772278); Lee et al. (PMID 31551487).",
    )

    register(
        name="bis_bsr", version="1", fn=f_bis_bsr, complexity=3,
        interpretation="Burst suppression ratio: fraction of the epoch spent within +/-5 uV of baseline for "
                       "at least 0.5 s. Requires MICROVOLTS.",
        predictions={"unconscious_vs_awake": "higher"},
        notes="EXPECTED TO BE IDENTICALLY ZERO OUTSIDE DEEP ANAESTHESIA, including in natural N3 sleep, "
              "which is unconscious and not suppressed. A cohort where this column has no variance has not "
              "refuted the measure; it has failed to reach the state the measure reads (rule 32 — a "
              "measurement's availability defines a stratum). A NON-zero BSR in natural sleep would instead "
              "mean the 5 uV threshold is being applied to something that is not microvolts.",
        failure_conditions=(
            "BSR is non-zero in awake, artefact-free EEG at ordinary amplitude.",
            "BSR disagrees with the VitalDB device's own BIS/SR track in DIRECTION across windows where "
            "the device reports suppression.",
        ),
        requires=("computational",),
        prior_art="Rampil, Anesthesiology 1998 (PMID 9772278).",
    )

    register(
        name="bis_quazi", version="1", fn=f_bis_quazi, complexity=5,
        interpretation="QUAZI suppression index, as the INCREMENT over plain BSR after removing baseline "
                       "drift: suppression that a slow wave riding underneath hides from BSR.",
        predictions={"unconscious_vs_awake": "higher"},
        notes="Defined as a difference rather than a level precisely so it does not duplicate bis_bsr "
              "(rule 28). If the two columns still correlate above ~0.9 on real data the increment is not "
              "carrying separate information and the pair should be collapsed before either is fitted.",
        failure_conditions=(
            "bis_quazi correlates with bis_bsr above 0.9 on VitalDB windows — then it is a second copy of "
            "BSR, not the thing BSR misses.",
            "bis_quazi is materially non-zero in awake EEG, where there is no suppression under any "
            "detrending.",
        ),
        requires=("computational",),
        prior_art="Rampil, Anesthesiology 1998 (PMID 9772278).",
    )

    register(
        name="bis_sfs", version="1", fn=f_bis_sfs, complexity=5,
        interpretation="SyncFastSlow: log(bispectral sum over 0.5-47 Hz / bispectral sum over sum-frequency "
                       "40-47 Hz). The only genuinely bispectral quantity in BIS, and the reason the index "
                       "is called bispectral — it reads PHASE COUPLING between frequency pairs, not power.",
        predictions={"unconscious_vs_awake": "higher"},
        notes="THE ONE MEASURE HERE THIS REPO COULD NOT ALREADY COMPUTE. Every other feature in the "
              "registry is spectral or amplitude-based, so if a BIS-like index built from these four beats "
              "the existing feature set, bis_sfs is the first place to look for the reason — and if it does "
              "NOT, that is itself informative about how much of BIS is bispectral in practice.",
        failure_conditions=(
            "bis_sfs is unchanged between a signal with quadratic phase coupling and one with identical "
            "power at identical frequencies and independent phase (tested directly in "
            "tests/test_bis_subparams.py).",
            "bis_sfs moves when the signal is rescaled — it is a ratio of bispectral sums.",
        ),
        requires=("computational",),
        prior_art="Rampil, Anesthesiology 1998 (PMID 9772278); Sigl & Chamoun, J Clin Monit 1994.",
    )


def bis_candidates():
    """The four, in a fixed order, after ensuring they are registered."""
    seed_bis_comparator()
    return [REGISTRY.get(n) for n in ("bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs")]
