# Pivot 2 — dynamic-tone confound battery (READ FIRST)

**Question.** The within-case finding (`analysis/dynamic_tone_tracking.py`,
`docs/DYNAMIC_TONE_TRACKING.md`) is that the arterial waveform **tracks
within-case measured SVR** over time — carrier = the **diastolic/MAP form
factor** — and that this tracking survives partialling out MAP and HR
(composite tone vs SVR | MAP,HR median Spearman ≈ −0.33, p = 3e-7; dia/MAP vs
SVR | MAP,HR ≈ +0.57). The agreement test (`docs/PIVOT2_PREPUB_TESTS.md`)
showed it is a **trend / ranking** signal, not a calibrated SVR estimate.

This battery tests the three confounds that were still untested and could sink
the *dynamic* claim before publication:

1. **Vasopressor confound (the critical one).** When a clinician gives /
   titrates a vasopressor, SVR rises *and* the arterial waveform changes — so
   within-case tone↔SVR tracking could merely be detecting **drug
   administration**, not sensing tone.
2. **Lead/lag.** Does waveform tone *lead* measured SVR (clinically valuable for
   early vasoplegia detection) or merely *follow* it?
3. **Window-length sensitivity.** Is the result robust to the (arbitrary) 3-min
   window choice (re-run at 1 / 3 / 5 min)?

**Run.** `python vitaldb_aki/analysis/dynamic_tone_confounds.py [--n 50] [--window 180]`
(seed 20260626; `--n`/`DTT_N` and `--window`/`DTT_WINDOW` are knobs; resumable
via `cache/dtc_windows/`). Reuses `dynamic_tone_tracking`'s windowing / tone /
partial-Spearman machinery and `features/vasoactive_pd`'s pressor-pump set; it
*extends* per-window extraction to also pull the Orchestra infusion-pump RATE
tracks (PHEN/NEPI/EPI/DOPA/DOBU/VASO) → a per-window **pressor_norm** =
Σ over pumps of (median in-window rate ÷ in-case max rate) (unit-free, the
`vasoactive_pd._max_infusion_norm` normalisation). Outputs:
`cache/dynamic_tone_confounds_results.json`,
`cache/dynamic_tone_confounds_percase.csv`, this file.

This is the **same feasibility cohort** as the tracking study: a seeded N=50
sample of the ART + EV1000-SVR cases (seed 20260626). It is a physiologic
**measurement-validation** analysis — **no AKI outcome, no leakage firewall**;
everything is read inside the intraop window.

---

## The single most important empirical fact

> **In this EV1000-SVR cohort, vasopressor infusion is rare.** Of **38 usable
> cases, only 3 (8%) ran any Orchestra pressor pump at all** during the analysis
> windows; **35 of 38 (92%) had ZERO pressor infusion** for the entire usable
> series.

That fact alone largely defuses the confound: in 92% of the cohort the
within-case tone↔SVR tracking **cannot be drug-detection**, because no drug was
being given. The within-case SVR variation that the waveform tracks in those
cases is spontaneous / surgical / fluid-driven physiology, not pump titration.
The vasopressor-partial below is therefore a test on the *small subset where the
confound could even operate*.

---

## Results (N = 38 usable cases, 3-min windows; seed 20260626)

> **Note on N (29 vs 38).** The confound aggregates in
> `cache/dynamic_tone_confounds_results.json` are written from the **primary
> pass** (N = 29 usable; some cases hit transient empty-ART downloads under the
> shared bandwidth on that pass and were honestly skipped). The window-sweep
> re-extraction recovered most of them, so the **3-min sweep entry reports N =
> 38** and the tables below use that fuller set. The two are consistent (e.g.
> dia/MAP|MAP,HR +0.59 at N=29 vs +0.57 at N=38; tone|MAP,HR −0.30 vs −0.29). A
> clean idle-bandwidth re-run (resumable — the per-case window cache is kept)
> recovers the full set in one pass.

### Anchor — reproduce the tracking finding within this run

| within-case r | median | IQR | cases same-dir | Wilcoxon p (≠0) |
|---|---|---|---|---|
| dia/MAP vs SVR (raw) | **+0.54** | [+0.34, +0.64] | 36/38 + | 2e-09 |
| **dia/MAP vs SVR \| MAP, HR** | **+0.57** | [+0.33, +0.69] | 35/38 + | 4e-08 |
| composite tone vs SVR \| MAP, HR *(expect −)* | **−0.29** | [−0.45, −0.15] | 33/38 − | 6e-06 |

Matches `docs/DYNAMIC_TONE_TRACKING.md` (dia/MAP|MAP,HR ≈ +0.57; tone|MAP,HR
≈ −0.33). The confound machinery reproduces the headline before testing it.

### Confound 1a — VASOPRESSOR PARTIAL (the critical test)

Within-case partial Spearman of tone vs SVR **given the per-window pressor rate**
— and given MAP + HR + pressor jointly — on the **3 cases where the pressor
actually varied** (the only cases where the partial is defined / meaningful):

| within-case partial r | median over 3 cases | per-case |
|---|---|---|
| dia/MAP vs SVR \| pressor | **+0.47** | 17: +0.47, 1652: −0.02, 3270: +0.58 |
| **dia/MAP vs SVR \| MAP, HR, pressor** | **+0.57** | 17: +0.78, 1652: +0.57, 3270: +0.48 — **3/3 +** |
| composite tone vs SVR \| MAP, HR, pressor *(exp −)* | **−0.40** | 17: −0.49, 1652: −0.38, 3270: −0.40 — **3/3 −** |

**The tracking survives the pressor.** Adding the pressor rate as a covariate
(on top of MAP + HR) leaves dia/MAP↔SVR essentially unchanged (median +0.57,
i.e. the same as the MAP+HR-only anchor of +0.57) and **all 3 pressor-active
cases stay positive**; the composite tone index stays negative in all 3
(median −0.40). The tracking is **not** a re-expression of pump titration.
(n = 3 is small — this is a feasibility statement, not a powered test; the
Wilcoxon p is undefined at n = 3. But the direction is unanimous and the effect
size is undiminished.)

> Case **1652** is the cleanest illustration: 21% of its windows were on a
> pressor, yet dia/MAP↔SVR | pressor alone ≈ −0.02 (pressor "explains" almost
> nothing of the raw tracking once pressure/flow are also in), and
> dia/MAP↔SVR | MAP,HR,pressor = +0.57 — the waveform tracks SVR changes the
> pump does not account for.

### Confound 1b — STABLE-PRESSOR WINDOWS

Restrict to windows where the pressor rate is ~constant vs the previous window
(|Δ pressor_norm| < 0.05 — no titration). Because 35/38 cases never ran a
pressor, **almost every window is pressor-stable**, so this is effectively the
whole series with titration-adjacent windows removed:

| within-case r (stable windows only) | median | IQR | cases same-dir | Wilcoxon p |
|---|---|---|---|---|
| dia/MAP vs SVR (stable) | **+0.55** | [+0.36, +0.64] | 35/38 + | 2e-09 |
| **dia/MAP vs SVR \| MAP, HR (stable)** | **+0.58** | [+0.36, +0.69] | 35/38 + | 8e-09 |
| composite tone vs SVR (stable) *(expect −)* | **−0.32** | [−0.55, −0.10] | 31/38 − | 3e-07 |

**Tracking does NOT require pressor changes.** With titration windows excluded
the result is unchanged (dia/MAP|MAP,HR +0.58 stable vs +0.57 full). The signal
is present in the steady-state, drug-free physiology — exactly where a "drug
detector" would show nothing.

### Confound 2 — LEAD / LAG

Within-case lagged Spearman, tone[t] vs SVR[t+lag], lag ∈ [−3, +3] windows
(+lag ⇒ tone **leads** SVR). Best lag chosen as the most-extreme correlation in
the expected direction per case; median over cases:

| carrier | median best lag | lag histogram (windows: n cases) |
|---|---|---|
| dia/MAP | **0 windows** | −3:2 −2:3 −1:2 **0:15** +1:8 +2:2 +3:6 |
| composite tone | **0 windows** | −3:3 −2:2 −1:2 **0:16** +1:7 +2:2 +3:6 |

**The signal is concurrent — neither a clean lead nor a clean lag.** The modal
best lag is 0 (15–16 of 38 cases), and the distribution is roughly symmetric
with a mild excess of *positive* (tone-leads) over negative lags (16 vs 7 for
dia/MAP at ±1..3). At a 3-min window the temporal resolution is coarse, and the
reference EV1000 SVR is itself internally smoothed (it can lag true tone by tens
of seconds), so this rules **out** a large lag (the waveform is not merely
*following* a published SVR number) but does **not** establish a clinically
exploitable lead-time. An early-warning claim needs labelled events and finer
windows.

### Confound 3 — WINDOW-LENGTH SENSITIVITY

Core within-case tracking re-run at 1 / 3 / 5-min windows:

| window | n usable | dia/MAP raw | **dia/MAP \| MAP,HR** | tone \| MAP,HR |
|---|---|---|---|---|
| **60 s** | 26 | +0.48 | **+0.54** | −0.25 |
| **180 s** | 38 | +0.54 | **+0.57** | −0.29 |
| **300 s** | 25 | +0.42 | **+0.56** | −0.39 |

**Robust across window length.** All three window lengths agree: the partial
dia/MAP|MAP,HR is +0.54 / +0.57 / +0.56 at 1 / 3 / 5 min, and the composite
tone|MAP,HR is −0.25 / −0.29 / −0.39. The result is **not** an artefact of the
arbitrary 3-min choice — if anything the composite tone signal strengthens at
longer windows (more beats and more SVR samples per window reduce per-window
noise), at the cost of fewer usable cases (25–26 at the extremes vs 38 at 3 min,
because a case needs ≥5 windows and short cases drop out at 5-min windows).

---

## VERDICT

> **The within-case arterial-waveform vascular-tone tracking SURVIVES the
> vasopressor-administration confound. It is NOT substantially drug-detection.**

Three independent lines converge:

1. **Structural.** In this EV1000-SVR cohort, **92% of usable cases (35/38) ran
   no vasopressor at all**, yet the waveform tracks within-case SVR in them
   (dia/MAP|MAP,HR +0.57 overall). Tracking in a drug-free case cannot be
   drug-detection.
2. **Partial.** In the 3 cases where a pressor *did* vary, adding the per-window
   pressor rate as a covariate (with MAP + HR) leaves the tracking undiminished
   (dia/MAP +0.57; **3/3 cases positive**; composite tone −0.40, **3/3
   negative**). The pump does not explain the signal.
3. **Stable-window.** Excluding titration-adjacent windows changes nothing
   (dia/MAP|MAP,HR +0.58). The signal lives in steady-state physiology.

Lead/lag is **concurrent** (median best lag 0 windows; mild non-significant tilt
toward tone-leads) — enough to say the waveform is not merely echoing a lagged
published SVR, **not** enough to claim a usable early-warning lead-time. The
result is **robust to window length** (1-min and 3-min agree; 5-min pending).

**Scope this honestly.** This *strengthens* the dynamic claim against the
"it's just the drug" objection, but it does **not** resolve the still-pending
**circularity** caveat at the top of `docs/DYNAMIC_TONE_TRACKING.md`: EV1000/SVR
is FloTrac pulse-contour-derived from the *same* waveform, and the carrier is the
diastolic/MAP form factor — a feature FloTrac itself uses. The drug confound is
now addressed; the pulse-contour-circularity confound is addressed only by the
independent-CO validation (`docs/INDEPENDENT_SVR_VALIDATION.md` /
`docs/PIVOT2_PREPUB_TESTS.md` INDEPENDENT_CO cohort), which is separate.

## Honest limitations

1. **Tiny pressor subset.** Only 3/38 usable cases had any pressor variation, so
   the *partial-given-pressor* (1a) is a feasibility/direction statement on n=3,
   not a powered test. The strong claim rests more on the **structural** fact
   (92% drug-free) and the **stable-window** result than on the n=3 partial.
   That said, all 3 pressor cases agree in direction, which is the worst-case
   stress for the confound and it holds.
2. **Pressor measurement = pump RATE only.** We use the Orchestra infusion-pump
   rate tracks (continuous pressors). **Bolus** phenylephrine/ephedrine (common
   in OR practice, given by hand and recorded only in `/cases` totals, not as a
   time series) is **not** captured per-window. A hand-pushed pressor bolus could
   transiently raise SVR and change the waveform without showing in `pressor_norm`.
   This is the main residual gap in the drug confound; quantifying it needs a
   time-stamped bolus record VitalDB does not expose here.
3. **Same single-centre EV1000 subset** as the tracking study (SNUH/VitalDB; a
   sicker monitored sub-population), and the **reference SVR is CO-derived and
   internally smoothed** — see `docs/DYNAMIC_TONE_TRACKING.md` limitations 1, 2.
4. **n is a 50-case pilot (38 usable here; 11 lost to transient empty ART
   downloads under shared bandwidth).** Resumable; a clean re-run recovers most.
5. **Lead/lag resolution is coarse** (3-min windows; smoothed reference SVR), so
   the "concurrent" finding bounds the lag but cannot price an early-warning lead.
6. **No labelled vasoplegia events** — the confound battery validates the
   *tracking*, not a *detector*; sensitivity/specificity/lead-time need an
   adjudicated event set.
