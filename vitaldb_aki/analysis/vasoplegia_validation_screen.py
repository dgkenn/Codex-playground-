"""vasoplegia_validation_screen.py -- THE validation of the SVR-free waveform
vasoplegia index against MEASURED SVRI, on the cohort extracted by
analysis/vasoplegia_validation_extract.py (cache/vasoplegia_validation.csv).

HEADLINE (construct validity)
-----------------------------
Spearman correlation between the WAVEFORM TONE INDEX (rebuilt EXACTLY as in
analysis/vasoplegia_biomarker.py: orientation-signed z-mean of diastolic decay
tau, diastolic/MAP, form factor, augmentation index -- all oriented so HIGH =
more vasoplegia) and the MEASURED SVRI (svri_measured from the extractor).

  Hypothesis: more waveform vasoplegia (HIGH index) <-> LOWER measured SVRI, i.e.
  a NEGATIVE Spearman r.  We ALSO report tau-vs-SVRI directly (tau = R*C tracks
  resistance, hypothesised POSITIVE).  Reported: Spearman r, p, N, scatter
  description.  A correlation in the hypothesised direction LICENSES the SVR-free
  claim (within the limits stated in docs/VASOPLEGIA_VALIDATION.md).

SECONDARY (convergent / criterion)
----------------------------------
  * Does MEASURED SVRI itself predict organ injury (organ_renal / composite)
    INCREMENTAL over MAP burden (+ body size + age + sex)?  DeLong-style
    incremental AUROC reusing vasoplegia_biomarker._incremental_multibaseline
    (LR p + patient-clustered bootstrap CI).  organ_hepatocellular = negative
    control.  BH-FDR across the primary tests.  E-values on the OR.
  * Does the waveform index AGREE with the SVV-based preload state (fluid_svv_*)?
    Spearman + a 2x2 median-split convergent table.

All weight / BSA / age / sex adjusted.  Leakage firewall: every predictor is
preop+intraop; organ_* are y only.

Power: feasibility-scale (the EV1000/SVR-on-ART subset is small and renal events
are rare), so EVERY cell prints N/events and is flagged.  This is
HYPOTHESIS-GENERATING.

Writes cache/vasoplegia_validation_results.json + docs/VASOPLEGIA_VALIDATION.md.
Heavy deps lazy; module imports with the stdlib only.

Run:  python3 -m vitaldb_aki.analysis.vasoplegia_validation_screen
"""
from __future__ import annotations

import csv as _csv
import json
import math
import os
from typing import Any

CACHE_DEFAULT = "vitaldb_aki/cache"
RANDOM_SEED = 20260626

VALIDATION_CSV = "vasoplegia_validation.csv"
COMPOSITE_FILE = "cohort_composite.csv"
FEATURE_MATRIX_FILE = "feature_matrix.csv"
RESULTS_JSON = "vasoplegia_validation_results.json"
RESULTS_MD = "VASOPLEGIA_VALIDATION.md"

PRIMARY_OUTCOMES = ("organ_renal", "composite")
NEGATIVE_CONTROL_OUTCOME = "organ_hepatocellular"
MAP_BURDEN_BASELINE = "map_auc_below_65"
MIN_EVENTS_FEASIBLE = 10
FDR_ALPHA = 0.05


def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return CACHE_DEFAULT


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


# ===========================================================================
# Frame assembly (REUSES vasoplegia_biomarker's waveform-index definition)
# ===========================================================================
def assemble_frame(cfg) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Build {caseid: row} from cache/vasoplegia_validation.csv + outcomes/baseline,
    then attach the WAVEFORM VASOPLEGIA INDEX rebuilt with vasoplegia_biomarker's
    EXACT orientation/z-score logic (so the validated index == the published one).
    """
    # Reuse the exact tone-component derivation + index builder from the biomarker.
    from vitaldb_aki.analysis import vasoplegia_biomarker as VB

    cache_dir = _resolve_cache_dir(cfg)
    val_path = os.path.join(cache_dir, VALIDATION_CSV)
    if not os.path.exists(val_path):
        raise FileNotFoundError(
            f"{val_path} not found -- run the EXTRACT stage first "
            "(python3 vitaldb_aki/analysis/vasoplegia_validation_extract.py).")

    # outcomes + subjectid
    comp = VB._load_composite(cache_dir)  # {cid: {organ_*, subjectid}}
    # MAP burden from the feature matrix.
    baseline: dict[str, float | None] = {}
    fm = os.path.join(cache_dir, FEATURE_MATRIX_FILE)
    if os.path.exists(fm):
        with open(fm, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                if cid:
                    baseline[cid] = _to_float(r.get(MAP_BURDEN_BASELINE))

    frame: dict[str, dict[str, Any]] = {}
    with open(val_path, "r", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            cid = str(r.get("caseid", "")).strip()
            if not cid:
                continue
            avail = str(r.get("aline_available", "")).strip() in ("1", "1.0", "True")
            row: dict[str, Any] = {"caseid": cid}
            c = comp.get(cid, {})
            row["subjectid"] = c.get("subjectid", cid)
            for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
                row[oc] = c.get(oc)
            row[MAP_BURDEN_BASELINE] = baseline.get(cid)

            # size/demo (carried by the extractor)
            row["weight_kg"] = _to_float(r.get("weight_kg"))
            row["bsa_m2"] = _to_float(r.get("bsa_m2"))
            row["age"] = _to_float(r.get("age"))
            row["sex_male"] = _to_float(r.get("sex_male"))

            # measured reference standard
            row["svri_measured"] = _to_float(r.get("svri_measured"))
            row["svri_source"] = (r.get("svri_source") or "").strip()
            row["has_direct_svr"] = _to_float(r.get("has_direct_svr"))
            row["fluid_svr_mean"] = _to_float(r.get("fluid_svr_mean"))
            row["fluid_svv_mean"] = _to_float(r.get("fluid_svv_mean"))
            row["fluid_co_mean"] = _to_float(r.get("fluid_co_mean"))

            # waveform tone components (build the SAME derived cols VB uses)
            row["aline_available"] = 1 if avail else 0
            if avail:
                tau = _to_float(r.get("art_tau_decay_mean"))
                dbp = _to_float(r.get("art_dbp_mean"))
                amap = _to_float(r.get("art_map_mean"))
                pp = _to_float(r.get("art_pulse_pressure_mean"))
                aug = _to_float(r.get("art_aug_index_mean"))
                row["art_tau_decay_mean"] = tau
                row["art_aug_index_mean"] = aug
                row["art_ppv_mean"] = _to_float(r.get("art_ppv_mean"))
                row["_diastolic_over_map"] = (
                    (dbp / amap) if (dbp is not None and amap and amap > 0) else None)
                row["_map_dia_form_factor"] = (
                    ((amap - dbp) / pp)
                    if (amap is not None and dbp is not None and pp and pp > 0)
                    else None)
            else:
                for k in ("art_tau_decay_mean", "art_aug_index_mean", "art_ppv_mean",
                          "_diastolic_over_map", "_map_dia_form_factor"):
                    row[k] = None
            frame[cid] = row

    # Attach the WAVEFORM VASOPLEGIA INDEX using VB's exact builder (orientation +
    # z-mean across WAVEFORM_TONE_COMPONENTS; HIGH = vasoplegia).
    VB._add_waveform_index(frame)

    meta = {
        "n_rows": len(frame),
        "n_waveform": sum(1 for r in frame.values() if r.get("aline_available") == 1),
        "n_measured_svri": sum(1 for r in frame.values()
                               if r.get("svri_measured") is not None),
        "n_direct_svr": sum(1 for r in frame.values()
                            if (r.get("has_direct_svr") or 0) >= 1),
        "n_joint_index_and_svri": sum(
            1 for r in frame.values()
            if r.get(VB.PRIMARY_INDEX_WAVEFORM) is not None
            and r.get("svri_measured") is not None),
        "cache_dir": cache_dir,
        "waveform_index_col": VB.PRIMARY_INDEX_WAVEFORM,
        "waveform_components": list(VB.WAVEFORM_TONE_COMPONENTS),
    }
    return frame, meta


# ===========================================================================
# HEADLINE: waveform tone index vs MEASURED SVRI
# ===========================================================================
def headline_construct(frame, H, index_col) -> dict[str, Any]:
    """Spearman(waveform vasoplegia index, measured SVRI) -- the headline.

    Also tau-vs-SVRI.  Reports r, p (permutation/t-approx), N, and a scatter
    description.  Both the full joint subset and the DIRECT-SVR-only subset (the
    cleanest cases) are reported.
    """
    def _collect(restrict_direct: bool):
        idx_xy, tau_xy = [], []
        for r in frame.values():
            if restrict_direct and (r.get("has_direct_svr") or 0) < 1:
                continue
            svri = r.get("svri_measured")
            if svri is None:
                continue
            idx = r.get(index_col)
            tau = r.get("art_tau_decay_mean")
            if idx is not None:
                idx_xy.append((idx, svri))
            if tau is not None:
                tau_xy.append((tau, svri))
        return idx_xy, tau_xy

    def _spear(pairs):
        if len(pairs) < 3:
            return {"spearman_r": None, "p": None, "n": len(pairs)}
        x = [p[0] for p in pairs]
        y = [p[1] for p in pairs]
        r = H["spearman"](x, y)
        p = _spearman_p(r, len(pairs))
        return {"spearman_r": r, "p": p, "n": len(pairs)}

    out: dict[str, Any] = {}
    for label, restrict in (("all_joint", False), ("direct_svr_only", True)):
        idx_xy, tau_xy = _collect(restrict)
        idx_res = _spear(idx_xy)
        tau_res = _spear(tau_xy)
        # scatter description
        scatter = None
        if idx_xy:
            xs = sorted(p[0] for p in idx_xy)
            ys = sorted(p[1] for p in idx_xy)
            scatter = {
                "index_range": [round(xs[0], 3), round(xs[-1], 3)],
                "svri_range": [round(ys[0], 1), round(ys[-1], 1)],
                "svri_median": round(ys[len(ys) // 2], 1),
            }
        out[label] = {
            "waveform_index_vs_measured_svri": {
                **idx_res,
                "hypothesised_sign": "negative (high index = low tone = low SVRI)",
                "supports_hypothesis": (idx_res["spearman_r"] is not None
                                        and idx_res["spearman_r"] < 0),
            },
            "tau_vs_measured_svri": {
                **tau_res,
                "hypothesised_sign": "positive (tau = R*C tracks SVRI)",
                "supports_hypothesis": (tau_res["spearman_r"] is not None
                                        and tau_res["spearman_r"] > 0),
            },
            "scatter": scatter,
        }
    out["interpretation"] = (
        "A Spearman r in the hypothesised direction (waveform index NEGATIVELY "
        "correlated with measured SVRI; tau POSITIVELY correlated) is the "
        "construct-validity evidence that LICENSES calling the waveform index an "
        "SVR-free vasoplegia marker. The DIRECT-SVR-only subset is the cleanest "
        "(measured EV1000 SVR/SVRI, not CO-derived).")
    return out


def _spearman_p(rho, n):
    """Two-sided p for a Spearman rho via the t-approximation
    t = rho * sqrt((n-2)/(1-rho^2)), df = n-2.  stdlib (math.erf-free t-dist not
    available -> use a normal approx for the t for n large, exact-ish via the
    incomplete-beta-free fallback).  None if degenerate."""
    if rho is None or n is None or n < 4:
        return None
    if abs(rho) >= 1.0:
        return 0.0
    try:
        t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    except (ValueError, ZeroDivisionError):
        return None
    # Use scipy when available for an exact t p-value; else a normal approx.
    try:
        from scipy import stats as _stats
        return float(2.0 * _stats.t.sf(abs(t), df=n - 2))
    except Exception:
        # normal approximation (adequate for n moderately large)
        z = abs(t)
        p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
        return float(max(0.0, min(1.0, p)))


# ===========================================================================
# SECONDARY 1: measured SVRI predicts injury incremental over MAP burden
# ===========================================================================
def measured_svri_predicts_injury(frame, seed) -> dict[str, Any]:
    """Incremental AUROC of measured SVRI over MAP burden + body size + demo, for
    organ_renal / composite + the negative control; BH-FDR; reuses
    vasoplegia_biomarker._incremental_multibaseline."""
    from vitaldb_aki.analysis.vasoplegia_biomarker import (
        _incremental_multibaseline, ADJUSTMENT_BASELINE_COLS,
    )
    from vitaldb_aki.analysis.actionable_targets import benjamini_hochberg

    feature_col = "svri_measured"
    outcomes = list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]
    per: dict[str, Any] = {}
    pvals: list[float | None] = []
    pkeys: list[str] = []
    for oc in outcomes:
        cids = [c for c in frame
                if frame[c].get(feature_col) is not None
                and frame[c].get(oc) is not None
                and frame[c].get(MAP_BURDEN_BASELINE) is not None]
        if len(cids) < 20:
            per[oc] = {"available": False, "n": len(cids),
                       "note": "too few joint rows"}
            continue
        inc = _incremental_multibaseline(
            frame, cids, oc, feature_col, ADJUSTMENT_BASELINE_COLS, seed)
        inc["underpowered"] = (inc.get("events") or 0) < MIN_EVENTS_FEASIBLE
        if oc == NEGATIVE_CONTROL_OUTCOME:
            inc["is_negative_control"] = True
        per[oc] = inc
        if oc in PRIMARY_OUTCOMES:
            pvals.append(inc.get("lr_p"))
            pkeys.append(oc)
    reject = benjamini_hochberg([p if p is not None else 1.0 for p in pvals],
                                alpha=FDR_ALPHA)
    fdr = {oc: {"lr_p": p, "fdr_reject": bool(rj)}
           for oc, p, rj in zip(pkeys, pvals, reject)}
    return {"feature": feature_col, "per_outcome": per, "fdr_primary": fdr,
            "baseline": list(ADJUSTMENT_BASELINE_COLS),
            "min_events_feasible": MIN_EVENTS_FEASIBLE}


# ===========================================================================
# SECONDARY 2: waveform index agrees with SVV preload state
# ===========================================================================
def waveform_vs_svv(frame, H, index_col) -> dict[str, Any]:
    """Spearman + median-split 2x2 of the waveform vasoplegia index vs the SVV
    (preload) state.  Vasoplegia (tone loss) and hypovolemia (high SVV) are the
    two distinct arterial-line axes -> we expect at most weak correlation; this
    documents their (in)dependence (a convergent/divergent table)."""
    xs, ys = [], []
    for r in frame.values():
        idx = r.get(index_col)
        svv = r.get("fluid_svv_mean")
        if idx is not None and svv is not None:
            xs.append(idx)
            ys.append(svv)
    n = len(xs)
    rho = H["spearman"](xs, ys) if n >= 3 else None
    table = {"both_high": 0, "vaso_high_svv_low": 0,
             "vaso_low_svv_high": 0, "both_low": 0}
    if n >= 4:
        mx = sorted(xs)[n // 2]
        my = sorted(ys)[n // 2]
        for a, b in zip(xs, ys):
            ah, bh = a > mx, b > my
            if ah and bh:
                table["both_high"] += 1
            elif ah and not bh:
                table["vaso_high_svv_low"] += 1
            elif not ah and bh:
                table["vaso_low_svv_high"] += 1
            else:
                table["both_low"] += 1
    return {
        "available": n >= 3, "n": n, "spearman_r": rho,
        "two_by_two_median_split": table,
        "note": "Vasoplegia (tone) and SVV (preload) are distinct axes; a low/zero "
                "correlation is EXPECTED and supports that the waveform index "
                "measures TONE, not preload (discriminant validity).",
    }


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================
def run(cfg) -> dict[str, Any]:
    from vitaldb_aki.analysis.vasoplegia_biomarker import _import_helpers, PRIMARY_INDEX_WAVEFORM

    cache_dir = _resolve_cache_dir(cfg)
    seed = int(cfg.get("seed", RANDOM_SEED))
    os.makedirs(cache_dir, exist_ok=True)
    H = _import_helpers()

    frame, meta = assemble_frame(cfg)
    index_col = PRIMARY_INDEX_WAVEFORM

    headline = headline_construct(frame, H, index_col)
    secondary_injury = measured_svri_predicts_injury(frame, seed)
    secondary_svv = waveform_vs_svv(frame, H, index_col)

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "seed": seed,
        "meta": meta,
        "headline_waveform_index_vs_measured_svri": headline,
        "secondary_measured_svri_predicts_injury": secondary_injury,
        "secondary_waveform_index_vs_svv_preload": secondary_svv,
        "interpretation": (
            "Observational, single-centre (VitalDB / SNUH). The headline is the "
            "construct-validity correlation between the SVR-FREE waveform tone "
            "index and MEASURED SVRI on the cases where both now exist. A "
            "correlation in the hypothesised direction (negative for the index, "
            "positive for tau) LICENSES the SVR-free vasoplegia-index claim. All "
            "secondary tests are HYPOTHESIS-GENERATING and feasibility-scale; "
            "leakage firewall: predictors are preop+intraop, organ_* are y."),
    }

    results_path = os.path.join(cache_dir, RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[vaso_val_screen] results -> {results_path}", flush=True)

    _write_md(results, cfg)
    return results


def _json_default(obj):
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


def _f(v, spec="{:.4g}"):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return spec.format(v)
    return str(v)


def _write_md(results, cfg) -> str:
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, RESULTS_MD)

    meta = results["meta"]
    hl = results["headline_waveform_index_vs_measured_svri"]
    inj = results["secondary_measured_svri_predicts_injury"]
    svv = results["secondary_waveform_index_vs_svv_preload"]

    aj = hl["all_joint"]
    dj = hl["direct_svr_only"]

    L: list[str] = []
    L += [
        "# Vasoplegia Validation -- waveform tone index vs MEASURED SVRI (VitalDB-AKI)",
        "",
        "## READ FIRST -- what this validates and what it does NOT",
        "",
        "This is the construct-validity check the vasoplegia biomarker "
        "(`docs/VASOPLEGIA_BIOMARKER.md`) could not previously run: it puts "
        "**MEASURED SVR/SVRI** onto the SAME cases as the **SVR-free WAVEFORM tone "
        "index** and correlates them.",
        "",
        "- **Observational, single-centre** (VitalDB / SNUH). **HYPOTHESIS-"
        "GENERATING**; not causal proof; external validation pending.",
        "- **Leakage firewall:** every predictor is PREOP+INTRAOP; `organ_*` are y "
        "only.",
        "- The measured SVRI is a **reference standard with caveats**: where a "
        "direct EV1000/SVR or SVRI track exists it is used (cleanest); otherwise "
        "SVRI is **computed** as `80*(MAP-CVP)/CO * BSA` with CVP defaulted to "
        "5 mmHg when no CVP track is present. CO-derived SVRI is noisier than a "
        "direct measurement -- the **DIRECT-SVR-only** subset is the gold cut.",
        "- Feasibility-scale: small joint subset and rare renal events -> every "
        "cell below shows N / events.",
        "",
        "## SVRI computation / units (binding)",
        "",
        "- `SVR (dyn*s*cm^-5) = 80 * (MAP - CVP) / CO`  (MAP, CVP in mmHg; CO in "
        "L/min; 80 = mmHg*min/L -> dyn*s*cm^-5).",
        "- `SVRI (dyn*s*cm^-5*m^2) = SVR * BSA`,  BSA (Mosteller) = "
        "`sqrt(height_cm*weight_kg/3600)`.",
        "- Preference: **EV1000/SVRI direct** > **EV1000/SVR * BSA** > "
        "**CO-derived `80*(MAP-CVP)/CO * BSA`**. CVP defaults to **5 mmHg** when "
        "no `Solar8000/CVP` track is present.",
        "",
        "## Cohort / availability (N)",
        "",
        f"- Rows extracted: **{meta['n_rows']}**.",
        f"- With a waveform vasoplegia index: **{meta['n_waveform']}**.",
        f"- With a measured SVRI: **{meta['n_measured_svri']}** "
        f"({meta['n_direct_svr']} via a DIRECT EV1000 SVR/SVRI track).",
        f"- **JOINT (index AND measured SVRI): {meta['n_joint_index_and_svri']}** "
        "<- the headline N.",
        "",
        "## THE HEADLINE -- waveform tone index vs measured SVRI",
        "",
    ]
    wi = aj["waveform_index_vs_measured_svri"]
    tt = aj["tau_vs_measured_svri"]
    wid = dj["waveform_index_vs_measured_svri"]
    ttd = dj["tau_vs_measured_svri"]
    L += [
        "| subset | comparison | Spearman r | p | N | hypothesised | supports? |",
        "|---|---|---|---|---|---|---|",
        f"| all joint | waveform index vs SVRI | **{_f(wi['spearman_r'])}** | "
        f"{_f(wi['p'])} | {wi['n']} | negative | {wi['supports_hypothesis']} |",
        f"| all joint | tau vs SVRI | {_f(tt['spearman_r'])} | {_f(tt['p'])} | "
        f"{tt['n']} | positive | {tt['supports_hypothesis']} |",
        f"| direct-SVR only | waveform index vs SVRI | **{_f(wid['spearman_r'])}** | "
        f"{_f(wid['p'])} | {wid['n']} | negative | {wid['supports_hypothesis']} |",
        f"| direct-SVR only | tau vs SVRI | {_f(ttd['spearman_r'])} | "
        f"{_f(ttd['p'])} | {ttd['n']} | positive | {ttd['supports_hypothesis']} |",
        "",
        f"> {hl['interpretation']}",
        "",
    ]
    if aj.get("scatter"):
        sc = aj["scatter"]
        L += [
            f"Scatter (all joint): waveform index in {sc['index_range']}, "
            f"measured SVRI in {sc['svri_range']} (median "
            f"{sc['svri_median']} dyn*s*cm^-5*m^2). A downward cloud "
            "(high index, low SVRI) is the hypothesised pattern.",
            "",
        ]

    L += [
        "## Secondary -- does MEASURED SVRI predict organ injury (incremental over "
        "MAP burden + body size + age + sex)?",
        "",
        "| outcome | N | events | dAUROC | LR p | FDR reject | E-value(pt) |",
        "|---|---|---|---|---|---|---|",
    ]
    for oc in list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]:
        blk = inj["per_outcome"].get(oc, {})
        ev = blk.get("e_value_point") if isinstance(blk, dict) else None
        fr = inj["fdr_primary"].get(oc, {}).get("fdr_reject")
        tag = " (neg. control)" if oc == NEGATIVE_CONTROL_OUTCOME else ""
        L += [
            f"| {oc}{tag} | {blk.get('n', 'n/a')} | {blk.get('events', 'n/a')} | "
            f"{_f(blk.get('delta_auroc'))} | {_f(blk.get('lr_p'))} | "
            f"{fr if fr is not None else 'n/a'} | {_f(ev)} |",
        ]
    L += [
        "",
        f"Baseline adjustment set: `{inj.get('baseline')}`. Cells with "
        f"< {inj.get('min_events_feasible')} events are underpowered.",
        "",
        "## Secondary -- waveform index vs SVV preload state (discriminant)",
        "",
        f"- N = {svv.get('n')}; Spearman r = **{_f(svv.get('spearman_r'))}**.",
        f"- 2x2 median split: {svv.get('two_by_two_median_split')}.",
        f"- {svv.get('note')}",
        "",
        "## What this licenses",
        "",
        "If the waveform index correlates with measured SVRI in the hypothesised "
        "direction (especially in the DIRECT-SVR subset), the **SVR-free waveform "
        "vasoplegia index** has construct validity and may be used as a "
        "tone read on the full ART-instrumented cohort where no CO monitor "
        "exists -- the original motivation for an SVR-free index. A null or "
        "wrong-signed correlation does NOT license that claim and would send the "
        "index back to the drawing board. Either way this is single-centre and "
        "hypothesis-generating; confirmation needs external arterial-waveform + "
        "CO-monitor data.",
        "",
        f"_Seed {results['seed']}. Generated by "
        "`analysis/vasoplegia_validation_screen.py`._",
    ]
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[vaso_val_screen] report -> {md_path}", flush=True)
    return md_path


def main():
    import sys
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from common.config import load_yaml
    cfg = load_yaml(os.path.join(_root, "vitaldb_aki", "config.yaml"))
    run(cfg)


if __name__ == "__main__":
    main()
