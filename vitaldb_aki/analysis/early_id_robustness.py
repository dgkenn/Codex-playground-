"""early_id_robustness.py -- hostile-review battery for the LEAD finding: early
identification of the vasoplegia-prone (high vasopressor-requirement) patient.

The actionable claim (docs/ACTIONABILITY_TESTS.md): early-epoch norepi requirement
predicts the LATE requirement (Spearman +0.54), so the vasoplegia-prone patient is
flaggable before the pressor escalation. A hostile reviewer will demand four things; this
module tests all on existing caches (NO new extraction):

  1. INCREMENTAL OVER CLINICAL -- "you just rediscovered that sick/old/high-ASA patients
     need pressors." Does the EARLY A-line signal (early dose + tone morphology) predict
     the LATE requirement BEYOND a clinical baseline (age, ASA, weight, baseline MAP)?
     Nested out-of-fold R2/Spearman: clinical-only vs clinical + A-line.
  2. LEAD-TIME IN MINUTES -- how much real warning? Time from the first stable epoch to
     the epoch where the patient crosses a HIGH requirement, and the early-signal window.
  3. OPERATING POINT (ROC) -- predict eventual high-requirement (top tertile) from the
     first-half dose; AUC + a usable sensitivity/specificity threshold.
  4. DEFINITION ROBUSTNESS -- does the phenotype's reliability + spread survive changing
     the MAP target band and the min-epochs rule (anti-cherry-pick)?

stdlib only at import; numpy/pandas/sklearn/scipy lazy.
Run: python3 -m vitaldb_aki.analysis.early_id_robustness
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
EPOCHS = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
FEATS = os.path.join(_CACHE, "combined_biosignal_features.csv")


def _epoch_table():
    import numpy as np, pandas as pd
    df = pd.read_csv(EPOCHS, low_memory=False)
    for c in ("dose_per_kg", "map_mean", "norepi_only", "t_start"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    return df[(df["drug"] == "NEPI") & (df["norepi_only"] == 1) & df["dose_per_kg"].notna()].copy()


def _per_case(q, band=(55, 80), min_ep=2):
    """Per-case early/late/median requirement + timing, for cases with >= min_ep*2 epochs."""
    import numpy as np
    rows = {}
    for cid, g in q.groupby("caseid"):
        g = g.sort_values("t_start")
        gb = g[g["map_mean"].between(*band)]
        if len(g) < max(4, min_ep * 2):
            continue
        h = len(g) // 2
        rows[cid] = {
            "early": float(np.median(g["dose_per_kg"].iloc[:h])),
            "late": float(np.median(g["dose_per_kg"].iloc[h:])),
            "first": float(g["dose_per_kg"].iloc[0]),
            "median_band": float(np.median(gb["dose_per_kg"])) if len(gb) >= min_ep else float(np.median(g["dose_per_kg"])),
            "t_first": float(g["t_start"].iloc[0]), "t_mid": float(g["t_start"].iloc[h]),
            "t_last": float(g["t_start"].iloc[-1]),
            "doses": g["dose_per_kg"].to_numpy(float), "times": g["t_start"].to_numpy(float)}
    return rows


def _oof_spear(X, y, k=5):
    import numpy as np
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    if len(y) < 15 or X.shape[1] == 0:
        return None
    oof = np.full(len(y), np.nan)
    kk = min(k, len(y) // 3)
    for tr, te in KFold(kk, shuffle=True, random_state=SEED).split(X):
        p = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                      ("m", RidgeCV(alphas=(.1, 1, 10, 100)))])
        p.fit(X[tr], y[tr]); oof[te] = p.predict(X[te])
    m = np.isfinite(oof) & np.isfinite(y)
    return round(float(stats.spearmanr(oof[m], y[m])[0]), 3) if m.sum() >= 10 else None


def test_incremental_over_clinical(q):
    """Does early A-line (early dose + tone) predict LATE requirement beyond clinical?"""
    import numpy as np, pandas as pd
    pc = _per_case(q)
    if len(pc) < 15:
        return {"n": len(pc), "note": "too few"}
    cs = pd.read_csv(os.path.join(_CACHE, "cases.csv"), low_memory=False)
    idc = [c for c in cs.columns if c.lstrip("﻿").lower() == "caseid"][0]
    cs = cs.rename(columns={idc: "caseid"}); cs["caseid"] = cs["caseid"].astype(str)
    for c in ("age", "asa", "weight"):
        cs[c] = pd.to_numeric(cs.get(c), errors="coerce")
    feats = pd.read_csv(FEATS, low_memory=False) if os.path.exists(FEATS) else pd.DataFrame()
    if not feats.empty:
        feats["caseid"] = feats["caseid"].astype(str)
        for c in ("map_dia_form_factor", "art_map_mean"):
            if c in feats.columns:
                feats[c] = pd.to_numeric(feats[c], errors="coerce")
    rows = []
    for cid, d in pc.items():
        r = {"caseid": cid, "late": d["late"], "early": d["early"]}
        c = cs[cs["caseid"] == cid]
        r["age"] = float(c["age"].iloc[0]) if len(c) and np.isfinite(c["age"].iloc[0]) else np.nan
        r["asa"] = float(c["asa"].iloc[0]) if len(c) and np.isfinite(c["asa"].iloc[0]) else np.nan
        r["weight"] = float(c["weight"].iloc[0]) if len(c) and np.isfinite(c["weight"].iloc[0]) else np.nan
        if not feats.empty:
            ff = feats[feats["caseid"] == cid]
            r["tone"] = float(ff["map_dia_form_factor"].iloc[0]) if len(ff) and "map_dia_form_factor" in ff and np.isfinite(ff["map_dia_form_factor"].iloc[0]) else np.nan
            r["base_map"] = float(ff["art_map_mean"].iloc[0]) if len(ff) and "art_map_mean" in ff and np.isfinite(ff["art_map_mean"].iloc[0]) else np.nan
        rows.append(r)
    m = pd.DataFrame(rows)
    y = m["late"].to_numpy(float)
    clin = ["age", "asa", "weight", "base_map"]
    clin = [c for c in clin if c in m.columns]
    Xc = m[clin].to_numpy(float)
    Xce = m[clin + ["early"]].to_numpy(float)
    Xcet = m[clin + ["early", "tone"]].to_numpy(float) if "tone" in m.columns else Xce
    return {"n": int(len(m)),
            "clinical_only_oof_spearman": _oof_spear(Xc, y),
            "clinical_plus_early_dose_oof_spearman": _oof_spear(Xce, y),
            "clinical_plus_early_and_tone_oof_spearman": _oof_spear(Xcet, y),
            "interpretation": "if clinical+A-line > clinical-only, the waveform/early-requirement "
            "ADDS information beyond age/ASA/weight/baseline-MAP -> worth measuring."}


def test_lead_time(q):
    """Real-minute warning: time from first stable epoch to crossing HIGH requirement, and
    the early-signal window (first epoch -> mid epoch)."""
    import numpy as np
    pc = _per_case(q)
    if len(pc) < 8:
        return {"n": len(pc)}
    meds = np.array([d["median_band"] for d in pc.values()])
    thr = np.percentile(meds, 66)   # cohort high-requirement threshold
    cross_min, early_window_min, runway_min = [], [], []
    n_high = 0
    for cid, d in pc.items():
        early_window_min.append((d["t_mid"] - d["t_first"]) / 60.0)
        runway_min.append((d["t_last"] - d["t_first"]) / 60.0)
        if d["median_band"] >= thr:   # eventual high-req patient
            n_high += 1
            doses, times = d["doses"], d["times"]
            hit = np.where(doses >= thr)[0]
            if len(hit):
                cross_min.append((times[hit[0]] - d["t_first"]) / 60.0)
    return {"n_cases": len(pc), "high_req_threshold_dose_per_kg": round(float(thr), 4),
            "early_signal_window_min_median": round(float(np.median(early_window_min)), 1),
            "case_runway_min_median": round(float(np.median(runway_min)), 1),
            "n_high_req": n_high,
            "time_to_cross_high_min_median": round(float(np.median(cross_min)), 1) if cross_min else None,
            "time_to_cross_high_min_iqr": [round(float(np.percentile(cross_min, 25)), 1),
                                           round(float(np.percentile(cross_min, 75)), 1)] if cross_min else None,
            "interpretation": "time_to_cross_high = minutes from first stable epoch until the patient "
            "actually reaches high requirement -- the window in which an early flag would let you act."}


def test_operating_point(q):
    """ROC: first-half dose predicts eventual high-requirement (top tertile)."""
    import numpy as np
    from sklearn.metrics import roc_auc_score
    pc = _per_case(q)
    if len(pc) < 20:
        return {"n": len(pc)}
    early = np.array([d["early"] for d in pc.values()])
    late = np.array([d["late"] for d in pc.values()])   # DISJOINT from early (no overlap)
    hi = (late >= np.percentile(late, 66)).astype(int)  # eventual high req = top tertile of LATE half
    if len(set(hi)) < 2:
        return {"n": len(pc), "note": "no variation"}
    auc = float(roc_auc_score(hi, early))
    # operating point: threshold = cohort median early dose
    thr = float(np.median(early))
    pred = (early >= thr).astype(int)
    tp = int(((pred == 1) & (hi == 1)).sum()); fn = int(((pred == 0) & (hi == 1)).sum())
    tn = int(((pred == 0) & (hi == 0)).sum()); fp = int(((pred == 1) & (hi == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    return {"n": len(pc), "auc_early_dose_predicts_high_req": round(auc, 3),
            "operating_point_threshold": round(thr, 4),
            "sensitivity": round(sens, 2) if sens is not None else None,
            "specificity": round(spec, 2) if spec is not None else None}


def test_definition_robustness(q):
    """Phenotype reliability (split-half) + spread across MAP bands & min-epochs."""
    import numpy as np
    from scipy import stats
    out = {}
    for band in ((50, 75), (55, 80), (60, 85)):
        for min_ep in (2, 3):
            pc = {}
            for cid, g in q.groupby("caseid"):
                g = g.sort_values("t_start")
                gb = g[g["map_mean"].between(*band)]
                if len(gb) >= max(min_ep, 4):
                    pc[cid] = gb["dose_per_kg"].to_numpy(float)
            if len(pc) < 8:
                out[f"band{band}_minep{min_ep}"] = {"n": len(pc)}
                continue
            meds = np.array([np.median(v) for v in pc.values()])
            mpos = meds[meds > 0]
            odd = [np.median(v[0::2]) for v in pc.values() if len(v) >= 4]
            even = [np.median(v[1::2]) for v in pc.values() if len(v) >= 4]
            rel = float(stats.spearmanr(odd, even)[0]) if len(odd) >= 5 else None
            out[f"band{band}_minep{min_ep}"] = {
                "n": len(pc), "split_half_reliability": round(rel, 3) if rel is not None else None,
                "fold_range_p90_p10": round(float(np.percentile(mpos, 90) / np.percentile(mpos, 10)), 1)
                if len(mpos) and np.percentile(mpos, 10) > 0 else None}
    out["interpretation"] = "reliability + spread should hold across band/min-epoch choices -> the "
    "phenotype is not an artifact of one definition."
    return out


def main():
    q = _epoch_table()
    res = {"seed": SEED,
           "incremental_over_clinical": test_incremental_over_clinical(q),
           "lead_time_minutes": test_lead_time(q),
           "operating_point": test_operating_point(q),
           "definition_robustness": test_definition_robustness(q)}
    inc = res["incremental_over_clinical"]
    c0 = inc.get("clinical_only_oof_spearman"); c1 = inc.get("clinical_plus_early_dose_oof_spearman")
    res["verdict"] = (
        f"Incremental over clinical: clinical-only OOF {c0} vs clinical+early-A-line {c1} "
        + ("(A-line ADDS predictive value beyond clinical baseline)."
           if (c0 is not None and c1 is not None and c1 > c0 + 0.05) else
           "(A-line does NOT clearly add beyond clinical at this N).")
        + f" Lead-time to high requirement: {res['lead_time_minutes'].get('time_to_cross_high_min_median')} min "
        f"(early-signal window {res['lead_time_minutes'].get('early_signal_window_min_median')} min). "
        f"Operating point AUC {res['operating_point'].get('auc_early_dose_predicts_high_req')} "
        f"(sens {res['operating_point'].get('sensitivity')}, spec {res['operating_point'].get('specificity')}).")
    json.dump(res, open(os.path.join(_CACHE, "early_id_robustness.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[earlyid] VERDICT:", res["verdict"], flush=True)
    print("[earlyid] -> docs/EARLY_ID_ROBUSTNESS.md", flush=True)


def _doc(res):
    inc, lt, op, dr = (res["incremental_over_clinical"], res["lead_time_minutes"],
                       res["operating_point"], res["definition_robustness"])
    L = ["# Early-identification robustness battery (hostile review of the lead finding)\n",
         "Defends 'the A-line identifies the vasoplegia-prone patient early' against the four "
         "questions a hostile reviewer asks.\n",
         "## 1. Incremental over clinical baseline (the key test)",
         f"- N = {inc.get('n')}. OOF Spearman predicting LATE requirement:",
         f"  - clinical only (age/ASA/weight/baseline-MAP): **{inc.get('clinical_only_oof_spearman')}**",
         f"  - clinical + early dose: **{inc.get('clinical_plus_early_dose_oof_spearman')}**",
         f"  - clinical + early dose + tone: **{inc.get('clinical_plus_early_and_tone_oof_spearman')}**",
         f"  _{inc.get('interpretation','')}_\n",
         "## 2. Lead-time (real minutes)",
         f"- High-requirement threshold: {lt.get('high_req_threshold_dose_per_kg')} (per-kg).",
         f"- **Time from first stable epoch to crossing high requirement: "
         f"{lt.get('time_to_cross_high_min_median')} min** (IQR {lt.get('time_to_cross_high_min_iqr')}, "
         f"n_high={lt.get('n_high_req')}).",
         f"- Early-signal window {lt.get('early_signal_window_min_median')} min; case runway "
         f"{lt.get('case_runway_min_median')} min.\n",
         "## 3. Operating point (ROC)",
         f"- **AUC (first-half dose -> eventual high requirement): {op.get('auc_early_dose_predicts_high_req')}** "
         f"(n={op.get('n')}); at threshold {op.get('operating_point_threshold')}: sensitivity "
         f"{op.get('sensitivity')}, specificity {op.get('specificity')}.\n",
         "## 4. Definition robustness (anti-cherry-pick)"]
    for k, v in dr.items():
        if isinstance(v, dict):
            L.append(f"- {k}: reliability {v.get('split_half_reliability')}, fold-range "
                     f"{v.get('fold_range_p90_p10')} (n={v.get('n')}).")
    L += ["", "## Verdict", res["verdict"], "",
          "## Caveats",
          "- N ~ 40-52 (the requirement phenotype is small); OOF only. Lead-time is intra-operative "
          "(within-case epoch timing), single-centre. The incremental-over-clinical test is the one "
          "that matters most -- if it is null, the A-line is redundant with bedside clinical data.",
          "- All observational; identifies WHO needs more pressor early, not that acting helps (trial)."]
    open(os.path.join(_DOCS, "EARLY_ID_ROBUSTNESS.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
