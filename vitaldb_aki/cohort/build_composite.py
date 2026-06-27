"""build_composite.py -- assemble the composite end-organ-damage cohort.

Extends the renal-only cohort (cohort/build.py) to the PRIMARY composite outcome
and its per-organ SECONDARY components (cohort/organ_labeling.py). Joins /cases +
/labs, derives each organ's preop baseline and postop series, labels every
component, ORs them into the composite, and emits one row per labelable case plus
a transparent per-component event-count summary.

Writes:
  cache_dir/cohort_composite.csv          one row/case: composite + per-organ labels
  cache_dir/cohort_composite_summary.json event counts per component + composite

stdlib only; reuses common/hashing + the eligibility/anchor/baseline logic.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.hashing import hash_object as content_hash
from vitaldb_aki.cohort.build import _anchor_seconds, _baseline
from vitaldb_aki.cohort.eligibility import check_eligibility
from vitaldb_aki.cohort.organ_labeling import label_organs
from vitaldb_aki.data.client import fetch_cases, fetch_table, to_float

# Analytes whose preop baseline + postop series the components need.
_ANALYTES = ("cr", "ast", "alt", "tbil", "plt", "ptinr", "lac")


def _labs_index(cfg, cset) -> dict[str, dict[str, list[tuple[float, float]]]]:
    idx: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for l in fetch_table(cfg, "labs"):
        cid = l["caseid"]
        if cid not in cset or l["name"] not in _ANALYTES:
            continue
        dt, v = to_float(l.get("dt")), to_float(l.get("result"))
        if dt is not None and v is not None:
            idx[cid][l["name"]].append((dt, v))
    for cid in idx:
        for a in idx[cid]:
            idx[cid][a].sort(key=lambda x: x[0])
    return idx


def _preop_most_recent(series, anchor, win_s):
    xs = [(dt, v) for dt, v in series if dt < anchor and (anchor - dt) <= win_s]
    return xs[-1][1] if xs else None


def build_composite_cohort(cfg: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
    kcfg = cfg["kdigo"]
    oc = cfg["organ_outcomes"]
    win_s = float(oc["postop_window_h"]) * 3600.0
    base_win = float(kcfg["baseline_preop_window_h"]) * 3600.0

    cases = fetch_cases(cfg, refresh=refresh)
    cset = {c["caseid"] for c in cases}
    labs = _labs_index(cfg, cset)

    rows: list[dict] = []
    drops: dict[str, int] = {}
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

        cl = labs.get(cid, {})
        baselines = {a: _preop_most_recent(cl.get(a, []), anchor, base_win) for a in _ANALYTES}
        postop = {a: [v for dt, v in cl.get(a, []) if anchor < dt <= anchor + win_s]
                  for a in _ANALYTES}

        # renal (KDIGO) inputs -- baseline prefers /cases preop_cr (cohort/build logic)
        cr_base, cr_src = _baseline(case, cl.get("cr", []), anchor, kcfg)
        renal_inputs = {"caseid": cid, "baseline": cr_base, "baseline_source": cr_src,
                        "postop_cr": [(dt - anchor, v) for dt, v in cl.get("cr", []) if dt > anchor]}

        death = str(case.get("death_inhosp", "")).strip() in ("1", "Y", "Yes", "True")
        ol = label_organs(cid, case.get("optype"), baselines, postop, death,
                          renal_inputs, cfg, case=case)
        if ol.composite is None:
            drops["no labelable organ component"] = drops.get("no labelable organ component", 0) + 1
            continue

        row = {"caseid": cid, "subjectid": case.get("subjectid"),
               "composite": ol.composite, "n_organs_hit": len(ol.fired),
               "organs_fired": "|".join(ol.fired),
               "age": to_float(case.get("age")), "sex": case.get("sex"),
               "optype": case.get("optype"), "department": case.get("department")}
        for name, val in ol.components.items():
            row[f"organ_{name}"] = "" if val is None else val
        rows.append(row)

    n = len(rows)
    n_comp = sum(r["composite"] for r in rows)
    comp_counts = {}
    for name in oc["components"]:
        col = f"organ_{name}"
        pos = sum(1 for r in rows if r.get(col) == 1)
        labl = sum(1 for r in rows if r.get(col) in (0, 1))
        comp_counts[name] = {"events": pos, "labelable": labl,
                             "rate": round(pos / labl, 4) if labl else None}
    summary = {
        "n_labelable": n,
        "composite_events": n_comp,
        "composite_rate": round(n_comp / n, 4) if n else None,
        "n_unique_patients": len({r["subjectid"] for r in rows}),
        "component_counts": comp_counts,
        "multi_organ_distribution": _multi_hist(rows),
        "primary": oc["primary"],
        "excluded_not_labelable_for_myocardial": "no troponin/CK in VitalDB open labs",
        "config_hash": content_hash(cfg),
        "drop_reasons": dict(sorted(drops.items(), key=lambda kv: -kv[1])),
    }
    cdir = cfg["data"]["cache_dir"]
    os.makedirs(cdir, exist_ok=True)
    _write_csv(os.path.join(cdir, "cohort_composite.csv"), rows)
    with open(os.path.join(cdir, "cohort_composite_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def _multi_hist(rows) -> dict[str, int]:
    h: dict[str, int] = {}
    for r in rows:
        k = str(r["n_organs_hit"])
        h[k] = h.get(k, 0) + 1
    return dict(sorted(h.items()))


def _write_csv(path, rows):
    if not rows:
        open(path, "w").close()
        return
    cols = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
