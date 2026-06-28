"""external_validation_inspire.py -- EXTERNAL validation of the REPLICABLE CORE of the
vasopressor-requirement finding in INSPIRE (independent ~131k-op cohort).

HONEST SCOPE. INSPIRE has cumulative `intraop_norepi`, outcomes (incl. a HARD endpoint
`death_inhosp` that VitalDB lacked), MAP-AUC, demographics, and multi-operation subjects --
but NO arterial waveforms and NO per-epoch timing. So it can externally validate the
*concept* (requirement is a stable patient trait + carries outcome information beyond MAP),
NOT the waveform / early-identification specifics (those need an external WAVEFORM cohort,
e.g. MIMIC-IV waveform / eICU -- not loaded here).

Two external tests:
  1. TRAIT REPLICATION ACROSS OPERATIONS. For subjects with norepinephrine used in >=2
     operations, does the requirement in one operation predict another? (within-subject
     correlation of duration-normalised norepi). A DIFFERENT design (across operations, not
     epochs) in a DIFFERENT cohort -> if it holds, the requirement-as-trait generalises.
     Confounding caveat: operations differ in surgery type/duration -> normalise by
     anaesthesia duration and report.
  2. INCREMENTAL OVER MAP for OUTCOMES. Does the norepi requirement predict composite organ
     injury / AKI / IN-HOSPITAL DEATH BEYOND map_auc_below_65 + demographics? Nested
     out-of-fold AUC (clinical+MAP vs +requirement). The control-theory corollary -- the
     dose is the informative hemodynamic signal -- tested externally on a hard endpoint.

stdlib only at import; numpy/sklearn lazy.
Run: python3 -m vitaldb_aki.analysis.external_validation_inspire
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
CLIN = ["age", "sex_male", "asa_class", "anesthesia_duration", "egfr_ckd_epi"]


def _load():
    import numpy as np, pandas as pd
    m = pd.read_csv(os.path.join(_CACHE, "inspire_matrix.csv"), low_memory=False)
    sid = "subject_id" if "subject_id" in m.columns else "subjectid"
    m[sid] = m[sid].astype(str)
    for c in ["intraop_norepi", "map_auc_below_65", "composite", "organ_renal",
              "death_inhosp", "anesthesia_duration", "surgery_duration"] + CLIN:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c], errors="coerce")
    m["norepi"] = m["intraop_norepi"].fillna(0)
    # duration-normalised requirement (approx rate): norepi per hour of anaesthesia
    dur_h = (m["anesthesia_duration"].where(m["anesthesia_duration"] > 0)) / 60.0
    m["norepi_rate"] = m["norepi"] / dur_h
    return m, sid


def _trait_across_ops(m, sid):
    """Within-subject reliability of the norepi requirement across operations."""
    import numpy as np, pandas as pd
    from scipy import stats
    use = m[m["norepi"] > 0].copy()
    vc = use[sid].value_counts()
    multi = use[use[sid].isin(vc[vc >= 2].index)].copy()
    pairs_raw, pairs_rate = [], []
    rng = np.random.default_rng(SEED)
    for s, g in multi.groupby(sid):
        g = g.dropna(subset=["norepi"])
        if len(g) < 2:
            continue
        # take two distinct operations (first two by index)
        a, b = g["norepi"].iloc[0], g["norepi"].iloc[1]
        pairs_raw.append((a, b))
        ra, rb = g["norepi_rate"].iloc[0], g["norepi_rate"].iloc[1]
        if np.isfinite(ra) and np.isfinite(rb):
            pairs_rate.append((ra, rb))
    def rel(pairs):
        if len(pairs) < 10:
            return {"n": len(pairs)}
        x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
        r = float(stats.spearmanr(x, y)[0])
        bs = []
        for _ in range(2000):
            idx = rng.integers(0, len(x), len(x))
            bs.append(stats.spearmanr(x[idx], y[idx])[0])
        return {"n": len(pairs), "spearman": round(r, 3),
                "ci": [round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)]}
    return {"raw_dose": rel(pairs_raw), "duration_normalised_rate": rel(pairs_rate),
            "interpretation": "positive within-subject correlation across operations = the vasopressor "
            "requirement is a reproducible patient trait in an INDEPENDENT cohort + design. Caveat: "
            "operations differ in surgery type/duration -> the duration-normalised rate is the cleaner."}


def _oof_auc(X, y, k=5):
    import numpy as np
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    if X.shape[0] < 100 or len(set(y)) < 2:
        return None
    oof = np.full(len(y), np.nan)
    for tr, te in StratifiedKFold(k, shuffle=True, random_state=SEED).split(X, y):
        p = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                      ("m", LogisticRegression(max_iter=2000))])
        p.fit(X[tr], y[tr]); oof[te] = p.predict_proba(X[te])[:, 1]
    mask = np.isfinite(oof)
    return round(float(roc_auc_score(y[mask], oof[mask])), 4)


def _incremental(m):
    """Does norepi requirement add beyond MAP-AUC + demographics for outcomes?"""
    import numpy as np, pandas as pd
    out = {}
    clin = [c for c in CLIN if c in m.columns]
    base_cols = clin + ["map_auc_below_65"]
    for oc in ("composite", "organ_renal", "death_inhosp"):
        if oc not in m.columns:
            continue
        d = m[base_cols + ["norepi_rate", oc]].copy()
        d[oc] = pd.to_numeric(d[oc], errors="coerce")
        d = d[np.isfinite(d[oc])]
        # require enough events
        if d[oc].sum() < 30 or len(d) < 500:
            out[oc] = {"note": f"too few events ({int(d[oc].sum())})"}
            continue
        y = d[oc].to_numpy(int)
        Xbase = d[base_cols].to_numpy(float)
        Xfull = d[base_cols + ["norepi_rate"]].to_numpy(float)
        a_base = _oof_auc(Xbase, y); a_full = _oof_auc(Xfull, y)
        # MAP-only vs norepi-only head-to-head
        a_map = _oof_auc(d[["map_auc_below_65"]].to_numpy(float), y)
        a_nor = _oof_auc(d[["norepi_rate"]].to_numpy(float), y)
        out[oc] = {"n": int(len(d)), "events": int(y.sum()),
                   "auc_clinical_plus_MAP": a_base, "auc_plus_requirement": a_full,
                   "delta_auc": round((a_full - a_base), 4) if (a_full and a_base) else None,
                   "auc_MAP_alone": a_map, "auc_requirement_alone": a_nor}
    out["interpretation"] = ("delta_auc > 0 => the vasopressor requirement adds predictive value "
        "BEYOND MAP-AUC + demographics in an independent cohort (external support for the control-"
        "theory corollary that the dose carries the hemodynamic insult). Compare requirement-alone "
        "vs MAP-alone AUC for which signal is better-identified.")
    return out


def main():
    import numpy as np
    m, sid = _load()
    res = {"seed": SEED, "n_ops": int(len(m)), "n_norepi_ops": int((m["norepi"] > 0).sum()),
           "trait_across_operations": _trait_across_ops(m, sid),
           "incremental_over_MAP": _incremental(m)}
    tr = res["trait_across_operations"].get("duration_normalised_rate", {})
    inc = res["incremental_over_MAP"]
    death = inc.get("death_inhosp", {})
    comp = inc.get("composite", {})
    trait_ok = bool(tr.get("ci") and tr["ci"][0] > 0)
    inc_ok = any(isinstance(inc.get(o), dict) and (inc[o].get("delta_auc") or 0) > 0.005
                 for o in ("composite", "organ_renal", "death_inhosp"))
    res["verdict"] = (
        f"EXTERNAL (INSPIRE, n_norepi={res['n_norepi_ops']}): "
        + (f"TRAIT REPLICATES across operations (duration-normalised within-subject Spearman "
           f"{tr.get('spearman')} {tr.get('ci')}, n={tr.get('n')}); " if trait_ok else
           f"trait across operations weak/null ({tr.get('spearman')} {tr.get('ci')}, n={tr.get('n')}); ")
        + ("requirement ADDS over MAP+demographics for outcomes (e.g. death dAUC "
           f"{death.get('delta_auc')}, composite dAUC {comp.get('delta_auc')}). " if inc_ok else
           f"requirement does NOT clearly add over MAP+demographics (death dAUC {death.get('delta_auc')}, "
           f"composite dAUC {comp.get('delta_auc')}). ")
        + "NOTE: validates the CONCEPT (trait + incremental); the waveform/early-ID specifics need an "
        "external WAVEFORM cohort (MIMIC-IV/eICU), not testable in INSPIRE.")
    json.dump(res, open(os.path.join(_CACHE, "external_validation_inspire.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[extval] VERDICT:", res["verdict"], flush=True)
    print("[extval] trait:", json.dumps(res["trait_across_operations"].get("duration_normalised_rate")), flush=True)
    print("[extval] incremental:", json.dumps({k: v for k, v in res["incremental_over_MAP"].items() if isinstance(v, dict)}), flush=True)
    print("[extval] -> docs/EXTERNAL_VALIDATION_INSPIRE.md", flush=True)


def _doc(res):
    tr = res["trait_across_operations"]; inc = res["incremental_over_MAP"]
    L = ["# External validation in INSPIRE (independent ~131k-op cohort)\n",
         "Validates the REPLICABLE CORE of the vasopressor-requirement finding in an independent "
         "cohort. HONEST SCOPE: INSPIRE has no arterial waveforms / no per-epoch timing, so it "
         "validates the CONCEPT (requirement is a trait + carries outcome info beyond MAP), NOT the "
         "waveform / early-identification specifics (those need an external WAVEFORM cohort).\n",
         f"- INSPIRE operations: {res['n_ops']}; with norepinephrine used: {res['n_norepi_ops']}.\n",
         "## 1. Trait replication across operations (within-subject)",
         f"- Duration-normalised requirement: within-subject Spearman "
         f"**{tr.get('duration_normalised_rate',{}).get('spearman')}** "
         f"(95% CI {tr.get('duration_normalised_rate',{}).get('ci')}, "
         f"n={tr.get('duration_normalised_rate',{}).get('n')} subjects with norepi in >=2 ops).",
         f"- Raw cumulative dose: {tr.get('raw_dose',{}).get('spearman')} "
         f"(CI {tr.get('raw_dose',{}).get('ci')}).",
         f"  _{tr.get('interpretation','')}_\n",
         "## 2. Incremental over MAP-AUC for outcomes (out-of-fold AUC)"]
    for oc in ("composite", "organ_renal", "death_inhosp"):
        v = inc.get(oc)
        if isinstance(v, dict) and "auc_clinical_plus_MAP" in v:
            L.append(f"- **{oc}** (events {v.get('events')}/{v.get('n')}): clinical+MAP AUC "
                     f"{v.get('auc_clinical_plus_MAP')} -> +requirement {v.get('auc_plus_requirement')} "
                     f"(**ΔAUC {v.get('delta_auc')}**); MAP-alone {v.get('auc_MAP_alone')} vs "
                     f"requirement-alone {v.get('auc_requirement_alone')}.")
    L += [f"  _{inc.get('interpretation','')}_\n",
          "## Verdict", res["verdict"], "",
          "## Caveats",
          "- Trait-across-operations is confounded by surgery type/duration differing between a "
          "subject's operations; the duration-normalised rate is the cleaner estimate but residual "
          "confounding remains. INSPIRE norepi is a cumulative total (no rate/timing).",
          "- Incremental-AUC is association/prediction, not causal; norepi->AKI was shown confounded "
          "by indication (negative-control calibration) -- this is about PREDICTIVE information, the "
          "control-theory corollary, not a treatment effect.",
          "- Full external validation of the WAVEFORM tone estimator + EARLY-identification finding "
          "requires an external arterial-waveform cohort (MIMIC-IV waveform / eICU); stated as the "
          "remaining external step, not done here."]
    open(os.path.join(_DOCS, "EXTERNAL_VALIDATION_INSPIRE.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
