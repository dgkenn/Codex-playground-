# Simulation study: which severity control identifies the assay-noise IV? (known-truth Monte Carlo)

**Why this exists.** A hostile-referee red-team claimed the first Mg design was "not identified" because the
severity control `T̂=(M1+M2)/2` shares noise with the instrument `Z=1(M2<flag)`, allegedly re-introducing
confounding, and prescribed dropping `M2` (control on `M1` alone). Before committing that fix I validated it in
a **known-truth Monte Carlo** (`docs/sim_assay_noise_iv.py`, N=200k/rep, σ=0.134). The simulation **refutes the specific
fix** and yields the correct, defensible prescription. This is the bulletproofing: an over-claimed refutation is
as damaging as an over-claimed finding.

## The data-generating process
True severity `T` (true serum Mg) ~ N(2.0, 0.22²); draws `W_j = T + ε_j`, ε ~ N(0, σ²). Reflexive treatment at
the decision node: `logit P(D)=a + b·1(W<flag) + g·(flag−T)` — the `b` term is the noise-instrument first
stage, the `g·(flag−T)` term is confounding by indication (sicker → treated more). Outcome (linear-probability):
`P(Y)=p0 + s·(flag−T) − θ·D` — sicker die more (`s>0`), and the **true causal risk difference of treatment is
−θ** (set to 0 and −0.03). Recovering −θ = success.

## Results (verbatim key rows)
| control | true RD 0 → LATE | balance on TRUE severity | true RD −0.03 → LATE |
|---|---|---|---|
| naive `Y~D` (no control) | **+0.014** (confounded) | — | −0.016 (confounded, attenuated) |
| **midpoint `(M1+M2)/2`** | **−0.002 ✓** | **balT +0.0000 ✓** | **−0.032 ✓** |
| `M1`-only ("drop M2") | **+0.062 ✗** | balT −0.120 ✗ | +0.032 ✗ |
| leave-one-out mean, k=9 draws | +0.016 | balT −0.025 | −0.011 |

### 1. The midpoint control is *unbiased*, not contaminated — under equal-variance noise
For symmetric Gaussian noise, conditional on `A=(M1+M2)/2` the instrument driver `∝(ε2−ε1)` is **orthogonal** to
the true-severity driver `∝(ε1+ε2)` because `Cov(ε2−ε1, ε1+ε2)=Var(ε2)−Var(ε1)=0`. So conditioning on the
midpoint exactly balances `Z ⟂ T` (balT = 0.0000, LATE recovers truth). The red-team's heuristic ("low M2
forces high M1 → sicker") ignored this cancellation. **The original age-balance test (+0.27 yr ≈ 0) was
therefore valid evidence, not an artifact.**

### 2. The prescribed fix (`M1`-only) is the biased one
Conditioning on `M1=T+ε1` alone leaves `ε1` driving **both** `Z=1(T+ε2<flag)` (via `T`) and the residual `T`,
so `Z` correlates with true severity within an `M1` stratum (balT −0.12) → LATE biased to +0.062. Dropping the
second draw does **not** clean the design; it breaks the symmetric cancellation that made the midpoint work.

### 3. The real vulnerability is ASYMMETRIC noise
Bias of the midpoint `∝ Var(ε2)−Var(ε1)`. With unequal draw noise (e.g. `sd1=0.08, sd2=0.20` — draws at
different times/analyzers/specimen quality) the midpoint breaks: LATE −0.065, balT +0.11. **Implication:** the
midpoint is defensible only when the two draws have (approximately) equal analytic variance — likely true in
MIMIC (same platform) but it must be **tested**, not assumed (σ by draw context / time-of-day / interval).

### 4. The renewal (many-draw) leave-one-out proxy is the robust general control
The leave-one-out mean of `k` other draws has variance `σ²/k` around `T`, so bias → 0 as `k` grows (balT
−0.12→−0.025 for k: 2→9). Under drift a *local* (nearest-neighbor) proxy is needed rather than a plain mean.
This is the identified, assumption-light control — and the same many-draw structure delivers the power gain:

### 5. Renewal recovers precision the single-draw design throws away
Over 40 replications (θ=0): single-draw LATE SD 0.021 vs pooled-renewal SD 0.009 → **variance ratio 5.8×,
i.e. renewal is 2.4× more precise.** Consistent with the concentration-parameter argument (effective sample ×
mean eligible-draws-per-patient).

## Corrected prescription (supersedes the "drop M2" fix)
1. **Primary control = midpoint / balanced multi-draw pre-decision average**, *after verifying equal draw
   variance* — NOT `M1`-only. Report the covariate-balance test as the empirical arbiter (it is valid here).
2. **Robust control = local leave-one-out proxy** over many pre-treatment draws (renewal design) → converges to
   true severity and simultaneously buys ~√(draws/patient) precision.
3. The genuine surviving threats from the red-team are unchanged and still gate "bulletproof": **weak first
   stage + delta-method CI (use Anderson–Rubin, lead with reduced-form ITT), care-bundle/exclusion (balance K
   co-repletion, telemetry, LOS on Z), competing-risks/LOS-dependent mortality (30/90-day, Fine–Gray), heaping
   at the round threshold (density test + donut hole), selection into ≥2 draws, and σ-symmetry/drift.**

## Status
The first-cut Mg result is **NOT void on the shared-noise grounds** (simulation-verified); the midpoint control
is defensible under equal-variance noise, which the real-data re-run will test directly. What still must pass
before any claim is the falsification battery above. Simulation output: `scratchpad/sim_results.txt`.
