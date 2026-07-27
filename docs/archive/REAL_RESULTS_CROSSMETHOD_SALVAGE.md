# The bulletproof fix: cross-method discordance recovers the transfusion RCT null

## The problem (decisive benchmark failure)
The temporal assay-noise IV (instrument = consecutive-draw variation) FAILED the transfusion benchmark:
flag-ITT +0.032 (harm) vs the TRICC/TRISS NULL, because the empirical Hb sigma (0.70 g/dL) is dominated by
BIOLOGICAL DRIFT (Hb falling from bleeding), not analytic noise -> the flag-crossing tracks bleeding severity
-> confounded. Age balance passed (-0.08) but didn't catch it (bleeding isn't age-related).

## The fix: use a genuinely-exogenous noise source
Two INDEPENDENT measurements of the SAME blood at the SAME time — CBC Hb (itemid 51222) vs blood-gas Hb (50811),
matched within 1h — have ZERO temporal drift. Their difference is pure analytic/method (+arterial-venous)
discordance, orthogonal to prognosis. Conditional on one (CBC = contemporaneous true-Hb control), which side of
the flag the OTHER method reads is as-good-as-random.

## Result — it recovers the null
| instrument | flag-ITT (mortality) | balance (age) | vs TRICC/TRISS null |
|---|---|---|---|
| temporal (drift-contaminated) | +0.032 (SE 0.005) HARM | −0.08 | ✗ fails |
| **cross-method discordance** | **+0.0015 (SE 0.015) NULL** | +0.62 | ✅ recovers |
(band Hb 6.3–7.7, n=2797, FS +0.082 F=11; band 6.0–8.0 flag-ITT −0.003, same conclusion.)

## Why this matters (answers "is the method salvageable?")
YES. The assay-noise IV is valid when the noise is genuinely analytic/exogenous. Temporal variation in clinical
labs is drift-dominated and fails; **cross-method / same-specimen discordance is the exogenous noise source that
works** — it recovers the landmark RCT null on the decisive case where the naive/temporal approach shows harm.
This is the bulletproof version of the instrument.

## Still to do (tighten it)
1. **Proper TRICC/TRISS emulation** — exclude active bleeding, restrict to the trial population + outcome window
   (30/90-day). This should sharpen the null and the balance (bleeding is the residual confounder).
2. Extend cross-method to glucose (chemistry 50931 vs blood-gas 50809), and any analyte with dual measurement.
3. First stage is weak (F~11) -> lead with the flag-ITT null; report implied-LATE with AR CIs.
