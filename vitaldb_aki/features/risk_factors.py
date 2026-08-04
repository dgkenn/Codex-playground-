"""risk_factors.py -- Stage 2a supplement: AKI risk factors missing from tabular.py (Sec 7A/7B).

Sources and features added here (all fset="comprehensive", timing="preop" per protocol §7):

1. /labs time-stamped analytes not in /cases (preop window, dt < opend, most-recent value):
   - preop_crp    : C-reactive protein mg/dL (inflammation/infection; ~58% coverage)
   - preop_lactate: blood lactate mmol/L (hypoperfusion/shock; ~68%)
   - preop_chloride: serum chloride mEq/L (hyperchloremia context; ~91%)
   - preop_wbc    : white blood cell count 10^3/uL (infection marker; ~76%)
   - preop_hct    : hematocrit % (anemia; ~90%)
   - preop_gfr_lab: lab-reported eGFR mL/min/1.73m^2 (renal function; ~74%)

2. Derived comorbidity flags from /cases:
   - ckd_flag      : 1 if CKD-EPI eGFR<60 from baseline_cr/age/sex (100% computable).
   - liver_disease_flag: 1 if dx text contains cirrhosis/hepatic-failure/liver-cirrhosis/
                         hepatocellular-carcinoma/liver-failure keywords, OR preop_ast>80
                         or preop_alt>80 (2x upper normal ~40 U/L; ~7.4% flag positive).
                         AST/ALT >80 U/L threshold follows standard 2x-ULN convention.
   - cardiac_flag  : 1 if preop_ecg is anything other than 'Normal Sinus Rhythm' (all
                     arrhythmias, conduction blocks, pacemakers) OR dx contains
                     'heart failure'/'cardiomyopathy'/'congestive heart failure'. In this
                     cohort 'Normal Sinus Rhythm' covers 98.5% of ECGs; the 1.5% with
                     abnormal ECG (AF, BBB, pacemakers, AV block, ectopy) are flagged.
   - infection_flag: 1 if dx text contains infection/sepsis/abscess/peritonitis/
                     bacteremia/septic keywords (~1.1% from dx alone). Elevated CRP
                     (>5 mg/dL) alone is NOT sufficient to flag infection without WBC
                     because CRP is also elevated in cancer/inflammatory states; the dx-
                     based rule is the primary gate.

3. Surgical descriptors (§7B) from /cases:
   - is_open_surgery    : 1 if approach=='Open', 0 if Videoscopic or Robotic.
   - is_general_anesthesia: 1 if ane_type=='General', 0 otherwise (Spinal, Sedationalgesia).
   - position_risk      : ordinal encoding of surgical position by AKI-relevant
                          cardiovascular stress (Supine=0, Lithotomy=1, Trendelenburg=1,
                          LateralDecubitus=1, ReverseTrendelenburg=2, Prone=2,
                          Sitting=3, Kidney=3, Unknown=0). Higher score = greater
                          venous return/positional hypotension risk.
   - is_high_risk_surgery: 1 if optype in {'Hepatic','Vascular','Biliary/Pancreas',
                            'Major resection','Colorectal','Stomach','Transplantation'}.
                            These categories involve major abdominal, vascular, or
                            transplant-adjacent surgery with documented AKI risk.

All features are numeric (float or int) or None when the value cannot be derived.
Heavy deps are absent; only stdlib + vitaldb_aki.data.client (to_float) are used.
All labs are lazy-grouped once via `build_labs_index`; this runs the entire cohort
in seconds with no per-case network I/O.

Postop timing (dt >= opend) is NEVER used -- enforced by preop_lab() logic.
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.data.client import to_float
from vitaldb_aki.features.base import FeatureSpec, audit_specs
from vitaldb_aki.features.tabular import ckd_epi_2021  # reuse the validated CKD-EPI impl

# ---------------------------------------------------------------------------
# Feature specs
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # -- Labs from /labs not currently in /cases ----------------------------
    FeatureSpec("preop_crp",      "comprehensive", "preop", "C-reactive protein mg/dL (preop, most-recent)"),
    FeatureSpec("preop_lactate",  "comprehensive", "preop", "lactate mmol/L (preop, most-recent)"),
    FeatureSpec("preop_chloride", "comprehensive", "preop", "chloride mEq/L (preop, most-recent)"),
    FeatureSpec("preop_wbc",      "comprehensive", "preop", "WBC 10^3/uL (preop, most-recent)"),
    FeatureSpec("preop_hct",      "comprehensive", "preop", "hematocrit % (preop, most-recent)"),
    FeatureSpec("preop_gfr_lab",  "comprehensive", "preop", "lab-reported eGFR mL/min/1.73m^2 (preop)"),
    # -- Derived comorbidity flags ------------------------------------------
    FeatureSpec("ckd_flag",           "comprehensive", "preop", "1 if CKD-EPI eGFR<60 (recomputed)"),
    FeatureSpec("liver_disease_flag", "comprehensive", "preop",
                "1 if dx~cirrhosis/hepatic-failure/HCC OR AST>80 OR ALT>80"),
    FeatureSpec("cardiac_flag",       "comprehensive", "preop",
                "1 if ECG!=NormalSinusRhythm OR dx~heart-failure/cardiomyopathy"),
    FeatureSpec("infection_flag",     "comprehensive", "preop",
                "1 if dx~infection/sepsis/abscess/peritonitis/bacteremia"),
    # -- Surgical descriptors (§7B) ----------------------------------------
    FeatureSpec("is_open_surgery",       "comprehensive", "preop", "1=Open approach, 0=Videoscopic/Robotic"),
    FeatureSpec("is_general_anesthesia", "comprehensive", "preop", "1=General, 0=Spinal/Sedation"),
    FeatureSpec("position_risk",         "comprehensive", "preop",
                "ordinal positional cardiovascular stress 0-3 (Supine=0, Kidney/Sitting=3)"),
    FeatureSpec("is_high_risk_surgery",  "comprehensive", "preop",
                "1 if optype in {Hepatic,Vascular,Biliary/Pancreas,Major resection,"
                "Colorectal,Stomach,Transplantation}"),
]
audit_specs(SPECS)  # fail at import if any feature is timed after the prediction cutoff

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Preop window: most recent lab within WINDOW_S seconds before opend.
_DEFAULT_WINDOW_S: float = 30.0 * 86400.0  # 30 days

# Analyte names in /labs that we extract
_LAB_ANALYTES = frozenset(["crp", "lac", "cl", "wbc", "hct", "gfr"])

# Diagnosis-text keywords (lowercased) for each comorbidity flag.
_LIVER_KW = (
    "cirrhosis", "liver cirrhosis", "hepatic failure", "liver failure",
    "hepatocellular carcinoma", "liver donor",
)
_CARDIAC_KW = (
    "heart failure", "congestive heart failure", "cardiomyopathy", "cardiac failure",
)
_INFECTION_KW = (
    "infection", "sepsis", "septic", "abscess", "peritonitis", "bacteremia",
)

# ECG values that indicate abnormality (everything != Normal Sinus Rhythm)
_ECG_NORMAL = "Normal Sinus Rhythm"

# Surgical position -> AKI-relevant cardiovascular stress ordinal (0-3).
# Higher = greater venous-return disruption / positional hypotension risk.
_POSITION_RISK: dict[str, int] = {
    "Supine": 0,
    "Lithotomy": 1,
    "Trendelenburg": 1,
    "Left lateral decubitus": 1,
    "Right lateral decubitus": 1,
    "Reverse Trendelenburg": 2,
    "Prone": 2,
    "Left kidney": 3,
    "Right kidney": 3,
    "Sitting": 3,
}

# High-risk optype categories (abdominal/vascular/transplant-adjacent major surgery)
_HIGH_RISK_OPTYPES = frozenset({
    "Hepatic", "Vascular", "Biliary/Pancreas", "Major resection",
    "Colorectal", "Stomach", "Transplantation",
})


# ---------------------------------------------------------------------------
# Helper: build labs index (call once, pass to extract)
# ---------------------------------------------------------------------------

def build_labs_index(
    labs_rows: list[dict[str, Any]],
    analytes: frozenset[str] = _LAB_ANALYTES,
) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """Group raw /labs rows into {caseid: {analyte: [(dt_s, val), ...]}} sorted by dt.

    Only rows whose `name` is in `analytes` and whose `result` is numeric are kept.
    `dt` is seconds from casestart (negative = pre-casestart, i.e., definitely preop).
    The sort (ascending dt) lets preop_lab pick the most-recent value efficiently.
    """
    idx: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for row in labs_rows:
        name = row.get("name", "")
        if name not in analytes:
            continue
        cid = row.get("caseid", "")
        if not cid:
            continue
        try:
            dt = float(row["dt"])
            val = float(row["result"])
        except (KeyError, ValueError, TypeError):
            continue
        by_analyte = idx.setdefault(cid, {})
        by_analyte.setdefault(name, []).append((dt, val))
    # sort ascending so we can scan from the right for the most-recent preop value
    for by_analyte in idx.values():
        for lst in by_analyte.values():
            lst.sort(key=lambda x: x[0])
    return idx


def preop_lab(
    labs_by_case: dict[str, dict[str, list[tuple[float, float]]]],
    caseid: str,
    analyte: str,
    anchor_s: float,
    window_s: float = _DEFAULT_WINDOW_S,
) -> float | None:
    """Return the most-recent preop value of `analyte` for `caseid`.

    Preop means dt < anchor_s (anchor = opend, so intraop labs collected before end
    of surgery are included -- they are safe per §11; postop is dt >= anchor_s).
    The look-back window is anchor_s - window_s <= dt < anchor_s.

    Returns None if no qualifying value exists (honest missing; not imputed here).
    NEVER returns a value with dt >= anchor_s (leakage guard).
    """
    case_labs = labs_by_case.get(str(caseid))
    if case_labs is None:
        return None
    series = case_labs.get(analyte)
    if not series:
        return None
    lo = anchor_s - window_s
    # series is sorted ascending; scan right-to-left to find the most recent preop value
    for dt, val in reversed(series):
        if dt >= anchor_s:
            continue          # postop -- skip (leakage)
        if dt < lo:
            break             # too old -- past the look-back window
        return val            # most-recent qualifying value
    return None


# ---------------------------------------------------------------------------
# Comorbidity flag helpers (operate on a single /cases row dict)
# ---------------------------------------------------------------------------

def _ckd_flag(case: dict[str, Any]) -> int | None:
    """1 if CKD-EPI 2021 eGFR < 60, 0 if >= 60, None if not computable."""
    cr = to_float(case.get("preop_cr"))
    age = to_float(case.get("age"))
    sex_male = 1 if str(case.get("sex", "")).strip().upper().startswith("M") else 0
    egfr = ckd_epi_2021(cr, age, sex_male)
    if egfr is None:
        return None
    return 1 if egfr < 60.0 else 0


def _liver_flag(case: dict[str, Any]) -> int:
    """1 if diagnosis text or liver enzymes indicate liver disease.

    Rule (OR):
      (a) dx text (lowercased) contains any of: 'cirrhosis', 'liver cirrhosis',
          'hepatic failure', 'liver failure', 'hepatocellular carcinoma',
          'liver donor'.
      (b) preop_ast > 80 U/L  (2x upper normal ~40 U/L).
      (c) preop_alt > 80 U/L.

    dx is 100% present in this cohort so the flag is always derivable (defaults 0).
    """
    dx = str(case.get("dx", "")).lower()
    if any(kw in dx for kw in _LIVER_KW):
        return 1
    ast = to_float(case.get("preop_ast"))
    if ast is not None and ast > 80.0:
        return 1
    alt = to_float(case.get("preop_alt"))
    if alt is not None and alt > 80.0:
        return 1
    return 0


def _cardiac_flag(case: dict[str, Any]) -> int:
    """1 if ECG is abnormal or dx indicates heart failure / cardiomyopathy.

    Rule (OR):
      (a) preop_ecg != 'Normal Sinus Rhythm' (any arrhythmia, conduction block,
          pacemaker, or ectopy). In the cohort, 98.5% are NSR; the 1.5% flagged
          include AF, BBB, AV block, pacemakers, and premature complexes.
      (b) dx text (lowercased) contains: 'heart failure', 'congestive heart failure',
          'cardiomyopathy', 'cardiac failure'.

    preop_ecg is 100% present; dx is 100% present; flag is always derivable.
    """
    ecg = str(case.get("preop_ecg", "")).strip()
    if ecg and ecg != _ECG_NORMAL:
        return 1
    dx = str(case.get("dx", "")).lower()
    if any(kw in dx for kw in _CARDIAC_KW):
        return 1
    return 0


def _infection_flag(case: dict[str, Any]) -> int:
    """1 if diagnosis text suggests active infection or sepsis.

    Rule: dx text (lowercased) contains any of: 'infection', 'sepsis', 'septic',
    'abscess', 'peritonitis', 'bacteremia'.

    Note: CRP elevation alone is NOT used as a proxy because CRP is non-specific
    (cancer, autoimmune, post-op). The dx text is 100% present and is the
    primary gate; CRP elevation strengthens clinical suspicion but is not
    required by this binary flag (avoids false positives in cancer-heavy cohort).
    """
    dx = str(case.get("dx", "")).lower()
    if any(kw in dx for kw in _INFECTION_KW):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Surgical descriptor helpers
# ---------------------------------------------------------------------------

def _is_open(case: dict[str, Any]) -> int:
    """1 if approach is 'Open', 0 if Videoscopic or Robotic (or unknown)."""
    approach = str(case.get("approach", "")).strip()
    return 1 if approach == "Open" else 0


def _is_general(case: dict[str, Any]) -> int:
    """1 if ane_type is 'General', 0 for Spinal/Sedationalgesia/unknown."""
    return 1 if str(case.get("ane_type", "")).strip() == "General" else 0


def _position_risk(case: dict[str, Any]) -> int:
    """Ordinal cardiovascular stress score for surgical position (0–3).

    0 = Supine (lowest; balanced venous return).
    1 = Lithotomy, Trendelenburg, Lateral decubitus (moderate positional change).
    2 = Reverse Trendelenburg, Prone (greater cardiovascular stress).
    3 = Kidney position, Sitting (highest AKI-relevant hemodynamic disruption).

    Unknown/missing position returns 0 (conservative default; 89/3924 = 2.3% missing).
    """
    pos = str(case.get("position", "")).strip()
    return _POSITION_RISK.get(pos, 0)


def _is_high_risk(case: dict[str, Any]) -> int:
    """1 if optype is in the high-risk abdominal/vascular/transplant category.

    High-risk optypes: Hepatic, Vascular, Biliary/Pancreas, Major resection,
    Colorectal, Stomach, Transplantation. These involve major intra-abdominal,
    retroperitoneal, or large-vessel exposure with documented AKI risk in the
    literature (renal ischaemia, third-spacing, aortic cross-clamp, hepatorenal
    physiology). Covers ~72% of this cohort.
    """
    return 1 if str(case.get("optype", "")).strip() in _HIGH_RISK_OPTYPES else 0


# ---------------------------------------------------------------------------
# Main extract function
# ---------------------------------------------------------------------------

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
    labs_index: dict[str, dict[str, list[tuple[float, float]]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return {caseid: {feature_name: value|None}} for all risk-factor features.

    `labs_index` should be pre-built with `build_labs_index(fetch_labs(cfg))`.
    If omitted (e.g., in unit tests with synthetic data), lab features return None.

    All lab features use anchor = opend (seconds from casestart) from /cases,
    with a 30-day look-back. A value is preop iff dt < opend; no postop value
    (dt >= opend) is ever returned (§11 leakage prevention).
    """
    if labs_index is None:
        labs_index = {}

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        c = cases_by_id.get(str(cid))
        if c is None:
            continue

        # anchor for preop lab cut-off = opend (seconds from casestart)
        anchor = to_float(c.get("opend"))  # None for cases missing opend

        f: dict[str, Any] = {
            # -- /labs features (all None if labs_index absent or lab missing) --
            "preop_crp":      preop_lab(labs_index, cid, "crp",  anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            "preop_lactate":  preop_lab(labs_index, cid, "lac",  anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            "preop_chloride": preop_lab(labs_index, cid, "cl",   anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            "preop_wbc":      preop_lab(labs_index, cid, "wbc",  anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            "preop_hct":      preop_lab(labs_index, cid, "hct",  anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            "preop_gfr_lab":  preop_lab(labs_index, cid, "gfr",  anchor, _DEFAULT_WINDOW_S) if anchor is not None else None,
            # -- Comorbidity flags from /cases --------------------------------
            "ckd_flag":           _ckd_flag(c),
            "liver_disease_flag": _liver_flag(c),
            "cardiac_flag":       _cardiac_flag(c),
            "infection_flag":     _infection_flag(c),
            # -- Surgical descriptors from /cases ----------------------------
            "is_open_surgery":       _is_open(c),
            "is_general_anesthesia": _is_general(c),
            "position_risk":         _position_risk(c),
            "is_high_risk_surgery":  _is_high_risk(c),
        }
        out[str(cid)] = f
    return out
