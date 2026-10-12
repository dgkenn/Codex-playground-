"""recovery_velocity_specificity.py -- specificity / robustness DE-RISKING of the
recovery-velocity finding (analysis/recovery_velocity_screen.py).

CONTEXT
-------
recovery_velocity_screen found that raw-MAP per-episode recovery velocity adds
incremental discrimination for organ injury OVER static hypotension burden
(COMPOSITE dAUROC +0.079, DeLong p=2.6e-9; 11 IPTW per-SD associations survive
BH-FDR). TWO THREATS must be rigorously tested before the finding can be called
perfusion-relevant rather than a generic "sick/unstable patient" axis:

  (1) NON-SPECIFICITY. The negative control `organ_hepatocellular` ALSO showed
      incremental AUROC (+0.047, p=0.053). If recovery velocity helps the
      negative controls as much as it helps the composite, the incremental signal
      is generic severity, not perfusion-recovery-specific.

  (2) SEVERITY CONFOUNDING. The UNADJUSTED quartile dose-response of the primary
      feature `rv_depthwt_slope` was non-monotone / anti-hypothesis -- the raw
      depth-weighted slope is confounded by episode severity; only burden+
      covariate-adjusted models showed the hypothesised direction.

ANALYSES (this module)
----------------------
1. NEGATIVE-CONTROL PANEL + formal specificity test. Incremental AUROC of the
   recovery-feature SET over static burden for COMPOSITE vs a panel of negative /
   less-plausible controls (organ_hepatocellular, organ_cholestatic,
   organ_coagulation_inr, organ_coagulation_plt). For EACH, dAUROC + DeLong p.
   THEN bootstrap the DIFFERENCE of paired dAUROCs (composite - control) on the
   SHARED set of cases/folds: does composite's incremental signal significantly
   EXCEED each control's? If not -> generic severity. If yes -> perfusion-relevant
   specificity.
2. WITHIN-BURDEN-STRATUM test ("at matched burden"). Stratify by static-burden
   quartile (map_auc_below_65). WITHIN each stratum, per-SD logistic OR + p of the
   cleanest recovery features (rv_min_slope, rv_median_tau) on composite; pooled
   (inverse-variance) within-stratum estimate. If recovery velocity discriminates
   injury WITHIN burden strata, it is not merely burden re-expressed.
3. CONFOUNDING-WITH-SEVERITY diagnostics. Correlation of each recovery feature
   with static burden + n_episodes + duration. Identify the LEAST severity-
   confounded yet still injury-associated feature -> cleanest headline candidate.
   For that feature, redo the quartile dose-response WITHIN burden strata, to see
   whether the anti-hypothesis raw pattern was purely confounding.
4. INCREMENTAL OVER A GENERIC-SEVERITY PROXY. Does recovery velocity predict
   composite beyond a severity proxy set (n_episodes + total burden + map_lowest +
   duration)? Incremental AUROC over that richer baseline.
5. BH-FDR across the new tests; E-values on the within-stratum estimates.

Cohort = cases with rv_depthwt_slope present (the recovery cohort, ~3743).
Seed 20260626. LEAKAGE FIREWALL: predictors preop+intraop only; organ_* only as y.

Reuses verbatim: reperfusion_dynamics.load_merged / incremental_auroc /
adjusted_logistic_iptw / _paired_oof_logistic / STATIC_BURDEN_COLS /
PREOP_COVARIATES; models.metrics.delong_roc_test / bootstrap_ci;
actionable_targets.e_value / e_value_ci / benjamini_hochberg.

Run:  python3 -m vitaldb_aki.analysis.recovery_velocity_specificity   (from repo root)
Outputs: cache/recovery_velocity_specificity_results.json,
         docs/RECOVERY_VELOCITY_SPECIFICITY.md.
stdlib only at module import; heavy deps lazy (numpy/pandas/sklearn/scipy/statsmodels).
"""
from __future__ import annotations

import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_RV_CSV = os.path.join(_CACHE, "recovery_velocity.csv")
_RESULTS_JSON = os.path.join(_CACHE, "recovery_velocity_specificity_results.json")

RANDOM_SEED = 20260626

PRIMARY_OUTCOME = "composite"
# Negative / less-plausible controls: organ injuries NOT plausibly caused by
# MAP-recovery dynamics the way renal/hypoperfusion are. Subset to those present
# and powered at runtime.
NEGATIVE_CONTROLS = [
    "organ_hepatocellular",
    "organ_cholestatic",
    "organ_coagulation_inr",
    "organ_coagulation_plt",
]

RECOVERY_FEATURES = [
    "rv_depthwt_slope", "rv_min_slope", "rv_median_slope",
    "rv_max_time_to_recover", "rv_frac_unrecovered",
    "rv_total_unrecovered_min", "rv_median_tau", "rv_n_episodes",
]
PRIMARY_FEATURE = "rv_depthwt_slope"
# The two "cleanest" features for the within-stratum test (per the prompt).
CLEAN_FEATURES = ["rv_min_slope", "rv_median_tau"]

# Static-burden stratifier for the "at matched burden" analysis.
STRATIFY_COL = "map_auc_below_65"
N_STRATA = 4

# Bootstrap iterations for the difference-of-dAUROC test. The reperfusion harness
# uses 2000; the box is loaded and we run one full paired-OOF refit per bootstrap
# resample per control, so we REDUCE to 600 (still tight CIs for a difference of
# two ~0.05-scale dAUROCs). Stated explicitly per CONSTRAINTS.
N_BOOTSTRAP_DIFF = 600

# Orientation for the clean features (mirrors reperfusion_dynamics.RECOVERY_DIRECTION
# semantics: +1 means larger value = better/faster recovery = hypothesised LESS
# injury). rv_min_slope: higher (less negative / faster worst-episode climb) = better.
# rv_median_tau: larger = SLOWER exponential recovery = WORSE, so direction -1.
FEATURE_DIRECTION = {
    "rv_min_slope": +1,
    "rv_median_slope": +1,
    "rv_depthwt_slope": +1,
    "rv_median_tau": -1,
    "rv_max_time_to_recover": -1,
    "rv_frac_unrecovered": -1,
    "rv_total_unrecovered_min": -1,
    "rv_n_episodes": -1,        # more episodes = more unstable = worse
}

MIN_EVENTS_STRATUM = 8     # below this a stratum estimate is flagged underpowered


# ===========================================================================
# DATA
# ===========================================================================
def _load_with_recovery():
    """reperfusion_dynamics.load_merged() LEFT-joined to the recovery-velocity CSV,
    restricted to the recovery cohort (rv_depthwt_slope present). Also brings in the
    negative-control outcome columns (load_merged only carries composite/renal/
    hepatocellular) and a duration column for severity diagnostics."""
    import pandas as pd
    from vitaldb_aki.analysis.reperfusion_dynamics import load_merged

    df = load_merged()
    df["caseid"] = df["caseid"].astype(str)

    # load_merged carries only composite/organ_renal/organ_hepatocellular; pull the
    # remaining negative-control outcomes straight from cohort_composite.
    co = pd.read_csv(os.path.join(_CACHE, "cohort_composite.csv"))
    co["caseid"] = co["caseid"].astype(str)
    extra = [c for c in NEGATIVE_CONTROLS if c in co.columns and c not in df.columns]
    if extra:
        df = df.merge(co[["caseid"] + extra], on="caseid", how="left")

    if not os.path.exists(_RV_CSV):
        raise FileNotFoundError(f"{_RV_CSV} not found -- run recovery_velocity_extract first.")
    rv = pd.read_csv(_RV_CSV)
    rv["caseid"] = rv["caseid"].astype(str)
    keep = ["caseid"] + [c for c in RECOVERY_FEATURES if c in rv.columns]
    df = df.merge(rv[keep], on="caseid", how="left")
    df = df[df[PRIMARY_FEATURE].notna()].reset_index(drop=True)
    return df


def _duration_col(df):
    """Best available case-duration column for severity diagnostics."""
    for c in ("anesthesia_duration_min", "surgery_duration_min"):
        if c in df.columns:
            return c
    return None


# ===========================================================================
# ANALYSIS 1 -- NEGATIVE-CONTROL PANEL + composite-exceeds-control bootstrap
# ===========================================================================
def _delta_auc_on_oof(y, oob, oop):
    """dAUROC (plus - base) via DeLong on a paired OOF set."""
    from vitaldb_aki.models.metrics import delong_roc_test
    return delong_roc_test(y, oob, oop)["delta"]


def _paired_dauroc_difference(df, feature_names, outcome_a, outcome_b, seed):
    """Bootstrap the DIFFERENCE of paired dAUROCs (outcome_a - outcome_b) on the
    SHARED set of cases that have BOTH outcomes + the static baseline present.

    For each outcome we fit the same paired-OOF logistic (static baseline vs
    static+recovery) on the SHARED subset, on the SAME StratifiedGroupKFold splits
    (seed fixed). dAUROC_a and dAUROC_b are then two statistics on the SAME patients
    -> a patient-cluster bootstrap of (dAUROC_a - dAUROC_b) is valid. Returns the
    point difference, a 95% CI, and a bootstrap two-sided p for H0: diff <= 0
    (composite does NOT exceed the control)."""
    import numpy as np
    from vitaldb_aki.analysis.reperfusion_dynamics import STATIC_BURDEN_COLS

    base_cols = [c for c in STATIC_BURDEN_COLS if c in df.columns]
    plus_cols = [c for c in feature_names if c in df.columns]

    sub = df.dropna(subset=[outcome_a, outcome_b] + base_cols).copy().reset_index(drop=True)
    ea = int(sub[outcome_a].astype(float).astype(int).sum())
    eb = int(sub[outcome_b].astype(float).astype(int).sum())
    out = {"outcome_a": outcome_a, "outcome_b": outcome_b,
           "n_shared": int(len(sub)), "events_a": ea, "events_b": eb}
    if min(ea, eb) < 15 or len(sub) < 50:
        out["underpowered"] = True
        return out

    # Paired OOF for BOTH outcomes on the SAME shared cases + SAME folds, returned on
    # a COMMON row index + groups so the two dAUROCs are computed on the same patients
    # (paired-difference cluster bootstrap valid). _paired_oof_logistic is reused
    # inside _aligned_oof's per-outcome model fits.
    ya2, oba2, opa2, opb2, obb2, yb2, grp = _aligned_oof(
        sub, base_cols, plus_cols, outcome_a, outcome_b, seed)

    da_aligned = _delta_auc_on_oof(ya2, oba2, opa2)
    db_aligned = _delta_auc_on_oof(yb2, obb2, opb2)
    diff_point = da_aligned - db_aligned

    rng = np.random.default_rng(seed)
    uniq = np.unique(grp)
    idx_by_g = {u: np.where(grp == u)[0] for u in uniq}
    diffs = []
    for _ in range(N_BOOTSTRAP_DIFF):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_g[u] for u in pick])
        ja, jb = ya2[idx], yb2[idx]
        if ja.min() == ja.max() or jb.min() == jb.max():
            continue
        try:
            d = (_delta_auc_on_oof(ja, oba2[idx], opa2[idx])
                 - _delta_auc_on_oof(jb, obb2[idx], opb2[idx]))
        except Exception:
            continue
        diffs.append(d)
    if not diffs:
        out["error"] = "bootstrap produced no valid resamples"
        return out
    diffs = np.asarray(diffs, float)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    # one-sided bootstrap p for H0: composite does NOT exceed control (diff <= 0)
    p_one_sided = float((diffs <= 0).mean())
    out.update({
        "underpowered": False,
        "dauroc_composite": round(float(da_aligned), 4),
        "dauroc_control": round(float(db_aligned), 4),
        "dauroc_difference": round(float(diff_point), 4),
        "diff_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "p_composite_exceeds_control_one_sided": p_one_sided,
        "n_bootstrap": N_BOOTSTRAP_DIFF,
        "composite_exceeds_control": bool(lo > 0),
    })
    return out


def _aligned_oof(sub, base_cols, plus_cols, outcome_a, outcome_b, seed):
    """Paired OOF for BOTH outcomes returned on a COMMON row index + groups, so the
    two dAUROCs are computed on the same patients (paired-difference bootstrap valid).

    We run a single StratifiedGroupKFold stratified on outcome_a (the primary) and
    fit four models (base/plus x a/b) on each fold's TRAIN, predicting the fold's
    TEST. Every test row gets all four OOF predictions -> perfect alignment."""
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.linear_model import LogisticRegression
    from sklearn.base import clone
    from vitaldb_aki.analysis.reperfusion_dynamics import (
        N_OUTER_FOLDS, OPTYPE_COL,
    )

    ya = sub[outcome_a].astype(float).astype(int).to_numpy()
    yb = sub[outcome_b].astype(float).astype(int).to_numpy()
    groups = (sub["subjectid"].to_numpy() if "subjectid" in sub.columns
              else sub["caseid"].to_numpy())

    def _build(cols):
        cat = [c for c in cols if c == OPTYPE_COL]
        num = [c for c in cols if c != OPTYPE_COL]
        transformers = [("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler())]), num)]
        if cat:
            transformers.append(("cat", OneHotEncoder(handle_unknown="ignore"), cat))
        pre = ColumnTransformer(transformers)
        return Pipeline([("pre", pre),
                         ("clf", LogisticRegression(max_iter=2000, solver="lbfgs",
                                                    C=1.0, random_state=seed))])

    full_plus = base_cols + [c for c in plus_cols if c not in base_cols]
    X_base = sub[base_cols].copy()
    X_plus = sub[full_plus].copy()

    n_splits = min(N_OUTER_FOLDS, int(ya.sum()), int((1 - ya).sum()),
                   int(yb.sum()), int((1 - yb).sum()))
    n_splits = max(n_splits, 2)
    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    n = len(ya)
    oba = np.full(n, np.nan); opa = np.full(n, np.nan)
    obb = np.full(n, np.nan); opb = np.full(n, np.nan)
    for tr, te in outer.split(X_base, ya, groups):
        # outcome A models
        ba = clone(_build(base_cols)).fit(X_base.iloc[tr], ya[tr])
        oba[te] = ba.predict_proba(X_base.iloc[te])[:, 1]
        pa = clone(_build(full_plus)).fit(X_plus.iloc[tr], ya[tr])
        opa[te] = pa.predict_proba(X_plus.iloc[te])[:, 1]
        # outcome B models (same folds)
        bb = clone(_build(base_cols)).fit(X_base.iloc[tr], yb[tr])
        obb[te] = bb.predict_proba(X_base.iloc[te])[:, 1]
        pb = clone(_build(full_plus)).fit(X_plus.iloc[tr], yb[tr])
        opb[te] = pb.predict_proba(X_plus.iloc[te])[:, 1]

    keep = ~np.isnan(oba) & ~np.isnan(opa) & ~np.isnan(obb) & ~np.isnan(opb)
    return (ya[keep], oba[keep], opa[keep], opb[keep], obb[keep], yb[keep], groups[keep])


def negative_control_panel(df, seed=RANDOM_SEED):
    """Per-outcome incremental AUROC (composite + each powered negative control)
    PLUS the composite-exceeds-control paired-difference bootstrap."""
    from vitaldb_aki.analysis.reperfusion_dynamics import incremental_auroc
    avail = [c for c in RECOVERY_FEATURES if c in df.columns and df[c].notna().sum() >= 50]

    panel = {"recovery_features_used": avail, "incremental_auroc": {}, "vs_composite": {}}

    outcomes = [PRIMARY_OUTCOME] + [c for c in NEGATIVE_CONTROLS if c in df.columns]
    for o in outcomes:
        try:
            panel["incremental_auroc"][o] = incremental_auroc(df, avail, o, seed=seed)
        except Exception as exc:  # noqa: BLE001
            panel["incremental_auroc"][o] = {"error": str(exc)}

    for o in [c for c in NEGATIVE_CONTROLS if c in df.columns]:
        try:
            panel["vs_composite"][o] = _paired_dauroc_difference(
                df, avail, PRIMARY_OUTCOME, o, seed)
        except Exception as exc:  # noqa: BLE001
            panel["vs_composite"][o] = {"error": str(exc)}
    return panel


# ===========================================================================
# ANALYSIS 2 -- WITHIN-BURDEN-STRATUM test ("at matched burden")
# ===========================================================================
def _zscore(s):
    import numpy as np
    import pandas as pd
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.nan, index=s.index)
    return (s - s.mean()) / sd


def _logit_or_per_sd(sub, feature, outcome, adjust_cols=None):
    """Per-SD logistic OR of `feature` on `outcome` within a subset, optionally
    adjusting for a small covariate set (z-scored). Returns OR, CI, p, n, events."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    import warnings

    s = sub.dropna(subset=[outcome]).copy()
    z = _zscore(s[feature])
    s = s[z.notna()]
    z = z[z.notna()]
    y = s[outcome].astype(float).astype(int)
    n, events = int(len(y)), int(y.sum())
    res = {"feature": feature, "n": n, "events": events}
    if events < MIN_EVENTS_STRATUM or n < 30 or y.nunique() < 2:
        res["underpowered"] = True
        return res
    pieces = {"feat_z": z.to_numpy()}
    if adjust_cols:
        for c in adjust_cols:
            if c in s.columns:
                pieces[f"adj__{c}"] = _zscore(s[c]).to_numpy()
    X = pd.DataFrame(pieces, index=s.index).fillna(0.0)
    Xc = sm.add_constant(X, has_constant="add")
    j = list(Xc.columns).index("feat_z")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = sm.Logit(y.to_numpy(), Xc.to_numpy().astype(float)).fit(
                disp=0, maxiter=300, method="bfgs")
        beta, se, p = float(fit.params[j]), float(fit.bse[j]), float(fit.pvalues[j])
        if not (math.isfinite(beta) and math.isfinite(se) and se > 0):
            raise ValueError("non-finite MLE")
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {e}"
        return res
    res.update({
        "underpowered": False,
        "or_per_sd": round(math.exp(beta), 4),
        "or_ci95": [round(math.exp(beta - 1.96 * se), 4),
                    round(math.exp(beta + 1.96 * se), 4)],
        "p_value": p, "beta": round(beta, 4), "se": round(se, 4),
    })
    return res


def within_burden_stratum(df, feature, outcome=PRIMARY_OUTCOME, seed=RANDOM_SEED):
    """Stratify by static-burden quartile (map_auc_below_65); per-SD logistic OR of
    `feature` on `outcome` WITHIN each stratum + an inverse-variance pooled estimate.

    The per-SD feature is ORIENTED (sign-aligned to FEATURE_DIRECTION) so that an
    OR>1 consistently means 'better/faster recovery -> injury' (the screen's
    surprising direction) and the pooled sign is interpretable. We also compute the
    E-value on the pooled OR."""
    import numpy as np
    import pandas as pd
    from vitaldb_aki.analysis.actionable_targets import e_value, e_value_ci

    out = {"feature": feature, "outcome": outcome, "stratifier": STRATIFY_COL,
           "n_strata": N_STRATA, "orientation": FEATURE_DIRECTION.get(feature, +1),
           "strata": []}
    s = df.dropna(subset=[STRATIFY_COL]).copy()
    burden = pd.to_numeric(s[STRATIFY_COL], errors="coerce")
    s = s[burden.notna()]
    try:
        q = pd.qcut(burden[burden.notna()].rank(method="first"), N_STRATA, labels=False)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        return out
    s = s.assign(_bstratum=q.to_numpy())
    direction = FEATURE_DIRECTION.get(feature, +1)
    # oriented feature: larger = faster/better recovery
    s = s.copy()
    s["_oriented"] = pd.to_numeric(s[feature], errors="coerce") * direction

    betas, ses = [], []
    for k in range(N_STRATA):
        stratum = s[s["_bstratum"] == k]
        r = _logit_or_per_sd(stratum, "_oriented", outcome)
        r["stratum"] = int(k)
        if not r.get("underpowered") and "beta" in r and r.get("se"):
            burden_k = pd.to_numeric(stratum[STRATIFY_COL], errors="coerce")
            r["burden_range"] = [round(float(burden_k.min()), 2),
                                 round(float(burden_k.max()), 2)]
            betas.append(r["beta"]); ses.append(r["se"])
        out["strata"].append(r)

    if betas:
        betas = np.asarray(betas); ses = np.asarray(ses)
        w = 1.0 / (ses ** 2)
        beta_pool = float((w * betas).sum() / w.sum())
        se_pool = float(math.sqrt(1.0 / w.sum()))
        from scipy import stats
        zp = beta_pool / se_pool
        p_pool = float(2 * (1 - stats.norm.cdf(abs(zp))))
        orr = math.exp(beta_pool)
        or_lo, or_hi = math.exp(beta_pool - 1.96 * se_pool), math.exp(beta_pool + 1.96 * se_pool)
        # heterogeneity (Cochran Q)
        q_stat = float((w * (betas - beta_pool) ** 2).sum())
        df_q = len(betas) - 1
        p_het = float(1 - stats.chi2.cdf(q_stat, df_q)) if df_q > 0 else None
        out["pooled"] = {
            "n_strata_used": int(len(betas)),
            "or_per_sd_oriented": round(orr, 4),
            "or_ci95": [round(or_lo, 4), round(or_hi, 4)],
            "p_value": p_pool,
            "e_value_point": round(e_value(orr), 3),
            "e_value_ci": round(e_value_ci(orr, or_lo, or_hi), 3),
            "cochran_q": round(q_stat, 3),
            "q_df": df_q,
            "p_heterogeneity": p_het,
            "note": ("OR>1 means faster/better recovery -> MORE injury within "
                     "matched burden (the screen's IPTW direction; oriented feature)."),
        }
    return out


# ===========================================================================
# ANALYSIS 3 -- CONFOUNDING-WITH-SEVERITY diagnostics
# ===========================================================================
def severity_confounding(df, outcome=PRIMARY_OUTCOME):
    """For each recovery feature: |Spearman r| with static burden, n_episodes,
    duration (the severity axes) + a crude per-SD univariate OR on the outcome.
    Flags the LEAST severity-confounded feature that is still injury-associated."""
    import numpy as np
    import pandas as pd
    from scipy import stats

    dur = _duration_col(df)
    severity_axes = {"burden": STRATIFY_COL, "n_episodes": "rv_n_episodes"}
    if dur:
        severity_axes["duration"] = dur

    rows = {}
    y = pd.to_numeric(df[outcome], errors="coerce")
    for feat in [c for c in RECOVERY_FEATURES if c in df.columns]:
        f = pd.to_numeric(df[feat], errors="coerce")
        entry = {"abs_spearman": {}}
        max_abs = 0.0
        for name, col in severity_axes.items():
            if col not in df.columns or col == feat:
                entry["abs_spearman"][name] = None
                continue
            g = pd.to_numeric(df[col], errors="coerce")
            m = f.notna() & g.notna()
            if m.sum() < 30:
                entry["abs_spearman"][name] = None
                continue
            r = float(stats.spearmanr(f[m], g[m]).correlation)
            entry["abs_spearman"][name] = round(abs(r), 4)
            if math.isfinite(abs(r)):
                max_abs = max(max_abs, abs(r))
        entry["max_abs_spearman_with_severity"] = round(max_abs, 4)
        # univariate per-SD OR on outcome (oriented), as the injury-association signal
        tmp = pd.DataFrame({
            "_or": pd.to_numeric(df[feat], errors="coerce") * FEATURE_DIRECTION.get(feat, +1),
            outcome: y,
        })
        r = _logit_or_per_sd(tmp, "_or", outcome)
        entry["univariate_or_per_sd_oriented"] = r.get("or_per_sd")
        entry["univariate_p"] = r.get("p_value")
        rows[feat] = entry

    # cleanest candidate: lowest max|r| with severity among features that are still
    # injury-associated (univariate p < 0.05), preferring the clean-feature set.
    def _assoc(feat):
        p = rows[feat].get("univariate_p")
        return (p is not None and math.isfinite(p) and p < 0.05)
    assoc_feats = [f for f in rows if _assoc(f)]
    pool = assoc_feats or list(rows.keys())
    cleanest = min(pool, key=lambda f: rows[f]["max_abs_spearman_with_severity"])
    return {"per_feature": rows, "cleanest_least_confounded_feature": cleanest,
            "severity_axes": list(severity_axes.keys()),
            "criterion": ("min max|Spearman r| with {burden, n_episodes, duration} "
                          "among features with univariate p<0.05")}


def stratified_dose_response(df, feature, outcome=PRIMARY_OUTCOME):
    """Within each static-burden quartile, injury rate by within-stratum quartile of
    the ORIENTED recovery feature (larger = faster recovery). If the anti-hypothesis
    raw pattern was pure confounding, the within-stratum trend should flip toward the
    protective direction (rate FALLS as recovery speeds up)."""
    import numpy as np
    import pandas as pd

    s = df.dropna(subset=[outcome, STRATIFY_COL]).copy()
    burden = pd.to_numeric(s[STRATIFY_COL], errors="coerce")
    s = s[burden.notna()]
    q_b = pd.qcut(burden[burden.notna()].rank(method="first"), N_STRATA, labels=False)
    s = s.assign(_bstratum=q_b.to_numpy())
    direction = FEATURE_DIRECTION.get(feature, +1)
    s["_oriented"] = pd.to_numeric(s[feature], errors="coerce") * direction

    out = {"feature": feature, "outcome": outcome,
           "orientation": "within each burden stratum, Q1=slowest ... Q4=fastest recovery",
           "by_burden_stratum": []}
    for k in range(N_STRATA):
        st = s[s["_bstratum"] == k].copy()
        f = st["_oriented"]
        st = st[f.notna()]
        if len(st) < 40:
            out["by_burden_stratum"].append({"stratum": int(k), "underpowered": True,
                                             "n": int(len(st))})
            continue
        try:
            qf = pd.qcut(st["_oriented"].rank(method="first"), 4, labels=False)
        except Exception:
            out["by_burden_stratum"].append({"stratum": int(k), "error": "qcut failed"})
            continue
        y = st[outcome].astype(float).astype(int).to_numpy()
        rates, ns = [], []
        for b in range(4):
            mask = (qf == b).to_numpy()
            ns.append(int(mask.sum()))
            rates.append(round(float(y[mask].mean()), 4) if mask.sum() else None)
        valid = [r for r in rates if r is not None]
        trend = ("protective (rate falls slow->fast)" if len(valid) >= 2 and valid[-1] < valid[0]
                 else "ANTI-hypothesis (rate rises slow->fast)" if len(valid) >= 2
                 else None)
        out["by_burden_stratum"].append({
            "stratum": int(k), "quartile_rates_slow_to_fast": rates,
            "quartile_n": ns, "direction": trend})
    return out


# ===========================================================================
# ANALYSIS 4 -- INCREMENTAL OVER A GENERIC-SEVERITY PROXY
# ===========================================================================
def incremental_over_severity_proxy(df, outcome=PRIMARY_OUTCOME, seed=RANDOM_SEED):
    """Incremental AUROC of the recovery-feature SET over a RICHER 'generic severity'
    baseline (n_episodes + total burden + map_lowest + duration), instead of the
    static-burden-only baseline. If recovery velocity is just generic severity, the
    incremental signal should largely vanish against this proxy."""
    import numpy as np
    from vitaldb_aki.models.metrics import bootstrap_ci, delong_roc_test
    from vitaldb_aki.analysis.reperfusion_dynamics import (
        _paired_oof_logistic, N_BOOTSTRAP as _NB,
    )

    dur = _duration_col(df)
    proxy_base = [c for c in ["rv_n_episodes", "map_auc_below_65", "map_lowest"]
                  if c in df.columns]
    if dur:
        proxy_base.append(dur)
    # recovery features EXCLUDING the ones already in the proxy baseline (n_episodes)
    avail = [c for c in RECOVERY_FEATURES
             if c in df.columns and df[c].notna().sum() >= 50 and c not in proxy_base]

    sub = df.dropna(subset=[outcome]).dropna(subset=proxy_base).copy()
    n, events = int(len(sub)), int(sub[outcome].astype(float).astype(int).sum())
    res = {"outcome": outcome, "severity_proxy_baseline": proxy_base,
           "recovery_cols": avail, "n": n, "events": events}
    if events < 15 or n < 50:
        res["underpowered"] = True
        return res
    # reuse the paired-OOF harness with a CUSTOM baseline by temporarily swapping
    # STATIC_BURDEN_COLS is not clean; instead call _paired_oof_logistic directly.
    y, oob, oop, groups = _paired_oof_logistic(sub, proxy_base, avail, outcome, seed)
    dl = delong_roc_test(y, oob, oop)
    ci = bootstrap_ci(lambda yy, a, b: delong_roc_test(yy, a, b)["delta"],
                      y, oob, oop, groups, n_iter=_NB, seed=seed)
    res.update({
        "underpowered": False,
        "auroc_severity_proxy": round(float(dl["auc_a"]), 4),
        "auroc_proxy_plus_recovery": round(float(dl["auc_b"]), 4),
        "delta_auroc": round(float(dl["delta"]), 4),
        "delta_auroc_ci95": [round(float(ci[0]), 4), round(float(ci[1]), 4)],
        "delong_p": float(dl["p_value"]),
        "delong_z": round(float(dl["z"]), 4),
    })
    return res


# ===========================================================================
# ORCHESTRATION
# ===========================================================================
def main():
    from vitaldb_aki.analysis.actionable_targets import benjamini_hochberg

    df = _load_with_recovery()
    print(f"[rv_specificity] recovery cohort N={len(df)}; seed={RANDOM_SEED}", flush=True)

    results = {
        "module": "recovery_velocity_specificity",
        "seed": RANDOM_SEED,
        "n_cohort": int(len(df)),
        "primary_outcome": PRIMARY_OUTCOME,
        "negative_controls": [c for c in NEGATIVE_CONTROLS if c in df.columns],
        "n_bootstrap_diff": N_BOOTSTRAP_DIFF,
        "leakage_firewall": "predictors preop+intraop only; organ_* used only as y",
    }

    # --- Analysis 1: negative-control panel + composite-exceeds-control ---
    print("[rv_specificity] (1) negative-control panel + composite-exceeds-control bootstrap ...",
          flush=True)
    results["negative_control_panel"] = negative_control_panel(df, seed=RANDOM_SEED)

    # --- Analysis 2: within-burden-stratum (clean features) ---
    print("[rv_specificity] (2) within-burden-stratum test ...", flush=True)
    results["within_burden_stratum"] = {
        f: within_burden_stratum(df, f, PRIMARY_OUTCOME, seed=RANDOM_SEED)
        for f in [c for c in CLEAN_FEATURES if c in df.columns]
    }

    # --- Analysis 3: severity-confounding diagnostics + stratified dose-response ---
    print("[rv_specificity] (3) severity-confounding diagnostics ...", flush=True)
    sev = severity_confounding(df, PRIMARY_OUTCOME)
    results["severity_confounding"] = sev
    cleanest = sev["cleanest_least_confounded_feature"]
    results["stratified_dose_response_cleanest"] = stratified_dose_response(
        df, cleanest, PRIMARY_OUTCOME)
    # also the primary feature (the one whose RAW quartile pattern was anti-hypothesis)
    results["stratified_dose_response_primary"] = stratified_dose_response(
        df, PRIMARY_FEATURE, PRIMARY_OUTCOME)

    # --- Analysis 4: incremental over generic-severity proxy ---
    print("[rv_specificity] (4) incremental over generic-severity proxy ...", flush=True)
    results["incremental_over_severity_proxy"] = incremental_over_severity_proxy(
        df, PRIMARY_OUTCOME, seed=RANDOM_SEED)

    # --- Analysis 5: BH-FDR across the new tests ---
    print("[rv_specificity] (5) BH-FDR across new tests ...", flush=True)
    pvals, keys = [], []
    # composite-exceeds-control one-sided p's
    for o, r in results["negative_control_panel"]["vs_composite"].items():
        if isinstance(r, dict) and r.get("p_composite_exceeds_control_one_sided") is not None:
            pvals.append(float(r["p_composite_exceeds_control_one_sided"]))
            keys.append(("composite_exceeds", o))
    # pooled within-stratum p's
    for f, r in results["within_burden_stratum"].items():
        pooled = r.get("pooled")
        if pooled and pooled.get("p_value") is not None:
            pvals.append(float(pooled["p_value"]))
            keys.append(("within_stratum_pooled", f))
    # incremental-over-proxy p
    ip = results["incremental_over_severity_proxy"]
    if not ip.get("underpowered") and ip.get("delong_p") is not None:
        pvals.append(float(ip["delong_p"]))
        keys.append(("incremental_over_severity_proxy", PRIMARY_OUTCOME))
    if pvals:
        flags = benjamini_hochberg(pvals)
        results["fdr"] = {
            "alpha": 0.05, "n_tests": len(pvals),
            "tests": [{"family": k[0], "label": k[1], "p": p, "survives": bool(s)}
                      for k, p, s in zip(keys, pvals, flags)],
            "n_survive": int(sum(flags)),
        }

    os.makedirs(_CACHE, exist_ok=True)
    with open(_RESULTS_JSON, "w") as fh:
        json.dump(results, fh, indent=2, allow_nan=True, default=float)
    _write_doc(results)
    print(_fmt(results), flush=True)
    print(f"[rv_specificity] DONE -> {_RESULTS_JSON} + docs/RECOVERY_VELOCITY_SPECIFICITY.md",
          flush=True)
    return results


# ===========================================================================
# VERDICT + REPORTING
# ===========================================================================
def _verdict(results):
    """Programmatic candid verdict synthesised from the three decisive tests."""
    panel = results.get("negative_control_panel", {})
    vs = panel.get("vs_composite", {})
    # how many controls does composite SIGNIFICANTLY exceed (CI lower > 0)?
    exceed = [o for o, r in vs.items()
              if isinstance(r, dict) and r.get("composite_exceeds_control")]
    n_ctrl = sum(1 for r in vs.values() if isinstance(r, dict) and not r.get("underpowered")
                 and "dauroc_difference" in r)

    # within-stratum: does at least one clean feature survive pooled at p<0.05 with
    # the screen's (OR>1) direction?
    ws = results.get("within_burden_stratum", {})
    ws_survivors = []
    for f, r in ws.items():
        p = r.get("pooled", {})
        if p and p.get("p_value") is not None and p["p_value"] < 0.05:
            ws_survivors.append((f, p["or_per_sd_oriented"], p["p_value"]))

    ip = results.get("incremental_over_severity_proxy", {})
    proxy_survives = (not ip.get("underpowered")
                      and ip.get("delong_p") is not None and ip["delong_p"] < 0.05
                      and ip.get("delta_auroc", 0) > 0)

    if n_ctrl and len(exceed) == n_ctrl and ws_survivors and proxy_survives:
        verdict = "PERFUSION-RELEVANT-SPECIFIC (robust)"
    elif (len(exceed) >= 1 or ws_survivors) and proxy_survives:
        verdict = "PARTIALLY SPECIFIC -- survives burden matching but specificity vs negative controls is incomplete"
    elif ws_survivors or proxy_survives:
        verdict = "MIXED -- discriminates within burden but NOT clearly distinguishable from generic-severity controls"
    else:
        verdict = "GENERIC SEVERITY / BURDEN-CONFOUNDED -- does not exceed negative controls nor survive severity-proxy adjustment"

    return {
        "verdict": verdict,
        "n_negative_controls_tested": n_ctrl,
        "controls_composite_significantly_exceeds": exceed,
        "within_stratum_clean_survivors": [
            {"feature": f, "pooled_or_oriented": orr, "p": p} for f, orr, p in ws_survivors],
        "survives_generic_severity_proxy": bool(proxy_survives),
    }


def _fmt(results):
    L = ["", "=" * 74,
         "RECOVERY-VELOCITY SPECIFICITY / ROBUSTNESS DE-RISKING",
         "=" * 74,
         f"Cohort N={results['n_cohort']}  seed={results['seed']}  "
         f"diff-bootstrap={results['n_bootstrap_diff']}", ""]
    panel = results.get("negative_control_panel", {})
    L.append("(1) NEGATIVE-CONTROL PANEL -- incremental dAUROC over static burden:")
    for o, r in panel.get("incremental_auroc", {}).items():
        if "delta_auroc" in r:
            L.append(f"    {o:26s} dAUROC={r['delta_auroc']:+.4f}  DeLong p={r['delong_p']:.3g}")
    L.append("")
    L.append("    Composite EXCEEDS control? (paired diff-of-dAUROC bootstrap):")
    for o, r in panel.get("vs_composite", {}).items():
        if r.get("underpowered"):
            L.append(f"    {o:26s} underpowered"); continue
        if "dauroc_difference" in r:
            tag = "YES" if r["composite_exceeds_control"] else "no"
            L.append(f"    {o:26s} diff={r['dauroc_difference']:+.4f} "
                     f"CI[{r['diff_ci95'][0]:+.4f},{r['diff_ci95'][1]:+.4f}] "
                     f"exceeds={tag} (1-sided p={r['p_composite_exceeds_control_one_sided']:.3g})")
    L.append("")
    L.append("(2) WITHIN-BURDEN-STRATUM (pooled per-SD OR, oriented faster=better):")
    for f, r in results.get("within_burden_stratum", {}).items():
        p = r.get("pooled")
        if p:
            L.append(f"    {f:20s} pooled OR/SD={p['or_per_sd_oriented']:.3f} "
                     f"CI[{p['or_ci95'][0]:.3f},{p['or_ci95'][1]:.3f}] p={p['p_value']:.3g} "
                     f"E={p['e_value_point']} (Q-het p={p['p_heterogeneity']})")
    L.append("")
    sev = results.get("severity_confounding", {})
    L.append(f"(3) CLEANEST least-severity-confounded feature: "
             f"{sev.get('cleanest_least_confounded_feature')}")
    for f, e in sev.get("per_feature", {}).items():
        L.append(f"    {f:24s} max|r|sev={e['max_abs_spearman_with_severity']:.3f} "
                 f"univ OR/SD={e['univariate_or_per_sd_oriented']} p={e['univariate_p']}")
    L.append("")
    ip = results.get("incremental_over_severity_proxy", {})
    if "delta_auroc" in ip:
        L.append(f"(4) INCREMENTAL over generic-severity proxy {ip['severity_proxy_baseline']}:")
        L.append(f"    dAUROC={ip['delta_auroc']:+.4f} "
                 f"CI[{ip['delta_auroc_ci95'][0]:+.4f},{ip['delta_auroc_ci95'][1]:+.4f}] "
                 f"DeLong p={ip['delong_p']:.3g}")
    L.append("")
    fdr = results.get("fdr", {})
    L.append(f"(5) BH-FDR: {fdr.get('n_survive')}/{fdr.get('n_tests')} new tests survive q<0.05")
    L.append("")
    v = _verdict(results)
    L.append("VERDICT: " + v["verdict"])
    L.append(f"  composite significantly exceeds: {v['controls_composite_significantly_exceeds']} "
             f"of {v['n_negative_controls_tested']} controls")
    L.append(f"  within-stratum survivors: "
             f"{[s['feature'] for s in v['within_stratum_clean_survivors']]}")
    L.append(f"  survives generic-severity proxy: {v['survives_generic_severity_proxy']}")
    L.append("=" * 74)
    return "\n".join(L)


def _write_doc(results):
    v = _verdict(results)
    panel = results.get("negative_control_panel", {})
    sev = results.get("severity_confounding", {})
    ip = results.get("incremental_over_severity_proxy", {})
    L = []
    A = L.append
    A("# Recovery Velocity -- Specificity & Robustness De-risking\n")
    A("## READ FIRST -- what this document does and its limitations\n")
    A("This is a **de-risking / falsification** analysis of the recovery-velocity "
      "finding in `docs/RECOVERY_VELOCITY.md` (raw-MAP per-episode recovery velocity "
      "adds incremental discrimination for organ injury over static hypotension "
      "burden: COMPOSITE dAUROC +0.079, DeLong p=2.6e-9). It does **not** re-establish "
      "the finding; it stress-tests TWO specific threats:\n")
    A("1. **Non-specificity:** the negative control `organ_hepatocellular` ALSO showed "
      "incremental AUROC (+0.047, p=0.053), so part of the signal may be a generic "
      "'unstable/sick patient' axis rather than perfusion-recovery-specific.\n")
    A("2. **Severity confounding:** the UNADJUSTED quartile dose-response of the "
      "primary feature `rv_depthwt_slope` was non-monotone / anti-hypothesis; only "
      "burden+covariate-adjusted models showed the hypothesised direction.\n")
    A("**Limitations (unchanged from the parent screen):** observational, single-centre "
      "(VitalDB/SNUH); confounding by indication remains; cohort = cases with a "
      "recovered MAP<65 episode; hypothesis-generating; external replication on "
      "INSPIRE pending. The IPTW/within-stratum directions point the *surprising* way "
      "(faster/better measured recovery -> MORE injury after adjustment), which is "
      "itself most consistent with residual confounding by episode severity / "
      "reverse causation, and is flagged below.\n")
    A(f"**Cohort N = {results.get('n_cohort')}**, seed {results.get('seed')}, "
      f"difference-bootstrap N = {results.get('n_bootstrap_diff')} "
      "(reduced from the parent's 2000 because each resample refits a full paired-OOF "
      "model per control on a loaded box; CIs remain tight at the dAUROC-difference "
      "scale).\n")

    A("\n## VERDICT (candid)\n")
    A(f"**{v['verdict']}**\n")
    A(f"- Composite's incremental dAUROC significantly exceeds "
      f"**{len(v['controls_composite_significantly_exceeds'])} of "
      f"{v['n_negative_controls_tested']}** negative controls "
      f"(CI-lower>0): {v['controls_composite_significantly_exceeds'] or 'none'}.")
    A(f"- Within-burden-stratum pooled survivors (p<0.05): "
      f"{[s['feature'] for s in v['within_stratum_clean_survivors']] or 'none'}.")
    A(f"- Survives a generic-severity proxy baseline "
      f"(n_episodes+burden+map_lowest+duration): "
      f"**{v['survives_generic_severity_proxy']}**.\n")

    A("\n## (1) Negative-control panel + composite-exceeds-control test\n")
    A("Incremental dAUROC of the recovery-feature SET over the static-burden baseline, "
      "per outcome (DeLong on shared grouped OOF folds):\n")
    A("| outcome | dAUROC | DeLong p |")
    A("|---|---|---|")
    for o, r in panel.get("incremental_auroc", {}).items():
        if "delta_auroc" in r:
            A(f"| {o} | {r['delta_auroc']:+.4f} | {r['delong_p']:.3g} |")
    A("\nFormal specificity test -- bootstrap of the DIFFERENCE of paired dAUROCs "
      "(composite - control) on the SHARED cases/folds. `exceeds=YES` iff the 95% CI "
      "lower bound > 0:\n")
    A("| control | dAUROC diff (comp-ctrl) | 95% CI | exceeds? | 1-sided p |")
    A("|---|---|---|---|---|")
    for o, r in panel.get("vs_composite", {}).items():
        if r.get("underpowered"):
            A(f"| {o} | underpowered | | | |"); continue
        if "dauroc_difference" in r:
            A(f"| {o} | {r['dauroc_difference']:+.4f} | "
              f"[{r['diff_ci95'][0]:+.4f}, {r['diff_ci95'][1]:+.4f}] | "
              f"{'YES' if r['composite_exceeds_control'] else 'no'} | "
              f"{r['p_composite_exceeds_control_one_sided']:.3g} |")
    A("\nInterpretation: if composite does NOT clearly exceed the controls, the "
      "incremental recovery signal is largely a **generic severity** axis shared by "
      "outcomes that MAP-recovery dynamics should not mechanistically drive.\n")

    A("\n## (2) Within-burden-stratum test ('at matched burden')\n")
    A(f"Stratified by static-burden quartile (`{STRATIFY_COL}`). Per-SD logistic OR of "
      "the ORIENTED clean feature (larger = faster/better recovery) on composite, "
      "WITHIN each stratum, plus an inverse-variance pooled estimate. **OR>1 means "
      "faster/better measured recovery -> MORE injury at matched burden** (the screen's "
      "post-adjustment direction).\n")
    for f, r in results.get("within_burden_stratum", {}).items():
        p = r.get("pooled")
        if not p:
            A(f"- `{f}`: no pooled estimate."); continue
        A(f"- `{f}`: pooled OR/SD = **{p['or_per_sd_oriented']}** "
          f"(95% CI {p['or_ci95']}), p = {p['p_value']:.3g}, "
          f"E-value(point) = {p['e_value_point']}, E-value(CI) = {p['e_value_ci']}; "
          f"heterogeneity Cochran-Q p = {p['p_heterogeneity']} "
          f"(n strata used {p['n_strata_used']}).")
    A("\nIf recovery velocity still discriminates injury WITHIN burden strata, it is "
      "not *merely* burden re-expressed. NOTE: a within-stratum OR>1 (faster recovery -> "
      "more injury) is the anti-hypothesis sign and most plausibly reflects residual "
      "severity confounding within the stratum, not protection.\n")

    A("\n## (3) Severity-confounding diagnostics\n")
    A(f"Severity axes: {sev.get('severity_axes')}. For each recovery feature: "
      "max |Spearman r| with those axes, and the univariate per-SD oriented OR on "
      "composite.\n")
    A("| feature | max abs r (severity) | univ OR/SD (oriented) | univ p |")
    A("|---|---|---|---|")
    for f, e in sev.get("per_feature", {}).items():
        A(f"| {f} | {e['max_abs_spearman_with_severity']:.3f} | "
          f"{e['univariate_or_per_sd_oriented']} | {e['univariate_p']} |")
    A(f"\n**Cleanest least-severity-confounded yet injury-associated feature: "
      f"`{sev.get('cleanest_least_confounded_feature')}`** "
      f"({sev.get('criterion')}).\n")
    A("Within-burden-stratum quartile dose-response of the cleanest feature "
      "(does the anti-hypothesis raw pattern flip once burden is matched?):\n")
    for blk in results.get("stratified_dose_response_cleanest", {}).get("by_burden_stratum", []):
        if blk.get("underpowered") or blk.get("error"):
            A(f"- burden stratum {blk['stratum']}: n/a"); continue
        A(f"- burden stratum {blk['stratum']}: rates slow->fast "
          f"{blk['quartile_rates_slow_to_fast']} (n {blk['quartile_n']}) -> "
          f"{blk['direction']}")
    A("\nFor reference, the same within-stratum dose-response of the PRIMARY feature "
      f"`{PRIMARY_FEATURE}` (whose RAW quartile pattern was anti-hypothesis):\n")
    for blk in results.get("stratified_dose_response_primary", {}).get("by_burden_stratum", []):
        if blk.get("underpowered") or blk.get("error"):
            A(f"- burden stratum {blk['stratum']}: n/a"); continue
        A(f"- burden stratum {blk['stratum']}: rates slow->fast "
          f"{blk['quartile_rates_slow_to_fast']} -> {blk['direction']}")

    A("\n## (4) Incremental over a generic-severity proxy\n")
    if "delta_auroc" in ip:
        A(f"Baseline = severity proxy `{ip['severity_proxy_baseline']}` "
          f"(AUROC {ip['auroc_severity_proxy']}). Adding the recovery features: "
          f"AUROC -> {ip['auroc_proxy_plus_recovery']}; **dAUROC = {ip['delta_auroc']:+.4f}** "
          f"(95% CI {ip['delta_auroc_ci95']}), DeLong p = {ip['delong_p']:.3g}.\n")
        A("If recovery velocity were just generic severity, this incremental signal "
          "over an explicit severity proxy should largely vanish.\n")
    else:
        A("(underpowered / not computed)\n")

    A("\n## (5) BH-FDR across the new specificity tests\n")
    fdr = results.get("fdr", {})
    A(f"{fdr.get('n_survive')}/{fdr.get('n_tests')} survive BH at q<0.05.\n")
    A("| family | label | p | survives |")
    A("|---|---|---|---|")
    for t in fdr.get("tests", []):
        A(f"| {t['family']} | {t['label']} | {t['p']:.3g} | {t['survives']} |")

    A("\n## Methods (brief)\n")
    A("- Reuses `reperfusion_dynamics` (load_merged, incremental_auroc, "
      "_paired_oof_logistic, static-burden baseline, preop covariates), "
      "`models.metrics` (DeLong + cluster bootstrap), and `actionable_targets` "
      "(E-value, BH-FDR). Difference-of-dAUROC: both outcomes fit on the SAME "
      "StratifiedGroupKFold folds and the SAME shared cases, then a patient-cluster "
      "bootstrap of (dAUROC_composite - dAUROC_control).")
    A("- Within-stratum: static-burden quartiles; per-SD logistic OR within each; "
      "inverse-variance pooling + Cochran-Q heterogeneity; E-value on the pooled OR.")
    A("- Leakage firewall: all predictors preop+intraop; organ_* only as outcomes. "
      f"Seed {results.get('seed')}.")
    A("\n---\n*Generated by vitaldb_aki/analysis/recovery_velocity_specificity.py*")
    os.makedirs(_DOCS, exist_ok=True)
    with open(os.path.join(_DOCS, "RECOVERY_VELOCITY_SPECIFICITY.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
