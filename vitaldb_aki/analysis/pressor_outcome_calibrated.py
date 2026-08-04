"""pressor_outcome_calibrated.py -- PIVOT #3: is CUMULATIVE VASOPRESSOR REQUIREMENT
the real intraoperative hemodynamic-insult exposure for organ injury (vs MAP)?

Rationale (from the controlled-variable finding, docs/PRESSOR_REQUIREMENT.md)
---------------------------------------------------------------------------
Intraoperative MAP is feedback-REGULATED: the anaesthetist titrates pressor to hold
MAP at target. So `map_auc_below_65` mostly measures controller LAG, while the DOSE
required measures the true hemodynamic insult. Hypothesis: cumulative norepinephrine
requirement predicts AKI better than -- and beyond -- MAP-AUC.

The honest threat is identical to the one that KILLED the CKD-MAP finding: pressor is
given to SICKER patients (confounding by indication), so a raw norepi->AKI excess is
expected from confounding alone. This module applies the SAME negative-control
calibration (Schuemie/Madigan) that killed CKD-MAP:

  * Target outcome     : organ_renal (AKI).
  * Negative controls  : organ_hepatocellular / cholestatic / coagulation (NOT
                         perfusion/pressor-target organs -> any norepi "effect" on
                         them is pure confounding-by-indication).
  * Calibrate the renal adjusted-RD against the empirical null from the controls.
    SPECIFIC only if renal excess EXCEEDS the negative-control null.

Plus the head-to-head the reframe predicts:
  * AKI ~ MAP-AUC<65 alone   vs   AKI ~ norepi-dose alone   (adjusted);
  * mutual adjustment: does norepi add BEYOND MAP-AUC, and does MAP-AUC survive
    adjustment for norepi? (if dose is the true insult, MAP-AUC should attenuate);
  * norepi dose-response (tertiles) on AKI, adjusted + calibrated.

stdlib only at import; numpy/sklearn lazy.
Run: python3 -m vitaldb_aki.analysis.pressor_outcome_calibrated
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
TARGET = "organ_renal"
CONTROLS = ["organ_hepatocellular", "organ_cholestatic", "organ_coagulation"]
PERFUSION = "organ_hypoperfusion"   # perfusion-related (positive-ish reference)
COVS = ["age", "sex_male", "weight_kg", "height_cm", "asa_class", "surgery_duration",
        "egfr_ckd_epi"]


def _prep(m):
    import numpy as np, pandas as pd
    df = m.copy()
    for c in [TARGET, PERFUSION] + CONTROLS + COVS + ["intraop_norepi", "map_auc_below_65",
                                                      "any_vasopressor", "optype_code"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["NOREPI"] = (df["intraop_norepi"].fillna(0) > 0).astype(int)
    return df


def _gcomp_rd(df, expo, out, cov, n_boot=300):
    """Marginal (g-computation) adjusted risk difference of `expo` on `out`, logistic
    outcome model + standardization over the sample; cluster-free bootstrap CI."""
    import numpy as np, pandas as pd
    from sklearn.linear_model import LogisticRegression
    cols = [expo] + [c for c in cov if c in df.columns]
    d = df[cols + [out]].copy()
    d[out] = pd.to_numeric(d[out], errors="coerce")
    d = d.dropna()
    if len(d) < 200 or d[out].nunique() < 2 or d[expo].nunique() < 2:
        return None
    X = d[cols].to_numpy(float); y = d[out].to_numpy(int)
    # standardize covariates for conditioning stability
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1
    Xs = (X - mu) / sd
    ei = cols.index(expo)
    def fit_rd(Xs_, y_):
        lr = LogisticRegression(max_iter=2000, C=1.0)
        lr.fit(Xs_, y_)
        X1 = Xs_.copy(); X1[:, ei] = (1 - mu[ei]) / sd[ei]
        X0 = Xs_.copy(); X0[:, ei] = (0 - mu[ei]) / sd[ei]
        return float(lr.predict_proba(X1)[:, 1].mean() - lr.predict_proba(X0)[:, 1].mean())
    rd = fit_rd(Xs, y)
    rng = np.random.default_rng(SEED); bs = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            bs.append(fit_rd(Xs[idx], y[idx]))
        except Exception:
            pass
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)
    base = float(y.mean())
    return {"rd": round(rd, 5), "ci": [round(lo, 5), round(hi, 5)] if lo is not None else None,
            "base_rate": round(base, 4), "n": int(n), "events": int(y.sum())}


def _evalue(rd, base):
    """E-value for a risk difference via approximate RR on the outcome."""
    import math
    if base <= 0:
        return None
    rr = (base + rd) / base
    if rr < 1:
        rr = 1 / rr
    return round(rr + math.sqrt(rr * (rr - 1)), 2) if rr > 1 else 1.0


def main():
    import numpy as np, pandas as pd
    m = pd.read_csv(os.path.join(_CACHE, "inspire_matrix.csv"), low_memory=False)
    df = _prep(m)
    res = {"seed": SEED, "exposure": "NOREPI (intraop norepinephrine infusion used)",
           "n_total": int(len(df)), "n_norepi": int(df["NOREPI"].sum())}

    # 1) adjusted RD of NOREPI on target + controls + perfusion
    rds = {}
    for o in [TARGET, PERFUSION] + CONTROLS:
        r = _gcomp_rd(df, "NOREPI", o, COVS)
        if r:
            rds[o] = r
            print(f"[pout] NOREPI -> {o}: adjRD {r['rd']} CI {r['ci']} (base {r['base_rate']})", flush=True)
    res["adjusted_rd"] = rds

    # 2) negative-control calibration of the renal effect
    ctrl = [rds[o]["rd"] for o in CONTROLS if o in rds]
    mu = float(np.mean(ctrl)) if ctrl else 0.0
    sd = float(np.std(ctrl, ddof=1)) if len(ctrl) > 1 else 0.0
    renal = rds.get(TARGET, {}).get("rd", 0.0)
    res["negative_control_null"] = {"mean": round(mu, 5), "sd": round(sd, 5),
                                    "controls": {o: rds[o]["rd"] for o in CONTROLS if o in rds}}
    res["renal_calibrated"] = round(renal - mu, 5)
    res["renal_z_vs_null"] = round((renal - mu) / sd, 2) if sd > 0 else None
    specific = (renal - mu > 0 and rds.get(TARGET, {}).get("ci", [0])[0] is not None and
                rds[TARGET]["ci"][0] > 0 and res["renal_z_vs_null"] is not None and
                res["renal_z_vs_null"] > 1.0)
    res["evalue_renal"] = _evalue(renal, rds.get(TARGET, {}).get("base_rate", 0.05))

    # 3) head-to-head: MAP-AUC vs NOREPI dose, and mutual adjustment
    df["MAPAUC"] = pd.to_numeric(df["map_auc_below_65"], errors="coerce")
    df["MAPAUC_hi"] = (df["MAPAUC"] > df["MAPAUC"][df["MAPAUC"] > 0].median()).astype(int)
    hh = {}
    hh["mapauc_alone"] = _gcomp_rd(df, "MAPAUC_hi", TARGET, COVS)
    hh["norepi_alone"] = _gcomp_rd(df, "NOREPI", TARGET, COVS)
    hh["norepi_adj_for_mapauc"] = _gcomp_rd(df, "NOREPI", TARGET, COVS + ["MAPAUC_hi"])
    hh["mapauc_adj_for_norepi"] = _gcomp_rd(df, "MAPAUC_hi", TARGET, COVS + ["NOREPI"])
    res["head_to_head"] = hh

    # 4) dose-response across norepi tertiles (among users), adjusted RD vs non-users
    users = df[df["NOREPI"] == 1].copy()
    if len(users) > 60:
        d = pd.to_numeric(users["intraop_norepi"], errors="coerce")
        t1, t2 = d.quantile([1/3, 2/3])
        df["norepi_tertile"] = 0
        df.loc[df["NOREPI"] == 1, "norepi_tertile"] = np.where(d <= t1, 1, np.where(d <= t2, 2, 3))
        dr = {}
        for t in (1, 2, 3):
            sub = df[(df["norepi_tertile"] == t) | (df["NOREPI"] == 0)].copy()
            sub["EXP"] = (sub["norepi_tertile"] == t).astype(int)
            r = _gcomp_rd(sub, "EXP", TARGET, COVS)
            if r:
                dr[f"tertile_{t}_vs_none"] = r["rd"]
        res["dose_response_adjRD"] = dr
        res["dose_response_monotone"] = bool(
            len(dr) == 3 and dr["tertile_1_vs_none"] <= dr["tertile_2_vs_none"] <= dr["tertile_3_vs_none"])

    # verdict
    na = hh.get("norepi_adj_for_mapauc") or {}
    ma = hh.get("mapauc_adj_for_norepi") or {}
    reframe = bool(na.get("rd", 0) > 0 and na.get("ci") and na["ci"][0] > 0 and
                   ma.get("rd", 1) is not None and abs(ma.get("rd", 0)) < (hh.get("mapauc_alone") or {}).get("rd", 1))
    res["verdict"] = (
        (f"SPECIFIC -- norepi requirement -> AKI survives negative-control calibration "
         f"(renal adjRD {renal} vs null {round(mu,5)}+-{round(sd,5)}, calibrated "
         f"{res['renal_calibrated']}, z={res['renal_z_vs_null']}, E-value {res['evalue_renal']})."
         if specific else
         f"NOT SPECIFIC -- renal adjRD {renal} ~ negative-control null {round(mu,5)} "
         f"(calibrated {res['renal_calibrated']}, z={res['renal_z_vs_null']}); like CKD-MAP, the "
         f"cumulative-pressor->AKI excess is largely confounding by indication.") +
        (" REFRAME SUPPORTED: norepi adds beyond MAP-AUC and MAP-AUC attenuates when adjusted for "
         "norepi -- dose is the better-identified insult." if reframe else
         " Reframe NOT clearly supported in adjusted head-to-head."))
    json.dump(res, open(os.path.join(_CACHE, "pressor_outcome_calibrated.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("\n[pout] VERDICT: " + res["verdict"], flush=True)
    print("[pout] -> docs/PRESSOR_OUTCOME_CALIBRATED.md", flush=True)


def _doc(res):
    L = ["# Pivot #3: cumulative vasopressor requirement -> organ injury (calibrated)\n",
         "Tests whether cumulative norepinephrine requirement is the real intraoperative "
         "hemodynamic-insult exposure for AKI -- using the SAME negative-control calibration that "
         "killed the CKD-MAP finding, because pressor-by-indication confounding is the central "
         "threat.\n",
         f"- Cohort: {res['n_total']} INSPIRE operations; norepi infusion used in {res['n_norepi']}.",
         "## Adjusted risk differences (g-computation, marginal)"]
    for o, r in res.get("adjusted_rd", {}).items():
        tag = "TARGET" if o == TARGET else ("perfusion" if o == PERFUSION else "negative control")
        L.append(f"- {o} ({tag}): adjRD **{r['rd']}** (95% CI {r['ci']}, base {r['base_rate']}, "
                 f"events {r['events']}).")
    nc = res.get("negative_control_null", {})
    L += ["", f"**Negative-control null:** {nc.get('mean')} +- {nc.get('sd')} "
          f"(hepatocellular/cholestatic/coagulation).",
          f"**Renal calibrated vs null:** {res.get('renal_calibrated')} (z={res.get('renal_z_vs_null')}, "
          f"E-value {res.get('evalue_renal')}).", "",
          "## Head-to-head: MAP-AUC<65 vs norepi requirement"]
    for k, r in res.get("head_to_head", {}).items():
        if r:
            L.append(f"- {k}: adjRD {r['rd']} (CI {r['ci']}).")
    if "dose_response_adjRD" in res:
        L += ["", f"## Norepi dose-response (tertiles vs non-users): {res['dose_response_adjRD']} "
              f"(monotone={res.get('dose_response_monotone')})"]
    L += ["", "## Verdict", res["verdict"], "",
          "## Caveats",
          "- `intraop_norepi` is the recorded cumulative norepinephrine (INSPIRE); not "
          "concentration/weight-normalised here beyond weight as a covariate.",
          "- Confounding by indication is the central threat; negative-control calibration is the "
          "mitigation, not randomisation. A NULL after calibration means the raw excess was "
          "confounding (the honest, CKD-MAP-style outcome).",
          "- Single database (INSPIRE); VitalDB stable-epoch requirement is the mechanistic complement."]
    open(os.path.join(_DOCS, "PRESSOR_OUTCOME_CALIBRATED.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
