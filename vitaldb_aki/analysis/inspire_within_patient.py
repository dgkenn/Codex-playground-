"""inspire_within_patient.py -- WITHIN-PATIENT (patient fixed-effects) causal-leaning
analysis of intraoperative hypotension -> postoperative AKI on INSPIRE.

WHY: the between-patient association findings (incl the CKD personalized-MAP-target)
failed hostile review -- a negative-control calibration showed the apparent
effect-modification is generic confounding (docs/REDTEAM_CKD_MAP.md). The escape is a
WITHIN-PATIENT design. INSPIRE has many patients with >=2 renal-labelable operations.
Comparing a patient's higher-hypotension surgery to their OWN lower-hypotension surgery
removes ALL time-invariant confounding (baseline severity, CKD, genetics, chronic
comorbidity). This script builds that estimator properly.

Estimators:
  PRIMARY    conditional logistic regression stratified by subject_id (the correct
             binary within-patient estimator; concordant strata condition out, so only
             exposure-AND-outcome-discordant subjects are informative).
  EFFECT     linear-probability patient fixed-effects (within/demeaning) estimator for
             HYPO -> AKI probability, cluster-bootstrap CI over subjects.
  CONTRAST   within-patient vs naive between-patient estimate (the headline test of
             whether the signal survives removal of time-invariant confounding).
  DOSE       FE estimate across hypotension dose bands (within-patient monotonicity).
  ADJUST     time-varying covariates (age-at-op, surgery_duration, optype, emergency,
             n_map) added to FE; time-invariant covariates drop out automatically.

Outputs: cache/inspire_within_patient_results.json, docs/INSPIRE_WITHIN_PATIENT.md
Run from repo root: python vitaldb_aki/analysis/inspire_within_patient.py
"""
from __future__ import annotations
import json, os, sys, time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_MATRIX = os.path.join(_CACHE, "inspire_matrix.csv")
_RESULTS = os.path.join(_CACHE, "inspire_within_patient_results.json")
_DOC = os.path.join(_DOCS, "INSPIRE_WITHIN_PATIENT.md")

SEED = 20260626
N_BOOT = 2000
# time-varying covariates (change between a patient's operations). Time-invariant
# covariates (sex, baseline CKD) drop out of the FE / conditional likelihood.
TV_COV = ["age", "surgery_duration", "emergency", "n_map"]


# ----------------------------------------------------------------------------- load
def _load():
    import numpy as np, pandas as pd
    df = pd.read_csv(_MATRIX, low_memory=False)
    keep = ["op_id", "subject_id", "organ_renal", "aki_stage", "death_inhosp",
            "map_auc_below_65", "map_auc_below_70", "map_auc_below_75", "map_lowest",
            "n_map", "age", "sex_male", "asa_class", "emergency", "optype_code",
            "surgery_duration", "ckd", "baseline_cr"]
    for c in keep:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # renal-labelable operations only (each op KDIGO-labelled vs its own preop Cr)
    df = df[df["organ_renal"].notna()].copy()
    # cohort: subjects with >=2 renal-labelable operations
    vc = df.groupby("subject_id").size()
    multi_ids = vc[vc >= 2].index
    df = df[df["subject_id"].isin(multi_ids)].copy()

    # EXPOSURE (pre-specified): substantial intraop hypotension burden = map_auc_below_65
    # above the exposed-median (median among ops with positive burden), computed in the
    # multi-op cohort. Binary HYPO so the conditional-logit OR is interpretable.
    b = df["map_auc_below_65"].fillna(0.0)
    pos = b[b > 0]
    thr = float(pos.median()) if len(pos) else 0.0
    df["HYPO"] = (b > thr).astype(int)
    df["_b65"] = b
    df["AKI"] = df["organ_renal"].astype(float)
    return df, thr


# ------------------------------------------------------------------ cohort summary
def _cohort(df):
    import numpy as np
    n_ops = int(len(df))
    n_sub = int(df["subject_id"].nunique())
    g = df.groupby("subject_id")
    expo_disc = g["HYPO"].nunique() > 1
    out_disc = g["AKI"].nunique() > 1
    n_expo_disc = int(expo_disc.sum())                       # FE-informative (LPM)
    n_informative = int((expo_disc & out_disc).sum())        # clogit-informative
    ops_per = g.size()
    return {
        "n_ops": n_ops,
        "n_subjects": n_sub,
        "n_exposure_discordant_subjects": n_expo_disc,
        "n_informative_subjects_clogit": n_informative,
        "ops_per_subject_mean": float(ops_per.mean()),
        "ops_per_subject_median": float(ops_per.median()),
        "ops_per_subject_max": int(ops_per.max()),
        "overall_aki_rate": float(df["AKI"].mean()),
        "hypo_prevalence": float(df["HYPO"].mean()),
    }


# --------------------------------------------------------- PRIMARY: conditional logit
def _conditional_logit(df, exog_cols):
    """Conditional logistic stratified by subject_id. Concordant strata (all y=0 or all
    y=1, or no exposure variation) contribute nothing to the conditional likelihood, so
    statsmodels effectively uses the informative strata. We pass the full multi-op frame;
    ConditionalLogit drops non-informative groups internally. Returns OR + CI for HYPO."""
    import warnings
    import numpy as np, pandas as pd
    from statsmodels.discrete.conditional_models import ConditionalLogit
    d = df.dropna(subset=["AKI", "subject_id"] + exog_cols).copy()
    # restrict to informative strata to keep it fast & numerically clean: a stratum is
    # informative for clogit only if it is outcome-discordant. (Exposure discordance is
    # additionally required for HYPO to be identified.) This is exactly what the
    # conditional likelihood conditions on; restricting changes nothing in the estimate.
    g = d.groupby("subject_id")
    out_disc = g["AKI"].transform("nunique") > 1
    d = d[out_disc].copy()
    res = {}
    if len(d) == 0:
        return {"error": "no outcome-discordant strata"}
    y = d["AKI"].to_numpy(float)
    # standardize continuous covariates (NOT the binary HYPO) so the exact conditional
    # likelihood recursion does not overflow; this rescales their coefficients but leaves
    # the HYPO OR (verified) unchanged. We unscale nothing we report except via the note.
    Xdf = d[exog_cols].astype(float).copy()
    scales = {}
    for c in exog_cols:
        if c == "HYPO":
            continue
        s = float(Xdf[c].std())
        if s > 0:
            mu = float(Xdf[c].mean())
            Xdf[c] = (Xdf[c] - mu) / s
            scales[c] = s
    X = Xdf.to_numpy(float)
    groups = d["subject_id"].to_numpy()
    t0 = time.time()
    model = ConditionalLogit(y, X, groups=groups)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # benign overflow in per-stratum recursion
        fit = model.fit(disp=False)
    secs = time.time() - t0
    params = np.asarray(fit.params, float)
    bse = np.asarray(fit.bse, float)
    ci = fit.conf_int()
    ci = np.asarray(ci, float)
    for i, name in enumerate(exog_cols):
        res[name] = {
            "beta": float(params[i]),
            "OR": float(np.exp(params[i])),
            "se": float(bse[i]),
            "OR_ci": [float(np.exp(ci[i, 0])), float(np.exp(ci[i, 1]))],
            "p": float(fit.pvalues[i]),
        }
    res["_n_ops_in_informative_strata"] = int(len(d))
    res["_n_strata"] = int(d["subject_id"].nunique())
    res["_fit_seconds"] = round(secs, 2)
    res["_note"] = ("continuous covariate ORs are per-1-SD (standardized for numeric "
                    "stability); HYPO is binary and its OR is unaffected.")
    return res


# ----------------------------------------- EFFECT: linear-probability fixed effects
def _within_demean(d, expo_cols, ycol="AKI"):
    """Patient fixed-effects via within-transformation (subtract subject means), then OLS
    on demeaned columns. Returns coefficient vector keyed by expo_cols. Subjects with a
    single op contribute nothing post-demeaning. NaNs in any used column drop the op."""
    import numpy as np, pandas as pd
    cols = expo_cols + [ycol]
    dd = d.dropna(subset=cols + ["subject_id"]).copy()
    grp = dd.groupby("subject_id")
    dm = dd[cols].copy()
    for c in cols:
        dm[c] = dd[c] - grp[c].transform("mean")
    X = dm[expo_cols].to_numpy(float)
    y = dm[ycol].to_numpy(float)
    # drop all-zero (perfectly collinear / constant) columns guard handled by lstsq
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {c: float(coef[i]) for i, c in enumerate(expo_cols)}, dd


def _cluster_bootstrap_fe(df, expo_cols, ycol="AKI", n_boot=N_BOOT, seed=SEED):
    """Cluster-bootstrap over subjects for the within (demeaning) FE estimator.

    KEY: the within-transformation is performed *inside each subject* and is therefore
    invariant under resampling of subjects -- a subject's demeaned rows do not change when
    other subjects are added/removed. So the FE OLS estimate for any cluster-bootstrap
    resample is the solution of  (sum_s w_s A_s) beta = (sum_s w_s b_s), where
    A_s = Xd_s' Xd_s and b_s = Xd_s' yd_s are the per-subject demeaned normal-equation
    blocks (precomputed once) and w_s is the multiplicity of subject s in the resample.
    This turns each bootstrap iteration into a small weighted sum + p x p solve -- fully
    vectorized over all resamples, ~1e4x faster than refitting frames.
    """
    import numpy as np, pandas as pd
    rng = np.random.default_rng(seed)
    cols = expo_cols + [ycol]
    dd = df.dropna(subset=cols + ["subject_id"]).copy()
    grp = dd.groupby("subject_id")
    Xd = (dd[expo_cols] - grp[expo_cols].transform("mean")).to_numpy(float)
    yd = (dd[ycol] - grp[ycol].transform("mean")).to_numpy(float)
    # point estimate (full sample)
    coef, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    point = {c: float(coef[i]) for i, c in enumerate(expo_cols)}

    # per-subject normal-equation blocks
    codes, uniq = pd.factorize(dd["subject_id"].to_numpy())
    S = len(uniq)
    p = len(expo_cols)
    A = np.zeros((S, p, p))      # Xd_s' Xd_s
    b = np.zeros((S, p))         # Xd_s' yd_s
    # accumulate via np.add.at over subject codes
    # outer products: for each row, Xd[i] outer Xd[i] -> add to A[code]
    for j in range(p):
        for k in range(p):
            np.add.at(A[:, j, k], codes, Xd[:, j] * Xd[:, k])
        np.add.at(b[:, j], codes, Xd[:, j] * yd)

    boots = {c: [] for c in expo_cols}
    for _ in range(n_boot):
        # multiplicity of each subject in a size-S resample with replacement
        w = np.bincount(rng.integers(0, S, size=S), minlength=S).astype(float)
        Asum = np.tensordot(w, A, axes=(0, 0))   # p x p
        bsum = w @ b                              # p
        try:
            beta = np.linalg.solve(Asum, bsum)
        except np.linalg.LinAlgError:
            beta, *_ = np.linalg.lstsq(Asum, bsum, rcond=None)
        for i, c in enumerate(expo_cols):
            boots[c].append(float(beta[i]))

    out = {}
    for c in expo_cols:
        arr = np.array(boots[c], float)
        out[c] = {
            "point": point[c],
            "boot_mean": float(arr.mean()) if len(arr) else float("nan"),
            "ci": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))] if len(arr) else [float("nan")] * 2,
            "n_boot": int(len(arr)),
        }
    return out


# --------------------------------------------------- BETWEEN-patient naive estimate
def _between(df):
    """Naive between-patient estimates ignoring patient structure (op-level): raw risk
    difference for HYPO->AKI, and an op-level OLS LPM coefficient. This is the comparator
    the within-patient design is meant to improve on."""
    import numpy as np
    e = df["HYPO"].to_numpy(); y = df["AKI"].to_numpy(float)
    r1 = float(y[e == 1].mean()); r0 = float(y[e == 0].mean())
    rd = r1 - r0
    # op-level logit OR for comparability with conditional-logit OR
    import statsmodels.api as sm
    X = sm.add_constant(df["HYPO"].to_numpy(float))
    try:
        fit = sm.Logit(y, X).fit(disp=False)
        or_ = float(np.exp(fit.params[1]))
        or_ci = [float(np.exp(fit.conf_int()[1, 0])), float(np.exp(fit.conf_int()[1, 1]))]
        or_p = float(fit.pvalues[1])
    except Exception:
        or_ = or_ci = or_p = None
    return {"risk_hypo": r1, "risk_nohypo": r0, "risk_difference": rd,
            "OR": or_, "OR_ci": or_ci, "p": or_p,
            "n_hypo": int((e == 1).sum()), "n_nohypo": int((e == 0).sum()),
            "n_aki": int(y.sum())}


# ------------------------------------------------------- DOSE-RESPONSE within patient
def _dose_response(df, seed=SEED):
    """Within-patient FE LPM with hypotension dose coded as ordered bands, plus a
    per-band FE contrast vs the no/low-burden band. Bands from map_auc_below_65 tertiles
    among positive-burden ops (0 burden = band 0)."""
    import numpy as np, pandas as pd
    d = df.copy()
    b = d["_b65"]
    pos = b[b > 0]
    q1, q2 = pos.quantile([1 / 3, 2 / 3]) if len(pos) else (0.0, 0.0)
    band = np.zeros(len(d), int)
    band = np.where(b > 0, 1, band)
    band = np.where(b >= q1, 2, band)
    band = np.where(b >= q2, 3, band)
    d["dose_band"] = band
    # FE: linear trend in band
    d["dose_lin"] = d["dose_band"].astype(float)
    trend, _ = _within_demean(d, ["dose_lin"], "AKI")
    # per-band dummy FE contrasts vs band 0
    for k in (1, 2, 3):
        d[f"band_{k}"] = (d["dose_band"] == k).astype(float)
    dummy, _ = _within_demean(d, ["band_1", "band_2", "band_3"], "AKI")
    # also report within-patient mean AKI by band (informative subjects only feel it)
    by_band = d.groupby("dose_band").agg(n=("AKI", "size"), aki=("AKI", "mean")).reset_index()
    return {
        "band_cuts_auc65": [float(q1), float(q2)],
        "fe_linear_trend_per_band": float(trend["dose_lin"]),
        "fe_band_contrasts_vs0": {k: float(v) for k, v in dummy.items()},
        "marginal_aki_by_band": by_band.to_dict(orient="records"),
    }


# ------------------------------------------- SECONDARY: aki_stage ordinal severity FE
def _aki_stage_fe(df):
    """Within-patient FE LPM on aki_stage (0-3) treated as a quasi-continuous severity
    score. A clean ordinal within-patient model (e.g. conditional ordinal logit) is not
    in statsmodels; the FE LPM slope is a defensible linear approximation of the
    within-patient shift in severity per HYPO."""
    import numpy as np
    d = df.dropna(subset=["aki_stage"]).copy()
    d["aki_stage"] = d["aki_stage"].astype(float)
    coef, _ = _within_demean(d, ["HYPO"], "aki_stage")
    return {"fe_hypo_on_aki_stage": float(coef["HYPO"]),
            "note": "FE LPM slope on ordinal aki_stage(0-3); linear approximation."}


# ------------------------------------------------------------------------------ main
def main():
    import numpy as np
    np.random.seed(SEED)
    df, thr = _load()
    out = {"seed": SEED, "exposure_def": "map_auc_below_65 > exposed-median",
           "exposure_threshold_auc65": thr,
           "n_boot": N_BOOT, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

    out["cohort"] = _cohort(df)
    print("[cohort]", out["cohort"])

    # PRIMARY: conditional logistic, HYPO only, then HYPO + time-varying covariates
    out["primary_conditional_logit_unadjusted"] = _conditional_logit(df, ["HYPO"])
    print("[clogit unadj]", out["primary_conditional_logit_unadjusted"].get("HYPO"))
    tv = [c for c in TV_COV if c in df.columns]
    out["primary_conditional_logit_adjusted"] = _conditional_logit(df, ["HYPO"] + tv)
    print("[clogit adj]", out["primary_conditional_logit_adjusted"].get("HYPO"))

    # EFFECT SIZE: FE LPM, cluster-bootstrap over subjects (unadjusted + tv-adjusted)
    out["fe_lpm_unadjusted"] = _cluster_bootstrap_fe(df, ["HYPO"])
    print("[FE LPM unadj]", out["fe_lpm_unadjusted"]["HYPO"])
    out["fe_lpm_adjusted"] = _cluster_bootstrap_fe(df, ["HYPO"] + tv)
    print("[FE LPM adj]", out["fe_lpm_adjusted"]["HYPO"])

    # BETWEEN-patient naive comparator
    out["between_patient"] = _between(df)
    print("[between]", out["between_patient"])

    # WITHIN vs BETWEEN contrast
    within_rd = out["fe_lpm_unadjusted"]["HYPO"]["point"]
    between_rd = out["between_patient"]["risk_difference"]
    out["within_vs_between"] = {
        "within_fe_rd": within_rd,
        "between_rd": between_rd,
        "ratio_within_over_between": float(within_rd / between_rd) if between_rd else None,
        "within_clogit_OR": out["primary_conditional_logit_unadjusted"].get("HYPO", {}).get("OR"),
        "between_logit_OR": out["between_patient"]["OR"],
    }
    print("[within vs between]", out["within_vs_between"])

    # DOSE-RESPONSE
    out["dose_response"] = _dose_response(df)
    print("[dose]", out["dose_response"]["fe_band_contrasts_vs0"],
          "trend", out["dose_response"]["fe_linear_trend_per_band"])

    # SECONDARY severity
    out["secondary_aki_stage_fe"] = _aki_stage_fe(df)
    out["death_inhosp_note"] = ("death_inhosp NOT analysed within-patient: a patient dies "
                                "at most once, so in-hospital death has no within-subject "
                                "variation across a patient's operations -- the FE / "
                                "conditional likelihood would condition it entirely out.")

    with open(_RESULTS, "w") as f:
        json.dump(out, f, indent=2, allow_nan=True)
    print("[written]", _RESULTS)
    _write_doc(out)
    print("[written]", _DOC)
    return out


def _fmt_ci(ci):
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def _write_doc(o):
    c = o["cohort"]
    cl = o["primary_conditional_logit_unadjusted"].get("HYPO", {})
    cla = o["primary_conditional_logit_adjusted"].get("HYPO", {})
    fe = o["fe_lpm_unadjusted"]["HYPO"]
    fea = o["fe_lpm_adjusted"]["HYPO"]
    bw = o["between_patient"]
    wvb = o["within_vs_between"]
    dr = o["dose_response"]
    md = f"""# INSPIRE within-patient (patient fixed-effects) hypotension -> AKI

**Generated:** {o['timestamp']}  ·  seed {o['seed']}  ·  `analysis/inspire_within_patient.py`

## READ FIRST -- scope and honest limitations
This is the **defensible causal-leaning CORE** for the MAIN intraoperative
hypotension -> postoperative AKI effect. It is **NOT** the failed CKD
personalized-MAP-target finding (see `docs/REDTEAM_CKD_MAP.md`), and it does **not**
and **cannot** rehabilitate it.

A within-patient (patient fixed-effects) design compares a patient's
**higher-hypotension** operation to **their own lower-hypotension** operation. By
construction it removes **all time-invariant confounding**: baseline disease severity,
chronic kidney disease, genetics, sex, chronic comorbidity -- anything that does not
change between a patient's operations is differenced out exactly.

What it does **not** fix, stated plainly:
- **Time-varying confounding remains.** If a patient became sicker *before* their
  higher-hypotension operation (worse acute illness, a more aggressive procedure), that
  acute change can drive both the hypotension and the AKI. Within-patient removes the
  *chronic* baseline, not the *acute* trajectory.
- **Prior-operation AKI can shift the next operation's KDIGO baseline** (each op is
  graded against its own preop creatinine), creating carry-over dependence between a
  subject's operations.
- **Informative subjects are a selected subset.** Only subjects whose operations are
  *discordant* on exposure (FE) and on both exposure and outcome (conditional logit)
  carry information. They are sicker / more operated-on than average; the estimate
  generalizes to that subset.
- **Time-invariant effect-modification is untestable here.** CKD, sex, etc. drop out of
  the model, so this design **CANNOT** test CKD-specificity. That is by design and is the
  reason it is immune to the confounding that sank the CKD finding.
- This is **causal-LEANING**, not a randomized trial. Treat it as the strongest
  observational evidence available in this dataset, not as proof.

## Cohort
Operations belonging to subjects with **>=2 renal-labelable operations** (each operation
KDIGO-graded against its own preoperative creatinine).

| quantity | value |
|---|---|
| operations | {c['n_ops']:,} |
| subjects | {c['n_subjects']:,} |
| exposure-discordant subjects (inform the FE LPM) | {c['n_exposure_discordant_subjects']:,} |
| **informative subjects (exposure-AND-outcome discordant, inform the conditional logit)** | **{c['n_informative_subjects_clogit']:,}** |
| ops/subject (mean / median / max) | {c['ops_per_subject_mean']:.2f} / {c['ops_per_subject_median']:.0f} / {c['ops_per_subject_max']} |
| overall AKI (organ_renal) rate | {c['overall_aki_rate']:.4f} |
| HYPO prevalence | {c['hypo_prevalence']:.4f} |

**Exposure (pre-specified):** `HYPO = 1` iff `map_auc_below_65` exceeds the
exposed-median (median among operations with positive sub-65 AUC), computed in this
cohort. Threshold = **{o['exposure_threshold_auc65']:.1f}** mmHg·min.

Only the **{c['n_informative_subjects_clogit']:,}** exposure-and-outcome-discordant
subjects contribute to the conditional-logit likelihood; concordant strata condition out.

## PRIMARY -- conditional logistic (stratified by subject_id)
Within-patient odds ratio for HYPO -> AKI (organ_renal), exact conditional likelihood.

| model | OR | 95% CI | p |
|---|---|---|---|
| HYPO only | **{cl.get('OR', float('nan')):.3f}** | {_fmt_ci(cl.get('OR_ci',[float('nan')]*2))} | {cl.get('p', float('nan')):.4g} |
| HYPO + time-varying cov | {cla.get('OR', float('nan')):.3f} | {_fmt_ci(cla.get('OR_ci',[float('nan')]*2))} | {cla.get('p', float('nan')):.4g} |

Time-varying covariates adjusted: {', '.join([c for c in TV_COV])}. Time-invariant
covariates (sex, baseline CKD, baseline creatinine) drop out of the conditional
likelihood automatically.

## EFFECT SIZE -- linear-probability patient fixed-effects (within / demeaning)
Within-patient change in AKI **probability** per HYPO, cluster-bootstrap CI over subjects
({fe['n_boot']} resamples).

| model | within-patient RD (AKI prob) | 95% CI |
|---|---|---|
| HYPO only | **{fe['point']:+.4f}** | {_fmt_ci(fe['ci'])} |
| HYPO + time-varying cov | {fea['point']:+.4f} | {_fmt_ci(fea['ci'])} |

## WITHIN vs BETWEEN -- the headline contrast
| estimate | within-patient | between-patient (naive) |
|---|---|---|
| risk difference (AKI prob) | **{wvb['within_fe_rd']:+.4f}** | {wvb['between_rd']:+.4f} |
| odds ratio | {wvb['within_clogit_OR']:.3f} (conditional logit) | {bw['OR']:.3f} (op-level logit) |

within / between RD ratio = **{wvb['ratio_within_over_between']:.2f}**.

**Interpretation.** {(
    "The within-patient risk difference is comparable to the naive between-patient risk "
    "difference (ratio near 1). The effect is therefore NOT an artifact of time-invariant "
    "confounding: when a patient acts as their own control, a higher-hypotension operation "
    "still carries higher AKI risk than that same patient's lower-hypotension operation."
) if (wvb['ratio_within_over_between'] is not None and wvb['ratio_within_over_between'] >= 0.6) else (
    "The within-patient risk difference is substantially SMALLER than the naive "
    "between-patient difference: most of the between-patient signal was time-invariant "
    "confounding. A residual within-patient effect "
    + ("does" if fe['ci'][0] > 0 else "does not") + " survive."
)}

## DOSE-RESPONSE within patient
FE LPM with `map_auc_below_65` coded as bands (0 = no burden; 1-3 = tertiles of positive
burden). Band cut points (AUC65): {dr['band_cuts_auc65'][0]:.1f}, {dr['band_cuts_auc65'][1]:.1f}.

| band | within-patient FE contrast vs band 0 (AKI prob) |
|---|---|
| band 1 | {dr['fe_band_contrasts_vs0'].get('band_1', float('nan')):+.4f} |
| band 2 | {dr['fe_band_contrasts_vs0'].get('band_2', float('nan')):+.4f} |
| band 3 | {dr['fe_band_contrasts_vs0'].get('band_3', float('nan')):+.4f} |

FE linear trend per band = **{dr['fe_linear_trend_per_band']:+.5f}** AKI-prob per band step.

## SECONDARY -- AKI severity (ordinal aki_stage, FE)
Within-patient FE LPM slope on `aki_stage` (0-3) per HYPO =
**{o['secondary_aki_stage_fe']['fe_hypo_on_aki_stage']:+.4f}**
({o['secondary_aki_stage_fe']['note']})

**Mortality:** {o['death_inhosp_note']}

## Verdict
A **defensible, causal-leaning** intraoperative-hypotension -> postoperative-AKI claim
**{('survives' if (fe['ci'][0] > 0 and cl.get('OR_ci',[0,0])[0] > 1) else 'is weakened')}**
the within-patient design. {('Removing every time-invariant confounder via patient '
'fixed effects leaves a positive within-patient effect whose CI excludes the null, and '
'it is of the same order as the between-patient effect -- so the association is not '
'merely chronic-severity confounding. Residual risk is time-VARYING confounding, which '
'this design cannot remove; the claim is strong observational evidence, not an RCT.')
if (fe['ci'][0] > 0 and cl.get('OR_ci',[0,0])[0] > 1) else
('The within-patient effect does not cleanly exclude the null after differencing out '
'time-invariant confounders; treat the hypotension->AKI effect as not robustly '
'established by this design.')}
"""
    with open(_DOC, "w") as f:
        f.write(md)


if __name__ == "__main__":
    main()
