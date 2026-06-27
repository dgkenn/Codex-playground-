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
    aline_morphology, hemodynamics, pfds, pk, pkpd_sensitivity, risk_factors, tabular, temporal,
)
# Discovery biomarker modules (novel-axis candidates; numeric-first, waveform tiers
# gated off by default). Kept OUT of the headline MODULES so the confirmatory build
# is unchanged; folded in only for the dedicated discovery build (DISCOVERY_MODULES).
from vitaldb_aki.features import (
    autonomic, bp_variability, capnogram, fluid_responsiveness, ischemia,
    neuro_eeg, thermoregulation, vasoactive_pd, venous_congestion, ventilation,
)
# Higher-order (3+ signal) COUPLING discovery modules: organ injury as multi-system
# decoupling. Each aligns several signals on a common grid per case; numeric-first.
from vitaldb_aki.features import (
    cardioresp_coupling, cerebral_autoreg, drug_brain_circ, multivariate_complexity,
    perfusion_cascade, physio_network,
)


# Registered feature modules (each: SPECS + extract). All validated and active:
# tabular (§7A/B/D/E), hemodynamics (§7C), pk (§8, Spearman 0.96 + bolus split),
# temporal (§7C/9), risk_factors (§7A/B labs+flags), aline_morphology (§7F),
# cross_waveform (§7F novel coupling biomarkers).
# aline_morphology + cross_waveform are 500 Hz waveform-MORPHOLOGY modules
# (SNUADC/ART ~50 MB/case, ~200 GB cohort-wide): inherently bandwidth-bound, not
# optimizable. They run as a SEPARATE supervised waveform-enrichment pass and are
# excluded from the headline matrix so the numeric/clinical/PK build completes
# fast. (aline_morphology stays imported above for that pass + tests.)
MODULES = [tabular, hemodynamics, pk, temporal, risk_factors, pfds, pkpd_sensitivity]

# DISCOVERY_MODULES: 10 novel-axis biomarker families to be screened for incremental
# value (redundancy/novelty control) before any promotion to the confirmatory set.
# Each is numeric-first (fast) with heavy 500 Hz tiers gated off by default
# (neuro_eeg embedding, autonomic raw-ECG HRV/BRS, capnogram phase-III). Run a
# discovery build via build_matrix(cfg, modules=MODULES + DISCOVERY_MODULES).
#   neuro_eeg          -- burst suppression / EEG depth (+foundation-model hook)
#   ventilation        -- driving pressure / mechanical power (VILI)
#   bp_variability     -- BP variability + sample-entropy complexity loss
#   autonomic          -- HRV (coarse) + deferred baroreflex
#   vasoactive_pd      -- vasoplegia signature / pressor responsiveness
#   ischemia           -- ST-segment ischemia burden (feature; no troponin label)
#   venous_congestion  -- CVP / renal venous congestion (cardiorenal)
#   capnogram          -- EtCO2 dynamics (pulmonary perfusion / dead space)
#   thermoregulation   -- intraop hypothermia burden / rewarming
#   fluid_responsiveness -- SVV / SVR / CO (occult hypovolemia, vasoplegia)
# Higher-order coupling families (3+ signals; mostly pk-tier on instrumented subsets):
#   perfusion_cascade       -- MAP x EtCO2 x SpO2 tri-witness occult hypoperfusion
#   cerebral_autoreg        -- EEG x MAP | Ce conditional autoregulation failure
#   cardioresp_coupling     -- HR x RR x MAP cardio-respiratory-autonomic triad
#   drug_brain_circ         -- Ce x BIS x MAP PK/PD/hemodynamic fragility surface
#   multivariate_complexity -- N-way joint sample entropy + coupling dispersion
#   physio_network          -- coupling-network topology + transfer-entropy info flow
COUPLING_MODULES = [
    perfusion_cascade, cerebral_autoreg, cardioresp_coupling, drug_brain_circ,
    multivariate_complexity, physio_network,
]
DISCOVERY_MODULES = [
    neuro_eeg, ventilation, bp_variability, autonomic, vasoactive_pd,
    ischemia, venous_congestion, capnogram, thermoregulation, fluid_responsiveness,
] + COUPLING_MODULES


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



def _purge_track_cache(cfg):
    """Delete cached per-track CSVs to bound disk on this small (~38G) filesystem.
    Each module's features are already saved to _featcache, so raw tracks are
    disposable; the next track-module re-downloads only what it needs (peak disk
    ~= one module's track footprint instead of all modules' accumulated)."""
    import glob
    tdir = os.path.join(cfg["data"]["cache_dir"], "tracks")
    for f in glob.glob(os.path.join(tdir, "*.csv")):
        try:
            os.remove(f)
        except OSError:
            pass

def _extract_parallel(m, cfg, cases_by_id, caseids, workers, partial_path=None):
    """Run one module's extract across cases in a thread pool, RESUMABLY: each
    completed case is appended to `partial_path` (jsonl) as it finishes, so a
    restart/hang reloads finished cases and only re-processes the remainder. Track
    downloads are I/O-bound; the /trks index is pre-warmed before fan-out."""
    from concurrent.futures import ThreadPoolExecutor
    merged: dict[str, dict] = {}
    done: set[str] = set()
    if partial_path and os.path.exists(partial_path):
        with open(partial_path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                    merged[rec["caseid"]] = rec["feats"]; done.add(rec["caseid"])
                except Exception:
                    continue
    todo = [c for c in caseids if c not in done]
    def one(cid):
        return cid, m.extract(cfg, cases_by_id, [cid])
    fh = open(partial_path, "a", encoding="utf-8") if partial_path else None
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for cid, d in ex.map(one, todo):
                merged.update(d)
                if fh is not None:
                    fh.write(json.dumps({"caseid": cid, "feats": d.get(cid)}) + "\n"); fh.flush()
    finally:
        if fh is not None:
            fh.close()
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
        partial = cache_file + ".partial"
        if uses_tracks and workers > 1:
            feats = _extract_parallel(m, cfg, cases_by_id, caseids, workers, partial)
        else:
            feats = m.extract(cfg, cases_by_id, caseids)
        _save_module_cache(cache_file, feats)
        try:
            os.remove(partial)
        except OSError:
            pass
        print(f"[build_matrix] {mod_name}: cached to {cache_file}")
        per_module.append(feats)
        if uses_tracks:
            _purge_track_cache(cfg)   # bounded disk on ~38G fs
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
