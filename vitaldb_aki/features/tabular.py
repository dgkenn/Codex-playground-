"""tabular.py -- Stage 2a: preoperative + intraoperative-total features (Sec 7).

Everything here comes from the /cases table (no track downloads), so it runs in
seconds over the whole cohort. Covers Sec 7A (patient/renal), 7B (surgical), and
the cumulative-total parts of 7C/7D/7E (fluids, transfusion, EBL, drug totals).
The per-sample hypotension curve (Sec 7C area-under-MAP) lives in
features/hemodynamics.py; the pharmacokinetic layer (Sec 8) in features/pk.py.

Set membership (Sec 9 nested design):
  * "standard"      -- the parsimonious prior-work baseline (clinical + basics).
  * "comprehensive" -- the full Sec 7 taxonomy added on top.
The intraoperative *totals* (drug mg, fluid mL) are Comprehensive; their
pharmacokinetic refinements (effect-site Ce, exposure integrals) are +PK (Sec 8).

All timings are preop or intraop (<= end of surgery) -- never postop (Sec 11).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.data.client import to_float
from vitaldb_aki.features.base import FeatureSpec, audit_specs

# ----------------------------------------------------------------------------
# Feature specs (name, set, timing). Names match the keys emitted by extract().
# ----------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # -- Standard (prior-work baseline) --------------------------------------
    FeatureSpec("age", "standard", "preop", "years"),
    FeatureSpec("sex_male", "standard", "preop", "1=M 0=F"),
    FeatureSpec("bmi", "standard", "preop", "kg/m^2 (U-shaped risk)"),
    FeatureSpec("asa", "standard", "preop", "ASA physical status 1-5"),
    FeatureSpec("is_emergency", "standard", "preop", "emergency operation flag"),
    FeatureSpec("baseline_cr", "standard", "preop", "most-recent preop creatinine mg/dL"),
    FeatureSpec("egfr_ckdepi", "standard", "preop", "CKD-EPI 2021 race-free eGFR"),
    FeatureSpec("preop_htn", "standard", "preop", "hypertension flag"),
    FeatureSpec("preop_dm", "standard", "preop", "diabetes flag"),
    FeatureSpec("surgery_duration_min", "standard", "intraop", "opend-opstart minutes"),
    # -- Comprehensive: Sec 7A patient/renal labs ----------------------------
    FeatureSpec("height_cm", "comprehensive", "preop"),
    FeatureSpec("weight_kg", "comprehensive", "preop"),
    FeatureSpec("preop_hb", "comprehensive", "preop", "hemoglobin (anemia predictor)"),
    FeatureSpec("anemia_flag", "comprehensive", "preop", "Hb<13 M / <12 F"),
    FeatureSpec("preop_alb", "comprehensive", "preop", "albumin (hypoalbuminemia predictor)"),
    FeatureSpec("hypoalbuminemia_flag", "comprehensive", "preop", "albumin<3.5"),
    FeatureSpec("preop_plt", "comprehensive", "preop"),
    FeatureSpec("preop_pt", "comprehensive", "preop"),
    FeatureSpec("preop_aptt", "comprehensive", "preop"),
    FeatureSpec("preop_na", "comprehensive", "preop"),
    FeatureSpec("preop_k", "comprehensive", "preop"),
    FeatureSpec("preop_hco3", "comprehensive", "preop", "bicarbonate / acid-base"),
    FeatureSpec("preop_be", "comprehensive", "preop", "base excess"),
    FeatureSpec("preop_ph", "comprehensive", "preop"),
    FeatureSpec("preop_gluc", "comprehensive", "preop", "glucose / hyperglycemia"),
    FeatureSpec("preop_bun", "comprehensive", "preop"),
    FeatureSpec("preop_ast", "comprehensive", "preop", "liver (hepatorenal)"),
    FeatureSpec("preop_alt", "comprehensive", "preop", "liver"),
    FeatureSpec("preop_pao2", "comprehensive", "preop"),
    FeatureSpec("preop_paco2", "comprehensive", "preop"),
    FeatureSpec("preop_sao2", "comprehensive", "preop"),
    # -- Comprehensive: Sec 7B surgical --------------------------------------
    FeatureSpec("anesthesia_duration_min", "comprehensive", "intraop"),
    FeatureSpec("optype", "comprehensive", "preop", "surgery type (model stage one-hots)"),
    FeatureSpec("department", "comprehensive", "preop"),
    # -- Comprehensive: Sec 7D/7E intraoperative totals ----------------------
    FeatureSpec("intraop_ebl", "comprehensive", "intraop", "estimated blood loss mL"),
    FeatureSpec("intraop_uo", "comprehensive", "intraop", "intraop urine output mL (intermittent)"),
    FeatureSpec("intraop_crystalloid", "comprehensive", "intraop", "mL (chloride-load proxy)"),
    FeatureSpec("intraop_colloid", "comprehensive", "intraop", "mL (HES nephrotoxicity)"),
    FeatureSpec("intraop_rbc", "comprehensive", "intraop", "PRBC mL (transfusion-AKI)"),
    FeatureSpec("intraop_ffp", "comprehensive", "intraop", "FFP mL"),
    FeatureSpec("intraop_ppf", "comprehensive", "intraop", "propofol total mg (PK-refined in +PK)"),
    FeatureSpec("intraop_mdz", "comprehensive", "intraop", "midazolam total mg"),
    FeatureSpec("intraop_ftn", "comprehensive", "intraop", "fentanyl total ug"),
    FeatureSpec("intraop_rocu", "comprehensive", "intraop", "rocuronium total mg"),
    FeatureSpec("intraop_vecu", "comprehensive", "intraop", "vecuronium total mg"),
    FeatureSpec("intraop_eph", "comprehensive", "intraop", "ephedrine total mg (vasopressor)"),
    FeatureSpec("intraop_phe", "comprehensive", "intraop", "phenylephrine total ug (vasopressor)"),
    FeatureSpec("intraop_epi", "comprehensive", "intraop", "epinephrine total mg"),
    FeatureSpec("intraop_ca", "comprehensive", "intraop", "calcium total mg"),
]
audit_specs(SPECS)  # fail at import if any feature is timed after the cutoff


def ckd_epi_2021(scr: float | None, age: float | None, sex_male: int | None) -> float | None:
    """CKD-EPI 2021 race-free eGFR (mL/min/1.73m^2). Returns None if inputs missing."""
    if scr is None or age is None or sex_male is None or scr <= 0:
        return None
    female = sex_male == 0
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = scr / kappa
    egfr = 142.0 * (min(ratio, 1.0) ** alpha) * (max(ratio, 1.0) ** -1.200) * (0.9938 ** age)
    if female:
        egfr *= 1.012
    return round(egfr, 1)


def _dur_min(case: dict[str, Any], a: str, b: str) -> float | None:
    ta, tb = to_float(case.get(a)), to_float(case.get(b))
    if ta is None or tb is None:
        return None
    return round((ta - tb) / 60.0, 1)


def extract(cfg: dict[str, Any], cases_by_id: dict[str, dict],
            caseids: list[str]) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the tabular Sec-7 features."""
    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        c = cases_by_id.get(str(cid))
        if c is None:
            continue
        sex_male = 1 if str(c.get("sex", "")).strip().upper().startswith("M") else 0
        age = to_float(c.get("age"))
        base_cr = to_float(c.get("preop_cr"))
        hb = to_float(c.get("preop_hb"))
        alb = to_float(c.get("preop_alb"))
        f: dict[str, Any] = {
            "age": age,
            "sex_male": sex_male,
            "bmi": to_float(c.get("bmi")),
            "asa": to_float(c.get("asa")),
            "is_emergency": 1 if str(c.get("emop", "")).strip() in ("1", "Y", "Yes", "True") else 0,
            "baseline_cr": base_cr,
            "egfr_ckdepi": ckd_epi_2021(base_cr, age, sex_male),
            "preop_htn": _flag(c.get("preop_htn")),
            "preop_dm": _flag(c.get("preop_dm")),
            "surgery_duration_min": _dur_min(c, "opend", "opstart"),
            "height_cm": to_float(c.get("height")),
            "weight_kg": to_float(c.get("weight")),
            "preop_hb": hb,
            "anemia_flag": _anemia(hb, sex_male),
            "preop_alb": alb,
            "hypoalbuminemia_flag": (1 if (alb is not None and alb < 3.5) else (0 if alb is not None else None)),
            "preop_plt": to_float(c.get("preop_plt")),
            "preop_pt": to_float(c.get("preop_pt")),
            "preop_aptt": to_float(c.get("preop_aptt")),
            "preop_na": to_float(c.get("preop_na")),
            "preop_k": to_float(c.get("preop_k")),
            "preop_hco3": to_float(c.get("preop_hco3")),
            "preop_be": to_float(c.get("preop_be")),
            "preop_ph": to_float(c.get("preop_ph")),
            "preop_gluc": to_float(c.get("preop_gluc")),
            "preop_bun": to_float(c.get("preop_bun")),
            "preop_ast": to_float(c.get("preop_ast")),
            "preop_alt": to_float(c.get("preop_alt")),
            "preop_pao2": to_float(c.get("preop_pao2")),
            "preop_paco2": to_float(c.get("preop_paco2")),
            "preop_sao2": to_float(c.get("preop_sao2")),
            "anesthesia_duration_min": _dur_min(c, "aneend", "anestart"),
            "optype": (c.get("optype") or None),
            "department": (c.get("department") or None),
        }
        for col in ("intraop_ebl", "intraop_uo", "intraop_crystalloid", "intraop_colloid",
                    "intraop_rbc", "intraop_ffp", "intraop_ppf", "intraop_mdz", "intraop_ftn",
                    "intraop_rocu", "intraop_vecu", "intraop_eph", "intraop_phe",
                    "intraop_epi", "intraop_ca"):
            f[col] = to_float(c.get(col))
        out[str(cid)] = f
    return out


def _flag(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    return 1 if str(v).strip() in ("1", "Y", "Yes", "True") else 0


def _anemia(hb: float | None, sex_male: int | None) -> int | None:
    if hb is None:
        return None
    thr = 13.0 if sex_male == 1 else 12.0
    return 1 if hb < thr else 0
