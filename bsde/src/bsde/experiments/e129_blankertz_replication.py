"""E129 -- Does the FIELD's own published predictor of BCI performance replicate?

REGISTERED BEFORE `dreyer_smr.csv` HAS BEEN PUT NEAR ANY PERFORMANCE NUMBER. The extraction is complete
(87/87) and its construction is committed; nothing has been correlated.

=========================================================================================================
WHY THIS IS THE RIGHT CHALLENGE-B EXPERIMENT NOW
=========================================================================================================
This project's only Challenge B positive is closed. E86 found `ge_norm` predicts BCI accuracy in Stieger's
62 subjects at +0.3069 [+0.0495, +0.5343]; E124 found -0.1298 [-0.3225, +0.0735] in eegmmidb, EXCLUDING an
effect of that size; E125 found -0.2065 [-0.3921, -0.0003] in Dreyer's ONLINE-control cohort, inside its
own permutation band and again excluding E86's size. Two independent cohorts, one construct-matched, both
negative. E86 is cohort-specific.

**A fourth measure of ours would answer nothing. The question that does is whether ANYONE's predictor
replicates**, because that distinguishes two very different worlds:

    if the field's predictor replicates here  -> resting EEG does predict BCI performance, and `ge_norm`
                                                 is simply the wrong measure. Challenge B is alive.
    if it does not                            -> the replication problem is the FIELD's, not ours, and
                                                 E86's fate is unremarkable. That reframes the challenge
                                                 rather than losing it.

Blankertz B, Sannelli C, Halder S, Hammer EM, Kubler A, Muller KR, Curio G, Dickhaus T. "Neurophysiological
predictor of SMR-based BCI performance." Neuroimage 2010;51(4):1303-9. PMID 20303409 (verified from the
MEDLINE record, rule 25). Quoting the abstract:

    "we propose a neurophysiological predictor of BCI performance which can be determined from a two
     minute recording of a 'relax with eyes open' condition using two Laplacian EEG channels. A
     correlation of r=0.53 between the proposed predictor and BCI feedback performance was obtained on a
     large data base with N=80 BCI-naive participants in their first session"

**Dreyer is close to a direct replication cohort**: N=87, BCI-naive, first and only session, online
feedback performance, an eyes-open baseline, and a montage carrying both C3 and C4 with all four Laplacian
neighbours each. The window this project already used for its graph extraction is 120 s -- two minutes --
so not even that had to be adjusted to match.

POWER. r = 0.53 is far larger than E86's +0.3069. At n = 87 a two-sided 95 % interval around an observed
0.53 would be roughly [0.36, 0.66], and even E101's single-session attenuation of 1.267 leaves an expected
0.42. **A null here is therefore a statement about the field rather than about sample size**, which is the
property that makes this worth running and that E108's own null did not have.

=========================================================================================================
THE ONE HYPOTHESIS
=========================================================================================================
    P   spearman( smr_predictor_db , online_accuracy ) across Dreyer subjects, PREDICTED POSITIVE.
        One test. `online_accuracy` is the mean of `Perf_RUN_3` .. `Perf_RUN_6`, the SAME outcome
        definition E125 registered and used, so the two experiments differ only in the predictor.

    `smr_predictor_db` is the larger of the two Laplacian channels' peak decibel excess of the eyes-open
    PSD over a 1/f background fitted EXCLUDING the SMR band. The formula is an INFERENCE from the
    abstract's description (the paper is paywalled) and is labelled as one in
    `bsde/scripts/extract_dreyer_smr.py`; what is quoted is two minutes, eyes open, two Laplacian
    channels, and the reported r.

SECONDARIES, reported whole either way (rule 59) and NOT eligible to become the headline:
    S1  `smr_C3_db` and `smr_C4_db` separately, since "the larger of two" is the one convention choice.
    S2  `alpha_prom` from `dreyer_graph.csv` -- the pre-existing 7-13 Hz median-over-channels version of
        the same idea. If it behaves like the Laplacian version, the sensorimotor localisation is not
        doing the work; if it does not, it is (rule 28's question, asked before rather than after).
    S3  `ge_norm` on these same subjects, so E125's -0.2065 sits beside this in one table.

GATES
    G1  COVERAGE >= 50 subjects with a finite predictor and outcome.
    G2  OUTCOME ALIVE -- E125's, unchanged and not renegotiated: median online accuracy above chance, and
        >= 20 % of subjects above the DERIVED Binomial(160, 0.5) 95 % point of 56.5 %. E125 measured
        56.25 % median with 49.4 % above it, so this is expected to pass; it is re-evaluated rather than
        assumed.
    G3  PREDICTOR ALIVE. `smr_predictor_db` must vary and must be positive for most subjects -- an SMR
        peak that does not exceed its own noise floor would mean the band or the background fit is wrong.

PLACEBO, gating the verdict: outcome permuted across subjects, 2000 draws; real estimate inside the
central 95 % is WITHDRAWN, whatever its direction. **That last clause is written explicitly because
E125's first draft applied the placebo gate only to the favourable branch and printed CONTRADICTED over an
estimate the permutation null reproduced.** Rule 48: the primary interval is read first.

VERDICT, wrong direction FIRST (rule 37, eighth occurrence):
    (a) interval excludes 0 NEGATIVE -> CONTRADICTED. A published r = +0.53 coming back negative in a
        matched cohort is a strong claim and would need the placebo and a seed-stability check before it
        could be said out loud.
    (b) interval includes 0 -> NOT REPLICATED, and the report must say WHICH KIND (rule 31): whether
        +0.53 and its attenuated +0.42 lie inside the interval (underpowered) or outside (actively
        excluding the published effect). Both are computed and printed.
    (c) interval excludes 0 POSITIVE and beats the placebo -> REPLICATED. Then resting EEG does predict
        BCI performance, `ge_norm` is simply worse than the published predictor, and Challenge B has a
        live incumbent to improve on rather than a dead line.

CALIBRATION, before the run: (c) ~45 %, (b) ~40 %, (a) ~15 %. (c) is favoured because the cohort match is
unusually close and the published effect is large; (b) is given nearly as much because the formula is
inferred rather than transcribed, and an inferred formula is a real way to lose a true effect.

SCOPE. One deposit, one session per participant, OpenViBE's own online classifier, two-class left/right
motor imagery. Blankertz's cohort used the Berlin BBCI system; "online feedback performance" is the same
construct but not the same apparatus. And the predictor is an inference from a description, so a null is
weaker evidence against the published claim than a replication would be evidence for it -- an asymmetry
stated now rather than discovered afterwards (rule 47).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e129_blankertz_replication.json")
SMR = os.path.join(RESULTS, "dreyer_smr.csv")
GRAPH = os.path.join(RESULTS, "dreyer_graph.csv")

PUBLISHED_R = 0.53
E101_ATTENUATION = 1.267
MIN_SUBJECTS = 50
G2_FRACTION = 0.20
TRIALS = 160
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260802


def _read_shards(base):
    root, ext = os.path.splitext(base)
    seen, rows = set(), []
    for p in [base] + sorted(glob.glob(f"{root}.s*{ext}")):
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            k = (r.get("subject"), r.get("run", ""))
            if k in seen or r.get("status") != "ok":
                continue
            seen.add(k)
            rows.append(r)
    return rows


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E129", "B",
            "Does Blankertz 2010's published SMR predictor (r=0.53) replicate on Dreyer's 87 subjects?",
            "dreyer-bci-2023",
            "spearman(smr_predictor_db, mean online accuracy), PREDICTED POSITIVE, one test",
            ["G1 >=50 subjects", "G2 outcome alive (E125's, unchanged)", "G3 predictor alive and positive"],
            "outcome permuted across subjects, 2000 draws; inside the central 95% is WITHDRAWN in EITHER "
            "direction",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E125",
            instrument_changed="the PREDICTOR: the field's own published SMR measure replaces ge_norm, so "
                               "the question becomes whether ANYONE's predictor replicates")
        print("registered E129")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)
    if a.register_only:
        return 0

    sys.path.insert(0, HERE)
    from e108_ge_norm_external_replication import boot, spearman           # noqa: E402
    from e125_ge_norm_online_control import load_performance               # noqa: E402

    smr = {r["subject"]: r for r in _read_shards(SMR)}
    perf = load_performance()
    graph = {}
    for r in _read_shards(GRAPH):
        graph.setdefault(r["subject"], []).append(r)

    subs = sorted(set(smr) & set(perf))
    x = np.array([_f(smr[s]["smr_predictor_db"]) for s in subs])
    y = np.array([perf[s]["accuracy"] for s in subs])
    c3 = np.array([_f(smr[s]["smr_C3_db"]) for s in subs])
    c4 = np.array([_f(smr[s]["smr_C4_db"]) for s in subs])

    def gmean(s, key):
        v = [_f(r.get(key, "")) for r in graph.get(s, [])]
        v = [q for q in v if np.isfinite(q)]
        return float(np.mean(v)) if v else float("nan")
    ap_ = np.array([gmean(s, "alpha_prom") for s in subs])
    gn = np.array([gmean(s, "ge_norm") for s in subs])

    ok = np.isfinite(x) & np.isfinite(y)
    x, y, c3, c4, ap_, gn = x[ok], y[ok], c3[ok], c4[ok], ap_[ok], gn[ok]
    n = x.size
    res = {"n_subjects": int(n), "gates": {}}
    print(f"{len(smr)} subjects with an SMR predictor, {len(perf)} with an outcome; {n} usable")

    res["gates"]["G1_pass"] = bool(n >= MIN_SUBJECTS)
    thr = 100.0 * (0.5 + 1.645 * np.sqrt(0.25 / TRIALS))
    frac_above = float(np.mean(y > thr))
    med = float(np.median(y))
    g2 = bool(np.ptp(y) > 0 and med > 50.0 and frac_above >= G2_FRACTION)
    res["gates"].update({"G2_median_accuracy": med, "G2_threshold_pct": thr,
                         "G2_frac_above": frac_above, "G2_pass": g2})
    g3 = bool(np.ptp(x) > 0 and np.mean(x > 0) > 0.5)
    res["gates"].update({"G3_smr_median_db": float(np.median(x)), "G3_smr_sd": float(np.std(x)),
                         "G3_frac_positive": float(np.mean(x > 0)), "G3_pass": g3})
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    print(f"G2 outcome    median {med:.2f}%, {frac_above*100:.1f}% above {thr:.2f}%  "
          f"{'PASS' if g2 else 'FAIL'}")
    print(f"G3 predictor  median {np.median(x):.3f} dB, sd {np.std(x):.3f}, "
          f"range [{x.min():.2f}, {x.max():.2f}], {100*np.mean(x>0):.1f}% positive  "
          f"{'PASS' if g3 else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = "ABSENT -- a precondition failed; this is not a null about the predictor."
        json.dump(res, open(a.out, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']}")
        return 1

    rng = np.random.default_rng(SEED)
    r = spearman(x, y)
    lo, hi = boot(x, y, rng, reps=REPS)
    expect = PUBLISHED_R / E101_ATTENUATION
    res["primary"] = {"rho": r, "lo": lo, "hi": hi, "n": int(n),
                      "published_r": PUBLISHED_R, "attenuated_expectation": expect}
    print(f"\nP  spearman(smr_predictor_db, online_accuracy) = {r:+.4f} [{lo:+.4f}, {hi:+.4f}]  n={n}")
    print(f"   Blankertz reported r = {PUBLISHED_R:+.2f} at N=80; attenuated expectation {expect:+.4f}")

    sec = {}
    for name, v in (("smr_C3_db", c3), ("smr_C4_db", c4), ("alpha_prom", ap_), ("ge_norm", gn)):
        m = np.isfinite(v)
        if m.sum() < MIN_SUBJECTS:
            sec[name] = None
            continue
        rr = spearman(v[m], y[m])
        l2, h2 = boot(v[m], y[m], np.random.default_rng(SEED + 1), reps=REPS)
        sec[name] = {"rho": rr, "lo": l2, "hi": h2, "n": int(m.sum())}
        print(f"S  {name:16s} {rr:+.4f} [{l2:+.4f}, {h2:+.4f}]  n={int(m.sum())}")
    res["secondaries"] = sec

    prng = np.random.default_rng(SEED + 2)
    draws = np.array([spearman(x, prng.permutation(y)) for _ in range(PLACEBO_DRAWS)])
    plo, phi = float(np.quantile(draws, .025)), float(np.quantile(draws, .975))
    inside = bool(plo <= r <= phi)
    res["placebo"] = {"p2.5": plo, "p97.5": phi, "real_inside": inside}
    print(f"PLACEBO outcome permuted: [{plo:+.4f}, {phi:+.4f}]  real "
          f"{'INSIDE' if inside else 'OUTSIDE'}")

    seeds = [boot(x, y, np.random.default_rng(SEED + 100 + k), reps=REPS) for k in range(5)]
    n_excl = sum(1 for l2, h2 in seeds if (h2 < 0 or l2 > 0))
    res["seed_stability"] = {"n_seeds": 5, "n_excluding_zero": n_excl}
    print(f"SEED STABILITY  {n_excl}/5 seeds give an interval excluding zero")

    if not np.isfinite(lo):
        res["verdict"] = "ABSENT -- the primary could not be estimated."
    elif inside:
        kind = ("UNDERPOWERED and compatible with the published effect"
                if lo <= expect <= hi else "and it EXCLUDES the published effect")
        res["verdict"] = (
            f"NOT REPLICATED, {kind}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}] lies INSIDE the permutation "
            f"interval [{plo:+.4f}, {phi:+.4f}], so the permutation null reproduces it and no directional "
            f"claim survives, whatever its sign. Blankertz reported {PUBLISHED_R:+.2f} at N=80; the "
            f"attenuated expectation here is {expect:+.4f}. "
            "READ WITH THE REGISTERED ASYMMETRY: the predictor is an INFERENCE from a paywalled paper's "
            "description, so a null is weaker evidence against the published claim than a replication "
            "would have been for it.")
    elif hi < 0:
        res["verdict"] = (f"(a) CONTRADICTED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] excludes zero NEGATIVE "
                          f"at {n_excl}/5 seeds and beats the permutation placebo, against a published "
                          f"{PUBLISHED_R:+.2f}.")
    elif lo > 0:
        res["verdict"] = (f"(c) REPLICATED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}], beating the permutation "
                          f"placebo, against a published {PUBLISHED_R:+.2f} (attenuated {expect:+.4f}). "
                          "Resting EEG DOES predict BCI performance in an independent cohort; ge_norm is "
                          "simply the wrong measure, and Challenge B has a live incumbent to improve on.")
    else:
        kind = ("UNDERPOWERED and compatible with the published effect"
                if lo <= expect <= hi else "and it EXCLUDES the published effect")
        res["verdict"] = (f"(b) NOT REPLICATED, {kind}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}] against a "
                          f"published {PUBLISHED_R:+.2f} and an attenuated {expect:+.4f}. The placebo is "
                          "NOT INFORMATIVE (rule 48).")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(a.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
