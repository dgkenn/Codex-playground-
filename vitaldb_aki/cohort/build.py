"""build.py -- assemble the labelable AKI cohort (Sec 5 + Sec 6).

Pipeline: fetch /cases + /labs (cached) -> apply eligibility (Sec 5) -> derive the
KDIGO baseline and postoperative creatinine series -> label (Sec 6) -> emit the
labelable cohort plus a transparent accounting of every drop reason and the
selection-bias comparison (labelable vs full eligible, Sec 5).

Writes:
  cache_dir/cohort.csv          one row per labelable case (caseid, subjectid, aki, stage, ...)
  cache_dir/cohort_summary.json event rate, stage distribution, drop accounting, hashes

stdlib only; reuses common/hashing from the EEG project for the canonical content
hash so splits/artifacts are reproducible (Sec 14).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.hashing import hash_object as content_hash  # canonical-JSON hash (Sec 14)
from vitaldb_aki.cohort.eligibility import check_eligibility
from vitaldb_aki.cohort.labeling import label_case
from vitaldb_aki.data.client import creatinine_by_case, fetch_cases, to_float


def _anchor_seconds(case: dict[str, Any], kcfg: dict[str, Any]) -> float | None:
    """End-of-surgery anchor (seconds from casestart). Falls back caseend->aneend."""
    for key in (kcfg.get("window_anchor", "opend"), "opend", "caseend", "aneend"):
        v = to_float(case.get(key))
        if v is not None:
            return v
    return None


def _baseline(case: dict[str, Any], cr_series: list[tuple[float, float]],
              anchor: float, kcfg: dict[str, Any]) -> tuple[float | None, str]:
    """Most-recent preoperative creatinine (Sec 6): prefer preop_cr, else newest
    preop lab cr within the configured pre-op window."""
    base = to_float(case.get(kcfg.get("baseline", "preop_cr")))
    if base is not None and base > 0:
        return base, "preop_cr"
    if kcfg.get("baseline_fallback_to_labs"):
        win_s = float(kcfg["baseline_preop_window_h"]) * 3600.0
        preop = [(dt, v) for dt, v in cr_series if dt < anchor and (anchor - dt) <= win_s]
        if preop:
            preop.sort(key=lambda x: x[0])
            return preop[-1][1], "preop_lab"   # most recent before anchor
    return None, "none"


def build_cohort(cfg: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
    kcfg = cfg["kdigo"]
    cases = fetch_cases(cfg, refresh=refresh)
    cr_by_case = creatinine_by_case(cfg, refresh=refresh)

    drops: dict[str, int] = {}
    eligible_rows: list[dict] = []      # eligible (for selection-bias denom)
    labelable: list[dict] = []
    for case in cases:
        cid = case.get("caseid")
        keep, reason = check_eligibility(case, cfg)
        if not keep:
            drops[reason] = drops.get(reason, 0) + 1
            continue

        anchor = _anchor_seconds(case, kcfg)
        if anchor is None:
            drops["no surgery-end anchor"] = drops.get("no surgery-end anchor", 0) + 1
            continue
        series = cr_by_case.get(cid, [])
        base, base_src = _baseline(case, series, anchor, kcfg)
        # postop creatinine = measured strictly after end of surgery, in seconds-after-anchor
        postop = [(dt - anchor, v) for dt, v in series if dt > anchor]

        eligible_rows.append({"caseid": cid, "subjectid": case.get("subjectid"),
                              "has_label": bool(base and postop),
                              "age": to_float(case.get("age")),
                              "asa": case.get("asa"), "preop_cr": base})

        res = label_case(cid, base, base_src, postop, kcfg)
        if res.aki is None:
            drops[res.reason] = drops.get(res.reason, 0) + 1
            continue
        labelable.append({
            "caseid": cid,
            "subjectid": case.get("subjectid"),
            "aki": res.aki,
            "kdigo_stage": res.stage,
            "baseline_cr": res.baseline_cr,
            "baseline_source": res.baseline_source,
            "peak_postop_cr": res.peak_postop_cr,
            "n_postop_cr": res.n_postop_cr,
            "criterion": res.reason,
            "age": to_float(case.get("age")),
            "sex": case.get("sex"),
            "asa": case.get("asa"),
            "optype": case.get("optype"),
            "department": case.get("department"),
            "emop": case.get("emop"),
        })

    n = len(labelable)
    n_aki = sum(r["aki"] for r in labelable)
    stages = {s: sum(1 for r in labelable if r["kdigo_stage"] == s) for s in (1, 2, 3)}
    summary = {
        "n_cases_total": len(cases),
        "n_eligible": len(eligible_rows),
        "n_labelable": n,
        "n_aki": n_aki,
        "aki_rate": round(n_aki / n, 4) if n else None,
        "kdigo_stage_counts": stages,
        "n_unique_patients": len({r["subjectid"] for r in labelable}),
        "drop_reasons": dict(sorted(drops.items(), key=lambda kv: -kv[1])),
        "selection_bias": _selection_bias(eligible_rows),
        "config_hash": content_hash(cfg),
    }
    summary["cohort_hash"] = content_hash(
        [{"caseid": r["caseid"], "aki": r["aki"]} for r in sorted(labelable, key=lambda r: r["caseid"])]
    )

    cdir = cfg["data"]["cache_dir"]
    os.makedirs(cdir, exist_ok=True)
    _write_csv(os.path.join(cdir, "cohort.csv"), labelable)
    with open(os.path.join(cdir, "cohort_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def _selection_bias(eligible_rows: list[dict]) -> dict[str, Any]:
    """Labelable (got a postop cr) vs not-labelable among eligible (Sec 5)."""
    lab = [r for r in eligible_rows if r["has_label"]]
    nolab = [r for r in eligible_rows if not r["has_label"]]

    def _mean(rows, key):
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    def _mean_asa(rows):
        vals = [float(r["asa"]) for r in rows if str(r.get("asa", "")).strip() not in ("", "nan", "None")]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "n_labelable": len(lab), "n_not_labelable": len(nolab),
        "mean_age_labelable": _mean(lab, "age"), "mean_age_not": _mean(nolab, "age"),
        "mean_asa_labelable": _mean_asa(lab), "mean_asa_not": _mean_asa(nolab),
        "note": "patients with a postop creatinine are sicker/more-monitored; cohort is not representative (Sec 5).",
    }


def _write_csv(path: str, rows: list[dict]) -> None:
    import csv
    if not rows:
        open(path, "w").close()
        return
    cols = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
