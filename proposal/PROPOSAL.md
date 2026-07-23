# RH to 10¹³, with Corollary Λ ≤ 0.19: Draft Project Proposal

**Status:** Draft v0.2, July 23, 2026. Produced from an AI-assisted literature reconstruction and one round of external review; v0.2 incorporates a source-level verification pass against arXiv:1904.12438 and arXiv:2004.09765 (see `VERIFICATION.md`). Requires expert sign-off (Gate Step 6) before any resource commitment. Nothing here is a claimed result.

## 1. Summary

The primary objective is a rigorous numerical verification of the Riemann Hypothesis for all nontrivial zeros with 0 < Im ρ ≤ 10¹³ + 65,626, extending Platt–Trudgian (2021), which certified RH to height 3,000,175,332,800 using Arb ball arithmetic, sign changes of the completed zeta function, and a Turing-method count — a computation covering roughly 1.236 × 10¹³ zeros. A verification to 10¹³ would be a significant computational number theory result in its own right and the natural successor to that paper.

The corollary objective, and the headline motivation, is a new world record for the de Bruijn–Newman constant. Row 3 of Table 1 in the Polymath15 paper (D.H.J. Polymath, *Res. Math. Sci.* 2019) records completed barrier and asymptotic verifications at X = 2 × 10¹³ + 131,252 which, combined with Theorem 1.2 of that paper, yield Λ ≤ 0.19 conditional only on RH verification to height X/2. The current record, Λ ≤ 0.20, was assembled in exactly this way in April 2020: Platt–Trudgian's Corollary 2 discharged the hypothesis of Table 1 row 2 (required height X/2 = 2.5 × 10¹² + 97,429; their paper states the threshold conservatively as H > 2.51 × 10¹²). This project performs the same move one rung down the ladder — a move Platt–Trudgian themselves point out: "The next entry in Table 1 … is conditional on taking H a little higher than 10¹³ … This would enable one to prove Λ < 0.19."

Following external review, the framing is deliberately: **primary theorem — RH holds to 10¹³; corollary — Λ ≤ 0.19.** This is cleaner for referees, correctly weights the scientific contributions, and makes the project worthwhile even if any subtlety were discovered in the corollary step.

## 2. Mathematical basis

Theorem 1.2 of Polymath15 states that Λ ≤ t₀ + y₀²/2 provided three hypotheses hold: (i) no zeta zeros with (1+y₀)/2 ≤ σ ≤ 1 and 0 ≤ T ≤ X/2; (ii) an asymptotic zero-free region for H_{t₀} to the right of the barrier; (iii) a zero-free barrier region at X for all 0 ≤ t ≤ t₀. Hypotheses (ii) and (iii) for the target parameters are recorded as verified in Table 1 of the published paper. The frozen hypothesis ledger for this project is:

| Quantity | Value (Polymath15, Table 1, row 3) |
|---|---|
| Barrier location X | 2 × 10¹³ + 131,252 |
| Required verification height T = X/2 | 10¹³ + 65,626 |
| t₀ | 0.180 |
| y₀ | 0.14142 |
| Resulting bound Λ = t₀ + y₀²/2 | 0.19 |
| N₀ (Riemann–Siegel length at barrier) | 1,261,566 |
| Barrier winding number | 0 (recorded verified) |
| Lower bound on \|f_t\| in barrier | 0.0349 |

One refinement belongs in the ledger. Hypothesis (i) does not require full RH verification: it requires only zero-freeness in the strip σ ≥ (1+y₀)/2 = 0.57071 up to height T. Standard verification methodology (sign changes on the critical line plus a Turing count) certifies the stronger full statement anyway, and that is the recommended path; but the minimal hypothesis should be recorded, and reviewers should be asked whether any partial-verification technique changes the economics (most likely it does not).

## 3. Gap analysis — what is actually missing

**Gap A: the verification extension.** From 3.0002 × 10¹² to 10¹³ + 65,626. By the Riemann–von Mangoldt formula, N(3.0002 × 10¹²) ≈ 1.236 × 10¹³ (consistent with the count reported for the 2021 computation) and N(10¹³) ≈ 4.312 × 10¹³. The extension must therefore certify approximately **3.08 × 10¹³ additional zeros — about 2.5 times the entire Platt–Trudgian computation in new work, roughly 3.5× cumulative.** The naive height ratio of 3.33× understates the work: zero density grows logarithmically with height, and per-evaluation cost, checkpointing, storage of certificates, Turing-count boundary work, and independent auditing all add overhead that must be measured, not assumed (Gate Step 4).

**Gap B: rigor audit of the row-3 barrier.** The headline Λ ≤ 0.22 barrier computation is presented in §8.4, which cites its implementation only as "the directory `dbn_upper_bound/arb` in the github repository" — the words "Arb" and "ball arithmetic" appear nowhere in the paper's prose, so even the headline barrier's arithmetic model rests on a directory-name citation. The paper introduces Table 1 as numerical results verifying hypotheses (ii)–(iii) but does not state, row by row, which toolchain produced them (§10 records only that all barrier runs gave winding number 0 and that mesh points were computed to 20-digit accuracy — 10 digits for the two highest rows — so the Λ = 0.19 row was a 20-digit run of unstated arithmetic model); the project wiki's permanent zero-free-region record was last updated in May 2018, before the conditional rows existed; and the repository documents both Pari/GP and Arb implementations, recommending Arb for large-scale runs. Whether row 3 meets the ball-arithmetic standard of the published theorem must be confirmed with the Polymath participants. If it does not, re-running the row-3 barrier and asymptotic checks in Arb is a bounded sub-project — the paper notes barrier verification was fast relative to the asymptotic region even for the main theorem — but it changes scope and must be planned, not discovered mid-run.

## 4. Cost model

No core-year figure is quoted here, deliberately: the honest cost model is the empirical one produced at Gate Step 4. The structural facts are that rigorous isolate-and-count verification amortizes to roughly linear cost in the number of zeros with polylogarithmic factors, that the floor is ~2.5 Platt–Trudgian-equivalents of new certified zeros, and that engineering overheads (restartable distributed runs, corruption resistance, certificate retention, independent segment reproduction) multiply that floor by a factor to be measured. One published anchor exists: Platt–Trudgian report 7.5 million core-hours on 3.6 GHz Xeons for the 3 × 10¹² verification, so the ~2.5× floor implies on the order of 19 million core-hours of equivalent work before overheads and before any algorithmic or hardware differences — an orientation figure only, not a price; Step 4 governs. For scope discipline: the ladder beyond this rung steepens — by certified-zero count (heights from Polymath15 Table 1), the 0.19 → 0.18 rung (height 3 × 10¹³, 10× the current record) costs ≈3.1× this project, and the average from 0.19 down to 0.10 (height 4.5 × 10²¹) is ≈9.7× per 0.01 of Λ, the growth accelerating sharply at lower Λ consistent with the exp(O(1/Λ₀)) scaling. This project is strictly the 0.19 rung.

## 5. Reproduction gate

No large computation is purchased or launched until every step below passes.

**Step 0 — prior-art re-check.** Fresh literature and preprint search for any published Λ < 0.20 or any rigorous verification beyond 3 × 10¹². As of July 2026 the record tables still show 0.20 and 3 × 10¹²; given the current climate of large-scale AI-assisted computation, re-check immediately before launch — and simply ask Platt and Trudgian whether an extension is already running.

**Step 1 — hypothesis ledger.** Freeze Section 2's table against the published paper (exact row values, exact endpoint T = 10¹³ + 65,626), signed off by a computational number theorist.

**Step 2 — code custody.** Obtain or reconstruct the exact Platt–Trudgian verification implementation (their rewritten Arb-based code and zero-isolation algorithm) and the `dbn_upper_bound` Arb barrier code; reproduce the build environment and numerical assumptions.

**Step 3 — reproduction.** Reproduce a published lower-height segment of the 3 × 10¹² verification bit-for-bit or certificate-for-certificate before touching new heights.

**Step 4 — benchmarking and pricing.** Measure runtime, memory, storage, and precision behavior at several increasing heights; fit empirical cost scaling; price the full run with contingency.

**Step 5 — rigor audit of Table 1 row 3** (Gap B above); if needed, re-run the barrier and asymptotic checks in Arb and archive the certificates.

**Step 6 — expert review.** Have Platt, Trudgian, and/or Polymath15 participants (T. Tao; repository maintainers) review the complete plan before launch. This is simultaneously the courtesy step: the natural authors of this result are the people whose pipeline it is, and the best version of this project is plausibly a collaboration.

## 6. Deliverables and publication plan

Primary paper: a rigorous verification of RH to 10¹³, in the style of the 2021 Bulletin of the LMS paper, with archived certificates, audit data, and independently reproduced segments. Corollary (same paper or companion note): Λ ≤ 0.19 via Polymath15 Theorem 1.2 and Table 1 row 3, with the Gap-B audit outcome documented explicitly. Artifacts: reproducible build, distributed-run logs with checkpoints, and a public record page updating the Polymath wiki.

## 7. Risks

The dominant risk is engineering scale, not mathematics: distributed rigor at tens of trillions of certified zeros is an infrastructure problem with real failure modes (silent corruption, checkpoint loss, unaudited segments). Cost risk follows from the same uncertainty and is bounded by refusing to launch before Step 4 pricing. Scooping risk is real and is converted into de-risking by Steps 0 and 6 — early contact either reveals a running effort or recruits its natural collaborators. Gap B is a bounded scope risk. Finally, the honesty constraint that frames the whole effort: this project improves a quantitative bound with a fully specified finite computation; it does not materially approach Λ = 0. The method's own authors show verification of Λ ≤ Λ₀ costs time exp(O(1/Λ₀)), so the road this project walks reaches 0.19 and, by design, stops there.

## 8. References

D.H.J. Polymath, *Effective approximation of heat flow evolution of the Riemann ξ function, and a new upper bound for the de Bruijn–Newman constant*, Research in the Mathematical Sciences 6 (2019); arXiv:1904.12438 — Theorem 1.2, Table 1, §8.4, §10, Remark 9.3. · D. Platt and T. Trudgian, *The Riemann hypothesis is true up to 3·10¹²*, Bull. London Math. Soc. 53 (2021), 792–797. · B. Rodgers and T. Tao, *The de Bruijn–Newman constant is non-negative*, Forum of Mathematics, Pi 8 (2020), e6. · `km-git-acc/dbn_upper_bound` repository (Arb and Pari/GP implementations; output records) and the Polymath wiki zero-free-regions page (permanent record through May 2018).
