"""mimic_mortality_severity.py -- HONEST severity-adjustment of the MIMIC-IV
requirement -> mortality association.

The obvious reviewer attack on 'norepi requirement predicts death (OR 3.8/SD)' is: the dose
is just an ILLNESS-SEVERITY marker. This adjusts the norepinephrine-requirement mortality OR
for the best severity proxies available from manageable MIMIC tables:
  * NUMBER OF DISTINCT VASOPRESSORS per stay (multi-pressor support = refractory shock -- the
    single most direct severity signal) -- from icu/inputevents (all vasoconstrictor itemids);
  * COMORBIDITY BURDEN (count of distinct ICD diagnoses per admission) -- hosp/diagnoses_icd;
  * ICU LENGTH OF STAY -- icu/icustays;
  * AGE -- hosp/patients.
Reports the norepi-requirement mortality OR crude (age-only) vs FULLY adjusted, the
attenuation, and the AUC the requirement adds OVER the full severity model. If the OR largely
survives -> the requirement carries information beyond crude severity; if it collapses -> it is
mostly a severity marker (the honest answer).

DISK-SAFE: stream-filters inputevents (never full-decompress), deletes the raw .gz after.
Reads MIMIC raw from $MIMIC_RAW. Reuses cache/mimic_norepi.csv (norepi segments) for the
requirement. stdlib only at import; numpy/sklearn lazy.
Run: python3 -m vitaldb_aki.analysis.mimic_mortality_severity
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
VASO_CLASS = {  # vasoCONSTRICTOR itemid -> drug class (for distinct-pressor count)
    "221906": "norepi", "221289": "epi", "229617": "epi", "222315": "vasopressin",
    "221749": "phenyl", "229630": "phenyl", "229631": "phenyl", "229632": "phenyl",
    "221662": "dopamine", "229764": "dopamine"}
VASO_CSV = os.path.join(_CACHE, "mimic_vaso_count.csv")


def _build_vaso_count(delete_raw=True):
    """Stream inputevents -> per-stay set of distinct vasopressor classes -> cache CSV."""
    src = os.path.join(MIMIC_RAW, "inputevents.csv.gz")
    if not os.path.exists(src):
        raise FileNotFoundError(f"inputevents not found at {src}")
    stay_classes = {}
    n = 0
    with gzip.open(src, "rt") as fh:
        r = _csv.DictReader(fh)
        for row in r:
            n += 1
            cls = VASO_CLASS.get(row.get("itemid"))
            if not cls:
                continue
            sid = row.get("stay_id")
            if not sid:
                continue
            stay_classes.setdefault(sid, set()).add(cls)
    tmp = VASO_CSV + ".tmp"
    with open(tmp, "w", newline="") as out:
        w = _csv.writer(out); w.writerow(["stay_id", "n_vasopressors", "classes"])
        for sid, cl in stay_classes.items():
            w.writerow([sid, len(cl), "|".join(sorted(cl))])
    os.replace(tmp, VASO_CSV)
    print(f"[sev] inputevents {n} rows -> {len(stay_classes)} stays with vasopressors", flush=True)
    if delete_raw and not os.environ.get("MIMIC_KEEP_RAW"):
        try:
            os.remove(src); print("[sev] disk-safe: removed raw inputevents", flush=True)
        except OSError:
            pass


def _comorbidity():
    """Per-hadm distinct-ICD-code count from hosp/diagnoses_icd."""
    src = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    if not os.path.exists(src):
        return {}
    cnt = {}
    with gzip.open(src, "rt") as fh:
        for row in _csv.DictReader(fh):
            h = row.get("hadm_id")
            if h:
                cnt[h] = cnt.get(h, 0) + 1
    return cnt


def _norepi_req():
    """Per-stay norepi requirement (median rate) from cache/mimic_norepi.csv."""
    import numpy as np
    stay = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rt = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rt <= 0 or rt > 5:
                continue
            stay.setdefault(row["stay_id"], []).append(rt)
    return {s: float(np.median(v)) for s, v in stay.items() if v}


def model():
    import numpy as np, gzip as gz
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    req = _norepi_req()
    comorb = _comorbidity()
    vaso = {}
    with open(VASO_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            vaso[row["stay_id"]] = int(row["n_vasopressors"])
    # stay -> hadm, subject, los
    stay_hadm, stay_subj, stay_los = {}, {}, {}
    with gz.open(os.path.join(MIMIC_RAW, "icustays.csv.gz"), "rt") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]; stay_subj[row["stay_id"]] = row["subject_id"]
            try:
                stay_los[row["stay_id"]] = float(row["los"])
            except (ValueError, TypeError):
                stay_los[row["stay_id"]] = np.nan
    hadm_death = {}
    with gz.open(os.path.join(MIMIC_RAW, "admissions.csv.gz"), "rt") as fh:
        for row in _csv.DictReader(fh):
            hadm_death[row["hadm_id"]] = row.get("hospital_expire_flag", "0")
    subj_age = {}
    with gz.open(os.path.join(MIMIC_RAW, "patients.csv.gz"), "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                subj_age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
    rows = []
    for sid, r in req.items():
        h = stay_hadm.get(sid)
        if not h or h not in hadm_death:
            continue
        try:
            d = int(hadm_death[h])
        except (ValueError, TypeError):
            continue
        rows.append((r, subj_age.get(stay_subj.get(sid), np.nan), vaso.get(sid, 1),
                     comorb.get(h, np.nan), stay_los.get(sid, np.nan), d))
    arr = np.array([row for row in rows if all(np.isfinite(x) for x in row)], float)
    res = {"seed": SEED, "n": int(len(arr)), "deaths": int(arr[:, 5].sum()) if len(arr) else 0}
    if len(arr) < 500:
        res["note"] = "too few complete rows"; return res
    reqv, age, nv, com, los, death = arr.T
    death = death.astype(int)
    def fit(cols):
        Z = np.column_stack(cols)
        Zs = (Z - Z.mean(0)) / np.where(Z.std(0) == 0, 1, Z.std(0))
        lr = LogisticRegression(max_iter=3000).fit(Zs, death)
        return lr, Zs
    reqs = (reqv - reqv.mean()) / reqv.std()
    # crude (age only), full severity-adjusted
    lr_c, Zc = fit([age, reqv]); or_c = float(np.exp(lr_c.coef_[0][1]))
    lr_f, Zf = fit([age, nv, com, los, reqv]); or_f = float(np.exp(lr_f.coef_[0][-1]))
    # bootstrap CI on adjusted OR
    rng = np.random.default_rng(SEED); bs = []
    Zf_full = Zf
    for _ in range(400):
        idx = rng.integers(0, len(death), len(death))
        try:
            bs.append(float(np.exp(LogisticRegression(max_iter=1500).fit(Zf_full[idx], death[idx]).coef_[0][-1])))
        except Exception:
            pass
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)
    # AUC: severity-only vs +requirement
    lr_sev, Zsev = fit([age, nv, com, los])
    auc_sev = float(roc_auc_score(death, lr_sev.predict_proba(Zsev)[:, 1]))
    auc_full = float(roc_auc_score(death, lr_f.predict_proba(Zf)[:, 1]))
    res.update({
        "mortality_rate": round(float(death.mean()), 3),
        "or_age_adjusted_per_sd": round(or_c, 3),
        "or_fully_adjusted_per_sd": round(or_f, 3),
        "or_fully_adjusted_ci": [round(lo, 3), round(hi, 3)] if lo else None,
        "attenuation_pct": round(100 * (or_c - or_f) / (or_c - 1), 1) if or_c > 1 else None,
        "auc_severity_only": round(auc_sev, 3), "auc_severity_plus_requirement": round(auc_full, 3),
        "delta_auc_over_severity": round(auc_full - auc_sev, 4),
        "severity_covariates": ["age", "n_vasopressors", "comorbidity_count", "icu_los"]})
    surv = bool(or_f > 1.2 and res["or_fully_adjusted_ci"] and res["or_fully_adjusted_ci"][0] > 1.0)
    res["verdict"] = (
        f"Requirement->mortality OR {or_c} (age-adj) -> {or_f} (FULLY adjusted for n-vasopressors + "
        f"comorbidity + ICU-LOS + age), CI {res['or_fully_adjusted_ci']}; attenuation "
        f"{res['attenuation_pct']}%. " +
        ("SURVIVES severity adjustment -- the requirement carries mortality information BEYOND crude "
         f"severity (adds AUC +{res['delta_auc_over_severity']} over the severity model). The dose is "
         "not merely a severity proxy." if surv else
         "LARGELY a severity marker -- the association collapses once multi-pressor burden + "
         "comorbidity are adjusted. Honest: the mortality link is mostly illness severity.") +
        " NOTE: no lactate/SOFA (would attenuate further); observational.")
    return res


def _doc(res):
    L = ["# MIMIC-IV requirement -> mortality: severity-adjusted (honest)\n",
         "Does the norepinephrine-requirement mortality association survive adjustment for illness "
         "severity (number of distinct vasopressors = refractory-shock marker, comorbidity burden, "
         "ICU LOS, age)? The key reviewer attack: 'the dose is just a severity marker'.\n",
         f"- Complete-case stays: **{res.get('n')}** ({res.get('deaths')} deaths, rate "
         f"{res.get('mortality_rate')}).\n"]
    if "or_fully_adjusted_per_sd" in res:
        L += [f"- Requirement mortality OR per SD: **{res['or_age_adjusted_per_sd']} (age-adjusted) "
              f"-> {res['or_fully_adjusted_per_sd']} (fully adjusted)**, CI "
              f"{res['or_fully_adjusted_ci']}; **attenuation {res['attenuation_pct']}%**.",
              f"- AUC: severity-only {res['auc_severity_only']} -> +requirement "
              f"{res['auc_severity_plus_requirement']} (**ΔAUC {res['delta_auc_over_severity']}**).",
              f"- Severity covariates: {res['severity_covariates']}.\n",
              "## Verdict", res["verdict"], ""]
    L += ["## Caveats",
          "- Severity proxies are crude: distinct-vasopressor COUNT, distinct-ICD COUNT, ICU LOS, "
          "age. NO lactate / SOFA / APACHE (not in the manageable tables) -> a full severity score "
          "would attenuate the requirement OR FURTHER. So this is an UPPER bound on the independent "
          "signal.",
          "- norepinephrine dose is a known ICU severity/mortality marker; this analysis quantifies "
          "how much survives crude-severity adjustment, honestly. Observational; not causal."]
    open(os.path.join(_DOCS, "MIMIC_MORTALITY_SEVERITY.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--rebuild-vaso", action="store_true")
    a = ap.parse_args()
    try:
        st = os.statvfs(_CACHE)
        if st.f_bavail * st.f_frsize / 1e9 < 1.0:
            print("[sev] ABORT (disk-safe): <1GB free", flush=True); return
    except OSError:
        pass
    if a.rebuild_vaso or not os.path.exists(VASO_CSV):
        _build_vaso_count()
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "mimic_mortality_severity.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[sev] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    print("[sev] -> docs/MIMIC_MORTALITY_SEVERITY.md", flush=True)


if __name__ == "__main__":
    main()
