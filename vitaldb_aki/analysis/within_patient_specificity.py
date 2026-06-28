"""within_patient_specificity.py -- the decisive hostile-review test of the NEW
headline (within-patient causal hypotension->AKI, docs/INSPIRE_WITHIN_PATIENT.md).

The between-patient CKD finding died because its excess was NOT organ-specific
(negative-control calibration -> confounding null; docs/REDTEAM_CKD_MAP.md). The
within-patient design removes time-INVARIANT confounding, but TIME-VARYING confounding
(a patient acutely sicker the day of the higher-hypotension op) remains. This applies
the SAME negative-control specificity test to the WITHIN-PATIENT estimate:

  Patient fixed-effects (demeaned LPM) within-patient association of HYPO with EACH
  organ outcome. If hypotension is a CAUSE, the within-patient effect should
  concentrate on hypotension-target organs (renal / hypoperfusion) and be ~null on
  non-perfusion negative controls (hepatocellular / cholestatic / coagulation). If it
  is pan-organ within-patient too, even the within-patient effect is time-varying
  confounded -> the causal-leaning claim does NOT survive.

Run: python3 -m vitaldb_aki.analysis.within_patient_specificity   (from repo root)
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260626
TARGETS = ["organ_renal", "organ_hypoperfusion"]   # hypotension-target organs
CONTROLS = ["organ_hepatocellular", "organ_cholestatic", "organ_coagulation"]


def _fe_rd(df, sid, expo, out, n_boot=300):
    """Within-patient (patient fixed-effects) demeaned-LPM risk difference of `expo`
    on `out`, with a cluster (subject) bootstrap CI. Uses only exposure-varying
    subjects (others contribute 0 to the within estimator)."""
    import numpy as np, pandas as pd
    d = df[[sid, expo, out]].copy()
    d[out] = pd.to_numeric(d[out], errors="coerce")
    d = d[d[out].notna() & d[expo].notna()]
    g = d.groupby(sid)
    d["x_dm"] = d[expo] - g[expo].transform("mean")
    d["y_dm"] = d[out] - g[out].transform("mean")
    x = d["x_dm"].to_numpy(float); y = d["y_dm"].to_numpy(float)
    sxx = float(np.sum(x * x))
    if sxx <= 0:
        return None
    beta = float(np.sum(x * y) / sxx)
    # cluster bootstrap: precompute per-subject sums, resample subjects
    d["_xy"] = x * y; d["_xx"] = x * x
    by = d.groupby(sid)[["_xy", "_xx"]].sum()
    xy = by["_xy"].to_numpy(); xx = by["_xx"].to_numpy(); m = len(xy)
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(n_boot):
        idx = rng.integers(0, m, m)
        sx = xx[idx].sum()
        if sx > 0:
            bs.append(xy[idx].sum() / sx)
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)
    return {"rd": round(beta, 4), "ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
            "n_informative_ops": int((d["x_dm"] != 0).sum())}


def main():
    import numpy as np, pandas as pd
    m = pd.read_csv(os.path.join(_CACHE, "inspire_matrix.csv"), low_memory=False)
    sid = "subject_id" if "subject_id" in m.columns else "subjectid"
    m[sid] = m[sid].astype(str)
    m["map_auc_below_65"] = pd.to_numeric(m["map_auc_below_65"], errors="coerce")
    b = m["map_auc_below_65"].fillna(0.0)
    m["HYPO"] = (b > b[b > 0].median()).astype(int)
    # multi-op subjects only
    vc = m[sid].value_counts()
    m = m[m[sid].isin(vc[vc >= 2].index)].copy()
    res = {"seed": SEED, "n_ops": int(len(m)), "n_subjects": int(m[sid].nunique()),
           "within_patient_rd": {}}
    for o in TARGETS + CONTROLS:
        if o in m.columns:
            r = _fe_rd(m, sid, "HYPO", o)
            if r:
                res["within_patient_rd"][o] = r
                print(f"[wp_spec] {o}: within-RD {r['rd']} CI {r['ci']}", flush=True)
    # negative-control calibration of the within-patient renal estimate
    ctrl_rds = [res["within_patient_rd"][o]["rd"] for o in CONTROLS if o in res["within_patient_rd"]]
    mu = float(np.mean(ctrl_rds)) if ctrl_rds else 0.0
    sd = float(np.std(ctrl_rds, ddof=1)) if len(ctrl_rds) > 1 else 0.0
    renal = res["within_patient_rd"].get("organ_renal", {}).get("rd", 0.0)
    res["within_negative_control_null"] = {"mean": round(mu, 4), "sd": round(sd, 4),
                                           "controls": {o: res["within_patient_rd"][o]["rd"]
                                                        for o in CONTROLS if o in res["within_patient_rd"]}}
    res["renal_calibrated_within"] = round(renal - mu, 4)
    res["renal_z_vs_within_null"] = round((renal - mu) / sd, 2) if sd > 0 else None
    specific = (renal - mu > 0) and (res["within_patient_rd"]["organ_renal"]["ci"][0] > 0) and \
               (res["renal_z_vs_within_null"] is not None and res["renal_z_vs_within_null"] > 1.0)
    res["verdict"] = (
        f"SURVIVES specificity within-patient -- renal within-RD {renal} vs negative-control "
        f"within-null {round(mu,4)}+-{round(sd,4)} (calibrated {res['renal_calibrated_within']}, "
        f"z={res['renal_z_vs_within_null']}); the causal-leaning hypotension->AKI effect is "
        "organ-specific even within-patient." if specific else
        f"FAILS specificity within-patient -- renal within-RD {renal} ~ negative-control null "
        f"{round(mu,4)} (calibrated {res['renal_calibrated_within']}); the within-patient effect "
        "is ALSO pan-organ -> time-varying confounding not excluded.")
    json.dump(res, open(os.path.join(_CACHE, "within_patient_specificity_results.json"), "w"),
              indent=2, default=float)
    # doc
    L = ["# Within-patient SPECIFICITY test (hostile review of the causal-leaning pivot)\n",
         "Applies the negative-control specificity test that killed the BETWEEN-patient CKD "
         "finding to the WITHIN-PATIENT hypotension->AKI estimate (docs/INSPIRE_WITHIN_PATIENT.md). "
         "Patient fixed-effects (demeaned LPM) within-patient risk difference of substantial "
         "hypotension (HYPO) on each organ outcome; cluster-bootstrap CI over subjects.\n",
         f"Cohort: {res['n_ops']} multi-op operations, {res['n_subjects']} subjects.\n",
         "| outcome | type | within-patient RD | 95% CI |", "|---|---|---|---|"]
    for o in TARGETS + CONTROLS:
        if o in res["within_patient_rd"]:
            r = res["within_patient_rd"][o]
            t = "hypotension-target" if o in TARGETS else "negative control"
            L.append(f"| {o} | {t} | {r['rd']} | {r['ci']} |")
    L += ["", f"**Within-patient negative-control null:** {res['within_negative_control_null']['mean']} "
          f"+- {res['within_negative_control_null']['sd']} (hepatocellular/cholestatic/coagulation).",
          f"**Renal within-RD calibrated against the within-null:** {res['renal_calibrated_within']} "
          f"(z={res['renal_z_vs_within_null']}).", "",
          f"## Verdict\n{res['verdict']}\n",
          "Note: a within-patient effect on renal/hypoperfusion that EXCEEDS the non-perfusion "
          "negative-control organs is strong evidence the within-patient hypotension->AKI signal is "
          "organ-specific (causal-leaning), not generic time-varying severity. If the controls move "
          "as much as renal, time-varying confounding cannot be excluded even within-patient."]
    open(os.path.join(_DOCS, "WITHIN_PATIENT_SPECIFICITY.md"), "w").write("\n".join(L) + "\n")
    print(f"[wp_spec] VERDICT: {res['verdict']}", flush=True)


if __name__ == "__main__":
    main()
