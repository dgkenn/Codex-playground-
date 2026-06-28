"""requirement_parsimony.py -- is the stable-epoch DOSE-REQUIREMENT machinery NECESSARY?

Two honest stress-tests of the stable-epoch norepinephrine dose-requirement
phenotype (docs/PRESSOR_REQUIREMENT.md, analysis/pressor_requirement.py):

A. IS THE MACHINERY NECESSARY?  The requirement phenotype is the median norepi
   dose/kg over STABLE constant-infusion epochs with MAP in the [55,80] target
   band -- a deliberately conditioned, multi-step construct. If a SIMPLER pressor
   metric computed off the same epochs (peak dose, total exposure, time-weighted
   mean, fraction-on-pressor) matches it on reliability / spread / construct
   validity / early->late prediction, then the stable-epoch + MAP-band machinery
   buys nothing and we should say so. We compare the phenotype against four
   simpler alternatives on:
     (a) split-half reliability (odd/even epochs, Spearman),
     (b) between-patient spread (p90/p10 fold-range),
     (c) construct validity vs EV1000 svr_mean (expect NEGATIVE: low tone = high need),
     (d) early->late prediction (split each case's epochs by TIME, correlate the
         early-half summary with the late-half summary across patients).

B. NOREPI-EQUIVALENTS to expand N.  Only ~52 cases reach the norepi-only phenotype.
   PHEN (phenylephrine) and DOPA (dopamine) epochs are discarded. Converting them to
   norepinephrine-equivalents (NEE) using published potency ratios lets us pool a
   multi-drug cohort and re-derive the requirement. We then ask whether reliability,
   spread, and early->late HOLD on the expanded cohort and at what larger N.

   *** CONCENTRATION CAVEAT (read this) ***
   Orchestra RATE is a DEVICE rate (mL/h), not ug/kg/min -- VitalDB does not expose
   per-case drug concentration. The norepi phenotype is only valid between patients
   under a "standard institutional concentration" assumption (stated in the parent
   doc). Norepi-EQUIVALENT conversion STACKS a SECOND assumption on top: it assumes a
   standard mL/h->ug/kg/min mapping for EACH drug AND a fixed potency ratio between
   drugs. The potency ratios used are approximate, Goradia-style institutional
   norepinephrine-equivalent conversions (Goradia 2021 Crit Care Resusc review;
   Brown 2012). Treat expanded-cohort numbers as HYPOTHESIS-GENERATING only.

stdlib only at import; numpy/pandas/scipy lazy.
Run: python3 -m vitaldb_aki.analysis.requirement_parsimony
Writes: cache/requirement_parsimony.json + docs/REQUIREMENT_PARSIMONY.md
"""
from __future__ import annotations
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
OUT_JSON = os.path.join(_CACHE, "requirement_parsimony.json")
OUT_DOC = os.path.join(_DOCS, "REQUIREMENT_PARSIMONY.md")

TARGET_LO, TARGET_HI = 55.0, 80.0
MAP_MIN, MAP_MAX = 20.0, 200.0
MIN_EPOCHS_PER_CASE = 2          # for the phenotype median
MIN_EPOCHS_SPLITHALF = 4         # need >=4 epochs to split odd/even
PRIMARY_DRUG = "NEPI"

# ------------------------------------------------------------------ NEE ratios
# Norepinephrine-equivalent (NEE) potency multipliers, applied to a per-kg
# device-rate ASSUMED already in ug/kg/min-comparable units (see caveat).
# Goradia 2021 / Brown 2012 institutional convention:
#   norepinephrine 1 ug/kg/min            == 1.0  NEE   (reference)
#   phenylephrine  ~ 1/10 of norepi       == 0.1  NEE   (per vasopressor-unit)
#   dopamine: norepi-equiv = dopa(ug/kg/min)/100  == 0.01 NEE
# These are APPROXIMATE. Stated, not measured. See the caveat block above.
NEE_RATIO = {"NEPI": 1.0, "PHEN": 0.1, "DOPA": 0.01, "VASO": None}  # VASO excluded (unit not dose-comparable)


# --------------------------------------------------------------------- loaders
def _load_epochs():
    import pandas as pd
    df = pd.read_csv(EPOCHS_CSV, low_memory=False)
    for c in df.columns:
        if c not in ("caseid", "drug", "sex", "optype"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    return df


# --------------------------------------------------------------- metric builders
def _per_case_metrics(g):
    """All candidate per-case summaries from one case's qualifying epochs.

    g is a DataFrame of one case's NEPI norepi-only epochs with a valid dose_per_kg.
    Target-band rows are used for the phenotype; the simpler metrics use ALL the
    case's norepi-only epochs (peak/total/twm/fraction don't condition on MAP band,
    which is the point -- they're the 'cheap' alternatives).
    """
    import numpy as np
    out = {}
    tb = g[g["map_mean"].between(TARGET_LO, TARGET_HI)]
    # PHENOTYPE: median dose in target band (the expensive construct)
    out["phenotype"] = float(np.median(tb["dose_per_kg"])) if len(tb) >= MIN_EPOCHS_PER_CASE else None
    # SIMPLER ALTERNATIVES over ALL norepi-only epochs (no MAP-band conditioning)
    d = g["dose_per_kg"].to_numpy(float)
    dur = g["dur"].to_numpy(float)
    out["peak"] = float(np.max(d)) if len(d) else None
    out["total"] = float(np.sum(d * dur)) if len(d) else None        # exposure = sum(rate/kg * dur)
    out["twm"] = float(np.sum(d * dur) / np.sum(dur)) if dur.sum() > 0 else None  # time-weighted mean
    return out


def _splithalf(case_epoch_lists, summ):
    """Odd/even split-half reliability of a per-case summary function `summ`
    (takes a list of (dose,dur,map,t) tuples -> scalar). Spearman across cases
    with >= MIN_EPOCHS_SPLITHALF epochs."""
    import numpy as np
    from scipy import stats
    odd, even = [], []
    for cid, ep in case_epoch_lists.items():
        if len(ep) < MIN_EPOCHS_SPLITHALF:
            continue
        o = summ(ep[0::2]); e = summ(ep[1::2])
        if o is not None and e is not None and np.isfinite(o) and np.isfinite(e):
            odd.append(o); even.append(e)
    if len(odd) < 5:
        return {"n": len(odd), "splithalf_spearman": None}
    r = float(stats.spearmanr(odd, even)[0])
    return {"n": len(odd), "splithalf_spearman": round(r, 3)}


def _early_late(case_epoch_lists, summ):
    """Early->late prediction: split each case's epochs by TIME (t_start) into the
    first half (early) and second half (late); correlate early-summary vs
    late-summary ACROSS patients. Tests whether the metric is a stable trait that
    early measurement predicts later (the property a pre-epoch model would exploit)."""
    import numpy as np
    from scipy import stats
    early, late = [], []
    for cid, ep in case_epoch_lists.items():
        if len(ep) < MIN_EPOCHS_SPLITHALF:
            continue
        ep_sorted = sorted(ep, key=lambda x: x[3])   # x[3] = t_start
        h = len(ep_sorted) // 2
        e_s = summ(ep_sorted[:h]); l_s = summ(ep_sorted[h:])
        if e_s is not None and l_s is not None and np.isfinite(e_s) and np.isfinite(l_s):
            early.append(e_s); late.append(l_s)
    if len(early) < 5:
        return {"n": len(early), "early_late_spearman": None}
    r = float(stats.spearmanr(early, late)[0])
    return {"n": len(early), "early_late_spearman": round(r, 3)}


def _spread(vals):
    import numpy as np
    v = np.array([x for x in vals if x is not None and np.isfinite(x)], float)
    vp = v[v > 0]
    if vp.size < 8:
        return {"n": int(v.size), "fold_range_p90_p10": None}
    p10, p90 = np.percentile(vp, 10), np.percentile(vp, 90)
    return {"n": int(v.size),
            "median": round(float(np.median(v)), 5),
            "p10_p90": [round(float(p10), 5), round(float(p90), 5)],
            "fold_range_p90_p10": round(float(p90 / p10), 2) if p10 > 0 else None}


def _construct_vs_svr(per_case_metric, per_case_svr):
    """Spearman of a per-case metric vs per-case mean EV1000 SVR. Expect NEGATIVE
    for a real vasoplegia requirement (low tone -> high requirement)."""
    import numpy as np
    from scipy import stats
    cids = [c for c in per_case_metric if c in per_case_svr
            and per_case_metric[c] is not None and np.isfinite(per_case_metric[c])]
    if len(cids) < 6:
        return {"n_overlap": len(cids), "spearman": None}
    x = [per_case_metric[c] for c in cids]
    y = [per_case_svr[c] for c in cids]
    return {"n_overlap": len(cids), "spearman": round(float(stats.spearmanr(x, y)[0]), 3)}


# ---- summary functions on epoch-tuple lists (dose, dur, map, t_start) ----
def _summ_phenotype(ep):
    import numpy as np
    tb = [d for (d, du, m, t) in ep if TARGET_LO <= m <= TARGET_HI]
    return float(np.median(tb)) if len(tb) >= 1 else None

def _summ_peak(ep):
    return max((d for (d, du, m, t) in ep), default=None) if ep else None

def _summ_total(ep):
    return sum(d * du for (d, du, m, t) in ep) if ep else None

def _summ_twm(ep):
    sd = sum(du for (d, du, m, t) in ep)
    return (sum(d * du for (d, du, m, t) in ep) / sd) if sd > 0 else None


# ===================================================================== PART A
def part_a(df):
    """Phenotype vs simpler metrics. Norepi-only NEPI epochs with valid dose."""
    import numpy as np
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["norepi_only"] == 1) &
           (df["map_mean"].between(MAP_MIN, MAP_MAX)) & df["dose_per_kg"].notna()].copy()

    # epoch-tuple lists per case (ordered by time for early/late)
    case_ep = {}
    for cid, g in q.groupby("caseid"):
        gg = g.sort_values("t_start")
        case_ep[cid] = list(zip(gg["dose_per_kg"].astype(float),
                                gg["dur"].astype(float),
                                gg["map_mean"].astype(float),
                                gg["t_start"].astype(float)))

    # per-case point estimates (full data) for spread + construct
    pc = {"phenotype": {}, "peak": {}, "total": {}, "twm": {}, "fraction_on": {}}
    for cid, g in q.groupby("caseid"):
        m = _per_case_metrics(g)
        for k in ("phenotype", "peak", "total", "twm"):
            pc[k][cid] = m[k]

    # fraction-of-time on pressor: needs total case anaesthesia time as denominator.
    # We approximate "fraction of stable-epoch time spent on norepi at target band"
    # as target-band epoch duration / total norepi-only epoch duration (a pure
    # composition metric, no external denominator needed).
    for cid, g in q.groupby("caseid"):
        tot_dur = float(g["dur"].sum())
        tb_dur = float(g[g["map_mean"].between(TARGET_LO, TARGET_HI)]["dur"].sum())
        pc["fraction_on"][cid] = (tb_dur / tot_dur) if tot_dur > 0 else None

    # per-case SVR (mean over the case's epochs)
    svr = {}
    for cid, g in df[df["drug"] == PRIMARY_DRUG].groupby("caseid"):
        s = g["svr_mean"].dropna()
        if len(s):
            svr[cid] = float(s.mean())

    summ_fns = {"phenotype": _summ_phenotype, "peak": _summ_peak,
                "total": _summ_total, "twm": _summ_twm}

    metrics = {}
    for name in ("phenotype", "peak", "total", "twm", "fraction_on"):
        entry = {}
        # spread
        # phenotype point estimate requires >=2 target-band epochs; keep only those
        if name == "phenotype":
            vals = [v for v in pc[name].values() if v is not None]
        else:
            vals = list(pc[name].values())
        entry["spread"] = _spread(vals)
        # reliability + early/late (only for metrics with an epoch summary fn)
        if name in summ_fns:
            entry["reliability"] = _splithalf(case_ep, summ_fns[name])
            entry["early_late"] = _early_late(case_ep, summ_fns[name])
        else:
            entry["reliability"] = {"note": "fraction-on-pressor is a composition metric; "
                                            "split-half not meaningful per-epoch"}
            entry["early_late"] = {"note": "n/a"}
        # construct vs SVR
        entry["construct_vs_SVR"] = _construct_vs_svr(pc[name], svr)
        metrics[name] = entry

    # phenotype-vs-alternative correlation (do the simpler metrics just reproduce it?)
    from scipy import stats
    corr = {}
    ph = pc["phenotype"]
    for name in ("peak", "total", "twm", "fraction_on"):
        cids = [c for c in ph if c in pc[name] and ph[c] is not None
                and pc[name][c] is not None and np.isfinite(ph[c]) and np.isfinite(pc[name][c])]
        if len(cids) >= 8:
            r = float(stats.spearmanr([ph[c] for c in cids], [pc[name][c] for c in cids])[0])
            corr[name] = {"n": len(cids), "spearman_vs_phenotype": round(r, 3)}
        else:
            corr[name] = {"n": len(cids), "spearman_vs_phenotype": None}

    return {"n_norepi_only_epochs": int(len(q)),
            "n_cases": int(q["caseid"].nunique()),
            "n_cases_with_phenotype": int(sum(1 for v in ph.values() if v is not None)),
            "metrics": metrics,
            "alt_vs_phenotype_correlation": corr}, pc


def _verdict_a(a):
    """Decide whether the machinery is necessary based on the comparison."""
    M = a["metrics"]
    ph = M["phenotype"]
    ph_rel = ph["reliability"].get("splithalf_spearman")
    ph_spread = ph["spread"].get("fold_range_p90_p10")
    ph_svr = ph["construct_vs_SVR"].get("spearman")
    ph_el = ph["early_late"].get("early_late_spearman")

    # find the best simpler alternative on each axis
    alts = {k: v for k, v in M.items() if k != "phenotype"}
    best_rel = max((v["reliability"].get("splithalf_spearman") or -2
                    for v in alts.values()))
    best_el = max((v["early_late"].get("early_late_spearman") or -2
                   for v in alts.values()))
    # construct: we want the most NEGATIVE (strongest vasoplegia signal)
    svr_vals = [v["construct_vs_SVR"].get("spearman") for v in alts.values()
                if v["construct_vs_SVR"].get("spearman") is not None]
    best_svr_neg = min(svr_vals) if svr_vals else None

    # is any alternative ALSO highly correlated with the phenotype (a proxy)?
    proxies = [k for k, v in a["alt_vs_phenotype_correlation"].items()
               if (v.get("spearman_vs_phenotype") or 0) >= 0.85]

    reasons = []
    machinery_needed = False
    # the phenotype earns its keep if it's better on construct OR reliability,
    # AND no simpler metric is both a near-perfect proxy and equally reliable.
    if ph_svr is not None and ph_svr < 0 and (best_svr_neg is None or ph_svr <= best_svr_neg + 1e-9):
        reasons.append(f"phenotype has the strongest (most negative) SVR construct link "
                       f"({ph_svr} vs best simpler {best_svr_neg})")
        machinery_needed = True
    if ph_rel is not None and (best_rel is None or ph_rel >= best_rel - 0.05):
        reasons.append(f"phenotype reliability {ph_rel} is at/above the best simpler metric ({best_rel})")
    if best_rel is not None and ph_rel is not None and best_rel > ph_rel + 0.05:
        reasons.append(f"a SIMPLER metric is MORE reliable ({best_rel} > {ph_rel}) -- machinery NOT clearly needed on reliability")
    if proxies and not machinery_needed:
        reasons.append(f"simpler metric(s) {proxies} reproduce the phenotype (rho>=0.85) AND it has no construct edge -- machinery NOT necessary")
    return {"machinery_needed": bool(machinery_needed),
            "phenotype": {"reliability": ph_rel, "spread_fold": ph_spread,
                          "construct_vs_SVR": ph_svr, "early_late": ph_el},
            "best_simpler": {"reliability": best_rel if best_rel > -2 else None,
                             "early_late": best_el if best_el > -2 else None,
                             "construct_vs_SVR_most_neg": best_svr_neg},
            "near_perfect_proxies_rho_ge_0.85": proxies,
            "reasons": reasons}


# ===================================================================== PART B
def part_b(df):
    """Norepi-equivalent expansion. Pool NEPI+PHEN+DOPA single-agent epochs,
    convert dose_per_kg to NEE, re-derive the requirement phenotype."""
    import numpy as np
    from scipy import stats

    keep = df[df["drug"].isin(["NEPI", "PHEN", "DOPA"]) &
              (df["norepi_only"] == 1) & df["dose_per_kg"].notna() &
              (df["map_mean"].between(MAP_MIN, MAP_MAX))].copy()
    keep["nee_ratio"] = keep["drug"].map(NEE_RATIO)
    keep = keep[keep["nee_ratio"].notna()].copy()
    keep["nee_dose"] = keep["dose_per_kg"].astype(float) * keep["nee_ratio"].astype(float)

    def _derive(sub, label):
        case_ep = {}
        for cid, g in sub.groupby("caseid"):
            gg = g.sort_values("t_start")
            case_ep[cid] = list(zip(gg["nee_dose"].astype(float),
                                    gg["dur"].astype(float),
                                    gg["map_mean"].astype(float),
                                    gg["t_start"].astype(float)))
        # phenotype = median NEE dose over target-band epochs
        pheno = {}
        for cid, g in sub.groupby("caseid"):
            tb = g[g["map_mean"].between(TARGET_LO, TARGET_HI)]
            if len(tb) >= MIN_EPOCHS_PER_CASE:
                pheno[cid] = float(np.median(tb["nee_dose"]))
        rel = _splithalf(case_ep, _summ_phenotype)
        el = _early_late(case_ep, _summ_phenotype)
        spread = _spread(list(pheno.values()))
        # drug composition of the phenotype cohort
        comp = {}
        for cid in pheno:
            ds = sorted(sub[sub["caseid"] == cid]["drug"].unique())
            comp[",".join(ds)] = comp.get(",".join(ds), 0) + 1
        return {"label": label,
                "n_epochs": int(len(sub)),
                "n_cases_with_phenotype": len(pheno),
                "drug_composition_of_phenotype_cases": comp,
                "spread": spread, "reliability": rel, "early_late": el}

    # baseline (NEPI only) for an apples-to-apples comparison using the SAME code path
    nepi_only = keep[keep["drug"] == "NEPI"]
    res = {
        "nee_ratios_used": {k: v for k, v in NEE_RATIO.items() if v is not None},
        "baseline_NEPI_only": _derive(nepi_only, "NEPI-only (NEE=identity)"),
        "expanded_NEPI_PHEN_DOPA": _derive(keep, "NEPI+PHEN+DOPA norepi-equivalent"),
    }
    base = res["baseline_NEPI_only"]
    exp = res["expanded_NEPI_PHEN_DOPA"]
    holds = (
        (exp["reliability"].get("splithalf_spearman") is not None) and
        (exp["reliability"]["splithalf_spearman"] >= 0.4) and
        (exp["spread"].get("fold_range_p90_p10") or 0) >= 3 and
        (exp["early_late"].get("early_late_spearman") or 0) >= 0.3
    )
    res["expansion_holds"] = bool(holds)
    res["n_gain"] = exp["n_cases_with_phenotype"] - base["n_cases_with_phenotype"]
    return res


# ===================================================================== driver
def run():
    df = _load_epochs()
    a, _pc = part_a(df)
    a["verdict"] = _verdict_a(a)
    b = part_b(df)

    machinery = a["verdict"]["machinery_needed"]
    expand = b["expansion_holds"]
    overall = (
        ("MACHINERY JUSTIFIED" if machinery else "MACHINERY NOT CLEARLY NECESSARY")
        + "; EXPANSION " + ("HOLDS (assumption-laden -- see caveat)" if expand else "DOES NOT cleanly hold")
    )
    res = {"seed": SEED, "part_a_necessity": a, "part_b_norepi_equivalents": b,
           "overall_verdict": overall}
    os.makedirs(_CACHE, exist_ok=True)
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    return res


def _fmt(x):
    return "n/a" if x is None else x


def _doc(res):
    a = res["part_a_necessity"]; b = res["part_b_norepi_equivalents"]
    M = a["metrics"]; va = a["verdict"]
    L = []
    L.append("# Is the stable-epoch dose-REQUIREMENT machinery NECESSARY? (parsimony + expansion)\n")
    L.append("Two stress-tests of the stable-epoch norepinephrine dose-requirement phenotype "
             "(docs/PRESSOR_REQUIREMENT.md). **A:** does a SIMPLER pressor metric off the same "
             "epochs match it? **B:** can norepinephrine-equivalents expand N beyond the "
             "norepi-only cohort?\n")
    L.append(f"**OVERALL VERDICT: {res['overall_verdict']}**\n")

    L.append("## A. Necessity -- phenotype vs simpler metrics")
    L.append(f"- Norepi-only NEPI epochs: **{a['n_norepi_only_epochs']}** over "
             f"**{a['n_cases']}** cases; cases with the target-band phenotype: "
             f"**{a['n_cases_with_phenotype']}**.\n")
    L.append("| metric | split-half reliability (n) | spread p90/p10 (n) | construct vs EV1000 SVR rho (n) | early->late rho (n) |")
    L.append("|---|---|---|---|---|")
    order = ["phenotype", "peak", "total", "twm", "fraction_on"]
    label = {"phenotype": "**stable-epoch REQUIREMENT (median target-band dose/kg)**",
             "peak": "peak dose/kg", "total": "total exposure sum(dose*dur)",
             "twm": "time-weighted mean dose/kg", "fraction_on": "fraction target-band time"}
    for k in order:
        m = M[k]
        rel = m["reliability"]; sp = m["spread"]; cv = m["construct_vs_SVR"]; el = m["early_late"]
        rel_s = f"{_fmt(rel.get('splithalf_spearman'))} ({rel.get('n','-')})" if "splithalf_spearman" in rel else "n/a"
        sp_s = f"{_fmt(sp.get('fold_range_p90_p10'))} ({sp.get('n','-')})"
        cv_s = f"{_fmt(cv.get('spearman'))} ({cv.get('n_overlap','-')})"
        el_s = f"{_fmt(el.get('early_late_spearman'))} ({el.get('n','-')})" if "early_late_spearman" in el else "n/a"
        L.append(f"| {label[k]} | {rel_s} | {sp_s} | {cv_s} | {el_s} |")
    L.append("")
    L.append("Construct sign: a real vasoplegia REQUIREMENT should correlate **NEGATIVELY** "
             "with EV1000 SVR (low systemic tone -> needs more pressor).\n")
    L.append("**How much do the simpler metrics just reproduce the phenotype?** (Spearman vs phenotype)")
    for k, v in a["alt_vs_phenotype_correlation"].items():
        L.append(f"- {label[k]}: rho = {_fmt(v.get('spearman_vs_phenotype'))} (n={v.get('n')})")
    L.append("")
    L.append("### Verdict A")
    L.append(f"- **Machinery needed: {va['machinery_needed']}**")
    L.append(f"- phenotype: reliability {va['phenotype']['reliability']}, spread {va['phenotype']['spread_fold']}x, "
             f"construct vs SVR {va['phenotype']['construct_vs_SVR']}, early->late {va['phenotype']['early_late']}")
    L.append(f"- best simpler metric: reliability {va['best_simpler']['reliability']}, "
             f"early->late {va['best_simpler']['early_late']}, most-negative construct {va['best_simpler']['construct_vs_SVR_most_neg']}")
    if va["near_perfect_proxies_rho_ge_0.85"]:
        L.append(f"- near-perfect proxies (rho>=0.85): {va['near_perfect_proxies_rho_ge_0.85']}")
    for r in va["reasons"]:
        L.append(f"- {r}")
    L.append("")

    L.append("## B. Norepinephrine-equivalents to expand N")
    L.append("> **CONCENTRATION CAVEAT (prominent):** Orchestra RATE is a DEVICE rate (mL/h), "
             "not ug/kg/min -- VitalDB does not expose per-case concentration. The norepi "
             "phenotype already assumes a standard institutional norepi concentration *between "
             "patients*. NEE conversion STACKS a second assumption: a standard mL/h->dose mapping "
             "for EACH drug AND a fixed cross-drug potency ratio. Ratios used are approximate, "
             "Goradia/Brown-style institutional norepinephrine-equivalents. **Expanded-cohort "
             "numbers are HYPOTHESIS-GENERATING ONLY.**\n")
    L.append(f"NEE ratios used (norepi-equivalent per device-dose/kg): {b['nee_ratios_used']}. "
             "phenylephrine ~1/10 norepi; dopamine norepi-equiv = dopa/100; VASO excluded "
             "(vasopressin units are not dose-comparable).\n")
    L.append("| cohort | N (phenotype cases) | epochs | spread p90/p10 | split-half reliability | early->late rho |")
    L.append("|---|---|---|---|---|---|")
    for key in ("baseline_NEPI_only", "expanded_NEPI_PHEN_DOPA"):
        d = b[key]
        L.append(f"| {d['label']} | {d['n_cases_with_phenotype']} | {d['n_epochs']} | "
                 f"{_fmt(d['spread'].get('fold_range_p90_p10'))} | "
                 f"{_fmt(d['reliability'].get('splithalf_spearman'))} (n={d['reliability'].get('n')}) | "
                 f"{_fmt(d['early_late'].get('early_late_spearman'))} (n={d['early_late'].get('n')}) |")
    L.append("")
    L.append(f"- Phenotype-case N gain from expansion: **+{b['n_gain']}** "
             f"({b['baseline_NEPI_only']['n_cases_with_phenotype']} -> "
             f"{b['expanded_NEPI_PHEN_DOPA']['n_cases_with_phenotype']}).")
    L.append(f"- Drug composition of expanded phenotype cases: "
             f"{b['expanded_NEPI_PHEN_DOPA']['drug_composition_of_phenotype_cases']}")
    L.append(f"- **Expansion holds (reliability>=0.4, spread>=3x, early->late>=0.3): "
             f"{b['expansion_holds']}**")
    if b["expansion_holds"]:
        bspread = b["baseline_NEPI_only"]["spread"].get("fold_range_p90_p10")
        espread = b["expanded_NEPI_PHEN_DOPA"]["spread"].get("fold_range_p90_p10")
        L.append("- Reliability/spread/early->late SURVIVE the NEE pooling at the larger N -- but "
                 "this could partly reflect the (assumption-laden) conversion creating apparent "
                 "between-patient spread. Do NOT report expanded numbers as confirmatory.")
        if espread and bspread and espread > 3 * bspread:
            L.append(f"- **RED FLAG:** the expanded spread ({espread}x) is far larger than the "
                     f"norepi-only spread ({bspread}x). The 10x/100x cross-drug NEE ratios place "
                     "PHEN- and DOPA-dominant patients in fixed lower bands BY CONSTRUCTION, so "
                     "much of the inflated spread (and the higher split-half/early-late) is DRUG "
                     "IDENTITY masquerading as a requirement trait, not new physiologic signal. "
                     "The expanded N is real; the apparent improvement is largely an artefact of "
                     "the conversion. Trust the norepi-only cohort for effect sizes.")
    else:
        L.append("- Pooling did NOT cleanly preserve the phenotype's properties -- the NEE "
                 "conversion is too assumption-laden to trust here; stay with the norepi-only cohort.")
    L.append("")
    open(OUT_DOC, "w").write("\n".join(L) + "\n")


def main():
    res = run()
    print("\n[parsimony] OVERALL: " + res["overall_verdict"])
    print("[parsimony] Part A machinery_needed:", res["part_a_necessity"]["verdict"]["machinery_needed"])
    print("[parsimony] Part B expansion_holds:", res["part_b_norepi_equivalents"]["expansion_holds"],
          "| N", res["part_b_norepi_equivalents"]["baseline_NEPI_only"]["n_cases_with_phenotype"],
          "->", res["part_b_norepi_equivalents"]["expanded_NEPI_PHEN_DOPA"]["n_cases_with_phenotype"])
    print("[parsimony] ->", OUT_DOC)


if __name__ == "__main__":
    main()
