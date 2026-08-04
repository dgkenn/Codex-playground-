"""discovery_screen.py -- EXPLORATORY discovery analysis (stages 2-3).

Runs AFTER the enriched matrix (cache/feature_matrix_enriched.csv) is built by
discovery_run.build_enriched_matrix. Two analyses, both EXPLORATORY (kept fully
separate from the frozen confirmatory pipeline so confirmatory integrity holds):

(A) Per-family x per-outcome INCREMENTAL-VALUE SCREEN
    Does each of the 16 DISCOVERY families add discrimination OVER the
    confirmatory comprehensive baseline, for the composite primary + 7 per-organ
    secondaries? For each (family x outcome) we evaluate, on an AVAILABILITY-aware
    subset (rows where that family's `<prefix>_available` flag == 1), the
    confirmatory comprehensive baseline vs baseline+family for BOTH model classes
    (logreg, gbm), reusing the nested-CV harness machinery (run.py / dataset.py).
    Baseline and baseline+family share the SAME outer/inner folds, so their
    out-of-fold (OOF) probability vectors are paired and DeLong (metrics.py) gives
    a correlated-ROC p-value for ΔAUROC. Cells with < 15 events or < 100 rows are
    flagged UNDERPOWERED and NOT fit. BH-FDR is applied across the full grid of
    computed p-values; q<0.05 AND ΔAUROC>0 -> "hit".

(B) Enriched PHENOTYPE discovery (availability-aware)
    Do richer features yield phenotypes that stratify outcome BEYOND the
    confirmatory hypotension phenotype? CRITICAL anti-artifact rule: clustering on
    sparse-monitor features (EEG, advanced-hemo, CVP) would manufacture a
    "has-monitor vs not" cluster (monitor placement is confounded with case
    severity). So we cluster ONLY on WIDELY-AVAILABLE features: the confirmatory
    physiology features PLUS discovery families whose `_available` flag is 1 in
    >= 80% of the cohort. Low-coverage families are DROPPED and listed. We reuse
    phenotypes.discover_phenotypes / characterize / phenotype_outcome_association.

Heavy deps (numpy/pandas/sklearn/scipy) are imported INSIDE functions, following
the repo convention; the pure helpers below (BH-FDR, availability subset,
coverage) are stdlib-only and unit-tested in tests/test_discovery_screen.py.
"""
from __future__ import annotations

import json
import os
from typing import Any

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

ENRICHED_MATRIX_FILE = "feature_matrix_enriched.csv"
RESULTS_JSON = "discovery_screen_results.json"
DONE_MARKER = "_discovery_done.json"
RESULTS_MD = "DISCOVERY_RESULTS.md"

# Outcomes screened: composite PRIMARY + 7 pre-registered per-organ SECONDARIES.
OUTCOMES = [
    "composite",
    "organ_renal",
    "organ_hepatocellular",
    "organ_cholestatic",
    "organ_coagulation_plt",
    "organ_coagulation_inr",
    "organ_hypoperfusion",
    "organ_mortality",
]

MODELS = ["logreg", "gbm"]

# Power thresholds for a cell: fit only if BOTH are met on the family subset.
MIN_EVENTS = 15
MIN_N = 100

# Coverage cutoff for including a discovery family in the enriched clustering
# matrix (anti-artifact: drop sparse-monitor families). A family is kept iff its
# `_available` flag == 1 in >= this fraction of the cohort.
COVERAGE_CUTOFF = 0.80

# FDR threshold for marking a cell a "hit".
FDR_ALPHA = 0.05


# ---------------------------------------------------------------------------
# Pure helpers (stdlib only -- unit-tested without the science stack)
# ---------------------------------------------------------------------------

def benjamini_hochberg(pvalues: list[float], alpha: float = FDR_ALPHA) -> list[float]:
    """Benjamini-Hochberg step-up FDR q-values for a list of p-values.

    Returns q-values in the SAME order as the input list. q_i is the BH-adjusted
    p-value with the standard monotonicity enforcement (cumulative minimum from
    the largest p downward), clipped to <= 1. NaN/None p-values pass through as
    None and are excluded from the rank count (they were never tested).

    This is the only multiple-testing correction in the screen; see the
    "multiple testing" note in DISCOVERY_RESULTS.md.
    """
    # Separate the genuinely-tested p-values (finite floats) from None/NaN.
    indexed = []
    for i, p in enumerate(pvalues):
        if p is None:
            continue
        try:
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if pf != pf:  # NaN
            continue
        indexed.append((i, pf))

    m = len(indexed)
    q = [None] * len(pvalues)
    if m == 0:
        return q

    # Sort by p ascending; assign rank 1..m.
    indexed.sort(key=lambda t: t[1])
    # Raw BH: q_raw[rank] = p * m / rank.
    raw = [(idx, p * m / (rank + 1)) for rank, (idx, p) in enumerate(indexed)]
    # Enforce monotonicity from the largest p down (cumulative minimum).
    running_min = float("inf")
    adjusted = {}
    for rank in range(m - 1, -1, -1):
        idx, qr = raw[rank]
        running_min = min(running_min, qr)
        adjusted[idx] = min(running_min, 1.0)
    for idx, qv in adjusted.items():
        q[idx] = qv
    return q


def availability_flag_name(module) -> str:
    """The `<prefix>_available` flag for a discovery module = the NAME of its
    FIRST SPEC (repo convention; verified across all 16 discovery families:
    ventilation_available, bpv_available, neuro_available, ...)."""
    specs = getattr(module, "SPECS", None)
    if not specs:
        raise ValueError(f"module {getattr(module, '__name__', module)!r} has no SPECS")
    return specs[0].name


def availability_subset_mask(rows: list[dict], flag: str, outcome: str) -> list[bool]:
    """Boolean mask over `rows` (list of dict-like records): keep a row iff its
    family availability flag == 1 AND the outcome is present (non-blank).

    Pure / stdlib-only so it can be unit-tested on a tiny synthetic frame without
    pandas. `rows` may be list-of-dicts (csv.DictReader) or anything supporting
    `.get`. Values are coerced leniently: "1"/1/1.0/True -> available.
    """
    mask = []
    for r in rows:
        avail = _is_one(r.get(flag))
        has_outcome = _present(r.get(outcome))
        mask.append(bool(avail and has_outcome))
    return mask


def coverage(rows: list[dict], flag: str) -> float:
    """Fraction of rows whose availability flag == 1 (cohort coverage of a family).
    Pure / stdlib-only. Empty cohort -> 0.0."""
    if not rows:
        return 0.0
    n_avail = sum(1 for r in rows if _is_one(r.get(flag)))
    return n_avail / len(rows)


def _is_one(v) -> bool:
    """Lenient truthiness for an availability flag value."""
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("", "nan", "none", "0", "0.0", "false"):
        return False
    try:
        return float(s) == 1.0
    except (TypeError, ValueError):
        return False


def _present(v) -> bool:
    """A non-blank, non-NaN outcome value (labelable for that outcome)."""
    if v is None:
        return False
    s = str(v).strip().lower()
    return s not in ("", "nan", "none")


# ---------------------------------------------------------------------------
# cfg / path helpers
# ---------------------------------------------------------------------------

def _cache_dir(cfg: dict[str, Any]) -> str:
    """Resolve cache_dir from either the NESTED confirmatory cfg
    (cfg['data']['cache_dir'], used by run.py/dataset.py/discovery_run.py) or the
    FLAT phenotypes cfg (cfg['cache_dir']). discovery_run passes the nested form."""
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    raise KeyError("cfg has neither data.cache_dir nor cache_dir")


def _seed(cfg: dict[str, Any]) -> int:
    ev = cfg.get("evaluation", {})
    return int(cfg.get("seed", ev.get("seed", 42)))


def _eval_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Evaluation block with safe defaults (outer/inner folds, bootstrap_iters),
    so the screen runs even on a flat phenotypes-style cfg."""
    ev = dict(cfg.get("evaluation", {}))
    ev.setdefault("outer_folds", 5)
    ev.setdefault("inner_folds", 5)
    ev.setdefault("bootstrap_iters", 150)
    return ev


# ---------------------------------------------------------------------------
# (A) Per-family x per-outcome incremental-value screen
# ---------------------------------------------------------------------------

def _confirmatory_baseline_columns(df, modules) -> list[str]:
    """Confirmatory baseline = ALL confirmatory feature columns present in the
    matrix. We use the `comprehensive` nested set over the confirmatory MODULES
    (== standard + comprehensive specs; the `pk` tier is the confirmatory PK
    add-on and is folded in too via names_for_set('pk') below if present). Per
    the task spec the baseline is the confirmatory COMPREHENSIVE feature set."""
    from vitaldb_aki.features.base import names_for_set
    all_specs = []
    for m in modules:
        all_specs.extend(m.SPECS)
    names = names_for_set(all_specs, "comprehensive")
    return [c for c in names if c in df.columns]


def _family_columns(df, module) -> list[str]:
    """Feature columns contributed by one discovery family that are present in the
    matrix. Excludes the `_available` flag itself (it is a gating indicator, not a
    physiology feature, and is constant == 1 on the availability subset)."""
    flag = availability_flag_name(module)
    cols = [s.name for s in module.SPECS if s.name in df.columns and s.name != flag]
    return cols


def _paired_oof(df_sub, baseline_cols, family_cols, model_name, eval_cfg, seed, target):
    """Nested-CV OOF probabilities for baseline AND baseline+family on the SAME
    folds (paired), so DeLong is valid. Mirrors run.oof_predictions but takes
    EXPLICIT column lists (the harness selects by fset; here we need a custom
    baseline vs baseline+family contrast on a family-availability subset).

    Returns (y, oof_base, oof_plus, groups). Both OOF vectors come from the
    identical StratifiedGroupKFold split -> paired comparison.
    """
    import numpy as np
    from sklearn.base import clone
    from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
    from sklearn.pipeline import Pipeline

    from vitaldb_aki.models.dataset import CATEGORICAL, make_preprocessor
    from vitaldb_aki.models.run import _model, _param_grid

    y = df_sub[target].astype(float).astype(int).to_numpy()
    groups = df_sub["subjectid"].to_numpy()

    def _build(cols):
        cat_cols = [c for c in cols if c in CATEGORICAL]
        num_cols = [c for c in cols if c not in CATEGORICAL]
        X = df_sub[cols].copy()
        pre = make_preprocessor(num_cols, cat_cols)
        pipe = Pipeline([("pre", pre), ("clf", _model(model_name, seed))])
        return X, pipe

    plus_cols = baseline_cols + [c for c in family_cols if c not in baseline_cols]
    X_base, pipe_base = _build(baseline_cols)
    X_plus, pipe_plus = _build(plus_cols)

    n_out = eval_cfg["outer_folds"]
    n_in = eval_cfg["inner_folds"]
    outer = StratifiedGroupKFold(n_splits=n_out, shuffle=True, random_state=seed)

    oof_base = np.full(len(y), np.nan)
    oof_plus = np.full(len(y), np.nan)
    # X_base / X_plus share row order with df_sub, so the same (tr, te) indices
    # apply to both -> identical folds -> paired OOF vectors.
    for tr, te in outer.split(X_base, y, groups):
        inner = StratifiedGroupKFold(n_splits=n_in, shuffle=True, random_state=seed)
        gs_b = GridSearchCV(clone(pipe_base), _param_grid(model_name), scoring="roc_auc",
                            cv=inner, n_jobs=-1, refit=True)
        gs_b.fit(X_base.iloc[tr], y[tr], groups=groups[tr])
        oof_base[te] = gs_b.predict_proba(X_base.iloc[te])[:, 1]

        gs_p = GridSearchCV(clone(pipe_plus), _param_grid(model_name), scoring="roc_auc",
                            cv=inner, n_jobs=-1, refit=True)
        gs_p.fit(X_plus.iloc[tr], y[tr], groups=groups[tr])
        oof_plus[te] = gs_p.predict_proba(X_plus.iloc[te])[:, 1]

    return y, oof_base, oof_plus, groups


def _screen_cell(df, baseline_cols, module, outcome, model_name, eval_cfg, seed):
    """One grid cell: availability subset -> power gate -> paired OOF -> DeLong.

    Returns a dict. If underpowered, {"underpowered": True, "n":..., "events":...}
    and NO model is fit.
    """
    import numpy as np

    flag = availability_flag_name(module)
    family = module.__name__.split(".")[-1]

    # Availability-aware subset: rows where the family flag==1 AND outcome present.
    if flag not in df.columns or outcome not in df.columns:
        return {"family": family, "outcome": outcome, "model": model_name,
                "skipped": True, "reason": f"missing column ({flag!r} or {outcome!r})"}

    rows = df.to_dict("records")
    mask = availability_subset_mask(rows, flag, outcome)
    df_sub = df[np.asarray(mask, dtype=bool)].copy()

    n = int(len(df_sub))
    if n == 0:
        return {"family": family, "outcome": outcome, "model": model_name,
                "n": 0, "events": 0, "underpowered": True}
    events = int(df_sub[outcome].astype(float).astype(int).sum())

    if events < MIN_EVENTS or n < MIN_N:
        return {"family": family, "outcome": outcome, "model": model_name,
                "n": n, "events": events, "underpowered": True}

    family_cols = _family_columns(df, module)
    if not family_cols:
        return {"family": family, "outcome": outcome, "model": model_name,
                "n": n, "events": events, "skipped": True,
                "reason": "no family feature columns present in matrix"}

    try:
        y, oof_base, oof_plus, groups = _paired_oof(
            df_sub, baseline_cols, family_cols, model_name, eval_cfg, seed, outcome)
        from vitaldb_aki.models.metrics import bootstrap_ci, delong_roc_test
        dl = delong_roc_test(y, oof_base, oof_plus)
        ci = bootstrap_ci(
            lambda yy, a, b: delong_roc_test(yy, a, b)["delta"],
            y, oof_base, oof_plus, groups,
            n_iter=eval_cfg["bootstrap_iters"], seed=seed)
        return {
            "family": family, "outcome": outcome, "model": model_name,
            "n": n, "events": events,
            "n_family_features": len(family_cols),
            "auroc_base": round(float(dl["auc_a"]), 4),
            "auroc_base_plus_family": round(float(dl["auc_b"]), 4),
            "delta_auroc": round(float(dl["delta"]), 4),
            "delta_auroc_ci95": [round(float(ci[0]), 4), round(float(ci[1]), 4)],
            "p_value": float(dl["p_value"]),
            "p_method": "delong",
            "underpowered": False,
        }
    except Exception as e:  # CV fold failure / degenerate fold -> record, don't crash
        return {"family": family, "outcome": outcome, "model": model_name,
                "n": n, "events": events, "skipped": True,
                "reason": f"{type(e).__name__}: {e}"}


def run_family_screen(cfg, df, confirmatory_modules, discovery_modules) -> dict[str, Any]:
    """Analysis (A): full family x outcome x model grid + BH-FDR over computed
    p-values. Returns {"baseline_features", "n_baseline", "grid", "hits"}."""
    seed = _seed(cfg)
    eval_cfg = _eval_cfg(cfg)

    baseline_cols = _confirmatory_baseline_columns(df, confirmatory_modules)

    grid = []
    for module in discovery_modules:
        for outcome in OUTCOMES:
            for model_name in MODELS:
                cell = _screen_cell(df, baseline_cols, module, outcome,
                                    model_name, eval_cfg, seed)
                grid.append(cell)

    # BH-FDR across the FULL grid of COMPUTED p-values (skip underpowered/skipped).
    pvals = [c.get("p_value") if (not c.get("underpowered") and not c.get("skipped"))
             else None for c in grid]
    qvals = benjamini_hochberg(pvals, alpha=FDR_ALPHA)
    for cell, q in zip(grid, qvals):
        if q is not None:
            cell["q_value"] = round(float(q), 6)
            cell["hit"] = bool(q < FDR_ALPHA and cell.get("delta_auroc", 0) > 0)
        else:
            cell["hit"] = False

    n_tested = sum(1 for p in pvals if p is not None)
    hits = sorted([c for c in grid if c.get("hit")],
                  key=lambda c: c.get("delta_auroc", 0.0), reverse=True)

    return {
        "baseline_definition": "confirmatory comprehensive feature set "
                               "(names_for_set(MODULES.SPECS, 'comprehensive'))",
        "baseline_features": baseline_cols,
        "n_baseline": len(baseline_cols),
        "outcomes": OUTCOMES,
        "models": MODELS,
        "min_events": MIN_EVENTS,
        "min_n": MIN_N,
        "n_tests": n_tested,
        "fdr_alpha": FDR_ALPHA,
        "p_method": "delong (paired correlated-ROC on shared OOF folds)",
        "grid": grid,
        "hits": hits,
    }


# ---------------------------------------------------------------------------
# (B) Enriched phenotype discovery (availability-aware)
# ---------------------------------------------------------------------------

def select_clustering_features(df, confirmatory_modules, discovery_modules,
                               coverage_cutoff: float = COVERAGE_CUTOFF):
    """Choose the WIDELY-AVAILABLE feature set for enriched clustering.

    Includes: confirmatory physiology features (comprehensive set) PLUS the
    feature columns of every discovery family whose `_available` flag is 1 in
    >= coverage_cutoff of the cohort. Sparse-monitor families (EEG, advanced-hemo,
    CVP -- coverage < cutoff) are DROPPED to avoid a "has-monitor vs not" artifact
    cluster (monitor placement is confounded with case severity).

    Returns (feature_cols, kept_families, dropped_families) where the *_families
    entries are {"family", "coverage", "n_features"} dicts.
    """
    from vitaldb_aki.features.base import names_for_set

    rows = df.to_dict("records")

    conf_specs = []
    for m in confirmatory_modules:
        conf_specs.extend(m.SPECS)
    conf_cols = [c for c in names_for_set(conf_specs, "comprehensive") if c in df.columns]

    feature_cols = list(conf_cols)
    kept, dropped = [], []
    for module in discovery_modules:
        flag = availability_flag_name(module)
        if flag not in df.columns:
            dropped.append({"family": module.__name__.split(".")[-1],
                            "coverage": None, "n_features": 0,
                            "reason": "availability flag absent from matrix"})
            continue
        cov = coverage(rows, flag)
        fam_cols = _family_columns(df, module)
        entry = {"family": module.__name__.split(".")[-1],
                 "coverage": round(cov, 4), "n_features": len(fam_cols)}
        if cov >= coverage_cutoff and fam_cols:
            feature_cols.extend([c for c in fam_cols if c not in feature_cols])
            kept.append(entry)
        else:
            if cov < coverage_cutoff:
                entry["reason"] = f"coverage {cov:.3f} < {coverage_cutoff}"
            else:
                entry["reason"] = "no feature columns present"
            dropped.append(entry)

    return feature_cols, kept, dropped


def _build_clustering_X(df, feature_cols):
    """Impute (median) + standardize the widely-available feature matrix, applying
    the same all-NaN-column drop / name-alignment safeguards as
    phenotypes.load_physiology_matrix. Returns (X_scaled, kept_feature_names)."""
    import numpy as np
    import pandas as pd
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    X_df = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    # Drop entirely-missing columns BEFORE imputation (SimpleImputer silently drops
    # all-NaN columns from its output, desyncing names vs matrix -- the bug fixed in
    # load_physiology_matrix). Keep names aligned to X.
    non_empty = [c for c in feature_cols if bool(X_df[c].notna().any())]
    dropped = [c for c in feature_cols if c not in non_empty]
    if dropped:
        print(f"[discovery_screen] dropping {len(dropped)} all-missing clustering "
              f"column(s): {dropped}")
    if not non_empty:
        raise RuntimeError("All candidate clustering columns are entirely missing.")
    X_df = X_df[non_empty]

    X_imputed = SimpleImputer(strategy="median").fit_transform(X_df)
    X_scaled = StandardScaler().fit_transform(X_imputed)
    assert X_scaled.shape[1] == len(non_empty), "feature/name desync in clustering matrix"
    return X_scaled.astype(np.float64), non_empty


def run_enriched_phenotypes(cfg, df, confirmatory_modules, discovery_modules) -> dict[str, Any]:
    """Analysis (B): availability-aware enriched phenotype discovery, reusing
    phenotypes.discover_phenotypes / characterize / phenotype_outcome_association.

    Returns a dict with best_k, stability, per-cluster profiles, the highest-risk
    cluster's rate ratios + replication for composite & organ_renal, the kept /
    dropped family lists, and a comparison to the confirmatory hypotension
    phenotype rate ratios (from the existing PHENOTYPES run, if available)."""
    from vitaldb_aki.analysis.phenotypes import (
        characterize, discover_phenotypes, phenotype_outcome_association,
    )

    seed = _seed(cfg)

    feature_cols, kept, dropped = select_clustering_features(
        df, confirmatory_modules, discovery_modules, COVERAGE_CUTOFF)
    X, feat_names = _build_clustering_X(df, feature_cols)

    print(f"[discovery_screen] enriched clustering on {X.shape[0]} cases x "
          f"{X.shape[1]} widely-available features "
          f"({len(kept)} discovery families kept, {len(dropped)} dropped)")

    results_by_k, best_k = discover_phenotypes(X, k_range=range(2, 8), seed=seed)
    labels = results_by_k[best_k]["labels"]
    stability = results_by_k[best_k]["stability"]

    char = characterize(X, labels, feat_names)

    # phenotype_outcome_association reads its split seed from cfg.get("seed"); pass
    # a flat seed so it is reproducible regardless of cfg shape.
    assoc = phenotype_outcome_association(df, labels, {"seed": seed},
                                          outcome_col="composite",
                                          organ_col="organ_renal", seed=seed)

    # Confirmatory hypotension-phenotype rate ratios for the EXCEEDS comparison.
    conf_rr = _load_confirmatory_phenotype_rr(cfg)

    enriched_rr = {}
    for oc in ("composite", "organ_renal"):
        try:
            ho = assoc["holdout"]["outcomes"][oc]
            enriched_rr[oc] = ho.get("rate_ratio")
        except (KeyError, TypeError):
            enriched_rr[oc] = None

    exceeds = {}
    for oc in ("composite", "organ_renal"):
        e = enriched_rr.get(oc)
        c = conf_rr.get(oc) if conf_rr else None
        exceeds[oc] = (bool(e is not None and c is not None and e > c)
                       if (e is not None and c is not None) else None)

    return {
        "n_patients": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_names": feat_names,
        "kept_families": kept,
        "dropped_families": dropped,
        "coverage_cutoff": COVERAGE_CUTOFF,
        "best_k": int(best_k),
        "stability_by_k": {str(k): float(v["stability"]) for k, v in results_by_k.items()},
        "best_k_stability": float(stability),
        "characterization": char,
        "outcome_association": assoc,
        "enriched_rate_ratios": enriched_rr,
        "confirmatory_rate_ratios": conf_rr,
        "enriched_exceeds_confirmatory": exceeds,
    }


def _load_confirmatory_phenotype_rr(cfg) -> dict[str, Any] | None:
    """Best-effort read of the confirmatory hypotension-phenotype holdout rate
    ratios from a prior phenotypes_results.json (written by phenotypes.py). Used
    only for the EXCEEDS comparison; returns None if absent."""
    path = os.path.join(_cache_dir(cfg), "phenotypes_results.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            res = json.load(fh)
        out = {}
        for oc in ("composite", "organ_renal"):
            out[oc] = res["outcome_association"]["holdout"]["outcomes"][oc]["rate_ratio"]
        return out
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_discovery_screen(cfg: dict[str, Any]) -> dict[str, Any]:
    """Run stages 2-3 of the discovery track on cache/feature_matrix_enriched.csv.

    Writes (in order; the done-marker is written LAST):
      - cache/discovery_screen_results.json
      - vitaldb_aki/docs/DISCOVERY_RESULTS.md
      - cache/_discovery_done.json   (final marker)

    Returns the full results dict.
    """
    import pandas as pd

    from vitaldb_aki.features.build_matrix import DISCOVERY_MODULES, MODULES

    cache_dir = _cache_dir(cfg)
    matrix_path = os.path.join(cache_dir, ENRICHED_MATRIX_FILE)
    if not os.path.exists(matrix_path):
        raise FileNotFoundError(
            f"{matrix_path} not found -- build the enriched matrix first "
            "(discovery_run.build_enriched_matrix).")

    df = pd.read_csv(matrix_path)
    print(f"[discovery_screen] loaded enriched matrix: {df.shape[0]} cases x "
          f"{df.shape[1]} columns")

    # (A) per-family x per-outcome incremental-value screen.
    print("[discovery_screen] Stage 2: per-family incremental-value screen ...")
    screen = run_family_screen(cfg, df, MODULES, DISCOVERY_MODULES)
    print(f"[discovery_screen]   {screen['n_tests']} cells tested, "
          f"{len(screen['hits'])} hit(s) at q<{FDR_ALPHA}")

    # (B) enriched phenotype discovery.
    print("[discovery_screen] Stage 3: enriched phenotype discovery ...")
    try:
        phenotypes = run_enriched_phenotypes(cfg, df, MODULES, DISCOVERY_MODULES)
        print(f"[discovery_screen]   best_k={phenotypes['best_k']} "
              f"stability={phenotypes['best_k_stability']:.3f}")
    except Exception as e:
        phenotypes = {"error": f"{type(e).__name__}: {e}"}
        print(f"[discovery_screen]   enriched phenotype discovery failed: {phenotypes['error']}")

    results = {
        "matrix": ENRICHED_MATRIX_FILE,
        "n_cases": int(df.shape[0]),
        "seed": _seed(cfg),
        "family_screen": screen,
        "enriched_phenotypes": phenotypes,
    }

    os.makedirs(cache_dir, exist_ok=True)
    results_path = os.path.join(cache_dir, RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[discovery_screen] results -> {results_path}")

    _write_discovery_md(results, cfg)

    # Final done-marker written LAST so a watchdog only sees it once everything
    # above has been persisted.
    done_path = os.path.join(cache_dir, DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({
            "n_cases": results["n_cases"],
            "n_tests": screen["n_tests"],
            "n_hits": len(screen["hits"]),
            "enriched_best_k": phenotypes.get("best_k"),
        }, fh, indent=2, default=_json_default)
    print(f"[discovery_screen] DONE marker -> {done_path}")

    return results


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _fmt(v, spec="{:+.3f}"):
    return spec.format(v) if isinstance(v, (int, float)) else "—"


def _write_discovery_md(results: dict, cfg: dict) -> str:
    """Write vitaldb_aki/docs/DISCOVERY_RESULTS.md."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, RESULTS_MD)

    screen = results.get("family_screen", {})
    phen = results.get("enriched_phenotypes", {})
    grid = screen.get("grid", [])

    lines = [
        "# VitalDB-AKI Discovery Screen Results",
        "",
        "**Exploratory** analysis on the enriched matrix "
        f"(`{results.get('matrix')}`, n_cases = {results.get('n_cases')}). Fully "
        "separate from the frozen confirmatory pipeline.",
        "",
        "## (A) Per-family x per-outcome incremental-value screen",
        "",
        f"- Baseline: {screen.get('baseline_definition')} "
        f"({screen.get('n_baseline')} feature columns present).",
        f"- Outcomes ({len(screen.get('outcomes', []))}): "
        f"{', '.join(screen.get('outcomes', []))}.",
        f"- Models: {', '.join(screen.get('models', []))}.",
        "- Each cell is evaluated on an AVAILABILITY-aware subset (rows where the "
        "family `_available` flag == 1 and the outcome is labelable).",
        f"- Power gate: a cell is fit only if events >= {screen.get('min_events')} "
        f"AND n >= {screen.get('min_n')}; otherwise it is flagged UNDERPOWERED and "
        "NOT fit.",
        f"- ΔAUROC = AUROC(baseline+family) - AUROC(baseline); paired p-value via "
        f"**{screen.get('p_method')}** (baseline and baseline+family share the "
        "identical nested-CV folds, so their OOF probability vectors are paired).",
        "",
        f"**Multiple testing: {screen.get('n_tests')} tests computed; "
        f"BH-FDR at alpha = {screen.get('fdr_alpha')}.** A cell is a *hit* iff "
        "q < 0.05 AND ΔAUROC > 0.",
        "",
        "_Underpowered cells are NOT interpreted (no model fit; ΔAUROC and "
        "p-value are undefined for them)._",
        "",
        "### ΔAUROC grid",
        "",
        "Cells show ΔAUROC (q-value). `UP` = underpowered (n/events shown). "
        "`**` marks an FDR hit (q<0.05, ΔAUROC>0). `—` = skipped/missing.",
        "",
    ]

    # Pivot grid into family x (outcome,model) table.
    families = []
    for c in grid:
        if c.get("family") not in families:
            families.append(c.get("family"))
    cell_by_key = {(c.get("family"), c.get("outcome"), c.get("model")): c for c in grid}
    outcomes = screen.get("outcomes", [])
    models = screen.get("models", [])

    header = "| Family | " + " | ".join(f"{o}/{m}" for o in outcomes for m in models) + " |"
    sep = "|" + "---|" * (1 + len(outcomes) * len(models))
    lines += [header, sep]
    for fam in families:
        row = [fam]
        for o in outcomes:
            for m in models:
                c = cell_by_key.get((fam, o, m), {})
                if c.get("underpowered"):
                    row.append(f"UP(n={c.get('n')},e={c.get('events')})")
                elif c.get("skipped"):
                    row.append("—")
                elif "delta_auroc" in c:
                    mark = " **" if c.get("hit") else ""
                    q = c.get("q_value")
                    qs = f"q={q:.3f}" if isinstance(q, (int, float)) else "q=—"
                    row.append(f"{c['delta_auroc']:+.3f} ({qs}){mark}")
                else:
                    row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    # Ranked hits.
    lines += ["", "### Ranked hits (q < 0.05, ΔAUROC > 0)", ""]
    hits = screen.get("hits", [])
    if not hits:
        lines.append("_No family x outcome x model cell reached FDR significance "
                     "with positive ΔAUROC._")
    else:
        lines += ["| Rank | Family | Outcome | Model | ΔAUROC | 95% CI | q | n | events |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for i, c in enumerate(hits, 1):
            ci = c.get("delta_auroc_ci95", [None, None])
            ci_s = (f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"
                    if all(isinstance(x, (int, float)) for x in ci) else "—")
            lines.append(
                f"| {i} | {c['family']} | {c['outcome']} | {c['model']} | "
                f"{c['delta_auroc']:+.3f} | {ci_s} | {c.get('q_value'):.4f} | "
                f"{c.get('n')} | {c.get('events')} |")

    # (B) Enriched phenotypes.
    lines += ["", "## (B) Enriched phenotype discovery (availability-aware)", ""]
    if "error" in phen:
        lines += [f"_Enriched phenotype discovery failed: {phen['error']}_", ""]
    else:
        lines += [
            "Anti-artifact rule: clustering uses ONLY widely-available features "
            "(confirmatory physiology + discovery families with `_available` "
            f"coverage >= {phen.get('coverage_cutoff')}). Sparse-monitor families "
            "(EEG, advanced-hemo, CVP) are dropped to avoid a 'has-monitor vs not' "
            "artifact cluster (monitor placement is confounded with case severity).",
            "",
            f"- Cases clustered: {phen.get('n_patients')}",
            f"- Features used: {phen.get('n_features')}",
            f"- Best k: **{phen.get('best_k')}**  "
            f"(stability / mean pairwise ARI = {phen.get('best_k_stability'):.3f})"
            if isinstance(phen.get("best_k_stability"), (int, float))
            else f"- Best k: {phen.get('best_k')}",
            "",
            "### Families kept in clustering (coverage >= cutoff)",
            "",
            "| Family | Coverage | #features |",
            "|---|---|---|",
        ]
        for e in phen.get("kept_families", []):
            cov = e.get("coverage")
            lines.append(f"| {e.get('family')} | "
                         f"{cov:.3f} | {e.get('n_features')} |"
                         if isinstance(cov, (int, float))
                         else f"| {e.get('family')} | — | {e.get('n_features')} |")

        lines += ["", "### Families DROPPED from clustering (and why)", "",
                  "| Family | Coverage | Reason |", "|---|---|---|"]
        for e in phen.get("dropped_families", []):
            cov = e.get("coverage")
            cov_s = f"{cov:.3f}" if isinstance(cov, (int, float)) else "—"
            lines.append(f"| {e.get('family')} | {cov_s} | {e.get('reason', '')} |")

        # Per-cluster profiles.
        lines += ["", "### Phenotype profiles (z-scored vs population mean)", ""]
        char = phen.get("characterization", {})
        for cid, info in sorted(char.get("phenotypes", {}).items(), key=lambda x: int(x[0])):
            lines += [
                f"#### Cluster {cid} — {info.get('subtype_hint')}",
                f"- n = {info.get('n')} ({info.get('pct')}% of cohort)",
                f"- Top elevated: {', '.join(info.get('top_high', [])[:5])}",
                f"- Top suppressed: {', '.join(info.get('top_low', [])[:5])}",
                "",
            ]

        # Risk stratification + comparison.
        lines += ["### Risk stratification (held-out split) & comparison to "
                  "confirmatory hypotension phenotype", ""]
        assoc = phen.get("outcome_association", {})
        e_rr = phen.get("enriched_rate_ratios", {})
        c_rr = phen.get("confirmatory_rate_ratios") or {}
        exceeds = phen.get("enriched_exceeds_confirmatory", {})
        lines += ["| Outcome | Enriched RR (highest vs rest) | Confirmatory RR | "
                  "Replicated | Exceeds confirmatory? |",
                  "|---|---|---|---|---|"]
        for oc in ("composite", "organ_renal"):
            try:
                rep = assoc["replication"][oc]["replicated"]
            except (KeyError, TypeError):
                rep = None
            e = e_rr.get(oc)
            c = c_rr.get(oc)
            lines.append(
                f"| {oc} | {_fmt(e, '{:.2f}')} | "
                f"{_fmt(c, '{:.2f}') if c is not None else 'n/a'} | "
                f"{'YES' if rep else ('NO' if rep is not None else '—')} | "
                f"{'YES' if exceeds.get(oc) else ('NO' if exceeds.get(oc) is not None else '—')} |")
        lines += ["",
                  "_Confirmatory hypotension phenotype reference (prior run): "
                  "composite RR ~2.4-3.0, renal RR ~3.0-3.6. 'Exceeds' compares the "
                  "enriched highest-risk cluster's held-out rate ratio against the "
                  "confirmatory phenotype's (read from phenotypes_results.json when "
                  "available)._"]

    lines += ["", "---", "*Generated by vitaldb_aki/analysis/discovery_screen.py*", ""]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[discovery_screen] DISCOVERY_RESULTS.md -> {md_path}")
    return md_path


def _json_default(obj):
    """Fallback JSON serializer for numpy types (mirrors phenotypes._json_default)."""
    import math
    try:
        import numpy as np
    except ImportError:
        raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


if __name__ == "__main__":
    from common.config import load_yaml
    _CFG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config.yaml")
    run_discovery_screen(load_yaml(_CFG))
