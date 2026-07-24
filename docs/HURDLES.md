# Hurdle Inventory: From Here to Everything Reachable — and Where "Systematic" Stops

**Date:** July 24, 2026. Companion to `ROADMAP.md` (targets), `META.md` (honesty ladder), `TURING_SPEC.md`, `STEP2_CODE_CUSTODY.md`. This is the complete dependency chain from the current position upward, each hurdle stated with its attack. One structural fact is stated without varnish at the end, because a hurdle list that hides it would be a lie.

## Current position (verified, on this branch)

A working ball-arithmetic verifier that produces proof-grade statements ("all 1,516 zeros with 0 < Im s ≤ 1998.92 lie on the critical line" — certified signs + Lehman–Brent/Trudgian completeness certificate), cross-validated against Odlyzko's tables and against a second independent implementation path; full-range runs to T≈75,000 (100,000 zeros) in flight; measured cost scaling (per-eval α ≈ 0.44, per-zero ≈ T^0.46, two independent fits agreeing); code custody mapped; the plan itself source-audited. That is Gate Steps 0–3 substantially advanced and Step 4 seeded, on a project whose targets are RH to 10¹³ and Λ ≤ 0.19.

## Tier 0 — Immediate hurdles (attackable now, days–weeks)

**H1. Finish and cross-validate the reproduction runs.** Two implementations must agree exactly on 100,000 zeros and match Odlyzko. In flight. Risk: low. Also hardening: background-process persistence (runs died twice to session mechanics — checkpointing goes into the verifier next, which production needs anyway).

**H2. Close the completeness gap at height.** The windowed benchmark found count deficits (~3 at T=10⁸–10⁹) consistent with S(t) fluctuation but not yet *proven* to not be missed close pairs. Attack: run Turing-certified (not expectation-judged) segments at those heights; wire in the sharper T14 constants for heights ≥ 10⁵. This is exactly what the certificate machinery is for.

**H3. The 2,500× algorithm hurdle — the big engineering one.** Naive certified scanning extrapolates to ~10¹⁰ core-hours at 10¹³; Platt–Trudgian did it in 7.5×10⁶ via windowed-FFT multi-evaluation (Booker/Platt 2017, documented at pseudocode level). Nothing at production scale happens until this is implemented in Arb. Attack: staged reimplementation from the 2017 paper (§3's 8 steps, Appendices A–C error bounds), validated against our existing per-point verifier segment-by-segment — each window's output must match the point-by-point certified result exactly. This is also roadmap target T3's on-ramp (Hiary t^{1/3} → t^{4/13} sits on the same foundations).

**H4. Custody contacts.** Two emails only a human can send: (a) Platt/Trudgian — code request, blessing, and "is an extension already running?" (Steps 0/2/6 in one letter); (b) Polymath15 participants — the Gap-B row-3 toolchain question. Attack: I draft both, you send them. Additionally: authorize `add_repo km-git-acc/dbn_upper_bound` in a session and the Gap-B code audit happens directly.

## Tier 1 — Hurdles to the Level 1 result (RH to 10¹³, Λ ≤ 0.19; months, gated)

**H5. Honest pricing (Gate Step 4 proper).** Requires H3 first — pricing the naive algorithm would overstate cost by three orders of magnitude. Attack: benchmark the windowed implementation at 10¹⁰–10¹², fit, price with contingency.

**H6. Distributed rigor infrastructure.** Restartable sharded runs, certificate archives, corruption detection, independent segment reproduction. Known-solvable engineering; the failure modes (silent corruption, unaudited segments) are the project's dominant risk per `PROPOSAL.md` §7.

**H7. Compute acquisition.** ~19M core-hour floor (2.5× Platt–Trudgian) — academic allocations (NCI/ACCESS-class) or ~low-single-digit-$M cloud. Attack: H5's empirical price sheet + the collaboration from H4 (their allocations track record) → grant/allocation applications. Not fundable before Step 4; that ordering is the gate working as designed.

**H8. Gap B resolution.** Row-3 barrier rigor audit — contact-dependent (H4b); worst case is a bounded re-run of the barrier in Arb.

**H9. Expert sign-off / collaboration (Gate Step 6).** The natural authors of this result are the people whose pipeline it extends. Best case: this project becomes a Platt–Trudgian(+us) collaboration. Every hurdle above gets easier if H4 lands well; none require it except H8.

**Output of Tier 1: two world records.** This is the highest rung reachable by purely systematic attack.

## Tier 2 — Hurdles to genuine new theorems (Level 2; 1–3 years)

**H10. Depth.** The binding constraint is no longer engineering: contributing to Turing-constant sharpening (T1), zero-free regions (T4), or barrier machinery (T5) requires re-derivation-level fluency in the explicit-estimates literature (`ROADMAP.md` §Phase 3 study track). AI accelerates this (search over parameter choices, formalization, audit) but does not substitute for it.

**H11. Execution of T1–T5** per the roadmap, ordered by tractability: consequences paper (T2, low risk, uses our own Tier 1 assets) → Hiary implementation (T3, continues H3) → Turing constants (T1) → zero-free regions (T4) → dBN barrier theory (T5). Each is a real publication; T1/T4 are live threads where the same few authors have landed successive improvements — the field's signal that entry is possible.

## Tier 3 — The discontinuity (stated plainly)

Above Tier 2 the question changes from "can we verify/sharpen more?" to "why must every zero lie on the line?" — and here **there is no hurdle list**, for anyone, human or AI. A proof of RH requires mathematics that does not currently exist: a spectral realization (Hilbert–Pólya), a positivity proof (Li/Weil), a workable equivalent, or something no one has imagined. The field's own state is the evidence: the best minds with the deepest tools have not produced a decomposition of this problem into attackable subproblems. "Attack systematically" is precisely the strategy that stops working at this boundary — that is what makes it a Millennium Problem rather than a large project.

What a systematic actor *can* do about the discontinuity — and this is the honest limit of planning:
1. **Maximize surface area for luck**: Tier 2 depth is the only known on-ramp; every genuinely new tool in this field was found by someone fluent in the old ones.
2. **Formalize** (Lean) what we build — machine-checked infrastructure compounds and is where AI-assisted mathematics is advancing fastest.
3. **Monitor the frontier** (Step-0 discipline, primary sources only) so that if the enabling idea appears anywhere, we are positioned to act on it within days rather than years.
4. **Never schedule it.** Any plan that puts a date on Level 3+ is dishonest, and dishonesty is the one thing that would disqualify this project from the collaboration (H9) it needs.

For completeness, the prize itself adds procedural hurdles even given a proof: publication, community verification, a multi-year waiting period, and the Clay Institute's decision — mechanical compared to the mathematics, listed here only so the chain is complete.

## This week's attack order

1. H1: runs complete → Step 3 status doc (in flight).
2. H2: Turing-certified segments at 10⁸–10⁹; wire T14 constants.
3. H4: draft both contact emails for the user to send.
4. H3: begin windowed-FFT implementation skeleton against the 2017 paper.
5. H11-prep: outline the T2 consequences paper (it becomes real the day Tier 1 lands).
