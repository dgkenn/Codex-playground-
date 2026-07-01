# Findings ledger — HEEDB EEG-foundation-model research machine

Running log of experiments + hostile-review verdicts. Status: PROVISIONAL (not gated) / GATED-NULL
(ran the hostile-review gate, no finding) / SURVIVED (passed gate + external validation) / KILLED.

| # | Cycle | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|---|
| 1 | 1 | Novelty pre-screen: frozen EEG-FM → outcome, cross-site | No prior work combines FM + clinical outcome + multi-site external validation (DELPHI-EEG single-center) | — | white space confirmed |
| 2 | 1 | Design pre-mortem (hostile-review BEFORE running) | 3 CRITICALs: site confound; abnormal-EEG is solved+circular; use ICD/death not report | redesigned → cognitive-ICD primary + mortality secondary + site gate | design gate PASSED |
| 3 | 2 | **Gated cross-site: frozen CBraMod + attention-MIL, S0001↔I0002** (n=327) | **Site-probe embedding→hospital AUC 0.961**; cross-site abnormal 0.50/0.53 (in-sample 0.52); cognitive 0.62/0.58 (underpowered) | **FAILS site-invariance gate** (site-AUC 0.96 ≫ chance); outcome AUCs confounded + ~chance | **GATED-NULL** |

## Reading
- The machine's hostile-review gate is doing its job: it **refused to claim a cross-site finding** because
  the frozen embeddings encode hospital (AUC 0.96) → any outcome signal is site-confounded, and the frozen
  per-window MIL shows little usable outcome signal (in-sample ~chance/weak). This is the honest state.
- **The path forward is concrete** (LESSONS cycle-3 fixes): site-correction (`correct_sites.py`) with a
  published post-correction site-AUC ≤ ~0.6 gate; fix class/outcome balance; then re-test. If corrected
  site-invariant frozen embeddings still underperform, that is itself a publishable methods result
  (frozen EEG-FM insufficient for cross-site clinical outcome → fine-tuning required).
- No over-claim anywhere. Every step committed + logged.
