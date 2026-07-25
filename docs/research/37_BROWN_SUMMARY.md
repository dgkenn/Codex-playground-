# Burst suppression acts on the circulation as a distinct cortical state, not as anaesthetic depth

**A physiology finding from 1,859 propofol and 2,202 sevoflurane cases (VitalDB), with every claim's
falsification test stated and run.**

*Prepared for senior-advisor review. Effect sizes are small and stated plainly; two of three original headline
claims from an earlier draft have been retracted; six pre-registered predictions failed and are listed. Read
Section 6 before Section 2.*

---

## 1. The claim, in one paragraph

Within the same patient, at the same arterial pressure and the same anaesthetic concentration, a 30-second epoch
containing burst suppression is followed 60–120 s later by a fall in mean arterial pressure that is **not**
preceded by an equivalent fall. The fall is **vasodilatory** — measured cardiac output *rises* while systemic
vascular resistance falls — it scales with **cumulative dwell time** in the suppressed state on three independent
exposure axes, it resolves within four minutes of the state ending, and it is **abolished when a vasopressor is
running**. Critically, it is **specific to suppression**: slow-delta power and frontal alpha, the graded markers of
anaesthetic depth, carry no lead whatsoever. The effect is small (≈0.33 mmHg per suppressed epoch, ≈0.85 mmHg at
high occupancy) and does **not** increase time below any clinical hypotension threshold.

**Why it may be of interest:** it separates a *dynamical brain state* from *drug concentration* as the thing that
acts on the circulation. The relevant prior work (microneurography showing propofol cuts muscle sympathetic nerve
activity 76 ± 5 %) is about the **drug at induction** in 10–20 subjects. This is about the **state during
maintenance**, at fixed dose, within patient.

---

## 2. The evidence, and what each element rules out

| finding | estimate | what it excludes |
|---|---|---|
| forward-minus-backward asymmetry in ΔMAP | **−0.332 mmHg** [−0.430, −0.229] | shared contemporaneous state (would be time-symmetric) |
| slow-delta power, same model | **+0.023** [−0.047, +0.085] **ns** | anaesthetic depth as the operative variable |
| frontal alpha, same model | **+0.004** [−0.065, +0.074] **ns** | as above |
| measured cardiac output (EV1000, 704 cases) | **+0.273 %** [+0.140, +0.421] | myocardial depression (requires CO to *fall*) |
| systemic vascular resistance | −0.305 % | — |
| occupancy gradient (suppressed bins in last 5 min) | −0.14 → −0.42 → −0.64 → **−0.85 mmHg** | a threshold or all-or-none phenomenon |
| run-length gradient | −0.31 → −0.44 → −0.56 → −0.65 → **−0.70** | a transition/onset effect |
| within-bin depth gradient | −0.52 → −0.79 → −0.96 → −1.09 | — |
| decay after the episode ends | −0.63 → −0.30 → −0.23 → **−0.07 ns** | a persistent patient trajectory |
| **asymmetry at MAP ≥ 90 mmHg** | **−0.678** [−0.849, −0.518] | **reverse causation via cerebral hypoperfusion** |
| asymmetry at MAP < 70 mmHg | +0.116 [−0.061, +0.300] **ns** | — |
| **interaction when a vasopressor runs** | **+0.506** [+0.027, +1.099] — effect abolished | a non-vascular route |
| frontal EMG negative control | **+0.568** — opposite sign on every haemodynamic column | design artefact |
| monitor's own suppression ratio (independent instrument) | reproduces the association | detector artefact |
| pre-registered hold-out (random halves) | −0.313 vs −0.366, overlapping | overfitting to analytic choices |

**The autoregulation row is the strongest single result.** The standard rival — that low pressure causes
suppression by reducing cerebral perfusion — *requires* the association to concentrate at low pressure. It is
largest at MAP ≥ 90, where autoregulation fully protects perfusion, and vanishes below 70, exactly where
hypoperfusion would begin. That is the inverse of the rival's prediction.

---

## 3. Design

Estimator, identical throughout: within-case fixed effects (Frisch–Waugh–Lovell), adjusting for MAP(t),
anaesthetic concentration, the *rate of change* of concentration, and a pre-trend measured over [t−3k, t−2k];
rows restricted to bins holding both a forward and a backward neighbour so direction is the only thing that
differs; **case-level cluster bootstrap** intervals throughout (≈600,000 bins are ≈1,800 independent units, not
600,000).

Burst suppression is detected from the **raw EEG** (0.1 s frames, peak-to-peak < 8 µV, runs ≥ 0.5 s), never from
the proprietary depth index; the monitor's own suppression ratio is used only as an independent check.

---

## 4. Six pre-registered predictions that FAILED

Stated because they constrain the mechanism more than the successes do.

| prediction | result |
|---|---|
| larger effect in the elderly (less baroreflex reserve) | **reversed**, +0.718 difference |
| larger effect at higher anaesthetic concentration | **reversed**, +1.364 |
| the *transition into* suppression carries the signal | **refuted** — sustained beats onset in both cohorts |
| suppression blunts baroreflex gain | **null**, +0.0001 [−0.0044, +0.0045] |
| suppression precedes a fall in heart-rate variability | **null** — HRV moves symmetrically |
| pressure *recovers* (overshoots) after the episode | **failed** — it decays to zero, no rebound |

The first two are explained post hoc by suppression burden (young, low-dose patients are precisely the
low-burden patients), but that explanation was **not** registered and is not claimed. The baroreflex null is
uninformative: I measured 30-second-averaged heart rate against 60-second pressure changes, and the arterial
baroreflex acts over one to three heartbeats — **that claim was retracted**.

---

## 5. What is NOT supported

1. **No clinical hypotension benefit.** The effect does not increase time below 65 mmHg — the population
   attributable fraction is **−5.8 %** [−11.5, −0.5], and it is non-positive at every threshold from 55 to
   75 mmHg. This reconciles with the autoregulation result: suppression lowers pressure *from high starting
   points*, where a sub-millimetre displacement never crosses a clinical threshold. **Any claim that this
   identifies a modifiable cause of clinically-defined intraoperative hypotension is unsupported.**
2. **The AKI association is confounded.** Cumulative suppression predicts post-operative renal injury robustly
   (+3.44 pp/SD, and +3.89 on an absolute-rise definition that never divides by baseline). But suppression also
   "predicts" **pre-operative** creatinine (−0.226 mg/dL per SD), which is causally impossible — a negative-control
   outcome demonstrating residual patient-level confounding. It is an association, not a causal claim, and it is
   **not** mediated by hypotension.
3. **The ageing story does not exist here.** Age raises suppression strongly (+15.6 min/decade at matched dose,
   confirming the Purdon/Brown result), but age does **not** predict hypotensive minutes (+0.38 ns). There is
   nothing to mediate.
4. **The sympathetic step is inferred, not measured.** Sympathetic withdrawal is the established mechanism for
   propofol, but we have not measured it. HRV indexes cardiac vagal control; sequence-method baroreflex
   sensitivity was underpowered (5,839 bins). Mayer wave (~0.1 Hz) power in the arterial waveform is the correct
   instrument and extraction is in progress.
5. **The sub-minute temporal claim cannot be externally replicated.** A full survey (MIMIC-IV/III waveform, BDSP
   HEEDB / sah / I-CARE / PSG / ECG, UCLA MLORD) found **no** other dataset pairing high-resolution EEG with
   continuous arterial pressure, and VitalDB contains no third anaesthetic agent. Replication requires prospective
   collection.

---

## 6. Errors found and corrected during this analysis

Listed because they bear on how much confidence the surviving numbers deserve.

1. **Arterial pressure was never range-filtered.** 4.27 % of MAP values were ≤ 0 (minimum −78 mmHg; negative
   arterial pressure is impossible), producing ΔMAP values spanning −312 to +390 mmHg. **Every result was inflated
   about threefold.** Found because two scripts disagreed on row sets differing by 0.9 %. The case-level bootstrap
   did *not* catch it — cluster bootstrapping protects against correlated observations, not contaminated ones.
2. **The pre-trend covariate shared an endpoint with the backward outcome** (partial correlation 0.528), shrinking
   the backward coefficient while leaving the forward one untouched and inflating the asymmetry ~24 %.
3. **The two-phenotype dissociation was retracted** — tested as a formal interaction it is 1.08 [0.89, 1.32]. The
   original contrast was a difference-of-significance artefact between strata differing 14-fold in size.
4. **The significance criterion is not calibrated.** The EMG negative control is non-null under all three
   estimators, so "the interval excludes zero" cannot stand alone; a shared-bootstrap contrast against EMG is
   reported alongside every raw estimate.

---

## 7. What would most strengthen this next

1. **Mayer wave power** — the one available instrument that indexes *vasomotor* sympathetic outflow rather than
   cardiac autonomic control. Would close the mechanism with our own measurement rather than by citation.
2. **A prospective cohort with simultaneous EEG and an arterial line** — the only route to external replication of
   the temporal claim.
3. **`SLOWING.pth` from MORGOTH 2** (now accessible) as an independent, foundation-model-derived slow-activity
   measure. The slow-delta *null* currently carries the specificity claim; reproducing it with a wholly independent
   feature extractor would strengthen the argument materially.
