# E290–E299 — hardening the state-dependence claim. **6 of 8 testable met; two narrow it substantially.**

*2026-08-07. Predictions committed before any statistic existed. This battery exists to attack the one
result that might matter outside this repo, and two of its own items succeeded in doing so.*

---

## 1. What survived, and it survived well

**E291 — the gradient replicates in the PERI cohort at 3.5× the n, and more strongly.** Stratifying
2,503 cases by pre-landmark BIS:

| candidate | deep | mid | light |
|---|---|---|---|
| `whole_head_exponent` | **0.3649** | 0.1119 | 0.0788 |
| `critical_slowing_ar1` | **0.3298** | 0.1193 | 0.1316 |
| `alpha_peak_hz` | **0.3271** | 0.2094 | 0.2167 |

Deep ≥ light in **6 of 6**, independent of the control extraction entirely.

**E296 — the proper trend test, replacing E282's weak monotone count.** Quintiles, Spearman of leakage
against quintile index: **median ρ = −0.9000**, permutation null 5th percentile −0.6000, **p = 0.0000**.
Four of six candidates hit ρ = −1.0000 exactly. `whole_head_exponent` runs 0.489 → 0.452 → 0.417 → 0.386
→ 0.284. This is the statistic to quote; "monotone in 6 of 6" is not.

**E297 — not a cohort-size artefact.** Subsampling PERI to 250/arm, 200 times: CTRL sits above the PERI
99th percentile for all four top candidates (0.3788 vs a 99th of 0.2404).

**E298 — the gap is mostly depth, not the transition.** Matched on BIS ∈ [41.3, 52.9] (PERI 672, CTRL
250), median ratio **0.806**. Most of the maintenance/emergence difference is explained by depth. The
residual ~20 % suppression near the landmark is real but secondary.

**E294 — and it is not merely a static offset.** The *within-patient* maintenance-minus-emergence
difference identifies the agent in **16 of 18 cells** over 738 patients who appear in both cohorts. Agents
differ in how far the measure travels between depths, not only where it sits. I named the deflationary
outcome first in the registration; it did not occur.

**E293 — the effect in readable units.** `whole_head_exponent` at maintenance: sevoflurane **2.6151**,
desflurane **2.7342**, propofol **2.2532**. Volatile-minus-propofol ≈ **0.36–0.48 exponent units**,
Cliff's δ **+0.705 / +0.758**. Sevoflurane vs desflurane is −0.12, δ −0.205. Large, and concentrated where
pharmacology says it should be.

## 2. TWO ITEMS THAT NARROW THE CLAIM, AND ONE THAT COMPLICATES IT

### E299 — the gradient is carried entirely by the volatile-versus-propofol contrast

    without sevoflurane : median deep-light drop  +0.1721
    without desflurane  : median deep-light drop  +0.1825
    without propofol    : median deep-light drop  -0.0086

**Remove propofol and the depth gradient vanishes.** Prediction NOT MET.

What remains without propofol is sevoflurane vs desflurane, whose leakage is near the floor everywhere
(0.05–0.12), so this may be a floor effect rather than a biological statement — there is little signal to
grade. Either way the honest scope is narrower than what I told the investigator: **"agent identity grows
with depth" is established for a GABAergic-volatile versus propofol contrast, and is absent or
unmeasurable between two volatiles.** Any external statement must say which contrast.

### E295 — the circularity control is not clean

Stratifying by BIS risks circularity: BIS is EEG-derived, and so are the candidates. The control was to
repeat the stratification on `emg_index`, a muscle channel. Median deep-light drop: **BIS +0.1721,
muscle +0.0958.** My criterion (muscle < 0.5 × BIS) fails at 0.56×.

**A muscle stratifier produces more than half the gradient.** The benign reading is that muscle tone is
itself depth-related, so `emg_index` is a partial depth proxy and the control was never independent —
which is plausible and is exactly the kind of plausible mechanism rule 50 says stops you checking. **The
control as designed cannot separate "depth" from "any stratifier correlated with depth", and I am not
claiming it did.** What would: a non-EEG, non-physiological depth axis — end-tidal agent concentration or
effect-site propofol — which this deposit does not carry, as the programme already established.

### E292 — BIS is the exception, and it runs the other way

BIS's own leakage across depth: deep **0.0884**, mid 0.1184, light **0.1286**. Prediction NOT MET.
Every candidate's leakage rises with depth; **the incumbent's falls.** I registered in advance that this
would be a point in BIS's favour needing to be said, and it is: BIS is not merely lower-leaking at
maintenance (E273), it is the one measure here whose agent-identifiability does *not* worsen as the
patient goes deeper.

## 3. E290 — novelty is UNRESOLVED and is not being claimed

Seven candidate records (PMIDs 40638527, 40113116, 35404821, 34517477, 20051218, 15816591, 12885180) for
the broad query; **zero** for the specific phrasings. The metadata tool requires interactive approval
unavailable here, so **no record was verified from MEDLINE and no citation is made** (rules 25, 39). The
literature check is owed before any external claim. Recorded as blocked before the run and not upgraded.

## 4. The claim, restated at the precision the evidence now supports

> In frontal EEG under general anaesthesia, the identifiability of **volatile versus propofol** from
> spectral and complexity measures **increases monotonically with anaesthetic depth** (quintile trend
> ρ = −0.90, p = 0.0000; replicated in two cohorts, n = 2,503 and 726), is not explained by cohort size
> or by proximity to emergence, and is visible **within patients** across their own depth change. The
> ranking of which measures leak most transports only weakly between depths (ρ ≈ 0.3).
> **Not established:** that this extends to volatile-versus-volatile contrasts; that the depth axis is
> separable from any correlated stratifier on this deposit; that it is novel.
> **Counter-observation:** BIS itself shows the opposite gradient.

**The practical consequence, which is what would matter to anyone else:** a drug-invariance result
measured at one depth does not transfer to another, and measuring near emergence understates leakage
roughly five-fold. Any published invariance claim needs its measurement depth stated.

## 5. What a successor owes

1. **The verification E290 could not do.** Nothing external should be said first.
2. **A non-EEG depth axis.** E295's failure is not fixable inside this deposit.
3. **A second volatile-versus-intravenous contrast** to test whether E299's narrowing is a floor effect
   or a real limit — dexmedetomidine (Krause) would be the adversarial case.
4. **Explain E292.** A composite index whose drug-identifiability *falls* with depth, while all its
   apparent ingredients rise, is either a real property of the proprietary weighting or an artefact of
   BIS's compressed deep range. Both are worth knowing and the second is checkable.
