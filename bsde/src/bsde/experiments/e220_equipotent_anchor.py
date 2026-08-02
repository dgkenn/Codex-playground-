#!/usr/bin/env python3
"""E220 — the alpha asymmetry on a PHARMACOLOGICALLY EQUIPOTENT depth anchor.

REGISTERED WHILE THE PK TRACK EXTRACTION IT CONSUMES IS STILL RUNNING. No potency value has been computed
on real data, and no alpha value has been read against one.

=========================================================================================================
THE BLOCKER THIS EXISTS TO REMOVE
=========================================================================================================
Every Challenge A result on VitalDB has been limited by the same thing, now written into
`NOTE_ALPHA_INSTABILITY.md` as a standing caution: **this cohort has had no clean depth anchor.**

  * **BIS cannot serve.** It is not equipotent across agents — Kuizenga 2019 (PMID 31567365) puts the
    index at which half of subjects lose an endpoint at **46.7 for propofol against 68 for sevoflurane**,
    while the drug concentrations themselves are *"perfectly correlated (correlation coefficient = 1)"* —
    and it is computed from the same EEG, so residualising a spectral feature on it partly residualises
    that feature on itself.
  * **The drug's own units cannot serve either.** A tercile of MAC and a tercile of effect-site
    concentration are not the same depth. Kuizenga's C50 values make the gap explicit: for tolerance to
    shake and shout, **1.85 µg/ml propofol against 0.90 vol % sevoflurane**.
  * Suppression ratio is 0.000 throughout, so it cannot substitute.

So every statement of the form "at equal depth the agents differ in alpha" has been unavailable, and what
has actually been shown is about **dose**, not depth.

**The anchor this file uses is a published cross-agent potency scale, and it was already in the repo.**
Hannivoort's NSRI response surface (PMID 27106965), implemented in `bsde/pkpd/interaction.py`:

    U  =  (end-tidal sevoflurane / 2.59 vol %  +  propofol Ce / 7.58 ug/ml) * (1 + remifentanil Ce / 1.36 ng/ml)

`U = 1` is the PTOL-50 surface. Three properties make it the right anchor here and each matters:

  1. **It is equipotent by construction** — both agents are divided by their own Ce50, so a propofol
     window and a sevoflurane window with the same `U` are at the same modelled potency.
  2. **It carries the opioid term**, which this cohort needs: propofol cases run at **2.3x** the
     remifentanil of sevoflurane cases (3.504 against 1.503, difference +2.001 [+1.568, +2.492]).
  3. **It contains no EEG**, so §6.2 of `PKPD_MODEL_REVIEW.md` is satisfied: the exposure model is never
     validated, tuned or selected against BIS.

**UNITS ARE THE TRAP AND THE MODULE ALREADY REFUSES IT.** `potency_units` wants sevoflurane in END-TIDAL
vol %. VitalDB publishes `Primus/MAC`, an age-adjusted MAC MULTIPLE, and `mac_to_vol_pct_sevo` RAISES
rather than guessing a conversion this project has not verified from a primary source. So this file uses
`Primus/EXP_SEVO` directly, which the deposit records, and inspired sevoflurane is NOT used because it
overstates the effect site.

=========================================================================================================
WHAT THE COMMON SCALE MAKES POSSIBLE, AND WHY IT IS NOT THE OLD STATISTIC
=========================================================================================================
**The within-case rank statistic would be nearly unchanged by construction and is therefore NOT the
primary.** Within one case, if remifentanil is constant, `U` is a strictly increasing function of that
case's own drug concentration, so the ordering of its windows — and any rank statistic computed on it — is
IDENTICAL. Reporting that as a new result would be reporting arithmetic.

What a common scale actually buys is a **shared x-axis between the arms**, which no previous analysis had:

    **P1  Pool every window from both arms, bin by `U`, and ask whether alpha differs BETWEEN AGENTS
          WITHIN A BIN — that is, at matched pharmacological potency.**

    **P2  Does the alpha-versus-`U` SLOPE differ between agents, estimated on the common axis?**

P1 is the question that has been unanswerable on this cohort from the beginning.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE: >= `MIN_PER_ARM` cases per arm with `U` computable — end-tidal sevoflurane for the volatile
    arm, propofol Ce for the TIVA arm, remifentanil Ce for both — at the feature grid times.
G2  **THE ANCHOR MUST VARY** (rule 43). `U` must have a non-degenerate within-case spread, and the fraction
    of windows at `U = 0` must be reported; a correlation spans an off-state perfectly happily and a
    stratified analysis cannot.
G3  **THE ARMS' `U` DISTRIBUTIONS MUST OVERLAP, AND THIS IS THE GATE THE WHOLE DESIGN RESTS ON.** If the
    sevoflurane arm sits at one end of the potency axis and the propofol arm at the other, then "at matched
    `U`" describes an empty stratum and the equipotent anchor has bought nothing. The overlapping range and
    the number of cases contributing to it are reported, and bins holding fewer than `MIN_BIN` windows from
    EITHER arm are dropped and counted (rule 14).
G4  **THE ANCHOR MUST DIFFER FROM THE RAW EXPOSURE ORDERING** (rule 60's escape check). If `U` reorders
    each case's windows identically to its own drug concentration, then nothing has changed and this is the
    old analysis renamed. Reported as the per-case rank correlation between `U` and the raw exposure.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails. In particular, if the arms do not overlap on `U` there is no
                         matched comparison to make and nothing below may be read.
  (2) AMPLIFIED          the between-agent alpha difference at matched `U` is LARGER than on raw units.
                         Non-equipotence was MASKING an agent difference.
  (3) UNCHANGED          the difference at matched `U` is indistinguishable from the raw-unit version.
                         Non-equipotence does not explain the asymmetry, and the last standing candidate
                         mechanism falls with it.
  (4) ATTENUATED         smaller but still excluding zero. Non-equipotence explains part.
  (5) REMOVED            no difference between agents at matched `U`, where there is one on raw units. The
                         asymmetry is an artefact of comparing two non-equipotent dose scales.

**REGISTERED PREDICTION: (4) ATTENUATED, weakly held.** Five candidate mechanisms have now been tested and
refuted on this cohort — band placement, burst suppression, age, dose range and co-medication — and
non-equipotence is the only one the literature still supports. But the opioid imbalance is already known
NOT to explain the effect under direct matching, and the opioid term is the largest single change `U`
makes. **(5) would close the whole Challenge A line with a clean answer**; **(3) would mean the effect is
not pharmacological in any way this cohort can express, and the next move would have to be a different
deposit rather than a different statistic.**

**SCOPE AND THE HONEST LIMIT.** `U` is a POPULATION response surface transported to a new population, and
this project has measured what transport costs: a fixed kernel reproduced a pump's own effect-site
concentration at MDAPE 54.9 % while fitting each patient at R2 0.9990. Expect **good ordering and poor
absolute calibration**, which is exactly why every statistic here is rank-based or bin-based and why no
claim is made about the absolute value of `U` at which anything happens.

    python bsde/src/bsde/experiments/e220_equipotent_anchor.py
"""
