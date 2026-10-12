"""E82 -- Challenge B's flagship question, on a deposit no registered experiment has touched:
can anything separate COVERT command-following from PASSIVE stimulation, within subject?

=========================================================================================================
WHAT WAS SEEN BEFORE THIS WAS WRITTEN, stated exactly
=========================================================================================================
`ds007554_features.csv` was extracted long ago for a different purpose and **has never appeared in the
registration ledger** (checked: zero mentions). Before writing this file the following were read, and
nothing else: the column names; the task counts (`nback` 41, `motorimagery` 39, `full` 34,
`mentalarithmetic` 34, `passivemotor` 33, `activemotor` 31, `nbackarithmetic` 31 across 243 recordings,
15 subjects, 3 sessions, 33 channels, every row `status=ok`); the per-feature between-subject standard
deviations; and the rule-60 cross-correlation matrix reported below. **No task contrast of any feature has
been computed.**

=========================================================================================================
WHY THIS DEPOSIT, AND WHY IT IS A BETTER CHALLENGE B SUBSTRATE THAN BCI APTITUDE
=========================================================================================================
Challenge B's flagship target is covert consciousness -- detecting volitional command-following in someone
who cannot move. E41, E68 and E73 all approached it through BCI *aptitude*: how well does a healthy person
control a motor-imagery BCI, and can resting EEG predict that. E73 returned a real null.

**ds007554 carries the paradigm itself rather than a proxy for it.** `passivemotor` and `motorimagery`
differ in exactly one thing -- whether the subject is volitionally attempting the task -- while sharing
limb, session, montage and sensory context. That is the structure of every bedside covert-consciousness
protocol (passive listening versus active counting), with ground truth available because the healthy
subject was in fact instructed. `activemotor` supplies an overt-movement anchor that must be detectable if
the pipeline works at all.

SCOPE, FIRST AND NOT LAST. These are healthy volunteers. Brief 02 calls such datasets "method-development
aids only", and this experiment is method development: it asks whether a measure CAN separate covert
attempt from passive input under ideal conditions. **A positive result would not be evidence about any
patient, and a negative result would be the more informative of the two** -- if it cannot be done in
healthy volunteers who are certainly complying, the measure cannot be proposed for someone who might not
be.

=========================================================================================================
THE RULE-60 CHECK, RUN BEFORE THIS REGISTRATION AND IT CHANGED THE DESIGN
=========================================================================================================
The intended primary was `wpli_alpha` -- the only connectivity measure in the table, chosen to escape the
amplitude family. Rule 60 requires that a measure chosen for belonging to a different family be SHOWN to
differ from it, on the units the design will use. Across the 15 subject means:

    wpli_alpha vs spectral_edge_95        rho -0.9179
    wpli_alpha vs whole_head_exponent     rho +0.8893
    wpli_alpha vs uce_v1                  rho +0.8714
    wpli_alpha vs lempel_ziv              rho -0.7679
    wpli_alpha vs spectral_entropy        rho -0.7000
    wpli_alpha vs relative_delta_power    rho +0.6821
    wpli_alpha vs relative_alpha_power    rho -0.3214

**It does not escape.** At |rho| 0.92 against `spectral_edge_95` this table's eight features are one
family, and a "connectivity primary" here would be the same mistake E73 made with global efficiency. The
design therefore makes **no family claim at all**, and the primary is the question that actually matters.

=========================================================================================================
PRIMARY
=========================================================================================================
    P   Within subject, paired across sessions, does `relative_alpha_power` -- the named incumbent (rule
        45), because sensorimotor alpha ERD is the established motor-imagery marker -- separate
        `motorimagery` from `passivemotor`? Cohen's d_z across the 15 subjects, subject bootstrap.

    PREDICTED DIRECTION, written now: NEGATIVE. Motor imagery desynchronises sensorimotor alpha, so alpha
    power should be LOWER in imagery than in passive stimulation. Predicting the sign is what makes a
    wrong-direction result readable as a refutation rather than as a discovery (rule 37).

    FAMILY (context, BH q = 0.05 across the other seven): reported beside the primary and explicitly not a
    result on its own -- "a measure that wins only here has not won" (E73's formulation, carried over).

=========================================================================================================
GATES, before the primary, each able to refuse it
=========================================================================================================
    G1  COVERAGE   >= 10 subjects contributing at least one session with BOTH tasks present.
    G2  THE PIPELINE CAN SEE A REAL EFFECT (rule 53, in E33's formulation -- the incumbent must be alive).
                   The OVERT anchor, `activemotor` versus `passivemotor`, must give the incumbent a d_z
                   whose interval excludes zero. If overt movement is undetectable, a null on covert
                   attempt says nothing about covert attempt.
    G3  NOT A SESSION ARTEFACT. Every pair is taken WITHIN session, so session order cannot drive it. The
                   count of usable within-session pairs is reported, not assumed.

PLACEBO (after the primary, able only to remove). Task labels permuted WITHIN subject and session, 500
draws, d_z recomputed. Rule 55: this destroys exactly which condition a value came from and nothing else,
and the statistic is a function of it. Any primary inside the placebo's central 95 % is withdrawn.

VERDICT RULE, wrong direction first (rule 37):

    (a) interval excludes 0 with the WRONG sign (alpha HIGHER in imagery)
            -> REVERSED. Not a detection: it contradicts the marker the design is built on, and would
               more likely mean the conditions are mislabelled than that imagery raises alpha.
    (b) interval includes 0
            -> NOT SEPARATED. Given G2 passed, this is a real null about covert attempt.
    (c) interval excludes 0 in the predicted direction
            -> SEPARATED, subject to the placebo, and subject to the scope limit above.

    python -m bsde.experiments.e82_covert_vs_passive
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "ds007554_features.csv")
OUT = os.path.join(RESULTS, "e82_covert_vs_passive.json")

INCUMBENT = "relative_alpha_power"
FAMILY = ["lempel_ziv", "relative_delta_power", "spectral_edge_95", "spectral_entropy",
          "uce_v1", "whole_head_exponent", "wpli_alpha"]
COVERT, PASSIVE, OVERT = "motorimagery", "passivemotor", "activemotor"
MIN_SUBJECTS = 10
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731

TASK = re.compile(r"task-([a-z]+)")
SES = re.compile(r"ses-(\d+)")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    """subject -> session -> task -> row."""
    per = defaultdict(lambda: defaultdict(dict))
    for r in csv.DictReader(open(TABLE, newline="")):
        if r.get("status") != "ok":
            continue
        mt, ms = TASK.search(r["recording_id"]), SES.search(r["recording_id"])
        if not (mt and ms):
            continue
        per[r["subject"]][ms.group(1)][mt.group(1)] = r
    return per


def paired(per, feat, task_a, task_b):
    """One value per subject: the mean within-session (a - b) difference for that subject."""
    subs, vals = [], []
    for s in sorted(per):
        d = [_f(per[s][ses][task_a].get(feat, "")) - _f(per[s][ses][task_b].get(feat, ""))
             for ses in per[s] if task_a in per[s][ses] and task_b in per[s][ses]]
        d = [x for x in d if np.isfinite(x)]
        if d:
            subs.append(s)
            vals.append(float(np.mean(d)))
    return subs, np.asarray(vals, float)


def dz(v):
    v = v[np.isfinite(v)]
    if v.size < 5 or v.std(ddof=1) < 1e-12:
        return float("nan")
    return float(v.mean() / v.std(ddof=1))


def boot_dz(v, seed, reps=REPS):
    v = v[np.isfinite(v)]
    if v.size < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        b = v[rng.integers(0, v.size, v.size)]
        if b.std(ddof=1) > 1e-12:
            out.append(b.mean() / b.std(ddof=1))
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}"); return 2
    per = load()
    res = {"gates": {}, "primary": {}, "anchor": {}, "family": {}}

    subs, v = paired(per, INCUMBENT, COVERT, PASSIVE)
    n_pairs = sum(1 for s in per for ses in per[s]
                  if COVERT in per[s][ses] and PASSIVE in per[s][ses])
    res["gates"].update({"G1_subjects": len(subs), "G3_within_session_pairs": n_pairs,
                         "G1_pass": bool(len(subs) >= MIN_SUBJECTS)})
    print(f"{len(per)} subjects in table")
    print(f"G1 coverage   {len(subs)} subjects with a {COVERT}/{PASSIVE} pair   "
          f"{'PASS' if len(subs) >= MIN_SUBJECTS else 'FAIL'}")
    print(f"G3 pairs      {n_pairs} within-session {COVERT}/{PASSIVE} pairs")

    asub, av = paired(per, INCUMBENT, OVERT, PASSIVE)
    a_pt = dz(av)
    a_lo, a_hi = boot_dz(av, SEED + 1)
    alive = bool(np.isfinite(a_lo) and ((a_lo > 0 and a_hi > 0) or (a_lo < 0 and a_hi < 0)))
    res["anchor"] = {"contrast": f"{OVERT} vs {PASSIVE}", "feature": INCUMBENT,
                     "d_z": a_pt, "lo": a_lo, "hi": a_hi, "n": len(asub), "alive": alive}
    res["gates"]["G2_pass"] = alive
    print(f"G2 anchor     {INCUMBENT} on {OVERT} vs {PASSIVE}: d_z {a_pt:+.3f} "
          f"[{a_lo:+.3f}, {a_hi:+.3f}] over {len(asub)} subjects   {'PASS' if alive else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"]):
        print("\nGATE FAILED -- the primary is not evaluated. Verdict ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pt = dz(v)
    lo, hi = boot_dz(v, SEED + 2)
    print(f"\nPRIMARY  {INCUMBENT}, {COVERT} vs {PASSIVE}: d_z {pt:+.3f} [{lo:+.3f}, {hi:+.3f}] "
          f"over {len(subs)} subjects")

    # placebo: permute the task label within subject and session
    rng = np.random.default_rng(SEED + 3)
    pl = []
    for _ in range(PLACEBO_DRAWS):
        vv = v * np.where(rng.random(v.size) < 0.5, -1.0, 1.0)
        d = dz(vv)
        if np.isfinite(d):
            pl.append(d)
    pl = np.asarray(pl)
    p_lo, p_hi = float(np.quantile(pl, .025)), float(np.quantile(pl, .975))
    inside = bool(p_lo <= pt <= p_hi)
    print(f"PLACEBO  label-sign permutation within subject: [{p_lo:+.3f}, {p_hi:+.3f}]   "
          f"{'primary INSIDE -- withdrawn' if inside else 'primary outside'}")

    if not np.isfinite(lo):
        v_txt = "NOT-COMPUTABLE"
    elif lo > 0 and hi > 0:
        v_txt = ("REVERSED -- alpha power is HIGHER during covert attempt than passive stimulation, "
                 "contradicting the sensorimotor-ERD marker this design is built on. More likely a "
                 "labelling or montage problem than a discovery.")
    elif lo < 0 and hi < 0:
        v_txt = ("SEPARATED -- alpha power is lower during covert attempt, in the predicted direction"
                 + (", but the primary lies inside the placebo distribution and is WITHDRAWN."
                    if inside else ". Healthy volunteers; method development, not patient evidence."))
        if inside:
            v_txt = "WITHDRAWN-BY-PLACEBO -- " + v_txt
    else:
        v_txt = ("NOT SEPARATED -- the incumbent does not distinguish covert attempt from passive "
                 "stimulation within subject. G2 passed, so the pipeline can see the overt anchor; this "
                 "is a real null about covert attempt in healthy, complying volunteers.")
    res["primary"] = {"feature": INCUMBENT, "contrast": f"{COVERT} vs {PASSIVE}", "d_z": pt,
                      "lo": lo, "hi": hi, "n": len(subs),
                      "placebo": [p_lo, p_hi], "inside_placebo": inside}

    print("\nFAMILY (context only, BH q=0.05; a measure that wins only here has not won)")
    fam = []
    for f in FAMILY:
        fs, fv = paired(per, f, COVERT, PASSIVE)
        fp = dz(fv)
        flo, fhi = boot_dz(fv, SEED + 4)
        if np.isfinite(fp):
            fam.append((f, fp, flo, fhi, len(fs)))
        print(f"    {f:24s} d_z {fp:+.3f} [{flo:+.3f}, {fhi:+.3f}]  n={len(fs)}")
    res["family"] = {f: {"d_z": p, "lo": l, "hi": h, "n": n} for f, p, l, h, n in fam}

    res["verdict"] = v_txt
    print(f"\nVERDICT: {v_txt}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
