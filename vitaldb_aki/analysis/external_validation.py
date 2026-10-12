"""external_validation.py -- INSPIRE replication harness for the VitalDB-AKI study.

Why this module exists
----------------------
Every headline finding in this repo is OBSERVATIONAL and SINGLE-CENTRE (VitalDB /
SNUH):

  * organ-injury / fragility PHENOTYPES (phenotypes.py / phenotype_v2.py),
  * hypotension-burden -> AKI/composite ASSOCIATION (hypotension_treatment.py),
  * personalized-MAP-target HTE (map_hte.py / map_target_analysis.py),
  * reperfusion-velocity incremental biomarker (reperfusion_dynamics.py),
  * pressor-choice (phe vs norepi) effect (actionable_targets.py).

Single-centre observational results are HYPOTHESIS-GENERATING.  To be publishable
as more than that, the ones that CAN be replicated must be re-run, unchanged, on an
INDEPENDENT multi-centre cohort.  INSPIRE (the multi-centre perioperative dataset)
carries MAP, serum creatinine, pressors and baseline covariates, so it can host
the hemodynamic / outcome findings -- but NOT the arterial-waveform-morphology
findings (INSPIRE has no waveforms; that arm is unvalidatable here, stated
explicitly below).

What this module is (and is NOT)
--------------------------------
This is a GATED, RUNNABLE-WHEN-DATA-ARRIVES harness, exactly analogous to the
Phase-2 prereq guards in ``analysis/phase2_prereq_guard.py`` and the gated specs in
``docs/``.  It is *ready* to run the moment an INSPIRE feature matrix is dropped at
``cache/inspire_matrix.csv``.  Until then it HARD-FAILS with a clear BLOCKED status.

It NEVER fabricates an INSPIRE result.  The ONLY synthetic data it touches is the
self-contained smoke-test frame in :func:`make_synthetic_inspire_frame`, which is
clearly labelled synthetic, used only to prove the harness wiring runs end-to-end,
and is NEVER written to ``cache/inspire_matrix.csv`` nor reported as a result.

Anti-HARKing
------------
The concordance bar is PRE-SPECIFIED here in code + in docs/EXTERNAL_VALIDATION.md
BEFORE any INSPIRE data is seen: a target replicates iff the INSPIRE estimate has
(1) the SAME SIGN/direction as the internal VitalDB estimate, (2) a CONFIDENCE
INTERVAL that OVERLAPS the internal CI, and (3) a MAGNITUDE within a pre-set factor
of the internal point estimate.  See :data:`CONCORDANCE`.

Heavy dependencies (numpy / pandas / sklearn / scipy / statsmodels) are lazy-
imported INSIDE functions, so this module imports with the stdlib only -- matching
the repo convention in actionable_targets.py / hypotension_treatment.py /
phase2_prereq_guard.py.  The smoke test stays light.

Entry points
------------
    run_external_validation(cfg, matrix_path=None) -> dict     # the gated harness
    make_synthetic_inspire_frame(n, seed) -> DataFrame          # smoke-test data ONLY
    python3 -m vitaldb_aki.analysis.external_validation         # prints BLOCKED status
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Callable

# ===========================================================================
# Constants -- config-as-code; the gate path, the seed, the concordance bar.
# ===========================================================================

# The INSPIRE matrix the harness needs.  ABSENT today -> the harness is BLOCKED.
INSPIRE_MATRIX_FILE = "inspire_matrix.csv"
STATUS_FILE = "external_validation_status.json"

RANDOM_SEED = 20260626          # matches config.yaml seed default

# --------------------------------------------------------------------------
# PRE-SPECIFIED concordance bar (anti-HARKing -- fixed BEFORE seeing INSPIRE).
# --------------------------------------------------------------------------
# A replication target is judged CONCORDANT iff ALL THREE hold:
#   (1) same_direction: INSPIRE point estimate has the same sign relative to the
#       null as the internal VitalDB estimate (RD null = 0; RR/OR null = 1;
#       delta-AUROC null = 0).
#   (2) ci_overlap: the INSPIRE 95% CI overlaps the internal VitalDB 95% CI.
#   (3) magnitude: the INSPIRE effect magnitude is within MAGNITUDE_FACTOR of the
#       internal magnitude (on the natural scale of the estimand: RD on the
#       additive scale, RR/OR on the log/ratio scale, delta-AUROC additive).
CONCORDANCE = {
    "magnitude_factor": 2.0,        # INSPIRE effect within 2x (or 1/2x) of internal
    "rd_abs_floor": 0.01,           # below this abs RD, treat magnitudes as "both ~0"
    "auroc_abs_floor": 0.01,        # below this abs delta-AUROC, "both ~0"
    "require_all_three": True,      # direction AND ci-overlap AND magnitude
}


# ===========================================================================
# INSPIRE -> internal VARIABLE MAPPING (also documented in
# docs/EXTERNAL_VALIDATION.md).  Keys are the INTERNAL feature names the
# estimators expect; values describe how to derive them from INSPIRE.
#
# INSPIRE schema reference: the public INSPIRE release ships `operations`,
# `labs`, `vitals`, `medications`, `diagnosis` tables.  The derivations below
# name the INSPIRE source column(s) / table the harness reads when a real matrix
# is built (the matrix-builder is a separate stage; this mapping is the contract).
# ===========================================================================

INSPIRE_VARIABLE_MAP: dict[str, dict[str, str]] = {
    # --- intraoperative hypotension burden (the key EXPOSURE family) ---------
    "map_auc_below_65": {
        "inspire_source": "vitals: non-invasive/arterial MBP series",
        "derivation": "area under MAP<65 mmHg over the intraop window "
                      "(opstart..opend), mmHg*min; identical estimand to "
                      "features/pfds.py map_auc_below_65 on VitalDB.",
        "internal_estimator_role": "exposure (burden) for hypotension_treatment "
                                   "and the HTE dose-response",
    },
    "map_min_below_65": {
        "inspire_source": "vitals: MBP series",
        "derivation": "minutes with MAP<65 mmHg in the intraop window.",
        "internal_estimator_role": "secondary burden / confounder",
    },
    "map_mean": {
        "inspire_source": "vitals: MBP series",
        "derivation": "time-weighted mean intraop MAP (artifact-gated 20-200).",
        "internal_estimator_role": "covariate / descriptive",
    },
    "map_lowest": {
        "inspire_source": "vitals: MBP series",
        "derivation": "minimum artifact-gated MAP (nadir) over the intraop window.",
        "internal_estimator_role": "static-burden baseline for incremental AUROC",
    },
    # --- KDIGO AKI label (the OUTCOME) ---------------------------------------
    "organ_renal": {
        "inspire_source": "labs: serum creatinine (preop baseline + postop peak)",
        "derivation": "KDIGO AKI from pre/post serum creatinine via "
                      "inspire/labeling.py (SAME thresholds as cohort/labeling.py): "
                      ">=0.3 mg/dL rise in 48h OR >=1.5x baseline in 7d.",
        "internal_estimator_role": "primary outcome y",
    },
    "composite": {
        "inspire_source": "labs + diagnosis (renal +/- available organ axes)",
        "derivation": "composite organ-injury flag; on INSPIRE this reduces to the "
                      "renal (KDIGO) + mortality axes that INSPIRE supports -- the "
                      "VitalDB composite's lab-only organ axes are mapped where the "
                      "corresponding INSPIRE labs exist, else dropped (documented).",
        "internal_estimator_role": "secondary outcome y",
    },
    # --- pressor exposure / choice (EXPOSURE) --------------------------------
    "any_vasopressor": {
        "inspire_source": "medications: intraop vasopressor administrations",
        "derivation": "1 if any intraop phenylephrine/ephedrine/norepinephrine "
                      "given, else 0.",
        "internal_estimator_role": "exposure (pressor use)",
    },
    "phe_vs_norepi": {
        "inspire_source": "medications: phenylephrine vs norepinephrine records",
        "derivation": "among pressor-exposed: 1 = phenylephrine-dominant, "
                      "0 = norepinephrine-dominant (INSPIRE records both drugs "
                      "explicitly -> better-powered than VitalDB, where norepi is "
                      "pump-track-only ~88 cases).",
        "internal_estimator_role": "exposure (pressor CHOICE -- mechanistic headline)",
    },
    "intraop_phe": {
        "inspire_source": "medications: phenylephrine dose",
        "derivation": "total intraop phenylephrine (ug).",
        "internal_estimator_role": "exposure component",
    },
    "intraop_norepi": {
        "inspire_source": "medications: norepinephrine dose",
        "derivation": "total intraop norepinephrine (ug); NO VitalDB /cases column "
                      "-- VitalDB detects norepi from Orchestra pump tracks only.",
        "internal_estimator_role": "exposure component",
    },
    "intraop_eph": {
        "inspire_source": "medications: ephedrine dose",
        "derivation": "total intraop ephedrine (mg).",
        "internal_estimator_role": "exposure component (define_treatment input)",
    },
    # --- baseline covariates (CONFOUNDERS / subgroup axes) -------------------
    "age": {"inspire_source": "operations.age", "derivation": "years.",
            "internal_estimator_role": "confounder / age-subgroup axis"},
    "sex_male": {"inspire_source": "operations.sex", "derivation": "1=male, 0=female.",
                 "internal_estimator_role": "confounder"},
    "asa_class": {"inspire_source": "operations.asa", "derivation": "ASA physical status (1-5).",
                  "internal_estimator_role": "confounder"},
    "preop_htn": {"inspire_source": "diagnosis / preop flags",
                  "derivation": "1 if preoperative hypertension, else 0.",
                  "internal_estimator_role": "confounder / HTN-subgroup axis (HTE)"},
    "preop_dm": {"inspire_source": "diagnosis / preop flags",
                 "derivation": "1 if preoperative diabetes, else 0.",
                 "internal_estimator_role": "confounder"},
    "baseline_cr": {"inspire_source": "labs: most-recent preop creatinine",
                    "derivation": "mg/dL; same baseline-selection rule as "
                                  "inspire/labeling.py.",
                    "internal_estimator_role": "confounder / CKD-subgroup axis (HTE)"},
    "egfr_ckd_epi": {"inspire_source": "derived from baseline_cr + age + sex",
                     "derivation": "CKD-EPI eGFR; CKD subgroup = eGFR<60.",
                     "internal_estimator_role": "CKD-subgroup axis (HTE)"},
    "surgery_duration": {"inspire_source": "operations: opstart/opend",
                         "derivation": "(opend - opstart)/60 minutes.",
                         "internal_estimator_role": "confounder"},
    "optype_code": {"inspire_source": "operations: surgery type / department",
                    "derivation": "factorised integer code of surgery category.",
                    "internal_estimator_role": "confounder"},
    "ebl": {"inspire_source": "operations: estimated blood loss (if present)",
            "derivation": "mL; INSPIRE EBL coverage is PARTIAL -> imputed/dropped "
                          "where absent (documented limitation).",
            "internal_estimator_role": "confounder"},
    # --- reperfusion-velocity recovery feature (EXPOSURE for incremental AUROC) ---
    "recovery_velocity": {
        "inspire_source": "vitals: MBP series (post-nadir recovery slope)",
        "derivation": "late-vs-early MAP recovery scaled by nadir depth, from the "
                      "intraop MBP series -- SAME estimand as "
                      "reperfusion_dynamics.py recovery_velocity, BUT computed on "
                      "INSPIRE's COARSER (typically 1-min) MBP sampling, not a "
                      "high-resolution arterial waveform. Validatable in a "
                      "degraded-resolution sense ONLY; flagged.",
        "internal_estimator_role": "incremental feature over static burden",
    },
}

# Internal features with NO INSPIRE equivalent -- their findings CANNOT be
# externally validated on INSPIRE and must NOT be claimed as replicated here.
NO_INSPIRE_EQUIVALENT: dict[str, str] = {
    "arterial_waveform_morphology": (
        "INSPIRE ships NO continuous arterial waveform -- only intermittent "
        "(typically 1-min) numeric vitals. Every finding that depends on beat-to-"
        "beat waveform MORPHOLOGY (the a-line organ-injury arm, dP/dt, pulse-"
        "pressure-variation morphology, waveform-shape phenotypes) is UNVALIDATABLE "
        "on INSPIRE."
    ),
    "arterial_line_monitoring_exposure": (
        "The 'arterial_line' management exposure (invasive continuous BP present in "
        "the VitalDB /trks index) has no analogue in INSPIRE's table schema."
    ),
    "high_resolution_recovery_dynamics": (
        "Beat-resolved reperfusion DYNAMICS require waveform-rate sampling; INSPIRE's "
        "coarse MBP can only support a degraded recovery_velocity proxy (see "
        "INSPIRE_VARIABLE_MAP['recovery_velocity']), not the full biomarker."
    ),
}


# ===========================================================================
# REPLICATION-TARGET REGISTRY
# Each target names: the internal finding, which internal result JSON holds the
# VitalDB estimate, the estimand type, the estimator (a callable run on INSPIRE),
# and the INSPIRE columns required.  Mirrors the registry style of the other
# modules (ACTIONABLE_EXPOSURES, GATES, etc.).
# ===========================================================================

# Estimand kinds determine the null + how concordance is judged.
KIND_RD = "risk_difference"     # additive; null = 0
KIND_RR = "risk_ratio"          # ratio; null = 1
KIND_OR = "odds_ratio"          # ratio; null = 1
KIND_DELTA_AUROC = "delta_auroc"  # additive; null = 0


def _internal_from_hypotension(results: dict) -> dict:
    """Extract the internal VitalDB hypotension-treatment OR estimate."""
    o = (results or {}).get("iptw_or", {}) or {}
    return {
        "kind": KIND_OR,
        "point": o.get("OR"),
        "ci": [o.get("CI_lower"), o.get("CI_upper")],
        "n": o.get("n"),
        "n_events": o.get("n_events"),
        "source": "cache/hypotension_treatment_results.json :: iptw_or",
    }


def _internal_from_map_hte(results: dict, outcome: str = "organ_renal",
                           target: str = "target_65") -> dict:
    """Extract the internal VitalDB within-subgroup burden dose-response RR at a
    MAP target (the HTE estimand). Reads map_target_results.json C_modifiable_iptw."""
    block = (((results or {}).get("C_modifiable_iptw", {}) or {})
             .get(outcome, {}) or {}).get(target, {}) or {}
    return {
        "kind": KIND_RR,
        "point": block.get("iptw_risk_ratio"),
        "ci": block.get("rr_CI", [None, None]),
        "rd_point": block.get("iptw_risk_difference"),
        "rd_ci": block.get("rd_CI", [None, None]),
        "n": block.get("n"),
        "n_events": block.get("n_events"),
        "source": f"cache/map_target_results.json :: C_modifiable_iptw.{outcome}.{target}",
    }


def _internal_from_reperfusion(results: dict, outcome: str = "organ_renal") -> dict:
    """Extract the internal VitalDB incremental delta-AUROC of recovery features."""
    block = ((results or {}).get("incremental_auroc", {}) or {}).get(outcome, {}) or {}
    return {
        "kind": KIND_DELTA_AUROC,
        "point": block.get("delta_auroc"),
        "ci": block.get("delta_auroc_ci95", [None, None]),
        "auroc_static": block.get("auroc_static_burden"),
        "n": block.get("n"),
        "n_events": block.get("events"),
        "source": f"cache/reperfusion_dynamics_results.json :: incremental_auroc.{outcome}",
    }


def _internal_from_pressor_choice(results: dict, outcome: str = "organ_renal") -> dict:
    """Extract the internal VitalDB phe_vs_norepi within-phenotype RR.

    actionable_results.json structure is keyed by exposure; we look up the
    within-high-risk-phenotype RR for the requested outcome.
    """
    expo = (((results or {}).get("exposures", {}) or {})
            .get("phe_vs_norepi", {}) or {})
    out_block = expo.get(outcome, {}) if isinstance(expo, dict) else {}
    wp = (out_block.get("within_high_risk_phenotype", {})
          if isinstance(out_block, dict) else {}) or {}
    return {
        "kind": KIND_RR,
        "point": wp.get("risk_ratio"),
        "ci": wp.get("rr_ci", [None, None]),
        "rd_point": wp.get("risk_difference"),
        "rd_ci": wp.get("rd_ci", [None, None]),
        "n": wp.get("n"),
        "n_events": wp.get("n_events"),
        "source": f"cache/actionable_results.json :: phe_vs_norepi.{outcome}",
    }


# The four replication targets. ``estimator`` is resolved lazily (string name)
# to keep import stdlib-only; ``required_cols`` are INTERNAL feature names (mapped
# from INSPIRE via INSPIRE_VARIABLE_MAP).
REPLICATION_TARGETS: dict[str, dict[str, Any]] = {
    "hypotension_burden_aki": {
        "label": "Hypotension-burden -> AKI/composite (IPTW OR/RD/RR + AUROC)",
        "kind": KIND_OR,
        "internal_result_file": "hypotension_treatment_results.json",
        "internal_extractor": _internal_from_hypotension,
        "estimator": "_estimate_hypotension_burden",
        "outcome": "composite",
        "required_cols": ["map_auc_below_65", "composite", "any_vasopressor",
                          "age", "asa_class", "baseline_cr"],
    },
    "personalized_map_target_hte": {
        "label": "Personalized-MAP-target HTE (burden x subgroup interaction)",
        "kind": KIND_RR,
        "internal_result_file": "map_target_results.json",
        "internal_extractor": _internal_from_map_hte,
        "estimator": "_estimate_map_hte",
        "outcome": "organ_renal",
        "subgroup_axis": "preop_htn",
        "required_cols": ["map_auc_below_65", "organ_renal", "preop_htn",
                          "age", "asa_class", "baseline_cr"],
    },
    "reperfusion_velocity_increment": {
        "label": "Reperfusion-velocity incremental AUROC over static burden",
        "kind": KIND_DELTA_AUROC,
        "internal_result_file": "reperfusion_dynamics_results.json",
        "internal_extractor": _internal_from_reperfusion,
        "estimator": "_estimate_reperfusion_increment",
        "outcome": "organ_renal",
        "degraded": True,   # coarse MBP only -- validatable in degraded sense
        "required_cols": ["map_lowest", "map_auc_below_65", "recovery_velocity",
                          "organ_renal"],
    },
    "pressor_choice_phe_vs_norepi": {
        "label": "Pressor choice: phenylephrine vs norepinephrine effect (IPTW RR)",
        "kind": KIND_RR,
        "internal_result_file": "actionable_results.json",
        "internal_extractor": _internal_from_pressor_choice,
        "estimator": "_estimate_pressor_choice",
        "outcome": "organ_renal",
        "required_cols": ["phe_vs_norepi", "organ_renal",
                          "age", "asa_class", "baseline_cr"],
    },
}


# ===========================================================================
# CONCORDANCE LOGIC (pure; stdlib only -- unit-testable without numpy)
# ===========================================================================

def _null_of(kind: str) -> float:
    return 1.0 if kind in (KIND_RR, KIND_OR) else 0.0


def _sign_vs_null(value: float, kind: str) -> int:
    """-1 / 0 / +1 for value below / at / above the null."""
    if value is None or not (isinstance(value, (int, float)) and math.isfinite(value)):
        return 0
    null = _null_of(kind)
    if value > null:
        return 1
    if value < null:
        return -1
    return 0


def _ci_overlap(ci_a, ci_b) -> bool | None:
    """Do two CIs [lo, hi] overlap? None if either is unusable."""
    try:
        alo, ahi = float(ci_a[0]), float(ci_a[1])
        blo, bhi = float(ci_b[0]), float(ci_b[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not all(math.isfinite(v) for v in (alo, ahi, blo, bhi)):
        return None
    if alo > ahi:
        alo, ahi = ahi, alo
    if blo > bhi:
        blo, bhi = bhi, blo
    return not (ahi < blo or bhi < alo)


def _magnitude_concordant(internal_point, inspire_point, kind: str,
                          cfg: dict | None = None) -> bool | None:
    """Magnitude within MAGNITUDE_FACTOR on the estimand's natural scale.

    Ratio estimands (RR/OR): the ratio of the two effects' distances from 1
    (i.e. internal/inspire after mapping both to >=1 side) must be <= factor.
    Additive estimands (RD/delta-AUROC): both 'effectively zero' (below floor)
    -> concordant; else the abs ratio must be within factor.
    """
    cfg = cfg or CONCORDANCE
    factor = float(cfg.get("magnitude_factor", 2.0))
    for v in (internal_point, inspire_point):
        if v is None or not (isinstance(v, (int, float)) and math.isfinite(v)):
            return None
    if kind in (KIND_RR, KIND_OR):
        # Distance from the multiplicative null on the log scale.
        ia, ib = abs(math.log(internal_point)) if internal_point > 0 else None, \
                 abs(math.log(inspire_point)) if inspire_point > 0 else None
        if ia is None or ib is None:
            return None
        if ia < 1e-6 and ib < 1e-6:
            return True
        hi = max(ia, ib)
        lo = min(ia, ib)
        if lo < 1e-6:
            return False
        return (hi / lo) <= factor
    # additive
    floor = float(cfg.get("rd_abs_floor" if kind == KIND_RD else "auroc_abs_floor",
                          0.01))
    if kind == KIND_DELTA_AUROC:
        floor = float(cfg.get("auroc_abs_floor", 0.01))
    ai, bi = abs(internal_point), abs(inspire_point)
    if ai < floor and bi < floor:
        return True
    hi = max(ai, bi)
    lo = min(ai, bi)
    if lo < 1e-9:
        return False
    return (hi / lo) <= factor


def judge_concordance(internal: dict, inspire: dict, kind: str,
                      cfg: dict | None = None) -> dict:
    """Apply the PRE-SPECIFIED concordance bar. Pure; returns a verdict dict."""
    cfg = cfg or CONCORDANCE
    ip, sp = internal.get("point"), inspire.get("point")
    same_direction = (_sign_vs_null(ip, kind) != 0
                      and _sign_vs_null(ip, kind) == _sign_vs_null(sp, kind))
    ci_ovl = _ci_overlap(internal.get("ci"), inspire.get("ci"))
    mag = _magnitude_concordant(ip, sp, kind, cfg)

    components = {
        "same_direction": bool(same_direction),
        "ci_overlap": ci_ovl,
        "magnitude_within_factor": mag,
    }
    # Concordant iff all three pass (None = could-not-evaluate -> not concordant).
    if cfg.get("require_all_three", True):
        concordant = bool(same_direction) and (ci_ovl is True) and (mag is True)
    else:
        concordant = bool(same_direction)

    return {
        "internal_point": ip,
        "internal_ci": internal.get("ci"),
        "inspire_point": sp,
        "inspire_ci": inspire.get("ci"),
        "kind": kind,
        "null": _null_of(kind),
        "components": components,
        "concordant": concordant,
        "verdict": ("CONCORDANT (replicates)" if concordant
                    else "DISCORDANT / inconclusive"),
        "criteria": dict(cfg),
    }


# ===========================================================================
# IO HELPERS
# ===========================================================================

def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    # Default to THIS package's cache dir (absolute), like phase2_prereq_guard.
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "cache")


def _resolve_seed(cfg: dict[str, Any]) -> int:
    return int(cfg.get("seed", RANDOM_SEED))


def _empty_required_cols(df, required_cols) -> list[str]:
    """Return the subset of *required_cols* that are present but ENTIRELY empty
    (all-NaN) in *df*. Used to detect the PENDING-upstream-data state (e.g. MAP
    columns before vitals is built) so the harness reports PENDING, not a crash."""
    import pandas as pd  # lazy
    out = []
    for c in required_cols:
        if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().sum() == 0:
            out.append(c)
    return out


def _load_internal_result(cache_dir: str, fname: str) -> dict:
    path = os.path.join(cache_dir, fname)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _json_default(obj):
    import numpy as np  # lazy
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ===========================================================================
# THE GATE -- refuse to run without a real INSPIRE matrix (mirrors
# phase2_prereq_guard.assert_phase2_prerequisite).
# ===========================================================================

class InspireMatrixAbsentError(RuntimeError):
    """Raised when the INSPIRE feature matrix is absent -- external validation
    is correctly BLOCKED (never silently fabricated)."""


def external_validation_status(cfg: dict[str, Any],
                               matrix_path: str | None = None) -> dict[str, Any]:
    """Return {blocked, matrix_path, reasons, ...} WITHOUT running anything heavy.

    BLOCKED unless an INSPIRE matrix exists. This is the gate analogue of
    phase2_prereq_status: callable with the stdlib only.
    """
    cache_dir = _resolve_cache_dir(cfg)
    path = matrix_path or os.path.join(cache_dir, INSPIRE_MATRIX_FILE)
    present = os.path.exists(path)
    if not present:
        return {
            "blocked": True,
            "status": "BLOCKED",
            "matrix_path": path,
            "matrix_present": False,
            "reasons": [
                f"INSPIRE feature matrix {path!r} does not exist on this host. "
                "External validation is correctly BLOCKED -- the harness refuses "
                "to run (and NEVER fabricates an INSPIRE result) until a real "
                "INSPIRE matrix is provided. Drop the matrix at this path (see "
                "docs/EXTERNAL_VALIDATION.md and the INSPIRE_VARIABLE_MAP) to "
                "unlock the run."
            ],
            "replication_targets": list(REPLICATION_TARGETS.keys()),
            "concordance_criteria": dict(CONCORDANCE),
            "unvalidatable_on_inspire": NO_INSPIRE_EQUIVALENT,
        }
    return {
        "blocked": False,
        "status": "READY",
        "matrix_path": path,
        "matrix_present": True,
        "reasons": [],
        "replication_targets": list(REPLICATION_TARGETS.keys()),
        "concordance_criteria": dict(CONCORDANCE),
    }


def assert_inspire_matrix(cfg: dict[str, Any], matrix_path: str | None = None) -> str:
    """Hard gate: raise InspireMatrixAbsentError unless the INSPIRE matrix exists.
    Returns the resolved matrix path on success."""
    st = external_validation_status(cfg, matrix_path=matrix_path)
    if st["blocked"]:
        raise InspireMatrixAbsentError(
            "INSPIRE external validation is BLOCKED.\n"
            + "\n".join(f"  - {r}" for r in st["reasons"])
        )
    return st["matrix_path"]


# ===========================================================================
# PER-TARGET ESTIMATORS (run on INSPIRE; reuse internal estimators).
# Each returns an {kind, point, ci, n, n_events, ...} dict in the SAME shape as
# the internal extractors, so judge_concordance can compare them directly.
# Heavy imports are inside each function.
# ===========================================================================

def _estimate_hypotension_burden(df, target_spec, seed=RANDOM_SEED) -> dict:
    """Re-run the EXACT internal IPTW estimator (hypotension_treatment.run_analysis)
    on the INSPIRE frame and return its OR estimate."""
    from vitaldb_aki.analysis.hypotension_treatment import run_analysis
    outcome = target_spec.get("outcome", "composite")
    sub = df.copy()
    # hypotension_treatment expects the outcome in a 'composite' column.
    if outcome != "composite" and outcome in sub.columns:
        sub["composite"] = sub[outcome]
    res = run_analysis(sub, cache_dir=None)
    o = res.get("iptw_or", {})
    return {
        "kind": KIND_OR,
        "point": o.get("OR"),
        "ci": [o.get("CI_lower"), o.get("CI_upper")],
        "n": o.get("n"),
        "n_events": o.get("n_events"),
        "estimator": "hypotension_treatment.run_analysis (IPTW logistic OR)",
        "balance_max_smd_post": res.get("balance", {}).get("max_smd_post"),
    }


def _estimate_map_hte(df, target_spec, seed=RANDOM_SEED) -> dict:
    """Within-subgroup burden->outcome IPTW risk ratio (the HTE estimand).

    Reuses hypotension_treatment.fit_propensity_model / compute_iptw_weights and
    the actionable_targets within-phenotype RD/RR machinery, restricted to the
    pre-specified subgroup (default preop_htn==1). This is the SAME estimator the
    internal map_hte/map_target analysis uses (IPTW weighted arm risks + bootstrap
    CI on a high-vs-low burden contrast)."""
    import numpy as np
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )
    from vitaldb_aki.analysis.actionable_targets import _weighted_risk_diff_ratio

    outcome = target_spec.get("outcome", "organ_renal")
    axis = target_spec.get("subgroup_axis", "preop_htn")
    burden_col = "map_auc_below_65"

    sub = df.copy()
    # High-vs-low burden exposure = top tertile of burden (matches internal "high burden").
    burden = pd.to_numeric(sub[burden_col], errors="coerce")
    try:
        tert = pd.qcut(burden, q=3, labels=False, duplicates="drop")
    except ValueError:
        tert = pd.Series(1, index=sub.index)
    sub["_exposure"] = (tert == tert.max()).astype(int)
    sub["vasopressor_treated"] = sub["_exposure"]  # alias for PS reuse

    # Confounders: drop the subgroup axis itself.
    covs = [c for c in ["age", "sex_male", "asa_class", "baseline_cr",
                        "egfr_ckd_epi", "preop_dm", "surgery_duration", "ebl"]
            if c in sub.columns and c != axis]
    if sub["vasopressor_treated"].nunique() < 2 or not covs:
        return {"kind": KIND_RR, "point": None, "ci": [None, None],
                "note": "no contrast / no covariates", "n": int(len(sub))}

    df_ps, _m, _u = fit_propensity_model(sub, covariates=covs)
    df_w = compute_iptw_weights(df_ps)

    # Restrict to the right-shifted-autoregulation subgroup.
    if axis in df_w.columns:
        mask = pd.to_numeric(df_w[axis], errors="coerce").fillna(0) == 1
    else:
        mask = pd.Series(True, index=df_w.index)
    g = df_w[mask].copy()
    y = pd.to_numeric(g[outcome], errors="coerce")
    valid = y.notna() & g["_exposure"].notna() & g["iptw_weight"].notna()
    g = g[valid]
    yv = pd.to_numeric(g[outcome], errors="coerce").astype(int).to_numpy()
    ev = g["_exposure"].astype(int).to_numpy()
    wv = g["iptw_weight"].to_numpy(dtype=float)
    n = int(len(g))
    if n == 0 or ev.min() == ev.max():
        return {"kind": KIND_RR, "point": None, "ci": [None, None],
                "note": "empty subgroup or single arm", "n": n}

    _, _, rd, rr = _weighted_risk_diff_ratio(yv, ev, wv)
    rng = np.random.default_rng(seed)
    rr_boot = []
    for _ in range(500):
        idx = rng.integers(0, n, size=n)
        eb = ev[idx]
        if eb.min() == eb.max():
            continue
        _, _, _, rrb = _weighted_risk_diff_ratio(yv[idx], eb, wv[idx])
        if math.isfinite(rrb):
            rr_boot.append(rrb)
    rr_lo = float(np.percentile(rr_boot, 2.5)) if rr_boot else float("nan")
    rr_hi = float(np.percentile(rr_boot, 97.5)) if rr_boot else float("nan")
    return {
        "kind": KIND_RR,
        "point": round(rr, 4) if math.isfinite(rr) else None,
        "ci": [round(rr_lo, 4) if math.isfinite(rr_lo) else None,
               round(rr_hi, 4) if math.isfinite(rr_hi) else None],
        "rd_point": round(rd, 4) if math.isfinite(rd) else None,
        "n": n, "n_events": int(yv.sum()),
        "subgroup_axis": axis,
        "estimator": "IPTW within-subgroup high-vs-low burden RR (bootstrap CI)",
    }


def _estimate_reperfusion_increment(df, target_spec, seed=RANDOM_SEED) -> dict:
    """Incremental delta-AUROC of recovery_velocity over static burden, via the
    EXACT internal reperfusion_dynamics.incremental_auroc (paired-OOF DeLong)."""
    import numpy as np
    import vitaldb_aki.analysis.reperfusion_dynamics as rd

    outcome = target_spec.get("outcome", "organ_renal")
    sub = df.copy()
    if "subjectid" not in sub.columns and "caseid" in sub.columns:
        sub["subjectid"] = sub["caseid"]
    res = rd.incremental_auroc(sub, ["recovery_velocity"], outcome, seed=seed)
    if res.get("underpowered"):
        return {"kind": KIND_DELTA_AUROC, "point": None, "ci": [None, None],
                "underpowered": True, "n": res.get("n"), "n_events": res.get("events"),
                "note": "underpowered on INSPIRE subset"}
    return {
        "kind": KIND_DELTA_AUROC,
        "point": res.get("delta_auroc"),
        "ci": res.get("delta_auroc_ci95", [None, None]),
        "auroc_static": res.get("auroc_static_burden"),
        "n": res.get("n"), "n_events": res.get("events"),
        "estimator": "reperfusion_dynamics.incremental_auroc (paired-OOF DeLong)",
        "degraded_resolution": True,
    }


def _estimate_pressor_choice(df, target_spec, seed=RANDOM_SEED) -> dict:
    """Phe-vs-norepi IPTW risk ratio for the outcome, reusing the propensity/IPTW
    machinery (phe_vs_norepi is the binary exposure; INSPIRE records both drugs)."""
    import numpy as np
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )
    from vitaldb_aki.analysis.actionable_targets import _weighted_risk_diff_ratio

    outcome = target_spec.get("outcome", "organ_renal")
    sub = df.copy()
    expo = pd.to_numeric(sub.get("phe_vs_norepi"), errors="coerce")
    sub = sub[expo.notna()].copy()
    sub["vasopressor_treated"] = expo[expo.notna()].astype(int).to_numpy()
    covs = [c for c in ["age", "sex_male", "asa_class", "baseline_cr",
                        "egfr_ckd_epi", "preop_htn", "preop_dm",
                        "surgery_duration", "ebl"] if c in sub.columns]
    if sub["vasopressor_treated"].nunique() < 2 or not covs:
        return {"kind": KIND_RR, "point": None, "ci": [None, None],
                "note": "no contrast / no covariates", "n": int(len(sub))}
    df_ps, _m, _u = fit_propensity_model(sub, covariates=covs)
    df_w = compute_iptw_weights(df_ps)
    y = pd.to_numeric(df_w[outcome], errors="coerce")
    valid = y.notna() & df_w["vasopressor_treated"].notna() & df_w["iptw_weight"].notna()
    g = df_w[valid]
    yv = pd.to_numeric(g[outcome], errors="coerce").astype(int).to_numpy()
    ev = g["vasopressor_treated"].astype(int).to_numpy()
    wv = g["iptw_weight"].to_numpy(dtype=float)
    n = int(len(g))
    if n == 0 or ev.min() == ev.max():
        return {"kind": KIND_RR, "point": None, "ci": [None, None],
                "note": "single arm", "n": n}
    _, _, rd, rr = _weighted_risk_diff_ratio(yv, ev, wv)
    rng = np.random.default_rng(seed)
    rr_boot = []
    for _ in range(500):
        idx = rng.integers(0, n, size=n)
        eb = ev[idx]
        if eb.min() == eb.max():
            continue
        _, _, _, rrb = _weighted_risk_diff_ratio(yv[idx], eb, wv[idx])
        if math.isfinite(rrb):
            rr_boot.append(rrb)
    rr_lo = float(np.percentile(rr_boot, 2.5)) if rr_boot else float("nan")
    rr_hi = float(np.percentile(rr_boot, 97.5)) if rr_boot else float("nan")
    return {
        "kind": KIND_RR,
        "point": round(rr, 4) if math.isfinite(rr) else None,
        "ci": [round(rr_lo, 4) if math.isfinite(rr_lo) else None,
               round(rr_hi, 4) if math.isfinite(rr_hi) else None],
        "rd_point": round(rd, 4) if math.isfinite(rd) else None,
        "n": n, "n_events": int(yv.sum()),
        "estimator": "IPTW phe-vs-norepi RR (bootstrap CI)",
    }


_ESTIMATORS: dict[str, Callable] = {
    "_estimate_hypotension_burden": _estimate_hypotension_burden,
    "_estimate_map_hte": _estimate_map_hte,
    "_estimate_reperfusion_increment": _estimate_reperfusion_increment,
    "_estimate_pressor_choice": _estimate_pressor_choice,
}


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================

def run_external_validation(cfg: dict[str, Any], matrix_path: str | None = None,
                            targets: list[str] | None = None,
                            write_status: bool = True) -> dict[str, Any]:
    """Run the INSPIRE replication harness.

    GATED: if the INSPIRE matrix is absent, returns a BLOCKED status dict (and
    writes external_validation_status.json) WITHOUT running or fabricating
    anything. Otherwise, for each replication target, runs the internal estimator
    on the INSPIRE frame and reports the INSPIRE estimate beside the internal
    VitalDB estimate with a pre-specified concordance verdict.
    """
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    status = external_validation_status(cfg, matrix_path=matrix_path)

    if status["blocked"]:
        if write_status:
            _write_status(cache_dir, status)
        return status

    # --- Matrix present: load + run (heavy imports here) ---
    import pandas as pd  # lazy
    path = status["matrix_path"]
    df = pd.read_csv(path)

    chosen = targets or list(REPLICATION_TARGETS.keys())
    internal_results_cache: dict[str, dict] = {}
    target_reports: dict[str, Any] = {}

    for name in chosen:
        spec = REPLICATION_TARGETS.get(name)
        if spec is None:
            target_reports[name] = {"error": f"unknown target {name!r}"}
            continue

        # Required-column check (mapped INTERNAL names).
        missing = [c for c in spec["required_cols"] if c not in df.columns]
        if missing:
            target_reports[name] = {
                "label": spec["label"], "kind": spec["kind"],
                "ran": False,
                "reason": f"INSPIRE matrix missing required mapped columns: {missing}. "
                          "See INSPIRE_VARIABLE_MAP for how to derive them.",
            }
            continue

        # PENDING check: required columns PRESENT but entirely empty (all-NaN).
        # This is the explicit "data not yet available" state -- e.g. the MAP /
        # burden / recovery columns before vitals.csv.gz has finished downloading.
        # It avoids a misleading estimator crash / "no contrast" message and marks
        # the target as PENDING rather than DISCORDANT.
        empty = _empty_required_cols(df, spec["required_cols"])
        if empty:
            target_reports[name] = {
                "label": spec["label"], "kind": spec["kind"],
                "ran": False,
                "pending": True,
                "reason": f"PENDING upstream data: required columns present but EMPTY "
                          f"(all-NaN): {empty}. For MAP/burden/recovery columns this "
                          "means vitals.csv.gz is not yet built into the matrix. "
                          "Rebuild the matrix once vitals is downloaded, then re-run.",
            }
            continue

        # Internal VitalDB estimate.
        ifile = spec["internal_result_file"]
        if ifile not in internal_results_cache:
            internal_results_cache[ifile] = _load_internal_result(cache_dir, ifile)
        internal = spec["internal_extractor"](internal_results_cache[ifile])

        # INSPIRE estimate (run the internal estimator on INSPIRE data).
        est = _ESTIMATORS[spec["estimator"]]
        try:
            inspire = est(df, spec, seed=seed)
        except Exception as exc:  # never let one target crash the harness
            target_reports[name] = {
                "label": spec["label"], "kind": spec["kind"], "ran": False,
                "reason": f"estimator raised: {type(exc).__name__}: {exc}",
            }
            continue

        verdict = judge_concordance(internal, inspire, spec["kind"])
        report = {
            "label": spec["label"],
            "kind": spec["kind"],
            "ran": True,
            "internal_vitaldb": internal,
            "inspire": inspire,
            "concordance": verdict,
        }
        if spec.get("degraded"):
            report["caveat"] = ("DEGRADED-RESOLUTION replication: INSPIRE has coarse "
                                "MBP, not arterial waveforms -- proxy validation only.")
        target_reports[name] = report

    out = {
        "blocked": False,
        "status": "RAN",
        "matrix_path": path,
        "n_inspire_cases": int(len(df)),
        "seed": seed,
        "concordance_criteria": dict(CONCORDANCE),
        "targets": target_reports,
        "unvalidatable_on_inspire": NO_INSPIRE_EQUIVALENT,
        "summary": {
            "n_targets_run": sum(1 for r in target_reports.values()
                                 if isinstance(r, dict) and r.get("ran")),
            "n_concordant": sum(1 for r in target_reports.values()
                                if isinstance(r, dict) and r.get("ran")
                                and r.get("concordance", {}).get("concordant")),
            "n_pending": sum(1 for r in target_reports.values()
                             if isinstance(r, dict) and r.get("pending")),
            "pending_targets": [n for n, r in target_reports.items()
                                if isinstance(r, dict) and r.get("pending")],
        },
    }
    if write_status:
        _write_status(cache_dir, out)
    return out


def _write_status(cache_dir: str, payload: dict) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, STATUS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=_json_default)
    return path


# ===========================================================================
# SYNTHETIC INSPIRE FRAME -- SMOKE TEST DATA ONLY (clearly labelled synthetic).
# NEVER written to cache/inspire_matrix.csv; never reported as a result.
# ===========================================================================

def make_synthetic_inspire_frame(n: int = 600, seed: int = RANDOM_SEED):
    """Build a small INSPIRE-SHAPED *SYNTHETIC* frame for the smoke test ONLY.

    This is NOT INSPIRE data. It exists solely to prove the harness wiring runs
    end-to-end (estimators fire, concordance fields populate). The structure mimics
    a real INSPIRE-derived matrix (mapped INTERNAL column names per
    INSPIRE_VARIABLE_MAP) with a planted confounding-by-indication structure so the
    estimators have signal to chew on. Do NOT persist this to the gate path.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    age = rng.normal(60, 13, n).clip(18, 92)
    sex_male = rng.integers(0, 2, n)
    asa = rng.choice([1, 2, 3, 4], n, p=[0.15, 0.45, 0.35, 0.05]).astype(float)
    baseline_cr = rng.gamma(1.2, 0.8, n).clip(0.4, 6.0)
    egfr = (140 - age) / (baseline_cr * 72.0) * 100.0
    preop_htn = rng.binomial(1, 0.42, n)
    preop_dm = rng.binomial(1, 0.2, n)
    surgery_duration = rng.gamma(3.0, 45.0, n)
    ebl = rng.exponential(220, n)
    optype_code = rng.integers(0, 8, n).astype(float)

    # Hypotension burden (zero-inflated heavy tail) -- the exposure.
    burden = rng.exponential(6.0, n)
    map_min65 = rng.exponential(2.0, n)
    map_mean = (78 - 0.05 * burden + rng.normal(0, 6, n)).clip(50, 110)
    map_lowest = (62 - 0.04 * burden + rng.normal(0, 5, n)).clip(30, 90)

    # Recovery velocity (incremental feature) -- weakly outcome-linked.
    recovery_velocity = rng.normal(0.0, 1.0, n) - 0.03 * burden / 10.0

    # Pressor exposure (confounded) and choice.
    p_trt = 1.0 / (1.0 + np.exp(-(-1.2 + 0.06 * (burden - burden.mean()) + 0.4 * (asa > 2))))
    any_vaso = rng.binomial(1, p_trt, n)
    # phe vs norepi among the pressor-exposed (1=phe-dominant, 0=norepi).
    phe_vs_norepi = np.full(n, np.nan)
    exposed = any_vaso == 1
    phe_vs_norepi[exposed] = rng.binomial(1, 0.6, exposed.sum())
    intraop_phe = np.where(phe_vs_norepi == 1, rng.exponential(120, n), 0.0)
    intraop_norepi = np.where(phe_vs_norepi == 0, rng.exponential(80, n), 0.0)
    # Ephedrine: VitalDB hypotension_treatment.define_treatment keys on
    # intraop_eph OR intraop_phe; INSPIRE records ephedrine too, so carry it.
    intraop_eph = np.where(any_vaso == 1, rng.exponential(6.0, n), 0.0)

    # Outcomes: renal (KDIGO) + composite, driven by burden + sickness, with a
    # phe-vs-norepi penalty (phe pressure != perfusion) so the estimator has a sign.
    lo_renal = (-3.0 + 0.05 * (burden - burden.mean()) + 0.4 * (asa > 2)
                + 0.5 * (baseline_cr > 1.5) - 0.3 * any_vaso
                + 0.4 * np.nan_to_num(phe_vs_norepi))
    p_renal = 1.0 / (1.0 + np.exp(-lo_renal))
    organ_renal = rng.binomial(1, p_renal, n).astype(float)
    lo_comp = lo_renal + 0.3 * (ebl > 400)
    composite = rng.binomial(1, 1.0 / (1.0 + np.exp(-lo_comp)), n).astype(float)

    df = pd.DataFrame({
        "caseid": [f"INSPIRE_SYNTH_{i:05d}" for i in range(n)],
        "subjectid": [f"INSPIRE_SYNTH_{i:05d}" for i in range(n)],
        "map_auc_below_65": burden,
        "map_min_below_65": map_min65,
        "map_mean": map_mean,
        "map_lowest": map_lowest,
        "recovery_velocity": recovery_velocity,
        "any_vasopressor": any_vaso.astype(int),
        "phe_vs_norepi": phe_vs_norepi,
        "intraop_phe": intraop_phe,
        "intraop_norepi": intraop_norepi,
        "intraop_eph": intraop_eph,
        "age": age, "sex_male": sex_male, "asa_class": asa,
        "baseline_cr": baseline_cr, "egfr_ckd_epi": egfr,
        "preop_htn": preop_htn, "preop_dm": preop_dm,
        "surgery_duration": surgery_duration, "ebl": ebl,
        "optype_code": optype_code,
        "organ_renal": organ_renal, "composite": composite,
    })
    df.attrs["SYNTHETIC"] = True
    df.attrs["WARNING"] = "SYNTHETIC smoke-test data -- NOT INSPIRE; never a result."
    return df


def smoke_test(seed: int = RANDOM_SEED) -> dict[str, Any]:
    """Self-contained end-to-end smoke test of the harness on SYNTHETIC INSPIRE-
    shaped data. Writes the synthetic frame to a TEMP path (never the gate path),
    runs run_external_validation against it, and returns the report.

    Asserts (raises AssertionError on failure) that the output schema is correct:
    every chosen target ran and produced populated concordance fields.
    """
    import tempfile

    df = make_synthetic_inspire_frame(n=600, seed=seed)
    tmpdir = tempfile.mkdtemp(prefix="inspire_smoke_")
    matrix_path = os.path.join(tmpdir, "synthetic_inspire_matrix.csv")  # NOT the gate path
    df.to_csv(matrix_path, index=False)

    cfg = {"cache_dir": tmpdir, "seed": seed}   # temp cache so we never touch real cache
    report = run_external_validation(cfg, matrix_path=matrix_path, write_status=False)

    # --- schema assertions ---
    assert report["blocked"] is False, "harness should run when matrix present"
    assert report["status"] == "RAN"
    assert report["n_inspire_cases"] == 600
    assert "targets" in report and len(report["targets"]) == len(REPLICATION_TARGETS)
    for name, rep in report["targets"].items():
        assert rep.get("ran") is True, f"target {name} did not run: {rep}"
        conc = rep.get("concordance", {})
        assert "concordant" in conc, f"target {name} missing concordant field"
        assert "components" in conc, f"target {name} missing components"
        assert set(conc["components"]) == {
            "same_direction", "ci_overlap", "magnitude_within_factor"
        }, f"target {name} bad components"
        assert "internal_point" in conc and "inspire_point" in conc
    return report


# ===========================================================================
# CLI -- prints BLOCKED status when the matrix is absent (the live default).
# ===========================================================================

def _default_cfg() -> dict[str, Any]:
    here = os.path.dirname(os.path.abspath(__file__))
    return {"cache_dir": os.path.join(os.path.dirname(here), "cache"),
            "seed": RANDOM_SEED}


if __name__ == "__main__":
    import sys

    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    if "--smoke" in sys.argv:
        rep = smoke_test()
        print("[external_validation] SMOKE TEST passed on SYNTHETIC data.")
        print(f"  targets run: {rep['summary']['n_targets_run']} / "
              f"{len(REPLICATION_TARGETS)}; concordant: {rep['summary']['n_concordant']}")
        for nm, r in rep["targets"].items():
            c = r["concordance"]
            print(f"  - {nm}: internal={c['internal_point']} "
                  f"inspire={c['inspire_point']} -> {c['verdict']}")
        sys.exit(0)

    cfg = _default_cfg()
    status = run_external_validation(cfg)   # writes external_validation_status.json
    print(f"[external_validation] status: {status['status']}")
    for r in status.get("reasons", []):
        print(f"  - {r}")
    print(f"  replication targets ({len(REPLICATION_TARGETS)}): "
          f"{', '.join(REPLICATION_TARGETS)}")
    print(f"  pre-specified concordance bar: same direction + CI overlap + "
          f"magnitude within {CONCORDANCE['magnitude_factor']}x")
    print("  CANNOT be validated on INSPIRE (no waveforms): "
          f"{', '.join(NO_INSPIRE_EQUIVALENT)}")
    if status["blocked"]:
        print(f"  -> external_validation_status.json written; "
              f"drop {os.path.join(_resolve_cache_dir(cfg), INSPIRE_MATRIX_FILE)} "
              "to unlock.")
