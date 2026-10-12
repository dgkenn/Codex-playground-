"""svri_morphology_feasibility.py -- is a waveform->SVRI predictor a good Phase-2
generative-counterfactual candidate?

Phase 2 (Obermeyer-style) is worth running ONLY if a model predicting measured SVRI
from the arterial waveform carries signal that is BOTH:
  (A) NON-CIRCULAR  -- adds predictive value for SVRI OVER mean pressure (SVRI is
      mechanically 80*(MAP-CVP)/CO, so a predictor that just re-reads MAP is cheating;
      the residual-beyond-pressure signal is the morphology Phase 2 would interpret); and
  (B) RICHER THAN THE HAND-BUILT INDEX -- the full waveform-morphology feature set beats
      the single hand-built vasoplegia index (tau/diastolic-MAP/form-factor/AIx, r~0.34).
      If the scalar index already captures everything, a generative model has nothing
      new to discover and Phase 2 is pointless.

This is the CPU-feasible GO/NO-GO that confirms candidacy BEFORE committing a GPU to
train the DL predictor + generative model. Data: cache/vasoplegia_validation.csv (the
co-extraction of waveform morphology + MEASURED SVRI on the direct-EV1000-SVR cohort).

Run: python3 -m vitaldb_aki.analysis.svri_morphology_feasibility   (from repo root)
Outputs: cache/svri_morphology_feasibility_results.json, docs/SVRI_MORPHOLOGY_FEASIBILITY.md
stdlib only at import; heavy deps lazy.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_CSV = os.path.join(_CACHE, "vasoplegia_validation.csv")

RANDOM_SEED = 20260626
SVRI_MIN, SVRI_MAX = 300.0, 5000.0   # physiologic gate (drops CO-derived garbage)

# Mean-pressure scalars: mechanically related to SVRI -> the CIRCULARITY floor to beat.
PRESSURE = ["art_map_mean", "art_sbp_mean", "art_dbp_mean", "art_pulse_pressure_mean"]
# The hand-built scalar vasoplegia index components (what the r~0.34 read used).
INDEX = ["art_tau_decay_mean", "art_dbp_mean", "art_map_mean", "art_aug_index_mean"]
# Full waveform MORPHOLOGY (shape/timing/coupling) -- NOT reducible to mean pressure.
MORPH = [
    "art_tau_decay_mean", "art_aug_index_mean", "art_dpdt_max_mean", "art_dpdt_max_min",
    "art_systolic_auc_mean", "art_ppv_mean", "art_pulse_pressure_sd", "art_hr_mean",
    "art_hr_sd", "pat_mean_ms", "pat_sd_ms", "pat_slope", "art_ppg_amp_corr",
    "central_peripheral_decoupling", "brs_mean", "cardiopulm_coherence",
    "resp_sbp_coupling", "art_narrow_pp_burden_min", "art_low_dpdt_burden_min",
    "art_low_dbp_burden_min", "art_perfusion_failure_burden_min",
]
# NEVER predictors (they ARE the SVRI ingredients -> circular by construction):
#   fluid_svr_*, fluid_co_*, fluid_ci_*, svri_*  -- excluded explicitly below.


def _load():
    import numpy as np
    import pandas as pd
    df = pd.read_csv(_CSV)
    if "has_direct_svr" in df.columns:
        df = df[df["has_direct_svr"].astype(str) == "1"]
    y = pd.to_numeric(df.get("svri_measured"), errors="coerce")
    ok = y.between(SVRI_MIN, SVRI_MAX)
    df, y = df[ok].reset_index(drop=True), y[ok].reset_index(drop=True)
    return df, y.to_numpy(dtype=float)


def _oof_spearman_r2(df, cols, y, seed=RANDOM_SEED, n_splits=5, n_repeats=5):
    """Repeated-KFold out-of-fold Ridge predictions of SVRI from `cols`; return
    cross-validated Spearman r and R^2 (averaged over repeats). Regularised + imputed
    + standardised -> robust at small N (~120)."""
    import numpy as np
    from sklearn.model_selection import RepeatedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats

    cols = [c for c in cols if c in df.columns]
    X = df[cols].apply(lambda s: __import__("pandas").to_numeric(s, errors="coerce")).to_numpy(float)
    if X.shape[1] == 0:
        return {"r": None, "r2": None, "n": int(len(y)), "n_features": 0, "cols": []}
    rs, r2s = [], []
    rkf = RepeatedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    for rep in range(n_repeats):
        oof = np.full(len(y), np.nan)
        # one full KFold pass per repeat
        from sklearn.model_selection import KFold
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed + rep)
        for tr, te in kf.split(X):
            pipe = Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("sc", StandardScaler()),
                ("m", RidgeCV(alphas=(0.1, 1.0, 10.0, 100.0))),
            ])
            pipe.fit(X[tr], y[tr])
            oof[te] = pipe.predict(X[te])
        m = ~np.isnan(oof)
        if m.sum() > 5 and np.std(oof[m]) > 1e-9:
            rs.append(float(stats.spearmanr(oof[m], y[m])[0]))
            ss_res = float(np.sum((y[m] - oof[m]) ** 2))
            ss_tot = float(np.sum((y[m] - np.mean(y[m])) ** 2))
            r2s.append(1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"))
    return {
        "r": round(float(np.mean(rs)), 4) if rs else None,
        "r_sd": round(float(np.std(rs)), 4) if rs else None,
        "r2": round(float(np.nanmean(r2s)), 4) if r2s else None,
        "n": int(len(y)), "n_features": len(cols), "cols": cols,
    }


def main():
    import numpy as np
    df, y = _load()
    n = len(y)
    res = {"seed": RANDOM_SEED, "n_direct_svr": n,
           "svri_median": round(float(np.median(y)), 1) if n else None,
           "models": {}}
    print(f"[svri_feas] N(direct-SVR, physiologic SVRI)={n}; SVRI median={res['svri_median']}",
          flush=True)
    if n < 40:
        res["verdict"] = "INSUFFICIENT_N"
        res["note"] = (f"only {n} usable direct-SVR cases; extraction still running "
                       "(parallelised). Re-run as N grows toward 248.")
        _write(res)
        print(f"[svri_feas] INSUFFICIENT N ({n}) -- re-run as extraction grows.", flush=True)
        return

    # The three model families.
    res["models"]["pressure_only"] = _oof_spearman_r2(df, PRESSURE, y)   # circular floor
    res["models"]["handbuilt_index"] = _oof_spearman_r2(df, INDEX, y)    # the r~0.34 scalar
    res["models"]["full_morphology"] = _oof_spearman_r2(df, MORPH, y)    # DL-upside proxy
    res["models"]["pressure_plus_morph"] = _oof_spearman_r2(df, PRESSURE + MORPH, y)

    p_r2 = res["models"]["pressure_only"]["r2"] or 0.0
    pm_r2 = res["models"]["pressure_plus_morph"]["r2"] or 0.0
    idx_r = res["models"]["handbuilt_index"]["r"] or 0.0
    morph_r = res["models"]["full_morphology"]["r"] or 0.0

    # (A) NON-CIRCULAR: morphology adds R^2 OVER mean pressure.
    incremental_r2 = round(pm_r2 - p_r2, 4)
    # (B) DL-UPSIDE: full morphology beats the single hand-built index.
    morph_beats_index = morph_r > idx_r + 0.03   # margin

    res["tests"] = {
        "A_noncircular_incremental_r2_over_pressure": incremental_r2,
        "A_pass": bool(incremental_r2 > 0.02),
        "B_full_morph_spearman": morph_r,
        "B_handbuilt_index_spearman": idx_r,
        "B_full_beats_index": bool(morph_beats_index),
    }
    go = res["tests"]["A_pass"] and morph_beats_index
    res["verdict"] = "GO -- good Phase-2 candidate" if go else (
        "MARGINAL/NO-GO -- see tests")
    _write(res)
    print(f"[svri_feas] incremental R2 over pressure = {incremental_r2}; "
          f"full-morph r={morph_r} vs index r={idx_r}; VERDICT: {res['verdict']}",
          flush=True)


def _write(res):
    os.makedirs(_CACHE, exist_ok=True)
    with open(os.path.join(_CACHE, "svri_morphology_feasibility_results.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=float)
    L = []
    a = L.append
    a("# Is a waveform->SVRI predictor a good Phase-2 candidate? (CPU feasibility)\n")
    a("## READ FIRST")
    a("- Tests whether a model predicting MEASURED SVRI from the arterial waveform carries "
      "signal worth a DL + generative (Phase-2) investment, BEFORE committing a GPU.")
    a("- Phase 2 is worth it iff the waveform morphology (A) adds SVRI-prediction OVER mean "
      "pressure (non-circular -- SVRI is mechanically tied to MAP), and (B) the FULL "
      "morphology beats the single hand-built vasoplegia index (room for a generative "
      "model to discover residual tone-encoding shape).")
    a("- Predictors EXCLUDE the SVRI ingredients (fluid_svr_*/co/ci, svri_*) -- circular.")
    a(f"- **N = {res.get('n_direct_svr')}** direct-EV1000-SVR cases (extraction still running, "
      "parallelised; re-run as N grows toward 248). Small-N -> regularised Ridge, "
      "repeated-KFold out-of-fold. HYPOTHESIS-GENERATING.\n")
    if res.get("verdict") == "INSUFFICIENT_N":
        a(f"## Verdict: INSUFFICIENT N ({res.get('n_direct_svr')}). {res.get('note')}")
    else:
        m = res["models"]; t = res["tests"]
        a("## Cross-validated waveform->SVRI prediction (out-of-fold Spearman r / R^2)\n")
        a("| model | features | OOF Spearman r | OOF R^2 |")
        a("|---|---|---|---|")
        for k in ("pressure_only", "handbuilt_index", "full_morphology", "pressure_plus_morph"):
            mm = m[k]
            a(f"| {k} | {mm['n_features']} | {mm['r']} (sd {mm.get('r_sd')}) | {mm['r2']} |")
        a("")
        a("## The two candidacy tests\n")
        a(f"- **(A) Non-circular** -- morphology incremental R^2 OVER mean pressure = "
          f"**{t['A_noncircular_incremental_r2_over_pressure']}** -> "
          f"{'PASS' if t['A_pass'] else 'FAIL'} (need > 0.02). If positive, there is "
          "tone-encoding waveform shape beyond pressure -- exactly what Phase 2 would "
          "synthesise/interpret.")
        a(f"- **(B) DL-upside** -- full-morphology r = {t['B_full_morph_spearman']} vs "
          f"hand-built index r = {t['B_handbuilt_index_spearman']} -> "
          f"{'full set beats the index (room to discover)' if t['B_full_beats_index'] else 'index already captures it (little DL upside)'}.")
        a(f"\n## VERDICT: **{res['verdict']}**\n")
        a("Caveats: small N (re-run as extraction grows); SVRI is CO-derived (noisy ceiling); "
          "Ridge is a linear proxy for the DL upside -- a true DL model could find MORE "
          "than the linear full-morphology model shows, so a positive (A) with even a "
          "modest (B) is encouraging. A leakage-clean DL waveform->SVRI predictor that is "
          "incremental over pressure + the scalar index, on a locked test, would be the "
          "gate to the Phase-2 SVRI-morphology arm.")
    a("\n---\n*Generated by analysis/svri_morphology_feasibility.py*")
    os.makedirs(_DOCS, exist_ok=True)
    with open(os.path.join(_DOCS, "SVRI_MORPHOLOGY_FEASIBILITY.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
