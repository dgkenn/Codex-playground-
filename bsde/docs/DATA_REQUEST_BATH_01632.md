# Data access request — Bath PDoC motor-imagery BCI dataset (DOI 10.15125/BATH-01632)

*Drafted 2026-08-02. **Not sent.** Fields in `[[ ]]` must be completed or deleted by the investigator
before sending — several of them are claims I cannot make on your behalf.*

**Target record:** https://researchdata.bath.ac.uk/1632/ — *Motor-imagery brain-computer interface
electroencephalography and behavioural assessment datasets in prolonged disorders of consciousness*,
Coyle D., Du Bois N., Korik A., 2026. ClinicalTrials.gov NCT03827187. Cohort N = 42 (UWS 14, MCS 17,
LIS 11) plus 2 able-bodied benchmark participants. Access is a "mixed access regime" — granted on
reasonable request, subject to custodian review.

**Route:** the record's own contact/request mechanism on the landing page, copying
`researchdata@bath.ac.uk` if a direct address is not offered. Prof. Damien Coyle is the corresponding
author.

> ⚠️ **Check before sending.** `DEPOSIT_ACCESS_STATUS.md` states this was "requested 2026-07-30" while
> `MASTER_PLAN.md` line 233 still lists *"File the Bath access request"* as an open action, and there is
> no artefact of a sent request anywhere in the repo. If one *was* sent, use the bracketed follow-up
> opening instead of the first paragraph — sending a fresh first-contact request over an existing one
> reads badly to a custodian.

---

**Subject:** Data access request — BATH-01632 (motor-imagery BCI in prolonged disorders of consciousness)

Dear Professor Coyle and colleagues,

I am writing to request access to the dataset *Motor-imagery brain-computer interface
electroencephalography and behavioural assessment datasets in prolonged disorders of consciousness*
(DOI 10.15125/BATH-01632).

*[[FOLLOW-UP VARIANT — use instead of the paragraph above if a request was already sent on 30 July:
"I wrote on 30 July to request access to BATH-01632 and am following up in case that message did not
reach the right person. I am happy to resubmit through whichever route you prefer."]]*

I am [[ROLE]] at [[INSTITUTION]], working on methods for assessing residual cognitive capacity from EEG.
The specific question I need this dataset for is whether **task-free EEG recorded outside an active
paradigm carries information about a patient's capacity to follow commands** — and, critically, whether
it does so beyond what is already available from the bedside behavioural assessment.

That last clause is why your dataset is the one I need rather than one of several options. The
comparison requires an outcome scored by a procedure **independent of the clinical observation it is
being tested against**. In a motor-imagery BCI the outcome is produced by a classifier from the EEG
itself, not by a rater at the bedside, while your concurrent behavioural scores provide the clinical
comparator separately. I have surveyed OpenNeuro, PhysioNet, Zenodo, Dryad, Figshare and OSF for a
public dataset combining patient-level command-following with session-linked behavioural assessment, and
found none — every accessible alternative either lacks the patient cohort or scores the outcome and the
comparator in the same clinical encounter, which makes the comparison uninformative.

What I would need is the EEG with its task event triggers and the session-level behavioural scores; I do
not need any direct identifiers, imaging, or clinical free text.

On handling: [[STATE YOUR ACTUAL POSITION — do not overstate]]. I would expect to sign a data use
agreement, to hold the data on [[institutionally managed / encrypted storage]] with no redistribution
and no deposit of derived data that could be re-identified, and to delete it on request or at the end of
the agreed period. [[If you have IRB/ethics approval or an exemption determination, say so and give the
number. If you do not yet, say that you will obtain it before any data transfer — do not imply you have
it.]]

I would of course acknowledge the dataset and cite the record and the associated trial (NCT03827187) in
any output, and I am glad to share findings with you before publication, or to discuss co-authorship if
you would prefer involvement rather than release.

If a formal application, DUA, or sponsor is required, I would be grateful if you could point me to it.

With thanks and best wishes,

[[NAME]]
[[TITLE, DEPARTMENT, INSTITUTION]]
[[EMAIL]] · [[ORCID or institutional page]]

---

## Notes on what this deliberately does not say

Custodians need enough to judge that the request is reasonable and the data will be safe. They do not
need the analysis plan, and stating it invites scope negotiation over methods.

**Included:** the general question, the one structural property of the dataset that makes it necessary
(an outcome scored independently of the clinical comparator), evidence that alternatives were checked,
the minimum fields needed, and the handling commitments.

**Deliberately omitted:** which EEG measures are candidates, the verifier architecture, the pre-registered
gate and placebo design, and the fact that this sits inside a broader programme with two other challenges.
None of that helps a custodian decide, and all of it is easier to discuss later than to walk back.

**Do not add:** any claim of funding, ethics approval, institutional sponsorship or prior collaboration
that is not already true. A custodian who discovers an overstatement at DUA stage will refuse, and this
is the only dataset of its kind that was found.
