# M4 On-Ramp: De Bruijn–Newman Barrier Reproduction Spec

**Date:** July 24, 2026. **Scope note on provenance:** `docs/TIER2_MOONSHOTS.md` does not exist in this
repository and no file or label "M4" was found anywhere in `docs/` or `proposal/` (checked by grep). The
closest match to the requested on-ramp is `proposal/ROADMAP.md` §"Phase 1", target **T5 — De Bruijn–Newman
barrier machinery**, which explicitly names "the Gap-B audit in Phase 0 [as] the natural on-ramp," and
`docs/STEP2_CODE_CUSTODY.md` item 2 (`dbn_upper_bound`), whose follow-up #3 calls for exactly this kind of
direct-audit spec. This document proceeds on that basis — implementing item 2's reconstruction target and
T5's on-ramp — rather than guessing at an unverifiable "M4" label. If a real `TIER2_MOONSHOTS.md` exists
elsewhere, this doc should be reconciled against it.

**Method:** Primary-source extraction from arXiv:1904.12438v2 (D.H.J. Polymath, *Effective approximation of
heat flow evolution of the Riemann ξ function, and a new upper bound for the de Bruijn-Newman constant*,
Res. Math. Sci. 6 (2019)), fetched as PDF and converted to text (`pdftotext -layout`) for page/section-range
reading, since the raw PDF byte stream is not directly parseable. Sections 7 ("Fast evaluation of multiple
sums") and 8 ("A new upper bound for the de Bruijn-Newman constant") were read in full; Lemma 8.4 and its
proof, the winding-number algorithm of §8.4, and the parameter-selection prose of §8.1 and §10 are quoted
or paraphrased below with equation numbers matching the paper. Cross-checked against this repo's existing
`proposal/VERIFICATION.md` (which already fetched and audited the same paper in a prior session) — no
discrepancies found; the given target parameters (X0 = 6×10¹⁰ + 83952, t0 = 0.2, y0 = 0.2) match the
paper's §8.1 exactly and match the prior audit's residual-uncertainties note verbatim.

**Important distinction (already flagged in `VERIFICATION.md` and `PROPOSAL.md` §3):** the "0.22 barrier" is
**Theorem 1.1**, not a row of Table 1. Table 1 is a *family* of conditional results (Λ = 0.21 down to 0.10)
produced by re-running the same machinery at different (X, t0, y0, N0); Theorem 1.1 is the unconditional
headline, proved once at the specific triple frozen in §8.1. This spec targets reproducing **Theorem 1.1's
barrier** (§8.4, claim (a)) since that is what the task's parameters name; the Table 1 methodology is
documented in §7 below because it is the literal "improvement search surface" the task asks to identify.

---

## 1. Mathematical objects (fully explicit, all from §§2–3 and §7–8)

**Region of validity (eq. 5):** `0 < t ≤ 1/2; 0 ≤ y ≤ 1; x ≥ 200`.

**Renormalizing function** (removes the Γ-factor's exponential decay so the barrier can be checked at
finite precision):

- `M0(s) := (1/8) s(s-1) π^{-s/2} Γ(s/2) · √(2π) exp((s/2 - 1/2) Log(s/2) - s/2)`  — eq. (6), a Stirling
  approximation to the Γ-factor in the completed ξ.
- `log M0(s) := Log s + Log(s-1) - log π + log(√(2π)/16) + (s/2 - 1/2) Log(s/2) - s/2` — eq. (7).
- `α(s) := (log M0)'(s) = 1/(2s) + 1/(s-1) + (1/2) Log(s/(2π))` — eq. (8)-(9).
- `Mt(s) := exp(t/4 · α(s)²) · M0(s)` — eq. (10) — the heat-flow deformation of M0.
- `Bt(x+iy) := Mt((1+y-ix)/2)` — eq. (11). Non-vanishing for t ≥ 0, y > 0; `|Bt(x+iy)| = e^{-(π/8+o(1))x}`.

**Riemann–Siegel-type approximation to Ht/Bt** (Theorem 1.3 / restated as Proposition 8.1 for the barrier
regions):

```
f_t(x+iy) := Σ_{n=1}^{N} b_n^t / n^{s*}  +  γ · Σ_{n=1}^{N} b_n^t · n^y / n^{s*+κ}      (eq. 14)
b_n^t := exp((t/4) log²n)                                                              (eq. 15)
γ(x+iy) := Mt((1-y+ix)/2) / Mt((1+y-ix)/2)                                             (eq. 16)
s* := (1+y-ix)/2 + (t/2)·α((1+y-ix)/2)                                                 (eq. 17)
κ := (t/2)·(α((1-y+ix)/2) - α((1+y+ix)/2))                                             (eq. 18)
N := floor(√(x/4π) + t/16)                                                             (eq. 19)
```

`f_t` is holomorphic in x+iy as long as N is constant, with jump discontinuities when N increments (this
is why the barrier's rectangle gets partitioned into N-constant sub-rectangles, region (a) below).

**Non-vanishing criterion** (Corollary 1.4): if `|f_t(x+iy)| > e_A + e_B + e_{C,0}` (explicit computable
error bounds, eqs. 20-24), then `Ht(x+iy) ≠ 0`. For the specific barrier regions used in §8, this collapses
to the simpler **Proposition 8.1**: `Ht(x+iy)/Bt(x+iy) = f_t(x+iy) + O≤(1.25×10⁻³)` throughout regions
(a)/(b)/(c) below.

## 2. Frozen barrier parameters for Theorem 1.1 (§8.1)

```
X0 := 6×10^10 + 83952
t0 := 0.2
y0 := 0.2
X  := X0 - 0.5                     (the actual barrier-region left edge)
N0 := 69098                        (Riemann-Siegel length at the barrier)
N1 := 1.5×10^6                     (cutoff between "moderate N" and "crude tail" regions)
```

Theorem 1.2's three hypotheses reduce (§8.2) to non-vanishing of `Ht(x+iy)/Bt(x+iy)` in three regions:

- **(a)** `X0-0.5 ≤ x ≤ X0+0.5`, `N = N0` (constant, holomorphic), `0 ≤ t ≤ 0.2`, `0.2 ≤ y ≤ 1` — **the
  barrier itself**, proved by the winding-number method (§8.4, below).
- **(b)** `x ≥ X0-0.5`, `N0 ≤ N ≤ N1`, `t = 0.2`, `0.2 ≤ y ≤ 1` — proved via an Euler-product mollifier
  (§8.5) since direct argument-principle tracking is too oscillatory here.
- **(c)** `N ≥ N1`, `t = 0.2`, `0.2 ≤ y ≤ 1` — proved via a crude closed-form triangle-inequality bound
  (Lemma 8.2 / Remark 8.3, using the imaginary error function `erfi`).

Hypothesis (i) of Theorem 1.2 (zero-freeness at t=0) is discharged for free by citing Platt's numerical RH
verification to height `T ≈ 3.06×10^10` (ref [18] in the paper) — **this is the one hypothesis this spec
does not need to reproduce**; it is imported, not recomputed.

## 3. Winding-number barrier verification (§8.4, claim (a)) — the core of "M4"

For each fixed `t ∈ [0, 0.2]`, `f_t` is holomorphic on rectangle `R = {X0-0.5 ≤ x ≤ X0+0.5; 0.2 ≤ y ≤ 1}`.
By Rouché's theorem it suffices to show `f_t(∂R)` (a) stays outside the ball `B = {|z| ≤ 1.25×10⁻³}` and
(b) has winding number 0 around the origin.

**Discrete algorithm as specified in the paper:**

1. Subdivide `∂R` into `4n` equally spaced mesh points `x_j + i y_j`, adjacent points ≤ `1/n` apart.
2. Evaluate `f_t` at every mesh point (via the fast method of §4 below).
3. Compute the discrete winding number:
   `W = (1/2π) Σ_{j=1}^{4n} arg( f_t(x_{j+1}+iy_{j+1}) / f_t(x_j+iy_j) )`   — verify `W = 0`.
4. To transfer this discrete-path claim to the *true* continuous trajectory `f_t(∂R)`, use a derivative
   bound `|∂f_t/∂z| ≤ D_z` on `∂R`: the polygonal path and the true trajectory differ by at most `D_z/(2n)`,
   so winding number and ball-avoidance both transfer as long as
   `|f_t(x_j+iy_j)| > 1.25×10⁻³ + D_z/(2n)`.
5. To cover a whole time-interval `[t, t']` at once (not just one t), use the stronger inequality (91):
   `|f_t(x_j+iy_j)| > 1.25×10⁻³ + D_z/(2n) + D_t·|t'-t|/(2n)`, where `D_t` bounds `|∂f_t̃/∂t|` for
   `t ≤ t̃ ≤ t'` on `∂R`. **This is the adaptive-stepping trick**: start at t=0, compute `D_z, D_t`, choose
   `n` so `D_z/(2n) ≤ 1`, evaluate the mesh, find the largest `t'` for which (91) still holds (or `t'=0.2`
   if it holds all the way), then repeat from `t'` until `t=0.2` is reached. This is why the paper reports
   mesh-point counts that vary with t (11076 at t=0, down to 56 at t=0.195 — the barrier gets numerically
   "easier" as t increases toward 0.2).

**Lemma 8.4 (the Dz/Dt derivative bounds), quoted in full:**

```
∂f_t/∂z bound:
  |∂f_t/∂z| ≤ Σ_{n=1}^N (b_n^t log n / n^{Re s*}) · (t log n / 2 + t log n / (4(x-6)))
              + |γ|·N^{|κ|} · Σ_{n=1}^N (b_n^t n^y / n^{Re s*}) ·
                  ( t log n/(4(x-6)) + log(|1+y+ix|/4π) + π + 3/x + 1/(4(x-6)) )

∂f_t/∂t bound:
  |∂f_t/∂t| ≤ Σ_{n=1}^N (b_n^t/n^{Re s*}) · ( (1/4) log n log(x/4πn) + (log n)/8 + (2 log n)/(x-6) )
              + |γ|·N^{|κ|} · Σ_{n=1}^N (b_n^t n^y/n^{Re s*}) ·
                  ( (1/4) log n log(x/4πn) + (log n)/8 + 1/(x-6) + (π/4)(2 log n/(x-6) + 1/2)
                    + (1/8π)(log(x/4π) + 8/(x-6)) )
```

Proof method: `s*, s**, γ` are holomorphic in `x+iy`, so Cauchy-Riemann gives `∂f_t/∂x = -i·∂f_t/∂y`;
differentiate the closed forms for `s*` (eq. 17) and `γ` (via `log γ = (t/4)(α(s)²-α(1-s)²) + log M0(s) -
log M0(1-s)`) directly and bound each piece with the elementary estimates of Lemma 5.1 and the crude bound
`α(s) = O≤(log(x/4π)/2 + O(1/(x-6)))`. Nothing here is numerically exotic — every bound is closed-form in
`x, y, t, N` and can be evaluated as a rigorous ball once `x, N` are fixed on `∂R`.

**Reported numerical outcome (§8.4, after Figs. 13–17):** stored-sum Taylor coefficients targeted to **20
decimal digits** of accuracy; derivative bounds were "chosen quite conservatively" (i.e. `D_z`, `D_t` as
computed are looser than the true derivatives, costing extra mesh points but not correctness); **overall
winding number came out 0** for every rectangle across `t = 0 → 0.2`. Code citation in the paper:
`dbn_upper_bound/arb` (the directory-name citation Gap B already flagged as the paper's only toolchain
disclosure for this step — no explicit mention of "Arb" or "ball arithmetic" in the prose itself).

## 4. Fast evaluation via stored-sum Taylor factorization (§7 — the engineering core)

Naive evaluation of `f_t(s)` for `M` mesh values costs `O(NM)`. §7 gives an `O((N+M)E²)` factorization:

Recenter the sum at `n0 := floor(N/2)`, write `B(b) := Σ_h (n0+h)^b b^t_{n0+h} / (n0+h)^{(1+y-iX)/2}` (and
similarly `A(a)` for the other half of eq. 14, so `f_t(s) = B(b) + γ(s)·A(a)`). Expand the numerator via
`(n0+h)^b = n0^b · exp(b·log(1+h/n0))` and `b^t_{n0+h} = n0^{t log n0/4}·exp((t/4) log²(1+h/n0))·exp((t/2)
log n0 · log(1+h/n0))`, then double-Taylor-expand both exponentials in `h/n0` to a cutoff order `E`:

```
B(b) ≈ n0^{b + (t/4) log n0} · Σ_{i=0}^{E-1} Σ_{j=0}^{E-1} B_{i,j} · (b + (t/2) log n0)^j / j!
B_{i,j} := Σ_h ( (t/4) log²(1+h/n0) )^i · log^j(1+h/n0) / ( (n0+h)^{(1+y-iX)/2} · i! )
```

`B_{i,j}` (an `E×E` table, `i,j = 0..E-1`) is **independent of the mesh point** `s` — it depends only on
`t, N, y, X`, so it is precomputed once per `t` (cost `O(NE²)`), then every mesh evaluation costs `O(E²)`
instead of `O(N)`. The paper used **E = 50**. Reported wall-clock for the main theorem's evaluation load
(**785,052 (t,s) pairs across 152 distinct t-values**, `N = N0 = 69098`): **78.5 core-hours naive → ~0.025
core-hours (~90 seconds) with the Taylor trick** — a ~3,100× speedup. Code citation:
`dbn_upper_bound/pari/barrier_multieval_t_agnostic.txt`.

## 5. X0 selection procedure (§8.1) — explicitly ad hoc, explicitly feasibility-driven

This is the clearest single passage where the paper states its own parameter choice is a *search*, not a
derivation:

1. Introduce `eulerprod(x, p_n) := Π_{p≤p_n} 1/(1 - p^{-1+ix/2})`, the y=1 Euler-product factor (where
   `|f_t|` is expected smallest in the barrier).
2. Numerically scan candidate integer shifts `1 ≤ q ≤ 10^5` near `X = 6×10^10`, keeping those where
   `min_{x - 6×10^10 - q ∈ {-0.5,0,0.5}} |eulerprod(x, 29)|` exceeds an arbitrarily chosen threshold (4).
   This produced **seven candidates**: q = 1046, 22402, 24198, 52806, 77752, 83952, 99108.
3. Among the seven, pick the `q` maximizing `min |f_0(x+i)|` over the same three-point neighborhood —
   **q = 83952 won**, with the maximized quantity ≈ 4.32.

Every number in this paragraph (the search window `10^5`, the threshold `4`, the choice to test only 3
offsets `{-0.5,0,0.5}`, the decision to use primes up to 29 in the scan but only up to 11 in the final
argument) is a tuning knob, not a mathematical requirement. **This — plus the analogous Table 1 parameter
search below — is the "improvement search surface" the task asks to identify.**

## 6. The Table 1 search (context: this is the general machinery, not Theorem 1.1)

§10 describes how the whole (X, t0, y0, N0) tuple was searched to build Table 1: fix a target lower bound
for `|f_{t0}(N0 + iy0)|` — **the paper says "we arbitrarily chose a target lower bound of 0.03"** — then use
Lemma 8.2/Remark 8.3's closed form to sweep `(t0, y0, N0)` triples minimizing `Λ = t0 + y0²/2` subject to
that bound, producing an "envelope" (their Fig. 20) of feasible `(x, Λ)` pairs. The barrier location `X0` is
then chosen by re-running the §8.1 ad hoc procedure at each new scale. **All barrier runs (Table 1 rows)
came back winding number 0**; mesh points were computed to **20-digit accuracy except the two highest rows,
done at 10 digits** (a precision/runtime trade-off, not a mathematical one) — this is the "unstated
arithmetic model" Gap B already flagged in `proposal/VERIFICATION.md`.

**Every one of these is a feasibility knob, and every one is a place a new search could plausibly do
better** (per `ROADMAP.md` T5's framing — "better barrier test functions" is exactly a proposal to replace
this ad hoc scalar search with something more systematic, e.g. gradient/lattice search over `(X0, t0, y0)`,
or a provably-near-optimal mollifier in place of the "significant trial and error" {2,3,5} choice in §8.5).

## 7. python-flint (Arb/FLINT 3.6.0, python-flint 0.9.0) — what's covered, what's a gap

Checked directly in this environment (`python3 -c "import flint; ..."`).

**Already covered / directly usable:**
- `acb`/`arb` ball arithmetic with `.log()`, `.gamma()`/`.lgamma()`, `.zeta()`, `.exp()`, `.erfi()` (needed
  verbatim for Remark 8.3's closed form), `.arg()` (principal argument — directly implements the paper's
  own winding-number formula `arg(f(z_{j+1})/f(z_j))`, since the paper's own fine-mesh design keeps each
  step's argument change `< π`, so no branch-unwrapping code is needed beyond what the paper already relies
  on).
- `arb_series.riemann_siegel_theta` / `.riemann_siegel_z` — native, rigorous, but these are the *classical*
  Riemann-Siegel θ/Z for ζ on the critical line, **not** the paper's `M0`/`Mt`/`Bt`/`f_t` (a different,
  heat-flow-deformed normalization) — cannot be substituted directly, only used as a cross-check tool (e.g.
  `Ht=0` iff `Bt`-normalized value vanishes, and one could sanity-check `t=0, y=0` limits against classical
  Z, but the acceleration machinery of §7 is entirely bespoke).
- `acb_series`/`arb_series` support composing `.log()`/`.exp()` as truncated power series with `.derivative()`,
  `.integral()`, `.reversion()` — this is structurally the same operation as §7's nested Taylor expansion of
  `exp(b·log(1+h/n0))` and `exp((t/4)log²(1+h/n0))`; implementing the `B_{i,j}` table via `acb_series`
  composition (rather than hand-rolled double sums) is a plausible, lower-risk implementation path than a
  literal transcription of §7's algebra.
- `dirichlet_char.hardy_z` (already validated in `verification/rs_verify.py`) is irrelevant to this specific
  barrier (it's for ζ directly, not `Ht`), but its presence confirms the substrate's rigorous-zeta layer is
  solid, which matters for hypothesis (i)'s import and for any future re-verification of Platt's height.

**Real gaps (must be hand-built, nothing in FLINT/python-flint ships these):**
1. `M0(s)`, `log M0(s)`, `α(s)`, `Mt(s)`, `Bt(x+iy)` (eqs. 6–11) — bespoke Stirling-type Γ-factor
   deformation, entirely absent from any library; must be coded from the closed forms above using `acb`
   primitives (`Log`, `sqrt`, `exp`) with careful branch handling (`Log` here is explicitly the principal
   branch with cut on `(-∞,1]`, matching `acb.log()`'s default branch convention, which should be verified
   rather than assumed).
2. `f_t(x+iy)` itself (eq. 14) and its two component sums (`b/γ` split) — no library primitive; a direct
   implementation is `O(N)` per point, fine for spot-checks but not for the barrier's ~785k evaluations.
3. The full §7 stored-sum/Taylor-factorization acceleration (`B_{i,j}` table, `E=50` truncation, error
   bound in footnote 5 of §7) — this is the single largest implementation gap by engineering effort; it is
   also the piece with the best available cross-check (compare accelerated vs. naive `f_t` at a handful of
   points before trusting the accelerated path at scale, exactly as the paper's own Figure 13 does).
4. Lemma 8.4's derivative bounds `D_z, D_t` — closed-form but intricate; needs its own careful transcription
   and a unit test against numerically-differenced `f_t` values (finite differences) before being trusted
   as a rigorous bound in an implementation, since a transcription slip here would silently under-bound the
   true derivative and invalidate the Rouché argument.
5. The adaptive-t-stepping algorithm of §8.4 step 5 (find the largest valid `t'` satisfying eq. 91, repeat)
   — simple control flow, not present anywhere as a library primitive, but the part of the spec most likely
   to have off-by-one or boundary-condition bugs if implemented casually.
6. The Euler-product mollifier `E_{t,5}` (§8.5) and its argument-principle handling of the negative real
   axis (eq. 93) — bespoke, and explicitly the product of hand-tuned trial and error (see §5–6 above), so a
   from-scratch reimplementation should not assume `{2,3,5}` is optimal, only that it is *sufficient* per
   the paper's own proof.
7. No winding-number/argument-principle *utility* exists in python-flint — the accumulation loop
   (`Σ arg(ratio)`, check `≈ 0` or `≈ 2πk`) is ~10 lines of glue code, not a gap in the substrate, but it is
   also not something to `import`.

Bottom line consistent with `docs/STEP2_CODE_CUSTODY.md` item 3: **no ball-arithmetic primitive needs
reconstructing** — the gap is entirely the bespoke heat-flow/M_t layer and the §7 acceleration scheme, both
fully specified in the paper's prose and equations, none of it exotic mathematics, all of it implementable
directly from §§2–3 and §7–8 above.

## 8. Compute estimate for reproducing the 0.22 barrier (Theorem 1.1, claim (a) only)

This is an order-of-magnitude estimate, not a benchmark; no code from this spec has been run yet (Gate
Step 3, "reproduce a published lower-height segment... before touching new heights," is the appropriate
next gate before spending real compute here — see `proposal/PROPOSAL.md` §5).

- **Paper's own anchor:** 785,052 `(t,s)` evaluations at `N=69098`, naive `O(N)` per point = 78.5 core-hours
  on late-2010s hardware (PARI/GP, precision/arithmetic model unstated per Gap B — plausibly double-double
  or GMP-backed multiprecision floats, not necessarily certified ball arithmetic); with the §7 acceleration
  (`E=50`), ~0.025 core-hours (~90 s).
- **Dominant cost in a from-scratch rigorous (Arb ball-arithmetic) reproduction** is not the `O(E²)` mesh
  evaluation (785,052 × 2,500 ≈ 2×10⁹ arithmetic ops — seconds to low minutes on one modern core even with
  a 10–50× ball-arithmetic constant-factor tax over plain floats) but the **`B_{i,j}` stored-sum precompute**:
  `O(N·E)` elementary-function evaluations (`log`, `exp` at the target 20-digit / ~70-bit precision, with
  headroom for the safety margin the paper itself uses — plausibly 128–256 bit working precision) per
  `t`-value, i.e. `69098 × 50 ≈ 3.45×10⁶` such evaluations × 152 `t`-values ≈ **5×10⁸ high-precision
  elementary-function ball evaluations**. At a rough 1–10 µs each (typical for Arb `log`/`exp` at a few
  hundred bits), that is **roughly 0.15–1.5 core-hours**, i.e. plausibly *comparable to or somewhat larger
  than* the paper's own 0.025-core-hour optimized run, with the gap explained by ball-arithmetic overhead
  and any extra precision margin taken for rigor. Add derivative-bound (Lemma 8.4) evaluation, which is the
  same order of cost as `f_t` itself, and generous engineering overhead (mesh count varies 11076→56 across
  152 `t`-steps, so the true mesh-point total needs re-deriving rather than assumed uniform — the 785,052
  figure already accounts for this), and a **single-core budget of roughly 1–10 core-hours** is a defensible
  planning number for a first rigorous reproduction attempt, with the usual caveat that precision-escalation
  retries (needed whenever a ball fails to exclude the target threshold) could push this up by a small
  constant factor and are not separately budgeted here.
- This is **dramatically cheaper** than Gate Step 4's ~19M-core-hour estimate for Phase 0's actual RH
  extension — consistent with `PROPOSAL.md`'s own remark that "barrier verification was fast relative to
  the asymptotic region even for the main theorem." The barrier is a good, cheap first target precisely
  because of this asymmetry: it is where a Gap-B rigor audit (re-running in certified Arb to confirm the
  headline Theorem 1.1 meets the ball-arithmetic standard) can be attempted without committing Phase 0-scale
  resources.
- **Not estimated here and explicitly out of scope:** reproducing Table 1 row 3 (X ≈ 2×10¹³) or beyond —
  that barrier is at a much larger `X`, needs a correspondingly larger `N0` (1,261,566 vs 69,098, an ~18×
  increase) and a fresh instance of the §8.1 ad hoc `X0`-search; cost there should be benchmarked
  separately (Gate Step 4 discipline applies) rather than extrapolated from this estimate.

## 9. Summary: which choices were feasibility-driven (the improvement search surface)

| Choice | Feasibility-driven? | Evidence |
|---|---|---|
| `t0 = y0 = 0.2` | Yes | §8.1: "due to the limitations of our numerical verifications" (bottlenecked on known RH-verification height, not on the barrier math) |
| `X0 = 6×10^10 + 83952` (the `83952` shift) | Yes | §8.1: explicit ad hoc scan over 7 candidates, arbitrary threshold "4" |
| Mollifier primes `{2,3,5}` (§8.5) | Yes | Footnote 7: "obtained after significant trial and error"; footnote explicitly says other mollifiers were tried and rejected as "inferior" |
| Taylor cutoff `E = 50` (§7) | Yes | Chosen for "adequate accuracy," not derived as optimal; paper notes a further speedup (splitting the summation range) was possible but "we did not need to exploit this" |
| Target precision (20 digits, 10 for the two highest Table 1 rows) | Yes | §10, explicit runtime/precision trade-off |
| `N0 = 69098`, `N1 = 1.5×10^6` region split (a)/(b)/(c) | Partially | Driven by which proof technique is tractable in which regime (holomorphic-and-small-N vs. mollified vs. crude-tail), an engineering decomposition rather than a value forced by the theorem |
| Table 1's target lower bound `0.03` for `|f_{t0}|` | Yes | §10: "we arbitrarily chose" |
| Theorem 1.2's hypotheses (i)-(iii) themselves | No | These are the actual mathematical content (Theorem 1.2's proof, §3) — not tunable |
| Lemma 8.4's derivative-bound *form* | No | Derived rigorously from Cauchy-Riemann + Lemma 5.1; only the resulting *numerical looseness* ("chosen quite conservatively") is a feasibility slack, not the bound's validity |

This table is the concrete answer to "which parameter choices were feasibility-driven": nearly every
*numerical* choice in §§7–8 (X0's shift, t0/y0, mollifier primes, Taylor cutoff, precision targets, Table
1's target bound) is explicitly, in the paper's own words, an ad hoc or arbitrary choice made for tractability
— none of them is claimed to be optimal. That gap between "sufficient" and "optimal" is exactly the surface
`ROADMAP.md` T5 points at when it lists "better barrier test functions" as an opening for genuinely new
technique, and it is a surface a systematic (rather than manual trial-and-error) search could plausibly
improve without any new theory — e.g. a real optimization over `(X0 shift, mollifier prime set, E)` jointly,
rather than the paper's sequential, hand-tuned choices.

## References

D.H.J. Polymath, *Effective approximation of heat flow evolution of the Riemann ξ function, and a new upper
bound for the de Bruijn-Newman constant*, Res. Math. Sci. 6 (2019); arXiv:1904.12438v2 (fetched and
`pdftotext`-extracted directly for this document) — Theorem 1.1, 1.2, 1.3, Corollary 1.4, Lemma 5.1, Lemma
8.2, Lemma 8.4, Proposition 8.1, §§7, 8.1–8.5, §10, Table 1. Cross-checked against `proposal/VERIFICATION.md`
(same paper, prior independent audit) and `proposal/PROPOSAL.md` §3 (Gap B). Code file names as cited in the
paper: `dbn_upper_bound/pari/barrier_multieval_t_agnostic.txt` (§7), `dbn_upper_bound/arb` (§8.4) — both in
the `km-git-acc/dbn_upper_bound` GitHub repository per `docs/STEP2_CODE_CUSTODY.md` item 2; neither file was
browsed directly (out of session scope pending user-authorized `add_repo`, per that document's follow-up
#3). python-flint capability check: `python3 -c "import flint"` → version 0.9.0, `dir(flint.acb)`,
`dir(flint.acb_series)`, `dir(flint.arb_series)` enumerated directly in this environment, July 24, 2026.
