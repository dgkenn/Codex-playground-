"""build_matrix.py -- assemble the modeling feature matrix (Sec 7-9).

Joins the labelable cohort (cohort/build.py output) with every registered feature
module, runs the Sec 11 leakage audit over the union of specs, and writes one row
per case with all features + the AKI label + the patient id (for patient-level
splits, Sec 11.6).

Feature modules are pluggable: each exposes SPECS + extract(cfg, cases_by_id,
caseids). Stage 2a (tabular) is wired in now; hemodynamics (Sec 7C) and PK
(Sec 8) register here as they land, with no change to the modeling stage.

Per-module feature caching
--------------------------
Each module's extracted features are cached to disk at:
  cache_dir/_featcache/<module>__<hash>.json
where <hash> = content hash of (module name, sorted spec names+timings, sorted
caseids, and relevant config keys). On rebuild, cached modules are loaded instead
of re-extracted, making container-restart recovery cheap.
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
from vitaldb_aki.features import (
    aline_morphology, cross_waveform, hemodynamics, pk, risk_factors, tabular, temporal,
)


# Registered feature modules (each: SPECS + extract). All validated and active:
# tabular (§7A/B/D/E), hemodynamics (§7C), pk (§8, Spearman 0.96 + bolus split),
# temporal (§7C/9), risk_factors (§7A/B labs+flags), aline_morphology (§7F),
# cross_waveform (§7F novel coupling biomarkers).
MODULES = [tabular, hemodynamics, pk, temporal, risk_factors, aline_morphology, cross_waveform]


# ---------------------------------------------------------------------------
# Per-module feature cache helpers
# ---------------------------------------------------------------------------

def _module_cache_key(m, caseids: list[str]) -> str:
    """Stable content hash that identifies a unique (module, specs, cohort) triple.

    Changing the module's SPEC list or the cohort case-list invalidates the key
    so stale cache files are never loaded.
    """
    mod_name = m.__name__.split(".")[-1]
    spec_sig = sorted((s.name, s.timing, s.fset) for s in m.SPECS)
    caseid_sig = sorted(str(c) for c in caseids)
    return content_hash({"module": mod_name, "specs": spec_sig, "caseids": caseid_sig})


def _cache_path(cfg: dict[str, Any], m, key: str) -> str:
    mod_name = m.__name__.split(".")[-1]
    cdir = os.path.join(cfg["data"]["cache_dir"], "_featcache")
    os.makedirs(cdir, exist_ok=True)
    return os.path.join(cdir, f"{mod_name}__{key[:16]}.json")


def _load_module_cache(path: str) -> dict[str, dict] | None:
    """Return cached features dict, or None if absent/corrupt."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _save_module_cache(path: str, feats: dict[str, dict]) -> None:
    """Write module features to the JSON cache file (atomic via tmp rename)."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(feats, fh, allow_nan=False, default=lambda x: None)
        os.replace(tmp, path)
    except Exception:
        # Non-fatal: a failed write means cache miss on next run, not corruption.
        try:
            os.remove(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Non-feature columns
# ---------------------------------------------------------------------------

# Non-feature columns to carry from the cohort into the matrix: the composite
# primary label, per-organ secondary labels, and the renal-only label.
def _label_cols(cohort: list[dict]) -> list[str]:
    if not cohort:
        return []
    keys = cohort[0].keys()
    cols = [c for c in ("composite", "n_organs_hit", "aki", "kdigo_stage") if c in keys]
    cols += [c for c in keys if c.startswith("organ_")]
    return cols


def _load_cohort(cfg: dict[str, Any]) -> list[dict]:
    """Prefer the composite cohort (primary outcome); fall back to renal-only."""
    cdir = cfg["data"]["cache_dir"]
    for name in ("cohort_composite.csv", "cohort.csv"):
        path = os.path.join(cdir, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as fh:
                return list(csv.DictReader(fh))
    raise FileNotFoundError(f"no cohort in {cdir} -- run `cli.py cohort-composite` first")


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

    # extract + merge per module; check per-module cache first.
    # For USES_TRACKS modules the expensive work is the download; the cache
    # short-circuits both the download AND the extract entirely on cache hit.
    per_module = []
    for m in modules:
        mod_name = m.__name__.split(".")[-1]
        cache_key = _module_cache_key(m, caseids)
        cache_file = _cache_path(cfg, m, cache_key)
        cached = _load_module_cache(cache_file)
        if cached is not None:
            print(f"[build_matrix] {mod_name}: loaded from cache ({cache_file})")
            per_module.append(cached)
            continue

        print(f"[build_matrix] {mod_name}: cache miss -- extracting ...")
        uses_tracks = getattr(m, "USES_TRACKS", mod_name in ("hemodynamics", "pk"))
        if uses_tracks and workers > 1:
            feats = _extract_parallel(m, cfg, cases_by_id, caseids, workers)
        else:
            feats = m.extract(cfg, cases_by_id, caseids)
        _save_module_cache(cache_file, feats)
        print(f"[build_matrix] {mod_name}: cached to {cache_file}")
        per_module.append(feats)
    feat_names = [s.name for s in all_specs]

    label_cols = _label_cols(cohort)
    rows: list[dict] = []
    for r in cohort:
        cid = r["caseid"]
        row = {"caseid": cid, "subjectid": r["subjectid"]}
        for lc in label_cols:
            row[lc] = r.get(lc)
        for feats in per_module:
            row.update(feats.get(cid, {}))
        rows.append(row)

    cdir = cfg["data"]["cache_dir"]
    cols = ["caseid", "subjectid"] + label_cols + feat_names
    out_csv = os.path.join(cdir, "feature_matrix.csv")
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # coverage / missingness report (drives imputation choices, Sec 10)
    miss = {name: round(sum(1 for r in rows if r.get(name) in (None, "")) / len(rows), 3)
            for name in feat_names} if rows else {}
    def _count(col):
        return sum(1 for r in rows if str(r.get(col)) == "1")
    summary = {
        "n_rows": len(rows),
        "n_composite": _count("composite"),
        "n_aki": _count("organ_renal") or _count("aki"),
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
