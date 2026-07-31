"""E88 -- Does the population reference TRANSPORT? Do awake people in a new cohort land near zero?

REGISTERED BEFORE `*_regional_aperiodic.csv` EXISTS for any awake cohort except the three ds004541
`sub-02` rows disclosed in E87.

=========================================================================================================
THE CLAIM UNDER TEST, stated as its proponents state it
=========================================================================================================
Population referencing is what turns a raw spectral slope into an interpretable score. The claim is:

    UCE = 0  means the patient's frontal/posterior aperiodic configuration matches the average AWAKE
             reference population; negative means displaced in the suppressive direction.

That is a strong claim and it is the whole basis for calling the output "distance from typical awake
brain" rather than "an aperiodic exponent in arbitrary units". **It is also entirely untested here, and
the machinery to test it does not exist in this repository:** `f_uce_v1` standardises only when
`meta['uce_ref']` is supplied and it never is, so every stored `uce_v1` value is the raw weighted
combination. The population constants an external audit reports (F_mean -1.4320, F_SD 0.5294,
P_mean -1.4658, P_SD 0.5187) appear nowhere here and are NOT used below -- this experiment derives its own
reference from its own data and states which.

**The red-team objection this is built to answer, in their own framing: z-scoring can make things look
stable when the raw centroids are not.** If awake people in cohort B land at -1.4 when referenced to
cohort A, then "zero means awake" is false outside A, and every threshold, alert level and cross-dataset
comparison built on it inherits that error.

=========================================================================================================
DESIGN -- leave-one-cohort-out, awake only
=========================================================================================================
Every cohort contributes only its AWAKE recordings. For each cohort in turn as the REFERENCE:

    mean_F, sd_F, mean_P, sd_P are computed from the reference cohort's awake recordings ONLY
    every OTHER cohort's awake recordings are scored:
        UCE_ref = 0.696 * (F - mean_F)/sd_F  +  0.718 * (P - mean_P)/sd_P

    P  For each (reference, held-out) pair, the MEAN UCE_ref of the held-out awake cohort.
       Under the interpretability claim this should be ~ 0.

    EQUIVALENCE, margin fixed here before any value exists: the held-out cohort's mean is TRANSPORTS if
    its whole 95 % interval lies within +-0.5 weighted-SD units of zero. Half a population SD is a
    generous margin; a score whose awake centre moves more than that across cohorts cannot support an
    absolute threshold.

       TRANSPORTS      interval inside +-0.5
       FAILS           interval excludes 0 AND lies outside +-0.5, i.e. the awake centre is
                       demonstrably displaced
       UNDETERMINED    neither -- named, and not reportable as either

PREDICTION WRITTEN NOW: **transport FAILS for at least one adult pair.** Aperiodic exponent is known to
depend on montage, reference, amplifier bandwidth and fit range, none of which is shared across these
deposits, and this repository has already measured a between-deposit displacement it could not attribute
to population. Predicting failure is predicting against the framing that makes the score attractive.

=========================================================================================================
THE CHILDREN ARE NOT A FAILURE CASE AND ARE NOT POOLED (rule 54)
=========================================================================================================
HBN is a developmental cohort. The aperiodic exponent changes with age, so an offset there is **expected
biology, not a transport failure**, and pooling it with adults would be exactly the error E66 made when it
computed a transportability statistic across anaesthetised patients, awake children and awake adults and
could not tell working features from broken ones. HBN is therefore reported in a SEPARATE block, labelled,
and excluded from the verdict. It is retained because it is the one cohort where a large offset would be
the CORRECT answer, which makes it the design's positive control: **a reference scheme that shows no
offset for children is not measuring what it claims.**

GATES (rule 40):

    G1  COHORTS    >= 3 adult awake cohorts with >= 20 recordings each, else the leave-one-out has no
                   denominator and the verdict is ABSENT.
    G2  CHANNELS   >= 5 frontal and >= 5 posterior channels in every included recording.
    G3  THE SD IS REAL. Each reference cohort's frontal and posterior SD must exceed 0.05. Dividing by a
                   near-zero SD manufactures enormous z-scores and would make transport look catastrophic
                   for an arithmetic reason.
    G4  POSITIVE CONTROL. Referencing a cohort to ITSELF must give a mean of 0 to within 1e-9, by
                   construction. If it does not, the standardisation is misimplemented and nothing below
                   is interpretable.

WHAT NO OUTCOME LICENSES. This consults no state label beyond "awake", and it is a measurement-scale
question, not a claim about consciousness. TRANSPORTS would not show the score is useful; it would show
that one specific interpretive sentence about zero is defensible.

    python -m bsde.experiments.e88_population_reference_transport
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

OUT = os.path.join(RESULTS, "e88_population_reference_transport.json")

# awake-only selectors, declared here rather than inferred at run time
COHORTS = {
    "lemon":    {"table": "lemon_regional_aperiodic.csv", "awake": None, "adult": True},
    "eegmmidb":  {"table": "eegmmidb_regional_aperiodic.csv", "awake": None, "adult": True},
    "ds004541":  {"table": "ds004541_regional_aperiodic.csv", "awake": ("baseline",), "adult": True,
                  "exclude_subjects": {"sub-02"}},
    "ds005620":  {"table": "ds005620_regional_aperiodic.csv",
                  "awake": ("awake", "eyesclosed", "rest"), "adult": True},
    "hbn":       {"table": "hbn_regional_aperiodic.csv", "awake": None, "adult": False},
}
MIN_RECORDINGS = 20
MIN_CHANNELS = 5
MIN_SD = 0.05
EQUIV = 0.5
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(name, spec):
    p = os.path.join(RESULTS, spec["table"])
    if not os.path.exists(p):
        return None
    rows = [r for r in csv.DictReader(open(p, newline="")) if r.get("status") == "ok"]
    ex = spec.get("exclude_subjects", set())
    rows = [r for r in rows if r.get("subject") not in ex]
    if spec["awake"]:
        rows = [r for r in rows
                if any(t in r["recording_id"].lower() for t in spec["awake"])]
    fr = np.array([_f(r["aperiodic_frontal"]) for r in rows])
    po = np.array([_f(r["aperiodic_posterior"]) for r in rows])
    nf = np.array([_f(r.get("n_frontal", "")) for r in rows])
    npo = np.array([_f(r.get("n_posterior", "")) for r in rows])
    ok = (np.isfinite(fr) & np.isfinite(po) & (nf >= MIN_CHANNELS) & (npo >= MIN_CHANNELS))
    return {"frontal": fr[ok], "posterior": po[ok], "n": int(ok.sum()),
            "n_dropped_channels": int((~ok).sum()), "adult": spec["adult"]}


def score(target, ref):
    zf = (target["frontal"] - ref["mF"]) / ref["sF"]
    zp = (target["posterior"] - ref["mP"]) / ref["sP"]
    return W_FRONTAL * zf + W_POSTERIOR * zp


def boot_mean(v, seed, reps=REPS):
    rng = np.random.default_rng(seed)
    b = v[rng.integers(0, v.size, size=(reps, v.size))].mean(axis=1)
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def classify(lo, hi):
    if not np.isfinite(lo):
        return "NOT-COMPUTABLE"
    if lo > -EQUIV and hi < EQUIV:
        return "TRANSPORTS"
    if (lo > 0 or hi < 0) and (lo > EQUIV or hi < -EQUIV):
        return "FAILS"
    return "UNDETERMINED"


def main() -> int:
    res = {"gates": {}, "cohorts": {}, "pairs": {}, "children_block": {}}
    data = {}
    for name, spec in COHORTS.items():
        d = load(name, spec)
        if d is None:
            print(f"{name:12s} ABSENT (not extracted yet)")
            continue
        data[name] = d
        res["cohorts"][name] = {"n_awake": d["n"], "n_dropped_for_channels": d["n_dropped_channels"],
                                "adult": d["adult"],
                                "mean_frontal": float(np.mean(d["frontal"])) if d["n"] else None,
                                "sd_frontal": float(np.std(d["frontal"], ddof=1)) if d["n"] > 1 else None,
                                "mean_posterior": float(np.mean(d["posterior"])) if d["n"] else None,
                                "sd_posterior": float(np.std(d["posterior"], ddof=1)) if d["n"] > 1 else None}
        c = res["cohorts"][name]
        print(f"{name:12s} n={d['n']:4d} adult={d['adult']}  "
              f"F {c['mean_frontal']:+.4f} (sd {c['sd_frontal']:.4f})  "
              f"P {c['mean_posterior']:+.4f} (sd {c['sd_posterior']:.4f})"
              if d["n"] > 1 else f"{name:12s} n={d['n']} -- too few")

    adults = [k for k, d in data.items() if d["adult"] and d["n"] >= MIN_RECORDINGS]
    res["gates"]["G1_adult_cohorts"] = adults
    res["gates"]["G1_pass"] = len(adults) >= 3
    print(f"\nG1 cohorts   {len(adults)} adult awake cohorts with >= {MIN_RECORDINGS}: {adults}   "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    refs = {}
    g3 = True
    for k in data:
        d = data[k]
        if d["n"] < 2:
            continue
        r = {"mF": float(np.mean(d["frontal"])), "sF": float(np.std(d["frontal"], ddof=1)),
             "mP": float(np.mean(d["posterior"])), "sP": float(np.std(d["posterior"], ddof=1))}
        refs[k] = r
        if k in adults and (r["sF"] < MIN_SD or r["sP"] < MIN_SD):
            g3 = False
    res["gates"]["G3_pass"] = bool(g3)
    print(f"G3 sd real   {'PASS' if g3 else 'FAIL -- a reference SD is below ' + str(MIN_SD)}")

    g4 = True
    for k in adults:
        s = score(data[k], refs[k])
        if abs(float(np.mean(s))) > 1e-9:
            g4 = False
    res["gates"]["G4_pass"] = bool(g4)
    print(f"G4 self-ref  referencing a cohort to itself gives mean 0   {'PASS' if g4 else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and g3 and g4):
        print("\nGATE FAILED -- no pair is evaluated. Verdict ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    print(f"\n{'reference':<12s} -> {'held-out':<12s} {'mean UCE':>10s} {'95% CI':>22s}  verdict")
    verdicts = []
    for ref_name in adults:
        for out_name in adults:
            if out_name == ref_name:
                continue
            s = score(data[out_name], refs[ref_name])
            m = float(np.mean(s))
            lo, hi = boot_mean(s, SEED)
            v = classify(lo, hi)
            res["pairs"][f"{ref_name}->{out_name}"] = {"mean": m, "lo": lo, "hi": hi, "verdict": v}
            verdicts.append(v)
            print(f"{ref_name:<12s} -> {out_name:<12s} {m:+10.4f} [{lo:+9.4f}, {hi:+9.4f}]  {v}")

    print("\nCHILDREN BLOCK -- reported separately, EXCLUDED from the verdict (rule 54). A large offset "
          "here is expected biology and is this design's positive control.")
    if "hbn" in data and data["hbn"]["n"] >= MIN_RECORDINGS:
        for ref_name in adults:
            s = score(data["hbn"], refs[ref_name])
            m = float(np.mean(s))
            lo, hi = boot_mean(s, SEED)
            res["children_block"][f"{ref_name}->hbn"] = {"mean": m, "lo": lo, "hi": hi}
            print(f"{ref_name:<12s} -> {'hbn':<12s} {m:+10.4f} [{lo:+9.4f}, {hi:+9.4f}]")
    else:
        print("   hbn not available")

    n_fail = verdicts.count("FAILS")
    n_ok = verdicts.count("TRANSPORTS")
    res["verdict"] = (
        f"{n_ok} of {len(verdicts)} adult awake pairs TRANSPORT within +-{EQUIV} weighted-SD units; "
        f"{n_fail} FAIL; {len(verdicts) - n_ok - n_fail} UNDETERMINED. "
        + ("A single FAIL is sufficient to withdraw the sentence 'UCE = 0 means the awake reference', "
           "because that sentence is a claim about every cohort, not most of them."
           if n_fail else
           "No pair failed, so the zero-means-awake sentence survives on these cohorts at this margin -- "
           "which is a claim about the SCALE, not about the score's usefulness."))
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
