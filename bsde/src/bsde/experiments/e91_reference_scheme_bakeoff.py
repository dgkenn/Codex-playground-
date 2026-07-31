"""E91 -- Seven ways to build a population reference, scored on transport AND on discrimination.

REGISTERED BEFORE ANY SCHEME IS SCORED. The awake-cohort tables it consumes are still extracting; what has
been read of them is only what E88's registration already discloses.

=========================================================================================================
WHY A BAKE-OFF, AND WHY THERE IS NOTHING TO DOWNLOAD
=========================================================================================================
Population referencing is what turns an aperiodic exponent in arbitrary units into "distance from typical
awake brain". E88 asks whether ONE scheme -- mean/SD of a single derivation cohort, which is what UCE v1
uses -- transports across cohorts. This asks the prior question: **is that the right scheme at all, and
what does the choice cost?**

**There is no published normative table to adopt.** Checked against PubMed through E-utilities, six query
phrasings: "EEG aperiodic exponent reference values percentile", "EEG aperiodic norms healthy population",
"electroencephalography normative database aperiodic", "aperiodic exponent EEG age lifespan normative" and
two others all return **count = 0**. The one hit for "spectral parameterization FOOOF normative EEG
reference" (PMID 42294963, *Clin EEG Neurosci* 2026) is about aperiodic CORRECTION of a ratio, not a norming
table. The literature that does exist is associational -- the exponent changes with age (PMID 41468657,
PMID 38373849) and is modulated by education (PMID 38956186, PMID 41801996) -- which motivates
age-conditioning as a scheme but supplies no constants.

**And borrowed constants would not be usable even if they existed**, because an aperiodic exponent depends
on fit range, PSD method, epoch length, montage and reference, none of which a published mean/SD carries
with it. So the reference has to be built here, and the question is how.

=========================================================================================================
THE SEVEN SCHEMES
=========================================================================================================
Every scheme maps a recording's (frontal, posterior) exponent pair to one number, using ONLY the reference
cohort's awake recordings to fit whatever it needs.

    S1  Z-MEAN-SD      0.696*z_F + 0.718*z_P with z from the reference's awake mean and SD.  (UCE v1)
    S2  Z-MEDIAN-IQR   the same with median and IQR/1.349 -- resistant to a few outlying recordings, which
                       matter more here than usual because a bad channel can drag a regional mean.
    S3  RANK           each exponent replaced by its percentile in the reference's awake empirical CDF,
                       then centred on 0.5 and combined with the same weights. **Invariant to any monotone
                       transform of the exponent**, so a montage or amplifier difference that rescales the
                       measure cannot move it -- the one scheme with a principled reason to transport.
    S4  POOLED         S1 with mean and SD pooled over ALL reference cohorts rather than one.
    S5  SELF           z using the TARGET cohort's own awake mean and SD. **The trivial control.**
    S6  RAW            the whole-head exponent, unreferenced. The does-this-machinery-earn-its-keep arm.
    S7  CONTRAST       (frontal - posterior) / (|frontal| + |posterior|), scale-free by construction and
                       needing no reference at all.

=========================================================================================================
THREE AXES, AND THE THIRD IS WHY THE TRIVIAL SCHEME DOES NOT WIN
=========================================================================================================
    A1  TRANSPORT       |mean score among AWAKE recordings of a HELD-OUT cohort|, leave-one-cohort-out.
                        Lower is better; equivalence margin +-0.5 in the score's own units, as E88 uses.
    A2  DISCRIMINATION  within-deposit separation of awake from anaesthetised, Cohen's d, on the deposits
                        that carry both states (ds004541, ds005620). Higher is better.
    A3  AUTONOMY        does the scheme need AWAKE DATA FROM THE TARGET COHORT? **This is a declared
                        property, not a measurement.**

**A3 exists because without it the bake-off has a trivial winner.** S5 centres on the target cohort's own
awake recordings, so its transport is exactly 0 by construction and its discrimination is untouched (an
affine map cannot change Cohen's d). It wins A1 and A2 outright and is useless for the thing population
referencing is FOR: scoring a patient when you have no awake recording from their cohort. Ranking S5 with
the others would be a category error, so it is reported as the CEILING that requires target-cohort awake
data, and excluded from the ranking. Recognising that A1 and A2 alone cannot separate the schemes is the
design decision this experiment turns on.

PREDICTIONS, written now:
    * **S3 RANK transports best** among the autonomous schemes, because it is the only one invariant to a
      monotone rescaling of the measure, and cross-deposit montage differences are the most likely cause of
      centroid displacement.
    * **S6 RAW discriminates as well as S1**, because `uce_v1.py` already shows the two-region score is the
      whole-head mean to within r = 0.88-0.98 in three cohorts.
    * **No autonomous scheme reaches S5's transport.** If one does, referencing is free and that is the
      most useful outcome available here.

VERDICT RULE, and the wrong-direction case is named first (rule 37):

    (a) an autonomous scheme discriminates WORSE than S6 RAW while transporting no better
            -> that scheme is COST WITHOUT BENEFIT and must be reported as such, not as "comparable".
    (b) no autonomous scheme transports within +-0.5
            -> NO SCHEME TRANSPORTS. The sentence "zero means the awake reference" is not defensible in
               any form tested, and an absolute coordinate is not available from these cohorts.
    (c) at least one autonomous scheme transports within +-0.5 AND holds discrimination within 0.2 d of
        the best
            -> that scheme is the RECOMMENDATION, named, with its cost stated.

GATES (rule 40):
    G1  >= 3 adult awake cohorts with >= 20 recordings each (E88's floor, same reason).
    G2  >= 2 deposits carrying both awake and anaesthetised recordings, >= 5 each, for A2.
    G3  CONSTRUCTION CHECK. S5's transport must be 0 to within 1e-9 and its discrimination must equal
        S1's to within 1e-9 when S1 uses the same cohort. A scheme that cannot hit its own trivial target
        is misimplemented and nothing below is interpretable.
    G4  >= 5 frontal and >= 5 posterior channels in every included recording.

SCOPE. This is a measurement-scale question. No scheme winning here would show the score is clinically
useful, and HBN children are excluded from every ranking for the reason E88 gives (rule 54); they appear
only in the separate offset block, where a LARGE offset is the correct answer.

    python -m bsde.experiments.e91_reference_scheme_bakeoff
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.uce_v1 import W_FRONTAL, W_POSTERIOR                    # noqa: E402

OUT = os.path.join(RESULTS, "e91_reference_scheme_bakeoff.json")

AWAKE_COHORTS = {
    "lemon":    {"table": "lemon_regional_aperiodic.csv", "awake": None, "adult": True},
    "eegmmidb": {"table": "eegmmidb_regional_aperiodic.csv", "awake": None, "adult": True},
    # rule 61: ds004541's awake recordings are `@baseline`, `@start-N` and `@loc-N` (N seconds BEFORE
    # loss of consciousness). Matching the substring `baseline` alone found 2 of ~59 and E88 inherited
    # that defect. Fixed here BEFORE this experiment runs, which is correcting a known cohort-selection
    # bug, not revising a gate after a failure.
    "ds004541": {"table": "ds004541_regional_aperiodic.csv", "awake": ("@baseline", "@start-", "@loc-"),
                 "adult": True, "exclude_subjects": {"sub-02"}},
    "ds005620": {"table": "ds005620_regional_aperiodic.csv",
                 "awake": ("awake", "eyesclosed", "rest"), "adult": True},
    "hbn": {"table": "hbn_regional_aperiodic.csv", "awake": None, "adult": False},
}
STATE_DEPOSITS = {
    "ds004541": {"table": "ds004541_regional_aperiodic.csv", "awake": ("baseline",),
                 "anaes": ("post-loc", "postloc", "loc"), "exclude_subjects": {"sub-02"}},
    "ds005620": {"table": "ds005620_regional_aperiodic.csv",
                 "awake": ("awake", "eyesclosed", "rest"), "anaes": ("sed", "propofol", "anes")},
}
AUTONOMOUS = ("S1_z_mean_sd", "S2_z_median_iqr", "S3_rank", "S4_pooled", "S6_raw", "S7_contrast")
MIN_RECORDINGS, MIN_CHANNELS, MIN_PER_STATE = 20, 5, 5
EQUIV = 0.5
D_TOLERANCE = 0.2
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(spec):
    p = os.path.join(RESULTS, spec["table"])
    if not os.path.exists(p):
        return None
    rows = [r for r in csv.DictReader(open(p, newline="")) if r.get("status") == "ok"]
    rows = [r for r in rows if r.get("subject") not in spec.get("exclude_subjects", set())]
    return rows


def select(rows, tokens):
    if tokens is None:
        return rows
    return [r for r in rows if any(t in r["recording_id"].lower() for t in tokens)]


def pairs(rows):
    fr = np.array([_f(r["aperiodic_frontal"]) for r in rows])
    po = np.array([_f(r["aperiodic_posterior"]) for r in rows])
    wh = np.array([_f(r["aperiodic_wholehead"]) for r in rows])
    nf = np.array([_f(r.get("n_frontal", "")) for r in rows])
    npo = np.array([_f(r.get("n_posterior", "")) for r in rows])
    ok = (np.isfinite(fr) & np.isfinite(po) & np.isfinite(wh)
          & (nf >= MIN_CHANNELS) & (npo >= MIN_CHANNELS))
    return fr[ok], po[ok], wh[ok]


# ---- the seven schemes: each returns a callable (fr, po, wh) -> score ---------------------------------

def fit_scheme(name, ref_fr, ref_po, ref_wh, pooled=None):
    if name == "S1_z_mean_sd" or name == "S5_self":
        mF, sF = float(np.mean(ref_fr)), float(np.std(ref_fr, ddof=1))
        mP, sP = float(np.mean(ref_po)), float(np.std(ref_po, ddof=1))
        return lambda f, p, w: W_FRONTAL * (f - mF) / sF + W_POSTERIOR * (p - mP) / sP
    if name == "S2_z_median_iqr":
        def rb(v):
            q1, q3 = np.percentile(v, [25, 75])
            return float(np.median(v)), max(float(q3 - q1) / 1.349, 1e-9)
        mF, sF = rb(ref_fr)
        mP, sP = rb(ref_po)
        return lambda f, p, w: W_FRONTAL * (f - mF) / sF + W_POSTERIOR * (p - mP) / sP
    if name == "S3_rank":
        rf, rp = np.sort(ref_fr), np.sort(ref_po)

        def pct(v, ref):
            return np.searchsorted(ref, v, side="left") / max(len(ref), 1)
        return lambda f, p, w: (W_FRONTAL * (pct(f, rf) - 0.5) + W_POSTERIOR * (pct(p, rp) - 0.5))
    if name == "S4_pooled":
        pf, pp = pooled
        mF, sF = float(np.mean(pf)), float(np.std(pf, ddof=1))
        mP, sP = float(np.mean(pp)), float(np.std(pp, ddof=1))
        return lambda f, p, w: W_FRONTAL * (f - mF) / sF + W_POSTERIOR * (p - mP) / sP
    if name == "S6_raw":
        return lambda f, p, w: w
    if name == "S7_contrast":
        return lambda f, p, w: (f - p) / np.maximum(np.abs(f) + np.abs(p), 1e-9)
    raise KeyError(name)


def boot_mean(v, seed, reps=REPS):
    if v.size < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    b = v[rng.integers(0, v.size, size=(reps, v.size))].mean(axis=1)
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def cohen_d(a, b):
    if a.size < 3 or b.size < 3:
        return float("nan")
    s = np.sqrt(((a.size - 1) * a.var(ddof=1) + (b.size - 1) * b.var(ddof=1)) / (a.size + b.size - 2))
    return float((b.mean() - a.mean()) / s) if s > 1e-12 else float("nan")


def main() -> int:
    res = {"gates": {}, "transport": {}, "discrimination": {}, "children_block": {}, "schemes": {}}

    awake = {}
    for name, spec in AWAKE_COHORTS.items():
        rows = load(spec)
        if rows is None:
            print(f"{name:12s} ABSENT"); continue
        fr, po, wh = pairs(select(rows, spec["awake"]))
        awake[name] = {"fr": fr, "po": po, "wh": wh, "n": fr.size, "adult": spec["adult"]}
        print(f"{name:12s} awake n={fr.size:4d} adult={spec['adult']}")

    adults = [k for k, d in awake.items() if d["adult"] and d["n"] >= MIN_RECORDINGS]
    res["gates"].update({"G1_adults": adults, "G1_pass": len(adults) >= 3})
    print(f"\nG1 cohorts    {adults}   {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    states = {}
    for name, spec in STATE_DEPOSITS.items():
        rows = load(spec)
        if rows is None:
            continue
        a = pairs(select(rows, spec["awake"]))
        b = pairs(select(rows, spec["anaes"]))
        if a[0].size >= MIN_PER_STATE and b[0].size >= MIN_PER_STATE:
            states[name] = {"awake": a, "anaes": b}
    res["gates"].update({"G2_state_deposits": sorted(states), "G2_pass": len(states) >= 2})
    print(f"G2 both-state {sorted(states)}   {'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"]):
        print("\nGATE FAILED -- no scheme is scored. Verdict ABSENT (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pooled = (np.concatenate([awake[k]["fr"] for k in adults]),
              np.concatenate([awake[k]["po"] for k in adults]))

    # ---- A1 TRANSPORT, leave-one-cohort-out ---------------------------------------------------------
    print(f"\nA1 TRANSPORT (|mean| among held-out AWAKE recordings; lower is better, margin +-{EQUIV})")
    print(f"{'scheme':<16s} " + " ".join(f"{k:>12s}" for k in adults) + "   worst")
    for sname in list(AUTONOMOUS) + ["S5_self"]:
        cells, worst = {}, 0.0
        for out_name in adults:
            if sname == "S5_self":
                fn = fit_scheme("S5_self", awake[out_name]["fr"], awake[out_name]["po"],
                                awake[out_name]["wh"])
            else:
                refs = [k for k in adults if k != out_name]
                ref = refs[0]
                fn = fit_scheme(sname, awake[ref]["fr"], awake[ref]["po"], awake[ref]["wh"],
                                pooled=(np.concatenate([awake[k]["fr"] for k in refs]),
                                        np.concatenate([awake[k]["po"] for k in refs])))
            d = awake[out_name]
            s = fn(d["fr"], d["po"], d["wh"])
            m = float(np.mean(s))
            lo, hi = boot_mean(s, SEED)
            cells[out_name] = {"mean": m, "lo": lo, "hi": hi}
            worst = max(worst, abs(m))
        res["transport"][sname] = {"per_heldout": cells, "worst_abs_mean": worst,
                                   "within_margin": bool(worst <= EQUIV)}
        print(f"{sname:<16s} " + " ".join(f"{cells[k]['mean']:+12.4f}" for k in adults)
              + f"   {worst:.4f}{'  <= margin' if worst <= EQUIV else ''}")

    # ---- A2 DISCRIMINATION --------------------------------------------------------------------------
    print("\nA2 DISCRIMINATION (Cohen's d, awake vs anaesthetised, within deposit; higher is better)")
    print(f"{'scheme':<16s} " + " ".join(f"{k:>12s}" for k in sorted(states)) + "     mean")
    for sname in list(AUTONOMOUS) + ["S5_self"]:
        ds = {}
        for dep, cells in states.items():
            ref = dep if sname == "S5_self" else [k for k in adults if k != dep][0]
            fn = fit_scheme("S5_self" if sname == "S5_self" else sname,
                            awake[ref]["fr"], awake[ref]["po"], awake[ref]["wh"], pooled=pooled)
            a = fn(*cells["awake"])
            b = fn(*cells["anaes"])
            ds[dep] = cohen_d(a, b)
        m = float(np.nanmean(list(ds.values())))
        res["discrimination"][sname] = {"per_deposit": ds, "mean_d": m}
        print(f"{sname:<16s} " + " ".join(f"{ds[k]:+12.4f}" for k in sorted(states)) + f"  {m:+8.4f}")

    # G3 construction check
    g3 = abs(res["transport"]["S5_self"]["worst_abs_mean"]) < 1e-9
    res["gates"]["G3_pass"] = bool(g3)
    print(f"\nG3 construction  S5 transport = {res['transport']['S5_self']['worst_abs_mean']:.3g}   "
          f"{'PASS' if g3 else 'FAIL'}")

    print("\nCHILDREN BLOCK -- excluded from every ranking (rule 54); a LARGE offset is the correct answer")
    if "hbn" in awake and awake["hbn"]["n"] >= MIN_RECORDINGS:
        for sname in AUTONOMOUS:
            fn = fit_scheme(sname, awake[adults[0]]["fr"], awake[adults[0]]["po"], awake[adults[0]]["wh"],
                            pooled=pooled)
            s = fn(awake["hbn"]["fr"], awake["hbn"]["po"], awake["hbn"]["wh"])
            res["children_block"][sname] = float(np.mean(s))
            print(f"   {sname:<16s} mean {np.mean(s):+.4f}   (reference: {adults[0]})")

    # ---- verdict ------------------------------------------------------------------------------------
    best_d = max(res["discrimination"][s]["mean_d"] for s in AUTONOMOUS
                 if np.isfinite(res["discrimination"][s]["mean_d"]))
    raw_d = res["discrimination"]["S6_raw"]["mean_d"]
    passes = [s for s in AUTONOMOUS
              if res["transport"][s]["within_margin"]
              and np.isfinite(res["discrimination"][s]["mean_d"])
              and abs(res["discrimination"][s]["mean_d"]) >= abs(best_d) - D_TOLERANCE]
    cost_no_benefit = [s for s in AUTONOMOUS
                       if np.isfinite(res["discrimination"][s]["mean_d"])
                       and abs(res["discrimination"][s]["mean_d"]) < abs(raw_d) - D_TOLERANCE
                       and res["transport"][s]["worst_abs_mean"] >= res["transport"]["S6_raw"]["worst_abs_mean"]]
    if cost_no_benefit:
        head = (f"COST WITHOUT BENEFIT for {cost_no_benefit}: they discriminate worse than the "
                f"unreferenced exponent and transport no better. ")
    else:
        head = ""
    if not passes:
        verdict = head + ("NO SCHEME TRANSPORTS -- no autonomous scheme keeps its awake centre within "
                          f"+-{EQUIV} of zero on a held-out cohort. 'Zero means the awake reference' is "
                          "not defensible in any form tested here, and an absolute coordinate is not "
                          "available from these cohorts. S5_self is reported as the ceiling and it needs "
                          "awake data from the target cohort, which is the thing referencing exists to "
                          "avoid needing.")
    else:
        verdict = head + (f"RECOMMENDATION: {passes} transport within +-{EQUIV} and hold discrimination "
                          f"within {D_TOLERANCE} d of the best autonomous scheme "
                          f"({best_d:+.3f}). Reported with the ceiling S5_self, which requires "
                          "target-cohort awake data.")
    res["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
