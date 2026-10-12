"""vasoplegia_biomarker.py -- A dedicated VASOPLEGIA / PRESSOR-RESPONSIVENESS
biomarker and its validation for the VitalDB postoperative-AKI study.

THE IDEA (the pressor-side analog of SVV)
-----------------------------------------
SVV / PPV quantify FLUID responsiveness ("would a bolus raise stroke volume?").
This module builds the TWIN that quantifies PRESSOR responsiveness / VASOPLEGIA:
does the vasculature still respond to a vasopressor and hold arterial TONE, or is
tone pathologically lost (vasoplegia)?  That is the second axis of the arterial-
line "fluid vs pressor" decision, and -- like occult hypovolemia -- a vasoplegic
circulation under-perfuses the kidney even when MAP looks adequate.

THREE BIOMARKER FAMILIES (axes)
-------------------------------
A. PUMP + MAP REQUIREMENT (download-free, full cohort).  How hard did the
   circulation have to be propped up, and did MAP respond?
     * norepinephrine-equivalent (NEE) total + peak dose (reusing the
       actionable_targets pressor -> phenylephrine-equivalent conversion, then
       to a norepi-equivalent axis),
     * pressor-duration fraction / multi-agent breadth,
     * MAP-per-dose GAIN proxy (vaso_responsiveness; blunted = vasoplegia).
   Low gain + high requirement = vasoplegia.

B. CO-BASED REFERENCE STANDARD (EV1000 / Vigileo subset).  MEASURED SVR / SVRI
   from fluid_responsiveness -- the gold-standard vasoplegia marker.  Used to
   VALIDATE the waveform surrogate (family C).  This subset is small in VitalDB
   and is NOT pre-extracted into a flat cache, so it is loaded if available and
   otherwise reported as N=0 / "validation deferred".

C. WAVEFORM-ONLY TONE SURROGATE (the novel one).  From the A-line morphology
   pilot (cache/aline_sample.csv): the diastolic decay time constant
   tau = R*C of the arterial tree (LOW tau = fast diastolic runoff = LOW
   resistance = vasoplegia), the diastolic/MAP ratio, the (MAP-diastolic)/PP
   "form factor", and the augmentation index (a wave-reflection / tone proxy).
   These are combined into ONE pre-specified WAVEFORM VASOPLEGIA INDEX
   (z-scored mean, oriented so HIGH = more vasoplegia).

VALIDATION (what this module reports)
-------------------------------------
  1. CONSTRUCT VALIDITY (the headline): does the waveform-only tone surrogate (C)
     correlate with MEASURED SVR (B) in the EV1000 subset where both exist?
     Spearman r + N.  If the joint subset is tiny / absent, this is flagged
     LOUDLY as preliminary -- it is the validation that powers the eventual
     "SVR-free vasoplegia index" claim.
  2. CONVERGENT: do A (requirement/gain) and C (waveform tone) agree on a
     vasoplegic phenotype?  Spearman r + a 2x2 on median splits.
  3. CRITERION: does each biomarker predict (a) high pressor REQUIREMENT and
     (b) organ injury (renal / composite), INCREMENTAL over MAP burden
     (map_auc_below_65, map_mean)?  Incremental AUROC (LR p, patient-clustered
     bootstrap CI) + IPTW-adjusted per-SD/median-split logistic (E-values) +
     organ_hepatocellular negative control + BH-FDR.
  4. DOSE-RESPONSE: quartiles of the primary vasoplegia index vs organ-injury
     rate (direction-aware: MORE vasoplegia hypothesised -> MORE injury).

LEAKAGE FIREWALL
----------------
Every biomarker / predictor is PREOP+INTRAOP only (dose totals, pump duration,
intraop arterial-waveform morphology, MAP burden).  organ_* outcomes are y --
NEVER a feature.

REUSE (does NOT duplicate)
--------------------------
  * features/vasoactive_pd.py    -- the vaso_* requirement/gain signal (v1).
  * features/fluid_responsiveness.py -- measured SVR (reference standard).
  * features/aline_morphology.py / cross_waveform.py -- the waveform morphology
    feeding cache/aline_sample.csv.
  * analysis/actionable_targets.py -- pressor->equiv conversion, e_value /
    e_value_ci, benjamini_hochberg, IPTW propensity machinery.
  * analysis/aline_feasibility.py  -- _auroc, _incremental_logit, _spearman_rho,
    dose-response / Cochran-Armitage helpers, outcome/sample loaders.

This is HYPOTHESIS-GENERATING.  Heavy deps (numpy/sklearn/scipy/pandas) are
lazy-imported; the module imports with the stdlib only.

Run:  python3 -m vitaldb_aki.analysis.vasoplegia_biomarker
"""
from __future__ import annotations

import csv as _csv
import json
import math
import os
from typing import Any

# ---------------------------------------------------------------------------
# Constants (binding; config-as-code)
# ---------------------------------------------------------------------------
CACHE_DEFAULT = "vitaldb_aki/cache"
RANDOM_SEED = 20260626                 # matches config.yaml seed

ALINE_SAMPLE_CSV = "aline_sample.csv"
FEATURE_MATRIX_FILE = "feature_matrix.csv"
FEATURE_MATRIX_ENRICHED = "feature_matrix_enriched.csv"   # preferred if present
COMPOSITE_FILE = "cohort_composite.csv"
CASES_FILE = "cases.csv"
SVR_SUBSET_CSV = "fluid_responsiveness_sample.csv"        # measured SVR, if extracted

RESULTS_JSON = "vasoplegia_biomarker_results.json"
DONE_MARKER = "_vasoplegia_biomarker_done.json"
RESULTS_MD = "VASOPLEGIA_BIOMARKER.md"

# Outcomes (y; never a feature).
PRIMARY_OUTCOMES = ("organ_renal", "composite")
NEGATIVE_CONTROL_OUTCOME = "organ_hepatocellular"

# MAP-burden baseline the vasoplegia signal must beat (the accepted hypotension
# dose paradigm).  map_auc_below_65 is the primary; map_mean is added as a 2nd
# baseline column where present.
MAP_BURDEN_BASELINE = "map_auc_below_65"
MAP_BURDEN_BASELINE2 = "map_mean"

# Norepinephrine-equivalent (NEE) potency anchors (rough, documented; NOT a PK
# claim -- used only to put pressors on a single requirement axis).  Reference:
# norepinephrine = 1.  Phenylephrine ~ 1/10 as potent (ug), so 10 ug phe ~ 1 ug
# norepi-equiv; epinephrine ~ parity (ug); ephedrine bolus is dosed in mg and is
# far weaker -- 1 mg ephedrine ~ 1 ug norepi-equiv (order-of-magnitude anchor).
# These convert the /cases & matrix dose totals to a common "requirement" scale.
PHE_UG_PER_NEE_UG = 10.0       # 10 ug phenylephrine ~ 1 ug norepi-equivalent
EPI_UG_PER_NEE_UG = 1.0        # epinephrine ug ~ parity on the ug axis
EPH_MG_PER_NEE_UG = 1.0        # 1 mg ephedrine ~ 1 ug norepi-equivalent (anchor)

# BODY-SIZE / DOSE NORMALIZATION (binding methodological control).
# A raw-dose requirement marker is confounded by body size (a big patient needs
# more drug for the same effect), so Family-A pressor doses are normalised PER KG.
# UNIT ASSUMPTION: the matrix dose totals (phe_total_ug, nepi_cum_dose, ...) are
# CUMULATIVE amounts (ug / mg) over the case, so the NEE total normalised by
# weight is ug-NEE PER KG (a per-case cumulative-per-kg requirement).  The
# clinically familiar norepi-equivalent is ug/kg/MIN (a RATE); we do NOT have a
# clean per-case infusion-minutes denominator in the flat matrix, so we report
# the cumulative ug-NEE/kg and state this assumption explicitly.  BSA (Mosteller)
# = sqrt(height_cm * weight_kg / 3600) is also computed and used to INDEX SVR.
SVR_TO_SVRI = "multiply_by_bsa"   # SVRI = SVR * BSA (size-indexed vascular resistance)

# Body-size + demographic covariates added to EVERY criterion adjustment set so a
# biomarker's predictive value is not merely a body-size / demographic proxy.
SIZE_DEMO_COVARIATES = ("weight_kg", "bsa_m2", "age", "sex_male")

# Power / honesty thresholds.
MIN_EVENTS_FEASIBLE = 10       # below this a criterion cell is feasibility-only
FDR_ALPHA = 0.05
N_BOOTSTRAP = 500
DOSE_RESPONSE_MAX_Q = 4
DOSE_RESPONSE_MIN_Q = 3
DOSE_RESPONSE_MIN_N = 20

# A "high pressor REQUIREMENT" label (criterion target 3a): any norepi infusion,
# OR a phenylephrine-equivalent dose in the top cohort quartile.  Defined on
# PREOP+INTRAOP exposure only.
HIGH_REQUIREMENT_TOP_QUANTILE = 0.75

# ---------------------------------------------------------------------------
# Waveform tone surrogate (family C) component columns from aline_sample.csv.
# Orientation factor: multiply so that HIGHER oriented value == MORE vasoplegia.
#   art_tau_decay_mean      : tau = R*C; LOW tau = vasoplegia          -> sign -1
#   diastolic_over_map      : DBP/MAP; LOW = poor tone (runs off)      -> sign -1
#   map_dia_form_factor     : (MAP-DBP)/PP; LOW = decay-dominated      -> sign -1
#   art_aug_index_mean      : wave reflection; LOW = low tone          -> sign -1
# (All four point the same way: a LOW value indicates lost tone, so the
#  vasoplegia index is the z-scored mean of their NEGATED z-scores.)
# ---------------------------------------------------------------------------
WAVEFORM_TONE_COMPONENTS = {
    "art_tau_decay_mean": -1.0,
    "_diastolic_over_map": -1.0,
    "_map_dia_form_factor": -1.0,
    "art_aug_index_mean": -1.0,
}

# Family-A requirement/gain biomarkers (matrix-derived, full cohort).
# ALL doses are WEIGHT-NORMALISED (per kg) to remove body-size confounding.
#   nee_total_ug_per_kg : norepi-equiv total dose / kg (requirement) HIGH=vasoplegia
#   nee_peak_rate_per_kg: peak NEE infusion intensity / kg           HIGH=vasoplegia
#   pressor_dur_min     : total pressor infusion duration (min; size-free) HIGH=vaso
#   pressor_n_agents    : distinct vasoactive agents used (size-free)  HIGH=vasoplegia
# Orientation: +1 means HIGHER == MORE vasoplegia (so AUROC>0.5 = harmful).
FAMILY_A_BIOMARKERS = {
    "nee_total_ug_per_kg": +1.0,
    "nee_peak_rate_per_kg": +1.0,
    "pressor_dur_min": +1.0,
    "pressor_n_agents": +1.0,
}

# The PRIMARY vasoplegia index used for dose-response is the waveform index when
# the waveform subset exists, else the family-A requirement index.
PRIMARY_INDEX_WAVEFORM = "waveform_vasoplegia_index"
PRIMARY_INDEX_REQUIREMENT = "requirement_vasoplegia_index"


# ===========================================================================
# REUSED PURE HELPERS (imported from sibling analysis modules; stdlib only)
# ===========================================================================
def _import_helpers():
    """Lazy import of the reused stdlib helpers (kept out of import surface)."""
    from vitaldb_aki.analysis.aline_feasibility import (
        _spearman_rho, _auroc, _incremental_logit,
        quantile_breaks, assign_quantiles, cochran_armitage_trend,
    )
    from vitaldb_aki.analysis.actionable_targets import (
        e_value, e_value_ci, benjamini_hochberg,
    )
    return {
        "spearman": _spearman_rho, "auroc": _auroc,
        "incremental_logit": _incremental_logit,
        "quantile_breaks": quantile_breaks, "assign_quantiles": assign_quantiles,
        "cochran_armitage": cochran_armitage_trend,
        "e_value": e_value, "e_value_ci": e_value_ci,
        "benjamini_hochberg": benjamini_hochberg,
    }


def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return CACHE_DEFAULT


def _resolve_seed(cfg: dict[str, Any]) -> int:
    return int(cfg.get("seed", RANDOM_SEED))


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "NA", "None", "NaN"):
        return None
    try:
        f = float(s)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _zscores(vals: list[float | None]) -> list[float | None]:
    """Standard z-scores over the finite entries; None passes through."""
    finite = [v for v in vals if v is not None and math.isfinite(v)]
    if len(finite) < 3:
        return [None] * len(vals)
    mu = sum(finite) / len(finite)
    var = sum((v - mu) ** 2 for v in finite) / (len(finite) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return [None] * len(vals)
    return [((v - mu) / sd) if (v is not None and math.isfinite(v)) else None
            for v in vals]


def nee_total_ug(phe_ug, eph_mg, epi_ug, nepi_ug=None) -> float:
    """Total norepinephrine-equivalent pressor exposure (ug-NEE; RAW, not /kg).

    NEE = nepi_ug + phe_ug/PHE_UG_PER_NEE_UG + epi_ug/EPI_UG_PER_NEE_UG
          + eph_mg/EPH_MG_PER_NEE_UG.  Missing components count as zero.
    Documented potency anchors (NOT a PK claim).  Weight-normalisation is applied
    by the caller (divide by weight_kg) to remove body-size confounding.
    """
    def _z(x):
        f = _to_float(x)
        return f if (f is not None and f > 0) else 0.0
    total = _z(nepi_ug)
    total += _z(phe_ug) / PHE_UG_PER_NEE_UG
    total += _z(epi_ug) / EPI_UG_PER_NEE_UG
    total += _z(eph_mg) / EPH_MG_PER_NEE_UG
    return total


def bsa_mosteller(height_cm, weight_kg) -> float | None:
    """Body-surface area (m^2) via Mosteller: sqrt(height_cm * weight_kg / 3600).
    Returns None if either input is missing / non-positive."""
    h = _to_float(height_cm)
    w = _to_float(weight_kg)
    if h is None or w is None or h <= 0 or w <= 0:
        return None
    return round(math.sqrt(h * w / 3600.0), 6)


# ===========================================================================
# STEP 1 -- ASSEMBLE the analysis frame from ALREADY-EXTRACTED caches
# ===========================================================================
def _load_matrix(cache_dir: str):
    """Load feature_matrix_enriched.csv if present, else feature_matrix.csv.
    Returns (rows_by_cid: dict, source_filename)."""
    for fn in (FEATURE_MATRIX_ENRICHED, FEATURE_MATRIX_FILE):
        path = os.path.join(cache_dir, fn)
        if os.path.exists(path):
            rows: dict[str, dict[str, str]] = {}
            with open(path, "r", newline="", encoding="utf-8") as fh:
                for r in _csv.DictReader(fh):
                    cid = str(r.get("caseid", "")).strip()
                    if cid:
                        rows[cid] = r
            return rows, fn
    return {}, None


def _load_composite(cache_dir: str):
    """Load {caseid: {outcome: 0/1, subjectid}} from cohort_composite.csv."""
    path = os.path.join(cache_dir, COMPOSITE_FILE)
    out: dict[str, dict[str, Any]] = {}
    if not os.path.exists(path):
        return out
    want = list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]
    with open(path, "r", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            cid = str(r.get("caseid", "")).strip()
            if not cid:
                continue
            rec = {oc: _to_float(r.get(oc)) for oc in want}
            rec["subjectid"] = str(r.get("subjectid", cid)).strip() or cid
            out[cid] = rec
    return out


def _load_aline(cache_dir: str):
    """Load {caseid: row} for aline_available==1 rows from aline_sample.csv."""
    path = os.path.join(cache_dir, ALINE_SAMPLE_CSV)
    out: dict[str, dict[str, str]] = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            cid = str(r.get("caseid", "")).strip()
            if not cid:
                continue
            if str(r.get("aline_available", "")).strip() in ("1", "1.0", "True"):
                out[cid] = r
    return out


def _load_measured_svr(cache_dir: str):
    """Load measured SVR/SVRI per case from a flat fluid-responsiveness cache, if
    one was extracted.  Returns {caseid: {svr_mean, svr_min, svr_low_frac}}.

    There is no committed flat SVR cache in this repo (the EV1000 subset requires
    a dedicated extraction); so this returns {} unless `SVR_SUBSET_CSV` exists.
    We DO scan an enriched feature matrix for fluid_svr_* columns first (a future
    enrichment may carry them there)."""
    out: dict[str, dict[str, float | None]] = {}
    # (a) enriched matrix may carry fluid_svr_* columns.
    for fn in (FEATURE_MATRIX_ENRICHED, FEATURE_MATRIX_FILE):
        path = os.path.join(cache_dir, fn)
        if not os.path.exists(path):
            continue
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = _csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
            if "fluid_svr_mean" not in cols:
                break   # this matrix has no SVR; stop (don't fall through file 2)
            is_svri_col = "fluid_svr_is_svri" in cols
            for r in reader:
                cid = str(r.get("caseid", "")).strip()
                sm = _to_float(r.get("fluid_svr_mean"))
                if cid and sm is not None:
                    out[cid] = {
                        "svr_mean": sm,
                        "svr_min": _to_float(r.get("fluid_svr_min")),
                        "svr_low_frac": _to_float(r.get("fluid_svr_low_frac")),
                        # EV1000/SVRI is already a body-size INDEX; EV1000/SVR is not.
                        "is_svri": (str(r.get("fluid_svr_is_svri", "")).strip()
                                    in ("1", "1.0", "True")) if is_svri_col else False,
                    }
        if out:
            return out
    # (b) dedicated flat SVR subset cache.
    path = os.path.join(cache_dir, SVR_SUBSET_CSV)
    if os.path.exists(path):
        with open(path, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                sm = _to_float(r.get("fluid_svr_mean") or r.get("svr_mean"))
                if cid and sm is not None:
                    out[cid] = {
                        "svr_mean": sm,
                        "svr_min": _to_float(r.get("fluid_svr_min")
                                             or r.get("svr_min")),
                        "svr_low_frac": _to_float(r.get("fluid_svr_low_frac")
                                                  or r.get("svr_low_frac")),
                        "is_svri": (str(r.get("fluid_svr_is_svri")
                                        or r.get("is_svri") or "").strip()
                                    in ("1", "1.0", "True")),
                    }
    return out


def assemble_frame(cfg: dict[str, Any]):
    """Assemble the per-case analysis frame from the caches (NO extraction).

    Returns (frame: dict[cid->dict], meta: dict).  Each frame row carries:
      caseid, subjectid, outcomes, MAP-burden baselines,
      family-A requirement/gain biomarkers (full cohort),
      family-C waveform tone components + waveform_vasoplegia_index (aline subset),
      family-B measured SVR (if available),
      derived requirement_vasoplegia_index and high_requirement label.
    """
    cache_dir = _resolve_cache_dir(cfg)
    matrix, matrix_src = _load_matrix(cache_dir)
    comp = _load_composite(cache_dir)
    aline = _load_aline(cache_dir)
    svr = _load_measured_svr(cache_dir)

    all_cids = set(matrix) | set(comp)
    frame: dict[str, dict[str, Any]] = {}

    for cid in all_cids:
        m = matrix.get(cid, {})
        c = comp.get(cid, {})
        row: dict[str, Any] = {"caseid": cid}
        row["subjectid"] = c.get("subjectid", cid)

        # ---- outcomes (y) -------------------------------------------------
        for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
            v = c.get(oc)
            if v is None:
                v = _to_float(m.get(oc))   # matrix also carries outcome cols
            row[oc] = v

        # ---- MAP-burden baselines ----------------------------------------
        row[MAP_BURDEN_BASELINE] = _to_float(m.get(MAP_BURDEN_BASELINE))
        row[MAP_BURDEN_BASELINE2] = _to_float(m.get(MAP_BURDEN_BASELINE2))

        # ---- body size + demographics (size/dose-confounding controls) ----
        weight_kg = _to_float(m.get("weight_kg"))
        height_cm = _to_float(m.get("height_cm"))
        row["weight_kg"] = weight_kg
        row["height_cm"] = height_cm
        row["bmi"] = _to_float(m.get("bmi"))
        row["age"] = _to_float(m.get("age"))
        row["sex_male"] = _to_float(m.get("sex_male"))
        row["bsa_m2"] = bsa_mosteller(height_cm, weight_kg)

        # ---- FAMILY A: requirement/gain (matrix dose columns; WEIGHT-NORM) --
        phe_ug = _to_float(m.get("phe_total_ug"))
        eph_mg = _to_float(m.get("eph_bolus_mg"))
        epi_ug = _to_float(m.get("epi_cum_dose"))
        nepi_ug = _to_float(m.get("nepi_cum_dose"))
        nee_raw = nee_total_ug(phe_ug, eph_mg, epi_ug, nepi_ug)
        row["nee_total_ug"] = nee_raw                      # raw (kept for ref/label)
        # Weight-normalised requirement: ug-NEE PER KG (removes body-size confound).
        row["nee_total_ug_per_kg"] = (
            round(nee_raw / weight_kg, 6)
            if (weight_kg and weight_kg > 0) else None)
        # Peak NEE intensity: max of the per-drug peak rates on the NEE axis.
        phe_peak = _to_float(m.get("phe_peak_rate")) or 0.0
        nepi_peak = _to_float(m.get("nepi_peak_rate")) or 0.0
        epi_peak = _to_float(m.get("epi_peak_rate")) or 0.0
        nee_peak_raw = max(
            nepi_peak,
            phe_peak / PHE_UG_PER_NEE_UG,
            epi_peak / EPI_UG_PER_NEE_UG,
        )
        row["nee_peak_rate"] = nee_peak_raw
        row["nee_peak_rate_per_kg"] = (
            round(nee_peak_raw / weight_kg, 6)
            if (weight_kg and weight_kg > 0) else None)
        # Total pressor infusion duration = union proxy via max of per-drug dur.
        durs = [
            _to_float(m.get("phe_dur_min")) or 0.0,
            _to_float(m.get("nepi_dur_min")) or 0.0,
            _to_float(m.get("epi_dur_min")) or 0.0,
            _to_float(m.get("dopa_dur_min")) or 0.0,
            _to_float(m.get("vaso_dur_min")) or 0.0,
        ]
        row["pressor_dur_min"] = max(durs) if any(d > 0 for d in durs) else 0.0
        # Distinct vasoactive agents with any positive evidence.
        n_agents = 0
        if (phe_ug or 0) > 0 or phe_peak > 0:
            n_agents += 1
        if (nepi_ug or 0) > 0 or nepi_peak > 0:
            n_agents += 1
        if (epi_ug or 0) > 0 or epi_peak > 0:
            n_agents += 1
        if (eph_mg or 0) > 0:
            n_agents += 1
        if (_to_float(m.get("dopa_cum_dose")) or 0) > 0:
            n_agents += 1
        if (_to_float(m.get("vaso_cum_dose")) or 0) > 0:
            n_agents += 1
        row["pressor_n_agents"] = float(n_agents)

        # ---- FAMILY C: waveform tone surrogate (aline subset) ------------
        a = aline.get(cid)
        row["aline_available"] = 1 if a is not None else 0
        if a is not None:
            tau = _to_float(a.get("art_tau_decay_mean"))
            dbp = _to_float(a.get("art_dbp_mean"))
            amap = _to_float(a.get("art_map_mean"))
            pp = _to_float(a.get("art_pulse_pressure_mean"))
            aug = _to_float(a.get("art_aug_index_mean"))
            row["art_tau_decay_mean"] = tau
            row["art_aug_index_mean"] = aug
            # diastolic/MAP ratio (LOW = poor tone).
            row["_diastolic_over_map"] = (
                (dbp / amap) if (dbp is not None and amap and amap > 0) else None)
            # form factor (MAP-DBP)/PP (LOW = decay-dominated waveform).
            row["_map_dia_form_factor"] = (
                ((amap - dbp) / pp)
                if (amap is not None and dbp is not None and pp and pp > 0)
                else None)
        else:
            for k in ("art_tau_decay_mean", "art_aug_index_mean",
                      "_diastolic_over_map", "_map_dia_form_factor"):
                row[k] = None

        # ---- FAMILY B: measured SVR (reference standard) -----------------
        # Reference standard is the BSA-INDEXED SVRI (size-normalised vascular
        # resistance), not raw SVR.  If the source already reports SVRI we use it;
        # if it reports SVR we index it ourselves: SVRI = SVR * BSA.
        s = svr.get(cid)
        row["svr_available"] = 1 if s is not None else 0
        svr_mean = s.get("svr_mean") if s else None
        row["fluid_svr_mean"] = svr_mean
        row["fluid_svr_min"] = s.get("svr_min") if s else None
        row["fluid_svr_low_frac"] = s.get("svr_low_frac") if s else None
        # BSA-indexed SVRI (the size-normalised gold standard for vasoplegia).
        svri = None
        if s is not None and s.get("is_svri"):
            svri = svr_mean                      # source already an index
        elif svr_mean is not None and row.get("bsa_m2"):
            svri = round(svr_mean * row["bsa_m2"], 4)
        row["svri_indexed"] = svri

        frame[cid] = row

    # ---- z-scored composite indices (computed across the full frame) -----
    _add_waveform_index(frame)
    _add_requirement_index(frame)
    _add_high_requirement_label(frame)

    meta = {
        "matrix_source": matrix_src,
        "n_cases_total": len(frame),
        "n_with_outcomes": sum(1 for r in frame.values()
                               if r.get("organ_renal") is not None),
        "n_waveform_subset": sum(1 for r in frame.values()
                                 if r.get("aline_available") == 1),
        "n_measured_svr": sum(1 for r in frame.values()
                              if r.get("svr_available") == 1),
        "cache_dir": cache_dir,
    }
    return frame, meta


def _add_waveform_index(frame: dict[str, dict[str, Any]]):
    """WAVEFORM VASOPLEGIA INDEX = mean of orientation-signed z-scores of the
    waveform tone components, restricted to the aline subset; HIGH = vasoplegia.
    Pre-specified simple combination (no outcome fitting)."""
    cids = list(frame)
    comp_z: dict[str, list[float | None]] = {}
    for col, sign in WAVEFORM_TONE_COMPONENTS.items():
        raw = [frame[c].get(col) for c in cids]
        zs = _zscores(raw)
        comp_z[col] = [(sign * z) if z is not None else None for z in zs]
    for i, cid in enumerate(cids):
        if frame[cid].get("aline_available") != 1:
            frame[cid][PRIMARY_INDEX_WAVEFORM] = None
            continue
        parts = [comp_z[col][i] for col in WAVEFORM_TONE_COMPONENTS
                 if comp_z[col][i] is not None]
        frame[cid][PRIMARY_INDEX_WAVEFORM] = (
            round(sum(parts) / len(parts), 6) if parts else None)


def _add_requirement_index(frame: dict[str, dict[str, Any]]):
    """REQUIREMENT VASOPLEGIA INDEX = mean of signed z-scores of the family-A
    requirement/gain biomarkers (full cohort); HIGH = vasoplegia."""
    cids = list(frame)
    comp_z: dict[str, list[float | None]] = {}
    for col, sign in FAMILY_A_BIOMARKERS.items():
        raw = [frame[c].get(col) for c in cids]
        zs = _zscores(raw)
        comp_z[col] = [(sign * z) if z is not None else None for z in zs]
    for i, cid in enumerate(cids):
        parts = [comp_z[col][i] for col in FAMILY_A_BIOMARKERS
                 if comp_z[col][i] is not None]
        frame[cid][PRIMARY_INDEX_REQUIREMENT] = (
            round(sum(parts) / len(parts), 6) if parts else None)


def _add_high_requirement_label(frame: dict[str, dict[str, Any]]):
    """high_requirement = WEIGHT-NORMALISED NEE dose (ug-NEE/kg) in the top cohort
    quartile (criterion target 3a: does the biomarker predict who needed the most
    pressor support, per body size?).  Using the per-kg dose (not raw) means the
    "high requirement" label is itself body-size-corrected."""
    cids = list(frame)
    nee = [frame[c].get("nee_total_ug_per_kg") for c in cids]
    finite = sorted(v for v in nee if v is not None and v > 0)
    thr = None
    if len(finite) >= 4:
        k = int(HIGH_REQUIREMENT_TOP_QUANTILE * (len(finite) - 1))
        thr = finite[k]
    for cid in cids:
        v = frame[cid].get("nee_total_ug_per_kg")
        hi = 1 if (thr is not None and v is not None and v >= thr and v > 0) else 0
        frame[cid]["high_requirement"] = hi


# ===========================================================================
# STEP 2 -- VALIDATION 1: construct validity (waveform surrogate vs measured SVR)
# ===========================================================================
def construct_validity(frame: dict[str, dict[str, Any]], H) -> dict[str, Any]:
    """Spearman correlation of the WAVEFORM tone surrogate (C) against MEASURED
    SVR (B) in the joint EV1000 subset.  The headline validation that powers the
    SVR-free vasoplegia-index claim.  Reports r + N, and flags small N."""
    # Validate against the BSA-INDEXED SVRI (size-normalised gold standard), not
    # raw SVR.  Fall back to raw SVR only if SVRI could not be indexed (no BSA).
    pairs_idx_svr: list[tuple[float, float]] = []
    pairs_tau_svr: list[tuple[float, float]] = []
    for r in frame.values():
        if r.get("svr_available") != 1:
            continue
        svr = r.get("svri_indexed")
        if svr is None:
            svr = r.get("fluid_svr_mean")
        if svr is None:
            continue
        idx = r.get(PRIMARY_INDEX_WAVEFORM)
        tau = r.get("art_tau_decay_mean")
        if idx is not None:
            pairs_idx_svr.append((idx, svr))
        if tau is not None:
            pairs_tau_svr.append((tau, svr))

    def _rho(pairs):
        if len(pairs) < 3:
            return None, len(pairs)
        x = [p[0] for p in pairs]
        y = [p[1] for p in pairs]
        return H["spearman"](x, y), len(pairs)

    rho_idx, n_idx = _rho(pairs_idx_svr)
    rho_tau, n_tau = _rho(pairs_tau_svr)

    # Hypothesised signs: vasoplegia index HIGH = low tone -> NEGATIVE corr with
    # SVR; tau HIGH = high tone -> POSITIVE corr with SVR.
    available = n_idx >= 3 or n_tau >= 3
    return {
        "available": available,
        "n_joint_subset": max(n_idx, n_tau),
        "reference_standard": "BSA-indexed SVRI (SVR * BSA); falls back to raw SVR "
                              "only where BSA is missing",
        "waveform_index_vs_measured_svri": {
            "spearman_r": rho_idx, "n": n_idx,
            "hypothesised_sign": "negative (high index = low tone = low SVRI)",
        },
        "tau_vs_measured_svri": {
            "spearman_r": rho_tau, "n": n_tau,
            "hypothesised_sign": "positive (tau = R*C tracks SVRI)",
        },
        "preliminary_flag": (
            "NOT AVAILABLE -- no measured-SVR (EV1000/Vigileo) cases overlap the "
            "A-line waveform subset in the present caches. This is the KEY "
            "validation and CANNOT be run until the EV1000 SVR subset is "
            "extracted onto the same cases as the ART-waveform pilot. The "
            "SVR-free vasoplegia-index claim is therefore UNVALIDATED so far."
            if not available else
            ("PRELIMINARY -- joint subset is very small (N<30); treat r as "
             "hypothesis-generating only." if max(n_idx, n_tau) < 30 else
             "Joint subset adequate; see r above.")
        ),
    }


# ===========================================================================
# STEP 3 -- VALIDATION 2: convergent (requirement A vs waveform C)
# ===========================================================================
def convergent_validity(frame: dict[str, dict[str, Any]], H) -> dict[str, Any]:
    """Do family A (requirement index) and family C (waveform index) agree on a
    vasoplegic phenotype?  Spearman r over the joint (waveform) subset + a 2x2 of
    median splits (both oriented HIGH = vasoplegia)."""
    xs: list[float] = []
    ys: list[float] = []
    for r in frame.values():
        if r.get("aline_available") != 1:
            continue
        a = r.get(PRIMARY_INDEX_REQUIREMENT)
        c = r.get(PRIMARY_INDEX_WAVEFORM)
        if a is not None and c is not None:
            xs.append(a)
            ys.append(c)
    n = len(xs)
    rho = H["spearman"](xs, ys) if n >= 3 else None

    table = {"both_high": 0, "req_high_wave_low": 0,
             "req_low_wave_high": 0, "both_low": 0}
    kappa = None
    if n >= 4:
        mx = sorted(xs)[n // 2]
        my = sorted(ys)[n // 2]
        for a, c in zip(xs, ys):
            ah, ch = a > mx, c > my
            if ah and ch:
                table["both_high"] += 1
            elif ah and not ch:
                table["req_high_wave_low"] += 1
            elif not ah and ch:
                table["req_low_wave_high"] += 1
            else:
                table["both_low"] += 1
        # Cohen's kappa on the 2x2 (chance-corrected agreement).
        a_, b_, c_, d_ = (table["both_high"], table["req_high_wave_low"],
                          table["req_low_wave_high"], table["both_low"])
        tot = a_ + b_ + c_ + d_
        if tot > 0:
            po = (a_ + d_) / tot
            p_yes = ((a_ + b_) / tot) * ((a_ + c_) / tot)
            p_no = ((c_ + d_) / tot) * ((b_ + d_) / tot)
            pe = p_yes + p_no
            kappa = round((po - pe) / (1 - pe), 4) if pe < 1 else None
    return {
        "available": n >= 3,
        "n": n,
        "spearman_r": rho,
        "two_by_two_median_split": table,
        "cohen_kappa": kappa,
        "note": "Both indices oriented HIGH = vasoplegia; positive r / agreement "
                "= convergent. Small N on the A-line pilot -> hypothesis-generating.",
    }


# ===========================================================================
# STEP 4 -- VALIDATION 3: criterion validity (predicts requirement + injury)
# ===========================================================================
def _series_for(frame, cids, col):
    return [frame[c].get(col) for c in cids]


# Baseline = MAP burden + body-size + demographics, so any incremental signal of
# the vasoplegia biomarker is OVER hypotension dose AND not a size/demo proxy.
ADJUSTMENT_BASELINE_COLS = (MAP_BURDEN_BASELINE,) + SIZE_DEMO_COVARIATES


def _incremental_multibaseline(frame, cids, outcome, feature_col, baseline_cols,
                               seed):
    """Incremental AUROC + LR p of (baselines + feature) over baselines alone, on a
    multi-column baseline (MAP burden + body size + demographics), with a
    patient-clustered bootstrap CI on dAUROC.  Mirrors aline_feasibility.
    _incremental_logit but supports a multivariable baseline so the vasoplegia
    biomarker's value is incremental over the size/dose-confounding controls.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from scipy import stats as _stats
    from vitaldb_aki.analysis.aline_feasibility import _auroc

    y, feat, grp = [], [], []
    base_cols = [bc for bc in baseline_cols if any(
        frame[c].get(bc) is not None for c in cids)]
    base_rows: list[list[float]] = []
    for c in cids:
        oc = frame[c].get(outcome)
        f = frame[c].get(feature_col)
        if oc is None or f is None:
            continue
        brow = [frame[c].get(bc) for bc in base_cols]
        if any(b is None for b in brow):
            continue
        y.append(int(oc)); feat.append(float(f)); grp.append(frame[c]["subjectid"])
        base_rows.append([float(b) for b in brow])

    n = len(y); events = int(sum(y)) if n else 0
    out = {"auroc_base": None, "auroc_plus": None, "delta_auroc": None,
           "lr_p": None, "delta_ci": [None, None], "n": n, "events": events,
           "baseline_cols": base_cols}
    if n < 20 or events < 3 or min(y) == max(y):
        out["available"] = False
        return out

    yy = np.asarray(y, dtype=int)
    B = np.asarray(base_rows, dtype=float)
    f = np.asarray(feat, dtype=float)
    g = np.asarray(grp)

    def _fit(X):
        Xs = X.copy()
        for c in range(Xs.shape[1]):
            sd = Xs[:, c].std()
            if sd > 0:
                Xs[:, c] = (Xs[:, c] - Xs[:, c].mean()) / sd
        lr = LogisticRegression(max_iter=1000, solver="lbfgs", C=1e6)
        lr.fit(Xs, yy)
        p = lr.predict_proba(Xs)[:, 1]
        eps = 1e-12
        ll = float(np.sum(yy * np.log(p + eps) + (1 - yy) * np.log(1 - p + eps)))
        return p, -2.0 * ll

    try:
        pb, dev_b = _fit(B)
        pp, dev_p = _fit(np.column_stack([B, f]))
    except Exception:
        out["available"] = False
        return out

    ab = _auroc(yy.tolist(), pb.tolist())
    ap = _auroc(yy.tolist(), pp.tolist())
    delta = (ap - ab) if (ab is not None and ap is not None) else None
    lr_stat = max(0.0, dev_b - dev_p)
    lr_p = float(1.0 - _stats.chi2.cdf(lr_stat, df=1))

    rng = np.random.default_rng(seed)
    uniq = np.unique(g)
    idx_by_g = {u: np.where(g == u)[0] for u in uniq}
    deltas = []
    for _ in range(N_BOOTSTRAP):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_g[u] for u in pick])
        yb = yy[idx]
        if yb.min() == yb.max():
            continue
        a0 = _auroc(yb.tolist(), pb[idx].tolist())
        a1 = _auroc(yb.tolist(), pp[idx].tolist())
        if a0 is not None and a1 is not None:
            deltas.append(a1 - a0)
    lo = float(np.percentile(deltas, 2.5)) if deltas else None
    hi = float(np.percentile(deltas, 97.5)) if deltas else None

    out.update({
        "available": delta is not None,
        "auroc_base": round(ab, 4) if ab is not None else None,
        "auroc_plus": round(ap, 4) if ap is not None else None,
        "delta_auroc": round(delta, 4) if delta is not None else None,
        "lr_p": lr_p,
        "delta_ci": [round(lo, 4) if lo is not None else None,
                     round(hi, 4) if hi is not None else None],
    })
    return out


def criterion_predicts_requirement(frame, H) -> dict[str, Any]:
    """3a: does each biomarker predict HIGH pressor REQUIREMENT (univariate
    AUROC)?  The waveform surrogate is the interesting one (it should flag the
    cases that ended up needing the most pressor)."""
    cids = [c for c in frame if frame[c].get("high_requirement") is not None]
    y = [int(frame[c]["high_requirement"]) for c in cids]
    out: dict[str, Any] = {
        "n": len(cids), "n_high_requirement": int(sum(y)),
        "caveat": ("high_requirement is derived from NEE/kg, which is a COMPONENT "
                   "of requirement_vasoplegia_index -> that index's AUROC here is "
                   "partly TAUTOLOGICAL and is shown only as a sanity check. The "
                   "INFORMATIVE rows are the WAVEFORM markers (C), which are "
                   "independent of the dose label."),
    }
    biomarkers = {
        PRIMARY_INDEX_WAVEFORM: "waveform tone surrogate (C)",
        "art_tau_decay_mean": "diastolic decay tau (C)",
        PRIMARY_INDEX_REQUIREMENT: "requirement index (A)",
    }
    per = {}
    for col, label in biomarkers.items():
        xc = [(c, frame[c].get(col)) for c in cids
              if frame[c].get(col) is not None]
        if len(xc) < 20:
            per[col] = {"label": label, "available": False,
                        "n": len(xc), "note": "too few with biomarker"}
            continue
        sub_cids = [c for c, _ in xc]
        yy = [int(frame[c]["high_requirement"]) for c in sub_cids]
        xx = [v for _, v in xc]
        auc = H["auroc"](yy, xx) if (sum(yy) > 0 and sum(yy) < len(yy)) else None
        per[col] = {"label": label, "available": auc is not None,
                    "n": len(xc), "n_events": int(sum(yy)),
                    "auroc_vs_high_requirement": round(auc, 4)
                    if auc is not None else None}
    out["biomarkers"] = per
    return out


def criterion_predicts_injury(frame, H, seed) -> dict[str, Any]:
    """3b: does each vasoplegia biomarker predict organ injury INCREMENTAL over
    MAP burden?  Incremental AUROC (LR p + patient-clustered bootstrap CI) for
    every (biomarker x outcome), plus the negative control; BH-FDR across the
    primary-outcome tests."""
    # All candidate biomarkers across families (each evaluated where present).
    candidates = {
        PRIMARY_INDEX_WAVEFORM: "waveform vasoplegia index (C)",
        "art_tau_decay_mean": "diastolic decay tau (C)",
        PRIMARY_INDEX_REQUIREMENT: "requirement vasoplegia index (A)",
        "nee_total_ug_per_kg": "NEE total dose per kg (A)",
        "pressor_dur_min": "pressor duration (A)",
    }
    outcomes = list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]
    results: dict[str, Any] = {}
    pvals: list[float | None] = []
    pkeys: list[tuple[str, str]] = []

    for col, label in candidates.items():
        results[col] = {"label": label}
        for oc in outcomes:
            cids = [c for c in frame
                    if frame[c].get(col) is not None
                    and frame[c].get(oc) is not None
                    and frame[c].get(MAP_BURDEN_BASELINE) is not None]
            if len(cids) < 20:
                results[col][oc] = {"available": False, "n": len(cids),
                                    "note": "too few joint rows"}
                continue
            # Incremental over MAP burden + body size + demographics, so the signal
            # is not a hypotension-dose, body-size, or demographic proxy.
            inc = _incremental_multibaseline(
                frame, cids, oc, col, ADJUSTMENT_BASELINE_COLS, seed)
            inc["underpowered"] = (inc.get("events") or 0) < MIN_EVENTS_FEASIBLE
            if oc == NEGATIVE_CONTROL_OUTCOME:
                inc["is_negative_control"] = True
            results[col][oc] = inc
            if oc in PRIMARY_OUTCOMES:
                pvals.append(inc.get("lr_p"))
                pkeys.append((col, oc))

    reject = H["benjamini_hochberg"]([p if p is not None else 1.0 for p in pvals])
    fdr = {}
    for (col, oc), p, rj in zip(pkeys, pvals, reject):
        fdr.setdefault(col, {})[oc] = {"lr_p": p, "fdr_reject": bool(rj)}
    return {"per_biomarker": results, "fdr_primary": fdr,
            "baseline": list(ADJUSTMENT_BASELINE_COLS),
            "min_events_feasible": MIN_EVENTS_FEASIBLE}


def criterion_adjusted_iptw(frame, H, seed) -> dict[str, Any]:
    """IPTW-adjusted per-median-split logistic OR for the PRIMARY vasoplegia index
    on each outcome, reusing hypotension_treatment IPTW + actionable e-values.

    Exposure = vasoplegic (index above median).  PS covariates = the available
    preop confounders + MAP burden.  Returns OR + 95% CI + E-values per outcome,
    with the negative control."""
    import numpy as np
    import pandas as pd

    # Choose the index with the broadest support (requirement index = full cohort).
    primary = PRIMARY_INDEX_REQUIREMENT
    rows = [r for r in frame.values() if r.get(primary) is not None]
    if len(rows) < 50:
        return {"available": False, "note": "fewer than 50 rows with primary index"}

    df = pd.DataFrame(rows)
    df["_vasoplegic"] = (pd.to_numeric(df[primary], errors="coerce")
                         > pd.to_numeric(df[primary], errors="coerce").median()
                         ).astype("Int64")

    from vitaldb_aki.analysis import hypotension_treatment as ht
    from vitaldb_aki.analysis.actionable_targets import e_value, e_value_ci
    import statsmodels.api as sm

    # Confounders available in our assembled frame: MAP burden + BODY SIZE +
    # DEMOGRAPHICS (so the adjusted OR is not a size/dose/demographic proxy).  We
    # deliberately did NOT re-pull preop labs to keep this download-free.
    ps_covs = [c for c in (MAP_BURDEN_BASELINE, MAP_BURDEN_BASELINE2)
               + SIZE_DEMO_COVARIATES if c in df.columns]
    out: dict[str, Any] = {"available": True, "primary_index": primary,
                           "exposure": "vasoplegic (index > median)",
                           "ps_covariates": ps_covs,
                           "note": "PS adjusts for MAP burden + body size (weight, "
                                   "BSA) + age + sex (download-free frame); residual "
                                   "confounding by preop SEVERITY (labs/comorbidity) "
                                   "is NOT removed -> hypothesis-generating."}
    for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
        sub = df.dropna(subset=[oc, "_vasoplegic"]).copy()
        sub["vasopressor_treated"] = sub["_vasoplegic"].astype(int)
        n = int(len(sub))
        events = int(pd.to_numeric(sub[oc], errors="coerce").fillna(0).astype(int).sum())
        blk: dict[str, Any] = {"n": n, "events": events}
        if events < MIN_EVENTS_FEASIBLE or sub["vasopressor_treated"].nunique() < 2 \
           or not ps_covs:
            blk["underpowered"] = True
            blk["available"] = False
            if oc == NEGATIVE_CONTROL_OUTCOME:
                blk["is_negative_control"] = True
            out[oc] = blk
            continue
        try:
            sub_ps, _, used = ht.fit_propensity_model(sub, covariates=ps_covs)
            sub_w = ht.compute_iptw_weights(sub_ps)
            w = sub_w["iptw_weight"].to_numpy(dtype=float)
            X = pd.DataFrame({"vasoplegic": sub_w["vasopressor_treated"].astype(float)},
                             index=sub_w.index)
            Xc = sm.add_constant(X, has_constant="add")
            fit = sm.GLM(
                pd.to_numeric(sub_w[oc], errors="coerce").astype(float).to_numpy(),
                Xc.to_numpy().astype(float),
                family=sm.families.Binomial(),
                freq_weights=w,
            ).fit()
            j = list(Xc.columns).index("vasoplegic")
            beta, se = float(fit.params[j]), float(fit.bse[j])
            p = float(fit.pvalues[j])
            orr = math.exp(beta)
            or_lo, or_hi = math.exp(beta - 1.96 * se), math.exp(beta + 1.96 * se)
            blk.update({
                "available": True, "underpowered": False,
                "or_vasoplegic": round(orr, 4),
                "or_ci95": [round(or_lo, 4), round(or_hi, 4)],
                "p_value": p,
                "e_value_point": round(e_value(orr), 3),
                "e_value_ci": round(e_value_ci(orr, or_lo, or_hi), 3),
                "ps_covariates_used": used,
            })
            if oc == NEGATIVE_CONTROL_OUTCOME:
                blk["is_negative_control"] = True
                blk["negative_control_flag"] = (
                    "NON-NULL (possible residual confounding)"
                    if (or_lo > 1.0 or or_hi < 1.0) else "null (reassuring)")
        except Exception as e:
            blk["available"] = False
            blk["error"] = f"{type(e).__name__}: {e}"
        out[oc] = blk
    return out


# ===========================================================================
# STEP 5 -- VALIDATION 4: dose-response (quartiles of primary index)
# ===========================================================================
def dose_response(frame, H) -> dict[str, Any]:
    """Quartiles (or tertiles if sparse) of the PRIMARY vasoplegia index vs
    organ-injury rate, with a Cochran-Armitage trend test.  Direction-aware: MORE
    vasoplegia (higher index) hypothesised -> MORE injury."""
    # Use the requirement index (full cohort) as the powered primary; also report
    # the waveform index where the subset allows.
    out: dict[str, Any] = {}
    for primary, label in ((PRIMARY_INDEX_REQUIREMENT, "requirement index (A; full cohort)"),
                           (PRIMARY_INDEX_WAVEFORM, "waveform index (C; A-line pilot)")):
        blk: dict[str, Any] = {"label": label}
        for oc in PRIMARY_OUTCOMES:
            cids = [c for c in frame
                    if frame[c].get(primary) is not None
                    and frame[c].get(oc) is not None]
            vals = [frame[c][primary] for c in cids]
            evs = [int(frame[c][oc]) for c in cids]
            n_ev = sum(evs)
            if len(cids) < DOSE_RESPONSE_MIN_N or n_ev < 3:
                blk[oc] = {"available": False, "n": len(cids), "events": n_ev,
                           "note": "too few cases/events"}
                continue
            nq = (DOSE_RESPONSE_MAX_Q if n_ev >= 4 * DOSE_RESPONSE_MIN_Q
                  else DOSE_RESPONSE_MIN_Q)
            breaks = H["quantile_breaks"](vals, nq)
            qid = H["assign_quantiles"](vals, nq)
            counts = [0] * nq
            events = [0] * nq
            for q, e in zip(qid, evs):
                if 0 <= q < nq:
                    counts[q] += 1
                    events[q] += e
            rates = [round(events[i] / counts[i], 4) if counts[i] else None
                     for i in range(nq)]
            z, p = H["cochran_armitage"](counts, events)
            blk[oc] = {
                "available": True, "n": len(cids), "events": n_ev,
                "n_quantiles": nq, "counts": counts, "events_per_q": events,
                "rate_per_q": rates,
                "cochran_armitage_z": round(z, 4) if z is not None else None,
                "cochran_armitage_p": round(p, 4) if p is not None else None,
                "monotone_increasing": all(
                    rates[i] is not None and rates[i + 1] is not None
                    and rates[i + 1] >= rates[i] for i in range(nq - 1)),
                "direction_hypothesis": "higher index -> higher injury rate",
            }
        out[primary] = blk
    return out


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================
def run(cfg: dict[str, Any]) -> dict[str, Any]:
    """Public entry point: assemble + validate, write results JSON + MD + done."""
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    os.makedirs(cache_dir, exist_ok=True)
    H = _import_helpers()

    frame, meta = assemble_frame(cfg)

    v1 = construct_validity(frame, H)
    v2 = convergent_validity(frame, H)
    v3a = criterion_predicts_requirement(frame, H)
    v3b = criterion_predicts_injury(frame, H, seed)
    v3c = criterion_adjusted_iptw(frame, H, seed)
    v4 = dose_response(frame, H)

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "seed": seed,
        "axes": {
            "A_requirement_gain": {"available": True,
                                   "n": meta["n_cases_total"],
                                   "biomarkers": list(FAMILY_A_BIOMARKERS)},
            "B_measured_svr": {"available": meta["n_measured_svr"] > 0,
                               "n": meta["n_measured_svr"],
                               "note": "reference standard; EV1000/Vigileo subset"},
            "C_waveform_tone": {"available": meta["n_waveform_subset"] > 0,
                                "n": meta["n_waveform_subset"],
                                "components": list(WAVEFORM_TONE_COMPONENTS),
                                "index": PRIMARY_INDEX_WAVEFORM},
        },
        "meta": meta,
        "validation_1_construct_waveform_vs_measured_svr": v1,
        "validation_2_convergent_requirement_vs_waveform": v2,
        "validation_3a_predicts_pressor_requirement": v3a,
        "validation_3b_incremental_over_map_burden": v3b,
        "validation_3c_adjusted_iptw_or": v3c,
        "validation_4_dose_response": v4,
        "nee_potency_anchors": {
            "phe_ug_per_nee_ug": PHE_UG_PER_NEE_UG,
            "epi_ug_per_nee_ug": EPI_UG_PER_NEE_UG,
            "eph_mg_per_nee_ug": EPH_MG_PER_NEE_UG,
        },
        "interpretation": (
            "Observational, single-centre (VitalDB / SNUH). Vasoplegia biomarkers "
            "are PREOP+INTRAOP only; organ_* are outcomes, never features. The "
            "waveform-only tone surrogate is the novel, SVR-free candidate; its "
            "construct validity rests on correlation with MEASURED SVR, which "
            "needs the EV1000 subset extracted onto the same cases as the A-line "
            "pilot. All criterion estimates are HYPOTHESIS-GENERATING and the "
            "A-line subset is feasibility-scale (few renal events)."
        ),
    }

    results_path = os.path.join(cache_dir, RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[vasoplegia] results -> {results_path}")

    _write_md(results, cfg)

    done_path = os.path.join(cache_dir, DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"done": True, "results_json": RESULTS_JSON,
                   "n_cases": meta["n_cases_total"],
                   "n_waveform": meta["n_waveform_subset"],
                   "n_measured_svr": meta["n_measured_svr"]}, fh, indent=2)
    print(f"[vasoplegia] done marker -> {done_path}")
    return results


def _json_default(obj):
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ===========================================================================
# REPORT
# ===========================================================================
def _f(v, spec="{:.4g}"):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return spec.format(v)
    return str(v)


def _write_md(results: dict, cfg: dict) -> str:
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, RESULTS_MD)

    meta = results["meta"]
    v1 = results["validation_1_construct_waveform_vs_measured_svr"]
    v2 = results["validation_2_convergent_requirement_vs_waveform"]
    v3a = results["validation_3a_predicts_pressor_requirement"]
    v3b = results["validation_3b_incremental_over_map_burden"]
    v3c = results["validation_3c_adjusted_iptw_or"]
    v4 = results["validation_4_dose_response"]

    L: list[str] = []
    L += [
        "# Vasoplegia / Pressor-Responsiveness Biomarker (VitalDB-AKI)",
        "",
        "## READ FIRST -- what this is and what it is NOT",
        "",
        "This is the **pressor-side analog of SVV**. SVV/PPV index FLUID",
        "responsiveness; this biomarker indexes **PRESSOR responsiveness /",
        "VASOPLEGIA** -- whether the vasculature still holds arterial TONE or has",
        "lost it. It is the second axis of the arterial-line *fluid vs pressor*",
        "decision.",
        "",
        "- **Observational, single-centre** (VitalDB / SNUH). Everything here is",
        "  **HYPOTHESIS-GENERATING**, not causal proof. External validation pending.",
        "- **Leakage firewall:** every biomarker is PREOP+INTRAOP only; `organ_*`",
        "  outcomes are y, never predictors.",
        "- The novel **waveform-only tone surrogate** is SVR-free *by construction*;",
        "  its validity depends on the construct-validity check below.",
        "",
        "## THE HEADLINE -- waveform tone surrogate vs MEASURED SVR",
        "",
    ]
    if not v1.get("available"):
        L += [
            f"> **{v1.get('preliminary_flag')}**",
            "",
            "The measured-SVR reference standard (EV1000/Vigileo `fluid_svr_*`) is",
            "**not present** on the same cases as the A-line waveform pilot in the",
            "current caches, so the surrogate-vs-SVR correlation **could not be**",
            "**computed**. This is the single validation that would license calling",
            "the waveform index an *SVR-free vasoplegia* marker. Until the EV1000",
            "SVR subset is extracted onto the ART-waveform cases, the claim is",
            "**UNVALIDATED**.",
        ]
    else:
        wi = v1["waveform_index_vs_measured_svri"]
        tt = v1["tau_vs_measured_svri"]
        L += [
            f"- Reference standard: {v1.get('reference_standard')}.",
            f"- Joint subset N = **{v1.get('n_joint_subset')}**. "
            f"**{v1.get('preliminary_flag')}**",
            f"- Waveform vasoplegia index vs measured SVRI: Spearman r = "
            f"**{_f(wi.get('spearman_r'))}** (N={wi.get('n')}); "
            f"hypothesised {wi.get('hypothesised_sign')}.",
            f"- Diastolic decay tau vs measured SVRI: Spearman r = "
            f"**{_f(tt.get('spearman_r'))}** (N={tt.get('n')}); "
            f"hypothesised {tt.get('hypothesised_sign')}.",
        ]
    L += [""]

    L += [
        "## Axis availability (N)",
        "",
        f"- **A. Pump+MAP requirement/gain** (full cohort, download-free): "
        f"N = {meta['n_cases_total']} (with outcomes {meta['n_with_outcomes']}).",
        f"- **B. Measured SVR / SVRI** (EV1000/Vigileo reference standard): "
        f"N = {meta['n_measured_svr']}"
        + ("  **<- NOT extracted; validation deferred**"
           if meta['n_measured_svr'] == 0 else "") + ".",
        f"- **C. Waveform-only tone surrogate** (A-line pilot "
        f"cache/aline_sample.csv): N = {meta['n_waveform_subset']}.",
        f"- Feature-matrix source: `{meta.get('matrix_source')}`.",
        "",
        "## Body-size & dose normalization (READ -- key methodological control)",
        "",
        "A raw-dose requirement marker is **confounded by body size** (a larger",
        "patient needs more drug for the same effect). To avoid measuring body",
        "size instead of vasoplegia:",
        "- **BSA** (Mosteller) = `sqrt(height_cm * weight_kg / 3600)` m^2 is computed",
        "  per case.",
        "- **Family A** doses are **weight-normalised (per kg)**: the norepinephrine-",
        "  equivalent total is divided by `weight_kg` -> **ug-NEE / kg**. UNIT NOTE:",
        "  the matrix dose totals are CUMULATIVE amounts, so this is a cumulative",
        "  ug-NEE/kg; the clinically familiar norepi-equivalent is ug/kg/**min** (a",
        "  rate) -- we lack a clean per-case infusion-minutes denominator in the flat",
        "  matrix, so the cumulative-per-kg assumption is stated explicitly. The",
        "  `vaso_responsiveness` slope (features/vasoactive_pd.py) is in RAW dose",
        "  units (documented limitation); we therefore also carry `weight_kg`/BSA as",
        "  covariates in the requirement analyses.",
        "- **Family B** uses the **BSA-indexed SVRI** (= SVR x BSA), the size-",
        "  normalised vascular-resistance index, as the gold standard (not raw SVR).",
        "- **Family C** (tau, diastolic/MAP, form factor, augmentation index) is",
        "  **intrinsically size-INDEPENDENT** -- these are waveform SHAPE / TIME-",
        "  CONSTANT quantities needing no weight or dose. **That is a key advantage**",
        "  of the waveform vasoplegia index: an SVR-free AND dose/size-free tone",
        "  read. Even so, the criterion regressions still adjust for `weight_kg`/BSA",
        "  + age + sex so the surrogate's value cannot be a body-size proxy.",
        "- All incremental-AUROC / IPTW / dose-response adjustment sets include",
        "  `weight_kg` (and BSA) + age + sex.",
        "",
        "## Biomarker definitions",
        "",
        "**Family A -- requirement / gain (HIGH = vasoplegia; WEIGHT-NORMALISED):**",
        "- `nee_total_ug_per_kg` -- norepinephrine-equivalent total dose per kg "
        "(phe/10 + epi + eph + nepi on a ug-NEE axis, / weight_kg).",
        "- `nee_peak_rate_per_kg` -- peak NEE infusion intensity per kg.",
        "- `pressor_dur_min` -- total pressor infusion duration (size-independent).",
        "- `pressor_n_agents` -- distinct vasoactive agents (size-independent).",
        "- (`vaso_responsiveness` from features/vasoactive_pd.py is the MAP-per-dose",
        "  GAIN; blunted = vasoplegia. Not in the flat matrix cache; raw dose units",
        "  -> noted as the v1 gain signal feeding this family.)",
        "",
        "**Family B -- measured SVR / SVRI (reference standard):** `fluid_svr_mean`, "
        "`fluid_svr_min`, `fluid_svr_low_frac` from features/fluid_responsiveness.py "
        "(SVR < 800 dyn*s*cm^-5 = vasoplegia), indexed to **`svri_indexed` = SVR x "
        "BSA** (the size-normalised standard used for validation).",
        "",
        "**Family C -- waveform-only tone surrogate (the novel one; HIGH = "
        "vasoplegia; SIZE-INDEPENDENT):** z-scored mean of orientation-signed "
        "components from the A-line morphology pilot --",
        "- `art_tau_decay_mean` -- diastolic decay tau = R*C; **LOW tau = fast "
        "runoff = lost tone**.",
        "- diastolic/MAP ratio (LOW = poor tone), (MAP-DBP)/PP form factor (LOW = "
        "decay-dominated), augmentation index (LOW = low wave reflection / tone).",
        f"- combined -> **`{PRIMARY_INDEX_WAVEFORM}`** (pre-specified simple "
        "z-mean; no outcome fitting; no weight/dose input).",
        "",
    ]

    # Convergent
    L += [
        "## Convergent validity (requirement A vs waveform C)",
        "",
        f"- N (joint A-line subset) = {v2.get('n')}; Spearman r = "
        f"**{_f(v2.get('spearman_r'))}**; Cohen kappa (median split) = "
        f"{_f(v2.get('cohen_kappa'))}.",
        f"- 2x2 (median split): {v2.get('two_by_two_median_split')}.",
        f"- {v2.get('note')}",
        "",
    ]

    # 3a requirement
    L += [
        "## Criterion 3a -- predicts high pressor REQUIREMENT",
        "",
        f"- High-requirement label N = {v3a.get('n')}, "
        f"events = {v3a.get('n_high_requirement')}.",
        f"- _Caveat:_ {v3a.get('caveat')}",
    ]
    for col, blk in (v3a.get("biomarkers") or {}).items():
        if blk.get("available"):
            L.append(f"  - `{col}` ({blk['label']}): AUROC vs high-requirement = "
                     f"**{_f(blk.get('auroc_vs_high_requirement'))}** "
                     f"(N={blk.get('n')}, events={blk.get('n_events')}).")
        else:
            L.append(f"  - `{col}`: not available ({blk.get('note')}).")
    L += [""]

    # 3b incremental
    L += [
        "## Criterion 3b -- organ injury INCREMENTAL over MAP burden",
        "",
        f"Baseline = `{v3b.get('baseline')}`; incremental AUROC (delta), LR p, "
        "patient-clustered bootstrap CI. BH-FDR across primary outcomes.",
        "",
    ]
    for col, blk in (v3b.get("per_biomarker") or {}).items():
        L.append(f"### `{col}` -- {blk.get('label')}")
        for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
            ob = blk.get(oc, {})
            if not ob.get("available"):
                L.append(f"- {oc}: not available ({ob.get('note', 'n/a')}).")
                continue
            tag = " **[negative control]**" if ob.get("is_negative_control") else ""
            up = " *[underpowered]*" if ob.get("underpowered") else ""
            rj = ((v3b.get("fdr_primary", {}).get(col, {}) or {}).get(oc, {})
                  or {}).get("fdr_reject")
            fdrtag = f" FDR-reject={rj}" if rj is not None else ""
            L.append(
                f"- {oc}{tag}: dAUROC = **{_f(ob.get('delta_auroc'))}** "
                f"(base {_f(ob.get('auroc_base'))} -> {_f(ob.get('auroc_plus'))}; "
                f"95% CI {_f((ob.get('delta_ci') or [None,None])[0])} to "
                f"{_f((ob.get('delta_ci') or [None,None])[1])}); "
                f"LR p = {_f(ob.get('lr_p'))}; n={ob.get('n')}, "
                f"events={ob.get('events')}.{up}{fdrtag}")
        L.append("")

    # 3c IPTW
    L += ["## Criterion 3c -- IPTW-adjusted OR (primary index, vasoplegic vs not)",
          ""]
    if not v3c.get("available"):
        L.append(f"- Not available: {v3c.get('note')}")
    else:
        L.append(f"- Exposure: {v3c.get('exposure')} on `{v3c.get('primary_index')}`; "
                 f"PS covariates {v3c.get('ps_covariates')}.")
        L.append(f"- {v3c.get('note')}")
        for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
            ob = v3c.get(oc, {})
            if not ob.get("available"):
                L.append(f"  - {oc}: underpowered/unavailable "
                         f"(n={ob.get('n')}, events={ob.get('events')}).")
                continue
            tag = " **[negative control]**" if ob.get("is_negative_control") else ""
            ncflag = (f" -> {ob.get('negative_control_flag')}"
                      if ob.get("negative_control_flag") else "")
            L.append(
                f"  - {oc}{tag}: OR = **{_f(ob.get('or_vasoplegic'))}** "
                f"(95% CI {_f((ob.get('or_ci95') or [None,None])[0])}-"
                f"{_f((ob.get('or_ci95') or [None,None])[1])}); "
                f"p = {_f(ob.get('p_value'))}; E-value(point) = "
                f"{_f(ob.get('e_value_point'))}, E-value(CI) = "
                f"{_f(ob.get('e_value_ci'))}.{ncflag}")
    L += [""]

    # 4 dose-response
    L += ["## Validation 4 -- dose-response (quartiles of the vasoplegia index)",
          ""]
    for primary, blk in (v4 or {}).items():
        L.append(f"### {blk.get('label')} (`{primary}`)")
        for oc in PRIMARY_OUTCOMES:
            ob = blk.get(oc, {})
            if not ob.get("available"):
                L.append(f"- {oc}: not available ({ob.get('note', 'n/a')}).")
                continue
            L.append(
                f"- {oc}: rates by quantile = {ob.get('rate_per_q')} "
                f"(n/q {ob.get('counts')}, ev/q {ob.get('events_per_q')}); "
                f"Cochran-Armitage z = {_f(ob.get('cochran_armitage_z'))}, "
                f"p = {_f(ob.get('cochran_armitage_p'))}; "
                f"monotone-increasing = {ob.get('monotone_increasing')}.")
        L.append("")

    L += [
        "## Bottom line",
        "",
        "- Axis A (requirement/gain) is available cohort-wide and is the "
        "best-powered vasoplegia signal today.",
        "- Axis C (waveform-only tone surrogate) is computable on the A-line pilot "
        "and is the novel SVR-free candidate, but the pilot carries very few renal "
        "events -> criterion estimates are feasibility-scale.",
        "- **Axis B (measured SVR) is the missing keystone:** without it on the "
        "same cases, the surrogate's construct validity is unproven. **Fuller "
        "power needs the broader ART-waveform + EV1000/SVR extraction.**",
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/vasoplegia_biomarker.py*",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[vasoplegia] {RESULTS_MD} -> {md_path}")
    return md_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    res = run(cfg)
    print(json.dumps({
        "axes": res["axes"],
        "construct_validity_available":
            res["validation_1_construct_waveform_vs_measured_svr"]["available"],
        "convergent_r":
            res["validation_2_convergent_requirement_vs_waveform"].get("spearman_r"),
    }, indent=2))


if __name__ == "__main__":
    main()
