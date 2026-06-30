# Red-team Round 3 — synthesis (the occult-dependence finding)

Four-reviewer panel (stats/restriction+adjustment, causal/collider, novelty/PubMed, independent
reproduction) on the NEW finding (ICU_OCCULT_DEPENDENCE.md), enabled by the successful MIMIC chartevents
MAP pull (7.58 M MAP rows, 76,500 stays). Per-reviewer docs: REDTEAM_R3_{STATS,CAUSAL,NOVELTY,REPRO}.md.

## Verdict: SURVIVES — hardened to a defensible top-critical-care finding
Unlike Rounds 1–2 (which killed the trait framing), Round 3's deepest attacks were defeated *empirically*,
and the reframe is a sharpening, not a retraction.

| Attack | Result |
|---|---|
| **Collider bias** (conditioning on at-target MAP, a post-treatment node) — the make-or-break | **PASSED.** Fully-adjusted OR 1.84 at-target ≈ 1.68 not-at-target, interaction p=0.072 (NS). A collider artifact would elevate the OR only within at-target; it doesn't → not a selection artifact. |
| **Full severity adjustment within at-target** | **SURVIVES.** complete-case OR 1.84 [1.56,2.25], E-value 2.53; **MICE-pooled (full cohort n=7,836) 2.04 [1.85,2.24]** — informative-missingness resolved, complete-case was conservative. |
| **Restriction-of-range** (MAP within band) | MAP variance falls to 24% in-band → MAP AUC 0.47 is partly artifact. Requirement is NOT range-restricted (AUC 0.72→0.74). Reframe: lead with the requirement side + the across-stratum AUC gap, not "MAP is worthless." |
| **Invasive-only (art-line) sensitivity** | **STRONGER**: OR 3.10 [2.82,3.45], gradient 10.5× — signal larger where pressure is genuinely regulated, as the mechanism predicts. |
| **Prior art (VDI dose/MAP, BPRI MAP/VIS)** | **PARTIALLY NOVEL.** Must cite VDI (BEAT-SHOCK 2025) + BPRI (Shen 2026). Genuinely new = the at-target conditioning + the across-stratum AUC gap (0.156→0.268). |
| **Control-theory premise "closes causal Issue 1"** | **OVERCLAIM WITHDRAWN.** MAP CV < dose CV is partly a regulation identity; the real content is the *magnitude* (ICU MAP CV 0.125 confirms tight regulation), not causal information. |
| **Reproduction** | **EXACT.** Independent pipeline reproduces every headline number (the OR 2.26→2.82 gap was a NEE-load unit convention — now stated as mcg/kg-min). |

## The reframed claim (what goes in the paper)
Lead with the **information gap**: among ICU patients AT MAP target, the vasopressor requirement
discriminates a 9× mortality gradient (3.1%→27.8%) that the pressure cannot — the requirement-vs-MAP AUC
gap doubles once MAP is at goal (0.156→0.268). Fully-adjusted (MICE) OR 2.04 [1.85,2.24], E-value 2.5,
stronger in art-line patients (3.10). Risk-stratification, motivated as a monitoring-error caution —
not causal/decision-benefit. Cite VDI/BPRI; the novelty is the "at-target" conditioning.

## Remaining honest limitations (named, not fatal)
1. Confounding-by-indication within the at-target stratum (missing GCS/PaO2-FiO2/shock-etiology) — bounded
   by E-value 2.5, not eliminated; the five-front full-cohort defense should be reproduced for this subsample.
2. "At-target" is a post-treatment conditioning — collider addressed empirically (interaction NS) but the
   assumption should be stated.
3. Single-cohort (MIMIC-IV); external replication (eICU) is future work.
4. Lactate anchored to hospital admittime, not ICU intime (carried over from the landmark; S6).
5. Observational; landmark defeats reverse-causation temporally, not confounding.

## Target tier and next step
Critical Care Medicine / Intensive Care Medicine. The finding has survived its hardest round intact and
been strengthened (MICE 2.04, collider passed, invasive 3.10). → Round 4 will attack the REFRAMED claim
(the AUC-gap/monitoring-error framing + the prior-art differentiation + the within-stratum confounding
defense) to confirm convergence before declaring it 100% submission-ready.
