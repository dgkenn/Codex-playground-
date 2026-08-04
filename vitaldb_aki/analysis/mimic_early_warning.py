"""mimic_early_warning.py -- ACTIONABLE early-warning value of the in-ICU norepinephrine
requirement in MIMIC-IV (timestamps + hard in-hospital-mortality endpoint -- the version
VitalDB could not power).

mimic_external_validation.py established that the per-stay requirement REPLICATES and marks
mortality risk (age-adjusted OR ~3.8, AUC +0.20 over age). That used the WHOLE-stay summary.
The clinical question that matters is EARLINESS: can a snapshot taken from only the FIRST few
hours of norepinephrine already stratify death (an actionable lead), and does the WITHIN-stay
TRAJECTORY (rising dose, escalation events) add warning beyond the early level? With real
infusion timestamps and a hard endpoint, MIMIC can answer this; VitalDB (intraoperative, no
mortality) could not.

Four tests, per stay's time-ordered norepi rate series (mcg/kg/min):
  1. EARLY REQUIREMENT -> MORTALITY. Using ONLY the first X h (default 6 h) of norepi from the
     first segment, compute the early requirement (median + peak rate). Age-adjusted OR + AUC,
     and first-6h AUC vs whole-stay AUC (how much warning is lost by looking early?).
  2. RISING TRAJECTORY -> death BEYOND early level. In stays with >=4 segments over >=6 h, fit
     the within-stay dose slope (rate vs hours). Nested logistic (age+early-level vs
     age+early-level+slope): likelihood-ratio test + delta-AUC -- does a rising requirement add
     warning over the early snapshot?
  3. ESCALATION events. escalation = rate doubling OR a +0.1 mcg/kg/min step after the first
     hour. Does presence/number predict mortality (age-adjusted)? Lead time = median hours from
     first norepi to the last escalation, among deaths (how early does the warning fire?).
  4. SIMPLE BEDSIDE RULE. Early-peak-norepi thresholds (0.2 / 0.3 mcg/kg/min): risk table --
     mortality above vs below, sensitivity, specificity, PPV, NPV.

HONEST SCOPE: AUC is rank-based and honest (no threshold tuning). Risk-table operating points
use IN-SAMPLE thresholds (pre-specified clinical round numbers, but evaluated on the same data
-- labelled as such, not cross-validated). All associations are observational and age-adjusted
ONLY; illness-severity confounding is NOT removed here (the requirement marks the sicker
patient by construction) and is handled elsewhere. This shows whether the EARLY requirement is
an actionable mortality early-warning MARKER, not that intervening on it helps (a trial).

Reads MIMIC raw from $MIMIC_RAW (default: session scratchpad) for the mortality/age tables and
the norepi-segment cache written by mimic_external_validation.py. stdlib only at import;
numpy/scipy/sklearn lazy. Run: python3 -m vitaldb_aki.analysis.mimic_early_warning
"""
from __future__ import annotations
import csv as _csv
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
MIMIC_RAW = os.environ.get("MIMIC_RAW",
    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad")
NOREPI_CSV = os.path.join(_CACHE, "mimic_norepi.csv")
EARLY_HOURS = 6.0          # the early window, from the first norepi segment
ESC_ABS = 0.1              # absolute escalation step (mcg/kg/min)
ESC_FACTOR = 2.0           # relative escalation = rate doubling
RULE_THRESHOLDS = (0.2, 0.3)   # early-peak bedside thresholds (mcg/kg/min)


def _parse_ts(s):
    """'YYYY-MM-DD HH:MM:SS' -> epoch seconds (relative ordering / hour-deltas only)."""
    import time
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _stays():
    """Per stay: ordered list of (t_start_seconds, rate). {stay_id: {subject, segs}}.

    Mirrors mimic_external_validation._stays (same physiologic gate) so the two modules see an
    identical cohort."""
    stays = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rate = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rate <= 0 or rate > 5:   # mcg/kg/min physiologic gate
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


def _mortality_tables():
    """Load stay_id->hadm_id, hadm_id->death, subject_id->age. Returns (stay_hadm, hadm_death,
    subj_age) or None if any table is missing."""
    icu = os.path.join(MIMIC_RAW, "icustays.csv.gz")
    adm = os.path.join(MIMIC_RAW, "admissions.csv.gz")
    pat = os.path.join(MIMIC_RAW, "patients.csv.gz")
    if not all(os.path.exists(p) for p in (icu, adm, pat)):
        return None
    stay_hadm = {}
    with gzip.open(icu, "rt") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]
    hadm_death = {}
    with gzip.open(adm, "rt") as fh:
        for row in _csv.DictReader(fh):
            hadm_death[row["hadm_id"]] = row.get("hospital_expire_flag", "0")
    subj_age = {}
    with gzip.open(pat, "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                subj_age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
    return stay_hadm, hadm_death, subj_age


def _features(stays):
    """Per stay, build early-window + trajectory features. Returns list of dicts (one per stay
    with usable norepi)."""
    import numpy as np
    out = []
    for sid, d in stays.items():
        segs = d["segs"]
        if not segs:
            continue
        t0 = segs[0][0]
        hours = [(t - t0) / 3600.0 for t, _ in segs]
        rates = [r for _, r in segs]
        span_h = hours[-1]
        # early window: segments whose start is within EARLY_HOURS of the first segment
        ew = [(h, r) for h, r in zip(hours, rates) if h <= EARLY_HOURS]
        if not ew:                       # guarantee >=1 (first segment is at h=0)
            ew = [(hours[0], rates[0])]
        early_rates = [r for _, r in ew]
        feat = {
            "stay_id": sid, "subject": d["subject"], "n_seg": len(segs), "span_h": span_h,
            "early_median": float(np.median(early_rates)),
            "early_peak": float(np.max(early_rates)),
            "whole_median": float(np.median(rates)),
            "whole_peak": float(np.max(rates)),
            "n_early_seg": len(ew),
        }
        # within-stay dose slope (rate vs hours), only meaningful with spread in time
        if len(segs) >= 4 and span_h >= 6.0 and len(set(hours)) >= 2:
            h = np.asarray(hours, float); r = np.asarray(rates, float)
            slope = float(np.polyfit(h, r, 1)[0])    # mcg/kg/min per hour
            feat["slope"] = slope
        else:
            feat["slope"] = None
        # escalation events after the first hour: rate >= factor*previous OR >= prev + abs step
        n_esc, esc_hours = 0, []
        prev = rates[0]
        for hh, rr in zip(hours[1:], rates[1:]):
            if hh >= 1.0 and (rr >= ESC_FACTOR * prev or rr >= prev + ESC_ABS):
                n_esc += 1
                esc_hours.append(hh)
            prev = rr
        feat["n_esc"] = n_esc
        feat["last_esc_h"] = float(esc_hours[-1]) if esc_hours else None
        out.append(feat)
    return out


def _attach_outcome(feats, tables):
    """Attach death (int) and age (float, may be nan) to each feature dict; drop stays without a
    mortality record. Returns filtered list."""
    import numpy as np
    stay_hadm, hadm_death, subj_age = tables
    out = []
    for f in feats:
        h = stay_hadm.get(f["stay_id"])
        if h is None or h not in hadm_death:
            continue
        try:
            d = int(hadm_death[h])
        except (ValueError, TypeError):
            continue
        f["death"] = d
        f["age"] = subj_age.get(f["subject"], np.nan)
        out.append(f)
    return out


def _adj_or_auc(x, age, death, nboot=500):
    """Age-adjusted logistic OR per SD of x + delta-AUC over age-alone. x and age standardised
    internally. Returns dict (or {note} if too few)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    x = np.asarray(x, float); age = np.asarray(age, float); death = np.asarray(death, int)
    m = np.isfinite(x) & np.isfinite(age)
    x, age, death = x[m], age[m], death[m]
    if len(x) < 200 or death.sum() < 30 or len(set(death.tolist())) < 2:
        return {"n": int(len(x)), "deaths": int(death.sum()), "note": "too few"}
    xs = (x - x.mean()) / (x.std() or 1.0)
    ags = (age - age.mean()) / (age.std() or 1.0)
    X = np.column_stack([ags, xs])
    lr = LogisticRegression(max_iter=2000).fit(X, death)
    or_x = float(np.exp(lr.coef_[0][1]))
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(death), len(death))
        if len(set(death[idx].tolist())) < 2:
            continue
        try:
            bs.append(float(np.exp(LogisticRegression(max_iter=1000).fit(X[idx], death[idx]).coef_[0][1])))
        except Exception:
            pass
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)
    auc_age = float(roc_auc_score(death, age))
    auc_x_alone = float(roc_auc_score(death, x))
    auc_full = float(roc_auc_score(death, lr.predict_proba(X)[:, 1]))
    return {"n": int(len(x)), "deaths": int(death.sum()),
            "mortality_rate": round(float(death.mean()), 3),
            "adj_or_per_sd": round(or_x, 3),
            "ci": [round(lo, 3), round(hi, 3)] if lo is not None else None,
            "auc_x_alone": round(auc_x_alone, 3),
            "auc_age_alone": round(auc_age, 3),
            "auc_age_plus_x": round(auc_full, 3),
            "delta_auc_over_age": round(auc_full - auc_age, 4)}


def test_early_vs_whole(feats):
    """Test 1. Early-window (first EARLY_HOURS) requirement vs whole-stay -> mortality."""
    import numpy as np
    from sklearn.metrics import roc_auc_score
    age = [f["age"] for f in feats]; death = [f["death"] for f in feats]
    res = {"early_window_hours": EARLY_HOURS}
    res["early_peak"] = _adj_or_auc([f["early_peak"] for f in feats], age, death)
    res["early_median"] = _adj_or_auc([f["early_median"] for f in feats], age, death)
    res["whole_peak"] = _adj_or_auc([f["whole_peak"] for f in feats], age, death)
    res["whole_median"] = _adj_or_auc([f["whole_median"] for f in feats], age, death)
    # head-to-head rank AUC of the raw marker (honest, no threshold), early vs whole
    d = np.asarray(death, int)
    if d.sum() >= 30 and len(set(d.tolist())) == 2:
        ep = roc_auc_score(d, [f["early_peak"] for f in feats])
        wp = roc_auc_score(d, [f["whole_peak"] for f in feats])
        res["auc_early_peak"] = round(float(ep), 3)
        res["auc_whole_peak"] = round(float(wp), 3)
        res["auc_warning_retained_frac"] = (
            round(float((ep - 0.5) / (wp - 0.5)), 3) if wp > 0.5 else None)
    return res


def test_rising_trajectory(feats):
    """Test 2. Among stays with a fitted slope (>=4 seg over >=6 h), does a RISING requirement
    add mortality warning BEYOND the early level? Nested logistic LR test + delta-AUC."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from scipy import stats
    sub = [f for f in feats if f["slope"] is not None and np.isfinite(f["age"])]
    early = np.array([f["early_median"] for f in sub], float)
    slope = np.array([f["slope"] for f in sub], float)
    age = np.array([f["age"] for f in sub], float)
    death = np.array([f["death"] for f in sub], int)
    out = {"n": int(len(sub)), "deaths": int(death.sum()),
           "frac_rising": round(float((slope > 0).mean()), 3) if len(slope) else None,
           "median_slope": round(float(np.median(slope)), 5) if len(slope) else None}
    if len(sub) < 200 or death.sum() < 30:
        out["note"] = "too few"
        return out

    def z(a):
        return (a - a.mean()) / (a.std() or 1.0)
    age_z, early_z, slope_z = z(age), z(early), z(slope)

    def _ll(X):
        lr = LogisticRegression(max_iter=3000).fit(X, death)
        p = np.clip(lr.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
        ll = float(np.sum(death * np.log(p) + (1 - death) * np.log(1 - p)))
        return lr, p, ll
    X_base = np.column_stack([age_z, early_z])
    X_full = np.column_stack([age_z, early_z, slope_z])
    lr_b, p_b, ll_b = _ll(X_base)
    lr_f, p_f, ll_f = _ll(X_full)
    lr_stat = 2.0 * (ll_f - ll_b)
    p_lrt = float(stats.chi2.sf(lr_stat, df=1)) if lr_stat > 0 else 1.0
    out["slope_adj_or_per_sd"] = round(float(np.exp(lr_f.coef_[0][2])), 3)
    out["auc_base_age_early"] = round(float(roc_auc_score(death, p_b)), 3)
    out["auc_plus_slope"] = round(float(roc_auc_score(death, p_f)), 3)
    out["delta_auc_slope_increment"] = round(float(roc_auc_score(death, p_f) - roc_auc_score(death, p_b)), 4)
    out["lr_test_chi2"] = round(lr_stat, 3)
    out["lr_test_p"] = float(f"{p_lrt:.3e}")
    return out


def test_escalation(feats):
    """Test 3. Escalation events (rate doubling or +ESC_ABS after the first hour) -> mortality
    (age-adjusted), and lead time (hours from first norepi to last escalation) among deaths."""
    import numpy as np
    age = [f["age"] for f in feats]; death = np.array([f["death"] for f in feats], int)
    n_esc = [f["n_esc"] for f in feats]
    any_esc = [1 if f["n_esc"] > 0 else 0 for f in feats]
    out = {"esc_def": f"rate>= {ESC_FACTOR}x prev OR >= prev+{ESC_ABS} mcg/kg/min, after 1h",
           "frac_any_escalation": round(float(np.mean(any_esc)), 3)}
    out["count_escalations"] = _adj_or_auc(n_esc, age, death)
    # presence as a binary marker: age-adjusted OR via the same helper (0/1 input is fine)
    out["any_escalation"] = _adj_or_auc(any_esc, age, death)
    # crude mortality split by presence
    a = np.array(any_esc, int)
    if a.sum() > 0 and (a == 0).sum() > 0:
        out["mortality_with_escalation"] = round(float(death[a == 1].mean()), 3)
        out["mortality_without_escalation"] = round(float(death[a == 0].mean()), 3)
    # lead time among deaths: hours from first norepi to the LAST escalation (the warning that
    # precedes death). Among non-survivors with >=1 escalation.
    lead = [f["last_esc_h"] for f in feats if f["death"] == 1 and f["last_esc_h"] is not None]
    span_d = [f["span_h"] for f in feats if f["death"] == 1 and f["last_esc_h"] is not None]
    if lead:
        out["lead_time_n_deaths_with_esc"] = len(lead)
        out["median_lead_h_first_norepi_to_last_esc"] = round(float(np.median(lead)), 2)
        out["lead_iqr_h"] = [round(float(np.percentile(lead, 25)), 2),
                             round(float(np.percentile(lead, 75)), 2)]
        # warning runway: hours from that escalation to end of norepi record (proxy for time
        # remaining to act). NOT time-to-death (no death timestamp here).
        runway = [s - l for s, l in zip(span_d, lead)]
        out["median_runway_h_last_esc_to_end_of_norepi"] = round(float(np.median(runway)), 2)
    return out


def test_bedside_rule(feats):
    """Test 4. Early-peak-norepi bedside thresholds -> risk table (in-sample operating points)."""
    import numpy as np
    death = np.array([f["death"] for f in feats], int)
    peak = np.array([f["early_peak"] for f in feats], float)
    rows = []
    for thr in RULE_THRESHOLDS:
        pos = peak >= thr
        tp = int(((pos) & (death == 1)).sum()); fp = int(((pos) & (death == 0)).sum())
        fn = int(((~pos) & (death == 1)).sum()); tn = int(((~pos) & (death == 0)).sum())
        sens = tp / (tp + fn) if (tp + fn) else None
        spec = tn / (tn + fp) if (tn + fp) else None
        ppv = tp / (tp + fp) if (tp + fp) else None
        npv = tn / (tn + fn) if (tn + fn) else None
        rows.append({
            "early_peak_threshold_mcg_kg_min": thr,
            "n_above": int(pos.sum()), "n_below": int((~pos).sum()),
            "mortality_above": round(tp / (tp + fp), 3) if (tp + fp) else None,
            "mortality_below": round(fn / (fn + tn), 3) if (fn + tn) else None,
            "sensitivity": round(sens, 3) if sens is not None else None,
            "specificity": round(spec, 3) if spec is not None else None,
            "ppv": round(ppv, 3) if ppv is not None else None,
            "npv": round(npv, 3) if npv is not None else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn})
    return {"window_hours": EARLY_HOURS, "note": "IN-SAMPLE operating points (pre-specified "
            "round-number thresholds, evaluated on the same data -- NOT cross-validated)",
            "rules": rows}


def model():
    import numpy as np
    stays = _stays()
    tables = _mortality_tables()
    res = {"seed": SEED, "early_window_hours": EARLY_HOURS,
           "n_stays_with_norepi": len(stays)}
    feats_all = _features(stays)
    if tables is None:
        res["note"] = "mortality tables missing -- cannot run early-warning tests"
        return res
    feats = _attach_outcome(feats_all, tables)
    res["n_stays_with_outcome"] = len(feats)
    res["n_deaths"] = int(sum(f["death"] for f in feats))
    res["overall_mortality"] = round(res["n_deaths"] / len(feats), 3) if feats else None
    res["test1_early_vs_whole"] = test_early_vs_whole(feats)
    res["test2_rising_trajectory"] = test_rising_trajectory(feats)
    res["test3_escalation"] = test_escalation(feats)
    res["test4_bedside_rule"] = test_bedside_rule(feats)

    # verdict
    t1 = res["test1_early_vs_whole"]; t2 = res["test2_rising_trajectory"]
    t3 = res["test3_escalation"]; t4 = res["test4_bedside_rule"]
    ep = t1.get("early_peak", {})
    parts = []
    early_actionable = (ep.get("auc_age_plus_x") is not None
                        and ep.get("delta_auc_over_age", 0) >= 0.05
                        and (ep.get("ci") or [0])[0] > 1.0)
    if early_actionable:
        parts.append(
            f"first-{int(EARLY_HOURS)}h norepi already stratifies death (early-peak age-adj OR "
            f"{ep['adj_or_per_sd']} {ep['ci']}, AUC {t1.get('auc_early_peak')} vs whole-stay "
            f"{t1.get('auc_whole_peak')} -> {t1.get('auc_warning_retained_frac')} of the rank "
            f"signal retained from a {int(EARLY_HOURS)}h snapshot)")
    slope_adds = (t2.get("lr_test_p") is not None and t2["lr_test_p"] < 0.05
                  and t2.get("delta_auc_slope_increment", 0) > 0)
    if slope_adds:
        parts.append(
            f"a RISING requirement adds warning beyond the early level (slope LR-test p "
            f"{t2['lr_test_p']}, +{t2['delta_auc_slope_increment']} AUC, slope OR "
            f"{t2.get('slope_adj_or_per_sd')}/SD)")
    elif t2.get("note") != "too few":
        parts.append(
            f"the within-stay slope adds little beyond the early level (LR-test p "
            f"{t2.get('lr_test_p')}, +{t2.get('delta_auc_slope_increment')} AUC)")
    esc = t3.get("any_escalation", {})
    if esc.get("adj_or_per_sd") and (esc.get("ci") or [0])[0] > 1.0:
        parts.append(
            f"escalation events mark risk (any-escalation age-adj OR {esc['adj_or_per_sd']} "
            f"{esc['ci']}; median lead {t3.get('median_lead_h_first_norepi_to_last_esc')} h "
            f"from first norepi to the last escalation among deaths)")
    rule = (t4["rules"][0] if t4.get("rules") else {})
    verdict_head = ("ACTIONABLE EARLY-WARNING -- " if early_actionable else
                    "WEAK/limited early-warning -- ")
    res["verdict"] = (
        f"EARLY in-ICU norepinephrine requirement (MIMIC-IV, {res['n_stays_with_outcome']} stays, "
        f"{res['n_deaths']} deaths, {res['overall_mortality']:.0%} mortality): " + verdict_head
        + "; ".join(parts) + ". "
        + (f"Bedside rule: early-peak >= {rule.get('early_peak_threshold_mcg_kg_min')} mcg/kg/min "
           f"-> {rule.get('mortality_above')} mortality vs {rule.get('mortality_below')} below "
           f"(sens {rule.get('sensitivity')}, spec {rule.get('specificity')}, PPV "
           f"{rule.get('ppv')}, NPV {rule.get('npv')}; IN-SAMPLE). " if rule else "")
        + "Observational, age-adjusted ONLY -- the early requirement MARKS the sicker patient "
        "(severity confounding unaddressed here, handled elsewhere); this identifies WHO is "
        "high-risk early, not that acting on the dose changes outcome (a trial).")
    return res


def _doc(res):
    if res.get("note") and "missing" in res["note"]:
        open(os.path.join(_DOCS, "MIMIC_EARLY_WARNING.md"), "w").write(
            "# Early-warning value of the in-ICU norepinephrine requirement (MIMIC-IV)\n\n"
            f"NOT RUN: {res['note']}.\n")
        return
    t1, t2 = res["test1_early_vs_whole"], res["test2_rising_trajectory"]
    t3, t4 = res["test3_escalation"], res["test4_bedside_rule"]
    L = ["# Early-warning value of the in-ICU norepinephrine requirement (MIMIC-IV)\n",
         "Tests whether an EARLY snapshot of the norepinephrine requirement (first "
         f"{int(EARLY_HOURS)} h from the first segment) is an ACTIONABLE in-hospital-mortality "
         "early-warning, and whether the within-stay TRAJECTORY (rising dose, escalation events) "
         "adds warning beyond that early level. Real infusion timestamps + a hard endpoint -- "
         "the version VitalDB (intraoperative, no mortality) could not power. Norepinephrine "
         "(mcg/kg/min) from icu/inputevents; in-hospital death from admissions.hospital_expire_flag.\n",
         f"- Stays with norepinephrine: **{res['n_stays_with_norepi']}**; with a mortality "
         f"record: **{res['n_stays_with_outcome']}**; deaths: **{res['n_deaths']}** "
         f"({res['overall_mortality']:.0%}).\n",
         f"## 1. Does an EARLY snapshot (first {int(EARLY_HOURS)} h) already stratify death?",
         f"- **Early-peak norepi:** {t1.get('early_peak')}.",
         f"- **Early-median norepi:** {t1.get('early_median')}.",
         f"- **Whole-stay peak (reference):** {t1.get('whole_peak')}.",
         f"- **Whole-stay median (reference):** {t1.get('whole_median')}.",
         f"- **Honest rank AUC, early-peak {t1.get('auc_early_peak')} vs whole-stay-peak "
         f"{t1.get('auc_whole_peak')}** -> a {int(EARLY_HOURS)} h snapshot retains "
         f"**{t1.get('auc_warning_retained_frac')}** of the whole-stay rank signal (1.0 = no "
         "warning lost by looking early).\n",
         "## 2. Does a RISING requirement add warning BEYOND the early level? (nested logistic)",
         f"- Trajectory-eligible stays (>=4 segments over >=6 h): **{t2.get('n')}** "
         f"({t2.get('deaths')} deaths); rising (slope>0): **{t2.get('frac_rising')}**, median "
         f"slope {t2.get('median_slope')} mcg/kg/min/h.",
         f"- Base (age+early-level) AUC {t2.get('auc_base_age_early')} -> +slope AUC "
         f"{t2.get('auc_plus_slope')} (**+{t2.get('delta_auc_slope_increment')}**); slope "
         f"age-adj OR {t2.get('slope_adj_or_per_sd')}/SD; LR-test chi2 {t2.get('lr_test_chi2')}, "
         f"**p {t2.get('lr_test_p')}**.\n",
         "## 3. Escalation events -> mortality + lead time",
         f"- Definition: {t3.get('esc_def')}. Fraction of stays with >=1 escalation: "
         f"**{t3.get('frac_any_escalation')}**.",
         f"- **Any escalation (age-adjusted):** {t3.get('any_escalation')}.",
         f"- **Number of escalations (age-adjusted):** {t3.get('count_escalations')}.",
         f"- Crude mortality with vs without escalation: "
         f"{t3.get('mortality_with_escalation')} vs {t3.get('mortality_without_escalation')}.",
         f"- **Lead time** (deaths with >=1 escalation, n={t3.get('lead_time_n_deaths_with_esc')}): "
         f"median **{t3.get('median_lead_h_first_norepi_to_last_esc')} h** from first norepi to "
         f"the last escalation (IQR {t3.get('lead_iqr_h')}); median norepi recorded for "
         f"{t3.get('median_runway_h_last_esc_to_end_of_norepi')} h after that escalation.\n",
         "## 4. Simple bedside rule (early-peak norepi threshold)",
         f"_{t4.get('note')}._\n",
         "| early-peak >= | n above | mortality above | mortality below | sens | spec | PPV | NPV |",
         "|---|---|---|---|---|---|---|---|"]
    for r in t4.get("rules", []):
        L.append(f"| {r['early_peak_threshold_mcg_kg_min']} mcg/kg/min | {r['n_above']} | "
                 f"{r['mortality_above']} | {r['mortality_below']} | {r['sensitivity']} | "
                 f"{r['specificity']} | {r['ppv']} | {r['npv']} |")
    L += ["",
          "## Verdict", res["verdict"], "",
          "## Caveats",
          f"- **AUC is honest (rank-based, no tuning); the bedside-rule operating points in "
          "Test 4 are IN-SAMPLE** -- pre-specified round-number thresholds (0.2/0.3 mcg/kg/min) "
          "but evaluated on the same data, so sens/spec/PPV/NPV are optimistic vs a held-out test.",
          "- **Observational and age-adjusted ONLY.** The early requirement marks the sicker "
          "patient by construction; illness-severity confounding is NOT removed here (handled "
          "elsewhere). This identifies WHO is high-risk early, not that titrating the dose helps.",
          "- **Early window = first 6 h from the FIRST norepi segment**, not from ICU admission; "
          "a late-starting infusion's 'early' window is late in the stay. The whole-stay "
          "comparison is the same cohort, so the early-vs-whole AUC contrast is fair.",
          "- **No death timestamp here**, so 'lead time' is first-norepi -> last-escalation and "
          "'runway' is last-escalation -> end-of-norepi-record, both proxies for time-to-act, "
          "not time-to-death.",
          "- In-hospital death (hospital_expire_flag) is per-admission; the requirement is "
          "per-stay. Multi-stay admissions share an outcome (minority of stays).",
          "- Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform)."]
    open(os.path.join(_DOCS, "MIMIC_EARLY_WARNING.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.parse_args()
    if not os.path.exists(NOREPI_CSV):
        print(f"[mimic-ew] missing {NOREPI_CSV} -- run mimic_external_validation first", flush=True)
        return
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "mimic_early_warning.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[mimic-ew] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    for k in ("test1_early_vs_whole", "test2_rising_trajectory", "test3_escalation", "test4_bedside_rule"):
        if k in res:
            print(f"[mimic-ew] {k}: {json.dumps(res[k])}", flush=True)
    print("[mimic-ew] -> docs/MIMIC_EARLY_WARNING.md, cache/mimic_early_warning.json", flush=True)


if __name__ == "__main__":
    main()
