#!/usr/bin/env python3
"""E212 — does spontaneous EEG predict command-following WITHIN a patient?

REGISTERED BEFORE ANY CANDIDATE COLUMN HAS BEEN INSPECTED. The extraction that feeds this file is running
as it is written; 983 of 23,192 rows existed at registration time and **no candidate value in them has been
read, plotted or summarised.** What HAS been read is the label table, the sedative-exposure table and the
row counts — the rule-41 feasibility probe, which is required to run *before* a registration so the floors
below are set knowing the coverage rather than discovered by a gate failing.

=========================================================================================================
WHY E204 IS NOT SIMPLY RE-RUN
=========================================================================================================
E204 asked the between-patient question — does EEG predict whether *this patient* obeys commands — and was
**withdrawn** for a data defect (an `EDF Annotations` channel entered the panel and truncated the window).
The defect is fixed and verified: every row now carries exactly 19 channels, matched by case-insensitive
equality against the 10-20 set rather than by substring (rule 61).

But re-running the same design would inherit its real weakness, which was never the bug. **A between-patient
contrast confounds command-following with everything else that differs between two patients** — age, the
reason they are in the ICU, skull, montage, how sedated their clinician keeps them. The label is a
consequence of the brain injury, and so is the EEG.

The feasibility probe found the design that removes all of it. Of 12,501 patients with a GCS-motor
assessment, **712 have two assessments that DISAGREE** on obeying commands. Each of those patients is their
own control: the same skull, the same electrodes, the same diagnosis, the same clinician, hours apart.

    **P1  Among discordant patients, is the candidate HIGHER at the assessment where the patient obeys
          commands than at the one where they do not, more often than chance — after the incumbent is
          allowed to explain it first?**

The probe's numbers, all label-side and all reported before the run: base rate of `obeys` 0.5564 over 23,192
assessments; exactly 2 assessments per patient by construction; RASS present on 0.6170 of rows; a sedative
active on 0.5593, with `n_sedatives_active` 44.07 % zero (rule 43 — the exposure has a large off-state, so
it is used as a binary incumbent and not as a dose).

=========================================================================================================
THE UNIT IS THE PAIR (rule 69)
=========================================================================================================
The exposure is nested inside the patient, so the effective n is **the number of discordant patients, not
the number of rows**. Every interval here is a bootstrap over PAIRS and every null permutes the label
WITHIN a pair — which, for a two-element pair, is a sign flip. A row-level interval would be a fiction.

=========================================================================================================
INCUMBENT (rule 45) — TWO, BOTH DECLARED IN ADVANCE
=========================================================================================================
  I1  **RASS at the same assessment.** The bedside sedation score. It is the thing an EEG marker has to
      beat, and it is available on 61.70 % of rows.
  I2  **`any_sedative` at the same assessment**, from the drug record. A cheaper and coarser incumbent.

An EEG candidate is only interesting if it adds over I1. **Neither incumbent shares a measurement act with
the outcome** — GCS-motor is scored by a different observation than RASS, so rule 86's unclearable bar does
not apply here, but they are scored by the SAME PERSON at the SAME bedside visit, and that is stated as a
limitation rather than claimed as independence.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE. At least `MIN_PAIRS` discordant patients with BOTH rows extracted, every tested candidate
    finite in both, and `n_channels == 19` on every row — the E204 contamination check, kept as a gate
    because it is the defect that withdrew the parent.
G2  THE INCUMBENT MUST BE ALIVE (rule 53, and E208 died exactly here). RASS must itself separate the two
    members of a discordant pair above its own within-pair sign-flip floor. **If the bedside score cannot
    tell the two assessments apart, nothing about an EEG marker beating it is interpretable.**
G3  NEGATIVE CONTROL. An i.i.d. noise column, paired identically, must NOT clear the floor.
G4  **TIME-ORDER PLACEBO, AND IT GATES THE VERDICT.** The two assessments of a pair differ in TIME as well
    as in label. Electrode drift, cumulative artefact, day-of-stay and recovery trajectory all supply a
    within-patient time trend, and a trend alone would produce a within-pair difference with no relation to
    command-following (catalogue rule 64 — a contrast keyed to an event is a time split in disguise until
    shown otherwise). So the pairs are split by ORIENTATION — those where the obeying assessment comes
    EARLIER, and those where it comes LATER — and the effect must appear **in both, with the same sign**.
    A pure time trend reverses sign between the two orientations and is refused here. A candidate clearing
    in only one orientation is reported as TIME-CONFOUNDED, never as a positive.

=========================================================================================================
PRIMARY STATISTIC
=========================================================================================================
For each discordant pair, the out-of-fold predicted probability of `obeys` is formed for both members from
a model fitted on OTHER PATIENTS ONLY (leave-patient-out folds), and the pair is scored as concordant if the
obeying member is predicted higher. The primary is the **increment in that concordance rate** from adding
the candidate to the incumbent-only design, with a **pair-level bootstrap** interval.

Concordance over a two-element pair is exactly a matched AUC, and its null is 0.5 — but rule 72 records
that a pooled cross-validated AUC's null is not where it is assumed to be, so the floor is **measured**
here by within-pair sign-flip permutation rather than assumed.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails. Nothing about any candidate may be read.
  (2) REVERSED            a candidate's increment interval excludes zero on the NEGATIVE side. This is not
                          support in any form and is reported as its own outcome (rules 37 and the fourth
                          occurrence recorded under rule 34).
  (3) TIME-CONFOUNDED     a candidate clears in the pooled pairs but NOT in both orientations, or clears
                          with opposite signs in the two orientations. The effect is a within-patient time
                          trend and G4 refuses it.
  (4) ABSENT              every interval includes zero. The honest and most likely outcome.
  (5) ADDS                the increment interval excludes zero on the POSITIVE side AND both orientations
                          agree in sign with the pooled estimate.

**REGISTERED PREDICTION: (4) ABSENT for every candidate.** The within-patient design removes exactly the
between-patient variance that makes EEG look predictive of anything clinical, and the surviving contrast is
hours apart in the same ICU stay. Two assessments of one patient hours apart differ far less in EEG than two
patients do, while the label difference is total. I expect the spectral panel to have nothing left.
**If (5) comes back for `lempel_ziv` or `whole_head_exponent` it is the more important result**, because a
marker that tracks command-following within a patient is the first thing Challenge B has ever had that is
not explicable by who the patient is.

Multiplicity: **7 candidates** are tested against 2 incumbent designs. That is 14 comparisons and no
correction is applied; the count is stated so a reader can apply their own (the ledger's standing position).

    python bsde/src/bsde/experiments/e212_command_following_discordant.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import grouped_cv_predict  # noqa: E402  (import checked at run time)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e212_command_following_discordant.json")
SHARDS = "/tmp/eeg_probe/heedb_cmd_follow.*.csv"
EXPOSURE = "/tmp/eeg_probe/cmd_sedative_exposure.csv"

SEED = 20260802
MIN_PAIRS = 120
N_BOOT = 2000
N_PERM = 400
N_CHANNELS_REQUIRED = 19

CANDIDATES = ("whole_head_exponent", "exponent_low", "exponent_high", "relative_alpha_power",
              "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv")
