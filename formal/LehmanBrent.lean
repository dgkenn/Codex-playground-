/-
  formal/LehmanBrent.lean

  Formal (Lean 4 / mathlib-style) scaffold for the Turing-method completeness
  certificate used in `docs/TURING_SPEC.md` and implemented (numerically, in
  ball arithmetic) by `verification/rs_verify.py`.

  STATUS: every proof below is `sorry`. This file has NOT been checked by
  `lake build` — no Lean/mathlib toolchain is available in the environment
  this file was authored in (see `formal/M1_PLAN.md`, obstacle 1). Identifiers,
  import paths, and lemma names are written to mathlib4-as-of-2026 naming
  conventions from documentation review, not from a green build. Treat this
  file as a specification of proof *obligations*, not a certificate.

  Provenance of every numerical constant and every inequality below is
  `docs/TURING_SPEC.md`, which in turn cites:
    T11  = Trudgian, "Improvements to Turing's method", arXiv:0903.1885,
           Math. Comp. 80 (2011) 2259-2279.
    T14  = Trudgian, "Improvements to Turing's method II", arXiv:1406.3416.
    T14b = "An improved upper bound for the argument of the Riemann
           zeta-function on the critical line II", arXiv:1208.5846,
           J. Number Theory 134 (2014) 280-292.

  Three theorem families are formalized here, in increasing order of how
  settled the mathematics is:
    1. `turing_integral_bound`        — T11 Theorem 2.2 (fully published).
    2. `lehman_brent_block_theorem`   — T11 Theorem 2.1 / Corollary 2.3
                                         (fully published, Lehman-Brent form).
    3. `lehman_brent_block_theorem_3term` — OUR OWN provisional generalization
                                         of (2) to T14's sharper 3-term bound.
                                         T14 explicitly does *not* republish
                                         the block-count corollary (see
                                         TURING_SPEC.md line 24); re-deriving
                                         it is implementer work. The statement
                                         below is a conjectured target, not a
                                         transcription of a proof from any
                                         paper — flagged throughout.
-/

import Mathlib.NumberTheory.LSeries.RiemannZeta
import Mathlib.Analysis.SpecialFunctions.Gamma.Basic
import Mathlib.Analysis.SpecialFunctions.Complex.LogBounds
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.MeasureTheory.Integral.IntervalIntegral.Basic
import Mathlib.MeasureTheory.Integral.IntervalIntegral.FundThmCalculus

noncomputable section

open Complex Real MeasureTheory intervalIntegral

namespace LehmanBrent

/-! ### 1. Basic objects: θ, Z, S, N

None of these currently exist in mathlib (see `formal/M1_PLAN.md` §1). They are
introduced here as `def`s where a formula is available, and as hypotheses
bundled into the statements where mathlib lacks the supporting machinery
(chiefly: a continuous/non-principal branch of `arg` along a path, needed for
`S`). This mirrors the honest status: these are the actual open construction
obligations, not just bookkeeping.
-/

/-- The Riemann–Siegel theta function,
    `θ(t) = Im log Γ(1/4 + it/2) − (t/2) log π`.
    CAVEAT (obstacle 2 in `M1_PLAN.md`): this uses mathlib's principal-branch
    `Complex.log`, via `Complex.arg`. That branch is continuous on
    `ℂ \ (Set.Iio 0 : Set ℝ)` (mathlib: `Complex.continuousAt_arg`), and the
    path `t ↦ 1/4 + i t/2` never touches the non-positive reals, so continuity
    in `t` is plausible — but "θ(0) = 0 as a continuous branch" per
    `TURING_SPEC.md` §1 is an unproven side-condition here, not a consequence
    of this definition alone. -/
def riemannSiegelTheta (t : ℝ) : ℝ :=
  (Complex.log (Complex.Gamma (1 / 4 + (t : ℂ) / 2 * Complex.I))).im
    - (t / 2) * Real.log Real.pi

/-- Hardy's `Z` function: `Z(t) = e^{iθ(t)} ζ(1/2 + it)`, real-valued for real
    `t` because `θ` is chosen exactly to cancel the phase of `ζ` on the
    critical line. Realness (`hardyZ_im_eq_zero` below) is a genuine theorem,
    not definitional, since `riemannSiegelTheta` is defined via `.im` of a
    complex log and mathlib does not (yet) know the cancellation identity. -/
def hardyZ (t : ℝ) : ℝ :=
  (Complex.exp (Complex.I * riemannSiegelTheta t)
      * riemannZeta (1 / 2 + (t : ℂ) * Complex.I)).re

/-- `Z` really is real, i.e. its imaginary part vanishes. This is the
    standard identity `arg ζ(1/2+it) = -θ(t) (mod 2π)` and is the first real
    theorem this file owes mathlib (obstacle 2). -/
theorem hardyZ_im_eq_zero (t : ℝ) :
    (Complex.exp (Complex.I * riemannSiegelTheta t)
        * riemannZeta (1 / 2 + (t : ℂ) * Complex.I)).im = 0 := by
  sorry

/-- `S(T) = π⁻¹ arg ζ(1/2+iT)`, via continuous variation of the argument
    along the path `2 → 2+iT → 1/2+iT` (TURING_SPEC.md §1), with the
    symmetric convention at ordinates that are themselves zeros. Mathlib has
    no "argument continued along a path" primitive (obstacle 3): the
    principal-branch `Complex.arg` jumps at the negative real axis and is
    *not* what is wanted here. We therefore take `S` as an opaque function
    satisfying its two characterizing properties as hypotheses
    (`CountsZeta`, `JumpsAtZeros` below) rather than as a `def`, so that the
    theorems below are stated against the *specification* of S, independent
    of which construction eventually discharges it. -/
variable (S : ℝ → ℝ)

/-- Defining property 1 of `S`: away from ordinates of zeros of `ζ` in the
    strip, `N(T) = θ(T)/π + 1 + S(T)` where `N` counts zeros (with
    multiplicity) of `ζ` in `0 < Im s ≤ T`, `0 ≤ Re s ≤ 1`. -/
def CountsZeta (N : ℝ → ℝ) : Prop :=
  ∀ T : ℝ, N T = riemannSiegelTheta T / Real.pi + 1 + S T

/-- Defining property 2 of `S`: `S` jumps by exactly `+1` at every zero of
    `ζ` in the strip (on the line or off it) and is otherwise continuous.
    This is exactly what makes the Turing/Lehman-Brent argument sensitive to
    off-line zeros (`TURING_SPEC.md` §1, last sentence). -/
def JumpsAtZeros (S : ℝ → ℝ) : Prop :=
  ∀ ρ : ℂ, riemannZeta ρ = 0 → 0 < ρ.im → ρ.re ∈ Set.Icc (0 : ℝ) 1 →
    ∃ ε > 0, ∀ t ∈ Set.Ioo (ρ.im - ε) ρ.im, ∀ t' ∈ Set.Ioo ρ.im (ρ.im + ε),
      S t' - S t = 1 -- schematic; the real statement needs a multiplicity
                      -- count and is itself an open obligation (see plan §3).

/-! ### 2. Gram points and Gram blocks -/

/-- A choice of Gram points: `θ(g n) = n π`. Existence/uniqueness for large
    `n` is classical (θ is eventually strictly increasing) but not currently
    in mathlib either (obstacle 2 territory: needs θ's derivative sign). -/
structure GramPoints (g : ℕ → ℝ) : Prop where
  theta_eq : ∀ n : ℕ, riemannSiegelTheta (g n) = n * Real.pi
  strictMono : StrictMono g

/-- A Gram point `g n` is *good* when the parity/sign certificate holds:
    `(-1)^n Z(g n) > 0`. -/
def GoodGramPoint (g : ℕ → ℝ) (n : ℕ) : Prop :=
  0 < (-1 : ℝ) ^ n * hardyZ (g n)

/-- `N` conforms to Rosser's rule on the block `(g n, g (n+p)]`: it contains
    exactly `p` certified sign changes of `Z`. Formalizing "certified sign
    changes of Z" precisely (as opposed to just "N T - N (g n) = p" via the
    zero-counting function) is left abstract via `countSignChanges`; wiring
    it to an actual zero count is obstacle 3. -/
def ConformsToRosser (countSignChanges : ℝ → ℝ → ℕ) (g : ℕ → ℝ) (n p : ℕ) : Prop :=
  countSignChanges (g n) (g (n + p)) = p

/-! ### 3. T11 Theorem 2.2 — the Turing integral bound -/

/-- **Turing integral bound** (`docs/TURING_SPEC.md` §2, T11 Theorem 2.2).
    For `t₂ > t₁ > 168π`,
    `|∫_{t₁}^{t₂} S(t) dt| ≤ 2.067 + 0.059 log t₂`.
    This is the published, fully general bound; T14 Theorem 1 below sharpens
    it for `t₂ > 10⁵` at the cost of an extra `log log` term. -/
theorem turing_integral_bound
    (t₁ t₂ : ℝ) (h1 : 168 * Real.pi < t₁) (h2 : t₁ < t₂) :
    |∫ t in t₁..t₂, S t| ≤ 2.067 + 0.059 * Real.log t₂ := by
  sorry

/-- **T14 Theorem 1** (`docs/TURING_SPEC.md` §2), the sharper 3-term bound,
    valid for `t₂ > t₁ > 10⁵`:
    `|∫ S| ≤ 1.698 + 0.183 log log t₂ + 0.049 log t₂`.
    `TURING_SPEC.md` also records a decade-specific triple at `t₂ ≈ 10¹³`:
    `(a, b, c) = (1.792, 0.178, 0.046)`, captured separately below as
    `turing_integral_bound_T14_at_1e13` since it is a *different* published
    numeric instance, not a corollary of this one. -/
theorem turing_integral_bound_T14
    (t₁ t₂ : ℝ) (h1 : (10:ℝ)^5 < t₁) (h2 : t₁ < t₂) :
    |∫ t in t₁..t₂, S t| ≤ 1.698 + 0.183 * Real.log (Real.log t₂) + 0.049 * Real.log t₂ := by
  sorry

/-- The decade-specific T14 triple at `t₂ ≈ 10¹³`, as tabulated in
    `docs/TURING_SPEC.md` §2. Kept as a distinct theorem (rather than derived
    from `turing_integral_bound_T14`) because the tighter per-decade
    constants are a *separate* published table entry, not an instantiation of
    the global 3-term bound. -/
theorem turing_integral_bound_T14_at_1e13
    (t₁ t₂ : ℝ) (h1 : (10:ℝ)^5 < t₁) (h2 : t₁ < t₂) (h3 : t₂ ≤ (10:ℝ)^13) :
    |∫ t in t₁..t₂, S t| ≤ 1.792 + 0.178 * Real.log (Real.log t₂) + 0.046 * Real.log t₂ := by
  sorry

/-- **Pointwise sanity bound** (T14b Theorem 1, `docs/TURING_SPEC.md` §2):
    `|S(T)| ≤ 0.111 log T + 0.275 log log T + 2.450` for `T ≥ e`.
    Not used by the block theorem itself, but load-bearing in
    `verification/rs_verify.py` as an escalation sanity check; included here
    for completeness and because a future proof of `JumpsAtZeros`/`CountsZeta`
    consistency will likely lean on it. -/
theorem turing_pointwise_bound (T : ℝ) (hT : Real.exp 1 ≤ T) :
    |S T| ≤ 0.111 * Real.log T + 0.275 * Real.log (Real.log T) + 2.450 := by
  sorry

/-! ### 4. T11 Theorem 2.1 — the Lehman–Brent block theorem -/

/-- **Lehman–Brent block theorem** (`docs/TURING_SPEC.md` §2, T11 Theorem
    2.1, itself Lehman 1970 sharpened by Turing's argument as reworked by
    Brent 1979 and again by Trudgian). If `N` consecutive Gram blocks with
    union `(g n, g p]` all conform to Rosser's rule, and
    `N ≥ (b / 6π) log² (g p) + ((a − b log 2π) / 6π) log (g p)`
    for the constants `a, b` of the *general* 2-term integral bound
    `|∫ S| ≤ a + b log t`, then `Nzeta (g n) ≤ n + 1` and
    `Nzeta (g p) ≥ p + 1`.

    `Nzeta` denotes the zero-counting function `N(T)` of `TURING_SPEC.md` §1
    (`N(T) = θ(T)/π + 1 + S(T)`); it is passed in via `CountsZeta` rather than
    fixed as `def`, matching the treatment of `S` above. -/
theorem lehman_brent_block_theorem
    (Nzeta : ℝ → ℝ) (hNzeta : CountsZeta S Nzeta)
    (g : ℕ → ℝ) (hg : GramPoints g)
    (countSignChanges : ℝ → ℝ → ℕ)
    (a b : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b)
    (hbound : ∀ t₁ t₂ : ℝ, 168 * Real.pi < t₁ → t₁ < t₂ →
      |∫ t in t₁..t₂, S t| ≤ a + b * Real.log t₂)
    (n p N : ℕ) (hnp : n < p)
    (hconform : ∀ k, n ≤ k → k < p → GoodGramPoint g k ∧ GoodGramPoint g (k+1))
    (hblocks : ConformsToRosser countSignChanges g n (p - n))
    (hcount : (N : ℝ) ≥
      (b / (6 * Real.pi)) * (Real.log (g p))^2
        + ((a - b * Real.log (2 * Real.pi)) / (6 * Real.pi)) * Real.log (g p)) :
    Nzeta (g n) ≤ n + 1 ∧ p + 1 ≤ Nzeta (g p) := by
  sorry

/-- **T11 Corollary 2.3**, the numeric instantiation of the block theorem at
    `a = 2.067, b = 0.059` (T11 Theorem 2.2's own constants):
    `N ≥ 0.0031 log² (g p) + 0.11 log (g p)`.
    `docs/TURING_SPEC.md` §2 records the cross-check
    `0.059 / 6π ≈ 0.0031` and `(2.067 − 0.059 log 2π) / 6π ≈ 0.11`, and notes
    at `g p ≈ 2π·10¹²`, `N = 6` conforming blocks suffice. This corollary is
    *the* certificate `verification/rs_verify.py` currently implements. -/
theorem lehman_brent_corollary_T11
    (Nzeta : ℝ → ℝ) (hNzeta : CountsZeta S Nzeta)
    (g : ℕ → ℝ) (hg : GramPoints g)
    (countSignChanges : ℝ → ℝ → ℕ)
    (n p N : ℕ) (hnp : n < p)
    (hconform : ∀ k, n ≤ k → k < p → GoodGramPoint g k ∧ GoodGramPoint g (k+1))
    (hblocks : ConformsToRosser countSignChanges g n (p - n))
    (hcount : (N : ℝ) ≥ 0.0031 * (Real.log (g p))^2 + 0.11 * Real.log (g p)) :
    Nzeta (g n) ≤ n + 1 ∧ p + 1 ≤ Nzeta (g p) := by
  sorry

/-! ### 5. Provisional 3-term generalization (OUR OWN, UNPUBLISHED)

`docs/TURING_SPEC.md` line 24 is explicit: *"T14 does not republish the
block-count corollary — re-deriving it with the 3-term bound is implementer
work, flagged as such."* Everything in this section is exactly that
implementer work, attempted, and it is a CONJECTURE, not a citation. The
functional form below is obtained by mimicking the shape of the T11
Corollary 2.3 derivation (bound `a + b log t` → count
`(b/6π) log² g_p + ((a − b log 2π)/6π) log g_p`) applied term-by-term to the
3-term bound `a + b log log t + c log t`, i.e. treating the `log log t` term
the same way the constant term `a` was treated (since `log log t` varies far
slower than `log t` across one Gram block). THIS SUBSTITUTION HAS NOT BEEN
JUSTIFIED — see `formal/M1_PLAN.md` obstacle 1. The correct treatment may
require re-running the original Lehman-Brent counting argument (which
integrates the bound across each block and sums over blocks) rather than
naively swapping the constant. -/

/-- **Provisional / conjectural** 3-term Lehman-Brent block theorem. Uses
    the T14 Theorem 1 integral bound `|∫S| ≤ a + b log log t + c log t`
    (general form; `lehman_brent_corollary_T14_3term_at_1e13` below plugs in
    the tabulated constants at `t ≈ 10¹³`). The count hypothesis
    `hcount_conjectural` is our best-guess generalization, NOT a proven
    requirement — flagged in the name and in the `sorry`'s companion comment.
-/
theorem lehman_brent_block_theorem_3term_PROVISIONAL
    (Nzeta : ℝ → ℝ) (hNzeta : CountsZeta S Nzeta)
    (g : ℕ → ℝ) (hg : GramPoints g)
    (countSignChanges : ℝ → ℝ → ℕ)
    (a b c : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b) (hc : 0 ≤ c)
    (hbound : ∀ t₁ t₂ : ℝ, (10:ℝ)^5 < t₁ → t₁ < t₂ →
      |∫ t in t₁..t₂, S t| ≤ a + b * Real.log (Real.log t₂) + c * Real.log t₂)
    (n p N : ℕ) (hnp : n < p)
    (hconform : ∀ k, n ≤ k → k < p → GoodGramPoint g k ∧ GoodGramPoint g (k+1))
    (hblocks : ConformsToRosser countSignChanges g n (p - n))
    -- CONJECTURAL count requirement — see block comment above. The `b`-term
    -- is folded in alongside `a` under the (unjustified) slow-variation
    -- heuristic; a correct derivation may instead produce a `log g_p * log
    -- log g_p` cross term, which this statement does NOT contain.
    (hcount_conjectural : (N : ℝ) ≥
      (c / (6 * Real.pi)) * (Real.log (g p))^2
        + ((a + b * Real.log (Real.log (g p)) - c * Real.log (2 * Real.pi))
            / (6 * Real.pi)) * Real.log (g p)) :
    Nzeta (g n) ≤ n + 1 ∧ p + 1 ≤ Nzeta (g p) := by
  sorry

/-- Numeric instantiation of the provisional 3-term theorem at the
    `t₂ ≈ 10¹³` decade table entry `(a,b,c) = (1.792, 0.178, 0.046)`
    (`docs/TURING_SPEC.md` §2). This is the version relevant to Phase 0's
    target height (`proposal/PROPOSAL.md`: RH to `10¹³`). Same provisional
    status as the general theorem above. -/
theorem lehman_brent_corollary_T14_3term_at_1e13_PROVISIONAL
    (Nzeta : ℝ → ℝ) (hNzeta : CountsZeta S Nzeta)
    (g : ℕ → ℝ) (hg : GramPoints g)
    (countSignChanges : ℝ → ℝ → ℕ)
    (n p N : ℕ) (hnp : n < p)
    (hgp_range : (10:ℝ)^5 < g p ∧ g p ≤ (10:ℝ)^13)
    (hconform : ∀ k, n ≤ k → k < p → GoodGramPoint g k ∧ GoodGramPoint g (k+1))
    (hblocks : ConformsToRosser countSignChanges g n (p - n))
    (hcount_conjectural : (N : ℝ) ≥
      0.00244 * (Real.log (g p))^2  -- c/(6π) = 0.046/(6π), see M1_PLAN.md §4
        + (0.0906 + 0.00944 * Real.log (Real.log (g p)))
            * Real.log (g p)) :  -- (a − c log 2π)/(6π) = 0.0906 ; b/(6π) = 0.00944
    Nzeta (g n) ≤ n + 1 ∧ p + 1 ≤ Nzeta (g p) := by
  sorry

end LehmanBrent
