# Red-team Round 1 — synthesis (control-theory vasopressor-requirement paper)

Four-reviewer adversarial panel on the SELECTED primary finding (the highest-impact pick from
IDEAS_LEDGER.md): the control-theory vasopressor-requirement trait paper. Lenses: statistics,
causal inference, clinical novelty/editor (with PubMed prior-art), independent reproduction.
Per-reviewer docs: RED_TEAM_ROUND1_{STATS,CAUSAL,NOVELTY,REPRO}.md.

## The single most important result of Round 1 (strategic)
**The dose→mortality framing is NOT novel — it is the VIS literature.** PubMed prior-art (novelty
reviewer): the Vasoactive-Inotropic Score has a 2024 meta-analysis (58 studies, ~30k patients,
OR 1.08/unit → mortality/AKI); Roberts 2020 already did prospective NEE→mortality (adj OR 1.33/10
µg/min); Saugel BJA 2025 did intraop norepi→AKI (n=38k). Submitting "vasopressor load predicts death"
as the headline = **desk reject**.

**What IS novel (must become the lede):** the **reliability / TRAIT framing** — nobody has
characterized the vasopressor requirement's split-half/test-retest reliability as a *stable patient
phenotype*; plus the control-theory inferential step *with data* (MAP CV 0.09 ≪ dose CV 0.44), the
landmark prospective design defeating reverse-causation at scale, the negative-control-exposure
falsification, and the concordance-null. → **Reframe:** lead with "is the vasopressor requirement a
stable, reliable trait?" (unanswered by prior art); dose→mortality is the *consequence*; confront VIS
head-on in the intro. Realistic tier: **Anesthesiology** conditional on this restructuring; **BJA / A&A**
without it.

## Findings, verdicts, and what was done
| ID | Reviewer | Issue | Sev | New? | Resolution |
|---|---|---|---|---|---|
| C1 | causal | Cross-cohort estimand seam: control-theory mechanism is VitalDB MAP-conditioned; the prospective mortality result is MIMIC MAP-*unconditional* → mechanism not evidenced for the quantity carrying the headline | CRIT | NEW | **DECOUPLED** in framing: mechanism (controller-effort) is a VitalDB claim; MIMIC carries "dose-ORDERING is a reliable, prospectively mortality-graded trait" WITHOUT the MAP-conditioned mechanism. Stated, not blurred. |
| C2 | causal | Propofol negative-control is a collider (restricted to norepi∩propofol; propofol titrated to RASS not MAP) | CRIT | NEW | **DEMOTED** to exploratory specificity analysis; confounding re-anchored on E-value + within-severity (8/8) + homogeneous restriction. |
| C3 | causal | Landmark OR 2.27 only age+lactate-adjusted; E-value ~6 does not transport | CRIT | NEW | **RAN full adjustment** (age+lactate+creatinine+bilirubin+platelets+comorbidity): landmark OR **1.74 [1.57, 1.91]** (n=4,260); **E-value 2.31 point / 2.11 CI-LB**. Cite ~2.1–2.3, not 6. (FINDING4_LANDMARK.md) |
| S1 | stats | MIMIC reliability 0.95 may be inflated by repeat-stay clustering | CRIT | NEW | **DEFEATED** by repro: first-stay-per-subject r=0.9476 (vs 0.9467) — no inflation. |
| S2 | stats | Landmark 2.57→2.27 might be selection, not lactate | CRIT | NEW | **REFUTED**: age-only OR within the lactate subset is **2.649** → lactate genuinely attenuates to 2.27 (real adjustment). |
| S6 | stats | Lactate anchored to hospital admittime+24h, not ICU intime+24h | MOD | NEW | **DISCLOSED** (possible mild under-adjustment for ward-to-ICU transfers); concurrent-ICU-lactate rebuild = future work. |
| S3 | stats | Landmark bootstrap resamples stays not subjects | MOD | PARTIAL | **DEFEATED** by repro: subject-clustered CI [2.443,2.691] vs stay [2.447,2.690] — ~2% wider, OR unchanged. Disclosure sentence added. |
| S4 | stats | SOFA approximation (no GCS/PaO2-FiO2) → full SOFA could attenuate to 1.9–2.1 | MOD | PARTIAL | Partly **closed** (lab SOFA components now in the full-adjust model → 1.74); residual GCS/PaO2-FiO2 gap disclosed (needs chartevents). |
| N1 | novelty | Dose→mortality is VIS (desk-reject risk) | CRIT | NEW | **REFRAME** to reliability-first + confront VIS (above). |
| REPRO | repro | Independent re-derivation | — | — | **All headline numbers reproduce exactly**; no data-integrity hole. |

## Net effect on the claim (corrected, hardened)
1. **Lede = reliability/trait** (the novel construct), control-theory as the *why*, dose→mortality as
   the *consequence*; VIS explicitly differentiated.
2. **Prospective number corrected**: fully-adjusted landmark OR **1.74 [1.57, 1.91]**, E-value ~2.1–2.3
   (was citing the non-transportable ~6). Still survives — CI excludes 1, monotone, reverse-causation
   defeated by design.
3. **Mechanism scoped to VitalDB**; MIMIC carries the trait + prospective grading, not the controller-
   effort mechanism.
4. **Confounding argument re-anchored** on E-value + within-severity + homogeneous restriction (propofol
   negative-control and prescribing-preference IV both demoted to exploratory).
5. Reliability robustness (subject-clustering), reproduction, and the S2/S3 checks all **pass**.

## Verdict after Round 1
No fatal hole. Two CRITICAL items were *empirically resolved by new analysis* (C3 full adjustment,
S2 selection check) and two by reproduction (S1, S3). The remaining CRITICALs (C1 estimand seam, C2
propofol, N1 novelty) are resolved by **honest reframing/scoping**, not by weakening the data. The
prospective effect is smaller than first stated (1.74 vs 2.27 fully adjusted) but real and now correctly
bounded. → Proceed to Round 2 to attack the *reframed* (reliability-first) claim and the new fully-
adjusted numbers with fresh adversaries.
