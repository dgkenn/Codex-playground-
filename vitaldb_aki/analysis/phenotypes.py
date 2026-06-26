"""phenotypes.py -- Label-free intraoperative fragility-phenotype discovery (VitalDB).

Research question
-----------------
Do intraoperative physiologic patterns form stable subtypes — and if so, which
subtype carries the greatest post-operative organ-injury risk?

Design discipline
-----------------
DISCOVERY FIREWALL: clustering uses ZERO outcome information.  The physiology
feature matrix X is constructed from intraoperative hemodynamic and drug-exposure
signals only.  No composite/organ_*/aki* column may appear in X at any point
during discovery.  The outcome association is computed POST-HOC on a held-out
patient split that was never touched during clustering.

Intended subtypes (hypothesis-generating labels added after discovery):
  - Vasoplegic:        low MAP, high vasopressor requirement
  - Pressure-flow dissociation: MAP-AUC burden + high fluids, minimal response
  - Low-flow:          low UO, high hypotension burden, minimal vasopressor
  - Recovery-lag:      late MAP drop, prolonged surgery duration

Heavy dependencies (numpy, sklearn, scipy, pandas) are lazy-imported inside
functions, following the repo convention in vitaldb_aki/analysis/hypotension_treatment.py.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Intraoperative physiology prefixes to INCLUDE in the clustering matrix.
# These are purely intraoperative hemodynamic and drug-exposure signals.
PHYSIOLOGY_PREFIXES = (
    "map_",          # MAP-based hemodynamic burden features
    "hr_",           # heart-rate features
    "intraop_uo",    # intraoperative urine output (renal perfusion marker)
    "intraop_ebl",   # estimated blood loss (perfusion stress)
    "intraop_crystalloid",  # fluid resuscitation
    "intraop_colloid",
    "intraop_rbc",
    "intraop_ffp",
    "intraop_ppf",   # propofol (depth of anaesthesia marker)
    "intraop_mdz",   # midazolam
    "intraop_ftn",   # fentanyl
    "intraop_eph",   # ephedrine (vasopressor)
    "intraop_phe",   # phenylephrine (vasopressor)
    "intraop_epi",   # epinephrine (vasopressor)
    "intraop_ca",    # calcium (vasopressor adjunct)
    "phe_",          # phenylephrine PK features
    "nepi_",         # norepinephrine PK features
    "epi_",          # epinephrine PK features
    "dopa_",         # dopamine PK features
    "vaso_",         # vasopressin PK features
    "ppf_ce_",       # propofol effect-site concentration features
    "rftn_ce_",      # remifentanil effect-site concentration features
    "mac_hours",     # volatile-agent exposure
    "anesthesia_duration_min",  # case temporal feature
    "pfds_clin_",    # pressure-flow dissociation score (clinical)
    "pfds_wf_",      # pressure-flow dissociation score (waveform)
    "cross_waveform", # cross-waveform correlation features
    "aline_morphology", # arterial-line morphology (aline)
    "art_",          # arterial-waveform features
    "temporal_",     # temporal physiology features
)

# Columns that must NEVER appear in the clustering matrix.
# Any match (full name or prefix) triggers the firewall.
OUTCOME_PATTERNS = (
    "composite",
    "organ_",
    "aki",
    "kdigo",
)

# Columns that are identifiers / administrative (excluded from features).
ID_COLUMNS = {"caseid", "subjectid"}

# Columns that are static preop or demographic (excluded).
STATIC_PREOP_PREFIXES = (
    "age", "sex", "bmi", "asa", "is_emergency", "baseline_cr", "egfr",
    "preop_", "height_cm", "weight_kg", "anemia_flag", "hypoalbuminemia_flag",
    "optype", "department", "surgery_duration_min",
    "map_available", "map_invasive", "pk_available",
)

# Default path config key.
_DEFAULT_CACHE_SUBDIR = "vitaldb_aki/cache"
_FEATURE_MATRIX_FILE = "feature_matrix.csv"
_COMPOSITE_FILE = "cohort_composite.csv"


# ---------------------------------------------------------------------------
# Firewall assertion
# ---------------------------------------------------------------------------

def _assert_no_outcome_in_X(feature_names: list[str]) -> None:
    """Raise ValueError if any outcome column made it into the clustering matrix.

    This is the discovery-phase firewall.  It mirrors the EEG project's
    ``assert_no_outcome_in_loader_fields`` in common/config.py.
    """
    bad = []
    for name in feature_names:
        for pat in OUTCOME_PATTERNS:
            if re.search(pat, name, re.IGNORECASE):
                bad.append(name)
                break
    if bad:
        raise ValueError(
            f"FIREWALL VIOLATION: outcome column(s) detected in clustering matrix: "
            f"{bad!r}.  Clustering must use NO outcome label."
        )


# ---------------------------------------------------------------------------
# 1. load_physiology_matrix
# ---------------------------------------------------------------------------

def load_physiology_matrix(cfg: dict[str, Any]):
    """Load the intraoperative physiology feature matrix for unsupervised clustering.

    Selects ONLY intraoperative physiology features (hemodynamics, drug exposure,
    waveform-derived) and EXCLUDES:
      - outcome labels: composite, organ_*, aki*, kdigo*
      - static preop / demographic features: age, sex, bmi, asa, preop_*, etc.
      - identifier columns: caseid, subjectid

    Imputes missing values with column medians, then standardizes to zero mean /
    unit variance.

    Parameters
    ----------
    cfg : dict
        Must contain ``cache_dir`` key pointing to the directory with
        ``feature_matrix.csv`` (and optionally ``cohort_composite.csv`` for the
        outcome association step).

    Returns
    -------
    tuple[np.ndarray, list[str], pd.DataFrame]
        X_array      -- (n_patients, n_features) float64 scaled array
        feature_names -- list of column names corresponding to X columns
        df_full      -- the full merged DataFrame (with all original columns +
                        composite/organ_renal from cohort_composite.csv if
                        available); used for post-hoc outcome testing.
    """
    import numpy as np
    import pandas as pd
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    cache_dir = cfg.get("cache_dir", _DEFAULT_CACHE_SUBDIR)
    matrix_path = os.path.join(cache_dir, _FEATURE_MATRIX_FILE)
    composite_path = os.path.join(cache_dir, _COMPOSITE_FILE)

    if not os.path.exists(matrix_path):
        raise FileNotFoundError(
            f"Feature matrix not found at {matrix_path!r}.  "
            "Run the pipeline (build_matrix) first or set cfg['cache_dir'] correctly."
        )

    df = pd.read_csv(matrix_path)

    # Optionally merge composite/organ labels (for later outcome testing).
    if os.path.exists(composite_path):
        comp_df = pd.read_csv(composite_path)
        # Keep only caseid + label columns from composite file.
        label_cols = [c for c in comp_df.columns if c == "caseid"
                      or any(re.search(p, c, re.IGNORECASE) for p in OUTCOME_PATTERNS)]
        df = df.merge(comp_df[label_cols], on="caseid", how="left")

    df_full = df.copy()

    # --- Select physiology feature columns ---
    all_cols = list(df.columns)
    physiology_cols = []
    for col in all_cols:
        # Skip identifiers.
        if col in ID_COLUMNS:
            continue
        # Skip outcome columns.
        is_outcome = any(re.search(p, col, re.IGNORECASE) for p in OUTCOME_PATTERNS)
        if is_outcome:
            continue
        # Skip static preop / demographic.
        is_static = any(col.startswith(p) or col == p for p in STATIC_PREOP_PREFIXES)
        if is_static:
            continue
        # Include only physiology prefixes.
        is_physiology = any(col.startswith(p) for p in PHYSIOLOGY_PREFIXES)
        if is_physiology:
            physiology_cols.append(col)

    if not physiology_cols:
        raise RuntimeError(
            "No physiology columns found in the feature matrix.  "
            f"Expected columns with prefixes: {PHYSIOLOGY_PREFIXES}"
        )

    # Firewall: double-check that no outcome leaked through.
    _assert_no_outcome_in_X(physiology_cols)

    # Extract numeric matrix.
    X_df = df[physiology_cols].apply(pd.to_numeric, errors="coerce")

    # Median imputation for missing values.
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X_df)

    # Standardize.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    return X_scaled.astype(np.float64), physiology_cols, df_full


# ---------------------------------------------------------------------------
# 2. discover_phenotypes
# ---------------------------------------------------------------------------

def _remap_labels(ref_labels, target_labels, n_clusters: int):
    """Remap target_labels to maximally align with ref_labels using the Hungarian
    algorithm (linear_sum_assignment).

    Parameters
    ----------
    ref_labels, target_labels : array-like
        Integer cluster labels for the same set of observations.
    n_clusters : int
        Number of clusters (max label + 1).

    Returns
    -------
    np.ndarray
        target_labels remapped so that the global assignment is optimal.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    ref = np.asarray(ref_labels, dtype=int)
    tgt = np.asarray(target_labels, dtype=int)
    # Build cost matrix: entry (i,j) = number of points where ref==i, tgt==j.
    cost = np.zeros((n_clusters, n_clusters), dtype=int)
    for ri in range(n_clusters):
        for ti in range(n_clusters):
            cost[ri, ti] = int(np.sum((ref == ri) & (tgt == ti)))
    # Maximise agreement = minimise negative cost.
    row_ind, col_ind = linear_sum_assignment(-cost)
    mapping = {col_ind[r]: row_ind[r] for r in range(len(row_ind))}
    remapped = np.array([mapping.get(t, t) for t in tgt], dtype=int)
    return remapped


def discover_phenotypes(
    X,
    k_range=range(2, 8),
    seed: int = 42,
    n_bootstrap: int = 30,
    subsample_frac: float = 0.80,
) -> tuple[dict[int, dict], int]:
    """Consensus clustering to discover stable intraoperative physiology subtypes.

    Algorithm (mirrors EEG project's consensus_pac / stability_score pattern):
      1. For each candidate k in k_range:
         a. Run n_bootstrap bootstrap resamples (subsample rows without replacement).
         b. Fit KMeans on each subsample.
         c. For each pair of bootstrap runs, compute ARI between their predictions
            on the INTERSECTION of their subsampled rows (remapped via Hungarian
            algorithm so label permutations do not penalise ARI).
         d. Stability = mean pairwise ARI across all pairs.
      2. Best k = highest mean pairwise ARI; ties broken by smaller k (parsimony).

    Parameters
    ----------
    X : array-like, shape (n, p)
        Standardized physiology feature matrix.  Must NOT contain outcome columns.
    k_range : iterable[int]
        Candidate number of clusters to try.
    seed : int
        Random seed for reproducibility.
    n_bootstrap : int
        Number of bootstrap subsamples per k.
    subsample_frac : float
        Fraction of rows in each bootstrap subsample.

    Returns
    -------
    tuple[dict[int, dict], int]
        results_by_k : dict mapping k -> {"labels": np.ndarray, "stability": float}
            ``labels`` are from the full-data KMeans fit for that k.
        best_k : int
            The k selected by max stability (ties -> smaller k).
    """
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score

    X = np.asarray(X, dtype="float64")
    n = X.shape[0]
    k_list = sorted(set(k_range))
    rng = np.random.default_rng(seed)

    results_by_k: dict[int, dict] = {}

    for k in k_list:
        # Full-data fit for final labels.
        km_full = KMeans(n_clusters=k, random_state=seed, n_init=10)
        full_labels = km_full.fit_predict(X)

        # Bootstrap stability.
        subsample_size = max(k + 1, int(subsample_frac * n))
        boot_results = []  # list of (indices, labels) per bootstrap

        for _ in range(n_bootstrap):
            idx = rng.choice(n, size=subsample_size, replace=False)
            km_b = KMeans(
                n_clusters=k,
                random_state=int(rng.integers(1 << 30)),
                n_init=5,
            )
            lab_b = km_b.fit_predict(X[idx])
            boot_results.append((idx, lab_b))

        # Pairwise ARI on the intersection of each pair of bootstrap samples.
        ari_scores = []
        for i in range(len(boot_results)):
            for j in range(i + 1, len(boot_results)):
                idx_i, lab_i = boot_results[i]
                idx_j, lab_j = boot_results[j]
                # Intersection of the two subsample index sets.
                common_idx = np.intersect1d(idx_i, idx_j)
                if len(common_idx) < k:
                    # Not enough shared points to compute meaningful ARI.
                    continue
                # Map common indices back to positions within each subsample.
                pos_i = np.searchsorted(np.sort(idx_i), common_idx)
                pos_j = np.searchsorted(np.sort(idx_j), common_idx)
                # Remap labels (Hungarian) before ARI to remove permutation bias.
                lab_i_sorted = lab_i[np.argsort(idx_i)][pos_i]
                lab_j_sorted = lab_j[np.argsort(idx_j)][pos_j]
                lab_j_remapped = _remap_labels(lab_i_sorted, lab_j_sorted, k)
                ari = float(adjusted_rand_score(lab_i_sorted, lab_j_remapped))
                ari_scores.append(ari)

        stability = float(np.mean(ari_scores)) if ari_scores else 0.0

        results_by_k[k] = {
            "labels": full_labels,
            "stability": stability,
        }

    # Select best k: highest stability; ties -> smallest k.
    best_k = max(k_list, key=lambda k: (results_by_k[k]["stability"], -k))
    # Re-break ties by parsimony (if multiple k share the same stability).
    best_stability = results_by_k[best_k]["stability"]
    candidates_at_best = [k for k in k_list
                          if results_by_k[k]["stability"] == best_stability]
    best_k = min(candidates_at_best)  # parsimony: smallest k wins ties

    return results_by_k, best_k


# ---------------------------------------------------------------------------
# 3. characterize
# ---------------------------------------------------------------------------

def characterize(
    X,
    labels,
    feature_names: list[str],
    n_top: int = 5,
) -> dict[str, Any]:
    """Compute per-cluster standardized physiology profiles.

    For each cluster, identify which features are highest/lowest relative to the
    overall population mean (i.e., the standardized mean deviation for that
    cluster).

    Produces human-readable subtype descriptions from dominant features, mapping
    known feature patterns to clinical subtype hypotheses (e.g., vasoplegic,
    pressure-flow dissociation, low-flow, recovery-lag).

    Parameters
    ----------
    X : array-like, shape (n, p)
        Standardized physiology feature matrix (same as fed to clustering).
    labels : array-like, shape (n,)
        Cluster labels from discover_phenotypes (full-data fit).
    feature_names : list[str]
        Names for the p columns of X.
    n_top : int
        Number of top distinguishing features to report per cluster.

    Returns
    -------
    dict
        {
            "n_clusters": int,
            "feature_names": list[str],
            "phenotypes": {
                cluster_id (str): {
                    "n": int,
                    "pct": float,
                    "mean_profile": list[float],  # mean standardized feature value
                    "top_high": list[str],         # features highest vs population
                    "top_low": list[str],          # features lowest vs population
                    "subtype_hint": str,           # interpretive label
                }
            }
        }
    """
    import numpy as np

    X = np.asarray(X, dtype="float64")
    labels = np.asarray(labels, dtype=int)
    n, p = X.shape
    n_clusters = int(labels.max()) + 1

    # Global population mean (X is already standardized so ~0).
    pop_mean = X.mean(axis=0)

    phenotypes = {}
    for c in range(n_clusters):
        mask = labels == c
        Xc = X[mask]
        cluster_mean = Xc.mean(axis=0)
        delta = cluster_mean - pop_mean  # deviation from population mean

        # Top features elevated in this cluster.
        high_idx = np.argsort(delta)[::-1][:n_top]
        low_idx = np.argsort(delta)[:n_top]
        top_high = [feature_names[i] for i in high_idx]
        top_low = [feature_names[i] for i in low_idx]

        # Human-readable subtype hint based on dominant features.
        subtype_hint = _infer_subtype_hint(delta, feature_names)

        phenotypes[str(c)] = {
            "n": int(mask.sum()),
            "pct": round(float(mask.mean()) * 100, 1),
            "mean_profile": [round(float(v), 4) for v in cluster_mean],
            "top_high": top_high,
            "top_low": top_low,
            "subtype_hint": subtype_hint,
        }

    return {
        "n_clusters": n_clusters,
        "feature_names": feature_names,
        "phenotypes": phenotypes,
    }


def _infer_subtype_hint(delta, feature_names: list[str]) -> str:
    """Heuristic mapping of dominant feature deviations to a clinical subtype.

    Rules (applied in priority order):
      1. High vasopressor dose + low MAP burden -> Vasoplegic (treated/responsive)
      2. High MAP burden + high fluids + low vasopressor response -> Pressure-flow
         dissociation
      3. High MAP burden + low UO + low vasopressor -> Low-flow
      4. High anesthesia duration + late MAP drop -> Recovery-lag
      5. Otherwise -> Unclassified

    These are hypothesis-generating labels added AFTER discovery.
    """
    import numpy as np

    d = {feature_names[i]: delta[i] for i in range(len(feature_names))}

    def _score(prefix: str) -> float:
        vals = [v for k, v in d.items() if k.startswith(prefix)]
        return float(np.mean(vals)) if vals else 0.0

    vaso_score = _score("phe_") + _score("nepi_") + _score("epi_") + \
        _score("intraop_eph") + _score("intraop_phe") + _score("intraop_epi")
    map_burden = _score("map_auc_below") + _score("map_min_below") + _score("map_frac")
    uo_score = _score("intraop_uo")
    fluid_score = _score("intraop_crystalloid") + _score("intraop_colloid")
    dur_score = _score("anesthesia_duration")

    if vaso_score > 0.3 and map_burden < 0.1:
        return "vasoplegic (treated, MAP-maintained by vasopressors)"
    elif map_burden > 0.3 and fluid_score > 0.2 and vaso_score < 0.1:
        return "pressure-flow dissociation (hypotension + fluids, vasopressor-sparse)"
    elif map_burden > 0.3 and uo_score < -0.2 and vaso_score < 0.0:
        return "low-flow (hypotension + oliguria, minimal vasopressor)"
    elif dur_score > 0.3 and map_burden > 0.1:
        return "recovery-lag (prolonged case with late MAP decline)"
    else:
        return "unclassified intraoperative phenotype"


# ---------------------------------------------------------------------------
# 4. phenotype_outcome_association
# ---------------------------------------------------------------------------

def phenotype_outcome_association(
    df_full,
    labels,
    cfg: dict[str, Any],
    outcome_col: str = "composite",
    organ_col: str = "organ_renal",
    subject_col: str = "subjectid",
    holdout_frac: float = 0.50,
    seed: int = 42,
) -> dict[str, Any]:
    """POST-HOC outcome association on a held-out patient split.

    This function is called AFTER clustering is complete and frozen.  It tests
    whether the discovered phenotypes differ in their composite organ-injury and
    renal-injury rates.

    Patient-level split: subjects are split 50/50 by subjectid (not row-level),
    so that each patient appears in only one half.  The analysis is run on the
    held-out half; replicated on the discovery half as a consistency check.

    Statistical tests:
      - Chi-square test (or Fisher's exact test for cells < 5) of phenotype x
        outcome across clusters.
      - Rate ratio: highest-risk cluster vs all others (prospective comparison).
      - Replication check: same direction in both halves.

    Parameters
    ----------
    df_full : pd.DataFrame
        The full DataFrame returned by load_physiology_matrix (all columns),
        with rows in the same order as the clustering labels.
    labels : array-like, shape (n,)
        Cluster labels aligned to df_full rows.
    cfg : dict
        Config dict (used for seed override if present).
    outcome_col : str
        Primary outcome column (default: "composite").
    organ_col : str
        Secondary organ-injury outcome (default: "organ_renal").
    subject_col : str
        Patient-level identifier column.
    holdout_frac : float
        Fraction of subjects to hold out.
    seed : int
        Random seed for the split.

    Returns
    -------
    dict
        Full results including per-cluster rates, chi-square p-values, rate ratios,
        and replication flag.
    """
    import numpy as np
    import pandas as pd
    from scipy import stats

    rng = np.random.default_rng(cfg.get("seed", seed))

    df = df_full.copy()
    df["_phenotype"] = labels

    # Check that the required outcome column exists.
    for col in (outcome_col, organ_col):
        if col not in df.columns:
            df[col] = np.nan  # graceful degradation

    # Patient-level split on unique subjects.
    all_subjects = df[subject_col].dropna().unique()
    n_subjects = len(all_subjects)
    n_holdout = max(1, int(holdout_frac * n_subjects))
    shuffled = rng.permutation(all_subjects)
    holdout_subjects = set(shuffled[:n_holdout])
    discovery_subjects = set(shuffled[n_holdout:])

    holdout_mask = df[subject_col].isin(holdout_subjects)
    discovery_mask = df[subject_col].isin(discovery_subjects)

    def _run_association(mask, split_name: str) -> dict:
        sub = df[mask].copy()
        n_total = len(sub)
        if n_total == 0:
            return {"split": split_name, "n": 0, "error": "empty split"}

        results_per_outcome = {}
        for oc in (outcome_col, organ_col):
            outcome_vals = pd.to_numeric(sub[oc], errors="coerce")
            valid = outcome_vals.notna()
            sub_valid = sub[valid].copy()
            out_valid = outcome_vals[valid]

            if len(sub_valid) == 0 or out_valid.sum() == 0:
                results_per_outcome[oc] = {"error": "no events or no valid rows"}
                continue

            # Per-cluster event rate.
            cluster_ids = sorted(sub_valid["_phenotype"].unique())
            per_cluster = {}
            for c in cluster_ids:
                cm = sub_valid["_phenotype"] == c
                nc = int(cm.sum())
                ec = int(out_valid[cm].sum())
                per_cluster[str(c)] = {
                    "n": nc,
                    "events": ec,
                    "rate": round(ec / nc, 4) if nc > 0 else None,
                }

            # Chi-square / Fisher test across clusters.
            contingency = np.array([
                [per_cluster[str(c)]["events"],
                 per_cluster[str(c)]["n"] - per_cluster[str(c)]["events"]]
                for c in cluster_ids
            ])
            min_expected = (contingency.sum(axis=1, keepdims=True) *
                            contingency.sum(axis=0, keepdims=True) /
                            contingency.sum())
            if min_expected.min() < 5 or len(cluster_ids) == 2:
                # Use Fisher's exact for 2x2 or sparse tables.
                if contingency.shape[0] == 2:
                    _, pval = stats.fisher_exact(contingency)
                    test_name = "fisher_exact"
                else:
                    chi2, pval, _, _ = stats.chi2_contingency(contingency)
                    test_name = "chi2"
            else:
                chi2, pval, _, _ = stats.chi2_contingency(contingency)
                test_name = "chi2"

            # Rate ratio: highest-rate cluster vs all others.
            rates = {c: per_cluster[str(c)]["rate"] or 0.0 for c in cluster_ids}
            highest_c = max(rates, key=rates.get)
            hr_events = per_cluster[str(highest_c)]["events"]
            hr_n = per_cluster[str(highest_c)]["n"]
            rest_events = sum(per_cluster[str(c)]["events"] for c in cluster_ids
                              if c != highest_c)
            rest_n = sum(per_cluster[str(c)]["n"] for c in cluster_ids
                         if c != highest_c)
            rate_high = hr_events / hr_n if hr_n > 0 else 0.0
            rate_rest = rest_events / rest_n if rest_n > 0 else 0.0
            rate_ratio = (rate_high / rate_rest
                          if rate_rest > 0
                          else float("inf") if rate_high > 0 else 1.0)

            results_per_outcome[oc] = {
                "per_cluster": per_cluster,
                "test": test_name,
                "p_value": round(float(pval), 6),
                "highest_risk_cluster": str(highest_c),
                "rate_high": round(rate_high, 4),
                "rate_rest": round(rate_rest, 4),
                "rate_ratio": round(rate_ratio, 4),
                "n_valid": int(len(sub_valid)),
                "n_events": int(out_valid.sum()),
            }

        return {
            "split": split_name,
            "n": n_total,
            "outcomes": results_per_outcome,
        }

    holdout_result = _run_association(holdout_mask, "holdout")
    discovery_result = _run_association(discovery_mask, "discovery")

    # Replication: same highest-risk cluster in both halves?
    def _highest_cluster(result, oc):
        try:
            return result["outcomes"][oc]["highest_risk_cluster"]
        except (KeyError, TypeError):
            return None

    replication = {}
    for oc in (outcome_col, organ_col):
        hh = _highest_cluster(holdout_result, oc)
        dh = _highest_cluster(discovery_result, oc)
        replication[oc] = {
            "holdout_highest_risk": hh,
            "discovery_highest_risk": dh,
            "replicated": hh == dh if (hh is not None and dh is not None) else None,
        }

    return {
        "n_subjects": int(n_subjects),
        "n_holdout": int(n_holdout),
        "n_discovery": int(n_subjects - n_holdout),
        "holdout": holdout_result,
        "discovery": discovery_result,
        "replication": replication,
    }


# ---------------------------------------------------------------------------
# 5. run_phenotype_analysis
# ---------------------------------------------------------------------------

def run_phenotype_analysis(cfg: dict[str, Any]) -> dict[str, Any]:
    """Orchestrator: load matrix → discover → characterize → outcome association.

    Writes:
      - cache_dir/phenotypes_results.json
      - vitaldb_aki/docs/PHENOTYPES.md

    Returns
    -------
    dict
        Full results dictionary.
    """
    cache_dir = cfg.get("cache_dir", _DEFAULT_CACHE_SUBDIR)
    seed = cfg.get("seed", 42)

    # 1. Load physiology matrix (discovery firewall is enforced inside).
    print("[phenotypes] Loading physiology matrix...")
    X, feature_names, df_full = load_physiology_matrix(cfg)
    print(f"[phenotypes] Matrix shape: {X.shape}  features: {len(feature_names)}")
    print(f"[phenotypes] Features: {feature_names}")

    # 2. Discover phenotypes.
    print("[phenotypes] Running consensus clustering...")
    results_by_k, best_k = discover_phenotypes(
        X, k_range=range(2, 8), seed=seed
    )
    labels = results_by_k[best_k]["labels"]
    stability = results_by_k[best_k]["stability"]
    print(f"[phenotypes] Best k={best_k}  stability(ARI)={stability:.3f}")

    # 3. Characterize clusters.
    print("[phenotypes] Characterizing phenotypes...")
    char = characterize(X, labels, feature_names)

    for cid, info in char["phenotypes"].items():
        print(
            f"  Cluster {cid}: n={info['n']} ({info['pct']}%)  "
            f"hint={info['subtype_hint']!r}"
        )
        print(f"    top_high={info['top_high'][:3]}")
        print(f"    top_low={info['top_low'][:3]}")

    # 4. Post-hoc outcome association.
    print("[phenotypes] Running post-hoc outcome association...")
    assoc = phenotype_outcome_association(df_full, labels, cfg, seed=seed)

    # 5. Assemble full results.
    stability_all = {str(k): v["stability"] for k, v in results_by_k.items()}
    results = {
        "n_patients": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "best_k": int(best_k),
        "stability_by_k": stability_all,
        "best_k_stability": float(stability),
        "characterization": char,
        "outcome_association": assoc,
    }

    # 6. Write JSON results.
    os.makedirs(cache_dir, exist_ok=True)
    results_path = os.path.join(cache_dir, "phenotypes_results.json")
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[phenotypes] Results written to {results_path}")

    # 7. Write PHENOTYPES.md report.
    _write_phenotypes_md(results, cfg)

    return results


def _write_phenotypes_md(results: dict, cfg: dict) -> str:
    """Write a human-readable PHENOTYPES.md report.

    Placed at vitaldb_aki/docs/PHENOTYPES.md relative to the cache_dir parent.
    """
    cache_dir = cfg.get("cache_dir", _DEFAULT_CACHE_SUBDIR)
    # Resolve docs/ dir relative to the vitaldb_aki package root.
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "PHENOTYPES.md")

    best_k = results["best_k"]
    stability = results["best_k_stability"]
    char = results["characterization"]
    assoc = results.get("outcome_association", {})

    lines = [
        "# VitalDB Intraoperative Fragility-Phenotype Discovery",
        "",
        "## Overview",
        "",
        "Label-free unsupervised discovery of intraoperative physiology subtypes.",
        "Clustering used ZERO outcome information (discovery firewall enforced).",
        "Outcome association is post-hoc on a held-out patient split.",
        "",
        f"- **Patients analysed:** {results['n_patients']}",
        f"- **Features used:** {results['n_features']}",
        f"- **Best k (phenotypes):** {best_k}",
        f"- **Stability (mean pairwise ARI):** {stability:.3f}",
        "",
        "## Stability by k",
        "",
        "| k | Mean pairwise ARI |",
        "|---|-------------------|",
    ]
    for k, s in sorted(results["stability_by_k"].items(), key=lambda x: int(x[0])):
        marker = " **(best)**" if int(k) == best_k else ""
        lines.append(f"| {k} | {float(s):.3f}{marker} |")

    lines += [
        "",
        "## Phenotype Profiles",
        "",
        "Features are standardised (z-score relative to population mean).",
        "",
    ]

    for cid, info in sorted(char["phenotypes"].items(), key=lambda x: int(x[0])):
        lines += [
            f"### Cluster {cid} — {info['subtype_hint']}",
            f"- **n = {info['n']}** ({info['pct']}% of cohort)",
            f"- Top elevated features: {', '.join(info['top_high'][:5])}",
            f"- Top suppressed features: {', '.join(info['top_low'][:5])}",
            "",
        ]

    lines += [
        "## Post-hoc Outcome Association (held-out patient split)",
        "",
        "(50/50 patient-level split; highest-risk cluster vs rest)",
        "",
    ]

    for oc in ("composite", "organ_renal"):
        try:
            ho = assoc["holdout"]["outcomes"][oc]
            lines += [
                f"### {oc}",
                f"- Holdout n_valid={ho['n_valid']}, events={ho['n_events']}",
                f"- p-value ({ho['test']}): {ho['p_value']}",
                f"- Highest-risk cluster: {ho['highest_risk_cluster']}",
                f"- Rate ratio (highest vs rest): {ho['rate_ratio']}",
            ]
            rep = assoc["replication"].get(oc, {})
            lines.append(
                f"- Replication in discovery half: "
                f"{'YES' if rep.get('replicated') else 'NO/unknown'}"
            )
            lines.append("")
        except (KeyError, TypeError):
            lines += [f"### {oc}", "- Not available", ""]

    lines += [
        "## Feature List (intraoperative physiology only)",
        "",
        ", ".join(results["feature_names"]),
        "",
        "---",
        "*Generated by vitaldb_aki/analysis/phenotypes.py*",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"[phenotypes] PHENOTYPES.md written to {md_path}")
    return md_path


def _json_default(obj):
    """Fallback JSON serializer for numpy types."""
    import math
    import numpy as np

    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")
