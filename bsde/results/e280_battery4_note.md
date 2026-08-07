# E280–E289 — fourth battery. **9 of 10 met.** The depth confound is cleared, and calibration works.

*2026-08-07. Predictions committed before any statistic existed. PERI = 2,589 cases; CTRL = 740 cases
at maintenance (arms 249/244/247, leakage null₉₅ ≈ 0.0511).*

---

## 1. The confound battery 3 never checked — raised, then cleared

**E280: the arms DO sit at different BIS.** des vs ppf **0.1218** against a null of 0.0510 (medians 38.7
vs 41.0); sevo vs des 0.0747; sevo vs ppf 0.0469. Prediction MET. If maintenance leakage were a depth
contrast in disguise, everything in battery 3 would need restating.

**E281 clears it, and clears it the strong way.** Matching arms 1:1 on control-window BIS (±3 units,
158/179/162 pairs, floor rising to ~0.063) leaves leakage **unchanged or larger**:

| pair | candidate | full | BIS-matched |
|---|---|---|---|
| sevo vs ppf | `whole_head_exponent` | 0.352 | **0.406** |
| des vs ppf | `whole_head_exponent` | 0.379 | **0.408** |
| des vs ppf | `multiscale_entropy_slope` | 0.387 | **0.432** |
| sevo vs des | `whole_head_exponent` | 0.103 | 0.076 |

Median retention **1.086** — leakage *rises* by 9 % under matching. Rule 17: when a fix makes the effect
stronger, the diagnosis was wrong. **Maintenance leakage is a drug signature, not a depth contrast.**
(Only sevo-vs-des attenuates, and that pair sits near the floor throughout.)

## 2. Per-drug calibration removes essentially all of it

**E283.** Subtracting each arm's own median and re-testing against a patient-level permutation null:
residual leakage is **at or below its null in 16 of 18 cells**. The two exceptions are `alpha_peak_hz`
(0.052 and 0.055 against ~0.051), i.e. marginal.

**E285 — the calibrated Challenge A screen is no longer empty, and the survivor is genuine.**
E279's only survivor was `emg_index`, the artefact channel. After per-drug centring:

    medians: state 0.1799 | residual PERI 0.0249 | residual CTRL 0.0238
    SURVIVOR: spectral_entropy   (non-muscle)

One real EEG measure clears above-median state tracking with below-median residual leakage at **both**
states. Prediction MET.

**The framing registered in advance, and it matters more than the result.** Per-drug centring requires
knowing the agent. In theatre the agent *is* known, so this is a deployable calibration — but it is a
different object from the agent-blind representation Challenge A's wording asks for. **The honest claim
is "a per-drug-calibrated measure can be agent-invariant here", not "we found an agent-invariant
measure."**

## 3. Transport works, against a placebo that actually tests transport

**E286.** A before/after threshold fitted on one arm and applied to another, with the rule-94-compliant
placebo (a threshold fitted for a *different* candidate on the same source arm — not a random threshold,
which tests whether a parameter is special rather than whether it transports):

| candidate | sevo→ppf | ppf→sevo | sevo→des | placebo |
|---|---|---|---|---|
| `whole_head_exponent` | 0.768→**0.785** | 0.808→0.768 | 0.768→0.764 | 0.555–0.585 |
| `multiscale_entropy_slope` | 0.716→**0.744** | 0.757→0.713 | 0.716→0.713 | 0.479–0.488 |

**Median transport loss +0.0042; beats the placebo in 10 of 12.** The state axis transports across
anaesthetic agents essentially intact — and in two cells it transports *better* than it fits at source.
The two failures are both `emg_beta_gamma_fraction`, whose placebo scores 0.745–0.757 because the
"wrong" measure is also a muscle measure. That is the placebo behaving correctly.

**E287** confirms the state axis is not depth-confined: `|signed mean| ≥ 0.15` in all three
pre-landmark BIS terciles for **6 of 6** top candidates.

## 4. Two more

**E288 — the maintenance estimates are resolved.** Split-half Spearman **+0.8596** across 19 candidates,
median absolute difference 0.0344. 740 cases *can* rank candidates at maintenance; battery 3's CTRL
rankings are not under-resolved.

**E289 — level dominates change at maintenance in 19 of 19 candidates**, even more decisively than
E254's 16 of 19 peri-landmark. Consistent with a per-drug offset and with E272/E283.

---

## 5. THE ONE THAT FAILED, AND WHY I AM NOT REPORTING THE p-VALUE INSTEAD

**E282.** E271's "monotone in 6 of 6" needed a null and now has one:

    observed monotone   6 of 6
    permuted null       mean 1.035, 95th percentile 4,   p = 0.0100

**My registered prediction was that the permuted 95th would be ≤ 2. It is 4. The prediction FAILS.**

The permutation p is 0.0100, and it would be easy to lead with that. I am not, because they are different
criteria and only one of them was committed to in advance. What actually happened is that **I mis-modelled
the null**: monotone runs across three terciles are far more common under permutation than I assumed, so
"6 of 6" is a weaker statement than it reads. The substantive claim — that the depth gradient is not
chance — survives at p = 0.0100 and should be quoted **as a permutation p, never as "6 of 6 monotone"**,
which is the phrasing that made it look decisive.

## 6. AND ONE THAT PASSED FOR THE WRONG REASON

**E284** returned `retained = 1.000` for all six candidates. I registered it as a near-tautology and
machinery check, and it passed — but the code centres **per case**, not **per arm**, and a within-patient
rank statistic is exactly invariant to a per-case constant. So it confirms the pipeline and **says nothing
about what per-arm calibration costs the state axis**, which is what E283/E285 actually rely on. That
question is unanswered. It is the same shape as E263's failure last battery — adjusting a statistic by
something it is mathematically invariant to — and it recurred despite being written up two hours earlier.

**The rule this earns: before registering an adjustment, apply it symbolically to the statistic and check
the statistic can move.** Twice in one session is enough to make it a standing check.

## 7. Where this leaves Challenge A on this deposit

* Agent identity at maintenance is real, large (0.35–0.43), **not** depth, **not** case mix, **not**
  signal quality, and reproducible across split halves.
* It is **almost entirely a per-drug location offset** — removable by a calibration constant the operating
  theatre already has.
* The state axis **transports across agents intact** and is not depth-confined.
* Agent-**blind** invariance: no candidate achieves it (E279).
  Agent-**calibrated** invariance: `spectral_entropy` achieves it (E285).

**That distinction is the deliverable, and it is sharper than anything the previous three batteries
produced.**
