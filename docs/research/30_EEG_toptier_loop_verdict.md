# EEG top-tier loop — verdict and decision memo (2026-07-10)

**Directive:** "find an EEG-based NEJM/JAMA/Nature-tier idea by putting ideas through the loop until one works."
**Honest result:** the loop ran every reachable EEG angle and the bottleneck-removers. All capped at the same two
root gates. A top-tier EEG finding is **not reachable with current compute + data access**; the reachable EEG win is
an Anesthesiology/A&A-tier measurement note. This memo documents the map so the next move is an informed choice, not
another spin on a capped idea.

## What was tried and why each capped (this session + prior)
| Angle | Best result | Ceiling / kill reason |
|---|---|---|
| IIC binary classifier (GPD/LPD vs slowing), CBraMod embed | cross-site AUC 0.75 | me-too; CBraMod 0.75 ≈ classical DSP 0.74 (no model win) |
| IIC morphology → mortality (outcome-anchored) | within-GPD/LPD ~0.59 | **generic encephalopathy severity** — neg-control slowing pattern predicts death *better* (0.73) |
| Seizure prognostication, CBraMod +0.067 over age | 0.591→0.654 | **ascertainment**: monitoring-intensity alone predicts 0.83; +0.067 → +0.001 after adjustment |
| BIS occult burst-suppression (reclassification) | age gradient 0.4→15.9% | **circular reference** (BIS blends BSR; same-device); known age-EEG physiology; no delirium outcome; raw-EEG confirm failed (r=−0.386) |
| ComBat / CORAL harmonization (bottleneck-remover) | — | **fails & backfires**: site-probe 0.71→1.00, class AUC 0.74→0.61 (leakage is higher-moment, not batch) |
| "Confound as finding" methods paper | — | **refuted**: under class-balanced design, cross-site signal ⊥ site; not confounded |

## The two root gates (everything traces here)
1. **No GPU.** Frozen CBraMod never cleanly beat 48 classical DSP features on any clinical outcome. Without
   fine-tuning (LoRA/full), the foundation model can't earn a top-tier *model* claim — it's me-too or classical-equivalent.
2. **No external EEG+hard-outcome+2nd-site dataset.** No NEDC/TUH key → TUSZ unreachable; VitalDB has no delirium;
   HEEDB is site-confounded (and unharmonizable — see ComBat result). Top-tier requires external validation, which is blocked.

## The single cleanest discriminator (why C8 won and EEG capped)
The winning measurement-reclassification template needs an **INDEPENDENT gold-standard reference**. C8
(cuff-misses-hypotension, Anesthesiology-tier, submission-ready) works because the **arterial line is a physically
independent instrument** from the cuff. Every EEG depth-monitor idea caps because its reference is a **same-device
sub-parameter** (BIS vs SR/SEF, all from one monitor, algorithmically coupled). No independent gold standard for an
EEG-derived clinical call exists in the reachable data.

## What unblocks the next tier (decision fork)
- **GPU access** → fine-tune a foundation model to try to beat classical DSP + clinicians on a real outcome (the
  core top-tier-*model* requirement). Cheapest concrete step: LoRA/last-layer on the IIC + seizure tasks.
- **TUH/NEDC key** → external validation on TUSZ (2nd site, seizure annotations); makes a cross-site EEG→outcome
  claim testable. This is the CLAUDE.md-named white space (first cross-site-validated EEG-FM→outcome study).
- **A delirium-linked intraop-EEG dataset** (e.g. ENGAGES/public) → makes the BIS-suppression *consequence* testable
  with an *independent* outcome, lifting it above technical-note tier.
- **Bank + pivot** → C8 (cuff) is submission-ready Anesthesiology-tier; stop forcing EEG and redirect the loop to
  non-EEG ideas where an independent reference + hard outcome exist.

## Recommendation
Bank C8 now (real, hardened, submission-ready). For EEG top-tier, open the **TUH/NEDC** gate first (cheapest path to
the named white space) or **GPU** (for the model-win path). Continuing to run observational EEG variants in-environment
is negative-EV — the confounds (severity, ascertainment, site) are fundamental to observational EEG-outcome work and
require a design change (randomization / independent reference / external site), not another feature set.
