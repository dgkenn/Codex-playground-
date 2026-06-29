"""mimic_sofa_lactate.py -- the DECISIVE 'signal vs just-sicker' test.

Re-runs the MIMIC-IV requirement->mortality association adjusting for LACTATE (the shock-
severity gold standard) + the lab components of SOFA (creatinine=renal, bilirubin=liver,
platelets=coagulation) measured in the FIRST 24h of admission, ON TOP of the prior crude
severity model (age, number of distinct vasopressors [cardiovascular SOFA proxy], comorbidity
count, ICU LOS). If the norepinephrine-requirement OR SURVIVES this, the dose carries mortality
information BEYOND severity; if it COLLAPSES, it is mostly a severity marker (the honest answer
to 'how do we know it's signal and not just that sick patients got more drug').

First-24h labs (not worst-ever) avoid reverse causation (a dying patient's late lactate).
TRUE SOFA also needs GCS + PaO2/FiO2 (only in the 30GB chartevents) -> we approximate with the
lab components + #vasopressors and say so.

DISK-SAFE: stream-filters labevents (2.4GB gz, never full-decompress) for 4 itemids into a small
per-admission CSV, deletes the raw after. Reuses cache/mimic_norepi.csv + cache/mimic_vaso_count.csv.
Run: python3 -m vitaldb_aki.analysis.mimic_sofa_lactate
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
LABS_CSV = os.path.join(_CACHE, "mimic_labs24h.csv")
LAB_ITEMS = {"50813": "lactate", "50885": "bilirubin", "50912": "creatinine", "51265": "platelets"}


def _ts(s):
    import time
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _admittime():
    import gzip as gz
    at = {}
    with gz.open(os.path.join(MIMIC_RAW, "admissions.csv.gz"), "rt") as fh:
        for row in _csv.DictReader(fh):
            t = _ts(row.get("admittime"))
            if t is not None:
                at[row["hadm_id"]] = t
    return at


def build_labs(delete_raw=True):
    """Stream labevents -> per-hadm first-24h worst values for the 4 itemids."""
    src = os.path.join(MIMIC_RAW, "labevents.csv.gz")
    if not os.path.exists(src):
        raise FileNotFoundError(f"labevents not found at {src}")
    admit = _admittime()
    agg = {}   # hadm -> {lab: worst}
    n = nkept = 0
    with gzip.open(src, "rt") as fh:
        r = _csv.DictReader(fh)
        for row in r:
            n += 1
            lab = LAB_ITEMS.get(row.get("itemid"))
            if not lab:
                continue
            h = row.get("hadm_id")
            if not h or h not in admit:
                continue
            t = _ts(row.get("charttime"))
            if t is None or t < admit[h] or t > admit[h] + 86400:   # first 24h
                continue
            try:
                v = float(row.get("valuenum") or "nan")
            except ValueError:
                continue
            if v != v or v <= 0:
                continue
            d = agg.setdefault(h, {})
            # worst = max for lactate/creatinine/bilirubin, min for platelets
            if lab == "platelets":
                d[lab] = min(d.get(lab, v), v)
            else:
                d[lab] = max(d.get(lab, v), v)
            nkept += 1
    tmp = LABS_CSV + ".tmp"
    with open(tmp, "w", newline="") as out:
        w = _csv.writer(out); w.writerow(["hadm_id"] + list(LAB_ITEMS.values()))
        for h, d in agg.items():
            w.writerow([h] + [d.get(l, "") for l in LAB_ITEMS.values()])
    os.replace(tmp, LABS_CSV)
    print(f"[lac] labevents {n} rows -> {len(agg)} hadm with first-24h labs ({nkept} kept)", flush=True)
    if delete_raw and not os.environ.get("MIMIC_KEEP_RAW"):
        try:
            os.remove(src); print("[lac] disk-safe: removed raw labevents", flush=True)
        except OSError:
            pass


def _load(name):
    import gzip as gz
    return gz.open(os.path.join(MIMIC_RAW, name), "rt")


def model():
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    # norepi requirement per stay
    req = {}
    with open(os.path.join(_CACHE, "mimic_norepi.csv"), newline="") as fh:
        tmp = {}
        for row in _csv.DictReader(fh):
            try:
                rt = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if 0 < rt <= 5:
                tmp.setdefault(row["stay_id"], []).append(rt)
        req = {s: float(np.median(v)) for s, v in tmp.items() if v}
    vaso = {}
    with open(os.path.join(_CACHE, "mimic_vaso_count.csv"), newline="") as fh:
        for row in _csv.DictReader(fh):
            vaso[row["stay_id"]] = int(row["n_vasopressors"])
    labs = {}
    with open(LABS_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            labs[row["hadm_id"]] = {k: (float(row[k]) if row[k] not in ("", None) else np.nan)
                                    for k in LAB_ITEMS.values()}
    comorb = {}
    with _load("diagnoses_icd.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            h = row.get("hadm_id");  comorb[h] = comorb.get(h, 0) + 1 if h else comorb.get(h, 0)
    stay_hadm, stay_subj, stay_los = {}, {}, {}
    with _load("icustays.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]; stay_subj[row["stay_id"]] = row["subject_id"]
            try:
                stay_los[row["stay_id"]] = float(row["los"])
            except (ValueError, TypeError):
                stay_los[row["stay_id"]] = np.nan
    death = {}
    with _load("admissions.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                death[row["hadm_id"]] = int(row.get("hospital_expire_flag", "0"))
            except (ValueError, TypeError):
                pass
    age = {}
    with _load("patients.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
    rows = []
    for sid, r in req.items():
        h = stay_hadm.get(sid)
        if not h or h not in death or h not in labs:
            continue
        lb = labs[h]
        rows.append([r, age.get(stay_subj.get(sid), np.nan), vaso.get(sid, 1),
                     comorb.get(h, np.nan), stay_los.get(sid, np.nan),
                     lb["lactate"], lb["creatinine"], lb["bilirubin"], lb["platelets"], death[h]])
    arr = np.array([row for row in rows if all(np.isfinite(x) for x in row)], float)
    res = {"seed": SEED, "n": int(len(arr)), "deaths": int(arr[:, -1].sum()) if len(arr) else 0,
           "lab_components": list(LAB_ITEMS.values())}
    if len(arr) < 400:
        res["note"] = f"only {len(arr)} complete rows (lab coverage limits N)"; return res
    reqv, ageA, nv, com, los, lac, cr, bil, plt, dth = arr.T
    dth = dth.astype(int)
    # log-transform skewed labs
    lac, cr, bil = np.log(lac), np.log(cr), np.log(bil + 0.1)
    def or_req(cols):
        Z = np.column_stack(cols)
        Zs = (Z - Z.mean(0)) / np.where(Z.std(0) == 0, 1, Z.std(0))
        lr = LogisticRegression(max_iter=4000).fit(Zs, dth)
        return float(np.exp(lr.coef_[0][0])), lr, Zs   # requirement is col 0
    or_age, _, _ = or_req([reqv, ageA])
    or_crude, _, _ = or_req([reqv, ageA, nv, com, los])
    or_full, lr_f, Zf = or_req([reqv, ageA, nv, com, los, lac, cr, bil, plt])
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(400):
        idx = rng.integers(0, len(dth), len(dth))
        try:
            Z = Zf[idx]; bs.append(float(np.exp(LogisticRegression(max_iter=2000).fit(Z, dth[idx]).coef_[0][0])))
        except Exception:
            pass
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)
    # AUC: full severity (incl labs) WITHOUT vs WITH requirement
    def auc_of(cols):
        Z = np.column_stack(cols); Zs = (Z - Z.mean(0)) / np.where(Z.std(0) == 0, 1, Z.std(0))
        lr = LogisticRegression(max_iter=4000).fit(Zs, dth)
        return float(roc_auc_score(dth, lr.predict_proba(Zs)[:, 1]))
    auc_sev = auc_of([ageA, nv, com, los, lac, cr, bil, plt])
    auc_full = auc_of([reqv, ageA, nv, com, los, lac, cr, bil, plt])
    res.update({
        "mortality_rate": round(float(dth.mean()), 3),
        "or_req_age_adjusted": round(or_age, 3),
        "or_req_crude_severity": round(or_crude, 3),
        "or_req_FULL_with_lactate_sofalabs": round(or_full, 3),
        "or_full_ci": [round(lo, 3), round(hi, 3)] if lo else None,
        "attenuation_age_to_full_pct": round(100 * (or_age - or_full) / (or_age - 1), 1) if or_age > 1 else None,
        "auc_full_severity_only": round(auc_sev, 3),
        "auc_severity_plus_requirement": round(auc_full, 3),
        "delta_auc_over_full_severity": round(auc_full - auc_sev, 4)})
    surv = bool(or_full > 1.15 and res["or_full_ci"] and res["or_full_ci"][0] > 1.0)
    res["verdict"] = (
        f"Requirement->mortality OR per SD: {or_age} (age) -> {or_crude} (crude severity) -> "
        f"**{or_full}** (FULL: + first-24h lactate + SOFA labs [creatinine/bilirubin/platelets]), "
        f"CI {res['or_full_ci']}; total attenuation {res['attenuation_age_to_full_pct']}%. " +
        ("SIGNAL BEYOND SEVERITY: the requirement OR survives adjustment for lactate + the SOFA lab "
         f"components, still adding AUC +{res['delta_auc_over_full_severity']} over the full severity "
         "model. So it is not MERELY 'sicker patients got more drug'." if surv else
         "MOSTLY SEVERITY: once lactate + SOFA labs are adjusted, the requirement OR collapses toward "
         "1 -- the mortality association is largely explained by illness severity. Honest answer: the "
         "dose is mostly a severity marker for mortality.") +
        " CAVEAT: SOFA approximated by lab components + #vasopressors; no GCS / PaO2-FiO2 (chartevents).")
    return res


def _doc(res):
    L = ["# MIMIC requirement->mortality adjusted for LACTATE + SOFA labs (signal vs just-sicker)\n",
         "The decisive test of 'how do we know the dose is signal, not just that sick patients got "
         "more drug'. Adds first-24h lactate (shock-severity gold standard) + the lab components of "
         "SOFA (creatinine=renal, bilirubin=liver, platelets=coagulation) on top of the crude "
         "severity model (age, #vasopressors, comorbidity, ICU-LOS).\n",
         f"- Complete-case stays: **{res.get('n')}** ({res.get('deaths')} deaths, rate "
         f"{res.get('mortality_rate')}). Lab components: {res.get('lab_components')}.\n"]
    if "or_req_FULL_with_lactate_sofalabs" in res:
        L += ["## Requirement -> mortality OR per SD, adding severity in steps",
              f"- age-adjusted: **{res['or_req_age_adjusted']}**",
              f"- + crude severity (#vasopressors, comorbidity, LOS): **{res['or_req_crude_severity']}**",
              f"- + **lactate + SOFA labs (FULL)**: **{res['or_req_FULL_with_lactate_sofalabs']}** "
              f"(95% CI {res['or_full_ci']})",
              f"- total attenuation age->full: **{res['attenuation_age_to_full_pct']}%**.",
              f"- AUC: full-severity-only {res['auc_full_severity_only']} -> +requirement "
              f"{res['auc_severity_plus_requirement']} (**ΔAUC {res['delta_auc_over_full_severity']}**).\n",
              "## Verdict", res["verdict"], ""]
    else:
        L += ["## Verdict", res.get("note", "insufficient"), ""]
    L += ["## Caveats",
          "- First-24h WORST labs (max lactate/creatinine/bilirubin, min platelets) avoid end-of-life "
          "reverse causation. Lab coverage limits N (only stays with first-24h labs).",
          "- SOFA is APPROXIMATED: lab components (renal/liver/coag) + #vasopressors (cardiovascular). "
          "NO neurological (GCS) or respiratory (PaO2/FiO2) components -- those need the 30GB "
          "chartevents. A full SOFA could attenuate slightly further.",
          "- Observational; norepinephrine dose is a known severity/mortality marker -- this quantifies "
          "how much of the requirement->mortality link is independent of measured severity."]
    open(os.path.join(_DOCS, "MIMIC_SOFA_LACTATE.md"), "w").write("\n".join(L) + "\n")


def main():
    try:
        st = os.statvfs(_CACHE)
        if st.f_bavail * st.f_frsize / 1e9 < 1.0:
            print("[lac] ABORT (disk-safe): <1GB free", flush=True); return
    except OSError:
        pass
    if not os.path.exists(LABS_CSV):
        build_labs()
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "mimic_sofa_lactate.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[lac] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    print("[lac] -> docs/MIMIC_SOFA_LACTATE.md", flush=True)


if __name__ == "__main__":
    main()
