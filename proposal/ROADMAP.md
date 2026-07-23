# Max-Effort Roadmap: From Verified Computation Toward Real Theorems

**Status:** July 23, 2026. Companion to `PROPOSAL.md` (the Level 1 project), `META.md` (the honesty ladder), and `VERIFICATION.md` (the source audit). This document converts the ambition "give maximum effort on RH" into the strongest program that is actually executable, with the division of labor AI is genuinely good at. It does not promise a proof of RH, and per META.md it never will; it promises the fastest honest ascent of the ladder.

## What this week's AI results do and do not license

Two claims circulating in July 2026 were fact-checked against primary sources (see §5):

- **Jacobian conjecture, dimension ≥ 3: credibly *disproved* by an AI-found counterexample** — an explicit degree-7 map ℂ³→ℂ³ with constant Jacobian determinant, generically 3-to-1. Corroborated by Terence Tao's technical blog digestion, the Secret Blogging Seminar's independent verification writeup, Lean-checking within a day, and named engagement from Buzzard and Mathew. Not yet peer-reviewed; n = 2 remains open.
- **"Dinitz–Garg–Goemans" (Goemans' cost-version conjecture for single-source unsplittable flow, from the 1999 DGG paper): an announced counterexample** (fractional cost 58 vs. every unsplittable rounding ≥ 60), AI-assisted, resting so far on one researcher's social-media post and a chat log. Unverified; no preprint; no independent confirmation found.

The pattern in both: **AI found counterexamples — finite, explicitly checkable objects.** That is the regime where large-scale AI search demonstrably works. RH is the mirror image: its counterexample direction (a zero off the critical line) is precisely what a verification computation detects, and a century of evidence says none exists to be found; its truth direction quantifies over infinitely many zeros and admits no finite certificate. So the honest reading of this week is: *AI-heavy mathematics is real, and it is strongest exactly at the levels this project already occupies — rigorous computation, explicit-constant optimization, and formally checkable constructions.* That is where maximum effort goes.

## Phase 0 — Execute Level 1 (the standing project)

`PROPOSAL.md` v0.2, unchanged: RH to 10¹³ + 65,626 through the six-step reproduction gate, corollary Λ ≤ 0.19 via Polymath15 Table 1 row 3. This is the deliverable everything else builds on, and its gate discipline (no launch before reproduction and pricing) is non-negotiable. Note the flywheel: target T3 below, if it succeeds, directly cuts Phase 0's compute bill.

## Phase 1 — Level 2 targets, ranked

Ranked by (tractability × synergy with Phase 0 × how recently the thread moved). The top two threads each saw multiple published improvements in the last four years by a small set of authors following a recognizable explicit-constant playbook — the strongest available signal that a well-prepared newcomer with heavy computational leverage can contribute.

**T1. Sharpen Turing's method.** The completeness-certification step of every RH verification. Lineage: Turing 1953 → Lehman 1970 → Trudgian 2011 (Math. Comp. 80, arXiv:0903.1885) → Trudgian 2014/16 (arXiv:1406.3416) → *active in the last year*: Palojärvi–Zhao on Artin/Selberg-class Turing methods (arXiv:2508.03023, Aug 2025) and Amberger on bounding ∫S(t) directly (arXiv:2512.23064, Dec 2025). Openings: sharpen the ζ constants again; extend to further L-function classes; couple the sharpened constants to Phase 0's own boundary computations. *This is also the deepest-expertise-per-page topic in the field — the study track (§4) runs through it.*

**T2. Consequences paper from our own results.** Template: Johnston (arXiv:2109.02249) turned Platt–Trudgian's 3×10¹² into improved explicit prime-counting bounds (|π(x)−li(x)| < √x·log x/(8π) on a huge range). Rerunning that machinery — and the Büthe-style criteria Platt–Trudgian themselves invoke — at height 10¹³ with Λ ≤ 0.19 in hand yields a low-risk, clearly publishable explicit-bounds paper that leverages assets nobody else will have. Near-zero new theory; real value to the explicit-estimates community.

**T3. Implement and rigorize Hiary's O(t^{4/13}) algorithm.** Hiary (Annals 174, 2011; arXiv:0711.5005) gave O(t^{1/3}) and O(t^{4/13}) evaluation methods for ζ(1/2+it); Bober–Hiary implemented only the t^{1/3} one (arXiv:1607.00709, spot computations near t = 10³²). The t^{4/13} algorithm appears never to have been implemented, let alone with interval/ball arithmetic. A rigorous Arb implementation is a concrete, well-defined, unclaimed target — simultaneously a publishable contribution and a direct cost-reducer for Phase 0 and any future rung. Highest engineering content of the six; highest synergy.

**T4. Zero-free region constants.** Active thread: Mossinghoff–Trudgian–Yang 2022 (C = 5.558691, arXiv:2212.06867) → Bellotti 2023 (Korobov–Vinogradov constant 54.004, arXiv:2306.10680) → Bellotti–Trudgian–Yang, March 2026 (C = 4.896, arXiv:2603.21490, via Heath-Brown-inspired techniques). These results stitch directly to verified height (MTY's KV region explicitly kicks in at 3×10¹² — our Phase 0 raises that stitch point). Incremental constant-shaving is live and ongoing; entering it requires the §4 study track first.

**T5. De Bruijn–Newman barrier machinery.** The upper-bound method itself (Polymath15's effective H_t estimates + barrier) has not structurally improved since 2019; all progress since has been "more verification" (0.22 → 0.20 → our targeted 0.19). Openings: better effective bounds on the heat-flow evolution, better barrier test functions, and Dobner's complex-analytic reproof of Λ ≥ 0 as a possible source of new technique. Hardest of the five; genuinely new mathematics required; the Gap-B audit in Phase 0 is the natural on-ramp.

**T6 (deprioritized). Li/Keiper coefficients.** Johansson's rigorous n = 10⁵ record (via Arb, arXiv:1611.02831) makes a bigger computation low-novelty unless paired with structural theorems (e.g., the Chebyshev-recurrence angle of arXiv:2006.13103). Park unless a theorem-shaped idea appears.

## Phase 2 — Where AI effort concentrates

Matched to demonstrated AI strengths, in order: (1) *rigorous computation at scale* — Phase 0 itself, T3's implementation, T2's bound-grinding; (2) *explicit-constant optimization* — T1/T4 involve large searches over parameter choices in fixed analytic frameworks, exactly the shape of work AI accelerates; (3) *formalization* — Lean-checking the Turing-method constants and the Λ-corollary assembly would be both a safeguard and a standalone contribution (the Jacobian counterexample was Lean-checked within a day; that standard is now the bar); (4) *literature synthesis and audit* — as already demonstrated in `VERIFICATION.md`. What AI does not change: the need for the analytic depth in §4 before T1/T4/T5 contributions are real.

## Phase 3 — The study track (from META.md §strategy)

Depth before breadth, in this order: explicit-formula and S(t) theory (Titchmarsh ch. 9; Trudgian's papers line-by-line) → Turing/Lehman method internals → Riemann–Siegel and Hiary's exponential-sum machinery → Polymath15's effective estimates in full → the explicit zero-free-region literature. Target: be able to re-derive, not just cite, every constant Phase 0 and T1–T4 depend on. This is the multi-year "become the narrow expert" path that is also the only known on-ramp to Levels 3–5.

## §5. Source discipline (standing rule)

Every record claim and every "X was just solved" report gets checked against primary sources before it steers a decision. This week's sweep found real signal (Tao's blog, Secret Blogging Seminar) wrapped in heavy content-mill amplification, plus one outright fabricator (mathlumen.com) and one unverifiable viral claim. Aggregators are never evidence. Post-knowledge-cutoff arXiv IDs cited above (2508.03023, 2512.23064, 2603.21490) are agent-fetched and should be re-confirmed at Step 0 of any launch.

## The honest endpoint, restated

Executing this roadmap perfectly produces: a new verification record, a new world record on Λ, one to three genuine Level 2 theorems/implementations, formal certificates, and — the real asset — deep expertise in the one corner of analytic number theory where computation and theory meet. It does not produce a proof of RH, and nothing on any current horizon does. If a route to Level 3+ ever opens for this project, it will open *because* of the depth built here, and it will be recognized by the experts recruited in Gate Step 6 — not by us declaring it.
