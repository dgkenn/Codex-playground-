# Data request — Chennu 2014 DoC resting-state EEG cohort (WBIC)

**Status: drafted 2026-07-30, NOT SENT.** To: `enquiries@wbic.cam.ac.uk`, copying the study authors.
The access route is quoted from the paper's own data-availability statement (PMID 25329398, PMC4199497):
*"data are available by request to either the study authors or the Wolfson Brain Imaging Centre's data
protection officer (enquiries@wbic.cam.ac.uk) for researchers who can meet the requisite ethical criteria...
subject to case-by-case review."*

**Why this dataset and no other:** it is the only public record located, across PubMed, OpenNeuro, Dryad,
Zenodo, OSF, Figshare and PhysioNet, that pairs task-free resting-state EEG with a **per-patient
command-following label** — and it carries two, one behavioural and one imaging.

---

## Draft

> **Subject:** Data access request — resting-state EEG, disorders of consciousness (Chennu et al., 2014,
> PLoS Comput Biol)
>
> Dear Wolfson Brain Imaging Centre data protection officer,
>
> I am writing to request access to the resting-state EEG recordings underlying Chennu et al. (2014),
> "Spectral signatures of reorganised brain networks in disorders of consciousness", *PLoS Computational
> Biology* 10(10): e1003887 (PMID 25329398). The paper's data availability statement directs requests to
> your office, and I am following that route.
>
> **What I am asking for.** The 10-minute, 128-channel resting-state recordings from the 32 patients in
> Table 1, together with the per-patient fields already published in that table — etiology, diagnosis,
> CRS-R total, and the two command-following columns (CRS-R and fMRI). If sharing the full cohort is not
> possible, a subset, or derived per-patient spectral and connectivity measures rather than raw traces,
> would still be valuable.
>
> **What the research is.** I am investigating whether spontaneous, task-free EEG carries information about
> a patient's ability to follow commands — that is, whether resting activity alone can flag likely
> cognitive motor dissociation before any task paradigm is attempted. To my knowledge no published study
> predicts command-following specifically from resting EEG; the literature predicts diagnostic category
> (UWS vs MCS) or functional outcome instead. Your Table 1 is, as far as I have been able to establish, the
> only published dataset with a per-patient command-following label alongside genuinely task-free
> recordings — and it includes at least one patient (P3) who was behaviourally negative but fMRI-positive,
> which is precisely the case the question is about.
>
> **How the data would be handled.** Analysis only, no re-identification attempted, no onward sharing, no
> transfer outside the agreed environment, and deletion on completion or on request. I am glad to work
> under whatever data transfer agreement, ethics review or local-processing arrangement you require, and to
> supply a fuller protocol, institutional details and named-custodian information on request. Nothing would
> be published without your review of how the data is described.
>
> **Two things I should be explicit about.** First, this is currently exploratory methodological research
> rather than a funded clinical study, and I would rather say so plainly than overstate it. Second, if the
> ethics protocol under which these patients consented does not admit this use, I would be grateful simply
> to be told that, and I will not press.
>
> I am happy to be redirected to the study authors instead if that is the more appropriate route.
>
> With thanks for considering it,
>
> [name, affiliation, contact]

---

## If this is declined

Challenge B has **no ground-truth command-following label available**, and that has to be stated rather than
worked around. The fallbacks, in order, and each is weaker than the last:

1. **The Della Bella / Sitt cohort** (PMID 40796934, *Commun Biol* 2025) — 237 DoC patients across three
   centres, with a public per-patient table on OSF (node `nfwyj`) carrying diagnosis, CRS-R **total**,
   etiology and outcome. Raw EEG by author request, no formal DUA stated. **CRS-R total is not
   command-following**, so this substitutes a coarser label rather than the one the challenge names.
2. **E28's healthy-BCI substitution**, already running. The review confirmed **no published work tests
   transfer from healthy or sedated populations to DoC in either direction**, so this remains an analogy
   under test and must be reported as one.
3. **MOAA/S on DOSE-I as a graded responsiveness ladder.** Tempting, and the review found the closest
   precedent in Gao et al., *PNAS* 2025 (PMID 40324087), which reports arousal signatures generalising
   across anaesthesia emergence and coma recovery. But **Sarasso 2015 (PMID 26752078) cuts directly
   against it**: behavioural unresponsiveness and consciousness dissociate under anaesthesia — the same
   failure mode cognitive motor dissociation describes in DoC. Using MOAA/S as ground truth for
   command-following would import exactly the error the challenge exists to detect.

---

## AMENDMENT 2026-08-02 — this is in scope, and the draft above needs two changes before sending

**Verified by Opus directly against the PMC full text (PMC4199497), not taken on report.** The paper's own
data-availability statement reads, verbatim:

> *"data are available by request to **either the study authors or** the Wolfson Brain Imaging Centre's
> **data protection officer** (enquiries@wbic.cam.ac.uk) for researchers who can meet the requisite
> ethical criteria for access to confidential UK National Health Service patient data. **All requests
> will be subject to case-by-case review by the WBIC's data access committee.**"*

Three things follow.

**1. The DPO route is offered as an ALTERNATIVE to the authors, and there is a formal data access
committee.** So this is squarely inside the investigator's standing constraint (formal access routes
only, no cold-emailing authors) — it is the record's own published institutional route with a named
review body, not an author request.

**2. Two edits are required to the draft above before it is sent.** As written it (a) copies the study
authors and (b) offers *"I am happy to be redirected to the study authors instead if that is the more
appropriate route."* Both invite exactly the author-mediated channel the constraint excludes. **Remove
both.** Address `enquiries@wbic.cam.ac.uk` only, and let the committee route it if they choose to.

**3. Ask for BOTH cohorts in the same request**, since they share a custodian and a committee:

| | cohort |
|---|---|
| Chennu et al. 2014, **PMID 25329398** | n = 32 DoC patients, 128-channel, 10-min eyes-open resting EEG, CRS-R **and** fMRI-based command-following determinations |
| Chennu et al. 2017, **PMID 28666351** — *"Brain networks predict metabolism, diagnosis and prognosis at the bedside in disorders of consciousness"* (title verified via E-utilities) | the larger follow-on cohort |

**Why this is now the priority request rather than the second one.** A formal-access survey run today found
**no new deposit anywhere** that clears the constraint, and rated this the cleanest escape from rule 86 of
anything located: task-free resting EEG, with command-following determined by **fMRI** — a procedure
entirely separate from the bedside CRS-R that would serve as the clinical comparator. Bath remains the
other live request; this one is not a fallback to it but the better-matched instrument for the briefed
Challenge B question.
