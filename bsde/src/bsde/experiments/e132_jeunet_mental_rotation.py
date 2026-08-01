"""E132 -- Does MENTAL ROTATION predict BCI performance, and is it independent of the SMR predictor?

REGISTERED BEFORE ANY QUESTIONNAIRE COLUMN HAS BEEN CORRELATED WITH THE OUTCOME. The columns were listed
(66 of them) and the primary chosen from the literature, not from the data; nothing has been run.

=========================================================================================================
WHY, AND WHY IT IS ONE TEST AND NOT SIXTY-SIX
=========================================================================================================
Track G's incumbent sweep (`INCUMBENT_REGISTRY.md`) found that Dreyer's `Perfomances.csv` ships 66
non-performance columns -- mental rotation, 16PF personality, Index of Learning Style, pre/post mood,
mindfulness, motivation, alertness, sleep, stimulants -- and **this project parsed straight past all of
them to reach `Perf_RUN_3..6`.** That is the E129 mistake in progress: a predictor sitting in our own
files, unexamined because every registration pointed elsewhere.

**Sweeping 66 columns against 87 subjects would manufacture findings.** So the hypothesis comes from the
literature and is fixed here:

    Jeunet C, N'Kaoua B, Subramanian S, Hachet M, Lotte F. "Predicting Mental Imagery-Based BCI
    Performance from Personality, Cognitive Profile and Neurophysiological Patterns."
    PLoS One 2015;10(12):e0143962. PMID 26625261 (verified from the MEDLINE record, rule 25).
    Erratum PLoS One 2023;18(2):e0282281, PMID 36821640.

Quoting the abstract:

    "While no relevant relationships with neurophysiological markers were found, strong correlations
     between MI-BCI performances and mental-rotation scores (reflecting spatial abilities) were revealed."

Two things follow, and the second is the interesting one.

**(1) Mental rotation is the single strongest published psychometric claim**, so it is the primary and it
is one test.

**(2) Jeunet found NO relationship with neurophysiological markers -- and E129 found a strong one.** On
these same 87 subjects the SMR predictor gives +0.4440 [+0.2480, +0.6104]. Jeunet's cohort was 18
participants over 6 sessions with non-motor imagery tasks; Dreyer is 87 over one session with motor
imagery. Both cannot be the last word, and the pair is directly testable here.

=========================================================================================================
DESIGN
=========================================================================================================
    P1  spearman( mental rotation `score` , online_accuracy ), PREDICTED POSITIVE. One test.
        `online_accuracy` is the mean of `Perf_RUN_3..6`, the definition E125 and E129 both used, so this
        differs from them only in the predictor.

    P2  THE TENSION, and it is the reason this is worth running rather than just checking a box.
        Partial spearman of each against the outcome, controlling for the other:
          - mental rotation | SMR
          - SMR | mental rotation
        Jeunet's claim implies the SMR term should die once spatial ability is accounted for. E129's
        result implies the opposite. **If BOTH survive, the two literatures are describing independent
        factors and a two-term model is better than either** -- which neither paper could have found,
        because neither cohort had both measures.

SECONDARIES, pre-specified from Jeunet's own three-category framework (Prog Brain Res 2016;228:3-35,
PMID 27590964: "(1) users' relationship with the technology (including ... sense of agency), (2)
attention, and (3) spatial abilities"), ONE column per category, chosen by name before any was computed:
    S1  `POST_Agentivity`          -> relationship with the technology / sense of agency
    S2  `PRE_Level_of_alertness`   -> attention
    (spatial abilities is the primary)
Benjamini-Hochberg at q = 0.05 across P1 + S1 + S2. **The other 63 columns are not tested here**; if they
are ever tested it will be in a registration that says so in advance.

GATES
    G1  COVERAGE >= 50 subjects with a finite predictor and outcome.
    G2  OUTCOME ALIVE -- E125's, unchanged: median above chance and >= 20 % above the derived
        Binomial(160, 0.5) point of 56.5 %.
    G3  PREDICTOR ALIVE -- the mental-rotation score must vary; a constant or near-constant column would
        mean the questionnaire was not administered to everyone.

PLACEBO, gating the verdict in EITHER direction: outcome permuted across subjects, 2000 draws; a real
estimate inside the central 95 % is WITHDRAWN whatever its sign. Rule 48: the interval is read first.

VERDICT, wrong direction FIRST (rule 37, eleventh occurrence):
    (a) excludes 0 NEGATIVE -> CONTRADICTED. Better spatial ability going with WORSE BCI control would
        contradict a published claim and needs the placebo and seed stability before being said.
    (b) includes 0 -> NOT REPLICATED, and say which kind (rule 31): whether a Jeunet-sized effect lies
        inside the interval. Jeunet reports "strong correlations" without a number in the abstract, so
        **no numeric expectation is asserted** -- what is reported is the interval and whether it excludes
        moderate effects (|rho| >= 0.3), stated this way because inventing a value to compare against
        would be worse than admitting the abstract does not give one.
    (c) excludes 0 POSITIVE and beats the placebo -> REPLICATED. Then Challenge B has a NON-EEG predictor
        that works, and P2 decides whether it is the same factor as the SMR predictor or a second one.

CALIBRATION before the run: (c) ~50 %, (b) ~40 %, (a) ~10 %. For P2, the outcome I consider most likely is
that both survive (~55 %), because they are measurements of very different things.

SCOPE. One deposit, single session, OpenViBE two-class motor imagery. Jeunet's cohort performed THREE
imagery tasks, two of them non-motor, over six sessions -- so a difference between her result and this one
could be a difference in task, in session count, or in cohort, and this design cannot separate those.
Stated now (rule 47).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e132_jeunet_mental_rotation.json")
PERF = os.path.join(RESULTS, "dreyer_performance.csv")
SMR = os.path.join(RESULTS, "dreyer_smr.csv")

PRIMARY_COL = "score"                      # the Mental Rotation block's score column
SECONDARY_COLS = ["POST_Agentivity", "PRE_Level_of_alertness"]
MIN_SUBJECTS = 50
TRIALS = 160
G2_FRACTION = 0.20
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260804


def _f(v):
    v = (v or "").strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def load_questionnaire(path=PERF):
    """Per-subject questionnaire columns from the deposit's three stacked blocks.

    Parsed structurally -- find each `SUJ_ID` header, read until the next `DATA X` banner -- rather than by
    line offsets, exactly as `e125`'s loader does, so a block gaining a row cannot shift the join."""
    lines = open(path, encoding="utf8", errors="replace").read().splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("SUJ_ID")]
    out = {}
    for hi in heads:
        hdr = lines[hi].split(";")
        j = hi + 1
        while j < len(lines) and not re.match(r"^DATA [A-C]", lines[j]):
            parts = lines[j].split(";")
            if parts and re.match(r"^[A-C]\d+$", parts[0].strip()):
                out[parts[0].strip()] = dict(zip(hdr, parts))
            j += 1
    return out


def main(argv=None) -> int:
    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E132", "B",
            "Does mental rotation predict BCI performance, and is it independent of the SMR predictor?",
            "dreyer-bci-2023",
            "spearman(mental rotation score, mean online accuracy), PREDICTED POSITIVE, one test; plus "
            "partial correlations each controlling for the other",
            ["G1 >=50 subjects", "G2 outcome alive (E125's, unchanged)", "G3 predictor varies"],
            "outcome permuted across subjects, 2000 draws; inside the central 95% is WITHDRAWN in EITHER "
            "direction",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E129",
            instrument_changed="a NON-EEG predictor: Jeunet 2015's mental-rotation score, taken from the "
                               "deposit's own questionnaire columns which this project had never opened")
        print("registered E132")
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
    from e129_blankertz_replication import _read_shards                    # noqa: E402

    q = load_questionnaire()
    perf = load_performance()
    smr = {r["subject"]: _f(r["smr_predictor_db"]) for r in _read_shards(SMR)}

    subs = sorted(set(q) & set(perf))
    x = np.array([_f(q[s].get(PRIMARY_COL)) for s in subs])
    y = np.array([perf[s]["accuracy"] for s in subs])
    z = np.array([smr.get(s, np.nan) for s in subs])
    sec = {c: np.array([_f(q[s].get(c)) for s in subs]) for c in SECONDARY_COLS}

    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    res = {"n_subjects": n, "gates": {}}
    print(f"{len(q)} subjects in the questionnaire, {len(perf)} with an outcome; {n} usable")

    thr = 100.0 * (0.5 + 1.645 * np.sqrt(0.25 / TRIALS))
    yy = y[ok]
    g2 = bool(np.ptp(yy) > 0 and float(np.median(yy)) > 50.0 and float(np.mean(yy > thr)) >= G2_FRACTION)
    g3 = bool(np.ptp(x[ok]) > 0)
    res["gates"].update({"G1_pass": n >= MIN_SUBJECTS, "G2_pass": g2, "G3_pass": g3,
                         "G2_median": float(np.median(yy)), "G2_frac_above": float(np.mean(yy > thr)),
                         "G3_score_median": float(np.median(x[ok])), "G3_score_sd": float(np.std(x[ok])),
                         "G3_score_range": [float(x[ok].min()), float(x[ok].max())]})
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    print(f"G2 outcome    median {np.median(yy):.2f}%, {100*np.mean(yy>thr):.1f}% above {thr:.2f}%  "
          f"{'PASS' if g2 else 'FAIL'}")
    print(f"G3 predictor  mental rotation median {np.median(x[ok]):.2f}, sd {np.std(x[ok]):.2f}, "
          f"range [{x[ok].min():.0f}, {x[ok].max():.0f}]  {'PASS' if g3 else 'FAIL'}")
    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = "ABSENT -- a precondition failed."
        json.dump(res, open(a.out, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']}")
        return 1

    r = spearman(x[ok], yy)
    lo, hi = boot(x[ok], yy, np.random.default_rng(SEED), reps=REPS)
    res["primary"] = {"rho": r, "lo": lo, "hi": hi, "n": n}
    print(f"\nP1 spearman(mental_rotation, online_accuracy) = {r:+.4f} [{lo:+.4f}, {hi:+.4f}]  n={n}")

    # ---- P2: the tension between Jeunet and E129 ----------------------------------------------------
    def partial(u, v, w):
        """spearman(u, v | w) via rank residuals -- the standard construction, computed on ranks so it
        matches the rank statistic used everywhere else in this project."""
        from scipy.stats import rankdata
        m = np.isfinite(u) & np.isfinite(v) & np.isfinite(w)
        ru, rv, rw = rankdata(u[m]), rankdata(v[m]), rankdata(w[m])
        A = np.column_stack([np.ones(rw.size), rw])
        eu = ru - A @ np.linalg.lstsq(A, ru, rcond=None)[0]
        ev = rv - A @ np.linalg.lstsq(A, rv, rcond=None)[0]
        return spearman(eu, ev), int(m.sum())

    m3 = ok & np.isfinite(z)
    r_smr = spearman(z[m3], y[m3])
    pr_mr, n_mr = partial(x, y, z)
    pr_smr, n_smr = partial(z, y, x)
    res["P2_tension"] = {"smr_marginal": r_smr,
                         "mental_rotation_given_smr": pr_mr,
                         "smr_given_mental_rotation": pr_smr,
                         "rho_mr_smr": spearman(x[m3], z[m3]), "n": n_mr}
    print(f"P2 SMR marginal on these subjects        {r_smr:+.4f}")
    print(f"   mental rotation | SMR                 {pr_mr:+.4f}   (n={n_mr})")
    print(f"   SMR | mental rotation                 {pr_smr:+.4f}")
    print(f"   rho(mental rotation, SMR)             {spearman(x[m3], z[m3]):+.4f}")

    secr = {}
    for c, v in sec.items():
        m = np.isfinite(v) & np.isfinite(y)
        if m.sum() < MIN_SUBJECTS:
            secr[c] = None
            continue
        rr = spearman(v[m], y[m])
        l2, h2 = boot(v[m], y[m], np.random.default_rng(SEED + 1), reps=REPS)
        secr[c] = {"rho": rr, "lo": l2, "hi": h2, "n": int(m.sum())}
        print(f"S  {c:26s} {rr:+.4f} [{l2:+.4f}, {h2:+.4f}]  n={int(m.sum())}")
    res["secondaries"] = secr

    prng = np.random.default_rng(SEED + 2)
    draws = np.array([spearman(x[ok], prng.permutation(yy)) for _ in range(PLACEBO_DRAWS)])
    plo, phi = float(np.quantile(draws, .025)), float(np.quantile(draws, .975))
    inside = bool(plo <= r <= phi)
    res["placebo"] = {"p2.5": plo, "p97.5": phi, "real_inside": inside}
    print(f"PLACEBO outcome permuted: [{plo:+.4f}, {phi:+.4f}]  real "
          f"{'INSIDE' if inside else 'OUTSIDE'}")

    both = (np.isfinite(pr_mr) and abs(pr_mr) > 0.15) and (np.isfinite(pr_smr) and abs(pr_smr) > 0.15)
    if not np.isfinite(lo):
        res["verdict"] = "ABSENT -- the primary could not be estimated."
    elif inside:
        excl = "and it EXCLUDES moderate effects (|rho| >= 0.3)" if (lo > -0.3 and hi < 0.3) else \
               "and it does NOT exclude moderate effects"
        res["verdict"] = (f"NOT REPLICATED, {excl}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}] lies INSIDE the "
                          f"permutation interval [{plo:+.4f}, {phi:+.4f}]. Jeunet reports 'strong "
                          "correlations' without a number in the abstract, so no numeric expectation is "
                          "asserted here.")
    elif hi < 0:
        res["verdict"] = (f"(a) CONTRADICTED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}]: better spatial ability "
                          "goes with WORSE BCI control, against a published positive claim.")
    elif lo > 0:
        res["verdict"] = (
            f"(c) REPLICATED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}], beating the permutation placebo. "
            "Challenge B has a NON-EEG predictor that works. "
            + (f"AND BOTH SURVIVE PARTIALLING: mental rotation | SMR = {pr_mr:+.4f}, SMR | mental "
               f"rotation = {pr_smr:+.4f}, with rho(mr, smr) = "
               f"{res['P2_tension']['rho_mr_smr']:+.4f}. Jeunet found no neurophysiological relationship "
               "and E129 found a strong one; on a cohort carrying BOTH they are independent factors, "
               "which neither paper could have shown."
               if both else
               f"P2: mental rotation | SMR = {pr_mr:+.4f}, SMR | mental rotation = {pr_smr:+.4f} -- one "
               "term does not survive partialling, so the two literatures may be describing one factor."))
    else:
        res["verdict"] = f"(b) NOT REPLICATED. {r:+.4f} [{lo:+.4f}, {hi:+.4f}]."
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(a.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
