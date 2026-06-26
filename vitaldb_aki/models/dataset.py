"""dataset.py -- turn the feature matrix into model inputs (Sec 9-11).

Builds (X, y, groups) for a chosen NESTED feature set (standard | comprehensive |
pk, Sec 9) and a preprocessing pipeline that is fit INSIDE each CV fold (median
imputation + missingness indicator + scaling for numerics; capped one-hot for the
two categoricals) so nothing leaks across the split (Sec 11). `groups` is the
patient id for patient-level splitting (Sec 11.6).
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from vitaldb_aki.features.base import names_for_set
from vitaldb_aki.features import tabular

# Registered modules whose SPECS define the available features + their set tags.
# Kept in sync with features/build_matrix.MODULES as stages land.
def _all_specs(modules):
    specs = []
    for m in modules:
        specs.extend(m.SPECS)
    return specs


CATEGORICAL = ("optype", "department")


def load_matrix(cfg: dict[str, Any]) -> pd.DataFrame:
    path = os.path.join(cfg["data"]["cache_dir"], "feature_matrix.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} -- run features/build_matrix first")
    return pd.read_csv(path)


def feature_columns(fset: str, modules) -> list[str]:
    return names_for_set(_all_specs(modules), fset)


def build_xy(df: pd.DataFrame, fset: str, modules):
    """Return (X: DataFrame, y: int array, groups: array, num_cols, cat_cols)."""
    cols = [c for c in feature_columns(fset, modules) if c in df.columns]
    cat_cols = [c for c in cols if c in CATEGORICAL]
    num_cols = [c for c in cols if c not in CATEGORICAL]
    X = df[cols].copy()
    y = df["aki"].astype(int).to_numpy()
    groups = df["subjectid"].to_numpy()
    return X, y, groups, num_cols, cat_cols


def make_preprocessor(num_cols, cat_cols, max_cat=6):
    """Within-fold preprocessing. Numerics: median impute (+ missing-indicator) +
    scale. Categoricals: most-frequent impute + capped one-hot (max_cat) so the
    143-event budget isn't blown on rare surgery types (Sec 10)."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    num_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    transformers = [("num", num_pipe, num_cols)]
    if cat_cols:
        cat_pipe = Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("oh", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                 max_categories=max_cat, min_frequency=20,
                                 sparse_output=False)),
        ])
        transformers.append(("cat", cat_pipe, cat_cols))
    return ColumnTransformer(transformers, remainder="drop")


def events_per_variable(df: pd.DataFrame, fset: str, modules) -> dict[str, Any]:
    """EPV accounting (Sec 10): events / number of model inputs (post-encoding is
    larger, but this raw count flags the danger)."""
    X, y, _, num_cols, cat_cols = build_xy(df, fset, modules)
    n_events = int(y.sum())
    n_vars = len(num_cols) + len(cat_cols)
    return {"set": fset, "n_events": n_events, "n_raw_features": n_vars,
            "epv": round(n_events / n_vars, 2) if n_vars else None}
