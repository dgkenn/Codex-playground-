"""E83 -- E82 repeated with the instrument its own gate said was missing: cue-locked sensorimotor ERD.

REGISTERED BEFORE `ds007554_erd.csv` EXISTS beyond the three smoke-test runs disclosed below.

=========================================================================================================
THE SMOKE TEST WAS RUN ON REAL LABELS, WHICH RULE 26 FORBIDS. WHAT WAS SEEN, AND WHAT IT COSTS.
=========================================================================================================
The extractor was smoke-tested on **sub-001 ses-01**, all three tasks, and the three values were printed:
`activemotor` +0.0469, `motorimagery` +0.0892, `passivemotor` +0.0958. That is one subject of fifteen and
it is the anchor contrast's direction. Rule 26 exists precisely to stop this -- a smoke test belongs on
permuted labels -- and it was not followed.

**The remedy is applied here rather than argued away: `sub-001` is EXCLUDED from this experiment**, and is
named in the code as the burned subject. The analysis runs on the remaining subjects only. The exclusion
is declared before any of their values exist, so blindness is intact for every subject that contributes.

=========================================================================================================
THE ONE INSTRUMENT CHANGE (rule 58: one repair, with the reason written down)
=========================================================================================================
E82's gate G2 failed: the OVERT anchor `activemotor` versus `passivemotor` gave the incumbent
`relative_alpha_power` d_z = +0.393 [-0.028, +0.934] -- interval including zero, sign wrong for
sensorimotor ERD -- so the covert primary was never evaluated. The diagnosis was the reduction:
`ds007554_features.csv` holds one whole-run summary median-reduced across 33 channels, and alpha ERD is
transient, cue-locked and focal.

**Changed: whole-run median over all channels -> per-trial log ratio of post-cue to pre-cue alpha power on
the sensorimotor strip.** Nothing else moves -- same deposit, same three tasks, same subjects, same
sessions, same incumbent, same primary question, same gates. `PRE = [-2.0, -0.5] s`, `POST = [+0.5, +2.5]
s`, alpha 8-13 Hz, channels C1 C2 C3 C4 Cz FC3 FC4 CP1 CP2 (verified present in the deposit's own
`channels.tsv`, not recalled).

=========================================================================================================
PRIMARY, GATES, PLACEBO
=========================================================================================================
    P   `erd_sm`, within subject and session, `motorimagery` minus `passivemotor`; Cohen's d_z across
        subjects with a subject bootstrap.

    PREDICTED DIRECTION, written now: **NEGATIVE** -- covert motor attempt desynchronises sensorimotor
    alpha relative to passive input, so the post/pre log ratio is lower for imagery.

    G1  COVERAGE   >= 8 contributing subjects (of the 14 available after the sub-001 exclusion).
    G2  THE ANCHOR MUST BE ALIVE (rule 53 / E33, carried over from E82 unchanged). `activemotor` minus
        `passivemotor` on `erd_sm` must give an interval excluding zero, in the NEGATIVE direction. A
        wrong-signed anchor fails the gate as surely as a null one: if overt movement does not
        desynchronise sensorimotor alpha here, this instrument is not measuring ERD and the covert
        question cannot be asked with it.
    G3  SPECIFICITY, evaluated after the primary and able only to remove. `erd_wholehead` uses identical
        timing on every channel. If the whole-head contrast matches the sensorimotor one, the effect is
        global arousal rather than a sensorimotor signature, and the primary is reported
        NOT-SENSORIMOTOR-SPECIFIC rather than as a detection. This is the objection a bilateral ERD
        invites and it is built in rather than answered afterwards.

    PLACEBO. Trial-to-condition assignment is destroyed by permuting the sign of each subject's paired
    difference, 500 draws (rule 55: the statistic is a function of which condition a value came from, and
    that is exactly what the permutation destroys). A primary inside the central 95 % is withdrawn.

VERDICT RULE, wrong direction first:

    (a) interval excludes 0 POSITIVE -- REVERSED. Covert attempt would be *synchronising* sensorimotor
        alpha relative to passive input, contradicting the marker; report as a refutation, not a finding.
    (b) interval includes 0 -- NOT SEPARATED. With G2 passed this is a real null about covert attempt.
    (c) interval excludes 0 NEGATIVE -- SEPARATED, subject to G3 and the placebo.

SCOPE, first and not last: healthy volunteers who were instructed and are presumed compliant. Brief 02
calls such deposits method-development aids. A positive is not patient evidence; **a negative is the more
informative outcome**, because a measure that cannot do this under ideal conditions cannot be proposed for
someone who may not be attempting at all.

    python -m bsde.experiments.e83_covert_vs_passive_erd
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "ds007554_erd.csv")
OUT = os.path.join(RESULTS, "e83_covert_vs_passive_erd.json")

BURNED = {"sub-001"}          # smoke-tested on real labels; excluded, see the docstring
COVERT, PASSIVE, OVERT = "motorimagery", "passivemotor", "activemotor"
MIN_SUBJECTS = 8
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    per = defaultdict(lambda: defaultdict(dict))
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["subject"] in BURNED:
            continue
        per[r["subject"]][r["session"]][r["task"]] = r
    return per


def paired(per, col, a, b):
    subs, vals = [], []
    for s in sorted(per):
        d = [_f(per[s][ses][a].get(col, "")) - _f(per[s][ses][b].get(col, ""))
             for ses in per[s] if a in per[s][ses] and b in per[s][ses]]
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
    out = [b.mean() / b.std(ddof=1) for b in
           (v[rng.integers(0, v.size, v.size)] for _ in range(reps)) if b.std(ddof=1) > 1e-12]
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}"); return 2
    per = load()
    res = {"gates": {}, "excluded": sorted(BURNED)}
    print(f"{len(per)} subjects after excluding {sorted(BURNED)}")

    asub, av = paired(per, "erd_sm", OVERT, PASSIVE)
    a_pt = dz(av)
    a_lo, a_hi = boot_dz(av, SEED + 1)
    alive = bool(np.isfinite(a_hi) and a_hi < 0)          # must exclude zero AND be negative
    res["anchor"] = {"contrast": f"{OVERT} - {PASSIVE}", "d_z": a_pt, "lo": a_lo, "hi": a_hi,
                     "n": len(asub), "alive": alive}
    print(f"G2 anchor     erd_sm {OVERT} - {PASSIVE}: d_z {a_pt:+.3f} [{a_lo:+.3f}, {a_hi:+.3f}] "
          f"over {len(asub)} subjects   {'PASS' if alive else 'FAIL'}")

    subs, v = paired(per, "erd_sm", COVERT, PASSIVE)
    res["gates"].update({"G1_subjects": len(subs), "G1_pass": bool(len(subs) >= MIN_SUBJECTS),
                         "G2_pass": alive})
    print(f"G1 coverage   {len(subs)} subjects   "
          f"{'PASS' if len(subs) >= MIN_SUBJECTS else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and alive):
        print("\nGATE FAILED -- the primary is not evaluated. Verdict ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pt = dz(v)
    lo, hi = boot_dz(v, SEED + 2)
    print(f"\nPRIMARY  erd_sm {COVERT} - {PASSIVE}: d_z {pt:+.3f} [{lo:+.3f}, {hi:+.3f}] "
          f"over {len(subs)} subjects")

    rng = np.random.default_rng(SEED + 3)
    pl = np.sort([d for d in
                  (dz(v * np.where(rng.random(v.size) < 0.5, -1.0, 1.0)) for _ in range(PLACEBO_DRAWS))
                  if np.isfinite(d)])
    p_lo, p_hi = float(np.quantile(pl, .025)), float(np.quantile(pl, .975))
    inside = bool(p_lo <= pt <= p_hi)
    print(f"PLACEBO  sign permutation: [{p_lo:+.3f}, {p_hi:+.3f}]   "
          f"{'primary INSIDE -- withdrawn' if inside else 'primary outside'}")

    wsub, wv = paired(per, "erd_wholehead", COVERT, PASSIVE)
    w_pt = dz(wv)
    w_lo, w_hi = boot_dz(wv, SEED + 4)
    specific = bool(np.isfinite(w_hi) and not (w_lo < 0 and w_hi < 0))
    res["specificity"] = {"whole_head_d_z": w_pt, "lo": w_lo, "hi": w_hi, "n": len(wsub),
                          "sensorimotor_specific": specific}
    print(f"G3 specificity erd_wholehead {COVERT} - {PASSIVE}: d_z {w_pt:+.3f} "
          f"[{w_lo:+.3f}, {w_hi:+.3f}]   "
          f"{'sensorimotor-specific' if specific else 'ALSO GLOBAL -- not specific'}")

    if not np.isfinite(lo):
        verdict = "NOT-COMPUTABLE"
    elif lo > 0 and hi > 0:
        verdict = ("REVERSED -- covert attempt SYNCHRONISES sensorimotor alpha relative to passive input, "
                   "contradicting the marker this design is built on. A refutation, not a finding.")
    elif lo < 0 and hi < 0:
        if inside:
            verdict = "WITHDRAWN-BY-PLACEBO -- the primary lies inside the sign-permutation distribution."
        elif not specific:
            verdict = ("NOT-SENSORIMOTOR-SPECIFIC -- the sensorimotor contrast is matched by the "
                       "whole-head one, so this is global arousal rather than a motor signature.")
        else:
            verdict = ("SEPARATED -- covert attempt desynchronises sensorimotor alpha relative to passive "
                       "stimulation, in the predicted direction, specific to the sensorimotor strip and "
                       "outside the placebo. Healthy compliant volunteers: method development, not "
                       "patient evidence.")
    else:
        verdict = ("NOT SEPARATED -- with the overt anchor alive, cue-locked sensorimotor ERD does not "
                   "distinguish covert attempt from passive stimulation. A real null about covert "
                   "attempt, and the more informative outcome of the two.")

    res["primary"] = {"d_z": pt, "lo": lo, "hi": hi, "n": len(subs),
                      "placebo": [p_lo, p_hi], "inside_placebo": inside}
    res["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
