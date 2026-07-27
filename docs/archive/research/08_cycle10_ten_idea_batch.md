# Cycle 10 — Ten-Idea Measurement-Bias Batch (from the top-tier journal mine)

**Ten pre-specified measurement/definitional-bias ideas** (seeded by the NEJM/JAMA/Nature mine,
doc 07), each run in parallel on MIMIC-IV with a mandatory PubMed **novelty pre-screen first** and the
cycle-9 guardrails (never bin a difference by its own component → Bland-Altman mean; never contrast
occult-vs-overt on mortality; beware tautological checks; cluster SE). Winners went through the hostile
red-team loop. Every number below is from a real run; nulls and demotions are reported, not hidden.

## Scorecard

| # | Idea | Verdict (post red-team where applicable) |
|---|------|------------------------------------------|
| 9 | **Chloride 2-method discordance by race** | **WIN (survives red-team, tempered)** — a coordinated 4th analyte for the flagship panel |
| 7 | Hyperglycemia-corrected sodium → false-hyponatremia labeling by race | **Demoted** — real but ~84% is the known hyperglycemia disparity; ~16% residual; consequence untested |
| 5 | Corrected calcium by **sex** | **NULL — valuable specificity control** (bias is race-specific, not sex-specific → reinforces flagship) |
| 1 | QTc Bazett vs Fridericia by sex/HR | Already-known mechanism + modest formula-choice sex-disparity reversal at 450 ms |
| 3 | HbA1c–glucose by race | Already-known; confirmatory (~½ the inpatient A1c "diabetes gap" is measurement artifact) |
| 2 | Benign ethnic neutropenia (ANC/Duffy) | **NULL in ICU** — biology confirmed (baseline ANC ↓, z=−22.8) but over-labeling *reverses* (acute causes dominate; BEN is outpatient) |
| 4 | Albumin-uncorrected anion gap → HAGMA | Already-known core; **NULL subgroup** (hypoalbuminemia race/sex-invariant) |
| 6 | Co-oximetry vs CBC hemoglobin → transfusion | **NULL/confounded** — apparent sex gap is a base-rate artifact (vanishes conditioning on Hb near 7) |
| 8 | eGFR equation → renal drug-dosing | Mechanism-only/already-known; race arm arithmetically forced (tautological) |
| 10 | Bilirubin–Jaffe creatinine interference | Already-known; **NULL** (−0.017 mg/dL per SD, clinically trivial, inseparable from sarcopenia) |

**Yield: 1 genuine new finding (idea 9), 1 demoted-modest (idea 7), 8 nulls/confirmatory.** A realistic
rate for mining single-analyte biases — most are already documented, and the guardrails correctly caught
the false leads (idea 2 acuity reversal, idea 6 base-rate, idea 8 tautology) instead of letting them through.

---

## Idea 9 (WIN) — Chloride indirect-ISE vs direct-ISE discordance by race: a coordinated 4th analyte

**Claim.** Chemistry (indirect-ISE) chloride reads systematically lower than blood-gas (direct-ISE)
chloride in Black vs White patients **at matched true chloride** — the same electrolyte-exclusion /
plasma-water-displacement physics as the sodium/calcium panel (docs 01, 03) — so chemistry differentially
**under-labels hyperchloremia** in Black patients.

**Cohort.** 12,056 blood-gas↔chemistry Cl pairs (±1h), 9,832 admissions; BLACK 1,299 / WHITE 7,886.

**Result.**
- Differential discordance (chem − blood-gas), BLACK vs WHITE = **−1.31 mmol/L (z=−9.42)** unadjusted;
  −1.29 (z=−9.23) at matched Bland-Altman level; −1.38 (z=−10.31) bg-Cl-adjusted. Race is regressed as a
  covariate on the difference (RTM rule satisfied — verified by red-team).
- Hyperchloremia over-call (chem) at >106: Black 5.2% vs White 11.1% (diff −5.9%, z=−7.33).
- **Artifactual disparity:** at >106 the true (blood-gas) Black−White gap is −4.0 pts but chem reports
  −14.6 pts (**3.65× inflation**); at >110 the truth is **+3.0 pts (Black more)** but chem **sign-flips to
  −3.7 pts** (non-overlapping CIs — solid, not small-n noise).

**Red-team verdict: SURVIVES, tempered** (independent re-run + 6 attacks):
- **Arterial-venous confound disclosed but doesn't explain it.** Real care-access disparity (arterial-line
  presence 57.3% White vs 38.3% Black, z=−13.0), but splitting by confirmed arterial-line presence leaves
  the racial discordance undiminished (−1.37 art-confirmed vs −0.99 no-art-line). Compartment mixing is not
  the driver.
- **Independent of sodium (~69%).** Cl- and Na-discordance correlate only r=0.263 (R²=0.069); adjusting for
  concurrent Na-discordance shrinks the coefficient from −1.17 to **−0.81 (z=−5.65)** — so the honest
  headline is **−0.8 to −1.3 mmol/L**, and chloride is a mostly-independent 4th analyte.
- **Mechanism is a hypothesis, not established.** Total protein co-measured in only 237/12,056 pairs;
  globulin slope directionally right (−0.73/g/dL) but z=−1.64; full mediation model n=134. The
  electrolyte-exclusion attribution is plausible (matches the Na/Ca panel) but empirically unconfirmed here.
- Clinical consequence softer than Na/K/Ca (hyperchloremia rarely triggers a discrete action); generalizes
  only to the paired-labs **critical-care** cohort (ICU/ED-enriched by construction).

**Tightest claim.** *In a critically-ill MIMIC-IV subpopulation, chemistry chloride reads ~0.8–1.3 mmol/L
lower than blood-gas chloride in Black vs White patients at matched true chloride (Na-adjusted floor −0.8,
z=−5.65), inflating the apparent racial hyperchloremia gap 3–4× and reversing its sign at >110 — a plausible
but not-yet-protein-confirmed instance of the lab's indirect-ISE electrolyte-exclusion bias family.*
This extends the flagship panel (Na↓, Cl↓, Ca↑) with chloride as an independently-measured 4th analyte.

---

## Idea 7 (DEMOTED) — Hyperglycemia-corrected sodium → false-hyponatremia labeling by race

**Cohort.** 2,509,304 Na↔glucose pairs (±1h), 174,326 subjects. False hyponatremia = measured Na<135
that flips to ≥135 after glucose correction (Hillier 2.4).

**Result (naive).** 15.3% of measured-hyponatremia labels spurious overall; flip rate Black 20.3% vs White
14.1% (z=37.7); driven by higher hyperglycemia exposure (%glu>200: 10.8% vs 7.9%).

**Red-team verdict: survives but much narrower than advertised.**
- **~84% is the known hyperglycemia disparity.** Oaxaca decomposition (11 glucose bands): composition
  effect (Black's worse glucose-band mix) = 5.20 pp = **83.9%** of the 6.20 pp gap; residual within-band
  rate effect = 1.00 pp = **16.1%** (statistically real per band, z=2.35–10.98, but clinically tiny).
- Robust to clustering (subject-collapsed z=11–14) and to factor choice (holds under 1.6: z=25.7 per-draw)
  — so report the spurious-rate as a **range 9.3%–15.3%**, not the larger factor alone.
- **Framing imprecise:** this is *translocational* hyponatremia (a real osmotic water shift), not
  *pseudohyponatremia* (an assay artifact) — the measured value isn't "wrong"; the corrected value is a
  euglycemic counterfactual. Reframe "false label" → "not actionable as hypotonic hyponatremia."
- **No clinical consequence tested** — pure label quality; any mistreatment/harm claim is future work.

**Net:** a quantifiable label-quality inequity that ~5/6 tracks the known Black–White hyperglycemia gap —
**not a novel race-specific measurement bias.** Modest; not a flagship.

---

## Selected nulls & confirmatory results (kept so they aren't re-chased)

- **Idea 5 — corrected calcium by sex: NULL, and useful.** No residual sex offset at matched ionized Ca
  (+0.023 mg/dL, z=0.99); the correction *collapses* the small true sex gap rather than manufacturing one.
  This is a **specificity control**: the corrected-Ca bias is **race-specific, not sex-specific**,
  strengthening the doc-01 flagship's ancestry/globulin attribution. (SICdb sex-axis replication queued.)
- **Idea 1 — QTc Bazett vs Fridericia:** textbook mechanism; the one non-obvious result is that at the
  common 450 ms cutoff Bazett manufactures a female "prolonged QT" excess (+2.1 pp, z=8.5) that **reverses
  under Fridericia** (−1.0 pp) — switching to the rate-stable formula erases the apparent sex disparity.
  Small absolute effect; HR recovered algebraically. Documentable, not a flagship.
- **Idea 3 — HbA1c–glucose by race:** confirms published outpatient finding at inpatient scale — at matched
  glycemia Black patients cross A1c≥6.5% ~2× more often; ~½ the inpatient A1c "diabetes gap" is artifact.
  Magnitude inflated by regression dilution (noisy non-fasting glucose) — trust the sign/threshold pattern,
  not the absolute size.
- **Idea 2 — benign ethnic neutropenia: NULL in ICU (direction reverses).** Baseline ANC robustly lower in
  Black patients (z=−22.8) but neutropenia prevalence is ≤ White at every threshold and the White excess
  *grows* toward the severe end — acute pathologic neutropenia (chemo nadirs, sepsis) dominates the
  inpatient threshold. BEN over-labeling is an **outpatient** phenomenon; MIMIC is the wrong substrate.
- **Idea 4 (anion gap), 6 (hemoglobin), 8 (eGFR), 10 (bilirubin):** already-known cores; subgroup angles
  null/confounded/tautological (details in the ledger). Guardrails caught the base-rate (6) and tautology (8).

---

## Cross-batch lessons (also in `../LESSONS.md`)

1. **Most single-analyte measurement biases are already published** — the novelty pre-screen (now mandatory)
   flagged ideas 1, 3, 4, 6, 8, 10 as already-known *before* over-claiming. The wins come from a genuinely
   uncharted subgroup angle (idea 9 chloride-by-race: 0 PubMed hits) or a specificity dissociation (idea 5).
2. **"Differential misclassification by subgroup" often decomposes into a known disparity + a tiny residual.**
   Always run the Oaxaca/within-stratum decomposition (idea 7: 84% known-disparity, 16% residual) before
   calling a subgroup measurement effect novel.
3. **Cohort substrate matters:** an outpatient phenomenon (BEN over-labeling, idea 2) can *reverse* in an
   ICU cohort where acute pathology dominates the threshold. Match the cohort to the phenomenon.
4. **A rigorous NULL is a deliverable** — idea 5's sex-null is the best negative control the flagship has.
