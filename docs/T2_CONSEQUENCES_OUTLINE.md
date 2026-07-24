# T2 Consequences Paper — Outline (Tier 2 look-ahead)

**Source audit:** Johnston, arXiv:2109.02249 (Ramanujan J.) read in full by research agent, July 2026; dependency currency checked against 2021–2026 explicit-estimates literature. This outlines the paper that becomes writable the day Tier 1's verification lands.

## Headline expected results (H = 10¹³ + 65,626 replacing T = 3×10¹²)

- Criterion constant: 9.06 → **8.94** (Johnston's own Table 1 already tabulates the T₀ = 10¹³ row — our H differs from 10¹³ by 6.6×10⁻⁹ relatively, invisible at published precision).
- Validity range for |π(x)−li(x)| < (√x/8π)log x and the ψ/θ/Π analogues: x ≤ 1.101×10²⁶ → **x ≤ 1.335×10²⁷** (~12.1×, tracking H² times slow log factors).
- Weakened-constant family (Thm 4.1/Table 2 analogues): all rows scale ~11–13×; e.g. a=1 row 2.165×10³⁰ → ~2.5×10³¹. Requires rerunning Johnston's iterative fixed-point optimization (the paper's real technical work — hand-tuned constants, 3 convergence rounds; automate or replicate carefully against Table 1 as ground truth).
- Ramanujan inequality endpoint (exp(103)) moves modestly; **check arXiv:2408.02591 / 2407.12052 first** — they may already close the gap unconditionally, shrinking this section.

## Mechanism (what H touches and what it doesn't)

H enters solely through Büthe's criterion (≈ (8.94/loglog x)·√(x/log x) ≤ T) gating where RH-is-known applies to the zero-sum split. **Unchanged by H:** the unconditional tail bounds (Fiori–Kadiri–Swidinsky 2023 ψ and π−li; Johnston–Yang 2023), the ψ−θ correction (Broadbent et al. 2021), the Σ1/|Im ρ| bound (Brent–Platt–Trudgian 2021), and — critically — **Λ ≤ 0.19 contributes nothing here**: no literature bridges a de Bruijn–Newman bound to explicit prime-counting estimates (Weil-formula/Laguerre–Pólya toolkit is disjoint from Büthe smoothing). The paper must say so plainly (a short expository section at most).

## Structure and risk register

§1 intro (low) · §2 lemma inventory with H-independence table (low) · §3 main theorem via rerun fixed-point (medium-high; **hotspot 1**: hand-tuned constants compound across iterations — automate the optimization) · §4 Table 2 rerun + possibly new a-grid rows (medium) · §5 stitch to unconditional regime — new vs Johnston (low-medium; **hotspot 2**: the conditional/unconditional crossover point must be computed, not assumed at x_max) · §6 Ramanujan application (medium/high compute; **hotspot 3**: brute-force step size δ must be re-justified over the longer interval) · §7 optional honest Λ remarks (low, but reputation-sensitive) · §8 future work.

Full dependency list (15 items) in the research record; newest superseding inputs: FKS arXiv:2204.02588 & 2206.12557, Johnston–Yang arXiv:2204.01980.

## Related Tier 2 result banked this session

The Lehman–Brent block-count corollary generalized to Trudgian-II's 3-term bound — algebraically exact against both published instantiations, implemented as `required_blocks_t14_provisional` in `verification/rs_verify.py`, worth one Gram block at g_p = 10¹³ (6 vs 7). Status: provisional — the generalization is valid iff Brent's 1979 proof uses the Turing bound only as a scalar at the top endpoint (all structural evidence says yes: Trudgian's own uniform-in-t₁ formulation, Booker 2006's parallel decomposition, and the zero-constant-term algebra); Brent 1979 and Lehman 1970 are paywalled, so primary confirmation needs library access or the H4 contacts. Until then production certification uses max(published, provisional) = published.
