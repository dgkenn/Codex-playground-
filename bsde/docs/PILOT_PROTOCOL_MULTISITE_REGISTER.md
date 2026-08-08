# Multi-site pre-registration register: pilot protocol

*Study B of `PROPOSAL_THE_STUDY_I_WOULD_RUN.md`. Everything needed to run it exists:
`bsde/src/bsde/preregistry/` holds the spec, a stdlib-only reference implementation, an adapter for an
existing register, and a metrics tool validated against an independently written analysis of the same
data.*

---

## The claim under test

On one programme's register of 225 pre-registered biomarker analyses:

| quantity | value |
|---|---|
| died on machinery before testing the hypothesis | **24.0 %** |
| true positive rate (of runs) | **31.6 %** |
| positive rate among those reaching a conclusion | 47.3 % |
| **overstatement factor** of a positives-only view | **3.17×** |
| positives that hedge in their own outcome text | 50.7 % |
| designs naming no incumbent | 64.0 % |
| of machinery failures, the analyst's own gate rather than the data | **29.6 %** |

**The weakness is n = 1 programme, one analyst lineage.** The pilot exists to find out whether any of
this is general or whether it is a fact about us.

## Design

**Sites.** 4–6 labs doing EEG or comparable biomarker discovery. Two is enough for a first pass and would
already establish whether the rates are within an order of magnitude of ours.

**Duration.** 12 months, or 30 registrations per site, whichever comes first.

**Intervention — and there is deliberately almost none.** Sites do not change how they analyse anything.
Before running an analysis they append one JSON line recording question, primary, gates, incumbent,
placebo. Afterwards they attach an outcome from a fixed vocabulary. That is the entire burden.

**Primary outcome.** Between-site spread in the machinery-failure rate. `metrics.py --by-site` computes
it.

**Secondary.** Positive rate, overstatement factor, failures per gate carried, no-incumbent rate,
qualification rate.

**The analyst-defect fraction requires classification and is therefore NOT automated.** Our 29.6 % came
from reading all 54 outcome texts by hand. The pilot should have two readers classify independently and
report agreement; a helper that guesses from keywords would be an oracle pretending to be a measurement.

## What would make the pilot informative either way

* **If between-site spread is small**, these rates are a property of pre-registered biomarker work and
  the headline generalises.
* **If it is large**, the interesting object is *what differs* — gating intensity, field, seniority,
  whether registration is enforced by tooling or by habit.
* **If our rates are outliers**, that is worth knowing and publishable, and it is the outcome this
  protocol most needs to be able to reach. It is named here so that it cannot later be presented as a
  surprise.

## Anticipated objections, with answers

**"This just measures how strictly a lab writes gates."** Partly, and `failures_per_gate` and
`mean_gates` are reported precisely so that raw rates can be read against gating intensity. Our own
machinery-failure rate rose 19.1 % → 26.3 % across the programme while failures *per gate* fell
0.0847 → 0.0638; the raw number alone would have been misleading.

**"Nobody will join, because the output is unflattering."** Likely, and it is the main risk. Two
mitigations: sites may report pooled-only, with per-site rates held by the coordinating centre; and the
register is useful to a lab on its own terms before anyone else sees it, because it makes its own
gate-failure modes visible.

**"Retrospective registration will contaminate it."** The reference implementation refuses to create a
row with any outcome other than `registered`, and refuses to modify any field except the outcome pair.
That is enforcement, not etiquette. It does not stop a determined backdater and nothing would.

**"The outcome vocabulary is arbitrary."** The one distinction the format exists for is
`gate_failed` versus `negative` — an experiment that could not speak versus one that spoke and said no.
Everything else can be collapsed at analysis time.

## Cost

Per site: minutes per analysis, no server, no account, one file under version control. Coordinating
centre: the tooling already exists and is tested. There is no data sharing, no patient information, and
no ethics requirement beyond consent to publish aggregate metadata.

## Deliverables

1. The between-site table above.
2. A pooled taxonomy of machinery failures, two-reader classified with agreement reported.
3. The registers themselves, published — which is the durable part, because a literature cannot contain
   dead experiments and a register is the only place they survive.
