"""build_matrix.py -- assemble the modeling feature matrix (Sec 7-9).

Joins the labelable cohort (cohort/build.py output) with every registered feature
module, runs the Sec 11 leakage audit over the union of specs, and writes one row
per case with all features + the AKI label + the patient id (for patient-level
splits, Sec 11.6).

Feature modules are pluggable: each exposes SPECS + extract(cfg, cases_by_id,
caseids). Stage 2a (tabular) is wired in now; hemodynamics (Sec 7C) and PK
(Sec 8) register here as they land, with no change to the modeling stage.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.hashing import hash_object as content_hash
from vitaldb_aki.data.client import fetch_cases
from vitaldb_aki.features.base import FeatureSpec, audit_specs
from vitaldb_aki.features import hemodynamics, pk, tabular


# Registered feature modules (each: SPECS + extract). PK (Sec 8) is active:
# Eleveld-vs-pump Ce validation confirmed (Spearman 0.96).
MODULES = [tabular, hemodynamics, pk]


def _load_cohort(cfg: dict[str, Any]) -> list[dict]:
    path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found -- run `cli.py cohort` first")
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _extract_parallel(m, cfg, cases_by_id, caseids, workers):
    """Run one module's extract across cases in a thread pool. Track downloads are
    I/O-bound, so threads give a big wall-clock win; the per-case extract calls are
    independent and the /trks index is pre-warmed before fan-out to avoid a race."""
    from concurrent.futures import ThreadPoolExecutor
    merged: dict[str, dict] = {}
    def one(cid):
        return m.extract(cfg, cases_by_id, [cid])
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for d in ex.map(one, caseids):
            merged.update(d)
    return merged


def build_matrix(cfg: dict[str, Any], modules: list[Any] | None = None,
                 workers: int = 12) -> dict[str, Any]:
    modules = modules or MODULES
    cohort = _load_cohort(cfg)
    caseids = [r["caseid"] for r in cohort]
    cases = fetch_cases(cfg)
    cases_by_id = {c["caseid"]: c for c in cases}

    all_specs: list[FeatureSpec] = []
    for m in modules:
        all_specs.extend(m.SPECS)
    audit_specs(all_specs)  # Sec 11 firewall over the FULL union

    # Pre-warm the (caseid,tname)->tid index once so threaded workers don't race
    # building it (modules that don't use tracks simply ignore it).
    from vitaldb_aki.data import tracks as _tracks
    _tracks.tid_for(cfg, caseids[0], "Solar8000/ART_MBP")

    # extract + merge per module; parallelize the download-heavy modules per case.
    per_module = []
    for m in modules:
        uses_tracks = getattr(m, "USES_TRACKS", m.__name__.split(".")[-1] in ("hemodynamics", "pk"))
        if uses_tracks and workers > 1:
            per_module.append(_extract_parallel(m, cfg, cases_by_id, caseids, workers))
        else:
            per_module.append(m.extract(cfg, cases_by_id, caseids))
    feat_names = [s.name for s in all_specs]

    rows: list[dict] = []
    for r in cohort:
        cid = r["caseid"]
        row = {"caseid": cid, "subjectid": r["subjectid"], "aki": int(r["aki"]),
               "kdigo_stage": r["kdigo_stage"]}
        for feats in per_module:
            row.update(feats.get(cid, {}))
        rows.append(row)

    cdir = cfg["data"]["cache_dir"]
    cols = ["caseid", "subjectid", "aki", "kdigo_stage"] + feat_names
    out_csv = os.path.join(cdir, "feature_matrix.csv")
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # coverage / missingness report (drives imputation choices, Sec 10)
    miss = {name: round(sum(1 for r in rows if r.get(name) in (None, "")) / len(rows), 3)
            for name in feat_names} if rows else {}
    summary = {
        "n_rows": len(rows),
        "n_aki": sum(r["aki"] for r in rows),
        "n_features": len(feat_names),
        "feature_sets": {s: sum(1 for sp in all_specs if sp.fset == s)
                         for s in ("standard", "comprehensive", "pk")},
        "modules": [m.__name__.split(".")[-1] for m in modules],
        "missingness_top": dict(sorted(miss.items(), key=lambda kv: -kv[1])[:15]),
        "matrix_hash": content_hash([{k: r.get(k) for k in cols} for r in rows]),
        "specs_hash": content_hash([(s.name, s.fset, s.timing) for s in all_specs]),
    }
    with open(os.path.join(cdir, "feature_matrix_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary
