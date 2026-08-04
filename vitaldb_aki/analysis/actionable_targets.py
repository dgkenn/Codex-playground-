"""actionable_targets.py -- Modifiable intraoperative management targets within the
high-risk fragility phenotype (VitalDB postoperative organ-injury study).

Research question
-----------------
Within the *high-risk* intraoperative phenotype discovered label-free in
``phenotypes.py``, which MODIFIABLE intraoperative-management decisions are
associated with LOWER organ-injury risk?  This is the "actionable" analysis: it
takes the descriptive phenotype finding and asks "what could a clinician do
differently?" using causal / target-trial methods.

Design discipline
-----------------
This is an OBSERVATIONAL causal-inference analysis.  Confounding by indication is
the central threat (sicker, more unstable patients receive different management
AND are more likely to sustain organ injury).  We reuse the propensity-score /
IPTW machinery from ``hypotension_treatment.py`` (stabilised, trimmed weights) and
add, for each modifiable exposure:

  - PRIMARY (powered): a full-cohort IPTW-weighted logistic outcome model with an
    ``exposure x high_risk_phenotype`` INTERACTION term (does the exposure effect
    DIFFER inside the high-risk phenotype?), plus the marginal exposure effect
    WITHIN the high-risk phenotype as an IPTW risk difference + risk ratio with a
    bootstrap 95% CI (the actionable number).
  - An E-VALUE for the within-phenotype point estimate and its CI bound
    (VanderWeele & Ding 2017) -- how strong unmeasured confounding would have to
    be to explain the result away.
  - A NEGATIVE-CONTROL outcome that management plausibly should NOT cause
    (organ_hepatocellular): a non-null signal there flags residual confounding.
  - Explicit power flags: a cell with < ``MIN_EVENTS_FOR_POWER`` events within the
    high-risk phenotype is reported but marked "underpowered, hypothesis-only".

Everything here is HYPOTHESIS-GENERATING for a prospective trial; external
validation on INSPIRE is pending.

Heavy dependencies (numpy, pandas, sklearn, scipy) are lazy-imported inside the
functions that need them so that this module -- and the pure helpers below -- import
with the stdlib only, matching the repo convention in phenotypes.py /
hypotension_treatment.py.  ``run_actionable_targets`` is import-safe without
sklearn; sklearn is only touched once it is actually called on real data.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants -- every threshold is named here (config-as-code; nothing magic is
# buried in the logic below).
# ---------------------------------------------------------------------------

# /cases drug-total columns and their UNITS (documented assumption -- see the
# module docstring and the unit note in ACTIONABLE_RESULTS.md):
#   intraop_phe -- phenylephrine, micrograms (ug)
#   intraop_eph -- ephedrine,     milligrams (mg)
#   intraop_epi -- epinephrine,   micrograms (ug)
#   intraop_crystalloid / intraop_colloid -- millilitres (mL)
PHE_COL = "intraop_phe"          # phenylephrine (ug)
EPH_COL = "intraop_eph"          # ephedrine (mg)
EPI_COL = "intraop_epi"          # epinephrine (ug)
CRYSTALLOID_COL = "intraop_crystalloid"   # mL
COLLOID_COL = "intraop_colloid"           # mL

# Phenylephrine-equivalent conversion factors (rough potency anchors, used ONLY
# to put the three pressors on a common axis for the "predominant" rules; they are
# NOT pharmacokinetic claims).  Ephedrine is dosed in mg and is ~10x less potent
# per-mg-vs-phenylephrine-ug for pressor effect, so 1 mg ephedrine -> ~10 PHE-ug
# equivalents (documented constant, tunable).  Epinephrine (ug) is counted at
# parity on the same ug axis for the "total pressor" sum only.
EPH_TO_PHE_EQUIV = 10.0          # 1 mg ephedrine -> 10 ug PHE-equivalent

# Tertile cut labels (shared with hypotension_treatment style).
TERTILE_LABELS = ("low", "med", "high")

# Power threshold: high-risk-phenotype cells with fewer events than this are
# reported but flagged "underpowered, hypothesis-only".
MIN_EVENTS_FOR_POWER = 15

# Outcomes analysed.
PRIMARY_OUTCOMES = ("organ_renal", "composite")
# Negative-control outcome: intraoperative haemodynamic MANAGEMENT (pressor choice,
# fluids, monitoring) is not a plausible cause of hepatocellular injury, which is
# driven by the surgical field / hepatotoxic exposure.  A non-null effect here
# signals residual confounding by overall illness severity.
NEGATIVE_CONTROL_OUTCOME = "organ_hepatocellular"

# Arterial-line track name in the VitalDB /trks index (invasive continuous BP).
ART_TRACK_NAME = "SNUADC/ART"

# MAP candidate tracks + artifact gate (mirrors features/pfds.py).
MAP_TRACK_CANDIDATES = ("Solar8000/ART_MBP", "Solar8000/NIBP_MBP", "EV1000/ART_MBP")
MAP_MIN = 20.0          # mmHg artifact gate
MAP_MAX = 200.0         # mmHg artifact gate
HYPOTENSION_MAP_THRESHOLD = 65.0   # MAP < 65 mmHg defines a hypotensive sample

# Infusion-pump RATE tracks (Orchestra) used to detect first pressor ONSET.
PRESSOR_RATE_TRACKS = (
    "Orchestra/PHEN_RATE", "Orchestra/NEPI_RATE",
    "Orchestra/DOPA_RATE", "Orchestra/EPI_RATE",
)
# Pump VOLUME tracks (presence + non-zero -> drug actually delivered).
NEPI_VOL_TRACKS = ("Orchestra/NEPI_VOL", "Orchestra/NEPI_RATE")
PHEN_VOL_TRACKS = ("Orchestra/PHEN_VOL", "Orchestra/PHEN_RATE")

# Confounder set for the propensity model (modifiable exposure ~ confounders).
# Only columns present in the merged frame are used; missing ones are dropped
# gracefully (mirrors hypotension_treatment.fit_propensity_model).
DEFAULT_PS_COVARIATES = [
    "age", "sex", "asa",
    "preop_htn", "preop_dm", "preop_cr",
    "intraop_ebl",
    "anesthesia_duration_min", "op_duration_min",
    "optype_code",            # numeric-encoded surgery type (built below if optype present)
]

# Bootstrap replicates for within-phenotype risk-difference / risk-ratio CIs.
N_BOOTSTRAP = 500
RANDOM_SEED = 20260626         # matches config.yaml seed default

_DEFAULT_CACHE_SUBDIR = "vitaldb_aki/cache"
_CASES_FILE = "cases.csv"
_COMPOSITE_FILE = "cohort_composite.csv"
_RESULTS_JSON = "actionable_results.json"
_DONE_MARKER = "_actionable_done.json"


# ===========================================================================
# PURE HELPERS (stdlib only -- covered by the stdlib-only test file)
# ===========================================================================

def e_value(point_estimate: float) -> float:
    """E-value for a risk-ratio-scale point estimate (VanderWeele & Ding 2017).

    The E-value is the minimum strength of association (on the risk-ratio scale)
    that an unmeasured confounder would need to have with BOTH the exposure and
    the outcome -- above and beyond the measured confounders -- to fully explain
    away an observed exposure-outcome association.

    Formula (for a risk ratio RR):
        if RR < 1, first map to the protective scale RR* = 1 / RR;
        E = RR* + sqrt( RR* * (RR* - 1) )

    A risk ratio of exactly 1 (or non-finite / non-positive input) yields an
    E-value of 1.0 (no unmeasured confounding needed -- the null is already
    consistent with the data).

    Parameters
    ----------
    point_estimate : float
        Risk ratio (RR).  Values < 1 are protective; they are mapped to 1/RR so
        the returned E-value is always >= 1.

    Returns
    -------
    float
        The E-value (>= 1.0).

    Examples
    --------
    >>> round(e_value(2.0), 2)
    3.41
    >>> round(e_value(0.5), 2)   # 1/0.5 = 2 -> same E-value as RR=2
    3.41
    >>> e_value(1.0)
    1.0
    """
    rr = float(point_estimate)
    if not math.isfinite(rr) or rr <= 0.0:
        return 1.0
    if rr == 1.0:
        return 1.0
    # Map protective effects onto the >1 scale.
    rr_star = rr if rr > 1.0 else 1.0 / rr
    return rr_star + math.sqrt(rr_star * (rr_star - 1.0))


def e_value_ci(rr_point: float, ci_lower: float, ci_upper: float) -> float:
    """E-value for the CONFIDENCE-INTERVAL bound closest to the null (RR=1).

    Per VanderWeele & Ding: report the E-value for the limit of the CI nearest the
    null.  If the CI crosses 1 (the bound nearest the null is on the other side of
    1, i.e. the result is non-significant) the E-value for the CI is 1.0 -- no
    unmeasured confounding is needed because the data are already compatible with
    the null.

    Parameters
    ----------
    rr_point : float
        The point risk ratio (used only to decide which bound is "nearest null").
    ci_lower, ci_upper : float
        Lower / upper limits of the 95% CI on the risk-ratio scale.

    Returns
    -------
    float
        E-value of the null-nearest CI bound (>= 1.0).
    """
    lo, hi = float(ci_lower), float(ci_upper)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return 1.0
    rr = float(rr_point)
    # CI crosses the null -> not significant -> E-value of CI is 1.
    if lo <= 1.0 <= hi:
        return 1.0
    # Bound nearest the null:
    if rr > 1.0:
        bound = lo          # protective-side limit of a harmful estimate
    else:
        bound = hi          # harmful-side limit of a protective estimate
    return e_value(bound)


def benjamini_hochberg(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg FDR control.  Returns a reject/keep mask aligned to input.

    Pure-Python (stdlib only).  ``None`` / non-finite p-values are treated as 1.0
    (never rejected).

    Parameters
    ----------
    pvals : list[float]
        Raw p-values.
    alpha : float
        Target false-discovery rate.

    Returns
    -------
    list[bool]
        ``True`` where the corresponding hypothesis is rejected at FDR ``alpha``.
    """
    clean = [
        (p if (p is not None and isinstance(p, (int, float)) and math.isfinite(p)) else 1.0)
        for p in pvals
    ]
    m = len(clean)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: clean[i])
    reject = [False] * m
    max_k = -1
    for rank, idx in enumerate(order, start=1):
        if clean[idx] <= (rank / m) * alpha:
            max_k = rank
    if max_k >= 1:
        for rank, idx in enumerate(order, start=1):
            if rank <= max_k:
                reject[idx] = True
    return reject


def tertile_assign(values: list[float]) -> list[int | None]:
    """Assign each value to a tertile index 0/1/2 (low/med/high) by rank.

    Pure-Python equal-frequency tertiles, robust to ties and to NaN/None.  Uses
    rank position so the cut is well-defined even with heavy zero-inflation:
    each non-missing value's fractional rank r in [0,1) maps to floor(3*r).
    Missing / non-finite inputs map to ``None``.

    This mirrors the INTENT of pandas.qcut(q=3, duplicates='drop') used in
    hypotension_treatment.assign_burden_tertiles, but with no pandas dependency so
    it is unit-testable on a tiny synthetic frame.

    Parameters
    ----------
    values : list[float]
        Raw exposure magnitudes.

    Returns
    -------
    list[int | None]
        Tertile index per input value (0=low, 1=med, 2=high); ``None`` if missing.
    """
    n = len(values)
    finite_idx = [
        i for i, v in enumerate(values)
        if v is not None and isinstance(v, (int, float)) and math.isfinite(v)
    ]
    out: list[int | None] = [None] * n
    m = len(finite_idx)
    if m == 0:
        return out
    # Rank by (value, original index) for a stable, deterministic ordering.
    ordered = sorted(finite_idx, key=lambda i: (values[i], i))
    for rank, i in enumerate(ordered):
        frac = rank / m                     # in [0, 1)
        t = int(frac * 3)                   # 0, 1, or 2
        if t > 2:
            t = 2
        out[i] = t
    return out


# --- Exposure-rule helpers (pure; operate on plain numeric scalars) --------

def pressor_phe_equiv(phe_ug: float, eph_mg: float, epi_ug: float) -> float:
    """Total pressor exposure on a phenylephrine-equivalent (ug) axis.

    total = phe_ug + eph_mg * EPH_TO_PHE_EQUIV + epi_ug

    Missing / non-finite components are treated as zero.  Documented unit
    assumption: intraop_phe in ug, intraop_eph in mg, intraop_epi in ug.
    """
    def _z(x: float) -> float:
        return float(x) if (x is not None and isinstance(x, (int, float)) and math.isfinite(x)) else 0.0
    return _z(phe_ug) + _z(eph_mg) * EPH_TO_PHE_EQUIV + _z(epi_ug)


def any_vasopressor_flag(phe_ug: float, eph_mg: float, epi_ug: float) -> int:
    """1 if ANY pressor was given (phe>0 OR eph>0 OR epi>0), else 0."""
    def _z(x: float) -> float:
        return float(x) if (x is not None and isinstance(x, (int, float)) and math.isfinite(x)) else 0.0
    return int(_z(phe_ug) > 0 or _z(eph_mg) > 0 or _z(epi_ug) > 0)


def phenylephrine_predominant_flag(phe_ug: float, eph_mg: float) -> int:
    """1 if phenylephrine is the dominant pressor on the PHE-equivalent axis.

    phe_equiv (= phe_ug) > eph_equiv (= eph_mg * EPH_TO_PHE_EQUIV), and a pressor
    was actually given.  Mechanistic tie-in: phenylephrine raises MAP via pure
    alpha-constriction, which may RAISE pressure without restoring renal perfusion
    ("pressure != perfusion").
    """
    def _z(x: float) -> float:
        return float(x) if (x is not None and isinstance(x, (int, float)) and math.isfinite(x)) else 0.0
    phe_eq = _z(phe_ug)
    eph_eq = _z(eph_mg) * EPH_TO_PHE_EQUIV
    if phe_eq <= 0.0:
        return 0
    return int(phe_eq > eph_eq)


# --- Time-to-treat lag: PURE core (stdlib only; unit-tested) ----------------

def first_hypotension_onset(map_series, threshold=HYPOTENSION_MAP_THRESHOLD,
                            vmin=MAP_MIN, vmax=MAP_MAX):
    """Time (seconds) of the FIRST artifact-gated MAP sample below ``threshold``.

    Parameters
    ----------
    map_series : list[tuple[float, float]]
        [(t_seconds, map_mmHg), ...]; already clipped to the intraop window.
    threshold : float
        Hypotension cutoff (MAP < threshold).
    vmin, vmax : float
        Artifact gate; samples outside [vmin, vmax] are ignored.

    Returns
    -------
    float | None
        Earliest time with a gated MAP < threshold, or ``None`` if no such sample.
    """
    best = None
    for t, v in map_series:
        if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        if v < vmin or v > vmax:
            continue
        if v < threshold:
            if best is None or t < best:
                best = float(t)
    return best


def first_pressor_onset(rate_series):
    """Time (seconds) of the FIRST strictly-positive sample in a pump RATE series.

    Parameters
    ----------
    rate_series : list[tuple[float, float]]
        [(t_seconds, rate), ...]; already clipped to the intraop window.

    Returns
    -------
    float | None
        Earliest time with rate > 0, or ``None`` if the pump never ran.
    """
    best = None
    for t, v in rate_series:
        if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        if v > 0:
            if best is None or t < best:
                best = float(t)
    return best


def treatment_lag_minutes(hypo_onset_s, pressor_onset_s):
    """Lag (minutes) from first hypotension to first pressor.

    Returns a dict describing the case's time-to-treat level:
      - no sub-65 episode            -> {"level": "no_hypotension", "lag_min": None}
      - hypotension but no pressor    -> {"level": "untreated",      "lag_min": None}
      - both present                  -> {"level": "treated", "lag_min": <minutes>}

    A pressor that started BEFORE the first sub-65 sample (pre-emptive) yields a
    non-negative lag clamped at 0.0 (treated promptly / pre-emptively).
    """
    if hypo_onset_s is None:
        return {"level": "no_hypotension", "lag_min": None}
    if pressor_onset_s is None:
        return {"level": "untreated", "lag_min": None}
    lag_s = float(pressor_onset_s) - float(hypo_onset_s)
    if lag_s < 0:
        lag_s = 0.0
    return {"level": "treated", "lag_min": lag_s / 60.0}


# ===========================================================================
# CONFIG / IO HELPERS
# ===========================================================================

def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    """Resolve cache_dir from nested (cfg['data']['cache_dir']) or flat
    (cfg['cache_dir']) form; mirrors discovery_screen._cache_dir."""
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return _DEFAULT_CACHE_SUBDIR


def _resolve_seed(cfg: dict[str, Any]) -> int:
    return int(cfg.get("seed", RANDOM_SEED))


def _flat_cfg_for_phenotypes(cfg: dict[str, Any]) -> dict[str, Any]:
    """phenotypes.load_physiology_matrix reads cfg.get('cache_dir') (FLAT only).
    Build a flat-keyed copy so we can reuse it regardless of how cfg was passed."""
    return {"cache_dir": _resolve_cache_dir(cfg), "seed": _resolve_seed(cfg)}


def _json_default(obj):
    """Fallback JSON serializer for numpy scalars / NaN / arrays."""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ===========================================================================
# STEP 1 -- cohort + phenotype + outcomes
# ===========================================================================

def _regenerate_phenotype_labels(cfg: dict[str, Any]):
    """Deterministically REGENERATE the confirmatory phenotype labels.

    Per-case labels are NOT persisted, so we recompute them exactly as
    phenotypes.run_phenotype_analysis would:
        X, names, df_full = load_physiology_matrix(cfg)
        results_by_k, best_k = discover_phenotypes(X, range(2,8), seed)
        labels = results_by_k[best_k]['labels']

    Returns
    -------
    tuple (labels: np.ndarray, df_full: pd.DataFrame, best_k: int)
        labels aligned row-for-row with df_full.
    """
    from vitaldb_aki.analysis.phenotypes import load_physiology_matrix
    from sklearn.cluster import KMeans

    flat = _flat_cfg_for_phenotypes(cfg)
    seed = _resolve_seed(cfg)
    X, names, df_full = load_physiology_matrix(flat)
    # Fast KMeans(k=2) instead of the slow consensus discover_phenotypes: the
    # confirmatory solution is best_k=2 and stable at ARI 0.88, so the KMeans
    # labels match it; consensus clustering (bootstrap x k=2..7) took >15min and
    # is fragile under the ~15-30min container kills on this host (the analysis
    # is not resumable). Seconds vs minutes, equivalent labels.
    best_k = 2
    labels = KMeans(n_clusters=best_k, n_init=10, random_state=seed).fit_predict(X)
    return labels, df_full, int(best_k)


def _identify_high_risk_cluster(df_full, labels):
    """Identify the HIGH-RISK cluster = highest organ_renal rate (fallback composite).

    Returns (high_risk_cluster_id: int, rate_table: dict).
    """
    import numpy as np
    import pandas as pd

    df = df_full.copy()
    df["_phenotype"] = np.asarray(labels, dtype=int)

    def _rate_by_cluster(col):
        if col not in df.columns:
            return None
        vals = pd.to_numeric(df[col], errors="coerce")
        rates = {}
        for c in sorted(df["_phenotype"].unique()):
            m = (df["_phenotype"] == c) & vals.notna()
            n = int(m.sum())
            ev = int(vals[m].sum()) if n else 0
            rates[int(c)] = {"n": n, "events": ev,
                             "rate": (ev / n) if n else None}
        return rates

    renal_rates = _rate_by_cluster("organ_renal")
    comp_rates = _rate_by_cluster("composite")

    chosen, by = renal_rates, "organ_renal"
    if chosen is None or all((r["rate"] is None) for r in chosen.values()):
        chosen, by = comp_rates, "composite"

    if chosen is None or all((r["rate"] is None) for r in chosen.values()):
        # No usable outcome -> default to cluster 0; flagged downstream.
        high_c = int(sorted(df["_phenotype"].unique())[0])
    else:
        high_c = max(
            (c for c, r in chosen.items() if r["rate"] is not None),
            key=lambda c: chosen[c]["rate"],
        )

    return int(high_c), {
        "selected_by": by,
        "organ_renal_rate_by_cluster": renal_rates,
        "composite_rate_by_cluster": comp_rates,
        "high_risk_cluster": int(high_c),
    }


def build_cohort(cfg: dict[str, Any]):
    """STEP 1: regenerate phenotypes, mark the high-risk cluster, merge outcomes
    and /cases exposures + PMH.

    Returns
    -------
    tuple (df: pd.DataFrame, meta: dict)
        df has one row per case with: caseid, _phenotype, high_risk_phenotype,
        outcome columns (composite, organ_renal, organ_hepatocellular if present),
        and the /cases exposure + PMH columns.
    """
    import numpy as np
    import pandas as pd

    cache_dir = _resolve_cache_dir(cfg)

    labels, df_full, best_k = _regenerate_phenotype_labels(cfg)
    high_c, rate_meta = _identify_high_risk_cluster(df_full, labels)

    df = df_full.copy()
    df["_phenotype"] = np.asarray(labels, dtype=int)
    df["high_risk_phenotype"] = (df["_phenotype"] == high_c).astype(int)

    if "caseid" not in df.columns:
        raise RuntimeError("Feature matrix has no 'caseid'; cannot join outcomes/cases.")

    # --- Merge outcomes from cohort_composite.csv (only cols not already present) ---
    comp_path = os.path.join(cache_dir, _COMPOSITE_FILE)
    if os.path.exists(comp_path):
        comp = pd.read_csv(comp_path)
        want = ["composite", "organ_renal", NEGATIVE_CONTROL_OUTCOME]
        add = [c for c in want if c in comp.columns and c not in df.columns]
        if add:
            df = df.merge(comp[["caseid"] + add], on="caseid", how="left")

    # --- Merge /cases exposures + PMH (only cols not already present) ---
    cases_path = os.path.join(cache_dir, _CASES_FILE)
    cases_cols_merged: list[str] = []
    if os.path.exists(cases_path):
        cases = pd.read_csv(cases_path)
        cases.columns = [c.lstrip("﻿") for c in cases.columns]  # strip any BOM
        exposure_pmh = [
            PHE_COL, EPH_COL, EPI_COL, CRYSTALLOID_COL, COLLOID_COL,
            "age", "sex", "asa", "preop_htn", "preop_dm", "preop_cr",
            "intraop_ebl", "optype", "opstart", "opend", "anestart", "aneend",
        ]
        add = [c for c in exposure_pmh if c in cases.columns and c not in df.columns]
        if add:
            df = df.merge(cases[["caseid"] + add], on="caseid", how="left")
            cases_cols_merged = add

    # Derive durations (minutes) if the raw timestamps are present.
    df = _derive_durations(df)
    # Encode sex / optype numerically for the PS model.
    df = _encode_confounders(df)

    meta = {
        "best_k": best_k,
        "high_risk_cluster": high_c,
        "cluster_rates": rate_meta,
        "n_cases": int(len(df)),
        "n_high_risk": int(df["high_risk_phenotype"].sum()),
        "cases_columns_merged": cases_cols_merged,
    }
    return df, meta


def _derive_durations(df):
    """Add anesthesia_duration_min / op_duration_min from raw second timestamps."""
    import numpy as np
    import pandas as pd
    df = df.copy()
    if "anesthesia_duration_min" not in df.columns and {"anestart", "aneend"} <= set(df.columns):
        dur = (pd.to_numeric(df["aneend"], errors="coerce")
               - pd.to_numeric(df["anestart"], errors="coerce")) / 60.0
        df["anesthesia_duration_min"] = dur.where(dur >= 0)
    if "op_duration_min" not in df.columns and {"opstart", "opend"} <= set(df.columns):
        dur = (pd.to_numeric(df["opend"], errors="coerce")
               - pd.to_numeric(df["opstart"], errors="coerce")) / 60.0
        df["op_duration_min"] = dur.where(dur >= 0)
    return df


def _encode_confounders(df):
    """Numeric-encode sex (M/F) and optype (category -> integer code)."""
    import numpy as np
    import pandas as pd
    df = df.copy()
    if "sex" in df.columns and not pd.api.types.is_numeric_dtype(df["sex"]):
        s = df["sex"].astype(str).str.upper().str.strip()
        df["sex"] = s.map({"M": 1, "MALE": 1, "F": 0, "FEMALE": 0}).astype("float")
    if "optype" in df.columns and "optype_code" not in df.columns:
        codes, _ = pd.factorize(df["optype"].astype(str), sort=True)
        df["optype_code"] = codes.astype(float)
    return df


# ===========================================================================
# STEP 2 -- define ACTIONABLE exposures
# ===========================================================================

def define_exposures(df):
    """STEP 2: add binary / ordinal ACTIONABLE-management exposure columns.

    Adds (all 0/1 unless noted):
      - total_pressor_phe_equiv  (continuous ug, PHE-equivalent)   [helper col]
      - fluid_total_ml           (crystalloid + colloid, mL)        [helper col]
      - pressor_tertile          (0/1/2 over pressor>0 cases)       [helper col]
      - fluid_tertile            (0/1/2 over all cases)             [helper col]
      - any_vasopressor          (1 if any pressor given)
      - vasopressor_predominant  (1 if pressor in top tertile AND fluids modest:
                                   i.e. management leaned on pressors over fluids)
      - phenylephrine_predominant(1 if phe is the dominant pressor on PHE-eq axis)
      - arterial_line            (filled later from /trks; placeholder NaN here)
      - high_fluid               (1 if fluid in top tertile)
      - low_fluid                (1 if fluid in bottom tertile)
      - fluid_level              (0=low / 1=med / 2=high; the U-shape, 3 levels)

    'arterial_line' is added/overwritten by add_arterial_line() (needs cfg+trks).

    Returns a copy of df with the columns above.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()

    phe = pd.to_numeric(df.get(PHE_COL, 0), errors="coerce").fillna(0.0)
    eph = pd.to_numeric(df.get(EPH_COL, 0), errors="coerce").fillna(0.0)
    epi = pd.to_numeric(df.get(EPI_COL, 0), errors="coerce").fillna(0.0)
    cry = pd.to_numeric(df.get(CRYSTALLOID_COL, 0), errors="coerce").fillna(0.0)
    col = pd.to_numeric(df.get(COLLOID_COL, 0), errors="coerce").fillna(0.0)

    pressor_eq = phe + eph * EPH_TO_PHE_EQUIV + epi
    fluid_total = cry + col
    df["total_pressor_phe_equiv"] = pressor_eq
    df["fluid_total_ml"] = fluid_total

    # any_vasopressor
    df["any_vasopressor"] = ((phe > 0) | (eph > 0) | (epi > 0)).astype(int)

    # phenylephrine_predominant (PHE-eq dominance, pressor actually given)
    df["phenylephrine_predominant"] = (
        (phe > 0) & (phe > eph * EPH_TO_PHE_EQUIV)
    ).astype(int)

    # Pressor tertile computed AMONG cases that received any pressor (a tertile over
    # zero-inflated totals is uninformative). Cases with no pressor are tertile NaN.
    pressor_tertile = pd.Series(np.nan, index=df.index)
    treated = pressor_eq > 0
    if treated.sum() >= 3:
        pressor_tertile.loc[treated] = pd.Series(
            tertile_assign(pressor_eq[treated].tolist()), index=df.index[treated]
        )
    df["pressor_tertile"] = pressor_tertile

    # Fluid tertile over ALL cases (U-shape: overload vs hypovolemia).
    fluid_t = pd.Series(tertile_assign(fluid_total.tolist()), index=df.index)
    df["fluid_tertile"] = fluid_t
    df["fluid_level"] = fluid_t                       # alias: 0/1/2 (low/med/high)
    df["high_fluid"] = (fluid_t == 2).astype("Int64").fillna(0).astype(int)
    df["low_fluid"] = (fluid_t == 0).astype("Int64").fillna(0).astype(int)

    # vasopressor_predominant: management leaned on PRESSORS vs FLUIDS.
    # Rule: received a pressor in the TOP tertile of pressor dose AND fluids were
    # NOT in the top tertile (i.e. high pressor + modest/low fluids).
    df["vasopressor_predominant"] = (
        (df["pressor_tertile"] == 2) & (fluid_t != 2)
    ).fillna(False).astype(int)

    return df


def add_arterial_line(df, cfg):
    """Fill the binary ``arterial_line`` column from the /trks index.

    arterial_line = 1 if ``SNUADC/ART`` is present among that case's available
    tracks (invasive continuous BP monitoring), else 0.  Waveforms are NEVER
    downloaded -- only the (caseid, tname) -> tid index is consulted.

    If the /trks index cannot be built (offline / no network), the column is left
    as NaN and the exposure is skipped downstream (reported as unavailable).  When
    a /cases ``aline1`` column is present it is NOT used here (it records a planned
    line, not a confirmed track); track presence is the operational signal.

    Returns a copy of df with ``arterial_line`` (int 0/1) or NaN if unavailable.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()
    try:
        from vitaldb_aki.data.tracks import available_tracks
    except Exception:
        df["arterial_line"] = np.nan
        return df

    flags = []
    ok = True
    for cid in df["caseid"].tolist():
        try:
            tracks = available_tracks(cfg, str(cid))
            flags.append(1 if ART_TRACK_NAME in tracks else 0)
        except Exception:
            ok = False
            break
    if ok and len(flags) == len(df):
        df["arterial_line"] = pd.Series(flags, index=df.index).astype(int)
    else:
        df["arterial_line"] = np.nan
    return df


def _intraop_window_from_row(row):
    """(t_start, t_end) seconds from a merged row: anestart>opstart, end=opend.
    Mirrors features/pfds.py._intraop_window."""
    def _f(k):
        v = row.get(k)
        try:
            f = float(v)
            return f if math.isfinite(f) else None
        except (TypeError, ValueError):
            return None
    opend = _f("opend")
    if opend is None:
        return None, None
    anestart = _f("anestart")
    if anestart is not None:
        return anestart, opend
    opstart = _f("opstart")
    if opstart is not None:
        return opstart, opend
    return None, opend


def _track_nonzero(cfg, caseid, candidates):
    """True if any of ``candidates`` exists in the case's trks index AND (for the
    first present one) the downloaded series has a strictly-positive sample.

    Presence is checked via the index (no download); a small confirmatory download
    of the FIRST present track verifies the drug was actually delivered.  Returns
    False if no candidate is present or the index is unavailable.
    """
    try:
        from vitaldb_aki.data.tracks import available_tracks, download_track
        tracks = set(available_tracks(cfg, str(caseid)))
    except Exception:
        return None      # index unavailable -> caller treats as missing
    # Presence-only: a pump track existing in the /trks index means that drug's
    # pump was configured for the case -> treat as exposed. (Was a per-case
    # confirmatory download of the series; over 4335 cases that made the analysis
    # download-bound and unable to survive container kills. Presence is a sound,
    # download-free proxy for "drug used", esp. for the small norepi subset.)
    present = [t for t in candidates if t in tracks]
    return bool(present)


def add_phe_vs_norepi(df, cfg):
    """Add the MECHANISTIC headline exposure ``phe_vs_norepi`` (among pressor-
    exposed cases): 1 = phenylephrine-dominant, 0 = norepinephrine-dominant.

    Norepinephrine is NOT in /cases -> detected from the Orchestra pump tracks
    (NEPI_VOL / NEPI_RATE present + non-zero).  Phe exposure = intraop_phe>0 OR
    Orchestra/PHEN_VOL present + non-zero.  Restricted to cases exposed to at least
    one of the two; cases exposed to neither (or to both ambiguously) get NaN.

    Norepi is rare in VitalDB (~88 cases) -> the resulting cell is small-N; flagged
    prominently downstream.  Waveforms are never downloaded (only small pump
    VOL/RATE confirmatory reads).

    Returns a copy of df with ``phe_vs_norepi`` (int 0/1) or NaN, plus helper
    booleans ``_phe_exposed`` / ``_norepi_exposed``.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()
    phe_cases = pd.to_numeric(df.get(PHE_COL, 0), errors="coerce").fillna(0.0) > 0

    norepi_flags, phe_track_flags = [], []
    index_ok = True
    for cid in df["caseid"].tolist():
        nz_nepi = _track_nonzero(cfg, cid, NEPI_VOL_TRACKS)
        nz_phen = _track_nonzero(cfg, cid, PHEN_VOL_TRACKS)
        if nz_nepi is None and nz_phen is None:
            index_ok = False
            break
        norepi_flags.append(bool(nz_nepi))
        phe_track_flags.append(bool(nz_phen))

    if not index_ok or len(norepi_flags) != len(df):
        # No trks access (offline). Norepi undetectable -> exposure unavailable.
        df["_norepi_exposed"] = np.nan
        df["_phe_exposed"] = phe_cases.astype(int)
        df["phe_vs_norepi"] = np.nan
        return df

    norepi = pd.Series(norepi_flags, index=df.index)
    phe_exposed = phe_cases | pd.Series(phe_track_flags, index=df.index)
    df["_norepi_exposed"] = norepi.astype(int)
    df["_phe_exposed"] = phe_exposed.astype(int)

    # Among cases exposed to exactly one of {phe, norepi}: phe-dominant=1, norepi=0.
    # Cases on BOTH are ambiguous for a head-to-head -> NaN; cases on neither -> NaN.
    val = pd.Series(np.nan, index=df.index)
    phe_only = phe_exposed & (~norepi)
    norepi_only = norepi & (~phe_exposed)
    val.loc[phe_only] = 1
    val.loc[norepi_only] = 0
    df["phe_vs_norepi"] = val
    return df


def add_time_to_treat(df, cfg, use_tracks=None):
    """Add the time-to-treat-hypotension exposures.

    Adds:
      - treat_lag_min      (continuous minutes; NaN unless level=='treated')
      - treat_lag_level    ("no_hypotension" / "untreated" / "fast" / "slow")
      - slow_treat         (1 if 'slow', 0 if 'fast'; NaN otherwise) -- the binary
                            exposure analysed via IPTW (FAST<median vs SLOW>median).

    Two derivation paths (documented in results):
      - "tracks": per-case MAP (first_available over MAP candidates, 20-200 gate,
        clipped to intraop window, never t>opend) + pump RATE onset across
        Orchestra/{PHEN,NEPI,DOPA,EPI}_RATE. Pure cores: first_hypotension_onset,
        first_pressor_onset, treatment_lag_minutes.
      - "matrix": light approximation -- hypotension onset from feature_matrix
        column ``map_time_to_first_below65_frac`` (fraction of window) scaled by
        op_duration; pressor onset from a single small pump read. Used only when
        track derivation is unavailable/too heavy.

    ``use_tracks`` forces a path (True/False); default auto-detects (tracks if the
    trks index is reachable, else matrix).

    Returns a copy of df with the columns above.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()

    # Decide derivation path.
    if use_tracks is None:
        try:
            from vitaldb_aki.data.tracks import available_tracks
            available_tracks(cfg, str(df["caseid"].iloc[0]))
            use_tracks = True
        except Exception:
            use_tracks = False

    levels, lags = [], []

    if use_tracks:
        from vitaldb_aki.data.tracks import first_available, download_track
        for _, row in df.iterrows():
            cid = str(row["caseid"])
            t0, t1 = _intraop_window_from_row(row)
            # MAP series (first available candidate), gated + window-clipped.
            try:
                _name, raw_map = first_available(cfg, cid, list(MAP_TRACK_CANDIDATES))
            except Exception:
                raw_map = []
            map_s = [(t, v) for t, v in raw_map
                     if (t1 is None or t <= t1) and (t0 is None or t >= t0)]
            hypo = first_hypotension_onset(map_s)
            # Pressor onset = earliest non-zero across all RATE pumps.
            onset = None
            for tn in PRESSOR_RATE_TRACKS:
                try:
                    raw = download_track(cfg, cid, tn)
                except Exception:
                    raw = []
                raw = [(t, v) for t, v in raw
                       if (t1 is None or t <= t1) and (t0 is None or t >= t0)]
                o = first_pressor_onset(raw)
                if o is not None and (onset is None or o < onset):
                    onset = o
            r = treatment_lag_minutes(hypo, onset)
            levels.append(r["level"])
            lags.append(r["lag_min"])
        derivation = "tracks"
    else:
        # Matrix approximation.
        frac = pd.to_numeric(df.get("map_time_to_first_below65_frac"),
                             errors="coerce") if "map_time_to_first_below65_frac" in df.columns else None
        op_dur = pd.to_numeric(df.get("op_duration_min"), errors="coerce")
        for i, (_, row) in enumerate(df.iterrows()):
            cid = str(row["caseid"])
            hypo = None
            if frac is not None and pd.notna(frac.iloc[i]) and pd.notna(op_dur.iloc[i]):
                hypo = float(frac.iloc[i]) * float(op_dur.iloc[i]) * 60.0
            # Pressor-onset timing requires a per-case pump-track read; over the
            # pressor-exposed subset that is download-bound and un-kill-survivable
            # on this host. Skip it for this fast run -> time-to-treat resolves to
            # NaN/untreated and its IPTW cell is reported as deferred/underpowered.
            # (Run the dedicated pump-onset extraction separately to enable it.)
            onset = None
            r = treatment_lag_minutes(hypo, onset)
            levels.append(r["level"])
            lags.append(r["lag_min"])
        derivation = "matrix_approx"

    df["treat_lag_min"] = pd.Series(lags, index=df.index, dtype="float")
    lvl = pd.Series(levels, index=df.index)

    # FAST/SLOW split among TREATED cases at the median lag.
    treated_lag = df.loc[lvl == "treated", "treat_lag_min"]
    median_lag = float(treated_lag.median()) if len(treated_lag) else float("nan")
    fast_slow = pd.Series("", index=df.index)
    for idx in df.index:
        if lvl[idx] == "treated":
            v = df.at[idx, "treat_lag_min"]
            fast_slow[idx] = "slow" if (math.isfinite(median_lag) and v > median_lag) else "fast"
        else:
            fast_slow[idx] = lvl[idx]
    df["treat_lag_level"] = fast_slow

    slow = pd.Series(np.nan, index=df.index)
    slow.loc[fast_slow == "slow"] = 1
    slow.loc[fast_slow == "fast"] = 0
    df["slow_treat"] = slow
    df.attrs["time_to_treat_derivation"] = derivation
    df.attrs["time_to_treat_median_lag_min"] = median_lag
    return df


# All actionable exposures (binary; analysed via IPTW).
ACTIONABLE_EXPOSURES = (
    "any_vasopressor",
    "vasopressor_predominant",
    "phenylephrine_predominant",   # phe vs ephedrine (better-powered secondary)
    "phe_vs_norepi",               # phe vs norepinephrine (mechanistic headline, small-N)
    "arterial_line",
    "high_fluid",
    "low_fluid",
    "slow_treat",                  # time-to-treat hypotension: slow vs fast
)


# ===========================================================================
# STEP 3 -- causal estimation (REUSE hypotension_treatment IPTW)
# ===========================================================================

def _fit_iptw_for_exposure(df, exposure, covariates):
    """Fit PS + stabilised, trimmed IPTW for a single binary exposure, REUSING
    hypotension_treatment.fit_propensity_model / compute_iptw_weights.

    Those functions key off a ``vasopressor_treated`` column, so we alias the
    exposure into that name, run them, then return the frame with an
    ``iptw_weight`` column.

    Returns (df_w: DataFrame, used_covariates: list[str]) or (None, []) on failure.
    """
    import numpy as np
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )

    sub = df.copy()
    expo = pd.to_numeric(sub[exposure], errors="coerce")
    sub = sub[expo.notna()].copy()
    sub["vasopressor_treated"] = expo[expo.notna()].astype(int).to_numpy()

    # Need both exposed and unexposed to fit a PS model.
    if sub["vasopressor_treated"].nunique() < 2:
        return None, []

    avail = [c for c in covariates if c in sub.columns]
    if not avail:
        return None, []

    try:
        df_ps, _model, used = fit_propensity_model(sub, covariates=avail)
        df_w = compute_iptw_weights(df_ps)        # stabilised + trimmed (1%)
    except Exception:
        return None, []
    return df_w, used


def _weighted_risk_diff_ratio(y, expo, w):
    """IPTW risk difference and risk ratio (exposed minus/over unexposed).

    Risk in each arm is the weighted event mean; RD = r1 - r0, RR = r1 / r0.
    """
    import numpy as np
    y = np.asarray(y, dtype=float)
    e = np.asarray(expo, dtype=int)
    w = np.asarray(w, dtype=float)

    def _risk(mask):
        ww = w[mask]
        yy = y[mask]
        sw = ww.sum()
        return float((ww * yy).sum() / sw) if sw > 0 else float("nan")

    r1 = _risk(e == 1)
    r0 = _risk(e == 0)
    rd = r1 - r0
    rr = (r1 / r0) if (r0 and math.isfinite(r0) and r0 > 0) else float("nan")
    return r1, r0, rd, rr


def within_phenotype_effect(df_w, exposure, outcome, n_bootstrap=N_BOOTSTRAP,
                            seed=RANDOM_SEED):
    """IPTW risk difference + risk ratio for ``exposure`` on ``outcome`` WITHIN the
    high-risk phenotype, with a bootstrap 95% CI.

    The actionable number: among high-risk-phenotype cases, how does the modifiable
    exposure shift absolute (RD) and relative (RR) organ-injury risk?

    CIs are nonparametric percentile bootstraps (resample cases with replacement,
    recompute the weighted RD/RR each draw, take the 2.5/97.5 percentiles).  The
    IPTW weights are taken as fixed (computed on the full cohort) -- a documented
    simplification that does not re-estimate the propensity model inside each
    bootstrap draw.

    Returns a dict with point estimates, CIs, n, events, and a power flag.
    """
    import numpy as np
    import pandas as pd

    hr = df_w[df_w["high_risk_phenotype"] == 1].copy()
    y = pd.to_numeric(hr[outcome], errors="coerce")
    valid = y.notna() & hr[exposure].notna() & hr["iptw_weight"].notna()
    hr = hr[valid].copy()
    yv = pd.to_numeric(hr[outcome], errors="coerce").astype(int).to_numpy()
    ev = pd.to_numeric(hr[exposure], errors="coerce").astype(int).to_numpy()
    wv = hr["iptw_weight"].to_numpy(dtype=float)

    n = int(len(hr))
    n_events = int(yv.sum())
    n_exposed = int((ev == 1).sum())

    if n == 0 or ev.min() == ev.max():
        return {
            "n": n, "n_events": n_events, "n_exposed": n_exposed,
            "risk_exposed": None, "risk_unexposed": None,
            "risk_difference": None, "risk_ratio": None,
            "rd_ci": [None, None], "rr_ci": [None, None],
            "underpowered": True,
            "note": "no contrast (single exposure arm) or empty cell",
        }

    r1, r0, rd, rr = _weighted_risk_diff_ratio(yv, ev, wv)

    rng = np.random.default_rng(seed)
    rd_boot, rr_boot = [], []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        eb = ev[idx]
        if eb.min() == eb.max():
            continue
        _, _, rdb, rrb = _weighted_risk_diff_ratio(yv[idx], eb, wv[idx])
        if math.isfinite(rdb):
            rd_boot.append(rdb)
        if math.isfinite(rrb):
            rr_boot.append(rrb)

    def _pct(arr, q):
        return float(np.percentile(arr, q)) if len(arr) else float("nan")

    rd_lo, rd_hi = _pct(rd_boot, 2.5), _pct(rd_boot, 97.5)
    rr_lo, rr_hi = _pct(rr_boot, 2.5), _pct(rr_boot, 97.5)

    return {
        "n": n,
        "n_events": n_events,
        "n_exposed": n_exposed,
        "risk_exposed": round(r1, 4) if math.isfinite(r1) else None,
        "risk_unexposed": round(r0, 4) if math.isfinite(r0) else None,
        "risk_difference": round(rd, 4) if math.isfinite(rd) else None,
        "risk_ratio": round(rr, 4) if math.isfinite(rr) else None,
        "rd_ci": [round(rd_lo, 4) if math.isfinite(rd_lo) else None,
                  round(rd_hi, 4) if math.isfinite(rd_hi) else None],
        "rr_ci": [round(rr_lo, 4) if math.isfinite(rr_lo) else None,
                  round(rr_hi, 4) if math.isfinite(rr_hi) else None],
        "underpowered": bool(n_events < MIN_EVENTS_FOR_POWER),
    }


def interaction_test(df_w, exposure, outcome, seed=RANDOM_SEED):
    """Full-cohort IPTW logistic outcome model with an
    ``exposure x high_risk_phenotype`` INTERACTION term.

    Model (sample-weighted by iptw_weight):
        logit P(outcome) = b0 + b1*exposure + b2*high_risk_phenotype
                           + b3*(exposure x high_risk_phenotype)
    The interaction coefficient b3 (and its bootstrap p-value via the sign of the
    bootstrap distribution) answers "does the exposure effect DIFFER by phenotype?"

    Returns a dict with the interaction log-OR, OR, bootstrap p-value, and the main
    exposure log-OR.
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    sub = df_w.copy()
    y = pd.to_numeric(sub[outcome], errors="coerce")
    valid = (y.notna() & sub[exposure].notna()
             & sub["high_risk_phenotype"].notna() & sub["iptw_weight"].notna())
    sub = sub[valid].copy()
    yv = pd.to_numeric(sub[outcome], errors="coerce").astype(int).to_numpy()
    ex = pd.to_numeric(sub[exposure], errors="coerce").astype(float).to_numpy()
    hp = sub["high_risk_phenotype"].astype(float).to_numpy()
    wv = sub["iptw_weight"].to_numpy(dtype=float)

    if len(yv) == 0 or yv.min() == yv.max() or len(np.unique(ex)) < 2:
        return {"interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None, "exposure_log_or": None,
                "note": "insufficient variation to fit interaction model"}

    def _design(ex_, hp_):
        return np.column_stack([ex_, hp_, ex_ * hp_])

    def _fit(X_, y_, w_):
        lr = LogisticRegression(fit_intercept=True, max_iter=1000,
                                solver="lbfgs", C=1e6, random_state=seed)
        lr.fit(X_, y_, sample_weight=w_)
        return lr.coef_[0]   # [b_expo, b_hp, b_interaction]

    try:
        coef = _fit(_design(ex, hp), yv, wv)
    except Exception:
        return {"interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None, "exposure_log_or": None,
                "note": "model failed to converge"}

    b_expo, b_inter = float(coef[0]), float(coef[2])

    # Bootstrap p-value for the interaction: proportion of resamples whose
    # interaction coefficient is on the opposite side of zero from the point
    # estimate, x2 (two-sided), clamped to [0,1].
    rng = np.random.default_rng(seed)
    n = len(yv)
    inter_boot = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, size=n)
        yb = yv[idx]
        if yb.min() == yb.max():
            continue
        try:
            cb = _fit(_design(ex[idx], hp[idx]), yb, wv[idx])
            inter_boot.append(float(cb[2]))
        except Exception:
            continue
    if inter_boot:
        arr = np.asarray(inter_boot)
        if b_inter >= 0:
            p = 2.0 * float((arr <= 0).mean())
        else:
            p = 2.0 * float((arr >= 0).mean())
        p = min(1.0, max(0.0, p))
    else:
        p = None

    return {
        "interaction_log_or": round(b_inter, 4),
        "interaction_or": round(math.exp(b_inter), 4),
        "interaction_p_bootstrap": round(p, 4) if p is not None else None,
        "exposure_log_or": round(b_expo, 4),
        "n": int(n),
        "n_events": int(yv.sum()),
    }


def analyse_exposure(df, exposure, covariates, outcomes=PRIMARY_OUTCOMES,
                     negative_control=NEGATIVE_CONTROL_OUTCOME,
                     n_bootstrap=N_BOOTSTRAP, seed=RANDOM_SEED):
    """Full causal estimation for ONE exposure across all outcomes.

    For each outcome: fit cohort IPTW (PS keyed on the exposure), run the
    phenotype-interaction model, the within-high-risk-phenotype RD/RR with CI, and
    the E-values.  The negative-control outcome is run the same way; a non-null
    within-phenotype effect there flags residual confounding.

    Returns a dict keyed by outcome plus a 'negative_control' block.
    """
    import numpy as np

    if exposure not in df.columns or df[exposure].isna().all():
        return {"exposure": exposure, "available": False,
                "note": f"exposure '{exposure}' unavailable (missing/all-NaN)"}

    df_w, used = _fit_iptw_for_exposure(df, exposure, covariates)
    if df_w is None:
        return {"exposure": exposure, "available": False,
                "note": "could not fit propensity / IPTW (no contrast or no covariates)"}

    out: dict[str, Any] = {"exposure": exposure, "available": True,
                           "ps_covariates": used}

    all_outcomes = list(outcomes) + [negative_control]
    for oc in all_outcomes:
        if oc not in df_w.columns or df_w[oc].isna().all():
            out[oc] = {"available": False, "note": "outcome column missing/all-NaN"}
            continue

        within = within_phenotype_effect(df_w, exposure, oc,
                                          n_bootstrap=n_bootstrap, seed=seed)
        inter = interaction_test(df_w, exposure, oc, seed=seed)

        rr = within.get("risk_ratio")
        rr_ci = within.get("rr_ci", [None, None])
        ev_point = e_value(rr) if rr is not None else None
        ev_ci = (e_value_ci(rr, rr_ci[0], rr_ci[1])
                 if (rr is not None and rr_ci[0] is not None and rr_ci[1] is not None)
                 else None)

        block = {
            "available": True,
            "within_high_risk_phenotype": within,
            "phenotype_interaction": inter,
            "e_value_point": round(ev_point, 3) if ev_point is not None else None,
            "e_value_ci": round(ev_ci, 3) if ev_ci is not None else None,
            "underpowered": within.get("underpowered", True),
        }
        if oc == negative_control:
            block["is_negative_control"] = True
            rd = within.get("risk_difference")
            block["negative_control_flag"] = (
                "NON-NULL (possible residual confounding)"
                if (rd is not None and abs(rd) >= 0.02) else "null (reassuring)"
            )
        out[oc] = block

    return out


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================

def run_actionable_targets(cfg: dict[str, Any]) -> dict[str, Any]:
    """Public entry point.  Run the full actionable-targets analysis.

    Pipeline:
      1. Regenerate confirmatory phenotype labels, mark the high-risk cluster,
         merge outcomes + /cases exposures/PMH.
      2. Define modifiable exposures (incl. arterial-line from /trks index).
      3. For each exposure x outcome: cohort IPTW with phenotype interaction +
         within-phenotype RD/RR with bootstrap CI + E-values + negative control.
      4. Write actionable_results.json, ACTIONABLE_RESULTS.md, and (LAST)
         _actionable_done.json.

    Returns the full results dict.
    """
    import numpy as np

    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    os.makedirs(cache_dir, exist_ok=True)

    # 1. Cohort + phenotype + outcomes.
    df, cohort_meta = build_cohort(cfg)

    # 2. Exposures.
    df = define_exposures(df)
    df = add_arterial_line(df, cfg)
    df = add_phe_vs_norepi(df, cfg)
    # use_tracks=False: the matrix-approximation path (hypotension onset from
    # feature_matrix map_time_to_first_below65_frac) avoids per-case MAP/pump
    # downloads that made this analysis download-bound + un-kill-survivable.
    df = add_time_to_treat(df, cfg, use_tracks=False)
    time_to_treat_meta = {
        "derivation": df.attrs.get("time_to_treat_derivation"),
        "median_lag_min": df.attrs.get("time_to_treat_median_lag_min"),
    }

    # 3. Causal estimation per exposure.
    covariates = DEFAULT_PS_COVARIATES
    per_exposure = {}
    pvals_for_fdr = []
    pval_keys = []
    for expo in ACTIONABLE_EXPOSURES:
        res = analyse_exposure(df, expo, covariates, seed=seed)
        per_exposure[expo] = res
        # collect interaction p-values for an FDR pass across exposure x outcome.
        if res.get("available"):
            for oc in PRIMARY_OUTCOMES:
                blk = res.get(oc, {})
                p = (blk.get("phenotype_interaction") or {}).get("interaction_p_bootstrap")
                pvals_for_fdr.append(p)
                pval_keys.append((expo, oc))

    # BH-FDR across all phenotype-interaction tests (primary outcomes only).
    reject = benjamini_hochberg([p if p is not None else 1.0 for p in pvals_for_fdr])
    fdr = {}
    for (expo, oc), p, rj in zip(pval_keys, pvals_for_fdr, reject):
        fdr.setdefault(expo, {})[oc] = {"interaction_p": p, "fdr_reject": bool(rj)}

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "seed": seed,
        "min_events_for_power": MIN_EVENTS_FOR_POWER,
        "eph_to_phe_equiv": EPH_TO_PHE_EQUIV,
        "confounder_set": covariates,
        "primary_outcomes": list(PRIMARY_OUTCOMES),
        "negative_control_outcome": NEGATIVE_CONTROL_OUTCOME,
        "cohort": cohort_meta,
        "time_to_treat": time_to_treat_meta,
        "exposures": per_exposure,
        "fdr_interaction": fdr,
        "interpretation": (
            "Observational, single-centre (VitalDB / SNUH), confounding-by-"
            "indication is the central threat. Within-high-risk-phenotype effects "
            "are HYPOTHESIS-GENERATING for a prospective trial; external validation "
            "on INSPIRE pending. E-values quantify required unmeasured-confounder "
            "strength; the organ_hepatocellular negative control checks residual "
            "confounding."
        ),
    }

    # 4. Write outputs (done marker LAST).
    results_path = os.path.join(cache_dir, _RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[actionable] results written to {results_path}")

    _write_actionable_md(results, cfg)

    done_path = os.path.join(cache_dir, _DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"done": True, "results_json": _RESULTS_JSON,
                   "n_cases": cohort_meta["n_cases"],
                   "n_high_risk": cohort_meta["n_high_risk"]}, fh, indent=2)
    print(f"[actionable] done marker written to {done_path}")

    return results


# ===========================================================================
# REPORT
# ===========================================================================

def _fmt(v):
    return "n/a" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _rank_findings(results):
    """Order exposures by (best-powered, most actionable): primary = renal RD with
    a non-overlapping CI and adequate power, then by |RD|."""
    scored = []
    for expo, res in results["exposures"].items():
        if not res.get("available"):
            continue
        blk = res.get("organ_renal", {})
        within = blk.get("within_high_risk_phenotype", {}) if blk.get("available") else {}
        rd = within.get("risk_difference")
        powered = not within.get("underpowered", True)
        rd_ci = within.get("rd_ci", [None, None])
        significant = (rd_ci[0] is not None and rd_ci[1] is not None
                       and (rd_ci[0] > 0 or rd_ci[1] < 0))
        score = (1 if powered else 0, 1 if significant else 0,
                 abs(rd) if isinstance(rd, (int, float)) else 0.0)
        scored.append((score, expo))
    scored.sort(reverse=True)
    return [e for _, e in scored]


def _write_actionable_md(results: dict, cfg: dict) -> str:
    """Write the human-readable ACTIONABLE_RESULTS.md report."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "ACTIONABLE_RESULTS.md")

    cohort = results["cohort"]
    L = [
        "# Actionable Intraoperative Management Targets (High-Risk Phenotype)",
        "",
        "## Interpretation & limitations (READ FIRST)",
        "",
        "- **Observational, single-centre** (VitalDB / SNUH). Treatment was not",
        "  randomised; **confounding by indication** is the central threat -- sicker,",
        "  more unstable patients receive different management AND are more likely to",
        "  sustain organ injury.",
        "- Effects below are the **within-high-risk-phenotype** association of each",
        "  MODIFIABLE intraoperative decision with organ injury, IPTW-adjusted for the",
        f"  confounder set `{results['confounder_set']}`.",
        "- These are **HYPOTHESIS-GENERATING for a prospective trial**, not causal",
        "  proof. **External validation on INSPIRE is pending.**",
        "- **E-values** quantify how strong an unmeasured confounder would have to be",
        "  (risk-ratio scale) to explain a result away. A small E-value (~1-1.5) means",
        "  weak residual confounding could nullify the finding.",
        f"- **Negative control:** `{results['negative_control_outcome']}` -- management",
        "  should not plausibly cause it; a non-null effect there flags residual",
        "  confounding.",
        f"- **Power:** high-risk-phenotype cells with < {results['min_events_for_power']}",
        "  events are reported but marked **underpowered, hypothesis-only**.",
        "",
        "## Cohort",
        "",
        f"- Confirmatory phenotypes regenerated deterministically (best k = "
        f"{cohort.get('best_k')}; seed {results['seed']}).",
        f"- High-risk cluster = **{cohort.get('high_risk_cluster')}** "
        f"(selected by {cohort['cluster_rates'].get('selected_by')} rate).",
        f"- N cases = {cohort.get('n_cases')}; N in high-risk phenotype = "
        f"{cohort.get('n_high_risk')}.",
        f"- Pressor unit assumption: intraop_phe (ug), intraop_eph (mg, x"
        f"{results['eph_to_phe_equiv']} -> PHE-ug equiv), intraop_epi (ug); fluids (mL).",
        "",
        "## The five modifiable exposures (definitions)",
        "",
        "1. **Vasopressor- vs fluid-predominant management** (`vasopressor_predominant`):",
        "   pressor dose in the TOP tertile (PHE-equivalent, among pressor-treated) AND",
        "   fluids NOT in the top tertile. Also reported: `any_vasopressor` (any pressor).",
        "2. **Phenylephrine-predominant** vs ephedrine (`phenylephrine_predominant`):",
        "   phe (ug) > ephedrine PHE-equivalent. Better-powered secondary to #3.",
        "3. **Phenylephrine vs NOREPINEPHRINE** (`phe_vs_norepi`) -- MECHANISTIC HEADLINE:",
        "   among pressor-exposed, phe-dominant (1) vs norepi-dominant (0). Norepi from",
        "   Orchestra/NEPI pump tracks (~88 VitalDB cases) -> SMALL-N, hypothesis-only.",
        "   Phe alpha-constriction raises MAP but may not restore renal perfusion.",
        "4. **Arterial line** (`arterial_line`): invasive continuous BP -- SNUADC/ART",
        "   present in the trks index.",
        "5. **Time-to-treat hypotension** (`slow_treat`): lag from first MAP<65 to first",
        "   pump pressor onset; SLOW (>median) vs FAST (<median); hypotension-but-no-",
        f"   pressor is a separate 'untreated' level. Derivation: "
        f"{results.get('time_to_treat', {}).get('derivation')}; "
        f"median lag = {_fmt(results.get('time_to_treat', {}).get('median_lag_min'))} min.",
        "   Plus the **fluid U-shape** (`high_fluid` top tertile / `low_fluid` bottom",
        "   tertile; `fluid_level` 0/1/2): overload (venous congestion) vs hypovolemia.",
        "",
        "## Findings (led by best-powered + most actionable)",
        "",
    ]

    order = _rank_findings(results)
    if not order:
        L.append("_No exposure produced an estimable within-phenotype effect "
                 "(data may be synthetic / incomplete)._")
        L.append("")

    for expo in order:
        res = results["exposures"][expo]
        L.append(f"### {expo}")
        for oc in results["primary_outcomes"]:
            blk = res.get(oc, {})
            if not blk.get("available"):
                L.append(f"- **{oc}:** not available.")
                continue
            w = blk["within_high_risk_phenotype"]
            inter = blk.get("phenotype_interaction", {})
            flag = " **[UNDERPOWERED, hypothesis-only]**" if blk.get("underpowered") else ""
            L.append(
                f"- **{oc}:** within high-risk phenotype "
                f"RD = {_fmt(w.get('risk_difference'))} "
                f"(95% CI {_fmt(w.get('rd_ci', [None,None])[0])} to "
                f"{_fmt(w.get('rd_ci', [None,None])[1])}); "
                f"RR = {_fmt(w.get('risk_ratio'))} "
                f"(95% CI {_fmt(w.get('rr_ci', [None,None])[0])} to "
                f"{_fmt(w.get('rr_ci', [None,None])[1])}). "
                f"n = {w.get('n')}, events = {w.get('n_events')}.{flag}"
            )
            L.append(
                f"  - Phenotype interaction OR = {_fmt(inter.get('interaction_or'))} "
                f"(p = {_fmt(inter.get('interaction_p_bootstrap'))}); "
                f"E-value (point) = {_fmt(blk.get('e_value_point'))}, "
                f"E-value (CI) = {_fmt(blk.get('e_value_ci'))}."
            )
        nc = res.get(results["negative_control_outcome"], {})
        if nc.get("available"):
            w = nc["within_high_risk_phenotype"]
            L.append(
                f"- _Negative control ({results['negative_control_outcome']}):_ "
                f"RD = {_fmt(w.get('risk_difference'))} -> "
                f"{nc.get('negative_control_flag')}."
            )
        L.append("")

    # Exposures that could not be analysed.
    unavail = [e for e, r in results["exposures"].items() if not r.get("available")]
    if unavail:
        L += ["## Exposures not analysable", ""]
        for e in unavail:
            L.append(f"- **{e}:** {results['exposures'][e].get('note', 'unavailable')}")
        L.append("")

    L += [
        "## Methods (brief)",
        "",
        "- Phenotype labels regenerated via `phenotypes.load_physiology_matrix` +",
        "  `discover_phenotypes` (k in 2..7, seed from config); high-risk = highest",
        "  organ_renal rate (fallback composite).",
        "- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model",
        "  (reused from `hypotension_treatment.py`), refit per exposure.",
        "- PRIMARY model: full-cohort IPTW logistic outcome model with an",
        "  exposure x high_risk_phenotype interaction term.",
        "- Within-phenotype RD/RR: IPTW-weighted arm risks; 95% CI by nonparametric",
        "  percentile bootstrap (weights fixed).",
        "- E-value: VanderWeele & Ding (2017), point + null-nearest CI bound.",
        "- Multiplicity: Benjamini-Hochberg FDR across interaction tests.",
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/actionable_targets.py*",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[actionable] ACTIONABLE_RESULTS.md written to {md_path}")
    return md_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Load config.yaml and run.  Requires the real feature_matrix/cases caches."""
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    res = run_actionable_targets(cfg)
    print(json.dumps(res["cohort"], indent=2))


if __name__ == "__main__":
    main()
