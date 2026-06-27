"""phenotype_v2.py -- redesigned phenotyping to address the diagnostics findings:
  (1) MAP-threshold sweep: which hypotension threshold/metric best predicts AKI.
  (2) De-redundify collinear features (corr-prune) so hypotension stops dominating
      by sheer feature count.
  (3) Insult-residualize: regress each physiology feature on surgical-magnitude
      covariates (duration, EBL, age, ASA, optype) and cluster on the RESIDUALS,
      so the phenotype captures excess physiology FOR a given operation -- the
      modifiable part -- not just "who had a big surgery".

Run: python3 -u vitaldb_aki/analysis/phenotype_v2.py   (prints a report; no writes)
Fast KMeans labels (the consensus solution is already known-stable).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

INSULT_COVARIATES = ["age", "asa", "anesthesia_duration_min", "intraop_ebl"]
CORR_PRUNE_THRESHOLD = 0.85


def _auroc(y, x):
    from sklearn.metrics import roc_auc_score
    import numpy as np
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 30 or len(set(y[m])) < 2:
        return float("nan")
    a = roc_auc_score(y[m], x[m])
    return max(a, 1 - a)


def map_threshold_sweep(cfg):
    import numpy as np
    import pandas as pd
    cdir = cfg.get("cache_dir") or cfg["data"]["cache_dir"]
    df = pd.read_csv(os.path.join(cdir, "feature_matrix.csv"))
    print("\n=== (1) MAP THRESHOLD / METRIC SWEEP: univariate AUROC vs outcome ===")
    print("    (which definition of intraop hypotension best discriminates injury?)")
    cand = [c for c in df.columns if c.startswith("map_") and ("below" in c or "rel_drop" in c or c in ("map_lowest", "map_sd"))]
    for outcome in ("organ_renal", "composite"):
        if outcome not in df.columns:
            continue
        y = pd.to_numeric(df[outcome], errors="coerce").to_numpy(dtype=float)
        rows = []
        for c in cand:
            x = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
            rows.append((c, _auroc(y, x)))
        rows = [r for r in rows if not np.isnan(r[1])]
        rows.sort(key=lambda r: -r[1])
        print(f"\n  -- {outcome} (events={int(np.nansum(y))}) top discriminating hypotension metrics --")
        for c, a in rows[:10]:
            print(f"     AUROC={a:.3f}  {c}")


def _corr_prune(X, names, thr):
    """Greedy: keep a feature unless |corr| >= thr with an already-kept one."""
    import numpy as np
    keep, kept_idx = [], []
    C = np.corrcoef(X.T)
    for j in range(X.shape[1]):
        red = any(abs(C[j, k]) >= thr for k in kept_idx)
        if not red:
            kept_idx.append(j); keep.append(names[j])
    return kept_idx, keep


def residualized_declustering(cfg):
    import numpy as np
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score
    from vitaldb_aki.analysis.phenotypes import load_physiology_matrix

    seed = cfg.get("seed", 42)
    X, names, df_full = load_physiology_matrix(cfg)
    names = list(names)
    n = X.shape[0]

    # insult covariates (from df_full; optype -> integer code)
    cov = []
    for c in INSULT_COVARIATES:
        if c in df_full.columns:
            cov.append(pd.to_numeric(df_full[c], errors="coerce").to_numpy(dtype=float))
    if "optype" in df_full.columns:
        cov.append(df_full["optype"].astype("category").cat.codes.to_numpy(dtype=float))
    Z = np.column_stack(cov)
    # median-impute covariates
    for j in range(Z.shape[1]):
        col = Z[:, j]; col[np.isnan(col)] = np.nanmedian(col); Z[:, j] = col

    # drop surgical-insult markers from the clustering features (treat as insult, not phenotype)
    drop = {"anesthesia_duration_min", "intraop_ebl"}
    cfeat = [i for i, nm in enumerate(names) if nm not in drop]
    Xc = X[:, cfeat]; cnames = [names[i] for i in cfeat]

    # (2) de-redundify
    kept_idx, kept = _corr_prune(Xc, cnames, CORR_PRUNE_THRESHOLD)
    Xk = Xc[:, kept_idx]
    print(f"\n=== (2) DE-REDUNDIFY: {Xc.shape[1]} -> {len(kept)} features "
          f"(|corr|>={CORR_PRUNE_THRESHOLD} pruned) ===")
    print("    kept (representative axes): " + ", ".join(kept[:18]) + (" ..." if len(kept) > 18 else ""))

    # (3) insult-residualize each kept feature on Z, cluster on residuals
    resid = np.empty_like(Xk)
    for j in range(Xk.shape[1]):
        lr = LinearRegression().fit(Z, Xk[:, j])
        resid[:, j] = Xk[:, j] - lr.predict(Z)
    Rz = StandardScaler().fit_transform(resid)
    print(f"\n=== (3) INSULT-RESIDUALIZED CLUSTERING (covariates: "
          f"{INSULT_COVARIATES}+optype) ===")

    labels = KMeans(n_clusters=2, n_init=10, random_state=seed).fit_predict(Rz)

    # high-risk cluster = higher organ_renal rate
    def rate(col, mask):
        v = pd.to_numeric(df_full[col], errors="coerce").to_numpy(dtype=float)
        m = mask & ~np.isnan(v)
        return v[m].mean() if m.any() else float("nan"), int(np.nansum(v[m]))
    ren = pd.to_numeric(df_full.get("organ_renal"), errors="coerce").to_numpy(dtype=float)
    r0 = np.nanmean(ren[labels == 0]); r1 = np.nanmean(ren[labels == 1])
    hi = 0 if (r0 or 0) >= (r1 or 0) else 1
    clhi = (labels == hi)
    print(f"  cluster sizes={np.bincount(labels).tolist()}  high-risk=cluster{hi} (n={int(clhi.sum())})")

    for oc in ("organ_renal", "composite"):
        if oc not in df_full.columns:
            continue
        rh, eh = rate(oc, clhi); rl, el = rate(oc, ~clhi)
        rr = (rh / rl) if rl else float("nan")
        print(f"  {oc:12s}: high-risk={rh:.3f} ({eh} ev) vs rest={rl:.3f} ({el} ev)  RR={rr:.2f}")

    # what separates the residualized cluster now? (is it still hypotension, or new axes?)
    disc = []
    for j, nm in enumerate(kept):
        smd = Rz[clhi, j].mean() - Rz[~clhi, j].mean()
        disc.append((nm, smd))
    disc.sort(key=lambda t: -abs(t[1]))
    print("\n  top features separating the INSULT-ADJUSTED high-risk cluster:")
    for nm, smd in disc[:12]:
        print(f"     {smd:+.2f}  {nm}")

    # residual confounding check: is it STILL just big surgery?
    print("\n  case-mix after residualization (should be attenuated vs raw):")
    for col in ("anesthesia_duration_min", "intraop_ebl", "age", "asa"):
        if col in df_full.columns:
            v = pd.to_numeric(df_full[col], errors="coerce").to_numpy(dtype=float)
            print(f"     {col:24s} high-risk={np.nanmean(v[clhi]):8.1f}  rest={np.nanmean(v[~clhi]):8.1f}")


def main():
    from common.config import load_yaml
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cfg.setdefault("cache_dir", os.path.join(_ROOT, "vitaldb_aki", "cache"))
    map_threshold_sweep(cfg)
    residualized_declustering(cfg)


if __name__ == "__main__":
    main()
