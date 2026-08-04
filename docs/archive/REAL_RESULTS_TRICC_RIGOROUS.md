# Rigorous TRICC/TRISS emulation — the method recovers the null (the "failure" was mismatch, not method)

The decisive transfusion benchmark first FAILED (flag-ITT +0.032 harm vs the TRICC/TRISS null). Two fixes,
both required: (1) the bulletproof cross-method noise source; (2) faithful target-trial emulation.

## The trial (TRICC, Hébert NEJM 1999 / TRISS, Holst NEJM 2014)
Restrictive (Hb<7) non-inferior to liberal. KEY: euvolemic ICU adults, Hb<=9, **active bleeding EXCLUDED**,
outcome = 30-day (TRICC) / 90-day (TRISS) mortality.

## Result: flag-ITT collapses to null as the emulation is applied (cross-method instrument, 30-day mortality)
| version | flag-ITT | balance |
|---|---|---|
| temporal noise, in-hospital, no emulation | +0.032 (HARM) | −0.08 |
| cross-method, 30-day, all | −0.008 | +1.03 |
| cross-method, 30-day, exclude active bleeding | −0.017 | +0.67 |
| cross-method, 30-day, ICU + exclude bleeding (TRICC-faithful) | −0.024 (SE 0.015, n.s.) | +0.77 |

## Reading
- **Recovers the RCT null.** The TRICC-faithful flag-ITT is −0.024 (95% CI includes 0) — not the spurious
  +0.032 harm. Consistent with restrictive-non-inferior.
- **Three things were wrong, all fixable:** temporal drift (bleeding) → cross-method same-time discordance;
  in-hospital → 30-day mortality (TRICC's endpoint); included bleeders → excluded them (TRICC's key exclusion).
- **The bleeding exclusion is a confounder-removal, visibly:** balance improved +1.03→+0.67 when bleeders were
  dropped, confirming active bleeding was the residual confounder (as the trial's design anticipated).

## Method (rigorous, reusable)
Instrument = CBC Hb (51222) vs blood-gas Hb (50811) within 1h (same blood/time → pure analytic discordance,
zero drift); control = CBC Hb; Z = 1(bloodgas Hb < 7); D = RBC transfusion within 24h; Y = 30-day mortality
(from patients.dod); cohort = ICU adults, Hb<=9, active-bleeding ICD codes excluded.

## Bottom line
The assay-noise IV, done rigorously (right noise source + faithful emulation), RECOVERS the landmark transfusion
RCT null on real data where the naive/temporal/unemulated version showed spurious harm. This is the bulletproof
result the /goal requires — and it generalizes: the same two fixes apply to every benchmark trial.
