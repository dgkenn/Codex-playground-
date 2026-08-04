"""cluster_diagnostics.py -- what is the confirmatory phenotype clustering actually
picking up? Run: python3 vitaldb_aki/analysis/cluster_diagnostics.py

Reports: feature-block composition (redundancy), PCA structure (is it 1-D?),
per-feature cluster discrimination, a hypotension-axis test, case-mix confounding,
and higher-k substructure. No writes -- prints a report for human inspection.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main():
    import numpy as np
    import pandas as pd
    from common.config import load_yaml
    from vitaldb_aki.analysis.phenotypes import load_physiology_matrix, discover_phenotypes

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cfg.setdefault("cache_dir", os.path.join(_ROOT, "vitaldb_aki", "cache"))
    seed = cfg.get("seed", 42)

    X, names, df_full = load_physiology_matrix(cfg)
    names = list(names)
    n, p = X.shape
    print(f"\n=== MATRIX: {n} cases x {p} features ===")

    # --- 1. feature-block composition (redundancy) ---
    def block(nm):
        if nm.startswith("map_"): return "MAP/hypotension"
        if nm.startswith("hr_"): return "heart-rate"
        if nm.startswith(("ppf_", "rftn_", "mac")): return "anesthetic/drug-Ce"
        if nm.startswith(("phe_", "nepi_", "epi_", "dopa_", "vaso")): return "vasopressor"
        if nm.startswith("intraop_"): return "fluids/transfusion/EBL"
        if nm.startswith("pfds_"): return "PFDS biomarkers"
        if nm.startswith(("temporal", "anesthesia")): return "temporal/duration"
        return "other"
    from collections import Counter
    blocks = Counter(block(nm) for nm in names)
    print("\n--- feature-block composition (count drives clustering weight) ---")
    for b, c in blocks.most_common():
        print(f"  {c:3d}  {b}")

    # --- regenerate labels -- fast KMeans(k=2); the consensus solution is already
    # known-stable at ARI 0.88, so we only need the assignment to dissect the split.
    from sklearn.cluster import KMeans
    best_k = 2
    labels = KMeans(n_clusters=best_k, n_init=10, random_state=seed).fit_predict(X)
    print(f"\n=== CLUSTERING: k={best_k}  sizes={np.bincount(labels).tolist()} ===", flush=True)

    # --- 2. PCA: is the split 1-dimensional? ---
    from sklearn.decomposition import PCA
    pca = PCA(n_components=min(8, p)).fit(X)
    evr = pca.explained_variance_ratio_
    print("\n--- PCA variance explained ---")
    print("  PC1..PC5: " + ", ".join(f"{v:.1%}" for v in evr[:5]) +
          f"   (cum5={evr[:5].sum():.1%})")
    pc1 = X @ pca.components_[0]
    # which features load PC1
    load1 = sorted(zip(names, pca.components_[0]), key=lambda kv: -abs(kv[1]))[:8]
    print("  PC1 top loadings: " + ", ".join(f"{nm}({w:+.2f})" for nm, w in load1))

    # correlation of cluster membership with PC1 (point-biserial)
    hi = int(np.argmax([labels[labels == c].size and
                        df_full.loc[labels == c, "composite"].apply(pd.to_numeric, errors="coerce").mean()
                        for c in range(best_k)]))
    cl_hi = (labels == hi).astype(float)
    r_pc1 = np.corrcoef(cl_hi, pc1)[0, 1]
    print(f"  corr(high-risk cluster, PC1) = {r_pc1:+.3f}   (|r|->1 means the split IS PC1)")

    # --- 3. hypotension-axis test ---
    hypo_cols = [i for i, nm in enumerate(names) if nm.startswith("map_") and "below" in nm]
    if hypo_cols:
        hypo_score = X[:, hypo_cols].mean(axis=1)  # mean z of hypotension-burden features
        r_hypo = np.corrcoef(cl_hi, hypo_score)[0, 1]
        r_hypo_pc1 = np.corrcoef(hypo_score, pc1)[0, 1]
        print(f"\n--- hypotension-axis test ({len(hypo_cols)} MAP-below features) ---")
        print(f"  corr(high-risk cluster, hypotension-burden score) = {r_hypo:+.3f}")
        print(f"  corr(hypotension-burden score, PC1)               = {r_hypo_pc1:+.3f}")

    # --- 4. per-feature discrimination (cluster hi vs rest) ---
    from sklearn.metrics import roc_auc_score
    disc = []
    for i, nm in enumerate(names):
        smd = X[cl_hi == 1, i].mean() - X[cl_hi == 0, i].mean()
        try:
            auc = roc_auc_score(cl_hi, X[:, i])
        except Exception:
            auc = float("nan")
        disc.append((nm, smd, max(auc, 1 - auc)))
    disc.sort(key=lambda t: -abs(t[1]))
    print("\n--- top features separating the high-risk cluster (std mean diff | uni-AUC) ---")
    for nm, smd, auc in disc[:12]:
        print(f"  {smd:+.2f}  AUC={auc:.2f}  {nm}")

    # --- 5. case-mix confounding ---
    print("\n--- case-mix by cluster (confounding check) ---")
    for col in ("age", "asa", "anesthesia_duration_min", "intraop_ebl"):
        if col in df_full.columns:
            v = pd.to_numeric(df_full[col], errors="coerce")
            m_hi, m_lo = v[cl_hi == 1].mean(), v[cl_hi == 0].mean()
            print(f"  {col:24s} high-risk={m_hi:8.1f}   rest={m_lo:8.1f}")
    if "optype" in df_full.columns:
        top_hi = df_full.loc[cl_hi == 1, "optype"].value_counts(normalize=True).head(3)
        print("  top optypes in high-risk cluster: " +
              ", ".join(f"{k} {v:.0%}" for k, v in top_hi.items()))

    # --- 6. higher-k substructure (does anything beyond hypotension emerge?) ---
    from sklearn.metrics import silhouette_score
    print("\n--- sizes + silhouette by k (substructure beyond k=2?) ---")
    for k in range(2, 6):
        lab = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
        try:
            sil = silhouette_score(X, lab, sample_size=min(2000, n), random_state=seed)
        except Exception:
            sil = float("nan")
        print(f"  k={k}  silhouette={sil:.3f}  sizes={np.bincount(lab).tolist()}", flush=True)


if __name__ == "__main__":
    main()
