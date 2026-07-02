# Validation ledger — favorable recoveries toward the 10+ bar (before touching the "big 10" de-implementation targets)

**Milestone (set by PI):** accumulate **≥10 FAVORABLE validations** — cases where the method recovers a known
RCT truth with all validity gates passing — before applying the toolkit to the unknown "big 10" de-implementation
questions. A *favorable* must recover the trial's actual answer (null OR non-null) with correct sign; recovering a
**non-null** truth is much stronger evidence than a null (a null is cheap — low power also lands near zero).

## Scorecard (honest)
| # | trial | analyte/instrument | RCT truth | our result | gates | **FAVORABLE?** |
|---|---|---|---|---|---|---|
| 1 | TRICC | Hb cross-method | null (restrictive non-inf) | flag-ITT≈0, all powered strata | pass | ✅ **yes** |
| 2 | TRISS | Hb cross-method (septic shock) | null | CI incl 0 but weak F | weak-instrument | ~ weak |
| — | NICE-SUGAR | glucose cross-method | harm (tight) | estimand boundary (single-flag≠target) | n/a | ✗ (not the estimand) |
| — | Potassium | K cross-method | (de-impl, unknown) | NC fires (hemolysis) | NC fail | ✗ retired |
| — | TOPPS | platelet | protective | no 2nd method; temporal drift | drift fail | ✗ retired |
| — | ALBIOS / BICAR-ICU | albumin / HCO₃ temporal | null | drift + NC fail | fail | ✗ retired |
| — | MIND-USA | nurse-preference | null | F<1 (emar charting) | relevance fail | ✗ infeasible |
| — | SUP-ICU | provider-preference PPI | null | ITT −0.13 (confounded) | balance/NC fail | ✗ confounded |
| — | PREVENT / ADRENAL / PEPTIC | gate | null | no exposure/eligibility data | — | ✗ design-only |

**Favorable count: 1 strong (TRICC) + 1 weak (TRISS) + 1 weak directional (MI/MINT sign) = ~2 / 10.** The rest
are correct *refusals* (good for the gates' credibility) but do not advance the ledger.

### Population-transfusion attempt (REAL_RESULTS_POPULATION_TRANSFUSION.md) — mostly power-limited
One clean Hb instrument, sliced by RCT population: general-ICU null recovered cleanly ✅; acute-MI protective
sign matches MINT (n.s., weak) ~; cardiac-surgery n.s. (contested truth); GI-bleed instrument invalid (drift);
hip-fracture untestable (no arterial blood-gas Hb, n=23). **Structural limit found:** cross-method Hb needs a
same-time arterial blood-gas → restricts to ICU → non-ICU/elective RCT populations are starved of power. And
chemistry lactate (53154) is absent in MIMIC (0 rows) → no lactate cross-method pair. So slicing one ICU-bound
instrument will NOT reach 10; need external ICU datasets (HiRID/SICdb) for power+sites, or a new instrument
family (dose-intensity IV, now enabled by newly-streamed vasopressor+vent data).

## Path to 10 — depth in the clean Hb instrument across the transfusion-RCT landscape
The blood-gas panel yields only Hb, Na, glucose, K as same-time cross-method pairs, and only **Hb** is clean with
a hard-outcome RCT. So breadth-across-analytes cannot reach 10. The viable route is **one clean instrument, many
population-specific transfusion RCTs**, several non-null:

| candidate | population (ICD-selectable) | known truth | value |
|---|---|---|---|
| FOCUS | hip-fracture surgery + CV risk | null | clean elective population |
| TITRe2 | cardiac surgery | null (mortality signal) | select cardiac (services CSURG/VSURG) |
| **MINT** | acute MI + anemia | **liberal favored — NON-NULL** | strongest validation (teeth) |
| REALITY | acute MI + anemia | restrictive non-inferior | MI, non-bleeding |
| Villanueva | acute upper GI bleed | **restrictive SUPERIOR — NON-NULL** | hard: instrument drift in bleeders |
| CRIT/ABC | general ICU | anemia→mortality dose-response | observational anchor |

Plus, outside Hb: Na cross-method (weak RCT truth), and provider-preference elective-stratum recoveries where an
NC-calibrated estimate matches a known trial. Realistic yield: ~4–6 additional favorables from the transfusion
landscape (incl. 1–2 non-null), getting the ledger to ~6–8; the last few need either new same-time assay pairs
(re-stream blood-gas lactate/Ca) or external replication on HiRID/SICdb.

## Rule
Do NOT open the "big 10" until the ledger reaches ≥10 favorables including **≥3 non-null recoveries** (a suite of
only-nulls is not convincing to a hostile reviewer). Every new attempt is added here, favorable or not.
