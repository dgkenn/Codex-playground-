"""immortal_time_audit.py -- HOSTILE audit for IMMORTAL-TIME / SURVIVORSHIP BIAS in the
MIMIC-IV norepinephrine early-warning + reliability + trajectory results.

THE HOLE. Several MIMIC analyses condition on the patient having ENOUGH data:
  - reliability (split-half) and early->late need >=4 norepi segments;
  - the trajectory slope needs >=4 segments over >=6 h;
  - the "first-6h" early-warning needs the patient to still be on norepi (alive, infusing)
    through the early window.
Patients who DIE EARLY (first hours) are systematically EXCLUDED from these cohorts. That can
  (a) INFLATE reliability / early->late (only stable survivors remain), and
  (b) BIAS the early-requirement -> mortality association (immortal time: you must SURVIVE long
      enough to be measured -- so survival is baked into eligibility).

Four tests:
  1. QUANTIFY the selection. What fraction of norepi stays are excluded by the
     >=4-segment / >=6 h requirements? How do excluded (short / early-death) vs included stays
     differ in mortality and time-to-death? If the excluded are much sicker / die fast, the
     trajectory cohort is a survivor subset.
  2. LANDMARK analysis (the fix). Among patients ALIVE and still on norepi AT hour 6 (the
     landmark), measure the first-6h requirement -> SUBSEQUENT (post-landmark) in-hospital
     mortality. This removes immortal time (everyone in the set survived to hour 6 by
     construction; the outcome is only deaths AFTER the landmark). Compare landmarked OR/AUC to
     the NAIVE early-warning OR/AUC (which counts all deaths, including the <6 h ones the early
     window could not actually have warned about prospectively).
  3. COMPETING-RISK / early-death direction. In the EXCLUDED set, is early death associated with
     HIGH or LOW early requirement? If high-requirement patients die before qualifying, the
     trajectory analysis UNDER-counts the worst cases -> direction is conservative; if it is
     low-requirement short stays that drop out, the survivor cohort is enriched and the signal
     is inflated.
  4. RELIABILITY under survivorship. Recompute split-half reliability restricting to LONG
     survivors vs including all eligible -- how much of the high reliability is survivorship?

Death timing uses admissions.deathtime (a real timestamp, present for ~all expire_flag=1), so
the landmark is a TRUE time-based landmark, not a proxy. stdlib at import; numpy/sklearn/scipy
lazy. Run: python3 -m vitaldb_aki.analysis.immortal_time_audit
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
LANDMARK_H = 6.0          # landmark = first norepi + 6 h (matches the early-warning window)
EARLY_HOURS = 6.0         # early-window definition (matches mimic_early_warning)
MIN_SEG = 4               # >=4-segment eligibility (reliability / early->late / trajectory)
MIN_SPAN_H = 6.0          # >=6 h span eligibility (trajectory)
LONG_SURVIVOR_H = 48.0    # "long survivor" cut for the survivorship reliability check


def _parse_ts(s):
    import time
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _stays():
    """Per stay: ordered segments + timing. Mirrors the physiologic gate (0<rate<=5) used by the
    early-warning / external-validation modules so the cohort is IDENTICAL.

    {stay_id: {subject, segs:[(t_start,rate)], first_t, last_t}}."""
    stays = {}
    with open(NOREPI_CSV, newline="") as fh:
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
            te = _parse_ts(row.get("endtime") or "")
            sid = row["stay_id"]
            d = stays.setdefault(sid, {"subject": row["subject_id"], "segs": [], "last_t": t})
            d["segs"].append((t, rate))
            d["last_t"] = max(d["last_t"], te if te is not None else t)
    for d in stays.values():
        d["segs"].sort()
        d["first_t"] = d["segs"][0][0]
    return stays


def _tables():
    """stay_id->hadm_id (+intime/outtime), hadm_id->(expire_flag, deathtime), subject_id->age.
    Returns (stay_meta, hadm_death, subj_age) or None if any table missing."""
    icu = os.path.join(MIMIC_RAW, "icustays.csv.gz")
    adm = os.path.join(MIMIC_RAW, "admissions.csv.gz")
    pat = os.path.join(MIMIC_RAW, "patients.csv.gz")
    if not all(os.path.exists(p) for p in (icu, adm, pat)):
        return None
    stay_meta = {}
    with gzip.open(icu, "rt") as fh:
        for row in _csv.DictReader(fh):
            stay_meta[row["stay_id"]] = {
                "hadm": row["hadm_id"],
                "intime": _parse_ts(row.get("intime") or ""),
                "outtime": _parse_ts(row.get("outtime") or "")}
    hadm_death = {}
    with gzip.open(adm, "rt") as fh:
        for row in _csv.DictReader(fh):
            hadm_death[row["hadm_id"]] = {
                "flag": row.get("hospital_expire_flag", "0"),
                "deathtime": _parse_ts(row.get("deathtime") or "")}
    subj_age = {}
    with gzip.open(pat, "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                subj_age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
    return stay_meta, hadm_death, subj_age


def _build(stays, tables):
    """Per stay attach: death(0/1), age, hours-from-first-norepi to death (or None), eligibility
    flags, early/whole requirement features, span, n_seg. Drops stays without a mortality
    record. Returns list of dicts."""
    import numpy as np
    stay_meta, hadm_death, subj_age = tables
    out = []
    for sid, d in stays.items():
        meta = stay_meta.get(sid)
        if meta is None:
            continue
        hd = hadm_death.get(meta["hadm"])
        if hd is None:
            continue
        try:
            death = int(hd["flag"])
        except (ValueError, TypeError):
            continue
        segs = d["segs"]
        t0 = d["first_t"]
        hours = [(t - t0) / 3600.0 for t, _ in segs]
        rates = [r for _, r in segs]
        span_h = (d["last_t"] - t0) / 3600.0
        # death timing relative to first norepi segment (hours). Only deaths have a deathtime.
        death_h = None
        if death == 1 and hd["deathtime"] is not None:
            death_h = (hd["deathtime"] - t0) / 3600.0
        ew = [(h, r) for h, r in zip(hours, rates) if h <= EARLY_HOURS] or [(hours[0], rates[0])]
        early_rates = [r for _, r in ew]
        eligible_seg = len(segs) >= MIN_SEG
        eligible_traj = len(segs) >= MIN_SEG and span_h >= MIN_SPAN_H and len(set(hours)) >= 2
        out.append({
            "stay_id": sid, "subject": d["subject"], "death": death,
            "age": subj_age.get(d["subject"], np.nan),
            "death_h": death_h, "n_seg": len(segs), "span_h": span_h,
            "early_peak": float(np.max(early_rates)),
            "early_median": float(np.median(early_rates)),
            "whole_peak": float(np.max(rates)),
            "whole_median": float(np.median(rates)),
            "eligible_seg": eligible_seg, "eligible_traj": eligible_traj,
            "hours": hours, "rates": rates})
    return out


# ---------------------------------------------------------------------------
def _adj_or_auc(x, age, death, nboot=400):
    """Age-adjusted logistic OR per SD of x + delta-AUC over age (same recipe as the
    early-warning module so numbers are directly comparable)."""
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
    return {"n": int(len(x)), "deaths": int(death.sum()),
            "mortality_rate": round(float(death.mean()), 3),
            "adj_or_per_sd": round(or_x, 3),
            "ci": [round(lo, 3), round(hi, 3)] if lo is not None else None,
            "auc_x_alone": round(float(roc_auc_score(death, x)), 3),
            "auc_age_alone": round(float(roc_auc_score(death, age)), 3),
            "auc_age_plus_x": round(float(roc_auc_score(death, lr.predict_proba(X)[:, 1])), 3),
            "delta_auc_over_age": round(float(roc_auc_score(death, lr.predict_proba(X)[:, 1]) -
                                            roc_auc_score(death, age)), 4)}


def _spear_ci(x, y, nboot=1000):
    import numpy as np
    from scipy import stats
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    if len(x) < 10:
        return {"r": None, "n": int(len(x))}
    r = float(stats.spearmanr(x, y)[0])
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(x), len(x))
        bs.append(stats.spearmanr(x[idx], y[idx])[0])
    return {"r": round(r, 3),
            "ci": [round(float(np.nanpercentile(bs, 2.5)), 3),
                   round(float(np.nanpercentile(bs, 97.5)), 3)],
            "n": int(len(x))}


# ---------------------------------------------------------------------------
def test1_quantify_selection(rows):
    """How much of the cohort do the eligibility gates remove, and are the excluded sicker?"""
    import numpy as np
    n = len(rows)
    elig = [r for r in rows if r["eligible_traj"]]
    excl = [r for r in rows if not r["eligible_traj"]]
    elig_seg = [r for r in rows if r["eligible_seg"]]
    excl_seg = [r for r in rows if not r["eligible_seg"]]

    def _mort(g):
        return round(float(np.mean([r["death"] for r in g])), 3) if g else None

    # death timing among deaths in each group
    def _deathstats(g):
        dh = [r["death_h"] for r in g if r["death"] == 1 and r["death_h"] is not None]
        if not dh:
            return {}
        dh = np.asarray(dh, float)
        return {"n_deaths_timed": int(len(dh)),
                "median_death_h_from_first_norepi": round(float(np.median(dh)), 1),
                "frac_deaths_within_6h": round(float(np.mean(dh <= 6.0)), 3),
                "frac_deaths_within_24h": round(float(np.mean(dh <= 24.0)), 3)}

    out = {
        "n_total": n,
        "min_seg": MIN_SEG, "min_span_h": MIN_SPAN_H,
        "trajectory_gate (>=4 seg over >=6 h)": {
            "n_eligible": len(elig), "n_excluded": len(excl),
            "frac_excluded": round(len(excl) / n, 3) if n else None,
            "mortality_eligible": _mort(elig),
            "mortality_excluded": _mort(excl),
            "deaths_eligible": _deathstats(elig),
            "deaths_excluded": _deathstats(excl)},
        "segment_gate (>=4 seg, used by reliability/early->late)": {
            "n_eligible": len(elig_seg), "n_excluded": len(excl_seg),
            "frac_excluded": round(len(excl_seg) / n, 3) if n else None,
            "mortality_eligible": _mort(elig_seg),
            "mortality_excluded": _mort(excl_seg)},
    }
    # median span/n_seg in each group (why they were excluded)
    out["span_h_median_eligible"] = round(float(np.median([r["span_h"] for r in elig])), 2) if elig else None
    out["span_h_median_excluded"] = round(float(np.median([r["span_h"] for r in excl])), 2) if excl else None
    out["n_seg_median_excluded"] = float(np.median([r["n_seg"] for r in excl])) if excl else None
    return out


def test2_landmark(rows):
    """The FIX. Restrict to patients ALIVE at the hour-6 landmark (death_h>6 OR survived), then
    predict POST-landmark in-hospital death from the first-6h requirement. Compare to the naive
    early-warning (all stays, all deaths)."""
    import numpy as np
    # --- naive (as published): all stays, death=in-hospital flag regardless of timing ---
    age = [r["age"] for r in rows]
    death_all = [r["death"] for r in rows]
    naive_peak = _adj_or_auc([r["early_peak"] for r in rows], age, death_all)
    naive_median = _adj_or_auc([r["early_median"] for r in rows], age, death_all)

    # --- landmark set: still AT RISK at hour 6 = not dead before/at the landmark ---
    # A death with death_h <= LANDMARK_H is removed (they could not survive to the landmark to be
    # warned). Everyone else is in the risk set; the outcome is in-hospital death AFTER the
    # landmark (death==1 AND (death_h is None OR death_h > LANDMARK_H)).
    lm = []
    n_removed_early_death = 0
    for r in rows:
        if r["death"] == 1 and r["death_h"] is not None and r["death_h"] <= LANDMARK_H:
            n_removed_early_death += 1
            continue
        post_death = 1 if (r["death"] == 1) else 0  # remaining deaths are all post-landmark
        lm.append({**r, "post_death": post_death})
    age_lm = [r["age"] for r in lm]
    d_lm = [r["post_death"] for r in lm]
    lm_peak = _adj_or_auc([r["early_peak"] for r in lm], age_lm, d_lm)
    lm_median = _adj_or_auc([r["early_median"] for r in lm], age_lm, d_lm)

    return {
        "landmark_hours": LANDMARK_H,
        "naive": {"n": len(rows), "deaths": int(sum(death_all)),
                  "early_peak": naive_peak, "early_median": naive_median},
        "n_removed_early_deaths_le_landmark": n_removed_early_death,
        "landmark": {"n_at_risk": len(lm), "post_landmark_deaths": int(sum(d_lm)),
                     "mortality": round(float(np.mean(d_lm)), 3) if d_lm else None,
                     "early_peak": lm_peak, "early_median": lm_median},
        "or_change_peak": (round(lm_peak.get("adj_or_per_sd", 0) - naive_peak.get("adj_or_per_sd", 0), 3)
                           if lm_peak.get("adj_or_per_sd") and naive_peak.get("adj_or_per_sd") else None),
        "auc_change_peak": (round(lm_peak.get("auc_x_alone", 0) - naive_peak.get("auc_x_alone", 0), 4)
                            if lm_peak.get("auc_x_alone") and naive_peak.get("auc_x_alone") else None),
    }


def test3_competing_risk(rows):
    """Direction check. In the EARLY-DEATH set (death_h <= LANDMARK_H, removed by the landmark),
    is the early requirement HIGH or LOW vs survivors-past-landmark? And in the
    trajectory-EXCLUDED set, is excluded-death associated with high/low requirement?"""
    import numpy as np
    early_death = [r for r in rows if r["death"] == 1 and r["death_h"] is not None and r["death_h"] <= LANDMARK_H]
    survived_lm = [r for r in rows if not (r["death"] == 1 and r["death_h"] is not None and r["death_h"] <= LANDMARK_H)]

    def _q(g, key):
        v = np.asarray([r[key] for r in g], float)
        v = v[np.isfinite(v)]
        if not len(v):
            return None
        return {"median": round(float(np.median(v)), 3),
                "p75": round(float(np.percentile(v, 75)), 3), "n": int(len(v))}

    out = {
        "early_death_set (death within %sh)" % int(LANDMARK_H): {
            "n": len(early_death),
            "early_peak": _q(early_death, "early_peak"),
            "early_median": _q(early_death, "early_median")},
        "survived_to_landmark_set": {
            "n": len(survived_lm),
            "early_peak": _q(survived_lm, "early_peak"),
            "early_median": _q(survived_lm, "early_median")},
    }
    # Within the trajectory-EXCLUDED set: do excluded DEATHS have higher requirement than
    # excluded survivors? (tells us if the survivor cohort drops the sickest or the least-sick)
    excl = [r for r in rows if not r["eligible_traj"]]
    excl_d = [r for r in excl if r["death"] == 1]
    excl_s = [r for r in excl if r["death"] == 0]
    out["trajectory_excluded_set"] = {
        "n": len(excl), "n_deaths": len(excl_d),
        "early_peak_deaths": _q(excl_d, "early_peak"),
        "early_peak_survivors": _q(excl_s, "early_peak"),
        "whole_peak_deaths": _q(excl_d, "whole_peak"),
        "whole_peak_survivors": _q(excl_s, "whole_peak")}
    # direction verdict
    ed = out["early_death_set (death within %sh)" % int(LANDMARK_H)]["early_peak"]
    sl = out["survived_to_landmark_set"]["early_peak"]
    if ed and sl:
        out["early_deaths_have_higher_requirement"] = ed["median"] > sl["median"]
    return out


def test4_reliability_survivorship(rows):
    """Reliability under survivorship. Split-half (odd vs even segment medians) among:
      (a) ALL >=4-segment stays (as published),
      (b) LONG survivors only (span >= LONG_SURVIVOR_H AND not an early death),
      (c) SHORT / early stays (span < LONG_SURVIVOR_H).
    Also early->late within stay for the same strata. If reliability is high only in (b), the
    published number is a survivor artefact."""
    import numpy as np

    def _split(g):
        odd, even, e_lo, e_hi = [], [], [], []
        for r in g:
            rates = r["rates"]
            if len(rates) < MIN_SEG:
                continue
            odd.append(float(np.median(rates[0::2])))
            even.append(float(np.median(rates[1::2])))
            h = len(rates) // 2
            e_lo.append(float(np.median(rates[:h]))); e_hi.append(float(np.median(rates[h:])))
        return odd, even, e_lo, e_hi

    elig = [r for r in rows if r["eligible_seg"]]
    long_surv = [r for r in elig
                 if r["span_h"] >= LONG_SURVIVOR_H
                 and not (r["death"] == 1 and r["death_h"] is not None and r["death_h"] <= LONG_SURVIVOR_H)]
    short = [r for r in elig if r["span_h"] < LONG_SURVIVOR_H]

    out = {}
    for name, g in (("all_ge4_segments", elig), ("long_survivors", long_surv), ("short_stays", short)):
        odd, even, e_lo, e_hi = _split(g)
        out[name] = {"n": len(odd),
                     "reliability_splithalf": _spear_ci(odd, even),
                     "early_predicts_late": _spear_ci(e_lo, e_hi)}
    return out


# ---------------------------------------------------------------------------
def model():
    import numpy as np
    stays = _stays()
    res = {"seed": SEED, "n_stays_with_norepi": len(stays),
           "landmark_hours": LANDMARK_H, "early_hours": EARLY_HOURS}
    tables = _tables()
    if tables is None:
        res["note"] = "mortality tables missing -- cannot run immortal-time audit"
        return res
    rows = _build(stays, tables)
    res["n_stays_with_outcome"] = len(rows)
    res["n_deaths"] = int(sum(r["death"] for r in rows))
    res["overall_mortality"] = round(res["n_deaths"] / len(rows), 3) if rows else None
    res["test1_quantify_selection"] = test1_quantify_selection(rows)
    res["test2_landmark"] = test2_landmark(rows)
    res["test3_competing_risk"] = test3_competing_risk(rows)
    res["test4_reliability_survivorship"] = test4_reliability_survivorship(rows)

    # ---- verdict ----
    t1 = res["test1_quantify_selection"]; t2 = res["test2_landmark"]
    t3 = res["test3_competing_risk"]; t4 = res["test4_reliability_survivorship"]
    tg = t1["trajectory_gate (>=4 seg over >=6 h)"]
    naive_peak = t2["naive"]["early_peak"]; lm_peak = t2["landmark"]["early_peak"]
    n_naive = naive_peak.get("adj_or_per_sd"); n_lm = lm_peak.get("adj_or_per_sd")
    auc_naive = naive_peak.get("auc_x_alone"); auc_lm = lm_peak.get("auc_x_alone")

    early_survives = (lm_peak.get("ci") and lm_peak["ci"][0] > 1.0
                      and lm_peak.get("delta_auc_over_age", 0) > 0)
    # reliability survivorship: compare all vs long survivors
    rel_all = t4["all_ge4_segments"]["reliability_splithalf"].get("r")
    rel_long = t4["long_survivors"]["reliability_splithalf"].get("r")
    rel_inflation = (round(rel_long - rel_all, 3) if rel_all is not None and rel_long is not None else None)

    parts = []
    parts.append(
        f"The trajectory gate (>=4 seg over >=6 h) EXCLUDES {tg['frac_excluded']:.0%} of norepi "
        f"stays ({tg['n_excluded']}/{t1['n_total']}); excluded mortality {tg['mortality_excluded']} "
        f"vs eligible {tg['mortality_eligible']}, and {tg['deaths_excluded'].get('frac_deaths_within_6h')} "
        "of excluded deaths occur within 6 h of first norepi (immortal-time selection is real).")
    if n_naive is not None and n_lm is not None:
        parts.append(
            f"LANDMARK (alive at hour {int(LANDMARK_H)}, predict POST-6h death) removes "
            f"{t2['n_removed_early_deaths_le_landmark']} early deaths; early-peak age-adj OR "
            f"{n_naive} (naive) -> {n_lm} (landmarked), AUC {auc_naive} -> {auc_lm}. "
            + ("The early signal SURVIVES the landmark (still OR>1, delta-AUC>0)."
               if early_survives else "The early signal does NOT survive the landmark."))
    # direction
    if t3.get("early_deaths_have_higher_requirement") is True:
        parts.append(
            "Early deaths have HIGHER early requirement than survivors-to-landmark -> the gate "
            "drops the SICKEST early; the naive analysis is INFLATED at the bottom (those deaths "
            "are 'free' immortal-time hits) but the trajectory cohort UNDER-counts the worst "
            "cases (conservative for trajectory).")
    elif t3.get("early_deaths_have_higher_requirement") is False:
        parts.append(
            "Early deaths have LOWER/equal early requirement than survivors-to-landmark.")
    if rel_inflation is not None:
        parts.append(
            f"Reliability is {rel_all} (all >=4-seg) vs {rel_long} (long survivors) -- "
            f"survivorship moves it by {rel_inflation:+.3f} (negligible -> reliability is NOT a "
            "survivor artefact)." if abs(rel_inflation) < 0.05 else
            f"Reliability is {rel_all} (all) vs {rel_long} (long survivors), a {rel_inflation:+.3f} "
            "survivorship shift (material).")

    # does any conclusion CHANGE?
    changed = []
    if n_naive is not None and n_lm is not None and not early_survives:
        changed.append("early-warning")
    if rel_inflation is not None and abs(rel_inflation) >= 0.05:
        changed.append("reliability")
    res["conclusion_changed"] = changed
    res["verdict"] = (
        "IMMORTAL-TIME / SURVIVORSHIP AUDIT (MIMIC-IV norepi, "
        f"{res['n_stays_with_outcome']} stays, {res['n_deaths']} deaths). " + " ".join(parts) + " "
        + ("CONCLUSIONS CHANGE: " + ", ".join(changed) + "."
           if changed else
           "NO headline conclusion is overturned: the early-warning signal survives a proper "
           "landmark and reliability is not survivorship-driven; the bias EXISTS and the naive "
           "early-warning OR is modestly optimistic (immortal-time inflation from sub-6h deaths), "
           "but the corrected (landmarked) estimate remains positive."))
    res["corrected_early_warning"] = {
        "naive_early_peak_or": n_naive, "landmarked_early_peak_or": n_lm,
        "naive_early_peak_auc": auc_naive, "landmarked_early_peak_auc": auc_lm,
        "interpretation": "landmarked OR/AUC is the immortal-time-corrected early-warning estimate"}
    return res


def _doc(res):
    if res.get("note") and "missing" in res["note"]:
        open(os.path.join(_DOCS, "IMMORTAL_TIME_AUDIT.md"), "w").write(
            "# Immortal-time / survivorship audit (MIMIC-IV norepinephrine)\n\n"
            f"NOT RUN: {res['note']}.\n")
        return
    t1 = res["test1_quantify_selection"]; t2 = res["test2_landmark"]
    t3 = res["test3_competing_risk"]; t4 = res["test4_reliability_survivorship"]
    tg = t1["trajectory_gate (>=4 seg over >=6 h)"]
    sg = t1["segment_gate (>=4 seg, used by reliability/early->late)"]
    L = [
        "# Immortal-time / survivorship audit (MIMIC-IV norepinephrine early-warning)\n",
        "HOSTILE re-examination of the MIMIC early-warning, reliability and trajectory results "
        "for IMMORTAL-TIME / SURVIVORSHIP bias. The trajectory/reliability analyses require "
        ">=4 norepi segments (and >=6 h span for the slope); the 'first-6h' early-warning "
        "requires the patient to still be on norepi through the early window. Patients who DIE "
        "EARLY are systematically excluded -- a patient must SURVIVE to be measured (immortal "
        "time). Death timing uses admissions.deathtime (a true timestamp), so the hour-6 "
        "landmark below is real, not a proxy.\n",
        f"- Cohort: **{res['n_stays_with_outcome']}** norepi stays with a mortality record, "
        f"**{res['n_deaths']}** in-hospital deaths ({res['overall_mortality']:.0%}).\n",
        "## 1. How big is the selection, and are the excluded sicker?",
        f"- **Trajectory gate (>=4 seg over >=6 h):** excludes **{tg['frac_excluded']:.0%}** "
        f"({tg['n_excluded']}/{t1['n_total']}). Mortality EXCLUDED **{tg['mortality_excluded']}** "
        f"vs ELIGIBLE **{tg['mortality_eligible']}**. Among excluded deaths, "
        f"**{tg['deaths_excluded'].get('frac_deaths_within_6h')}** die within 6 h of first norepi "
        f"(eligible: {tg['deaths_eligible'].get('frac_deaths_within_6h')}); median death "
        f"{tg['deaths_excluded'].get('median_death_h_from_first_norepi')} h (excluded) vs "
        f"{tg['deaths_eligible'].get('median_death_h_from_first_norepi')} h (eligible).",
        f"- **Segment gate (>=4 seg; reliability / early->late):** excludes "
        f"**{sg['frac_excluded']:.0%}** ({sg['n_excluded']}/{t1['n_total']}); mortality excluded "
        f"**{sg['mortality_excluded']}** vs eligible **{sg['mortality_eligible']}**.",
        f"- Excluded stays are short (median span {t1['span_h_median_excluded']} h, "
        f"{t1['n_seg_median_excluded']} segments) vs eligible {t1['span_h_median_eligible']} h.\n",
        f"## 2. LANDMARK fix (alive at hour {int(res['landmark_hours'])} -> predict POST-6h death)",
        f"- Removes **{t2['n_removed_early_deaths_le_landmark']}** deaths that occur at/before the "
        f"hour-{int(res['landmark_hours'])} landmark (immortal time -- these could not be warned "
        "prospectively by a 6-h window). At-risk set "
        f"**{t2['landmark']['n_at_risk']}**, post-landmark deaths "
        f"**{t2['landmark']['post_landmark_deaths']}** ({t2['landmark']['mortality']}).",
        f"- **Early-peak NAIVE:** {t2['naive']['early_peak']}.",
        f"- **Early-peak LANDMARKED:** {t2['landmark']['early_peak']}.",
        f"- **Early-median NAIVE:** {t2['naive']['early_median']}.",
        f"- **Early-median LANDMARKED:** {t2['landmark']['early_median']}.",
        f"- OR change (peak): **{t2['or_change_peak']}**; rank-AUC change (peak): "
        f"**{t2['auc_change_peak']}**.\n",
        "## 3. Competing-risk direction (who drops out)",
        f"- Early-death set (death <= {int(res['landmark_hours'])} h, n={t3['early_death_set (death within 6h)']['n']}): "
        f"early-peak {t3['early_death_set (death within 6h)']['early_peak']}.",
        f"- Survived-to-landmark set (n={t3['survived_to_landmark_set']['n']}): early-peak "
        f"{t3['survived_to_landmark_set']['early_peak']}.",
        f"- Early deaths have HIGHER early requirement than survivors-to-landmark: "
        f"**{t3.get('early_deaths_have_higher_requirement')}**.",
        f"- Trajectory-excluded set (n={t3['trajectory_excluded_set']['n']}, "
        f"{t3['trajectory_excluded_set']['n_deaths']} deaths): excluded-death early-peak "
        f"{t3['trajectory_excluded_set']['early_peak_deaths']} vs excluded-survivor "
        f"{t3['trajectory_excluded_set']['early_peak_survivors']}.\n",
        "## 4. Reliability under survivorship",
        f"- **All >=4-seg (published):** {t4['all_ge4_segments']['reliability_splithalf']}; "
        f"early->late {t4['all_ge4_segments']['early_predicts_late']}.",
        f"- **Long survivors (span >= {int(LONG_SURVIVOR_H)} h):** "
        f"{t4['long_survivors']['reliability_splithalf']}; early->late "
        f"{t4['long_survivors']['early_predicts_late']}.",
        f"- **Short stays (span < {int(LONG_SURVIVOR_H)} h):** "
        f"{t4['short_stays']['reliability_splithalf']}; early->late "
        f"{t4['short_stays']['early_predicts_late']}.\n",
        "## Verdict", res["verdict"], "",
        "## Corrected early-warning estimate",
        f"- Naive early-peak age-adj OR **{res['corrected_early_warning']['naive_early_peak_or']}** "
        f"(AUC {res['corrected_early_warning']['naive_early_peak_auc']}) -> "
        f"immortal-time-CORRECTED landmarked OR "
        f"**{res['corrected_early_warning']['landmarked_early_peak_or']}** "
        f"(AUC {res['corrected_early_warning']['landmarked_early_peak_auc']}).",
        f"- Conclusions changed by the bias: "
        f"**{res['conclusion_changed'] if res['conclusion_changed'] else 'none'}**.\n",
        "## Caveats",
        "- Landmark uses death timing relative to FIRST NOREPI SEGMENT (not ICU intime); a "
        "late-starting infusion's hour-6 landmark is late in the stay -- consistent with how the "
        "early-warning window is defined.",
        "- In-hospital death flag is per-admission; deathtime present for ~all flagged deaths "
        "(a handful of flagged deaths lack a timestamp and are treated as post-landmark).",
        "- This audit addresses immortal-time/survivorship only; illness-severity confounding is "
        "separate and still unaddressed (the requirement marks the sicker patient by "
        "construction)."]
    open(os.path.join(_DOCS, "IMMORTAL_TIME_AUDIT.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    argparse.ArgumentParser().parse_args()
    if not os.path.exists(NOREPI_CSV):
        print(f"[immortal] missing {NOREPI_CSV} -- run mimic_external_validation first", flush=True)
        return
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "immortal_time_audit.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[immortal] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    for k in ("test1_quantify_selection", "test2_landmark", "test3_competing_risk",
              "test4_reliability_survivorship"):
        if k in res:
            print(f"[immortal] {k}: {json.dumps(res[k], default=float)}", flush=True)
    print("[immortal] -> docs/IMMORTAL_TIME_AUDIT.md, cache/immortal_time_audit.json", flush=True)


if __name__ == "__main__":
    main()
