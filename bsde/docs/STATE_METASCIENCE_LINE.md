# STATE — the pre-registration register line (E330 → E350)

*Written 2026-08-09. This is the single current-state document for this line. It supersedes the numbers
in `METASCIENCE_WHAT_KILLS_AN_EXPERIMENT.md`, `PILOT_PROTOCOL_MULTISITE_REGISTER.md` and
`PROPOSAL_THE_STUDY_I_WOULD_RUN.md` wherever they disagree — those three predate E344 and are marked at
their heads. If you are a new session picking this up, read this file and then the result notes only for
the tests you actually need.*

---

## 1. What the line is

This project registered every analysis **before** running it — question, primary, gates, placebo,
incumbent — in an append-only file whose rows cannot be edited except to attach an outcome afterwards.
That gives something the published literature cannot supply: **a denominator for the method**, including
the designs that never reached their hypothesis.

225 registrations. The claim is not about EEG; it is about what happens to analyses.

## 2. The numbers, with their units. **Never quote one without its unit.**

| estimand | value | unit / source |
|---|---|---|
| machinery-failure, per **design** | **0.240** [0.187, 0.298] | 225 registrations (E344/T1) |
| machinery-failure, per **design**, PROSPECTIVE | **0.269** [0.137, 0.461] | 26 pre-committed tests (E347/T7) |
| machinery-failure, per **question** | **0.081** [0.028, 0.213] | 37 lineages, majority vote (E346/T8) |
| true-positive rate | **0.29 – 0.32** | bookkeeping range, not a point (E348/T3) |
| analyst-defect share of gate failures | 0.296 (per design) / 0.444 (per lineage) | E344/T1, E346/T8 |
| no incumbent named | 0.640 / 0.703 | per design / per lineage |

**The row-level and lineage-level rates are DIFFERENT ESTIMANDS, not competing estimates.** The first is
*designs that died*; the second is *questions that mostly died*. Both belong in the paper with their
definitions attached. Analyst-defect moves in the opposite direction between them, which is a property of
majority-voting, not a contradiction.

**The 225 rows are only 37 independent lineages** (E346/T3): effective n is 16.4 % of the row count, and
that is the first thing a referee will find.

## 3. The external benchmark — ClinicalTrials.gov, N = 300,090

| | value |
|---|---|
| stopped share, all interventional | 0.1491 [0.1478, 0.1504] |
| machinery share of those stops | 0.628 – 0.866 (E349/T8) |
| **external machinery-failure rate** | **0.094 – 0.129** |
| **matched stratum: academic/hospital sponsor, enrolment ≤ 20** | **0.2737** (N = 37,843) |

**The matched comparison is the headline.** A register of small-n analyses fails on machinery at
0.24 (retrospective) and 0.27 (prospective); the matched external stratum is 0.2737. **This register's
rate is ordinary for work of this size** — a far better sentence than "this lab fails a lot".

**The size gradient is why**, and it survives every generalisation test tried:

- interventional: 0.2732 (n ≤ 20) → 0.0501 (n > 500), **5.5-fold** (E346/T4)
- observational: 0.2154 → 0.0302 (E349/T4)
- holds in 4/4 phases, 3/3 sponsor classes, both sides of the US boundary, under randomisation
- size spreads the rate by 0.2231 against ≤ 0.08 for phase, purpose, study type and sponsor (E349/T10)

**And E347/T9 supplies the mechanism**: among stopped trials the MACHINERY share is 0.582 at n ≤ 20
against 0.235 above 500, while the RESULT share runs the other way (0.071 vs 0.259). *A large trial that
stops has usually learned something; a small one usually has not.*

## 4. Why none of this reaches the literature

- **1 in 891** published abstracts states that a study could not evaluate its question (E346/T10, three
  fields pooled; the anaesthesia/EEG arm is refused on its own control).
- **1 in 107** published *conclusions* states an explicit null — 0.0093 [0.0040, 0.0217] — and **0.974**
  of the conclusions a classifier can call either way are positive (E350/T5).
- Machinery failures are **doubly invisible**: terminated-for-machinery trials post results at 0.4389
  against 0.5638 for terminated-for-result (E349/T9), on top of the literature rate above.
- Counter-intuitively, **terminated trials post results MORE often than completed ones**, within every
  sponsor class (academic 0.3525 vs 0.1767). The registry captures the stops; it is the *completions*
  that go unreported (E347/T2).

## 5. The argument FOR the format

**E348/T1, the counterfactual: 6 of 7 prospective gate failures had already printed a primary that would
have read as a finding** (0.857 [0.487, 0.974]) — E341's dissociation surviving at p ≤ 0.0028, E346/T5's
"terminations are getting worse", E344/T2's "the labelling is unreliable", and three more, each named in
`results/e348_result_note.md` with the note to check it against.

**A gate failure is a prevented report, not a null.** That is now measured rather than asserted. n = 7,
hand-tabulated, and every call is auditable.

Supporting: **23 % of successors reverse their parent** (43 of 188 pairs, E348/T4) — the successors are
doing real work.

## 6. Corrections a new session MUST carry

1. **"3.17× overstatement" is UNDER-SPECIFIED, not wrong.** E330 contrasted the register's positive rate
   against *"the 100 % a positives-only literature implies"*. Measured, the factor spans **1.07× to
   3.42×** on the same data, decided entirely by how classifier abstentions are assigned (E350/T6).
   **Publish the table, not the ratio.** The quotable number is the explicit-null rate: **1 in 107**.
2. **The outcome labelling CANNOT be audited from text** — not by my vocabulary (E344/T2, destroyed by 54
   rows that merely *mention* withdrawal) nor by an external one from CTG (E346/T7, 6.2 % coverage,
   precision 0.071). **It CAN be audited from the code's own emitted verdict** (E347/T1): 215/225 rows
   resolve to an artifact, **3 contradictions (1.4 %)** against 15 under permuted labels.
3. **Whether the external rate is improving is NOT determined.** The assumption-free lower bound is flat
   near 0.12 across 2005–2020, so there has been **no large improvement**; but that bound is itself
   censoring-depressed, so the direction of any small change needs follow-up times, not status counts
   (E347/T3).
4. **E349/T1 is a self-correction.** The registered two-block statistic printed RISE (+0.0387) across the
   FDAAA boundary, but the series peaks in **2007 — before the mandate** — and declines monotonically for
   thirteen years after. A block contrast cannot detect a discontinuity (rule 33). **There is no step at
   2008.**
5. **A prose lessons-learned register is not machine-auditable** (E343, and rule 101). This repo contains
   **one** auditable register, not two: the burst-suppression programme's 419 results carry 4
   verdict-bearing artifacts across 156 scripts, coverage 0.032 (E348/T10).

## 7. Registered predictions that FAILED, and are reported as failing

| test | prediction | outcome |
|---|---|---|
| E344/T5 | naming an incumbent lowers P(positive) | null, +0.0015, p = 1.0000 — *removes an alternative explanation* |
| E344/T10 | machinery rate falls over the programme | flat, +0.0716, p = 0.3134 |
| E348/T3 | rates robust to canonicalisation within 0.02 | positive rate moved 0.0267 — **failed its own bar** |
| E350/T1 | conclusions-only text reduces abstention | rose to 0.647 from 0.623 — the ambiguity is in how authors write |
| E350/T2 | RCTs report positives less than observational | opposite: 0.473 vs 0.433 |

## 8. Closed cleanly — do not re-run these

- Gate **type** does not predict failure (spread 0.072, overlapping intervals; E348/T2).
- **Deposit** does not predict failure (p = 0.8980; E348/T5).
- The **placebo** contrast is refused on its own rule-32 variance check — 214 of 225 rows name one
  (E348/T7).
- "Do registered studies conclude differently" is **unanswerable from abstract text**: only 2 of 535
  abstracts carry an NCT number (E350/T7).
- **OSF is unreachable** from this environment, so there is no external register *of analyses*.

## 9. What is still open

1. **A second human reader on the outcome labels.** E347/T1 audits what the code emitted; it cannot audit
   a row whose artifact carries no verdict string, and the converse direction (36 rows labelled
   `gate_failed` whose artifact lacks the phrase) is uninformative because verdict strings are not a
   controlled vocabulary.
2. **A second lab.** Everything here is one analyst. `PILOT_PROTOCOL_MULTISITE_REGISTER.md` now carries
   the sample size: **600 registrations per lab** for 80 % power at a 0.10 difference (E348/T9) — an
   upper bound, since the registered rule (non-overlapping 95 % intervals) is stricter than a
   two-proportion test.
3. **The paper itself.** Fifty tests across E344–E350 have supplied every number a referee would demand.
   Writing it is the next step, not more tests.

## 10. Where the evidence lives

| artifact | what it holds |
|---|---|
| `bsde/governance/REGISTRATION_LEDGER.jsonl` | the register, 225 rows, append-only |
| `bsde/src/bsde/preregistry/` | the portable format: `SPEC.md` (v1.1), `register.py`, `metrics.py`, `recurrence.py`, 22 tests |
| `results/e344_result_note.md` | intervals, clustering, the noise-bias of the dissociation criterion |
| `results/e346_result_note.md` | the CTG externalisation, lineage-level rates, two refusals |
| `results/e347_result_note.md` | the code-verdict audit, the prospective sample, the mechanism |
| `results/e348_result_note.md` | the counterfactual, the 3.17× correction, successor reversals |
| `results/e349_e350_result_note.md` | policy discontinuities, generalisation, the conclusions benchmark |
| `results/e343_result_note.md` | why a prose register cannot audit itself |
