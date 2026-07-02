# Gate-triggered trials (SUP-ICU, PEPTIC, PREVENT, ADRENAL) — REVISED after fixing real data gaps

**Correction to the prior version of this doc:** the original run classified PEPTIC/PREVENT/ADRENAL as
"design-only data-gap" because this MIMIC-IV extract lacked ventilator, vasopressor, and compression-device
data. That was true of the *extract as fetched*, not of MIMIC-IV itself — the user correctly pushed back that
several trial "failures" were from not copying the source data as completely as possible, not genuine limits.
Investigation confirmed: `procedureevents.csv.gz` (ventilation), `inputevents.csv.gz` re-extracted with
rate/caregiver (vasopressors), and `chartevents.csv.gz` (compression-device itemids 228419–228452) are all
fetchable from PhysioNet with credentials already present in this environment. All three have now been
streamed in. This doc reports the corrected trials.

| trial | trigger | fidelity status | instrument | result vs RCT truth | verdict |
|---|---|---|---|---|---|
| **SUP-ICU** | ≥1 of 6 GI-bleed risk factors | **FIXED** (mech-vent>24h added via procedureevents; gate now 6/6) | admit-provider LOO PPI rate | OTHER-NONELEC: balance-valid but ITT90d=−0.137, far from RCT null (RR 1.02) | emulatable, still **confounded** |
| **PEPTIC** | mech-vent within 24h | **FIXED** (eligibility now verified via procedureevents, not proxied) | unit-month LOO default-class | n=783 (bucket≥15), F=4 (weak), ITT90d=+0.030 [wide CI] | emulatable, **weak instrument** |
| **PREVENT** | expected ICU LOS≥72h + pharm ppx | **PARTIALLY FIXED** (compression-device itemids 228419-228452 found in chartevents; extraction running) | TBD pending extraction | not yet run | in progress |
| **ADRENAL** | vasopressor ≥4h at BP target | **MOSTLY FIXED** (continuous vasopressor-span timing now real, via re-streamed inputevents; BP-target component still pending chartevents MAP) | admit-provider LOO steroid rate | n=21,355, F=336 (very strong) but balAge=−3.54yr | emulatable, **balance-invalid** |

## Reading — fidelity and instrument validity are separate problems
Fixing the data gaps was real and worth doing — SUP-ICU's gate is now complete (6/6 criteria), PEPTIC's
population is no longer mismatched, and ADRENAL's cohort/time-zero are now constructible from real vasopressor
timing (a well-powered n=21,355, strong first stage F=336). **None of these fixes produced a new favorable**,
though:
- SUP-ICU: the fidelity fix left the *estimate* essentially unchanged (still −0.137 vs RCT null) — the
  confounding was never about the missing mech-vent criterion; the provider-preference instrument itself is
  invalid here, for a different reason (residual indication bias the NC/balance check doesn't fully clear).
- PEPTIC: now a legitimately runnable design, but the instrument is underpowered/weak (F=4) — an honest
  inconclusive, not a favorable and not a refusal either.
- ADRENAL: the vasopressor-timing fix makes the cohort real and well-powered, but the provider-preference
  instrument fails balance badly (−3.54yr) — correctly caught and NOT reported as a claim, exactly the gate
  behavior the toolkit is supposed to have.

## Remaining honest gap
ADRENAL's BP-target component (SBP>90/MAP>60) and PREVENT's full pharmacologic-ppx+device gate both need the
chartevents MAP/BP stream (in progress) to be fully faithful; until then both cohorts are duration/state-gated
approximations, not the complete trial gate. This will be revised again once that data lands.

## Ledger impact
Still zero new favorables from the gate-trial family — but the reason has changed from "we don't have the
data" (an excuse) to "we have the data and the instruments are genuinely weak/invalid here" (a finding). That
is a stronger, more defensible negative than before.
