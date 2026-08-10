# What kills a pre-registered biomarker experiment? Evidence from 225 of them

> ## ⚠ SUPERSEDED IN PART — read `STATE_METASCIENCE_LINE.md` first
>
> This document is **E330/E331 as written on 2026-08-07** and is kept as the record of what that analysis
> said. Fifty further tests (E344–E350) have since added intervals, an external benchmark of 300,090
> ClinicalTrials.gov studies, a prospective sample, and a mechanical audit of the outcome labelling.
> **Three numbers below are corrected there:**
>
> * the rates need a **unit** — 0.240 [0.187, 0.298] per *design*, 0.081 [0.028, 0.213] per *question*
>   (the 225 rows are only 37 independent lineages);
> * the true-positive rate is a **range, 0.29–0.32**, not 0.316 — it moves with how 11 free-text outcomes
>   are mapped;
> * **"3.17×" is under-specified**, spanning 1.07×–3.42× by how classifier abstentions are assigned. The
>   quotable literature figure is the explicit-null rate, **1 conclusion in 107**.
>
> Nothing below is retracted; it is the earlier and less-qualified version of the same measurements.


**E330, 2026-08-07.** Meta-research on this project's own append-only registration ledger. Predictions
committed before any statistic was computed; `results/e330_ledger_metascience.json` carries the output.

---

## 1. Why this data exists and why it is unusual

The published EEG-consciousness literature contains **survivors**. An experiment that died because its
gate could not fire, its placebo could not be constructed, its incumbent turned out to be dead in the
cohort, or its statistic was passed by noise **does not become a paper**. The field therefore has no
denominator for its own method.

This project registered every design *before* running it — primary, gates, placebo, incumbent, and
afterwards an outcome — in an append-only file whose rows cannot be edited except to attach that outcome.
**225 registrations.** That is a denominator.

## 2. A quarter of designs never reached their hypothesis

| outcome | n | share |
|---|---|---|
| positive | 71 | 31.6 % *(→ 0.29–0.32 corrected, E348/T3)* |
| negative | 56 | 24.9 % |
| **gate_failed** | **54** | **24.0 %** *(per DESIGN; 0.081 per QUESTION, E346/T8)* |
| absent | 18 | 8.0 % |
| withdrawn | 8 | 3.6 % |
| blocked | 6 | 2.7 % |
| closed | 5 | 2.2 % |
| mixed | 2 | 0.9 % |

**54 of 225 designs (24.0 %) died on machinery** — a gate refused before the hypothesis was tested. These
are not negative results. Nothing about the biology was learned, and none of them would have appeared
anywhere in a conventional literature.

## 3. A positives-only literature would overstate success threefold

    positives                                71
    reached any biological conclusion       150   (positive + negative + absent)
    registered but never concluded           75

    true positive rate, all registrations   31.6 %
    positive rate among those that concluded 47.3 %
    implied rate if only positives are seen  100 %
    OVERSTATEMENT FACTOR                     3.17x   <-- UNDER-SPECIFIED: 1.07x-3.42x (E350/T6)

And the positives are softer than their label: **35 of 71 (49 %) carry an explicit qualification in their
own outcome text** — "but", "however", "not licensed", "caveat". The register contains 159 separate
mentions of reversal language (overturned, withdrawn, superseded, corrected).

## 4. The prediction that failed, and the disambiguation that changes its meaning

I predicted machinery failure would **fall** across the programme as its error catalogue grew from 25
rules to 97. **It rose: 19.1 % → 28.4 %.** Registered as the more important outcome, because it would
mean the catalogue documents failures without preventing them.

**It does not mean that, and one extra measurement shows why.**

| | first half | second half |
|---|---|---|
| mean gates per design | 2.51 | **4.13** |
| designs naming an incumbent | 25.5 % | **41.1 %** |
| machinery failure (raw) | 21.3 % | 26.3 % |
| **machinery failures per gate carried** | 0.0847 | **0.0638** |

Designs came to carry **64 % more gates**, and named an incumbent **61 % more often**. Per gate written,
the failure rate **fell by 25 %**. The raw rise is substantially a consequence of more things being
checked, not of designs getting worse.

**This is not a clean win and I am not reporting it as one.** Conditional on gate count the evidence is
mixed and underpowered — at 3 gates the failure rate fell (30.8 % → 0.0 %, but n = 11 in the second half),
at 4 gates it rose (23.5 % → 34.4 %). **P3 fails as registered.** What the data supports is the narrower
statement that the raw rise is confounded with gating intensity, and that the deflationary reading is not
established.


## 4b. A taxonomy of the 54 machinery failures — and 30 % of them were my own gate

All 54 were classified by reading every `outcome_detail` in full; none was left unclassified.

| class | n |
|---|---|
| coverage / support floor not met | 6 |
| **incumbent or phenomenon not alive in the cohort** | **6** |
| gate itself defective | 4 |
| positive / capability control silent | 5 |
| artefact or sentinel exposed | 2 |
| exposure shape (off-state, no variance) | 2 |
| surrogate or placebo unusable | 4 |
| implementation defect | 2 |
| confound exposed by the gate | 2 |
| *(21 further classes at n = 1)* | 21 |

Collapsing by whether the gate caught something real:

    THE GATE CAUGHT A REAL PROBLEM IN THE DATA OR COHORT    38   70.4 %
    THE GATE OR THE CODE WAS ITSELF DEFECTIVE               16   29.6 %

**Nearly a third of machinery failures were the analyst's own apparatus, not the data** — vacuous success
bars, verdict rules that could not express the wrong-direction case, thresholds set below what the
arithmetic could resolve, placebos insensitive to the estimand, and in one case a file whose registered
gates were never implemented at all. That number is the most useful thing in this document for anyone
adopting the method: **budget for the fact that a third of your refusals will be your own mistakes, and
that you will only find them because the gate refused.**

The single most actionable data-side class is **"incumbent or phenomenon not alive"** at 6 of 54. These
are designs that would have produced a publishable-looking comparison against something that does not
work in that cohort — a bar nothing needed to clear. None of them would have been detectable from the
result alone.

## 4c. The external comparison I can make, and the one I cannot

Fanelli 2010 (*PLoS One*, **PMID 20383332**, retrieved and read from its MEDLINE record) analysed 2,434
papers that declared to have tested a hypothesis, and found the odds of reporting a positive result
around **5 times higher** in Psychology/Psychiatry and Economics/Business than in Space Science, **2.3
times higher** in social than physical sciences, and **3.4 times higher** for behavioural methodologies
on people than physical studies on non-biological material, with biological studies intermediate.

**That paper reports odds ratios, not absolute positive-result rates, so no percentage is quoted from it
here** (rule 42: a quotation supports only what it literally says). It establishes that published
positive-result rates are high and vary systematically by field; it does not supply the number against
which our 31.6 % could be directly benchmarked. **That benchmark NOW EXISTS -- see E346/T10, E349, E350 in `STATE_METASCIENCE_LINE.md`.** As of 2026-08-07 it did not exist in a form I could
verify, and inventing one would be the exact error this document is about.**

## 5. More gates means more machinery failure, and that is the mechanism working

| gates carried | machinery failure |
|---|---|
| 0 | 0.0 % (n = 8) |
| 1–2 | 17.9 % |
| 3 | 20.0 % |
| 4 | 30.9 % |
| 5+ | 23.1 % |

≤ 2 gates: **14.9 %**. ≥ 4 gates: **28.6 %**. A design with no gates cannot fail on machinery — it can
only produce a number. Rule 40 in this project's catalogue says a gate that cannot fail is not a gate; the
converse is visible here as an ungated design that cannot be refused.

## 6. What generalises, and what does not

**The specific rates are this programme's alone.** One research line, anaesthesia and sleep EEG, a single
analyst lineage, one deposit family. This is not a sample of the field and no sentence here should be read
as a claim about how other laboratories fare.

**The method generalises, and it is the contribution.** Keep an append-only register in which each design
states its primary, its gates, its placebo and its incumbent *before* it runs, and attach an outcome
afterwards. These quantities then become measurable — the machinery-failure fraction, the overstatement
factor, the qualification rate among positives, the failure rate per gate — and none of them is
recoverable from a published literature, because the register is the only place the dead experiments
survive.

The uncomfortable corollary: **a field that does not keep this record cannot know its own denominator**,
and the more rigorous its published work looks, the less it can say about what its methods do on average.
