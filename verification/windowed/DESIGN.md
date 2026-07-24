# Windowed multi-evaluation: design notes (H3 on-ramp)

Status: on-ramp / Stage A validated. This maps Platt's windowed-FFT
multi-evaluation idea (Platt, "Isolating some non-trivial zeros of zeta,"
Math. Comp. 86 (2017) 2449-2467) onto our stack (`verification/rs_verify.py`,
python-flint 0.9.0 / Arb, mpmath). It is a design document, not a proof:
Stage C is explicitly unfinished and requires re-deriving results from the
2017 paper's appendices (see docs/STEP2_CODE_CUSTODY.md item 1 -- no code
survives, only the paper).

## (a) The mathematical object

The naive approach certifies Z(t) one point at a time: each call costs
~O(sqrt(t)) work (the Riemann-Siegel main sum has ~sqrt(t/2*pi) terms),
independently repeated per t. Our benchmark (`verification/bench_window.py`,
fit in `verification/results/bench_window.json`) measures this scaling
empirically as ~T^0.46 wall-clock seconds per certified zero.

Platt's trick is to stop treating each t independently. Fix a window
center t0 and half-width h, and define the Gaussian-windowed completed
zeta function

    f(u) = Lambda(u + t0) * exp(pi*(u + t0)/4) * exp(-u^2 / (2*h^2))

where Lambda is the completed zeta function (so |Lambda(1/2+iu)| relates
to Z via a theta-factor) and the Gaussian factor exp(-u^2/(2h^2)) confines
the effective support to u in roughly [-6h, 6h] with negligible tail. Because
f is (to high accuracy) compactly supported and smooth, its Fourier
transform F(x) = integral f(u) e^{-2*pi*i*u*x} du decays fast, and a single
finite Riemann sum approximation of f -- sampled at a lattice of J points
spaced by 1/(some bandwidth) -- can be pushed through ONE forward DFT and
ONE inverse DFT (the "two DFT passes" in STEP2_CODE_CUSTODY item 1) to
recover accurate values of the completed zeta function (hence Z) at an
entire lattice of ~J points around t0 simultaneously, instead of running J
independent Riemann-Siegel evaluations. The "Taylor convolutions" step
handles points that fall between the DFT's natural output lattice via
local Taylor expansion (equivalently, Whittaker-Shannon / bandlimited
upsampling with a truncation-error bound -- STEP2_CODE_CUSTODY calls this
"Weiss-type error bound").

The payoff: for one window of ~J points, total cost is O(N + J log J)
(N = main-sum length, shared once; J log J = DFT cost) instead of O(J *
sqrt(t)) for J independent evaluations. At T=10^13, N ~ sqrt(T/2*pi) ~
1.26e6 and Platt used J = 104000 (upsampled to 2^20), so the amortization
factor is enormous -- consistent with the observed ~2500x gap between our
per-point cost model and Platt-Trudgian's reported throughput.

## (b) Rigor obligations vs heuristics

Rigor-bearing (must be proven / bounded, not just numerically checked):

1. **Main-sum truncation.** Where the Riemann-Siegel-type sum for the
   windowed function is cut off at N terms, the tail must be bounded above
   by a rigorous inequality (the 2017 paper's Lemma 3.2/3.3 territory), not
   just observed to be small on test points.
2. **Gaussian window truncation.** f(u) is only *effectively* compactly
   supported; discarding |u| > 6h (or wherever) requires a rigorous tail
   bound on the Gaussian factor times the growth rate of Lambda(u+t0) on
   vertical lines -- growth of zeta on the critical line is itself only
   known via explicit bounds (e.g. Backlund-type or the paper's own
   estimates), so this is not "small because Gaussian decays fast" without
   pairing it against an explicit growth bound for Lambda.
3. **Lattice aliasing / sampling.** Turning a continuous Fourier transform
   into a DFT means periodizing on a finite lattice; aliasing error (energy
   from outside one period folding back in) must be bounded, and the
   sampling rate must be proven sufficient (a rigorous Nyquist-type
   argument tied to the effective bandwidth of the windowed function).
4. **Ball propagation through the FFT.** Even granting a correct
   *un-rounded* transform, doing this in finite precision with Arb requires
   propagating interval/ball error through every butterfly stage (or,
   more simply, through whatever the DFT primitive contributes as its own
   ball error -- see (c)) plus the input quantization/windowing error into
   a final rigorous ball on each output Z-value. This composition step
   itself needs a lemma, not just "Arb balls are conservative so it's
   fine" -- error terms interact multiplicatively across steps 1-3 and 4.
5. **Whittaker-Shannon upsampling error.** The "Weiss-type error bound"
   mentioned in STEP2_CODE_CUSTODY for interpolating between DFT-native
   lattice points needs its own explicit, checkable inequality.

Heuristic (soundness of the final certified statement does not depend on
these, only its usefulness/completeness does -- same posture as
rs_verify's Gram-point placement):

- Choice of window center t0 and half-width h (affects efficiency, not
  correctness, as long as the rigor obligations above are met for the
  chosen h).
- Choice of lattice spacing / upsampling factor for convenience (as
  opposed to the *minimum* rate a Nyquist-type bound would require --
  over-sampling is heuristic slack, not a rigor question).
- Any Gram-point-based grid used downstream to decide *where* to look for
  sign changes once Z-values are in hand (same status as in rs_verify.py).

The dividing line mirrors rs_verify.py exactly: the certified *sign* of Z
at a given t must always be backed by a ball excluding 0. Everything about
*how efficiently* or *at which points* we choose to compute is heuristic.
A windowed-FFT Z-value inherits that same requirement -- it must land in a
ball with a proven (not just empirically observed) radius before any sign
claim drawn from it can enter a certification path.

## (c) What python-flint / Arb already provides

Checked directly against the installed python-flint 0.9.0 in this
environment (`python3 -c "from flint import acb; print(dir(acb))"`,
`help(acb.dft)`):

- **`acb.dft(vec, inverse=False)` exists** and is a genuine primitive: it
  takes an iterable of `acb` balls and returns their DFT as a list of
  `acb` balls -- i.e. **ball-arithmetic error propagation through the
  transform is already handled by Arb's `acb_dft`**, not something we'd
  need to build. Its own docstring example round-trips
  `dft(dft(range(1,12)), inverse=True)` and recovers rigorous balls
  containing the exact integers with radii ~1e-13 at default precision --
  concrete evidence the ball propagation obligation in (b)#4 for the raw
  transform step itself is *already discharged by Arb*, which meaningfully
  de-risks Stage C. (What Arb's ball propagation does NOT give us for free:
  the windowing/truncation/aliasing bounds in (b)#1-3/5, which are specific
  to *this* algorithm, not to DFTs in general.)
- Timing sanity check (non-power-of-two sizes 1000/2000/4000/8000 acb
  vectors at 100-bit precision): 5.5ms / 9.0ms / 16.6ms / 34.9ms --
  consistent with an O(n log n) algorithm (roughly linear growth, not
  quadratic), so Arb is not falling back to a naive O(n^2) DFT even off
  power-of-two sizes (Bluestein/mixed-radix, presumably, though the
  compiled `.so` gives no source to confirm the exact algorithm from this
  environment).
- **What's missing:** no exposed convolution primitive, no chirp-Z /
  Bluestein wrapper as a separate callable, no windowing function
  (Gaussian or otherwise), and no built-in Whittaker-Shannon / bandlimited
  interpolation helper. `dir(acb)` has no `convolve`, `fft`, `chirp`, or
  `window`-named entries. All of the *algorithm-specific* orchestration
  (building the windowed lattice, doing the Taylor-convolution correction
  step, tracking the aliasing/truncation bounds, gluing the theta-factor
  back on to recover real-valued Z from complex Lambda) has to be written
  from scratch on top of the raw `acb.dft` primitive. `acb_theta`
  (`flint.types.acb_theta`) exists but is Riemann theta functions for
  abelian varieties -- unrelated name collision, not usable here.

Net assessment: the single scariest-looking primitive (rigorous DFT over
balls) is already available and validated as part of the substrate
(consistent with STEP2_CODE_CUSTODY's framing that "no low-level
ball-arithmetic zeta machinery needs reconstructing -- only the
windowing/FFT orchestration ... layers"). That reduces Stage B to
"orchestration over an existing rigorous primitive" rather than
"build a rigorous FFT from scratch." Stage C's error-term accounting
(items (b)#1,2,3,5) is unaffected by this and remains the hard,
paper-specific work.

## (d) Staged implementation plan

**Stage A -- brute-force windowed sum, no FFT (this on-ramp).**
Pick a window (t0, h). Evaluate the main Riemann-Siegel-type sum's
per-term data (n^-1/2, log n for n=1..N) ONCE. For each of ~50 lattice
points t in the window, reuse that per-term data to cheaply compute an
approximate Z(t) (Euler-Maclaurin tail correction here, standing in for
the paper's Taylor-convolution step) and validate purely by numeric
comparison against `rs_verify.z_ball` / `certified_sign`. No rigor claimed
for the approximation itself -- the certified reference is what validates
it. Implemented in `verification/windowed/prototype.py`; achieves max
deviation ~1.7e-9 over a t0=10000, h=2 window (target was 1e-6). This
demonstrates the *shape* of the amortization (shared per-term setup, cheap
per-point reuse) without yet claiming the FFT speedup or any rigor.

**Stage B -- FFT lattice evaluation.**
Replace Stage A's per-point O(N) phase sweep with a genuine single-shot
transform: build the windowed sample vector as `acb` balls (window
function applied to the main-sum terms, or to the assembled f(u) samples
per the paper's construction), call `acb.dft` once, and read off
Z-approximations at the whole DFT-native lattice simultaneously. This is
where the paper's exact 8-step procedure (window construction, forward
DFT, "Taylor convolutions" to shift on-lattice values to the desired
off-lattice t's, inverse DFT where applicable) needs to be followed
step-by-step, using `acb.dft` as the DFT engine. Deliverable: a lattice of
*ball-valued* Z-approximations, still without a rigorous truncation/
aliasing bound wired in (the balls from `acb.dft` are only as tight as the
rigor of the *inputs* fed to it -- garbage in, tight-but-meaningless balls
out, until Stage C's input-side bounds exist). Validate the same way as
Stage A: compare against `rs_verify` at scale, and confirm wall-clock
scaling actually beats the ~T^0.46 per-point baseline.

**Stage C -- rigorous error-term accounting (flagged, not attempted here).**
Requires re-deriving, from the 2017 paper's Appendices A-C (no surviving
code per docs/STEP2_CODE_CUSTODY.md item 1 -- Platt has been asked for
originals but reconstruction must be assumed necessary):

- The main-sum truncation bound (paper's Lemma-level statement bounding
  the tail of the windowed Riemann-Siegel-type sum by an explicit,
  computable quantity in terms of t0, h, N).
- The Gaussian window's effective-support bound, paired with an explicit
  growth bound for Lambda(u+t0) on the relevant vertical strip (needed
  jointly -- neither alone suffices).
- The DFT lattice's aliasing bound (a rigorous statement of "how much
  energy from outside one Nyquist period can fold back," as a function of
  sampling rate and the window's effective bandwidth).
- The Whittaker-Shannon/upsampling ("Weiss-type") interpolation error bound
  for reading off off-lattice t values.
- Composition of all of the above (b#1-3,5) plus Arb's own ball radius
  from `acb.dft` (b#4, already handled by Arb per (c)) into one final,
  provably-correct radius per output Z-value -- this composition lemma is
  itself new work, since it is specific to chaining these four error
  sources through this exact 8-step procedure, and nothing in Arb or
  python-flint does it automatically.

A from-scratch reimplementation must prove all of the above as explicit,
checkable inequalities (not just empirically verify smallness on sample
points, which is all Stage A/B do) before any Stage B/C output may feed
`rs_verify`-style sign certification or a Turing-method completeness
argument. Until Stage C exists, Stage B is a fast *heuristic* oracle for
where zeros probably are -- useful for guiding where to spend rigorous
per-point Riemann-Siegel evaluation, but not itself a certificate.

## Biggest risks for Stage C

1. **No surviving code or detailed pseudocode** (STEP2_CODE_CUSTODY item
   1) -- the paper is unusually explicit about parameters and step names
   but the actual constants inside Lemmas 3.2-3.3 and Appendices A-C have
   to be re-derived from the paper's math, not checked against a reference
   implementation. Any transcription error is invisible until it produces
   a wrong sign somewhere downstream.
2. **Growth bounds for Lambda/zeta on vertical strips near t0=10^13** are
   themselves nontrivial explicit-analytic-number-theory results (the kind
   of estimate that has its own literature and revision history, e.g.
   improving bounds on |zeta(1/2+it)|); the window-truncation bound in (b)
   #2 cannot be closed without picking a specific, currently-defensible
   such bound and re-verifying it is still state-of-the-art enough to give
   a useful (not just correct-but-vacuous) error term.
3. **Composing four independent error sources (main-sum truncation, window
   truncation, aliasing, upsampling) through two DFT passes into one final
   ball radius** is exactly the kind of multi-stage error-propagation proof
   that is easy to get *directionally* right but wrong by a constant factor
   or an order in some parameter -- and a factor-of-2 mistake here is far
   more dangerous than in Stage A/B (where wrongness just shows up as a
   larger deviation from the certified reference) because Stage C's whole
   purpose is to license *skipping* that reference check at scale.
