# Cycle-11 — Second Measurement-Bias Batch (novel-angle ideas)

Ten measurement/definitional-bias ideas deliberately skewed toward *novel angles* (propagation,
meta-detectors, specificity controls, threshold complements, decision endpoints) rather than
"is analyte X biased" — per the cycle-10 lesson that single-analyte mining mostly reproduces
known/null results. Each ran its own PubMed novelty pre-screen + the guardrails; the two strongest
wins went through the hostile red-team.

**Net after red-team: 1 solid new win (false hypercalcemia) + 1 negative control (bicarbonate),
both hardening the calcium/electrolyte flagship; 1 demoted-to-principle (osmolar gap); 7
confirmatory/null.** The red-teams earned their keep — catching that the osmolar-gap "win" was the
sodium finding statistically rescaled, and scoping the false-hypercalcemia win correctly.

## Scorecard

| # | Idea | Verdict |
|---|------|---------|
| 5 | **False hypercalcemia (corrected-Ca)** | **WIN** — survives red-team; scoped to hypoalbuminemic ICU subgroup |
| 3 | **Bicarbonate specificity control** | **WIN** — well-powered negative control (bias is Na/Cl-specific) |
| 1 | Osmolar-gap propagation | **Demoted** — valid principle, but a statistical corollary of sodium; flag underpowered |
| 4 | Paraprotein-extreme pseudohyponatremia | Confirmatory (known mechanism; clean EHR dose-response) |
| 6 | Occult hypoxemia (clean arterial SaO₂) | Confirmatory (replicates Sjoding OR 2.45) + validated the clean 220227 source |
| 9 | TSH age/race reference | Confirmatory (Surks already published age+race) |
| 2 | Low anion gap as self-flag | **Null** (AG doesn't track globulin in a general cohort) |
| 7 | Sex-specific troponin | **Null/dataset-limited** (conventional cTnT can't resolve the hs window) |
| 8 | Ferritin × inflammation | **Null** on subgroup (no iron gold standard; race gap NS) |
| 10 | ETCO₂–PaCO₂ gradient | Confirmatory (dead-space physiology; no subgroup signal) |

---

## Idea 5 (WIN) — False hypercalcemia from corrected calcium: the upper-threshold complement to the flagship

The calcium flagship (doc 01) showed corrected calcium **masks hypocalcemia** in Black patients. This
is the symmetric complement at the **upper** threshold: the same albumin-correction formula **over-flags
hypercalcemia**.

**Cohort.** 103,655 ionized+total(+albumin) pairs within ±1h; 14,933 Black / 88,722 White.

**Result.** False hypercalcemia (corrected Ca >10.5 but ionized <1.30 mmol/L): Black 13.3% vs White 8.0%,
**cluster-robust OR 1.77 (z=4.66)**. At a matched true-ionized band [1.20,1.30): corrected>10.5 crossings
Black 32.9% vs White 20.0% (z=5.71); raw total>10.5 Black 7.0% vs White 4.4% (z=5.47).

**Red-team verdict: SURVIVES, with two scope corrections.**
- **Robust:** OR flat 1.73–1.77 across ionized ceilings 1.30/1.32/1.35; not RTM/circularity (there is a
  *genuine* +0.216 mg/dL higher raw total Ca in Black patients at matched true ionized calcium, with equal
  SD — a mean shift, not differential noise); **not a hypoalbuminemia-composition confound** (albumin
  distributions nearly identical by race; correction magnitude race-neutral within every albumin stratum —
  the formula doesn't discriminate, it *amplifies* the pre-existing raw-total gap).
- **Scope 1:** the amplification is proven in the hypoalbuminemic 84% of the cohort (OR 1.82, z=4.59) but
  underpowered in normoalbuminemic patients (OR 1.43, z=1.39, n=424 Black) — claim it for the hypoalbuminemic
  ICU subgroup.
- **Scope 2:** it is a **measurement-classification disparity, not demonstrated harm** — no PTH/imaging
  order data; differential workup is untested. Lead with the matched-band crossing rates (32.9% vs 20.0%),
  treat "~75% artifactual" as a corroborating summary.
- Selection caveat: only ~6% of Black vs ~10% of White admissions get a paired ionized draw.

**Net:** the corrected-Ca-fails-by-race flagship now has **both** threshold complements — masked
hypocalcemia (lower) and false hypercalcemia (upper) — same formula, same globulin mechanism, opposite
clinical error.

## Idea 3 (WIN) — Bicarbonate specificity control

Prediction (negative control): chem-vs-blood-gas **bicarbonate** shows no racial discordance, because it
isn't a protein-displaced indirect-ISE analyte. **Confirmed:** HCO₃ Black−White differential β=−0.16
(z=−1.32, NS, n=3,129); the 95% CI [−0.40, +0.08] **excludes** the sodium (−1.08) and chloride (−1.28)
effect sizes — a *well-powered* null, not underpowered. HCO₃ discordance doesn't track protein (z=0.28)
while sodium's does (z=−7.2). This rules out the "generic — all electrolytes read low in Black patients"
alternative: the bias is **specific to indirect-ISE plasma-water-displaced analytes (Na, Cl)**, as the
mechanism predicts. Strengthens the flagship's mechanistic specificity.

## Idea 1 (DEMOTED to a principle) — Osmolar-gap propagation

The algebra is exact and correct: the chem-vs-bg sodium bias propagates ×−2 into the calculated osmolar
gap (osmgap = measured − [2·Na + glu/18 + BUN/2.8]) and, unlike the anion gap, does **not** cancel (Na has
no co-biased partner subtracted from it). This is a valid, teachable **principle: whether a measurement
bias harms a subgroup depends on formula structure — single-entry (osmolar gap → propagates) vs
co-biased-difference (anion gap → cancels).**

**But the red-team correctly demoted it as a *finding*:** Test 1's z=2.77 is an **exact −2× rescaling of the
already-established sodium-bias regression** (identical z to six decimals) — zero incremental statistical
evidence. The only genuinely new content (the osmolar-gap>10 flag disparity) is **not established under
disciplined timing**: null at the pre-registered ±1h and at metabolically-tight ±6h (glu/BUN pinned),
significant only at a ±24h sodium window that reintroduces fluid-shift confounds. Plus Black patients are
ordered for osmolality ~21% less often (a separate disparity). **Status:** the propagates-vs-cancels
principle is retained (it pairs with the anion-gap cancellation, doc 09); the clinical flag disparity is a
mechanistically-plausible but underpowered hypothesis, not a finding.

## Confirmatory / null (kept so they aren't re-chased)

- **Occult hypoxemia (idea 6):** the cycle-9 data-quality block is closed — the clean chartevents 220227
  arterial SaO₂ (p25=94, truly arterial) confirms occult hypoxemia ~2.4× in Black patients (OR 2.45
  [1.68–3.57]) with only ~1 pp SpO₂ over-read, **refuting the +13–17 pp artifact** from the venous-mixed
  labevents 50817. Replicates Sjoding (known). The novel escalation-decision endpoint is **non-testable
  here** — 53% of SaO₂<88 arterial draws are already on invasive ventilation (no escalation headroom).
- **Paraprotein pseudohyponatremia (idea 4):** known mechanism; clean EHR dose-response (−0.96 mEq/L per
  g/dL protein, z=−8.3) turning strongly negative at the myeloma extreme; racial false-hyponatremia ~2× —
  but the extreme tail/racial cells are small. Confirmatory quantification.
- **TSH (idea 9):** replicates Surks age+race reference shift; sick-cohort contaminated. Confirmatory.
- **Low-AG self-flag (idea 2): null** — AG doesn't track globulin in a general cohort (z=−0.3; lactate/renal
  anions swamp it); low AG is *less* common in Black patients (disparity reversed).
- **Troponin (idea 7): null/dataset-limited** — MIMIC's conventional cTnT can't resolve the hs sex window;
  the raw female MI-underdiagnosis gap vanishes after adjusting for troponin level+age (OR 0.98, NS).
- **Ferritin (idea 8): null** subgroup (no iron/TSat gold standard; race CRP gap NS).
- **ETCO₂ (idea 10):** confirmatory dead-space physiology (masked hypercapnia 16.4%, lung-dz OR 3.5); no
  race/sex signal.

## Lessons (also in `../LESSONS.md`)

1. **An exact algebraic rescaling of an existing finding carries ZERO incremental statistical evidence** —
   the osmolar-gap propagation z was identical to the sodium-bias z to six decimals. Red-team check: compute
   the underlying regression alongside the "new" one; if the z-stats match, the new test is a corollary, not
   a confirmation. New content can only live where the *distribution shape* matters (e.g. threshold crossings).
2. **Widening a pairing window changes the COHORT, not just timing** — even when a formula term cancels
   algebraically row-by-row (glu/BUN in the osmolar gap), loosening its window shifts *which patients enter*,
   and that composition effect can manufacture significance. Re-test with each input pinned to its tight window.
3. **Negative controls sharpen mechanism:** the bicarbonate null (CI excludes the Na/Cl effect) rules out a
   generic explanation and localizes the bias to indirect-ISE displaced analytes — as valuable as a positive.
4. **Threshold biases come in symmetric pairs:** a formula that miscalibrates by subgroup will over-flag at
   one threshold and mask at the other (corrected-Ca: false hypercalcemia + masked hypocalcemia). Test both.
