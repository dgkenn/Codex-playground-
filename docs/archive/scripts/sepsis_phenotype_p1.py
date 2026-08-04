#!/usr/bin/env python3
"""
Phase 1 -- Sepsis subphenotype discovery on MIMIC-IV (derivation arm).

Follows /home/user/Codex-playground-/docs/SUBPHENOTYPE_STUDY_DESIGN.md and the
Phase-1 task spec exactly:
  - ICD-anchored sepsis cohort (we lack a clean antibiotics table -> honestly
    labeled "ICD-anchored Sepsis", NOT full Sepsis-3 with antibiotic timing).
  - First-24h LEVEL (median) + TRAJECTORY (slope, CV) features, z-scored.
  - k chosen by bootstrap-ARI STABILITY (2..6), not by outcome separation.
  - Phenotype profiles + mortality with 95% CI at the primary k.
  - Centroids + scaler frozen to sepsis_p1_model.npz for Phase-2 cross-site use.

DUA data lives only in this scratchpad dir; nothing raw is written outside it,
and no raw row-level data is committed (aggregate results only, per instructions).
"""
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

DATA = Path(__file__).parent
OUT = DATA
RNG_SEED = 42
N_BOOT = 50
K_RANGE = range(2, 7)
COVERAGE_MIN = 0.60
WINDOW_HOURS = 24.0

LAB_FILES = {
    "lab_creat": "creatinine", "lab_bun": "bun", "lab_lactate": "lactate",
    "lab_hb": "hemoglobin", "lab_hct": "hematocrit", "lab_plt": "platelets",
    "lab_na": "sodium", "lab_k": "potassium", "lab_hco3": "bicarbonate",
    "lab_glu": "glucose", "lab_ca": "calcium", "lab_cl": "chloride",
    "lab_mg": "magnesium", "lab_inr": "inr", "lab_alb": "albumin",
    "lab_ph": "ph", "lab_pco2": "pco2",
}
VITAL_FILES = {"chart_hr": "hr", "chart_spo2": "spo2", "chart_rr": "rr"}

ICD9_SEPSIS = {"99591", "99592", "78552"}
ICD10_SEPSIS_PREFIX = ("A40", "A41")
ICD10_SEPSIS_EXACT = {"R6520", "R6521"}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# 1. Cohort construction
# --------------------------------------------------------------------------
def build_base_cohort():
    log("Loading patients/icustays/admissions ...")
    patients = pd.read_csv(
        DATA / "patients.csv",
        usecols=["subject_id", "anchor_age", "dod"],
        dtype={"subject_id": "int64", "anchor_age": "int32"},
        parse_dates=["dod"],
    )
    icu = pd.read_csv(
        DATA / "icustays.csv",
        usecols=["subject_id", "hadm_id", "stay_id", "first_careunit", "intime", "outtime", "los"],
        dtype={"subject_id": "int64", "hadm_id": "int64", "stay_id": "int64", "los": "float64"},
        parse_dates=["intime", "outtime"],
    )
    adm = pd.read_csv(
        DATA / "admissions.csv",
        usecols=["subject_id", "hadm_id", "admittime", "hospital_expire_flag"],
        dtype={"subject_id": "int64", "hadm_id": "int64", "hospital_expire_flag": "int8"},
        parse_dates=["admittime"],
    )

    n0_stays = len(icu)
    n0_hadm = icu["hadm_id"].nunique()
    log(f"  raw icustays rows={n0_stays}, unique hadm_id={n0_hadm}")

    # "First ICU stay" = per hadm_id, earliest intime (collapses ICU-to-ICU
    # transfers within one hospitalization to a single index stay).
    icu = icu.sort_values("intime")
    icu_first = icu.groupby("hadm_id", as_index=False).first()
    log(f"  after collapsing to earliest ICU stay per hadm_id: n={len(icu_first)}")

    cohort = icu_first.merge(patients, on="subject_id", how="left")
    cohort = cohort.merge(adm, on=["subject_id", "hadm_id"], how="left")

    n_before_age = len(cohort)
    cohort = cohort[cohort["anchor_age"] >= 18]
    log(f"  age>=18: {n_before_age} -> {len(cohort)}")

    n_before_los = len(cohort)
    cohort = cohort[cohort["los"] >= 1.0]  # los is in days; >=24h
    log(f"  ICU LOS>=24h: {n_before_los} -> {len(cohort)}")

    dup_subjects = cohort["subject_id"].duplicated().sum()
    log(f"  NOTE: {dup_subjects} rows are repeat hospitalizations of a subject "
        f"already in the cohort (unit of analysis = hadm_id per task spec, "
        f"not deduped further to one-per-subject).")

    cohort = cohort.set_index("hadm_id", drop=False)
    return cohort


def flag_sepsis(cohort):
    hadm_ids = set(cohort["hadm_id"])
    log("Scanning diagnoses_icd.csv for sepsis ICD codes ...")
    sepsis_hadm = set()
    reader = pd.read_csv(
        DATA / "diagnoses_icd.csv",
        usecols=["hadm_id", "icd_code", "icd_version"],
        dtype={"hadm_id": "int64", "icd_code": "str", "icd_version": "int8"},
        chunksize=1_000_000,
    )
    for chunk in reader:
        chunk = chunk[chunk["hadm_id"].isin(hadm_ids)]
        if chunk.empty:
            continue
        codes = chunk["icd_code"].str.strip()
        is9 = (chunk["icd_version"] == 9) & codes.isin(ICD9_SEPSIS)
        is10 = (chunk["icd_version"] == 10) & (
            codes.str.startswith(ICD10_SEPSIS_PREFIX) | codes.isin(ICD10_SEPSIS_EXACT)
        )
        sepsis_hadm.update(chunk.loc[is9 | is10, "hadm_id"].tolist())

    n_before = len(cohort)
    cohort = cohort[cohort["hadm_id"].isin(sepsis_hadm)]
    log(f"  sepsis ICD-9/10 present: {n_before} -> {len(cohort)}")
    return cohort


def load_window(fname, intime_map, value_col="valuenum", extra_cols=None):
    """Load a hadm_id,charttime,valuenum CSV, restrict to cohort hadm_ids and
    the first-24h window [intime, intime+24h]. Returns hadm_id, hours_since, value."""
    usecols = ["hadm_id", "charttime", value_col] + (extra_cols or [])
    df = pd.read_csv(
        DATA / fname,
        usecols=usecols,
        dtype={"hadm_id": "int64", value_col: "float32"},
        parse_dates=["charttime"],
    )
    df = df[df["hadm_id"].isin(intime_map.index)]
    if df.empty:
        return df.assign(hours_since=pd.Series(dtype="float64"))
    df["intime"] = df["hadm_id"].map(intime_map)
    df["hours_since"] = (df["charttime"] - df["intime"]).dt.total_seconds() / 3600.0
    df = df[(df["hours_since"] >= 0) & (df["hours_since"] <= WINDOW_HOURS)]
    return df


def flag_organ_dysfunction(cohort):
    intime_map = cohort["intime"]
    n_before = len(cohort)
    log("Checking organ dysfunction criteria in first 24h ...")

    flags = pd.DataFrame(index=cohort["hadm_id"])
    flags["creat"] = False
    flags["plt"] = False
    flags["map"] = False
    flags["lactate"] = False
    flags["vent"] = False

    creat = load_window("lab_creat.csv", intime_map)
    hi = creat.groupby("hadm_id")["valuenum"].max()
    flags.loc[flags.index.isin(hi[hi >= 2.0].index), "creat"] = True

    plt = load_window("lab_plt.csv", intime_map)
    lo = plt.groupby("hadm_id")["valuenum"].min()
    flags.loc[flags.index.isin(lo[lo < 100].index), "plt"] = True

    lac = load_window("lab_lactate.csv", intime_map)
    hi = lac.groupby("hadm_id")["valuenum"].max()
    flags.loc[flags.index.isin(hi[hi >= 2.0].index), "lactate"] = True

    abpm = load_window("chart_abpm.csv", intime_map)
    nbpm = load_window("chart_nbpm.csv", intime_map)
    lo_a = abpm.groupby("hadm_id")["valuenum"].min()
    lo_n = nbpm.groupby("hadm_id")["valuenum"].min()
    low_map_hadm = set(lo_a[lo_a < 65].index) | set(lo_n[lo_n < 65].index)
    flags.loc[flags.index.isin(low_map_hadm), "map"] = True

    # vasopressor overlapping the 24h window
    vaso = pd.read_csv(
        DATA / "vaso.csv",
        usecols=["hadm_id", "starttime", "endtime"],
        dtype={"hadm_id": "int64"},
        parse_dates=["starttime", "endtime"],
    )
    vaso = vaso[vaso["hadm_id"].isin(intime_map.index)]
    vaso["intime"] = vaso["hadm_id"].map(intime_map)
    vaso["window_end"] = vaso["intime"] + pd.Timedelta(hours=WINDOW_HOURS)
    on_vaso = vaso[(vaso["starttime"] <= vaso["window_end"]) & (vaso["endtime"] >= vaso["intime"])]
    flags.loc[flags.index.isin(on_vaso["hadm_id"].unique()), "map"] = True

    # invasive mechanical ventilation overlapping the 24h window
    vent = pd.read_csv(
        DATA / "vent.csv",
        usecols=["hadm_id", "starttime", "endtime", "kind"],
        dtype={"hadm_id": "int64"},
        parse_dates=["starttime", "endtime"],
    )
    vent = vent[(vent["hadm_id"].isin(intime_map.index)) & (vent["kind"] == "invasive")]
    vent["intime"] = vent["hadm_id"].map(intime_map)
    vent["window_end"] = vent["intime"] + pd.Timedelta(hours=WINDOW_HOURS)
    on_vent = vent[(vent["starttime"] <= vent["window_end"]) & (vent["endtime"] >= vent["intime"])]
    flags.loc[flags.index.isin(on_vent["hadm_id"].unique()), "vent"] = True

    any_dys = flags.any(axis=1)
    for col, label in [
        ("creat", "creatinine>=2"), ("plt", "platelets<100"),
        ("map", "MAP<65 or vasopressor"), ("lactate", "lactate>=2"),
        ("vent", "invasive mechanical ventilation"),
    ]:
        log(f"  {label}: {int(flags[col].sum())} / {len(flags)} hadm_ids")

    cohort = cohort[cohort["hadm_id"].isin(flags.index[any_dys])]
    log(f"  >=1 organ dysfunction: {n_before} -> {len(cohort)}")
    return cohort, flags.loc[flags.index.isin(cohort["hadm_id"])]


# --------------------------------------------------------------------------
# 2. Feature extraction: level (median), trajectory (slope), CV
# --------------------------------------------------------------------------
def level_traj_cv(df):
    """Vectorized per-hadm_id median / OLS-slope-vs-hours_since / CV."""
    if df.empty:
        return pd.DataFrame(columns=["level", "slope", "cv"])
    g = df.groupby("hadm_id")
    n = g.size()
    level = g["valuenum"].median()
    mean = g["valuenum"].mean()
    std = g["valuenum"].std(ddof=1)
    cv = std / mean.replace(0, np.nan)

    sx = g["hours_since"].sum()
    sxx = df.assign(x2=df["hours_since"] ** 2).groupby("hadm_id")["x2"].sum()
    sy = g["valuenum"].sum()
    sxy = df.assign(xy=df["hours_since"] * df["valuenum"]).groupby("hadm_id")["xy"].sum()
    denom = n * sxx - sx ** 2
    slope = (n * sxy - sx * sy) / denom.replace(0, np.nan)
    slope[n < 2] = np.nan

    out = pd.DataFrame({"level": level, "slope": slope, "cv": cv})
    return out


def extract_features(cohort):
    intime_map = cohort["intime"]
    hadm_index = cohort["hadm_id"]
    feature_frames = {}

    log("Extracting lab features (level/slope/cv) ...")
    for fname, short in LAB_FILES.items():
        df = load_window(f"{fname}.csv", intime_map)
        stats_df = level_traj_cv(df)
        feature_frames[short] = stats_df
        log(f"  {short}: {len(stats_df)} hadm_ids with data")

    log("Extracting vital-sign features (level/slope/cv) ...")
    for fname, short in VITAL_FILES.items():
        df = load_window(f"{fname}.csv", intime_map)
        stats_df = level_traj_cv(df)
        feature_frames[short] = stats_df
        log(f"  {short}: {len(stats_df)} hadm_ids with data")

    # MAP: prefer invasive (abpm); fallback to non-invasive (nbpm) per patient
    log("Extracting MAP (abpm preferred, nbpm fallback) ...")
    abpm = load_window("chart_abpm.csv", intime_map)
    nbpm = load_window("chart_nbpm.csv", intime_map)
    abpm_stats = level_traj_cv(abpm)
    nbpm_stats = level_traj_cv(nbpm)
    map_stats = abpm_stats.combine_first(nbpm_stats)  # abpm rows win where present
    n_abpm_only = len(set(abpm_stats.index) - set(nbpm_stats.index))
    n_nbpm_fallback = len(set(nbpm_stats.index) - set(abpm_stats.index))
    log(f"  MAP: {len(abpm_stats)} via abpm, {n_nbpm_fallback} additional via nbpm fallback, "
        f"total {len(map_stats)} hadm_ids")
    feature_frames["map"] = map_stats

    # assemble wide feature matrix: one column per (variable, level/slope/cv)
    hadm_id_values = pd.Index(hadm_index.values, name="hadm_id")
    cols = {}
    for short, stats_df in feature_frames.items():
        for stat in ["level", "slope", "cv"]:
            if stat in stats_df.columns:
                s = stats_df[stat].reindex(hadm_id_values)
            else:
                s = pd.Series(np.nan, index=hadm_id_values)
            cols[f"{short}_{stat}"] = s.values

    X = pd.DataFrame(cols, index=hadm_id_values)
    return X


# --------------------------------------------------------------------------
# 3. Coverage filter, imputation, standardization
# --------------------------------------------------------------------------
def clean_matrix(X):
    coverage = X.notna().mean(axis=1)
    n_before = len(X)
    keep = coverage >= COVERAGE_MIN
    log(f"Feature coverage: mean={coverage.mean():.3f}, median={coverage.median():.3f}; "
        f"dropping {(~keep).sum()} of {n_before} rows with <{COVERAGE_MIN:.0%} coverage")
    X = X.loc[keep]
    cov_kept = coverage.loc[keep]

    medians = X.median(axis=0)
    X_imputed = X.fillna(medians)

    scaler = StandardScaler()
    Xz = scaler.fit_transform(X_imputed.values)
    Xz = pd.DataFrame(Xz, index=X.index, columns=X.columns)
    return X_imputed, Xz, scaler, cov_kept, medians


# --------------------------------------------------------------------------
# 4. Consensus k-means: bootstrap ARI stability + silhouette
# --------------------------------------------------------------------------
def bootstrap_stability(Xz_values, k, n_boot=N_BOOT, seed=RNG_SEED, consensus_subsample=1500):
    """Bootstrap cluster stability: refit k-means on 50 bootstrap resamples,
    predict ALL patients from each bootstrap-fit model, and compare to the
    full-data reference clustering via ARI (the primary stability metric).
    Also builds a Monti-style consensus (co-clustering) matrix on a random
    subsample of patients (capped at `consensus_subsample`) to keep memory
    bounded for large n, and reports its mean off-diagonal value as a
    secondary stability summary."""
    n = Xz_values.shape[0]
    rng = np.random.RandomState(seed)

    ref = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Xz_values)
    ref_labels = ref.labels_

    cons_idx = rng.choice(n, size=min(n, consensus_subsample), replace=False)
    m = len(cons_idx)
    consensus_counts = np.zeros((m, m), dtype=np.float32)

    aris = []
    for b in range(n_boot):
        idx = rng.randint(0, n, size=n)  # bootstrap resample with replacement
        boot_seed = seed + b + 1
        km = KMeans(n_clusters=k, n_init=5, random_state=boot_seed).fit(Xz_values[idx])
        pred_full = km.predict(Xz_values)  # assign ALL patients to bootstrap-fit centroids
        aris.append(adjusted_rand_score(ref_labels, pred_full))
        pred_sub = pred_full[cons_idx]
        consensus_counts += (pred_sub[:, None] == pred_sub[None, :])

    consensus_matrix = consensus_counts / n_boot
    off_diag_mask = ~np.eye(m, dtype=bool)
    consensus_mean_offdiag = float(consensus_matrix[off_diag_mask].mean())
    # bimodality of the consensus distribution (close to 0/1 = crisp, stable clusters)
    consensus_vals = consensus_matrix[off_diag_mask]
    consensus_crispness = float(np.mean((consensus_vals < 0.1) | (consensus_vals > 0.9)))

    sil = silhouette_score(Xz_values, ref_labels) if k > 1 else np.nan
    return {
        "k": k,
        "ref_labels": ref_labels,
        "aris": np.array(aris),
        "median_ari": float(np.median(aris)),
        "ari_q1": float(np.percentile(aris, 25)),
        "ari_q3": float(np.percentile(aris, 75)),
        "silhouette": float(sil),
        "consensus_mean_offdiag": consensus_mean_offdiag,
        "consensus_crispness": consensus_crispness,
        "centroids": ref.cluster_centers_,
    }


# --------------------------------------------------------------------------
# 5. Prognosis: mortality with Wilson 95% CI
# --------------------------------------------------------------------------
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = (z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))) / denom
    return p, max(0, center - half), min(1, center + half)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    t0 = time.time()
    cohort = build_base_cohort()
    cohort = flag_sepsis(cohort)
    cohort, organ_flags = flag_organ_dysfunction(cohort)
    n_final_cohort = len(cohort)
    log(f"Final cohort n={n_final_cohort} (t={time.time()-t0:.0f}s)")

    if n_final_cohort < 50:
        log("Cohort too small to proceed with clustering; aborting.")
        return

    CACHE = OUT / "sepsis_p1_featcache.pkl"
    if CACHE.exists():
        log("Loading cached feature matrix (delete sepsis_p1_featcache.pkl to rebuild) ...")
        Xz = pd.read_pickle(CACHE)
        cov = Xz.pop("_coverage") if "_coverage" in Xz.columns else pd.Series(1.0, index=Xz.index)
        X_imputed = Xz
        from sklearn.preprocessing import StandardScaler as _SS
        scaler = _SS(); scaler.mean_ = np.zeros(Xz.shape[1]); scaler.scale_ = np.ones(Xz.shape[1])
        coverage_kept = cov; medians = None
    else:
        X = extract_features(cohort)
        X_imputed, Xz, scaler, coverage_kept, medians = clean_matrix(X)
        cache_df = Xz.copy(); cache_df["_coverage"] = coverage_kept
        cache_df.to_pickle(CACHE)
        log(f"Feature matrix cached -> {CACHE.name}")
    hadm_kept = Xz.index
    cohort_kept = cohort.set_index("hadm_id").loc[hadm_kept]
    n_analysis = len(hadm_kept)
    log(f"Analysis cohort n={n_analysis}, coverage mean={coverage_kept.mean():.3f} "
        f"(t={time.time()-t0:.0f}s)")

    feature_names = list(X_imputed.columns)
    Xz_values = Xz.values.astype(np.float64)

    log("Running consensus k-means, k=2..6, 50 bootstraps each ...")
    results = {}
    for k in K_RANGE:
        log(f"  k={k} ...")
        res = bootstrap_stability(Xz_values, k)
        results[k] = res
        log(f"    median ARI={res['median_ari']:.3f} (IQR {res['ari_q1']:.3f}-{res['ari_q3']:.3f}), "
            f"silhouette={res['silhouette']:.3f}, consensus_mean={res['consensus_mean_offdiag']:.3f}, "
            f"consensus_crispness={res['consensus_crispness']:.3f}")

    # ---- choose primary k by stability (highest median bootstrap ARI) ----
    primary_k = max(results, key=lambda k: results[k]["median_ari"])
    log(f"PRIMARY k = {primary_k} (highest median bootstrap ARI = "
        f"{results[primary_k]['median_ari']:.3f})")

    primary = results[primary_k]
    labels = primary["ref_labels"]
    centroids_z = primary["centroids"]

    # ---- phenotype profiles: mean standardized feature value per cluster ----
    profile = pd.DataFrame(centroids_z, columns=feature_names)
    profile.index.name = "cluster"

    # human-readable top distinguishing features per cluster (|z| > 0.5)
    profile_text = {}
    for c in profile.index:
        row = profile.loc[c].sort_values(key=lambda s: -s.abs())
        top = row[row.abs() > 0.5]
        desc = ", ".join(f"{name}={val:+.2f}" for name, val in top.items())
        profile_text[int(c)] = desc if desc else "(no feature with |z|>0.5 -- near-average profile)"
        log(f"  cluster {c} signature: {profile_text[int(c)]}")
    with open(OUT / "sepsis_p1_profile_text.json", "w") as f:
        json.dump(profile_text, f, indent=2)

    # ---- prognosis ----
    adm = pd.read_csv(
        DATA / "admissions.csv",
        usecols=["hadm_id", "hospital_expire_flag"],
        dtype={"hadm_id": "int64", "hospital_expire_flag": "int8"},
    ).set_index("hadm_id")
    # cohort already carries 'dod' from the patients merge in build_base_cohort()
    cohort_kept = cohort_kept.copy()
    cohort_kept["cluster"] = labels
    cohort_kept["hospital_expire_flag"] = adm.reindex(cohort_kept.index)["hospital_expire_flag"].values
    cohort_kept["days_to_dod"] = (cohort_kept["dod"] - cohort_kept["intime"]).dt.days
    cohort_kept["mort30"] = ((cohort_kept["days_to_dod"] >= 0) & (cohort_kept["days_to_dod"] <= 30)).astype(int)

    prognosis_rows = []
    for c in sorted(cohort_kept["cluster"].unique()):
        sub = cohort_kept[cohort_kept["cluster"] == c]
        n = len(sub)
        ih_k = int(sub["hospital_expire_flag"].sum())
        m30_k = int(sub["mort30"].sum())
        ih_p, ih_lo, ih_hi = wilson_ci(ih_k, n)
        m30_p, m30_lo, m30_hi = wilson_ci(m30_k, n)
        prognosis_rows.append({
            "cluster": int(c), "n": n,
            "in_hospital_mortality": ih_p, "ih_ci_lo": ih_lo, "ih_ci_hi": ih_hi,
            "mortality_30d": m30_p, "m30_ci_lo": m30_lo, "m30_ci_hi": m30_hi,
        })
    prognosis = pd.DataFrame(prognosis_rows)

    # ---- k-sweep summary table ----
    sweep_rows = []
    for k in K_RANGE:
        r = results[k]
        sweep_rows.append({
            "k": k, "median_ari": r["median_ari"], "ari_q1": r["ari_q1"],
            "ari_q3": r["ari_q3"], "silhouette": r["silhouette"],
            "consensus_mean_offdiag": r["consensus_mean_offdiag"],
            "consensus_crispness": r["consensus_crispness"],
        })
    sweep = pd.DataFrame(sweep_rows)

    # ---- save outputs ----
    sweep.to_csv(OUT / "sepsis_p1_ksweep.csv", index=False)
    profile.to_csv(OUT / "sepsis_p1_profiles.csv")
    prognosis.to_csv(OUT / "sepsis_p1_prognosis.csv", index=False)
    organ_flags.to_csv(OUT / "sepsis_p1_organ_dysfunction_counts.csv")

    cluster_sizes = cohort_kept["cluster"].value_counts().sort_index()

    summary = {
        "n_final_cohort_pre_feature_filter": n_final_cohort,
        "n_analysis_cohort": n_analysis,
        "coverage_mean": float(coverage_kept.mean()),
        "coverage_median": float(coverage_kept.median()),
        "primary_k": int(primary_k),
        "primary_k_reason": "highest median bootstrap ARI (stability), not outcome separation",
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "cluster_sizes": {int(k): int(v) for k, v in cluster_sizes.items()},
        "duplicate_subject_rows": int(cohort_kept["subject_id"].duplicated().sum()),
        "runtime_sec": time.time() - t0,
    }
    with open(OUT / "sepsis_p1_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # save model for phase 2 cross-site assignment
    np.savez(
        OUT / "sepsis_p1_model.npz",
        centroids_z=centroids_z,
        scaler_mean=scaler.mean_,
        scaler_scale=scaler.scale_,
        feature_names=np.array(feature_names),
        primary_k=primary_k,
        medians=medians.values,
    )

    log(f"DONE in {time.time()-t0:.0f}s. Outputs written to {OUT}")
    log(f"k-sweep:\n{sweep.to_string(index=False)}")
    log(f"cluster sizes: {dict(cluster_sizes)}")
    log(f"prognosis:\n{prognosis.to_string(index=False)}")


if __name__ == "__main__":
    main()
