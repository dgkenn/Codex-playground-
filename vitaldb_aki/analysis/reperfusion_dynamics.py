"""reperfusion_dynamics.py -- Reperfusion-dynamics biomarker (recovery velocity).

SCIENTIFIC THESIS
-----------------
"It's not the pressure target -- it's how perfusion is RESTORED at that pressure."

Static intraoperative-hypotension burden (area/time under MAP 65 mmHg) is
confounded by surgical magnitude: bigger, longer, bloodier operations accrue more
burden AND more organ injury. This module asks whether the *dynamics* of recovery
-- how FAST mean arterial pressure (MAP) climbs back out of its hypotensive nadir,
i.e. the rate at which a perfusion debt is repaid -- carries information about
organ injury BEYOND the static burden. The hypothesis: a slow climb back from a
nadir is worse than a fast one at EQUAL total burden.

WHAT IS BUILT
-------------
Interpretable per-case recovery-dynamics features derived from per-case SUMMARY
statistics that are ALREADY in cache/feature_matrix.csv (no track download / no
re-extraction):

  recovery_velocity     -- late-vs-early MAP recovery scaled by nadir depth:
                           map_early_vs_late_mean_delta / (nadir_depth + eps).
                           Positive-and-large = strong recovery for a given drop.
  debt_repayment_rate   -- total hypotensive burden CONCENTRATION:
                           map_auc_below_65 / (map_longest_hypotension_run_min+eps).
                           High = the debt is repaid in a concentrated window
                           (a deep-but-brief dip); low = the debt is smeared out
                           over a long, grinding, slowly-recovering run.
  late_residual_burden  -- map_auc65_late: un-recovered hypotension in the final
                           third of the case (failure to have recovered by case end).
  recovery_slope        -- map_slope_per_hr: signed MAP trend (mmHg/hr); positive
                           = MAP rising over the case.
  nadir_recovery_frac   -- 1 - map_nadir_time_frac: fraction of the case spent
                           AFTER the nadir (time available to recover; a late nadir
                           leaves little runway to climb back).
  recovery_lag          -- pfds_clin_recovery_lag (clinical PFDS recovery-lag
                           summary; minutes-scale). pfds_wf_recovery_lag is too
                           sparse (n~=21) and is excluded.

IMPORTANT (limitation, stated up front and in docs/REPERFUSION_DYNAMICS.md):
these features are derived from per-case SUMMARY statistics, NOT from the raw
per-beat MAP time series. A true per-beat recovery slope (regress MAP on time
over the post-nadir window) would be richer and is noted as FUTURE WORK; it needs
the raw MAP series, which this module deliberately does not touch.

TESTS
-----
1. PRIMARY -- incremental AUROC (cross-validated, paired OOF, DeLong) of the
   recovery-dynamics feature SET over a STATIC-BURDEN baseline
   (map_auc_below_65 + map_mean + map_lowest + map_min_below_65), for `composite`
   and `organ_renal`. DeLong delta-AUROC, DeLong p, cluster-bootstrap 95% CI.
2. Adjusted association -- logistic AND IPTW-weighted logistic of each recovery
   feature (per-SD) on the outcome, adjusting for static burden + preop covariates.
   OR + 95% CI + E-value (VanderWeele-Ding).
3. Negative control -- organ_hepatocellular: the incremental signal must be
   WEAKER/null there.
4. BH-FDR across feature x outcome adjusted tests.
5. Monotonic dose-response -- best recovery feature in quartiles -> AKI-rate trend
   (Cochran-Armitage trend test).

LEAKAGE FIREWALL: every feature is PREOP+INTRAOP only. The organ_* outcomes are y;
they are NEVER used as features.

Heavy deps (pandas/numpy/sklearn/scipy/statsmodels) are imported lazily inside
functions so the module imports under the stdlib-only test environment.

Run:  python3 -m vitaldb_aki.analysis.reperfusion_dynamics
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

# ---------------------------------------------------------------------------
# Constants (config-driven; seed mirrors config.yaml)
# ---------------------------------------------------------------------------
RANDOM_SEED = 20260626

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))      # .../Codex-playground-
_PKG_ROOT = os.path.dirname(_HERE)                        # .../vitaldb_aki
_CACHE = os.path.join(_PKG_ROOT, "cache")

_FEATURE_MATRIX = os.path.join(_CACHE, "feature_matrix.csv")
_COHORT = os.path.join(_CACHE, "cohort_composite.csv")
_RESULTS_JSON = os.path.join(_CACHE, "reperfusion_dynamics_results.json")

# Outcomes
PRIMARY_OUTCOMES = ["composite", "organ_renal"]
NEGATIVE_CONTROL = "organ_hepatocellular"
ALL_OUTCOMES = PRIMARY_OUTCOMES + [NEGATIVE_CONTROL]

# Static-burden baseline (the thing recovery must beat).
STATIC_BURDEN_COLS = [
    "map_auc_below_65",
    "map_mean",
    "map_lowest",
    "map_min_below_65",
]

# Preoperative + duration covariates for adjustment / propensity.
PREOP_COVARIATES = [
    "age",
    "sex_male",
    "asa",
    "preop_htn",
    "preop_dm",
    "baseline_cr",
    "surgery_duration_min",
    "anesthesia_duration_min",
    "intraop_ebl",
]
OPTYPE_COL = "optype"

# Cross-validation / bootstrap.
N_OUTER_FOLDS = 5
N_BOOTSTRAP = 2000
MIN_EVENTS = 15          # below this an outcome is reported but flagged underpowered

_EPS = 1e-6


# ===========================================================================
# PURE FEATURE CONSTRUCTION (numpy)
# ===========================================================================
def build_recovery_features(df):
    """Construct interpretable recovery-dynamics features from SUMMARY columns.

    Returns (df_with_features, feature_names). All inputs are preop/intraop
    physiology summaries; no outcome touches this function.
    """
    import numpy as np
    import pandas as pd

    out = df.copy()

    def col(name):
        if name in out.columns:
            return pd.to_numeric(out[name], errors="coerce")
        return pd.Series(np.nan, index=out.index)

    # Nadir depth below the 65 mmHg threshold (>=0). Deeper nadir -> larger debt.
    nadir_depth = (65.0 - col("map_lowest")).clip(lower=0.0)

    feats = {}

    # 1. recovery_velocity: late-vs-early recovery scaled by how deep we fell.
    #    map_early_vs_late_mean_delta > 0 means LATE mean MAP > EARLY mean MAP
    #    (net recovery over the case). Dividing by nadir depth makes it "recovery
    #    achieved per unit of perfusion debt incurred".
    feats["recovery_velocity"] = col("map_early_vs_late_mean_delta") / (nadir_depth + _EPS)

    # 2. debt_repayment_rate: burden CONCENTRATION. AUC<65 per minute of the
    #    longest hypotensive run. High = deep-but-brief (debt cleared fast);
    #    low = shallow-but-smeared (a long grinding low-perfusion plateau).
    feats["debt_repayment_rate"] = col("map_auc_below_65") / (
        col("map_longest_hypotension_run_min") + _EPS
    )

    # 3. late_residual_burden: un-recovered hypotension in the final epoch.
    feats["late_residual_burden"] = col("map_auc65_late")

    # 4. recovery_slope: signed MAP trend over the case (mmHg/hr).
    feats["recovery_slope"] = col("map_slope_per_hr")

    # 5. nadir_recovery_frac: runway after the nadir (1 - nadir time fraction).
    feats["nadir_recovery_frac"] = 1.0 - col("map_nadir_time_frac")

    # 6. recovery_lag: clinical PFDS recovery-lag summary (minutes-scale).
    #    pfds_wf_recovery_lag excluded (too sparse).
    feats["recovery_lag"] = col("pfds_clin_recovery_lag")

    for k, v in feats.items():
        # Guard against +/-inf from any residual zero-division.
        out[k] = v.replace([np.inf, -np.inf], np.nan)

    return out, list(feats.keys())


# Direction in which the feature is HYPOTHESISED to be PROTECTIVE (recovery is
# "good"). Used only to orient quartile dose-response / sign reporting.
# +1 means larger value = better recovery = lower expected injury.
RECOVERY_DIRECTION = {
    "recovery_velocity": +1,
    "debt_repayment_rate": +1,     # concentrated debt (brief dip) hypothesised better
    "late_residual_burden": -1,    # more residual late burden = worse
    "recovery_slope": +1,          # rising MAP = better
    "nadir_recovery_frac": +1,     # more runway after nadir = better
    "recovery_lag": -1,            # longer lag = worse
}


# ===========================================================================
# DATA LOADING
# ===========================================================================
def load_merged(feature_path=_FEATURE_MATRIX, cohort_path=_COHORT):
    """Load feature_matrix + cohort_composite, merged on caseid.

    Outcome merge = ONLY columns not already present (per repo convention), so we
    never clobber feature-matrix columns with cohort copies.
    """
    import pandas as pd

    fm = pd.read_csv(feature_path)
    co = pd.read_csv(cohort_path)

    # Merge only the columns we actually need that are NOT already in fm.
    need = ["caseid"] + [c for c in ALL_OUTCOMES if c in co.columns]
    if "subjectid" in co.columns and "subjectid" not in fm.columns:
        need.append("subjectid")
    new_cols = [c for c in need if (c == "caseid") or (c not in fm.columns)]
    merged = fm.merge(co[new_cols], on="caseid", how="inner")
    return merged


# ===========================================================================
# TEST 1 -- INCREMENTAL AUROC (paired OOF + DeLong)
# ===========================================================================
def _paired_oof_logistic(df_sub, base_cols, plus_cols, outcome, seed):
    """Cross-validated, paired out-of-fold probabilities for a baseline model and
    a baseline+recovery model on the SAME StratifiedGroupKFold splits (grouped by
    subjectid). Returns (y, oof_base, oof_plus, groups). Paired -> DeLong valid.

    Each fold fits a standardised, median-imputed logistic regression. Categorical
    optype is one-hot encoded inside the column set.
    """
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.linear_model import LogisticRegression

    y = df_sub[outcome].astype(float).astype(int).to_numpy()
    if "subjectid" in df_sub.columns:
        groups = df_sub["subjectid"].to_numpy()
    else:
        groups = df_sub["caseid"].to_numpy()

    def _build(cols):
        cat = [c for c in cols if c == OPTYPE_COL]
        num = [c for c in cols if c != OPTYPE_COL]
        transformers = [
            ("num", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), num),
        ]
        if cat:
            transformers.append((
                "cat",
                OneHotEncoder(handle_unknown="ignore"),
                cat,
            ))
        pre = ColumnTransformer(transformers)
        pipe = Pipeline([
            ("pre", pre),
            ("clf", LogisticRegression(max_iter=2000, solver="lbfgs",
                                       C=1.0, random_state=seed)),
        ])
        return df_sub[cols].copy(), pipe

    full_plus = base_cols + [c for c in plus_cols if c not in base_cols]
    X_base, pipe_base = _build(base_cols)
    X_plus, pipe_plus = _build(full_plus)

    n_splits = min(N_OUTER_FOLDS, int(y.sum()), int((1 - y).sum()))
    n_splits = max(n_splits, 2)
    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    oof_base = np.full(len(y), np.nan)
    oof_plus = np.full(len(y), np.nan)
    from sklearn.base import clone
    for tr, te in outer.split(X_base, y, groups):
        b = clone(pipe_base).fit(X_base.iloc[tr], y[tr])
        oof_base[te] = b.predict_proba(X_base.iloc[te])[:, 1]
        p = clone(pipe_plus).fit(X_plus.iloc[tr], y[tr])
        oof_plus[te] = p.predict_proba(X_plus.iloc[te])[:, 1]

    keep = ~np.isnan(oof_base) & ~np.isnan(oof_plus)
    return y[keep], oof_base[keep], oof_plus[keep], groups[keep]


def incremental_auroc(df, feature_names, outcome, seed=RANDOM_SEED):
    """Paired-OOF DeLong incremental AUROC of recovery features over static burden.

    Subset = cases with MAP available (all baseline + recovery cols computable)
    and a non-missing outcome.
    """
    import numpy as np
    from vitaldb_aki.models.metrics import bootstrap_ci, delong_roc_test

    base_cols = [c for c in STATIC_BURDEN_COLS if c in df.columns]
    plus_cols = [c for c in feature_names if c in df.columns]

    sub = df.dropna(subset=[outcome]).copy()
    # Require baseline columns present (recovery cols may have isolated NaNs ->
    # median-imputed inside CV).
    sub = sub.dropna(subset=base_cols)
    n = int(len(sub))
    events = int(sub[outcome].astype(float).astype(int).sum())
    res = {
        "outcome": outcome, "n": n, "events": events,
        "baseline_cols": base_cols, "recovery_cols": plus_cols,
    }
    if events < MIN_EVENTS or n < 50:
        res.update({"underpowered": True})
        return res

    y, oob, oop, groups = _paired_oof_logistic(sub, base_cols, plus_cols, outcome, seed)
    dl = delong_roc_test(y, oob, oop)
    ci = bootstrap_ci(
        lambda yy, a, b: delong_roc_test(yy, a, b)["delta"],
        y, oob, oop, groups, n_iter=N_BOOTSTRAP, seed=seed,
    )
    res.update({
        "underpowered": False,
        "auroc_static_burden": round(float(dl["auc_a"]), 4),
        "auroc_static_plus_recovery": round(float(dl["auc_b"]), 4),
        "delta_auroc": round(float(dl["delta"]), 4),
        "delta_auroc_ci95": [round(float(ci[0]), 4), round(float(ci[1]), 4)],
        "delong_p": float(dl["p_value"]),
        "delong_z": round(float(dl["z"]), 4),
        "p_method": "DeLong (paired correlated-ROC on shared grouped OOF folds)",
    })
    return res


# ===========================================================================
# TEST 2 -- ADJUSTED ASSOCIATION (logistic + IPTW), OR + E-value
# ===========================================================================
def _zscore(s):
    import numpy as np
    import pandas as pd
    s = pd.to_numeric(s, errors="coerce")
    mu = s.mean()
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.nan, index=s.index)
    return (s - mu) / sd


def _design_matrix(df, feature, outcome):
    """Build (X, y, used_cols) for an adjusted logistic model: per-SD recovery
    feature + static burden + preop covariates + one-hot optype. Median-impute,
    drop rows with missing outcome."""
    import numpy as np
    import pandas as pd

    sub = df.dropna(subset=[outcome]).copy()

    # All continuous predictors are z-scored so the design is well-conditioned
    # (avoids logistic overflow / non-convergence from raw-scale AUC columns).
    # The recovery_z OR (per-SD) is unaffected by scaling the OTHER columns.
    pieces = {}
    pieces["recovery_z"] = _zscore(sub[feature])
    for c in STATIC_BURDEN_COLS:
        if c in sub.columns:
            pieces[f"burden__{c}"] = _zscore(sub[c])
    for c in PREOP_COVARIATES:
        if c in sub.columns:
            pieces[f"cov__{c}"] = _zscore(sub[c])

    X = pd.DataFrame(pieces, index=sub.index)
    # one-hot optype
    if OPTYPE_COL in sub.columns:
        dummies = pd.get_dummies(sub[OPTYPE_COL].astype(str), prefix="optype",
                                 drop_first=True, dtype=float)
        X = pd.concat([X, dummies], axis=1)

    # median-impute numeric NaNs (keeps the recovery_z row even if a covariate
    # is missing); drop rows where the recovery feature itself is undefined.
    X = X[X["recovery_z"].notna()]
    y = sub.loc[X.index, outcome].astype(float).astype(int)
    X = X.fillna(X.median(numeric_only=True))
    # any column that is still all-NaN (no data) -> drop
    X = X.dropna(axis=1, how="all")
    return X, y


def adjusted_logistic(df, feature, outcome):
    """Unweighted adjusted logistic OR for a per-SD increase in the recovery
    feature. Returns OR, 95% CI, p, E-value, E-value(CI)."""
    import numpy as np
    import statsmodels.api as sm
    from vitaldb_aki.analysis.actionable_targets import e_value, e_value_ci

    X, y = _design_matrix(df, feature, outcome)
    n = int(len(y)); events = int(y.sum())
    out = {"feature": feature, "outcome": outcome, "n": n, "events": events}
    if events < MIN_EVENTS or n < 50:
        out["underpowered"] = True
        return out
    Xc = sm.add_constant(X, has_constant="add")
    cols = list(Xc.columns)
    j = cols.index("recovery_z")
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = sm.Logit(y.to_numpy(), Xc.to_numpy().astype(float)).fit(
                disp=0, maxiter=300, method="bfgs")
        beta = float(fit.params[j]); se = float(fit.bse[j]); p = float(fit.pvalues[j])
        if not (math.isfinite(beta) and math.isfinite(se) and se > 0):
            raise ValueError("non-finite MLE")
    except Exception:
        # Mild L2 ridge for separation / non-convergence (does not bias the
        # standardized recovery coefficient meaningfully at this alpha).
        out["regularized"] = True
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = sm.Logit(y.to_numpy(), Xc.to_numpy().astype(float)).fit_regularized(
                    alpha=1.0, L1_wt=0.0, disp=0, maxiter=300)
            beta = float(fit.params[j])
            # statsmodels regularized fit lacks reliable bse; approximate via
            # the (penalized) Hessian if available, else mark CI unavailable.
            try:
                se = float(fit.bse[j])
            except Exception:
                se = float("nan")
            p = float(getattr(fit, "pvalues", [float("nan")] * len(cols))[j])
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
            return out
    if not (math.isfinite(beta)):
        out["error"] = "non-finite recovery coefficient"
        return out
    orr = math.exp(beta)
    if math.isfinite(se) and se > 0:
        or_lo, or_hi = math.exp(beta - 1.96 * se), math.exp(beta + 1.96 * se)
        ci = [round(or_lo, 4), round(or_hi, 4)]
        ev_ci = round(e_value_ci(orr, or_lo, or_hi), 3)
    else:
        or_lo = or_hi = float("nan")
        ci = [None, None]
        ev_ci = None
    out.update({
        "underpowered": False,
        "or_per_sd": round(orr, 4),
        "or_ci95": ci,
        "p_value": (p if math.isfinite(p) else None),
        "beta": round(beta, 4),
        "e_value_point": round(e_value(orr), 3),
        "e_value_ci": ev_ci,
    })
    return out


def adjusted_logistic_iptw(df, feature, outcome, seed=RANDOM_SEED):
    """IPTW-weighted adjusted OR. The treatment is a BINARISED recovery feature
    (good recovery = top half on the protective orientation) so we can reuse
    hypotension_treatment.fit_propensity_model / compute_iptw_weights, which expect
    a binary `vasopressor_treated` column. We rename the binary recovery exposure
    into that column so the existing propensity machinery applies unchanged."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    from vitaldb_aki.analysis.actionable_targets import e_value, e_value_ci
    from vitaldb_aki.analysis import hypotension_treatment as ht

    sub = df.dropna(subset=[outcome]).copy()
    feat = pd.to_numeric(sub[feature], errors="coerce")
    sub = sub[feat.notna()].copy()
    feat = feat[feat.notna()]
    direction = RECOVERY_DIRECTION.get(feature, +1)
    oriented = feat * direction
    med = oriented.median()
    # "treated" = GOOD recovery (oriented above median).
    sub["vasopressor_treated"] = (oriented > med).astype(int)

    n = int(len(sub)); events = int(sub[outcome].astype(float).astype(int).sum())
    out = {"feature": feature, "outcome": outcome, "n": n, "events": events,
           "exposure": "good_recovery (oriented > median)"}
    if events < MIN_EVENTS or n < 50 or sub["vasopressor_treated"].nunique() < 2:
        out["underpowered"] = True
        return out

    ps_covs = [c for c in PREOP_COVARIATES if c in sub.columns] + \
              [c for c in STATIC_BURDEN_COLS if c in sub.columns]
    try:
        sub_ps, _, used = ht.fit_propensity_model(sub, covariates=ps_covs)
        sub_w = ht.compute_iptw_weights(sub_ps)
        w = sub_w["iptw_weight"].to_numpy(dtype=float)
        X = pd.DataFrame({"good_recovery": sub_w["vasopressor_treated"].astype(float)},
                         index=sub_w.index)
        Xc = sm.add_constant(X, has_constant="add")
        fit = sm.GLM(
            sub_w[outcome].astype(float).to_numpy(),
            Xc.to_numpy().astype(float),
            family=sm.families.Binomial(),
            freq_weights=w,
        ).fit()
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    j = list(Xc.columns).index("good_recovery")
    beta = float(fit.params[j]); se = float(fit.bse[j]); p = float(fit.pvalues[j])
    lo, hi = beta - 1.96 * se, beta + 1.96 * se
    orr, or_lo, or_hi = math.exp(beta), math.exp(lo), math.exp(hi)
    out.update({
        "underpowered": False,
        "or_good_recovery": round(orr, 4),
        "or_ci95": [round(or_lo, 4), round(or_hi, 4)],
        "p_value": p,
        "e_value_point": round(e_value(orr), 3),
        "e_value_ci": round(e_value_ci(orr, or_lo, or_hi), 3),
        "ps_covariates_used": used,
    })
    return out


# ===========================================================================
# TEST 5 -- MONOTONIC DOSE-RESPONSE (quartiles + Cochran-Armitage trend)
# ===========================================================================
def _cochran_armitage(events_per_group, n_per_group, scores=None):
    """Cochran-Armitage trend test. events/n per ordered group; scores default
    0..K-1. Returns (z, two-sided p). Pure numpy + scipy.norm."""
    import numpy as np
    from scipy import stats

    e = np.asarray(events_per_group, float)
    n = np.asarray(n_per_group, float)
    K = len(e)
    if scores is None:
        scores = np.arange(K, dtype=float)
    else:
        scores = np.asarray(scores, float)
    N = n.sum()
    if N == 0:
        return float("nan"), float("nan")
    p_bar = e.sum() / N
    T = np.sum(scores * (e - n * p_bar))
    s_bar = np.sum(n * scores) / N
    var = p_bar * (1 - p_bar) * np.sum(n * (scores - s_bar) ** 2)
    if var <= 0:
        return float("nan"), float("nan")
    z = T / math.sqrt(var)
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return float(z), float(p)


def dose_response(df, feature, outcome, n_bins=4):
    """Bin the recovery feature into quartiles (oriented so Q1=worst recovery,
    Q4=best recovery) and report the AKI/outcome rate per quartile + a
    Cochran-Armitage trend test across quartiles."""
    import numpy as np
    import pandas as pd

    sub = df.dropna(subset=[outcome]).copy()
    feat = pd.to_numeric(sub[feature], errors="coerce")
    sub = sub[feat.notna()].copy()
    feat = feat[feat.notna()]
    direction = RECOVERY_DIRECTION.get(feature, +1)
    oriented = feat * direction      # higher = better recovery

    try:
        q = pd.qcut(oriented.rank(method="first"), n_bins, labels=False)
    except Exception as e:
        return {"feature": feature, "outcome": outcome, "error": str(e)}

    y = sub[outcome].astype(float).astype(int).to_numpy()
    rates, ns, evs = [], [], []
    for b in range(n_bins):
        mask = (q == b).to_numpy()
        yi = y[mask]
        ns.append(int(mask.sum()))
        evs.append(int(yi.sum()))
        rates.append(round(float(yi.mean()), 4) if mask.sum() else float("nan"))

    z, p = _cochran_armitage(evs, ns)
    # Under the protective hypothesis (Q4 = BEST recovery) the outcome rate should
    # DECREASE from Q1 to Q4. A positive z (rate rising with quartile) therefore
    # CONTRADICTS the hypothesis -- record that explicitly so a "significant trend"
    # is not mistaken for support.
    if z != z:
        direction = None
    elif z < 0:
        direction = "protective (rate falls Q1->Q4, supports hypothesis)"
    else:
        direction = "ANTI-hypothesis (rate RISES Q1->Q4; best-recovery quartile has HIGHER rate)"
    return {
        "feature": feature, "outcome": outcome,
        "orientation": "Q1=worst recovery ... Q4=best recovery",
        "quartile_n": ns,
        "quartile_events": evs,
        "quartile_rates": rates,
        "trend_z": round(z, 4) if z == z else None,
        "trend_p": p if p == p else None,
        "trend_direction": direction,
        "trend_test": "Cochran-Armitage",
    }


# ===========================================================================
# ORCHESTRATION
# ===========================================================================
def run(seed=RANDOM_SEED, write=True):
    """Full reperfusion-dynamics analysis. Returns the results dict; optionally
    writes cache/reperfusion_dynamics_results.json."""
    df = load_merged()
    df, feature_names = build_recovery_features(df)

    results: dict[str, Any] = {
        "module": "reperfusion_dynamics",
        "thesis": ("Recovery DYNAMICS (how fast MAP is restored after a "
                   "hypotensive nadir) carry organ-injury signal BEYOND static "
                   "hypotension burden."),
        "seed": seed,
        "n_cases": int(len(df)),
        "recovery_features": feature_names,
        "recovery_feature_definitions": {
            "recovery_velocity": "map_early_vs_late_mean_delta / (65 - map_lowest)+",
            "debt_repayment_rate": "map_auc_below_65 / map_longest_hypotension_run_min",
            "late_residual_burden": "map_auc65_late",
            "recovery_slope": "map_slope_per_hr",
            "nadir_recovery_frac": "1 - map_nadir_time_frac",
            "recovery_lag": "pfds_clin_recovery_lag",
        },
        "static_burden_baseline": STATIC_BURDEN_COLS,
        "derived_from": ("per-case SUMMARY statistics (NOT raw per-beat MAP "
                         "series); per-beat recovery slope is future work."),
        "incremental_auroc": {},
        "adjusted_logistic": {},
        "adjusted_iptw": {},
        "dose_response": {},
        "negative_control_outcome": NEGATIVE_CONTROL,
    }

    # --- TEST 1: incremental AUROC for each outcome (incl. negative control) ---
    for outcome in ALL_OUTCOMES:
        results["incremental_auroc"][outcome] = incremental_auroc(
            df, feature_names, outcome, seed=seed)

    # --- TESTS 2: adjusted association (unweighted + IPTW), per feature/outcome ---
    fdr_pvals = []
    fdr_keys = []
    for outcome in ALL_OUTCOMES:
        results["adjusted_logistic"][outcome] = {}
        results["adjusted_iptw"][outcome] = {}
        for feat in feature_names:
            r = adjusted_logistic(df, feat, outcome)
            results["adjusted_logistic"][outcome][feat] = r
            if not r.get("underpowered") and r.get("p_value") is not None:
                fdr_pvals.append(r["p_value"])
                fdr_keys.append((outcome, feat))
            results["adjusted_iptw"][outcome][feat] = adjusted_logistic_iptw(
                df, feat, outcome, seed=seed)

    # --- TEST 4: BH-FDR across (feature x outcome) adjusted logistic tests ---
    from vitaldb_aki.analysis.actionable_targets import benjamini_hochberg
    rejects = benjamini_hochberg(fdr_pvals, alpha=0.05)
    results["fdr"] = {
        "alpha": 0.05,
        "n_tests": len(fdr_pvals),
        "method": "Benjamini-Hochberg across adjusted-logistic feature x outcome tests",
        "significant": [
            {"outcome": k[0], "feature": k[1], "p_value": p, "fdr_reject": bool(rej)}
            for k, p, rej in zip(fdr_keys, fdr_pvals, rejects)
        ],
    }

    # --- TEST 5: dose-response on the BEST recovery feature (by |DeLong z| on
    #     the primary composite incremental model is set-level; instead pick the
    #     feature with the most significant adjusted-logistic p on organ_renal,
    #     fall back to composite). ---
    def _best_feature(outcome):
        d = results["adjusted_logistic"].get(outcome, {})
        cand = [(f, r["p_value"]) for f, r in d.items()
                if not r.get("underpowered") and r.get("p_value") is not None]
        if not cand:
            return None
        return min(cand, key=lambda t: t[1])[0]

    best = _best_feature("organ_renal") or _best_feature("composite") or feature_names[0]
    results["best_recovery_feature"] = best
    for outcome in ALL_OUTCOMES:
        results["dose_response"][outcome] = dose_response(df, best, outcome)

    # --- Negative-control summary (incremental signal must be weaker/null) ---
    ia = results["incremental_auroc"]
    def _d(o):
        return ia.get(o, {}).get("delta_auroc")
    results["negative_control_summary"] = {
        "delta_auroc_composite": _d("composite"),
        "delta_auroc_organ_renal": _d("organ_renal"),
        "delta_auroc_hepatocellular": _d(NEGATIVE_CONTROL),
        "interpretation": ("Incremental AUROC on the hepatocellular negative "
                           "control should be weaker / null relative to the "
                           "renal & composite outcomes if the recovery signal "
                           "is renal-perfusion-specific."),
    }

    if write:
        with open(_RESULTS_JSON, "w") as fh:
            json.dump(results, fh, indent=2, allow_nan=True)
        results["_written_to"] = _RESULTS_JSON

    return results


def _fmt(results):
    """Console summary."""
    lines = ["", "=" * 72,
             "REPERFUSION-DYNAMICS BIOMARKER -- recovery velocity over static burden",
             "=" * 72,
             f"N cases merged: {results['n_cases']}   seed: {results['seed']}",
             f"Recovery features: {', '.join(results['recovery_features'])}",
             "",
             "TEST 1 -- Incremental AUROC (recovery set OVER static burden), DeLong:"]
    for o in ALL_OUTCOMES:
        r = results["incremental_auroc"][o]
        tag = "  [NEG-CTRL]" if o == NEGATIVE_CONTROL else ""
        if r.get("underpowered"):
            lines.append(f"  {o:22s}{tag} UNDERPOWERED (n={r.get('n')}, events={r.get('events')})")
            continue
        lines.append(
            f"  {o:22s}{tag} AUROC {r['auroc_static_burden']:.3f} -> "
            f"{r['auroc_static_plus_recovery']:.3f}  dAUROC={r['delta_auroc']:+.4f} "
            f"CI95[{r['delta_auroc_ci95'][0]:+.4f},{r['delta_auroc_ci95'][1]:+.4f}] "
            f"p={r['delong_p']:.4f}  (events={r['events']})")

    lines += ["", "TEST 2 -- Adjusted logistic OR per SD (best feature shown per outcome):"]
    for o in ALL_OUTCOMES:
        best = results["best_recovery_feature"]
        r = results["adjusted_logistic"][o].get(best, {})
        if r.get("underpowered") or "or_per_sd" not in r:
            lines.append(f"  {o:22s} {best}: n/a")
            continue
        ci = r.get("or_ci95") or [None, None]
        ci_s = (f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci[0] is not None else "[n/a]")
        p_s = (f"{r['p_value']:.4f}" if r.get("p_value") is not None else "n/a")
        lines.append(
            f"  {o:22s} {best}: OR/SD={r['or_per_sd']:.3f} "
            f"CI{ci_s} p={p_s} E={r['e_value_point']} (CI E={r['e_value_ci']})")

    lines += ["", f"TEST 5 -- Dose-response (best feature = {results['best_recovery_feature']}):"]
    for o in ALL_OUTCOMES:
        r = results["dose_response"][o]
        if "error" in r:
            lines.append(f"  {o:22s} error: {r['error']}")
            continue
        rates = ", ".join(f"{x:.3f}" for x in r["quartile_rates"])
        lines.append(f"  {o:22s} Q1..Q4 rates=[{rates}] trend p={r['trend_p']}")

    nc = results["negative_control_summary"]
    lines += ["", "NEGATIVE CONTROL (hepatocellular dAUROC must be weaker/null):",
              f"  composite={nc['delta_auroc_composite']}  "
              f"renal={nc['delta_auroc_organ_renal']}  "
              f"hepatocellular={nc['delta_auroc_hepatocellular']}"]

    fdr = results["fdr"]
    nsig = sum(1 for s in fdr["significant"] if s["fdr_reject"])
    lines += ["", f"FDR: {nsig}/{fdr['n_tests']} adjusted tests survive BH at q<0.05"]
    lines += ["=" * 72, ""]
    return "\n".join(lines)


def main():
    results = run(write=True)
    print(_fmt(results))
    print(f"Results JSON -> {results.get('_written_to')}")


if __name__ == "__main__":
    main()
