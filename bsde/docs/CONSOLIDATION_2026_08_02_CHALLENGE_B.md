# Consolidation, 2026-08-02 — Challenge B: spontaneous EEG predicting command-following

*Written after E238. Not a registration, not a ledger row. Every ledger fact below is read directly from
`bsde/governance/REGISTRATION_LEDGER.jsonl` (44 rows tagged `challenge: "B"`, plus 3 related rows tagged
`B?` / `B/cross-cutting`, enumerated in full below) and from `bsde/src/bsde/experiments/e238_eeg_over_self_report.py`.
Citations were re-verified against NCBI E-utilities in this session (`efetch.fcgi`), not WebFetch (rules 25,
39) — the raw abstract text is quoted where it matters. File existence was checked with `ls -la` before any
claim that a deposit is cached, not assumed from a prior document.*

**Challenge B, as actually briefed** (`CHALLENGE_DEFINITIONS_CORRECTION.md`, quoting `UCE_AND_THE_THREE_CHALLENGES.md`
verbatim): *"spontaneous EEG predicting command-following."* Not BCI aptitude in healthy volunteers — that
substitution is itself untested, a point this consolidation returns to in §2(c).

---

## 1. Every Challenge B experiment in the ledger, enumerated

`incumbent` is quoted verbatim from the ledger field, including where it is literally `None` — a registered
row with no incumbent is a fact about that row, not an omission to paper over. `outcome` is the ledger's
categorical field, verbatim. The right-hand quote is the load-bearing phrase from `outcome_detail`, verbatim
in quotation marks.

| id | deposit (verbatim, trimmed) | incumbent (verbatim) | outcome | verdict quote (verbatim from `outcome_detail`) |
|---|---|---|---|---|
| e28 | eegmmidb | "relative_alpha_power as a declared-weak proxy for Blankertz 2010 (PMID 20303409)" | gate_failed | "P1(a) FAILED at 16.3% against a registered floor of 20%... verdict ABSENT (rule 31)." |
| e38 | physionet eegmmidb, 104 healthy subjects... trial-level cache from the same decoder E28 used | None | positive | "LABEL VIABLE... r_sb +0.2918 [+0.1163,+0.4345]... CEILING = sqrt(r_sb) = 0.5402." |
| e41 | physionet eegmmidb, 104 subjects with a resting row and an imagery label | None | negative | "UNDERPOWERED NULL for the primary... but the INCUMBENT is real... relative_alpha_power rho +0.2018 [+0.0050, +0.3857]" |
| e42 | eegmmidb, re-extracted with 20 candidates | None | positive | "REFINED as registered, and it does NOT survive multiplicity... lrtc_alpha +0.2446 [+0.0638,+0.4126]... but NOTHING survives FWER 0.05." |
| e56 | eegmmidb, fully local, 104 subjects | "exponent_low, the measure used before E42" | suggestive but not decisive | (descriptive only; no verdict string in `outcome_detail`) growth "in the direction attenuation predicts, then drops at k=45" |
| e63 | Stieger 2021 (figshare 13123148), 186 sessions, labels only | None | absent | "ABSENT at G2, the exchangeability gate, which is the gate working." |
| e68 | Stieger 2021, 185 sessions, labels only | None | positive | "PREMISE SUPPORTED, decisively, and this is the result that unblocks Challenge B... R1 WITHIN-SESSION = 0.9652." |
| e73 | Stieger et al. MI-BCI, 62 subjects | None | negative | "CHALLENGE B'S FIRST INTERPRETABLE NULL... THE PRIMARY WAS NOT THE NETWORK MEASURE IT WAS CHOSEN TO BE." |
| e82 | OpenNeuro ds007554, 15 subjects | None | gate_failed | "G2 FAILED AND THE GATE WAS RIGHT... the primary was not evaluated." |
| e83 | ds007554, sub-001 excluded | None | gate_failed | "G2 FAILED AGAIN, AND THE LITERATURE CHECK AFTERWARDS SHOWS THE ANCHOR WAS THE WRONG STATISTIC." |
| e85 | ds007554 ERD time course | None | closed | "BOTH GATES FAILED AND THE STOPPING RULE WAS APPLIED AS REGISTERED. ds007554 is CLOSED for the covert-versus-passive contrast." |
| e86 | Stieger 62-channel graph table | None | positive | "PREDICTS in D1 -- Challenge B's first primary to clear its own gates -- and it comes with four qualifications" |
| e97 | Stieger 62-channel graph table, 186 sessions | None | positive | "TRAIT-LIKE, but only moderately... ICC(2,1) = +0.4288 [+0.2486, +0.5438]" |
| e101 | Stieger, 61 subjects with exactly 3 sessions | None | absent | "UNDETERMINED -- and it was named as the likely outcome before the first pass" |
| e106 | Stieger 62-channel graph table, same 62 subjects as E86 | None | positive | "IT IS THE NETWORK MEASURE -- but read the two caveats printed with the verdict before using it." |
| e108 | eegmmidb, ~105 subjects, new graph extraction | None | gate_failed | "ABSENT AT G2 -- the outcome is not alive enough to be predicted, so nothing about ge_norm was tested (rule 31)." |
| e114 | Stieger 62-channel graph table, 62 subjects | None | positive | "PASSES -- ge_norm predicts BOTH independent halves of BCI accuracy... IT DOES NOT ADDRESS BH q = 0.0920." |
| E124 | eegmmidb | None | negative | "NOT REPLICATED, and powered enough to EXCLUDE an effect of E86's size." |
| E125 | dreyer-bci-2023 | None | negative | "NOT REPLICATED, and it closes E86's last defence." |
| E129 | dreyer-bci-2023 | None | positive | "(c) REPLICATED, and it lands almost exactly on the attenuated expectation." |
| E131 | stieger | None | negative | "(b) DOES NOT WORK HERE, and it EXCLUDES Dreyer's +0.3710" |
| E132 | dreyer-bci-2023 | "smr_predictor_db" | negative | "NOT REPLICATED for the primary -- but P2 STRENGTHENS E129" |
| E134 | dreyer-bci-2023 | "smr_predictor_db" | negative | "AMENDED BY E163 -- THE WORD COMPREHENSIVE IS WITHDRAWN... zero of ten candidates add under the calibrated test either" |
| E143 | eegmmidb, 104 subjects, 32 candidates | None | gate_failed | "NO VERDICT as registered; two gates failed and they fail for different reasons." |
| E144 | eegmmidb, 104 subjects | None | gate_failed | "BOTH REGISTERED PREDICTIONS CONFIRMED, and the run is NO VERDICT because both gates failed... eegmmidb cannot support an increment test at n=104 under any rule." |
| E145 | Stieger, 186 sessions | None | blocked | "THE PRINTED VERDICT IS WITHDRAWN BY THE EXPERIMENT THAT RAN BESIDE IT... G2 failing says nothing about the incumbent (rule 31)." |
| E149 | eegmmidb and Stieger, same incumbent and same test | None | positive | "THE PRINTED VERDICT IS WRONG AND IS CORRECTED HERE... THE REAL RESULT IS THE EEGMMIDB ARM AND IT IS CLEAN." |
| E164 | Stieger, 123 consecutive session pairs | None | negative | "NEGATIVE AS REGISTERED, and the prediction was made for the right reason." |
| E167 | Stieger 2021 per-trial pre-cue table | None | gate_failed | "NOT INTERPRETABLE at G2, and the ONE repair rule 58 allows was spent before it failed." |
| E172 | Stieger 2021 per-trial pre-cue table, 27,900 trials | None | positive | "PRESENT, and it is Challenge B's first positive under a calibrated instrument." |
| E174 | Stieger sessions 2 and 3, 124 held-out sessions | None | negative | "NOT REPLICATED. E172's effect does not survive to held-out recording days from the same subjects, at greater power, with every gate passing." |
| E175 | eegmmidb, new per-trial pre-cue table | None | gate_failed | "GATE-FAILED AT G1, EXACTLY AS REGISTERED... only 8 subjects of 105 reach the registered floor of 20 pairs." |
| E179 | Stieger per-trial pre-cue table, simulated gating | None | positive | "USABLE at one of six cells, AGAINST MY REGISTERED PREDICTION OF NO USABLE GAIN... THROUGHPUT FALLS AT EVERY CELL." |
| E181 | Stieger per-trial tables, discovery/confirmation | None | positive | "CONFIRMED, against its own registered prediction of ABSENT ABOVE FLOOR. The graded outcome finds what the binary one does not, and it finds it in the OPPOSITE valence." |
| E184 | Stieger per-trial tables, discovery/confirmation | None | negative | "SLOWER at every one of six cells -- the registered wrong-direction branch, and it fires by roughly a factor of twenty." |
| E188 | Dreyer 2023, 87 subjects, real EMG channels | None | absent | "ABSENT ABOVE FLOOR in BOTH arms... THE MUSCLE READING IS EXCLUDED BY MEASUREMENT, not by assumption." |
| E192 | Forenzo & He continuous-pursuit BCI, session Se01 | "E181 own discovery value... mu_mean = 0.4803 [0.4681, 0.4925]" | gate_failed | "NOT INTERPRETABLE at G2, and G2 is the gate this design was given precisely to catch this. THE BCI IS NOT ALIVE IN SESSION 1." |
| E199 | Forenzo & He, each subject FINAL session | "E181 own discovery value loaded from its JSON" | gate_failed | "NOT INTERPRETABLE at G2 again... THE GATE IS NOW THE SUSPECT, NOT THE COHORT." |
| E201 | Forenzo & He, chance-run reference | "E181 mu_mean = 0.4803 [0.4681, 0.4925]" | absent | "ABSENT ABOVE FLOOR, the registered prediction, and this is now the strongest statement Challenge B has." |
| E204 | HEEDB, 67,202-patient EEG cohort | "RASS, the bedside sedation score, entered as the BASELINE design rather than named as a confound" | withdrawn | "WITHDRAWN -- ITS FEATURES WERE COMPUTED ON THE WRONG DATA, found while profiling the extractor for speed." |
| E205 | HEEDB, the E204 cohort | "sedative exposure from the OMOP drug table as the baseline" | closed | "CLOSED UNRUN, superseded by E212 before its data existed... sedative status is IDENTICAL on both members of all but 6 of 181 discordant pairs." |
| E212 | HEEDB, 540 discordant pairs | "TWO, both declared before the run. I1 RASS... I2 any_sedative" | gate_failed | "SECOND RUN, ONE REPAIR APPLIED, G3 FAILS AGAIN, AND BY RULE 58 THE RUN IS OVER: METHOD FAILS." |
| E221 | HEEDB, 125 pairs with RASS identical | "RASS, held constant by matching rather than modelled" | negative | "ABSENT, and my registered prediction is confirmed... THE NEGATIVE CONTROL IS THE MOST INFORMATIVE LINE IN THE TABLE." |
| **E238** | Dreyer MI-BCI, 87 subjects | "Manual activity, Dreyer's pre-session self-report, licensed by Rimbert 2018 PMID 30728772 (rho 0.381, n=35)" | negative | "INCUMBENT DEAD by the registered rule, and the finding is a well-powered NON-REPLICATION of a published result." |

**Three related rows, tagged `B?` or `B/cross-cutting`, not `B`, included for completeness because they
bear directly on Challenge B:**

| id | deposit | incumbent | outcome | verdict quote |
|---|---|---|---|---|
| e20 | ds004541 | None | closed | "WITHDRAWN as uninterpretable — 39 of 62 channels not EEG" (predates the Challenge-B framing; not a command-following test) |
| e45 | ds005385, 5-year retest | None | positive | reliability study across measures generally; supplies E56's attenuation-ceiling arithmetic, tests no Challenge B candidate |
| e54 | 745 healthy adults, 3 deposits | None | NEGATIVE for Challenge B | "age and sex explain 0.03% of its between-subject variance. Gain = 1.000." |

**47 rows total that touch Challenge B in some form. Zero of them establish that spontaneous EEG predicts
genuine command-following in a disorders-of-consciousness patient — the construct the brief names.** Every
row above tests one of three substitute constructs: motor-imagery/BCI aptitude in healthy volunteers
(eegmmidb, Stieger, Dreyer, Forenzo & He — 37 rows), clinician-assessed GCS-motor obeying in HEEDB ICU
patients (5 rows), or a machinery/reliability prerequisite for one of those (e38, e45, e54, e63, e68, e97,
e101 — several already counted above).

---

## 2. What is established

### (a) Shown FALSE

- **Rimbert 2018's manual-activity finding does not replicate.** E238, well-powered (80%-power floor
  ρ = 0.2965 at n = 87, declared before the run): observed ρ = **−0.0841**, permutation |p| = 0.4368,
  against the published **ρ = 0.381** (verified against the MEDLINE full text in this session — see §4).
- **No resting-state BCI-aptitude predictor transports across even two of the three healthy-BCI cohorts
  tested.** `ge_norm` predicts in Stieger (E86, +0.307) and fails in eegmmidb (E124, −0.1298 [−0.3225,
  +0.0735]) and Dreyer (E125, −0.2065 [−0.3921, −0.0003], inside its own permutation interval). The
  Blankertz/SMR family (`alpha_prom`, `smr_predictor_db`) replicates in Dreyer (E129, +0.4440) and fails in
  Stieger (E131, +0.0747 [−0.1968, +0.3294], excluding Dreyer's value). E131's own words: **"NO PREDICTOR
  WORKS IN BOTH"** cohorts.
- **The trial-level pre-cue alpha effect (E172) does not replicate.** Held-out sessions from the same
  subjects (E174): "E172's effect does not survive to held-out recording days"; an independent deposit with
  a real EMG channel (E188): "ABSENT ABOVE FLOOR in BOTH arms."
- **The graded execution-speed effect (E181) does not replicate externally.** Three tests on an independent
  28-subject cohort (E192/E199/E201, the last with a corrected aliveness gate): "ABSENT ABOVE FLOOR... on a
  cohort where the paradigm is demonstrably working."
- **Geronimo 2016's negative on device-throughput gating replicates, twice, including in the one place most
  likely to overturn it** (E179's own accuracy-gating cells, E184's dedicated speed-gating test): "SLOWER at
  every one of six cells... by roughly a factor of twenty."
- **Mental rotation (Jeunet 2015) does not predict BCI accuracy in Dreyer** (E132, −0.1700 [−0.3833,
  +0.0434], inside its permutation interval) — though it does not confound E129 either.
- **`wpli_alpha_global_efficiency` is not a network measure distinct from mean connectivity strength** (E73:
  ρ = +0.9962 with mean degree) — a methodological finding, not a substantive one, but it falsifies the
  premise of that specific test.
- **`ge_norm`'s Stieger association does not survive multiplicity correction** (BH q = 0.0920 across its
  family, stated at registration and never resolved — E86 through E114).

### (b) Shown TRUE

- **eegmmidb's per-subject motor-imagery label has low split-half reliability**, r_sb = +0.2918
  [+0.1163, +0.4345], implying an attenuation ceiling of 0.5402 (E38) — genuinely low, not an artefact, and
  it caps every correlational design run on that deposit.
- **Stieger's label reliability is far higher**: within-session 0.9652 [0.9568, 0.9706], ceiling 0.9825
  (E68) — confirming E38's claim that reliability, not subject count, was the binding constraint.
- **`relative_alpha_power` (the weakened Blankertz proxy) has a real, small, marginal correlation with
  imagery ability on eegmmidb**: +0.2018 [+0.0050, +0.3857] at 20,000 resamples (E41) — but it does **not**
  survive as an out-of-bag increment predictor at n=104 under any tested rule (E143, E144: "the incumbent is
  simply not out-of-bag predictive on eegmmidb").
- **The Blankertz SMR predictor replicates almost exactly at its attenuation-corrected expected size in
  Dreyer**: observed +0.4440 [+0.2480, +0.6104] against a predicted +0.4183 (E129) — the single cleanest
  positive result in the whole programme.
- **RASS is an extremely strong within-observation predictor of GCS-motor obeying** (E204: +0.3513
  [+0.3280, +0.3730] over an intercept-only model) — real, and precisely the shared-measurement-act problem
  catalogue rule 86 describes.
- **Sedative exposure (`any_sedative`) barely varies within a patient across two assessments that
  disagree on obeying commands** — identical on all but 6 of 181 pairs (E205), all but 20 of 540 (E212) — a
  measured fact about the HEEDB cohort, not an assumption.
- **No public dataset currently reachable by this project pairs task-free resting EEG with a per-patient
  command-following label in disorders of consciousness** (§4 below; see also `PROBE_2026_08_02_CHALLENGE_B_GAPS.md`
  §3, Q9).

### (c) Untested

- **Whether resting-EEG BCI-aptitude in healthy volunteers transfers to command-following capacity in a
  brain-injured patient at all.** `CHALLENGE_DEFINITIONS_CORRECTION.md`, verbatim: *"That proxy relationship
  was never stated, never justified, and never tested."* Every eegmmidb/Stieger/Dreyer/Forenzo row above is
  evidence about the proxy construct, not the briefed one.
- **The HEEDB residual: whether EEG predicts command-following within a patient across the 415-534 (of 540)
  discordant pairs where RASS differs between the two assessments.** E212 died on estimator machinery
  ("METHOD FAILS," rule 58 — the run is over, not the question) before this could be tested; E221 tested
  only the RASS-matched subset (125 of 540 pairs, 23%), which by construction discards exactly the pairs
  where sedation changed.
- **Dreyer's ILS (8 columns) and 16PF5 (20 columns) questionnaire blocks** — flagged as untested by
  `INCUMBENT_REGISTRY.md` and confirmed untested in the ledger; E238 tested only `Manual activity`, the one
  column Rimbert 2018 actually licenses.
- **Genuine covert command-following in disorders of consciousness — the flagship construct itself**
  (a CRS-R-negative, fMRI/EEG-positive patient). Zero of 47 rows touch this. Not analytically blocked:
  **structurally blocked on data access** (§4).

---

## 3. The central structural problem

Catalogue rule 86: *"an incumbent that shares a measurement act with the outcome sets a bar nothing external
can clear."* Its converse, observed repeatedly in this programme: an incumbent independent of the outcome's
measurement act, but too weak, too invariant, or too cohort-specific to be a real bar at all. Every
Challenge B design that named an incumbent falls into one column or the other — never a third case where an
incumbent was both independent and genuinely alive on the target construct.

| incumbent | deposit(s) | observation, or exposure/objective measure? | alive? | what happened |
|---|---|---|---|---|
| `relative_alpha_power` (declared-weak Blankertz proxy) | eegmmidb | Objective (EEG-derived spectral measure; no clinician involved) | Marginally alive as a bivariate correlation (+0.2018, E41); **dead** as an out-of-bag increment predictor (E143, E144) | Not a rule-86 case — no shared observer with the outcome — but fails a different way: too weak to survive the estimator it needs to be useful in |
| SMR predictor / `alpha_prom` (Blankertz 2010) | Dreyer / Stieger | Objective (EEG-derived) | Alive in Dreyer (+0.4440, E129); **dead** in Stieger (+0.0747, E131) | Independent of the outcome's measurement act, but cohort-specific — "NO PREDICTOR WORKS IN BOTH" (E131) |
| **RASS** (bedside sedation score) | HEEDB | **Observation** — clinician-charted, same bedside round as the outcome | **Alive, powerfully** (+0.3513, E204) | **The textbook rule-86 case.** Alive precisely because it is close kin to the outcome; the EEG increment over it is uninterpretable evidence about the brain, whatever its sign |
| `any_sedative` (OMOP drug-exposure record) | HEEDB | **Exposure/objective** — a drug administration record, no clinician judgement | **Dead** — identical on 175/181 (E205), 520/540 (E212) discordant pairs | The converse case: genuinely independent of the outcome's measurement act, and dead for an unrelated reason — it does not vary enough within a patient to discriminate anything |
| `Manual activity` (Rimbert 2018 self-report) | Dreyer | Independent — subjective self-report, but pre-session, machine-scored outcome, no shared clinician or moment | **Dead** (−0.0841, well-powered non-replication, E238) | Escapes rule 86 by construction (E238's own design note: *"no observer is shared by any pair of them"*) and is dead anyway |

**The pattern, stated plainly.** The one incumbent that was ever unambiguously *alive* on its own construct
(RASS) is alive *because* it shares a measurement act with the outcome — which is precisely what makes a
comparison against it uninformative about the brain. Every incumbent this project has found that is
genuinely independent of the outcome's provenance — `any_sedative`, `Manual activity`, and the
cross-cohort SMR/`ge_norm` family taken as a whole — has been dead, either structurally (too little
within-patient variance to discriminate anything) or empirically (a real but cohort-specific or
sub-threshold correlation that does not survive the next test). **This project has never had both
properties — independence and life — in the same incumbent at the same time**, and 47 registered
experiments is enough attempts that this reads as a property of the available deposits rather than of any
one design.

---

## 4. What would unblock it

**Property a deposit needs**: task-free (or clearly pre-task) EEG, a per-patient command-following label
that is not itself the thing being predicted (i.e., not the same clinician score used as if it were both
incumbent and outcome), and enough patients/sessions to power a within-subject or between-subject test at
the effect sizes this programme has actually observed (ρ ≈ 0.2–0.4, attenuated further by whatever the
label's own reliability turns out to be — E38's lesson generalises to any new deposit).

**Chennu 2014 (WBIC), the only DoC deposit with a genuine command-following label located across PubMed,
OpenNeuro, Dryad, Zenodo, OSF, Figshare and PhysioNet** (`DATA_REQUEST_WBIC_CHENNU.md`). Access statement,
quoted verbatim from the paper's own data-availability text (PMID 25329398, PMC4199497):

> *"data are available by request to either the study authors or the Wolfson Brain Imaging Centre's data
> protection officer (enquiries@wbic.cam.ac.uk) for researchers who can meet the requisite ethical criteria...
> subject to case-by-case review."*

**Status, verified against `git log`**: `PROBE_2026_08_02_CHALLENGE_B_GAPS.md` records that the request
"sits **drafted 2026-07-30, unsent**" — confirmed again here: the file header itself reads **"Status:
drafted 2026-07-30, NOT SENT."** Nobody has emailed WBIC. This is the single highest-leverage unsent action
available to the project for Challenge B's flagship construct.

**Bath prolonged-DoC motor-imagery dataset (DOI 10.15125/BATH-01632)**, N=42 (UWS 14, MCS 17, LIS 11, plus
2 able-bodied), structured motor-imagery BCI to auditory cues with session-linked CRS-R and WHIM scores.
`DEPOSIT_ACCESS_STATUS.md` describes it, quoted verbatim, as *"requested 2026-07-30, is the pre-registered
target of E18 and there is no public substitute"* — no ledger row `e18` exists (confirmed by grep against
`REGISTRATION_LEDGER.jsonl`), so this was a planned design that was never actually registered or run; the
label is carried here rather than corrected, since the substance (Bath is the target, and it is unrun) is
what matters. Access statement, quoted verbatim from the record (`MASTER_PLAN.md` §9.24):

> *"a brief description of the proposed research use, evidence of relevant ethical approval, and agreement
> to data use conditions that prohibit data redistribution or use beyond the approved scope."*

`MASTER_PLAN.md`'s own assessment, quoted: **"The ethical-approval requirement is the real gate — and it is
not something this project can satisfy by asking politely — it needs an institutional sponsor."**
`MASTER_PLAN.md` line 88, quoted verbatim: *"**access request required** — VERIFIED restricted; no named
open licence; redistribution prohibited by the landing page's own text."*

**Whether a request was actually sent is not consistently stated and could not be verified.** Unlike
Chennu, there is no `DATA_REQUEST_BATH*.md` file and no commit touching one (`git log --all -- '*bath*'`
returns only the file-location note at §9.24). `MASTER_PLAN.md`'s own action-item list still reads **"File
the Bath access request"** as something outstanding at one point in the document, while a later section
(§9.34, `outcome` table) reads **"Bath access requested, not granted"** as though it had been done by then.
Both sentences are quoted above rather than reconciled, because the repo does not contain the evidence to
reconcile them — no draft email, no correspondence, no git-tracked artefact of a request having gone out.
**This should be resolved by asking the investigator directly whether Bath has actually been contacted,
rather than assumed either way.**

Two files are already open without any request (supplementary decoding-accuracy tables), which is enough to
draft a pre-registration in advance but **not enough to develop or test an EEG feature — it contains derived
accuracies, not signal** (`MASTER_PLAN.md` §9.24, quoted).

**Fallbacks already on record, each weaker than the last** (`DATA_REQUEST_WBIC_CHENNU.md`'s own ordering,
quoted): (1) the Della Bella/Sitt cohort (PMID 40796934, OSF node `nfwyj`, 237 patients, public table) —
*"CRS-R total is not command-following, so this substitutes a coarser label rather than the one the
challenge names"*; (2) the healthy-BCI substitution already run to exhaustion in §1-2 above, which the same
document states *"remains an analogy under test"* with *"no published work tests transfer from healthy or
sedated populations to DoC in either direction"*; (3) MOAA/S on DOSE-I as a responsiveness ladder, which the
same document says would *"import exactly the error the challenge exists to detect"* (behavioural
unresponsiveness and consciousness dissociate under anaesthesia, PMID 26752078 — the same failure mode
covert command-following describes).

**A survey fact that closes off looking for a fourth alternative**: OpenNeuro was enumerated exhaustively
(1,834 datasets, 517 with EEG, 36 keyword matches) and **"not one of the 36 is a disorders-of-consciousness
cohort"** (`DEPOSIT_ACCESS_STATUS.md`). The BDSP Neurotech BIDS path, separately, lists 0 objects.

---

## 5. Recommendation

**BLOCKED ON DATA, for the construct the brief actually names (Q9: genuine covert command-following in
disorders of consciousness).** No experiment changes this. What would change it: sending the drafted WBIC
email (`DATA_REQUEST_WBIC_CHENNU.md`, confirmed unsent by its own header) and confirming and, if
necessary, actually filing the Bath access request through an institutional sponsor who can supply the
ethical-approval evidence the record requires (§4 — the repo's own account of whether that request has
already gone out is internally inconsistent and should be resolved with the investigator directly rather
than assumed). Both are outside the scope of a registered experiment, and at least the first has not been
done.

**Not blocked, but exhausted of reasonable incumbents, for the healthy-volunteer BCI-aptitude proxy branch.**
Every literature-licensed non-observational incumbent this project could find on eegmmidb/Stieger/Dreyer
(Blankertz SMR, `alpha_prom`, `ge_norm`, mental rotation, manual-activity habits) has now been tested; none
transports across more than one cohort, and E238 closes the last one on Dreyer specifically. Continuing to
iterate incumbents on these three healthy-volunteer deposits has diminishing returns, because the unresolved
question was never "does something beat this incumbent" — it is whether the whole proxy relationship
(healthy-volunteer BCI aptitude standing in for patient command-following) holds at all, and that is
untestable on healthy-volunteer data by definition.

**One specific next experiment remains open and is not blocked on new data access**, if the investigator
wants Challenge B work to continue in the interim: **the HEEDB residual** — whether spontaneous EEG predicts
command-following within a patient across the discordant pairs where RASS *differs* between the two
assessments (415–534 of 540 pairs, depending on cohort version), using the **model-free within-pair
statistic E212 itself specified as the fix** ("a paired sign test on the candidate, stratified or matched on
RASS rather than adjusting for it in a fitted model — has no refit variance to pay for") rather than the
ridge/increment estimator that failed on machinery. The relevant cache exists **right now**
(`/tmp/eeg_probe/heedb_cmd_follow.p0-3.csv`, `.w0-5.csv`, `/tmp/eeg_probe/cmd_sedative_exposure.csv`, all
verified present via `ls -la` in this session) but per `CLAUDE.md`'s standing operational fact is not durable
across a container restart and is not committed to git. This is real progress on the incumbent problem in
§3 (RASS matched by stratification rather than modelled, avoiding rule-58's collapse) but it is still the
HEEDB clinical construct, not the flagship one — it would answer Q7, not Q9.

**What the project should do with the challenge in the meantime, if neither request is sent**: report
Challenge B honestly as unsolved for the construct it was briefed to solve, with the healthy-volunteer proxy
work reported as exactly that — a proxy, repeatedly shown not to transport even between two healthy
cohorts — rather than as progress toward the flagship question. `CHALLENGE_DEFINITIONS_CORRECTION.md`
already says this once; this document is the second time it has needed saying, and the record now has 15
more experiments' worth of evidence for it (E124 onward) than it did the first time.
