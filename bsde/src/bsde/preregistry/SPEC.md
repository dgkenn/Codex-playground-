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

## Running the tests

The package is stdlib-only and so are its tests, but they are written in two styles and the commands
differ. **`python -m unittest` collects ZERO tests from `test_register.py`** — it is pytest-style
`test_*` functions with bare asserts, and unittest reports "Ran 0 tests ... OK", which reads as a pass.
Use one of:

```bash
PYTHONPATH=bsde/src python -m pytest bsde/src/bsde/preregistry/tests/ -q          # all 22
PYTHONPATH=bsde/src python bsde/src/bsde/preregistry/tests/test_register.py       # 6, no pytest needed
PYTHONPATH=bsde/src python -m unittest bsde.preregistry.tests.test_recurrence     # 16
```

22 tests total: 6 on the register (v1), 16 on the recurrence record (v1.1).

## Adoption cost

One file, appended to. No server, no account, no schema migration. The reference implementation is
stdlib-only Python in two files and can be replaced by anything that emits the same JSON.

---

# v1.1 addition — the recurrence record

*Added 2026-08-08, after E343 tried to measure whether documenting a failure mode prevents it and could
not, on an artifact purpose-built for exactly that. The defect was not in the analysis. It was that the
register recorded failure modes in prose.*

## The problem this solves

A lab that records its failure modes — a lessons-learned file, a post-mortem log, an error catalogue —
has, in principle, the denominator needed to answer the question every such document assumes: *does
writing a failure mode down reduce how often it recurs?* In practice it does not, and E343 verified four
reasons on a 100-rule catalogue with full git history:

1. **Recurrences go undated.** "THIRD OCCURRENCE, ninety minutes after the second" is clear to a reader
   and carries no timestamp. A recurrence that cannot be dated cannot be placed before or after the rule
   meant to prevent it, which is the whole question.
2. **"Nth occurrence" means two opposite things.** A rule *written at* its third occurrence has failed
   zero times; a rule that *accumulated* a third occurrence has failed twice. Prose does not separate
   them, and a classifier that guesses inflates the count.
3. **A recurrence is often filed under a new identifier.** A fresh instance of an old failure mode is
   interesting, so it gets written up as a *new* rule rather than appended to the old one — after which
   no scan of the original rule can find it. This deflates the count, and it is structural rather than
   incidental, so **the naive count is most likely an undercount.**
4. **Free text is not reliably machine-readable at all** — markers split across line wraps, prose
   numbered lists formatted identically to rules, and so on.

Defects 1–3 are properties of the record, not of the reader. No parser fixes them.

## The record

One JSON object per line, append-only, in its own `recurrences.jsonl`. A recurrence is an **event**, not
a property of a rule, so multiple rows may share a `rule_id`.

| field | type | meaning |
|---|---|---|
| `rule_id` | string | **which rule FAILED** — never which document the write-up was filed under. This one field is what makes defect 3 visible. |
| `filed_as` | string or null | where the write-up actually lives, if not under `rule_id`. Non-null is the normal case, not an exception. |
| `occurred_on` | ISO date | when the failure mode recurred |
| `first_stated_on` | ISO date | when `rule_id` was first written down, carried on the row so before/after is decidable offline and survives renumbering |
| `noticed_by` | enum | `self` \| `gate` \| `reviewer` \| `downstream` — see below |
| `was_cited` | bool | whether the rule was invoked **by name** in the work that then violated it |
| `detail` | string | free text, as long as you like; it is never parsed |

`occurred_on < first_stated_on` is legal and meaningful: it records an instance that predates the rule,
which is what a rule written at its own third occurrence should emit. Two such rows plus the rule is the
correct encoding of rule 36's "third occurrence", and it yields **zero** post-statement failures rather
than the false positive a prose scan produces.

## `noticed_by`, and why the lower-bound problem needs it

Every count of recurrences is a **lower bound**, because a recurrence nobody noticed is invisible. That
caveat is unavoidable and usually where the discussion stops. `noticed_by` turns it into an estimable
quantity: if a growing share of recurrences are caught by `gate` rather than by `self`, detection is
improving and the earlier `self`-only counts were more incomplete than the later ones. A register whose
recurrences are *all* `self` has no evidence about its own sensitivity at all.

  * `self` — the analyst noticed while doing the work
  * `gate` — a registered gate refused and the diagnosis followed
  * `reviewer` — someone else found it
  * `downstream` — surfaced only when a later result contradicted an earlier one

## What can then be measured

* **post-statement recurrence count**, exactly: rows with `occurred_on > first_stated_on`, per rule
* **time-to-first-recurrence** and per-rule exposure, so a rule written yesterday is not scored as one
  that held
* **cited-then-violated rate** — `was_cited` among post-statement recurrences. This is the strongest
  form of the finding, because it removes the only innocent explanation: that the rule was unread
* **detection mix over time** — `noticed_by` shares, the only handle on how incomplete the count is

## What it still cannot do

A recurrence nobody ever noticed remains invisible, and no schema changes that. Structure repairs the
recurrences that **were** noticed and mis-recorded; it does not manufacture the ones that were missed.
Any count from this format is reported as a lower bound with its `noticed_by` mix beside it.
