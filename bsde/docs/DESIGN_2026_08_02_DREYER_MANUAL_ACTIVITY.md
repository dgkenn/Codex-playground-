# Design & feasibility — Dreyer `Manual activity` vs. online BCI accuracy (Challenge B)

*Design and feasibility assessment only, per instruction. No registration is written, no row is added to
`bsde/governance/REGISTRATION_LEDGER.jsonl`, no file is created under `bsde/src/bsde/experiments/`. Every
count below was produced by directly parsing the files named, printed before being interpreted (rule 5), and
no correlation between `Manual activity` and the outcome was computed at any point in this document — that
computation belongs to the registered run, not to a feasibility check, or the pre-registration is void before
it starts.*

**Bottom line: REGISTER IT.** Section 7 gives the reasoning; it is not the answer the brief invited me to
find easiest to give, and I checked the arithmetic twice before writing it down.

---

## 1. Does the column exist, and is it usable? (verified against the file, not assumed)

```
$ git ls-files | grep dreyer_performance
bsde/results/dreyer_performance.csv
$ wc -l bsde/results/dreyer_performance.csv
113 bsde/results/dreyer_performance.csv
```

Tracked in git, not gitignored, not a `/tmp` artefact. The file is the deposit's raw `Perfomances.csv`:
semicolon-delimited, comma-decimal, three concatenated sections ("DATA A/B/C") with repeated header rows.
Parsed with a strict `^[A-Za-z]\d+$` match on the id field (rule 61 — do not substring/naively split a
structured file); this reproduces `PROBE_2026_08_02_DREYER_CHALLENGE_B.md`'s own count exactly:

- **87 real subject rows, 87 unique `SUJ_ID`, zero duplicates** (dataset A = 60, B = 21, C = 6).
- Header row 3 (0-indexed row 2) confirms the column name verbatim: **`Manual activity`** (index 16), with
  a companion free-text column **`Manual activity TXT`** (index 17) immediately after it.
- The section-header row (row 1) maps index 16 to the **`Demographic and Biosocial Info`** section
  (indices 8–17, `Birth_year` through `Manual activity TXT`) — **before** `Mental Rotation` (18+),
  **before** `Participant PRE-session` (21+), and far before `Participant POST-session` (36+). This is a
  structural fact about the file, not an inference: the column sits with `Birth_year`, `Vision`, and
  `Laterality answered`, not with any session-state questionnaire.

**Distribution** (measured directly, all 87 rows):

| value | meaning (Dreyer 2023 codebook, verified below) | n | % |
|---|---|---|---|
| 1 | Never | 6 | 6.9% |
| 2 | Less than once/week | 18 | 20.7% |
| 3 | ~Once/week | 13 | 14.9% |
| 4 | Several times/week | 31 | 35.6% |
| 5 | Every day | 19 | 21.8% |

- **n non-missing: 87/87 (100%).** No missingness at all.
- **Ordinal, 5 distinct values**, coded 1–5. The companion free-text field (`Manual activity TXT`, 79/87
  non-missing, French free text — "Cardistry", "Musculation", "Escalade", etc.) is a description of what
  the activity *is*, not an alternative encoding of frequency; it is not a candidate itself.
- **Not near-constant.** The modal value (4) holds 35.6% of subjects — nowhere near the 90%+ that would
  trip `verifier/stats.screen_candidates`'s near-constant guard (rule 74). Every level has ≥6 subjects.
  **This does not kill the design.**
- **The codebook is not guessed.** Fetched the Dreyer 2023 data descriptor itself (PMID 37670009, `Sci
  Data` 2023;10:580, via `efetch` on PMC10480224, quoted verbatim below) and it states the coding exactly:
  *"Manual activity = practice, Yes every day: 5 – Yes several times per week: 4 – Yes around one time per
  week: 3 – Yes less than one per week: 2 – Never: 1."* This matches the measured distribution's five
  levels exactly and confirms it is a **pre-session self-report of habitual practice frequency**, collected
  as part of the demographic intake, not a state measure taken during the experiment.

**Verdict on this item: usable. 5 ordinal levels, 100% coverage, no level dominates, and the coding is
independently confirmed from the source data descriptor. Nothing here kills the design (rule 74's failure
mode — a nearly-constant or all-NaN column — does not apply).**

---

## 2. Power

**The design under consideration is a single bivariate correlation** — `Manual activity` against mean
online BCI accuracy — mirroring the exact template already used and registered on this cohort for other
non-EEG predictors (E129's SMR test, E132's mental-rotation test). This is **not** the same statistical task
as E134/E163's out-of-bag increment test (add a candidate to the SMR predictor, evaluate the improvement in
cross-validation), and the two designs have different power at the same *n* — conflating them would be an
error of exactly the kind rule 63 warns against (importing a threshold derived for one machinery into a
different one).

**Closed-form power for a bivariate correlation, n = 87, α = 0.05 two-sided (Fisher z):**

```
z_(α/2) = 1.959964, z_β (80% power) = 0.841621
C = (z_(α/2)+z_β) / sqrt(n-3) = 2.801585 / sqrt(84) = 0.305680
r_detectable = tanh(C) = 0.2965
```

| true ρ | power at n=87 |
|---|---|
| 0.10 | 15.1% |
| 0.20 | 46.0% |
| **0.297** | **80.0% (the 80%-power floor)** |
| 0.30 | 81.0% |
| 0.35 | 91.8% |
| **0.381** | **95.7%** |
| 0.40 | 97.3% |
| 0.44 | 99.1% |

**Comparison to the E134/E163 floor.** `CLAUDE.md` rule and the ledger both state, verbatim, for the
*increment* design on this identical cohort (E163, quoted in full in §3): **"floor ABOVE 0.4 — 70 percent
detection at rho_partial 0.40, 38 percent at 0.30, 8 percent at 0.10."** A plain bivariate correlation is
measurably **more sensitive** than that increment test at the same n (0.297 vs. ~0.40 for comparable power) —
which is expected, since an out-of-bag increment test spends some of its information on cross-validation
splits and on a already-fitted incumbent, while a bivariate correlation does not. **This distinction is the
one thing this section must not blur**: a design that asks "does `Manual activity` ADD to the SMR predictor
out-of-bag" inherits the ~0.40 floor and needs a large partial effect to say anything; a design that asks
"does `Manual activity` correlate with accuracy," full stop, is bound by the 0.297 floor instead.

**Is 0.297 met by a plausible effect size?** Fetched the Rimbert 2018 full text (PMC6352609, licensed via
this exact PMID) rather than trusting the abstract's qualitative wording alone, and it reports the actual
number: **"a statistically significant positive linear correlation between BCI accuracy and declared
frequency of manual activities... r = 0.473; ρ = 0.381; p < 0.04"** (n = 35). **0.381 clears the 0.297 floor
with room (95.7% power if it replicates at that magnitude)** — this is not a design that can only detect an
implausibly large effect; it is adequately powered for the literature's own point estimate, on the
literature's own statistic (Spearman ρ, reported alongside Pearson r).

**The honest caveat, stated rather than glossed over.** Rimbert's n = 35 is small, and small-sample published
correlations are subject to winner's-curse inflation; several non-EEG BCI self-report correlates in this
project's own hands have NOT replicated near their source magnitude — mental rotation came back at
**−0.1700 [−0.3833, +0.0434]** against Jeunet's "strong correlations" claim (E132), and `POST_Agentivity`'s
apparent **+0.2714** was withdrawn as a look-ahead artefact, not a real predictor (E132). If the true effect
here is closer to 0.15–0.20 rather than 0.38, power falls to 30–46%, and a null would be **underpowered, not
informative** (rule 31) — this must be stated in the registration and the verdict branch for "CI includes
zero" must say so explicitly rather than reading as "manual activity does not matter."

**Conclusion for this section: the design is adequately powered for the literature-quoted effect size (0.381,
95.7% power), and NOT adequately powered to distinguish "no effect" from "a small effect" (≤0.20, ≤46%
power) if the true value is smaller than reported. That asymmetry is a limitation to disclose, not a reason
to refuse registration** — E129 and E132 registered under the identical asymmetry and both produced
interpretable results (one positive, one a clean non-replication with a stated interval).

---

## 3. The incumbent (rule 45), verified from the ledger, not from the brief

Quoted **verbatim** from `bsde/governance/REGISTRATION_LEDGER.jsonl`, row `"id": "E129"`:

> *"(c) REPLICATED, and it lands almost exactly on the attenuated expectation. 87 subjects, all gates
> passed: outcome median 56.25 % with 49.4 % above the derived Binomial(160,0.5) threshold of 56.50 %;
> predictor median 5.766 dB, sd 4.625, range [-0.59, 18.15], 98.9 % positive. PRIMARY
> spearman(smr_predictor_db, online accuracy) = +0.4440 [+0.2480, +0.6104], excluding zero at 5/5 bootstrap
> seeds and lying OUTSIDE the permutation interval [-0.2108, +0.2189]. Blankertz reported r = +0.53 at
> N=80; E101's single-session attenuation predicts +0.4183 here, and the observed +0.4440 is within 0.026
> of it. ... alpha_prom +0.3710 [+0.1709, +0.5512] -- the pre-existing 7-13 Hz median-over-all-channels
> version of the same idea, ALREADY IN THIS PROJECT'S REGISTRY AND ALREADY EXTRACTED, works too."*

**Confirmed alive, on this exact cohort, at rho +0.4440 [+0.2480, +0.6104] (`smr_predictor_db`) and +0.3710
[+0.1709, +0.5512] (`alpha_prom`).** Both survive a placebo (outcome permuted, 2000 draws) and both survive
partialling out mental rotation (E132: "+0.4294 after partialling out mental rotation — spatial ability
removes essentially nothing"). This is a genuinely alive, non-trivial incumbent on the identical 87 subjects
— exactly what rule 45 requires and rule 53 requires be checked rather than assumed.

---

## 4. Rule-86 audit — could the incumbent and the outcome share an observer, moment, or procedure?

**No, on every pairing this design could use.**

| pair | provenance | same observer/moment/procedure? |
|---|---|---|
| `Perf_RUN_3..6` (outcome) | Real-time output of OpenViBE's automated left/right motor-imagery classifier during four online feedback runs. Machine-scored; no rater, no clinician, no human judgement in the loop at all. | — |
| `smr_predictor_db` / `alpha_prom` (incumbent) | Signal-processing pipeline (Welch PSD, Laplacian re-reference, dB-excess-over-background fit) applied offline to a 120 s eyes-open baseline recording, made **before** the four online runs. | **No shared observer with the outcome** — one is a fixed DSP pipeline, the other is a different piece of software (the online decoder); neither involves a human rater. |
| `Manual activity` (candidate) | A pre-session self-report item, administered by an experimenter as part of demographic intake, **before any EEG is recorded** (confirmed by its position in the file's own `Demographic and Biosocial Info` section, §1). | **No shared observer, moment, or procedure with either the incumbent or the outcome** — it is a fixed biographical fact reported once, at intake, disjoint in time and instrument from both the baseline DSP extraction and the online classifier. |

Rule 86 exists to catch designs where "beating the incumbent" secretly reduces to "reproducing an observer"
(RASS vs. GCS-motor, both charted by the same nurse in the same round, E204/E205). **No leg of this triangle
—candidate, incumbent, outcome— involves a human rater at all.** The escape is structural, not argued: there
is no observer to share. This is the same conclusion `PROBE_2026_08_02_DREYER_CHALLENGE_B.md` §4 reached;
verified independently here from the raw provenance rather than accepted on the probe's say-so.

---

## 5. Rule-70 audit — what is a candidate ALLOWED to be, and does `Manual activity` clear it?

**Allowed:** a measurement of the subject taken with no reference anywhere in its own construction to the
outcome, its timing, trial count, run index, or classifier confidence (the rule's own wording, written after
`mean_triallength` — E149 — smuggled trial count into a "feature").

**`Manual activity` clears it, and the clearance is structural rather than incidental:**
- It is collected once, at intake, **before the EEG baseline is recorded and before any of the four online
  BCI runs exist** — confirmed by its position in the file (`Demographic and Biosocial Info`, index 16,
  before `Mental Rotation` at 18 and `PRE-session` at 21).
- Its value is a **fixed biographical fact** (how often the subject practises a manual hobby in ordinary
  life), with no mechanism by which it could be computed from, or adjusted in response to, `Perf_RUN_3..6`,
  a trial count, a run label, or classifier output. Contrast with `mean_triallength` (E149), which was
  *mechanically* the inverse of accuracy in its own task; there is no analogous mechanical link here.
- It is distinct from the six `POST_*` columns in the same file (`POST_Mood, POST_Mindfulness,
  POST_Motivation, POST_Cognitive load, POST_Agentivity, POST_Expectations_filled`), which sit in the
  `Participant POST-session` section (index 36+) and are measured **after** the four online runs —
  `POST_Agentivity` was tested once (E132) and withdrawn for exactly this reason. `Manual activity` cannot
  be confused with this group; it is fourteen columns earlier in the file, in a different named section,
  and was recorded before the subject had ever attempted the task.

**Nothing in this design violates rule 70.** The one column excluded from the broader Dreyer questionnaire
block on separate grounds, `Interrogation`, is not part of this design at all.

---

## 6. The design

### Primary
`spearman(Manual_activity, mean(Perf_RUN_3..6))` over the 87-subject cohort, mean taken over whichever of
the four runs are non-missing per subject (the convention E129/E132 already use on this file). **Predicted
positive**, per Rimbert 2018 (PMID 30728772, verified via NCBI efetch above): *"BCI performance is correlated
to habits and frequency of practicing manual activities"* (ρ = 0.381, r = 0.473, p < 0.04, n = 35).

### Gates (each constructed to be able to FAIL — rule 40)

- **G1 — cohort integrity.** The join of `dreyer_performance.csv` × `dreyer_smr.*.csv` (OE run only) on
  `SUJ_ID`/`subject` must yield ≥ 50 subjects with zero duplicate ids. (Currently 87/87, 0 duplicates — but
  this is a live check against the join code, not a tautology; a re-extraction or a shard merge bug could
  break it, exactly as E145's estimator bug did for a different design.)
- **G2 — outcome alive.** Reproduce E125/E129's outcome-aliveness gate unchanged (median online accuracy
  against the derived Binomial(160, 0.5) chance threshold). This gate could fail if the outcome file
  changes or is re-extracted differently; it is not re-derived here, it is re-run.
- **G3 — incumbent alive, on THIS join.** `spearman(smr_predictor_db, mean accuracy)` on the exact cohort
  this design assembles must exclude zero and be positive. This is not assumed from E129's number — it must
  be recomputed on this design's own join, because a subtle join error (e.g. losing the one subject with
  missing `Perf_RUN_5/6`, or mis-joining `dreyer_smr`'s OE-only rows against `dreyer_graph`'s OE+CE rows)
  would silently change the cohort without changing the subject count.
- **G4 — candidate not degenerate (rule 74).** `Manual activity` must retain ≥ 3 distinct values with no
  single level holding > 90% of subjects. (Currently 5 distinct values, max share 35.6% — passes with large
  margin, but the check is registered as code, not asserted from this document.)

### Placebo (rule 55/88 — must be able to move the primary, and must permute the right thing)

**Permute the (`Manual activity`, outcome) pairing across subjects, 2000 draws**, exactly the template
E129/E131/E132 already use on this file ("candidate permuted across subjects, 2000 draws; inside the
central 95% is WITHDRAWN in EITHER direction"). This is deliberately **not** a covariate-matching placebo of
the kind rule 88 forbids (E230/E231's fatal error: permuting a matching covariate while leaving the
contrast's own subject pairing intact, which cannot move a whole-arm effect). There is no matching procedure
in this design to exploit that failure mode — the estimand **is** the subject-level correspondence between
`Manual activity` and accuracy, and permuting exactly that correspondence is the one operation guaranteed to
be able to change Spearman ρ, because ρ is a function of nothing else. **What this placebo destroys:** the
pairing between a given subject's questionnaire answer and that same subject's accuracy. **What it leaves
untouched:** the marginal distribution of `Manual activity` (still 6/18/13/31/19), the marginal distribution
of accuracy, the incumbent's own correlation, and every gate above. That is the correct match of destruction
to estimand (rule 55's own check, applied before registering rather than after a gate fails).

### Verdict rule — wrong-direction case enumerated FIRST (rule 37, four prior occurrences of getting this wrong)

```
if ci_high(rho) < 0:
    # WRONG DIRECTION — checked FIRST, not folded into "null"
    verdict = "REFUTES: excludes zero on the NEGATIVE side, opposite Rimbert's finding"
elif ci_low(rho) <= 0 <= ci_high(rho):
    verdict = "NULL — CI includes zero. State the power context (Section 2) alongside:
               this design has ~80% power for rho>=0.30 and ~46% for rho=0.20, so a null
               here is decisive against a Rimbert-sized effect and NOT decisive against
               a small one."
elif ci_low(rho) > 0:
    if point_estimate(rho) outside placebo_central_95_interval:
        verdict = "SUPPORTED — replicates Rimbert 2018 in an independent cohort"
    else:
        verdict = "UNRESOLVED — CI excludes zero by the bootstrap but the point estimate
                   sits inside the permutation placebo's own spread; report both intervals,
                   do not round this up to SUPPORTED (rule 46 — do not let one Monte Carlo
                   comparison stand in for a considered verdict)"
```

No other branch exists; every possible CI position is covered, and the branch most likely to be
mis-written by habit (wrong direction) is checked first and named explicitly, per rule 37's own diagnosis of
its four prior failures ("write the verdict branch to state the failing case first").

### Secondaries (reported whole, per rule 59 — not selectively transcribed)

- **S1 — partial correlations**, mirroring E132's template exactly: `partial(Manual_activity, accuracy |
  smr_predictor_db)` and `partial(smr_predictor_db, accuracy | Manual_activity)`. Answers whether a
  positive primary is independent information or redundant with the incumbent, and whether the incumbent
  survives controlling for manual activity (as it survived controlling for mental rotation in E132).
- **S2 — redundancy check.** `spearman(Manual_activity, smr_predictor_db)` reported directly (the same
  check E132 ran for mental rotation, `rho = -0.1190`), to characterise rather than assume the relationship
  between the new candidate and the incumbent.
- **S3 — leave-group-out robustness (rule 89).** A rank correlation across an ordinal variable with an
  extreme, small-n level (here, level 1 = "never," n = 6) can be a threshold effect in disguise rather than
  a gradient — rule 89's own diagnosis, from a different design, was that leave-one-out looks robust while
  leave-*group*-out reveals the split. Drop the 6 subjects at level 1 and recompute the primary; report
  both. Not a gate — a disclosure.
- **S4 — same statistic as the source.** Report **both** Spearman ρ and Pearson r (Rimbert's own paper
  reports both: r = 0.473, ρ = 0.381), so the number is directly comparable to the cited source rather than
  an analogue of it (rule 42 — a quotation, and a replication, supports only what it is actually the same
  measurement of).

**No multiplicity correction is needed or applied**, because this is **one pre-specified primary test**, not
a sweep — the explicit thing `INCUMBENT_REGISTRY.md`'s own corrected entry warns against ("a 28-column sweep
on n=87 against a measured detection floor near rho_partial 0.40 is not a test"). This design tests exactly
the one column the literature licenses, and none of the other 27 untested Dreyer questionnaire columns.

### Scope and limitations to state in the registration itself

- **Construct match is strong but not proven identical.** Dreyer 2023's `Manual activity` item
  (5 = every day … 1 = never, confirmed from the paper's own data descriptor) and Rimbert 2018's "frequency
  of practicing manual activities" (none/yearly/monthly/weekly/daily) are both 5-level ordinal habitual-
  practice-frequency self-reports, and **Rimbert is a co-author of the Dreyer 2023 descriptor** (Dreyer,
  Roc, Pillette, **Rimbert**, Lotte — PMID 37670009), which is circumstantial support for deliberate
  continuity of the same instrument rather than coincidence. It is not a verified item-for-item identical
  questionnaire (no shared data dictionary was found), and the registration should say this rather than
  assert identity.
- **Single deposit, single session.** As with every prior Dreyer registration, this cannot speak to whether
  the effect transports to Stieger (E131 already found the incumbent itself does not) or to any other
  cohort.
- **The power asymmetry from §2** — adequately powered for the literature's own effect size, not for a
  small one — must be stated in the registration's own docstring before the run, not discovered afterward.

---

## 7. Recommendation

**Register it.** Every gate that could have killed this design at the feasibility stage clears:

1. The column exists, is 100% populated, is genuinely 5-level ordinal, and is independently confirmed
   (from the source data descriptor, not just this deposit) to encode habitual practice frequency — the
   exact construct Rimbert's finding is about.
2. **Power is adequate for the literature-quoted effect** (95.7% at ρ = 0.381, n = 87), because the design
   under consideration is a plain bivariate correlation (floor ≈ 0.297 at 80% power) and **not** the harder
   out-of-bag increment test whose ≈0.40 floor comes from a different statistical task (E163). Conflating
   the two floors would have wrongly killed a design that is, in fact, reasonably well powered.
3. The incumbent (SMR predictor / `alpha_prom`) is independently verified alive on this exact cohort from
   the ledger, quoted verbatim, not taken on trust.
4. Rule 86 does not apply — no leg of candidate/incumbent/outcome involves a shared human observer, because
   none involves a human rater at all.
5. Rule 70 is clean — `Manual activity` is a pre-EEG, pre-task demographic self-report with no mechanical
   or referential path back to the outcome, structurally distinct from the `POST_*` columns that already
   failed this check once in this exact file (E132).
6. A placebo that can actually move the primary statistic is specified (permute the candidate-outcome
   pairing itself, not a matching covariate — the rule-88 distinction), and the verdict rule enumerates the
   wrong-direction case first, per rule 37's four prior failures.

**What would have made me recommend against it:** if the literature effect size had been unavailable or
much smaller than 0.30 (it is not — Rimbert reports 0.381), or if `Manual activity` had turned out
near-constant or largely missing (it is 100% populated across 5 real levels), or if the only available
design were the out-of-bag increment test against the ≈0.40 floor rather than a plain correlation (it is
not — a plain correlation is the design that matches both Rimbert's own analysis and this project's own
E129/E132 precedent on this exact file). None of those conditions held. The honest qualification is the one
in §2: **a null result here would be decisive evidence against an effect of Rimbert's reported size, and
inconclusive (not decisive) against a smaller one** — that sentence belongs in the registration's own
docstring, not discovered after the fact.
