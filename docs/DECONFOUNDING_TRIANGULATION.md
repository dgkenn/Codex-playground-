# G7 — Convergent partial-identification (triangulation bounds): the reviewer-proof packaging

**Purpose.** No single observational design for reflexive-care confounding is unimpeachable. Triangulation
converts a set of designs with *known bias sign* into a Manski-style **bracket** around the true effect, with the
assay-noise flag-ITT as the ~unbiased anchor. You report the INTERVAL, not one fragile point. Code:
`docs/triangulate.py`.

## The construction
Risk-difference scale, treatment→mortality:
- **HARM-biased designs** (`θ̂ ≥ θ`: sicker → more treatment → worse outcome): naive/IPTW, provider-preference-IV
  (habit ~ care intensity), within-patient FE (treated episode = sicker episode). → an **upper** bound on θ.
- **BENEFIT-biased designs** (`θ̂ ≤ θ`: treatment WITHHELD from the sickest — contraindication): renal-impairment
  / comfort-care / DNR strata where the frailest are not treated. → a **lower** bound on θ.
- **ANCHOR** (~unbiased, design-based): the assay-noise **flag-ITT**.

Bracket = `[ max(benefit-biased) , min(harm-biased) ]`; the anchor should sit **inside** (a falsifiable check).
Conservative variant widens to one-sided CIs. If the bracket excludes clinical benefit → de-implementation
supported; if it spans the null band → inconclusive, tighter designs needed.

## Worked example (illustrative, documented Mg estimates — replace with real-data outputs)
`triangulate.py` on IPTW +0.090, provider-IV +0.160, within-patient +0.070 (harm), renal-withheld −0.020
(benefit), anchor +0.002 →
- point bracket **[−0.020, +0.070]**, conservative **[−0.000, +0.054]**, anchor **inside ✓**,
- **DECISION: spans the null band → inconclusive.**

**Honest reading:** the bracket is wide because the harm-biased designs are far from zero — so triangulation
*alone* does not decisively exclude a small benefit. Its value is (1) the anchor-inside-bracket check
(falsifies gross anchor error), and (2) forcing the *bias-sign assumptions* into the open as the reviewable
claim. Decisiveness still comes from the anchor's own precision (the flag-ITT), not from the bracket.

## What makes it credible / where it can fail
- **Credible:** the harm-bias sign is nearly mechanical (sicker→treated→worse); the anchor-inside check is
  falsifiable; reporting the interval is honest about residual uncertainty.
- **Fragile:** the *benefit*-biased design is the weak link — "the sickest are withheld treatment" must be
  positively demonstrated in the chosen stratum (e.g., show treatment rate falls with severity there), not
  assumed. If no credible benefit-biased design exists, you only get an upper bound (still useful: "θ ≤ X").
- **Scale:** convert RR/HR estimates to a common RD scale at a stated baseline risk before bracketing.

## Status
Framework + estimator built and unit-exercised. Real bracket pending: the assay-noise anchor (from
`corrected_iv.py`) + a demonstrated benefit-biased contraindication stratum. This is the packaging layer, not
the source of decisiveness — that remains the flag-ITT.
