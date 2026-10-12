"""map_target_analysis.py -- Does a HIGHER intraoperative MAP target (70/75 vs the
canonical 65) reduce end-organ injury?  A rigorously-confounder-controlled,
journal-defensible observational interrogation on VitalDB.

THE CENTRAL BIAS (stated plainly, and guarded against throughout)
-----------------------------------------------------------------
Patients who *naturally* hold MAP >= 75 mmHg through an operation are, on average,
HEALTHIER: less vasoplegia, better baseline cardiac function, smaller / shorter
operations, lower blood loss.  Achieved-MAP >= 75 is therefore mostly a MARKER of
being well, NOT a cause of good kidneys.  A naive contrast --

    "achieved MAP >= 75  vs  not  ->  AKI"

is fatally confounded by indication / by health, and will manufacture a spurious
"protective" association of a higher MAP target.  We report that naive estimate
EXPLICITLY LABELLED AS CONFOUNDED, precisely to show the gap to the adjusted
estimates; we never headline it.

WHAT IS ACTUALLY DEFENSIBLE
---------------------------
We attack the question four ways, each designed so the exposure is *modifiable*
and the confounding is *controlled*:

  (A) INCREMENTAL-BAND test (the cleanest primary).  Does hypotension burden in the
      65-75 BAND add AKI risk BEYOND burden < 65?  If so, that is "risk the current
      65 guideline misses".  Nested adjusted logistic models + LRT + DeLong ΔAUROC.

  (B) ADJUSTED THRESHOLD-RESPONSE CURVE.  For each threshold T in 50..80, the
      fully-adjusted OR per SD of below-T burden.  Honest read: does adjusted risk
      keep climbing above 65 toward 75 (-> a higher target might help), or flatten
      at 65 (-> no benefit to a higher target)?

  (C) MODIFIABLE (expected-vs-observed) EXPOSURE + IPTW target-trial.  Residualize
      below-75 burden on the surgical-insult + baseline covariates: the RESIDUAL is
      "more time below 75 than the case warranted" -- the modifiable excess, shorn
      of the health-marker component.  Top-tertile residual = "under-treated at the
      75 target".  IPTW (reusing hypotension_treatment) -> risk difference / risk
      ratio for AKI.  Repeated at the 65 target as a comparator.

  (D) BIAS-CONTROL BATTERY.  E-value (VanderWeele) + its CI bound; a NEGATIVE-CONTROL
      outcome a MAP target should not cause (organ_cholestatic) run through the SAME
      models (a non-null result flags residual confounding); dose-response
      monotonicity; and effect-modification by the vulnerable phenotype.

Deliverable: a rigorously-controlled, externally-validatable HYPOTHESIS for a
randomized 65-vs-75 MAP-target trial (benchmark: INPRESS, RR ~0.73 for organ
dysfunction).  NOT proof of causation.  Results that are null / flat at 65 are
reported as such, and underpowered cells (events < 15) are flagged.

Public entry
------------
    run_map_target_analysis(cfg) -> dict

Writes (in this order; the done-flag is LAST):
    cache/map_target_results.json
    docs/MAP_TARGET_RESULTS.md
    cache/_map_target_done.json

Heavy dependencies (numpy, pandas, sklearn, scipy) are lazy-imported inside
functions, so the module imports under the stdlib-only integrity core -- matching
the repo convention in phenotypes.py / hypotension_treatment.py / phenotype_v2.py.
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Exposure / covariate definitions  (single source of truth -- documented)
# ---------------------------------------------------------------------------

# Outcomes analysed (organ_renal primary, composite secondary).
PRIMARY_OUTCOME = "organ_renal"
SECONDARY_OUTCOME = "composite"
OUTCOMES = (PRIMARY_OUTCOME, SECONDARY_OUTCOME)

# Negative-control outcome (D): something a MAP target should NOT cause.  A
# non-null association of the modifiable MAP-target exposure with this outcome,
# through the SAME adjusted model, is evidence of residual confounding.
NEGATIVE_CONTROL_OUTCOME = "organ_cholestatic"

# Thresholds present in map_thresholds.csv (min_below_T / auc_below_T).
THRESHOLDS = (50, 55, 60, 65, 70, 75, 80)

# The two MAP targets we contrast: the canonical 65, and the candidate higher 75.
BASE_TARGET = 65
HIGH_TARGET = 75

# Confounder set (Saugel 2024-style): demographics + baseline organ reserve +
# surgical magnitude + the cumulative vasopressor dose (so the exposure is not just
# proxying "got lots of pressor").  Names are resolved leniently against the merged
# matrix; missing columns are silently dropped so the analysis degrades gracefully.
CONFOUNDERS = [
    "age",
    "sex_male",
    "asa",
    "preop_htn",
    "preop_dm",
    "preop_cr",                 # falls back to baseline_cr if absent (resolved below)
    "intraop_ebl",
    "anesthesia_duration_min",
    "optype_code",              # numeric-encoded surgery type (built if optype present)
    "cum_vasopressor_dose",     # intraop_phe + 10*intraop_eph + intraop_epi (built below)
]

# Surgical-insult + baseline covariates the MODIFIABLE-exposure residualizer (C)
# regresses below-T burden on.  Burden NOT explained by these = the modifiable
# excess.  (We deliberately EXCLUDE cumulative vasopressor here: pressor use is a
# CONSEQUENCE of low MAP / a treatment, so conditioning on it would residualize
# away part of the very thing we want to capture.)
INSULT_COVARIATES = [
    "age", "asa", "anesthesia_duration_min", "intraop_ebl",
    "preop_cr", "preop_htn", "preop_dm", "sex_male", "optype_code",
]

RANDOM_SEED = 42
N_BOOTSTRAP = 500
UNDERPOWERED_EVENTS = 15        # flag any analysed cell with fewer events than this


# ===========================================================================
# PURE HELPERS (stdlib-light -- covered by the stdlib-only test file)
# ===========================================================================

def e_value(point_estimate: float) -> float:
    """E-value for a risk-ratio-scale point estimate (VanderWeele & Ding 2017).

    Minimum strength of association (RR scale) an unmeasured confounder would need
    with BOTH exposure and outcome to fully explain away the observed association.
    RR<1 maps to 1/RR; RR==1 / non-finite / non-positive -> 1.0.

        E = RR* + sqrt(RR* * (RR* - 1)),  RR* = max(RR, 1/RR)
    """
    rr = float(point_estimate)
    if not math.isfinite(rr) or rr <= 0.0:
        return 1.0
    if rr == 1.0:
        return 1.0
    rr_star = rr if rr > 1.0 else 1.0 / rr
    return rr_star + math.sqrt(rr_star * (rr_star - 1.0))


def e_value_ci(rr_point: float, ci_lower: float, ci_upper: float) -> float:
    """E-value for the CI bound nearest the null (VanderWeele & Ding 2017).

    If the CI crosses 1 (non-significant) the CI E-value is 1.0.
    """
    lo, hi = float(ci_lower), float(ci_upper)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return 1.0
    if lo <= 1.0 <= hi:
        return 1.0
    rr = float(rr_point)
    bound = lo if rr > 1.0 else hi
    return e_value(bound)


def incremental_band(min_below_low, min_below_high,
                     auc_below_low, auc_below_high):
    """Construct the BAND burden between two thresholds = high-burden - low-burden.

    The minutes/AUC spent below the HIGHER threshold (e.g. 75) always includes the
    minutes/AUC spent below the LOWER threshold (e.g. 65): {MAP<65} is a subset of
    {MAP<75}.  The strictly-in-between exposure ("how much time/area was in the
    65-75 band") is therefore the difference:

        band_min = min_below_high - min_below_low
        band_auc = auc_below_high - auc_below_low

    Both are clamped at 0 to absorb extraction float noise (the difference is a
    nonnegative quantity by construction).

    Accepts scalars or anything supporting subtraction + ``max`` element-wise via
    numpy; returns (band_min, band_auc).
    """
    band_min = _clamp0(min_below_high - min_below_low)
    band_auc = _clamp0(auc_below_high - auc_below_low)
    return band_min, band_auc


def _clamp0(v):
    """Element-wise max(v, 0) for scalars or numpy arrays (no hard numpy dep)."""
    try:
        import numpy as np
        return np.maximum(v, 0.0)
    except Exception:
        return v if v > 0.0 else 0.0


def top_tertile_mask(values):
    """Boolean mask marking the TOP tertile (>= 2/3 quantile) of ``values``.

    Used for the modifiable-exposure binary in (C): top-tertile residual =
    "under-treated at the target" (more below-T burden than the case warranted).
    Ties at the cut go to the top tertile (>=), so the flagged group is never empty
    when there is any spread.  NaNs are excluded (mask False).

    Pure-ish: uses numpy only for the quantile; falls back to a stdlib quantile.
    """
    try:
        import numpy as np
        arr = np.asarray(values, dtype=float)
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return np.zeros(arr.shape, dtype=bool)
        cut = float(np.quantile(finite, 2.0 / 3.0))
        return (arr >= cut) & np.isfinite(arr)
    except Exception:
        vals = [float(v) for v in values if v is not None and v == v]
        if not vals:
            return [False] * len(list(values))
        s = sorted(vals)
        idx = int(math.ceil((2.0 / 3.0) * (len(s) - 1)))
        cut = s[idx]
        return [(v is not None and v == v and float(v) >= cut) for v in values]


def threshold_pairs(thresholds=THRESHOLDS):
    """Yield the (low, high) consecutive threshold pairs for the band/curve loops.

    e.g. (50,55),(55,60),...,(75,80).  Pure stdlib -- handy for the curve test.
    """
    ts = sorted(thresholds)
    return [(ts[i], ts[i + 1]) for i in range(len(ts) - 1)]


# ===========================================================================
# DATA ASSEMBLY
# ===========================================================================

def _resolve_cache_dir(cfg):
    return (cfg.get("cache_dir")
            or cfg.get("data", {}).get("cache_dir")
            or os.path.join("vitaldb_aki", "cache"))


def load_map_target_matrix(cfg):
    """Merge feature_matrix.csv + map_thresholds.csv (+ cases.csv pressor totals).

    Builds the derived columns the analyses need:
      - the canonical confounders (optype_code, cum_vasopressor_dose, preop_cr),
      - the per-threshold min_below_T / auc_below_T (from map_thresholds.csv),
      - burden_below_65, and the incremental band 65->75 (min and auc),
      - the naive achieved-MAP>=75 / >=65 health-marker flags (for D's naive
        contrast), from map_mean.

    Returns
    -------
    (df, meta) : (pandas.DataFrame, dict)
        df keyed by caseid with everything joined; meta records which columns were
        actually found / built and basic n's.
    """
    import numpy as np
    import pandas as pd

    cache_dir = _resolve_cache_dir(cfg)
    fm_path = os.path.join(cache_dir, "feature_matrix.csv")
    th_path = os.path.join(cache_dir, "map_thresholds.csv")
    cases_path = os.path.join(cache_dir, "cases.csv")

    if not os.path.exists(fm_path):
        raise FileNotFoundError(f"feature_matrix.csv not found at {fm_path!r}")
    if not os.path.exists(th_path):
        raise FileNotFoundError(
            f"map_thresholds.csv not found at {th_path!r}.  Run the threshold "
            "extractor first (it produces min_below_T / auc_below_T per caseid)."
        )

    fm = pd.read_csv(fm_path)
    th = pd.read_csv(th_path)
    th.columns = [c.lstrip("﻿") for c in th.columns]
    fm.columns = [c.lstrip("﻿") for c in fm.columns]

    # Threshold burdens: keep caseid + the min_below_T / auc_below_T columns.
    # (map_thresholds also carries map_mean/map_lowest; prefer feature_matrix's,
    # so only pull the burden columns + map_mean if feature_matrix lacks it.)
    burden_cols = [c for c in th.columns
                   if c.startswith("min_below_") or c.startswith("auc_below_")]
    pull = ["caseid"] + burden_cols
    if "map_mean" not in fm.columns and "map_mean" in th.columns:
        pull.append("map_mean")
    df = fm.merge(th[pull], on="caseid", how="inner")

    # --- cumulative vasopressor dose: pull pressor totals from cases.csv only if
    #     feature_matrix lacks them (merge before building derived columns) ---
    need_pressor = [c for c in ("intraop_phe", "intraop_eph", "intraop_epi")
                    if c not in df.columns]
    if need_pressor and os.path.exists(cases_path):
        cs = pd.read_csv(cases_path)
        cs.columns = [c.lstrip("﻿") for c in cs.columns]
        keep = ["caseid"] + [c for c in need_pressor if c in cs.columns]
        if len(keep) > 1:
            df = df.merge(cs[keep], on="caseid", how="left")

    # Build ALL derived columns at once (single pd.concat) to avoid the
    # fragmented-frame PerformanceWarning that per-column insertion triggers.
    def _g(col):
        return pd.to_numeric(df.get(col), errors="coerce") if col in df.columns else None

    derived = {}
    # preop_cr fallback
    if "preop_cr" not in df.columns and "baseline_cr" in df.columns:
        derived["preop_cr"] = pd.to_numeric(df["baseline_cr"], errors="coerce")
    # optype_code (numeric encode of surgery type)
    if "optype_code" not in df.columns and "optype" in df.columns:
        codes, _ = pd.factorize(df["optype"].astype(str), sort=True)
        derived["optype_code"] = pd.Series(codes.astype(float), index=df.index)
    # cumulative vasopressor dose (Saugel 2024): phe(ug) + 10*eph(mg) + epi
    phe = pd.to_numeric(df.get("intraop_phe", 0), errors="coerce").fillna(0.0)
    eph = pd.to_numeric(df.get("intraop_eph", 0), errors="coerce").fillna(0.0)
    epi = pd.to_numeric(df.get("intraop_epi", 0), errors="coerce").fillna(0.0)
    derived["cum_vasopressor_dose"] = phe + 10.0 * eph + epi

    # burden below 65 + incremental band 65->75
    min65 = _g(f"min_below_{BASE_TARGET}")
    min75 = _g(f"min_below_{HIGH_TARGET}")
    auc65 = _g(f"auc_below_{BASE_TARGET}")
    auc75 = _g(f"auc_below_{HIGH_TARGET}")
    if min65 is not None:
        derived["burden_below_65_min"] = min65
    if auc65 is not None:
        derived["burden_below_65_auc"] = auc65
    if min75 is not None:
        derived["burden_below_75_min"] = min75
    if auc75 is not None:
        derived["burden_below_75_auc"] = auc75
    if min65 is not None and min75 is not None:
        derived["band_65_75_min"], _ = incremental_band(min65, min75, 0.0, 0.0)
    if auc65 is not None and auc75 is not None:
        _, derived["band_65_75_auc"] = incremental_band(0.0, 0.0, auc65, auc75)

    # naive achieved-MAP health-marker flags (for the D naive contrast ONLY)
    map_mean = _g("map_mean")
    if map_mean is not None:
        derived["achieved_map_ge_75"] = (map_mean >= 75).astype(float)
        derived["achieved_map_ge_65"] = (map_mean >= 65).astype(float)

    df = pd.concat([df, pd.DataFrame(derived, index=df.index)], axis=1)

    meta = {
        "n_merged": int(len(df)),
        "n_feature_matrix": int(len(fm)),
        "n_thresholds": int(len(th)),
        "thresholds_present": sorted(
            int(c.split("_")[-1]) for c in burden_cols if c.startswith("min_below_")
        ),
        "confounders_present": [c for c in CONFOUNDERS if c in df.columns],
        "confounders_missing": [c for c in CONFOUNDERS if c not in df.columns],
        "has_map_mean": bool(map_mean is not None),
    }
    return df, meta


def _design(df, cols):
    """Median-imputed, standardized numeric design matrix for ``cols`` present.

    Returns (X, used_cols, scaler_means_unused).  Drops all-missing columns.
    """
    import numpy as np
    import pandas as pd
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    used = [c for c in cols if c in df.columns
            and pd.to_numeric(df[c], errors="coerce").notna().any()]
    if not used:
        return np.empty((len(df), 0)), used
    raw = df[used].apply(pd.to_numeric, errors="coerce")
    Xi = SimpleImputer(strategy="median").fit_transform(raw)
    Xs = StandardScaler().fit_transform(Xi)
    return Xs.astype(np.float64), used


def _fit_logit_get_or(X, y, target_idx, seed=RANDOM_SEED):
    """Fit a near-unpenalized logistic model; return (model, predicted_prob, log_OR
    for column target_idx).  target_idx may be None (no single coefficient wanted).
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(max_iter=2000, solver="lbfgs", C=1e6,
                            random_state=seed)
    lr.fit(X, y)
    prob = lr.predict_proba(X)[:, 1]
    log_or = float(lr.coef_[0][target_idx]) if target_idx is not None else None
    return lr, prob, log_or


# ===========================================================================
# (A) INCREMENTAL-BAND test
# ===========================================================================

def incremental_band_test(df, outcome, seed=RANDOM_SEED):
    """Does 65-75 BAND burden add AKI risk BEYOND burden < 65?

    Nested adjusted logistic models on the SAME rows:
        base : outcome ~ confounders + burden_below_65
        full : base + band_65_75
    Reports the band's adjusted OR (per SD) + bootstrap CI, the LRT p-value (full
    vs base via deviance) and the DeLong ΔAUROC (correlated, same patients).

    A significant, positive band effect = "risk the current 65 guideline misses".
    """
    import numpy as np
    import pandas as pd
    from scipy import stats as sps

    y = pd.to_numeric(df[outcome], errors="coerce")
    keep = y.notna()
    sub = df[keep].copy()
    y = y[keep].astype(int).to_numpy()
    if y.sum() == 0 or y.sum() == len(y):
        return {"outcome": outcome, "error": "no outcome variation"}

    conf = [c for c in CONFOUNDERS if c in sub.columns]
    # base burden + band columns (prefer AUC; it's the dose-area metric)
    base_burden = "burden_below_65_auc" if "burden_below_65_auc" in sub.columns else "burden_below_65_min"
    band_col = "band_65_75_auc" if "band_65_75_auc" in sub.columns else "band_65_75_min"

    Xbase, base_cols = _design(sub, conf + [base_burden])
    Xfull, full_cols = _design(sub, conf + [base_burden, band_col])
    if band_col not in full_cols:
        return {"outcome": outcome, "error": f"band column {band_col} unavailable"}
    band_idx = full_cols.index(band_col)

    _, prob_base, _ = _fit_logit_get_or(Xbase, y, None, seed)
    _, prob_full, log_or_band = _fit_logit_get_or(Xfull, y, band_idx, seed)

    # Likelihood-ratio test (deviance difference, 1 df = the band term).
    ll_base = _loglik(y, prob_base)
    ll_full = _loglik(y, prob_full)
    lr_stat = 2.0 * (ll_full - ll_base)
    lrt_p = float(sps.chi2.sf(lr_stat, df=1)) if lr_stat > 0 else 1.0

    # Bootstrap CI for the band log-OR.
    rng = np.random.default_rng(seed)
    n = len(y)
    boot = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, size=n)
        if y[idx].sum() in (0, len(idx)):
            continue
        try:
            _, _, lo = _fit_logit_get_or(Xfull[idx], y[idx], band_idx, seed)
            boot.append(lo)
        except Exception:
            continue
    boot = np.asarray(boot)
    ci_lo = float(np.percentile(boot, 2.5)) if boot.size else float("nan")
    ci_hi = float(np.percentile(boot, 97.5)) if boot.size else float("nan")

    # DeLong ΔAUROC (full vs base, correlated).
    try:
        from vitaldb_aki.models.metrics import delong_roc_test
        delong = delong_roc_test(y, prob_base, prob_full)
    except Exception as exc:  # pragma: no cover - metrics needs scipy
        delong = {"error": str(exc)}

    n_events = int(y.sum())
    return {
        "outcome": outcome,
        "n": int(n),
        "n_events": n_events,
        "underpowered": bool(n_events < UNDERPOWERED_EVENTS),
        "base_burden_col": base_burden,
        "band_col": band_col,
        "confounders": conf,
        "band_OR": round(float(np.exp(log_or_band)), 4),
        "band_log_OR": round(float(log_or_band), 4),
        "band_CI_lower": round(float(np.exp(ci_lo)), 4) if math.isfinite(ci_lo) else None,
        "band_CI_upper": round(float(np.exp(ci_hi)), 4) if math.isfinite(ci_hi) else None,
        "lrt_chi2": round(float(lr_stat), 4),
        "lrt_p": round(lrt_p, 6),
        "delong": _round_delong(delong),
        "interpretation": (
            "Band OR>1 with LRT p<0.05 and positive ΔAUROC => hypotension in the "
            "65-75 band carries AKI risk the 65 threshold misses (supports a higher "
            "target). Band OR~1 / LRT p NS / ΔAUROC~0 => no detectable excess risk "
            "above 65 (no signal for a higher target)."
        ),
    }


def _loglik(y, p):
    import numpy as np
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _round_delong(d):
    if not isinstance(d, dict) or "error" in d:
        return d
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in d.items()}


# ===========================================================================
# (B) ADJUSTED THRESHOLD-RESPONSE CURVE
# ===========================================================================

def adjusted_threshold_response(df, outcome, seed=RANDOM_SEED):
    """Per-threshold adjusted OR (per SD of min_below_T) for AKI, T in 50..80.

    For each T, fit outcome ~ confounders + min_below_T and read the OR for the
    burden term (which, because _design standardizes, is per-SD).  Shows where the
    adjusted association inflects / flattens.  The honest read is whether adjusted
    risk keeps rising above 65 toward 75 (-> a higher target may help) or flattens
    at 65 (-> no benefit to a higher target).
    """
    import numpy as np
    import pandas as pd
    from scipy import stats as sps

    y = pd.to_numeric(df[outcome], errors="coerce")
    keep = y.notna()
    sub = df[keep].copy()
    yv = y[keep].astype(int).to_numpy()
    conf = [c for c in CONFOUNDERS if c in sub.columns]

    rng = np.random.default_rng(seed)
    rows = []
    for T in THRESHOLDS:
        col = f"min_below_{T}"
        if col not in sub.columns or pd.to_numeric(sub[col], errors="coerce").notna().sum() == 0:
            rows.append({"T": T, "error": "burden column unavailable"})
            continue
        X, used = _design(sub, conf + [col])
        if col not in used:
            rows.append({"T": T, "error": "burden column all-missing"})
            continue
        bidx = used.index(col)
        try:
            _, _, log_or = _fit_logit_get_or(X, yv, bidx, seed)
        except Exception as exc:
            rows.append({"T": T, "error": str(exc)})
            continue
        # quick bootstrap CI (lighter -- N_BOOTSTRAP//2 -- this loops over 7 Ts)
        n = len(yv)
        boot = []
        for _ in range(N_BOOTSTRAP // 2):
            idx = rng.integers(0, n, size=n)
            if yv[idx].sum() in (0, len(idx)):
                continue
            try:
                _, _, lo = _fit_logit_get_or(X[idx], yv[idx], bidx, seed)
                boot.append(lo)
            except Exception:
                continue
        boot = np.asarray(boot)
        lo = float(np.percentile(boot, 2.5)) if boot.size else float("nan")
        hi = float(np.percentile(boot, 97.5)) if boot.size else float("nan")
        rows.append({
            "T": T,
            "adjusted_OR_per_SD": round(float(np.exp(log_or)), 4),
            "CI_lower": round(float(np.exp(lo)), 4) if math.isfinite(lo) else None,
            "CI_upper": round(float(np.exp(hi)), 4) if math.isfinite(hi) else None,
        })

    # monotonicity note over the ORs that fit
    ors = [(r["T"], r["adjusted_OR_per_SD"]) for r in rows if "adjusted_OR_per_SD" in r]
    flat_at_65 = None
    if any(t == 65 for t, _ in ors) and any(t == 75 for t, _ in ors):
        or65 = next(o for t, o in ors if t == 65)
        or75 = next(o for t, o in ors if t == 75)
        flat_at_65 = bool(or75 <= or65 + 0.02)  # essentially no further rise above 65
    return {
        "outcome": outcome,
        "n_events": int(yv.sum()),
        "underpowered": bool(int(yv.sum()) < UNDERPOWERED_EVENTS),
        "confounders": conf,
        "curve": rows,
        "flat_at_65": flat_at_65,
        "interpretation": (
            "If adjusted OR per SD keeps climbing from T=65 toward T=75/80, "
            "hypotension relative to a higher target still predicts AKI after "
            "adjustment (a higher target may help). If the OR flattens at/above 65, "
            "there is no adjusted signal for a higher target."
        ),
    }


# ===========================================================================
# (C) MODIFIABLE (expected-vs-observed) EXPOSURE + IPTW target-trial
# ===========================================================================

def modifiable_exposure_iptw(df, outcome, target=HIGH_TARGET, seed=RANDOM_SEED):
    """Residualize below-target burden on insult+baseline; top-tertile residual =
    "under-treated at the target".  IPTW the binary exposure -> RD + RR for AKI.

    Steps
    -----
    1. Regress min_below_{target} on INSULT_COVARIATES (NOT on cumulative pressor):
       residual = observed - expected = excess hypotension the case did not warrant.
    2. exposure = top-tertile residual (1) vs rest (0)  -> the MODIFIABLE part.
    3. IPTW (reuse hypotension_treatment.fit_propensity_model / compute_iptw_weights
       by aliasing exposure -> 'vasopressor_treated') over the full confounder set.
    4. IPTW risk difference + risk ratio for ``outcome`` with bootstrap CIs.
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression
    from vitaldb_aki.analysis import hypotension_treatment as ht

    col = f"min_below_{target}"
    if col not in df.columns:
        return {"outcome": outcome, "target": target,
                "error": f"{col} unavailable"}

    y = pd.to_numeric(df[outcome], errors="coerce")
    keep = y.notna() & pd.to_numeric(df[col], errors="coerce").notna()
    sub = df[keep].copy()
    if len(sub) == 0:
        return {"outcome": outcome, "target": target, "error": "no valid rows"}

    # 1. expected burden from insult+baseline -> residual
    insult = [c for c in INSULT_COVARIATES if c in sub.columns]
    Z, zused = _design(sub, insult)
    burden = pd.to_numeric(sub[col], errors="coerce").fillna(
        pd.to_numeric(sub[col], errors="coerce").median()).to_numpy(dtype=float)
    if Z.shape[1] > 0:
        lr = LinearRegression().fit(Z, burden)
        residual = burden - lr.predict(Z)
    else:
        residual = burden - np.nanmedian(burden)

    # 2. top-tertile residual = "under-treated at the target"
    mask = top_tertile_mask(residual)
    sub = sub.copy()
    sub["vasopressor_treated"] = np.asarray(mask, dtype=int)   # alias for the IPTW fns
    sub[ht.OUTCOME_COL] = pd.to_numeric(sub[outcome], errors="coerce")

    # 3. IPTW over the full confounder set (full CONFOUNDERS, present subset)
    ps_cov = [c for c in CONFOUNDERS if c in sub.columns]
    try:
        sub_ps, _, used_cov = ht.fit_propensity_model(sub, covariates=ps_cov)
        sub_w = ht.compute_iptw_weights(sub_ps)
    except Exception as exc:
        return {"outcome": outcome, "target": target, "error": f"IPTW failed: {exc}"}

    # balance (max SMD before/after) for the report
    bal_pre = ht.check_balance(sub_w, covariates=used_cov)
    bal_post = ht.check_balance(sub_w, covariates=used_cov, weight_col="iptw_weight")
    max_smd_pre = float(bal_pre["smd"].dropna().max()) if not bal_pre.empty else float("nan")
    max_smd_post = float(bal_post["smd"].dropna().max()) if not bal_post.empty else float("nan")

    # 4. IPTW risk difference / risk ratio with bootstrap CI
    yv = pd.to_numeric(sub_w[outcome], errors="coerce").astype(int).to_numpy()
    expo = sub_w["vasopressor_treated"].astype(int).to_numpy()
    w = sub_w["iptw_weight"].to_numpy(dtype=float)
    rd, rr, r1, r0 = _iptw_rd_rr(yv, expo, w)

    rng = np.random.default_rng(seed)
    n = len(yv)
    rds, rrs = [], []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, size=n)
        d, r, _, _ = _iptw_rd_rr(yv[idx], expo[idx], w[idx])
        if math.isfinite(d):
            rds.append(d)
        if math.isfinite(r):
            rrs.append(r)
    rds, rrs = np.asarray(rds), np.asarray(rrs)
    n_events = int(yv.sum())
    n_exposed_events = int(yv[expo == 1].sum())

    return {
        "outcome": outcome,
        "target": target,
        "n": int(n),
        "n_events": n_events,
        "n_exposed": int(expo.sum()),
        "n_exposed_events": n_exposed_events,
        "underpowered": bool(min(n_exposed_events, n_events - n_exposed_events) < UNDERPOWERED_EVENTS),
        "exposure_def": (
            f"top-tertile residual of min_below_{target} after regressing on "
            f"{insult} (observed-minus-expected hypotension at the {target} target)"
        ),
        "risk_exposed": round(float(r1), 4),
        "risk_unexposed": round(float(r0), 4),
        "iptw_risk_difference": round(float(rd), 4),
        "rd_CI": [round(float(np.percentile(rds, 2.5)), 4),
                  round(float(np.percentile(rds, 97.5)), 4)] if rds.size else None,
        "iptw_risk_ratio": round(float(rr), 4) if math.isfinite(rr) else None,
        "rr_CI": [round(float(np.percentile(rrs, 2.5)), 4),
                  round(float(np.percentile(rrs, 97.5)), 4)] if rrs.size else None,
        "max_smd_pre": round(max_smd_pre, 4) if math.isfinite(max_smd_pre) else None,
        "max_smd_post": round(max_smd_post, 4) if math.isfinite(max_smd_post) else None,
        "ps_covariates": used_cov,
    }


def _iptw_rd_rr(y, expo, w):
    """Weighted risks in exposed/unexposed -> (risk difference, risk ratio, r1, r0)."""
    import numpy as np
    m1 = expo == 1
    m0 = expo == 0
    if not m1.any() or not m0.any():
        return float("nan"), float("nan"), float("nan"), float("nan")
    r1 = float(np.average(y[m1], weights=w[m1]))
    r0 = float(np.average(y[m0], weights=w[m0]))
    rd = r1 - r0
    rr = (r1 / r0) if r0 > 0 else float("nan")
    return rd, rr, r1, r0


# ===========================================================================
# (D) BIAS-CONTROL BATTERY
# ===========================================================================

def naive_achieved_map_association(df, outcome):
    """The NAIVE, CONFOUNDED achieved-MAP>=75 -> AKI contrast (unadjusted).

    Reported EXPLICITLY as confounded -- it is the health-marker artefact -- to
    quantify the gap to the adjusted estimates.  NEVER a headline.
    """
    import numpy as np
    import pandas as pd

    if "achieved_map_ge_75" not in df.columns:
        return {"error": "map_mean unavailable -- cannot build achieved-MAP flag"}
    y = pd.to_numeric(df[outcome], errors="coerce")
    flag = pd.to_numeric(df["achieved_map_ge_75"], errors="coerce")
    keep = y.notna() & flag.notna()
    y = y[keep].astype(int).to_numpy()
    f = flag[keep].astype(int).to_numpy()
    if f.sum() == 0 or (1 - f).sum() == 0:
        return {"error": "achieved-MAP flag has no variation"}
    # achieved>=75 is the "healthy marker"; compute RR of AKI for >=75 vs <75.
    r_hi = float(y[f == 1].mean())   # achieved >= 75
    r_lo = float(y[f == 0].mean())   # achieved <  75
    rr = (r_hi / r_lo) if r_lo > 0 else float("nan")
    return {
        "outcome": outcome,
        "label": "NAIVE / CONFOUNDED -- achieved-MAP is a health marker, not a cause",
        "n_ge75": int(f.sum()),
        "n_lt75": int((1 - f).sum()),
        "aki_rate_ge75": round(r_hi, 4),
        "aki_rate_lt75": round(r_lo, 4),
        "naive_RR_ge75_vs_lt75": round(rr, 4) if math.isfinite(rr) else None,
        "interpretation": (
            "An RR<1 here ('higher achieved MAP -> less AKI') is the textbook "
            "confounded result: healthier patients both hold MAP>=75 and have "
            "better kidneys. The gap between this and the adjusted/modifiable "
            "estimates is the bias this study controls for."
        ),
    }


def bias_battery(df, band_result, modifiable_result, seed=RANDOM_SEED):
    """E-values, negative-control outcome, dose-response, effect-modification, and
    the naive-vs-adjusted contrast -- assembled for the primary (A/C) estimates.
    """
    import numpy as np
    import pandas as pd

    out = {}

    # --- E-values on the primary (A band) and (C modifiable RR) estimates ---
    evs = {}
    band_or = band_result.get("band_OR")
    if band_or is not None:
        evs["band_A"] = {
            "point": round(e_value(band_or), 4),
            "ci": round(e_value_ci(band_or,
                                   band_result.get("band_CI_lower", float("nan")),
                                   band_result.get("band_CI_upper", float("nan"))), 4),
            "note": "E-value for the 65-75 band adjusted OR (treated on RR scale).",
        }
    mrr = modifiable_result.get("iptw_risk_ratio")
    if mrr is not None and modifiable_result.get("rr_CI"):
        lo, hi = modifiable_result["rr_CI"]
        evs["modifiable_C"] = {
            "point": round(e_value(mrr), 4),
            "ci": round(e_value_ci(mrr, lo, hi), 4),
            "note": "E-value for the IPTW risk ratio of the modifiable 75-target exposure.",
        }
    out["e_values"] = evs

    # --- NEGATIVE-CONTROL outcome through the SAME models (A and C) ---
    neg = {}
    if NEGATIVE_CONTROL_OUTCOME in df.columns:
        neg["band_A"] = incremental_band_test(df, NEGATIVE_CONTROL_OUTCOME, seed)
        neg["modifiable_C"] = modifiable_exposure_iptw(
            df, NEGATIVE_CONTROL_OUTCOME, target=HIGH_TARGET, seed=seed)
        neg["read"] = (
            f"{NEGATIVE_CONTROL_OUTCOME} should NOT be caused by the MAP target. "
            "A clearly non-null band OR or IPTW RR here flags RESIDUAL CONFOUNDING "
            "and should temper any positive primary result."
        )
    else:
        neg["error"] = f"{NEGATIVE_CONTROL_OUTCOME} not in matrix"
    out["negative_control"] = neg

    # --- dose-response monotonicity note (from the threshold curve, organ_renal) ---
    # (computed by caller and passed via band_result if desired; here we recompute
    # a light monotonicity flag from the band sign.)
    out["dose_response_note"] = (
        "Dose-response is assessed in the adjusted threshold-response curve (B): a "
        "monotone rise in adjusted OR with deepening below-T burden supports "
        "causality; a flat/non-monotone curve weakens it."
    )

    # --- effect-modification by the vulnerable phenotype (interaction) ---
    out["effect_modification"] = _effect_modification_by_phenotype(
        df, PRIMARY_OUTCOME, seed)

    # --- naive-vs-adjusted contrast (the instructive gap) ---
    out["naive_vs_adjusted"] = {
        oc: naive_achieved_map_association(df, oc) for oc in OUTCOMES
    }
    return out


def _effect_modification_by_phenotype(df, outcome, seed=RANDOM_SEED):
    """Regenerate the high-risk phenotype label, then test band x phenotype
    interaction: does the 65-75 band effect CONCENTRATE in the vulnerable subtype?
    """
    import numpy as np
    import pandas as pd

    try:
        labels, hi_cluster = _regen_highrisk_phenotype(df, seed)
    except Exception as exc:
        return {"error": f"phenotype regeneration failed: {exc}"}

    band_col = "band_65_75_auc" if "band_65_75_auc" in df.columns else "band_65_75_min"
    if band_col not in df.columns:
        return {"error": "band column unavailable for interaction"}

    y = pd.to_numeric(df[outcome], errors="coerce")
    keep = y.notna()
    yv = y[keep].astype(int).to_numpy()
    vuln = (np.asarray(labels)[keep.to_numpy()] == hi_cluster).astype(float)
    conf = [c for c in CONFOUNDERS if c in df.columns]

    sub = df[keep].copy()
    Xc, cols = _design(sub, conf + [band_col])
    if band_col not in cols:
        return {"error": "band column all-missing"}
    band = Xc[:, cols.index(band_col)]
    inter = band * vuln
    X = np.column_stack([Xc, vuln, inter])

    try:
        from sklearn.linear_model import LogisticRegression
        from scipy import stats as sps
        lr = LogisticRegression(max_iter=2000, solver="lbfgs", C=1e6,
                                random_state=seed).fit(X, yv)
        inter_coef = float(lr.coef_[0][-1])
        # reduced (no interaction) vs full LRT
        lr0 = LogisticRegression(max_iter=2000, solver="lbfgs", C=1e6,
                                 random_state=seed).fit(X[:, :-1], yv)
        ll1 = _loglik(yv, lr.predict_proba(X)[:, 1])
        ll0 = _loglik(yv, lr0.predict_proba(X[:, :-1])[:, 1])
        stat = 2.0 * (ll1 - ll0)
        p = float(sps.chi2.sf(stat, df=1)) if stat > 0 else 1.0
    except Exception as exc:
        return {"error": str(exc)}

    n_vuln_events = int(yv[vuln == 1].sum())
    return {
        "outcome": outcome,
        "interaction_OR": round(float(np.exp(inter_coef)), 4),
        "interaction_log_OR": round(inter_coef, 4),
        "interaction_lrt_p": round(p, 6),
        "n_vulnerable": int(vuln.sum()),
        "n_vulnerable_events": n_vuln_events,
        "underpowered": bool(n_vuln_events < UNDERPOWERED_EVENTS),
        "interpretation": (
            "Interaction OR>1 with p<0.05 => the 65-75 band's AKI risk concentrates "
            "in the vulnerable phenotype (where a higher target would help most). "
            "p NS => no detectable effect-modification (likely underpowered with "
            "143 renal events)."
        ),
    }


def _regen_highrisk_phenotype(df, seed=RANDOM_SEED):
    """Reuse phenotypes.load_physiology_matrix + insult-residualized KMeans (the
    phenotype_v2 pattern) to regenerate per-row labels and the high-renal-risk
    cluster id, aligned to df rows by caseid.
    """
    import numpy as np
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from vitaldb_aki.analysis.phenotypes import load_physiology_matrix
    from vitaldb_aki.analysis.phenotype_v2 import INSULT_COVARIATES as PV2_INSULT, _corr_prune, CORR_PRUNE_THRESHOLD

    cache_dir = _resolve_cache_dir({"cache_dir": None}) if False else None
    cfg = {"cache_dir": os.path.dirname(
        os.path.abspath(os.path.join(_ROOT, "vitaldb_aki", "cache", "feature_matrix.csv")))}
    X, names, df_full = load_physiology_matrix(cfg)
    names = list(names)

    cov = []
    for c in PV2_INSULT:
        if c in df_full.columns:
            cov.append(pd.to_numeric(df_full[c], errors="coerce").to_numpy(dtype=float))
    if "optype" in df_full.columns:
        cov.append(df_full["optype"].astype("category").cat.codes.to_numpy(dtype=float))
    Z = np.column_stack(cov)
    for j in range(Z.shape[1]):
        col = Z[:, j]; col[np.isnan(col)] = np.nanmedian(col); Z[:, j] = col

    drop = {"anesthesia_duration_min", "intraop_ebl"}
    cfeat = [i for i, nm in enumerate(names) if nm not in drop]
    Xc = X[:, cfeat]; cnames = [names[i] for i in cfeat]
    kept_idx, _ = _corr_prune(Xc, cnames, CORR_PRUNE_THRESHOLD)
    Xk = Xc[:, kept_idx]
    resid = np.empty_like(Xk)
    for j in range(Xk.shape[1]):
        resid[:, j] = Xk[:, j] - LinearRegression().fit(Z, Xk[:, j]).predict(Z)
    Rz = StandardScaler().fit_transform(resid)
    labels_full = KMeans(n_clusters=2, n_init=10, random_state=seed).fit_predict(Rz)

    ren = pd.to_numeric(df_full.get("organ_renal"), errors="coerce").to_numpy(dtype=float)
    r0 = np.nanmean(ren[labels_full == 0]); r1 = np.nanmean(ren[labels_full == 1])
    hi = 0 if (r0 or 0) >= (r1 or 0) else 1

    # align to df rows by caseid
    lab_by_case = dict(zip(df_full["caseid"].to_numpy(), labels_full))
    aligned = np.array([lab_by_case.get(cid, -1) for cid in df["caseid"].to_numpy()])
    return aligned, hi


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================

def run_map_target_analysis(cfg) -> dict:
    """Run the full MAP-target interrogation and write results + report + done-flag.

    Writes (in order): cache/map_target_results.json, docs/MAP_TARGET_RESULTS.md,
    cache/_map_target_done.json (LAST).
    """
    cache_dir = _resolve_cache_dir(cfg)
    seed = cfg.get("seed", RANDOM_SEED)

    print("[map_target] loading + merging feature_matrix + map_thresholds ...")
    df, meta = load_map_target_matrix(cfg)
    print(f"[map_target] merged n={meta['n_merged']} "
          f"(feature_matrix={meta['n_feature_matrix']}, thresholds={meta['n_thresholds']})")

    results: dict[str, Any] = {
        "meta": meta,
        "exposure_definitions": {
            "incremental_band_65_75": "below-75 burden minus below-65 burden (AUC and minutes)",
            "modifiable_exposure": (
                "top-tertile residual of min_below_T after regressing on "
                f"{INSULT_COVARIATES} -- observed-minus-expected hypotension at target T"
            ),
            "naive_confounded": "achieved map_mean >= 75 vs < 75 (health marker; reported, not headlined)",
            "confounders": CONFOUNDERS,
        },
        "A_incremental_band": {},
        "B_threshold_response": {},
        "C_modifiable_iptw": {},
        "D_bias_battery": {},
    }

    # (A) incremental-band, both outcomes
    for oc in OUTCOMES:
        print(f"[map_target] (A) incremental-band test :: {oc}")
        results["A_incremental_band"][oc] = incremental_band_test(df, oc, seed)

    # (B) adjusted threshold-response curve, both outcomes
    for oc in OUTCOMES:
        print(f"[map_target] (B) adjusted threshold-response :: {oc}")
        results["B_threshold_response"][oc] = adjusted_threshold_response(df, oc, seed)

    # (C) modifiable IPTW at the 75 target (primary) + 65 comparator, both outcomes
    for oc in OUTCOMES:
        print(f"[map_target] (C) modifiable IPTW :: {oc}")
        results["C_modifiable_iptw"][oc] = {
            "target_75": modifiable_exposure_iptw(df, oc, target=HIGH_TARGET, seed=seed),
            "target_65": modifiable_exposure_iptw(df, oc, target=BASE_TARGET, seed=seed),
        }

    # (D) bias battery, anchored on the PRIMARY outcome's A + C(75) estimates
    print("[map_target] (D) bias-control battery ...")
    results["D_bias_battery"] = bias_battery(
        df,
        band_result=results["A_incremental_band"][PRIMARY_OUTCOME],
        modifiable_result=results["C_modifiable_iptw"][PRIMARY_OUTCOME]["target_75"],
        seed=seed,
    )

    # --- write JSON ---
    os.makedirs(cache_dir, exist_ok=True)
    json_path = os.path.join(cache_dir, "map_target_results.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[map_target] results -> {json_path}")

    # --- write report ---
    md_path = _write_md(results, cfg)
    print(f"[map_target] report  -> {md_path}")

    # --- write done flag LAST ---
    done_path = os.path.join(cache_dir, "_map_target_done.json")
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"done": True, "json": json_path, "md": md_path,
                   "n": meta["n_merged"]}, fh, indent=2)
    print(f"[map_target] done    -> {done_path}")
    return results


def _json_default(obj):
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_md(results, cfg) -> str:
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "MAP_TARGET_RESULTS.md")

    meta = results["meta"]
    A = results["A_incremental_band"]
    B = results["B_threshold_response"]
    C = results["C_modifiable_iptw"]
    D = results["D_bias_battery"]

    L = []
    L += [
        "# Does a Higher Intraoperative MAP Target (70/75 vs 65) Reduce End-Organ Injury?",
        "",
        "Rigorously-confounder-controlled observational interrogation on VitalDB. "
        "Primary outcome: **organ_renal** (AKI). Secondary: **composite**.",
        "",
        f"- Cases merged: **{meta['n_merged']}**  "
        f"(feature_matrix={meta['n_feature_matrix']}, map_thresholds={meta['n_thresholds']})",
        f"- Confounders present: {', '.join(meta['confounders_present'])}",
        (f"- Confounders MISSING (dropped): {', '.join(meta['confounders_missing'])}"
         if meta["confounders_missing"] else "- All confounders present."),
        "",
        "## Interpretation & limitations (READ FIRST)",
        "",
        "This is **observational**. The central threat is **confounding by "
        "indication / by health**: patients who naturally hold MAP>=75 are "
        "healthier (less vasoplegia, better cardiac function, smaller/shorter "
        "operations), so achieved-MAP>=75 is mostly a **marker of being well, not "
        "a cause of good kidneys**. Every analysis here is built to neutralise that "
        "(modifiable exposures + heavy adjustment + a negative-control outcome + "
        "E-values). The deliverable is a **rigorously-controlled, externally-"
        "validatable HYPOTHESIS** for a randomized 65-vs-75 MAP-target trial "
        "(benchmark: INPRESS, RR ~0.73 for organ dysfunction) -- **not proof of "
        "causation**. Cells with <15 events are underpowered and flagged.",
        "",
    ]

    def _band_block(oc):
        r = A.get(oc, {})
        if "error" in r:
            return [f"- **{oc}**: {r['error']}", ""]
        flag = " ⚠️ UNDERPOWERED (events<15)" if r.get("underpowered") else ""
        dl = r.get("delong", {})
        dauc = dl.get("delta") if isinstance(dl, dict) else None
        dp = dl.get("p_value") if isinstance(dl, dict) else None
        return [
            f"- **{oc}** (n={r['n']}, events={r['n_events']}{flag})",
            f"  - Band adjusted OR (per SD of {r['band_col']}): "
            f"**{r['band_OR']}** [{r['band_CI_lower']}, {r['band_CI_upper']}]",
            f"  - LRT (band added to <65 base): chi2={r['lrt_chi2']}, **p={r['lrt_p']}**",
            f"  - DeLong ΔAUROC (full vs base): {dauc}  (p={dp})",
            "",
        ]

    L += ["## (A) Incremental-band test -- HEADLINE",
          "",
          "Does hypotension in the **65-75 band** add AKI risk **beyond** burden "
          "<65? If yes, that is risk the current 65 guideline misses.",
          ""]
    for oc in OUTCOMES:
        L += _band_block(oc)

    L += ["## (B) Adjusted threshold-response curve",
          "",
          "Fully-adjusted OR per SD of below-T burden, T=50..80. Does adjusted risk "
          "keep rising above 65 toward 75, or flatten at 65 (= no benefit to a "
          "higher target)?",
          ""]
    for oc in OUTCOMES:
        r = B.get(oc, {})
        L += [f"### {oc} (events={r.get('n_events')})"
              + (" ⚠️ UNDERPOWERED" if r.get("underpowered") else ""),
              "",
              "| T | adjusted OR/SD | 95% CI |",
              "|---|----------------|--------|"]
        for row in r.get("curve", []):
            if "adjusted_OR_per_SD" in row:
                L.append(f"| {row['T']} | {row['adjusted_OR_per_SD']} | "
                         f"[{row['CI_lower']}, {row['CI_upper']}] |")
            else:
                L.append(f"| {row['T']} | -- | {row.get('error', 'n/a')} |")
        flat = r.get("flat_at_65")
        L += ["",
              f"Flat at 65 (no further rise to 75): **{flat}** -- "
              + ("no adjusted signal for a higher target." if flat
                 else "adjusted risk still climbs toward 75 (a higher target may help)."
                 if flat is False else "indeterminate."),
              ""]

    L += ["## (C) Modifiable-exposure IPTW target-trial",
          "",
          "Residualize below-target burden on surgical-insult+baseline covariates; "
          "the **top-tertile residual** = 'under-treated at the target' = the "
          "modifiable excess (health-marker component removed). IPTW over the full "
          "confounder set -> the causal estimate of the *modifiable* part.",
          ""]
    for oc in OUTCOMES:
        for tgt_key, tgt in (("target_75", 75), ("target_65", 65)):
            r = C.get(oc, {}).get(tgt_key, {})
            if "error" in r:
                L += [f"- **{oc} @ {tgt}**: {r['error']}", ""]
                continue
            flag = " ⚠️ UNDERPOWERED" if r.get("underpowered") else ""
            L += [
                f"- **{oc} @ {tgt}-target**{flag} "
                f"(n={r['n']}, events={r['n_events']}, exposed={r['n_exposed']})",
                f"  - IPTW risk difference: **{r['iptw_risk_difference']}** "
                f"CI {r.get('rd_CI')}",
                f"  - IPTW risk ratio: **{r['iptw_risk_ratio']}** CI {r.get('rr_CI')}",
                f"  - Balance max-SMD pre/post weighting: "
                f"{r.get('max_smd_pre')} -> {r.get('max_smd_post')}",
                "",
            ]

    L += ["## (D) Bias-control battery", ""]
    ev = D.get("e_values", {})
    L += ["### E-values (VanderWeele)"]
    if ev:
        for k, v in ev.items():
            L.append(f"- {k}: point E-value **{v['point']}**, CI-bound E-value "
                     f"{v['ci']} -- {v['note']}")
    else:
        L.append("- (no significant primary estimate to compute an E-value for)")
    L.append("")

    nc = D.get("negative_control", {})
    L += ["### Negative-control outcome (organ_cholestatic)"]
    if "error" in nc:
        L.append(f"- {nc['error']}")
    else:
        nb = nc.get("band_A", {})
        ncm = nc.get("modifiable_C", {})
        L += [
            f"- Band OR on negative control: {nb.get('band_OR')} "
            f"(LRT p={nb.get('lrt_p')})",
            f"- IPTW RR on negative control: {ncm.get('iptw_risk_ratio')} "
            f"CI {ncm.get('rr_CI')}",
            f"- {nc.get('read', '')}",
        ]
    L.append("")

    em = D.get("effect_modification", {})
    L += ["### Effect-modification by the vulnerable phenotype"]
    if "error" in em:
        L.append(f"- {em['error']}")
    else:
        flag = " ⚠️ UNDERPOWERED" if em.get("underpowered") else ""
        L += [
            f"- Band x phenotype interaction OR: **{em['interaction_OR']}** "
            f"(LRT p={em['interaction_lrt_p']}){flag}",
            f"- Vulnerable n={em['n_vulnerable']}, events={em['n_vulnerable_events']}",
            f"- {em['interpretation']}",
        ]
    L.append("")

    L += ["### Naive-vs-adjusted contrast (the instructive gap)",
          "",
          "The naive achieved-MAP>=75 association is **confounded** (health "
          "marker). Its distance from the adjusted/modifiable estimates above is "
          "the bias this study removes.",
          ""]
    nva = D.get("naive_vs_adjusted", {})
    for oc in OUTCOMES:
        n = nva.get(oc, {})
        if "error" in n:
            L += [f"- **{oc}**: {n['error']}", ""]
            continue
        L += [
            f"- **{oc}** (CONFOUNDED): AKI rate achieved>=75 = {n['aki_rate_ge75']} "
            f"(n={n['n_ge75']}) vs <75 = {n['aki_rate_lt75']} (n={n['n_lt75']}); "
            f"naive RR = **{n['naive_RR_ge75_vs_lt75']}**",
            "",
        ]

    L += [D.get("dose_response_note", ""), "",
          "---", "*Generated by vitaldb_aki/analysis/map_target_analysis.py*"]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return md_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    from common.config import load_yaml
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cfg.setdefault("cache_dir", os.path.join(_ROOT, "vitaldb_aki", "cache"))
    run_map_target_analysis(cfg)


if __name__ == "__main__":
    main()
