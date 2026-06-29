"""construct_validity.py -- HOSTILE construct-validity test of the vasopressor
dose-REQUIREMENT phenotype as a VASOPLEGIA / vascular-tone index.

THE ATTACK (a reviewer's words)
-------------------------------
"You call this a VASOPLEGIA signal, but a high vasopressor requirement can reflect
ANY reason for pressor use -- hypovolemia, cardiogenic shock, bradycardia, deep
anaesthesia, bleeding. You have NOT shown the requirement is specifically
vascular-tone/vasoplegia. Your only direct vasoplegia anchor (vs measured SVR) was
n=15 with the WRONG sign (+0.18). The construct is unproven."

This module assembles ALL available evidence on whether the requirement indexes
vascular tone / vasoplegia *specifically*, and reports -- honestly -- how strong
(or weak) the construct is. Four tests:

  1. CONVERGENT (vs vascular TONE). The Pivot-2 arterial-line tone carrier is the
     diastolic/MAP form factor (map_dia_form_factor / diastolic_over_map). A
     vasoplegic patient has LOW diastolic tone -> a vasoplegia requirement should
     correlate NEGATIVELY with the form factor. Spearman + bootstrap CI.

  2. DISCRIMINANT (vs PRELOAD / hypovolemia). High pulse-pressure variation
     (art_ppv_burden_min) marks hypovolemia / preload-responsiveness -- a DIFFERENT
     reason to need pressor. If the requirement is specifically vasoplegia (low
     tone) and NOT hypovolemia, it should be MORE related to low tone than to high
     PPV. We compare the two correlations (and partial each out of the other).

  3. SVR ANCHOR (honest). Re-report requirement vs EV1000 svr_mean at whatever N
     exists -- explicit about the N and the (wrong) sign. No spin.

  4. ETIOLOGY (surgery type). Does the requirement run high in vasoplegia-prone
     surgery (liver transplantation) vs cleaner cases? Descriptive, honest.

Per-case requirement phenotype = median NEPI norepi-only dose_per_kg in the MAP
band [55, 80] over epochs with >=2 qualifying epochs (identical to
pressor_requirement.py).

stdlib only at import; numpy/pandas/scipy/sklearn lazy.
Run: python3 -m vitaldb_aki.analysis.construct_validity
"""
from __future__ import annotations
import csv as _csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628

EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
CASES_CSV = os.path.join(_CACHE, "cases.csv")
OUT_JSON = os.path.join(_CACHE, "construct_validity.json")
OUT_DOC = os.path.join(_DOCS, "CONSTRUCT_VALIDITY.md")

# phenotype definition (must match pressor_requirement.py)
PRIMARY_DRUG = "NEPI"
TARGET_LO, TARGET_HI = 55.0, 80.0
MIN_EPOCHS_PER_CASE = 2

# tone / preload carriers (combine ALL shards for max coverage)
CBS_FILES = (
    ["combined_biosignal_features.csv"]
    + [f"combined_biosignal_features_s{s}.csv" for s in range(4)]
)
LEVER_FILES = [f"lever_axes_s{s}.csv" for s in range(4)] + ["lever_axes.csv"]
# TONE carriers.  NOTE (data-quality, verified): `map_dia_form_factor` is a
# DEGENERATE column -- constant 0.3333 with SD=0.00000 across all 631 cases, so it
# carries NO information and any correlation against it is tie-broken noise.  The
# REAL tone variation lives in `diastolic_over_map` (SD~0.044, range 0.58-0.88;
# high = preserved diastolic tone, low = vasoplegic).  We therefore use
# diastolic_over_map as the PRIMARY tone carrier and report form_factor only to
# expose the degeneracy.
TONE_DOM = "diastolic_over_map"          # PRIMARY tone carrier; high = preserved tone, low = vasoplegic
TONE_FORM = "map_dia_form_factor"        # DEGENERATE (constant 0.3333) -- reported, not relied on
PPV_BURDEN = "art_ppv_burden_min"        # high = hypovolemia / preload-responsive
PPV_MEAN = "art_ppv_mean"
FEAT_COLS = [TONE_FORM, TONE_DOM, PPV_BURDEN, PPV_MEAN]


# ----------------------------------------------------------------------------
# data loading (stdlib)
# ----------------------------------------------------------------------------
def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(_csv.DictReader(f))


def _fnum(v):
    if v in (None, "", "None", "nan", "NaN"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _phenotype():
    """Per-case requirement = median norepi-only NEPI dose_per_kg in MAP[55,80],
    cases with >= 2 qualifying epochs.  Returns {caseid: dose}."""
    from collections import defaultdict
    import statistics
    rows = _read(EPOCHS_CSV)
    by = defaultdict(list)
    for r in rows:
        if r.get("drug") != PRIMARY_DRUG:
            continue
        if r.get("norepi_only") != "1":
            continue
        d = _fnum(r.get("dose_per_kg"))
        m = _fnum(r.get("map_mean"))
        if d is None or m is None:
            continue
        if TARGET_LO <= m <= TARGET_HI:
            by[r["caseid"]].append(d)
    return {c: float(statistics.median(v)) for c, v in by.items()
            if len(v) >= MIN_EPOCHS_PER_CASE}


def _svr_by_case():
    """Mean EV1000 svr_mean over all epochs that carry one (sparse)."""
    from collections import defaultdict
    import statistics
    by = defaultdict(list)
    for r in _read(EPOCHS_CSV):
        s = _fnum(r.get("svr_mean"))
        if s is not None:
            by[r["caseid"]].append(s)
    return {c: float(statistics.mean(v)) for c, v in by.items()}


def _optype_by_case():
    out = {}
    for r in _read(EPOCHS_CSV):
        out[r["caseid"]] = r.get("optype", "")
    return out


def _opname_by_case():
    rows = _read(CASES_CSV)
    if not rows:
        return {}
    key = next((k for k in rows[0].keys() if k.lstrip("﻿") == "caseid"), None)
    if key is None:
        return {}
    return {r[key]: r.get("opname", "") for r in rows}


def _features():
    """Merge tone/PPV carriers across ALL cbs + lever shards.  cbs preferred where
    both carry a value; lever provides the bulk of the coverage.  {caseid: {col: v}}."""
    merged = {}
    # lever first (broad), then cbs overwrites (richer / canonical)
    for fn in LEVER_FILES + CBS_FILES:
        for r in _read(os.path.join(_CACHE, fn)):
            cid = r.get("caseid")
            if not cid:
                continue
            rec = merged.setdefault(cid, {})
            for c in FEAT_COLS:
                v = _fnum(r.get(c))
                if v is not None:
                    rec[c] = v   # later files (cbs) win
    return merged


# ----------------------------------------------------------------------------
# stats helpers (lazy sci stack)
# ----------------------------------------------------------------------------
def _spearman_ci(x, y, n_boot=5000, seed=SEED):
    import numpy as np
    from scipy import stats
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    if n < 4:
        return {"r": None, "p": None, "ci95": [None, None], "n": int(n)}
    r, p = stats.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(x[idx])) < 3 or len(np.unique(y[idx])) < 3:
            continue
        bs.append(stats.spearmanr(x[idx], y[idx])[0])
    ci = ([round(float(np.percentile(bs, 2.5)), 4),
           round(float(np.percentile(bs, 97.5)), 4)] if bs else [None, None])
    return {"r": round(float(r), 4), "p": round(float(p), 5),
            "ci95": ci, "n": int(n)}


def _partial_spearman(xa, xb, given):
    """partial Spearman corr(xa, xb | given) via rank-residualisation (OLS on ranks)."""
    import numpy as np
    from scipy import stats
    xa = np.asarray(xa, float)
    xb = np.asarray(xb, float)
    given = np.asarray(given, float).reshape(len(xa), -1)

    def _rr(v):
        rv = stats.rankdata(v)
        G = np.c_[np.ones(len(v)), given]
        beta, *_ = np.linalg.lstsq(G, rv, rcond=None)
        return rv - G @ beta

    ra, rb = _rr(xa), _rr(xb)
    if np.std(ra) < 1e-9 or np.std(rb) < 1e-9:
        return None
    return round(float(stats.spearmanr(ra, rb)[0]), 4)


def _aligned(pheno, feats, col):
    """Return (pheno_vals, feat_vals, caseids) for cases having both."""
    cids = [c for c in pheno if feats.get(c, {}).get(col) is not None]
    return ([pheno[c] for c in cids],
            [feats[c][col] for c in cids], cids)


# ----------------------------------------------------------------------------
# main analysis
# ----------------------------------------------------------------------------
def run():
    import numpy as np  # noqa: F401  (ensures sci stack present early, clearer error)

    pheno = _phenotype()
    feats = _features()
    svr = _svr_by_case()
    optype = _optype_by_case()
    opname = _opname_by_case()

    res = {
        "seed": SEED,
        "phenotype": {
            "definition": "median NEPI norepi-only dose_per_kg in MAP[55,80], >=2 epochs",
            "n_cases": len(pheno),
        },
        "attack": ("a high vasopressor requirement can reflect ANY reason for pressor "
                   "use (hypovolemia, cardiogenic shock, bradycardia, deep anaesthesia, "
                   "bleeding); the vasoplegia construct is unproven."),
    }

    # ---- TEST 1: CONVERGENT vs vascular TONE ---------------------------------
    # Degeneracy check: is each tone carrier informative at all?
    import numpy as np
    def _spread(col):
        vals = [feats[c][col] for c in feats if feats.get(c, {}).get(col) is not None]
        return {"n": len(vals), "sd": round(float(np.std(vals)), 6) if vals else None,
                "min": round(min(vals), 4) if vals else None,
                "max": round(max(vals), 4) if vals else None}
    spread_dom = _spread(TONE_DOM)
    spread_ff = _spread(TONE_FORM)

    # PRIMARY carrier = diastolic_over_map (the one with real variance).
    px, fx, _ = _aligned(pheno, feats, TONE_DOM)
    conv = _spearman_ci(px, fx)
    conv["carrier"] = TONE_DOM
    conv["expectation"] = ("NEGATIVE (vasoplegic = LOW diastolic tone = low "
                           "diastolic_over_map -> high requirement)")
    # form_factor reported only to expose its degeneracy.
    px2, fx2, _ = _aligned(pheno, feats, TONE_FORM)
    conv_ff = _spearman_ci(px2, fx2)
    conv_ff["carrier"] = TONE_FORM
    conv_ff["degenerate"] = (spread_ff["sd"] is not None and spread_ff["sd"] < 1e-4)
    conv_ff["note"] = ("DEGENERATE constant column (SD~0); correlation is tie-broken "
                       "NOISE and must not be relied on."
                       if conv_ff["degenerate"] else "informative")
    res["test1_convergent_tone"] = {
        "primary": conv,
        "form_factor_degenerate_check": conv_ff,
        "carrier_spread": {TONE_DOM: spread_dom, TONE_FORM: spread_ff},
    }

    # ---- TEST 2: DISCRIMINANT vs PRELOAD (PPV) -------------------------------
    pxp, ppv, cids_ppv = _aligned(pheno, feats, PPV_BURDEN)
    disc = _spearman_ci(pxp, ppv)
    disc["carrier"] = PPV_BURDEN
    disc["expectation"] = ("if vasoplegia-specific (NOT hypovolemia), requirement should "
                           "be LESS related to PPV than to low tone")
    pxp2, ppv2, _ = _aligned(pheno, feats, PPV_MEAN)
    disc_alt = _spearman_ci(pxp2, ppv2)
    disc_alt["carrier"] = PPV_MEAN

    # head-to-head on the COMMON subset (cases with BOTH tone and PPV):
    both = [c for c in pheno
            if feats.get(c, {}).get(TONE_DOM) is not None
            and feats.get(c, {}).get(PPV_BURDEN) is not None]
    h2h = {"n_common": len(both), "tone_carrier": TONE_DOM}
    if len(both) >= 8:
        p_b = [pheno[c] for c in both]
        tone_b = [feats[c][TONE_DOM] for c in both]
        ppv_b = [feats[c][PPV_BURDEN] for c in both]
        r_tone = _spearman_ci(p_b, tone_b)
        r_ppv = _spearman_ci(p_b, ppv_b)
        h2h["r_vs_tone"] = r_tone["r"]
        h2h["r_vs_ppv"] = r_ppv["r"]
        # partials: does tone survive controlling PPV, and vice-versa?
        h2h["tone_partial_given_ppv"] = _partial_spearman(p_b, tone_b, ppv_b)
        h2h["ppv_partial_given_tone"] = _partial_spearman(p_b, ppv_b, tone_b)
        # |tone| vs |ppv|: which mechanism dominates?
        if r_tone["r"] is not None and r_ppv["r"] is not None:
            h2h["tone_dominates"] = abs(r_tone["r"]) > abs(r_ppv["r"])
    res["test2_discriminant_preload"] = {
        "primary": disc, "alt_carrier": disc_alt, "head_to_head_common_subset": h2h,
    }

    # ---- TEST 3: SVR anchor (honest) ----------------------------------------
    sx, sy, svr_ids = [], [], []
    for c in pheno:
        if c in svr:
            sx.append(pheno[c]); sy.append(svr[c]); svr_ids.append(c)
    svr_res = _spearman_ci(sx, sy)
    svr_res["carrier"] = "EV1000 svr_mean (epoch-mean)"
    svr_res["expectation"] = "NEGATIVE (low SVR = vasoplegic = high requirement)"
    svr_res["honest_note"] = (
        f"n={svr_res['n']}; sign is "
        + ("POSITIVE (WRONG direction)" if (svr_res["r"] or 0) > 0 else
           "negative (expected)" if (svr_res["r"] or 0) < 0 else "~0")
        + " and underpowered. This is the soft spot of the construct."
        + (" CI crosses 0." if (svr_res["ci95"][0] is not None
            and svr_res["ci95"][0] <= 0 <= svr_res["ci95"][1]) else "")
    )
    res["test3_svr_anchor"] = svr_res

    # ---- TEST 4: ETIOLOGY by surgery type -----------------------------------
    from collections import defaultdict
    grp = defaultdict(list)
    for c in pheno:
        grp[optype.get(c, "Unknown") or "Unknown"].append(pheno[c])
    by_optype = {}
    for k, v in grp.items():
        v_sorted = sorted(v)
        med = v_sorted[len(v_sorted) // 2] if v_sorted else None
        by_optype[k] = {"n": len(v), "median_requirement": round(float(med), 5) if med is not None else None}
    # vasoplegia-prone (liver transplantation, captured under "Transplantation"
    # -- dominated by liver tx) vs the rest:
    tx_cids = [c for c in pheno
               if "transplant" in (opname.get(c, "").lower())
               or optype.get(c, "") == "Transplantation"]
    liver_cids = [c for c in pheno if "liver transplant" in opname.get(c, "").lower()]
    rest_cids = [c for c in pheno if c not in set(tx_cids)]
    etiol = {
        "by_optype": dict(sorted(by_optype.items(),
                                 key=lambda kv: -kv[1]["median_requirement"]
                                 if kv[1]["median_requirement"] is not None else 0)),
        "n_transplant": len(tx_cids),
        "n_liver_transplant": len(liver_cids),
    }
    if len(tx_cids) >= 3 and len(rest_cids) >= 3:
        import numpy as np
        from scipy import stats
        a = np.array([pheno[c] for c in tx_cids], float)
        b = np.array([pheno[c] for c in rest_cids], float)
        u, pmw = stats.mannwhitneyu(a, b, alternative="greater")
        etiol["transplant_vs_rest"] = {
            "median_transplant": round(float(np.median(a)), 5),
            "median_rest": round(float(np.median(b)), 5),
            "fold_higher": round(float(np.median(a) / np.median(b)), 2)
            if np.median(b) > 0 else None,
            "mannwhitney_p_one_sided_higher": round(float(pmw), 4),
            "direction_consistent_with_vasoplegia": bool(np.median(a) > np.median(b)),
        }
    if len(liver_cids) >= 3 and len(rest_cids) >= 3:
        import numpy as np
        al = np.array([pheno[c] for c in liver_cids], float)
        bl = np.array([pheno[c] for c in pheno if c not in set(liver_cids)], float)
        etiol["liver_tx_vs_rest"] = {
            "median_liver_tx": round(float(np.median(al)), 5),
            "median_rest": round(float(np.median(bl)), 5),
            "fold_higher": round(float(np.median(al) / np.median(bl)), 2)
            if np.median(bl) > 0 else None,
        }
    res["test4_etiology_surgery"] = etiol

    # ---- VERDICT -------------------------------------------------------------
    res["verdict"] = _verdict(res)

    with open(OUT_JSON, "w") as f:
        json.dump(res, f, indent=2)
    _doc(res)
    print(json.dumps(res["verdict"], indent=2))
    return res


def _verdict(res):
    conv = res["test1_convergent_tone"]["primary"]
    disc = res["test2_discriminant_preload"]["primary"]
    h2h = res["test2_discriminant_preload"]["head_to_head_common_subset"]
    svr = res["test3_svr_anchor"]
    etiol = res["test4_etiology_surgery"].get("transplant_vs_rest", {})

    conv_r = conv["r"]
    conv_ci_excl0 = (conv["ci95"][1] is not None and conv["ci95"][1] < 0)
    conv_dir = conv_r is not None and conv_r < 0
    # "meaningful" = right sign AND magnitude not trivially small
    conv_meaningful = conv_dir and abs(conv_r) >= 0.15
    # PPV (preload) signal strength and whether it dominates the (real) tone signal
    tone_partial = h2h.get("tone_partial_given_ppv")        # tone | PPV  (want < 0)
    ppv_partial = h2h.get("ppv_partial_given_tone")          # PPV  | tone (want > 0)
    r_tone = h2h.get("r_vs_tone")
    r_ppv = h2h.get("r_vs_ppv")
    tone_survives = tone_partial is not None and tone_partial < 0
    ppv_survives = ppv_partial is not None and ppv_partial > 0
    ppv_stronger = (r_ppv is not None and r_tone is not None
                    and abs(r_ppv) > abs(r_tone))
    svr_wrong = (svr["r"] or 0) > 0
    etiol_ok = etiol.get("direction_consistent_with_vasoplegia", False)
    etiol_sig = (etiol.get("mannwhitney_p_one_sided_higher") or 1) < 0.05

    bullets = []
    bullets.append(
        f"CONVERGENT vs REAL tone carrier (diastolic_over_map): Spearman {conv_r} "
        f"(95% CI {conv['ci95']}, n={conv['n']}). "
        + ("Right sign, CI excludes 0." if (conv_dir and conv_ci_excl0)
           else "Right sign and material magnitude, but CI crosses 0 (underpowered)."
           if conv_meaningful
           else "Right sign but the magnitude is NEAR-NULL -- weak convergent evidence."
           if conv_dir
           else "WRONG sign -- no convergent support.")
        + " (The originally-named carrier map_dia_form_factor is a constant/degenerate "
        "column; its earlier -0.26 was tie-broken noise -- discarded.)")
    bullets.append(
        f"DISCRIMINANT vs PPV/preload: requirement vs PPV-burden Spearman {disc['r']} "
        f"(n={disc['n']}); head-to-head (n={h2h.get('n_common')}): "
        f"r_tone={r_tone} vs r_ppv={r_ppv}. Partials: tone|PPV={tone_partial}, "
        f"PPV|tone={ppv_partial}. "
        + ("BOTH mechanisms carry INDEPENDENT signal (each survives partialling out the "
           "other), and PPV (hypovolemia) is at least as strong as tone -> the "
           "requirement is a MIXED preload+tone signal, NOT cleanly vasoplegia-specific."
           if (tone_survives and ppv_survives and ppv_stronger) else
           "Tone dominates and survives partialling out PPV -> not just hypovolemia."
           if (tone_survives and not ppv_stronger) else
           "PPV (preload/hypovolemia) is comparable-or-stronger -> requirement is NOT "
           "cleanly discriminated from hypovolemia at this N."))
    bullets.append(
        f"SVR anchor (gold standard): Spearman {svr['r']} at n={svr['n']} -- "
        + ("POSITIVE, the WRONG sign, underpowered. The direct vasoplegia anchor FAILS."
           if svr_wrong else "negative (expected) but underpowered."))
    bullets.append(
        "ETIOLOGY: transplant (liver-tx-dominated, vasoplegia-prone) median requirement "
        f"{etiol.get('median_transplant')} vs rest {etiol.get('median_rest')} "
        f"({etiol.get('fold_higher')}x, MW p={etiol.get('mannwhitney_p_one_sided_higher')}). "
        + ("Direction consistent with vasoplegia"
           + (" (significant)." if etiol_sig else " but NOT significant.")
           if etiol_ok else "Not higher in the vasoplegia-prone group -- inconsistent."))

    # overall grade -- count of genuinely supportive lines of evidence
    support = sum([conv_meaningful, (tone_survives and not ppv_stronger), etiol_ok])
    if conv_meaningful and conv_ci_excl0 and (tone_survives and not ppv_stronger) \
            and etiol_ok and not svr_wrong:
        grade = "SUPPORTED"
    elif (conv_dir and (etiol_ok or tone_survives)):
        grade = "PARTIALLY SUPPORTED"
    else:
        grade = "WEAK / UNPROVEN"

    summary = (
        f"{grade}. After correcting a data-quality defect (the named tone carrier "
        "map_dia_form_factor is a degenerate constant, so the earlier -0.26 convergent "
        "value was noise), the requirement's correlation with the REAL diastolic-tone "
        f"carrier is {conv_r} (n={conv['n']}, CI {conv['ci95']}) -- "
        + ("a material, vasoplegia-direction effect" if conv_meaningful
           else "right-signed but near-null") + ". "
        "On discriminant validity the requirement tracks PPV/preload "
        f"(r={disc['r']}) as strongly as -- or more strongly than -- tone, and both "
        "survive mutual partialling: it is a MIXED preload+tone vasopressor-need signal, "
        "not a pure vasoplegia index. It does run higher in vasoplegia-prone surgery "
        f"({etiol.get('fold_higher')}x) but not significantly. The DIRECT SVR anchor "
        f"(n={svr['n']}) still points the WRONG way (+{svr['r']}). "
        "BOTTOM LINE for the reviewer's attack: the attack LANDS in part -- the construct "
        "is NOT shown to be specifically vascular-tone. The evidence supports a weaker, "
        "honest claim: the requirement is a generic 'vasopressor-need / hemodynamic "
        "fragility' phenotype with a tone component, not a validated vasoplegia-specific "
        "marker. The vasoplegia label is aspirational until a powered independent SVR "
        "cohort confirms it.")

    return {"grade": grade, "support_score_of_3": support,
            "bullets": bullets, "summary": summary,
            "convergent_r": conv["r"], "convergent_carrier": conv["carrier"],
            "discriminant_ppv_r": disc["r"],
            "svr_anchor_n": svr["n"], "svr_anchor_r": svr["r"]}


def _doc(res):
    conv = res["test1_convergent_tone"]["primary"]
    conv_ff = res["test1_convergent_tone"]["form_factor_degenerate_check"]
    spr = res["test1_convergent_tone"]["carrier_spread"]
    disc = res["test2_discriminant_preload"]["primary"]
    h2h = res["test2_discriminant_preload"]["head_to_head_common_subset"]
    svr = res["test3_svr_anchor"]
    et = res["test4_etiology_surgery"]
    v = res["verdict"]

    L = []
    L.append("# Construct validity of the vasopressor dose-REQUIREMENT as a "
             "VASOPLEGIA / vascular-tone index")
    L.append("")
    L.append("**Hostile reviewer's attack.** " + res["attack"])
    L.append("")
    L.append("This document assembles every available piece of evidence on whether the "
             "requirement indexes vascular tone / vasoplegia *specifically* (not just "
             '"some reason to need a pressor"), and reports honestly how strong the '
             "construct is. Phenotype = "
             f"`{res['phenotype']['definition']}`, **n={res['phenotype']['n_cases']}** cases.")
    L.append("")
    L.append("## 1. CONVERGENT validity vs vascular TONE (A-line diastolic carrier)")
    L.append("Vasoplegia = low diastolic tone -> the requirement should correlate "
             "**negatively** with the diastolic-tone carrier.")
    L.append("")
    L.append("**Data-quality flag (verified, load-bearing).** The originally-named tone "
             f"carrier `{TONE_FORM}` is a **DEGENERATE constant** "
             f"(value 0.3333, SD={spr[TONE_FORM]['sd']} across n={spr[TONE_FORM]['n']} "
             "cases) -- it carries NO variance, so any correlation against it is "
             "tie-broken noise. The real diastolic-tone variation lives in "
             f"`{TONE_DOM}` (SD={spr[TONE_DOM]['sd']}, range "
             f"[{spr[TONE_DOM]['min']}, {spr[TONE_DOM]['max']}]). We therefore use "
             f"`{TONE_DOM}` as the primary carrier.")
    L.append("")
    L.append(f"- Requirement vs `{conv['carrier']}` (REAL tone carrier): "
             f"**Spearman {conv['r']}** (95% CI {conv['ci95']}, p={conv['p']}, n={conv['n']}).")
    L.append(f"- For the record, vs degenerate `{conv_ff['carrier']}`: Spearman "
             f"{conv_ff['r']} -- {conv_ff['note']}")
    L.append(f"- Expected direction: {conv['expectation']}.")
    L.append("")
    L.append("## 2. DISCRIMINANT validity vs PRELOAD / hypovolemia (PPV)")
    L.append("High pulse-pressure variation (`art_ppv_burden_min`) marks hypovolemia / "
             "preload-responsiveness -- a **different** mechanism for needing pressor. "
             "If the requirement is vasoplegia-specific it should be **more** related to "
             "low tone than to high PPV.")
    L.append("")
    L.append(f"- Requirement vs `{disc['carrier']}`: Spearman {disc['r']} "
             f"(95% CI {disc['ci95']}, n={disc['n']}).")
    L.append(f"- Head-to-head on the common subset (n={h2h.get('n_common')}): "
             f"r_vs_tone={h2h.get('r_vs_tone')}, r_vs_ppv={h2h.get('r_vs_ppv')}.")
    L.append(f"- Partial Spearman: tone | PPV = {h2h.get('tone_partial_given_ppv')}; "
             f"PPV | tone = {h2h.get('ppv_partial_given_tone')}.")
    L.append(f"- Tone effect larger in magnitude than PPV effect: {h2h.get('tone_dominates')}.")
    L.append("")
    L.append("**Reading.** The preload (PPV) relationship is at least as strong as the "
             "tone relationship, and BOTH survive partialling out the other -- the "
             "requirement is a **mixed preload + tone** vasopressor-need signal, not a "
             "clean vasoplegia index. Note that PPV acts as a *suppressor*: removing it "
             f"strengthens the tone signal from {h2h.get('r_vs_tone')} (raw) to "
             f"{h2h.get('tone_partial_given_ppv')} (partial), which is the only place a "
             "material vasoplegia-direction tone effect appears.")
    L.append("")
    L.append("## 3. SVR anchor (the direct gold standard) -- honest re-report")
    L.append(f"- Requirement vs `{svr['carrier']}`: **Spearman {svr['r']}** "
             f"(95% CI {svr['ci95']}, p={svr['p']}, **n={svr['n']}**).")
    L.append(f"- {svr['honest_note']}")
    L.append(f"- Expected direction: {svr['expectation']}. This is the weakest link.")
    L.append("")
    L.append("## 4. ETIOLOGY by surgery type (vasoplegia-prone vs cleaner cases)")
    L.append(f"- Cases by optype (median requirement, descending):")
    for k, d in et["by_optype"].items():
        L.append(f"  - {k}: n={d['n']}, median={d['median_requirement']}")
    tv = et.get("transplant_vs_rest", {})
    if tv:
        L.append(f"- Transplantation (n={et['n_transplant']}, liver-tx-dominated, "
                 f"vasoplegia-prone) median **{tv.get('median_transplant')}** vs rest "
                 f"**{tv.get('median_rest')}** -> {tv.get('fold_higher')}x, "
                 f"Mann-Whitney one-sided p={tv.get('mannwhitney_p_one_sided_higher')}.")
    lv = et.get("liver_tx_vs_rest", {})
    if lv:
        L.append(f"- Liver transplantation only (n={et['n_liver_transplant']}): median "
                 f"{lv.get('median_liver_tx')} vs rest {lv.get('median_rest')} "
                 f"({lv.get('fold_higher')}x).")
    L.append("")
    L.append("## VERDICT")
    L.append(f"**{v['grade']}** (support score {v['support_score_of_3']}/3).")
    L.append("")
    for b in v["bullets"]:
        L.append(f"- {b}")
    L.append("")
    L.append(v["summary"])
    L.append("")
    L.append("### What a reviewer should STILL doubt")
    L.append("0. **The raw convergent correlation is near-null** (diastolic_over_map "
             f"r={conv['r']}). The vasoplegia-direction tone signal only emerges as a "
             f"*partial* (tone | PPV = {h2h.get('tone_partial_given_ppv')}) once preload "
             "is removed -- i.e. PPV acts as a suppressor. This is real but indirect, and "
             "depends on the partialling model.")
    L.append("1. **Estimator-vs-estimator convergence.** The tone carrier "
             "(`diastolic_over_map`) is itself an arterial-waveform *estimator* of tone, "
             "not a gold-standard SVR. Convergent validity here is two A-line-derived "
             "quantities agreeing -- suggestive, not dispositive.")
    L.append("2. **The gold-standard SVR points the wrong way (n=15, +sign).** Until a "
             "properly powered independent-CO SVR cohort tests the requirement directly, "
             "the vasoplegia label rests on convergent + etiologic evidence, not the anchor.")
    L.append("3. **Discriminant power is N-limited.** PPV separation is estimated on a "
             f"small common subset (n={h2h.get('n_common')}); confounding by mixed "
             "hypovolemia+vasoplegia (common in liver tx) is not fully excluded.")
    L.append("4. **Requirement = management x physiology.** MAP-band + norepi-only "
             "conditioning blunts the 'deep anaesthesia / bradycardia / drug-identity' "
             "confounds the attack names, but observational management is not removed.")
    L.append("")
    L.append("_Generated by analysis/construct_validity.py; numbers in "
             "cache/construct_validity.json._")
    with open(OUT_DOC, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
