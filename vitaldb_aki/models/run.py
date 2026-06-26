"""run.py -- the incremental-value harness (Sec 9, 10, 11, 12).

Nested, patient-level cross-validation over the three NESTED feature sets
(standard -> +comprehensive -> +pk) and two tabular model classes (regularized
logistic regression, gradient boosting). Inner folds tune; outer folds produce
out-of-fold (OOF) predicted probabilities used for every downstream statistic.

From the OOF predictions we compute (Sec 12):
  * discrimination: AUROC + AUPRC (the rare-event metric, Sec 10),
  * incremental value: ΔAUROC (DeLong) and continuous NRI/IDI with patient-level
    bootstrap CIs, for +PK vs +Comprehensive (the pre-specified primary contrast)
    and +Comprehensive vs Standard,
  * a shuffled-label negative control (Sec 11.5) -> AUROC collapses to ~0.5.

The deep-learning waveform arm (Sec 9F) and calibration/decision-curve (Sec 12)
attach to these same OOF vectors.
"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from vitaldb_aki.models.dataset import (
    build_xy, events_per_variable, load_matrix, make_preprocessor,
)
from vitaldb_aki.models.metrics import bootstrap_ci, delong_roc_test, idi_nri

FEATURE_SETS = ["standard", "comprehensive", "pk"]


def _model(name: str, seed: int):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    if name == "logreg":
        return LogisticRegression(penalty="l2", class_weight="balanced",
                                  solver="liblinear", max_iter=2000, random_state=seed)
    if name == "gbm":
        return HistGradientBoostingClassifier(
            learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
            l2_regularization=1.0, early_stopping=True, random_state=seed)
    raise ValueError(name)


def _param_grid(name: str):
    if name == "logreg":
        return {"clf__C": [0.01, 0.1, 1.0]}
    return {"clf__max_leaf_nodes": [7, 15, 31]}


def oof_predictions(df, fset, modules, model_name, cfg, seed=0):
    """Nested-CV out-of-fold probabilities for one (feature set, model)."""
    from sklearn.base import clone
    from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
    from sklearn.pipeline import Pipeline

    X, y, groups, num_cols, cat_cols = build_xy(df, fset, modules)
    pre = make_preprocessor(num_cols, cat_cols)
    pipe = Pipeline([("pre", pre), ("clf", _model(model_name, seed))])

    n_out = cfg["evaluation"]["outer_folds"]
    n_in = cfg["evaluation"]["inner_folds"]
    outer = StratifiedGroupKFold(n_splits=n_out, shuffle=True, random_state=seed)
    oof = np.full(len(y), np.nan)
    for tr, te in outer.split(X, y, groups):
        inner = StratifiedGroupKFold(n_splits=n_in, shuffle=True, random_state=seed)
        gs = GridSearchCV(clone(pipe), _param_grid(model_name), scoring="roc_auc",
                          cv=inner, n_jobs=-1, refit=True)
        gs.fit(X.iloc[tr], y[tr], groups=groups[tr])
        oof[te] = gs.predict_proba(X.iloc[te])[:, 1]
    return oof, y, groups


def _disc(y, p):
    from sklearn.metrics import average_precision_score, roc_auc_score
    return {"auroc": float(roc_auc_score(y, p)),
            "auprc": float(average_precision_score(y, p)),
            "prevalence": float(np.mean(y))}


def run(cfg: dict[str, Any], modules=None, model_name="logreg", seed=0,
        sets=None) -> dict[str, Any]:
    if modules is None:
        from vitaldb_aki.features import build_matrix
        modules = build_matrix.MODULES
    df = load_matrix(cfg)
    sets = sets or [s for s in FEATURE_SETS
                    if events_per_variable(df, s, modules)["n_raw_features"] > 0]

    result: dict[str, Any] = {"model": model_name, "n": int(len(df)),
                              "n_events": int(df["aki"].sum()), "sets": {}}
    oof: dict[str, np.ndarray] = {}
    y_ref = None; g_ref = None
    for s in sets:
        p, y, g = oof_predictions(df, s, modules, model_name, cfg, seed)
        oof[s] = p; y_ref = y; g_ref = g
        result["sets"][s] = {**_disc(y, p),
                             "epv": events_per_variable(df, s, modules)}

    # incremental-value contrasts (Sec 12): each adjacent nested pair present
    contrasts = []
    pairs = [("comprehensive", "standard"), ("pk", "comprehensive")]
    nb = cfg["evaluation"]["bootstrap_iters"]
    for new, old in pairs:
        if new in oof and old in oof:
            dl = delong_roc_test(y_ref, oof[old], oof[new])
            ni = idi_nri(y_ref, oof[old], oof[new])
            ci = bootstrap_ci(lambda yy, a, b: delong_roc_test(yy, a, b)["delta"],
                              y_ref, oof[old], oof[new], g_ref, n_iter=nb, seed=seed)
            contrasts.append({"contrast": f"{new}_vs_{old}",
                              "delta_auroc": dl["delta"], "delong_p": dl["p_value"],
                              "delta_auroc_ci95": ci, **ni,
                              "primary": (new == "pk" and old == "comprehensive")})
    result["incremental_value"] = contrasts

    # negative control (Sec 11.5): shuffle labels -> AUROC ~ 0.5
    rng = np.random.default_rng(seed)
    biggest = sets[-1]
    y_shuf = rng.permutation(y_ref)
    df_shuf = df.copy(); df_shuf["aki"] = y_shuf
    p_shuf, _, _ = oof_predictions(df_shuf, biggest, modules, model_name, cfg, seed)
    result["negative_control"] = {"set": biggest, "auroc_shuffled": _disc(y_shuf, p_shuf)["auroc"]}

    out = os.path.join(cfg["data"]["cache_dir"], f"incremental_value_{model_name}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    return result
