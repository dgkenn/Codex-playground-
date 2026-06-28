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


def _gcomp_rd(df, expo="HYPO", out="organ_renal"):
    """Covariate-adjusted marginal risk difference + risk ratio via g-computation
    (logistic outcome model, standardise over the stratum's own covariate dist)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    cov = [c for c in COV if c in df.columns]
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
    fn = {1: round1}.get(rnd)
    if fn is None:
        print(f"[redteam] round {rnd} not implemented in this module yet.", flush=True)
        return
    payload = fn(df)
    _write(rnd, payload)
    print(f"[redteam] round {rnd} VERDICT: {payload.get('verdict')}", flush=True)
    print(json.dumps(payload, indent=1, default=float)[:1500], flush=True)


if __name__ == "__main__":
    main()
