"""requirement_waveform_predict.py -- does the pre-existing arterial-line
WAVEFORM/MORPHOLOGY predict a patient's vasopressor DOSE-REQUIREMENT (the
vasoplegia phenotype)?

THE QUESTION
------------
Two prior findings on this VitalDB cohort frame this analysis:

  (1) pressor_requirement.py established that intraoperative MAP is FEEDBACK-
      regulated (the anaesthetist titrates norepinephrine to hold MAP at target),
      so the vasoreactivity signal is the DOSE REQUIREMENT -- the norepinephrine
      dose/kg needed to sustain MAP in [55, 80] mmHg over stable constant-infusion
      epochs -- NOT the achieved MAP. High requirement = vasoplegia.

  (2) Pivot 2 (independent_svr_validation.py / docs/PIVOT2_PREPUB_TESTS.md) showed
      the A-line MORPHOLOGY -- especially the diastolic/MAP form factor, tau decay
      and augmentation index -- tracks measured vascular tone (SVR), and survives
      the circularity attack against a thermodilution/Doppler CO source.

NEW QUESTION: does pre-existing A-line morphology PREDICT the norepinephrine
dose-requirement phenotype? If yes, one could pre-emptively flag vasoplegia-prone
patients from the waveform alone.

DESIGN (a no-extraction MERGE-AND-MODEL task -- no new waveforms downloaded)
---------------------------------------------------------------------------
  * TARGET = the per-case requirement phenotype = median dose_per_kg over that
    case's NEPI norepi-ONLY epochs with map_mean in [55, 80], requiring >= 2 such
    epochs (mirrors pressor_requirement.py exactly). Continuous; binary
    high-requirement = top tertile.
  * FEATURES = per-case A-line morphology, merged on caseid from the existing
    extraction caches (aline_sample / independent_svr_validation /
    vasoplegia_validation). The Pivot-2 carrier diastolic_over_map = art_dbp_mean /
    art_map_mean is the PRE-SPECIFIED PRIMARY feature.
  * Out-of-fold (KFold) RidgeCV/ElasticNet OOF Spearman/R2 -- OOF ONLY, never an
    in-sample R2 as the headline. Logistic OOF AUC for high-requirement vs rest.
  * Incremental value over body size (weight/age/BMI/ASA): nested OOF R2 gain.
  * Negative control: morphology vs an unrelated label (surgery duration).

HONESTY: the morphology caches and the requirement phenotype overlap on a SMALL
set of caseids (the requirement phenotype needs >=2 stable norepi-only target-band
epochs, which is rare). If the merged N < 25 this is reported as a FEASIBILITY
signal, not a result, and the verdict is FEASIBILITY-ONLY regardless of point
estimates -- a Spearman on a dozen cases is not evidence.

stdlib only at import; numpy/pandas/sklearn/scipy lazy.
Run (from repo root /home/user/Codex-playground-/):
    python3 -m vitaldb_aki.analysis.requirement_waveform_predict
"""
from __future__ import annotations
import csv as _csv
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

# --- phenotype definition (mirror pressor_requirement.py) -------------------
PRIMARY_DRUG = "NEPI"
TARGET_LO, TARGET_HI = 55.0, 80.0
MIN_EPOCHS_PER_CASE = 2
EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")

# --- morphology feature caches (keyed by caseid, A-line morphology columns) -
# preference order when a case appears in more than one (vasoplegia is largest /
# the canonical tone-validation extraction; then the circularity-clean indep set;
# then the generic sample).
MORPH_FILES = ["vasoplegia_validation.csv", "independent_svr_validation.csv",
               "aline_sample.csv"]

# the A-line morphology feature set (shape / timing / decay / coupling). Pressure
# LEVELS are included as context but the PRIMARY signal is the form factors.
MORPH_FEATURES = ["art_dbp_mean", "art_map_mean", "art_sbp_mean",
                  "art_pulse_pressure_mean", "art_tau_decay_mean",
                  "art_aug_index_mean", "art_systolic_auc_mean",
                  "art_hr_mean", "art_hr_sd", "brs_mean"]
# the Pivot-2 carrier -- PRE-SPECIFIED PRIMARY feature (computed if absent).
PRIMARY_FEATURE = "diastolic_over_map"
SIZE_FEATURES = ["weight_kg", "age", "bmi", "asa"]

OUT_JSON = os.path.join(_CACHE, "requirement_waveform_predict.json")
OUT_DOC = os.path.join(_DOCS, "REQUIREMENT_WAVEFORM_PREDICT.md")

N_FEASIBILITY = 25   # merged N below this -> feasibility-only, not a result


# ===========================================================================
# stdlib helpers (build the merged table without importing numpy)
# ===========================================================================
def _f(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "NA", "None", "NaN"):
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(_csv.DictReader(fh))


def build_phenotype():
    """Per-case requirement phenotype = median dose_per_kg over NEPI norepi-only
    epochs with map_mean in [TARGET_LO, TARGET_HI], requiring >= MIN_EPOCHS_PER_CASE.
    Returns {caseid: {dose, n_epochs}}.  (mirrors pressor_requirement.model())"""
    rows = _load(EPOCHS_CSV)
    per = {}
    for r in rows:
        if r.get("drug") != PRIMARY_DRUG:
            continue
        if str(r.get("norepi_only", "")).strip() not in ("1", "1.0", "True", "true"):
            continue
        d = _f(r.get("dose_per_kg"))
        mm = _f(r.get("map_mean"))
        if d is None or mm is None:
            continue
        if TARGET_LO <= mm <= TARGET_HI:
            per.setdefault(r["caseid"], []).append(d)
    out = {}
    for cid, doses in per.items():
        if len(doses) >= MIN_EPOCHS_PER_CASE:
            sd = sorted(doses)
            n = len(sd)
            med = sd[n // 2] if n % 2 else 0.5 * (sd[n // 2 - 1] + sd[n // 2])
            out[cid] = {"dose": float(med), "n_epochs": n}
    return out


def build_morphology():
    """Merge per-case A-line morphology from the extraction caches (preference
    order MORPH_FILES). Computes the Pivot-2 carrier diastolic_over_map =
    art_dbp_mean / art_map_mean for every case. Returns {caseid: {feat: val}}."""
    merged = {}
    for f in MORPH_FILES:
        for r in _load(os.path.join(_CACHE, f)):
            if str(r.get("aline_available", "")).strip() not in ("1", "True", "true"):
                continue
            cid = r["caseid"]
            if cid in merged:
                continue
            rec = {}
            for c in MORPH_FEATURES:
                rec[c] = _f(r.get(c))
            # Pivot-2 carrier: prefer the stored _diastolic_over_map, else compute.
            dom = _f(r.get("_diastolic_over_map"))
            if dom is None:
                dbp, amap = rec.get("art_dbp_mean"), rec.get("art_map_mean")
                dom = (dbp / amap) if (dbp is not None and amap and amap > 0) else None
            rec[PRIMARY_FEATURE] = dom
            merged[cid] = rec
    return merged


def build_covariates():
    """Per-case body-size covariates + a surgery-duration placebo label, from
    cases.csv (complete) with feature_matrix_enriched.csv fallback for bmi.
    Returns {caseid: {weight_kg, age, bmi, asa, surgery_duration_min}}."""
    out = {}
    for r in _load(os.path.join(_CACHE, "cases.csv")):
        cid = str(r.get("caseid", "") or r.get("﻿caseid", "")).strip()
        if not cid:
            continue
        ostart, oend = _f(r.get("opstart")), _f(r.get("opend"))
        dur = (oend - ostart) / 60.0 if (ostart is not None and oend is not None
                                         and oend > ostart) else None
        out[cid] = {"weight_kg": _f(r.get("weight")), "age": _f(r.get("age")),
                    "bmi": _f(r.get("bmi")), "asa": _f(r.get("asa")),
                    "surgery_duration_min": dur}
    # fill bmi / duration gaps from the enriched matrix
    for r in _load(os.path.join(_CACHE, "feature_matrix_enriched.csv")):
        cid = r.get("caseid")
        if cid not in out:
            out[cid] = {}
        rec = out[cid]
        if rec.get("bmi") is None:
            rec["bmi"] = _f(r.get("bmi"))
        if rec.get("weight_kg") is None:
            rec["weight_kg"] = _f(r.get("weight_kg"))
        if rec.get("age") is None:
            rec["age"] = _f(r.get("age"))
        if rec.get("asa") is None:
            rec["asa"] = _f(r.get("asa"))
        if rec.get("surgery_duration_min") is None:
            rec["surgery_duration_min"] = _f(r.get("surgery_duration_min"))
    return out


# ===========================================================================
# modeling (numpy/pandas/sklearn/scipy lazy)
# ===========================================================================
def _oof_ridge(X, y, seed=SEED, n_splits=5, n_rep=5):
    """OOF RidgeCV: returns mean OOF Spearman + OOF R2 over n_rep KFold repeats."""
    import numpy as np
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    n = len(y)
    nsp = min(n_splits, n)
    if nsp < 2 or X.shape[1] == 0:
        return {"spearman": None, "r2": None, "n": n}
    rs, r2s = [], []
    for rep in range(n_rep):
        oof = np.full(n, np.nan)
        for tr, te in KFold(nsp, shuffle=True, random_state=seed + rep).split(X):
            pipe = Pipeline([("i", SimpleImputer(strategy="median")),
                             ("s", StandardScaler()),
                             ("m", RidgeCV(alphas=(0.01, 0.1, 1, 10, 100)))])
            pipe.fit(X[tr], y[tr])
            oof[te] = pipe.predict(X[te])
        msk = ~np.isnan(oof)
        if msk.sum() > 4 and np.std(oof[msk]) > 1e-9:
            rs.append(float(stats.spearmanr(oof[msk], y[msk])[0]))
            ssr = float(np.sum((y[msk] - oof[msk]) ** 2))
            sst = float(np.sum((y[msk] - y[msk].mean()) ** 2))
            r2s.append(1 - ssr / sst if sst > 0 else float("nan"))
    return {"spearman": round(float(np.mean(rs)), 4) if rs else None,
            "r2": round(float(np.nanmean(r2s)), 4) if r2s else None,
            "n": n, "n_features": int(X.shape[1])}


def _oof_logistic_auc(X, ybin, seed=SEED, n_splits=5, n_rep=5):
    import numpy as np
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    n = len(ybin)
    pos = int(ybin.sum())
    nsp = min(n_splits, pos, n - pos)
    if nsp < 2 or X.shape[1] == 0:
        return {"auc": None, "n": n, "n_pos": pos}
    aucs = []
    for rep in range(n_rep):
        oof = np.full(n, np.nan)
        skf = StratifiedKFold(nsp, shuffle=True, random_state=seed + rep)
        for tr, te in skf.split(X, ybin):
            pipe = Pipeline([("i", SimpleImputer(strategy="median")),
                             ("s", StandardScaler()),
                             ("m", LogisticRegression(C=1.0, max_iter=2000))])
            pipe.fit(X[tr], ybin[tr])
            oof[te] = pipe.predict_proba(X[te])[:, 1]
        msk = ~np.isnan(oof)
        if len(set(ybin[msk].tolist())) == 2:
            aucs.append(float(roc_auc_score(ybin[msk], oof[msk])))
    return {"auc": round(float(np.mean(aucs)), 4) if aucs else None,
            "n": n, "n_pos": pos, "n_features": int(X.shape[1])}


def _spearman_ci(x, y, seed=SEED, nboot=2000):
    import numpy as np
    from scipy import stats
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    msk = np.isfinite(x) & np.isfinite(y)
    x, y = x[msk], y[msk]
    if len(x) < 4 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return None, [None, None], int(len(x))
    r = float(stats.spearmanr(x, y)[0])
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(x), len(x))
        if np.std(x[idx]) > 1e-12 and np.std(y[idx]) > 1e-12:
            bs.append(float(stats.spearmanr(x[idx], y[idx])[0]))
    ci = [round(float(np.percentile(bs, 2.5)), 4),
          round(float(np.percentile(bs, 97.5)), 4)] if bs else [None, None]
    return round(r, 4), ci, int(len(x))


def analyze():
    import numpy as np
    import pandas as pd

    pheno = build_phenotype()
    morph = build_morphology()
    cov = build_covariates()

    res = {
        "seed": SEED,
        "phenotype": {
            "definition": "median dose_per_kg over NEPI norepi-only epochs with "
                          f"map_mean in [{TARGET_LO},{TARGET_HI}], >= "
                          f"{MIN_EPOCHS_PER_CASE} epochs (mirrors pressor_requirement.py)",
            "n_cases_with_phenotype": len(pheno),
        },
        "morphology_source": {
            "files": MORPH_FILES,
            "n_cases_with_morphology": len(morph),
            "primary_feature": PRIMARY_FEATURE,
            "feature_set": MORPH_FEATURES + [PRIMARY_FEATURE],
        },
    }

    # --- MERGE ---------------------------------------------------------------
    ids = sorted(set(pheno) & set(morph), key=lambda c: int(c) if c.isdigit() else c)
    res["merged_n"] = len(ids)
    if not ids:
        res["verdict"] = "NO-GO -- zero overlap between phenotype and morphology caches."
        return res

    rows = []
    for cid in ids:
        rec = {"caseid": cid, "dose": pheno[cid]["dose"],
               "n_epochs": pheno[cid]["n_epochs"]}
        rec.update({k: morph[cid].get(k) for k in MORPH_FEATURES + [PRIMARY_FEATURE]})
        c = cov.get(cid, {})
        rec.update({k: c.get(k) for k in SIZE_FEATURES + ["surgery_duration_min"]})
        rows.append(rec)
    df = pd.DataFrame(rows)
    y = df["dose"].to_numpy(float)

    # binary high-requirement = top tertile
    thr = float(np.nanpercentile(y, 100.0 * 2.0 / 3.0))
    ybin = (y >= thr).astype(int)
    res["target_summary"] = {
        "dose_median": round(float(np.median(y)), 6),
        "dose_iqr": [round(float(np.percentile(y, 25)), 6),
                     round(float(np.percentile(y, 75)), 6)],
        "high_requirement_top_tertile_threshold": round(thr, 6),
        "n_high": int(ybin.sum()), "n_low": int((1 - ybin).sum()),
        "epochs_per_case_median": int(np.median(df["n_epochs"].to_numpy(float))),
    }

    feasible = len(ids) >= N_FEASIBILITY

    # --- 1+2. OOF morphology -> requirement ---------------------------------
    Xm = df[MORPH_FEATURES + [PRIMARY_FEATURE]].apply(
        lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    res["oof_morphology_regression"] = _oof_ridge(Xm, y)
    res["oof_high_requirement_auc"] = _oof_logistic_auc(Xm, ybin)

    # --- 3. PRIMARY feature univariate Spearman + bootstrap CI --------------
    pf = pd.to_numeric(df[PRIMARY_FEATURE], errors="coerce").to_numpy(float)
    r, ci, npf = _spearman_ci(pf, y)
    res["primary_feature_univariate"] = {
        "feature": PRIMARY_FEATURE,
        "spearman_vs_requirement": r, "bootstrap_ci_95": ci, "n_used": npf,
        "hypothesised_sign": "NEGATIVE (low diastolic/MAP = low tone = vasoplegia "
                             "= HIGH norepi requirement)",
        "in_hypothesised_direction": (bool(r < 0) if r is not None else None),
    }
    # also tau and AIx as secondary carriers, for context
    sec = {}
    for f in ("art_tau_decay_mean", "art_aug_index_mean"):
        rr, cci, nn = _spearman_ci(
            pd.to_numeric(df[f], errors="coerce").to_numpy(float), y)
        sec[f] = {"spearman": rr, "ci": cci, "n": nn}
    res["secondary_carriers_univariate"] = sec

    # --- 4. incremental over body size --------------------------------------
    Xs = df[SIZE_FEATURES].apply(
        lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    Xsm = df[SIZE_FEATURES + MORPH_FEATURES + [PRIMARY_FEATURE]].apply(
        lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    size_only = _oof_ridge(Xs, y)
    size_plus = _oof_ridge(Xsm, y)
    incr = None
    if size_only["r2"] is not None and size_plus["r2"] is not None:
        incr = round(size_plus["r2"] - size_only["r2"], 4)
    res["incremental_over_body_size"] = {
        "size_only_oof_r2": size_only["r2"],
        "size_plus_morphology_oof_r2": size_plus["r2"],
        "morphology_incremental_oof_r2": incr,
        "note": "nested OOF R2 gain of A-line morphology over weight/age/BMI/ASA. "
                "Positive gain = waveform carries requirement info beyond body size.",
    }

    # --- 5. negative control / placebo: morphology vs surgery duration ------
    dur = pd.to_numeric(df["surgery_duration_min"], errors="coerce").to_numpy(float)
    placebo = {}
    msk = np.isfinite(dur)
    if msk.sum() >= 6:
        # OOF morphology -> duration (should be weaker / near 0)
        pl = _oof_ridge(Xm[msk], dur[msk])
        placebo["oof_morphology_vs_surgery_duration_spearman"] = pl["spearman"]
        placebo["oof_morphology_vs_surgery_duration_r2"] = pl["r2"]
        # primary feature vs duration
        rr, cci, nn = _spearman_ci(pf[msk], dur[msk])
        placebo["primary_feature_vs_surgery_duration_spearman"] = rr
        placebo["primary_feature_vs_surgery_duration_ci"] = cci
        placebo["n_used"] = int(msk.sum())
    else:
        placebo["note"] = f"insufficient surgery-duration coverage (n={int(msk.sum())})"
    placebo["interpretation"] = ("calibration negative control: A-line morphology "
                                 "should NOT predict an unrelated label (surgery "
                                 "duration) as strongly as the requirement phenotype.")
    res["placebo_negative_control"] = placebo

    # --- VERDICT -------------------------------------------------------------
    oof_r = res["oof_morphology_regression"]["spearman"]
    auc = res["oof_high_requirement_auc"]["auc"]
    prim_dir = res["primary_feature_univariate"]["in_hypothesised_direction"]
    signal = bool((oof_r is not None and oof_r > 0.2) or (auc is not None and auc > 0.65))

    if not feasible:
        res["go"] = False
        res["verdict"] = (
            f"FEASIBILITY-ONLY (merged N = {len(ids)} < {N_FEASIBILITY}). The "
            "requirement phenotype (needs >= 2 stable norepi-only target-band epochs) "
            "and the A-line morphology caches overlap on too few cases for a "
            f"trustworthy out-of-fold estimate. Directional read (NOT a result): OOF "
            f"morphology->requirement Spearman {oof_r}, high-requirement OOF AUC {auc}, "
            f"primary feature {PRIMARY_FEATURE} univariate Spearman "
            f"{res['primary_feature_univariate']['spearman_vs_requirement']} "
            f"(CI {res['primary_feature_univariate']['bootstrap_ci_95']}, "
            f"{'hypothesised direction' if prim_dir else 'WRONG/null sign'}), "
            f"morphology incremental-over-body-size OOF R2 {incr}. "
            "Any Spearman/AUC on this N is dominated by sampling noise and a wide CI; "
            "GROW the phenotype cohort (more cases with >= 2 stable epochs that ALSO "
            "have an A-line morphology extraction) before claiming predictive value. "
            "The placebo correlation is reported for calibration, not inference.")
    elif signal and prim_dir:
        res["go"] = True
        res["verdict"] = (
            f"GO -- on N = {len(ids)} merged cases the pre-existing A-line morphology "
            f"predicts the norepinephrine dose-requirement out-of-fold (Spearman "
            f"{oof_r}, high-requirement AUC {auc}), the pre-specified Pivot-2 carrier "
            f"{PRIMARY_FEATURE} correlates in the hypothesised direction, and "
            f"morphology adds OOF R2 {incr} beyond body size while NOT predicting the "
            "surgery-duration placebo. Waveform-based pre-emptive vasoplegia flagging "
            "is supported; external/prospective replication required.")
    else:
        res["go"] = False
        res["verdict"] = (
            f"NO-GO at N = {len(ids)} -- A-line morphology does not predict the "
            f"requirement out-of-fold strongly enough (Spearman {oof_r}, AUC {auc}; "
            f"primary {PRIMARY_FEATURE} "
            f"{'in hypothesised direction' if prim_dir else 'wrong/null sign'}, "
            f"incremental-over-body-size OOF R2 {incr}). No predictive claim warranted.")
    return res


# ===========================================================================
# documentation
# ===========================================================================
def _doc(res):
    L = ["# Does A-line WAVEFORM morphology predict the vasopressor "
         "DOSE-REQUIREMENT (vasoplegia) phenotype?\n",
         "Merge-and-model test (no new waveform extraction). TARGET = the per-case "
         "norepinephrine dose-REQUIREMENT phenotype from pressor_requirement.py "
         "(median dose/kg over stable norepi-only epochs holding MAP in "
         f"[{TARGET_LO}, {TARGET_HI}] mmHg, >= {MIN_EPOCHS_PER_CASE} epochs; high "
         "requirement = vasoplegia). FEATURES = pre-existing A-line morphology "
         "(Pivot-2 tone family: diastolic/MAP form factor, tau decay, augmentation "
         "index, ...). PRE-SPECIFIED PRIMARY feature = `diastolic_over_map` "
         "(the Pivot-2 carrier). OOF (KFold) estimates ONLY; no in-sample R2.\n"]
    L += [f"- Phenotype cases (requirement target): **{res['phenotype']['n_cases_with_phenotype']}**.",
          f"- Cases with A-line morphology: **{res['morphology_source']['n_cases_with_morphology']}** "
          f"(merged from {', '.join(MORPH_FILES)}).",
          f"- **MERGED N (phenotype AND morphology) = {res.get('merged_n')}**.\n"]
    if res.get("merged_n", 0) == 0:
        L += ["## Verdict", res.get("verdict", ""), ""]
        open(OUT_DOC, "w").write("\n".join(L) + "\n")
        return
    ts = res.get("target_summary", {})
    L += [f"- Requirement (dose/kg) median {ts.get('dose_median')}, IQR {ts.get('dose_iqr')}; "
          f"high-requirement top-tertile threshold {ts.get('high_requirement_top_tertile_threshold')} "
          f"(n_high {ts.get('n_high')} / n_low {ts.get('n_low')}); median epochs/case "
          f"{ts.get('epochs_per_case_median')}.\n"]
    reg = res.get("oof_morphology_regression", {})
    auc = res.get("oof_high_requirement_auc", {})
    L += ["## 1-2. Out-of-fold morphology -> requirement",
          f"- Full morphology set ({reg.get('n_features')} features), 5-fold x5 "
          f"RidgeCV: **OOF Spearman {reg.get('spearman')}**, **OOF R2 {reg.get('r2')}** "
          f"(N={reg.get('n')}).",
          f"- High-requirement (top tertile) logistic **OOF AUC {auc.get('auc')}** "
          f"(n_pos {auc.get('n_pos')}/{auc.get('n')}).\n"]
    pu = res.get("primary_feature_univariate", {})
    L += ["## 3. Pre-specified PRIMARY feature (diastolic_over_map, the Pivot-2 carrier)",
          f"- Univariate **Spearman vs requirement = {pu.get('spearman_vs_requirement')}** "
          f"(95% bootstrap CI {pu.get('bootstrap_ci_95')}, n={pu.get('n_used')}).",
          f"- Hypothesised sign: {pu.get('hypothesised_sign')} -> observed is "
          f"**{'in the hypothesised direction' if pu.get('in_hypothesised_direction') else 'NOT in the hypothesised direction'}**.",
          f"- Secondary carriers: {res.get('secondary_carriers_univariate')}.\n"]
    inc = res.get("incremental_over_body_size", {})
    L += ["## 4. Incremental value over body size (weight/age/BMI/ASA)",
          f"- Size-only OOF R2 {inc.get('size_only_oof_r2')}; +morphology OOF R2 "
          f"{inc.get('size_plus_morphology_oof_r2')}; **morphology incremental OOF R2 "
          f"= {inc.get('morphology_incremental_oof_r2')}**.\n"]
    pl = res.get("placebo_negative_control", {})
    L += ["## 5. Negative control / placebo (surgery duration)",
          f"- OOF morphology -> surgery duration Spearman "
          f"{pl.get('oof_morphology_vs_surgery_duration_spearman')} "
          f"(R2 {pl.get('oof_morphology_vs_surgery_duration_r2')}); primary feature vs "
          f"duration Spearman {pl.get('primary_feature_vs_surgery_duration_spearman')} "
          f"(CI {pl.get('primary_feature_vs_surgery_duration_ci')}).",
          f"- {pl.get('interpretation')}\n"]
    L += ["## Verdict", res.get("verdict", ""), "",
          "## Caveats",
          "- **N is the binding limit.** The requirement phenotype needs >= 2 stable "
          "norepi-only target-band epochs, which is rare; the A-line morphology caches "
          "were extracted for the SVR/vasoplegia sub-studies, not this phenotype. Their "
          f"intersection (N={res.get('merged_n')}) is the hard ceiling here. Below "
          f"N={N_FEASIBILITY} this is a FEASIBILITY signal, not a result -- OOF "
          "estimates at this N have very wide CIs and can flip on one case.",
          "- **OOF only.** Every Spearman/R2/AUC headline above is out-of-fold "
          "(KFold), never in-sample, to avoid overfitting inflation at small N.",
          "- **Observational, single-centre (SNUH/VitalDB).** The requirement reflects "
          "management + physiology; morphology features are intraoperative summaries, "
          "not strictly PRE-induction baselines -- so 'pre-emptive' is aspirational "
          "until a true pre-pressor window is used. External replication required.",
          "- Links to: pressor_requirement.py (target), independent_svr_validation.py / "
          "PIVOT2_PREPUB_TESTS.md (the morphology->tone evidence the carrier rests on)."]
    open(OUT_DOC, "w").write("\n".join(L) + "\n")


def main():
    res = analyze()
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    print("\n[reqwf] MERGED N: " + str(res.get("merged_n")))
    print("[reqwf] VERDICT: " + res.get("verdict", "no data"))
    print("[reqwf] -> " + OUT_JSON)
    print("[reqwf] -> " + OUT_DOC)


if __name__ == "__main__":
    main()
