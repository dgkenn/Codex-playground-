# Deconfounding reflexive lab-triggered treatment: the assay-noise instrument (corrected design + identification)

**Purpose of this document.** The `/goal` is a *bulletproof, broadly-applicable* method to defeat
confounding-by-indication for reflexive, lab-triggered inpatient treatments (electrolyte repletion, PPI,
transfusion, insulin, …), where treatment is a near-deterministic function of a time-varying severity signal
that also drives the outcome. This is the corrected methodology after a hostile-referee red-team destroyed the
first implementation and a formal identification derivation fixed it. It supersedes the *design* described in
`ASSAY_NOISE_IV_RESULTS.md` (whose empirical numbers are now known to be contaminated — see §2).

---

## 1. The universal obstacle and why the noise instrument is the escape

Reflexive treatment fires when a **measured** lab `W` crosses a clinical flag `c` (e.g. Mg < 2.0 mg/dL). But
`W = T + ε`, where `T` is the *true* (latent) severity and `ε` is assay + short-term biologic noise. **Conditional
on the true value `T`, which side of the flag the noisy `W` lands on is as-good-as-random** — driven by lab
error, not prognosis. Among patients whose true value sits near the flag, the noise thus supplies an exogenous,
severity-independent nudge into/out of treatment: an instrument. It applies to *every* lab-flag-triggered
treatment, and its identifying assumption (analytic imprecision of a chemistry assay) is auditable and
severity-independent — a far more defensible foundation than provider-habit (exclusion fails) or smooth-density
RDD (no discontinuity here).

Every standard design provably fails on this structure (demonstrated on Mg repletion, MIMIC-IV):
RDD (no first-stage discontinuity — smooth dose-response); provider-preference IV (exclusion restriction fails,
habit ~ care intensity); within-patient FE (treated episode = sicker episode, +7.3 d LOS bias); IPTW
target-trial (RR 4.17, negative control fails). Solving it once, broadly, is the high-yield methods play.

---

## 2. What the first implementation got WRONG (the referee's fatal catch)

The first design used two pre-treatment draws `M1, M2`, severity control **T̂ = (M1+M2)/2**, and instrument
**Z = 1(M2 < 2.0)**. This is **not identified**, for a reason baked into the estimating equation:

> **The control shares noise with the instrument.** `T̂` contains `M2`, and `Z` is a function of `M2`. Holding
> `T̂` fixed, a lower `ε₂` (what pushed `M2` under the flag, raising `Z`) must be offset by a higher `M1` to keep
> the average fixed — so within a `T̂` stratum, `Z = 1` patients have systematically higher *true* severity.
> Conditioning on `T̂` therefore does **not** hold true severity constant across `Z`; it re-introduces
> confounding by indication, **biased toward false harm** (a within-stratum regression-to-the-mean / Berkson
> leak). The reported "balance passes" test was itself run on the contaminated control, so it does not license
> the exogeneity claim.

Consequently the previously reported first stage (+0.032), reduced form (+0.0015), and LATE (+0.045) are
**uninterpretable** and must not be cited or acted on. The fix is mechanical and cheap (§3–4).

Secondary but independently serious problems in the first cut: (i) delta-method CI on a ratio with a weak
(3.2 pp) first stage is anti-conservative → must use Anderson–Rubin / Fieller and lead with the **reduced-form
ITT**; (ii) `σ = 0.134` from 1–12 h draw-pairs conflates assay noise with true biologic drift → it is an
*upper bound* on pure analytic noise and must be re-estimated by inter-draw interval and severity stratum;
(iii) in-hospital mortality is a competing-risks / LOS-dependent outcome → balance LOS on `Z`, prefer 30/90-day;
(iv) requiring two pre-treatment draws selects *out* the sickest single-draw-then-treat patients (external
validity + possible collider); (v) heaping at the round threshold 2.0 needs a McCrary/CJM density test and a
donut hole.

---

## 3. The corrected design: leave-one-out severity control

Replace the leaky control with a **leave-one-out** severity proxy built from draws *other than* the one whose
noise supplies the instrument, so the control is independent of the instrument's noise.

For a hospitalization with ordered pre-treatment draws `W_{i1},…`, at a candidate decision draw `t`:

- Instrument: `Z_{it} = 1(W_{it} < c)`.
- Leave-one-out severity control: **T̂_{i,-t} = g(all draws except t)** — e.g. a local-linear / nearest-
  neighbor smoother of the patient's *own* trajectory evaluated at time τ_{it}, using only other draws. Under
  independent noise, `T̂_{i,-t} ⟂ ε_{it}` while still informative about `T_{it}` through the serial correlation
  of the true trajectory. (Single-draw practical fallback when only `M1` precedes: control on `M1` alone — no
  shared noise with `Z=1(M2<c)` — at the cost of a noisier severity proxy; report both.)
- Treatment: `D_{it}` = repletion within the decision window of draw `t`.
- Outcome: `Y_i` terminal (prefer 30-day mortality; report in-hospital with LOS balanced).

This is the same device jackknife/split-sample IV uses to purge own-observation noise from a control — here the
"other information" is the patient's *own* other draws (a within-subject analog Pei–Shen's cross-sectional
RDD-with-error has no counterpart for).

---

## 4. Identification (single decision) and the renewal extension (power)

### 4.1 Assumptions
1. **Noise exogeneity | true severity:** `ε_{it} ⟂ (T-trajectory, potential outcomes, unmeasured confounders) | T_{it}`.
   We only need independence *conditional on the true value*, so heteroskedastic (severity-dependent) noise
   *level* is allowed; what is not allowed is the noise carrying outcome-relevant information beyond `T_{it}`.
2. **Exclusion at the flag:** crossing `c` changes `Y` only through the repletion decision `D_{it}` — no care
   bundle (extra telemetry, co-repletion, monitoring, attention). *The* substantive threat; falsifiable (§5).
3. **Leave-one-out control validity:** `T̂_{i,-t}` independent of `ε_{it}` (needs independent, or
   innovation-purged, noise across draws) and a good proxy for `T_{it}` (needs a smooth true trajectory; bias
   is `O(Δτ)` in the local sampling gap — testable by varying the smoother bandwidth).
4. **Monotonicity** (no defiers) conditional on eligibility and `T̂_{i,-t}`.
5. **Absorbing-treatment censoring:** once repleted, later draws leave the risk set; eligibility must be
   *predictable* (measurable before τ_{it}, excluding `D_{it}` and anything downstream) so restriction is a
   risk-set restriction, **not** collider conditioning.

### 4.2 Estimand
The **renewal-pooled LATE (RP-LATE)**: the average effect of repletion on the terminal outcome among
*noise-complier decision-nodes* — draws where the patient would be treated iff noise pushed `W` under the flag
— pooled over eligible nodes `E = {(i,t): not-yet-treated ∧ |T̂_{i,-t} − c| ≤ h}`. Crucially the bandwidth
window is evaluated on the **noise-free** proxy `T̂_{i,-t}`, not on the noisy `W_{it}`; defining eligibility on
the instrumented value (as naive pooling did) conditions on the instrument and biases/dilutes the first stage —
the exact reason naive pooling gave a degenerate ≈0 first stage.

### 4.3 Why restriction to `E` is not selection bias
`E`-membership is measurable w.r.t. variables that, conditional on `T_{it}`, are independent of `ε_{it}`
(not-yet-treated = pre-`t` history; near-margin = *other* draws' noise). So it is conditioning on a
pre-instrument covariate / risk-set restriction — not on a collider on the `Z→Y` path.

### 4.4 Estimator
Stacked 2SLS / just-identified GMM over `(i,t) ∈ E`: first stage `D_{it} ~ Z_{it} + f(T̂_{i,-t}) + X_i + t`;
structural `Y_i ~ D̂_{it} + f(T̂_{i,-t}) + X_i + t`. `Y_i` is repeated across a patient's eligible rows ⇒
**cluster SE on patient** (mechanical within-patient outcome correlation + serially-correlated noise); use
CR2 / wild-cluster bootstrap. Report a weight triad: per-draw, per-patient (`1/n_i^E`), and first-stage-strength.
Complementary assumption-light estimator: **near-far matching** (Baiocchi) of opposite-side draws within
`T̂_{i,-t}` calipers, matched-pair Wald ratio, patient-clustered randomization inference + Rosenbaum bounds.

### 4.5 Power — why the renewal structure recovers what the single draw throws away
Single-draw effective complier count ≈ `N × π₁` (one node/patient). The renewal design sums compliance events
over every eligible pre-absorption node: `≈ (Σ_i n_i^E) × π₁`. The IV concentration parameter scales with
`(Σ n_i^E) π₁² / σ_D²`, so effective sample multiplies by mean eligible-draws-per-patient `n̄^E` ⇒ ~`√n̄^E`
SE reduction — **without diluting `π₁`**, because we excised the post-treatment and off-margin draws that
dragged naive pooling to zero. Report the estimated effective noise-complier count vs. the single-draw count as
the headline power statistic. (The clustering correction keeps this honest — correlated rows are not free `n`.)

---

## 5. Falsification battery (run in this priority order; fail #1 ⇒ stop)

1. **Density-manipulation test** (McCrary / Cattaneo–Jansson–Ma) on `W` at `c`, plus histogram at 0.1 mg/dL
   resolution. A density jump / atom at the round threshold falsifies the local-continuity premise. If heaping
   at exactly 2.0 → **donut hole** (drop `W = c` ± one reporting unit) and test `<` vs `≤`.
2. **Leave-one-out re-estimation** (T̂_{i,-t} vs the old (M1+M2)/2): first stage, reduced form, balance. If the
   corrected result differs materially, the original was a shared-noise artifact (expected).
3. **Bundle-balance battery** — regress on `Z` (with the corrected control): time-to-next-electrolyte-panel,
   #labs next 24 h, K and Phos co-repletion orders, ICU transfer ≤24 h, LOS, and (ICU-only) telemetry/vitals
   cadence. Any discontinuity ⇒ exclusion fails ⇒ reduced form is an *intent-to-flag* effect, not a repletion
   effect. **Disclose that ward draws (chartevents ICU-only in MIMIC) cannot test bundle balance on the floor.**
4. **Weak-IV-robust inference:** Olea–Pflueger effective F; Anderson–Rubin / Fieller confidence set replacing
   the delta-method CI. **Lead with the reduced-form ITT**; treat LATE as fragile/exploratory.
5. **Selection-into-second-draw / eligibility:** characterize excluded single-draw-then-treat patients
   (severity, mortality); test whether provider / time-of-day predicts having another pre-treatment draw; test
   `Z ⟂ n_i^E`. Bound external-validity claims to "decisions preceded by a confirmatory draw."
6. **σ stability / classical-error check:** re-estimate noise SD by inter-draw interval (drift signature if σ
   grows with Δt → use shortest interval or model σ(Δt)→0), by severity stratum (heteroskedasticity), and by
   calendar period (assay/instrument recalibration); exclude pairs with any intervening intervention.
7. **Competing-risks / LOS outcome robustness:** balance LOS and discharge-to-hospice on `Z`; re-run with
   30/90-day mortality; Fine–Gray (death vs discharge-alive) instead of a binary in-hospital indicator.
8. **Bandwidth × functional-form sensitivity surface** (pre-registered grid, not a single spec); patient-level
   clustering for multi-admission patients; complier profiling (Abadie) + first-stage sign-stability across
   provider/shift/service subgroups as monotonicity probes.
9. **Serially-correlated-noise placebo (renewal-specific):** `Z_{it}` must not predict clearly non-affectable
   baseline covariates given `T̂_{i,-t}`; re-estimate `T̂_{i,-t}` excluding adjacent draws (t±1, t±2, …) — a
   stable `θ̂` across exclusion windows is reassuring; drift is a red flag.

---

## 6. Prior-art positioning (novelty is the renewal extension, not the core idea)
- **Core (single-decision) noise-induced randomization is PRIOR ART:** Eckles, Ignatiadis, Wager, Wu
  (*Biometrika* 2025); Pei–Shen (RDD-with-measurement-error, 2017); Barreca et al. (birthweight-heaping at
  1500 g — the closest clinical cousin, and the literature that had to solve this exact leaky-control problem).
- **Genuinely new + publishable:** (1) the **repeated / renewal** structure — a *sequence* of noise-randomized
  decisions per unit with an **absorbing** treatment (predictably censored to avoid collider conditioning) and
  a **terminal** shared outcome; (2) the **within-subject leave-one-out** control for a *serially-correlated
  latent state* using only noisy repeated measures of that same state; (3) the formal characterization of which
  interior nodes are legitimately noise-randomized (eligibility on the noise-free proxy) proven not to induce
  selection bias; (4) grounding the instrument in **CLIA/clinical-chemistry analytic imprecision** (auditable,
  severity-independent); (5) clinical operationalization for reflexive-care **de-implementation** + near-far
  matching to make a weak instrument usable. No existing noise-IV / RDD-with-error / MSM (needs sequential
  ignorability we reject) / IPSI (needs no-unmeasured-confounding we reject) framework provides this combination.
- **Complement, not competitor:** an incremental-propensity ("shift the flag") estimand (Kennedy) answers the
  policy-transportable dose-response question the local LATE cannot; report alongside. A **supply-shock DiD**
  (reagent stockouts / order-set rollouts / formulary switches) is unambiguously exogenous and a strong
  near-term design, but needs real-calendar data (MIMIC dates obfuscated).

---

## 7. Triangulation → reviewer-proof bounds (the packaging)
No single observational design is unimpeachable, so certify with **convergent partial identification**:
combine estimators with *known bias sign*. The naive/IPTW/within-patient/provider-IV designs are biased toward
**harm** (sicker → more treatment → worse outcome) → an upper bracket. A design biased toward **benefit** (e.g.
strata where the sickest are *withheld* treatment — renal impairment / hyper-electrolyte risk — or healthy-user
elective strata) → a lower bracket. The **assay-noise reduced form** (once corrected + falsification-passed) is
the approximately-unbiased anchor inside the bracket. If even the benefit-biased lower bracket excludes clinical
benefit, de-implementation is supported with honest, hostile-review-proof uncertainty. This converts
"triangulation" into formal Manski-style bounds and is what makes the package bulletproof rather than one
fragile estimate.

---

## 8. Status and next actions
- **Done (theory):** corrected identification (leave-one-out), renewal extension for power, full prioritized
  falsification battery, prior-art/novelty position, triangulation framing. This is the publishable methods core.
- **In progress (data):** re-streaming MIMIC-IV labevents (proxy-throttled ~200 KB/s; resumable) to RE-RUN the
  corrected design + falsification battery #1–#7 (the first-cut numbers are void per §2).
- **Then:** near-far matching + renewal estimator on Mg; replicate on K and Phos (stack flags for power);
  extend to the portfolio (PPI is the ideal RCT-vs-observational validation case); RESTRAINT RCT as the
  ground-truth anchor (RCT-DUPLICATE paradigm) that certifies the method for trial-infeasible questions.
- **Honest ledger:** we have a *valid corrected design + a novel power-recovering extension on paper*; we do
  **not** yet have a clean empirical estimate — the previous one was contaminated. Bulletproofing means the
  re-run must pass the battery, not just produce a number.
