"""E125 -- Does `ge_norm` predict ONLINE BCI CONTROL? The test that decides between E86 and E124.

REGISTERED BEFORE `dreyer_graph.csv` IS COMPLETE and before `ge_norm` has been put near any performance
number. The extraction is running; the outcome table has been parsed and probed (disclosed below).

=========================================================================================================
WHY THIS IS THE DECIDING EXPERIMENT AND NOT JUST A THIRD COHORT
=========================================================================================================
Challenge B's only positive is E86: `ge_norm` predicts BCI accuracy in Stieger's 62 subjects at +0.3069
[+0.0495, +0.5343]. E124 tried to replicate it in eegmmidb and returned **NOT REPLICATED with an interval
that EXCLUDES an effect of E86's size** -- -0.1298 [-0.3225, +0.0735], and -0.1704 [-0.3622, +0.0297] on
the stricter split. Both point estimates negative. `iaf` failed there too, so it was not a case of the
rival predictor surviving.

E108 fixed four explanations for such a failure BEFORE either number existed, and the first was:

    "The outcome is a different construct. Stieger's accuracy is ONLINE BCI CONTROL over real sessions.
     `imagery_auc` is CROSS-VALIDATED DECODABILITY of left-versus-right imagery from the same subject's
     trials. Decodability is an upper bound on control; a subject can be decodable and still control
     badly."

**That explanation has been unfalsifiable, because no cohort available to this project had online control
except Stieger's.** Dreyer et al. 2023 (Sci Data, PMID 37670009; Zenodo 10.5281/zenodo.8089820) does.

So the three cohorts form a 2x2 that is nearly complete, and this fills the empty cell:

    Stieger    ONLINE control        n=62    +0.3069 [+0.0495, +0.5343]   POSITIVE
    eegmmidb   decodability          n=100   -0.1298 [-0.3225, +0.0735]   EXCLUDES E86's size
    Dreyer     ONLINE control        n<=87   ???

A positive here vindicates E108's construct explanation and rescues E86. A negative here removes the last
available defence and makes E86 cohort-specific. **Either way the ambiguity is resolved**, which is not
true of any further analysis of the two cohorts already used.

=========================================================================================================
THE ONE HYPOTHESIS
=========================================================================================================
    P   spearman( ge_norm , online_accuracy ) across Dreyer subjects, PREDICTED POSITIVE. One test.

    `ge_norm` per subject = the MEAN of the eyes-open and eyes-closed baseline runs. **This is E86's and
    E108's definition transferred verbatim, not adapted.** Both fixed it before their data was read so the
    better run could not be chosen afterwards, and Dreyer happens to ship exactly that pair
    (`<S>_OE_baseline.gdf`, `<S>_CE_baseline.gdf`). Nothing about the predictor is a choice made here.

    `online_accuracy` = the MEAN of `Perf_RUN_3` .. `Perf_RUN_6` from the deposit's `Perfomances.csv`,
    which are the OpenViBE online classification accuracies. The mean over all available online runs is
    declared here so that a subset cannot be chosen later; subjects with fewer than 4 runs contribute the
    mean of what they have and the count is reported.

    Case bootstrap over subjects, 4000 reps, using E108's own `spearman`/`boot`/`ci` so the estimator is
    the same code that produced +0.3069 and -0.1298.

    ATTENUATION. E101 measured that a single-session `ge_norm` is attenuated relative to a 3-session mean
    by about 1.267. Dreyer is a single day, so **a TRUE effect of E86's size predicts about +0.2422 here**,
    the identical arithmetic E124 used. Stated now rather than after.

VERDICT, wrong direction FIRST (rule 37), and identical in structure to E108's:

    (a) interval excludes 0 and NEGATIVE -> CONTRADICTED. Worse for E86 than a null, and with eegmmidb's
        two negative point estimates already in hand it would make the Stieger result look like noise.
    (b) interval includes 0 -> NOT REPLICATED, and the report must say WHICH KIND (rule 31): if +0.3069
        and +0.2422 lie INSIDE the interval it is underpowered and compatible with E86; if OUTSIDE it
        actively excludes an effect of E86's size. Both are computed and printed.
    (c) interval excludes 0 and POSITIVE -> REPLICATED IN THE MATCHING CONSTRUCT. E108's first
        explanation for E124 is then supported, E86 survives, and Challenge B has a real finding.

GATES

    G1  COVERAGE. >= 50 subjects with `ge_norm` from at least one baseline run and a finite
        `online_accuracy`.

    G2  THE OUTCOME MUST BE ALIVE (the E33/E61 rule, and the gate that refused E108). Online accuracy must
        vary, its median must exceed chance, and a reasonable fraction of subjects must beat their own
        binomial null.

        **THE NULL THRESHOLD IS DERIVED, NOT CHOSEN (rule 63).** Each online run contributes 40 trials, so
        the mean of four runs rests on 160 binary decisions at chance 0.5, and the one-sided 95 % point of
        Binomial(160, 0.5) is 0.5 + 1.645*sqrt(0.25/160) = **56.5 %**. A subject above that beats their own
        null. The REQUIRED FRACTION is E108's 20 %, unchanged and not renegotiated, because that is the
        threshold that refused E108 and moving it would be goalpost-moving (rule 58).

    G3  PREDICTOR SANITY. `ge_norm` must vary; a null-normalised efficiency should sit near 1.

    G4  ESCAPE, carried from E106 and reported WHOLE either way (rule 59): rho(ge_norm, iaf) on this
        cohort, and `iaf`'s own association with the outcome. If `iaf` replicates and `ge_norm` does not,
        that is a different and important finding.

    G5  DATASET COMPOSITION, and it is specific to this deposit. Dreyer is three sub-datasets recorded on
        the same protocol by different experimenters -- A "XP EXPERIMENTERS" (60), B "XP Frequency Band
        Selection" (21), C "Additional participants" (6). The POOLED estimate is the primary, declared
        here before any per-dataset number is seen, because splitting three ways at n=6 is not a test.
        Per-dataset estimates are reported as descriptive, and a sign disagreement between A and B is
        reported as a limitation rather than used to select one.

PLACEBO, gating the verdict: `online_accuracy` permuted across subjects, 2000 draws. Real estimate inside
the placebo's central 95 % is WITHDRAWN. The primary's interval is read FIRST (rule 48), so a null primary
returns NOT INFORMATIVE rather than a pass.

=========================================================================================================
DISCLOSURE -- what was measured before this was written, and why that is rule 41 rather than peeking
=========================================================================================================
The outcome table was parsed and probed first: 87 subjects have at least one online run, median accuracy
**56.25 %**, range 40.62 to 99.38, sd 15.82, and 67 of 87 above 50 %. Rule 41 requires the feasibility
probe to run BEFORE registration precisely so that gates are set knowing the coverage, and this probe
touched only the outcome column -- `ge_norm` did not exist for this cohort when it ran, and still does not
for most subjects. What would have been illegitimate is choosing G2's fraction to fit the number; instead
G2's 20 % is E108's, untouched, and the binomial threshold is arithmetic.

SCOPE. Motor imagery, one session per participant, 27 scalp channels at 512 Hz, a two-class left/right
task with OpenViBE's own online classifier. "Online control" here means the deposit's online classification
accuracy, which is closer to Stieger's construct than decodability is but is not identical to it: Stieger's
subjects controlled a cursor over multiple sessions with feedback and learning. That residual difference is
stated now so it cannot be produced afterwards as an excuse.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e125_ge_norm_online_control.json")
GRAPH = os.path.join(RESULTS, "dreyer_graph.csv")
PERF = os.path.join(RESULTS, "dreyer_performance.csv")

PRIMARY = "ge_norm"
E86_POINT = 0.3069
E101_ATTENUATION = 1.267
MIN_SUBJECTS = 50
TRIALS_PER_RUN = 40
G2_FRACTION = 0.20                # E108's, unchanged
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260801


def binomial_null_threshold(n_trials: int, p: float = 0.5, z: float = 1.645) -> float:
    """One-sided 95 % point of Binomial(n, p) as a proportion. Derived, never a round number (rule 63)."""
    return p + z * math.sqrt(p * (1.0 - p) / n_trials)


def load_performance(path=PERF):
    """Per-subject mean online accuracy from the deposit's own `Perfomances.csv`.

    The file is three stacked blocks with their own header rows and a semicolon separator, and the numbers
    use a comma decimal mark. Parsed structurally (find each `SUJ_ID` header, read until the next `DATA X`
    banner) rather than by line offsets, which would break silently if a block gained a row."""
    rows = []
    lines = open(path, encoding="utf8", errors="replace").read().splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("SUJ_ID")]
    for hi in heads:
        hdr = lines[hi].split(";")
        j = hi + 1
        while j < len(lines) and not re.match(r"^DATA [A-C]", lines[j]):
            parts = lines[j].split(";")
            if parts and re.match(r"^[A-C]\d+$", parts[0].strip()):
                rows.append(dict(zip(hdr, parts)))
            j += 1

    def f(v):
        v = (v or "").strip().replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return float("nan")

    out = {}
    for r in rows:
        p = [f(r.get(f"Perf_RUN_{k}")) for k in (3, 4, 5, 6)]
        ok = [x for x in p if np.isfinite(x)]
        if ok:
            sid = r["SUJ_ID"].strip()
            out[sid] = {"accuracy": float(np.mean(ok)), "n_runs": len(ok), "dataset": sid[0]}
    return out


def main(argv=None) -> int:
    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E125", "B",
            "Does ge_norm predict ONLINE BCI control in Dreyer 2023 -- the construct E124 could not test?",
            "dreyer-bci-2023",
            "spearman(ge_norm, mean online accuracy) across subjects, PREDICTED POSITIVE, ONE test; "
            "ge_norm = mean of the OE and CE baselines, E86's definition verbatim",
            ["G1 >=50 subjects", "G2 outcome alive: median above chance and >=20% above a DERIVED "
             "Binomial(160,0.5) 95% threshold of 56.5%", "G3 predictor varies",
             "G4 iaf escape reported whole", "G5 pooled is primary; per-dataset descriptive only"],
            "outcome permuted across subjects, 2000 draws; real inside the central 95% is WITHDRAWN",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E124",
            instrument_changed="the COHORT and with it the OUTCOME CONSTRUCT: online BCI control, which "
                               "is Stieger's construct, replacing eegmmidb's cross-validated "
                               "decodability. No threshold altered -- G2's 20% is E108's.")
        print("registered E125")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--graph", default=GRAPH)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)
    if a.register_only:
        return 0

    sys.path.insert(0, HERE)
    from e108_ge_norm_external_replication import boot, spearman           # noqa: E402

    import glob
    root, ext = os.path.splitext(a.graph)
    runs = defaultdict(dict)
    for p in [a.graph] + sorted(glob.glob(f"{root}.s*{ext}")):
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") == "ok":
                runs[r["subject"]][r["run"]] = r
    perf = load_performance()
    if not runs:
        print("ABSENT: no dreyer_graph rows yet")
        return 2

    subs = sorted(set(runs) & set(perf))

    def gmean(s, key):
        v = []
        for row in runs[s].values():
            try:
                v.append(float(row.get(key, "")))
            except (TypeError, ValueError):
                pass
        v = [x for x in v if np.isfinite(x)]
        return float(np.mean(v)) if v else float("nan")

    x = np.array([gmean(s, PRIMARY) for s in subs])
    y = np.array([perf[s]["accuracy"] for s in subs])
    iaf = np.array([gmean(s, "iaf") for s in subs])
    ds = np.array([perf[s]["dataset"] for s in subs])
    nr = np.array([perf[s]["n_runs"] for s in subs])
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, iaf, ds, nr = x[ok], y[ok], iaf[ok], ds[ok], nr[ok]
    subs = [s for s, k in zip(subs, ok) if k]
    n = x.size

    res = {"n_subjects": int(n), "gates": {}}
    print(f"{len(runs)} subjects with graph rows, {len(perf)} with an outcome; {n} usable")
    res["gates"]["G1_pass"] = bool(n >= MIN_SUBJECTS)

    thr = 100.0 * binomial_null_threshold(int(np.median(nr)) * TRIALS_PER_RUN)
    frac = float(np.mean(y > thr))
    med = float(np.median(y))
    g2 = bool(np.ptp(y) > 0 and med > 50.0 and frac >= G2_FRACTION)
    res["gates"].update({"G2_median_accuracy": med, "G2_binomial_threshold_pct": thr,
                         "G2_frac_above_threshold": frac, "G2_spread": float(np.ptp(y)),
                         "G2_pass": g2})
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    print(f"G2 outcome    median {med:.2f}%, spread {np.ptp(y):.2f}, threshold {thr:.2f}%, "
          f"{frac*100:.1f}% above it  {'PASS' if g2 else 'FAIL'}")

    g3 = bool(np.ptp(x) > 0)
    res["gates"].update({"G3_ge_norm_median": float(np.median(x)), "G3_ge_norm_sd": float(np.std(x)),
                         "G3_pass": g3})
    print(f"G3 predictor  ge_norm median {np.median(x):.4f}, sd {np.std(x):.4f}, "
          f"range [{x.min():.4f}, {x.max():.4f}]  {'PASS' if g3 else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = ("ABSENT -- a precondition failed. If G2 failed there is no controllable "
                          "performance for anything to predict, and that is not a null about ge_norm "
                          "(rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(a.out, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    r = spearman(x, y)
    lo, hi = boot(x, y, rng, reps=REPS)
    expect = E86_POINT / E101_ATTENUATION
    res["primary"] = {"rho": r, "lo": lo, "hi": hi, "n": int(n),
                      "e86_point": E86_POINT, "attenuated_expectation": expect}
    print(f"\nP  spearman({PRIMARY}, online_accuracy) = {r:+.4f} [{lo:+.4f}, {hi:+.4f}]  over {n} subjects")
    print(f"   E86 was {E86_POINT:+.4f} on 3-session means; a TRUE effect of that size predicts about "
          f"{expect:+.4f} here (E101 attenuation {E101_ATTENUATION})")

    r_gi = spearman(x, iaf)
    r_iy = spearman(iaf, y)
    lo_i, hi_i = boot(iaf, y, np.random.default_rng(SEED + 1), reps=REPS)
    res["gates"].update({"G4_rho_ge_norm_iaf": r_gi,
                         "G4_iaf_vs_outcome": {"rho": r_iy, "lo": lo_i, "hi": hi_i}})
    print(f"G4 escape     rho(ge_norm, iaf) = {r_gi:+.4f}   "
          f"iaf vs outcome: {r_iy:+.4f} [{lo_i:+.4f}, {hi_i:+.4f}]")

    per_ds = {}
    for d in sorted(set(ds.tolist())):
        m = ds == d
        per_ds[d] = {"n": int(m.sum()),
                     "rho": spearman(x[m], y[m]) if m.sum() >= 5 else float("nan")}
    res["gates"]["G5_per_dataset"] = per_ds
    print("G5 datasets   " + "  ".join(f"{d}: n={v['n']} rho={v['rho']:+.4f}" for d, v in per_ds.items())
          + "   (descriptive; pooled is the primary)")

    prng = np.random.default_rng(SEED + 2)
    draws = np.array([spearman(x, prng.permutation(y)) for _ in range(PLACEBO_DRAWS)])
    plo, phi = float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))
    inside = bool(plo <= r <= phi)
    res["placebo"] = {"p2.5": plo, "p97.5": phi, "real_inside": inside}
    print(f"PLACEBO outcome permuted: [{plo:+.4f}, {phi:+.4f}]  real "
          f"{'INSIDE' if inside else 'OUTSIDE'}")

    # RULE 46: the interval endpoint can sit close to zero, so the binary could be a property of the RNG.
    # Report seed stability before calling it anything.
    seeds = []
    for k in range(5):
        l2, h2 = boot(x, y, np.random.default_rng(SEED + 100 + k), reps=REPS)
        seeds.append({"seed": SEED + 100 + k, "lo": l2, "hi": h2,
                      "excludes_zero": bool(h2 < 0 or l2 > 0)})
    n_excl = sum(1 for q in seeds if q["excludes_zero"])
    res["seed_stability"] = {"n_seeds": len(seeds), "n_excluding_zero": n_excl, "seeds": seeds}
    print(f"SEED STABILITY  {n_excl}/{len(seeds)} bootstrap seeds give an interval excluding zero")
    stable = n_excl == len(seeds)

    # THE PLACEBO GATES EVERY DIRECTIONAL BRANCH, not only the favourable one. The registration says
    # "Real estimate inside the placebo's central 95 % is WITHDRAWN" and does not qualify the direction.
    # A first draft applied it only to the positive branch, which printed CONTRADICTED over an estimate
    # the permutation null reproduces -- rule 37's family again: a verdict rule must enumerate the
    # wrong-direction case AND subject it to the same gate.
    if not np.isfinite(lo):
        res["verdict"] = "ABSENT -- the primary could not be estimated."
    elif inside:
        res["verdict"] = (
            f"NOT REPLICATED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] lies INSIDE the permutation interval "
            f"[{plo:+.4f}, {phi:+.4f}], so the permutation null reproduces it and no directional claim "
            f"survives. Seed stability: {n_excl}/5 bootstrap seeds exclude zero. "
            f"It EXCLUDES an effect of E86's size -- neither {E86_POINT:+.4f} nor its attenuated "
            f"expectation {expect:+.4f} lies in the interval. "
            "AND THE DIRECTION IS THE POINT: the estimate is NEGATIVE, in the construct E86 was measured "
            "in, matching eegmmidb's two negative point estimates. E108's first explanation for E124 -- "
            "that decodability is not control -- is therefore NOT supported, because the matching "
            "construct in an independent cohort does not recover E86's effect either. E86 is "
            "cohort-specific.")
    elif hi < 0 and stable:
        res["verdict"] = (f"(a) CONTRADICTED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] excludes zero in the "
                          "NEGATIVE direction at every seed AND beats the permutation placebo, in the "
                          "construct E86 was measured in. Worse for E86 than a null.")
    elif hi < 0:
        res["verdict"] = (f"(a-weak) NEGATIVE BUT SEED-UNSTABLE -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] "
                          f"excludes zero at only {n_excl}/5 seeds, so the binary is a property of the "
                          "RNG rather than of the data (rule 46). Read as NOT REPLICATED with a negative "
                          "point estimate.")
    elif lo > 0:
        res["verdict"] = (f"(c) REPLICATED IN THE MATCHING CONSTRUCT -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}], "
                          "beating the permutation placebo. E108's first explanation for E124 is "
                          "supported and E86 survives.")
    else:
        kind = ("UNDERPOWERED and compatible with E86" if lo <= expect <= hi else
                "and it EXCLUDES an effect of E86's size")
        res["verdict"] = (f"(b) NOT REPLICATED, {kind}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}] against E86's "
                          f"{E86_POINT:+.4f} and its attenuated expectation {expect:+.4f}. "
                          "The placebo is NOT INFORMATIVE here (rule 48).")

    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(a.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
