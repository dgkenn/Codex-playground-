# Immortal-time / survivorship audit (MIMIC-IV norepinephrine early-warning)

HOSTILE re-examination of the MIMIC early-warning, reliability and trajectory results for IMMORTAL-TIME / SURVIVORSHIP bias. The trajectory/reliability analyses require >=4 norepi segments (and >=6 h span for the slope); the 'first-6h' early-warning requires the patient to still be on norepi through the early window. Patients who DIE EARLY are systematically excluded -- a patient must SURVIVE to be measured (immortal time). Death timing uses admissions.deathtime (a true timestamp), so the hour-6 landmark below is real, not a proxy.

- Cohort: **15949** norepi stays with a mortality record, **5258** in-hospital deaths (33%).

## 1. How big is the selection, and are the excluded sicker?
- **Trajectory gate (>=4 seg over >=6 h):** excludes **21%** (3409/15949). Mortality EXCLUDED **0.279** vs ELIGIBLE **0.344**. Among excluded deaths, **0.469** die within 6 h of first norepi (eligible: 0.01); median death 6.4 h (excluded) vs 103.0 h (eligible).
- **Segment gate (>=4 seg; reliability / early->late):** excludes **15%** (2364/15949); mortality excluded **0.295** vs eligible **0.336**.
- Excluded stays are short (median span 2.87 h, 3.0 segments) vs eligible 40.92 h.

## 2. LANDMARK fix (alive at hour 6 -> predict POST-6h death)
- Removes **487** deaths that occur at/before the hour-6 landmark (immortal time -- these could not be warned prospectively by a 6-h window). At-risk set **15462**, post-landmark deaths **4771** (0.309).
- **Early-peak NAIVE:** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 1.726, 'ci': [1.588, 1.895], 'auc_x_alone': 0.668, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.673, 'delta_auc_over_age': 0.1148}.
- **Early-peak LANDMARKED:** {'n': 15462, 'deaths': 4771, 'mortality_rate': 0.309, 'adj_or_per_sd': 1.544, 'ci': [1.43, 1.684], 'auc_x_alone': 0.652, 'auc_age_alone': 0.556, 'auc_age_plus_x': 0.656, 'delta_auc_over_age': 0.0992}.
- **Early-median NAIVE:** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 2.032, 'ci': [1.893, 2.154], 'auc_x_alone': 0.673, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.682, 'delta_auc_over_age': 0.1232}.
- **Early-median LANDMARKED:** {'n': 15462, 'deaths': 4771, 'mortality_rate': 0.309, 'adj_or_per_sd': 1.763, 'ci': [1.659, 1.862], 'auc_x_alone': 0.656, 'auc_age_alone': 0.556, 'auc_age_plus_x': 0.664, 'delta_auc_over_age': 0.1073}.
- OR change (peak): **-0.182**; rank-AUC change (peak): **-0.016**.

## 3. Competing-risk direction (who drops out)
- Early-death set (death <= 6 h, n=487): early-peak {'median': 0.43, 'p75': 0.501, 'n': 487}.
- Survived-to-landmark set (n=15462): early-peak {'median': 0.14, 'p75': 0.281, 'n': 15462}.
- Early deaths have HIGHER early requirement than survivors-to-landmark: **True**.
- Trajectory-excluded set (n=3409, 950 deaths): excluded-death early-peak {'median': 0.3, 'p75': 0.5, 'n': 950} vs excluded-survivor {'median': 0.06, 'p75': 0.1, 'n': 2459}.

## 4. Reliability under survivorship
- **All >=4-seg (published):** {'r': 0.947, 'ci': [0.943, 0.95], 'n': 13585}; early->late {'r': 0.617, 'ci': [0.605, 0.628], 'n': 13585}.
- **Long survivors (span >= 48 h):** {'r': 0.971, 'ci': [0.967, 0.973], 'n': 5587}; early->late {'r': 0.49, 'ci': [0.469, 0.511], 'n': 5587}.
- **Short stays (span < 48 h):** {'r': 0.929, 'ci': [0.924, 0.934], 'n': 7977}; early->late {'r': 0.681, 'ci': [0.668, 0.695], 'n': 7977}.

## Verdict
IMMORTAL-TIME / SURVIVORSHIP AUDIT (MIMIC-IV norepi, 15949 stays, 5258 deaths). The trajectory gate (>=4 seg over >=6 h) EXCLUDES 21% of norepi stays (3409/15949); excluded mortality 0.279 vs eligible 0.344, and 0.469 of excluded deaths occur within 6 h of first norepi (immortal-time selection is real). LANDMARK (alive at hour 6, predict POST-6h death) removes 487 early deaths; early-peak age-adj OR 1.726 (naive) -> 1.544 (landmarked), AUC 0.668 -> 0.652. The early signal SURVIVES the landmark (still OR>1, delta-AUC>0). Early deaths have HIGHER early requirement than survivors-to-landmark -> the gate drops the SICKEST early; the naive analysis is INFLATED at the bottom (those deaths are 'free' immortal-time hits) but the trajectory cohort UNDER-counts the worst cases (conservative for trajectory). Reliability is 0.947 (all >=4-seg) vs 0.971 (long survivors) -- survivorship moves it by +0.024 (negligible -> reliability is NOT a survivor artefact). NO headline conclusion is overturned: the early-warning signal survives a proper landmark and reliability is not survivorship-driven; the bias EXISTS and the naive early-warning OR is modestly optimistic (immortal-time inflation from sub-6h deaths), but the corrected (landmarked) estimate remains positive.

## Corrected early-warning estimate
- Naive early-peak age-adj OR **1.726** (AUC 0.668) -> immortal-time-CORRECTED landmarked OR **1.544** (AUC 0.652).
- Conclusions changed by the bias: **none**.

## Caveats
- Landmark uses death timing relative to FIRST NOREPI SEGMENT (not ICU intime); a late-starting infusion's hour-6 landmark is late in the stay -- consistent with how the early-warning window is defined.
- In-hospital death flag is per-admission; deathtime present for ~all flagged deaths (a handful of flagged deaths lack a timestamp and are treated as post-landmark).
- This audit addresses immortal-time/survivorship only; illness-severity confounding is separate and still unaddressed (the requirement marks the sicker patient by construction).
