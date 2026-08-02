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
