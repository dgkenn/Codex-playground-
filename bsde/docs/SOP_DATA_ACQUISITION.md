# SOP — data acquisition: rank routes by whether a human has to say yes

*Standing. Written 2026-08-07 after a session that produced three data requests, all of which depend on
authors replying to email. **That is the lowest-yield route in existence and this project had made it the
plan.** The rule below is not about politeness; it is about designing studies that can actually run.*

---

## The ranking, and the only question that matters for each tier

**Ask of any dataset: what has to happen for me to hold it? If the answer contains "someone chooses to
reply", it is Tier 4 and it is not a plan.**

### Tier 0 — open, no request, no account
OpenNeuro, Zenodo, Dryad, figshare, OSF, PhysioNet open-access, G-Node, CRCNS (some).
**Latency: minutes.** Failure mode: the label you need was never deposited (ds005620's awakening reports).
**Always check what is deposited, not what the paper describes.**

### Tier 1 — automated or form-based credentialing; the gatekeeper is a process, not a person
PhysioNet credentialed (CITI training + signed DUA), **NSRR (National Sleep Research Resource)**, DANDI,
NEMAR, BossDB, OpenNeuro restricted.
**Latency: days to weeks, deterministic.** These are the highest-value tier for this project and are
systematically under-used here — NSRR alone holds tens of thousands of scored PSGs with EMG.

### Tier 2 — structured application to a committee, published criteria, appealable
dbGaP, NIMH NDA, UK Biobank, ABCD, HCP, ADNI, institutional biobanks.
**Latency: 1–6 months, but the criteria are written down and the decision is reviewable.** A rejection
tells you why. Budget for it in a grant, not in a sprint.

### Tier 3 — no permission required at all, because it is already published
Supplementary tables, per-subject figures (digitisation is standard practice in meta-analysis and is
citable), reported effect sizes and confidence intervals, theses and preprints — **university repository
theses routinely contain the per-subject appendices the paper omitted**.
**Latency: hours.** This tier is chronically forgotten and it is how a meta-analysis is built.

### Tier 4 — email the authors
**Assume it fails.** Response rates for IPD requests are poor and non-response is uninformative — you
cannot distinguish refusal from a stale address. **Never let a study design depend on Tier 4.** Send it
anyway if the ask is cheap, but the study must be viable without it.

---

## The design rule this produces, and it inverts how this project has worked

**Do not design the ideal study and then look for data. Enumerate what is reachable at Tier 0–2, then ask
which real question that inventory can answer.** Every stalled line in this programme — Challenge B's
command-following label, Challenge A's two-agent cohort, Study A's serial awakenings — comes from having
done it the other way round.

**Corollary for novelty checks:** before proposing a study, search for the cohort *and* for the paper. In
this session Study A was proposed as novel and Casey 2022 (PMID 35148892, NCT03284307) had already run
it. The search that would have caught it is the same one that finds the data.

---

## Journal-defensible substitutes when the data will not come

Ranked by how well they survive review:

1. **Re-analysis of a Tier 0–2 cohort with the same contrast**, stating explicitly what differs from the
   cohort you wanted. Strongest.
2. **Meta-analysis of published effect sizes** across studies. Needs no IPD and is the standard method for
   exactly this situation.
3. **Digitised per-subject data from figures**, with the digitisation tool and error named. Accepted
   practice; say so in the methods.
4. **A methods or negative result on data you hold**, framed as what the field's measures do rather than
   what the brain does. This is where E321 and the leakage line actually live.
5. **Meta-research on your own record** — needs no patient data at all, which is why Study B is the
   tractable one. `bsde/src/bsde/preregistry/`.

**Not defensible:** describing an analysis you could not run, or reporting a Tier 4 non-response as
evidence about the data.

---

## What to do before writing another data request

1. **Search Tier 0–1 for the contrast, not the cohort.** You want a *state comparison*, not a specific
   study. Different deposits may supply it.
2. **Check the trial registry** for an IPD sharing statement (`clinicaltrials.gov/api/v2/studies/NCTxxxx`,
   field `ipdSharingStatementModule`). **An empty statement means no declared plan and predicts
   non-response.** NCT03284307's is empty.
3. **Check for a thesis.** Multi-year EEG studies produce them, and they carry appendices.
4. **Check whether the derived quantity you need is already in the paper.** Casey 2022's AUCs and CIs are
   published; some questions are answerable from them.
5. Only then, send the email — and design as though it will not be answered.
