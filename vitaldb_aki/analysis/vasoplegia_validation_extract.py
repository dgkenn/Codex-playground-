"""vasoplegia_validation_extract.py -- resumable, disk-bounded extraction that
puts MEASURED SVR/SVRI onto the SAME cases as the A-line WAVEFORM tone surrogate,
so the novel SVR-free WAVEFORM VASOPLEGIA INDEX (analysis/vasoplegia_biomarker.py)
can finally be VALIDATED against a reference standard.

WHY THIS EXISTS
---------------
vasoplegia_biomarker.py built a waveform-only tone surrogate (diastolic decay
tau, diastolic/MAP, form factor, augmentation index) as an SVR-free vasoplegia
index.  Its construct validity was UNVALIDATED because measured SVR overlapped the
waveform cases in N=0 of the current-cache cases -- we simply never extracted SVR
onto the ART-waveform cohort.  The /trks index shows the data EXISTS:
    SNUADC/ART  in  3645 cases
    EV1000/SVR or EV1000/SVRI         intersect ART -> ~248 cases (direct SVR)
    any CO monitor (EV1000/Vigileo/Vigilance/CardioQ) intersect ART -> ~977 cases
This module extracts both the WAVEFORM tone features AND measured SVR/SVRI/CO/SVV
onto each such case, so the headline Spearman(waveform index, measured SVRI) can
be computed (analysis/vasoplegia_validation_screen.py).

COHORT (built from cache/trks.csv -- NO download to build the list)
-------------------------------------------------------------------
caseids with SNUADC/ART AND at least one of
    {EV1000/SVR, EV1000/SVRI, EV1000/CO, Vigileo/CO, Vigilance/CO, CardioQ/CO}.
ORDERED SVR/SVRI-FIRST: the ~248 cases with a DIRECTLY-MEASURED SVR/SVRI track go
first (the cleanest validation cases), then the CO-only cases (SVRI computed from
CO).  This way a killed/resumed run still extracts the cleanest cases first.
Capped at the full ~977.

PER CASE
--------
  * features/aline_morphology.extract  + features/cross_waveform.extract  ->
    the waveform tone features (tau / diastolic / MAP / form-factor / AIx / PPV).
  * features/fluid_responsiveness.extract -> measured fluid_svr_mean/min/low_frac,
    fluid_svv_mean/..., fluid_co_mean, fluid_ci_min  (the reference standard).
  * a per-case MEASURED SVRI (svri_measured) computed with this preference order:
      1. EV1000/SVRI directly (already a body-size INDEX), else
      2. EV1000/SVR  (raw resistance), indexed -> SVRI = SVR * BSA, else
      3. SVRI = 80 * (MAP_mean - CVP_mean) / CO_mean * BSA
         with CO from the CO candidates, MAP from Solar8000/ART_MBP, CVP from
         Solar8000/CVP (default 5 mmHg if absent), BSA via Mosteller.
    The provenance is recorded in svri_source.

  UNIT / FORMULA NOTE (binding):
    SVR (dyn*s*cm^-5) = 80 * (MAP - CVP) / CO,  MAP/CVP in mmHg, CO in L/min;
    the 80 is the (mmHg*min/L) -> (dyn*s*cm^-5) conversion constant.
    SVRI (dyn*s*cm^-5*m^2) = SVR * BSA  (BSA in m^2, Mosteller
    = sqrt(height_cm * weight_kg / 3600)).  EV1000/SVRI is ALREADY indexed, so it
    is used as-is; EV1000/SVR and the CO-derived SVR are indexed by * BSA.  CVP
    defaults to 5 mmHg when no Solar8000/CVP track is present (a standard normal-
    range central venous pressure assumption; documented limitation).

STREAM / PURGE (disk-bounded)
-----------------------------
After each case the big SNUADC waveform CSVs (SNUADC/ART, SNUADC/PLETH,
SNUADC/ECG_II) AND the per-case monitor track files (SVR/SVRI/CO/CI/SVV, MAP,
CVP) are purged from cache/tracks/ so the ~50-100 MB/case ART waveform never
accumulates (discovery + aline jobs share the disk).  Mirrors
aline_feasibility's purge.

RESUMABLE
---------
Skips caseids already present in cache/vasoplegia_validation.csv; appends per
case; writes cache/_vasoplegia_validation_done.json when the whole cohort is done.

SMOKE TEST
----------
Set env VASOVAL_SMOKE_N=3 (or pass --limit 3) to extract only the first N cases
(SVR-first) -- used to confirm a row with BOTH waveform tone AND measured SVRI is
written without launching the multi-hour full run.

Heavy deps (numpy via the feature modules) are lazy; this module imports with the
stdlib only.

Run:  python3 vitaldb_aki/analysis/vasoplegia_validation_extract.py [--limit N]
"""
from __future__ import annotations

import csv as _csv
import json
import math
import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Constants (binding)
# ---------------------------------------------------------------------------
ART_TRACK_NAME = "SNUADC/ART"

# Direct measured-SVR tracks (the cleanest validation cases -> extracted first).
SVR_DIRECT_TRACKS = ("EV1000/SVRI", "EV1000/SVR")
# CO monitors (used to compute SVRI when no direct SVR/SVRI track exists).
CO_TRACKS = ("EV1000/CO", "Vigileo/CO", "Vigilance/CO", "CardioQ/CO")
# Any-CO-monitor membership for the cohort definition (SVR/SVRI tracks imply a
# monitor too, but we list CO explicitly for the cohort-membership predicate).
ANY_CO_MONITOR_TRACKS = SVR_DIRECT_TRACKS + CO_TRACKS

MAP_TRACK = "Solar8000/ART_MBP"
CVP_TRACK = "Solar8000/CVP"
DEFAULT_CVP_MMHG = 5.0          # normal-range CVP assumed when no CVP track

OUT_CSV = "vasoplegia_validation.csv"
DONE_MARKER = "_vasoplegia_validation_done.json"
FEATURE_MATRIX_FILE = "feature_matrix.csv"
CASES_FILE = "cases.csv"

FLUSH_EVERY = 10                # flush CSV + progress every N cases

# Big SNUADC waveform tracks to purge after each case (bounds disk).
_BIG_SNUADC_TRACKS = ("SNUADC/ART", "SNUADC/PLETH", "SNUADC/ECG_II")
# Monitor / numeric tracks to purge after each case too (small, but tidy).
_MONITOR_TRACKS = (
    "EV1000/SVR", "EV1000/SVRI", "EV1000/CO", "EV1000/CI", "EV1000/SVV",
    "Vigileo/CO", "Vigileo/CI", "Vigileo/SVV", "Vigilance/CO", "Vigilance/CI",
    "CardioQ/CO", "CardioQ/CI", MAP_TRACK, CVP_TRACK,
)

# SVR physiologic gate (mirror fluid_responsiveness) for the CO-derived SVR.
SVR_MIN, SVR_MAX = 100.0, 4000.0


# ===========================================================================
# PURE HELPERS (stdlib only)
# ===========================================================================
def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return "vitaldb_aki/cache"


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


def bsa_mosteller(height_cm, weight_kg) -> float | None:
    """Body-surface area (m^2) via Mosteller: sqrt(height_cm * weight_kg / 3600).
    Returns None if either input is missing / non-positive."""
    h = _to_float(height_cm)
    w = _to_float(weight_kg)
    if h is None or w is None or h <= 0 or w <= 0:
        return None
    return round(math.sqrt(h * w / 3600.0), 6)


def build_cohort(trks_path: str) -> tuple[list[str], list[str]]:
    """Build the validation cohort from cache/trks.csv WITHOUT any download.

    Returns (ordered_cohort, svr_first_ids) where:
      * ordered_cohort = caseids with SNUADC/ART AND at least one of the measured
        SVR/SVRI/CO monitor tracks, ORDERED SVR/SVRI-first (the direct-SVR cases),
        then CO-only cases.  Within each group the order is numeric-by-caseid for
        determinism.
      * svr_first_ids = the subset that carry a direct EV1000/SVR or EV1000/SVRI
        track (the ~248 cleanest validation cases).

    Pure / stdlib-only.  Idempotent and deterministic given trks.csv.
    """
    art: set[str] = set()
    has_svr: set[str] = set()
    has_co: set[str] = set()
    with open(trks_path, "r", newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        for r in reader:
            cid = str(r.get("caseid", "")).strip()
            tn = str(r.get("tname", "")).strip()
            if not cid or not tn:
                continue
            if tn == ART_TRACK_NAME:
                art.add(cid)
            elif tn in SVR_DIRECT_TRACKS:
                has_svr.add(cid)
            elif tn in CO_TRACKS:
                has_co.add(cid)

    def _numkey(c: str):
        try:
            return (0, int(c))
        except ValueError:
            return (1, c)

    svr_first = sorted(art & has_svr, key=_numkey)
    co_only = sorted((art & has_co) - has_svr, key=_numkey)
    ordered = svr_first + co_only
    return ordered, svr_first


# ===========================================================================
# Per-case MEASURED SVRI
# ===========================================================================
def _measured_svri(cfg, cid, fluid_row, bsa, t_start, t_end):
    """Compute a per-case MEASURED SVRI + provenance.

    Preference order (documented in the module docstring):
      1. EV1000/SVRI directly (already a body-size INDEX).
      2. EV1000/SVR (raw resistance) indexed -> SVRI = SVR * BSA.
      3. SVRI = 80 * (MAP_mean - CVP_mean) / CO_mean * BSA  (CO-derived).

    Returns (svri, source, detail_dict).  svri is None if no path succeeds.
    fluid_row is the fluid_responsiveness.extract() output for this case (carries
    fluid_svr_mean, fluid_co_mean).  The SVR/SVRI track *priority* in
    fluid_responsiveness is EV1000/SVR -> EV1000/SVRI, so to know whether the SVR
    value it returned is already an index we re-check the track index directly.
    """
    from vitaldb_aki.data.tracks import tid_for

    detail: dict[str, Any] = {}

    # ---- path 1 & 2: a direct SVR/SVRI track is present --------------------
    svr_mean = _to_float((fluid_row or {}).get("fluid_svr_mean"))
    has_svri_track = tid_for(cfg, cid, "EV1000/SVRI") is not None
    has_svr_track = tid_for(cfg, cid, "EV1000/SVR") is not None

    if svr_mean is not None and has_svr_track:
        # fluid_responsiveness prioritises EV1000/SVR (raw resistance) -> index it.
        if bsa is not None:
            svri = round(svr_mean * bsa, 4)
            detail["svr_raw"] = svr_mean
            return svri, "EV1000/SVR * BSA", detail
        # No BSA: fall through to SVRI-track or CO path; keep raw as a last resort.
        detail["svr_raw_no_bsa"] = svr_mean
    if svr_mean is not None and has_svri_track and not has_svr_track:
        # Only an SVRI track present -> fluid_responsiveness returned the INDEX.
        detail["svri_direct"] = svr_mean
        return round(svr_mean, 4), "EV1000/SVRI direct", detail

    # ---- path 3: compute from CO + MAP + CVP -------------------------------
    co_mean = _to_float((fluid_row or {}).get("fluid_co_mean"))
    if co_mean is None or co_mean <= 0:
        # last-resort raw SVR with no BSA (path-2 fallback) if we had one
        if svr_mean is not None and bsa is None and has_svr_track:
            return None, "unindexed (no BSA, no CO)", {"svr_raw": svr_mean}
        return None, "none", detail
    if bsa is None:
        return None, "none (no BSA for CO-derived index)", detail

    map_mean = _track_mean(cfg, cid, MAP_TRACK, t_start, t_end, 20.0, 200.0)
    cvp_mean = _track_mean(cfg, cid, CVP_TRACK, t_start, t_end, -5.0, 40.0)
    if map_mean is None:
        return None, "none (no MAP for CO-derived SVRI)", detail
    if cvp_mean is None:
        cvp_mean = DEFAULT_CVP_MMHG
        detail["cvp_default"] = DEFAULT_CVP_MMHG
    svr_raw = 80.0 * (map_mean - cvp_mean) / co_mean
    if not (SVR_MIN <= svr_raw <= SVR_MAX):
        detail["svr_raw_out_of_range"] = round(svr_raw, 2)
        # keep it but flag -- a wildly out-of-range derived SVR is suspect
    svri = round(svr_raw * bsa, 4)
    detail.update({"map_mean": round(map_mean, 3), "cvp_mean": round(cvp_mean, 3),
                   "co_mean": round(co_mean, 4), "svr_derived": round(svr_raw, 2)})
    return svri, "80*(MAP-CVP)/CO * BSA", detail


def _track_mean(cfg, cid, tname, t_start, t_end, vmin, vmax):
    """Time-weighted mean of a numeric monitor track over [t_start, t_end] with a
    physiologic gate.  Reuses fluid_responsiveness's window/weight helpers.  None
    if the track is absent / unusable."""
    from vitaldb_aki.data.tracks import download_track
    from vitaldb_aki.features.fluid_responsiveness import (
        _clip_to_window, _filter_physiologic, _time_weighted_mean,
    )
    raw = download_track(cfg, cid, tname)
    if not raw:
        return None
    s = _filter_physiologic(_clip_to_window(raw, t_start, t_end), vmin, vmax)
    return _time_weighted_mean(s)


# ===========================================================================
# CSV I/O (resumable)
# ===========================================================================
def _existing_caseids(path: str) -> set[str]:
    out: set[str] = set()
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                if cid:
                    out.add(cid)
    except Exception:
        pass
    return out


def _append_rows(path, rows, fieldnames):
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_size_demo(cache_dir):
    """{caseid: {height_cm, weight_kg, age, sex_male, bsa_m2}} from the feature
    matrix (preferred) with a cases.csv fallback for height/weight."""
    out: dict[str, dict[str, Any]] = {}
    fm = os.path.join(cache_dir, FEATURE_MATRIX_FILE)
    if os.path.exists(fm):
        with open(fm, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                if not cid:
                    continue
                h = _to_float(r.get("height_cm"))
                w = _to_float(r.get("weight_kg"))
                out[cid] = {
                    "height_cm": h, "weight_kg": w,
                    "age": _to_float(r.get("age")),
                    "sex_male": _to_float(r.get("sex_male")),
                    "bsa_m2": bsa_mosteller(h, w),
                }
    # cases.csv fallback for any case missing height/weight.
    cp = os.path.join(cache_dir, CASES_FILE)
    if os.path.exists(cp):
        with open(cp, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "") or r.get("﻿caseid", "")).strip()
                if not cid:
                    continue
                rec = out.setdefault(cid, {})
                if rec.get("height_cm") is None:
                    rec["height_cm"] = _to_float(r.get("height"))
                if rec.get("weight_kg") is None:
                    rec["weight_kg"] = _to_float(r.get("weight"))
                if rec.get("bsa_m2") is None:
                    rec["bsa_m2"] = bsa_mosteller(rec.get("height_cm"),
                                                  rec.get("weight_kg"))
                if rec.get("age") is None:
                    rec["age"] = _to_float(r.get("age"))
                if rec.get("sex_male") is None:
                    sx = str(r.get("sex", "")).strip().upper()
                    rec["sex_male"] = (1.0 if sx in ("M", "1", "MALE")
                                       else 0.0 if sx in ("F", "0", "FEMALE")
                                       else None)
    return out


# ===========================================================================
# MAIN
# ===========================================================================
def main(limit: int | None = None):
    from common.config import load_yaml
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.data.client import fetch_cases
    from vitaldb_aki.features import aline_morphology as _aline
    from vitaldb_aki.features import cross_waveform as _cross
    from vitaldb_aki.features import fluid_responsiveness as _fluid

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cache_dir = _resolve_cache_dir(cfg)
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(cache_dir, OUT_CSV)
    trks_path = os.path.join(cache_dir, "trks.csv")

    # Smoke-test cap: env var or --limit.
    if limit is None:
        env = os.environ.get("VASOVAL_SMOKE_N")
        if env:
            try:
                limit = int(env)
            except ValueError:
                limit = None

    cohort, svr_first = build_cohort(trks_path)
    print(f"[vaso_val] cohort: {len(cohort)} cases (ART AND a CO/SVR monitor); "
          f"{len(svr_first)} carry a DIRECT EV1000/SVR or SVRI (extracted first)",
          flush=True)
    if limit is not None:
        cohort = cohort[:limit]
        print(f"[vaso_val] SMOKE CAP active -> only {len(cohort)} cases this run",
              flush=True)

    done = _existing_caseids(out_path)
    todo = [c for c in cohort if c not in done]
    print(f"[vaso_val] {len(done)} already in {OUT_CSV}; {len(todo)} to go",
          flush=True)

    if not todo:
        _write_done(cache_dir, len(cohort), len(done))
        return

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}
    size_demo = _load_size_demo(cache_dir)

    # Column set: caseid + waveform-tone features (aline) + cross + fluid + the
    # derived measured-SVRI block + size/demo controls.
    aline_cols = [s.name for s in _aline.SPECS]
    cross_cols = [s.name for s in _cross.SPECS]
    fluid_cols = [s.name for s in _fluid.SPECS]
    derived_cols = ["svri_measured", "svri_source", "has_direct_svr",
                    "height_cm", "weight_kg", "age", "sex_male", "bsa_m2"]
    fieldnames = (["caseid"] + aline_cols + cross_cols + fluid_cols + derived_cols)

    svr_first_set = set(svr_first)
    buffer: list[dict[str, Any]] = []
    n_new = 0
    for i, cid in enumerate(todo, 1):
        row: dict[str, Any] = {"caseid": cid}
        try:
            aline_out = _aline.extract(cfg, cases_by_id, [cid]).get(cid, {})
            cross_out = _cross.extract(cfg, cases_by_id, [cid]).get(cid, {})
            fluid_out = _fluid.extract(cfg, cases_by_id, [cid]).get(cid, {})
            row.update(aline_out)
            row.update(cross_out)
            row.update(fluid_out)

            sd = size_demo.get(cid, {})
            bsa = sd.get("bsa_m2")
            case = cases_by_id.get(cid)
            t_start = t_end = None
            if case is not None:
                t_start, t_end = _fluid._intraop_window(case)
            svri, src, _detail = _measured_svri(cfg, cid, fluid_out, bsa,
                                                 t_start, t_end)
            row["svri_measured"] = svri
            row["svri_source"] = src
            row["has_direct_svr"] = 1 if cid in svr_first_set else 0
            row["height_cm"] = sd.get("height_cm")
            row["weight_kg"] = sd.get("weight_kg")
            row["age"] = sd.get("age")
            row["sex_male"] = sd.get("sex_male")
            row["bsa_m2"] = bsa
            buffer.append(row)
            n_new += 1
        except Exception as exc:  # never let one bad case abort a long run
            print(f"[vaso_val]   case {cid} FAILED: {type(exc).__name__}: {exc}",
                  flush=True)
        finally:
            # STREAM/PURGE: drop the big SNUADC waveforms + monitor tracks so disk
            # stays bounded (discovery + aline jobs share the volume).
            for tn in (_BIG_SNUADC_TRACKS + _MONITOR_TRACKS):
                try:
                    _T.purge_track(cfg, cid, tn)
                except Exception:
                    pass

        if len(buffer) >= FLUSH_EVERY:
            _append_rows(out_path, buffer, fieldnames)
            buffer = []
            print(f"[vaso_val]   progress {i}/{len(todo)} "
                  f"(+{n_new} new; {len(done) + n_new}/{len(cohort)} total)",
                  flush=True)

    if buffer:
        _append_rows(out_path, buffer, fieldnames)
        print(f"[vaso_val]   final flush ({len(done) + n_new}/{len(cohort)} total)",
              flush=True)

    total = _existing_caseids(out_path)
    if len(set(cohort) - total) == 0:
        _write_done(cache_dir, len(cohort), len(total))
    else:
        print(f"[vaso_val] EXTRACT partial: {len(total)}/{len(cohort)} "
              "(resume to finish)", flush=True)


def _write_done(cache_dir, n_cohort, n_extracted):
    path = os.path.join(cache_dir, DONE_MARKER)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n_cohort": n_cohort, "n_extracted": n_extracted}, fh, indent=2)
    print(f"[vaso_val] EXTRACT complete -> {path}", flush=True)


if __name__ == "__main__":
    _limit = None
    argv = sys.argv[1:]
    for k, a in enumerate(argv):
        if a == "--limit" and k + 1 < len(argv):
            try:
                _limit = int(argv[k + 1])
            except ValueError:
                _limit = None
        elif a.startswith("--limit="):
            try:
                _limit = int(a.split("=", 1)[1])
            except ValueError:
                _limit = None
    main(limit=_limit)
