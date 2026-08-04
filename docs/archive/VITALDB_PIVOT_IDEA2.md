# CPU pivot (user chose "broaden the hunt") — VitalDB intraoperative hemodynamics → postop AKI

**Context.** EEG-FM path is GPU-gated (Cycles 3–4: frozen encoder is the ceiling). User: pursue a
high-impact, CPU-feasible, externally-validated anesthesiology question. Picked from
`docs/ANESTHESIA_FIVE_IDEAS.md` Idea 2 (VitalDB is fully OPEN, no DUA; 500 Hz arterial waveform).

## Novelty pre-screen result (haiku + PubMed, vocabulary-varied) — the idea was REFRAMED because of it
Original Idea 2 = "arterial WAVE-REFLECTION recovery kinetics → postop AKI." Verdict: **INCREMENTAL + two
near-fatal problems.**
- **Named-index proximity:** static augmentation index / wave reflection is a 20-yr named construct (O'Rourke).
- **FATAL methods flaw:** pressure-only wave separation is discredited (Mynard 2012, *J Hypertens* — the
  reservoir-wave paradigm "introduces error into arterial wave analysis"). VitalDB has no aortic flow →
  cannot do true wave separation. A reviewer kills this on sight.
- **Weak external validation:** INSPIRE has no waveforms → cannot replicate a waveform-derived marker.

**But the pre-screen CONFIRMED the white space underneath:** the higher-MAP-target RCTs are NULL
(Salmasi 2017 established TWA-MAP; Chiou 2026 meta-analysis of 15 trials, Saugel 2025 IMPROVE — no benefit
of higher/individualized MAP for AKI/MI). The field explicitly calls for a **dynamic "reserve/endotype"
dimension beyond absolute pressure / TWA-MAP** (Joosten 2026 consensus). "Hemodynamic recovery time
constant / perturbation" returns **0 hits**.

## Reframed idea (Idea 2′) — pressure-only, non-named, dynamic; dodges Mynard entirely
**Marker:** the **recovery kinetics (time-constant τ / settling behaviour) of MAP and pulse pressure after
the universal perturbation of anesthetic INDUCTION** — every case has induction → MAP nadir → recovery.
Pressure-only (no wave separation). Non-named. Dynamic ("vasoregulatory reserve").
**Hypothesis:** slower/again recovery predicts postop **AKI** (primary; KDIGO creatinine) and in-hospital
mortality (secondary), **incremental to TWA-MAP, MAP variability, and baseline risk** (age, ASA, preop
creatinine/labs, surgery type). If it adds nothing over TWA-MAP → honest null (still informative given the
null RCTs). 
**Make-or-break threats (pre-registered):**
1. **Confounding by the recovery intervention** (pressors/fluids given during induction recovery) — τ is
   partly iatrogenic. Must adjust for induction-period drug/fluid dose, or model τ conditional on it, or
   stratify to comparable management. This is the liberation-order lesson applied up front.
2. **External validation of a waveform marker** is the structural risk (VitalDB is the only open intraop
   waveform DB). Plan: internal validation by surgery-type hold-out + temporal split; explore MOVER (DUA)
   or a MIMIC ICU arterial-line analog as a coarse external check. Flagged as the key limitation.
3. Incremental-marker trap: MUST beat TWA-MAP + variability, or it's another "detects sick patients."

## Feasibility (VitalDB open API — CONFIRMED)
- 6,388 cases; **3,645 with SNUADC/ART 500 Hz** arterial waveform; death_inhosp, icu_days, asa, preop labs,
  optype/opname/approach/position/ane_type, anesthesia/op timestamps all present.
- **Make-or-break gate before any modeling: is AKI derivable at scale** (preop + postop creatinine from the
  `/labs` endpoint) on the ART cohort? If yes → pilot the τ marker vs TWA-MAP. If no → pivot.

## Feasibility gate — PASSED (VitalDB `/labs` = time-stamped `cr`, 37,311 values)
- ART ∩ baseline+postop creatinine (**AKI-derivable**): **2,542–2,579 cases**; **AKI prevalence 12.0%
  (305 events)** by KDIGO creatinine (≥1.5× baseline or ≥0.3 mg/dL rise ≤48 h). Well-powered.
- The τ marker needs only the **numeric `Solar8000/ART_MBP/SBP/DBP` tracks (~2 s res)** — NOT the 500 Hz
  waveform → downloads are ~250× cheaper, whole study is CPU/bandwidth-light.

## Preliminary pilot (n=162, only 17 AKI events — UNDERPOWERED, do not over-read)
Induction MAP-nadir → recovery-τ (time back to 90 % of pre-induction baseline) + TWA-MAP + AUC(MAP<65).
Univariate AUC vs AKI: **τ 0.375** (if anything *reversed* from the "slow recovery → more AKI" hypothesis),
TWA-MAP 0.487, AUC65 0.542, MAP-variability 0.430, induction nadir 0.592. Everything ≈chance at 17 events —
cannot distinguish "no signal" from "underpowered" (the Cycle-3 lesson). **A properly-powered read on
~1,000+ cases (~120+ events) is running before any verdict.** Early indication: the τ marker is NOT looking
promising, and even TWA-MAP is ~chance here (consistent with the null higher-MAP-target RCTs in noncardiac
surgery). If the powered read confirms τ adds nothing over baseline risk, this is an honest null → log and
re-rank, do not force it.

## POWERED RESULT (n=1,255; 149 AKI events) — clean NULL for the recovery-τ marker
Nested 5-fold OOF logistic (mean of 5 seeds):
| Model | OOF AUC |
|---|---|
| M0 baseline (age, sex, ASA, preop creatinine) | 0.770 |
| M1 = M0 + standard intraop hemodynamics (TWA-MAP, AUC<65, MAP-variability, induction nadir, drop) | 0.806 |
| **M2 = M1 + recovery-τ** | **0.801 (Δ over M1 = −0.005)** |
| M0 + τ only | 0.764 (Δ over M0 = −0.006) |

τ adjusted standardized logit coef **+0.043, 95% CI [−0.156, +0.187]** (spans 0). **The induction
MAP-recovery-τ marker has ZERO incremental value** for postop AKI over baseline risk and standard
hemodynamics — a clean, powered null (not a marginal miss). No τ-definition fishing (would be
garden-of-forking-paths); one pre-specified marker, powered, null.
- Secondary (non-novel): baseline clinical risk alone predicts AKI at 0.770; standard intraop
  hemodynamics add a modest +0.036 — consistent with the literature, not a finding.
- **Reusable asset built:** a VitalDB AKI cohort (2,579 cases with arterial line + KDIGO creatinine, ~305
  events) with cheap 2 s numeric hemodynamics — reuse for other markers/outcomes without re-fetching.
- **Verdict: GATED-NULL. Re-rank the queue** (next candidates: Idea 4 ventilator-waveform dynamics → PPCs;
  Idea 3 individual cerebral-suppression threshold → delirium; or a cleanly externally-validated MIMIC↔eICU
  tabular question). The recovery-kinetics reserve hypothesis is not supported in noncardiac surgery.
