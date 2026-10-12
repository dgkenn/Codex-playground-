# Overnight candidate hunt — new top-tier (NEJM/Nature/JAMA) candidates

Autonomous overnight run. Goal: surface MORE finalized top-tier candidates beyond the calcium flagship.
Strategy: the MIMIC/eICU measurement-bias seam is tapped for new disparity wins → expand to (a) ED-observable
measurement-bias-drives-ACTION studies (MC-MED — breaks the ICU paired-design wall), (b) new non-tautological
(mechanism+reference+driver) triples in less-mined data, (c) treatment-effect heterogeneity decision rules,
externally validated. Each candidate: feasibility-gate → run → red-team → log honest verdict.

## ☀️ MORNING BRIEF (read this first)
**Bottom line: no NEW top-tier candidate emerged tonight — but the night was productive and honest.** I rigorously
tested 5 candidates; all are documented negatives, and two of them *bounded prior findings* (a real contribution).
- **C1 BEN (0.45):** exposure disparity real (Black flagged low-ANC 1.85×) but the over-workup harm is FALSIFIED —
  Black patients get LESS workup at matched ANC (appropriate BEN recognition); action confounded by presentation.
- **C2 glucose-Hct (0.40):** MIMIC #15 mechanism does NOT replicate in a modern ED (Hct-corrected glucometers) →
  **bounds #15 as older-device-specific.**
- **C3 occult hypoxemia (0.30):** feasibility kill — no arterial SaO2 reference in the ED (venous gases only).
- **C4 triage-ESI (0.25):** Black under-triaged at matched vitals, but it doesn't validate against bounce-back
  admission (falsified) + it's actively scooped.
- **C5 Friedewald LDL (new, 0.30):** clean large reclassification (21% of statin-eligible falsely 'at-goal') but
  guideline-established (Martin/Sathiyakumar) and the racial angle is weak/reversed. Confirmatory.
- **C6 testosterone/SHBG in NHANES (new, 0.30):** PubMed-screened (framing was open); over-diagnosis of
  hypogonadism in obesity is clean & dose-dependent BUT guideline-known (Bhasin 2018), threshold-fragile, weak
  equity angle. Confirmatory. **Silver lining: opened NHANES (public, no-DUA, nationally representative) as a
  validated new substrate** — pipeline works (XPT download + Vermeulen free-T).

**Pattern after 6 candidates (2 sessions):** clean *reclassification* findings all land CONFIRMATORY — the famous
subgroup-miscalibration wins (calcium-globulin, eGFR-race, Friedewald, vitamin-D-VDBP, testosterone-SHBG) are the
archetypes that *inspired* this direction and are all published/guideline-addressed. Genuinely NOVEL top-tier
CPU findings in accessible tabular data are scarce — this is now well-evidenced, not a hunch.

**What I learned (raises future success rate):** the ED "recorded-action" wall-breaker thesis largely failed —
attaching a HARM/ACTION endpoint to a disparity keeps getting confounded, reversed, or unvalidated. The calcium
flagship won because it stopped at a clean **reclassification** endpoint. C5 confirmed that reclassification
endpoints ARE clean (no confounding) — so the revised rule is: **hunt non-tautological reclassification findings
with a novel angle**, not action-harm chains. Tonight's reclassification (LDL) was clean but already-published.

**Your calcium flagship remains the one solid top-tier candidate** (and it's stronger after this session's
consolidation). **Recommended next moves (need your call):** (a) accept calcium as the deliverable and move to
submission prep; (b) point me at a genuinely new data source (a dataset not yet mined) for a fresh reclassification
hunt; or (c) the GPU-gated ECG/EEG deep-learning direction (the one avenue with clear un-mined upside). I've held
the loop at low cadence rather than grind the remaining pre-flagged-fatal candidates (C6/C7).

## Standing deliverable (context)
- **Calcium flagship** — validated, submission-adjacent (5-cohort mechanism; MIMIC+eICU racial reclassification;
  reconciled cohort N=23,449 OR 1.65; 63% of high-Ca ICU flags false; globulin-fix honestly bounded). This is the
  #1 candidate; overnight work seeks ADDITIONAL ones.

## Ranked backlog (idea-generation engine, sonnet) — predicted win-likelihoods
| rank | candidate | class | dataset | pred | fatal-flaw check |
|---|---|---|---|---|---|
| **1** | **Benign ethnic neutropenia (BEN) → ED ANC-threshold actions** | wall-breaker | MC-MED | **0.45** | none fatal; repeat-visit CBC density is the risk. Executes ledger #9f lesson (BEN reversed in ICU = wrong substrate; ED is right) |
| 2 | POC glucose-meter Hct interference → ED insulin/dextrose action | depth (won mechanism, ledger #15) | MC-MED | 0.40 | none fatal; safest bet; single-method action layer is the fresh piece |
| 3 | Occult hypoxemia → O2-flow action timing + Perf specificity control | wall-breaker | MC-MED | 0.30 | crowded (Fawzy 2022 JAMA-IM); narrow wedge = titration-timing + perfusion-index dissociation |
| 4 | ED triage-acuity (ESI) miscalibration vs bounce-back-admit ground truth | decision-threshold | MC-MED | 0.25 | active scoop risk (2025 arXiv) |
| 5 | Indirect-ISE Na/Cl exclusion → ED fluid/admit action | new triple | MC-MED | 0.15 | tautological direction + thin driver prevalence — gate-check before compute |
| 6 | Ketamine vs opioid ED analgesia HTE | treatment HTE | MC-MED+MIMIC-ED | 0.12 | confounding-by-indication (matches 3 prior decision-tool failures); needs a protocol-change instrument |
| 7 | PPG perfusion-index racial artifact | novel construct | MC-MED | 0.10 | no mechanism anchor; side-query only |

## Candidate ledger (this run — verdicts as they complete)
| # | Candidate | Feasibility | Verdict | Status |
|---|---|---|---|---|
| C1 | BEN → ED ANC actions (MC-MED, 97,058 ANC / 92,908 visits) | strong (real data) | **STRIKE-OUT on top-tier harm.** BEN signature CONFIRMED (Black ANC left-shifted, median 4540 vs White 5330, concentrated in MILD range; %<1500 3.2% vs 2.1% but %<1000 LOWER 0.9% vs 1.2%). Exposure disparity REAL (Black low-ANC flag 3.1% vs 1.7%, **ratio 1.85**, non-overlapping CIs). **BUT the over-workup harm hypothesis is FALSIFIED in the predicted direction:** at matched low ANC, Black patients get LESS reactive workup (repeat-CBC-after-ANC 9.8% vs 21.5%, isolation 41% vs 50%, culture 50% vs 63%) and lower admission (11.8% vs 19.1%) — most parsimoniously appropriate BEN recognition; action layer also confounded by septic presentation. Predicted 0.45 → actual: confirmatory exposure disparity, no top-tier harm | **DONE — NOT a candidate (exposure disparity real but textbook; harm falsified/reversed)** |
| C2 | POC glucose Hct → ED insulin action (MC-MED, N=1,345 paired POC-meter/lab glucose+Hct) | mechanism substrate present | **STRIKE-OUT — mechanism does NOT replicate.** Hct slope +0.19 mg/dL/%Hct (z=0.9 NS, WRONG sign) vs MIMIC #15 −0.449; POC-lab diff SD 76 mg/dL (noisy). Cause: MC-MED 2020-2022 → modern Hct-corrected glucometers (StatStrip-class) engineer out the interference (pre-registered risk realized) + noisy 30-min pairing. **Bounds MIMIC #15 as device/era-specific.** No mechanism → no action | **DONE — NOT a candidate; tempers #15 (older-device artifact)** |
| C3 | Occult hypoxemia → ED O2 action timing | **FEASIBILITY KILL** | MC-MED has only VENOUS O2 saturation ("POCT Venous Blood Gases," values 59–79%), NOT arterial SaO2 (co-oximetry) — occult hypoxemia's required ground-truth reference is absent (EDs draw venous, not arterial, gases; pre-registered risk realized). Untestable | **DONE — killed at gate (no arterial reference); cheap** |
| C4 | Triage-acuity (ESI) miscalibration vs bounce-back-admit (MC-MED, N=107,722) | strong (visits.csv only) | **STRIKE-OUT — harm chain falsified.** Black patients ARE under-triaged at matched vitals (residual +0.19 vs White +0.095 — real assignment disparity), BUT under-triage does NOT predict the bounce-back-admit outcome (under-triaged bounce back LESS: 1.44% vs over-triaged 2.03%; Black bounce-admit 1.58% [1.25,2.00] vs White 2.06% [1.89,2.25]). Vitals-residual is a poor proxy for harmful under-triage; hard outcome doesn't validate it; raw disparity is crowded/scooped (2025 arXiv) | **DONE — NOT a candidate (disparity real but harm unvalidated + scooped)** |

| C5 | Friedewald calculated LDL vs measured direct LDL → statin-threshold reclassification (MIMIC, N=10,455 paired) | strong (9,465+ both) | **CLEAN but CONFIRMATORY (novelty-capped).** Mechanism strong: Friedewald error −11 mg/dL, monotone in TG (−8 at TG<150 → −26 at TG300-600). Large reclassification: 21.6% of true-LDL≥100 falsely 'at-goal' (30% at ≥130). BUT (1) racial angle weak/REVERSED (Black lowest 16.7%, Hispanic highest — TG-driven, no clean equity gradient); (2) mechanism + fix are GUIDELINE-ESTABLISHED (Martin-Hopkins 2013; Sathiyakumar 2018 Circulation already showed this reclassification). Not top-tier | **DONE — confirmatory; VALIDATES the revised rule (first clean non-confounded endpoint of the night) but already published** |

| C6 | Total-T vs Vermeulen free-T reclassification of hypogonadism by SHBG/obesity (**NHANES** G+H+I, N=4,592 men) | strong (new public substrate opened) | **CLEAN DIRECTION but CONFIRMATORY + threshold-fragile.** Over-diagnosis (low total-T, normal free-T) rises monotonically with BMI (0.8%→4.9%) as SHBG falls (47→32) — real, dose-dependent. BUT (1) mechanism is GUIDELINE-established (Bhasin/Endocrine Soc 2018: measure free T in obesity); (2) reclassification MAGNITUDE is implementation/cutoff-fragile (Vermeulen free-T ~15-20% low → over-dx swung 2.8%→0.2% on cutoff change; free-T<70 flags implausible 54%); (3) racial angle WEAK (no clean differential; White highest 'missed'). PubMed: the 1 NHANES-testosterone paper (Tienforti 2025) is a different question → framing was open, but lands confirmatory | **DONE — confirmatory + fragile, not top-tier. WIN: NHANES opened as a validated public (no-DUA) substrate for future reclassification hunts** |

| C7 | **Critical-care: corrected calcium masks severe ionized hypocalcemia — worse than total** (MIMIC, N=31,903; doc 19) | strong (data in hand) | **BEST-ALIGNED result (critical-care/anesthesia pivot).** Corrected Ca reads 'normal' (≥8.5) in 40.6% of critical (<0.90) and 57% of severe (0.90-1.00) ionized hypocalcemia — vs 20-22% for total. Danger cell: 52% of ionized<1.00 (n=3,828) masked by corrected; corrected sensitivity ~48% vs total ~78% (correction ~halves sensitivity because it inflates the value in hypoalbuminemic ICU patients). Race-neutral, actionable ('measure ionized in critically ill/massively-transfused; don't trust corrected'). Honest: corrected>total direction is arithmetic in hypoalbuminemia; magnitude + framing are the contribution | **KEEP — critical-care/anesthesia patient-safety companion to the flagship; strongest of the session for the user's field. Optional dev: citrate/CRRT + massive-transfusion subgroups** |

| C8 | **VitalDB: intra-op cuff misses most true (art-line) hypotension** (365-case pilot, 2,109 paired; doc 20) | GO (3,106 co-recording cases) | **STRONG artifact-hardened pilot.** RTM-safe (art-line=gold-standard reference; windowed-median, Bland-Altman bias -0.2). Cuff sensitivity for art-defined hypotension: MAP<65 **59%** (misses 41%), <60 47%, <55 **34%** (misses 66%); over-reads +22 mmHg at severe hypotension. In 60% of cases with true hypotension, cuff missed >=1 episode. Fresh angle: intra-op-hypotension research using CUFF systematically UNDER-detects the exposure -> INSPIRE validation planned (cuff- vs art-based hypotension->AKI attenuation). Honest: cuff-inaccuracy-at-low-BP known (Wax/Kaufmann); the hardened sensitivity quantification + research-bias implication + cross-dataset validation are the contribution | **VALIDATED & HARDENED — top candidate. INSPIRE (47,533 ops) replicates; ATTENUATION: intra-op hypotension->mortality adj OR 2.09 (art) vs 1.48 (cuff), hyperlactatemia 1.91 vs 1.46; matched-cadence confirms MEASUREMENT bias not sampling. Field-reframing: cuff-based hypotension evidence base UNDERESTIMATES harm. See doc 20** |

## STRATEGIC SYNTHESIS — the MC-MED ED "wall-breaker" thesis largely FAILED (4 strikes); revised rule validated
The overnight thesis was: measurement-bias HARM is observable in the ED (recorded actions) where it's unobservable
in ICU paired data. Result across C1–C4: it does NOT deliver top-tier candidates, for consistent reasons:
- **C1 (BEN):** exposure disparity real (1.85×) but the ACTION reversed (Black low-ANC → LESS workup, appropriate
  BEN recognition); action layer confounded by septic presentation.
- **C2 (glucose-Hct):** mechanism doesn't replicate — modern (2020-22) Hct-corrected glucometers engineer it out.
- **C3 (hypoxemia):** no arterial SaO2 reference in the ED (venous only) → untestable.
- **C4 (triage):** the disparity is real but the residual proxy fails to validate against the hard outcome, and
  it's actively scooped.
**Root cause:** attaching a HARM/ACTION endpoint to a disparity keeps failing — the ED action layer is
presentation-confounded, reverses, or doesn't validate. The calcium flagship WON precisely because it stopped at
the OBSERVABLE RECLASSIFICATION endpoint and never needed to prove downstream harm. **Revised search rule for new
candidates: hunt clean RECLASSIFICATION findings (observable, non-tautological direction, subgroup driver) — NOT
action-harm chains.** Remaining backlog C5 (tautological), C6 (confounded), C7 (no anchor) are pre-flagged fatal
→ not worth grinding. Calcium flagship remains the one solid top-tier candidate; new ones need a non-tautological
reclassification in fresh data, or the GPU-gated ECG/EEG deep-learning direction.

## Log
- Idea engine returned 7-candidate ranked backlog. Top = BEN in MC-MED (0.45), directly executing ledger #9f
  (match cohort to where the phenomenon lives — ICU reversed it, ED is right). MC-MED data was recycled →
  re-downloading visits.csv (full) + labs.csv stream-filtered to neutrophil rows. Then: confirm ANC component,
  within-patient longitudinal BEN reference, test abnormal-flag + repeat-order rate by race at matched ANC.
