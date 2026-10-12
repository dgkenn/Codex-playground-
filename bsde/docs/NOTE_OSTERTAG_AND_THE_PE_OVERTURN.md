# What Ostertag 2025 actually says, and how E166/E170's overturn sits against it

*Written 2026-08-01, from the MEDLINE record fetched with `curl` against E-utilities and parsed directly —
never a WebFetch summary (rules 25, 39). Written BEFORE E170's placebo and verdict were available, so that
the framing could not be chosen to fit the result.*

---

## The source, verbatim where it matters

**Ostertag J, Zanner R, Schneider G, Kreuzer M. PMID 38412114, *Anesthesia and Analgesia*, 2025.**
*"Permutation Entropy Does Not Track the Electroencephalogram-Related Manifestations of Paradoxical
Excitation During Propofol-Induced Loss of Responsiveness: Results From a Prospective Observational Cohort
Study."* 60 patients, general anaesthesia, EEG around loss of responsiveness.

> "Spectral edge frequency and spectral entropy values **increased** from 19.78 [10.25-34.18] Hz to
> 25.39 [22.46-30.27] Hz (P = .0122) and from 0.61 [0.54-0.75] to 0.77 [0.64-0.81] (P < .0001),
> respectively, **before LOR**, indicating a (paradoxically) higher level of high-frequency activity.
> **PeEn and beta ratio values decrease** from 0.78 [0.77-0.82] to 0.76 [0.73-0.81] (P < .0001) and from
> -0.74 [-1.14 to -0.09] to -2.58 [-2.83 to -1.77] (P < .0001), respectively, **better reflecting the
> state transition into anesthesia**."

> "**PeEn, in particular, may present a single parameter capable of tracking the LOR transition without
> being affected by paradoxical excitation.**"

---

## Two different claims, and this project has tested both without noticing they were different

**Claim 1 — the LEVEL CHANGE.** SEF95 rises approaching loss; PeEn falls. **E34's P4 refuted this in
DOSE-I**: both fall, SEF95 by -1.02 and PE by -0.05 in median change approaching the loss. That
disagreement stands and is not affected by anything below.

**Claim 2 — the INCREMENT.** PeEn tracks the transition *where the spectral parameters are confounded by
paradoxical excitation*. That is a statement about PeEn carrying information the spectral measures do not,
which is exactly what an increment over SEF95 measures — and it is **not** what E34 tested. E34's P3b asked
the increment question with the blind estimator and returned +0.0178 [-0.0226, +0.0474], a null.

**E166 re-derived that increment with a calibrated test and it moved**: -0.02147 at p = 0.0000 against a
500-draw recording-level permutation null, on the cohort rebuilt to the row (79,429 windows, 129
recordings), with a measured detection floor of rho = 0.05 and a rho = 0 calibration rung that did not
fire. In the lower-is-better convention that is an AUC increment of **+0.021 for PE31 over SEF95**.

**So the two results point in opposite directions about the same paper, and both can be true.** DOSE-I is
procedural sedation for endoscopy with bolus propofol and an observer scale; Ostertag is general
anaesthesia induction in an operating theatre. A level change can fail to transport while an
information-increment survives — they are different quantities, and rule 28's warning (two measurements
are not thereby measuring different things) has a mirror here: two measurements of the *same* named
phenomenon are not thereby measuring the same thing either.

---

## What must be said alongside the overturn, whatever E170 returns

1. **The whole permutation-entropy family moves, not one member.** E170's table so far: PE31 -0.02180,
   PE32 -0.05107, PE61 -0.03924, and the weighted spectral multiscale measures **WSMF30 -0.07110** and
   WSMF49 -0.05321 — three times PE31's magnitude. The registered primary is the *smallest* effect in its
   own family. That is reassuring for the phenomenon and awkward for the pre-registration, and both should
   be said.

2. **The muscle comparator is close.** `rel_gamma` increments **-0.01985** against PE31's **-0.02180**.
   PE31 exceeds it, but by 0.002 on a scale where the family spans 0.07. DOSE-I has no EMG channel, so
   muscle cannot be excluded any other way, and E34's own record already flagged this as unexcludable
   (`rel_gamma` 0.632 against the primary's 0.623 on raw AUC). **Any claim from this must carry that
   sentence.**

3. **`MF` moves the wrong way** (+0.00587, p = 0.9840) and `rel_delta1` and `rel_beta1` barely move. So
   this is not "everything adds at n = 79,429", which is the first thing to check when a large cohort
   returns many small significant effects.

---

## The claim this licenses, and the one it does not

**Licensed, if E170's placebo distribution and BH hold:** on 129 procedural-sedation recordings, time-domain
order-pattern measures carry information about imminent loss of consciousness that the spectral edge
frequency does not, which is the mechanism Ostertag's conclusion proposes and tests differently.

**Not licensed:** anything about the direction of the level change (E34 refuted it here), anything about
general anaesthesia (different cohort), and anything that treats PE31 as privileged within its family. If
the effect is real it belongs to the order-pattern family, and the pre-registered primary is simply the
member that was named first.
