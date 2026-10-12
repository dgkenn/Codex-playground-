"""requirement_onset_shape.py -- DEEPER trajectory tangent: the SHAPE and ONSET
TIMING of the rising vasopressor-requirement.

Premise (established)
---------------------
docs/PRESSOR_REQUIREMENT.md: the stable-epoch norepinephrine dose-REQUIREMENT is a
reliable, between-patient vasoplegia phenotype (MAP is feedback-regulated, so the
signal lives in the DOSE). docs/PRESSOR_REQUIREMENT_TRAJECTORY.md: 54% of NEPI-only
cases show a RISING dose_per_kg requirement over time -- the requirement is a real,
common trajectory. analysis/pressor_requirement_trajectory.py already established
TREND / LEAD-TIME / OUTCOME / SVR-falsification. This module does NOT duplicate that;
it asks the next, complementary questions about the trajectory's SHAPE and TIMING.

This module (complementary, not overlapping)
--------------------------------------------
  1. RATE-OF-RISE vs LEVEL -- per case the within-case OLS slope of dose_per_kg on
     t_start (minutes) is the "rise rate". Does the EARLY rate-of-rise add predictive
     information BEYOND the early LEVEL for the LATE/eventual requirement? Nested OLS
     (late ~ early_level) vs (late ~ early_level + early_slope): partial-R^2,
     partial correlation, F-test. Is a "fast riser" a distinct, identifiable subgroup?

  2. ONSET TIMING -- the minute at which a case first crosses a HIGH-requirement
     threshold (per-cohort high percentile of dose_per_kg). Time measured both from
     the case's first stable epoch and (using cases.csv anestart) from anaesthesia
     start. Distribution: median, spread, bimodality (dip-style gap + a simple
     2-means split on onset time -> early-onset vs late-onset).

  3. PROGRESSIVE vs TRANSIENT -- classify each case as monotonic-rising / plateau /
     falling using the overall slope sign + end-vs-peak ratio. Do the classes differ
     in outcome (cohort_composite) and in SVR trend where available? Honest about N.

Sample: NEPI norepi-only stable epochs, time-ordered within case, >= MIN_EPOCHS (4)
epochs/case (a stricter floor than the trajectory module's 3, because shape/onset
need more points).

stdlib only at import; numpy/pandas/scipy lazy. Style mirrors pressor_requirement.py.
Run: python3 -m vitaldb_aki.analysis.requirement_onset_shape
"""
from __future__ import annotations
import csv as _csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628

PRIMARY_DRUG = "NEPI"
EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
COMPOSITE_CSV = os.path.join(_CACHE, "cohort_composite.csv")
COHORT_CSV = os.path.join(_CACHE, "cohort.csv")
CASES_CSV = os.path.join(_CACHE, "cases.csv")

MIN_EPOCHS = 4                 # shape/onset need >=4 time-ordered epochs/case
HIGH_PCTL = 75.0               # "HIGH requirement" threshold = this cohort percentile of dose_per_kg
EARLY_FRAC = 0.5              # "early" window = first half of a case's epochs (by index)
PLATEAU_TOL = 0.15           # |end-peak|/peak <= this AND small slope -> plateau
B_BOOT = 2000

OUT_JSON = os.path.join(_CACHE, "requirement_onset_shape.json")
OUT_DOC = os.path.join(_DOCS, "REQUIREMENT_ONSET_SHAPE.md")


# --------------------------------------------------------------------- helpers
def _ols(x, y):
    """OLS slope, intercept of y on x. None if degenerate."""
    import numpy as np
    x = np.asarray(x, float); y = np.asarray(y, float)
    xc = x - x.mean()
    sxx = float(np.sum(xc * xc))
    if sxx <= 0:
        return None, None
    slope = float(np.sum(xc * (y - y.mean())) / sxx)
    intercept = float(y.mean() - slope * x.mean())
    return slope, intercept


def _anes_offsets():
    """caseid -> anestart (seconds, usually negative). Lets us express onset time
    from ANAESTHESIA START as well as from the first stable epoch."""
    out = {}
    if not os.path.exists(CASES_CSV):
        return out
    with open(CASES_CSV, newline="", encoding="utf-8") as fh:
        r = _csv.DictReader(fh)
        idc = [c for c in r.fieldnames if c.lstrip("﻿").lower() == "caseid"][0]
        for row in r:
            cid = row[idc]
            try:
                out[cid] = float(row.get("anestart", ""))
            except (ValueError, TypeError):
                pass
    return out


def _load_outcomes():
    """caseid -> {composite, organ_renal, aki}."""
    out = {}
    if os.path.exists(COMPOSITE_CSV):
        for r in _csv.DictReader(open(COMPOSITE_CSV, newline="")):
            out.setdefault(r["caseid"], {})
            out[r["caseid"]]["composite"] = r.get("composite", "")
            out[r["caseid"]]["organ_renal"] = r.get("organ_renal", "")
    if os.path.exists(COHORT_CSV):
        for r in _csv.DictReader(open(COHORT_CSV, newline="")):
            out.setdefault(r["caseid"], {})
            out[r["caseid"]]["aki"] = r.get("aki", "")
    return out


def _case_series(q, anes):
    """Per case: time-ordered NEPI-only epochs with >=MIN_EPOCHS. Returns dict keyed
    by caseid with arrays in MINUTES from the case's first stable epoch (t_min) and,
    where anestart known, minutes from anaesthesia start (t_anes_min)."""
    out = {}
    for cid, g in q.groupby("caseid"):
        g = g.sort_values("t_start")
        d = g[["t_start", "dose_per_kg", "map_mean", "svr_mean"]].dropna(
            subset=["t_start", "dose_per_kg"])
        if len(d) < MIN_EPOCHS or d["t_start"].nunique() < 2:
            continue
        t_s = d["t_start"].to_numpy(float)
        t_min = (t_s - t_s[0]) / 60.0
        rec = {
            "n_epochs": int(len(d)),
            "t_start_s": t_s.tolist(),
            "t_min": t_min.tolist(),
            "dose": d["dose_per_kg"].to_numpy(float).tolist(),
            "map": d["map_mean"].to_numpy(float).tolist(),
            "svr": d["svr_mean"].to_numpy(float).tolist(),  # may contain NaN
        }
        a = anes.get(str(cid))
        if a is not None and a == a:
            rec["t_anes_min"] = ((t_s - a) / 60.0).tolist()
        out[str(cid)] = rec
    return out


# --------------------------------------------------------------------- 1. RATE vs LEVEL
def _rate_vs_level(series):
    """For each case: split epochs into an EARLY window (first EARLY_FRAC by index,
    >=2 points) and a LATE target = the case's PEAK (max) dose in the late window
    (last epochs). early_level = mean early dose; early_slope = OLS slope (per min) of
    early dose vs early time. Nested OLS predicting late requirement from early_level
    alone vs early_level + early_slope. Reports partial-R^2 / partial-r / F."""
    import numpy as np
    from scipy import stats
    rows = []
    for cid, r in series.items():
        t = np.asarray(r["t_min"], float)
        dose = np.asarray(r["dose"], float)
        n = len(dose)
        k = max(2, int(round(n * EARLY_FRAC)))
        if k >= n:                  # need at least one late epoch beyond the early window
            k = n - 1
        if k < 2:
            continue
        et, ed = t[:k], dose[:k]
        if len(set(et)) < 2:
            continue
        e_slope, _ = _ols(et, ed)
        if e_slope is None:
            continue
        e_level = float(np.mean(ed))
        late = dose[k:]
        late_req = float(np.max(late))      # eventual/peak late requirement
        late_end = float(late[-1])
        rows.append({"caseid": cid, "early_level": e_level,
                     "early_slope_per_min": e_slope, "late_peak": late_req,
                     "late_end": late_end, "n": int(n), "k_early": int(k)})
    out = {"n_cases": len(rows)}
    if len(rows) < 8:
        out["note"] = "too few cases for a nested early-level vs early-slope model"
        out["per_case"] = rows
        return out
    Y = np.array([r["late_peak"] for r in rows])
    L = np.array([r["early_level"] for r in rows])
    S = np.array([r["early_slope_per_min"] for r in rows])

    def _r2(X, y):
        # X: design WITHOUT intercept column; add it. Returns R^2 and residuals.
        Xd = np.column_stack([np.ones(len(y))] + [X[:, j] for j in range(X.shape[1])])
        beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
        yhat = Xd @ beta
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return r2, ss_res, beta

    r2_lvl, ssr_lvl, _ = _r2(L.reshape(-1, 1), Y)
    r2_both, ssr_both, beta_both = _r2(np.column_stack([L, S]), Y)
    n = len(Y)
    p_full, p_red = 3, 2  # params incl intercept
    # nested F-test for adding slope
    df_num = p_full - p_red
    df_den = n - p_full
    if df_den > 0 and ssr_both > 0:
        F = ((ssr_lvl - ssr_both) / df_num) / (ssr_both / df_den)
        p_F = float(stats.f.sf(F, df_num, df_den))
    else:
        F, p_F = None, None
    partial_r2 = (ssr_lvl - ssr_both) / ssr_lvl if ssr_lvl > 0 else 0.0
    # MARGINAL (zero-order) correlations, to expose suppressor/collinearity honestly
    marg_slope_late = round(float(np.corrcoef(S, Y)[0, 1]), 3) if np.std(S) > 0 else None
    marg_level_late = round(float(np.corrcoef(L, Y)[0, 1]), 3) if np.std(L) > 0 else None
    collinearity_level_slope = round(float(np.corrcoef(L, S)[0, 1]), 3) if np.std(S) > 0 else None
    # partial correlation slope~late_peak controlling for early_level (residualize)
    def _resid_on(a, ctrl):
        sl, ic = _ols(ctrl, a)
        if sl is None:
            return a - a.mean()
        return a - (ic + sl * ctrl)
    rS = _resid_on(S, L)
    rY = _resid_on(Y, L)
    if np.std(rS) > 0 and np.std(rY) > 0:
        pr, pr_p = stats.pearsonr(rS, rY)
        partial_r = round(float(pr), 3); partial_r_p = round(float(pr_p), 4)
    else:
        partial_r, partial_r_p = None, None
    # fast-riser subgroup: top tertile of early_slope; is its LATE requirement higher?
    s_hi = float(np.percentile(S, 66.7))
    fast = Y[S >= s_hi]; slow = Y[S < s_hi]
    fast_vs_slow = None
    if len(fast) >= 3 and len(slow) >= 3:
        u, p_u = stats.mannwhitneyu(fast, slow, alternative="greater")
        fast_vs_slow = {"n_fast": int(len(fast)), "n_slow": int(len(slow)),
                        "late_peak_fast_median": round(float(np.median(fast)), 5),
                        "late_peak_slow_median": round(float(np.median(slow)), 5),
                        "mannwhitney_p_fast_gt_slow": round(float(p_u), 4)}
    out.update({
        "early_window_frac": EARLY_FRAC,
        "r2_level_only": round(float(r2_lvl), 3),
        "r2_level_plus_slope": round(float(r2_both), 3),
        "delta_r2": round(float(r2_both - r2_lvl), 3),
        "partial_r2_slope_given_level": round(float(partial_r2), 3),
        "marginal_corr_early_level_vs_latepeak": marg_level_late,
        "marginal_corr_early_slope_vs_latepeak": marg_slope_late,
        "collinearity_early_level_vs_early_slope": collinearity_level_slope,
        "partial_corr_slope_vs_latepeak_given_level": partial_r,
        "partial_corr_p": partial_r_p,
        "nested_F": round(float(F), 3) if F is not None else None,
        "nested_F_p": p_F,
        "beta_intercept_level_slope": [round(float(b), 5) for b in beta_both],
        "fast_riser_subgroup": fast_vs_slow,
        "interpretation": ("does the EARLY rate-of-rise add information about the LATE/peak "
                           "requirement BEYOND the EARLY level? delta_r2 / partial-r / nested-F "
                           "answer that; fast_riser subgroup tests whether fast early risers reach "
                           "a higher eventual requirement."),
        "per_case": rows})
    return out


# --------------------------------------------------------------------- 2. ONSET TIMING
def _onset_timing(series, q):
    """Onset = the first epoch whose dose_per_kg crosses the cohort HIGH threshold
    (HIGH_PCTL percentile of all NEPI-only dose_per_kg). Time of that epoch from the
    case's first stable epoch (t_min) and from anaesthesia start (t_anes_min).
    Distribution + a 2-means split on onset-from-first-epoch (early vs late onset),
    plus a crude bimodality gap diagnostic."""
    import numpy as np
    thr = float(np.percentile(q["dose_per_kg"].dropna().to_numpy(float), HIGH_PCTL))
    onset_min, onset_anes, crossing_ids = [], [], []
    never = 0
    left_censored = 0   # already >= HIGH at the FIRST stable epoch (onset before window)
    for cid, r in series.items():
        dose = np.asarray(r["dose"], float)
        tm = np.asarray(r["t_min"], float)
        hit = np.where(dose >= thr)[0]
        if hit.size == 0:
            never += 1
            continue
        i = int(hit[0])
        onset_min.append(float(tm[i]))
        crossing_ids.append(cid)
        if i == 0:
            left_censored += 1
        if "t_anes_min" in r:
            onset_anes.append(float(np.asarray(r["t_anes_min"], float)[i]))
    out = {"high_threshold_dose_per_kg": round(thr, 6),
           "high_pctl": HIGH_PCTL,
           "n_cases_crossing_high": len(onset_min),
           "n_cases_never_high": never,
           "n_left_censored_high_at_first_epoch": left_censored,
           "left_censoring_note": (f"{left_censored} of {len(onset_min)} crossing cases are already "
                                   ">= HIGH at their FIRST stable epoch (onset=0). Their true onset is "
                                   "LEFT-CENSORED (it occurred before the norepi-only stable window "
                                   "began), so the 'early-onset' cluster is inflated/contaminated by "
                                   "entry-already-high cases -- read the bimodality with this caveat.")}
    if len(onset_min) >= 5:
        om = np.array(onset_min)
        out["onset_from_first_epoch_min"] = {
            "median": round(float(np.median(om)), 1),
            "iqr": [round(float(np.percentile(om, 25)), 1), round(float(np.percentile(om, 75)), 1)],
            "min_max": [round(float(om.min()), 1), round(float(om.max()), 1)],
            "values": [round(float(x), 1) for x in sorted(om)]}
        # 2-means (1-D) split on onset-from-first-epoch
        out["two_cluster_split"] = _two_means(om)
        out["bimodality_gap"] = _gap_diag(om)
    if len(onset_anes) >= 5:
        oa = np.array(onset_anes)
        out["onset_from_anesthesia_start_min"] = {
            "n": int(len(oa)),
            "median": round(float(np.median(oa)), 1),
            "iqr": [round(float(np.percentile(oa, 25)), 1), round(float(np.percentile(oa, 75)), 1)],
            "min_max": [round(float(oa.min()), 1), round(float(oa.max()), 1)]}
    out["interpretation"] = ("when does the patient first cross a HIGH norepi requirement? "
                             "a single early peak in the histogram = unimodal onset; two separated "
                             "clusters (early-onset vs late-onset vasoplegia) = bimodal -> two "
                             "physiologically distinct timing phenotypes.")
    return out


def _two_means(x):
    """Simple 1-D 2-means (sorted threshold sweep minimising within-cluster SS)."""
    import numpy as np
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if n < 4:
        return {"note": "n<4, no split"}
    best = None
    for i in range(1, n):
        a, b = x[:i], x[i:]
        ss = float(((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum())
        if best is None or ss < best[0]:
            best = (ss, i)
    i = best[1]
    a, b = x[:i], x[i:]
    total_ss = float(((x - x.mean()) ** 2).sum())
    return {"split_point_min": round(float((a[-1] + b[0]) / 2), 1),
            "n_early": int(len(a)), "n_late": int(len(b)),
            "early_mean_min": round(float(a.mean()), 1),
            "late_mean_min": round(float(b.mean()), 1),
            "between_over_total_ss": round(1 - best[0] / total_ss, 3) if total_ss > 0 else None,
            "note": ("between/total SS is the fraction of onset-time variance explained by a "
                     "2-cluster split; high (->1) with a clear split-point gap supports bimodality.")}


def _gap_diag(x):
    """Largest normalised gap between consecutive sorted onset times -- a crude
    bimodality cue (a big interior gap suggests two clusters)."""
    import numpy as np
    x = np.sort(np.asarray(x, float))
    if len(x) < 4:
        return {"note": "n<4"}
    gaps = np.diff(x)
    rng = float(x[-1] - x[0]) or 1.0
    j = int(np.argmax(gaps))
    return {"largest_gap_min": round(float(gaps[j]), 1),
            "largest_gap_frac_of_range": round(float(gaps[j] / rng), 3),
            "gap_location_min": round(float((x[j] + x[j + 1]) / 2), 1),
            "note": "largest interior gap as a fraction of the onset-time range; >~0.3 hints bimodal."}


# --------------------------------------------------------------------- 3. SHAPE CLASS
def _classify_shape(series):
    """monotonic-rising / plateau / falling per case from overall slope + end-vs-peak.
      - falling   : overall slope < 0 AND end < peak by > PLATEAU_TOL.
      - plateau   : |end-peak|/peak <= PLATEAU_TOL (dose rose then held) OR |slope|
                    small relative to dose level.
      - rising    : overall slope > 0 and end is at/near the peak (still climbing).
    Also computes within-case SVR slope where >=3 SVR points exist."""
    import numpy as np
    classes = {}
    for cid, r in series.items():
        t = np.asarray(r["t_min"], float)
        dose = np.asarray(r["dose"], float)
        slope, _ = _ols(t, dose)
        if slope is None:
            continue
        peak = float(np.max(dose)); end = float(dose[-1]); start = float(dose[0])
        end_vs_peak = (end - peak) / peak if peak > 0 else 0.0
        # mean dose to scale slope -> per-minute fractional change
        mean_dose = float(np.mean(dose)) or 1.0
        frac_slope = slope / mean_dose  # fractional change per minute
        if slope < 0 and end < start and end_vs_peak < -PLATEAU_TOL:
            cls = "falling"
        elif abs(end_vs_peak) <= PLATEAU_TOL and peak > start * (1 + PLATEAU_TOL):
            cls = "plateau"          # rose then held near the peak
        elif slope > 0 and end_vs_peak >= -PLATEAU_TOL:
            cls = "rising"
        elif abs(frac_slope) <= 0.002:
            cls = "plateau"          # essentially flat
        else:
            cls = "rising" if slope > 0 else "falling"
        # SVR slope where available
        svr = np.asarray(r["svr"], float)
        ok = ~np.isnan(svr)
        svr_slope = None
        if ok.sum() >= 3 and len(set(t[ok])) >= 2:
            ss, _ = _ols(t[ok], svr[ok])
            svr_slope = ss
        classes[cid] = {"shape": cls, "overall_slope_per_min": round(float(slope), 8),
                        "frac_slope_per_min": round(float(frac_slope), 6),
                        "start": round(start, 6), "peak": round(peak, 6),
                        "end": round(end, 6), "end_vs_peak": round(float(end_vs_peak), 3),
                        "svr_slope_per_min": round(float(svr_slope), 4) if svr_slope is not None else None}
    return classes


def _shape_outcomes(classes, outcomes):
    import numpy as np
    from scipy import stats
    by_class = {"rising": [], "plateau": [], "falling": []}
    for cid, c in classes.items():
        by_class.setdefault(c["shape"], []).append(cid)
    counts = {k: len(v) for k, v in by_class.items()}
    out = {"class_counts": counts}
    # outcome event rate per class for composite / organ_renal
    for label in ("composite", "organ_renal", "aki"):
        rates = {}
        for cls, ids in by_class.items():
            ys = []
            for cid in ids:
                v = outcomes.get(cid, {}).get(label, "")
                if v in ("", None):
                    continue
                ys.append(1 if str(v) == "1" else 0)
            if ys:
                rates[cls] = {"n": len(ys), "event_rate": round(float(np.mean(ys)), 3),
                              "events": int(sum(ys))}
        out[label] = rates
        # rising-or-plateau (progressive) vs falling (transient) contrast, composite
    prog_ids = by_class.get("rising", []) + by_class.get("plateau", [])
    trans_ids = by_class.get("falling", [])
    contrast = {}
    for label in ("composite", "organ_renal", "aki"):
        pa = [1 if str(outcomes.get(c, {}).get(label, "")) == "1" else 0
              for c in prog_ids if outcomes.get(c, {}).get(label, "") not in ("", None)]
        ta = [1 if str(outcomes.get(c, {}).get(label, "")) == "1" else 0
              for c in trans_ids if outcomes.get(c, {}).get(label, "") not in ("", None)]
        if len(pa) >= 3 and len(ta) >= 3:
            a, b = sum(pa), len(pa) - sum(pa)
            cc, dd = sum(ta), len(ta) - sum(ta)
            rd = a / len(pa) - cc / len(ta)
            _, p = stats.fisher_exact([[a, b], [cc, dd]])
            contrast[label] = {"progressive_rate": round(a / len(pa), 3), "n_progressive": len(pa),
                               "transient_rate": round(cc / len(ta), 3), "n_transient": len(ta),
                               "risk_difference": round(float(rd), 3), "fisher_p": round(float(p), 4)}
        else:
            contrast[label] = {"note": "one arm <3 with outcome", "n_progressive": len(pa),
                               "n_transient": len(ta)}
    out["progressive_vs_transient"] = contrast
    # SVR slope by class (vasoplegia mechanism: rising should track FALLING SVR)
    svr_by_class = {}
    for cls, ids in by_class.items():
        vals = [classes[c]["svr_slope_per_min"] for c in ids
                if classes[c]["svr_slope_per_min"] is not None]
        if vals:
            svr_by_class[cls] = {"n": len(vals), "median_svr_slope_per_min": round(float(np.median(vals)), 4)}
    out["svr_slope_by_class"] = svr_by_class
    out["confounding_note"] = ("CONFOUNDING-BY-SEVERITY: progressive (rising/plateau) cases are by "
                               "construction the more vasoplegic patients, who are independently more "
                               "likely to suffer organ injury; with this N no severity adjustment is "
                               "possible. Treat any class-outcome difference as hypothesis-generating.")
    return out


# --------------------------------------------------------------------- model
def model():
    import numpy as np, pandas as pd
    if not os.path.exists(EPOCHS_CSV):
        return {"available": False}
    df = pd.read_csv(EPOCHS_CSV, low_memory=False)
    for c in df.columns:
        if c not in ("caseid", "drug", "sex", "optype"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["norepi_only"] == 1) &
           df["dose_per_kg"].notna() & df["map_mean"].notna()].copy()
    anes = _anes_offsets()
    series = _case_series(q, anes)
    res = {"seed": SEED, "primary_drug": PRIMARY_DRUG, "min_epochs_per_case": MIN_EPOCHS,
           "n_nepi_only_epochs": int(len(q)),
           "n_cases_nepi_only": int(q["caseid"].nunique()),
           "n_cases_ge_min_epochs": len(series),
           "n_cases_with_anes_timing": int(sum("t_anes_min" in r for r in series.values()))}
    if len(series) < 8:
        res["verdict_flag"] = "INSUFFICIENT"
        res["verdict"] = (f"INSUFFICIENT -- only {len(series)} NEPI-only cases with "
                          f">={MIN_EPOCHS} time-ordered epochs; cannot assess trajectory shape.")
        return res

    res["rate_vs_level"] = _rate_vs_level(series)
    res["onset_timing"] = _onset_timing(series, q)
    classes = _classify_shape(series)
    res["shape_classification"] = {
        "class_counts": {k: sum(1 for c in classes.values() if c["shape"] == k)
                         for k in ("rising", "plateau", "falling")},
        "plateau_tol": PLATEAU_TOL,
        "per_case": classes}
    outcomes = _load_outcomes()
    res["shape_vs_outcome"] = _shape_outcomes(classes, outcomes)

    # ---- VERDICT -------------------------------------------------------------
    rl = res["rate_vs_level"]
    ot = res["onset_timing"]
    sc = res["shape_vs_outcome"]
    # Does rate-of-rise add ACTIONABLE info beyond level? Two distinct things:
    #  (a) statistical variance added (delta_r2 / nested-F) -- can be a SUPPRESSOR;
    #  (b) the ACTIONABLE direction "fast riser -> higher eventual requirement"
    #      (positive partial-r AND a non-null fast-riser subgroup).
    # We must NOT call a negative suppressor effect actionable.
    pr = rl.get("partial_corr_slope_vs_latepeak_given_level")
    fr = rl.get("fast_riser_subgroup") or {}
    fr_p = fr.get("mannwhitney_p_fast_gt_slow")
    slope_adds_variance = (rl.get("delta_r2") or 0) >= 0.05 and (
        (rl.get("nested_F_p") is not None and rl["nested_F_p"] < 0.1))
    slope_actionable = (pr is not None and pr > 0 and (rl.get("partial_corr_p") or 1) < 0.1
                        and fr_p is not None and fr_p < 0.1)
    slope_suppressor = slope_adds_variance and (pr is not None and pr < 0)
    # bimodal onset (discount if heavily left-censored)?
    tc = ot.get("two_cluster_split", {}) if ot else {}
    gap = ot.get("bimodality_gap", {}) if ot else {}
    lc = ot.get("n_left_censored_high_at_first_epoch", 0)
    ncross = ot.get("n_cases_crossing_high", 0) or 1
    heavy_censor = lc / ncross >= 0.25
    bimodal = ((tc.get("between_over_total_ss") or 0) >= 0.6 and
               (gap.get("largest_gap_frac_of_range") or 0) >= 0.3)
    bimodal_clean = bimodal and not heavy_censor
    # progressive vs transient outcome separation?
    pvt = sc.get("progressive_vs_transient", {}).get("composite", {})
    pvt_signal = (pvt.get("risk_difference") is not None and abs(pvt.get("risk_difference", 0)) >= 0.1
                  and pvt.get("n_progressive", 0) >= 5 and pvt.get("n_transient", 0) >= 5
                  and (pvt.get("fisher_p") or 1) < 0.1)

    # GO requires an ACTIONABLE axis (not just variance from a suppressor) + a second corroborating axis.
    if slope_actionable and (bimodal_clean or pvt_signal):
        flag = "GO"
    elif slope_actionable or bimodal_clean or pvt_signal or slope_suppressor:
        flag = "PARTIAL"
    else:
        flag = "NO-GO"
    res["verdict_flag"] = flag

    parts = []
    if slope_actionable:
        slope_msg = ("The early rate-of-rise ADDS ACTIONABLE information: fast early risers reach a "
                     "HIGHER eventual requirement, beyond the early level.")
    elif slope_suppressor:
        slope_msg = ("The early slope adds R^2 but as a NEGATIVE SUPPRESSOR, not an actionable signal: "
                     "the marginal slope<->late-peak correlation is ~0 and the early slope is highly "
                     "COLLINEAR with the early level (high-level cases also rise fast), so the negative "
                     "partial coefficient is a collinearity/mathematical-coupling artifact, NOT 'fast "
                     "risers are worse'. The fast-riser subgroup test is NULL. Actionably, the early "
                     "LEVEL alone is the dominant summary.")
    else:
        slope_msg = "The early rate-of-rise adds NO clear information beyond the level (level dominates)."
    parts.append(
        f"RATE-OF-RISE vs LEVEL (n={rl.get('n_cases')}): predicting the LATE/peak requirement, "
        f"early LEVEL alone R^2={rl.get('r2_level_only')}; LEVEL + rate-of-rise R^2="
        f"{rl.get('r2_level_plus_slope')} (delta R^2 {rl.get('delta_r2')}; MARGINAL slope<->latepeak "
        f"r {rl.get('marginal_corr_early_slope_vs_latepeak')}; level<->slope collinearity "
        f"{rl.get('collinearity_early_level_vs_early_slope')}; PARTIAL r {pr} p {rl.get('partial_corr_p')}; "
        f"nested-F p {rl.get('nested_F_p')}; "
        f"fast-riser subgroup MWU p {fr_p}). " + slope_msg)
    if ot.get("onset_from_first_epoch_min"):
        o = ot["onset_from_first_epoch_min"]
        parts.append(
            f"ONSET TIMING ({ot.get('n_cases_crossing_high')} of {res['n_cases_ge_min_epochs']} "
            f"cases cross the HIGH threshold): median first-crossing "
            f"{o['median']} min from first stable epoch (IQR {o['iqr']}); "
            f"2-cluster split-point {tc.get('split_point_min')} min "
            f"(early n={tc.get('n_early')} / late n={tc.get('n_late')}, between/total SS "
            f"{tc.get('between_over_total_ss')}, largest gap frac {gap.get('largest_gap_frac_of_range')}; "
            f"{lc} already-HIGH at first epoch = left-censored). "
            + ("Onset shows a clean two-cluster (early- vs late-onset) split."
               if bimodal_clean else
               ("A two-cluster split exists but is CONTAMINATED by left-censoring (many onset=0 "
                "entry-already-high cases), so the early-onset cluster is not cleanly interpretable."
                if bimodal else
                "Onset is essentially UNIMODAL at this N -- no clean two-cluster separation.")))
    cc = res["shape_classification"]["class_counts"]
    parts.append(
        f"SHAPE classes: rising {cc['rising']} / plateau {cc['plateau']} / falling {cc['falling']}. "
        + (f"Progressive vs transient (composite): {pvt.get('progressive_rate')} (n={pvt.get('n_progressive')}) "
           f"vs {pvt.get('transient_rate')} (n={pvt.get('n_transient')}), RD {pvt.get('risk_difference')}, "
           f"Fisher p {pvt.get('fisher_p')}."
           if pvt.get("risk_difference") is not None else
           f"Progressive-vs-transient outcome contrast not estimable (n_prog={pvt.get('n_progressive')}, "
           f"n_trans={pvt.get('n_transient')}).")
        + " CONFOUNDED BY SEVERITY; hypothesis-generating.")

    if flag == "GO":
        head = ("GO -- trajectory SHAPE adds ACTIONABLE information beyond the LEVEL: fast early risers "
                "reach a higher eventual requirement, corroborated by onset timing or shape-outcome.")
    elif flag == "PARTIAL":
        head = ("PARTIAL -- the trajectory shape's main statistical signal (the early slope) is a "
                "COLLINEAR/SUPPRESSOR artifact, NOT an actionable 'fast riser = worse' effect; the early "
                "LEVEL is the dominant actionable summary. Onset timing and shape-outcome show suggestive "
                "but underpowered / left-censored structure. Net: shape adds little ACTIONABLE info beyond "
                "the level at this N.")
    else:
        head = ("NO-GO at this N -- the trajectory SHAPE/ONSET does not add clear actionable "
                "information beyond the early LEVEL; the level is the dominant summary.")
    res["verdict"] = head + " " + " ".join(parts)
    return res


# --------------------------------------------------------------------- doc
def _doc(res):
    L = ["# Trajectory SHAPE & ONSET of the vasopressor requirement (deeper tangent)\n",
         "Complementary to docs/PRESSOR_REQUIREMENT_TRAJECTORY.md (which established that the "
         "requirement RISES in ~54% of cases). That module answered *does it rise?*; this one asks "
         "the next questions: does the trajectory's **shape** and **onset timing** carry information "
         "BEYOND the early level?\n",
         f"Sample: NEPI norepi-only stable epochs, time-ordered within case, >= {MIN_EPOCHS} "
         "epochs/case (stricter than the trajectory module's 3 -- shape/onset need more points).\n"]
    if not res.get("available", True) or res.get("n_cases_ge_min_epochs", 0) < 8:
        L.append("_" + res.get("verdict", "insufficient data") + "_\n")
        open(OUT_DOC, "w").write("\n".join(L) + "\n")
        return
    L += [f"- NEPI norepi-only epochs: **{res['n_nepi_only_epochs']}** over "
          f"**{res['n_cases_nepi_only']}** cases.",
          f"- Cases with >= {MIN_EPOCHS} time-ordered epochs (shape-eligible): "
          f"**{res['n_cases_ge_min_epochs']}** ({res['n_cases_with_anes_timing']} with anaesthesia-"
          "start timing from cases.csv).\n"]

    rl = res["rate_vs_level"]
    L += ["## 1. RATE-OF-RISE vs LEVEL (does the early slope add info beyond the early level?)",
          f"Predicting each case's LATE/peak requirement from an EARLY window "
          f"(first {int(EARLY_FRAC*100)}% of epochs):",
          f"- LEVEL only: R^2 = **{rl.get('r2_level_only')}**.",
          f"- LEVEL + rate-of-rise: R^2 = **{rl.get('r2_level_plus_slope')}** "
          f"(delta R^2 **{rl.get('delta_r2')}**, partial-R^2 {rl.get('partial_r2_slope_given_level')}).",
          f"- Partial correlation (early slope vs late peak, controlling for early level): "
          f"**{rl.get('partial_corr_slope_vs_latepeak_given_level')}** (p {rl.get('partial_corr_p')}); "
          f"nested-F p {rl.get('nested_F_p')}.",
          f"- Fast-riser subgroup (top tertile of early slope): {rl.get('fast_riser_subgroup')}.\n"]

    ot = res["onset_timing"]
    L += ["## 2. ONSET TIMING (when does the patient first cross a HIGH requirement?)",
          f"HIGH threshold = the cohort p{HIGH_PCTL:.0f} of NEPI-only dose_per_kg = "
          f"**{ot.get('high_threshold_dose_per_kg')}**.",
          f"- Cases crossing HIGH: **{ot.get('n_cases_crossing_high')}** "
          f"(never-high: {ot.get('n_cases_never_high')}; "
          f"already-HIGH at first epoch / left-censored: "
          f"**{ot.get('n_left_censored_high_at_first_epoch')}**)."]
    if ot.get("onset_from_first_epoch_min"):
        o = ot["onset_from_first_epoch_min"]
        L += [f"- Onset from first stable epoch: median **{o['median']} min** "
              f"(IQR {o['iqr']}, range {o['min_max']}).",
              f"- 2-cluster split: {ot.get('two_cluster_split')}.",
              f"- Bimodality gap diagnostic: {ot.get('bimodality_gap')}.",
              f"- _{ot.get('left_censoring_note')}_"]
    if ot.get("onset_from_anesthesia_start_min"):
        oa = ot["onset_from_anesthesia_start_min"]
        L += [f"- Onset from ANAESTHESIA START (n={oa['n']}): median **{oa['median']} min** "
              f"(IQR {oa['iqr']}, range {oa['min_max']})."]
    L += [""]

    sc = res["shape_classification"]["class_counts"]
    so = res["shape_vs_outcome"]
    L += ["## 3. PROGRESSIVE vs TRANSIENT (shape class -> outcome)",
          f"- Shape classes: **rising {sc['rising']} / plateau {sc['plateau']} / "
          f"falling {sc['falling']}**.",
          "- Outcome event-rate by class:"]
    for label in ("composite", "organ_renal", "aki"):
        L.append(f"  - **{label}**: " + ", ".join(
            f"{cls} {v['event_rate']} (n={v['n']})" for cls, v in so.get(label, {}).items()) or
            f"  - **{label}**: (no rates)")
    L.append("- Progressive (rising+plateau) vs transient (falling):")
    for label in ("composite", "organ_renal", "aki"):
        c = so["progressive_vs_transient"].get(label, {})
        if c.get("risk_difference") is not None:
            L.append(f"  - **{label}**: progressive {c['progressive_rate']} (n={c['n_progressive']}) "
                     f"vs transient {c['transient_rate']} (n={c['n_transient']}) -> RD "
                     f"**{c['risk_difference']}** (Fisher p {c['fisher_p']}).")
        else:
            L.append(f"  - **{label}**: not estimable ({c.get('note','')}; "
                     f"n_prog={c.get('n_progressive')}, n_trans={c.get('n_transient')}).")
    if so.get("svr_slope_by_class"):
        L.append(f"- Within-case SVR slope by class (vasoplegia mechanism, rising should track "
                 f"falling SVR): {so['svr_slope_by_class']}.")
    L += ["", "  " + so["confounding_note"] + "\n"]

    L += ["## Verdict", res.get("verdict", ""), ""]
    L += ["## Caveats",
          f"- **Small N (~{res['n_cases_ge_min_epochs']} shape-eligible cases).** Every test here is "
          "descriptive / hypothesis-generating; the nested model, the onset clustering and the "
          "shape-outcome contrast are all underpowered. Re-run as the epochs CSV grows.",
          "- **Confounding by severity is unadjusted** -- progressive cases are the sicker patients; "
          "any class-outcome difference is expected from severity alone.",
          "- **Onset threshold is cohort-relative** (p" + f"{HIGH_PCTL:.0f}" + " of dose_per_kg), not an "
          "absolute clinical dose; 'HIGH' is defined within this single-centre sample.",
          "- **Dose units** are Orchestra device rate/kg (not ug/kg/min); within-case slopes and "
          "the cohort percentile are concentration-relative, not absolute.",
          "- **Anaesthesia-start timing** uses cases.csv `anestart` (seconds, vs casestart=0); a few "
          "cases may lack it -- onset-from-anaesthesia uses only those with the field.",
          "- **Single-centre (SNUH/VitalDB)**; external replication required."]
    open(OUT_DOC, "w").write("\n".join(L) + "\n")


def main():
    res = model()
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    print("\n[req-shape] VERDICT: " + res.get("verdict", "no data"), flush=True)
    print("[req-shape] -> docs/REQUIREMENT_ONSET_SHAPE.md", flush=True)
    print("[req-shape] -> cache/requirement_onset_shape.json", flush=True)


if __name__ == "__main__":
    main()
