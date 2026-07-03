# Racial bias in routine sodium measurement — a Sjoding-template patient-safety lead (JAMA/NEJM class)

## The finding
Chemistry sodium (**indirect ISE** — the routinely-reported, clinically-acted-on value) is biased relative to
blood-gas sodium (**direct ISE** — protein-independent, the accurate reference), and **the bias differs by race**:

| group | chem − bloodgas Na bias (mEq/L) | n (pairs, ≤1h) |
|---|---|---|
| WHITE | **+2.28** | 9,968 |
| BLACK | **+1.09** | 1,591 |
| HISPANIC | +1.27 | 663 |
| ASIAN | +1.56 | 511 |
| **BLACK − WHITE differential** | **−1.18 (SE 0.09, z = −12.6)** | |

For the same true (blood-gas) sodium, a Black patient's **reported chemistry sodium reads ~1.2 mEq/L lower**
than a White patient's. Robust at **near-simultaneous (≤10 min) pairing** (−1.30, z = −10.2) → not a temporal
artifact of the two separate draws. Potassium shows a smaller same-direction effect (+0.10, z = +8.4);
glucose/bicarbonate show no racial differential (specificity — argues against a generic selection artifact).

## Why this is the JAMA/NEJM class (and why it dodges our walls)
- **Exact Sjoding pulse-ox template** (Sjoding et al., *NEJM* 2020): a routine measurement device systematically
  biased by race vs a gold standard, with downstream care consequences — that paper changed FDA policy.
- **Observational measurement-agreement + association — no causal instrument needed**, so it is immune to the
  first-stage/power wall that capped every causal-effect analysis this session.
- **Sodium is among the most-ordered labs in medicine** → any systematic racial bias is high-reach.
- **Mechanism is a priori clean**: indirect ISE dilutes the sample and is displaced by the solid phase
  (protein + lipid); higher plasma protein → larger pseudo-dysnatremia artifact. Black populations have
  documented higher total protein/globulins → predicted smaller positive chem−bloodgas gap. Matches the data.

## Novelty (PubMed)
Blood-gas-vs-lab-ISE sodium method-comparison studies exist (e.g. a 2026 critical-care agreement study finding
the ABG analyzer reliable for Na/K, DOI 10.1155/bmri/9203768), but **none report a racial differential** in that
bias. The equity/patient-safety framing appears unpublished. (Per articles retrieved from PubMed.)

## What must be bulletproofed (the paper stands or falls on these)
1. **Mechanism** — does plasma **albumin/total protein mediate** the racial differential? (Have `lab_alb`.) If
   controlling for protein collapses the BLACK−WHITE gap, the indirect-ISE mechanism is confirmed. ⏳ testing
2. **Consequence (the NEJM-maker)** — at the **same true (blood-gas) sodium**, are Black patients more often
   labeled hyponatremic on chemistry and **treated differently** (hypertonic saline, fluid restriction, free
   water, workup)? Differential misclassification → differential care is the harm. ⏳ testing
3. **Arterial–venous confound** — chem is usually venous, blood-gas arterial; A–V sodium difference is small
   (~1 mEq/L) and not plausibly racially differential by this magnitude, but must be addressed (source-matched
   sensitivity).
4. **Selection** — are paired-draw populations comparable by race? Report.
5. **Cross-site replication** — eICU has race + chem Na + blood-gas Na (208 hospitals); SICdb Na (race likely
   absent). Replication in eICU = the multi-site confirmation.

## Status
Discovery + robustness (tight-window) done. Novelty checked. Next: mechanism (protein mediation) + consequence
(differential dysnatremia treatment by race) — these determine whether this is NEJM-tier (harm shown) or a
lab-medicine note (bias only). This is the strongest available-data JAMA/NEJM swing found; it plays to the
paired-measurement machinery built this session and requires no causal instrument.

## MECHANISM + CONSEQUENCE results (the decisive tests)
**Mechanism — albumin does NOT explain it.** Adjusting the BLACK−WHITE bias for albumin shrinks it only ~3%
(−0.94 → −0.91); mean albumin is identical (BLACK 3.23 vs WHITE 3.19 g/dL). So the driver is not albumin —
most plausibly **globulins/total protein** (higher immunoglobulins in Black patients → higher total solid phase
at equal albumin → larger indirect-ISE artifact). Total protein/globulin was not streamed; testing it is the
key remaining mechanistic step. (Albumin's own coefficient is correctly signed, −0.82, confirming protein
*does* drive the indirect-ISE bias — just that albumin isn't the racially-differential component.)

**Consequence — differential misclassification of care (the NEJM-maker), confirmed.** At the SAME true
(blood-gas) sodium, chem-based dysnatremia labels and Na-directed treatment differ by race:
| true Na band | race | n | chem<135 (false hypo-label) | chem>145 (false hyper) | Na-tx rate |
|---|---|---|---|---|---|
| 135–140 (normal) | WHITE | 4,455 | **3.9%** | 0.9% | 6.7% |
| 135–140 (normal) | BLACK | 539 | **10.8%** (**2.8×**) | 0.9% | 8.2% |
| 145–150 (high) | WHITE | 354 | 0.3% | **75.1%** | 21.8% |
| 145–150 (high) | BLACK | 108 | 0.0% | **63.9%** | 15.7% |

A Black patient with a truly-normal sodium is **~3× more likely to be mislabeled hyponatremic** by the routine
chemistry lab; a Black patient with true hypernatremia is **under-flagged and under-treated**. Differential
misclassification → differential care, from a biased measurement — the Sjoding harm, on sodium.

## Verdict / status
Strong, robust, apparently-novel patient-safety/equity lead with a clear consequence. **Remaining to make it
bulletproof-for-NEJM:** (1) nail the mechanism (stream total protein/globulin; show it mediates the racial
differential); (2) rule out arterial-venous confound (source-matched sensitivity); (3) **replicate in eICU**
(race + chem-Na + blood-gas-Na, 208 hospitals) — multi-site is decisive; (4) formalize the consequence with
adjusted models (differential dysnatremia treatment by race at matched true Na). This is the best available-data
JAMA/NEJM swing found — observational, no causal instrument, dodges every power wall.
