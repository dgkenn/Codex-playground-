"""hypotension_treatment.py -- Modifiable-risk analysis: early vasopressor treatment
and composite organ-injury at matched intraoperative hypotension burden (VitalDB).

Research question
-----------------
At matched intraoperative hypotension burden (MAP-AUC below 65 mmHg), is early
vasopressor treatment (ephedrine OR phenylephrine) associated with lower composite
organ-injury risk?

Design
------
Observational causal-inference analysis; confounding by indication is the central
threat (sicker / more haemodynamically unstable patients are more likely to receive
pressors AND more likely to develop organ injury).  We use propensity-score methods
(logistic PS model + IPTW + propensity-stratified logistic regression) to attenuate
observed confounding.  Results are **hypothesis-generating only**.

Entry points
------------
    main(matrix_path=None, cache_dir=None)   -- CLI / script entry
    run_analysis(df, cache_dir=None)         -- programmatic; accepts a DataFrame

Heavy dependencies (numpy, pandas, sklearn, scipy, statsmodels) are lazy-imported
inside functions so that the integrity / import core stays stdlib-only, matching the
repo convention in features/* and models/dataset.py.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BURDEN_COL   = "map_auc_below_65"   # MAP-AUC below 65 mmHg·min
EPH_COL      = "intraop_eph"        # ephedrine  (mg)
PHE_COL      = "intraop_phe"        # phenylephrine (μg)
OUTCOME_COL  = "composite"          # composite organ-injury flag (0/1)
SUBJECT_COL  = "subjectid"

TERTILE_LABELS = ("low", "med", "high")

# Propensity-model covariates (preop + intraop non-treatment).
# Columns are looked up dynamically at runtime; missing ones are silently dropped
# so the module degrades gracefully when only a subset of features are present.
DEFAULT_PS_COVARIATES = [
    "age", "sex_male", "asa_class",
    "baseline_cr", "egfr_ckd_epi",
    "dm", "htn", "hf", "ckd",              # comorbidity flags
    "surgery_duration",
    BURDEN_COL, "map_min_below_65",         # hypotension burden (key confounder)
    "ebl",                                  # estimated blood loss
]

# Bootstrap replicates for confidence intervals.
N_BOOTSTRAP = 500
RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Step 1 -- Define treatment
# ---------------------------------------------------------------------------

def define_treatment(df):
    """Add ``vasopressor_treated`` binary column (1 = received any bolus).

    Treatment is defined as having received ANY ephedrine OR phenylephrine
    dose during the intraoperative period (EPH>0 OR PHE>0).

    Parameters
    ----------
    df : pandas.DataFrame
        Feature matrix containing ``intraop_eph`` and ``intraop_phe`` columns.
        Columns not present are treated as zero.

    Returns
    -------
    pandas.DataFrame
        Copy of *df* with an additional ``vasopressor_treated`` column (int 0/1).
    """
    import pandas as pd  # lazy import -- repo convention

    df = df.copy()
    eph = pd.to_numeric(df.get(EPH_COL, 0), errors="coerce").fillna(0.0)
    phe = pd.to_numeric(df.get(PHE_COL, 0), errors="coerce").fillna(0.0)
    df["vasopressor_treated"] = ((eph > 0) | (phe > 0)).astype(int)
    return df


# ---------------------------------------------------------------------------
# Step 2 -- Burden tertiles
# ---------------------------------------------------------------------------

def assign_burden_tertiles(df):
    """Assign MAP-AUC burden to tertiles: 0=low, 1=med, 2=high.

    Ties are broken consistently by ``pandas.qcut`` using ``duplicates='drop'``
    to handle the common case where many subjects have AUC=0 (no hypotension).

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain ``map_auc_below_65``.

    Returns
    -------
    pandas.DataFrame
        Copy with additional ``burden_tertile`` (int 0/1/2) and
        ``burden_label`` (str "low"/"med"/"high") columns.
    """
    import pandas as pd
    import numpy as np

    df = df.copy()
    burden = pd.to_numeric(df[BURDEN_COL], errors="coerce")
    # qcut with 3 equal-frequency bins; duplicates='drop' merges zero-inflated
    # edge bins so the result is always well-defined.
    try:
        labels_cat = pd.qcut(burden, q=3, labels=False, duplicates="drop")
    except ValueError:
        # Degenerate case: all values identical -- assign mid tertile
        labels_cat = pd.Series(1, index=df.index)

    df["burden_tertile"] = labels_cat.astype("Int64")
    df["burden_label"] = df["burden_tertile"].map(
        {0: "low", 1: "med", 2: "high"}
    )
    return df


# ---------------------------------------------------------------------------
# Step 3 -- Crude rate table
# ---------------------------------------------------------------------------

def crude_rate_table(df):
    """Compute composite outcome rates stratified by burden tertile x treatment.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain ``burden_label``, ``vasopressor_treated``, ``composite``.

    Returns
    -------
    pandas.DataFrame
        Rows = burden strata (low/med/high), columns = untreated/treated.
        Cell values: dict with keys ``n``, ``events``, ``rate``.
    """
    import pandas as pd

    outcome = pd.to_numeric(df[OUTCOME_COL], errors="coerce")
    treated  = df["vasopressor_treated"]
    tertile  = df["burden_label"]

    rows = []
    for label in TERTILE_LABELS:
        mask_t  = tertile == label
        for trt in (0, 1):
            mask = mask_t & (treated == trt)
            n      = int(mask.sum())
            events = int(outcome[mask].sum()) if n > 0 else 0
            rate   = round(events / n, 4) if n > 0 else None
            rows.append({
                "burden":   label,
                "treated":  trt,
                "n":        n,
                "events":   events,
                "rate":     rate,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 4 -- Propensity model
# ---------------------------------------------------------------------------

def fit_propensity_model(df, covariates=None):
    """Fit a logistic regression propensity model for vasopressor treatment.

    Only covariates present in *df* are used; missing columns are silently
    dropped so the analysis degrades gracefully on reduced matrices.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain ``vasopressor_treated``.
    covariates : list[str] | None
        Covariate names; defaults to ``DEFAULT_PS_COVARIATES``.

    Returns
    -------
    tuple[pandas.DataFrame, sklearn.pipeline.Pipeline, list[str]]
        (df_with_ps, fitted_pipeline, used_covariates)
        *df_with_ps* gains a ``propensity_score`` column.
    """
    import pandas as pd
    import numpy as np
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    covariates = covariates or DEFAULT_PS_COVARIATES
    available  = [c for c in covariates if c in df.columns]

    df = df.copy()

    # Numeric-only coercion for the PS model
    X_raw = df[available].apply(pd.to_numeric, errors="coerce")
    y     = df["vasopressor_treated"].astype(int).to_numpy()

    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale",  StandardScaler()),
        ("lr",     LogisticRegression(
            max_iter=1000,
            solver="lbfgs",
            C=1.0,
            random_state=RANDOM_SEED,
        )),
    ])
    pipe.fit(X_raw, y)
    ps = pipe.predict_proba(X_raw)[:, 1]
    df["propensity_score"] = ps
    return df, pipe, available


# ---------------------------------------------------------------------------
# Step 5 -- IPTW weights
# ---------------------------------------------------------------------------

def compute_iptw_weights(df, trim_quantile=0.01):
    """Add stabilised IPTW weights; trim extreme weights at *trim_quantile*.

    Stabilised ATE weights:
        treated     : w = p(T=1) / ps
        untreated   : w = p(T=0) / (1 - ps)

    where p(T=1) is the marginal probability of treatment.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain ``propensity_score`` and ``vasopressor_treated``.
    trim_quantile : float
        Symmetrically trim weights below this quantile and above 1-quantile.

    Returns
    -------
    pandas.DataFrame
        Copy with ``iptw_weight`` column added.
    """
    import numpy as np

    df = df.copy()
    ps  = df["propensity_score"].to_numpy(dtype=float)
    trt = df["vasopressor_treated"].to_numpy(dtype=int)

    # Clip PS away from 0/1 to avoid extreme weights
    ps = ps.clip(1e-6, 1 - 1e-6)

    p1 = trt.mean()           # marginal P(T=1)
    p0 = 1.0 - p1             # marginal P(T=0)

    weights = np.where(trt == 1, p1 / ps, p0 / (1.0 - ps))

    # Symmetric trim at trim_quantile / 1-trim_quantile
    lo = float(np.quantile(weights, trim_quantile))
    hi = float(np.quantile(weights, 1.0 - trim_quantile))
    weights = weights.clip(lo, hi)

    df["iptw_weight"] = weights
    return df


# ---------------------------------------------------------------------------
# Step 6 -- Covariate balance
# ---------------------------------------------------------------------------

def check_balance(df, covariates=None, weight_col=None):
    """Compute standardised mean difference (SMD) for each covariate.

    SMD = |mean_treated - mean_untreated| / pooled_SD
    Values < 0.1 indicate adequate balance (Austin 2011 convention).

    Parameters
    ----------
    df : pandas.DataFrame
    covariates : list[str] | None
    weight_col : str | None
        If given, use as sample weights for the weighted means/SDs.

    Returns
    -------
    pandas.DataFrame
        Columns: covariate, smd, smd_label ("ok"/<"0.1")
    """
    import pandas as pd
    import numpy as np

    covariates = covariates or DEFAULT_PS_COVARIATES
    available  = [c for c in covariates if c in df.columns]

    trt  = df["vasopressor_treated"].astype(int).to_numpy()
    rows = []
    for col in available:
        x = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        w = df[weight_col].to_numpy(dtype=float) if weight_col else np.ones(len(x))

        def _wmean(mask):
            xi, wi = x[mask], w[mask]
            finite  = np.isfinite(xi) & np.isfinite(wi)
            if not finite.any():
                return np.nan
            return float(np.average(xi[finite], weights=wi[finite]))

        def _wvar(mask):
            xi, wi = x[mask], w[mask]
            finite  = np.isfinite(xi) & np.isfinite(wi)
            if finite.sum() < 2:
                return np.nan
            mu = np.average(xi[finite], weights=wi[finite])
            return float(np.average((xi[finite] - mu) ** 2, weights=wi[finite]))

        m1 = _wmean(trt == 1)
        m0 = _wmean(trt == 0)
        v1 = _wvar(trt == 1)
        v0 = _wvar(trt == 0)

        pooled_sd = float(np.sqrt((v1 + v0) / 2.0)) if (
            np.isfinite(v1) and np.isfinite(v0) and (v1 + v0) > 0
        ) else np.nan

        smd = abs(m1 - m0) / pooled_sd if (np.isfinite(pooled_sd) and pooled_sd > 0
                                            and np.isfinite(m1) and np.isfinite(m0)) else np.nan
        rows.append({
            "covariate": col,
            "mean_treated":   round(m1, 4) if np.isfinite(m1) else None,
            "mean_untreated": round(m0, 4) if np.isfinite(m0) else None,
            "smd":            round(smd, 4) if np.isfinite(smd) else None,
            "balanced":       bool(smd < 0.1) if np.isfinite(smd) else None,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 7 -- IPTW outcome model
# ---------------------------------------------------------------------------

def iptw_outcome_model(df, n_bootstrap=N_BOOTSTRAP, seed=RANDOM_SEED):
    """Estimate the treatment-outcome association via weighted logistic regression.

    Fits a logistic regression of ``composite`` on ``vasopressor_treated``
    (+ burden tertile dummies as covariates) with ``iptw_weight`` as sample
    weights.  Returns OR + bootstrap 95% CI.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain ``composite``, ``vasopressor_treated``, ``iptw_weight``,
        and ``burden_tertile``.
    n_bootstrap : int
    seed : int

    Returns
    -------
    dict
        ``{"OR": float, "CI_lower": float, "CI_upper": float, "log_OR": float,
           "log_OR_se_bootstrap": float, "n": int, "n_events": int}``
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(seed)

    # Drop rows with missing outcome or weight
    mask   = (
        df[OUTCOME_COL].notna()
        & df["vasopressor_treated"].notna()
        & df["iptw_weight"].notna()
    )
    sub    = df[mask].copy()
    y      = pd.to_numeric(sub[OUTCOME_COL], errors="coerce").astype(int).to_numpy()
    trt    = sub["vasopressor_treated"].astype(int).to_numpy()
    wts    = sub["iptw_weight"].to_numpy(dtype=float)

    # Build design matrix: treatment + burden tertile indicators
    bt = pd.to_numeric(sub.get("burden_tertile", pd.Series(1, index=sub.index)),
                       errors="coerce").fillna(1).astype(int).to_numpy()
    X  = np.column_stack([
        trt,
        (bt == 1).astype(float),   # medium burden indicator
        (bt == 2).astype(float),   # high burden indicator
    ])

    def _fit_or(X_, y_, w_):
        lr = LogisticRegression(
            fit_intercept=True, max_iter=1000, solver="lbfgs",
            C=1e6,   # nearly unpenalised; weights carry the adjustment
            random_state=seed,
        )
        lr.fit(X_, y_, sample_weight=w_)
        return float(lr.coef_[0][0])   # log-OR for treatment

    log_or_point = _fit_or(X, y, wts)

    # Bootstrap CI
    log_or_boot = []
    n = len(y)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        try:
            lo = _fit_or(X[idx], y[idx], wts[idx])
            log_or_boot.append(lo)
        except Exception:
            pass   # convergence failure in a degenerate bootstrap draw

    log_or_boot_arr = np.array(log_or_boot)
    ci_lo = float(np.percentile(log_or_boot_arr, 2.5))  if len(log_or_boot_arr) else float("nan")
    ci_hi = float(np.percentile(log_or_boot_arr, 97.5)) if len(log_or_boot_arr) else float("nan")

    import math
    return {
        "log_OR":               round(log_or_point, 4),
        "OR":                   round(math.exp(log_or_point), 4),
        "CI_lower":             round(math.exp(ci_lo), 4) if math.isfinite(ci_lo) else None,
        "CI_upper":             round(math.exp(ci_hi), 4) if math.isfinite(ci_hi) else None,
        "log_OR_se_bootstrap":  round(float(log_or_boot_arr.std()), 4) if len(log_or_boot_arr) else None,
        "n":                    int(n),
        "n_events":             int(y.sum()),
    }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_analysis(df, cache_dir=None):
    """Run the full modifiable-risk analysis pipeline.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature matrix (must contain burden, vasopressor, and outcome columns).
    cache_dir : str | None
        If supplied, write ``hypotension_treatment_results.json`` here.

    Returns
    -------
    dict
        Full results dictionary with crude table, balance SMDs, and adjusted OR.
    """
    import pandas as pd
    import numpy as np

    # ------------------------------------------------------------------ #
    # 1. Define treatment & burden tertiles
    # ------------------------------------------------------------------ #
    df = define_treatment(df)
    df = assign_burden_tertiles(df)

    # Drop rows without a valid outcome label
    outcome_num = pd.to_numeric(df[OUTCOME_COL], errors="coerce")
    df = df[outcome_num.notna()].copy()

    n_total    = len(df)
    n_treated  = int((df["vasopressor_treated"] == 1).sum())
    n_events   = int(pd.to_numeric(df[OUTCOME_COL], errors="coerce").sum())

    # ------------------------------------------------------------------ #
    # 2. Crude rate table
    # ------------------------------------------------------------------ #
    crude = crude_rate_table(df)

    # ------------------------------------------------------------------ #
    # 3. Propensity model + IPTW
    # ------------------------------------------------------------------ #
    df_ps, ps_model, ps_covariates = fit_propensity_model(df)
    df_iptw = compute_iptw_weights(df_ps)

    # ------------------------------------------------------------------ #
    # 4. Covariate balance pre / post weighting
    # ------------------------------------------------------------------ #
    balance_pre  = check_balance(df_iptw, covariates=ps_covariates)
    balance_post = check_balance(df_iptw, covariates=ps_covariates,
                                 weight_col="iptw_weight")

    # Summarise: max SMD before / after
    max_smd_pre  = float(balance_pre["smd"].dropna().max())  if not balance_pre.empty  else float("nan")
    max_smd_post = float(balance_post["smd"].dropna().max()) if not balance_post.empty else float("nan")
    n_balanced_pre  = int((balance_pre["smd"].dropna()  < 0.1).sum())
    n_balanced_post = int((balance_post["smd"].dropna() < 0.1).sum())

    # ------------------------------------------------------------------ #
    # 5. IPTW outcome model
    # ------------------------------------------------------------------ #
    or_result = iptw_outcome_model(df_iptw)

    # ------------------------------------------------------------------ #
    # 6. Assemble results
    # ------------------------------------------------------------------ #
    results: dict[str, Any] = {
        "n_total":    n_total,
        "n_treated":  n_treated,
        "n_events":   n_events,
        "treatment_rate":  round(n_treated / n_total, 4) if n_total else None,
        "event_rate":      round(n_events  / n_total, 4) if n_total else None,
        "ps_covariates":   ps_covariates,
        "crude_table":     crude.to_dict(orient="records"),
        "balance": {
            "pre_weighting":  balance_pre.to_dict(orient="records"),
            "post_weighting": balance_post.to_dict(orient="records"),
            "max_smd_pre":    round(max_smd_pre,  4) if np.isfinite(max_smd_pre)  else None,
            "max_smd_post":   round(max_smd_post, 4) if np.isfinite(max_smd_post) else None,
            "n_balanced_pre":  n_balanced_pre,
            "n_balanced_post": n_balanced_post,
        },
        "iptw_or": or_result,
        "interpretation": (
            "Confounding-by-indication direction: sicker/more unstable patients "
            "are more likely to receive vasopressors AND more likely to sustain "
            "organ injury, biasing the crude estimate TOWARD harm for the treated "
            "group.  A propensity-adjusted OR < 1.0 for vasopressor treatment "
            "would be consistent with a beneficial effect at matched burden; "
            "OR >= 1.0 after weighting may still reflect residual unmeasured "
            "confounding.  This analysis is hypothesis-generating only."
        ),
    }

    # ------------------------------------------------------------------ #
    # 7. Write cache
    # ------------------------------------------------------------------ #
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        out_path = os.path.join(cache_dir, "hypotension_treatment_results.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, default=_json_default)

    return results


def _json_default(obj):
    """Fallback serialiser for numpy scalars, NaN, etc."""
    import math
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(matrix_path=None, cache_dir=None):
    """CLI entry point.

    If ``/vitaldb_aki/cache/_matrix_build_done.json`` exists (or *matrix_path*
    is supplied), load the real feature matrix and run the analysis.
    Otherwise, synthesise a small confounded dataset and run offline to
    demonstrate the pipeline.
    """
    import pandas as pd

    # Resolve paths
    _here      = os.path.dirname(os.path.abspath(__file__))
    _pkg_root  = os.path.dirname(_here)
    _cache_dir = cache_dir or os.path.join(_pkg_root, "cache")
    _done_flag = os.path.join(_cache_dir, "_matrix_build_done.json")

    if matrix_path and os.path.exists(matrix_path):
        print(f"[hypotension_treatment] Loading matrix from {matrix_path}")
        df = pd.read_csv(matrix_path)
    elif os.path.exists(_done_flag):
        _matrix = os.path.join(_cache_dir, "feature_matrix.csv")
        print(f"[hypotension_treatment] Real matrix found; loading {_matrix}")
        df = pd.read_csv(_matrix)
    else:
        print("[hypotension_treatment] No real matrix -- running on SYNTHETIC data (offline demo).")
        df = _make_synthetic_df(n=400, seed=RANDOM_SEED)

    results = run_analysis(df, cache_dir=_cache_dir)

    or_res = results["iptw_or"]
    print(
        f"\n=== Hypotension-Treatment Modifiable-Risk Analysis ===\n"
        f"  N={results['n_total']}  treated={results['n_treated']}  "
        f"events={results['n_events']}\n"
        f"  IPTW-adjusted OR={or_res['OR']}  "
        f"95% CI [{or_res['CI_lower']}, {or_res['CI_upper']}]\n"
        f"  Max SMD before weighting: {results['balance']['max_smd_pre']}\n"
        f"  Max SMD after weighting:  {results['balance']['max_smd_post']}\n"
        f"\nResults written to {_cache_dir}/hypotension_treatment_results.json\n"
    )
    return results


# ---------------------------------------------------------------------------
# Synthetic dataset for offline testing / demo
# ---------------------------------------------------------------------------

def _make_synthetic_df(n=400, seed=42):
    """Build a small confounded synthetic dataset for offline testing.

    Confounding-by-indication structure:
      - High burden (AUC) -> more likely treated
      - High burden -> more likely outcome
      - Treatment also has a direct protective effect (OR~0.6)
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)

    # Preop features
    age    = rng.normal(60, 12, n).clip(18, 90)
    sex    = rng.integers(0, 2, n)
    asa    = rng.choice([1, 2, 3, 4], n, p=[0.15, 0.45, 0.35, 0.05])
    cr     = rng.gamma(1.2, 0.8, n).clip(0.4, 5.0)
    egfr   = (140 - age) * (0.85 if True else 1.0) / cr  # crude approximation
    dm     = rng.binomial(1, 0.2, n)
    htn    = rng.binomial(1, 0.45, n)
    hf     = rng.binomial(1, 0.08, n)
    ckd    = (cr > 1.5).astype(int)
    dur    = rng.gamma(3.0, 45.0, n)        # surgery duration (min)
    ebl    = rng.exponential(200, n)

    # Hypotension burden: mixture -- many zeros + heavy tail
    burden_z      = rng.exponential(5.0, n)
    map_auc_65    = burden_z
    map_min_65    = rng.exponential(2.0, n)

    # Vasopressor exposure (confounded: high burden + sick -> more treated)
    log_odds_trt  = -1.5 + 0.08 * (map_auc_65 - map_auc_65.mean()) + 0.5 * (asa > 2)
    p_trt         = 1.0 / (1.0 + np.exp(-log_odds_trt))
    eph_any       = rng.binomial(1, p_trt, n)
    phe_any       = rng.binomial(1, p_trt * 0.6, n)
    eph_mg        = eph_any * rng.exponential(8.0, n)
    phe_ug        = phe_any * rng.exponential(100.0, n)

    # Composite outcome (burden + sickness + protective treatment effect)
    treated        = ((eph_mg > 0) | (phe_ug > 0)).astype(int)
    log_odds_out   = (
        -2.0
        + 0.06 * (map_auc_65 - map_auc_65.mean())
        + 0.4  * (asa > 2)
        + 0.3  * ckd
        - 0.5  * treated        # true protective effect of treatment
        + 0.4  * (ebl > 400)
    )
    p_out     = 1.0 / (1.0 + np.exp(-log_odds_out))
    composite = rng.binomial(1, p_out, n).astype(float)

    subjectids = [f"S{i:04d}" for i in range(n)]

    df = pd.DataFrame({
        SUBJECT_COL:  subjectids,
        OUTCOME_COL:  composite,
        BURDEN_COL:   map_auc_65,
        "map_min_below_65": map_min_65,
        EPH_COL:      eph_mg,
        PHE_COL:      phe_ug,
        "age":         age,
        "sex_male":    sex,
        "asa_class":   asa.astype(float),
        "baseline_cr": cr,
        "egfr_ckd_epi": egfr,
        "dm":   dm.astype(float),
        "htn":  htn.astype(float),
        "hf":   hf.astype(float),
        "ckd":  ckd.astype(float),
        "surgery_duration": dur,
        "ebl":  ebl,
    })
    return df


if __name__ == "__main__":
    import sys
    _args = sys.argv[1:]
    _matrix = _args[0] if _args else None
    main(matrix_path=_matrix)
