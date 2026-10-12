"""E85 -- the covert-versus-passive question with the statistic the LITERATURE specifies, and a stopping rule.

REGISTERED BEFORE `ds007554_erd_timecourse.csv` EXISTS. **THIRD AND FINAL ATTEMPT AT THIS QUESTION ON THIS
DEPOSIT.** The stopping rule is in this docstring, not in a later decision: if the anchor gate fails again,
ds007554 is CLOSED for the covert-versus-passive contrast and that closure is recorded in the ledger. A
question retried indefinitely with a new statistic each time is a scan wearing three registrations.

=========================================================================================================
WHY A THIRD ATTEMPT IS LEGITIMATE, AND WHAT MAKES IT DIFFERENT FROM THE FIRST TWO
=========================================================================================================
E82 (whole-run median over 33 channels) and E83 (cue-locked, sensorimotor, fixed [+0.5, +2.5] s average)
both failed the same gate: the OVERT anchor `activemotor` minus `passivemotor` could not be detected --
d_z +0.393 [-0.028, +0.934] and +0.271 [-0.190, +0.565], both including zero, both with the wrong sign.

The rule-21 check ran only after the second failure and it explains both, from physiology that was
available before either run. Verified through E-utilities rather than a summariser (rules 25/39):

    PMID 31425038, IEEE Trans Neural Syst Rehabil Eng 2019, "EEG Sensorimotor Correlates of Speed During
    Forearm Passive Movements" -- passive forearm oscillations delivered by a haptic device elicit mu and
    beta ERD, tested as proportional to passive movement speed.

    PMID 27529874, IEEE Trans Neural Syst Rehabil Eng 2017, "EEG Analysis During Active and Assisted
    Repetitive Movements" -- in a 2x2 of volitional intention against robotic assistance, "statistically
    significant ERDs began EARLIER in conditions requiring subject's volitional contribution".

**Passive movement produces ERD of its own, so an active-minus-passive contrast of ERD MAGNITUDE is small
by construction; the published volitional signature is in LATENCY.** ds007554 ships Biodex dynamometer
recordings alongside its EEG, so its `passivemotor` condition is of exactly the robot-assisted kind those
papers describe. Neither prior failure was about the deposit or the epoching.

*(That is what the two abstracts state. The inference that a fixed late-window average of alpha power
cannot express a latency difference is mine, not theirs -- rule 42.)*

=========================================================================================================
THE STATISTIC, fixed before any value exists
=========================================================================================================
`ds007554_erd_timecourse.csv` carries, per run, the mean over trials of log10(alpha power in each 0.25 s
bin / that trial's own pre-cue [-2.0, -0.5] s baseline), from -2 s to +4 s, on the sensorimotor strip.

    EARLY = [0.00, 0.75] s      the window where a volitional ERD should already be under way
    LATE  = [1.50, 3.00] s      the window where the literature says the two conditions converge

    P    `motorimagery` minus `passivemotor`, EARLY window, within session, Cohen's d_z across subjects.
         PREDICTED NEGATIVE: covert attempt desynchronises earlier than passive input.

GATES, before the primary (rule 40):

    G1  COVERAGE      >= 8 contributing subjects, `sub-001` excluded as E83's smoke-test burn.
    G2  ANCHOR ALIVE  `activemotor` minus `passivemotor` in the EARLY window must exclude zero AND be
                      negative. Same requirement as E83, on the new statistic.
    G2b LATENCY SIGNATURE, and this one tests the PREMISE rather than the effect. The anchor's EARLY
                      contrast must be LARGER IN MAGNITUDE than its LATE contrast. If the overt-versus-
                      passive difference is not concentrated early, the latency reading of PMID 27529874
                      does not hold in this deposit, the design's rationale is wrong, and the verdict is
                      ABSENT rather than a null about covert attempt. **A premise gate that can fail is
                      the thing E82 and E83 both lacked.**

PLACEBO (after the primary, able only to remove): sign permutation of each subject's paired difference,
500 draws. A primary inside the central 95 % is withdrawn.

SPECIFICITY IS NOT TESTED HERE AND IS THEREFORE NOT CLAIMED. The time-course table is sensorimotor-only;
no whole-head time course was extracted. `erd_wholehead` in the companion table covers the LATE window
only, so a sensorimotor-specific claim about the EARLY window cannot be made from what exists. If the
primary passes, that control is the first thing a successor owes.

VERDICT, wrong direction first (rule 37):

    (a) interval excludes 0 POSITIVE -> REVERSED. Covert attempt would be synchronising sensorimotor alpha
        earlier than passive input. A refutation of the marker, not a detection.
    (b) interval includes 0            -> NOT SEPARATED. With G2 and G2b passed, a real null about covert
        attempt in healthy, instructed, presumably compliant volunteers -- which is the more informative
        outcome, because a measure that cannot do this under ideal conditions cannot be proposed for
        someone who may not be attempting at all.
    (c) interval excludes 0 NEGATIVE   -> SEPARATED, subject to the placebo and to the missing spatial
        control above. Method development on healthy volunteers; not patient evidence.

    python -m bsde.experiments.e85_covert_erd_latency
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

TABLE = os.path.join(RESULTS, "ds007554_erd_timecourse.csv")
OUT = os.path.join(RESULTS, "e85_covert_erd_latency.json")

BURNED = {"sub-001"}
COVERT, PASSIVE, OVERT = "motorimagery", "passivemotor", "activemotor"
BIN_S, TC_FROM = 0.25, -2.0
EARLY, LATE = (0.00, 0.75), (1.50, 3.00)
MIN_SUBJECTS = 8
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def bins_for(win):
    lo = int(round((win[0] - TC_FROM) / BIN_S))
    hi = int(round((win[1] - TC_FROM) / BIN_S))
    return list(range(lo, hi))


def load():
    per = defaultdict(lambda: defaultdict(dict))
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["subject"] in BURNED:
            continue
        per[r["subject"]][r["session"]][r["task"]] = r
    return per


def window_value(row, idx):
    v = [_f(row.get(f"b{i:02d}", "")) for i in idx]
    v = [x for x in v if np.isfinite(x)]
    return float(np.mean(v)) if v else float("nan")


def paired(per, idx, a, b):
    subs, vals = [], []
    for s in sorted(per):
        d = [window_value(per[s][ses][a], idx) - window_value(per[s][ses][b], idx)
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
    out = sorted(b.mean() / b.std(ddof=1) for b in
                 (v[rng.integers(0, v.size, v.size)] for _ in range(reps)) if b.std(ddof=1) > 1e-12)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    per = load()
    e_idx, l_idx = bins_for(EARLY), bins_for(LATE)
    res = {"gates": {}, "excluded": sorted(BURNED),
           "windows": {"early": EARLY, "late": LATE, "early_bins": e_idx, "late_bins": l_idx}}
    print(f"{len(per)} subjects after excluding {sorted(BURNED)}; "
          f"EARLY bins {e_idx[0]}-{e_idx[-1]}, LATE bins {l_idx[0]}-{l_idx[-1]}")

    asub, av = paired(per, e_idx, OVERT, PASSIVE)
    a_pt = dz(av)
    a_lo, a_hi = boot_dz(av, SEED + 1)
    alive = bool(np.isfinite(a_hi) and a_hi < 0)
    _, alv = paired(per, l_idx, OVERT, PASSIVE)
    l_pt = dz(alv)
    concentrated = bool(np.isfinite(a_pt) and np.isfinite(l_pt) and abs(a_pt) > abs(l_pt))
    res["anchor"] = {"early_d_z": a_pt, "lo": a_lo, "hi": a_hi, "late_d_z": l_pt,
                     "n": len(asub), "alive": alive, "early_larger_than_late": concentrated}
    print(f"G2  anchor EARLY  {OVERT} - {PASSIVE}: d_z {a_pt:+.3f} [{a_lo:+.3f}, {a_hi:+.3f}] "
          f"over {len(asub)} subjects   {'PASS' if alive else 'FAIL'}")
    print(f"G2b latency       anchor LATE d_z {l_pt:+.3f}; |early| > |late| ? "
          f"{'YES' if concentrated else 'NO -- the premise fails'}")

    subs, v = paired(per, e_idx, COVERT, PASSIVE)
    res["gates"].update({"G1_subjects": len(subs), "G1_pass": bool(len(subs) >= MIN_SUBJECTS),
                         "G2_pass": alive, "G2b_pass": concentrated})
    print(f"G1  coverage      {len(subs)} subjects   "
          f"{'PASS' if len(subs) >= MIN_SUBJECTS else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and alive and concentrated):
        why = ("the overt anchor is still undetectable" if not alive else
               "the anchor's effect is not concentrated early, so the latency premise does not hold here"
               if not concentrated else "too few subjects")
        print(f"\nGATE FAILED ({why}) -- the primary is not evaluated. Verdict ABSENT (rule 31).")
        print("STOPPING RULE APPLIES: this was the third and final attempt at the covert-versus-passive "
              "contrast on ds007554. The deposit is CLOSED for this question.")
        res["verdict"] = "GATE-FAILED -- ds007554 CLOSED for covert-versus-passive by the stopping rule"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pt = dz(v)
    lo, hi = boot_dz(v, SEED + 2)
    print(f"\nPRIMARY  EARLY {COVERT} - {PASSIVE}: d_z {pt:+.3f} [{lo:+.3f}, {hi:+.3f}] "
          f"over {len(subs)} subjects")

    rng = np.random.default_rng(SEED + 3)
    pl = np.sort([d for d in
                  (dz(v * np.where(rng.random(v.size) < 0.5, -1.0, 1.0)) for _ in range(PLACEBO_DRAWS))
                  if np.isfinite(d)])
    p_lo, p_hi = float(np.quantile(pl, .025)), float(np.quantile(pl, .975))
    inside = bool(p_lo <= pt <= p_hi)
    print(f"PLACEBO  [{p_lo:+.3f}, {p_hi:+.3f}]   "
          f"{'primary INSIDE -- withdrawn' if inside else 'primary outside'}")

    if not np.isfinite(lo):
        verdict = "NOT-COMPUTABLE"
    elif lo > 0 and hi > 0:
        verdict = ("REVERSED -- covert attempt synchronises sensorimotor alpha earlier than passive "
                   "input, contradicting the marker. A refutation, not a detection.")
    elif lo < 0 and hi < 0:
        verdict = ("WITHDRAWN-BY-PLACEBO" if inside else
                   "SEPARATED -- covert attempt desynchronises sensorimotor alpha earlier than passive "
                   "stimulation, in the predicted direction and outside the placebo. Spatial specificity "
                   "is UNTESTED for this window and is therefore not claimed. Healthy instructed "
                   "volunteers: method development, not patient evidence.")
    else:
        verdict = ("NOT SEPARATED -- with the overt anchor alive AND concentrated early, early-window "
                   "sensorimotor ERD does not distinguish covert attempt from passive stimulation. A "
                   "real null, and the more informative outcome of the two.")

    res["primary"] = {"d_z": pt, "lo": lo, "hi": hi, "n": len(subs),
                      "placebo": [p_lo, p_hi], "inside_placebo": inside}
    res["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
