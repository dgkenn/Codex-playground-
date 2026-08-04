"""E124 -- E108 retried with a DECODER that works. Does `ge_norm` predict BCI performance in eegmmidb?

REGISTERED BEFORE `ge_norm` HAS BEEN PUT NEAR THE NEW LABEL. The CSP label was built to replace a broken
outcome, and its aliveness was probed (see the disclosure below); the association this file tests has not
been computed.

=========================================================================================================
WHY A SUCCESSOR RATHER THAN A RE-RUN, AND WHAT EXACTLY CHANGED
=========================================================================================================
E108 asked the one question that can close E86's last standing qualification. E86 found `ge_norm` predicts
BCI accuracy at D1 rho +0.3069 [+0.0495, +0.5343]; E97, E101 and E106 worked three of its four
qualifications, and the survivor is multiplicity -- BH q = 0.0920 across the E86 family. No further
analysis of those same 62 Stieger subjects can fix that. **A single pre-registered hypothesis tested once
in an independent cohort has a family of size one and needs no correction at all.**

**E108 never got to ask it.** It returned ABSENT at G2, the outcome-aliveness gate: median `imagery_auc`
0.5306 over 104 subjects with only **16.3 %** beating their own permutation null, against a required 20 %.
That is the E33/E61 rule firing correctly -- if nobody can be decoded there is no performance for anything
to predict, and a null would have been a statement about the label, not about `ge_norm`.

The label was the problem, not the cohort. `imagery_auc` came from a band-power decoder. Motor imagery is
a SPATIAL phenomenon -- the mu/beta desynchronisation is lateralised over sensorimotor cortex -- and the
standard instrument for it is Common Spatial Patterns, which learns the discriminative spatial filters
instead of averaging over them. `build_eegmmidb_csp_label.py` fits CSP **inside each cross-validation
fold**, so the filters never see the trials they are scored on.

**WHAT CHANGED IS THE INSTRUMENT AND ONLY THE INSTRUMENT (rule 58).** This file calls E108's own `main()`
with three arguments -- the label table, the outcome column, the output path -- and touches nothing else.
`MIN_SUBJECTS` is still 80. G2 is still `median > 0.5` and `frac_perm_p < 0.05 >= 0.20`, the identical
numbers that just refused E108. The primary is still `spearman(ge_norm, outcome)` predicted POSITIVE with
`ge_norm` the MEAN of R01 and R02. The placebo is still 2000 permutations of the outcome across subjects.
E108's default invocation was re-run after the parameterisation and reproduces its logged gates and
verdict exactly, so the shared code is the same code.

**DISCLOSURE, because it is the difference between rule 41 and goalpost-moving.** The CSP label's aliveness
WAS measured before this registration was written: median `csp_auc` 0.6181 and 37.8 % of subjects beating
their own permutation null, on the 90 subjects finished at the time. Rule 41 requires exactly this -- run
the feasibility probe before registering, not after failing -- and the probe touched only the label, never
`ge_norm` and never their association. What would have been illegitimate is moving G2's 20 % to fit a
label; instead the threshold is untouched and a better instrument was built to clear it. If the finished
label falls back below 20 %, this experiment returns ABSENT exactly as E108 did.

THE LEAVE-ONE-RUN-OUT COLUMN IS SECONDARY AND IS DECLARED AS SUCH HERE. The label table ships both a
random-fold AUC (`csp_auc`) and a leave-one-run-out AUC (`csp_auc_loro`), which is the stricter split
because eegmmidb's runs are separated in time and a random fold can share within-run drift. The PRIMARY is
`csp_auc`, chosen before the numbers were compared, because it is the direct analogue of E108's
`imagery_auc`; `csp_auc_loro` is reported beside it as a sensitivity arm and a disagreement between them
is a finding about the label rather than about `ge_norm`.

VERDICT branches, gates, placebo and the "what necessarily differs" list are E108's, unchanged, and are
not restated here so that there is exactly one copy of them to read (rule 20).

SCOPE. eegmmidb, motor-imagery decodability, resting-state graph measures. Decodability is an upper bound
on BCI control, not the same construct as Stieger's online accuracy -- E108's point 1, which still stands
and still limits what a replication here would mean.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))

LABEL = os.path.join(RESULTS, "eegmmidb_csp_label.csv")
OUT = os.path.join(RESULTS, "e124_ge_norm_csp_replication.json")
OUT_LORO = os.path.join(RESULTS, "e124_ge_norm_csp_replication.loro.json")


def main(argv=None) -> int:
    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E124", "B",
            "Does ge_norm predict BCI performance in eegmmidb, with a CSP decoder that is actually alive?",
            "eegmmidb",
            "spearman(ge_norm, csp_auc) across subjects, PREDICTED POSITIVE, ONE test; "
            "ge_norm = mean of R01 and R02",
            ["E108's gates unchanged: G1 >=80 subjects; G2 median>0.5 and >=20% beat their own "
             "permutation null; G3 predictor varies; G4 iaf escape reported either way"],
            "outcome permuted across subjects, 2000 draws; real estimate inside the central 95% is "
            "WITHDRAWN",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E108",
            instrument_changed="the DECODER: band-power imagery_auc replaced by CSP fitted inside each "
                               "CV fold. No threshold, cohort or horizon altered.")
        print("registered E124")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")

    if "--register-only" in (argv if argv is not None else sys.argv[1:]):
        return 0
    if not os.path.exists(LABEL):
        print(f"ABSENT: {LABEL} does not exist yet")
        return 2

    sys.path.insert(0, os.path.dirname(HERE))
    from bsde.experiments import e108_ge_norm_external_replication as e108  # noqa: E402

    print("=" * 100)
    print("PRIMARY -- csp_auc (random folds), the direct analogue of E108's imagery_auc")
    print("=" * 100)
    rc = e108.main(["--bci", LABEL, "--outcome", "csp_auc", "--perm-column", "perm_p", "--out", OUT])

    print()
    print("=" * 100)
    print("SENSITIVITY -- csp_auc_loro (leave one run out), the stricter split. Declared secondary before")
    print("the two were compared; a disagreement is a finding about the label, not about ge_norm.")
    print("=" * 100)
    e108.main(["--bci", LABEL, "--outcome", "csp_auc_loro", "--perm-column", "perm_p_loro",
               "--out", OUT_LORO])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
