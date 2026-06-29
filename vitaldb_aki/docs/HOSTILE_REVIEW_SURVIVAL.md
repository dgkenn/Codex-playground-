# Hostile-review survival map (paper-level)

Every reviewer attack we could think of, the test that answers it, and an honest verdict.
SURVIVES = attack defeated. SURVIVES-WITH-CAVEAT = holds but with a stated limit. HONEST
LIMITATION = the attack lands; we disclose and scope. DID NOT SURVIVE = claim retracted.

## The claim after this pass (scoped to what survived)
> The **early intraoperative/ICU vasopressor dose-REQUIREMENT** (a simple per-kg dose metric)
> is a **reproducible, early-identifiable patient signal** that predicts the patient's later
> requirement and strongly stratifies mortality. It is **drug-agnostic** (norepi + phenylephrine)
> and **externally replicated** (INSPIRE OR + MIMIC-IV ICU, n>16k). It is grounded in a
> control-theory observation: intraoperative MAP is feedback-regulated, so the hemodynamic
> insult is carried by the dose, not the (held-normal) pressure. It is **NOT** shown to be
> vasoplegia-specific, it does **NOT** improve outcomes when acted on (no decision-benefit), and
> it lives in an already-on-pressor, arterial-line-monitored population.

## Attack -> defense -> verdict

| # | Reviewer attack | Test / evidence | Verdict |
|---|---|---|---|
| 1 | **Multiplicity / "you tested dozens of things"** | Findings ledger; ONE pre-specifiable primary; early->late p=6.8e-6, reliability p=3.4e-14 both survive Bonferroni(~30 tests, alpha 0.0017) | **SURVIVES** |
| 2 | **"Just sick/old patients need pressors"** | Incremental over clinical: age/ASA/weight/baseline-MAP predict late requirement OOF -0.01 (useless); +early signal -> +0.19 | **SURVIVES-WITH-CAVEAT** (no CV-lift over *early MAP*, which is itself predictive; selected sicker cohort) |
| 3 | **Cherry-picked phenotype definition** | Reliability 0.73-0.85 + 3.3-4.0x spread across MAP bands [50,75]/[55,80]/[60,85] x min-epochs {2,3} | **SURVIVES** |
| 4 | **Single-centre (SNUH/VitalDB)** | External: INSPIRE OR trait-across-ops 0.32 (n=218); MIMIC-IV ICU reliability 0.95, early->late 0.62 (n=15,949) | **SURVIVES** |
| 5 | **Reliability is trivial autocorrelation of a flat infusion** | ICC 0.39 (MIMIC)/0.21 (VitalDB); time-gapped early->late survives multi-hour gaps (0.59->0.51 at >=6h->0.30 at >=24h); shuffle-null ~0; holds in high-CV (non-flat) subset (0.35) | **SURVIVES** (part is persistence; a real between-patient trait remains) |
| 6 | **"You call it VASOPLEGIA but never proved it"** | Convergent vs real tone (diastolic/MAP) -0.03; discriminant vs PPV/preload +0.38 (stronger); SVR anchor +0.14 n=15 (wrong sign) | **HONEST LIMITATION** -> relabel as *vasopressor requirement*, not vasoplegia; mixed preload+tone mechanism |
| 7 | **Mortality is just illness severity** | OR per SD 3.80 (age-adj) -> **3.01** (adj n-vasopressors+comorbidity+ICU-LOS), CI [2.72,3.37], only **28%** attenuation; +AUC 0.063 over severity | **SURVIVES-WITH-CAVEAT** (no lactate/SOFA -> upper bound; full score would attenuate further) |
| 8 | **It's not actionable / no benefit** | Concordance->outcome adjusted RD null & attenuates with N (-0.09->+0.08); interaction null (n=549) | **HONEST NULL** (disclosed: risk-stratification, not decision-benefit) |
| 9 | **The A-line gives orthogonal fluid-vs-pressor info** | Original "PPV _|_ tone r=-0.09" used a DEGENERATE tone column (map_dia_form_factor = 1/3 constant). Real tone -> r=+0.23 [0.15,0.30] | **DID NOT SURVIVE** -> retracted; axes are CORRELATED, not independent |
| 10 | **Hidden statistical bugs / leakage** | Adversarial code audit of 5 headline modules: no conclusion-flipping bug; found degenerate-tone (fixed, #9), circular +0.69 construct (relabeled), wrong-sign SVR (relabeled), in-sample operating point (relabeled) | **SURVIVES** (headlines reproduce; oversold supports cut) |

## What got cut by this pass (honesty record)
- **"Vasoplegia" label** -> "vasopressor requirement" (attack 6).
- **Lever discrimination "independent axes / A-line picks the lever"** -> retracted (attack 9); the lever line is now: axes are modestly correlated; ~57% of patients fall in a single-lever quadrant but no orthogonality and no outcome benefit.
- **"Pivot-2 tone carrier predicts requirement (-0.30)" unifying link** -> invalid (degenerate column); real tone ~-0.13 (near-null).
- **Construct-validity "+0.69 vs cumulative exposure"** -> circular (~+0.02 disjoint); dropped from the GO.
- **Decision-benefit** -> null (attack 8).

## What stands, hardened
Requirement is a **reliable (0.82-0.95), early-identifiable (AUC 0.77, early->late 0.5-0.6),
drug-agnostic, externally-replicated (OR+ICU, n>16k) patient signal that stratifies mortality
(adj OR 3.0)**, with a novel **control-theory** framing. Honest tier: a strong, defensible
characterization + risk-stratification paper -- not a demonstrated practice-changer.

Cross-ref: FINDINGS_LEDGER.md, AUTOCORRELATION_ATTACK.md, CONSTRUCT_VALIDITY.md,
MIMIC_MORTALITY_SEVERITY.md, STATS_CODE_AUDIT.md, EARLY_ID_ROBUSTNESS.md,
REQUIREMENT_SPECIFICITY.md, CONCORDANCE_OUTCOME.md, EXTERNAL_VALIDATION_INSPIRE.md,
MIMIC_EXTERNAL_VALIDATION.md.
