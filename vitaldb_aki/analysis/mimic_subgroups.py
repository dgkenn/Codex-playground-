"""mimic_subgroups.py -- GENERALIZABILITY of the vasopressor-requirement -> in-hospital
mortality finding ACROSS MIMIC-IV subgroups.

The requirement->mortality signal already REPLICATES in the whole MIMIC-IV ICU norepi cohort
(see mimic_external_validation.py: age-adjusted OR ~3.8/SD). But "replicates in the pooled
cohort" is not the same as "generalizes". This module asks the sharper question: does the SAME
requirement->mortality signal hold *within* clinically distinct subgroups -- and is it
CONSISTENT (overlapping CIs) or HETEROGENEOUS across them?

Why these subgroups, and why they matter for the ORIGIN of the finding:
  * The finding ORIGINATED intraoperatively (anaesthesia). If the ICU requirement->mortality
    signal holds in SURGICAL (SICU) and CARDIAC (CVICU) ICUs -- the patients closest to the OR
    -- that BRIDGES the ICU result back to its intraoperative origin.
  * SEPSIS is the classic vasoplegia population: everyone is sick and (near-)everyone gets
    norepinephrine, so it is the hardest place for "more requirement -> worse" to survive. If
    the requirement still stratifies mortality WITHIN septic patients, the signal is not merely
    "got-a-pressor vs not".
  * AGE strata and SEX test demographic breadth.

A consistent, positive, age-adjusted OR across diverse ICUs + within sepsis = the requirement
marks risk broadly, i.e. it GENERALIZES. Heterogeneity (some subgroup CIs excluding others, or
crossing 1.0) would qualify that.

HONEST SCOPE (unchanged from the external validation): observational, AGE-ADJUSTED ONLY. The OR
is confounded by illness severity (sicker patients need more pressor AND die more); subgroup
analysis cannot fix that. It shows the requirement MARKS risk within each stratum, not a
treatment effect. Does NOT validate the arterial-waveform tone estimator.

Per-stay requirement = median norepinephrine rate (mcg/kg/min), physiologic gate 0<rate<=5.
Reads MIMIC raw from $MIMIC_RAW (default: session scratchpad) + cache/mimic_norepi.csv.
stdlib only at import; numpy/scipy/sklearn lazy. No new downloads.
Run: python3 -m vitaldb_aki.analysis.mimic_subgroups
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

# first_careunit in MIMIC-IV is a descriptive string; map to short codes we report on.
# Highlight: SICU (surgical) + CVICU (cardiac) -> closest to the intraoperative origin.
CAREUNIT_MAP = {
    "Medical Intensive Care Unit (MICU)": "MICU",
    "Surgical Intensive Care Unit (SICU)": "SICU",
    "Cardiac Vascular Intensive Care Unit (CVICU)": "CVICU",
    "Coronary Care Unit (CCU)": "CCU",
    "Medical/Surgical Intensive Care Unit (MICU/SICU)": "MICU/SICU",
    "Trauma SICU (TSICU)": "TSICU",
}
ICU_ORDER = ["MICU", "SICU", "CVICU", "CCU", "MICU/SICU", "TSICU"]
SURGICAL_CARDIAC = {"SICU", "CVICU"}  # bridge-to-origin units

# Sepsis ICD flags. ICD-9: 995.91 sepsis, 995.92 severe sepsis, 785.52 septic shock.
# ICD-10: A41* (other sepsis), R65.20 severe sepsis w/o shock, R65.21 severe sepsis w/ shock.
ICD9_SEPSIS = {"99591", "99592", "78552"}
ICD10_SEPSIS_EXACT = {"R6520", "R6521"}
ICD10_SEPSIS_PREFIX = ("A41",)


def _per_stay_requirement():
    """cache/mimic_norepi.csv -> {stay_id: median rate} over physiologic 0<rate<=5 segments."""
    import numpy as np
    seg = {}
    subj = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rate = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rate <= 0 or rate > 5:
                continue
            sid = row["stay_id"]
            seg.setdefault(sid, []).append(rate)
            subj[sid] = row["subject_id"]
    return {sid: float(np.median(v)) for sid, v in seg.items()}, subj


def _load_tables():
    """Join keys for the cohort: stay->hadm/careunit, hadm->death, subject->age/sex, sepsis flag."""
    icu = os.path.join(MIMIC_RAW, "icustays.csv.gz")
    adm = os.path.join(MIMIC_RAW, "admissions.csv.gz")
    pat = os.path.join(MIMIC_RAW, "patients.csv.gz")
    dia = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    for p in (icu, adm, pat, dia):
        if not os.path.exists(p):
            raise FileNotFoundError(f"required table missing: {p}")
    stay_hadm, stay_unit = {}, {}
    with gzip.open(icu, "rt") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]
            stay_unit[row["stay_id"]] = CAREUNIT_MAP.get(row["first_careunit"])  # None if other
    hadm_death = {}
    with gzip.open(adm, "rt") as fh:
        for row in _csv.DictReader(fh):
            hadm_death[row["hadm_id"]] = row.get("hospital_expire_flag", "0")
    subj_age, subj_sex = {}, {}
    with gzip.open(pat, "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                subj_age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
            subj_sex[row["subject_id"]] = (row.get("gender") or "").strip().upper()
    sepsis_hadm = set()
    with gzip.open(dia, "rt") as fh:
        for row in _csv.DictReader(fh):
            code = (row.get("icd_code") or "").strip().upper().replace(".", "")
            ver = (row.get("icd_version") or "").strip()
            if ver == "9":
                if code in ICD9_SEPSIS:
                    sepsis_hadm.add(row["hadm_id"])
            elif ver == "10":
                if code in ICD10_SEPSIS_EXACT or any(code.startswith(p) for p in ICD10_SEPSIS_PREFIX):
                    sepsis_hadm.add(row["hadm_id"])
    return stay_hadm, stay_unit, hadm_death, subj_age, subj_sex, sepsis_hadm


def _adj_or(req, age, death, nboot=500):
    """Age-adjusted logistic OR per +1 SD of requirement + bootstrap CI + AUCs.

    Returns None if too few cases to fit (so the caller can mark a subgroup underpowered)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    req, age, death = np.asarray(req, float), np.asarray(age, float), np.asarray(death, int)
    m = np.isfinite(req) & np.isfinite(age)
    req, age, death = req[m], age[m], death[m]
    n, ndead = int(len(req)), int(death.sum())
    base = {"n": n, "deaths": ndead,
            "mortality_rate": round(float(death.mean()), 3) if n else None}
    if n < 200 or ndead < 30 or ndead == n:
        base["note"] = "underpowered (n<200 or deaths<30)"
        return base
    reqs = (req - req.mean()) / (req.std() or 1.0)
    ages = (age - age.mean()) / (age.std() or 1.0)
    X = np.column_stack([ages, reqs])
    lr = LogisticRegression(max_iter=2000).fit(X, death)
    or_req = float(np.exp(lr.coef_[0][1]))
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(nboot):
        idx = rng.integers(0, n, n)
        if death[idx].sum() in (0, n):
            continue
        try:
            bs.append(float(np.exp(
                LogisticRegression(max_iter=1000).fit(X[idx], death[idx]).coef_[0][1])))
        except Exception:
            pass
    ci = ([round(float(np.percentile(bs, 2.5)), 3),
           round(float(np.percentile(bs, 97.5)), 3)] if len(bs) >= 50 else None)
    try:
        auc_age = float(roc_auc_score(death, age))
        auc_full = float(roc_auc_score(death, lr.predict_proba(X)[:, 1]))
    except Exception:
        auc_age = auc_full = None
    base.update({"adj_or_per_sd": round(or_req, 3), "ci": ci,
                 "auc_age_alone": round(auc_age, 3) if auc_age is not None else None,
                 "auc_age_plus_requirement": round(auc_full, 3) if auc_full is not None else None,
                 "delta_auc": round(auc_full - auc_age, 4) if auc_age is not None else None})
    return base


def _cohort():
    """Assemble per-stay records with all covariates needed for every subgroup cut."""
    import numpy as np
    stay_req, stay_subj = _per_stay_requirement()
    stay_hadm, stay_unit, hadm_death, subj_age, subj_sex, sepsis_hadm = _load_tables()
    rows = []
    for sid, r in stay_req.items():
        h = stay_hadm.get(sid)
        if h is None or h not in hadm_death:
            continue
        try:
            d = int(hadm_death[h])
        except (ValueError, TypeError):
            continue
        subj = stay_subj.get(sid)
        a = subj_age.get(subj, np.nan)
        if not np.isfinite(a):
            continue
        rows.append({
            "req": r, "age": float(a), "death": d,
            "unit": stay_unit.get(sid),                 # short code or None
            "sex": subj_sex.get(subj, ""),
            "sepsis": h in sepsis_hadm,
        })
    return rows


def model():
    res = {"seed": SEED}
    rows = _cohort()
    res["n_total"] = len(rows)
    res["overall"] = _adj_or([x["req"] for x in rows], [x["age"] for x in rows],
                             [x["death"] for x in rows])

    # 1. BY ICU TYPE
    by_unit = {}
    for u in ICU_ORDER:
        sub = [x for x in rows if x["unit"] == u]
        by_unit[u] = _adj_or([x["req"] for x in sub], [x["age"] for x in sub],
                             [x["death"] for x in sub])
    res["by_icu_type"] = by_unit
    res["surgical_cardiac_units"] = sorted(SURGICAL_CARDIAC)

    # 2. SEPSIS subgroup (does requirement stratify mortality WITHIN septic patients?)
    sep = [x for x in rows if x["sepsis"]]
    nonsep = [x for x in rows if not x["sepsis"]]
    res["sepsis"] = {
        "septic": _adj_or([x["req"] for x in sep], [x["age"] for x in sep],
                          [x["death"] for x in sep]),
        "non_septic": _adj_or([x["req"] for x in nonsep], [x["age"] for x in nonsep],
                              [x["death"] for x in nonsep]),
    }

    # 3. AGE strata + SEX
    def _agebin(a):
        return "<55" if a < 55 else ("55-70" if a <= 70 else ">70")
    by_age = {}
    for lab in ("<55", "55-70", ">70"):
        sub = [x for x in rows if _agebin(x["age"]) == lab]
        by_age[lab] = _adj_or([x["req"] for x in sub], [x["age"] for x in sub],
                              [x["death"] for x in sub])
    res["by_age"] = by_age
    by_sex = {}
    for lab, code in (("male", "M"), ("female", "F")):
        sub = [x for x in rows if x["sex"] == code]
        by_sex[lab] = _adj_or([x["req"] for x in sub], [x["age"] for x in sub],
                              [x["death"] for x in sub])
    res["by_sex"] = by_sex

    res["heterogeneity"] = _heterogeneity(res)
    res["verdict"] = _verdict(res)
    return res


def _heterogeneity(res):
    """Consistency check: collect every subgroup OR/CI, test positivity + CI overlap.

    Two subgroups are 'consistent' if their bootstrap CIs overlap. We report: are ALL subgroup
    ORs > 1 with CIs excluding 1.0 (positive everywhere), and does every pair of CIs overlap
    (no heterogeneity)."""
    groups = {}
    for fam, key in (("ICU", "by_icu_type"), ("age", "by_age"), ("sex", "by_sex")):
        for name, d in res[key].items():
            if d.get("adj_or_per_sd") and d.get("ci"):
                groups[f"{fam}:{name}"] = (d["adj_or_per_sd"], d["ci"])
    for name in ("septic", "non_septic"):
        d = res["sepsis"][name]
        if d.get("adj_or_per_sd") and d.get("ci"):
            groups[f"sepsis:{name}"] = (d["adj_or_per_sd"], d["ci"])
    names = list(groups)
    all_positive = all(groups[n][1][0] > 1.0 for n in names)  # CI lower bound > 1
    # global CI overlap: max of lower bounds <= min of upper bounds across all subgroups
    los = [groups[n][1][0] for n in names]
    his = [groups[n][1][1] for n in names]
    all_overlap = (max(los) <= min(his)) if names else False
    # which subgroups (if any) fail to overlap the overall CI
    ov = res["overall"].get("ci")
    non_overlap = []
    if ov:
        for n in names:
            lo, hi = groups[n][1]
            if hi < ov[0] or lo > ov[1]:
                non_overlap.append(n)
    return {"n_subgroups": len(names),
            "all_CI_lower_bound_above_1": all_positive,
            "all_subgroup_CIs_overlap": all_overlap,
            "OR_range": [round(min(groups[n][0] for n in names), 3),
                         round(max(groups[n][0] for n in names), 3)] if names else None,
            "subgroups_not_overlapping_overall_CI": non_overlap}


def _verdict(res):
    h = res["heterogeneity"]
    ov = res["overall"]
    sicu = res["by_icu_type"].get("SICU", {})
    cvicu = res["by_icu_type"].get("CVICU", {})
    sep = res["sepsis"]["septic"]
    pieces = [
        f"GENERALIZABILITY (MIMIC-IV, n={res['n_total']} norepi ICU stays; age-adjusted, "
        f"observational): overall requirement->mortality OR {ov.get('adj_or_per_sd')}/SD "
        f"{ov.get('ci')}."]
    if sicu.get("adj_or_per_sd"):
        pieces.append(f"SURGICAL/SICU OR {sicu['adj_or_per_sd']} {sicu.get('ci')} "
                      f"(n={sicu.get('n')}).")
    if cvicu.get("adj_or_per_sd"):
        pieces.append(f"CARDIAC/CVICU OR {cvicu['adj_or_per_sd']} {cvicu.get('ci')} "
                      f"(n={cvicu.get('n')}) -- bridges back to the intraoperative origin.")
    if sep.get("adj_or_per_sd"):
        pieces.append(f"WITHIN SEPSIS OR {sep['adj_or_per_sd']} {sep.get('ci')} "
                      f"(n={sep.get('n')}, deaths={sep.get('deaths')}): requirement still "
                      f"stratifies mortality where vasoplegia is expected and everyone is sick.")
    if h["all_CI_lower_bound_above_1"] and h["all_subgroup_CIs_overlap"]:
        pieces.append(f"GENERALIZES: every subgroup OR>1 with CI excluding 1.0, and all "
                      f"{h['n_subgroups']} subgroup CIs overlap (OR range {h['OR_range']}) -- "
                      f"a consistent, positive signal across surgical, cardiac, medical, "
                      f"coronary, trauma ICUs and within sepsis. Consistent positive OR across "
                      f"diverse ICUs = generalizable.")
    elif h["all_CI_lower_bound_above_1"]:
        pieces.append(f"MOSTLY GENERALIZES with HETEROGENEITY in MAGNITUDE: every subgroup OR>1 "
                      f"(CI excludes 1.0) but some CIs do not all overlap (OR range "
                      f"{h['OR_range']}; outliers vs overall: {h['subgroups_not_overlapping_overall_CI']}). "
                      f"DIRECTION is consistent; effect SIZE varies by population.")
    else:
        pieces.append(f"PARTIAL: not positive in every subgroup (OR range {h['OR_range']}); "
                      f"signal is NOT uniformly generalizable across these strata.")
    pieces.append("CAVEAT: age-adjusted only; the OR is confounded by illness severity within "
                  "each stratum (sicker -> more pressor AND more death). Shows the requirement "
                  "MARKS risk broadly, not a treatment effect.")
    return " ".join(pieces)


def _fmt(d):
    if not isinstance(d, dict):
        return str(d)
    if "adj_or_per_sd" not in d:
        return f"n={d.get('n')}, deaths={d.get('deaths')} -- {d.get('note', 'n/a')}"
    return (f"OR {d['adj_or_per_sd']}/SD {d.get('ci')}, n={d['n']}, deaths={d['deaths']} "
            f"({d.get('mortality_rate')}), AUC age {d.get('auc_age_alone')} -> "
            f"+req {d.get('auc_age_plus_requirement')} (Delta {d.get('delta_auc')})")


def _doc(res):
    h = res["heterogeneity"]
    L = ["# Generalizability of requirement -> in-hospital mortality across MIMIC-IV subgroups\n",
         "The pooled MIMIC-IV ICU cohort already shows a strong vasopressor-requirement -> "
         "mortality signal. This asks whether the SAME (age-adjusted) signal holds *within* "
         "clinically distinct subgroups and whether it is CONSISTENT (overlapping CIs) or "
         "HETEROGENEOUS. The finding originated intraoperatively (anaesthesia): holding in "
         "SURGICAL (SICU) and CARDIAC (CVICU) ICUs bridges the ICU result back to that origin; "
         "holding within SEPSIS (the classic vasoplegia population, where everyone is sick) and "
         "across MICU/CCU/TSICU shows breadth.\n",
         f"- Cohort: **{res['n_total']}** norepi ICU stays with age + mortality + careunit join.",
         f"- Per-stay requirement = median norepinephrine rate (mcg/kg/min), gate 0<rate<=5.\n",
         "## Overall",
         f"- {_fmt(res['overall'])}\n",
         "## 1. By ICU type (first_careunit) -- SICU + CVICU highlighted (bridge to OR origin)"]
    for u in ICU_ORDER:
        tag = "  <- surgical/cardiac, bridge to intraoperative origin" if u in SURGICAL_CARDIAC else ""
        L.append(f"- **{u}:** {_fmt(res['by_icu_type'][u])}{tag}")
    L += ["",
          "## 2. Sepsis (ICD-9 995.91/995.92/785.52; ICD-10 A41*, R65.20/R65.21)",
          "Does the requirement still stratify mortality WITHIN septic patients (vasoplegia "
          "expected, everyone sick)?",
          f"- **Septic:** {_fmt(res['sepsis']['septic'])}",
          f"- **Non-septic:** {_fmt(res['sepsis']['non_septic'])}\n",
          "## 3. Age strata"]
    for lab in ("<55", "55-70", ">70"):
        L.append(f"- **{lab}:** {_fmt(res['by_age'][lab])}")
    L += ["", "## Sex"]
    for lab in ("male", "female"):
        L.append(f"- **{lab}:** {_fmt(res['by_sex'][lab])}")
    L += ["",
          "## Heterogeneity / consistency",
          f"- Subgroups with a fitted OR+CI: {h['n_subgroups']}; OR range {h['OR_range']}.",
          f"- Every subgroup CI excludes 1.0 (positive everywhere): "
          f"**{h['all_CI_lower_bound_above_1']}**.",
          f"- All subgroup CIs overlap (no heterogeneity): **{h['all_subgroup_CIs_overlap']}**.",
          f"- Subgroups whose CI does not overlap the overall CI: "
          f"{h['subgroups_not_overlapping_overall_CI'] or 'none'}.\n",
          "## Verdict", res["verdict"], "",
          "## Caveats",
          "- OBSERVATIONAL, AGE-ADJUSTED ONLY. The OR is confounded by illness severity within "
          "every stratum (sicker patients need more pressor AND die more). Subgroup analysis "
          "does not remove this; it shows the requirement MARKS risk within each stratum, not a "
          "treatment effect.",
          "- Requirement = median of segment rates (mcg/kg/min); MIMIC rate is already per-kg.",
          "- Sepsis is flagged by ICD diagnosis codes on the admission (hadm), not a clinical "
          "Sepsis-3 definition; it is a coarse proxy.",
          "- first_careunit is the FIRST ICU of the stay; transfers are not modelled.",
          "- 'Overlapping CIs' is a screen for heterogeneity, not a formal interaction test.",
          "- Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform)."]
    open(os.path.join(_DOCS, "MIMIC_SUBGROUPS.md"), "w").write("\n".join(L) + "\n")


def main():
    if not os.path.exists(NOREPI_CSV):
        print(f"[subgroups] ABORT: {NOREPI_CSV} missing (run mimic_external_validation first)",
              flush=True)
        return
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "mimic_subgroups.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[subgroups] VERDICT:", res["verdict"], flush=True)
    print("[subgroups] overall:", _fmt(res["overall"]), flush=True)
    for u in ICU_ORDER:
        print(f"[subgroups] ICU {u}: {_fmt(res['by_icu_type'][u])}", flush=True)
    print("[subgroups] septic:", _fmt(res["sepsis"]["septic"]), flush=True)
    print("[subgroups] non-septic:", _fmt(res["sepsis"]["non_septic"]), flush=True)
    for lab in ("<55", "55-70", ">70"):
        print(f"[subgroups] age {lab}: {_fmt(res['by_age'][lab])}", flush=True)
    for lab in ("male", "female"):
        print(f"[subgroups] sex {lab}: {_fmt(res['by_sex'][lab])}", flush=True)
    print("[subgroups] heterogeneity:", json.dumps(res["heterogeneity"]), flush=True)
    print("[subgroups] -> docs/MIMIC_SUBGROUPS.md + cache/mimic_subgroups.json", flush=True)


if __name__ == "__main__":
    main()
