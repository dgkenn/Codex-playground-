# Creative high-impact angles for the electrolyte-repletion question (after RDD failed)

RDD failed (smooth dose-response, no discontinuity) and IPTW is hopelessly confounded (RR 4.17, marker of
severity). We need EXOGENOUS variation in repletion unrelated to the individual patient. Ranked by promise ×
feasibility with the data in hand (MIMIC obfuscates calendar dates but preserves time-of-day/day-of-week,
within-patient timing, and provider IDs).

## #1 — PROVIDER-PREFERENCE IV (tested feasible — the lead creative angle)
Classic solution to confounding-by-indication (McClellan cardiac-cath, Brookhart preference-based IV):
patients are ~as-if-randomly assigned to admitting providers who vary in repletion habit; the provider's
baseline repletion tendency instruments the individual's treatment.
**Feasibility test (mild-Mg cohort, n=130,249, 834 providers ≥20 pts):**
- Provider repletion rate spans p10=0% → p90=20% (strong variation).
- **RELEVANCE: corr(provider leave-one-out repletion rate, individual repletion) = +0.41** — a STRONG first
  stage (vs ≈0 for every threshold design). This is the first design with a real first stage.
- **BALANCE: corr(provider tendency, Mg value) = −0.016** (excellent). corr(provider tendency, mortality) =
  **+0.127** — a moderate exclusion-restriction concern (repletion-happier providers have somewhat sicker
  patients — likely SERVICE-mix). **Fix: condition the IV within service/care-unit** (compare providers on
  the same service); if the mortality correlation vanishes within service, the IV is valid. If it persists,
  the exclusion restriction fails and this angle dies too — but it is by far the most promising path to a
  causal estimate, and worth the next cycle.
- Estimator: two-stage / 2SLS or a Wald ratio (provider-tendency → repletion → outcome), with provider fixed
  or random effects nested in service; report the LATE (effect on compliers = patients whose repletion is
  determined by which provider they drew). Falsification: negative-control outcomes; over-identification if
  multiple instruments (provider + service tendency).

## #2 — MENDELIAN RANDOMIZATION (complementary, uses PUBLIC data, no patient records)
Two-sample MR: genetic variants for serum Mg (and K) as instruments for the LEVEL → AF / arrhythmia /
mortality, using public GWAS summary statistics (OpenGWAS/MR-Base). Answers "does the LEVEL causally affect
outcomes" — if genetically-lower serum Mg is NOT causal for AF/mortality, correcting mild low Mg is
biologically pointless. Sidesteps confounding entirely via germline randomization. Caveats: answers
level-effect (not the repletion decision); MR of Mg may partly exist (novelty check needed). High-impact,
genuinely creative, feasible without any patient data — a strong COMPLEMENTARY paper alongside #1.

## #3 — IV-electrolyte SHORTAGE natural experiment (ideal, but needs real-calendar data)
Documented national IV Mg/K shortages (e.g., post-2017) forced rationing of repletion EXOGENOUS to individual
severity → interrupted-time-series / diff-in-diff of outcomes across shortage vs non-shortage periods. The
cleanest possible natural experiment. NOT feasible in MIMIC/eICU (calendar dates obfuscated); needs a
real-date source (Premier/Vizient/a health-system EHR). Flag as the killer design IF data access is obtained.

## #4 — Time-of-draw instruments — TESTED, FAILED
Night (0–6h) draw ↑ repletion (0.086 vs 0.032) but is CONFOUNDED (mortality 3.9% vs 2.7% — sicker acute
draws). Weekend draw is balanced (mortality 3.0 vs 3.0) but IRRELEVANT (repletion 0.049 vs 0.048). Neither
works: relevant-but-endogenous or exogenous-but-irrelevant.

## #5 — Reframe to cleaner questions (fallbacks)
- **Over-repletion HARM in renal impairment** (cleaner causal direction: aggressive repletion → dangerous
  hyper-Mg/K → events). We found no threshold harm signal, but a renal-subgroup dose-response harm analysis is cleaner.
- **Low-value-care / practice-variation DESCRIPTIVE paper** (health-services): quantify the enormous
  variation + waste; honest, publishable, non-causal (JAMA IM Viewpoint / research letter).

## The RCT — RESTRAINT (the definitive guideline-setter; see full protocol below)
`docs/ELECTROLYTE_DEIMPLEMENTATION_RCT_PROTOCOL.md`. Pragmatic ward-level cluster-randomized non-inferiority
trial: conservative (auto-replete only Mg<1.5 / K<3.0 or symptomatic) vs standard (Mg<2.0 / K<3.5), carving
out proven indications (post-cardiac-surgery, torsades/long-QT, digoxin, severe/symptomatic). Co-primary =
new-onset clinically-significant arrhythmia + in-hospital mortality; NI margins 2.0 / 1.5 pp; ≈25,000 patients
across ≈160 ward-clusters (80/arm, ~15–20 hospitals), 18–24 mo; waiver of consent + always-available override;
GLMM with ward random intercept; blinded outcome adjudication. This is the NEJM/JAMA guideline-setting study.

## Recommended plan
Run the **provider-preference IV within-service** next (the one creative angle with a real first stage) — if
it survives the exclusion-restriction check, it is a genuine causal estimate that (with the RESTRAINT protocol
as the definitive trial and the "observational methods fail" methods point) makes a high-impact package. Add
**Mendelian randomization** as the complementary germline-randomized angle. Both are runnable now.
