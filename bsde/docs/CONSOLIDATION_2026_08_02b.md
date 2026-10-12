# Consolidation, 2026-08-02 (second) — E212 to E222

*Eleven registered results since the previous consolidation, across all four challenges. The ledger now
holds **199 registrations**: 57 positive, 51 negative, 44 gate-failed, 18 absent, 6 blocked, 6 withdrawn,
5 closed. Every number below was recomputed by Opus against the raw source before it was written here.*

---

## 1. The one substantive positive, and it is Challenge C

**E222 — two band-free measures replicate on a fourth deposit, with muscle already in the baseline.**

| candidate | over incumbent | **muscle-adjusted** | retained |
|---|---|---|---|
| `whole_head_exponent` | +0.0587 [+0.032, +0.094] | **+0.0542 [+0.030, +0.082]** | 92 % |
| `multiscale_entropy_slope` | +0.0327 [+0.010, +0.061] | **+0.0280 [+0.011, +0.049]** | 86 % |
| `relative_alpha_power` | −0.0041 | −0.0036 | absent |
| `pac_slow_alpha` | +0.0113 | +0.0095 | absent |

The incumbent on that deposit is the strongest this programme has measured anywhere (Spearman −0.8461
against a within-subject floor of 0.0922), so headroom was minimal and both cleared it regardless. Muscle
tracks the label at −0.6542 in the same direction, and the increments survive putting `emg_index` into the
baseline.

**The cross-deposit table is consistent for the first time:**

| candidate | ds005620 (E209) | capslpdb (E219) | sleep_edfx (E222) |
|---|---|---|---|
| `whole_head_exponent` | replicates | redundant with incumbent | **replicates** |
| `multiscale_entropy_slope` | replicates | not testable (cost) | **replicates** |
| `relative_alpha_power` | absent | absent | **absent** |

**The two that travel are band-free. The one that fails is the fixed-band measure.** That is the same split
Challenge A arrived at independently.

> **CORRECTED LATER THE SAME DAY (E223).** This section originally called that split *the single most reusable
> finding of this block*. It was tested as a hypothesis rather than read off as a by-product, on eight
> features of the same deposit that had never touched its label, with the family partition set by a
> synthetic sweep and the null an exhaustive enumeration of all 70 balanced partitions. **It did not
> reproduce**: D = −0.0042 at the 7.1st percentile, leaning if anything the other way. The test is
> underpowered — every increment lies between −0.005 and +0.010 because the incumbent leaves almost no
> headroom — so it settles nothing in either direction. What survives is the narrower claim: **three
> specific candidates behave this way across deposits, not a family law.**

---

## 2. Challenge A — the effect is real, the explanation is not, and the design cannot supply one

Six candidate mechanisms were tested. **Five are refuted and the sixth is unavailable.**

| mechanism | verdict | how |
|---|---|---|
| band placement (fixed 8–13 Hz window) | **refuted** | E213: restriction moved the gap −0.0310, the 18.8th percentile of a matched-size null |
| frequency sensitivity as a general property | **weak** | E214 passed at p = 0.046 and was not robust to dropping any single feature; E216's constructive version ranked 106 of 120 |
| burst suppression differing by agent | **refuted** | excluding every suppression case makes the gap LARGER, −0.4792 vs −0.3742 |
| age | **refuted** | arms matched; published age effects run the same direction in both drugs |
| dose range / co-medication | **refuted** | CV identical (0.341 vs 0.355); the effect survives matching on the overlapping remifentanil band |
| **non-equipotent depth scales** | **not explained by it** | E220: the effect survives on a published cross-agent potency scale |
| different alpha generators | **untestable** | no public deposit has ≥16 channels AND a documented multi-agent contrast |

### What is identified, and what is not

**E220's post-hoc correction is the most important methodological result of the block.** Case-mean centring
collapses the between-agent difference from −0.0429 to −0.0045. Because every case receives exactly one
agent, that centring removes the agent MAIN EFFECT along with the between-patient differences it is
confounded with — so the centred statistic sees only an agent×potency INTERACTION, and that is null, while
the uncentred one contains the main effect but cannot separate it from patient differences.

**In an observational cohort where each patient receives one agent, the agent main effect is not
identifiable.** E220's registered primary was the confounded quantity, and that should have been a gate.

What survives as identified is the **within-case** result, because a per-case correlation never crosses a
patient boundary: **alpha tracks sevoflurane dose at −0.3827 [−0.467, −0.246] and does not track propofol
dose at +0.0416 [−0.003, +0.103]**. That is the claim, and "inversion" overstates it — one arm moves and
the other does not detectably move.

**The crossover route is closed, verified rather than assumed.** VitalDB has 58 cases labelled as receiving
both agents; the median within-case span of the propofol potency share is **0.000**, and three cases
qualify at a strict dominance threshold. The label means induction propofol then maintenance volatile.

### Standing caution now recorded: BIS cannot anchor depth here

Two independent reasons. It is **not equipotent** — Kuizenga 2019 puts the index at 46.7 for propofol
against 68 for sevoflurane at matched behavioural depth while the drug concentrations are perfectly
correlated. And it is **computed from the same EEG**, so residualising a spectral feature on it partly
residualises that feature on itself. This cohort has **no clean depth anchor at all**: every candidate is
either an EEG index or a drug concentration, and suppression ratio is 0.000 throughout.

---

## 3. Challenge B — closed cleanly on the residual question

**E212 METHOD FAILS.** Its cohort is sound (540 discordant pairs; RASS discriminating within pairs at
0.8113 against a null of [0.4291, 0.5662]; read failures shown not outcome-related at p = 0.4101), but its
estimator was not: an i.i.d. noise column degraded out-of-fold concordance by −0.1377 [−0.1850, −0.0953],
indistinguishable from every real candidate. Rule 58 ended the run.

**E221 replaced adjustment with matching and returned a clean ABSENT.** On 125 pairs where RASS is
identical on both members and the patient obeyed commands at one assessment and not the other, no candidate
separates them; every two-sided permutation p ≥ 0.128. **The negative control is the informative line**: at
0.5520 it is the largest deviation from 0.5 of any column, behaving exactly as noise should where E212's
was indistinguishable from signal. Keeping the control unchanged between the two designs is what makes
that comparison possible.

**Scope, which is the honest limit:** matching discards 77 % of the discordant cohort, and the discarded
pairs are precisely those where sedation changed — where the bedside score already explains the label. This
tests the residual, which is the clinically interesting part and also the hardest.

---

## 4. Challenge D — five diagnoses for one negative, and the lesson is the gate that was missing

**E215: the reference does not transport.** Both references resolve 1 of 3 adjacent strata on capslpdb
against 2 of 3 and 3 of 3 internally. My successive explanations:

| diagnosis | outcome |
|---|---|
| montage level offset | withdrawn — underpowered against a size-matched control |
| deposit-wide level shift | refuted — wake medians match to 0.004 |
| reference lacks deep-end range | refuted — the deposit that saturates MORE resolves BETTER (98 % vs 66 %) |
| Nyquist / fit-range headroom | refuted — 512 Hz records have the LARGEST spread |
| clinical heterogeneity | partial — pooled sd 0.512 vs 0.405 within single groups |

**What stands is a measurement, not an attribution.** The between-stage gap in units of within-stage spread
is **0.378 / 1.366 / 0.460** on capslpdb against **1.794 / 1.750 / 1.869** on sleep_edfx — and capslpdb
resolves exactly the one pair whose ratio reaches 1.366. No reference can resolve strata the raw measure
does not separate.

**The missing gate:** E215 gated on coverage, alignment, saturation and the null floor, but never asked
whether the raw measure separates the strata IN THIS COHORT. With that gate it would have returned NOT
INTERPRETABLE and five diagnoses would have been unnecessary. Rule 53, in a place it had not been applied.

---

## 5. Process: four gates that could not discriminate, in eleven experiments

This block produced an unusual concentration of gate defects, all mine, and they cluster:

| experiment | defect | class |
|---|---|---|
| E216 | G4 compared a sorted tuple against combination-order keys, so it looked up a key that cannot exist | key/scoping |
| E217 | G2 was global over four deposits, refusing an arm that does not use the failing deposit | scoping (rule 71 mirrored) |
| E218 | no gate asked whether the ANCHORED measure carried depth at all; it did not, so "no inversion" meant "no signal" | missing aliveness (rule 83) |
| E222 | REM placebo flagged all four candidates: tolerance 0.35 on a range of 0.47, and its premise (EMG puts REM deep) is false because the index does not detect atonia | rule 63 + rule 57 |

**Three of the four were caught by the gate failing loudly rather than passing quietly**, which is the
discipline working. E218 is the exception and the dangerous one: it printed a confident positive verdict
that survived four passing gates, and only a post-hoc aliveness check killed it.

**The reusable rule:** for every gate, ask not only whether it can fail (rule 40) but whether the quantity
it tests can take values that would distinguish the cases. E222's REM tolerance and E216's key lookup both
fail that test arithmetically, before any data.

---

## 6. What is worth doing next, in order

1. **Extend the band-free/fixed-band split to a fifth deposit.** It is now the programme's most consistent
   finding and it has never been registered as a hypothesis in its own right — every observation of it has
   been a by-product.
2. **Challenge A needs a crossover cohort or it needs to stop.** The identified claim is within-case and
   the between-agent question is not answerable with what exists publicly.
3. **Challenge D's successor must gate on cohort separability** before comparing reference schemes.
4. **Do not build another REM placebo on `emg_index`.** Validate the artefact instrument first, or use a
   submental channel where the deposit has one.
