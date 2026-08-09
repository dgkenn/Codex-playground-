# E348 — result note. The argument FOR the format, and a correction to its most quotable number.

Registration: `bsde/src/bsde/experiments/e348_counterfactual_and_design.py`, committed before any statistic
in it existed. Output: `bsde/results/e348_counterfactual_and_design.json`.

**Two things matter here. T1 supplies the argument the paper was missing. T6 forces a correction to
E330's "3.17× overstatement", which turns out to depend entirely on a denominator nobody had stated.**

---

## T1 — **the counterfactual. 6 of 7. PREDICTION MET.**

The register format's whole claim is that a gate failure is not a null but a *prevented report*. That had
never been quantified. Scope is the 26 prospective tests of E340–E346, because only there is every
primary's printed value in a committed note that a reader can check.

| test | would it have been reported? | what had already printed |
|---|---|---|
| E340/P2 | **yes** | muscle proxies vs real EMG all \|ρ\| ≤ 0.18 → "the measures are not muscle-driven" |
| E341 | **yes** | the dissociation SURVIVING removal of `allEnvCorr` at p ≤ 0.0028 on all four tests |
| E343 | **yes** | 3 rules with 5 post-statement recurrences; 3 cited-then-violated |
| E344/T2 | **yes** | agreement 0.353 → "E330's labelling is unreliable" |
| E346/T5 | **yes** | slope +0.00142/yr → "trial terminations are getting worse over 16 years" |
| E346/T7 | **yes** | precision 0.071 → a finding about auditability rather than insufficient coverage |
| E344/T7 | no | no held-out rows existed, so no primary was computed at all |

**6 of 7 = 0.857 [0.487, 0.974].** Every one of those six is a claim I would have written up, and four of
them are the kind that reads well: a clean negative, a survival at p ≤ 0.0028, a quantified trend, a
methodological warning. n = 7, hand-tabulated, and each call is named above with the note to check it
against — the same standing as E347/T7, and not a rate to compare against anything.

## T6 — **the correction. "3.17× overstatement" depends on a denominator that was never stated.**

E330's most quotable number contrasted this register's true-positive rate against *"the 100 % a
positives-only literature implies"*. **That assumption is not what the literature does.** Measuring it
directly on 297 unselected PubMed abstracts (G6 PASS: a positive-language corpus scores 0.759 against a
null-language corpus at 0.025, so the classifier separates what it is counting):

| quantity | value |
|---|---|
| abstracts using clearly supportive language | **0.347** [0.295, 0.403] (103/297) |
| abstracts stating an explicit null | 0.030 (9/297) |
| **classifier abstained** | **0.623** (185/297) |
| positive among those it could call either way | **0.920** (103/112) |
| this register's true-positive rate | 0.320 |

**Two defensible readings, and they differ by a factor of nearly three:**

- Against *all* sampled abstracts: 0.347 / 0.320 = **1.08×** — essentially no overstatement.
- Against abstracts the classifier could call: 0.920 / 0.320 = **2.87×** — close to E330's 3.17×, but
  arrived at from a measurement rather than an assumption.

**The honest report is both, with the abstention rate attached.** The 62 % abstention is the crux: those
abstracts are neither clearly supportive nor explicitly null, and which way they are counted decides the
headline. **E330's "3.17×" should not be quoted without saying that its denominator is
positives-versus-explicit-nulls, not positives-versus-all-published-work.**

## T4 — **23 % of successors reverse their parent.**

Among 188 resolvable parent/successor pairs: **138 (0.734 [0.667, 0.792]) differ in class**, and
**43 (0.229 [0.174, 0.294]) REVERSE** — positive↔negative. Nearly a quarter of the time, a design built
to check a previous result overturns its direction. That is an internal reproducibility figure with an
exact denominator, and it is the single most direct evidence in this repo that the successors are doing
real work rather than confirming their parents.

## T2 — gate type barely matters. **Spread 0.072, intervals overlapping.**

| gate type | carried by | gate_failed | rate |
|---|---|---|---|
| CAPABILITY | 70 | 22 | 0.314 [0.218, 0.430] |
| PLACEBO | 47 | 13 | 0.277 [0.169, 0.418] |
| SUPPORT | 157 | 42 | 0.268 [0.204, 0.342] |
| ALIVENESS | 86 | 23 | 0.267 [0.185, 0.369] |
| QUALITY | 15 | 4 | 0.267 [0.109, 0.520] |
| OTHER | 186 | 45 | 0.242 [0.186, 0.308] |

No type stands out. Capability gates are nominally highest, and the registration already forbids the
causal reading: a design carrying a capability gate is a *different design* from one that does not.
**Association, not attribution**, as registered.

## T3 — **PREDICTION NOT MET, marginally, and in the direction that matters.**

Under four reasonable mappings of the 11 free-text outcomes, the machinery-failure rate moves by
**0.0123** (fine, under the 0.02 bar) but the true-positive rate moves by **0.0267** (over it): 0.293 to
0.320 depending on how free text is handled. **So the positive rate carries ±0.013 of pure bookkeeping
uncertainty on top of its sampling interval**, and any quotation of "0.320" should be "0.29–0.32". Small,
but it fails the registered bar and is reported as failing it.

## T5 — the data source does **not** predict machinery failure. Observed spread 0.150, permutation null 95th 0.377, **p = 0.8980**.

VitalDB is nominally worst (0.306, n = 72) and ds004541-family best (0.158, n = 19), but the spread is
well inside what label permutation produces. No actionable guidance about which deposits cost designs.

## T7 — **NOT RUN, and that is the correct outcome.** 214 of 225 rows name a placebo; 11 do not.

The registration put the rule-32 variance check *before* the contrast and set a floor of 25 rows per arm.
The smaller arm has 11. Running the comparison anyway would be exactly the mistake rule 32 was paid for —
a contrast between two cohorts rather than two conditions.

## T8 — the pipeline agrees with itself.

```
E344/T1 row level          0.240  [0.187, 0.298]   225 registrations
E347/T7 prospective        0.269  [0.137, 0.461]   26 pre-committed tests
E347/T5 external matched   0.274  [0.269, 0.278]   CTG academic, n <= 20
E346/T8 lineage level      0.081  [0.028, 0.213]   37 lineages, majority vote
```

**The three that share an estimand — all "per design" — share a common point.** The lineage estimate sits
apart, which is expected and was stated in advance: it counts *questions*, not designs.

## T9 — what a multi-lab study needs. **600 registrations per lab.**

Under the registered decision rule (non-overlapping 95 % Wilson intervals between two labs, base rate
0.24): **600 per lab** for 80 % power to detect a 0.10 difference; **more than 1,200 per lab** for a 0.05
difference.

*Unregistered note, labelled as such*: non-overlapping 95 % intervals is markedly stricter than a standard
two-proportion test (roughly p < 0.005), so the registered figure is an **upper bound** on what a study
actually needs. `PILOT_PROTOCOL_MULTISITE_REGISTER.md` currently states no sample size and should carry
this one.

## T10 — **this repo contains ONE auditable register, not two.**

The burst-suppression programme references **419** results, of which **125** have a structured ledger
entry, across **156** analysis scripts of which **4** write a machine-readable artifact — coverage
**0.032**.

E347/T1's audit needs a verdict-bearing artifact per result, and this programme has essentially none; its
ledger is prose, which E343, E344/T2 and E346/T7 established across three independent tests is not
machine-auditable. **Registered as a feasibility measurement rather than an attempt**, because repeating
a method already shown to fail three times is exactly the failure rule 101 exists to prevent.

---

## What E348 does to the paper

**Supplies the argument for the format (T1).** Six of seven refused designs had already printed something
that would have been written up. That is the sentence the paper needed and did not have.

**Forces one correction and one qualification.** The "3.17× overstatement" is denominator-dependent and
ranges from 1.08× to 2.87× depending on how 62 % of abstracts are counted (T6); and the true-positive
rate carries ±0.013 of bookkeeping uncertainty (T3).

**Adds an internal reproducibility number with an exact denominator**: 23 % of successors reverse their
parent (T4).

**Closes three lines cleanly rather than forcing them**: gate type does not matter (T2), deposit does not
matter (T5), and the placebo contrast is refused on its own variance check (T7).

**Parameterises the pilot**: 600 registrations per lab, as an upper bound (T9).
