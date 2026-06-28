"""Persistent vs transient AKI -- prognostic enrichment (hypothesis-generating).

SCIENTIFIC GOAL
---------------
Transient AKI usually recovers; PERSISTENT AKI is the prognostically important
phenotype (-> CKD).  Trajectories were adjudicated upstream
(``cache/aki_trajectory.csv`` + ``cache/aki_trajectory_summary.json``):
recovery window 24-72 h, KDIGO window 168 h -> 94 transient / 41 persistent /
8 indeterminate.  Two questions:

  (1) Which INTRAOP/PREOP factors predict NON-recovery (persistent) among AKI+
      cases?  -> penalised (L2) logistic regression, persistent (1) vs transient
      (0), report ORs with wide CIs + BH-FDR.  N is small (41 persistent) ->
      HYPOTHESIS-GENERATING only.
  (2) Are the study's main hemodynamic signals (hypotension burden
      ``map_auc_below_65`` etc.) STRONGER for persistent than transient AKI?
      -> effect-modification: OR-per-SD-of-burden and AUROC for the
      persistent-vs-noAKI and transient-vs-noAKI contrasts.

LEAKAGE FIREWALL
----------------
Predictors are PREOP + INTRAOP only.  The trajectory label is derived from
POSTOP creatinine -- that is fine as the OUTCOME (y), but NO postop-creatinine
value is ever used as a predictor.  The trajectory CSV carries baseline_cr /
peak_cr / recovery_cr columns; we take ONLY ``baseline_cr`` (a preop value) and
NEVER peak/recovery (postop).

Run from repo root::

    python3 -m vitaldb_aki.analysis.aki_persistence

Heavy deps (numpy/scipy/sklearn) import lazily inside functions so the module
imports under the stdlib-only integrity core.
"""

from __future__ import annotations

import csv
import json
import math
import os
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RANDOM_SEED = 20260626          # matches config.yaml seed default

_TRAJ_FILE = "aki_trajectory.csv"
_TRAJ_SUMMARY = "aki_trajectory_summary.json"
_MATRIX_FILE = "feature_matrix.csv"
_RESULTS_JSON = "aki_persistence_results.json"
_DONE_MARKER = "_aki_persistence_done.json"

# Predictors for the persistent-vs-transient logistic model (PREOP + INTRAOP
# only).  baseline_cr / egfr_ckdepi are PREOP renal status; the rest are preop
# comorbidity / intraop hemodynamics + magnitude.  optype is handled separately
# (categorical -> top-level dummies).  NO postop creatinine here.
_HYPOTENSION_BURDEN = [
    "map_auc_below_65",   # primary study hypotension-burden signal
    "map_lowest",
    "map_min_below_65",
]
_PREDICTORS = [
    # hypotension burden (the study's main hemodynamic signal)
    "map_auc_below_65",
    "map_lowest",
    "map_min_below_65",
    # preop renal status (preop labs -- NOT postop)
    "baseline_cr",
    "egfr_ckdepi",
    # demographics / risk
    "age",
    "sex_male",
    "asa",
    "preop_htn",
    "preop_dm",
    # intraop magnitude / duration
    "intraop_ebl",
    "anesthesia_duration_min",
    "surgery_duration_min",
]
# optype as a small set of dummies (reference = most common level).
_OPTYPE_COL = "optype"


# ---------------------------------------------------------------------------
# Config / path helpers (mirror analysis/actionable_targets.py conventions)
# ---------------------------------------------------------------------------
def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return "vitaldb_aki/cache"


def _resolve_seed(cfg: dict[str, Any]) -> int:
    return int(cfg.get("seed", RANDOM_SEED))


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


# ---------------------------------------------------------------------------
# BH-FDR (stdlib; same semantics as actionable_targets.benjamini_hochberg)
# ---------------------------------------------------------------------------
def benjamini_hochberg(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg FDR.  ``None``/non-finite -> 1.0 (never rejected)."""
    clean = [
        (p if (p is not None and isinstance(p, (int, float)) and math.isfinite(p)) else 1.0)
        for p in pvals
    ]
    m = len(clean)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: clean[i])
    reject = [False] * m
    max_k = -1
    for rank, idx in enumerate(order, start=1):
        if clean[idx] <= (rank / m) * alpha:
            max_k = rank
    if max_k >= 1:
        for rank, idx in enumerate(order, start=1):
            if rank <= max_k:
                reject[idx] = True
    return reject


# ---------------------------------------------------------------------------
# Data loading / join
# ---------------------------------------------------------------------------
def _read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _to_float(v):
    try:
        if v is None or v == "" or str(v).lower() in ("na", "nan", "none"):
            return None
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def load_joined(cache_dir: str):
    """Join trajectory labels to feature_matrix on caseid.

    Returns (rows, summary) where ``rows`` is a list of dicts each carrying the
    raw feature_matrix record plus ``_trajectory`` ('transient'/'persistent'/
    'indeterminate') and ``_persistent`` (1/0/None).
    """
    traj_path = os.path.join(cache_dir, _TRAJ_FILE)
    mat_path = os.path.join(cache_dir, _MATRIX_FILE)
    summ_path = os.path.join(cache_dir, _TRAJ_SUMMARY)

    traj = _read_csv(traj_path)
    mat = _read_csv(mat_path)
    with open(summ_path, "r", encoding="utf-8") as fh:
        summary = json.load(fh)

    label_by_case: dict[str, str] = {}
    for r in traj:
        label_by_case[str(r["caseid"]).strip()] = r["trajectory"].strip()

    rows = []
    for r in mat:
        cid = str(r["caseid"]).strip()
        if cid not in label_by_case:
            continue
        lab = label_by_case[cid]
        r = dict(r)
        r["_trajectory"] = lab
        r["_persistent"] = 1 if lab == "persistent" else (0 if lab == "transient" else None)
        rows.append(r)
    return rows, summary


# ---------------------------------------------------------------------------
# Design-matrix construction
# ---------------------------------------------------------------------------
def _build_design(rows, predictors, optype_dummies):
    """Return (X, y, feature_names, kept_rows) for AKI+ rows with a trajectory
    of transient/persistent.  Rows with any missing predictor are dropped
    (complete-case); the count is reported.  X columns are mean-imputed? No --
    complete-case, because N is tiny and imputation would be opaque.
    """
    import numpy as np

    feat_names = list(predictors) + [f"optype__{lvl}" for lvl in optype_dummies]
    X_rows, y, kept = [], [], []
    for r in rows:
        if r["_persistent"] is None:
            continue
        vec = []
        ok = True
        for p in predictors:
            v = _to_float(r.get(p))
            if v is None:
                ok = False
                break
            vec.append(v)
        if not ok:
            continue
        ot = (r.get(_OPTYPE_COL) or "").strip()
        for lvl in optype_dummies:
            vec.append(1.0 if ot == lvl else 0.0)
        X_rows.append(vec)
        y.append(int(r["_persistent"]))
        kept.append(r)
    X = np.asarray(X_rows, dtype=float)
    y = np.asarray(y, dtype=int)
    return X, y, feat_names, kept


def _choose_optype_dummies(rows, max_levels=3):
    """Pick the most common optype levels (excluding reference) as dummies.

    Returns (dummies, reference_level).  Reference = most common level.
    """
    from collections import Counter
    cnt = Counter()
    for r in rows:
        if r["_persistent"] is None:
            continue
        ot = (r.get(_OPTYPE_COL) or "").strip()
        if ot:
            cnt[ot] += 1
    ordered = [lvl for lvl, _ in cnt.most_common()]
    if not ordered:
        return [], None
    reference = ordered[0]
    dummies = ordered[1:1 + max_levels]
    return dummies, reference


# ---------------------------------------------------------------------------
# Penalised logistic: ORs + CIs via bootstrap
# ---------------------------------------------------------------------------
def fit_penalised_logistic(X, y, feature_names, seed=RANDOM_SEED,
                           n_boot=1000, C=1.0):
    """L2-penalised logistic regression of y on standardised X.

    Coefficients are reported on the per-SD scale (X standardised) so ORs are
    comparable across predictors.  CIs + two-sided p-values come from a
    nonparametric (case-resampling) bootstrap -- appropriate because the
    penalised point estimate has no closed-form Wald SE and N is small.

    Returns list of dicts (one per feature) with or, ci_lo, ci_hi, p, and the
    point coefficient.
    """
    import warnings
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    rng = np.random.default_rng(seed)
    n, p = X.shape

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    # guard against zero-variance columns producing nan after scaling
    Xs = np.nan_to_num(Xs, nan=0.0)

    def _fit(Xm, ym):
        clf = LogisticRegression(penalty="l2", C=C, solver="liblinear",
                                 max_iter=1000, random_state=seed)
        clf.fit(Xm, ym)
        return clf.coef_.ravel().copy()

    point = _fit(Xs, y)

    boot = np.full((n_boot, p), np.nan)
    idx_all = np.arange(n)
    for b in range(n_boot):
        bi = rng.choice(idx_all, size=n, replace=True)
        yb = y[bi]
        # need both classes present in the resample
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        try:
            boot[b] = _fit(Xs[bi], yb)
        except Exception:
            continue

    out = []
    for j, name in enumerate(feature_names):
        col = boot[:, j]
        col = col[np.isfinite(col)]
        coef = float(point[j])
        if col.size >= 50:
            lo, hi = np.percentile(col, [2.5, 97.5])
            # two-sided bootstrap p: proportion on the far side of 0, x2
            frac_pos = float((col > 0).mean())
            pval = 2.0 * min(frac_pos, 1.0 - frac_pos)
            pval = min(1.0, max(pval, 1.0 / (col.size + 1)))
        else:
            lo = hi = float("nan")
            pval = None
        out.append({
            "feature": name,
            "coef_per_sd": coef,
            "or_per_sd": float(math.exp(coef)),
            "ci95_lo": float(math.exp(lo)) if math.isfinite(lo) else None,
            "ci95_hi": float(math.exp(hi)) if math.isfinite(hi) else None,
            "p_bootstrap": pval,
            "n_boot_valid": int(col.size),
        })
    return out


# ---------------------------------------------------------------------------
# Effect-modification: burden discrimination, persistent vs transient
# ---------------------------------------------------------------------------
def burden_contrasts(rows, burden_cols, seed=RANDOM_SEED, n_boot=1000):
    """For each burden column, quantify how strongly it discriminates each AKI
    trajectory FROM no-AKI.

    Three groups among the joined cohort:
      - no-AKI  : feature_matrix rows NOT in the trajectory file -> handled by
                  caller (passed in as ``_group == 'noaki'``)
      - transient / persistent : from the trajectory join.

    For each burden column we fit two univariate logistic contrasts on
    standardised burden:
        persistent (1) vs no-AKI (0)
        transient  (1) vs no-AKI (0)
    and report OR-per-SD + AUROC for each, plus a head-to-head
    persistent-vs-transient (among AKI+) OR-per-SD.  A LARGER persistent OR/AUROC
    than transient is evidence the burden signal tracks the prognostically
    important phenotype.
    """
    import warnings
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    rng = np.random.default_rng(seed)

    # near-unpenalised but numerically stable + fast (mirrors actionable_targets
    # C=1e6 convention); avoids the lbfgs quasi-separation slowdown on a single
    # standardised burden column.
    def _newclf():
        return LogisticRegression(penalty="l2", C=1e6, solver="liblinear",
                                  max_iter=1000)

    def _vals(group, col):
        out = []
        for r in rows:
            if r["_group"] != group:
                continue
            v = _to_float(r.get(col))
            if v is not None:
                out.append(v)
        return np.asarray(out, dtype=float)

    def _contrast(pos, neg):
        """OR per SD + AUROC for pos(1) vs neg(0) on a single burden column."""
        if pos.size < 5 or neg.size < 5:
            return None
        y = np.concatenate([np.ones(pos.size), np.zeros(neg.size)])
        x = np.concatenate([pos, neg]).reshape(-1, 1)
        sd = x.std() or 1.0
        xs = (x - x.mean()) / sd
        clf = _newclf()
        try:
            clf.fit(xs, y)
            coef = float(clf.coef_.ravel()[0])
            prob = clf.predict_proba(xs)[:, 1]
            auc = float(roc_auc_score(y, prob))
        except Exception:
            return None
        # bootstrap CI for OR-per-SD and AUROC
        ors, aucs = [], []
        nall = y.size
        idx = np.arange(nall)
        for _ in range(n_boot):
            bi = rng.choice(idx, size=nall, replace=True)
            yb, xb = y[bi], xs[bi]
            if yb.sum() < 3 or (nall - yb.sum()) < 3:
                continue
            try:
                c = _newclf().fit(xb, yb)
                ors.append(math.exp(float(c.coef_.ravel()[0])))
                aucs.append(float(roc_auc_score(yb, c.predict_proba(xb)[:, 1])))
            except Exception:
                continue
        def _ci(arr):
            arr = np.asarray(arr, dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size < 50:
                return (None, None)
            lo, hi = np.percentile(arr, [2.5, 97.5])
            return (float(lo), float(hi))
        or_lo, or_hi = _ci(ors)
        auc_lo, auc_hi = _ci(aucs)
        return {
            "n_pos": int(pos.size), "n_neg": int(neg.size),
            "or_per_sd": float(math.exp(coef)),
            "or_ci95": [or_lo, or_hi],
            "auroc": auc, "auroc_ci95": [auc_lo, auc_hi],
        }

    results = {}
    for col in burden_cols:
        noaki = _vals("noaki", col)
        trans = _vals("transient", col)
        pers = _vals("persistent", col)
        block = {
            "persistent_vs_noaki": _contrast(pers, noaki),
            "transient_vs_noaki": _contrast(trans, noaki),
            "persistent_vs_transient": _contrast(pers, trans),
        }
        # head-to-head summary: does burden discriminate persistent MORE?
        pv = block["persistent_vs_noaki"]
        tv = block["transient_vs_noaki"]
        if pv and tv:
            block["stronger_for_persistent"] = bool(
                (pv["or_per_sd"] > tv["or_per_sd"]) and (pv["auroc"] > tv["auroc"])
            )
            block["delta_or_per_sd"] = pv["or_per_sd"] - tv["or_per_sd"]
            block["delta_auroc"] = pv["auroc"] - tv["auroc"]
        else:
            block["stronger_for_persistent"] = None
        results[col] = block
    return results


# ---------------------------------------------------------------------------
# Descriptive baseline characteristics
# ---------------------------------------------------------------------------
def describe_groups(rows, cols):
    """Mean (sd) / n of each col for transient vs persistent (AKI+ only)."""
    import numpy as np

    def _summ(group, col):
        vals = [
            _to_float(r.get(col)) for r in rows
            if r["_trajectory"] == group and r["_group"] != "noaki"
        ]
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"n": 0, "mean": None, "sd": None}
        a = np.asarray(vals, dtype=float)
        return {"n": int(a.size), "mean": float(a.mean()),
                "sd": float(a.std(ddof=1)) if a.size > 1 else 0.0}

    out = {}
    for col in cols:
        out[col] = {
            "transient": _summ("transient", col),
            "persistent": _summ("persistent", col),
        }
    return out


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_aki_persistence(cfg: dict[str, Any]) -> dict[str, Any]:
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)
    os.makedirs(cache_dir, exist_ok=True)

    # ---- load + tag groups (incl. no-AKI from the full matrix) ----
    traj_rows, summary = load_joined(cache_dir)            # AKI+ only (in traj file)
    traj_cases = {str(r["caseid"]).strip() for r in traj_rows}

    full = _read_csv(os.path.join(cache_dir, _MATRIX_FILE))
    all_rows = []
    for r in full:
        cid = str(r["caseid"]).strip()
        r = dict(r)
        if cid in traj_cases:
            # already in traj_rows with _trajectory/_persistent; copy label
            lab = next(t["_trajectory"] for t in traj_rows if str(t["caseid"]).strip() == cid)
            r["_trajectory"] = lab
            r["_persistent"] = 1 if lab == "persistent" else (0 if lab == "transient" else None)
            r["_group"] = lab  # transient/persistent/indeterminate
        else:
            r["_trajectory"] = "noaki"
            r["_persistent"] = None
            r["_group"] = "noaki"
        all_rows.append(r)

    aki_rows = [r for r in all_rows if r["_group"] in ("transient", "persistent", "indeterminate")]

    n_persistent = sum(1 for r in aki_rows if r["_group"] == "persistent")
    n_transient = sum(1 for r in aki_rows if r["_group"] == "transient")
    n_indeterminate = sum(1 for r in aki_rows if r["_group"] == "indeterminate")
    n_noaki = sum(1 for r in all_rows if r["_group"] == "noaki")

    # ---- Analysis 1: penalised logistic, persistent vs transient ----
    optype_dummies, optype_ref = _choose_optype_dummies(aki_rows, max_levels=3)
    X, y, feat_names, kept = _build_design(aki_rows, _PREDICTORS, optype_dummies)

    n_model = int(y.size)
    n_model_pers = int(y.sum()) if n_model else 0
    n_model_trans = n_model - n_model_pers

    predictor_block = {}
    if n_model >= 20 and 0 < n_model_pers < n_model:
        fits = fit_penalised_logistic(X, y, feat_names, seed=seed,
                                      n_boot=1000, C=1.0)
        pvals = [f["p_bootstrap"] for f in fits]
        reject = benjamini_hochberg([p if p is not None else 1.0 for p in pvals])
        for f, rj in zip(fits, reject):
            f["fdr_reject"] = bool(rj)
        predictor_block = {
            "model": "L2-penalised logistic (C=1.0), per-SD standardised predictors",
            "outcome": "persistent (1) vs transient (0), among AKI+",
            "n": n_model, "n_persistent": n_model_pers, "n_transient": n_model_trans,
            "optype_reference": optype_ref,
            "optype_dummies": optype_dummies,
            "predictors": fits,
            "fdr_note": "BH-FDR across all predictor p-values (bootstrap).",
        }
    else:
        predictor_block = {"available": False,
                           "reason": f"insufficient data (n={n_model}, persistent={n_model_pers})"}

    # ---- Analysis 2: burden effect-modification (persistent vs transient) ----
    burden_block = burden_contrasts(all_rows, _HYPOTENSION_BURDEN,
                                    seed=seed, n_boot=1000)

    # ---- Analysis 3: descriptive baseline + intraop hemodynamics ----
    desc_cols = [
        "baseline_cr", "egfr_ckdepi", "age", "asa", "preop_htn", "preop_dm",
        "intraop_ebl", "anesthesia_duration_min", "surgery_duration_min",
    ] + _HYPOTENSION_BURDEN
    descriptive = describe_groups(aki_rows, desc_cols)

    results = {
        "study": cfg.get("study", "vitaldb_aki"),
        "seed": seed,
        "definitions": {
            "recovery_early_h": summary.get("recovery_early_h"),
            "recovery_late_h": summary.get("recovery_late_h"),
            "kdigo_window_h": summary.get("kdigo_window_h"),
            "note": summary.get("note"),
        },
        "n": {
            "aki_positive": n_persistent + n_transient + n_indeterminate,
            "persistent": n_persistent,
            "transient": n_transient,
            "indeterminate_excluded": n_indeterminate,
            "noaki": n_noaki,
        },
        "predictors_of_persistence": predictor_block,
        "burden_effect_modification": burden_block,
        "descriptive": descriptive,
        "leakage_firewall": (
            "Predictors are PREOP+INTRAOP only. The trajectory label is derived "
            "from POSTOP creatinine and used solely as the OUTCOME (y). Only "
            "baseline_cr (a preop value) enters the predictor set; peak/recovery "
            "creatinine (postop) are never predictors."
        ),
        "interpretation": (
            "HYPOTHESIS-GENERATING. Persistent AKI N=41 -> the penalised logistic "
            "is underpowered; ORs are per-SD with wide bootstrap CIs and should "
            "not be over-interpreted. Effect-modification compares how strongly "
            "hypotension burden discriminates persistent vs transient AKI from "
            "no-AKI; a larger persistent OR/AUROC suggests the primary "
            "hemodynamic signal tracks the prognostically important phenotype."
        ),
    }

    results_path = os.path.join(cache_dir, _RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[aki_persistence] results written to {results_path}")

    _write_md(results, cfg)

    done_path = os.path.join(cache_dir, _DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"done": True, "results_json": _RESULTS_JSON,
                   "n_persistent": n_persistent, "n_transient": n_transient},
                  fh, indent=2)
    print(f"[aki_persistence] done marker written to {done_path}")
    return results


# ---------------------------------------------------------------------------
# Markdown report (READ-FIRST limitations, like docs/ACTIONABLE_RESULTS.md)
# ---------------------------------------------------------------------------
def _fmt_or(f):
    lo = f.get("ci95_lo"); hi = f.get("ci95_hi")
    ci = f"{lo:.2f} to {hi:.2f}" if (lo is not None and hi is not None) else "n/a"
    p = f.get("p_bootstrap")
    ps = f"{p:.3f}" if p is not None else "n/a"
    star = " (FDR-reject)" if f.get("fdr_reject") else ""
    return f"OR/SD = {f['or_per_sd']:.2f} (95% CI {ci}); p = {ps}{star}"


def _write_md(results, cfg):
    cache_dir = _resolve_cache_dir(cfg)
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(cache_dir)), "docs")
    # cache_dir is e.g. vitaldb_aki/cache -> repo docs is vitaldb_aki/docs
    docs_dir = os.path.join(os.path.dirname(cache_dir.rstrip("/")), "docs")
    if not os.path.isdir(docs_dir):
        # fallback relative to this file
        here = os.path.dirname(os.path.abspath(__file__))
        docs_dir = os.path.join(os.path.dirname(here), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "AKI_PERSISTENCE.md")

    n = results["n"]
    defs = results["definitions"]
    L = []
    L.append("# Persistent vs Transient AKI -- Prognostic Enrichment\n")
    L.append("## Interpretation & limitations (READ FIRST)\n")
    L.append(
        f"- **Small N, hypothesis-generating only.** Persistent AKI **N = {n['persistent']}** "
        f"vs transient N = {n['transient']} (indeterminate N = {n['indeterminate_excluded']} "
        "excluded). With 41 events the penalised logistic is **underpowered**; ORs are "
        "reported **per SD** with **wide bootstrap CIs** and must not be over-interpreted.")
    L.append(
        "- **No correction survives strongly.** BH-FDR is applied across the predictor "
        "p-values, but with this N the study is exploratory: treat any 'FDR-reject' flag "
        "as a lead for a prospective study, not a confirmed effect.")
    L.append(
        "- **Observational, single-centre** (VitalDB / SNUH). Confounding by indication "
        "is the central threat: persistent non-recovery may reflect sicker patients rather "
        "than any single intraoperative exposure.")
    L.append(
        "- **Leakage firewall.** Predictors are PREOP+INTRAOP only. The trajectory label "
        "is derived from POSTOP creatinine and is used **only as the outcome (y)**. Only "
        "`baseline_cr` (preop) enters the predictor set; peak/recovery creatinine (postop) "
        "are never predictors.\n")

    L.append("## Trajectory definitions (from `aki_trajectory_summary.json`)\n")
    L.append(
        f"- **AKI+** = met KDIGO creatinine criteria within {defs.get('kdigo_window_h')} h.")
    L.append(
        f"- **Transient** = recovered within the **{defs.get('recovery_early_h')}-"
        f"{defs.get('recovery_late_h')} h** window (< 1.5x baseline AND within 0.3 mg/dL of "
        "baseline).")
    L.append(
        "- **Persistent** = AKI+ that did NOT recover in that window (prognostically "
        "important -> CKD).")
    L.append(
        "- **Indeterminate** = AKI+ but no creatinine measured in the recovery window "
        "(cannot adjudicate) -> **excluded** from the persistent-vs-transient model.\n")

    # ---- Predictors ----
    L.append("## Q1. Predictors of NON-recovery (persistent vs transient, AKI+)\n")
    pb = results["predictors_of_persistence"]
    if pb.get("available") is False:
        L.append(f"_Not analysable: {pb.get('reason')}._\n")
    else:
        L.append(
            f"- Model: {pb['model']}. Outcome: {pb['outcome']}. "
            f"N = {pb['n']} (persistent {pb['n_persistent']}, transient {pb['n_transient']}).")
        L.append(
            f"- optype reference level = `{pb['optype_reference']}`; dummies = "
            f"{pb['optype_dummies']}.\n")
        # rank by |coef|
        fits = sorted(pb["predictors"], key=lambda f: abs(f["coef_per_sd"]), reverse=True)
        L.append("Ranked by |effect| (OR per SD of standardised predictor):\n")
        for f in fits:
            L.append(f"- **{f['feature']}**: {_fmt_or(f)}")
        L.append("")

    # ---- Burden effect modification ----
    L.append("## Q2. Does hypotension burden discriminate PERSISTENT more strongly?\n")
    L.append(
        "For each burden column: OR per SD + AUROC for `persistent vs no-AKI` and "
        "`transient vs no-AKI`. A LARGER persistent OR/AUROC = the primary hemodynamic "
        "signal tracks the prognostically important phenotype.\n")
    for col, blk in results["burden_effect_modification"].items():
        L.append(f"### `{col}`")
        pv = blk.get("persistent_vs_noaki")
        tv = blk.get("transient_vs_noaki")
        def _line(tag, c):
            if not c:
                return f"- {tag}: n/a"
            orci = c["or_ci95"]
            aci = c["auroc_ci95"]
            orcis = (f"{orci[0]:.2f}-{orci[1]:.2f}" if orci[0] is not None else "n/a")
            acis = (f"{aci[0]:.2f}-{aci[1]:.2f}" if aci[0] is not None else "n/a")
            return (f"- {tag} (n+={c['n_pos']}, n-={c['n_neg']}): OR/SD = "
                    f"{c['or_per_sd']:.2f} (95% CI {orcis}); AUROC = {c['auroc']:.2f} "
                    f"(95% CI {acis})")
        L.append(_line("persistent vs no-AKI", pv))
        L.append(_line("transient vs no-AKI", tv))
        sp = blk.get("stronger_for_persistent")
        if sp is None:
            L.append("- head-to-head: not estimable")
        else:
            L.append(
                f"- **stronger for persistent = {sp}** "
                f"(delta OR/SD = {blk.get('delta_or_per_sd'):+.2f}, "
                f"delta AUROC = {blk.get('delta_auroc'):+.2f})")
        L.append("")

    # ---- Descriptive ----
    L.append("## Q3. Baseline + intraop characteristics (transient vs persistent)\n")
    L.append("| feature | transient mean (sd), n | persistent mean (sd), n |")
    L.append("| --- | --- | --- |")
    for col, blk in results["descriptive"].items():
        t = blk["transient"]; p = blk["persistent"]
        def _c(s):
            if s["mean"] is None:
                return f"n={s['n']}"
            return f"{s['mean']:.3g} ({s['sd']:.3g}), n={s['n']}"
        L.append(f"| {col} | {_c(t)} | {_c(p)} |")
    L.append("")

    L.append("## Methods (brief)\n")
    L.append(
        "- Join `aki_trajectory.csv` (trajectory label) to `feature_matrix.csv` on "
        "`caseid`. AKI+ = present in trajectory file; no-AKI = remaining matrix cases.")
    L.append(
        "- Q1: complete-case L2-penalised logistic (sklearn, C=1.0) of persistent (1) vs "
        "transient (0) on standardised PREOP+INTRAOP predictors + optype dummies; ORs per "
        "SD; 95% CIs + two-sided p from a 1000-rep case-resampling bootstrap; BH-FDR across "
        "predictors.")
    L.append(
        "- Q2: per burden column, unpenalised univariate logistic of trajectory-vs-no-AKI "
        "on standardised burden; OR per SD + AUROC with bootstrap CIs; head-to-head flag "
        "if persistent OR AND AUROC both exceed transient.")
    L.append(f"- Seed = {results['seed']} (config.yaml).\n")
    L.append("---")
    L.append("*Generated by `vitaldb_aki/analysis/aki_persistence.py`*")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[aki_persistence] markdown written to {md_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    res = run_aki_persistence(cfg)
    print(json.dumps(res["n"], indent=2))


if __name__ == "__main__":
    main()
