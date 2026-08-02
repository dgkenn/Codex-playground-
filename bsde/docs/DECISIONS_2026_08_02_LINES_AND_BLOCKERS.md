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
