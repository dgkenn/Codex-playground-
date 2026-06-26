# VitalDB AKI — data-availability audit (labelable cohort, N = 3,924)

Coverage of every modeling-relevant variable across the **3,924 labelable cases**
(adults, non-cardiac, baseline + ≥1 postop creatinine; 143 AKI events). Percentages
are share of the cohort. This audit corrects an earlier mistake — vasoactives are
**common as boluses**, not rare; the earlier "≈1% vasoactive" figure only counted
continuous *infusion* tracks and missed bolus dosing recorded in `/cases` totals.

## Headline corrections
- **Ephedrine reaches 54% and phenylephrine 16% of the cohort** — as **boluses**
  (in `/cases` totals), invisible to the Orchestra infusion `_RATE` tracks.
- Continuous vasopressor **infusions** are genuinely rare (norepinephrine 1.4%,
  dopamine 0.4%, vasopressin 0%) — they are reserved for the sickest cases.
- So vasoactive *exposure* must be modeled from `/cases` totals (bolus + infusion),
  with the infusion tracks adding the continuous-exposure time-course on top.

## Drugs / fluids — `/cases` totals (capture bolus **and** infusion)
| Variable | % cohort with >0 | median (when given) |
|---|---|---|
| Rocuronium (`intraop_rocu`) | 97.8% | 80 mg |
| Crystalloid (`intraop_crystalloid`) | 95.7% | 850 mL |
| Urine output (`intraop_uo`) | 75.4% | 150 mL |
| Estimated blood loss (`intraop_ebl`) | 70.9% | 150 mL |
| **Ephedrine (`intraop_eph`)** | **54.1%** | 10 mg |
| Propofol (`intraop_ppf`) | 38.0% | 100 mg |
| **Phenylephrine (`intraop_phe`)** | **15.6%** | 100 µg |
| Calcium (`intraop_ca`) | 14.3% | 600 mg |
| Fentanyl (`intraop_ftn`) | 13.4% | 100 µg |
| Colloid (`intraop_colloid`) | 7.2% | 500 mL |
| PRBC (`intraop_rbc`) | 5.8% | 2 u |
| FFP (`intraop_ffp`) | 1.4% | 2 u |
| Midazolam / vecuronium / epinephrine | <1% each | — |

## Continuous-infusion tracks (Orchestra `_RATE`) — % cohort present
| Infusion | % | | Infusion | % |
|---|---|---|---|---|
| Remifentanil | 82.5% | | Norepinephrine | 1.4% |
| Propofol | 56.4% | | Nitroglycerin | 0.7% |
| Phenylephrine | 2.5% | | Dopamine | 0.4% |
| | | | Epinephrine / vasopressin / dobutamine | ≤0.1% |

Note propofol: infusion track present 56% but `intraop_ppf>0` only 38% — pump
connected ≠ TIVA delivered; the bolus/infusion decomposition (total − infused)
handles this and recovers the induction bolus.

## Intraoperative physiologic signals — % cohort present
| Signal | % | | Signal | % |
|---|---|---|---|---|
| Heart rate | 100% | | NIBP mean BP | 87.8% |
| SpO₂ (pleth) | 100% | | **ART invasive mean BP** | **72.3%** |
| MAC / volatile | 99.6% | | ET sevoflurane | 59.4% |
| EtCO₂ | 99.3% | | ET desflurane | 31.2% |
| Temperature | 96.5% | | | |

Hemodynamic coverage is strong: invasive **or** non-invasive MAP available for
essentially the whole cohort (ART 72% ∪ NIBP 88%), full HR/SpO₂/EtCO₂/temperature.

## Labs (`/labs`, time-stamped; preop = before end-of-surgery anchor)
| Analyte | preop | postop | | Analyte | preop | postop |
|---|---|---|---|---|---|---|
| Na | 96.2% | 99.6% | | **CRP** | **59.6%** | 94.0% |
| Cl | 92.1% | 99.6% | | **Lactate** | **68.8%** | 22.5% |
| Hct | 90.3% | 99.6% | | HCO₃ | 69.1% | 22.5% |
| WBC | 77.1% | 99.6% | | AST/ALT | 75.3% | 99.7% |
| Hb / Plt | 77% | 99.7% | | Creatinine | 75.5% | 100% |
| K | 96.2% | 99.6% | | BUN / lab-eGFR | 75.5% | ~100% |

`crp`, `lactate`, and `cl` are **only** in `/labs` (not in `/cases`) and are
currently unused — major additions for §7A (infection/inflammation, hypoperfusion,
chloride context). `ccr` (measured creatinine clearance) is absent (0.5%).

## `/cases` preop comorbidity columns — completeness
`preop_htn`, `preop_dm`, `preop_ecg`, `preop_pft`, `dx` (diagnosis text),
`approach`, `ane_type` are **100%** populated; `asa` 98%, `position` 98%,
`preop_cr/alb/hb` 94%. These support derived flags (CKD, liver, cardiac, sepsis)
and surgical descriptors (open vs laparoscopic, position, anesthetic type).

## Confirmed NOT derivable from the open API (documented §7 gaps)
Preoperative medication list — so **RAAS inhibitors (ACEi/ARB), NSAIDs,
aminoglycosides/vancomycin, and iodinated contrast** exposure cannot be derived.
Also absent: echocardiographic ejection fraction, uric acid, and reliable
ESRD/dialysis flags (proxied by baseline creatinine). These are stated as
limitations, not silently dropped.
