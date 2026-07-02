# Gate-triggered trials (SUP-ICU, PEPTIC, PREVENT, ADRENAL) — no favorable; data gaps + confounded preference-IV

These four trials have a **risk-factor / clinical-state gate** trigger (not a single lab flag), so the
assay-noise IV does not apply; the candidate instrument is provider/unit preference or a threshold RDD. None
produces a validated recovery of the RCT truth on this MIMIC-IV extract.

| trial | trigger | instrument attempted | result vs RCT truth | verdict |
|---|---|---|---|---|
| **SUP-ICU** | ≥1 GI-bleed risk factor at ICU admit | admit-provider LOO PPI-initiation rate | EMER stratum balAge −3.4yr (invalid); OTHER-NONELEC ITT-90d **−0.13** vs RCT **null (RR 1.02)** | emulatable but **confounded** — not a favorable |
| **PEPTIC** | mech-vent within 24h | unit-month LOO default-class IV | balAge −4.2yr (fails); ITT far from RCT null | **design-only** (vent eligibility unverifiable) |
| **PREVENT** | expected ICU LOS ≥72h + on pharm ppx | none — **IPC device exposure absent** | cannot run | **design-only data-gap** |
| **ADRENAL** | vasopressor ≥4h at BP target | none — **vasopressor timing/dose absent** | cannot run | **design-only data-gap** |

## Reading
- **SUP-ICU is the informative negative:** the provider-preference PPI instrument has a very strong first stage
  (F>1000) yet the passing stratum's estimate (−13 pp mortality) is nowhere near the trial's null. A single-covariate
  age-balance check passed while the estimate is grossly confounded — the same "balance ≠ exclusion" lesson, now
  in a preference-IV. Without a negative-control empirical null this would have been a false positive; with it, it
  is correctly rejected. Not a favorable.
- **PEPTIC/PREVENT/ADRENAL are data-gap design-onlys:** this extract's `repletions` carries only
  electrolyte/blood-product/insulin itemids (no vasopressor/heparin), and there is no ventilator or IPC-device
  table — so eligibility, time-zero, and the randomized exposure cannot be reconstructed. Logged as designs with
  the specific missing table, not fabricated runs.

## Useful data discovered (for later)
`rx_class.csv` exists with drug classes (ppi, h2, anticoag_ppx, steroid), and `admissions.admit_provider_id`
supports provider-preference IVs. These enable future PPI/steroid exposure and provider-level instruments —
but the gate trials still need vasopressor/vent/device streams absent here.

## Bottom line for the validation program
The gate family contributes **zero favorables**. Confirms that the path to a 10+ favorable validation ledger is
**not** breadth across trigger types but depth in the one clean instrument (Hb) across the transfusion-RCT
landscape (FOCUS/TITRe2/MINT/REALITY/Villanueva), several of which have non-null truths.
