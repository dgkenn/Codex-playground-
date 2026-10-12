# Which lines continue, which stop, and what is blocked on the investigator

*2026-08-02. Written under the abstract-first rule: for each live line, the ONE SENTENCE it would license
if it succeeded completely, then a decision. A line whose sentence is already true in the literature, or
too weak to matter, stops.*

---

## ABANDON NOW — the sentence is already true

### Challenge C: the aperiodic exponent tracks sleep depth

> *"The aperiodic (1/f) exponent adds to a spectral-edge incumbent in discriminating sleep depth."*

**This is established.** The aperiodic slope as an arousal/depth marker is a known result, and E240's
replication on ds006695 (+0.1264 [+0.0542, +0.2082], 22.3 % of headroom) confirms rather than discovers.
**Stop treating it as a finding.** It keeps two legitimate uses and neither is a paper on its own:

1. a **positive control** — a measure known to work, against which a new instrument or gate can be checked;
2. the **vehicle** for the transport question, which is where the novelty actually lives.

E240 stays in the ledger as a positive; what changes is that no further experiment should be spent
establishing it.

### Challenge B: covert command-following

> *"Resting EEG predicts command-following capacity beyond an independent incumbent."*

**47 registered experiments; zero touched the flagship construct.** The consolidated record shows why, and
it is structural rather than a design failure: of every incumbent tried, RASS is the only one ever
unambiguously alive, and it is alive *because* it shares a measurement act with the outcome (rule 86).
Every genuinely independent incumbent died — sedative exposure has near-zero within-patient variance;
Rimbert 2018's manual-activity effect does not replicate (E238: −0.0841, |p| = 0.4368 at n = 87, with
better than 95 % power for the published +0.381). That is rule 92.

**Abandon until data access changes.** Not "keep probing" — there is nothing left to probe on cached
deposits, and further designs rearrange the same impasse.

---

## CONTINUE, PENDING A LITERATURE VERDICT ISSUED TODAY

### Challenge A: propofol peak stability

> *"The frontal alpha peak frequency does not change with propofol dose across the clinical range,
> whereas it slows monotonically with sevoflurane dose."*

The sevoflurane half is **already published** (Hayashi 2008, PMID 18431119: 11.0 → 9.8 → 8.7 Hz across
1–3 %). The propofol half is the novel part and it is a NULL, on one deposit, n = 33 matched pairs,
between-patient. A literature check on exactly that half is running; **if it returns ALREADY PUBLISHED,
this line stops** regardless of how the DOSE-I replication comes out.

If it returns UNADDRESSED, the DOSE-I replication (101 recordings, 89–832 windows each) is worth
finishing — a null that holds on two independent deposits with an order of magnitude more windows is a
different object from a null on one.

### Challenge D: threshold transport

> *"EEG measures whose distributions differ substantially between sites nonetheless transport a decision
> THRESHOLD with negligible accuracy loss, so distributional harmonisation is not a prerequisite for
> deploying an index."*

**My own prior is that this is a re-derivation and the line may stop.** The discrimination-transports /
calibration-does-not distinction is standard in clinical prediction modelling, and if our result is that
observation restated on EEG, it is a much smaller contribution than it looks. The literature check was
told to test that possibility first and hardest. The EEG-specific part — that the harmonisation
literature assumes distributional alignment is *needed* — may still be novel even if the statistics are not.

---

## BLOCKED ON THE INVESTIGATOR

These are not analytical problems and no amount of further computation touches them.

1. **The Bath PDoC MI-BCI data request (DOI 10.15125/BATH-01632) appears unsent**, and `MASTER_PLAN.md`
   is internally inconsistent — line 233 lists "file the Bath access request" as an action item while
   lines 162 and 1220 describe it as "request-only and not yet granted", with no corroborating artefact.
   **Bath is the only patient-level command-following dataset found in a full sweep** of OpenNeuro,
   PhysioNet, Zenodo, Dryad, Figshare and OSF. Challenge B is blocked on an email.
2. **The Chennu / WBIC request (`DATA_REQUEST_WBIC_CHENNU.md`) is drafted and unsent.**
3. **NCT02043938** (Groningen/Ghent, Kuizenga/Vereecke/Struys) is the only study with the design Challenge
   A needs — the same volunteers under propofol AND sevoflurane with EEG throughout — and its registry
   entry states `"ipdSharing": "NO"`. An author-mediated request is a long shot and is the only route to a
   within-patient test of the asymmetry.
4. **Credential rotation.** Credentials were pasted into chat earlier in this programme. They were written
   only to `~/.netrc` mode 600 outside the repo and never committed, but rotation has been advised
   repeatedly and not confirmed.

---

## VERDICT IN, 2026-08-02: Challenge D stops as a standalone line

The literature check returned **PARTIALLY PUBLISHED**, and the part that is published is the part the
claim rested on. Verified directly against MEDLINE rather than taken on report:

* **Van Calster et al. 2016, PMID 26772608** — *"we prove that moderate calibration guarantees
  nonharmful decision making."* Moderate calibration is a far weaker condition than two sites'
  distributions matching. That is a formal proof of the mechanism our result instantiates.
* **Justice, Covinsky & Berlin 1999, PMID 10075620** originated the calibration/discrimination and
  reproducibility/transportability distinctions.
* **Debray et al. 2015, PMID 25179855** frames external validation around case-mix differences and
  reports a model needing no extensive updating across sites of differing case-mix.

**So the statistical contribution is nil.** "A threshold transports when both sites' class distributions
straddle a common value, regardless of their means" is textbook clinical prediction modelling, proved
seven years before this project started. E243 and E244 re-derived it on EEG without knowing it existed —
which is precisely the failure the pre-third-experiment literature rule was added to prevent, arriving
one experiment too late again.

**What survives is narrow and real.** No EEG paper states or tests it: the harmonisation literature
(ComBat, neuroCombat, neuroHarmonize) uniformly harmonises *then* classifies, and none asks whether
harmonisation was necessary. So "the EEG harmonisation literature assumes an alignment step that a
decision threshold does not require" is an unmade point — but it is a **paragraph in a methods paper,
not a paper**, and it should be written as such.

**Decision: stop Challenge D as a standalone line.** E245 finishes because it is already running and its
numbers are the evidence for even the narrow version; nothing further is registered after it. Any
write-up must cite Van Calster 2016 as the mechanism and claim only the EEG instantiation — presenting
this as a new insight about transportability would be wrong on the record.

---

## VERDICT IN, 2026-08-02: Challenge A stops too — the published evidence points the wrong way

The propofol check returned **PARTIALLY PUBLISHED, with the published half cutting AGAINST the
hypothesis.** Two things I verified myself against the MEDLINE record, and one I could not:

**Verified.** Hight et al. 2017 (PMID 28611600, *Front Syst Neurosci*) is a **305-patient** volatile
series that "fitted linear concentration-response curves to assess the sensitivity of alpha power and
**frequency** measures to changing levels of anesthesia", and that explicitly asks "what effect
increased age has on alpha frequency". So the sevoflurane half of our sentence is published twice over —
Hayashi 2008 and now a 305-patient concentration-response study — and **age is a documented confound on
the exact measure we used**, in a comparison that is between-patient by construction.

**NOT verified, and I am flagging it rather than passing it on.** The agent's key quote — that with
propofol "the spectral median, a close approximation to peak frequency, reaches a lower frequency limit
during deeper stages of anesthesia" — is **not in the Hight abstract**. It is reported from full text and
I could not confirm it from the record. If true it contradicts our null directly, describing propofol as
slowing then plateauing rather than not moving. A modelling paper (Noroozbabaee 2021, PMID 33316393) is
reported to predict the same direction.

**Decision: stop Challenge A as framed.** Three reasons, any one sufficient:

1. The sentence's novel half is **contradicted, or at best pre-empted**, by evidence pointing to
   slow-then-floor rather than invariance.
2. Age is a **documented, sizable confound** (0.5 Hz young-versus-elderly, and it flattens the
   dose-response slope itself) on a between-patient design that E228-E231 already established cannot be
   made within-patient on any public deposit.
3. What would survive — "propofol's peak floors while sevoflurane's keeps slowing" — **is someone
   else's finding**, not ours.

**The DOSE-I extraction is allowed to finish** (it is at 80 of 101 recordings and costs nothing further)
and the table is kept, but **no experiment is registered on it**. A replication of a claim we are
withdrawing is not worth running, and running it anyway would be the sunk-cost move the abstract-first
rule exists to prevent.

---

## Where that leaves the programme

All three challenges are now closed or downgraded, and that is the honest state rather than a failure of
effort:

| challenge | state |
|---|---|
| **A** — anaesthetic-invariant depth | **stopped**: novel half contradicted, confound unremovable on public data |
| **B** — covert command-following | **blocked on data**, 47 experiments, zero touching the construct |
| **C** — earlier transition detection | **confirmatory only**: the aperiodic exponent result is established prior art |
| **D** — transport / calibration | **stopped**: mechanism is a published proof (Van Calster 2016) |

**What is left that is genuinely ours** is the methodological record: 220 registrations, and an error
catalogue of 94 rules each paid for with a wrong result — the peak estimator firing on 91.5 % of
signal-free noise, band placement manufacturing a drug reversal that survived four confound experiments,
leave-one-out concealing a zero-versus-nonzero split, a placebo unable to fire at a ceiling. That is a
real contribution and it is the one to write up.

---

## STANDING CONSTRAINT, set by the investigator 2026-08-02: formal access routes only

**The investigator will pursue datasets through formal access routes but will NOT cold-email authors.**
This is a permanent constraint on data strategy, not a one-off preference, and it changes what counts as
a live option.

**IN SCOPE** — repository credentialing (PhysioNet DUA and credentialed tiers), institutional
data-access portals with an application form, managed-access archives with a published procedure,
registered-access schemes, and a data office or data-protection-officer inbox where that inbox is the
record's OWN published access route.

**OUT OF SCOPE** — "available from the corresponding author on reasonable request", author-mediated
sharing, personal emails to research groups. However scientifically attractive, these are not to be
proposed again.

### What this closes, permanently

* **NCT02043938** (Kuizenga / Vereecke / Struys, Groningen–Ghent) — the only study anywhere with the
  design Challenge A needed: the same volunteers under propofol AND sevoflurane with EEG throughout. Its
  registry states `"ipdSharing": "NO"`, so the only route was ever an author request. **Closed.** This
  is now moot in any case, since Challenge A stopped on scientific grounds above, but it should not be
  revisited if that line is ever reopened.
* **Any deposit whose data-availability statement is "on reasonable request".** Several near-misses in
  `DATA_SEARCH_2026_08_02_CROSSOVER.md` and the Challenge B probes fall here — Della Bella / Sitt's
  237-patient DoC cohort among them. They stop being near-misses and become unavailable.

### What remains open

* **Bath PDoC (DOI 10.15125/BATH-01632) — request SENT 2026-08-02.** A managed-access institutional
  repository with a published request procedure, so squarely in scope. This is now the only route to a
  live scientific question in the programme.
* **Chennu / WBIC** — the drafted request is addressed to `enquiries@wbic.cam.ac.uk`, which is the access
  route quoted in the paper's own data-availability statement (PMID 25329398), i.e. an institutional data
  office rather than an author. **In scope as drafted**, but note the draft as written also copies the
  study authors and offers to be redirected to them; those elements should be removed before sending if
  the constraint is to be honoured strictly.
* **PhysioNet restricted tiers** — `eeg-power-anesthesia` (DOI 10.13026/m792-h077) needs only a signed
  DUA with no committee review, and is in scope. Its limitation is scientific rather than procedural: it
  ships derived multitaper spectra rather than raw EEG, so only band-power-type candidates are computable.

**Consequence for planning.** Challenge B is now single-sourced on Bath. A search for additional
formal-access cohorts is running so that it is not, because a challenge resting on one pending request is
one refusal away from closed.

---

## CONSTRAINT REVISED AGAIN, 2026-08-02: fully public data only

The investigator now wants **publicly available data instead** of access requests. IN SCOPE: a URL that
returns data today, with no application, committee, custodian, DUA, credentialed tier or email to anyone.
This is stricter than the formal-access constraint recorded above and supersedes it for planning.

**What it retires.** Bath (sent) and Chennu/WBIC (drafted) may still land, but **nothing is planned around
them**. PhysioNet credentialed and restricted tiers go out of scope too, which removes
`eeg-power-anesthesia` from consideration.

### The important consequence: access was never Challenge A's or C's problem

Re-reading the blockers under this constraint changes the picture for two of the three challenges, and the
change is in our favour:

* **Challenge C** needs transitions with a conventional monitor recorded alongside. **VitalDB is fully
  public and already held**, and it records BIS. Today's feasibility probe showed the obstacle is that
  `vitaldb_grid` samples the maintenance phase at 300 s spacing with a median of ZERO windows within
  ±10 min of anaesthesia start. That is an **extraction-design problem, not an access problem**, and it is
  fixed by one S3 pass at ~10 s spacing across both transitions.
* **Challenge A** needs loss and recovery under at least two agents. VitalDB (public) has both propofol
  and volatile arms; OpenNeuro ds004541 and ds005620 (public) have anaesthesia transitions. The obstacle
  there was never access either — it was that no candidate has been scored on the actual acceptance
  condition, and that the comparison is between-patient.

**So under this constraint, A and C become the live challenges and B becomes the blocked one** — the
reverse of the position an hour ago, when B had two pending requests and A and C were closed.

* **Challenge B is the one with a genuine public-data gap.** Every survey so far has failed to find a
  public deposit pairing task-free EEG with an independently-scored command-following outcome in
  brain-injured patients. One lead has NOT yet been checked and is being checked now: **BCI datasets in
  locked-in / ALS / severely paralysed patients**, several of which are openly downloadable through the
  BNCI Horizon 2020 catalogue and MOABB's registry. Locked-in syndrome is command-following with MACHINE
  scoring, which is precisely the rule-86 escape the challenge needs. If that returns nothing, Challenge B
  has no public route and should be stated as blocked rather than repeatedly re-searched.

---

## ABSTRACTS AS REVISED BY THE LITERATURE CHECKS, 2026-08-02

Both remaining challenges came back PARTIALLY. The checks did not kill either line, but they moved where
the novelty sits, so the licensed sentence is rewritten here — sharpened to what is actually unclaimed.

### Challenge C — the sentence is now about the ABLATION, not the lead

> *"A raw-EEG measure detects anaesthetic state transitions earlier than BIS, and the lead SURVIVES
> matching the measure's smoothing window to BIS's — establishing it as neurophysiological rather than
> an artefact of less smoothing."*

**Prior art that constrains it.** BIS's lag is measured, not assumed: **20–160 s, asymmetric by
direction**, from a four-paper series that replayed known transitions into the monitors (PMIDs 16508396,
19648154, 22584557, 32040794). A thin precedent for the lead itself exists — Ra, Li & Li 2021
(PMID 33978842) report a spectral-entropy index reacting **158 s earlier** than BIS (range 6–331, n = 14),
single-centre and one direction only. And the framing is live on this very dataset: Kavuncu et al. 2026
(PMID 42351597) used **5,471 VitalDB cases** to predict BIS-threshold crossings 3/5/10 min ahead.

**What is unclaimed.** No smoothing-window-matched ablation exists anywhere in that literature. Without
it, a lead is engineering — a shorter window reacting faster — and not a discovery. That ablation IS the
contribution; the lead on its own is not. **The clause after the dash is the paper.**

### Challenge A — the sentence is about MINIMISATION, and it has a number

> *"A representation retains loss-and-recovery tracking across anaesthetic agents while reducing
> agent-identifiability from 91.43 % toward chance."*

**What is unclaimed.** The failure half is extensive prior art (BIS unreliable for ketamine,
dexmedetomidine, N₂O, xenon, opioids — PMID 16634416). But nobody states agent-identifiability as a
quantity to ACTIVELY MINIMISE. PSI's validation (PMID 14742326) targeted "consistency across anaesthetic
agents" and tested it as pooled/per-agent regression agreement — the same post-hoc logic a prior session
mistakenly used. The 91.43 % baseline comes from PMID 42131603 and is **recorded as not independently
verified**: the paper and title are confirmed, the number is from full text.

**The blocker is in this project's own brief.** `BRIEF_02_DATASET_STRATEGY.md` states VitalDB lacks
precise behavioural consciousness labels, so a VitalDB design would test whether a candidate reproduces
BIS's agent-dependent quirks rather than tracking consciousness. A probe is running to find whether ANY
fully public deposit has two agents, both transitions, and a non-monitor state label. **If it returns
none, Challenge A is blocked on public data and stops** — the minimisation framing being novel does not
rescue a design with no valid state label.

---

# RESOLVED LATER THE SAME DAY — two stops fire, one line survives

*Both stops below were pre-committed above, conditional on a probe. Both probes have now returned and been
verified by Opus against the raw source rather than accepted from a subagent.*

## Challenge A — STOPPED on fully public data

The condition was: *"A probe is running to find whether ANY fully public deposit has two agents, both
transitions, and a non-monitor state label. If it returns none, Challenge A is blocked on public data and
stops."*

**It returned none.** The one cell I had personally disputed — Krause, criterion (b), loss AND recovery —
is resolved against continuing: **1 of 29 drug patients** (19 propofol, 10 dexmedetomidine, no overlap)
shows any block transition leaving unresponsiveness, and that one is separated from its loss event by the
largest gap in the cohort. Re-derived independently; see the verification section of
`PROBE_2026_08_02_CHALLENGE_A_STATE_LABELS.md`, which also withdraws one of the subagent's ratios and
corrects my own "13 of 34" spot-check to 1 of 34.

n = 1 recoverer cannot support a design whose acceptance has loss-and-recovery **across agents** in it.

**What is NOT being abandoned:** the framing. The minimisation sentence — *"a representation retains
loss-and-recovery tracking across anaesthetic agents while reducing agent-identifiability from 91.43 %
toward chance"* — survives the literature check as unclaimed, and it is the strongest unclaimed sentence
this project holds. What is missing is a deposit, not an idea.

**BLOCKED ON THE INVESTIGATOR.** This line restarts the moment any one of these exists:
1. **A credentialed or on-request deposit with two agents and a behavioural state label.** The Bath
   request (`DATA_REQUEST_BATH_01632.md`) is the wrong dataset for this — it is Challenge B's. What
   Challenge A needs is an anaesthesia deposit with per-epoch OAA/S or equivalent under >= 2 agents.
2. **Confirmation that the 91.43 % figure is real.** It is from PMID 42131603's full text and is recorded
   as NOT independently verified. The whole minimisation framing quotes it as its baseline. One PDF
   settles it.
3. A decision to accept a BIS-derived state label, which `BRIEF_02` currently forbids and which would
   change what the result means (it would test reproduction of BIS's agent-dependence, not consciousness).

## Challenge B — STOPPED, and the reason is now stronger than "no incumbent"

Abandoned above on rule 92 (the only live incumbent shares a measurement act with the outcome). The
public-only search returned exactly one new candidate deposit — a Zenodo CLIS set — and it does not
rescue the line for two independent reasons, either sufficient:

1. **n = 4 patients.** No incumbent comparison, no cluster-level null, no gate in this project's
   repertoire is estimable at that size (rule 69: the effective n is the number of clusters).
2. **It is already analysed.** PMID **41017975** (*Assessing consciousness in patients with locked-in
   syndrome using their EEG*, Frontiers in Neuroscience 2025, verified via E-utilities) analyses "EEG data
   from four LIS patients ... extracting different features based on frequency, complexity, and
   connectivity measures", and states the work is done "given the inexistence of ground truth". That is
   this project's candidate panel, on these patients, with the same missing outcome.

A caveat carried for the record and not load-bearing: PMID 31841514, in the same literature, is a
**Retraction Notice** (verified: pubtype `['Journal Article', 'Retraction Notice']`) for the CLIS
BCI-communication result. PMID 33743301 is a separate, non-retracted data descriptor.

**BLOCKED ON THE INVESTIGATOR.** Challenge B restarts only on data access, and the specific object is
named: a patient cohort where command-following is scored by a procedure **independent of the bedside
rater** (rule 86). `DATA_REQUEST_BATH_01632.md` is exactly that request and is drafted with the
investigator's fields still blank.

## Challenge C — CONTINUES, and is now the only live front

It is the only one of the three whose blocker was compute rather than access. The unclaimed sentence is
the smoothing-window-matched ablation, and the data for it is being extracted now.

---

# Challenge C, re-scoped the same day — the design was wrong, the challenge is not

E246 ran and returned **ABSENT** as registered, and the ABSENT carries no information. The incumbent's
aliveness gate failed at **0.343** and the reason is structural: over 134 usable cases, the number
carrying any valid BIS in 200 s bins from `aneend` runs **130 / 120 / 73 / 33 / 14 / 5**, while the same
bins for the EEG measure run **134 / 134 / 134 / 134 / 121 / 71**. **The monitor declares its own index
unusable while the sensor stays attached and keeps delivering EEG** — corrected the same day; see the
correction block in `bsde/results/e246_first_pass_note.md`, which separates *device emitting* from
*device emitting a valid reading* over all 245 cases and finds the emitting count identical to the EEG
count in every bin. Full account in `bsde/results/e246_first_pass_note.md`; catalogue rule 96 records
that the deposit adapter's own docstring said this before the design was written.

**This does NOT stop Challenge C, and it specifically does not stop it for lack of data.** What it stops
is the design: a lead over BIS cannot be measured on a landmark BIS never reacts to. Three changes
follow, and each is an instrument change rather than a moved threshold.

1. **The landmark stops being `aneend`.** Rule 86 prefers an exposure over an observation, and VitalDB
   carries one continuously — the anaesthetic drug record. "The agent was switched off" is precisely
   timed, recorded for the whole case, and independent of both instruments.
2. **The cohort restricts to cases where the monitor is present THROUGH the transition**, with the
   exclusion reported and tested for outcome-relatedness (rule 14), because it obviously is one.
3. **Matched false-alarm rate is calibrated per detector, not by a common z.** G2 measured BIS's
   held-out baseline false-alarm rate at **0.000** against the candidate's **0.0448** at the identical
   threshold: BIS in deep anaesthesia is far more stable than any EEG summary of the same signal, so a
   shared z is not a shared operating point. Found by building the gate.

**Two feasibility steps are running now, in the order rule 41 requires — probe first, register second.**

* A v2 sampling plan over the full public deposit: **5,870 eligible cases, 822,166 windows** (against
  v1's 250 and 34,866). Verified independently against the API: `/cases` 6,388 rows x 74 columns,
  `/trks` 486,449 rows, `BIS/EEG1_WAV` on **5,871** cases, of which **5,870** carry a sane `aneend`
  (case 4476 stores -3.69e9 and is correctly dropped).
* A **monitor-availability probe** over all 5,866 cases carrying BIS, SQI and EEG, fetching only the
  two 1 Hz numeric tracks and no waveform. It measures, per case, how long a valid (SQI > 0) BIS
  reading survives relative to `aneend`. This is 20-50x cheaper than finding out by extraction — one
  EEG track is ~9.4 MB, so a blind 5,870-case waveform pull is ~55 GB against a fixed disk allowance,
  most of it spent on cases the successor will exclude. **The probe decides which cases are worth the
  waveform fetch**, and its own output is the population-scale version of the availability curve above.

**NOT BLOCKED ON THE INVESTIGATOR.** Challenge C is the one front that needs no access decision: VitalDB
is fully public, the probe and the plan are running, and the successor design is determined by what the
probe returns.

---

## Challenge A's stop, confirmed a second time by an independent search

An independent public-only sweep of PhysioNet (712 published projects, full local grep of the REST
listing), OpenNeuro (447 EEG datasets enumerated via GraphQL, per-dataset `channels.tsv` pulled from S3),
Zenodo, OSF, Dryad and Figshare returned **DOSE-I** (Zenodo 10.5281/zenodo.18483292, 171 recordings,
procedural sedation for endoscopy, MOAA/S behavioural scores, 1,129 annotated consciousness transitions)
as the best public candidate for a deposit with a behavioural state label spanning loss and recovery.

**This project already has DOSE-I extracted** (`bsde/results/dosei_*.csv`) and already assessed it against
Challenge A's three criteria: `PROBE_2026_08_02_CHALLENGE_A_STATE_LABELS.md` line 260 records
**(a) two agents — NO, propofol bolus only**, with (b) and (c) both satisfied. So the strongest candidate
a fresh six-archive search can find fails the *same* criterion, for the same reason, as everything else.

Two things follow. **Challenge A's stop is confirmed** and is not an artefact of one probe's search terms.
And this is catalogue rule 50's corollary earning its place again: the internal record answered the
question before the external search did, and grepping it first would have saved the sweep.

The sweep's other useful output is a NEGATIVE with a shape: across all six archives, the criterion that
always fails for a *monitor-comparison* design is the **monitor channel**. Fully public deposits with raw
EEG through a transition carry no commercial index (DOSE-I's `pEEG` panel is author-computed SEF95/entropy,
not a device output); the deposits that plausibly carry one are gated. Rejected solely for being gated,
and therefore possibly unlockable by the investigator: Zenodo **1168447** (Oxford, ultra-slow induction to
and emergence from propofol, `access_right: restricted`), PhysioNet **eeg-gaba-anesthesia** (Contributor
Review), PhysioNet **eeg-power-anesthesia** (Restricted, and derived spectra only).

---

## Challenge A: the three unlockable deposits were triaged, and NONE of them unblocks it

Access-triage of the three gated candidates, from landing-page metadata and the Zenodo REST API parsed
directly. Both publication records verified by Opus against retrieved esummary output.

| deposit | access route, as stated on the record | fails |
|---|---|---|
| PhysioNet `eeg-gaba-anesthesia` | **Contributor Review** — credentialed user + CITI training + **per-study approval by the authors** + DUA | **(c)**, and (a) only nominally: 4 subjects, of which **one** sevoflurane; the only per-subject signals are drug concentration and infusion rate, i.e. the drug record that criterion (c) excludes |
| PhysioNet `eeg-power-anesthesia` | Restricted — register and sign the DUA | **(a)+(b)+(c) jointly** — see below |
| Zenodo `1168447` | "Data available on request" | **(a)** — bench/volunteer **propofol only**; has genuine bidirectional behavioural labelling, which is the harder half, but for one agent |

Publications, verified: PMID **37467269** (Adam et al., *Proc Natl Acad Sci U S A* 2023, "Modulatory
dynamics mark the transition between anesthetic states of unconsciousness") and PMID **33956800** (Abel
et al., *PLoS One* 2021, "Machine learning of EEG spectra classifies unconsciousness during GABAergic
anesthesia").

**And `eeg-power-anesthesia` is not a request at all — this project already has it.** It appears in
**13 rows** of `REGISTRATION_LEDGER.jsonl` and its extractions are on disk
(`deposit_eeg_power_anesthesia.json`, `e154_lambda_mgh_or.json`). The triage recommended it as "cheapest
to request"; there is nothing to request. What matters is *why* it does not solve the problem, and the
answer is a split the deposit's own structure makes unavoidable:

* the **volunteer arm** carries a real per-epoch behavioural responsiveness label — response probability
  to click and verbal cues crossing 5 %, in both directions — and is **propofol only**;
* the **operating-room arm** is genuinely multi-agent (propofol / sevoflurane / mixed, pre-split by a
  shipped `rx_sorted_case_ids.yml`) and has **no behavioural test and no recovery at all** — its "LOC" is
  the time surgery began, and recording stops at the end of surgery because, in the contributors' own
  words, it is unclear retrospectively when a patient returns to consciousness.

**So the cell Challenge A needs is empty in the deposit that comes closest to filling it, and empty for a
reason that is about how the data was collected rather than about what was shared.** That is the same
shape as rule 92's finding for Challenge B: the criteria "multi-agent" and "behaviourally labelled in both
directions" keep landing in different cohorts, and no amount of further searching among existing public or
requestable deposits looks likely to put them in the same one.

### The honest statement of the blocker, for the investigator

**Challenge A is blocked on data that may not exist in any accessible deposit.** Four independent
searches — the original probe, a six-archive public sweep, the Krause re-check, and this access triage —
have each returned deposits satisfying two of the three criteria and never all three. Further searching
is now low-yield and I am not recommending more of it.

**Three things could change that, and all three are yours rather than mine:**
1. **A collaborator with unpublished perioperative EEG that carries per-epoch OAA/S or equivalent under
   two or more agents, in both directions.** This is a collection problem, not a search problem.
2. **Confirmation of the 91.43 % agent-identifiability figure** (PMID 42131603, full text). It is the
   baseline the whole minimisation framing quotes and it is recorded as NOT independently verified. One
   PDF settles it, and if the number is wrong the framing needs rewriting regardless of data access.
3. **A decision to relax criterion (c)** and accept a drug-record or monitor-derived state label. That is
   yours to make, not mine, and it changes what the result means: it would test whether a candidate
   reproduces the monitor's or the pharmacology's behaviour, not whether it tracks consciousness. I would
   report it as such.

---

# CHALLENGE A REOPENED — the investigator relaxed criterion (c), and it is runnable

*Logged as a CHANGE OF ACCEPTABLE EVIDENCE, made by the investigator, before any result was seen. It is
recorded here rather than absorbed silently because a criterion that moves after a line has failed looks
identical, in a git history, to a goalpost being moved — and the only thing that distinguishes them is
whether the change was written down at the time and what it was known to cost.*

**What changed.** Challenge A's criterion (c) previously required a state label that is neither a
depth-of-anaesthesia monitor nor the drug record. The investigator has relaxed it. Criteria (a) two
agents and (b) loss AND recovery are unchanged.

**What that costs, stated before the design rather than after the result.** Relaxing (c) admits two
obvious labels and each is circular for *this particular* challenge:

* **the drug record** (MAC, propofol effect-site concentration) makes "tracks state" and "follows the
  drug" the same quantity — and Challenge A's entire statistic is the separation between them;
* **BIS** is computed from the same EEG a candidate is computed from, so the label and the candidate
  share the measurement act (rules 28 and 86).

So the relaxation is used for a **third** label that the old criterion had also excluded but that is
neither of those, and is better than both here.

## The label: ventilation state, from the airway record

Under controlled ventilation the measured respiratory rate (`Primus/RR_CO2`) equals the ventilator's set
rate (`Primus/SET_RR_IPPV`) **exactly**; when the patient breathes for themselves the two diverge. That
makes controlled-versus-spontaneous a clean, continuously recorded binary that is independent of the
agent's identity and independent of the cortical EEG.

**Measured on a balanced 30-case sample across the three single-agent arms, before any design:**

| quantity | result |
|---|---|
| both tracks finite | 0.93–0.99 of the record |
| median \|RR − set RR\| in deep maintenance (−3600 to −1800 s) | **0.0 in every case** |
| separated in [0, +900] s about `aneend` | **1.00 in 26 of 30**; 2 cases never (stayed ventilated) |
| separated in the same window about a mid-case **placebo** landmark | **0.000–0.089**, median 0.0 |
| **early separation (loss direction), cases with early coverage** | **19 of 19**, median fraction 0.238 |
| time of first agreement (spontaneous → controlled) | median ≈ 500 s into the record |
| last agreement relative to `aneend` (controlled → spontaneous) | mostly **−130 to −1000 s** |

Two things follow and both matter. **The loss direction is captured** — recordings begin while the patient
is still breathing spontaneously and converge to controlled ventilation a few minutes in, so both
transitions sit inside a single case. And the ventilation landmark is **better timed than `aneend`**,
which it precedes by 2–17 minutes; `aneend` is the charted administrative time that E246 already
established lags the physiological event.

## Cohort — this is the part that was missing

`BIS/EEG1_WAV` + `Primus/MAC` + `Primus/RR_CO2` + `Primus/SET_RR_IPPV`: **5,566 cases**, of which
**sevoflurane 1,474, desflurane 460, propofol TCI 996** carry exactly one agent track, plus 2,613 mixed.

Set that against **E154's own projection**, which is the reason this matters rather than a nice-to-have.
E154 measured the cluster-level drug-legibility null at a 95th percentile of **0.1904 with 39 clusters**,
against **0.2791 at Krause's 15**, a ratio of 0.68 against the 0.62 that pure sample size predicts — so
the floor scales as √n and E154 concluded that resolving leakage at 0.10 needs **roughly 140 clusters**,
adding: *"no public deposit this project has found comes close."*

VitalDB has 460–1,474 patients per single-agent arm. At √n scaling the floor lands near **0.03**. The
minimisation half of Challenge A — **which a later check the same day found is NO LONGER SAFE TO CALL
UNCLAIMED; see "E248's framing is CORRECTED" below before relying on this sentence** — becomes
measurable for the first time in this project.

## What must be carried into the design, not discovered later

1. **E154's confound will still be here and will be worse with more power.** Recording duration
   identified the agent at **0.3771**, above every feature; sevoflurane cases are systematically longer.
   The successor must summarise over **fixed-length windows at fixed offsets from the ventilation
   transition**, identical for every case, so recording length cannot enter, and must run duration
   through the identical path as a placebo and require candidates to beat it.
2. **The state label is a BEHAVIOURAL OUTPUT, at the brainstem, and it is not consciousness.** Brief 01
   exists to separate arousal, cognitive processing, command-following and behavioural output; this
   measures the last of them. Any result says "tracks loss and recovery of a behavioural output across
   agents", which is weaker than the briefed construct. **That weakening is what relaxing (c) bought and
   it belongs in the abstract, not in a limitations paragraph.**
3. **Exclusions are outcome-related** (rule 14): the ~7 % of cases that never resume spontaneous
   ventilation in the window are ones that stayed ventilated, and they are not a random sample.

## Challenge B is NOT reopened by this

Relaxing (c) is a Challenge A criterion about state labels. Challenge B's outcome is **command-following**,
which is a behavioural assessment by definition — there is no monitor-derived or drug-derived proxy for
"the patient followed an instruction", and rule 92's finding stands: the only reliably live incumbent is
one that shares a measurement act with the outcome. **Challenge B remains stopped and remains blocked on
the Bath request.**

## E248, written abstract-first before the design is registered

**The one sentence the line would license if it succeeded completely:**

> *A single EEG representation tracks loss and recovery of spontaneous ventilation equally well under
> sevoflurane, desflurane and propofol while carrying less information about which agent was used than
> any measure currently in clinical use — and the reduction is verified against a patient-level
> permutation null on a cohort large enough to resolve it.*

**Draft abstract.** *Background.* Processed EEG depth-of-anaesthesia indices are known to behave
differently under different anaesthetic agents, and that failure is well documented. What has not been
attempted is the converse: treating agent-identifiability as a quantity to be actively minimised while
state-tracking is preserved. **[WITHDRAWN the same day — PMID 41385421 applies domain-adversarial
training with cross-anaesthetic evaluation and the abstract does not say whether the adversarial domain
was drug or subject. See "E248's framing is CORRECTED" below. The draft abstract in this section is
superseded by the revised sentence there and is kept only so the correction is auditable.]** Attempts to measure it have been limited by cohort size — the patient-level
permutation null for a leakage statistic scales as √n, and in the largest cohort previously available to
us (39 patients) the null's own 95th percentile sat at 0.19, above every candidate's observed value.
*Methods.* In N public intraoperative cases (VitalDB) with exactly one anaesthetic agent recorded
(sevoflurane, desflurane, propofol), we labelled brain state from the airway record — measured
respiratory rate against the ventilator's set rate, which separates controlled from spontaneous
ventilation and moves in both directions within a single case — and computed a panel of EEG measures over
fixed-length windows at fixed offsets from each ventilation transition, identical for every case so that
recording length cannot enter the summary. State legibility and agent legibility were each scored against
patient-level permutation nulls, with recording duration carried through the identical path as a placebo.
*Results.* [N] *Conclusions.* [N]

**What is deliberately NOT claimed, written before the numbers exist.** The label is ventilation state:
a **behavioural output, at the brainstem**. It is not consciousness, not command-following, and not
cognitive processing — the three things Brief 01 exists to separate from behavioural output. Any result
is a statement about tracking a brainstem behavioural transition, and the abstract above says so in its
first result clause or it is misleading.

**The honest ceiling.** If the minimisation half works, this is a genuinely new framing with a number
behind it and a cohort large enough to support it — a strong methods-and-measurement paper, and the basis
for a claim the project has been trying to earn since Brief 01. If only the state-tracking half works, it
is a re-demonstration of something already known and is not worth writing up on its own.

**Pre-committed stops.**
1. If the literature check now running finds agent-invariance already used as a construction objective in
   EEG anaesthesia, the minimisation framing is claimed and **the line stops** — the state-tracking half
   alone does not justify it.
2. If recording duration's agent legibility is not brought below the candidates' by the fixed-window
   design, E154's confound has survived and **the verdict is VOID, not negative** (rule 31).
3. If the patient-level permutation null's 95th percentile does not fall materially below 0.19 at this
   cohort size, the measurement is no better resolved than before and the line stops for the same reason
   E154 gave.

---

## E248's framing is CORRECTED before it is registered — half of it is published, and the stop partly fires

*The literature check I pre-committed to has returned. Both decisive records were pulled and read by Opus
from efetch output, not taken from the subagent. The abstract written above is wrong in its first half
and has to be replaced rather than defended.*

### HALF 1 — "tracks loss and recovery across anaesthetics" — is PUBLISHED, with a better label than ours

**PMID 31326088** — Ramaswamy et al., *British Journal of Anaesthesia* 2019, "Novel **drug-independent**
sedation level estimation based on machine learning of quantitative frontal electroencephalogram features
in healthy volunteers." Verified verbatim from the abstract: **102 healthy volunteers across three agents**
(propofol 36, sevoflurane 36, dexmedetomidine 30), state labelled by **MOAA/S** — the behavioural scale
that criterion (c) originally demanded and that we have just relaxed away — 44 QEEG features, elastic-net.
Per-drug AUC **0.97 / 0.74 / 0.77**; the **drug-independent** system **0.83**. The paper's own conclusion
is that "the sedation-level estimator maintained a high performance for predicting MOAA/S independent of
the drug used."

That is Challenge A's first half, done, in a specialty journal, six years ago, on a **stronger** label than
the ventilation state we were about to substitute for it. **Our version of that half would be a weaker
replication and it must be presented as one, or not at all.**

### HALF 2 — the minimisation framing — is NO LONGER SAFE TO CALL UNCLAIMED

**PMID 41385421** — Jeong et al., *IEEE J Biomed Health Inform* 2025, "EEG-based **Cross-subject**
Prediction for Consciousness State Transitions under Sedation using a Deep Learning Framework." Verified
from the abstract: the framework incorporates "**domain-adversarial training** for robust classification",
is evaluated on propofol and midazolam, "demonstrated strong cross anesthetic generalizability... when
evaluated across propofol and midazolam in external validation", and claims to identify "robust and
**drug-independent** EEG signatures".

**The decisive detail is not in the record.** The title says *cross-subject*, and the abstract describes
cross-anaesthetic performance as **evaluated in external validation** rather than as an adversarial
objective — which reads as an adversarial term on SUBJECT identity with agent transfer measured
afterwards. If that reading is right, the minimisation framing survives. If the adversarial domain label
was the DRUG, the framing is claimed and this line's novelty goes with it. The paper is IEEE, has no PMC
record, and the abstract cannot settle it.

**So my pre-committed stop fires in the form it was written for, but on a fact I cannot verify.** I am
not going to lawyer it into a pass, and I am also not going to fire a stop on an unverified reading —
that is the same error, in the other direction, that I correctly refused to make on the Krause cell
earlier today. **What changes now, unconditionally, is the claim: the minimisation framing is no longer
described as unclaimed anywhere in this project's documents.**

### What is left, and it is narrower and still worth doing

Neither paper **measures how much agent identity a representation carries.** Ramaswamy compares pooled
against per-drug AUC — a performance comparison, not a leakage statistic. Jeong reports transfer accuracy.
Neither quotes a leakage value against a null, and this project already knows why that is hard: **E154
measured the patient-level permutation null's 95th percentile at 0.1904 with 39 clusters, above every
candidate's observed value, and concluded that resolving leakage at 0.10 needs ~140 clusters.**

VitalDB gives **1,474 / 460 / 996** single-agent patients. That is the resolution nobody has had.

**The revised sentence, replacing the one written earlier today:**

> *Frontal EEG measures carry agent identity at |AUC − 0.5| = X, measured at matched behavioural state
> against a patient-level permutation null on ~2,900 patients — a resolution an order of magnitude finer
> than any previous estimate — so the drug-independent estimators already in the literature are [or are
> not] carrying agent information they do not report.*

It is two-sided and decision-relevant either way, which is the property to want. A **large** leakage is a
direct, quantified criticism of every "drug-independent" estimator including Ramaswamy's. A **small** one
says the invariance problem is smaller than the field assumes. Neither outcome is a null.

**This is a measurement, not a discovery, and it is a smaller claim than the one written this morning.**
It is stated that way here so that no later document can quietly re-inflate it.

### Consequences for the design

1. The state-tracking arm becomes a **replication of Ramaswamy 2019**, cited as such, and is not a
   finding. It stays in only because the leakage statistic must be computed **at matched state** and
   therefore needs a state axis that works.
2. E154's duration confound (agent identified at **0.3771**, above every feature) remains the single
   biggest threat and the fixed-window design remains mandatory.
3. **BLOCKED ON THE INVESTIGATOR:** the full text of **PMID 41385421** (IEEE JBHI, paywalled, no PMC).
   One PDF decides whether the minimisation framing is claimed. Institutional access would settle it in
   minutes and it is worth doing before the extraction runs, not after.

## Pre-committed stop #3 does NOT fire — the leakage floor drops 6–8×, and the check validated itself first

Stop #3 was: *"if the patient-level permutation null's 95th percentile does not fall materially below
0.19 at this cohort size, the measurement is no better resolved than before and the line stops."*

The floor is a pure property of the arm sizes, so it needs no features and no extraction — under label
permutation the null AUC has sd = √((n₁+n₂+1) / 12n₁n₂). **That form was validated by reproducing E154's
own measured number before it was trusted anywhere new** (rule 23: an independent implementation), and a
Monte Carlo permutation was run beside it as a second route:

| contrast | n₁ | n₂ | analytic 95th pct of \|AUC−0.5\| | Monte Carlo |
|---|---|---|---|---|
| **E154, MGH OR** (25 vs 14) | 25 | 14 | 0.1913 | 0.1886 |
| **Krause** (E142) | 8 | 7 | 0.3024 | 0.3036 |
| VitalDB sevoflurane vs desflurane | 1,474 | 460 | **0.0302** | 0.0300 |
| VitalDB sevoflurane vs propofol | 1,474 | 996 | **0.0232** | 0.0232 |
| VitalDB desflurane vs propofol | 460 | 996 | **0.0319** | 0.0315 |

E154 reported **0.1904** at 39 clusters and E142 **0.2791** at Krause's 15. The analytic form returns
0.1913 and 0.3024 for those splits, so it reproduces both measured values and can be trusted at the new
sizes.

**The floor falls from 0.1904 to 0.023–0.032 — a factor of 6 to 8.** E154's own conclusion was that
resolving leakage at 0.10 needs roughly 140 clusters and that no public deposit came close; these arms
resolve it at 0.10 with a wide margin and resolve it at **0.05** as well. The measurement E154 could not
make is now makeable, and this is the strongest single reason the line is worth its extraction cost.

Note what this does and does not license. It says the **instrument** now has the resolution. It says
nothing about whether leakage is large or small — that is what the run measures, and both answers are
reportable (a large leakage is a quantified criticism of every "drug-independent" estimator including
Ramaswamy 2019's; a small one says the invariance problem is smaller than the field assumes).

## The landmark rule's one free parameter, derived rather than picked

The ventilation label has exactly one free parameter: how long a run of agreement or separation must
last before it counts as a state change rather than a dropped packet. Rule 63 says a threshold picked as
a round number measures the round number, so it was measured — **in both directions**, because a sustain
derived only from one is one-sided and the two corrupt different landmarks.

Fetched the two 1 Hz tracks for ~56 sampled single-agent cases and counted spurious runs against the
prevailing state: **separations during deep maintenance** (`[aneend−3600, aneend−1800]`, where controlled
ventilation is the background) and **agreements during spontaneous breathing** (`[aneend+300,
aneend+1500]`, restricted to cases actually breathing spontaneously there).

| sustain | spurious separations / case | spurious agreements / case |
|---|---|---|
| 30 s | 0.27 | 0.04 |
| 60 s | 0.07 | 0.02 |
| 90 s | 0.04 | 0.02 |
| **120 s** | **0.00** | **0.02** |
| 300 s | 0.00 | 0.02 |

**Derived value: 120 s (12 grid steps).** It is the smallest sustain at which the separation column
reaches zero, and it sits on a plateau rather than at a cliff — which matters because the measurement was
run twice on differently-drawn samples (92 spurious separated runs in one, 41 in the other, max run length
18 steps against 11) and the two disagree on the tail while agreeing that ~120 s is negligible. A value
chosen at the observed maximum would have been fitting the sample; a value on the plateau is not.

**One thing the mirror column shows that the rule cannot fix, recorded rather than smoothed over.** The
spurious *agreements* are few (2 across 48 cases) but **long** — median 200 s, max 380 s — so no sustain
length removes them and the column plateaus at 0.02 per case. At that length they are almost certainly
not noise: they are episodes where a patient who had resumed spontaneous breathing was supported again.
That is a real state change, and because the rule takes the **last** sustained agreeing run it moves
`t_rec` later in those ~2 % of cases, which is the correct behaviour rather than an error. It is written
down here so that nobody later reads the 0.02 as an unfixed defect.

## The landmarks are built, and criterion (b) is only half met at usable scale

Landmarks emitted for all **2,930** single-agent cases at the derived 120 s sustain, with no errors.

| | sevoflurane | desflurane | propofol | total |
|---|---|---|---|---|
| cases | 1,474 | 460 | 996 | 2,930 |
| **recovery landmark usable** | 1,274 | 415 | 903 | **2,592** |
| **loss landmark usable** | — | — | — | **110** |
| **both directions** | 39 | 15 | 40 | **94** |

**The recovery direction is abundant and the loss direction is not**, and the reason is a design error
rather than a threshold that failed. The sustain was derived from spurious runs during *maintenance* and
during *post-recovery spontaneous breathing* — both long, stable states. The loss landmark's context is
neither: it is the minute or two of pre-intubation spontaneous breathing at the very start of a record,
which frequently does not contain 120 s of *sustained* separation. A single sustain derived from
long-window contexts and applied to a short one was the wrong instrument for that landmark.

**It is not being re-tuned now.** Shortening the sustain after seeing that it costs the loss direction is
the move `DISCOVERY_LOOP.md` §2 forbids and rule 58 names, regardless of how defensible the reasoning
sounds. A separately-derived loss rule is a **successor with a stated instrument change**, not a patch.

### What this costs, stated plainly

**Challenge A's criterion (b) — loss AND recovery — is met in 94 patients, not 2,930.** At 39 / 15 / 40
per arm the patient-level null's 95th percentile is 0.25–0.35, i.e. back where E142 and E154 were, so no
cross-agent contrast is resolvable on the both-directions subset. **The reopened Challenge A is, at
usable scale, a RECOVERY-ONLY design**, and that is weaker than the briefed statement.

**E248's primary is unaffected in power.** The leakage measurement is made at matched state, and matched
state is definable at recovery alone: arms of 1,274 / 415 / 903 give analytic null 95th percentiles of
**0.0325 (sevo–des), 0.0243 (sevo–ppf), 0.0335 (des–ppf)** — the 6–8× improvement over E154's 0.1904
stands. What is lost is the *direction-generality* of the state-tracking arm, which was a replication of
Ramaswamy 2019 rather than a finding.

**Window plan: 2,608 cases, 56,731 windows, median 21 per case** — the fixed 21-offset grid, so recording
length still cannot enter the summary.

## The smoke test caught a dead gate before any result existed — which is what it is for

E248's rule-26 smoke run (arm labels permuted across patients, so every code path executes on real
feature distributions while the real association is never seen) surfaced two defects. Both were repaired
before the extraction finished and before any real number existed, so neither repair is tuning.

**1. G2 — the gate this whole design exists to pass — could not fire.** The nuisance placebo read
`opdur_s`, `age` and `bmi` from the landmark table, which never carried them, so all three returned NaN
in every case. E154's failure was precisely that recording duration out-identified every candidate at
|AUC−0.5| = 0.3771; a design built to beat that confound had shipped with the check inert. Catalogue rule
40 in its exact form, in this project's own file, again. The repair reads the three variables from
VitalDB's clinical endpoint and **refuses to run** if any is finite in fewer than half the cases. After
it: finite in **425 of 425**.

**2. Five candidate columns are all-NaN and were being scored rather than excluded.** `icoh_alpha`,
`lrtc_alpha`, `spatial_participation_ratio`, `uce_v1` and `wpli_alpha` return no finite value on any
window. That is rule 74's exact failure mode — a NaN column scored at p = 0.0000 because
`nanmean(null >= nan)` counts every comparison False — and this project has now hit it four times. They
are dropped with the count reported.

**Worth stating on its own: `uce_v1` is one of the dropped columns.** The project's first named candidate
cannot be computed at all on this deposit. The reason is structural rather than a bug: VitalDB exposes
**two** frontal EEG channels and these windows are **10 s**, and every one of the five dropped measures is
a connectivity or spatial-organisation statistic that needs more channels or a longer window than that.
It is a limit of the deposit, not evidence about the measure, and E248 therefore says nothing about UCE.
