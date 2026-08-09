# E349 + E350 — result note. Twenty tests: does policy fix it, and what does the literature actually say?

Registrations: `e349_policy_and_scope.py`, `e350_conclusions_benchmark.py`, both committed before any
statistic in them existed. Outputs: `e349_policy_and_scope.json`, `e350_conclusions_benchmark.json`.

**Three results carry: the size gradient survives every generalisation test (E349/T4, T5, T10); the
external machinery-failure bound tightens from [0.070, 0.149] to [0.094, 0.129] (E349/T8); and the
literature states an explicit null in 1 conclusion in 107 (E350/T5). Two registered predictions failed,
and one registered statistic turned out to be the wrong instrument for its own question.**

---

# E349 — policy, and how far the findings generalise

## T1 — **the registered statistic said RISE. Reading the series says there is no discontinuity.**

Results posting among completed interventional studies, by start year:

```
2004 0.1964   2007 0.3696 ← peak    2010 0.3269   2014 0.2901   2018 0.2515
2005 0.2490   2008 0.3608           2011 0.3144   2015 0.2891   2019 0.2440
2006 0.3241   2009 0.3535           2012 0.2992   2016 0.2710   2020 0.2320
```

The registered comparison — `mean(2009–12) − mean(2004–07)` — returns **+0.0387**, and the code duly
printed RISE. **But the rise happened entirely BEFORE the boundary**: the series climbs from 0.1964 to a
peak of 0.3696 in **2007**, the year the FDAAA was passed and a year before it took effect, and then
declines monotonically for the next thirteen years.

**So the registered statistic was the wrong instrument for its own question, and this is rule 33 exactly**
— a contrast between two blocks cannot detect a discontinuity, because any smoothly-varying series with a
peak near the boundary will produce one. What was needed was a second difference at 2008 against its own
neighbours. The verdict as registered is +0.0387; **the honest report is that there is no step at 2008,
the increase precedes the mandate, and the post-mandate trend is negative.**

Part of the late decline is censoring (posting is due a year after completion), which the registration
anticipated for T2 but not for T1.

## T2 — Final Rule 2017: **mean(2014–16) 0.2834 → mean(2018–20) 0.2425, change −0.0409.**

Registered in advance: right-censoring biases this downward, so **only a rise would have been readable**.
A decline is uninterpretable and is reported as such, not as evidence the Final Rule failed.

## T3 / T4 — **the phenomenon and its size gradient both exist outside interventional research.**

| | stopped / terminal | rate |
|---|---|---|
| INTERVENTIONAL | 44,742 / 300,090 | 0.1491 [0.1478, 0.1504] |
| OBSERVATIONAL | 7,717 / 78,670 | 0.0981 [0.0960, 0.1002] |

And within observational studies the gradient holds cleanly: **0.2154** (n ≤ 20) → 0.0593 → 0.0394 →
**0.0302** (n > 500). **PREDICTION MET.** This is the strongest available evidence that the gradient is
about study *size* and not about anything peculiar to trials.

## T5 — it holds on both sides of the US boundary, but the levels differ sharply.

| | 1–20 | 501+ |
|---|---|---|
| US site | **0.3498** | 0.0653 |
| no US site | **0.1943** | 0.0367 |

The gradient is present in both. **US-site small studies stop at nearly twice the rate of non-US ones**
(0.3498 vs 0.1943) — most likely because US trials face status-reporting obligations and their
terminations are recorded rather than left dangling. That is a hypothesis; nothing here tests it.

## T6 / T7 — randomisation barely matters; primary purpose does a little.

Randomised 1–20 **0.2948** vs non-randomised 1–20 **0.2803** — essentially the same. By purpose:
TREATMENT 0.1727 · DIAGNOSTIC 0.1788 · SUPPORTIVE_CARE 0.1160 · **BASIC_SCIENCE 0.1001** · PREVENTION
0.0988. `BASIC_SCIENCE`, named in advance as the category closest to this project's own register, is
among the **lowest** — which cuts against reading the register's rate as typical of mechanistic work.

## T8 — **the bound tightens. G8 PASSED at 0.740.**

E346/T2 could only give the external machinery-failure rate as a range, because 46.8 % of `whyStopped`
texts matched nothing. A second pattern set, derived from the unmatched residue's own frequent terms
(`study`, `sponsor`, `decision`, `data`, `analysis`, …) and gated on agreeing with the first pass on the
already-matched corpus (**0.740**, above the registered 0.70 floor), classifies that residue:
**MACHINERY 0.437, RESULT 0.099, still unclassified 0.464.**

```
machinery share of all stops   from >= 0.496   to  0.628 - 0.866
external machinery-failure     from [0.070, 0.149]  to  [0.094, 0.129]
```

**A materially tighter bound**, and it moves the estimate *up*, toward the small-study strata rather than
away from them. 0.464 of the residue plus the 9.6 % of stops with a blank reason remain unclassifiable,
which is why this is still an interval.

## T9 — **machinery failures are doubly invisible.**

Results-posting among terminated studies: **machinery reasons (accrual/enrolment/funding/recruitment)
4,272/9,734 = 0.4389**; **result reasons (efficacy/futility/safety) 1,605/2,847 = 0.5638**. Difference
**+0.1249**. PREDICTION MET.

So a trial stopped because it never got going is *less* likely to post results than one stopped because it
learned something — and E346/T10 already showed the literature reports such events at 1 in 891. **The
invisibility compounds at two separate stages.**

## T10 — size dominates. **Descriptive ranking only, as registered — no model, no variance decomposition.**

```
size (interventional)   0.2231      phase                0.0747
size (observational)    0.1852      study type           0.0510
primary purpose         0.0800      sponsor (at n<=20)   0.0220
```

---

# E350 — the literature benchmark, on CONCLUSIONS rather than whole abstracts

**G1 PASS** on externally-retrieved corpora rather than self-written plants: a positive-language corpus
scores POS 0.508 against a null-language corpus at 0.305, and the null corpus states explicit nulls at
0.063 against 0.005.

## T1 — **PREDICTION NOT MET, and this was named as the outcome that costs the most.**

| | POSITIVE | NULL | **ABSTAIN** | positive among called |
|---|---|---|---|---|
| CONCLUSIONS only (n = 535) | 0.344 | 0.009 | **0.647** | 0.974 |
| same PMIDs, whole abstract | 0.544 | 0.019 | 0.437 | 0.967 |

Abstention on conclusions is **0.647 — higher than the whole-abstract 0.623.** Restricting to the section
where an author states what they found did **not** resolve the ambiguity. **The ambiguity is in how
authors write, not in the section boundary**, and the 1.08×/2.87× spread from E348/T6 is therefore not
fixable by this route. That is the registered wrong-if outcome and it happened.

## T5 — **the cleanest number in either battery. 1 conclusion in 107 states an explicit null.**

**0.0093 [0.0040, 0.0217]** — 5 of 535. And among the conclusions the classifier *can* call either way,
**0.974 are positive**. Whatever one does with the abstentions, the published conclusion that plainly says
"we found nothing" is close to absent.

## T2 / T4 — **PREDICTION NOT MET**, and the literature is remarkably uniform.

RCTs **0.473**, observational **0.433**, meta-analyses 0.453 — RCTs report positives *more*, not less,
against prediction, and all three sit within 0.04. By field: anaesthesia/EEG 0.438, oncology 0.409,
cardiology 0.398, psychiatry 0.368 — a spread of 0.07 across four unrelated literatures.

## T6 — the overstatement factor, under every assignment of abstentions.

| assignment | literature rate | factor vs the register's 0.29–0.32 |
|---|---|---|
| abstentions → positive | 0.991 | **3.10× – 3.42×** |
| abstentions split / dropped | 0.974 | 3.04× – 3.36× |
| abstentions → null | 0.344 | **1.07× – 1.19×** |

**The factor spans 1.07× to 3.42× on the same data, decided entirely by a bookkeeping choice.** E330's
"3.17×" sits inside that span: **it is not wrong, it is under-specified**, and the correction is to publish
the table rather than the number.

## T7 — **NOT INTERPRETABLE, and the reason is worth recording.** Only **2 of 535** unselected abstracts
carry an NCT number in their text. Trial-registration identifiers essentially do not appear in abstract
bodies, so "do registered studies conclude differently?" cannot be asked this way at all.

## T8 / T9 — two nuisance checks that came back clean.

Length is **not** a monotone driver (0.203 / 0.406 / 0.353 / 0.412 across quartiles), so T1 is not a
length artefact — though the shortest quartile abstains much more. And the conclusions and whole-abstract
instruments agree on **0.656** of PMIDs, with the dominant disagreement being whole-abstract POSITIVE →
conclusions ABSTAIN (138 cases): the whole abstract fires on results-section language that the conclusion
does not repeat.

---

## What these twenty tests change

**Strengthened.** The size gradient is not a trials artefact (observational, 0.2154 → 0.0302), not a US
artefact (present both sides), and not a randomisation artefact — and size dominates every other factor
measured. The external machinery-failure rate tightens to **[0.094, 0.129]**. Machinery failures are less
likely to be posted *and* almost never appear in the literature.

**Corrected.** E349/T1's registered statistic reported a rise across the FDAAA boundary; the series shows
the rise *precedes* the mandate and reverses after it. The registered number stands as registered and the
instrument was wrong for the question (rule 33).

**Bounded rather than resolved.** The overstatement factor is 1.07×–3.42× and cannot be narrowed by moving
to conclusions text, because abstention is a property of how authors write (E350/T1). The paper should
publish the table and the explicit-null rate — **1 in 107** — rather than a single ratio.

**Closed.** "Do registered studies conclude differently" is unanswerable from abstract text (2 of 535).
