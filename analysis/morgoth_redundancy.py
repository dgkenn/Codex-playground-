"""morgoth_redundancy.py -- the MORGOTH-finding redundancy / novelty control
(Pre-Registration v3, Sec 9(4), Sec 13.3).

Because the backbone (MORGOTH) was pretrained on HEEDB and fine-tuned to emit the
known clinical findings, its embedding already encodes them -- so a "discovered"
phenotype risks being a re-expression of an existing model output. This module
operationalises the mandatory requirement that a phenotype carry information
*beyond* the model's own task outputs. It is BOTH the novelty criterion and a
leakage control: a phenotype that is merely a relabelling of a model finding
cannot pass.

Mechanism: for each phenotype, ask how well its membership is predictable from
the model's task-output vector (the 17 EEG-level findings + the 6-class IIIC
posterior + sleep stage + spike/slowing/burst-suppression). A phenotype is
*reducible* (fails novelty) if that prediction is too good.

Backbone-agnostic: pass any per-recording matrix of model task outputs. With the
CBraMod backbone (no task heads) there are no such outputs, so the check is
skipped; with MORGOTH it runs. The Phase-2 counterpart is covariate adjustment
for these same findings (see phase2.adjusted_association covariates).

NumPy / scikit-learn are imported lazily.
"""
from __future__ import annotations

from typing import Any


def _cv_auc(X, y, seed: int, folds: int = 5) -> float:
    """Cross-validated AUC of predicting binary y from X (chance = 0.5)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    X = np.asarray(X, dtype="float64")
    y = np.asarray(y).astype(int)
    if len(set(y.tolist())) < 2:
        return 0.5
    _, counts = np.unique(y, return_counts=True)
    n_splits = int(min(folds, counts.min()))
    if n_splits < 2:
        return 0.5
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    scores = []
    for tr, te in skf.split(X, y):
        if len(set(y[tr].tolist())) < 2:
            continue
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X[tr], y[tr])
        proba = clf.predict_proba(X[te])[:, 1]
        try:
            scores.append(roc_auc_score(y[te], proba))
        except ValueError:
            continue
    return float(np.mean(scores)) if scores else 0.5


def redundancy_check(labels, model_outputs, cfg: dict[str, Any]) -> dict[str, Any]:
    """Per-phenotype redundancy against the model's task outputs (Sec 13.3).

    `labels`        -- phenotype assignment per recording.
    `model_outputs` -- (n, m) matrix of the backbone's task-output probabilities
                       (findings/IIIC/sleep/...); None or empty -> check skipped.
    Returns, per phenotype, the AUC of predicting its membership from the model
    outputs and whether it is `reducible` (AUC >= the pre-specified threshold ->
    fails novelty). `novel_phenotypes` lists those that carry information beyond
    the model outputs.
    """
    import numpy as np

    thr = cfg.get("audits", {}).get("morgoth_redundancy", {}).get(
        "max_predictable_auc", 0.80)
    if model_outputs is None:
        return {"applicable": False, "reason": "no model task outputs "
                "(backbone has no task heads); redundancy control not applied",
                "threshold": thr, "per_phenotype": {}, "novel_phenotypes": []}

    M = np.asarray(model_outputs, dtype="float64")
    labels = np.asarray(labels)
    if M.ndim != 2 or M.shape[0] != labels.shape[0] or M.shape[0] == 0:
        return {"applicable": False, "reason": "model_outputs shape mismatch",
                "threshold": thr, "per_phenotype": {}, "novel_phenotypes": []}

    seed = cfg.get("seed", 0)
    per: dict[int, dict[str, Any]] = {}
    for c in sorted(set(labels.tolist())):
        auc = _cv_auc(M, labels == c, seed)
        per[int(c)] = {"predictable_auc": round(auc, 4),
                       "reducible": bool(auc >= thr),
                       "novelty_residual": round(max(0.0, 1.0 - auc), 4)}
    novel = [c for c, d in per.items() if not d["reducible"]]
    return {"applicable": True, "threshold": thr, "per_phenotype": per,
            "novel_phenotypes": sorted(novel),
            "n_reducible": sum(1 for d in per.values() if d["reducible"])}


def annotate_phenotype_bar(bar: dict[str, Any], redundancy: dict[str, Any]) -> dict[str, Any]:
    """Fold the redundancy result into a phenotype-bar decision dict: any admitted
    phenotype that is reducible to the model outputs is demoted to 'rejected'
    with reason 'morgoth_redundant' (Sec 9(4)). No-op when the check did not apply.
    """
    if not redundancy.get("applicable"):
        bar = dict(bar)
        bar["morgoth_redundancy"] = "not applied (no model task outputs)"
        return bar
    decisions = dict(bar.get("decisions", {}))
    reducible = {c for c, d in redundancy["per_phenotype"].items() if d["reducible"]}
    for c in list(decisions):
        if int(c) in reducible and decisions[c].get("status") in ("provisional", "confirmed"):
            d = dict(decisions[c])
            d["status"] = "rejected"
            d["reasons"] = list(d.get("reasons", [])) + ["morgoth_redundant"]
            decisions[c] = d
    admitted = [c for c, d in decisions.items()
                if d["status"] in ("provisional", "confirmed")]
    out = dict(bar)
    out["decisions"] = decisions
    out["admitted"] = sorted(admitted)
    out["n_admitted"] = len(admitted)
    out["morgoth_redundancy"] = redundancy
    return out
