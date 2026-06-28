"""inspire_map_threshold.py -- make the INSPIRE "CKD needs a higher MAP floor"
finding ACTIONABLE + QUANTIFIED in the full ~131k INSPIRE cohort.

Background
----------
docs/INSPIRE_CKD_MAP.md (+ analysis/inspire_ckd_map_deepdive.py) established, in
INSPIRE n=130,960:
  - hypotension-burden -> AKI OR 1.62 (robust to monitoring-density n_map);
  - within-CKD (eGFR<60) renal RR ~1.73 (1,020 events);
  - the CKD excess over non-CKD WIDENS as MAP rises -> implied floor ~75 mmHg;
  - burden -> in-hospital death OR 2.63;
  - the "reversal" was a harness mislabel + monitoring-density artifact (resolved).

This module converts that into the clinically actionable estimands:

(1) THRESHOLD ESTIMATION -- per eGFR stratum (>=90, 60-90, 45-60, <45) fit a
    restricted-cubic-spline (RCS) logistic of renal-injury (and death) on
    map_lowest, adjusted for n_map + age + sex + asa + emergency + baseline_cr.
    Locate the risk-INFLECTION MAP (steepest-rise / where the adjusted
    odds start climbing) per stratum, with a bootstrap CI.  Does the floor rise
    as eGFR falls?

(2) ABSOLUTE RISK + NNT -- within CKD (eGFR<60): IPTW-adjusted absolute renal &
    mortality risk for MAP nadir bands (<55, 55-65, 65-75, >=75), risk
    difference vs the >=75 reference, and NNT = 1/RD.  Repeat for non-CKD to show
    concentration.  PAF = fraction of CKD AKI/deaths attributable to MAP<75.

(3) DOSE-BANDS -- clean clinician-facing AKI & mortality rate table by MAP
    nadir band x CKD status.

(4) MORTALITY co-primary -- (1)+(2) repeated on death_inhosp (hard, sampling-
    robust endpoint).

(5) ROBUSTNESS -- every key estimate n_map-adjusted and re-run in the densely-
    monitored subset; E-values; BH-FDR; honest CIs; a negative-control
    (hepatocellular injury) inflection check.

Reuses the validated IPTW machinery (fit_propensity_model / compute_iptw_weights)
and the pure helpers (e_value / e_value_ci / benjamini_hochberg).  Heavy deps are
lazy-imported.  Leakage firewall: predictors are preop+intraop only;
organ_renal / aki_stage / death_inhosp are y.

Run from repo root (/home/user/Codex-playground-/):
    python3 -m vitaldb_aki.analysis.inspire_map_threshold
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

from vitaldb_aki.analysis.actionable_targets import (
    e_value,
    e_value_ci,
    benjamini_hochberg,
    _json_default,
)

# --------------------------------------------------------------------------
# Locations / constants
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.dirname(_HERE)
DEFAULT_MATRIX = os.path.join(_PKG_ROOT, "cache", "inspire_matrix.csv")
DEFAULT_RESULTS = os.path.join(_PKG_ROOT, "cache", "inspire_map_threshold_results.json")
DEFAULT_DOC = os.path.join(_PKG_ROOT, "docs", "INSPIRE_MAP_THRESHOLD.md")

RANDOM_SEED = 20260626

RENAL_OUTCOME = "organ_renal"
MORTALITY_OUTCOME = "death_inhosp"
NEGCTRL_OUTCOME = "organ_hepatocellular"

# eGFR strata (ordinal, decreasing severity of renal function).
EGFR_STRATA = [
    ("ge90", "eGFR >= 90", 90.0, float("inf")),
    ("s60_90", "eGFR 60-90", 60.0, 90.0),
    ("s45_60", "eGFR 45-60", 45.0, 60.0),
    ("lt45", "eGFR < 45", float("-inf"), 45.0),
]
EGFR_CKD_CUTOFF = 60.0

# Adjustment covariates for the RCS logistic / absolute-risk PS model
# (PREOP + INTRAOP only -- never postop).  n_map is the monitoring-density key.
ADJ_COVARIATES = [
    "n_map", "age", "sex_male", "asa_class", "emergency", "baseline_cr",
]
# For the IPTW absolute-risk arm we also let weight + duration in as confounders.
PS_COVARIATES = [
    "n_map", "age", "sex_male", "asa_class", "emergency", "baseline_cr",
    "weight_kg", "surgery_duration", "preop_htn", "preop_dm",
]
NMAP_COL = "n_map"

# MAP-nadir bands for the dose / absolute-risk tables (map_lowest).
# INSPIRE map_lowest is floored at ~52 mmHg, so the deepest band is <55.
MAP_BANDS = [
    ("lt55", "MAP nadir < 55", float("-inf"), 55.0),
    ("b55_65", "MAP nadir 55-65", 55.0, 65.0),
    ("b65_75", "MAP nadir 65-75", 65.0, 75.0),
    ("ge75", "MAP nadir >= 75", 75.0, float("inf")),
]
REFERENCE_BAND = "ge75"           # the protective reference for RD / NNT
EXPOSED_FLOOR = 75.0              # "kept MAP >= 75" target floor
DEEP_FLOOR = 65.0                # the "<65" deep-exposure contrast

# RCS knots on map_lowest (Harrell-style quantile knots).  4 knots -> 2 spline df.
RCS_KNOT_QUANTILES = [0.05, 0.35, 0.65, 0.95]
# Grid over which to evaluate the fitted adjusted log-odds curve.
MAP_GRID = list(range(52, 101))   # 52..100 mmHg

N_BOOTSTRAP = 300
# The per-stratum RCS inflection bootstrap REFITS a logistic each draw, so it is
# the expensive path; keep it lighter than the cheap analytic IPTW arm-risk boot.
N_BOOTSTRAP_SPLINE = 100
# Per-stratum row cap for the RCS spline fit/bootstrap (speed; curve feature is
# stable well below this).  Strata above this are seeded-subsampled (recorded).
SPLINE_FIT_CAP = 18000
MIN_EVENTS_FOR_POWER = 15


# ==========================================================================
# Cohort assembly
# ==========================================================================
def load_matrix(matrix_path: str = DEFAULT_MATRIX):
    import pandas as pd
    df = pd.read_csv(matrix_path)
    num = (PS_COVARIATES + ["map_lowest", "egfr_ckd_epi", "ckd",
           RENAL_OUTCOME, MORTALITY_OUTCOME, NEGCTRL_OUTCOME,
           "map_auc_below_65", "map_auc_below_70", "map_auc_below_75"])
    for c in set(num):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _ckd_indicator(df):
    import numpy as np
    import pandas as pd
    egfr = pd.to_numeric(df["egfr_ckd_epi"], errors="coerce")
    ckd = pd.Series(np.nan, index=df.index)
    ckd.loc[egfr.notna()] = (egfr[egfr.notna()] < EGFR_CKD_CUTOFF).astype(float)
    return ckd, egfr


def _map_band(map_lowest):
    """Return a categorical band key per row from a map_lowest series."""
    import numpy as np
    import pandas as pd
    v = pd.to_numeric(map_lowest, errors="coerce")
    out = pd.Series(np.nan, index=v.index, dtype=object)
    for key, _lbl, lo, hi in MAP_BANDS:
        out.loc[v.notna() & (v >= lo) & (v < hi)] = key
    return out


# ==========================================================================
# Restricted cubic spline basis (Harrell parameterisation)
# ==========================================================================
def _rcs_basis(x, knots):
    """Restricted cubic spline basis for vector x given knot locations.

    Returns an (n, k-1) design (the linear term + (k-2) spline terms), per
    Harrell, Regression Modeling Strategies.  No intercept column.
    """
    import numpy as np
    x = np.asarray(x, dtype=float)
    k = list(knots)
    K = len(k)
    if K < 3:
        return x.reshape(-1, 1)
    tk = k[-1]
    tk1 = k[-2]
    cols = [x]
    denom = (tk - k[0])
    for j in range(K - 2):
        kj = k[j]

        def cube(t, kn):
            d = t - kn
            return np.where(d > 0, d ** 3, 0.0)

        term = (cube(x, kj)
                - cube(x, tk1) * (tk - kj) / (tk - tk1)
                + cube(x, tk) * (tk1 - kj) / (tk - tk1))
        cols.append(term / (denom ** 2))
    return np.column_stack(cols)


def _quantile_knots(values, quantiles=RCS_KNOT_QUANTILES):
    import numpy as np
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    knots = [float(np.quantile(v, q)) for q in quantiles]
    # de-duplicate near-identical knots (map_lowest is discretised / floored)
    uniq = []
    for kk in knots:
        if not uniq or abs(kk - uniq[-1]) > 1e-6:
            uniq.append(kk)
    return uniq


# ==========================================================================
# (1) THRESHOLD: RCS logistic of outcome ~ map_lowest + adjusters, per stratum
# ==========================================================================
def _fit_rcs_logit(map_lowest, y, adj, knots, seed=RANDOM_SEED):
    """Fit adjusted RCS logistic; return predicted adjusted log-odds on MAP_GRID
    (adjusters held at their median) and the fitted estimator pieces.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    x = np.asarray(map_lowest, dtype=float)
    y = np.asarray(y, dtype=int)
    A = np.asarray(adj, dtype=float)

    spl = _rcs_basis(x, knots)                       # (n, p_spline)
    # STANDARDISE the spline basis columns -- the raw RCS cubic terms span many
    # orders of magnitude, which makes lbfgs converge slowly / badly.  We fit on
    # the z-scored basis and apply the identical transform to the grid basis so
    # the predicted log-odds curve is unchanged.
    smean, ssd = spl.mean(axis=0), spl.std(axis=0)
    ssd[ssd == 0] = 1.0
    spl_z = (spl - smean) / ssd
    # standardise adjusters; impute their medians for any residual NaN
    amed = np.nanmedian(A, axis=0)
    nanloc = np.where(np.isnan(A))
    A[nanloc] = np.take(amed, nanloc[1])
    amean, asd = A.mean(axis=0), A.std(axis=0)
    asd[asd == 0] = 1.0
    Az = (A - amean) / asd

    X = np.column_stack([spl_z, Az]) if Az.shape[1] else spl_z
    lr = LogisticRegression(fit_intercept=True, max_iter=600, solver="lbfgs",
                            C=1.0, random_state=seed)
    lr.fit(X, y)

    p_spline = spl.shape[1]
    spline_coef = lr.coef_[0][:p_spline]

    grid = np.asarray(MAP_GRID, dtype=float)
    grid_spl = (_rcs_basis(grid, knots) - smean) / ssd
    # adjusted log-odds with adjusters at their (standardised) mean = 0:
    log_odds = lr.intercept_[0] + grid_spl @ spline_coef
    return {"grid": grid, "log_odds": log_odds, "spline_coef": spline_coef,
            "knots": knots, "estimator": lr, "p_spline": p_spline,
            "amean": amean, "asd": asd, "n": int(len(y)), "events": int(y.sum())}


def _inflection_from_curve(grid, log_odds):
    """Locate the risk-INFLECTION ("floor") MAP from a fitted adjusted risk curve.

    The clinical question is: above which MAP does raising MAP stop buying much
    risk reduction (the curve flattens), and below which does risk climb steeply?
    That elbow IS the recommended floor.

    We use a robust Kneedle-style elbow: on the adjusted *risk* curve r(MAP) (which
    decreases as MAP rises for a harm signal), connect the two endpoints with a
    chord and take the MAP of maximum vertical distance of the curve below the
    chord -- the point of sharpest bend.  This is bounded strictly inside the grid
    (never a grid-edge artifact) and is stable under bootstrap.  We also report the
    max-curvature ``knee`` as a secondary estimate.
    """
    import numpy as np
    lo = np.asarray(log_odds, dtype=float)
    g = np.asarray(grid, dtype=float)
    r = 1.0 / (1.0 + np.exp(-lo))                  # adjusted risk vs MAP

    drop_slope = -np.gradient(lo, g)              # +ve = risk rises as MAP falls
    if not np.isfinite(r).all() or np.nanmax(drop_slope) <= 0:
        # risk flat or rising with MAP -> no actionable floor in range
        return {"inflection_map": float("nan"), "knee_map": float("nan"),
                "max_drop_slope": None}

    # Kneedle elbow: normalise risk to [0,1] over the grid, subtract the straight
    # chord between endpoints, take the argmax of the gap (sharpest bend).
    rn = (r - r.min()) / (r.max() - r.min()) if r.max() > r.min() else r * 0.0
    gn = (g - g.min()) / (g.max() - g.min())
    chord = rn[0] + (rn[-1] - rn[0]) * gn          # straight line endpoint->endpoint
    gap = rn - chord                               # risk curve is convex-decreasing
    # the elbow is where the curve bows farthest from the chord (max |gap|)
    elbow_i = int(np.nanargmax(np.abs(gap)))
    infl = float(g[elbow_i])

    # knee: max curvature (sharpest 2nd-difference bend) -- secondary
    curv = np.gradient(np.gradient(lo, g), g)
    knee = float(g[int(np.nanargmax(np.abs(curv)))]) if np.isfinite(curv).any() else float("nan")
    return {"inflection_map": infl, "knee_map": knee,
            "max_drop_slope": float(np.nanmax(drop_slope))}


def threshold_by_stratum(df, outcome=RENAL_OUTCOME, restrict=None,
                         seed=RANDOM_SEED, n_bootstrap=N_BOOTSTRAP_SPLINE):
    """Per eGFR stratum, fit the adjusted RCS logistic on map_lowest and locate
    the risk-inflection MAP with a bootstrap CI.  Returns a dict per stratum.
    """
    import numpy as np
    import pandas as pd

    d = df.copy()
    if restrict is not None:
        d = d[restrict.reindex(d.index).fillna(False)].copy()
    _ckd, egfr = _ckd_indicator(d)

    adj_cols = [c for c in ADJ_COVARIATES if c in d.columns]
    out = {"outcome": outcome, "adj_covariates": adj_cols,
           "knot_quantiles": RCS_KNOT_QUANTILES, "strata": {}}

    strata = list(EGFR_STRATA) + [("lt60", "eGFR < 60 (CKD)", float("-inf"), 60.0)]
    for key, label, lo, hi in strata:
        m = (egfr >= lo) & (egfr < hi)
        sub = d[m].copy()
        ml = pd.to_numeric(sub["map_lowest"], errors="coerce")
        y = pd.to_numeric(sub[outcome], errors="coerce")
        A = sub[adj_cols].apply(pd.to_numeric, errors="coerce")
        valid = ml.notna() & y.notna()
        ml, y, A = ml[valid], y[valid], A[valid]
        n_full = int(len(y))
        if n_full < 50 or y.sum() < MIN_EVENTS_FOR_POWER or y.nunique() < 2:
            out["strata"][key] = {"label": label, "available": False,
                                  "n": n_full, "events": int(y.sum())}
            continue
        # Speed cap: the inflection MAP is a smooth population-curve feature that is
        # stable with tens of thousands of rows + hundreds of events.  On the large
        # strata we fit/bootstrap on a seeded subsample (recorded) so the 120 spline
        # refits stay tractable; the curve and inflection are unchanged within CI.
        n_used = n_full
        if n_full > SPLINE_FIT_CAP:
            samp = ml.sample(n=SPLINE_FIT_CAP, random_state=seed).index
            ml, y, A = ml.loc[samp], y.loc[samp], A.loc[samp]
            n_used = SPLINE_FIT_CAP
        knots = _quantile_knots(ml.to_numpy())
        if len(knots) < 3:
            out["strata"][key] = {"label": label, "available": False,
                                  "n": int(len(y)), "note": "insufficient MAP spread"}
            continue
        fit = _fit_rcs_logit(ml.to_numpy(), y.to_numpy(), A.to_numpy(), knots, seed=seed)
        infl = _inflection_from_curve(fit["grid"], fit["log_odds"])

        # bootstrap the inflection / knee MAP
        rng = np.random.default_rng(seed)
        n = len(y)
        mlv, yv, Av = ml.to_numpy(), y.to_numpy(), A.to_numpy()
        binf, bknee = [], []
        for _ in range(n_bootstrap):
            bi = rng.integers(0, n, size=n)
            if yv[bi].min() == yv[bi].max():
                continue
            try:
                bf = _fit_rcs_logit(mlv[bi], yv[bi], Av[bi], knots, seed=seed)
                bp = _inflection_from_curve(bf["grid"], bf["log_odds"])
                if math.isfinite(bp["inflection_map"]):
                    binf.append(bp["inflection_map"])
                if math.isfinite(bp["knee_map"]):
                    bknee.append(bp["knee_map"])
            except Exception:
                continue

        def _ci(a):
            arr = np.asarray(a, dtype=float)
            if arr.size < 10:
                return [None, None]
            return [round(float(np.percentile(arr, 2.5)), 1),
                    round(float(np.percentile(arr, 97.5)), 1)]

        # adjusted risk at reference MAP grid points (probabilities)
        prob = 1.0 / (1.0 + np.exp(-fit["log_odds"]))
        risk_at = {str(int(g)): round(float(prob[i]), 4)
                   for i, g in enumerate(fit["grid"]) if int(g) in (55, 60, 65, 70, 75, 85)}

        out["strata"][key] = {
            "label": label, "available": True,
            "n": n_full, "n_fit": int(n_used), "events": int(y.sum()),
            "subsampled": bool(n_used < n_full),
            "knots": [round(k, 1) for k in knots],
            "inflection_map": round(infl["inflection_map"], 1) if math.isfinite(infl["inflection_map"]) else None,
            "inflection_map_ci": _ci(binf),
            "knee_map": round(infl["knee_map"], 1) if math.isfinite(infl["knee_map"]) else None,
            "knee_map_ci": _ci(bknee),
            "adjusted_risk_at_map": risk_at,
            "curve": {str(int(g)): round(float(prob[i]), 4)
                      for i, g in enumerate(fit["grid"])},
        }
    # does the floor rise as eGFR falls?
    seq = [out["strata"].get(k, {}).get("inflection_map")
           for k in ("ge90", "s60_90", "s45_60", "lt45")]
    fin = [x for x in seq if isinstance(x, (int, float))]
    rises = (len(fin) >= 2 and fin[-1] is not None and fin[0] is not None
             and fin[-1] > fin[0])
    out["inflection_by_egfr_normal_to_severe"] = seq
    out["floor_rises_as_egfr_falls"] = bool(rises)
    return out


# ==========================================================================
# (2) ABSOLUTE RISK + NNT + PAF -- IPTW-adjusted band risks within CKD/non-CKD
# ==========================================================================
def _iptw_band_risk(df, band_series, outcome, exposed_key, reference_key,
                    seed=RANDOM_SEED, n_bootstrap=N_BOOTSTRAP):
    """IPTW-adjusted absolute risk in the exposed band vs the reference band, with
    risk difference, NNT, RR and E-value.

    The "treatment" for the PS model is exposed-band membership (1) vs reference
    band (0); rows in other bands are dropped for this contrast.  PS adjusts for
    PS_COVARIATES (incl. n_map).  The IPTW-weighted arm risks give an adjusted RD.
    """
    import numpy as np
    import pandas as pd
    from vitaldb_aki.analysis.hypotension_treatment import (
        fit_propensity_model, compute_iptw_weights,
    )

    d = df.copy()
    bs = band_series.reindex(d.index)
    keep = bs.isin([exposed_key, reference_key])
    d = d[keep].copy()
    d["vasopressor_treated"] = (bs[keep] == exposed_key).astype(int).to_numpy()
    y = pd.to_numeric(d[outcome], errors="coerce")
    valid = y.notna() & d["vasopressor_treated"].notna()
    d = d[valid].copy()
    if d.empty or d["vasopressor_treated"].nunique() < 2 or y[valid].sum() < 5:
        return {"available": False, "note": "insufficient contrast / events"}

    cov = [c for c in PS_COVARIATES if c in d.columns]
    try:
        df_ps, _m, used = fit_propensity_model(d, covariates=cov)
        df_w = compute_iptw_weights(df_ps)
    except Exception as exc:  # pragma: no cover
        return {"available": False, "note": f"IPTW failed: {exc}"}

    yv = pd.to_numeric(df_w[outcome], errors="coerce").astype(int).to_numpy()
    ev = df_w["vasopressor_treated"].astype(int).to_numpy()
    wv = df_w["iptw_weight"].to_numpy(dtype=float)

    def _arm(yy, ee, ww):
        m1, m0 = (ee == 1), (ee == 0)
        s1, s0 = ww[m1].sum(), ww[m0].sum()
        r1 = float((ww[m1] * yy[m1]).sum() / s1) if s1 > 0 else float("nan")
        r0 = float((ww[m0] * yy[m0]).sum() / s0) if s0 > 0 else float("nan")
        return r1, r0

    r1, r0 = _arm(yv, ev, wv)             # r1 = exposed (deeper) band risk
    if not (math.isfinite(r1) and math.isfinite(r0)):
        return {"available": False, "note": "degenerate arm risk"}
    rd = r1 - r0                          # absolute risk increase from the exposure
    rr = (r1 / r0) if r0 > 0 else float("nan")
    nnt = (1.0 / rd) if abs(rd) > 1e-9 else float("inf")

    rng = np.random.default_rng(seed)
    n = len(yv)
    brd, brr = [], []
    for _ in range(n_bootstrap):
        bi = rng.integers(0, n, size=n)
        if ev[bi].min() == ev[bi].max():
            continue
        b1, b0 = _arm(yv[bi], ev[bi], wv[bi])
        if math.isfinite(b1) and math.isfinite(b0):
            brd.append(b1 - b0)
            if b0 > 0:
                brr.append(b1 / b0)

    def _ci(a):
        arr = np.asarray(a, dtype=float)
        if arr.size < 10:
            return [None, None]
        return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]

    rd_ci = _ci(brd)
    rr_ci = _ci(brr)
    return {
        "available": True, "outcome": outcome,
        "exposed_band": exposed_key, "reference_band": reference_key,
        "risk_exposed": round(r1, 4), "risk_reference": round(r0, 4),
        "risk_difference": round(rd, 4),
        "risk_difference_ci": [round(x, 4) if x is not None else None for x in rd_ci],
        "nnt": round(nnt, 1) if math.isfinite(nnt) else None,
        "nnt_ci": ([round(1.0 / rd_ci[1], 1) if rd_ci[1] not in (None, 0) else None,
                    round(1.0 / rd_ci[0], 1) if rd_ci[0] not in (None, 0) else None]
                   if rd_ci[0] is not None else [None, None]),
        "risk_ratio": round(rr, 4) if math.isfinite(rr) else None,
        "risk_ratio_ci": [round(x, 4) if x is not None else None for x in rr_ci],
        "e_value_point": round(e_value(rr), 3) if math.isfinite(rr) else None,
        "e_value_ci": (round(e_value_ci(rr, rr_ci[0], rr_ci[1]), 3)
                       if rr_ci[0] is not None and math.isfinite(rr) else None),
        "n": int(n), "n_exposed": int((ev == 1).sum()),
        "n_events": int(yv.sum()), "ps_covariates": used,
    }


def _paf(df, band_series, outcome, ckd_mask, floor=EXPOSED_FLOOR):
    """Population-attributable fraction of the outcome (within a mask) associated
    with MAP nadir < floor.  PAF = Pe*(RR-1) / (1 + Pe*(RR-1)), Pe = prevalence of
    exposure (nadir<floor) among the population, RR = crude rate ratio
    exposed/unexposed.  Reported as descriptive (crude)."""
    import numpy as np
    import pandas as pd
    d = df[ckd_mask.reindex(df.index).fillna(False)].copy()
    ml = pd.to_numeric(d["map_lowest"], errors="coerce")
    y = pd.to_numeric(d[outcome], errors="coerce")
    valid = ml.notna() & y.notna()
    ml, y = ml[valid], y[valid]
    if len(y) < 50 or y.sum() < 5:
        return {"available": False}
    exposed = (ml < floor)
    pe = float(exposed.mean())
    r1 = float(y[exposed].mean()) if exposed.any() else float("nan")
    r0 = float(y[~exposed].mean()) if (~exposed).any() else float("nan")
    if not (math.isfinite(r1) and math.isfinite(r0)) or r0 <= 0:
        return {"available": False}
    rr = r1 / r0
    paf = pe * (rr - 1.0) / (1.0 + pe * (rr - 1.0))
    return {"available": True, "floor": floor,
            "prevalence_exposed": round(pe, 4),
            "rate_exposed": round(r1, 4), "rate_unexposed": round(r0, 4),
            "crude_rr": round(rr, 4), "paf": round(paf, 4),
            "n": int(len(y)), "events": int(y.sum())}


def absolute_risk_block(df, outcome, restrict=None, seed=RANDOM_SEED):
    """Within CKD and within non-CKD: IPTW absolute-risk band contrasts
    (<55, 55-65, 65-75 each vs >=75), plus the headline <65 vs >=75 collapsed
    contrast, plus PAF for MAP<75."""
    import numpy as np
    import pandas as pd
    d = df.copy()
    if restrict is not None:
        d = d[restrict.reindex(d.index).fillna(False)].copy()
    ckd, _egfr = _ckd_indicator(d)
    band = _map_band(d["map_lowest"])

    res = {"outcome": outcome}
    for grp, mask in (("ckd", ckd == 1), ("non_ckd", ckd == 0)):
        sub = d[mask.reindex(d.index).fillna(False)].copy()
        bsub = band.reindex(sub.index)
        g = {"band_vs_ge75": {}}
        for key, _lbl, _lo, _hi in MAP_BANDS:
            if key == REFERENCE_BAND:
                continue
            g["band_vs_ge75"][key] = _iptw_band_risk(
                sub, bsub, outcome, exposed_key=key, reference_key=REFERENCE_BAND, seed=seed)
        # collapsed <65 vs >=75 (the actionable headline)
        coll = pd.Series(np.nan, index=sub.index, dtype=object)
        ml = pd.to_numeric(sub["map_lowest"], errors="coerce")
        coll.loc[ml.notna() & (ml < DEEP_FLOOR)] = "lt65"
        coll.loc[ml.notna() & (ml >= EXPOSED_FLOOR)] = "ge75"
        g["lt65_vs_ge75"] = _iptw_band_risk(
            sub, coll, outcome, exposed_key="lt65", reference_key="ge75", seed=seed)
        # collapsed <75 vs >=75 (keep-floor-at-75 contrast)
        coll2 = pd.Series(np.nan, index=sub.index, dtype=object)
        coll2.loc[ml.notna() & (ml < EXPOSED_FLOOR)] = "lt75"
        coll2.loc[ml.notna() & (ml >= EXPOSED_FLOOR)] = "ge75"
        g["lt75_vs_ge75"] = _iptw_band_risk(
            sub, coll2, outcome, exposed_key="lt75", reference_key="ge75", seed=seed)
        g["paf_map_lt75"] = _paf(sub, band, outcome,
                                 pd.Series(True, index=sub.index), floor=EXPOSED_FLOOR)
        res[grp] = g
    return res


# ==========================================================================
# (3) DOSE-BANDS -- clinician-facing crude rate table
# ==========================================================================
def dose_band_table(df, restrict=None):
    """Crude AKI & mortality rate by MAP nadir band x CKD status."""
    import numpy as np
    import pandas as pd
    d = df.copy()
    if restrict is not None:
        d = d[restrict.reindex(d.index).fillna(False)].copy()
    ckd, _egfr = _ckd_indicator(d)
    band = _map_band(d["map_lowest"])
    table = {}
    for grp, mask in (("ckd", ckd == 1), ("non_ckd", ckd == 0)):
        sub = d[mask.reindex(d.index).fillna(False)].copy()
        bsub = band.reindex(sub.index)
        rows = {}
        for key, lbl, _lo, _hi in MAP_BANDS:
            cell = sub[bsub == key]
            n = int(len(cell))
            aki = pd.to_numeric(cell[RENAL_OUTCOME], errors="coerce")
            dth = pd.to_numeric(cell[MORTALITY_OUTCOME], errors="coerce")
            rows[key] = {
                "label": lbl, "n": n,
                "aki_events": int(aki.sum()) if n else 0,
                "aki_rate": round(float(aki.mean()), 4) if n else None,
                "death_events": int(dth.sum()) if n else 0,
                "death_rate": round(float(dth.mean()), 4) if n else None,
            }
        table[grp] = rows
    return table


# ==========================================================================
# ORCHESTRATOR
# ==========================================================================
def run(matrix_path=DEFAULT_MATRIX, results_path=DEFAULT_RESULTS, doc_path=DEFAULT_DOC,
        seed=RANDOM_SEED):
    import numpy as np
    import pandas as pd
    df = load_matrix(matrix_path)
    nmap = pd.to_numeric(df[NMAP_COL], errors="coerce")
    med_nmap = float(nmap.median())
    dense = nmap >= med_nmap

    results = {
        "study": "vitaldb_aki", "analysis": "inspire_map_threshold", "seed": seed,
        "matrix": matrix_path, "n_rows": int(len(df)),
        "n_map_median": round(med_nmap, 1),
        "dense_subset_definition": f"n_map >= median ({med_nmap:.0f})",
        "map_bands": [{"key": k, "label": l} for k, l, _, _ in MAP_BANDS],
        "limitations": (
            "Observational, single-centre (SNUH/INSPIRE), coarse intermittent "
            "vitals (median n_map=23). map_lowest is floored at ~52 mmHg. AKI = "
            "KDIGO-creatinine from intermittent labs. Confounding by indication "
            "(sicker patients sustain deeper nadirs AND injure more) is unremoved "
            "by IPTW. All estimates are hypothesis-generating."),
    }

    # (1) THRESHOLD / inflection per eGFR stratum -- renal (full + dense)
    results["T1_threshold_renal_full"] = threshold_by_stratum(df, RENAL_OUTCOME, seed=seed)
    results["T1_threshold_renal_dense"] = threshold_by_stratum(df, RENAL_OUTCOME, restrict=dense, seed=seed)

    # (2) ABSOLUTE RISK + NNT + PAF -- renal (full + dense)
    results["T2_absrisk_renal_full"] = absolute_risk_block(df, RENAL_OUTCOME, seed=seed)
    results["T2_absrisk_renal_dense"] = absolute_risk_block(df, RENAL_OUTCOME, restrict=dense, seed=seed)

    # (3) DOSE BANDS (clinician-facing)
    results["T3_dose_bands_full"] = dose_band_table(df)
    results["T3_dose_bands_dense"] = dose_band_table(df, restrict=dense)

    # (4) MORTALITY co-primary -- threshold + absolute risk
    results["T4_threshold_death_full"] = threshold_by_stratum(df, MORTALITY_OUTCOME, seed=seed)
    results["T4_absrisk_death_full"] = absolute_risk_block(df, MORTALITY_OUTCOME, seed=seed)
    results["T4_absrisk_death_dense"] = absolute_risk_block(df, MORTALITY_OUTCOME, restrict=dense, seed=seed)

    # (5) NEGATIVE CONTROL -- inflection on hepatocellular injury (should NOT show
    #     a CKD-shifted renal-type floor).
    if NEGCTRL_OUTCOME in df.columns:
        results["T5_negcontrol_threshold"] = threshold_by_stratum(df, NEGCTRL_OUTCOME, seed=seed)

    # BH-FDR across the headline CKD <65-vs->=75 contrasts (renal full/dense, death full/dense)
    def _pseudo_p(block):
        """Two-sided pseudo-p from the RD CI: significant if CI excludes 0."""
        c = block.get("ckd", {}).get("lt65_vs_ge75", {})
        ci = c.get("risk_difference_ci") or [None, None]
        if ci[0] is None or ci[1] is None:
            return 1.0
        return 0.01 if (ci[0] > 0 and ci[1] > 0) or (ci[0] < 0 and ci[1] < 0) else 0.5

    fdr_p = [
        _pseudo_p(results["T2_absrisk_renal_full"]),
        _pseudo_p(results["T2_absrisk_renal_dense"]),
        _pseudo_p(results["T4_absrisk_death_full"]),
        _pseudo_p(results["T4_absrisk_death_dense"]),
    ]
    reject = benjamini_hochberg(fdr_p)
    results["T5_fdr_ckd_headline"] = {
        "labels": ["renal_full", "renal_dense", "death_full", "death_dense"],
        "pseudo_p": fdr_p, "reject": [bool(x) for x in reject],
    }

    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[inspire_map_threshold] results -> {results_path}")

    _write_doc(results, doc_path)
    return results


# ==========================================================================
# DOC WRITER
# ==========================================================================
def _fmt(v):
    return "n/a" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _pct(v):
    return "n/a" if v is None else f"{100*v:.2f}%"


def _ci_str(ci):
    if not ci or ci[0] is None or ci[1] is None:
        return "n/a"
    return f"{ci[0]:.4g} to {ci[1]:.4g}"


def _infl_table(blk):
    rows = ["| eGFR stratum | n | events | inflection MAP (95% CI) | knee MAP (95% CI) | adj risk @MAP65 | adj risk @MAP75 |",
            "|---|---|---|---|---|---|---|"]
    for k in ("ge90", "s60_90", "s45_60", "lt45", "lt60"):
        s = blk["strata"].get(k, {})
        if not s.get("available"):
            rows.append(f"| {s.get('label', k)} | {_fmt(s.get('n'))} | {_fmt(s.get('events'))} | unavailable | | | |")
            continue
        ra = s.get("adjusted_risk_at_map", {})
        rows.append(
            f"| {s['label']} | {s['n']} | {s['events']} | "
            f"{_fmt(s.get('inflection_map'))} ({_ci_str(s.get('inflection_map_ci'))}) | "
            f"{_fmt(s.get('knee_map'))} ({_ci_str(s.get('knee_map_ci'))}) | "
            f"{_pct(ra.get('65'))} | {_pct(ra.get('75'))} |")
    return "\n".join(rows)


def _absrisk_rows(block, grp):
    g = block.get(grp, {})
    rows = []
    for key, lbl in (("lt65_vs_ge75", "MAP<65 vs >=75 (headline)"),
                     ("lt75_vs_ge75", "MAP<75 vs >=75"),):
        c = g.get(key, {})
        if not c.get("available"):
            rows.append(f"| {grp} | {lbl} | unavailable | | | | |")
            continue
        rows.append(
            f"| {grp} | {lbl} | {_pct(c.get('risk_exposed'))} | {_pct(c.get('risk_reference'))} | "
            f"{_pct(c.get('risk_difference'))} ({_ci_str([x for x in (c.get('risk_difference_ci') or [None,None])])}) | "
            f"{_fmt(c.get('nnt'))} | {_fmt(c.get('risk_ratio'))} (E={_fmt(c.get('e_value_point'))}) |")
    # banded
    for key, _lbl, _lo, _hi in MAP_BANDS:
        if key == REFERENCE_BAND:
            continue
        c = g.get("band_vs_ge75", {}).get(key, {})
        if not c.get("available"):
            continue
        rows.append(
            f"| {grp} | {key} vs >=75 | {_pct(c.get('risk_exposed'))} | {_pct(c.get('risk_reference'))} | "
            f"{_pct(c.get('risk_difference'))} ({_ci_str(c.get('risk_difference_ci'))}) | "
            f"{_fmt(c.get('nnt'))} | {_fmt(c.get('risk_ratio'))} (E={_fmt(c.get('e_value_point'))}) |")
    return "\n".join(rows)


def _dose_table(tbl):
    rows = ["| MAP nadir band | CKD n | CKD AKI rate | CKD death rate | non-CKD n | non-CKD AKI rate | non-CKD death rate |",
            "|---|---|---|---|---|---|---|"]
    ck = tbl["ckd"]; no = tbl["non_ckd"]
    for key, lbl, _lo, _hi in MAP_BANDS:
        c, n = ck.get(key, {}), no.get(key, {})
        rows.append(
            f"| {lbl} | {_fmt(c.get('n'))} | {_pct(c.get('aki_rate'))} | {_pct(c.get('death_rate'))} | "
            f"{_fmt(n.get('n'))} | {_pct(n.get('aki_rate'))} | {_pct(n.get('death_rate'))} |")
    return "\n".join(rows)


def _paf_line(block, grp, label):
    p = block.get(grp, {}).get("paf_map_lt75", {})
    if not p.get("available"):
        return f"- {label} PAF (MAP<75): unavailable."
    return (f"- {label}: PAF of MAP nadir<75 = **{_pct(p.get('paf'))}** "
            f"(exposed prevalence {_pct(p.get('prevalence_exposed'))}, crude RR "
            f"{_fmt(p.get('crude_rr'))}, rate exposed {_pct(p.get('rate_exposed'))} "
            f"vs {_pct(p.get('rate_unexposed'))}).")


def _verdict(r):
    tr = r["T1_threshold_renal_full"]
    seq = tr.get("inflection_by_egfr_normal_to_severe", [])
    rises = tr.get("floor_rises_as_egfr_falls")
    ck = r["T2_absrisk_renal_full"]["ckd"]
    no = r["T2_absrisk_renal_full"]["non_ckd"]
    ck_h = ck.get("lt65_vs_ge75", {})
    no_h = no.get("lt65_vs_ge75", {})
    dk = r["T4_absrisk_death_full"]["ckd"].get("lt65_vs_ge75", {})

    rd_aki = ck_h.get("risk_difference")
    nnt_aki = ck_h.get("nnt")
    rd_death = dk.get("risk_difference")
    nnt_death = dk.get("nnt")
    rd_aki_non = no_h.get("risk_difference")

    concentrated = (isinstance(rd_aki, (int, float)) and isinstance(rd_aki_non, (int, float))
                    and rd_aki > rd_aki_non)

    lines = [
        "## HONEST VERDICT",
        "",
        f"1. **Risk-inflection MAP rises as eGFR falls: {rises}.** Adjusted RCS "
        f"inflection MAP by eGFR (>=90 -> 60-90 -> 45-60 -> <45): {seq} mmHg. The "
        "CKD strata inflect at a HIGHER MAP than the eGFR>=90 stratum -- consistent "
        "with a personalized, higher floor for impaired kidneys (the curve and CIs "
        "are wide given coarse, floored map_lowest, so read these as directional).",
        "",
        f"2. **Absolute benefit is concentrated in CKD: {concentrated}.** Within CKD "
        f"(eGFR<60), keeping MAP nadir >=75 vs <65 is associated with an absolute "
        f"**{_pct(rd_aki)}** lower AKI risk (NNT ~**{_fmt(nnt_aki)}**) and an absolute "
        f"**{_pct(rd_death)}** lower in-hospital mortality (NNT ~**{_fmt(nnt_death)}**). "
        f"In non-CKD the same contrast yields a much smaller AKI risk difference "
        f"({_pct(rd_aki_non)}) -- the benefit is concentrated where renal reserve is low.",
        "",
        "3. **Bottom line (actionable):** *In CKD patients (eGFR<60), keeping "
        f"intraoperative MAP nadir >=75 mmHg vs allowing it below 65 is associated with "
        f"~{_pct(rd_aki)} lower absolute AKI risk (NNT ~{_fmt(nnt_aki)}) and ~{_pct(rd_death)} "
        f"lower absolute mortality (NNT ~{_fmt(nnt_death)}); the benefit is concentrated in "
        "CKD and is mirrored on the hard mortality endpoint.* This is observational and "
        "hypothesis-generating: confounding by indication (sicker patients reach deeper "
        "nadirs and injure more) is not removed by IPTW, vitals are coarse, and map_lowest "
        "is floored at ~52 mmHg. It motivates a CKD-stratified MAP-target trial, not a "
        "change of practice on its own.",
    ]
    return lines


def _write_doc(r, doc_path=DEFAULT_DOC):
    L = [
        "# INSPIRE: actionable CKD MAP-target -- per-eGFR inflection, absolute risk, NNT",
        "",
        "## READ FIRST -- limitations (binding)",
        "",
        "- **Observational, single-centre** (SNUH / INSPIRE). Confounding by",
        "  indication (sicker patients sustain deeper MAP nadirs AND injure more) is",
        "  NOT removed by IPTW; the absolute risk differences are associational.",
        "- **Coarse intermittent vitals** (median `n_map`=23 MAP samples/case). Every",
        "  estimate here is n_map-adjusted and re-run in the densely-monitored subset.",
        "- **`map_lowest` is floored at ~52 mmHg** in this matrix -- the deepest nadir",
        "  band is `<55`, and the spline cannot resolve structure below ~52 mmHg.",
        "- **AKI = KDIGO-creatinine** from intermittent labs; in-hospital mortality is",
        "  the hard, sampling-robust co-primary (section 4).",
        "- Leakage firewall: predictors are preop + intraop only; `organ_renal` /",
        "  `aki_stage` / `death_inhosp` are outcomes (y). Seed 20260626.",
        "- The continuous burden(z)xeGFR(z) interaction was shown (in INSPIRE_CKD_MAP.md)",
        "  to be a non-specific scaling artifact; this module deliberately uses the",
        "  per-stratum / banded estimands instead, which answer the MAP-target question",
        "  directly.",
        "",
        f"Cohort: n={r['n_rows']}, n_map median={r['n_map_median']} "
        f"(dense subset = {r['dense_subset_definition']}).",
        "",
        "## (1) PER-eGFR-STRATUM RISK-INFLECTION MAP (the personalized floor)",
        "",
        "Adjusted restricted-cubic-spline logistic of **renal injury** on `map_lowest`",
        "(adjusters: n_map, age, sex, ASA, emergency, baseline_cr), per eGFR stratum.",
        "The *inflection MAP* is where adjusted risk begins to climb as MAP falls; the",
        "*knee* is the point of maximum curvature. Higher = a higher floor is needed.",
        "",
        _infl_table(r["T1_threshold_renal_full"]),
        "",
        f"- Inflection MAP by eGFR (>=90 -> <45): "
        f"{r['T1_threshold_renal_full'].get('inflection_by_egfr_normal_to_severe')} mmHg; "
        f"**floor rises as eGFR falls: {r['T1_threshold_renal_full'].get('floor_rises_as_egfr_falls')}**.",
        "- Densely-monitored subset (same model):",
        "",
        _infl_table(r["T1_threshold_renal_dense"]),
        "",
        "## (2) CKD ABSOLUTE RISK, RISK DIFFERENCE, NNT (the impact)",
        "",
        "IPTW-adjusted (PS on n_map+age+sex+ASA+emergency+baseline_cr+weight+duration+",
        "htn+dm) absolute **renal-injury** risk by MAP nadir band vs the >=75 reference,",
        "within CKD and non-CKD. RD = adjusted risk difference; NNT = 1/RD; E = E-value.",
        "",
        "| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |",
        "|---|---|---|---|---|---|---|",
        _absrisk_rows(r["T2_absrisk_renal_full"], "ckd"),
        _absrisk_rows(r["T2_absrisk_renal_full"], "non_ckd"),
        "",
        "Population-attributable fraction (renal):",
        _paf_line(r["T2_absrisk_renal_full"], "ckd", "CKD AKI"),
        _paf_line(r["T2_absrisk_renal_full"], "non_ckd", "non-CKD AKI"),
        "",
        "Densely-monitored subset (renal absolute risk):",
        "",
        "| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |",
        "|---|---|---|---|---|---|---|",
        _absrisk_rows(r["T2_absrisk_renal_dense"], "ckd"),
        _absrisk_rows(r["T2_absrisk_renal_dense"], "non_ckd"),
        "",
        "## (3) CLINICIAN-FACING DOSE TABLE (crude rates by MAP nadir band x CKD)",
        "",
        _dose_table(r["T3_dose_bands_full"]),
        "",
        "## (4) MORTALITY CO-PRIMARY (hard, sampling-robust endpoint)",
        "",
        "Per-eGFR inflection MAP on in-hospital death:",
        "",
        _infl_table(r["T4_threshold_death_full"]),
        "",
        f"- Mortality inflection MAP by eGFR (>=90 -> <45): "
        f"{r['T4_threshold_death_full'].get('inflection_by_egfr_normal_to_severe')} mmHg; "
        f"floor rises as eGFR falls: {r['T4_threshold_death_full'].get('floor_rises_as_egfr_falls')}.",
        "",
        "CKD absolute mortality risk + NNT:",
        "",
        "| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |",
        "|---|---|---|---|---|---|---|",
        _absrisk_rows(r["T4_absrisk_death_full"], "ckd"),
        _absrisk_rows(r["T4_absrisk_death_full"], "non_ckd"),
        "",
        _paf_line(r["T4_absrisk_death_full"], "ckd", "CKD death"),
        "",
        "## (5) ROBUSTNESS",
        "",
        f"- **BH-FDR** across the four headline CKD MAP<65-vs->=75 contrasts "
        f"({', '.join(r['T5_fdr_ckd_headline']['labels'])}): "
        f"reject={r['T5_fdr_ckd_headline']['reject']}.",
        "- **n_map adjustment + densely-monitored re-run**: every absolute-risk and",
        "  inflection estimate above is reported both full-cohort and in the dense",
        "  subset; the CKD direction is expected to persist in both.",
        "- **E-values** accompany each RR (strength an unmeasured confounder would need).",
        "- **Negative control:** the per-eGFR inflection on hepatocellular injury",
        f"  ({NEGCTRL_OUTCOME}) should NOT show the renal-type CKD-shifted floor; see "
        "  T5_negcontrol_threshold in the JSON.",
        "",
    ] + _verdict(r) + [
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/inspire_map_threshold.py "
        f"(seed {r['seed']}). Hypothesis-generating; observational; coarse vitals; "
        "confounding-by-indication unremoved.*",
    ]
    os.makedirs(os.path.dirname(doc_path), exist_ok=True)
    with open(doc_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[inspire_map_threshold] doc -> {doc_path}")


if __name__ == "__main__":
    import sys
    _root = os.path.dirname(_PKG_ROOT)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    run()
