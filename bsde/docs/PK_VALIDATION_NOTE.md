# Validating the propofol kinetics — what passed, what failed, and what it means for the depth marker

*Result of `bsde/scripts/validate_pk_against_pump.py` on 145 VitalDB cases, 2026-08-01. The reference is
the infusion pump's own effect-site concentration, never BIS (`PKPD_MODEL_REVIEW.md` §6.2).*

---

## 1. What was tested

`Orchestra/PPF20_RATE` (what the pump delivered) → our model → compare against `Orchestra/PPF20_CE` (what
the pump computed). No EEG anywhere in this loop, which is the point: it asks only whether we turn an
infusion record into a concentration the way a TCI device does.

Metrics are Varvel's (PMID 1588504, verified from the MEDLINE record), medians across cases.

---

## 2. Two checks passed cleanly

**The input is read correctly.** Integrating the rate segments reproduces the pump's own cumulative volume
at **0.159 % median relative error**, 133 of 145 within 2 %. That validates the zero-order-hold reading of
the rate track — a pump rate is held between updates, and treating it as linear interpolation or as
per-sample boluses would both be wrong, in opposite directions.

**The function space is right.** Per case, in sample, the 8-rate exponential basis reproduces the pump's
effect-site model at **R² = 0.9990** (p10 0.9783; 134 of 145 above 0.95). This is the claim
`bsde/src/bsde/pkpd/propofol.py` makes — that a sum of exponentials contains any linear compartment model —
tested against a **real TCI device driven by a real infusion record**, not against the synthetic ODE
integration in `tests/test_pkpd_basis.py`. It is in-sample on purpose: the question is whether the function
space is adequate, and that is a different question from whether one kernel transfers between patients.

---

## 3. One check failed, and the failure is informative

**A single fixed kernel does not transfer across patients.** Fitted on training cases and scored on cases
never seen:

| arm | MDPE (bias) | MDAPE (inaccuracy) | wobble | divergence %/h |
|---|---|---|---|---|
| slowest kernel only (reference) | −48.07 | **53.81** | 9.15 | +0.19 |
| full 8-rate basis | −49.39 | **54.89** | 10.11 | +0.63 |
| basis × demographic covariates | −54.02 | **66.03** | 10.78 | +0.86 |

Three things to read here.

**Wobble is ~10 % while MDAPE is ~54 %.** The *shape* within a case is right and the *scale* is wrong. This
is a systematic offset between patients, not a kinetic failure — consistent with the per-case R² of 0.9990.

**Eight kernels buy nothing over one.** 54.89 against 53.81. Whatever a fixed global kernel can capture,
the slowest exponential already captures.

**Adding demographic covariates made it WORSE** — 66.03 against 54.89. That is rule 17's shape: a fix that
makes things worse means the diagnosis was wrong. Weight, age, height and sex, entered as multiplicative
scale modifiers on every kernel (40 columns fitted on ~115 effective observations), do not explain the
between-patient scale variation; they add variance.

**This replicates E121 on a completely different target.** E121 found that elaborating the *exposure* made
EEG tracking worse on VitalDB. Here elaborating the *PK model* makes pump-Ce prediction worse. Elaboration
has now failed to pay twice, against two unrelated references.

An earlier run reported MDAPE 69.2 %; the difference is one repair, stated (rule 58). Records run from 176
to 4,797 evaluation points, so an unweighted pooled fit let a 9-hour case outvote 27 short ones. Weighting
each case equally took MDAPE from 69.2 to 54.9 and left the conclusion unchanged.

---

## 4. What this changes about the depth-marker work

**For VitalDB, use the pump's own Ce and not ours.** The transfer arm measures exactly the error we would
be injecting by substituting our model, and it is ~54 % MDAPE against a reference that is free and already
in the deposit. There is no argument for the substitution. Our model's value on VitalDB is as the *check*
that was just run, not as the exposure.

**For DOSE-I there is no pump, and the per-case result is what licenses the model there.** E122 fits the
basis weights inside the analysis, out of bag by recording, which is the per-case regime the R² = 0.9990
result speaks to — not the cross-patient transfer regime that failed.

**The failed arm is not the individual sensitivity the EEG is supposed to measure, and must not be
presented as it.** The scale variation here is variation in *the pump's model output* driven by *the pump's
covariates*. True PD sensitivity is a different quantity and this experiment says nothing about it.
Conflating the two would be the most attractive available mistake, so it is written down here.

---

## 5. Two limits that were stated before any number existed

1. **The pump's model is not named in the deposit**, so this measures agreement with whichever model the
   Orchestra implements, not agreement with truth. A disagreement is therefore ambiguous — but the
   agreement in §2 is not, because reproducing an unknown three-compartment model from its input alone is
   exactly what the exponential-basis argument predicts, and failing to would have refuted it.
2. **The pump's Ce is a model output, not assayed blood.** No deposit this project can reach has measured
   propofol concentrations. This validates against a reference implementation, which is weaker than
   validating against blood and is the strongest available here.
