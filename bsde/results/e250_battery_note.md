# E250–E259 — ten-part battery on the completed VitalDB table

*2026-08-07. Predictions committed in `3daba17`'s successor before any statistic existed; results below.
**3 of 10 predictions met.** Two items turned out to be flawed by design and are reported as
uninterpretable rather than as findings — that is the useful part of the run, not an aside.*

---

## THE HEADLINE: two results that change the Challenge A position

### E251 — BIS leaks MORE agent identity than our panel's median. In all three arm pairs.

| pair | **BIS** | null₉₅ | p | median candidate |
|---|---|---|---|---|
| sevo vs des | **0.1198** | 0.0325 | 0.0000 | 0.0758 |
| sevo vs ppf | **0.0669** | 0.0251 | 0.0000 | 0.0581 |
| des vs ppf | **0.1832** | 0.0342 | 0.0000 | 0.0814 |

Aliveness gate passes first: BIS tracks the ventilation transition at **+0.3603** over 2,389 cases.

**Prediction MET, and it was signed in advance from Kuizenga 2019** — the index reads 46.7 for propofol
against 68 for sevoflurane at matched behavioural depth, and a drug-dependent offset is leakage by
definition. The commercial incumbent, the thing every candidate in this programme is measured against,
is *less* agent-invariant than the median measure in our own panel. E249's "quantified criticism of every
drug-independent estimator" now has the incumbent's own number attached.

### E250 — the leakage axis is NOT the state axis, and my prediction was wrong in the informative direction

Spearman(leakage, state tracking) across 19 candidates = **−0.1807**, against a predicted ≥ +0.40.

**A low-leakage / high-tracking corner exists and is populated:** `whole_head_exponent`,
`multiscale_entropy_slope`, `spectral_edge_95`, `emg_index`, `emg_beta_gamma_fraction`.

I predicted the two axes would be the same thing, which would have meant Challenge A is blocked on the
inventory rather than on statistics. **They dissociate.** Tracking the transition and identifying the
agent are separable properties on this deposit, and the corner names which measures to look at. This is
the most consequential thing in the battery and it is a *positive* — it says A's minimisation half is
not structurally hopeless here, which E249's leakage result on its own could have been read as implying.

---

## TWO ITEMS THAT DIED ON THEIR OWN DESIGN, AND BOTH ARE MINE

### E252 — the placebo landmark cannot discriminate, BY CONSTRUCTION. It is not a refutation of P2.

Placebo −0.3239 against real −0.3629 for `whole_head_exponent`; every candidate reproduces ~89 % of its
real value under a fake landmark. Read naively that destroys E249's G1 as a within-case time trend
(rule 64).

**It does not, and the reason is arithmetic.** The extracted table is *only* ±300 s about the landmark.
A fake landmark drawn inside that span sits within ~270 s of the real one, and the state change is
monotone across the window — so any split of it separates earlier from later. **The placebo has no
landmark-free region to draw from, because none was ever extracted.** A statistic that must fall when the
landmark is destroyed cannot fall when the landmark cannot be destroyed.

So P2's landmark-*specificity* is **untested**, not refuted. What the numbers do show is that the real
split beats a random split by only ~12 %, which is consistent with monotone drift across the window and
does not evidence anything special about offset 0. **This is E40's DOSE-I finding recurring on a new
deposit**: there is no population of windows far from a transition, so the position control cannot be
built. It is a data-shape requirement and belongs on any future extraction plan — the fix is to extract
control windows far from any landmark, which is cheap now that the fetch path exists.

### E253 — conditioning on the monitor's EMG is rule 13, and I registered it without noticing

`whole_head_exponent` retains **0.206** of its state-tracking sign consistency after adjustment; all four
measures collapse (0.057–0.235). Read naively, the state axis is muscle.

**`meta_emg` is a POST-EXPOSURE variable.** The patient starts breathing at the recovery landmark, so EMG
*is* part of the transition — it is a mediator, and conditioning on a mediator removes the true effect
along with any artefact. Rule 13, in a file that cites rule 57 two lines above. The number cannot
distinguish "the exponent was muscle all along" from "muscle is on the causal path from the transition to
the exponent", and those have opposite implications.

**What would answer it**: a muscle covariate measured *before* the transition (pre-landmark EMG as a
patient-level trait), or an artefact channel that is not itself state-dependent. Neither is in this table.

---

## THE REST

| | result | prediction |
|---|---|---|
| **E254** level vs change | level out-leaks change in **16 of 19** candidates | **MET** |
| **E255** leakage by state | only **0.28** of 18 comparisons within 30 %; pre-landmark leakage generally exceeds post | descriptive |
| **E256** state-tracking axes | PC1 = **47.6 %** of variance over 14 live candidates | NOT MET (predicted ≥ 50 %) |
| **E257** coverage gap | spread 0.0423, null₉₅ 0.0385, **p = 0.0325**; dropped cases 13,200 s vs kept 11,100 s | **MET** |
| **E258** age modification | older larger in **11 of 24**; no modification | NOT MET |
| **E259** aperiodic family | low~high **−0.2310**, whole~low **+0.7505**, whole~high **+0.2780** | NOT MET |

**E254 + E255 together are more interesting than either alone.** Leakage lives in the level rather than
the change (E254), *and* the level differs by state — pre-landmark leakage generally exceeds post-landmark
(E255, only 28 % of comparisons within 30 %). So it is not a fixed per-drug offset that any centring would
remove; it is a drug-dependent offset that is largest while the drug is still doing its work. That is
harder for an invariance method to strip out than a constant, and it is the shape a successor should
assume.

**E257 settles the exclusion this session left owed.** The coverage gap *is* arm-related (p = 0.0325,
against 0.0200 on a second seed — the verdict is stable across seeds, the p is not tightly resolved at
2,000 draws, rule 46) and it tracks anaesthesia duration exactly as predicted: dropped cases run 13,200 s
against 11,100 s kept, while age is identical at 59. Sevoflurane cases run longer, so the fixed ±300 s
grid more often runs past the record end. **Benign for the leakage contrast** — it selects on case length,
not on the candidates — but it is now measured rather than asserted.

**E259 refutes my reading of rule 90.** The aperiodic family splits by **band, not estimator**:
`whole_head_exponent` correlates +0.7505 with `exponent_low` despite using a different fit, while
`exponent_low` and `exponent_high` — same estimator — correlate **−0.2310**. The whole-head fit is
dominated by the low band, and the estimator inconsistency rule 90 documents is not visibly driving the
correlation structure. Rule 90's *defect* stands as a defect; its *exposure* on this deposit is smaller
than the audit implied.

**E256's 47.6 % is a genuine borderline and is reported as one.** Just under a threshold I set in advance,
on 14 candidates and 2,573 patients. It does not support "one arousal axis" as cleanly as this programme's
prior findings, and it does not establish multi-dimensionality either. A verdict that turns on 2.4
percentage points is not a verdict (rule 46's spirit); the honest statement is that state tracking here is
neither one axis nor obviously many.

---

## A DEFECT IN THE BATTERY'S OWN SMOKE, RECORDED RATHER THAN GLOSSED

Rule 26 says smoke-test on permuted labels. This battery's smoke permutes the **arm** label and P2's
after-label — but **E252, E253, E257 and E259 use neither**, so those four ran unblinded and their smoke
output was already their real result. Pre-registration integrity survives (predictions were committed
before the code ran, so nothing could be tuned to them), but the smoke did not do its job for 4 of 10
items. **A smoke run must permute every label each item depends on, enumerated per item, not one global
shuffle.**

## WHAT A SUCCESSOR OWES

1. **Extract control windows far from any landmark.** It unblocks E252's placebo, and it is the same
   data-shape requirement E40 identified on DOSE-I. Cheap now.
2. **Pursue the E250 corner.** `whole_head_exponent` and `multiscale_entropy_slope` track the transition
   while leaking below the median. That is the Challenge A shape, and it should be tested directly rather
   than read off a scatter of 19 points.
3. **Re-ask E253 with a pre-landmark muscle trait**, not a concurrent one.
4. **Do not re-run E251.** BIS's leakage is computed, its null is calibrated, and it is the battery's
   strongest and best-signed result.
