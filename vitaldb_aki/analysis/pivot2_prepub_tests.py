"""pivot2_prepub_tests.py -- pre-publication robustness battery for the A-line
vascular-tone / SVR-estimation finding (Pivot 2). Runs the tests a reviewer of a
MEASUREMENT paper will demand, on the already-extracted cohorts:
  - cache/vasoplegia_validation.csv  (EV1000 SVRI, larger N)
  - cache/independent_svr_validation.csv  (Vigilance/CardioQ SVR, circularity-clean)

Tests: (1) AGREEMENT -- Bland-Altman bias / 95% limits of agreement / Critchley
percentage error of waveform-estimated SVR vs measured (correlation != agreement);
(2) PRE-SPECIFIED PRIMARY feature (diastolic/MAP form factor) Spearman + bootstrap CI
on BOTH cohorts; (3) CASE-MIX robustness -- does it hold excluding cardiac/CPB cases?
(4) reference-standard note. stdlib only at import; heavy deps lazy.

Run: python3 -m vitaldb_aki.analysis.pivot2_prepub_tests   (from repo root)
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260626
PRESSURE = ["art_map_mean", "art_sbp_mean", "art_dbp_mean", "art_pulse_pressure_mean", "art_pulse_pressure_sd"]
MORPH = ["art_tau_decay_mean", "art_aug_index_mean", "art_hr_mean", "art_hr_sd",
         "pat_mean_ms", "pat_sd_ms", "art_ppg_amp_corr", "central_peripheral_decoupling",
         "brs_mean", "cardiopulm_coherence", "resp_sbp_coupling"]
PRIMARY = "diastolic_over_map"   # pre-specified primary (the R4/dynamic carrier)


def _prep(path, svri_col):
    import numpy as np, pandas as pd
    if not os.path.exists(path):
        return None
    v = pd.read_csv(path)
    if "has_direct_svr" in v.columns and "vasoplegia_validation" in path:
        v = v[v["has_direct_svr"].astype(str) == "1"]
    y = pd.to_numeric(v.get(svri_col), errors="coerce")
    keep = y.between(300, 5000)
    v, y = v[keep].reset_index(drop=True), y[keep].reset_index(drop=True)
    if "art_dbp_mean" in v and "art_map_mean" in v:
        v[PRIMARY] = pd.to_numeric(v["art_dbp_mean"], errors="coerce") / pd.to_numeric(v["art_map_mean"], errors="coerce")
    return v, y.to_numpy(float)


def _oof_pred(v, cols, y):
    import numpy as np, pandas as pd
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    cols = [c for c in cols if c in v.columns]
    X = v[cols].apply(lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    oof = np.full(len(y), np.nan)
    for tr, te in KFold(5, shuffle=True, random_state=SEED).split(X):
        p = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                      ("m", RidgeCV(alphas=(.1, 1, 10, 100)))])
        p.fit(X[tr], y[tr]); oof[te] = p.predict(X[te])
    return oof


def _bland_altman(pred, meas):
    import numpy as np
    m = np.isfinite(pred) & np.isfinite(meas)
    pred, meas = pred[m], meas[m]
    diff = pred - meas
    bias = float(np.mean(diff)); sd = float(np.std(diff, ddof=1))
    mean_ref = float(np.mean(meas))
    # Critchley percentage error = 1.96*SD(diff) / mean(reference)
    pe = float(1.96 * sd / mean_ref) if mean_ref else None
    return {"n": int(m.sum()), "bias": round(bias, 1), "sd_diff": round(sd, 1),
            "loa_95": [round(bias - 1.96 * sd, 1), round(bias + 1.96 * sd, 1)],
            "mean_measured_svr": round(mean_ref, 1),
            "percentage_error": round(pe, 3) if pe else None,
            "critchley_pass_30pct": bool(pe is not None and pe <= 0.30)}


def _spearman_ci(x, y, nboot=2000):
    import numpy as np
    from scipy import stats
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    r = float(stats.spearmanr(x, y)[0])
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(x), len(x))
        bs.append(stats.spearmanr(x[idx], y[idx])[0])
    return {"r": round(r, 4), "ci": [round(float(np.percentile(bs, 2.5)), 4),
            round(float(np.percentile(bs, 97.5)), 4)], "n": int(len(x))}


def _casemix(v, y):
    """Merge surgery type from cases.csv; report primary-feature Spearman excluding
    cardiac/CPB-type cases (extreme SVR + pump artifacts)."""
    import numpy as np, pandas as pd
    from scipy import stats
    cases_path = os.path.join(_CACHE, "cases.csv")
    if not os.path.exists(cases_path) or PRIMARY not in v.columns:
        return None
    cases = pd.read_csv(cases_path)
    idc = "caseid" if "caseid" in cases.columns else None
    optcol = next((c for c in ("optype", "opname", "department", "approach") if c in cases.columns), None)
    if idc is None or optcol is None:
        return None
    v = v.copy(); v["caseid"] = v["caseid"].astype(str); cases["caseid"] = cases[idc].astype(str)
    v = v.merge(cases[["caseid", optcol]], on="caseid", how="left")
    opt = v[optcol].astype(str).str.lower()
    is_cardiac = opt.str.contains("cardiac|aort|cabg|valve|cpb|thoracic", regex=True, na=False)
    x = pd.to_numeric(v[PRIMARY], errors="coerce").to_numpy(float)
    out = {"n_cardiac": int(is_cardiac.sum()), "n_noncardiac": int((~is_cardiac).sum())}
    for lab, mask in (("all", np.ones(len(v), bool)), ("non_cardiac", (~is_cardiac).to_numpy())):
        m = mask & np.isfinite(x) & np.isfinite(y)
        if m.sum() > 15:
            out[lab + "_primary_spearman"] = round(float(stats.spearmanr(x[m], y[m])[0]), 4)
            out[lab + "_n"] = int(m.sum())
    return out


def main():
    import numpy as np
    import pandas as pd
    res = {"seed": SEED, "primary_feature": PRIMARY, "cohorts": {}}
    for name, path, col in (("EV1000_pulsecontour", os.path.join(_CACHE, "vasoplegia_validation.csv"), "svri_measured"),
                            ("INDEPENDENT_CO", os.path.join(_CACHE, "independent_svr_validation.csv"), None)):
        prepped = None
        if name == "INDEPENDENT_CO":
            # independent file: find the SVR column
            import pandas as pd
            if os.path.exists(path):
                cols = pd.read_csv(path, nrows=1).columns
                col = next((c for c in ("svri_measured", "svr_indep", "svri_indep", "svr_measured") if c in cols), None)
        if col:
            prepped = _prep(path, col)
        if not prepped:
            res["cohorts"][name] = {"available": False}
            continue
        v, y = prepped
        block = {"available": True, "n": int(len(y)), "svr_source_col": col}
        # AGREEMENT (full model estimator)
        pred = _oof_pred(v, PRESSURE + MORPH, y)
        block["agreement_bland_altman"] = _bland_altman(pred, y)
        # PRE-SPECIFIED PRIMARY
        if PRIMARY in v.columns:
            x = np.asarray(pd.to_numeric(v[PRIMARY], errors="coerce"), float)
            block["primary_feature_spearman"] = _spearman_ci(x, y)
        # CASE-MIX
        cm = _casemix(v, y)
        if cm:
            block["case_mix"] = cm
        res["cohorts"][name] = block
        print(f"[prepub] {name}: N={len(y)} | "
              f"agreement %err={block['agreement_bland_altman'].get('percentage_error')} | "
              f"primary r={block.get('primary_feature_spearman',{}).get('r')}", flush=True)

    json.dump(res, open(os.path.join(_CACHE, "pivot2_prepub_results.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[prepub] done -> docs/PIVOT2_PREPUB_TESTS.md", flush=True)


def _doc(res):
    L = ["# Pivot 2 pre-publication robustness battery\n",
         "Tests a reviewer of a MEASUREMENT paper demands, on the extracted cohorts. The "
         "EV1000 cohort is larger but pulse-contour (waveform-derived); the INDEPENDENT_CO "
         "cohort (Vigilance thermodilution / CardioQ Doppler) is the circularity-clean one.\n"]
    for name, b in res["cohorts"].items():
        L.append(f"## {name}")
        if not b.get("available"):
            L.append("_cohort not available._\n"); continue
        ba = b.get("agreement_bland_altman", {})
        L.append(f"- N = {b['n']} (SVR source col `{b.get('svr_source_col')}`).")
        L.append(f"- **Agreement (Bland-Altman, waveform-estimated vs measured SVR):** bias "
                 f"{ba.get('bias')}, 95% LoA {ba.get('loa_95')}, **percentage error "
                 f"{ba.get('percentage_error')}** (Critchley <=0.30 pass = "
                 f"{ba.get('critchley_pass_30pct')}; mean measured SVR {ba.get('mean_measured_svr')}).")
        pf = b.get("primary_feature_spearman", {})
        L.append(f"- **Pre-specified primary (diastolic/MAP) Spearman vs measured SVR:** "
                 f"{pf.get('r')} (95% CI {pf.get('ci')}, n={pf.get('n')}).")
        cm = b.get("case_mix")
        if cm:
            L.append(f"- **Case-mix:** primary Spearman all={cm.get('all_primary_spearman')} "
                     f"(n={cm.get('all_n')}) vs NON-cardiac={cm.get('non_cardiac_primary_spearman')} "
                     f"(n={cm.get('non_cardiac_n')}); n_cardiac={cm.get('n_cardiac')}.")
        L.append("")
    L += ["## Interpretation",
          "- **Correlation vs agreement:** a high Spearman with a LARGE percentage error means "
          "the waveform RANKS vascular tone well but is not a calibrated point-estimate of SVR. "
          "For a 'trend monitor / vasoplegia detector' that is acceptable (the clinical use is "
          "detecting CHANGE/low-tone, not replacing a number); for 'replaces the SVR monitor' it "
          "is not. Scope the claim to what the percentage error supports.",
          "- **Pre-specified primary** = diastolic/MAP form factor (the carrier identified by the "
          "red-team R4 + dynamic decomposition) -- declared primary to avoid multiplicity fishing; "
          "other features are secondary/exploratory.",
          "- **External validity:** single-centre (SNUH/VitalDB); no public external arterial-"
          "waveform + CO cohort -> external replication is stated future work, not done here.",
          "- Still PENDING separately: the vasopressor-administration confound + lead/lag + "
          "window-length sensitivity (dynamic within-case claim) -- see docs/PIVOT2_DYNAMIC_CONFOUNDS.md."]
    open(os.path.join(_DOCS, "PIVOT2_PREPUB_TESTS.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
