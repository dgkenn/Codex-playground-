# Severity-stratified anion-gap masking of lactic acidosis in hypoalbuminemia (MIMIC-IV)

**Status:** NARROW-BUT-NOVEL win, honestly bounded. Mechanism/blind-spot gradient is real and large; the
naive corrected-AG "fix" fails on specificity (reproduces Dinh 2006). Decision endpoint (Phase 2) is the
make-or-break next step. Predicted win-likelihood 0.40 (IDEA_GATE) → novelty screen 0.30 (NARROW-BUT-NOVEL) →
actual: matches the narrow prediction.

## Idea (propagation template)
- **Bias (KNOWN, Figge 1998):** albumin is the dominant unmeasured anion; each ~1 g/dL fall lowers the measured
  anion gap by ~2.5 mEq/L → hypoalbuminemia produces a falsely-normal AG that can hide organic (lactic) acidosis.
- **Ground-truth reference (in cohort):** measured lactate (blood-gas, itemid 50813), free/untitrated → truth
  for lactic acidosis.
- **Driver:** hypoalbuminemia (albumin 50862).
- **Pre-computed AG:** MIMIC lab itemid 50868 (also cross-checkable from Na 50983 − [Cl 50902 + HCO3 50882]).

## Prior-art gate (sonnet novelty screen)
- LAYER-1 mechanism KNOWN (Figge/Feldman/Kraut-Madias).
- LAYER-2 (corrected-AG improves lactate detection) MODERATE-TO-SATURATED **with a published NEGATIVE**: Dinh
  2006 (Emerg Med J, n=356) — pooled AUC 0.757 uncorr vs 0.750 corr, "no advantage"; Chawla 2008 (BMC Emerg Med)
  — correction raises sensitivity but craters specificity; EMCrit/Carvounis-2000 methodological-circularity
  rebuttal (corrected AG r≈0.11 with true unmeasured anions). A 2023-25 MIMIC/eICU wave uses corrected-AG only as
  a **mortality-prognostic covariate**, not a detection endpoint.
- LAYER-3 wedge PARTIALLY-CLAIMED: the pooled comparison is done (negatively). UNCLAIMED = **severity-stratified**
  miss-rate gradient at scale + a **decision/action endpoint** (delayed lactate/resuscitation) + disparity.
- **Verdict: NARROW-BUT-NOVEL.** Sharpest differentiator: do NOT re-run pooled AUC (Dinh owns the null); run the
  severity-stratified gradient + decision endpoint. Biggest threat: Dinh 2006.

## Phase 1 result (MIMIC-IV; local labevents copy is truncated → N is a lower bound)
Paired chem-panel (AG+albumin) ↔ nearest lactate within ±2h: **57,761 panels**; true lactic acidosis
(lactate ≥4) = 5,431.

**Missed lactic acidosis (uncorrected AG ≤12) by albumin — monotone gradient:**

| albumin (g/dL) | n (acidosis) | % missed (uncorr AG≤12) | % missed (corr AG≤12) | mean AG | mean corrAG |
|---|---|---|---|---|---|
| <2.0    | 473  | **8.7%** | 0.4% | 21.3 | 27.3 |
| 2.0–2.5 | 781  | 6.1% | 0.1% | 21.0 | 25.5 |
| 2.5–3.0 | 1072 | 4.9% | 0.3% | 21.3 | 24.5 |
| 3.0–3.5 | 1041 | 3.0% | 0.4% | 21.7 | 23.8 |
| ≥3.5    | 2064 | **1.0%** | 0.7% | 22.9 | 22.5 |

- **Relative risk of a missed (normal-looking) AG, severe-hypoalb (<2.0) vs normoalb (≥3.5) = 8.95
  (95% CI 5.29–15.12).** Mean AG is flat (~21) across albumin strata while mean corrected AG rises as albumin
  falls (22.5→27.3) — the Figge mechanism, at scale.
- **Robust:** lactate ≥6 → 3.4% vs 0.26% (~13×); miss threshold AG≤10 → 3.8% vs 0.19% (~20×).

## The load-bearing caveat (Dinh confirmed — the "fix" is not the corrected threshold)
2×2 sensitivity/specificity for AG>12 detecting lactate≥4, by albumin stratum:

| stratum | sens uncorr→corr | spec uncorr→corr |
|---|---|---|
| hypoalb (alb<3.0), npos=2326 nneg=7458 | 93.9% → 99.7% (**+5.8**) | 44.9% → **8.1%** (**−36.8**) |
| normoalb (alb≥3.5), npos=2064 nneg=21261 | 99.0% → 99.3% (+0.3) | 21.6% → 20.9% (−0.6) |

In hypoalbuminemia, switching to corrected-AG>12 recovers sensitivity **only at a catastrophic specificity cost**
(45%→8%) — i.e. it flags ~92% of non-acidotic hypoalbuminemic patients. This **reproduces Dinh 2006 / the
EMCrit critique**: corrected-AG is not a viable decision rule. (Caveat on the caveat: AG>12 has many non-lactate
causes, so specificity-vs-lactate understates AG's true utility — but the over-flagging direction is unambiguous.)

## Honest synthesis / actionable message
The value is **not** "correct the anion gap" (fails on specificity, already litigated). It is:
1. A quantified, severity-stratified diagnostic **blind spot**: hypoalbuminemic patients with true lactic
   acidosis are ~9× more likely to present a reassuring-normal AG (novel vs Dinh's pooled null).
2. The safeguard is **direct lactate measurement whenever albumin is low**, not a corrected-AG threshold.

## Phase 2 (make-or-break, NOT yet run) — the decision endpoint
Does a masked-normal AG actually **delay lactate measurement / resuscitation** in practice? Design: population
with a chem panel (AG+albumin) and **NO concurrent lactate**; exposure = hypoalbuminemia-masked normal AG
(uncorr≤12 & corr>12) vs truly-normal (both ≤12) vs flagged (uncorr>12); outcome = time-to-first-lactate order,
whether a later lactate reveals acidosis, mortality.
**Two hard risks (pre-registered):** (a) **truncation** — the local labevents is partial, so "no concurrent
lactate" can be an artifact; Phase 2 requires the FULL labevents re-download. (b) **confounding by acuity** — why
lactate wasn't drawn is confounded by how sick the patient looked; the masked-AG-no-lactate group may be less
acute, not victims of masking (same paired-design/indication trap as C12-1). Needs acuity adjustment + a
falsification (masked vs truly-normal AG should differ only if the AG drove behavior).

## Files
- Extraction: `scratchpad/aniongap_rows.csv` (itemids 50868/50862/50813/50983/50902/50882/53154).
- Analysis: inline (this doc); reproducible from the extraction.
