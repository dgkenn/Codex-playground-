"""doseresponse_severity.py -- HOSTILE severity-attack on the headline dose-response
gradient: "ICU norepinephrine requirement mortality climbs Q1 14% -> Q4 65%, monotonic".

THE ATTACK (mimic_outcomes_doseresponse.py reports the gradient AGE-ADJUSTED ONLY):
    "This gradient is just severity. Higher vasopressor dose marks sicker patients who die
     more. Adjust it for real comorbidity/severity (Charlson + van Walraven/Elixhauser +
     #vasopressors), not just age, and the monotone Q1->Q4 gradient will flatten."

This module tests that attack HONESTLY. It re-expresses the dose-response in QUARTILES of the
per-stay requirement (median norepinephrine rate, 0<rate<=5 mcg/kg/min) and computes
SEVERITY-ADJUSTED predicted mortality per quartile by G-COMPUTATION (standardization):

    Fit one logistic model  death ~ C(quartile) + age + Charlson + vanWalraven [+ n_vaso].
    For each quartile level q, set EVERYONE's quartile = q (keep their real covariates),
    predict each patient's risk, and average over the whole cohort. This is the marginal,
    covariate-standardized risk that the cohort WOULD have at dose-quartile q -- the apples-to-
    apples adjusted gradient. (Equivalent to direct standardization to the pooled covariate
    distribution; far better than reading model coefficients off a non-collapsible OR.)

TESTS
  1. ADJUSTED dose-response gradient: g-computed adjusted mortality per requirement quartile,
     controlling age + Charlson + van Walraven + #vasopressors. Adjusted Q4-vs-Q1 risk ratio
     and risk difference + a logistic linear-trend test on the ordinal quartile under
     adjustment. Does the monotone gradient SURVIVE or FLATTEN?
  2. ADJUSTED per-SD OR with the full severity set (gradient framing; should reproduce the
     ~3.0 from mimic_severity_scores).
  3. KEY HONEST CHECK: how much of the attenuation is #vasopressors (multi-pressor =
     refractory shock)? Report the adjusted gradient WITHOUT vs WITH n_vasopressors to localise
     where the flattening comes from.
  4. MONOTONICITY after adjustment: are the adjusted quartile risks STILL strictly increasing?

Reuses cache/mimic_norepi.csv (requirement), cache/mimic_vaso_count.csv (#vasopressors), and
the Charlson + van Walraven (Quan 2005 / vanWalraven 2009) per-hadm scoring from
mimic_severity_scores.py (imported, NOT re-derived). Reads raw MIMIC from $MIMIC_RAW.
stdlib only at import; numpy/sklearn/scipy lazy. Writes cache/doseresponse_severity.json +
docs/DOSERESPONSE_SEVERITY.md.
Run: python3 -m vitaldb_aki.analysis.doseresponse_severity
"""
from __future__ import annotations
import csv as _csv
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
MIMIC_RAW = os.environ.get("MIMIC_RAW",
    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad")
NOREPI_CSV = os.path.join(_CACHE, "mimic_norepi.csv")
VASO_CSV = os.path.join(_CACHE, "mimic_vaso_count.csv")
OUT_JSON = os.path.join(_CACHE, "doseresponse_severity.json")
NQUART = 4


# ----------------------------------------------------------------------------- data assembly
def _norepi_req():
    """Per-stay requirement = MEDIAN norepinephrine rate (0 < rate <= 5 mcg/kg/min).
    Same definition the headline finding uses."""
    import numpy as np
    stay = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rt = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rt <= 0 or rt > 5:
                continue
            stay.setdefault(row["stay_id"], []).append(rt)
    return {s: float(np.median(v)) for s, v in stay.items() if v}


def _gz(name):
    return gzip.open(os.path.join(MIMIC_RAW, name), "rt")


def _assemble():
    """Build the complete-case analysis matrix:
       requirement, age, Charlson, vanWalraven, n_vasopressors, in-hospital death.
    Charlson + van Walraven come straight from mimic_severity_scores._comorbidity_scores()."""
    import numpy as np
    from vitaldb_aki.analysis.mimic_severity_scores import _comorbidity_scores

    req = _norepi_req()
    com = _comorbidity_scores()
    charlson_score = com["charlson_score"]
    vw_score = com["vw_score"]

    vaso = {}
    with open(VASO_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                vaso[row["stay_id"]] = int(row["n_vasopressors"])
            except (ValueError, TypeError):
                pass

    stay_hadm, stay_subj = {}, {}
    with _gz("icustays.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]
            stay_subj[row["stay_id"]] = row["subject_id"]
    death = {}
    with _gz("admissions.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                death[row["hadm_id"]] = int(row.get("hospital_expire_flag", "0"))
            except (ValueError, TypeError):
                pass
    age = {}
    with _gz("patients.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass

    rows = []
    for sid, r in req.items():
        h = stay_hadm.get(sid)
        if not h or h not in death:
            continue
        a = age.get(stay_subj.get(sid), np.nan)
        nv = vaso.get(sid, 1)                 # absence in vaso file -> at least the 1 (norepi)
        ch = charlson_score.get(h, 0)         # standard convention: no mapped dx -> 0
        vw = vw_score.get(h, 0)
        rows.append([r, a, nv, ch, vw, death[h]])
    arr = np.array([row for row in rows if all(np.isfinite(x) for x in row)], float)
    return arr, com


def _quartile_index(req, k=NQUART):
    """Rank-based equal-count quartile index in [0,k). Ties at the low-dose floor are
    distributed by stable rank exactly as the headline module does, so the bins match."""
    import numpy as np
    order = np.argsort(req, kind="mergesort")
    ranks = np.empty(len(req), int)
    ranks[order] = np.arange(len(req))
    return (ranks * k // len(req)).clip(0, k - 1)


# ----------------------------------------------------------------------------- g-computation
def _gcomp_gradient(req, qidx, covars, death, label, nboot=400):
    """G-computation (standardization) of adjusted mortality per requirement quartile.

    Design: death ~ [quartile dummies q1..q3 vs Q1 ref] + standardized covars.
    For each quartile level q in 0..k-1: set the WHOLE cohort's quartile dummies to q,
    predict each patient's risk under their real covariates, average -> standardized
    adjusted risk at dose-quartile q. CRUDE (unadjusted) per-quartile rates reported too.

    Returns adjusted risks per quartile, Q4/Q1 RR + RD, monotonicity, an adjusted ordinal
    linear-trend p (Wald on the quartile-as-score coefficient in the same covar model),
    and a bootstrap CI for the adjusted Q4-Q1 risk difference (resample stays)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    k = NQUART
    n = len(death)
    covars = np.asarray(covars, float).reshape(n, -1)

    def zfit(C):
        mu = C.mean(0); sd = C.std(0); sd[sd == 0] = 1.0
        return mu, sd

    mu, sd = zfit(covars)
    Cz = (covars - mu) / sd

    def dummies(qi):
        # k-1 dummies, Q1 (index 0) is reference
        D = np.zeros((len(qi), k - 1))
        for j in range(1, k):
            D[:, j - 1] = (qi == j).astype(float)
        return D

    def fit_predict_standardized(qi, Cz_, y):
        # fit death ~ quartile dummies + covars, then standardize: set the whole sample to
        # each quartile q and average the predicted risk. y MUST be the (resampled) outcome
        # aligned to qi/Cz_ -- not the outer death array (that was the bootstrap bug).
        X = np.column_stack([dummies(qi), Cz_])
        lr = LogisticRegression(max_iter=5000).fit(X, y)
        adj = []
        for q in range(k):
            qfix = np.full(len(qi), q)
            Xq = np.column_stack([dummies(qfix), Cz_])
            adj.append(float(lr.predict_proba(Xq)[:, 1].mean()))
        return adj

    adj = fit_predict_standardized(qidx, Cz, death)

    # crude (unadjusted) per-quartile mortality
    crude = [float(death[qidx == q].mean()) for q in range(k)]

    # adjusted ordinal linear-trend: quartile as a 0..k-1 score in the SAME covar model
    qscore = (qidx - qidx.mean()) / (qidx.std() if qidx.std() else 1.0)
    Xlin = np.column_stack([qscore, Cz])
    lr_lin = LogisticRegression(max_iter=5000).fit(Xlin, death)
    beta = float(lr_lin.coef_[0][0])
    # Wald p via observed information of the standardized logistic model
    p_trend = _wald_p(Xlin, death, lr_lin, col=0)
    or_per_quartile_sd = float(np.exp(beta))

    # bootstrap CI for adjusted Q4-Q1 risk difference and ratio
    rng = np.random.default_rng(SEED)
    rd_bs, rr_bs = [], []
    for _ in range(nboot):
        idx = rng.integers(0, n, n)
        try:
            a_b = fit_predict_standardized(qidx[idx], Cz[idx], death[idx])
            rd_bs.append(a_b[-1] - a_b[0])
            if a_b[0] > 0:
                rr_bs.append(a_b[-1] / a_b[0])
        except Exception:
            pass
    rd_ci = ([round(float(np.percentile(rd_bs, 2.5)), 4),
              round(float(np.percentile(rd_bs, 97.5)), 4)] if rd_bs else None)
    rr_ci = ([round(float(np.percentile(rr_bs, 2.5)), 3),
              round(float(np.percentile(rr_bs, 97.5)), 3)] if rr_bs else None)

    mono = all(adj[j + 1] >= adj[j] - 1e-9 for j in range(k - 1))
    mono_strict = all(adj[j + 1] > adj[j] + 1e-6 for j in range(k - 1))
    _covnames = ["age", "Charlson", "vanWalraven", "n_vasopressors"]
    return {
        "label": label,
        "covariates": _covnames[:covars.shape[1]],
        "crude_mortality_per_quartile": [round(c, 4) for c in crude],
        "adjusted_mortality_per_quartile": [round(a, 4) for a in adj],
        "adj_q1": round(adj[0], 4), "adj_q4": round(adj[-1], 4),
        "adj_q4_over_q1_riskratio": round(adj[-1] / adj[0], 3) if adj[0] > 0 else None,
        "adj_q4_over_q1_rr_ci": rr_ci,
        "adj_q4_minus_q1_riskdiff": round(adj[-1] - adj[0], 4),
        "adj_q4_minus_q1_rd_ci": rd_ci,
        "adjusted_monotonic_nondecreasing": bool(mono),
        "adjusted_strictly_increasing": bool(mono_strict),
        "adj_linear_trend_or_per_quartile_sd": round(or_per_quartile_sd, 3),
        "adj_linear_trend_p": p_trend,
    }


def _wald_p(X, y, lr, col=0):
    """Two-sided Wald p for coefficient `col` of a fitted (unpenalized-ish) logistic model.
    Uses the model's predicted probabilities to form the observed information matrix
    Xt W X. sklearn's default L2 is light at large n; this p is a standard-error read, the
    gradient itself (predicted risks) is the load-bearing result."""
    import numpy as np
    Xc = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    coef = np.concatenate([lr.intercept_, lr.coef_[0]])
    eta = Xc @ coef
    p = 1.0 / (1.0 + np.exp(-eta))
    W = p * (1 - p)
    XtWX = Xc.T @ (Xc * W[:, None])
    try:
        cov = np.linalg.inv(XtWX)
        se = float(np.sqrt(cov[col + 1, col + 1]))   # +1 for intercept
    except np.linalg.LinAlgError:
        return None
    from scipy import stats
    z = float(coef[col + 1] / se) if se > 0 else 0.0
    return float(2 * stats.norm.sf(abs(z)))


# ----------------------------------------------------------------------------- per-SD OR (test 2)
def _adjusted_or_per_sd(req, covars, death, label):
    """Standardized logistic: death ~ z(requirement) + z(covars). Requirement OR per SD +
    bootstrap CI. Reproduces the mimic_severity_scores 'FULL' framing on the gradient cohort."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    n = len(death)
    C = np.asarray(covars, float).reshape(n, -1)
    def z(v):
        v = np.asarray(v, float); s = v.std()
        return (v - v.mean()) / (s if s else 1.0)
    design = np.column_stack([z(req)] + [z(C[:, j]) for j in range(C.shape[1])])
    lr = LogisticRegression(max_iter=5000).fit(design, death)
    or_req = float(np.exp(lr.coef_[0][0]))
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(400):
        idx = rng.integers(0, n, n)
        try:
            bs.append(float(np.exp(
                LogisticRegression(max_iter=3000).fit(design[idx], death[idx]).coef_[0][0])))
        except Exception:
            pass
    ci = ([round(float(np.percentile(bs, 2.5)), 3),
           round(float(np.percentile(bs, 97.5)), 3)] if bs else None)
    return {"label": label, "or_per_sd": round(or_req, 3), "ci": ci}


# ----------------------------------------------------------------------------- model
def model():
    import numpy as np
    arr, com = _assemble()
    res = {"seed": SEED, "n": int(len(arr)),
           "deaths": int(arr[:, -1].sum()) if len(arr) else 0,
           "charlson_distribution": _dist(com["charlson_score"]),
           "vanwalraven_distribution": _dist(com["vw_score"])}
    if len(arr) < 500:
        res["note"] = f"only {len(arr)} complete rows"
        return res

    req, age, nv, ch, vw, death = (arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3],
                                   arr[:, 4], arr[:, -1].astype(int))
    res["event_rate"] = round(float(death.mean()), 4)
    qidx = _quartile_index(req, NQUART)
    res["n_per_quartile"] = [int((qidx == q).sum()) for q in range(NQUART)]
    res["dose_range_per_quartile"] = [
        [round(float(req[qidx == q].min()), 4), round(float(req[qidx == q].max()), 4)]
        for q in range(NQUART)]

    # crude (age-adjusted-only headline replication is the crude rates here)
    res["crude_mortality_per_quartile"] = [round(float(death[qidx == q].mean()), 4)
                                            for q in range(NQUART)]
    res["crude_q4_over_q1_riskratio"] = round(
        res["crude_mortality_per_quartile"][-1] / res["crude_mortality_per_quartile"][0], 3)

    # TEST 1 / 4: fully severity-adjusted g-computation gradient (age+Charlson+vW+#vaso)
    cov_full = np.column_stack([age, ch, vw, nv])
    res["gradient_full_adjustment"] = _gcomp_gradient(req, qidx, cov_full, death,
        "age + Charlson + vanWalraven + n_vasopressors")

    # TEST 3: localise attenuation -- WITHOUT n_vasopressors vs WITH it
    cov_nocard = np.column_stack([age, ch, vw])
    res["gradient_comorbidity_no_nvaso"] = _gcomp_gradient(req, qidx, cov_nocard, death,
        "age + Charlson + vanWalraven (NO n_vasopressors)")
    # age-only adjusted gradient too, as the baseline the headline implicitly used
    res["gradient_age_only"] = _gcomp_gradient(req, qidx, age.reshape(-1, 1), death,
        "age only")

    # TEST 2: adjusted per-SD OR (full severity set), gradient framing
    res["per_sd_or_full"] = _adjusted_or_per_sd(req, cov_full, death,
        "requirement OR/SD | full (age+Charlson+vanWalraven+#vaso)")
    res["per_sd_or_age_only"] = _adjusted_or_per_sd(req, age.reshape(-1, 1), death,
        "requirement OR/SD | age only")

    res["verdict"] = _verdict(res)
    return res


def _dist(d):
    import numpy as np
    if not d:
        return {}
    v = np.array(list(d.values()), float)
    return {"n": int(len(v)), "mean": round(float(v.mean()), 3), "sd": round(float(v.std()), 3),
            "median": round(float(np.median(v)), 3)}


# ----------------------------------------------------------------------------- verdict
def _verdict(res):
    crude = res["crude_mortality_per_quartile"]
    g = res["gradient_full_adjustment"]
    gnc = res["gradient_comorbidity_no_nvaso"]
    adj = g["adjusted_mortality_per_quartile"]
    rr_crude = res["crude_q4_over_q1_riskratio"]
    rr_adj = g["adj_q4_over_q1_riskratio"]
    mono = g["adjusted_monotonic_nondecreasing"]
    mono_s = g["adjusted_strictly_increasing"]
    p = g["adj_linear_trend_p"]

    # how much of the Q4/Q1 ratio survived?
    surv_frac = None
    if rr_crude and rr_adj and rr_crude > 1:
        surv_frac = round((rr_adj - 1) / (rr_crude - 1), 3)
    # localisation: RR without vs with n_vaso
    rr_nocard = gnc["adj_q4_over_q1_riskratio"]

    # classification of the result
    if rr_adj is None:
        tag = "INSUFFICIENT"
    elif rr_adj >= 2.0 and mono:
        tag = "SURVIVES — DOSE-RESPONSE BEYOND SEVERITY"
    elif rr_adj >= 1.4 and mono:
        tag = "ATTENUATED BUT STILL GRADED"
    elif rr_adj < 1.25:
        tag = "FLATTENS — LARGELY SEVERITY"
    else:
        tag = "PARTLY ATTENUATED"

    v = (f"SEVERITY ATTACK ON THE DOSE-RESPONSE GRADIENT (MIMIC-IV, n={res['n']} norepi stays, "
         f"{res['deaths']} in-hospital deaths). CRUDE (age-era headline) quartile mortality "
         f"{crude} (Q4/Q1 risk ratio {rr_crude}x). After FULL severity adjustment "
         f"(age + Charlson + van Walraven/Elixhauser + #vasopressors) by g-computation, the "
         f"STANDARDIZED quartile mortality is {adj} (adjusted Q4/Q1 RR {rr_adj}x "
         f"[{g['adj_q4_over_q1_rr_ci']}], adjusted risk difference "
         f"{g['adj_q4_minus_q1_riskdiff']} [{g['adj_q4_minus_q1_rd_ci']}]). "
         f"Adjusted gradient monotonic non-decreasing: {mono}; strictly increasing: {mono_s}; "
         f"adjusted ordinal linear-trend p={p}. ")
    if surv_frac is not None:
        v += (f"The excess Q4-vs-Q1 risk ratio above 1 retains {surv_frac:.0%} of its crude "
              f"magnitude after full adjustment. ")
    v += (f"LOCALISING THE ATTENUATION: adjusting for comorbidity WITHOUT #vasopressors leaves "
          f"adjusted Q4/Q1 RR {rr_nocard}x ({gnc['adjusted_mortality_per_quartile']}); ADDING "
          f"#vasopressors brings it to {rr_adj}x -- so "
          + ("most of the flattening is driven by #vasopressors (multi-pressor refractory shock), "
             "not by chronic comorbidity burden. "
             if (rr_nocard and rr_adj and (rr_nocard - rr_adj) > 0.5 * (rr_crude - rr_adj))
             else "comorbidity and #vasopressors each remove a share of the gradient. ")
          + f"PER-SD OR (gradient framing): full-severity {res['per_sd_or_full']['or_per_sd']} "
          f"{res['per_sd_or_full']['ci']} (age-only {res['per_sd_or_age_only']['or_per_sd']}). ")
    v += "VERDICT: " + tag + ". "
    if tag.startswith("SURVIVES") or tag.startswith("ATTENUATED BUT"):
        v += ("The monotone dose-response is NOT merely severity confounding -- it persists, "
              "graded, after standard comorbidity + cardiovascular-severity adjustment. The "
              "headline gradient holds in attenuated but real form. ")
    elif tag.startswith("FLATTENS"):
        v += ("HONEST: the headline gradient is largely a severity artifact -- once comorbidity "
              "and #vasopressors are standardized out, the quartiles are near-flat. ")
    else:
        v += ("HONEST: a real but materially attenuated gradient; a meaningful fraction of the "
              "crude Q1->Q4 spread is measured severity. ")
    v += ("CAVEAT: observational; severity captured by Charlson + van Walraven + #vasopressors "
          "(a cardiovascular-SOFA proxy) -- no GCS/PaO2-FiO2/lactate here, so residual confounding "
          "by acute physiology remains; the requirement marks risk, not a treatment effect.")
    return v


# ----------------------------------------------------------------------------- doc
def _doc(res):
    g = res.get("gradient_full_adjustment", {})
    gnc = res.get("gradient_comorbidity_no_nvaso", {})
    ga = res.get("gradient_age_only", {})
    L = ["# Severity attack on the MIMIC-IV norepinephrine dose-response gradient\n",
         "HOSTILE review of the headline finding *\"ICU norepinephrine requirement mortality "
         "climbs Q1 14% -> Q4 65%, monotonic\"* (mimic_outcomes_doseresponse.py), which is "
         "**age-adjusted only**. The attack: the gradient is just severity -- higher dose marks "
         "sicker patients. Here we adjust the quartile gradient for **real comorbidity + "
         "cardiovascular severity** (age + Charlson + van Walraven/Elixhauser + #vasopressors) by "
         "**g-computation / standardization** and ask whether the monotone Q1->Q4 gradient "
         "**survives or flattens**.\n",
         "Method: fit one logistic model `death ~ C(quartile) + covariates`; for each quartile q, "
         "set the WHOLE cohort to quartile q, predict each patient's risk under their real "
         "covariates, average -> the covariate-standardized adjusted mortality at dose-quartile q. "
         "Requirement = per-stay median norepinephrine rate (0<rate<=5 mcg/kg/min). Charlson + van "
         "Walraven reuse the Quan-2005 / vanWalraven-2009 scoring from mimic_severity_scores.py.\n",
         f"- Complete-case stays: **{res.get('n')}** ({res.get('deaths')} in-hospital deaths, "
         f"rate {res.get('event_rate')}).",
         f"- Stays per quartile: {res.get('n_per_quartile')}; dose range per quartile "
         f"(mcg/kg/min): {res.get('dose_range_per_quartile')}.\n"]
    cd = res.get("charlson_distribution", {}); vd = res.get("vanwalraven_distribution", {})
    L += [f"- Charlson per hadm: mean {cd.get('mean')} (SD {cd.get('sd')}); van Walraven mean "
          f"{vd.get('mean')} (SD {vd.get('sd')}).\n",
          "## 1+4. Adjusted dose-response gradient (g-computation) and monotonicity\n",
          "| Quartile | Crude mortality | Adjusted (age only) | Adjusted (age+Charlson+vanWalraven) "
          "| Adjusted (FULL +#vaso) |",
          "|---|---|---|---|---|"]
    crude = res.get("crude_mortality_per_quartile", [])
    af = g.get("adjusted_mortality_per_quartile", [])
    an = gnc.get("adjusted_mortality_per_quartile", [])
    aa = ga.get("adjusted_mortality_per_quartile", [])
    for i in range(len(crude)):
        L.append(f"| Q{i+1} | {crude[i]} | {aa[i] if i < len(aa) else ''} | "
                 f"{an[i] if i < len(an) else ''} | {af[i] if i < len(af) else ''} |")
    L += ["",
          f"- **Crude Q1 {crude[0]} -> Q4 {crude[-1]} (risk ratio "
          f"{res.get('crude_q4_over_q1_riskratio')}x).**",
          f"- **FULL-severity-adjusted Q1 {g.get('adj_q1')} -> Q4 {g.get('adj_q4')} "
          f"(adjusted risk ratio {g.get('adj_q4_over_q1_riskratio')}x "
          f"[{g.get('adj_q4_over_q1_rr_ci')}]; adjusted risk difference "
          f"{g.get('adj_q4_minus_q1_riskdiff')} [{g.get('adj_q4_minus_q1_rd_ci')}]).**",
          f"- Adjusted gradient monotonic non-decreasing: **{g.get('adjusted_monotonic_nondecreasing')}**; "
          f"strictly increasing: **{g.get('adjusted_strictly_increasing')}**.",
          f"- Adjusted ordinal linear-trend (quartile score in the covar model): OR "
          f"{g.get('adj_linear_trend_or_per_quartile_sd')}/quartile-SD, "
          f"p={g.get('adj_linear_trend_p')}.\n",
          "## 2. Adjusted per-SD OR (gradient framing)",
          f"- Full severity (age+Charlson+vanWalraven+#vaso): OR **{res.get('per_sd_or_full',{}).get('or_per_sd')}**/SD "
          f"{res.get('per_sd_or_full',{}).get('ci')}.",
          f"- Age only: OR {res.get('per_sd_or_age_only',{}).get('or_per_sd')}/SD "
          f"{res.get('per_sd_or_age_only',{}).get('ci')}.",
          "- (Should reproduce the ~3.0 full-adjustment OR from MIMIC_SEVERITY_SCORES.md.)\n",
          "## 3. Where does the attenuation come from? (#vasopressors localisation)",
          f"- Adjusted Q4/Q1 RR WITHOUT #vasopressors (age+Charlson+vanWalraven): "
          f"**{gnc.get('adj_q4_over_q1_riskratio')}x**.",
          f"- Adjusted Q4/Q1 RR WITH #vasopressors (full): **{g.get('adj_q4_over_q1_riskratio')}x**.",
          "- The drop between these two localises how much of the flattening is multi-pressor "
          "refractory shock (#vasopressors) vs chronic comorbidity burden.\n",
          "## Verdict", res.get("verdict", res.get("note", "insufficient data")), "",
          "## Methods / caveats",
          "- G-computation (direct standardization to the pooled covariate distribution) is used "
          "instead of reading a coefficient, because the logistic OR is non-collapsible; the "
          "standardized marginal risks are the apples-to-apples adjusted gradient.",
          "- Quartiles are rank-based equal-count bins on the median requirement, matching the "
          "headline module's binning so the crude column reproduces the published gradient.",
          "- Bootstrap 95% CIs resample stays (400 reps, seed " + str(SEED) + "). The adjusted "
          "linear-trend p is a Wald read from the observed information matrix.",
          "- Severity = Charlson + van Walraven (Quan 2005 / vanWalraven 2009, per hadm) + "
          "#vasopressors (cardiovascular-SOFA proxy). No GCS / PaO2-FiO2 / lactate (chartevents / "
          "labs not used here), so residual confounding by acute physiology remains. Observational; "
          "the requirement marks severity/risk, not a treatment effect."]
    open(os.path.join(_DOCS, "DOSERESPONSE_SEVERITY.md"), "w").write("\n".join(L) + "\n")


def main():
    try:
        st = os.statvfs(_CACHE)
        if st.f_bavail * st.f_frsize / 1e9 < 1.0:
            print("[drsev] ABORT (disk-safe): <1GB free", flush=True)
            return
    except OSError:
        pass
    for p in (NOREPI_CSV, VASO_CSV):
        if not os.path.exists(p):
            raise FileNotFoundError(f"{p} missing")
    res = model()
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    print("[drsev] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    print("[drsev] -> cache/doseresponse_severity.json, docs/DOSERESPONSE_SEVERITY.md", flush=True)


if __name__ == "__main__":
    main()
