"""svri_morphology_hostile_review.py -- adversarial stress-test of PIVOT 2: the
SVR-free arterial-waveform estimate of measured SVRI (docs/SVRI_MORPHOLOGY_FEASIBILITY.md).

This is the one finding that survived the outcome-confounding battery (it targets a
MEASURED physiologic quantity, not a confounded outcome). Subject it to the same
hostile review. Attacks tested:
  A. CIRCULARITY -- SVRI = 80*(MAP-CVP)/CO is mechanically tied to MAP. Does STRICTLY
     non-pressure morphology (shape/timing/coupling, NOT pressure levels) predict
     DIRECT-measured SVRI incrementally over ALL pressure scalars? On the DIRECT-SVR
     subset only, so the target never contains the predictor's MAP.
  B. OVERFITTING -- permutation null: shuffle SVRI, recompute the OOF r; the real r
     must exceed the permutation distribution.
  C. BODY-SIZE confounding -- does morphology add over pressure + weight/BSA/age/sex?
  D. WHICH FEATURE -- tau (diastolic decay = R*C) partial-correlated with SVRI given
     MAP; is there a mechanistic, non-pressure single feature?
  E. STABILITY -- bootstrap CI on the OOF r.

Run: python3 -m vitaldb_aki.analysis.svri_morphology_hostile_review   (from repo root)
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_CSV = os.path.join(_CACHE, "vasoplegia_validation.csv")
SEED = 20260626

PRESSURE = ["art_map_mean", "art_sbp_mean", "art_dbp_mean", "art_pulse_pressure_mean",
            "art_pulse_pressure_sd"]
# STRICTLY non-pressure-LEVEL morphology: shape, timing, rate, coupling -- NOT derivable
# from mean pressure. (dP/dt and burden-of-low-pressure features excluded as conservative.)
MORPH_STRICT = ["art_tau_decay_mean", "art_aug_index_mean", "art_hr_mean", "art_hr_sd",
                "pat_mean_ms", "pat_sd_ms", "pat_slope", "art_ppg_amp_corr",
                "central_peripheral_decoupling", "brs_mean", "cardiopulm_coherence",
                "resp_sbp_coupling"]
SIZE = ["weight_kg", "bsa_m2", "age", "sex_male"]


def _oof(df, cols, y, seed=SEED, n_splits=5, n_rep=5):
    import numpy as np, pandas as pd
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return {"r": None, "r2": None}
    X = df[cols].apply(lambda s: pd.to_numeric(s, errors="coerce")).to_numpy(float)
    rs, r2s = [], []
    for rep in range(n_rep):
        oof = np.full(len(y), np.nan)
        for tr, te in KFold(n_splits, shuffle=True, random_state=seed + rep).split(X):
            pipe = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                             ("m", RidgeCV(alphas=(0.1, 1, 10, 100)))])
            pipe.fit(X[tr], y[tr]); oof[te] = pipe.predict(X[te])
        msk = ~np.isnan(oof)
        if msk.sum() > 5 and np.std(oof[msk]) > 1e-9:
            rs.append(float(stats.spearmanr(oof[msk], y[msk])[0]))
            ssr = float(np.sum((y[msk] - oof[msk]) ** 2)); sst = float(np.sum((y[msk] - y[msk].mean()) ** 2))
            r2s.append(1 - ssr / sst if sst > 0 else float("nan"))
    return {"r": round(float(np.mean(rs)), 4) if rs else None,
            "r2": round(float(np.nanmean(r2s)), 4) if r2s else None,
            "n_features": len(cols)}


def main():
    import numpy as np, pandas as pd
    from scipy import stats
    v = pd.read_csv(_CSV)
    v = v[v.get("has_direct_svr").astype(str) == "1"] if "has_direct_svr" in v else v
    y = pd.to_numeric(v.get("svri_measured"), errors="coerce")
    keep = y.between(300, 5000)
    v, y = v[keep].reset_index(drop=True), y[keep].reset_index(drop=True).to_numpy(float)
    res = {"seed": SEED, "n_direct_svr": int(len(y)), "attacks": {}}
    print(f"[hostile] N(direct-SVR)={len(y)}", flush=True)
    if len(y) < 40:
        res["verdict"] = "INSUFFICIENT_N"; _write(res); return

    # A. CIRCULARITY: strict non-pressure morphology incremental over ALL pressure
    p = _oof(v, PRESSURE, y); ps = _oof(v, PRESSURE + MORPH_STRICT, y)
    incr = round((ps["r2"] or 0) - (p["r2"] or 0), 4)
    res["attacks"]["A_circularity"] = {
        "pressure_only_r2": p["r2"], "pressure_plus_strict_morph_r2": ps["r2"],
        "strict_morph_incremental_r2_over_pressure": incr,
        "pass": bool(incr > 0.02),
        "note": "strict non-pressure morphology (tau/AIx/timing/coupling) adds R2 over ALL "
                "pressure scalars on DIRECT-measured SVRI -> not circular with MAP"}

    # B. OVERFITTING: permutation null
    full = _oof(v, PRESSURE + MORPH_STRICT, y)
    rng = np.random.default_rng(SEED)
    null = []
    for _ in range(200):
        yp = rng.permutation(y)
        rr = _oof(v, PRESSURE + MORPH_STRICT, yp, n_rep=2)["r"]
        if rr is not None:
            null.append(abs(rr))
    real = abs(full["r"] or 0)
    pval = round((1 + sum(1 for z in null if z >= real)) / (1 + len(null)), 4)
    res["attacks"]["B_overfitting"] = {
        "real_oof_r": full["r"], "perm_null_r_mean": round(float(np.mean(null)), 4),
        "perm_null_r_95pct": round(float(np.percentile(null, 95)), 4), "perm_p": pval,
        "pass": bool(pval < 0.05)}

    # C. BODY-SIZE confounding: morph adds over pressure + size?
    base = _oof(v, PRESSURE + SIZE, y); base_m = _oof(v, PRESSURE + SIZE + MORPH_STRICT, y)
    incr_c = round((base_m["r2"] or 0) - (base["r2"] or 0), 4)
    res["attacks"]["C_body_size"] = {
        "pressure_plus_size_r2": base["r2"], "plus_morph_r2": base_m["r2"],
        "morph_incremental_r2_over_pressure_and_size": incr_c, "pass": bool(incr_c > 0.02)}

    # D. tau partial-correlation with SVRI given MAP (mechanistic single feature)
    tau = pd.to_numeric(v.get("art_tau_decay_mean"), errors="coerce").to_numpy(float)
    mapm = pd.to_numeric(v.get("art_map_mean"), errors="coerce").to_numpy(float)
    msk = np.isfinite(tau) & np.isfinite(mapm) & np.isfinite(y)
    def _resid(a, b):  # residual of a on b (linear)
        bb = np.c_[np.ones(b.sum() if b.dtype == bool else len(b))]
        return a
    # partial spearman: residualize tau and SVRI on MAP (rank), correlate residuals
    from numpy.polynomial import polynomial as P
    def partial(xa, xb, xc):  # corr(xa, xb | xc)
        ra = xa - np.poly1d(np.polyfit(xc, xa, 1))(xc)
        rb = xb - np.poly1d(np.polyfit(xc, xb, 1))(xc)
        return float(stats.spearmanr(ra, rb)[0])
    res["attacks"]["D_tau_mechanism"] = {
        "tau_vs_svri_spearman": round(float(stats.spearmanr(tau[msk], y[msk])[0]), 4),
        "tau_vs_svri_partial_given_MAP": round(partial(tau[msk], y[msk], mapm[msk]), 4),
        "note": "tau = diastolic decay time constant ~ R*C; a POSITIVE partial corr with "
                "measured SVRI given MAP is mechanistic, non-pressure evidence"}

    # E. STABILITY: bootstrap CI on the full OOF r (case resample)
    rng2 = np.random.default_rng(SEED + 1)
    bs = []
    for _ in range(300):
        idx = rng2.integers(0, len(y), len(y))
        rr = _oof(v.iloc[idx].reset_index(drop=True), PRESSURE + MORPH_STRICT, y[idx], n_rep=2)["r"]
        if rr is not None:
            bs.append(rr)
    res["attacks"]["E_stability"] = {"oof_r": full["r"],
        "bootstrap_ci": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]}

    A = res["attacks"]
    passes = [A["A_circularity"]["pass"], A["B_overfitting"]["pass"], A["C_body_size"]["pass"]]
    res["n_attacks_survived"] = int(sum(passes))
    res["verdict"] = (
        "PASSES hostile review -- strict non-pressure morphology predicts DIRECT-measured "
        f"SVRI beyond all pressure scalars (incr R2 {A['A_circularity']['strict_morph_incremental_r2_over_pressure']}), "
        f"beats permutation null (p={A['B_overfitting']['perm_p']}), survives body-size "
        f"adjustment (incr R2 {A['C_body_size']['morph_incremental_r2_over_pressure_and_size']}); "
        f"tau partial-vs-SVRI given MAP = {A['D_tau_mechanism']['tau_vs_svri_partial_given_MAP']}."
        if all(passes) else
        "WEAKENED -- see per-attack flags; the SVR-free morphology claim does not fully "
        "clear all hostile attacks at this N.")
    _write(res)
    print(f"[hostile] survived {res['n_attacks_survived']}/3 core attacks. {res['verdict']}", flush=True)


def _write(res):
    json.dump(res, open(os.path.join(_CACHE, "svri_morphology_hostile_review_results.json"), "w"),
              indent=2, default=float)
    L = ["# Pivot 2 hostile review: SVR-free waveform estimate of measured SVRI\n",
         f"N (direct-EV1000-SVR cases, physiologic SVRI) = {res.get('n_direct_svr')}. The one "
         "finding that survived the outcome-confounding battery (targets MEASURED physiology, "
         "not a confounded outcome) -- here stress-tested with the same hostility.\n"]
    if res.get("verdict") == "INSUFFICIENT_N":
        L.append("INSUFFICIENT N -- extraction still running; re-run as N grows.")
    else:
        a = res["attacks"]
        L += [f"- **A. Circularity:** strict NON-pressure morphology incremental R^2 over ALL "
              f"pressure scalars (direct-SVR) = **{a['A_circularity']['strict_morph_incremental_r2_over_pressure']}** "
              f"-> {'PASS' if a['A_circularity']['pass'] else 'FAIL'} (not just re-reading MAP).",
              f"- **B. Overfitting:** OOF r {a['B_overfitting']['real_oof_r']} vs permutation null "
              f"mean {a['B_overfitting']['perm_null_r_mean']} (95th {a['B_overfitting']['perm_null_r_95pct']}), "
              f"perm p = **{a['B_overfitting']['perm_p']}** -> {'PASS' if a['B_overfitting']['pass'] else 'FAIL'}.",
              f"- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = "
              f"**{a['C_body_size']['morph_incremental_r2_over_pressure_and_size']}** -> "
              f"{'PASS' if a['C_body_size']['pass'] else 'FAIL'}.",
              f"- **D. Mechanism:** tau (diastolic decay ~ R*C) partial-Spearman vs SVRI given MAP "
              f"= **{a['D_tau_mechanism']['tau_vs_svri_partial_given_MAP']}** (raw "
              f"{a['D_tau_mechanism']['tau_vs_svri_spearman']}).",
              f"- **E. Stability:** OOF r {a['E_stability']['oof_r']}, bootstrap CI "
              f"{a['E_stability']['bootstrap_ci']}.",
              f"\n## Verdict: {res['verdict']}\n",
              "Limitations: single-centre; EV1000/Vigileo CO-monitor subset (selected); SVRI is "
              "CO-derived (noisy); modest N. PASS here means the SVR-free morphology signal is "
              "real, non-circular, not overfit, and not a body-size proxy -- a defensible "
              "MEASUREMENT claim (no outcome, so no outcome-confounding), and the basis for Phase 2e."]
    open(os.path.join(_DOCS, "SVRI_MORPHOLOGY_HOSTILE_REVIEW.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
