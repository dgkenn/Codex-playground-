# E261–E269 — second battery. 7 of 9 predictions met, and two items needed correcting after the fact.

*2026-08-07. Predictions committed before any statistic existed. E260, the control-window extraction, is
running separately and is written up on its own.*

---

## 1. The corner is real — and it is the strongest thing in either battery

**E261.** E250 named a low-leakage / high-tracking corner off a 19-point scatter, which is not a result
until it beats a null (rule 47). Against the exhaustive enumeration of **all 11,628 equal-sized subsets**
of the panel:

    mean(state tracking - leakage) for the corner = +0.2332
    subset null 95th percentile                   = +0.1547
    p = 0.0003

**Corner members: `whole_head_exponent`, `multiscale_entropy_slope`, `spectral_edge_95`, `emg_index`,
`emg_beta_gamma_fraction`.** That is Challenge A's shape — measures that track the transition while
identifying the agent less than the panel typically does.

## 2. BIS leaks because of the spectral content we already measure

**E262.** Residualising BIS on the 19-candidate panel at patient level and re-running the leakage path:

| pair | BIS raw | residual | reduction | p (residual) |
|---|---|---|---|---|
| sevo vs des | 0.1198 | 0.0245 | **−79.5 %** | 0.1485 |
| sevo vs ppf | 0.0669 | 0.0331 | **−50.4 %** | 0.0090 |
| des vs ppf | 0.1832 | 0.0070 | **−96.2 %** | 0.7015 |

Prediction MET. **After adjustment BIS's leakage is at its null in 2 of 3 pairs.** The incumbent's
drug-dependence is not proprietary magic — it is the alpha, exponent and edge content of the same signal,
recombined. That makes E251 mechanistic rather than merely comparative.

**E269** puts a rank on it: BIS is **4th, 9th and 3rd of 20** in the extended panel — top third in 2 of 3
pairs, as predicted. The right sentence is "among the worst in the panel", not "unexceptional".

## 3. Three confounds tested and none of them explains it

**E264 — suppression.** Max suppression ratio per case has a median of **0.00 in every arm**; 87.8 % of
cases never exceed 0.5. Restricting to the 2,194 suppression-free cases leaves leakage essentially
unchanged. E248's assertion that SR is ~0 throughout is confirmed on this cohort rather than inherited.

**E265 — signal quality.** Prediction NOT MET, and in the reassuring direction. Restricting to
`meta_sqi >= 50` **increases** leakage for most top candidates (`alpha_peak_hz` sevo/ppf 0.154 → 0.207;
des/ppf 0.271 → 0.319). Leakage is not an artefact of the sensor failing, and it is not failing
differently by agent — it is *stronger* where the monitor says the signal is good. This is rule 52's
corollary used properly: the deposit's own quality flag, applied before anyone had to speculate.

**E268 — case mix.** Trimming each pair to the joint 10th–90th percentile overlap on age, BMI and
anaesthesia duration discards roughly half of every pair and leaves leakage where it was
(`alpha_peak_hz` des/ppf 0.271 → 0.262). The arm contrast is not a case-mix contrast.

**E266 — where the variance lives.** Spearman(between-patient variance share, leakage) = **+0.7474**
across 19 candidates. Leakage is carried by between-patient variance, which is the only place a
patient-level property *can* live. Consistent and unsurprising, and worth having stated.

---

## 4. TWO ITEMS I GOT WRONG, BOTH CAUGHT AFTER THE RUN

### E263 printed "retained 1.000" for every candidate, and that is an arithmetic impossibility, not a result

The design adjusted each candidate's **across-patient mean** of `AUC_i − 0.5` for a patient-level EMG
covariate by mean-centred linear regression. The adjusted mean is
`mean(w) − b·(mean(x) − mean(x)) = mean(w)`. **The statistic is invariant to the adjustment by
construction.** Every candidate returned exactly 1.000 because it had to. A gate that cannot move is not
a gate (rules 40, 55), and this one was checkable with one line of algebra before the run.

**Redone correctly**, comparing state tracking between high- and low-EMG patient strata:

| candidate | high-EMG | low-EMG | ratio |
|---|---|---|---|
| `whole_head_exponent` | −0.3353 | −0.3725 | 1.111 |
| `spectral_edge_95` | +0.3058 | +0.3311 | 1.083 |
| `multiscale_entropy_slope` | −0.2921 | −0.3266 | 1.118 |
| `emg_beta_gamma_fraction` | +0.3122 | +0.3498 | 1.120 |

**The substantive answer stands and is now actually tested**: a patient-level muscle trait does not
explain the state tracking, and if anything tracking is slightly *stronger* in low-EMG patients. Together
with E253's rule-13 failure last battery, muscle has now been asked about twice and answered once.

### E267 was not the replication I claimed, and correcting it REVERSES its verdict

As written, E267 recomputed leakage from the **pre-landmark median** while E250 used E248's
**all-window patient median**. Different statistic, so the halves were never a replication of E250. It
returned +0.0930 and +0.2526 and I would have reported the dissociation as failing to replicate.

**Re-run with E250's own definition:**

    half 0: Spearman = -0.1351      half 1: Spearman = -0.2825      full cohort: -0.1807

**Both halves negative, both bracketing the full-cohort value. The dissociation replicates.**

What is genuinely learned is narrower than either verdict: **the sign of this correlation depends on how
leakage is defined** — all-window median gives −0.18, pre-landmark level gives around +0.17 — and at
n = 19 candidates none of these is a strong correlation. **E261's corner test, at p = 0.0003 against an
exhaustive subset null, is the load-bearing evidence for the dissociation. The Spearman is not**, and last
turn I reported it as though it were.

---

## 5. A SECOND SMOKE DEFECT, DEEPER THAN THE FIRST

Battery 1's smoke permuted one global arm label, so items not using it ran unblinded. This battery fixed
that with a per-item `SMOKE_LABELS` declaration — **and it still did not work for E261 and E266**, because
those two read precomputed leakage from `e248_agent_leakage.json`. **A statistic loaded from disk cannot
be blinded by permuting labels in this process.** The permutation has nothing to act on.

**The rule: an item that imports a precomputed statistic is unblindable by an in-process smoke, and the
only honest options are to recompute it under the permutation or to declare the item unblinded.** Naming
the labels was necessary and not sufficient; what matters is whether every input is *derived* inside the
run.

## 6. What a successor owes

1. **E260's control windows** answer the placebo question these two batteries could not. In flight.
2. **Test the corner directly** rather than as a set contrast — a pre-registered head-to-head of
   `whole_head_exponent` against the panel median on both axes, in a held-out half.
3. **Never adjust a mean for a mean-centred covariate and call it a control** (E263). Stratify instead.
4. **Quote E261, not the Spearman**, wherever the dissociation is claimed.
