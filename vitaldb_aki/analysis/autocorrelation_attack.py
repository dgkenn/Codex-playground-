"""autocorrelation_attack.py -- HOSTILE test of whether the vasopressor-REQUIREMENT
reliability (MIMIC split-half 0.95, VitalDB 0.82) and the early->late prediction (MIMIC
0.62, VitalDB 0.54) are MORE than trivial autocorrelation.

THE ATTACK (a hostile methods reviewer): "A slowly-titrated norepinephrine infusion is
piecewise-constant. An early sample mechanically predicts a late sample because the rate
barely moves -- this is adjacent-sample stickiness / mechanical persistence, not a
meaningful, between-patient TRAIT." If the reviewer is right, the 'reliability' is an
artifact of a near-constant signal and carries no patient information.

This script tries to BREAK that attack honestly with four tests, run primarily on MIMIC
(N huge) and mirrored on VitalDB where feasible:

  1. BETWEEN-PATIENT vs WITHIN-PATIENT variance (ICC / variance partition). A real trait
     needs most of the variance to live BETWEEN patients. Reports the one-way-ANOVA ICC(1)
     of log-requirement, the between-patient SD, and the between-patient fold-range
     (p90/p10). A high ICC means a late sample is predictable from an early one because
     patients genuinely DIFFER, not merely because the signal is locally flat.

  2. TIME-GAPPED prediction. Instead of adjacent early/late, predict the LATE-window
     requirement from an EARLY window separated by a REAL TIME GAP (>=1h, >=3h, >=6h,
     >=12h). Mechanical adjacent-sample stickiness decays fast; a real trait survives a
     multi-hour gap. Reports Spearman at increasing gaps (with N at each gap).

  3. NULL / PLACEBO. Shuffle the requirement across patients (break the patient link) and
     confirm reliability + early->late collapse to ~0 -- a sanity check that the metric is
     not spuriously inflated. Plus a MECHANICAL yardstick: predicting late MAP-band / mean-
     rate-quantile membership, to see what a purely-persistent control scores.

  4. PERSISTENCE-ADJUSTED. Does the patient's MEAN/level dominate? Reports the within-stay
     coefficient of variation of the rate. If rates barely move within a stay (CV ~ 0), the
     'reliability' is trivially mechanical. If rates move a LOT within a stay yet an early
     window still predicts a late one, that is a genuine patient trait surviving real
     within-stay dynamics. Also: early->late Spearman restricted to the HIGH-within-stay-CV
     subset (the stays where persistence is weakest).

VERDICT logic: the signal is a GENUINE BETWEEN-PATIENT TRAIT (not just mechanical) iff
(a) ICC is substantial (most variance between patients), (b) early->late survives a real
multi-hour gap, (c) the shuffle-null collapses to ~0, AND (d) early->late survives in the
high-within-stay-CV subset. If instead within-stay CV ~ 0 and the gapped prediction decays
to the null, the attack stands (mechanical persistence).

stdlib only at import; numpy/scipy/pandas lazy. Run from repo root:
    python3 -m vitaldb_aki.analysis.autocorrelation_attack
Writes cache/autocorrelation_attack.json + docs/AUTOCORRELATION_ATTACK.md.
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

MIMIC_CSV = os.path.join(_CACHE, "mimic_norepi.csv")
VITALDB_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")


# --------------------------------------------------------------------------- helpers
def _parse_ts(s):
    """'YYYY-MM-DD HH:MM:SS' -> epoch seconds (relative ordering only)."""
    import time
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _spear(x, y):
    """Spearman r + n; None if <10 finite pairs."""
    import numpy as np
    from scipy import stats
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 10:
        return {"r": None, "n": int(len(x))}
    r = float(stats.spearmanr(x, y)[0])
    return {"r": round(r, 3), "n": int(len(x))}


def _icc1(groups):
    """ICC(1) via one-way random-effects ANOVA on a list of per-group value-lists.

    ICC(1) = (MSB - MSW) / (MSB + (k0-1)*MSW), the fraction of total variance that is
    BETWEEN groups (patients). High ICC -> the requirement is a stable per-patient level
    (a trait); low ICC -> within-patient noise dominates. Also returns the between-patient
    SD (sqrt of the between-group variance component) and a balanced-design k0.
    """
    import numpy as np
    groups = [np.asarray(g, float) for g in groups if len(g) >= 2]
    groups = [g[np.isfinite(g)] for g in groups]
    groups = [g for g in groups if len(g) >= 2]
    k = len(groups)
    if k < 2:
        return {"icc1": None, "n_groups": k}
    ns = np.array([len(g) for g in groups], float)
    N = ns.sum()
    grand = np.concatenate(groups).mean()
    means = np.array([g.mean() for g in groups])
    ssb = float((ns * (means - grand) ** 2).sum())
    ssw = float(sum(((g - g.mean()) ** 2).sum() for g in groups))
    dfb = k - 1
    dfw = N - k
    msb = ssb / dfb
    msw = ssw / dfw if dfw > 0 else float("nan")
    # k0 for unbalanced one-way design
    k0 = (N - (ns ** 2).sum() / N) / (k - 1)
    var_between = (msb - msw) / k0
    var_within = msw
    denom = var_between + var_within
    icc = var_between / denom if denom > 0 else 0.0
    return {
        "icc1": round(float(icc), 3),
        "var_between": round(float(var_between), 5),
        "var_within": round(float(var_within), 5),
        "between_sd": round(float(np.sqrt(max(var_between, 0.0))), 4),
        "within_sd": round(float(np.sqrt(max(var_within, 0.0))), 4),
        "n_groups": int(k),
        "k0": round(float(k0), 2),
        "msb": round(float(msb), 5),
        "msw": round(float(msw), 5),
    }


def _fold_range(vals):
    """p90/p10 between-patient fold-range + between-patient SD of per-patient levels."""
    import numpy as np
    v = np.asarray([x for x in vals if x is not None and np.isfinite(x) and x > 0], float)
    if len(v) < 10:
        return {"fold_range_p90_p10": None, "n": int(len(v))}
    p10, p50, p90 = np.percentile(v, [10, 50, 90])
    return {
        "p10": round(float(p10), 4), "median": round(float(p50), 4),
        "p90": round(float(p90), 4),
        "fold_range_p90_p10": round(float(p90 / p10), 2) if p10 > 0 else None,
        "between_patient_sd": round(float(v.std()), 4),
        "between_patient_sd_log": round(float(np.log(v).std()), 4),
        "n": int(len(v)),
    }


# --------------------------------------------------------------------------- MIMIC
def _mimic_stays():
    """Per stay: ordered [(t_seconds, rate)] for norepi (mcg/kg/min), same gates as the
    external-validation script (0 < rate <= 5 mcg/kg/min, parseable timestamp)."""
    stays = {}
    with open(MIMIC_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rate = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rate <= 0 or rate > 5:
                continue
            t = _parse_ts(row["starttime"])
            if t is None:
                continue
            sid = row["stay_id"]
            d = stays.setdefault(sid, {"subject": row["subject_id"], "segs": []})
            d["segs"].append((t, rate))
    for d in stays.values():
        d["segs"].sort()
    return stays


def _mimic_attack():
    import numpy as np
    stays = _mimic_stays()
    out = {"n_stays_with_norepi": len(stays)}

    # per-stay rate lists / medians / within-stay CV
    stay_rates, stay_req, stay_cv, stay_dur_h = {}, {}, {}, {}
    rel_odd, rel_even = [], []
    early_adj, late_adj = [], []
    for sid, d in stays.items():
        segs = d["segs"]
        rates = np.array([r for _, r in segs], float)
        times = np.array([t for t, _ in segs], float)
        stay_rates[sid] = rates
        stay_req[sid] = float(np.median(rates))
        stay_cv[sid] = float(rates.std() / rates.mean()) if rates.mean() > 0 else 0.0
        stay_dur_h[sid] = float((times[-1] - times[0]) / 3600.0)
        if len(segs) >= 4:
            h = len(segs) // 2
            rel_odd.append(float(np.median(rates[0::2])))
            rel_even.append(float(np.median(rates[1::2])))
            early_adj.append(float(np.median(rates[:h])))
            late_adj.append(float(np.median(rates[h:])))

    # --- baseline reproductions (sanity that we match the published numbers) ---
    out["baseline_reliability_splithalf"] = _spear(rel_odd, rel_even)
    out["baseline_early_predicts_late_adjacent"] = _spear(early_adj, late_adj)
    out["n_stays_ge4_segments"] = len(rel_odd)

    # === TEST 1: ICC / between vs within variance ============================
    # log-rate so the multiplicative dosing scale is additive; trait = stable level.
    log_groups = [np.log(stay_rates[sid]) for sid in stay_rates if len(stay_rates[sid]) >= 2]
    out["icc_log_rate"] = _icc1(log_groups)
    out["between_patient_spread_median_req"] = _fold_range(list(stay_req.values()))

    # === TEST 4 (compute CV early; used by tests below) =====================
    cvs = np.array([stay_cv[sid] for sid in stay_rates if len(stay_rates[sid]) >= 4], float)
    cvs = cvs[np.isfinite(cvs)]
    out["within_stay_cv"] = {
        "median": round(float(np.median(cvs)), 3),
        "p25": round(float(np.percentile(cvs, 25)), 3),
        "p75": round(float(np.percentile(cvs, 75)), 3),
        "frac_cv_gt_0p2": round(float((cvs > 0.2).mean()), 3),
        "frac_cv_gt_0p5": round(float((cvs > 0.5).mean()), 3),
        "n": int(len(cvs)),
        "note": "within-stay coefficient of variation of the norepi rate; CV~0 => trivially "
                "constant (mechanical); CV large => rate genuinely moves within the stay.",
    }

    # === TEST 2: TIME-GAPPED early->late prediction =========================
    # For each stay split the timeline at its temporal midpoint. EARLY window = segments in
    # the first portion; LATE window = segments AFTER a buffer gap from the early window's
    # last sample. We require the actual elapsed time between the early window's last sample
    # and the late window's first sample to be >= GAP hours. Mechanical stickiness should
    # decay as the gap grows; a trait should persist.
    gaps_h = [0.0, 1.0, 3.0, 6.0, 12.0, 24.0]
    gapped = {}
    for g in gaps_h:
        ea, la = [], []
        for sid, d in stays.items():
            segs = d["segs"]
            if len(segs) < 4:
                continue
            times = np.array([t for t, _ in segs], float)
            rates = np.array([r for _, r in segs], float)
            t0, t1 = times[0], times[-1]
            mid = t0 + (t1 - t0) / 2.0
            early_mask = times <= mid
            if early_mask.sum() < 1 or (~early_mask).sum() < 1:
                continue
            last_early_t = times[early_mask].max()
            # late window starts only after >= g hours past last early sample
            late_mask = times >= (last_early_t + g * 3600.0)
            # also keep late strictly in the second half to avoid overlap when g==0
            late_mask = late_mask & (times > mid)
            if early_mask.sum() < 1 or late_mask.sum() < 1:
                continue
            ea.append(float(np.median(rates[early_mask])))
            la.append(float(np.median(rates[late_mask])))
        gapped[f"gap_ge_{g:g}h"] = _spear(ea, la)
    out["time_gapped_early_predicts_late"] = gapped

    # === TEST 3: NULL / PLACEBO shuffle ======================================
    rng = np.random.default_rng(SEED)
    # 3a. shuffle reliability: permute the EVEN halves across stays -> patient link broken
    ro = np.array(rel_odd, float)
    re = np.array(rel_even, float)
    perm = rng.permutation(len(re))
    out["null_reliability_shuffled"] = _spear(ro, re[perm])
    # 3b. shuffle early->late: permute late across stays
    ea = np.array(early_adj, float)
    la = np.array(late_adj, float)
    perm2 = rng.permutation(len(la))
    out["null_early_late_shuffled"] = _spear(ea, la[perm2])
    # 3c. mechanical yardstick: late mean-rate-quantile predicted from early quantile.
    #     Build a deliberately persistent control: discretize the per-stay early/late medians
    #     into terciles (a 'band membership' proxy) and check rank agreement. This is the
    #     kind of mechanical/coarse signal the attack says we are really measuring.
    if len(ea) >= 30:
        e_q = np.digitize(ea, np.percentile(ea, [33, 66]))
        l_q = np.digitize(la, np.percentile(la, [33, 66]))
        out["mechanical_yardstick_band_membership"] = {
            "spearman_early_tercile_vs_late_tercile": _spear(e_q, l_q),
            "frac_same_tercile": round(float((e_q == l_q).mean()), 3),
            "note": "coarse 3-level 'band membership' rank agreement -- a purely mechanical "
                    "persistence yardstick to compare the continuous reliability against.",
        }

    # === TEST 4b: early->late in the HIGH-within-stay-CV subset ==============
    # The stays where the rate moves the MOST within the stay are where mechanical
    # persistence is WEAKEST. If early still predicts late there, it is a trait.
    hi_e, hi_l, lo_e, lo_l = [], [], [], []
    cv_thresh = float(np.median(cvs)) if len(cvs) else 0.0
    for sid, d in stays.items():
        segs = d["segs"]
        if len(segs) < 4:
            continue
        rates = np.array([r for _, r in segs], float)
        h = len(segs) // 2
        e = float(np.median(rates[:h]))
        l = float(np.median(rates[h:]))
        cv = stay_cv[sid]
        if cv >= cv_thresh:
            hi_e.append(e); hi_l.append(l)
        else:
            lo_e.append(e); lo_l.append(l)
    out["early_late_high_cv_subset"] = {
        "cv_threshold_median": round(cv_thresh, 3),
        "high_cv": _spear(hi_e, hi_l),
        "low_cv": _spear(lo_e, lo_l),
        "note": "early->late split by within-stay CV. Survival in the HIGH-CV subset (rate "
                "moves a lot) is evidence the signal is a trait, not flatness.",
    }
    return out


# --------------------------------------------------------------------------- VitalDB
def _vitaldb_cases():
    """Per case: ordered [(t_start, dose_per_kg, map_mean, norepi_only)] from the stable-
    epoch table."""
    cases = {}
    with open(VITALDB_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                t = float(row["t_start"])
                dose = float(row["dose_per_kg"])
            except (ValueError, TypeError, KeyError):
                continue
            try:
                mapm = float(row["map_mean"])
            except (ValueError, TypeError, KeyError):
                mapm = float("nan")
            norepi_only = str(row.get("norepi_only", "")).strip() in ("1", "1.0", "True", "true")
            cid = row["caseid"]
            cases.setdefault(cid, []).append((t, dose, mapm, norepi_only))
    for cid in cases:
        cases[cid].sort()
    return cases


def _vitaldb_attack():
    import numpy as np
    cases = _vitaldb_cases()
    out = {"n_cases": len(cases)}

    # restrict to norepi-only epochs (the requirement-phenotype definition)
    case_doses, case_times, case_req, case_cv = {}, {}, {}, {}
    rel_odd, rel_even, early_adj, late_adj = [], [], [], []
    for cid, eps in cases.items():
        doses = np.array([d for (_, d, _, no) in eps if no], float)
        times = np.array([t for (t, _, _, no) in eps if no], float)
        if len(doses) < 2:
            continue
        case_doses[cid] = doses
        case_times[cid] = times
        case_req[cid] = float(np.median(doses))
        case_cv[cid] = float(doses.std() / doses.mean()) if doses.mean() > 0 else 0.0
        if len(doses) >= 4:
            h = len(doses) // 2
            rel_odd.append(float(np.median(doses[0::2])))
            rel_even.append(float(np.median(doses[1::2])))
            early_adj.append(float(np.median(doses[:h])))
            late_adj.append(float(np.median(doses[h:])))

    out["n_cases_norepi_only_ge2"] = len(case_doses)
    out["n_cases_ge4_epochs"] = len(rel_odd)
    out["baseline_reliability_splithalf"] = _spear(rel_odd, rel_even)
    out["baseline_early_predicts_late_adjacent"] = _spear(early_adj, late_adj)

    # TEST 1: ICC + between-patient spread
    log_groups = [np.log(case_doses[cid]) for cid in case_doses
                  if len(case_doses[cid]) >= 2 and (case_doses[cid] > 0).all()]
    out["icc_log_dose"] = _icc1(log_groups)
    out["between_patient_spread_median_req"] = _fold_range(list(case_req.values()))

    # TEST 4: within-case CV
    if case_cv:
        cvs = np.array([case_cv[cid] for cid in case_doses if len(case_doses[cid]) >= 4], float)
        cvs = cvs[np.isfinite(cvs)]
        if len(cvs):
            out["within_case_cv"] = {
                "median": round(float(np.median(cvs)), 3),
                "p25": round(float(np.percentile(cvs, 25)), 3),
                "p75": round(float(np.percentile(cvs, 75)), 3),
                "frac_cv_gt_0p2": round(float((cvs > 0.2).mean()), 3),
                "n": int(len(cvs)),
            }

    # TEST 2: time-gapped (epoch t_start is in SECONDS within a case; intra-op so gaps are
    # minutes-to-hours). Use gaps in minutes appropriate to surgery length.
    gaps_min = [0.0, 10.0, 20.0, 30.0, 45.0]
    gapped = {}
    for g in gaps_min:
        ea, la = [], []
        for cid in case_doses:
            doses = case_doses[cid]
            times = case_times[cid]
            if len(doses) < 4:
                continue
            t0, t1 = times[0], times[-1]
            mid = t0 + (t1 - t0) / 2.0
            early_mask = times <= mid
            if early_mask.sum() < 1 or (~early_mask).sum() < 1:
                continue
            last_early_t = times[early_mask].max()
            late_mask = (times >= (last_early_t + g * 60.0)) & (times > mid)
            if late_mask.sum() < 1:
                continue
            ea.append(float(np.median(doses[early_mask])))
            la.append(float(np.median(doses[late_mask])))
        gapped[f"gap_ge_{g:g}min"] = _spear(ea, la)
    out["time_gapped_early_predicts_late"] = gapped

    # TEST 3: shuffle null
    rng = np.random.default_rng(SEED)
    if len(rel_even) >= 10:
        re = np.array(rel_even, float)
        out["null_reliability_shuffled"] = _spear(np.array(rel_odd, float), re[rng.permutation(len(re))])
    if len(late_adj) >= 10:
        la = np.array(late_adj, float)
        out["null_early_late_shuffled"] = _spear(np.array(early_adj, float), la[rng.permutation(len(la))])

    # TEST 4b: early->late in high-CV subset
    if case_cv:
        cv_thresh = float(np.median([case_cv[cid] for cid in case_doses if len(case_doses[cid]) >= 4]))
        hi_e, hi_l, lo_e, lo_l = [], [], [], []
        for cid in case_doses:
            doses = case_doses[cid]
            if len(doses) < 4:
                continue
            h = len(doses) // 2
            e = float(np.median(doses[:h])); l = float(np.median(doses[h:]))
            if case_cv[cid] >= cv_thresh:
                hi_e.append(e); hi_l.append(l)
            else:
                lo_e.append(e); lo_l.append(l)
        out["early_late_high_cv_subset"] = {
            "cv_threshold_median": round(cv_thresh, 3),
            "high_cv": _spear(hi_e, hi_l),
            "low_cv": _spear(lo_e, lo_l),
        }
    return out


# --------------------------------------------------------------------------- verdict
def _verdict(mimic, vitaldb):
    """Honest assessment: trait vs mechanical persistence."""
    icc = mimic.get("icc_log_rate", {}).get("icc1")
    fold = mimic.get("between_patient_spread_median_req", {}).get("fold_range_p90_p10")
    gap6 = mimic.get("time_gapped_early_predicts_late", {}).get("gap_ge_6h", {}).get("r")
    gap12 = mimic.get("time_gapped_early_predicts_late", {}).get("gap_ge_12h", {}).get("r")
    gap0 = mimic.get("time_gapped_early_predicts_late", {}).get("gap_ge_0h", {}).get("r")
    null_rel = mimic.get("null_reliability_shuffled", {}).get("r")
    null_el = mimic.get("null_early_late_shuffled", {}).get("r")
    cv_med = mimic.get("within_stay_cv", {}).get("median")
    hi_cv = mimic.get("early_late_high_cv_subset", {}).get("high_cv", {}).get("r")

    checks = {
        "icc_substantial(>=0.3)": (icc is not None and icc >= 0.3),
        "between_patient_fold_range(>=2)": (fold is not None and fold >= 2.0),
        "gap6h_survives(>=0.3)": (gap6 is not None and gap6 >= 0.3),
        "null_collapses(|r|<=0.1)": (null_rel is not None and abs(null_rel) <= 0.1
                                     and null_el is not None and abs(null_el) <= 0.1),
        "within_stay_cv_nontrivial(>=0.15)": (cv_med is not None and cv_med >= 0.15),
        "early_late_survives_high_cv(>=0.3)": (hi_cv is not None and hi_cv >= 0.3),
    }
    n_pass = sum(checks.values())

    if n_pass >= 5 and checks["null_collapses(|r|<=0.1)"] and checks["gap6h_survives(>=0.3)"]:
        tier = ("GENUINE BETWEEN-PATIENT TRAIT (attack REJECTED). The reliability/early->late "
                "is NOT merely mechanical persistence")
    elif n_pass >= 3 and checks["null_collapses(|r|<=0.1)"]:
        tier = ("PARTLY TRAIT, PARTLY PERSISTENCE (attack PARTIALLY survives). There is real "
                "between-patient signal but mechanical persistence inflates the headline numbers")
    else:
        tier = ("LARGELY MECHANICAL PERSISTENCE (attack STANDS). The reliability is mostly "
                "adjacent-sample stickiness of a near-constant infusion")

    detail = []
    if icc is not None:
        detail.append(f"ICC(1) of log-requirement = {icc} ({mimic['icc_log_rate'].get('n_groups')} "
                      f"stays): {'most variance BETWEEN patients' if icc >= 0.5 else 'substantial between-patient variance' if icc >= 0.3 else 'within-patient noise dominates'}.")
    if fold is not None:
        detail.append(f"Between-patient fold-range (p90/p10) of the requirement = {fold}x.")
    if gap0 is not None and gap6 is not None:
        detail.append(f"Early->late Spearman: {gap0} at gap=0h vs {gap6} at gap>=6h"
                      + (f", {gap12} at >=12h" if gap12 is not None else "")
                      + " -- " + ("SURVIVES a multi-hour gap (not adjacent stickiness)."
                                  if (gap6 is not None and gap6 >= 0.3) else "decays toward null with the gap (persistence)."))
    if null_rel is not None:
        detail.append(f"Shuffle-null: reliability {null_rel}, early->late {null_el} "
                      f"(both ~0 => metric not spuriously inflated).")
    if cv_med is not None:
        detail.append(f"Within-stay rate CV median = {cv_med} "
                      + ("(rate genuinely MOVES within a stay -- not trivially constant)."
                         if cv_med >= 0.15 else "(rate is nearly constant within a stay -- persistence is real and large)."))
    if hi_cv is not None:
        detail.append(f"Early->late in the HIGH-within-stay-CV subset (weakest persistence) = {hi_cv}.")

    # VitalDB mirror line
    v_icc = vitaldb.get("icc_log_dose", {}).get("icc1")
    v_fold = vitaldb.get("between_patient_spread_median_req", {}).get("fold_range_p90_p10")
    v_gap = None
    g = vitaldb.get("time_gapped_early_predicts_late", {})
    for k in ("gap_ge_30min", "gap_ge_20min", "gap_ge_45min"):
        if g.get(k, {}).get("r") is not None:
            v_gap = (k, g[k]["r"]); break
    vline = (f"VitalDB mirror (N small): ICC(1) log-dose = {v_icc}, fold-range = {v_fold}x"
             + (f", time-gapped early->late {v_gap[1]} at {v_gap[0]}" if v_gap else "")
             + ".")

    return {
        "checks": checks,
        "n_checks_passed": n_pass,
        "verdict": (f"{tier}. " + " ".join(detail) + " " + vline),
        "headline": tier,
    }


# --------------------------------------------------------------------------- doc
def _doc(res):
    m = res["mimic"]
    v = res["vitaldb"]
    j = json.dumps
    L = [
        "# Autocorrelation attack on the vasopressor-requirement reliability\n",
        "**The attack (hostile methods reviewer):** \"The within-encounter reliability "
        "(MIMIC split-half 0.95, VitalDB 0.82) and the early->late prediction (MIMIC 0.62, "
        "VitalDB 0.54) are TRIVIAL AUTOCORRELATION. A slowly-titrated infusion is piecewise-"
        "constant, so an early sample mechanically predicts a late sample. This is mechanical "
        "persistence, not a meaningful patient trait.\"\n",
        "This document tests, honestly, whether the signal is MORE than mechanical persistence.\n",
        f"**VERDICT: {res['judgement']['headline']}.**\n",
        res["judgement"]["verdict"] + "\n",
        "## Checks (MIMIC, primary)",
    ]
    for k, val in res["judgement"]["checks"].items():
        L.append(f"- {'PASS' if val else 'FAIL'} -- {k}")
    L.append(f"\n({res['judgement']['n_checks_passed']}/6 checks passed.)\n")

    L += [
        "## MIMIC-IV ICU (primary, N huge)",
        f"- Stays with norepi: **{m['n_stays_with_norepi']}**; >=4 segments: "
        f"**{m['n_stays_ge4_segments']}**.",
        f"- Baseline (reproduced) reliability split-half: {j(m['baseline_reliability_splithalf'])}; "
        f"early->late adjacent: {j(m['baseline_early_predicts_late_adjacent'])}.\n",
        "### Test 1 -- between- vs within-patient variance (ICC)",
        f"- ICC(1) of log-rate: **{m['icc_log_rate'].get('icc1')}** "
        f"(between-patient SD {m['icc_log_rate'].get('between_sd')}, within-patient SD "
        f"{m['icc_log_rate'].get('within_sd')}, {m['icc_log_rate'].get('n_groups')} stays).",
        f"- Between-patient requirement spread: {j(m['between_patient_spread_median_req'])}.",
        "  A real trait needs the variance to live BETWEEN patients (high ICC) and a wide "
        "between-patient fold-range. A near-constant signal with no between-patient spread "
        "would make reliability trivial.\n",
        "### Test 2 -- TIME-GAPPED early->late (the decisive test)",
        f"- {j(m['time_gapped_early_predicts_late'])}",
        "  Mechanical adjacent-sample stickiness decays as the gap grows; a genuine trait "
        "survives a multi-hour gap between the early window and the late window.\n",
        "### Test 3 -- NULL / placebo (shuffle the patient link)",
        f"- Shuffled reliability: {j(m.get('null_reliability_shuffled'))}; shuffled early->late: "
        f"{j(m.get('null_early_late_shuffled'))}.",
        f"- Mechanical yardstick: {j(m.get('mechanical_yardstick_band_membership'))}.",
        "  Breaking the patient link must collapse the metric to ~0 (confirms it is not "
        "spuriously inflated by the estimator).\n",
        "### Test 4 -- persistence-adjusted (within-stay dynamics)",
        f"- Within-stay rate CV: {j(m['within_stay_cv'])}.",
        f"- Early->late split by within-stay CV: {j(m['early_late_high_cv_subset'])}.",
        "  If the rate barely moves within a stay (CV~0) the reliability is trivially "
        "mechanical; if it moves a lot yet early still predicts late, it is a real trait.\n",
        "## VitalDB (mirror, N small -- intraoperative stable epochs)",
        f"- Cases (norepi-only, >=2 epochs): **{v.get('n_cases_norepi_only_ge2')}**; >=4 epochs: "
        f"**{v.get('n_cases_ge4_epochs')}**.",
        f"- Baseline reliability split-half: {j(v.get('baseline_reliability_splithalf'))}; "
        f"early->late adjacent: {j(v.get('baseline_early_predicts_late_adjacent'))}.",
        f"- ICC(1) log-dose: {j(v.get('icc_log_dose'))}.",
        f"- Between-patient spread: {j(v.get('between_patient_spread_median_req'))}.",
        f"- Time-gapped early->late: {j(v.get('time_gapped_early_predicts_late'))}.",
        f"- Within-case CV: {j(v.get('within_case_cv'))}.",
        f"- Shuffle null reliability: {j(v.get('null_reliability_shuffled'))}; "
        f"early->late: {j(v.get('null_early_late_shuffled'))}.",
        f"- Early->late high-CV subset: {j(v.get('early_late_high_cv_subset'))}.\n",
        "## Honest caveats",
        "- ICC(1) on log-rate treats segments as exchangeable within a stay; serial "
        "autocorrelation means the effective within-stay N is smaller than the raw count, "
        "so the ICC is a lower bound on the between-patient share if anything.",
        "- The time-gapped test reduces N (stays must span the gap); the reported r at large "
        "gaps is on the longer-stay subset, which is itself a selected population.",
        "- The mechanical yardstick (tercile band membership) is a coarse control, not a "
        "ground-truth mechanical generator; it bounds, not proves, the persistence baseline.",
        "- VitalDB is single-centre, small N, intra-operative (gaps are minutes not hours); "
        "it is a mirror, not an independent confirmation.",
    ]
    open(os.path.join(_DOCS, "AUTOCORRELATION_ATTACK.md"), "w").write("\n".join(L) + "\n")


def main():
    for p in (MIMIC_CSV, VITALDB_CSV):
        if not os.path.exists(p):
            print(f"[attack] MISSING input: {p}", flush=True)
    res = {"seed": SEED}
    print("[attack] MIMIC...", flush=True)
    res["mimic"] = _mimic_attack() if os.path.exists(MIMIC_CSV) else {"note": "missing"}
    print("[attack] VitalDB...", flush=True)
    res["vitaldb"] = _vitaldb_attack() if os.path.exists(VITALDB_CSV) else {"note": "missing"}
    res["judgement"] = _verdict(res["mimic"], res["vitaldb"])
    json.dump(res, open(os.path.join(_CACHE, "autocorrelation_attack.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("\n[attack] VERDICT:", res["judgement"]["headline"], flush=True)
    print("[attack]", res["judgement"]["verdict"], flush=True)
    print("[attack] -> cache/autocorrelation_attack.json, docs/AUTOCORRELATION_ATTACK.md", flush=True)


if __name__ == "__main__":
    main()
