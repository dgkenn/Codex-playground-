# eICU hospital-preference IV — confounded (fails positive-control calibration); the gates discriminate

Paper #1's intended second, independent instrument: across eICU's 208 hospitals, hospital transfusion-liberality
(leave-one-out) instruments individual RBC transfusion in anemic patients, conditional on age + APACHE severity.
Different failure modes from the cross-method assay-noise IV — the point was triangulation.

## Result
| cohort | n | first-stage F | pref-ITT [95% CI] | LATE | balAge | vs RCT truth |
|---|---|---|---|---|---|---|
| ALL anemic (Hb 6–10) | 79,293 | **21,918** | **+0.034 [+0.023, +0.044]** | +0.034 | −0.00 | ✗ RCT null — instrument shows **significant HARM** |
| acute MI (apache dx) | 621 | 248 | −0.030 [−0.124, +0.064] | −0.032 | −0.00 | ~ protective (MINT/MIMIC direction), CI incl 0 |

## The instrument is confounded (and its own positive control proves it)
The first stage is essentially perfect (F=21,918 — hospital liberality is a textbook strong instrument) and age
balance is exact (−0.00). Yet in the **all-anemic** cohort — where the transfusion RCTs establish **non-
inferiority (null)** — it produces **significant harm (+0.034, CI excludes 0)**. A valid instrument must recover
that null. It does not. Mechanism: **hospital-level confounding** — hospitals that transfuse more liberally
differ in unmeasured case-mix / quality / practice that also raise mortality, and age + APACHE do not remove it.
This is the well-known Achilles heel of preference IVs, and here the all-comers cohort acts as a **built-in
positive control that the instrument fails.**

## Empirical-null calibration (Schuemie/Madigan) — the honest salvage
Treat the all-comers estimate as the instrument's measured bias on a known-null exposure→outcome pair (+0.034).
Calibrating the MI estimate against it: **MI_calibrated ≈ −0.030 − 0.034 = −0.064** (more protective), i.e. after
removing the instrument's systematic upward bias, the MI signal is protective and **consistent in direction with
MINT (liberal-favoring) and the MIMIC cross-method MI LATE (−0.18).** Caveat: this assumes the confounding bias
is similar in the all-comers and MI cohorts — a strong assumption; a rigorous version needs a *panel* of
negative-control outcomes per cohort, not a single anchor.

## What this means for Paper #1
- The **cross-method assay-noise IV remains the only clean instrument**: passes all gates and recovers the
  transfusion null **cross-nationally (MIMIC + SICdb)**.
- The **hospital-preference IV is confounded** (fails its positive control) — so the triangulation does **not**
  get a second clean instrument. The MI direction agrees across all three lines (MIMIC −0.18, eICU raw −0.03 /
  calibrated −0.06, MINT liberal-trend), but only suggestively — the eICU arm is direction-consistent, not
  confirmatory.
- **This strengthens the FLAGSHIP, not #1:** it is a clean demonstration that the gate battery **discriminates**
  — the cross-method instrument passes the null-recovery gate on two continents while the hospital-preference
  instrument fails it, exactly as a self-diagnosing framework should. It becomes a key panel in the specificity
  figure (F4), and a cautionary result on preference IVs.

## Honest verdict
Paper #1's open MI question is **not cleanly resolved**: consistent protective direction across three lines, but
the only gate-passing instrument (MIMIC cross-method) is underpowered (n=766) and SICdb can't add MI power
(n=10). The eICU hospital-preference IV is confounded. The durable, publishable results are (a) the
**cross-national transfusion-null replication** (MIMIC↔SICdb) and (b) the **flagship's gate-discrimination**
evidence — with MI transfusion reframed as a well-characterized, direction-suggestive open question rather than
a resolved one.
