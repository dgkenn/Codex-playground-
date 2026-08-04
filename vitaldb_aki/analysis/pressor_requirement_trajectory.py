"""pressor_requirement_trajectory.py -- the "rising vasopressor-requirement
early-warning" pivot.

Premise (established, docs/PRESSOR_REQUIREMENT.md)
-------------------------------------------------
Intraoperative MAP is FEEDBACK-REGULATED: the anaesthetist titrates norepinephrine
dose to hold MAP at a target, so within a case MAP barely moves (CV ~0.09) while the
DOSE moves a lot (CV ~0.44). The deterioration / vasoreactivity signal therefore
lives in the DOSE (controller effort), not in MAP.

Hypothesis
----------
Because BP is held flat until the controller SATURATES, a RISING norepinephrine
requirement (the dose needed to hold target MAP) is an EARLY signal of evolving
vasoplegia/deterioration that PRECEDES any fall in MAP. This script tests it on the
stable constant-infusion epochs in cache/pressor_requirement_epochs.csv.

Four tests
----------
  1. TREND        -- within each case (>=3 time-ordered NEPI norepi-only epochs),
                     OLS slope of dose_per_kg on t_start; sign + fraction rising.
  2. LEAD-TIME    -- in cases where MAP later drops below the target floor (65 mmHg),
                     does the dose start rising BEFORE MAP falls? Median lead time
                     (s between requirement starting to rise and MAP first dropping).
  3. OUTCOME      -- merge AKI / composite-organ outcome on caseid; risk difference
                     (rising vs stable requirement) with Fisher + bootstrap CI.
                     Confounding-by-severity flagged honestly.
  4. FALSIFICATION-- a rising requirement should track FALLING svr_mean where SVR is
                     available (true vasoplegia), not merely rising dose for other
                     reasons.

stdlib only at import; numpy/pandas/scipy lazy. Style mirrors pressor_requirement.py.
Run: python3 -m vitaldb_aki.analysis.pressor_requirement_trajectory
"""
from __future__ import annotations
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

MIN_EPOCHS = 3                  # need >=3 time-ordered epochs for a within-case trend
MAP_FLOOR = 65.0               # target floor; "MAP drop" = sustained below this
TARGET_LO, TARGET_HI = 55.0, 80.0
RISE_FRAC_DOSE = 0.0           # slope > 0 = rising requirement
B_BOOT = 2000


# --------------------------------------------------------------------- helpers
def _ols_slope(x, y):
    """Simple OLS slope of y on x (numpy)."""
    import numpy as np
    x = np.asarray(x, float); y = np.asarray(y, float)
    xc = x - x.mean()
    sxx = float(np.sum(xc * xc))
    if sxx <= 0:
        return None
    return float(np.sum(xc * (y - y.mean())) / sxx)


def _case_trends(q):
    """Per-case dose_per_kg trend over time (t_start). Returns dict keyed by caseid:
    {slope, sign, n_epochs, t0, t1, doses, maps, t}. Only cases with >=MIN_EPOCHS
    valid time-ordered epochs."""
    out = {}
    for cid, g in q.groupby("caseid"):
        g = g.sort_values("t_start")
        d = g[["t_start", "dose_per_kg", "map_mean"]].dropna()
        if len(d) < MIN_EPOCHS:
            continue
        t = d["t_start"].to_numpy(float)
        dose = d["dose_per_kg"].to_numpy(float)
        mp = d["map_mean"].to_numpy(float)
        if len(set(t)) < 2:
            continue
        sl = _ols_slope(t, dose)
        if sl is None:
            continue
        out[cid] = {"slope_dose_per_s": sl, "rising": int(sl > RISE_FRAC_DOSE),
                    "n_epochs": int(len(d)),
                    "t": t.tolist(), "dose": dose.tolist(), "map": mp.tolist(),
                    "frac_dose_change": float((dose[-1] - dose[0]) / dose[0])
                    if dose[0] > 0 else None}
    return out


def _first_sustained_below(t, mp, floor):
    """Index of the first epoch whose MAP is below `floor` AND (if a later epoch
    exists) the NEXT one is also below -> 'sustained'. Returns (idx, t_drop) or
    (None, None). For a lone trailing below-epoch we accept it as sustained."""
    n = len(mp)
    for i in range(n):
        if mp[i] < floor:
            if i == n - 1 or mp[i + 1] < floor:
                return i, t[i]
    return None, None


def _lead_time(trends):
    """For cases whose MAP drops below MAP_FLOOR after the first epoch: is the dose
    rising in the window BEFORE the first sustained below-floor epoch? Lead time =
    seconds between when the requirement starts rising (first epoch of a positive
    pre-drop run / simply the start of the pre-drop window where slope>0) and the
    MAP drop. We operationalise lead time as the gap between the first PRE-drop
    epoch (where the rising trajectory begins) and the MAP-drop epoch, restricted to
    cases whose pre-drop dose slope is positive."""
    import numpy as np
    rows = []
    for cid, tr in trends.items():
        t = np.asarray(tr["t"], float)
        dose = np.asarray(tr["dose"], float)
        mp = np.asarray(tr["map"], float)
        di, t_drop = _first_sustained_below(t, mp, MAP_FLOOR)
        if di is None or di < 1:
            continue  # need at least one epoch before the drop
        pre_t = t[: di + 1]; pre_dose = dose[: di + 1]
        if len(pre_t) < 2:
            continue
        pre_slope = _ols_slope(pre_t, pre_dose)
        dose_rose = pre_slope is not None and pre_slope > 0
        lead = float(t_drop - t[0]) if dose_rose else None  # since dose-rise window onset
        rows.append({"caseid": cid, "pre_drop_dose_slope": pre_slope,
                     "dose_rose_before_drop": int(bool(dose_rose)),
                     "t_drop": float(t_drop), "lead_time_s": lead,
                     "n_pre_epochs": int(di)})
    n_drop = len(rows)
    n_rose = sum(r["dose_rose_before_drop"] for r in rows)
    leads = [r["lead_time_s"] for r in rows if r["lead_time_s"] is not None]
    out = {"n_cases_with_map_drop": n_drop,
           "n_dose_rose_before_drop": n_rose,
           "frac_dose_rose_before_drop": round(n_rose / n_drop, 3) if n_drop else None,
           "median_lead_time_s": round(float(np.median(leads)), 1) if leads else None,
           "lead_times_s": [round(x, 1) for x in leads],
           "per_case": rows}
    return out


def _load_outcomes():
    """caseid -> {aki, composite, organ_renal}. Prefer composite file for composite /
    organ_renal; cohort.csv for the binary AKI label."""
    import csv as _csv
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


def _fisher_rd(a, b, c, d):
    """2x2 risk difference + Fisher exact p. groups: rising (events a / n a+b),
    stable (events c / n c+d). Returns (rd, p, ci_via_caller)."""
    from scipy import stats
    n1, n0 = a + b, c + d
    if n1 == 0 or n0 == 0:
        return None, None
    rd = a / n1 - c / n0
    _, p = stats.fisher_exact([[a, b], [c, d]])
    return float(rd), float(p)


def _boot_rd_ci(rise_y, stable_y):
    """Cluster (case-level) bootstrap CI for the risk difference rising - stable."""
    import numpy as np
    rng = np.random.default_rng(SEED)
    r = np.asarray(rise_y, float); s = np.asarray(stable_y, float)
    if len(r) == 0 or len(s) == 0:
        return None
    bs = []
    for _ in range(B_BOOT):
        rb = r[rng.integers(0, len(r), len(r))]
        sb = s[rng.integers(0, len(s), len(s))]
        bs.append(rb.mean() - sb.mean())
    return [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]


def _outcome_test(trends, outcomes, label):
    """Risk difference in `label` between rising-requirement and stable cases."""
    import numpy as np
    rise_y, stable_y = [], []
    missing = 0
    for cid, tr in trends.items():
        o = outcomes.get(cid, {})
        v = o.get(label, "")
        if v in ("", None):
            missing += 1
            continue
        y = 1 if str(v) == "1" else 0
        (rise_y if tr["rising"] else stable_y).append(y)
    n_rise, n_stable = len(rise_y), len(stable_y)
    if n_rise == 0 or n_stable == 0:
        return {"label": label, "n_rising": n_rise, "n_stable": n_stable,
                "n_missing_outcome": missing,
                "note": "one arm empty -> RD not estimable"}
    a, b = int(sum(rise_y)), int(n_rise - sum(rise_y))
    c, d = int(sum(stable_y)), int(n_stable - sum(stable_y))
    rd, p = _fisher_rd(a, b, c, d)
    ci = _boot_rd_ci(rise_y, stable_y)
    return {"label": label, "n_rising": n_rise, "n_stable": n_stable,
            "n_missing_outcome": missing,
            "event_rate_rising": round(float(np.mean(rise_y)), 3),
            "event_rate_stable": round(float(np.mean(stable_y)), 3),
            "risk_difference": round(rd, 3) if rd is not None else None,
            "rd_boot_ci": ci, "fisher_p": round(p, 4) if p is not None else None}


def _falsification(q, trends):
    """A genuine rising requirement (vasoplegia) should track FALLING SVR. Within
    each case with >=3 epochs that HAVE svr_mean, OLS slope of svr_mean over time;
    test whether dose-rising cases show negative SVR slopes (Spearman of dose-slope
    vs svr-slope across cases, plus the per-case sign concordance)."""
    import numpy as np
    from scipy import stats
    pairs = []
    for cid, tr in trends.items():
        g = q[q["caseid"] == cid].sort_values("t_start")
        s = g[["t_start", "svr_mean"]].dropna()
        if len(s) < 3 or s["t_start"].nunique() < 2:
            continue
        svr_slope = _ols_slope(s["t_start"].to_numpy(float), s["svr_mean"].to_numpy(float))
        if svr_slope is None:
            continue
        pairs.append((cid, tr["slope_dose_per_s"], svr_slope, tr["rising"]))
    out = {"n_cases_with_svr_trend": len(pairs)}
    if len(pairs) >= 3:
        dose_sl = np.array([p[1] for p in pairs])
        svr_sl = np.array([p[2] for p in pairs])
        # expectation: dose-slope UP <-> svr-slope DOWN -> NEGATIVE correlation
        if len(pairs) >= 4 and np.std(dose_sl) > 0 and np.std(svr_sl) > 0:
            rho, p = stats.spearmanr(dose_sl, svr_sl)
            out["spearman_dose_slope_vs_svr_slope"] = round(float(rho), 3)
            out["spearman_p"] = round(float(p), 4)
        rising = [pp for pp in pairs if pp[3] == 1]
        out["n_rising_with_svr"] = len(rising)
        if rising:
            out["frac_rising_with_falling_svr"] = round(
                float(np.mean([1 if pp[2] < 0 else 0 for pp in rising])), 3)
        out["per_case_dose_svr_slopes"] = [
            {"caseid": c, "dose_slope": round(ds, 9), "svr_slope": round(ss, 4),
             "rising": int(rs)} for (c, ds, ss, rs) in pairs]
        out["expectation"] = ("vasoplegia falsification: rising DOSE should track "
                              "FALLING SVR -> dose-slope vs svr-slope NEGATIVE, and "
                              "rising cases should mostly show svr_slope<0.")
    else:
        out["note"] = "too few cases with a within-case SVR trend to test falsification"
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
    # NEPI norepi-only, valid per-kg dose, plausible MAP
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["norepi_only"] == 1) &
           df["dose_per_kg"].notna() & df["map_mean"].notna()].copy()
    res = {"seed": SEED, "primary_drug": PRIMARY_DRUG,
           "min_epochs_per_case": MIN_EPOCHS, "map_floor": MAP_FLOOR,
           "target_band": [TARGET_LO, TARGET_HI],
           "n_epochs_total": int(len(df)),
           "n_nepi_only_epochs": int(len(q)),
           "n_cases_nepi_only": int(q["caseid"].nunique())}

    # 1. TREND -----------------------------------------------------------------
    trends = _case_trends(q)
    n_cases = len(trends)
    res["n_cases_ge3_epochs"] = n_cases
    if n_cases == 0:
        res["verdict"] = "INSUFFICIENT -- no cases with >=3 time-ordered NEPI-only epochs."
        return res
    n_rising = sum(t["rising"] for t in trends.values())
    fracs = [t["frac_dose_change"] for t in trends.values() if t["frac_dose_change"] is not None]
    res["trend"] = {
        "n_cases": n_cases,
        "n_rising": n_rising,
        "frac_rising": round(n_rising / n_cases, 3),
        "median_total_dose_change_frac": round(float(np.median(fracs)), 3) if fracs else None,
        "median_dose_change_frac_rising": round(float(np.median(
            [t["frac_dose_change"] for t in trends.values()
             if t["rising"] and t["frac_dose_change"] is not None])), 3)
        if n_rising else None,
        "interpretation": ("fraction of cases whose dose_per_kg trends UP over time "
                           "(requirement rising = controller working harder to hold MAP).")}

    # 2. LEAD-TIME -------------------------------------------------------------
    res["lead_time"] = _lead_time(trends)

    # 3. OUTCOME ---------------------------------------------------------------
    outcomes = _load_outcomes()
    res["outcome"] = {
        "composite": _outcome_test(trends, outcomes, "composite"),
        "organ_renal": _outcome_test(trends, outcomes, "organ_renal"),
        "aki": _outcome_test(trends, outcomes, "aki"),
        "confounding_note": ("CONFOUNDING-BY-SEVERITY: rising-requirement cases are, by "
                             "construction, the sicker/more-vasoplegic patients, who are "
                             "independently more likely to suffer organ injury. A positive "
                             "RD is therefore expected even if the trajectory adds no "
                             "predictive value beyond baseline severity; with this N no "
                             "severity adjustment is possible. Treat any association as "
                             "hypothesis-generating, NOT causal.")}

    # 4. FALSIFICATION ---------------------------------------------------------
    res["falsification_svr"] = _falsification(q, trends)

    # ---- VERDICT -------------------------------------------------------------
    lt = res["lead_time"]; fz = res["falsification_svr"]
    trend_supported = (res["trend"]["frac_rising"] >= 0.4 and n_cases >= 15)
    lead_testable = lt["n_cases_with_map_drop"] >= 8
    lead_supported = lead_testable and (lt.get("frac_dose_rose_before_drop") or 0) >= 0.6
    svr_testable = fz["n_cases_with_svr_trend"] >= 5
    svr_supported = svr_testable and (
        (fz.get("spearman_dose_slope_vs_svr_slope") or 0) < 0 or
        (fz.get("frac_rising_with_falling_svr") or 0) >= 0.6)
    oc = res["outcome"]["composite"]
    outcome_signal = (oc.get("risk_difference") or 0) > 0 and \
        oc.get("n_rising", 0) >= 5 and oc.get("n_stable", 0) >= 5

    if trend_supported and lead_supported and (svr_supported or outcome_signal):
        verdict_flag = "GO"
    elif trend_supported and (lead_testable or svr_testable) and \
            (lead_supported or svr_supported or outcome_signal):
        verdict_flag = "PARTIAL"
    elif trend_supported:
        verdict_flag = "PARTIAL"
    else:
        verdict_flag = "NO-GO"
    res["verdict_flag"] = verdict_flag

    parts = []
    parts.append(f"A rising norepinephrine REQUIREMENT exists and is common: "
                 f"{n_rising}/{n_cases} ({res['trend']['frac_rising']*100:.0f}%) of "
                 f"NEPI-only cases with >=3 stable epochs show a positive dose_per_kg "
                 f"trend over time.")
    if lead_testable:
        parts.append(f"LEAD-TIME (n={lt['n_cases_with_map_drop']} cases with a MAP<{MAP_FLOOR:.0f} "
                     f"drop): dose rose before the drop in "
                     f"{lt['n_dose_rose_before_drop']}/{lt['n_cases_with_map_drop']} "
                     f"(median lead {lt.get('median_lead_time_s')} s).")
    else:
        parts.append(f"LEAD-TIME is UNDERPOWERED: only {lt['n_cases_with_map_drop']} case(s) had a "
                     f"sustained MAP<{MAP_FLOOR:.0f} drop with a prior epoch, too few to estimate "
                     f"a reliable lead time (observed leads {lt.get('lead_times_s')}).")
    if svr_testable:
        parts.append(f"FALSIFICATION (SVR, n={fz['n_cases_with_svr_trend']}): "
                     f"dose-slope vs svr-slope Spearman "
                     f"{fz.get('spearman_dose_slope_vs_svr_slope')}, "
                     f"frac rising-with-falling-SVR {fz.get('frac_rising_with_falling_svr')}.")
    else:
        parts.append(f"FALSIFICATION is UNDERPOWERED: only {fz['n_cases_with_svr_trend']} case(s) "
                     f"have a within-case SVR trend, too few to confirm the vasoplegia mechanism.")
    parts.append(f"OUTCOME (composite): rising RD {oc.get('risk_difference')} "
                 f"(CI {oc.get('rd_boot_ci')}, Fisher p {oc.get('fisher_p')}, "
                 f"n_rising={oc.get('n_rising')}, n_stable={oc.get('n_stable')}) -- "
                 f"CONFOUNDED BY SEVERITY, hypothesis-generating only.")

    if verdict_flag == "GO":
        head = "GO -- rising requirement is a supported early-warning concept: common, leads the MAP fall, and tracks falling SVR."
    elif verdict_flag == "PARTIAL":
        head = ("PARTIAL -- the rising-requirement phenomenon is REAL and common, but the "
                "lead-time and/or SVR-falsification tests are underpowered at this N; the "
                "early-warning CLAIM is not yet confirmed.")
    else:
        head = "NO-GO -- insufficient evidence that a rising requirement is common or early-warning at this N."
    res["verdict"] = head + " " + " ".join(parts)
    return res


# --------------------------------------------------------------------- doc
def _doc(res):
    L = ["# Rising vasopressor-REQUIREMENT early-warning (trajectory pivot)\n",
         "Because intraoperative MAP is FEEDBACK-REGULATED (anaesthetist titrates norepinephrine "
         "dose to a MAP target; within-patient MAP CV ~0.09 vs dose CV ~0.44, see "
         "docs/PRESSOR_REQUIREMENT.md), the deterioration signal lives in the DOSE (controller "
         "effort), not in MAP. **Hypothesis:** a RISING norepinephrine requirement is an EARLY "
         "signal of evolving vasoplegia that PRECEDES any MAP fall, because BP is held flat until "
         "the controller saturates.\n",
         "Sample: STABLE constant-infusion NEPI norepi-only epochs, time-ordered within case, "
         f">= {MIN_EPOCHS} epochs/case.\n"]
    if not res.get("available", True) or res.get("n_cases_ge3_epochs", 0) == 0:
        L.append("_" + res.get("verdict", "no data") + "_")
        open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT_TRAJECTORY.md"), "w").write("\n".join(L) + "\n")
        return
    L += [f"- NEPI norepi-only epochs: **{res['n_nepi_only_epochs']}** over "
          f"**{res['n_cases_nepi_only']}** cases (of {res['n_epochs_total']} total epochs).",
          f"- Cases with >= {MIN_EPOCHS} time-ordered epochs (trajectory-eligible): "
          f"**{res['n_cases_ge3_epochs']}**.\n"]
    tr = res["trend"]
    L += ["## 1. Within-case requirement TREND",
          f"- Rising (dose_per_kg slope > 0): **{tr['n_rising']}/{tr['n_cases']} "
          f"({tr['frac_rising']*100:.0f}%)**.",
          f"- Median total dose change across a case: {tr['median_total_dose_change_frac']} "
          f"(rising cases: {tr['median_dose_change_frac_rising']}).\n"]
    lt = res["lead_time"]
    L += ["## 2. LEAD-TIME (does dose rise BEFORE MAP falls?)",
          f"- Cases with a sustained MAP<{MAP_FLOOR:.0f} drop after epoch 0: "
          f"**{lt['n_cases_with_map_drop']}**.",
          f"- Of those, dose rose before the drop: **{lt['n_dose_rose_before_drop']}** "
          f"(frac {lt.get('frac_dose_rose_before_drop')}).",
          f"- Median lead time: **{lt.get('median_lead_time_s')} s** "
          f"(observed leads: {lt.get('lead_times_s')}).",
          ("  _Note: with this N the lead-time test is UNDERPOWERED; the numbers above are "
           "descriptive, not inferential._" if lt['n_cases_with_map_drop'] < 8 else "") + "\n"]
    oc = res["outcome"]
    L += ["## 3. Outcome association (rising vs stable requirement)"]
    for key in ("composite", "organ_renal", "aki"):
        o = oc[key]
        if "risk_difference" in o:
            L.append(f"- **{key}**: rising {o['event_rate_rising']} vs stable "
                     f"{o['event_rate_stable']} -> RD **{o['risk_difference']}** "
                     f"(boot CI {o['rd_boot_ci']}, Fisher p {o['fisher_p']}; "
                     f"n_rising={o['n_rising']}, n_stable={o['n_stable']}).")
        else:
            L.append(f"- **{key}**: not estimable (n_rising={o.get('n_rising')}, "
                     f"n_stable={o.get('n_stable')}).")
    L += ["", "  " + oc["confounding_note"] + "\n"]
    fz = res["falsification_svr"]
    L += ["## 4. Falsification -- rising requirement should track FALLING SVR",
          f"- Cases with a within-case SVR trend: **{fz['n_cases_with_svr_trend']}**."]
    if "spearman_dose_slope_vs_svr_slope" in fz:
        L.append(f"- Spearman(dose-slope, svr-slope) = **{fz['spearman_dose_slope_vs_svr_slope']}** "
                 f"(p {fz.get('spearman_p')}); expected NEGATIVE.")
    if "frac_rising_with_falling_svr" in fz:
        L.append(f"- Rising cases with FALLING SVR: **{fz['frac_rising_with_falling_svr']}** "
                 f"(of {fz.get('n_rising_with_svr')} rising-with-SVR cases).")
    if "note" in fz:
        L.append(f"- _{fz['note']}._")
    L += [""]
    L += ["## Verdict", res.get("verdict", ""), ""]
    L += ["## Caveats",
          "- **Confounding by severity is unadjusted** -- sicker patients both need rising pressor "
          "and suffer more organ injury; the outcome RD is hypothesis-generating only.",
          "- **Lead-time / SVR-falsification are N-limited** -- few cases reach a sustained MAP<65 "
          "drop, and SVR (EV1000) is recorded in only a minority; treat as descriptive.",
          "- **Dose units** are Orchestra device rate / kg (not ug/kg/min); within-case TRENDS are "
          "concentration-invariant, which is exactly what the trajectory test uses.",
          "- **Single-centre (SNUH/VitalDB)**; external replication required.",
          "- The CSV is actively extended; re-run as N grows -- the lead-time and SVR tests are the "
          "ones that will move from descriptive to inferential first."]
    open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT_TRAJECTORY.md"), "w").write("\n".join(L) + "\n")


def main():
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "pressor_requirement_trajectory.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("\n[preq-traj] VERDICT: " + res.get("verdict", "no data"), flush=True)
    print("[preq-traj] -> docs/PRESSOR_REQUIREMENT_TRAJECTORY.md", flush=True)
    print("[preq-traj] -> cache/pressor_requirement_trajectory.json", flush=True)


if __name__ == "__main__":
    main()
