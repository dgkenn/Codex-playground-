# Chloride Use-Case Round — where the measurement bias matters, and where it cancels

Follow-up to the cycle-10 chloride win (doc 08): given chemistry (indirect-ISE) chloride reads
~0.8–1.3 mmol/L lower than blood-gas (direct-ISE) chloride in Black patients at matched true chloride
(electrolyte-exclusion), we asked **what novel use cases this opens** — where the bias propagates and
matters vs where it self-corrects. Four parallel investigations; two winners went through the hostile
red-team loop. A PubMed landscape scout confirmed the entire *chloride measurement-bias-by-race* space
is unpublished (0 hits) — so this is coherent white space.

## The unifying map (the round's payload)

| Clinical target | Depends on | Bias effect | Verdict |
|-----------------|-----------|-------------|---------|
| **Absolute chloride** (hyper-/hypochloremia labels, prognostic flags) | Cl alone | **Matters** — differential misclassification | masks hyperchloremia (z=−7.9); over-flags hypochloremia (z=4.2) |
| **Anion gap** (Na−Cl−HCO₃) | Na − Cl | **Largely cancels** (self-protected) | B−W AG bias +0.10 (95% CI −0.21…+0.42) |
| **Strong-ion difference / Na−Cl screen** | Na − Cl | **Cancels** | same +0.10, z=0.65 |
| **Hard renal outcome (AKI)** | — | **No proven harm** | masked-hyperchloremia adjOR(AKI)=1.03, ns |

**One-sentence message:** the panel electrolyte-exclusion bias corrupts *absolute* chloride
interpretation (hyper-/hypochloremia labeling) but is **self-protected in the most-used acid-base tools**
(anion gap, SID) because they subtract two co-biased analytes — so clinicians can keep trusting the anion
gap while treating absolute chloride and hyperchloremia flags with subgroup caution.

---

## Finding A (WIN, tempered) — Acid-base cancellation / self-protection

**Cohort.** 8,018 paired draws (chem Na, bg Na, chem Cl, bg Cl, chem HCO₃ within ±1h); BLACK 1,228 / WHITE 6,790.

**Result.** The bias is algebraically exact: AG_chem − AG_true = Na_bias − Cl_bias (HCO₃ shared, cancels).
- Absolute Cl bias (B−W): **−1.20 mmol/L, z=−8.48**; absolute Na bias: **−1.10, z=−8.76** — both survive.
- **Anion gap / SID / Na−Cl bias (B−W): +0.105, z=0.65 — cancels** (the two absolute biases are nearly
  equal, so they subtract to a null).
- Where it does NOT cancel — absolute hyperchloremia straddle (chem vs true, B−W): Cl>106 diff −6.18%
  (z=−7.90); Cl>110 −3.70% (z=−6.44). Chem under-reads Cl more in Black patients → **differentially masks
  true hyperchloremia**.

**Red-team verdict: SURVIVES, tempered** (independent re-run + verification scripts):
- **RTM correctly handled.** The true-AG-adjusted model gives a spurious z=3.93 — the exact
  difference-vs-component coupling artifact (AG_bias = AG_chem − AG_true anti-correlates with AG_true, and
  Black patients have higher true AG). The Bland-Altman-mean primary (z=−0.43) is the correctly-specified
  one. Attack defused by the analysis itself.
- **The AG>16 "caveat" is a case-mix artifact, not a bias residual.** Black patients have higher *true* AG
  (12.03 vs 9.54) → more mass near the fixed cutoff → more crossings mechanically, even under a race-neutral
  bias. Within-true-AG-level over-call rates are close (1–4 pp). Re-attributing this *removes* the strongest
  apparent counter-evidence against cancellation.
- **Underpowered null (tempering).** 95% CI on the AG-bias differential = **[−0.21, +0.42]**; MDE at 80%
  power ≈ 0.45. So the honest statement is "no residual detected; residuals up to ~0.4 mmol/L (≈⅓ of the
  absolute bias) can't be excluded," not a clean zero.
- **Cohort-specificity.** Cancellation requires Na_bias ≈ Cl_bias, which is empirical in this MIMIC/analyzer
  combination — "AG is protected" needs external replication (SICdb/eICU) before being stated generally.
- **Arterial-venous confound** unresolved but direction reassuring (venous-skewed bg draws in Black patients
  would *reinforce* the small residual, not erase it).

**Tightest claim.** *The panel bias's ~1.1–1.2 mmol/L differential in absolute Na/Cl is not statistically
detectable in the anion gap / SID / Na−Cl screen (B−W +0.10, 95% CI −0.21…+0.42) in this MIMIC cohort —
i.e. the most-used acid-base tools are largely self-protected — though residuals up to ~0.4 mmol/L can't be
excluded and external replication is needed before "AG is protected" is stated generally.*
Novel (0 PubMed hits): the classic bench lore "Na and Cl move together so AG is preserved" has never been
quantified as a *racial* cancellation with a where-it-matters-vs-cancels map.

---

## Finding B (SURVIVES at measurement level) — Prognostic misclassification (false-hypochloremia)

**Cohort.** 4,010 paired draws (1 admission/subject, ±2h); BLACK 338 / WHITE 2,424.

**Result.** Because low chloride is an established mortality/HF-diuretic-resistance marker (Grodin *Circ HF*
2016 PMID 26721916; Kataoka chloride theory PMID 31114959), the measurement bias distorts chloride-based
risk labeling:
- Bias reproduced at label level: chem−bg −1.26 (Black) vs −0.01 (White), z=−4.8.
- **False-hypochloremia (chem hypo | bg normal): Black 11.7% vs White 4.8%** — Fisher exact **p=0.00014**,
  OR 2.62, non-overlapping Wilson CIs (robust despite the small cell; already subject-deduped).
- Artifactual disparity: the apparent "Black more hypochloremic" gap (19.2% vs 12.7% by chem) **largely
  vanishes at the true value** (14.5% vs 13.4% by blood-gas).

**Red-team verdict: SURVIVES as a measurement-classification disparity; harm framing was overclaimed.**
- The false-hypochloremia gap is statistically solid, not fragile.
- BUT: the chloride→mortality association collapses from crude OR 2.77 to **OR 1.28** with even partial
  severity adjustment (log lactate + creatinine); the cohort is a sick, blood-gas-drawn ICU subgroup (76%
  ICU-touch, 12% mortality); and no chloride-based clinical-decision-support flag is in standard use. So
  "over-assigns the high-risk flag / harm" outruns the evidence.

**Tightest claim.** *In a sicker, blood-gas-drawn ICU subgroup, the routine chemistry panel mislabels Black
patients as hypochloremic (vs blood-gas truth) at ~2–3× the rate of White patients (11.7% vs 4.8%,
p=0.0001), inflating the apparent racial gap in a marker whose crude mortality association (OR 2.77) falls
to a modest, still-confounded OR 1.28 after partial severity adjustment — a documented measurement-
classification disparity, not a demonstrated point-of-care harm.*

---

## Finding C (partial / mechanism-only) — Masked hyperchloremia & AKI

Fluid-type data can't distinguish saline from balanced (design gap disclosed), so the clean signal:
**masked hyperchloremia** (true bg Cl>110 but chem reads ≤106) is more common in Black patients — WHITE
10.9% vs BLACK 14.7%, **z=3.34** (~35% relative excess) — the mirror of Finding B. But it does **not**
translate to AKI harm at matched true chloride (adjOR 1.03, z=0.3, ns; hyperchloremia→AKI itself confirmed,
chem Cl>115 adjOR 4.92). A real measurement-level under-recognition disparity without proven downstream harm.

---

## Landscape scout (white space confirmed)

PubMed: **0 hits** for chloride direct-vs-indirect-ISE bias by race. The measurement-bias-by-subgroup angle
is unmined across every chloride use case: anion gap / SID (Findings A), hyper-/hypochloremia prognosis
(Finding B; Grodin, Neyra *CCM* 2015 PMID 26154934, Kimura *J Intensive Care* 2014 PMID 25908989), fluid
trials (SMART PMID 29485925, PLUS chloride subgroup PMID 39928118 — used *chemistry* Cl to define quartiles,
a re-analysis hook), DKA resolution (Self *JAMA Netw Open* 2020 PMID 33196806), and urine chloride
(near-total EHR white space). The mechanism anchor (electrolyte-exclusion on indirect ISE) is El-Khoury/
Barkhuizen — established for Na, never done for Cl by race.

## Mechanism CONFIRMED cross-nationally (SICdb)

The chloride finding's main open gap — protein-mediation (underpowered in MIMIC, n=134) — is now closed.
**SICdb (Salzburg, Austria; 8,912 paired patients) confirms the electrolyte-exclusion mechanism for
chloride:** chem−blood-gas discordance ∼ total-protein slope **−0.552 mmol/L per g/dL (z=−18.6), strictly
monotone across protein quartiles** (−0.95 → −1.51 → −1.73 → −2.31), robust to a 10-min window (−0.495,
z=−14.1), globulin-gap consistent (−0.642). Same negative, monotone, protein-driven signature as SICdb
sodium (−0.843). **Quantitative prediction confirmed:** the Na:Cl slope ratio 0.552/0.843 = **0.65** matches
the ion concentration ratio 100/140 = **0.71** — exactly what proportional plasma-water displacement predicts
and an analyzer artifact could not manufacture. The chloride blood-gas reference (item 683) carries *no*
sensor-reliability flag (unlike sodium's 686), so chloride is *cleaner* than sodium on the reference-trust
axis. Sex axis weak/non-robust (z=−1.8 at 10-min), not claimed. This replicates a method that already
survived 4 rounds of hostile review (the sodium mechanism). Limits: single-center Austrian, one analyzer
fleet; no race (confirms the *protein mechanism*, not the racial endpoint, which stays MIMIC-specific).

## Net addition to the program

Chloride is now a **validated coordinated 4th analyte** in the indirect-ISE electrolyte-exclusion family
(Na↓, Cl↓, Ca↑) — mechanism confirmed on two continents and two analyzer fleets. This round also adds the
**clinically actionable map** of where that bias propagates: it corrupts absolute-chloride decisions but is
self-protected in the anion gap and strong-ion difference. Remaining open item: external replication of the
AG *cancellation* (SICdb/eICU) before stating it generally.
