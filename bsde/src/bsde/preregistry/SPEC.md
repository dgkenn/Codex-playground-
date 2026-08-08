# The Minimal Pre-Registration Register — v1 specification

*A portable, tool-agnostic format for recording what an analysis intended **before** it ran, and what
happened after. Designed so that a lab can adopt it without adopting anything else.*

---

## Why this format and not a general pre-registration platform

Existing pre-registration (OSF, AsPredicted, ClinicalTrials.gov) records **intent** and is optimised for
human reading. It rarely records **outcome**, and almost never records the *machinery* — the gates a
design must clear before its hypothesis is even testable. The quantities that turn out to matter
(what fraction of designs die before testing anything; how often the refusal is the analyst's own gate)
are not recoverable from those platforms.

This format adds exactly three things and nothing else: **gates**, **an incumbent**, and **a
machine-readable outcome class**.

## The record

One JSON object per line, append-only (`.jsonl`). Rows are never edited except to attach `outcome` and
`outcome_detail`. Required fields:

| field | type | meaning |
|---|---|---|
| `id` | string | unique within the register |
| `registered_utc` | ISO-8601 | when the design was registered, **before** running |
| `question` | string | one sentence, the thing being asked |
| `primary` | string | the statistic that answers it, specified enough to compute |
| `gates` | array of strings | each a condition that, if it fails, means the primary **must not** be interpreted |
| `incumbent` | string | what the result must beat. `""` is permitted and is counted as a defect |
| `placebo` | string or null | the control that destroys the effect while preserving nuisance structure |
| `outcome` | enum | see below; `registered` until the run completes |
| `outcome_detail` | string | free text, written after |

Optional: `successor_of`, `instrument_changed`, `dataset`, `code_ref`, `tags`.

## The outcome vocabulary — deliberately more granular than pass/fail

| value | meaning |
|---|---|
| `registered` | not yet run |
| `gate_failed` | a gate refused; **the hypothesis was never tested** |
| `positive` | the primary supported the hypothesis |
| `negative` | the primary refuted it |
| `absent` | the primary ran and found nothing, with adequate power |
| `blocked` | could not run for access or resource reasons |
| `withdrawn` | a verdict was issued and later retracted |
| `closed` | the question was retired without a verdict |

**`gate_failed` versus `negative` is the distinction the whole format exists for.** A negative result
says something about the world. A gate failure says the experiment could not speak, and the two are
routinely conflated in the literature because only one of them gets published.

## The one rule that makes the register worth keeping

**A row is written before the analysis runs, and `outcome` is attached after.** If rows are created
retrospectively the register measures nothing. The reference implementation refuses to create a row whose
`outcome` is anything other than `registered`, and refuses to modify any field except `outcome` and
`outcome_detail`.

## What can then be measured, that a literature cannot supply

* **machinery-failure rate** — `gate_failed / all`
* **overstatement factor** — `1 / (positive / all)`, i.e. how much a positives-only view inflates success
* **analyst-defect fraction** — of the gate failures, how many were the gate rather than the data
  (requires classifying `outcome_detail`; the reference implementation ships a helper, not an oracle)
* **qualification rate** — positives whose own detail text contains a hedge
* **failures per gate carried** — controls for how heavily designs are gated

## Adoption cost

One file, appended to. No server, no account, no schema migration. The reference implementation is
stdlib-only Python in two files and can be replaced by anything that emits the same JSON.
