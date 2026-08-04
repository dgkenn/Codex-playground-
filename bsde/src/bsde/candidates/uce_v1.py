"""FROZEN UCE v1 — the locked baseline. Do not modify these coefficients.

    UCE v1 = 0.696 * z(frontal aperiodic exponent) + 0.718 * z(posterior aperiodic exponent)

Per the brief §4 this version is FROZEN. Any change is a new version in a new module
(`uce_v2.py`, ...), evaluated independently. Editing the constants below is a protocol violation and
`tests/test_uce_v1.py` asserts their exact values so that an accidental edit fails the suite.

------------------------------------------------------------------------------------------------------------
WHAT THIS SCORE IS, established by algebra before any data (RESEARCH_STRATEGY.md §0)

For two STANDARDIZED variables the correlation matrix [[1,r],[r,1]] has eigenvectors (1/sqrt2)(1,1) and
(1/sqrt2)(1,-1) for ALL r. So equal PC1 loadings are a mathematical necessity, not an empirical finding, and
the reported "96.8 % of variance explained" is an exact restatement of r(frontal, posterior) = 0.936 via
VE = (1+r)/2. The stated weights are a unit vector whose mean is 0.7070 against 1/sqrt2 = 0.7071.

Therefore UCE v1 is, to a very good approximation, **the mean of two nearly-identical measurements** — i.e. a
whole-head aperiodic exponent. That may still be a useful arousal marker. It is not, on this evidence, a
two-dimensional discovery.

`uce_v1_with_baseline()` returns the score TOGETHER WITH the single-feature baseline it must beat, so the
comparison mandated by RESEARCH_STRATEGY.md R-01 cannot be quietly omitted.

------------------------------------------------------------------------------------------------------------
CONFIRMED ON REAL DATA, 2026-07-31 — the algebraic prediction above held in three independent cohorts.

    r(uce_v1, whole_head_exponent)     eegmmidb resting  n=210   Pearson +0.980   Spearman +0.973
                                       ds004541          n=124           +0.882            +0.899
                                       chennu propofol   n= 80           +0.962            +0.957

**No outcome label was consulted for that table, and none is needed.** Two measures correlating at 0.98
cannot differ meaningfully in what they predict, so RESEARCH_STRATEGY.md §0's binding consequence is
discharged by the redundancy alone: **the frontal/posterior structure is decorative.** Describe this score
as a whole-head aperiodic exponent; do not quote 0.696/0.718 as a finding about frontal versus posterior
cortex; report "96.8 % of variance" as the restatement of r = 0.936 that it is.

E41's Challenge B numbers are consistent and decide nothing on their own — `uce_v1` +0.0853 [-0.1066,
+0.2651] against `whole_head_exponent` +0.0490 [-0.1322, +0.2430], a gap of 0.036 against that experiment's
own minimum detectable effect of 0.272. **The redundancy is the evidence; the label comparison is not.**

**Consequence for anyone trying to improve this marker: re-weighting cannot do it.** If the weights are
forced by symmetry and the two inputs are one measurement, there is nothing in the weights to tune, and a
refinement must change the PROPERTY being measured rather than its spatial decomposition. The constants
below stay frozen not only because the brief says so, but because moving them could not help.
"""
from __future__ import annotations

from typing import Dict, Iterable, Sequence

import numpy as np

# --- FROZEN. Do not edit. ---------------------------------------------------------------------------------
W_FRONTAL: float = 0.696
W_POSTERIOR: float = 0.718
UCE_V1_VERSION: str = "uce_v1.0-frozen"
# ----------------------------------------------------------------------------------------------------------

# 10-20 names treated as frontal / posterior. Deliberately explicit: a montage that does not contain both
# groups cannot yield UCE v1, and the code must say so rather than silently averaging whatever is present.
FRONTAL_CH = ("FP1", "FP2", "FPZ", "AF3", "AF4", "AF7", "AF8", "F1", "F2", "F3", "F4",
              "F5", "F6", "F7", "F8", "FZ")
POSTERIOR_CH = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "PZ", "PO3", "PO4",
                "PO7", "PO8", "POZ", "O1", "O2", "OZ", "T5", "T6")


def _norm(name: str) -> str:
    return "".join(c for c in str(name).upper() if c.isalnum())


def group_indices(ch_names: Sequence[str]) -> Dict[str, list[int]]:
    """Indices of frontal and posterior channels. Names are normalised (case, punctuation, '-REF' suffixes)."""
    fro, pos = [], []
    for i, nm in enumerate(ch_names):
        n = _norm(nm)
        for suf in ("REF", "LE", "AVG"):
            if n.endswith(suf) and len(n) > len(suf):
                n = n[: -len(suf)]
        if n in FRONTAL_CH:
            fro.append(i)
        elif n in POSTERIOR_CH:
            pos.append(i)
    return {"frontal": fro, "posterior": pos}


def zscore(v: np.ndarray, mean: float | None = None, sd: float | None = None) -> np.ndarray:
    """Standardise. Reference mean/sd MUST come from a training fold, never from the test data.

    Passing mean/sd explicitly is the supported path; computing them from `v` is convenience for exploration
    and is a leakage risk in any evaluation (brief §13).
    """
    v = np.asarray(v, float)
    mu = float(np.nanmean(v)) if mean is None else float(mean)
    s = float(np.nanstd(v)) if sd is None else float(sd)
    return (v - mu) / (s if s > 1e-12 else 1.0)


def uce_v1_from_z(z_frontal: float | np.ndarray, z_posterior: float | np.ndarray):
    """The frozen equation itself, on already-standardized inputs."""
    return W_FRONTAL * np.asarray(z_frontal, float) + W_POSTERIOR * np.asarray(z_posterior, float)


def regional_exponents(exponents: Iterable[float], ch_names: Sequence[str]) -> Dict[str, float]:
    """Frontal / posterior / whole-head mean exponent for ONE recording.

    Returns NaN for a region with no channels rather than substituting the other region — silently
    substituting would make UCE v1 computable on montages that cannot support it.
    """
    e = np.asarray(list(exponents), float)
    if e.size != len(ch_names):
        raise ValueError(f"{e.size} exponents but {len(ch_names)} channel names")
    g = group_indices(ch_names)
    def m(idx):
        vals = e[idx] if idx else np.array([])
        vals = vals[np.isfinite(vals)]
        return float(vals.mean()) if vals.size else float("nan")
    finite = e[np.isfinite(e)]
    return {"frontal": m(g["frontal"]), "posterior": m(g["posterior"]),
            "whole_head": float(finite.mean()) if finite.size else float("nan"),
            "n_frontal": len(g["frontal"]), "n_posterior": len(g["posterior"])}


def uce_v1_with_baseline(frontal: np.ndarray, posterior: np.ndarray, whole_head: np.ndarray,
                         ref: Dict[str, tuple[float, float]] | None = None) -> Dict[str, np.ndarray]:
    """Cohort-level UCE v1 AND the one-feature baseline it is required to beat (strategy R-01).

    ref: optional {'frontal': (mean, sd), 'posterior': (...), 'whole_head': (...)} from the TRAINING fold.
    Returns uce_v1, baseline_whole_head_z, and the frontal/posterior correlation that determines whether the
    two-region structure carries any information at all.
    """
    fr, po, wh = (np.asarray(a, float) for a in (frontal, posterior, whole_head))
    ref = ref or {}
    zf = zscore(fr, *ref.get("frontal", (None, None)))
    zp = zscore(po, *ref.get("posterior", (None, None)))
    zw = zscore(wh, *ref.get("whole_head", (None, None)))
    ok = np.isfinite(fr) & np.isfinite(po)
    r = float(np.corrcoef(fr[ok], po[ok])[0, 1]) if ok.sum() > 2 else float("nan")
    return {
        "uce_v1": uce_v1_from_z(zf, zp),
        "baseline_whole_head_z": zw,
        "r_frontal_posterior": r,
        # If the two regions are this correlated, PC1 variance-explained is (1+r)/2 by construction.
        "implied_pc1_variance_explained": (1.0 + r) / 2.0 if np.isfinite(r) else float("nan"),
        "version": UCE_V1_VERSION,
    }
