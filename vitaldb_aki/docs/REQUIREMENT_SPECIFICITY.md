# Requirement specificity / placebo / confounding hardening (lead-finding defense)

Hostile-review battery for the LEAD finding: the EARLY norepinephrine dose-REQUIREMENT predicts the LATE requirement (Spearman +0.54) and adds beyond clinical baseline (docs/EARLY_ID_ROBUSTNESS.md). Each case's TIME-ORDERED norepi-only epochs are split into an early half and a late half (cases with >= 4 epochs). NO new extraction.

- NEPI norepi-only cases: **75**; with >= 4 epochs (analyzable): **52**.

## Attack 1 -- Specificity / incremental over hemodynamics  (`weakened`)
Does early dose predict LATE requirement BEYOND early MAP & HR? (n=52)
- Raw early->late Spearman: **0.537** (p=0.0).
- **Partial Spearman controlling early MAP + early HR: 0.466** (n=52).
- Nested OOF: hemodynamics-only **0.217** vs hemodynamics+dose **0.17** (dose increment **-0.047**).
  _TWO legs. PARTIAL leg: dose must keep a rank association with the late requirement after removing early MAP & HR -- this is the specificity test (if it collapses the 'requirement' is just early BP/HR in a costume). OOF-INCREMENT leg: dose should also lift a cross-validated hemodynamics-only model. 'weakened' = partial survives but OOF does not add (the late requirement is partly forecastable from early MAP alone, and at N~52 the OOF leg is noisy); 'fails' = partial itself collapses._

## Attack 2 -- Placebo predictors  (`survives`)
Do early MAP / HR per se predict the late requirement? (they should be weaker)
- early DOSE -> late: **0.537** (p=0.0).
- placebo early MAP -> late: -0.404 (p=0.003).
- placebo early HR -> late: -0.009 (p=0.9473).
- |r| margin of dose over MAP 0.133, over HR 0.528.
  _early MAP & HR are placebo predictors of the late requirement. The dose-requirement should out-predict both by a clear |r| margin; if a placebo matches it, the early->late link is non-specific hemodynamic persistence, not a vasopressor-requirement trait._

## Attack 3 -- Case-mix robustness  (`survives`)
Early->late Spearman off the high-vasoplegia surgeries:
- full: **0.537** (n=52).
- excl liver-transplant (12 cases): **0.544** (n=40).
- excl cardiac/CPB-proxy aortic/aneurysm (2 cases): **0.547** (n=50).
- excl both: **0.557** (n=38).
  _the early->late link must hold OFF the highest-vasoplegia surgeries (liver transplant; aortic/aneurysm vascular as a CPB proxy -- VitalDB has NO true cardiac/CPB surgery). If it only exists because a few transplant/aortic cases anchor both ends, it is case-mix, not a trait._

## Attack 4 -- Selection bias  (`selected-sicker-subset (generalizes to monitored pressor patients only)`)
INCLUDED (>= 4 epochs, n=52) vs EXCLUDED pressor cases (n=23):
- age: incl 61.5 vs excl 72.0 (MWU p=0.1207).
- ASA: incl 3.0 vs excl 3.0 (MWU p=0.7693).
- weight: incl 56.1 vs excl 63.9.
- **composite-outcome rate: incl 0.706 vs excl 0.5** (rate ratio 1.41).
  _the analyzable subset requires >= 4 stable norepi-only epochs, i.e. sustained pressor support -> structurally enriched for sicker, longer-pressor patients. Reported honestly: the finding generalizes to ALREADY-on-pressor monitored patients, not to all-comers._

## Attack 5 -- Influence / jackknife  (`survives`)
Leave-one-case-out early->late Spearman (full 0.537, n=52):
- **jackknife r range: [0.512, 0.571]** (span 0.059).
- most influential case 5282 (r without it 0.571).
  _leave-one-case-out: if dropping any single case collapses the early->late Spearman, the finding rides on a few high-leverage patients. The min jackknife r is the worst-case; it should stay clearly positive._

## Summary
- Core attacks survived: **3/4 (attack4 bounds generalizability, not pass/fail)**.
- Verdicts: specificity `weakened`, placebo `survives`, case-mix `survives`, jackknife `survives`; selection: selected-sicker-subset (generalizes to monitored pressor patients only).

## Caveats (honest, small N)
- N is small: 52 cases with >= 4 epochs. Partial-correlation and nested-OOF estimates are unstable at this N; treat magnitudes as directional, not precise.
- VitalDB (SNUH) is a NON-cardiac surgical cohort: there is NO true cardiac/CPB surgery. The 'cardiac/CPB proxy' is aortic/aneurysm vascular surgery -- the closest high-vasoplegia non-transplant set -- stated as a proxy, not real CPB.
- Attack 4 BOUNDS generalizability rather than passing/failing the finding: the analyzable subset is structurally enriched for sustained-pressor (sicker) patients.
- All observational, single-centre; identifies WHO is vasoplegia-prone early, not that acting on it helps.
