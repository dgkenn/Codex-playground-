# E347 — result note. Nine interpretable, one bounded instead of refused.

Registration: `bsde/src/bsde/experiments/e347_audit_and_standardise.py`, committed before any statistic in
it existed except T2's headline direction, which is declared SEEN in the registration itself. Output:
`bsde/results/e347_audit_and_standardise.json`.

**The headline: the register's rate is now validated three ways that agree — retrospectively, prospectively,
and against the matched external stratum — and the audit that E346 said needed a human reader turned out to
be mechanical after all.**

---

## T1 — **the audit that works.** 3 detectable contradictions in 215 rows.

Two attempts to audit this register's outcome labels from *text* failed: my own vocabulary (E344/T2,
destroyed by 54 rows that merely *mention* withdrawal) and an external one from CTG (E346/T7, 6.2 %
coverage). I concluded it needed a second human reader. **That was too quick.** Every row carries a
`file`, every experiment writes a result JSON, and most carry the verdict string the **code itself**
emitted at run time — a third artifact, and not prose.

The audit tests the one implication needing no vocabulary judgement: *an artifact saying NOT INTERPRETABLE
while the row claims anything other than `gate_failed`.*

- **G1 PASS** — a planted contradiction is detected, a planted consistent pair is not.
- **G1b PASS** — 215 of 225 rows (95.6 %) resolve to an artifact.
- **Under permuted labels the count is 15; on the real labels it is 3.** The detector detects.

| row | register says | artifact says |
|---|---|---|
| `e110` | negative | NOT INTERPRETABLE |
| `e115` | withdrawn | NOT INTERPRETABLE |
| `E243` | negative | NOT INTERPRETABLE |

**3 of 215 = 1.4 %**, and the registered prediction ("a small non-zero count") is met. One nuance worth
stating rather than burying: `e115` is labelled **`withdrawn`**, which is a defensible label for a result
that was retracted — but the registered criterion counts it, and I am not narrowing the criterion after
seeing which rows it caught. Reported as 3, with the nuance attached.

Also reported, and **not** scored as errors: 36 rows labelled `gate_failed` whose artifact does not carry
that phrase. Verdict strings are not a controlled vocabulary and a gate failure can be phrased many ways,
so the converse direction is uninformative — which is exactly why the primary is one-directional.

> **What this changes: the labelling is now audited, at 1.4 % detected fault, by a method with a
> demonstrated detection capability.** E346's "needs a human reader" is withdrawn. The remaining caveat is
> honest and narrow: this detects only faults visible in the code's own verdict string.

## T2 — **counterintuitive, and it holds within every sponsor stratum.**

Declared SEEN before registration: terminated trials post results *more* often than completed ones
(0.3902 vs 0.2429), refuting what I expected. The registered contribution was the decomposition, and it
rules out the obvious explanation:

| | COMPLETED | TERMINATED |
|---|---|---|
| INDUSTRY | 0.3852 (75,148) | **0.4528** (10,507) |
| NIH | 0.2976 (5,665) | **0.5730** (747) |
| OTHER (academic/hospital) | 0.1767 (164,066) | **0.3525** (17,446) |

**Terminated trials post more in all three classes**, by the largest margin in NIH (nearly 2×). So it is
not sponsor composition.

The implication for the paper is the useful part: **the registry captures the stops. It is the
completions that go unreported** — and, per E346/T10, the *literature* reports such events at 1 in 891.
The failure is not in the registry, it is downstream of it.

## T3 — **bounded rather than refused.** No large improvement, direction still undetermined.

E346/T5 was NOT INTERPRETABLE because censoring confounded the trend. T3 replaces one cutoff with two
quantities:

- **Trend over cohorts clearing 0.90 follow-up** — only 2005–2008 qualify (follow-up falls below 0.90
  from 2009). Slope **+0.01175/yr** on 4 points, all at the start of the window. Too few to carry a claim.
- **Assumption-free lower bound** (stopped / *all* registered, which incomplete follow-up cannot inflate):
  0.1180 → 0.1484 (2007) → 0.1185 (2020), slope **−0.00153/yr** over all 16 cohorts. Remarkably flat,
  hovering near **0.12**.

**And the two do not settle the direction, for a reason worth stating explicitly.** The lower bound is
*also* depressed in recent cohorts, because studies still running have not stopped **yet**. So a flat
lower bound under growing censoring is consistent with a *rising* true rate.

> **What T3 licenses is a bound, not a trend: every cohort from 2005 to 2020 eventually stops at least
> ~12 % of its registered studies, so there has been no large improvement.** Whether there has been a
> small one in either direction is not determined by status counts, and would need actual follow-up times.
> That is a better outcome than E346/T5's refusal and weaker than a trend; both statements belong.

## T4 — the size gradient survives phase. **4 of 4. PREDICTION MET.**

| phase | 1–20 | 21–100 | 101–500 | 501+ |
|---|---|---|---|---|
| PHASE1 | 0.235 | 0.086 | 0.077 | 0.025 |
| PHASE2 | 0.433 | 0.130 | 0.089 | 0.074 |
| PHASE3 | **0.450** | 0.153 | 0.090 | 0.074 |
| PHASE4 | 0.369 | 0.090 | 0.057 | 0.036 |

Not a phase effect wearing a size costume. Note the extreme cell: **45 % of phase-3 trials with ≤ 20
participants stop.**

## T5 — it survives sponsor too, and gives the comparator to quote.

| sponsor | 1–20 | 21–100 | 101–500 | 501+ |
|---|---|---|---|---|
| INDUSTRY | 0.275 | 0.108 | 0.088 | 0.072 |
| NIH | 0.296 | 0.101 | 0.057 | 0.039 |
| OTHER | **0.274** | 0.064 | 0.045 | 0.034 |

**The tightest external comparator, named in advance: academic/hospital sponsor, enrolment ≤ 20 —
10,359/37,843 = 0.2737.**

## T6 — my own field is *less* affected, not more.

Anaesthesia-condition interventional studies: 457/4,780 stopped = **0.0956**, against 0.1491 corpus-wide.
Machinery share within the field **0.492**, essentially the corpus value (0.472). So anaesthesia trials
stop less often and for the same reasons. Nothing about this domain is unusual in the direction that
would explain the register's rate.

## T7 — **the prospective sample E344/T7 refused for want of data.**

Every test registered and run in this session, each named in the output so a reader can check the call
against its result note: **26 tests** (E340–E346, with E344 and E346 contributing ten pre-committed tests
each).

```
positive     15  (0.577)      absent        2  (0.077)
gate_failed   7  (0.269)      negative      1  (0.038)
                              blocked       1  (0.038)
```

**Prospective machinery-failure rate: 7/26 = 0.269 [0.137, 0.461].** n = 26, so this is a tabulation and
not an estimate — but it is genuinely prospective, every gate was pre-committed, and it lands on top of
the retrospective row-level 0.240 [0.187, 0.298].

## T8 — the `absent` verdicts are powered. **PREDICTION MET.**

16 of 18 (0.889 [0.672, 0.969]) state an interval or an effect size. An absence with no stated resolution
is not an absence, and this register mostly avoids that.

## T9 — **the finding that explains T4.** Small studies stop for machinery; large ones stop on results.

| enrolment | MACHINERY | RESULT | OTHER | n |
|---|---|---|---|---|
| 1–20 | **0.582** | 0.071 | 0.347 | 1,200 |
| 501+ | **0.235** | 0.259 | 0.506 | 941 |

E346/T4 showed *how often* stopping depends on size. T9 shows *why* does too, and in the direction that
matters: **a big trial that stops has usually learned something; a small one usually has not.** The
RESULT share is 3.6× higher in large studies and the MACHINERY share is 2.5× higher in small ones.

## T10 — direct standardisation. **No significance test, as registered.**

Every analysis in this register is small-n, so its size distribution is a point mass in the smallest
stratum; standardising CTG to it reduces to reading that cell, and the file says so rather than dressing
it as a model.

```
CTG, academic/hospital sponsor, enrolment <= 20   0.2737          N = 37,843
this register, row level          (E344/T1)       0.240  [0.187, 0.298]   n = 225 registrations
this register, PROSPECTIVE        (T7)            0.269  [0.137, 0.461]   n = 26 tests
this register, lineage level      (E346/T8)       0.081  [0.028, 0.213]   n = 37 lineages
CTG, all studies                                  0.1491                  N = 300,090
```

The first three land on top of each other. That is stated as an observation, not a test — the two
artifacts count different objects and a p-value would imply a common estimand that does not exist.

---

## What E347 does to the paper

**Three things that were open are now closed.** The labelling is audited mechanically at 1.4 % detected
fault (T1). There is a prospective sample and it agrees with the retrospective one (T7). And the size
gradient is not a phase or sponsor artefact (T4, T5) — with T9 supplying the mechanism.

**The claim is now a matched comparison, not a coincidence.** A register of small-n analyses fails on
machinery at ~0.24–0.27; the matched external stratum — academic-sponsored trials with ≤ 20 participants,
n = 37,843 — fails at 0.2737. **This is what work of this size does**, and the paper can say so with a
denominator behind it.

**One thing remains genuinely undetermined**, and is now bounded rather than refused: whether the external
rate is improving. Every cohort 2005–2020 eventually stops ≥ ~12 % of its studies, so there has been no
large improvement; finer than that needs follow-up times, not status counts (T3).
