"""site_probe.py -- THE GATE (Sec 8, 11).

After correction, attempt to predict hospital / device / sampling-rate from the
corrected embeddings. If any is predictable above a chance tolerance, correction
has failed: escalate (Route B) or reject the affected structure. Phenotypes that
align with site predictions are rejected (Sec 8, 9).

scikit-learn is imported lazily.
"""
from __future__ import annotations

from typing import Any


def probe_site(X, labels, cfg: dict[str, Any]) -> dict[str, Any]:
    """Cross-validated multiclass AUC for predicting `labels` from `X`.

    Returns {auc, pass, n_classes, chance_auc}. `pass` is True when the probe is
    at/near chance (AUC <= tolerance), i.e. site identity is *not* recoverable.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import label_binarize

    X = np.asarray(X, dtype="float64")
    labels = np.asarray(labels)
    classes = np.unique(labels)
    n_classes = len(classes)
    tol = cfg.get("site_invariance", {}).get("site_probe", {}).get(
        "chance_tolerance_auc", 0.58
    )
    folds = cfg.get("site_invariance", {}).get("site_probe", {}).get("cv_folds", 5)

    if n_classes < 2:
        return {"auc": 0.5, "pass": True, "n_classes": int(n_classes),
                "chance_auc": 0.5, "tolerance": tol}

    skf = StratifiedKFold(n_splits=min(folds, _min_class_count(labels)),
                          shuffle=True, random_state=cfg.get("seed", 0))
    y_true_all, y_score_all = [], []
    for tr, te in skf.split(X, labels):
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X[tr], labels[tr])
        proba = clf.predict_proba(X[te])
        y_true_all.append(labels[te])
        y_score_all.append((proba, clf.classes_))

    # Aggregate one-vs-rest AUC across folds.
    aucs = []
    for (yt, (proba, cls)) in zip(y_true_all, y_score_all):
        yb = label_binarize(yt, classes=cls)
        if yb.shape[1] == 1:  # binary edge case
            try:
                aucs.append(roc_auc_score(yt == cls[1], proba[:, 1]))
            except ValueError:
                continue
        else:
            try:
                aucs.append(roc_auc_score(yb, proba, average="macro",
                                          multi_class="ovr"))
            except ValueError:
                continue
    auc = float(np.mean(aucs)) if aucs else 0.5
    return {"auc": auc, "pass": auc <= tol, "n_classes": int(n_classes),
            "chance_auc": 0.5, "tolerance": tol}


def _min_class_count(labels) -> int:
    import numpy as np
    _, counts = np.unique(labels, return_counts=True)
    return max(2, int(counts.min()))
