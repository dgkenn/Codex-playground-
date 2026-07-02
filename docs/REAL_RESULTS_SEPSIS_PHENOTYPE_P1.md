# Sepsis subphenotypes — Phase 1 (MIMIC derivation): severity-orthogonal phenotypes found

## Cohort
ICD-anchored sepsis (ICD-9 995.91/92, 785.52; ICD-10 A40/A41/R65.2), adult, first ICU stay, LOS≥24h, ≥1 organ
dysfunction in first 24h. **n=11,308** (→ 9,302 after ≥60% feature coverage; mean coverage 0.81). Features:
first-24h LEVEL (median) + TRAJECTORY (slope, CV) of 17 labs + 4 vitals + MAP. (Honest: ICD-anchored sepsis,
not full Sepsis-3 with antibiotic timing — no clean antibiotic table.)

## The key methodological finding: naive clustering = severity; residualized = real phenotypes
| clustering | primary k | stability (ARI) | what it is |
|---|---|---|---|
| all features (level+slope+cv) | 2 | 0.934 | acidotic/high-lactate/high-variability vs rest — **severity axis** (cv features also measurement-frequency-confounded) |
| **level-only** | 2 | 0.936 | renal-failure+acidosis (mort 45%) vs rest (22%) — **still a severity/AKI gradient** |
| **severity-residualized (level)** | **3** | **0.927** | **3 phenotypes at SIMILAR severity, distinct physiology — NOVEL** |

Residualizing each level feature on the severity index (1st PC of lactate/bicarbonate/pH/creatinine/BUN) before
clustering removes the trivial severity axis. A **stable k=3** structure then emerges (ARI 0.927, higher than
residualized k=2's 0.865), with clusters that are severity-orthogonal (severity-index +0.05 / +0.07 / −0.15):

- **Phenotype A — hemoconcentrated/hypoxemic** (n=2,697, mort 27.8%): Hb/Hct **+1.15**, SpO₂ −0.42.
- **Phenotype B — anemic/hyperchloremic** (n=3,827, mort 27.5%): Hb/Hct −0.48, chloride +0.46, calcium −0.43.
- **Phenotype C — renal/hypochloremic** (n=2,778, mort 34.1%): creatinine/BUN +0.5, chloride −0.74, calcium +0.52.

The dominant severity-orthogonal axis is **hemoglobin (anemic ↔ hemoconcentrated)**, plus a renal/electrolyte
axis. These are physiologic-pattern phenotypes, not a severity ladder (mortality is not monotone with the
severity index across them) — the "beyond-severity" property that made Seymour/Calfee high-impact.

## Why this matters for the study (and the novelty)
1. **Severity-orthogonal phenotypes** — the non-trivial result; most subphenotype papers that don't residualize
   just recover severity.
2. **The Hb axis sets up the instrument-anchored Phase 3** — our clean cross-method Hb transfusion IV can test
   whether transfusion helps the **anemic** phenotype but not the **hemoconcentrated** one (causal differential
   response, answering the usual "confounded interaction" criticism). This is the unique, high-impact angle.
3. All defining features (Hb, Hct, chloride, creatinine, BUN, calcium, SpO₂) are measured in eICU and SICdb →
   the phenotypes are transportable for the Phase-2 cross-national reproduction test.

## Honest caveats / guards
- k=3 is the *residualized* stable solution; report both the naive-severity k=2 and the residualized k=3, and
  be explicit that the novelty is the severity-orthogonal structure.
- CV/variability features are measurement-frequency-confounded → excluded from the residualized phenotyping.
- Residualization choice (severity index = 1st PC of lactate/acidosis/renal) is a modeling decision; sensitivity
  to the severity-index definition should be reported in the paper.
- ICD-anchored sepsis (not antibiotic-timed Sepsis-3) — a known limitation to state.

## Next
Phase 2: freeze the residualized k=3 centroids + severity-residualization params; extract the SAME features in
**eICU (208 US hospitals)** and **SICdb (Austria)**; assign patients to phenotypes; test whether (a) the
phenotype profiles reproduce and (b) mortality/organ-pattern separation holds cross-nationally. Reproduction
across three countries is the headline. Phase 3: instrument-anchored transfusion HTE across phenotypes.
