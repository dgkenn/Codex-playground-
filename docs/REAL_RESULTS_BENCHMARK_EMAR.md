# RCT benchmark, first pass (treatment from emar) — a valid null, a caught failure, a data limit

The make-or-break test: does the assay-noise IV recover the RCT truth while naive shows confounding? First pass
sourced treatment hospital-wide from emar (to avoid waiting on the slow inputevents download). Full log:
`scratchpad/benchmark_emar_results.txt`.

## Results
| case | n | FS (F) | NAIVE | flag-ITT | ITT age-adj | balance | RCT truth | verdict |
|---|---|---|---|---|---|---|---|---|
| Insulin @glucose>180 | 16,415 | +0.052 (73) | +0.0016 | +0.0013 | +0.0022 | **−0.16 yr** | NICE-SUGAR (intensive harms) | ✅ VALID, near-null |
| Bicarbonate @HCO3<15 | 9,529 | +0.057 (30) | +0.0527 | +0.113 | +0.107 | **+2.02 yr** | settled null | ❌ INVALID (gate catches it) |
| RBC transfusion @Hb<7 | — | — | — | — | — | — | TRICC/TRISS null | ⏳ can't run from emar |
| Platelet @plt<10 | — | — | — | — | — | — | Stanworth null | ⏳ can't run from emar |

## Honest reading
1. **Insulin @glucose>180 is a VALID clean result** (balance −0.16 yr): being pushed above the glucose flag by
   noise → insulin → ~no mortality effect (near-null ITT). Caveat: this tests the *conventional* 180 threshold,
   not NICE-SUGAR's intensive 80–110 target, so it is a weak benchmark *match* even though it is a valid estimate.
2. **Bicarbonate @HCO3<15 FAILS — and the balance gate correctly catches it** (+2.0 yr; ITT even larger than
   naive). HCO3<15 *is* severe acidosis: the flag is a severity marker and HCO3 varies biologically, so the
   noise-IV cannot overcome the confounding. The method rejects itself here — a passed gate, not a false result.
3. **RBC & platelet transfusions are NOT in emar** (blood products aren't emar medications; they live in ICU
   `inputevents`). So the two *cleanest* benchmark cases (TRICC/TRISS, Stanworth) require inputevents.

## The scientifically important pattern (emerging across all real results)
The assay-noise IV is valid where the trigger lab is **precisely measured and not itself a severity marker**
(glucose balance clean; ICU electrolytes better than ward), and it **fails — with the balance gate catching it —**
where the flag lab is a **severity marker or biologically variable** (HCO3<15 severe acidosis; ward Mg/K renal
variability). This is exactly the honest scope statement a top-tier methods paper needs, and the gate policing
itself is the credibility mechanism.

## The decisive test is still pending
The cleanest case — **Hb<7 → RBC transfusion** — is precisely where the method *should* work: Hb has CV 1–2%
(analytic-noise-dominated), Hb<7 is a threshold not a severity-marker per se, and Bosch et al. 2022 already
showed an RDD works there. That benchmark needs `inputevents` (blood products, itemid 225168), now downloading
(107 MB of ~400 MB). It is wired to auto-run via `run_when_ready.sh` → `portfolio_run.py` on ALLDONE. That is the
result that most determines the flagship framing, and it is imminent, not blocked.
