"""aline_fluid_vs_pressor.py -- Phase-0 feasibility: can the ARTERIAL LINE tell you
whether a hypotensive patient needs FLUID or a PRESSOR?

The idea (user's)
-----------------
Use the A-line waveform to PERSONALISE the fluid-vs-pressor decision in a
hypotensive intraoperative patient:

  * A **preload-responsive** patient -- high pulse-pressure variation
    (``art_ppv_mean`` > 13 %, the validated Michard fluid-responsiveness
    cutpoint) -- should be restored by a FLUID bolus. Their stroke volume is on
    the steep part of the Frank-Starling curve.
  * A **vasoplegic** patient -- a blunted MAP response per unit pressor infusion
    (low ``vaso_responsiveness`` OLS slope), often needing multiple agents and
    long pressor durations -- will NOT be restored by fluid and needs a PRESSOR.

If the A-line phenotype identifies WHO benefits from WHICH, and getting the
A-line-INDICATED treatment associates with LESS organ injury, that is a GO for a
gated, separate deep-learning version. THIS module is the runnable, NO-deep-
learning, NO-new-extraction Phase-0 feasibility check.

Two analyses
------------
1. AXIS VALIDATION.
   (a) Does high PPV (>13 %) mark a distinct preload-responsive phenotype
       (descriptives, separation from the rest of the waveform)?
   (b) Does low ``vaso_responsiveness`` co-occur with vasoplegia markers
       (multi-agent support, long pressor duration)?  -- run only if the
       vasoactive-PD axis is present in the matrix; else marked UNAVAILABLE.

2. THE DECISION / CONCORDANCE HTE (the headline).
   Define the A-line-RECOMMENDED treatment per case:
       FLUID   if preload-responsive (high PPV / high SVV)
       PRESSOR if vasoplegic        (low PPV + blunted vaso_responsiveness)
   Define CONCORDANT = the actual management (from actionable_targets'
   download-free fluid-vs-pressor derivation) matched the recommendation.
   Test whether CONCORDANT management associates with LOWER organ injury
   (organ_renal primary, composite secondary) than DISCORDANT, as:
     * an IPTW-adjusted outcome model with a (recommendation x management)
       INTERACTION term,
     * a within-recommendation-stratum RD/RR with bootstrap 95 % CI,
     * E-values for the point + null-nearest CI bound,
     * a negative control (organ_hepatocellular) that must stay null,
     * BH-FDR across the interaction tests.

Honest causal caveat (built into the report)
---------------------------------------------
Confounding by indication is SEVERE here and runs the OPPOSITE way from the usual
worry: clinicians may ALREADY read PPV / pressor-response off the same A-line and
choose accordingly. If they already optimise, concordance is near-universal and a
NULL concordance benefit is EXPECTED. So a positive concordance benefit would be
strong (it means there is still a recoverable gap), whereas a null is consistent
with both "no signal" and "clinicians already optimal" -- it does NOT kill the DL
idea on its own. The report states what a positive vs null result each mean.

Data strategy (inputs are partly in-flight)
-------------------------------------------
Assemble from whatever is available NOW and report N + axis availability at every
step; NEVER block on the enriched matrix and NEVER launch extraction.
  * PPV/preload axis  <- cache/aline_sample.csv (``art_ppv_mean`` etc.), merged on
    caseid.  This is the operational A-line feasibility extraction.
  * vaso_* / fluid_*  <- cache/feature_matrix_enriched.csv IF present, else
    cache/feature_matrix.csv if those columns are present & non-empty, else the
    axis is marked UNAVAILABLE (degrade gracefully -- do not block).
  * management        <- actionable_targets derivations (any_vasopressor, fluid
    tertiles, fluid- vs pressor-predominant; download-free, presence/dose based).
  * outcomes          <- cache/cohort_composite.csv (organ_renal primary,
    composite secondary; negative control organ_hepatocellular).

If PPV coverage is too low (< ~80 cases) the module still runs but flags the whole
analysis PRELIMINARY / INPUTS-PENDING.

Leakage firewall
----------------
Predictors / recommendation / management are PREOP+INTRAOP only; organ_* outcomes
are y, never features.

Heavy deps (numpy/pandas/sklearn) are lazy-imported inside the functions that need
them so the import surface is stdlib-only, matching repo convention.  Run with:
    python3 -m vitaldb_aki.analysis.aline_fluid_vs_pressor      (from repo root)
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

# Reuse the validated pure helpers + IPTW machinery (stdlib import surface).
from vitaldb_aki.analysis.actionable_targets import (
    e_value,
    e_value_ci,
    benjamini_hochberg,
    tertile_assign,
    _resolve_cache_dir,
    _resolve_seed,
    _json_default,
    PHE_COL,
    EPH_COL,
    EPI_COL,
    CRYSTALLOID_COL,
    COLLOID_COL,
    EPH_TO_PHE_EQUIV,
    NEGATIVE_CONTROL_OUTCOME,
    MIN_EVENTS_FOR_POWER,
    N_BOOTSTRAP,
    RANDOM_SEED,
    DEFAULT_PS_COVARIATES,
)

# ---------------------------------------------------------------------------
# Constants -- every threshold named here (config-as-code).
# ---------------------------------------------------------------------------

# Pulse-pressure-variation cutpoint: the validated Michard fluid-responsiveness
# threshold. PPV > 13 % -> preload-responsive (a fluid bolus should raise SV).
PPV_PRELOAD_RESPONSIVE_CUT = 13.0          # %
# SVV (gold-standard preload axis, where present) uses the same 13 % convention.
SVV_PRELOAD_RESPONSIVE_CUT = 13.0          # %

# Vasoplegia from the vasoactive-PD axis: a BLUNTED MAP-vs-pressor slope.
# vaso_responsiveness is the OLS slope of MAP on total pressor-infusion rate;
# "blunted" = at or below this slope (mmHg per normalised infusion unit). A
# vasoplegic circulation does not raise its MAP much per unit pressor.
VASO_RESPONSIVENESS_BLUNTED_CUT = 0.0      # slope <= 0 == no MAP gain per pressor

# Outcomes.
PRIMARY_OUTCOME = "organ_renal"
SECONDARY_OUTCOME = "composite"
PRIMARY_OUTCOMES = (PRIMARY_OUTCOME, SECONDARY_OUTCOME)

# PPV coverage below this -> flag the whole analysis PRELIMINARY / inputs-pending.
MIN_PPV_CASES_FOR_VERDICT = 80

# Body-size normalisation. The /cases pressor totals are RAW (ug, NOT ug/kg) and
# fluid volumes are RAW mL -- both confounded by body size. We normalise dose per
# kg before building the pressor-/fluid-predominant tertiles and add weight + age +
# sex to the IPTW covariate set. PPV/SVV (the preload axis) are intrinsically
# size-independent and are left as-is. BSA (Mosteller) = sqrt(height_cm*weight_kg/3600).
# Candidate body-size columns (first present wins), preferring feature_matrix names.
WEIGHT_COLS = ("weight_kg", "weight")
HEIGHT_COLS = ("height_cm", "height")
BMI_COLS = ("bmi",)
# Extra covariates added to the propensity/adjustment set for size-awareness.
SIZE_AWARE_PS_COVARIATES = ("weight_kg", "age", "sex")

# Candidate column names for each axis, in priority order (first present wins).
PPV_COLS = ("art_ppv_mean",)
PPV_BURDEN_COLS = ("art_ppv_burden_min",)
SVV_COLS = ("fluid_svv_mean", "fluid_svv_max")
VASO_RESPONSIVENESS_COLS = ("vaso_responsiveness",)
VASO_NAGENTS_COLS = ("vaso_n_agents",)
VASO_DURFRAC_COLS = ("vaso_pressor_duration_frac",)
VASO_MAXINF_COLS = ("vaso_max_infusion_norm",)

# Files.
_ALINE_SAMPLE = "aline_sample.csv"
_ENRICHED_MATRIX = "feature_matrix_enriched.csv"
_FEATURE_MATRIX = "feature_matrix.csv"
_CASES_FILE = "cases.csv"
_COMPOSITE_FILE = "cohort_composite.csv"
_RESULTS_JSON = "aline_fluid_vs_pressor_results.json"
_DONE_MARKER = "_aline_fluid_vs_pressor_done.json"


# ===========================================================================
# DATA ASSEMBLY -- merge whatever is available NOW; report N at each step.
# ===========================================================================

def _first_present_col(df, candidates):
    """Return the first candidate column that is present AND has >=1 non-null
    numeric value, else None."""
    import pandas as pd
    for c in candidates:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce")
            if v.notna().any():
                return c
    return None


def assemble_frame(cfg: dict[str, Any]):
    """Assemble the analysis frame from the currently-available caches.

    Returns
    -------
    tuple (df: pd.DataFrame, avail: dict)
        df: one row per case that has PPV AND an outcome row; columns include
            caseid, ppv, ppv_burden, outcomes, /cases exposures+confounders, and
            (if present) the vaso_*/fluid_* axes.
        avail: per-axis availability + N at each merge step (for the report).
    """
    import numpy as np
    import pandas as pd

    cache_dir = _resolve_cache_dir(cfg)
    avail: dict[str, Any] = {"cache_dir": cache_dir, "steps": []}

    def _step(name, **kw):
        avail["steps"].append({"step": name, **kw})

    # --- 1. PPV / preload axis from aline_sample.csv (the operational A-line) ---
    aline_path = os.path.join(cache_dir, _ALINE_SAMPLE)
    if not os.path.exists(aline_path):
        raise RuntimeError(
            f"aline_sample.csv not found at {aline_path}; the PPV axis is the "
            "minimum required input -- nothing to analyse."
        )
    aline = pd.read_csv(aline_path)
    aline.columns = [c.lstrip("﻿") for c in aline.columns]
    ppv_col = _first_present_col(aline, PPV_COLS)
    ppv_burden_col = _first_present_col(aline, PPV_BURDEN_COLS)
    if ppv_col is None:
        raise RuntimeError(
            "aline_sample.csv has no usable PPV column (art_ppv_mean); cannot run."
        )
    df = aline[["caseid"]].copy()
    df["ppv"] = pd.to_numeric(aline[ppv_col], errors="coerce")
    # carry a few morphology columns for axis-validation descriptives.
    for c in ("art_map_mean", "art_pulse_pressure_mean", "art_dpdt_max_mean",
              "art_low_dpdt_burden_min", "art_perfusion_failure_burden_min",
              "aline_available"):
        if c in aline.columns:
            df[c] = pd.to_numeric(aline[c], errors="coerce")
    if ppv_burden_col is not None:
        df["ppv_burden"] = pd.to_numeric(aline[ppv_burden_col], errors="coerce")
    df = df[df["ppv"].notna()].drop_duplicates("caseid").reset_index(drop=True)
    n_ppv = int(len(df))
    _step("ppv_from_aline_sample", n=n_ppv, ppv_col=ppv_col,
          ppv_burden_col=ppv_burden_col)
    avail["preload_ppv"] = {"available": True, "source": _ALINE_SAMPLE,
                            "column": ppv_col, "n": n_ppv}

    # --- 2. vaso_* / fluid_* axes from enriched matrix, else feature_matrix ----
    enriched_path = os.path.join(cache_dir, _ENRICHED_MATRIX)
    matrix_path = os.path.join(cache_dir, _FEATURE_MATRIX)
    matrix_used = None
    mat = None
    if os.path.exists(enriched_path):
        mat = pd.read_csv(enriched_path)
        matrix_used = _ENRICHED_MATRIX
    elif os.path.exists(matrix_path):
        mat = pd.read_csv(matrix_path)
        matrix_used = _FEATURE_MATRIX

    vaso_axis = {"available": False, "source": matrix_used,
                 "note": "vaso_responsiveness column absent/empty in matrix"}
    svv_axis = {"available": False, "source": matrix_used,
                "note": "SVV column absent/empty in matrix"}

    if mat is not None:
        mat.columns = [c.lstrip("﻿") for c in mat.columns]
        vaso_resp_col = _first_present_col(mat, VASO_RESPONSIVENESS_COLS)
        vaso_n_col = _first_present_col(mat, VASO_NAGENTS_COLS)
        vaso_dur_col = _first_present_col(mat, VASO_DURFRAC_COLS)
        vaso_max_col = _first_present_col(mat, VASO_MAXINF_COLS)
        svv_col = _first_present_col(mat, SVV_COLS)

        carry = {"caseid": "caseid"}
        if vaso_resp_col:
            carry[vaso_resp_col] = "vaso_responsiveness"
        if vaso_n_col:
            carry[vaso_n_col] = "vaso_n_agents"
        if vaso_dur_col:
            carry[vaso_dur_col] = "vaso_pressor_duration_frac"
        if vaso_max_col:
            carry[vaso_max_col] = "vaso_max_infusion_norm"
        if svv_col:
            carry[svv_col] = "svv"
        keep = [c for c in carry if c in mat.columns]
        if len(keep) > 1:
            sub = mat[keep].rename(columns=carry).drop_duplicates("caseid")
            add = [c for c in sub.columns if c != "caseid" and c not in df.columns]
            if add:
                df = df.merge(sub[["caseid"] + add], on="caseid", how="left")

        if vaso_resp_col is not None and "vaso_responsiveness" in df.columns:
            vaso_axis = {
                "available": True, "source": matrix_used,
                "responsiveness_col": vaso_resp_col,
                "n_nonnull": int(pd.to_numeric(df["vaso_responsiveness"],
                                               errors="coerce").notna().sum()),
                "has_n_agents": "vaso_n_agents" in df.columns,
                "has_duration_frac": "vaso_pressor_duration_frac" in df.columns,
            }
        if svv_col is not None and "svv" in df.columns:
            svv_axis = {"available": True, "source": matrix_used,
                        "column": svv_col,
                        "n_nonnull": int(pd.to_numeric(df["svv"],
                                                       errors="coerce").notna().sum())}
    _step("vaso_fluid_axes", matrix_used=matrix_used,
          vaso_available=vaso_axis["available"], svv_available=svv_axis["available"])
    avail["vasoplegia_vaso_responsiveness"] = vaso_axis
    avail["preload_svv"] = svv_axis

    # --- 3. /cases exposures + confounders (management + PS covariates) --------
    cases_path = os.path.join(cache_dir, _CASES_FILE)
    cases_cols_merged: list[str] = []
    if os.path.exists(cases_path):
        cases = pd.read_csv(cases_path)
        cases.columns = [c.lstrip("﻿") for c in cases.columns]
        want = [
            PHE_COL, EPH_COL, EPI_COL, CRYSTALLOID_COL, COLLOID_COL,
            "age", "sex", "asa", "preop_htn", "preop_dm", "preop_cr",
            "intraop_ebl", "optype", "opstart", "opend", "anestart", "aneend",
            "weight", "height", "bmi",          # body size for dose normalisation
        ]
        add = [c for c in want if c in cases.columns and c not in df.columns]
        if add:
            df = df.merge(cases[["caseid"] + add], on="caseid", how="left")
            cases_cols_merged = add
    _step("cases_exposures_confounders", n=int(len(df)),
          columns=cases_cols_merged)
    avail["cases_merged"] = cases_cols_merged

    # --- 4. outcomes (only columns not already present) -----------------------
    comp_path = os.path.join(cache_dir, _COMPOSITE_FILE)
    outcomes_present: list[str] = []
    if os.path.exists(comp_path):
        comp = pd.read_csv(comp_path)
        comp.columns = [c.lstrip("﻿") for c in comp.columns]
        want = [PRIMARY_OUTCOME, SECONDARY_OUTCOME, NEGATIVE_CONTROL_OUTCOME]
        addc = [c for c in want if c in comp.columns and c not in df.columns]
        if addc:
            df = df.merge(comp[["caseid"] + addc], on="caseid", how="left")
        outcomes_present = [c for c in want if c in df.columns]
    # restrict to cases that have at least the primary outcome.
    if PRIMARY_OUTCOME in df.columns:
        df = df[pd.to_numeric(df[PRIMARY_OUTCOME], errors="coerce").notna()].copy()
    n_with_outcome = int(len(df))
    _step("outcomes_merged", n=n_with_outcome, outcomes=outcomes_present)
    avail["outcomes_present"] = outcomes_present
    avail["n_ppv"] = n_ppv
    avail["n_analysis"] = n_with_outcome
    avail["preliminary"] = bool(n_with_outcome < MIN_PPV_CASES_FOR_VERDICT)

    # Derive durations + body size + encode confounders.
    df = _derive_durations(df)
    df, size_meta = _derive_bodysize(df)
    df = _encode_confounders(df)
    avail["body_size"] = size_meta
    return df, avail


def _derive_bodysize(df):
    """Add canonical weight_kg, height_cm, bsa_m2 (Mosteller). Returns (df, meta).

    BSA (Mosteller) = sqrt(height_cm * weight_kg / 3600). Used to size-normalise
    raw pressor doses (ug -> ug/kg) and fluid volumes (mL -> mL/kg) before tertiles.
    """
    import numpy as np
    import pandas as pd
    df = df.copy()
    wcol = next((c for c in WEIGHT_COLS if c in df.columns), None)
    hcol = next((c for c in HEIGHT_COLS if c in df.columns), None)
    if wcol is not None and "weight_kg" not in df.columns:
        df["weight_kg"] = pd.to_numeric(df[wcol], errors="coerce")
    if hcol is not None and "height_cm" not in df.columns:
        df["height_cm"] = pd.to_numeric(df[hcol], errors="coerce")
    w = pd.to_numeric(df.get("weight_kg"), errors="coerce") if "weight_kg" in df.columns else None
    h = pd.to_numeric(df.get("height_cm"), errors="coerce") if "height_cm" in df.columns else None
    # plausibility gate (drop absurd/zero values so per-kg ratios stay finite).
    if w is not None:
        w = w.where((w >= 20) & (w <= 250))
        df["weight_kg"] = w
    if w is not None and h is not None:
        h = h.where((h >= 100) & (h <= 230))
        df["height_cm"] = h
        df["bsa_m2"] = np.sqrt((h * w) / 3600.0)
    meta = {
        "weight_source": wcol, "height_source": hcol,
        "n_weight": int(w.notna().sum()) if w is not None else 0,
        "n_bsa": int(df["bsa_m2"].notna().sum()) if "bsa_m2" in df.columns else 0,
        "available": bool(w is not None and w.notna().any()),
    }
    return df, meta


def _derive_durations(df):
    import pandas as pd
    df = df.copy()
    if "anesthesia_duration_min" not in df.columns and {"anestart", "aneend"} <= set(df.columns):
        dur = (pd.to_numeric(df["aneend"], errors="coerce")
               - pd.to_numeric(df["anestart"], errors="coerce")) / 60.0
        df["anesthesia_duration_min"] = dur.where(dur >= 0)
    if "op_duration_min" not in df.columns and {"opstart", "opend"} <= set(df.columns):
        dur = (pd.to_numeric(df["opend"], errors="coerce")
               - pd.to_numeric(df["opstart"], errors="coerce")) / 60.0
        df["op_duration_min"] = dur.where(dur >= 0)
    return df


def _encode_confounders(df):
    import pandas as pd
    df = df.copy()
    if "sex" in df.columns and not pd.api.types.is_numeric_dtype(df["sex"]):
        s = df["sex"].astype(str).str.upper().str.strip()
        df["sex"] = s.map({"M": 1, "MALE": 1, "F": 0, "FEMALE": 0}).astype("float")
    if "optype" in df.columns and "optype_code" not in df.columns:
        codes, _ = pd.factorize(df["optype"].astype(str), sort=True)
        df["optype_code"] = codes.astype(float)
    return df


# ===========================================================================
# AXIS DERIVATION -- preload-responsive flag, vasoplegic flag, management, the
# A-line recommendation, and concordance.
# ===========================================================================

def derive_axes(df, avail):
    """Add the preload / vasoplegia phenotype flags, the actual management axis,
    the A-line RECOMMENDATION, and the CONCORDANT flag.

    Adds:
      preload_responsive   1 if PPV>13 (or SVV>13 where present), else 0
      vasoplegic           1 if vaso_responsiveness blunted (slope<=0), else 0/NaN
                           (NaN if the vaso axis is unavailable)
      gave_fluid           1 if fluids in TOP tertile (fluid-predominant), else 0
      gave_pressor         1 if any vasopressor given, else 0
      mgmt_fluid_vs_pressor "fluid" / "pressor" / "both" / "neither" (actual)
      aline_reco           "FLUID" if preload_responsive, "PRESSOR" if vasoplegic
                           (PPV-only fallback: "PRESSOR" if NOT preload_responsive
                           when the vaso axis is unavailable); NaN if undecidable
      concordant           1 if actual management matched aline_reco, else 0; NaN
                           where aline_reco is NaN
    """
    import numpy as np
    import pandas as pd

    df = df.copy()

    # ---- preload-responsive (PPV>13; prefer SVV gold standard where present) --
    ppv = pd.to_numeric(df["ppv"], errors="coerce")
    preload = (ppv > PPV_PRELOAD_RESPONSIVE_CUT)
    used_svv = False
    if avail.get("preload_svv", {}).get("available") and "svv" in df.columns:
        svv = pd.to_numeric(df["svv"], errors="coerce")
        # Where SVV is present, it overrides PPV (gold standard); else keep PPV.
        preload = np.where(svv.notna(), svv > SVV_PRELOAD_RESPONSIVE_CUT, preload)
        preload = pd.Series(preload, index=df.index)
        used_svv = True
    df["preload_responsive"] = pd.Series(preload, index=df.index).astype(int)
    df.attrs["preload_used_svv"] = used_svv

    # ---- vasoplegic (blunted vaso_responsiveness) -- NaN if axis unavailable --
    if avail.get("vasoplegia_vaso_responsiveness", {}).get("available") \
            and "vaso_responsiveness" in df.columns:
        vr = pd.to_numeric(df["vaso_responsiveness"], errors="coerce")
        vaso = pd.Series(np.nan, index=df.index)
        vaso.loc[vr.notna()] = (vr[vr.notna()] <= VASO_RESPONSIVENESS_BLUNTED_CUT).astype(float)
        df["vasoplegic"] = vaso
    else:
        df["vasoplegic"] = np.nan

    # ---- ACTUAL management (download-free; actionable_targets-style) ----------
    # Doses are size-normalised before tertiles: the /cases pressor totals are RAW
    # ug (NOT ug/kg) and fluids are RAW mL -- both confounded by body size. We
    # divide by weight_kg (ug/kg, mL/kg) and recompute tertiles on the per-kg
    # values. Where weight is missing the raw value is kept (graceful fallback).
    phe = pd.to_numeric(df.get(PHE_COL, 0), errors="coerce").fillna(0.0)
    eph = pd.to_numeric(df.get(EPH_COL, 0), errors="coerce").fillna(0.0)
    epi = pd.to_numeric(df.get(EPI_COL, 0), errors="coerce").fillna(0.0)
    cry = pd.to_numeric(df.get(CRYSTALLOID_COL, 0), errors="coerce").fillna(0.0)
    col = pd.to_numeric(df.get(COLLOID_COL, 0), errors="coerce").fillna(0.0)
    fluid_total = cry + col
    pressor_eq = phe + eph * EPH_TO_PHE_EQUIV + epi      # PHE-equivalent ug
    df["fluid_total_ml"] = fluid_total
    df["pressor_phe_equiv_ug"] = pressor_eq
    df["any_vasopressor"] = ((phe > 0) | (eph > 0) | (epi > 0)).astype(int)

    # Per-kg normalisation (fallback to raw where weight missing).
    if "weight_kg" in df.columns:
        wkg = pd.to_numeric(df["weight_kg"], errors="coerce")
        size_used = bool(wkg.notna().any())
    else:
        wkg = pd.Series(np.nan, index=df.index)
        size_used = False
    fluid_norm = (fluid_total / wkg).where(wkg.notna(), fluid_total)   # mL/kg
    pressor_norm = (pressor_eq / wkg).where(wkg.notna(), pressor_eq)   # ug/kg
    df["fluid_ml_per_kg"] = fluid_norm
    df["pressor_phe_equiv_ug_per_kg"] = pressor_norm
    df.attrs["dose_size_normalised"] = size_used

    # Tertiles on the WEIGHT-NORMALISED values.
    fluid_t = pd.Series(tertile_assign(fluid_norm.tolist()), index=df.index)
    df["fluid_tertile"] = fluid_t
    df["gave_fluid"] = (fluid_t == 2).fillna(False).astype(int)        # top tertile (mL/kg)
    df["gave_pressor"] = df["any_vasopressor"].astype(int)
    # Pressor tertile among pressor-treated (ug/kg) -- the dose-aware pressor axis.
    pressor_tertile = pd.Series(np.nan, index=df.index)
    treated = (df["gave_pressor"] == 1) & pressor_norm.notna()
    if treated.sum() >= 3:
        pressor_tertile.loc[treated] = pd.Series(
            tertile_assign(pressor_norm[treated].tolist()), index=df.index[treated])
    df["pressor_tertile"] = pressor_tertile

    # Actual fluid-vs-pressor LEAN: who got the bigger relative intervention.
    # "fluid"  = top-tertile fluids and NOT any pressor
    # "pressor"= any pressor and NOT top-tertile fluids
    # "both"   = both; "neither" = neither.
    mgmt = pd.Series("neither", index=df.index)
    gf = df["gave_fluid"] == 1
    gp = df["gave_pressor"] == 1
    mgmt[gf & ~gp] = "fluid"
    mgmt[gp & ~gf] = "pressor"
    mgmt[gf & gp] = "both"
    df["mgmt_fluid_vs_pressor"] = mgmt

    # ---- A-line RECOMMENDATION ------------------------------------------------
    vaso_axis_ok = bool(avail.get("vasoplegia_vaso_responsiveness", {}).get("available"))
    reco = pd.Series(np.nan, index=df.index, dtype=object)
    pr = df["preload_responsive"] == 1
    if vaso_axis_ok:
        vp = df["vasoplegic"] == 1
        # FLUID if preload-responsive; PRESSOR if vasoplegic (low PPV + blunted).
        # Preload-responsive takes precedence (a steep Starling curve responds to
        # fluid regardless of tone). Vasoplegic-and-not-preload-responsive -> pressor.
        reco[pr] = "FLUID"
        reco[(~pr) & vp] = "PRESSOR"
        # not preload-responsive AND not vasoplegic -> undecidable (NaN).
        reco_rule = "ppv_plus_vaso_responsiveness"
    else:
        # PPV-only fallback: high PPV -> FLUID; low PPV -> PRESSOR (the simplest
        # runnable A-line rule until the vaso axis lands).
        reco[pr] = "FLUID"
        reco[~pr] = "PRESSOR"
        reco_rule = "ppv_only_fallback"
    df["aline_reco"] = reco
    df.attrs["reco_rule"] = reco_rule

    # ---- CONCORDANT: did actual management match the recommendation? ----------
    # FLUID reco  -> concordant if actual lean is "fluid" (or "both"); discordant
    #                if "pressor" (or "neither"-with-no-fluid).
    # PRESSOR reco-> concordant if actual lean is "pressor" (or "both"); discordant
    #                if "fluid" (or "neither").
    concordant = pd.Series(np.nan, index=df.index)
    is_fluid_reco = reco == "FLUID"
    is_pressor_reco = reco == "PRESSOR"
    got_fluid = mgmt.isin(["fluid", "both"])
    got_pressor = mgmt.isin(["pressor", "both"])
    concordant[is_fluid_reco] = got_fluid[is_fluid_reco].astype(float)
    concordant[is_pressor_reco] = got_pressor[is_pressor_reco].astype(float)
    df["concordant"] = concordant
    df["aline_recommended"] = reco.map({"FLUID": 1, "PRESSOR": 0}).astype("float")
    return df


# ===========================================================================
# ANALYSIS 1 -- axis validation.
# ===========================================================================

def validate_axes(df, avail):
    """Descriptives + correlations validating the two A-line axes."""
    import numpy as np
    import pandas as pd

    out: dict[str, Any] = {}

    # (a) Does high PPV mark a distinct preload-responsive phenotype?
    ppv = pd.to_numeric(df["ppv"], errors="coerce")
    pr = df["preload_responsive"] == 1
    def _desc(mask, col):
        v = pd.to_numeric(df.loc[mask, col], errors="coerce").dropna() if col in df.columns else pd.Series([], dtype=float)
        if len(v) == 0:
            return {"n": 0, "mean": None, "sd": None, "median": None}
        return {"n": int(len(v)), "mean": round(float(v.mean()), 3),
                "sd": round(float(v.std()), 3), "median": round(float(v.median()), 3)}
    ppv_a = {
        "ppv_cut": PPV_PRELOAD_RESPONSIVE_CUT,
        "n_total": int(ppv.notna().sum()),
        "n_preload_responsive": int(pr.sum()),
        "frac_preload_responsive": round(float(pr.mean()), 3) if len(df) else None,
        "ppv_distribution": {
            "min": round(float(ppv.min()), 2) if ppv.notna().any() else None,
            "median": round(float(ppv.median()), 2) if ppv.notna().any() else None,
            "p75": round(float(ppv.quantile(0.75)), 2) if ppv.notna().any() else None,
            "max": round(float(ppv.max()), 2) if ppv.notna().any() else None,
        },
        "by_group": {
            "preload_responsive": {
                "art_map_mean": _desc(pr, "art_map_mean"),
                "art_pulse_pressure_mean": _desc(pr, "art_pulse_pressure_mean"),
                "ppv_burden": _desc(pr, "ppv_burden") if "ppv_burden" in df.columns else None,
            },
            "not_preload_responsive": {
                "art_map_mean": _desc(~pr, "art_map_mean"),
                "art_pulse_pressure_mean": _desc(~pr, "art_pulse_pressure_mean"),
                "ppv_burden": _desc(~pr, "ppv_burden") if "ppv_burden" in df.columns else None,
            },
        },
    }
    # correlation of PPV with its own burden (sanity: should be strongly positive).
    if "ppv_burden" in df.columns:
        m = ppv.notna() & pd.to_numeric(df["ppv_burden"], errors="coerce").notna()
        if m.sum() >= 3:
            ppv_a["corr_ppv_vs_ppv_burden"] = round(
                float(np.corrcoef(ppv[m], pd.to_numeric(df["ppv_burden"], errors="coerce")[m])[0, 1]), 3)
    out["ppv_preload_axis"] = ppv_a

    # (b) Does low vaso_responsiveness co-occur with vasoplegia markers?
    if avail.get("vasoplegia_vaso_responsiveness", {}).get("available") \
            and "vaso_responsiveness" in df.columns:
        vr = pd.to_numeric(df["vaso_responsiveness"], errors="coerce")
        vb = {"available": True,
              "n_nonnull": int(vr.notna().sum()),
              "blunted_cut": VASO_RESPONSIVENESS_BLUNTED_CUT,
              "n_vasoplegic": int((df["vasoplegic"] == 1).sum())}
        for marker in ("vaso_n_agents", "vaso_pressor_duration_frac",
                       "vaso_max_infusion_norm"):
            if marker in df.columns:
                mv = pd.to_numeric(df[marker], errors="coerce")
                m = vr.notna() & mv.notna()
                if m.sum() >= 3:
                    vb[f"corr_vaso_responsiveness_vs_{marker}"] = round(
                        float(np.corrcoef(vr[m], mv[m])[0, 1]), 3)
                    # vasoplegia (blunted) should co-occur with MORE agents / longer
                    # duration -> compare marker between blunted vs not.
                    blunted = df["vasoplegic"] == 1
                    vb[f"{marker}_blunted_mean"] = (
                        round(float(mv[blunted & mv.notna()].mean()), 3)
                        if (blunted & mv.notna()).any() else None)
                    vb[f"{marker}_responsive_mean"] = (
                        round(float(mv[(~blunted) & mv.notna()].mean()), 3)
                        if ((~blunted) & mv.notna()).any() else None)
        out["vasoplegia_axis"] = vb
    else:
        out["vasoplegia_axis"] = {
            "available": False,
            "note": ("vaso_responsiveness not in any available matrix "
                     "(feature_matrix_enriched.csv absent and feature_matrix.csv "
                     "lacks/empties the column). Vasoplegia axis pending the "
                     "broader vasoactive-PD extraction; the A-line recommendation "
                     "falls back to a PPV-only rule."),
        }
    return out


# ===========================================================================
# ANALYSIS 2 -- concordance HTE (the headline).
# ===========================================================================

def _fit_iptw_for_concordance(df, covariates, seed=RANDOM_SEED):
    """Stabilised, trimmed IPTW for the CONCORDANT exposure, reusing
    hypotension_treatment.fit_propensity_model / compute_iptw_weights (which key
    off a ``vasopressor_treated`` column -> alias concordant into it).

    Returns (df_w, used_covariates) restricted to rows where concordant is 0/1,
    or (None, []) if it cannot be fit.
    """
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )

    sub = df.copy()
    c = pd.to_numeric(sub["concordant"], errors="coerce")
    sub = sub[c.notna()].copy()
    sub["vasopressor_treated"] = c[c.notna()].astype(int).to_numpy()
    if sub["vasopressor_treated"].nunique() < 2:
        return None, []
    avail = [cc for cc in covariates if cc in sub.columns]
    if not avail:
        return None, []
    try:
        df_ps, _m, used = fit_propensity_model(sub, covariates=avail)
        df_w = compute_iptw_weights(df_ps)
    except Exception:
        return None, []
    return df_w, used


def _weighted_rd_rr(y, expo, w):
    import numpy as np
    y = np.asarray(y, dtype=float)
    e = np.asarray(expo, dtype=int)
    w = np.asarray(w, dtype=float)

    def _risk(mask):
        ww, yy = w[mask], y[mask]
        sw = ww.sum()
        return float((ww * yy).sum() / sw) if sw > 0 else float("nan")

    r1, r0 = _risk(e == 1), _risk(e == 0)
    rd = r1 - r0
    rr = (r1 / r0) if (r0 and math.isfinite(r0) and r0 > 0) else float("nan")
    return r1, r0, rd, rr


def within_stratum_effect(df_w, outcome, stratum_col, stratum_val,
                          n_bootstrap=N_BOOTSTRAP, seed=RANDOM_SEED):
    """IPTW RD/RR of CONCORDANT (1) vs DISCORDANT (0) on ``outcome`` within the
    recommendation stratum (e.g. all FLUID-recommended cases), bootstrap 95% CI.

    A NEGATIVE risk difference means concordant management had LOWER organ injury
    (the hoped-for direction).
    """
    import numpy as np
    import pandas as pd

    sub = df_w[df_w[stratum_col] == stratum_val].copy()
    y = pd.to_numeric(sub[outcome], errors="coerce")
    valid = y.notna() & sub["concordant"].notna() & sub["iptw_weight"].notna()
    sub = sub[valid].copy()
    yv = pd.to_numeric(sub[outcome], errors="coerce").astype(int).to_numpy()
    ev = pd.to_numeric(sub["concordant"], errors="coerce").astype(int).to_numpy()
    wv = sub["iptw_weight"].to_numpy(dtype=float)

    n = int(len(sub))
    n_events = int(yv.sum())
    n_concordant = int((ev == 1).sum())

    if n == 0 or ev.min() == ev.max():
        return {"n": n, "n_events": n_events, "n_concordant": n_concordant,
                "risk_concordant": None, "risk_discordant": None,
                "risk_difference": None, "risk_ratio": None,
                "rd_ci": [None, None], "rr_ci": [None, None],
                "underpowered": True,
                "note": "no contrast (single arm) or empty stratum"}

    r1, r0, rd, rr = _weighted_rd_rr(yv, ev, wv)
    rng = np.random.default_rng(seed)
    rd_b, rr_b = [], []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        eb = ev[idx]
        if eb.min() == eb.max():
            continue
        _, _, rdb, rrb = _weighted_rd_rr(yv[idx], eb, wv[idx])
        if math.isfinite(rdb):
            rd_b.append(rdb)
        if math.isfinite(rrb):
            rr_b.append(rrb)

    def _p(a, q):
        return float(np.percentile(a, q)) if len(a) else float("nan")
    rd_lo, rd_hi = _p(rd_b, 2.5), _p(rd_b, 97.5)
    rr_lo, rr_hi = _p(rr_b, 2.5), _p(rr_b, 97.5)

    return {
        "n": n, "n_events": n_events, "n_concordant": n_concordant,
        "risk_concordant": round(r1, 4) if math.isfinite(r1) else None,
        "risk_discordant": round(r0, 4) if math.isfinite(r0) else None,
        "risk_difference": round(rd, 4) if math.isfinite(rd) else None,
        "risk_ratio": round(rr, 4) if math.isfinite(rr) else None,
        "rd_ci": [round(rd_lo, 4) if math.isfinite(rd_lo) else None,
                  round(rd_hi, 4) if math.isfinite(rd_hi) else None],
        "rr_ci": [round(rr_lo, 4) if math.isfinite(rr_lo) else None,
                  round(rr_hi, 4) if math.isfinite(rr_hi) else None],
        "underpowered": bool(n_events < MIN_EVENTS_FOR_POWER),
    }


def concordance_interaction(df_w, outcome, seed=RANDOM_SEED):
    """Full-frame IPTW logistic outcome model with a (recommendation x management)
    INTERACTION.  Operationalised as concordant x aline_recommended:

        logit P(y) = b0 + b1*concordant + b2*aline_recommended
                     + b3*(concordant x aline_recommended)

    b1 is the main concordance effect (lower y = protective). b3 tests whether the
    concordance benefit DIFFERS between FLUID-recommended and PRESSOR-recommended
    cases (the heterogeneity the A-line is supposed to create).  Bootstrap p-value
    on b1 (main concordance) and b3 (interaction).
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    sub = df_w.copy()
    y = pd.to_numeric(sub[outcome], errors="coerce")
    valid = (y.notna() & sub["concordant"].notna()
             & sub["aline_recommended"].notna() & sub["iptw_weight"].notna())
    sub = sub[valid].copy()
    yv = pd.to_numeric(sub[outcome], errors="coerce").astype(int).to_numpy()
    cc = pd.to_numeric(sub["concordant"], errors="coerce").astype(float).to_numpy()
    rec = pd.to_numeric(sub["aline_recommended"], errors="coerce").astype(float).to_numpy()
    wv = sub["iptw_weight"].to_numpy(dtype=float)

    if len(yv) == 0 or yv.min() == yv.max() or len(np.unique(cc)) < 2:
        return {"concordant_log_or": None, "concordant_or": None,
                "concordant_p_bootstrap": None,
                "interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None,
                "note": "insufficient variation to fit interaction model"}

    has_reco_var = len(np.unique(rec)) >= 2

    def _design(c_, r_):
        if has_reco_var:
            return np.column_stack([c_, r_, c_ * r_])
        return c_.reshape(-1, 1)            # concordant only (one reco stratum)

    def _fit(X_, y_, w_):
        lr = LogisticRegression(fit_intercept=True, max_iter=1000,
                                solver="lbfgs", C=1e6, random_state=seed)
        lr.fit(X_, y_, sample_weight=w_)
        return lr.coef_[0]

    try:
        coef = _fit(_design(cc, rec), yv, wv)
    except Exception:
        return {"concordant_log_or": None, "concordant_or": None,
                "concordant_p_bootstrap": None,
                "interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None,
                "note": "model failed to converge"}

    b_conc = float(coef[0])
    b_inter = float(coef[2]) if has_reco_var else None

    rng = np.random.default_rng(seed)
    n = len(yv)
    conc_boot, inter_boot = [], []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, size=n)
        yb = yv[idx]
        if yb.min() == yb.max():
            continue
        try:
            cb = _fit(_design(cc[idx], rec[idx]), yb, wv[idx])
            conc_boot.append(float(cb[0]))
            if has_reco_var:
                inter_boot.append(float(cb[2]))
        except Exception:
            continue

    def _bp(arr, point):
        if not arr or point is None:
            return None
        a = np.asarray(arr)
        p = (2.0 * float((a <= 0).mean()) if point >= 0
             else 2.0 * float((a >= 0).mean()))
        return min(1.0, max(0.0, p))

    return {
        "concordant_log_or": round(b_conc, 4),
        "concordant_or": round(math.exp(b_conc), 4),
        "concordant_p_bootstrap": (round(_bp(conc_boot, b_conc), 4)
                                   if _bp(conc_boot, b_conc) is not None else None),
        "interaction_log_or": round(b_inter, 4) if b_inter is not None else None,
        "interaction_or": round(math.exp(b_inter), 4) if b_inter is not None else None,
        "interaction_p_bootstrap": (round(_bp(inter_boot, b_inter), 4)
                                    if (b_inter is not None and _bp(inter_boot, b_inter) is not None)
                                    else None),
        "has_recommendation_variation": bool(has_reco_var),
        "n": int(n), "n_events": int(yv.sum()),
    }


def run_concordance_hte(df, covariates, seed=RANDOM_SEED):
    """The headline: does CONCORDANT (A-line-indicated) management associate with
    LOWER organ injury?  Overall + within each recommendation stratum + E-values +
    negative control + interaction.
    """
    import numpy as np
    import pandas as pd

    out: dict[str, Any] = {}

    # Concordance distribution (descriptive, for the report).
    cc = pd.to_numeric(df["concordant"], errors="coerce")
    reco = df["aline_reco"]
    out["concordance_distribution"] = {
        "n_decidable": int(cc.notna().sum()),
        "n_concordant": int((cc == 1).sum()),
        "n_discordant": int((cc == 0).sum()),
        "frac_concordant": round(float(cc.mean()), 3) if cc.notna().any() else None,
        "n_fluid_reco": int((reco == "FLUID").sum()),
        "n_pressor_reco": int((reco == "PRESSOR").sum()),
        "n_undecidable_reco": int(reco.isna().sum()),
    }

    df_w, used = _fit_iptw_for_concordance(df, covariates, seed=seed)
    if df_w is None:
        out["available"] = False
        out["note"] = "could not fit IPTW for concordance (no contrast / no covariates)"
        return out
    out["available"] = True
    out["ps_covariates"] = used

    all_outcomes = list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]
    by_outcome: dict[str, Any] = {}
    for oc in all_outcomes:
        if oc not in df_w.columns or pd.to_numeric(df_w[oc], errors="coerce").isna().all():
            by_outcome[oc] = {"available": False, "note": "outcome missing/all-NaN"}
            continue

        # Overall concordant-vs-discordant (pooled across reco strata), IPTW.
        overall = within_stratum_effect(df_w, oc, stratum_col="available_all",
                                         stratum_val=1, seed=seed) \
            if "available_all" in df_w.columns else None
        # Build a pooled estimate by treating the whole frame as one stratum.
        dfw2 = df_w.copy()
        dfw2["_all"] = 1
        pooled = within_stratum_effect(dfw2, oc, "_all", 1, seed=seed)

        # Within-recommendation strata.
        strata = {}
        for sval, sname in (("FLUID", "fluid_recommended"),
                            ("PRESSOR", "pressor_recommended")):
            s = within_stratum_effect(df_w, oc, "aline_reco", sval, seed=seed)
            strata[sname] = s

        inter = concordance_interaction(df_w, oc, seed=seed)

        rr = pooled.get("risk_ratio")
        rr_ci = pooled.get("rr_ci", [None, None])
        ev_pt = e_value(rr) if rr is not None else None
        ev_ci = (e_value_ci(rr, rr_ci[0], rr_ci[1])
                 if (rr is not None and rr_ci[0] is not None and rr_ci[1] is not None)
                 else None)

        block = {
            "available": True,
            "concordant_vs_discordant_pooled": pooled,
            "within_recommendation_strata": strata,
            "interaction": inter,
            "e_value_point": round(ev_pt, 3) if ev_pt is not None else None,
            "e_value_ci": round(ev_ci, 3) if ev_ci is not None else None,
            "underpowered": pooled.get("underpowered", True),
        }
        if oc == NEGATIVE_CONTROL_OUTCOME:
            rd = pooled.get("risk_difference")
            block["is_negative_control"] = True
            block["negative_control_flag"] = (
                "NON-NULL (possible residual confounding)"
                if (rd is not None and abs(rd) >= 0.02) else "null (reassuring)"
            )
        by_outcome[oc] = block

    out["by_outcome"] = by_outcome

    # BH-FDR across the concordance (main-effect) bootstrap p-values, primary
    # outcomes only.
    pvals, keys = [], []
    for oc in PRIMARY_OUTCOMES:
        blk = by_outcome.get(oc, {})
        if blk.get("available"):
            p = (blk.get("interaction") or {}).get("concordant_p_bootstrap")
            pvals.append(p if p is not None else 1.0)
            keys.append(oc)
    reject = benjamini_hochberg(pvals)
    out["fdr_concordance"] = {
        oc: {"concordant_p": p, "fdr_reject": bool(rj)}
        for oc, p, rj in zip(keys, pvals, reject)
    }
    return out


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================

def run(cfg: dict[str, Any]) -> dict[str, Any]:
    """Public entry point: assemble -> derive axes -> validate -> concordance HTE
    -> write results JSON + docs + done marker (LAST)."""
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    os.makedirs(cache_dir, exist_ok=True)

    df, avail = assemble_frame(cfg)
    df = derive_axes(df, avail)
    validation = validate_axes(df, avail)
    # Size-aware covariate set: actionable confounders + weight/age/sex (age/sex
    # are already in DEFAULT_PS_COVARIATES; weight_kg is added for body size).
    covariates = list(dict.fromkeys(
        list(DEFAULT_PS_COVARIATES) + list(SIZE_AWARE_PS_COVARIATES)))
    concordance = run_concordance_hte(df, covariates, seed=seed)

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "analysis": "aline_fluid_vs_pressor_feasibility_phase0",
        "seed": seed,
        "min_events_for_power": MIN_EVENTS_FOR_POWER,
        "min_ppv_cases_for_verdict": MIN_PPV_CASES_FOR_VERDICT,
        "thresholds": {
            "ppv_preload_responsive_cut_pct": PPV_PRELOAD_RESPONSIVE_CUT,
            "svv_preload_responsive_cut_pct": SVV_PRELOAD_RESPONSIVE_CUT,
            "vaso_responsiveness_blunted_cut": VASO_RESPONSIVENESS_BLUNTED_CUT,
        },
        "primary_outcome": PRIMARY_OUTCOME,
        "secondary_outcome": SECONDARY_OUTCOME,
        "negative_control_outcome": NEGATIVE_CONTROL_OUTCOME,
        "confounder_set": covariates,
        "dose_size_normalised": df.attrs.get("dose_size_normalised", False),
        "body_size": avail.get("body_size"),
        "axis_availability": avail,
        "recommendation_rule": df.attrs.get("reco_rule"),
        "preload_used_svv": df.attrs.get("preload_used_svv", False),
        "preliminary": avail.get("preliminary"),
        "axis_validation": validation,
        "concordance_hte": concordance,
        "interpretation": (
            "Phase-0 feasibility, observational, single-centre (VitalDB/SNUH). "
            "Confounding by indication is SEVERE and runs the opposite way from "
            "usual: clinicians may already read PPV / pressor-response off the same "
            "A-line, so high concordance and a NULL concordance benefit are EXPECTED "
            "if they already optimise. A POSITIVE concordance benefit (lower organ "
            "injury when management matched the A-line) is the strong, GO-supporting "
            "result; a NULL is consistent with both 'no signal' and 'already "
            "optimal' and does not by itself kill the deep-learning idea. Fuller "
            "power needs the broader ART-waveform + vasoactive-PD extraction."
        ),
    }

    results_path = os.path.join(cache_dir, _RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[aline_fvp] results -> {results_path}")

    _write_md(results, cfg)

    done_path = os.path.join(cache_dir, _DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"done": True, "results_json": _RESULTS_JSON,
                   "n_ppv": avail.get("n_ppv"),
                   "n_analysis": avail.get("n_analysis"),
                   "preliminary": avail.get("preliminary")}, fh, indent=2)
    print(f"[aline_fvp] done marker -> {done_path}")
    return results


# ===========================================================================
# REPORT
# ===========================================================================

def _fmt(v):
    return "n/a" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _go_no_go(results) -> tuple[str, list[str]]:
    """Derive an explicit GO / NO-GO / INPUTS-PENDING read for the DL version."""
    avail = results["axis_availability"]
    conc = results.get("concordance_hte", {})
    n = avail.get("n_analysis", 0)
    reasons: list[str] = []

    if results.get("preliminary"):
        reasons.append(
            f"PPV/outcome N = {n} (< {results['min_ppv_cases_for_verdict']}): "
            "underpowered for a verdict.")
    if not avail.get("vasoplegia_vaso_responsiveness", {}).get("available"):
        reasons.append(
            "Vasoplegia axis (vaso_responsiveness) UNAVAILABLE in current caches; "
            "recommendation used a PPV-only fallback rule.")

    # Was the primary concordance effect estimable + protective + powered?
    blk = (conc.get("by_outcome", {}) or {}).get(PRIMARY_OUTCOME, {})
    pooled = blk.get("concordant_vs_discordant_pooled", {}) if blk.get("available") else {}
    rd = pooled.get("risk_difference")
    rd_ci = pooled.get("rd_ci", [None, None])
    powered = blk.get("available") and not pooled.get("underpowered", True)
    protective = isinstance(rd, (int, float)) and rd < 0
    ci_excludes_null = (rd_ci[0] is not None and rd_ci[1] is not None
                        and (rd_ci[1] < 0 or rd_ci[0] > 0))
    nc = (conc.get("by_outcome", {}) or {}).get(NEGATIVE_CONTROL_OUTCOME, {})
    nc_null = nc.get("negative_control_flag", "").startswith("null") if nc.get("available") else None

    if powered and protective and ci_excludes_null and nc_null:
        verdict = "GO"
        reasons.append(
            f"Concordant management showed LOWER renal injury (RD={_fmt(rd)}, "
            "CI excludes 0) with the negative control null -- a recoverable signal.")
    elif results.get("preliminary") or not avail.get("vasoplegia_vaso_responsiveness", {}).get("available"):
        verdict = "INPUTS-PENDING"
        reasons.append(
            "Verdict deferred: too few PPV cases and/or the vasoplegia axis is not "
            "yet extracted. Re-run after the broader ART-waveform + vasoactive-PD "
            "extraction completes.")
    elif protective and not ci_excludes_null:
        verdict = "WEAK-GO (signal in the right direction, CI crosses null)"
        reasons.append(
            f"Concordant management trended toward LOWER injury (RD={_fmt(rd)}) but "
            "the CI crosses 0 at current N.")
    else:
        verdict = "NO-GO / NULL"
        reasons.append(
            "No protective concordance association at current N. Note this is "
            "consistent with clinicians ALREADY optimising on the A-line, so it does "
            "not by itself exclude a deep-learning signal -- but it provides no "
            "positive support.")
    return verdict, reasons


def _write_md(results: dict, cfg: dict) -> str:
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "ALINE_FLUID_VS_PRESSOR.md")

    avail = results["axis_availability"]
    conc = results.get("concordance_hte", {})
    val = results.get("axis_validation", {})
    verdict, reasons = _go_no_go(results)

    L = [
        "# A-line FLUID-vs-PRESSOR feasibility (Phase-0)",
        "",
        "## READ FIRST -- what this is and is not",
        "",
        "- **The question.** Can the arterial line tell you whether a hypotensive",
        "  patient needs a **FLUID** bolus or a **PRESSOR**? A preload-responsive",
        f"  patient (PPV > {results['thresholds']['ppv_preload_responsive_cut_pct']} %, "
        "Michard cutpoint) should respond to fluid; a vasoplegic patient (blunted",
        "  MAP-per-pressor `vaso_responsiveness`) needs a pressor.",
        "- **Phase-0 feasibility only.** NO deep learning, NO new heavy extraction.",
        "  It runs on whatever caches exist NOW and reports N + axis availability at",
        "  every step. A gated deep-learning version is a separate decision.",
        "- **Observational, single-centre** (VitalDB / SNUH). Treatment was not",
        "  randomised. **Confounding by indication is SEVERE and runs the OPPOSITE",
        "  way from usual**: clinicians may ALREADY read PPV / pressor-response off",
        "  the same A-line and choose accordingly. If they already optimise,",
        "  concordance is near-universal and a **NULL concordance benefit is",
        "  EXPECTED**. So:",
        "    - a **POSITIVE** concordance benefit (less organ injury when management",
        "      matched the A-line) is the STRONG, GO-supporting result;",
        "    - a **NULL** is consistent with BOTH 'no signal' AND 'clinicians already",
        "      optimal' and does NOT by itself kill the deep-learning idea.",
        "- **Hypothesis-generating** for a prospective/target-trial design; external",
        "  validation (INSPIRE) pending. E-values quantify required unmeasured",
        "  confounding; `organ_hepatocellular` is the negative control.",
        "",
        f"> **PRELIMINARY: {results.get('preliminary')}** "
        f"(analysis N = {avail.get('n_analysis')}; "
        f"verdict threshold = {results['min_ppv_cases_for_verdict']} cases).",
        "",
        "## Axis availability and N at each step",
        "",
        f"- **Preload / PPV axis:** {'AVAILABLE' if avail['preload_ppv']['available'] else 'UNAVAILABLE'}"
        f" -- source `{avail['preload_ppv'].get('source')}`, column "
        f"`{avail['preload_ppv'].get('column')}`, N = {avail['preload_ppv'].get('n')}.",
        f"- **Preload / SVV gold-standard axis:** "
        f"{'AVAILABLE' if avail['preload_svv']['available'] else 'UNAVAILABLE'}"
        f" ({avail['preload_svv'].get('note', avail['preload_svv'].get('column'))}).",
        f"- **Vasoplegia / vaso_responsiveness axis:** "
        f"{'AVAILABLE' if avail['vasoplegia_vaso_responsiveness']['available'] else 'UNAVAILABLE'}"
        f" ({avail['vasoplegia_vaso_responsiveness'].get('note', avail['vasoplegia_vaso_responsiveness'].get('source'))}).",
        f"- **Management (download-free):** from /cases (`{', '.join(avail.get('cases_merged', []) ) or 'none merged'}`).",
        f"- **Outcomes:** {', '.join(avail.get('outcomes_present', [])) or 'none'}.",
        f"- **Recommendation rule used:** `{results.get('recommendation_rule')}`"
        f"{' (SVV-augmented)' if results.get('preload_used_svv') else ''}.",
        "",
        "### Merge trace (N at each step)",
        "",
    ]
    for s in avail.get("steps", []):
        L.append(f"- `{s.get('step')}`: " + ", ".join(
            f"{k}={v}" for k, v in s.items() if k != "step"))
    L += ["", "## Axis definitions", "",
          f"- **preload_responsive** = 1 if PPV > "
          f"{results['thresholds']['ppv_preload_responsive_cut_pct']} % "
          "(SVV > 13 % overrides where present).",
          f"- **vasoplegic** = 1 if `vaso_responsiveness` (OLS MAP-vs-pressor slope) "
          f"<= {results['thresholds']['vaso_responsiveness_blunted_cut']} "
          "(NaN if the axis is unavailable).",
          "- **A-line reco** = FLUID if preload-responsive; PRESSOR if vasoplegic-",
          "  and-not-preload-responsive. PPV-only fallback (used here if the",
          "  vasoplegia axis is absent): high PPV -> FLUID, low PPV -> PRESSOR.",
          "- **management (actual)** = top-tertile fluids without pressor -> 'fluid';",
          "  any pressor without top-tertile fluids -> 'pressor'; both / neither.",
          "- **concordant** = 1 if actual management matched the A-line reco.",
          "",
          "### Body-size / dosage normalisation",
          "",
          "The /cases pressor totals are **RAW** (PHE-equivalent ug, NOT ug/kg) and",
          "fluids are **RAW mL** -- both confounded by body size. Before building the",
          "fluid-/pressor-predominant tertiles we normalise per kg:",
          "  - pressor PHE-equivalent total / weight_kg -> **ug/kg**,",
          "  - fluid mL / weight_kg -> **mL/kg**,",
          "and recompute the tertiles on the weight-normalised values. BSA (Mosteller)",
          "= sqrt(height_cm*weight_kg/3600) is also derived. **weight_kg + age + sex**",
          "are added to the IPTW propensity/adjustment covariate set. PPV/SVV (the",
          "preload axis) are intrinsically size-independent and are left as-is.",
          f"  - body size available: {results.get('body_size', {}).get('available')} "
          f"(N weight = {results.get('body_size', {}).get('n_weight')}, "
          f"N BSA = {results.get('body_size', {}).get('n_bsa')}); "
          f"dose size-normalised: {results.get('dose_size_normalised')}.",
          ""]

    # ---- Axis validation ----
    L += ["## 1. Axis validation", ""]
    pa = val.get("ppv_preload_axis", {})
    L += [
        "### (a) PPV / preload axis",
        f"- N = {pa.get('n_total')}; preload-responsive (PPV>13) = "
        f"{pa.get('n_preload_responsive')} ({_fmt(pa.get('frac_preload_responsive'))}).",
        f"- PPV distribution: min {_fmt(pa.get('ppv_distribution', {}).get('min'))}, "
        f"median {_fmt(pa.get('ppv_distribution', {}).get('median'))}, "
        f"p75 {_fmt(pa.get('ppv_distribution', {}).get('p75'))}, "
        f"max {_fmt(pa.get('ppv_distribution', {}).get('max'))}.",
    ]
    if "corr_ppv_vs_ppv_burden" in pa:
        L.append(f"- corr(PPV, PPV-burden) = {_fmt(pa['corr_ppv_vs_ppv_burden'])} "
                 "(sanity: should be strongly positive).")
    va = val.get("vasoplegia_axis", {})
    L += ["", "### (b) Vasoplegia axis"]
    if va.get("available"):
        L.append(f"- N non-null vaso_responsiveness = {va.get('n_nonnull')}; "
                 f"vasoplegic (blunted) = {va.get('n_vasoplegic')}.")
        for k, v in va.items():
            if k.startswith("corr_") or k.endswith("_blunted_mean") or k.endswith("_responsive_mean"):
                L.append(f"  - {k} = {_fmt(v)}")
    else:
        L.append(f"- **UNAVAILABLE.** {va.get('note')}")
    L.append("")

    # ---- Concordance HTE ----
    L += ["## 2. Concordance HTE (headline)", ""]
    cd = conc.get("concordance_distribution", {})
    L += [
        f"- Decidable recommendations: {cd.get('n_decidable')} "
        f"(FLUID={cd.get('n_fluid_reco')}, PRESSOR={cd.get('n_pressor_reco')}, "
        f"undecidable={cd.get('n_undecidable_reco')}).",
        f"- Concordant (management matched A-line) = {cd.get('n_concordant')} "
        f"({_fmt(cd.get('frac_concordant'))}); discordant = {cd.get('n_discordant')}.",
        "",
    ]
    if not conc.get("available"):
        L.append(f"_Concordance model not estimable: {conc.get('note')}._")
        L.append("")
    else:
        for oc in (results["primary_outcome"], results["secondary_outcome"]):
            blk = conc.get("by_outcome", {}).get(oc, {})
            if not blk.get("available"):
                L.append(f"### {oc}: not available ({blk.get('note')})")
                continue
            p = blk["concordant_vs_discordant_pooled"]
            inter = blk.get("interaction", {})
            flag = " **[UNDERPOWERED, hypothesis-only]**" if blk.get("underpowered") else ""
            L += [
                f"### {oc}{flag}",
                f"- **Pooled concordant vs discordant:** RD = {_fmt(p.get('risk_difference'))} "
                f"(95% CI {_fmt(p.get('rd_ci', [None,None])[0])} to "
                f"{_fmt(p.get('rd_ci', [None,None])[1])}); "
                f"RR = {_fmt(p.get('risk_ratio'))} "
                f"(95% CI {_fmt(p.get('rr_ci', [None,None])[0])} to "
                f"{_fmt(p.get('rr_ci', [None,None])[1])}). "
                f"n={p.get('n')}, events={p.get('n_events')}, "
                f"concordant={p.get('n_concordant')}. "
                "(Negative RD = concordant had LESS injury.)",
                f"  - E-value point = {_fmt(blk.get('e_value_point'))}, "
                f"E-value CI = {_fmt(blk.get('e_value_ci'))}.",
                f"  - Concordance main OR = {_fmt(inter.get('concordant_or'))} "
                f"(p = {_fmt(inter.get('concordant_p_bootstrap'))}); "
                f"reco-interaction OR = {_fmt(inter.get('interaction_or'))} "
                f"(p = {_fmt(inter.get('interaction_p_bootstrap'))}).",
            ]
            for sname, s in blk.get("within_recommendation_strata", {}).items():
                L.append(
                    f"  - _{sname}:_ RD = {_fmt(s.get('risk_difference'))} "
                    f"(CI {_fmt(s.get('rd_ci', [None,None])[0])} to "
                    f"{_fmt(s.get('rd_ci', [None,None])[1])}); "
                    f"n={s.get('n')}, events={s.get('n_events')}"
                    + (" [underpowered]" if s.get("underpowered") else ""))
            L.append("")
        nc = conc.get("by_outcome", {}).get(results["negative_control_outcome"], {})
        if nc.get("available"):
            p = nc["concordant_vs_discordant_pooled"]
            L += [
                f"### Negative control ({results['negative_control_outcome']})",
                f"- RD = {_fmt(p.get('risk_difference'))} -> **{nc.get('negative_control_flag')}**.",
                "",
            ]
        fdr = conc.get("fdr_concordance", {})
        if fdr:
            L.append("### BH-FDR (concordance main effect, primary outcomes)")
            for oc, d in fdr.items():
                L.append(f"- {oc}: p = {_fmt(d.get('concordant_p'))}, "
                         f"FDR-reject = {d.get('fdr_reject')}")
            L.append("")

    # ---- GO/NO-GO ----
    L += [
        "## GO / NO-GO for the deep-learning version",
        "",
        f"### Verdict: **{verdict}**",
        "",
    ]
    for r in reasons:
        L.append(f"- {r}")
    L += [
        "",
        "### Explicit criteria",
        "- **GO** if: concordant management shows a powered, protective renal RD "
        "(CI excludes 0) with the negative control null -- i.e. a recoverable gap a "
        "model could exploit.",
        "- **INPUTS-PENDING** if: PPV/outcome N < "
        f"{results['min_ppv_cases_for_verdict']} OR the vasoplegia axis "
        "(`vaso_responsiveness`) is not yet extracted -- re-run after the broader "
        "ART-waveform + vasoactive-PD extraction.",
        "- **NO-GO / NULL** if: no protective concordance association at adequate N "
        "(remembering a null can mean 'clinicians already optimal', so weigh it with "
        "the descriptive separation of the axes, not in isolation).",
        "",
        "**Fuller power needs the broader ART-waveform extraction** (more PPV cases) "
        "and the vasoactive-PD enrichment (`vaso_responsiveness`, `vaso_n_agents`, "
        "`vaso_pressor_duration_frac`) landing in `feature_matrix_enriched.csv`.",
        "",
        "## Methods (brief)",
        "- Preload-responsive from PPV>13 % (`art_ppv_mean`; SVV>13 % overrides where "
        "present). Vasoplegic from blunted `vaso_responsiveness` (OLS MAP-vs-pressor "
        "slope), where that axis is extracted.",
        "- Management is download-free from /cases (fluid tertiles + any-pressor "
        "presence), reusing the actionable_targets derivations. Pressor PHE-"
        "equivalent dose and fluid volume are **size-normalised per kg** (ug/kg, "
        "mL/kg) before tertiles; weight_kg+age+sex are in the IPTW covariate set.",
        "- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model "
        "(reused from hypotension_treatment.py), refit on the concordant exposure; "
        "PS covariates = the actionable confounder set.",
        "- Concordance HTE: pooled + within-recommendation-stratum IPTW RD/RR with "
        "nonparametric percentile-bootstrap 95% CIs; a (concordant x recommendation) "
        "IPTW logistic interaction; E-values (VanderWeele & Ding 2017); "
        "organ_hepatocellular negative control; BH-FDR across primary outcomes.",
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/aline_fluid_vs_pressor.py*",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[aline_fvp] ALINE_FLUID_VS_PRESSOR.md -> {md_path}")
    return md_path


def main():
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    res = run(cfg)
    print(json.dumps({
        "preliminary": res.get("preliminary"),
        "n_analysis": res["axis_availability"].get("n_analysis"),
        "recommendation_rule": res.get("recommendation_rule"),
    }, indent=2))


if __name__ == "__main__":
    main()
