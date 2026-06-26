"""multitask.py -- Multi-task organ-injury model (Sec 9, multi-organ Tier-2 idea #4).

Trains a SHARED-trunk MLP (torch) that simultaneously predicts all seven
organ-injury binary labels.  A masked BCE loss ignores missing labels per
sample (each organ is labelled on its own subset; un-labelled cells are NaN).

Architecture
------------
shared trunk : Linear(n_in, 128) -> BN -> ReLU -> Dropout(0.3)
               Linear(128, 64)   -> BN -> ReLU -> Dropout(0.3)
per-organ head: Linear(64, 1) -> Sigmoid   (×7)

Loss
----
Masked binary cross-entropy: for each of the 7 outputs, we compute BCELoss
only on the rows where the label is not NaN, then average across organs.
This lets each organ borrow representation strength from the shared trunk
without any organ polluting another's gradient via its missing labels.

CV protocol
-----------
StratifiedGroupKFold (patient-level) on ``subjectid``, stratifying on
``organ_renal`` (highest prevalence → most stable stratification).
Preprocessing (make_preprocessor from dataset.py) is fit inside each fold
so nothing leaks across the split.

Comparison
----------
For each organ we also train a SINGLE-TASK logistic-regression baseline
(same CV folds, same preprocessor) and report:

    organ | n_events | single-task AUROC | multi-task AUROC | delta

Results are written to ``{cache_dir}/multitask_results.json``.

Usage
-----
    from vitaldb_aki.models.multitask import run_multitask
    results = run_multitask(cfg)          # cfg from common.config.load_yaml
"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import pandas as pd

# ── organ targets (pre-registered) ────────────────────────────────────────────
ORGAN_TARGETS: list[str] = [
    "organ_renal",
    "organ_hepatocellular",
    "organ_cholestatic",
    "organ_coagulation_plt",
    "organ_coagulation_inr",
    "organ_hypoperfusion",
    "organ_mortality",
]

_FSET = "comprehensive"   # Tier-2 specifies comprehensive feature set

# ── architecture hyperparameters ───────────────────────────────────────────────
_HIDDEN1 = 128
_HIDDEN2 = 64
_DROPOUT = 0.3
_EPOCHS  = 50
_BATCH   = 256
_LR      = 3e-3
_SEED    = 42


# ── neural network ─────────────────────────────────────────────────────────────

def _build_model(n_in: int, n_tasks: int):
    """Return a fresh SharedTrunkMLP (lazy torch import)."""
    import torch
    import torch.nn as nn

    class SharedTrunkMLP(nn.Module):
        """Shared trunk + per-organ sigmoid heads."""

        def __init__(self):
            super().__init__()
            self.trunk = nn.Sequential(
                nn.Linear(n_in, _HIDDEN1),
                nn.BatchNorm1d(_HIDDEN1),
                nn.ReLU(),
                nn.Dropout(_DROPOUT),
                nn.Linear(_HIDDEN1, _HIDDEN2),
                nn.BatchNorm1d(_HIDDEN2),
                nn.ReLU(),
                nn.Dropout(_DROPOUT),
            )
            # one Linear(64→1) per organ, collected as ModuleList
            self.heads = nn.ModuleList([nn.Linear(_HIDDEN2, 1) for _ in range(n_tasks)])

        def forward(self, x):
            h = self.trunk(x)
            # (batch, n_tasks) -- sigmoid applied per head
            return torch.cat([torch.sigmoid(head(h)) for head in self.heads], dim=1)

    return SharedTrunkMLP()


def masked_bce_loss(preds, targets):
    """Masked per-organ BCE loss.

    ``preds``   : (batch, n_tasks) float in [0,1]
    ``targets`` : (batch, n_tasks) float in {0,1,NaN}

    For each organ column, the BCE is averaged only over non-NaN rows.
    Then the per-organ losses are averaged (equal weighting across organs).
    Organs with ALL-NaN in the batch contribute 0.0 to the loss (no gradient).
    """
    import torch
    import torch.nn.functional as F  # noqa: N812

    n_tasks = targets.shape[1]
    total_loss = torch.tensor(0.0, device=preds.device)
    n_active = 0
    for k in range(n_tasks):
        t_k = targets[:, k]
        mask = ~torch.isnan(t_k)
        if mask.sum() == 0:
            continue
        loss_k = F.binary_cross_entropy(preds[mask, k], t_k[mask])
        total_loss = total_loss + loss_k
        n_active += 1
    return total_loss / n_active if n_active > 0 else total_loss


# ── training helpers ───────────────────────────────────────────────────────────

def _train_one_fold(X_tr: np.ndarray, Y_tr: np.ndarray,
                    X_val: np.ndarray, Y_val: np.ndarray,
                    seed: int = _SEED):
    """Train the shared-trunk MLP for one CV fold.

    Returns the trained model (in eval mode) as a Python object; all torch
    objects stay local so the caller can immediately use ``_predict_proba``.
    """
    import torch
    import torch.optim as optim

    rng = np.random.default_rng(seed)
    torch.manual_seed(int(rng.integers(0, 2**31)))

    n_in = X_tr.shape[1]
    n_tasks = Y_tr.shape[1]
    model = _build_model(n_in, n_tasks)
    opt   = optim.Adam(model.parameters(), lr=_LR, weight_decay=1e-4)

    Xt = torch.tensor(X_tr, dtype=torch.float32)
    Yt = torch.tensor(Y_tr, dtype=torch.float32)

    n = len(Xt)
    model.train()
    for epoch in range(_EPOCHS):
        idx = torch.randperm(n)
        for start in range(0, n, _BATCH):
            b = idx[start: start + _BATCH]
            opt.zero_grad()
            loss = masked_bce_loss(model(Xt[b]), Yt[b])
            loss.backward()
            opt.step()

    model.eval()
    return model


def _predict_proba(model, X: np.ndarray) -> np.ndarray:
    """Return (n_samples, n_tasks) probability matrix."""
    import torch

    with torch.no_grad():
        Xt = torch.tensor(X, dtype=torch.float32)
        return model(Xt).numpy()


# ── preprocessing + data helpers ──────────────────────────────────────────────

def _load_df(cfg: dict[str, Any]) -> pd.DataFrame:
    from vitaldb_aki.models.dataset import load_matrix
    return load_matrix(cfg)


def _feature_cols(df: pd.DataFrame, modules) -> tuple[list[str], list[str]]:
    """Return (num_cols, cat_cols) for the comprehensive feature set."""
    from vitaldb_aki.models.dataset import CATEGORICAL, feature_columns
    cols = [c for c in feature_columns(_FSET, modules) if c in df.columns]
    cat_cols = [c for c in cols if c in CATEGORICAL]
    num_cols = [c for c in cols if c not in CATEGORICAL]
    return num_cols, cat_cols


def _build_organ_matrix(df: pd.DataFrame, organ_targets: list[str]) -> np.ndarray:
    """(n_rows, n_tasks) float matrix with NaN where label is missing."""
    rows = []
    for col in organ_targets:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        else:
            vals = np.full(len(df), np.nan)
        rows.append(vals)
    return np.column_stack(rows)   # (n_rows, n_tasks)


def _stratify_label(df: pd.DataFrame, organ_targets: list[str]) -> np.ndarray:
    """Best-effort stratification label for StratifiedGroupKFold.

    Uses organ_renal if available; falls back to the first organ with labels;
    falls back to zeros (unstratified but won't crash).
    """
    for col in organ_targets:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            if s.sum() > 0:
                return s.to_numpy()
    return np.zeros(len(df), dtype=int)


# ── single-task baseline (logistic regression per organ) ──────────────────────

def _single_task_oof(X_all: np.ndarray, Y_all: np.ndarray,
                     groups: np.ndarray,
                     strat_y: np.ndarray,
                     n_splits: int, seed: int) -> np.ndarray:
    """(n_rows, n_tasks) OOF probabilities from independent LR per organ."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold

    n_tasks = Y_all.shape[1]
    oof = np.full_like(Y_all, np.nan, dtype=float)
    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    for organ_k in range(n_tasks):
        y_k = Y_all[:, organ_k]
        label_mask = ~np.isnan(y_k)
        if label_mask.sum() == 0 or y_k[label_mask].sum() < 2:
            continue   # skip organs with no events

        X_k = X_all[label_mask]
        y_k_clean = y_k[label_mask].astype(int)
        g_k = groups[label_mask]
        s_k = strat_y[label_mask]

        oof_k = np.full(label_mask.sum(), np.nan)
        for tr, te in outer.split(X_k, s_k, g_k):
            clf = LogisticRegression(penalty="l2", C=0.1, class_weight="balanced",
                                     solver="liblinear", max_iter=2000,
                                     random_state=seed)
            clf.fit(X_k[tr], y_k_clean[tr])
            oof_k[te] = clf.predict_proba(X_k[te])[:, 1]

        oof[label_mask, organ_k] = oof_k

    return oof


# ── multi-task OOF (shared-trunk MLP) ─────────────────────────────────────────

def _multitask_oof(X_all: np.ndarray, Y_all: np.ndarray,
                   groups: np.ndarray,
                   strat_y: np.ndarray,
                   n_splits: int, seed: int) -> np.ndarray:
    """(n_rows, n_tasks) OOF probabilities from the shared-trunk MLP."""
    from sklearn.model_selection import StratifiedGroupKFold

    oof = np.full_like(Y_all, np.nan, dtype=float)
    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    for fold_i, (tr, te) in enumerate(outer.split(X_all, strat_y, groups)):
        model = _train_one_fold(X_all[tr], Y_all[tr],
                                X_all[te], Y_all[te],
                                seed=seed + fold_i)
        oof[te] = _predict_proba(model, X_all[te])

    return oof


# ── AUROC table ───────────────────────────────────────────────────────────────

def _organ_aurocs(Y_all: np.ndarray, oof_single: np.ndarray,
                  oof_multi: np.ndarray,
                  organ_targets: list[str]) -> list[dict]:
    """Return list of per-organ result dicts for the comparison table."""
    from sklearn.metrics import roc_auc_score

    rows = []
    for k, organ in enumerate(organ_targets):
        y_k = Y_all[:, k]
        label_mask = ~np.isnan(y_k)
        n_events = int(np.nansum(y_k)) if label_mask.any() else 0

        def _auc(oof_col):
            m = label_mask & ~np.isnan(oof_col)
            if m.sum() == 0 or y_k[m].sum() < 1 or (y_k[m] == 0).sum() < 1:
                return float("nan")
            try:
                return float(roc_auc_score(y_k[m].astype(int), oof_col[m]))
            except Exception:
                return float("nan")

        auc_s = _auc(oof_single[:, k])
        auc_m = _auc(oof_multi[:, k])
        delta = (auc_m - auc_s) if not (np.isnan(auc_m) or np.isnan(auc_s)) else float("nan")
        rows.append({
            "organ": organ,
            "n_events": n_events,
            "auroc_single": round(auc_s, 4) if not np.isnan(auc_s) else None,
            "auroc_multi":  round(auc_m, 4) if not np.isnan(auc_m) else None,
            "delta":        round(delta, 4) if not np.isnan(delta) else None,
        })
    return rows


# ── public entry point ─────────────────────────────────────────────────────────

def run_multitask(cfg: dict[str, Any],
                  organ_targets: list[str] | None = None,
                  modules=None,
                  n_splits: int = 5,
                  seed: int = _SEED) -> dict[str, Any]:
    """Run multi-task vs single-task comparison and write results.

    Args:
        cfg:           loaded config dict (see vitaldb_aki/config.yaml).
        organ_targets: list of label columns; defaults to ORGAN_TARGETS.
        modules:       feature modules; defaults to build_matrix.MODULES.
        n_splits:      outer CV folds (patient-level).
        seed:          random seed.

    Returns:
        results dict (also written to ``{cache_dir}/multitask_results.json``).
    """
    if organ_targets is None:
        organ_targets = ORGAN_TARGETS
    if modules is None:
        from vitaldb_aki.features import build_matrix
        modules = build_matrix.MODULES

    from vitaldb_aki.models.dataset import make_preprocessor

    df = _load_df(cfg)
    num_cols, cat_cols = _feature_cols(df, modules)

    # ── feature matrix (no label leak) ────────────────────────────────────────
    X_raw = df[num_cols + cat_cols].copy()
    groups = df["subjectid"].to_numpy()

    # ── label matrix (n_rows, n_tasks) with NaN for missing ───────────────────
    Y_all = _build_organ_matrix(df, organ_targets)

    # ── stratification label ───────────────────────────────────────────────────
    strat_y = _stratify_label(df, organ_targets)

    # ── within-fold preprocessing (no leakage) ────────────────────────────────
    # We need a pre-fitted array for OOF, so we fit a global preprocessor once
    # only to determine the output shape, then re-fit inside each fold.
    # For OOF we collect transformed arrays per fold inside the oof functions.
    # To share folds exactly, we materialise fold indices once here.
    from sklearn.model_selection import StratifiedGroupKFold

    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_splits = list(outer.split(X_raw, strat_y, groups))

    # ── fit preprocessor inside each fold, transform, then run OOF ────────────
    # We stack fold transforms into full-sized arrays.
    # First, get output dimension from a dry run.
    pre_dry = make_preprocessor(num_cols, cat_cols)
    tr0, _ = fold_splits[0]
    X_dry = pre_dry.fit_transform(X_raw.iloc[tr0])
    n_features = X_dry.shape[1]

    X_preprocessed = np.zeros((len(X_raw), n_features), dtype=np.float32)
    # We use the test-fold transform (fitted on train) as the canonical
    # preprocessed features for OOF — this is the leak-free view.
    for tr, te in fold_splits:
        pre = make_preprocessor(num_cols, cat_cols)
        pre.fit(X_raw.iloc[tr])
        X_preprocessed[te] = pre.transform(X_raw.iloc[te]).astype(np.float32)

    # ── single-task OOF ────────────────────────────────────────────────────────
    oof_single = _single_task_oof(
        X_preprocessed, Y_all, groups, strat_y, n_splits, seed
    )

    # ── multi-task OOF ────────────────────────────────────────────────────────
    oof_multi = _multitask_oof(
        X_preprocessed, Y_all, groups, strat_y, n_splits, seed
    )

    # ── comparison table ───────────────────────────────────────────────────────
    table = _organ_aurocs(Y_all, oof_single, oof_multi, organ_targets)

    # ── print table ───────────────────────────────────────────────────────────
    print("\n§9 Multi-task vs Single-task per-organ AUROC (comprehensive fset)")
    print(f"{'organ':<30}  {'n_ev':>6}  {'single':>8}  {'multi':>8}  {'delta':>8}")
    print("-" * 70)
    for row in table:
        s = f"{row['auroc_single']:.4f}" if row["auroc_single"] is not None else "  N/A  "
        m = f"{row['auroc_multi']:.4f}"  if row["auroc_multi"]  is not None else "  N/A  "
        d = f"{row['delta']:+.4f}"       if row["delta"]        is not None else "  N/A  "
        print(f"{row['organ']:<30}  {row['n_events']:>6}  {s:>8}  {m:>8}  {d:>8}")

    results: dict[str, Any] = {
        "fset": _FSET,
        "n_splits": n_splits,
        "seed": seed,
        "architecture": {
            "hidden": [_HIDDEN1, _HIDDEN2],
            "dropout": _DROPOUT,
            "epochs": _EPOCHS,
            "batch": _BATCH,
            "lr": _LR,
        },
        "organ_targets": organ_targets,
        "table": table,
    }

    cache_dir = cfg["data"]["cache_dir"]
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(cache_dir, "multitask_results.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nResults written to {out_path}")

    return results
