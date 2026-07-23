# Verification Report for PROPOSAL.md (Draft v0.1 → v0.2)

**Date:** July 23, 2026. **Method:** Four background research agents (two paper audits and a prior-art search on Sonnet, arithmetic checks on Haiku) fanned out over the primary sources, followed by an independent cross-verification pass by the coordinating model (Fable): re-derived all arithmetic from scratch and checked the extracted Polymath15 Table 1 against two internal identities. Primary sources fetched directly: arXiv:1904.12438 (Polymath15, full PDF), arXiv:2004.09765v1 (Platt–Trudgian, full PDF). No GitHub repositories were browsed.

## Headline verdict

**The proposal's mathematical basis is sound.** The hypothesis ledger (Section 2) is confirmed verbatim against the published Polymath15 Table 1. The Platt–Trudgian claims are confirmed against the published paper, which itself explicitly anticipates this project's move ("The next entry in Table 1 … conditional on taking H a little higher than 10¹³ … would enable one to prove Λ < 0.19"). The prior-art premise holds as of July 2026. **One quantitative claim in Section 4 is wrong (the "~7.5× per rung" ladder figure) and one Gap-B sentence overstates what §8.4 literally says; both are corrected in v0.2.**

## Verified claims

### Hypothesis ledger (Section 2) — CONFIRMED verbatim

Polymath15 Table 1 ("Conditional Λ Results", §10) row 3 reads exactly: X = 2×10¹³ + 131,252, t₀ = 0.180, y₀ = 0.14142, Λ = 0.19, winding number 0, N₀ = 1,261,566, |f_t| lower bound 0.0349. Theorem 1.2's hypotheses match the proposal's statement exactly, including the strip (1+y₀)/2 ≤ σ ≤ 1 and the height 0 ≤ T ≤ X/2.

**Independent cross-check (Fable):** all 12 extracted rows satisfy Λ = t₀ + y₀²/2 to 5 decimal places, and all 12 satisfy N₀ = ⌊√(X/4π)⌋ to the integer (the Riemann–Siegel length identity). A misread X, N₀, t₀, or y₀ in any row would break these identities; none does. Row 3's X/2 = 10,000,000,065,626 = 10¹³ + 65,626 exactly (the proposal's endpoint T). Row 12's X/2 = 4.5×10²¹, matching the paper's prose statement for Λ ≤ 0.10.

### Platt–Trudgian claims (Section 1) — CONFIRMED

- Height exactly 3,000,175,332,800; exactly 12,363,153,437,138 zeros (Theorem 1) — "roughly 1.236×10¹³" is right.
- Method as described: sign changes of the completed zeta function, a variation of Turing's method, and code rewritten from MPFI to **Arb ball arithmetic** (explicitly stated, with a ~50% space saving cited as motivation). Base algorithm from Platt, Math. Comp. 86 (2017). They deliberately did not finely isolate zeros (default sampling ≈ 0.01 isolates 999,997.5 per 10⁶ zeros).
- Λ ≤ 0.2 is their Corollary 2, assembled exactly as the proposal describes, in April 2020 (arXiv v1: 21 Apr 2020). Nuance: they state the required threshold as **H > 2.51×10¹²** (a conservative rounding of row 2's X/2 = 2,500,000,097,429 ≈ 2.5×10¹²), with the footnote "X in Table 1 corresponds to 2H."
- New datum for the cost model: the computation used **7.5 million core-hours** on 3.6 GHz Xeons (~856 core-years); each GHz-hour processed ≈110,000 units of half-line. Gourdon's non-rigorous run was ~725× cheaper per unit height (sampling 1.2/zero vs 25/zero; hardware floats vs rigorous multiprecision).

### Arithmetic (Section 3, Gap A) — CONFIRMED

Riemann–von Mangoldt (main terms + 7/8) reproduces Platt–Trudgian's exact zero count to 5 significant figures, validating the formula. N(10¹³+65,626) ≈ 4.312×10¹³; new zeros ≈ 3.076×10¹³; ratio to the whole Platt–Trudgian computation ≈ 2.49 ("about 2.5×" ✓); cumulative ≈ 3.49 ("roughly 3.5×" ✓); height ratio 3.33 ✓; t₀ + y₀²/2 = 0.19000 exactly ✓; (1+y₀)/2 = 0.57071 exactly ✓. Independently computed twice (Haiku agent, then Fable re-derivation); results agree.

### Prior art (Section 5, Step 0) — CONFIRMED as of July 2026

Λ ≤ 0.20 and the 3×10¹² rigorous verification are still the records; Rodgers–Tao Λ ≥ 0 still stands (Dobner 2020 re-proved it by another route; no improvement is possible short of resolving RH); Gourdon 2004 is correctly characterized as non-rigorous (Odlyzko–Schönhage, floating point); no active or announced verification-extension project was found (ZetaGrid defunct since 2005, Polymath15 dormant). Caveat: search indexes may lag very recent postings — Step 0's "re-check immediately before launch" remains necessary. **Step-0 hygiene note:** at least one AI-generated content-mill page (mathlumen.com, "RH: A 2026 Status Report") circulates fabricated record claims (verification to 2×10¹³; "Λ < 10⁻¹²"). Record checks must use primary sources only.

## Corrections applied in v0.2

1. **Section 4, ladder steepness — REFUTED as written.** "Roughly 7.5× more verification per additional 0.01 of Λ on average" matches no consistent computation. Correct figures (zero-count basis, from confirmed Table 1 heights): the 0.20→0.19 rung is ≈4.2×; the next rung 0.19→0.18 (height 3×10¹³) is ≈3.1×; the geometric average from 0.19 down to 0.10 (height 4.5×10²¹, 9 rungs) is ≈9.7× per 0.01. The ladder is *gentler* than claimed at the next rung and *steeper* than claimed on average — the growth accelerates sharply at lower Λ, consistent with exp(O(1/Λ₀)).
2. **Section 3, Gap B wording — overstated.** Polymath15 §8.4 does **not** state in prose that the Λ ≤ 0.22 barrier used "Arb ball arithmetic." The words "Arb," "ball arithmetic," and "Pari/GP" never appear in the paper; §8.4 cites "the directory `dbn_upper_bound/arb` in the github repository," and §7 separately cites a `dbn_upper_bound/pari/...` file. This *strengthens* Gap B: even the headline barrier's arithmetic model rests on a directory-name citation. Also newly recorded, from §10's text after Table 1: all conditional barrier runs produced winding number 0, with mesh points at 20-digit accuracy except the two highest rows at 10 digits — so the Λ = 0.19 row was a 20-digit run, but the arithmetic model (ball/interval vs. float-with-manual-bounds) is unstated row-by-row.
3. **Section 1, threshold rounding — minor.** Platt–Trudgian state the row-2 requirement as H > 2.51×10¹² (their conservative rounding); the exact row-2 value is X/2 ≈ 2.5×10¹² + 97,429. The proposal's "2.5×10¹²" is essentially right but now carries the exact value.
4. **Section 1/4, additions.** Platt–Trudgian's own prose anticipating the Λ < 0.19 move is now cited (it is direct published support for the corollary's assembly); their 7.5M core-hour figure is added to Section 4 as an orientation anchor (floor ≈ 2.5× ⇒ order 19M core-hours of equivalent work before overheads — Step 4 pricing still governs).

## Residual uncertainties

- The row-by-row toolchain question (Gap B) is confirmed **open** — the paper is genuinely silent; only the Polymath participants can resolve it. This validates keeping Step 5 in the gate.
- The Λ = 0.22 headline result is *not* a Table 1 row (Table 1 is exclusively conditional results, starting at Λ ≤ 0.21); it is Theorem 1.1, proven via Platt's 3.06×10¹⁰ verification with t₀ = 0.2, y₀ = 0.2 at X₀ = 6×10¹⁰ + 83,952. The proposal's phrasing ("headline Λ ≤ 0.22 barrier") is compatible but this distinction is worth keeping in mind when talking to reviewers.
- Search-index lag means the prior-art all-clear is as of the tools' index dates, not literally today; Step 0 re-check before launch stands.
