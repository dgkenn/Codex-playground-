"""map_hte.py -- Personalized MAP target: heterogeneous treatment effect (HTE) of
intraoperative hypotension burden on postoperative organ injury (VitalDB).

Scientific question
-------------------
A higher intraoperative MAP target shows NULL benefit *in aggregate* after bias
control, yet the high-risk renal phenotype is real.  Is the association between
intraoperative HYPOTENSION BURDEN and organ injury HETEROGENEOUS -- concentrated
in patients whose cerebral/renal autoregulation is RIGHT-SHIFTED?  Those patients
are pre-specified as:

  (a) chronic hypertension          (``preop_htn`` == 1 vs 0),
  (b) chronic kidney disease (CKD)  (``egfr_ckdepi`` < 60 vs >= 60;
                                     fallback: top ``baseline_cr`` tertile vs rest),
  (c) older age                     (``age`` >= median vs <).

The headline claim, IF it holds: "hypertensive / CKD patients need a higher MAP;
normotensive patients tolerate 65."  This is the INPRESS / individualized-BP-target
controversy.

Design discipline
-----------------
OBSERVATIONAL, single-centre (VitalDB / SNUH).  Confounding by indication is the
central threat: sicker / more unstable patients sustain deeper hypotension AND are
more likely to suffer organ injury.  We reuse the propensity-score / IPTW machinery
from ``hypotension_treatment.py`` (stabilised, 1%-trimmed weights) and, for each
pre-specified subgroup:

  - an IPTW-weighted LOGISTIC outcome model with an
    ``exposure x subgroup`` INTERACTION term (does the hypotension effect DIFFER
    inside the right-shifted-autoregulation subgroup?), reported as interaction
    OR + bootstrap p, per subgroup x outcome;
  - the WITHIN-SUBGROUP IPTW dose-response: risk difference + risk ratio of
    HIGH-vs-LOW burden, with a percentile bootstrap 95% CI, shown across the
    burden thresholds (65/60/55/50, plus 70/75 if a higher-threshold extract is
    cached) so we can see whether the slope STEEPENS in the HTN / CKD / older arm;
  - an E-VALUE for each within-subgroup RR (point + null-nearest CI bound);
  - a NEGATIVE-CONTROL outcome (``organ_hepatocellular``): management / perfusion
    should NOT cause it, so a non-null interaction there flags residual confounding;
  - BH-FDR across all interaction tests.

LEAKAGE FIREWALL: confounders / subgroup-defining variables are PREOP + INTRAOP
only.  The postop ``organ_*`` / ``composite`` columns are OUTCOMES (y), NEVER
features.  When a variable IS the subgroup axis (e.g. preop_htn for the HTN
subgroup, egfr/baseline_cr for the CKD subgroup, age for the age subgroup) it is
DROPPED from that subgroup's confounder set to avoid conditioning on the
stratifier.

Everything here is HYPOTHESIS-GENERATING for a prospective trial; external
validation on INSPIRE is pending.

Heavy dependencies (numpy, pandas, sklearn) are lazy-imported INSIDE the functions
that need them so this module imports with the stdlib only, matching the repo
convention in actionable_targets.py / hypotension_treatment.py.  The pure helpers
(e_value, e_value_ci, benjamini_hochberg) are re-used from actionable_targets.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

# Re-use the validated pure helpers (stdlib-only) from the sibling module.
from vitaldb_aki.analysis.actionable_targets import (
    e_value,
    e_value_ci,
    benjamini_hochberg,
    _resolve_cache_dir,
    _resolve_seed,
    _json_default,
)

# ---------------------------------------------------------------------------
# Constants -- every threshold named here (config-as-code).
# ---------------------------------------------------------------------------

# PRIMARY exposure: MAP-AUC below 65 mmHg.min (continuous, and dichotomized at its
# median AMONG EXPOSED into high-vs-low burden).
PRIMARY_EXPOSURE = "map_auc_below_65"

# Burden thresholds for the dose-response gradient (does the slope steepen in the
# right-shifted-autoregulation subgroup?).  Higher thresholds (70/75) are merged
# from cache/map_thresholds.csv if that extract is present; we NEVER run extraction.
BURDEN_AUC_COLS = ["map_auc_below_65", "map_auc_below_60",
                   "map_auc_below_55", "map_auc_below_50"]
# Higher-threshold burden, present only if a map-threshold extract was cached.
HIGHER_THRESHOLD_MAP = {
    "map_auc_below_70": "auc_below_70",
    "map_auc_below_75": "auc_below_75",
}
_MAP_THRESHOLDS_FILE = "map_thresholds.csv"

# Outcomes.
PRIMARY_OUTCOME = "composite"
SECONDARY_OUTCOME = "organ_renal"
PRIMARY_OUTCOMES = (PRIMARY_OUTCOME, SECONDARY_OUTCOME)
# Negative control: intraoperative haemodynamic MANAGEMENT / PERFUSION is not a
# plausible cause of hepatocellular injury (driven by surgical field / hepatotoxic
# exposure); a non-null interaction there signals residual confounding.
NEGATIVE_CONTROL_OUTCOME = "organ_hepatocellular"

# CKD definition + fallback.
EGFR_COL = "egfr_ckdepi"
EGFR_CKD_CUTOFF = 60.0          # eGFR < 60 ml/min/1.73m2 -> CKD stage >=3
BASELINE_CR_COL = "baseline_cr"  # fallback CKD axis: top creatinine tertile

# Confounder set for the propensity model (PREOP + INTRAOP only -- NEVER postop).
# Only columns present in the merged frame are used; missing ones drop gracefully.
# ``sex_male`` is the encoded sex column in feature_matrix.csv.
DEFAULT_PS_COVARIATES = [
    "age", "sex_male", "asa",
    "preop_htn", "preop_dm", "baseline_cr", EGFR_COL,
    "intraop_ebl",
    "anesthesia_duration_min", "surgery_duration_min",
    "optype_code",
]

# Power threshold: subgroup x outcome cells with fewer events than this are
# reported but flagged "underpowered, hypothesis-only".
MIN_EVENTS_FOR_POWER = 15

N_BOOTSTRAP = 500
# The dose-response gradient reports POINT RD/RR per threshold (the "does the slope
# steepen" narrative); its per-cell CIs are descriptive, so it uses a lighter
# bootstrap to keep the 6-threshold x 2-arm x 3-outcome x 3-subgroup grid tractable
# under shared CPU. The HEADLINE within-arm effect + interaction keep full N_BOOTSTRAP.
N_BOOTSTRAP_GRADIENT = 200
RANDOM_SEED = 20260626          # matches config.yaml seed default

_DEFAULT_CACHE_SUBDIR = "vitaldb_aki/cache"
_FEATURE_MATRIX_FILE = "feature_matrix.csv"
_COMPOSITE_FILE = "cohort_composite.csv"
_RESULTS_JSON = "map_hte_results.json"


# ===========================================================================
# Pre-specified subgroups
# ===========================================================================
# Each subgroup: a key, a human label, the function building the 0/1 indicator
# (1 = right-shifted-autoregulation arm = "needs higher MAP" hypothesis), and the
# confounder(s) to DROP from the PS model because they DEFINE the stratifier.
SUBGROUP_SPECS = [
    {
        "key": "htn",
        "label": "chronic hypertension (preop_htn=1 vs 0)",
        "drop_confounders": ["preop_htn"],
    },
    {
        "key": "ckd",
        "label": "CKD (egfr_ckdepi<60 vs >=60; fallback top baseline_cr tertile)",
        "drop_confounders": [EGFR_COL, BASELINE_CR_COL],
    },
    {
        "key": "older",
        "label": "older age (age >= median vs <)",
        "drop_confounders": ["age"],
    },
]


# ===========================================================================
# STEP 1 -- cohort assembly (PREOP/INTRAOP features + merged outcomes)
# ===========================================================================

def build_cohort(cfg: dict[str, Any]):
    """Load feature_matrix.csv, merge outcomes from cohort_composite.csv (ONLY
    columns not already present), derive subgroup indicators + the dichotomized
    high-burden exposure + higher-threshold burden (if cached).

    Returns (df: pd.DataFrame, meta: dict).
    """
    import numpy as np
    import pandas as pd

    cache_dir = _resolve_cache_dir(cfg)
    matrix_path = os.path.join(cache_dir, _FEATURE_MATRIX_FILE)
    df = pd.read_csv(matrix_path)
    if "caseid" not in df.columns:
        raise RuntimeError("feature_matrix.csv has no 'caseid'; cannot merge outcomes.")

    # --- Merge outcomes from cohort_composite.csv (only cols not already present) ---
    comp_path = os.path.join(cache_dir, _COMPOSITE_FILE)
    if os.path.exists(comp_path):
        comp = pd.read_csv(comp_path)
        want = [PRIMARY_OUTCOME, SECONDARY_OUTCOME, NEGATIVE_CONTROL_OUTCOME]
        add = [c for c in want if c in comp.columns and c not in df.columns]
        if add:
            df = df.merge(comp[["caseid"] + add], on="caseid", how="left")

    # --- Merge higher-threshold MAP burden (70/75) IF a cached extract exists. ---
    higher_present = []
    thr_path = os.path.join(cache_dir, _MAP_THRESHOLDS_FILE)
    if os.path.exists(thr_path):
        thr = pd.read_csv(thr_path)
        ren = {}
        for new_col, src_col in HIGHER_THRESHOLD_MAP.items():
            if src_col in thr.columns and new_col not in df.columns:
                ren[src_col] = new_col
        if ren and "caseid" in thr.columns:
            sub = thr[["caseid"] + list(ren.keys())].rename(columns=ren)
            df = df.merge(sub, on="caseid", how="left")
            higher_present = list(ren.values())

    df = _encode_confounders(df)
    df = _derive_subgroups(df)
    df = _derive_high_burden(df)

    meta = {
        "n_cases": int(len(df)),
        "higher_threshold_burden_available": higher_present,
        "burden_gradient_cols": [c for c in (BURDEN_AUC_COLS + list(HIGHER_THRESHOLD_MAP))
                                 if c in df.columns],
        "exposed_n": int((pd.to_numeric(df[PRIMARY_EXPOSURE], errors="coerce") > 0).sum()),
        "high_burden_median_among_exposed": df.attrs.get("high_burden_cutoff"),
    }
    return df, meta


def _encode_confounders(df):
    """Ensure numeric sex + optype_code are available for the PS model.

    feature_matrix.csv already carries ``sex_male`` (0/1) and ``preop_htn`` /
    ``preop_dm`` as ints; we only need to factorize ``optype`` -> ``optype_code``.
    """
    import pandas as pd
    df = df.copy()
    if "optype" in df.columns and "optype_code" not in df.columns:
        codes, _ = pd.factorize(df["optype"].astype(str), sort=True)
        df["optype_code"] = codes.astype(float)
    return df


def _derive_subgroups(df):
    """Add the 0/1 subgroup indicator columns (1 = right-shifted-autoregulation arm).

    - htn   : preop_htn == 1
    - ckd   : egfr_ckdepi < 60; fallback to top baseline_cr tertile if egfr is
              missing/all-NaN.  NaN where neither axis is available for a case.
    - older : age >= median (median taken over non-missing ages).

    Also records, in df.attrs['ckd_definition'], which CKD axis was used.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()

    # (a) HTN
    if "preop_htn" in df.columns:
        htn = pd.to_numeric(df["preop_htn"], errors="coerce")
        df["sg_htn"] = htn.where(htn.isna(), (htn == 1).astype(float))
    else:
        df["sg_htn"] = np.nan

    # (b) CKD: egfr<60, fallback top creatinine tertile.
    ckd_def = "unavailable"
    sg_ckd = pd.Series(np.nan, index=df.index)
    egfr = pd.to_numeric(df.get(EGFR_COL), errors="coerce") if EGFR_COL in df.columns else None
    if egfr is not None and egfr.notna().any():
        sg_ckd = sg_ckd.where(egfr.isna(), (egfr < EGFR_CKD_CUTOFF).astype(float))
        ckd_def = f"{EGFR_COL} < {EGFR_CKD_CUTOFF}"
    else:
        cr = pd.to_numeric(df.get(BASELINE_CR_COL), errors="coerce") if BASELINE_CR_COL in df.columns else None
        if cr is not None and cr.notna().any():
            cut = cr.quantile(2.0 / 3.0)
            sg_ckd = sg_ckd.where(cr.isna(), (cr >= cut).astype(float))
            ckd_def = f"top tertile {BASELINE_CR_COL} (>= {round(float(cut), 3)})"
    df["sg_ckd"] = sg_ckd
    df.attrs["ckd_definition"] = ckd_def

    # (c) older age >= median
    if "age" in df.columns:
        age = pd.to_numeric(df["age"], errors="coerce")
        med = float(age.median()) if age.notna().any() else float("nan")
        df["sg_older"] = age.where(age.isna(), (age >= med).astype(float))
        df.attrs["age_median"] = med
    else:
        df["sg_older"] = np.nan
        df.attrs["age_median"] = float("nan")

    return df


def _derive_high_burden(df):
    """Dichotomize the PRIMARY exposure (map_auc_below_65) into ``high_burden``
    (0/1) at its MEDIAN AMONG EXPOSED cases (burden > 0).

    Cases with burden == 0 (no sub-65 episode) form the unexposed reference arm
    (high_burden = 0); among the exposed, those above the median burden are
    high_burden = 1.  Cases with a missing burden value get NaN.

    This is the dichotomization used for the IPTW propensity + interaction model;
    the continuous burden columns drive the gradient.
    """
    import numpy as np
    import pandas as pd

    df = df.copy()
    b = pd.to_numeric(df.get(PRIMARY_EXPOSURE), errors="coerce")
    exposed = b > 0
    cutoff = float(b[exposed].median()) if exposed.any() else float("nan")
    hb = pd.Series(np.nan, index=df.index)
    # burden 0 -> low (reference); burden > median -> high; in-between -> low.
    hb.loc[b.notna()] = 0.0
    if math.isfinite(cutoff):
        hb.loc[exposed & (b > cutoff)] = 1.0
    df["high_burden"] = hb
    df.attrs["high_burden_cutoff"] = round(cutoff, 4) if math.isfinite(cutoff) else None
    return df


# ===========================================================================
# STEP 2 -- IPTW (reuse hypotension_treatment machinery)
# ===========================================================================

def _fit_iptw_for_exposure(df, exposure_col, covariates):
    """Fit PS + stabilised, trimmed IPTW for a binary exposure, REUSING
    hypotension_treatment.fit_propensity_model / compute_iptw_weights.

    Those functions key off a ``vasopressor_treated`` column, so we alias the
    binary exposure into that name, run them, then return the frame with an
    ``iptw_weight`` column.

    Returns (df_w: DataFrame, used_covariates: list[str]) or (None, []) on failure.
    """
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )

    sub = df.copy()
    expo = pd.to_numeric(sub[exposure_col], errors="coerce")
    sub = sub[expo.notna()].copy()
    sub["vasopressor_treated"] = expo[expo.notna()].astype(int).to_numpy()

    if sub["vasopressor_treated"].nunique() < 2:
        return None, []

    avail = [c for c in covariates if c in sub.columns]
    if not avail:
        return None, []

    try:
        df_ps, _model, used = fit_propensity_model(sub, covariates=avail)
        df_w = compute_iptw_weights(df_ps)        # stabilised + 1%-trimmed
    except Exception:
        return None, []
    return df_w, used


def _weighted_risk_diff_ratio(y, expo, w):
    """IPTW risk difference + risk ratio (high-burden minus/over low-burden)."""
    import numpy as np
    y = np.asarray(y, dtype=float)
    e = np.asarray(expo, dtype=int)
    w = np.asarray(w, dtype=float)

    def _risk(mask):
        ww, yy = w[mask], y[mask]
        sw = ww.sum()
        return float((ww * yy).sum() / sw) if sw > 0 else float("nan")

    r1 = _risk(e == 1)
    r0 = _risk(e == 0)
    rd = r1 - r0
    rr = (r1 / r0) if (r0 and math.isfinite(r0) and r0 > 0) else float("nan")
    return r1, r0, rd, rr


def within_subgroup_effect(df_w, exposure_col, outcome, subgroup_col, sg_value,
                           n_bootstrap=N_BOOTSTRAP, seed=RANDOM_SEED):
    """IPTW RD + RR for ``exposure_col`` on ``outcome`` WITHIN one subgroup arm
    (``subgroup_col`` == ``sg_value``), with a percentile bootstrap 95% CI.

    Weights are taken as fixed (computed on the full eligible cohort) -- a
    documented simplification that does not re-estimate the PS inside each draw.

    Returns a dict with point estimates, CIs, n, events, exposed-n, power flag.
    """
    import numpy as np
    import pandas as pd

    sg = pd.to_numeric(df_w[subgroup_col], errors="coerce")
    arm = df_w[sg == sg_value].copy()
    y = pd.to_numeric(arm[outcome], errors="coerce")
    valid = y.notna() & arm[exposure_col].notna() & arm["iptw_weight"].notna()
    arm = arm[valid].copy()
    yv = pd.to_numeric(arm[outcome], errors="coerce").astype(int).to_numpy()
    ev = pd.to_numeric(arm[exposure_col], errors="coerce").astype(int).to_numpy()
    wv = arm["iptw_weight"].to_numpy(dtype=float)

    n = int(len(arm))
    n_events = int(yv.sum()) if n else 0
    n_exposed = int((ev == 1).sum()) if n else 0

    if n == 0 or ev.min() == ev.max():
        return {
            "n": n, "n_events": n_events, "n_exposed": n_exposed,
            "risk_exposed": None, "risk_unexposed": None,
            "risk_difference": None, "risk_ratio": None,
            "rd_ci": [None, None], "rr_ci": [None, None],
            "underpowered": True,
            "note": "no contrast (single burden arm) or empty cell",
        }

    r1, r0, rd, rr = _weighted_risk_diff_ratio(yv, ev, wv)

    rng = np.random.default_rng(seed)
    rd_boot, rr_boot = [], []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        eb = ev[idx]
        if eb.min() == eb.max():
            continue
        _, _, rdb, rrb = _weighted_risk_diff_ratio(yv[idx], eb, wv[idx])
        if math.isfinite(rdb):
            rd_boot.append(rdb)
        if math.isfinite(rrb):
            rr_boot.append(rrb)

    def _pct(arr, q):
        return float(np.percentile(arr, q)) if len(arr) else float("nan")

    rd_lo, rd_hi = _pct(rd_boot, 2.5), _pct(rd_boot, 97.5)
    rr_lo, rr_hi = _pct(rr_boot, 2.5), _pct(rr_boot, 97.5)

    return {
        "n": n,
        "n_events": n_events,
        "n_exposed": n_exposed,
        "risk_exposed": round(r1, 4) if math.isfinite(r1) else None,
        "risk_unexposed": round(r0, 4) if math.isfinite(r0) else None,
        "risk_difference": round(rd, 4) if math.isfinite(rd) else None,
        "risk_ratio": round(rr, 4) if math.isfinite(rr) else None,
        "rd_ci": [round(rd_lo, 4) if math.isfinite(rd_lo) else None,
                  round(rd_hi, 4) if math.isfinite(rd_hi) else None],
        "rr_ci": [round(rr_lo, 4) if math.isfinite(rr_lo) else None,
                  round(rr_hi, 4) if math.isfinite(rr_hi) else None],
        "underpowered": bool(n_events < MIN_EVENTS_FOR_POWER),
    }


def interaction_test(df_w, exposure_col, outcome, subgroup_col, seed=RANDOM_SEED):
    """IPTW-weighted logistic outcome model with an ``exposure x subgroup``
    INTERACTION term (sample-weighted by iptw_weight):

        logit P(outcome) = b0 + b1*exposure + b2*subgroup + b3*(exposure x subgroup)

    The interaction OR exp(b3) > 1 means the hypotension->injury association is
    STRONGER inside the right-shifted-autoregulation arm (subgroup == 1) -- the
    HTE direction the headline predicts.  p via the sign of the bootstrap
    distribution of b3 (two-sided).

    Returns a dict with interaction log-OR, OR, bootstrap p, main exposure log-OR.
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    sub = df_w.copy()
    y = pd.to_numeric(sub[outcome], errors="coerce")
    sgn = pd.to_numeric(sub[subgroup_col], errors="coerce")
    valid = (y.notna() & sub[exposure_col].notna()
             & sgn.notna() & sub["iptw_weight"].notna())
    sub = sub[valid].copy()
    yv = pd.to_numeric(sub[outcome], errors="coerce").astype(int).to_numpy()
    ex = pd.to_numeric(sub[exposure_col], errors="coerce").astype(float).to_numpy()
    sgv = pd.to_numeric(sub[subgroup_col], errors="coerce").astype(float).to_numpy()
    wv = sub["iptw_weight"].to_numpy(dtype=float)

    if (len(yv) == 0 or yv.min() == yv.max()
            or len(np.unique(ex)) < 2 or len(np.unique(sgv)) < 2):
        return {"interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None, "exposure_log_or": None,
                "n": int(len(yv)), "n_events": int(yv.sum()) if len(yv) else 0,
                "note": "insufficient variation to fit interaction model"}

    def _design(ex_, sg_):
        return np.column_stack([ex_, sg_, ex_ * sg_])

    def _fit(X_, y_, w_):
        lr = LogisticRegression(fit_intercept=True, max_iter=1000,
                                solver="lbfgs", C=1e6, random_state=seed)
        lr.fit(X_, y_, sample_weight=w_)
        return lr.coef_[0]   # [b_expo, b_sg, b_interaction]

    try:
        coef = _fit(_design(ex, sgv), yv, wv)
    except Exception:
        return {"interaction_log_or": None, "interaction_or": None,
                "interaction_p_bootstrap": None, "exposure_log_or": None,
                "n": int(len(yv)), "n_events": int(yv.sum()),
                "note": "model failed to converge"}

    b_expo, b_inter = float(coef[0]), float(coef[2])

    rng = np.random.default_rng(seed)
    n = len(yv)
    inter_boot = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, size=n)
        yb = yv[idx]
        if yb.min() == yb.max():
            continue
        try:
            cb = _fit(_design(ex[idx], sgv[idx]), yb, wv[idx])
            inter_boot.append(float(cb[2]))
        except Exception:
            continue
    if inter_boot:
        arr = np.asarray(inter_boot)
        if b_inter >= 0:
            p = 2.0 * float((arr <= 0).mean())
        else:
            p = 2.0 * float((arr >= 0).mean())
        p = min(1.0, max(0.0, p))
    else:
        p = None

    return {
        "interaction_log_or": round(b_inter, 4),
        "interaction_or": round(math.exp(b_inter), 4),
        "interaction_p_bootstrap": round(p, 4) if p is not None else None,
        "exposure_log_or": round(b_expo, 4),
        "n": int(n),
        "n_events": int(yv.sum()),
    }


# ===========================================================================
# STEP 3 -- per-subgroup analysis across outcomes + burden gradient
# ===========================================================================

def _subgroup_confounders(spec):
    """Confounders for one subgroup = DEFAULT minus the variable(s) that DEFINE it
    (never condition on the stratifier)."""
    drop = set(spec["drop_confounders"])
    return [c for c in DEFAULT_PS_COVARIATES if c not in drop]


def analyse_subgroup(df, spec, n_bootstrap=N_BOOTSTRAP, seed=RANDOM_SEED):
    """Full HTE analysis for ONE subgroup across all outcomes + the burden gradient.

    For each outcome (primary + negative control):
      - fit cohort IPTW on the dichotomized high-burden exposure (PS drops the
        stratifier variable),
      - run the exposure x subgroup interaction model (interaction OR + p),
      - within EACH subgroup arm (1 = right-shifted, 0 = reference): the IPTW
        RD/RR of high-vs-low burden with bootstrap CI + E-values,
      - the within-arm dose-response GRADIENT: RD/RR of high-vs-low burden
        recomputed dichotomizing each successive burden threshold, so we can see
        whether the slope steepens in the right-shifted arm.

    Returns a dict keyed by outcome (+ a 'negative_control' marker on that block).
    """
    import numpy as np
    import pandas as pd

    sg_col = f"sg_{spec['key']}"
    if sg_col not in df.columns or df[sg_col].isna().all():
        return {"subgroup": spec["key"], "available": False,
                "note": f"subgroup '{spec['key']}' indicator unavailable"}

    covariates = _subgroup_confounders(spec)
    df_w, used = _fit_iptw_for_exposure(df, "high_burden", covariates)
    if df_w is None:
        return {"subgroup": spec["key"], "available": False,
                "note": "could not fit propensity / IPTW for high_burden"}
    # Carry the subgroup column into the weighted frame (row order preserved by
    # fit_propensity_model / compute_iptw_weights, which copy in place).
    df_w[sg_col] = pd.to_numeric(df_w[sg_col], errors="coerce")

    out: dict[str, Any] = {
        "subgroup": spec["key"],
        "label": spec["label"],
        "available": True,
        "ps_covariates": used,
        "subgroup_n": {
            "right_shifted_arm_n": int((pd.to_numeric(df[sg_col], errors="coerce") == 1).sum()),
            "reference_arm_n": int((pd.to_numeric(df[sg_col], errors="coerce") == 0).sum()),
        },
    }

    all_outcomes = list(PRIMARY_OUTCOMES) + [NEGATIVE_CONTROL_OUTCOME]
    for oc in all_outcomes:
        if oc not in df_w.columns or df_w[oc].isna().all():
            out[oc] = {"available": False, "note": "outcome column missing/all-NaN"}
            continue

        inter = interaction_test(df_w, "high_burden", oc, sg_col, seed=seed)

        within_right = within_subgroup_effect(
            df_w, "high_burden", oc, sg_col, 1, n_bootstrap=n_bootstrap, seed=seed)
        within_ref = within_subgroup_effect(
            df_w, "high_burden", oc, sg_col, 0, n_bootstrap=n_bootstrap, seed=seed)

        # E-values for the right-shifted-arm RR (the headline number).
        rr = within_right.get("risk_ratio")
        rr_ci = within_right.get("rr_ci", [None, None])
        ev_point = e_value(rr) if rr is not None else None
        ev_ci = (e_value_ci(rr, rr_ci[0], rr_ci[1])
                 if (rr is not None and rr_ci[0] is not None and rr_ci[1] is not None)
                 else None)

        # Dose-response gradient across burden thresholds, per arm (lighter boot).
        gradient = _burden_gradient(df_w, oc, sg_col,
                                    n_bootstrap=N_BOOTSTRAP_GRADIENT, seed=seed)

        block = {
            "available": True,
            "subgroup_interaction": inter,
            "within_right_shifted_arm": within_right,
            "within_reference_arm": within_ref,
            "e_value_point": round(ev_point, 3) if ev_point is not None else None,
            "e_value_ci": round(ev_ci, 3) if ev_ci is not None else None,
            "underpowered": within_right.get("underpowered", True),
            "burden_gradient": gradient,
        }
        if oc == NEGATIVE_CONTROL_OUTCOME:
            block["is_negative_control"] = True
            io = inter.get("interaction_or")
            ip = inter.get("interaction_p_bootstrap")
            block["negative_control_flag"] = (
                "NON-NULL interaction (possible residual confounding)"
                if (ip is not None and ip < 0.05) else "null (reassuring)"
            )
        out[oc] = block

    return out


def _burden_gradient(df_w, outcome, sg_col, n_bootstrap=N_BOOTSTRAP_GRADIENT, seed=RANDOM_SEED):
    """Within-arm dose-response: for each burden threshold column, dichotomize at
    the median among exposed and compute the IPTW high-vs-low RD/RR per arm.

    Steepening of the gradient (larger RD/RR at deeper thresholds) in the
    right-shifted arm vs the reference arm is the dose-response signature of the
    HTE hypothesis.  Weights are held fixed (the high_burden PS weights) -- this
    is a descriptive gradient, not a re-weighted re-estimation per threshold.

    Returns a dict: {col: {"right_shifted": {...}, "reference": {...}}} with the
    point RD/RR/CI + n/events per arm.
    """
    import numpy as np
    import pandas as pd

    grad: dict[str, Any] = {}
    for col in BURDEN_AUC_COLS + list(HIGHER_THRESHOLD_MAP):
        if col not in df_w.columns:
            continue
        b = pd.to_numeric(df_w[col], errors="coerce")
        exposed = b > 0
        if not exposed.any():
            continue
        cutoff = float(b[exposed].median())
        if not math.isfinite(cutoff):
            continue
        hb = pd.Series(np.nan, index=df_w.index)
        hb.loc[b.notna()] = 0.0
        hb.loc[exposed & (b > cutoff)] = 1.0
        tmp = df_w.copy()
        tmp["_grad_burden"] = hb
        right = within_subgroup_effect(tmp, "_grad_burden", outcome, sg_col, 1,
                                       n_bootstrap=n_bootstrap, seed=seed)
        ref = within_subgroup_effect(tmp, "_grad_burden", outcome, sg_col, 0,
                                     n_bootstrap=n_bootstrap, seed=seed)
        grad[col] = {
            "cutoff_median_among_exposed": round(cutoff, 4),
            "right_shifted": {k: right[k] for k in
                              ("risk_difference", "rd_ci", "risk_ratio", "rr_ci",
                               "n", "n_events", "n_exposed", "underpowered")},
            "reference": {k: ref[k] for k in
                          ("risk_difference", "rd_ci", "risk_ratio", "rr_ci",
                           "n", "n_events", "n_exposed", "underpowered")},
        }
    return grad


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================

def run_map_hte(cfg: dict[str, Any]) -> dict[str, Any]:
    """Public entry point.  Run the full personalized-MAP-target HTE analysis.

    Pipeline:
      1. Assemble cohort (feature_matrix + merged outcomes + subgroups + exposure).
      2. For each pre-specified subgroup x outcome: cohort IPTW with an
         exposure x subgroup interaction + within-arm RD/RR with bootstrap CI +
         E-values + burden gradient; plus the negative-control outcome.
      3. BH-FDR across all interaction tests (primary outcomes, both arms' headline
         = the interaction p per subgroup x primary-outcome).
      4. Write map_hte_results.json + docs/MAP_HTE.md.

    Returns the full results dict.
    """
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    os.makedirs(cache_dir, exist_ok=True)

    df, cohort_meta = build_cohort(cfg)
    cohort_meta["ckd_definition"] = df.attrs.get("ckd_definition")
    cohort_meta["age_median"] = df.attrs.get("age_median")

    per_subgroup = {}
    pvals_for_fdr = []
    pval_keys = []
    for spec in SUBGROUP_SPECS:
        res = analyse_subgroup(df, spec, seed=seed)
        per_subgroup[spec["key"]] = res
        if res.get("available"):
            for oc in PRIMARY_OUTCOMES:
                blk = res.get(oc, {})
                p = (blk.get("subgroup_interaction") or {}).get("interaction_p_bootstrap")
                pvals_for_fdr.append(p)
                pval_keys.append((spec["key"], oc))

    reject = benjamini_hochberg([p if p is not None else 1.0 for p in pvals_for_fdr])
    fdr = {}
    for (sg, oc), p, rj in zip(pval_keys, pvals_for_fdr, reject):
        fdr.setdefault(sg, {})[oc] = {"interaction_p": p, "fdr_reject": bool(rj)}

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "analysis": "personalized_map_target_hte",
        "seed": seed,
        "min_events_for_power": MIN_EVENTS_FOR_POWER,
        "primary_exposure": PRIMARY_EXPOSURE,
        "exposure_dichotomization": "high vs low burden at median map_auc_below_65 among exposed",
        "burden_gradient_cols": cohort_meta["burden_gradient_cols"],
        "confounder_set_full": DEFAULT_PS_COVARIATES,
        "primary_outcomes": list(PRIMARY_OUTCOMES),
        "negative_control_outcome": NEGATIVE_CONTROL_OUTCOME,
        "subgroup_specs": [{"key": s["key"], "label": s["label"],
                            "dropped_confounders": s["drop_confounders"]}
                           for s in SUBGROUP_SPECS],
        "cohort": cohort_meta,
        "subgroups": per_subgroup,
        "fdr_interaction": fdr,
        "interpretation": (
            "Observational, single-centre (VitalDB / SNUH); confounding-by-"
            "indication is the central threat. The exposure x subgroup interaction "
            "OR > 1 means the hypotension->injury association is STRONGER in the "
            "right-shifted-autoregulation arm (HTN / CKD / older) -- the "
            "individualized-MAP-target (INPRESS) hypothesis. Effects are "
            "HYPOTHESIS-GENERATING; external validation on INSPIRE pending. "
            "E-values quantify required unmeasured-confounder strength; the "
            "organ_hepatocellular negative control checks residual confounding."
        ),
    }

    results_path = os.path.join(cache_dir, _RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[map_hte] results written to {results_path}")

    _write_map_hte_md(results, cfg)
    return results


# ===========================================================================
# REPORT
# ===========================================================================

def _fmt(v):
    return "n/a" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _rank_subgroups(results):
    """Order subgroups by best-powered + strongest HTE: prefer an available block
    whose primary-outcome interaction OR > 1 with a small p, adequate power, then
    by interaction OR magnitude."""
    scored = []
    for sg, res in results["subgroups"].items():
        if not res.get("available"):
            continue
        blk = res.get(PRIMARY_OUTCOME, {})
        inter = blk.get("subgroup_interaction", {}) if blk.get("available") else {}
        io = inter.get("interaction_or")
        p = inter.get("interaction_p_bootstrap")
        powered = not blk.get("underpowered", True)
        sig = (p is not None and p < 0.05)
        mag = abs(math.log(io)) if isinstance(io, (int, float)) and io and io > 0 else 0.0
        scored.append(((1 if powered else 0, 1 if sig else 0, mag), sg))
    scored.sort(reverse=True)
    return [s for _, s in scored]


def _write_map_hte_md(results: dict, cfg: dict) -> str:
    """Write the human-readable docs/MAP_HTE.md report (READ-FIRST limitations
    block first, then findings led by the best-powered subgroup, then methods)."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "MAP_HTE.md")

    cohort = results["cohort"]
    higher = cohort.get("higher_threshold_burden_available") or []
    L = [
        "# Personalized MAP Target -- Heterogeneous Treatment Effect (HTE)",
        "",
        "## Interpretation & limitations (READ FIRST)",
        "",
        "- **Observational, single-centre** (VitalDB / SNUH). MAP target was not",
        "  randomised; **confounding by indication** is the central threat -- sicker /",
        "  more unstable patients sustain deeper intraoperative hypotension AND are",
        "  more likely to sustain organ injury, biasing the burden->injury estimate",
        "  TOWARD harm.",
        "- The HEADLINE is the **exposure x subgroup INTERACTION**: an interaction",
        "  OR **> 1** means the hypotension-burden -> organ-injury association is",
        "  **stronger** inside the right-shifted-autoregulation arm (chronic HTN /",
        "  CKD / older) -- i.e. those patients are hypothesised to **need a higher",
        "  MAP** while normotensive patients tolerate 65 (the INPRESS /",
        "  individualized-BP-target controversy).",
        "- Within-arm effects are IPTW-adjusted for the PREOP+INTRAOP confounder set",
        f"  `{results['confounder_set_full']}`; the variable that DEFINES a subgroup is",
        "  dropped from that subgroup's confounder set (never condition on the",
        "  stratifier).",
        "- **E-values** quantify how strong an unmeasured confounder would have to be",
        "  (risk-ratio scale) to explain a within-arm result away. A small E-value",
        "  (~1-1.5) means weak residual confounding could nullify the finding.",
        f"- **Negative control:** `{results['negative_control_outcome']}` -- intraoperative",
        "  perfusion/management is not a plausible cause of hepatocellular injury;",
        "  a non-null INTERACTION there flags residual confounding.",
        f"- **Power:** subgroup x outcome cells with < {results['min_events_for_power']} events",
        "  (right-shifted arm) are reported but marked **underpowered, hypothesis-only**.",
        "- These are **HYPOTHESIS-GENERATING for a prospective trial**, not causal",
        "  proof. **External validation on INSPIRE is pending.**",
    ]
    if not higher:
        L += [
            "- **Burden-threshold limitation:** higher-threshold burden",
            "  (`map_auc_below_70` / `_75`) was NOT available in the cache; the",
            "  dose-response gradient spans 65/60/55/50 only. No extraction was run.",
        ]
    else:
        L += [
            f"- Higher-threshold burden available and used: `{', '.join(higher)}` "
            "(from the cached map-threshold extract).",
        ]
    L += [
        "",
        "## Cohort & exposure",
        "",
        f"- N cases = {cohort.get('n_cases')}; exposed (any MAP-AUC<65) = "
        f"{cohort.get('exposed_n')}.",
        f"- PRIMARY exposure = `{results['primary_exposure']}` (continuous);",
        f"  dichotomized HIGH vs LOW at the median burden among exposed = "
        f"{_fmt(cohort.get('high_burden_median_among_exposed'))} mmHg.min.",
        f"- Burden gradient columns: `{', '.join(cohort.get('burden_gradient_cols', []))}`.",
        f"- CKD definition: {cohort.get('ckd_definition')}; age median split = "
        f"{_fmt(cohort.get('age_median'))} y.",
        "",
        "## Subgroups (pre-specified)",
        "",
    ]
    for s in results["subgroup_specs"]:
        L.append(f"- **{s['key']}** -- {s['label']} "
                 f"(dropped from its confounder set: `{s['dropped_confounders']}`).")
    L += ["", "## Findings (led by best-powered + strongest HTE)", ""]

    order = _rank_subgroups(results)
    if not order:
        L += ["_No subgroup produced an estimable interaction (data may be "
              "incomplete)._", ""]

    for sg in order:
        res = results["subgroups"][sg]
        fdr_sg = results["fdr_interaction"].get(sg, {})
        L.append(f"### {sg} -- {res.get('label', '')}")
        narm = res.get("subgroup_n", {})
        L.append(f"- Arm sizes: right-shifted n = {narm.get('right_shifted_arm_n')}, "
                 f"reference n = {narm.get('reference_arm_n')}.")
        for oc in results["primary_outcomes"]:
            blk = res.get(oc, {})
            if not blk.get("available"):
                L.append(f"- **{oc}:** not available.")
                continue
            inter = blk.get("subgroup_interaction", {})
            wr = blk.get("within_right_shifted_arm", {})
            wref = blk.get("within_reference_arm", {})
            flag = " **[UNDERPOWERED, hypothesis-only]**" if blk.get("underpowered") else ""
            rej = fdr_sg.get(oc, {}).get("fdr_reject")
            L.append(
                f"- **{oc}:** interaction OR = {_fmt(inter.get('interaction_or'))} "
                f"(p = {_fmt(inter.get('interaction_p_bootstrap'))}"
                f"{', FDR-significant' if rej else ''}). "
                f"Within RIGHT-SHIFTED arm: high-vs-low burden "
                f"RD = {_fmt(wr.get('risk_difference'))} "
                f"(95% CI {_fmt(wr.get('rd_ci', [None, None])[0])} to "
                f"{_fmt(wr.get('rd_ci', [None, None])[1])}); "
                f"RR = {_fmt(wr.get('risk_ratio'))} "
                f"(95% CI {_fmt(wr.get('rr_ci', [None, None])[0])} to "
                f"{_fmt(wr.get('rr_ci', [None, None])[1])}). "
                f"n = {wr.get('n')}, events = {wr.get('n_events')}.{flag}"
            )
            L.append(
                f"  - Reference arm (for contrast): RD = {_fmt(wref.get('risk_difference'))}, "
                f"RR = {_fmt(wref.get('risk_ratio'))}, "
                f"n = {wref.get('n')}, events = {wref.get('n_events')}."
            )
            L.append(
                f"  - E-value (right-shifted RR, point) = {_fmt(blk.get('e_value_point'))}, "
                f"E-value (CI) = {_fmt(blk.get('e_value_ci'))}."
            )
            # Dose-response gradient (right-shifted arm RR across thresholds).
            grad = blk.get("burden_gradient", {})
            if grad:
                cells = []
                for col in results["cohort"].get("burden_gradient_cols", []):
                    g = grad.get(col)
                    if not g:
                        continue
                    rrr = g["right_shifted"].get("risk_ratio")
                    cells.append(f"{col.replace('map_auc_below_', '<')}: "
                                 f"RR={_fmt(rrr)}")
                if cells:
                    L.append("  - Right-shifted-arm RR gradient across thresholds: "
                             + "; ".join(cells) + ".")
        nc = res.get(results["negative_control_outcome"], {})
        if nc.get("available"):
            inter = nc.get("subgroup_interaction", {})
            L.append(
                f"- _Negative control ({results['negative_control_outcome']}):_ "
                f"interaction OR = {_fmt(inter.get('interaction_or'))} "
                f"(p = {_fmt(inter.get('interaction_p_bootstrap'))}) -> "
                f"{nc.get('negative_control_flag')}."
            )
        L.append("")

    unavail = [s for s, r in results["subgroups"].items() if not r.get("available")]
    if unavail:
        L += ["## Subgroups not analysable", ""]
        for s in unavail:
            L.append(f"- **{s}:** {results['subgroups'][s].get('note', 'unavailable')}")
        L.append("")

    L += [
        "## Methods (brief)",
        "",
        "- Cohort: `feature_matrix.csv` merged with `cohort_composite.csv` outcomes",
        "  (only columns not already present). Subgroup indicators + the dichotomized",
        "  high-burden exposure derived from preop / intraop columns only.",
        "- Exposure: PRIMARY = `map_auc_below_65` (continuous); dichotomized HIGH vs",
        "  LOW at the median burden among exposed (burden==0 -> low reference). The",
        "  burden gradient re-dichotomizes each successive AUC threshold.",
        "- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model",
        "  (reused from `hypotension_treatment.py`), refit per subgroup (the",
        "  stratifier variable dropped from the PS covariates).",
        "- PRIMARY model: IPTW-weighted logistic outcome model with an",
        "  exposure x subgroup interaction term; interaction OR > 1 = stronger",
        "  hypotension->injury association in the right-shifted arm.",
        "- Within-arm RD/RR: IPTW-weighted arm risks; 95% CI by nonparametric",
        "  percentile bootstrap (weights fixed).",
        "- E-value: VanderWeele & Ding (2017), point + null-nearest CI bound.",
        "- Multiplicity: Benjamini-Hochberg FDR across the subgroup x primary-outcome",
        "  interaction tests.",
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/map_hte.py*",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[map_hte] MAP_HTE.md written to {md_path}")
    return md_path


# ===========================================================================
# CLI
# ===========================================================================

def main():
    """Load config.yaml and run.  Requires the real feature_matrix / composite caches."""
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    res = run_map_hte(cfg)
    print(json.dumps(res["cohort"], indent=2))
    print(json.dumps(res["fdr_interaction"], indent=2))


if __name__ == "__main__":
    main()
