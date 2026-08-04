"""eligibility.py -- cohort inclusion/exclusion (Sec 5).

Each rule returns (keep: bool, reason: str). VitalDB has no structured diagnosis
codes for several protocol exclusions (ESRD, transplant, AV-fistula), so those are
best-effort and documented per-flag here -- the protocol explicitly requires the
rule to be stated where the data is imperfect (Sec 5). Cardiac cases are already
absent from VitalDB's public non-cardiac release, but the optype/department filter
is applied defensively.

Pure stdlib: operates on a single case dict (string cells) + parsed helpers.
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.data.client import to_float


# substrings (lowercased) used for best-effort text-based exclusions
_OBSTETRIC = ("cesarean", "c-sec", "obstet", "gyneco-ob", "delivery")
_TRANSPLANT = ("transplant", "kidney transplant", "renal transplant", "donor nephrectomy")
_FISTULA = ("av fistula", "a-v fistula", "arteriovenous fistula", "avf creation")
_CARDIAC = ("cardiac", "cabg", "coronary", "valve", "aortic valve", "cardiopulmonary bypass")


def _text(case: dict[str, Any]) -> str:
    parts = [case.get(k, "") or "" for k in ("optype", "opname", "dx", "department", "approach")]
    return " ".join(parts).lower()


def check_eligibility(case: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, str]:
    """Return (eligible, reason). First failing rule wins."""
    ccfg = cfg["cohort"]
    txt = _text(case)

    age = to_float(case.get("age"))
    if age is None or age < float(ccfg["min_age_years"]):
        return False, f"age<{ccfg['min_age_years']} or missing"

    if ccfg.get("exclude_cardiac") and any(s in txt for s in _CARDIAC):
        return False, "cardiac surgery"

    if ccfg.get("exclude_obstetric") and any(s in txt for s in _OBSTETRIC):
        return False, "obstetric case"

    if ccfg.get("exclude_transplant") and any(s in txt for s in _TRANSPLANT):
        return False, "transplant/donor"

    if ccfg.get("exclude_av_fistula") and any(s in txt for s in _FISTULA):
        return False, "AV-fistula case"

    # Pre-existing ESRD / advanced CKD: no dialysis flag in VitalDB, so we use a
    # high baseline-creatinine threshold as a documented proxy (Sec 5).
    if ccfg.get("exclude_preexisting_esrd"):
        base = to_float(case.get("preop_cr"))
        if base is not None and base >= float(ccfg["esrd_baseline_cr_mgdl"]):
            return False, f"preop_cr>={ccfg['esrd_baseline_cr_mgdl']} (ESRD/advanced-CKD proxy)"

    return True, "eligible"
