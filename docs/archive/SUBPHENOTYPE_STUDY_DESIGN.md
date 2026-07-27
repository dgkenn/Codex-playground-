# Study design — cross-nationally reproducible sepsis subphenotypes with instrument-anchored treatment response

## The novelty (why this isn't just another Seymour/Calfee)
The subphenotype space is crowded, so the design earns novelty on **three** axes a typical paper lacks:
1. **Three-country external reproducibility** — derive in MIMIC (US academic), reproduce in **eICU (US, 208
   hospitals)** and **SICdb (Austria)**. Most subphenotype papers are single/few-database and never test
   cross-national transportability; if the same phenotypes reproduce across three health systems, that is the
   strongest possible validity argument and the core differentiator.
2. **Early-TRAJECTORY features, not a static admission snapshot** — Seymour clustered baseline values; we add
   first-24h **dynamics** (slopes, variability, treatment response) that static clustering discards. Trajectory
   phenotyping is less crowded and more mechanistically meaningful.
3. **Instrument-anchored differential treatment response** — the standard criticism of subphenotype
   treatment-response claims is that they are confounded observational interactions. For the ONE treatment where
   we have a validated causal instrument (**cross-method Hb transfusion IV**), we test whether the *causal*
   effect differs by phenotype (causal HTE), not just a confounded interaction. This is unique and directly
   answers the usual reviewer objection.

## Population (Sepsis-3, pre-specified)
Adults, first ICU stay, meeting **Sepsis-3**: suspected infection (antibiotics + cultures/culture-order within
±24–48h) **AND** organ dysfunction (SOFA ≥ 2 from baseline in the first 24h). Same definition operationalized
per database. Exclude: comfort-care within 24h, ICU LOS < 24h (need a 24h trajectory), age < 18.

## Features (first 24h, routinely collected — level AND trajectory)
- Labs: WBC, lactate, creatinine, bilirubin, platelets, hemoglobin, sodium, potassium, bicarbonate, BUN, glucose.
- Vitals: heart rate, MAP, SpO2, respiratory rate, temperature.
- For each: **level** (median first 24h) + **trajectory** (slope over 24h, coefficient of variation). Standardize
  within-site (z-score) so clustering is scale-free and site-comparable.

## Method (pre-specified, honest about k)
1. **Derivation (MIMIC):** consensus clustering — k-means over bootstrap resamples (also GMM as sensitivity);
   evaluate k = 2…6 by **consensus stability (bootstrap ARI)**, silhouette, and clinical interpretability.
   Pre-specify the primary k as the most **stable** solution, not the one with the best outcome separation
   (avoids outcome-peeking).
2. **Internal validation:** bootstrap cluster stability (ARI distribution); feature profiles per phenotype.
3. **External reproduction (eICU, SICdb):** freeze the MIMIC cluster centroids + scaler; assign each external
   patient to the nearest centroid; test whether (a) feature profiles per phenotype match MIMIC, and (b)
   **outcome separation (mortality) reproduces** in each country. Reproduction across all three = the headline.
4. **Prognosis:** in-hospital + 30-day mortality, AKI, ventilator-free days — distinct across phenotypes,
   reproducibly per site (forest plots by site).
5. **Differential treatment response:** phenotype × treatment (fluids volume, RBC transfusion, vasopressors,
   corticosteroids) on mortality (adjusted). For **transfusion**, additionally the **cross-method Hb instrument**
   per phenotype → causal HTE (does transfusion help/hurt differently by phenotype?). Report interaction p +
   per-phenotype estimates; treat non-transfusion interactions as hypothesis-generating (confounded).

## Guards against the crowded-space / over-claiming traps
- **Pre-specify primary k by stability**, report the full k-sweep; do not tune k to outcomes.
- **Reproduction is the claim**, not derivation — a phenotype that doesn't transport to eICU+SICdb is reported as
  non-reproducible (negative), not buried.
- **Treatment-response causality:** only the transfusion arm is instrument-anchored; everything else is labeled
  confounded/hypothesis-generating.
- Report ARI stability, silhouette, and per-site outcome separation with CIs; no single-number cluster claims.

## Phasing
- **Phase 1 (now, MIMIC):** Sepsis-3 cohort + first-24h level+trajectory feature matrix + consensus clustering +
  internal stability + phenotype profiles + prognosis. Deliverable: the derived phenotypes with a stability-
  chosen k.
- **Phase 2 (eICU + SICdb):** freeze centroids, assign, test reproduction of profiles + mortality separation.
- **Phase 3:** differential treatment response incl. instrument-anchored transfusion HTE.

## Impact ceiling (honest)
If the phenotypes reproduce across three countries AND show differential (ideally instrument-anchored)
transfusion response, this is a JAMA/Lancet-Respiratory-tier contribution — a *transportable, causally-anchored*
sepsis phenotyping, which the field lacks. If they don't reproduce cross-nationally, that is itself a valuable
(publishable) cautionary result on subphenotype transportability. Either way the design is falsifiable and honest.
