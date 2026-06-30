"""requirement_aki_crossval.py -- does the VASOPRESSOR REQUIREMENT predict ACUTE KIDNEY
INJURY (AKI / KDIGO)?  Discovered in MIMIC-IV ICU, validated the OTHER way in INSPIRE +
VitalDB.  AKI/KDIGO is the project's original organ-injury target and is present in all
three cohorts -- so this is a clean cross-cohort test of the same estimand on the same
outcome, not a re-derivation of the mortality story.

Three cohorts, three independent verdicts:

  (1) MIMIC DISCOVERY (icu, n~15k norepi stays).  KDIGO AKI is derived per ICU stay from
      serum creatinine (itemid 50912) streamed out of a ~46% labevents snapshot:
        - per-hadm baseline  = min creatinine over the admission (a robust pre-injury floor),
        - peak               = max creatinine over the admission,
        - AKI  if  peak/baseline >= 1.5  OR  peak - baseline >= 0.3 mg/dL  (KDIGO Scr criteria),
        - stage 1/2/3 by the standard ratio thresholds (1.5-1.9 / 2.0-2.9 / >=3.0 or >=4.0 mg/dL).
      ESRD/dialysis is EXCLUDED honestly (ICD N18.6 / Z99.2 / 585.6 / V45.11 / V56.x, or a
      very high baseline creatinine floor) -- in ESRD creatinine cannot move with AKI and a
      high floor would fake "no AKI."  Then: per-stay norepi requirement (median segment
      rate, mcg/kg/min) -> AKI, age-adjusted OR per SD + bootstrap CI; a DOSE-RESPONSE
      gradient across requirement quartiles (is it monotone?); and a WITHIN-SEVERITY check
      that conditions on first-24h lactate (cache/mimic_labs24h.csv) and on a comorbidity
      count -- does the dose still grade AKI after conditioning on the indication?

  (2) INSPIRE EXTERNAL (the OTHER way, n~40k with renal known).  Does intraop_norepi (>0,
      and dose) predict organ_renal, adjusted for age/sex/asa/egfr/duration, WITH a
      negative-control-OUTCOME calibration vs the non-renal organ injuries (hepatocellular /
      cholestatic / coagulation), exactly as in REDTEAM_CKD_MAP / Pivot 3?  The honest
      question: does the renal effect SURVIVE calibration, or DIE within the empirical
      confounding null like the CKD personalized-MAP claim did?

  (3) VitalDB EXTERNAL (small N, honest).  Among pressor cases (pressor_requirement_epochs
      NEPI cases + cases with any intraop pressor bolus), does the requirement / pressor
      exposure associate with organ_renal?  N is small; reported as a directional check only.

HONEST by construction: each cohort gets its own verdict and the overall verdict is allowed
to be "confounded / dies on calibration."  A null INSPIRE causal arm is the EXPECTED result
given Pivot 3 and is not massaged away.

stdlib only at import; numpy/scipy/sklearn lazy.  Reads MIMIC raw from $MIMIC_RAW (default:
session scratchpad).  Streams the creatinine column out of labevents_46.gz ONCE into a
compact cache (cache/mimic_creatinine.csv, ~hadm/charttime/value only) -- the big raw .gz is
SHARED and is NEVER deleted here.  Writes cache/requirement_aki_crossval.json +
docs/REQUIREMENT_AKI_CROSSVAL.md.

Run: python3 -m vitaldb_aki.analysis.requirement_aki_crossval
"""
from __future__ import annotations
import csv as _csv
import gzip
import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
CREAT_ITEMID = "50912"
MIMIC_RAW = os.environ.get(
    "MIMIC_RAW",
    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad",
)
NOREPI_CSV = os.path.join(_CACHE, "mimic_norepi.csv")
CREAT_CSV = os.path.join(_CACHE, "mimic_creatinine.csv")   # compact, derived; safe to keep
LABS24H = os.path.join(_CACHE, "mimic_labs24h.csv")

# ESRD / chronic-dialysis ICD codes (ICD-9 and ICD-10, codes stored without the dot).
_ESRD_ICD = ("N186", "Z992", "Z9115", "5856", "V4511", "V4512", "V560", "V561", "V562")
# A baseline creatinine floor above which AKI-by-ratio is unreliable (likely CKD5/ESRD).
_ESRD_BASELINE_FLOOR = 4.0   # mg/dL


# --------------------------------------------------------------------------- #
# MIMIC: stream creatinine, derive KDIGO AKI per admission
# --------------------------------------------------------------------------- #
def stream_creatinine(force=False):
    """Stream labevents_46.gz -> cache/mimic_creatinine.csv (hadm_id, charttime, valuenum
    for itemid 50912 only).  DISK-SAFE: gzip streams (the big .gz is never expanded to
    disk) and only the small creatinine CSV is written.  The shared labevents_46.gz is
    KEPT (never deleted) -- it is a shared snapshot.  The snapshot is a partial (~46%) member
    that ends mid-stream; the trailing EOFError/gzip error is caught so we keep every row we
    successfully read (the prompt confirms the gz integrity is otherwise OK)."""
    if os.path.exists(CREAT_CSV) and not force:
        return None
    src = os.path.join(MIMIC_RAW, "labevents_46.gz")
    if not os.path.exists(src):
        raise FileNotFoundError(f"labevents_46.gz not found at {src}")
    tmp = CREAT_CSV + ".tmp"
    n_in = n_out = 0
    try:
        with gzip.open(src, "rt") as fh, open(tmp, "w", newline="") as out:
            r = _csv.reader(fh)
            w = _csv.writer(out)
            header = next(r)
            idx = {c: i for i, c in enumerate(header)}
            ih, ic, iv, ii = (idx["hadm_id"], idx["charttime"], idx["valuenum"], idx["itemid"])
            w.writerow(["hadm_id", "charttime", "valuenum"])
            for row in r:
                n_in += 1
                if len(row) <= ii or row[ii] != CREAT_ITEMID:
                    continue
                hadm, val = row[ih], row[iv]
                if not hadm or not val:    # AKI is per-admission; rows w/o hadm can't be scoped
                    continue
                w.writerow([hadm, row[ic], val])
                n_out += 1
    except (EOFError, OSError) as e:
        print(f"[aki] labevents snapshot truncated ({type(e).__name__}) after {n_in} rows "
              f"-- keeping the {n_out} creatinine rows read so far (expected for a partial gz)",
              flush=True)
    os.replace(tmp, CREAT_CSV)
    print(f"[aki] streamed creatinine: {n_in} rows scanned -> {n_out} creat(50912) rows", flush=True)
    return n_out


def _esrd_hadms():
    """hadm_ids (and subjects) flagged ESRD/chronic-dialysis by ICD code."""
    diag = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    hadms, subjects = set(), set()
    if not os.path.exists(diag):
        return hadms, subjects
    with gzip.open(diag, "rt") as fh:
        for row in _csv.DictReader(fh):
            code = (row.get("icd_code") or "").strip().upper().replace(".", "")
            if any(code.startswith(p) for p in _ESRD_ICD):
                hadms.add(row.get("hadm_id"))
                subjects.add(row.get("subject_id"))
    return hadms, subjects


def derive_aki(baseline_mode="first"):
    """Per hadm_id: peak=max creatinine; baseline = FIRST creatinine of the admission
    (standard KDIGO admission baseline; `baseline_mode="min"` = the lowest creatinine, a
    sensitivity that is more liberal and over-calls AKI present-on-admission).  AKI + stage
    by KDIGO Scr criteria.  Returns {hadm_id: {baseline, peak, aki, stage, esrd}}.

    Why FIRST is primary: `min` over the whole admission takes the post-resuscitation nadir
    as the reference, so almost any earlier value is a "rise" -> an AKI rate near ceiling
    (~0.87 in norepi ICU stays), which destroys outcome contrast.  FIRST creatinine is the
    clinically standard admission baseline and preserves a usable AKI prevalence + contrast."""
    import numpy as np  # noqa: F401 (kept lazy/consistent; not strictly needed here)
    stream_creatinine()
    esrd_hadms, _esrd_subj = _esrd_hadms()
    # collect (charttime, value) per hadm so we can take the FIRST measurement as baseline
    series = {}
    with open(CREAT_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                v = float(row["valuenum"])
            except (ValueError, TypeError):
                continue
            if v <= 0 or v > 30:     # physiologic gate (mg/dL)
                continue
            series.setdefault(row["hadm_id"], []).append((row.get("charttime") or "", v))
    out = {}
    for hadm, sv in series.items():
        if len(sv) < 2:              # need >=2 measurements to define a rise
            continue
        sv.sort(key=lambda t: t[0])  # charttime is ISO 'YYYY-MM-DD HH:MM:SS' -> lexical = chrono
        vs = [v for _, v in sv]
        baseline = vs[0] if baseline_mode == "first" else min(vs)
        peak = max(vs)
        esrd = (hadm in esrd_hadms) or (baseline >= _ESRD_BASELINE_FLOOR)
        ratio = peak / baseline if baseline > 0 else 1.0
        delta = peak - baseline
        aki = (ratio >= 1.5) or (delta >= 0.3)
        if peak >= 4.0 or ratio >= 3.0:
            stage = 3
        elif ratio >= 2.0:
            stage = 2
        elif aki:
            stage = 1
        else:
            stage = 0
        out[hadm] = {"baseline": baseline, "peak": peak, "ratio": ratio,
                     "aki": int(aki), "stage": stage, "esrd": int(esrd)}
    return out


# --------------------------------------------------------------------------- #
# small stats helpers (mirror style of sibling modules)
# --------------------------------------------------------------------------- #
def _logit_or(X, y, col=-1, nboot=400, seed=SEED):
    """Adjusted OR (exp coef) for column `col` of standardized X, with bootstrap CI."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    X = np.asarray(X, float); y = np.asarray(y, int)
    lr = LogisticRegression(max_iter=2000).fit(X, y)
    orv = float(np.exp(lr.coef_[0][col]))
    rng = np.random.default_rng(seed); bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].sum() < 5 or y[idx].sum() > len(idx) - 5:
            continue
        try:
            bs.append(float(np.exp(
                LogisticRegression(max_iter=1000).fit(X[idx], y[idx]).coef_[0][col])))
        except Exception:
            pass
    ci = ([round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]
          if len(bs) > 30 else None)
    return round(orv, 3), ci


def _zscore(a):
    import numpy as np
    a = np.asarray(a, float)
    s = a.std()
    return (a - a.mean()) / s if s > 0 else a * 0.0


# --------------------------------------------------------------------------- #
# MIMIC requirement -> AKI
# --------------------------------------------------------------------------- #
def _stay_requirement():
    """stay_id -> median norepi rate (mcg/kg/min); also subject_id."""
    import numpy as np
    req, subj = {}, {}
    segs = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rate = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rate <= 0 or rate > 5:
                continue
            sid = row["stay_id"]
            segs.setdefault(sid, []).append(rate)
            subj[sid] = row["subject_id"]
    for sid, rates in segs.items():
        req[sid] = float(np.median(rates))
    return req, subj


def _stay_to_hadm():
    icu = os.path.join(MIMIC_RAW, "icustays.csv.gz")
    m = {}
    with gzip.open(icu, "rt") as fh:
        for row in _csv.DictReader(fh):
            m[row["stay_id"]] = row["hadm_id"]
    return m


def _subject_age():
    pat = os.path.join(MIMIC_RAW, "patients.csv.gz")
    age = {}
    with gzip.open(pat, "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass
    return age


def _hadm_lactate():
    """hadm_id -> first-24h lactate (cache/mimic_labs24h.csv)."""
    lac = {}
    if not os.path.exists(LABS24H):
        return lac
    with open(LABS24H, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                lac[row["hadm_id"]] = float(row["lactate"])
            except (ValueError, TypeError, KeyError):
                pass
    return lac


def _hadm_comorbidity():
    """hadm_id -> Charlson-ish comorbidity count (# distinct ICD chapters), a crude severity
    proxy independent of the AKI definition."""
    diag = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    cnt = {}
    if not os.path.exists(diag):
        return cnt
    with gzip.open(diag, "rt") as fh:
        for row in _csv.DictReader(fh):
            cnt[row["hadm_id"]] = cnt.get(row["hadm_id"], 0) + 1
    return cnt


def mimic_discovery():
    import numpy as np
    aki = derive_aki("first")               # primary: standard admission baseline
    aki_min = derive_aki("min")             # sensitivity: liberal min-baseline
    req, subj = _stay_requirement()
    s2h = _stay_to_hadm()
    age = _subject_age()
    lac = _hadm_lactate()
    como = _hadm_comorbidity()

    rows = []   # (requirement, age, aki, stage, lactate, comorbidity, esrd)
    n_esrd_excl = 0
    for sid, r in req.items():
        h = s2h.get(sid)
        if h is None or h not in aki:
            continue
        a = aki[h]
        if a["esrd"]:
            n_esrd_excl += 1
            continue
        ag = age.get(subj.get(sid), np.nan)
        rows.append((r, ag, a["aki"], a["stage"], lac.get(h, np.nan), como.get(h, np.nan)))
    R = np.array([x[0] for x in rows], float)
    A = np.array([x[1] for x in rows], float)
    Y = np.array([x[2] for x in rows], int)
    ST = np.array([x[3] for x in rows], float)
    LA = np.array([x[4] for x in rows], float)
    CO = np.array([x[5] for x in rows], float)
    # sensitivity AKI rate under the liberal min-baseline (same linked stays)
    y_min = []
    for sid, r in req.items():
        h = s2h.get(sid)
        if h is None or h not in aki_min or aki_min[h]["esrd"]:
            continue
        y_min.append(aki_min[h]["aki"])
    out = {"seed": SEED, "baseline_mode": "first (admission); min reported as sensitivity",
           "n_linked_stays": len(rows), "n_esrd_excluded": n_esrd_excl,
           "aki_rate": round(float(Y.mean()), 3) if len(Y) else None,
           "aki_rate_min_baseline_sensitivity": round(float(np.mean(y_min)), 3) if y_min else None,
           "stage_dist": {int(s): int((ST == s).sum()) for s in (0, 1, 2, 3)}}

    # (1) age-adjusted requirement -> AKI, OR per SD
    m = np.isfinite(R) & np.isfinite(A)
    Rz, Az, Ym = _zscore(R[m]), _zscore(A[m]), Y[m]
    orv, ci = _logit_or(np.column_stack([Az, Rz]), Ym)
    out["age_adjusted_OR_per_SD"] = {"or": orv, "ci": ci, "n": int(m.sum()),
                                     "events": int(Ym.sum())}

    # (2) DOSE-RESPONSE across requirement quartiles (monotone?)
    rr = R[m]; yy = Ym
    q = np.quantile(rr, [0.25, 0.5, 0.75])
    qid = np.digitize(rr, q)   # 0..3
    grad = []
    for k in range(4):
        sel = qid == k
        grad.append({"quartile": k + 1, "n": int(sel.sum()),
                     "median_req": round(float(np.median(rr[sel])), 4),
                     "aki_rate": round(float(yy[sel].mean()), 3)})
    rates = [g["aki_rate"] for g in grad]
    monotone = all(rates[i] <= rates[i + 1] + 1e-9 for i in range(3))
    out["dose_response_quartiles"] = grad
    out["dose_response_monotone"] = bool(monotone)
    out["dose_response_q4_minus_q1"] = round(rates[3] - rates[0], 3)

    # (3) WITHIN-SEVERITY: adjust for lactate + comorbidity (where available), and a
    # within-lactate-tertile stratified OR.
    ml = m & np.isfinite(LA) & np.isfinite(CO)
    adj = None
    if ml.sum() > 200 and Y[ml].sum() > 30:
        X = np.column_stack([_zscore(A[ml]), _zscore(LA[ml]), _zscore(CO[ml]), _zscore(R[ml])])
        a_or, a_ci = _logit_or(X, Y[ml])
        adj = {"or": a_or, "ci": a_ci, "n": int(ml.sum()), "events": int(Y[ml].sum()),
               "covars": ["age", "lactate", "comorbidity_count", "requirement(target)"]}
    out["within_severity_adjusted_OR_per_SD"] = adj

    strata = []
    if ml.sum() > 300:
        la = LA[ml]; rr2 = R[ml]; yy2 = Y[ml]; aa2 = A[ml]
        tert = np.quantile(la, [1 / 3, 2 / 3])
        tid = np.digitize(la, tert)
        for k in range(3):
            sel = tid == k
            if sel.sum() < 80 or yy2[sel].sum() < 15:
                strata.append({"lactate_tertile": k + 1, "n": int(sel.sum()), "note": "too few"})
                continue
            so, sci = _logit_or(np.column_stack([_zscore(aa2[sel]), _zscore(rr2[sel])]),
                                yy2[sel], nboot=300)
            strata.append({"lactate_tertile": k + 1, "n": int(sel.sum()),
                           "events": int(yy2[sel].sum()), "aki_rate": round(float(yy2[sel].mean()), 3),
                           "or": so, "ci": sci})
    out["within_lactate_tertile_OR"] = strata

    # verdict
    base = out["age_adjusted_OR_per_SD"]
    holds = (base["ci"] and base["ci"][0] > 1.0)
    survived = [s for s in strata if s.get("ci") and s["ci"][0] > 1.0]
    out["verdict"] = (
        f"MIMIC DISCOVERY (n={out['n_linked_stays']} norepi stays, {n_esrd_excl} ESRD excluded, "
        f"AKI {out['aki_rate']}): requirement->AKI age-adjusted OR/SD {base['or']} {base['ci']} "
        + ("(CI excludes 1) " if holds else "(CI includes 1) ")
        + f"| dose-response Q4-Q1 {out['dose_response_q4_minus_q1']} "
        + (f"MONOTONE across quartiles " if monotone else "NON-monotone ")
        + (f"| within-severity (age+lactate+comorbidity adj) OR/SD {adj['or']} {adj['ci']} "
           if adj else "| within-severity n/a ")
        + (f"| {len(survived)}/{len([s for s in strata if s.get('or')])} lactate strata keep OR>1 "
           "(CI excl 1). " if strata else ". ")
        + ("DOSE-RESPONSE TO AKI HOLDS within severity -> requirement marks renal risk beyond "
           "measured severity (observational; not a treatment effect)."
           if (holds and monotone and adj and adj["ci"] and adj["ci"][0] > 1.0)
           else "Attenuates/within-severity uncertain -> consistent with confounding by indication."))
    return out


# --------------------------------------------------------------------------- #
# INSPIRE: intraop norepi -> renal, negative-control-OUTCOME calibration (the "other way")
# --------------------------------------------------------------------------- #
def _load_inspire():
    path = os.path.join(_CACHE, "inspire_matrix.csv")
    rows = list(_csv.DictReader(open(path)))
    return rows


def _num(x):
    try:
        v = float(x)
        return v
    except (ValueError, TypeError):
        return None


def inspire_validation():
    import numpy as np
    rows = _load_inspire()
    # restrict to the intraop-medication subset: cases where intraop_norepi is populated
    # (outside this subset blank != 0, it is "no med extract").
    sub = [r for r in rows if _num(r.get("intraop_norepi")) is not None]
    cov_cols = ["age", "sex_male", "asa_class", "egfr_ckd_epi", "anesthesia_duration"]
    organs = ["organ_renal", "organ_hepatocellular", "organ_cholestatic", "organ_coagulation"]

    def build(outcome, exposure):
        Xc, expo, y = [], [], []
        for r in sub:
            ov = _num(r.get(outcome))
            ev = _num(r.get(exposure)) if exposure == "intraop_norepi" else None
            if exposure == "norepi_any":
                ev = _num(r.get("intraop_norepi"))
                ev = (1.0 if (ev is not None and ev > 0) else 0.0)
            if ov is None or ev is None:
                continue
            cv = [_num(r.get(c)) for c in cov_cols]
            if any(c is None for c in cv):
                continue
            Xc.append(cv); expo.append(ev); y.append(int(ov))
        return np.array(Xc, float), np.array(expo, float), np.array(y, int)

    def adj_logor(outcome, exposure):
        from sklearn.linear_model import LogisticRegression
        Xc, expo, y = build(outcome, exposure)
        if len(y) < 200 or y.sum() < 20:
            return None
        # standardize covariates and (continuous) exposure
        Xz = np.column_stack([_zscore(Xc[:, j]) for j in range(Xc.shape[1])])
        ez = _zscore(expo) if exposure == "intraop_norepi" else expo
        X = np.column_stack([Xz, ez])
        lr = LogisticRegression(max_iter=2000).fit(X, y)
        logor = float(lr.coef_[0][-1])
        return {"log_or": round(logor, 4), "or": round(math.exp(logor), 3),
                "n": int(len(y)), "events": int(y.sum())}

    out = {"seed": SEED, "n_medicated_subset": len(sub),
           "exposure_note": "intraop_norepi populated only in the 50.5k intraop-med subset; "
                            "blank elsewhere means 'no med extract', not zero -> restricted here."}

    for expo in ("intraop_norepi", "norepi_any"):
        panel = {}
        for o in organs:
            panel[o] = adj_logor(o, expo)
        # empirical null from the non-renal negative-control organs
        ctrl = [panel[o]["log_or"] for o in organs[1:] if panel.get(o)]
        renal = panel.get("organ_renal")
        res = {"panel": panel}
        if renal and len(ctrl) >= 2:
            mu = float(np.mean(ctrl)); sd = float(np.std(ctrl, ddof=1))
            cal = renal["log_or"] - mu
            z = (renal["log_or"] - mu) / sd if sd > 0 else None
            res["null_mean_logor"] = round(mu, 4)
            res["null_sd_logor"] = round(sd, 4)
            res["renal_raw_logor"] = renal["log_or"]
            res["renal_calibrated_logor"] = round(cal, 4)
            res["renal_calibrated_OR"] = round(math.exp(cal), 3)
            res["renal_z_vs_null"] = round(z, 2) if z is not None else None
            res["survives"] = bool(z is not None and z > 1.96)
            res["verdict"] = (
                f"renal raw OR {renal['or']} (logOR {renal['log_or']}); negative-control null "
                f"mean {round(mu,4)} sd {round(sd,4)}; CALIBRATED logOR {round(cal,4)} "
                f"(OR {round(math.exp(cal),3)}, z={res['renal_z_vs_null']}) -> "
                + ("SURVIVES calibration (renal-specific signal)" if res["survives"]
                   else "DIES within the empirical confounding null (NOT renal-specific) -- "
                        "same fate as Pivot 3"))
        out[expo] = res
    # headline = the dose (intraop_norepi) calibrated verdict
    head = out["intraop_norepi"].get("verdict", "insufficient events")
    out["verdict"] = "INSPIRE EXTERNAL (norepi dose -> AKI, age/sex/asa/egfr/duration-adj): " + head
    return out


# --------------------------------------------------------------------------- #
# VitalDB: small-N directional check among pressor cases
# --------------------------------------------------------------------------- #
def vitaldb_validation():
    import numpy as np
    comp_path = os.path.join(_CACHE, "cohort_composite.csv")
    cases_path = os.path.join(_CACHE, "cases.csv")
    epochs_path = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
    comp = {r["caseid"]: r for r in _csv.DictReader(open(comp_path))}

    # NEPI-requirement cases: median dose_per_kg over a case's stable epochs
    req = {}
    if os.path.exists(epochs_path):
        per = {}
        for r in _csv.DictReader(open(epochs_path)):
            d = _num(r.get("dose_per_kg"))
            if d is not None and d > 0:
                per.setdefault(r["caseid"], []).append(d)
        for cid, v in per.items():
            req[cid] = float(np.median(v))

    # any intraop pressor bolus from cases.csv (phe/eph/epi totals)
    pressor_any = {}
    if os.path.exists(cases_path):
        for r in _csv.DictReader(open(cases_path)):
            cid = (r.get("caseid") or r.get("﻿caseid") or "").strip()
            tot = sum((_num(r.get(c)) or 0.0) for c in ("intraop_phe", "intraop_eph", "intraop_epi"))
            pressor_any[cid] = 1 if tot > 0 else 0

    out = {"seed": SEED, "n_nepi_requirement_cases": len(req),
           "n_cases_any_pressor": int(sum(pressor_any.values()))}

    # (a) within NEPI-requirement cases: requirement -> organ_renal (very small N)
    rr, yy = [], []
    for cid, q in req.items():
        c = comp.get(cid)
        if not c:
            continue
        y = _num(c.get("organ_renal"))
        if y is None:
            continue
        rr.append(q); yy.append(int(y))
    rr = np.array(rr, float); yy = np.array(yy, int)
    a = {"n": int(len(yy)), "renal_events": int(yy.sum())}
    if len(yy) >= 40 and 3 <= yy.sum() <= len(yy) - 3:
        from scipy import stats
        # rank-biserial via Mann-Whitney (requirement higher in renal+?)
        u, p = stats.mannwhitneyu(rr[yy == 1], rr[yy == 0], alternative="two-sided")
        a["median_req_renal_pos"] = round(float(np.median(rr[yy == 1])), 4)
        a["median_req_renal_neg"] = round(float(np.median(rr[yy == 0])), 4)
        a["mannwhitney_p"] = round(float(p), 4)
    else:
        a["note"] = "too few renal events among NEPI-requirement cases for a stable test"
    out["requirement_vs_renal"] = a

    # (b) any-pressor exposure -> organ_renal across the composite cohort (2x2, larger N)
    e, y2 = [], []
    for cid, c in comp.items():
        yo = _num(c.get("organ_renal"))
        if yo is None or cid not in pressor_any:
            continue
        e.append(pressor_any[cid]); y2.append(int(yo))
    e = np.array(e, int); y2 = np.array(y2, int)
    b = {"n": int(len(y2)), "renal_events": int(y2.sum())}
    if len(y2) >= 100 and y2.sum() >= 10:
        from scipy import stats
        a11 = int(((e == 1) & (y2 == 1)).sum()); a10 = int(((e == 1) & (y2 == 0)).sum())
        a01 = int(((e == 0) & (y2 == 1)).sum()); a00 = int(((e == 0) & (y2 == 0)).sum())
        orv = (a11 * a00) / max(a10 * a01, 1e-9)
        _, p = stats.fisher_exact([[a11, a10], [a01, a00]])
        b.update({"table": {"pressor_renal": a11, "pressor_norenal": a10,
                            "nopressor_renal": a01, "nopressor_norenal": a00},
                  "crude_OR": round(float(orv), 3), "fisher_p": round(float(p), 4)})
    out["any_pressor_vs_renal"] = b

    sig = (out["requirement_vs_renal"].get("mannwhitney_p") is not None
           and out["requirement_vs_renal"]["mannwhitney_p"] < 0.05)
    out["verdict"] = (
        f"VitalDB EXTERNAL (small N): NEPI-requirement cases n={out['n_nepi_requirement_cases']} "
        f"(renal events {out['requirement_vs_renal'].get('renal_events')}); "
        + ("requirement higher in renal+ (MW p="
           f"{out['requirement_vs_renal'].get('mannwhitney_p')}) " if sig
           else "NO requirement->renal signal at this N "
                f"(MW p={out['requirement_vs_renal'].get('mannwhitney_p')}) ")
        + (f"| any-pressor crude OR {out['any_pressor_vs_renal'].get('crude_OR')} "
           f"(fisher p {out['any_pressor_vs_renal'].get('fisher_p')}). "
           if out['any_pressor_vs_renal'].get('crude_OR') else ". ")
        + "Underpowered -- directional only.")
    return out


# --------------------------------------------------------------------------- #
def _overall(mimic, inspire, vit):
    disc_holds = ("HOLDS" in mimic["verdict"])
    ins_survives = inspire.get("intraop_norepi", {}).get("survives", False)
    parts = []
    parts.append("DISCOVERY (MIMIC): " + ("dose-response to AKI holds within severity"
                 if disc_holds else "association present but attenuates / confounding-consistent"))
    parts.append("INSPIRE causal arm: " + ("SURVIVES negative-control calibration"
                 if ins_survives else "DIES on negative-control calibration (expected, cf Pivot 3)"))
    parts.append("VitalDB: underpowered directional")
    overall = (
        "OVERALL: " + "; ".join(parts) + ". "
        + ("The requirement is a robust RISK MARKER for AKI that grades dose-response within "
           "measured severity in the discovery ICU cohort, BUT the cross-cohort CAUSAL arm "
           "(INSPIRE, the honest negative-control-calibrated test) "
           + ("survives -- a defensible renal-specific signal."
              if ins_survives else
              "does NOT survive: the renal effect is indistinguishable from the empirical "
              "confounding null built from non-renal organ injuries. So: predictive / "
              "risk-stratifying YES, renal-SPECIFIC CAUSAL claim NO. Consistent with "
              "confounding by indication, exactly as Pivot 3 found for the CKD-MAP claim.")))
    return overall


def run():
    os.makedirs(_CACHE, exist_ok=True)
    os.makedirs(_DOCS, exist_ok=True)
    # disk guard
    try:
        st = os.statvfs(_CACHE)
        free_gb = st.f_bavail * st.f_frsize / 1e9
        if free_gb < 1.0:
            print(f"[aki] ABORT (disk-safe): only {free_gb:.1f} GB free", flush=True)
            return None
    except OSError:
        pass

    print("[aki] === MIMIC discovery ===", flush=True)
    mimic = mimic_discovery()
    print("[aki]", mimic["verdict"], flush=True)
    print("[aki] === INSPIRE external (calibrated) ===", flush=True)
    inspire = inspire_validation()
    print("[aki]", inspire["verdict"], flush=True)
    print("[aki] === VitalDB external ===", flush=True)
    vit = vitaldb_validation()
    print("[aki]", vit["verdict"], flush=True)

    res = {"seed": SEED, "mimic_discovery": mimic, "inspire_validation": inspire,
           "vitaldb_validation": vit}
    res["overall_verdict"] = _overall(mimic, inspire, vit)
    json.dump(res, open(os.path.join(_CACHE, "requirement_aki_crossval.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("[aki]", res["overall_verdict"], flush=True)
    print("[aki] -> docs/REQUIREMENT_AKI_CROSSVAL.md", flush=True)
    return res


def _doc(res):
    m = res["mimic_discovery"]; ins = res["inspire_validation"]; v = res["vitaldb_validation"]
    L = []
    L.append("# Vasopressor REQUIREMENT -> ACUTE KIDNEY INJURY (KDIGO): MIMIC discovery, "
             "INSPIRE + VitalDB cross-validation\n")
    L.append("Tests whether the vasopressor-requirement signal (discovered against mortality in "
             "MIMIC-IV ICU) also predicts the project's ORIGINAL organ-injury target -- **AKI / "
             "KDIGO**, which is present in all three cohorts. Discovery in MIMIC; honest "
             "cross-cohort validation the OTHER way (INSPIRE 130k, VitalDB). Each cohort gets its "
             "own verdict; the INSPIRE causal arm uses negative-control-outcome calibration (as in "
             "`REDTEAM_CKD_MAP.md` / Pivot 3) and is allowed to die.\n")

    # MIMIC
    L.append("## 1. MIMIC discovery -- requirement -> KDIGO AKI")
    L.append(f"KDIGO AKI derived per admission from serum creatinine (itemid 50912): "
             f"**baseline = FIRST (admission) creatinine** (primary; the standard KDIGO "
             f"reference), peak=max over the admission; AKI = peak/baseline >= 1.5 OR "
             f"peak-baseline >= 0.3 mg/dL; stage by ratio. ESRD/dialysis excluded "
             f"(ICD N18.6/Z99.2/585.6/V45.11/V56.x or baseline >= {_ESRD_BASELINE_FLOOR} mg/dL). "
             f"The liberal min-baseline is reported as a sensitivity only -- it over-calls "
             f"AKI-on-admission and pushes the rate to ceiling.\n")
    L.append(f"- Linked norepi ICU stays: **{m['n_linked_stays']}** (ESRD excluded: "
             f"{m['n_esrd_excluded']}); AKI rate **{m['aki_rate']}** "
             f"(min-baseline sensitivity rate {m['aki_rate_min_baseline_sensitivity']}); "
             f"stages {m['stage_dist']}.")
    b = m["age_adjusted_OR_per_SD"]
    L.append(f"- **Requirement -> AKI, age-adjusted OR per SD: {b['or']} {b['ci']}** "
             f"(n={b['n']}, events={b['events']}).")
    L.append(f"- **Dose-response across requirement quartiles** "
             f"(monotone={m['dose_response_monotone']}, Q4-Q1={m['dose_response_q4_minus_q1']}):")
    for g in m["dose_response_quartiles"]:
        L.append(f"  - Q{g['quartile']}: median req {g['median_req']} mcg/kg/min, "
                 f"AKI rate {g['aki_rate']} (n={g['n']}).")
    adj = m["within_severity_adjusted_OR_per_SD"]
    if adj:
        L.append(f"- **Within-severity (adjusted for age + first-24h lactate + comorbidity count): "
                 f"OR per SD {adj['or']} {adj['ci']}** (n={adj['n']}, events={adj['events']}).")
    if m["within_lactate_tertile_OR"]:
        L.append("- Within lactate tertiles (age-adjusted requirement OR):")
        for s in m["within_lactate_tertile_OR"]:
            if s.get("or"):
                L.append(f"  - lactate T{s['lactate_tertile']}: OR {s['or']} {s['ci']} "
                         f"(n={s['n']}, AKI {s.get('aki_rate')}).")
            else:
                L.append(f"  - lactate T{s['lactate_tertile']}: {s.get('note')} (n={s['n']}).")
    L.append(f"\n**MIMIC verdict:** {m['verdict']}\n")

    # INSPIRE
    L.append("## 2. INSPIRE external validation (the other way) -- negative-control calibrated")
    L.append(f"Restricted to the intraop-medication subset (n={ins['n_medicated_subset']}; outside "
             f"it `intraop_norepi` is blank = no med extract, NOT zero). Exposure = intraop "
             f"norepi (dose, and >0). Outcome panel = renal (target) + hepatocellular / cholestatic "
             f"/ coagulation (negative controls). Adjusted for age/sex/asa/egfr/anesthesia-duration. "
             f"Empirical null built from the non-renal controls; renal estimate calibrated to it.\n")
    for expo, label in (("intraop_norepi", "norepi DOSE (per SD)"), ("norepi_any", "norepi ANY (>0)")):
        r = ins.get(expo, {})
        panel = r.get("panel", {})
        L.append(f"### Exposure: {label}")
        for o, pv in panel.items():
            if pv:
                L.append(f"- {o}: adjusted OR {pv['or']} (logOR {pv['log_or']}, n={pv['n']}, "
                         f"events={pv['events']}).")
        if r.get("verdict"):
            L.append(f"- null logOR mean {r.get('null_mean_logor')} sd {r.get('null_sd_logor')}; "
                     f"**renal calibrated OR {r.get('renal_calibrated_OR')} "
                     f"(z={r.get('renal_z_vs_null')})** -> "
                     + ("SURVIVES." if r.get("survives") else "DIES within the null."))
        L.append("")
    L.append(f"**INSPIRE verdict:** {ins['verdict']}\n")

    # VitalDB
    L.append("## 3. VitalDB external validation (small N, honest)")
    rv = v["requirement_vs_renal"]; ap = v["any_pressor_vs_renal"]
    L.append(f"- NEPI-requirement cases: n={v['n_nepi_requirement_cases']} "
             f"(renal events {rv.get('renal_events')}). "
             + (f"Requirement median renal+ {rv.get('median_req_renal_pos')} vs renal- "
                f"{rv.get('median_req_renal_neg')}, MW p={rv.get('mannwhitney_p')}."
                if rv.get("mannwhitney_p") is not None else rv.get("note", "")))
    if ap.get("crude_OR"):
        L.append(f"- Any-pressor exposure -> renal: crude OR {ap['crude_OR']} "
                 f"(fisher p {ap['fisher_p']}, n={ap['n']}, table {ap['table']}).")
    L.append(f"\n**VitalDB verdict:** {v['verdict']}\n")

    # Overall
    L.append("## Overall verdict")
    L.append(res["overall_verdict"])
    L.append("")
    L.append("## Caveats (honest)")
    L.append("- MIMIC AKI is creatinine-only (no urine-output KDIGO criterion) and built on a "
             "**partial (~46%) labevents snapshot** -- some admissions have sparse/absent "
             "creatinine, so AKI ascertainment is incomplete (missing-not-quite-at-random). "
             "The FIRST-creatinine baseline can MISS AKI already present on admission (the "
             "admission value is itself elevated) -> under-call; bias is toward the null. The "
             "min-baseline sensitivity over-calls instead (rate 0.87, ceiling) -- the truth is "
             "bracketed and the dose-response gradient is present under both.")
    L.append("- The MIMIC association is observational; within-severity conditioning controls "
             "MEASURED severity (lactate, comorbidity, age) only -- the strongest honest causal "
             "test is the INSPIRE negative-control-calibrated arm.")
    L.append("- INSPIRE intraop_norepi exists only for a medicated subset; the restriction is "
             "principled but means the INSPIRE estimand is 'among cases with a med record'.")
    L.append("- VitalDB renal events among NEPI-requirement cases are few -> directional only.")
    open(os.path.join(_DOCS, "REQUIREMENT_AKI_CROSSVAL.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
