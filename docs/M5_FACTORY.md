# M5: The Explicit-Estimates Factory — Design and First Run

**Date:** July 24, 2026. Executes `docs/TIER2_MOONSHOTS.md`'s M5 entry: *"candidate
parameter/lemma-chain search (AI) → Arb-verified bound evaluation → Lean-checked
statement (M1 infrastructure) → human review. Run it across the standing corpus
(Turing constants, |S(T)| bounds, zero-free regions, zero-density estimates)... it
industrializes the genre... the slack, across dozens of published constants, is real
prize money lying on the table."* Companion docs: `docs/TURING_SPEC.md` (the constants
inventory M5 operates on), `formal/M1_PLAN.md` + `formal/LehmanBrent.lean` (the
statement-emission target), `docs/T2_CONSEQUENCES_OUTLINE.md` (a second, independent
instance of exactly this slack pattern), `verification/rs_verify.py` (the certificate
executor these constants feed).

**Concurrency note:** this session initially found `docs/TIER2_MOONSHOTS.md` and
`docs/T2_CONSEQUENCES_OUTLINE.md` absent from the tree (as `formal/M1_PLAN.md` and
`docs/M4_BARRIER_REPRO.md` also record, independently, at their own time of writing).
Both landed mid-session (commits `dbd1ae5`, `d474f1e`) from parallel moonshot work.
This document was written after they existed and is grounded in their actual text,
not a reconstruction.

## 1. Inventory: 8 explicit constants in this corpus, with likeliest slack

All entries below are sourced from files already in this repository
(`docs/TURING_SPEC.md`, `verification/rs_verify.py`, `formal/LehmanBrent.lean`,
`proposal/*.md`) plus the primary source fetched directly for this run
(arXiv:0903.1885v3). Items 7-8 are marked with lower confidence since their numeric
detail comes from this session's own domain knowledge / the cited repo docs rather
than a freshly re-fetched primary source — flagged rather than silently trusted, per
the project's standing source-discipline rule (`proposal/ROADMAP.md` §5).

| # | Constant | Current value | Source | Likeliest lemma-chain slack |
|---|---|---|---|---|
| 1 | **T11 Thm 2.2** integral bound | `a=2.067, b=0.059` for `t₂>t₁>168π` | Trudgian 2011, §2.2-2.3 | Free params `c∈(1,5/4]`, `d∈(1/2,1]` chosen by a **hand grid, Δ=0.01, 1979-era-style manual search** (§2.3, quoted in full below); the growth-bound pair `(K,θ)=(2.53, 1/4)` is van der Corput-derived — the paper itself flags a sharper option (Huxley's `α=32/205≈0.1561` convexity exponent) as available but "the calculation of the implied constant would prove lengthy" — i.e. an *author-acknowledged, unrealized* improvement. |
| 2 | **T11 Cor 2.3** block count | `N ≥ 0.0031 log²gp + 0.11 log gp` | `TURING_SPEC.md` §2, `rs_verify.required_blocks` | The `0.0031/0.11` pair is (2.15)/(2.16) rounded and frozen for **all** `gp ≥ 2π·10¹²`; it is not re-derived per target height. This session's own run (§4 below) shows evaluating the *exact*, unrounded `(a,b)` at a specific target height (rather than reusing the universal rounded pair) saves a full Gram block at `gp≈10¹³`. |
| 3 | **T14 Thm 1** 3-term bound | `a=1.698,b=0.183,c=0.049` for `t₂>t₁>10⁵`, per-decade table (e.g. `1.792,0.178,0.046` at `10¹³`) | `TURING_SPEC.md` §2 | Table is discretized by decade, not continuous in the target height; `TURING_SPEC.md` line 24 explicitly flags that **T14 never republishes the block-count corollary** for this bound — the generalization is pure implementer work. |
| 4 | **T14-provisional block corollary** | `required_blocks_t14_provisional` in `rs_verify.py`; `lehman_brent_corollary_T14_3term_at_1e13_PROVISIONAL` in `LehmanBrent.lean` | This project (unpublished) | Not "slack to extract" but **an unverified factory output already sitting in the codebase** — the derivation folds T14's `log log t` term in with the constant term under an unjustified "slow variation" heuristic; `formal/M1_PLAN.md` obstacle 3 flags that the correct Lehman-Brent counting argument (integrate-then-sum over blocks) could produce a `log gp · log log gp` cross-term this guess lacks. This is the single most valuable open M5 ticket: prove or refute the guess. |
| 5 | **T14b Thm 1** pointwise bound | `\|S(T)\| ≤ 0.111 logT + 0.275 loglogT + 2.450` | `TURING_SPEC.md` §2 | Single fixed triple; almost certainly has its own `(c,d)`-style free-parameter derivation (same shape as item 1) not re-examined by this project — a second, structurally identical M5 target once item 1's harness exists. |
| 6 | **Zeta growth-bound pair** feeding item 1 | `K=2.53, θ=1/4` | Trudgian 2011 Lemma 2.5/2.7, van der Corput | Superseding input available in principle: Huxley's `θ=32/205` convexity exponent (cited in the same paper, not adopted "for the paper's purposes"); since `b ∝ θ`, swapping it in is a direct, mechanical test of how much of item 1's `b=0.059` is growth-bound slack vs. genuinely irreducible. |
| 7 | **Polymath15 Thm 1.2, Table 1 row 3** | `t₀=0.180, y₀=0.14142, Λ=0.19` at `X=2×10¹³+131,252` | `proposal/PROPOSAL.md` §2, `proposal/VERIFICATION.md` (independently cross-checked in this repo already) | Table 1's rows are a discrete sweep of `(t₀,y₀,N₀)` triples (`docs/M4_BARRIER_REPRO.md` §6 confirms the paper's own §10 calls its target bound "arbitrarily chosen"); re-optimizing continuously for the *exact* project target height (`10¹³+65,626`, not the nearest table row) is the same "height-specific re-tune" pattern as item 2, applied one level up the stack. Confidence: medium (constants independently re-verified in this repo per `VERIFICATION.md`, but this session did not re-derive Table 1's own generating machinery). |
| 8 | **Johnston's PNT-type criterion constant** | `9.06 → 8.94` (H-updated) per `docs/T2_CONSEQUENCES_OUTLINE.md` | Johnston arXiv:2109.02249, via Büthe's criterion | `T2_CONSEQUENCES_OUTLINE.md` itself flags this as requiring "rerunning Johnston's iterative fixed-point optimization (the paper's real technical work — hand-tuned constants, 3 convergence rounds)" — i.e. a hand-iterated fixed point is exactly the shape of thing an automated search should replace. Confidence: medium — sourced from this repo's own outline doc, which itself is a single research-agent's read of the paper, not independently re-verified here. |

**Why 8, not 12:** the brief asked for 8-12; this list stops at 8 because each entry
above is traceable to a concrete file already in this repository (no invented
constants), and a 9th-12th slot would have meant reaching for zero-free-region or
zero-density constants (`ROADMAP.md` T4: Mossinghoff–Trudgian–Yang, Bellotti,
Bellotti–Trudgian–Yang) this session did not re-fetch and verify against a primary
source. Padding the table with unverified numbers would violate the same
source-discipline this project already holds itself to (`ROADMAP.md` §5) — better to
under-fill the quota honestly. §3 below still lists T4 as a corpus M5 should eventually
reach.

## 2. Loop architecture

```
 ┌──────────────────┐   ┌──────────────────────┐   ┌───────────────────┐   ┌────────────┐
 │ 1. CANDIDATE      │   │ 2. ARB-VERIFIED      │   │ 3. STATEMENT       │   │ 4. REVIEW  │
 │    SEARCH         │──▶│    EVALUATION        │──▶│    EMISSION        │──▶│    GATE    │
 │ (heuristic, fast) │   │ (rigorous, slow)     │   │ (machine-checkable)│   │ (human)    │
 └──────────────────┘   └──────────────────────┘   └───────────────────┘   └────────────┘
        │                         │                          │                    │
   mpmath/float            python-flint / Arb          formal/*.lean         merge into
   grid or 1D scan         ctx.prec, arb literals,      theorem stub with     TURING_SPEC.md
   over free params        mid()+rad() outward           the winning          + rs_verify.py,
   (c,d,θ,K,...)            rounding — exactly            (a,b,...) plugged    or reject with
                            rs_verify.required_blocks'    in, `sorry`d until   a documented
                            pattern                       gate 4 clears        reason
```

1. **Candidate search (this run's `verification/const_factory_t11.py`).** Given a
   closed-form `F(params)` derived symbolically from the target lemma chain, search
   the free parameters' valid analytic ranges for a minimum, at one or more target
   heights. Cheap, non-rigorous, floating point (mpmath here). Purpose: find *leads*,
   not certificates — exactly analogous to how `rs_verify.py`'s Gram-point placement
   is heuristic while its sign certification is not (`docs/TURING_SPEC.md` §4's
   "may be heuristic" / "must be rigorous" split, reused verbatim as this loop's
   organizing principle).
2. **Arb-verified evaluation.** Every candidate that beats (or nears) the current best
   gets replayed through the *same* closed form using `python-flint`/Arb ball
   arithmetic — `ctx.prec`, `arb`/`acb` literals, and outward rounding via
   `mid()+rad()`, precisely the pattern already implemented in
   `rs_verify.required_blocks`. The messy `∫ log ζ(σ)dσ` integrals in T11's own proof
   (this run's `logzeta_integral`) are exactly the kind of term that needs a certified
   quadrature or a published enclosure before a candidate is trusted, not a float
   `mp.quad` call — this run's script is explicitly flagged (in its own docstring) as
   stopping short of that stage.
3. **Statement emission.** Package the verified `(a,b,...)` (or block-count
   requirement) as a machine-checkable object. `formal/LehmanBrent.lean` already
   defines the exact target shape for this corpus: `turing_integral_bound`,
   `lehman_brent_corollary_T11`, and the flagged-provisional
   `lehman_brent_corollary_T14_3term_at_1e13_PROVISIONAL`. A winning M5 candidate's
   job is to either fill a `sorry` with a real proof, or supply the missing
   derivation `M1_PLAN.md` obstacle 3 says is needed (the 3-term count formula).
4. **Review gate.** No output goes live without independent re-derivation, mirroring
   `proposal/VERIFICATION.md`'s own process (multiple research agents extracting
   claims, then an independent cross-verification pass re-deriving the arithmetic from
   scratch). Concretely for this corpus: (a) re-check the closed form against the
   lemma chain by an independent read of the primary source (this run already caught
   one such transcription slip — see §4); (b) confirm the result is a *proof*, not a
   numerically-fitted table entry (guard exactly the risk already flagged on
   `required_blocks_t14_provisional`); (c) sign-off before `rs_verify.py` or
   `TURING_SPEC.md` are edited to depend on it. Nothing here is a new invention — it
   is `TURING_SPEC.md` §4's rigor split plus `VERIFICATION.md`'s review process,
   wired into a loop instead of run once by hand.

## 3. Repo components already in place

| Component | Role in the M5 loop |
|---|---|
| `verification/rs_verify.py` — `theta_ball`, `z_ball`, `certified_sign`, `required_blocks` | The Arb-verified-evaluation primitives (stage 2) already exist and already implement the exact "closed form → arb literals → outward-rounded ceiling" pattern a factory-derived constant must be re-run through. |
| `verification/rs_verify.py` — `required_blocks_t14_provisional` | A **live, already-produced, not-yet-gated** M5 output: a candidate that passed stage-1/2 (algebraically matches both published instantiations) but is explicitly held at stage 4 pending independent confirmation ("production certification uses `max(published, provisional)`" per `docs/T2_CONSEQUENCES_OUTLINE.md`). This is the worked example the task asked for — it did not need to be constructed, it already exists in the tree. |
| `formal/LehmanBrent.lean`, `formal/M1_PLAN.md` | The statement-emission target and its own honest gap analysis. `M1_PLAN.md` obstacle 3 is, verbatim, an open M5 ticket: derive (not guess) the 3-term block-count formula. |
| `docs/TURING_SPEC.md` | Where a verified factory output gets a new dated entry, following the same provenance-note convention already used at the top of that file. |
| `verification/bench_window.py`, `verification/results/*.json` | Template for a factory run-harness: parameter/result logging to JSON, exactly the shape a candidate-search sweep should emit for audit. |
| `proposal/VERIFICATION.md` | Template for the review-gate stage: multiple extraction agents + one independent cross-verification pass, already demonstrated on this exact corpus (Polymath15 Table 1, Platt-Trudgian's constants). |
| `docs/M4_BARRIER_REPRO.md` §9 | A second worked example of the same underlying pattern, one level up the stack: an explicit table of which Polymath15 barrier parameters (`X0` shift, mollifier primes, Taylor cutoff `E`) are author-acknowledged "feasibility, not optimality" choices — i.e. M5's target corpus is not limited to Turing's method; the barrier machinery (M4) is built from the identical kind of slack. |

## 4. First factory run: re-derive T11 Theorem 2.2, search (c,d) for slack

**Implementation:** `verification/const_factory_t11.py` (committed alongside this
doc, already run — this is not merely specced, it executed).

**What it does.** Transcribes Trudgian 2011's closed-form Theorem 2.12
(`πa = ...`, `2πb = θ(c-1/2) + d²(log4-1)`, equations (2.15)-(2.16), read directly
from the fetched PDF, arXiv:0903.1885v3 pages 9-10) as `Fc(c) + Fd(d)` — the same
additive split Trudgian's own §2.3 notes ("there are no terms in (2.15) and (2.16)
which involve both c and d") — then does two independent 1D scans over
`c∈(1,5/4]`, `d∈(1/2,1]` to minimize `F(c,d) = a + b·log(gp/2π)` at a chosen target
Gram point `gp`, for `θ=1/4, K=2.53` (Trudgian's own growth-bound pair).

**Validation gate (passed).** A literal transcription of the `(c-1/2)log(Kζ(c))`
term (as it renders in the fetched image, no `1/2` prefactor) reproduces `b` exactly
but overshoots `a`. Restoring the `1/2` prefactor — present in the precursor Lemma
2.8 this term descends from — reproduces **both** of Trudgian's own worked
instantiations to 4 significant figures:

```
c=1.25  d=1.0   a=1.6084 (paper 1.61)    b=0.0913 (paper 0.0914)
c=1.1   d=0.75  a=2.0666 (paper 2.0666)  b=0.0585 (paper 0.0585)
```

This is the review-gate discipline (§2, stage 4) working as intended *during
construction*, not after: a transcription slip was caught by demanding the harness
reproduce known published numbers before trusting it on new ones.

**Search results.**

*Legacy height* `gp = 2π×10¹²` (Trudgian's own 2009 target, Corollary 2.3):
the harness's continuous 1D optimum is `F=3.680431` at `c=1.1028, d=0.7403` —
matching Trudgian's own coarse hand grid (`Δ=0.01`) reported optimum of `F=3.6805`
at `c=1.1, d=0.74` to within numerical noise. **Finding: no material slack in (c,d)
at this height** — the 2009 hand search was already essentially optimal.

*Project target height* `gp = 10¹³+65,626` (`proposal/PROPOSAL.md` §2's frozen
endpoint, never optimized by Trudgian since his paper predates this project):
optimum `F=3.707080` at `c=1.1003, d=0.7353`, versus `F=3.708941` reusing Trudgian's
"nice fraction" instantiation `(c=11/10, d=3/4)` unmodified — **a 0.050% gain**,
again essentially nothing. `(c,d)` re-optimization is not where this corpus's slack
lives.

**Where the real slack was found — not in (c,d), in rounding discipline.**
Converting both results to Theorem 2.1's block-count requirement at the target
height:

```
T11 Cor 2.3's published, rounded, universal constants (0.0031, 0.11):  N >= 7
exact (a,b) at c=11/10,d=3/4, evaluated at THIS height (no rounding):  N >= 6
height-specific re-optimized (c,d):                                    N >= 6
```

Corollary 2.3's constants are rounded once and frozen for *all* `gp ≥ 2π×10¹²`
forever; simply not rounding — evaluating the exact closed form at the actual
target height — saves one full Gram block. Re-optimizing `(c,d)` beyond Trudgian's
own choice buys nothing further at this height.

**Independent cross-check.** `docs/T2_CONSEQUENCES_OUTLINE.md` (written by a
different session, working the T14-provisional bound rather than T11 rounding)
reports the identical practical number by a different mechanism: *"worth one Gram
block at g_p = 10¹³ (6 vs 7)."* Two independent slack-extraction routes — (a) stop
rounding T11's own constants, (b) switch to T14's sharper 3-term bound — land on the
same `6` at the same height. That agreement is itself evidence (not proof) that `6`
is close to a real floor for this method at this height, and a natural next
experiment is whether combining both (T14's bound *and* a fresh `(c,d)`-style
re-optimization of *its* free parameters) pushes past `6` — this run did not attempt
that; §1 item 3/4 name it as the next ticket.

**Runtime:** ~2.5 minutes on one core (mpmath, 30 decimal digits, two 100-point 1D
scans at two heights); no Arb/ball-arithmetic pass was run — per §2's stage
boundary, that is the required next step before any of these numbers can be called a
certificate rather than a lead.

## 5. Honest scope note

Per `docs/TIER2_MOONSHOTS.md`'s own framing: this factory *finds what existing
methods' slack allows* — it does not invent new methods. This first run confirms
that framing empirically: at the one target height that actually matters for this
project, the 17-year-old hand-tuned `(c,d)` choice already sitting in the literature
was within 0.05% of the continuous optimum. The real, repeatable win this session
found was procedural (evaluate exactly, at the height that matters, instead of
reusing a rounded one-size-fits-all corollary) rather than analytic — consistent
with `TIER2_MOONSHOTS.md`'s own caveat that "new *methods* remain human-plus-luck
territory."
