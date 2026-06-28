"""redteam_ckd_map.py -- adversarial stress-tests of the CKD personalized-MAP-target
finding (intraop hypotension -> renal injury concentrated in eGFR<60), run on INSPIRE
cache/inspire_matrix.csv (131k). Each round = a distinct attack a skeptical reviewer
would make, tested empirically. Appends to cache/redteam_ckd_map_results.json and
docs/REDTEAM_CKD_MAP.md. Round selected via argv[1] (default 1).
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_MATRIX = os.path.join(_CACHE, "inspire_matrix.csv")
SEED = 20260626
COV = ["age", "sex_male", "asa_class", "emergency", "baseline_cr", "weight_kg", "n_map"]


def _load():
    import numpy as np, pandas as pd
    df = pd.read_csv(_MATRIX, low_memory=False)
    # exposure: substantial intraop hypotension burden (top-half of >0 burden) + a
    # sampling-robust nadir flag. ckd = eGFR<60. outcome organ_renal (KDIGO).
    for c in ["map_auc_below_65", "map_lowest", "organ_renal", "ckd", "egfr_ckd_epi", *COV]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["organ_renal"].notna() & df["ckd"].notna()].copy()
    b = df["map_auc_below_65"].fillna(0.0)
    pos = b[b > 0]
    thr = float(pos.median()) if len(pos) else 0.0
    df["HYPO"] = (b > thr).astype(int)              # substantial burden
    if "map_lowest" in df:
        df["HYPO_nadir"] = (df["map_lowest"] < 65).astype(int)
    return df


def _risk(df, expo="HYPO", out="organ_renal"):
    import numpy as np
    e = df[expo].to_numpy(); y = df[out].to_numpy(float)
    r1 = float(y[e == 1].mean()) if (e == 1).any() else float("nan")
    r0 = float(y[e == 0].mean()) if (e == 0).any() else float("nan")
    return r1, r0, int((e == 1).sum()), int((e == 0).sum()), int(y.sum())


def _gcomp_rd(df, expo="HYPO", out="organ_renal", cov=None):
    """Covariate-adjusted marginal risk difference + risk ratio via g-computation
    (logistic outcome model, standardise over the stratum's own covariate dist)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    cov = [c for c in (cov or COV) if c in df.columns]
    X = df[cov + [expo]].copy()
    y = df[out].to_numpy(float)
    pipe = Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("sc", StandardScaler()),
                     ("lr", LogisticRegression(max_iter=2000, C=1.0))])
    pipe.fit(X.to_numpy(float), y)
    X1 = X.copy(); X1[expo] = 1
    X0 = X.copy(); X0[expo] = 0
    p1 = pipe.predict_proba(X1.to_numpy(float))[:, 1].mean()
    p0 = pipe.predict_proba(X0.to_numpy(float))[:, 1].mean()
    return float(p1 - p0), float(p1 / p0) if p0 > 0 else float("nan"), float(p1), float(p0)


def round1(df):
    """ATTACK: the CKD x hypotension 'interaction' is RR non-collapsibility, not a real
    effect-modification. RR is non-collapsible -- CKD patients have higher BASELINE AKI
    risk, so an identical absolute (additive) effect yields a larger RR in CKD. The
    finding only matters clinically if the excess survives on the ADDITIVE (risk-
    difference) scale. TEST: crude + g-computation-adjusted RD and RR within CKD vs
    non-CKD; compare the interaction on the additive scale (RD_ckd - RD_nonckd) vs the
    multiplicative scale (RR ratio)."""
    import numpy as np
    out = {"attack": "RR non-collapsibility -- does CKD excess survive on the ADDITIVE (RD) scale?",
           "strata": {}}
    rng = np.random.default_rng(SEED)
    for name, sub in (("ckd", df[df["ckd"] == 1]), ("non_ckd", df[df["ckd"] == 0])):
        r1, r0, n1, n0, ev = _risk(sub)
        crude_rd, crude_rr = r1 - r0, (r1 / r0 if r0 > 0 else float("nan"))
        adj_rd, adj_rr, p1, p0 = _gcomp_rd(sub)
        # bootstrap CI for adjusted RD
        rds = []
        idx = np.arange(len(sub))
        for _ in range(200):
            bs = sub.iloc[rng.choice(idx, len(idx), replace=True)]
            try:
                rds.append(_gcomp_rd(bs)[0])
            except Exception:
                pass
        lo, hi = (float(np.percentile(rds, 2.5)), float(np.percentile(rds, 97.5))) if rds else (float("nan"),) * 2
        out["strata"][name] = {
            "n": int(len(sub)), "events": ev, "base_risk_unexposed": round(r0, 4),
            "crude_RD": round(crude_rd, 4), "crude_RR": round(crude_rr, 3),
            "adj_RD": round(adj_rd, 4), "adj_RD_ci": [round(lo, 4), round(hi, 4)],
            "adj_RR": round(adj_rr, 3),
        }
    rd_c = out["strata"]["ckd"]["adj_RD"]; rd_n = out["strata"]["non_ckd"]["adj_RD"]
    rr_c = out["strata"]["ckd"]["adj_RR"]; rr_n = out["strata"]["non_ckd"]["adj_RR"]
    out["additive_interaction_RD_ckd_minus_RD_nonckd"] = round(rd_c - rd_n, 4)
    out["multiplicative_ratio_RR_ckd_over_RR_nonckd"] = round(rr_c / rr_n, 3) if rr_n else None
    ci_c = out["strata"]["ckd"]["adj_RD_ci"]
    survives_additive = (rd_c > rd_n) and (ci_c[0] > 0)
    out["verdict"] = ("SURVIVES on the additive scale (CKD adj-RD > non-CKD adj-RD AND "
                      "CKD adj-RD CI excludes 0) -- the excess is real, not just RR "
                      "non-collapsibility") if survives_additive else (
                      "WEAKENED -- CKD excess does not clearly survive on the additive "
                      "scale; the RR-based finding is partly non-collapsibility")
    return out


def _additive_interaction(df, out, cov=None):
    """RD_ckd - RD_nonckd (g-computation adjusted) for a given outcome."""
    rd_c = _gcomp_rd(df[df["ckd"] == 1], out=out, cov=cov)[0]
    rd_n = _gcomp_rd(df[df["ckd"] == 0], out=out, cov=cov)[0]
    return round(rd_c - rd_n, 4), round(rd_c, 4), round(rd_n, 4)


def round2(df):
    """ATTACK: confounding by indication / severity / procedure. (1) NEGATIVE-CONTROL
    OUTCOMES -- if CKD patients who get hypotension are simply sicker, the CKD x
    hypotension ADDITIVE excess should appear on NON-renal organ outcomes too, not just
    renal. A renal-SPECIFIC excess argues against generic confounding. (2) PROCEDURE
    confounding -- cardiac/vascular surgery has more hypotension AND more AKI AND more
    CKD; does the renal CKD excess survive adding optype_code + surgery_duration? (3)
    E-value -- how strong an unmeasured confounder would have to be."""
    import math
    out = {"attack": "confounding by indication/severity/procedure -- negative-control "
                      "outcomes + procedure adjustment + E-value"}
    # (1) negative-control outcome panel (renal is the target; others should be ~0 if specific)
    panel = {}
    for o in ["organ_renal", "organ_hypoperfusion", "organ_hepatocellular",
              "organ_cholestatic", "organ_coagulation"]:
        if o in df.columns:
            import pandas as pd
            df[o] = pd.to_numeric(df[o], errors="coerce")
            sub = df[df[o].notna()]
            if sub[o].sum() >= 30:
                ai, rdc, rdn = _additive_interaction(sub, o)
                panel[o] = {"additive_interaction": ai, "RD_ckd": rdc, "RD_nonckd": rdn,
                            "events": int(sub[o].sum())}
    out["negative_control_outcome_panel"] = panel
    renal_ai = panel.get("organ_renal", {}).get("additive_interaction", 0.0)
    # specificity: renal interaction should exceed the non-renal/non-hypoperfusion controls
    ctrls = [panel[o]["additive_interaction"] for o in
             ("organ_hepatocellular", "organ_cholestatic", "organ_coagulation") if o in panel]
    max_ctrl = max([abs(c) for c in ctrls], default=0.0)
    out["renal_additive_interaction"] = renal_ai
    out["max_nonrenal_control_interaction"] = round(max_ctrl, 4)
    # (2) procedure-adjusted renal CKD excess
    proc_cov = COV + [c for c in ("optype_code", "surgery_duration") if c in df.columns]
    ai_proc, rdc_proc, rdn_proc = _additive_interaction(df[df["organ_renal"].notna()],
                                                         "organ_renal", cov=proc_cov)
    out["procedure_adjusted"] = {"additive_interaction": ai_proc, "RD_ckd": rdc_proc,
                                 "RD_nonckd": rdn_proc, "added_cov": proc_cov[len(COV):]}
    # (3) E-value for the CKD-stratum adjusted RR
    rr = _gcomp_rd(df[df["ckd"] == 1])[1]
    evalue = round(rr + math.sqrt(rr * (rr - 1)), 3) if rr and rr > 1 else None
    out["ckd_adjusted_RR"] = round(rr, 3) if rr else None
    out["e_value_ckd_RR"] = evalue
    specific = (renal_ai > 0.02) and (renal_ai > 2 * max_ctrl)
    survives_proc = ai_proc > 0.02
    out["verdict"] = (
        f"SURVIVES -- renal CKD excess ({renal_ai}) is {'renal-SPECIFIC' if specific else 'NOT clearly specific'} "
        f"(max non-renal control interaction {max_ctrl}); procedure-adjusted excess "
        f"{ai_proc} {'holds' if survives_proc else 'collapses'}; E-value {evalue}."
        if (specific and survives_proc) else
        f"WEAKENED -- specificity {'fails' if not specific else 'ok'} (renal {renal_ai} vs "
        f"max control {max_ctrl}); procedure-adjusted {ai_proc} "
        f"{'collapses' if not survives_proc else 'holds'}.")
    return out


def round3(df):
    """ATTACK: measurement/ascertainment + is the dose-response confounding-resistant?
    (1) AKI-ASCERTAINMENT bias -- CKD patients get more creatinine draws -> AKI more
    likely DETECTED; the hard endpoint death_inhosp is ascertainment-robust. Does the
    CKD x hypotension ADDITIVE excess hold for MORTALITY, and is it (like the organ panel)
    non-specific? (2) DOSE-RESPONSE -- a steeper hypotension-DOSE->AKI gradient in CKD is
    harder for pure confounding to fake than a binary flag. AKI rate by map_lowest band x
    CKD: is the gradient monotone AND steeper in CKD?"""
    import numpy as np, pandas as pd
    out = {"attack": "ascertainment (mortality endpoint) + dose-response confounding-resistance"}
    # (1) mortality
    if "death_inhosp" in df.columns:
        df["death_inhosp"] = pd.to_numeric(df["death_inhosp"], errors="coerce")
        sub = df[df["death_inhosp"].notna()]
        ai, rdc, rdn = _additive_interaction(sub, "death_inhosp")
        out["mortality_additive_interaction"] = {"interaction": ai, "RD_ckd": rdc,
                                                 "RD_nonckd": rdn, "events": int(sub["death_inhosp"].sum())}
    # (2) dose-response: AKI rate by map_lowest band x CKD
    ml = pd.to_numeric(df.get("map_lowest"), errors="coerce")
    bands = [(">=75", ml >= 75), ("65-75", (ml >= 65) & (ml < 75)),
             ("55-65", (ml >= 55) & (ml < 65)), ("<55", ml < 55)]
    dr = {}
    for ck, lab in ((1, "ckd"), (0, "non_ckd")):
        rates = []
        for bl, mask in bands:
            m = mask & (df["ckd"] == ck) & df["organ_renal"].notna()
            y = pd.to_numeric(df.loc[m, "organ_renal"], errors="coerce")
            rates.append({"band": bl, "n": int(m.sum()), "aki_rate": round(float(y.mean()), 4) if m.sum() else None})
        dr[lab] = rates
    out["dose_response_aki_by_map_lowest"] = dr
    # gradient = rate(<55) - rate(>=75), per stratum
    def _grad(rates):
        lo = next((r["aki_rate"] for r in rates if r["band"] == ">=75"), None)
        hi = next((r["aki_rate"] for r in rates if r["band"] == "<55"), None)
        return round(hi - lo, 4) if (lo is not None and hi is not None) else None
    g_ckd = _grad(dr["ckd"]); g_non = _grad(dr["non_ckd"])
    out["dose_gradient_ckd"] = g_ckd
    out["dose_gradient_nonckd"] = g_non
    out["gradient_steeper_in_ckd"] = bool(g_ckd is not None and g_non is not None and g_ckd > g_non)
    mort_ai = out.get("mortality_additive_interaction", {}).get("interaction")
    out["verdict"] = (
        f"PARTIAL -- mortality CKD x hypotension additive excess = {mort_ai} (ascertainment-"
        f"robust, but mortality is itself non-specific); hypotension dose-response gradient "
        f"steeper in CKD ({g_ckd} vs {g_non})={out['gradient_steeper_in_ckd']}. A steeper CKD "
        "dose-response is the one confounding-resistant signal, but R2's pan-organ "
        "non-specificity still caps the renal-specific claim.")
    return out


def round4(df_unused):
    """ATTACK: is the A-line vasoplegia index vs measured-SVRI correlation (r~-0.34)
    FRAGILE -- driven by a few influential cases, one cherry-picked component, or the
    SVRI computation? TEST on cache/vasoplegia_validation.csv: jackknife (drop-one r
    range), bootstrap CI, component-wise directional consistency, and physiologic-SVRI
    sensitivity."""
    import numpy as np, pandas as pd
    from scipy import stats
    out = {"attack": "vasoplegia index vs measured-SVRI -- fragility (leverage / single "
                      "component / SVRI computation)"}
    p = os.path.join(_CACHE, "vasoplegia_validation.csv")
    if not os.path.exists(p):
        out["verdict"] = "SKIP -- vasoplegia_validation.csv absent"
        return out
    v = pd.read_csv(p)
    if "has_direct_svr" in v:
        v = v[v["has_direct_svr"].astype(str) == "1"]
    svri = pd.to_numeric(v.get("svri_measured"), errors="coerce")
    keep = svri.between(300, 5000)
    v, svri = v[keep].reset_index(drop=True), svri[keep].reset_index(drop=True).to_numpy()
    n = len(svri)
    # reconstruct an oriented vasoplegia index: high index = low tone = vasoplegic.
    def z(s):
        s = np.asarray(s, dtype=float)
        sd = np.nanstd(s)
        return (s - np.nanmean(s)) / sd if sd > 0 else np.zeros_like(s)
    tau = pd.to_numeric(v.get("art_tau_decay_mean"), errors="coerce").to_numpy(float)
    dia_map = (pd.to_numeric(v.get("art_dbp_mean"), errors="coerce") /
               pd.to_numeric(v.get("art_map_mean"), errors="coerce")).to_numpy(float)
    aix = pd.to_numeric(v.get("art_aug_index_mean"), errors="coerce").to_numpy(float)
    # component-wise Spearman vs SVRI (hypothesised POSITIVE: more tone -> higher SVRI)
    comps = {"tau_decay": tau, "diastolic_over_map": dia_map, "aug_index": aix}
    comp_r = {}
    for k, x in comps.items():
        m = np.isfinite(x) & np.isfinite(svri)
        if m.sum() > 10:
            comp_r[k] = round(float(stats.spearmanr(x[m], svri[m])[0]), 4)
    out["component_spearman_vs_svri"] = comp_r
    out["components_directionally_consistent"] = bool(
        sum(1 for r in comp_r.values() if r > 0) >= 2)  # >=2 of 3 positive (more tone->higher SVRI)
    # oriented composite: high = vasoplegic -> NEGATIVE vs SVRI
    idx = -(z(tau) + z(dia_map) + z(aix))
    m = np.isfinite(idx) & np.isfinite(svri)
    idx, sv = idx[m], svri[m]
    nfit = len(sv)
    r_full = float(stats.spearmanr(idx, sv)[0])
    out["index_spearman_full"] = round(r_full, 4)
    out["n"] = int(nfit)
    # jackknife drop-one
    jr = []
    for i in range(nfit):
        mask = np.ones(nfit, bool); mask[i] = False
        jr.append(float(stats.spearmanr(idx[mask], sv[mask])[0]))
    out["jackknife_r_range"] = [round(min(jr), 4), round(max(jr), 4)]
    # drop top-5 most influential (largest jackknife deviation from full)
    infl = np.argsort(np.abs(np.array(jr) - r_full))[-5:]
    mask = np.ones(nfit, bool); mask[infl] = False
    out["r_drop_top5_influential"] = round(float(stats.spearmanr(idx[mask], sv[mask])[0]), 4)
    # bootstrap CI
    rng = np.random.default_rng(SEED)
    bs = [float(stats.spearmanr(idx[ii], sv[ii])[0])
          for ii in (rng.integers(0, nfit, nfit) for _ in range(1000))]
    out["bootstrap_ci"] = [round(float(np.percentile(bs, 2.5)), 4),
                           round(float(np.percentile(bs, 97.5)), 4)]
    robust = (out["bootstrap_ci"][1] < 0 and out["r_drop_top5_influential"] < -0.15
              and out["components_directionally_consistent"])
    out["verdict"] = (
        f"ROBUST -- index r={out['index_spearman_full']} (n={nfit}); bootstrap CI "
        f"{out['bootstrap_ci']} excludes 0; survives dropping top-5 influential "
        f"(r={out['r_drop_top5_influential']}); components directionally consistent "
        f"{out['components_directionally_consistent']}. MODERATE strength, not fragile."
        if robust else
        f"FRAGILE -- index r={out['index_spearman_full']}; bootstrap CI {out['bootstrap_ci']}; "
        f"drop-top5 r={out['r_drop_top5_influential']}; consistent={out['components_directionally_consistent']}.")
    return out


def _write(round_no, payload):
    path = os.path.join(_CACHE, "redteam_ckd_map_results.json")
    allr = {}
    if os.path.exists(path):
        try:
            allr = json.load(open(path))
        except Exception:
            allr = {}
    allr[f"round{round_no}"] = payload
    json.dump(allr, open(path, "w"), indent=2, default=float)
    # doc
    md = os.path.join(_DOCS, "REDTEAM_CKD_MAP.md")
    lines = ["# Red-team: CKD personalized-MAP-target finding (INSPIRE 131k)\n",
             "Adversarial stress-tests. Each round mounts the strongest attack a skeptical "
             "reviewer/biostatistician would make and tests it empirically. SURVIVES = the "
             "finding withstands; WEAKENED/BREAKS = honest downgrade.\n"]
    for rk in sorted(allr):
        p = allr[rk]
        lines.append(f"## {rk}: {p.get('attack','')}\n")
        lines.append("```json")
        lines.append(json.dumps(p, indent=1, default=float)[:2200])
        lines.append("```")
        lines.append(f"**Verdict:** {p.get('verdict','')}\n")
    open(md, "w").write("\n".join(lines) + "\n")


def main():
    rnd = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    df = _load()
    print(f"[redteam] round {rnd}; INSPIRE N={len(df)} (renal-labelable); "
          f"CKD={int((df['ckd']==1).sum())}", flush=True)
    fn = {1: round1, 2: round2, 3: round3, 4: round4}.get(rnd)
    if fn is None:
        print(f"[redteam] round {rnd} not implemented in this module yet.", flush=True)
        return
    payload = fn(df)
    _write(rnd, payload)
    print(f"[redteam] round {rnd} VERDICT: {payload.get('verdict')}", flush=True)
    print(json.dumps(payload, indent=1, default=float)[:1500], flush=True)


if __name__ == "__main__":
    main()
