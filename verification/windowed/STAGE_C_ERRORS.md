# Stage C Error-Term Accounting: Groundwork from Platt (2017) Appendices A-C

**Status:** M2 Stage C groundwork (not Stage C itself). This document extracts every
error-bound lemma from the primary source and maps it onto Stage A/B's actual error
sources (`prototype.py`, `stage_b.py`), per `DESIGN.md`'s Stage C task list. No lemma
below has yet been re-derived, adapted, or verified against our stack; this is a
reading/mapping pass, the prerequisite `DESIGN.md` calls for before any composition
work starts. **Nothing in this document may back a certified sign or feed
`rs_verify`-style certification.**

**Primary source:** David J. Platt, "Isolating some non-trivial zeros of zeta,"
*Math. Comp.* 86 (2017), 2449-2467. DOI 10.1090/mcom/3198. Text extracted from the
Bristol Research Portal author-accepted manuscript
(research-information.bris.ac.uk/ws/portalfiles/portal/78836669/platt_zeta_submitted.pdf),
confirmed page-for-page against the AMS abstract/DOI record. Lemma numbers, equation
numbers, and constants below are quoted directly from that text.

## 0. Recap: the 8-step algorithm and its object

Platt's windowed completed-zeta function (his eq. 3.1), with
`Lambda(t) = pi^(-it/2) * Gamma((1/2+it)/2) * zeta(1/2+it)`:

```
f(t) := Lambda(t + t0) * exp(pi(t+t0)/4 - t^2/2h^2)
```

Step (1) evaluates an analytic kernel `g(t;k) = Gamma((1/2+i(t+t0))/2) * exp(pi(t+t0)/4
- t^2/2h^2) * (-2*pi*i*t)^k` at a uniform lattice `n/A`, for derivative orders
`k = 0..K`. Steps (2)/(4)/(6)/(8) each approximate a periodized (aliased) sum by its
one visible term, discarding an infinite tail — these are the four bounds in
**Appendix A**. Steps (3)/(7) are exact discrete Fourier transforms (Lemma 3.1, via
Poisson summation) of length `N = AB`. Step (5) is the hard middle: recovering `F(m/B)`
(the transform of `f`) from `G(m/B)` and its derivatives via a residue term (Lemma 3.2)
plus a Taylor-expansion convolution truncated at `K` derivatives and `J` Dirichlet-series
terms (Lemma 3.3) — bounded in **Appendix B**. Zero isolation ("zoom in" to a sign
change) is a separate Whittaker-Shannon/Weiss up-sampling step using a second window
`W(t)` with independent Gaussian width `H` — bounded in **Appendix C**.

Tuned parameters from Platt's run (height 3.06e10, 300-bit MPFI): `h = 176431/2048`,
`J = 104000`, `K = 44`, `N = 2^15` upsampled to `2^20`, `B = 5476`, `A = N/B`,
up-sampling `H = 2089.0/16384.0`, `Ns` = 70 points either side of `t0`, stride 5.

## 1. Main-sum truncation

**What it means here:** cutting the Dirichlet series `zeta(s) = sum_j j^-s` at `J` terms
inside step (5)'s residue expansion (Lemma 3.2: `F(x) - sum_{j<=J} (...) = ...`).

**Platt's bound (Appendix B, Lemma B.1):** for `x >= 0`,
```
| sum_{j>J} (1/sqrt(j)) * pi^(-it0) * G(x + log(j*sqrt(pi))/2pi) |
    <= C(sigma, t0, h, 0) * exp((2*sigma-1)^2 / 8h^2) * pi^((1-2*sigma)/4) * J^(1-sigma) / (sigma-1)
```
where `C(sigma, t0, h, k)` is the master constant of Lemma A.3 (an explicit closed form
in incomplete-gamma terms). Decays polynomially in `J` like `J^(1-sigma)`, `sigma` a free
integer parameter `>1` chosen to trade off decay rate against the constant's size.

**Our analog (`prototype.py`/`stage_b.py`):** `N_TERMS` truncation of the direct
Riemann-Siegel-type sum `sum_{n=1}^{N} n^-1/2 exp(-i t log n)`. **Structural mismatch:**
Platt never sums over `n` directly at all in this part of the algorithm — his
"main sum" is the pole-residue Dirichlet re-expansion indexed by `j` (Lemma 3.2), a
different object from our direct main sum. Lemma B.1's bound is *not* transferable
as-is to our `N_TERMS` cutoff; ours would need either (a) a from-scratch tail bound on
`sum_{n>N} n^-1/2 exp(-i t log n)` (closer to classical Riemann-Siegel remainder theory,
not in this paper), or (b) restructuring Stage B to actually follow Lemma 3.2's
construction so Lemma B.1 applies directly. This is flagged in `DESIGN.md` (b)#1 and is
still open.

## 2. Euler-Maclaurin tail

**Platt's algorithm does not use Euler-Maclaurin at all.** Section 1.2 explicitly lists
Euler-Maclaurin as a competing *existing method* (O(t) time, single-point evaluation)
that his windowed-FFT approach is designed to amortize away — it never reappears in the
8-step procedure or in Appendices A-C. **There is no Platt lemma to extract here.**

Our `zeta_windowed()` (`prototype.py` lines 63-78, reused unchanged by `stage_b.py`)
uses classical Euler-Maclaurin (Bernoulli-number tail, `M_CORR` terms) as a
stand-in — `DESIGN.md`'s own docstring in `stage_b.py` calls this out ("Euler-Maclaurin
tail correction here, standing in for the paper's Taylor-convolution step"). Closing
this gap for Stage C means either (a) sourcing a standard Euler-Maclaurin remainder
bound from elsewhere (e.g. Apostol, cited as Platt's ref [3], or Odlyzko-Schönhage) —
genuinely outside this paper — or (b) replacing the EM tail with Platt's actual Lemma
3.2/3.3 construction, at which point this error source *disappears* and is subsumed by
§1 and §5 below. **This is the one error source in the task's list that Platt's paper
supplies no bound for at all.**

## 3. NUFFT kernel (the central architecture mismatch)

**Platt's method contains no NUFFT.** His step (1) evaluates the closed-form analytic
kernel `g(t;k)` directly at the uniform lattice points `n/A` it needs — there is no
nonuniform-frequency data anywhere in his construction, hence no gridding/deconvolution
step. The two DFTs (steps 3, 7) are plain uniform-to-uniform transforms of length
`N=AB`, justified purely by Poisson summation (Lemma 3.1). The relevant Appendix A
bounds are pointwise decay bounds on the kernel itself:

- **Lemma A.4:** `|g(t;k)| <= 4*(2*pi*|t|)^k * exp(-t^2/2h^2)`.
- **Lemma A.5** (step 2's aliasing tail, requires `B > h*sqrt(k)`):
```
| sum_{l != 0} g(n/A + lB; k) | <=
    8*(pi*B)^k * exp(-B^2/8h^2)
    + 2^(3k-1) * (h/B)^(k+1) * Gamma((k+1)/2, B^2/8h^2)
```

**Our Stage B is architecturally different.** `stage_b.py`'s `stage_b_lattice()` treats
the main sum's frequencies `log(n)` as genuinely *nonuniform* (they are, unlike
Platt's setup) and solves a **type-2 NUFFT** problem via Gaussian-kernel gridding
(Dutt-Rokhlin 1993 / Greengard-Lee 2004): each term is spread onto a fine oversampled
grid with a Gaussian spreading kernel of width `tau = (PTS_PER_STD * ds)^2 / 2`
(`grid_params()`, lines 64-79), pushed through one `acb.dft`, then divided by the
kernel's own Fourier transform `phi_hat = sqrt(4*pi*tau) * exp(-tau*(k*du)^2)` to
deconvolve. **This entire step, and its error, has no counterpart anywhere in
Appendices A-C** — Platt's paper never needed to solve a nonuniform-to-uniform
resampling problem, so there is no lemma to borrow. The relevant literature for this
error source is NUFFT accuracy theory itself (Dutt-Rokhlin's original error bound for
Gaussian gridding, or Greengard-Lee's refinement), not Platt (2017). This is the
single largest gap flagged for Stage C: **closing it requires importing and proving a
bound from a different paper family than the one this groundwork pass was scoped to
read**, and `DESIGN.md` (b)#3's "rigorous Nyquist-type argument" is stated as an
aliasing bound in the Platt sense, but our actual code's dominant unbounded error term
(gridding-kernel truncation at `half_supp` standard deviations, `PTS_PER_STD=3`) is a
*different* mathematical object from Platt's Lemma A.5-style aliasing tail.

## 4. DFT aliasing

**OCR-fidelity caveat:** the source PDF is a scanned/typeset two-column-free layout
with stacked fractions, multi-line exponents, and integral signs; `pdftotext -layout`
flattens these to plain text and can misplace which numerator/denominator or exponent
belongs to which symbol on dense multi-term lemmas (worst for A.7, A.9, A.11 below).
Every formula quoted here was reconstructed by pattern-matching against the paper's
own internal consistency (e.g. Lemma A.11's X/Y/Z should follow the same
`(...)^beta * exp(...)` / `Gamma(.,.)`-tail shape used identically in Lemmas A.5 and
A.10's proof) rather than read off a clean single line. Treat the *shape and which
lemma bounds which step* as solid; treat exact exponent placement in Y/Z-type terms as
**needing verification against the original PDF** before any of this is coded up.

**Platt's bounds (Appendix A, all four periodization tails, each requiring the
companion constant `C(sigma,t0,h,k)` from Lemma A.3):**

- **Lemma A.5** — step (2): quoted above (§3).
- **Lemma A.7** — step (4), the frequency-domain tail of `G^(k)`:
```
| sum_{l!=0} G^(k)(m/B + lA) | <=
    2^(k+3) * pi^(k+1) * exp(-t0^2/2h^2) * S
    + 2*(1 + 1/(A*pi*(2*sigma-1))) * C(sigma,t0,h,k) * exp((2sigma+1)^2/8h^2 - A*pi*(2sigma-1)/2)
```
  (`S` a finite sum defined in the lemma over `l = 0..(sigma-1)/2`).
- **Lemma A.9** — step (6), using the pointwise bound on `F` from Lemma A.8
  (`F(x) <= zeta(sigma)*pi^((1-2sigma)/4)*C(sigma,t0,h,0)*exp(...) + 2*pi^(5/4)*exp(...)`,
  picking up the simple pole of `zeta(s)` at `s=1` with residue 1):
```
|F~(n) - F(n/B)| <= 2*zeta(sigma)*pi^((1-2sigma)/4)*C(sigma,t0,h,0)*exp((2sigma-1)^2/8h^2
    - A*pi*(2sigma-1)/2)*(1+1/(A*pi*(2sigma-1))) + 4*pi^(5/4)*exp((1-4t0^2)/8h^2 - A*pi/2)*(1+1/(A*pi))
```
- **Lemma A.11** — step (8), using the pointwise bound on `f` from Lemma A.10
  (`|f(t)| <= 3*(t+t0)^beta * exp(-t^2/2h^2)`, `beta = 1/6 + loglog(t0)/log(t0)`, itself
  built on Platt-Trudgian's own explicit zeta bound `|zeta(1/2+it)| <= 0.732*t^(1/6)*log(t)`
  — ref [22], their own 2015 paper). Requires `beta*h^2/t0 <= B/2 <= t0`:
```
| sum_{l!=0} f((n-N/2)/A + lB) | <= 6*(X + (2^beta * h/B)*(Y+Z))
    X = (B/2 + t0)^beta * exp(-B^2/8h^2)
    Y = 2^(-1/2*beta) * t0^beta * Gamma(1/2, B^2/8h^2)
    Z = 2^(beta-1) * h^beta * Gamma((beta+1)/2, t0^2/2h^2)
```

**Our Stage B:** `stage_b.py`'s single `acb.dft` call over the oversampled grid of size
`M` is itself periodized (implicit period `M`), and its own aliasing behavior has not
been analyzed at all — no `Lemma A.5/A.7/A.9/A.11`-style bound has been written down
for our grid. Because our gridding/deconvolution step (§3) sits *upstream* of the one
DFT we do call, Platt's four-lemma structure (one bound per step, chained through two
separate DFTs) doesn't map one-to-one onto our single-DFT pipeline; the aliasing
question for us reduces to one bound instead of four, but that one bound still needs to
be derived fresh (it would need to account for both the NUFFT grid's periodicity *and*
the kernel gridding error of §3 jointly, since they're now coupled in one pass).

## 5. Deconvolution

**Platt's "deconvolution" is a Taylor-derivative expansion, not a spreading-kernel
division.** Step (5)'s Lemma 3.3 expresses `F(x)` as a double sum over derivative order
`k` (0..K) and lattice cell `m`, each `S_m^(k)` term being (essentially) `j`-weighted
finite differences of `log(j*sqrt(pi))/2pi` from the cell center `u_m`, truncated at
`k=K`, `xi = 1/2B`. The Taylor-truncation error is bounded in **Lemma B.2**:
```
| sum_{k>=K} G^(k)(u)*w^k / k! |  <=  2^(K + 5/2) * pi^(K + 1/2) * h^(K+1) * xi^K / Gamma((K+2)/2)
```
multiplied by `2*sqrt(J-1)` since (per the paper's own note directly after Lemma B.2)
this error recurs `J` times, each weighted by `1/sqrt(j)`.

**Our "deconvolution"** (`stage_b.py` line 118, `main = ds * fk / phi_hat * ...`) is
the standard NUFFT gridding-kernel division by the known closed-form transform of a
Gaussian spreading kernel — an entirely different mechanism serving an entirely
different purpose (undoing the spreading-onto-a-fine-grid step of §3, not truncating a
Taylor series in derivative order). **Lemma B.2 does not bound our deconvolution
error**; it bounds a Taylor-truncation error for a construction we don't use. Our
deconvolution's error is a NUFFT gridding/aliasing-in-the-Fourier-domain quantity,
again external to this paper (see §3).

## 6. Theta phase

**Platt never isolates `theta(t)` as a separate rigor-bearing quantity.** His `Lambda(t)
= pi^(-it/2)*Gamma((1/2+it)/2)*zeta(1/2+it)` folds the phase into the Gamma/pi factors
directly; the only place a Gamma-factor *magnitude* bound is needed is **Lemma A.2**:
```
Gamma((sigma+it)/2) * exp(pi*t/4)  <  2^((3-sigma)/4) * sqrt(pi*t)^(sigma-1) * exp((1+2*sqrt(2))/6t)
```
— used repeatedly inside Lemma A.3's constant `C(sigma,t0,h,k)`, itself feeding every
Appendix A/B bound above. There is no separate "phase error" lemma because Platt's
construction is real-valued by the functional equation (`f(t)` real by definition, per
the paper's remark right after eq. 3.1) — the phase is exact by construction, not
approximated.

**Our pipeline separates phase and magnitude explicitly** (`Z = Re[e^{i*theta(t)} *
zeta(1/2+it)]`), and Stage A/B both use `rs_verify.theta_asym` — the **non-rigorous**
asymptotic Riemann-Siegel theta (float, "heuristic use only" per its own docstring in
`rs_verify.py`), not `rs_verify.theta_ball`'s certified-ball version. This is the one
error source of the six that is *already solved elsewhere in our own codebase*
(`theta_ball`, ball-certified via `lgamma`) rather than needing anything from Platt —
Stage C just needs to swap `theta_asym` for `theta_ball` and account for the resulting
ball's radius in the final composition, not re-derive a new bound from the paper.

## 7. Composing into one final ball radius

**How Platt's own pieces compose** (implicit in the paper — steps 1-8 are not given a
single combined formula in the text, only per-step bounds; the composition below is our
synthesis of how they chain, not a quotation):

```
eps_f(n/A)  =  eps_step2(Lemma A.5)                         [main-sum-side aliasing]
             + eps_step4(Lemma A.7)                          [G-side aliasing]
             + eps_step5(Lemma B.1, J-truncation
                         + Lemma B.2, K-truncation)           [j-sum + Taylor truncation]
             + eps_step6(Lemma A.9)                           [F-side aliasing]
             + eps_step8(Lemma A.11)                          [f-side aliasing]
```
(steps 3/7's DFTs are exact under Lemma 3.1 and contribute no error of their own in the
paper's idealized/infinite-precision analysis — Platt's *floating-point* rounding on top
of this is a separate, additional 300-bit-precision interval-arithmetic overhead not
covered by Appendices A-C at all). For zero isolation, a further term is added from
**Appendix C** (Lemma C.1's band-limitation tail `I`, Lemma C.2's pointwise bound on
`W`, Lemma C.3's up-sampling truncation at `Ns` points) combined via Theorem 4.4
(Weiss): `|f(t) - sinc-interpolant| <= 4 * integral_{|x|>B} |F(x)| dx`, itself bounded by
`I` from Lemma C.1. Finally, Theorem 4.2 (Trudgian's Turing bound,
`|integral S(t) dt| <= 2.067 + 0.059*log(t2)` for `t2 > t1 > 168*pi`) supplies zero-count
completeness, independent of the above and already the basis of our own
`required_blocks()` in `rs_verify.py` (different constant packaging — Trudgian's later
Corollary 2.3 block-count form vs. this paper's direct integral form — but the same
underlying theorem lineage).

**What Stage C would actually have to compose, given our current Stage B code:**
```
eps_stageB(t)  =  eps_main_sum_truncation(N_TERMS)      [see-through: needs a fresh
                                                          bound, Lemma B.1 doesn't
                                                          transfer -- SS1]
                 + eps_euler_maclaurin_tail(M_CORR)      [no Platt lemma exists -- SS2]
                 + eps_nufft_gridding(tau, half_supp,     [no Platt lemma exists;
                                      OVERSAMPLE)          import from NUFFT theory -- SS3]
                 + eps_dft_aliasing(M, grid period)       [needs fresh derivation,
                                                           coupled to SS3 -- SS4]
                 + eps_deconvolution(phi_hat division)    [no Platt lemma exists;
                                                           part of SS3's NUFFT theory -- SS5]
                 + eps_theta_phase(theta_asym vs
                                    theta_ball)            [already solved -- swap in
                                                           rs_verify.theta_ball -- SS6]
                 + eps_acb_dft_rounding                    [already discharged by Arb,
                                                           per DESIGN.md (c) -- FREE]
```
Of the six requested error sources, only **§1 (main-sum, partial)**, **§4 (aliasing,
partial)**, and **§6 (theta phase, fully)** have any direct Platt lemma to draw on as
currently structured; **§2 (EM tail)** and **§3/§5 (NUFFT kernel/deconvolution)** have
*no counterpart in Platt (2017) at all* because Stage B's NUFFT-gridding architecture
solves a problem (nonuniform-frequency resampling) that Platt's algorithm never
encounters, having sidestepped it by construction (step 1 evaluates the kernel directly
on the uniform lattice it needs). **The only way to make Appendix A-C's exact lemmas
apply without modification is to restructure Stage B to follow the paper's literal
8-step construction** (analytic `g(t;k)` kernel evaluated on-lattice, Lemma 3.2/3.3
residue-and-Taylor recovery of `F`) instead of the current NUFFT-gridding shortcut —
which is a bigger rewrite than "add error bars to the existing code."

## 8. Status and next steps

This pass is reading/mapping only, per the instruction that groundwork precedes
composition. Nothing here is proven; every formula above is a direct transcription
from Platt (2017), quoted for reference, not yet checked against our own parameter
choices (`N_TERMS`, `tau`, `OVERSAMPLE`, `PTS_PER_STD` in `stage_b.py`) or adapted to
our NUFFT architecture. Next actual Stage C work, in tractability order: (a) swap
`theta_ball` for `theta_asym` in Stage A/B (§6, free); (b) decide whether to keep the
NUFFT architecture (requiring net-new NUFFT-accuracy-literature bounds for §3/§4/§5) or
rewrite Stage B to follow Platt's literal step (1)-(8) construction (making Appendix
A-C's lemmas apply directly, at the cost of losing the current gridding implementation);
(c) either way, source or derive an Euler-Maclaurin remainder bound or eliminate the EM
tail per the same rewrite decision (§2). Per `DESIGN.md`'s risk #3, the final
composition step across whichever bounds result is itself new work and the likeliest
place for a silent factor-of-2/constant error, so it should be built with a
cross-check against `rs_verify`'s certified values at every stage, exactly as Stage A/B
already do numerically.
