# TOPPS (prophylactic platelets) — no assay-noise instrument exists for platelet (honest retirement)

TOPPS (Stanworth NEJM 2013): no-prophylaxis vs prophylactic platelets at count <10×10⁹/L in heme-malignancy
thrombocytopenia; primary = WHO grade≥2 bleeding within 30d. RCT truth: **non-inferiority NOT shown —
prophylaxis was PROTECTIVE** (50% vs 43% bleeding). So unlike TRICC/TRISS (null), the reflexive
transfuse-at-<10 decision genuinely reduces bleeding; a valid instrument should recover a protective effect.

## Step 1 — is there a second, contemporaneous platelet method? (needed for cross-method discordance)
Exhaustive scan of MIMIC-IV platelet-family itemids:
| itemid | label | rows | usable 2nd method? |
|---|---|---|---|
| 51265 | Platelet Count (impedance/CBC) | 4,214,048 | this IS `lab_plt.csv` — the only operational count |
| 53189 | Platelet Count (Chemistry) | **17** | no — all rows have empty hadm_id (unlinkable reference draws) |
| 51266 | Platelet Smear (manual) | 317,261 | no — valuenum empty; only free-text buckets ("LOW.", "RARE*.") |
| 51240 / 51264 | Large Platelets / Clumps | 6,157 / 329 | no — qualitative flags, not counts |
| 52142 / 52159 / 52105 | MPV / aggregation / antibodies | 0 / 0 / 0 | no — different quantity or empty |

**Conclusion:** hospital labs have essentially ONE platelet-count method (impedance). There is no CBC-vs-blood-gas
analogue for platelet, so the bulletproof cross-method discordance instrument **does not transfer**.

## Step 2 — does the temporal (single-method) fallback survive near the <10 threshold?
Repeat-draw difference statistics in the flag band (platelet 5–20×10⁹/L):

| gap bucket | n | mean(diff) | sd(diff) | implied per-draw σ |
|---|---|---|---|---|
| SHORT (<2h) | 791 | +8.99 | 33.07 | 23.4 |
| LONG (12–24h) | 26,846 | −2.83 | 13.50 | 9.5 |

Expected pure-analytic impedance σ at count ≈10 is ~1.5 (10–15% CV). Both buckets are **far** larger, and the
short bucket is *larger*, not smaller — because platelet **transfusions are given between the two draws**, and
marrow-failure kinetics move the count fast. The short-interval variance is dominated by drift + intervention,
not analytic noise — the exact failure mode that retired the temporal Hb instrument (σ=0.70 g/dL = bleeding).

## Verdict — RETIRED (no valid assay-noise instrument for platelet)
Neither cross-method (no second method) nor temporal (<2h still drift-contaminated) yields an identified
assay-noise instrument for the platelet-transfusion decision. Reporting a flag-ITT here would launder residual
drift into a precise-looking but unidentified number. A valid TOPPS emulation would need a **design-based
instrument external to the platelet count** (plausibly-exogenous provider/unit practice-variation in prophylaxis
thresholds), not a repurposed noise instrument. Logged as an honest boundary of the assay-noise family.

## Where this leaves the taxonomy
Assay-noise cross-method is clean only when two independent same-time methods measure the same physical
measurand (Hb ✓). It degrades or fails when: only one method exists (platelet ✗), the discordance carries a
non-analytic artifact correlated with acuity (potassium — hemolysis), or the flagged side isn't the acted-upon
measurement (glucose/K — fixable by direction choice). Platelet is the "single-method" failure class.
