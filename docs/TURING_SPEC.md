# Turing Method Specification (Step 3)

**Provenance:** Constants extracted directly from fetched PDFs of Trudgian, *Improvements to Turing's Method* (arXiv:0903.1885, Math. Comp. 80 (2011) 2259–2279) ["T11"], *Improvements to Turing's Method II* (arXiv:1406.3416) ["T14"], and *An improved upper bound for the argument of the Riemann zeta-function on the critical line II* (arXiv:1208.5846, J. Number Theory 134 (2014) 280–292) ["T14b"], July 2026. Cross-checks applied: Corollary 2.3's coefficients reproduce from Theorem 2.2 via b/6π = 0.059/(6π) ≈ 0.0031 and (a − b log 2π)/6π ≈ 0.104; the Theorem 2.2 constants independently match those quoted in Platt's 2017 paper (Theorem 4.2 there). The pseudocode shape is standard practice (Brent 1979, Booker 2006, Platt), not verbatim from the papers; every constant is individually cited.

## 1. Definitions

- **θ(t)** = Im log Γ(¼ + it/2) − (t/2) log π, continuous branch with θ(0)=0 (principal branch of lngamma suffices on Re > 0).
- **Hardy Z**: Z(t) = e^{iθ(t)} ζ(½+it); real for real t; its sign changes locate critical-line zeros unconditionally.
- **S(T)** = π⁻¹ arg ζ(½+iT) by continuous variation along 2 → 2+iT → ½+iT (symmetric limit at zero ordinates); N(T) = θ(T)/π + 1 + S(T); S jumps by +1 at every zero of ζ in the strip, on or off the line — this is what makes the method sensitive to off-line zeros.
- **Gram points** g_n: θ(g_n) = nπ. **Good** Gram point: (−1)ⁿ Z(g_n) > 0 (certified). **Gram block** (g_n, g_{n+p}]: bounded by good Gram points with no good Gram point inside. A block **conforms to Rosser's rule** when it contains exactly p certified sign changes. Rosser's rule fails infinitely often (Lehman) — conformance is a per-block computational certificate, never an assumption.

## 2. The certificate inequalities

**T11 Theorem 2.2:** for t₂ > t₁ > 168π, |∫_{t₁}^{t₂} S(t) dt| ≤ 2.067 + 0.059 log t₂.

**T11 Theorem 2.1 (Lehman–Brent form):** if N consecutive Gram blocks with union [g_n, g_p] all conform to Rosser's rule, and
N ≥ (b/6π) log² g_p + ((a − b log 2π)/6π) log g_p,
then N(g_n) ≤ n+1 and N(g_p) ≥ p+1.

**T11 Corollary 2.3 (with Theorem 2.2's constants):** the requirement becomes
**N ≥ 0.0031 log² g_p + 0.11 log g_p.**
(At g_p ≈ 2π·10¹², 6 conforming blocks suffice.)

**T14 Theorem 1 (sharper, for t₂ > t₁ > 10⁵):** |∫ S| ≤ 1.698 + 0.183 log log t₂ + 0.049 log t₂, with a table of (a,b,c) triples per decade 10⁵…10¹⁵ (at 10¹³: 1.792 + 0.178 log log + 0.046 log). Note: T14 does *not* republish the block-count corollary — re-deriving it with the 3-term bound is implementer work, flagged as such.

**Pointwise sanity bound (T14b Theorem 1):** |S(T)| ≤ 0.111 log T + 0.275 log log T + 2.450 for T ≥ e. (A circulating variant 0.112/0.278/2.510 could not be located in the primary source — do not use.)

## 3. Operational recipe

1. Scan Z's certified signs from below the first zero to a good Gram point g_n near the target height; count sign changes with escalating hidden-pair hunts; result: count ≥ (number of certified zeros below g_n).
2. Continue above g_n, splitting at good Gram points into Gram blocks; certify each block's exact sign-change count; accumulate N consecutive conforming blocks up to some good g_p.
3. Check N ≥ 0.0031 log² g_p + 0.11 log g_p **using the upper endpoint of a ball enclosure of the RHS**. If satisfied: N(g_n) ≤ n+1 (Theorem 2.1).
4. If the count from step 1 equals n+1: then n+1 ≤ N(g_n) ≤ n+1, so **N(g_n) = n+1 exactly — every zero of ζ with 0 < Im s ≤ g_n lies on the critical line** (the count includes all strip zeros; the located ones are all on-line).
5. Failure handling: a non-conforming block → refine (finer grid, higher precision) before concluding anything; persistent nonconformance → extend the scan (more blocks) or report failure with diagnostics.

## 4. Ball-arithmetic soundness rules

**Must be rigorous:** every sign used anywhere (ball excludes 0, else escalate precision — never assume); the RHS of the block-count inequality (evaluate in arb, compare against integer N conservatively); θ-related quantities feeding any inequality.
**May be heuristic:** grid placement, Gram-point location used for scan scheduling, block lookahead, parallelization — errors there cost performance, never soundness, because acceptance always re-checks certified signs.
**Pitfalls:** close zero pairs hiding between grid points (hunt adaptively where |Z| is small); Lehmer-phenomenon near-tangencies (legitimate precision escalation); a failed parity pattern usually means a missed sign change, not a Rosser failure.

## 5. Implementation status

`verification/rs_verify.py` implements §3 steps 1–4 with T11 Corollary 2.3 as the certificate inequality (adequate for prototype heights; switch to re-derived T14 constants for production heights ≥ 10⁵ where the sharper triple pays). The certificate applies at the largest good Gram point at or below the requested T.
