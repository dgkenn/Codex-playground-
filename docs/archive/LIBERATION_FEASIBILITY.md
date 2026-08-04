# Liberation-sequencing study (#1) — feasibility scout → COMMIT

Goal: of the 4 pivot candidates, drive ONE to a high-impact, fully-validated finding. Scouted #1
(order of organ-support liberation) first; signal + cohort confirmed → committing to the full build.

## Cohort (MIMIC-IV 3.1; procedureevents 225792 IMV / 225802 CRRT; vasopressors from the infusion extract)
- Invasive ventilation: 31,969 stays; vasopressor recipients: 28,483; CRRT: 2,274.
- **vent ∩ pressor = 21,222** (the large 2-way cohort).
- **triple support (vent ∩ pressor ∩ CRRT) = 1,851** (the novel ≥3-way).
- CRRT pairings: vent∩crrt 1,930, pressor∩crrt 2,100.

## Preliminary signal (vent+pressor, both liberated, alive at later liberation; n=18,982)
- Ventilation liberated first → mortality **10.0%**; vasopressor first → **15.1%**.
- Pressor-first mortality OR: **1.48 [1.35, 1.62]** (age-adj) → **1.25 [1.06, 1.47]** (age+lactate). Survives.

## Decision: COMMIT to #1, with the novelty-defensible framing
- **2-way vent-vs-vaso liberation order is published (Zarrabian, AJRCCM 2022)** → a pure 2-way replication
  is not novel. The contribution must be: (i) the **≥3-way generalization incl. CRRT** (n=1,851, open);
  (ii) a **rigorous target-trial emulation** (landmark at first liberation; severity at the decision
  point; sequence as a prospectively-defined exposure) that bounds the confounding the raw signal carries;
  (iii) **external validation in eICU-CRD**.
- **Primary threat:** confounding by indication / immortal-time — pressor-first patients differ
  systematically (resolving shock but persistent respiratory failure carries its own mortality). The
  make-or-break is the emulation design, not the data. If the adjusted/landmarked effect collapses, the
  finding is "sicker patients are liberated in a different order" and we report that honestly.

## Build plan
1. `analysis/liberation_sequence.py` — target-trial emulation: eligibility (co-treated IMV+vaso),
   landmark = first liberation among patients alive+on-both to that point, exposure = which liberated
   first, adjust for age + comorbidity + first-24h SOFA labs + lactate + pre-landmark support durations,
   outcomes = in-hospital mortality (primary) + reintubation ≤72h (liberation failure) + the 3-way order.
2. eICU-CRD replication.
3. Red-team rounds to "fully validated."
