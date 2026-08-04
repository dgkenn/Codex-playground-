"""requirement_specificity.py -- specificity / placebo / confounding hardening for
the LEAD finding: the EARLY norepinephrine dose-REQUIREMENT predicts the LATE
requirement (Spearman +0.54) and identifies vasoplegia-prone patients, adding
beyond clinical baseline (OOF -0.01 -> +0.19; docs/EARLY_ID_ROBUSTNESS.md).

A hostile reviewer attacks a single positive correlation from five angles. This
module runs all five on existing caches (NO new extraction), using NEPI norepi-only
epochs, splitting each case's TIME-ORDERED epochs into an early half and a late half
(cases with >= 4 epochs), and asks whether the early->late signal is REAL (specific,
non-placebo, not a case-mix artifact, not a selection artifact, not leverage-driven):

  1. SPECIFICITY / INCREMENTAL-OVER-HEMODYNAMICS -- does early dose-requirement predict
     the LATE requirement BEYOND early MAP and early HR? Partial Spearman of early-dose
     vs late-req controlling early map_mean + hr_mean, plus a nested OOF
     ([early MAP,HR] vs [early MAP,HR,dose]). The DOSE must add unique information.
  2. PLACEBO predictors -- do early map_mean and early hr_mean PER SE predict the late
     requirement? They should be WEAKER than early dose; if a placebo predicts as well,
     the signal is non-specific.
  3. CASE-MIX robustness -- recompute the early->late Spearman EXCLUDING liver-transplant
     cases and EXCLUDING the cardiac/CPB-proxy (aortic/aneurysm vascular) cases. Does it
     hold off the high-vasoplegia surgeries? (Note: VitalDB is a non-cardiac cohort -- it
     has NO true CPB; the aortic-vascular set is the closest proxy, stated honestly.)
  4. SELECTION BIAS -- compare INCLUDED (>=4 stable epochs) vs EXCLUDED pressor cases on
     age / asa / weight and composite-outcome rate. Quantifies how selected/sicker the
     analyzable subset is (limits generalizability). Reported honestly, not hidden.
  5. INFLUENCE / JACKKNIFE -- leave-one-case-out: is the early->late Spearman driven by a
     few high-leverage cases? Reports min/max jackknife r and the most influential case.

HONEST about small N (~52 pressor cases with epochs; ~40 with >= 4 epochs). Each attack
gets a clear verdict: survives / weakened / fails.

stdlib only at import; numpy/pandas/scipy/sklearn lazy.
Run: python3 -m vitaldb_aki.analysis.requirement_specificity
"""
from __future__ import annotations
import json, os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628

EPOCHS = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
CASES = os.path.join(_CACHE, "cases.csv")
COHORT = os.path.join(_CACHE, "cohort_composite.csv")
OUT_JSON = os.path.join(_CACHE, "requirement_specificity.json")
OUT_DOC = os.path.join(_DOCS, "REQUIREMENT_SPECIFICITY.md")

MIN_EPOCHS = 4   # need >= 4 time-ordered epochs to split into early-half / late-half

# Surgery exclusion sets for the case-mix attack (matched on lowercased opname/optype).
# VitalDB (SNUH) is a NON-cardiac surgical cohort: it has no CABG/valve/true CPB. The
# closest high-vasoplegia non-transplant surgeries are the aortic / aneurysm vascular
# cases -- used as a "cardiac/CPB proxy", stated honestly as a proxy not real CPB.
_LIVERTX_KEYS = ("liver transplant",)
_CARDIAC_PROXY_KEYS = ("aneurysm", "aortic", "aorto", "aortoiliac", "aortofemoral",
                       "aortorenal", "ilioiliac", "endovascular")


# ----------------------------------------------------------------- data assembly
def _epoch_table():
    """NEPI norepi-only epochs with a valid per-kg dose (the lead-finding substrate)."""
    import pandas as pd
    df = pd.read_csv(EPOCHS, low_memory=False)
    for c in ("dose_per_kg", "map_mean", "hr_mean", "norepi_only", "t_start"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    return df[(df["drug"] == "NEPI") & (df["norepi_only"] == 1)
              & df["dose_per_kg"].notna()].copy()


def _per_case(q):
    """Per case (>= MIN_EPOCHS epochs): early-half vs late-half medians of dose, MAP, HR,
    over the TIME-ORDERED epochs. early/late halves are DISJOINT (no overlap)."""
    import numpy as np
    rows = {}
    for cid, g in q.groupby("caseid"):
        g = g.sort_values("t_start")
        if len(g) < MIN_EPOCHS:
            continue
        h = len(g) // 2
        e, l = g.iloc[:h], g.iloc[h:]
        rows[cid] = {
            "n_epochs": int(len(g)),
            "early_dose": float(np.median(e["dose_per_kg"])),
            "late_dose": float(np.median(l["dose_per_kg"])),
            "early_map": float(np.nanmedian(e["map_mean"])),
            "early_hr": float(np.nanmedian(e["hr_mean"])),
        }
    return rows


def _case_meta():
    import pandas as pd
    cs = pd.read_csv(CASES, low_memory=False, encoding="utf-8-sig")
    idc = [c for c in cs.columns if c.lstrip("﻿").lower() == "caseid"][0]
    cs = cs.rename(columns={idc: "caseid"})
    cs["caseid"] = cs["caseid"].astype(str)
    for c in ("age", "asa", "weight"):
        cs[c] = pd.to_numeric(cs.get(c), errors="coerce")
    for c in ("optype", "opname"):
        if c not in cs.columns:
            cs[c] = ""
        cs[c] = cs[c].fillna("").astype(str)
    return cs[["caseid", "age", "asa", "weight", "optype", "opname"]]


def _composite_map():
    import pandas as pd
    if not os.path.exists(COHORT):
        return {}
    co = pd.read_csv(COHORT, low_memory=False, encoding="utf-8-sig")
    co["caseid"] = co["caseid"].astype(str)
    co["composite"] = pd.to_numeric(co["composite"], errors="coerce")
    return dict(zip(co["caseid"], co["composite"]))


# ------------------------------------------------------------- statistical bits
def _spearman(x, y):
    import numpy as np
    from scipy import stats
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 5:
        return None, None, int(m.sum())
    r, p = stats.spearmanr(x[m], y[m])
    return round(float(r), 3), round(float(p), 4), int(m.sum())


def _partial_spearman(x, y, controls):
    """Partial Spearman of x vs y controlling for `controls` (list of arrays): rank-
    transform everything, OLS-residualize x and y on the controls, correlate residuals.
    Returns (partial_r, n)."""
    import numpy as np
    from scipy import stats
    cols = [np.asarray(x, float), np.asarray(y, float)] + [np.asarray(c, float) for c in controls]
    M = np.column_stack(cols)
    m = np.all(np.isfinite(M), axis=1)
    M = M[m]
    if M.shape[0] < 8:
        return None, int(M.shape[0])
    R = np.column_stack([stats.rankdata(M[:, j]) for j in range(M.shape[1])])
    xr, yr, Z = R[:, 0], R[:, 1], R[:, 2:]
    Z1 = np.column_stack([np.ones(len(xr)), Z])
    bx, *_ = np.linalg.lstsq(Z1, xr, rcond=None)
    by, *_ = np.linalg.lstsq(Z1, yr, rcond=None)
    rx, ry = xr - Z1 @ bx, yr - Z1 @ by
    if np.std(rx) < 1e-9 or np.std(ry) < 1e-9:
        return None, int(M.shape[0])
    return round(float(np.corrcoef(rx, ry)[0, 1]), 3), int(M.shape[0])


def _oof_spear(X, y, k=5):
    """Out-of-fold Spearman of a RidgeCV prediction (mirrors early_id_robustness)."""
    import numpy as np
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    y = np.asarray(y, float)
    if len(y) < 15 or X.shape[1] == 0:
        return None
    oof = np.full(len(y), np.nan)
    kk = max(2, min(k, len(y) // 3))
    for tr, te in KFold(kk, shuffle=True, random_state=SEED).split(X):
        p = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                      ("m", RidgeCV(alphas=(.1, 1, 10, 100)))])
        p.fit(X[tr], y[tr]); oof[te] = p.predict(X[te])
    m = np.isfinite(oof) & np.isfinite(y)
    return round(float(stats.spearmanr(oof[m], y[m])[0]), 3) if m.sum() >= 10 else None


# ------------------------------------------------------------------- the attacks
def attack1_specificity(pc):
    """Does early dose predict LATE requirement BEYOND early MAP and early HR?"""
    import numpy as np
    cids = list(pc.keys())
    early = [pc[c]["early_dose"] for c in cids]
    late = [pc[c]["late_dose"] for c in cids]
    emap = [pc[c]["early_map"] for c in cids]
    ehr = [pc[c]["early_hr"] for c in cids]
    raw_r, raw_p, n = _spearman(early, late)
    part_r, n_part = _partial_spearman(early, late, [emap, ehr])
    X = np.column_stack([emap, ehr]).astype(float)
    Xd = np.column_stack([emap, ehr, early]).astype(float)
    y = np.asarray(late, float)
    oof_hemo = _oof_spear(X, y)
    oof_hemo_dose = _oof_spear(Xd, y)
    # Two independent legs that can disagree -- report both honestly:
    #   (a) PARTIAL leg: dose keeps unique early->late rank association after removing
    #       early MAP & HR. This is the specificity test proper.
    #   (b) OOF-INCREMENT leg: dose lifts a cross-validated hemodynamics-only model.
    #       At N~52 this leg is noisy (a single Ridge fold can erase a real +0.05).
    # survives = both clear; weakened = partial survives but OOF does not add (the late
    # requirement is partly forecastable from early MAP alone); fails = partial collapses.
    inc = (oof_hemo_dose - oof_hemo) if (oof_hemo is not None and oof_hemo_dose is not None) else None
    partial_ok = part_r is not None and part_r >= 0.25
    oof_ok = inc is not None and inc > 0.05
    if partial_ok and oof_ok:
        verdict = "survives"
    elif partial_ok:
        verdict = "weakened"      # specific by partial-r, but no OOF lift over hemodynamics
    elif part_r is not None and part_r >= 0.10:
        verdict = "weakened"
    else:
        verdict = "fails"
    return {"n": n,
            "raw_early_late_spearman": raw_r, "raw_p": raw_p,
            "partial_spearman_controlling_earlyMAP_earlyHR": part_r, "n_partial": n_part,
            "oof_hemodynamics_only": oof_hemo,
            "oof_hemodynamics_plus_dose": oof_hemo_dose,
            "oof_dose_increment": (round(oof_hemo_dose - oof_hemo, 3)
                                   if (oof_hemo is not None and oof_hemo_dose is not None) else None),
            "verdict": verdict,
            "interpretation": "TWO legs. PARTIAL leg: dose must keep a rank association "
            "with the late requirement after removing early MAP & HR -- this is the "
            "specificity test (if it collapses the 'requirement' is just early BP/HR in a "
            "costume). OOF-INCREMENT leg: dose should also lift a cross-validated "
            "hemodynamics-only model. 'weakened' = partial survives but OOF does not add "
            "(the late requirement is partly forecastable from early MAP alone, and at "
            "N~52 the OOF leg is noisy); 'fails' = partial itself collapses."}


def attack2_placebo(pc):
    """Do early MAP and early HR PER SE predict late requirement? They should be weaker."""
    cids = list(pc.keys())
    late = [pc[c]["late_dose"] for c in cids]
    early = [pc[c]["early_dose"] for c in cids]
    dose_r, dose_p, _ = _spearman(early, late)
    map_r, map_p, _ = _spearman([pc[c]["early_map"] for c in cids], late)
    hr_r, hr_p, _ = _spearman([pc[c]["early_hr"] for c in cids], late)
    # the real predictor (dose) should dominate both placebos in |r|
    def _abs(v): return abs(v) if v is not None else -1.0
    margin_map = round(_abs(dose_r) - _abs(map_r), 3) if dose_r is not None else None
    margin_hr = round(_abs(dose_r) - _abs(hr_r), 3) if dose_r is not None else None
    survives = (dose_r is not None
                and _abs(dose_r) >= _abs(map_r) + 0.10
                and _abs(dose_r) >= _abs(hr_r) + 0.10)
    weakened = (dose_r is not None
                and _abs(dose_r) > _abs(map_r) and _abs(dose_r) > _abs(hr_r)
                and not survives)
    verdict = "survives" if survives else ("weakened" if weakened else "fails")
    return {"early_dose_vs_late_spearman": dose_r, "early_dose_p": dose_p,
            "placebo_early_MAP_vs_late_spearman": map_r, "placebo_early_MAP_p": map_p,
            "placebo_early_HR_vs_late_spearman": hr_r, "placebo_early_HR_p": hr_p,
            "abs_margin_dose_over_MAP": margin_map, "abs_margin_dose_over_HR": margin_hr,
            "verdict": verdict,
            "interpretation": "early MAP & HR are placebo predictors of the late "
            "requirement. The dose-requirement should out-predict both by a clear |r| "
            "margin; if a placebo matches it, the early->late link is non-specific "
            "hemodynamic persistence, not a vasopressor-requirement trait."}


def attack3_casemix(pc, meta):
    """Recompute early->late Spearman excluding liver-transplant and cardiac/CPB-proxy."""
    optype = dict(zip(meta["caseid"], meta["optype"].str.lower()))
    opname = dict(zip(meta["caseid"], meta["opname"].str.lower()))

    def _is(cid, keys):
        s = (opname.get(cid, "") + " " + optype.get(cid, ""))
        return any(k in s for k in keys)

    def _sub(exclude_keys):
        cids = [c for c in pc if not _is(c, exclude_keys)]
        r, p, n = _spearman([pc[c]["early_dose"] for c in cids],
                            [pc[c]["late_dose"] for c in cids])
        return r, p, n

    full_r, full_p, full_n = _spearman([pc[c]["early_dose"] for c in pc],
                                       [pc[c]["late_dose"] for c in pc])
    no_liver_r, no_liver_p, no_liver_n = _sub(_LIVERTX_KEYS)
    no_card_r, no_card_p, no_card_n = _sub(_CARDIAC_PROXY_KEYS)
    no_both_r, no_both_p, no_both_n = _sub(_LIVERTX_KEYS + _CARDIAC_PROXY_KEYS)
    n_liver = sum(1 for c in pc if _is(c, _LIVERTX_KEYS))
    n_card = sum(1 for c in pc if _is(c, _CARDIAC_PROXY_KEYS))

    def _ok(r):  # holds if still a clear positive association
        return r is not None and r >= 0.30
    survives = all(_ok(r) for r in (no_liver_r, no_card_r, no_both_r))
    weakened = (not survives) and all((r is not None and r >= 0.15)
                                      for r in (no_liver_r, no_card_r, no_both_r))
    verdict = "survives" if survives else ("weakened" if weakened else "fails")
    return {"full_spearman": full_r, "full_n": full_n,
            "n_livertx_in_set": n_liver, "n_cardiac_proxy_in_set": n_card,
            "excl_livertx_spearman": no_liver_r, "excl_livertx_n": no_liver_n,
            "excl_cardiac_proxy_spearman": no_card_r, "excl_cardiac_proxy_n": no_card_n,
            "excl_both_spearman": no_both_r, "excl_both_n": no_both_n,
            "verdict": verdict,
            "interpretation": "the early->late link must hold OFF the highest-vasoplegia "
            "surgeries (liver transplant; aortic/aneurysm vascular as a CPB proxy -- "
            "VitalDB has NO true cardiac/CPB surgery). If it only exists because a few "
            "transplant/aortic cases anchor both ends, it is case-mix, not a trait."}


def attack4_selection(q, pc, meta, comp):
    """INCLUDED (>=4 epochs) vs EXCLUDED pressor cases: age/asa/weight + composite rate."""
    import numpy as np
    all_pressor = set(q["caseid"].unique())
    included = set(pc.keys())
    excluded = all_pressor - included
    age = dict(zip(meta["caseid"], meta["age"]))
    asa = dict(zip(meta["caseid"], meta["asa"]))
    wt = dict(zip(meta["caseid"], meta["weight"]))

    def _summ(ids, d):
        vals = [d.get(c) for c in ids]
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        return (round(float(np.median(vals)), 2), len(vals)) if vals else (None, 0)

    def _comp_rate(ids):
        vals = [comp.get(c) for c in ids]
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        return (round(float(np.mean(vals)), 3), len(vals)) if vals else (None, 0)

    inc_age, _ = _summ(included, age); exc_age, _ = _summ(excluded, age)
    inc_asa, _ = _summ(included, asa); exc_asa, _ = _summ(excluded, asa)
    inc_wt, _ = _summ(included, wt); exc_wt, _ = _summ(excluded, wt)
    inc_comp, inc_comp_n = _comp_rate(included)
    exc_comp, exc_comp_n = _comp_rate(excluded)
    # Mann-Whitney on age/asa for whether included differ (descriptive)
    from scipy import stats

    def _mw(d):
        a = [d[c] for c in included if d.get(c) is not None and np.isfinite(d.get(c))]
        b = [d[c] for c in excluded if d.get(c) is not None and np.isfinite(d.get(c))]
        if len(a) < 5 or len(b) < 5:
            return None
        return round(float(stats.mannwhitneyu(a, b, alternative="two-sided")[1]), 4)

    rate_ratio = (round(inc_comp / exc_comp, 2)
                  if (inc_comp and exc_comp and exc_comp > 0) else None)
    # this attack does not "fail" the finding; it BOUNDS generalizability. Verdict
    # = how selected the analyzable subset is.
    selected = (rate_ratio is not None and rate_ratio >= 1.3) or \
               (inc_asa is not None and exc_asa is not None and inc_asa > exc_asa)
    verdict = ("selected-sicker-subset (generalizes to monitored pressor patients only)"
               if selected else "included subset not markedly sicker than excluded")
    return {"n_pressor_cases_with_any_epoch": len(all_pressor),
            "n_included_ge4_epochs": len(included), "n_excluded": len(excluded),
            "included": {"median_age": inc_age, "median_asa": inc_asa,
                         "median_weight": inc_wt,
                         "composite_outcome_rate": inc_comp, "n_with_outcome": inc_comp_n},
            "excluded": {"median_age": exc_age, "median_asa": exc_asa,
                         "median_weight": exc_wt,
                         "composite_outcome_rate": exc_comp, "n_with_outcome": exc_comp_n},
            "composite_rate_ratio_incl_over_excl": rate_ratio,
            "mannwhitney_p_age": _mw(age), "mannwhitney_p_asa": _mw(asa),
            "verdict": verdict,
            "interpretation": "the analyzable subset requires >= 4 stable norepi-only "
            "epochs, i.e. sustained pressor support -> structurally enriched for sicker, "
            "longer-pressor patients. Reported honestly: the finding generalizes to "
            "ALREADY-on-pressor monitored patients, not to all-comers."}


def attack5_jackknife(pc):
    """Leave-one-case-out early->late Spearman: leverage / influence diagnostic."""
    import numpy as np
    from scipy import stats
    cids = list(pc.keys())
    early = np.array([pc[c]["early_dose"] for c in cids], float)
    late = np.array([pc[c]["late_dose"] for c in cids], float)
    full = float(stats.spearmanr(early, late)[0])
    rs = []
    for i in range(len(cids)):
        idx = [j for j in range(len(cids)) if j != i]
        rs.append(float(stats.spearmanr(early[idx], late[idx])[0]))
    rs = np.array(rs)
    imin, imax = int(np.argmin(rs)), int(np.argmax(rs))
    # most-influential = whose removal moves r most (in absolute terms)
    infl = np.abs(rs - full)
    imost = int(np.argmax(infl))
    # survives if even the worst-case jackknife r stays clearly positive
    survives = float(rs.min()) >= 0.30
    weakened = (not survives) and float(rs.min()) >= 0.15
    verdict = "survives" if survives else ("weakened" if weakened else "fails")
    return {"n": len(cids), "full_spearman": round(full, 3),
            "jackknife_min_r": round(float(rs.min()), 3),
            "jackknife_max_r": round(float(rs.max()), 3),
            "jackknife_r_range": round(float(rs.max() - rs.min()), 3),
            "most_influential_caseid": cids[imost],
            "r_without_most_influential": round(float(rs[imost]), 3),
            "case_dropping_r_lowest": cids[imin], "case_dropping_r_highest": cids[imax],
            "verdict": verdict,
            "interpretation": "leave-one-case-out: if dropping any single case collapses "
            "the early->late Spearman, the finding rides on a few high-leverage patients. "
            "The min jackknife r is the worst-case; it should stay clearly positive."}


# ----------------------------------------------------------------------- driver
def run():
    q = _epoch_table()
    pc = _per_case(q)
    meta = _case_meta()
    comp = _composite_map()
    res = {"seed": SEED, "min_epochs_per_case": MIN_EPOCHS,
           "n_norepi_only_cases": int(q["caseid"].nunique()),
           "n_cases_ge4_epochs": len(pc)}
    if len(pc) < 10:
        res["error"] = f"only {len(pc)} cases with >= {MIN_EPOCHS} epochs; too few to attack."
        return res
    res["attack1_specificity_incremental_over_hemodynamics"] = attack1_specificity(pc)
    res["attack2_placebo_predictors"] = attack2_placebo(pc)
    res["attack3_casemix_robustness"] = attack3_casemix(pc, meta)
    res["attack4_selection_bias"] = attack4_selection(q, pc, meta, comp)
    res["attack5_influence_jackknife"] = attack5_jackknife(pc)
    survives = sum(1 for k in ("attack1_specificity_incremental_over_hemodynamics",
                               "attack2_placebo_predictors", "attack3_casemix_robustness",
                               "attack5_influence_jackknife")
                   if res[k]["verdict"] == "survives")
    res["n_core_attacks_survived"] = f"{survives}/4 (attack4 bounds generalizability, not pass/fail)"
    return res


def _doc(res):
    L = ["# Requirement specificity / placebo / confounding hardening (lead-finding defense)\n",
         "Hostile-review battery for the LEAD finding: the EARLY norepinephrine "
         "dose-REQUIREMENT predicts the LATE requirement (Spearman +0.54) and adds beyond "
         "clinical baseline (docs/EARLY_ID_ROBUSTNESS.md). Each case's TIME-ORDERED "
         f"norepi-only epochs are split into an early half and a late half (cases with "
         f">= {MIN_EPOCHS} epochs). NO new extraction.\n",
         f"- NEPI norepi-only cases: **{res.get('n_norepi_only_cases')}**; "
         f"with >= {MIN_EPOCHS} epochs (analyzable): **{res.get('n_cases_ge4_epochs')}**.\n"]
    if res.get("error"):
        L.append("_" + res["error"] + "_\n")
        open(OUT_DOC, "w").write("\n".join(L)); return

    a1 = res["attack1_specificity_incremental_over_hemodynamics"]
    L += ["## Attack 1 -- Specificity / incremental over hemodynamics  (`%s`)" % a1["verdict"],
          f"Does early dose predict LATE requirement BEYOND early MAP & HR? (n={a1['n']})",
          f"- Raw early->late Spearman: **{a1['raw_early_late_spearman']}** (p={a1['raw_p']}).",
          f"- **Partial Spearman controlling early MAP + early HR: {a1['partial_spearman_controlling_earlyMAP_earlyHR']}** "
          f"(n={a1['n_partial']}).",
          f"- Nested OOF: hemodynamics-only **{a1['oof_hemodynamics_only']}** vs "
          f"hemodynamics+dose **{a1['oof_hemodynamics_plus_dose']}** "
          f"(dose increment **{a1['oof_dose_increment']}**).",
          f"  _{a1['interpretation']}_\n",
          "## Attack 2 -- Placebo predictors  (`%s`)" % res["attack2_placebo_predictors"]["verdict"]]
    a2 = res["attack2_placebo_predictors"]
    L += [f"Do early MAP / HR per se predict the late requirement? (they should be weaker)",
          f"- early DOSE -> late: **{a2['early_dose_vs_late_spearman']}** (p={a2['early_dose_p']}).",
          f"- placebo early MAP -> late: {a2['placebo_early_MAP_vs_late_spearman']} (p={a2['placebo_early_MAP_p']}).",
          f"- placebo early HR -> late: {a2['placebo_early_HR_vs_late_spearman']} (p={a2['placebo_early_HR_p']}).",
          f"- |r| margin of dose over MAP {a2['abs_margin_dose_over_MAP']}, over HR {a2['abs_margin_dose_over_HR']}.",
          f"  _{a2['interpretation']}_\n"]
    a3 = res["attack3_casemix_robustness"]
    L += ["## Attack 3 -- Case-mix robustness  (`%s`)" % a3["verdict"],
          f"Early->late Spearman off the high-vasoplegia surgeries:",
          f"- full: **{a3['full_spearman']}** (n={a3['full_n']}).",
          f"- excl liver-transplant ({a3['n_livertx_in_set']} cases): **{a3['excl_livertx_spearman']}** "
          f"(n={a3['excl_livertx_n']}).",
          f"- excl cardiac/CPB-proxy aortic/aneurysm ({a3['n_cardiac_proxy_in_set']} cases): "
          f"**{a3['excl_cardiac_proxy_spearman']}** (n={a3['excl_cardiac_proxy_n']}).",
          f"- excl both: **{a3['excl_both_spearman']}** (n={a3['excl_both_n']}).",
          f"  _{a3['interpretation']}_\n"]
    a4 = res["attack4_selection_bias"]
    L += ["## Attack 4 -- Selection bias  (`%s`)" % a4["verdict"],
          f"INCLUDED (>= {MIN_EPOCHS} epochs, n={a4['n_included_ge4_epochs']}) vs EXCLUDED "
          f"pressor cases (n={a4['n_excluded']}):",
          f"- age: incl {a4['included']['median_age']} vs excl {a4['excluded']['median_age']} "
          f"(MWU p={a4['mannwhitney_p_age']}).",
          f"- ASA: incl {a4['included']['median_asa']} vs excl {a4['excluded']['median_asa']} "
          f"(MWU p={a4['mannwhitney_p_asa']}).",
          f"- weight: incl {a4['included']['median_weight']} vs excl {a4['excluded']['median_weight']}.",
          f"- **composite-outcome rate: incl {a4['included']['composite_outcome_rate']} "
          f"vs excl {a4['excluded']['composite_outcome_rate']}** "
          f"(rate ratio {a4['composite_rate_ratio_incl_over_excl']}).",
          f"  _{a4['interpretation']}_\n"]
    a5 = res["attack5_influence_jackknife"]
    L += ["## Attack 5 -- Influence / jackknife  (`%s`)" % a5["verdict"],
          f"Leave-one-case-out early->late Spearman (full {a5['full_spearman']}, n={a5['n']}):",
          f"- **jackknife r range: [{a5['jackknife_min_r']}, {a5['jackknife_max_r']}]** "
          f"(span {a5['jackknife_r_range']}).",
          f"- most influential case {a5['most_influential_caseid']} "
          f"(r without it {a5['r_without_most_influential']}).",
          f"  _{a5['interpretation']}_\n",
          "## Summary",
          f"- Core attacks survived: **{res['n_core_attacks_survived']}**.",
          "- Verdicts: "
          f"specificity `{a1['verdict']}`, placebo `{a2['verdict']}`, case-mix `{a3['verdict']}`, "
          f"jackknife `{a5['verdict']}`; selection: {a4['verdict']}.\n",
          "## Caveats (honest, small N)",
          f"- N is small: {res['n_cases_ge4_epochs']} cases with >= {MIN_EPOCHS} epochs. "
          "Partial-correlation and nested-OOF estimates are unstable at this N; treat magnitudes "
          "as directional, not precise.",
          "- VitalDB (SNUH) is a NON-cardiac surgical cohort: there is NO true cardiac/CPB surgery. "
          "The 'cardiac/CPB proxy' is aortic/aneurysm vascular surgery -- the closest high-vasoplegia "
          "non-transplant set -- stated as a proxy, not real CPB.",
          "- Attack 4 BOUNDS generalizability rather than passing/failing the finding: the analyzable "
          "subset is structurally enriched for sustained-pressor (sicker) patients.",
          "- All observational, single-centre; identifies WHO is vasoplegia-prone early, not that "
          "acting on it helps."]
    open(OUT_DOC, "w").write("\n".join(L) + "\n")


def main():
    res = run()
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    print(f"[reqspec] cases >= {MIN_EPOCHS} epochs: {res.get('n_cases_ge4_epochs')}", flush=True)
    if res.get("error"):
        print("[reqspec]", res["error"]); return
    for k in ("attack1_specificity_incremental_over_hemodynamics", "attack2_placebo_predictors",
              "attack3_casemix_robustness", "attack4_selection_bias", "attack5_influence_jackknife"):
        print(f"[reqspec] {k}: {res[k]['verdict']}", flush=True)
    print(f"[reqspec] core survived: {res['n_core_attacks_survived']}", flush=True)
    print("[reqspec] -> docs/REQUIREMENT_SPECIFICITY.md, cache/requirement_specificity.json", flush=True)


if __name__ == "__main__":
    main()
