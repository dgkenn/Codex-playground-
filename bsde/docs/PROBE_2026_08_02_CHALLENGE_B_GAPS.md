# Probe 2026-08-02 — Challenge B: what is genuinely untested, from the project's own record

*Reconnaissance only, per instruction. No experiment, registration or ledger row is written here. Every
count below was produced from `bsde/governance/REGISTRATION_LEDGER.jsonl` (read in full, all 46 rows tagged
challenge `B`, `B/cross-cutting` or `B?`), `bsde/docs/MASTER_PLAN.md`, `bsde/docs/INCUMBENT_REGISTRY.md`,
`bsde/docs/QUEUE.md`, `bsde/docs/ANALYSIS_PLAN.md`, `bsde/docs/CONSOLIDATION_2026_08_02b.md`, and by
`ls`/`head`/`wc -l` against the actual files under `bsde/results/` and `/tmp/eeg_probe/`. Every PMID cited
is fetched live via NCBI E-utilities (`efetch.fcgi`), not WebFetch (rules 25/39) — the raw output is quoted
where it matters.*

---

## 1. Every Challenge B experiment ever registered (46 rows, enumerated)

Column `settled?` is one line on why the row did or did not close a question, not a restatement of the
outcome field. Outcome text is quoted verbatim (in quotation marks) from the ledger where it is the
load-bearing phrase; paraphrase is marked as such.

| id | deposit | question (verbatim, trimmed) | incumbent | outcome | settled? |
|---|---|---|---|---|---|
| **e20** | ds004541 | "awake pre-drug vs post-LOC on ds004541" | none named | closed | No — gate failed 5/7, then the whole result was **"WITHDRAWN as uninterpretable — 39 of 62 channels not EEG."** Not a command-following test of any kind (it predates the Challenge-B framing being applied to it; tagged `B?`). |
| **e28** | eegmmidb | "resting EEG predicts covert command-following" | `relative_alpha_power` as a declared-weak proxy for Blankertz 2010 (PMID 20303409) | gate_failed | No — P1(a) failed its own floor (16.3% vs 20%). Diagnosed as **"THE GATE ASKED THE WRONG QUANTITY (rule 30)"**: a prevalence floor applied to a detection rate at n=45/subject. Verdict ABSENT, and it named its own fix (reliability, not significance rate). |
| **e38** | eegmmidb, trial cache from E28 | "How much of E28's per-subject BCI label is real?" | none (measures the label, not a candidate) | positive | Yes, as a **prerequisite**, not an answer: `r_sb +0.2918 [+0.1163,+0.4345]`, ceiling `sqrt(r_sb)=0.5402`. Unblocked E28 to be re-run rather than answering whether EEG predicts anything. |
| **e41** | eegmmidb | "Does a resting-EEG feature predict per-subject motor-imagery decoding ability?" (E28's original primary, re-run against E38's ceiling) | none pre-E177 | negative | Partially — primary (`exponent_high`) is an **"UNDERPOWERED NULL,"** but incidentally found the incumbent alive: `relative_alpha_power rho +0.2018 [+0.0050,+0.3857]`, beating all 14 candidates. |
| **e42** | eegmmidb, 20 new candidates | "Does the temporal structure of resting alpha (LRTC) predict motor-imagery ability where magnitude does not?" | `relative_alpha_power` (E41) | positive | Half-settled — `lrtc_alpha +0.2446 [+0.0638,+0.4126]` clears the primary and a placebo (imagery vs executed dissociation), but **"NOTHING survives FWER 0.05"** (second look at the same 104 subjects) and is explicitly flagged **"promising and unclaimed"** pending independent replication. |
| **e45** | ds005385, 5-yr retest | Five-year ICC of each candidate measure, incl. `lrtc_alpha` | n/a (reliability study) | positive | Settles a **different** question (trait stability of measures generally) — supplies E56's attenuation-ceiling arithmetic for Challenge B but tests no candidate against BCI ability. |
| **e54** | 745 healthy adults, 3 deposits | "How much Challenge-B gain would a conditional (age/sex) reference buy?" | n/a | NEGATIVE for Challenge B | Yes — **"age and sex explain 0.03% of its between-subject variance. Gain = 1.000."** Clean, decisive null on this specific mechanism. |
| **e56** | eegmmidb | "Is Challenge B's marker ATTENUATED by a noisy label, or simply WEAK?" | `exponent_low` | suggestive but not decisive | No — verdict corrected mid-file (a ratio statistic was wrong, rule 33); final reading is **"UNDERPOWERED,"** growth consistent with attenuation but not distinguishable from weak at n=104. |
| **e63** | Stieger labels only | "Is Stieger's BCI-ability label decisively more reliable than eegmmidb's?" | n/a | absent | Machinery question — **"ABSENT at G2, the exchangeability gate, which is the gate working"** (odd/even halves non-exchangeable). Superseded in estimator by E68. |
| **e68** | Stieger labels only | Same, binomial-corrected estimator | n/a | positive | Yes for the prerequisite — **"R1 WITHIN-SESSION = 0.9652... The within-session attenuation ceiling rises from 0.5402 to 0.9825."** Still no candidate touched. |
| **e73** | Stieger, 10ch graph | "Does a resting NETWORK measure predict BCI ability?" | none named at registration | negative | Yes, **Challenge B's first interpretable null** — but its own primary (`wpli_alpha_global_efficiency`) turned out to be **"mean connectivity strength restated"** (rho +0.9962 with mean degree), so the null is about a mislabelled measure, not about networks generally. |
| **e82** | ds007554 | "Can anything separate covert command-following (motorimagery) from passive stimulation, within subject?" | `relative_alpha_power` (sensorimotor ERD anchor) | gate_failed | No — **"G2 FAILED AND THE GATE WAS RIGHT"**: the overt anchor (active vs passive) itself did not clear, wrong sign. Diagnosed as a reduction artefact (whole-run channel median). |
| **e83** | ds007554 | Same, per-trial cue-locked reduction | same anchor | gate_failed | No — anchor still wrong-signed; literature check (PMID 31425038, 27529874) showed passive movement produces its own ERD, explaining both failures. |
| **e85** | ds007554 | Same, early-window ERD latency | same anchor | closed | No — **"BOTH GATES FAILED AND THE STOPPING RULE WAS APPLIED... ds007554 is CLOSED for the covert-versus-passive contrast."** Third and final attempt, per its own pre-declared stopping rule. |
| **e86** | Stieger 62ch graph | "Does a network measure SHOWN to escape mean connectivity strength predict BCI ability?" | none pre-declared; `relative_alpha_power` reported alongside | positive | Yes, with four stated qualifications — `ge_norm +0.307 [+0.049,+0.534]` clears its placebo, but does **not** beat the incumbent (overlapping intervals) and **"BH q = 0.0920 — it does NOT survive"** multiplicity. |
| **e97** | Stieger 62ch graph | "Is `ge_norm` a TRAIT or a STATE?" | iaf (trait control), Gaussian (noise control) | positive | Settles E86's qualification-3 (D2 null is expected, not evidence against D1) but is a reliability question, not a new predictive test. |
| **e101** | Stieger, exactly-3-session subjects | Does session-averaging raise E86's correlation by the amount E97's ICC predicts (measurement-error) or by sqrt(k) (pure noise)? | two competing models from the same theory | absent | No — **"UNDETERMINED... BOTH models lie inside the interval."** 61 subjects cannot separate the hypotheses; calibration (G5) shows the machinery itself is sound. |
| **e106** | Stieger 62ch graph | "Is E86's result just individual alpha frequency?" | `iaf` | positive | Yes — **"ge_norm and iaf are nearly orthogonal: rho +0.0781."** Rules out the redescription reading, but flags the comparison itself as underpowered (both partials below the measured resolvability floor) and BH q=0.0920 "untouched and still stands." |
| **e108** | eegmmidb, new graph extraction | External replication of `ge_norm` (band-power decoder) | `ge_norm` (E86) | gate_failed | No test run — **"ABSENT AT G2... median imagery_auc 0.5306... only 16.3% beat their own permutation null"** vs a 20% floor. Outcome itself not alive; nothing about `ge_norm` was tested. |
| **e114** | Stieger 62ch graph, split-half | Does `ge_norm` predict BOTH independent trial halves? | none (internal consistency, not external replication) | positive | Yes for internal consistency — `+0.2909`/`+0.2967` both clear, **"does NOT address BH q = 0.0920... this is internal consistency, not external replication."** |
| **E124** | eegmmidb, CSP decoder | External replication of `ge_norm`, decoder now alive | `ge_norm` | negative | Yes, decisively — **"powered enough to EXCLUDE an effect of E86's size"**: `-0.1298 [-0.3225,+0.0735]`, excludes both E86's value and E101's attenuated expectation. |
| **E125** | dreyer-bci-2023 | Same replication, matching Stieger's ONLINE-CONTROL construct | `ge_norm` | negative | Yes — **"NOT REPLICATED, and it closes E86's last defence"**: `-0.2065 [-0.3921,-0.0003]`, inside its own permutation interval. Three-cohort picture: Stieger `+0.31`, eegmmidb `-0.13`, Dreyer `-0.21`. |
| **E129** | dreyer-bci-2023 | Does Blankertz 2010's SMR predictor (r=0.53) replicate? | none (this IS the incumbent test) | positive | Yes — **"REPLICATED... within 0.026 of"** the attenuated expectation, `+0.4440 [+0.2480,+0.6104]`. Also discovered `alpha_prom` (already extracted, never tested) works at `+0.3710`. |
| **E131** | stieger | Does the SMR predictor (`alpha_prom`) work in Stieger too? | none | negative | Yes — **"DOES NOT WORK HERE"**, `+0.0747 [-0.1968,+0.3294]`, excludes Dreyer's value. Reading: initial-aptitude vs learned-performance may be different constructs. |
| **E132** | dreyer-bci-2023 | Does mental-rotation score (Jeunet 2015) predict, and does it confound E129? | `smr_predictor_db` | negative | Yes for its primary — `-0.1700 [-0.3833,+0.0434]`; **strengthens** E129 (SMR survives partialling out mental rotation, `+0.4294`); one secondary (`POST_Agentivity`) withdrawn as invalid look-ahead. |
| **E134** | dreyer-bci-2023 | Does any graph measure add to the SMR predictor? | `smr_predictor_db` | negative | Amended by E163 — null stands but **"is only evidence ABOVE"** a floor of rho_partial ≈0.40, measured, not assumed, after the fact. |
| **E143** | eegmmidb | Does anything add to `relative_alpha_power` out of bag? | `relative_alpha_power` | gate_failed | No verdict — **"G2 FAILED... the incumbent... does NOT beat an intercept-only model out of bag"**; G3 (detectability floor) also failed on Monte Carlo resolution grounds. |
| **E144** | eegmmidb | Same, rank-based estimator | `relative_alpha_power` | gate_failed | No verdict, but decisively diagnostic — **"the incumbent is simply not out-of-bag predictive on eegmmidb"** at n=104; the detectability floor failure is now real (not MC artefact), i.e. eegmmidb cannot support this design at all. |
| **E145** | Stieger | Same design, on the deposit with the higher label ceiling | `relative_alpha_power` | blocked | No — printed verdict **"WITHDRAWN"**: E146 (referenced) showed the estimator itself is blind (0% detection where a closed-form test gets 88%), so the G2 failure says nothing about the incumbent. |
| **E149** | eegmmidb + Stieger | Under a calibrated increment test, is the incumbent alive, does anything add, do increments agree cross-deposit? | `relative_alpha_power` | positive | Yes on the interpretable arm — **"THE REAL RESULT IS THE EEGMMIDB ARM AND IT IS CLEAN"**: incumbent alive (p=0.034), 0 of 32 candidates add. Also caught and voided its own wrong POSITIVE printout (a re-description-of-outcome candidate on a dead-incumbent arm). |
| **E164** | Stieger, consecutive session pairs | Does session-to-session CHANGE in any measure track accuracy change? | n/a (state design) | negative | Yes — **"NONE of 27 feature CHANGES tracks"** the change in accuracy, with the ceiling quoted (0.9478) so it is a real null, not attenuation — but only above a measured floor of rho≈0.4. |
| **E167** | Stieger per-trial | Does pre-cue EEG predict THAT trial's success, within session? | n/a | gate_failed | No — **"NOT INTERPRETABLE at G2"**: trial position leaks into the outcome after adjustment; the repair (block-centring) still leaked (rule 58, one repair spent). |
| **E172** | Stieger per-trial, matched pairs | Same, with position removed BY CONSTRUCTION | n/a | positive | Yes on this cohort — **"PRESENT, and it is Challenge B's first positive under a calibrated instrument"**: `mu_mean` 0.5176 of pairs, p=0.006, clean placebo. |
| **E174** | Stieger, held-out sessions 2–3 | Does E172's effect reproduce on later sessions from the SAME subjects? | E172's own value | negative | Yes — **"E172's effect does not survive to held-out recording days... at greater power, with every gate passing"**; placebo even inverts (lagged signature). |
| **E175** | eegmmidb per-trial | Does the effect exist outside Stieger / outside feedback? | E172's own value | gate_failed | No test run — **"GATE-FAILED AT G1, EXACTLY AS REGISTERED"**: only 8 of 105 subjects reach 20 matched pairs (45 trials total vs Stieger's 450). |
| **E179** | Stieger per-trial, simulated gating | Can E172's effect be USED to raise hits-per-attempt? | Geronimo 2016 (PMID 27199630) negative | positive | Yes at one of six cells — **"USABLE... AGAINST MY REGISTERED PREDICTION"**, `+0.0347 [+0.0048,+0.0645]` at N=20, q=0.67 — but **"THROUGHPUT FALLS AT EVERY CELL."** |
| **E181** | Stieger, discovery/confirmation split | Does pre-cue state predict HOW FAST (graded) rather than WHETHER (binary)? | n/a | positive | Yes, confirmed on a held-out session — **"MORE pre-cue alpha goes with a SLOWER trial"**, opposite valence to E172's binary effect. |
| **E184** | Stieger, gating for speed | Does gating on low alpha improve THROUGHPUT? | Geronimo 2016, in his own unit | negative | Yes, decisively — **"SLOWER at every one of six cells... by roughly a factor of twenty"**; confirms Geronimo's negative a second, harder way. |
| **E188** | Dreyer 2023 | Does E172's pre-cue effect (or E181's graded version) replicate externally, with a real EMG channel available? | E172/E181's own values | absent | Yes — **"ABSENT ABOVE FLOOR in BOTH arms"**; real EMG channel null in both (rule 57's promise delivered: "not by assumption"). |
| **E192** | Forenzo & He, session 1 | Does E181's graded effect replicate on a third, disjoint cohort? | E181's own value | gate_failed | No test run — **"THE BCI IS NOT ALIVE IN SESSION 1"** (aliveness gate correctly refused a non-functioning paradigm session). |
| **E199** | Forenzo & He, final session | Same, cohort changed to most-trained session | E181's own value | gate_failed | No test run — aliveness gate failed again; diagnosed as **the gate's OWN statistic being wrong** (lag-confounded), not the cohort. |
| **E201** | Forenzo & He, chance-referenced gate | Same, aliveness measured against the study's own chance-level runs | E181's own value | negative | Yes, cleanly — **"ABSENT ABOVE FLOOR... on a cohort where the paradigm is demonstrably working"** (26 of 28 subjects beat their own chance run). E181 is now **failed in three independent tests**, one within-deposit and two external. |
| **E204** | HEEDB, GCS-motor cohort | Does spontaneous EEG predict clinician-assessed command-following beyond RASS? | RASS | withdrawn | No — **"WITHDRAWN — ITS FEATURES WERE COMPUTED ON THE WRONG DATA"** (EDF-reader channel-filter and truncation bug found while profiling). Numbers recorded, not usable. |
| **E205** | HEEDB, same cohort | Same, incumbent = sedative-EXPOSURE (drug record) instead of RASS | any_sedative | closed | No — **"CLOSED UNRUN, superseded by E212"**: within-patient exposure turned out identical on 175/181 discordant pairs, so it cannot discriminate at all as a within-patient incumbent. |
| **E212** | HEEDB, discordant pairs | Does EEG predict command-following WITHIN a patient, beyond RASS / exposure? | RASS, any_sedative | gate_failed | No — **"G3 FAILS AGAIN, AND BY RULE 58 THE RUN IS OVER: METHOD FAILS"**: an i.i.d. noise column degrades the ridge-increment estimator as much as every real candidate at this n. |
| **E221** | HEEDB, RASS-EXACT-MATCH subset | Same, RASS held fixed by cohort construction rather than modelled | RASS (held constant by matching) | negative | Yes, cleanly — **"ABSENT... no candidate separates them"**, all p≥0.128, noise control behaving correctly (0.5520, largest deviation, as noise should) — **but on 125 of 540 pairs (23%)**, discarding exactly the pairs where sedation changed. |

---

## 2. Distinct questions answered, and the ones that are not

**Q1 — Does a resting-state EEG measure predict cross-subject ("trait") BCI/motor-imagery aptitude, and do
published predictors transport across cohorts?** **ANSWERED, and answered negatively for transport.** Label
reliability was the real first-order blocker (E38/E63/E68/E97/E101/E114 built and validated the
instrumentation for this). Once resolved: `ge_norm` predicts in Stieger only (E86, internally consistent —
E114 split-half, E97 trait-like) and fails to replicate in eegmmidb (E124) or Dreyer (E125) — **"E86 is
COHORT-SPECIFIC."** Blankertz's SMR/`alpha_prom` replicates in Dreyer (E129) but not Stieger (E131) — **"NO
PREDICTOR WORKS IN BOTH"** cohorts (E131's own words). No resting-EEG BCI-aptitude predictor in this
project's hands has been shown to transport across even two of the three healthy-BCI cohorts tested.

**Q2 — Does within-subject session-to-session CHANGE in a resting measure track change in accuracy?**
**ANSWERED** (E164): no, though only above a measured floor (~0.4).

**Q3 — Does covert motor imagery separate from passive/active movement within subject, on a deposit that
is not a BCI-aptitude proxy?** **ANSWERED AND CLOSED** (E82/E83/E85): ds007554 cannot resolve this; three
instruments failed for a physiological reason (passive movement produces its own ERD, PMID 31425038) rather
than a statistical one, and the file's own stopping rule closed the deposit for this question.

**Q4 — Does pre-cue, trial-level spontaneous EEG predict THAT trial's binary success, within a session?**
**ANSWERED, and the answer is a discovery that failed three replications.** E172 found it in Stieger's
discovery data; E174 (same subjects, later sessions) and E188 (Dreyer, external, with real EMG) both refute
it. **The effect exists in exactly the sample it was discovered in.**

**Q5 — Does pre-cue EEG predict trial EXECUTION QUALITY/SPEED (graded), where it does not predict WHETHER
a command is followed?** **ANSWERED, and closed on external replication.** E181 found it, opposite valence
to E172, confirmed once within Stieger; E192/E199/E201 (independent 28-subject cohort, aliveness gate
eventually fixed and passing) refute it — **"E181... does NOT replicate externally, on a cohort where the
paradigm is demonstrably working."**

**Q6 — Can any of the above be turned into a usable device-control decision rule?** **ANSWERED.** E179
found one cell of six where gating raises hit rate, at the cost of throughput everywhere; E184 tested the
speed-gating alternative directly in Geronimo's own unit and it is **worse by roughly a factor of twenty.**
Nothing here is clinically actionable at the measured effect sizes.

**Q7 — Does spontaneous EEG predict CLINICIAN-ASSESSED command-following in real DoC/ICU patients (HEEDB
GCS-motor), beyond a bedside sedation score?** **PARTIALLY ANSWERED.** The only sub-question that reached
a clean, gated, interpretable verdict is the narrowest one: among discordant pairs where **RASS is
identical on both assessments**, no EEG candidate separates them (E221). The broader discordant cohort
(540 pairs, RASS *varying* between the two assessments) has **never been tested with a working estimator**
— E212's ridge/increment approach failed on machinery (rule 58: the run is over, not the question).

**Q8 — Does a non-EEG covariate/questionnaire predict BCI ability?** **PARTIALLY ANSWERED.** Age/sex
(E54) and mental-rotation score (E132) are both tested and null. **Not tested:** Dreyer's own
manual-activity-habits column, its 8 Index-of-Learning-Style columns, and its 20 16PF5 personality
columns — flagged as untested by `INCUMBENT_REGISTRY.md`'s own priority-1 action item and confirmed
untested by `bsde/docs/PROBE_2026_08_02_CHALLENGE_B_GAPS.md`'s predecessor,
`PROBE_2026_08_02_DREYER_CHALLENGE_B.md` (already on disk this session, §7).

**Q9 — Does spontaneous EEG predict genuinely COVERT command-following in disorders of consciousness —
the flagship construct (a CRS-R-negative, fMRI/EEG-positive patient)?** **NEVER TESTED. Structurally
blocked, not analytically blocked.** No experiment in the 46-row table touches this construct. e20 is the
closest by deposit type (ds004541, "unconscious") and it withdrew for an unrelated reason (channel
identity) before ever reaching a command-following label, which ds004541 does not carry in any case. Every
healthy-BCI substitution (E28 onward) is explicitly logged as an **analogy under test**, never a DoC claim.

---

## 3. Can any deposit CURRENTLY IN THE CACHE address the two open questions (Q7's residual, Q8's untested columns)?

Checked directly against the filesystem, not assumed.

### Q8 — Dreyer questionnaire columns

**YES, and durably.** `bsde/results/dreyer_performance.csv` is tracked in git (`git ls-files` confirms; not
gitignored), 87 subjects, 73 columns, joined 1:1 by `SUJ_ID`/`subject` to `dreyer_graph.s0-5.csv` (174 rows,
2/subject) and `dreyer_smr.s0-5.csv` (87 rows, 1/subject) — all three files verified present with the
row/column counts stated. The outcome (`Perf_RUN_3..6`, OpenViBE online accuracy) is present for 86-87 of
87 subjects. This was already reconnoitred this session in
`bsde/docs/PROBE_2026_08_02_DREYER_CHALLENGE_B.md`, whose Deliverable calls it **"FEASIBLE... this is not a
rerun of anything on the ledger,"** bounded by a measured detection floor of rho_partial ≈0.40 at n=87
(from E134/E163 on the identical cohort).

### Q7 — HEEDB residual (the 415 discordant pairs where RASS *differs*)

**PRESENT RIGHT NOW, BUT NOT DURABLE.** `/tmp/eeg_probe/heedb_cmd_follow.p0-3.csv` and `.w0-5.csv`
(patient- and window-level shards) plus `/tmp/eeg_probe/cmd_sedative_exposure.csv` exist on disk at this
moment (verified by `ls -la`, most recently modified today) and carry the same 8-feature spectral panel
E204/E212/E221 used. **None of this is committed to git and none of it lives under `bsde/results/`** — per
`CLAUDE.md`'s standing operational fact, `/tmp` is rolled back to a snapshot on container restart and this
cache has no guarantee of surviving to the next session. Any design built on it must either (a) run in this
same session, or (b) budget for re-extraction, whose cost is not established here (the extraction script
was not timed in this probe).

### Q9 — flagship DoC command-following

**NO.** No file under `bsde/results/` or `/tmp/eeg_probe/` carries a per-patient command-following label
alongside task-free EEG for a disorders-of-consciousness population. `figshare_features.csv` (99 rows,
verified) is the ingested Figshare DoC deposit and — per `MASTER_PLAN.md` §1 row 2 and confirmed here —
carries no CRS-R/diagnosis column at all, only spectral features. The WBIC request for Chennu 2014
(PMID 25329398, verified via efetch above) sits **drafted 2026-07-30, unsent** (`git log` on
`DATA_REQUEST_WBIC_CHENNU.md` shows no edits since the draft commit). Bath is access-request-only per
`MASTER_PLAN.md` and not pursued in this ledger. The Della Bella/Sitt OSF cohort (its fallback #1) is not
ingested (no matching file on disk) and, even if it were, ships only CRS-R **totals**, not the
command-following subscore. **This question cannot be addressed by anything currently reachable.**

---

## 4. Rule-86 audit — could the incumbent and outcome have been recorded by the same observer, at the same moment, as part of the same procedure?

| candidate design | incumbent | outcome | same observer/moment/procedure? | reasoning |
|---|---|---|---|---|
| Dreyer questionnaire (manual activity / ILS / 16PF5) vs online accuracy | SMR predictor / `alpha_prom` (E129) | `Perf_RUN_3..6`, OpenViBE online classifier accuracy | **No.** | The incumbent is computed from a 2-minute EEG baseline by a fixed signal-processing pipeline; the outcome is the real-time output of an automated classifier during a separate, later block of the session. Neither is a human rating. This is the escape from rule 86 that `PROBE_2026_08_02_DREYER_CHALLENGE_B.md` §2 already names explicitly: **"the incumbent-vs-outcome shared-observer problem does not apply here because the outcome is not a bedside/clinician score at all."** The new candidate (a pre-session self-report questionnaire, administered by an experimenter before any EEG is recorded) is likewise disjoint in time, instrument and observer from the outcome. |
| HEEDB, any design pairing RASS with GCS-motor obeys (extension of E212/E221 to more of the 540 pairs, e.g. by coarser RASS strata) | RASS | GCS-motor best response = 6 (obeys) | **Yes.** | Already established and load-bearing in this exact deposit: E205's own words, **"RASS and GCS-motor are both clinician bedside scores, routinely charted by the same nurse in the same assessment round — two readings of one act, sharing method variance no instrument outside the room can access"** (catalogue rule 86's own origin). Any successor that widens RASS strata rather than holding RASS exactly fixed by matching (E221's solution) reintroduces this problem in proportion to how coarse the stratum is — a wide bin (e.g. "RASS within ±2") lets genuine sedation-driven confounding back in through the same shared-observer channel. |
| HEEDB, EEG vs sedative-EXPOSURE as incumbent (E205's route) | `any_sedative` / drug record | GCS-motor obeys | **No, by construction — but dead for a different reason.** | A drug record and a bedside GCS score are not the same observer or the same moment (E205 was registered precisely to escape rule 86). It is closed unrun because, within the discordant-pair design, exposure status turned out **identical on 175 of 181 (and later 520 of 540) pairs** — it cannot discriminate a within-patient pair at all, which is a *power* failure of a clean design, not a rule-86 failure. |
| Chennu 2014 DoC (if the WBIC request is granted) — EEG vs CRS-R command-following, with CRS-R **total** as a covariate/incumbent | CRS-R total | CRS-R command-following subscore | **Yes, if CRS-R total is used as the incumbent.** | Both are scored in the same bedside CRS-R administration by the same examiner in one sitting — textbook rule 86. If the design instead uses **no clinician incumbent at all** (EEG alone vs the command-following label, as E28's original Challenge-B framing did for the BCI analogy), rule 86 does not obviously apply, but a different problem, already logged in `QUEUE.md` Q3 (Bruno 2011, PMID from that entry), remains: **MCS+ / CRS-R composite categories are not a pure command-following label**, so the outcome definition itself needs care independent of the incumbent question. This is a **cannot-tell** until a specific design is written, because it depends entirely on what, if anything, is chosen as the comparator. |

---

## 5. Rule-70 audit — what is a candidate ALLOWED to be, and does any cached column violate it?

**General statement of the rule, applied to each remaining design:** a candidate must be a measurement of
the subject or the signal, computed **without reference anywhere in its own construction to the outcome,
its timing, trial count, run index, or classifier confidence** (rule 70's own wording, and the specific
failure — `mean_triallength` — it was written to name).

### Dreyer questionnaire design

**Allowed:** any pre-session self-report, demographic, or resting-EEG-derived measure computed from the
120 s `OE`/`CE` baseline files, with no reference to `Perf_RUN_3..6`, trial count, or run index.

- `dreyer_graph.*.csv`'s 10 substantive columns (`ge, cl, deg, ge_norm, cl_norm, smallworld, modularity,
  strength_cv, iaf, alpha_prom` — recounted directly from the file header with `head -1 | tr ',' '\n'`;
  the predecessor probe's document says "12 substantive columns," which does not match either its own list
  or a direct recount, and is corrected here) and `dreyer_smr.*.csv`'s 4 (`smr_C3_db, smr_C4_db,
  smr_predictor_db, smr_peak_hz`, also recounted directly) — **all pass**, verified in
  `PROBE_2026_08_02_DREYER_CHALLENGE_B.md` §5 by tracing each to `graph_features`/`periodic_features_at`
  on the baseline files alone.
- `dreyer_performance.csv`'s **6 `POST_*` columns** (`POST_Mood, POST_Mindfulness, POST_Motivation,
  POST_Cognitive load, POST_Agentivity, POST_Expectations_filled`) — **VIOLATE**, though as a look-ahead
  (rule 10) rather than a re-description (rule 70) specifically: they are measured *after* the four online
  runs the outcome is built from. E132 already demonstrated the failure mode directly on this exact column
  (`POST_Agentivity` scored `+0.2714 [+0.0415,+0.4135]` and was withdrawn as a consequence of the outcome,
  not a predictor of it). Any successor must exclude all six.
- `Interrogation` — **excluded pending clarification**, not because it is shown to violate, but because its
  provenance (item count from the personality/ILS battery, or something else) was never verified against a
  data dictionary.
- Everything else in `dreyer_performance.csv` (demographics, `Level of study`, `Meditation practice`,
  `Laterality answered`, `Manual activity`, the 12 `PRE_*` columns, 8 ILS columns, 20 16PF5 columns) is a
  **pre-session** measurement with no possible reference to the outcome — **all pass rule 70.**

### HEEDB residual design

**Allowed:** an EEG feature computed on the pre-assessment window with no reference to `gcs_motor`,
`obeys`, assessment timing, or RASS itself (RASS is the design's incumbent/matching variable, not a
candidate, and must not be smuggled into a candidate list).

- The 8-feature spectral panel already used across E204/E212/E221 (`exponent_low, exponent_high,
  whole_head_exponent, relative_alpha_power, relative_delta_power, spectral_edge_95, spectral_entropy,
  lempel_ziv`) — **all pass**, computed from the EEG window alone, already gated for artefact contamination
  by E204's own channel-filter correction.
- `n_channels`, `minutes_before`, `rass_minutes` — **metadata, not candidates**, and none is used as one in
  any registered row; flagged here only so a successor does not repeat E149's `mean_triallength` mistake by
  including a timing/administrative column in a candidate sweep.
- No column currently in `/tmp/eeg_probe/heedb_cmd_follow.*.csv` violates rule 70 as a **candidate** — the
  cache has not been extended past the same 8 features any of the three prior HEEDB rows used, so there is
  no new violation risk and also **no new candidate** to test beyond what E212/E221 already tried.

---

## 6. Recommended next experiment

**Recommend ONE experiment: test Dreyer's `Manual activity` column (and, secondarily, the ILS/16PF5 block)
against online BCI accuracy — but not for the reason `INCUMBENT_REGISTRY.md` currently states.**

The registry's Challenge B action item #1 cites Rimbert 2018 (PMID 30728772) as motivation for testing
Dreyer's "personality, mental-rotation, mood and motivation columns." **Reading the actual abstract (fetched
via efetch above, not summarised) shows this is imprecise in a way rule 42 exists to catch**: Rimbert's
own study tested the **Motor Imagery Questionnaire-Revised Second Edition (MIQ-RS)** — a questionnaire
Dreyer's deposit does not carry at all — and found **"no significant correlation between BCI performance
and the MIQ-RS scores."** The positive finding in that paper is narrower and different: **"BCI performance
is correlated to habits and frequency of practicing manual activities."** Dreyer's deposit *does* carry
exactly that column (`Manual activity`, 87/87 non-missing, plus free-text `Manual activity TXT`, 79/87),
confirmed present in `dreyer_performance.csv` and confirmed untested anywhere in the 46-row ledger. **The
literature-licensed, single, pre-registrable hypothesis is therefore "manual activity habits predict online
BCI accuracy, direction positive," not a blanket test of the ILS/16PF5 block**, which Rimbert's paper does
not speak to at all and which the existing probe (§ Deliverable) already warns against running as an
uncorrected 28-column sweep at n=87 (rule 47/rule 34: registering the family before seeing the numbers).

Why this clears the bar the table above sets:
- **Feasible and durable** — `dreyer_performance.csv`, `dreyer_graph.*.csv`, `dreyer_smr.*.csv` are all
  tracked in git (verified), unlike the HEEDB residual cache, which is a `/tmp` artifact of unknown
  persistence.
- **Rule 86 clean** — no clinician incumbent, no shared observer/moment between candidate and outcome
  (§4 above).
- **Rule 70 clean** — a pre-session self-report with no reference to the outcome, distinct from the
  already-flagged `POST_*` look-ahead columns and the unverified `Interrogation` column, both excludable
  in advance (§5 above).
- **Rule 45 satisfiable** — the SMR predictor / `alpha_prom` are already alive on this exact cohort
  (`+0.4440`, `+0.3710`, both from E129) and available as the named incumbent, exactly as E129/E132 used.
- **Power is honestly bounded, not glossed over** — E134/E163 already measured this design's detection
  floor directly on this cohort (≈70% detection at rho_partial 0.40, ≈8% at 0.10 — a large-effect-only
  design), and any registration should state that floor before the run, per the standing `CLAUDE.md`
  discipline this project already follows everywhere else in this table.

**This does not touch Q7 (HEEDB residual) or Q9 (flagship DoC covert command-following), and it should not
be described as though it does.** Q7's honest state is that the residual question beyond exact RASS-match
has never been tested with a working estimator and the data to test it may not persist past this session.
Q9 remains **structurally blocked on data access, not on analysis** — no experiment recommended here
changes that, and the only action that would is sending the drafted WBIC email, which is outside the scope
of "a pre-registered experiment" and is not fabricated as one here.
