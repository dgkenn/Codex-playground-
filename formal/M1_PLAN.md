# M1 Plan — Formalizing the Turing / Lehman–Brent Completeness Certificate

**Status:** July 24, 2026. First milestone of the formalization moonshot referenced in
`docs/TURING_SPEC.md` and `proposal/ROADMAP.md` Phase 2, point 3 ("Lean-checking the
Turing-method constants and the Λ-corollary assembly would be both a safeguard and a
standalone contribution"). Companion file: `formal/LehmanBrent.lean` (Lean 4 /
mathlib-style statements, every proof `sorry`).

**Note on the source document named in this task:** `docs/TIER2_MOONSHOTS.md` does not
exist in this repository (checked: `docs/` contains only `TURING_SPEC.md` and
`STEP2_CODE_CUSTODY.md`; no file or git history reference to that name anywhere in the
tree, including packed git objects). The nearest existing equivalent is
`proposal/ROADMAP.md` Phase 1/2, which ranks "T1: Sharpen Turing's method" as the
top synergy target and names Lean-checking the Turing-method constants as the
formalization angle — that is the plan this document executes against. If a
`TIER2_MOONSHOTS.md` exists elsewhere (a different branch, a not-yet-committed
draft), it was not visible to this session; the milestone content here should be
reconciled with it when found.

---

## 1. What mathlib (mathlib4, as of 2026) already has

Checked via mathlib4_docs and web search (no local Lean toolchain available in this
environment — see obstacle 1). Confidence noted per item.

| Needed | mathlib status | Confidence |
|---|---|---|
| `riemannZeta : ℂ → ℂ`, `completedRiemannZeta`, functional equation (`riemannZeta_one_sub`, `completedRiemannZeta_one_sub`) | **Present.** `Mathlib.NumberTheory.LSeries.RiemannZeta`. | High (docs page fetched directly) |
| `RiemannHypothesis` as a formal `Prop` (`∀ s, ζ s = 0 → ¬trivial → s ≠ 1 → s.re = 1/2`) | **Present**, same file. | High |
| Trivial zeros (`riemannZeta_neg_two_mul_nat_add_one`), residue at 1 | **Present.** | High |
| Nonvanishing for `Re s ≥ 1` (`riemannZeta_ne_zero_of_one_le_re`) | **Present**, `Mathlib.NumberTheory.LSeries.Nonvanishing`. | Medium-high |
| Complex `Gamma` function, its basic analytic properties | **Present.** `Mathlib.Analysis.SpecialFunctions.Gamma.Basic` and related files. | High |
| `Complex.log`, `Complex.arg`, continuity of `arg`/`log` off the branch cut | **Present** (principal branch only). | High |
| Interval integrals (`intervalIntegral`), FTC, integration by parts, dominated convergence, basic norm bounds | **Present.** `Mathlib.MeasureTheory.Integral.IntervalIntegral.*`. | High |
| Meromorphic function zero/pole theory: isolated zeros, identity principle | **Present**, `Mathlib.Analysis.Meromorphic.IsolatedZeros`. | Medium |
| A Nevanlinna-style zero/pole **counting function** for meromorphic functions | **Present**, `Mathlib.Analysis.Complex.ValueDistribution.CountingFunction` — logarithmic counting function for locally-finite-support divisors. Closest existing relative of `N(T)`, but built for value-distribution theory, not tied to contour integrals of `f'/f` or to `ζ` specifically. | Medium (found by name search only, not read in full) |
| **The Argument Principle** as a standalone contour-integral ⇔ zero-count theorem, ready to invoke | **Not found** as a directly citable name (`ArgumentPrinciple`-style file). May be derivable from the meromorphic/isolated-zeros API plus complex-analytic contour integration, but no single lemma matching the classical statement surfaced in two search passes. | Low-medium — needs a session with actual mathlib source access, not just docs search, to confirm absence vs. just poor discoverability |
| **Riemann–Siegel theta function** `θ(t)` | **Absent.** No `riemannSiegelTheta` (or similarly named) def found anywhere in mathlib4_docs or search. | Medium-high confidence of absence |
| **Hardy's Z function** | **Absent.** | Medium-high confidence of absence |
| **`S(T)`, `N(T)` (argument/counting functions of Riemann–von Mangoldt theory)** | **Absent.** | Medium-high confidence of absence |
| **Gram points, Gram blocks, Rosser's rule** | **Absent** — these are extremely specialized, no reason to expect otherwise. | High confidence of absence |
| **Turing's method / Lehman–Brent theorem itself** | **Absent.** | High confidence of absence |
| Continuous branch of `arg` *along a specified path* (not just off a fixed cut) | **Not found as a ready-made tool.** This is precisely what defining `S(T)` rigorously needs (continuous variation along `2 → 2+iT → 1/2+iT`), and it is a genuinely different thing from "principal branch is continuous off `(-∞,0]`" — obstacle 3 below. | Medium |

**Bottom line:** mathlib gives us the *analytic substrate* (ζ, Γ, functional equation,
integral calculus, meromorphic function theory) but **none** of the Riemann–von Mangoldt
apparatus (θ, Z, S, N, Gram points, Rosser's rule, Turing's method) exists yet. Every
object in `formal/LehmanBrent.lean` from §1 onward ("Basic objects") had to be
introduced from scratch in that file.

---

## 2. What must be built (in dependency order)

1. **`riemannSiegelTheta`** — definable now from existing mathlib `Complex.Gamma` /
   `Complex.log`, *if* the continuity-in-`t` and `θ(0)=0` normalization can be proven
   (needs: the path `t ↦ 1/4+it/2` avoids the branch cut of `Complex.log`'s principal
   value — should follow from `Complex.Gamma` having no zeros/poles for `Re > 0` plus a
   case argument that its value never lands on the non-positive reals along this path,
   which is *not* obviously true without checking — flagged as a real lemma to prove,
   not an assumption).
2. **Realness of Hardy `Z`** (`hardyZ_im_eq_zero` in the Lean file) — needs the identity
   `arg ζ(1/2+it) ≡ −θ(t) (mod 2π)`, which in turn needs a continuous-argument
   machinery for `ζ` restricted to the critical line.
3. **A continuous-argument-along-a-path primitive** for `ℂ`-valued functions, general
   enough to define `S(T)` per its actual specification (continuous variation along
   `2 → 2+iT → 1/2+iT`, `TURING_SPEC.md` §1) rather than mathlib's principal `arg`.
   This is the single largest new piece of infrastructure needed and does not yet
   exist in a form found by this session's search (item 2 in the obstacles below).
4. **`N(T)`, the zero-counting function**, and the identity `N(T) = θ(T)/π + 1 + S(T)`
   — this *is* effectively a form of the argument principle for `ζ` in the critical
   strip and should be provable from mathlib's meromorphic-function zero-counting
   machinery (`ValueDistribution.CountingFunction`) plus (3), once (3) exists. This is
   the connective tissue between "generic complex analysis" (which mathlib has) and
   "Riemann–von Mangoldt theory" (which it doesn't).
5. **Gram points and the "good"/Rosser's-rule predicates** — purely definitional once
   (1) and a monotonicity lemma for `θ` (`θ` eventually strictly increasing, from its
   known asymptotic `θ'(t) ~ (1/2) log(t/2π)`) are available.
6. **T11 Theorem 2.2 (the integral bound)** — this is Trudgian's actual analytic
   argument (bounding `S` via the argument principle applied to a rectangle plus
   explicit error control on `Γ`); it is a substantial, self-contained piece of
   classical analytic number theory that has never been formalized. This is real
   research-grade formalization work, not a restatement.
7. **T11 Theorem 2.1 / Corollary 2.3 (the block theorem)** — combinatorial argument on
   top of (4)+(6): if `N` consecutive blocks conform, the accumulated integral bound
   from (6) forces the accumulated `S`-jump budget below what `N` non-conforming or
   missed zeros would need. This is Lehman's original counting argument (1970),
   reworked by Brent (1979) and again by Trudgian; formalizing it means transcribing
   that specific combinatorial-analytic argument, not just its final inequality.
8. **The 3-term generalization** — genuinely open even on paper (flagged by
   `docs/TURING_SPEC.md` line 24 itself: *"T14 does not republish the block-count
   corollary — re-deriving it... is implementer work"*). Formalizing it requires first
   doing the mathematical derivation (pen-and-paper or Lean-assisted) that step 7 does
   for the 2-term bound, then repeating it for 3 terms. `formal/LehmanBrent.lean`'s
   `..._PROVISIONAL` theorems are a placeholder guess at the target statement, explicitly
   not a claim that the guessed count formula is correct.

## 3. Proof-obligation graph

Nodes are proof obligations; an edge `A → B` means `B` depends on `A`. Roughly
matches the numbered list above.

```
mathlib: riemannZeta, completedRiemannZeta, functional equation   (HAVE)
mathlib: Complex.Gamma, Complex.log/arg (principal branch)        (HAVE)
mathlib: intervalIntegral + FTC + norm bounds                     (HAVE)
mathlib: Meromorphic.IsolatedZeros, ValueDistribution.CountingFn  (HAVE, partial fit)
        |
        v
[1] riemannSiegelTheta θ(t), well-defined + continuous + θ(0)=0
        |
        +----------------------------------------+
        v                                         v
[5] Gram points g_n (θ strictly increasing    [2] hardyZ_im_eq_zero
    eventually; existence/uniqueness of g_n)       (needs [3] partially: the
        |                                          mod-2π argument identity)
        |                                              |
        |                                              v
        |                                     [3] continuous-arg-along-path
        |                                         primitive  ***BOTTLENECK***
        |                                              |
        |                          +-------------------+-------------------+
        |                          v                                       v
        |                 [4] S(T) construction                  [4'] N(T) = θ/π+1+S
        |                     (CountsZeta / JumpsAtZeros              identity (argument
        |                      properties, currently taken            principle for ζ
        |                      as hypotheses in the .lean file)        in the strip)
        |                          |                                       |
        v                          v                                       v
[5] GoodGramPoint, ConformsToRosser predicates (definitional, needs [1]+[4]/[4'])
        |
        v
[6] turing_integral_bound   (T11 Thm 2.2 — Trudgian's actual analytic argument;
    depends on [3]/[4] to even state |∫S| meaningfully, and is itself a large
    new analytic argument: Gamma asymptotics + contour/rectangle estimates)
        |
        v
[7] lehman_brent_block_theorem / corollary_T11   (Lehman's counting argument;
    depends on [4'], [5], [6])
        |
        v
[8] lehman_brent_block_theorem_3term (PROVISIONAL)   (depends on [6] being redone
    with T14's 3-term bound in place of T11's 2-term one, AND on [7]'s counting
    argument being re-run against 3 terms instead of 2 — the count formula in
    `formal/LehmanBrent.lean` is an unverified guess pending this)
```

The graph has one clear bottleneck: **node [3], the continuous-argument-along-a-path
primitive.** Nodes [2], [4], [4'] all route through it, and everything above [4]/[4']
(items 6-8, i.e. the actual Turing/Lehman-Brent theorems) is unstatable in a
mathematically faithful way until it exists — mathlib's principal-branch `Complex.arg`
is not the same object as `S(T)`'s continuously-varied argument, and silently
substituting one for the other would make the formalized theorems either false or
vacuous, not just incomplete.

## 4. Numeric cross-checks performed for this milestone

To catch transcription errors before they became `sorry`d Lean statements:

- T11 Corollary 2.3: `0.059/(6π) = 0.05900/18.8496 ≈ 0.003131` — matches
  `TURING_SPEC.md`'s quoted `≈ 0.0031`. `(2.067 − 0.059·log(2π))/(6π)`: `log(2π) ≈
  1.83788`, `0.059 × 1.83788 ≈ 0.10844`, `(2.067 − 0.10844)/18.8496 ≈ 0.10389` —
  matches the spec's quoted `≈ 0.104` (the published corollary rounds this up to
  `0.11`, which is what both the spec and `formal/LehmanBrent.lean` use for the actual
  inequality — the tighter `0.104` is only the unrounded cross-check value).
- Provisional 3-term corollary at `t₂ ≈ 10¹³`, `(a,b,c) = (1.792, 0.178, 0.046)`:
  `c/(6π) = 0.046/18.8496 ≈ 0.002441`; `(a − c·log 2π)/(6π) = (1.792 − 0.046×1.83788)
  /18.8496 = (1.792 − 0.08454)/18.8496 ≈ 0.09055`; `b/(6π) = 0.178/18.8496 ≈ 0.009444`.
  These feed the `hcount_conjectural` hypothesis of
  `lehman_brent_corollary_T14_3term_at_1e13_PROVISIONAL`. An earlier draft of this
  computation contained an arithmetic slip (`0.0122`/`0.294` instead of
  `0.00244`/`0.0906`) caught and fixed before finalizing the Lean file — flagged here
  as a reminder that even the *provisional* numbers need independent re-checking, let
  alone the underlying derivation.

## 5. Top 3 obstacles

**1. No Lean/mathlib toolchain in this environment — nothing here has been compiled.**
`which lean/lake/elan` all fail; no local mathlib checkout. Every identifier, import
path, and lemma name in `formal/LehmanBrent.lean` was chosen from documentation review
and naming-convention pattern-matching, not from `lake build` feedback or `#check`.
Concretely this means: import paths may be stale or wrong, lemma names invoked nowhere
in this file but implied to exist (e.g., for the `sorry` proofs to eventually close)
may not exist under those names, and even the type-correctness of the statements
(e.g., coercions between `ℕ`, `ℝ`, `ℂ` in the Gram-point/count arithmetic) is unverified.
**Mitigation:** the very next action for M1 execution (not this milestone) should be
getting this file in front of an actual `lake build` — either a container with mathlib
cached, or a `leanprover/mathlib4` CI-style environment — before adding any real
mathematical content to the `sorry`s.

**2. The continuous-argument-along-a-path primitive (graph node [3]) does not
exist in mathlib and blocks everything downstream.** `S(T)`'s defining property
(`TURING_SPEC.md` §1: "continuous variation along `2 → 2+iT → 1/2+iT`") is not the
same mathematical object as mathlib's principal-branch `Complex.arg`, which has a
discontinuity at the negative real axis. Building this properly likely means: (a)
proving `ζ` is nonvanishing on the horizontal leg `Re s = 2` (easy — mathlib's
`riemannZeta_ne_zero_of_one_le_re` already gives this) so a continuous logarithm exists
there by general covering-space / simply-connected-domain theory; (b) handling the
vertical leg `Re s ∈ [1/2, 2]` where `ζ` *can* vanish inside the strip, meaning the
"continuous variation" is only well-defined up to the convention that `S` jumps at
zeros — i.e., `S` is fundamentally a *multi-valued-made-single-valued-by-convention*
object, not a continuous function at all, which changes what "define `S`" even means
formally (a genuine design decision, not just missing library code). This is why
`formal/LehmanBrent.lean` takes `S` as a hypothesis-characterized opaque function
(`CountsZeta`, `JumpsAtZeros`) rather than a `def` — that dodge is honest about the gap
but does not close it, and it means `hardyZ_im_eq_zero` and every downstream theorem
are currently uninhabited without this piece.

**3. The 3-term generalization's count-formula derivation is genuinely unknown, not
merely unformalized.** Unlike obstacles 1-2 (engineering/infrastructure gaps around a
settled piece of mathematics), this is a mathematics gap: nobody — not Trudgian's T14
paper, not this project before today — has published a re-derivation of the
Lehman-Brent block-count inequality using the 3-term integral bound in place of the
2-term one. `formal/LehmanBrent.lean`'s `lehman_brent_block_theorem_3term_PROVISIONAL`
guesses a functional form (fold the `log log t` term in alongside the constant term,
under a "slow variation" heuristic) that has NOT been checked against the actual
Lehman/Brent/Trudgian counting argument, which works by integrating the bound across
each Gram block and summing — a step where a `log t · log log t` cross-term could
plausibly appear and is absent from the current guess. Closing this obstacle requires
either (a) locating and adapting the original T11 Theorem 2.1 proof technique (not
just its statement, which is all `docs/TURING_SPEC.md` records) to the 3-term case by
hand before attempting to formalize it, or (b) treating this as its own small research
question with its own literature check (the Palojärvi–Zhao and Amberger papers named in
`proposal/ROADMAP.md`'s T1 entry are the most likely places a general-bound-shape
block theorem already exists and could be adapted rather than re-derived from scratch).

## 6. Suggested next milestone (M2, not executed here)

Get an actual Lean toolchain + mathlib checkout in a session with more setup budget;
run `lake build` on `formal/LehmanBrent.lean` far enough to fix import paths and
surface which mathlib identifiers referenced above (`Complex.continuousAt_arg`, the
exact name of the meromorphic counting function API, etc.) are real versus
misremembered from documentation search. That single step would upgrade most of §1's
"Medium confidence" rows to verified fact or verified absence.
