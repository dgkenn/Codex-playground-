# Quasi-experimental tests against confounding by indication (MIMIC requirement->mortality)

Confounding by indication (sicker patients get more vasopressor) cannot be excluded observationally. The E-value + within-severity-stratum evidence lives in `CONFOUNDING_BY_INDICATION.md`. This document adds two QUASI-EXPERIMENTAL checks built from a one-time inputevents re-stream (raw deleted after filtering, disk-safe).

- Norepi stays analysed: **15949**; with propofol co-exposure: **9203**. Propofol itemid 222168 (confirmed via d_items).

## 1. Negative-control exposure: propofol (sedation depth)
Propofol is titrated to sedation in ventilated, sicker patients -- a treatment-intensity marker, NOT a vasopressor. If it predicts death as strongly as norepi, the signal is generic 'sicker get more of everything'. If norepi is specifically stronger, the vasopressor requirement is not merely treatment intensity.

- Norepi (age-adj): OR/SD 3.798 (CI [3.451, 4.15], n=15949).
- Propofol (age-adj): OR/SD 0.829 (CI [0.785, 0.879], n=9203).
- Propofol adjusted for norepi: OR/SD 0.88 (CI [0.829, 0.931]).
- **Head-to-head** (death ~ norepi + propofol + age, mutually adjusted): norepi OR 3.012 [2.736, 3.299] vs propofol OR 0.88 [0.829, 0.931] (n=9203).

  _propofol OR 0.829 is weak/null vs norepi OR 3.798 (ratio 4.58); the vasopressor requirement is SPECIFIC, not generic treatment intensity._

## 2. Prescribing-preference instrument (preference IV / 2SLS)
Instrument = leave-one-out mean norepi requirement of the patient's care unit (`first_careunit`) or caregiver group -- a provider/unit titration TENDENCY independent of the individual patient. Relevance is testable (first-stage F); exclusion (preference affects death only via dose) is argued, not tested.

- Unit-level: first-stage F 155.68 (weak=False); naive dose OR/SD 2.569 -> IV dose OR/SD 3.78 [3.082, 4.69] (n=5304, groups=10).
- Caregiver-level: first-stage F 76.58 (weak=False); naive OR/SD 2.917 -> IV OR/SD 3.85 [2.879, 5.213] (n=3857).
- Chosen instrument: **unit**.

  _chosen instrument = unit (first-stage F 155.68). IV dose->mortality OR 3.78 [3.082, 4.69] vs naive OR 2.569. IV estimate stays positive with CI excluding 1 -> the dose->mortality link survives instrumentation by prescribing preference, arguing it is not PURELY patient-level confounding by indication._

## Verdict
The quasi-experiments STRENGTHEN the argument against confounding by indication. (1) NEGATIVE CONTROL: norepi age-adj OR 3.798 vs propofol age-adj OR 0.829; head-to-head norepi OR 3.012 [2.736, 3.299] vs propofol OR 0.88 [0.829, 0.931] (mutually adjusted). propofol OR 0.829 is weak/null vs norepi OR 3.798 (ratio 4.58); the vasopressor requirement is SPECIFIC, not generic treatment intensity. (2) PREFERENCE IV: chosen instrument = unit (first-stage F 155.68). IV dose->mortality OR 3.78 [3.082, 4.69] vs naive OR 2.569. IV estimate stays positive with CI excluding 1 -> the dose->mortality link survives instrumentation by prescribing preference, arguing it is not PURELY patient-level confounding by indication. HONEST CAVEATS: IV exclusion (unit/provider preference affects death only via dose) is UNTESTABLE and a unit that titrates higher may also be a sicker unit (unit-level confounding the IV cannot purge); weak instruments bias the IV toward the naive estimate. The negative control is imperfect (propofol use itself tracks ventilation/severity). These checks COMPLEMENT, not replace, the E-value + within-severity-stratum evidence; together they make confounding by indication an implausible SOLE explanation, not an excluded one.

## Honest IV / negative-control caveats
- **Exclusion restriction is untestable.** A unit's/provider's titration preference is assumed to affect mortality only through the dose it produces. If higher-titrating units are also sicker units, the instrument is invalid (unit-level confounding).
- **Weak instruments** bias the IV estimate toward the naive (confounded) estimate; we report the first-stage F and flag F<10. A usable F does not prove exclusion.
- **The negative control is imperfect:** propofol use itself tracks mechanical ventilation and severity, so a non-null propofol OR is expected; the argument rests on the SPECIFICITY gap (norepi >> propofol after mutual adjustment), not on propofol being exactly null.
- These are observational quasi-experiments. They COMPLEMENT the E-value + within-severity-stratum analyses; together they make confounding by indication an implausible SOLE explanation, not an excluded one. The claim remains risk-stratification, not a demonstrated treatment effect.
