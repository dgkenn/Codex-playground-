#!/usr/bin/env python3
"""E199 — E192's test, moved to the session where the BCI actually works.

REGISTERED WHILE THE FINAL-SESSION EXTRACTION IS STILL RUNNING; no feature or outcome value from it has
been inspected.

=========================================================================================================
WHAT E192 SETTLED, AND WHY ITS COHORT WAS THE WRONG ONE
=========================================================================================================
E192 tested E181's graded execution-quality finding on continuous pursuit and returned NOT INTERPRETABLE at
its BCI-aliveness gate. **The gate did its job.** In session 1:

    pooled cursor-velocity-to-target alignment   **−0.0738**   against a sign-flip 95th percentile of +0.0416
    subjects with positive alignment             **6 of 28**
    median per-trial cursor-target distance      **0.4831**    where a random pair in the workspace ~0.52
    median fraction inside a 0.1 hit radius      **0.043**

The cursor is not being driven at the target, so "how well the command was executed" has no estimand
(rule 53). **Everything else in the design passed**: 1,680 trials, 28 subjects, 1,230 matched adjacent
pairs, the outcome graded within run (sd_within/sd_subject 0.780), and a pairing balanced to +0.0000 with
the trial index at 0.5000, p = 1.0000. The failure was the cohort, not the machinery — and the extractor
was verified against an independent implementation first, with the deposit's own `cursorvel` matching the
empirical derivative of its `cursorpos` at cos 0.9687, so no sign or axis error is in play.

**The cause was a choice I made.** Session Se01 is the first session, subjects are least trained, and for
the fourteen "Main" subjects it contains only the traditional AR decoder. Choosing it was blind to any
feature, which was the intent, and also blind to whether the paradigm functions — rule 41, where the probe
that would have caught it needed no EEG at all, only the cursor and target traces.

=========================================================================================================
THE COHORT CHANGE, AND WHY IT IS NOT A RANKING ON THE OUTCOME
=========================================================================================================
E199 uses **each subject's FINAL session** — Se08 for the Main sub-study, Se04 for Transfer Learning. That
is a protocol-level criterion (the most-trained session, carrying the study's later decoders), fixed
without looking at any subject's tracking score, and applied identically to all 28 subjects. It is not
"the session with the best performance", which would be selection on the outcome's level.

**G2 is unchanged and can still fail.** If the BCI is not alive in the final session either, this deposit
cannot test E181 at all and that is the result. Nothing else about the design moves: the same four
scorings extracted together, the same declared primary (`mean_dist`), the same matched adjacent-trial
pairing within a run, the same E181 direction fixed in advance at BELOW 0.5, the same REVERSED branch, the
same floors and the same BH correction.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails. If it is G2 again, the deposit cannot test E181.
  (2) REVERSED            `mu_mean` clears its floor with an interval ABOVE 0.5 — refutes E181's
                          direction and must never be written as support.
  (3) ABSENT ABOVE FLOOR  `mu_mean` does not clear the measured floor.
  (4) FRAGILE             it clears in E181's direction on the primary scoring but at least two of the
                          three other scorings sit the other side of 0.5.
  (5) REPLICATED          it clears in E181's direction and the other scorings agree in sign.

**REGISTERED PREDICTION: (3) ABSENT ABOVE FLOOR**, unchanged from E192 and restated rather than inherited.
Two of the three prior external or held-out tests of a pre-cue alpha effect in this programme returned
absent (E174 on held-out Stieger sessions, E188 on Dreyer with real EMG channels showing muscle null at
p = 0.972), and the one that survived did so on the deposit it was discovered in.

**Independence limitation, unchanged and declared:** this deposit and Stieger's come from the same
laboratory, so with disjoint subjects and a different task this is a subject-and-task replication, not a
laboratory-independent one. Dreyer supplied that independence and could not supply the graded outcome.

    python bsde/src/bsde/experiments/e199_continuous_pursuit_final_session.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e192_continuous_pursuit_graded_replication as E192                      # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))

# The ONLY change: the cohort. Every threshold, statistic, gate and branch below is E192's, reached
# through its own module so the two cannot drift apart (rule 20 — when two scripts compute the same
# quantity, diff them; here there is nothing to diff because there is one implementation).
E192.TABLES = [os.path.join(RESULTS, f"cp_last.s{k}.csv") for k in range(4)] + \
              [os.path.join(RESULTS, "cp_last.csv")]
E192.OUT = os.path.join(RESULTS, "e199_continuous_pursuit_final_session.json")


def main() -> int:
    print("E199 — E192's test on each subject's FINAL session (Se08 Main / Se04 Transfer Learning)")
    print("   cohort is the ONLY change; G2 aliveness is unchanged and can still fail")
    return E192.main()


if __name__ == "__main__":
    raise SystemExit(main())
