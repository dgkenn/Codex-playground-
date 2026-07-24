# Tier 2, Thought Bigger: Five Moonshots

Expansion of `ROADMAP.md` Tier 2 beyond incremental constant-sharpening. Each is a program, not a paper — chosen so that failure still leaves publishable residue, and so AI leverage (search, formalization, verified computation at scale) is the differentiator rather than a garnish.

## M1. The first formally verified RH verification (Lean)

Nobody has ever machine-checked a large-scale RH verification end to end: the Turing-method theorems (Trudgian's constants), the ball-arithmetic evaluation layer, and the certificate chain itself. Build it: formalize the Lehman–Brent/Trudgian corollary in Lean (mathlib already has ζ basics and the argument principle), have the verifier emit Lean-checkable certificates per shard, and the record computation becomes the largest formally verified numerical theorem ever produced. Why bigger: it changes the epistemic standard for all computational number theory — and the Jacobian-counterexample episode showed same-day Lean checking is now the community's bar for AI-touched mathematics. First milestone: formalize the block-count corollary statement and our provisional 3-term generalization (killing the Brent-1979-paywall uncertainty *by reproving it*, the strongest possible resolution of that open item).

## M2. The rigorous fast-zeta library ("FFTW of ζ")

Hiary's O(t^{4/13}) algorithm has sat unimplemented for 15 years; the windowed multi-evaluation exists only in Platt's private code. Build the open, Arb-based, certificate-emitting library that owns this niche: per-point RS, windowed-FFT multi-eval (our Stage A→C), Hiary t^{1/3} then t^{4/13}, all behind one API, all rigorously error-bounded, benchmarked and shipped. Why bigger: infrastructure compounds — every future verification, every L-function record, every Λ rung by anyone runs through it; it is how a newcomer becomes load-bearing in the field in one move. First milestone: Stage B (in flight tonight).

## M3. GRH at scale: the L-function verification program

The identical certificate machinery generalizes: Booker 2006 and Palojärvi–Zhao (Aug 2025 — the thread is moving *now*) supply Turing methods for Artin L-functions and the Selberg class; Platt's GRH verification (q ≤ 400,000) is a decade old and pre-Arb. Target: a systematic GRH verification factory over Dirichlet/Artin families with published certificates — records nobody currently contests, feeding directly into explicit bounds for primes in progressions (the Bennett–Martin–O'Bryant–Rechnitzer-style constants the field actually consumes). Why bigger: it's a *family* of records plus a reusable pipeline, and the natural first application of M2 beyond ζ.

## M4. Move the barrier, not just the height: dBN method improvement

Every Λ improvement since 2019 held Polymath15's machinery fixed and bought computation. The bigger swing: improve the machinery — better mollifiers/test functions in the barrier argument, sharper effective H_t bounds (their Appendix estimates were tuned for feasibility, not optimality), Dobner's complex-analytic technique as fresh input. Payoff structure: any improvement multiplies *every* future rung (a barrier needing height X/4 instead of X/2 halves the log-cost of the entire ladder forever). This is genuine analytic number theory with a computable scoreboard — the right arena for AI-assisted search over analytic choices with Arb-verified consequences. First milestone: reproduce the Λ ≤ 0.22 barrier computation (Gap B audit doubles as the on-ramp), then parameter-search the test-function space.

## M5. The explicit-estimates factory

The pattern across T1/T4 and this week's own micro-result (the 3-term block bound): explicit-constant theorems are optimization problems over analytic parameter choices, verified by rigorous arithmetic — exactly the shape AI search excels at. Build the loop as a system: candidate parameter/lemma-chain search (AI) → Arb-verified bound evaluation → Lean-checked statement (M1 infrastructure) → human review. Run it across the standing corpus (Turing constants, |S(T)| bounds, zero-free regions, zero-density estimates). Why bigger: it industrializes the genre — instead of one sharpened constant per paper per year, a pipeline that sweeps the whole frontier and emits verified improvements. Honest bound: it finds what the existing methods' slack allows — new *methods* remain human-plus-luck territory. But the slack, across dozens of published constants, is real prize money lying on the table.

## Sequencing

M2 is already running (Stage B). M1 starts with the block-corollary formalization (also unblocks the provisional bound). M4's on-ramp is the Gap B audit we already owe. M3 follows M2. M5 assembles the other four's tooling. Every one feeds Tier 1 or is fed by it — no moonshot is orthogonal to the records program.
