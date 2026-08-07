# E300–E304 — the deciding test could not be decided. The circularity objection stands unresolved.

*2026-08-07. Exposure probe: 2,930 cases, `Primus/MAC` for volatiles and `Orchestra/PPF20_CE` for
propofol, **100 % coverage in all three arms**.*

---

## 1. E302 — the new axis FAILED its own validation, and that governs everything after it

The registration says, before any result existed:

> **E302.** Correlate each case's within-arm exposure percentile against its BIS. A validity check on the
> new axis BEFORE it is trusted (rule 57). **WRONG IF: no relationship, in which case the exposure axis is
> not measuring depth in this cohort and E301 is uninterpretable whichever way it comes out.**

    pooled Spearman(exposure percentile, BIS) = -0.0529   over 726 cases
    per arm:  sevo -0.2150 | des -0.0161 | ppf +0.0815

**Only sevoflurane reaches the predicted −0.20. Desflurane is flat and propofol runs the wrong way.**
The anaesthesia machine's own drug record, at a single maintenance moment, carries almost no information
about where the patient's EEG sits. That is not a bug in the probe — it is the well-known fact that
inter-individual sensitivity to anaesthetic is large, so concentration is a weak predictor of EEG state
between people. It does mean this axis cannot arbitrate anything about depth.

## 2. E301 "passed", and I am not claiming it

    quintile n = [149, 148, 146, 148, 149]      (0 = least drug ... 4 = most drug)
    critical_slowing_ar1   rho = +1.0000   0.273 0.345 0.402 0.427 0.451
    exponent_low           rho = +1.0000   0.205 0.298 0.359 0.413 0.450
    multiscale_entropy     rho = +0.9000   0.293 0.333 0.434 0.422 0.448
    alpha_peak_hz          rho = +0.9000   0.153 0.366 0.330 0.426 0.464
    median rho = +0.9000;  permutation null 95th = +0.7000;  p = 0.0250

Leakage rises with drug exposure, in the same direction as the BIS-stratified gradient, at p = 0.0250.
**This is the answer I wanted and my own pre-registered gate forbids me from using it.** E302 failed, and
the registration states the consequence "whichever way it comes out". Reporting E301 as the confirmation
would be exactly the move `DISCOVERY_LOOP.md` §2 forbids — using a validity gate's failure as optional
when the primary happens to agree.

**What E301 does establish, at most:** something ordered by drug exposure also orders leakage. Because
exposure and BIS are nearly unrelated here (E302), that "something" is *not* demonstrably depth, and it
may be a third variable — case type, duration, institutional practice — that drives both dose and
spectrum. The circularity objection to E271/E291/E296 is therefore **neither confirmed nor refuted. It
remains the single largest unresolved weakness in the claim.**

## 3. E303 — the within-patient dose-response is NULL, and the estimator is fragile

    above null in 0 of 18 cells, n = 688 patients
    whole_head_exponent   sevo/des 0.024   sevo/ppf 0.051   des/ppf 0.027   (null95 ~0.05-0.07)

The gate passed first: **E304** confirms both arms genuinely move (median |exposure percentile change|
22.4 / 25.3 / 19.0), so this is not rule 32's dead-variable failure.

**Prediction NOT MET, and I named this deflationary outcome first in the registration.** Once the
candidate's between-state change is normalised by how much drug changed, agents no longer differ. Taken
with **E294** — where the un-normalised within-patient change *does* identify the agent in 16 of 18 cells
— the combined reading is that the arms differ in *how far the state moved*, not in a drug-specific
slope. That is a materially weaker and more deflationary picture than E294 alone suggested.

**A defect in my own estimator, reported without re-running it (rule 58).** E303's statistic is the
per-patient ratio `Δcandidate / Δexposure`, and I gated only `|Δexposure| ≥ 1.0` percentile point. A ratio
with a near-zero denominator has unbounded variance, so a minority of patients dominate and power
collapses. **The null may be the statistic rather than the biology.** The correct successor is a
regression slope across patients with exposure change as the regressor, not a per-patient ratio — and it
is a successor, not a re-run, because changing the guard after seeing a null is goalpost-moving.

## 4. Where this leaves the paper

| question | status |
|---|---|
| Is leakage larger at maintenance than at emergence? | **Established** — E260, E297, E298, two cohorts |
| Does it grade with BIS? | **Established on the BIS axis** — E291, E296 (ρ = −0.90, p = 0.0000) |
| Is that gradient circular (EEG measure stratified by EEG index)? | **UNRESOLVED** — E295 failed, E301/E302 could not arbitrate |
| Does it hold within patients, per unit drug? | **Null**, with a fragile estimator — E303 |
| Does it extend beyond volatile-vs-propofol? | **No** — E299 |
| Is it novel? | **Unverified** — E290, tooling blocked |

**Two of those six are blocking, and neither can be closed in this environment.** Circularity needs a
depth axis that is neither EEG-derived nor drug concentration — a behavioural or reflex measure, which
VitalDB does not carry. Novelty needs a human to read four to seven papers.

## 5. What I would need to make this publishable, in priority order

1. **A behavioural depth anchor.** DOSE-I ships per-second MOAA/S in 171 recordings and both an EEG and
   a computed monitor. It is single-agent (propofol), so it cannot test leakage — but it *can* test
   whether the BIS-stratified gradient survives when depth is defined behaviourally in a cohort where
   that is possible, which is the transportable half of the objection.
2. **The novelty read.** PMIDs 38157438, 31326088, 10965721, 10939694 ("drug-independent" + EEG +
   anaesthesia, the entire returned set) and 28574372, 23567809, 11759923, 11171465. Eight papers.
3. **The slope-based within-patient successor** to E303.
4. **A second deposit with two mechanistically distinct agents.** Q9 records that none is public; the
   Turku/Kallionpää cohort (PMID 32773216) is the named request target.
