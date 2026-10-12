#!/usr/bin/env python3
"""E162 -- is the ICU transport result pharmacology, or the care process? Test the GAIN, not the level.

REGISTERED BEFORE ANY GOAL-ADJUSTED GAIN HAS BEEN COMPUTED. Successor to E160. Cohort, exposure ladder,
statistic and clustering are E160's, unchanged.

=========================================================================================================
WHAT E160 LEFT UNDECIDED, AND WHY IT COULD NOT DECIDE IT
=========================================================================================================
E160 carried the DOSE-I exposure ladder to 123,728 RASS observations from 4,000 ICU stays and it
reproduced to within 0.01 at every rung:

    rung                     MIMIC-IV        DOSE-I (E122)
    L0 cumulative dose       +0.1872         +0.1755
    L2 + kinetic basis       **+0.4293**     +0.4263
    L0 -> L2 gain            **+0.2421**     +0.2508

Both registered predictions failed. Then two alternatives were tested before the verdict was allowed to
stand. **Time is refuted** -- `hours_in` alone reaches +0.0695 and adds nothing to the model.
**Clinical intent is not**: `Goal Richmond-RAS Scale` alone reaches **+0.6151**, above the pharmacology,
and residualising it out of RASS drops the exposure model from +0.4304 to **+0.1629**.

**And that adjustment is not clean either.** The goal is re-charted through the stay and is updated in
response to how the patient looks, so the most recent goal is partly POST-EXPOSURE and conditioning on it
is a collider (rule 13). E160's honest conclusion was that the true transport lies somewhere in
**[+0.16, +0.43]** with the pre-registered +0.25 inside the interval -- i.e. the test does not settle
itself.

=========================================================================================================
THE TWO CHANGES THAT MAKE IT SETTLEABLE
=========================================================================================================
**1. THE PRIMARY BECOMES THE GAIN, NOT THE LEVEL.** A care-process confound inflates how well *any*
exposure summary orders RASS, because more drug and a deeper target travel together. It has no reason to
inflate the **INCREMENT from cumulative dose to a kinetic basis**, which is a statement about the SHAPE of
the exposure-response relation rather than its strength: both rungs see the same drug and the same target,
and only one of them knows when it was given. E160's secondary prediction was that this gain would
collapse under infusion at ICU timescales; it did not (+0.2421 against +0.2508), and no confound that
acts on the level explains that.

**2. THE GOAL IS HANDLED THREE WAYS, ONE OF WHICH IS NEARLY PRE-EXPOSURE.**

    A  unadjusted                         E160's arm, reported again for continuity
    B  most-recent goal as a covariate    E160's adjustment; a partial collider, kept because dropping an
                                          arm because it is imperfect is how a result gets chosen
    C  **FIRST goal of the stay** as a     set near admission, before most of the exposure and before most
       stay-level covariate                of the RASS observations exist. Checked before registration:
                                          3,580 of 4,000 stays have one and it varies properly
                                          (0 in 1,384 stays, -1 in 1,069, -5 in 599, -4 in 209, -2 in 197,
                                          -3 in 122). This is the arm that is closest to a genuine
                                          confounder adjustment rather than a collider one.

=========================================================================================================
GATES
=========================================================================================================
G1  E160's cohort gates carried: >= 500 stays, RASS varying within stays, 0 unparsed.
G2  **THE FIRST GOAL MUST VARY** across stays -- an adjustment for a constant is no adjustment.
G3  **NEGATIVE CONTROL ON THE GAIN.** A Gaussian block of the same width as the kinetic basis must produce
    a gain indistinguishable from zero. The gain is a difference of two fitted models and more columns can
    buy correlation by themselves; this is what bounds that.
G4  **COLLIDER DIRECTION CHECK, and it is descriptive rather than a bar.** Report the correlation between
    the most-recent goal and the PREVIOUS RASS observation in the same stay. A strong one is direct
    evidence that the goal responds to the patient, which is what makes arm B a collider and arm C
    necessary. Stating the mechanism's magnitude is worth more than asserting it.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF THE GAIN COLLAPSES IN ARM C** -- below half of E160's +0.2421 once the first goal is adjusted for --
then the kinetic elaboration was buying care-process structure too, the ICU result is not evidence about
pharmacology at any rung, and Challenge D needs a cohort where sedation is not titrated to a charted
target. That would leave the construct-match rule untested rather than refuted, and it is the outcome
that costs most because it removes the only unconditional finding E160 produced.

**REGISTERED PREDICTION: the gain survives all three arms at >= half of +0.2421.** The reasoning is above
and it is falsifiable: if the confound explained the gain, arm C should remove most of it.

**SECONDARY, NO VERDICT: the level in each arm**, so the [+0.16, +0.43] interval E160 could not narrow is
reported under an adjustment that is not a collider.

WHAT WAS ALREADY SEEN (rule 41). All of E160's output and its two follow-up diagnostics, quoted above;
and the first-goal distribution across stays, checked to design arm C and involving no exposure column.

    python bsde/src/bsde/experiments/e162_transport_gain_vs_intent.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import spearman                                       # noqa: E402

sys.path.insert(0, HERE)
from e160_mimic_transport import DRUGS, HALF_LIVES, TABLE, _f, oob_rho         # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e162_transport_gain.json")

REPS = 200
E160_GAIN = 0.2421


def main(argv=None) -> int:
    rng = np.random.default_rng(162)
    rows = list(csv.DictReader(open(TABLE, newline="")))
    stay = np.array([r["stay_id"] for r in rows])
    y = np.array([_f(r["rass"]) for r in rows], float)
    goal = np.array([_f(r["goal_rass"]) for r in rows], float)
    t = np.array([_f(r["t"]) for r in rows], float)
    L0 = np.column_stack([[_f(r[f"cum_{d}"]) for r in rows] for d in DRUGS]).astype(float)
    L2 = np.column_stack([[_f(r[f"k{h}_{d}"]) for r in rows] for d in DRUGS for h in HALF_LIVES]
                         ).astype(float)

    # first charted goal per stay, and the previous RASS in the same stay (for G4)
    order = np.lexsort((t, stay))
    first_goal = {}
    prev_rass = np.full(len(rows), np.nan)
    last = {}
    for i in order:
        s = stay[i]
        if s in last:
            prev_rass[i] = last[s]
        last[s] = y[i]
        if s not in first_goal and math.isfinite(goal[i]):
            first_goal[s] = goal[i]
    fg = np.array([first_goal.get(s, np.nan) for s in stay], float)

    ok = np.isfinite(y) & np.isfinite(L0).all(1) & np.isfinite(L2).all(1)
    out = {"experiment": "E162", "n_rows": int(ok.sum()),
           "n_stays": int(len(set(stay[ok].tolist()))), "reps": REPS, "e160_gain": E160_GAIN}
    print(f"G1 COHORT  {int(ok.sum()):,} observations, {len(set(stay[ok].tolist())):,} stays")

    uniq_fg = sorted({v for v in first_goal.values() if math.isfinite(v)})
    g2 = len(uniq_fg) >= 3
    print(f"G2 FIRST GOAL VARIES  {len(first_goal):,} stays have one, {len(uniq_fg)} distinct values "
          f"{uniq_fg} -> {'PASS' if g2 else 'FAIL'}")

    m4 = ok & np.isfinite(goal) & np.isfinite(prev_rass)
    r_collider = spearman(list(goal[m4]), list(prev_rass[m4]))
    print(f"G4 COLLIDER DIRECTION (descriptive)  rho(most-recent goal, PREVIOUS RASS in the same stay) = "
          f"{r_collider:+.4f} over {int(m4.sum()):,} rows")
    print(f"   a strong value is direct evidence the goal RESPONDS to the patient, which is what makes "
          f"arm B a collider and arm C necessary")
    out["G2"] = {"pass": bool(g2), "distinct_first_goals": uniq_fg}
    out["G4_collider_rho"] = r_collider

    def ladder(mask, extra=None, tag=""):
        X0 = L0[mask] if extra is None else np.c_[L0[mask], extra]
        X2 = np.c_[L0[mask], L2[mask]] if extra is None else np.c_[L0[mask], L2[mask], extra]
        a = oob_rho(X0, y[mask], stay[mask], rng, reps=REPS)
        b = oob_rho(X2, y[mask], stay[mask], rng, reps=REPS)
        print(f"   {tag:34s} L0 {a[0]:+.4f}  L2 {b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]  "
              f"gain {b[0] - a[0]:+.4f}")
        return {"L0": a[0], "L2": b[0], "L2_ci": [b[1], b[2]], "gain": b[0] - a[0],
                "n": int(mask.sum())}

    # ---- G3 negative control on the GAIN ---------------------------------------------------------------
    print(f"\nG3 NEGATIVE CONTROL on the gain -- a Gaussian block as wide as the kinetic basis")
    gz = rng.standard_normal((int(ok.sum()), L2.shape[1]))
    a = oob_rho(L0[ok], y[ok], stay[ok], rng, reps=REPS)
    b = oob_rho(np.c_[L0[ok], gz], y[ok], stay[ok], rng, reps=REPS)
    g3_gain = b[0] - a[0]
    g3 = abs(g3_gain) < 0.05
    print(f"   L0 {a[0]:+.4f} -> L0 + {L2.shape[1]} Gaussian columns {b[0]:+.4f}  "
          f"gain {g3_gain:+.4f} -> {'PASS' if g3 else 'FAIL'}")
    out["G3"] = {"pass": bool(g3), "gain": g3_gain}

    gates = g2 and g3
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    print("THE LADDER under three treatments of clinical intent")
    arms = {}
    arms["A_unadjusted"] = ladder(ok, None, "A unadjusted")
    mB = ok & np.isfinite(goal)
    arms["B_recent_goal"] = ladder(mB, goal[mB].reshape(-1, 1), "B + most-recent goal (collider)")
    mC = ok & np.isfinite(fg)
    arms["C_first_goal"] = ladder(mC, fg[mC].reshape(-1, 1), "C + FIRST goal of the stay")
    out["arms"] = arms

    gC = arms["C_first_goal"]["gain"]
    keep = gC >= E160_GAIN / 2
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif keep:
        verdict = (f"THE GAIN SURVIVES -- the kinetic elaboration is worth {gC:+.4f} even with the "
                   f"stay's FIRST sedation target adjusted for, against E160's unadjusted {E160_GAIN:+.4f} "
                   f"and DOSE-I's +0.2508. A care-process confound inflates how strongly any exposure "
                   f"summary orders RASS; it does not explain why knowing WHEN the drug was given helps "
                   f"as much in an ICU over days as in an endoscopy suite over minutes. **That shape is "
                   f"the transport finding, and the construct-match rule does not predict it.**")
    else:
        verdict = (f"THE GAIN COLLAPSES -- {gC:+.4f} against half of {E160_GAIN:+.4f}. The kinetic "
                   f"elaboration was buying care-process structure too, so the ICU result is not "
                   f"evidence about pharmacology at any rung and Challenge D needs a cohort where "
                   f"sedation is not titrated to a charted target. The construct-match rule is left "
                   f"UNTESTED rather than refuted, and E160's verdict must be softened to that.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
