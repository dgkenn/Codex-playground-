# Critical-Care / Anesthesia Measurement-Bias Batch (Cycle 9)

**Five pre-specified NEJM-tier ideas in critical care / anesthesia, run on MIMIC-IV
data already in hand.** All extend this project's one replicated positive template —
*measurement/definition bias that produces differential misclassification by subgroup*
(cf. the sodium/calcium work in docs 01–05). Every result below is from a real run;
nulls and confounds are reported, not hidden. Exact numbers, n's, and z-scores are
preserved from the analysis logs.

**Batch scorecard**

| # | Idea | Verdict | One-line result |
|---|------|---------|-----------------|
| 1 | Occult hypoxemia (SpO₂>SaO₂) by race → harm | **PARTIAL** | Racial direction replicates (occult OR 1.47); magnitude/harm **blocked** by arterial/venous SaO₂ contamination |
| 2 | Cuff-vs-arterial MAP discordance → under-titration | **DEMOTED by red-team** | Headline +14 mmHg / −0.645 was largely a regression-to-the-mean binning artifact (Bland-Altman-correct ≈ +1.5 mmHg); harm reverses to null on sustained hypotension; what survives (range compression, high-MAP under-read) is *known* device behavior |
| 3 | Personalized MAP floor for chronic HTN | **NULL / opposite** | Sub-65 harm interaction is significant in the *wrong* direction; "count<T" metric is a monotone artifact |
| 4 | **Creatinine-masked AKI by muscle mass (sex)** | **SURVIVES, reframed & demoted** | Effect robust (isolated-absolute-criterion sensitivity F 90.5% vs M 97.4%, OR 0.47–0.63 across baseline defs; artifact 1.295→0.999) — but **not novel** (already published), applies only to the *isolated absolute* criterion (full KDIGO misses no one here), and the whole effect sits in baseline <0.6 mg/dL where a 1.5× rise may be noise |
| 5 | Blood-gas vs lab glucose discordance in shock | **WEAK / mostly NULL** | Discordance real (SD 16) but widens at *high* glucose; no mortality signal; central lab is the bigger misser (opposite of hypothesis) |

---

## Idea 4 (WINNER) — The KDIGO absolute-increase AKI criterion under-diagnoses AKI in women

**Claim.** Serum creatinine generation scales with muscle mass. Women (and other
low-muscle patients) generate less creatinine, so an identical *proportional*
glomerular injury produces a *smaller absolute* creatinine rise. The KDIGO AKI
definition's **absolute criterion (rise ≥0.3 mg/dL in 48 h)** therefore systematically
**under-detects AKI in women**, and the widely-reported "men have more AKI" pattern is
substantially a **measurement-definition artifact**.

**Cohort.** MIMIC-IV admissions with ≥2 creatinine values: **n = 320,677**.
Proportionally-injured (max ratio ≥1.5× baseline): **n = 28,029**.

**Result 1 — absolute-criterion sensitivity among the proportionally-injured**

| Group | n | abs-criterion sensitivity | missed (masked) |
|-------|---|---------------------------|-----------------|
| Male | 14,255 | 0.974 | 366 |
| Female | 13,774 | **0.905** | 1,314 |
| Age <65 | 14,598 | 0.922 | 1,132 |
| Age ≥65 | 13,431 | 0.959 | 548 |
| M <65 | 7,792 | 0.965 | 275 |
| M ≥65 | 6,463 | 0.986 | 91 |
| **F <65** | 6,806 | **0.874** | 857 |
| F ≥65 | 6,968 | 0.934 | 457 |

Women with genuine ≥50% creatinine rises are **~3.6× more likely to be missed** by the
0.3 rule than men (9.5% vs 2.6% missed). The most-masked cell is younger women (F<65,
12.6% missed). Age runs *opposite* to the naive prediction (older patients have higher
baseline creatinine → larger absolute deltas → slightly better detection); **sex is the
real axis of masking.**

Logistic `P(meets abs ≥0.3 | proportionally injured)`:
**female OR 0.471 [0.409, 0.543], z = −10.45** — women roughly half as likely to cross the
absolute threshold at identical proportional injury.
*(z(baseline creatinine) shows near-separation collinearity — for fixed ratio, higher
baseline mechanically forces a larger absolute delta; reported for honesty, not
interpreted as a finding.)*

**Result 2 — mechanism, at matched proportional injury (ratio band 1.5–2.0×, n=19,224)**

| Group | n | mean baseline Cr | mean ratio | mean absolute Δ | abs-sens |
|-------|---|------------------|-----------|-----------------|----------|
| Male | 9,787 | 1.527 | 1.654 | **1.117** | 0.969 |
| Female | 9,437 | 1.171 | 1.656 | **0.853** | 0.883 |

Holding proportional injury essentially constant (ratio ≈1.65 in every group), women
have **lower baseline creatinine (1.17 vs 1.53)** and therefore a **smaller absolute rise
(0.85 vs 1.12 mg/dL)** — exactly the compressed-swing prediction.

**Result 3 — the artifactual disparity (all ≥2-creatinine admissions, n=320,677)**

| Definition | Male prevalence | Female prevalence | M/F ratio |
|-----------|-----------------|-------------------|-----------|
| Absolute (≥0.3 mg/dL) | 0.219 | 0.169 | **1.295** |
| Proportional (≥1.5×) | 0.0866 | 0.0866 | **0.999** |

The "men have ~30% more AKI" signal is an **artifact of the measurement definition**:
proportional injury is identical between sexes to three decimals; only the absolute rule
manufactures the male excess. This mirrors the sodium/calcium artifactual-disparity
payload (docs 01, 03) in a new, high-volume domain (AKI is one of the most-studied ICU
outcomes).

**Honest limits.**
- **Harm/mortality is confounded** and not claimed. Crude mortality among the
  proportionally-injured is *lower* in the masked (abs-negative) group (0.085 vs 0.152),
  and stays lower after adjustment (OR 0.553, z=−6.44) — because absolute-positive means a
  larger absolute swing (sicker), and because being flagged plausibly triggers
  nephrology/nephrotoxin-hold (a treatment-response confound running the other way). The
  design cannot isolate the harm of non-recognition. The defensible claims are the
  **definitional-sensitivity** and **artifactual-disparity** results.
- **External validation pending** (eICU creatinine + gender streaming at time of writing).
  The mechanism is arithmetic + physiology (lower muscle mass in women is universal), so it
  is expected to replicate; the value is confirming the artifactual-disparity magnitude
  generalizes.

> **Red-team verdict (independent re-run, 6 attacks): SURVIVES but must be REFRAMED and
> DEMOTED — not a discovery.** The *effect* is robust; the *framing* and *novelty* are not.
> - **FATAL to the literal claim** "KDIGO misses AKI in women": full KDIGO 2012 is *absolute
>   OR relative*, and every "masked" patient here is relative-positive by construction — so
>   full-guideline KDIGO misses **no one** in this cohort. The claim is only defensible about
>   the **isolated absolute criterion as commonly automated in EHR AKI alerts** (many real-time
>   CDS trigger on the 48h absolute rise alone because a reliable pre-admission baseline for the
>   ratio arm isn't available at the point of care).
> - **Not novel:** the mechanism (absolute-creatinine thresholds disadvantage low-muscle
>   women/elderly) is already published — *Nat Rev Nephrol* on sex/age bias in organ-failure
>   creatinine thresholds, and a Swiss *BMJ Public Health* POA-AKI cohort stating it explicitly.
>   Frame as **confirmatory large-N (US, n=320,677) replication + clean matched-band mechanistic
>   decomposition**, not discovery.
> - **Unresolved (cannot be fixed with this data):** the entire disparity is mathematically
>   confined to baseline creatinine **<0.6 mg/dL** (isolated <0.6 stratum: OR 0.491, women 65.6%
>   of it) — exactly the zone where a 1.5× rise (e.g. 0.4→0.6) is most plausibly assay/physiologic
>   noise rather than true GFR-reducing injury, and MIMIC has **no cystatin C / muscle-independent
>   GFR reference** to adjudicate. Present this transparently (the "restrict to baseline ≥0.6"
>   check is a tautology — sensitivity is forced to 1.0 there — so it is NOT a valid robustness test).
> - **Robustness that HELD (attacks that didn't land):** baseline definition (OR 0.467/0.467/0.633/0.471
>   across first / 24h / median / rolling-min); RTM/noise (baseline CV M 0.960 vs F 1.011 — no
>   sex noise excess); selection by number of draws (OR <1 across strata). The artifact ratio
>   (1.295 abs vs 0.999 proportional) holds across all four baseline definitions.
>
> **Net tightest defensible claim:** *In MIMIC-IV, among patients meeting KDIGO's proportional
> (≥1.5×) criterion, the isolated absolute (≥0.3 mg/dL/48h) criterion has significantly lower
> sensitivity in women (90.5% vs 97.4%; OR ~0.47–0.63), because lower baseline creatinine
> compresses the absolute delta for equivalent proportional injury — fully accounting for the raw
> ~30% male excess in absolute-defined AKI. Applies to isolated-absolute EHR alerting, replicates a
> known mechanism, and carries an unresolved caveat that the low-baseline stratum driving it cannot
> be confirmed as true injury without a GFR-independent marker.* Publishable as a **methods/quality
> letter**, not an NEJM flagship. External replication (eICU, streaming) + the corrected-calcium and
> two-method-discordance leads (docs 01–05, and lit-mining doc 07) remain the stronger program.

---

## Idea 2 (DEMOTED by hostile red-team) — Oscillometric cuff MAP discordance

> **Red-team verdict (independent re-run, `verify_attacks.py`): the novel claims do NOT
> survive.** Two attacks land:
> 1. **Regression-to-the-mean binning artifact (SERIOUS).** The headline table below bins the
>    difference `disc = cuff − art` by `art` — one of its own components — which mechanically
>    inflates the low-band mean. Redone on the Bland-Altman-correct x-axis `mean(art,cuff)`:
>    correlation **−0.645 → −0.295**, and the low-band bias **+14.42 → +1.49 mmHg** (a ~10×
>    collapse). Only the high-MAP under-read is comparatively robust (−16.43 → −12.14).
> 2. **Harm reverses (SERIOUS).** Restricting the under-titration test to *sustained*
>    hypotension (prior arterial reading also <65 within 10 min) flips **OR 0.822 (z=−4.19) →
>    1.14 (z=+0.84, ns)** — consistent with clinicians correctly ignoring transient/artifactual
>    low readings (underpowered subsample, 10% of pairs, so not dispositive but shifts the burden).
> 3. **Untestable population (SERIOUS).** Only 5.7% of admissions ever have an arterial line —
>    the sickest, and precisely the group where the true MAP *is* visible, so the "cuff masks
>    hypotension on the ward" story cannot be observed here, only inferred by analogy.
> 4. **Not novel.** What survives — cuff compresses dynamic range (Var(cuff)≈0.6×Var(art)) and
>    under-reads at high true MAP — is decades-old validated-device behavior.
>
> **Net: idea 2 is not a defensible novel finding.** Retained below for the record with the
> caveats inline. The genuine methodological lesson (bin differences by the Bland-Altman mean,
> never by a component) is logged in `../LESSONS.md`.

**Cohort.** BLACK/WHITE MIMIC-IV admissions; arterial MAP paired to nearest cuff
MAP within ±5 min → **232,656 pairs**.

**Mechanism (unambiguous).** cuff − arterial discordance by true arterial band:

| Arterial MAP band | n | mean cuff−art (mmHg) |
|-------------------|---|----------------------|
| <55 | 11,477 | **+14.42** |
| 55–65 | 35,352 | +3.88 |
| 65–75 | 62,540 | −0.14 |
| 75–90 | 70,571 | −5.06 |
| >90 | 52,716 | −16.43 |

corr(arterial, discordance) = **−0.645** — **but see red-team box: binning `disc` by `art`
inflates this; the Bland-Altman-correct correlation is −0.295 and the low-band bias ≈ +1.5 mmHg,
not +14.** Only the high-MAP under-read is robust.

**Occult hypotension** (arterial <65 but cuff ≥65): **20,139/46,829 = 43.0%** masked;
**male-skewed** (M 47.6% vs F 35.6%; race BLACK 45.0% vs WHITE 42.7%, underpowered).
*(BMI/obesity subgroup unavailable — no height field in MIMIC to compute BMI.)*

**Harm signal (does NOT survive).** Among arterial-<65 pairs, adjusted
`treated ~ occult + arterialMAP` (cluster-robust): occult OR 0.822, z=−4.19 in the naive test —
**but this reverses to OR 1.14 (z=+0.84, ns) when restricted to sustained hypotension** (red-team
attack 2), consistent with clinicians ignoring transient/artifactual low arterial readings.

**Honest limits.** AKI/mortality vs occult exposure run *protective* (OR 0.79/0.70) —
acuity-confounded (overt = both-low = crashing), not adjustable here; not a harm claim.
**Key caveat:** these patients *have* an arterial line, so clinicians can see the true MAP;
the −4.2σ under-titration signal despite that is notable but means the mechanism is best
read as **hypothesis-generating for the far larger ward cuff-only population** where no
arterial truth is visible.

---

## Idea 1 (PARTIAL) — Occult hypoxemia by race

Racial **direction replicates** Sjoding (NEJM 2020): among SpO₂ 92–96%, true SaO₂<88%
was 51.3% (Black) vs 41.8% (White), **adj OR 1.47 [1.18–1.82], z=+3.5**.

**Blocked on data quality.** MIMIC-IV labevents itemid **50817 ("Oxygen Saturation",
Blood Gas) mixes arterial and venous specimens** — the cached SaO₂ has p25=70, p10=57
(a venous SvO₂ ~60–75% cluster), so the "occult" magnitude and any harm estimate are
contaminated. The clean source is **chartevents itemid 220227 (Arterial O2 Saturation)**,
not in the local extract. Additionally, the naive occult-vs-overt mortality contrast is
fatally acuity-confounded (occult looked spuriously *protective*, OR 0.30, z=−11.0 —
because overt low-SpO₂ marks actively crashing patients). Idea 1 is the least novel of the
batch (replicates a known NEJM finding); **not pursued further** — arterial re-extraction
queued if the harm/threshold angle is revisited.

---

## Idea 3 (NULL / opposite) — Personalized MAP floor for chronic hypertensives

Hypothesis: chronic-HTN patients auto-regulate higher and need a higher MAP floor.
**Not supported.** Cohort: 33,861 ICU stays (HTN 22,510 / non-HTN 11,351). The interaction
`AKI ~ exposure_below65 × HTN` is **significant in the wrong direction** (interaction
z=−2.97, OR 0.893 — the same sub-65 exposure is *less* harmful in HTN patients), and HTN's
"optimal" threshold was equal-or-lower, never higher. **Methodological caveat:** "count of
readings below T" grows monotonically with T, so the apparent peak at the top of the tested
range is partly a metric artifact, not a physiologic floor — a true autoregulation floor
can't be localized from this design. Residual severity confounding (HTN patients older/sicker)
also remains. Dead end as posed.

---

## Idea 5 (WEAK / mostly NULL) — Blood-gas vs central-lab glucose discordance in shock

Paired **n=47,894** (±30 min); discordance (lab − BG) mean **+4.09, SD 16.14 mg/dL**.
Discordance widens modestly on vasopressors (`|disc| ~ onpressor` β=+0.55, z=+3.01) **but at
high glucose, not in the hypoglycemic range** (interaction null). Among true-hypoglycemia
events (n=1,091), 33.7% are discordant "misses" — and the **central lab, not the blood-gas
analyzer, is the bigger misser** (278 vs 90), opposite the hypothesis. Missed hypoglycemia
shows **no mortality signal** after adjusting for pressor acuity (OR 0.86, z=−1.03); pressor
status swamps everything (OR 3.99). A genuine discordance exists, but the
"widens-in-shock → misses-hypoglycemia → drives-death" chain is not borne out.

---

## Cross-batch lessons (also in `../LESSONS.md`)

1. **The measurement/definition-bias template keeps producing the wins** (idea 4 here; sodium/
   calcium earlier); causal/threshold hunts (ideas 3, 5) keep nulling — consistent with the
   project's meta-pattern.
2. **"Occult vs overt" outcome contrasts are fatally acuity-confounded** (ideas 1, 2, 4, 5 all
   hit this) — the clean signal is always *hold the true value fixed and test recognition/
   treatment*, never *contrast masked-vs-unmasked on mortality*.
3. **Definitional artifacts hide in headline disparities** — the male AKI excess (idea 4) and
   the racial dyselectrolytemia gaps (docs 01, 03) are the same phenomenon: a measurement
   rule, not biology, generates the disparity.
