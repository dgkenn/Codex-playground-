"""independent_svr_validation.py -- the CIRCULARITY-CLEAN validation of the
arterial-waveform vascular-tone index for the VitalDB-AKI study.

THE ATTACK BEING DEFEATED
-------------------------
Pivot 2 (waveform tone -> measured SVRI, docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md)
validated the A-line WAVEFORM tone index against EV1000/Vigileo "measured" SVR.
But EV1000/Vigileo (FloTrac/Vigileo algorithm) compute CO -- and therefore SVR =
80*(MAP-CVP)/CO -- by PULSE-CONTOUR analysis of the ARTERIAL WAVEFORM ITSELF. So
the "measured SVR" is NOT independent of the predictor: it is itself derived from
the same arterial waveform that the tone index is read from. The headline
correlation (waveform-derived tone  vs  waveform-derived SVR) may be CIRCULAR. A
reviewer kills the finding on this alone.

THE DEFENSE (this module)
-------------------------
Validate the SAME waveform tone index against SVR computed from a cardiac-output
source that is INDEPENDENT of the arterial waveform:

  * Vigilance/CO  -- pulmonary-artery-catheter THERMODILUTION (gold standard CO,
    measured by a thermistor in the PA, has NOTHING to do with the radial A-line),
  * CardioQ/CO    -- esophageal DOPPLER (descending-aorta flow velocity x area;
    also independent of the radial arterial pressure waveform).

  SVR_INDEP = 80 * (MAP_mean - CVP_mean) / CO_mean    [dyn*s*cm^-5]

with CO from the independent monitor, MAP from Solar8000/ART_MBP, CVP from
Solar8000/CVP (default 5 mmHg if absent). If the waveform tone index still
predicts SVR_INDEP, the tone->resistance measurement is REAL, not circular. If it
COLLAPSES to ~0, the EV1000 correlation was circular -> honest retraction.

COHORT (built from cache/trks.csv -- NO download to build the list)
-------------------------------------------------------------------
caseids with SNUADC/ART AND (Vigilance/CO OR CardioQ/CO).  ~90 cases
(~75 also carry Solar8000/CVP).  Vigilance (thermodilution) is preferred over
CardioQ when both are present (PAC thermodilution is the cleaner reference).

PER CASE
--------
  * features/aline_morphology.extract + features/cross_waveform.extract ->
    the waveform tone features (tau / diastolic / MAP / form-factor / AIx / HR /
    coupling) -- the SAME features as vasoplegia_validation_extract.py.
  * the INDEPENDENT CO track (Vigilance/CO preferred, else CardioQ/CO),
    Solar8000/CVP, Solar8000/ART_MBP (MAP) -> SVR_INDEP over the intraop window.
  * PURGE the big SNUADC waveform CSVs + the monitor tracks after each case so
    disk stays bounded (mirrors vasoplegia_validation_extract.py).

STREAM/PURGE + RESUMABLE + a small WORKERS thread pool: identical pattern to
vasoplegia_validation_extract.py.  Writes cache/independent_svr_validation.csv.

VALIDATE (mirror analysis/svri_morphology_hostile_review.py, target = SVR_INDEP):
  - Spearman(waveform tone index, SVR_INDEP) + bootstrap CI.
  - Strict NON-pressure morphology incremental R^2 over ALL pressure scalars (OOF Ridge).
  - Permutation null (shuffle SVR_INDEP).
  - Body-size adjustment.
  - tau partial-Spearman vs SVR_INDEP given MAP, and given MAP+HR (the airtight test).
  - EV1000-vs-independent comparison (r~0.49 EV1000 baseline from the hostile review).

Heavy deps (numpy/scipy/sklearn via the feature modules) are lazy; this module
imports with the stdlib only.

Run (from repo root /home/user/Codex-playground-/):
    python3 vitaldb_aki/analysis/independent_svr_validation.py            # extract + validate
    python3 vitaldb_aki/analysis/independent_svr_validation.py --validate-only
    python3 vitaldb_aki/analysis/independent_svr_validation.py --limit 50
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

SEED = 20260626

# ---------------------------------------------------------------------------
# Constants (binding)
# ---------------------------------------------------------------------------
ART_TRACK_NAME = "SNUADC/ART"

# INDEPENDENT cardiac-output sources -- NOT derived from the arterial waveform.
# Vigilance = PAC thermodilution (preferred); CardioQ = esophageal Doppler.
INDEP_CO_TRACKS = ("Vigilance/CO", "CardioQ/CO")   # preference order

MAP_TRACK = "Solar8000/ART_MBP"
CVP_TRACK = "Solar8000/CVP"
DEFAULT_CVP_MMHG = 5.0          # normal-range CVP assumed when no CVP track

# Physiologic gates.
CO_MIN, CO_MAX = 1.0, 15.0      # L/min  (gate the independent CO)
SVR_INDEP_MIN, SVR_INDEP_MAX = 300.0, 5000.0   # dyn*s*cm^-5 (gate computed SVR)
MAP_MIN, MAP_MAX = 20.0, 200.0
CVP_MIN, CVP_MAX = -5.0, 40.0

OUT_CSV = "independent_svr_validation.csv"
RESULTS_JSON = "independent_svr_validation_results.json"
DONE_MARKER = "_independent_svr_validation_done.json"
DOC = "INDEPENDENT_SVR_VALIDATION.md"
FEATURE_MATRIX_FILE = "feature_matrix.csv"
CASES_FILE = "cases.csv"

# Big SNUADC waveform tracks to purge after each case (bounds disk).
_BIG_SNUADC_TRACKS = ("SNUADC/ART", "SNUADC/PLETH", "SNUADC/ECG_II")
# Monitor / numeric tracks to purge after each case too.
_MONITOR_TRACKS = ("Vigilance/CO", "CardioQ/CO", MAP_TRACK, CVP_TRACK)


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
    """Body-surface area (m^2) via Mosteller: sqrt(height_cm * weight_kg / 3600)."""
    h = _to_float(height_cm)
    w = _to_float(weight_kg)
    if h is None or w is None or h <= 0 or w <= 0:
        return None
    return round(math.sqrt(h * w / 3600.0), 6)


def build_cohort(trks_path: str) -> tuple[list[str], dict[str, str]]:
    """Build the circularity-clean cohort from cache/trks.csv WITHOUT any download.

    Returns (ordered_cohort, co_source_by_id) where:
      * ordered_cohort = caseids with SNUADC/ART AND (Vigilance/CO OR CardioQ/CO),
        deterministic numeric-by-caseid order.
      * co_source_by_id = {caseid: 'Vigilance/CO' | 'CardioQ/CO'} preferring
        Vigilance (PAC thermodilution) when both are present.
    """
    art: set[str] = set()
    has_track: dict[str, set[str]] = {tn: set() for tn in INDEP_CO_TRACKS}
    with open(trks_path, "r", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            cid = str(r.get("caseid", "")).strip()
            tn = str(r.get("tname", "")).strip()
            if not cid or not tn:
                continue
            if tn == ART_TRACK_NAME:
                art.add(cid)
            elif tn in has_track:
                has_track[tn].add(cid)

    co_source: dict[str, str] = {}
    for cid in art:
        for tn in INDEP_CO_TRACKS:    # preference order: Vigilance, then CardioQ
            if cid in has_track[tn]:
                co_source[cid] = tn
                break

    def _numkey(c: str):
        try:
            return (0, int(c))
        except ValueError:
            return (1, c)

    ordered = sorted(co_source.keys(), key=_numkey)
    return ordered, co_source


# ===========================================================================
# Per-case INDEPENDENT-CO-derived SVR
# ===========================================================================
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


def _svr_indep(cfg, cid, co_track, t_start, t_end):
    """Compute SVR_INDEP = 80*(MAP_mean - CVP_mean)/CO_mean using the INDEPENDENT
    CO source (PAC thermodilution / esophageal Doppler).

    Returns (svr_indep, detail_dict).  svr_indep is None if no path succeeds or it
    falls outside the physiologic gate.
    """
    detail: dict[str, Any] = {"co_source": co_track}
    co_mean = _track_mean(cfg, cid, co_track, t_start, t_end, CO_MIN, CO_MAX)
    if co_mean is None or co_mean <= 0:
        detail["fail"] = "no_indep_co"
        return None, detail
    map_mean = _track_mean(cfg, cid, MAP_TRACK, t_start, t_end, MAP_MIN, MAP_MAX)
    if map_mean is None:
        detail["fail"] = "no_map"
        return None, detail
    cvp_mean = _track_mean(cfg, cid, CVP_TRACK, t_start, t_end, CVP_MIN, CVP_MAX)
    if cvp_mean is None:
        cvp_mean = DEFAULT_CVP_MMHG
        detail["cvp_default"] = DEFAULT_CVP_MMHG
    svr = 80.0 * (map_mean - cvp_mean) / co_mean
    detail.update({"map_mean": round(map_mean, 3), "cvp_mean": round(cvp_mean, 3),
                   "co_mean": round(co_mean, 4), "svr_raw": round(svr, 2)})
    if not (SVR_INDEP_MIN <= svr <= SVR_INDEP_MAX):
        detail["fail"] = "svr_out_of_range"
        return None, detail
    return round(svr, 4), detail


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
    """{caseid: {height_cm, weight_kg, age, sex_male, bsa_m2}} from feature_matrix
    (preferred) with a cases.csv fallback for height/weight."""
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
                out[cid] = {"height_cm": h, "weight_kg": w,
                            "age": _to_float(r.get("age")),
                            "sex_male": _to_float(r.get("sex_male")),
                            "bsa_m2": bsa_mosteller(h, w)}
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
# EXTRACT
# ===========================================================================
def extract(limit: int | None = None):
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

    if limit is None:
        env = os.environ.get("INDEPSVR_SMOKE_N")
        if env:
            try:
                limit = int(env)
            except ValueError:
                limit = None

    cohort, co_source = build_cohort(trks_path)
    n_vig = sum(1 for v in co_source.values() if v == "Vigilance/CO")
    n_cq = sum(1 for v in co_source.values() if v == "CardioQ/CO")
    print(f"[indep_svr] cohort: {len(cohort)} cases (ART AND independent-CO); "
          f"{n_vig} Vigilance(thermodilution), {n_cq} CardioQ(esoph.Doppler)",
          flush=True)
    if limit is not None:
        cohort = cohort[:limit]
        print(f"[indep_svr] LIMIT active -> only {len(cohort)} cases this run",
              flush=True)

    done = _existing_caseids(out_path)
    todo = [c for c in cohort if c not in done]
    print(f"[indep_svr] {len(done)} already in {OUT_CSV}; {len(todo)} to go",
          flush=True)
    if not todo:
        _write_done(cache_dir, len(cohort), len(done))
        return

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}
    size_demo = _load_size_demo(cache_dir)

    aline_cols = [s.name for s in _aline.SPECS]
    cross_cols = [s.name for s in _cross.SPECS]
    derived_cols = ["svr_indep", "co_source", "svr_map_mean", "svr_cvp_mean",
                    "svr_co_mean", "cvp_defaulted",
                    "_diastolic_over_map", "_map_dia_form_factor",
                    "height_cm", "weight_kg", "age", "sex_male", "bsa_m2"]
    fieldnames = ["caseid"] + aline_cols + cross_cols + derived_cols

    def _extract_one(cid: str):
        row: dict[str, Any] = {"caseid": cid}
        try:
            aline_out = _aline.extract(cfg, cases_by_id, [cid]).get(cid, {})
            cross_out = _cross.extract(cfg, cases_by_id, [cid]).get(cid, {})
            row.update(aline_out)
            row.update(cross_out)

            # derived tone components (mirror vasoplegia_biomarker family-C)
            dbp = _to_float(aline_out.get("art_dbp_mean"))
            amap = _to_float(aline_out.get("art_map_mean"))
            pp = _to_float(aline_out.get("art_pulse_pressure_mean"))
            row["_diastolic_over_map"] = ((dbp / amap)
                                          if (dbp is not None and amap and amap > 0)
                                          else None)
            row["_map_dia_form_factor"] = (((amap - dbp) / pp)
                                           if (amap is not None and dbp is not None
                                               and pp and pp > 0) else None)

            sd = size_demo.get(cid, {})
            case = cases_by_id.get(cid)
            t_start = t_end = None
            if case is not None:
                t_start, t_end = _fluid._intraop_window(case)
            svr, detail = _svr_indep(cfg, cid, co_source[cid], t_start, t_end)
            row["svr_indep"] = svr
            row["co_source"] = co_source[cid]
            row["svr_map_mean"] = detail.get("map_mean")
            row["svr_cvp_mean"] = detail.get("cvp_mean")
            row["svr_co_mean"] = detail.get("co_mean")
            row["cvp_defaulted"] = 1 if "cvp_default" in detail else 0
            row["height_cm"] = sd.get("height_cm")
            row["weight_kg"] = sd.get("weight_kg")
            row["age"] = sd.get("age")
            row["sex_male"] = sd.get("sex_male")
            row["bsa_m2"] = sd.get("bsa_m2")
            return row
        except Exception as exc:
            print(f"[indep_svr]   case {cid} FAILED: {type(exc).__name__}: {exc}",
                  flush=True)
            return None
        finally:
            for tn in (_BIG_SNUADC_TRACKS + _MONITOR_TRACKS):
                try:
                    _T.purge_track(cfg, cid, tn)
                except Exception:
                    pass

    import concurrent.futures
    workers = max(1, int(os.environ.get("INDEPSVR_WORKERS", "4")))
    n_new = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for chunk_start in range(0, len(todo), workers):
            chunk = todo[chunk_start:chunk_start + workers]
            rows = [r for r in ex.map(_extract_one, chunk) if r is not None]
            n_new += len(rows)
            if rows:
                _append_rows(out_path, rows, fieldnames)
            print(f"[indep_svr]   progress {min(chunk_start + workers, len(todo))}/"
                  f"{len(todo)} (+{n_new} new; {len(done) + n_new}/{len(cohort)} "
                  f"total) [parallel x{workers}]", flush=True)

    total = _existing_caseids(out_path)
    if len(set(cohort) - total) == 0:
        _write_done(cache_dir, len(cohort), len(total))
    else:
        print(f"[indep_svr] EXTRACT partial: {len(total)}/{len(cohort)} "
              "(resume to finish)", flush=True)


def _write_done(cache_dir, n_cohort, n_extracted):
    path = os.path.join(cache_dir, DONE_MARKER)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n_cohort": n_cohort, "n_extracted": n_extracted}, fh, indent=2)
    print(f"[indep_svr] EXTRACT complete -> {path}", flush=True)


# ===========================================================================
# VALIDATE  (mirror svri_morphology_hostile_review.py, target = SVR_INDEP)
# ===========================================================================
# Strictly non-pressure-LEVEL morphology (shape/timing/rate/coupling), same set as
# the hostile review.
PRESSURE = ["art_map_mean", "art_sbp_mean", "art_dbp_mean",
            "art_pulse_pressure_mean", "art_pulse_pressure_sd"]
MORPH_STRICT = ["art_tau_decay_mean", "art_aug_index_mean", "art_hr_mean",
                "art_hr_sd", "pat_mean_ms", "pat_sd_ms", "pat_slope",
                "art_ppg_amp_corr", "central_peripheral_decoupling", "brs_mean",
                "cardiopulm_coherence", "resp_sbp_coupling"]
# Pure SHAPE only (no HR, no flow): the airtight tone-shape set.
PURE_SHAPE = ["art_tau_decay_mean", "art_aug_index_mean"]
SIZE = ["weight_kg", "bsa_m2", "age", "sex_male"]
# The waveform TONE INDEX components (vasoplegia_biomarker family-C), each NEGATED
# (low tau / low diastolic / low form-factor / low AIx = LOW tone = LOW resistance).
TONE_COMPONENTS = {"art_tau_decay_mean": -1.0, "_diastolic_over_map": -1.0,
                   "_map_dia_form_factor": -1.0, "art_aug_index_mean": -1.0}

# EV1000 baseline (from the prior hostile review on EV1000/Vigileo SVRI).
EV1000_BASELINE = {
    "headline_oof_r": 0.4561,
    "strict_morph_incremental_r2_over_pressure": 0.1109,
    "perm_p": 0.005,
    "tau_partial_given_MAP": 0.1613,
    "pure_shape_incremental_over_pressure_plus_HR": -0.007,
    "source": "docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md (EV1000/Vigileo SVRI, "
              "pulse-contour CO -> CIRCULAR with the arterial waveform)",
}


def _zscore_index(df, components):
    """Build the waveform tone index = mean of NEGATED z-scores of the components
    (mirrors vasoplegia_biomarker).  Returns a numpy array (NaN where all-missing)."""
    import numpy as np, pandas as pd
    cols = [c for c in components if c in df.columns]
    if not cols:
        return None
    Z = []
    for c in cols:
        x = pd.to_numeric(df[c], errors="coerce").to_numpy(float)
        mu, sd = np.nanmean(x), np.nanstd(x)
        z = (x - mu) / sd if sd > 1e-9 else np.zeros_like(x)
        Z.append(components[c] * z)
    Z = np.vstack(Z)
    with np.errstate(invalid="ignore"):
        idx = np.nanmean(Z, axis=0)
    return idx


def _oof(df, cols, y, seed=SEED, n_splits=5, n_rep=5):
    import numpy as np, pandas as pd
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return {"r": None, "r2": None}
    X = df[cols].apply(lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    rs, r2s = [], []
    for rep in range(n_rep):
        oof = np.full(len(y), np.nan)
        for tr, te in KFold(n_splits, shuffle=True,
                            random_state=seed + rep).split(X):
            pipe = Pipeline([("i", SimpleImputer(strategy="median")),
                             ("s", StandardScaler()),
                             ("m", RidgeCV(alphas=(0.1, 1, 10, 100)))])
            pipe.fit(X[tr], y[tr]); oof[te] = pipe.predict(X[te])
        msk = ~np.isnan(oof)
        if msk.sum() > 5 and np.std(oof[msk]) > 1e-9:
            rs.append(float(stats.spearmanr(oof[msk], y[msk])[0]))
            ssr = float(np.sum((y[msk] - oof[msk]) ** 2))
            sst = float(np.sum((y[msk] - y[msk].mean()) ** 2))
            r2s.append(1 - ssr / sst if sst > 0 else float("nan"))
    return {"r": round(float(np.mean(rs)), 4) if rs else None,
            "r2": round(float(np.nanmean(r2s)), 4) if r2s else None,
            "n_features": len(cols)}


def _partial(xa, xb, given):
    """partial Spearman corr(xa, xb | given-columns) via rank-residualisation.
    `given` is a 2D array (n x k).  Residualise ranks of xa, xb on `given` (with
    intercept) by OLS, then Spearman of residuals."""
    import numpy as np
    from scipy import stats

    def _rank_resid(v):
        rv = stats.rankdata(v)
        G = np.c_[np.ones(len(v)), given]
        beta, *_ = np.linalg.lstsq(G, rv, rcond=None)
        return rv - G @ beta

    ra, rb = _rank_resid(xa), _rank_resid(xb)
    if np.std(ra) < 1e-9 or np.std(rb) < 1e-9:
        return float("nan")
    return float(stats.spearmanr(ra, rb)[0])


def validate():
    import numpy as np, pandas as pd
    from scipy import stats
    cache = os.path.join(_ROOT, "vitaldb_aki", "cache")
    docs = os.path.join(_ROOT, "vitaldb_aki", "docs")
    csv_path = os.path.join(cache, OUT_CSV)
    if not os.path.exists(csv_path):
        print(f"[indep_svr] no {OUT_CSV} yet -- run extract first.", flush=True)
        return

    v = pd.read_csv(csv_path)
    y_all = pd.to_numeric(v.get("svr_indep"), errors="coerce")
    keep = y_all.between(SVR_INDEP_MIN, SVR_INDEP_MAX)
    v = v[keep].reset_index(drop=True)
    y = y_all[keep].reset_index(drop=True).to_numpy(float)
    n = len(y)
    n_vig = int((v.get("co_source") == "Vigilance/CO").sum()) if "co_source" in v else 0
    n_cq = int((v.get("co_source") == "CardioQ/CO").sum()) if "co_source" in v else 0

    res: dict[str, Any] = {"seed": SEED, "target": "SVR_INDEP (independent-CO)",
                           "n": n, "n_vigilance_thermodilution": n_vig,
                           "n_cardioq_doppler": n_cq,
                           "ev1000_baseline": EV1000_BASELINE, "attacks": {}}
    print(f"[indep_svr] N(independent-CO, physiologic SVR)={n} "
          f"({n_vig} Vigilance, {n_cq} CardioQ)", flush=True)
    if n < 20:
        res["verdict"] = (f"INSUFFICIENT_N (N={n}); extraction still running / too "
                          "few clean cases. Re-run --validate-only as N grows.")
        _write_results(res, cache, docs)
        print(f"[indep_svr] {res['verdict']}", flush=True)
        return

    # ---- 0. HEADLINE: Spearman(tone index, SVR_INDEP) + bootstrap CI ----------
    tone = _zscore_index(v, TONE_COMPONENTS)
    msk0 = np.isfinite(tone) & np.isfinite(y)
    rho = float(stats.spearmanr(tone[msk0], y[msk0])[0])
    rng_bs = np.random.default_rng(SEED)
    tv, yv = tone[msk0], y[msk0]
    bs = []
    for _ in range(2000):
        idx = rng_bs.integers(0, len(yv), len(yv))
        if np.std(tv[idx]) > 1e-9 and np.std(yv[idx]) > 1e-9:
            bs.append(float(stats.spearmanr(tv[idx], yv[idx])[0]))
    ci = [round(float(np.percentile(bs, 2.5)), 4),
          round(float(np.percentile(bs, 97.5)), 4)] if bs else [None, None]
    # permutation null on the headline Spearman
    null0 = []
    for _ in range(2000):
        null0.append(abs(float(stats.spearmanr(tv, rng_bs.permutation(yv))[0])))
    rho_perm_p = round((1 + sum(1 for z in null0 if z >= abs(rho))) /
                       (1 + len(null0)), 4)
    res["headline"] = {
        "tone_index_vs_svr_indep_spearman": round(rho, 4),
        "n_used": int(msk0.sum()), "bootstrap_ci_95": ci,
        "perm_p": rho_perm_p,
        "hypothesised_sign": "NEGATIVE (high vasoplegia index = low tone = low SVR)",
        "in_hypothesised_direction": bool(rho < 0),
        "note": "waveform TONE/VASOPLEGIA INDEX (mean of NEGATED z of "
                "tau/diastolic/form-factor/AIx) vs SVR from an INDEPENDENT CO source "
                "(thermodilution / esoph. Doppler). By construction a HIGH index = "
                "LOW tone, so it should correlate NEGATIVELY with resistance; tau "
                "(below) is the same signal with the natural POSITIVE sign."}

    # ---- A. CIRCULARITY: strict non-pressure morph incremental over pressure --
    p = _oof(v, PRESSURE, y); ps = _oof(v, PRESSURE + MORPH_STRICT, y)
    incr = round((ps["r2"] or 0) - (p["r2"] or 0), 4)
    res["attacks"]["A_circularity"] = {
        "pressure_only_r2": p["r2"], "pressure_plus_strict_morph_r2": ps["r2"],
        "strict_morph_incremental_r2_over_pressure": incr,
        "full_model_oof_r": ps["r"], "pass": bool(incr > 0.02),
        "note": "strict non-pressure morphology adds R2 over ALL pressure scalars "
                "on INDEPENDENT-CO SVR -> not circular with the arterial waveform"}

    # ---- B. OVERFITTING: permutation null on the full OOF model ---------------
    full = ps
    rng = np.random.default_rng(SEED)
    null = []
    for _ in range(200):
        rr = _oof(v, PRESSURE + MORPH_STRICT, rng.permutation(y), n_rep=2)["r"]
        if rr is not None:
            null.append(abs(rr))
    real = abs(full["r"] or 0)
    pval = round((1 + sum(1 for z in null if z >= real)) / (1 + len(null)), 4)
    res["attacks"]["B_overfitting"] = {
        "real_oof_r": full["r"],
        "perm_null_r_mean": round(float(np.mean(null)), 4) if null else None,
        "perm_null_r_95pct": round(float(np.percentile(null, 95)), 4) if null else None,
        "perm_p": pval, "pass": bool(pval < 0.05)}

    # ---- C. BODY-SIZE confounding --------------------------------------------
    base = _oof(v, PRESSURE + SIZE, y)
    base_m = _oof(v, PRESSURE + SIZE + MORPH_STRICT, y)
    incr_c = round((base_m["r2"] or 0) - (base["r2"] or 0), 4)
    res["attacks"]["C_body_size"] = {
        "pressure_plus_size_r2": base["r2"], "plus_morph_r2": base_m["r2"],
        "morph_incremental_r2_over_pressure_and_size": incr_c,
        "pass": bool(incr_c > 0.02)}

    # ---- D. tau partial-Spearman vs SVR_INDEP given MAP, and given MAP+HR ------
    tau = pd.to_numeric(v.get("art_tau_decay_mean"), errors="coerce").to_numpy(float)
    mapm = pd.to_numeric(v.get("art_map_mean"), errors="coerce").to_numpy(float)
    hr = pd.to_numeric(v.get("art_hr_mean"), errors="coerce").to_numpy(float)
    m1 = np.isfinite(tau) & np.isfinite(mapm) & np.isfinite(y)
    m2 = m1 & np.isfinite(hr)
    tau_raw = round(float(stats.spearmanr(tau[m1], y[m1])[0]), 4) if m1.sum() > 5 else None
    tau_pMAP = (round(_partial(tau[m1], y[m1], mapm[m1].reshape(-1, 1)), 4)
                if m1.sum() > 5 else None)
    tau_pMAPHR = (round(_partial(tau[m2], y[m2],
                                 np.c_[mapm[m2], hr[m2]]), 4)
                  if m2.sum() > 5 else None)
    # pure-shape (tau,AIx) incremental over pressure + HR (the airtight test)
    pHR = _oof(v, PRESSURE + ["art_hr_mean"], y)
    pHR_shape = _oof(v, PRESSURE + ["art_hr_mean"] + PURE_SHAPE, y)
    pure_incr = round((pHR_shape["r2"] or 0) - (pHR["r2"] or 0), 4)
    res["attacks"]["D_tau_mechanism"] = {
        "tau_vs_svr_indep_spearman": tau_raw,
        "tau_partial_given_MAP": tau_pMAP,
        "tau_partial_given_MAP_and_HR": tau_pMAPHR,
        "pressure_plus_HR_r2": pHR["r2"],
        "pressure_plus_HR_plus_pure_shape_r2": pHR_shape["r2"],
        "pure_shape_incremental_r2_over_pressure_plus_HR": pure_incr,
        "note": "the airtight test -- does tone SHAPE (tau/AIx, no HR/flow) add over "
                "pressure+HR against an INDEPENDENT-CO SVR?"}

    # ---- E. STABILITY: bootstrap CI on the full OOF r -------------------------
    rng2 = np.random.default_rng(SEED + 1)
    bse = []
    for _ in range(300):
        idx = rng2.integers(0, n, n)
        rr = _oof(v.iloc[idx].reset_index(drop=True), PRESSURE + MORPH_STRICT,
                  y[idx], n_rep=2)["r"]
        if rr is not None:
            bse.append(rr)
    res["attacks"]["E_stability"] = {
        "oof_r": full["r"],
        "bootstrap_ci": [round(float(np.percentile(bse, 2.5)), 4),
                         round(float(np.percentile(bse, 97.5)), 4)] if bse else [None, None]}

    # ---- COMPARISON: EV1000 (circular) vs INDEPENDENT-CO ----------------------
    res["comparison_ev1000_vs_independent"] = {
        "ev1000_headline_oof_r": EV1000_BASELINE["headline_oof_r"],
        "independent_full_oof_r": full["r"],
        "ev1000_strict_morph_incr_r2_over_pressure":
            EV1000_BASELINE["strict_morph_incremental_r2_over_pressure"],
        "independent_strict_morph_incr_r2_over_pressure": incr,
        "ev1000_tau_partial_given_MAP": EV1000_BASELINE["tau_partial_given_MAP"],
        "independent_tau_partial_given_MAP": tau_pMAP,
        "independent_tone_index_spearman": round(rho, 4)}

    # ---- VERDICT -------------------------------------------------------------
    # Sign-aware: the vasoplegia INDEX must correlate NEGATIVELY with SVR (high
    # index = low tone = low resistance); tau must be POSITIVE. CI excludes 0 iff
    # ci[0]*ci[1] > 0. The headline "survives" only if it is significant AND in the
    # hypothesised (negative) direction.
    A = res["attacks"]
    ci_excludes_0 = bool(ci[0] is not None and ci[0] * ci[1] > 0)
    headline_survives = bool(rho < -0.2 and rho_perm_p < 0.05 and ci_excludes_0)
    # The incremental/OOF Ridge models report |r|; pair them with the sign-correct
    # single-feature tau partial (must be POSITIVE) so a sign-flip can't masquerade
    # as a pass.
    incr_survives = bool(A["A_circularity"]["pass"] and A["B_overfitting"]["pass"]
                         and (tau_pMAP is not None and tau_pMAP > 0))
    res["headline_survives"] = headline_survives
    res["incremental_survives"] = incr_survives

    if headline_survives and incr_survives:
        verdict = (
            "SURVIVES the circularity attack. The waveform TONE INDEX predicts SVR "
            f"from an INDEPENDENT cardiac-output source (Spearman {rho:.3f}, 95% CI "
            f"{ci}, perm p={rho_perm_p}); strict non-pressure morphology adds incr "
            f"R2 {incr} over ALL pressure scalars (perm p={pval}) against a CO that "
            "is NOT derived from the arterial waveform. The EV1000 correlation was "
            "NOT merely circular -- the tone->resistance signal is real. "
            f"(EV1000 headline r {EV1000_BASELINE['headline_oof_r']} vs "
            f"independent full-model r {full['r']}.)")
    elif headline_survives or incr_survives:
        verdict = (
            "PARTIALLY survives. The waveform tone index shows a real association "
            f"with independent-CO SVR (Spearman {rho:.3f}, CI {ci}, perm p="
            f"{rho_perm_p}; strict-morph incr R2 {incr}, perm p={pval}), but it is "
            "ATTENUATED relative to the EV1000 result -- some of the original "
            f"correlation (EV1000 r {EV1000_BASELINE['headline_oof_r']}) was likely "
            "inflated by circularity. The finding stands as an A-line SVR estimator "
            "but the effect size against a truly independent CO is smaller.")
    else:
        verdict = (
            "DOES NOT survive -- the EV1000 correlation was CIRCULAR. Against an "
            f"INDEPENDENT cardiac-output source the waveform tone index correlation "
            f"COLLAPSES (Spearman {rho:.3f}, CI {ci}, perm p={rho_perm_p}; "
            f"strict-morph incr R2 {incr}, perm p={pval}). The original "
            f"EV1000 r~{EV1000_BASELINE['headline_oof_r']} was waveform-derived tone "
            "vs waveform-derived SVR -- HONEST RETRACTION of the measurement claim "
            "is warranted.")
    res["verdict"] = verdict
    _write_results(res, cache, docs)
    print(f"[indep_svr] VERDICT: {verdict}", flush=True)


def _write_results(res, cache, docs):
    json.dump(res, open(os.path.join(cache, RESULTS_JSON), "w"), indent=2,
              default=float)
    L = [
        "# INDEPENDENT-CO validation of the arterial-waveform vascular-tone index",
        "## (READ FIRST) the circularity attack this defeats",
        "",
        "**Pivot 2** (docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md) validated the A-line "
        "WAVEFORM tone index against **EV1000/Vigileo \"measured\" SVR**. But "
        "EV1000/Vigileo (FloTrac) compute cardiac output -- and hence "
        "SVR = 80*(MAP-CVP)/CO -- by **PULSE-CONTOUR analysis of the arterial "
        "waveform itself**. So the \"measured SVR\" is *not independent* of the "
        "predictor: both the tone index and the reference SVR are read from the "
        "SAME radial arterial waveform. The headline correlation (waveform-derived "
        "tone vs waveform-derived SVR) may be **CIRCULAR** -- a reviewer can kill "
        "the finding on this alone.",
        "",
        "**The defense (this analysis):** re-run the validation against SVR computed "
        "from a cardiac-output source that is **INDEPENDENT of the arterial "
        "waveform**:",
        "- **Vigilance/CO** -- PA-catheter **thermodilution** (a PA thermistor; "
        "nothing to do with the radial A-line), preferred;",
        "- **CardioQ/CO** -- **esophageal Doppler** (descending-aorta flow).",
        "",
        "`SVR_INDEP = 80 * (MAP_mean - CVP_mean) / CO_indep_mean`  (MAP = "
        "Solar8000/ART_MBP, CVP = Solar8000/CVP, default 5 mmHg if absent; CO gated "
        f"{CO_MIN}-{CO_MAX} L/min, SVR gated {int(SVR_INDEP_MIN)}-{int(SVR_INDEP_MAX)}).",
        "",
        "If the waveform tone index still predicts SVR_INDEP, the measurement is "
        "**real, not circular**. If it collapses to ~0, the EV1000 result **was "
        "circular** -> honest retraction.",
        "",
    ]
    if str(res.get("verdict", "")).startswith("INSUFFICIENT"):
        L += [f"## Status: {res['verdict']}",
              f"N so far = {res.get('n')}. Extraction is resumable; re-run "
              "`--validate-only` as N grows."]
        open(os.path.join(docs, DOC), "w").write("\n".join(L) + "\n")
        return

    h = res["headline"]; A = res["attacks"]; cmp = res["comparison_ev1000_vs_independent"]
    D = A["D_tau_mechanism"]
    L += [
        f"## Cohort",
        f"N = **{res['n']}** circularity-clean cases "
        f"({res['n_vigilance_thermodilution']} Vigilance/thermodilution + "
        f"{res['n_cardioq_doppler']} CardioQ/Doppler), each with SNUADC/ART AND an "
        f"independent-CO monitor. Seed {res['seed']}.",
        "",
        "## Results vs an INDEPENDENT cardiac-output SVR",
        f"- **Headline Spearman(tone index, SVR_INDEP) = {h['tone_index_vs_svr_indep_spearman']}** "
        f"(95% bootstrap CI {h['bootstrap_ci_95']}, perm p = {h['perm_p']}; "
        f"N used {h['n_used']}).",
        f"- **A. Non-circularity:** strict NON-pressure morphology incremental R^2 over "
        f"ALL pressure scalars = **{A['A_circularity']['strict_morph_incremental_r2_over_pressure']}** "
        f"(pressure-only R^2 {A['A_circularity']['pressure_only_r2']} -> "
        f"+morph R^2 {A['A_circularity']['pressure_plus_strict_morph_r2']}; full OOF r "
        f"{A['A_circularity']['full_model_oof_r']}) -> "
        f"{'PASS' if A['A_circularity']['pass'] else 'FAIL'}.",
        f"- **B. Overfitting:** OOF r {A['B_overfitting']['real_oof_r']} vs permutation "
        f"null mean {A['B_overfitting']['perm_null_r_mean']} "
        f"(95th {A['B_overfitting']['perm_null_r_95pct']}), perm p = "
        f"**{A['B_overfitting']['perm_p']}** -> "
        f"{'PASS' if A['B_overfitting']['pass'] else 'FAIL'}.",
        f"- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex "
        f"= **{A['C_body_size']['morph_incremental_r2_over_pressure_and_size']}** -> "
        f"{'PASS' if A['C_body_size']['pass'] else 'FAIL'}.",
        f"- **D. tau partial-Spearman vs SVR_INDEP:** raw {D['tau_vs_svr_indep_spearman']}, "
        f"**given MAP = {D['tau_partial_given_MAP']}**, "
        f"**given MAP+HR = {D['tau_partial_given_MAP_and_HR']}** (the airtight test); "
        f"pure-shape(tau,AIx) incremental R^2 over pressure+HR = "
        f"**{D['pure_shape_incremental_r2_over_pressure_plus_HR']}**.",
        f"- **E. Stability:** OOF r {A['E_stability']['oof_r']}, bootstrap CI "
        f"{A['E_stability']['bootstrap_ci']}.",
        "",
        "## EV1000 (potentially circular) vs INDEPENDENT-CO",
        "| metric | EV1000 (pulse-contour CO) | INDEPENDENT CO (thermodil./Doppler) |",
        "|---|---|---|",
        f"| headline OOF r (full model) | {cmp['ev1000_headline_oof_r']} | {cmp['independent_full_oof_r']} |",
        f"| tone-index Spearman | (r~0.49 region) | {cmp['independent_tone_index_spearman']} |",
        f"| strict-morph incr R^2 over pressure | {cmp['ev1000_strict_morph_incr_r2_over_pressure']} | {cmp['independent_strict_morph_incr_r2_over_pressure']} |",
        f"| tau partial given MAP | {cmp['ev1000_tau_partial_given_MAP']} | {cmp['independent_tau_partial_given_MAP']} |",
        "",
        f"## HONEST VERDICT",
        "",
        res["verdict"],
        "",
        "## Limitations",
        "- Single-centre (SNUADC); the independent-CO monitor subset is small and "
        "selected (sicker cases get a PAC / esoph. Doppler).",
        "- CVP defaults to 5 mmHg when no Solar8000/CVP track is present (a "
        "documented assumption); thermodilution/Doppler CO is itself noisy and "
        "intermittent (thermodilution boluses) -> SVR_INDEP is a noisier target than "
        "the continuous pulse-contour SVR, which BIASES correlations DOWNWARD. A "
        "preserved correlation here is therefore conservative; an attenuated one is "
        "partly measurement noise, not necessarily circularity.",
    ]
    open(os.path.join(docs, DOC), "w").write("\n".join(L) + "\n")


# ===========================================================================
# MAIN
# ===========================================================================
def main(argv):
    limit = None
    validate_only = extract_only = False
    for k, a in enumerate(argv):
        if a == "--validate-only":
            validate_only = True
        elif a == "--extract-only":
            extract_only = True
        elif a == "--limit" and k + 1 < len(argv):
            try:
                limit = int(argv[k + 1])
            except ValueError:
                limit = None
        elif a.startswith("--limit="):
            try:
                limit = int(a.split("=", 1)[1])
            except ValueError:
                limit = None
    if not validate_only:
        extract(limit=limit)
    if not extract_only:
        validate()


if __name__ == "__main__":
    main(sys.argv[1:])
